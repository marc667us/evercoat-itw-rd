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

### 🔴 CORRECTED 2026-08-17 — GATE-1's STATED BLOCKER WAS WRONG

**This file previously said GATE-1 was blocked by Docker VM memory, and
that stopping the `aw-*` stack would unblock it. Both are false, and
acting on them would have burnt a session — and pushed at the one thing
the operator forbade touching.**

The scenario cannot be executed at any amount of memory, because eleven
of its fifteen arrows have nothing to drive. Verified against the
filesystem and independently confirmed by Codex:

| Golden-scenario noun | Table | Route | Service | Web page |
|---|---|---|---|---|
| Formula / formula version | ✗ | ✗ | ✗ | ✗ |
| Lab batch | ✗ | ✗ | ✗ | ✗ |
| Sample | ✗ | ✗ | ✗ | ✗ |
| Test / raw measurement | ✗ | ✗ | ✗ | ✗ |
| Failure investigation | ✗ | ✗ | ✗ | ✗ |
| Approval engine | ✗ | partial¹ | partial¹ | ✗ |

¹ Requirement approval and opportunity decision only. There is no shared
approval engine, and none of the five templates in `CLAUDE.md` §9 exist.

**Playwright has never been configured.** `@playwright/test` and
`@axe-core/playwright` are devDependencies in `apps/web/package.json` and
there is an `npm run e2e` script, but there is **no `playwright.config.*`
and no `.spec.ts` anywhere in the repository.** The golden E2E was never
written. `npm run e2e` today fails for want of a config, not for want of
memory.

**Also measured:** only three web pages exist — `/`, `/dashboard`,
`/admin`. Every Slice 2 API surface (opportunities, pipeline,
requirements, My Work, projects) has **no user-reachable page**, and
`CURRENT_SLICE = 1` in `apps/web/lib/navigation.ts` renders the rest of
the sidebar disabled.

**Where GATE-1 actually belongs.** `IMPLEMENTATION_PLAN.md:436` schedules
the golden Playwright E2E in **Slice 7**, alongside messaging, MSD and
the dashboards — which is correct, because the scenario needs Slices 3–6
to exist first. GATE-1 is not a deferred *run*. It is unbuilt *work*,
misfiled as a blocked run.

**What must NOT happen:** a future session trying to "just run GATE-1",
or stopping the `aw-*` containers to make room for it. Neither helps.

**What must happen instead:** GATE-1 moves to Slice 7 and is re-scoped.

### ✅ 2026-08-17 — Playwright now exists, and the interim scope was corrected again

`playwright.config.ts` and `tests/e2e/` are in place and **28 E2E tests
pass**. The browsers were already cached; no download was needed.

**The interim scope proposed above turned out to be wrong too, for a
second reason nobody had recorded.** The plan was an E2E over the arrows
that DO exist — opportunity → project → stage gate → requirement → task.
That is also impossible in a browser: **`apps/web` makes no API calls at
all.** There is no `fetch`, no `next-auth` wiring and no sign-in flow
anywhere in the application. `next-auth` is a declared dependency that
nothing imports. So the browser has no means of driving *any* domain
operation, built or not.

What was built instead, and what each part actually proves:

- **`tests/e2e/shell/`** — the application rendered in real Chromium for
  the first time. Root redirect, landmarks, product identity, the
  navigation gating (an unbuilt destination must be inert, never a dead
  link), sidebar collapse keeping labels in the accessibility tree, and
  `/my-work` correctly 404ing rather than serving an empty shell.
- **`tests/e2e/shell/accessibility.spec.ts`** — **axe-core against WCAG
  2.1 AA**, which `CLAUDE.md` §11 has required since Slice 1 and which
  had never executed. It failed on its first run, with real defects (see
  below).
- **`tests/e2e/api/`** — the API under **uvicorn over real HTTP**, not
  Starlette's `TestClient`. Every registered GET is probed anonymously
  and must refuse; the OpenAPI surface is checked to still carry the
  Slice 2 write paths.

Both servers are started by Playwright itself and the Next app is
**rebuilt every run**, so a pass cannot come from a stale `.next` or from
something a developer left running.

**Verified the suite can actually fail**, rather than assuming: bumping
`CURRENT_SLICE` to 2 makes the gating test fail (My Work becomes a link
to a route that 404s), and it passes again when restored.

### 🔴 The first axe-core run found real WCAG AA failures

Present since Slice 1, on every page, and invisible to 26 passing web
unit tests:

- **Sidebar group headings** (`WORK`, `GOVERNANCE`) were `text-slate-400`
  on white — about **2.9:1** against a required **4.5:1** for normal
  text at 11px.
- **`EntityHeader` and `StatusBadge` `<dt>` labels** — same class, same
  failure. These appear on every entity screen from Slice 2 onward, so
  the defect was about to be inherited by every future page.
- **The `<code>` chip on `/admin`** — `slate-500` on a `slate-100`
  background is ≈4.35:1, just under the line.

All fixed. Disabled controls in `top-bar.tsx` deliberately keep
`text-slate-400`: WCAG 1.4.3 exempts inactive components, and axe agreed
— it did not flag them.

**Still not covered, and named so it is not mistaken for done:** the rule
this domain cares most about — that status is never conveyed by colour
alone — cannot be scanned yet, because `StatusBadge` is not rendered on
any page. Pass-green against fail-red is ΔE 4.2 under deuteranopia. When
the Slice 2 screens land, the colour+icon+text assertion belongs in
`accessibility.spec.ts`.

**Still true and still outstanding:** the full stack has never been up at
once. That remains the largest unproven assumption in the build.

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

## ✅ RESOLVED 2026-08-17 — the audit chain (and the diagnosis was wrong)

**Closed by migration 011.** Recorded here in full because the previous
entry named the wrong CAUSE, and the fix that follows from a wrong cause
is the wrong fix.

**What this file used to say:** `audit.events` is a single GLOBAL chain
that "forks under concurrency", because two transactions each read the
tail before either commits and both write `prev_hash = 'GENESIS'`.

**Why that was wrong.** `audit.chain_row()` takes
`pg_advisory_xact_lock()`, which is held until COMMIT. A second writer
blocks until the first finishes and then, under READ COMMITTED, takes a
fresh snapshot that includes the row just committed. Concurrency alone
never forked this chain.

**The real mechanism — measured, not reasoned.** The trigger was SECURITY
INVOKER, so its tail read was filtered by the `audit_org_isolation` RLS
policy. Every writer chained onto **its own organization's** tail. Six
interleaved inserts on a live database:

```
label     id    org        prev_hash points at
A1       681   org A       GENESIS
B1       682   org B       GENESIS      <- org B starts its own chain
A2       683   org A       A1           <- skips B1 entirely
B2       684   org B       B1
UNSCOPED 685   NULL        B2           <- splices across chains
A3       686   org A       A2
```

The chain was **already per-organization**, as an accident of RLS rather
than a decision. The observed symptom (two rows at GENESIS) was reported
correctly; it was never a race.

**The actual defect** was row 685: a writer with no `app.current_org` —
a migration, a backfill, a maintenance script — fell through to the
permissive branch, saw every row, and spliced one tenant's chain onto
another's, non-deterministically depending on who wrote last.

**Second defect found on the way:** the insert policy was
`WITH CHECK (true)`. Any session could write audit rows attributed to any
organization — forging entries in another tenant's tamper-evident log.

- [x] Migration 011: chain per `organization_id`, explicitly, in the
      trigger's own predicate rather than as a side effect of RLS
- [x] `chain_row()` is SECURITY DEFINER with a pinned `search_path`, so
      chain shape no longer depends on who is writing
- [x] Per-organization advisory lock (tenants no longer serialise against
      each other)
- [x] Insert policy refuses a scoped session writing another org's rows
- [x] `verify_chain` now REQUIRES an `organization_id` (`None` = the
      system chain); the Celery task passes it explicitly
- [x] Discontinuity recorded as an audit row of its own, so a break at a
      pre-011 row reads as a known regime change rather than as an attack
- [x] Regression tests: `tests/db/test_011_audit_chain_scope.py`

**One known future risk, with a failing tripwire rather than a comment.**
`chain_row()`'s tail read is immune today because `audit.events` has RLS
ENABLED but not FORCED, and an owner is exempt from a non-forced policy.
The planned cutover (`core.rls_permissive()` → FALSE, FORCE on) removes
that exemption and reintroduces the same class of defect for system and
unscoped writes. `test_the_force_rls_cutover_must_revisit_the_chain_trigger`
fails the moment the cutover lands and explains what to do.

---

## 🔴 E2E suite — Codex findings still OPEN (2026-08-17)

Codex reviewed the new Playwright suite specifically for "tests that
cannot fail". It found twelve; **five are fixed, seven remain**. Listed
here rather than left in a review log, because a suite that is weaker
than it looks is the thing it was built to prevent.

Fixed: `reuseExistingServer` (it silently disabled the rebuild locally),
the leak test now compares bodies rather than only status codes, the
organization-header test no longer claims to cover the authenticated
case, write operations are now checked for declared authentication, and
the `not-started` marker contrast (`text-slate-300`, ≈1.5:1) — which
**axe-core cannot catch**, because the marks are `aria-hidden` and axe
skips hidden nodes for contrast.

Still open:

- [ ] **HIGH — the E2E suite does not run in CI.** `.github/workflows/ci.yml`
      never installs the root package, never installs browsers, never
      invokes it. Every PR can be green without Playwright or axe-core
      having executed. This is the same shape as axe-core being "required
      in CI" for months while never running.
- [ ] **MEDIUM — the Administration submenu links to pages that do not
      exist.** `EntityHeader` renders every `not-started` submenu entry as
      a live link, and `app/admin/page.tsx` declares entries for absent
      pages. The sidebar carefully renders unbuilt destinations inert; the
      submenu does not, so the guarantee is only half-applied.
- [ ] **MEDIUM — a structurally invalid token triggers an outbound JWKS
      fetch.** `security.py` fetches keys before parsing the token at all,
      so arbitrary garbage causes a 5-second outbound request and a 503 —
      an avoidable availability vector. It should parse first and 401
      immediately.
- [ ] **MEDIUM — the navigation property test cannot tell "built" from
      "linked".** It accepts every anchor as built. An item that lost its
      `slice` and now points at a 404 would pass.
- [ ] **MEDIUM — the write-paths test checks path keys, not methods.**
      Removing POST from milestones/risks/members would leave the GET and
      keep it green.
- [ ] **MEDIUM — readiness accepts 503 unconditionally**, so a wrong
      database URL leaves the run green. Where CI supplies a database it
      should require 200.
- [ ] **LOW — the keyboard test presses Tab once on one page**, and CI
      `retries: 1` would let an intermittent failure pass as green.

---

## Deployment prerequisites — found by review, not yet needed

Neither of these affects this host, and nothing is deployed. Both would
bite on the FIRST real deployment, so they are recorded now rather than
discovered then.

- [ ] **Migration 011 needs an owner-capable migration role.** It calls
      `CREATE OR REPLACE FUNCTION audit.chain_row()` *before*
      `ALTER FUNCTION ... OWNER TO evercoat_owner`. Replacing a function
      requires ownership or membership in the owning role. Migrations run
      as `postgres` here, so it works; a non-superuser deployment role
      needs membership in the role that currently owns the function, or
      an out-of-band ownership transfer first.
- [ ] **Migration 012's CHECK constraints validate immediately.**
      `milestones_actual_date_matches_status` and
      `risks_mitigating_states_the_mitigation` are added and validated in
      one step. Both tables were empty here so it was safe. On a database
      carrying real rows, add them `NOT VALID`, remediate the violating
      rows explicitly, then `VALIDATE CONSTRAINT` — silently "fixing" R&D
      rows to satisfy a constraint is not acceptable.
- [ ] **The FORCE RLS cutover must revisit `audit.chain_row()`.**
      SECURITY DEFINER makes its tail read caller-independent only while
      RLS is ENABLED but not FORCED, because an owner is exempt from a
      non-forced policy. Covered by a test that fails when the cutover
      lands: `tests/db/test_011_audit_chain_scope.py::test_the_force_rls_cutover_must_revisit_the_chain_trigger`.

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
- [x] **Milestones and risks write endpoints** — done 2026-08-17,
      migration 012 + `app/domains/projects/planning.py`. The permissions
      did not merely lack grants, they **did not exist**: migration 002
      seeded codes for every future domain and none for milestone or
      risk. Added `milestone.manage`, `risk.create`, `risk.manage`, with
      create/manage split for risks mirroring `failure.create` vs
      `failure.close` — a Chemist who spots a single-sourced resin must
      be able to raise it; deciding it is closed is the Lead's call.
      Two invariants enforced in the database, not just the service:
      a milestone that is met/missed records WHEN, and a risk marked
      `mitigating` must state the mitigation.
      Tests assert the **dashboard counter actually moves** — a 201 with
      a tile still reading zero is the state this was fixing.
- [x] **Project members: assign/remove** — done 2026-08-17,
      `app/domains/projects/members.py`. Membership IS the RLS predicate,
      so this is the access grant, and the test asserts it from the
      colleague's own token rather than from the members list. Removal
      deactivates rather than deletes. The project's own lead cannot be
      removed: migration 006 rescues their view of the project ROW only,
      and every child policy tests `core.is_project_member` and nothing
      else — so removing the lead of a restricted project leaves them the
      header and none of its contents, which presents as "the project is
      empty" rather than as a permission error.

---

## Open decisions

None blocking. ADR-002 (LangGraph) and ADR-024 (full depth, gate by gate)
were both settled by the operator on 2026-08-16.

Still unanswered, non-blocking:

- [ ] Git remote — the repository is local only, no remote configured.
- [ ] Repository hosting policy — GitHub Actions assumed; CI logic lives
      in the workflow file and should move to `scripts/*.sh` so the
      runner stays swappable (ADR-010).
