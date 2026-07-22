# asteroid-docking-bay 0.8 — *"a watch is a watch, over any wire — and easy on the eye"*

0.7 taught the fleet manager to name every watch as exactly itself. 0.8 does two
larger things: it makes a watch **fully operable over SSH, not just ADB**, and —
foremost — it turns the web UI from a working table into something that, replayed
in the right light, reads as a small **design study**. Ninety commits. The
functional half is the wire; the other half is the glass.

## The wire — SSH becomes a first-class transport

Until now every watch feature spoke ADB. 0.8 introduces a **transport
abstraction** (`AdbTransport` / `SshTransport`) and routes *every* Watch command
through it, so the Control Center, the toggles, time-sync, screenshots, even a
graceful power-off all work identically whether a watch is on ADB or in
SSH/developer mode. `_reachable_transport()` simply picks the wire that answers.

The hard part of "several watches on SSH at once" is that every developer-mode
watch defaults to the SailfishOS-inherited `192.168.2.15`, so two of them collide
and become unaddressable. 0.8 solves it end to end:

- **Per-watch SSH IPs**, sticky per serial, handed out from `192.168.13.37`
  (LEET), set over ADB before the switch so each watch keeps its own address.
- A situational **`prefer ADB` / `prefer SSH`** toggle in the top bar — the
  user's standing consent for how the fleet is kept.
- **Auto-alignment**: a stray watch that self-enumerated on the shared `.15` is
  quietly relocated to its unique IP (under *prefer SSH*) or returned to ADB
  (under *prefer ADB*) — built entirely from the two existing switch ops, no new
  device code, and verified live on hardware.
- **Exact-codename addressing** so `rover` hits *rover*, not "the first
  rubyfish", and an ambiguous name refuses rather than guesses.

Around it: passive standby-drain measurement across a power-off, fastboot power
actions and a downloadable `getvar` report for a bricked unit, a per-watch event
timeline external tools can write to, and honest boot-state signalling —
**"booting up"** for a cold boot, **"boot failed?"** (question mark deliberate)
once the window lapses, and **"reconnecting"** when a running watch merely
re-enumerates after a VBUS cut.

## The glass — an origin story

It started with **one pill**. A rounded, bordered capsule — first the power
toggle and the ADB/SSH badges — turned out to be the whole vocabulary waiting to
happen. Everything after is that pill, and its sibling the **dot**, answering one
self-imposed constraint: **it all has to live in the row.** No drilling into a
screen for the common case. That constraint is the engine of the entire study.

Because everything had to fit a row, things *folded*:

- Five action buttons collapsed into **one `menu`** — grouped, indented, every
  option visible at once.
- The battery cell became a **filling gauge** — a real little battery whose fill
  grows left-to-right.
- The stats became a **row of dots** — power, wearability, battery-graph, charge —
  each a glyph in a circle, and each now *clickable*: the battery dots all open
  one **Battery Info** panel (history folded into its foot); the power dot opens a
  short power menu; the wearability dot opens drain/wear. Duplicate panels were
  retired into one.
- Redundancy fell away: the `socket 1` label became `s1`, the `├─` tree glyphs
  vanished (the hub labels already break the flow), the Port column folded into
  Power, and the last-seen age stopped pretending to be a pill.

Then came **colour as weight**. Colour is not decoration here; it's a rationed
signal, and we caught ourselves overspending it. The battery was amber everywhere
("technically the mid-band, but so much ambiguous amber"), and Smart's green
"yes" competed with the greens that mean *power* and *charge*. So we pulled colour
back to meaning: **green = powered / live**, **orange = ambiguous or stale**,
**blue = a type or an action** (Smart became `ppps` in blue), **red = danger**,
**pink = worn**. A battery is now grey until it's connected and we can honestly
colour its charge. Amber was freed to mean only *caution*.

Alongside it, **honest nomenclature** — the UI claims only what it can assert.
`not docked` (which blames the plug) became the neutral **`no link`**; a graceful
power-down became **`shelved`**; and a raw toggle-off now clears the shelved
marker so it never falsely claims a watch is safely down.

And **consolidation** as the finish: one `--pill-h` token drives the height of
every pill, dot, gauge and toggle at once; one centring class serves four columns;
one Battery Info panel is reached from three places. When something could be
deleted or shared instead of added, it was.

The **toggle** deserves its own line. It was designed twice — an elaborate sliding
*orbit-eclipse*, wired in faithfully, judged "out of language", and brought home
to the flat `● ON/OFF` pill it always wanted to be — but now carrying an
**animated exec hand-off** the original never had.

Then all the pieces fell into place at once: the table went to the screen edges
and back to a **viewport-scaled margin**, a seeded **Depth Drift starfield** was
painted behind everything so the header and margins twinkle, and the table itself
turned **milk-glass** — semi-opaque rows frosting the stars so they faintly shine
through.

## Under the hood

- Op-table contract pinned by tests + `docs/CONTAINERS.md`; split-mode ready
  throughout.
- ~290 tests, every new behaviour **planted-bug validated**; a headless-DOM
  harness renders the page's JS so column order, wiring and each pill/dot is
  checked without a browser.
- RAG updated with the `set:ip`-applies-on-transition finding and the SSH-IP
  relocation mechanism.

*asteroid-docking-bay is a full-LLM-written project under moWerk's direction; the
process record ships in the repo, and that transparency is the point.*
