# TODO — EvercoatITWRD APP

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
- [ ] **`scripts/seed.sh`** — ten synthetic demo users, one per role,
      clearly labelled as demo data. Referenced by the realm file's
      comment; does not exist yet.
- [ ] **`scripts/live-suite.sh`** — referenced in `CLAUDE.md` §13.
- [ ] **`scripts/backup.sh` + restore smoke test** — Slice 1 was supposed
      to include a restore drill (Codex F43). Backup is designed in
      `SECURITY.md` §14 and not yet implemented. *An untested backup is
      not a backup.*
- [ ] **Container memory measurement** — recorded qualitatively (exit 137,
      178% CPU) but not as numbers. Needed before Slice 7 chooses an
      Ollama model size.

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

Do not start before GATE-1, or start knowing GATE-1 is outstanding and
record that choice.

- [ ] Opportunities → projects, project members, milestones, risks
- [ ] 8 seeded pipeline stages as **configuration rows**, not an enum
- [ ] **Stage history preserved** — never merely update `current_stage`
- [ ] Structured requirements: target / min / max / unit / criticality /
      verification method
- [ ] Requirements Verification Matrix
- [ ] Tasks + My Work inbox
- [ ] Project dashboard + context bar
- [ ] **Administration §2** — stage-gate configuration (ADR-021: a config
      value referenced anywhere must have an Administration screen in the
      same slice or earlier)

---

## Open decisions

None blocking. ADR-002 (LangGraph) and ADR-024 (full depth, gate by gate)
were both settled by the operator on 2026-08-16.

Still unanswered, non-blocking:

- [ ] Git remote — the repository is local only, no remote configured.
- [ ] Repository hosting policy — GitHub Actions assumed; CI logic lives
      in the workflow file and should move to `scripts/*.sh` so the
      runner stays swappable (ADR-010).
