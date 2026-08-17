# TODO — EvercoatITWRD APP

> **▶ Read `RESUME_HERE.md` first.** It carries the session pointer, the
> environment commands, and the standing AutoWorkshop constraint.


Ordered by what blocks what. Anything marked **GATE** must pass before
the slice it belongs to can be called complete.

---

## 🔴 CARRIED FORWARD — Slice 1's acceptance gate is NOT met

**Slice 1 is code-complete and gate-incomplete. Those are different, and
this file exists so the difference is not quietly forgotten.**

Everything in Slice 1 is written, committed and unit-verified — 63 tests
passing, migrations applied against real PostgreSQL, the API served over
HTTP, the web app built and served. What has **never happened** is the
whole stack running at once with a browser driving it.

### GATE-1 — Golden end-to-end scenario · **DEFERRED by the operator, 2026-08-16**

Mandated by the master prompt §44. Deferred with agreement, to be
completed in a later session — not cancelled.

```
Director creates/approves project
  → Lead assigns team
  → Chemist creates formula
  → Lead approves lab
  → Lab creates batch + sample
  → Engineer creates confirmation test
  → raw results entered
  → app analyzes
  → RED
  → failure investigation opens
  → Chemist creates revised formula
  → new batch
  → retest passes technically
  → YELLOW pending approvals
  → Engineer/Chemist/Lead approve
  → GREEN
  → formula becomes validation candidate
  → dashboards update
```

Every arrow asserted in **UI and database state**. The YELLOW→GREEN
transition is the single most important assertion in the suite: it is the
only thing that proves rule 6 — a technically passing test stays YELLOW
until mandatory approvals complete — actually works end to end rather
than in isolation.

**Why it is blocked:** the full stack needs postgres + valkey + garage +
keycloak + api + worker + web + caddy. Docker Desktop on this host runs a
3.78 GiB VM already carrying seven AutoWorkshop containers. A ninth
container was killed with exit 137 (VM-level OOM), and `aw-keycloak` sits
at 178% CPU — admin calls to it exceed 180s.

**What unblocks it:** stopping the `aw-*` stack for a window. That is the
operator's call and was not taken.

**What must NOT happen:** Slice 2 building on the assumption that this
passed. It has not been run.

### GATE-2 — Full live suite against a deployed instance

Platform-wide hard rule: a deploy is finished when the full suite has run
against the **deployed** site and the counts are reported as three
numbers — passed / failed / **skipped** — never an exit code. No deploy
has happened yet, so this has never run.

---

## Slice 1 — remaining work items

- [ ] **Administration tables wired to live endpoints.** The seven
      `/api/admin/*` routes exist and are tested; the screen renders the
      structure but shows no rows, because nothing can authenticate
      without a running Keycloak. Blocked with GATE-1.
- [ ] **Visual review of the sidebar.** `layout.tsx` passes an empty
      permission set deliberately, so most navigation does not render.
      The filter is proven in both directions by 17 tests, but no human
      has yet *seen* the full sidebar. Blocked with GATE-1.
- [x] **`scripts/seed.sh`** + `scripts/seed.py` — exist and are
      idempotent; all 10 roles have holders.
- [x] **`scripts/live-suite.sh`** — written 2026-08-16. Reports
      passed/failed/skipped as three numbers, never an exit code.
      Reconciles a non-zero exit against parsed counts, so a collection
      error or "no tests ran" is force-counted as FAILED rather than
      reading as a clean pass. **Syntax-checked and its dead-site path
      exercised; NEVER RUN AGAINST A REAL DEPLOYMENT** (nothing is
      deployed) — that is GATE-2.
- [x] **`scripts/backup.sh` + restore drill** — implemented and
      VERIFIED: 276 rows dumped and restored identically. *An untested
      backup is not a backup* — this one was tested.
- [x] **Container memory measurement** — done 2026-08-16, as numbers:
      **~1094 MiB of 3.782 GiB in use, ~2.71 GiB free.** Breakdown in
      `RESUME_HERE.md`.

      🔴 **CORRECTION:** the "178% CPU" recorded above for `aw-keycloak`
      is STALE. Measured at **0.16%**. That spike was transient, so
      GATE-1's stated blocker is weaker than this file claims — the real
      constraint is the ~2.71 GiB ceiling, which is what matters when
      Slice 7 picks an Ollama model size.

---

## 🔴 Known limitation — the audit chain forks under concurrency

Found while building Slice 2, recorded rather than papered over.

`audit.events` is a single GLOBAL hash chain. The insert trigger takes an
advisory lock and reads the current tail, but two transactions that each
read the tail before either commits will both write
`prev_hash = 'GENESIS'`, and the verifier reports a break that is an
artefact of concurrency rather than tampering.

The test suite reproduces it immediately, because it runs many short
transactions and rolls most of them back.

**Why it matters:** a tamper-evidence mechanism that raises false alarms
under normal load is one whose alarms stop being read. The first response
to a real break becomes "the hash thing is flaky again".

**The fix:** chain PER ORGANIZATION rather than globally —
`prev_hash` resolves against the last row for that `organization_id`, so
concurrent work in different tenants cannot fork each other, and a single
tenant's writes are already serialised by the advisory lock. Verification
then walks one organization's chain, which is also the only scope a
tenant administrator should be able to verify.

- [ ] Migration: partition the chain by `organization_id`
- [ ] `verify_chain` takes an organization and walks only that chain
- [ ] Document the discontinuity introduced by the migration itself

Until then `verify_chain(start_id=...)` verifies a contiguous run, which
is what the Slice 1 test now asserts.

---

## Documentation debt

`CONTEXT.md` lists these as forward declarations. They are referenced by
other files and do not yet exist:

- [ ] `REQUIREMENTS.md` · `ARCHITECTURE.md` · `DATA_MODEL.md`
- [ ] `DATABASE_RELATIONSHIPS.md` · `WORKFLOWS.md` · `UI_UX.md`
- [ ] `NAVIGATION.md` · `API_CONTRACTS.md` · `AI_ARCHITECTURE.md`
- [ ] `TESTING_STRATEGY.md` · `DEPLOYMENT.md` · `ACCEPTANCE_CRITERIA.md`
- [ ] `docs/REUSABILITY.md` — required by root §0.3

`DATA_MODEL.md` is the urgent one: `CLAUDE.md` §10 and `DECISIONS.md`
ADR-007 both promise it holds the test-status state dictionary and
transition table, and Slice 5 cannot be built correctly without it.

---

## Slice 2 — Projects, Pipeline, Requirements, My Work

> **Started 2026-08-16 with GATE-1 outstanding.** The operator chose to
> proceed. Recorded here rather than left implicit, because this file
> asked for exactly that.
>
> What it means in practice: everything Slice 2 builds sits on a Slice 1
> foundation that is unit-verified but never exercised end to end. If
> GATE-1 later fails, the fault will be in Slice 1 and the fix may reach
> up into Slice 2. Slice 2 work is therefore written to be independently
> testable — migrations verified against a real database, services tested
> through the API — so a Slice 1 defect surfaces as a specific failing
> test rather than a vague "nothing works".

- [x] Opportunities → projects (funnel, gate decision, conversion that
      keeps the thread link and enrols the lead)
- [x] 8 seeded pipeline stages as **configuration rows**, not an enum
- [x] **Stage history preserved** — new `project_stages` row per visit +
      append-only `stage_transitions`
- [x] Structured requirements: target / min / max / unit / criticality /
      verification method
- [x] Requirements Verification Matrix
- [x] Tasks + My Work inbox (list, counts, claim, complete, reassign,
      per-project view)
- [x] Project dashboard + context bar — shaped to CLAUDE.md §11's five
      questions, one key each
- [x] **Administration §2** — stage-gate configuration: list, create,
      edit, retire/restore, reorder (ADR-021 satisfied)
- [ ] **Milestones and risks have TABLES and dashboard COUNTS but no
      write endpoints.** A count with no way to create the thing it
      counts is a read-only dashboard panel that can only ever show zero.
      *Ask of every entity: which production path WRITES it?*
- [ ] Project members: assign/remove endpoints (`project.assign_member`
      exists as a permission; no route uses it yet)

---

## Open decisions

None blocking. ADR-002 (LangGraph) and ADR-024 (full depth, gate by gate)
were both settled by the operator on 2026-08-16.

Still unanswered, non-blocking:

- [ ] Git remote — the repository is local only, no remote configured.
- [ ] Repository hosting policy — GitHub Actions assumed; CI logic lives
      in the workflow file and should move to `scripts/*.sh` so the
      runner stays swappable (ADR-010).
