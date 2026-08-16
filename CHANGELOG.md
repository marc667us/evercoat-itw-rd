# CHANGELOG — EvercoatITWRD APP

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
