# CHANGELOG — EvercoatITWRD APP

## 2026-08-18 (pt3) — Slice 3's back half: the engine finally has callers

**229 tests collected** (from 155). **60 API routes** (from 51). Migrations
through **016**. `ruff check`, `ruff format` and `mypy` all clean.

🔴 **THE DATABASE TESTS IN THIS CHANGE HAVE NOT BEEN RUN LOCALLY.** The
Docker daemon on this host is wedged — `docker exec` returns HTTP 500,
`docker restart evercoat-postgres` fails with *"tried to kill container,
but did not receive an exit event"*, and a TCP connection to port 55432 is
accepted by the port proxy and then never answered (proven with a 90-second
`connect_timeout`, not assumed from a short one). Migration 015 has never
been applied on this machine. **Verification is CI's**, which starts a
clean `pgvector/pg16`, runs `alembic upgrade head` twice and the full
suite. What DID run here: `ruff`, `mypy`, an app-boot check confirming all
17 new routes register, and **43 passed / 0 failed / 0 skipped** on the
database-free tests.

Recorded this plainly because the alternative — reporting a green lint run
as though it were a green test run — is the exact failure this project's
own rules exist to prevent.

### What was built

`apps/web` has shipped `/materials`, `/suppliers` and
`/formulations/[code]` since Slice 3's front half, and
`app/calculations/formulation.py` has been pure, exact and
property-tested. **Nothing connected them.** There was no `materials`
table, no `formulas` table, no service and no route, and every figure on
the live formulation workspace is baked at BUILD time by
`scripts/build_demo_formulations.py`.

That is this codebase's most-repeated defect running backwards: normally a
table exists with no write path; here a screen existed with no table. The
question is the same one — *which production path WRITES this?* — and the
answer for the whole workspace was "a build script".

- **Migration 015** — `materials` (library, documents, lots, suppliers,
  the M:M) and `formulations` (formulas, versions, components), plus
  Administration section 3's `units` and `product_families`.
- **`app/domains/materials/service.py`** and
  **`app/domains/formulations/service.py`**.
- **17 routes** across `/api/materials`, `/api/suppliers`,
  `/api/formulations` and `/api/admin`.
- **`evaluate_version` is the first runtime caller of the engine** in this
  product's history.

### One vocabulary, not three

The status and role literals in migration 015 are taken from
`apps/web/lib/demo/demo-data.json`, which the deployed pages already
render — `development` / `approved` / `preferred` / `restricted` /
`obsolete` — rather than the `evaluation` / `lab_approved` /
`production_approved` that the permission names suggest. Inventing a
second set would have had the API return statuses the shipped UI has no
badge for. `test_015_materials_formulations.py` reads the CHECK constraint
out of `pg_constraint` and compares it against that JSON, so the two
cannot drift in silence.

### 🔴 `material.approve_production` existed and NO ROLE HELD IT

Found by asking the standing question of a *permission* rather than of a
role. Migration 002 defines the code and grants it to none of the ten
seeded roles: Chemist has create/edit, Lead has `approve_lab`, QA has
`restrict`, Procurement has create/edit. Nobody had it.

So **`preferred`, one of the five material statuses the deployed site
already renders, was a state no user of this system could ever set** —
not hidden, not permission-denied for most people; unreachable, for
everyone, permanently. This is the sixth instance of that defect class on
this platform, and the mirror image of the other five: a write path with
no holder rather than a role with no write path.

Migration 016 grants it to `qa_compliance_officer`, which already holds
`material.restrict` — the negative control over the same judgement.
Procurement was rejected as the holder for a stated reason: it holds
`material.create` and `material.edit`, so the same person would enter a
material's data and declare it fit for commercial production.

### 🔴 `tests/db/test_002_roles_permissions.py` DID NOT EXIST

Migration 002 has ended with this comment since Slice 1:

```
-- Verified by tests/db/test_002_roles_permissions.py:
--   * every permission code referenced in application source exists here
--   * every permission here is referenced somewhere in source
--   ...
```

**None of those five properties was checked by anything.** A comment
asserting a safety net made of prose, sitting at the bottom of the file
that defines the entire authorization model — which is the worst possible
place for it, because every other security claim in the product is
downstream of these grants. It is also how the orphaned permission above
survived.

The file is now written, with a sixth property the original comment did
not claim and which is the one that would have caught it: **every
permission must have at least one holder.**

### Immutability is the database's, not the service's

`CLAUDE.md` section 8 requires a released master formula to be read-only
*at the database level, not merely hidden in the UI*. Three triggers:
`formula_code` is immutable once issued; a version that has left `draft`
is frozen except for `status`, the approval columns and `observed_effect`;
and **components follow their version** — freezing the version row while
leaving its component rows writable would let an approved formula be
changed without a single column of the version ever being touched.

The component trigger is SECURITY DEFINER with a pinned `search_path`, so
its own lookup cannot be defeated by a session whose RLS view of
`formula_versions` is empty. A guard that passes when it cannot see its
subject is the "check that walks through its own gap" already recorded
twice against this platform. The FORCE-RLS cutover will need to revisit
it, and that is written in the migration next to the existing tripwire.

### Governance — three findings from Codex, all real, all fixed

Checked against source before acting, as the standing rule requires.

1. **HIGH — a non-member could WRITE into a restricted project.**
   `create_formula` inserted with the caller's `project_id` and no
   membership check. Migration 005 deliberately made the project-scoped
   `WITH CHECK` organization-only (requiring membership to WRITE makes the
   first row of a restricted project impossible to create), so the INSERT
   **succeeded** for a non-member and the row merely became invisible to
   them afterwards. Invisible is not refused: it landed in another team's
   confidential project. **And the module docstring asserted the opposite
   guarantee** — a comment claiming a rule the code did not implement,
   committed inside the docstring making the claim. Now an
   `INSERT ... SELECT` whose source row is the project under the same
   predicate the RLS `USING` clause applies.
2. **HIGH — `formula.view_cost` was bypassable one URL away.**
   `GET /versions/{id}` requires only `formula.view` and returned every
   component's `cost_per_kg` alongside its percentage — the whole cost of
   the formula, to a caller who lacked the cost permission. The key is now
   removed (not nulled: a null would say "no cost on file", which is a
   different and false claim).
3. **MEDIUM — production approval could skip laboratory approval.** QA
   holds both `material.restrict` and, since migration 016,
   `material.approve_production`, so QA could take a brand-new
   `development` material straight to `preferred`, never passing through
   `approved` or the Lead who holds `material.approve_lab`. Permission
   answers "may this person ever do this"; it cannot answer "may it be
   done from where the material is now". `ALLOWED_TRANSITIONS` now does,
   enforced inside the UPDATE's own WHERE clause rather than checked in a
   preceding SELECT.

Two further defects were found in self-review before Codex ran: a dead
branch in `compare_versions` reading a `_components` key that never
existed, and a weigh-up sheet ordered by the engine's return dict — which
places the largest line last because it absorbs the rounding remainder —
rather than by the formula's own display order.

### Administration section 3, in the same change that needed it

Migration 015 creates `materials.units` and `materials.product_families`.
Shipping two configuration tables with no writer, in the very change that
criticises exactly that pattern, would have made them the seventh and
eighth instances. `app/api/admin_reference_data.py` is their write path.

Material statuses are deliberately NOT editable rows: each one is reachable
through a distinct permission and rendered by a specific badge, so an
added status would be one no permission grants and no component draws.

## 2026-08-17 — Audit chain scope, milestone/risk/member write paths

**146 passed / 0 failed / 0 skipped** (from 124). **51 API routes** (from
42). Migrations through **012**, each applied and verified against a real
database. `ruff check` and `ruff format` clean. `mypy` is not installed
in this environment and could not be run.

### A recorded defect whose stated CAUSE was wrong

`TODO.md` carried the audit chain as "a single GLOBAL hash chain that
forks under concurrency: two transactions each read the tail before
either commits". That cannot happen — `audit.chain_row()` already took
`pg_advisory_xact_lock()`, which is transaction-scoped, and the tail read
after it takes a fresh READ COMMITTED snapshot.

Established by experiment instead of argument. Six interleaved inserts on
a live database:

```
label     id    org        prev_hash points at
A1       681   org A       GENESIS
B1       682   org B       GENESIS      <- org B starts its own chain
A2       683   org A       A1           <- skips B1 entirely
B2       684   org B       B1
UNSCOPED 685   NULL        B2           <- splices across chains
A3       686   org A       A2
```

The trigger was SECURITY INVOKER, so its tail read was filtered by the
`audit_org_isolation` RLS policy: the chain was **already
per-organization, by accident**. The genuine defect was row 685 — a
writer with no `app.current_org` saw every row and spliced one tenant's
chain onto another's, non-deterministically.

**Second defect found on the way:** the insert policy was
`WITH CHECK (true)`. Any session could write audit rows attributed to any
organization — forging entries in another tenant's tamper-evident log.

**Migration 011** chains per organization in the trigger's own predicate,
makes `chain_row()` SECURITY DEFINER with a pinned `search_path`, locks
the advisory lock per organization, replaces the insert policy, and
records the regime change as an audit row of its own so a break at a
pre-011 row reads as a known migration rather than as tampering.
`verify_chain` now **requires** an `organization_id`.

A FORCE-RLS cutover would reintroduce the same class of defect. That is
covered by a test that fails the moment the cutover lands, not by a
comment.

### Two counters that could only ever show zero

`projects.milestones` and `projects.risks` shipped in Slice 2 with
tables, indexes, RLS policies and dashboard counters — and no writer.
`milestones` had none even in a test fixture, so its counters had never
been non-zero. `projects.risks` had exactly one INSERT, in a test.
`project.assign_member` was a granted permission that no route used.

The permissions for milestones and risks **did not exist in the
catalogue**: migration 002 seeded codes for every future domain and none
for these. **Migration 012** adds `milestone.manage`, `risk.create` and
`risk.manage` — split for risks the way `failure.create` and
`failure.close` already are — plus two invariants enforced in the
database: a milestone that is met or missed records *when*, and a risk
marked `mitigating` must state its mitigation.

The tests assert the **dashboard counter moves**, not merely that the
endpoint returns 201. A create endpoint whose result is invisible is the
state this work was fixing.

Project membership is the RLS predicate, so adding a member *is* the
access grant; the test asserts it from the colleague's own token. Removal
deactivates rather than deletes, and the project's own lead cannot be
removed — migration 006 rescues their view of the project row only, while
every child policy tests `core.is_project_member` and nothing else, so
removing them from a restricted project leaves the header and none of its
contents.

### GATE-1 corrected

The golden E2E was recorded as blocked by Docker VM memory. It is not
runnable at any amount of memory: eleven of the scenario's fifteen arrows
have no table, route, service or page, and Playwright has no config and
no spec files anywhere in the repository. Re-filed to Slice 7, where
`IMPLEMENTATION_PLAN.md:436` already put it. Detail in `TODO.md`.

### Documentation

`DATA_MODEL.md` written — the test-status state dictionary, the ordered
derivation, and the transition table that `CLAUDE.md` §10 and ADR-007
both promise, and that Slice 5 needs. Every section is marked **BUILT**
or **SPECIFIED**, because mixing the two is how the artifacts above went
wrong.

### Codex review — 10 findings, 8 fixed, 2 documented

Codex confirmed the audit-chain diagnosis independently and returned ten
findings on the work itself. The serious one is worth naming:

- **HIGH — child mutations were not bound to the project in the URL.**
  `set_milestone_status` and `update_risk` filtered on child id and
  organization only. `require_project_member()` authorises the project in
  the *path*, and the service then ignored it — so a member of project A
  could pass A's id in the URL with project B's milestone id and mutate
  it. RLS does not repair this: the child policy admits rows from any
  `normal` project in the organization. **Fixed**, and the regression test
  was verified to fail without the fix and pass with it.
- **HIGH — `verify_chain` never authenticated the head of the walk.**
  The first row's `prev_hash` was skipped, so deleting a chain's genesis
  event promoted its second event to first-returned and the walk reported
  the chain intact. Deleting a row is exactly what the chain exists to
  detect. **Fixed**: a full walk must begin at `GENESIS`; a bounded walk
  seeds from the last row of the same chain at or before the boundary.
- **HIGH — the audit insert policy from 011 was still fail-open in one
  direction.** `organization_id IS NULL` was unconditional, letting any
  tenant session append to the platform's SYSTEM chain, and
  `current_org_id() IS NULL` made any accidentally unscoped connection
  trusted for every organization. **Fixed by migration 013.**
- **MEDIUM — the duplicate-risk race still became a 500.** My own comment
  said the constraint "still fires if two requests race here", and nothing
  caught it. **Fixed** by translating `risks_org_code_key` at the insert.
- **MEDIUM — member removal locked only the membership row**, so a
  concurrent lead assignment could defeat the lead guard. **Fixed** with
  `FOR UPDATE OF pm, p`.
- **LOW — repeated removal wrote a false audit transition**, claiming a
  move from `active` that never happened. **Fixed**: only an active
  membership can be removed.
- **LOW — the definer `search_path` did not name `pg_temp` last.**
  **Fixed by migration 013.** `public` must stay: pgcrypto's `digest()`
  lives there, verified in the live catalogue.
- **HIGH — `SECURITY DEFINER` does not survive a FORCE RLS cutover.**
  Correct, and 011's comment overclaimed by implying it did. **The comment
  is corrected in 013**; the condition was already covered by a test that
  fails the moment the cutover lands.

**Documented rather than fixed, deliberately:**

- **Migration 011 uses `CREATE OR REPLACE FUNCTION` before its
  `ALTER ... OWNER`.** On a deployment whose migration role is not a
  superuser and does not hold membership in the owning role, that fails.
  It does not affect this host (migrations run as `postgres`) and no
  deployment exists. Recorded in `TODO.md` as a deployment prerequisite.
- **Migration 012's CHECK constraints are validated immediately.** On a
  database with pre-existing violating rows the migration would roll
  back. Both tables were empty here. The `NOT VALID` → clean →
  `VALIDATE` pattern is recorded in `TODO.md` for the first real
  deployment.

---

## Slice 1 — Foundation, Identity, Administration §1, Shell, Observability

**Status: code-complete, GATE-INCOMPLETE.** The golden end-to-end
scenario has never run — see `TODO.md` GATE-1. Deferred by the operator
on 2026-08-16, not cancelled.

### Verified

| | |
|---|---|
| API tests | **37 passed / 0 failed / 0 skipped** |
| Web tests | **26 passed** |
| Migrations | `alembic upgrade head` twice from empty, second run a no-op |
| API over HTTP | `/health/live` 200 · `/health/ready` 503 (correct, no DB) · `/api/admin/roles` 401 · `/metrics` 200 |
| Web build | `next build` exit 0, 4 routes · `tsc` 0 errors · eslint clean |
| Lint | `ruff check` + `ruff format` clean, 17 files |

### Defects found by running things, not by reading them

1. **`SET LOCAL app.current_user` is a syntax error.** `current_user` is
   a reserved SQL keyword; PostgreSQL rejects it even inside a qualified
   custom GUC name. Would have broken every authenticated request.
2. **The app could not import.** `EmailStr` needs `email-validator` at
   class-definition time and it was undeclared — the container would not
   have started. Syntax checks passed.
3. **The app aborted during startup.** `structlog.stdlib.add_logger_name`
   reads `logger.name`, which `PrintLogger` lacks. It raised on the first
   log line, before binding a port, buried in a structlog traceback.
4. **`audit.events` lacked its composite tenant key**, which the rule
   requires without exception.
5. **Alembic's version table could not live in `audit`.** Fixing it by
   pre-creating the schema introduced a worse bug: the schema became
   owned by the migration user, so `AUTHORIZATION evercoat_owner` silently
   became a no-op and the owner role lost `USAGE`.

### Measured, not assumed

- Pass-green vs fail-red is **ΔE 4.2 under deuteranopia**. Roughly 8% of
  men cannot distinguish them by hue. This is the measurement behind the
  colour + icon + text rule.
- Three series colours validated all-pairs both modes; a fourth fails.
- Docker VM cannot fit a ninth container: exit 137, VM-level OOM.

### Added

Migrations 001–002 · Alembic · five DB roles · RLS on organization **and**
project membership · composite tenant keys · SHA-256 audit hash chain ·
session context with fail-closed guard · Keycloak JWT verification ·
permission + resource-scope dependencies · Administration §1 (7 routes) ·
Celery worker · health/metrics/structured logging · Next.js shell ·
sidebar from a single navigation source · 8 shared components ·
CI (3 jobs) · Keycloak realm · compose stack.

### Decisions

ADR-001…024 in `DECISIONS.md`. Two settled by the operator: **ADR-002**
LangGraph (an explicit exception to root §0.1) and **ADR-024** full
depth, gate by gate.

### Review

56 findings raised across Codex and Supervisor; 53 upheld and addressed.
Record in `docs/REVIEW_PASS1_ADJUDICATION.md`.
