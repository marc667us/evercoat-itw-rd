# ▶ RESUME HERE — EvercoatITWRD APP

## 🔴 RENDER IS RETIRED. THIS APP RUNS LOCALLY, SHARED BY TUNNEL.

**Owner decision, 2026-08-21: $0 on Render.** Settled by measurement, not
preference: Keycloak 26 in production mode under a hard 512 MB cap is
**OOM-killed at 451.6 MiB (exit 137)**, and Render has nothing between Starter
($7 / 512 MB) and Standard ($25 / 2 GB). Evercoat on Render is API $7 +
Keycloak $25 + Postgres $6 = **$38/month** against a $30 ceiling.

All apps here are prototypes and zero-cost is a hard rule. **Do not re-open
the Render hosting question without new information.**

The free **static site** stays — `itwevercoatrd.aiappinvent.com` costs nothing
and keeps a working certificate.

### Run it locally, share it with a client

```bash
"C:/Users/USER/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe" start evercoat-postgres
docker compose -f infrastructure/compose/docker-compose.yml up -d
C:/Users/USER/cloudflared.exe tunnel --url http://localhost:18081
```

Caddy fronts web + api + keycloak on **18081**, so a client needs **one** URL.

⚠️ `NEXT_PUBLIC_*` is inlined at **BUILD** time, so a random quick-tunnel URL
means rebuilding the web bundle each restart. One `cloudflared tunnel login`
gives a stable named tunnel and ends that — a browser step, the owner's to do.

✅ Full session record and every script:
`C:\Users\USER\Documents\session-archives\2026-08-21\`

---

**Session 2026-08-21. Read this file, then `TODO.md`.**

Repository: **https://github.com/marc667us/evercoat-itw-rd** (PUBLIC), branch
`master`. Tip **`c358625`**, working tree clean, pushed.
**CI 5 of 5 GREEN.** Local API suite **416 passed / 0 failed / 0 skipped**.

Run `./scripts/handover.sh` first — it prints the repo tip, CI conclusion,
what production is actually serving, and the next command to run.

---

## ▶ THE THREE THINGS THAT CHANGED TODAY

### 1. 🔴 THE LOCAL DATABASE WORKS. IT ALWAYS COULD HAVE.

Every previous session recorded *"Docker on this host is WEDGED — nothing
answers on 5432 or 55432, so every database test's first execution is CI."*

**That was wrong.** Docker Desktop had simply never been started, and it is
not at the standard path — it is a user-level install at
`%LOCALAPPDATA%\Programs\DockerDesktop\`. `evercoat-postgres` existed the
whole time, exited 137 (OOM-killed).

```bash
"C:/Users/USER/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe" start evercoat-postgres
```

It comes up healthy on port **55432**. The database is now at migration head.
To run the db suite:

```bash
cd apps/api
TEST_DB_HOST=localhost TEST_DB_PORT=55432 POSTGRES_DB=evercoat_itw_rd \
TEST_OWNER_USER=evercoat_owner TEST_OWNER_PASSWORD=ci-owner \
APP_DB_USER=evercoat_app APP_DB_PASSWORD=ci-app \
DATABASE_URL="postgresql+psycopg://evercoat_app:ci-app@localhost:55432/evercoat_itw_rd" \
KEYCLOAK_ISSUER="http://127.0.0.1:1/realms/evercoat" \
python -m pytest tests/ -q --ignore=tests/auth --ignore=tests/integration
```

The role passwords are set on the container to match CI's (`ci-owner` /
`ci-app`); the superuser is `postgres` / `dev-superuser-pw`. To migrate:
`MIGRATION_DATABASE_URL="postgresql+psycopg://postgres:dev-superuser-pw@localhost:55432/evercoat_itw_rd" python -m alembic upgrade head`

⚠️ **Host RAM is 7.92 GB with very little free.** The 7 `aw-*` containers
auto-start with Docker. A stray `nginxdemos/hello` container
(`adoring_lederberg`) was stopped to make room — it belongs to nothing.
**Do not stop any `aw-*` container.**

**This matters more than it sounds.** Three defects found today were found
*only* because the suite could run locally against a real PostgreSQL — CI had
been green over all three.

### 2. 🔴 THE DEPLOY BLOCKER IS STRUCTURAL, NOT A WAITING GAME — ADR-027

The operator's rules as of today: **zero cost, strictly**, and **no task may
be assigned to them** (no signup, no interactive login, no dashboard action).
Under those two rules:

| | |
|---|---|
| **Railway (ADR-026)** | 🔴 **REVERSED.** It has **no free tier** — $5 of credit for 30 days, then $1/month, then Hobby at $5/month minimum for anything with a database. It was never zero-cost compliant. **Do not restart this path.** |
| **Render free web service** | Re-measured today: `POST /services plan=free` → **400 "free tier usage quota has been exhausted"** |
| **Render free database** | **400 "cannot have more than ONE active free tier database"** — `autoworkshop-postgres` holds it and expires **2026-09-01**, when a live AutoWorkshop needs it back |

🔴 **The database limit is per WORKSPACE, so waiting for the monthly
instance-hour reset does not help.** Evercoat can obtain a free Render
database only by taking the slot another running application depends on.
Waiting changes *who* is broken, not *whether*.

**Consequence, plainly: under the current rules there is no provider on which
this app's API and Keycloak can be deployed.** The web tier stays on Render
as a static site with a working certificate.

Best measured alternative for whenever that constraint changes: **Coolify
(open source) on Oracle Cloud Always Free** — permanent, 4 ARM cores, 24 GB,
no deploy cap, no sleep, no cold start. Costs exactly one signup. Full
compliance matrix (zero cost / no card / no owner action / supports an
iterative loop) in `Desktop\Evercoat-Hosting-Options-2026-08-21.pdf`.

⚠️ There is **exactly one** Render workspace, `tea-d86fu8mk1jcs7397i70g`
"My Workspace". Solar, AutoWorkshop and Evercoat's web tier are all already
in it. The operator's "no new workspace" rule is structurally satisfied.

### 3. THE DIGITAL THREAD'S TWO OPEN ENDS ARE CLOSED — I6 AND I7

Both functions existed, were correct, and **had no caller**.

* **I6** — `open_failure_for_failed_test` is now called from
  `complete_execution`, the only writer of `calculated_result`. A RED
  confirmation result opens its Failure Investigation, as §10 has always said.
* **I7** — `revise_version` now writes `formula_version_drivers`, so §29's
  *"why was F008 created?"* has an answer. `driver_type` is **required** on
  the revision endpoint — a **breaking change** to that route, made because §2
  says a revision must show which failure or objective caused it, and
  `change_reason` is prose that explains without linking.

---

## 🔴 WHAT THE REVIEWERS FOUND — SEVENTH SESSION, NEITHER ALONE WAS ENOUGH

**Codex found the transaction hazard. The Supervisor found five defects Codex
did not, two of them permanent lockouts.** Run both, every time.

### Codex

1. **`open_failure` called `session.rollback()`**, which rolls back the
   TOPMOST transaction and discards nested ones. Once `complete_execution`
   called it, a duplicate failure code would have destroyed the test
   completion and its audit event. Now `begin_nested()` — placed **outside**
   the `try`, because entering it flushes pending state before the savepoint
   exists.
2. 🔴 **My own test for that could not fail.** It asserted the session was
   still usable — but `session.rollback()` leaves a Session perfectly usable,
   so it would have passed against the broken code. It now asserts the
   caller's work *survived*, and was **proved by falsification**: the old
   implementation was temporarily restored and the test fails against it.
3. **Migration 028 claimed more than it delivers.** `clock_timestamp()` plus a
   random-UUID tiebreaker is a *stable display order*, not a guaranteed
   insertion order. The same defect the last two sessions kept finding — a
   comment stating a stronger rule than the code — this time in my own comment
   one commit after writing it.

### Supervisor

1. `post_completion` didn't map the failure domain's exceptions → **HTTP 500**
   instead of the 409 its sibling routes give the same condition.
2. 🔴 **PERMANENT LOCKOUT.** No uniqueness on `(organization_id, test_id)`, and
   `POST /api/failures` accepts any `test_id` — so two engineers opening an
   investigation for one test made the link lookup raise
   `MultipleResultsFound` on **every retry**. That test could never be
   completed again. Fixed at both layers (service uses `LIMIT 1`; migration
   029 adds the partial unique index, which **refuses to build** over existing
   duplicates and names them).
3. 🔴 **PERMANENT LOCKOUT, second one.** One squatted `FI-<test_number>` code
   made a test uncompletable forever — `failure_code` has no rename path.
   `_free_failure_code` now takes the first free suffix.
4. 🔴 **`list_messages` returned the OLDEST page.** `ORDER BY posted_at ASC …
   LIMIT 100` with no cursor: past 100 messages a reader was pinned to the
   opening of the conversation permanently and nothing new was reachable.
5. 028's `id` tiebreaker made the sort unservable by 022's index → full sort
   on every channel read. 029 adds a matching index.

### And one found by simply running the suite

🔴 **`now()` IS TRANSACTION-START TIME.** `messaging.messages.posted_at`
defaulted to `now()`, so every message written in one transaction got an
**identical** timestamp and `ORDER BY posted_at` had nothing to order by. A
conversation had *no defined order* and a reply could render above the message
it answered. `test_023_messaging` failed locally while passing in CI — **CI
had been green on heap luck.** Migration 028.

---

## ▶ NEXT

1. **I5** — `record_decision` writes `testing.test_decisions` directly instead
   of driving `workflow.approval_routes`. Two approval records for one event;
   §9 says one shared engine.
2. **I8** — notifications have no producer outside mentions, so §11's sidebar
   counts read zero.
3. 🔴 **I30** — **22 more `session.rollback()` calls inside IntegrityError
   handlers, across 9 modules.** Full inventory in `TODO.md`. Every one is a
   latent transaction-destroyer the moment §12's reuse rule composes it into a
   larger unit of work; two have already bitten. They are also **redundant
   even standalone** — `session_scope` already rolls back on any exception —
   so the sweep only removes risk. One reviewed slice with a shared helper.
4. **I3** — the golden Playwright E2E. Now genuinely reachable for the first
   time, because a real database is available locally.

---

## Constraints that must not be forgotten

- 🔴 **Zero cost, strictly. And no task may be assigned to the operator** —
  no signup, no interactive login, no dashboard action. A path whose first
  step is an owner action is not a path.
- 🔴 **Solar is never part of this app**, and Solar has **no running Docker
  container on this machine** — measured. Only a `factory/intelligent-pv-solar`
  image, exited three months ago. Solar is Render-only.
- 🔴 **Do not touch any `aw-*` container.** This project's DB is
  `evercoat-postgres` on port **55432**.
- ⚠️ **CI has a one-run-per-ref concurrency group.** Pushing evicts an
  in-progress run — a `cancelled` conclusion on the previous commit is usually
  this, not a failure.
- ⚠️ **Never** use `render-setup.yml` apply mode to force a deploy: it issues
  `DELETE` against **AutoWorkshop** custom domains. Use
  `gh workflow run "Deploy web (manual)"`.
- ⚠️ **Codex `exec` cannot take a long prompt as an argument on Windows** —
  the command line is limited to ~8 KB. Pipe it on **stdin** instead:
  `codex.cmd exec --skip-git-repo-check - < prompt.txt`. That also closes
  stdin, which is what stops it hanging.
- ⚠️ **CodeRabbit CLI 0.7.5** is installed and signature-verified but has
  **never been authenticated**; `coderabbit auth login` is interactive and is
  therefore blocked by the no-assignment rule.
