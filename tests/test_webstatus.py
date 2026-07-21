# SPDX-License-Identifier: GPL-3.0-only
"""fake-power self-heal: only cycle a wedged, idle, opt-in port — and only
once per episode. Guards a hardware-actuating path, so it's worth pinning."""

import asteroid_docking_bay.webstatus as ws
from asteroid_docking_bay.lastseen import LastSeen


class _SyncThread:
    """Run the daemon cycle inline so the test can observe it."""
    def __init__(self, target, args=(), daemon=None):
        self._target, self._args = target, args

    def start(self):
        self._target(*self._args)


def _setup(monkeypatch, enabled=True):
    calls = []
    monkeypatch.setattr(ws, "uhubctl_cycle", lambda loc, port: calls.append((loc, port)))
    monkeypatch.setattr(ws.threading, "Thread", _SyncThread)
    ws._fake_power_since.clear()
    ws._fake_power_cycled.clear()
    cfg = {"charge": {"fake_power_self_heal": enabled}}
    return calls, cfg


def test_heals_after_grace(monkeypatch):
    calls, cfg = _setup(monkeypatch)
    ws._fake_power_since["1-2:1"] = 0        # wedged since the epoch → past grace
    ws._maybe_self_heal_fake_power("1-2:1", "1-2", 1, wedged=True, busy=False, cfg=cfg)
    assert calls == [("1-2", 1)]


def test_no_heal_within_grace(monkeypatch):
    calls, cfg = _setup(monkeypatch)
    # First sighting starts the clock; nothing fires yet.
    ws._maybe_self_heal_fake_power("1-2:1", "1-2", 1, wedged=True, busy=False, cfg=cfg)
    assert calls == []


def test_no_heal_when_busy(monkeypatch):
    calls, cfg = _setup(monkeypatch)
    ws._fake_power_since["1-2:1"] = 0
    ws._maybe_self_heal_fake_power("1-2:1", "1-2", 1, wedged=True, busy=True, cfg=cfg)
    assert calls == [] and "1-2:1" not in ws._fake_power_since


def test_no_heal_when_disabled(monkeypatch):
    calls, cfg = _setup(monkeypatch, enabled=False)
    ws._fake_power_since["1-2:1"] = 0
    ws._maybe_self_heal_fake_power("1-2:1", "1-2", 1, wedged=True, busy=False, cfg=cfg)
    assert calls == []


def test_backoff_prevents_repeat(monkeypatch):
    import time
    calls, cfg = _setup(monkeypatch)
    ws._fake_power_since["1-2:1"] = 0
    ws._fake_power_cycled["1-2:1"] = time.time()   # just cycled
    ws._maybe_self_heal_fake_power("1-2:1", "1-2", 1, wedged=True, busy=False, cfg=cfg)
    assert calls == []


# ── stale-value fallback (_battery_view) ─────────────────────────────────────

def test_battery_view_records_live_and_offers_no_stale(monkeypatch, tmp_path):
    monkeypatch.setattr(ws, "last_seen", LastSeen(tmp_path / "ls.json"))
    # A live watch stores its reading and returns no stale fallback — the
    # caller's live `battery` must not be shadowed by a cached one.
    assert ws._battery_view("device", "S1", 55, False, "aos") == (None, None)
    assert ws.last_seen.get("S1")["battery"] == 55


def test_battery_view_falls_back_when_offline(monkeypatch, tmp_path):
    monkeypatch.setattr(ws, "last_seen", LastSeen(tmp_path / "ls.json"))
    ws._battery_view("device", "S1", 55, False, "aos")     # seed while live
    battery_cached, last_live_ts = ws._battery_view(None, "S1", None, False, None)
    assert battery_cached == 55 and last_live_ts > 0


def test_battery_view_blank_without_a_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(ws, "last_seen", LastSeen(tmp_path / "ls.json"))
    assert ws._battery_view(None, "S1", None, False, None) == (None, None)


# ── geometry: probe once when live, then serve from cache ────────────────────

def test_geometry_view_probes_once_then_caches(monkeypatch, tmp_path):
    monkeypatch.setattr(ws, "last_seen", LastSeen(tmp_path / "ls.json"))
    calls = []

    class _W:
        def __init__(self, serial):
            pass
        def geometry(self):
            calls.append(1)
            return {"round": True, "resolution": "360x360"}

    monkeypatch.setattr(ws, "Watch", _W)
    g1 = ws._geometry_view("device", "S1")
    g2 = ws._geometry_view("device", "S1")     # cached → must not re-probe
    assert g1["round"] is True and g2 == g1 and len(calls) == 1


def test_geometry_view_offline_without_cache_is_none(monkeypatch, tmp_path):
    monkeypatch.setattr(ws, "last_seen", LastSeen(tmp_path / "ls.json"))
    assert ws._geometry_view(None, "S1") is None


def test_geometry_view_offline_reads_cache_without_probing(monkeypatch, tmp_path):
    ls = LastSeen(tmp_path / "ls.json")
    monkeypatch.setattr(ws, "last_seen", ls)
    ls.record("S1", geometry={"round": True, "resolution": "400x400"})
    # If it tried to probe an offline watch this would blow up.
    monkeypatch.setattr(ws, "Watch",
                        lambda s: (_ for _ in ()).throw(AssertionError("probed!")))
    assert ws._geometry_view(None, "S1")["resolution"] == "400x400"


def test_geometry_cache_refreshes_when_the_probe_gained_a_field(monkeypatch, tmp_path):
    """A watch cached before a new probe field existed must re-probe, not serve
    the stale shape forever. This bit for real: the bootloader codename
    detector shipped and every already-cached watch kept reporting no
    bootloader, because the cache was 'probe once, keep forever'."""
    from asteroid_docking_bay import webstatus as ws
    from asteroid_docking_bay.lastseen import LastSeen
    from asteroid_docking_bay.watchctl import GEOMETRY_PROBE_VERSION

    ls = LastSeen(tmp_path / "ls.json")
    ls.record("S1", geometry={"round": True, "resolution": "454x454"})  # no probe_v
    monkeypatch.setattr(ws, "last_seen", ls)

    class _W:
        def __init__(self, serial): pass
        def geometry(self):
            # The probe reports what it read; the cache layer stamps probe_v.
            return {"round": True, "resolution": "454x454",
                    "bootloader": "rover-03.02.39.03.16"}
    monkeypatch.setattr(ws, "Watch", _W)

    got = ws._geometry_view("device", "S1")
    assert got.get("bootloader") == "rover-03.02.39.03.16", (
        f"stale cache served instead of re-probing: {got}")

    # A current cache must NOT re-probe (the probe costs three adb round trips).
    def _boom(serial):
        raise AssertionError("re-probed a cache that was already current")
    monkeypatch.setattr(ws, "Watch", _boom)
    assert ws._geometry_view("device", "S1")["bootloader"] == "rover-03.02.39.03.16"


def test_fb_draining_flags_a_watch_left_in_the_bootloader(monkeypatch, tmp_path):
    """A watch that vanished from an unpowered port while it was in fastboot is
    still running on battery: LK does not shut down when USB goes away
    (measured 2026-07-18 — sturgeon reappeared 4s after power returned, where a
    cold boot takes ~20s). With the port off there is nothing left to read, so
    the only way to warn is to remember the state it vanished in. This is the
    failure that deep-discharged sturgeon to 0%."""
    from asteroid_docking_bay import webstatus as ws
    from asteroid_docking_bay.lastseen import LastSeen

    ls = LastSeen(tmp_path / "ls.json")
    monkeypatch.setattr(ws, "last_seen", ls)

    ls.record("S1", last_conn_state="fastboot")
    assert (ls.get("S1") or {}).get("last_conn_state") == "fastboot"

    # A watch last seen booted must NOT raise the warning — only fastboot
    # keeps running through a VBUS cut in the way this flag describes.
    ls.record("S2", last_conn_state="device")
    assert (ls.get("S2") or {}).get("last_conn_state") == "device"


def test_last_conn_state_is_not_erased_by_an_offline_poll(tmp_path):
    """record() ignores None fields, so a poll that sees nothing must not wipe
    the remembered state — that is precisely when the warning is needed."""
    from asteroid_docking_bay.lastseen import LastSeen
    ls = LastSeen(tmp_path / "ls.json")
    ls.record("S1", last_conn_state="fastboot")
    ls.record("S1", last_conn_state=None, battery=None)
    assert (ls.get("S1") or {}).get("last_conn_state") == "fastboot", (
        "an offline poll erased the state the warning depends on")


def test_lifecycle_down_only_after_a_graceful_shutdown(monkeypatch):
    """"down" is the one power-state we assert: a confirmed graceful shutdown
    (safe_off_ts) with the watch not seen live since and its port off. A raw
    port cut never stamps safe_off_ts, so it stays unmarked — absence is "no
    claim", never a false "definitely off"."""
    from asteroid_docking_bay import webstatus as ws
    store = {}
    monkeypatch.setattr(ws.last_seen, "get", lambda s: store.get(s))

    # Gracefully powered off: safe_off stamped at/after it was last seen live
    # (the real poweroff records both at the same "now").
    store["S1"] = {"last_live_ts": 1000.0, "safe_off_ts": 1000.0}
    assert ws._lifecycle("S1", present=False, power=False) == "down"
    # Its port is powered again (booting) -> not "down" anymore.
    assert ws._lifecycle("S1", present=False, power=True) is None
    # It is back on the bus -> not "down".
    assert ws._lifecycle("S1", present=True, power=True) is None
    # A watch cut raw (seen live, no safe_off) is NOT claimed down.
    store["S2"] = {"last_live_ts": 1000.0}
    assert ws._lifecycle("S2", present=False, power=False) is None


def test_lifecycle_self_clears_when_seen_live_again(monkeypatch):
    """After the watch is seen live again, last_live_ts advances past
    safe_off_ts and the claim drops with no explicit clear."""
    from asteroid_docking_bay import webstatus as ws
    store = {"S1": {"last_live_ts": 1000.0, "safe_off_ts": 1000.0}}
    monkeypatch.setattr(ws.last_seen, "get", lambda s: store.get(s))
    assert ws._lifecycle("S1", False, False) == "down"
    store["S1"]["last_live_ts"] = 3000.0   # seen live again
    assert ws._lifecycle("S1", False, False) is None


def test_wear_makes_a_departed_watch_worn_not_down(monkeypatch):
    """A wear-held watch that has left the bus is 'worn' (off-rig), overriding
    any 'down' — and while still docked it shows no pill (the button carries
    the armed state)."""
    from asteroid_docking_bay import webstatus as ws
    store = {"S1": {"wear": True, "safe_off_ts": 5000.0, "last_live_ts": 4000.0}}
    monkeypatch.setattr(ws.last_seen, "get", lambda s: store.get(s))
    assert ws._lifecycle("S1", present=False, power=True) == "worn"  # port held, gone
    assert ws._lifecycle("S1", present=True, power=True) is None     # docked, topping up
