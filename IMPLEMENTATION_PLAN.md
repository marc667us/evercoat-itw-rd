# IMPLEMENTATION_PLAN.md — EvercoatITWRD APP

**Product display name:** EvercoatITWRD APP
**Internal package slug:** `evercoat-itw-rd` · **DB identifier:** `evercoat_itw_rd` · **Docker project:** `evercoat-itw-rd`
**Workspace:** `C:\Users\USER\Documents\evercoat-itw-rd-workspace\`
**Reference (read-only):** `<workspace>\ITERDRD App\` — `EvercoatRD App1.txt` (944 lines) + `ITWRD App.txt` (29,862 lines). Canonical originals untouched at `C:\Users\USER\Documents\evercoatRD App\`.

**Status: v3 — post second review pass.**

Claude drafted v1 → **Codex reviewed: FAIL**, 43 findings, 5 BLOCKER → **Supervisor adjudicated: FAIL upheld**, 40 upheld / 3 overturned or narrowed / 1 escalated → v2 → **Supervisor independent code-review: 13 further findings, 9 of them new**, three surviving into v2 → v3.

**56 findings raised, 53 upheld and addressed here.** One remains open by design: ADR-002 (LangGraph vs Google ADK), which is the operator's decision and is required before Slice 8. Full record in `docs/REVIEW_PASS1_ADJUDICATION.md`. Reuse analysis in `REUSE.md`. Decisions in `DECISIONS.md` (ADR-001…024).

---

## A. What was found in the reference folder

The reference folder contains **no source code, no schemas, no migrations, no UI components, no configuration and no prior implementation plan.** Two plain-text documents, nothing else.

This is the most consequential finding, because the master prompt (§3, §9) assumes a reference *application* exists and instructs Claude to "reuse only components that meet the new architecture". **There is nothing to reuse. This build is greenfield.**

Codex sharpened what that costs, and it is accepted: no tested domain invariants, no validated calculation routines, no established authorization model or Keycloak realm, no UI components or accessibility baseline, no CI, no seed data, no golden fixture. Every ambiguous requirement becomes a design decision needing its own acceptance test. And critically — **synthetic data cannot validate scientific correctness.** The formula calculation engine requires review by an actual formulation chemist before it is trusted in production; passing tests against invented numbers proves only internal consistency.

| File | Lines | Content |
|---|---:|---|
| `EvercoatRD App1.txt` | 944 | UPDATED CONCEPT NOTE, 41 §. Introduces **MSD — Material Science & Development Assistant** |
| `ITWRD App.txt` | 29,862 | **Fifteen** concatenated iterative passes, ending in the **MASTER CLAUDE CODE PROMPT** (L27,909) + two amendments (L29,736+) |

The fifteen passes, with verified line anchors:

| # | Pass | Lines |
|---:|---|---|
| 1 | Consolidated System Implementation Blueprint | 1–3,491 |
| 2 | Zero-Cost Open-Source Technology Stack | 3,494–5,157 |
| 3 | Dashboards, Analytics, Infographics | 5,161–7,141 |
| 4 | End-to-End Application Workflow | 7,144–8,927 |
| 5 | Stack narrative + Render/Resend/Playwright | 8,932–10,137 |
| 6 | Consolidated Application and Implementation Plan | 10,139–11,538 |
| 7 | Frontend/Backend/Database/Schemas/UI narrative | 11,540–12,945 |
| 8 | Database Relationships | 12,947–15,009 |
| 9 | Navigation narrative | 15,014–16,699 |
| 10 | **Test Module narrative** | 16,706–18,440 |
| 11 | Messaging module — copy 1 | 18,447–19,884 |
| 12 | Messaging module — copy 2, verbatim | 19,887–**21,329** |
| 13 | Updated MVP Build and Follow-Up Full Build Plan **(begins L21,330, not 21,336)** | 21,330–22,655 |
| 14 | Two-week schedule + revised re-estimate | 22,662–26,310 |
| 15 | Expanded Requirements | 26,315–27,901 |
| — | **MASTER PROMPT + amendments** | 27,907–29,862 |

*v1 said "ten passes" and then listed fifteen with mismatched section counts. Since §A is the provenance record the whole reconciliation register cites, that inconsistency undermined the "later supersedes earlier" arbitration rule. Corrected.*

**Precedence applied throughout** (master prompt §2): repetition is refinement, not duplicate functionality. MASTER PROMPT > Expanded Requirements > topic narratives > original Blueprint. Later + more explicit wins; safety/security/data-integrity beats convenience; testing beats AI prediction; human approval is mandatory.

---

## B. Main consolidated product requirements

An industrial R&D product-development platform for formulated chemical products — polyester body fillers, automotive putties, epoxy putties, repair compounds, adhesives, structural adhesives, sealants, seam sealers, coatings, primers, UV-curing products.

Not an ELN, not a formula repository, not a project tracker. A controlled digital operating environment whose defining asset is the **digital thread**:

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

### The seven non-negotiable rules

1. **PostgreSQL owns verified technical facts.** AI is never the system of record.
2. **Python owns deterministic scientific calculation.** The LLM calls tools and explains; it never does the arithmetic.
3. **Physical testing verifies; models only predict.** Predictions never render as confirmed results.
4. **Humans approve.** AI cannot approve a test, change a controlled formula, confirm a root cause, or release a product.
5. **Released formulations are immutable** — including indirectly, via components, material revisions or documents (F35).
6. **Green/Red/Yellow is derived, never selected** — and a technically passing test stays YELLOW while mandatory approvals are incomplete.
7. **Zero-cost open-source core.** Render and Resend are optional adapters, never dependencies.

### Canonical roles

Ten seeded Keycloak realm roles: `product_development_chemist` · `product_development_engineer` · `product_development_lead` · `product_development_director` · `qa_compliance_officer` · `laboratory_technician` · `procurement_specialist` · `production_engineer` · `executive_viewer` · `administrator`.

**Roles are seeded defaults; capability is modelled independently.** QA review, compliance review and regulatory review are **separate permissions** that a deployment may assign to one person or three (F3/F12). Nothing in the data model assumes they are one actor, and approval routes may demand *distinct persons* regardless of role.

**Authorization chain, every request:**
`Authentication → Organization → Role → Permission → Resource Scope → Business Rule`
with PostgreSQL RLS enforcing **both** organization isolation **and** project membership (see §J — this changed after review).

---

## C. Repeated requirements normalized

| # | Repetition | Normalization |
|---|---|---|
| R1 | Messaging module appears **verbatim twice** — L18,447–19,884 and L19,887–**21,329** | One module; copy 2 ignored. **Precise boundary matters:** the next section, *Updated MVP Build and Follow-Up Full Build Plan*, begins at **L21,330**. v1 marked the duplicate as running to 21,335, which would have discarded that section's title and opening paragraph — the very text mandating dashboards as core MVP components rather than a later reporting feature, and therefore the justification for Slice 7's dashboards |
| R2 | Sidebar specified **six times** | One canonical sidebar (§E) |
| R3 | Zero-cost stack listed **five times** | One stack table (§E) |
| R4 | Role dashboards specified **four times** each | One spec per role; MVP subset + full-build additions |
| R5 | 14-day schedule appears **twice** | Second supersedes; both re-based honestly (§K) |
| R6 | Digital thread restated **nine times** | One canonical thread (§B) |
| R7 | Green/Red/Yellow defined **five times** | One state machine (§E) |
| R8 | Approval routes listed **four times** | Five configurable templates, one engine |
| R9 | Formula genealogy example restated **five times** | One `parent_version_id` model with branches |
| R10 | Reusable components listed **three times** | One shared library, Slices 1–3 (§E) |
| R11 | Flat `test_results` vs 13-table decomposition | Decomposition (source: "preferable to forcing everything into a single test-results table") |

---

## D. Reconciliation register — rebuilt in four classes

Codex correctly objected that v1 conflated genuine contradictions with ordinary decisions, which overstated the reconciliation work and buried the ones that mattered (F7). Rebuilt:

### D.1 True contradictions — source says two incompatible things

| # | Contradiction | Resolution | Basis |
|---|---|---|---|
| **X1** | **Test result model.** Blueprint §29 (L1,113): single `pass_fail`. Test narrative §49 (L18,150–18,170): `calculated_status` / `technical_status` / `final_status` / `display_color` / `review_status`. | Full state model (§E). `pass_fail` is superseded — it structurally cannot express YELLOW. | Later, far more detailed, integrity-critical |
| **X2** | **Repository layout.** Blueprint §9 vs master amendment L29,769–29,797. | Master amendment. | Last statement; "must contain" |
| **X3** | **Charts.** Blueprint §2 (L132) "Recharts or Plotly" vs Stack §6/master §15 **Apache ECharts**. | ECharts. Matplotlib/Plotly only for server-side static plots in PDFs. | Later + explicit |
| **X4** | **Object storage.** Blueprint §6 MinIO vs Stack §19/master §36 Garage. | Garage behind `ObjectStoragePort`. *Not claimed drop-in* — multipart, signing, versioning and retention differ (F7/C3). | Later + explicit |
| **X5** | **Sidebar WORK group.** Navigation §66 omits Messages; master §13 + Expanded §41 include it. | Include Messages. | Later, two independent passes |
| **X6** | **Sidebar INTELLIGENCE group.** Navigation §66 omits Product Models; master §13 + Expanded §41 include it. | Include Product Models. | Same |
| **X7** | **Formula submenu.** Navigation §68: 11 items; master §14 + Expanded §43: 13, adding Predicted Performance + Discussion. | 13 items. | Later + explicit |
| **X8** | **Test authority levels.** Master §23: 6 levels; Test narrative §6: 5 (omits `validation`). | 6. `validation` is required — VALIDATION_CONFIRMATION is a distinct template. | Later; internally consistent |
| **X9** | **MSD/RAG in MVP.** Concept Note §38 (L858–878) requires knowledge retrieval + an initial MSD chatbot **in the MVP**. Master §46 omits AI from MVP-1 scope; §47 assigns Knowledge/RAG to the follow-up build. | **Both satisfied.** MVP-1 ships MSD over *structured* tool-calls (8 of the 9 mandated first-MSD capabilities need no RAG). Document RAG/pgvector stays Slice 8. **ADR-013.** | Found by Codex (F8); resolution supersedes both readings |
| **X10** | **Workflow ownership.** L8,952–8,986 and L16,694 say Temporal *owns* durable stage-gate state; master §36/§54 qualify it as "where justified / where used". MVP Phase 0 (L21,834) puts Temporal in slice 0 while the revised 45-h budget allocates it zero hours. | Named ownership: stability time points, escalation timers, long-running qualification and announcement acknowledgement are **Temporal-owned** from Slice 11. Everything else stays transactional DB workflow permanently. **Cutover is a migration, not an adapter swap** (F13/F41). | Source contradicts itself; explicit ownership resolves it |
| **X11** | **Critical RED vs confirmation RED.** Master §27: critical red "should open/link" a failure. Test narrative §9/§36: a red *confirmation* result triggers automatically; a confirmation failure "normally" creates one. | Configured by **purpose × authority × criticality × deviation class**. No single global RED rule (F11). | Both true at different scopes |
| **X12** | **Screening GREEN.** Test narrative §13 allows a reviewed screening pass to be GREEN; §9/§26/§59 and master §24 place "screening success requiring confirmation" under YELLOW. | Status is **authority-qualified**: `GREEN — Screening Passed (preliminary authority)`. A green screening result is never confirmation evidence (F10/F30). | Both true once authority is displayed |
| **X13** | **Improvement test outcomes.** Everything else is PASS/FAIL; Test narrative §29 requires Improved / No Significant Change / Worsened. | Outcome vocabulary is **separate from** traffic-light disposition (F29). | Explicit later statement |
| **X14** | **Test navigation.** Test narrative §1 defines a module-level nav (Dashboard, Queue, Plans, purpose queues, Samples, Results, Failed, Awaiting Review/Approval, Methods, Equipment, Analytics); master §14 defines an 11-item entity-context submenu. | **Both, at different levels** — module nav and entity submenu are different things (F9). | Not actually in conflict |
| **X15** | **App name.** Operator's request says "ITW Evercoat RD App"; source amendment L29,736–29,817 mandates `EvercoatITWRD APP` and forbids renaming. | `EvercoatITWRD APP`. **Flagged to operator** (§L). | "Strictly follow the prompt in the files" |

### D.2 Deliberate staged refinement — not contradictions

- Pipeline stages: 8 in MVP expanding to 18. Stages are **configuration rows**, not a code enum, so expansion needs no migration.
- MSD capability phases 1–6 (Concept Note §39) are an explicit roadmap.
- MVP dashboards vs full-build dashboards.

### D.3 Renames and relabels

- **MSD ≡ "R&D Copilot".** Same component; product name is **MSD**, module `msd`. Telemetry and migration aliases retain `copilot` in case earlier records use it (F7/C10).

### D.4 Ordinary architecture decisions — *not* reconciliation

Previously and wrongly listed as contradictions:
- **TanStack Table over AG Grid** — AG Grid was never a stated requirement; the source removes it because Enterprise is commercial. A zero-cost technology decision.
- **GitHub Actions over Forgejo Actions** — source explicitly permits GitHub as a convenience. CI logic lives in `scripts/*.sh` so the runner is swappable. Repository hosting policy to be confirmed with the operator.
- **16 logical schemas** — master §37 says "such as" and is non-exhaustive. A union is reasonable **but now requires ownership justification** (F23): each schema declares an owner role, grants and dependency direction, or it is merged.
- **Render as optional staging only** — the source itself says free Render Postgres expires in 30 days and cannot hold R&D IP.
- **LangGraph vs Google ADK** — governance conflict, **escalated** (§L, ADR-002).

---

## E. Architecture selected

### Stack

| Layer | Technology | Slice |
|---|---|---|
| Web | Next.js (App Router) + React + TypeScript | 1 |
| UI | Tailwind + shadcn/ui + Radix | 1 |
| Tables | TanStack Table + Virtual | 1 |
| Forms | React Hook Form + Zod | 1 |
| Server state | TanStack Query | 1 |
| Charts | Apache ECharts (one `<ChartWrapper>`) | 1 |
| API | FastAPI + Python 3.12 + Pydantic v2 | 1 |
| ORM / migrations | SQLAlchemy 2.x + Alembic | 1 |
| Database | PostgreSQL 16 + RLS | 1 |
| Identity | Keycloak | 1 |
| Cache | Valkey | 1 |
| **Observability (baseline)** | health checks, structured logs, metrics, error tracking, **restore smoke test** | **1** (moved from 20 — F43) |
| **Object storage** | **Garage behind `ObjectStoragePort`** | **1** (moved from 8 — S13; Slice 3 ships TDS/SDS/CoA and `SECURITY.md` §6 forbids files in DB rows, so Garage must be in the Slice 1 compose stack) |
| Scientific | NumPy, SciPy, Pandas, Polars, statsmodels | 3 |
| Workflow | DB state machine + worker → Temporal OSS (named workflows only) | 1 → 11 |
| Testing | Pytest, Hypothesis, Vitest, Playwright, axe-core, Locust, Bruno | 1 |
| Quality/security | Ruff, mypy, ESLint, Prettier, pre-commit, Trivy, Semgrep, Gitleaks, SOPS+age | 1 |
| Proxy / runtime | Caddy + Docker/Podman Compose | 1 |
| Email | `NotificationService` → In-App + SMTP (+ optional Resend) | 7 |
| **Local LLM** | **Ollama behind an AI Gateway** | **7** (moved from 8 — F42) |
| Vector / RAG | pgvector, Sentence Transformers, Docling, PyMuPDF | 8 |
| AI orchestration | **LangGraph OSS** behind `AgentOrchestrationPort` — settled, ADR-002; explicit exception to root §0.1 | 8 |
| DOE | pyDOE3, statsmodels | 12 |
| Optimization | SciPy Optimize, Optuna | 13 |
| ML | scikit-learn, SHAP, MLflow | 14 |
| Reports | Jinja2, WeasyPrint, python-docx, OpenPyXL | 20 |
| Full observability | OpenTelemetry, Prometheus, Grafana, Loki, Jaeger, Uptime Kuma | 20 |

> **One numbering scheme only.** "Slice N" in this column means the slice of the same number in §H (1–7) and §I (8–20). §G's module numbering is a *dependency graph*, not a schedule, and must never be read as slice numbers. v1's table carried a third, inconsistent scheme that would have led an engineer starting the Laboratory slice to provision pgvector, Ollama and LangGraph inside MVP-1 — exactly the inversion §G calls non-negotiable (S1).

**Forbidden:** OpenAI/Anthropic/Gemini/Azure OpenAI/Bedrock APIs, Pinecone, Firebase, Firestore, MongoDB Atlas, Auth0, Clerk, paid Okta, Supabase Cloud, AWS S3, Azure Blob, GCS, Datadog, New Relic, Splunk Cloud, AG Grid Enterprise, commercial workflow SaaS, commercial OCR.

### Repository layout

```
EvercoatITWRD APP/
├── CLAUDE.md CONTEXT.md MEMORY.md BRAIN.md SECURITY.md
├── REQUIREMENTS.md ARCHITECTURE.md IMPLEMENTATION_PLAN.md
├── DATA_MODEL.md DATABASE_RELATIONSHIPS.md WORKFLOWS.md
├── UI_UX.md NAVIGATION.md API_CONTRACTS.md AI_ARCHITECTURE.md
├── TESTING_STRATEGY.md DEPLOYMENT.md DECISIONS.md
├── ACCEPTANCE_CRITERIA.md CHANGELOG.md TODO.md
├── .claude/  apps/{web,api}  services/  workers/  packages/
├── infrastructure/  tests/  scripts/  docs/{architecture,workflows,database,security,testing,ui,adr}
```

### Shared component library — Slices 1–3, then composed

`StatusBadge` · `TechnicalDataGrid` · `EntityHeader` · `ContextSubmenu` · `ApprovalEngine` · `ApprovalTimeline` · `DiscussionPanel` · `AttachmentManager` · `TaskCard` · `NotificationService` · `AuditHook` · `KpiCard` · `ChartWrapper` · `HistoryTimeline` · `AiRecommendationCard` · `RequirementStatus` · `EntityLink` · `MeasurementInput`

**Diagnostic:** if Pilot, Validation, Stability, Quality or Qualification needs new approval, discussion, attachment, task, audit, notification or dashboard infrastructure, that is a **defect in Slices 1–3**, not new scope.

### Navigation

**Sidebar** (collapsible 220–260px / 64–72px, RBAC-filtered, actionable counts):

```
WORK              Dashboard · My Work · Messages · Notifications
DEVELOPMENT       Innovation · R&D Pipeline · Projects · Formulations ·
                  Laboratory · Testing · Failures · DOE & Optimization
RESOURCES         Materials · Suppliers · Knowledge Library
INDUSTRIALIZATION Validation · Stability · Pilot & Scale-Up · Quality · Products
INTELLIGENCE      Analytics · Product Models · Infographics · Reports
GOVERNANCE        Approvals · Administration
```

**Module-level navigation** and **entity-context submenus** are distinct layers (X14). Testing module nav: Dashboard | Queue | Plans | Screening | Oversight | Confirmation | Improvement | Samples | Results | Failed | Awaiting Review | Awaiting Approval | Approved | Methods | Equipment | Analytics.

Entity submenus — **Project** (20 items) · **Formula** (13) · **Test** (11) · **Failure** (10) · **Lab Batch** (9) · **Pilot** (12) · **Product** (12), exactly as master §14 / Expanded §42–46 specify. Failure deliberately places **Evidence before Root Cause**.

Plus: global top bar, clickable breadcrumbs, right context drawer, `Ctrl/Cmd+K` palette, unsaved-changes guard, workflow-aware post-action redirects.

### Test Module — rebuilt as a state machine after review

v1 derived display from three columns. Codex correctly showed that cannot express awaiting review, returned for correction, conditional approval, retest requested, or escalation (F25/F26). Rebuilt:

**Five independent axes** (state dictionary and transition table published in `DATA_MODEL.md`):

| Axis | Values |
|---|---|
| `execution_status` | not_started · in_progress · complete · abandoned |
| `validity_status` **(new — F24)** | valid · minor_deviation · **invalid** |
| `calculated_result` | pass · fail · inconclusive · improved · no_significant_change · worsened **(F29)** |
| `review_state` | awaiting_review · under_review · returned_for_correction · retest_requested · escalated · reviewed |
| `approval_state` | not_required · pending(level n) · conditionally_approved · approved · rejected |

`display_color` and `final_status` are **derived** from all five plus `test_purpose` and `authority_level`. Never stored as a user-editable field.

**Evaluation is strictly ordered — first match wins (S3).** v1 stated the matrix as unordered rows with overlapping `Any/Any` predicates, so a passing, fully-approved, no-deviation test with a low margin matched both the GREEN row and the YELLOW row. Two implementers — or the API and the UI — could legitimately derive different colours for the same record. `display_color` is purely derived, so this had to be an ordered algorithm, not a table:

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
13. purpose == screening and
    authority < confirmation_required_for_use       → GREEN  (SCREENING PASSED — preliminary)
14. otherwise                                       → GREEN  (<authority> CONFIRMED)
```

RED conditions are evaluated before every YELLOW; GREEN is reachable only when no predicate above it fires. Each YELLOW carries its reason string and next required action — a bare yellow is a defect.

**Configuration keys are named, not implied.** v1's "YELLOW/RED by policy" for expired calibration named no key and was therefore unimplementable (S3). Replaced by `test_method.calibration_breach_policy ∈ {invalidate, deviate}` — `invalidate` sets `validity_status = invalid` (rule 1, RED); `deviate` sets `minor_deviation` (rule 8, YELLOW). Same pattern for `method.cv_limit`, `requirement.warning_threshold` and `method.trend_rule`.

**GREEN is authority-qualified** (X12/F30): the UI renders `GREEN — Screening Passed (preliminary authority)`, never a bare green tick, so screening evidence can never be mistaken for confirmation evidence.

**Two fields, always displayed separately** (F31): `Automatic evaluation: PASS` and `Final disposition: YELLOW — Awaiting Lead approval`. Colour is never the sole indicator; every YELLOW states why and what is next.

**Approval templates are versioned and snapshotted** (F28). `SCREENING_SIMPLE` · `OVERSIGHT_STANDARD` · `VALIDATION_CONFIRMATION` · `QUALIFICATION_CONFIRMATION` · `RELEASE_CRITICAL`. At test release, an **immutable route instance** is copied onto the test — mandatory/optional stages, parallel groups, ordering, role and person constraints. Editing a template can never retroactively change what a live test required.

**Incompatible-duty rules** (F27/S12), configurable and server-enforced.

v1 said "the executing user may not supply *all* mandatory approvals". Both reviewers independently showed that is satisfiable by the executor approving **five of six** levels on `RELEASE_CRITICAL`, and on the two-step `SCREENING_SIMPLE` route it degenerates to "one other person must click once". A server check written to the letter would pass. Replaced with rules that name the excluded levels:

- **At `qualification` and `release` authority the executor may supply *no* approval at all.**
- At `validation` and `controlled` authority the executor may not supply the Level-1 technical review, nor the final approval.
- QA approval may never be supplied by anyone who supplied a development-side approval on the same test.
- Author ≠ final approver, on every route.
- `min_distinct_approvers` is a property of the route template, defaulting to the number of mandatory levels.
- No self-approval; delegation is explicit, time-boxed and audited; every incompatible-duty rejection writes a conflict-of-interest audit event.

**MVP test-capability table** (F2/F4) — mandated by master §23/§26/§46, therefore **Slice 5, not deferrable**: purpose × authority · method versioning with immutable snapshot onto the test · equipment + calibration check · sample integrity check · per-replicate raw capture · mean/min/max/range/variance/SD/CV/% change/pass margin · historical, formula, benchmark and batch comparison · trend analysis · warning thresholds · release-to-queue · technical review with permanent comments and conditions · recommendation records with outcome tracking · correction-by-revision (never in-place edit) · retest with reason and `parent_test_result_id`. Deferred to Slice 9 as genuinely advanced: confidence intervals, ANOVA, control limits, outlier detection, dynamic entry schemas, test analytics dashboards.

### MSD — in MVP-1 (X9, F1/F8/F42)

Architectural principle (Concept Note §37): `MSD conversation → Permission check → Context identification → knowledge retrieval → deterministic tools/models → evidence assembly → response → optional human-approved action`.

**Slice 7 (MVP-1)** — local Ollama runtime + structured tool-calls over the digital thread, satisfying Concept Note §38: application guidance · formula retrieval · formula comparison · material lookup · test-result explanation · failure-history retrieval · pending-work queries · context-aware navigation. Every answer carries evidence links.

**Slice 8** — document RAG: Docling/PyMuPDF ingestion, Sentence Transformers, pgvector hybrid retrieval. This completes "R&D knowledge search".

**Authorization is the hard part** (F33). MSD operates under exactly the caller's boundary. **Filter before retrieval, never after generation.** Authorization provenance is carried through every chunk, embedding, cache entry, conversation memory, tool output and model dataset; permissions are re-checked at retrieval *and* at source-open; derived artifacts are purged when access is revoked. `tests/e2e/rbac/msd_boundary.spec.ts` is a required test, not an aspiration.

**Ceiling:** MSD may analyze, compare, retrieve, summarize and recommend. It may not approve a test, change a controlled formula, move YELLOW→GREEN, confirm a root cause, or release a product.

---

## F. Database architecture

PostgreSQL 16, 16 logical schemas — **each declaring an owner role, grants and dependency direction, or being merged** (F23):
`core` `projects` `innovation` `materials` `formulations` `laboratory` `testing` `workflow` `quality` `products` `knowledge` `messaging` `analytics` `modeling` `ai` `audit`

### Tenant integrity — relational, not just RLS (F14)

RLS prevents cross-tenant *reads*. It does **not** prevent cross-tenant *references*, because referential integrity bypasses RLS even under FORCE.

**Every tenant-scoped table carries a composite candidate key `(id, organization_id)`, and every child→parent FK is composite**, so a cross-organization reference is not creatable. This applies across the entire thread: project→formula, formula→version, version→component, version→batch, batch→sample, sample→result, result→failure, and onward.

**This imposes a constraint that must be written into the very first migration** (S7). PostgreSQL requires a unique index on the *referenced* columns, so a composite FK is impossible unless every parent table also declares:

```sql
ALTER TABLE <parent> ADD CONSTRAINT <parent>_id_org_key UNIQUE (id, organization_id);
```

Without it the first migration that follows this rule fails with *"there is no unique constraint matching given keys for referenced table"* — and the predictable reaction under time pressure is to drop the composite FK, which is precisely the defect the rule exists to prevent. `UNIQUE (id, organization_id)` is therefore a **mandatory column of the table-creation checklist**, not an optimisation, and Slice 1 ships a migration test that fails if any tenant-scoped table lacks it.

Where a composite key is genuinely impractical, a constraint trigger asserts tenant equality — and the exception is recorded in `DECISIONS.md`.

### Measurement model (F16)

"NUMERIC not float" is necessary but not sufficient. Every measured value stores: `value` (NUMERIC) · `canonical_unit` · `entered_unit` · `decimal_precision` · `significant_figures` · `uncertainty` · `qualifier` (`=`, `<`, `>`, `ND`) · `instrument_resolution` · `test_method_version_id` · `conversion_provenance`. Canonical units: adhesion MPa, density g/cm³, time minutes, temperature °C.

### Integrity rules

- **NUMERIC, never float**, for percentages, masses, densities, measured values.
- **`RESTRICT`/`NO ACTION`** on projects↔formulas, versions↔batches, batches↔tests, materials-in-formulas, released products. Never cascade-delete R&D history. Retire via `inactive`/`obsolete`/`archived`.
- **Composite `ON DELETE SET NULL` is banned** — it nulls every key column including NOT NULL tenant keys. Name the column (PG15+).
- **RESTRICT is not enough on its own** (F17): add transition constraints and **immutable link snapshots** on approved formula components, method versions, acceptance criteria, samples, qualifications and releases. Preventing deletion does not prevent illegal transitions or mutation of historical links.
- **Unique constraints, all tenant-scoped** (F15): `(organization_id, project_code)` · `(formula_id, version_number)` · `(organization_id, raw_material_code)` · `(organization_id, product_code)` · **`(organization_id, lab_batch_number)`** · **`(organization_id, sample_number)`** · `(document_id, revision_number)`.
- **Indexes** on every join FK, plus `(organization_id, status)`, `(project_id, current_stage)`, `(formula_version_id, test_date)`, `(raw_material_id, supplier_id)`.
- **Audit is database-enforced** (F22), not merely an application hook: append-only triggers or event procedures, `UPDATE`/`DELETE` revoked from runtime roles, before/after state, actor and session recorded, tamper evidence, protected backup retention. An application hook alone is bypassable by SQL, scripts, failed code paths and compromised service credentials.

### Release traceability — a transactional command, not a constraint (F18)

*No released product without a qualified formula; no qualified formula without validation and pilot evidence; no validated formula without lab batches and tests; no test result without traceability to the physical sample.*

This spans many tables and time, so it cannot be declarative. Release is a **single transactional command** that locks the relevant rows, evaluates an **immutable evidence snapshot**, records the qualification dossier version, freezes the full release snapshot (components, quantities, units, material revisions, calculations, specifications, procedures, documents, approvals — F35), and creates the released product atomically. Partial release is impossible by construction.

### Controlled numbering (F21)

Not "gap-tolerant sequences". A **numbering-policy table** + atomic allocator + uniqueness on `(organization_id, type, year)` + an **immutable issued-number ledger**, with document identity separate from revision identity, and defined behaviour for year rollover, cancellation, revision and correction.
Formats: `RDP-2026-001` · `RDP-2026-001-F001` · `-LB001` · `-T001` · `-FA001` · `-DOE001` · `-P001` · `-Q001` · `PRD-2026-001`.

### Database roles (F19)

v1 wrongly required migrations to run as the runtime role — that needs DDL privileges it must not have. Five roles:

| Role | Purpose |
|---|---|
| `evercoat_owner` | schema owner; DDL and migrations only |
| `evercoat_app` | runtime; **non-superuser, subject to FORCE RLS** |
| `evercoat_worker` | scheduler/analytics refresh; narrow grants |
| `evercoat_report` | read-only analytics; RLS-subject |
| `evercoat_breakglass` | audited emergency access, off by default |

Runtime tests exercise FORCE RLS under `SET ROLE evercoat_app`. Migration **data backfills and orphan checks** are still validated against RLS semantics — that is the real hazard the v1 rule was groping at.

### Analytics (F20)

Views and materialized views under `analytics.*`. **Materialized views do not inherit source-table RLS** — so each materializes `organization_id` and the resource-scope dimensions, carries its own RLS policy, refreshes under `evercoat_worker`, and has an explicit cross-tenant aggregate test. The reporting role has no unrestricted access.

Views: `project_health` `project_pipeline` `pipeline_duration` `formula_performance` `test_status` `test_performance` `failure_summary` `approval_summary` `team_workload` `material_dependency` `pilot_comparison` `model_performance` `product_quality` `portfolio_summary` `ai_effectiveness`.

Dashboards never issue unbounded queries against transactional tables.

---

## G. Module dependency order

```
0 Foundation ── 1 Identity/RBAC/Audit/Observability ── 2 App Shell
       │
       ├── 3 Projects · Pipeline · Requirements · My Work
       │        ├── 4 Materials · Suppliers · Lots · Documents
       │        │        └── 5 Formulations (versions, calc, compare)
       │        │                 └── 6 Laboratory (batches, lots, samples)
       │        │                          └── 7 Testing → 8 Approvals → 9 Failures/Reformulation
       │        └── 10 Messaging · Notifications · MSD (structured)
       └── 11 Dashboards · Analytics
12 Knowledge/RAG ── 13 DOE ── 14 Optimization ── 15 Product Modeling
16 Validation ── 17 Stability ── 18 Pilot/Scale-Up ── 19 Manufacturing
20 Quality ── 21 Qualification ── 22 Release ── 23 Lifecycle/CAPA ── 24 Advanced Analytics
```

**Sequencing rationale (source §95, L3,385):** the intelligence layer is built *on* reliable structured data. AI is never the foundation. Proposals to pull DOE, modeling or document-RAG earlier are rejected.

---

## H. MVP-1 sequence

**Gate:** MVP-1 is complete when the golden scenario passes **on the deployed instance**, with the full suite reporting passed / failed / skipped as three numbers.

**Slice 1 — Foundation, Identity, Administration, Shell, Observability.** Compose stack — web, api, postgres, keycloak, valkey, **garage**, caddy (S13: Slice 3 ships TDS/SDS/CoA and files may not live in DB rows, so object storage cannot wait) · Alembic baseline · five DB roles · **RLS from the first migration for both organization and project membership** · composite tenant keys + the `UNIQUE (id, organization_id)` migration test · Keycloak realm, 10 roles, permission model · audit triggers · **Administration §1 — users, roles, permissions, org settings (see below)** · sidebar/top bar/submenu/breadcrumbs · four role dashboard shells at final architecture · shared component library v1 · **health checks, structured logs, metrics, error tracking, backup + restore smoke test** · CI (ruff, mypy, eslint, vitest, pytest, gitleaks, trivy, semgrep) · **measure container memory headroom** before Slice 7 adds model weights.

### Administration is a thread through the build, not a slice (S8)

The Supervisor found that v1 and v2 both said role→permission mapping was "editable in Administration", that test methods were "editable in Administration", that pipeline stages were "configuration rows", and shipped an Administration sidebar entry — while **no slice ever built it.** That is this project's own most-repeated lesson turned on itself: *ask of every role, which production path **writes** it?* Seeding a Keycloak realm is not a write path. An administrator who can be read but never granted does not exist, and every "editable in Administration" escape hatch resolved to a screen nobody was scheduled to create.

Administration is therefore delivered incrementally, alongside whatever first depends on it:

| Section | Slice | Because |
|---|---|---|
| Users · Roles · Permissions · Organization settings | **1** | Nothing can be granted without it |
| Stage-gate definitions · pipeline configuration | **2** | Stages are config rows from Slice 2 |
| Units · product families · material statuses | **3** | Formulation needs canonical units |
| **Test methods · method versions · approval templates · equipment + calibration · warning-threshold policy** | **5** | The Test Module is meaningless without configurable methods and routes |
| Notification templates · escalation rules | **7** | Notification service ships here |
| AI configuration · model governance states | **8** | — |
| Audit browser · system settings · feature flags | **20** | — |

Each section is a real screen with a real write path, permission-gated on `admin.*`, and audited. **A configuration value referenced anywhere in this plan must have an Administration screen in the same slice or earlier**, and the slice gate checks that.

**Slice 2 — Projects, Pipeline, Requirements, My Work.** Opportunities → projects · members · milestones · risks · 8 seeded stages as config rows · **stage history preserved** · structured requirements (target/min/max/unit/criticality/verification) · Requirements Verification Matrix · tasks + My Work · project dashboard · context bar.

**Slice 3 — Materials, Suppliers, Formulations.** Material library, 5 statuses, properties, TDS/SDS/CoA, lots, suppliers M:M, usage + performance history · formula workspace · NUMERIC components · deterministic calculation engine (total %, batch scaling, theoretical density, binder/filler, resin/hardener, equivalents, solids, VOC, cost) · **hard submission validation** · versioning with branches · difference engine (old/new/Δ/%Δ/reason/expected/observed) · approval + lock.

**Slice 4 — Laboratory.** Guided batch flow: Material Verification → Lot Selection → Weighing → Charging → Mixing → Process Capture → Sampling → Deviations → Completion · planned vs actual with tolerance flagging · process parameters · samples with full traceability · batch review.

**Slice 5 — Testing, maximum depth.** Per the MVP test-capability table in §E. Non-deferrable.

**Slice 6 — Approvals, Failures, Reformulation.** Versioned approval engine with route snapshotting · sequential + parallel · 7 decision types · incompatible-duty rules · configurable RED→failure rules · evidence/hypotheses/root cause with `proposed|under_review|accepted|rejected` · **hypothesis ≠ root cause, enforced** · corrective actions · failure→revision link · retest lineage.

**Slice 7 — Messaging, Notifications, MSD, Dashboards, MVP release.** Project channels · DMs · technical threads · mentions · `#F008` smart linking · embedded cards · message→task/decision/failure/experiment/approval · NotificationService · **MSD over structured tool-calls with evidence links and enforced authorization boundary** · four completed role dashboards with drill-down · **golden Playwright E2E** · RBAC E2E incl. MSD boundary · deploy · **full live suite on the deployed site**.

### Golden scenario (MVP-1 acceptance, master §44)

Director creates/approves project → Lead assigns team → Chemist creates formula → Lead approves lab → Lab creates batch + sample → Engineer creates confirmation test → raw results entered → app analyzes → **RED** → failure investigation opens → Chemist creates revised formula → new batch → retest passes technically → **YELLOW pending approvals** → Engineer/Chemist/Lead approve → **GREEN** → validation candidate → dashboards update.

Every arrow asserted in UI **and** database state. The YELLOW→GREEN transition is the single most important assertion in the suite.

---

## I. Full build (Slices 8–20)

| Slice | Deliverable |
|---|---|
| 8 | Knowledge Library · Docling/PyMuPDF · Garage · Sentence Transformers · pgvector hybrid retrieval · MSD knowledge search · **LangGraph/ADK decision must be made before this slice** |
| 9 | Advanced test — confidence intervals, ANOVA, control limits, outliers, dynamic entry schemas, test analytics |
| 10 | Failure intelligence — cause trees, multi-hypothesis, AI failure analysis, recommendation effectiveness |
| 11 | **Temporal OSS** for the named durable workflows only (X10); treated as a migration |
| 12 | DOE — pyDOE3, runs↔formula/batch, statsmodels effects/interactions/significance, response surfaces, contour plots |
| 13 | Optimization — SciPy + Optuna, multi-objective, Pareto candidates |
| 14 | Product Modeling — datasets, scikit-learn, cross-validation, MLflow, SHAP, actual-vs-predicted, drift, model governance states, Predicted Performance panel visually separated from measured |
| 15 | Validation + Stability |
| 16 | Pilot + Scale-Up — **non-linear scale-up**; RPM/tip speed/shear/vacuum/addition rate never assumed linear |
| 17 | Manufacturing Process + Quality — 13 controlled steps, QC specs, incoming/in-process/finished/retention |
| 18 | Qualification + Release — dossier aggregation, 5-level route, transactional release command, master formula lock |
| 19 | Product Lifecycle — production results, complaints, field issues, CAPA, change control, improvement projects |
| 20 | **The 13 named reports** (F6), advanced analytics, infographics, full observability, hardening, performance, restore drill, full regression |

**The 13 controlled reports** (master §41), each named with its source records and approval state: Product Development Status · Formula Development History · Formula Comparison · Lab Batch · Test · Failure Investigation · DOE · Validation · Stability · Pilot · Qualification Dossier · Product Release · Portfolio.

**Dashboards** (F5): MVP delivers Chemist, Engineer, Lead, Director, Project, Test, Failure. Full build adds **Laboratory** and **QA/Compliance** (Concept Note §30) plus DOE, Product Modeling, Validation, Stability, Pilot, Quality — the 13 named in master §15.

---

## J. Security decisions

Full detail in `SECURITY.md`. What changed after review:

**The three-layer claim is corrected.** v1 asserted that Keycloak + FastAPI + org-RLS gave three layers where "any one failing must not expose data". **That was false** (F32): RLS scoped only to `organization_id`, so project-level confidentiality rested on application code alone. One missing dependency on one route would expose a colleague's formulations.

**Fix:** RLS enforces **both** organization isolation **and** project membership, via policies over a membership predicate plus `security_barrier` views for the analytics surface. Formula confidentiality classification is likewise database-enforced. Only then is the claim true.

Also adopted:

1. **Composite tenant keys and FKs** so cross-tenant references are not creatable (F14).
2. **Connection-pool tenant context** (F34): transaction-scoped `SET LOCAL`, pooled connections reset, **fail closed when context is absent**, user-controlled session variables forbidden, cross-request tenant switching tested. This is the classic way RLS silently fails.
3. **Five database roles** (F19) — owner/migrator, runtime, worker, reporting, break-glass.
4. **Materialized-view tenancy** (F20) — matviews carry their own `organization_id` and policies.
5. **MSD authorization provenance** (F33) across chunks, embeddings, caches, conversation memory, tool outputs and model datasets; purge on revocation.
6. **Release snapshot immutability** (F35) — freezing the row is not enough if components, material revisions or documents remain mutable.
7. **Domain commands + DB constraints** for server-controlled fields (F36) — DTO separation alone does not protect internal calls, bulk imports, workers or direct SQL.
8. **Document access** (F38) — very short expiry, audience/object binding, download audit, revocation strategy, and an authorization-checking download proxy for formulations. A signed URL outlives revocation.
9. **SSRF control on document ingestion** (F37 residue) — Docling/PyMuPDF fetches are restricted to an allow-list; no internal network reachability.
10. **Database-enforced append-only audit** (F22).

---

## K. Risks, and the schedule stated honestly

### Risk 1 — Authorization and tenancy model · **highest risk in the project**

Codex's Q3 answer, adopted. If organization-level RLS with application-only resource scope were kept, then by Slice 12 the wrong assumption would be embedded across DOE, RAG, modeling, reporting, workflow history, caches, search indexes and model datasets — simultaneously the most expensive rewrite and the most serious IP-exposure risk. **This is why F32 and F14 are fixed before Slice 1 rather than after.**

### Risk 2 — Schedule. Both numbers, stated plainly.

**What the source mandates** (master §45, L29,449; amendment L29,853): MVP-1 in **3 days / 45 hours**; full build in **14 days / 210 hours**, at "maximum depth", across ~25 modules including Keycloak, RLS, a deterministic calculation engine, the Test Module at maximum depth, a configurable approval engine, DOE, ML modeling with MLflow and SHAP, Temporal, RAG, and a full Playwright suite.

**Independent estimate for a hardened MVP-1 (Codex, verified as reasonable): 700–1,050 engineering hours.**

| Area | Hours |
|---|---:|
| Foundation, security, shell | 100–150 |
| Projects, requirements, work queues | 70–100 |
| Materials, formulation, calculations | 120–180 |
| Laboratory, traceability | 80–120 |
| Test module | 150–220 |
| Approvals, failures, retest | 90–130 |
| Messaging, dashboards, MSD, deploy, E2E | 90–150 |

≈5–8 calendar weeks for four experienced engineers; ≈18–26 working weeks solo. **The gap against 45 hours is roughly 15–23×.**

v1 tried to resolve this by silently redefining "Day N" as "Slice N". Codex correctly called that a fidelity change rather than a resolution (F39), and the plan no longer does it. **Both numbers now stand side by side and the operator decides.** The realistic readings are: (a) 45 hours yields a **demonstrator** with major depth omitted, (b) the full depth needs the larger budget, or (c) scope is explicitly cut using the source's own defer order (§5, L23,803): Infographics → Advanced Analytics → Product Modeling → Optimization → DOE → Stability → Lifecycle. **The MVP-1 core is never deferred.**

Slices retain the source's numbering and ordering. What a slice cannot do is be declared complete on a green build.

### Risk 3 — A green build is not a working feature
Type-checks, unit tests and successful deploys have coexisted with products that never worked. Every slice gate requires the feature exercised in a browser on the deployed instance, and the full suite run against the deployed site reporting **passed / failed / skipped as three numbers** — never an exit code. Free-tier cold starts take ~2 minutes; a short timeout is not proof of an outage.

### Risk 4 — Docker memory on Windows
Keycloak + Postgres + Valkey + Garage + later Ollama is heavy. Slice 1 **measures** actual headroom; the Ollama model is chosen from that measurement, not assumed.

### Risk 5 — No real domain data, and synthetic data cannot validate science
Seed data is synthetic and labelled, modelled on the source's own worked example (RDP-2026-014, F001→F008, RM-014 talc, adhesion ≥6.0 MPa). No undocumented ITW procedure will be represented as an official requirement (master §10). **The calculation engine requires subject-matter review by a formulation chemist before production trust** — Hypothesis tests prove internal consistency, not scientific correctness.

### Risk 6 — Agent framework leak
The `AgentOrchestrationPort` does not make LangGraph↔ADK free. Codex named ten leak paths. Mitigations adopted regardless of the answer: framework-neutral domain tools, application-owned conversation/event model, normalized streamed events, externalized checkpoints, contract tests against both adapters. **Decide before Slice 8.**

### Missing information — assumptions stated, build proceeds

| # | Unknown | Assumption |
|---|---|---|
| M1 | Deployment target | Docker Compose local + optional Render demo. Real R&D data never on Render free Postgres |
| M2 | Git remote | Local git initialised (`116cc64`); no remote until the operator names one |
| M3 | Real users / org | Seed org "ITW Evercoat (Demo)" + 10 synthetic users |
| M4 | SMTP credentials | Dev-mail adapter; SMTP at deploy; Resend optional |
| M5 | Multi-tenant? | Built multi-tenant — cheap now, very expensive to retrofit |
| M6 | Real test methods (ASTM/ISO) | Methods are data; generic definitions seeded, editable in Administration |
| M7 | Warning-threshold policy | Configurable per requirement; seeded at +5% of the acceptance limit |
| M8 | Repository hosting policy | GitHub Actions assumed; CI logic in `scripts/*.sh` so the runner is swappable |

---

## L. Operator decisions — both settled 2026-08-16

**1. AI framework — LangGraph OSS.** Chosen by the operator after being shown the governance conflict and Codex's contrary recommendation. This is an **explicit, operator-granted exception to root `CLAUDE.md` §0.1**, which declares Google ADK the only permitted agent framework platform-wide. Recorded loudly in ADR-002 rather than followed silently, because the root file itself treats a silent contradiction as a defect.

Codex's finding that the port abstraction leaks stands and is acted on: domain tools are framework-neutral plain Python with Pydantic signatures, the conversation/event model and checkpoints are ours rather than LangGraph's, streamed events are normalized to our own shape, and contract tests run against the tool layer with no orchestrator. The leak is therefore bounded to `app/agents/graphs/`.

§0.2 (orchestration-first — Root Orchestrator, department Conductors, specialists never call agents, routes never call specialists) and §0.3 (reusability) are **retained in full** — they are framework-independent. Only §0.1 is waived.

**2. Schedule — full depth, gate by gate.** Every slice built to the Definition of Done, in dependency order. Nothing cut; the source's defer order is not used. A slice ships when its gate passes, not when a day ends. The 45-hour and 14-day figures remain recorded as source requirements, not as commitments — reporting against them would be dishonest in both directions. See ADR-024.

**3. App name** — `EvercoatITWRD APP` per the source's explicit mandate, not "ITW Evercoat RD App" as phrased in the request. Reversing changes branding strings only. Non-blocking; flagged, not escalated.

---

## M. Definition of Done

Not complete because CRUD works. Required where applicable: database schema · relationships · migrations · indexes · constraints · Pydantic schemas · domain service · validation · business rules · REST API · RBAC + resource scope · list/queue view · detail workspace · contextual submenu · status header · empty/loading/error states · workflow status · approval · tasks/notifications · discussion link · audit · dashboard KPI · analytics · Pytest · Hypothesis for scientific code · Playwright for critical flows · accessibility · documentation · `CONTEXT.md`/`MEMORY.md`/`BRAIN.md`/`CHANGELOG.md`/`TODO.md` updated.

**Plus a requirements→acceptance traceability matrix** (Codex Q2), so every mandated requirement maps to a test that proves it.

**Then four gates:** Codex CLI → Supervisor → Work Reviewer Agent → Work Scheduler Agent.
**And the live-test rule:** after every deploy, the full suite runs against the **deployed** site and reports passed / failed / skipped.
