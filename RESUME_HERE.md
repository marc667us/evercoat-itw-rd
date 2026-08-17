# ▶ RESUME HERE — EvercoatITWRD APP

**Session closed 2026-08-17. Read this file first, then `TODO.md`.**

Repository is **local only, no git remote**.

---

## 🔴 THE ONE THING TO READ BEFORE PLANNING ANYTHING

**The previous version of this file put GATE-1 (the golden end-to-end
scenario) at the top of the queue and said Docker VM memory was blocking
it. That was wrong, and following it would have burnt this session** —
and pushed at the `aw-*` containers the operator forbade touching.

The scenario cannot run at any amount of memory, because eleven of its
fifteen arrows have nothing to drive. Formula, formula version, lab
batch, sample, test, raw measurement, failure investigation and the
approval engine have **no table, no route, no service and no page**.
Verified against the filesystem and confirmed independently by Codex.

**Playwright was never configured.** The packages are devDependencies and
`npm run e2e` exists, but there is no `playwright.config.*` and no
`.spec.ts` in the repository. The golden E2E was never written.

`IMPLEMENTATION_PLAN.md:436` schedules it in **Slice 7**, which is
correct — it needs Slices 3–6 first. GATE-1 is unbuilt work that had been
misfiled as a blocked run. Full detail in `TODO.md`.

**The lesson, which is the reusable part:** measure the repository; do not
quote the handover. This is the third status artifact in this project
found to be wrong.

---

## Where the build actually is

| | |
|---|---|
| Tests | **152 passed / 0 failed / 0 skipped** (was 124) |
| API routes | **51 registered** (was 42), app boots clean |
| Migrations | **013**, each applied and verified against a real database |
| Web pages | **3** — `/`, `/dashboard`, `/admin`. No Slice 2 surface is clickable. |
| Slice 1 | code-complete; full stack has still never run at once |
| Slice 2 | complete except the frontend |

### Start the environment

```bash
docker start evercoat-postgres          # host port 55432

cd "apps/api"
export MIGRATION_DATABASE_URL="postgresql+psycopg://postgres:dev-superuser-pw@localhost:55432/evercoat_itw_rd"
export DATABASE_URL="postgresql+psycopg://evercoat_app:dev-app-pw@localhost:55432/evercoat_itw_rd"
export KEYCLOAK_ISSUER="http://x/realms/y"
python -m alembic upgrade head

TEST_DB_HOST=localhost TEST_DB_PORT=55432 POSTGRES_DB=evercoat_itw_rd \
TEST_OWNER_USER=evercoat_owner TEST_OWNER_PASSWORD=dev-owner-pw \
APP_DB_USER=evercoat_app APP_DB_PASSWORD=dev-app-pw \
DATABASE_URL="$DATABASE_URL" KEYCLOAK_ISSUER="$KEYCLOAK_ISSUER" \
python -m pytest tests -q -rs
```

> **`alembic_version` is owned by `postgres`, not `evercoat_owner`.** Use
> `MIGRATION_DATABASE_URL` with the superuser; `DATABASE_URL` stays on
> the app role.

**`mypy` is NOT installed** in this environment, so `mypy app` from
`CLAUDE.md` §13 cannot run. Ruff check and format are clean.

---

## 🔴 THE STANDING CONSTRAINT — do not violate it

**The owner's words: *"if i find the autoworkshop in issues you will be
responsible for breaking it."***

Do not touch `aw-postgres`, `aw-keycloak`, or any `aw-*` container. All
database work uses **`evercoat-postgres` on port 55432**. Nothing this
session touched an `aw-*` container.

---

## What this session changed

**Migration 011 — the audit chain, on a corrected diagnosis.**
`TODO.md` blamed concurrency. `pg_advisory_xact_lock` is
transaction-scoped, so concurrency cannot fork this chain. Measured on a
live database, the real mechanism was RLS: `audit.chain_row()` was
SECURITY INVOKER and its tail read was filtered by `audit_org_isolation`,
so the chain was **already per-organization by accident**. The actual
defect was an **unscoped writer** — no `app.current_org` — which saw
every row and spliced one tenant's chain onto another's,
non-deterministically. A second defect surfaced on the way: the insert
policy was `WITH CHECK (true)`, so any session could forge audit rows
attributed to any organization.

**Migration 012 + new write paths.** `projects.milestones` and
`projects.risks` had dashboard counters and no writer — `milestones` did
not have one even in a test, so its counters had never been non-zero.
`project.assign_member` was a granted permission no route used. All three
now have endpoints, and the permissions for milestones and risks **did
not exist in the catalogue at all** and had to be created.

**Documentation.** `DATA_MODEL.md` written (queue item #2; blocks Slice
5). It marks every section BUILT or SPECIFIED, because mixing the two is
how this project's status artifacts went wrong.

---

## ▶ NEXT SESSION — in this order

1. **A `playwright.config.ts` and the first E2E that can actually pass.**
   Not the golden scenario — an interim one over what exists:
   opportunity → project → stage gate → requirement → task → milestone →
   risk. This would be the first time the stack has run end to end with a
   browser, which is the real outstanding risk. It needs the full stack
   up, and there is ~2.71 GiB of VM headroom.
2. **The Slice 2 frontend.** Five API surfaces have no clickable page and
   `CURRENT_SLICE = 1` in `apps/web/lib/navigation.ts` disables the rest
   of the sidebar. *A route with no caller is not shipped.*
3. **Slice 3**, per `IMPLEMENTATION_PLAN.md`.
4. Move GATE-1 to Slice 7 in the plan, where it belongs.

---

## 🔴 Lessons worth carrying forward

**A HANDOVER'S STATED BLOCKER IS A CLAIM, NOT A MEASUREMENT.** GATE-1's
blocker was recorded as Docker memory. The truth was that eleven of the
scenario's fifteen nouns do not exist. The memory figure was even
re-measured last session and corrected — which made the *rest* of the
entry look freshly verified when it had never been checked at all.

**A SYMPTOM CAN BE OBSERVED CORRECTLY AND EXPLAINED WRONGLY.** Two audit
rows really did both carry `prev_hash = 'GENESIS'`. The recorded cause —
a concurrency race — was impossible given the advisory lock already in
the code. The fix that follows from a wrong cause is the wrong fix; the
right one was found by writing six interleaved rows and looking at what
each `prev_hash` actually pointed at.

**CORRECT BY COINCIDENCE IS NOT CORRECT.** The chain was already
per-organization, and `verify_chain` already scoped itself — both because
RLS filtered them, not because anyone chose it. Behaviour that depends on
who is looking changes the moment a role, a policy or a call site
changes.

**ASK OF EVERY ENTITY: WHICH PRODUCTION PATH WRITES IT?** Caught
milestones (no writer anywhere, not even a test), risks (only a test
fixture), and project members (a granted permission with no route). Same
question, same result, third project running.

---

## Governance record for this session

- **Codex CLI** — invoked twice. First on the GATE-1 question, where it
  independently confirmed the finding with file-level evidence and
  sharpened one of my own claims (Playwright *is* a declared dependency;
  what is missing is the config and the specs). Then a full review of
  this session's diff.
- **Supervisor** — run independently rather than as an adjudicator of
  Codex. It established the audit-chain mechanism by direct database
  experiment, verified `digest()`'s schema against the pinned
  `search_path`, confirmed the function's owner and security attributes
  in `pg_proc`, and found the FORCE-RLS cutover risk now covered by a
  failing tripwire test.
- **Live-test rule** — still not applicable: nothing is deployed. GATE-2
  remains open and `scripts/live-suite.sh` has still never run against a
  real deployment.
- **Not used this session, by instruction:** Google ADK, Stitch.
