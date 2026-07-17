# Adding a newly-ported watch to the fleet

When you port AsteroidOS to a new watch and dock it, what — if anything — do
you need to change in asteroid-docking-bay? Short answer: **usually nothing.**
This document is the definitive checklist so anyone (LLM or human) can announce
a new watch to a-d-b correctly.

## The mental model

a-d-b identifies a docked watch from what the watch itself reports over ADB, so
a correctly-ported watch is recognised with **zero code changes**:

| What a-d-b shows | Where it comes from | Needs a code change? |
|---|---|---|
| Codename / label | `/etc/asteroid/machine.conf` `Identity/MACHINE` | No — read live |
| Screen shape (round/square/rect) | `machine.conf` `Display/ROUND`, `Display/FLAT_TIRE` | No — read live |
| Resolution | `/sys/class/graphics/fb0/modes` | No — read live |
| Product photo | `asteroidos.org/public/img/<codename>.png` | No — fetched + cached |
| Battery, Control Center stats | sysfs / dbus over ADB | No |

So the normal path is: **flash it, dock it, Onboard/Refresh it — done.** It
appears with its real codename, correct screen mask, and product photo.

### Example: porting `sol` (Pixel Watch 3)

`sol` gets its own system image, so `machine.conf` reports `MACHINE=sol`. a-d-b
needs **no changes** — dock it and it shows up as `sol`, pulls `sol.png` from
asteroidos.org, and masks its screenshot to `sol`'s shape/resolution
automatically. (If `sol.png` doesn't exist on the website yet, the thumbnail
just omits itself until it does.)

## The one exception: shared system images

The **only** time you touch a-d-b's code is when the new watch **does not get
its own image** and instead ships a sibling's — so `machine.conf MACHINE=` is a
*different* watch's name. The porters have done this to save space:

- `tunny` ships the **skipjack** image (`MACHINE=skipjack`)
- `belugaxl` / `orca` ship the **beluga** image
- `catshark`, `catfish_ext` ship the **catfish** image
- `carp` ships the **smelt** image
- `sawshark` ships the **sawfish** image
- `rover` ships the **rubyfish** image

For these, `MACHINE=` alone can't tell the variants apart, but the user-facing
codename must still be exact (it's what asteroidos.org lists). a-d-b resolves
the exact codename from whatever it can actually measure, using the ground
truth in [`asteroid_docking_bay/watch_variants.json`](../asteroid_docking_bay/watch_variants.json).

**This is purely cosmetic.** Config and every operation (flash, charge, drain,
mapping) still key on the MACHINE image name — because that image is what
actually gets flashed. Only the displayed codename changes.

### What "detectable" means

a-d-b can only disambiguate by attributes it can read from the watch. Today
that is **resolution only** (`variants.DETECTABLE`). Resolution is not unique
across the whole fleet, but it *is* unique within a shared-image family
(skipjack 360 vs tunny 400; beluga 320×360 vs belugaxl 402×476). Variants that
differ only by **LTE, GPS, RAM, or case size** cannot be told apart yet, so
they show as the family's **base** codename until a detector exists.

Record the full ground truth anyway — every variant's factors, detectable or
not. When a detector lands (e.g. GPS), add its key to `variants.DETECTABLE`,
populate it in the `observed` dict in `webstatus`, and the *same* table starts
resolving those variants with **no re-survey**.

## How to add a shared-image variant

Edit `asteroid_docking_bay/watch_variants.json`, under `shared_images` →
`<MACHINE name>` → `variants` (an **ordered** list, base first):

```jsonc
"skipjack": {
  "base": "skipjack",
  "variants": [
    {"codename": "skipjack", "model": "TicWatch C2",  "resolution": "360x360"},
    {"codename": "tunny",    "model": "TicWatch E2/S2","resolution": "400x400"}
  ]
}
```

Rules:
- **Order base-first.** The resolver returns the first variant whose
  *detectable* factors match, so a variant distinguished only by an
  undetectable factor (e.g. `orca` = belugaxl + LTE) must come *after* the one
  it collapses to.
- **Record every distinguishing factor** as ground truth: `resolution`
  (`"WxH"`, orientation doesn't matter), `gps`, `lte`, `ram_mb`, `case_mm`.
- Add a `"_note"` for anything unverified.

Or run the helper, which does the edit and validates for you:

```bash
./onboard-new-watch-to-fleet.sh
```

## Optional: live-screen composite (transparent screen cutout)

a-d-b can show the watch's **live screenshot inside its own screen** in the
product photo, instead of side by side. This needs one art edit per image and
**no per-watch coordinates** — the position is read from the image's alpha.

To enable it for a watch, edit its product PNG once:
- Cut the **screen glass** to fully transparent alpha (alpha 0).
- Leave the bezel, case, and any foreground **opaque** — including hands that
  sit over the screen (narwhal): they'll correctly occlude the screenshot.
- Leave the render's background as it is (transparent or opaque); the detector
  distinguishes the enclosed screen hole from the surrounding background.

a-d-b then composites the screenshot behind the product image (masked to the
exact screen shape by your cutout), with a black fill so an off/offline screen
reads as an off panel; the row thumbnail gets the same fill. An **un-cut**
image just falls back to the side-by-side look, so this is entirely opt-in and
per-image.

Edit the cached copy to try it (served as-is, no re-fetch):
`~/.local/share/asteroid-docking-bay/watch-images/<codename>.png`. The
canonical source is asteroidos.org `public/img/<codename>.png`. Note the image
is fetched by the **exact** codename, so cut `tunny.png` / `belugaxl.png`, not
the shared image's `skipjack.png` / `beluga.png`.

## Checklist

1. Flash + dock + Onboard the watch. Does it show the right codename already?
   → **You're done.** (This is the common case — unique image.)
2. Does it show a *sibling's* codename (shared image)? Add it to
   `watch_variants.json` (or run `onboard-new-watch-to-fleet.sh`).
3. Confirm the product photo (`asteroidos.org/public/img/<codename>.png`).
4. `pytest tests/test_variants.py` stays green.
5. If a-d-b gained a new detector (GPS/RAM/…), add its key to
   `variants.DETECTABLE` and populate it in `webstatus`.
