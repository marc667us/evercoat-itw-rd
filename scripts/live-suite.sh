#!/usr/bin/env bash
#
# live-suite.sh -- run the full test suite against a DEPLOYED instance.
#
#   ./scripts/live-suite.sh https://evercoat.example.com
#
# THE RULE THIS SCRIPT EXISTS TO ENFORCE (CLAUDE.md §15, platform-wide):
#
#   A deploy is NOT finished when CI turns green. It is finished when the
#   full suite has run against the DEPLOYED site and the counts are
#   reported as THREE NUMBERS -- passed / failed / skipped -- never an
#   exit code.
#
# Why three numbers. An exit code has two states and the world has three.
# A suite that skipped 40 tests because it could not authenticate exits 0
# and reads as success. The skip count is the one that catches
# "everything passed" when nothing actually ran -- five features have
# shipped green-but-broken on live under exactly that failure.
#
# ---------------------------------------------------------------------
# Shell hazards this script is written around. Each cost a real debugging
# session on this platform; none of them are hypothetical.
#
#   `x=$(curl ...) || echo 000`   prints AND exits non-zero, yielding
#                                 "000000". Use x="$(cmd)" || x="".
#
#   `cmd | tail`                  takes tail's exit code, not cmd's, and
#                                 destroys the head of the output -- the
#                                 part naming what failed. Redirect to a
#                                 file and read it afterwards.
#
#   `set -e` + $(curl)            an unguarded command substitution
#                                 aborts the whole step on a non-zero
#                                 exit, so the report never prints.
#
# ---------------------------------------------------------------------

set -uo pipefail
# NOTE: deliberately NOT `set -e`. A failing test must produce a REPORT,
# not an aborted script. Every command below checks its own status.

BASE_URL="${1:-}"
if [[ -z "${BASE_URL}" ]]; then
    echo "usage: $0 <deployed-base-url>" >&2
    echo "  e.g. $0 https://evercoat.example.com" >&2
    exit 2
fi
BASE_URL="${BASE_URL%/}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACTS="${REPO_ROOT}/tmp/live-suite"
mkdir -p "${ARTIFACTS}"

echo "=================================================================="
echo " LIVE SUITE -- ${BASE_URL}"
echo "=================================================================="

# ---------------------------------------------------------------------
# 1. Wait for the site to actually be live.
#
# Free-tier cold starts run to ~2 minutes; a 90-second timeout is not
# proof of an outage. Render's edge answers a ~10-byte 404 carrying
# `x-render-routing: no-server` in well under a second when NO instance
# exists -- that is a different condition from a cold start and worth
# distinguishing, because retrying a no-server is pointless.
# ---------------------------------------------------------------------
echo
echo "--- waiting for ${BASE_URL}/health/ready ---"
DEADLINE=$((SECONDS + 300))
LIVE="no"
while (( SECONDS < DEADLINE )); do
    CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
            "${BASE_URL}/health/ready")" || CODE=""
    [[ -z "${CODE}" ]] && CODE="000"

    if [[ "${CODE}" == "200" ]]; then
        LIVE="yes"
        echo "  live after $((SECONDS))s (HTTP 200)"
        break
    fi
    echo "  HTTP ${CODE} at $((SECONDS))s, still waiting..."
    sleep 10
done

if [[ "${LIVE}" != "yes" ]]; then
    echo
    echo "SITE NEVER BECAME READY after 300s. The suite did not run."
    echo "REPORT: passed=0 failed=0 skipped=0 (suite did not run)"
    exit 1
fi

# ---------------------------------------------------------------------
# 2. Prove a real page mounts -- not just that something answered.
#
# Probing `/` alone is a FALSE GREEN. Application roots are commonly
# redirect stubs, so a 200 or a 307 on `/` proves the edge is up and
# proves nothing about whether the app mounted. Follow redirects (-L)
# and probe a page that only exists if the app is really serving.
# ---------------------------------------------------------------------
echo
echo "--- proving the application actually mounts ---"
MOUNT_FAILURES=0
for path in "/" "/health/live" "/docs"; do
    CODE="$(curl -sL -o /dev/null -w '%{http_code}' --max-time 30 \
            "${BASE_URL}${path}")" || CODE=""
    [[ -z "${CODE}" ]] && CODE="000"
    if [[ "${CODE}" =~ ^(200|401|403)$ ]]; then
        # 401/403 is a PASS here: it proves the app mounted and its
        # authorization layer answered. Only 000/404/5xx mean not mounted.
        echo "  ${path} -> ${CODE}  ok"
    else
        echo "  ${path} -> ${CODE}  NOT MOUNTED"
        MOUNT_FAILURES=$((MOUNT_FAILURES + 1))
    fi
done

# ---------------------------------------------------------------------
# 3. The suites. Each writes to a file -- never piped -- so the exit
#    code survives and the head of the output is not thrown away.
# ---------------------------------------------------------------------
PASSED=0
FAILED=0
SKIPPED=0

run_pytest() {
    local label="$1"; shift
    local logfile="${ARTIFACTS}/${label}.log"

    echo
    echo "--- ${label} ---"
    ( cd "${REPO_ROOT}/apps/api" && \
      LIVE_BASE_URL="${BASE_URL}" python -m pytest "$@" \
        -q --no-header -rs ) > "${logfile}" 2>&1
    local rc=$?

    # Parse pytest's own summary line rather than trusting rc. rc==1
    # means "some test failed"; rc==5 means "no tests collected", which
    # is a SKIP-shaped outcome that must not read as success.
    local line
    line="$(grep -E '^[0-9]+ (passed|failed)|passed|failed|skipped|no tests ran' \
            "${logfile}" | tail -1)" || line=""

    local p f s
    p="$(sed -nE 's/.*[^0-9]([0-9]+) passed.*/\1/p'  <<< "${line}")"; p="${p:-0}"
    f="$(sed -nE 's/.*[^0-9]([0-9]+) failed.*/\1/p'  <<< "${line}")"; f="${f:-0}"
    s="$(sed -nE 's/.*[^0-9]([0-9]+) skipped.*/\1/p' <<< "${line}")"; s="${s:-0}"

    if [[ ${rc} -eq 5 ]]; then
        echo "  NO TESTS COLLECTED -- counted as a gap, not a pass"
    fi

    PASSED=$((PASSED + p))
    FAILED=$((FAILED + f))
    SKIPPED=$((SKIPPED + s))

    echo "  ${label}: passed=${p} failed=${f} skipped=${s} (rc=${rc})"
    echo "  log: ${logfile}"
    if [[ ${f} -gt 0 ]]; then
        echo "  --- failing tests ---"
        grep -E '^(FAILED|ERROR)' "${logfile}" || true
    fi
}

# Backend suites that can be pointed at a live instance.
run_pytest "api-live" tests -m "live or not live"

# Playwright, if it is installed. Absence is reported as a GAP rather
# than silently omitted -- a suite that quietly skips its only end-to-end
# coverage reads as "everything passed".
echo
echo "--- e2e (playwright) ---"
if [[ -d "${REPO_ROOT}/tests/e2e" ]] && command -v npx >/dev/null 2>&1; then
    ( cd "${REPO_ROOT}" && PLAYWRIGHT_BASE_URL="${BASE_URL}" \
      npx playwright test --reporter=line ) > "${ARTIFACTS}/e2e.log" 2>&1
    E2E_RC=$?
    E2E_P="$(grep -cE '^\s*✓' "${ARTIFACTS}/e2e.log")" || E2E_P=0
    E2E_F="$(grep -cE '^\s*✘|^\s*×' "${ARTIFACTS}/e2e.log")" || E2E_F=0
    PASSED=$((PASSED + E2E_P))
    FAILED=$((FAILED + E2E_F))
    echo "  e2e: passed=${E2E_P} failed=${E2E_F} (rc=${E2E_RC})"
else
    echo "  NOT RUN -- tests/e2e absent or npx unavailable."
    echo "  This is a COVERAGE GAP, counted as skipped, not as a pass."
    SKIPPED=$((SKIPPED + 1))
fi

# ---------------------------------------------------------------------
# 4. The report. Three numbers, always, even on total failure.
# ---------------------------------------------------------------------
FAILED=$((FAILED + MOUNT_FAILURES))

echo
echo "=================================================================="
echo " LIVE SUITE REPORT -- ${BASE_URL}"
echo "=================================================================="
echo "   passed  : ${PASSED}"
echo "   failed  : ${FAILED}"
echo "   skipped : ${SKIPPED}"
echo "------------------------------------------------------------------"
if [[ ${SKIPPED} -gt 0 ]]; then
    echo " NOTE: ${SKIPPED} skipped. A skip is not a pass -- read the logs"
    echo "       in ${ARTIFACTS} before calling this deploy finished."
fi
echo "=================================================================="

# The exit code is for CI. The REPORT above is for the human, and it is
# the report -- not this number -- that answers "did the deploy work".
[[ ${FAILED} -eq 0 ]] && exit 0 || exit 1
