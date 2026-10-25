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

# Which login answered at a given address, once we have found out. AsteroidOS
# is root everywhere, so it is tried first and nothing below ever runs for the
# watches. SailfishOS refuses root outright at sshd, and its login user is
# `nemo` on the older images and `defaultuser` from 4.x on -- a-d-b cannot
# know which before it has spoken to the device, and cannot read /etc/passwd
# to find out without logging in first.
_SSH_LOGINS = ("root", "nemo", "defaultuser")
_login_for: dict = {}


def forget_ssh_login(ip: str) -> None:
    """Drop a remembered login. A reflashed device at the same address may
    answer to a different one."""
    _login_for.pop(ip, None)


def _is_auth_refusal(rc: int, err: str) -> bool:
    """Whether ssh refused the LOGIN, as opposed to failing to reach the host.

    The distinction matters: a wrong login is worth one retry with another
    name, and an unreachable host is worth none. Both exit 255, so the exit
    code alone cannot tell them apart, and retrying on it would triple the
    cost of every timeout on a shelved watch."""
    low = (err or "").lower()
    return rc != 0 and ("permission denied" in low
                        or "no supported authentication" in low)
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
    """SSH to a watch, over USB-RNDIS, WiFi, or a USB-NCM link.

    `user` and IPv6 exist for the NCM watches. Their login is `ceres`, not
    root: it is sufficient for every read a-d-b makes and REQUIRED for
    screenshots, because the wayland socket is ceres:ceres inside
    /run/user/1000 at mode 0700 -- root can traverse that but must set
    XDG_RUNTIME_DIR and WAYLAND_DISPLAY by hand and may still hit
    session-scoped auth.

    An NCM watch is addressed by its IPv6 LINK-LOCAL with a scope, e.g.
    fe80::ba:45ff:fe0b:aeb8%enp0s20u3u4u3i1. That needs no addressing on either
    side and cannot collide, because the scope names the interface. Note the
    address takes NO brackets here: brackets are URL syntax (scp, curl), and
    ssh rejects them -- verified on the rig, where the bracketed form failed
    with "Could not resolve hostname".
    """

    def __init__(self, ip: str = USB_SSH_IP, over: str = "usb",
                 user: "str | None" = None):
        self.ip = ip
        self.over = over
        # An explicit user is honoured and never second-guessed: the NCM
        # watches must be ceres, and probing alternatives there would log in
        # as root and then fail at the wayland socket, which looks like a
        # broken screenshot rather than a wrong login.
        self.fixed_user = user is not None
        self.user = user or _login_for.get(ip, _SSH_LOGINS[0])
        self.kind = f"ssh ({over})"

    @property
    def _target(self) -> str:
        return f"{self.user}@{self.ip}"

    @property
    def _family(self) -> str:
        # Force v6 for a link-local: with a scope there is nothing to guess,
        # and it keeps a v4 fallback from silently changing which watch answers.
        return " -6" if ":" in self.ip else ""

    def shell(self, cmd, timeout=8, check=False):
        rc, out, err = _run(f"ssh{self._family} {_SSH_OPTS} {self._target} {cmd}",
                            check=check, timeout=timeout)
        if rc == 0:
            _login_for[self.ip] = self.user
            return rc, out, err
        if self.fixed_user or self.ip in _login_for:
            return rc, out, err
        # The command failed and we do not yet know which login this device
        # takes -- and we cannot tell why from THIS result. Callers routinely
        # append `2>/dev/null`, which the HOST shell applies to ssh itself, so
        # ssh's own "Permission denied" is thrown away and the refusal arrives
        # as a bare 255 with empty stderr, indistinguishable from an
        # unreachable host. Measured on an XA2: the os-release read carries
        # that redirect, so the fallback never fired, detection fell through
        # to getprop -- which hybris devices answer -- and a Jolla phone
        # reported itself as a Wear OS watch.
        #
        # So the question is asked with a command of OUR OWN, whose stderr no
        # caller can redirect. It runs only while the login is unknown.
        for candidate in _SSH_LOGINS:
            prc, _, perr = _run(
                f"ssh{self._family} {_SSH_OPTS} {candidate}@{self.ip} true",
                check=False, timeout=timeout)
            if prc == 0:
                _login_for[self.ip] = candidate
                if candidate == self.user:
                    return rc, out, err      # right login, command failed
                self.user = candidate
                return _run(
                    f"ssh{self._family} {_SSH_OPTS} {self._target} {cmd}",
                    check=check, timeout=timeout)
            if not _is_auth_refusal(prc, perr):
                break        # unreachable, not a login problem: stop probing
        return rc, out, err

    def pull(self, remote, local, timeout=15):
        # -r so a directory (backup: .config, connman) copies like `adb pull`.
        # scp DOES want brackets around a v6 address, unlike ssh.
        if ":" in self.ip:
            return _run(f"scp -6 {_SSH_OPTS} -r {self.user}@[{self.ip}]:{remote} {local}",
                        check=False, timeout=timeout)
        return _run(f"scp {_SSH_OPTS} -r {self._target}:{remote} {local}",
                    check=False, timeout=timeout)

    def push(self, local, remote, timeout=15):
        if ":" in self.ip:
            return _run(f"scp -6 {_SSH_OPTS} -r {local} {self.user}@[{self.ip}]:{remote}",
                        check=False, timeout=timeout)
        return _run(f"scp {_SSH_OPTS} -r {local} {self._target}:{remote}",
                    check=False, timeout=timeout)
