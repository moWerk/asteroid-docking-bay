# asteroid-docking-bay 1.0 — release notes (DRAFT)

*192 commits since 0.9 (2026-07-31 → 2026-08-23). Suite 488 → 806 tests,
31 → 37 modules. Six audit records shipped in-repo.*

0.9 gave the rig Orbit and a fleet registry. **1.0 is about a-d-b being
usable by somebody who did not build it** — a first run that explains itself,
watches that stay visible however they are connected, and every destructive
path either refused, armed, or explained.

---

## Guided onboarding — new

A first-run flow that **opens by itself whenever nothing is mapped**, and is not
summonable any other way. It also returns after a config loss, which is exactly
when somebody needs it and would not think to look for it.

It starts from what is already plugged in rather than from a tidy empty bus:

- **a watch is already connected** → keep it on this port, or move it to a hub
- **nothing is connected** → straight into this computer, set up a hub first, or
  add one over WiFi by IP *or hostname* with nothing plugged in at all

Each step waits for hardware to confirm it happened. The bus must read empty
before a hub is registered, and exactly one watch may appear at a time — two at
once is the enumeration flood the sequence exists to prevent, and it hard-stops.

**A user is never asked for a codename.** The watch knows it, and a-d-b reads it
over whichever link reaches it — ADB, SSH, fastboot's `getvar product`, or
`getprop` on a Wear OS unit.

Finishing lands in user mode; skipping stays in developer mode. The last screen
offers to **park the rig**: switch the unused ports of switchable hubs off, one
at a time, never on a port with a watch on it.

While the panel is open, a-d-b **holds fleet-wide corrections**, so it never
reshapes the watch somebody is in the middle of plugging in.

## Watches are visible however they are connected

- **Direct USB** — a watch on a port no hub owns now has a row. Previously
  a-d-b could see it, talk to it and flash it while showing an empty table.
- **Non-PPPS hubs are discovered**, so a user with a plain hub is no longer told
  their hardware does not exist.
- **SSH and fastboot watches appear** alongside ADB ones; sysfs is read as a
  third source so a watch on none of the usual lists is still shown.
- **A watch drawing no power is flagged** — `status` says *Charging* while
  nothing enters the pack, which is silent and costs days.

## Orbit — a live map of what is reachable over the air

Orbit stopped being "watches that have left" and became **the list of watches
reachable over WiFi**, kept current automatically:

- **auto-mirroring** — a docked watch whose address answers *from this host* is
  enrolled by itself, gated on having a mapped port
- a watch away from its cradle **keeps its port row**, marked *in orbit*, and
  the Control Center keeps working over the air
- rows say **docked** or **orbiting**, since only one of those states can be
  powered, charged or flashed
- **land** brings a watch down for real — WiFi and Bluetooth off — and its
  button becomes **Launch**, which looks for it again at its last address
- entries expire after repeated silence, and hand-launched ones never do

## Modern watches: ADB and SSH at the same time

Configfs-era watches (aurora, sol) carry adb and a CDC-NCM network function on
**one** gadget, so both are live together:

- a-d-b **refuses to switch the USB mode** of such a watch. On these kernels
  that lands in a charging-only fallback — it is destructive, not merely
  pointless.
- they are reachable at their **IPv6 link-local**, with no address assigned at
  either end and no collisions possible
- the gadget is classified from its **interface list**, never `idProduct`, which
  cannot tell a healthy composition from the dead one
- a **mass-storage-only gadget** is named as needing a reboot, because a port
  cycle cannot fix a composition

Ships with the host-side config (`udev` rule + NetworkManager conf) that makes
this work unprivileged.

## Stock ROM: dump, verify, restore

- **`compare-dumps`** — two dumps, per partition, so a capture states its own
  trustworthiness rather than being trusted for where it came from
- **restore families** — the recipe is decided by *what the port wrote*, not by
  the watch. Two families are proven: the classic `boot`+`userdata` install
  (28 devices in `flashy`'s table), and the W5100 boot chain (sol).
- **a whitelist that refuses by default**, requiring a verified dump *of that
  unit* — per-device state cannot come from another watch, and on some models
  the stock boot chain exists nowhere else
- **three dump methods** recorded with their real preconditions, including the
  `initramfs-clean` route that works where `fastboot boot` is refused

## Flashing

Release channels (`--channel`), image names read from the release's own
`SHA512SUMS`, flashing a watch **with no hub seat**, and watches whose
bootloader reports a non-Google vendor are no longer invisible.

## Safety, after two audits

- **operation locks honoured everywhere** — CLI power commands, charge, drain,
  workbench, flash and the automatic timers
- **automatic recovery cycles are serialized**, one at a time
- **config is written atomically and locked across processes**
- destructive menu items are **armed, not confirmed**
- device-supplied strings are escaped on their way into the page
- a serial that cannot be a serial is refused as an identity, everywhere

## Interface

A **user/developer mode** that hides the lab rather than pretending to protect;
panels with consistent window behaviour; a message log that keeps errors until
dismissed; scoped menus in place of duplicated buttons; the watch-hands editor
with per-hand grab dots; a live view that composites the screenshot beneath the
hands.

## wanze

The on-watch probe gained schema 2: the screen source resolved per watch, the
panel's own power state, the kernel's suspend counters, a low-battery flush and
marker, and an opt-in upload. Host side pairs **`display_on_fraction` with
`asleep_fraction`** — together they say in one line whether a watch drained
because its screen never turned off.

---

## Known limitations

- **`doRestoreDump` is still a stub.**
- a-d-b's **own runtime dump path has never been exercised** end to end.
- The restore whitelist covers two families; anything else is refused rather
  than guessed at.
- **aurora is whitelisted but blocked** — its recipe is known, it has no dump.
- Naming from fastboot and Wear OS is covered by tests, not yet by hardware.
- Reported and not fixed: F4 (`fastboot devices` implemented twice, one
  unbounded), F7 (`DISPATCH._data` reached into directly), F21 (`adb reboot
  bootloader` can hang with no timeout).

## Notes for upgraders

Install with `./install.sh`; the service must be restarted for the new version,
and the top bar shows what is running. The `udev` rules gained a section for
USB-NCM watches, and there is a new NetworkManager conf — both are one-time
privileged steps, printed by `install.sh`.

Nothing in the config format changed; a 0.9 config is read unchanged.
