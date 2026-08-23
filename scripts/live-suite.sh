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
    echo "usage: $0 <deployed-base-url> [profile]" >&2
    echo "  e.g. $0 https://evercoat.example.com web" >&2
    echo "  profile: web | api | full   (default: full)" >&2
    # The three-number report prints even here. "Three numbers, always"
    # has to mean ALWAYS, or a caller scraping this output for counts
    # gets nothing back and has to infer the outcome from an exit code --
    # which is the failure mode the contract exists to remove.
    echo "REPORT: passed=0 failed=0 skipped=0 (no URL given; suite did not run)"
    exit 2
fi
BASE_URL="${BASE_URL%/}"

# ---------------------------------------------------------------------
# WHICH SURFACES ARE ACTUALLY DEPLOYED.
#
# This script used to assume the API was there. Every probe it made --
# /health/ready, /health/live, /docs -- is an API route, so against a
# web-only deployment it waited the full 300s and reported
# "passed=0 failed=0 skipped=0, the suite did not run". Honest, and
# useless: the deployed thing was never tested at all.
#
# `render.yaml` deploys the WEB application only (ADR-009), so `web` is
# the profile that matches production today. The API surface is then
# counted as SKIPPED -- a coverage gap reported as a gap, never folded
# into `passed`.
#
# When the API is deployed at Slice 3, run `full` and this becomes a real
# assertion again rather than a skip.
# ---------------------------------------------------------------------
# 🔴 THE DEFAULT PROFILE DID NOT MATCH WHAT IS DEPLOYED.
#
# The default was `full`, so the documented invocation in CLAUDE.md §13
# -- `./scripts/live-suite.sh <deployed-url>` with no second argument --
# waited 300 seconds on /health/ready, an API route, against a web-only
# deployment, then reported "passed=0 failed=0 skipped=0, the suite did
# not run". Honest and useless: the deployed thing went untested, and
# the operator had to already know to pass `web` to get any coverage at
# all. The comment above already said `web` is the profile that matches
# production; the code did not.
#
# `auto` (the new default) MEASURES it instead of assuming either way.
# Probing the status alone is not enough -- a 404 could be a cold start,
# and free-tier cold starts run to ~2 minutes. The discriminator is the
# CONTENT TYPE: an API health route answers JSON, while a static site
# answers its own HTML 404 page. Measured on this deployment,
# /health/ready returns `Content-Type: text/html` with a 16KB body --
# that is the web application 404ing, not an API warming up.
#
# Pass `web`, `api` or `full` explicitly to override the detection.
PROFILE="${2:-auto}"

if [[ "${PROFILE}" == "auto" ]]; then
    PROBE_HEADERS="$(curl -s -o /dev/null -D - --max-time 20 "${BASE_URL}/health/ready")" || PROBE_HEADERS=""
    if printf '%s' "${PROBE_HEADERS}" | grep -qi '^content-type:[[:space:]]*text/html'; then
        PROFILE="web"
        echo "--- profile: auto -> web ---"
        echo "    ${BASE_URL}/health/ready answered with text/html, so the"
        echo "    web application is serving that path and no API is deployed"
        echo "    at this origin. The API surface is counted as SKIPPED."
    else
        PROFILE="full"
        echo "--- profile: auto -> full ---"
        echo "    ${BASE_URL}/health/ready did not answer as HTML, so an API"
        echo "    appears to be deployed here. Running the API suite too."
    fi
fi
case "${PROFILE}" in
    web)
        # /dashboard/, not /. The root is a client-side redirect page, and
        # a redirect stub answering 200 proves the edge is up and nothing
        # about whether the application mounted.
        READY_PATH="/dashboard/"
        # /knowledge/ is here because the mount proof should name the screens
        # a user is currently being told exist. It shipped 2026-08-22, and the
        # deploy that carried it proved nothing about it: the deploy workflow
        # probes /auth/callback/, which has existed for weeks, so a build that
        # omitted the new route entirely would still have reported that the
        # deployed site is serving the current build.
        #
        # Add a path here whenever a screen becomes reachable in the sidebar.
        # A route that 404s behind a link the application renders is the exact
        # failure this list exists to catch.
        MOUNT_PATHS=("/" "/dashboard/" "/admin/" "/knowledge/")
        RUN_API_SUITE="no"
        ;;
    api)
        READY_PATH="/health/ready"
        MOUNT_PATHS=("/" "/health/live" "/docs")
        RUN_API_SUITE="yes"
        ;;
    full)
        READY_PATH="/health/ready"
        MOUNT_PATHS=("/" "/health/live" "/docs" "/dashboard/")
        RUN_API_SUITE="yes"
        ;;
    *)
        echo "unknown profile '${PROFILE}' -- expected web, api or full" >&2
        echo "REPORT: passed=0 failed=0 skipped=0 (bad profile; suite did not run)"
        exit 2
        ;;
esac

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
echo "--- profile: ${PROFILE} ---"
echo "--- waiting for ${BASE_URL}${READY_PATH} ---"
DEADLINE=$((SECONDS + 300))
LIVE="no"
while (( SECONDS < DEADLINE )); do
    CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
            "${BASE_URL}${READY_PATH}")" || CODE=""
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
for path in "${MOUNT_PATHS[@]}"; do
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

    # 🔴 THE APPLICATION'S SETTINGS ARE REQUIRED AT IMPORT TIME, AND THIS STEP
    # SUPPLIED NEITHER OF THEM.
    #
    # `app/core/config.py` builds `settings` at module scope, and both
    # `database_url` and `keycloak_issuer` are `Field(...)` -- mandatory. Nearly
    # every test module imports something that reaches `app.core.db`, so with
    # those absent pytest died with **25 collection errors** before running a
    # single test.
    #
    # Measured 2026-08-23 against a healthy deployment: this reported
    # `api-live: passed=0 failed=1` and pointed the reader at the deployment,
    # when nothing was wrong with it. That is precisely the misdiagnosis this
    # script's three-number contract exists to prevent, reproduced one level
    # further in.
    #
    # They are FORWARDED from the caller, never defaulted. A default would aim
    # this suite at whatever database the script's author had in mind -- and
    # for a suite whose entire purpose is "test what is actually deployed",
    # that is the wrong answer in the most convincing direction.
    if [[ -z "${DATABASE_URL:-}" || -z "${KEYCLOAK_ISSUER:-}" ]]; then
        echo "  NOT RUN -- DATABASE_URL and/or KEYCLOAK_ISSUER are not set."
        echo "  These tests import the application, whose settings require both"
        echo "  at import time; without them pytest fails at COLLECTION and the"
        echo "  errors read as deployment faults. Export both and re-run."
        echo "  This is a COVERAGE GAP, counted as skipped. A skip is NOT a pass."
        SKIPPED=$((SKIPPED + 1))
        return 0
    fi

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

    # 🔴 `(^|.*[^0-9])`, NOT `.*[^0-9]`. THE OLD FORM DELETED THE PASSED COUNT
    # ON EVERY FULLY GREEN RUN.
    #
    # `.*[^0-9]([0-9]+) passed` requires a NON-DIGIT before the number. pytest
    # writes the passed count FIRST when nothing failed --
    #
    #     659 passed, 11 skipped, 6 warnings in 133.31s
    #
    # -- so there is no character before "659" and the match failed, yielding
    # "" and defaulting to 0. Measured 2026-08-23: this suite reported
    # `passed=0 failed=0 skipped=11` from a log whose own summary line said
    # **659 passed**.
    #
    # The polarity is the worst available. With failures present the line reads
    # "10 failed, 659 passed, ..." -- a comma and a space precede the number,
    # the match succeeds, and the count is right. So the parser was accurate
    # exactly when the run was broken, and wrong exactly when it was clean:
    # **the greener the run, the more wrong the report.**
    #
    # Nothing caught it because 0 passed / 0 failed reads as a plausible
    # "nothing to run" outcome, and the rc reconciliation below only fires when
    # p+f+s is zero -- 11 skips were enough to satisfy it. This is the same
    # shape as the CRLF and four-field bugs already recorded above it: the
    # counts destroyed by the parser rather than by the deployment.
    local p f s e
    p="$(sed -nE 's/(^|.*[^0-9])([0-9]+) passed.*/\2/p'  <<< "${line}")"; p="${p:-0}"
    f="$(sed -nE 's/(^|.*[^0-9])([0-9]+) failed.*/\2/p'  <<< "${line}")"; f="${f:-0}"
    s="$(sed -nE 's/(^|.*[^0-9])([0-9]+) skipped.*/\2/p' <<< "${line}")"; s="${s:-0}"
    # Collection errors are reported as "errors", not "failed", and are
    # every bit as much a not-working suite.
    e="$(sed -nE 's/(^|.*[^0-9])([0-9]+) errors?.*/\2/p'  <<< "${line}")"; e="${e:-0}"
    f=$((f + e))

    # RECONCILE THE EXIT CODE AGAINST THE PARSED COUNTS.
    #
    # Parsing alone is not enough. pytest exits non-zero for conditions
    # that produce no "N failed" at all -- collection error (2), internal
    # error (3), interrupted (2/3), no tests collected (5), or the
    # interpreter failing to start. Every one of those parsed as
    # 0 passed / 0 failed / 0 skipped and read as a clean pass.
    #
    # That is the exact shape of the five shipped-green-but-broken-on-live
    # incidents this script exists to prevent, so a non-zero rc with
    # nothing parsed is force-counted as a failure rather than trusted
    # (Codex C9).
    if [[ ${rc} -ne 0 && $((p + f + s)) -eq 0 ]]; then
        case ${rc} in
            5) echo "  NO TESTS COLLECTED (rc=5) -- counted as 1 FAILED, not a pass" ;;
            *) echo "  pytest exited ${rc} with no parseable summary -- counted as 1 FAILED" ;;
        esac
        f=1
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
if [[ "${RUN_API_SUITE}" == "yes" ]]; then
    run_pytest "api-live" tests -m "live or not live"
else
    echo
    echo "--- api-live ---"
    echo "  NOT RUN -- profile '${PROFILE}' declares no deployed API."
    echo "  render.yaml deploys the web application only (ADR-009), so there"
    echo "  is nothing at ${BASE_URL} for these tests to talk to. This is a"
    echo "  COVERAGE GAP, counted as skipped. A skip is NOT a pass."
    SKIPPED=$((SKIPPED + 1))
fi

# Playwright, if it is installed. Absence is reported as a GAP rather
# than silently omitted -- a suite that quietly skips its only end-to-end
# coverage reads as "everything passed".
echo
echo "--- e2e (playwright) ---"
if [[ -d "${REPO_ROOT}/tests/e2e" ]] && command -v npx >/dev/null 2>&1; then
    # --reporter=json, not line. Counting check and cross GLYPHS off
    # console output was fragile in every direction: ANSI escapes,
    # reporter formatting changes, a crash before any test ran, or a
    # config error all yield zero matches and therefore zero failures,
    # while the non-zero exit code was never folded in at all -- a
    # guaranteed false green (Codex C10).
    ( cd "${REPO_ROOT}" && PLAYWRIGHT_BASE_URL="${BASE_URL}" \
      npx playwright test --reporter=json ) > "${ARTIFACTS}/e2e.json" 2>"${ARTIFACTS}/e2e.log"
    E2E_RC=$?

    E2E_P=0; E2E_F=0; E2E_S=0
    if command -v python >/dev/null 2>&1; then
        # Read the machine-readable summary. Prints three integers, or
        # nothing at all if the JSON is absent or unparseable -- in which
        # case the rc reconciliation below takes over.
        # `tr -d '\r'` is not decoration. Python on Windows terminates
        # print() with CRLF, so the last field arrived as "0" and the
        # arithmetic below died with "invalid arithmetic operator". The
        # suite then reported passed=0 failed=0 skipped=1 while Playwright
        # had actually run all 14 tests -- the counts were destroyed by the
        # parser, not by the deployment.
        # FOUR variables for FOUR fields. `read` assigns the trailing
        # remainder of the line to the LAST name, so reading three names
        # from a four-field line put "0 0" into E2E_S and every later
        # $((...)) on it died with "syntax error in expression".
        read -r E2E_P E2E_F E2E_S E2E_FLAKY < <(python - "${ARTIFACTS}/e2e.json" <<'PY' | tr -d '\r' || true
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        report = json.load(fh)
except Exception:
    sys.exit(1)

# Read Playwright's OWN `stats` block rather than re-deriving the counts.
#
# The previous version walked the suite tree and asked `test.get("ok")`.
# That key does not exist on a test object -- `ok` lives on the SPEC --
# so it was None for every test, every test fell to the else branch, and
# a fully green run reported 0 passed / 14 failed. A hand-rolled parser
# disagreeing with the tool that produced the file is the same
# "two things that cannot be checked against each other" defect this
# repository keeps hitting; `stats` is the tool's own answer.
#
# `expected`   = passed.  `unexpected` = failed.  `flaky` = passed only
# after a retry, which is NOT a clean pass, so it is surfaced separately
# by the caller rather than folded silently into either column.
stats = report.get("stats")
if isinstance(stats, dict) and "expected" in stats:
    print(stats.get("expected", 0),
          stats.get("unexpected", 0),
          stats.get("skipped", 0),
          stats.get("flaky", 0))
    sys.exit(0)

# Fallback for a report with no stats block: count statuses, using the
# field that actually exists.
passed = failed = skipped = 0
def walk(suite):
    global passed, failed, skipped
    for spec in suite.get("specs", []):
        for test in spec.get("tests", []):
            status = test.get("status")
            if status == "skipped":
                skipped += 1
            elif status == "expected":
                passed += 1
            else:
                failed += 1
    for child in suite.get("suites", []):
        walk(child)
for s in report.get("suites", []):
    walk(s)
print(passed, failed, skipped, 0)
PY
        ) || true
    fi
    # Strip CR at the shell level as well as in the pipeline.
    #
    # Belt and braces on purpose. The `tr` above once held a LITERAL
    # carriage-return byte instead of the two-character escape, so it
    # deleted nothing, every count arrived as "14", and every $((...))
    # below died with "invalid arithmetic operator" -- which left the
    # REPORT reading passed=0 failed=0 while Playwright had just passed 14
    # tests against the live site. Counts destroyed by the reporter are
    # indistinguishable, in the report, from a broken deployment.
    E2E_P="${E2E_P//$''/}"; E2E_F="${E2E_F//$''/}"
    E2E_S="${E2E_S//$''/}"; E2E_FLAKY="${E2E_FLAKY//$''/}"
    E2E_P="${E2E_P:-0}"; E2E_F="${E2E_F:-0}"; E2E_S="${E2E_S:-0}"
    E2E_FLAKY="${E2E_FLAKY:-0}"
    if [[ "${E2E_FLAKY}" != "0" ]]; then
        # COUNTED AS FAILED, not merely mentioned.
        #
        # Playwright exits ZERO when a retry eventually passes, and flaky
        # was being added to none of the three columns -- so a run with
        # flaky tests reported failed=0, exited 0, and its three numbers
        # did not add up to the tests actually executed. A test that only
        # passes on a second attempt against a LIVE site is exactly the
        # signal this suite exists to surface. Raised by Codex.
        echo "  ${E2E_FLAKY} FLAKY (passed only on retry) -- counted as FAILED."
        echo "  A test that needs a retry against a live deployment is not a pass."
        E2E_F=$((E2E_F + E2E_FLAKY))
    fi

    # Same reconciliation as the pytest runner: a non-zero exit with
    # nothing parsed must never read as success.
    if [[ ${E2E_RC} -ne 0 && $((E2E_P + E2E_F + E2E_S)) -eq 0 ]]; then
        echo "  playwright exited ${E2E_RC} with no parseable report -- counted as 1 FAILED"
        E2E_F=1
    fi

    PASSED=$((PASSED + E2E_P))
    FAILED=$((FAILED + E2E_F))
    SKIPPED=$((SKIPPED + E2E_S))
    echo "  e2e: passed=${E2E_P} failed=${E2E_F} skipped=${E2E_S} (rc=${E2E_RC})"

    # 🔴 THE EXCLUDED SPEC IS NAMED, NOT SILENTLY DROPPED.
    #
    # playwright.config.ts skips tests/e2e/shell/api-wiring.spec.ts in
    # LIVE mode, because the API-wiring seam it asserts is compiled OUT
    # of production builds -- the deployed page carries no `api-status`
    # and no `data-source-error` element at all. Left in, it contributed
    # 8 permanent failures that said nothing about the deployment, and a
    # red that never goes away trains the reader to ignore the number
    # that is meant to stop a bad deploy.
    #
    # It is counted here as ONE skip and named, because a coverage gap
    # that is invisible is indistinguishable from coverage.
    if [[ "${PROFILE}" == "web" ]]; then
        echo "  e2e: api-wiring.spec.ts NOT RUN -- its seam is compiled out of"
        echo "       production builds. COVERAGE GAP, counted as skipped."
        SKIPPED=$((SKIPPED + 1))
    fi
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
