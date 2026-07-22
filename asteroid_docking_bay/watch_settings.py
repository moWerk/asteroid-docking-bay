# SPDX-License-Identifier: GPL-3.0-only
"""The AsteroidOS settings a-d-b mirrors, and how to read them off a watch.

Only the settings NOT already covered by the Control Center's own controls are
mirrored (mo): WiFi/BT/screen/USB-mode/power live in the other tabs and menus,
timezone in Sync-time, and the About page is the System tab. What's left are the
appearance and display preferences below, plus the currently-selected
watchface/launcher/wallpaper shown read-only.

Settings are dconf-direct (Nemo ConfigurationValue) — there is NO GSettings
schema on the watch (verified on skipjack 2026-07-22: `gsettings list-schemas`
lists nothing asteroid, and `gsettings get` fails). So `dconf read` returns
empty for any key still at its default, and the effective default lives in the
asteroid-settings QML `defaultValue`, baked here as `default`. The reader dumps
the whole dconf db once (the call backup already uses) and merges it over these
defaults, so an unset key still shows its true effective value."""

from collections import namedtuple

Setting = namedtuple("Setting", "group key label type default")

# type:
#   "bool" — a togglable switch backed by a dconf boolean
#   "path" — the currently-selected file, shown read-only (mo: display only, no
#            picker — a fleet manager rarely needs to set a watchface remotely)
SETTINGS = [
    Setting("Time & units", "/org/asteroidos/settings/use-12h-format",
            "12-hour clock", "bool", False),
    Setting("Time & units", "/org/asteroidos/settings/use-fahrenheit",
            "Fahrenheit units", "bool", False),
    Setting("Display", "/org/asteroidos/settings/always-on-display",
            "Always-on display", "bool", True),
    Setting("Nightstand", "/desktop/asteroid/nightstand/enabled",
            "Nightstand mode", "bool", True),
    Setting("Nightstand", "/desktop/asteroid/nightstand/always-on-display",
            "Nightstand always-on", "bool", True),
    Setting("Nightstand", "/desktop/asteroid/nightstand/use-custom-watchface",
            "Nightstand custom watchface", "bool", False),
    Setting("Appearance", "/desktop/asteroid/watchface", "Watchface", "path", None),
    Setting("Appearance", "/desktop/asteroid/applauncher", "Launcher", "path", None),
    Setting("Appearance", "/desktop/asteroid/background-filename", "Wallpaper", "path", None),
]


def _parse_gvariant(raw):
    """A dconf-dump scalar → a Python value. Handles the forms our keys use:
    booleans, single-quoted strings, and ints (bare or with a `uint32` prefix);
    anything else passes through as the raw string."""
    raw = raw.strip()
    if raw in ("true", "false"):
        return raw == "true"
    if len(raw) >= 2 and raw[0] == "'" and raw[-1] == "'":
        return raw[1:-1]
    tok = raw.split()[-1] if raw else raw   # 'uint32 30' → '30'
    try:
        return int(tok)
    except ValueError:
        return raw


def parse_dconf_dump(text):
    """`dconf dump /` output (INI-style sections) → {/full/key: value}. A section
    header `[a/b]` prefixes each `key=gvariant` beneath it to `/a/b/key`."""
    out = {}
    section = ""
    for line in (text or "").splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip("/")
            continue
        if section and "=" in line:
            k, v = line.split("=", 1)
            out["/" + section + "/" + k.strip()] = _parse_gvariant(v)
    return out


def effective_settings(dump_text):
    """Merge a dconf dump over the baked defaults → the rows the UI renders, each
    {group,key,label,type,value,is_set}. An unset key carries its QML default as
    `value` with is_set False, so the UI can mark it '(default)' rather than
    pretending nothing is configured."""
    stored = parse_dconf_dump(dump_text)
    rows = []
    for s in SETTINGS:
        is_set = s.key in stored
        rows.append({"group": s.group, "key": s.key, "label": s.label,
                     "type": s.type, "value": stored[s.key] if is_set else s.default,
                     "is_set": is_set})
    return rows


def writable(key):
    """The Setting for a key a-d-b may write, or None. Only the boolean settings
    are writable — the 'path' rows (watchface/launcher/wallpaper) are display-
    only (mo), and any key outside the catalog is refused. This is the boundary:
    the write op can only reach a key this returns non-None for."""
    for setting in SETTINGS:
        if setting.key == key:
            return setting if setting.type == "bool" else None
    return None


def dconf_arg(setting, value):
    """The dconf-write gvariant literal for a setting's new value (bools only)."""
    if setting.type == "bool":
        return "true" if value else "false"
    raise ValueError(f"{setting.type} settings are not writable")
