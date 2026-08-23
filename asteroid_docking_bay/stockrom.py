# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 Timo Könnecke (moWerk) <mo@mowerk.net>
"""Restore a watch to its stock ROM from a full-disk dump.

Users already do this by hand, brute-force, and arrive in chat afterwards —
so the risk of offering it is measured against THAT baseline, not against an
imaginary one where nobody tries. What a tool can add is the checking a person
cannot do by eye: that the image belongs to this model, and that the partitions
it writes are the ones that may safely be written.

Three rules carry the whole design, all of them learned from the manufacturer's
own flashing manifest (see the RAG, platform_and_build stock_rom_dump_and_restore):

1. A dump is trusted for what it CONTAINS, never for where it came from.
2. `userdata` is restored EMPTY, never from the capture. A populated userdata is
   encrypted against key material a stock restore erases, so writing it back
   boots to the vendor's spinner and never leaves it — the reason a beluga had
   never been successfully restored here before 2026-08-03.
3. Per-device state (calibration, radio NV, identity) is never taken from a
   dump of a DIFFERENT unit. It is not recoverable and nothing reports an error
   when it is wrong.
"""

from __future__ import annotations

import re
import struct
import subprocess
from pathlib import Path

from .util import log

GPT_SIG = b"EFI PART"
SECTOR = 512


class Partition:
    """One GPT entry. Sizes are derived, never stored twice."""

    __slots__ = ("name", "first_lba", "last_lba")

    def __init__(self, name: str, first_lba: int, last_lba: int):
        self.name, self.first_lba, self.last_lba = name, first_lba, last_lba

    @property
    def sectors(self) -> int:
        return self.last_lba - self.first_lba + 1

    @property
    def bytes(self) -> int:
        return self.sectors * SECTOR

    @property
    def offset(self) -> int:
        return self.first_lba * SECTOR

    def __eq__(self, other):
        return (isinstance(other, Partition) and self.name == other.name
                and self.first_lba == other.first_lba
                and self.last_lba == other.last_lba)

    def __repr__(self):
        return f"<{self.name} {self.first_lba}-{self.last_lba}>"


def parse_gpt(head: bytes) -> list[Partition]:
    """Partitions from the first sectors of a disk (or a dump of one).

    Reads the primary header at LBA 1 and the entry array it points at, so a
    disk whose entries do not start at the usual LBA 2 still parses. Returns []
    when there is no GPT rather than raising: callers treat "not a disk image"
    as a verification failure, not as a crash.
    """
    if len(head) < 2 * SECTOR or head[SECTOR:SECTOR + 8] != GPT_SIG:
        return []
    hdr = head[SECTOR:SECTOR + 92]
    ent_lba, n_ent, ent_sz = struct.unpack("<QII", hdr[72:88])
    if not (0 < ent_sz <= 4096) or n_ent > 4096:
        return []
    out, base = [], ent_lba * SECTOR
    for i in range(n_ent):
        off = base + i * ent_sz
        e = head[off:off + ent_sz]
        if len(e) < 56 or e[:16] == b"\0" * 16:
            continue
        first, last = struct.unpack("<QQ", e[32:48])
        name = e[56:128].decode("utf-16-le", "ignore").rstrip("\x00")
        if name:
            out.append(Partition(name, first, last))
    return out


# --- what may be written, and what may never be -----------------------------
#
# Straight out of the vendor's rawprogram manifest. Grouping by CLASS rather
# than listing partitions per operation is what keeps the dangerous ones from
# being swept into a convenient "restore everything" loop.

FIRMWARE = ("system", "vendor", "boot", "recovery", "cache", "oem",
            "splash", "LOGO", "modem", "opporeserve1", "opporeserve2",
            "sbl1", "sbl1bak", "aboot", "abootbak", "rpm", "rpmbak",
            "tz", "tzbak", "cmnlib", "cmnlibbak", "keymaster", "keymasterbak")

# Regenerated at first boot. Erasing them is how the vendor's own flow leaves
# them, and none of it identifies the device.
SAFE_ERASE = ("misc", "keystore", "config", "opporeserve3", "pad", "fsc",
              "ssd", "DDR")

# Calibration, radio NV, identity. The vendor erases some of these on a factory
# line, where the device is about to be re-provisioned anyway. We are not a
# factory line: on a watch in the field this data is irreplaceable and its loss
# is silent, so a-d-b neither writes nor erases it.
PER_DEVICE = ("persist", "oppodycnvbk", "oppostanvbk", "modemst1", "modemst2",
              "fsg", "sec", "devinfo")

USERDATA = "userdata"

# The subset proven to work on beluga by the community (MagneWater on reddit,
# confirmed still working 2026-06 by xuv). Deliberately smaller than FIRMWARE:
# it never touches the bootloader chain, so a failure cannot cost fastboot.
BELUGA_STAGE1 = ("boot", "system", "vendor", "recovery", "cache")


# --- families: the classes are per PORT, not universal ----------------------
#
# The lists above are the OPPO beluga rawprogram manifest, and the module used
# to apply them to every watch. That is wrong in a way that only showed up when
# a second family was proven: sol's restore writes `boot`,
# `vendor_kernel_boot`, `init_boot`, and only `boot` is in FIRMWARE — so a plan
# for the one family proven TWICE could not be built at all. Safe, since the
# allow-list fails closed, and useless.
#
# What actually decides the method is not A/B and not dynamic partitions, but
# WHAT THE ASTEROIDOS PORT WROTE (the porting session's finding, 2026-08-22).
# sol needs three partitions back because its port confined itself to the boot
# chain; beluga needed vendor and keystore because its port wrote them. A/B only
# changes how many copies get flashed, which is why `slots` is a separate axis
# from the class lists rather than the thing families are keyed on.

class Family:
    """One restore recipe: which partitions may be written, and how to finish.

    `per_device` is authoritative for what must NEVER be written. It is also
    knowingly INCOMPLETE outside the OPPO family — sol's own dump manifest
    reports 69 of 81 partitions as unclassified. That is safe only because
    classification is an allow-list: anything unrecognised is refused, so an
    incomplete list costs a refusal, never a silent write.
    """

    __slots__ = ("name", "firmware", "safe_erase", "per_device", "slots",
                 "finish", "note")

    def __init__(self, name, firmware, per_device, safe_erase=(), slots=(),
                 finish=(), note=""):
        self.name, self.firmware, self.per_device = name, firmware, per_device
        self.safe_erase, self.slots, self.finish, self.note = (
            safe_erase, slots, finish, note)


OPPO_BELUGA = Family(
    name="oppo-beluga",
    firmware=FIRMWARE, safe_erase=SAFE_ERASE, per_device=PER_DEVICE,
    finish=({"action": "flash_empty", "partition": USERDATA},),
    note=("Full restore: the port wrote system and vendor, so they must go "
          "back. userdata is written EMPTY from the factory image, never from "
          "the capture."))

W5100_BOOTCHAIN = Family(
    name="w5100-bootchain",
    # Exactly what sol's port writes, and nothing else. `super` is never
    # touched: this is not a firmware reinstall — put the boot chain back and
    # stock re-provisions itself.
    firmware=("boot", "vendor_kernel_boot", "init_boot"),
    # Known-incomplete on purpose; `sensorstore` is here because sol's dump
    # manifest identified it as per-device state that classify() did not know.
    per_device=("sensorstore", "persist", "modemst1", "modemst2", "devinfo"),
    # Both slots: the port writes whichever was active, and stock takes OTAs
    # across slots. A/B changes the COUNT of writes, not which partitions.
    slots=("a", "b"),
    finish=({"action": "erase", "partition": USERDATA},
            {"action": "set_active", "slot": "a"},
            # `continue`, never `reboot` — reboot landed in recovery three
            # times on sol. And never `fastboot -w`: it host-builds a
            # filesystem with mke2fs and erases metadata, leaving it raw, which
            # plain `erase userdata` does not undo.
            {"action": "continue"}),
    note=("First stock boot sits ambiguous for 30-40 minutes with adb silent. "
          "That is normal. adb staying silent afterwards is also correct — "
          "fresh Wear OS ships with developer options off."))

CLASSIC_BOOT = Family(
    name="classic",
    firmware=("boot",),
    per_device=PER_DEVICE,
    finish=({"action": "erase", "partition": USERDATA},),
    note=("Minimal method: stock boot plus a wiped userdata. Proven on sparrow "
          "and mooneye. Do NOT apply to a watch that already has a fuller "
          "recipe — beluga's sequence is canon and must not be shortened."))

FAMILIES = {
    OPPO_BELUGA.name: OPPO_BELUGA,
    W5100_BOOTCHAIN.name: W5100_BOOTCHAIN,
    CLASSIC_BOOT.name: CLASSIC_BOOT,
}


def classify(name: str, family: "Family | None" = None) -> str:
    """Which class a partition falls in, for THIS family.

    Defaults to the OPPO family so existing callers are unchanged. Anything
    unrecognised is `unknown`, and unknown is refused — unclassified is not
    the same as safe.
    """
    fam = family or OPPO_BELUGA
    if name == USERDATA:
        return "userdata"
    if name in fam.per_device:
        return "per_device"
    if name in fam.firmware:
        return "firmware"
    if name in fam.safe_erase:
        return "safe_erase"
    return "unknown"


def gpt_gate(dump: list[Partition], live: list[Partition]) -> tuple[bool, str]:
    """Cheap first gate: the dump's layout must match the watch's own.

    Everything up to `userdata` must agree on name AND position; `userdata` is
    last and grows to fill the disk, so it is expected to differ between units
    with different eMMC sizes and is excluded.

    This gate is NECESSARY BUT NOT SUFFICIENT and must never be the only check:
    beluga and belugaxl have byte-identical partition tables. It rejects a
    genuinely different device; it cannot tell two variants of one design apart.
    Use fingerprint_gate for that.
    """
    if not dump:
        return False, "no GPT in the dump — not a full-disk image"
    if not live:
        return False, "could not read the watch's own GPT"
    d = [p for p in dump if p.name != USERDATA]
    l = [p for p in live if p.name != USERDATA]
    if len(d) != len(l):
        return False, f"partition count differs: dump {len(d)}, watch {len(l)}"
    for a, b in zip(d, l):
        if a != b:
            return False, (f"layout differs at {a.name!r}: dump "
                           f"{a.first_lba}-{a.last_lba}, watch "
                           f"{b.first_lba}-{b.last_lba}")
    return True, f"{len(d)} partitions match exactly"


_FINGERPRINT = re.compile(rb"ro\.build\.fingerprint=([!-~]{1,120})")
_DEVICE = re.compile(rb"ro\.product\.(?:device|name)=([!-~]{1,40})")


def fingerprints(blob: bytes) -> set[str]:
    """Every build fingerprint in a raw partition image.

    Read straight out of the bytes rather than by mounting: the check must work
    on a dump file on a host that cannot mount the filesystem, and build.prop is
    plain text inside the image.
    """
    return {m.group(1).decode("ascii", "ignore")
            for m in _FINGERPRINT.finditer(blob)}


def devices(blob: bytes) -> set[str]:
    return {m.group(1).decode("ascii", "ignore")
            for m in _DEVICE.finditer(blob)}


def fingerprint_gate(dump_blob: bytes, expect_device: str) -> tuple[bool, str]:
    """The gate that actually establishes compatibility.

    A shared image may legitimately carry SEVERAL device names — beluga and
    belugaxl ship one system image naming both — so this asks whether the
    target is among them, not whether it is the only one.
    """
    found = devices(dump_blob)
    if not found:
        return False, "no ro.product.device in the image — cannot identify it"
    if expect_device not in found:
        return False, (f"image is for {sorted(found)}, "
                       f"but this watch reports {expect_device!r}")
    return True, f"image names {sorted(found)}, includes {expect_device!r}"


def restore_plan(parts: list[Partition], names: "tuple[str, ...]",
                 erase_safe: bool = False,
                 family: "Family | str | None" = None) -> list[dict]:
    """The ordered list of actions, with every one justified by its class.

    Refuses to build a plan that touches per-device state at all. That is a hard
    stop rather than a warning: the caller cannot opt in, because the damage is
    silent and unrecoverable and no UI affordance should exist for it.

    The family decides both the classes and how the run ends, because those
    differ per port rather than per watch: beluga finishes by writing an EMPTY
    userdata from the factory image, sol by erasing userdata, selecting slot a
    and issuing `continue`. A family with slots flashes every partition to each
    of them, since the port writes whichever slot was active and stock takes
    OTAs across both.
    """
    fam = FAMILIES[family] if isinstance(family, str) else (family or OPPO_BELUGA)
    by_name = {p.name: p for p in parts}
    plan: list[dict] = []
    for n in names:
        cls = classify(n, fam)
        if cls == "per_device":
            raise ValueError(f"refusing to restore per-device partition {n!r}")
        if cls != "firmware":
            raise ValueError(
                f"{n!r} is {cls} for family {fam.name!r}, not firmware — not "
                f"restorable. Unclassified is not the same as safe.")
        if n not in by_name:
            raise ValueError(f"{n!r} is not in this disk layout")
        if fam.slots:
            for slot in fam.slots:
                plan.append({"action": "flash", "partition": n,
                             "slot": slot, "part": by_name[n]})
        else:
            plan.append({"action": "flash", "partition": n, "part": by_name[n]})
    if erase_safe:
        for n in fam.safe_erase:
            if n in by_name:
                plan.append({"action": "erase", "partition": n})
    plan.extend(dict(step) for step in fam.finish)
    return plan


# --- how a dump may be taken, which is a DIFFERENT axis ---------------------
#
# The restore family is decided by what the port wrote. Dump availability is
# decided by what the bootloader will let you do, and the two do not line up.
#
# `initramfs_clean` is the one that needed writing down: it boots AsteroidOS's
# own initramfs from an init_boot FLASHED TO THE UNUSED SLOT, rather than via
# `fastboot boot`. That is why it works where the ramdisk method does not — it
# never asks the bootloader to boot an unsigned image — and it is structurally
# available exactly when the watch has a spare slot to flash into. Proven on
# sol 2026-08-08: two dumps of 31,406,948,352 bytes with IDENTICAL whole-image
# sha256, 81/81 partitions matching, userdata included, size checked against
# /sys/class/block/mmcblk0/size before the copy.
DUMP_METHODS = {
    "initramfs_clean": {
        "clean": True,
        "requires": ("unlocked bootloader", "A/B slots (a spare slot to flash "
                     "init_boot into)", "an AsteroidOS init_boot for this watch"),
        "note": ("userdata is never mounted, so the capture is byte-reproducible. "
                 "Does NOT need `fastboot boot`, which many bootloaders refuse "
                 "even when unlocked."),
    },
    "ramdisk_clean": {
        "clean": True,
        "requires": ("unlocked bootloader",
                     "`fastboot boot` of an unsigned image, at dump time"),
        "note": ("Crippled on many watches even after unlocking — it failed on "
                 "a locked nemo with 'not supported in locked device'."),
    },
    "runtime_unclean": {
        "clean": False,
        "requires": ("AsteroidOS installed and rooted",),
        "note": ("Taken from a live disk, so never byte-reproducible: on nemo "
                 "two runtime dumps matched on 33 of 34 partitions, differing "
                 "only in userdata. Trustworthy PER PARTITION, and two dumps "
                 "are what tell you which."),
    },
}


# --- the whitelist ----------------------------------------------------------
#
# A restore recipe is offered for a watch only when somebody has run it on that
# family and written down what happened. An entry is EVIDENCE, not an opinion,
# which is why each carries the date and unit it was proven on.
#
# Absence means refused, not "probably fine": a wrong recipe here costs a watch
# that cannot be re-provisioned, and the fleet has exactly one stock copy of
# some of these partitions in existence.
RESTORE_WHITELIST = {
    "beluga":   {"family": "oppo-beluga",
                 "proven": "2026-08-03, beluga 22979c8c, first attempt"},
    "belugaxl": {"family": "oppo-beluga",
                 "proven": "shares beluga's stock image and a byte-identical GPT"},
    "sparrow":  {"family": "classic", "proven": "2026-08-16, minimal method"},
    "mooneye":  {"family": "classic", "proven": "earlier, minimal method"},
    "sol":      {"family": "w5100-bootchain",
                 "proven": "twice: ~2026-08-09 and 2026-08-21, serial 4C111JEAYW00RJ"},
    # aurora is the same silicon and layout as sol, so the RECIPE is expected to
    # hold — but it has no dump of its own, and on these watches boot_b and
    # init_boot_b are the only stock copies that exist anywhere. The gate below
    # blocks it until one is taken, which is a precondition rather than a doubt
    # about the method.
    "aurora":   {"family": "w5100-bootchain",
                 "proven": None,
                 "note": "same layout as sol; needs its own verified dump first"},
}


def restore_method(codename: str, has_own_dump: "bool | None" = None) -> dict:
    """May this watch be restored, and how?

    Two preconditions, both learned the expensive way:

    * the family must be whitelisted — an unlisted watch is refused rather
      than guessed at;
    * a verified dump OF THIS UNIT must exist. Per-device state is not
      recoverable from another unit, and for the W5100 watches the stock boot
      chain exists nowhere else at all.
    """
    entry = RESTORE_WHITELIST.get((codename or "").lower())
    if not entry:
        return {"ok": False,
                "error": (f"{codename!r} is not whitelisted for restore. No "
                          f"recipe has been proven on its family, and guessing "
                          f"one risks a watch that cannot be re-provisioned.")}
    fam = FAMILIES[entry["family"]]
    if has_own_dump is False:
        return {"ok": False, "family": fam.name,
                "error": (f"{codename} has no verified dump of its own. Its "
                          f"stock partitions cannot be taken from another unit.")}
    return {"ok": True, "family": fam.name, "firmware": fam.firmware,
            "slots": fam.slots, "proven": entry.get("proven"),
            "note": entry.get("note") or fam.note,
            "unproven": entry.get("proven") is None}


def dump_methods_for(has_ab_slots: "bool | None",
                     can_fastboot_boot: "bool | None",
                     asteroid_installed: "bool | None") -> "list[str]":
    """Which dump methods this watch can actually offer, best first.

    Every input may be None, meaning "not established" — and an unknown
    capability yields no claim rather than an optimistic one, because the cost
    of being wrong is a user pushing a 741 MB rootfs and then discovering the
    bootloader refuses (which is exactly how the nemo attempt ended).
    """
    out = []
    if has_ab_slots:
        out.append("initramfs_clean")
    if can_fastboot_boot:
        out.append("ramdisk_clean")
    if asteroid_installed:
        out.append("runtime_unclean")
    return out


# --- host-side execution ----------------------------------------------------

def live_gpt(serial: str) -> list[Partition]:
    """The watch's own partition table, over adb. exec-out, not shell: shell
    mangles binary on some hosts and a corrupted GPT read would fail the gate
    for the wrong reason."""
    p = subprocess.run(["adb", "-s", serial, "exec-out",
                        "dd if=/dev/block/mmcblk0 bs=512 count=64 2>/dev/null"],
                       capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
    return parse_gpt(p.stdout)


def extract(dump_cmd: str, part: Partition, dest: str, extra_mb: int = 0) -> int:
    """Carve one partition out of a (possibly compressed) full-disk dump.

    Takes a shell command that STREAMS the image rather than a path, so a
    .tar.gz, a .zst and a raw .img are all the same to the caller and no 7.65 GB
    temporary copy is ever written.
    """
    skip = part.offset // (1024 * 1024)
    count = -(-part.bytes // (1024 * 1024)) + extra_mb
    if part.offset % (1024 * 1024):
        raise ValueError(f"{part.name} is not MiB-aligned; needs a byte-exact carve")
    cmd = (f"{dump_cmd} | dd bs=1M skip={skip} count={count} "
           f"iflag=fullblock 2>/dev/null > {dest}")
    subprocess.run(["bash", "-c", cmd], check=True,
                   stdin=subprocess.DEVNULL, timeout=3600)
    log.info("stockrom: extracted %s (%d MiB) -> %s", part.name, count, dest)
    return count


# --- taking a dump ----------------------------------------------------------

DUMP_ROOT = Path.home() / ".local/share/asteroid-docking-bay/dumps"


def dump_command(serial: str, ip: "str | None", dest: str) -> str:
    """The shell that streams a watch's whole disk into `dest`.

    Built as a string rather than run piecemeal because the copy has to be ONE
    pipeline: buffering 4 GB in the host process to hand it along would be
    slower and would turn a link hiccup into a lost dump instead of a short
    file. `ip` selects the link — SSH when the watch is in developer mode,
    otherwise adb exec-out, which is the binary-safe channel (`adb shell`
    mangles bytes on some hosts).
    """
    # serial is the device's own ro.serialno / USB iSerial — untrusted input on
    # a modded watch — and dest is a host path that may hold spaces; both land
    # in a `bash -c` string, so quote them. ip is internally allocated
    # (192.168.13.x) and constrained upstream.
    import shlex
    q_dest = shlex.quote(dest)
    if ip:
        return (f'ssh -o StrictHostKeyChecking=no -o ConnectTimeout=8 '
                f'root@{ip} "dd if=/dev/mmcblk0" | dd of={q_dest} bs=4096')
    return (f'adb -s {shlex.quote(serial)} exec-out "dd if=/dev/mmcblk0 2>/dev/null" '
            f'> {q_dest}')


NO_ROOT_BLOCKER = (
    "this watch answers, but will not let us read its disk. A stock Wear OS "
    "build runs the shell unprivileged and denies even the disk size. Dumping "
    "needs root: either AsteroidOS installed, or booted temporarily with "
    "`fastboot boot` — which needs an unlocked bootloader.")

UNREACHABLE_BLOCKER = (
    "cannot reach this watch to read its disk size — a dump that cannot be "
    "size-checked is not a backup.")


def disk_bytes(watch) -> "tuple[int | None, str | None]":
    """(size in bytes, reason it could not be read).

    Asked BEFORE the copy so a truncated result can be recognised as one: a
    short dump is the failure that hides best, because it looks like a file.

    The two failure modes are told apart deliberately. "Permission denied" and
    "no answer" both used to surface as "cannot reach this watch", which sends
    an operator chasing a connection problem that does not exist — measured on
    beluga 22979c8c, a Wear OS watch that answers every other command happily
    and refuses this one.
    """
    rc, out, err = watch.t.shell("cat /sys/class/block/mmcblk0/size", timeout=15)
    text = f"{out} {err}".lower()
    if "permission denied" in text or "denied" in text:
        return None, NO_ROOT_BLOCKER
    if rc != 0 or not out.strip():
        return None, UNREACHABLE_BLOCKER
    try:
        return int(out.strip()) * SECTOR, None
    except ValueError:
        return None, UNREACHABLE_BLOCKER


# How a dump is VERIFIED, as tooling rather than as prose.
#
# The method was already written down — the manifest tells you to take a second
# dump and compare per partition — and it was carried out once, by hand, for
# sol: 81 partitions, all matching. But the script that did it was never kept,
# so the instrument existed only as a report. This makes it re-runnable.
#
# What the comparison MEANS depends on how the dump was taken, and the
# difference is the whole point:
#
#   * A dump taken while the watch is RUNNING cannot have a matching userdata —
#     the filesystem is live and writes underneath the copy. Quiescent
#     partitions (firmware, boot, system) must still match exactly. So a
#     runtime pair that differs ONLY in userdata is a good pair; one whose
#     firmware differs means the copy is unreliable, not that the watch changed.
#   * A dump taken from an initramfs with userdata never mounted should match
#     everywhere, which is what makes that method the trustworthy one.
#
# Hashing is per partition and streamed, so comparing two 31 GB images costs
# one pass over each and never holds an image in memory.
_COMPARE_CHUNK = 8 * 1024 * 1024


def _hash_range(fh, start: int, length: int) -> str:
    """Streamed hash of one byte range, or "" past the end of the file."""
    import hashlib
    fh.seek(start)
    h = hashlib.sha256()
    left = length
    while left > 0:
        chunk = fh.read(min(_COMPARE_CHUNK, left))
        if not chunk:
            return ""            # truncated: the caller reports it as such
        h.update(chunk)
        left -= len(chunk)
    return h.hexdigest()[:16]


def compare_dumps(path_a, path_b) -> dict:
    """Per-partition comparison of two whole-disk dumps of the same watch.

    The partition table comes from dump A, deliberately: it describes the
    layout both images were taken with, and reading it from the live watch
    would let a later re-partition rewrite history.

    Returns {ok, sectors, partitions: [{name, class, mib, same, a, b}],
    same_count, differ, expected_differ, truncated} — where `expected_differ`
    is the set of partitions a RUNTIME dump is allowed to differ in (userdata
    and anything classified per-device), so a caller can tell an ordinary
    runtime pair from a bad copy.
    """
    a, b = Path(path_a), Path(path_b)
    head = a.open("rb").read(64 * 512)
    parts = parse_gpt(head)
    if not parts:
        return {"ok": False, "error": f"no readable GPT in {a.name}"}
    out, differ, expected, truncated = [], [], [], []
    with a.open("rb") as fa, b.open("rb") as fb:
        for part in parts:
            start, length = part.first_lba * SECTOR, part.bytes
            ha = _hash_range(fa, start, length)
            hb = _hash_range(fb, start, length)
            if not ha or not hb:
                truncated.append(part.name)
            same = bool(ha) and ha == hb
            cls = classify(part.name)
            if not same:
                # userdata and per-device state are EXPECTED to differ between
                # two runtime dumps; firmware differing means the copy is bad.
                (expected if cls in ("userdata", "per_device") else differ
                 ).append(part.name)
            out.append({"name": part.name, "class": cls,
                        "mib": round(length / (1024 * 1024), 1),
                        "same": same, "a": ha, "b": hb})
    return {"ok": True, "partitions": out, "same_count": sum(1 for p in out if p["same"]),
            "differ": differ, "expected_differ": expected, "truncated": truncated}


def write_manifest(path: Path, **fields) -> None:
    """Record what this dump IS, beside it.

    A filesystem timestamp is not a dump date — it is reset by any copy, which
    cost several exchanges of archaeology on 2026-08-03 to work out that an
    archive dated June had in fact been taken years earlier. The method matters
    too: a runtime capture is trustworthy per partition and never for userdata,
    and that distinction is lost the moment the file leaves this machine.
    """
    lines = [f"{k}: {v}" for k, v in fields.items() if v is not None]
    path.write_text("\n".join(lines) + "\n")
