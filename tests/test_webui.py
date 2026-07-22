# SPDX-License-Identifier: GPL-3.0-only
"""Wiring integrity of the served page: handlers, element ids, API paths.

Three UI bugs shipped that no endpoint test could catch: a toast() call
targeting an element that was never in the page (killed the screenshot
action), a menu item wired to a dead confirm-reveal instead of the action
(14 power-off clicks did nothing), and both were found by humans clicking.
These tests read the template the way the browser will."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from asteroid_docking_bay.webtemplate import _WEB_TEMPLATE

JS = max(re.findall(r"<script>(.*?)</script>", _WEB_TEMPLATE, re.S), key=len)


def global_simple():
    """JS that swaps reconcileRows for the plain innerHTML path in render tests."""
    return "\nreconcileRows=function(tb,h){tb.innerHTML=h.join('');};\n"
DEFINED_FUNCS = set(re.findall(r"function\s+([A-Za-z_]\w*)\s*\(", JS))


def _handler_names():
    """Every function name the page wires to a click, wherever it's wired:
    static onclick attributes, onclick inside JS-built HTML strings, and the
    menu-item builder's action argument."""
    names = set()
    # onclick="fn(..." — in raw HTML and in template-literal-built HTML
    names |= set(re.findall(r'onclick=\\?"\$?\{?([A-Za-z_]\w*)\(', _WEB_TEMPLATE))
    # mi(cls, label, "fn(...)") — the action is a string that becomes onclick
    names |= set(re.findall(r"mi\([^,]+,[^,]+,\s*[`'\"]([A-Za-z_]\w*)\(", JS))
    return names


def test_every_click_handler_is_defined():
    missing = sorted(_handler_names() - DEFINED_FUNCS)
    assert not missing, (
        f"onclick wires to undefined function(s): {missing} — "
        "clicking these does nothing (the doHalt/power-off bug class)")


def test_every_literal_element_id_exists():
    wanted = set(re.findall(r"getElementById\('([A-Za-z][\w-]*)'\)", JS))
    static_ids = set(re.findall(r'id="([\w-]+)"', _WEB_TEMPLATE))
    # ids the JS itself creates at runtime (t.id='toast' pattern)
    created = set(re.findall(r"\.id\s*=\s*'([\w-]+)'", JS))
    missing = sorted(wanted - static_ids - created)
    assert not missing, (
        f"getElementById targets that exist nowhere: {missing} — "
        "the missing-#toast bug class (handler throws, action dies)")


def _route_patterns():
    """Every route the server registers: the _JSON_ROUTES table (imported —
    it IS the contract) plus the explicit @app routes in webapp.py."""
    from asteroid_docking_bay.webapp import _JSON_ROUTES
    src = (Path(__file__).resolve().parent.parent
           / "asteroid_docking_bay" / "webapp.py").read_text()
    paths = [spec[1] for spec in _JSON_ROUTES]
    paths += re.findall(r'@app\.(?:get|post)\("([^"]+)"\)', src)
    return [(p, re.compile("^" + re.sub(r"<[^>]+>", "[^/]+", p) + "$"))
            for p in paths]


def test_every_js_api_call_hits_a_route():
    routes = _route_patterns()
    # fetch('/api/x/y/'+... and EventSource('/api/...') — take the literal
    # prefix and check it can still complete into some registered route.
    calls = re.findall(r"(?:fetch|EventSource)\('(/api/[^']*)'", JS)
    unmatched = []
    for prefix in calls:
        probe = prefix + ("X" if prefix.endswith("/") else "")
        # complete the probe with path segments until it matches or gives up
        ok = False
        for _, rx in routes:
            candidate = probe
            for _ in range(4):
                if rx.match(candidate):
                    ok = True
                    break
                candidate += "/X"
            if ok:
                break
        if not ok:
            unmatched.append(prefix)
    assert not unmatched, (
        f"JS calls API paths no route serves: {unmatched} — "
        "route/JS drift (renamed or removed endpoint)")


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_served_js_parses():
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(JS)
        path = f.name
    r = subprocess.run(["node", "--check", path], capture_output=True,
                       text=True)
    assert r.returncode == 0, f"served JS has a syntax error:\n{r.stderr}"


# Representative status doc exercising render's branches: a mapped on-adb watch
# with a wearable drain result + forced screen, a draining watch with a
# swap-candidate result, an empty port. Enough to run mkthumb/mkstrip/mkbat and
# the charge/drain paths.
_SAMPLE = {
    "version": "test", "thresholds": {"low": 40, "high": 80},
    "drain_floor": 15, "wearable_min_hours": 24,
    "hubs": [{"location": "1-2", "description": "Hub", "hidden": False, "ports": [
        {"port": 1, "codename": "skipjack", "serial": "S1", "slot_loc": "1-2",
         "power": True, "smart": True, "connected": True, "adb": "device",
         "battery": 83, "os": "asteroidos", "screen_forced": True,
         "charge_status": "Charging",
         "geometry": {"round": True, "resolution": "360x360",
                      "width": 360, "height": 360},
         "drain_last": {"est_h": 300, "ts": 1783900000}, "drain": None,
         "charging_active": False, "socket": 1},
        {"port": 2, "codename": "bass", "serial": "S2", "slot_loc": "1-2",
         "power": False, "smart": True, "connected": False, "adb": None,
         "battery": None, "drain": {"active": True, "last_pct": 50, "drain_rate": 0.9},
         "drain_last": {"est_h": 90, "ts": 1783900000}, "socket": 2},
        {"port": 3, "codename": None, "slot_loc": "1-2", "power": False,
         "empty": True, "adb": None, "socket": 3},
        {"port": 4, "codename": "casio", "serial": "S4", "slot_loc": "1-2",
         "power": False, "smart": True, "connected": False, "adb": None,
         "battery": None, "battery_cached": 62, "last_live_ts": 1783900000,
         "drain": None, "drain_last": None, "socket": 4},
    ]}],
}

_DOM_STUBS = r"""
function el(){return{style:{},classList:{add(){},remove(){},contains:()=>false,toggle(){}},
  innerHTML:'',textContent:'',value:'',querySelectorAll:()=>[],querySelector:()=>null,
  appendChild(){},removeChild(){},remove(){},setAttribute(){},getAttribute:()=>null,offsetHeight:100,offsetWidth:100};}
global.document={getElementById:()=>el(),createElement:()=>el(),addEventListener(){},body:el(),documentElement:el()};
global.window={innerWidth:1200,innerHeight:800,addEventListener(){},open(){},location:{href:''}};
global.fetch=()=>Promise.resolve({json:()=>Promise.resolve({}),text:()=>Promise.resolve('')});
global.EventSource=function(){this.close=function(){}};
global.localStorage={getItem:()=>null,setItem(){}};global.navigator={};
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_hole_detection_finds_interior_transparency(tmp_path):
    """holeBoxFromAlpha must return the enclosed screen-cutout box and ignore
    the render's transparent background (border-connected transparency)."""
    import json
    harness = r"""
      function grid(w,h,f){const a=new Uint8Array(w*h);
        for(let y=0;y<h;y++)for(let x=0;x<w;x++)a[y*w+x]=f(x,y);return a;}
      // opaque body, a 2x2 hole at (2,2) in a 6x6 image
      const b1=holeBoxFromAlpha(grid(6,6,(x,y)=>(x>=2&&x<=3&&y>=2&&y<=3)?0:255),6,6);
      // transparent BACKGROUND ring + opaque body + a 1px interior hole at (3,3)
      const b2=holeBoxFromAlpha(grid(7,7,(x,y)=>
        (x===0||y===0||x===6||y===6)?0:((x===3&&y===3)?0:255)),7,7);
      // no interior transparency at all -> null
      const b3=holeBoxFromAlpha(grid(5,5,(x,y)=>(x===0||y===0||x===4||y===4)?0:255),5,5);
      console.log(JSON.stringify({b1,b2,b3}));
      process.exit(0);
    """
    h = tmp_path / "hole.js"
    h.write_text(_DOM_STUBS + JS + "\n" + harness)
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:600]
    out = json.loads(r.stdout)
    b1 = out["b1"]
    assert abs(b1["x"] - 2/6) < 1e-6 and abs(b1["w"] - 2/6) < 1e-6
    b2 = out["b2"]                                    # background ring excluded
    assert abs(b2["x"] - 3/7) < 1e-6 and abs(b2["w"] - 1/7) < 1e-6
    assert out["b3"] is None


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_render_runs_without_throwing(tmp_path):
    """render() must execute against a real-shaped status doc. The parse test
    can't catch a runtime throw — e.g. a helper (mkstrip) referencing a
    render-local const (wearH), which silently surfaced as 'connection error'
    because the throw lands in the status fetch's .catch."""
    import json
    h = tmp_path / "harness.js"
    # Render twice: the first pass is the initial load (firstStatus true), the
    # second exercises the post-load path — the newly-plugged-row flash compares
    # against the serials seen on the first pass.
    h.write_text(_DOM_STUBS + JS + global_simple() +
                 f"\ntry{{const S={json.dumps(_SAMPLE)};render(S);render(S);"
                 f"console.log('RENDER_OK');}}"
                 f"catch(e){{console.error('THREW '+e);process.exit(1);}}\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0 and "RENDER_OK" in r.stdout, (
        f"render() threw when run headless:\n{r.stderr[:600]}")


# Caching DOM: getElementById must return the *same* object across calls so an
# innerHTML written during render is still readable afterwards. The plain
# _DOM_STUBS mint a fresh element each call, which is fine for "did it throw"
# but discards everything render() produced.
_DOM_CAPTURE = _DOM_STUBS.replace(
    "global.document={getElementById:()=>el(),",
    "global.__els={};global.document={getElementById:(i)=>(global.__els[i]=global.__els[i]||el()),")


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_refresh_button_powers_only_an_off_switchable_port(tmp_path):
    """The refresh button doubles as "power on and identify". A watch plugged
    into a powered-down port is invisible to adb, so refresh alone left the row
    showing the previous occupant forever — the button has to raise VBUS first.
    It must do that only where power is switchable and not excluded, and must
    NOT re-power a port that is already on (that would be a pointless write on
    every ordinary refresh)."""
    import json
    h = tmp_path / "refresh.js"
    h.write_text(_DOM_CAPTURE + JS + global_simple() +
                 f"\nconst S={json.dumps(_SAMPLE)};render(S);"
                 "console.log(JSON.stringify(Object.values(global.__els)"
                 ".map(e=>e.innerHTML).join('')));\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, f"harness failed:\n{r.stderr[:600]}"
    html = json.loads(r.stdout.strip().splitlines()[-1])

    flags = dict(re.findall(r"doRefresh\('([^']+)',(true|false)\)", html))
    assert flags, f"no doRefresh wiring found in rendered rows:\n{html[:400]}"
    # skipjack is powered on -> refresh must stay a plain re-read
    assert flags.get("1-2:1") == "false", (
        f"refresh on an already-powered port asks to power it again: {flags}")
    # bass and casio are switchable but off -> refresh must raise power
    assert flags.get("1-2:2") == "true", (
        f"refresh on an off switchable port does not power it — a watch "
        f"plugged in while the port was down stays unidentifiable: {flags}")
    assert flags.get("1-2:4") == "true", f"off port 4 not wired to power: {flags}"


def test_refreshing_row_pulse_survives_hover():
    """The refreshing-row pulse is the only feedback that a re-identify is in
    flight. An !important background on the :hover rule outranks the animation
    itself (important declarations beat keyframes), pinning the row and hiding
    the hint exactly while the pointer is on the row being watched."""
    hover = [ln for ln in _WEB_TEMPLATE.splitlines()
             if ".wr.refreshing:hover" in ln]
    assert hover, "no hover rule for a refreshing row — hover will mask the pulse"
    assert not any("!important" in ln for ln in hover), (
        f"!important on the refreshing-row hover rule kills the pulse "
        f"animation it is meant to preserve: {hover}")
    assert "@keyframes rpulsehover" in _WEB_TEMPLATE, (
        "hovered refreshing rows need their own keyframe pulsing from the "
        "hover colour, else the pulse is invisible under the highlight")


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_adb_and_ssh_badges_are_consistent_two_way_toggles(tmp_path):
    """Both USB-mode badges should read as one control: the same pill shape,
    the AsteroidOS logo in front, and a click that toggles to the other mode.
    The ADB pill switches an AsteroidOS watch to SSH; the SSH pill switches
    back to ADB."""
    import json
    h = tmp_path / "badges.js"
    h.write_text(_DOM_STUBS + JS +
                 "\nconsole.log(JSON.stringify({"
                 "adb: mkadb('device','', 'asteroidos','S9'),"
                 "ssh: mkadb('ssh','', null,'S9'),"
                 "wear: mkadb('device','', 'WearOS','S9')}));"
                 "\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    out = json.loads(r.stdout.strip().splitlines()[-1])

    # Both are pills (cbadge), real <button>s so the cursor is a pointer, and
    # carry the logo (an inline <svg>).
    for k in ("adb", "ssh"):
        assert "cbadge" in out[k], f"{k} badge is not the pill style: {out[k]}"
        assert "<button" in out[k], f"{k} clickable badge is not a real button: {out[k]}"
        assert "<svg" in out[k], f"{k} badge is missing the AsteroidOS logo"
    # Clicking a badge opens the Network Center (not an inline mode toggle,
    # which was too easy to misclick).
    assert "openNC(" in out["adb"], f"ADB pill does not open Network Center: {out['adb']}"
    assert "openNC(" in out["ssh"], f"SSH pill does not open Network Center: {out['ssh']}"
    # The ADB pill shows the serial (its address), like SSH shows the IP.
    assert "S9" in out["adb"], f"ADB pill does not show the serial: {out['adb']}"
    # A known non-AsteroidOS OS is a status pill, not an SSH toggle (usb_moded
    # is AsteroidOS-only) and carries no asteroid logo.
    assert "switchSsh(" not in out["wear"] and "<svg" not in out["wear"], out["wear"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_workbench_menu_shows_the_usb_ip_banner(tmp_path):
    """The watch's SSH address is the most useful thing to have while working
    on it, so the workbench menu leads with a prominent non-clickable IP
    banner — deliberately redundant with the row badge."""
    import json
    h = tmp_path / "wb.js"
    # Stub openMenu to capture the HTML it is handed.
    h.write_text(_DOM_STUBS + JS +
                 "\nlet CAP='';openMenu=function(ev,html){CAP=html;};"
                 "menuWorkbench({}, '1-2:1','S9', false,'ssh','192.168.13.37');"
                 "console.log(JSON.stringify(CAP));\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    html = json.loads(r.stdout.strip().splitlines()[-1])
    assert "menu-ip" in html and "192.168.13.37" in html, html
    # It must be a plain banner, not a clickable action.
    assert 'class="menu-ip"' in html and "onclick" not in html.split("menu-hd")[0]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_network_center_lists_usb_ip_and_mode_toggle(tmp_path):
    """Clicking the badge opens the Network Center. It must carry the USB IP —
    which lives nowhere else — and the deliberate USB-mode toggle that the
    badge no longer does inline."""
    import json
    h = tmp_path / "nc.js"
    h.write_text(_DOM_CAPTURE + JS +
                 "\nncSshIp='192.168.13.37';ncMode='ssh';ncSerial='S9';ncName='skipjack';"
                 "renderNC({serial:'S9', os:'AsteroidOS', wifi:1, ip:'10.0.0.9', wlanmac:'aa:bb'});"
                 "console.log(JSON.stringify(global.__els['nc'].innerHTML));"
                 "\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    html = json.loads(r.stdout.strip().splitlines()[-1])
    assert "192.168.13.37" in html, f"Network Center is missing the USB IP: {html[:300]}"
    assert "USB IP" in html
    assert "switchAdb(" in html, "SSH-mode Network Center lacks the USB->ADB toggle"
    assert "ncToggle('wifi'" in html, "Network Center lacks the WiFi toggle"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_control_center_no_longer_carries_the_network_section(tmp_path):
    """The network detail moved to the Network Center, freeing the Control
    Center. Its render must no longer emit the old WiFi/BT toggle wiring."""
    import json
    h = tmp_path / "ccnet.js"
    h.write_text(_DOM_CAPTURE + JS +
                 "\nccName='skipjack';ccSerial='S9';"
                 "renderCC({serial:'S9', kernel:'3.18', os:'AsteroidOS', wifi:1});"
                 "console.log(JSON.stringify(global.__els['cc'].innerHTML));"
                 "\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    html = json.loads(r.stdout.strip().splitlines()[-1])
    assert "ccToggle(" not in html, "Control Center still wires the moved WiFi/BT toggles"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_battery_cell_is_a_clickable_pill_opening_battery_info(tmp_path):
    """The battery cell is a pill: percent plus appended dim detail, clicking
    it opens Battery Info. A watch with a serial gets a real button."""
    import json
    h = tmp_path / "bp.js"
    h.write_text(_DOM_STUBS + JS +
                 "\nconst cell=mkbatCell({battery:83,charge_status:'Charging',"
                 "serial:'S9',codename:'skipjack'}, 40, 80);"
                 "console.log(JSON.stringify(cell));\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    cell = json.loads(r.stdout.strip().splitlines()[-1])
    assert "cbadge bat" in cell, f"battery cell is not a pill: {cell}"
    assert "<button" in cell and "openBI('S9'" in cell, cell
    assert "83%" in cell and "Charging" in cell, "pill missing percent or appended detail"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_battery_info_window_lists_the_detail(tmp_path):
    """Battery Info carries the detail moved out of the Control Center."""
    import json
    h = tmp_path / "bi.js"
    h.write_text(_DOM_CAPTURE + JS +
                 "\nbiSerial='S9';biName='skipjack';"
                 "renderBI({serial:'S9',os:'AsteroidOS',bat_cap:83,bat_status:'Charging',"
                 "bat_volt:3900000,bat_cycles:42,standby_measured:2.5});"
                 "console.log(JSON.stringify(global.__els['bi'].innerHTML));"
                 "\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    html = json.loads(r.stdout.strip().splitlines()[-1])
    assert "Cycles" in html and "42" in html, html[:300]
    assert "Standby" in html and "Voltage" in html


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_control_center_no_longer_carries_the_battery_section(tmp_path):
    """Battery detail moved to Battery Info; the Control Center System section
    stays but the Battery section is gone."""
    import json
    h = tmp_path / "ccbat.js"
    h.write_text(_DOM_CAPTURE + JS +
                 "\nccName='skipjack';ccSerial='S9';"
                 "renderCC({serial:'S9',kernel:'3.18',os:'AsteroidOS',bat_cap:83,bat_cycles:42});"
                 "console.log(JSON.stringify(global.__els['cc'].innerHTML));"
                 "\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    html = json.loads(r.stdout.strip().splitlines()[-1])
    assert "System" in html, "Control Center lost its System section"
    assert "Cycles" not in html, "Control Center still carries the moved battery detail"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_lifecycle_pill_shows_down_only_when_asserted(tmp_path):
    """The codename-adjacent pill appears only for an asserted state; a watch
    with no lifecycle claim shows nothing (no false 'off')."""
    import json
    h = tmp_path / "life.js"
    h.write_text(_DOM_STUBS + JS +
                 "\nconsole.log(JSON.stringify({down:mklife({lifecycle:'down'}),"
                 "worn:mklife({lifecycle:'worn'}),none:mklife({})}));"
                 "\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert "down" in out["down"] and "life down" in out["down"]
    assert "worn" in out["worn"] and "life worn" in out["worn"]
    assert out["none"] == "", "an unclaimed watch must show no lifecycle pill"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_reopening_a_panel_paints_instantly_from_cache(tmp_path):
    """A previously-opened panel must repaint from the cached payload straight
    away — no 'loading…' flash while the (possibly slow, over-SSH) fetch runs."""
    import json
    h = tmp_path / "cache.js"
    h.write_text(_DOM_CAPTURE + JS +
                 "\nglobal.fetch=()=>new Promise(()=>{});"          # never resolves
                 "\nccCache['S9']={kernel:'3.18',os:'AsteroidOS'};"  # seed a prior open
                 "openCC('S9','skipjack',{stopPropagation(){},clientX:5,clientY:5});"
                 "console.log(JSON.stringify(global.__els['cc'].innerHTML));"
                 "\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    html = json.loads(r.stdout.strip().splitlines()[-1])
    assert "System" in html and "3.18" in html, f"did not paint from cache: {html[:200]}"
    assert "loading" not in html, "showed a loading flash despite having a cache"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_reconcile_keys_rows_by_slot_and_hubs_by_location(tmp_path):
    """The row reconcile reuses a DOM node only when its key matches, so the
    key MUST be stable and unique per row — a watch row by its slot, a hub
    header by its location. A wrong key would reuse the wrong node (stale
    data) or never reuse (back to full flicker)."""
    import json
    h = tmp_path / "key.js"
    h.write_text(_DOM_STUBS + JS +
                 "\nconsole.log(JSON.stringify({"
                 "row:_rowKey('<tr class=\"wr\" id=\"wr-1-2.3:4\"><td>x</td></tr>'),"
                 "hub:_rowKey('<tr class=\"hub-hdr\"><td><span class=\"hl\">1-2.3</span></td></tr>')}));"
                 "\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["row"] == "row:1-2.3:4", out
    assert out["hub"] == "hub:1-2.3", out


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_spark_bars_scale_and_colour_by_metric_direction(tmp_path):
    """The live graph draws fixed-scale filled bars, coloured green→red toward
    the metric's bad end: a full battery (bad='low') is green, a high load
    (bad='high') is red. Newest sample is right-aligned."""
    import json
    h = tmp_path / "spark.js"
    h.write_text(_DOM_STUBS + JS +
                 "\ngraphData={bcap:[95],load:[3.9]};"
                 "const bat=spark('bcap',0,100,'low');"      # 95% battery -> green
                 "const load=spark('load',0,4,'high');"      # near-max load -> red
                 "const empty=spark('nope',0,100,'low');"
                 "console.log(JSON.stringify({bat,load,empty}));"
                 "\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    o = json.loads(r.stdout.strip().splitlines()[-1])
    assert "<svg" in o["bat"] and "<rect" in o["bat"], o["bat"]
    # hue: 120=green, 0=red. Full battery (bad=low, n=0.95) -> mostly green (hue>90).
    bhue = int(o["bat"].split("hsl(")[1].split(",")[0])
    lhue = int(o["load"].split("hsl(")[1].split(",")[0])
    assert bhue > 90, f"full battery should be green, hue={bhue}"
    assert lhue < 30, f"high load should be red, hue={lhue}"
    assert o["empty"] == "", "no samples yet must draw nothing"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_poll_interval_and_tag_follow_the_transport(tmp_path):
    """adb polls at 3s, SSH at 10s (a 3s poll can't keep up with an SSH
    round-trip), and the panel header shows which."""
    import json
    h = tmp_path / "poll.js"
    h.write_text(_DOM_STUBS + JS +
                 "\nconsole.log(JSON.stringify({"
                 "adbMs:panelPollMs({transport:'adb'}),sshMs:panelPollMs({transport:'ssh'}),"
                 "adbTag:pollTag({transport:'adb'}),sshTag:pollTag({transport:'ssh'})}));"
                 "\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    o = json.loads(r.stdout.strip().splitlines()[-1])
    assert o["adbMs"] == 3000 and o["sshMs"] == 10000, o
    assert "3s" in o["adbTag"] and "10s" in o["sshTag"] and "ssh" in o["sshTag"]


def test_stale_endpoint_and_paintstale_are_wired():
    """First open paints instantly from the fast /stale endpoint. It must be a
    registered route, and paintStale must call it."""
    from asteroid_docking_bay.webapp import _JSON_ROUTES
    stale = [r for r in _JSON_ROUTES if r[1].endswith("/stale")]
    assert stale and stale[0][2] == "watch.cc" and stale[0][3] == {"stale": True}, stale
    assert "function paintStale(" in JS
    assert "/stale'" in JS, "paintStale does not hit the /stale endpoint"


def test_action_buttons_pulse_on_click_for_instant_feedback():
    """A clicked action button (power toggle, cycle, wear) must give instant
    feedback while the command is in flight — pulseSelf(this) — since the state
    only updates on the next refresh cycle."""
    assert "function pulseSelf(" in JS
    # the persistent row toggles wire it
    assert JS.count("pulseSelf(this);") >= 3, "not all row toggles pulse on click"
    assert "pulseSelf(this);${pwrFn}" in JS, "power toggle lacks instant feedback"
    assert "pulseSelf(this);doCy(" in JS, "cycle button lacks instant feedback"
    assert "pulseSelf(this);doWear(" in JS, "wear button lacks instant feedback"


def test_failed_actions_flash_red():
    """A failed command flashes its element red 3× — the port toggle flashes
    the button, a refused mode switch flashes the connection pill."""
    assert "function flashFail(" in JS and "cmd-fail" in _WEB_TEMPLATE
    # port toggle: on confirmed===false, flash the clicked button
    assert "if(d.confirmed===false){flashFail(el)" in JS, "power toggle failure not flashed"
    # mode switch: on !ok, flash the row's connection pill
    assert "flashFail(connPill(serial))" in JS, "mode-switch failure not flashed"
    # the connection cell carries an id so the pill can be found
    assert 'id="conn-${esc(p.serial)}"' in JS


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_opening_a_panel_closes_the_others(tmp_path):
    """Only one floating window at a time — opening the Control Center while
    Battery Info is up must close Battery Info."""
    import json
    h = tmp_path / "one.js"
    h.write_text(_DOM_CAPTURE + JS +
                 "\nglobal.fetch=()=>new Promise(()=>{});"
                 "openBI('S9','sk',{stopPropagation(){},clientX:0,clientY:0});"
                 "const biBefore=biSerial;"
                 "openCC('S9','sk',{stopPropagation(){},clientX:0,clientY:0});"
                 "console.log(JSON.stringify({biBefore,biAfter:biSerial,ccAfter:ccSerial}));"
                 "\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    o = json.loads(r.stdout.strip().splitlines()[-1])
    assert o["biBefore"] == "S9", "Battery Info did not open"
    assert o["biAfter"] is None, "Battery Info stayed open when Control Center opened"
    assert o["ccAfter"] == "S9", "Control Center did not open"
