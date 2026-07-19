# SPDX-License-Identifier: GPL-3.0-only
"""_web_busy_slots: the check-charge timer's decision-level handoff to a
running web service. Parses active ops from /api/status; empty when it's down."""

import io
import json
import urllib.request

from asteroid_docking_bay.cli import _web_busy_slots

_DOC = {"hubs": [{"location": "1-2", "ports": [
    {"port": 1, "drain": {"active": True}},
    {"port": 2, "charging_active": True},
    {"port": 3},                                   # idle → not busy
    {"port": 4, "workbench": {"active": True}},
    {"port": 5, "flashing": True},
    {"port": 6, "drain": {"active": False}},        # a finished drain → not busy
]}]}


class _Ctx:
    def __enter__(self):
        return io.BytesIO(json.dumps(_DOC).encode())

    def __exit__(self, *a):
        return False


def test_busy_slots_parsed(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda u, timeout=0: _Ctx())
    assert _web_busy_slots() == {"1-2:1", "1-2:2", "1-2:4", "1-2:5"}


def test_busy_slots_empty_when_web_down(monkeypatch):
    def boom(*a, **k):
        raise OSError("connection refused")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert _web_busy_slots() == set()


# ── status: fastboot visibility and machine-readable output ─────────────────

def _status_cfg():
    return {"hubs": [{"location": "1-2", "port_smart": {"1": True},
                      "ports": {"1": "sturgeon"}}],
            "serials": {"S1": "sturgeon"}}


def test_status_table_shows_a_watch_in_fastboot(monkeypatch, capsys):
    """A watch in the bootloader is absent from `adb devices`, so consulting
    only adb printed "--" — indistinguishable from unplugged. During a flash
    cycle that reads as "the watch is gone" when it is actually sitting in
    fastboot waiting for the next command."""
    import argparse
    from asteroid_docking_bay import cli
    monkeypatch.setattr(cli, "adb_devices", lambda: {})
    monkeypatch.setattr(cli, "_fastboot_devices", lambda: {"S1": "fastboot"})
    monkeypatch.setattr(cli, "uhubctl_get_power", lambda loc, port: True)
    monkeypatch.setattr(cli, "get_watch_codename", lambda s: None)
    cli.cmd_status(argparse.Namespace(json=False), _status_cfg())
    out = capsys.readouterr().out
    assert "fastboot" in out, f"fastboot state not shown in the table:\n{out}"
    assert "sturgeon" in out


def test_status_json_reuses_the_web_status_document(monkeypatch, capsys):
    """--json must emit the SAME document the web UI renders, not a second
    status implementation that can drift from it."""
    import argparse
    import json as _json
    from asteroid_docking_bay import cli, rpcops
    sentinel = {"hubs": [], "version": "test", "thresholds": {}}
    monkeypatch.setitem(rpcops.DISPATCH._data, "status.get", lambda args: sentinel)
    cli.cmd_status(argparse.Namespace(json=True), _status_cfg())
    assert _json.loads(capsys.readouterr().out) == sentinel


def test_status_json_does_not_touch_hardware(monkeypatch, capsys):
    """The JSON path must not also run the table's own adb/uhubctl scan —
    that would double the hardware work and could disagree with itself."""
    import argparse
    from asteroid_docking_bay import cli, rpcops
    def _boom(*a, **k):
        raise AssertionError("table scan ran during --json")
    monkeypatch.setattr(cli, "adb_devices", _boom)
    monkeypatch.setattr(cli, "uhubctl_get_power", _boom)
    monkeypatch.setitem(rpcops.DISPATCH._data, "status.get", lambda args: {"ok": 1})
    cli.cmd_status(argparse.Namespace(json=True), _status_cfg())
    assert "ok" in capsys.readouterr().out
