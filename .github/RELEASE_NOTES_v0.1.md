# asteroid-docking-bay 0.1 — first release

Fleet manager for AsteroidOS smartwatches: keeps a whole collection of watches docked on smart USB hubs, sustains every battery in a healthy 40–80% band, measures which batteries are still wearable, and flashes nightlies to real hardware across every codename you own.

The [README](https://github.com/moWerk/asteroid-docking-bay#readme) covers installation and day-to-day use. These notes are the technical companion: how the thing actually works, in enough detail to review it.

## No binaries, on purpose

There is nothing to build. The entire tool is one Python 3 file (`bin/asteroid-docking-bay`) using only the standard library; the web UI additionally needs `bottle` (pure Python, one `pip install`). External tools (`uhubctl`, `adb`, `fastboot`, `wget`) come from your distro. The auto-attached source tarball plus `./install.sh` is the complete distribution. Anyone "unable to build" is already covered, because there is no build.

## Provenance — read this if FOSS ethics matter to you

This codebase was written end-to-end by an LLM coding agent (Anthropic Claude), directed, tested, and reviewed by a human maintainer working purely from the user/tester side. Every feature was verified on real hardware (a mixed fleet of 2014–2018 AsteroidOS and Wear OS watches on Lenovo dock hubs) before its commit, and the commit history is the unedited record of that process, including the bugs, the wrong hypotheses, and the reverts. License is GPL-3.0-only; the flashing sequence derives from beroset's GPL-3.0 [asteroid-hosttools](https://github.com/beroset/asteroid-hosttools). If LLM-authored code is not compatible with your ethics, this project is not for you, and we would rather you know that from the release notes than from a diff.

Everything below is inspectable in the single source file; section names match the code comments.

## Architecture

One process per role, both from the same file:

- **CLI / timer process**: `map`, `status`, `on/off/cycle`, `charge`, `check-charge` (what the systemd timer runs), `test-ports`, `flash`, `discover`.
- **Web process** (`serve`, systemd user service): Bottle app on a threading WSGI server. All operation state (charge, drain, workbench, flash, remap tasks) lives server-side in per-slot dicts, so browser reloads and multiple clients see the same running operations. Long operations run in daemon threads with `threading.Event` cancellation; flash and remap stream their log output to the browser via SSE with heartbeats.

Ports are addressed as `location:port` slots (e.g. `1-6.4:2`), matching `uhubctl` and sysfs topology. Config is a single JSON file; every read-modify-write cycle is serialized by a config lock.

## Concurrency and queueing model

Three layers, from coarse to fine:

1. **ADB-heavy operations serialize**: charge, flash, and remap acquire a global in-process lock before powering a port on and hold it until the port is off again, so at most one such operation owns the bus at a time. Drain-test polls intentionally do not take this lock; each poll is a short power-on → read → power-off pinned to one port, and holding the global lock for a poll's full ADB wait (up to ~2 min) was observed to starve every other operation.
2. **uhubctl invocations serialize twice**: an in-process re-entrant lock, plus an exclusive `flock` on a lock file shared across processes. The second one exists because the web service and the periodic timer are separate processes, and concurrent uhubctl bus scans from two processes were observed to glitch dock ports mid-charge.
3. **Status is scanned once and cached**: one full `uhubctl` scan carries every port's power and connect state (no per-port subprocess fan-out), and the JSON status response is cached for 2 seconds behind a lock so parallel browser tabs share a single scan. Every state-changing endpoint invalidates the cache, so a post-action refresh never serves pre-action state.

## Power-switching verification (PPPS test)

The central lesson of this project: **hub status registers lie.** Hubs acknowledge power commands and toggle their status bit while VBUS stays live; conversely, a wedged hub can claim power while delivering nothing. The port test therefore never trusts the register and instead uses an evidence hierarchy:

1. **ADB drop**: the adb server actively talks to each device. If VBUS is really cut, the watch drops off `adb devices` within seconds. This is the primary proof.
2. **Watch-side power state**: if the device keeps chatting after "off", it is asked directly (`dumpsys battery` on Android-based watches) whether it still sees external power, which distinguishes a self-powered data link from an uncut VBUS.
3. **sysfs disappearance** counts as positive proof only. Persistence proves nothing, because these docks do not raise a disconnect event for a port they power off, leaving a stale kernel node behind while the device is dark.

Verdicts are three-valued and stored per port: `SMART` (VBUS cut confirmed by a live device), `NOT SMART` (device demonstrably kept power), `UNVERIFIED` (no device present to test against, e.g. an empty port). ADB samples taken from a just-crashed adb server are discarded, because its freshly restarted replacement briefly reports an empty device list, which would fake a "device dropped" confirmation.

## Charge algorithm

Charge-to-target, not charge-by-the-clock. A charge cycle powers the port, waits for the watch (with one automatic port power-cycle if it fails to enumerate, see hardware notes), then polls the battery every 2 minutes and stops exactly at `high_threshold` (default 80%), hard-capped by `charge_max_minutes` (default 240) so a broken battery read cannot charge forever. A watch already at or above target finishes immediately. Watches whose battery cannot be read fall back to a blind fixed-duration charge. Every poll also re-asserts port power: whatever cuts the port mid-charge (a concurrent process, a dock glitch) is noticed, logged, and re-powered instead of silently polling a dead port. Battery level is read from the standard Linux `power_supply` class over ADB shell in a single invocation. The same loop drives the manual CLI charge, the web Charge button, and the 12-hour systemd sustain timer.

## Drain test and wearability triage

A drain test measures true standby drain: power the port off and let the watch run on battery, waking it every 30 minutes for one battery reading (power on → wait for ADB → read → power off), until it reaches a 15% floor or is stopped. The drain rate is computed from timestamps, so delayed polls skew nothing. Results are written as JSON (one file per test, with the full reading series and the watch serial).

From the newest result per watch, the UI derives a **wearability verdict**: estimated 100→15% standby time (85 / rate). At or above `wearable_min_hours` (default 24) the watch is wearable; below it, it is a battery-swap candidate best kept as a dock-sustained dev unit. The verdict annotates the watch's row permanently and a history view lists every recorded test, so a rate rising across months exposes battery wear early.

## Workbench mode

Checked-out watches (hands-on development over WiFi/SSH) previously meant a powered dock pegging the battery at 100% for hours. Workbench mode holds the band during the session instead: charge to `high_threshold`, then rest with the port off, re-check every `workbench_poll_minutes` (default 30), recharge at `low_threshold`. If the battery cannot be read (USB switched to RNDIS/SSH mode) it degrades to a blind duty cycle (`workbench_blind_charge_minutes` of power per rest period). Charge, drain, and flash refuse on a checked-out watch, and vice versa. Returning the watch drops it back into the sustain fleet already inside the band.

## Live soft-remapping

Every status refresh maps each ADB-online watch's serial to its physical hub port via a single sysfs scan. When that disagrees with the config, the watch was demonstrably moved, and the mapping updates itself within one refresh cycle, including watch-swaps between ports. Only booted, ADB-visible watches are followed; moving a powered-off watch still needs one click on its new port. Each port also stores the exact serial last seen there (`port_serials`), which is preferred everywhere a port resolves to a serial. This closes the duplicate-codename ambiguity where two units of the same watch model answered for each other's battery readings and power actions. A watch's old seat is cleared only on positive evidence (an exact serial binding, or a fleet-wide unambiguous codename match); ambiguous cases leave the old mapping alone rather than guess.

## Flash pipeline

Per watch: download `zImage-dtb-<codename>.fastboot` and `asteroid-image-<codename>.rootfs.ext4` from the AsteroidOS nightly server with SHA512 verification (cached copies that pass the checksum are reused), power the port, wait for ADB (with an SSH/RNDIS-mode hint if the watch answers on the network instead), `adb reboot bootloader`, wait for the fastboot device, `fastboot flash userdata` + `flash boot` + `continue`, then clear stale SSH `known_hosts` entries. The web UI streams the whole run live into an inline log; the CLI flashes a list or the entire fleet sequentially and prints a summary. Failed watches stay powered for inspection.

## Hardware failure handling

Written against a misbehaving dock and kept because every fleet will eventually meet one of these:

- **Stale device nodes**: these docks raise no disconnect event for ports they power off, so dark devices linger in sysfs, and a lingering dark node makes the adb server's startup fail (`LIBUSB_ERROR_IO`), wedging ADB bus-wide. A plain off→on often does not re-enumerate past a stale node; a single-invocation `uhubctl` power *cycle* does. The drain-test read path and the PPPS test both use one automatic cycle as their recovery primitive.
- **adb server crashes** during device-disconnect storms are tolerated: device-list samples from a failed adb invocation are never treated as evidence.
- **UI diagnostics for dead watches**: a powered port whose hub sees a connection but where nothing enumerates for over 60 s is flagged "not enumerating" (the signature of a flat-battery boot loop, with a hint that fastboot draws little enough to charge past the boot threshold). A powered port with nothing electrically connected is flagged "not docked" instead of showing an ambiguous blank.

## Known limitations in 0.1

- Operation state (running charges, drain tests, workbench sessions) is in-memory in the web process; a service restart forfeits running operations (completed drain results are on disk and survive).
- The web service and the periodic timer coordinate at the USB-bus level (flock) but not at the decision level; running both against the same watch simultaneously can make opposing choices. The intended setup is web UI plus timer, where the timer's actions are idempotent, but a decision-level handoff is future work.
- Wearability estimates extrapolate linearly from measured drain; nonlinear discharge near empty is not modeled.
- Tested on Linux only, against Lenovo dock hubs and an AsteroidOS/Wear OS fleet. Tizen watches use `sdb`, not `adb`, and are invisible to the rig.

## Requirements

Python ≥ 3.9 (stdlib only), uhubctl, adb; fastboot and wget for flashing; bottle for the web UI; a hub that does true per-port VBUS switching (the built-in test will tell you honestly whether yours does).
