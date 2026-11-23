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


@pytest.fixture(autouse=True)
def _isolate_task_store(tmp_path_factory, monkeypatch):
    """Redirect the persisted task store at a tmp dir for every test.

    active_op_on_slot() falls through to task_store.load_all() (the durable
    view a separate process sees), so a test running while a REAL charge/drain
    is persisted on disk (~/.local/state/.../tasks) reads that live task and
    false-fails — a port-op test on 1-2:1 gets "a drain owns this port" from an
    actual running drain. Point the store's dir at a tmpdir so the suite only
    ever sees tasks it created itself."""
    from asteroid_docking_bay.tasks import task_store
    monkeypatch.setattr(task_store, "dir",
                        tmp_path_factory.mktemp("tasks"))


@pytest.fixture(autouse=True)
def _clear_onboarding_quiet_window(monkeypatch):
    """Reset the onboarding quiet window before every test.

    While the guided setup is in use, a-d-b holds off fleet-wide corrections
    (the USB-mode aligner) so it does not reshape the watch the user is
    plugging in. That window is a module-level deadline, so ANY test that
    exercises an onboarding op silences the aligner for the next two minutes of
    suite time — which is how the aligner's own tests started failing while the
    aligner was perfectly fine. Reset it so each test states its own conditions.
    """
    import asteroid_docking_bay.util as util
    monkeypatch.setattr(util, "_onboarding_until", 0.0)


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path_factory, monkeypatch):
    """Redirect the config manager at a tmp file for every test.

    save_config/load_config use a module-level ConfigManager pointed at the
    REAL ~/.config/.../config.json. Many ops do `cfg = load_config(); …;
    save_config(cfg)`, and a test that patches load_config to a fleet-less
    store but leaves save_config real writes that store straight to the live
    file — which, run on the deploy host, truncated the whole 12-hub mapping to
    `{"ssh_ips": {}}` on 2026-11-22 and again on 2026-11-23. The suite was the
    culprit, not production.

    Same shape as _isolate_registry and _isolate_task_store above; config was
    simply never added. Repoint the singleton's path and its cross-process
    lock at a tmpdir so the suite can only ever write a config it owns."""
    from asteroid_docking_bay import config as cfg_mod
    d = tmp_path_factory.mktemp("config")
    path = d / "config.json"
    monkeypatch.setattr(cfg_mod.config_manager, "path", path)
    monkeypatch.setattr(cfg_mod.config_manager, "lock",
                        cfg_mod._ConfigLock(path.with_name(path.name + ".lock")))
    # The module also exposes the lock as a shared name; keep it consistent.
    monkeypatch.setattr(cfg_mod, "_config_lock", cfg_mod.config_manager.lock)
