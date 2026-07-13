# asteroid-docking-bay 0.6 — flashing, rest, and a quieter UI

0.5 shipped the container split and closed by naming three UI gaps as "next":
a stuck screen-force-on with no indicator, no split-mode "backend unreachable"
banner, and no fastboot/SSH row indicators. 0.6 closes all three — then keeps
going. You can now **flash a release and back up a watch's data from the
browser**; a **watch always returns to rest** after an operation instead of
draining behind an "off" port; the battery reading trusts the **right gauge**;
and a genuine **UX pass** strips the cheesy emoji and finally makes the page
usable on a phone.

The [README](https://github.com/moWerk/asteroid-docking-bay#readme) covers use;
[docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) is the map. These notes are the
technical companion. Tests **103 → 131**, CI-gated on Python 3.9 and 3.14.

## The three UI gaps 0.5 flagged — closed

- **Stuck demo-mode screen, caught and released.** A forgotten
  `mcetool -D on` holds a watch's display on and drains it invisibly. The
  status path now reads mce's `Blank inhibit` in the same round-trip and
  exposes a per-port flag: a fleet-wide banner names any draining watch with a
  one-click **release all**, each affected row carries a click-to-release
  marker, and the Control Center's screen control is a **stateful toggle**
  (dark = off, bright warning-amber = forced on) that reads ground truth.
- **Backend-unreachable banner.** In split mode, if the backend is down the
  page keeps the last-known table on screen, stamps the time "stale (backend
  down)", and raises a banner instead of silently blanking to an empty fleet.
- **fastboot / SSH indicators.** A watch in the bootloader or in SSH/developer
  USB mode now shows a clear pill in the Connection column, backed by a tested
  connection-state resolver.

## Flashing, from the browser

The **Flashing** menu (renamed from "Flash" now that it holds more than
flashing) is real:

- **Flash a chosen release** — `Flash 2.1` / `2.0` work, not just the nightly;
  a channel is swapped into the release URL with its own cached image dir.
- **Data Backup / Restore** — pull a watch's `~ceres/.config`, connman WiFi
  credentials and a `dconf` dump to a per-watch folder on the host, and push
  them back (re-owned to ceres, connman restarted so WiFi reconnects). Verified
  end to end: back up a watch, flash it clean, restore — settings and WiFi
  survive.
- **No more silent `oem unlock`** on every reflash — an AsteroidOS watch is
  already unlocked; deliberate unlocking is a separate, warned action for a
  future WearOS-onboarding flow.
- **Flashes hit the exact watch you clicked**, resolved by slot + serial, not
  by codename — so two watches sharing a codename can't cross wires (found live
  during the first browser flash).
- `Dump mmcblk0` / `Restore from dump` are staged but greyed ("not yet
  implemented"): a byte-exact raw image needs a per-model debug-ramdisk boot
  that crippled-fastboot watches can't do, so it's gated behind a per-codename
  capability table still to come.

## The fleet comes to rest

A cluster of lifecycle fixes so watches don't sit awake or half-charged:

- **Return to rest:** an optional `drain_rest_recharge` charges a finished
  drain back into the healthy band before powering off, so a test doesn't
  leave a watch stored near-empty.
- **Map ends default-off:** the mapping pass now powers each identified watch
  gracefully back down instead of leaving the fleet awake.
- **SSH→ADB recovery:** a watch that boots into SSH/developer mode (a fresh
  flash's default) can be switched to ADB — from a click on its SSH badge, and
  automatically during a flash — over `192.168.2.15`.
- **Timer defers to the web service:** the periodic check-charge now skips any
  watch the running web UI is mid-drain/-charge/-workbench on, so the two never
  collide on a decision (flock only ever covered the bus).
- **Sticky smart verdict:** a proven port-switchable result no longer flickers
  to "?" when a later marginal re-test comes back inconclusive.
- **Fake-power self-heal (opt-in):** `fake_power_self_heal` auto-cycles a port
  that reports power but never connects — the stale-node wedge — once, with
  backoff, never during an op.
- **Collect diagnostics:** a Workbench action bundles journal, dmesg, battery,
  thermal, storage, connman and dconf into a per-watch tarball for bug reports.

## The battery reading trusts the right gauge

Some watches expose two `power_supply` battery nodes. On at least one, the
generic `battery` node read a stale, miscalibrated 50% while the real
`nanohub_fuelgauge` — what the watch's own UI reads — reported the true 100%.
The dock now prefers the named hardware fuel gauge, falling through to
`battery` on watches that don't have one.

## The UX pass

- **The emoji are gone.** Wrench, floppy, clipboard, camera, lightning, the
  see-no-evil monkey and the rest were cheesy and, as colour-emoji, too bright
  on the dark theme. Buttons and menus are clean text now; the meaning lives in
  the labels and the existing colour classes. Kept: the header star ornament,
  the AsteroidOS logo, and the monochrome UI glyphs that are actually
  functional (dropdown caret, cycle/refresh icons, drain arrow, the row tree).
- **The page is responsive again.** An earlier fixed-width table (meant to stop
  columns shifting on string length) forced a permanent horizontal scrollbar;
  that trade wasn't worth it. The table is fluid again — columns follow the
  page width.
- **It works on a phone.** A viewport meta tag (its absence was letting mobile
  Chrome font-boost the buttons into giants) plus a stacked card layout below
  720px: each row becomes a slim, legible card, one labelled field per line, no
  sideways scrolling.

## Known limitations / on the roadmap

- **mmcblk0 dump/restore** is deferred pending the per-codename fastboot/
  ramdisk capability table (above).
- **SSH→ADB** is wired and its plumbing verified, but the live switch needs a
  watch actually in SSH mode to exercise end to end.
- `drain_rest_recharge` and `fake_power_self_heal` are **opt-in** (they actuate
  hardware / change stored charge) — enable them in the charge config.
- The **container backend on real USB** remains experimental, as in 0.5.

## Provenance (unchanged stance)

Written by an LLM coding agent (Anthropic Claude), directed, tested and
ground-truthed on hardware by the maintainer; commit discipline follows
cbea.ms — one coherent change per commit. Several fixes in this release were
found live on the rig during ordinary use (the wrong-watch flash, the fuel
gauge, the missing viewport meta). GPL-3.0-only; the commit history is the
unedited record.

## Requirements

Unchanged: Python ≥ 3.9 (stdlib), adb; uhubctl for discovery/fallback;
fastboot + wget for flashing; bottle for the web UI; podman for the container
split. For development: pytest (the CI gate).
