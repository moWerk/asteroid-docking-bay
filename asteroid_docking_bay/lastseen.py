# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 Timo Könnecke (moWerk) <mo@mowerk.net>
"""Last-known-good per-watch readings, so the UI can show stale values.

Every reading in the app is live-only today: battery, Control Center stats
and the screen state exist while a watch is on ADB and vanish the instant it
leaves the bus. That is poor UX (a row just empties) and it hides trouble — a
frozen battery reading looks like nothing is wrong.

This store keeps the last value we saw for each serial plus when we saw it
(`last_live_ts`), persisted to the state dir so it survives a service restart.
Consumers read it as a fallback when the watch is offline and mark the value
stale. Writes are coalesced: a material change flushes immediately, otherwise
the disk copy is refreshed at most once per `min_write_interval` so the busy
status warmer can't churn the disk on every identical re-read.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from .util import log


class LastSeen:
    """Per-serial last-known values with restart-surviving persistence.

    The path is a constructor argument so tests use a tmpdir; runtime code
    uses the `last_seen` module singleton."""

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

    def record(self, serial: "str | None", **fields) -> None:
        """Update the stored values for a live watch and stamp last_live_ts.

        None-valued fields are ignored (a failed sub-read must not erase a
        good prior value). last_live_ts always advances — its whole point is
        'when did we last have this watch on the bus'."""
        if not serial:
            return
        fields = {k: v for k, v in fields.items() if v is not None}
        now = time.time()
        with self._lock:
            entry = self._data.get(serial)
            changed = entry is None or any(entry.get(k) != v
                                           for k, v in fields.items())
            if entry is None:
                entry = self._data[serial] = {}
            entry.update(fields)
            entry["last_live_ts"] = now
            if changed or now - self._last_write >= self.min_write_interval:
                self._flush_locked(now)

    def get(self, serial: "str | None") -> "dict | None":
        """A copy of the stored values for a serial, or None if never seen."""
        if not serial:
            return None
        with self._lock:
            entry = self._data.get(serial)
            return dict(entry) if entry else None

    def _flush_locked(self, now: float) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            with tmp.open("w") as fh:
                json.dump(self._data, fh)
            tmp.replace(self.path)
            self._last_write = now
        except Exception as exc:
            log.debug("last_seen flush failed: %s", exc)


last_seen = LastSeen(Path.home()
                     / ".local/state/asteroid-docking-bay/last_seen.json")
