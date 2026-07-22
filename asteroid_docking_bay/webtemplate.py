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
    /* No side margin: the table runs to both screen edges (its own cell padding
       is the breathing room). Only the header band keeps a little side padding. */
    body{background:#0d1117;color:#c9d1d9;font:13px/1.6 'Cascadia Code','Fira Mono',monospace;padding:14px 0 24px}
    .topbar,.berr,.alert,.hdr{padding-left:10px;padding-right:10px}
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
    /* Rows a touch taller to seat the inline live graph beside the value. */
    .cc-grid .cc-v{min-height:15px;display:flex;align-items:center;justify-content:flex-end;gap:7px}
    .spark{flex:0 0 auto;vertical-align:middle}
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
    .menu{position:fixed;z-index:110;display:none;min-width:172px;max-height:calc(100vh - 24px);overflow-y:auto;background:#161b22;border:1px solid #30363d;border-radius:7px;box-shadow:0 10px 30px rgba(0,0,0,.6);padding:5px}
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
    .menu-item.wear{color:#e0a5b5;background:rgba(224,138,158,.07)}
    /* Execute menu: former buttons become group headers, items indented under. */
    .exgrp-hd{padding:7px 10px 3px;font-size:10px;font-weight:700;color:#8b949e;
      text-transform:uppercase;letter-spacing:.6px;border-top:1px solid #21262d;margin-top:3px}
    .exgrp-hd:first-child{border-top:none;margin-top:0}
    .exgrp{padding-left:9px}
    /* Prominent, non-clickable IP banner at the top of the workbench menu —
       the address you actually need to reach the watch over SSH/WiFi. */
    .menu-ip{display:block;width:100%;text-align:center;padding:7px 10px;margin:1px 0 3px;
      border-radius:5px;border:1px solid #d29922;background:rgba(210,153,34,.1);
      color:#d29922;font:inherit;font-size:13px;letter-spacing:.3px;cursor:default}
    .menu-ip b{font-weight:700}
    #toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%) translateY(20px);background:#161b22;border:1px solid #30363d;color:#c9d1d9;padding:9px 16px;border-radius:7px;font-size:12px;opacity:0;pointer-events:none;transition:.2s;z-index:200}
    #toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
    /* Watch product-photo thumbnail + click-to-enlarge overlay */
    td.thumb{width:34px;padding:2px 2px 2px 0}
    .thumbwrap{position:relative;display:inline-block;line-height:0;vertical-align:middle}
    .thumbfill{position:absolute;z-index:0;background:#000}
    .wthumb{width:30px;height:30px;object-fit:contain;cursor:pointer;vertical-align:middle;border-radius:4px;transition:transform .1s;position:relative;z-index:1}
    .wthumb:hover{transform:scale(1.12)}
    .svgi{width:15px;height:15px;fill:currentColor;vertical-align:-2px}
    td.stats{min-width:52px;white-space:nowrap}   /* >=2 icons wide so the base pair never wraps to two rows */
    td.stats .strip{margin-left:0}
    .strip{margin-left:8px;display:inline-flex;gap:6px;align-items:center;vertical-align:middle}
    /* Every stat is a dot — a glyph in a circle — for one visual language with
       the power dot and the charging circle. The last-seen age, being text, is
       a matching pill rather than a dot. */
    .sdot{display:inline-flex;align-items:center;justify-content:center;box-sizing:border-box;
      width:var(--pill-h);height:var(--pill-h);border-radius:50%;border:1px solid;font-size:var(--pill-fs);
      line-height:1;vertical-align:middle;flex:none}
    .sdot .svgi{width:14px;height:14px;vertical-align:0}
    .sdot.on{border-color:#3fb950;color:#3fb950}
    .sdot.err{border-color:#f85149;color:#f85149}
    .sdot.warn{border-color:#d29922;color:#d29922}
    .sdot.dim{border-color:#3d4756;color:#8b949e}
    .sdot.chg{border-color:#238636;background:#238636;color:#f2cc60}   /* charging: yellow bolt on green */
    .sdot.drain{border-color:#3d4756;color:#8b949e;animation:drainpulse 1.4s ease-in-out infinite}
    .sdot.spark{cursor:pointer}.sdot.spark:hover{background:rgba(88,166,255,.12)}
    @keyframes drainpulse{0%,100%{opacity:.3}50%{opacity:.85}}
    .spill{display:inline-block;box-sizing:border-box;min-height:var(--pill-h);line-height:1.5;
      padding:2px var(--pill-px);border-radius:var(--pill-r);border:1px solid #3d4756;
      color:#8b949e;font-size:var(--pill-fs);vertical-align:middle}
    .spark-hd{padding:6px 10px;font-size:11px;font-weight:700;white-space:nowrap}
    .spark-svg{display:block;padding:2px 8px 8px;background:#0d1117}
    .wimg{position:fixed;z-index:120;display:none;
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
    .device{display:inline-block}
    .dev-frame{position:relative;display:inline-block;line-height:0}
    .dev-prod{display:block;height:230px;width:auto;max-width:44vw;position:relative;z-index:2}
    .device.cut .dev-prod{max-width:none;height:auto}   /* JS (sizeComposite) sets the width, aspect-safe */
    .dev-shot{position:absolute;z-index:1;object-fit:contain}   /* preserve aspect (no squish) and never over-scale past the cutout */
    .dev-fill{position:absolute;z-index:0;background:#000}
    .wimg-shot{height:230px;width:auto;max-width:44vw;object-fit:contain;background:#000}
    .wimg-cap{color:#6e7681;font-size:10px;text-transform:uppercase;letter-spacing:.5px;text-align:center;margin-top:5px}
    /* Fluid: columns follow the page width with a minimal content margin, so
       the table always fits the viewport (no forced horizontal scroll). Column
       positions may shift slightly with string length — that's fine. */
    .tblwrap{overflow-x:auto}
    table{width:100%;border-collapse:collapse}
    th{color:#6e7681;text-align:left;padding:5px 12px;border-bottom:1px solid #21262d;font-size:11px;text-transform:uppercase;letter-spacing:1px;font-weight:normal}
    td{padding:7px 8px;border-bottom:1px solid #161b22;vertical-align:middle}
    /* Port folds into the Power cell: the informative s#/p# label, then the
       toggle — kept on one line. */
    .pcell{white-space:nowrap}
    .pcell .tgl{margin-left:8px}
    /* Smart pills vary in width (ppps / NO! / cycle), so centre them in a
       slightly tighter column. */
    .smtc{text-align:center}
    td.smtc{padding-left:6px;padding-right:6px}
    .wr:hover td{background:#161b22}
    .hub-hdr td{background:#0d1420;color:#6e7681;padding:9px 12px 4px;border-top:1px solid #21262d;border-bottom:1px solid #21262d;font-size:11px;letter-spacing:1px}
    .hub-hdr:first-child td{border-top:none;padding-top:0}
    .hl{color:#58a6ff;font-weight:bold;margin-right:8px}
    tr.empty td{color:#6e7681}
    tr.empty:hover td{background:#0a0d13}
    .on{color:#3fb950}.off{color:#6e7681}.warn{color:#d29922}.err{color:#f85149}.dim{color:#6e7681}
    .stale{color:#a1793a}.stale .agec{opacity:.7;font-size:10px}
    .shot-stale{opacity:.55;filter:grayscale(.3)}
    tr.justplugged>td{animation:plug 2s ease-out}
    @keyframes plug{0%{background:rgba(31,111,235,.4)}100%{background:transparent}}
    .wimg-shot.shape-round{border-radius:50%}.wimg-shot.shape-rect{border-radius:4px}
    .cc.stale-cc{border-color:#7a5b1e}.cc.stale-cc .cc-hd{background:#241d0e}
    .cc.stale-cc .cc-tgl,.cc.stale-cc .cc-act{opacity:.4;pointer-events:none}   /* offline: controls do nothing, so block + dim them */
    .dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;vertical-align:middle}
    .don{background:#3fb950}.doff{background:#30363d}
    /* One set of tokens for every in-row pill, glyph-dot and the port toggle,
       so they all share a height (widths stay content-driven) and a look.
       --pill-h is the port-toggle height — the toggle is the reference size and
       reads it back below. Single-line pills meet this height; a pill whose
       content is too long still wraps to two inner lines and grows. */
    :root{--pill-h:24px;--pill-r:12px;--pill-px:9px;--pill-fs:12px}
    /* Connection-column badges for the abnormal USB modes, so a watch sitting
       in the bootloader or SSH/developer mode stands out from a normal ADB row. */
    /* Pills are inline-block, not flex, so long content (Connection, Battery)
       wraps to a second inner line instead of forcing the column — and the
       table — wider than the viewport. min-height (not height) holds the
       single-line size; a wrapped pill grows past it. */
    .cbadge{display:inline-block;box-sizing:border-box;min-height:var(--pill-h);padding:2px var(--pill-px);border-radius:var(--pill-r);font-size:var(--pill-fs);line-height:1.5;border:1px solid;vertical-align:middle;background:transparent;font-family:inherit}
    .cbadge.fb{border-color:#f0883e;color:#f0883e}
    .cbadge.adb{border-color:#3fb950;color:#3fb950}
    .cbadge.ssh{border-color:#d29922;color:#d29922}
    .cbadge.bat{border-color:#6e7681;color:#c9d1d9}
    .smt{display:inline-block;box-sizing:border-box;min-height:var(--pill-h);padding:2px var(--pill-px);border-radius:var(--pill-r);font-size:var(--pill-fs);line-height:1.5;border:1px solid;background:transparent;font-family:inherit;vertical-align:middle}
    /* Smart type is blue, not green — green is reserved for the power/charge
       states so it keeps its weight. The known type (ppps) is the brighter
       tone; the untested cycle is a darker shade of the same blue (it is an
       action, so deliberately NOT orange — orange means ambiguous/stale here). */
    .smt.ppps{border-color:#58a6ff;color:#58a6ff}
    .smt.no{border-color:#f85149;color:#f85149}
    .smt.unk{border-color:#1f6feb;color:#388bfd;cursor:pointer}
    .smt.unk:hover:not(:disabled){background:#0d2136}
    .smt.unk:disabled{opacity:.35;cursor:default}
    .cbadge.life{font-size:10px;margin-left:6px;letter-spacing:.3px}
    .cbadge.life.down{border-color:#3d4756;color:#8b98a5}
    .cbadge.life.worn{border-color:#d98ca0;color:#e0a5b5}
    .cbadge.life.booting{border-color:#c9d1d9;color:#f0f6fc;animation:bootpulse 1.2s ease-in-out infinite}
    .cbadge.life.bootfail{border-color:#f85149;color:#f85149;animation:bootfail .5s ease-in-out infinite}
    @keyframes bootpulse{0%,100%{opacity:1}50%{opacity:.3}}
    @keyframes bootfail{0%,100%{background:transparent;color:#f85149}50%{background:rgba(248,81,73,.55);color:#fff}}
    .cbadge.bat.ok{border-color:#3fb950;color:#3fb950}
    .cbadge.bat.warn{border-color:#d29922;color:#d29922}
    .cbadge.bat.low{border-color:#f85149;color:#f85149}
    button.cbadge.bat:hover{background:rgba(255,255,255,.05)}
    /* Clickable badges are real <button>s so the cursor is a pointer, not a
       text caret; the non-clickable ones stay <span>s. */
    button.cbadge{cursor:pointer}
    button.cbadge.ssh:hover{background:#2a2113}
    button.cbadge.adb:hover{background:#122117}
    /* The port toggle is the reference the pill height comes from — it reads
       --pill-h back so it and every pill/dot stay the same height together. */
    .tgl{display:inline-flex;align-items:center;justify-content:center;gap:4px;box-sizing:border-box;min-height:var(--pill-h);background:none;border:1px solid;padding:2px 9px 2px 6px;border-radius:var(--pill-r);cursor:pointer;font:var(--pill-fs) monospace;vertical-align:middle;margin-right:3px;touch-action:manipulation;-webkit-tap-highlight-color:transparent;transition:background .12s,transform .12s}
    .tgl-on{border-color:#3fb950;color:#3fb950}.tgl-on:hover{background:#0f2a18}
    .tgl-off{border-color:#30363d;color:#6e7681}.tgl-off:hover{background:#161b22}
    .tgl:active{transform:scale(.92);transition:transform 55ms ease-out}
    .tgl:disabled{opacity:.35;cursor:default;pointer-events:none}
    .btn{background:none;color:#c9d1d9;border:1px solid #30363d;padding:3px 9px;border-radius:4px;cursor:pointer;font:12px monospace;margin:0 .36em;touch-action:manipulation;-webkit-tap-highlight-color:transparent;transition:background .12s,transform .12s}
    .btn:hover{background:#21262d}
    .btn:active{transform:scale(.92);transition:transform 55ms ease-out}
    .fl{border-color:#58a6ff;color:#fff}.fl:hover{background:#111d2e}
    .ch{border-color:#3fb950;color:#3fb950}.ch:hover{background:#0f2a18}
    .ht{border-color:#6e7681;color:#6e7681}.ht:hover{background:#1c1c1c}
    .hcut{border-color:#f85149;color:#f85149}.hcut:hover{background:#2a0d0b}
    .hrb{border-color:#d29922;color:#d29922}.hrb:hover{background:#2a2113}
    .hbl{border-color:#58a6ff;color:#58a6ff}.hbl:hover{background:#111d2e}
    .btn:disabled{opacity:.35;cursor:default;pointer-events:none}
    .btn.ex{border-radius:12px;padding:3px 15px;border-color:#58a6ff;color:#58a6ff}.btn.ex:hover{background:#122132}
    /* A worn row dims but stays. */
    .wr.worn td{opacity:.5}
    .wr.worn:hover td{opacity:.62}
    /* Instant feedback: a clicked action element pulses until the next update
       cycle confirms the new state (which rebuilds the row without this class). */
    .cmd-pending{animation:cmdpulse .8s ease-in-out infinite}
    @keyframes cmdpulse{0%,100%{opacity:1}50%{opacity:.38}}
    /* Failure: switch the pending pulse to a red flash, 3× at double the rate. */
    .cmd-fail{animation:cmdfail .4s ease-in-out 3!important}
    @keyframes cmdfail{0%,100%{background:transparent}50%{background:rgba(248,81,73,.6);border-color:#f85149;color:#fff}}
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
    /* Hovering a refreshing row must not hide the pulse. A plain `background`
       declaration would lose to :hover, and an !important one beats the
       animation itself (important declarations outrank keyframes) — pinning
       the row and killing the hint. So the hovered row gets its own keyframe
       that pulses *from* the hover colour instead. */
    @keyframes rpulsehover{0%,100%{background:#161b22}50%{background:rgba(88,166,255,.16)}}
    .wr.refreshing:hover td{animation:rpulsehover 1.1s ease-in-out infinite}
    .btn-ref.pulsing{animation:bpulse .85s ease-in-out infinite!important;border-color:#58a6ff!important;color:#58a6ff!important}
    @keyframes pwrwarn{0%,100%{background:transparent}40%{background:rgba(248,81,73,.12)}}
    .wr.pwr-warn td{animation:pwrwarn 1.8s ease-in-out 2}
    /* Phones: stack each row into a slim card — one labelled line per field —
       instead of a wide table that scrolls sideways. The desktop column order
       is the fleet's ground-truth order (port → power → … → watch); a card
       reads better name-first, so the card is a flex column that pulls the
       thumbnail and codename to the top with `order`, and the field labels
       come from :nth-child renumbered to the new column positions. */
    @media (max-width:720px){
      /* One card per screen is expected, so size up for legibility and touch —
         desktop's 11-13px is unreadable on a phone. */
      body{padding:12px;font-size:16px}
      .topbar,.meta{font-size:13px}
      .tblwrap{overflow-x:visible}
      table,tbody,tr,td{display:block;width:auto}
      thead{display:none}
      .hub-hdr td{padding:14px 4px 4px;font-size:13px}
      .wr{border:1px solid #21262d;border-radius:8px;margin:0 0 12px;padding:4px 14px;
          display:flex;flex-direction:column}
      .wr:hover td{background:transparent}
      .wr td{border:none;padding:9px 0;display:flex;justify-content:space-between;
             align-items:center;gap:14px;text-align:right;font-size:16px}
      .wr td:nth-child(4){order:-2;display:block;margin:8px 0 0;padding:0;border:none}  /* thumb, card top */
      .wr td:nth-child(4) .wthumb{width:44px;height:44px}
      .wr td:nth-child(5){order:-1;display:block;text-align:left;font-weight:700;font-size:20px;
                          padding:12px 0;border-bottom:1px solid #161b22;overflow:hidden}  /* codename title */
      .wr td.stats:empty{display:none}                           /* no stats read yet → no blank row */
      .wr td:nth-child(1)::before{content:"Port"}
      .wr td:nth-child(2)::before{content:"Smart"}
      .wr td:nth-child(3)::before{content:"Connection"}
      .wr td:nth-child(6)::before{content:"Stats"}
      .wr td:nth-child(7)::before{content:"Battery"}
      .wr td::before{color:#8b949e;font-size:13px;text-transform:uppercase;
                     letter-spacing:.5px;flex:none;font-weight:400}
      .wr td:nth-child(8){order:1;display:block;text-align:left;padding-top:10px}  /* actions span the card, last */
      /* Bigger, tappable controls */
      .wr .btn,.wr .tgl{font-size:15px;padding:9px 13px;margin:3px .3em}
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
  <p class="meta"><a href="#" id="histlink" onclick="toggleHistory();return false" style="color:#388bfd;text-decoration:none">show drain history</a> &nbsp;&middot;&nbsp; <a href="#" id="hidlink" onclick="toggleShowHidden();return false" style="color:#6e7681;text-decoration:none">show all ports</a> &nbsp;&middot;&nbsp; <a href="#" id="usbpreflink" onclick="toggleUsbPref();return false" style="color:#6e7681;text-decoration:none" title="Fleet USB-mode preference — how a watch that comes up on its own in the wrong mode is auto-corrected:&#10;&#10;• prefer ADB (standard): a stray SSH watch is switched back to adb — faster, and how a stock flash enumerates&#10;• prefer SSH: a stray watch is given its own SSH IP so several can run SSH at once — needed for WiFi/workbench work, but updates are slower&#10;&#10;A watch you switched by hand is left alone. Click to switch.">prefer ADB</a></p>
  </div>
  <div class="tblwrap">
  <table>
    <thead><tr>
      <th>Port</th><th class="smtc">Smart</th><th>Connection</th>
      <th></th><th>Watch</th><th>Stats</th><th>Battery</th><th>Actions</th>
    </tr></thead>
    <tbody id="tb"></tbody>
  </table>
  </div>
  <div id="hist" style="display:none"></div>
  <div id="cc" class="cc"></div>
  <div id="nc" class="cc"></div>
  <div id="bi" class="cc"></div>
  <div id="menu" class="menu"></div>
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
function mksmart(p,slot,dis){
  // Smart = can the port switch VBUS. A known verdict is a pill (green yes /
  // red NO!). Untested shows the power-cycle in its place, because the cycle
  // IS the test — one click cuts and restores power and records the verdict —
  // so the control lives exactly where its result will land.
  if(p.smart===true)return '<span class="smt ppps" title="PPPS — this port switches its own VBUS (per-port power switching)">ppps</span>';
  if(p.smart===false)return '<span class="smt no" title="port cannot switch its own power (not smart)">NO!</span>';
  return `<button class="smt unk"${dis} onclick="pulseSelf(this);doCy('${slot}')" title="smart capability not tested — click to power-cycle the port and detect it">&#x21BA;</button>`;
}
function pulseSelf(el){
  // Give a clicked action button instant feedback while the command is in
  // flight. The status refresh that reflects the new state rebuilds the row
  // (reconcile only rebuilds CHANGED rows) and the fresh button has no pulse —
  // so it self-clears on confirmation. The timeout is only a safety net for a
  // command that changes nothing (a no-op or a failure), where the row is
  // reused and the class would otherwise linger.
  if(!el)return;
  el.classList.add('cmd-pending');
  setTimeout(()=>{try{el.classList.remove('cmd-pending');}catch(e){}},8000);
}
function flashFail(el){
  // Direct feedback that a command FAILED: stop the pending pulse and flash
  // the element red three times. Used where the backend tells us the action
  // did not take (a port that would not switch, a refused mode switch).
  if(!el)return;
  el.classList.remove('cmd-pending');
  el.classList.add('cmd-fail');
  setTimeout(()=>{try{el.classList.remove('cmd-fail');}catch(e){}},1300);
}
function connPill(serial){return serial?document.getElementById('conn-'+serial):null;}
function pdot(p){
  // Power state as the first Stats dot: the ⏻ glyph in a circle, recoloured by
  // what we can positively assert. green = powered (the port is delivering
  // power); grey = safely down (a confirmed graceful shutdown, port off, not
  // draining); orange = ambiguous (off with no graceful-shutdown marker — a raw
  // port cut that could equally be off or still running on battery).
  const st=p.power===true?'on':(p.lifecycle==='down'?'down':'amb');
  const tip=st==='on'?'powered — the port is delivering power'
    :st==='down'?'safely powered down — gracefully halted, port off, not draining'
    :'power state ambiguous — port off with no graceful-shutdown marker; could be off, or still running on battery after a raw cut';
  return sdot(st==='on'?'on':st==='down'?'dim':'warn','&#9211;',tip);
}
function mklife(p){
  // Worn (off-rig via the wear toggle) is a marker on the name, so it keeps its
  // own pink pill beside the codename; the power state lives in the Stats dot.
  return p.lifecycle==='worn'?`<span class="cbadge life worn" title="worn — off the rig via the wear toggle; port held for re-docking">worn</span>`:'';
}
function batBand(v,lo,hi){return v==null?'':(v<lo?'low':v<=hi?'ok':'');}
function batPill(p,cls,inner,title){
  // The battery cell as a pill: the charge percent, plus one line of appended
  // detail (charge state, drain rate, …) in dim — like the mode badges carry
  // the serial/IP. Clicking opens the Battery Info window; a watch with no
  // serial (never seen) is a plain non-clickable pill.
  const t=title?` title="${esc(title)}"`:'';
  if(!p.serial)return `<span class="cbadge bat ${cls||''}"${t}>${inner}</span>`;
  return `<button class="cbadge bat ${cls||''}" onclick="openBI('${esc(p.serial)}','${esc(p.codename||p.serial)}',event)"${t}>${inner}</button>`;
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
  if(p.battery!=null){
    const cs=p.charge_status;
    const det=cs?` <span class="dim">${esc(cs)}</span>`:'';
    return batPill(p,batBand(p.battery,lo,hi),`${p.battery}%${det}`,'battery — click for details');
  }
  if(p.battery_cached!=null){
    const age=fmtAge(p.last_live_ts);
    return batPill(p,'warn',`${p.battery_cached}%<span class="dim">${age?' '+age:''}</span>`,
                   'watch off the bus — last reading'+(age?' '+age+' ago':''));
  }
  return '<span class="dim">&mdash;</span>';
}
function mkthumb(p){
  // Product photo thumbnail; removes itself if the watch has no image (404).
  if(!p.codename)return '';
  const g=p.geometry||{};
  const oc=`openWatchImg('${esc(p.codename)}','${esc(p.serial||'')}',event,${g.round?1:0},'${g.resolution?esc(g.resolution):''}')`;
  // Wrapped so a cut-out product image gets a black fill behind its
  // transparent screen — otherwise the row would shine through the hole.
  return `<span class="thumbwrap"><img class="wthumb" loading="lazy" alt="" onload="onThumbLoad(this,'${esc(p.codename)}',${g.round?1:0})" onerror="this.closest('.thumbwrap').remove()" src="/api/watch-image/${encodeURIComponent(p.codename)}" onclick="${oc}"></span>`;
}
function onThumbLoad(img,codename,round){
  // Fill the transparent screen with black in the row thumbnail (once cut),
  // clipped to a circle for round screens so no black corners leak.
  const box=holeFor(codename,img), wrap=img.closest('.thumbwrap');
  if(!box||!wrap)return;
  const f=document.createElement('div'); f.className='thumbfill';
  const pct=v=>(v*100).toFixed(2)+'%';
  f.style.cssText=`left:${pct(box.x)};top:${pct(box.y)};width:${pct(box.w)};height:${pct(box.h)}`+(round?';border-radius:50%':'');
  wrap.insertBefore(f,img);
}
const ICONS={watch:'<path d=\"M127.9 376c0-2 .7-4 2.2-5.5 3.1-3.2 8.1-3.3 11.3-.2 20.9 20 46.8 30.8 79.3 32.8 19 1.2 27.1 5.8 35 10.3 9.3 5.3 18.9 10.7 54.2 10.7 71.7 0 122-59.2 122-132v-56c0-24.7-3-48.9-16.1-69.8-12.8-20.4-26.9-37-48.3-47.9-3.9-2-5.5-6.8-3.5-10.8 2-3.9 6.8-5.5 10.8-3.5 24 12.2 40.2 30.8 54.6 53.6 14.8 23.5 18.5 50.6 18.5 78.3v56c0 81.6-57.5 148-138 148-39.4 0-51.4-6.8-62-12.8-7.2-4.1-12.8-7.3-28.2-8.2-36.4-2.3-65.6-14.4-89.3-37.2-1.6-1.6-2.5-3.7-2.5-5.8z\"/><path d=\"M272.7 402c0-.4 0-.9.1-1.3.7-4.4 4.8-7.3 9.2-6.6 35.5 5.8 66.1-2.4 88.5-23.9 3.2-3.1 8.3-2.9 11.3.2 3.1 3.2 2.9 8.3-.2 11.3-26.2 25.1-61.5 34.8-102.1 28.1-4-.6-6.8-4-6.8-7.8zM64 292v-56c0-27.7 3.8-54.8 18.5-78.3 14.3-22.8 30.6-41.4 54.6-53.6 3.9-2 8.8-.4 10.8 3.5s.4 8.8-3.5 10.8c-21.4 10.9-35.5 27.5-48.3 47.9-13.2 20.8-16.2 45-16.2 69.7v56c0 34.8 9 70.1 38.8 96.9 30.3 27.4 71 43.1 111.6 43.1 4.4 0 8 3.6 8 8s-3.6 8-8 8c-44.5 0-89-17.2-122.3-47.2-33.1-29.9-44-69.5-44-108.8z\"/><path d=\"M375.3 129c-1.9.6-3.9 1-6.1 1-10.5 0-19-8.5-19-19s8.5-19 19-19c5.7 0 10.7 2.4 14.2 6.3-3-19.4-19.8-34.3-40-34.3h-175c-19.6 0-36.1 14-39.8 32.7 3.4-3 7.8-4.7 12.6-4.7 10.5 0 19 8.5 19 19s-8.5 19-19 19c-1.5 0-2.9-.2-4.3-.5 7.4 8.9 18.8 14.5 31.5 14.5h175c12.9 0 24.6-5.8 31.9-15zm-98.1-25c0-14.9 12.1-27 27-27s27 12.1 27 27-12.1 27-27 27c-14.7 0-27-12.1-27-27z\"/>',batterydead:'<path d=\"M384 144H80c-17.6 0-32 14.4-32 32v160c0 17.6 14.4 32 32 32h304c17.6 0 32-14.4 32-32V176c0-17.6-14.4-32-32-32zm16 192c0 8.8-7.2 16-16 16H80c-8.8 0-16-7.2-16-16V176c0-8.8 7.2-16 16-16h304c8.8 0 16 7.2 16 16v160zm32-135.4v110.8c19.1-11.1 32-31.7 32-55.4s-12.9-44.3-32-55.4z\"/>',flash:'<path d=\"M302.7 64 143 288h95.8l-29.5 160L369 224h-95.8l29.5-160z\"/>',moon:'<path d=\"M246.9 64c-12.6 1.4-24.9 4-36.6 7.7C132.4 96.4 76 169.3 76 255.4 76 361.8 162 448 268.2 448c58.7 0 111.2-26.4 146.5-67.9 8.1-9.5 15.2-19.8 21.4-30.8-11.4 2.8-23.1 4.5-35 5.1-2.9.1-5.9.2-8.8.2-48.4 0-94-18.9-128.2-53.2-34.3-34.3-53.1-80-53.1-128.5 0-27.6 6.1-54.3 17.7-78.5 4.9-10.7 11-20.9 18.2-30.4z\"/>',trend:'<path d=\"M472 128H360c-4.4 0-8 3.6-8 8s3.6 8 8 8h92L287.6 308.4l-83.9-84c-1.5-1.5-3.5-2.3-5.7-2.3-2.1 0-4.2.8-5.7 2.3L34.1 382.6c-1.6 1.6-2.1 3.7-2.1 5.9 0 2.1.6 3.9 2.1 5.5 1.6 1.6 3.6 2.3 5.7 2.3 2 0 4.1-.8 5.7-2.3L198 241.3l83.9 84c3.1 3.1 8.2 3.1 11.3 0L464 156v92c0 4.4 3.6 8 8 8s8-3.6 8-8V136c0-4.4-3.6-8-8-8z\"/>'};
function svgicon(n){return `<svg class="svgi" viewBox="0 0 512 512">${ICONS[n]}</svg>`;}
function sdot(cls,inner,title,click){
  return `<span class="sdot ${cls}"${title?` title="${title}"`:''}${click?` onclick="${click}"`:''}>${inner}</span>`;
}
function mkstrip(p,wearH){
  let out='';
  // 0. power state — first, so it reads at the same spot on every row.
  if(p.codename)out+=pdot(p);
  // 1. wearable verdict from the last drain test, or an untested "?".
  const dl=p.drain_last;
  if(dl&&dl.est_h!=null){
    const ok=dl.est_h>=wearH;
    const when=new Date(dl.ts*1000).toLocaleDateString();
    const tip=`holds ~${fmtDur(dl.est_h)} standby (100&rarr;15%, drain test ${when})`+(ok?' — wearable':` — below ${wearH}h: battery swap candidate`);
    out+=sdot(ok?'on':'err',svgicon(ok?'watch':'batterydead'),tip);
  }else if(p.codename){
    out+=sdot('warn','?','never drain-tested — run a drain test to rate standby life');
  }
  // 2. active dock op first (charging = yellow bolt on a green disc; drain
  //    test = a dim pulse), else the watch-side charge state (ground truth).
  if(p.charging_active){
    out+=sdot('chg',svgicon('flash'),'charging to target');
  }else if(p.drain&&p.drain.active){
    out+=sdot('drain',svgicon('batterydead'),'drain test running');
  }else if(p.adb==='device'&&p.charge_status){
    const cs=p.charge_status;
    if(cs==='Charging')out+=sdot('on',svgicon('flash'),'charging (delivered power confirmed)');
    else if(cs==='Full')out+=sdot('on','&#10003;','battery full');
    else if(cs==='Discharging')out+=sdot('err','&#8595;','DISCHARGING while docked — on ADB but not taking charge (dirty contact / bad cable)');
  }
  // 3. sparkline launcher — click for the battery timeline (click, not hover).
  if(p.serial)out+=sdot('dim spark',svgicon('trend'),'battery history',`openSpark('${p.serial}','${esc(p.codename||'')}',event)`);
  // 4. last-seen age when the watch is off the bus — a pill, since it is text.
  if(p.adb!=='device'&&p.last_live_ts)out+=`<span class="spill" title="last live ${fmtAge(p.last_live_ts)} ago">${fmtAge(p.last_live_ts)}</span>`;
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
    ? `<b style="color:#c9d1d9">s${p.socket}</b> <span class="dim" style="font-size:10px">p${p.port}</span>`
    : `<span class="dim">p${p.port}</span>`;
  if(p.excluded) s = `<span class="err" title="${esc(p.excluded)}">avoid</span> ` + s;
  return s;
}
const AOSLOGO='<svg viewBox="0 0 2000 2000" width="13" height="13" style="vertical-align:-2px;margin-right:5px" shape-rendering="crispEdges" xmlns="http://www.w3.org/2000/svg"><defs><rect id="T" width="2" height="2"/></defs><g transform="matrix(100 100 -100 100 1000 0)"><g><use href="#T" style="fill:#be3729"/><use href="#T" id="b" x="2" style="fill:#dc2919"/><use href="#T" id="c" x="4" style="fill:#e54b3a"/><use href="#T" id="d" x="6" style="fill:#e56934"/><use href="#T" id="e" x="8" style="fill:#e57c21"/></g><g transform="translate(-2,2)"><use href="#b"/><use href="#c"/><use href="#T" id="f" x="10" style="fill:#e58a21"/></g><g transform="translate(-4,4)"><use href="#c"/><use href="#e"/><use href="#T" id="g" x="12" style="fill:#f19a11"/></g><g transform="translate(-6,6)"><use href="#d"/><use href="#e"/><use href="#f"/><use href="#T" id="h" x="14" style="fill:#f0ae0e"/></g><g transform="translate(-8,8)"><use href="#e"/><use href="#f"/><use href="#g"/><use href="#h"/><use href="#T" x="16" style="fill:#f0c30e"/></g></g></svg>';
function mkadb(adb,fbprod,os,serial,sshIp,name){
  const nm=esc(name||serial||'');
  if(adb==='device'){
    // Clicking the badge opens the Network Center (addresses, links, the USB
    // mode toggle) rather than switching mode inline — an inline toggle here
    // was too easy to misclick. A real <button> for the pointer cursor; a
    // known non-AsteroidOS watch (e.g. WearOS) stays a plain status span.
    // Shows the serial — the ADB address — mirroring the SSH pill's IP.
    const known=os&&os!=='asteroidos'&&os!=='unknown';
    const logo=os==='asteroidos'?AOSLOGO:'';
    const ser=serial?` <span class="dim">${esc(serial)}</span>`:'';
    const ttl=`ADB mode${os==='asteroidos'?' — AsteroidOS':(known?' — '+esc(os):'')}`;
    if(!known&&serial)
      return `<button class="cbadge adb" onclick="openNC('${esc(serial)}','${nm}',event,'${esc(sshIp||'')}','device')" title="${ttl} — click for network details">${logo}ADB${ser}</button>`;
    return `<span class="cbadge adb" title="${ttl}">${logo}ADB${ser}</span>`;
  }
  if(adb==='ssh'){const ipl=sshIp?` <span class="dim">${esc(sshIp)}</span>`:'';return `<button class="cbadge ssh" onclick="openNC('${esc(serial||'')}','${nm}',event,'${esc(sshIp||'')}','ssh')" title="SSH/developer USB mode at ${esc(sshIp||'192.168.2.15')} — click for network details">${AOSLOGO}SSH${ipl}</button>`;}
  if(adb==='fastboot'){const l=fbprod?`fastboot: ${esc(fbprod)}`:'fastboot';return `<span class="cbadge fb" title="watch is in the bootloader (fastboot) — flash/backup only, no ADB or watch functions">${l}</span>`;}
  if(adb)return `<span class="dim">${esc(adb)}</span>`;
  return '<span class="dim">&mdash;</span>';
}
function mkadbrow(p){
  // Highest-priority warning: the watch is almost certainly awake and
  // draining right now, and nothing else on the row can show it. Cutting VBUS
  // does not stop a watch in the bootloader — it keeps running on battery,
  // invisible, until flat. That is how sturgeon reached 0%.
  if(p.fb_draining)
    return '<span class="err" title="last seen in FASTBOOT, port now unpowered — a watch in the bootloader does NOT stop when power is cut, it keeps running on battery until flat and is invisible while it does. Power the port back on, then either boot it or power it off from the on-screen fastboot menu.">draining in fastboot?</span>';
  // A boot we deliberately triggered: white pulse while it is expected up,
  // then a red-flashing "boot failed?" once the ~40s window lapses. Both beat
  // the generic no-link/not-enumerating messages below — we have positive
  // evidence a boot is under way, so we name it.
  if(p.adb===null&&p.lifecycle==='booting')
    return '<span class="cbadge life booting" title="just powered on / rebooted — waiting for it to come up (~40s)">booting up</span>';
  if(p.adb===null&&p.lifecycle==='bootfail')
    return '<span class="cbadge life bootfail" title="triggered a boot but it has not come up in time — it may have failed to boot, or is simply not enumerating (flat battery, contact/cable)">boot failed?</span>';
  if(p.adb===null&&p.not_enumerating)
    return '<span class="err" title="port is powered and the hub sees a connection, but the device never enumerates — flat battery bootloop or bad cable. Tip: holding the watch in fastboot draws less than booting and lets a flat battery charge past the boot threshold.">not enumerating</span>';
  if(p.adb===null&&p.power===true&&p.connected===false)
    return '<span class="warn" title="port is powered but nothing is electrically connected — no watch docked, or a dead cable/contact. No claim which: the plug being pulled and a bad contact look identical from here.">no link</span>';
  // A safely-down or worn watch is offline on purpose — say so here rather than
  // a bare dash, so the connection column reads as intentional, not a fault.
  if(p.adb===null&&p.lifecycle==='down')
    return '<span class="cbadge life down" title="safely powered down — gracefully halted, port off, not draining">powered down</span>';
  if(p.adb===null&&p.lifecycle==='worn')
    return '<span class="cbadge life worn" title="worn — off the rig via the wear toggle; port held for re-docking">worn</span>';
  return mkadb(p.adb,null,p.os,p.serial,p.ssh_ip,p.codename);
}
// Keyed row reconcile: replacing the whole tbody innerHTML every refresh
// destroyed and recreated every product <img>, so each thumbnail reloaded and
// blanked briefly — a visible flicker and wasted decode of the full-size
// images. Instead, key each row (by its slot, or a hub header by location) and
// only rebuild rows whose HTML actually changed; unchanged rows keep their
// exact DOM node — moved, not recreated — so their images never reload.
const _rowSig={};
function _rowKey(html){
  const m=html.match(/id="wr-([^"]+)"/);
  if(m)return 'row:'+m[1];
  const h=html.match(/class="hl">([^<]*)</);
  if(h)return 'hub:'+h[1];
  return 'x:'+html.length;
}
function reconcileRows(tb, htmls){
  const existing={};
  for(const el of Array.from(tb.children)){
    const k=el.getAttribute('data-k'); if(k!==null)existing[k]=el;
  }
  const seen=new Set(), out=[];
  for(const html of htmls){
    const key=_rowKey(html);
    if(seen.has(key))continue;
    seen.add(key);
    let el=existing[key];
    if(!(el && _rowSig[key]===html)){          // new or changed → build fresh
      const tmp=document.createElement('tbody');
      tmp.innerHTML=html;
      el=tmp.firstElementChild;
      if(el){el.setAttribute('data-k',key); _rowSig[key]=html;}
    }
    if(el)out.push(el);                          // unchanged → reuse the node
  }
  for(const k in _rowSig)if(!seen.has(k))delete _rowSig[k];
  tb.replaceChildren(...out);
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
  usbPref=(data&&data.usb_mode_preference)==='ssh'?'ssh':'adb';
  const upl=document.getElementById('usbpreflink');
  if(upl)upl.textContent=usbPref==='ssh'?'prefer SSH':'prefer ADB';
  if(!hubs.length){tb.innerHTML='<tr><td colspan="8" class="dim">No watches configured. Run: asteroid-docking-bay map</td></tr>';return}
  const rows=[];
  const present=new Set();   // serials enumerated this render, for the plug flash
  hubs.forEach(hub=>{
    if(hub.hidden&&!showHidden)return;
    const hubHideBtn=`<a href="#" class="hidebtn" onclick="doHideHub('${esc(hub.location)}');return false" title="${hub.hidden?'un-hide this hub':'hide/show this hub'}">${hub.hidden?'&#x2295;':'&#x2296;'}</a>`;
    rows.push(`<tr class="hub-hdr${hub.hidden?' hiddenrow':''}"><td colspan="8"><span class="hl">${esc(hub.location)}</span><span class="dim">${esc(hub.description)}</span> ${hubHideBtn}</td></tr>`);
    const visPorts=hub.ports.filter(p=>showHidden||!p.excluded);
    visPorts.forEach((p,i)=>{
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
        const pwrFn=p.power===true?`doOff('${slot}',this)`:`doOn('${slot}',this)`;
        const onboardBtn=p.excluded?'':`<button class="btn ob"${d} onclick="doRemap('${slot}')" title="power on, boot, then identify and map this watch">Onboard</button>`;
        rows.push(
          `<tr class="wr empty${p.excluded?' excl':''}" id="wr-${slot}">` +
          `<td class="pcell">${mkport(p)}<button class="${pwrCls}"${d} title="${p.power===true?'power the port off':'power the port on'}" onclick="pulseSelf(this);${pwrFn}">${pwrLbl}</button></td>` +
          `<td class="smtc">${mksmart(p,slot,d)}</td>` +
          `<td>${adbCell}</td>` +
          `<td class="thumb">${mkthumb(p)}</td>` +
          `<td>${nameCell}</td>` +
          `<td class="stats">${mkstrip(p,wearH)}</td>` +
          `<td class="dim">&mdash;</td>` +
          `<td>`+onboardBtn+mkhide(slot,p.excluded)+`</td>` +
          `</tr>` +
          `<tr class="lr" id="lr-${slot}"><td colspan="8"><div class="log${busy?' show':''}" id="log-${slot}"></div></td></tr>`
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
        const noSw=p.smart===false;
        // Refresh doubles as "power on and identify" only where that is both
        // possible and wanted: a switchable port that is currently off and not
        // excluded (excluded ports are opted out of automatic power entirely).
        const needPwr=(p.power!==true&&!noSw&&!p.excluded);
        const dp=(busy||noSw||p.excluded)?' disabled':'';
        const adb=mkadbrow(p);
        let bat;
        if(wb){
          const w=p.workbench;
          const pct=w.pct!=null?w.pct+'% ':'';
          // Name the holder: on a rig several sessions share, "workbench
          // active" does not tell you whether to wait or take over.
          const who=w.owner?` — held by ${esc(w.owner)}`:'';
          bat=batPill(p,'warn',`${pct}<span class="dim">${esc(w.phase||'')}${w.owner?' ᴋ':''}</span>`,
                      `workbench: battery held in the ${lo}–${hi}% band while you work over WiFi/SSH${w.blind?' (battery unreadable — blind duty cycle)':''}${who}`);
        }else if(charging){
          if(p.charge_losing){bat=batPill(p,'low',`${p.charge_pct!=null?p.charge_pct:'?'}% <span class="dim">&#8595; losing</span>`,'battery is DROPPING while charging — losing power despite the charge attempt. Check contacts / cable / port (the dirty-contact failure).');}
          else if(p.charge_target!=null){bat=batPill(p,'warn',`${p.charge_pct!=null?p.charge_pct:'?'}% <span class="dim">&rarr; ${p.charge_target}%</span>`,'charging');}
          else if(chargeEnd[slot]){const rem=Math.max(0,Math.round((chargeEnd[slot]-Date.now())/1000));const m=Math.floor(rem/60),s=rem%60;bat=batPill(p,'warn',`<span class="dim">${m}m${String(s).padStart(2,'0')}s</span>`,'charging');}
          else{bat=batPill(p,'warn','<span class="dim">starting&hellip;</span>','charging');}
        }
        else if(draining){
          const dr=p.drain;
          let txt=(dr.last_pct!==null?dr.last_pct+'%':'?%')+' <span class="dim">&#x2193;</span>';
          if(dr.drain_rate!==null&&dr.drain_rate>0){
            txt=`${dr.last_pct}% <span class="dim">&minus;${dr.drain_rate.toFixed(1)}%/h`;
            if(dr.last_pct>floor){const estH=(dr.last_pct-floor)/dr.drain_rate;txt+=` (~${fmtDur(estH)})`;}
            txt+='</span>';
          }
          bat=batPill(p,'warn',txt,'drain test running');
        }else if(p.drain&&p.drain.done&&p.drain.last_pct!==null){
          const dr=p.drain;
          const summary=dr.drain_rate!==null?` &minus;${dr.drain_rate.toFixed(1)}%/h`:'';
          bat=batPill(p,batBand(p.battery,lo,hi),`${p.battery!=null?p.battery+'%':'—'}<span class="dim"> (test: ${dr.last_pct}%${summary})</span>`,'battery — click for details');
        }else{
          bat=mkbatCell(p,lo,hi);
        }
        const pwrFn=p.power===true?`doOff('${slot}',this)`:`doOn('${slot}',this)`;
        const pwrCls=p.power===true?'tgl tgl-on':'tgl tgl-off';
        const pwrLbl=p.power===true?'<span class="dot don"></span>ON':'<span class="dot doff"></span>OFF';
        const isRef=refreshing.has(slot);
        rows.push(
          `<tr class="wr${isRef?' refreshing':''}${p.excluded?' excl':''}${isNew?' justplugged':''}${p.lifecycle==='worn'?' worn':''}" id="wr-${slot}">` +
          `<td class="pcell">${mkport(p)}<button class="${pwrCls}"${dp} title="${noSw?'port cannot switch power (not smart)':(p.power===true?'power the port off':'power the port on')}" onclick="pulseSelf(this);${pwrFn}">${pwrLbl}</button></td>` +
          `<td class="smtc">${mksmart(p,slot,dp)}</td>` +
          `<td${p.serial?` id="conn-${esc(p.serial)}"`:''}>${adb}</td>` +
          `<td class="thumb">${mkthumb(p)}</td>` +
          `<td>`+(p.serial
            ?`<b class="cn" onclick="openCC('${p.serial}','${p.codename}',event)" title="open Control Center (stale if offline)">${esc(p.codename)}</b>`
            :`<b>${esc(p.codename)}</b>`)+mklife(p)+(p.screen_forced?`<span class="scrn" onclick="releaseScreen('${p.serial}')" title="screen forced ON (draining) — click to release">screen</span>`:'')+`</td>` +
          `<td class="stats">${mkstrip(p,wearH)}</td>` +
          `<td id="bat-${slot}">${bat}</td>` +
          `<td id="act-${slot}">` +
          `<button class="btn ex${isRef?' pulsing':''}"${p.excluded?' disabled':''} onclick="menuExecute(event,'${slot}',${isFb},${charging},${draining},${p.power===true},${noSw},'${p.serial||''}',${wb},'${p.adb||''}','${p.ssh_ip||''}',${p.wear?1:0},${needPwr})" title="refresh · power/charge/drain · flash/backup · workbench · wear">Execute</button>` +
          `</td></tr>` +
          `<tr class="lr" id="lr-${slot}"><td colspan="8"><div class="log${logActive?' show':''}" id="log-${slot}"></div></td></tr>`
        );
      }
    });
  });
  reconcileRows(tb, rows);
  seenSerials=present; firstStatus=false;
  Object.keys(srcs).forEach(c=>{const b=document.getElementById('log-'+c);if(b)b.classList.add('show');});
  if(Object.keys(chargeEnd).length>0&&!countdownRunning)tickCountdown();
}
// ── Control Center overlay ──────────────────────────────────────────────────
let ccSerial=null, ccName=null, ccAX=0, ccAY=0;
let ncSerial=null, ncName=null, ncAX=0, ncAY=0, ncSshIp=null, ncMode=null;
let biSerial=null, biName=null, biAX=0, biAY=0;
// Last-fetched payload per serial, so re-opening a panel paints instantly from
// the previous values while the fresh fetch is in flight — and a self-cancelling
// poll keeps an open panel live (important over SSH, where a fetch is slow).
const ccCache={}, ncCache={}, biCache={};
let ccPoll=null, ncPoll=null, biPoll=null;
// adb is a warm channel (poll briskly); SSH pays a handshake per call, so a
// 3s poll would never keep up — pace it to 10s. The panel header shows which.
function panelPollMs(d){return (d&&d.transport==='ssh')?10000:3000;}
function pollTag(d){return d?` <span class="dim" title="live refresh interval">&middot; ${d.transport==='ssh'?'10s &middot; ssh':'3s'}</span>`:'';}

// ── live btop-style graphs ──────────────────────────────────────────────────
// A temporary history that lives only while a panel is open — one shared store
// (only one panel is ever open), reset on every open so each graph starts empty
// and fills from the right. Each poll appends one sample per metric; we keep the
// last GRAPH_N. Bars are filled blocks, height = the value on a FIXED per-metric
// scale, colour green→red toward the metric's "bad" end (high battery is green,
// high load/temp is red). Newest bar sits at the right by the value, rolling left.
const GRAPH_N=20;
let graphData={}, graphPrev={};
function graphReset(){graphData={}; graphPrev={};}
function graphPush(id,v){
  if(v==null||isNaN(v))return;
  (graphData[id]=graphData[id]||[]).push(+v);
  if(graphData[id].length>GRAPH_N)graphData[id].shift();
}
function graphPushRate(id,cumulative){        // for counters (rx/tx bytes) → per-second rate
  const v=+cumulative, now=Date.now();
  const p=graphPrev[id];
  if(p&&now>p.t&&v>=p.v)graphPush(id,(v-p.v)/((now-p.t)/1000));
  graphPrev[id]={v:v,t:now};
}
function spark(id,min,max,bad){
  const a=graphData[id]||[];
  if(!a.length)return '';
  const bw=3,gap=1,H=13,W=GRAPH_N*(bw+gap);
  let bars='';
  for(let i=0;i<a.length;i++){
    let n=(a[i]-min)/(max-min); n=n<0?0:n>1?1:n;
    const h=Math.max(1,Math.round(n*H));
    const red=bad==='low'?1-n:n;            // fraction of the way to "bad"
    const hue=Math.round(120*(1-red));      // 120=green … 0=red, through amber
    const x=(GRAPH_N-a.length+i)*(bw+gap);  // right-aligned; newest at the far right
    bars+=`<rect x="${x}" y="${H-h}" width="${bw}" height="${h}" fill="hsl(${hue},68%,48%)"/>`;
  }
  return `<svg class="spark" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${bars}</svg>`;
}
function _ncpu(d){const m=(d.cores||'').match(/([0-9]+) *$/);return m?(+m[1]+1):1;}
function _memPct(d){const t=+d.memtotal;return t?Math.round((t-(+d.memfree||0))/t*100):null;}
function _load1(d){const x=parseFloat((d.load||'').split(/ +/)[0]);return isNaN(x)?null:x;}
let wimgAX=0, wimgAY=0;
let _compo=null;   // {boxW, target, aspect} for an open composite, else null
function sizeComposite(){
  // Set the product width so the screen hole shows the screenshot at `target`
  // px (2/3 of native — the screenshot is heavily JPEG-compressed, so full
  // size shows artefacts). Only width is set (height:auto), so the aspect
  // ratio is always kept; the width is bounded by BOTH viewport dimensions so
  // a small/squished window can't stretch or overflow it. Re-run on resize.
  const prod=document.getElementById('prodimg');
  if(!prod||!_compo)return;
  let w=_compo.target/_compo.boxW;
  w=Math.min(w, window.innerWidth*0.9, window.innerHeight*0.82*_compo.aspect);
  prod.style.width=Math.round(w)+'px'; prod.style.height='auto';
  wimgPlace();
}
window.addEventListener('resize',sizeComposite);
function fmtUp(sec){sec=Math.floor(+sec||0);const d=Math.floor(sec/86400),h=Math.floor(sec%86400/3600),m=Math.floor(sec%3600/60);return (d?d+'d ':'')+(h||d?h+'h ':'')+m+'m';}
function placeOverlay(el,ax,ay){
  // Anchor to the click; flip ABOVE the anchor if the panel would run off the
  // bottom (its height only known after the async data renders). No page scroll.
  const h=el.offsetHeight, w=el.offsetWidth;
  let left=Math.min(ax, window.innerWidth-w-8);
  let top=ay+10;
  if(top+h>window.innerHeight-8) top=ay-h-10;
  el.style.left=Math.max(8,left)+'px'; el.style.top=Math.max(8,top)+'px';
}
function ccPlace(){placeOverlay(document.getElementById('cc'),ccAX,ccAY);}
function ncPlace(){placeOverlay(document.getElementById('nc'),ncAX,ncAY);}
function biPlace(){placeOverlay(document.getElementById('bi'),biAX,biAY);}
// First open of a watch has no client cache, so instead of a "loading…" wait
// paint the server's last-known values immediately — the /stale endpoint reads
// them with no device I/O, so it returns at once (amber, marked stale). The
// slow live fetch then follows and replaces it. cacheHas() guards the race: if
// the live fetch already populated the cache, the late stale paint is dropped.
function paintStale(serial,curSerial,cacheHas,renderFn){
  fetch('/api/watch/'+encodeURIComponent(serial)+'/stale').then(r=>r.json()).then(d=>{
    if(curSerial()===serial && !cacheHas() && d && d.kernel)renderFn(d);
  }).catch(()=>{});
}
function openCC(serial,name,ev){
  ev.stopPropagation(); graphReset();
  ccSerial=serial; ccName=name; ccAX=ev.clientX; ccAY=ev.clientY;
  const cc=document.getElementById('cc');
  cc.classList.remove('stale-cc');
  cc.style.display='block';
  if(ccCache[serial])renderCC(ccCache[serial]);   // instant, from the last open
  else{cc.innerHTML=`<div class="cc-hd">${esc(name)} <span class="dim">loading&hellip;</span></div>`;ccPlace();
       paintStale(serial,()=>ccSerial,()=>!!ccCache[serial],renderCC);}
  ccFetch();
}
function ccFetch(){
  const s=ccSerial;
  fetch('/api/watch/'+encodeURIComponent(s)).then(r=>r.json()).then(d=>{
    if(ccSerial!==s)return;
    ccCache[s]=d; graphPush('load',_load1(d)); graphPush('mem',_memPct(d)); renderCC(d);
    clearTimeout(ccPoll); ccPoll=setTimeout(ccFetch,panelPollMs(d));   // keep live while open
  }).catch(()=>{
    if(ccSerial!==s)return;
    const cc=document.getElementById('cc');cc.innerHTML=`<div class="cc-hd">${esc(ccName)} <span class="err">unreachable</span><span class="cc-x" onclick="closeCC()">&times;</span></div>`;
  });
}
function renderCC(d){
  const cc=document.getElementById('cc');
  const stale=!!(d&&d.stale);
  cc.classList.toggle('stale-cc',stale);
  if(!d||!d.kernel){cc.innerHTML=`<div class="cc-hd">${ccName} <span class="err">no data (watch offline?)</span><span class="cc-x" onclick="closeCC()">&times;</span></div>`;ccPlace();return;}
  const kv=(k,v)=>`<div class="cc-k">${k}</div><div class="cc-v">${esc(v==null||v===''?'—':String(v))}</div>`;
  const kvg=(k,v,g)=>`<div class="cc-k">${k}</div><div class="cc-v">${esc(v==null||v===''?'—':String(v))}${g||''}</div>`;
  const sec=(t,r)=>`<div class="cc-sec"><div class="cc-sech">${t}</div><div class="cc-grid">${r}</div></div>`;
  const num=x=>(x==null||x===''||isNaN(+x))?null:+x;
  const mt=+d.memtotal,mf=+d.memfree,memU=mt?Math.round((mt-mf)/1024):null,memT=mt?Math.round(mt/1024):null;
  const freq=num(d.cpufreq);
  const dfp=(d.df||'').trim().split(/[ \t]+/);
  const storage=dfp.length>=5?`${dfp[2]} / ${dfp[1]} (${dfp[4]})`:null;
  const sys=sec('System',
    kv('Kernel',d.kernel)+kv('Qt',d.qt)+kv('SoC',(d.soc||'').trim())+
    kv('CPU',freq?(freq/1000).toFixed(0)+' MHz':null)+
    kv('Uptime',fmtUp(d.uptime))+kv('Boot',d.bootreason)+
    kvg('Load',d.load,spark('load',0,_ncpu(d),'high'))+kv('Threads',d.threads)+
    kvg('Memory',memU!=null?`${memU} / ${memT} MB`:null,spark('mem',0,100,'high'))+kv('Storage',storage)+
    kv('Resolution',d.resolution)+kv('Timezone',d.tz)+kv('Clock',d.datetime)+
    kv('Machine (image)',d.geometry&&d.geometry.machine)+
    // The bootloader version string names the true hardware, which is the only
    // thing that distinguishes watches sharing an image (rover vs rubyfish).
    // Worth showing verbatim: it is the field the porting community reads to
    // identify a device, so a human can check our detection against it.
    kv('Bootloader',d.geometry&&d.geometry.bootloader));
  cc.innerHTML=
    `<div class="cc-hd">${esc(ccName)} <span class="dim">${esc(d.os||'')}</span>${pollTag(d)}`+
      (stale?` <span class="warn" title="watch is off the bus — these are the last-known values">stale &middot; last live ${fmtAge(d.last_live_ts)} ago</span>`:'')+
      `<span class="cc-x" onclick="closeCC()">&times;</span></div>`+
    `<div class="cc-cols"><div class="cc-col">${sys}</div></div>`+
    `<div class="cc-tgls">`+
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
function ccSyncTime(){
  const b=document.getElementById('cc-time');if(b)b.textContent='syncing…';
  fetch('/api/watch/'+encodeURIComponent(ccSerial)+'/settime',{method:'POST'})
    .then(()=>setTimeout(()=>{const bb=document.getElementById('cc-time');if(bb){bb.textContent='✓ synced';bb.classList.add('done');}ccFetch();},700));
}
function closeCC(){const cc=document.getElementById('cc');cc.style.display='none';ccSerial=null;if(ccPoll){clearTimeout(ccPoll);ccPoll=null;}}

// ── Network Center ──────────────────────────────────────────────────────────
// A second Control-Center-like overlay, opened by clicking the ADB/SSH badge.
// It gathers the network detail that used to crowd the Control Center — links,
// addresses, the WiFi/BT toggles — and adds the USB IP, which lives nowhere
// else. The USB mode toggle lives here too, a deliberate click in an overlay
// rather than the misclick-prone inline badge.
function openNC(serial,name,ev,sshIp,mode){
  ev.stopPropagation(); graphReset();
  ncSerial=serial; ncName=name; ncAX=ev.clientX; ncAY=ev.clientY;
  ncSshIp=sshIp||''; ncMode=mode||'';
  const nc=document.getElementById('nc');
  nc.classList.remove('stale-cc');
  nc.style.display='block';
  if(ncCache[serial])renderNC(ncCache[serial]);
  else{nc.innerHTML=`<div class="cc-hd">${esc(name)} · Network <span class="dim">loading&hellip;</span></div>`;ncPlace();
       paintStale(serial,()=>ncSerial,()=>!!ncCache[serial],renderNC);}
  ncFetch();
}
function ncFetch(){
  const s=ncSerial;
  fetch('/api/watch/'+encodeURIComponent(s)).then(r=>r.json()).then(d=>{
    if(ncSerial!==s)return;
    ncCache[s]=d; graphPushRate('rx',d.net_rx); graphPushRate('tx',d.net_tx); renderNC(d);
    clearTimeout(ncPoll); ncPoll=setTimeout(ncFetch,panelPollMs(d));
  }).catch(()=>{
    if(ncSerial!==s)return;
    const nc=document.getElementById('nc');nc.innerHTML=`<div class="cc-hd">${esc(ncName)} <span class="err">unreachable</span><span class="cc-x" onclick="closeNC()">&times;</span></div>`;
  });
}
function renderNC(d){
  const nc=document.getElementById('nc');
  const stale=!!(d&&d.stale);
  nc.classList.toggle('stale-cc',stale);
  d=d||{};
  const kv=(k,v)=>`<div class="cc-k">${k}</div><div class="cc-v">${esc(v==null||v===''?'—':String(v))}</div>`;
  const kvg=(k,v,g)=>`<div class="cc-k">${k}</div><div class="cc-v">${esc(v==null||v===''?'—':String(v))}${g||''}</div>`;
  const sec=(t,r)=>`<div class="cc-sec"><div class="cc-sech">${t}</div><div class="cc-grid">${r}</div></div>`;
  const num=x=>(x==null||x===''||isNaN(+x))?null:+x;
  const mb=x=>{const n=num(x);return n==null?null:(n/1048576).toFixed(2)+' MB';};
  const phone=(+d.btcount>0)?(d.btmac||'connected'):'none';
  const usbip=ncSshIp||'192.168.2.15';
  const net=sec('Addresses &amp; links',
    kv('USB IP',usbip)+kv('USB mode',ncMode==='ssh'?'SSH (developer)':'ADB')+
    kv('WiFi',d.wifi==null?null:(d.wifi?'on':'off'))+kv('WiFi IP',d.ip)+
    kvg('RX / TX',(mb(d.net_rx)||'0')+' / '+(mb(d.net_tx)||'0'),spark('rx',0,500000,'high')+spark('tx',0,500000,'high'))+
    kv('Bluetooth',d.bluetooth==null?null:(d.bluetooth?'on':'off'))+kv('Phone',phone)+
    kv('WLAN MAC',d.wlanmac)+kv('Serial',d.serial));
  const tgl=(t,l,on)=>`<button class="cc-tgl${on?' on':''}" onclick="ncToggle('${t}',${on?0:1})">${l}: ${on?'ON':'OFF'}</button>`;
  // The USB-mode toggle: the deliberate home for the switch the badge used to
  // carry. Reaches the watch over whichever link it is currently on.
  const modeToggle=ncMode==='ssh'
    ? `<button class="cc-tgl" onclick="switchAdb('${esc(d.serial||ncSerial)}')" title="switch this watch's USB gadget back to ADB">USB &#8594; ADB</button>`
    : `<button class="cc-tgl" onclick="switchSsh('${esc(d.serial||ncSerial)}')" title="switch this watch's USB gadget to SSH/developer mode">USB &#8594; SSH</button>`;
  nc.innerHTML=
    `<div class="cc-hd">${esc(ncName)} &middot; Network <span class="dim">${esc(d.os||'')}</span>${pollTag(d)}`+
      (stale?` <span class="warn" title="watch is off the bus — last-known values">stale &middot; ${fmtAge(d.last_live_ts)} ago</span>`:'')+
      `<span class="cc-x" onclick="closeNC()">&times;</span></div>`+
    `<div class="cc-cols"><div class="cc-col">${net}</div></div>`+
    `<div class="cc-tgls">${tgl('wifi','WiFi',d.wifi)}${tgl('bluetooth','BT',d.bluetooth)}${modeToggle}</div>`;
  ncPlace();
}
function ncToggle(tech,on){
  document.querySelectorAll('#nc .cc-tgl').forEach(b=>b.classList.add('busy'));
  fetch('/api/watch/'+encodeURIComponent(ncSerial)+'/toggle/'+tech+'/'+(on?'on':'off'),{method:'POST'})
    .then(()=>setTimeout(ncFetch,1600)).catch(()=>ncFetch());
}
function closeNC(){const nc=document.getElementById('nc');nc.style.display='none';ncSerial=null;if(ncPoll){clearTimeout(ncPoll);ncPoll=null;}}

// ── Battery Info ────────────────────────────────────────────────────────────
// Opened by clicking the battery pill. There is nothing to *control* about a
// battery, so this detail (voltage, current, temperature, cycles, health,
// measured standby drain) moved out of the Control Center into its own
// read-only window, leaving the pill to carry just the charge and one line of
// appended detail.
function openBI(serial,name,ev){
  ev.stopPropagation(); graphReset();
  biSerial=serial; biName=name; biAX=ev.clientX; biAY=ev.clientY;
  const bi=document.getElementById('bi');
  bi.classList.remove('stale-cc');
  bi.style.display='block';
  if(biCache[serial])renderBI(biCache[serial]);
  else{bi.innerHTML=`<div class="cc-hd">${esc(name)} · Battery <span class="dim">loading&hellip;</span></div>`;biPlace();
       paintStale(serial,()=>biSerial,()=>!!biCache[serial],renderBI);}
  biFetch();
}
function biFetch(){
  const s=biSerial;
  fetch('/api/watch/'+encodeURIComponent(s)).then(r=>r.json()).then(d=>{
    if(biSerial!==s)return;
    biCache[s]=d; graphPush('bcap',d.bat_cap==null?null:+d.bat_cap); graphPush('bvolt',d.bat_volt?+d.bat_volt/1e6:null); graphPush('bcur',d.bat_curr?+d.bat_curr/1000:null); graphPush('btemp',d.bat_temp==null?null:+d.bat_temp/10); renderBI(d);
    clearTimeout(biPoll); biPoll=setTimeout(biFetch,panelPollMs(d));
  }).catch(()=>{
    if(biSerial!==s)return;
    const bi=document.getElementById('bi');bi.innerHTML=`<div class="cc-hd">${esc(biName)} <span class="err">unreachable</span><span class="cc-x" onclick="closeBI()">&times;</span></div>`;
  });
}
function renderBI(d){
  const bi=document.getElementById('bi');
  const stale=!!(d&&d.stale);
  bi.classList.toggle('stale-cc',stale);
  d=d||{};
  const kv=(k,v)=>`<div class="cc-k">${k}</div><div class="cc-v">${esc(v==null||v===''?'—':String(v))}</div>`;
  const kvg=(k,v,g)=>`<div class="cc-k">${k}</div><div class="cc-v">${esc(v==null||v===''?'—':String(v))}${g||''}</div>`;
  const sec=(t,r)=>`<div class="cc-sec"><div class="cc-sech">${t}</div><div class="cc-grid">${r}</div></div>`;
  const num=x=>(x==null||x===''||isNaN(+x))?null:+x;
  const bv=num(d.bat_volt),ba=num(d.bat_curr),bt=num(d.bat_temp),uv=num(d.usb_volt);
  const cur=ba==null?null:`${(ba/1000).toFixed(0)} mA ${ba<-5?'\\u25bc':ba>5?'\\u25b2':''}`;
  const bat=sec('Battery',
    kvg('Charge',d.bat_cap!=null&&d.bat_cap!==''?d.bat_cap+'%':null,spark('bcap',0,100,'low'))+kv('Status',d.bat_status)+
    kv('Health',d.bat_health)+kv('Tech',d.bat_tech)+
    kvg('Voltage',bv?(bv/1e6).toFixed(3)+' V':null,spark('bvolt',3.2,4.35,'low'))+kvg('Current',cur,spark('bcur',-600,600,'low'))+
    kvg('Temp',bt!=null?(bt/10).toFixed(1)+' °C':null,spark('btemp',15,50,'high'))+kv('Cycles',d.bat_cycles)+
    kv('USB in',uv!=null&&uv>0?(uv/1e6).toFixed(2)+' V':(+d.usb_online?'online':null))+
    kv('Standby',d.standby_measured!=null?`${d.standby_measured} %/h · ~${fmtDur(85/d.standby_measured)}`:null));
  bi.innerHTML=
    `<div class="cc-hd">${esc(biName)} &middot; Battery <span class="dim">${esc(d.os||'')}</span>${pollTag(d)}`+
      (stale?` <span class="warn" title="watch is off the bus — last-known values">stale &middot; ${fmtAge(d.last_live_ts)} ago</span>`:'')+
      `<span class="cc-x" onclick="closeBI()">&times;</span></div>`+
    `<div class="cc-cols"><div class="cc-col">${bat}</div></div>`;
  biPlace();
}
function closeBI(){const bi=document.getElementById('bi');bi.style.display='none';biSerial=null;if(biPoll){clearTimeout(biPoll);biPoll=null;}}
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
// ── Transparent-screen cutout detection ─────────────────────────────────────
// A product PNG whose screen is cut to transparent alpha lets us composite the
// live screenshot behind it (bezel + hands occlude). We only need the bounding
// box of the ENCLOSED transparent region: flood-fill transparency inward from
// the border (that is the render's transparent background) and take whatever
// transparency is left — the screen hole. Robust to the hole being split by
// opaque foreground (narwhal's hands): we union all interior-transparent px.
function holeBoxFromAlpha(alpha,w,h,thr){
  thr=thr||128;
  const isT=i=>alpha[i]<thr;
  const bg=new Uint8Array(w*h), stack=[];
  const seed=(x,y)=>{if(x<0||x>=w||y<0||y>=h)return;const i=y*w+x;if(!bg[i]&&isT(i)){bg[i]=1;stack.push(i);}};
  for(let x=0;x<w;x++){seed(x,0);seed(x,h-1);}
  for(let y=0;y<h;y++){seed(0,y);seed(w-1,y);}
  while(stack.length){const i=stack.pop(),x=i%w,y=(i/w)|0;seed(x-1,y);seed(x+1,y);seed(x,y-1);seed(x,y+1);}
  let x0=w,y0=h,x1=-1,y1=-1;
  for(let y=0;y<h;y++)for(let x=0;x<w;x++){const i=y*w+x;if(isT(i)&&!bg[i]){if(x<x0)x0=x;if(x>x1)x1=x;if(y<y0)y0=y;if(y>y1)y1=y;}}
  if(x1<0)return null;
  return {x:x0/w,y:y0/h,w:(x1-x0+1)/w,h:(y1-y0+1)/h};
}
function detectHole(img){
  const w=img.naturalWidth,h=img.naturalHeight;
  if(!w||!h)return null;
  const c=document.createElement('canvas');c.width=w;c.height=h;
  const ctx=c.getContext('2d');ctx.drawImage(img,0,0);
  let d;try{d=ctx.getImageData(0,0,w,h).data;}catch(e){return null;}  // taint guard (same-origin, shouldn't fire)
  const a=new Uint8Array(w*h);
  for(let i=0;i<w*h;i++)a[i]=d[i*4+3];
  return holeBoxFromAlpha(a,w,h);
}
const _holeCache={};
function holeFor(codename,img){
  if(codename in _holeCache)return _holeCache[codename];
  return (_holeCache[codename]=detectHole(img));
}
function openWatchImg(codename,serial,ev,isRound,res){
  if(ev){ev.stopPropagation();wimgAX=ev.clientX;wimgAY=ev.clientY;}
  // Load the product photo in a device frame; onProdLoad then decides the
  // layout once we can inspect the image for a transparent screen cutout.
  const o=document.getElementById('wimg');
  o.innerHTML=
    `<div class="wimg-hd"><span>${esc(codename)}</span><span class="wimg-x" onclick="closeWatchImg()">&times;</span></div>`+
    `<div class="wimg-body" id="wimg-body">`+
      `<div class="device" id="device"><div class="dev-frame" id="devframe">`+
        `<img class="dev-prod" id="prodimg" alt="" onerror="closeWatchImg()" `+
          `onload="onProdLoad('${esc(codename)}','${esc(serial||'')}',${isRound?1:0},'${res?esc(res):''}')" `+
          `src="/api/watch-image/${encodeURIComponent(codename)}"></div></div>`+
    `</div>`;
  o.style.display='block';
  wimgPlace();
}
function onProdLoad(codename,serial,isRound,res){
  const prod=document.getElementById('prodimg'); if(!prod)return;
  const dev=document.getElementById('device'), frame=document.getElementById('devframe');
  const box=holeFor(codename,prod);
  if(box){
    // Cutout present → composite: the product's transparent screen reveals the
    // screenshot behind it (bezel + hands occlude); a black fill under that so
    // an off / not-yet-loaded screen reads as an off panel. Positions are % of
    // the frame, which is exactly the image (caption lives outside it).
    dev.classList.add('cut');
    // Remember what sizeComposite() needs so it can re-fit on window resize.
    const nw=parseInt((res||'').split('x')[0],10);
    _compo=(nw&&box.w>0)?{boxW:box.w,target:nw*2/3,aspect:prod.naturalWidth/prod.naturalHeight}:null;
    const pct=v=>(v*100).toFixed(3)+'%';
    // Round screens: clip the fill+screenshot to a circle so the square hole
    // bounding box can't shine black corners past the bezel.
    const clip=isRound?';border-radius:50%':'';
    const css=`left:${pct(box.x)};top:${pct(box.y)};width:${pct(box.w)};height:${pct(box.h)}${clip}`;
    const fill=document.createElement('div'); fill.className='dev-fill'; fill.style.cssText=css;
    frame.insertBefore(fill,prod);
    if(serial){
      const shot=document.createElement('img'); shot.className='dev-shot'; shot.id='shotimg';
      shot.style.cssText=css; frame.insertBefore(shot,prod);
    }
    const cap=document.createElement('div'); cap.className='wimg-cap'; cap.id='shotcap';
    cap.textContent=serial?'loading…':('screen off'+(res?' · '+res:''));
    dev.appendChild(cap);
    if(serial)loadShot(serial,res);
    sizeComposite();
  }else{
    // No cutout yet → product beside a shape-masked screenshot (prior look).
    const cap=document.createElement('div'); cap.className='wimg-cap'; cap.textContent='product';
    dev.appendChild(cap);
    if(serial){
      const sb=document.createElement('div'); sb.id='shotbox';
      sb.innerHTML=`<img class="wimg-shot ${isRound?'shape-round':'shape-rect'}" id="shotimg" alt="" onload="wimgPlace()"><div class="wimg-cap" id="shotcap">loading&hellip;</div>`;
      document.getElementById('wimg-body').appendChild(sb);
      loadShot(serial,res);
    }
  }
  wimgPlace();
}
function wimgPlace(){
  // Anchor to the click and flip above if it would run off the bottom, like
  // the Control Center — images load async, so this is called again on each
  // image's onload once the real panel size is known.
  const o=document.getElementById('wimg');
  if(o.style.display!=='block')return;
  const h=o.offsetHeight, w=o.offsetWidth;
  let left=Math.min(wimgAX, window.innerWidth-w-8);
  let top=wimgAY+10;
  if(top+h>window.innerHeight-8) top=wimgAY-h-10;
  o.style.left=Math.max(8,left)+'px'; o.style.top=Math.max(8,top)+'px';
}
function loadShot(serial,res){
  const suffix=res?' · '+res:'';
  fetch('/api/watch/'+encodeURIComponent(serial)+'/screenshot.jpg?t='+Date.now())
    .then(r=>{if(!r.ok)throw 0;const st=r.headers.get('X-Screenshot-Stale');
      const ts=+r.headers.get('X-Screenshot-Ts')||0;
      return r.blob().then(b=>({b,st,ts}));})
    .then(({b,st,ts})=>{const img=document.getElementById('shotimg'),
      cap=document.getElementById('shotcap'); if(!img)return;
      img.onload=wimgPlace; img.src=URL.createObjectURL(b);
      if(st){img.classList.add('shot-stale');cap.className='wimg-cap warn';
        cap.textContent='stale screen'+(ts?' · '+fmtAge(ts)+' ago':'')+suffix;}
      else{cap.textContent='live screen'+suffix;}})
    .catch(()=>{
      const box=document.getElementById('shotbox');
      if(box){box.remove();return;}                      // side-by-side: drop the box
      const s=document.getElementById('shotimg');if(s)s.remove();   // composite: keep black fill
      const c=document.getElementById('shotcap');if(c){c.className='wimg-cap';c.textContent='screen off';}
    });
}
function closeWatchImg(){document.getElementById('wimg').style.display='none';_compo=null;}
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeWatchImg();closeCC();closeMenu();}});
function mi(cls,label,fn,dis,title){return `<button class="menu-item ${cls}"${dis?` disabled title="${title||'not available yet'}"`:` onclick="${fn};closeMenu()"`}>${label}</button>`;}
// The row's actions fold into one Execute menu: each former button becomes a
// group header, its items listed indented beneath, all visible at once (no
// nested submenus). Each group is a content-builder returning just its items;
// menuExecute composes them under headers. grpHd is a header, grpBox indents a
// group's items beneath it.
function grpHd(label){return `<div class="exgrp-hd">${label}</div>`;}
function grpBox(items){return `<div class="exgrp">${items}</div>`;}
function grpPower(slot,charging,draining,powered,noSw){
  return (charging?mi('ch','Stop charge',`doStopCharge('${slot}')`):mi('ch','Charge',`doCharge('${slot}')`,noSw))+
    (draining?mi('dr','Stop drain test',`doStopDrain('${slot}')`):mi('dr','Drain test',`doDrain('${slot}')`,noSw))+
    '<div class="menu-sep"></div>'+
    (powered?mi('po','Power off',`doPoweroff('${slot}')`):'')+
    mi('rb','Reboot',`doReboot('${slot}')`)+
    mi('bl','Bootloader',`doBootloader('${slot}')`);
}
// A watch in the bootloader used to get no Power menu at all — a dead end in
// the UI exactly where the watch needs steering. The same intents apply, they
// just travel over fastboot; charge and drain are omitted because both need
// battery reads the bootloader does not serve.
function grpPowerFb(slot,powered){
  return '<div class="menu-hd">in bootloader — fastboot actions</div>'+
    mi('rb','Continue boot',`doContinue('${slot}')`)+
    mi('rb','Reboot',`doReboot('${slot}')`)+
    '<div class="menu-sep"></div>'+
    mi('bl','Cycle bootloader',`doBootloader('${slot}')`)+
    mi('bl','Recovery',`doRecovery('${slot}')`)+
    // Deliberately disabled, not hidden: the watch CAN power off from the
    // bootloader, just not over the wire. rover and rubyfish have no `oem
    // poweroff` command at all, and cutting VBUS does not stop a fastboot
    // watch — it keeps running on battery until flat (measured). The
    // on-screen menu item works because a key press calls LK's shutdown
    // directly. Showing it greyed with the manual route is honest; hiding it
    // would imply the watch cannot be powered off, which is false.
    (powered?'<div class="menu-sep"></div>'+mi('po','Power off',null,true,
      'unavailable — select and confirm "Power off" in the fastboot on-screen menu'):'');
}
function grpWorkbench(slot,serial,wb,mode,sshIp){
  const online=mode==='device';
  // The address to reach this watch over SSH/WiFi — the single most useful
  // thing to have while working on it. Shown as a prominent non-clickable
  // banner at the top, deliberately redundant with the row badge. It is this
  // watch's assigned SSH IP when in SSH mode, otherwise the address it will
  // take on the next switch (the default until one has been assigned).
  const ip=sshIp||'192.168.2.15';
  const ipBanner=`<div class="menu-ip" title="reach this watch over SSH at this address">USB IP <b>${esc(ip)}</b></div>`;
  // USB-mode toggle. Workbench work happens over WiFi/SSH, so switching the
  // watch's USB gadget between adb and SSH/developer mode belongs here. The
  // item flips with the current mode: on adb it offers SSH (delivered over
  // adb, needs the watch online); in SSH mode it offers ADB (delivered over
  // the watch's rndis link, which is up precisely because it's in SSH mode).
  // Either switch re-enumerates the gadget and drops the current link.
  let usbToggle;
  if(mode==='ssh')
    usbToggle=mi('info','Switch USB to ADB',`switchAdb('${serial}')`);
  else
    usbToggle=mi('info','Switch USB to SSH',`switchSsh('${serial}')`,!online,
                 'watch must be on ADB to switch it to SSH mode');
  return ipBanner+
    '<div class="menu-hd">watch stays on — power off when done</div>'+
    (wb?mi('wbx','End checkout',`doStopWb('${slot}')`):mi('wbx','Checkout (hold band)',`doWb('${slot}')`))+
    '<div class="menu-sep"></div>'+
    usbToggle+
    '<div class="menu-sep"></div>'+
    mi('info','Set time from host',`doSetTime('${serial}')`,!online)+
    mi('info','Screenshot',`doScreenshot('${serial}')`,!online)+
    mi('info','Test notification',`doNotify('${serial}')`,!online)+
    mi('info','Collect diagnostics',`doDiag('${slot}')`,!online);
}
function grpFlash(slot){
  return mi('','Backup data',`doBackup('${slot}')`)+
    mi('','Restore data',`doRestore('${slot}')`)+
    mi('info','Fastboot report',`doFbReport('${slot}')`)+
    '<div class="menu-sep"></div>'+
    mi('','Flash nightly',`doFl('${slot}')`)+
    mi('',"Flash 2.1",`doFlV('${slot}','2.1')`)+
    mi('',"Flash 2.0",`doFlV('${slot}','2.0')`)+
    '<div class="menu-sep"></div>'+
    mi('','Dump mmcblk0',`doDump('${slot}')`,true,'not yet implemented')+
    mi('','Restore from dump',`doRestoreDump('${slot}')`,true,'not yet implemented');
}
function menuExecute(ev,slot,isFb,charging,draining,powered,noSw,serial,wb,mode,sshIp,wear,needPwr){
  openMenu(ev,
    grpHd('Refresh')+grpBox(mi('','Re-identify / power on',`doRefresh('${slot}',${needPwr})`))+
    grpHd('Power')+grpBox(isFb?grpPowerFb(slot,powered):grpPower(slot,charging,draining,powered,noSw))+
    grpHd('Flashing')+grpBox(grpFlash(slot))+
    (!isFb?grpHd('Workbench')+grpBox(grpWorkbench(slot,serial,wb,mode,sshIp)):'')+
    (!isFb&&serial?grpHd('Wear')+grpBox(wear?mi('wear','Release wear',`doWear('${slot}',0)`):mi('wear','Arm wear (hold band)',`doWear('${slot}',1)`)):''));
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
function switchAdb(serial){toast('switching to ADB…');fetch('/api/switch-adb'+(serial?'/'+encodeURIComponent(serial):''),{method:'POST'}).then(r=>r.json()).then(d=>{toast(d.ok?'switching — watch re-enumerating on ADB…':('Switch to ADB failed — '+(d.error||'unknown')));if(d.ok)setTimeout(refresh,5000);else flashFail(connPill(serial))});}
function switchSsh(serial){toast('switching to SSH…');fetch('/api/switch-ssh/'+encodeURIComponent(serial),{method:'POST'}).then(r=>r.json()).then(d=>{toast(d.ok?'switching — watch re-enumerating as SSH…':('Switch to SSH failed — '+(d.error||'unknown')));if(d.ok)setTimeout(refresh,6000);else flashFail(connPill(serial))});}
function doDiag(c){toast('collecting diagnostics…');fetch('/api/diagnostics/'+_api(c),{method:'POST'}).then(r=>r.json()).then(d=>{
  if(d.name){
    toast(d.ok?'diagnostics ready — downloading':'diagnostics partial — downloading what we have');
    const a=document.createElement('a');a.href='/api/diagnostics/download/'+encodeURIComponent(d.name);
    a.download=d.name;document.body.appendChild(a);a.click();a.remove();
  }else{toast(d.error||'diagnostics failed');}
}).catch(()=>toast('diagnostics failed'));}
function doFbReport(c){toast('reading bootloader…');fetch('/api/fbreport/'+_api(c),{method:'POST'}).then(r=>r.json()).then(d=>{
  if(d.name){
    toast('fastboot report ('+d.lines+' lines) — downloading');
    const a=document.createElement('a');a.href='/api/diagnostics/download/'+encodeURIComponent(d.name);
    a.download=d.name;document.body.appendChild(a);a.click();a.remove();
  }else{toast(d.error||'fastboot report failed');}
}).catch(()=>toast('fastboot report failed'));}
function doBackup(c){toast('backing up…');fetch('/api/backup/'+_api(c),{method:'POST'}).then(r=>r.json()).then(d=>toast(d.ok?'backup saved':'backup incomplete — see log')).catch(()=>toast('backup failed'));}
function doRestore(c){if(!confirm('Restore backed-up data onto this watch?\\nOverwrites its current settings + WiFi credentials with the last backup.'))return;toast('restoring…');fetch('/api/restore/'+_api(c),{method:'POST'}).then(r=>r.json()).then(d=>toast(d.ok?'restore done — reconnecting WiFi':(d.error||'restore incomplete — see log'))).catch(()=>toast('restore failed'));}
function doDump(s){} function doRestoreDump(s){}
// One floating window at a time, each persisting until a click lands OUTSIDE
// it. Handled on mousedown in the CAPTURE phase, so it runs before any
// trigger's onclick: the very click that opens a new window first closes
// whatever it landed outside of. This one check gives both behaviours — the
// outside-click close and mutual exclusivity — so openers need do nothing, and
// there is no hover-close to make a window vanish when the pointer drifts off.
document.addEventListener('mousedown',e=>{
  const overlays=[['cc',closeCC],['nc',closeNC],['bi',closeBI],
                  ['menu',closeMenu],['wimg',closeWatchImg]];
  for(const [id,close] of overlays){
    const el=document.getElementById(id);
    if(el&&el.style.display==='block'&&!el.contains(e.target))close();
  }
},true);
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
function doRefresh(c,needPwr){
  // A powered-down port has nothing to identify — a watch plugged in while the
  // port was down stays invisible, and the row keeps showing whoever sat there
  // last. So when the port is off, bring VBUS up first and give the watch time
  // to boot and enumerate; the pulse runs for that whole window, not just the
  // instant client-side re-read that a live port needs.
  if(c){refreshing.add(c);setTimeout(()=>refreshing.delete(c),needPwr?45000:10000);}
  if(!needPwr){refresh();return;}
  fetch('/api/on/'+_api(c),{method:'POST'})
    .then(()=>{[0,5000,15000,30000,44000].forEach(t=>setTimeout(refresh,t));})
    .catch(()=>refresh());
}
function _pwrFlash(c){
  const r=document.getElementById('wr-'+c);
  if(!r)return;
  r.classList.add('pwr-warn');
  setTimeout(()=>{r.classList.remove('pwr-warn');refresh();},3800);
}
function doOn(c,el){
  fetch('/api/on/'+_api(c),{method:'POST'}).then(rr=>rr.json()).then(d=>{
    if(d.confirmed===false){flashFail(el);_pwrFlash(c);}else setTimeout(refresh,2000);
  }).catch(()=>flashFail(el));
}
function doOff(c,el){
  fetch('/api/off/'+_api(c),{method:'POST'}).then(rr=>rr.json()).then(d=>{
    if(d.confirmed===false){flashFail(el);_pwrFlash(c);}else refresh();
  }).catch(()=>flashFail(el));
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
function doRecovery(c){
  fetch('/api/recovery/'+_api(c),{method:'POST'}).then(()=>setTimeout(refresh,4000));
}
function doContinue(c){
  // Resuming the boot chain takes the watch all the way to the OS, so give
  // adb time to come up before re-reading rather than showing a bare gap.
  fetch('/api/continue/'+_api(c),{method:'POST'}).then(()=>{
    [3000,15000,30000].forEach(t=>setTimeout(refresh,t));
  });
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
let usbPref='adb';   // fleet USB-mode preference, mirrored from status
function toggleUsbPref(){
  const next=usbPref==='ssh'?'adb':'ssh';
  fetch('/api/usb-preference/'+next,{method:'POST'}).then(()=>refresh());
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
function doWear(c,on){
  toast(on?'wear armed — topping up, port held':'wear released — port freed');
  const url=on?('/api/wear/on/'+_api(c)):('/api/wear/off/'+_api(c));
  fetch(url,{method:'POST'}).then(()=>setTimeout(refresh,1500));
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


