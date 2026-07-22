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
