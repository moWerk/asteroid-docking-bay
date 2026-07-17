#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 Timo Könnecke (moWerk) <mo@mowerk.net>
#
# onboard-new-watch-to-fleet.sh — announce a newly-ported watch to a-d-b.
#
# Most watches need NOTHING (a-d-b reads their identity live). The only case
# that needs a change is a variant that ships a *sibling's* system image, so
# machine.conf reports the wrong codename. This helper records that variant in
# the ground-truth exceptions table. See docs/ADDING-A-WATCH.md.

set -euo pipefail
cd "$(dirname "$0")"
JSON="asteroid_docking_bay/watch_variants.json"

echo "── Add a newly-ported watch to asteroid-docking-bay ──"
read -rp "Exact codename (as on asteroidos.org, e.g. tunny): " CODENAME
[ -n "$CODENAME" ] || { echo "codename required"; exit 1; }
read -rp "System image / MACHINE it flashes (machine.conf MACHINE=) [$CODENAME]: " MACHINE
MACHINE="${MACHINE:-$CODENAME}"

if [ "$MACHINE" = "$CODENAME" ]; then
  cat <<EOF

'$CODENAME' has its own system image — a-d-b needs NO code changes.
Flash it, dock it, Onboard/Refresh it: it shows as '$CODENAME', masks its
screen from machine.conf, and fetches asteroidos.org/public/img/$CODENAME.png.
Nothing to edit here. 🎉
EOF
  exit 0
fi

echo
echo "'$CODENAME' shares the '$MACHINE' image — recording it as a variant."
read -rp "  $CODENAME resolution WxH (e.g. 400x400): " RES
read -rp "  model name (optional, e.g. TicWatch E2): " MODEL
read -rp "  GPS?  [y/N, blank=unknown]: " GPS
read -rp "  LTE?  [y/N, blank=unknown]: " LTE
read -rp "  RAM in MB (optional): " RAM
read -rp "  case size in mm (optional): " CASE

BASE_RES=""
if ! python3 -c "import json,sys;d=json.load(open('$JSON'));sys.exit(0 if '$MACHINE' in d['shared_images'] else 1)"; then
  echo "  '$MACHINE' isn't tracked yet — also recording the base watch '$MACHINE'."
  read -rp "  $MACHINE (base) resolution WxH: " BASE_RES
fi

CODENAME="$CODENAME" MACHINE="$MACHINE" RES="$RES" MODEL="$MODEL" \
GPS="$GPS" LTE="$LTE" RAM="$RAM" CASE="$CASE" BASE_RES="$BASE_RES" \
python3 - "$JSON" <<'PY'
import json, os, sys
path = sys.argv[1]
d = json.load(open(path))
si = d["shared_images"]
machine, codename = os.environ["MACHINE"], os.environ["CODENAME"]

def tri(v):
    v = v.strip().lower()
    return True if v in ("y", "yes", "true") else (
        False if v in ("n", "no", "false") else None)

def variant(cn, res, model=None, gps=None, lte=None, ram=None, case=None):
    v = {"codename": cn}
    if model:            v["model"] = model
    if res:              v["resolution"] = res
    if gps is not None:  v["gps"] = gps
    if lte is not None:  v["lte"] = lte
    if ram:              v["ram_mb"] = int(ram)
    if case:             v["case_mm"] = int(case)
    return v

fam = si.get(machine)
if fam is None:
    fam = si[machine] = {"base": machine,
                         "variants": [variant(machine, os.environ.get("BASE_RES", ""))]}
# Replace any existing entry for this codename, keep base-first order otherwise.
fam["variants"] = [v for v in fam["variants"] if v.get("codename") != codename]
fam["variants"].append(variant(
    codename, os.environ["RES"], os.environ.get("MODEL") or None,
    tri(os.environ.get("GPS", "")), tri(os.environ.get("LTE", "")),
    os.environ.get("RAM") or None, os.environ.get("CASE") or None))

json.dump(d, open(path, "w"), indent=2, ensure_ascii=False)
open(path, "a").write("\n")
print(f"  recorded {codename} under the {machine} image")
PY

echo
echo "Validating…"
python3 -c "import json;json.load(open('$JSON'));print('  JSON OK')"
if command -v pytest >/dev/null 2>&1; then
  pytest -q tests/test_variants.py || echo "  (variant tests need review)"
fi
echo
echo "Done. Review it:  git diff $JSON"
echo "If two variants share a resolution (e.g. an LTE twin), make sure the base"
echo "one is listed first — see docs/ADDING-A-WATCH.md."
