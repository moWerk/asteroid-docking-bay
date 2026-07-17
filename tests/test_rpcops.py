# SPDX-License-Identifier: GPL-3.0-only
"""Integrity of the op table and the frontend's use of it.

The web routes and the op table are two sides of one contract; these tests
pin them together so a renamed op or a route calling a nonexistent one
fails here instead of returning ok:false to a browser."""

import re
from pathlib import Path

import pytest

from asteroid_docking_bay import rpcops
from asteroid_docking_bay.rpc import RpcError
from asteroid_docking_bay.lastseen import LastSeen

WEBAPP_SRC = (Path(__file__).resolve().parent.parent
              / "asteroid_docking_bay" / "webapp.py").read_text()

REGISTERED = set(rpcops.DISPATCH._data) | set(rpcops.DISPATCH._stream)


def test_every_frontend_op_is_registered():
    from asteroid_docking_bay.webapp import _JSON_ROUTES
    called = {spec[2] for spec in _JSON_ROUTES}
    called |= set(re.findall(r'_call\("([\w.]+)"', WEBAPP_SRC))
    called |= set(re.findall(r'_sse\("([\w.]+)"', WEBAPP_SRC))
    missing = sorted(called - REGISTERED)
    assert not missing, (
        f"webapp dispatches op(s) the table doesn't register: {missing}")


def test_no_op_is_both_data_and_stream():
    both = set(rpcops.DISPATCH._data) & set(rpcops.DISPATCH._stream)
    assert not both, f"op(s) registered as both kinds: {sorted(both)}"


def test_registered_ops_are_the_documented_contract():
    """The allow-list IS the security boundary: adding an op must be a
    conscious, reviewed act. If this fails because you added one, update it
    here and in docs/CONTAINERS.md — that is the point."""
    assert REGISTERED == {
        "status.get",
        "watch.cc", "watch.toggle", "watch.settime", "watch.notify",
        "watch.buzz", "watch.screen", "watch.screenshot", "screen.release_all",
        "watch.backup", "watch.restore", "watch.diagnostics",
        "watch.image", "ssh.switch_adb",
        "port.set", "port.cycle", "port.poweroff", "port.reboot",
        "port.bootloader", "port.hide", "hub.hide",
        "charge.start", "charge.stop",
        "workbench.start", "workbench.stop",
        "drain.start", "drain.stop", "drain.history",
        "flash.start", "onboard.start",
    }


# ── handler behavior with mocked hardware ────────────────────────────────────

def test_port_set_maps_runtime_error(monkeypatch):
    def boom(loc, port, on):
        raise RuntimeError("hub said no")
    monkeypatch.setattr(rpcops, "uhubctl_set_power", boom)
    d = rpcops.DISPATCH._data["port.set"]({"loc": "1-1", "port": 1, "on": True})
    assert d == {"ok": False, "error": "hub said no"}


def test_port_set_ok(monkeypatch):
    monkeypatch.setattr(rpcops, "uhubctl_set_power", lambda l, p, o: True)
    d = rpcops.DISPATCH._data["port.set"]({"loc": "1-1", "port": 1, "on": True})
    assert d == {"ok": True, "confirmed": True}


def test_watch_toggle_rejects_unknown_tech():
    d = rpcops.DISPATCH._data["watch.toggle"](
        {"serial": "S", "tech": "nfc", "on": True})
    assert d["ok"] is False and "unknown toggle" in d["error"]


def test_poweroff_without_serial_still_cuts(monkeypatch):
    cut = {}
    monkeypatch.setattr(rpcops, "find_serial_for_loc_port", lambda c, l, p: None)
    monkeypatch.setattr(rpcops, "load_config", lambda: {})
    monkeypatch.setattr(rpcops, "uhubctl_set_power",
                        lambda l, p, o: cut.setdefault("done", True))
    d = rpcops.DISPATCH._data["port.poweroff"]({"loc": "1-1", "port": 2})
    assert d["ok"] is True and d["adb_shutdown"] is False and cut["done"]


def test_charge_start_reports_running(monkeypatch):
    monkeypatch.setattr(rpcops.ChargeOp, "is_active",
                        classmethod(lambda cls, slot: True))
    monkeypatch.setattr(rpcops, "_charge_tasks",
                        {"1-1:1": {"charge_end_ts": 42}})
    d = rpcops.DISPATCH._data["charge.start"]({"loc": "1-1", "port": 1})
    assert d["ok"] is False and d["charge_end_ts"] == 42


def test_hide_on_unknown_hub(monkeypatch):
    monkeypatch.setattr(rpcops, "load_config", lambda: {"hubs": []})
    d = rpcops.DISPATCH._data["port.hide"]({"loc": "9-9", "port": 1})
    assert d == {"ok": False, "error": "hub not found"}


class _FakeWatch:
    def __init__(self, serial, data):
        self._data = data
    def cc_data(self):
        return self._data


def test_watch_cc_live_returns_and_caches(monkeypatch, tmp_path):
    ls = LastSeen(tmp_path / "ls.json")
    monkeypatch.setattr(rpcops, "last_seen", ls)
    monkeypatch.setattr(rpcops, "Watch",
                        lambda s: _FakeWatch(s, {"kernel": "x", "serial": s}))
    d = rpcops.DISPATCH._data["watch.cc"]({"serial": "S1"})
    assert d["kernel"] == "x" and "stale" not in d
    assert ls.get("S1")["cc"]["kernel"] == "x"


def test_watch_cc_offline_serves_stale(monkeypatch, tmp_path):
    ls = LastSeen(tmp_path / "ls.json")
    monkeypatch.setattr(rpcops, "last_seen", ls)
    monkeypatch.setattr(rpcops, "Watch", lambda s: _FakeWatch(s, {"kernel": "x"}))
    rpcops.DISPATCH._data["watch.cc"]({"serial": "S1"})       # seed while live
    monkeypatch.setattr(rpcops, "Watch", lambda s: _FakeWatch(s, {}))  # offline
    d = rpcops.DISPATCH._data["watch.cc"]({"serial": "S1"})
    assert d["kernel"] == "x" and d["stale"] is True and d["last_live_ts"] > 0


def test_watch_cc_offline_uncached_is_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(rpcops, "last_seen", LastSeen(tmp_path / "ls.json"))
    monkeypatch.setattr(rpcops, "Watch", lambda s: _FakeWatch(s, {}))
    assert rpcops.DISPATCH._data["watch.cc"]({"serial": "S1"}) == {}


def _fake_watch_cls(shot_return, last_path):
    class _W:
        def __init__(self, serial):
            pass
        def screenshot(self):
            return shot_return
        def last_screenshot_path(self):
            return last_path
    return _W


def test_watch_screenshot_stale_fallback(monkeypatch, tmp_path):
    shot = tmp_path / "s.jpg"; shot.write_bytes(b"\xff\xd8jpg")
    # Fresh capture fails (offline) but a last pull exists → serve it stale.
    monkeypatch.setattr(rpcops, "Watch", _fake_watch_cls(None, shot))
    d = rpcops.DISPATCH._data["watch.screenshot"]({"serial": "S1"})
    assert d["ok"] and d["stale"] is True and d["captured_ts"] > 0


def test_watch_screenshot_fresh_is_not_stale(monkeypatch, tmp_path):
    shot = tmp_path / "s.jpg"; shot.write_bytes(b"\xff\xd8jpg")
    monkeypatch.setattr(rpcops, "Watch", _fake_watch_cls(shot, shot))
    d = rpcops.DISPATCH._data["watch.screenshot"]({"serial": "S1"})
    assert d["ok"] and d["stale"] is False


def test_watch_screenshot_fails_when_never_captured(monkeypatch, tmp_path):
    monkeypatch.setattr(rpcops, "Watch",
                        _fake_watch_cls(None, tmp_path / "nope.jpg"))
    d = rpcops.DISPATCH._data["watch.screenshot"]({"serial": "S1"})
    assert d["ok"] is False


def test_flash_start_unmapped_port_streams_error(monkeypatch):
    monkeypatch.setattr(rpcops, "load_config",
                        lambda: {"hubs": [], "serials": {}})
    monkeypatch.setattr(rpcops, "find_codename_for_loc_port",
                        lambda c, l, p: None)
    frames = list(rpcops.DISPATCH._stream["flash.start"](
        {"loc": "9-9", "port": 9}))
    assert frames == ["ERROR: port not mapped to any codename"]
