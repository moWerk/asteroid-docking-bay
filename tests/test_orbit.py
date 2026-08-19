# SPDX-License-Identifier: GPL-3.0-only
"""The Orbit port — onboarding a watch reachable over the air (WiFi-SSH).

The transport is injected so these run offline. What must hold: probe() keys the
member on ro.serialno (the fleet serial, so orbit == docked identity), refuses
anything that does not answer as a watch, and the launch/de-orbit ops round-trip
through config without duplicating a re-launched watch."""

import json
import asteroid_docking_bay.orbit as orbit
import asteroid_docking_bay.rpcops as rpcops
import asteroid_docking_bay.webstatus as ws
from asteroid_docking_bay.config import orbit_add, orbit_forget, orbit_members


class _FakeTransport:
    """Stand-in for SshTransport: canned shell output, no network."""

    def __init__(self, out, rc=0):
        self._out, self._rc = out, rc

    def shell(self, cmd, timeout=None):
        return self._rc, self._out, ""


def _patch_probe(monkeypatch, out, rc=0, geo=None):
    monkeypatch.setattr(orbit, "SshTransport",
                        lambda ip: _FakeTransport(out, rc))
    monkeypatch.setattr(orbit, "Watch",
                        lambda serial, transport=None: type(
                            "W", (), {"geometry": lambda self: geo})())


# ── probe ────────────────────────────────────────────────────────────────────

def test_probe_reads_serial_mac_and_geometry(monkeypatch):
    _patch_probe(monkeypatch, "720EX8C130737\n---\n30:95:e3:2d:64:71\n",
                 geo={"machine": "catfish", "resolution": "400x400"})
    m = orbit.probe("192.168.176.97")
    assert m["serial"] == "720EX8C130737"        # ro.serialno = the fleet serial
    assert m["wlanmac"] == "30:95:e3:2d:64:71"
    assert m["codename"] == "catfish" and m["resolution"] == "400x400"
    assert m["ip"] == "192.168.176.97" and isinstance(m["added"], int)


def test_probe_strips_ip_whitespace(monkeypatch):
    _patch_probe(monkeypatch, "S\n---\naa:bb\n", geo={"machine": "x"})
    assert orbit.probe("  10.0.0.5  ")["ip"] == "10.0.0.5"


def test_probe_none_on_empty_ip():
    assert orbit.probe("") is None and orbit.probe(None) is None
    assert orbit.probe("   ") is None


def test_probe_none_when_ssh_fails(monkeypatch):
    # rc != 0 → nothing answered / not reachable → no member, never a half one.
    _patch_probe(monkeypatch, "", rc=255)
    assert orbit.probe("192.168.176.97") is None


def test_probe_none_when_no_serial(monkeypatch):
    # Answered, but no ro.serialno (not an AsteroidOS watch) → refused.
    _patch_probe(monkeypatch, "\n---\n30:95:e3:2d:64:71\n", geo={"machine": "x"})
    assert orbit.probe("192.168.176.97") is None


def test_probe_tolerates_missing_mac(monkeypatch):
    # A watch whose wlan0 read came back empty still onboards; MAC is optional.
    _patch_probe(monkeypatch, "S123\n---\n\n", geo={"machine": "pike"})
    m = orbit.probe("10.0.0.9")
    assert m["serial"] == "S123" and m["wlanmac"] is None


def test_probe_survives_geometry_none(monkeypatch):
    # geometry() returning None must not crash the launch — codename just unknown.
    _patch_probe(monkeypatch, "S1\n---\naa:bb\n", geo=None)
    m = orbit.probe("10.0.0.1")
    assert m["serial"] == "S1" and m["codename"] is None


# ── reachability gate ────────────────────────────────────────────────────────

def test_reachable_true_when_port_open(monkeypatch):
    opened = {}

    class _Sock:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_connect(addr, timeout=None):
        opened["addr"], opened["timeout"] = addr, timeout
        return _Sock()

    monkeypatch.setattr(orbit.socket, "create_connection", fake_connect)
    assert orbit.reachable("10.0.0.5", timeout=2) is True
    assert opened["addr"] == ("10.0.0.5", 22) and opened["timeout"] == 2


def test_reachable_false_when_refused_or_timeout(monkeypatch):
    def boom(addr, timeout=None):
        raise OSError("connection refused")
    monkeypatch.setattr(orbit.socket, "create_connection", boom)
    assert orbit.reachable("10.0.0.5") is False


def test_reachable_false_on_empty_ip():
    assert orbit.reachable("") is False and orbit.reachable(None) is False


# ── per-watch transport routing (the Orbit integration seam) ─────────────────

def test_reachable_transport_routes_to_orbit_wifi(monkeypatch):
    # Not on adb, no rndis SSH IP, but an orbiting member with a live WiFi IP →
    # the op should reach it over WiFi. This is what makes CC/weather/etc. work.
    monkeypatch.setattr(rpcops, "adb_devices", lambda: {})
    monkeypatch.setattr(rpcops, "_adb_state", lambda devs, s: None)
    monkeypatch.setattr(rpcops, "load_config",
                        lambda: {"orbit": {"S1": {"serial": "S1", "ip": "10.0.0.9"}}})
    monkeypatch.setattr(rpcops, "ssh_ip_for_serial", lambda cfg, s: None)
    monkeypatch.setattr(rpcops.orbit, "reachable", lambda ip, **k: True)
    monkeypatch.setattr(rpcops, "SshTransport", lambda ip, over="usb": ("ssh", ip, over))
    # over='wifi': the Control Center shows the transport kind, and calling a
    # WiFi link 'usb' misreports which cable the watch is on.
    assert rpcops._reachable_transport("S1") == ("ssh", "10.0.0.9", "wifi")


def test_reachable_transport_none_when_orbit_unreachable(monkeypatch):
    # An orbiting member that is off WiFi → None (default AdbTransport / stale),
    # never a transport that would block on a dead address.
    monkeypatch.setattr(rpcops, "adb_devices", lambda: {})
    monkeypatch.setattr(rpcops, "_adb_state", lambda devs, s: None)
    monkeypatch.setattr(rpcops, "load_config",
                        lambda: {"orbit": {"S1": {"serial": "S1", "ip": "10.0.0.9"}}})
    monkeypatch.setattr(rpcops, "ssh_ip_for_serial", lambda cfg, s: None)
    monkeypatch.setattr(rpcops.orbit, "reachable", lambda ip, **k: False)
    assert rpcops._reachable_transport("S1") is None


def test_reachable_transport_adb_wins_over_orbit(monkeypatch):
    # A watch that is BOTH docked and an orbit member must use adb (docked wins),
    # not its stale WiFi link.
    monkeypatch.setattr(rpcops, "adb_devices", lambda: {"S1": "device"})
    monkeypatch.setattr(rpcops, "_adb_state", lambda devs, s: "device")
    assert rpcops._reachable_transport("S1") is None


# ── config helpers ───────────────────────────────────────────────────────────

def test_orbit_add_get_and_forget_round_trip():
    cfg = {}
    orbit_add(cfg, {"serial": "S1", "ip": "10.0.0.1", "codename": "pike"})
    assert orbit_members(cfg) == {"S1": {"serial": "S1", "ip": "10.0.0.1",
                                         "codename": "pike"}}
    assert orbit_forget(cfg, "S1") is True
    assert orbit_members(cfg) == {}


def test_relaunch_same_serial_overwrites_not_duplicates():
    cfg = {}
    orbit_add(cfg, {"serial": "S1", "ip": "10.0.0.1"})
    orbit_add(cfg, {"serial": "S1", "ip": "10.0.0.9"})   # same watch, new IP
    assert list(orbit_members(cfg)) == ["S1"]
    assert orbit_members(cfg)["S1"]["ip"] == "10.0.0.9"


def test_forget_absent_or_no_serial_is_false_noop():
    cfg = {"orbit": {"S1": {"serial": "S1"}}}
    assert orbit_forget(cfg, "S9") is False              # not present
    assert orbit_forget(cfg, None) is False              # no serial given
    assert orbit_members(cfg) == {"S1": {"serial": "S1"}}  # untouched


def test_members_empty_when_never_used():
    assert orbit_members({}) == {}


# ── reachability cache ───────────────────────────────────────────────────────

def test_warmer_imports_orbit_members_directly():
    # The background warmer iterates orbit members; it must import orbit_members
    # at module load (a direct, loud import) rather than via a runtime attribute
    # lookup whose failure the warmer's broad except would swallow to debug.
    import asteroid_docking_bay.ops as ops
    assert ops.orbit_members is orbit_members


def test_reach_cache_round_trip():
    orbit.note_reachable("S1", True)
    orbit.note_reachable("S2", False)
    assert orbit.is_reachable_cached("S1") is True
    assert orbit.is_reachable_cached("S2") is False
    assert orbit.is_reachable_cached("never-probed") is False   # unknown → False


# ── handoff (rig ↔ orbit) ────────────────────────────────────────────────────

def test_handoff_only_when_undocked_and_reachable_in_orbit():
    orbit_map = {"S1": {"serial": "S1", "ip": "x"}}
    up = lambda s: True
    down = lambda s: False
    # Left the cradle, still reachable in orbit → hands off.
    assert ws._port_handed_off("S1", None, orbit_map, up) is True
    # Still on a wire here → never hands off, whatever orbit says.
    assert ws._port_handed_off("S1", "device", orbit_map, up) is False
    assert ws._port_handed_off("S1", "ssh", orbit_map, up) is False
    assert ws._port_handed_off("S1", "fastboot", orbit_map, up) is False
    # Undocked but NOT reachable in orbit → stays offline on its port, no handoff.
    assert ws._port_handed_off("S1", None, orbit_map, down) is False
    # Undocked, reachable, but never launched into orbit → no handoff.
    assert ws._port_handed_off("S1", None, {}, up) is False
    # No serial resolved → no handoff.
    assert ws._port_handed_off(None, None, orbit_map, up) is False


# ── status hub-view ──────────────────────────────────────────────────────────

def test_orbit_hub_view_builds_row_for_undocked_reachable(monkeypatch):
    monkeypatch.setattr(ws.orbit, "is_reachable_cached", lambda s: True)
    monkeypatch.setattr(ws.last_seen, "get",
                        lambda s: {"battery": 50, "last_live_ts": 1.0})
    cfg = {"orbit": {"S1": {"serial": "S1", "ip": "10.0.0.9",
                            "codename": "catfish", "resolution": "400x400"}}}
    v = ws._orbit_hub_view(cfg, set())
    assert v["location"] == "orbit" and v["virtual"] is True
    row = v["ports"][0]
    assert row["serial"] == "S1" and row["orbit"] is True
    assert row["adb"] == "ssh" and row["reachable"] is True     # reachable = live SSH
    assert row["battery_cached"] == 50 and row["ip"] == "10.0.0.9"
    assert row["machine"] == "catfish"


def test_orbit_lists_a_docked_watch_too(monkeypatch):
    """Orbit is the list of watches reachable OVER THE AIR, not the list of
    watches that have left.

    It used to hide any watch that was also docked, which answered a different
    and much less useful question. The point of mirroring is continuity: the
    same watch appears on its port (how it is wired) and here (how else it can
    be reached), so when the cable drops nothing has to be rediscovered.
    """
    monkeypatch.setattr(ws.orbit, "is_reachable_cached", lambda s: True)
    monkeypatch.setattr(ws.last_seen, "get", lambda s: {})
    cfg = {"orbit": {"S1": {"serial": "S1", "ip": "x"}}}

    row = ws._orbit_hub_view(cfg, {"S1"})["ports"][0]
    assert row["serial"] == "S1", (
        "a docked watch vanished from Orbit, so the section cannot answer "
        "'what can I reach over WiFi'")
    assert row["docked"] is True, (
        "the row does not say the watch is also on a port, so the UI cannot "
        "tell a mirrored watch from one that has actually left")

    assert ws._orbit_hub_view(cfg, set())["ports"][0]["docked"] is False


def test_orbit_hub_view_unreachable_keeps_last_known(monkeypatch):
    monkeypatch.setattr(ws.orbit, "is_reachable_cached", lambda s: False)
    monkeypatch.setattr(ws.last_seen, "get",
                        lambda s: {"battery": 42, "last_live_ts": 9.0})
    cfg = {"orbit": {"S1": {"serial": "S1", "ip": "x", "codename": "pike"}}}
    row = ws._orbit_hub_view(cfg, set())["ports"][0]
    assert row["adb"] is None and row["reachable"] is False     # no live link
    assert row["battery_cached"] == 42                          # but last-known shown


def test_orbit_hub_view_renders_empty():
    """The Orbit hub is emitted even with NO members: its header carries the
    launch-by-IP input, so hiding the empty section hid the only way to
    (re)populate it — after the 0.9 rig-test data reset the whole feature
    looked deleted (found 2026-07-26). Planted-bug: restore the old
    `return None` on empty rows and this fails."""
    view = ws._orbit_hub_view({}, set())
    assert view["virtual"] is True and view["location"] == "orbit"
    assert view["ports"] == []


# ── ops ──────────────────────────────────────────────────────────────────────

def test_launch_op_probes_and_persists(monkeypatch):
    saved = {}
    monkeypatch.setattr(rpcops.orbit, "probe",
                        lambda ip: {"serial": "S1", "ip": ip, "codename": "pike"})
    monkeypatch.setattr(rpcops, "load_config", lambda: {})
    monkeypatch.setattr(rpcops, "save_config", lambda cfg: saved.update(cfg))
    d = rpcops.DISPATCH._data["orbit.launch"]({"ip": "10.0.0.1"})
    assert d["ok"] is True and d["member"]["serial"] == "S1"
    assert saved["orbit"]["S1"]["ip"] == "10.0.0.1"


def test_launch_op_fails_cleanly_when_unreachable(monkeypatch):
    calls = {"saved": 0}
    monkeypatch.setattr(rpcops.orbit, "probe", lambda ip: None)
    monkeypatch.setattr(rpcops, "load_config", lambda: {})
    monkeypatch.setattr(rpcops, "save_config",
                        lambda cfg: calls.__setitem__("saved", calls["saved"] + 1))
    d = rpcops.DISPATCH._data["orbit.launch"]({"ip": "1.2.3.4"})
    assert d["ok"] is False and "reachable" in d["error"]
    assert calls["saved"] == 0                           # nothing written on failure


def test_deorbit_op_removes_and_saves(monkeypatch):
    saved = {}
    monkeypatch.setattr(rpcops, "load_config",
                        lambda: {"orbit": {"S1": {"serial": "S1"}}})
    monkeypatch.setattr(rpcops, "save_config", lambda cfg: saved.update(cfg))
    d = rpcops.DISPATCH._data["orbit.deorbit"]({"serial": "S1"})
    assert d["ok"] is True and saved["orbit"] == {}


def test_deorbit_op_noop_skips_write(monkeypatch):
    calls = {"saved": 0}
    monkeypatch.setattr(rpcops, "load_config", lambda: {"orbit": {}})
    monkeypatch.setattr(rpcops, "save_config",
                        lambda cfg: calls.__setitem__("saved", calls["saved"] + 1))
    d = rpcops.DISPATCH._data["orbit.deorbit"]({"serial": "S9"})
    assert d["ok"] is False and calls["saved"] == 0


# ── Direct USB: watches on a port no hub owns ────────────────────────────────

def test_direct_view_shows_a_watch_no_mapped_port_owns(monkeypatch):
    """The first thing a new user does: one watch, no smart hub, plugged
    straight into the machine. Rows are built by walking the CONFIGURED hubs,
    so without this view a-d-b talks to the watch over ADB while showing an
    empty table.

    Three cases that must sort correctly:
      - "1-1"     a root port. It has no dotted parent, so it can NEVER belong
                  to a hub -- the bare-laptop-socket case.
      - "1-6.2"   a hub that exists on the bus but nobody has mapped. Same
                  situation from a-d-b's side: connected, unowned.
      - "1-3.2"   a MAPPED hub port. Already has a real row with power and
                  charge cells; showing it twice would be a lie about where
                  the watch is.
    """
    cfg = {"hubs": [{"location": "1-3", "ports": {"2": "catfish"}}],
           "serials": {"SER-ROOT": "sturgeon"}}
    monkeypatch.setattr(ws, "_adb_state", lambda devices, serial: "device")
    monkeypatch.setattr(ws, "watch_devices_on_bus", lambda known_paths=None: [])
    view = ws._direct_hub_view(
        cfg,
        devices={"SER-ROOT": "device", "SER-UNMAPPED": "device", "SER-MAPPED": "device"},
        adb_paths={"SER-ROOT": "1-1", "SER-UNMAPPED": "1-6.2", "SER-MAPPED": "1-3.2"},
        fb_by_path={})
    assert view is not None
    serials = {r["serial"] for r in view["ports"]}
    assert serials == {"SER-ROOT", "SER-UNMAPPED"}, (
        "a watch on a mapped hub port was duplicated into the direct view, or "
        "a watch on an unmapped port was dropped from it")

    rows = {r["serial"]: r for r in view["ports"]}
    # A bare port cannot switch power. Saying so once, as a property of the
    # port, is what keeps the UI from drawing controls that cannot work.
    assert rows["SER-ROOT"]["smart"] is False
    assert rows["SER-ROOT"]["power"] is None
    # Identity comes from config when known and falls back to the serial, so an
    # unknown watch is still addressable rather than blank.
    assert rows["SER-ROOT"]["machine"] == "sturgeon" and rows["SER-ROOT"]["named"]
    assert rows["SER-UNMAPPED"]["machine"] is None
    assert rows["SER-UNMAPPED"]["codename"] == "SER-UNMAPPED"
    assert not rows["SER-UNMAPPED"]["named"]


def test_direct_view_reads_no_hardware_and_stays_quiet_when_empty(monkeypatch):
    """Two contracts.

    It must not touch the bus: this runs on every status refresh, and a watch
    that is slow to answer would stall the whole page. Identity comes from
    config and the last-seen cache only.

    And it returns None with nothing to show. Orbit is emitted empty because
    its header carries the launch-by-IP box; this section has no control of
    its own, so an always-present empty one is pure noise.
    """
    def boom(*a, **k):
        raise AssertionError("the direct view probed hardware during a refresh")
    for name in ("get_watch_codename", "adb_devices"):
        if hasattr(ws, name):
            monkeypatch.setattr(ws, name, boom)

    monkeypatch.setattr(ws, "watch_devices_on_bus", lambda known_paths=None: [])
    assert ws._direct_hub_view({"hubs": []}, {}, {}, {}) is None
    # every watch accounted for by a mapped hub -> still nothing to add
    cfg = {"hubs": [{"location": "1-3", "ports": {"2": "catfish"}}]}
    monkeypatch.setattr(ws, "_adb_state", lambda devices, serial: "device")
    assert ws._direct_hub_view(cfg, {"S": "device"}, {"S": "1-3.2"}, {}) is None

    # a sysfs read that fails must not take the whole status page down
    def boom_bus(known_paths=None):
        raise OSError("sysfs went away")
    monkeypatch.setattr(ws, "watch_devices_on_bus", boom_bus)
    assert ws._direct_hub_view({"hubs": []}, {}, {}, {}) is None


def test_direct_view_sees_a_watch_in_fastboot(monkeypatch):
    """A watch in its bootloader on a bare port is exactly when a user needs to
    see it -- that is the flashing case, which works without a hub. ADB cannot
    see it, so the fastboot path must feed the view too."""
    monkeypatch.setattr(ws, "_adb_state", lambda devices, serial: None)
    monkeypatch.setattr(ws, "watch_devices_on_bus", lambda known_paths=None: [])
    view = ws._direct_hub_view({"hubs": []}, devices={},
                               adb_paths={}, fb_by_path={"1-1": "FBSER"})
    assert view and len(view["ports"]) == 1
    assert view["ports"][0]["adb"] == "fastboot", (
        "a watch in fastboot on an unmapped port must not render as offline")


def test_identify_writes_a_fresh_config_and_keeps_the_rest(monkeypatch, tmp_path):
    """The onboarding write for a portless watch, and the guard against
    repeating 2026-08-16: a helper that persisted the cfg dict it was HANDED
    saved a caller's near-empty copy over a full config and erased 12 hubs.

    So this op must load the config fresh at write time and save that. The test
    plants a rich config on disk AFTER the op is entered, which a
    load-at-entry implementation would already have missed.
    """
    import asteroid_docking_bay.rpcops as ro
    import asteroid_docking_bay.config as cfgmod

    disk = {"hubs": [{"location": "1-3", "ports": {"1": "catfish"}}],
            "serials": {"OLD": "sol"}, "orbit": {"keep": "me"}}
    saved = {}
    monkeypatch.setattr(ro, "load_config", lambda: json.loads(json.dumps(disk)))
    monkeypatch.setattr(ro, "save_config", lambda c: saved.update(c))
    monkeypatch.setattr(ro, "get_watch_codename", lambda s, **kw: "sturgeon")
    monkeypatch.setattr(ro.registry, "note", lambda *a, **k: None)

    d = ro.DISPATCH._data["onboard.identify"]({"serial": "NEWSER"})
    assert d["ok"] and d["codename"] == "sturgeon"
    assert saved["serials"]["NEWSER"] == "sturgeon"
    assert saved["serials"]["OLD"] == "sol", "an existing serial was dropped"
    assert saved["hubs"] == disk["hubs"], (
        "the hub map did not survive naming one watch -- this is the config-wipe "
        "shape: writing a dict that was not loaded fresh at write time")
    assert saved["orbit"] == {"keep": "me"}


def test_identify_refuses_what_it_cannot_name(monkeypatch):
    """Two refusals, both of which would otherwise write junk into the config
    that every later sighting is matched against.

    A watch that does not answer must NOT be stored under a guessed name, and
    a serial that is not a serial (adb's own error strings arrive here) must
    never become a config key."""
    import asteroid_docking_bay.rpcops as ro
    wrote = []
    monkeypatch.setattr(ro, "save_config", lambda c: wrote.append(c))
    monkeypatch.setattr(ro, "get_watch_codename", lambda s, **kw: None)
    d = ro.DISPATCH._data["onboard.identify"]({"serial": "H1NZCJ010087020"})
    assert not d["ok"] and "did not answer" in d["error"]

    monkeypatch.setattr(ro, "get_watch_codename", lambda s, **kw: "sturgeon")
    bad = ro.DISPATCH._data["onboard.identify"]({"serial": "no permissions"})
    assert not bad["ok"]
    assert not wrote, "a refused identify still wrote to the config"


def test_identify_names_a_watch_that_is_only_on_ssh(monkeypatch):
    """Onboarding tells the user SSH works, so naming has to work there.

    Reading the codename was ADB-only: a watch in developer/SSH mode came back
    "did not answer", which blames the watch for a link the reader never
    tried. The op must hand the reader whichever transport reaches the watch.
    """
    import asteroid_docking_bay.rpcops as ro

    class FakeSsh:
        kind = "ssh (usb)"
        def shell(self, cmd, timeout=8, check=False):
            return 0, "MACHINE=sturgeon", ""

    used = {}
    monkeypatch.setattr(ro, "_reachable_transport", lambda s: FakeSsh())
    def reader(serial, shell=None):
        used["shell"] = shell
        if shell is None:
            return None                      # ADB path finds nothing here
        rc, out, _ = shell("cat /etc/asteroid-release")
        return out.split("=", 1)[1] if "=" in out else None
    monkeypatch.setattr(ro, "get_watch_codename", reader)
    monkeypatch.setattr(ro, "load_config", lambda: {})
    monkeypatch.setattr(ro, "save_config", lambda c: None)
    monkeypatch.setattr(ro.registry, "note", lambda *a, **k: None)

    d = ro.DISPATCH._data["onboard.identify"]({"serial": "H1NZCJ010087020"})
    assert d["ok"] and d["codename"] == "sturgeon"
    assert used["shell"] is not None, (
        "the SSH transport was never handed to the codename reader -- an "
        "SSH-only watch stays unnameable")


def test_identify_names_a_watch_in_its_bootloader(monkeypatch):
    """A watch in fastboot has no shell, so no transport reaches it -- and it
    is a real way to meet one during setup: a user arriving from a flash, or a
    watch that fell into its bootloader. Telling them "did not answer" sends
    them hunting for a fault that is not there, when the bootloader will say
    what it is.
    """
    import asteroid_docking_bay.rpcops as ro
    saved = {}
    monkeypatch.setattr(ro, "_fastboot_list", lambda: {"H1NZCJ010087020": "1-1"})
    monkeypatch.setattr(ro, "_fastboot_getvar_product", lambda s: "sparrow")
    monkeypatch.setattr(ro, "load_config", lambda: {"hubs": [{"location": "1-3"}]})
    monkeypatch.setattr(ro, "save_config", lambda c: saved.update(c))
    monkeypatch.setattr(ro.registry, "note", lambda *a, **k: None)
    # the ADB reader must never be reached for a bootloader watch
    monkeypatch.setattr(ro, "get_watch_codename",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("tried to shell into a bootloader")))

    d = ro.DISPATCH._data["onboard.identify"]({"serial": "H1NZCJ010087020"})
    assert d["ok"] and d["codename"] == "sparrow" and d["via"] == "fastboot"
    assert saved["serials"]["H1NZCJ010087020"] == "sparrow"
    assert saved["hubs"], "naming from fastboot dropped the rest of the config"


def test_a_wear_os_watch_names_itself_through_getprop(monkeypatch):
    """Wear OS reference units are Android: no /etc/asteroid-release, no
    /etc/os-release, and a hostname of "localhost" that is correctly refused as
    an identity. Their device codename is the SAME name AsteroidOS uses --
    the port takes the vendor's -- so getprop answers it directly.

    Order matters: getprop must be tried BEFORE hostname, or the search ends on
    a refused "localhost" and the watch reads as unnameable.
    """
    import asteroid_docking_bay.adb as a
    asked = []

    def shell(cmd, timeout=8, check=False):
        asked.append(cmd)
        if "asteroid-release" in cmd or "os-release" in cmd:
            return 1, "", "No such file"
        if "getprop" in cmd:
            return 0, "sturgeon", ""
        return 0, "localhost", ""          # Android hostname, not an identity

    assert a.get_watch_codename("S1", shell=shell) == "sturgeon"
    assert not any("hostname" in c for c in asked), (
        "fell through to hostname, which on Android is 'localhost' and is "
        "refused -- the watch would read as unnameable")


def test_direct_view_shows_a_watch_that_is_only_on_ssh(monkeypatch):
    """A watch in SSH/developer mode is on NEITHER the ADB list nor the
    fastboot one. Built from those two alone, the view showed an empty table
    while a watch sat plugged in and reachable -- which is exactly what a-d-b
    did the moment a watch was switched to SSH during onboarding, with the
    guide still telling the user SSH was supported.

    sysfs knows about it regardless of which service can talk to it.
    """
    monkeypatch.setattr(ws, "watch_devices_on_bus", lambda known_paths=None: [
        {"path": "1-1", "serial": "SER-SSH", "product": "HUAWEI WATCH",
         "pid": "0a02", "vendor": "18d1"}])
    monkeypatch.setattr(ws, "_sysfs_usb_mode", lambda path: "ssh")
    monkeypatch.setattr(ws, "_adb_state", lambda devices, serial: None)

    view = ws._direct_hub_view({"hubs": []}, devices={}, adb_paths={}, fb_by_path={})
    assert view is not None, "a watch on SSH left the table empty"
    row = view["ports"][0]
    assert row["serial"] == "SER-SSH"
    assert row["adb"] == "ssh", (
        "an SSH watch rendered as offline -- the row exists but claims the "
        "watch cannot be reached, which is the opposite of true")
    assert row["product"] == "HUAWEI WATCH"


def test_a_watch_is_matched_to_orbit_by_serial_or_codename(monkeypatch):
    """A watch does not have one serial -- it has whatever each channel reports.

    Measured on sol 2026-08-19: its USB descriptor says `0123456789ABCDEF` (a
    placeholder), while over SSH it reports `4C111JEAYW00RJ`. Launched into
    orbit by hostname, it is keyed by the second, and its port row knows only
    the first. A serial-only match left the port blank while the watch sat
    reachable two rows below, and the Control Center could not follow it.

    The codename is what both channels agree on, so it is the fallback -- but
    only when UNAMBIGUOUS. Two units can share a codename, since they share an
    image, and that is exactly when guessing would attach one unit's row to
    another unit's connection.
    """
    from asteroid_docking_bay.config import orbit_member_for

    cfg = {"serials": {"0123456789ABCDEF": "sol"},
           "orbit": {"4C111JEAYW00RJ": {"serial": "4C111JEAYW00RJ",
                                        "ip": "sol", "codename": "sol"}}}

    m = orbit_member_for(cfg, "0123456789ABCDEF")
    assert m and m["ip"] == "sol", (
        "the watch was not recognised as the orbit member it is -- its two "
        "channels simply report different serials")

    # an exact serial match still wins, and needs no codename at all
    assert orbit_member_for(cfg, "4C111JEAYW00RJ")["ip"] == "sol"

    # unknown watch -> no match rather than the only member present
    assert orbit_member_for(cfg, "SOMEONE-ELSE") is None

    # two orbit members share the codename -> refuse, do not guess
    cfg2 = {"serials": {"USB-A": "tunny"},
            "orbit": {"X": {"serial": "X", "ip": "a", "codename": "tunny"},
                      "Y": {"serial": "Y", "ip": "b", "codename": "tunny"}}}
    assert orbit_member_for(cfg2, "USB-A") is None, (
        "picked one of two watches sharing a codename -- the row would show "
        "another unit's connection")


def test_one_orbiting_watch_does_not_claim_its_shelved_twins(monkeypatch):
    """The rig holds THREE belugas and one of them was mirrored into Orbit.

    Matching that member by codename alone attached it to every beluga row --
    including two that were SHELVED and unpowered, which then displayed as
    reachable over WiFi. A watch that cannot possibly answer must never be
    shown as answering; that is the failure this refusal exists to prevent.

    The right answer is not a better guess but an exact link: an auto-mirror
    records the docked watch it was probed from, so the watch's over-the-air
    identity and its USB one are tied together and no codename is involved.
    """
    from asteroid_docking_bay.config import orbit_member_for

    cfg = {"serials": {"BEL-A": "beluga", "BEL-B": "beluga", "BEL-C": "beluga"},
           "orbit": {"100c0a32": {"serial": "100c0a32", "ip": "192.168.176.132",
                                  "codename": "beluga", "auto": True,
                                  "docked_serial": "BEL-A"}}}

    a = orbit_member_for(cfg, "BEL-A")
    assert a and a["ip"] == "192.168.176.132", (
        "the watch that was actually probed lost its own mirror")
    assert orbit_member_for(cfg, "BEL-B") is None, (
        "a shelved twin claimed the other watch's WiFi connection")
    assert orbit_member_for(cfg, "BEL-C") is None

    # Without the exact link, a single unit of that codename may still match --
    # that is the hand-launched case, and it stays unambiguous.
    solo = {"serials": {"SOL-USB": "sol"},
            "orbit": {"SOL-WIFI": {"serial": "SOL-WIFI", "ip": "sol",
                                   "codename": "sol"}}}
    assert orbit_member_for(solo, "SOL-USB")["ip"] == "sol"

    # ...but the moment a second unit of that codename exists, it refuses
    solo["serials"]["SOL-USB-2"] = "sol"
    assert orbit_member_for(solo, "SOL-USB") is None, (
        "guessed between two units of one model -- one of them is not on WiFi")


def test_orbit_drops_a_docked_watch_that_is_not_reachable(monkeypatch):
    """Two different meanings of an Orbit row, and only one survives going
    offline.

    For a DOCKED watch the row is a live claim -- "you can also reach this over
    the air" -- so when WiFi stops answering the claim is false and the row
    goes. The watch is plainly present on the rig and its port row says so; a
    second row reporting a connection it does not have is just noise.

    For a watch that is NOT on the rig, that row is the only place it exists.
    Dropping it when WiFi blinks would make the watch vanish altogether instead
    of showing offline with its last-known state.
    """
    monkeypatch.setattr(ws.last_seen, "get",
                        lambda s: {"battery": 42, "last_live_ts": 9.0})
    cfg = {"orbit": {"S1": {"serial": "S1", "ip": "x", "codename": "pike"}}}

    monkeypatch.setattr(ws.orbit, "is_reachable_cached", lambda s: False)
    assert ws._orbit_hub_view(cfg, {"S1"})["ports"] == [], (
        "a docked watch with no WiFi was listed in Orbit anyway -- the row "
        "claims a reachability it does not have, beside a port row that "
        "already shows the watch is right here")

    away = ws._orbit_hub_view(cfg, set())["ports"]
    assert len(away) == 1 and away[0]["reachable"] is False, (
        "an away watch vanished when WiFi dropped -- that row is the only "
        "place it exists, so it must stay and show as offline")
    assert away[0]["battery_cached"] == 42

    # docked AND reachable is still listed: the claim is true
    monkeypatch.setattr(ws.orbit, "is_reachable_cached", lambda s: True)
    both = ws._orbit_hub_view(cfg, {"S1"})["ports"]
    assert len(both) == 1 and both[0]["docked"] is True
