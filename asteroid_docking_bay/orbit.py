# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 Timo Könnecke (moWerk) <mo@mowerk.net>
"""The Orbit port — fleet watches reachable over the air, not on a USB socket.

A watch that has left the dock but stays on WiFi in developer/SSH mode is still
gravitationally bound to the fleet: it answers at its wlan0 address over SSH as
root — the very SshTransport the docked watches already use. Launching it into
orbit reads the identity the fleet keys on (ro.serialno = the adb serial, so a
watch is the same member whether docked or in orbit) plus its image codename and
geometry. An orbiting watch is just that Watch, minus a USB port. Verified
end-to-end on skipjack (docked→WiFi) and catfish (never docked)."""

import socket
import time

from .transport import SshTransport
from .watchctl import Watch


def probe(ip):
    """SSH-probe an IP → the watch's identity dict, or None when nothing answers
    or it is not a watch. Reads ro.serialno (the fleet serial), the wlan MAC, and
    the image codename + resolution (via the same geometry probe docked watches
    use). One deliberate launch cost; the status path uses reachable()."""
    ip = (ip or "").strip()
    if not ip:
        return None
    t = SshTransport(ip)
    rc, out, _ = t.shell('"getprop ro.serialno 2>/dev/null; echo ---; '
                         'cat /sys/class/net/wlan0/address 2>/dev/null"', timeout=10)
    if rc != 0:
        return None
    serial_part, _, mac = out.partition("---")
    serial = serial_part.strip()
    if not serial:
        return None
    geo = Watch(serial, transport=t).geometry() or {}
    return {"serial": serial, "ip": ip,
            "wlanmac": (mac.strip() or None),
            "codename": geo.get("machine"),
            "resolution": geo.get("resolution"),
            "added": int(time.time())}


def reachable(ip, timeout=3):
    """Cheap, bounded liveness gate: is the watch's SSH port open at ip? A TCP
    connect, not a full handshake — so an offline member costs at most `timeout`,
    never the SSH connect default. Mirrors _detect_rndis's role for the rndis
    link: the gate that keeps the status path and per-watch ops from blocking on
    a watch that has left WiFi."""
    if not ip:
        return False
    try:
        with socket.create_connection((ip, 22), timeout=timeout):
            return True
    except OSError:
        return False
