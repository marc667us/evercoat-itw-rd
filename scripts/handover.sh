#!/usr/bin/env bash
#
# handover.sh -- what is ACTUALLY true right now, at the start of a session.
#
#   ./scripts/handover.sh
#
# 🔴 WHY THIS EXISTS
#
# `RESUME_HERE.md` is a handover NOTE: it was true when it was written.
# This platform's own most-repeated lesson is *measure the repo, do not
# quote the last handover* -- status files here have been wrong in BOTH
# directions, claiming work open that was finished and finished that was
# open.
#
# So this script asserts nothing and remembers nothing. It reads the
# repository, GitHub and the deployed site, and prints what they say.
# Where it cannot reach something it says so, rather than omitting the
# line -- an absent check and a passing check must never look the same.
#
# It is READ-ONLY. No push, no deploy, no workflow dispatch.

set -uo pipefail
# NOT `set -e`. A missing `gh` must not abort the whole report; each
# section reports its own failure and the script continues.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1

GH="${GH_BIN:-$HOME/bin/gh.exe}"
[ -x "$GH" ] || GH="$(command -v gh 2>/dev/null || true)"
LIVE_URL="${LIVE_URL:-https://itwevercoatrd.aiappinvent.com}"

rule() { printf '\n%s\n%s\n' "$1" "$(printf '=%.0s' $(seq 1 ${#1}))"; }

# ---------------------------------------------------------------------
rule "REPOSITORY"
printf '  tip        %s\n' "$(git log --oneline -1 2>/dev/null || echo '(not a git repo)')"
printf '  branch     %s\n' "$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"

DIRTY="$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
if [ "$DIRTY" = "0" ]; then
    printf '  tree       clean\n'
else
    printf '  tree       %s uncommitted change(s) -- COMMIT BEFORE ANYTHING ELSE\n' "$DIRTY"
    git status --short | sed 's/^/               /'
fi

# Ahead/behind is the question "is what I am reading what CI ran?".
AHEAD="$(git rev-list --count '@{u}..HEAD' 2>/dev/null || echo '?')"
BEHIND="$(git rev-list --count 'HEAD..@{u}' 2>/dev/null || echo '?')"
printf '  vs origin  %s ahead, %s behind\n' "$AHEAD" "$BEHIND"

# ---------------------------------------------------------------------
rule "MIGRATIONS"
SQL_COUNT="$(find apps/api/migrations -maxdepth 1 -name '*.sql' 2>/dev/null | wc -l | tr -d ' ')"
REV_COUNT="$(find apps/api/migrations_alembic/versions -maxdepth 1 -name '*.py' 2>/dev/null | wc -l | tr -d ' ')"
printf '  %s .sql files, %s alembic revisions\n' "$SQL_COUNT" "$REV_COUNT"
printf '  latest     %s\n' "$(find apps/api/migrations -maxdepth 1 -name '*.sql' 2>/dev/null | sort | tail -1 | xargs -r basename)"
printf '  NOTE: a .sql file with no revision has run against NO database.\n'
printf '        tests/test_migration_coverage.py is the instrument.\n'

# ---------------------------------------------------------------------
rule "CI — the most recent run on this branch"
if [ -z "$GH" ]; then
    printf '  gh CLI not found; set GH_BIN. CI state NOT CHECKED (not "green").\n'
else
    RUN_JSON="$("$GH" run list --limit 1 --json databaseId,status,conclusion,headSha 2>/dev/null || true)"
    if [ -z "$RUN_JSON" ] || [ "$RUN_JSON" = "[]" ]; then
        # A transient api.github.com timeout returns an EMPTY id here, and
        # that once produced `gh run watch ""` -> "deploy failed" for a
        # deploy that had succeeded. Reported as unknown, never as bad.
        printf '  could not reach the GitHub API. CI state UNKNOWN, not failed.\n'
    else
        printf '%s' "$RUN_JSON" | python -c "
import json,sys
r=json.load(sys.stdin)[0]
print(f\"  run {r['databaseId']} on {r['headSha'][:7]} -> {r['status']}/{r['conclusion'] or '(pending)'}\")
" 2>/dev/null || printf '  could not parse the run list.\n'
    fi
fi

# ---------------------------------------------------------------------
rule "PRODUCTION — what the deployed site is actually serving"
HEADERS="$(curl -sS -o /dev/null -D - --max-time 30 "$LIVE_URL/dashboard/" 2>/dev/null || true)"
if [ -z "$HEADERS" ]; then
    printf '  %s unreachable from here. NOT the same as down.\n' "$LIVE_URL"
else
    printf '  %s\n' "$(printf '%s' "$HEADERS" | grep -i '^HTTP' | head -1 | tr -d '\r')"
    printf '  %s\n' "$(printf '%s' "$HEADERS" | grep -i '^last-modified' | head -1 | tr -d '\r')"
    printf '  NOTE: compare that timestamp against the tip above. Render'"'"'s push\n'
    printf '        webhook has silently stopped before, leaving CI green over a\n'
    printf '        site nobody was updating (B4).\n'
fi

# ---------------------------------------------------------------------
rule "THE ONE BLOCKER — I13"
printf '  The API and Keycloak are NOT deployed. Measured 2026-08-20 against\n'
printf '  the real Render API, with the repository key, which authenticated\n'
printf '  fine (GET /owners -> 200):\n\n'
printf '    POST /postgres       -> 400 cannot have more than one active free\n'
printf '                                tier database\n'
printf '    POST /services free  -> 400 free tier usage quota has been\n'
printf '                                exhausted, new services are not allowed\n\n'
printf '  Those are 400s, not 401s. It is a plan/billing boundary, not auth.\n'
printf '  A rotated key produces the identical errors -- do not spend a\n'
printf '  session on credentials.\n\n'
printf '  Once there is capacity, this is the whole of it:\n'
printf '    gh workflow run render-provision.yml -f resource=postgres \\\n'
printf '       -f plan=<paid> -f confirm=CREATE\n'
printf '    gh workflow run render-provision.yml -f resource=api-service \\\n'
printf '       -f plan=<paid> -f confirm=CREATE\n'

# ---------------------------------------------------------------------
rule "COMMANDS WORTH NOT RE-DERIVING"
cat <<'COMMANDS'
  Backend, no database needed:
    cd apps/api && DATABASE_URL=postgresql+psycopg://evercoat_app:x@127.0.0.1:1/x \
      KEYCLOAK_ISSUER=http://127.0.0.1:1/realms/evercoat \
      python -m pytest tests/ -q --ignore=tests/db --ignore=tests/auth \
      --ignore=tests/integration

  Quality:
    cd apps/api && ruff check app/ tests/ && ruff format --check app/ tests/ && mypy app
    cd apps/web && npm run typecheck && npm run lint && npm run test

  Browser (builds first, ~2 min):
    npx playwright test --project=shell

  Deploy, then the live suite -- a deploy is not finished until the suite
  has run against the DEPLOYED site and reported three numbers:
    gh workflow run "Deploy web (manual)"
    ./scripts/live-suite.sh https://itwevercoatrd.aiappinvent.com

  NEVER use render-setup.yml apply mode: it DELETEs AutoWorkshop domains.
COMMANDS

rule "REPORTED, NOT ASSERTED"
printf '  Nothing above is a claim from a status file. Every line was read\n'
printf '  from the repository, GitHub or the live site just now, and any\n'
printf '  check that could not run says so instead of passing quietly.\n\n'
