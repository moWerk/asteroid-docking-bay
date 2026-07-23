# SPDX-License-Identifier: GPL-3.0-only
"""Bluetooth scan correlation + pair op (bt.scan / bt.pair).

bt.py's D-Bus work is host-side and not unit-testable here; what matters in the
ops is the correlation — a scanned device is matched to the fleet by its BT-MAC
(the registry's stored btmac) or by the codename it advertises as its BT name —
and that pair refuses an empty MAC. (bt.scan/pair are monkeypatched; registry is
tmp-isolated by the autouse conftest fixture.)"""

import asteroid_docking_bay.rpcops as rpcops
from asteroid_docking_bay.registry import registry


def test_bt_scan_correlates_by_mac_and_name(monkeypatch):
    monkeypatch.setattr(rpcops.bt, "scan", lambda s: [
        {"mac": "98:28:A6:E8:05:FB", "name": "skipjack", "rssi": -50,
         "paired": False, "connected": False, "trusted": False},
        {"mac": "08:00:74:70:98:EE", "name": "medaka", "rssi": -60,
         "paired": False, "connected": False, "trusted": False},
        {"mac": "B8:69:C2:45:76:FF", "name": "JBL Charge 3", "rssi": -40,
         "paired": True, "connected": False, "trusted": True}])
    registry.note("S1", source="adb", codename="skipjack",
                  btmac="98:28:a6:e8:05:fb")             # known by MAC (lowercase in registry)
    monkeypatch.setattr(rpcops, "load_config",
                        lambda: {"hubs": [{"ports": {"1": "medaka"}}]})
    d = rpcops.DISPATCH._data["bt.scan"]({"seconds": 3})
    by = {x["mac"]: x for x in d["devices"]}
    # skipjack matched by MAC → carries the fleet serial
    assert by["98:28:A6:E8:05:FB"]["in_fleet"] and by["98:28:A6:E8:05:FB"]["serial"] == "S1"
    # medaka matched by the codename it advertises
    assert by["08:00:74:70:98:EE"]["in_fleet"] and by["08:00:74:70:98:EE"]["codename"] == "medaka"
    # the JBL is neither → not a fleet member
    assert by["B8:69:C2:45:76:FF"]["in_fleet"] is False
    # fleet watches sort first, peripherals last
    assert d["devices"][0]["in_fleet"] and d["devices"][-1]["in_fleet"] is False


def test_bt_pair_needs_a_mac(monkeypatch):
    assert rpcops.DISPATCH._data["bt.pair"]({})["ok"] is False
    seen = {}
    monkeypatch.setattr(rpcops.bt, "pair",
                        lambda mac, **k: (seen.setdefault("mac", mac),
                                          {"ok": True, "paired": True})[1])
    d = rpcops.DISPATCH._data["bt.pair"]({"mac": "AA:BB:CC:DD:EE:FF"})
    assert d["ok"] and seen["mac"] == "AA:BB:CC:DD:EE:FF"
