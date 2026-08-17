# CLAUDE.md — EvercoatITWRD APP

**Read this file before every significant development task in this repository.**

---

## 1. Product mission

EvercoatITWRD APP is an industrial R&D product-development platform for formulated chemical products — polyester body fillers, automotive putties, epoxy putties, repair compounds, adhesives, structural adhesives, sealants, seam sealers, coatings, primers and UV-curing products.

It is **not** an electronic lab notebook, a formula repository, or a project tracker. It is a controlled digital operating environment for the complete R&D lifecycle, and its defining asset is the **digital thread**.

**Identity strings — use these exactly, everywhere:**

| Context | Value |
|---|---|
| Product display name | `EvercoatITWRD APP` |
| Repository / app folder | `EvercoatITWRD APP` |
| Internal package slug | `evercoat-itw-rd` |
| Database app identifier | `evercoat_itw_rd` |
| Docker project name | `evercoat-itw-rd` |
| AI assistant (product name) | `MSD — Material Science & Development Assistant` |
| AI assistant (module name) | `msd` |

Never rename the visible product to ITERDRD or another generic R&D name. Never call MSD "R&D Copilot" — that synonym is retired.

---

## 2. The digital thread — the backbone of the entire system

```
Opportunity → Project → Requirement → Research → Benchmark → Raw Material
  → Formula → Formula Version → Lab Batch → Material Lot → Sample
  → Test → Raw Measurements → Analysis → Approval
  → Failure/Improvement → Corrective Action → New Formula Version
  → Validation → Stability → Pilot → Scale-Up → Qualification
  → Released Product → Production/Field Performance → Complaint/CAPA
  → Improvement Project
```

**No major technical record may become an isolated data island.**

Before adding any entity, answer: *what does it link to, in both directions?* If the answer is "nothing", the design is wrong. A failed test must always be traceable to the formula and batch that produced it. A new formula revision must show exactly which failure or improvement objective caused it. A released product must remain traceable to the complete experimental history that justified its approval.

New work must **preserve** the thread. Dashboards must drill down to real source records.

---

## 3. The seven non-negotiable rules

These are the acceptance spine. Any change that violates one is a defect regardless of test results.

1. **PostgreSQL owns verified technical facts.** AI is never the system of record. Valkey is never authoritative.
2. **Python owns deterministic scientific calculation.** The LLM may *call* calculation tools and *explain* results; it must never perform the arithmetic. Formula normalization, batch scaling, theoretical density, resin/hardener ratios, cost, statistics, DOE analysis and optimization are Python functions with automated tests.
3. **Physical testing verifies; models only predict.** Predictions must never render as, or be mistaken for, confirmed test results. Calculated / Predicted / Measured are three visually distinct things.
4. **Humans approve.** AI must not approve a test, change a controlled formula, move a result from YELLOW to GREEN, confirm a root cause, override a reviewer, or release a product.
5. **Released formulations are immutable.** No silent modification after release. Changes go through Product Change Control and produce a new version.
6. **Green / Red / Yellow is derived, never user-selected — and a technically PASSING test stays YELLOW while mandatory approvals are incomplete.**
7. **Zero-cost open-source core.** No essential paid SaaS, paid AI API, paid database, paid auth, paid vector store, paid object storage, paid workflow engine or paid monitoring. Render and Resend are optional *adapters*, never architectural dependencies.

---

## 4. Mandatory technology choices

Frontend: **Next.js + React + TypeScript + Tailwind + shadcn/ui + Radix**, **TanStack Table + Virtual** (AG Grid is forbidden — Enterprise is commercial), React Hook Form + Zod, TanStack Query, **Apache ECharts** (not Recharts, not Plotly, for app charts).

Backend: **FastAPI + Python 3.12 + Pydantic v2 + SQLAlchemy 2.x + Alembic**.

Data: **PostgreSQL 16** (+ RLS) and **pgvector**. Identity: **Keycloak**. Cache: **Valkey**. Object storage: **Garage**, behind an S3-compatible port.

Scientific: NumPy, SciPy, Pandas, Polars, statsmodels, pyDOE3, Optuna, scikit-learn, SHAP.

Workflow: Celery on Valkey now, **Temporal OSS** for named durable workflows later, both behind `WorkflowPort`.

AI: **LangGraph OSS** + **Ollama**, behind `AgentOrchestrationPort` and an AI Gateway (ADR-002, settled).

> **Governance note.** Root `C:\Users\USER\CLAUDE.md` §0.1 makes Google ADK the only permitted agent framework platform-wide. **This project has an explicit, operator-granted exception** to use LangGraph, which the source documents mandate five times. It is recorded in ADR-002 rather than followed silently. Do not "correct" it back to ADK.
>
> **§0.2 and §0.3 still apply in full** — they are framework-independent:
> - **Orchestration first.** Root Orchestrator at `app/agents/orchestrators/root_orchestrator.py`; department Conductors at `app/agents/conductors/<dept>_conductor.py`. **Specialists never call other agents. API routes never call specialists directly.** MSD is reached through the orchestrator.
> - **Reusability.** `pyproject.toml` + pip-installable; public API in `__all__`; no hardcoded paths in business logic; no cross-department imports between specialists; `docs/REUSABILITY.md` lists exports and consumers.
>
> **Keep the framework leak bounded to `app/agents/graphs/`.** Domain tools in `app/agents/tools/` are plain Python with Pydantic signatures, callable and testable with no framework imported. Threads, turns, evidence links and checkpoints are our tables in the `ai` schema — LangGraph state is derived from ours and disposable. Streamed events are normalized to our own shape before reaching the client. If you find yourself importing LangGraph outside `graphs/`, stop.

Testing: Pytest, Hypothesis, Vitest, Playwright, axe-core, Locust, Bruno.
Quality/security: Ruff, mypy, ESLint, Prettier, pre-commit, Trivy, Semgrep Community, Gitleaks, SOPS + age.

**Forbidden as dependencies:** OpenAI / Anthropic / Gemini / Azure OpenAI / Bedrock APIs, Pinecone, Firebase, Firestore, MongoDB Atlas, Auth0, Clerk, paid Okta, Supabase Cloud, AWS S3, Azure Blob, GCS, Datadog, New Relic, Splunk Cloud, AG Grid Enterprise, commercial workflow SaaS, commercial OCR.

---

## 5. Database rules

- **NUMERIC, never float**, for percentages, masses, densities and measured values. Floating-point on a controlled formulation percentage is a defect.
- **FK delete rules are `RESTRICT` / `NO ACTION`** for projects↔formulas, formula_versions↔batches, batches↔tests, materials used in formulas, and released products. **Never cascade-delete R&D history.** Retire with `inactive` / `obsolete` / `archived`, never `DELETE`.
- **Composite `ON DELETE SET NULL` is banned** — it nulls every key column, including `NOT NULL` tenant keys. Name the column (PG15+).
- **Unique constraints live in PostgreSQL, not only in the app**, and every code is **tenant-scoped**: `(organization_id, project_code)`, `(formula_id, version_number)`, `(organization_id, raw_material_code)`, `(organization_id, product_code)`, `(organization_id, lab_batch_number)`, `(organization_id, sample_number)`, `(document_id, revision_number)`. A globally unique batch or sample number would stop Org B creating `LB001` because Org A has one — and the constraint violation itself discloses another tenant's record.
- **Every tenant-scoped table also declares `UNIQUE (id, organization_id)`.** This is mandatory, not an optimisation: PostgreSQL requires a unique index on referenced columns, so composite tenant-qualified foreign keys are impossible without it, and the first migration that omits it fails with *"there is no unique constraint matching given keys for referenced table"*.
- **Child→parent foreign keys are composite**, carrying `(id, organization_id)`. RLS stops cross-tenant *reads*; it does not stop cross-tenant *references*, because referential integrity bypasses RLS even under FORCE.
- **Index every FK used in joins**, plus `(organization_id, status)`, `(project_id, current_stage)`, `(formula_version_id, test_date)`, `(raw_material_id, supplier_id)`.
- **RLS with `FORCE ROW LEVEL SECURITY`** on `organization_id` for every proprietary table. **The app connects as a non-superuser role.** Local superuser development hides RLS defects that only surface in production — migrations, backfills and orphan checks must be written to run under `SET ROLE evercoat_itw_rd_app`.
- **Referential traceability rule:** no released product without a qualified formula; no qualified formula without validation and pilot evidence; no validated formula without lab batches and tests; no test result without traceability to the physical sample.
- **Audit is append-only** and unreachable from ordinary UI paths.
- Preserve **stage history**; never merely update `current_stage`.
- Store measurements as **value + unit** with canonical units (adhesion → MPa, density → g/cm³, time → minutes, temperature → °C) and explicit conversion functions. Never as free strings.

Logical schemas: `core` `projects` `innovation` `materials` `formulations` `laboratory` `testing` `workflow` `quality` `products` `knowledge` `messaging` `analytics` `modeling` `ai` `audit`.

---

## 6. RBAC rules

Authorization chain, enforced in this order on **every** request:

```
Authentication → Organization → Role → Permission → Resource Scope → Business Rule
```

plus PostgreSQL RLS as an independent database-layer backstop.

- **Authorize on permissions, not role names** — `project.create`, `formula.submit`, `formula.approve_lab`, `test.execute`, `test.review`, `test.confirm`, `failure.close`, `product.release`, …
- Ten realm roles: `product_development_chemist`, `product_development_engineer`, `product_development_lead`, `product_development_director`, `qa_compliance_officer`, `laboratory_technician`, `procurement_specialist`, `production_engineer`, `executive_viewer`, `administrator`.
- **Frontend permission checks are cosmetic.** Every control is re-enforced server-side.
- **Playwright must test attempted unauthorized access**, not merely that a button is hidden.
- One application, not four. Role-aware presentation; authorization decisions never live in the frontend.

---

## 7. AI safety boundaries

- **MSD operates under exactly the calling user's authorization boundary.** If the user cannot open Formula F100 through the app, MSD must not retrieve, summarize, infer or expose F100 in chat. **Filter retrieval before the model sees anything — never filter after generation.** AI must never become a permission-bypass channel.
- Every AI output passes: Pydantic schema validation → permission validation → evidence check → human review where controlled.
- **AI hypothesis ≠ accepted root cause.** `failure_hypotheses.status ∈ {proposed, under_review, accepted, rejected}`; only a human moves it to `accepted`.
- AI recommendations are labelled **"AI-generated recommendation — requires technical review."**
- MSD answers carry **evidence links to source records**. Conclusions become controlled records only by explicit human promotion into Technical Decision / Experiment Proposal / Recommendation / Failure Hypothesis / Corrective Action / Task.
- Informal chat never becomes authoritative knowledge automatically. Promotion to the Knowledge Library is reviewed, and the RAG layer distinguishes *Controlled Technical Knowledge* from *Historical Discussion*.
- Natural-language analytics must compile to **governed** queries. Never arbitrary SQL.

---

## 8. Formula immutability rules

- Formula numbers are **immutable** once issued.
- **Never update an approved formula in place.** Clone to a new version.
- Every version records `parent_version_id`, `change_reason`, `technical_hypothesis`, expected effect, and — after testing — **observed effect**.
- Genealogy supports branches: `F001 → F002 → F003 → F004-A / F004-B`.
- A submitted or approved formula cannot be silently changed.
- A released master formula is **read-only at the database level**, not merely hidden in the UI.
- Submission is hard-blocked when: total percentage is outside configured tolerance, required material data is missing, a restricted material is used, or a critical safety check fails.

---

## 9. Multi-level approval rules

One shared approval engine. Never re-implement approval inside Formula, Test, Validation, Pilot, Qualification or Release.

Five configurable templates:

| Template | Route |
|---|---|
| `SCREENING_SIMPLE` | Tester → Chemist/Engineer |
| `OVERSIGHT_STANDARD` | Tester → Engineer (→ Lead on escalation) |
| `VALIDATION_CONFIRMATION` | Tester → Engineer → Chemist → Lead |
| `QUALIFICATION_CONFIRMATION` | Tester → Engineer → Chemist → Lead → QA |
| `RELEASE_CRITICAL` | Tester → Engineer → Chemist → Lead → QA → Director |

- Sequential **and** parallel approvals supported.
- Decisions are richer than approve/reject: Approve · Approve with Condition · Return for Correction · Request Retest · Reject · Escalate · Request Additional Test.
- **Conditional approval yields YELLOW**, and the stated limitation is preserved (e.g. "valid for development comparison only — not valid for final qualification").
- **Segregation of duties:** at `qualification`/`release` authority, the executing user may not supply all mandatory approvals. Enforced server-side.
- Every approval writes an electronic decision record into the permanent audit history.

---

## 10. Green / Yellow / Red test logic

**Status is derived by rules. It is never a field a user picks.**

### The five stored axes — these are the canonical column names

Use these names exactly. Nothing else. `DATA_MODEL.md` holds the full state dictionary and transition table.

| Column | Values |
|---|---|
| `execution_status` | `not_started` · `in_progress` · `complete` · `abandoned` |
| `validity_status` | `valid` · `minor_deviation` · `invalid` |
| `calculated_result` | `pass` · `fail` · `inconclusive` · `improved` · `no_significant_change` · `worsened` |
| `review_state` | `awaiting_review` · `under_review` · `returned_for_correction` · `retest_requested` · `escalated` · `reviewed` |
| `approval_state` | `not_required` · `pending` · `conditionally_approved` · `approved` · `rejected` |

`display_color`, `final_status` and `final_confirmed` are **derived and server-owned**. They are never client-settable and never stored as user input. Do not invent `approved_result`, `technical_status` or `calculated_status` — earlier drafts used all three and the mismatch would have left a safety-critical field off the server-controlled blocklist under its real name.

### Derivation is strictly ordered — first match wins

An unordered table produced two valid answers for the same record. Implement this as an ordered algorithm:

```
1.  validity_status == invalid                      → RED    (INVALID — not graded)
2.  calculated_result == fail                       → RED    (REQUIREMENT FAILED)
3.  approval_state == rejected                      → RED    (REJECTED)
4.  execution_status != complete                    → YELLOW (INCOMPLETE)
5.  replicates_valid < replicates_required          → YELLOW (INCOMPLETE REPLICATES)
6.  cv > method.cv_limit                            → YELLOW (EXCESSIVE VARIABILITY)
7.  review_state in {returned_for_correction,
                     retest_requested, escalated}   → YELLOW (<state>)
8.  validity_status == minor_deviation              → YELLOW (DEVIATION UNDER REVIEW)
9.  margin < requirement.warning_threshold          → YELLOW (PASS WITH LOW MARGIN)
10. trend_alert == true                             → YELLOW (TREND CONCERN)
11. approval_state == conditionally_approved        → YELLOW (CONDITIONAL — <condition>)
12. approval_state != approved                      → YELLOW (AWAITING <next approver>)
13. purpose == screening and not confirmed          → GREEN  (SCREENING PASSED — preliminary)
14. otherwise                                       → GREEN  (<authority> CONFIRMED)
```

Every configurable threshold is a named key with an Administration screen: `test_method.calibration_breach_policy` (`invalidate` | `deviate`), `method.cv_limit`, `requirement.warning_threshold`, `method.trend_rule`.

- **Colour is never the sole indicator.** Always colour + icon + text: `✓ PASS`, `✕ FAIL`, `! CONDITIONAL`.
- **Display automatic evaluation and final disposition as two separate fields** — `Automatic evaluation: PASS` beside `Final disposition: YELLOW — Awaiting Lead approval`. A low-margin pass awaiting approval is both a pass and not final; one field cannot say that.
- **GREEN is authority-qualified**: `GREEN — Screening Passed (preliminary authority)`, never a bare green tick.
- **Every YELLOW states why and what the next required action is.** A yellow with no explanation is a defect.
- A RED confirmation result automatically opens or links a Failure Investigation.
- Store **raw measurements per replicate**, always. Never only the aggregate.
- `test_purpose` ∈ {screening, oversight, confirmation, improvement} is orthogonal to `authority_level` ∈ {preliminary, development, controlled, validation, qualification, release}. A green screening test is never qualification evidence.

---

## 11. UI consistency rules

- Every major page answers: *Where am I in the process? What is the current status? What changed? What requires action? What evidence supports this?*
- Two-level navigation: left sidebar selects the **domain**; top contextual submenu selects the **workflow area**; the workspace holds the task; a right drawer gives context without navigating away; breadcrumbs preserve orientation. Canonical structures are in `NAVIGATION.md`.
- Desktop-first (formulation, DOE and analytics are data-dense). Mobile covers dashboard, My Work, messages, notifications, approvals, project review.
- Accessibility is required, not optional: keyboard navigation, labels, focus management, screen-reader semantics, contrast, and **no colour-only status**. axe-core runs in CI.
- Unsaved-changes guard on formula edit, batch execution, test result entry and DOE setup.
- Post-action redirects follow the workflow: submit formula → approval status; approve lab → create batch; complete batch → samples/test queue; record failed test → failure investigation.
- Sidebar counts represent **actionable items**, not total rows.

---

## 12. Rules against duplication — read before writing any module

**Do not rebuild infrastructure per module.** Reuse these, always:

`StatusBadge` · `TechnicalDataGrid` · `EntityHeader` · `ContextSubmenu` · `ApprovalEngine` · `ApprovalTimeline` · `DiscussionPanel` · `AttachmentManager` · `TaskCard` · `NotificationService` · `AuditHook` · `KpiCard` · `ChartWrapper` · `HistoryTimeline` · `AiRecommendationCard` · `RequirementStatus` · `EntityLink` · `MeasurementInput`

Pilot, Validation, Stability, Quality and Qualification must add **zero** new approval, discussion, attachment, task, audit, notification or dashboard infrastructure. If a later module needs new infrastructure, that is a defect in the shared layer — fix it there.

**Before coding each module**, check: existing related module · reusable components · database relationships · role permissions · workflows · status enums · audit requirements · analytics dependencies · tests.

**After coding each module**: lint · type-check · migrations · unit tests · backend tests · relevant Playwright flow · permission verification · UI review · update `CONTEXT.md`, `MEMORY.md`, `BRAIN.md`, `CHANGELOG.md`, `TODO.md`.

---

## 13. Commands

> Slice 1 creates these. Until then they are the contract, not yet the implementation.

**Stack**
```bash
docker compose -f infrastructure/compose/docker-compose.yml up -d     # full stack
docker compose -f infrastructure/compose/docker-compose.yml logs -f api
docker compose -f infrastructure/compose/docker-compose.yml down
```

**Database**
```bash
cd apps/api && alembic upgrade head
cd apps/api && alembic revision --autogenerate -m "<message>"
./scripts/seed.sh                      # synthetic demo data (clearly labelled)
./scripts/backup.sh                    # pg_dump + Garage snapshot
```

**Dev**
```bash
cd apps/api && uvicorn app.main:app --reload    # http://localhost:8000  (/docs)
cd apps/web && npm run dev                      # http://localhost:3000
```

**Tests**
```bash
cd apps/api && pytest                    # backend + scientific (Hypothesis)
cd apps/web && npm run test              # Vitest
npm install                              # ONCE, at the repo root, for the E2E deps
npx playwright test                      # E2E (from repo root)
npx playwright test --project=shell      # browser: shell, navigation gating, axe-core
npx playwright test --project=api        # the API over real HTTP under uvicorn
npx playwright show-report               # traces and screenshots of failures
./scripts/live-suite.sh <deployed-url>   # full suite against a DEPLOYED site
```

**Quality**
```bash
cd apps/api && ruff check . && ruff format --check . && mypy app
cd apps/web && npm run lint && npm run typecheck
./scripts/quality-gate.sh                # Codex 5-pass + Supervisor adjudication
gitleaks detect --source .
trivy fs .
semgrep --config auto
```

---

## 14. Important directories

| Path | Contents |
|---|---|
| `apps/web/` | Next.js app; `app/` routes, `components/`, `features/`, `hooks/`, `services/`, `schemas/` |
| `apps/api/app/domains/` | One folder per business domain — models, schemas, services, repositories, routes |
| `apps/api/app/calculations/` | **Deterministic scientific code.** Pure functions, Hypothesis-tested. No I/O, no LLM. |
| `apps/api/app/agents/` | LangGraph agents + controlled tools. Never touches the DB except through domain services. |
| `apps/api/app/workflows/` | Stage-gate and approval state machines behind `WorkflowPort` |
| `workers/` | Scheduler / notification / analytics-refresh worker |
| `packages/` | Shared TS types, generated API client, ui-kit |
| `infrastructure/` | Compose, Caddy, Keycloak realm, SOPS |
| `tests/e2e/` | Playwright. `shell/` browser + axe-core, `api/` real-HTTP. The golden and RBAC suites arrive with Slice 7 — see the note below. |
| `docs/adr/` | Architecture decision records |

---

## 15. Definition of Done

A module is **not** done because CRUD works. Where applicable it needs:

database schema · relationships · migrations · indexes · constraints · Pydantic schemas · domain service · validation · business rules · REST API · RBAC + resource scope · frontend list/queue view · detail workspace · contextual submenu · status header · empty/loading/error states · workflow status · approval · tasks/notifications · discussion link · audit · dashboard KPI · analytics · Pytest · Hypothesis for scientific code · Playwright for critical flows · accessibility · documentation · `CONTEXT.md` / `MEMORY.md` / `BRAIN.md` / `CHANGELOG.md` / `TODO.md` updated.

**Then the four governance gates:** Codex CLI review → Supervisor audit → Work Reviewer Agent → Work Scheduler Agent.

**And the live-test rule (hard, platform-wide):** a deploy is not finished when CI turns green. It is finished when the **full suite has run against the deployed site** and the counts are reported as **three numbers — passed / failed / skipped** — never an exit code. Wait for the deploy to actually be live first; free-tier cold starts can take ~2 minutes, and a short timeout is not proof of an outage.

**A green build is not a working feature.** Build it, run it, and look at it in a browser.

> **What the E2E suite can and cannot prove today (2026-08-17).** The
> golden MVP scenario (§44) and the RBAC/MSD-boundary suite are **not**
> written, and a file named after either would be worse than none.
> Eleven of the golden scenario's fifteen steps have no table, route,
> service or page, and `apps/web` currently makes **no API calls at all**
> — no `fetch`, no `next-auth` wiring, no sign-in — so a browser cannot
> drive the digital thread. Both belong to Slice 7, where
> `IMPLEMENTATION_PLAN.md:436` already places them.
>
> What runs today: the shell in a real Chromium (routing, navigation
> gating, keyboard reachability), **axe-core against WCAG 2.1 AA** — which
> §11 has always required and which had never once executed until it was
> wired up and immediately found real contrast failures — and the API
> under uvicorn over real HTTP, where every registered GET is probed
> anonymously and must refuse.
