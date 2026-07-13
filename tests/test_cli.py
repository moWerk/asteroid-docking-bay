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
