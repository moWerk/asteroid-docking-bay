# SPDX-License-Identifier: GPL-3.0-only
"""The Fleet Registry — durable per-serial history keyed on tracked-field change.

What must hold: a change in a TRACKED field (kernel/qt/...) appends one Log entry
with [old, new]; volatile fields never clog the Log; None never erases; records
survive a reload; and get()/all() hand out copies, not the live store."""

import json

from asteroid_docking_bay.registry import Registry, MAX_LOG


def _reg(tmp_path):
    return Registry(tmp_path / "reg.json", min_write_interval=0)


def test_first_note_creates_record_with_first_seen(tmp_path):
    r = _reg(tmp_path)
    r.note("S1", source="adb", codename="skipjack", kernel="3.18.24")
    rec = r.get("S1")
    assert rec["serial"] == "S1" and rec["fields"]["codename"] == "skipjack"
    assert rec["first_seen"] > 0 and rec["last_source"] == "adb"
    assert rec["log"] == []                       # first sighting is not a change


def test_tracked_change_appends_one_log_entry(tmp_path):
    r = _reg(tmp_path)
    r.note("S1", source="adb", qt="5.15.16")
    r.note("S1", source="ssh", qt="6.11.2")       # Qt migration → a Log event
    rec = r.get("S1")
    assert rec["fields"]["qt"] == "6.11.2"
    assert len(rec["log"]) == 1
    assert rec["log"][0]["changes"]["qt"] == ["5.15.16", "6.11.2"]
    assert rec["log"][0]["source"] == "ssh"


def test_volatile_field_never_logs(tmp_path):
    r = _reg(tmp_path)
    r.note("S1", battery=80, ip="10.0.0.1")
    r.note("S1", battery=40, ip="10.0.0.2")       # battery/ip churn every read
    rec = r.get("S1")
    assert rec["fields"]["battery"] == 40 and rec["fields"]["ip"] == "10.0.0.2"
    assert rec["log"] == []                        # ... but they are not tracked


def test_unchanged_tracked_field_does_not_log(tmp_path):
    r = _reg(tmp_path)
    r.note("S1", kernel="3.18.24")
    r.note("S1", kernel="3.18.24")                 # same value re-read
    assert r.get("S1")["log"] == []


def test_none_never_erases_a_good_value(tmp_path):
    r = _reg(tmp_path)
    r.note("S1", kernel="3.18.24")
    r.note("S1", kernel=None, battery=50)          # a failed sub-read
    rec = r.get("S1")
    assert rec["fields"]["kernel"] == "3.18.24"    # preserved
    assert rec["log"] == []


def test_first_seen_sticks_last_seen_advances(tmp_path):
    r = _reg(tmp_path)
    r.note("S1", kernel="a")
    first = r.get("S1")["first_seen"]
    r.note("S1", kernel="b")
    rec = r.get("S1")
    assert rec["first_seen"] == first              # never moves
    assert rec["last_seen"] >= first


def test_log_is_capped(tmp_path):
    r = _reg(tmp_path)
    for i in range(MAX_LOG + 25):
        r.note("S1", kernel=f"k{i}")               # each is a change → a Log entry
    rec = r.get("S1")
    assert len(rec["log"]) == MAX_LOG
    assert rec["log"][-1]["changes"]["kernel"][1] == f"k{MAX_LOG + 24}"  # newest kept


def test_persists_and_reloads(tmp_path):
    r = _reg(tmp_path)
    r.note("S1", source="orbit", codename="catfish", kernel="3.18.120")
    r.note("S1", kernel="3.18.121")
    r2 = Registry(tmp_path / "reg.json")           # fresh instance, same file
    rec = r2.get("S1")
    assert rec["fields"]["kernel"] == "3.18.121"
    assert len(rec["log"]) == 1 and rec["last_source"] == "orbit"
    # sanity: the on-disk file is the record dict
    assert "S1" in json.load((tmp_path / "reg.json").open())


def test_all_sorts_newest_first_and_copies(tmp_path):
    r = _reg(tmp_path)
    r.note("OLD", kernel="a")
    r.note("NEW", kernel="b")
    recs = r.all()
    assert [x["serial"] for x in recs] == ["NEW", "OLD"]   # last_seen desc
    recs[0]["fields"]["kernel"] = "mutated"                # a copy, not the store
    assert r.get("NEW")["fields"]["kernel"] == "b"


def test_none_serial_is_ignored(tmp_path):
    r = _reg(tmp_path)
    r.note(None, kernel="a")
    assert r.all() == [] and r.get(None) is None
