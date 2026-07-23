# SPDX-License-Identifier: GPL-3.0-only
"""Display brightness + sound volume/mute (the Settings tab Display & Sound group).

Brightness is MCE (mcetool, 1..100), volume/mute are PulseAudio (pactl, 0..100),
gated on the machine.conf HAS_SPEAKER capability. The ops clamp; av_read parses
mcetool + pactl output and only reads volume/mute on a speaker watch."""

import asteroid_docking_bay.rpcops as rpcops
from asteroid_docking_bay.watchctl import Watch


class _AVWatch:
    def __init__(self):
        self.calls = []

    def set_brightness(self, p): self.calls.append(("b", p)); return True
    def set_volume(self, p): self.calls.append(("v", p)); return True
    def set_mute(self, o): self.calls.append(("m", o)); return True
    def av_read(self): return {"brightness": 30, "has_speaker": False,
                               "volume": None, "muted": None}


# ── ops: clamp + validation ──────────────────────────────────────────────────

def test_set_brightness_clamps_and_validates(monkeypatch):
    w = _AVWatch()
    monkeypatch.setattr(rpcops, "_watch", lambda s: w)
    assert rpcops.DISPATCH._data["watch.set_brightness"](
        {"serial": "S", "pct": "150"})["pct"] == 100          # over → 100
    assert rpcops.DISPATCH._data["watch.set_brightness"](
        {"serial": "S", "pct": "0"})["pct"] == 1              # brightness never 0
    bad = rpcops.DISPATCH._data["watch.set_brightness"]({"serial": "S", "pct": "x"})
    assert bad["ok"] is False and "integer" in bad["error"]
    assert w.calls == [("b", 100), ("b", 1)]                  # nothing driven on the bad one


def test_set_volume_clamps(monkeypatch):
    w = _AVWatch()
    monkeypatch.setattr(rpcops, "_watch", lambda s: w)
    assert rpcops.DISPATCH._data["watch.set_volume"](
        {"serial": "S", "pct": "150"})["pct"] == 100
    assert rpcops.DISPATCH._data["watch.set_volume"](
        {"serial": "S", "pct": "-5"})["pct"] == 0             # volume may be 0 (silent)


def test_set_mute_and_av_read_passthrough(monkeypatch):
    w = _AVWatch()
    monkeypatch.setattr(rpcops, "_watch", lambda s: w)
    assert rpcops.DISPATCH._data["watch.set_mute"]({"serial": "S", "on": True})["ok"]
    assert w.calls == [("m", True)]
    d = rpcops.DISPATCH._data["watch.av_read"]({"serial": "S"})
    assert d["ok"] is True and d["brightness"] == 30 and d["has_speaker"] is False


# ── av_read parsing ──────────────────────────────────────────────────────────

class _T:
    def __init__(self, out): self._out = out
    def shell(self, cmd, timeout=None): return (0, self._out, "")


def test_av_read_parses_a_speaker_watch(monkeypatch):
    w = Watch("S", transport=_T("Brightness: 30 (1-100)\n---CAP---\nHAS_SPEAKER = true\n"))
    monkeypatch.setattr(w, "user_cmd", lambda cmd, timeout=None: (
        0, "Volume: front-left: 65536 / 40% / 0.00 dB\n---\nMute: yes\n", ""))
    av = w.av_read()
    assert av["brightness"] == 30 and av["has_speaker"] is True
    assert av["volume"] == 40 and av["muted"] is True


def test_av_read_skips_volume_without_a_speaker(monkeypatch):
    w = Watch("S", transport=_T("Brightness: 55 (1-100)\n---CAP---\n"))   # no HAS_SPEAKER
    called = {"n": 0}
    monkeypatch.setattr(w, "user_cmd",
                        lambda cmd, timeout=None: (called.__setitem__("n", 1), (0, "", ""))[1])
    av = w.av_read()
    assert av["brightness"] == 55 and av["has_speaker"] is False
    assert av["volume"] is None and av["muted"] is None
    assert called["n"] == 0                                   # no pactl call on a mute watch
