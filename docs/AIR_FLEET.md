# The Air port — managing watches over the air (design)

Status: **proposal / vision**, 2026-07-23, mo's idea. Depends on the SSH
transport (shipped, 0.8) and the Bluetooth companion (proposed, see
`BLUETOOTH_COMPANION.md`). Nothing implemented yet.

> mo's dream: *"an 'air' port where all watches are listed that are not on USB
> but have been added to the fleet via WiFi or BT."*

## The idea in one line

A virtual hub — **Air** — that lists fleet watches reachable **over the air**
(WiFi-SSH or Bluetooth) rather than on a physical USB port. The dock stops being
where a watch has to *live* and becomes where it is *onboarded*: dock once to
learn how to reach it wirelessly, then keep managing it after it walks away.

## Why it fits what a-d-b already is

Three things the fleet already has make this natural rather than a bolt-on:

1. **The transport abstraction.** `AdbTransport`/`SshTransport` already mean "a
   watch, reachable over *some* wire." An Air watch is the same Watch object with
   an SSH (WiFi) or BT transport instead of USB-ADB. Almost every per-watch
   feature already runs over SSH (CC, toggles, screenshot, settime, weather).
2. **Identity is the serial, not the port.** The fleet knows watches by serial +
   exact codename, independent of which port they sit on. An Air watch is just a
   fleet member with no current USB port.
3. **The correlation keys already exist.** The watch's **WiFi IP** (`d.ip`) and
   **BT MAC** (now in the Network tab) are read while it is docked — so a docked
   watch already tells us exactly how to reach it over the air later.

## Reachability — an Air watch has a *quality of link*, not just on/off

An Air watch can be reachable by two independent links, either/both/neither:

| Link | How | What works |
|---|---|---|
| **WiFi-SSH** | `SshTransport(wifi_ip)` — the watch's wlan0 address, in developer/SSH mode | **Almost everything**: the full Control Center (stats + toggles), screenshot, set-time, weather (dconf), diagnostics, backup. A shell over WiFi is nearly a docked watch. |
| **Bluetooth** | bonded GATT (see BLUETOOTH_COMPANION.md) | **Sync + notify**: push time, push weather, send/clear notifications, media/MPRIS, live battery %, BT screenshot, buzz-to-find. No shell → no CC stats. |
| neither | in the fleet, currently out of range / off WiFi | last-known (stale) values + "unreachable", like an off-dock USB watch today |

So an Air row's actions are gated by its live link: WiFi-SSH gives the rich CC;
BT gives the companion sync set; a watch on both gets the union.

## How a watch joins the Air port

Three onboarding paths, in order of elegance:

1. **From the dock (the primary path).** While a watch is docked, a-d-b already
   reads its WiFi IP and BT MAC. A **"Send to Air"** row action captures them:
   record the WiFi IP (and optionally switch the watch to a persistent SSH mode)
   and/or trigger a BT bond. On undock, the watch does not vanish — it moves to
   the Air port, still reachable. This is the killer flow: *dock, one click,
   undock, keep managing.*
2. **Fresh BT scan + pair.** A watch that has never docked but is in BT range:
   **Scan** (BLE discovery) lists advertising watches, correlated to the fleet by
   BT MAC / codename; **Pair** bonds it (one-time accept on the watch). It joins
   Air as a BT member. (This is also how a brand-new watch could be adopted.)
3. **Manual WiFi add.** Type an IP/hostname; a-d-b SSH-probes it, reads the
   serial + codename, and adds it as a WiFi-SSH Air member. For watches already
   on WiFi that never touched this dock.

## Data model

A virtual hub in config, alongside the physical ones:

```json
{ "location": "air", "virtual": true,
  "members": { "<serial>": {
      "codename": "skipjack",
      "wifi": { "ip": "192.168.1.50", "added": 1721... },
      "bt":   { "mac": "98:28:A6:E8:05:FB", "bonded": true } } } }
```

- Keyed by **serial** (the stable identity). `codename` cached for display.
- `wifi.ip` and `bt` are independent and optional — a member can have one or
  both. Reachability is *probed*, not stored (a member is "added" persistently;
  "reachable" is live).
- Config helpers mirror the existing ones (`air_members(cfg)`, add/remove).
- The status path treats `air` like any hub: iterate members → build rows →
  probe each member's links (WiFi-SSH reachable? BT connectable?). Probing costs
  a round-trip per member, so cache it / background it like the SSH battery read
  and the self-heal workers already do — the Air port must never block the USB
  status path.

## The UI

The fleet table grows an **Air** section (a virtual hub card) below the physical
hubs — same row grammar, so it reads as *one fleet*, not a second app:

- **Row identity**: codename + a small "air" glyph instead of a socket number.
- **Reachability badges** in the connection column: `WiFi` (green when SSH
  answers) and/or `BT` (blue when bonded+connected), or `unreachable · last live
  Xh ago`. This reuses the exact stale/last-seen machinery already built.
- **Actions**, gated by link: the codename opens the Control Center over
  WiFi-SSH (rich) or, BT-only, a lighter **Companion** panel (sync time / push
  weather / send test notification / battery); the menu carries "Sync all",
  "Forget from Air", and (BT) "Re-pair".
- **No power/charge/drain/flash** — those need the wire. An Air row is honest
  about being remote: it shows what it *can* do, greys what it can't.

### The scan + pair flow (mo's specific ask)

A fleet-level **Scan for watches** button (or on the Air card header):

1. `bt.scan` → BLE discovery (~10 s) → a results list `{mac, name}`.
2. Each result is **correlated to the fleet**: matched to a known watch by BT MAC
   (exact) or codename (fallback) — so it reads "skipjack — already in fleet
   (docked at 1-2:1)" or "beluga — new". The scan is not a raw device list; it is
   the fleet, seen over the air.
3. **Pair** per result → `bt.pair(mac)`. The watch shows a pairing prompt; the UI
   enters a pending state: *"Accept the pairing on skipjack's screen."* If a
   passkey is shown, display it to compare. (This one human step is unavoidable —
   the daemon requires an authenticated bond; see BLUETOOTH_COMPANION.md §C.)
4. On bond → the watch appears in the Air port with a BT badge. A "Trust" makes
   future reconnects silent.

The WiFi side needs no scan: **Send to Air** on a docked row (captures the IP it
already reads) or **Add by IP**.

## What the BT feature buys, concretely

Beyond "an Air port," the companion turns the rig into things a phone can't be:

- **A fleet notification test bench.** Send a crafted `<insert>` notification to
  any/all watches and watch how each renders it + vibrates — across the whole
  fleet at once, from the browser. Invaluable for launcher/notification work.
- **Weather + time over *any* wire.** a-d-b already fetches Open-Meteo and writes
  weather over USB/SSH dconf; the same fetch re-encoded as GATT bytes syncs a
  watch that is only in BT range. One "Sync all" reaches docked *and* Air watches
  by whatever link each has.
- **Live battery without a cable.** The BT battery notify gives a real % for a
  worn/Air watch — the honest standby data the drain tests approximate, straight
  from the watch, no charge-bump.
- **Find-my-watch.** Buzz an Air watch over the notification vibrate to locate it
  on the bench.

## Phased plan

- **P1 — Air data model + WiFi members.** The virtual `air` hub, `Send to Air`
  from a docked row (capture WiFi IP), the Air section rendering with WiFi-SSH
  reachability + the Control Center over WiFi. No BT yet — pure SSH, all the
  transport already exists. This alone realizes most of the dream.
- **P2 — BT companion core** (BLUETOOTH_COMPANION.md P1): scan + correlate +
  bond + push time. BT members join the Air port.
- **P3 — Companion panel**: weather/notification/battery/media over BT; "Sync
  all" across links; the light Companion panel for BT-only watches.
- **P4 — Polish**: mDNS/discovery for WiFi watches (if AsteroidOS advertises),
  auto-move dock↔Air on undock/redock, trust management.

## Open questions

1. **SSH over WiFi.** Does developer-mode `sshd` listen on wlan0 (reachable at
   the WiFi IP), or only on the USB RNDIS gadget? P1 hinges on this — verify on a
   watch (roadmap `ssh-full-feature-parity` already names WiFi-SSH as a distinct
   link, so it is expected to work). If sshd is USB-only, WiFi Air needs a watch-
   side sshd-on-wlan0 tweak.
2. **Probing cost.** Each Air member costs a reachability probe per status cycle
   (SSH connect / BT ping). Background it; cap concurrency; show last-known while
   probing — never block the USB table.
3. **Dock ↔ Air handoff.** When a watch re-docks, it should collapse back to its
   USB row (not show twice). Key both by serial and prefer the USB row when
   present; the Air entry becomes dormant, reactivated on undock.
4. **Bond authentication level** (BLUETOOTH_COMPANION.md §C) — the one thing that
   needs a real watch + mo to confirm.
5. **Ownership vs a phone.** A watch bonded to both the rig and a phone: scope the
   rig as a *bench/fleet* companion, and be explicit about which watches it syncs,
   so two companions don't fight over time/weather.

## The shape of it

The dock manages what's *here*; the Air port manages what's *out there but still
mine*. Same fleet, same table, same actions where the link allows them — the
watch that walked off your wrist and onto WiFi is still one row down from the one
in the cradle. That is the attention-to-detail-over-the-whole-fleet thing, made
architectural.
