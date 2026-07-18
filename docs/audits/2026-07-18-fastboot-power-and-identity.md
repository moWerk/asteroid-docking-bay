# Fastboot power, charging, and exact watch identity

**Date:** 2026-07-18 (interactive session, ~6 hours) ·
**Branch:** `0.8`, `90f9e69` → `9a046b6` (9 commits) ·
**Tests:** 191 → 214 ·
**Findings:** 14 (7 hardware ground truth, 4 defects fixed, 1 operator error,
2 open)

The day started as two small UI fixes and turned into a hardware
investigation, because every question about the bootloader produced an
answer that contradicted the previous one. Three of the findings below are
corrections of claims made *earlier the same day* by this assistant. They
are included in full, with the mechanism of each error, because the way a
wrong answer survived two rounds of "verification" is more useful to a
reviewer than the final answer alone.

Two watches were nearly lost during the session (one deep-discharged
overnight before it, one stranded by a power cycle), and one of mo's
running drain tests was destroyed by an operator error documented in F13.

## Method

Five probes, escalating from software to firmware:

1. **Status/API inspection.** Reading `/api/status` and the persisted task
   state directly rather than through the UI, which turned out to matter —
   the UI's own safety gating is not enforced by the backend (F13).
2. **USB layer forensics.** `uhubctl` per-port status flags, sysfs device
   descriptors, ACLs, `journalctl -k`. Used to separate "no device" from
   "device present, not enumerating" from "enumeration failing".
3. **Live hardware experiments with a stated discriminator.** Each
   experiment was designed so a single number decides the outcome before
   it was run (e.g. "reappears in ≤5 s means it never stopped; ~20 s means
   it cold-booted").
4. **Firmware string extraction.** `strings` over the `aboot` partition
   pulled from live watches over adb, to read the bootloader's actual
   command table instead of guessing at it.
5. **Tests validated against planted bugs.** Every new test was run against
   a deliberately reintroduced copy of the bug it exists to catch. One
   test had to be rewritten because the planted bug made it *hang* rather
   than fail — a hang is a worse signal than an assertion.

**Version stamps.** rover ran AsteroidOS 2.1, rubyfish 2.0; the rest of the
fleet is mixed and mostly pre-2.0. Nothing here should be treated as
current for 2.2 nightlies without re-measurement. This matters: undated
capability claims are the most likely reason the published feature matrix
drifted out of truth in the first place.

## Hardware ground truth

### F1 — Fastboot dwell charges the battery, slowly (CONFIRMED, after two wrong answers)

A watch parked in the bootloader does charge, reaching 100% over a day
(mo, direct observation). The route to that answer was bad enough to
document:

- **Wrong answer 1 (morning):** "fastboot charges" — inferred from sturgeon
  reading 4% before a dwell and 10% after. Right conclusion, worthless
  evidence: sturgeon had been deep-discharged to 0%, and a fuel gauge is
  badly out of calibration after that.
- **Wrong answer 2 (afternoon):** "fastboot net-drains" — from 10% before a
  90-minute dwell and 6% after. The 6% was read at **uptime 20 s**, i.e.
  peak boot draw. On a worn cell (`V = V_oc − I·ESR`, and wear raises ESR)
  the terminal voltage sags and a voltage-referenced gauge reports a
  collapsed SOC. It recovered to exactly 10% within 25 minutes.
- **Wrong answer 3:** a power budget "proving" that 20 mA input cannot
  offset a lit display, presented as arithmetic. **Every figure in it was
  invented** — display draw, SoC draw, the assumption the screen stays lit,
  the assumption LK never configures the PMIC charger. mo disproved it with
  one sentence (a day-long dwell reaching 100%).

**Lesson for the reviewer:** the third error is the dangerous one, because
the *format* signalled rigour the content didn't have. A plausible
quantitative model invites the reader to stop checking. Short-window
battery measurements on worn or deep-discharged cells are near-worthless
and should not be attempted again; prefer long windows and terminal states.

### F2 — `fastboot getvar battery-voltage` is a boot-time snapshot (CONFIRMED)

It never refreshes within a fastboot session. Re-entering the bootloader
(`fastboot reboot bootloader`) forces a fresh sample. Observed flat at
3668 mV across ~40 minutes while the cell demonstrably changed, then moving
on re-entry.

Also **not universal, and not uniformly formatted**: sturgeon reports
`3668mV`, rover reports `4129872` (µV), lenok exposes **no battery
variables at all**. Any consumer must probe for presence and normalise
units.

### F3 — Cutting VBUS does not power off a watch in fastboot (CONFIRMED)

Experiment: sturgeon in fastboot, VBUS cut 60 s, restored. It reappeared in
fastboot at **t+4 s**, where a cold boot into fastboot on that watch takes
~20 s. It never stopped — it ran in the bootloader on battery the whole
time, invisible to the host.

**This is the fleet's deep-discharge mechanism** and the most likely history
behind sturgeon reaching 0% before the session.

**Wrong inference corrected:** rover's `aboot` contains
`"Shutting down because USB is not present"`, from which this assistant
inferred LK powers off on USB loss. That string belongs to the off-mode
charging path, not the fastboot menu. mo's prior ("watches lie in fastboot
for hours and then die") was correct and the experiment confirmed it.
Reasoning about which code path owns a string, without testing it, produced
exactly the wrong answer.

### F4 — No wire-reachable poweroff on the devices we could read (CONFIRMED, scope-limited)

The `oem` command table extracted from rover's and rubyfish's `aboot`:

```
oem device-info      oem lock / unlock / unlock-go
oem enable-charger-screen    oem disable-charger-screen
oem off-mode-charge  oem select-display-panel
oem enter-ship-mode
```

No `poweroff`. `fastboot oem help` returns `unknown command`. Combined with
F3, there is no way to power off these watches from the host.

The capability plainly exists — every watch's **on-screen** fastboot menu
offers "Power off" (confirmed in the same strings dump alongside
`START / Restart / Restart bootloader / Recovery mode`) and mo has used it
on all of them. A key press invokes LK's shutdown directly; the wire path
is what's missing.

**Scope limit, stated explicitly:** extraction returned nothing on sturgeon
and lenok (2014–2015 devices). Their `aboot` may sit at a different path or
not store the table as `oem <cmd>` strings. Their command sets are
**unknown, not empty**.

### F5 — `off-mode-charge` is inert fleet-wide (CONFIRMED by mo, negative result)

mo enabled it on all watches; nothing changed anywhere. Decisively, watches
that *do* off-mode charge did not stop when it was turned **off** — inert in
both directions. Whether a watch charges while powered off is a fixed
firmware property. Likely never wired up: phones expose a dedicated
off-mode-charge screen these watches may lack, leaving the variable gating
nothing.

**Consequences:** no rescue or charging design may depend on enabling it;
`disable-charger-screen` is probably inert for the same reason. Note the
commands exist in the bootloader table while doing nothing — **presence in
`getvar` or a strings dump is not evidence of function.**

### F6 — `oem enter-ship-mode` exists (UNTESTED)

The factory transport state, which disconnects the battery for near-zero
drain. Given F5, it is the only remaining candidate for the storage
deep-discharge problem. **Deliberately not tested** — exiting ship mode
typically requires a charger insertion, and it is not a state to enter
without the operator present.

### F7 — OLED burn-in during fastboot dwell is a real cost (mo, RECALLED/partial)

Exactly one fleet watch has been seen blanking its display in fastboot
(model unrecorded). **Assume the display stays lit.** Cycling the bootloader
to blank it briefly is a weak mitigation: burn-in accrues with lit time, and
a black interval pauses rather than reverses it, so cycling only helps in
proportion to the duty cycle removed. No standard command blanks the
fastboot menu; `disable-charger-screen` governs the off-mode charging
animation, not the bootloader UI — and per F5 is probably inert anyway.

## Identity

### F8 — `androidboot.bootloader` names the true hardware (CONFIRMED, shipped `bf7dff7`)

rover and rubyfish share an image, a `MACHINE` name (`rubyfish`) and a
454×454 panel, and differ only by LTE — which nothing on the device
exposes. Resolution, the only detector a-d-b had, cannot split them.

`/proc/cmdline`'s `androidboot.bootloader` comes from firmware, so a shared
image cannot mask it:

| watch | `hardware` | `bootloader` | `baseband` | LTE |
|---|---|---|---|---|
| rover | rubyfish | **rover**-03.02.39.03.16 | `msm` | yes |
| rubyfish | rubyfish | **rubyfish**-03.02.04.02.16 | `apq` | no |

`baseband` (`msm` = integrated modem, `apq` = none) independently
corroborates and is a candidate **LTE detector** for the pairs resolution
can never split (`sawfish`/`sawshark`, `catfish`/`catshark`,
`belugaxl`/`orca`). Not yet implemented — it needs the same within-family
confirmation on one of those pairs.

**Parsing matters more than expected.** The fleet uses at least four
formats: `rover-03.02.39.03.16`, `SKIPJACK.40010.19320`, `LENOKZ22b`,
`STURGEONV4.4`. Splitting on `-` fails three of the five watches online.
The implementation matches the **longest case-insensitive codename prefix**,
which also prevents `catfish_ext` being read as `catfish`.

mo (UX maintainer) states this reading is ground truth for all watches in
existence and is what the porting community reads first to identify a
device, so no per-family verification campaign is required.

### F9 — The geometry cache never refreshed after a schema change (DEFECT, fixed `bf7dff7`)

`_geometry_view` was probe-once-cache-forever. Shipping F8 therefore changed
nothing for any already-cached watch — every one kept reporting no
bootloader. Caught on the first live check after deploy, not by tests.

Cached probes now carry `GEOMETRY_PROBE_VERSION`; a bump re-probes while the
watch is live. The probe reports what it read and the cache layer owns the
stamp, so a stubbed probe in tests behaves like the real one.

## Diagnosis path (including dead ends)

### F10 — rover: five wrong hypotheses before the right one

rover enumerated cleanly on USB but adb never claimed it. Hypotheses tested
and **eliminated**, in order:

1. *Stale-node adb wedge* (documented rig quirk) — `adb reconnect`, then a
   full server restart: still absent.
2. *Device node permissions* — ACLs compared against a working watch
   (catfish): byte-identical, `user:mo:rw-` on both.
3. *Wrong USB mode / fastboot* — interface descriptor `ff/42/01`,
   byte-identical to a working adb watch. `fastboot devices` showed only
   sturgeon.
4. *WearOS with adb debugging off* — plausible and wrong. mo's standing
   rule: **assume AsteroidOS unless stated**; the only WearOS unit is the
   nemo reference. This cost a round trip and is now a memory entry.
5. *Bus contention / power budget* — mo proposed clearing the bus, which
   was done (three watches gracefully powered down, verified individually).
   The kernel log showed one clean enumeration with every descriptor string
   read and no retries; contention was never consistent with that.

**Actual cause:** rover was never booting. The `d001` gadget seen was a
non-booted watch advertising the interface with no `adbd` behind it — which
is why adb skipped it silently rather than reporting `unauthorized`. Booted
from fastboot, adb claimed it **1.3 s** after enumeration and held.

### F11 — A three-way fault taxonomy, and its correction

From hub port status plus kernel log:

| hub status | kernel | meaning |
|---|---|---|
| `power` + `connect` | quiet | working |
| `power`, no `connect` | **silent** | **no data link — cause not determinable** |
| `power`, no `connect` | `Cannot enable / attempt power cycle` | link actively failing |

The middle row was first published (in-session) as "watch is off". **That
was wrong**: an open data line produces identical silence, because the hub
never sees a D+ pull-up either way. The two states are indistinguishable
from the host; splitting them needs an inline USB multimeter. A taxonomy
that asserts a cause it cannot observe is worse than one that admits the
ambiguity.

Correspondingly, "rover's dock is fine" (from one successful enumeration)
was wrong — it was luck of the current seating. Several rig watches sit on
custom 3D-printed cradles where any touch is ~50/50 to re-seat wrongly.

### F12 — bass: dead cradle (mo, CONFIRMED)

`power`, no `connect`, no kernel errors. Cause is mechanical: the mini-USB
connector on the cradle failed, suspected broken in transport. Replacement
on order. Not a hub fault — an earlier suggestion that hub `1-2.3.4` might
be at fault was wrong; rubyfish on the same hub works.

## Defects found and fixed in asteroid-docking-bay

### F13 — OPERATOR ERROR: a direct API call destroyed a running drain test

**This assistant broke one of mo's measurements.** At 12:59 a
`POST /api/on/1-2.3/1` was issued to live-test an unrelated feature on
catfish. catfish was mid-drain-test. The port powered, the watch charged,
and the next poll read 100%:

```
100 100 100 100 100 99 99 99 98 98 98 97 97 97 97 96 96 → 100 100 100 100
                                                     ↑ 12:59 power-on
```

Five hours of readings destroyed; drain rate now reads 0.00%/h. Repeated
service restarts during deploys compounded it — the log shows "drain test
resumed" seven times that afternoon, each re-powering the port to read.

Two causes, the second structural:

1. The port was selected from a status line reading `power=False adb=None`
   — which is exactly what a mid-drain watch looks like. "Idle" and
   "deliberately powered off for a measurement" are not distinguishable at
   a glance.
2. **The UI's guard was bypassed by calling the endpoint directly.** The
   refresh button *is* correctly disabled on a busy row — but that
   protection existed only in the frontend. `docs/CONTAINERS.md` states the
   frontend may be fully compromised and the backend must hold the line,
   yet the op table had **no conflict check at all**. Any script, curl, or
   compromised frontend could silently corrupt a running operation.

**Fixed (`9a046b6`):** `port.set`, `port.cycle`, `port.poweroff` and the
whole reboot/bootloader/recovery/continue family now refuse while a charge,
drain or workbench operation owns the port, naming the owner. No force
flag — stopping the operation is one click, and an override would recreate
the hole. Verified by replaying the exact call that caused the damage.

### F14 — Drain tests discharged blind when the battery became unreadable (fixed `f92b16f`)

The drain loop's failed-read path was `log.warning(...); continue`, with no
bound. The floor check only runs on a **successful** read, so losing the
reading silently disabled the only thing stopping the discharge.

This already happened: rubyfish (2026-07-14) stopped enumerating mid-test,
froze the displayed value at 71%, and discharged past the 15% floor to 0%
and 3.18 V unseen.

Now bounded two ways, because the failure mode is a watch that gets *harder
to read as it weakens*: a cap on consecutive misses catches a watch that
drops off entirely, and extrapolation from the measured drain rate catches
one that stays under the cap while coasting below the floor. A single
transient miss is still tolerated.

On abort the port is left **powered**. The watch is by definition low and
unreadable at that point, so the normal end-of-test power-off would cause
precisely the deep discharge the guard exists to prevent.

## Also shipped

- **`dbfcf51`** — refresh now powers an off port before re-identifying. A
  watch plugged into a dead port was invisible, so the row showed the
  previous occupant forever. Caveat learned live: powering the *port* does
  not boot an off *watch* (catfish booted on VBUS, rover did not).
- **`6659165`** — the refreshing-row pulse survived hover. An `!important`
  background on the `:hover` rule outranks animation keyframes, pinning the
  row and killing the very hint it was meant to preserve.
- **`9d34f6e` / `d8ca74a`** — a watch in fastboot had no Power menu at all.
  Ops now dispatch on the protocol the watch actually speaks, keeping one
  op per concept. Power off is deliberately greyed with a tooltip pointing
  at the on-screen menu (F4) — disabled rather than hidden, since hiding it
  would imply the watch cannot be powered off, which is false.
- **`f36a198`** — the bootloader string is shown in the Control Center, so
  F8's detection can be checked by eye against the value it came from.
- **`9a046b6`** — product images fall back to the family photo; naming a
  watch more precisely was costing it its picture (rover showed none).

## Open

- **Wire-reachable fastboot poweroff** (F4). Next: extract the full dispatch
  table rather than `oem `-prefixed strings; probe candidate names
  (unsupported ones fail harmlessly); find the `aboot` format on the
  2014–15 devices. mo intends to ask contacts who may know undocumented
  paths.
- **LTE detector via `baseband`** (F8). Needs within-family confirmation on
  a `sawfish`/`sawshark`, `catfish`/`catshark` or `belugaxl`/`orca` pair.
- **Ship mode** (F6). Untested, hard to reverse, operator must be present.
- **catfish's drain test** — contaminated from 12:37 (F13); needs stopping
  and restarting for a clean measurement.
