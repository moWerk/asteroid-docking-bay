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
