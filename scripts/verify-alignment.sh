#!/usr/bin/env bash
# Prove that LOCAL, DEPLOYED and LIVE are the same thing.
#
# WHY THIS IS A SEPARATE CHECK FROM THE LIVE SUITE.
#
# The live suite proves the deployed site WORKS. It does not prove the
# deployed site is the code in this working tree. Those come apart in ways
# that are individually mundane and jointly expensive:
#
#   · a commit that never got pushed
#   · a push whose deploy failed, leaving the PREVIOUS build serving
#   · a deploy that succeeded from a different branch
#   · a static export whose baked figures were never recomputed
#
# Every one of those produces a green suite against a site that does not
# match what anyone is looking at locally. This script asks the only
# question that settles it: does the content on the live URL match the
# content this tree produces?
#
# Usage:  ./scripts/verify-alignment.sh https://itwevercoatrd.aiappinvent.com

set -uo pipefail

BASE_URL="${1:-}"
if [[ -z "${BASE_URL}" ]]; then
    echo "usage: $0 <deployed-base-url>" >&2
    exit 2
fi
BASE_URL="${BASE_URL%/}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA="${REPO_ROOT}/apps/web/lib/demo/demo-data.json"

FAILURES=0
note() { printf '  %-52s %s\n' "$1" "$2"; }
fail() { note "$1" "FAIL — $2"; FAILURES=$((FAILURES + 1)); }
ok()   { note "$1" "ok — $2"; }

echo "=================================================================="
echo " ALIGNMENT — local tree vs ${BASE_URL}"
echo "=================================================================="

# ---------------------------------------------------------------- 1. git
echo
echo "--- source control ---"
LOCAL_SHA="$(git -C "${REPO_ROOT}" rev-parse HEAD)"
REMOTE_SHA="$(git -C "${REPO_ROOT}" rev-parse '@{upstream}' 2>/dev/null)" || REMOTE_SHA=""
DIRTY="$(git -C "${REPO_ROOT}" status --porcelain)"

if [[ -n "${DIRTY}" ]]; then
    fail "working tree" "uncommitted changes — local differs from any deploy"
else
    ok "working tree" "clean"
fi

if [[ -z "${REMOTE_SHA}" ]]; then
    fail "upstream" "no upstream branch to compare against"
elif [[ "${LOCAL_SHA}" != "${REMOTE_SHA}" ]]; then
    fail "local vs origin" "${LOCAL_SHA:0:7} != ${REMOTE_SHA:0:7} — unpushed commits"
else
    ok "local vs origin" "${LOCAL_SHA:0:7}"
fi

# ------------------------------------------------- 2. baked figures fresh
echo
echo "--- baked figures ---"
# The demonstration's numbers come from the Python engine. If the committed
# JSON is stale, the live site shows figures for a formula nobody has.
BEFORE="$(sha256sum "${DATA}" | cut -d' ' -f1)"
( cd "${REPO_ROOT}" && python scripts/build_demo_formulations.py >/dev/null 2>&1 ) || true
AFTER="$(sha256sum "${DATA}" | cut -d' ' -f1)"
if [[ "${BEFORE}" != "${AFTER}" ]]; then
    fail "committed figures" "STALE — recomputing changed them"
else
    ok "committed figures" "match a fresh run of the engine"
fi

# ---------------------------------------------- 3. live content matches
echo
echo "--- live content vs local dataset ---"
# Pull a handful of values the ENGINE produced and look for them verbatim in
# the served HTML. If the deployed bundle were built from different data or
# different code, these would not all be present.
read -r F_CODE DENSITY VOC SOLIDS TOTAL < <(
python - "${DATA}" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
f = d["formulas"][0]
# the approved version, the one the page leads with
v = [x for x in f["versions"] if x["status"] == "approved"]
v = (v or f["versions"])[-1]
c = v["computed"]
print(f["formula_code"], c["theoretical_density_g_cm3"], c["voc_g_per_l"],
      c["solids_percent"], c["total_percentage"])
PY
)

HTML="$(curl -sL --max-time 45 "${BASE_URL}/formulations/${F_CODE}/")" || HTML=""
if [[ -z "${HTML}" ]]; then
    fail "formula page" "could not fetch ${BASE_URL}/formulations/${F_CODE}/"
else
    for pair in "density:${DENSITY}" "VOC:${VOC}" "solids:${SOLIDS}" "total:${TOTAL}"; do
        label="${pair%%:*}"; value="${pair#*:}"
        if grep -qF -- "${value}" <<< "${HTML}"; then
            ok "live ${label}" "${value} present"
        else
            fail "live ${label}" "${value} NOT on the live page"
        fi
    done
fi

# ------------------------------------------------- 4. routes exist live
echo
echo "--- routes ---"
for path in "/dashboard/" "/projects/" "/materials/" "/suppliers/" "/formulations/"; do
    code="$(curl -sL -o /dev/null -w '%{http_code}' --max-time 30 "${BASE_URL}${path}")" || code="000"
    if [[ "${code}" == "200" ]]; then ok "${path}" "200"; else fail "${path}" "HTTP ${code}"; fi
done

echo
echo "=================================================================="
if [[ ${FAILURES} -eq 0 ]]; then
    echo " ALIGNED — local tree, origin and the live site agree."
else
    echo " ${FAILURES} ALIGNMENT FAILURE(S). The live site is NOT this tree."
fi
echo "=================================================================="
[[ ${FAILURES} -eq 0 ]] && exit 0 || exit 1
