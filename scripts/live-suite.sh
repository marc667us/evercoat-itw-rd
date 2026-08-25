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

# ---------------------------------------------------------------------
# FLAGS FIRST, THEN POSITIONALS.
#
# `--allow-partial` is the ONLY way to make this script report success
# while a capability it needs is absent. It exists because absence is
# sometimes legitimate -- a genuinely deployed site has no local
# database, so `tests/db` cannot run against it and never could -- and
# the alternative designs are both worse:
#
#   * defaulting the missing variables aims the suite at whatever
#     database the author had in mind, which is the wrong answer in the
#     most convincing direction;
#   * letting the absence pass silently is the defect this whole
#     preflight exists to remove (I100).
#
# So the operator must SAY that the run is partial. The report then
# names every absent capability instead of printing a clean green.
ALLOW_PARTIAL="no"
POSITIONAL=()
while (( $# )); do
    case "$1" in
        --allow-partial) ALLOW_PARTIAL="yes"; shift ;;
        --) shift; POSITIONAL+=("$@"); break ;;
        -*) echo "unknown flag '$1' -- expected --allow-partial" >&2
            echo "REPORT: passed=0 failed=0 skipped=0 (bad flag; suite did not run)"
            exit 2 ;;
        *) POSITIONAL+=("$1"); shift ;;
    esac
done
set -- ${POSITIONAL[@]+"${POSITIONAL[@]}"}

BASE_URL="${1:-}"
if [[ -z "${BASE_URL}" ]]; then
    echo "usage: $0 [--allow-partial] <deployed-base-url> [profile]" >&2
    echo "  e.g. $0 https://evercoat.example.com web" >&2
    echo "  profile: web | api | full   (default: auto)" >&2
    echo "  --allow-partial: proceed when a capability is absent," >&2
    echo "                   naming every gap in the report." >&2
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
# 0. PREFLIGHT -- WHAT THIS RUN CAN ACTUALLY COVER, DECIDED BEFORE IT RUNS.
#
# 🔴 I100: THIS SUITE REPORTED GREEN WHILE MOST OF IT NEVER RAN, THREE
#    INDEPENDENT WAYS, AND NONE OF THEM WAS A CODE DEFECT.
#
# Measured 2026-08-25. Every green number this script had ever printed
# depended on environment variables supplied BY HAND at the prompt. The
# script exported none of them and checked none of them, so running it
# exactly as `RESUME_HERE.md` and `CLAUDE.md` §13 document it gave:
#
#   290 passed / 0 failed / 392 skipped
#
# -- a confident, zero-failure report over 290 of 682 tests, with the
# sign-in flow unverified. The three gaps:
#
#   (a) `tests/db/conftest.py` reads `TEST_DB_PORT` and DEFAULTS IT TO
#       5432. This platform's database is on 55432. The fixture times
#       out, calls `pytest.skip`, and 341 tests vanish without a single
#       failure.
#   (b) `tests/e2e/shell/sign-in.spec.ts` self-skips without
#       `TEST_KEYCLOAK_PASSWORD` -- so the test written on 08-24
#       SPECIFICALLY to stop sign-in breaking silently does not run in
#       the live suite that exists to catch it. Its own header says so.
#   (c) `--project=api` does not exist in LIVE mode (`playwright.config.ts`
#       drops it), so a total that assumes both Playwright projects ran
#       is wrong. The projects that ran are named in the e2e step below,
#       read from Playwright's own report rather than assumed.
#
# THE FIX IS NOT TO REMEMBER TO EXPORT THEM. It is to make the script
# DEMAND what it needs and FAIL LOUDLY, which is what this section does.
#
# 🔴 AND THE FIX IS NOT TO DEFAULT THEM EITHER. Against a genuinely
# deployed site there is no local database and those 341 tests
# legitimately cannot run; hard-coding a port would aim the suite at
# whatever database the author had in mind and call the result live
# coverage. So absence is allowed -- but only when the operator SAYS so
# with `--allow-partial`, and it is named in the report either way.
#
# THE THREE STATES AND WHAT EACH MEANS:
#
#   CONFIGURED  every variable present. The tests will run, and if they
#               skip anyway that is a FAILURE, not a gap -- see the
#               unexpected-skip guard in `run_pytest`.
#   ABSENT      no variable present. A legitimate absence is possible,
#               so this fails unless `--allow-partial`.
#   PARTIAL     some present, some not. ALWAYS a hard failure: nobody
#               half-configures a capability on purpose, and a partially
#               configured one skips exactly like an absent one while
#               looking, at the prompt, like it was set up.
# ---------------------------------------------------------------------
PREFLIGHT_FAILURES=0
PREFLIGHT_GAPS=()

preflight_fail() {
    PREFLIGHT_FAILURES=$((PREFLIGHT_FAILURES + 1))
    echo
    echo "  PREFLIGHT FAILURE: $*"
}

# Does anything answer on host:port? Used to tell a legitimate absence
# (there is no database here) from a misconfiguration (there is one, and
# the suite was not pointed at it) -- the exact discrimination that would
# have caught (a).
tcp_answers() {
    local host="$1" port="$2"
    [[ -z "${host}" || -z "${port}" ]] && return 1
    # 🔴 VALIDATED, BECAUSE THIS IS THE ONE PLACE IN THE PREFLIGHT WHERE AN
    # ENVIRONMENT VARIABLE BECOMES SHELL TEXT. `bash -c` interpolates both,
    # so a host carrying shell syntax would be EXECUTED. And an IPv6 literal
    # cannot be spelled in /dev/tcp/HOST/PORT at all: unvalidated it would
    # read as a refused connection, silently turning a misconfiguration into
    # a "legitimate absence" -- the exact conversion this preflight exists to
    # prevent. Raised by Codex.
    [[ "${host}" =~ ^[A-Za-z0-9._-]+$ ]] || return 2
    [[ "${port}" =~ ^[0-9]+$ ]] || return 2
    if command -v timeout >/dev/null 2>&1; then
        timeout 3 bash -c "exec 3<>/dev/tcp/${host}/${port}" >/dev/null 2>&1
    else
        # Bounded by the operating system's TCP timeout, NOT by three
        # seconds. Announced above rather than claimed away here.
        ( exec 3<>"/dev/tcp/${host}/${port}" ) >/dev/null 2>&1
    fi
}

# 🔴 THE ADDRESS THE APPLICATION ITSELF IS POINTED AT.
#
# Codex, correctly: probing a hard-coded list of well-known ports cannot
# support the categorical claim that --allow-partial "does not cover a
# database that is present but unused". A database on 15432 would answer
# nothing on that list and the declared gap would be granted -- a comment
# asserting a rule the code did not implement, which is this repository's
# most repeated defect, written by me one screen above the code.
#
# DATABASE_URL is mandatory whenever the api-live suite runs, and it names
# the database this very run talks to. So the probe target is DERIVED from
# the configuration the run already has, not guessed.
DB_URL_HOST=""
DB_URL_PORT=""
if [[ "${DATABASE_URL:-}" =~ @([A-Za-z0-9._-]+):([0-9]+)/ ]]; then
    DB_URL_HOST="${BASH_REMATCH[1]}"
    DB_URL_PORT="${BASH_REMATCH[2]}"
fi

# Sets PF_STATUS and PF_UNSET, and prints one row of the coverage table.
preflight_capability() {
    local name="$1" governs="$2"; shift 2
    local v
    local -a have=() missing=()
    for v in "$@"; do
        if [[ -n "${!v:-}" ]]; then have+=("${v}"); else missing+=("${v}"); fi
    done
    if   (( ${#missing[@]} == 0 )); then PF_STATUS="CONFIGURED"
    elif (( ${#have[@]}    == 0 )); then PF_STATUS="ABSENT"
    else                                 PF_STATUS="PARTIAL"
    fi
    PF_UNSET="${missing[*]-}"
    printf '  %-19s %-11s %s\n' "${name}" "${PF_STATUS}" "${governs}"
    if [[ "${PF_STATUS}" != "CONFIGURED" ]]; then
        printf '  %-19s %-11s unset: %s\n' "" "" "${PF_UNSET}"
    fi
}

# Applies the three-state rule above to one capability.
preflight_judge() {
    local name="$1" status="$2" unset_vars="$3" cost="$4"
    case "${status}" in
        CONFIGURED) return 0 ;;
        PARTIAL)
            preflight_fail "${name} is HALF configured -- unset: ${unset_vars}
    A partially configured capability skips exactly like an absent one,
    and looks configured at the prompt. That is a misconfiguration, not a
    legitimate absence, so --allow-partial does NOT cover it.
    Cost if it runs anyway: ${cost}"
            ;;
        ABSENT)
            if [[ "${ALLOW_PARTIAL}" == "yes" ]]; then
                PREFLIGHT_GAPS+=("${name} -- ${cost} (unset: ${unset_vars})")
            else
                preflight_fail "${name} is not configured -- unset: ${unset_vars}
    Cost: ${cost}
    Export those variables, or re-run with --allow-partial to declare the
    run partial. A skip is not a pass, and this script will not print a
    clean three-number report over coverage it did not have."
            fi
            ;;
    esac
}

echo
echo "--- preflight: what this run can actually cover ---"
if ! command -v timeout >/dev/null 2>&1; then
    echo "  NOTE: 'timeout' is unavailable here, so the database probes below"
    echo "        are bounded by the operating system's TCP timeout rather"
    echo "        than by three seconds. They cannot hang forever, but they"
    echo "        can be slow against a filtered address."
fi
printf '  %-19s %-11s %s\n' "capability" "status" "governs"
printf '  %-19s %-11s %s\n' "-------------------" "-----------" "-------"

if [[ "${RUN_API_SUITE}" == "yes" ]]; then
    preflight_capability "api-import" "the whole api-live suite -- 682 tests" \
        DATABASE_URL KEYCLOAK_ISSUER
    PF_API_IMPORT="${PF_STATUS}"; PF_API_IMPORT_UNSET="${PF_UNSET}"

    # 🔴 NOT JUST tests/db. This said "341 tests" until it was measured:
    # tests/auth/conftest.py uses the SAME owner/app fixtures, and without
    # them `pytest tests/auth` reports 12 passed / 58 skipped. The run that
    # exposed I100 skipped 392, and a preflight that understates what its own
    # absence costs is a quieter version of the defect it exists to catch.
    preflight_capability "db-suite" "tests/db (341) + tests/auth's db-backed tests -- 392 skipped when this broke" \
        TEST_DB_HOST TEST_DB_PORT POSTGRES_DB \
        TEST_OWNER_USER TEST_OWNER_PASSWORD APP_DB_USER APP_DB_PASSWORD
    PF_DB="${PF_STATUS}"; PF_DB_UNSET="${PF_UNSET}"

    preflight_capability "auth-integration" "tests/integration -- 11 tests" \
        TEST_KEYCLOAK_URL TEST_API_URL TEST_KEYCLOAK_PASSWORD TEST_ORGANIZATION_ID
    PF_AUTH="${PF_STATUS}"; PF_AUTH_UNSET="${PF_UNSET}"
else
    echo "  (api-live not selected by profile ${PROFILE}; its capabilities are not required)"
    PF_API_IMPORT="n/a"; PF_DB="n/a"; PF_AUTH="n/a"
fi

preflight_capability "sign-in-round-trip" \
    "tests/e2e/shell/sign-in.spec.ts -- the flow every human uses" \
    TEST_KEYCLOAK_PASSWORD
PF_SIGNIN="${PF_STATUS}"; PF_SIGNIN_UNSET="${PF_UNSET}"

if [[ "${RUN_API_SUITE}" == "yes" ]]; then
    preflight_judge "api-import" "${PF_API_IMPORT}" "${PF_API_IMPORT_UNSET}" \
        "pytest dies at COLLECTION -- app/core/config.py makes both mandatory at import time -- and the collection errors read as deployment faults"
    preflight_judge "db-suite" "${PF_DB}" "${PF_DB_UNSET}" \
        "392 tests skipped silently the day this was measured -- all 341 in tests/db, plus 58 of the 70 in tests/auth, which shares the same fixtures. The entire RLS and tenant-isolation boundary goes unmeasured"
    preflight_judge "auth-integration" "${PF_AUTH}" "${PF_AUTH_UNSET}" \
        "11 tests skip; no real token is ever minted against the deployed realm"
fi
# Stricter than before, on purpose: a live run that cannot exercise sign-in
# must not print a clean three-number report. --allow-partial still runs the
# spec's password-free callback guard, which is the narrow I96 regression
# test; what it cannot run is the round trip. Codex flagged the change in
# behaviour, and the answer is to state what the operator gets, not to
# soften the default.
preflight_judge "sign-in-round-trip" "${PF_SIGNIN}" "${PF_SIGNIN_UNSET}" \
    "the sign-in ROUND TRIP is NOT verified -- the gap that let 713 green sit beside a 404 sign-in on 08-24 (I96). The password-free callback guard in the same spec still runs under --allow-partial"

# A port that is not a number never reaches the probe below. /dev/tcp is
# opened through `bash -c` with the value interpolated, so a junk value is
# both a guaranteed connection failure -- reported, confusingly, as "nothing
# answers there" -- and the one place in this preflight where an environment
# variable becomes shell text.
if [[ "${RUN_API_SUITE}" == "yes" && -n "${TEST_DB_PORT:-}" ]] &&
   [[ ! "${TEST_DB_PORT}" =~ ^[0-9]+$ ]]; then
    preflight_fail "TEST_DB_PORT is not a number: '${TEST_DB_PORT}'.
    Every db-suite connection would fail and pytest would report those 341
    tests as SKIPPED, which is the shape this preflight exists to catch."
    TEST_DB_PORT=""
fi

# 🔴 A DATABASE IS HERE AND THE SUITE WAS NOT POINTED AT IT.
#
# This is the discriminator that separates "no database, so those tests
# cannot run" from "a database is running within this run's reach and the
# suite skipped 341 tests anyway" -- which is what happened on 08-25 and
# what --allow-partial must NOT be able to wave through.
#
# WHAT IS PROBED, EXACTLY -- so this comment states the code and not a wish:
#   1. the host:port inside DATABASE_URL, which the api-live suite is
#      already talking to and therefore proves a database is in reach.
#      A URL with NO explicit port does not match, and falls through to
#      the guesses below rather than assuming 5432 -- named here because
#      an undocumented blind spot is how the last version of this comment
#      came to claim more than the code did;
#   2. TEST_DB_HOST:TEST_DB_PORT, where a half-configured attempt points;
#   3. TEST_DB_HOST at 55432 and 5432, this platform's two ports.
# A database on some other address reachable by neither the application nor
# any of the variables is NOT detected, and that is the honest boundary of
# this check rather than a claim about every database in the world.
if [[ "${RUN_API_SUITE}" == "yes" && "${PF_DB}" != "CONFIGURED" ]]; then
    PF_DB_HOST="${TEST_DB_HOST:-localhost}"
    PF_PROBES=()
    [[ -n "${DB_URL_HOST}" ]] && PF_PROBES+=("${DB_URL_HOST}:${DB_URL_PORT}")
    for candidate_port in "${TEST_DB_PORT:-5432}" 55432 5432; do
        PF_PROBES+=("${PF_DB_HOST}:${candidate_port}")
    done
    for probe in "${PF_PROBES[@]}"; do
        if tcp_answers "${probe%:*}" "${probe##*:}"; then
            preflight_fail "a database ANSWERS on ${probe}, and the db-suite variables are not set.
    That is a misconfiguration, not a legitimate absence: the 341 tests in
    tests/db, and the 58 of 70 in tests/auth that share its fixtures, could
    run against a database this run can already reach, and will skip
    instead. --allow-partial does not cover it. Export
    TEST_DB_HOST / TEST_DB_PORT / POSTGRES_DB / TEST_OWNER_USER /
    TEST_OWNER_PASSWORD / APP_DB_USER / APP_DB_PASSWORD."
            break
        fi
    done
fi

# 🔴 AND THE MIRROR IMAGE: CONFIGURED, BUT POINTED AT A DEAD PORT.
#
# Exactly the 290/0/392 shape. TEST_DB_PORT defaulting to 5432 on a host
# whose database is on 55432 produced a connection timeout inside a
# session fixture, which pytest reports as a SKIP. Catching it here costs
# three seconds; catching it in the report costs a session.
if [[ "${RUN_API_SUITE}" == "yes" && "${PF_DB}" == "CONFIGURED" ]]; then
    if ! tcp_answers "${TEST_DB_HOST}" "${TEST_DB_PORT}"; then
        preflight_fail "db-suite is CONFIGURED but NOTHING ANSWERS on ${TEST_DB_HOST}:${TEST_DB_PORT}.
    The session fixture will time out and pytest will report ~392 SKIPS,
    which is indistinguishable in the report from tests that were never
    meant to run. Fix the host/port before running the suite."
    fi
fi

if (( PREFLIGHT_FAILURES > 0 )); then
    echo
    echo "=================================================================="
    echo " PREFLIGHT FAILED -- ${PREFLIGHT_FAILURES} problem(s). THE SUITE DID NOT RUN."
    echo "=================================================================="
    echo " This script will not report three numbers over coverage it does"
    echo " not have. Fix the above, or pass --allow-partial to declare a"
    echo " deliberately partial run -- which does NOT cover a PARTIAL"
    echo " capability, nor a database reachable at an address this run"
    echo " is already configured to use."
    echo "REPORT: passed=0 failed=0 skipped=0 (preflight failed; suite did not run)"
    exit 2
fi

if (( ${#PREFLIGHT_GAPS[@]} > 0 )); then
    echo
    echo "  --allow-partial: proceeding with ${#PREFLIGHT_GAPS[@]} declared gap(s)."
    echo "  These are NOT covered by any number in the report below:"
    for gap in "${PREFLIGHT_GAPS[@]}"; do
        echo "    - ${gap}"
    done
fi

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

# 🔴 ONE SKIP CAN HIDE HUNDREDS OF TESTS, AND THE REPORT COULD NOT SAY SO.
#
# A capability that is absent -- no deployed API, no Playwright, no
# DATABASE_URL -- is counted as ONE skip, because there is no run to read a
# test count from. That is unavoidable, and it is also how `1 skipped` stood
# in for 682 absent tests. So every such gap is NAMED here as well as
# counted, and the report says how many of its skips are capability-level.
# The three numbers keep their contract; they stop being the whole story on
# their own.
GAP_CAPABILITIES=()

record_gap() {
    GAP_CAPABILITIES+=("$1")
    SKIPPED=$((SKIPPED + 1))
}

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
        echo "  🔴 ONE skip stands here for the WHOLE ${label} suite -- 682 tests"
        echo "     for api-live. The preflight above exists to make this branch"
        echo "     unreachable; if you are reading it, the preflight was bypassed."
        record_gap "${label} -- not run at all: DATABASE_URL and/or KEYCLOAK_ISSUER unset"
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

    # 🔴 A COUNT IS NOT AN EXPLANATION. NAME WHAT SKIPPED.
    #
    # `290 passed / 0 failed / 392 skipped` was an honest set of numbers and
    # told the reader nothing about WHICH 392 or WHY, so it read as "some
    # tests need something I have not got" rather than "the entire RLS and
    # tenant-isolation boundary went unmeasured because a port was wrong".
    # pytest already computes this under `-rs`; it was being written to a log
    # nobody opened.
    if grep -qE '^SKIPPED' "${logfile}"; then
        echo "  --- what skipped, and why (pytest -rs) ---"
        grep -E '^SKIPPED' "${logfile}" | sed 's/^/    /'
    fi

    # 🔴 A CAPABILITY THE PREFLIGHT CALLED CONFIGURED, WHOSE TESTS SKIPPED
    #    ANYWAY, IS A MISCONFIGURATION WEARING A COVERAGE GAP'S CLOTHES.
    #
    # The preflight can only prove the variables are SET and that something
    # answers on the port. Whether the credentials are right, the database is
    # the right one, or the realm has the user -- only the run itself knows,
    # and it expresses all three as a skip. So the preflight's promise is
    # closed HERE: declared configured, then skipped, is a FAILURE.
    local unexpected=0
    if [[ "${PF_DB:-n/a}" == "CONFIGURED" ]] &&
       grep -E '^SKIPPED' "${logfile}" |
       grep -qiE 'no database available|no application-role connection'; then
        echo "  🔴 db-suite was CONFIGURED and its tests SKIPPED ANYWAY."
        echo "     The variables are set and something answers on the port, so"
        echo "     this is credentials, database name, or roles -- not absence."
        echo "     COUNTED AS FAILED. A configured capability that skips is a"
        echo "     misconfiguration, and it is exactly what I100 was."
        unexpected=$((unexpected + 1))
    fi
    if [[ "${PF_AUTH:-n/a}" == "CONFIGURED" ]] &&
       grep -E '^SKIPPED' "${logfile}" |
       grep -qiE 'needs a running Keycloak and API'; then
        echo "  🔴 auth-integration was CONFIGURED and its tests SKIPPED ANYWAY."
        echo "     COUNTED AS FAILED, for the same reason."
        unexpected=$((unexpected + 1))
    fi
    f=$((f + unexpected))

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
    record_gap "api-live -- 682 tests not run: profile '${PROFILE}' declares no deployed API"
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

# 🔴 `json.load` IS WRONG HERE: PLAYWRIGHT WRITES ONE REPORT PER PROJECT.
#
# `playwright.config.ts` defines several projects, and with `--reporter=json`
# each one emits its own complete JSON document to the SAME stdout. The file is
# therefore a CONCATENATION, and strict parsing dies on the second document:
#
#     json.decoder.JSONDecodeError: Extra data: line 1187 column 4 (char 37826)
#
# Measured 2026-08-23. Playwright had run 31 tests and passed all 31
# (`expected: 31, unexpected: 0`, 918s). The parser raised, exited 1, and the
# suite reported `e2e: passed=0 failed=0 skipped=0` -- a fully green
# fifteen-minute run contributing NOTHING to the totals, and not flagged,
# because the reconciliation below only fired on a non-zero exit code.
#
# So: decode EVERY document in the stream and sum their stats. `raw_decode`
# returns where each object ended, which is the documented way to walk
# concatenated JSON; skipping a byte on failure keeps a truncated tail (a
# killed run) from losing the reports that did complete before it.
def _documents(text):
    dec = json.JSONDecoder()
    i, n = 0, len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n":
            i += 1
        if i >= n:
            return
        try:
            obj, end = dec.raw_decode(text, i)
            i = end
            if isinstance(obj, dict):
                yield obj
        except json.JSONDecodeError:
            i += 1

try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        raw = fh.read()
except Exception:
    sys.exit(1)

reports = [d for d in _documents(raw) if isinstance(d.get("stats"), dict)]
if reports:
    totals = {"expected": 0, "unexpected": 0, "skipped": 0, "flaky": 0}
    for r in reports:
        for key in totals:
            totals[key] += r["stats"].get(key, 0) or 0
    print(totals["expected"], totals["unexpected"], totals["skipped"], totals["flaky"])
    sys.exit(0)

# No stats anywhere. Fall through to the single-document path below, which
# still handles a report shaped differently by a future Playwright version.
try:
    report = json.loads(raw)
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
    # 🔴 ZERO COUNTS ARE A FAILURE WHATEVER THE EXIT CODE SAID.
    #
    # This condition used to require `E2E_RC -ne 0`, so it only fired when
    # Playwright had ALREADY failed. A run that exited 0 while the parser
    # extracted nothing sailed through as `passed=0 failed=0 skipped=0` and was
    # added to the totals as zero.
    #
    # Measured 2026-08-23: Playwright ran 31 tests, passed all 31, took 918s —
    # and contributed NOTHING to the report, silently, because its multi-project
    # output could not be parsed and its exit code was 0. That is this
    # platform's most-repeated defect wearing yet another face: *an empty
    # requirement set rendered "ALL REQUIREMENTS PASSED"*.
    #
    # An end-to-end suite that reports no tests has not passed; it has not run,
    # and the two must never be the same outcome. If Playwright is genuinely
    # absent this branch is unreachable — the enclosing `if` already checks for
    # `tests/e2e` and `npx`, and reports the absence as a gap.
    if [[ $((E2E_P + E2E_F + E2E_S)) -eq 0 ]]; then
        if [[ ${E2E_RC} -ne 0 ]]; then
            echo "  playwright exited ${E2E_RC} with no parseable report -- counted as 1 FAILED"
        else
            echo "  playwright exited 0 but reported NO TESTS -- counted as 1 FAILED."
            echo "  A suite that ran nothing has not passed. Check ${ARTIFACTS}/e2e.json:"
            echo "  a non-empty report here means the PARSER failed, not the deployment."
        fi
        E2E_F=1
    fi

    # 🔴 (c) OF I100: NAME THE PROJECTS THAT ACTUALLY RAN.
    #
    # `--project=api` does not exist in LIVE mode -- playwright.config.ts
    # drops it, because there is no deployed API to point it at -- so any
    # total that assumes both projects ran is wrong by the size of the api
    # project. Read the names out of Playwright's OWN report rather than
    # restating what the config is believed to do; the two have disagreed
    # before, and only one of them is what ran.
    #
    # The same pass lists every test Playwright marked skipped, by file, so a
    # self-skipping spec can never again be invisible in this output.
    # 🔴 TRUNCATE BEFORE, NOT INSIDE. `tmp/live-suite/` persists between runs,
    # and if python is absent the redirect below never happens -- so the
    # guards would read the PREVIOUS run's detail file and answer questions
    # about a run that is not this one. Stale artifacts faking a result is a
    # defect this platform has shipped before.
    E2E_DETAIL="${ARTIFACTS}/e2e-detail.txt"
    : > "${E2E_DETAIL}"

    if command -v python >/dev/null 2>&1; then
        python - "${ARTIFACTS}/e2e.json" > "${E2E_DETAIL}" 2>/dev/null <<'PYDETAIL' || true
import json, sys

def documents(text):
    dec = json.JSONDecoder()
    i, n = 0, len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n":
            i += 1
        if i >= n:
            return
        try:
            obj, end = dec.raw_decode(text, i)
            i = end
            if isinstance(obj, dict):
                yield obj
        except json.JSONDecodeError:
            i += 1

try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        raw = fh.read()
except Exception:
    sys.exit(0)

projects, statuses = [], []

def walk(suite, inherited):
    path = suite.get("file") or inherited
    for spec in suite.get("specs", []):
        spec_file = spec.get("file") or path
        for test in spec.get("tests", []):
            # EVERY test, not only the skipped ones. A guard that can only
            # see skips cannot tell "this test ran and passed" from "the
            # parser produced nothing", and those must never be the same
            # answer -- that is how a suite reporting no tests read as a
            # pass twice in this repository already.
            statuses.append((test.get("status") or "unknown",
                             spec_file, spec.get("title", "")))
    for child in suite.get("suites", []):
        walk(child, path)

for report in documents(raw):
    for project in (report.get("config") or {}).get("projects") or []:
        name = project.get("name")
        if name and name not in projects:
            projects.append(name)
    for suite in report.get("suites", []):
        walk(suite, "")

for name in projects:
    print("PROJECT", name)
for status, spec_file, title in statuses:
    print("STATUS", status, spec_file, "::", title)
PYDETAIL
    fi

    E2E_PROJECTS="$(sed -nE 's/^PROJECT (.*)$/\1/p' "${E2E_DETAIL}" | tr '\n' ' ')"
    E2E_PROJECTS="${E2E_PROJECTS%% }"
    if [[ -n "${E2E_PROJECTS}" ]]; then
        echo "  e2e projects that ran: ${E2E_PROJECTS}"
    else
        echo "  e2e projects that ran: UNKNOWN -- Playwright's report named none."
    fi
    if grep -q '^STATUS skipped ' "${E2E_DETAIL}"; then
        echo "  --- e2e tests that skipped ---"
        sed -nE 's/^STATUS skipped (.*)$/    \1/p' "${E2E_DETAIL}"
    fi

    # 🔴 (b) OF I100: THE SIGN-IN ROUND TRIP SELF-SKIPS, AND A SELF-SKIP IS
    #    INVISIBLE IN A THREE-NUMBER REPORT.
    #
    # sign-in.spec.ts calls `test.skip` when TEST_KEYCLOAK_PASSWORD is unset.
    # The preflight refuses to start without it, so reaching this branch means
    # the password was present and the test skipped for some OTHER reason --
    # which is a failure, not a gap. Its own header states the rule this
    # enforces: "if the round trip skips in a LIVE run, the sign-in flow was
    # NOT verified".
    # 🔴 ASK WHETHER IT RAN, NOT ONLY WHETHER IT SKIPPED.
    #
    # An absence-only test passes against an empty page, and a skip-only
    # guard passes against an empty report: if the JSON is unparseable, or
    # python is missing, or the spec was never collected, the detail file is
    # empty, `grep` finds no skip, and the guard reports nothing wrong about
    # a flow it never saw. So BOTH directions are asserted -- at least one
    # test in that file finished as `expected`, and none of them skipped.
    #
    # sign-in.spec.ts holds two tests: the round trip, which self-skips
    # without TEST_KEYCLOAK_PASSWORD, and a callback guard that needs no
    # password. Requiring only "one of them ran" would be satisfied by the
    # guard alone while the round trip skipped -- the exact thing being
    # checked for -- which is why the no-skips half is not redundant.
    if [[ "${PF_SIGNIN}" == "CONFIGURED" ]]; then
        SIGNIN_RAN="$(grep -c '^STATUS expected .*sign-in\.spec\.ts' "${E2E_DETAIL}")" || SIGNIN_RAN=0
        SIGNIN_SKIPPED="$(grep -c '^STATUS skipped .*sign-in\.spec\.ts' "${E2E_DETAIL}")" || SIGNIN_SKIPPED=0
        if (( SIGNIN_SKIPPED > 0 )); then
            echo "  🔴 ${SIGNIN_SKIPPED} test(s) in sign-in.spec.ts SKIPPED while their"
            echo "     credentials were set. That spec's own header states the rule:"
            echo "     a skip there means the sign-in flow was NOT verified. It is the"
            echo "     gap that let 713 green sit beside a 404 sign-in on 08-24."
            echo "     COUNTED AS FAILED."
            E2E_F=$((E2E_F + SIGNIN_SKIPPED))
        fi
        if (( SIGNIN_RAN == 0 )); then
            echo "  🔴 NO test in sign-in.spec.ts is reported as having RUN."
            echo "     Either the spec was not collected, or this detail file could"
            echo "     not be produced -- and 'the flow is fine' and 'nothing looked"
            echo "     at the flow' must never be the same outcome. COUNTED AS FAILED."
            echo "     Detail file: ${E2E_DETAIL}"
            E2E_F=$((E2E_F + 1))
        fi
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
        record_gap "e2e api-wiring.spec.ts -- excluded in LIVE mode: its seam is compiled out of production builds"
    fi
else
    echo "  NOT RUN -- tests/e2e absent or npx unavailable."
    echo "  This is a COVERAGE GAP, counted as skipped, not as a pass."
    record_gap "e2e -- the entire end-to-end suite not run: tests/e2e absent or npx unavailable"
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
if (( ${#GAP_CAPABILITIES[@]} > 0 )); then
    if (( ${#GAP_CAPABILITIES[@]} == 1 )); then
        echo " 1 of those skips is CAPABILITY-LEVEL -- one skip standing for"
        echo " however many tests did not run:"
    else
        echo " ${#GAP_CAPABILITIES[@]} of those skips are CAPABILITY-LEVEL -- one skip each,"
        echo " standing for however many tests did not run:"
    fi
    for gap in "${GAP_CAPABILITIES[@]}"; do
        echo "   - ${gap}"
    done
    echo "------------------------------------------------------------------"
fi
if (( ${#PREFLIGHT_GAPS[@]} > 0 )); then
    echo " DECLARED PARTIAL (--allow-partial). Nothing above covers these:"
    for gap in "${PREFLIGHT_GAPS[@]}"; do
        echo "   - ${gap}"
    done
    echo "------------------------------------------------------------------"
fi
if [[ ${SKIPPED} -gt 0 ]]; then
    echo " NOTE: ${SKIPPED} skipped. A skip is not a pass -- read the logs"
    echo "       in ${ARTIFACTS} before calling this deploy finished."
fi
echo "=================================================================="

# The exit code is for CI. The REPORT above is for the human, and it is
# the report -- not this number -- that answers "did the deploy work".
[[ ${FAILED} -eq 0 ]] && exit 0 || exit 1
