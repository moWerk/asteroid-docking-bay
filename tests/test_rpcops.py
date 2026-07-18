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
        "watch.cc", "watch.timeline",
        "watch.toggle", "watch.settime", "watch.notify",
        "watch.buzz", "watch.screen", "watch.screenshot", "screen.release_all",
        "watch.backup", "watch.restore", "watch.diagnostics", "watch.fbreport",
        "watch.image", "ssh.switch_adb",
        "port.set", "port.cycle", "port.poweroff", "port.reboot",
        "port.bootloader", "port.recovery", "port.continue",
        "port.hide", "hub.hide",
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


def test_port_cycle_records_smart_verdict(monkeypatch):
    saved = {}
    monkeypatch.setattr(rpcops, "find_serial_for_loc_port", lambda c, l, p: "S1")
    monkeypatch.setattr(rpcops, "test_port_power_switching",
                        lambda l, p, s: (True, "VBUS cut confirmed"))
    monkeypatch.setattr(rpcops, "load_config",
                        lambda: {"hubs": [{"location": "1-2", "port_smart": {}}]})
    monkeypatch.setattr(rpcops, "save_config", lambda cfg: saved.update(cfg=cfg))
    d = rpcops.DISPATCH._data["port.cycle"]({"loc": "1-2", "port": 2})
    assert d["ok"] is True and d["smart"] is True
    assert saved["cfg"]["hubs"][0]["port_smart"]["2"] is True


def test_port_cycle_inconclusive_does_not_save(monkeypatch):
    calls = {}
    monkeypatch.setattr(rpcops, "find_serial_for_loc_port", lambda c, l, p: None)
    monkeypatch.setattr(rpcops, "test_port_power_switching",
                        lambda l, p, s: (None, "unverified"))
    monkeypatch.setattr(rpcops, "load_config",
                        lambda: {"hubs": [{"location": "1-2", "port_smart": {}}]})
    monkeypatch.setattr(rpcops, "save_config",
                        lambda cfg: calls.setdefault("saved", True))
    d = rpcops.DISPATCH._data["port.cycle"]({"loc": "1-2", "port": 2})
    assert d["ok"] is True and d["smart"] is None and "saved" not in calls


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


def test_fbreport_writes_downloadable_text(monkeypatch, tmp_path):
    monkeypatch.setattr(rpcops, "DIAG_ROOT", tmp_path)
    monkeypatch.setattr(rpcops, "load_config", lambda: {})
    monkeypatch.setattr(rpcops, "find_serial_for_loc_port", lambda c, l, p: "S1")
    monkeypatch.setattr(rpcops, "find_codename_for_loc_port", lambda c, l, p: "sturgeon")
    monkeypatch.setattr(rpcops, "fastboot_getvar_all",
                        lambda s: "product:sturgeon\nbattery-voltage:3668mV")
    d = rpcops.DISPATCH._data["watch.fbreport"]({"loc": "1-2", "port": 1})
    assert d["ok"] and d["name"].startswith("sturgeon-")
    assert d["name"].endswith("-fastboot.txt") and d["lines"] == 2
    assert "battery-voltage:3668mV" in (tmp_path / d["name"]).read_text()


def test_fbreport_needs_a_fastboot_device(monkeypatch, tmp_path):
    monkeypatch.setattr(rpcops, "DIAG_ROOT", tmp_path)
    monkeypatch.setattr(rpcops, "load_config", lambda: {})
    monkeypatch.setattr(rpcops, "find_serial_for_loc_port", lambda c, l, p: "S1")
    monkeypatch.setattr(rpcops, "fastboot_getvar_all", lambda s: "")
    d = rpcops.DISPATCH._data["watch.fbreport"]({"loc": "1-2", "port": 1})
    assert d["ok"] is False and "bootloader" in d["error"]


def test_watch_timeline_returns_battery_points(monkeypatch):
    class _EL:
        def read(self, serial, codename=None):
            return [
                {"event": "check_reading", "ts": 100, "pct": 80},
                {"event": "charge_start", "ts": 150},
                {"event": "drain_reading", "ts": 200, "pct": 70},
                {"event": "flash", "ts": 250},          # no pct → excluded
            ]
        def standby_loss_rate(self, serial, codename, evs):
            return 1.5
    monkeypatch.setattr(rpcops, "event_log", _EL())
    d = rpcops.DISPATCH._data["watch.timeline"]({"serial": "S1"})
    assert d["rate"] == 1.5
    assert d["points"] == [{"ts": 100, "pct": 80}, {"ts": 200, "pct": 70}]


def test_watch_cc_attaches_cached_resolution(monkeypatch, tmp_path):
    ls = LastSeen(tmp_path / "ls.json")
    monkeypatch.setattr(rpcops, "last_seen", ls)
    ls.record("S1", geometry={"round": True, "resolution": "360x360"})
    monkeypatch.setattr(rpcops, "Watch", lambda s: _FakeWatch(s, {"kernel": "x"}))
    d = rpcops.DISPATCH._data["watch.cc"]({"serial": "S1"})
    assert d["resolution"] == "360x360" and d["geometry"]["round"] is True


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


# ── fastboot-aware power actions ────────────────────────────────────────────

def _cap_cmd(monkeypatch, in_fastboot):
    """Capture the command a power op would run, with the port's watch either
    in fastboot or on adb."""
    import asteroid_docking_bay.rpcops as ro
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return 0, "", ""

    monkeypatch.setattr(ro, "_run", fake_run)
    monkeypatch.setattr(ro, "find_serial_for_loc_port", lambda *a, **k: "S1")
    monkeypatch.setattr(ro, "load_config", lambda: {"hubs": []})
    monkeypatch.setattr(ro, "_fastboot_list",
                        lambda: ({"S1": "sturgeon"} if in_fastboot else {}))
    return ro, seen


def test_power_actions_use_fastboot_when_watch_is_in_bootloader(monkeypatch):
    """A watch in the bootloader speaks fastboot, not adb. Sending it an adb
    command is a silent no-op that leaves the UI claiming success, which is
    why the menu was previously hidden entirely in fastboot."""
    ro, seen = _cap_cmd(monkeypatch, in_fastboot=True)
    ro.DISPATCH._data["port.reboot"]({"loc": "1-2", "port": 1})
    assert seen["cmd"].startswith("fastboot -s S1 "), seen["cmd"]
    assert "adb" not in seen["cmd"]

    ro.DISPATCH._data["port.bootloader"]({"loc": "1-2", "port": 1})
    assert seen["cmd"] == "fastboot -s S1 reboot bootloader", seen["cmd"]

    ro.DISPATCH._data["port.recovery"]({"loc": "1-2", "port": 1})
    assert seen["cmd"] == "fastboot -s S1 reboot recovery", seen["cmd"]


def test_power_actions_use_adb_when_watch_is_booted(monkeypatch):
    ro, seen = _cap_cmd(monkeypatch, in_fastboot=False)
    ro.DISPATCH._data["port.reboot"]({"loc": "1-2", "port": 1})
    assert seen["cmd"] == "adb -s S1 reboot", seen["cmd"]

    ro.DISPATCH._data["port.recovery"]({"loc": "1-2", "port": 1})
    assert seen["cmd"] == "adb -s S1 reboot recovery", seen["cmd"]


def test_continue_is_rejected_on_a_booted_watch(monkeypatch):
    """`fastboot continue` resumes a boot chain; a running watch has none.
    Offering it over adb would send a meaningless command and report ok."""
    ro, seen = _cap_cmd(monkeypatch, in_fastboot=False)
    r = ro.DISPATCH._data["port.continue"]({"loc": "1-2", "port": 1})
    assert r["ok"] is False and "adb" in r["error"], r
    assert "cmd" not in seen, f"ran a command anyway: {seen}"


def test_fastboot_poweroff_uses_oem_poweroff_then_cuts_vbus(monkeypatch):
    """LK cannot shut down with USB attached — it grants ~5s to disconnect.
    The rig cuts VBUS itself, so the order (command first, power second) is
    load-bearing: cutting first would strand the watch running on battery."""
    import asteroid_docking_bay.rpcops as ro
    order = []
    monkeypatch.setattr(ro, "_run",
                        lambda cmd, **kw: (order.append(cmd), (0, "", ""))[1])
    monkeypatch.setattr(ro, "find_serial_for_loc_port", lambda *a, **k: "S1")
    monkeypatch.setattr(ro, "load_config", lambda: {"hubs": []})
    monkeypatch.setattr(ro, "_fastboot_list", lambda: {"S1": "sturgeon"})
    monkeypatch.setattr(ro, "uhubctl_set_power",
                        lambda *a, **k: order.append("VBUS_OFF") or True)
    r = ro.DISPATCH._data["port.poweroff"]({"loc": "1-2", "port": 1})
    assert r["ok"] is True, r
    assert order == ["fastboot -s S1 oem poweroff", "VBUS_OFF"], order


def test_failed_fastboot_poweroff_does_not_cut_vbus(monkeypatch):
    """`oem poweroff` is not universal — rover's bootloader lacks it entirely.
    Cutting VBUS after a failed shutdown strands the watch running on battery
    in the bootloader, invisible to the host: the rig's worst failure mode.
    A failed shutdown must leave power ON and say so."""
    import asteroid_docking_bay.rpcops as ro
    cut = {}
    monkeypatch.setattr(ro, "_run", lambda cmd, **kw: (1, "", "unknown command"))
    monkeypatch.setattr(ro, "find_serial_for_loc_port", lambda *a, **k: "S1")
    monkeypatch.setattr(ro, "load_config", lambda: {"hubs": []})
    monkeypatch.setattr(ro, "_fastboot_list", lambda: {"S1": "rover"})
    monkeypatch.setattr(ro, "uhubctl_set_power",
                        lambda *a, **k: cut.setdefault("done", True))
    r = ro.DISPATCH._data["port.poweroff"]({"loc": "1-2", "port": 1})
    assert r["ok"] is False, r
    assert "done" not in cut, "cut VBUS after a failed fastboot shutdown"


# ── port ops must not disturb a running operation ───────────────────────────
#
# The UI greys these controls out on a busy row, but the UI is not a safety
# boundary. On 2026-07-18 a direct `POST /api/on` to test an unrelated feature
# re-powered a port mid-drain, recharged the watch 96% -> 100%, and destroyed
# five hours of readings while the browser correctly showed the row disabled.

@pytest.mark.parametrize("op,args", [
    ("port.set",        {"on": True}),
    ("port.cycle",      {}),
    ("port.poweroff",   {}),
    ("port.reboot",     {}),
    ("port.bootloader", {}),
])
def test_port_ops_refuse_while_an_operation_owns_the_port(monkeypatch, op, args):
    import asteroid_docking_bay.rpcops as ro
    touched = {}
    monkeypatch.setattr(ro.DrainOp, "is_active", classmethod(lambda cls, slot: True))
    monkeypatch.setattr(ro, "uhubctl_set_power",
                        lambda *a, **k: touched.setdefault("power", True))
    monkeypatch.setattr(ro, "uhubctl_cycle",
                        lambda *a, **k: touched.setdefault("cycle", True))
    monkeypatch.setattr(ro, "test_port_power_switching",
                        lambda *a, **k: touched.setdefault("ppps", True))
    monkeypatch.setattr(ro, "_run", lambda *a, **k: touched.setdefault("cmd", True))
    r = ro.DISPATCH._data[op]({"loc": "1-2.3", "port": 1, **args})
    assert r["ok"] is False and r.get("busy") == "drain", r
    assert not touched, f"{op} touched the hardware anyway: {touched}"


def test_port_ops_work_normally_when_no_operation_is_running(monkeypatch):
    """The guard must not break ordinary use — an idle port still switches."""
    import asteroid_docking_bay.rpcops as ro
    for cls in (ro.ChargeOp, ro.DrainOp, ro.WorkbenchOp):
        monkeypatch.setattr(cls, "is_active", classmethod(lambda c, slot: False))
    monkeypatch.setattr(ro, "uhubctl_set_power", lambda *a, **k: True)
    r = ro.DISPATCH._data["port.set"]({"loc": "1-2.3", "port": 1, "on": True})
    assert r == {"ok": True, "confirmed": True}, r
