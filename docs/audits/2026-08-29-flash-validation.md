# Flashing, exercised on hardware for the first time — 2026-08-29

**Status:** the flash path works end to end, on two watches, in both
directions, across two release channels. Nothing in a-d-b failed.

## Why this record exists

a-d-b has been able to flash watches since 0.6, and the 1.0 notes describe
release channels, `SHA512SUMS`-driven image names and hub-less flashing as
shipped features. None of it had been run against real hardware in this
session's memory, and the 2026-08-08 audit found the flash and dump menu items
had been **silently dead in the UI since 2026-07-22** — reachable code that
nobody had exercised. A feature that has never been run is not a shipped
feature; this closes that gap with evidence rather than assertion.

Both flashes were requested by moWerk for his own reasons — rover needed Qt6 to
run benchymark, and beluga needed 2.1 for a hands-on test. The validation is a
by-product, which is the honest way round: the flashes were real work, not a
demo staged to pass.

## What was run

| watch | serial | slot | from | to | channel |
|---|---|---|---|---|---|
| rover | `A103X16100826` | 1-3:1 | 2.1-era (Qt5) | 2.2-nightly | default (nightly) |
| beluga | `225791c5` | 1-3.3.4:1 | 2.2-nightly | **2.1** | `--channel 2.1` |

Opposite directions, which matters: a flasher that only ever moves forward
could be hiding a version assumption.

## The sequence, as logged

    beluga: fetching SHA512SUMS…
    beluga: downloading zImage-dtb-beluga.fastboot…
    beluga: downloading asteroid-image-beluga.rootfs.ext4…
    beluga: images verified OK
    beluga: powering on port 1-3.3.4:1
    beluga: rebooting to bootloader…
    beluga: fastboot device ready (225791c5)
    beluga: done — watch is rebooting into AsteroidOS

## Verification, from sources independent of the flasher

1. **The watch itself.** beluga afterwards: `VERSION="2.1"`, `VERSION_ID=2.1`,
   `/usr/lib/libQt5Core.so.5.15.16`, `/proc/uptime` 87 s — a fresh boot on the
   requested release. rover afterwards: `VERSION="2.2-nightly"`,
   `libQt6Core.so.6.11.3`.
2. **The fleet registry, which was never told a flash happened.** It watches
   for field changes and logged both, as mirror images of each other:

       beluga  2026-08-29 20:37  {"qt": ["6.11.2", "5.15.16"]}
       rover   2026-08-29 12:39  {"qt": ["5.15.16", "6.11.3"]}

   That is [[project_fleet_registry]] doing exactly what it was built for —
   corroborating a change from a different code path than the one that caused
   it. It is the strongest single piece of evidence here, because nothing in
   the flash path produced it.
3. **Checksums.** `images verified OK` is a real `sha512sum --check` against
   the release's own `SHA512SUMS`, not a size check.

## What this confirms about specific 1.0 claims

- **Release channels work.** `--channel 2.1` resolved to
  `release.asteroidos.org/2.1/beluga/` and flashed it.
- **Image names come from the release's own `SHA512SUMS`.** The 2.1 pair is
  `asteroid-image-beluga.rootfs.ext4` + `zImage-dtb-beluga.fastboot`; the
  nightly pair differs. A hardcoded name would have 404'd on one of them.
- **Shared-image variants resolve correctly.** rover has no image of its own —
  `release.asteroidos.org/nightlies/rover/` is a 404 and `…/rubyfish/` is a
  200. a-d-b flashed the right image because both flash paths take the
  codename from the port map, which holds the hostname-derived name
  (`rubyfish`), not the cosmetic exact codename (`rover`). Checked before
  flashing, not after.

## A correction worth recording

During this work I claimed the flash path "doesn't map a shared-image variant
to its base image", inferring it from `_download_nightly(codename)` taking its
argument verbatim. That was **wrong**: I had not checked what the callers feed
it. Both `cmd_flash_all` and the web `flash.start` op resolve the codename via
`find_codename_for_loc_port()`, which returns the hostname-derived name — so
the mapping was already right, and `exact_codenames` is display-only. The
failure mode was bridging two true facts into an unverified conclusion, which
is the specific error this project's CLAUDE.md warns about twice.

## Defects found

None in a-d-b. One in the caller I wrote: the first flash driver printed no
progress because it never configured the root logger, and a-d-b reports flash
progress through `log.info`. The run looked stalled while it was working
correctly. Fixed in `~/DockingBay/scripts/flash_beluga_21.py`; worth knowing
that a-d-b's flash progress is invisible to a bare script.

## A fact established on the way

**2.1 ships Qt 5.15.16; 2.2-nightly ships Qt 6.11.x.** benchymark is Qt6-only
(`invoker --type=asteroid-qt6`, `MultiEffect`, `Shape.CurveRenderer`), so it
cannot run on 2.0 or 2.1 at all — it failed to launch on rover for exactly
this reason before rover was flashed. Any pre-Qt6 performance comparison needs
an instrument built from Qt5-compatible primitives; benchymark cannot answer
it, whatever it is flashed onto.
