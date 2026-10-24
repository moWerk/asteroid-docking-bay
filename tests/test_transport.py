# SPDX-License-Identifier: GPL-3.0-only
"""Transport: adb vs ssh issue the same watch command under different prefixes."""

import asteroid_docking_bay.transport as tp


def _spy(monkeypatch):
    calls = []
    monkeypatch.setattr(tp, "_run",
                        lambda cmd, check=True, timeout=None:
                        calls.append((cmd, check, timeout)) or (0, "", ""))
    return calls


def test_adb_prefixes_shell_pull_push(monkeypatch):
    calls = _spy(monkeypatch)
    t = tp.AdbTransport("SER1")
    t.shell("connmanctl enable wifi", timeout=12)
    t.pull("/a", "/b")
    t.push("/b", "/a")
    assert calls[0][0] == "adb -s SER1 shell connmanctl enable wifi"
    assert calls[1][0] == "adb -s SER1 pull /a /b"
    assert calls[2][0] == "adb -s SER1 push /b /a"
    assert t.kind == "adb"


def test_ssh_prefixes_the_same_command(monkeypatch):
    calls = _spy(monkeypatch)
    t = tp.SshTransport()                      # defaults to the USB-SSH IP
    t.shell("connmanctl enable wifi")
    t.pull("/a", "/b")
    t.push("/b", "/a")
    assert calls[0][0].endswith("root@192.168.2.15 connmanctl enable wifi")
    assert calls[0][0].startswith("ssh ")
    assert calls[1][0].endswith("root@192.168.2.15:/a /b") and " -r " in calls[1][0]
    assert calls[2][0].endswith("/b root@192.168.2.15:/a") and calls[2][0].startswith("scp ")
    assert t.kind == "ssh (usb)"


def test_ssh_wifi_uses_its_ip_and_label(monkeypatch):
    _spy(monkeypatch)
    t = tp.SshTransport("192.168.13.37", over="wifi")
    assert t.ip == "192.168.13.37" and t.kind == "ssh (wifi)"


def test_quoting_is_preserved_verbatim(monkeypatch):
    # A piped/quoted command must reach the back end unchanged, so both adb and
    # ssh forward the whole thing to the watch's shell (not the host's).
    calls = _spy(monkeypatch)
    q = '"cat /x 2>/dev/null | head -1"'
    tp.AdbTransport("S").shell(q)
    tp.SshTransport().shell(q)
    assert calls[0][0] == f"adb -s S shell {q}"
    assert calls[1][0].endswith(f"root@192.168.2.15 {q}")


def test_scp_honours_the_transports_user_over_ipv4(monkeypatch):
    """`shell` always used self.user, but pull/push hardcoded root@ on the v4
    path while the v6 path did not. So a transport built for a NON-root login
    ran its commands as that user and then tried to copy files as root.

    Both logins that need this are real: `ceres` on the NCM watches, where
    root cannot reach the wayland socket, and `nemo` on SailfishOS, where
    sshd refuses root outright. Neither is reachable over IPv6, so the branch
    that was wrong is the only branch they use.
    """
    calls = _spy(monkeypatch)
    t = tp.SshTransport("192.168.2.16", over="usb", user="nemo")
    t.pull("/remote/f", "/local/f")
    t.push("/local/f", "/remote/f")
    assert "nemo@192.168.2.16:/remote/f /local/f" in calls[0][0], calls[0][0]
    assert "/local/f nemo@192.168.2.16:/remote/f" in calls[1][0], calls[1][0]
    assert "root@" not in calls[0][0] and "root@" not in calls[1][0]


def test_scp_still_uses_root_when_that_is_the_user(monkeypatch):
    """The default login is root, and the fix must not quietly change it."""
    calls = _spy(monkeypatch)
    tp.SshTransport("192.168.2.15").pull("/a", "/b")
    assert "root@192.168.2.15:/a /b" in calls[0][0], calls[0][0]
