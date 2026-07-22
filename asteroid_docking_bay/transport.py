# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 Timo Könnecke (moWerk) <mo@mowerk.net>
"""Run commands and move files to one watch, over ADB or SSH.

A watch is normally reached over ADB by serial. Switched to SSH/developer USB
mode it is reached over SSH instead — at 192.168.2.15 for a USB-SSH link, or
its WiFi address for a WiFi-SSH link (the two can be active at once). A
Transport hides which, so the same `shell`/`pull`/`push` works either way.

The command quoting is deliberately the same for both back ends: `adb -s S
shell X` and `ssh root@IP X` each forward the already-quoted remote command X
to a shell on the watch, so callers build X exactly as they do today and only
the prefix differs.
"""

from __future__ import annotations

from .util import _run

# USB-SSH: a single watch in developer_mode is reachable here (fixed /24).
USB_SSH_IP = "192.168.2.15"
# Non-interactive, don't pollute/consult known_hosts (a flash rotates the key).
_SSH_OPTS = ("-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
             "-o ConnectTimeout=8 -o BatchMode=yes")


class Transport:
    """One watch's command/file channel. `kind` labels it for the UI/logs."""

    kind = "?"

    def shell(self, cmd: str, timeout: int = 8,
              check: bool = False) -> "tuple[int, str, str]":
        raise NotImplementedError

    def pull(self, remote: str, local: str,
             timeout: int = 15) -> "tuple[int, str, str]":
        raise NotImplementedError

    def push(self, local: str, remote: str,
             timeout: int = 15) -> "tuple[int, str, str]":
        raise NotImplementedError


class AdbTransport(Transport):
    kind = "adb"

    def __init__(self, serial: str):
        self.serial = serial

    def shell(self, cmd, timeout=8, check=False):
        return _run(f"adb -s {self.serial} shell {cmd}", check=check, timeout=timeout)

    def pull(self, remote, local, timeout=15):
        return _run(f"adb -s {self.serial} pull {remote} {local}",
                    check=False, timeout=timeout)

    def push(self, local, remote, timeout=15):
        return _run(f"adb -s {self.serial} push {local} {remote}",
                    check=False, timeout=timeout)


class SshTransport(Transport):
    def __init__(self, ip: str = USB_SSH_IP, over: str = "usb"):
        self.ip = ip
        self.over = over
        self.kind = f"ssh ({over})"

    def shell(self, cmd, timeout=8, check=False):
        return _run(f"ssh {_SSH_OPTS} root@{self.ip} {cmd}",
                    check=check, timeout=timeout)

    def pull(self, remote, local, timeout=15):
        # -r so a directory (backup: .config, connman) copies like `adb pull`.
        return _run(f"scp {_SSH_OPTS} -r root@{self.ip}:{remote} {local}",
                    check=False, timeout=timeout)

    def push(self, local, remote, timeout=15):
        return _run(f"scp {_SSH_OPTS} -r {local} root@{self.ip}:{remote}",
                    check=False, timeout=timeout)
