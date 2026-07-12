# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 Timo Könnecke (moWerk) <mo@mowerk.net>
# SPDX-FileCopyrightText: 2023 Ed Beroset <beroset@ieee.org>
"""The backend op table (see docs/CONTAINERS.md).

Every host-touching operation the web API offers is a named op here. This is
the single implementation of that logic: the monolithic web server dispatches
to it in-process via LocalCaller, and the split backend serves the same table
over RPC. Adding a capability means registering a named op in a reviewable
diff — there is deliberately no generic "run a command" op.

Op names mirror the former /api/* routes. Handlers take one args dict and
return a JSON-able value (the app-level response, distinct from the RPC
envelope's ok/error). Streaming ops (flash, onboard) are added in the
streaming-bridge step.
"""

import base64
import json
import time

from .util import _run, log
from .config import (_config_lock, charge_config, find_serial_for_loc_port,
                     load_config, save_config)
from .usb import uhubctl_set_power
from .watchctl import Watch
from .ops import ChargeOp, DrainOp, WorkbenchOp
from .events import _DRAIN_FLOOR_PCT, _DRAIN_RESULTS_DIR
from .webstatus import _web_status_data
from .tasks import _charge_tasks
from .rpc import Dispatcher

DISPATCH = Dispatcher()


# ── status ──────────────────────────────────────────────────────────────────

@DISPATCH.op("status.get")
def _status_get(args):
    cfg = load_config()
    cc = charge_config(cfg)
    return {
        "hubs": _web_status_data(cfg),
        "thresholds": {"low": cc.low_threshold, "high": cc.high_threshold},
        "drain_floor": _DRAIN_FLOOR_PCT,
        "wearable_min_hours": cfg.get("wearable_min_hours", 24),
    }


# ── per-watch (Control Center) ──────────────────────────────────────────────

@DISPATCH.op("watch.cc")
def _watch_cc(args):
    return Watch(args["serial"]).cc_data()


@DISPATCH.op("watch.toggle")
def _watch_toggle(args):
    tech = args["tech"]
    if tech not in ("wifi", "bluetooth"):
        return {"ok": False, "error": f"unknown toggle {tech}"}
    return {"ok": Watch(args["serial"]).toggle(tech, bool(args["on"]))}


@DISPATCH.op("watch.settime")
def _watch_settime(args):
    return {"ok": True, "timezone": Watch(args["serial"]).set_time_from_host()}


@DISPATCH.op("watch.notify")
def _watch_notify(args):
    return {"ok": Watch(args["serial"]).notify()}


@DISPATCH.op("watch.buzz")
def _watch_buzz(args):
    return {"ok": Watch(args["serial"]).buzz()}


@DISPATCH.op("watch.screen")
def _watch_screen(args):
    return {"ok": Watch(args["serial"]).screen(bool(args["on"]))}


@DISPATCH.op("watch.screenshot")
def _watch_screenshot(args):
    """JPEG as base64 in the response — keeps the protocol single-channel
    (a screenshot is ~60 KB, the overhead is irrelevant)."""
    local = Watch(args["serial"]).screenshot()
    if not local:
        return {"ok": False, "error": "screenshot failed"}
    return {"ok": True, "jpeg_b64": base64.b64encode(local.read_bytes()).decode()}


# ── port power ──────────────────────────────────────────────────────────────

@DISPATCH.op("port.set")
def _port_set(args):
    try:
        confirmed = uhubctl_set_power(args["loc"], args["port"], bool(args["on"]))
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "confirmed": confirmed}


@DISPATCH.op("port.cycle")
def _port_cycle(args):
    loc, port = args["loc"], args["port"]
    try:
        uhubctl_set_power(loc, port, False)
        time.sleep(5)
        uhubctl_set_power(loc, port, True)
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True}


@DISPATCH.op("port.poweroff")
def _port_poweroff(args):
    """Graceful OS shutdown then cut VBUS immediately — adb shell is
    synchronous, so the command is delivered before power is cut and the
    watch finishes halting on battery. Any delay here races the halt: cutting
    while the watch is still up lets a watch without offmode charging bounce
    back on."""
    loc, port = args["loc"], args["port"]
    serial = find_serial_for_loc_port(load_config(), loc, port)
    adb_ok = False
    if serial:
        rc, _, err = _run(f"adb -s {serial} shell poweroff", check=False,
                          timeout=10)
        adb_ok = (rc == 0)
        if not adb_ok:
            log.warning("poweroff %s:%s (%s): adb shutdown failed: %s",
                        loc, port, serial, err.strip() or f"rc={rc}")
    else:
        log.warning("poweroff %s:%s: no serial known — cutting power only",
                    loc, port)
    try:
        confirmed = uhubctl_set_power(loc, port, False)
    except RuntimeError as e:
        return {"ok": False, "error": str(e), "adb_shutdown": adb_ok}
    return {"ok": True, "adb_shutdown": adb_ok, "confirmed": confirmed}


def _adb_action(loc, port, cmd, fail_msg):
    serial = find_serial_for_loc_port(load_config(), loc, port)
    if not serial:
        return {"ok": False, "error": "no serial found for port"}
    rc, _, err = _run(f"adb -s {serial} {cmd}", check=False)
    if rc != 0:
        return {"ok": False, "error": err or fail_msg}
    return {"ok": True}


@DISPATCH.op("port.reboot")
def _port_reboot(args):
    return _adb_action(args["loc"], args["port"], "reboot",
                       "adb reboot failed")


@DISPATCH.op("port.bootloader")
def _port_bootloader(args):
    return _adb_action(args["loc"], args["port"], "reboot bootloader",
                       "adb reboot bootloader failed")


# ── config visibility ───────────────────────────────────────────────────────

@DISPATCH.op("port.hide")
def _port_hide(args):
    """Toggle a port's user avoid/hidden flag, stored in the hub's exclude
    map alongside auto-detected excludes."""
    loc, port = args["loc"], args["port"]
    with _config_lock:
        cfg = load_config()
        hub = next((h for h in cfg.get("hubs", []) if h["location"] == loc), None)
        if hub is None:
            return {"ok": False, "error": "hub not found"}
        excl = hub.setdefault("exclude", {})
        ps = str(port)
        if ps in excl:
            del excl[ps]
            state = False
        else:
            excl[ps] = "hidden by user"
            state = True
        save_config(cfg)
    return {"ok": True, "hidden": state}


@DISPATCH.op("hub.hide")
def _hub_hide(args):
    """Toggle a whole hub's hidden flag (for unused sub-hubs)."""
    loc = args["loc"]
    with _config_lock:
        cfg = load_config()
        hub = next((h for h in cfg.get("hubs", []) if h["location"] == loc), None)
        if hub is None:
            return {"ok": False, "error": "hub not found"}
        hub["hidden"] = not hub.get("hidden", False)
        state = hub["hidden"]
        save_config(cfg)
    return {"ok": True, "hidden": state}


# ── operations (charge / drain / workbench) ─────────────────────────────────

@DISPATCH.op("charge.start")
def _charge_start(args):
    loc, port = args["loc"], args["port"]
    slot = f"{loc}:{port}"
    if ChargeOp.is_active(slot):
        return {"ok": False, "error": "charge already running",
                "charge_end_ts": _charge_tasks[slot].get("charge_end_ts", 0)}
    cfg = load_config()
    err = ChargeOp.start(loc, port, cfg)
    if err:
        return {"ok": False, "error": err}
    return {"ok": True,
            "duration_seconds": charge_config(cfg).charge_duration_minutes * 60}


@DISPATCH.op("charge.stop")
def _charge_stop(args):
    if ChargeOp.stop(args["loc"], args["port"]):
        return {"ok": True}
    return {"ok": False, "error": "no charge running"}


@DISPATCH.op("workbench.start")
def _workbench_start(args):
    err = WorkbenchOp.start(args["loc"], args["port"], load_config())
    return {"ok": False, "error": err} if err else {"ok": True}


@DISPATCH.op("workbench.stop")
def _workbench_stop(args):
    if WorkbenchOp.stop(args["loc"], args["port"]):
        return {"ok": True}
    return {"ok": False, "error": "no workbench active"}


@DISPATCH.op("drain.start")
def _drain_start(args):
    err = DrainOp.start(args["loc"], args["port"], load_config())
    return {"ok": False, "error": err} if err else {"ok": True}


@DISPATCH.op("drain.stop")
def _drain_stop(args):
    if DrainOp.stop(args["loc"], args["port"]):
        return {"ok": True}
    return {"ok": False, "error": "no drain test running"}


@DISPATCH.op("drain.history")
def _drain_history(args):
    """All recorded drain results, newest first."""
    tests = []
    for f in _DRAIN_RESULTS_DIR.glob("*.json"):
        try:
            with f.open() as fh:
                d = json.load(fh)
        except Exception:
            continue
        readings = d.get("readings") or []
        tests.append({
            "codename":  d.get("codename"),
            "slot":      d.get("slot"),
            "start_ts":  d.get("start_ts"),
            "end_ts":    readings[-1].get("ts") if readings else d.get("start_ts"),
            "start_pct": d.get("start_pct"),
            "end_pct":   d.get("end_pct"),
            "rate":      d.get("drain_rate_pct_per_hour"),
            "stopped":   d.get("stopped_by_user", False),
            "samples":   len(readings),
        })
    tests.sort(key=lambda t: t.get("start_ts") or 0, reverse=True)
    return {"tests": tests,
            "wearable_min_hours": load_config().get("wearable_min_hours", 24)}
