# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 Timo Könnecke (moWerk) <mo@mowerk.net>
"""Reading a wanze trace honestly.

The two failure modes worth testing are both silent. Timing computed from the
watch's wall clock looks perfectly reasonable while being months wrong
(catfish's RTC was 130 days behind while recording fine), and a gap read as
"missing data" rather than "the watch slept" throws away the one measurement
this probe uniquely provides.
"""

from asteroid_docking_bay.wanze import (analyse, clock_check, gaps, parse,
                                        segments)

HEADER = ("epoch,uptime,current_ua,capacity,status,voltage_uv,temp,charger,"
          "backlight,cpu_online,cpu_freq,load1,gauge,schema")


def row(epoch, uptime, cap=100, status="Discharging", cur=-5000, back=0):
    return (f"{epoch},{uptime},{cur},{cap},{status},4400000,319,0,{back},"
            f"4,1094400,0.5,nanohub_fuelgauge-0,1")


def csv(*rows):
    return "\n".join([HEADER, *rows]) + "\n"


# --- parsing --------------------------------------------------------------

def test_parses_a_real_row():
    rows = parse(csv(row(1774271275, 679.73)))
    assert len(rows) == 1
    r = rows[0]
    assert r["uptime"] == 679.73 and r["capacity"] == 100
    assert r["gauge"] == "nanohub_fuelgauge-0"


def test_columns_are_read_by_name_not_position():
    """A trace harvested across an upgrade can hold two schemas. Reading by
    position would shift every later field and produce plausible nonsense."""
    text = ("uptime,epoch,capacity,current_ua,status\n"
            "500.0,1774271275,88,-4000,Discharging\n")
    rows = parse(text)
    assert rows[0]["capacity"] == 88 and rows[0]["current_ua"] == -4000


def test_torn_row_is_skipped_not_fatal():
    """Power can be lost mid-append; one bad line must not lose the trace."""
    rows = parse(csv(row(1, 100.0), "1774271280,", row(3, 400.0)))
    assert len(rows) == 2


def test_a_file_that_is_not_wanze_yields_nothing():
    assert parse("epoch,current_ua,capacity,status\n1,2,3,Full\n") == []
    assert parse("") == []


# --- reboots --------------------------------------------------------------

def test_an_uptime_drop_splits_the_trace():
    """uptime only rises inside one boot, so a drop IS a reboot — free
    forensics, and a break that timing must never be computed across."""
    rows = parse(csv(row(1, 500.0), row(2, 800.0), row(3, 40.0), row(4, 300.0)))
    segs = segments(rows)
    assert len(segs) == 2
    assert analyse(rows)["reboots"] == 1


def test_a_reboot_is_not_counted_as_a_gap():
    """Across a reboot the uptime delta is negative-then-small; treating the
    boundary as elapsed time would invent sleep that never happened."""
    rows = parse(csv(row(1, 5000.0), row(2, 30.0)))
    assert gaps(rows) == []
    assert analyse(rows)["asleep_s"] == 0


# --- gaps are data --------------------------------------------------------

def test_a_long_hole_is_recorded_as_sleep():
    rows = parse(csv(row(1, 300.0, cap=100), row(2, 11100.0, cap=97)))
    holes = gaps(rows)
    assert len(holes) == 1
    assert holes[0]["seconds"] == 10800
    assert holes[0]["capacity_from"] == 100 and holes[0]["capacity_to"] == 97


def test_normal_cadence_is_not_a_gap():
    """Samples at the nominal interval, and a late one, are the watch being
    awake — calling those sleep would inflate every standby figure."""
    rows = parse(csv(row(1, 300.0), row(2, 600.0), row(3, 1100.0)))
    assert gaps(rows) == []


def test_asleep_fraction_is_reported():
    rows = parse(csv(row(1, 0.0), row(2, 300.0), row(3, 4000.0)))
    a = analyse(rows)
    assert a["asleep_s"] == 3700
    assert a["covered_s"] == 4000
    assert a["asleep_fraction"] == round(3700 / 4000, 3)


# --- the clock is not to be trusted ---------------------------------------

def test_a_wrong_but_steady_clock_does_not_corrupt_timing():
    """catfish recorded fine with an RTC 130 days behind. A CONSTANT offset is
    the easy case — deltas survive it either way — so this only guards against
    the skew leaking into the figures, not against epoch-based timing. The two
    tests below are the ones that discriminate."""
    good = parse(csv(row(1785512000, 300.0), row(1785522800, 11100.0)))
    skewed = parse(csv(row(1774271000, 300.0), row(1774281800, 11100.0)))
    assert analyse(good)["asleep_s"] == analyse(skewed)["asleep_s"]
    assert analyse(good)["covered_s"] == analyse(skewed)["covered_s"]


def test_a_clock_jump_must_not_invent_sleep():
    """An NTP sync moves epoch by a day while the watch was awake throughout.
    Timing taken from the wall clock would report a day of standby that never
    happened — and it would look entirely plausible in a report."""
    rows = parse(csv(row(1000, 300.0), row(87400, 600.0), row(87700, 900.0)))
    assert gaps(rows) == [], "a clock jump was mistaken for sleep"
    assert analyse(rows)["asleep_s"] == 0


def test_a_frozen_clock_must_not_hide_real_sleep():
    """The inverse: a watch whose RTC does not advance across suspend. The
    wall clock says nothing happened; uptime knows three hours passed."""
    rows = parse(csv(row(1000, 300.0), row(1000, 11100.0)))
    holes = gaps(rows)
    assert len(holes) == 1 and holes[0]["seconds"] == 10800, \
        "real sleep was hidden by a stopped clock"


def test_a_clock_step_mid_trace_is_detected():
    """An NTP sync moves epoch without moving uptime. Invisible unless the two
    are compared, and it would corrupt anything epoch-based downstream."""
    stepped = parse(csv(row(1000, 300.0), row(90000, 600.0)))
    assert clock_check(stepped)["clock_stepped"] is True
    steady = parse(csv(row(1000, 300.0), row(1300, 600.0)))
    assert steady and clock_check(steady)["clock_stepped"] is False


def test_skew_against_the_host_is_reported_not_corrected():
    """A silently corrected timestamp is worse than an obviously wrong one."""
    rows = parse(csv(row(1774271323, 300.0)))
    a = analyse(rows, host_epoch=1785512378)
    assert a["clock_skew_days"] == -130.1
    assert a["last"]["epoch"] == 1774271323 if "last" in a else True
    assert rows[0]["epoch"] == 1774271323, "rows must not be rewritten"


# --- battery, via the module that already knows how -----------------------

def test_an_always_zero_sensor_is_named_not_read_as_no_drain():
    """nemo reports 0 forever. A tidy file of zeros reads as 'no drain' unless
    something says 'no instrument'."""
    rows = parse(csv(row(1, 300.0, cur=0), row(2, 600.0, cur=0)))
    assert analyse(rows)["battery"]["sensor"] == "always-zero"


def test_screen_on_samples_are_counted():
    rows = parse(csv(row(1, 300.0, back=0), row(2, 600.0, back=70)))
    assert analyse(rows)["samples_screen_on"] == 1


def test_empty_trace_reports_not_ok():
    assert analyse([])["ok"] is False


# --- source discovery -----------------------------------------------------

def test_a_partial_source_dir_is_not_accepted(tmp_path, monkeypatch):
    """A directory holding only some of the files would install a probe that
    cannot run, and nothing would reveal it until the trace came back empty
    days later — long after the watch left the dock."""
    from asteroid_docking_bay import wanze as w

    partial = tmp_path / "partial"
    partial.mkdir()
    (partial / "wanze-sample").write_text("#!/bin/sh\n")   # units missing
    complete = tmp_path / "complete"
    complete.mkdir()
    for f in w.SRC_FILES:
        (complete / f).write_text("x")

    monkeypatch.setattr(w, "SRC_CANDIDATES", (partial, complete))
    assert w.find_src() == complete


def test_no_source_anywhere_reports_where_it_looked(tmp_path, monkeypatch):
    """An install that fails must say what it wanted, not just that it failed."""
    from asteroid_docking_bay import wanze as w

    monkeypatch.setattr(w, "SRC_CANDIDATES", (tmp_path / "nope",))
    assert w.find_src() is None
    err = w.install(object())
    assert err and "not found" in err and "nope" in err


# --- the trailing gap -----------------------------------------------------

def test_harvest_closes_the_window_before_reading():
    """The trace ends at the last opportunistic sample, so sleep AFTER it is
    invisible. catfish's first undocked run lost ~41 minutes of standby that
    way — under-reporting the exact thing the probe exists to measure."""
    from asteroid_docking_bay import wanze as w

    calls = []

    class _T:
        def shell(self, cmd, timeout=0):
            calls.append(cmd)
            if cmd.startswith("cat "):
                return (0, csv(row(1, 300.0), row(2, 600.0)), "")
            return (0, "", "")

    class _W:
        serial = "S"
        t = _T()

    w.harvest(_W())
    assert any("wanze.service" in c for c in calls), \
        "harvest did not take a closing sample"
    assert calls.index(next(c for c in calls if "wanze.service" in c)) < \
        calls.index(next(c for c in calls if c.startswith("cat "))), \
        "the closing sample must be taken BEFORE the read, or it is not in it"


# ── removing the probe ───────────────────────────────────────────────────────

class _FakeT:
    """A watch transport that records what it was told to run."""
    def __init__(self, leftover=""):
        self.cmds, self._leftover = [], leftover
        self.pushed = []

    def shell(self, cmd, timeout=None):
        self.cmds.append(cmd)
        if "ls " in cmd:
            return 0, self._leftover, ""
        if "is-active" in cmd:
            return 0, "active", ""
        return 0, "", ""

    def push(self, src, dest, timeout=None):
        self.pushed.append((src, dest))
        return 0, "", ""


class _FakeWatch:
    def __init__(self, leftover=""):
        self.serial, self.t = "S1", _FakeT(leftover)


def test_uninstall_removes_everything_install_put_there():
    """The mirror of install(), file for file. A unit file left behind re-arms
    on the next boot and the watch quietly starts sampling again days later,
    which is the failure mode a half-removal produces."""
    from asteroid_docking_bay import wanze
    w = _FakeWatch()
    assert wanze.uninstall(w) is None
    joined = " ".join(w.t.cmds)

    assert f"disable --now {wanze.UNIT}" in joined, "the timer was not stopped first"
    for f in (wanze.REMOTE_BIN, "/etc/systemd/system/wanze.service",
              "/etc/systemd/system/wanze.timer"):
        assert f in joined, f"{f} left on the watch"
    assert "daemon-reload" in joined, "systemd still holds the removed units"


def test_uninstall_keeps_the_trace_unless_asked():
    """The trace is the ONLY copy of whatever the probe recorded until it has
    been harvested. Deleting a measurement as a side effect of tidying up the
    tool that produced it is a quiet, unrecoverable loss — it costs days of a
    run to collect and a moment to destroy."""
    from asteroid_docking_bay import wanze

    w = _FakeWatch()
    wanze.uninstall(w)
    assert wanze.REMOTE_LOG not in " ".join(w.t.cmds), \
        "removing the probe deleted the trace nobody asked to delete"

    w2 = _FakeWatch()
    wanze.uninstall(w2, clear_trace=True)
    assert wanze.REMOTE_LOG in " ".join(w2.t.cmds), \
        "an explicit clear_trace did not delete the trace"


def test_uninstall_reports_a_probe_that_is_still_there():
    """Confirm rather than assume — the same rule install() follows when it
    checks the timer actually armed. A removal that silently failed would leave
    the watch sampling with the UI insisting it is clean."""
    from asteroid_docking_bay import wanze
    w = _FakeWatch(leftover="/usr/bin/wanze-sample")
    err = wanze.uninstall(w)
    assert err and "still on the watch" in err


# --- schema 2: the columns added after the sol wrist run -------------------

HEADER2 = ("epoch,uptime,current_ua,capacity,status,voltage_uv,temp,charger,"
           "backlight,panel_power_state,cpu_online,cpu_freq,load1,"
           "suspend_success,suspend_fail,wakeup_source,reason,gauge,schema")


def row2(epoch, uptime, cap=100, back="", panel="", ok="", fail="",
         reason="", cur=-5000):
    return (f"{epoch},{uptime},{cur},{cap},Discharging,4400000,319,0,{back},"
            f"{panel},4,1094400,0.5,{ok},{fail},,{reason},"
            f"nanohub_fuelgauge-0,2")


def csv2(*rows):
    return "\n".join([HEADER2, *rows]) + "\n"


def test_an_unreadable_backlight_reports_unavailable_never_zero():
    """sol has no /sys/class/leds/lcd-backlight, so the column was empty for
    every row — and this reported `samples_screen_on: 0`, which reads as "the
    screen was never on" and meant "we could not see".

    A silent zero is worse than an obvious hole: it is a number somebody will
    put in a drain conclusion. The module already applies that reasoning to
    `epoch`, and it applies here.
    """
    out = analyse(parse(csv2(row2(1000, 100), row2(1300, 400), row2(1600, 700))))
    assert out["samples_screen_on"] is None, (
        "an unreadable backlight was reported as a count, which cannot be "
        "told apart from a screen that was genuinely never lit")
    assert out["screen_data"] == "unavailable"


def test_a_readable_backlight_that_is_always_off_still_reports_zero():
    """The counterpart, and the reason `unavailable` cannot simply mean "no
    lit samples": a column that IS readable and is all zeros is an answer —
    the screen really was never on. Reporting that as unavailable would throw
    away a genuine measurement."""
    out = analyse(parse(csv2(row2(1000, 100, back="0"),
                             row2(1300, 400, back="0"))))
    assert out["samples_screen_on"] == 0
    assert out["screen_data"] == "ok"

    lit = analyse(parse(csv2(row2(1000, 100, back="0"),
                             row2(1300, 400, back="120"))))
    assert lit["samples_screen_on"] == 1


def test_the_three_suspend_cases_are_distinguishable():
    """Gap analysis can only say "the probe did not fire, so the watch was
    PROBABLY asleep". The kernel's own counters separate three states that a
    trace otherwise renders identically — and the third is the one a wrist run
    needed and could not get, because the live counters die with the battery.
    """
    slept = analyse(parse(csv2(row2(1000, 100, ok="10", fail="0"),
                               row2(1300, 400, ok="14", fail="0"))))
    assert slept["suspend_attempted"] is True
    assert slept["suspend_entered_delta"] == 4, "a watch that slept looks idle"

    aborted = analyse(parse(csv2(row2(1000, 100, ok="10", fail="2"),
                                 row2(1300, 400, ok="10", fail="9"))))
    assert aborted["suspend_attempted"] is True
    assert aborted["suspend_entered_delta"] == 0, (
        "it entered suspend zero times and that must read as zero")
    assert aborted["suspend_fail_delta"] == 7, (
        "the aborts are the whole diagnosis: it TRIED and something stopped it")

    never = analyse(parse(csv2(row2(1000, 100, ok="0", fail="0"),
                               row2(1300, 400, ok="0", fail="0"))))
    assert never["suspend_attempted"] is False, (
        "suspend was never even attempted — the case that looks identical to "
        "'tried and failed' unless the counters are recorded")
    assert never["suspend_entered_delta"] == 0


def test_suspend_counters_are_not_differenced_across_a_reboot():
    """The counters are cumulative SINCE BOOT, so a delta taken across a
    reboot is meaningless in exactly the way an uptime delta is — and it would
    read as a huge negative, or silently swallow a boot's worth of sleep.

    Two boots that each slept twice is four, not the difference between the
    last number and the first.
    """
    rows = parse(csv2(
        row2(1000, 500, ok="10", fail="0"),
        row2(1300, 800, ok="12", fail="0"),
        row2(1600, 20, ok="0", fail="0"),      # uptime drops: rebooted
        row2(1900, 320, ok="2", fail="0"),
    ))
    out = analyse(rows)
    assert out["boots"] == 2
    assert out["suspend_entered_delta"] == 4, (
        f"expected 2+2 across two boots, got {out['suspend_entered_delta']}")


def test_a_schema_1_trace_says_the_counters_are_unavailable():
    """An old trace has no such columns at all. That must read as "we do not
    know", not as "suspend was never attempted" — which is a real diagnosis
    and would be a fabricated one here."""
    out = analyse(parse(csv(row(1000, 100), row(1300, 400))))
    assert out["suspend_attempted"] is None
    assert out["suspend_data"] == "unavailable"


def test_a_trace_spanning_the_upgrade_reads_as_one_trace():
    """A harvest can span the schema bump, so both shapes appear in one file.
    parse() is header-driven precisely so the older rows lose a column rather
    than shifting every later field — the failure that would silently move
    `capacity` into `status` and be believed."""
    text = csv(row(1000, 100, cap=90)) + csv2(row2(1300, 400, cap=80, ok="3"))
    rows = parse(text)
    # The second header line is not a row; it parses to nothing and is skipped.
    caps = [r["capacity"] for r in rows if r["capacity"] is not None]
    assert 90 in caps and 80 in caps, f"lost a row across the upgrade: {caps}"
    old = [r for r in rows if r["capacity"] == 90][0]
    new = [r for r in rows if r["capacity"] == 80][0]
    assert old["suspend_success"] is None, "an old row invented a new column"
    assert new["suspend_success"] == 3
    assert old["status"] == "Discharging" and new["status"] == "Discharging", (
        "a column shifted: the old row's fields moved when the header grew")


def test_the_low_battery_marker_says_why_a_trace_ended():
    """A trace that ends because the battery died and one that ends because
    the watch slept and never woke are both just a trailing gap. The sampler
    writes one marker row on the way down; reading it back is what turns
    "no more rows" into "it died"."""
    out = analyse(parse(csv2(row2(1000, 100, cap=40),
                             row2(1300, 400, cap=14, reason="lowbat"))))
    assert out["ended_reason"] == "lowbat"

    quiet = analyse(parse(csv2(row2(1000, 100, cap=40), row2(1300, 400, cap=35))))
    assert quiet["ended_reason"] is None, (
        "invented a reason for a trace that simply stopped")


def test_panel_state_separates_always_on_from_a_lit_screen():
    """Brightness alone cannot tell a cheap always-on watchface from an
    expensive lit screen — both report non-zero — and that is exactly the
    distinction a drain trace turns on."""
    out = analyse(parse(csv2(
        row2(1000, 100, back="10", panel="LP@30Hz"),
        row2(1300, 400, back="10", panel="LP@30Hz"),
        row2(1600, 700, back="200", panel="ON@60Hz"))))
    assert out["samples_screen_on"] == 3          # all three are "lit" by brightness
    assert out["panel_states"] == {"LP@30Hz": 2, "ON@60Hz": 1}, (
        "brightness said three lit samples; only the panel state distinguishes "
        "two cheap always-on frames from one genuinely lit screen")


# --- the display, which is the pairing that diagnosed sol ------------------

def test_a_display_that_never_slept_reads_as_one_line():
    """The pairing is the diagnosis, and neither number says much alone.

    Because the timer never wakes the watch, a watch whose display never turns
    off is also never asleep: it stays awake, so it produces regular samples
    and NO gaps. `asleep_fraction ~ 0` on its own looks like a merely busy
    watch. Beside `display_on_fraction ~ 1` it says the screen never went off,
    and there is the runtime -- which is exactly sol's 9 hours.
    """
    out = analyse(parse(csv2(
        row2(1000, 100, panel="ON@60Hz"),
        row2(1300, 400, panel="ON@60Hz"),
        row2(1600, 700, panel="ON@60Hz"))))
    assert out["display_on_fraction"] == 1.0
    assert out["asleep_fraction"] == 0.0, (
        "a watch that never slept must not read as having slept")
    assert out["display_data"] == "ok"


def test_a_panel_parked_in_lp_still_counts_as_on():
    """LP is a SELF-REFRESHING mode: the panel is powered and clocking even
    when nothing is rendered into it. sol parks there showing black and pays
    AoD's cost anyway, and brightness cannot see it because LP and ON both
    report non-zero. Only OFF is off."""
    lp = analyse(parse(csv2(row2(1000, 100, back="10", panel="LP@30Hz"),
                            row2(1300, 400, back="10", panel="LP@30Hz"))))
    assert lp["display_on_fraction"] == 1.0, (
        "LP was treated as off -- the exact mistake that hides sol's drain")

    off = analyse(parse(csv2(row2(1000, 100, back="0", panel="OFF"),
                             row2(1300, 400, back="0", panel="OFF"))))
    assert off["display_on_fraction"] == 0.0


def test_a_gap_is_attributed_to_no_display_state():
    """A gap means the watch was not awake, so no sample can speak for it.
    Extrapolating the last known state across one would invent the very thing
    the trace exists to measure -- here it would claim the display was OFF for
    four hours it cannot account for."""
    rows = parse(csv2(
        row2(1000, 100, panel="OFF"),
        row2(1300, 400, panel="OFF"),        # 300s, attributable
        row2(9000, 15000, panel="OFF"),      # ~4h gap, attributable to nobody
        row2(9300, 15300, panel="OFF")))     # 300s, attributable
    out = analyse(rows)
    assert out["display_attributed_s"] == 600, (
        f"the gap was folded into the display accounting: "
        f"{out['display_attributed_s']}s")
    assert out["asleep_s"] > 14000, "the gap stopped being counted as sleep"
    assert out["display_on_fraction"] == 0.0


def test_an_absent_panel_column_is_unavailable_not_off():
    """A watch that does not expose the DRM connector says nothing about its
    panel. Reporting that as `display_on_fraction: 0` would read as "the
    display was off the whole time" -- a conclusion, and a flattering one,
    from no data at all. Same reasoning as the backlight and the counters."""
    out = analyse(parse(csv2(row2(1000, 100), row2(1300, 400))))
    assert out["display_data"] == "unavailable"
    assert out["display_on_fraction"] is None
    assert out["panel_state_counts"] is None


def test_install_enables_both_units(tmp_path):
    """wanze has TWO enabled units since 2026-10-31 and install must arm both.

    The timer carries the 5-minute cadence; the service is enabled in its own
    right for the boot row, which on a watch that sleeps through every calendar
    slot of a short session is the only sample guaranteed to exist. Enabling
    only the timer silently loses it.
    """
    from asteroid_docking_bay import wanze
    for f in wanze.SRC_FILES:
        (tmp_path / f).write_text("x")
    w = _FakeWatch()

    assert wanze.install(w, src_dir=tmp_path) is None
    joined = " ".join(w.t.cmds)
    assert f"enable {wanze.SERVICE}" in joined, \
        f"the boot sample was never enabled: {w.t.cmds}"
    assert f"enable --now {wanze.UNIT}" in joined, \
        f"the timer was not armed: {w.t.cmds}"


def test_stop_disables_both_units():
    """Disabling the timer alone leaves wanze.service enabled in
    multi-user.target, so the watch keeps writing a row on every boot after
    the operator believed they had stopped it — a probe that outlives its own
    stop is the failure this project keeps finding."""
    from asteroid_docking_bay import wanze
    w = _FakeWatch()
    wanze.stop(w)
    joined = " ".join(w.t.cmds)
    assert wanze.UNIT in joined and wanze.SERVICE in joined, \
        f"stop left one unit enabled: {w.t.cmds}"


# The Pro1-X window of 2026-10-31, verbatim: systemd 238 fired the sampler
# twice on the wake after each long sleep, 0.3 s apart. Columns are
# epoch,uptime,current_ua,capacity,status,voltage_uv then the rest.
_PRO1X_BURSTY = """epoch,uptime,current_ua,capacity,status,voltage_uv,temp,charger,backlight,panel_power_state,cpu_online,cpu_freq,load1,suspend_success,suspend_fail,wakeup_source,reason,gauge,schema
1793472391,752.48,-73394,91,Discharging,4198116,,,,OFF,,,,,,,,bms,2
1793473110,1471.37,-92824,91,Discharging,4174437,,,,ON,,,,,,,,bms,2
1793473110,1471.68,-92824,91,Discharging,4174437,,,,ON,,,,,,,,bms,2
1793473830,2191.43,-72479,88,Discharging,4167234,,,,OFF,,,,,,,,bms,2
1793473830,2191.78,-72479,88,Discharging,4167234,,,,OFF,,,,,,,,bms,2
1793474340,2701.43,-79549,87,Discharging,4160552,,,,OFF,,,,,,,,bms,2
1793474461,2822.52,-141783,86,Discharging,4156707,,,,OFF,,,,,,,,bms,2
"""


def test_a_doubled_wake_row_is_not_two_samples():
    """systemd 238's second activation on a wake is an artefact, not an
    observation, and every COUNT the host reports is inflated by it.

    Real data: 7 rows written, of which 2 are duplicates 0.31 s and 0.35 s
    behind their twins. The analysis must say 5 samples and say that 2 went,
    because dropping rows without saying so is how a trace stops being
    evidence.
    """
    from asteroid_docking_bay import wanze
    rows = wanze.parse(_PRO1X_BURSTY)
    assert len(rows) == 7, "parse must stay faithful to the file"

    out = wanze.analyse(rows)
    assert out["samples"] == 5, out["samples"]
    assert out["duplicate_rows_dropped"] == 2, out
    # One boot, not several: a 0.3 s pair must never look like a reboot.
    assert out["boots"] == 1, out


def test_dedupe_keeps_the_row_that_spans_the_gap():
    """The FIRST of a pair is kept. Its interval to the previous sample is the
    one that crosses the sleep, and the sleep is the measurement."""
    from asteroid_docking_bay import wanze
    rows = wanze.parse(_PRO1X_BURSTY)
    kept = wanze.dedupe(rows)
    assert [round(r["uptime"], 2) for r in kept] == \
        [752.48, 1471.37, 2191.43, 2701.43, 2822.52], \
        [r["uptime"] for r in kept]


def _row(**over):
    """One CSV row built from the header, so a column cannot be miscounted.

    Writing these by hand cost a test: a row one field short is TORN, parse()
    skips it by design, and the test then failed for the wrong reason.
    """
    cols = _PRO1X_BURSTY.splitlines()[0].split(",")
    vals = {"epoch": "1793474461", "uptime": "2822.52", "current_ua": "-141783",
            "capacity": "86", "status": "Discharging", "voltage_uv": "4156707",
            "panel_power_state": "OFF", "gauge": "bms", "schema": "2"}
    vals.update({k: str(v) for k, v in over.items()})
    return ",".join(vals.get(c, "") for c in cols)


def test_dedupe_never_drops_a_reboot_or_a_marker():
    """A negative delta is a new boot; a different `reason` is a deliberate
    marker row that says something its neighbour does not. Neither is a
    duplicate however close it sits."""
    from asteroid_docking_bay import wanze
    hdr = _PRO1X_BURSTY.splitlines()[0]

    reboot = wanze.parse("\n".join([hdr,
        _row(uptime="2822.52"),
        _row(uptime="11.40", epoch="1793474470")]) + "\n")
    assert len(reboot) == 2, "fixture rows were not parsed"
    assert len(wanze.dedupe(reboot)) == 2, "a reboot was eaten as a duplicate"

    marker = wanze.parse("\n".join([hdr,
        _row(uptime="2822.52", capacity="14"),
        _row(uptime="2822.80", capacity="14", reason="lowbat")]) + "\n")
    assert len(marker) == 2, "fixture rows were not parsed"
    assert [r["reason"] for r in marker] == [None, "lowbat"], \
        [r["reason"] for r in marker]
    assert len(wanze.dedupe(marker)) == 2, "a lowbat marker was eaten"


def test_dedupe_cannot_swallow_a_real_sample():
    """The window sits far below the cadence. A genuine next sample, even an
    early one, must survive -- the probe's value is the five-minute picture and
    eating one of those would be worse than the duplicate."""
    from asteroid_docking_bay import wanze
    hdr = _PRO1X_BURSTY.splitlines()[0]
    rows = wanze.parse(
        f"{hdr}\n"
        "1793474000,1000.00,-90000,90,Discharging,4160000,,,,OFF,,,,,,,,bms,2\n"
        f"1793474031,{1000.0 + wanze.DUP_WINDOW_S + 1:.2f},-90000,90,Discharging,4160000,,,,OFF,,,,,,,,bms,2\n")
    assert len(wanze.dedupe(rows)) == 2, "dropped a sample outside the window"
