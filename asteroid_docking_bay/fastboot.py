# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 Timo Könnecke (moWerk) <mo@mowerk.net>
# SPDX-FileCopyrightText: 2023 Ed Beroset <beroset@ieee.org>
"""Fastboot device polling, nightly download + verify, flash sequence."""

from __future__ import annotations

import time
from pathlib import Path

from .util import _run, log
from .usb import _sysfs_path_to_serial_map


# Cache: fastboot serial → product codename, populated on first getvar call.
_fastboot_products: dict[str, str] = {}


def _fastboot_devices() -> dict[str, str]:
    """Return {serial: state} for all fastboot-visible devices."""
    rc, out, _ = _run("fastboot devices", check=False)
    result: dict[str, str] = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            result[parts[0]] = parts[1]
    return result


_fb_list_cache: dict = {"ts": 0.0, "val": {}}


def _fastboot_list() -> dict[str, str | None]:
    """
    Return {serial: sysfs_usb_path} for devices in fastboot mode, from a cache
    refreshed by the background warmer (_fastboot_poll) — never blocks on the
    slow `fastboot devices` scan. The flash/onboard flows poll fastboot directly.
    sysfs_usb_path may be None if the device's path cannot be determined.
    """
    return _fb_list_cache["val"]


def _fastboot_poll() -> None:
    """Refresh the fastboot device cache. `fastboot devices` is a slow USB scan
    (5-8s when nothing is in fastboot and it ignores the subprocess timeout), so
    ONLY the background warmer calls this — never the status path."""
    rc, out, _ = _run("fastboot devices", check=False, timeout=8)
    serials = {parts[0] for line in out.splitlines()
               if len(parts := line.split()) >= 2 and parts[1] == "fastboot"}
    if not serials:
        result: dict[str, str | None] = {}
    else:
        path_by_serial = {s: p for p, s in _sysfs_path_to_serial_map(serials).items()}
        result = {serial: path_by_serial.get(serial) for serial in serials}
    _fb_list_cache["ts"] = time.time()
    _fb_list_cache["val"] = result


def _fastboot_getvar_product(serial: str) -> str | None:
    """
    Read the product codename from a fastboot device via 'getvar product'.
    Result is cached in _fastboot_products so repeated status polls don't re-call fastboot.
    fastboot writes getvar output to stderr, not stdout.
    """
    if serial in _fastboot_products:
        return _fastboot_products[serial]
    _, out, err = _run(f"fastboot -s {serial} getvar product", check=False, timeout=5)
    for line in (err + "\n" + out).splitlines():
        if "product:" in line.lower():
            val = line.split("product:", 1)[1].strip()
            if val:
                _fastboot_products[serial] = val
                return val
    return None


def fastboot_getvar_all(serial: str) -> str:
    """The device's full `getvar all` dump as text — the bootloader's ground
    truth: identity (product, serialno, boardid), BT/WLAN MACs, bootloader
    version, unlock/secure state, live battery-voltage + battery-soc-ok, and
    the partition table. Readable even on a watch too flat to boot.

    fastboot writes getvar output to stderr, and prefixes each line with
    "(bootloader) " — both are normalised here."""
    _, out, err = _run(f"fastboot -s {serial} getvar all", check=False, timeout=20)
    lines = []
    for line in (err + "\n" + out).splitlines():
        line = line.replace("(bootloader) ", "", 1).rstrip()
        if line and not line.startswith(("Finished.", "Total time:")):
            lines.append(line)
    return "\n".join(lines)


def _wait_for_fastboot(known_serials: set[str], timeout: int = 30) -> str | None:
    """Wait for a fastboot serial not present in known_serials."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for serial in _fastboot_devices():
            if serial not in known_serials:
                return serial
        time.sleep(1)
    return None


def _detect_rndis(ip: str = "192.168.2.15") -> bool:
    """Return True if a watch is reachable at `ip` (its SSH/RNDIS address)."""
    rc, _, _ = _run(f"ping -c1 -W2 {ip}", check=False)
    return rc == 0


def _switch_ssh_to_adb(ip: str = "192.168.2.15") -> dict:
    """Switch a watch that enumerated in SSH/developer USB mode over to adb_mode.
    The watch is reachable at `ip` — its assigned SSH address (192.168.2.15 by
    default, or the per-watch address handed out by allocate_ssh_ip). The switch
    re-enumerates the USB gadget and drops the ssh session, so a non-zero return
    is expected — success is the watch reappearing on adb, which the caller
    waits for. ok=False when nothing was reachable there, or when the watch's
    usb-moded refused the switch (printed an error while the link stayed up)."""
    if not _detect_rndis(ip):
        return {"ok": False, "error": f"no SSH watch reachable at {ip}"}
    _clear_ssh_known_hosts(ip)   # a fresh flash rotates the host key
    _, out, err = _run(
        "ssh -o StrictHostKeyChecking=no -o ConnectTimeout=6 "
        f"root@{ip} usb_moded_util -s adb_mode", check=False, timeout=15)
    if _usb_moded_switch_failed(out, err):
        return {"ok": False,
                "error": "usb-moded refused the switch on this watch (its "
                         "service may be down)"}
    return {"ok": True}


def _usb_moded_switch_failed(out: str, err: str) -> bool:
    """usb_moded_util prints its failure on stdout while still exiting 0; a
    switch that took would have dropped the link before any reply. So the error
    text, not the return code, is the signal that the mode did not change."""
    blob = f"{out} {err}".lower()
    return "not processed" in blob or "an error occured" in blob \
        or "an error occurred" in blob


def _download_nightly(codename: str, download_dir: Path, nightly_url: str, force: bool = False) -> tuple[Path, Path]:
    """
    Download nightly images for codename into download_dir, verify SHA512.
    Skips files that already exist and pass verification (unless force=True).
    Returns (boot_file, img_file).
    """
    download_dir.mkdir(parents=True, exist_ok=True)
    # AsteroidOS renamed the fastboot boot image from zImage-dtb-<codename>.fastboot
    # to asteroid-<codename>-boot.img (2026-07; both names still ship during the
    # transition, verified against release.asteroidos.org). The rootfs name is
    # unchanged. Flashed to the `boot` partition below.
    boot_name = f"asteroid-{codename}-boot.img"
    img_name  = f"asteroid-image-{codename}.rootfs.ext4"
    sha_name  = "SHA512SUMS"
    boot_file = download_dir / boot_name
    img_file  = download_dir / img_name
    sha_file  = download_dir / sha_name
    base_url  = f"{nightly_url}/{codename}"

    # Always fetch SHA512SUMS so we detect when a new nightly has landed.
    log.info("%s: fetching SHA512SUMS…", codename)
    _run(f"wget -q '{base_url}/{sha_name}' -O '{sha_file}'")

    for url, local_file in [(f"{base_url}/{boot_name}", boot_file),
                            (f"{base_url}/{img_name}",  img_file)]:
        if local_file.exists() and not force:
            rc, _, _ = _run(
                f"cd '{download_dir}' && grep '{local_file.name}' SHA512SUMS | sha512sum --check --quiet",
                check=False,
            )
            if rc == 0:
                log.info("%s: cached and verified — skipping", local_file.name)
                continue
            log.info("%s: cached but checksum mismatch — re-downloading", local_file.name)
        log.info("%s: downloading %s…", codename, local_file.name)
        _run(f"wget -q --show-progress '{url}' -O '{local_file}'")

    # Final verification of both files.
    rc, _, err = _run(
        f"cd '{download_dir}' && grep -E '{boot_name}|{img_name}' SHA512SUMS | sha512sum --check --quiet",
        check=False,
    )
    if rc != 0:
        raise RuntimeError(f"SHA512 verification failed for {codename}: {err}")
    log.info("%s: images verified OK", codename)
    return boot_file, img_file


def _flash_watch(boot_file: Path, img_file: Path, fb_serial: str | None, dry_run: bool = False):
    """
    Flash a watch already in fastboot mode.
    Permanent install: flash userdata + boot, then fastboot continue.
    """
    sflag = f"-s {fb_serial}" if fb_serial else ""

    def fb(subcmd: str, fatal: bool = True):
        cmd = f"fastboot {sflag} {subcmd}".strip()
        if dry_run:
            print(f"    [dry-run] {cmd}")
            return
        rc, _, err = _run(cmd, check=False)
        if rc != 0:
            if fatal:
                raise RuntimeError(f"{cmd}: {err.strip() or f'rc={rc}'}")
            log.info("%s: non-fatal (%s)", cmd, err.strip() or f"rc={rc}")

    # No `oem unlock` here: a watch already running AsteroidOS is unlocked by
    # definition (a locked bootloader wouldn't boot it), so unlocking on every
    # reflash is a pointless — and warranty-voiding — side effect. Unlocking a
    # still-locked WearOS watch is a deliberate, warned action of its own; see
    # the bootloader-unlock toggle in the roadmap (gated on WearOS detection).
    fb(f"flash userdata '{img_file}'")
    fb(f"flash boot '{boot_file}'")
    fb("continue")


def _clear_ssh_known_hosts(ip: str = "192.168.2.15"):
    """Remove stale SSH host keys left by the previous AsteroidOS install."""
    _run("ssh-keygen -R watch", check=False)
    _run(f"ssh-keygen -R {ip}", check=False)


