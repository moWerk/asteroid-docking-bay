# SPDX-License-Identifier: GPL-3.0-only
"""ConfigManager file handling and the typed settings dataclasses."""

from asteroid_docking_bay.config import (ChargeConfig, ConfigManager,
                                         FlashConfig, charge_config,
                                         flash_config)


def test_charge_defaults():
    c = ChargeConfig()
    assert (c.low_threshold, c.high_threshold) == (40, 80)
    assert c.adaptive_cadence is True
    assert c.graceful_poweroff is True
    assert c.charge_max_minutes == 240


def test_charge_from_dict_overrides_and_ignores_unknown():
    c = ChargeConfig.from_dict({"low_threshold": 30, "graceful_poweroff": False,
                                "some_future_key": 1})
    assert c.low_threshold == 30
    assert c.graceful_poweroff is False
    assert c.high_threshold == 80          # untouched default
    assert not hasattr(c, "some_future_key")


def test_charge_from_dict_none():
    assert ChargeConfig.from_dict(None) == ChargeConfig()


def test_typed_slices_from_raw_config():
    raw = {"charge": {"high_threshold": 90}, "flash": {"nightly_url": "http://x"}}
    assert charge_config(raw).high_threshold == 90
    assert flash_config(raw).nightly_url == "http://x"
    assert isinstance(flash_config({}), FlashConfig)


def test_manager_missing_file_gives_skeleton(tmp_path):
    cm = ConfigManager(tmp_path / "config.json")
    cfg = cm.load()
    assert cfg == {"hubs": [], "serials": {}, "charge": {}, "flash": {}}


def test_manager_roundtrip_and_defaults_merge(tmp_path):
    cm = ConfigManager(tmp_path / "config.json")
    cm.save({"hubs": [{"location": "1-2"}], "charge": {"low_threshold": 35}})
    cfg = cm.load()
    assert cfg["hubs"][0]["location"] == "1-2"
    assert cfg["serials"] == {}            # missing keys seeded
    assert charge_config(cfg).low_threshold == 35
    assert charge_config(cfg).high_threshold == 80


# ── _store_smart_verdict: a proven verdict is sticky ──────────────────────────

from asteroid_docking_bay.config import _store_smart_verdict


def test_smart_verdict_none_does_not_erase_proven_true():
    hub = {"port_smart": {"1": True}}
    _store_smart_verdict(hub, 1, None)          # a marginal re-test
    assert hub["port_smart"]["1"] is True        # kept, not flickered to '?'


def test_smart_verdict_conclusive_updates():
    hub = {"port_smart": {"1": True}}
    _store_smart_verdict(hub, 1, False)          # a port genuinely changed
    assert hub["port_smart"]["1"] is False


def test_smart_verdict_none_stored_when_nothing_proven():
    hub = {}
    _store_smart_verdict(hub, 2, None)
    assert hub["port_smart"]["2"] is None
