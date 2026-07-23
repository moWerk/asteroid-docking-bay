# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 Timo Könnecke (moWerk) <mo@mowerk.net>
"""Host-side Bluetooth for the Orbit port — scan for watches and pair them.

The decided path is classic-BT → pair → PAN → IP → SSH (see BLUETOOTH_COMPANION.md):
a bonded link is the gate to everything else. This module is the first two rungs,
over bluez on the system D-Bus (the deprecated sdptool/hciconfig are gone on a
modern host):

- **scan(seconds)** — StartDiscovery, enumerate the devices bluez then knows.
  Correlation to the fleet (by BT-MAC / advertised codename) happens in the op.
- **pair(mac)** — register a pairing agent that auto-accepts the numeric compare
  (AsteroidOS confirms on the watch), call Device1.Pair(), Trust on success.
  The one human step is the on-watch confirm; the host does not prompt.

D-Bus (python-dbus + GLib) is imported lazily inside the functions, so importing
this module never requires the bindings — only actually scanning/pairing does,
and that runs on the host that has bluez. Hardware verified 2026-07-23: the host
has NetworkServer1 + bnep (PAN-ready)."""

import time

from .util import log

BLUEZ = "org.bluez"
_ADAPTER = "org.bluez.Adapter1"
_DEVICE = "org.bluez.Device1"
_OM = "org.freedesktop.DBus.ObjectManager"
_PROPS = "org.freedesktop.DBus.Properties"
_AGENT_MGR = "org.bluez.AgentManager1"
_AGENT_IFACE = "org.bluez.Agent1"
_AGENT_PATH = "/asteroid_docking_bay/btagent"


def _bus():
    import dbus
    import dbus.mainloop.glib
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    return dbus.SystemBus()


def _managed(bus):
    import dbus
    return dbus.Interface(bus.get_object(BLUEZ, "/"), _OM).GetManagedObjects()


def _adapter_path(bus):
    for path, ifaces in _managed(bus).items():
        if _ADAPTER in ifaces:
            return path
    return "/org/bluez/hci0"


def _device_path(bus, mac):
    want = mac.upper()
    for path, ifaces in _managed(bus).items():
        d = ifaces.get(_DEVICE)
        if d and str(d.get("Address", "")).upper() == want:
            return path
    return None


def devices(bus=None):
    """Every device bluez currently knows (from the last/ongoing discovery)."""
    bus = bus or _bus()
    out = []
    for path, ifaces in _managed(bus).items():
        d = ifaces.get(_DEVICE)
        if not d:
            continue
        out.append({"mac": str(d.get("Address", "")),
                    "name": str(d.get("Name", "") or d.get("Alias", "")),
                    "rssi": int(d["RSSI"]) if "RSSI" in d else None,
                    "paired": bool(d.get("Paired", False)),
                    "connected": bool(d.get("Connected", False)),
                    "trusted": bool(d.get("Trusted", False))})
    return out


def scan(seconds=10):
    """Discover for `seconds`, then return the devices bluez knows. Blocking — a
    manual action, never the status path."""
    import dbus
    bus = _bus()
    ad = dbus.Interface(bus.get_object(BLUEZ, _adapter_path(bus)), _ADAPTER)
    try:
        ad.StartDiscovery()
    except dbus.DBusException as e:
        log.debug("bt scan StartDiscovery: %s", e)
    time.sleep(max(1, int(seconds)))
    try:
        ad.StopDiscovery()
    except dbus.DBusException:
        pass
    return devices(bus)


def _make_agent(bus):
    """The auto-accept pairing agent, defined lazily so dbus.service is only
    needed when pairing. AsteroidOS uses numeric-comparison/just-works and
    confirms on the watch, so the host never prompts — it accepts and records the
    passkey (for display) rather than asking a human here."""
    import dbus.service

    class _Agent(dbus.service.Object):
        def __init__(self, b):
            super().__init__(b, _AGENT_PATH)
            self.passkey = None

        @dbus.service.method(_AGENT_IFACE, in_signature="ou", out_signature="")
        def RequestConfirmation(self, device, passkey):
            self.passkey = int(passkey)          # matched + confirmed on the watch

        @dbus.service.method(_AGENT_IFACE, in_signature="ouq", out_signature="")
        def DisplayPasskey(self, device, passkey, entered):
            self.passkey = int(passkey)

        @dbus.service.method(_AGENT_IFACE, in_signature="os", out_signature="")
        def AuthorizeService(self, device, uuid):
            return

        @dbus.service.method(_AGENT_IFACE, in_signature="o", out_signature="")
        def RequestAuthorization(self, device):
            return

        @dbus.service.method(_AGENT_IFACE, in_signature="", out_signature="")
        def Cancel(self):
            pass

        @dbus.service.method(_AGENT_IFACE, in_signature="", out_signature="")
        def Release(self):
            pass

    return _Agent(bus)


def pair(mac, seconds=40):
    """Pair (bond) a discovered device by MAC. Registers the auto-accept agent,
    calls Device1.Pair(), Trusts on success. Returns {ok, paired, passkey, error}.
    The one human step is confirming on the watch within `seconds`."""
    import dbus
    from gi.repository import GLib
    bus = _bus()
    devpath = _device_path(bus, mac)
    if not devpath:
        return {"ok": False, "error": "device not found — scan first"}
    loop = GLib.MainLoop()
    agent = _make_agent(bus)
    mgr = dbus.Interface(bus.get_object(BLUEZ, "/org/bluez"), _AGENT_MGR)
    result = {}
    try:
        mgr.RegisterAgent(_AGENT_PATH, "DisplayYesNo")
        mgr.RequestDefaultAgent(_AGENT_PATH)
    except dbus.DBusException as e:
        log.warning("bt pair agent register: %s", e)
    dev = dbus.Interface(bus.get_object(BLUEZ, devpath), _DEVICE)

    def done(ok, err=None):
        if "ok" not in result:
            result["ok"] = ok
            if err:
                result["error"] = err
            loop.quit()

    dev.Pair(reply_handler=lambda: done(True),
             error_handler=lambda e: done(False, str(e).split(":")[-1].strip()))
    GLib.timeout_add_seconds(
        seconds,
        lambda: (done(False, "timed out — confirm the pairing on the watch"), False)[1])
    loop.run()
    if result.get("ok"):
        try:
            dbus.Interface(bus.get_object(BLUEZ, devpath), _PROPS).Set(
                _DEVICE, "Trusted", True)
        except dbus.DBusException:
            pass
    try:
        mgr.UnregisterAgent(_AGENT_PATH)
        agent.remove_from_connection()
    except dbus.DBusException:
        pass
    result["paired"] = bool(result.get("ok"))
    result["passkey"] = agent.passkey
    return result
