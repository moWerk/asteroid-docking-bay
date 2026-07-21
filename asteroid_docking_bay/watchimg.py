# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 Timo Könnecke (moWerk) <mo@mowerk.net>
"""Per-watch product images from asteroidos.org, cached on the host.

Each AsteroidOS device has a cut-out product photo at
``asteroidos.org/public/img/<codename>.png`` — the same codename the dock
already uses. We fetch it once, cache it on the host, and serve it locally, so
the *viewer's* browser needn't reach asteroidos.org (a LAN-only rig works) and
their server isn't hit on every page refresh.
"""

from __future__ import annotations

import re
import urllib.request
from pathlib import Path

from .util import log

_IMG_URL = "https://asteroidos.org/public/img/{codename}.png"
_CACHE_DIR = Path.home() / ".local/share/asteroid-docking-bay/watch-images"
# Codenames are lowercase alphanumerics/underscores; anything else can't be a
# real codename and must not reach a URL or a filesystem path.
_CODENAME_RE = re.compile(r"[a-z0-9_]+")
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def watch_image_bytes(codename: "str | None") -> "bytes | None":
    """The watch's product PNG, fetched once and cached. None when there is no
    image for this codename.

    asteroidos.org serves an HTML 404 *page* with a 200 status for an unknown
    codename, so a status check isn't enough — we gate on the PNG magic bytes,
    and cache a genuine miss as a zero-byte file so we don't re-fetch it every
    request. A transient network failure is not cached (it'll retry next time).
    """
    if not codename or not _CODENAME_RE.fullmatch(codename.lower()):
        return None
    cn = codename.lower()
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Prefer a locally-placed transparent-screen cutout, "<cn>-trans.png": these
    # are the reworked HD masters whose alpha screen drives the live-screen
    # composite. They live only on disk (not on the website), so this is a pure
    # local-override layer; watches without one fall through to the plain image.
    trans = _CACHE_DIR / f"{cn}-trans.png"
    if trans.exists() and trans.stat().st_size:
        return trans.read_bytes()
    local = _CACHE_DIR / f"{cn}.png"
    if local.exists():
        data = local.read_bytes()
        return data or None                     # zero-byte marker = "no image"
    try:
        with urllib.request.urlopen(_IMG_URL.format(codename=cn), timeout=8) as resp:
            data = resp.read()
    except Exception as exc:
        log.debug("watch image fetch failed for %s: %s", cn, exc)
        return None                             # transient — don't cache the miss
    if data[:8] == _PNG_MAGIC:
        local.write_bytes(data)
        return data
    local.write_bytes(b"")                       # real miss — cache it
    log.info("no product image for codename %s (%d bytes, not PNG)", cn, len(data))
    return None
