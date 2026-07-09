# SPDX-License-Identifier: GPL-3.0-only
"""ChargeDropDetector — the losing-power alarm state machine."""

from asteroid_docking_bay.ops import ChargeDropDetector


def run(seq):
    d = ChargeDropDetector(seq[0])
    events = [v for p in seq[1:] if (v := d.feed(p))]
    return d, events


def test_normal_charge_never_alarms():
    d, events = run([50, 52, 54, 56])
    assert not d.alarmed and events == []


def test_consecutive_drops_alarm_once():
    d, events = run([50, 49, 48, 47])
    assert d.alarmed and events == ["alarm"]   # raised once, not re-raised


def test_single_dip_recovers_silently():
    d, events = run([50, 49, 50])
    assert not d.alarmed and events == []      # below threshold: no alarm


def test_plateau_is_not_a_drop():
    d, events = run([79, 79, 79])
    assert not d.alarmed and events == []


def test_recovery_after_alarm():
    d, events = run([50, 49, 48, 49, 50])
    assert not d.alarmed and events == ["alarm", "recovered"]


def test_plateau_holds_an_active_alarm():
    # Equal readings neither clear nor re-raise; only a gain clears.
    d, events = run([50, 49, 48, 48, 48])
    assert d.alarmed and events == ["alarm"]


def test_second_episode_alarms_again():
    d, events = run([50, 49, 48, 49, 48, 47])
    assert events == ["alarm", "recovered", "alarm"]
