# SPDX-License-Identifier: GPL-3.0-only
"""Hands motor control + calibration for a physical-hands watch (narwhal).

motor_move_all takes "minute:hour", each 0..179 (180/turn, 2 deg/step), absolute
and re-syncing. The motor-zero offset (physical degrees at motor value 0) is the
one calibration; the drag angle → motor value mapping lives in the frontend, so
here we pin the op's range guard, the cal round-trip, and its bench defaults."""

import asteroid_docking_bay.rpcops as rpcops
from asteroid_docking_bay.config import (hands_cal_for, set_hands_cal,
                                         HANDS_ZERO_MIN_DEG, HANDS_ZERO_HR_DEG)


class _MoveWatch:
    def __init__(self):
        self.moved = None

    def move_hands(self, m, h):
        self.moved = (m, h)
        return True


# ── calibration config ───────────────────────────────────────────────────────

def test_cal_defaults_to_the_bench_offsets():
    cal = hands_cal_for({}, "S1")
    assert cal["min_deg"] == HANDS_ZERO_MIN_DEG and cal["hr_deg"] == HANDS_ZERO_HR_DEG


def test_cal_round_trip_and_none_serial():
    cfg = {}
    set_hands_cal(cfg, "S1", 100.0, 110.5)
    assert hands_cal_for(cfg, "S1") == {"min_deg": 100.0, "hr_deg": 110.5}
    # An uncalibrated serial and a None serial both fall back to defaults.
    assert hands_cal_for(cfg, "S2")["min_deg"] == HANDS_ZERO_MIN_DEG
    assert hands_cal_for(cfg, None)["hr_deg"] == HANDS_ZERO_HR_DEG


# ── hands_move op (the range guard is the safety net) ────────────────────────

def test_hands_move_op_drives_the_motors(monkeypatch):
    w = _MoveWatch()
    monkeypatch.setattr(rpcops, "_watch", lambda s: w)
    d = rpcops.DISPATCH._data["watch.hands_move"]({"serial": "S1", "m": "45", "h": "135"})
    assert d["ok"] is True and w.moved == (45, 135)     # strings from the URL → ints


def test_hands_move_op_rejects_out_of_range(monkeypatch):
    w = _MoveWatch()
    monkeypatch.setattr(rpcops, "_watch", lambda s: w)
    for bad in ({"m": 180, "h": 0}, {"m": -1, "h": 0}, {"m": 0, "h": 200}):
        d = rpcops.DISPATCH._data["watch.hands_move"]({"serial": "S1", **bad})
        assert d["ok"] is False and "0..179" in d["error"]
    assert w.moved is None                               # nothing driven on a bad range


def test_hands_move_op_rejects_non_integer(monkeypatch):
    monkeypatch.setattr(rpcops, "_watch", lambda s: _MoveWatch())
    d = rpcops.DISPATCH._data["watch.hands_move"]({"serial": "S1", "m": "x", "h": "9"})
    assert d["ok"] is False and "integer" in d["error"]


# ── set_hands_cal op ─────────────────────────────────────────────────────────

def test_set_hands_cal_op_persists(monkeypatch):
    saved = {}
    monkeypatch.setattr(rpcops, "load_config", lambda: {})
    monkeypatch.setattr(rpcops, "save_config", lambda cfg: saved.update(cfg))
    d = rpcops.DISPATCH._data["watch.set_hands_cal"](
        {"serial": "S1", "min_deg": "101.5", "hr_deg": "109"})
    assert d["ok"] is True and d["cal"]["min_deg"] == 101.5
    assert saved["hands_cal"]["S1"] == {"min_deg": 101.5, "hr_deg": 109.0}


def test_hands_op_returns_calibration(monkeypatch):
    monkeypatch.setattr(rpcops, "load_config",
                        lambda: {"hands_cal": {"S1": {"min_deg": 100.0, "hr_deg": 108.0}}})
    monkeypatch.setattr(rpcops, "_watch",
                        lambda s: type("W", (), {"hands": lambda self: {
                            "position": "45:135"}})())
    d = rpcops.DISPATCH._data["watch.hands"]({"serial": "S1"})
    assert d["cal"] == {"min_deg": 100.0, "hr_deg": 108.0}
    assert d["hands"]["position"] == "45:135"
