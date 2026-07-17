# SPDX-License-Identifier: GPL-3.0-only
"""Last-seen store: value fallback + restart-surviving persistence."""

import json

from asteroid_docking_bay.lastseen import LastSeen


def test_record_then_get_roundtrips_fields_and_stamps_time(tmp_path):
    ls = LastSeen(tmp_path / "ls.json")
    ls.record("S1", battery=57, os="asteroid 1.0")
    got = ls.get("S1")
    assert got["battery"] == 57 and got["os"] == "asteroid 1.0"
    assert isinstance(got["last_live_ts"], (int, float)) and got["last_live_ts"] > 0


def test_get_unknown_or_none_serial_is_none(tmp_path):
    ls = LastSeen(tmp_path / "ls.json")
    assert ls.get("nope") is None
    assert ls.get(None) is None
    ls.record(None, battery=10)          # no serial → no-op
    assert ls._data == {}


def test_none_valued_field_does_not_erase_a_good_prior(tmp_path):
    ls = LastSeen(tmp_path / "ls.json")
    ls.record("S1", battery=80)
    ls.record("S1", battery=None, screen_forced=True)
    got = ls.get("S1")
    assert got["battery"] == 80          # prior kept, not clobbered by None
    assert got["screen_forced"] is True


def test_persists_across_a_restart(tmp_path):
    path = tmp_path / "ls.json"
    LastSeen(path).record("S1", battery=42)
    # A fresh instance = a service restart reading the same file.
    assert LastSeen(path).get("S1")["battery"] == 42


def test_material_change_flushes_immediately(tmp_path):
    path = tmp_path / "ls.json"
    ls = LastSeen(path, min_write_interval=9999)   # throttle repeats hard
    ls.record("S1", battery=42)
    assert json.loads(path.read_text())["S1"]["battery"] == 42
    ls.record("S1", battery=41)                    # a real change → on disk now
    assert json.loads(path.read_text())["S1"]["battery"] == 41


def test_identical_reread_is_throttled_but_memory_stays_live(tmp_path):
    path = tmp_path / "ls.json"
    ls = LastSeen(path, min_write_interval=9999)
    ls.record("S1", battery=42)
    disk_ts = json.loads(path.read_text())["S1"]["last_live_ts"]
    ls.record("S1", battery=42)                    # same value, throttled
    mem_ts = ls.get("S1")["last_live_ts"]
    assert mem_ts >= disk_ts                        # memory advanced
    assert json.loads(path.read_text())["S1"]["last_live_ts"] == disk_ts  # disk held
