# CHANGELOG — EvercoatITWRD APP

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
