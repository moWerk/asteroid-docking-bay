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


# ── exact codenames + unambiguous addressing ────────────────────────────────

def _multi_watch_cfg():
    """A rig fragment mirroring the real ambiguity: three ports share the
    'skipjack' image, two of them are physically tunnys; two share 'rubyfish',
    one is a rover. Serials are bound per port; exact codenames known for the
    live ones."""
    return {
        "hubs": [{"location": "1-2", "ports": {"1": "skipjack", "2": "rubyfish"},
                  "port_serials": {"1": "SKIP1", "2": "RUBY1"}},
                 {"location": "1-2.3", "ports": {"1": "skipjack", "2": "skipjack"},
                  "port_serials": {"1": "TUNNYA", "2": "TUNNYB"}},
                 {"location": "1-2.4", "ports": {"1": "rubyfish"},
                  "port_serials": {"1": "ROVER1"}}],
        "exact_codenames": {"TUNNYA": "tunny", "TUNNYB": "tunny",
                            "ROVER1": "rover", "RUBY1": "rubyfish"},
    }


def test_exact_codename_addresses_one_specific_watch():
    from asteroid_docking_bay.config import resolve_single_port
    cfg = _multi_watch_cfg()
    # 'rover' and 'rubyfish' share the rubyfish image; the exact codename picks
    # exactly one, where the image name could not.
    rover = resolve_single_port(cfg, "rover")
    ruby = resolve_single_port(cfg, "rubyfish")
    assert (rover["loc"], rover["port"]) == ("1-2.4", 1), rover
    assert (ruby["loc"], ruby["port"]) == ("1-2", 2), ruby
    assert rover["serial"] == "ROVER1" and ruby["serial"] == "RUBY1"


def test_serial_is_always_an_unambiguous_address():
    from asteroid_docking_bay.config import resolve_single_port
    d = resolve_single_port(_multi_watch_cfg(), "TUNNYB")
    assert (d["loc"], d["port"]) == ("1-2.3", 2), d


def test_shared_machine_name_raises_with_the_names_to_pick():
    from asteroid_docking_bay.config import resolve_single_port, AmbiguousTargetError
    import pytest
    cfg = _multi_watch_cfg()
    with pytest.raises(AmbiguousTargetError) as ei:
        resolve_single_port(cfg, "skipjack")   # three ports
    msg = str(ei.value)
    # The error must hand the user the serial (the only guaranteed unique
    # disambiguator), plus the exact codename where it differs from the query.
    assert "SKIP1" in msg and "TUNNYA" in msg and "tunny" in msg
    assert ei.value.candidates and len(ei.value.candidates) == 3


def test_unique_machine_name_still_resolves_directly():
    """Most machine names are unique (catfish, sturgeon); those must keep
    working as a plain single-target address with no ceremony."""
    from asteroid_docking_bay.config import resolve_single_port
    cfg = {"hubs": [{"location": "1-1", "ports": {"3": "catfish"},
                     "port_serials": {"3": "CAT1"}}]}
    d = resolve_single_port(cfg, "catfish")
    assert (d["loc"], d["port"]) == ("1-1", 3)


def test_all_resolves_every_port():
    from asteroid_docking_bay.config import find_ports_for_target
    assert len(find_ports_for_target(_multi_watch_cfg(), "all")) == 5


def test_record_exact_codename_is_change_gated():
    from asteroid_docking_bay.config import record_exact_codename, exact_codename_for_serial
    cfg = {}
    assert record_exact_codename(cfg, "S1", "rover") is True
    assert exact_codename_for_serial(cfg, "S1") == "rover"
    assert record_exact_codename(cfg, "S1", "rover") is False   # unchanged
    assert record_exact_codename(cfg, "S1", "rubyfish") is True  # changed
    assert record_exact_codename(cfg, None, "x") is False
    assert record_exact_codename(cfg, "S2", None) is False
