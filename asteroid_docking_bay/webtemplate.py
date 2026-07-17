# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 Timo Könnecke (moWerk) <mo@mowerk.net>
# SPDX-FileCopyrightText: 2023 Ed Beroset <beroset@ieee.org>
"""The single-page web UI (HTML/CSS/JS), served verbatim by webapp."""

from __future__ import annotations

_WEB_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>asteroid-docking-bay</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Archivo+Narrow:wght@400;700&display=swap" rel="stylesheet">
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:#0d1117;color:#c9d1d9;font:13px/1.6 'Cascadia Code','Fira Mono',monospace;padding:24px}
    h1{font:700 22px/1.4 'Archivo Narrow',sans-serif;color:#58a6ff;margin-bottom:4px;letter-spacing:1px}
    .hdim{color:#30363d;font-weight:400;font-size:16px;letter-spacing:3px}
    .htxt{letter-spacing:3px}
    .meta{color:#6e7681;font-size:11px;margin-bottom:20px}
    /* Fixed top bar: left/right pinned so varying string lengths (the
       update stamp) can never reposition their neighbours. */
    .topbar{display:flex;justify-content:space-between;color:#6e7681;font-size:11px;margin-bottom:2px}
    .berr{color:#f85149;font-size:12px;margin-bottom:6px}
    .berr:empty{display:none}
    .alert{color:#d29922;font-size:12px;margin-bottom:6px;min-height:1.2em}
    .alert a{color:#58a6ff;text-decoration:none}
    .scrn{cursor:pointer;color:#d29922;margin-left:6px;animation:bpulse 1.4s infinite;-webkit-tap-highlight-color:transparent}
    .scrn:hover{color:#f0b429}
    .hdr{text-align:center}
    /* Control Center overlay */
    .cn{cursor:pointer;border-bottom:1px dotted #4d5561}
    .cn:hover{color:#58a6ff;border-bottom-color:#58a6ff}
    .cc{position:fixed;z-index:100;display:none;width:auto;min-width:340px;max-width:94vw;background:#161b22;border:1px solid #30363d;border-radius:8px;box-shadow:0 10px 34px rgba(0,0,0,.6);font-size:12px;overflow:hidden}
    .cc-cols{display:flex;flex-wrap:wrap}
    .cc-col{flex:1 1 210px;min-width:200px}
    .cc-sec{padding:8px 14px}
    .cc-sech{font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:.6px;border-bottom:1px solid #21262d;padding-bottom:3px;margin-bottom:5px}
    .cc-hd{padding:8px 30px 8px 12px;background:#0d1117;border-bottom:1px solid #30363d;font-weight:700;color:#58a6ff;position:relative}
    .cc-hd .dim{font-weight:400}
    .cc-x{position:absolute;right:10px;top:6px;cursor:pointer;color:#6e7681;font-weight:400;font-size:16px;line-height:1}
    .cc-x:hover{color:#fff}
    .cc-grid{display:grid;grid-template-columns:auto 1fr;gap:3px 10px}
    .cc-act.mini{width:auto;flex:1;padding:6px}
    .cc-k{color:#6e7681}
    .cc-v{color:#c9d1d9;text-align:right;font-variant-numeric:tabular-nums;word-break:break-all}
    .cc-tgls{display:flex;flex-wrap:wrap;gap:8px;padding:2px 12px 10px}
    .cc-tgl{flex:1;padding:7px 4px;border-radius:6px;border:1px solid #30363d;background:transparent;cursor:pointer;font:inherit;color:#8b949e}
    .cc-tgl.on{border-color:#3fb950;color:#3fb950}
    /* Screen/demo-mode toggle when active: bright warning yellow (not the
       benign green of wifi/bt) — a forced-on screen is a drain, so its ON
       state should read as an alert. Off state is the plain greyed pill. */
    .cc-tgl.scrnon{border-color:#f0b429;color:#f0b429;background:rgba(240,180,41,.15);font-weight:700}
    .cc-tgl.busy{opacity:.5;cursor:progress}
    .cc-tgl:hover{background:#0d1117}
    .cc-acts{padding:0 12px 12px}
    .cc-act{width:100%;padding:8px;border-radius:6px;border:1px solid #388bfd;background:transparent;color:#388bfd;cursor:pointer;font:inherit}
    .cc-act:hover{background:#0d1f3a}
    .cc-act.done{border-color:#3fb950;color:#3fb950}
    /* Row action floating menus */
    .btn.pw{border-color:#f0883e;color:#f0883e}
    .btn.pw:hover{background:#2a1a0e}
    .menu{position:fixed;z-index:110;display:none;min-width:172px;background:#161b22;border:1px solid #30363d;border-radius:7px;box-shadow:0 10px 30px rgba(0,0,0,.6);padding:5px}
    .menu-item{display:block;width:100%;text-align:left;padding:6px 10px;margin:1px 0;border-radius:5px;border:1px solid transparent;background:transparent;color:#c9d1d9;cursor:pointer;font:inherit;white-space:nowrap}
    .menu-item:hover:not(:disabled){filter:brightness(1.4);border-color:#30363d}
    .menu-item:disabled{opacity:.38;cursor:default}
    /* Per-action accent: coloured label on a faint band of the same hue, to
       keep the colourful feel the flat buttons had. */
    .menu-item.ch{color:#3fb950;background:rgba(63,185,80,.07)}
    .menu-item.dr{color:#d29922;background:rgba(210,153,34,.07)}
    .menu-item.po{color:#f85149;background:rgba(248,81,73,.07)}
    .menu-item.rb{color:#f0883e;background:rgba(240,136,62,.07)}
    .menu-item.bl{color:#d2a8ff;background:rgba(210,168,255,.07)}
    .menu-item.wbx{color:#a371f7;background:rgba(163,113,247,.07)}
    .menu-item.info{color:#58a6ff;background:rgba(88,166,255,.07)}
    .menu-sep{height:1px;background:#30363d;margin:4px 2px}
    .menu-hd{padding:3px 10px 5px;font-size:10px;color:#6e7681}
    #toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%) translateY(20px);background:#161b22;border:1px solid #30363d;color:#c9d1d9;padding:9px 16px;border-radius:7px;font-size:12px;opacity:0;pointer-events:none;transition:.2s;z-index:200}
    #toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
    /* Watch product-photo thumbnail + click-to-enlarge overlay */
    td.thumb{width:34px;padding:2px 2px 2px 0}
    .wthumb{width:30px;height:30px;object-fit:contain;cursor:pointer;vertical-align:middle;border-radius:4px;transition:transform .1s}
    .wthumb:hover{transform:scale(1.12)}
    .svgi{width:15px;height:15px;fill:currentColor;vertical-align:-2px}
    td.stats{min-width:52px;white-space:nowrap}   /* >=2 icons wide so the base pair never wraps to two rows */
    td.stats .strip{margin-left:0}
    .strip{margin-left:8px;display:inline-flex;gap:7px;align-items:center;vertical-align:middle}
    .strip .svgw{cursor:default;line-height:0}
    .strip .ib{font-size:12px;line-height:1;font-weight:700}
    .strip .svgw.spark{cursor:pointer}
    .spark-hd{padding:6px 10px;font-size:11px;font-weight:700;white-space:nowrap}
    .spark-svg{display:block;padding:2px 8px 8px;background:#0d1117}
    .wimg-bg{position:fixed;inset:0;z-index:119;background:rgba(0,0,0,.55);display:none}
    .wimg{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);z-index:120;display:none;
          background:#161b22;border:1px solid #30363d;border-radius:10px;
          box-shadow:0 12px 40px rgba(0,0,0,.6);padding:14px;max-width:94vw;max-height:92vh;overflow:auto}
    .wimg-hd{display:flex;justify-content:space-between;align-items:baseline;gap:20px;margin-bottom:10px;
             color:#58a6ff;font-weight:700}
    .wimg-hd .dim{font-weight:400;font-size:11px}
    .wimg-x{cursor:pointer;color:#6e7681;font-size:18px;line-height:1}
    .wimg-x:hover{color:#fff}
    /* Product photo (left) and live screenshot (right) side by side at one
       shared height, so both read as the same size whatever the screen aspect. */
    .wimg-body{display:flex;gap:18px;align-items:flex-start;flex-wrap:nowrap;justify-content:center}
    .wimg-body img.prod{height:230px;width:auto;max-width:44vw;object-fit:contain}
    .wimg-shot{height:230px;width:auto;max-width:44vw;object-fit:contain;background:#000}
    .wimg-cap{color:#6e7681;font-size:10px;text-transform:uppercase;letter-spacing:.5px;text-align:center;margin-top:5px}
    /* Fluid: columns follow the page width with a minimal content margin, so
       the table always fits the viewport (no forced horizontal scroll). Column
       positions may shift slightly with string length — that's fine. */
    .tblwrap{overflow-x:auto}
    table{width:100%;border-collapse:collapse}
    th{color:#6e7681;text-align:left;padding:5px 12px;border-bottom:1px solid #21262d;font-size:11px;text-transform:uppercase;letter-spacing:1px;font-weight:normal}
    th:first-child,td.tc{width:22px;padding-right:0}
    td{padding:7px 8px;border-bottom:1px solid #161b22;vertical-align:middle}
    .wr:hover td{background:#161b22}
    .hub-hdr td{background:#0d1420;color:#6e7681;padding:9px 12px 4px;border-top:1px solid #21262d;border-bottom:1px solid #21262d;font-size:11px;letter-spacing:1px}
    .hub-hdr:first-child td{border-top:none;padding-top:0}
    .hl{color:#58a6ff;font-weight:bold;margin-right:8px}
    td.tc{color:#30363d;font-size:12px;user-select:none}
    tr.empty td{color:#6e7681}
    tr.empty:hover td{background:#0a0d13}
    .on{color:#3fb950}.off{color:#6e7681}.warn{color:#d29922}.err{color:#f85149}.dim{color:#6e7681}
    .stale{color:#a1793a}.stale .agec{opacity:.7;font-size:10px}
    .shot-stale{opacity:.55;filter:grayscale(.3)}
    tr.justplugged>td{animation:plug 2s ease-out}
    @keyframes plug{0%{background:rgba(31,111,235,.4)}100%{background:transparent}}
    .wimg-shot.shape-round{border-radius:50%}.wimg-shot.shape-rect{border-radius:4px}
    .cc.stale-cc{border-color:#7a5b1e}.cc.stale-cc .cc-hd{background:#241d0e}
    .dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;vertical-align:middle}
    .don{background:#3fb950}.doff{background:#30363d}
    /* Connection-column badges for the abnormal USB modes, so a watch sitting
       in the bootloader or SSH/developer mode stands out from a normal ADB row. */
    .cbadge{display:inline-block;padding:1px 7px;border-radius:10px;font-size:11px;border:1px solid;vertical-align:middle}
    .cbadge.fb{border-color:#f0883e;color:#f0883e}
    .cbadge.ssh{border-color:#d29922;color:#d29922;cursor:pointer}
    .cbadge.ssh:hover{background:#2a2113}
    .tgl{display:inline-flex;align-items:center;gap:4px;background:none;border:1px solid;padding:3px 9px 3px 6px;border-radius:20px;cursor:pointer;font:12px monospace;vertical-align:middle;margin-right:3px;touch-action:manipulation;-webkit-tap-highlight-color:transparent;transition:background .12s,transform .12s}
    .tgl-on{border-color:#3fb950;color:#3fb950}.tgl-on:hover{background:#0f2a18}
    .tgl-off{border-color:#30363d;color:#6e7681}.tgl-off:hover{background:#161b22}
    .tgl:active{transform:scale(.92);transition:transform 55ms ease-out}
    .ico{background:none;border:1px solid #30363d;color:#6e7681;padding:2px 6px;border-radius:4px;cursor:pointer;font:13px monospace;vertical-align:middle;touch-action:manipulation;-webkit-tap-highlight-color:transparent;transition:background .12s,transform .12s}
    .ico:hover{background:#21262d;color:#c9d1d9}
    .ico:active{transform:scale(.88);transition:transform 55ms ease-out}
    .tgl:disabled,.ico:disabled{opacity:.35;cursor:default;pointer-events:none}
    .btn{background:none;color:#c9d1d9;border:1px solid #30363d;padding:3px 9px;border-radius:4px;cursor:pointer;font:12px monospace;margin-right:3px;touch-action:manipulation;-webkit-tap-highlight-color:transparent;transition:background .12s,transform .12s}
    .btn:hover{background:#21262d}
    .btn:active{transform:scale(.92);transition:transform 55ms ease-out}
    .fl{border-color:#58a6ff;color:#58a6ff}.fl:hover{background:#111d2e}
    .ch{border-color:#3fb950;color:#3fb950}.ch:hover{background:#0f2a18}
    .ht{border-color:#6e7681;color:#6e7681}.ht:hover{background:#1c1c1c}
    .hcut{border-color:#f85149;color:#f85149}.hcut:hover{background:#2a0d0b}
    .hrb{border-color:#d29922;color:#d29922}.hrb:hover{background:#2a2113}
    .hbl{border-color:#58a6ff;color:#58a6ff}.hbl:hover{background:#111d2e}
    .btn:disabled{opacity:.35;cursor:default;pointer-events:none}
    .btn.dr{border-color:#388bfd;color:#388bfd}
    .btn.wb{border-color:#bc8cff;color:#bc8cff}.btn.wb:hover{background:#1d1430}
    .btn.ob{border-color:#1f6b39;color:#2c8a4c}.btn.ob:hover{background:#0d1f13}
    .hidebtn{color:#6e7681;text-decoration:none;font-size:15px;line-height:1;margin-left:6px;cursor:pointer;vertical-align:middle}
    .hidebtn:hover{color:#fff}
    tr.hiddenrow td,.wr.excl td{opacity:.5}
    .lr td{padding:0 12px 8px}
    .log{display:none;background:#010409;border:1px solid #21262d;border-radius:4px;padding:10px;font-size:12px;color:#8b949e;max-height:200px;overflow-y:auto;white-space:pre-wrap;word-break:break-all}
    .log.show{display:block}
    @keyframes bpulse{0%,100%{opacity:1}50%{opacity:.18}}
    @keyframes rpulse{0%,100%{background:transparent}50%{background:rgba(88,166,255,.06)}}
    .wr.refreshing td{animation:rpulse 1.1s ease-in-out infinite}
    .wr.refreshing:hover td{background:transparent!important;animation:rpulse 1.1s ease-in-out infinite}
    .btn-ref.pulsing{animation:bpulse .85s ease-in-out infinite!important;border-color:#58a6ff!important;color:#58a6ff!important}
    @keyframes pwrwarn{0%,100%{background:transparent}40%{background:rgba(248,81,73,.12)}}
    .wr.pwr-warn td{animation:pwrwarn 1.8s ease-in-out 2}
    /* Phones: stack each row into a slim card — one labelled line per field —
       instead of a wide table that scrolls sideways. Column order is fixed, so
       the field labels come from :nth-child; no markup change needed. */
    @media (max-width:720px){
      /* One card per screen is expected, so size up for legibility and touch —
         desktop's 11-13px is unreadable on a phone. */
      body{padding:12px;font-size:16px}
      .topbar,.meta{font-size:13px}
      .tblwrap{overflow-x:visible}
      table,tbody,tr,td{display:block;width:auto}
      thead{display:none}
      .hub-hdr td{padding:14px 4px 4px;font-size:13px}
      .wr{border:1px solid #21262d;border-radius:8px;margin:0 0 12px;padding:4px 14px}
      .wr:hover td{background:transparent}
      .wr td{border:none;padding:9px 0;display:flex;justify-content:space-between;
             align-items:center;gap:14px;text-align:right;font-size:16px}
      .wr td.tc{display:none}                                   /* tree is meaningless when stacked */
      .wr td:nth-child(2){display:block;float:left;margin:8px 12px 0 0;padding:0;border:none}
      .wr td:nth-child(2) .wthumb{width:44px;height:44px}       /* thumb beside the title */
      .wr td:nth-child(3){display:block;text-align:left;font-weight:700;font-size:20px;
                          padding:12px 0;border-bottom:1px solid #161b22;overflow:hidden}
      .wr td:nth-child(4){clear:both}                            /* fields start below the thumb */
      .wr td.stats:empty{display:none}                           /* no stats read yet → no blank row */
      .wr td:nth-child(4)::before{content:"Stats"}
      .wr td:nth-child(5)::before{content:"Port"}
      .wr td:nth-child(6)::before{content:"Power"}
      .wr td:nth-child(7)::before{content:"Smart"}
      .wr td:nth-child(8)::before{content:"Connection"}
      .wr td:nth-child(9)::before{content:"Battery"}
      .wr td::before{color:#8b949e;font-size:13px;text-transform:uppercase;
                     letter-spacing:.5px;flex:none;font-weight:400}
      .wr td:nth-child(10){display:block;text-align:left;padding-top:10px}  /* actions span the card */
      /* Bigger, tappable controls */
      .wr .btn,.wr .tgl,.wr .ico{font-size:15px;padding:9px 13px;margin:3px 6px 3px 0}
      .wr .cbadge,.wr .scrn{font-size:14px;padding:3px 9px}
      .wr .dot{width:9px;height:9px}
      .lr td{padding:0}
    }
  </style>
</head>
<body>
  <div class="topbar"><span id="ts">loading&hellip;</span><span id="ver"></span></div>
  <div id="berr" class="berr"></div>
  <div id="alert" class="alert"></div>
  <div class="hdr">
  <h1><span class="hdim">&#x2728;  &#x22C6;  &#x02DA; </span>&#x2726;<span class="htxt">  asteroid-docking-bay  </span>&#x2726;<span class="hdim"> &#x02DA;  &#x22C6;  &#x2728;</span></h1>
  <p class="meta"><a href="#" id="histlink" onclick="toggleHistory();return false" style="color:#388bfd;text-decoration:none">show drain history</a> &nbsp;&middot;&nbsp; <a href="#" id="hidlink" onclick="toggleShowHidden();return false" style="color:#6e7681;text-decoration:none">show all ports</a></p>
  </div>
  <div class="tblwrap">
  <table>
    <thead><tr>
      <th></th><th></th><th>Watch</th><th>Stats</th><th>Port</th><th>Power</th><th>Smart</th>
      <th>Connection</th><th>Battery</th><th>Actions</th>
    </tr></thead>
    <tbody id="tb"></tbody>
  </table>
  </div>
  <div id="hist" style="display:none"></div>
  <div id="cc" class="cc" onmouseleave="ccLeave()" onmouseenter="ccEnter()"></div>
  <div id="menu" class="menu"></div>
  <div id="wimg-bg" class="wimg-bg" onclick="closeWatchImg()"></div>
  <div id="wimg" class="wimg"></div>
<script>
const srcs={};
const chargeEnd={};
let countdownRunning=false;
let showHidden=false;
const refreshing=new Set();
// Serials seen enumerated on the last render, to flash a row when a watch is
// freshly plugged in. firstStatus suppresses the flash on the initial load.
let seenSerials=new Set();
let firstStatus=true;
function mkhide(slot,excluded){
  return `<a href="#" class="hidebtn" onclick="doHidePort('${slot}');return false" title="${excluded?'un-hide this row':'hide this row'}">${excluded?'&#x2295;':'&#x2296;'}</a>`;
}
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')}
function mkpwr(v){return v===true?'<span class="dot don"></span><span class="on">ON</span>':v===false?'<span class="dot doff"></span><span class="off">OFF</span>':'<span class="dim">---</span>'}
function mksmt(v){return v===true?'<span class="on">yes</span>':v===false?'<span class="err">NO!</span>':'<span class="warn">?</span>'}
function mkbat(v,lo,hi){
  if(v==null)return '<span class="dim">&mdash;</span>';
  const cls=v<lo?'err':v<=hi?'on':'dim';
  return `<span class="${cls}">${v}%</span>`;
}
function fmtAge(ts){
  // Compact "how long ago" for a last-live timestamp (seconds since epoch).
  if(!ts)return '';
  const s=Math.max(0,Math.floor(Date.now()/1000-ts));
  if(s<3600)return Math.floor(s/60)+'m';
  if(s<86400)return Math.floor(s/3600)+'h';
  return Math.floor(s/86400)+'d';
}
function mkbatCell(p,lo,hi){
  // Prefer the live reading; when the watch is off the bus fall back to the
  // last-seen value shown stale (amber) with its age, not a blank cell.
  if(p.battery!=null)return mkbat(p.battery,lo,hi);
  if(p.battery_cached!=null){
    const age=fmtAge(p.last_live_ts);
    return `<span class="stale" title="watch off the bus — last reading${age?' '+age+' ago':''}">${p.battery_cached}%<span class="agec">${age?' '+age:''}</span></span>`;
  }
  return '<span class="dim">&mdash;</span>';
}
function mkthumb(p){
  // Product photo thumbnail; removes itself if the watch has no image (404).
  if(!p.codename)return '';
  const g=p.geometry||{};
  return `<img class="wthumb" loading="lazy" alt="" src="/api/watch-image/${encodeURIComponent(p.codename)}" onerror="this.remove()" onclick="openWatchImg('${esc(p.codename)}','${esc(p.serial||'')}',event,${g.round?1:0},'${g.resolution?esc(g.resolution):''}')">`;
}
const ICONS={watch:'<path d=\"M127.9 376c0-2 .7-4 2.2-5.5 3.1-3.2 8.1-3.3 11.3-.2 20.9 20 46.8 30.8 79.3 32.8 19 1.2 27.1 5.8 35 10.3 9.3 5.3 18.9 10.7 54.2 10.7 71.7 0 122-59.2 122-132v-56c0-24.7-3-48.9-16.1-69.8-12.8-20.4-26.9-37-48.3-47.9-3.9-2-5.5-6.8-3.5-10.8 2-3.9 6.8-5.5 10.8-3.5 24 12.2 40.2 30.8 54.6 53.6 14.8 23.5 18.5 50.6 18.5 78.3v56c0 81.6-57.5 148-138 148-39.4 0-51.4-6.8-62-12.8-7.2-4.1-12.8-7.3-28.2-8.2-36.4-2.3-65.6-14.4-89.3-37.2-1.6-1.6-2.5-3.7-2.5-5.8z\"/><path d=\"M272.7 402c0-.4 0-.9.1-1.3.7-4.4 4.8-7.3 9.2-6.6 35.5 5.8 66.1-2.4 88.5-23.9 3.2-3.1 8.3-2.9 11.3.2 3.1 3.2 2.9 8.3-.2 11.3-26.2 25.1-61.5 34.8-102.1 28.1-4-.6-6.8-4-6.8-7.8zM64 292v-56c0-27.7 3.8-54.8 18.5-78.3 14.3-22.8 30.6-41.4 54.6-53.6 3.9-2 8.8-.4 10.8 3.5s.4 8.8-3.5 10.8c-21.4 10.9-35.5 27.5-48.3 47.9-13.2 20.8-16.2 45-16.2 69.7v56c0 34.8 9 70.1 38.8 96.9 30.3 27.4 71 43.1 111.6 43.1 4.4 0 8 3.6 8 8s-3.6 8-8 8c-44.5 0-89-17.2-122.3-47.2-33.1-29.9-44-69.5-44-108.8z\"/><path d=\"M375.3 129c-1.9.6-3.9 1-6.1 1-10.5 0-19-8.5-19-19s8.5-19 19-19c5.7 0 10.7 2.4 14.2 6.3-3-19.4-19.8-34.3-40-34.3h-175c-19.6 0-36.1 14-39.8 32.7 3.4-3 7.8-4.7 12.6-4.7 10.5 0 19 8.5 19 19s-8.5 19-19 19c-1.5 0-2.9-.2-4.3-.5 7.4 8.9 18.8 14.5 31.5 14.5h175c12.9 0 24.6-5.8 31.9-15zm-98.1-25c0-14.9 12.1-27 27-27s27 12.1 27 27-12.1 27-27 27c-14.7 0-27-12.1-27-27z\"/>',batterydead:'<path d=\"M384 144H80c-17.6 0-32 14.4-32 32v160c0 17.6 14.4 32 32 32h304c17.6 0 32-14.4 32-32V176c0-17.6-14.4-32-32-32zm16 192c0 8.8-7.2 16-16 16H80c-8.8 0-16-7.2-16-16V176c0-8.8 7.2-16 16-16h304c8.8 0 16 7.2 16 16v160zm32-135.4v110.8c19.1-11.1 32-31.7 32-55.4s-12.9-44.3-32-55.4z\"/>',flash:'<path d=\"M302.7 64 143 288h95.8l-29.5 160L369 224h-95.8l29.5-160z\"/>',moon:'<path d=\"M246.9 64c-12.6 1.4-24.9 4-36.6 7.7C132.4 96.4 76 169.3 76 255.4 76 361.8 162 448 268.2 448c58.7 0 111.2-26.4 146.5-67.9 8.1-9.5 15.2-19.8 21.4-30.8-11.4 2.8-23.1 4.5-35 5.1-2.9.1-5.9.2-8.8.2-48.4 0-94-18.9-128.2-53.2-34.3-34.3-53.1-80-53.1-128.5 0-27.6 6.1-54.3 17.7-78.5 4.9-10.7 11-20.9 18.2-30.4z\"/>',trend:'<path d=\"M472 128H360c-4.4 0-8 3.6-8 8s3.6 8 8 8h92L287.6 308.4l-83.9-84c-1.5-1.5-3.5-2.3-5.7-2.3-2.1 0-4.2.8-5.7 2.3L34.1 382.6c-1.6 1.6-2.1 3.7-2.1 5.9 0 2.1.6 3.9 2.1 5.5 1.6 1.6 3.6 2.3 5.7 2.3 2 0 4.1-.8 5.7-2.3L198 241.3l83.9 84c3.1 3.1 8.2 3.1 11.3 0L464 156v92c0 4.4 3.6 8 8 8s8-3.6 8-8V136c0-4.4-3.6-8-8-8z\"/>'};
function svgicon(n){return `<svg class="svgi" viewBox="0 0 512 512">${ICONS[n]}</svg>`;}
function mkstrip(p,wearH){
  let out='';
  // 1. wearable verdict from the last drain test, or a "?" if never tested.
  const dl=p.drain_last;
  if(dl&&dl.est_h!=null){
    const ok=dl.est_h>=wearH;
    const when=new Date(dl.ts*1000).toLocaleDateString();
    const tip=`holds ~${fmtDur(dl.est_h)} standby (100&rarr;15%, drain test ${when})`+(ok?' — wearable':` — below ${wearH}h: battery swap candidate`);
    out+=`<span class="svgw ${ok?'on':'err'}" title="${tip}">${svgicon(ok?'watch':'batterydead')}</span>`;
  }else if(p.codename){
    out+=`<span class="ib dim" title="never drain-tested — run a drain test to rate standby life">?</span>`;
  }
  // 2. watch-side charge state (live only) — delivered-power ground truth.
  if(p.adb==='device'&&p.charge_status){
    const cs=p.charge_status;
    if(cs==='Charging')out+=`<span class="svgw on" title="charging (delivered power confirmed)">${svgicon('flash')}</span>`;
    else if(cs==='Full')out+=`<span class="ib on" title="battery full">&#10003;</span>`;
    else if(cs==='Discharging')out+=`<span class="ib err" title="DISCHARGING while docked — on ADB but not taking charge (dirty contact / bad cable)">&#8595;</span>`;
  }
  // 3. sparkline launcher — click for the battery timeline (click, not hover).
  if(p.serial)out+=`<span class="svgw dim spark" title="battery history — click for the timeline" onclick="openSpark('${p.serial}','${esc(p.codename||'')}',event)">${svgicon('trend')}</span>`;
  // 4. last-seen age when the watch is off the bus.
  if(p.adb!=='device'&&p.last_live_ts)out+=`<span class="ib dim" title="last live ${fmtAge(p.last_live_ts)} ago">&#8226;${fmtAge(p.last_live_ts)}</span>`;
  return out?`<span class="strip">${out}</span>`:'';
}
function sparkSvg(pts){
  const W=260,H=90,pad=6;
  const ts=pts.map(p=>p.ts),t0=Math.min(...ts),t1=Math.max(...ts),tr=(t1-t0)||1;
  const x=t=>pad+(t-t0)/tr*(W-2*pad),y=v=>pad+(100-v)/100*(H-2*pad);
  const d=pts.map((p,i)=>(i?'L':'M')+x(p.ts).toFixed(1)+' '+y(p.pct).toFixed(1)).join(' ');
  return `<svg class="spark-svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}"><path d="${d}" fill="none" stroke="#58a6ff" stroke-width="1.5"/></svg>`;
}
function openSpark(serial,name,ev){
  ev.stopPropagation();
  openMenu(ev,`<div class="spark-hd">${esc(name)} <span class="dim">loading&hellip;</span></div>`);
  fetch('/api/watch/'+encodeURIComponent(serial)+'/timeline').then(r=>r.json()).then(d=>{
    const m=document.getElementById('menu');
    const pts=(d&&d.points)||[];
    if(pts.length<2){m.innerHTML=`<div class="spark-hd">${esc(name)} <span class="dim">no history yet — readings accrue as it's checked/drained</span></div>`;placeMenu();return;}
    m.innerHTML=`<div class="spark-hd">${esc(name)} battery history`+(d.rate?` <span class="dim">~${(+d.rate).toFixed(2)}%/h standby</span>`:'')+`</div>`+sparkSvg(pts);
    placeMenu();   // reposition now the real (larger) chart size is known
  }).catch(()=>{});
}
function mkport(p){
  let s = p.socket!=null
    ? `<b style="color:#c9d1d9">socket ${p.socket}</b> <span class="dim" style="font-size:10px">p${p.port}</span>`
    : `<span class="dim">p${p.port}</span>`;
  if(p.excluded) s = `<span class="err" title="${esc(p.excluded)}">avoid</span> ` + s;
  return s;
}
const AOSLOGO='<svg viewBox="0 0 2000 2000" width="13" height="13" style="vertical-align:-2px;margin-right:5px" shape-rendering="crispEdges" xmlns="http://www.w3.org/2000/svg"><defs><rect id="T" width="2" height="2"/></defs><g transform="matrix(100 100 -100 100 1000 0)"><g><use href="#T" style="fill:#be3729"/><use href="#T" id="b" x="2" style="fill:#dc2919"/><use href="#T" id="c" x="4" style="fill:#e54b3a"/><use href="#T" id="d" x="6" style="fill:#e56934"/><use href="#T" id="e" x="8" style="fill:#e57c21"/></g><g transform="translate(-2,2)"><use href="#b"/><use href="#c"/><use href="#T" id="f" x="10" style="fill:#e58a21"/></g><g transform="translate(-4,4)"><use href="#c"/><use href="#e"/><use href="#T" id="g" x="12" style="fill:#f19a11"/></g><g transform="translate(-6,6)"><use href="#d"/><use href="#e"/><use href="#f"/><use href="#T" id="h" x="14" style="fill:#f0ae0e"/></g><g transform="translate(-8,8)"><use href="#e"/><use href="#f"/><use href="#g"/><use href="#h"/><use href="#T" x="16" style="fill:#f0c30e"/></g></g></svg>';
function mkadb(adb,fbprod,os){
  if(adb==='device'){
    if(os==='asteroidos')return `${AOSLOGO}<span class="on" title="AsteroidOS on ADB">ADB</span>`;
    if(os&&os!=='unknown')return `<span class="on" title="${esc(os)} on ADB">ADB <span class="dim">${esc(os)}</span></span>`;
    return '<span class="on">ADB</span>';
  }
  if(adb==='ssh')return `${os==='asteroidos'?AOSLOGO:''}<span class="cbadge ssh" onclick="switchAdb()" title="SSH/developer USB mode — no ADB functions. Click to switch this watch to ADB (via 192.168.2.15).">SSH</span>`;
  if(adb==='fastboot'){const l=fbprod?`fastboot: ${esc(fbprod)}`:'fastboot';return `<span class="cbadge fb" title="watch is in the bootloader (fastboot) — flash/backup only, no ADB or watch functions">${l}</span>`;}
  if(adb)return `<span class="dim">${esc(adb)}</span>`;
  return '<span class="dim">&mdash;</span>';
}
function mkadbrow(p){
  if(p.adb===null&&p.not_enumerating)
    return '<span class="err" title="port is powered and the hub sees a connection, but the device never enumerates — flat battery bootloop or bad cable. Tip: holding the watch in fastboot draws less than booting and lets a flat battery charge past the boot threshold.">not enumerating</span>';
  if(p.adb===null&&p.power===true&&p.connected===false)
    return '<span class="warn" title="port is powered but nothing is electrically connected — watch not docked, or dead cable/contact">not docked</span>';
  return mkadb(p.adb,null,p.os);
}
function render(data){
  const tb=document.getElementById('tb');
  const hubs=(data&&data.hubs)||[];
  // Catch a forgotten screen-force-on (mcetool -D on) anywhere in the fleet:
  // it drains the watch invisibly, so surface it loudly with a release-all.
  const forced=[];hubs.forEach(h=>h.ports.forEach(p=>{if(p.screen_forced)forced.push(p.codename||p.serial)}));
  const al=document.getElementById('alert');
  al.innerHTML=forced.length?`screen forced ON, draining: <b>${forced.map(esc).join(', ')}</b> `+
    `<a href="#" onclick="releaseAllScreens();return false">release all</a>`:'';
  const lo=(data&&data.thresholds&&data.thresholds.low)||40;
  const hi=(data&&data.thresholds&&data.thresholds.high)||80;
  const floor=(data&&data.drain_floor)||15;
  const wearH=(data&&data.wearable_min_hours)||24;
  if(!hubs.length){tb.innerHTML='<tr><td colspan="10" class="dim">No watches configured. Run: asteroid-docking-bay map</td></tr>';return}
  const rows=[];
  const present=new Set();   // serials enumerated this render, for the plug flash
  hubs.forEach(hub=>{
    if(hub.hidden&&!showHidden)return;
    const hubHideBtn=`<a href="#" class="hidebtn" onclick="doHideHub('${esc(hub.location)}');return false" title="${hub.hidden?'un-hide this hub':'hide this whole hub'}">${hub.hidden?'show':'hide'}</a>`;
    rows.push(`<tr class="hub-hdr${hub.hidden?' hiddenrow':''}"><td colspan="10"><span class="hl">${esc(hub.location)}</span><span class="dim">${esc(hub.description)}</span> ${hubHideBtn}</td></tr>`);
    const visPorts=hub.ports.filter(p=>showHidden||!p.excluded);
    visPorts.forEach((p,i)=>{
      const tree=i===visPorts.length-1?'&#x2514;&#x2500;':'&#x251c;&#x2500;';
      if(p.empty){
        const slot=p.slot_loc+':'+p.port;
        const busy=!!(srcs[slot]||p.flashing);
        const d=(busy||p.excluded)?' disabled':'';
        const fbLabel=p.fastboot_product?`fastboot: ${esc(p.fastboot_product)}`:(p.adb==='fastboot'?'fastboot':'');
        const nameCell=p.unmapped
          ?`<span class="dim">${esc(p.codename)} <span style="font-size:.8em;opacity:.6">(click Onboard)</span></span>`
          :(p.fastboot_product?`<span class="warn">${esc(p.fastboot_product)}</span>`:'<span class="dim">&mdash;</span>');
        const adbCell=p.adb==='fastboot'?`<span class="warn">${fbLabel}</span>`
          :mkadbrow(p);
        const pwrCls=p.power===true?'tgl tgl-on':'tgl tgl-off';
        const pwrLbl=p.power===true?'<span class="dot don"></span>ON':'<span class="dot doff"></span>OFF';
        const pwrFn=p.power===true?`doOff('${slot}')`:`doOn('${slot}')`;
        const onboardBtn=p.excluded?'':`<button class="btn ob"${d} onclick="doRemap('${slot}')" title="power the port on, wait for the watch to boot (cycles once if it fails to enumerate), then identify and map it">Onboard</button>`;
        rows.push(
          `<tr class="wr empty${p.excluded?' excl':''}" id="wr-${slot}">` +
          `<td class="tc">${tree}</td>` +
          `<td class="thumb">${mkthumb(p)}</td>` +
          `<td>${nameCell}</td>` +
          `<td class="stats">${mkstrip(p,wearH)}</td>` +
          `<td>${mkport(p)}</td>` +
          `<td><button class="${pwrCls}"${d} onclick="${pwrFn}">${pwrLbl}</button><button class="ico"${d} onclick="doCy('${slot}')" title="Power-cycle port">&#x21BA;</button></td>` +
          `<td>${mksmt(p.smart)}</td>` +
          `<td>${adbCell}</td>` +
          `<td class="dim">&mdash;</td>` +
          `<td>`+onboardBtn+mkhide(slot,p.excluded)+`</td>` +
          `</tr>` +
          `<tr class="lr" id="lr-${slot}"><td colspan="10"><div class="log${busy?' show':''}" id="log-${slot}"></div></td></tr>`
        );
      }else{
        const slot=p.slot_loc+':'+p.port;
        // A watch that just enumerated (absent last render) flashes its row.
        const enumd=p.serial&&p.adb==='device';
        if(enumd)present.add(p.serial);
        const isNew=enumd&&!firstStatus&&!seenSerials.has(p.serial);
        // Only a FUTURE end time is a countdown: accepting a stale/past one
        // creates a tick->expire->refresh->re-add loop that hammers the API.
        if(p.charge_end_ts&&p.charge_end_ts*1000>Date.now()&&!chargeEnd[slot])chargeEnd[slot]=p.charge_end_ts*1000;
        if(!p.charging_active&&chargeEnd[slot])delete chargeEnd[slot];
        const charging=!!p.charging_active;
        const draining=!!(p.drain&&p.drain.active);
        const wb=!!(p.workbench&&p.workbench.active);
        const isFb=p.adb==='fastboot';
        const logActive=!!(srcs[slot]||p.flashing);
        const busy=!!(logActive||charging||draining||wb);
        const d=(busy||p.excluded)?' disabled':'';
        const noSw=p.smart===false;
        const dp=(busy||noSw||p.excluded)?' disabled':'';
        const noSwT=noSw?' title="port cannot switch power (not smart)"':'';
        const adb=mkadbrow(p);
        let bat;
        if(wb){
          const w=p.workbench;
          const pct=w.pct!=null?w.pct+'% ':'';
          bat=`<span class="warn" title="workbench: battery held in the ${lo}–${hi}% band while you work over WiFi/SSH${w.blind?' (battery unreadable — blind duty cycle)':''}">${pct}${esc(w.phase||'')}</span>`;
        }else if(charging){
          if(p.charge_losing){bat=`<span class="err" title="battery is DROPPING while charging — losing power despite the charge attempt. Check contacts / cable / port (the dirty-contact failure).">${p.charge_pct!=null?p.charge_pct:'?'}% &#8595; losing power!</span>`;}
          else if(p.charge_target!=null){bat=`<span class="warn">${p.charge_pct!=null?p.charge_pct:'?'}% &rarr; ${p.charge_target}%</span>`;}
          else if(chargeEnd[slot]){const rem=Math.max(0,Math.round((chargeEnd[slot]-Date.now())/1000));const m=Math.floor(rem/60),s=rem%60;bat=`<span class="warn">${m}m${String(s).padStart(2,'0')}s</span>`;}
          else{bat='<span class="warn">starting&hellip;</span>';}
        }
        else if(draining){
          const dr=p.drain;
          let txt=(dr.last_pct!==null?dr.last_pct+'%':'?%')+' &#x2193;';
          if(dr.drain_rate!==null&&dr.drain_rate>0){
            txt=`${dr.last_pct}% &minus;${dr.drain_rate.toFixed(1)}%/h`;
            if(dr.last_pct>floor){const estH=(dr.last_pct-floor)/dr.drain_rate;txt+=` (~${fmtDur(estH)})`;}
          }
          bat=`<span class="warn">${txt}</span>`;
        }else if(p.drain&&p.drain.done&&p.drain.last_pct!==null){
          const dr=p.drain;
          const summary=dr.drain_rate!==null?` &minus;${dr.drain_rate.toFixed(1)}%/h`:'';
          bat=`${mkbat(p.battery,lo,hi)}<span class="dim" style="font-size:10px"> (test: ${dr.last_pct}%${summary})</span>`;
        }else{
          bat=mkbatCell(p,lo,hi);
        }
        const pwrFn=p.power===true?`doOff('${slot}')`:`doOn('${slot}')`;
        const pwrCls=p.power===true?'tgl tgl-on':'tgl tgl-off';
        const pwrLbl=p.power===true?'<span class="dot don"></span>ON':'<span class="dot doff"></span>OFF';
        const isRef=refreshing.has(slot);
        rows.push(
          `<tr class="wr${isRef?' refreshing':''}${p.excluded?' excl':''}${isNew?' justplugged':''}" id="wr-${slot}">` +
          `<td class="tc">${tree}</td>` +
          `<td class="thumb">${mkthumb(p)}</td>` +
          `<td>`+(p.adb==='device'
            ?`<b class="cn" onclick="openCC('${p.serial}','${p.codename}',event)" title="open Control Center">${esc(p.codename)}</b>`
            :`<b>${esc(p.codename)}</b>`)+(p.screen_forced?`<span class="scrn" onclick="releaseScreen('${p.serial}')" title="screen forced ON (draining) — click to release">screen</span>`:'')+`</td>` +
          `<td class="stats">${mkstrip(p,wearH)}</td>` +
          `<td>${mkport(p)}</td>` +
          `<td><button class="${pwrCls}"${dp}${noSwT} onclick="${pwrFn}">${pwrLbl}</button><button class="ico"${dp} onclick="doCy('${slot}')" title="Power-cycle port">&#x21BA;</button></td>` +
          `<td>${mksmt(p.smart)}</td>` +
          `<td>${adb}</td>` +
          `<td id="bat-${slot}">${bat}</td>` +
          `<td id="act-${slot}">` +
          `<button class="ico${isRef?' pulsing':''}"${d} onclick="doRefresh('${slot}')" title="refresh / re-identify this port">&#x21BB;</button>` +
          (!isFb?`<button class="btn pw"${p.excluded?' disabled':''} onclick="menuPower(event,'${slot}',${charging},${draining},${p.power===true},${noSw})" title="power / charge / drain / reboot">Power &#9662;</button>`:'')+
          (!isFb?`<button class="btn wb"${p.excluded?' disabled':''} onclick="menuWorkbench(event,'${slot}','${p.serial}',${wb},${p.adb==='device'})" title="attended actions — watch stays on">Workbench &#9662;</button>`:'')+
          `<button class="btn fl"${d} onclick="menuFlash(event,'${slot}')" title="flash a release · data backup/restore · mmcblk0 dump">Flashing &#9662;</button>` +
          `</td></tr>` +
          `<tr class="lr" id="lr-${slot}"><td colspan="10"><div class="log${logActive?' show':''}" id="log-${slot}"></div></td></tr>`
        );
      }
    });
  });
  tb.innerHTML=rows.join('');
  seenSerials=present; firstStatus=false;
  Object.keys(srcs).forEach(c=>{const b=document.getElementById('log-'+c);if(b)b.classList.add('show');});
  if(Object.keys(chargeEnd).length>0&&!countdownRunning)tickCountdown();
}
// ── Control Center overlay ──────────────────────────────────────────────────
let ccSerial=null, ccName=null, ccTimer=null, ccAX=0, ccAY=0;
function fmtUp(sec){sec=Math.floor(+sec||0);const d=Math.floor(sec/86400),h=Math.floor(sec%86400/3600),m=Math.floor(sec%3600/60);return (d?d+'d ':'')+(h||d?h+'h ':'')+m+'m';}
function ccPlace(){
  // Anchor to the click; flip ABOVE the anchor if the panel would run off the
  // bottom (its height only known after the async data renders). No page scroll.
  const cc=document.getElementById('cc'), h=cc.offsetHeight, w=cc.offsetWidth;
  let left=Math.min(ccAX, window.innerWidth-w-8);
  let top=ccAY+10;
  if(top+h>window.innerHeight-8) top=ccAY-h-10;
  cc.style.left=Math.max(8,left)+'px'; cc.style.top=Math.max(8,top)+'px';
}
function openCC(serial,name,ev){
  ev.stopPropagation();
  ccSerial=serial; ccName=name; ccAX=ev.clientX; ccAY=ev.clientY;
  const cc=document.getElementById('cc');
  cc.classList.remove('stale-cc');
  cc.innerHTML=`<div class="cc-hd">${name} <span class="dim">loading&hellip;</span></div>`;
  cc.style.display='block'; ccPlace();
  ccFetch();
}
function ccFetch(){
  const s=ccSerial;
  fetch('/api/watch/'+encodeURIComponent(s)).then(r=>r.json()).then(d=>{if(ccSerial===s)renderCC(d)}).catch(()=>{
    const cc=document.getElementById('cc');cc.innerHTML=`<div class="cc-hd">${ccName} <span class="err">unreachable</span><span class="cc-x" onclick="closeCC()">&times;</span></div>`;
  });
}
function renderCC(d){
  const cc=document.getElementById('cc');
  const stale=!!(d&&d.stale);
  cc.classList.toggle('stale-cc',stale);
  if(!d||!d.kernel){cc.innerHTML=`<div class="cc-hd">${ccName} <span class="err">no data (watch offline?)</span><span class="cc-x" onclick="closeCC()">&times;</span></div>`;ccPlace();return;}
  const kv=(k,v)=>`<div class="cc-k">${k}</div><div class="cc-v">${esc(v==null||v===''?'—':String(v))}</div>`;
  const sec=(t,r)=>`<div class="cc-sec"><div class="cc-sech">${t}</div><div class="cc-grid">${r}</div></div>`;
  const num=x=>(x==null||x===''||isNaN(+x))?null:+x;
  const mt=+d.memtotal,mf=+d.memfree,memU=mt?Math.round((mt-mf)/1024):null,memT=mt?Math.round(mt/1024):null;
  const bv=num(d.bat_volt),ba=num(d.bat_curr),bt=num(d.bat_temp),uv=num(d.usb_volt),freq=num(d.cpufreq);
  const dfp=(d.df||'').trim().split(/[ \t]+/);
  const storage=dfp.length>=5?`${dfp[2]} / ${dfp[1]} (${dfp[4]})`:null;
  const mb=x=>{const n=num(x);return n==null?null:(n/1048576).toFixed(2)+' MB';};
  const phone=(+d.btcount>0)?(d.btmac||'connected'):'none';
  // Real unicode arrows, not entities: this value passes through esc(),
  // which would render an entity as literal "&#9660;" text.
  const cur=ba==null?null:`${(ba/1000).toFixed(0)} mA ${ba<-5?'\\u25bc':ba>5?'\\u25b2':''}`;
  const sys=sec('System',
    kv('Kernel',d.kernel)+kv('Qt',d.qt)+kv('SoC',(d.soc||'').trim())+
    kv('CPU',freq?(freq/1000).toFixed(0)+' MHz':null)+
    kv('Uptime',fmtUp(d.uptime))+kv('Boot',d.bootreason)+
    kv('Load',d.load)+kv('Threads',d.threads)+
    kv('Memory',memU!=null?`${memU} / ${memT} MB`:null)+kv('Storage',storage)+
    kv('Resolution',d.resolution));
  const bat=sec('Battery',
    kv('Charge',d.bat_cap!=null&&d.bat_cap!==''?d.bat_cap+'%':null)+kv('Status',d.bat_status)+
    kv('Health',d.bat_health)+kv('Tech',d.bat_tech)+
    kv('Voltage',bv?(bv/1e6).toFixed(3)+' V':null)+kv('Current',cur)+
    kv('Temp',bt!=null?(bt/10).toFixed(1)+' °C':null)+kv('Cycles',d.bat_cycles)+
    kv('USB in',uv!=null&&uv>0?(uv/1e6).toFixed(2)+' V':(+d.usb_online?'online':null)));
  const net=sec('Network &amp; links',
    kv('WiFi',d.wifi==null?null:(d.wifi?'on':'off'))+kv('IP',d.ip)+
    kv('RX / TX',(mb(d.net_rx)||'0')+' / '+(mb(d.net_tx)||'0'))+
    kv('Bluetooth',d.bluetooth==null?null:(d.bluetooth?'on':'off'))+kv('Phone',phone)+
    kv('Timezone',d.tz)+kv('Clock',d.datetime)+kv('WLAN MAC',d.wlanmac)+kv('Serial',d.serial));
  const tgl=(t,l,on)=>`<button class="cc-tgl${on?' on':''}" onclick="ccToggle('${t}',${on?0:1})">${l}: ${on?'ON':'OFF'}</button>`;
  cc.innerHTML=
    `<div class="cc-hd">${esc(ccName)} <span class="dim">${esc(d.os||'')}</span>`+
      (stale?` <span class="warn" title="watch is off the bus — these are the last-known values">stale &middot; last live ${fmtAge(d.last_live_ts)} ago</span>`:'')+
      `<span class="cc-x" onclick="closeCC()">&times;</span></div>`+
    `<div class="cc-cols"><div class="cc-col">${sys}</div><div class="cc-col">${bat}</div><div class="cc-col">${net}</div></div>`+
    `<div class="cc-tgls">${tgl('wifi','WiFi',d.wifi)}${tgl('bluetooth','BT',d.bluetooth)}`+
      `<button class="cc-tgl" onclick="ccBuzz()" title="vibrate to locate in the dock">Buzz</button>`+
      `<button class="cc-tgl${d.screen_forced?' scrnon':''}" onclick="ccScreen(${d.screen_forced?0:1})" title="${d.screen_forced?'demo mode is ON — the screen is forced on and draining. Click to release.':'force the screen on (mce demo mode — stays on and drains until released!)'}">Screen: ${d.screen_forced?'ON':'OFF'}</button>`+
      `<button class="cc-tgl" onclick="doScreenshot('${d.serial}')" title="screenshot in a new tab">Shot</button></div>`+
    `<div class="cc-acts"><button class="cc-act" id="cc-time" onclick="ccSyncTime()">Sync time from host</button></div>`;
  ccPlace();
}
function ccBuzz(){fetch('/api/watch/'+encodeURIComponent(ccSerial)+'/buzz',{method:'POST'}).then(()=>toast('buzzed'));}
function ccScreen(on){fetch('/api/watch/'+encodeURIComponent(ccSerial)+'/screen/'+(on?'on':'off'),{method:'POST'}).then(()=>{toast(on?'screen forced on \u2014 release it when done!':'screen released');ccFetch();refresh();});}
function releaseScreen(s){fetch('/api/watch/'+encodeURIComponent(s)+'/screen/off',{method:'POST'}).then(()=>{toast('screen released');refresh()});}
function releaseAllScreens(){fetch('/api/screen/release-all',{method:'POST'}).then(r=>r.json()).then(d=>{toast('released '+((d.released||[]).length)+' screen(s)');refresh()});}
function ccToggle(tech,on){
  document.querySelectorAll('.cc-tgl').forEach(b=>b.classList.add('busy'));
  fetch('/api/watch/'+encodeURIComponent(ccSerial)+'/toggle/'+tech+'/'+(on?'on':'off'),{method:'POST'})
    .then(()=>setTimeout(ccFetch,1600)).catch(()=>ccFetch());
}
function ccSyncTime(){
  const b=document.getElementById('cc-time');if(b)b.textContent='syncing…';
  fetch('/api/watch/'+encodeURIComponent(ccSerial)+'/settime',{method:'POST'})
    .then(()=>setTimeout(()=>{const bb=document.getElementById('cc-time');if(bb){bb.textContent='✓ synced';bb.classList.add('done');}ccFetch();},700));
}
function closeCC(){const cc=document.getElementById('cc');cc.style.display='none';ccSerial=null;if(ccTimer){clearTimeout(ccTimer);ccTimer=null;}}
function ccLeave(){ccTimer=setTimeout(closeCC,600);}
function ccEnter(){if(ccTimer){clearTimeout(ccTimer);ccTimer=null;}}
// ── Row action floating menus ───────────────────────────────────────────────
let _menuAnchor=null;
function openMenu(ev,html){
  ev.stopPropagation();
  _menuAnchor=ev.currentTarget.getBoundingClientRect();
  document.getElementById('menu').innerHTML=html;
  placeMenu();
}
// Position the menu against its anchor, flipping above/below and clamping to
// the viewport. Kept separate from openMenu so async content (the sparkline,
// which loads after the box opens) can re-place once its real size is known.
function placeMenu(){
  const m=document.getElementById('menu'); if(!_menuAnchor)return;
  m.style.left='-9999px'; m.style.top='0px'; m.style.display='block';
  const r=_menuAnchor, mw=m.offsetWidth, mh=m.offsetHeight;
  let left=r.left, top=r.bottom+3;
  if(left+mw>window.innerWidth-8)left=window.innerWidth-8-mw;
  if(top+mh>window.innerHeight-8)top=Math.max(8,r.top-mh-3);
  m.style.left=Math.max(8,left)+'px'; m.style.top=top+'px';
}
function closeMenu(){document.getElementById('menu').style.display='none';}
function openWatchImg(codename,serial,ev,isRound,res){
  if(ev)ev.stopPropagation();
  // A screenshot beside the product photo. Loaded via fetch (not <img src>)
  // so we can read the stale header: a live capture shows "live screen"; when
  // the watch is off the bus the last pulled screen is shown dimmed with its
  // age; a watch never captured removes the box. The screen is masked to the
  // watch's real shape (round watches get a circle) from live geometry.
  const shotCls='wimg-shot '+(isRound?'shape-round':'shape-rect');
  const shot=serial
    ?`<div id="shotbox"><img class="${shotCls}" id="shotimg" alt=""><div class="wimg-cap" id="shotcap">loading&hellip;</div></div>`
    :'';
  const o=document.getElementById('wimg');
  o.innerHTML=
    `<div class="wimg-hd"><span>${esc(codename)}</span><span class="wimg-x" onclick="closeWatchImg()">&times;</span></div>`+
    `<div class="wimg-body">`+
      `<div><img class="prod" alt="" src="/api/watch-image/${encodeURIComponent(codename)}"><div class="wimg-cap">product</div></div>`+
      shot+
    `</div>`;
  document.getElementById('wimg-bg').style.display='block';
  o.style.display='block';
  if(serial)loadShot(serial,res);
}
function loadShot(serial,res){
  const suffix=res?' · '+res:'';
  fetch('/api/watch/'+encodeURIComponent(serial)+'/screenshot.jpg?t='+Date.now())
    .then(r=>{if(!r.ok)throw 0;const st=r.headers.get('X-Screenshot-Stale');
      const ts=+r.headers.get('X-Screenshot-Ts')||0;
      return r.blob().then(b=>({b,st,ts}));})
    .then(({b,st,ts})=>{const img=document.getElementById('shotimg'),
      cap=document.getElementById('shotcap'); if(!img)return;
      img.src=URL.createObjectURL(b);
      if(st){img.classList.add('shot-stale');cap.className='wimg-cap warn';
        cap.textContent='stale screen'+(ts?' · '+fmtAge(ts)+' ago':'')+suffix;}
      else{cap.textContent='live screen'+suffix;}})
    .catch(()=>{const box=document.getElementById('shotbox');if(box)box.remove();});
}
function closeWatchImg(){document.getElementById('wimg').style.display='none';document.getElementById('wimg-bg').style.display='none';}
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeWatchImg();closeCC();closeMenu();}});
function mi(cls,label,fn,dis,title){return `<button class="menu-item ${cls}"${dis?` disabled title="${title||'not available yet'}"`:` onclick="${fn};closeMenu()"`}>${label}</button>`;}
function menuPower(ev,slot,charging,draining,powered,noSw){
  openMenu(ev,
    (charging?mi('ch','Stop charge',`doStopCharge('${slot}')`):mi('ch','Charge',`doCharge('${slot}')`,noSw))+
    (draining?mi('dr','Stop drain test',`doStopDrain('${slot}')`):mi('dr','Drain test',`doDrain('${slot}')`,noSw))+
    '<div class="menu-sep"></div>'+
    (powered?mi('po','Power off',`doPoweroff('${slot}')`):'')+
    mi('rb','Reboot',`doReboot('${slot}')`)+
    mi('bl','Bootloader',`doBootloader('${slot}')`));
}
function menuWorkbench(ev,slot,serial,wb,online){
  openMenu(ev,
    '<div class="menu-hd">watch stays on — power off when done</div>'+
    (wb?mi('wbx','End checkout',`doStopWb('${slot}')`):mi('wbx','Checkout (hold band)',`doWb('${slot}')`))+
    '<div class="menu-sep"></div>'+
    mi('info','Set time from host',`doSetTime('${serial}')`,!online)+
    mi('info','Screenshot',`doScreenshot('${serial}')`,!online)+
    mi('info','Test notification',`doNotify('${serial}')`,!online)+
    mi('info','Collect diagnostics',`doDiag('${slot}')`,!online));
}
function menuFlash(ev,slot){
  openMenu(ev,
    mi('','Backup data',`doBackup('${slot}')`)+
    mi('','Restore data',`doRestore('${slot}')`)+
    '<div class="menu-sep"></div>'+
    mi('','Flash nightly',`doFl('${slot}')`)+
    mi('',"Flash 2.1",`doFlV('${slot}','2.1')`)+
    mi('',"Flash 2.0",`doFlV('${slot}','2.0')`)+
    '<div class="menu-sep"></div>'+
    mi('','Dump mmcblk0',`doDump('${slot}')`,true,'not yet implemented')+
    mi('','Restore from dump',`doRestoreDump('${slot}')`,true,'not yet implemented'));
}
function toast(msg){
  // Created on first use — every menu action toasts, and a missing element
  // here threw and silently killed the action itself (screenshot bug).
  let t=document.getElementById('toast');
  if(!t){t=document.createElement('div');t.id='toast';document.body.appendChild(t);}
  t.textContent=msg;t.classList.add('show');
  clearTimeout(t._h);t._h=setTimeout(()=>t.classList.remove('show'),2400);
}
function doSetTime(s){toast('syncing time…');fetch('/api/watch/'+encodeURIComponent(s)+'/settime',{method:'POST'}).then(()=>toast('time synced from host'));}
function doNotify(s){fetch('/api/watch/'+encodeURIComponent(s)+'/notify',{method:'POST'}).then(r=>r.json()).then(d=>toast(d.ok?'notification sent to watch':'notify failed'));}
function doScreenshot(s){toast('capturing…');window.open('/api/watch/'+encodeURIComponent(s)+'/screenshot.jpg?t='+Date.now(),'_blank');}
function doFlV(s,v){if(!confirm('Flash AsteroidOS '+v+' to this watch?\\nThis wipes its data — back up first if you need it.'))return;doFl(s,v);}
function switchAdb(){toast('switching to ADB…');fetch('/api/switch-adb',{method:'POST'}).then(r=>r.json()).then(d=>{toast(d.ok?'switching — watch re-enumerating…':'no SSH watch reachable at 192.168.2.15');setTimeout(refresh,5000)});}
function doDiag(c){toast('collecting diagnostics…');fetch('/api/diagnostics/'+_api(c),{method:'POST'}).then(r=>r.json()).then(d=>{
  if(d.name){
    toast(d.ok?'diagnostics ready — downloading':'diagnostics partial — downloading what we have');
    const a=document.createElement('a');a.href='/api/diagnostics/download/'+encodeURIComponent(d.name);
    a.download=d.name;document.body.appendChild(a);a.click();a.remove();
  }else{toast(d.error||'diagnostics failed');}
}).catch(()=>toast('diagnostics failed'));}
function doBackup(c){toast('backing up…');fetch('/api/backup/'+_api(c),{method:'POST'}).then(r=>r.json()).then(d=>toast(d.ok?'backup saved':'backup incomplete — see log')).catch(()=>toast('backup failed'));}
function doRestore(c){if(!confirm('Restore backed-up data onto this watch?\\nOverwrites its current settings + WiFi credentials with the last backup.'))return;toast('restoring…');fetch('/api/restore/'+_api(c),{method:'POST'}).then(r=>r.json()).then(d=>toast(d.ok?'restore done — reconnecting WiFi':(d.error||'restore incomplete — see log'))).catch(()=>toast('restore failed'));}
function doDump(s){} function doRestoreDump(s){}
document.addEventListener('click',e=>{
  const cc=document.getElementById('cc');if(cc.style.display==='block'&&!cc.contains(e.target)&&!e.target.classList.contains('cn'))closeCC();
  const m=document.getElementById('menu');if(m.style.display==='block'&&!m.contains(e.target))closeMenu();
});
function showBackendError(msg){
  // Split mode: the page is served but the backend RPC failed, so status.get
  // came back as an {ok:false,error} envelope with no hubs. Keep the last table
  // on screen (don't blank it) and say clearly that it's stale.
  const b=document.getElementById('berr');
  if(b)b.innerHTML='backend unreachable &mdash; showing last known state <span class="dim">'+esc(msg||'')+'</span>';
  document.getElementById('ts').textContent='stale (backend down)';
}
function clearBackendError(){const b=document.getElementById('berr');if(b&&b.innerHTML)b.innerHTML='';}
function refresh(){
  fetch('/api/status').then(r=>r.json()).then(d=>{
    if(d&&d.error&&!d.hubs){showBackendError(d.error);return;}
    clearBackendError();
    render(d);document.getElementById('ts').textContent='updated '+new Date().toLocaleTimeString();if(d.version)document.getElementById('ver').textContent='v'+d.version
  }).catch(()=>{document.getElementById('ts').textContent='connection error'});
}
function _api(s){return s.replace(':','/');}
function doRefresh(c){
  if(c){refreshing.add(c);setTimeout(()=>refreshing.delete(c),10000);}
  refresh();
}
function _pwrFlash(c){
  const r=document.getElementById('wr-'+c);
  if(!r)return;
  r.classList.add('pwr-warn');
  setTimeout(()=>{r.classList.remove('pwr-warn');refresh();},3800);
}
function doOn(c){
  fetch('/api/on/'+_api(c),{method:'POST'}).then(rr=>rr.json()).then(d=>{
    if(d.confirmed===false)_pwrFlash(c);else setTimeout(refresh,2000);
  });
}
function doOff(c){
  fetch('/api/off/'+_api(c),{method:'POST'}).then(rr=>rr.json()).then(d=>{
    if(d.confirmed===false)_pwrFlash(c);else refresh();
  });
}
function doPoweroff(c){
  fetch('/api/poweroff/'+_api(c),{method:'POST'}).then(rr=>rr.json()).then(d=>{
    // adb_shutdown false = the watch never got the command (it keeps
    // running on battery even though the port is now off) — flag it.
    if(d.confirmed===false||d.adb_shutdown===false)_pwrFlash(c);
    else setTimeout(refresh,4000);
  });
}
function doReboot(c){
  fetch('/api/reboot/'+_api(c),{method:'POST'}).then(()=>setTimeout(refresh,3000));
}
function doBootloader(c){
  fetch('/api/bootloader/'+_api(c),{method:'POST'}).then(()=>setTimeout(refresh,3000));
}
function doCy(c){
  const r=document.getElementById('wr-'+c);
  if(r)r.querySelectorAll('button').forEach(b=>b.disabled=true);
  toast('power-cycling — testing port switching…');
  fetch('/api/cycle/'+_api(c),{method:'POST'}).then(rr=>rr.json()).then(d=>{
    if(d.smart===true)toast('port switches power (smart ✓)');
    else if(d.smart===false)toast('port does NOT cut power (not smart)');
    else if(d.ok)toast('power-cycled — smart still unverified');
    else toast(d.error||'cycle failed');
    setTimeout(refresh,2500);
  }).catch(()=>setTimeout(refresh,2500));
}
function doCharge(c){
  const r=document.getElementById('wr-'+c);
  if(r)r.querySelectorAll('button').forEach(b=>b.disabled=true);
  fetch('/api/charge/'+_api(c),{method:'POST'}).then(rr=>rr.json()).then(d=>{
    // Server state (charging_active + pct/target or end_ts) drives the row;
    // wait out the status cache before re-rendering.
    if(d.ok)setTimeout(refresh,2200);
    else{if(r)r.querySelectorAll('button').forEach(b=>b.disabled=false);}
  });
}
function tickCountdown(){
  countdownRunning=true;
  const now=Date.now();let any=false;
  Object.keys(chargeEnd).forEach(c=>{
    const rem=Math.max(0,Math.round((chargeEnd[c]-now)/1000));
    const cell=document.getElementById('bat-'+c);
    if(!cell)return;
    if(rem>0){
      any=true;
      const m=Math.floor(rem/60),s=rem%60;
      cell.innerHTML=`<span class="warn">${m}m${String(s).padStart(2,'0')}s</span>`;
    }else{delete chargeEnd[c];refresh();}
  });
  if(any){setTimeout(tickCountdown,1000);}else{countdownRunning=false;}
}
function doStopCharge(c){
  fetch('/api/charge/stop/'+_api(c),{method:'POST'}).then(()=>refresh());
}
function fmtDur(h){
  if(h<1)return Math.round(h*60)+'m';
  const d=Math.floor(h/24),hh=Math.floor(h%24);
  return d>0?`${d}d ${hh}h`:`${hh}h`;
}
function doDrain(c){
  fetch('/api/drain/'+_api(c),{method:'POST'}).then(()=>refresh());
}
let histShown=false;
function toggleHistory(){
  const el=document.getElementById('hist');
  histShown=!histShown;
  const l=document.getElementById('histlink');
  if(l)l.textContent=histShown?'hide drain history':'show drain history';
  if(!histShown){el.style.display='none';return;}
  el.style.display='block';
  el.innerHTML='<p class="dim" style="margin-top:14px">loading&hellip;</p>';
  fetch('/api/drain/history').then(r=>r.json()).then(d=>{
    if(!d.tests.length){
      el.innerHTML='<p class="dim" style="margin-top:14px">No drain tests recorded yet &mdash; results land here after the first Drain test finishes.</p>';
      return;
    }
    const wh=d.wearable_min_hours||24;
    const rows=d.tests.map(t=>{
      const dur=(t.end_ts&&t.start_ts&&t.end_ts>t.start_ts)?fmtDur((t.end_ts-t.start_ts)/3600):'&mdash;';
      const rate=t.rate!=null?t.rate.toFixed(2)+'%/h':'&mdash;';
      const estH=(t.rate!=null&&t.rate>0)?85/t.rate:null;
      const est=estH!=null?'~'+fmtDur(estH):'&mdash;';
      const verdict=estH==null?'<span class="dim">&mdash;</span>'
        :estH>=wh?'<span class="on">wearable</span>'
        :'<span class="err">swap candidate</span>';
      const dt=t.start_ts?new Date(t.start_ts*1000).toLocaleString([],{dateStyle:'medium',timeStyle:'short'}):'&mdash;';
      return `<tr><td><b>${esc(t.codename)}</b></td><td class="dim">${dt}</td>`+
        `<td>${t.start_pct}% &rarr; ${t.end_pct!=null?t.end_pct+'%':'?'}</td>`+
        `<td class="dim">${dur}</td><td>${rate}</td><td class="dim">${est}</td>`+
        `<td>${verdict}</td>`+
        `<td class="dim">${t.stopped?'stopped':'done'} (${t.samples} samples)</td></tr>`;
    }).join('');
    el.innerHTML=
      `<h1 style="font-size:15px;margin:24px 0 4px">drain test history</h1>`+
      `<p class="meta">standby drain per test &mdash; a rising rate across months means battery wear; `+
      `wearable = holds &ge;${wh}h standby (wearable_min_hours)</p>`+
      `<table><thead><tr><th>Watch</th><th>Date</th><th>Charge</th><th>Duration</th>`+
      `<th>Rate</th><th>Est. 100&rarr;15%</th><th>Verdict</th><th>Result</th></tr></thead><tbody>${rows}</tbody></table>`;
  });
}
function doStopDrain(c){
  fetch('/api/drain/stop/'+_api(c),{method:'POST'}).then(()=>refresh());
}
function toggleShowHidden(){
  showHidden=!showHidden;
  const l=document.getElementById('hidlink');
  if(l)l.textContent=showHidden?'hide avoided ports':'show all ports';
  refresh();
}
function doHidePort(c){
  fetch('/api/hide/'+_api(c),{method:'POST'}).then(()=>refresh());
}
function doHideHub(loc){
  fetch('/api/hide-hub/'+loc,{method:'POST'}).then(()=>refresh());
}
function doWb(c){
  fetch('/api/workbench/'+_api(c),{method:'POST'}).then(()=>setTimeout(refresh,2200));
}
function doStopWb(c){
  fetch('/api/workbench/stop/'+_api(c),{method:'POST'}).then(()=>setTimeout(refresh,2200));
}
function doFl(c,channel){
  if(srcs[c])return;
  const box=document.getElementById('log-'+c);
  if(!box)return;
  box.textContent='';box.classList.add('show');
  const r=document.getElementById('wr-'+c);
  if(r)r.querySelectorAll('button').forEach(b=>b.disabled=true);
  const es=new EventSource('/api/flash/'+_api(c)+(channel?('?channel='+encodeURIComponent(channel)):''));
  srcs[c]=es;
  es.onmessage=ev=>{box.textContent+=ev.data+'\\n';box.scrollTop=box.scrollHeight};
  es.addEventListener('done',()=>{box.textContent+='\\n\\u2500\\u2500 done \\u2500\\u2500\\n';box.scrollTop=box.scrollHeight;es.close();delete srcs[c];refresh()});
  es.onerror=()=>{box.textContent+='\\n\\u2500\\u2500 connection lost \\u2500\\u2500\\n';es.close();delete srcs[c];refresh()};
}
function doRemap(c){
  if(srcs[c])return;
  const box=document.getElementById('log-'+c);
  if(!box)return;
  box.textContent='';box.classList.add('show');
  const r=document.getElementById('wr-'+c);
  if(r)r.querySelectorAll('button').forEach(b=>b.disabled=true);
  const es=new EventSource('/api/remap/'+_api(c));
  srcs[c]=es;
  es.onmessage=ev=>{box.textContent+=ev.data+'\\n';box.scrollTop=box.scrollHeight};
  es.addEventListener('done',()=>{box.textContent+='\\n\\u2500\\u2500 done \\u2500\\u2500\\n';box.scrollTop=box.scrollHeight;es.close();delete srcs[c];setTimeout(refresh,1000)});
  es.onerror=()=>{box.textContent+='\\n\\u2500\\u2500 connection lost \\u2500\\u2500\\n';es.close();delete srcs[c];refresh()};
}
refresh();setInterval(refresh,15000);
</script>
</body>
</html>
"""


