# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 Timo Könnecke (moWerk) <mo@mowerk.net>
"""The Fleet Registry — a durable per-serial record of every watch the rig has
ever seen, docked or in orbit, with a time-stamped Log of what changed.

`last_seen` keeps only the LATEST reading and is really a staleness cache. The
registry is its historical superset: it never forgets a serial (a watch swapped
away into a drawer stays on the books), and it appends a Log entry whenever a
**tracked** field changes — kernel, Qt, OS release, SoC, the MACs, resolution,
codename. That is the archaeology: 'Qt went 5.15 → 6.11 on this date', 'the
kernel changed after that flash', 'this hull first appeared three weeks ago'.
Volatile values (battery, ip, time) are kept as latest but never clog the Log.

Fed automatically from the reads the app already does (Control Center, orbit
probe/warmer), so it fills itself with no extra device traffic."""

from __future__ import annotations

import copy
import json
import threading
import time
from pathlib import Path

from .util import log

# The fields whose CHANGE is worth a Log entry — identity and versions, the
# things a flash or an update moves. Everything else a caller passes is kept as
# "latest" only. `source` (adb|ssh|orbit) is recorded but is not itself tracked.
TRACKED = ("codename", "kernel", "qt", "release", "soc",
           "wlanmac", "btmac", "resolution")
MAX_LOG = 200          # cap the Log per watch; oldest entries drop first


class Registry:
    """Per-serial records with restart-surviving persistence. The path is a
    constructor argument so tests use a tmpdir; runtime uses the module
    singleton `registry`."""

    def __init__(self, path: Path, min_write_interval: float = 60.0):
        self.path = Path(path)
        self.min_write_interval = min_write_interval
        self._lock = threading.Lock()
        self._data: dict[str, dict] = self._load()
        self._last_write = 0.0

    def _load(self) -> dict[str, dict]:
        try:
            with self.path.open() as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except Exception as exc:
            log.warning("could not read %s: %s", self.path, exc)
            return {}

    def note(self, serial: "str | None", source: "str | None" = None,
             **fields) -> None:
        """Fold a sighting into the registry. None-valued fields are ignored (a
        failed sub-read must not erase a good prior value). A change in any
        TRACKED field appends a Log entry {ts, source, changes}; last_seen and
        last_source always advance; first_seen is stamped once."""
        if not serial:
            return
        fields = {k: v for k, v in fields.items() if v is not None}
        now = time.time()
        with self._lock:
            rec = self._data.get(serial)
            fresh = rec is None
            if fresh:
                rec = self._data[serial] = {"serial": serial,
                                            "first_seen": now,
                                            "fields": {}, "log": []}
            stored = rec["fields"]
            # A Log entry is a TRANSITION from a known prior value. First sighting
            # of the watch, and first acquisition of a field (None → value), are
            # the baseline, not a change — only value → different-value logs.
            changes = {k: [stored.get(k), v] for k, v in fields.items()
                       if k in TRACKED and stored.get(k) is not None
                       and stored.get(k) != v}
            stored.update(fields)
            rec["last_seen"] = now
            if source:
                rec["last_source"] = source
            if changes:
                rec["log"].append({"ts": now, "source": source,
                                   "changes": changes})
                del rec["log"][:-MAX_LOG]           # keep the newest MAX_LOG
            if fresh or changes or now - self._last_write >= self.min_write_interval:
                self._flush_locked(now)

    def get(self, serial: "str | None") -> "dict | None":
        """A deep copy of one watch's full record (incl. Log), or None."""
        if not serial:
            return None
        with self._lock:
            rec = self._data.get(serial)
            return copy.deepcopy(rec) if rec else None

    def all(self) -> list[dict]:
        """Every record, newest sighting first — the roster with full Logs."""
        with self._lock:
            recs = copy.deepcopy(list(self._data.values()))
        recs.sort(key=lambda r: r.get("last_seen", 0), reverse=True)
        return recs

    def _flush_locked(self, now: float) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            with tmp.open("w") as fh:
                json.dump(self._data, fh)
            tmp.replace(self.path)
            self._last_write = now
        except Exception as exc:
            log.debug("registry flush failed: %s", exc)


registry = Registry(Path.home()
                    / ".local/state/asteroid-docking-bay/registry.json")
