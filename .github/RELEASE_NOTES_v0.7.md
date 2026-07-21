# asteroid-docking-bay 0.7 — every watch, exactly itself

0.6 was a UX and flashing pass. 0.7 is about **identity and honesty**: the
dashboard now knows what each docked watch actually *is* — its exact hardware
codename, screen shape and resolution — even when the factory image lies about
it; it shows each watch's product photo with its **own live screen composited
inside the frame**; it keeps a watch's last-known readings on screen, marked
stale, when it drops off the bus instead of blanking; and it charges **several
watches at once** instead of silently queueing them.

The [README](https://github.com/moWerk/asteroid-docking-bay#readme) covers use;
[docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) is the map;
[docs/ADDING-A-WATCH.md](../docs/ADDING-A-WATCH.md) is new. These notes are the
technical companion. Tests **131 → 178**, CI-gated on Python 3.9 and 3.14.

## Exact identity, resolved from the hardware

AsteroidOS's porting process shares one system image across hardware variants
to save space, so `machine.conf`'s `MACHINE=` is ambiguous — a TicWatch E2
ships the `skipjack` image and reports `skipjack`, though it's really `tunny`.
0.7 shows the **exact** user-facing codename anyway, matching asteroidos.org:

- **Screen geometry is read live** from `/etc/asteroid/machine.conf` (the same
  source qml-asteroid's `DeviceSpecs` uses) for shape, and from
  `/sys/class/graphics/fb0/modes` for the true resolution — deliberately *not*
  `virtual_size`, which is double-buffered and reports the wrong height.
- **Variants are disambiguated by resolution**, which is unique within a
  shared-image family (`skipjack` 360 vs `tunny` 400; `beluga` 320×360 vs
  `belugaxl` 402×476). The full fleet ground truth — every variant's
  resolution, GPS, LTE, RAM and case size, detectable or not — lives in
  `watch_variants.json`; the resolver uses only what it can read today and
  falls back to the base codename rather than guessing. Add a detector later
  and the same table applies with no re-survey.
- It's **purely cosmetic**: config and every operation still key on the
  MACHINE image (the thing actually flashed). The Control Center adds a
  **Machine (image)** field so a user who clicked "tunny" sees why it flashes
  `skipjack`.
- New watches usually need **zero changes** (identity is read live, the photo
  is fetched); `docs/ADDING-A-WATCH.md` and `onboard-new-watch-to-fleet.sh`
  cover the rare shared-image case.

## The live screen, inside the watch

Each row now shows the watch's product photo, and clicking it opens the watch
with its **live screenshot composited into the screen**:

- The screen position is read from the product PNG's **transparent alpha
  cutout** — no per-watch coordinate table. A flood-fill from the border
  strips the render's transparent background; whatever enclosed transparency
  remains is the screen hole (robust to an opaque foreground splitting it,
  e.g. a watch's physical hands, which correctly occlude the shot).
- The screenshot sits *behind* the product image so the bezel and hands cover
  its edges; the alpha cutout is the mask. It renders at 2/3 native resolution
  (the JPEG is heavily compressed) with `object-fit: contain` so it never
  distorts or over-scales, sized so the watch scales around a true-size screen
  and re-fits responsively on window resize. An un-cut image falls straight
  back to a side-by-side view, so images upgrade themselves as their screen is
  cut. Round screens are clipped to a circle; the row thumbnail gets a black
  screen-fill so it can't shine through.

## Nothing blanks: stale-value display

A watch leaving the bus used to empty its row. Now a per-serial last-seen
store (persisted, so it survives a restart) keeps the last **battery, Control
Center stats and screenshot** and when they were seen:

- The battery column shows the cached percent in amber with its age; the
  Control Center renders the last-known stats on a stale frame with a "last
  live Nh ago" stamp; the watch-image overlay shows the last screenshot dimmed.
- The live `battery` field keeps its `None`-when-offline contract, so nothing
  mistakes a cached number for a fresh one.

## A Stats column and richer rows

The per-row status icons moved out of the codename cell into a dedicated
**Stats** column and grew into a full strip: the wearable / battery-swap
verdict, a **?** until a watch has ever been drain-tested, the watch-side
**charge state** (delivered-power ground truth — a docked watch reading
*Discharging* is a dirty contact), a click-to-open **battery-history
sparkline** from the event log, and a **last-live age** when offline. A freshly
plugged-in watch flashes its row.

## Charge several at once, and smoother controls

- **Concurrent charging.** Charge no longer holds the one-at-a-time bus lock
  for its whole duration — pressing Charge powers the port on immediately and
  several watches charge at once. (Real brownout/voltage-drop protection is the
  planned successor to the blind lock.)
- **Smart on power-cycle.** The ↺ button now runs the PPPS test and records the
  smart verdict, so a `?` resolves without a full re-onboard.
- **Downloadable diagnostics.** Collect-diagnostics now offers the bundle as a
  browser download instead of stranding it on the host.
- **Consistent overlays.** The watch-image panel anchors to the click and
  flips to fit like the Control Center; the row menus lost their fragile
  mouseleave auto-close (outside-click / Escape only) and regained per-action
  accent colours.

## Fixed

- **Remote operation restored** — a render-time `ReferenceError` (a helper
  referencing a render-local const) was surfacing as a permanent "connection
  error"; every render now runs in a headless smoke test.
