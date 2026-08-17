# DATA_MODEL.md — EvercoatITWRD APP

**Status: authoritative for the test-status model; partial for the rest.**

Written 2026-08-17. `CLAUDE.md` §10 and `DECISIONS.md` ADR-007 both name
this file as the holder of the **test-status state dictionary and
transition table**, and `TODO.md` records that Slice 5 cannot be built
correctly without it. That is the part below that is complete.

> **Read this before trusting any table here.** Every section is marked
> **BUILT** or **SPECIFIED**. *BUILT* means the objects exist in
> `apps/api/migrations/*.sql` and have been applied and tested against a
> real database. *SPECIFIED* means this document is the design, and
> nothing implements it yet.
>
> This distinction is not decoration. Three status artifacts in this
> repository have already been wrong — in both directions — and one of
> them (GATE-1's blocker) was wrong in a way that would have cost a
> session. A data-model document that silently mixes what exists with
> what is planned becomes the next one.

---

## 1. What exists today — BUILT

Migrations 001–013, applied and verified.

| Schema | Tables BUILT |
|---|---|
| `core` | `organizations`, `users`, `permissions`, `roles`, `role_permissions`, `organization_members`, `member_roles` |
| `innovation` | `opportunities` |
| `projects` | `projects`, `project_members`, `milestones`, `risks`, `requirements` |
| `workflow` | `stage_definitions`, `project_stages`, `stage_transitions`, `tasks` |
| `audit` | `events` |

Schemas **created but still empty**: `materials`, `formulations`,
`laboratory`, `testing`, `quality`, `products`, `knowledge`, `messaging`,
`analytics`, `modeling`, `ai`.

Everything in §4 below lives in those empty schemas. **None of it is
built.** That is the same fact that makes the GATE-1 golden scenario
unrunnable today, recorded here so the two cannot drift apart.

---

## 2. Tenancy invariants — BUILT, and non-negotiable

These hold for every table in every future slice. A new table that breaks
one is a defect regardless of tests.

1. **Every tenant table carries `organization_id NOT NULL`.**
2. **Every tenant table declares `UNIQUE (id, organization_id)`.** Not an
   optimisation: PostgreSQL requires a unique index on referenced
   columns, so a composite tenant-qualified FK is impossible without it,
   and the first migration that omits it fails outright.
3. **Child → parent foreign keys are composite**, carrying
   `(id, organization_id)`. RLS stops cross-tenant *reads*; it does not
   stop cross-tenant *references*, because referential integrity bypasses
   RLS even under FORCE.
4. **Composite `ON DELETE SET NULL` is banned** — it nulls every key
   column including `NOT NULL` tenant keys. Name the column (PG15+).
5. **FKs into R&D history are `RESTRICT` / `NO ACTION`.** Retire with
   `inactive` / `obsolete` / `archived`; never `DELETE`.
6. **Codes are unique per organization, never globally.** A global unique
   batch number would stop Org B creating `LB001` because Org A has one,
   and the constraint violation itself discloses another tenant's record.
7. **NUMERIC, never float**, for percentages, masses, densities and
   measured values.
8. **Measurements are value + unit**, in canonical units, never free
   strings.

### 2.1 The gap invariants 1–6 do NOT close — BUILT and important

**Foreign keys to `core.users` are plain `REFERENCES core.users(id)`,
because users are not tenant-scoped.** A user belongs to organizations
through `core.organization_members` and may belong to several. So RLS
gives **zero** protection on any user reference: an id RLS would never
let the caller read can still be assigned, named or enrolled.

Every such path must call `app.core.tenancy.require_active_member`.
Current call sites: task assignment and reassignment, opportunity
conversion, risk ownership, project membership. **Any new column
referencing `core.users` inherits this obligation.**

---

## 3. Test status — the state dictionary · SPECIFIED

**This is the section ADR-007 and `CLAUDE.md` §10 promise.** Nothing here
is built; `testing` is an empty schema. Slice 5 implements it.

### 3.1 The five stored axes

Use these names **exactly**. `approved_result`, `technical_status` and
`calculated_status` are forbidden — the drift across four earlier
documents would have left a safety-critical field off the
server-controlled blocklist under its real name (Supervisor S4).

| Column | Values | Meaning |
|---|---|---|
| `execution_status` | `not_started` · `in_progress` · `complete` · `abandoned` | Did the physical work happen? |
| `validity_status` | `valid` · `minor_deviation` · `invalid` | Was it done to method? |
| `calculated_result` | `pass` · `fail` · `inconclusive` · `improved` · `no_significant_change` · `worsened` | What did the numbers say, computed by Python? |
| `review_state` | `awaiting_review` · `under_review` · `returned_for_correction` · `retest_requested` · `escalated` · `reviewed` | Where is it in technical review? |
| `approval_state` | `not_required` · `pending` · `conditionally_approved` · `approved` · `rejected` | Where is it in the approval chain? |

**Derived and server-owned, never client-settable:** `display_color`,
`final_status`, `final_confirmed`. These must appear on the
server-controlled field blocklist under exactly these names.

**Orthogonal, and not part of the derivation:**

| Column | Values |
|---|---|
| `test_purpose` | `screening` · `oversight` · `confirmation` · `improvement` |
| `authority_level` | `preliminary` · `development` · `controlled` · `validation` · `qualification` · `release` |

Six authority levels, not five — `validation` is required because
`VALIDATION_CONFIRMATION` is a distinct approval template (ADR-012).
**A green screening test is never qualification evidence.**

### 3.2 Derivation — ordered, first match wins

An unordered table produced two valid colours for the same record
(Supervisor S3). This is an **algorithm**, not a lookup.

| # | Condition | Colour | Label |
|---|---|---|---|
| 1 | `validity_status = invalid` | RED | INVALID — not graded |
| 2 | `calculated_result = fail` | RED | REQUIREMENT FAILED |
| 3 | `approval_state = rejected` | RED | REJECTED |
| 4 | `execution_status ≠ complete` | YELLOW | INCOMPLETE |
| 5 | `replicates_valid < replicates_required` | YELLOW | INCOMPLETE REPLICATES |
| 6 | `cv > method.cv_limit` | YELLOW | EXCESSIVE VARIABILITY |
| 7 | `review_state ∈ {returned_for_correction, retest_requested, escalated}` | YELLOW | ‹state› |
| 8 | `validity_status = minor_deviation` | YELLOW | DEVIATION UNDER REVIEW |
| 9 | `margin < requirement.warning_threshold` | YELLOW | PASS WITH LOW MARGIN |
| 10 | `trend_alert = true` | YELLOW | TREND CONCERN |
| 11 | `approval_state = conditionally_approved` | YELLOW | CONDITIONAL — ‹condition› |
| 12 | `approval_state ≠ approved` | YELLOW | AWAITING ‹next approver› |
| 13 | `test_purpose = screening` and not confirmed | GREEN | SCREENING PASSED — preliminary |
| 14 | otherwise | GREEN | ‹authority› CONFIRMED |

**Rule 1 short-circuits before rule 2 deliberately.** "Technically
invalid" is a RED cause distinct from failure: an invalid test has no
trustworthy performance number to grade, so grading it would assert
something the data does not support (Codex F24).

**Rule 12 is why rule 6 of the seven non-negotiables holds.** A test that
passed technically stays YELLOW until mandatory approvals complete. That
single row is the most important assertion in the eventual golden E2E.

### 3.3 Presentation rules that are part of the model

- **Two separate fields, always**: `Automatic evaluation: PASS` beside
  `Final disposition: YELLOW — Awaiting Lead approval`. A low-margin pass
  awaiting approval is both a pass and not final; one field cannot say
  that.
- **GREEN is authority-qualified.** `GREEN — Screening Passed
  (preliminary authority)`, never a bare tick.
- **Every YELLOW states why AND what the next required action is.** A
  yellow with no explanation is a defect.
- **Never colour alone**: colour + icon + text (`✓ PASS`, `✕ FAIL`,
  `! CONDITIONAL`). Pass-green against fail-red is ΔE 4.2 under
  deuteranopia — indistinguishable for ~8% of men. This is a
  measurement, not a preference.
- **Raw measurements are stored per replicate, always.** Never only the
  aggregate: `cv` (rule 6) and `replicates_valid` (rule 5) cannot be
  recomputed from a mean.
- A RED **confirmation** result automatically opens or links a Failure
  Investigation.

### 3.4 Configurable thresholds — each needs an Administration screen

Administration is a thread across slices (ADR-021): a config value
referenced anywhere must have an Administration screen **in the same
slice or earlier**.

| Key | Values | Feeds |
|---|---|---|
| `test_method.calibration_breach_policy` | `invalidate` \| `deviate` | rules 1 / 8 |
| `method.cv_limit` | NUMERIC | rule 6 |
| `requirement.warning_threshold` | NUMERIC, per requirement | rule 9 |
| `method.trend_rule` | rule expression | rule 10 |

### 3.5 Transition table

Legend: **T** technician · **E** engineer · **C** chemist · **L** lead ·
**QA** QA/compliance · **D** director · **SYS** server-computed.

| Axis | From → To | Who | Guard |
|---|---|---|---|
| `execution_status` | `not_started` → `in_progress` | T (`test.execute`) | sample exists and is not consumed |
| | `in_progress` → `complete` | T (`test.execute`) | every required replicate has a raw measurement |
| | `in_progress` → `abandoned` | T, E | reason required; no result is graded |
| `validity_status` | `valid` → `minor_deviation` | T, E | deviation recorded with cause |
| | `valid`/`minor_deviation` → `invalid` | E (`test.review`), or SYS | SYS when calibration breach and policy = `invalidate` |
| `calculated_result` | ∅ → any | **SYS only** | computed by Python from raw replicates; never user-set (rule 2 of the seven) |
| `review_state` | `awaiting_review` → `under_review` | E, C (`test.review`) | reviewer ≠ executor |
| | `under_review` → `reviewed` | E, C | all replicates valid or deviation accepted |
| | `under_review` → `returned_for_correction` | E, C | reason required |
| | `under_review` → `retest_requested` | E, C, L, QA (`test.request_retest`) | creates the successor test, linked |
| | `under_review` → `escalated` | E, C | escalation target named |
| `approval_state` | `not_required` → `pending` | SYS | on `review_state = reviewed`, per the template for `authority_level` |
| | `pending` → `approved` | per template | **segregation of duties** (below) |
| | `pending` → `conditionally_approved` | per template | stated limitation is **mandatory** and preserved |
| | `pending` → `rejected` | per template | reason required |
| `final_confirmed` | false → true | L / QA / D (`test.confirm`) | only from `approved`; never from `conditionally_approved` |

**Segregation of duties, enforced server-side:**

- At `qualification` and `release` authority, the executing user may not
  supply all mandatory approvals.
- **QA approval may never come from anyone who supplied a
  development-side approval on the same test** (ADR-019). This is why
  authorization is on permissions and not role names: no role check can
  express a constraint that depends on per-test identity.
- No role holds both `test.approve_development` and `test.approve_qa`.

**Decisions are richer than approve/reject**: Approve · Approve with
Condition · Return for Correction · Request Retest · Reject · Escalate ·
Request Additional Test. Every one writes an electronic decision record
into permanent audit history.

### 3.6 Approval templates

One shared engine. Pilot, Validation, Stability, Quality and
Qualification add **zero** new approval infrastructure.

| Template | Route |
|---|---|
| `SCREENING_SIMPLE` | Tester → Chemist/Engineer |
| `OVERSIGHT_STANDARD` | Tester → Engineer (→ Lead on escalation) |
| `VALIDATION_CONFIRMATION` | Tester → Engineer → Chemist → Lead |
| `QUALIFICATION_CONFIRMATION` | Tester → Engineer → Chemist → Lead → QA |
| `RELEASE_CRITICAL` | Tester → Engineer → Chemist → Lead → QA → Director |

Sequential and parallel approvals are both supported.

---

## 4. The digital thread — SPECIFIED

```
Opportunity → Project → Requirement → Research → Benchmark → Raw Material
  → Formula → Formula Version → Lab Batch → Material Lot → Sample
  → Test → Raw Measurements → Analysis → Approval
  → Failure/Improvement → Corrective Action → New Formula Version
  → Validation → Stability → Pilot → Scale-Up → Qualification
  → Released Product → Production/Field Performance → Complaint/CAPA
  → Improvement Project
```

**BUILT portion:** `Opportunity → Project → Requirement`, plus the
project-scoped `Milestone`, `Risk`, `Task` and the `project_stages` /
`stage_transitions` history. Everything from `Research` onward is
specified only.

**Before adding any entity, answer: what does it link to, in both
directions?** If the answer is "nothing", the design is wrong.

Formula rules that constrain the schema when it is built:

- Formula numbers are **immutable** once issued.
- **Never update an approved formula in place** — clone to a new version.
- Every version records `parent_version_id`, `change_reason`,
  `technical_hypothesis`, expected effect, and after testing the
  **observed** effect.
- Genealogy branches: `F001 → F002 → F003 → F004-A / F004-B`.
- A released master formula is **read-only at the database level**, not
  merely hidden in the UI.

---

## 5. Audit — BUILT

`audit.events` is append-only, enforced by trigger, with a SHA-256 hash
chain. Python and SQL compute the hash from the same canonical
serialisation so each side verifies the other; the field order in
`app/core/audit.py` is a contract with `audit.canonical_content()`.

**Since migration 011 the chain is PER ORGANIZATION.** `prev_hash`
resolves against the last row carrying the same `organization_id`, with
`NULL` forming its own system chain. Verification must therefore name an
organization — a walk of the whole table sees several independent chains
interleaved in one id sequence and reports their boundaries as breaks.

Full reasoning, including why the previously recorded cause
("forks under concurrency") was wrong, is in
`migrations/011_audit_chain_per_organization.sql` and `TODO.md`.

---

## 6. Still to document

Not written yet, and named here rather than left implicit:

- Column-level DDL for the `testing` schema (Slice 5 will produce it;
  §3 is its specification).
- `DATABASE_RELATIONSHIPS.md` — the FK map with cardinalities.
- Retention and archival policy per schema.
- The `analytics` and `modeling` schemas.
