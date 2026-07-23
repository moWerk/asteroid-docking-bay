# SPDX-License-Identifier: GPL-3.0-only
"""Hands calibration — the stored drift offset for a physical-hands watch.

Narwhal's hands drift in timepiece mode (a microcontroller steps them with no OS
and no position feedback) and the sop716 sysfs cannot sense it. The correction is
a user-dialled signed-minute offset, persisted per serial and pre-applied on every
sync so the hands land on real time."""

import asteroid_docking_bay.rpcops as rpcops
from asteroid_docking_bay.config import hands_offset_for, set_hands_offset


def test_offset_default_zero_and_round_trip():
    cfg = {}
    assert hands_offset_for(cfg, "S1") == 0            # never calibrated → 0
    set_hands_offset(cfg, "S1", -3)
    assert hands_offset_for(cfg, "S1") == -3
    assert cfg["hands_offset"]["S1"] == -3


def test_offset_none_serial_is_zero():
    assert hands_offset_for({"hands_offset": {"S1": 5}}, None) == 0


def test_set_hands_offset_op_persists(monkeypatch):
    saved = {}
    monkeypatch.setattr(rpcops, "load_config", lambda: {})
    monkeypatch.setattr(rpcops, "save_config", lambda cfg: saved.update(cfg))
    d = rpcops.DISPATCH._data["watch.set_hands_offset"](
        {"serial": "S1", "offset_min": 7})
    assert d["ok"] is True and d["offset_min"] == 7
    assert saved["hands_offset"]["S1"] == 7


def test_set_hands_offset_op_coerces_to_int(monkeypatch):
    # The route hands through a string from the URL; the op must store an int, and
    # a negative drift (hands behind) must round-trip.
    saved = {}
    monkeypatch.setattr(rpcops, "load_config", lambda: {})
    monkeypatch.setattr(rpcops, "save_config", lambda cfg: saved.update(cfg))
    d = rpcops.DISPATCH._data["watch.set_hands_offset"](
        {"serial": "S1", "offset_min": "-12"})
    assert d["offset_min"] == -12 and saved["hands_offset"]["S1"] == -12


def test_hands_op_returns_stored_offset(monkeypatch):
    monkeypatch.setattr(rpcops, "load_config", lambda: {"hands_offset": {"S1": 4}})
    monkeypatch.setattr(rpcops, "_watch",
                        lambda s: type("W", (), {"hands": lambda self: {
                            "position": "132:41", "h": 132, "m": 41}})())
    d = rpcops.DISPATCH._data["watch.hands"]({"serial": "S1"})
    assert d["offset_min"] == 4 and d["hands"]["position"] == "132:41"
