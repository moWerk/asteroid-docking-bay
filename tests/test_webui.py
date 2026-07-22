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
  innerHTML:'',textContent:'',value:'',querySelectorAll:()=>[],querySelector:()=>null,contains:()=>false,
  appendChild(){},removeChild(){},remove(){},setAttribute(){},getAttribute:()=>null,offsetHeight:100,offsetWidth:100};}
global.__h={};
global.document={getElementById:()=>el(),createElement:()=>el(),addEventListener(t,f){global.__h[t]=f;},body:el(),documentElement:el()};
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

    # Refresh folded into the Execute menu; needPwr is the last menuExecute arg.
    flags = dict(re.findall(r"menuExecute\(event,'([^']+)',[^)]*,(true|false)\)", html))
    assert flags, f"no menuExecute wiring found in rendered rows:\n{html[:400]}"
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
def test_smart_column_is_pills_with_the_cycle_as_the_untested_state(tmp_path):
    """Smart is a pill — green 'yes' when the port can switch power, red 'NO!'
    when it can't. Untested shows the power-cycle button in place of a bare '?',
    because the cycle IS the test. The Power column keeps only the on/off
    toggle; the standalone cycle icon is gone from it."""
    import json
    h = tmp_path / "smt.js"
    h.write_text(_DOM_STUBS + JS +
                 "\nconsole.log(JSON.stringify({"
                 "yes:mksmart({smart:true},'1-2:1',''),"
                 "no:mksmart({smart:false},'1-2:1',''),"
                 "unk:mksmart({smart:null},'1-2:1','')}));"
                 "\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert 'class="smt ppps"' in out["yes"] and ">ppps<" in out["yes"]
    assert 'class="smt no"' in out["no"] and "NO!" in out["no"]
    assert 'class="smt unk"' in out["unk"] and "doCy('1-2:1')" in out["unk"], out["unk"]
    assert "&#x21BA;" in out["unk"], "untested state must show the cycle glyph"
    # The cycle lives only in the smart cell now — not as a power-column icon.
    assert JS.count("doCy('") == 1, "doCy wired in more than one place — cycle not consolidated"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_battery_graph_dot_opens_battery_info_with_history(tmp_path):
    """The Stats battery-graph dot opens the same Battery Info panel as the
    battery pill — not a separate sparkline popup — and the panel carries the
    history chart at its foot when history exists."""
    import json
    # (a) the dot wires openBI, and the old openSpark popup is gone.
    strip = _WEB_TEMPLATE
    assert "openSpark" not in strip, "battery-graph dot still opens the old popup"
    h = tmp_path / "bihist.js"
    h.write_text(_DOM_CAPTURE + JS +
                 "\nbiSerial='S9';biName='sk';"
                 "biHist['S9']={points:[{ts:1,pct:90},{ts:2,pct:80},{ts:3,pct:70}],rate:0.5};"
                 "renderBI({bat_cap:80});"
                 "console.log(JSON.stringify(global.__els['bi'].innerHTML));"
                 "\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    html = json.loads(r.stdout.strip().splitlines()[-1])
    assert "Battery history" in html and "spark-svg" in html, "BI panel lost its history chart"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_stats_items_are_dots_and_the_age_trails_as_text(tmp_path):
    """Every stat icon is a dot — a glyph in a circle — for one visual language
    with the power dot and the charging circle. The last-seen age is NOT a pill
    or a dot; it trails the dots as plain text. No legacy icon spans survive."""
    import json
    h = tmp_path / "strip.js"
    h.write_text(_DOM_STUBS + JS +
                 "\nconsole.log(JSON.stringify({"
                 "charging:mkstrip({codename:'x',charging_active:true,serial:'S9'},24),"
                 "off:mkstrip({codename:'x',adb:null,last_live_ts:1000},24),"
                 "full:mkstrip({codename:'x',adb:'device',charge_status:'Full',serial:'S9'},24)}));"
                 "\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert 'class="sdot chg' in out["charging"], "charging op is not a dot"
    assert 'class="sdot dim spark"' in out["charging"], "sparkline is not a dot"
    # Conditional charge state sits last, after the always-present sparkline.
    assert out["charging"].index("sdot dim spark") < out["charging"].index("sdot chg"), \
        "the conditional charge dot must come after the battery-graph dot"
    assert 'class="sdot on"' in out["full"], "full-charge state is not a dot"
    # The charge dot opens Battery Info too — gauge, graph dot and charge dot
    # all lead to the same panel (spark dot + charge dot = two openBI here).
    assert out["full"].count("openBI") >= 2, "charge dot does not open Battery Info"
    # An untested wearability reads grey, not amber.
    assert 'class="sdot dim"' in out["off"], "untested wearability is not grey"
    assert 'class="lastseen"' in out["off"], "last-seen age is not trailing text"
    assert "spill" not in out["off"], "last-seen age is still a pill"
    # The old icon-span classes are gone everywhere.
    for html in out.values():
        assert "svgw" not in html and 'class="ib' not in html, f"legacy icon span left: {html}"


def test_pills_and_dots_share_one_height_token():
    """Every in-row pill and glyph-dot draws its height from one --pill-h token,
    so they line up; change it once and all follow. Pills stay inline-block so
    long content wraps to a second inner line instead of forcing the table wider
    than the viewport. (The orbit-eclipse toggle keeps its own fixed geometry.)"""
    assert "--pill-h:" in _WEB_TEMPLATE, "no shared pill-height token"

    def rule(sel):
        # The declaration block where `sel` starts a rule — not where it appears
        # inside a descendant selector like ".pcell .tgl".
        m = re.search(r"(?:^|[\n;}])\s*" + re.escape(sel) + r"\s*\{([^}]*)\}",
                      _WEB_TEMPLATE)
        assert m, f"no standalone rule for {sel}"
        return m.group(1)

    for sel in (".cbadge", ".sdot", ".smt", ".tgl"):
        assert "var(--pill-h)" in rule(sel), f"{sel} does not use the shared height token"
    for sel in (".cbadge", ".smt"):
        assert "inline-block" in rule(sel), f"{sel} is not inline-block — long content won't wrap"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_power_toggle_uses_the_orbit_eclipse_states(tmp_path):
    """The power toggle is the flat dot pill (tgl-on/tgl-off with a coloured
    dot + ON/OFF). Clicking an OFF toggle adds the animated .pending exec state
    and POSTs the on op for the port."""
    import json
    h = tmp_path / "tgl.js"
    h.write_text(_DOM_CAPTURE + JS + global_simple() +
                 f"\nconst S={json.dumps(_SAMPLE)};render(S);"
                 "const html=global.__els['tb'].innerHTML;"
                 # simulate a click on an OFF toggle (no 'tgl-on' class -> switch on)
                 "let url=null;global.fetch=(u,o)=>{url=u;return new Promise(()=>{});};"
                 "const tel={classList:{_s:new Set(),add(c){this._s.add(c);},remove(){},"
                 "toggle(){},contains(c){return this._s.has(c);}}};"
                 "pwrGo(tel,'1-2:2');"
                 "console.log(JSON.stringify({html,pending:tel.classList.contains('pending'),url}));"
                 "\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert 'class="tgl tgl-off"' in out["html"] or 'class="tgl tgl-on"' in out["html"], "not the flat toggle"
    assert "dot doff" in out["html"] or "dot don" in out["html"], "toggle dot missing"
    assert "tgl-spin" not in _WEB_TEMPLATE and 'content:"EXEC"' not in _WEB_TEMPLATE, "orbit toggle bits survive"
    assert "@keyframes tgldot" in _WEB_TEMPLATE, "no animated exec state"
    assert out["pending"] is True, "click did not add the exec state"
    assert out["url"] == "/api/on/1-2/2", f"click did not POST the on op: {out['url']}"


def test_menu_trigger_is_a_markerless_pill():
    """The row menu trigger spawns a panel like the badges/battery pills do, so
    it reads as one of them: labelled "menu", a pill, and no dropdown ▾ marker
    (which also stopped it wrapping to two lines in a narrow tiled window)."""
    assert ">menu</button>" in _WEB_TEMPLATE, "menu trigger lost its label or gained a marker"
    assert "&#9662;" not in _WEB_TEMPLATE and "▾" not in _WEB_TEMPLATE
    assert ".btn.ex{border-radius" in _WEB_TEMPLATE, "menu trigger is not pill-shaped"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_stats_dots_open_contextual_mini_menus(tmp_path):
    """The power dot opens a short Power-only menu; the wearability dot opens a
    Drain-test + Wear menu — the same builders as the full row menu, scoped."""
    import json
    assert "menuPwr(event," in JS, "power dot not wired to its menu"
    assert "menuWear(event," in JS, "wearability dot not wired to its menu"
    h = tmp_path / "dm.js"
    ev = ("{stopPropagation(){},currentTarget:{getBoundingClientRect:()=>"
          "({left:0,right:0,top:0,bottom:0})}}")
    h.write_text(_DOM_CAPTURE + JS +
                 f"\nmenuPwr({ev},'1-2:1',false,false,false,true,false);"
                 "const pwr=global.__els['menu'].innerHTML;"
                 f"menuWear({ev},'1-2:1',false,'S9',0);"
                 "const wear=global.__els['menu'].innerHTML;"
                 "console.log(JSON.stringify({pwr,wear}));\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert 'exgrp-hd">Power<' in out["pwr"] and "Reboot" in out["pwr"]
    assert "Workbench" not in out["pwr"], "power dot menu should be power-only"
    assert 'exgrp-hd">Drain test<' in out["wear"] and "Drain test" in out["wear"]
    assert 'exgrp-hd">Wear<' in out["wear"] and "menu-wear" in out["wear"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_execute_menu_folds_every_group_under_a_header(tmp_path):
    """The single Execute button opens one menu holding all former action
    buttons as grouped, indented headers — every option visible at once, no
    nested submenus. The fastboot variant swaps in the bootloader power group
    and drops Workbench/Wear (which need a booted watch)."""
    import json
    h = tmp_path / "ex.js"
    ev = ("{stopPropagation(){},currentTarget:{getBoundingClientRect:()=>"
          "({left:0,right:0,top:0,bottom:0})}}")
    h.write_text(_DOM_CAPTURE + JS +
                 f"\nmenuExecute({ev},'1-2:1',false,false,false,true,false,"
                 "'S9',false,'device','192.168.13.37',0,true);"
                 "const on=global.__els['menu'].innerHTML;"
                 f"menuExecute({ev},'1-2:1',true,false,false,true,false,"
                 "'S9',false,'fastboot','',0,true);"
                 "const fb=global.__els['menu'].innerHTML;"
                 "console.log(JSON.stringify({on,fb}));\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    on = out["on"]
    for hd in ("Refresh", "Power", "Flashing", "Workbench", "Wear"):
        assert f'class="exgrp-hd">{hd}<' in on, f"missing group header {hd}: {on[:200]}"
    # A representative item from each group survived the fold.
    for item in ("Re-identify", "Reboot", "Backup data", "Checkout", "Arm wear"):
        assert item in on, f"folded menu lost {item!r}"
    # Wear leads, Refresh trails; wear is the one button, the rest are text links.
    assert on.index('exgrp-hd">Wear<') < on.index('exgrp-hd">Power<'), "Wear not first"
    assert on.index('exgrp-hd">Refresh<') > on.index('exgrp-hd">Workbench<'), "Refresh not last"
    assert 'class="menu-wear' in on, "wear should stay a pink button"
    # Fastboot: bootloader power group in, watch-only groups out.
    fb = out["fb"]
    assert "Continue boot" in fb and 'class="exgrp-hd">Workbench<' not in fb
    assert 'class="exgrp-hd">Wear<' not in fb


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_workbench_menu_no_longer_carries_the_usb_ip(tmp_path):
    """The USB IP moved out of the menu — it lives in the Connection column's
    Network Center now, a better place to find it — so the workbench group must
    not repeat it (and still carries the USB-mode switch)."""
    import json
    h = tmp_path / "wb.js"
    h.write_text(_DOM_STUBS + JS +
                 "\nconst CAP=grpWorkbench('1-2:1','S9',false,'ssh','192.168.13.37');"
                 "console.log(JSON.stringify(CAP));\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    html = json.loads(r.stdout.strip().splitlines()[-1])
    assert "menu-ip" not in html and "192.168.13.37" not in html, "USB IP still in the menu"
    assert "Switch USB to ADB" in html, "workbench group lost its USB-mode switch"


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
def test_battery_gauge_fills_by_level_and_colours_only_when_connected(tmp_path):
    """The battery cell is a gauge: a fixed-width bar whose fill grows with the
    charge level and opens Battery Info on click. Connected → coloured fill (a
    mid-level reads amber .ok); disconnected → grey (.off) fill at the last
    level, a level without a colour claim."""
    import json
    h = tmp_path / "bp.js"
    h.write_text(_DOM_STUBS + JS +
                 "\nconsole.log(JSON.stringify({"
                 "live:mkbatCell({battery:60,serial:'S9',codename:'sk'},40,80),"
                 "off:mkbatCell({battery_cached:55,serial:'S9',last_live_ts:1000},40,80)}));"
                 "\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert 'class="batw ok"' in out["live"] and "width:60%" in out["live"], out["live"]
    assert "openBI('S9'" in out["live"] and "60%" in out["live"]
    assert 'class="batw off"' in out["off"] and "width:55%" in out["off"], "offline gauge not grey"
    assert "Charging" not in out["live"], "charge status should not repeat in the gauge"


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
def test_power_dot_is_the_first_stats_dot_coloured_by_state(tmp_path):
    """The power state is the first Stats dot now (same circle language as the
    other stats): green when the port is powered, grey for a confirmed
    graceful-down, orange when ambiguous (off with no down marker) — always
    shown, never blank. Worn stays a pink pill by the codename, not a dot."""
    import json
    h = tmp_path / "life.js"
    h.write_text(_DOM_STUBS + JS +
                 "\nconsole.log(JSON.stringify({"
                 "on:pdot({power:true}),"
                 "down:pdot({lifecycle:'down'}),"
                 "amb:pdot({}),"
                 "worn:mklife({lifecycle:'worn'}),"
                 "plain:mklife({power:true})}));"
                 "\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert 'class="sdot on"' in out["on"] and 'class="pwri"' in out["on"], "power icon missing"
    assert "&#9211;" not in out["on"], "still the Unicode glyph, not an icon"
    assert 'class="sdot dim"' in out["down"], "safely-down must read grey"
    assert 'class="sdot warn"' in out["amb"], "ambiguous power must read orange"
    assert out["amb"] != "", "the power dot is persistent — never blank"
    # Worn is a name pill; mklife no longer carries the power state at all.
    assert "life worn" in out["worn"] and "sdot" not in out["worn"]
    assert out["plain"] == "", "mklife carries only worn now, not the power state"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_boot_pill_shows_in_connection_column_and_outranks_no_link(tmp_path):
    """A triggered boot paints a white pulsing 'booting up' pill in the
    connection column, escalating to a red-flashing 'boot failed?' once the
    window lapses. Both carry positive evidence a boot is under way, so they
    outrank the generic not-enumerating / no-link messages that would otherwise
    show for a powered port with no adb."""
    import json
    h = tmp_path / "boot.js"
    h.write_text(_DOM_STUBS + JS +
                 "\nconst base={adb:null,power:true,connected:true,not_enumerating:true};"
                 "console.log(JSON.stringify({"
                 "booting:mkadbrow({...base,lifecycle:'booting'}),"
                 "bootfail:mkadbrow({...base,lifecycle:'bootfail'}),"
                 "plain:mkadbrow({...base,lifecycle:null})}));"
                 "\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert "life booting" in out["booting"] and "booting up" in out["booting"]
    assert "life bootfail" in out["bootfail"] and "boot failed?" in out["bootfail"]
    # 'boot failed?' is hedged (question mark) — it is a suspicion, not a verdict.
    assert out["bootfail"].count("?") >= 1
    # Neither boot pill lets the generic not-enumerating pill through (match the
    # visible label, not the word where it appears inside the boot tooltip).
    assert ">not enumerating<" not in out["booting"]
    assert ">not enumerating<" not in out["bootfail"]
    # With no boot claim, the same row still shows not-enumerating as before.
    assert ">not enumerating<" in out["plain"]


def test_column_order_is_the_ground_truth_order():
    """Columns run in the fleet's ground-truth order: the port everything
    originates from, its controls (power, smart), then the connection/battery
    state that leads over to the watch, then the watch itself, its stats, and
    actions last. The two blank leading headers are the tree glyph and the
    thumbnail."""
    m = re.search(r"<thead>.*?</thead>", _WEB_TEMPLATE, re.S)
    labels = [t for t in re.findall(r"<th[^>]*>([^<]*)</th>", m.group(0)) if t.strip()]
    # Port folds into the Power cell, so there is no separate Power header; the
    # blank header is the thumbnail.
    assert labels == ["Port", "Smart", "Connection",
                      "Watch", "Stats", "Battery", "Actions"], labels


def test_usb_preference_toggle_is_present_with_a_bullet_tooltip():
    """The situational adb/ssh preference lives as a third top-bar link with a
    tooltip spelling out the consequences in bullets."""
    assert 'id="usbpreflink"' in _WEB_TEMPLATE
    assert "onclick=\"toggleUsbPref()" in _WEB_TEMPLATE
    assert _WEB_TEMPLATE.count("•") >= 2, "tooltip must list consequences as bullets"
    assert "function toggleUsbPref(" in JS


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_render_labels_the_usb_preference_from_status(tmp_path):
    """render() mirrors data.usb_mode_preference onto the top-bar link — 'prefer
    SSH' when set to ssh, 'prefer ADB' otherwise."""
    import json
    h = tmp_path / "pref.js"
    h.write_text(_DOM_CAPTURE + JS + global_simple() +
                 "\nrender({hubs:[],usb_mode_preference:'ssh'});"
                 "const ssh=global.__els['usbpreflink'].textContent;"
                 "render({hubs:[],usb_mode_preference:'adb'});"
                 "const adb=global.__els['usbpreflink'].textContent;"
                 "console.log(JSON.stringify({ssh,adb}));"
                 "\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["ssh"] == "prefer SSH" and out["adb"] == "prefer ADB", out


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_powered_but_unconnected_says_no_link_not_a_cause(tmp_path):
    """A powered port with nothing electrically connected reads "no link" — a
    neutral statement of the observation. It must NOT say "not docked", which
    claims a specific cause (the plug was pulled) we cannot tell apart from a
    dead contact."""
    import json
    h = tmp_path / "nolink.js"
    h.write_text(_DOM_STUBS + JS +
                 "\nconsole.log(JSON.stringify(mkadbrow("
                 "{adb:null,power:true,connected:false})));"
                 "\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert ">no link<" in out, out
    assert "not docked" not in out, "still claims the plug was pulled"


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


def test_action_buttons_give_instant_click_feedback():
    """A clicked in-row control gives instant feedback while the command is in
    flight, since state only updates on the next refresh. The cycle icon pulses
    (pulseSelf); the power toggle shows the orbit-eclipse .pending spinner via
    pwrGo."""
    assert "function pulseSelf(" in JS
    assert "pulseSelf(this);doCy(" in JS, "cycle button lacks instant feedback"
    assert "function pwrGo(" in JS and "classList.add('pending')" in JS, \
        "power toggle lacks its in-flight pending state"
    assert "pwrGo(this," in JS, "power toggle not wired to pwrGo"


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
def test_a_mousedown_outside_an_open_panel_closes_it(tmp_path):
    """One document-level mousedown-capture handler enforces both rules at once:
    a click anywhere outside an open panel closes it, and since triggering
    another panel is itself an outside click, only one window is ever up. The
    open() functions must NOT carry their own close-the-others helper — the
    outside-click handler already covers that case (beroset: refactor, don't
    add). The panel must persist on mere hover-out, so no timer/leave close."""
    import json
    h = tmp_path / "one.js"
    h.write_text(_DOM_CAPTURE + JS +
                 "\nglobal.fetch=()=>new Promise(()=>{});"
                 # Open Battery Info, then fire the captured mousedown handler
                 # with a target that no panel contains (contains()=>false).
                 "openBI('S9','sk',{stopPropagation(){},clientX:0,clientY:0});"
                 "global.__els['bi'].style.display='block';"
                 "const biBefore=biSerial;"
                 "global.__h.mousedown({target:el()});"
                 "console.log(JSON.stringify({biBefore,biAfter:biSerial,"
                 "hasHandler:typeof global.__h.mousedown}));"
                 "\nprocess.exit(0);\n")
    r = subprocess.run(["node", str(h)], capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr[:400]
    o = json.loads(r.stdout.strip().splitlines()[-1])
    assert o["hasHandler"] == "function", "no document mousedown-capture handler"
    assert o["biBefore"] == "S9", "Battery Info did not open"
    assert o["biAfter"] is None, "outside mousedown did not close Battery Info"
    # The refactor's whole point: no per-open close helper, no hover-close.
    assert "closePanels" not in JS, "openers still call an added close helper"
    assert "ccLeave" not in JS and "onmouseleave" not in _WEB_TEMPLATE, (
        "a hover-out close path survives — panels must persist until a click")
