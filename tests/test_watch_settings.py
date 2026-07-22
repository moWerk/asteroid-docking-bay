# SPDX-License-Identifier: GPL-3.0-only
"""The dconf-dump parser, the default-merge, and the read op.

Settings are dconf-direct with no GSettings schema on the watch, so an unset key
reads back empty and its effective value is the baked QML default — the merge
these tests pin. The parser must survive the shapes `dconf dump /` really emits."""

from asteroid_docking_bay import rpcops
from asteroid_docking_bay.watch_settings import (
    SETTINGS, _parse_gvariant, effective_settings, parse_dconf_dump)


def test_parse_gvariant_forms():
    assert _parse_gvariant("true") is True
    assert _parse_gvariant("false") is False
    assert _parse_gvariant("'file:///x.qml'") == "file:///x.qml"
    assert _parse_gvariant("30") == 30
    assert _parse_gvariant("uint32 30") == 30       # typed int prefix
    assert _parse_gvariant("''") == ""
    assert _parse_gvariant("0.5") == "0.5"          # a double we don't model → raw


def test_parse_dconf_dump_sections_and_keys():
    dump = ("[org/asteroidos/settings]\n"
            "use-12h-format=true\n"
            "use-fahrenheit=false\n"
            "\n"
            "[desktop/asteroid]\n"
            "background-filename='file:///w.qml'\n"
            "\n"
            "[desktop/asteroid/nightstand]\n"
            "enabled=false\n")
    d = parse_dconf_dump(dump)
    assert d["/org/asteroidos/settings/use-12h-format"] is True
    assert d["/org/asteroidos/settings/use-fahrenheit"] is False
    assert d["/desktop/asteroid/background-filename"] == "file:///w.qml"
    assert d["/desktop/asteroid/nightstand/enabled"] is False


def test_parse_ignores_comments_blanks_and_keyless_lines():
    d = parse_dconf_dump("# a comment\n\n[org/asteroidos/settings]\n"
                         "use-12h-format=true\nnostanza\n")
    assert d == {"/org/asteroidos/settings/use-12h-format": True}


def test_parse_key_before_any_section_is_dropped():
    # A key with no section header has no full path — it must not be invented as
    # '//key'; the section guard is what prevents that.
    assert parse_dconf_dump("use-12h-format=true\n") == {}


def test_effective_unset_key_shows_its_baked_default():
    rows = {r["key"]: r for r in effective_settings("")}   # empty dump = all default
    aod = rows["/org/asteroidos/settings/always-on-display"]
    assert aod["value"] is True and aod["is_set"] is False     # QML default: on
    twelve = rows["/org/asteroidos/settings/use-12h-format"]
    assert twelve["value"] is False and twelve["is_set"] is False


def test_effective_set_key_overrides_default_and_marks_set():
    rows = {r["key"]: r
            for r in effective_settings("[org/asteroidos/settings]\nuse-12h-format=true\n")}
    twelve = rows["/org/asteroidos/settings/use-12h-format"]
    assert twelve["value"] is True and twelve["is_set"] is True


def test_catalog_covers_only_non_redundant_settings():
    rows = effective_settings("")
    assert len(rows) == len(SETTINGS)
    assert all(r["type"] in ("bool", "path") for r in rows)
    keys = {r["key"] for r in rows}
    # The controls that already live in other tabs/menus must NOT be duplicated.
    assert not any(t in k for k in keys
                   for t in ("wifi", "bluetooth", "usb", "timezone", "power"))


# ── the read op ──────────────────────────────────────────────────────────────

class _FakeWatch:
    rows = [{"key": "/x", "value": True, "is_set": True}]

    def __init__(self, *a, **k):
        pass

    def settings_read(self):
        return type(self).rows


def test_settings_read_op_returns_rows(monkeypatch):
    monkeypatch.setattr(rpcops, "Watch", _FakeWatch)
    monkeypatch.setattr(rpcops, "_reachable_transport", lambda s: None)
    d = rpcops.DISPATCH._data["watch.settings_read"]({"serial": "S1"})
    assert d["ok"] is True and d["settings"][0]["value"] is True


def test_settings_read_op_reports_unreachable(monkeypatch):
    monkeypatch.setattr(rpcops, "_reachable_transport", lambda s: None)
    monkeypatch.setattr(rpcops, "Watch",
                        type("W", (), {"__init__": lambda self, *a, **k: None,
                                       "settings_read": lambda self: None}))
    d = rpcops.DISPATCH._data["watch.settings_read"]({"serial": "S1"})
    assert d["ok"] is False and "unreachable" in d["error"]


# ── the write gate ───────────────────────────────────────────────────────────

def test_writable_accepts_boolean_settings_only():
    from asteroid_docking_bay.watch_settings import writable
    assert writable("/org/asteroidos/settings/use-12h-format") is not None
    assert writable("/desktop/asteroid/watchface") is None        # display-only path
    assert writable("/desktop/asteroid/background-filename") is None
    assert writable("/etc/anything") is None                      # off-catalog


def test_dconf_arg_is_a_bool_literal():
    from asteroid_docking_bay.watch_settings import dconf_arg, writable
    s = writable("/org/asteroidos/settings/use-12h-format")
    assert dconf_arg(s, True) == "true" and dconf_arg(s, False) == "false"


def test_settings_write_refuses_a_display_only_key_without_touching_the_watch():
    from asteroid_docking_bay.watchctl import Watch
    calls = []
    w = Watch("S1", transport=object())
    w.user_cmd = lambda cmd, timeout=12: (calls.append(cmd), (0, "", ""))[1]
    assert w.settings_write("/desktop/asteroid/watchface", True) is False
    assert calls == [], "a display-only key still issued a dconf write"


def test_settings_write_writes_a_boolean_key():
    from asteroid_docking_bay.watchctl import Watch
    calls = []
    w = Watch("S1", transport=object())
    w.user_cmd = lambda cmd, timeout=12: (calls.append(cmd), (0, "", ""))[1]
    assert w.settings_write("/org/asteroidos/settings/use-12h-format", True) is True
    assert len(calls) == 1
    assert "dconf write" in calls[0] and "use-12h-format true" in calls[0]


def test_settings_write_op_coerces_value_and_dispatches(monkeypatch):
    seen = {}

    class W:
        def __init__(self, *a, **k):
            pass

        def settings_write(self, key, value):
            seen.update(key=key, value=value)
            return True

    monkeypatch.setattr(rpcops, "Watch", W)
    monkeypatch.setattr(rpcops, "_reachable_transport", lambda s: None)
    d = rpcops.DISPATCH._data["watch.settings_write"]({"serial": "S1", "key": "/k", "value": 1})
    assert d == {"ok": True} and seen == {"key": "/k", "value": True}


# ── arbitrary clock ──────────────────────────────────────────────────────────

def test_set_datetime_validates_before_touching_the_watch(monkeypatch):
    called = []
    monkeypatch.setattr(rpcops, "_reachable_transport", lambda s: None)
    monkeypatch.setattr(rpcops, "Watch",
                        type("W", (), {"__init__": lambda self, *a, **k: None,
                                       "set_datetime": lambda self, w: (called.append(w), True)[1]}))
    bad = rpcops.DISPATCH._data["watch.set_datetime"]({"serial": "S1", "when": "next tuesday"})
    assert bad == {"ok": False, "error": "bad datetime"} and called == [], \
        "a malformed datetime reached the shell"
    ok = rpcops.DISPATCH._data["watch.set_datetime"]({"serial": "S1", "when": "2026-07-22 14:30:00"})
    assert ok == {"ok": True} and called == ["2026-07-22 14:30:00"]
