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
    h.write_text(_DOM_STUBS + JS +
                 f"\ntry{{const S={json.dumps(_SAMPLE)};render(S);render(S);"
                 f"console.log('RENDER_OK');}}"
                 f"catch(e){{console.error('THREW '+e);process.exit(1);}}\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0 and "RENDER_OK" in r.stdout, (
        f"render() threw when run headless:\n{r.stderr[:600]}")


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
