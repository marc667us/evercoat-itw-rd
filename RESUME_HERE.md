# ▶ RESUME HERE — EvercoatITWRD APP

**Session closed 2026-08-16. Read this file first, then `TODO.md`.**

Repository is **local only, no git remote**. Tip: `5cb46a8`, working tree
clean.

---

## Where the build actually is

| | |
|---|---|
| Tests | **124 passed / 0 failed / 0 skipped** |
| API routes | 42 registered, app boots clean |
| Migrations | **010** applied and verified against a real database |
| Slice 1 | code-complete, **GATE-1 not met** (see below) |
| Slice 2 | Opportunities · Pipeline · Requirements · **My Work** · **Project dashboard** · **Administration §2** all shipped |

### Start the environment

```bash
# 1. The database container (already exists; start it if stopped)
docker start evercoat-postgres          # host port 55432

# 2. Migrations -- NOTE the two different roles
cd "apps/api"
export MIGRATION_DATABASE_URL="postgresql+psycopg://postgres:dev-superuser-pw@localhost:55432/evercoat_itw_rd"
export DATABASE_URL="postgresql+psycopg://evercoat_app:dev-app-pw@localhost:55432/evercoat_itw_rd"
export KEYCLOAK_ISSUER="http://x/realms/y"
python -m alembic upgrade head

# 3. The suite
TEST_DB_HOST=localhost TEST_DB_PORT=55432 POSTGRES_DB=evercoat_itw_rd \
TEST_OWNER_USER=evercoat_owner TEST_OWNER_PASSWORD=dev-owner-pw \
APP_DB_USER=evercoat_app APP_DB_PASSWORD=dev-app-pw \
DATABASE_URL="$DATABASE_URL" KEYCLOAK_ISSUER="$KEYCLOAK_ISSUER" \
python -m pytest tests -q -rs
```

> **`alembic_version` is owned by `postgres`, not `evercoat_owner`.**
> Running alembic as `evercoat_owner` fails with
> `permission denied for table alembic_version`. Use
> `MIGRATION_DATABASE_URL` with the superuser; `DATABASE_URL` stays on the
> app role.

---

## 🔴 THE STANDING CONSTRAINT — do not violate it

**The owner's words: *"if i find the autoworkshop in issues you will be
responsible for breaking it."***

Do not touch `aw-postgres`, `aw-keycloak`, or any `aw-*` container. All
database work uses **`evercoat-postgres` on port 55432**, which is this
project's own container.

Health at close (measured, not assumed):

| Container | Mem | CPU |
|---|---|---|
| `aw-keycloak` | 595.9 MiB | **0.16%** |
| `aw-postgres` | 230.9 MiB | 0.00% |
| `aw-minio` | 149.2 MiB | 10.37% |
| `evercoat-postgres` | 68.1 MiB | 0.00% |
| others (5) | ~50 MiB | — |
| **total** | **~1094 MiB of 3.782 GiB** | **~2.71 GiB free** |

**Correction to an earlier note:** `TODO.md` recorded `aw-keycloak` at
178% CPU as a GATE-1 blocker. It is at **0.16%**. That spike was
transient, so GATE-1's stated blocker is weaker than written — the real
constraint is the ~2.71 GiB ceiling, which matters for the Slice 7 Ollama
model size.

---

## ▶ NEXT SESSION — in this order

1. **GATE-1 — the golden end-to-end scenario.** Deferred by the owner
   with *"yes but come later to finish it"*, not cancelled. It is the
   single largest outstanding risk: it proves rule 6 (a technically
   passing test stays YELLOW until mandatory approvals complete) end to
   end. Full scenario is in `TODO.md`. Needs the whole stack plus a
   browser; there is now ~2.71 GiB of headroom to do it.
2. **`DATA_MODEL.md`** — the urgent documentation debt. `CLAUDE.md` §10
   and ADR-007 both promise it holds the test-status state dictionary and
   transition table, and **Slice 5 cannot be built correctly without
   it.** Write it before starting Slice 5.
3. **Partition the audit chain by organization** — see the known
   limitation in `TODO.md`. Currently a global chain that forks under
   concurrency and reports tampering that did not happen.
4. **Slice 2 remainder** — opportunities/milestones/risks *routes* exist
   only partly; milestones and risks have tables and dashboard counts but
   no write endpoints yet.
5. Then Slice 3.

---

## What this session actually changed

**Built:** My Work (tasks + inbox + counts), Opportunities (funnel, gate
decision, conversion to project), Project dashboard, Administration §2
(stage-gate config), `scripts/live-suite.sh`.

**Migrations 008, 009, 010** — every one of them fixing a defect that
would have reached a user:

- **008** — `'converted'` was missing from the opportunity status CHECK,
  so *every* conversion would have failed at runtime. And `on_hold` was a
  one-way door: the status existed from migration 003 and nothing could
  ever leave it, so "revisit next quarter" meant never.
- **009** — the pipeline reorder was broken. My comment claimed it was
  safe. See below.
- **010** — `stage_transitions.from_stage_id` had **no foreign key at
  all**, while `to_stage_id` had a composite tenant-qualified one.

---

## 🔴 Lessons worth carrying forward

**A COMMENT ASSERTING ENGINE SEMANTICS IS A CLAIM, NOT A CHECK.**
I wrote that a single `UPDATE ... FROM unnest()` was collision-free
"because a non-deferrable unique constraint is checked once at STATEMENT
end". PostgreSQL checks it **per row**. The reorder — the one operation
an Administration pipeline screen most obviously needs — would have
failed on the first swap an administrator attempted. Found by writing a
test that reverses a four-stage pipeline. Codex found it independently.
**Two methods, same defect; neither alone is the safety net.**

**DEFERRABLE CHANGES *HOW* A CONSTRAINT IS ENFORCED, NOT ONLY WHETHER IT
CAN BE POSTPONED.** Declaring it deferrable moves enforcement from a
per-row index check to a constraint trigger at end of statement. So the
`SET CONSTRAINTS ... DEFERRED` I added first was not merely redundant —
it was harmful, pushing violations to COMMIT past the route's error
handling, turning a 409 into a 500.

**RLS GIVES ZERO PROTECTION ON REFERENCES TO `core.users`.** Users are
not tenant-scoped, so every FK to them is a plain
`REFERENCES core.users(id)` and referential integrity bypasses RLS even
under FORCE. Two real holes: a task could be assigned to another tenant's
user, and `convert_to_project` accepted a foreign lead **and then
enrolled them as a project member**. The check existed in `reassign_task`
and nowhere else — which is exactly how a rule drifts. Now one shared
`app/core/tenancy.py`.

**A RULE CHECKED IN A SELECT AND ENFORCED IN A LATER UPDATE IS UNKNOWN AT
WRITE TIME.** Four instances. Two were load-bearing for other decisions:
"only the assignee may complete" is the stated reason `/api/my-work`
carries no permission dependency, and "a second decision is refused" is
the stated reason decision history survives.

**A FIX CAN INTRODUCE ITS OWN DEFECT.** `CrossTenantReferenceError` is
not a `TaskStateError`, so it escaped the routes as a **500**. Caught by
running the suite, not by re-reading the diff.

**MEASURE, DON'T QUOTE THE HANDOVER.** The 178% CPU figure in `TODO.md`
was stale by a wide margin.

---

## Governance record for this session

- **Codex CLI** — invoked, full review of the Slice 2 surface. Returned
  **9 defects** (5 high, 3 medium, 1 low). All 9 fixed, each with a
  regression test. Review output: `/tmp/codex_review.txt` (transient —
  the findings are recorded in the commit message of `5cb46a8`).
- **Supervisor** — run **independently**, not merely adjudicating Codex.
  It found the reorder defect by direct database experiment before Codex
  reported it, and separately found the requirement-bucket defect
  (3 of 6 statuses counted) and the untyped-NULL bind. Confirms the
  standing rule: **neither reviewer alone is enough.**
- **Live-test rule** — not yet applicable: nothing is deployed. `GATE-2`
  remains open and `scripts/live-suite.sh` is now written and
  syntax-checked, but **has never run against a real deployment.**
