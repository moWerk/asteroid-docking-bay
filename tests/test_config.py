# SPDX-License-Identifier: GPL-3.0-only
"""ConfigManager file handling and the typed settings dataclasses."""

from asteroid_docking_bay.config import (ChargeConfig, ConfigManager,
                                         FlashConfig, charge_config,
                                         derive_hub_names, flash_config,
                                         hub_name_for, seed_hub_names,
                                         set_hub_name)


# The rig's real topology: two A16 boxes (0bda) — one direct (1-2), one hanging
# off the Lenovo dock (17ef 1-9) at 1-9.1 — plus the dock itself. The nested
# case is the hard one: 1-9.1.x must read as the second A16, never the dock.
_RIG_HUBS = [
    {"location": "1-2",        "vendor": "0bda"},
    {"location": "1-2.3",      "vendor": "0bda"},
    {"location": "1-2.3.3",    "vendor": "0bda"},
    {"location": "1-2.4",      "vendor": "0bda"},
    {"location": "1-9",        "vendor": "17ef"},
    {"location": "1-9.1",      "vendor": "0bda"},
    {"location": "1-9.1.3",    "vendor": "0bda"},
    {"location": "1-9.1.3.3",  "vendor": "0bda"},
    {"location": "1-9.1.4",    "vendor": "0bda"},
]


def test_derive_hub_names_separates_nested_a16_from_dock():
    names = derive_hub_names(_RIG_HUBS)
    # Only the physical tops get named — not every cascade chip.
    assert names == {"1-2": "A16 #1", "1-9": "Lenovo dock", "1-9.1": "A16 #2"}
    cfg = {"hub_names": names}
    # Every chip/port inherits its box by longest-prefix.
    assert hub_name_for(cfg, "1-2.3.3") == "A16 #1"
    assert hub_name_for(cfg, "1-9.1.3.3") == "A16 #2"   # longer prefix beats "1-9"
    assert hub_name_for(cfg, "1-9") == "Lenovo dock"
    assert hub_name_for(cfg, "1-9.1.4") == "A16 #2"


def test_loc_covers_respects_component_boundaries():
    # A sibling that merely shares a text prefix must NOT inherit the name.
    cfg = {"hub_names": {"1-9.1": "A16 #2"}}
    assert hub_name_for(cfg, "1-9.1.3") == "A16 #2"
    assert hub_name_for(cfg, "1-9.10") is None          # not a child of 1-9.1
    assert hub_name_for(cfg, "1-2") is None


def test_seed_hub_names_scopes_to_boxes_with_configured_hubs():
    cfg = {"hubs": [{"location": "1-2.3.3"}, {"location": "1-9.1.3.3"}],
           "hub_names": {}}
    stray = _RIG_HUBS + [{"location": "2-1", "vendor": "1234"}]  # unrelated bus
    assert seed_hub_names(cfg, stray) is True
    # The stray box (no configured hub beneath it) is not named; the boxes in the
    # fleet's path are — including the dock the second A16 hangs off.
    assert cfg["hub_names"] == {"1-2": "A16 #1", "1-9": "Lenovo dock",
                                "1-9.1": "A16 #2"}
    # Idempotent: an already-seeded config is left untouched.
    assert seed_hub_names(cfg, _RIG_HUBS) is False


def test_set_hub_name_assigns_and_clears():
    cfg: dict = {}
    set_hub_name(cfg, "1-9.1", "A16 #2")
    assert cfg["hub_names"]["1-9.1"] == "A16 #2"
    set_hub_name(cfg, "1-9.1", "  ")                     # blank clears
    assert "1-9.1" not in cfg["hub_names"]


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


def test_a_save_never_leaves_a_half_written_config(tmp_path):
    """The old truncate-in-place left invalid JSON if the process died mid-write
    or the disk filled — and nothing catches the decode error, so every op and
    the whole status page break with the fleet's port mappings and operation
    locks unreadable. The write must be atomic: a reader sees the old file or
    the new one, never a truncated one."""
    import json
    cm = ConfigManager(tmp_path / "config.json")
    cm.save({"hubs": [{"location": "1-2"}], "serials": {"S1": "nemo"}})

    # A failure part-way through the new content must not destroy the old file.
    class _Boom(Exception):
        pass

    real_dump = json.dump

    def explode(obj, fp, **kw):
        fp.write('{"hubs": [{"loc')       # a plausible partial write
        raise _Boom("disk full")

    json.dump = explode
    try:
        try:
            cm.save({"hubs": [{"location": "9-9"}]})
        except _Boom:
            pass
    finally:
        json.dump = real_dump

    cfg = cm.load()                        # must still parse
    assert cfg["hubs"][0]["location"] == "1-2", \
        "a failed save destroyed the previous config"
    assert cfg["serials"] == {"S1": "nemo"}


def test_the_config_lock_excludes_another_process(tmp_path):
    """The CLI is a SEPARATE process running its own load/modify/save cycles
    (the check-charge timer, map, on/off). Two interleaving cycles lose one
    side's write outright, and one thing that can vanish that way is a live
    operation lock — the marker that stops housekeeping cutting a running dump.
    A threading.Lock cannot see another process; an flock can."""
    import subprocess
    import sys
    cm = ConfigManager(tmp_path / "config.json")
    lockfile = str(tmp_path / "config.json.lock")

    probe = (
        "import fcntl, os, sys\n"
        f"fd = os.open({lockfile!r}, os.O_CREAT | os.O_RDWR, 0o644)\n"
        "try:\n"
        "    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
        "    print('GOT')\n"
        "except OSError:\n"
        "    print('BLOCKED')\n")

    with cm.lock:                                   # this process holds it
        out = subprocess.run([sys.executable, "-c", probe],
                             capture_output=True, text=True, timeout=30).stdout
    assert out.strip() == "BLOCKED", \
        "another process could take the config lock while it was held"

    # Released afterwards, or the first crash would wedge the fleet forever.
    out = subprocess.run([sys.executable, "-c", probe],
                         capture_output=True, text=True, timeout=30).stdout
    assert out.strip() == "GOT", "the config lock was never released"


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


# ── SSH-mode IP allocation ──────────────────────────────────────────────────

def test_ssh_ips_are_unique_and_start_at_leet(monkeypatch):
    from asteroid_docking_bay import config as C
    monkeypatch.setattr(C, "_ssh_subnet_free", lambda third, run=None: True)
    cfg = {}
    a = C.allocate_ssh_ip(cfg, "S1")
    b = C.allocate_ssh_ip(cfg, "S2")
    c = C.allocate_ssh_ip(cfg, "S3")
    # One /24 per watch now (the conflict the old shared-/24 scheme caused);
    # the first keeps the historical base .13.37, the rest step the third octet.
    assert a == C.SSH_IP_BASE == "192.168.13.37"
    assert (b, c) == ("192.168.14.37", "192.168.15.37")
    assert len({a, b, c}) == 3


def test_ssh_ip_assignment_is_sticky(monkeypatch):
    from asteroid_docking_bay import config as C
    from asteroid_docking_bay.config import allocate_ssh_ip, ssh_ip_for_serial
    monkeypatch.setattr(C, "_ssh_subnet_free", lambda third, run=None: True)
    cfg = {}
    first = allocate_ssh_ip(cfg, "S1")
    allocate_ssh_ip(cfg, "S2")
    assert allocate_ssh_ip(cfg, "S1") == first, "a watch's SSH IP must not drift"
    assert ssh_ip_for_serial(cfg, "S1") == first
    assert ssh_ip_for_serial(cfg, "unknown") is None


def test_usb_mode_preference_defaults_to_adb_and_ignores_junk():
    from asteroid_docking_bay.config import usb_mode_preference
    assert usb_mode_preference({}) == "adb", "the standard mode is the default"
    assert usb_mode_preference({"usb_mode_preference": "ssh"}) == "ssh"
    assert usb_mode_preference({"usb_mode_preference": "adb"}) == "adb"
    assert usb_mode_preference({"usb_mode_preference": "wat"}) == "adb", (
        "a junk value must fall back to the safe standard, not pass through")


def test_ssh_ip_fills_a_freed_gap(monkeypatch):
    """A removed serial frees its /24, which is reused rather than skipped."""
    from asteroid_docking_bay import config as C
    monkeypatch.setattr(C, "_ssh_subnet_free", lambda third, run=None: True)
    cfg = {}
    C.allocate_ssh_ip(cfg, "S1")               # 192.168.13.37
    b = C.allocate_ssh_ip(cfg, "S2")           # 192.168.14.37
    del cfg["ssh_ips"]["S1"]                    # free the .13 /24
    assert C.allocate_ssh_ip(cfg, "S3") == "192.168.13.37", "did not reuse the /24"
    assert b == "192.168.14.37"


def test_loc_port_for_serial_only_trusts_an_exact_binding():
    """The seat lookup is used to CUT POWER, so it must never guess. An exact
    port_serials binding is the only acceptable answer; a codename mapping —
    which find_serial_for_loc_port is happy to fall back on — is not, because
    two watches of one codename would send the cycle to the innocent one."""
    from asteroid_docking_bay.config import loc_port_for_serial
    cfg = {"hubs": [{"location": "1-2", "port_serials": {"1": "OTHER"}},
                    {"location": "1-3.4", "port_serials": {"2": "S1", "3": "S2"}}],
           "serials": {"S9": "nemo"}}

    assert loc_port_for_serial(cfg, "S1") == ("1-3.4", 2)
    assert loc_port_for_serial(cfg, "S2") == ("1-3.4", 3)
    assert loc_port_for_serial(cfg, "OTHER") == ("1-2", 1)

    # Known watch, but bound to no port: None, not a codename-derived guess.
    assert loc_port_for_serial(cfg, "S9") is None
    assert loc_port_for_serial(cfg, "NEVER-SEEN") is None
    assert loc_port_for_serial(cfg, "") is None
    assert loc_port_for_serial({}, "S1") is None

    # Malformed entries are not ports to cut power on.
    assert loc_port_for_serial(
        {"hubs": [{"location": "1-2", "port_serials": {"notanint": "S1"}}]},
        "S1") is None
    assert loc_port_for_serial(
        {"hubs": [{"port_serials": {"1": "S1"}}]}, "S1") is None
    assert loc_port_for_serial(
        {"hubs": [{"location": "1-2", "port_serials": None}]}, "S1") is None


def _mgr(tmp_path):
    from asteroid_docking_bay.config import ConfigManager
    return ConfigManager(tmp_path / "config.json")


_POPULATED = {"hubs": [{"location": "1-3", "ports": {"1": "sol"}}],
              "serials": {"S1": "sol"}, "ssh_ips": {}}


def test_save_refuses_to_drop_a_populated_fleet_to_empty(tmp_path):
    """The 2026-11-22 incident: a caller saved {"ssh_ips": {}} over a 12-hub
    mapping, and with the backup also gone it was unrecoverable. No code here
    empties the fleet on purpose, so that transition is always a bug — the save
    must keep the good file.
    """
    m = _mgr(tmp_path)
    m.save(_POPULATED)
    assert m.load()["hubs"], "setup failed"

    # The wipe: only ssh_ips, no hubs, no serials.
    m.save({"ssh_ips": {}})

    reloaded = m.load()
    assert reloaded["hubs"], "the fleet mapping was lost — the guard did not hold"
    assert reloaded["serials"] == {"S1": "sol"}
    # The rejected config is kept aside, not silently discarded.
    import json
    rej = tmp_path / "config.json.rejected"
    assert rej.is_file() and json.loads(rej.read_text()) == {"ssh_ips": {}}


def test_first_run_can_still_write_an_empty_config(tmp_path):
    """The guard must not break first run or onboarding, which legitimately
    start from empty: with nothing on disk there is no fleet to lose."""
    m = _mgr(tmp_path)
    m.save({"ssh_ips": {}})                 # nothing on disk yet
    assert m.load().get("hubs") == []       # written, not refused
    # And onboarding builds UP from there — a populated save over empty is fine.
    m.save(_POPULATED)
    assert m.load()["hubs"]


def test_a_meaningful_change_leaves_a_backup(tmp_path):
    """The recovery point the atomic-save rewrite dropped. A change to hubs or
    serials snapshots the previous good file, so a bad later write is always
    one backup away from recovery."""
    m = _mgr(tmp_path)
    m.save(_POPULATED)
    # change the fleet: add a hub
    two = {"hubs": _POPULATED["hubs"] + [{"location": "1-6", "ports": {}}],
           "serials": {"S1": "sol"}, "ssh_ips": {}}
    m.save(two)

    baks = sorted(tmp_path.glob("config.json.bak-*"))
    assert baks, "no backup was written on a meaningful change"
    import json
    assert json.loads(baks[-1].read_text())["hubs"] == _POPULATED["hubs"], \
        "the backup does not hold the PREVIOUS good content"


def test_a_cosmetic_save_does_not_spam_backups(tmp_path):
    """The status path saves every few seconds without touching hubs or
    serials (exact codenames, etc). Those must NOT each cut a backup, or the
    history is buried under noise within a minute."""
    m = _mgr(tmp_path)
    m.save(_POPULATED)
    for i in range(5):
        cosmetic = dict(_POPULATED, exact_codenames={"S1": f"sol{i}"})
        m.save(cosmetic)
    assert list(tmp_path.glob("config.json.bak-*")) == [], \
        "a save that did not change hubs/serials still cut a backup"


def test_empty_over_empty_proceeds_without_a_false_refusal(tmp_path):
    """An already-empty on-disk config (a genuinely reset rig, or the morning
    after an incident) must accept another empty save — there is no fleet to
    lose, so refusing it would be a false positive that also litters a
    .rejected file. This is what makes the had_fleet check meaningful rather
    than just `current is not None`."""
    import json
    m = _mgr(tmp_path)
    m.save({"ssh_ips": {"S1": "192.168.13.37"}})     # empty of fleet, has an IP
    assert (tmp_path / "config.json.rejected").exists() is False

    # another fleet-less save: allowed, because nothing was there to lose
    m.save({"ssh_ips": {"S1": "192.168.13.37", "S2": "192.168.13.38"}})
    assert (tmp_path / "config.json.rejected").exists() is False
    assert m.load()["ssh_ips"] == {"S1": "192.168.13.37", "S2": "192.168.13.38"}


def _no_route(third, run=None):
    """Route check stub: every candidate /24 is free (via gateway)."""
    return True


def test_each_watch_gets_its_own_24(monkeypatch):
    """usb-moded derives its DHCP pool from the watch address, so two watches
    in one /24 give the host the same connected route twice and it can only
    reach the first (meta-smartwatch, approved 2026-11-26). Every watch must
    land in a distinct /24 so plain ssh root@<ip> works."""
    from asteroid_docking_bay import config as C
    monkeypatch.setattr(C, "_ssh_subnet_free", _no_route)
    cfg = {"ssh_ips": {}}
    a = C.allocate_ssh_ip(cfg, "S1")
    b = C.allocate_ssh_ip(cfg, "S2")
    c = C.allocate_ssh_ip(cfg, "S3")
    net = lambda ip: ip.rsplit(".", 1)[0]
    assert len({net(a), net(b), net(c)}) == 3, (a, b, c)
    # the watch sits at .37, outside usb-moded's .1-.15 pool
    assert all(ip.endswith(".37") for ip in (a, b, c)), (a, b, c)
    assert a == "192.168.13.37", a          # first /24 keeps the historical base


def test_allocation_is_sticky(monkeypatch):
    from asteroid_docking_bay import config as C
    monkeypatch.setattr(C, "_ssh_subnet_free", _no_route)
    cfg = {"ssh_ips": {}}
    first = C.allocate_ssh_ip(cfg, "S1")
    assert C.allocate_ssh_ip(cfg, "S1") == first


def test_migration_moves_a_shared_24_but_keeps_the_lowest(monkeypatch):
    """The exact two sticky entries the old scheme wrote: nemo 192.168.13.37
    and sawfish 192.168.13.38, same /24. nemo keeps its /24; sawfish moves to
    its own."""
    from asteroid_docking_bay import config as C
    monkeypatch.setattr(C, "_ssh_subnet_free", _no_route)
    table = {"604KPMZ003491": "192.168.13.37",
             "TKQ7N17406001852": "192.168.13.38"}
    assert C._migrate_ssh_ips(table) is True
    assert table["604KPMZ003491"] == "192.168.13.37"
    assert table["TKQ7N17406001852"] == "192.168.14.37"
    # idempotent: a second pass changes nothing
    assert C._migrate_ssh_ips(table) is False


def test_allocation_skips_a_subnet_the_host_already_routes(monkeypatch):
    """Skip any /24 the host already has a connected route for — the home LAN,
    and a watch link already up. 192.168.2.0/24 is skipped unconditionally
    (the default watch address and the Pro1-X)."""
    from asteroid_docking_bay import config as C
    # pretend 192.168.13 and 192.168.14 are already routed (connected)
    monkeypatch.setattr(C, "_ssh_subnet_free",
                        lambda third, run=None: third not in (13, 14))
    cfg = {"ssh_ips": {}}
    ip = C.allocate_ssh_ip(cfg, "S1")
    assert ip == "192.168.15.37", ip        # 13,14 routed → first free is 15
    # and 2 is reserved even if the route check says free
    monkeypatch.setattr(C, "_ssh_subnet_free", _no_route)
    assert C._next_free_ssh_third({13, 14, 15}) == 16
    assert 2 not in {C._next_free_ssh_third(set(range(13, n))) for n in range(13, 20)}


def test_subnet_free_reads_the_route(monkeypatch):
    """A directly-connected /24 (no `via`) is in use; one via the gateway is
    free. This is what skips the LAN and live watch links without listing them."""
    from asteroid_docking_bay import config as C
    connected = lambda cmd, check=False, timeout=None: (0, "192.168.13.37 dev enx0 src 192.168.13.1", "")
    viagw = lambda cmd, check=False, timeout=None: (0, "192.168.99.37 via 192.168.176.1 dev enp0s25 src 192.168.176.21", "")
    assert C._ssh_subnet_free(13, run=connected) is False
    assert C._ssh_subnet_free(99, run=viagw) is True
    # a failed lookup must not block a switch
    assert C._ssh_subnet_free(50, run=lambda *a, **k: (1, "", "err")) is True
