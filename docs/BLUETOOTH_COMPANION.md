# Bluetooth companion / sync client — design (proposal)

Status: **proposal, feasibility-verified, nothing implemented yet.** Written
2026-07-23 during the docking-bay session. The idea is mo's: make the fleet
manager a Bluetooth companion to the watches — pair over the rig's BlueZ and
push time, weather and notifications the way a phone (GadgetBridge) does, with
all the connection config in the web UI.

This doc records what the watches expose over BLE, what the reference companion
(GadgetBridge) sends, how a Linux host drives it, and a phased plan. The
protocol facts are cross-checked between the watch daemon
(`AsteroidOS/asteroid-btsyncd`) and GadgetBridge; they agree 100%.

---

## DIRECTION CHANGE — Orbit-over-BT, not a sync companion (2026-07-23 pm, mo)

**The BLE-sync-companion framing below is superseded for P2.** mo's decision:
a-d-b will **not** re-emulate a phone sync client — we already push time,
weather and notifications over adb/ssh/wifi. BT joins the **Orbit port** as a
*diagnostic + onboarding* link, and the chosen path is:

> **Classic BT → pair → identify by MAC → PAN/BNEP → IP-over-BT → `SshTransport(bt_ip)`**,
> which reuses the *entire* existing a-d-b stack over BT with no per-feature code
> — exactly how WiFi did. Classic first because RFCOMM/PAN are simple, solved,
> well-supported from a modern Linux host; BLE (the sync stack) stays a distant
> maybe for asleep-watch battery-notify / buzz-to-find only.

### Confirmed this session (feeds tomorrow's hardware work)

- **The AsteroidOS sync stack is BLE-only.** `AsteroidOSSync` (cloned to
  `~/Git/AsteroidOSSync`, HEAD `510ec5c`) uses the Nordic Android-BLE-Library +
  BLE scanner; **zero** classic profiles (no RFCOMM/OBEX/PAN/L2CAP). So Bluetooth
  Classic does **not** expose the GATT sync services — confirming we should not
  try to borrow them.
- **Identity over the air is BT-MAC ONLY.** The sync protocol carries **no serial
  or codename** (no DIS `180A`, no `2A25`). ⇒ correlate a discovered watch to the
  fleet by **BT MAC**, captured once while docked (a-d-b already reads `hci0`
  address into the Network tab). Serial↔MAC is learned on the wire, never over BT.
- **Pairing** is OS-level, confirmed **on the watch** (Just-Works/numeric, no
  app-supplied PIN); the bond is persistent (`Trusted=true`). The web UI shows the
  pairing state and any passkey; the human confirms on the watch.
- **GATT map** (corrected, for the record / a possible far-future BLE path):
  base `0000XXXX-0000-0000-0000-00A57E401D05`; services end `71`, chars end `NN`.
  Time svc `5071`/char `5001` (6 bytes `[yr-1900,mon0-11,day,h,m,s]`); Weather svc
  `8071` chars `8001` city / `8002` ids / `8003` min / `8004` max (5×BE int16,
  Kelvin); Notif svc `9071`/`9001`; Media `7071`; Screenshot `6071`; Battery
  standard `180F`/`2A19` (NOTIFY, 1 byte). Chars need a **bonded/encrypted link**.
- **bluez versions** (the new Network data point): host w541 **5.87**, skipjack
  **5.79** — both modern *userspace*. The real constraint is the **kernel BT =
  4.1-subsystem backport** (RAG `wiki_reference`/`pike_ble_arc`), which limits
  MGMT/BLE — matters far less for **classic** from a modern host. `asteroid-btsyncd`
  runs as ceres (DBus multiplexer BlueZ5↔apps).

### Open questions ONLY tomorrow's hardware can settle (BT 5.4 adapter)

1. **Classic discoverability.** The watch auto-enables BT + discovery, but the
   AsteroidOS marker (`…1D05`) is *BLE-advertised* — it won't show on a classic
   inquiry. So: does the watch answer a **BR/EDR inquiry** at all, and how do we
   recognize it (device name = watch/codename? class-of-device?)? Verify with
   `bluetoothctl scan on` / `hcitool inq` once the 5.4 adapter is in.
2. **PAN feasibility — the linchpin.** IP-over-BT needs the watch to run a PAN
   role (PANU) and get an address over `bnep0`. Neither AsteroidOSSync nor the
   watch sync stack does PAN, so this likely needs **watch-side connman/bluez
   config** (possibly a meta-nemo/-smartwatch addition). If the watch won't PAN
   out of the box, fall back to RFCOMM for a shell/identity channel and treat
   PAN-IP as a follow-up. **Test PAN before building the Orbit-BT UI on top of it.**
3. **Multi-pair / serialized connect.** Confirm the rig can bond several watches
   and connect them one at a time (simultaneous not needed).
4. **Toggle BLE↔classic** on the watch, if discoverability (Q1) needs it.

### Watch-side BT record (mo's "all watches get a BT record")

Store per serial in config, learned while docked: `{bt_mac, paired: bool,
last_bt_link: ts}`. MAC is the correlation key (Q about serial-over-BT is
answered: no). This slots beside the `orbit` members; a BT-reachable member gets
a `bt` subkey `{mac, bonded}` alongside `ip`, per AIR→ORBIT_FLEET.md's data model.

---

## Why this is compelling

The rig already docks the whole fleet over USB, and 0.8's transport work lets
every per-watch feature run over ADB **or** SSH. Bluetooth is the third wire —
and the *native* one: it is exactly how a watch is meant to receive time,
weather and notifications from a companion. Doing it from the rig turns a-d-b
into a bench-side GadgetBridge for the fleet, and — because the rig sees the
whole fleet at once — into something a phone companion is not: a fleet-wide
sync/notification test harness.

## Feasibility — verified on the w541 (2026-07-23)

- **The rig is a BLE central.** Adapter `CC:3D:82:71:9E:E9` (`hci0`), powered,
  `Roles: central`, not rfkill-blocked, BlueZ over D-Bus available.
- **Watches advertise by codename.** A scan found `skipjack`, `beluga`,
  `medaka`, `pike` advertising with their codename as the BLE name — exactly how
  GadgetBridge identifies them (it matches the name against a
  `KNOWN_DEVICE_CODENAMES` list; the advertised service UUID is often not
  surfaced by scanners, so name-match is the reliable path).
- **The advertised MAC correlates to the docked fleet.** skipjack advertised
  `98:28:A6:E8:05:FB` — identical to the BT adapter MAC a-d-b now reads over
  ADB/SSH (`/sys/class/bluetooth/hci0/address`, shown in the Network tab). So a
  scanned BLE device can be matched to a *specific docked watch* by BT MAC, with
  codename as a fallback. This is the linchpin: no guessing which advert is which
  watch.
- **Pairing needs a one-time on-watch confirm.** `Pair()` initiates but does not
  complete unbonded — the watch shows a pairing prompt a human accepts once. The
  watch daemon marks every writable characteristic `encrypt-authenticated-write`,
  so a bonded, encrypted link is required; a plain connect-and-write is rejected.
  After the one-time bond (persisted in `/var/lib/bluetooth`), reconnect + writes
  are automatic. **Consequence: the bond step is user-in-the-loop once per watch;
  everything after is hands-off.**

## The protocol (asteroid-btsyncd ↔ GadgetBridge)

Custom UUID base: `0000XXXX-0000-0000-0000-00A57E401D05` (note the non-SIG
suffix). Battery is standard SIG.

| Service | Characteristic | Dir (host view) | Payload |
|---|---|---|---|
| Time `00005071` | `00005001` | write | 6 bytes `[year-1900, month(0-11), day, hour, min, sec]` |
| Weather `00008071` | `…8001` city | write | UTF-8 city name |
| | `…8002` ids | write | 10 bytes = 5 days × 2-byte **big-endian** OWM condition id |
| | `…8003` min-temp | write | 10 bytes = 5 × 2-byte BE **Kelvin** |
| | `…8004` max-temp | write | 10 bytes = 5 × 2-byte BE **Kelvin** |
| Notification `00009071` | `…9001` update | write | UTF-8 XML `<insert>…</insert>` / `<removed><id>N</id></removed>` |
| Media `00007071` | `…7001-7003` title/album/artist | write | UTF-8 (MPRIS) |
| | `…7004` play | write | 1 byte: nonzero=playing, 0=paused |
| | `…7005` command | notify (watch→host) | 1 byte `0..4` = prev/next/play/pause/volume |
| | `…7006` volume | write | 1 byte 0-100 |
| Screenshot `00006071` | `…6001` req / `…6002` content | write / notify | write triggers; notify streams 4-byte LE size then 20-byte JPEG chunks |
| Battery `0000180F` (SIG) | `00002a19` (SIG) | read/notify | 1-byte percent (watch→host) |

Notification XML child tags: `pn` package, `id`, `an` app name, `ai` app icon,
`su` summary, `bo` body, `vb` vibrate (`none|normal|strong|ringtone`).

**Note the two asymmetries a companion must respect:** the Time payload's year
is `year-1900` and month is 0-based; the Weather arrays are big-endian Kelvin.
(The dconf-write weather path a-d-b already ships uses the same OWM codes + the
`round(°C)+273` Kelvin — the BT path would reuse that fetch/translate layer and
just re-encode as BE bytes.)

## How a-d-b would do it

Two layers, mirroring the existing ADB/SSH transport split:

1. **A `BtTransport` / companion module.** Talks to `org.bluez` over D-Bus. Two
   realistic implementations:
   - **`bleak`** (asyncio, wraps BlueZ) — ergonomic `write_gatt_char` /
     `start_notify`, but does bonding thinly; do the bond via BlueZ/`bluetoothctl`
     first, then bleak connects to the already-bonded device. Adds an asyncio
     dependency + an event loop in the (threaded) web process.
   - **Raw BlueZ D-Bus** via the `dbus`/`dbus-fast` stack a-d-b's containers plan
     already implies — no asyncio, more code. The op-table's existing threads fit
     this better than bleak's loop.
   Recommendation: prototype with `bleak` for speed; decide on the permanent
   dependency after P1.
2. **Ops + UI.** New ops behind the allow-list: `bt.scan` (discover + correlate
   to fleet by MAC/codename), `bt.pair` (initiate bond — surfaces "accept on the
   watch" in the UI), `bt.push_time` / `bt.push_weather` / `bt.notify`, and a
   `bt.status` per watch (bonded? connected? last sync?). The web UI grows a
   **Bluetooth** surface: a scan list that lines up scanned adverts with docked
   rows (the BT MAC already links them), a one-click **Pair** (with the
   accept-on-watch hint), and per-watch push buttons — or a fleet-wide "sync all".

### Fleet correlation (the neat part)

The status path already knows each watch's BT MAC (Network tab). A BLE scan
yields `{mac, name}`. Joining on MAC labels every advert with its docked row —
so the Bluetooth surface is not a separate device list, it is the *same fleet
table* with a BT column (unpaired / bonded / connected / synced Xm ago), and the
pair/sync actions sit on the row like the power and CC actions do.

## Phased plan

- **P1 — bond + time.** `bt.scan` + correlate; `bt.pair` (user accepts on watch
  once); connect + write the 6-byte time char. Proves the whole chain. UI: a BT
  status pill + Pair/Sync-time on the row.
- **P2 — weather over BT.** Reuse the existing Open-Meteo fetch/translate; encode
  the 3 arrays as BE Kelvin + city; write the 4 weather chars. (a-d-b then syncs
  weather over *whichever* wire — dconf-over-USB or GATT-over-BT.)
- **P3 — notifications.** Send a test notification as the `<insert>` XML — a real
  bench tool for testing a watch's notification rendering/vibration across the
  fleet. Subscribe to the battery notify for live % without USB.
- **P4 — media / screenshot / find-watch.** MPRIS push + the watch→host media
  commands; BT screenshot; a "buzz to find" over the notification vibrate.

## Open questions / risks

1. **Authentication level of the bond.** The daemon asks for *authenticated*
   encryption. A `NoInputNoOutput` "Just Works" bond may be treated as
   unauthenticated and get writes rejected (`NotPermitted`). Fallback: a
   `KeyboardDisplay` agent + confirm the passkey on the watch. Verify on first
   real bond (needs mo to accept on the watch).
2. **asyncio in the web process.** bleak is asyncio; a-d-b's web/op layer is
   threaded. Either run the BT loop in a dedicated thread with its own event
   loop, or go raw-D-Bus. Decide at P1.
3. **Bond persistence + multi-watch.** One adapter bonding to many watches is
   fine for BlueZ, but only one active GATT connection at a time is simplest;
   the sync loop would connect → push → disconnect per watch, like the SSH
   battery read does per status cycle.
4. **Coexistence with a real phone.** A watch bonded to the rig AND a phone —
   BLE allows multiple bonds, but pushing conflicting time/weather from two
   companions is a footgun. Scope the rig companion as a *bench* tool, or make it
   explicit which watches the rig owns.
5. **Containers threat model.** BT is another host capability the 0.5 backend
   container would own (like sysfs/adb); the frontend never touches BlueZ.

## What exists to build on

- The Open-Meteo fetch + WMO→OWM + Kelvin layer (`weather.py`) — reused verbatim
  for P2, only the encoding differs (dconf strings vs BE bytes).
- The BT MAC in the status/Network path — the correlation key.
- The op-table + allow-list pattern — the BT ops slot straight in.
- The transport abstraction — `BtTransport` is a natural third sibling to
  `AdbTransport`/`SshTransport`, though GATT is characteristic-writes, not a
  shell, so it is a looser fit than those two.
