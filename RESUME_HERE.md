# ▶ RESUME HERE — EvercoatITWRD APP

## ▶▶ SESSION CLOSE 2026-08-24 — START HERE

Tip **`7c2c453`**. Two commits: **23 of 37 endpoints across Laboratory,
Testing, Formulations and MSD had no browser caller.** All 37 do now — and
the second commit exists because the first one *claimed* that and was wrong.

| Module | Endpoints | Reachable before | Now |
|---|---|---|---|
| Laboratory | 11 | 10 | **11** |
| Testing | 9 | **1** | **9** |
| Formulations | 13 | **1** | **13** |
| MSD | 4 | 2 | **4** |

Local gates: API **671 passed / 0 failed / 11 skipped** (run ALONE — 139s),
web **137 / 0**, `tsc` exit 0, `next lint` + ruff + ruff format + mypy
(86 files) all green.

### 🔴 THE LIVE SUITE DID NOT FINISH — AND ITS e2e NUMBERS DO NOT EXIST

Run against the tunnel, `full` profile:

| phase | result |
|---|---|
| health / mount probes | `/`, `/health/live`, `/docs`, `/dashboard/` all **200** |
| **`api-live`** | **682 passed / 0 failed / 0 skipped** (rc=0) — COMPLETE and valid |
| **e2e (Playwright)** | 🔴 **KILLED MID-FLIGHT. `e2e.log` is 0 bytes. NO COUNTS.** |

The session's background tasks were stopped while Playwright was ~7 minutes
into its run, exactly as happened twice on 08-23. **A run killed mid-flight
has void numbers** — there is no e2e figure to quote and none is quoted.

`api-live` is reported because that phase FINISHED and the script printed its
own three numbers before the stop. It is up from 670 on 08-23, still with
**zero skipped**.

▶ **OUTSTANDING: one complete live-suite run.** Bring the stack back up (the
API and the tunnel are down; Postgres, Keycloak, Caddy and the web server
survived) and re-run `scripts/live-suite.sh <url> full`.

### 🔴 The orphaned routes were hiding real defects

Six, and the first two are the ones to remember.

* **I84 — every measurement on those routes was a FLOAT.** The formulations
  service had **no Decimal→string helper at all**, and `get_test` built its
  statistics *after* the row-level one had run. Measured against the running
  service: `percentage 2.5`, `theoretical_density_g_cm3
  1.0906918323011936`. §5 was satisfied in the database, satisfied in the
  engine, and **satisfied nowhere in between**. It is the same defect
  `test_laboratory_testing_serialisation.py` was written for on 08-19 —
  whose own header says it survived because *"no screen was wired to these
  routes yet"*. That fix reached exactly as far as the routes wired that day.
* **I85 — then the strings carried 28 significant digits** from inputs
  recorded to four. Quantized to `0.0001` at the response boundary, never in
  the engine (`binder_to_filler_ratio` must stay exactly 40/60). Four places
  is the scale `build_demo_formulations.py` already uses — the fixture and
  the live API render onto the **same screens**.
* **I86 — the formula list could not reach the workspace, which is why there
  was none.** Twelve of thirteen routes are keyed by `version_id`;
  `list_formulas` returned the version *code*. Not a missing screen: a
  missing column that made the screen unbuildable, with a fixture standing in.
* **I87 — the difference engine shipped without Δ and %Δ**, behind a
  correct-sounding comment that named the engine as the only place allowed
  to subtract two percentages. No such function had ever been written.
* **I88 — MSD had a complete memory and no way to read it.** Both history
  routes existed with no caller, so every reload began an empty conversation
  on top of a full record.
* **I89 — the bench could do everything to a batch except create one** (Codex).

### 🔴 The review round — read this before trusting a claim of mine

**Codex 4 findings, Supervisor 10, one overlap.** Thirteenth session running
where neither alone was enough.

* **I90 — the first commit's central claim was FALSE, and Codex checked it
  rather than believing it.** `createBatch`, `createTest`, `createFormula`
  and `classifyFormula` existed only as declarations in `lib/api/*.ts`.
  **A client function is not a caller** — the same defect the commit exists
  to remove, one layer up. Closing it needed `GET /api/testing/methods` and
  `GET /api/formulations/classifications` first: without them a planning form
  has no method to offer, so the create routes were unreachable **by
  construction**. §H's own warning, turned on this session.
* **I91 — four comments I wrote asserted a rule the code did not have.** The
  server's explanation sits in `.detail` and no screen read it, so every
  refusal rendered "the API refused this request (422)". A blocked
  submission's blocks were discarded **wholesale**. New `serverMessage()`.
* **I92 — the only UI path that creates a revision returned 422 on every
  press**, on the control the page calls "the only way a formula changes".
* **I93 — four inert mechanisms**, including an `invalidateQueries` key
  matching no query, under a comment claiming it prevented exactly that.
* **I94 — three of my own**, found by re-verifying rather than by a reviewer.
* **I95 — left open on purpose:** `app/knowledge/page.tsx` has I91's defect in
  three places. Out of the four modules under review, so **named rather than
  silently fixed**.

🔴 **AN EMPTY OUTPUT FILE IS NOT A PASSING RUN.** I read a still-being-written
`tsc` output as clean. It had silently taken `useWeighUp` with a block I
deleted. `next lint` caught it; the typecheck I trusted did not.

### ⚠️ Two operational findings

* **Last session's dev server was still running and holding ~2 GB** of this
  3.78 GB host. It starved Keycloak into `BlockedThreadChecker` warnings and
  made every gate crawl. **Check for a stale `next dev` before blaming the
  machine.**
* **Two pytest runs against the same database disagreed with each other** —
  one reported an error on `test_audit_update_and_delete_are_refused` that
  the other did not. Concurrent suites on one database produce numbers that
  are not evidence. Run the suite alone.

### Built

* **`/testing/test?id=…`** — both status fields side by side and labelled
  (F31), raw replicates with the mandatory exclusion reason, statistics with
  `null` rendered as a named absence rather than zero, the snapshotted
  approval ladder including **undecided** steps, all seven decision types,
  and the number of the rule that decided the colour.
* **`/formulations/formula?version=…`** — live composition, derived
  properties (each a value **or** the engine's own sentence saying why not),
  the weigh-up sheet, and the parent difference with both delta columns.
* Query parameters, not `[id]` — under `output: "export"` a dynamic segment
  must enumerate params at build time, so it would pre-render the seeded
  records and 404 every real one.

---

## SESSION CLOSE 2026-08-23

Tip **`ab9621e`**, tree clean, all pushed. **Nine commits.**

▶ **Restart procedure for the demo tunnel:**
`Documents/session-archives/2026-08-23/RESTART_THE_DEMO.md`
Full session record: `.../2026-08-23/README.md`

### The one thing outstanding

A **confirming live-suite run**. The last COMPLETE run was
**699 passed / 2 failed / 0 skipped** with `api-live` a clean **670 / 0 / 0**.
Those 2 e2e failures were a timeout budget sized for a local origin; the fix
landed in `playwright.config.ts` (180s live / 60s local) and both tests were
verified individually against the tunnel in 1.5m — but the full run confirming
it was **killed mid-flight and its numbers are void** (it showed 668/2, both
`httpx.ReadTimeout` against the API as it was shut down).

Expected on a clean run: **~701 / 0 / 0**.

### What shipped

* **Migration 044** — RLS on `core.users` (**I55**: 571 rows of cross-tenant
  PII readable with no context) and the cross-tenant WRITE in `invite_member`
  (**I80**, new: it renamed another tenant's user and returned their real email).
* 🔴 **A defect neither reviewer found.** `core.user_id_for_subject` was owned
  by `postgres` — `rolsuper`, `rolbypassrls` — while 044's own comment claimed
  `evercoat_owner`. I56's exact shape, three migrations after 033 wrote the
  warning. **`pg_proc` found it, not Codex and not the Supervisor**;
  `test_object_ownership.py` structurally could not, because its sweep only
  flags definers wrongly moved *to* `evercoat_owner`.
* **Laboratory workspace** at `/laboratory/batch?id=…` — eleven API routes that
  no browser could reach now have a caller.
* **I78** — the knowledge list reports what it truncates.
* **MSD relevance** — the distance threshold had stopped separating relevant
  from irrelevant (ranges OVERLAP: related 0.554–0.716, unrelated 0.664–0.859).
  Replaced with a shared-vocabulary requirement, which is what a LEXICAL
  embedder can actually attest to. **I77 still open** for a neural embedder.
* **Eight harness defects**, none in the product — see the archive README.
  The sharpest: a fully green 31-test Playwright run **reported nothing and
  passed**, and the pytest parser **deleted the passed count on every green
  run** (accurate when broken, wrong when clean).
* **`evercoat-test` Keycloak client** — the 11 auth round-trip tests had
  **never once executed** since they were written. They now pass (11 in 55.82s).

### Proven by hand, not by the suite

The full batch lifecycle driven end to end over the tunnel with real tokens:
create → authorise → start → 8/8 weighed → deviation → sample → complete →
accept. Authorization refused correctly three times, including **the technician
who executed a batch may not review it** (§9 segregation of duties).

⚠️ `evercoat-web`'s direct grant was temporarily enabled for that and
**disabled again, verified**. `evercoat-test` exists so nobody is tempted to
leave it on.

### 🔴 Read before touching the demo

* **localtunnel is unusable** — 15 of 15 concurrent requests → HTTP 429.
* **A Cloudflare QUICK tunnel changes hostname every restart**, and four things
  carry it (Keycloak `KC_HOSTNAME`, client redirect URIs, API issuer, the web
  bundle). **A named tunnel removes all of it and needs one browser login.**
* **Keycloak `start-dev` must NOT be memory-capped** — 512 MB + tuned heap is a
  Render `start` measurement; here it sticks at 497/512 and never boots.

---

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
`master`. Tip **`cafb34f`**, working tree clean, pushed.
**CI 5 of 5 GREEN.** Local API suite **507 passed / 0 failed / 0 skipped**
(that number INCLUDES `tests/auth`, which runs without Keycloak - its conftest
says so in its first paragraph, and it was excluded all session on the
opposite assumption).

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

**CORRECTED 2026-08-21: the `aw-*` containers are now deliberately STOPPED.**
AutoWorkshop is being retired and the owner confirmed nobody uses it; stopping
them freed **834 MiB** (`aw-keycloak` alone was 568 MiB). `docker start` brings
them back. The old rule said never to touch them, which was right while it was
running and is no longer.

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
