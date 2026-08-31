# ▶ RESUME HERE — EvercoatITWRD APP

## ▶▶ 2026-08-31 — THE PRODUCT COULD NOT BE SEARCHED, AND A WORKSPACE COULD NOT SAY WHY IT EXISTED

Tip **`<TIP>`** on `master`. Phase 5 §29, §25 and §22 shipped; §38/§39 remains.

- 🔴 **LIVE SUITE ON THE DEPLOYED SITE: 1139 / 0 / 0** (api-live 1056/0/0 · e2e 83/0/0)
- apps/api **1045 / 0 / 11** local (was 986 / 0 / **35** — see below) · apps/web **286**
- Migration head **`v1000`** (063) — `workflow.domain_events`, spec §22.
- ruff, ruff format, mypy, `tsc`, ESLint all clean
- Migration head **`u1000`** (062). **No migration added this session.**

### WHAT SHIPPED

**§29 global search.** Fifteen record types, one literal statement, gated on
AUTHENTICATION and then filtered per record type by a bound boolean — not a
post-filter, which would leak the total. The response reports what it did NOT
search, because "no results" and "not searched" are different answers. The
top-bar box had been `disabled` since Slice 1.

**§25 contextual entry points.** Both directions. Materials, Testing and
Failures carry "Research this →"; the workspace card says "Opened from: …".

### 🔴 THREE THINGS WORTH CARRYING FORWARD

- **THE FIRST SEARCH REGISTRY WOULD HAVE SHIPPED FIFTEEN DEAD LINKS.** Every
  record type was given a detail route and fourteen do not exist — only five
  workspace screens take a record id, and as `?id=`, not a path segment. Caught
  before commit. A test now reads `apps/web/app` and fails on any path the
  router would not serve, and a second reads each target page's source and
  asserts it calls `params.get("<name>")` — because the first guard split on
  "?" and would have passed `?verison=`.

- **§25 WAS THE DATES DEFECT AGAIN.** Four columns on `research.investigations`
  since 058, accepted by the create route since 058, projected by NOTHING and
  offered by NO client type. The columns were never missing; the projection was,
  at both ends. **Ask of every column: which production path WRITES it, and
  which one READS it back?**

- **`SET LOCAL statement_timeout = :ms` IS A SYNTAX ERROR.** SET takes a
  literal, never a bind parameter — PostgreSQL says `syntax error at or near
  "$1"`. `set_config('statement_timeout', :ms, true)` is a function call, so its
  arguments are values. Same reason `has_table_privilege` takes the table name
  as a bind parameter in `d0775ab`.

### ⚠️ WHAT THE REVIEWERS ADDED

Codex: **one P1 and five P2s on `b75f2e9`, every one real.** The P1 is the one
worth remembering: escaping `%` and `_` closed pattern INJECTION and did nothing
about pattern COST — a leading wildcard cannot use an index, so one common
letter scans fifteen tables, and `limit <= 50` bounds the RESPONSE not the WORK.

### 🔴 THREE SILENT-FAILURE MECHANISMS, ALL FIXED AT THE MECHANISM

1. **`tests/db/conftest.py` skipped on ANY connection error.** `evercoat_public`
   and `evercoat_agent` are `dev-public-pw` / `dev-agent-pw` on this host, not
   CI's `ci-*`. 24 tests reported SKIPPED; three handovers quoted
   "0 failed / 35 skipped" as though chosen. A supplied-and-refused password
   now FAILS; an unset one still skips. ⚠️ `docker exec psql` accepts BOTH
   passwords (local socket) — verify from the HOST over TCP.
2. **The realm `frontendUrl` overrides `KC_HOSTNAME`, and lives in the
   database.** Every token was issued with a dead hostname and the API refused
   all of them. It looks like a proxy problem and is not — the stale issuer was
   served on `localhost:18080` with Caddy out of the path. `kcadm get realms
   --fields attributes` returned `{}` while the row sat in `realm_attribute`,
   so the read-back goes to the database.
3. **`demo-up.ps1` printed "keycloak recreated" over two failed docker calls**,
   then on the next run repointed Keycloak BEFORE creating it and died in the
   gap — leaving a live tunnel with no identity provider. Reordered to
   recreate → wait → repoint.

**Five things carry the hostname, not the four the script's header claims:**
client redirectUris, `KC_HOSTNAME`, the API issuer, the web bundle, **and the
realm `frontendUrl`**.

### 🔴 §22 SHIPPED, AND WHAT IT IS NOT

Migration **063** adds `workflow.domain_events` — append-only by TRIGGER (a
revoked grant stops `evercoat_app` and nothing else), FORCE RLS, owned by
`evercoat_owner` because the migration runs as the SUPERUSER. §22's second
chain is wired whole: `confirm_test` announces `TestResultFinalized` and every
open investigation naming that test is told.

⚠️ **IT REWIRES NOTHING.** `revise_version` still calls `record_driver`
directly; the safety chain still calls `material_usage` directly. Do not read
the presence of a bus as decoupling — the module docstring says so too.

Four things it cost, all worth keeping:

- **The migration runs as the superuser**, so without an explicit
  `ALTER TABLE ... OWNER TO` the table is owned by `postgres` while every other
  table in `workflow` is owned by `evercoat_owner`. Commit `0108d7d` is the
  previous instance; there is now a probe.
- **`core.rls_permissive()` returns FALSE, not TRUE.** A note said otherwise
  and it was stale.
- **A stricter policy is not a safer one.** Mine omitted the
  `(rls_permissive() AND current_org_id() IS NULL)` branch every other tenant
  table carries, and broke two suites. Measure `pg_policies`, do not recall.
- 🔴 **`testing.tests` is RLS-enabled but NOT FORCED**, so `test_018` and the
  golden scenario had been calling `confirm_test` as the owner with no tenant
  GUC. Production sets it at `db.py:514`. The fixtures now set it too — the fix
  was to make the fixtures faithful to production, not to loosen a new table to
  match them. **Every table since 058 is born FORCE, so this will happen again
  to the next new table a service writes to.**

### ▶ NEXT, in order

1. **§22's remaining three chains** — rewiring hard-coded cross-module calls.
   A migration of behaviour, not an addition; its own slice. — the last structural part of Phase 5. 🔴 **Greenfield:
   measured this session, there is NO event infrastructure in this repository
   at all.** Emitting events nothing consumes would be a table with no reader,
   so this needs an emitter AND a consumer that replaces a hard-coded
   cross-module write (§22's own example: `ResearchFindingApproved` →
   Knowledge Library indexes it).
2. **§38 / §39 golden scenario** for the research vertical.
3. **L1 and L3 are OWNER DECISIONS, not unfinished work.** Self-service sign-up
   is a Keycloak registration flow and a policy about who may self-register;
   the news feed needs a licensed ingestion pipeline. **L2** needs more real
   manufacturers sourced (the verifier must not be loosened); **L4** re-run the
   seed when 3M's host responds.
4. **I12 messaging** — still 0 of 5 endpoints pressable.
5. **D1 — deploy API + Keycloak.** Held for 2026-09-01, which is now.
6. **I110** · **I111** · **I56/I58** · **I78** · **I9** · **I76/I77** · **I101**.

**I7 was CLOSED as stale**, not fixed — `revise_version` has called
`record_driver` since the failures work (`formulations/service.py:1421`).

### 📄 Progress report

`Desktop\EvercoatITWRD-Phase-Progress-2026-08-31.pdf` (10 pages). ⚠️ It records
that **the owner's "compressed to 10 phases" could not be found in any file** —
the folders define 11 founder implementation phases, a 13-step MVP sequence, 20
delivered slices, 12 extension slices, and this workstream's own 5 + 7. If a
ten-phase cut was agreed, it is not written down and should be.

---

## ▶▶ 2026-08-30 (part 4) — THE PIPELINE COULD NOT SAY WHEN, AND NOBODY KNEW WHO WAS HOLDING AN IDEA

Tip **`d45906b`** on `master`, pushed. Two owner instructions, both delivered.

- apps/api **986 / 0 / 35** · apps/web **283** vitest
- ruff, ruff format, mypy, `tsc`, ESLint all clean; `next build` proven green
- Migration head **`u1000`** (062). **No migration added this session.**

### WHAT SHIPPED

**1. Dates on every pipeline action and event.** The columns were never
missing — `created_at` is NOT NULL on every pipeline table — but four of the
five list endpoints selected everything except it. A search of the whole of
`apps/web` for `toLocaleDateString`, `Intl.DateTimeFormat` and `new Date(`
returned **two hits, neither of which displayed a date**. Fixed at every layer,
because each silently undoes the next: SQL projection → service reshaping →
Pydantic model → Zod schema → view. Eleven views now carry dates.

**2. "Action required — and by whom" on innovations.** A red marker (icon +
words + the `status-fail` token, never colour alone) naming the role that can
actually act, with the required control rendered red. The role names are read
out of the migrations by `lib/api/action-required.drift.test.ts`.

### 🔴 THREE THINGS THIS SESSION PROVED THE HARD WAY

- **A CALENDAR DATE IS NOT AN INSTANT.** `target_release_date` is a plain
  `date` column arriving as `2026-11-30`. ECMAScript parses a bare date as UTC
  midnight and `Intl` renders it in the viewer's zone — it displayed
  **29 Nov 2026** on this host. Every release target a day early for every user
  west of UTC. Found by a test, not by reading. `lib/format/date.ts` now builds
  calendar dates in local time and rejects malformed ones rather than letting
  `new Date(2026, 12, 45)` roll over into a real-looking wrong day.

- **A DEFAULT AND A MISSING COLUMN CANCEL EACH OTHER OUT.** `ProjectSummary`
  defaults `created_at`, so the create route's `RETURNING` could omit it and
  the route still answered 201 — with `created_at: null`. Nothing raised.
  Same defect one route over from the reported one.

- **THE DRIFT TEST'S OWN GUARD CAUGHT THE DRIFT TEST.** Its regex was built
  from a TEMPLATE literal, where `\s` is just `s`, so `[\s\S]` became `[sS]`
  and matched nothing. It would have compared two empty sets and passed. Only
  the guard-the-guard assertion caught it. It also read only migration `002`
  while `research.create` is granted in **058** — a guard reporting a defect
  that is not there is as useless as one missing a defect that is.

### ⚠️ WHAT BOTH REVIEWERS ADDED

Codex found two P1s I had not: a marketplace draft is blocked on the
**Research Center**, not the Lead (`submit_opportunity` refuses it until the
screening investigation records a finding), and `_DECIDABLE` is
`{feasibility, awaiting_decision, on_hold}` while the screen handled only
`awaiting_decision` — so a held opportunity was actionable on the server and
ownerless and inert in the UI. Both fixed; `list_opportunities` now projects
`screening_investigation_code` and `screening_has_finding` so the screen can
name the right blocker.

### ▶ REMAINING — LANDING PAGE

Shipped and live: public landing page, marketplace (44 real sourced products,
every `source_url` fetched before publication), industry news, access requests,
theme-aware including the red/blue/white theme, marketplace + news entry points
beside the app name, "create innovation" from a product card.

Still open:
- **Sign-UP is a request, not a registration.** `/api/public/access-requests`
  records an interest; nothing provisions an account. If self-service sign-up
  is wanted, that is a Keycloak registration flow and a decision, not a form.
- **50 competitors / 100+ products was the target; 44 products are live.** The
  gap is honest: `seed_public_intel_real.py` REFUSES to publish a row whose
  `source_url` does not resolve. Raising the count means sourcing more real
  manufacturers, not loosening the verifier.
- **The news feed is still demonstration data** and says so on every card. Real
  news needs a source-ingestion pipeline with licence and robots/ToS review.
- ⚠️ **3M was dropped on the last verification run** — it times out for both
  `httpx` and `urllib`, measured at the same moment, so it is the host and not
  the client. Re-run the seed when it is reachable.

### ▶ REMAINING — MATERIAL SAFETY DATA & RESEARCH CENTER

Shipped: the screening gate (migration **062**) — an opportunity carrying an
investigation cannot be submitted until that investigation records a finding;
the four registers (questions, sources, hypotheses, gaps) now show their dates.

Still open, all Phase 5:
- **§22 events** — the Research Center writes no domain events.
- **§25 contextual entry points** — reaching an investigation from the record
  that motivated it.
- **§29 global search** across investigations, findings and evidence.
- **§38 / §39 the golden scenario** for the research vertical.
- **I7** — `revise_version` never writes `formula_version_drivers`.

### ▶ REMAINING — CURRENT PHASE (issues)

- **I110** — `SECURITY.md` §13 states a Content-Security-Policy that does not
  exist. Measured twice, independently. Decide: ship the CSP or correct the doc.
- **I111** — `next build` REWRITES `apps/web/tsconfig.json` on every run. It has
  now been caught before commit rather than swept into one, but the fix is still
  owed. `.next-verify/` was added to `.gitignore` this session so a verification
  build no longer fights the running demo server for its dist directory.
- **I56 / I58** — the FORCE-RLS cutover, carrying the owed measurement on
  `core.authorization_for_current_session()`.
- **I78** — the knowledge document list truncates at 100, silently.
- **I9** — CI seed-gate coverage. **I76 / I77** — `MAX_DISTANCE = 0.74` must be
  re-derived. **I101**.

### 🔴 BEFORE YOU RUN ANYTHING

The suite needs FIVE role variables plus `KEYCLOAK_ISSUER`, or 60+ tests fail
as `AuthConnectionNotConfiguredError` and read like a regression. Without
`KEYCLOAK_ISSUER` **collection itself fails** with a Pydantic
`Settings.keycloak_issuer` error — an environment gap, not a code defect. The
full incantation is in `CLAUDE.md` §13; `TEST_DB_PORT` is **55432** on this
host, not 5432.

The demo stack: **Keycloak 18080, Caddy 18081, Postgres 55432, API 18000.**
The tunnel hostname ROTATES — read it from `tmp/demo/cloudflared.err.log`,
never from a note. It was
`https://planet-sounds-positions-band.trycloudflare.com` at close.
**Restart the :18000 listener only** — restarting `cloudflared` mints a new
hostname and invalidates the Keycloak `redirectUris` and realm `frontendUrl`.
Verify the PID owns `uvicorn app.main:app` before stopping it; a port names a
PID, not a process.

---

## ▶ PREVIOUS — 2026-08-29 (part 3) — FORMS, GATING, AND THREE LIVE-ONLY CONTRACT BUGS

Tip **`e0ef6f0`** on `master`. Working tree clean, pushed. **CI green on every
commit this session** — verified, not assumed.

- apps/api **961 / 0 / 11** · apps/web **257** vitest
- ruff, ruff format, mypy, `tsc`, ESLint all clean
- Migration head **`q1000`** (058). No migration added in part 3.

### 🔴 FIRST TASK IS NOT A BUG FIX

The owner specified the next task at session close: **a public landing page at
`/` carrying sign-up and sign-in, plus a competitor-product marketplace with
SolarPro-style cards — 50 competitors, 100+ products, agent-managed.** The full
instruction and the open design questions are at the top of `TODO.md`.

**Read SolarPro's marketplace card first** (`Desktop/solar-pv-designer-lite/`)
and adopt it. Then answer these before writing code:

- **There is no PUBLIC surface in this application.** Every screen is behind
  sign-in and `LiveOnlyPage` shows a "no data source" notice when signed out.
  An anonymous read path cuts across §6 and RLS. Do not bolt a flag onto the
  existing routes.
- **There is no sign-UP.** Keycloak self-registration is off, and registration
  into a tenanted R&D system needs an approval path.
- `competitor_products` has **no pricing column**.
- Rule 3 and §7: 100 agent-generated products presented as fact is a defect.
  Synthetic rows must be labelled.

### WHAT PART 3 DID

**It opened by finding CI already broken** — `0bfc812` was CANCELLED (not
passed) and `dbbd80b` had FAILED. Two e2e breaks from part 2's own work, both
fixed. *"Queued at close" is not "passing".*

- **`PUT /materials/{id}` had NO client at all.** The edit form now exists, and
  loads from the DETAIL endpoint because the LIST omits four editable columns —
  prefilling from the grid would have silently erased them on every save.
- **Raise-a-task had never once raised a task** (404 + no owner). It has an
  assignee control now, and Claim/Complete are pressable.
- **Twelve controls were offered to callers the server refuses**, across
  Material Safety, Competitors and the MSD button.
- **`scripts/role_forms_audit.py` is committed** — 0 gaps across all ten roles,
  down from 14, and still 0 with comments stripped.

### 🔴 THE LESSON: THREE DEFECTS, ONE CAUSE

All three were green in CI and invisible to every layer except a live press:

1. `createTask` posted to `/api/tasks`; the router is at **`/api/my-work`**.
2. `get_material` returned raw `Decimal`s — FastAPI encodes them as **floats**,
   so the edit form could not load. **Codex found it.**
3. `post_material` returned `{"id"}` while the client parsed `material_code` as
   required — **the row was created and the response then failed to parse.**

Server tests pass (the write is right), client tests stub the response, and
`tsc` cannot relate a `dict[str, str]` to a Zod schema.
`tests/e2e/api/serving.spec.ts` now asserts **every client path is a served
path** (127 of them).

### 🔴 FOUR OF MY OWN GUARDS COULD NOT FAIL

Two source-scraping tests passed over the reverted fix; **hoisting a literal
into a constant disabled the path-contract check**; a link guard flagged 10
innocent sites. **Revert the fix and watch the test go red — every time.**

### ⚠️ ENVIRONMENT

- **Keycloak is on host 18080, Caddy 18081, Postgres 55432.** A probe of
  `localhost:8080` returns nothing and looks like an outage.
- **`demo-up.ps1` killed `explorer.exe`** by force-killing an unverified PID.
  Fixed — it now names the process and refuses anything that is not
  node/python/uvicorn. Recovery is `Start-Process explorer.exe`.
- **`live-suite.sh` now waits for the identity provider.** Keycloak's ~2-minute
  cold start after a demo restart caused 8 false failures.
- 🔴 **Never edit a shell script while it is running.**
- **The tunnel hostname changes on every demo restart** — read it from
  `tmp/demo/cloudflared.err.log`.
- **Ten demo users, one per role, one password** (`EvercoatDemo-2026!`).
  🔴 **`lead.demo` holds neither `material.create` nor `test.plan`** — three
  e2e tests failed on that false premise against a correct product.

### ⚠️ OPEN, AND NAMED

- `POST /my-work/{id}/reassign` — no client, no control. It needs a people
  picker scoped to the task's project. I wrote the client and deleted it
  rather than ship a caller-less function.
- `MaterialActions` keeps `supplierId`/`target`/`reason` across a material
  switch, so "Link supplier" can attach one material's supplier to another.
- `/projects/[code]` renders from `lib/demo/dataset` and 404s for live records.
  Fixed at the analytics call site only.

---

## ▶▶ 2026-08-29 (part 2) — PHASE 5 §27, DEMO DATA, AND EVERY MISSING FORM

Tip **`0bfc812`** on `master`. Working tree clean, pushed.

- apps/api **956 / 0 / 11** · apps/web **232** vitest
- ruff, ruff format, mypy, `tsc`, ESLint all clean
- Migration head **`q1000`** (058). No migration added in part 2.

### 🔴 DO THESE THREE THINGS FIRST

1. **CHECK CI ON `0bfc812`** — it was queued at session close.
   `gh run list --limit 3 --json status,conclusion,headSha`, compare headSha.
2. **RUN THE LIVE SUITE.** Nothing since `21af227` has been run against the
   deployed site. Rebuild web + restart the `:18000` listener **without
   touching cloudflared** (that keeps the hostname), then
   `./scripts/live-suite.sh <url> full` and report **three numbers**.
   Last measured: **1024 / 0 / 0**.
3. **THE SUPERVISOR HAS NOT REVIEWED `b093726`..`0bfc812`.** Codex reviewed
   `b093726` and its 7 findings are fixed in `21af227`; everything after has
   had **no review by either gate**.

### What part 2 shipped

| Commit | |
|---|---|
| `b093726` | Phase 5 §27 — 15 role-dashboard widgets |
| `21af227` | Codex's 7 findings + the research/competitor demo seed |
| `d36aa80` | Create forms: materials, projects, testing, my-work |
| `c1f46f7` | **The composition editor** |
| `dbbd80b` | Material status ladder + supplier link |
| `0bfc812` | Innovation wired + Research Center controls gated |

### 🔴 THE FIND THAT MATTERED

**You could not enter a formula's composition.**
`PUT /api/formulations/versions/{id}/components` had existed since Slice 3 with
no client function, no hook and no control anywhere. The formula page DISPLAYED
a composition and offered no way to enter one — so total percentage, density,
binder/filler ratio, cost and VOC were all computing over nothing.

No audit found it, because every audit asked *which routes have a caller*
rather than *which form does a chemist use to do their job*. The owner's
question found it.

### 🔴 THE ROLE AUDIT IS THE TOOL WORTH KEEPING

For every role, does it have a CONTROL for every write permission it HOLDS? The
inverse of "a permission with no enforcement point". It reads the database, the
API source and the web source — nothing hand-kept — and found 7 gaps for the
chemist, 4 for the lead, 4 for the engineer, 3 for procurement, in three
different KINDS: controls that existed but were not permission-gated; no
control at all; and one whole missing screen.

⚠️ **`msd.use` is held by 8 of 10 roles and there is no MSD page.** A feature,
not a form — reported rather than built silently.

### Other lessons worth carrying

- **The role dashboard rendered NOTHING, for every role**, until `b093726`: the
  component walked the response's top-level keys and skipped `panels`, the one
  key holding all 21 of them.
- **`safety_alerts.severity` is `critical | high | informational`** — a
  "critical" panel filtering on `= high` HID every critical alert.
- **ESLint caught an authorization gap**: two research buttons had an extra
  condition so the bulk gating pass missed them, and their unused `may` named
  both.
- 🔴 **Editing a CRLF file from Python: open with `newline=""` BOTH ways.**
  `read_text`/`write_text` converted `scripts/live-suite.sh` and bash refused
  it; nothing in the diff looked wrong.

## ▶▶ SESSION 2026-08-29 — PHASE 4, AND 17 REVIEW FINDINGS ON IT

Tip **`ef160b3`** on **`master`**. Migration **058 / `q1000`**, both trees.

- apps/api **939 / 0 / 11** · apps/web **218** vitest
- ruff, ruff format, mypy, `tsc`, ESLint all clean

**Phase 4 shipped the research vertical**: eight `research` tables, six
permissions, 26 routes, `/material-safety/research`, and the single join to the
formula world — an accepted experiment proposal records the version
`formulations.revise_version` returned. `knowledge.promote` finally has an
enforcement point (29 orphaned permissions → 28).

### 🔴 WHAT THE REVIEWERS FOUND, AND WHY BOTH WERE NEEDED

**Codex 6 findings (2 P1). Supervisor 11 (2 HIGH). ONE overlapped.** All 17
upheld after measurement. The four that mattered most:

1. **Acceptance was raceable** — no row lock, no rowcount check, so two callers
   each cloned a formula version and the loser still returned success.
2. **Acceptance did not bind the version to the proposal's project** — project A
   could revise project B's formula and the thread would record A as the driver.
3. **`owner_user_id` came off the request body with no tenant check.** The tell
   was already in the route: it caught `CrossTenantReferenceError` and nothing
   in the call path could raise it.
4. **The promotion trigger was BEFORE UPDATE only** while its own comment
   claimed it held against direct SQL. `evercoat_app` has table-level INSERT.

🔴 **`lpad` TRUNCATES ON THE RIGHT** — `lpad('1000', 3, '0')` is `'100'`.
Three code allocators would have become permanently stuck at 1000 codes per
organization-year, with nothing looking wrong.

🔴 **A COMMENT CAN MAKE A GRANT WRONG.** The accept route's docstring said the
ordinary revision endpoint needs two permissions; it needs one. Measuring it
found `product_development_lead` holding `experiment.accept` and NOT
`formula.clone` — so a lead could never have accepted anything. The grant was
withdrawn, not the gate weakened.

### ⚠️ THINGS THIS PHASE LEARNED ABOUT THE APPROVAL ENGINE

- **Approval history cannot be deleted.** `workflow.approval_route_steps` carries
  `audit.deny_mutation` on DELETE, unconditionally. So a committing HTTP test
  that opens a route leaks an organization for ever, and 058's DOWNGRADE cannot
  remove routes either — it retires the template instead, and the provisioning
  function had to REACTIVATE rather than skip or a second upgrade left tenants
  with an inactive template.
- **A finding's approval is the ROUTE, never a column.** There is no approve
  button on `/material-safety/research`, deliberately.

## ▶▶ SESSION 2026-08-28 (LATE) — PHASE 3 FINISHED, AND THE FIX MADE A HOLE REACHABLE

Tip **`4effbe6`** on branch **`slice7-material-safety-data`** (3 commits ahead of
`master`, plus today's earlier three). Migration **057 / `p1000`**, both trees.

- apps/api **889 / 0 / 11** local · apps/web **218** vitest
- ruff, ruff format, mypy, `tsc`, ESLint all clean
- ▶ **LIVE SUITE ON THE DEPLOYED DEMO: 967 passed / 0 failed / 0 skipped** —
  api-live **900** + e2e **67**, run as **two phases** against the same build.
  Playwright collected 67 specs and passed 67, so nothing was refused.

🔴 **THE DEMO HOSTNAME CHANGED TODAY AND MEMORY'S WAS STALE.** It is now
`https://garcia-ottawa-financial-fame.trycloudflare.com`. The old one answered
**000**. Read the current one out of `tmp/demo/cloudflared.err.log`, never from a
note — a quick tunnel mints a new hostname every restart.

🔴 **`/health/ready` WAS 200 OVER A STALE BUILD.** All three checks reported ok
while the deployed API served **7 of the 11** competitor operations. The tell was
`/openapi.json`, not the health check. **Check the thing you changed.**

### What this session did

Phase 3's schema shipped this morning (`dcb0c06`, `e4f52e0`, `4e32a54`); its
**vertical** was unfinished and uncommitted.

**Two of 056's four tables had a writer route and nothing that could press it.**
`competitors.samples` and `competitors.benchmarks` had no GET, no client
function and no control — writable only by something never built, readable by
nothing. Added both readers, both routes, the clients, hooks and screen panels.

**The server had always accepted `sample_id` on evidence and nothing ever sent
it**, so every `manual_observation` — the entire third entry mode — was recorded
unattributable.

### 🔴 AND WIRING THAT FIELD MADE A DORMANT SCHEMA HOLE LIVE

056 bound `source_document_id` to the competitor product with a three-column key
and wrote the reason beside it: *"a label uploaded for product A could be cited
as evidence for product B and every other constraint would still hold."* True of
samples verbatim — and `composition_evidence_sample_fk` was left
`(sample_id, organization_id)`.

It was harmless **only because no client had ever sent the field**. Closed by
057, which asserts the resulting constraint definition rather than that the DDL
ran. Found by the Supervisor, on the commit that made it reachable.

> **NEW LESSON: ASK WHAT A CHANGE MAKES REACHABLE, NOT ONLY WHAT IT CHANGES.**
> Wiring a client to an existing field is the first time that field's
> constraints carry any weight.

### Two reviewers, 15 findings, 2 overlaps — the 22nd session running

Codex **VERDICT: FAIL** (1 P1, 3 P2); Supervisor 11 (3 HIGH, 4 MEDIUM, 4 LOW).
Full adjudication in `reviews/adjudication-c98420a-competitors-2026-08-28.md`.

- **A WRITE GATED ON A READ PERMISSION** — `POST /benchmarks` required only
  `test.view`. Now `material.edit` **and** `test.view`.
- **`POST /evidence/{id}/grade` HAD NO CALLER** — the third instance of the very
  defect this session set out to remove, beside the two I fixed. **A client
  function is not a caller.**
- **EVERY WORKSPACE WRITE FAILED SILENTLY** — the only alert was bound to a
  different mutation instance on the parent, hiding the **503 raised when no
  malware verdict could be obtained**.
- **`verify_evidence` had no `guarded_write` and no `except DBAPIError`** — two
  of 056's guards escaped as a 500. `_translate` already had branches for both
  and **both were unreachable**.
- **`_translate` returned raw PostgreSQL text** for four constraints.
- **A GUARD THAT PASSED BECAUSE IT COULD NOT SEE** — my cross-tenant test looped
  over four tables while the fixture wrote into one.

### Falsified by breaking the DATABASE, not the code

| Broken on purpose | Result | Restored |
|---|---|---|
| `DROP TRIGGER material_documents_supersedes_same_owner` | 2 red, incl. the SDS-stays-submittable assertion | ✅ |
| `ALTER TABLE competitors.samples DISABLE ROW LEVEL SECURITY` | 2 red, incl. the cross-tenant loop | ✅ `force=true` re-asserted |

### ⚠️ THINGS THE NEXT SESSION NEEDS

- 🔴 **`alembic upgrade head` NEEDS `MIGRATION_DATABASE_URL` WITH THE POSTGRES
  SUPERUSER ON THIS HOST.** `alembic_version` is owned by `postgres`; both
  `evercoat_app` and `evercoat_owner` are refused on it. Password
  `dev-superuser-pw` (container env).
- **Rebuild the demo by hand, never via `demo-up.ps1`, unless a new hostname is
  acceptable** — that script restarts cloudflared. Kill the **:3000** listener
  first or `next build` stalls forever holding `.next-demo`. Script kept at
  `scratchpad/redeploy_demo.ps1` pattern: stop 3000 + 18000, start uvicorn,
  build with `NEXT_PUBLIC_*` pointed at the CURRENT tunnel, start standalone.
- **I112 filed** — the competitor vertical has 23 DB tests and **not one route
  or service test**, which is exactly why three Supervisor findings were green.

### ▶ NEXT, in order

1. **I112** — route/service coverage for the competitor vertical.
   `apps/api/tests/test_knowledge_routes.py` is the precedent.
2. **Phase 4 — the research / formulation vertical** (`research` tables →
   investigation → finding → approval → experiment proposal → the **existing**
   Formulations `revise_version` → Knowledge promotion). Migration 058.
3. **Slice 7's messaging surface (I12)** — still **0 of 5 endpoints pressable**,
   no notifications screen. The last MVP-1 slice with unbuilt browser surface.
4. **I110** (SECURITY.md states a CSP that does not exist) · **I111** (`next
   build` rewrites `tsconfig.json`) · **I76/I77** (`MAX_DISTANCE = 0.74` must be
   re-derived) · **I56/I58** (FORCE RLS cutover, carrying the owed measurement).
5. **D1 — deploy API + Keycloak on/after 2026-09-01.** 🔴 Do NOT delete
   `autoworkshop-postgres` early; its app data is unarchived.

## ▶▶ SESSION 2026-08-27 (LATE) — THE REVIEW FIXES, AND THE FIXES' OWN DEFECTS

Tip **`91926ca`**. apps/api **846 / 0 / 11** (857 collected), apps/web **211**
vitest, e2e **75** specs local.

This session had one job: apply the 19 findings Codex and the Supervisor raised
on `b84a300` / `ad55d99`. Measuring them found four more. Reviewing the repair
found **eleven more**, one of which is the worst defect of the day.

### 🔴 THE LIVE E2E SUITE DID NOT RUN AT ALL, AND THE TASK REPORTED SUCCESS

Widening the accessibility sweep, I added
`{ name: "project workspace", path: "/projects/workspace" }` beside an existing
entry of the same name. Playwright refuses to run **any** test when two share a
title:

    Error: duplicate test title "project workspace has no WCAG 2.1 AA
    violations", first declared in shell/accessibility.spec.ts:102

Not one test executed. And the shell chain that ran it ended in `tail`, so the
exit code reported belonged to `tail` — the notification said *completed, exit
code 0*. **A SUITE THAT RAN NOTHING HAS NOT PASSED**, arriving by a route this
project had not seen: not a skip, not an empty selection, a refused run.

`lib/accessibility-coverage.test.ts` now asserts the names are unique, and says
in its own message that this is a suite-wide outage rather than a failure.
Falsified by introducing a duplicate.

### 🔴 A BLANK NAME LOCKED PEOPLE OUT OF THEIR OWN ACCOUNT

Fixing Codex's *"an empty `display_name` is accepted though the comment claims
otherwise"*, I made `activeProfile` return `null` on a blank name. `UserMenu`
renders nothing on a null profile, `top-bar.tsx` is its only mount, and
`/account/settings`, `/account/security` and `/account/profile` are linked from
nowhere else in the shell — so a signed-in person with no name on file **could
not sign out**. Reachable, not theoretical: the parse maps an absent field to
`""` for an API too old to send it.

The account is never withheld now. `profileLabel` falls back to the address and
then to "Your account"; `profileInitials` returns null rather than a "?".

**A COSMETIC RULE MUST NOT BE ENFORCED BY REMOVING A CONTROL.** The Supervisor
found it by asking who mounts the component — not by reading the change.

### 🔴 THE PAPER THEME ERASED EVERY ALERT FILL

`warmed()` mixed each accent `50` 55% into the paper surface. Both are
near-white and the surface is the **darker** of the two, so every fill landed on
the page's own luminance: red **1.007:1**, orange **1.004:1** — two in 255 in
one channel. A red notice and an amber one became the same colour; only the
border survived.

Grounds now start at the hue's `200`. That cost the light status set its margin
on them (pass fell to 4.08:1), so **Paper has its own status set** — the third
surface to need one, and the third time measurement said so rather than
reasoning that "the page is still light".

Two new guards: every ground against its own page, and every status colour
against the ground it is actually painted on — the pairing the badge test had
never made.

### What the 19 original findings came to

| Finding | Fix |
|---|---|
| The theme covered 12 of 34 colour tokens | Seven accent ramps + `slate-950` themed; `tailwind.config.ts` now **imports** the palette instead of hand-copying 60 triples under a comment claiming a drift test existed |
| `StatusBadge` unreadable on dark (1.65 / 2.53 / 1.61:1) | `theme.test.ts` reads the SOURCE for class strings pairing a background with a foreground. It immediately refused my first dark set at **3.62:1 on the fail badge** |
| A light flash on every load | A pre-paint script in the document head, built from the same `paletteVariables` the provider uses. Verified in the exported HTML at byte 8779, before `<body>` at 9296 |
| `profile` never cleared on sign-out; never refreshed on org switch; taken from `rows[0]` | `/api/me` no longer declares tenant attributes on the identity — each membership carries its own pair (052's own rule, re-broken one tier up). `activeProfile()` derives it |
| The landing preference had no reader | `app/page.tsx` opens on the chosen screen, which is also what sign-in returns to |
| `role="radiogroup"` with no arrow keys | `components/ui/radio-cards.tsx`: roving tabindex, arrows, Home/End, selection follows focus |
| Two pages missing from the a11y sweep | Measuring the route list found **eight more**. `accessibility-coverage.test.ts` derives it from the filesystem |
| Four Administration headers reporting "0" while unknown | `headerCount()` — and the Supervisor caught that I fixed "Permissions" and left "Domains" beside it |

### ▶ LIVE SUITE ON THE DEPLOYED DEMO — 922 / 0 / 0

| phase | passed | failed | skipped |
|---|---|---|---|
| `api-live` (pytest against the deployed instance) | **857** | 0 | 0 |
| e2e `shell` (Playwright against the deployed site) | **65** | 0 | 0 |
| **total** | **922** | **0** | **0** |

Run as **two phases** — a single `live-suite.sh` invocation exceeds the harness's
ten-minute cap (api 3m03s + e2e 7m00s). Both halves ran against the SAME
deployed build, with no commit between them that changed the bundle.

🔴 **THE FIRST api-live RUN WAS A RED, AND IT WAS RIGHT.** `857 passed, 1
failed` — my new assertion that each membership carries its own `email` found
the DEPLOYED API still serving the old `/api/me` shape. The `:18000` listener
predated the change. Restarted the listener only; `cloudflared` is never
restarted, because a quick tunnel mints a new hostname and `NEXT_PUBLIC_*` is
baked in at build time.

⚠️ **THE PREVIOUS e2e RUN WAS VOID, NOT GREEN** — a duplicate test title made
Playwright refuse the entire run, and the shell chain reported `tail`'s exit
code. This run executed all 65, and `sign-in.spec.ts`'s two are recorded `ok`
rather than skipped (I100's rule: a capability that skips while configured is a
failure). All 22 accessibility pages pass axe-core, **including the ten the
sweep had never seen**.

### Codex's P2 — the CSP, measured

The pre-paint script is inline, and `SECURITY.md` §13 states *"a
Content-Security-Policy without `unsafe-inline` scripts"*. **Measured: no CSP
exists** — not in `infrastructure/compose/Caddyfile`, not in `next.config.mjs`,
not on the live response. Both reviewers confirmed independently.

So the finding is real about the future and the **document is what is wrong
today**. Recorded as I110 rather than papered over. When the CSP lands, this
script needs its `sha256-` hash in `script-src`, and that is a decision about
deployment configuration, not a code change to make now.

### Reviewer arithmetic

**Codex: 1 finding. Supervisor: 10, none overlapping.** Twenty-first consecutive
session in which neither reviewer alone was enough. The Supervisor's were
sharper this round — it verified the whole mechanism with a real production
build, including `NEXT_OUTPUT=export`, before reporting.

---

## ▶ SESSION 2026-08-27 (EARLIER) — THE API'S WRITE PATHS FINALLY GOT BROWSERS

Tip **`ad55d99`**, 20 commits. apps/api **855 / 0 / 11**, apps/web **182**
vitest, **64** e2e specs.

🔴 **THE MEASUREMENT THAT SET THE DAY.** Asked how each role puts information in
and gets results out, I measured rather than answered: every
`require_permission` in `app/api/*.py`, all ten seeded roles signed in against
the live demo, cross-referenced with the web client and the pages calling it.

    31 of 79 write endpoints were pressable. 48 had NO client function at all.

The five modules with full coverage were exactly the five closed on 2026-08-24;
the same audit had never been run on the other nine. Per role: chemist 16
controls, technician 14, lead 10, **administrator 3**, executive 1. The Lead
held `project.advance_stage`, `requirement.approve`, `milestone.manage` and
`project.assign_member` — with a control for none of them.

**By close: ~63 of 79.**

### What shipped

| Slice | What |
|---|---|
| Navigation | The SECOND level is gated. `ContextSubmenu` had no permission concept at all, and three page comments still claimed *"/api/me returns roles, not permissions"* — false since I79 closed two days earlier. |
| Agent tier | Five more departments (formulations, materials, innovation, quality, knowledge). 9 of 19 API modules reach the orchestrator, was 4. |
| Slice 6 | `/failures`, `/failures/investigation?id=`, `/approvals` — eleven write endpoints that had no caller, in the module §10 writes to automatically. |
| Slice 2 | `/projects/workspace?id=` — ten of eleven project writes. |
| Administration | `/admin` members, stage gates, reference data, roles, permissions. All 11 `admin.*` writes reachable. |
| Account | User menu in the top bar, five themes, a landing screen. |

### 🔴 WHAT THIS COST, AND WHAT IT TAUGHT

**THE SQL IS NOT THE CONTRACT; THE RESPONSE IS.** Three wrong client types in
two days from reading a SELECT and believing it: `has_root_cause` was a
`count(*)` behind a yes/no name; `must_differ_from_group` is a nullable INTEGER
naming a parallel group; the requirements matrix is reshaped past recognition.
Probing the API with a real token before writing a schema caught the third.

**A GREEN TYPECHECK IS NOT A WORKING BUILD.** `tsc --noEmit`, lint and 173 tests
all passed over a bundle that could not be produced — a `page.tsx` may export
only its page, and only `next build` enforces it.

**I REPEATED A DEFECT HOURS AFTER FIXING IT.** The Supervisor found one test
hand-copying a list instead of importing it; I then wrote another doing exactly
the same thing. Both now read the other tier and both are falsified.

**A COMMENT ASSERTING A BEHAVIOUR THE CODE LACKS — three times, all mine.**

**36+ real defects from two reviewers, none overlapping.** One Codex claim was
wrong and six right; one Supervisor claim was wrong and five right.

### ⚠️ WHAT IS OWED

### ▶ LIVE SUITE ON THE DEPLOYED DEMO — 905 / 0 / 0

| phase | passed | failed | skipped |
|---|---|---|---|
| `api-live` | **855** | 0 | 0 |
| e2e `shell` | **50** | 0 | 0 |
| **TOTAL** | **905** | **0** | **0** |

⚠️ **RUN AS TWO PHASES, NOT ONE INVOCATION.** A full `live-suite.sh` run now
exceeds ten minutes (api-live 3m46s + e2e 5m12s + waits) and was killed at the
harness cap while e2e was running — `api-live` had already printed its own
pytest summary line. The e2e half was then run separately against the SAME
deployed build, with no commit between them that changed the bundle.

⚠️ **50 IS THE CORRECT LIVE e2e COUNT, NOT 64.** `--list` reports 64 because it
runs in LOCAL mode; in LIVE mode the config excludes `api-wiring.spec.ts` (14
tests) deliberately — that seam is compiled OUT of production builds, so its
failures were once a false red. 41 before today + 9 added = 50.

⚠️ The suite also needs `KEYCLOAK_ADMIN_USER` / `KEYCLOAK_ADMIN_PASSWORD` now:
five browser sign-ins per run, and one run went 881/1/0 on that contention
alone.

🔴 **`b84a300` AND `ad55d99` HAVE HAD NO CODEX OR SUPERVISOR REVIEW.** Every
other slice today was reviewed by both and both found real defects in every one.
`b84a300` is the largest unreviewed change — the theme system touches
`tailwind.config.ts`, so it affects every screen.

- **The deltaE measurement has not been redone for the dark status palette.**
- **Six of nine Administration sections have NO endpoint at all.**
- **No unlink for evidence**, only relabel.
- `next build` rewrites `apps/web/tsconfig.json`; swept into commits twice.

---

## ▶▶ SESSION 2026-08-26 (part 4) — I109 CLOSED

Tip **`3a8af36`**, migration **053 (`l1000`)**, **ADR-032**. API suite
**805 / 0 / 11**; ruff, format, mypy clean. Round-trip `l1000 → k1000 → l1000`
exercised.

`core.memberships_for_subject(TEXT)` and `core.principal_for_subject(TEXT, UUID)`
take a subject as an **argument** and cannot check their caller, because both
answer BEFORE a session has an organization. Granted to `evercoat_app`, an
ordinary member read a foreign subject's address **and the name and code of
every organization it belongs to**.

🔴 **SO THE FIX COULD NOT BE A CHECK.** A GUC naming the verified subject is
settable by `evercoat_app`; so is `SET ROLE`. Both are misuse barriers, not
boundaries. **Privilege had to follow the CONNECTION** — `evercoat_auth` holds
EXECUTE on those two functions, `NOINHERIT`, and **no table privilege in any
schema**, on a pool used by `get_principal` and `/api/me` and nothing else.

⚠️ **IT FAILS CLOSED AND NEEDS `AUTH_DATABASE_URL` EVERYWHERE.** An environment
that applies 053 without it cannot authenticate anybody — by design, so there is
no state where the fix reads as applied and the old privilege still works.
`/health/ready` now reports `sign_in`, measured across five states including the
URL pointed at the runtime role and at `evercoat_owner`. **Migration 053 creates
the role NOLOGIN**; each environment must `ALTER ROLE evercoat_auth LOGIN
PASSWORD …` after migrating (CI does; `demo-up.ps1` preflights and refuses with
the exact command; D1's deploy steps carry it).

**Codex's review of the fix: seven findings — one measured WRONG, six fixed.**
The "probe after COMMIT is not atomic" claim does not hold for the alembic path,
because `_sql.py` strips `BEGIN;`/`COMMIT;` — forced a probe failure and neither
the GRANT nor the REVOKE survived. The Supervisor then found a seventh:
`auth_database_url` lacked the superuser guard `database_url` has had since
ADR-017.

🔴 **A ROLE-LEVEL REVOKE AGAINST A `PUBLIC` GRANT DOES NOTHING** — ADR-029's
column-versus-table lesson, one level up. Found while correcting a downgrade
docstring that claimed the role was left "inert": PUBLIC holds CONNECT on the
database, and `evercoat_report`, never granted it, returns TRUE.

### ▶ LIVE SUITE AFTER 053 — 853 / 0 / 0

| phase | passed | failed | skipped |
|---|---|---|---|
| `api-live` | **816** | 0 | 0 |
| e2e `shell` | **37** | 0 | 0 |
| **TOTAL** | **853** | **0** | **0** |

Preflight all four capabilities CONFIGURED; both `sign-in.spec.ts` tests
`['passed']`. **Sign-in survives being moved to another database role.**

✅ **CI GREEN on `207f298`** — all six jobs, **805 passed / 11 skipped** in CI
too, and the eleven skips are the pre-existing `tests/integration` ones that
need a running Keycloak. **Zero sign-in skips**, which is the thing the previous
run got wrong.

---

## ▶▶ SESSION 2026-08-26 (part 3) — I106, I107 and I108 CLOSED; I109 FILED

Tip **`de99d56`**, pushed, **CI 6/6 GREEN** (`headSha` checked against the tip,
not read off the top row). Migration **052 (`k1000`)**, **ADR-031**. API suite
**791 / 0 / 11**; ruff, format, mypy clean. Downgrade round-trip
`k1000 → j1000 → k1000` exercised.

**I106 was a rolled-back bind reading another tenant's stored address and
name.** Measured first::

    submitted  : 'whatever@attacker.example'        / 'Whatever I Typed'
    read back  : 'secret.person@competitor.example' / 'Confidential B Person'
    memberships left behind after ROLLBACK : 0

🔴 **AND MEASURING IT FOUND A WIDER ONE — I108.** `evercoat_app` held
table-level INSERT on `core.organization_members`, `org_member_isolation`
constrains only `organization_id`, and `user_id` is a plain FK to a global
table. An **ordinary member** — no `admin.users`, no EXECUTE on the bind, no
`keycloak_sub` — manufactured a membership naming a foreign identity, read it,
and rolled back. So the defect is not "the bind leaks": **any membership row
turns a global identity into a readable one**, and the bind was one of two ways
to make one.

🔴 **WHICH MEANS THE TENANT-SCOPED COLUMNS ARE NOT THE CLOSURE.** They are what
keeps the application working once the closure lands. The closure is that
`core.users.email` and `core.users.display_name` stop being readable by the
runtime roles. 046's two advisory-lock trigger guards collapse into ONE partial
unique index `(organization_id, email) WHERE status = 'active'` — possible only
now the address lives on the membership, and **not `users_email_key` returning
because the key LEADS WITH the tenant**.

**I107** closed with seven end-to-end tests over real HTTP
(`tests/auth/test_admin_member_routes.py`). One reproduces the shipped
403-as-500 defect when `_standing_refusal` is broken on purpose.

🔴 **I109 FILED — the closure covers the TABLE, not every path.** Raised by
Codex and measured: `core.memberships_for_subject(TEXT)` and
`core.principal_for_subject(TEXT, UUID)` are SECURITY DEFINER, take a subject as
an ARGUMENT, and are granted to `evercoat_app`. An ordinary member of A read a
foreign identity's address **and the name and code of every organization that
subject belongs to**. Pre-existing (024/033/045). Bounded by 047 — no runtime
role can read `keycloak_sub` — and **a bound is not a closure**. Pinned open by
`test_the_sign_in_definers_still_answer_for_any_subject`, which MUST go red when
it closes.

### ▶ LIVE SUITE AFTER 052 — 839 / 0 / 0

| phase | passed | failed | skipped |
|---|---|---|---|
| `api-live` | **802** | 0 | 0 |
| e2e `shell` | **37** | 0 | 0 |
| **TOTAL** | **839** | **0** | **0** |

Preflight reported all four capabilities **CONFIGURED** — no `--allow-partial`.
Both `sign-in.spec.ts` tests are recorded in `tmp/live-suite/e2e.json` as
`['passed']`, i.e. they RAN rather than merely not being skipped (I100).

⚠️ **THE DEMO API HAD TO BE RESTARTED FIRST, AND THAT IS THE HAZARD TO
REMEMBER.** Migration 052 was applied to `evercoat-postgres`, which is the
database the RUNNING demo uses — so for the length of this session the deployed
demo was old code against a new schema, reading columns it no longer had
privileges on. `/health/ready` answered `200 {"database":"ok"}` throughout,
because a health check does not read those columns. **Only the :18000 listener
was restarted**: restarting `cloudflared` would mint a new quick-tunnel hostname
and repoint everything, and the web bundle needed no rebuild because the change
was API-only.

---

## ▶▶ SESSION 2026-08-26 (part 2) — I105 CLOSED

Tip **`fd62969`**, pushed, **CI 6/6 GREEN** (run 32991114903 — `headSha`
checked against the tip, not read off the top row). Migration **048 (`g1000`)**,
**ADR-030**. API suite **750 / 0 / 11**; `tests/db` **370 / 0 skipped**; ruff,
format, mypy clean.

**I105 is closed.** `core.authorization_for_current_session()` derives the
caller's roles AND permissions from the same two GUCs RLS reads, and
`AgentPrincipal.authorize()` replaces both sets with its answer. The gate and
the rows can no longer disagree about who is asking.

🔴 **It is not the design ADR-029 rejected**: that rejection was about a
definer that WRITES (the write fires ADR-028's guards as owner and reopens
I83). This one is `STABLE` with a single-SELECT body and takes **zero
arguments** — no write to start the chain, no parameter to aim it with.

### ▶ LIVE SUITE AFTER I105 — 798 / 0 / 0

| phase | passed | failed | skipped |
|---|---|---|---|
| `api-live` | **761** | 0 | 0 |
| e2e `shell` | **37** | 0 | 0 |
| **TOTAL** | **798** | **0** | **0** |

Preflight reported all four capabilities **CONFIGURED**. `api-live` counted
from pytest's own summary line (`761 passed ... in 133.87s`); the shell
project re-run alone, exit code 0.

🔴 **AND THE FIRST ATTEMPT'S "7 FAILED / 24 SKIPPED" WAS VOID, NOT RED.**
The e2e phase was interrupted mid-run: 8 tests passed, failures began, and
everything after was skipped — the signature of an aborted run, not of seven
defects. Re-run alone it is 37/0/0, which is what *a crashed worker is a VOID
measurement, not a red* means in practice. The harness printed 769/7/24 and
that number was never reported as a result.

⚠️ **THE API WAS RESTARTED FIRST.** The demo had been serving pre-I105 code
against the post-048 schema. The two-gate boundary was then re-measured across
five roles on the restarted API and is **identical** to before — correct, since
I105 changed where the authorization comes from, not what it is for a
legitimate caller.

### 🔴 GITHUB PUSH EVENTS RAN ~30 MINUTES LATE — AND ONE EVICTED THE OTHER

**CORRECTED.** I first concluded that pushes were not triggering CI at all,
having seen no run twice. They were triggering: the push run for `da708d8`
appeared at 16:45Z for a push made around 16:15Z. A **delay**, not a miss —
and the wrong conclusion was reached by measuring twice within the delay
window.

⚠️ **THE DELAY BITES TWICE.** A manually dispatched run on the newer tip was
then EVICTED by the late-arriving push run for the OLDER commit, because
`concurrency: ci-${{ github.ref }}` is a one-slot replacement waiting room and
not a queue — which `ci.yml`'s own comment says in as many words. CI then ran
a commit that had already been superseded.

**After pushing:** compare the top run's `headSha` to your tip, and be patient
before dispatching.

    gh run list --limit 3 --json databaseId,headSha,event,status,conclusion

### ⚠️ WHAT IS STILL OWED

**The I56/I58 FORCE cutover's effect on this function is UNMEASURED.** The
test was written and withdrawn — `ALTER TABLE ... FORCE` needs ACCESS
EXCLUSIVE on six shared `core` tables and hangs against a live API pool
(`lock_timeout` and fixture rollback both insufficient; killed at 120s;
reproduced independently). Measure it **during** the cutover, when those
tables are being altered anyway.

### ▶▶ NEXT — I82

`core.user_id_for_subject(TEXT)` hands out a uuid for an arbitrary subject —
**the oracle shape ADR-030 deliberately avoided by taking no arguments.**
🔴 Its original fix is REJECTED on evidence (ADR-029). ⚠️ **But re-measure
that rejection before designing around it:** ADR-029's mechanism was a
definer's WRITE firing ADR-028's guards as owner, and **047 then made both
guards scope-explicit**, which may have removed the reason. Measure it; do not
assume in either direction.

Then: I76/I77 · I56/I58 (with the owed measurement above) · I78 · I101 ·
**D1 on/after 2026-09-01** — do NOT delete `autoworkshop-postgres` early.

---


## ▶▶ SESSION 2026-08-26 — I104 CLOSED, INTELLIGENCE SHIPPED, I105 RAISED

Tip **`2d343c3`** on `master`, pushed, tree clean, 0 ahead / 0 behind,
**CI 6/6 green** (run 32982603290 on `e8cd7fd`) — Auth, API image, Security
scan, E2E, Web lint/type/test, API lint/type/test. Semgrep, which is CI-only
and has blocked a locally-green commit before, passed on the new raw SQL in
`app/domains/analytics/service.py`.

Closed today: **I104** (the orchestrator trusted its arguments),
**MSD's orchestration layer** (three of four doors went around the governed
one), and **`analytics.view` / `analytics.portfolio`** — held by nine and two
of ten seeded roles and read by **no line of code** until now.

**Intelligence has a browser surface**: `/analytics` and `/reports`.
`GET /api/analysis/reports/test-results` shipped on 08-25 with **no browser
caller at all** — the twenty-fourth orphaned route, one day after
twenty-three were closed.

### ▶ LIVE SUITE ON THE DEPLOYED DEMO — three numbers, one complete run

| phase | passed | failed | skipped |
|---|---|---|---|
| `api-live` | **747** | 0 | 0 |
| e2e (Playwright `shell`) | **37** | 0 | 0 |
| **TOTAL** | **784** | **0** | **0** |

Preflight reported all four capabilities **CONFIGURED**, so these numbers
cover the whole suite rather than a partial one — no `--allow-partial`.
Counts read from each tool's own summary line (`747 passed ... in 180.16s`),
not from the harness.

🔴 **AND THE NEW SCREENS WERE DRIVEN IN A REAL BROWSER**, recorded
`STATUS expected` in Playwright's own detail file — exercised, not merely
un-skipped:

    shell/navigation.spec.ts :: Analytics is an enabled link and the page renders
    shell/navigation.spec.ts :: Reports is an enabled link and the page renders
    shell/navigation.spec.ts :: neither Intelligence screen invents a figure when it has no data
    shell/sign-in.spec.ts    :: a person can press Sign in, authenticate, and come back signed in

e2e went 34 → 37: exactly the three tests added. `api-live` 720 → 747.

**Demo URL:** `https://radios-mayor-reduces-overcome.trycloudflare.com`
(users `lead.demo` … `exec.demo` / `EvercoatDemo-2026!`,
org `c6031e4b-eff3-4aa6-a87b-697b6941c6e9`).

🔴 **THE TWO ANALYTICS GATES, MEASURED ON THE DEPLOYED API, NOT ASSERTED:**

| user | role | analytics | report | by_project |
|---|---|---|---|---|
| `chem.demo` | chemist | 200 | 200 | **null** |
| `proc.demo` | procurement_specialist | 200 | **403** | null |
| `dir.demo` | director | 200 | 200 | **1** |
| `exec.demo` | executive_viewer | 200 | **403** | **1** |
| `tech.demo` | laboratory_technician | **403** | 403 | — |

`executive_viewer` is the proof the two permissions are independent gates: it
gets the portfolio and is refused the report. `laboratory_technician` holds
`project.view` and is still refused, so `analytics.view` is not `project.view`
under another name.

### ▶▶ EXACT NEXT ACTION — I105

🔴 **`bind()` VALIDATES IDENTITY AND NOT PERMISSIONS.**
`AgentPrincipal.bind()` asks PostgreSQL whether `app.current_org` /
`app.current_user_id` match the caller. It does **not** validate
`caller.permissions`. A forged principal carrying the real session identity
therefore passes `bind()` while claiming arbitrary authorization, and the
conductor gate consults the forged set. **Codex named this exactly and it is
the half of I104 that is not closed.**

The fix is to derive the effective permission set from the GUC-bound user at
the bound-session boundary and gate on that. 🔴 **It is a design task, not a
patch:** it needs a `SECURITY DEFINER` returning permissions for a user id,
which is the shape **ADR-029 rejected on measured evidence** for I82 — an
atomic bind inside a definer re-opened I83. **Do I105 and I82 together, with
the I83 precedent in front of you.**

### 🔴 What the AgentPrincipal type is worth — measured, not assumed

Codex enumerated four forgeries. All four were **reproduced against the real
code**; three are closed (exact type check; the guard is a nonce consumed on
use, so `dataclasses.replace` can no longer replay it; no long-lived sentinel
to import). **`object.__new__` remains open, cannot be closed in Python, and
has a test asserting it stays open** — so that closing it quietly cannot
re-inflate the docstring's claim.

The module now says plainly that it is a **misuse barrier, not an in-process
security boundary**. The first version said "you cannot construct one from
loose values" and you could, which is this repository's most-repeated defect
sitting on top of its authorization boundary.

### 🔴 Lessons from today

> **A SET COMPARISON CANNOT COUNT.** My test read
> `_route_permissions("msd.py") == {"msd.use"}` and stayed GREEN with one of
> four routes ungated — the other three contributed the same element. The
> ungated route was invisible to the test written to find it.

> **A TEST A COMMENT CAN REDDEN IS A TEST NOBODY TRUSTS** — mine failed on
> its own explanation. The inverse, a comment SATISFYING an assertion, is the
> same failure and the more dangerous direction.

> **AN UNCAST `:x IS NULL` BIND FAILS ONLY ON THE UNFILTERED CALL** — which
> is the call a browser makes by default. Caught by
> `tests/test_no_untyped_null_binds.py` on the day the query was written,
> because that rule is instrumented rather than restated.

> **`.get()` RETURNING A DEFAULT IS HOW A WRONG NUMBER SURVIVES REVIEW.** Two
> analytics counts were over fields the rows do not carry; both would have
> read `{"unknown": n}` — correct-looking, plausible, meaningless.

> **A SCREEN THAT INVENTS ITS TRUNCATION LIMIT IS WORSE THAN ONE THAT HIDES
> IT.** `capped at {"200"}` was a literal matching the default request;
> `?limit=10` would have been reported under a cap of 200. Raised by Codex.

---

## SESSION CLOSE 2026-08-25 (part 5)

Tip **`e9e471e`**, pushed, **CI 6/6 green**.
Closed today: **I100**, **I83**, **I81**, **I102** — and §0.2's conductor tier
is complete.

▶ **Live suite on the deployed demo — three numbers, ONE complete run:**

| phase | passed | failed | skipped |
|---|---|---|---|
| `api-live` | **716** | 0 | 0 |
| e2e (Playwright `shell`) | **34** | 0 | 0 |
| **TOTAL** | **750** | **0** | **0** |

Both sign-in tests recorded as `STATUS expected` — exercised, not un-skipped.

⚠️ **The API process must be restarted after any change under `apps/api/app/`.**
`scripts/demo-up.ps1` starts it detached; the conductor work needed a restart
and the I81 work did not (grants only). Check the LISTENER on :18000, not the
log.

---

### ✅ I102 CLOSED — the suite locked itself out and blamed the password

The realm sets `bruteForceProtected: true`, `failureFactor: 5`, and the auth
tests made **twelve** direct-grant calls per run. The client was told
*"invalid_grant — Invalid user credentials"* with the CORRECT password, while
Keycloak's log said `error="user_temporarily_disabled"`.

🔴 **Keycloak returns the same error for a lockout as for a wrong
password.** Fixed two ways: `_token()` caches per username, and
`live-suite.sh` clears the lockout before each run — **hygiene, not
coverage**, so it warns and proceeds rather than failing the preflight.
Proven by deliberately locking `lead.demo` and running 750/0/0 from that
state.

---

### ✅ §0.2's conductor tier is complete

Four departments: **laboratory**, **testing**, **MSD**, and a new
**analysis**. Each is structural — a permission gate plus dispatch to the
domain service — with `app/agents/boundary.py` owning §7's rule that the
agent tier runs under the caller's own authorization boundary.

🔴 **AND THE REVIEW FOUND MY GATE GUARDED A DOOR NOBODY USED.**
`msd_conductor`'s `explain_result` called the testing tool with **no**
permission check, so `msd.use` without `test.view` returned raw replicates,
statistics and the final disposition. I wrote a testing conductor gating on
`test.view` and the real path went around it. **The third instance of that
shape in that file**, after `knowledge.view` and `formula.view_cost` — the
precedent was thirty lines below the bug. Now gated, falling through to the
refusal as `knowledge_search` does.

Two more, one of which I caught first: the analysis department was gated on
`analytics.view` while the route has always required `project.view`, and
measured against the seeded roles those come apart **both ways** — a
`procurement_specialist` would have been *granted* a dashboard the route
refuses. And omitting `held_permissions` returned the same dashboard with
panels silently missing.

---

### ▶▶ EXACT NEXT ACTION — I103

🔴 **Nothing routes through the new conductors.** The three orchestrator
entry points have no callers; routes still reach their domain services
directly. Codex raised it and it is true: **a layer with no caller is the
same defect as a route with no caller.** Either route something through it —
the obvious candidate is `app/api/dashboards.py`, whose permission the
analysis conductor now matches exactly — or state plainly what the tier is
for and stop implying it is the single door.

Then **I104** (the orchestrator trusts its `permissions`/`user_id`
arguments), **I82**, I76/I77, I56/I58, I78, I101, and **D1 on or after
2026-09-01**.

---

### Carried forward

* ⚠️ **Do not run the live e2e beside pytest or Codex** — Chromium dies with
  `0xC0000142` on this 8 GB host and the failures read like app defects. **A
  crashed worker is a VOID measurement.**
* ⚠️ **`scripts/live-suite.sh` holds a deliberate literal CR** inside
  `$'<CR>'` — read/write it with `open(..., newline="")`.
* ⚠️ **Local migrations run as `postgres`**; password in the container env.
  Local is superuser, **Render is not**.
* ⚠️ **A column-level REVOKE against a table-level GRANT does nothing.**
* ⏳ **D1 waits for 2026-09-01.** Do NOT delete `autoworkshop-postgres` early.

---

## ▶▶ SESSION CLOSE 2026-08-25 (part 4) — START HERE

Tip **`d929293`**, pushed, **CI 6/6 green**. I100, I83 and I81 all closed today.

▶ **Restart the demo — one command:**
`powershell -File scripts\demo-up.ps1`. The stack has been up all session;
only the API process was restarted (for I83), and I81 changed no application
code at all — it is grants and a function body.

▶ **Live suite on the deployed demo — three numbers, ONE complete run:**

| phase | passed | failed | skipped |
|---|---|---|---|
| `api-live` | **702** | 0 | 0 |
| e2e (Playwright `shell`) | **34** | 0 | 0 |
| **TOTAL** | **736** | **0** | **0** |

---

### ✅ I81 CLOSED — an authentication identifier is not a readable column

Migration **047 / f2000**, **ADR-029**.

044's read policy hands over the whole `core.users` row where its
justification — attribution in eleven joins — needs only the name.

🔴 **THE OBJECTION WAS MEASURED, NOT ACCEPTED, AND IT WAS TWO-THIRDS
RIGHT.** `display_name` has eleven readers. `email` has **two production paths
that deliberately return it** — `admin.list_members`, and
`projects.list_members`, which documents that it lists FORMER members on
purpose — so removing it would break stated behaviour. `keycloak_sub` is read
by **no application query anywhere**. Only that one is over-granted, and RLS
cannot take a column away; column privileges can.

⚠️ **A column-level REVOKE against a table-level GRANT does nothing.** The
table grant must be dropped and replaced by an explicit column list. Written
the other way the migration reads exactly like a fix and changes nothing —
which is why the test asserts the PRIVILEGE, not the SQL.

Sign-in is unaffected because the three readers are owner-owned SECURITY
DEFINER functions. That is an argument, so it is also a test.

---

### 🔴 What the review round found

**Codex: FAIL, one blocker.** I had reached it independently; Codex supplied
the consequence I had not stated.

* **I granted a CROSS-TENANT WRITE while removing a cross-tenant read.** The
  first draft granted `UPDATE (email, display_name, status)`. `status` was
  speculative — the same reflex 047 exists to correct on `keycloak_sub`.
  `core.users` is GLOBAL, so a session scoped to ONE shared organization
  could set a multi-organization user to `inactive` and disable that identity
  **in every other tenant**. Now `(email, display_name)`, pinned by a test.

Non-blockers, all acted on: the claim was broader than the code (047 makes
the value unreadable, it does **not** make subject existence confidential —
that residue is I82); a future view projecting `keycloak_sub` would inherit
001's default privileges and hand it straight back, so a test now watches for
one; the downgrade left 047's COMMENT sitting on f1000's body; the 044 upsert
assertion accepted any "permission denied"; and two tests that cannot fail
when 047 is reverted now say so in their own docstrings.

🔴 **And measuring I82 found 046's rename guard was scoped by the CALLER,
not by itself.** Its `mine` side relied on the RLS policy, and a trigger runs
as whatever the current user is — inside a SECURITY DEFINER owned by the
table owner, that user bypasses RLS. Measured: `INVOKER path ACCEPTED` /
`DEFINER path REFUSED`, refusing on another tenant's row, which makes the
refusal a cross-tenant existence answer — I83 rebuilt inside its own
replacement. The predicate is explicit now.

⚠️ **My first probe tested the OTHER trigger and came back clean.** Check
which mechanism is load-bearing before a comment credits one.

---

### 🔴 I102 — the live suite can lock itself out, and the failure lies

Found during this task's live run, which reported **700 passed / 2 failed**:

    "Keycloak refused the direct grant for lead.demo:
     401 invalid_grant — Invalid user credentials"

The password was correct. Keycloak's own log, same second:

    type="LOGIN_ERROR" error="user_temporarily_disabled" username="lead.demo"

The realm sets `bruteForceProtected: true`, `failureFactor: 5`,
`permanentLockout: false`, `maxFailureWaitSeconds: 900`, and the suite
authenticates the same user repeatedly by direct grant — so one slow or
timed-out run trips the lock and everything after it is refused with a message
that says *wrong password*. **That makes the standing live-test rule
non-deterministic and its failures misleading.**

Cleared by hand and the suite then ran 736/0/0:

```bash
TOK=$(curl -s -X POST "$U/auth/realms/master/protocol/openid-connect/token" \
  -d client_id=admin-cli -d username=admin -d password=demo-admin-pw \
  -d grant_type=password | python -c "import json,sys;print(json.load(sys.stdin)['access_token'])")
curl -X DELETE "$U/auth/admin/realms/evercoat/attack-detection/brute-force/users" \
  -H "Authorization: Bearer $TOK"        # 204
```

**It is now task 1.** Two honest fixes: clear the lockout in `live-suite.sh`
before the run, and/or mint one token per user per session instead of one per
test.

---

### ▶▶ EXACT NEXT ACTION

**I102** — make the live suite deterministic, per above. It is small, and
everything else this project measures depends on those three numbers meaning
something.

Then **I82**, whose proposed design is now recorded as **rejected on
evidence** in ADR-029 — an atomic bind inside a SECURITY DEFINER would have
re-opened I83. It needs a different design, not the one in the plan.

Then I76/I77, I56/I58, I78, I101, and **D1 on or after 2026-09-01**.

---

### Carried forward

* ⚠️ **Do not run the live e2e beside pytest or Codex.** Chromium crashes on
  this 8 GB host with `0xC0000142` and the failures read like application
  defects. A crashed worker is a VOID measurement, not a red.
* ⚠️ **`next build` rewrites `apps/web/tsconfig.json` every demo build.**
* ⚠️ **Local migrations run as `postgres`**; the superuser password is in the
  container environment. Local is superuser, **Render is not**.
* ⏳ **D1 waits for 2026-09-01.** Do NOT delete `autoworkshop-postgres` early.

---

## ▶▶ SESSION CLOSE 2026-08-25 (part 3) — START HERE

Tip **`552112d`**, pushed, **CI 6/6 green**. Two commits, both I83.

▶ **Restart the demo — one command:**
`powershell -File scripts\demo-up.ps1` (prints the URL, writes
`tmp/tunnel_url.txt`). The stack has been up since part 1; only the API
process was restarted, to put the I83 fix on the deployed instance before the
live suite ran.

▶ **Live suite on the deployed demo — three numbers:**

| phase | passed | failed | skipped |
|---|---|---|---|
| `api-live` | **693** | 0 | 0 |
| e2e (Playwright `shell`) | **34** | 0 | 0 |
| **TOTAL** | **727** | **0** | **0** |

693, not 682: eleven auth-integration tests that need a live Keycloak run
here and skip locally, and eleven new tests shipped with I83.

---

### ✅ I83 CLOSED — the cross-tenant email existence oracle

Migration **046 / f1000**, **ADR-028**.

`core.users.email` carried `users_email_key`, **globally unique** — and unique
constraints are enforced **outside RLS**. Measured as `evercoat_app` scoped to
organization A: inserting an address held in organization B was **REFUSED**,
an unused address **ACCEPTED**. The route turns those into **409** and
**201**, so any `admin.users` holder in any tenant read platform-wide
existence from a status code, with a throwaway subject and no row left behind.
Squatting confirmed in the same run.

🔴 **The constraint is dropped, not disguised.** Migration 044 had
already made that refusal generic and **the oracle survived**, because the
attacker reads the status code. A creating endpoint cannot make *created*
indistinguishable from *not created*. Identity is `keycloak_sub`; the address
is an attribute mirrored from the identity provider.

**Replaced by two SECURITY INVOKER constraint triggers**, both advisory-locked:
`organization_members_one_address_per_organization` (the INSERT path) and
`users_address_stays_unique_in_organization` (the rename path).

---

### 🔴 What the review round found — the replacement was not a constraint, twice

**Codex: FAIL, three blockers.**

* **A trigger that decides by SELECT is not a unique index.** Found
  independently before Codex answered. Two concurrent transactions both
  committed and one organization ended with two active members at one address
  — measured on two connections. My own comments and ADR-028 said
  *"enforced"*. `pg_advisory_xact_lock` on (organization, address) is the
  mechanism, the same one `audit.chain_row()` has used since 013.
* **A rule enforced on INSERT and not on UPDATE.** Codex's catch, and the one
  I missed. The address lives on `core.users` and the trigger was on
  `core.organization_members`; `UPDATE core.users SET email = <a colleague's
  address>` was **ACCEPTED** with no membership row moved. On that path 046
  was **weaker than the constraint it removed**, because `users_email_key`
  covered updates.
* **The tests certified the rule while permitting both counterexamples.**
  Three added, each falsified by removing its mechanism.

🔴 **And the question Codex did not ask: does the replacement answer
across tenants?** A guard that refuses on a row you cannot see is the oracle
rebuilt inside its own replacement. Proven with a user active in BOTH
organizations, renamed onto an address held only in the one the caller cannot
see: **ACCEPTED**. It misses rather than answers — the trade ADR-028 now
states plainly instead of glossing.

---

### Also found while falsifying

* 🔴 **`test_023_messaging`'s fixture leaked an identity every run for
  months** — it deleted `author` and `outsider` and not `member`. **595
  orphaned rows against 782 users**, so any measurement over `core.users` is
  mostly measuring test debris. Fixed; the debris is now **I101**.
* 🔴 **A fixture that could DEADLOCK the suite.** A failing test never
  reaches its final `rollback()`, and its row locks then block the owner-side
  cleanup `DELETE` forever. It wedged exactly that way and had to be killed.
  A suite that hangs on a failure never reports the failure.
* ⚠️ **`INSERT ... RETURNING id` fails for a brand-new identity** —
  `RETURNING` applies 044's SELECT policy and a user with no membership is
  invisible to the connection that just created it.
* ⚠️ **`SET LOCAL app.current_org = :param` is a syntax error.** Use
  `set_config`, as `app/core/db.py` already says.

---

### ▶▶ EXACT NEXT ACTION

**I81 / I82.** 044's read policy grants the whole row where its justification
needs only the display name — every one of the eleven joins that resolve an
actor selects `display_name` and none selects `email` or `keycloak_sub`, so
the policy hands out contact details and an authentication identifier for a
former member of your own organization. I82's narrower design — fold subject
resolution into a single atomic bind so the uuid is returned only after the
membership exists — changes the route's transaction shape, which is why the
two belong together.

Then: I76/I77, I56/I58, I78, I101, and **D1 on or after 2026-09-01**.

⚠️ **I56/I58 now has more in scope.** 046 adds two SECURITY INVOKER trigger
functions that read `core.users` and `core.organization_members`. Under FORCE
RLS they must still see their own tenant's rows, or the address guards
silently stop guarding.

---

### Carried forward

* ⚠️ **`next build` rewrites `apps/web/tsconfig.json` every demo build.**
* ⚠️ **Local migrations run as `postgres`** (`alembic_version` denies
  `evercoat_owner`); the superuser password is in the container's environment.
  Local is superuser, **Render is not**.
* ⏳ **D1 deploy waits for 2026-09-01.** Do NOT delete `autoworkshop-postgres`
  early — its app data is unarchived.
* 🔴 **THE E2E SUITE CRASHED TWICE ON HOST PRESSURE, AND THE FAILURES LOOKED
  LIKE APPLICATION DEFECTS.** `browserContext.newPage: Target crashed`, then
  `worker process exited unexpectedly (code=3221225794)` — that is
  `0xC0000142`, STATUS_DLL_INIT_FAILED, a process failing to initialise.
  Reported **721/6/2** and then **700/7/22** with sign-in among the
  casualties. The same two sign-in tests then passed **in 30 seconds in
  isolation**, and the whole shell project passed 34/34 alone. Nothing was
  wrong with the application. ⚠️ **Do not run the live e2e beside pytest
  suites or Codex** — this host is 8 GB with Docker holding ~900 MB, and
  Chromium loses. Run it alone, and treat a crashed worker as a VOID
  measurement rather than a red.

---

## ▶▶ SESSION CLOSE 2026-08-25 (part 2) — START HERE

Tip **`8edee9b`**, tree clean. Two commits, both I100.

▶ **Restart the demo — one command:**
`powershell -File scripts\demo-up.ps1` (prints the URL, writes
`tmp/tunnel_url.txt`). The stack from part 1 was still up at the start of
this session and was never restarted.

▶ **Live suite on the deployed demo — three numbers:**

| phase | passed | failed | skipped |
|---|---|---|---|
| `api-live` | **682** | 0 | 0 |
| e2e (Playwright `shell`) | **34** | 0 | 0 |
| **TOTAL** | **716** | **0** | **0** |

Run twice, before and after the review round; identical both times. Counts
read from each tool's own summary line.

🔴 **AND FOR THE FIRST TIME THOSE NUMBERS DEFEND THEMSELVES.**
`tmp/live-suite/e2e-detail.txt` records both tests in `sign-in.spec.ts` as
`STATUS expected` — the flow was EXERCISED, not merely un-skipped. The
incantation is now in `CLAUDE.md` §13; the script refuses to run without it.

---

### ✅ I100 CLOSED — the suite no longer reports green over coverage it lacks

Every green number this script had ever printed depended on environment
variables typed by hand. It exported none and checked none, so running it as
`CLAUDE.md` documented it gave **290 passed / 0 failed / 392 skipped**: a
zero-failure report over 290 of 682 tests, sign-in never exercised.

`scripts/live-suite.sh` now opens with a **PREFLIGHT** that names every
capability, the variables it needs and the tests it governs, and classifies
each one:

| | meaning | if it happens |
|---|---|---|
| **CONFIGURED** | every variable present | if its tests skip anyway that is a **FAILURE**, not a gap — the promise is closed after the run, because only the run knows whether the credentials, database name or realm users were right |
| **ABSENT** | none present | a legitimate absence is possible — a deployed site has no local database — so it fails unless the operator passes `--allow-partial`, which **names every gap in the report** |
| **PARTIAL** | some present | **always** a hard failure. Nobody half-configures a capability on purpose, and a half-configured one skips exactly like an absent one while looking, at the prompt, like it was set up. `--allow-partial` does not cover it |

**Not defaults.** Hard-coding `TEST_DB_PORT=55432` would aim the suite at
whatever database the author had in mind and call the result live coverage.

Two probes separate absence from misconfiguration:

* a database **answering at an address this run is already configured to
  use** — parsed out of `DATABASE_URL`, not a guessed port list — while
  `db-suite` is unset. Unwaivable.
* `db-suite` set but **nothing answering** on `TEST_DB_HOST:TEST_DB_PORT`.
  That is the exact 290/0/392 shape, now caught in three seconds.

After the run: pytest's `-rs` reasons are printed instead of buried in a log
nobody opened; a CONFIGURED capability that skips anyway is counted FAILED;
the Playwright projects that ran are read from **Playwright's own report**
(`--project=api` does not exist in LIVE mode); every skipped e2e test is
listed by file; and capability-level skips are NAMED — `1 skipped` used to
stand for 682 absent tests.

---

### 🔴 What the reviewers found — seventeenth session, neither alone was enough

**Codex: FAIL, two blockers.**

* 🔴 **My own comment asserted a rule the code did not implement.**
  *“`--allow-partial` does NOT cover a database that is present but
  unused”* sat one screen above code that probed three hard-coded ports. A
  database on 15432 answers none of them. Fixed by DERIVING the probe from
  `DATABASE_URL`; falsified with a listener on `127.0.0.1:15432`, which the
  preflight names and no port list would have reached. This is the
  repository's most repeated defect and I had just written another one.
* **A guard that passed when it could not see.** The sign-in guard grepped
  for a skip; an empty detail file — dead parser, missing python, spec never
  collected — produced no skip and therefore no complaint about a flow it
  never looked at. **Found independently by my own Supervisor pass before
  Codex answered.** Both directions are asserted now, falsified four ways.

Non-blockers, all real and all fixed: `tcp_answers` interpolated unvalidated
values into `bash -c` (proven: `TEST_DB_PORT='55432; touch /tmp/pwned'` is
refused and no file appears); its fallback is unbounded without `timeout`,
now announced rather than denied; the skip-reason guards grepped the whole
log where a traceback carrying the same phrase would fail the run, and now
ask pytest's `-rs` lines; and `e2e-detail.txt` was truncated inside the
parser rather than before it, so with python absent the guards would have
read the **previous** run's file — `tmp/live-suite/` still holds an artifact
from 08-18.

🔴 **AND MY OWN PREFLIGHT UNDERSTATED WHAT ITS ABSENCE COSTS**, which is a
quieter version of the defect it exists to catch. `db-suite` was labelled
*“tests/db — 341 tests”* because that is what collection said. Measured:
`tests/auth/conftest.py` uses the same fixtures, and `pytest tests/auth`
without them reports **12 passed / 58 skipped**. The run that exposed I100
skipped **392**. Corrected everywhere it appears.

> **Falsify the guard, not the happy path.** Eleven runs, each removing one
> thing: nothing set → 5 failures, all named; `TEST_DB_PORT` alone unset →
> PARTIAL, `--allow-partial` refused; db block unset + `--allow-partial` →
> still fails, a database answers; db set on the wrong port → fails;
> `TEST_KEYCLOAK_PASSWORD` unset → fails twice; whole auth block unset +
> `--allow-partial` → proceeds with both gaps named; and the sign-in guard
> exercised in four states in isolation.

---

### ▶▶ EXACT NEXT ACTION

**I83 (P1) — the cross-tenant email existence oracle.** `core.users.email` is
`citext` with a **globally unique** constraint, and unique constraints are
enforced OUTSIDE RLS: a holder of `admin.users` in any tenant can POST
`/api/admin/members` with a throwaway `keycloak_sub` and read existence from
201 vs 409. Emails are guessable where a subject UUID is not. The probe
leaves no row behind, so it repeats without limit, and it doubles as a
squatting path. **It needs a schema decision, not a patch** — the two honest
remedies are in `TODO.md` under I83. I81/I82 fold into whichever is chosen.

Ranked queue after that: I81/I82, I76/I77, I56/I58, I78, then **D1 on or
after 2026-09-01**.

---

### Carried forward

* ⚠️ **`next build` rewrites `apps/web/tsconfig.json` every demo build.**
  Still undecided: commit the generated form, or ignore it.
* ⚠️ **Local migrations run as `postgres`** — `alembic_version` denies
  `evercoat_owner`. Local is superuser, **Render is not**; 09-01 meets this.
* ⏳ **D1 deploy waits for 2026-09-01.** Do NOT delete
  `autoworkshop-postgres` early — its app data is unarchived.
* ⚠️ **A misconfigured run is SLOW, not just wrong.** Each connection to a
  dead port costs ~21s here, so the 290/0/392 run crawled. If a suite is
  inexplicably slow, check what it is failing to connect to.

---

## ▶▶ SESSION CLOSE 2026-08-25 — START HERE

Tip **`2d26b2a`**, pushed, tree clean, **CI 6/6 green**. Eight commits.

▶ **Restart the demo — one command:**
`powershell -File scripts\demo-up.ps1` (prints the URL, writes
`tmp/tunnel_url.txt`). 🔴 **The launcher was BROKEN TWO WAYS at the start of
today and one half had never run at all** — both fixed, see I99 below.

▶ **Live suite on the deployed demo — three numbers:**

| phase | passed | failed | skipped |
|---|---|---|---|
| `api-live` | **682** | 0 | 0 |
| e2e (Playwright `shell`) | **34** | 0 | 0 |
| **TOTAL** | **716** | **0** | **0** |

Counts read from each tool's OWN summary line.

---

### 🔴 READ THIS FIRST — I100: THE LIVE SUITE REPORTS GREEN WHILE MOST OF IT NEVER RUNS

**Every number above depends on environment variables I supplied BY HAND.**
`scripts/live-suite.sh` exports none of them. Run it as documented and you get
a confident green covering **290 of 682** tests with sign-in unverified.

Three independent gaps, none of them a code defect:

1. **`tests/db/conftest.py` reads `TEST_DB_PORT`, defaulting to `5432`** — this
   machine's database is on **55432**. It times out and **skips**. First run
   today: **290 passed / 0 failed / 392 skipped.** 392 of 682 tests silently
   absent, zero failures reported.
2. **`tests/e2e/shell/sign-in.spec.ts` self-skips without
   `TEST_KEYCLOAK_PASSWORD`** — so the test written on 08-24 *specifically to
   stop sign-in breaking silently* **does not run in the live suite that
   exists to catch it.** Its own header says so: *"if the round trip skips in
   a LIVE run, the sign-in flow was NOT verified."*
3. **`--project=api` does not exist against a deployed URL**
   (`Available projects: "shell"`), so any total assuming both Playwright
   projects ran is wrong. Live browser coverage is the 34 `shell` tests; the
   deployed API surface is `api-live`.

**The incantation that actually works** (also at `RESUME_HERE.md` §db-suite):

```bash
cd apps/api
TEST_DB_HOST=localhost TEST_DB_PORT=55432 POSTGRES_DB=evercoat_itw_rd \
TEST_OWNER_USER=evercoat_owner TEST_OWNER_PASSWORD=ci-owner \
APP_DB_USER=evercoat_app APP_DB_PASSWORD=ci-app \
DATABASE_URL="postgresql+psycopg://evercoat_app:ci-app@localhost:55432/evercoat_itw_rd" \
KEYCLOAK_ISSUER="<tunnel>/auth/realms/evercoat" LIVE_BASE_URL="<tunnel>" \
TEST_KEYCLOAK_URL="<tunnel>/auth" TEST_API_URL="http://localhost:18000" \
TEST_KEYCLOAK_PASSWORD='EvercoatDemo-2026!' \
TEST_ORGANIZATION_ID='c6031e4b-eff3-4aa6-a87b-697b6941c6e9' \
python -m pytest tests -m "live or not live" -q --no-header -rs
```

```bash
TEST_KEYCLOAK_PASSWORD='EvercoatDemo-2026!' \
PLAYWRIGHT_BASE_URL="<tunnel>" npx playwright test --project=shell
```

▶ **THE FIX IS TO MAKE THE SCRIPT DEMAND WHAT IT NEEDS AND FAIL LOUDLY**, not
to remember to export it. That is the top task next session.

#### ▶▶ EXACT NEXT ACTION — the I100 fix, designed but NOT started

Nothing has been changed. `scripts/live-suite.sh` is untouched (587 lines) and
the tree is clean at `2d26b2a`. Resume by editing that file:

**Add a PREFLIGHT section after the profile block (~line 146, before
`echo " LIVE SUITE -- "`)** that names every capability and what its absence
costs, then decides:

| capability | required env | if missing |
|---|---|---|
| api-live imports | `DATABASE_URL`, `KEYCLOAK_ISSUER` | already handled at `run_pytest` (~line 248) — but it counts **one** skip for **392 tests** |
| `tests/db/*` | `TEST_DB_HOST` `TEST_DB_PORT` `POSTGRES_DB` `TEST_OWNER_USER` `TEST_OWNER_PASSWORD` `APP_DB_USER` `APP_DB_PASSWORD` | **392 tests skip silently** |
| sign-in round trip | `TEST_KEYCLOAK_PASSWORD` | **the flow is NOT verified** |
| auth integration | `TEST_KEYCLOAK_URL` `TEST_API_URL` `TEST_KEYCLOAK_PASSWORD` `TEST_ORGANIZATION_ID` | 11 tests skip |

🔴 **THE DESIGN DECISION THAT MATTERS.** Do **not** simply export defaults —
against a genuinely deployed site there is no local database, so those 392
tests legitimately cannot run, and hard-coding a port would aim the suite at
whatever database the author had in mind. Instead:

1. **Preflight prints a coverage table** — each capability CONFIGURED or
   ABSENT, with the test count it governs.
2. **Half-configured is a hard FAIL**, because it is a misconfiguration rather
   than a legitimate absence: if a database ANSWERS on `TEST_DB_PORT` (or on
   55432) while the test variables are unset, exit non-zero and say so.
3. **`TEST_KEYCLOAK_PASSWORD` unset must not report success.** Either exit
   non-zero, or require an explicit `--allow-partial` flag to proceed — the
   suite must never print a clean three-number report while the sign-in round
   trip skipped.
4. `run_pytest`'s current gate counts **one** skip for a whole suite. Make the
   skip count reflect the tests actually not run, or name them; `1 skipped`
   for 392 absent tests is the number that hid this.

**Verify by falsification, as everything else this session was:** run it with
each variable removed in turn and confirm it FAILS and names the gap. A
preflight that cannot fail is the third guard this session that read as
verification and was not.

**The 11 auth integration tests that had NEVER ONCE RUN now run and pass.**
`evercoat-test` was already in the realm as a public direct-grant client; the
demo org is `c6031e4b-eff3-4aa6-a87b-697b6941c6e9` (`EVERCOAT-DEMO`, all ten
`*.demo` users).

---

### What shipped

**I95 + I98 — the server's sentence now reaches every READ path.**
`DataSourceError` rendered `{error.message}` and is called from **fifteen
sites across eleven screens**, so every failed read showed *"the API refused
this request (403)"* instead of the reason, discarding a blocked submission's
entire block list. I91 fixed the four WRITE screens on 08-24 and missed the
shared read component. 🔴 **Codex was asked this exact question on 08-24 and
answered NONE** — it matched the literal `.error.message` while the component
reads `{error.message}`. The Supervisor pass found it.

🔴 **AND THE REASON IT COULD HIDE: NO COMPONENT HAD EVER BEEN RENDERED BY A
TEST.** `vitest.config.ts` was `environment: "node"` with no React plugin and
there were **zero `.test.tsx` files**, while `@testing-library/react`, `jsdom`
and `@vitejs/plugin-react` had been devDependencies all along — installed,
never wired.

**I98b — my own fix regressed the commonest error on a tunnelled demo.**
`serverMessage` mines `error.detail`, but `detail` is not always a response
body: `ApiUnreachableError` stores the caught `TypeError` there and
`ApiShapeError` a `SyntaxError`/`ZodError`. All carry `.message`, so the
component began rendering the browser's raw **"Failed to fetch"** in place of
*"the API could not be reached"*. Guarded at source.

**I99 — `scripts/demo-up.ps1` was broken two ways, and one half had NEVER RUN.**
(a) Line 207 held a literal **BEL byte (0x07)** where `\a` belongs —
`Set-Location '$RepoRoot<BEL>pps\web'` — introduced by `c98290f` at 08-24
12:52, **four minutes after the last successful web build**. (b) The Keycloak
repoint **could not work from PowerShell 5.1**: embedded double quotes passed
to a native exe are stripped by the `CommandLineToArgvW` round-trip and
`kcadm` answered `Cannot parse the JSON`. Now a `docker cp`'d ASCII JSON file
applied with `-f`. **The read-back guard is what caught (b).**

**I99b/c — TWO SUCCESSIVE GUARDS THAT READ AS VERIFICATION AND COULD NOT FAIL.**
Codex found the first (`-notlike "*$PublicUrl*"` never looked at `webOrigins`,
passed with three of four URIs missing, and with a NAMED tunnel would pass on
stale config). My fix for it **still walked through the empty-`webOrigins`
case**, because every webOrigin is a PREFIX of a redirect URI — a substring
test cannot say WHICH FIELD a value came from. Now `ConvertFrom-Json` with
per-field `-notcontains`, falsified four ways.

**I79 — a membership carries its permissions.** Migration **045 / e9000**.
`core.memberships_for_subject` returns permission codes per organization,
resolved through the same chain `core.principal_for_subject` (033) walks — ONE
definition rather than a TypeScript copy. Measured: `lead.demo` **38**,
`tech.demo` **11**. Proven **e9000 → e8000 → e9000** with shape, owner, ACL and
comment asserted at each end; **the downgrade had never been run before**.

---

### 🔴 What the reviewers found — sixteenth session, neither alone was enough

**Round 1 (I98):** Codex FAIL, 2 blockers — the `ApiUnreachableError` trap
(which I had found independently) extended to `ApiShapeError`, and the weak
read-back guard. It also **corrected my call-site count, 19 → 15**; I had
counted import lines.

**Round 2 (I79):** Codex FAIL, 2 blockers, and the round split THREE ways:

* 🔴 **Codex was RIGHT and I had contradicted myself.** Authenticated with an
  active tenant absent from `/api/me` returned the FULL module map, justified
  in my own comment as *"we do not know, so we do not pretend to"* — which
  directly contradicts what I had written one file away in
  `auth-provider.tsx`: an API that cannot report permissions must show
  **LESS, never everything**. Failing open on an authorization-shaped
  decision, beside my own note not to. Now fails closed.
* 🔴 **Codex was WRONG on the facts, and the measurement says so.** It argued
  `roles` might reorder because `array_agg(DISTINCT)` has no `ORDER BY`.
  Measured on PG 16.14: DISTINCT aggregation **must sort to deduplicate**, so
  reversing the input leaves the output identical. It does not reproduce.
  **But its reasoning was right** — that is behaviour, not contract — so the
  `ORDER BY` is now explicit. *A guarantee must be a mechanism, not an
  argument.*
* Two non-blockers, both real: the downgrade lost 024's `COMMENT`, and the
  `/api/me` contract test never asserted `permissions`.

🔴 **AND MY OWN SUPERVISOR PASS FOUND THAT MY VERIFICATION PROVED LESS THAN IT
READ.** *"747 users checked, 0 role-set mismatches"* sounds conclusive. That
population contains **no** user with two roles in one organization, **no** user
in two organizations and **no** role with zero permissions — exactly the shapes
a missing DISTINCT breaks. Built all three synthetically in a rolled-back
transaction to get a real answer.

> **A measurement over a population that cannot exercise the risk is not
> evidence, however large the number is.**

---

### 🔴 The composition, not the parts

Every LAYER of I79 was verified and the JOIN between them was not — which is
the shape that produced 713/0/0 alongside a 404 sign-in on 08-24. So
`tests/e2e/shell/permissions.spec.ts` drives the real path: `tech.demo` signs
in through the real realm and the sidebar is read.

It asserts **both directions** — Laboratory must be PRESENT (`batch.view`) as
well as Administration ABSENT (`admin.users`), because an absence-only test
passes against an empty or broken sidebar. And it deliberately does **not**
use `TEST_SIGNIN_USER`, which defaults to `lead.demo` and would have passed
against the unfixed code.

**Falsified end to end, with a full rebuild and redeploy per direction:**

| bundle | result |
|---|---|
| I79 fixed | 1 passed |
| reverted to the pre-I79 pass-through, rebuilt, redeployed | **1 FAILED**, with its own diagnostic and a screenshot |
| restored, rebuilt | **34 passed** |

---

### ⚠️ Carried forward

* **`next build` rewrites `apps/web/tsconfig.json` on EVERY demo build.**
  Reverted four times today; `cab4c1c` reverted it last session. It will keep
  returning until someone commits the generated form or ignores it
  deliberately. Right now it is a trap that invites an unreviewed change into
  a commit.
* **Local migrations run as `postgres`, not `evercoat_owner`** —
  `alembic_version` is owned by `postgres` and denies `evercoat_owner`
  outright. Local is superuser; **Render is not**, so the 09-01 deploy meets
  that ownership question for real.
* **The tunnel is still a QUICK tunnel** — the hostname lives only as long as
  that `cloudflared` process. `cloudflared tunnel login` once ends the
  repointing tax.


---

## SESSION CLOSE 2026-08-24

Tip **`cab4c1c`**, pushed, tree clean, **CI 6/6 green**. Eight commits.

▶ **Restart the demo — ONE command now:**
`powershell -File scripts\demo-up.ps1` (prints the URL, writes
`tmp/tunnel_url.txt`). Full notes and every trap:
`Documents/session-archives/2026-08-24/RESTART_THE_DEMO.md`
Session record: `.../2026-08-24/README.md` · Progress report (PDF):
`Desktop/Evercoat-Progress-2026-08-24.pdf`

▶ **Next session's ranked task list is at the top of `TODO.md`.**

### What shipped

**23 of 37 endpoints across Laboratory, Testing, Formulations and MSD had no
browser caller.** All 37 do now — Laboratory 10→11, Testing **1→9**,
Formulations **1→13**, MSD 2→4. New workspaces at `/testing/test?id=…` and
`/formulations/formula?version=…`, plus plan-a-test, create-batch,
create-formula and reclassify.

### ✅ THE LIVE SUITE — 713 / 0 / 0, AND THE STACK IS STILL UP

Against **`https://file-dawn-trailer-corners.trycloudflare.com`** (read
`tmp/tunnel_url.txt` — a QUICK tunnel, so the hostname holds only while that
`cloudflared` process lives):

| phase | passed | failed | skipped |
|---|---|---|---|
| `api-live` | **682** | 0 | 0 |
| e2e (Playwright) | **31** | 0 | 0 |
| **TOTAL** | **713** | **0** | **0** |

Counts verified against each tool's OWN output — pytest's `682 passed`, and
Playwright's JSON decoded ONE DOCUMENT AT A TIME (it writes one per project;
a strict `json.load` dying on the second is how a green 31-test run reported
nothing and passed on 08-23).

### 🔴 713 GREEN AND SIGN-IN WAS 404 — READ I97

Every one of those assertions passed **while browser sign-in was broken**
(I96: Caddy's `/auth/*` identity prefix swallowed the app's own
`/auth/callback/`). `api-live` authenticates by DIRECT GRANT; the e2e shell
suite uses a seam compiled out of production builds. **Neither traverses the
callback.** The number was true and did not mean a human could log in.

**I97 is open for exactly this**: no test drives authorize → login form →
callback. Verified by hand instead — 302 with a real code, callback 200.

### The stack OUTLIVES the session now

`scripts/demo-up.ps1` starts cloudflared, the API and the web tier
**detached**, and the containers carry `--restart unless-stopped`. It derives
the tunnel hostname from cloudflared's own log, repoints all four things that
carry it, and **verifies the Keycloak client by reading it back** — four
self-inflicted bugs are written up in its header, including `next start`
printing "✓ Ready" while binding nothing.

Sign in as any of the ten roles with **`EvercoatDemo-2026!`**: `lead.demo`
`chem.demo` `eng.demo` `tech.demo` `dir.demo` `qa.demo` `admin.demo`
`proc.demo` `prod.demo` `exec.demo`.

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
