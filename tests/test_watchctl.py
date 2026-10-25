# SPDX-License-Identifier: GPL-3.0-only
"""wait_for_adb targeting: an explicit serial must never resolve to a
different unit of the same codename.

This exists because the flash path identified its target only by codename.
With two watches sharing a codename (e.g. two "skipjack"), the codename scan
could pick — and flash — the wrong physical watch. wait_for_adb(serial=…) now
pins the exact unit; this test fails against the old codename-only match.
"""

import asteroid_docking_bay.watchctl as wc
import asteroid_docking_bay.transport as tp
from asteroid_docking_bay.watchctl import wait_for_adb


class _CC:
    adb_wait_seconds = 0      # no real sleeping in the test
    adb_wait_retries = 1


def test_explicit_serial_does_not_match_a_sibling(monkeypatch):
    # Only the SIBLING (same codename, different serial) is online.
    monkeypatch.setattr(wc, "adb_devices",
                        lambda: {"SIBLING": {"status": "device"}})
    monkeypatch.setattr(wc, "get_watch_codename", lambda s: "skipjack")
    # Asking for WANTED must not return SIBLING — the wrong-watch bug.
    assert wait_for_adb("skipjack", {}, _CC(), serial="WANTED") is None


def test_explicit_serial_matches_itself(monkeypatch):
    monkeypatch.setattr(wc, "adb_devices",
                        lambda: {"WANTED": {"status": "device"}})
    assert wait_for_adb("skipjack", {}, _CC(), serial="WANTED") == "WANTED"


def test_no_serial_still_matches_by_codename(monkeypatch):
    # Backward compatible: without an explicit serial, the codename scan runs.
    monkeypatch.setattr(wc, "adb_devices",
                        lambda: {"SOMEUNIT": {"status": "device"}})
    monkeypatch.setattr(wc, "get_watch_codename", lambda s: "skipjack")
    monkeypatch.setattr(wc, "save_config", lambda cfg: None)
    assert wait_for_adb("skipjack", {}, _CC()) == "SOMEUNIT"


# ── geometry: shape from machine.conf, resolution from fb0/modes ─────────────

def _geo_run(conf, modes):
    def fake(cmd, check=True, timeout=None):
        if "machine.conf" in cmd:
            return (0, conf, "")
        if "fb0/modes" in cmd:
            return (0, modes, "")
        return (1, "", "")
    return fake


def test_geometry_round_watch(monkeypatch):
    monkeypatch.setattr(tp, "_run", _geo_run(
        "[Display]\nROUND = true\n\n[Identity]\nMACHINE = skipjack\n",
        "U:360x360p-2640\n"))
    geo = wc.Watch("S1").geometry()
    assert geo["round"] is True and geo["machine"] == "skipjack"
    # Resolution must come from modes, not the double-buffered virtual_size.
    assert geo["width"] == 360 and geo["height"] == 360
    assert geo["resolution"] == "360x360"


def test_geometry_square_watch(monkeypatch):
    monkeypatch.setattr(tp, "_run", _geo_run(
        "[Display]\nROUND = false\nFLAT_TIRE = 0\n", "U:320x320p-100\n"))
    geo = wc.Watch("S1").geometry()
    assert geo["round"] is False and geo["flat_tire"] == 0 and geo["width"] == 320


def test_watch_routes_through_an_injected_ssh_transport(monkeypatch):
    from asteroid_docking_bay.transport import SshTransport
    calls = []
    monkeypatch.setattr(tp, "_run",
                        lambda cmd, check=True, timeout=None:
                        calls.append(cmd) or (0, "", ""))
    wc.Watch("S", SshTransport("1.2.3.4")).toggle("wifi", True)
    assert calls and calls[0].startswith("ssh ")
    assert "root@1.2.3.4 connmanctl enable wifi" in calls[0]


def test_geometry_empty_when_unreachable(monkeypatch):
    monkeypatch.setattr(tp, "_run", lambda *a, **k: (1, "", ""))
    assert wc.Watch("S1").geometry() == {}


def test_every_battery_reader_uses_the_preferred_gauge():
    """Two independent battery readers exist — the status path in adb.py and
    the Control Center's on-watch script — and BOTH must prefer the named
    fuel gauge. catfish carries a generic `battery` node frozen at 50% next to
    a nanohub gauge reading the truth (8% while the watch was panicking,
    2026-07-28); only adb.py knew, so the Control Center, the fleet registry
    and the battery history all showed a fabricated 50% for weeks. Planted-bug:
    hardcode /sys/class/power_supply/battery/capacity back into the script and
    this fails."""
    from asteroid_docking_bay.watchctl import _CC_SCRIPT
    from asteroid_docking_bay.adb import BATTERY_DIRS, _BATTERY_SYSFS_PATHS
    assert "/sys/class/power_supply/battery/capacity" not in _CC_SCRIPT
    assert "$BATD/capacity" in _CC_SCRIPT
    assert "nanohub_fuelgauge" in _CC_SCRIPT      # resolved from BATTERY_DIRS
    # the two readers derive from one list, so they cannot drift apart
    assert _BATTERY_SYSFS_PATHS == tuple(f"{d}/capacity" for d in BATTERY_DIRS)
    assert BATTERY_DIRS[0].endswith("nanohub_fuelgauge-*")


# ── Wear OS control-centre read ──────────────────────────────────────────────
# Fixture is VERBATIM output from a stock, non-rooted watch (beluga 22979c8c,
# Android 9 / SDK 28, uid 2000) captured 2026-08-03. The empty values are the
# point: those reads exist on AsteroidOS and silently return nothing here.

_WEAROS_CC_OUT = """android=9
host=OPPO Watch
kernel=4.9.112-gf6e60c6-dirty-ab109
uptime=39674.78
memtotal=921400
memfree=37180
membuffers=
memcached=
soc=msm8909
datetime=2021-12-03 12:32:53
tz=GMT
df=/dev/block/mmcblk0p40   4387952 398664   3989288  10% /data
bt_name=OPPO Watch 9c8c
build_id=PXDR.201012.001.OW19W6EU_11_A.51.211203091439
sdk=28
wear_app=2.41.0.333086249
bat_cap=100
bat_status_raw=5
bat_health_raw=2
bat_mv=4411
bat_temp=363
"""


def _cc_via(monkeypatch, serial, os_name, out):
    """Drive the real cc_data with a stubbed transport and OS detection."""
    from asteroid_docking_bay import watchctl as wc
    monkeypatch.setitem(wc._watch_os, serial, os_name)
    w = wc.Watch.__new__(wc.Watch)
    w.serial = serial
    seen = {}

    class _T:
        def shell(self, cmd, timeout=None):
            seen["cmd"] = cmd
            return 0, out, ""
    w.t = _T()
    return w.cc_data(), seen


def test_wearos_watch_is_read_with_android_commands(monkeypatch):
    """A Wear OS watch answers none of the AsteroidOS reads. Before this, the
    batch came back empty, cc_data returned {}, and the UI kept rendering the
    last AsteroidOS snapshot as though live — a watch reflashed to Wear OS went
    on reporting an AsteroidOS version and battery it no longer had."""
    info, seen = _cc_via(monkeypatch, "22979c8c", "WearOS", _WEAROS_CC_OUT)
    assert "dumpsys battery" in seen["cmd"], "used the AsteroidOS script"
    assert "connmanctl" not in seen["cmd"], "connman does not exist on Android"
    assert info["os"] == "Wear OS (Android 9)"
    assert info["host"] == "OPPO Watch"
    assert info["serial"] == "22979c8c"


def test_wearos_battery_is_translated_into_fleet_units(monkeypatch):
    """dumpsys reports status/health as integers and voltage in MILLIvolts,
    while every other watch reports words and MICROvolts. Leaving that alone
    would put two spellings of one concept in the same UI column."""
    info, _ = _cc_via(monkeypatch, "22979c8c", "WearOS", _WEAROS_CC_OUT)
    assert info["bat_cap"] == "100"
    assert info["bat_status"] == "Full"        # 5
    assert info["bat_health"] == "Good"        # 2
    assert info["bat_volt"] == "4411000"       # mV -> µV
    assert info["bat_temp"] == "363"           # tenths on both, unchanged
    for raw in ("bat_status_raw", "bat_health_raw", "bat_mv"):
        assert raw not in info, f"{raw} leaked into the UI payload"


def test_wearos_leaves_unread_toggles_unknown_rather_than_off(monkeypatch):
    """There is no connman on Android. Reporting the radios as off would show a
    state we never read — the same class of lie as rendering a stale snapshot."""
    info, _ = _cc_via(monkeypatch, "22979c8c", "WearOS", _WEAROS_CC_OUT)
    assert info.get("wifi") is None and info.get("bluetooth") is None


def test_asteroidos_watch_still_uses_the_original_script(monkeypatch):
    """The Wear OS path must not disturb the fleet's normal read."""
    out = "os=AsteroidOS 2.2-nightly\nbat_cap=88\n--connman--\nType = wifi\nPowered = True\n"
    info, seen = _cc_via(monkeypatch, "225791c5", "asteroidos", out)
    assert "connmanctl" in seen["cmd"] and "dumpsys" not in seen["cmd"]
    assert info["os"] == "AsteroidOS 2.2-nightly"
    assert info["wifi"] is True
    assert info["bat_cap"] == "88"


def test_normalise_invents_nothing_it_did_not_read():
    """It labels the OS and converts battery units — and touches nothing else.
    A field dumpsys did not report must stay absent rather than appear empty,
    since an empty value in the UI reads as a reading, not as a gap."""
    from asteroid_docking_bay.watchctl import normalise_wearos_cc
    got = normalise_wearos_cc({"bat_cap": "50", "host": "OPPO Watch"})
    assert got["bat_cap"] == "50" and got["host"] == "OPPO Watch"
    for absent in ("bat_status", "bat_health", "bat_volt", "bat_temp"):
        assert absent not in got, f"{absent} was invented from nothing"
    # No android version read: label the brand alone, do not print "(Android )".
    assert got["os"] == "Wear OS"

    # A code dumpsys could emit that we have no mapping for stays as-is rather
    # than being dropped or guessed at.
    odd = normalise_wearos_cc({"bat_status_raw": "9", "bat_mv": "notanumber"})
    assert odd["bat_status"] == "9"
    assert "bat_volt" not in odd, "a non-numeric voltage was converted anyway"


def test_os_label_never_prints_the_android_version_as_a_wear_version(monkeypatch):
    """ro.build.version.release is the ANDROID version. Printing it as
    "Wear OS 9" would state a version that has never existed — Android 9
    carries Wear OS 2.x — so the label names both explicitly."""
    info, _ = _cc_via(monkeypatch, "22979c8c", "WearOS", _WEAROS_CC_OUT)
    assert info["os"] == "Wear OS (Android 9)"
    assert info["os"] != "Wear OS 9"
    assert info["wear_brand"] == "WearOS"


def test_wear_brand_uses_the_companion_app_not_the_android_version():
    """Google renamed Android Wear to Wear OS in March 2018 via an update to
    the COMPANION APP, so watches that stayed on Android 7.1.1 were rebranded
    in place. The Android version alone therefore cannot separate them around
    that boundary — both rig watches sit on either side of it and are Wear OS."""
    from asteroid_docking_bay.watchctl import wear_brand
    # Verified devices: beluga (Android 9, app 2.41) and nemo (7.1.1, app 2.35).
    assert wear_brand("28", "2.41.0.333086249") == "WearOS"
    assert wear_brand("25", "2.35.0.325323493") == "WearOS", \
        "an old Android version was mistaken for old branding"
    # Pre-rename app on the same Android version -> the other brand.
    assert wear_brand("25", "2.10.0.1") == "AndroidWear"
    assert wear_brand("22", "1.5.0.7") == "AndroidWear"
    # SDK 26+ postdates the rename outright, whatever the app says.
    assert wear_brand("26", "1.0.0.0") == "WearOS"


def test_wear_brand_defaults_rather_than_guessing_wrong_when_unreadable():
    """Neither signal readable: answer with the modern name, because an Android
    Wear device still in service was rebranded in place years ago. A default,
    not a detection — and it must never crash on junk."""
    from asteroid_docking_bay.watchctl import wear_brand
    for bad in ("", "notanumber", "2", "..", None):
        assert wear_brand(bad or "", bad or "") == "WearOS"


def test_is_android_watch_covers_both_brands_but_not_asteroidos():
    """cc_data picks its script from this; missing a brand would send the
    AsteroidOS reads to an Android watch and reproduce the stale-panel bug."""
    from asteroid_docking_bay.watchctl import is_android_watch
    assert is_android_watch("WearOS") and is_android_watch("AndroidWear")
    assert not is_android_watch("asteroidos")
    assert not is_android_watch("unknown") and not is_android_watch(None)


# --- SailfishOS: same daemons, missing tools, non-root login ---------------

class _Spy:
    """A transport that records the command instead of running it."""
    def __init__(self, rc=0):
        self.calls = []
        self.rc = rc
    def shell(self, cmd, timeout=8, check=False):
        self.calls.append(cmd)
        return self.rc, "", ""


def _sfos_watch(monkeypatch, os_name="Sailfish OS 5.1.0.11 (Pispala)"):
    import asteroid_docking_bay.watchctl as wc
    monkeypatch.setattr(wc, "_watch_os_for", lambda s: os_name)
    w = wc.Watch.__new__(wc.Watch)
    w.serial = "XA2"
    w.t = _Spy()
    return w, w.t


def test_is_sailfish_matches_the_release_string_not_an_exact_name():
    """os-release carries the version and a codename that changes every
    release, so an equality test would go stale on the next update."""
    import asteroid_docking_bay.watchctl as wc
    assert wc.is_sailfish("Sailfish OS 5.1.0.11 (Pispala)")
    assert wc.is_sailfish("sailfishos")
    assert not wc.is_sailfish("asteroidos")
    assert not wc.is_sailfish("")
    assert not wc.is_sailfish(None)


def test_user_cmd_does_not_wrap_su_on_sailfish(monkeypatch):
    """a-d-b is already logged in AS the session user there: sshd refuses root
    outright, there is no su to drop into, and the session bus address is
    already in the environment. Wrapping in `su ceres` would be wrong twice."""
    w, spy = _sfos_watch(monkeypatch)
    w.user_cmd("dconf dump /")
    assert "su ceres" not in spy.calls[0], spy.calls[0]
    assert "dconf dump /" in spy.calls[0]


def test_user_cmd_still_drops_into_ceres_on_asteroidos(monkeypatch):
    w, spy = _sfos_watch(monkeypatch, os_name="asteroidos")
    w.user_cmd("dconf dump /")
    assert "su ceres" in spy.calls[0], spy.calls[0]
    assert "XDG_RUNTIME_DIR=/run/user/1000" in spy.calls[0]


def test_screen_on_sailfish_also_holds_the_display(monkeypatch):
    """mcetool's demo mode is one action; on SailfishOS turning the display on
    and keeping it on are two separate mce requests. Asking only for
    req_display_state_on gives a screen that blanks again on the usual
    timeout, which is not what the toggle promises."""
    w, spy = _sfos_watch(monkeypatch)
    assert w.screen(True) is True
    joined = " ".join(spy.calls)
    assert "req_display_state_on" in joined
    assert "req_display_blanking_pause" in joined
    assert "mcetool" not in joined


def test_screen_off_on_sailfish_releases_the_hold_first(monkeypatch):
    """Turning the display off without cancelling the pause leaves mce still
    asked to keep it awake, so it can come straight back on."""
    w, spy = _sfos_watch(monkeypatch)
    w.screen(False)
    joined = " ".join(spy.calls)
    assert "req_display_cancel_blanking_pause" in joined
    assert "req_display_state_off" in joined
    assert spy.calls.index([c for c in spy.calls if "cancel" in c][0]) < \
           spy.calls.index([c for c in spy.calls if "state_off" in c][0])


def test_screen_still_uses_mcetool_on_asteroidos(monkeypatch):
    w, spy = _sfos_watch(monkeypatch, os_name="asteroidos")
    w.screen(True)
    assert spy.calls[0] == "mcetool -D on", spy.calls[0]


def test_the_control_centre_script_puts_sbin_on_the_path():
    """a-d-b is root on an AsteroidOS watch, and root's PATH carries sbin. It
    is not root everywhere: on SailfishOS it logs in as the session user,
    whose non-interactive PATH is /usr/local/bin:/bin:/usr/bin. `ip` lives in
    /usr/sbin there, so every address came back empty -- and an empty address
    looks exactly like a device that has no such interface, which is how it
    was misread on an XA2 until the PATH was checked.
    """
    import asteroid_docking_bay.watchctl as wc
    assert wc._CC_SCRIPT.startswith("PATH="), wc._CC_SCRIPT[:60]
    assert "/usr/sbin" in wc._CC_SCRIPT.split(";", 1)[0]
    # and the script it guards is still there, not replaced by the prefix
    assert "os=$NAME $VERSION" in wc._CC_SCRIPT
