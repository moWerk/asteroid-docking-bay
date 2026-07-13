# SPDX-License-Identifier: GPL-3.0-only
"""fake-power self-heal: only cycle a wedged, idle, opt-in port — and only
once per episode. Guards a hardware-actuating path, so it's worth pinning."""

import asteroid_docking_bay.webstatus as ws


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
