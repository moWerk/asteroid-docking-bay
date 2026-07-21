# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 Timo Könnecke (moWerk) <mo@mowerk.net>
"""Exact hardware codenames for watches that share one system image.

The AsteroidOS porting process is inconsistent: some hardware variants ship
their own image and MACHINE name (sparrow, wren), while others were folded onto
a sibling's image to save space (tunny ships the skipjack image; belugaxl/orca
ship the beluga image). So machine.conf's MACHINE= is ambiguous — two
physically different watches report the same name, and no dedicated image
exists to flash for the folded-in variant.

The user-facing codename must still be exact (matching asteroidos.org), so we
disambiguate by whatever the watch actually exposes. Today that is only the
screen resolution (from /sys/class/graphics/fb0/modes); resolution is not
globally unique but IS unique within a shared-image family. The full ground
truth (GPS, LTE, RAM, case size) is recorded in watch_variants.json even where
no detector exists yet — add the factor to DETECTABLE once it can be read and
the same table applies with no re-survey.

This is purely cosmetic: the MACHINE image is what gets flashed. See
docs/ADDING-A-WATCH.md.
"""

from __future__ import annotations

import json
from pathlib import Path

from .util import log

# Attributes a-d-b can read from a live watch today. Extend this as detectors
# are built (and populate the matching keys in the `observed` dict passed to
# exact_codename); the ground truth in watch_variants.json already carries the
# per-variant values, so nothing needs re-testing.
DETECTABLE = ("resolution",)

_DATA_FILE = Path(__file__).parent / "watch_variants.json"


def _load() -> dict:
    try:
        with _DATA_FILE.open() as fh:
            return json.load(fh).get("shared_images", {})
    except Exception as exc:
        log.warning("could not load %s: %s", _DATA_FILE.name, exc)
        return {}


_SHARED_IMAGES = _load()


def _norm_res(res: "str | None") -> "str | None":
    """Canonicalise a WxH string to min-x-max so panel orientation (WxH vs HxW)
    can't cause a miss."""
    try:
        a, b = str(res).lower().split("x")
        return f"{min(int(a), int(b))}x{max(int(a), int(b))}"
    except Exception:
        return res


def exact_codename(machine: "str | None",
                   observed: "dict | None" = None) -> "str | None":
    """The exact hardware codename for a watch running the `machine` image.

    A unique image (machine not in the table) is returned unchanged. For a
    shared image, return the first variant whose DETECTABLE attributes all match
    the watch's `observed` ones, else the image's base codename — never a guess.
    """
    if not machine:
        return machine
    fam = _SHARED_IMAGES.get(machine)
    if not fam:
        return machine
    obs = dict(observed or {})
    if "resolution" in obs:
        obs["resolution"] = _norm_res(obs["resolution"])
    for variant in fam.get("variants", []):
        constraints = {k: variant[k] for k in DETECTABLE if k in variant}
        if "resolution" in constraints:
            constraints["resolution"] = _norm_res(constraints["resolution"])
        if all(obs.get(k) == val for k, val in constraints.items()):
            return variant["codename"]
    return fam.get("base", machine)


def image_of(codename: "str | None") -> "str | None":
    """The MACHINE image a codename ships on, or None if it is its own image
    (or unknown). image_of('tunny') == 'skipjack'."""
    for machine, fam in _SHARED_IMAGES.items():
        if any(v.get("codename") == codename for v in fam.get("variants", [])):
            return machine
    return None
