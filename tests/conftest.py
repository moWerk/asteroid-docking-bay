# SPDX-License-Identifier: GPL-3.0-only
"""Shared test fixtures."""

import pytest


@pytest.fixture(autouse=True)
def _isolate_registry(tmp_path_factory, monkeypatch):
    """Redirect the Fleet Registry singleton at a tmp file for every test.

    The CC and orbit ops feed the module-level `registry` singleton; without
    this, running the suite would write test serials into the real state file
    (~/.local/state/.../registry.json). Every module holds the same object, so
    repointing its path + clearing its data isolates them all at once."""
    from asteroid_docking_bay.registry import registry
    d = tmp_path_factory.mktemp("registry")
    monkeypatch.setattr(registry, "path", d / "registry.json")
    monkeypatch.setattr(registry, "_data", {})
    monkeypatch.setattr(registry, "_last_write", 0.0)
