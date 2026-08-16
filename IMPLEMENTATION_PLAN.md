# IMPLEMENTATION_PLAN.md — EvercoatITWRD APP

**Product display name:** EvercoatITWRD APP
**Internal package slug:** `evercoat-itw-rd`
**Database application identifier:** `evercoat_itw_rd`
**Docker project name:** `evercoat-itw-rd`
**Workspace:** `C:\Users\USER\Documents\evercoat-itw-rd-workspace\`
**Reference (read-only):** `<workspace>\ITERDRD App\` — copies of `EvercoatRD App1.txt` (34 KB) + `ITWRD App.txt` (537 KB, 29,862 lines). Canonical originals remain untouched at `C:\Users\USER\Documents\evercoatRD App\`.

Status: **DRAFT v1 — pre-review.** Pass 1 of the mandated review chain (Claude drafts → Codex reviews → Supervisor adjudicates → Claude revises → build).

---

## A. What was found in the reference folder

The reference folder contains **no source code, no schemas, no migrations, no UI components, no configuration, and no prior implementation plan.** It contains exactly two plain-text documents.

This is the single most consequential finding, because the master prompt (§3, §9) is written on the assumption that a reference *application* exists and instructs Claude to "reuse only components that meet the new architecture" and to treat the folder as a "reusable code source where technically sound."

**There is nothing to reuse. This build is greenfield.** Every instruction about salvaging, migrating, or not-inheriting poor architecture is void. That removes a risk (no legacy debt) and removes an accelerator (no head start). The 3-day MVP estimate in the source was written without this being explicit; see §K.

The two documents are:

| File | Lines | Content |
|---|---:|---|
| `EvercoatRD App1.txt` | 944 | Updated Concept Note. 41 sections. Introduces **MSD — Material Science & Development Assistant**, the conversational R&D assistant. |
| `ITWRD App.txt` | 29,862 | Ten concatenated iterative specification passes, ~96 + 48 + 70 + 52 + 71 + 73 + 73 + 60 + 70 + 55 numbered sections, ending in the **MASTER CLAUDE CODE PROMPT** (line 27,909) and its two amendments (line 29,736 onward). |

The ten passes inside `ITWRD App.txt`, in file order:

1. L1–3491 — Consolidated System Implementation Blueprint (96 §). Modules A–X, DB core tables, 11 implementation phases, MVP, sprints.
2. L3494–5157 — Zero-Cost Open-Source Technology Stack (48 §). The mandatory technology rule.
3. L5161–7141 — Dashboard, Analytics and Infographics (70 §).
4. L7144–8927 — End-to-End Application Workflow (52 §).
5. L8932–10137 — Stack narrative + Render/Resend/Playwright expansion (50 §).
6. L10139–11538 — Consolidated Application and Implementation Plan (71 §).
7. L11540–12945 — Frontend/Backend/Database/Schemas/UI narrative.
8. L12947–15009 — Database Relationships (78 §), incl. cardinalities, FK delete rules, unique constraints, indexing.
9. L15014–16699 — Navigation narrative (73 §).
10. L16706–18440 — Test Module narrative (60 §) — the most technically load-bearing single section.
11. L18447–21335 — Messaging module (70 §) — **present twice, verbatim** (L18455–19884 and L19887–21335).
12. L21336–22655 — MVP dashboards + MVP Phases 0–12.
13. L22662–26310 — Two-week compressed schedule, then a *revised* aggressive re-estimate of the same schedule.
14. L26315–27901 — Expanded Requirements for the Evercoat R&D Web Application (55 §).
15. L27907–29862 — **MASTER CLAUDE CODE PROMPT** (55 §) + amendment fixing the app name to *EvercoatITWRD APP* + amendment rewriting the opening and START NOW sections.

**Interpretation rule applied throughout (master prompt §2):** repetition is iterative refinement, not duplicate functionality. Later + more explicit supersedes earlier + vaguer. The MASTER PROMPT (last in file) is the highest authority, then the Expanded Requirements, then the topic narratives, then the original Blueprint.

---

## B. Main consolidated product requirements

EvercoatITWRD APP is an industrial R&D product-development platform for formulated chemical products — polyester body fillers, automotive putties, epoxy putties, repair compounds, adhesives, structural adhesives, sealants, seam sealers, coatings, primers, UV-curing products.

It is **not** an electronic lab notebook, a formula repository, or a project tracker. It is a controlled digital operating environment whose defining asset is the **digital thread**:

```
Opportunity → Project → Requirement → Research → Benchmark → Raw Material
  → Formula → Formula Version → Lab Batch → Material Lot → Sample
  → Test → Raw Measurements → Analysis → Approval
  → Failure/Improvement → Corrective Action → New Formula Version
  → Validation → Stability → Pilot → Scale-Up → Qualification
  → Released Product → Production/Field Performance → Complaint/CAPA
  → Improvement Project
```

**No major technical record may become an isolated data island.** Every module must attach to this chain, in the database and in the navigation.

### The seven non-negotiable rules

These recur across every pass of the source and are the acceptance spine of the whole build:

1. **PostgreSQL owns verified technical facts.** AI is never the system of record.
2. **Python owns deterministic scientific calculation.** The LLM may call calculation tools and explain results; it must never perform the arithmetic.
3. **Physical testing verifies; models only predict.** Predictions must never render as confirmed test results.
4. **Humans approve.** AI cannot approve a test, change a controlled formula, confirm a root cause, or release a product.
5. **Released formulations are immutable.** No silent modification after release; changes go through Product Change Control into a new version.
6. **Green / Red / Yellow is a derived state, not a user-selected label** — and **a technically passing test stays YELLOW while mandatory approvals are incomplete.**
7. **Zero-cost open-source core.** No essential paid SaaS, paid AI API, paid DB, paid auth, paid vector store, paid object storage, paid workflow engine, or paid monitoring. Render and Resend are optional *adapters*, never architectural dependencies.

### Canonical role set (reconciled)

The source names roles in three inconsistent lists. Reconciled to ten Keycloak realm roles:

| Keycloak role | Source |
|---|---|
| `product_development_chemist` | 4 principal roles, all passes |
| `product_development_engineer` | 4 principal roles, all passes |
| `product_development_lead` | 4 principal roles, all passes |
| `product_development_director` | 4 principal roles, all passes |
| `qa_compliance_officer` | Master §12 "Compliance/QA Officer"; earlier `qa_manager` + `regulatory_officer` merged |
| `laboratory_technician` | Master §12, blueprint §5 |
| `procurement_specialist` | Master §12 "Procurement/Material Specialist"; earlier `procurement_officer` |
| `production_engineer` | Blueprint §5 (retained — owns scale-up/manufacturing execution) |
| `executive_viewer` | Blueprint §5 (read-only portfolio) |
| `administrator` | Master §12, all passes |

Roles are coarse. **Authorization is by permission, not by role name** — `project.create`, `formula.submit`, `formula.approve_lab`, `test.execute`, `test.review`, `test.confirm`, `failure.close`, `product.release`, etc. (master prompt §2 of MVP-1 max-depth, L24176–24201). Roles map to permission sets in the DB, editable in Administration.

**Authorization chain (enforced in this order, every request):**
`Authentication → Organization → Role → Permission → Resource Scope → Business Rule`
plus PostgreSQL **Row Level Security** on `organization_id` as an independent database-layer backstop.

---

## C. Repeated requirements normalized

| # | Repetition | Normalization |
|---|---|---|
| R1 | Messaging module appears **verbatim twice** (L18455–19884, L19887–21335) | One messaging module. Second copy ignored. |
| R2 | The sidebar is specified **six times** (L6984, L7266, L15087, L16523, L28404, L27543) | One canonical sidebar — see §E. |
| R3 | The zero-cost stack is listed **five times** with growing detail | One stack table — see §E. |
| R4 | Role dashboards specified **four times** each | One dashboard spec per role; MVP subset + full-build additions. |
| R5 | The 14-day schedule appears **twice**, second an aggressive re-estimate of the first | Second supersedes; both re-based — see §K. |
| R6 | Digital thread restated **nine times** with minor wording drift | One canonical thread (§B). |
| R7 | Green/Red/Yellow defined **five times** | One decision matrix — see §E, Test Module. |
| R8 | Approval routes listed **four times** (Screening/Oversight/Validation/Qualification/Release-Critical) | Five configurable approval **templates**, one engine. |
| R9 | Formula genealogy example `F001→F002→F003→F004-A/F004-B` restated **five times** | One self-referential `parent_version_id` model supporting branches. |
| R10 | Reusable components listed **three times** (L11642, L26263, L29377) | One shared-component library, built in Slice 1–3 — see §E. |
| R11 | Test tables specified twice: a flat `test_results` (L2223–2226) vs. a 13-table decomposition (L18128–18141) | Decomposition wins (explicitly says "preferable to forcing everything into a single test-results table"). |

---

## D. Contradictions found and how they were resolved

This is the requirements reconciliation register mandated by master prompt §2. It also lives in `DECISIONS.md` as ADRs.

| # | Contradiction | Resolution | Rule applied |
|---|---|---|---|
| **C1** | **App name.** User's message says "ITW Evercoat RD App". Source amendment (L29,736–29,817) mandates **`EvercoatITWRD APP`**, says "Do not rename the visible product to ITERDRD or another generic R&D name", and fixes the folder name. | **`EvercoatITWRD APP`** as display + folder name; slug `evercoat-itw-rd`. **Flagged to the operator** — one word from them reverses it, and only branding strings change. | User instruction "strictly follow the prompt in the files"; later explicit correction supersedes. |
| **C2** | **Charts.** Blueprint §2 (L132): "Recharts or Plotly". Stack §6, dashboard §2, master §15: **Apache ECharts**. | **Apache ECharts**, single `<ChartWrapper>` component. Matplotlib/Plotly only for server-side static scientific plots in PDF reports. | Later + explicit ("Use Apache ECharts"). |
| **C3** | **Object storage.** Blueprint §6 (L240): **MinIO**. Stack §19, master §36: **Garage**. | **Garage**, behind an S3-compatible `ObjectStoragePort`. MinIO becomes a drop-in swap. | Later + explicit; port preserves both. |
| **C4** | **Data grid.** AG Grid implied by "technical tables"; §5 explicitly *removes* it because Enterprise is commercial. | **TanStack Table + TanStack Virtual**. AG Grid forbidden. | Zero-cost rule is mandatory and supersedes convenience. |
| **C5** | **Repository layout.** Blueprint §9: `frontend/ backend/ database/ infrastructure/ docs/`. Master amendment (L29,769–29,797): `apps/ services/ workers/ packages/ infrastructure/ tests/ docs/`. | **Master amendment layout.** See §E. | Last statement in file; explicitly mandated as "must contain". |
| **C6** | **Test result model.** Blueprint §29 (L1113): single `pass_fail` field. Test narrative §49 (L18150–18170): `calculated_status` / `technical_status` / `final_status` / `display_color`, plus `review_status`. | **Four-state decomposition.** `pass_fail` is superseded and must not be implemented — it structurally cannot express YELLOW. | Later, far more detailed, and safety/integrity-critical. |
| **C7** | **Sidebar WORK group.** Navigation §66 (L16528): Dashboard, My Work, Notifications. Master §13 + Expanded §41: Dashboard, My Work, **Messages**, Notifications. | **Include Messages.** | Later + appears in two independent later passes. |
| **C8** | **Sidebar INTELLIGENCE group.** Navigation §66: Analytics, Infographics, Reports. Master §13 + Expanded §41: Analytics, **Product Models**, Infographics, Reports. | **Include Product Models.** | Same as C7. |
| **C9** | **Formula top submenu.** Navigation §68: 11 items. Master §14 + Expanded §43: 13 items, adding **Predicted Performance** and **Discussion**. | **13 items.** | Later + explicit. |
| **C10** | **MSD vs. R&D Copilot.** `EvercoatRD App1.txt` names the assistant **MSD — Material Science & Development Assistant** with a defined UI header and 6-phase capability roadmap. `ITWRD App.txt` calls the same thing "R&D Copilot" throughout. | **Same component. Product name: MSD.** Internal module: `msd`. UI header exactly as specified: `MSD — Material Science & Development Assistant / Current Context: Formula F023 / Project P014`. "R&D Copilot" retired as a synonym. | The Concept Note is titled "UPDATED CONCEPT NOTE" and names the feature; a named product beats a generic label. |
| **C11** | **AI framework vs. house rule.** Source mandates **LangGraph OSS** (5×, incl. master §36). Root `C:\Users\USER\CLAUDE.md` §0.1 declares **Google ADK the only allowed agent framework** and says root wins on platform-wide governance. | **Genuine conflict — escalated to the operator (§K, Risk 1).** Working assumption: **LangGraph**, per "strictly follow the prompt in the files", implemented behind an `AgentOrchestrationPort` so an ADK adapter is a swap, not a rewrite. Recorded as ADR-002. | Cannot be resolved by inference; the port makes either answer cheap. |
| **C12** | **Workflow engine timing.** Temporal OSS is mandated for durable workflow, and MVP Phase 0 (L21834) puts Temporal in the very first foundation slice. Yet the revised 45-hour MVP budget (L25622–25648) allocates Temporal **zero hours**. | **Defer Temporal to Slice 7.** Implement stage-gate + approval + scheduling from Slice 1 as a DB-backed state machine plus a polling worker, behind a `WorkflowPort`. Temporal becomes an adapter. | Internal contradiction in the source itself; the port satisfies both. Nothing in MVP-1 is long-running — stability time points (the real durable case) arrive at Slice 11. |
| **C13** | **Local LLM timing.** MVP stack (L5045) includes Ollama; MVP scope lists "Basic RAG"; but the day plan puts Knowledge/RAG at Day 4, *after* MVP-1. | **AI Gateway port in Slice 1; Ollama adapter + pgvector RAG at Slice 4.** MVP-1 ships with MSD in application-guidance mode only (Phase 1 of the Concept Note's own 6-phase roadmap), which needs no LLM weights. | Concept Note §39 explicitly stages MSD in 6 phases starting with navigation/help. |
| **C14** | **Render.** Listed as zero-cost deployment convenience, but §3 (L9108) says free Render PostgreSQL **expires after 30 days** and "cannot be allowed to expire" for R&D IP. | **Docker/Podman Compose is the deployment path.** Render is optional demo staging only, and **must never hold real R&D records**. Independently confirmed by operator memory (`feedback_render_ephemeral_db`). | Source says so explicitly; data-integrity supersedes convenience. |
| **C15** | **CI/CD.** Forgejo Actions specified as the zero-cost self-hosted runner; GitHub Actions "optional convenience… not an architectural requirement". | **GitHub Actions** for this build (operator's existing toolchain, `gh.exe` present, zero cost at this scale), with all CI logic in `scripts/*.sh` so it is runner-agnostic. | Source explicitly permits it; scripts keep it portable. |
| **C16** | **DB schema list.** Master §37 lists 15 logical schemas; the schema narrative lists 13; messaging adds its own. | **16 canonical schemas** — see §F. | Union, deduplicated. |
| **C17** | **Pipeline stage list.** Blueprint §56: 18 stages. MVP-1 max-depth §4: 8-stage MVP pipeline expanding to 18. | **Stages are configuration rows, not an enum in code.** MVP seeds 8; full build seeds 18. | The later text explicitly frames it as MVP-then-expand; config avoids a migration. |
| **C18** | **Test authority levels.** Master §23: preliminary, development, controlled, validation, qualification, release (6). Test narrative §6: preliminary, development, controlled, qualification, release (5). | **6 levels** (master wins) — `validation` is needed because VALIDATION_CONFIRMATION is a distinct approval template. | Later + internally consistent with the 5 approval templates. |

---

## E. Architecture selected

### Stack (single canonical table — supersedes all five source listings)

| Layer | Technology | Slice introduced |
|---|---|---|
| Web framework | Next.js (App Router) + React + TypeScript | 1 |
| Styling / components | Tailwind CSS + shadcn/ui + Radix UI | 1 |
| Tables | TanStack Table + TanStack Virtual | 1 |
| Forms / validation | React Hook Form + Zod | 1 |
| Server state | TanStack Query | 1 |
| Charts | **Apache ECharts** (one `<ChartWrapper>`) | 1 |
| API | FastAPI + Python 3.12 | 1 |
| Validation | Pydantic v2 | 1 |
| ORM / migrations | SQLAlchemy 2.x + Alembic | 1 |
| Database | PostgreSQL 16 (+ RLS) | 1 |
| Vector / FTS | pgvector + PostgreSQL FTS | 4 |
| Identity | Keycloak | 1 |
| Cache / presence | Valkey | 1 |
| Object storage | **Garage** (S3-compatible, behind a port) | 2 |
| Workflow | DB state machine + worker (Slice 1) → **Temporal OSS** adapter (Slice 7) | 1 / 7 |
| AI orchestration | **LangGraph OSS** behind `AgentOrchestrationPort` (see C11) | 4 |
| Local LLM | Ollama (→ llama.cpp / vLLM adapters) | 4 |
| Embeddings | Sentence Transformers | 4 |
| Doc ingestion | Docling + PyMuPDF (+ Tesseract fallback) | 4 |
| Scientific | NumPy, SciPy, Pandas, Polars, statsmodels | 2 |
| DOE | pyDOE3 | 8 |
| Optimization | SciPy Optimize + Optuna | 8 |
| ML / explainability | scikit-learn + SHAP (+ MLflow registry) | 9–10 |
| Email | `NotificationService` → In-App + SMTP (+ optional Resend adapter) | 3 |
| Reports | Jinja2 + WeasyPrint + python-docx + OpenPyXL | 6 |
| Testing | Pytest, Hypothesis, Vitest, Playwright, axe-core, Locust, Bruno | 1 |
| Quality | Ruff, mypy, ESLint, Prettier, pre-commit | 1 |
| Security | Trivy, Semgrep Community, Gitleaks, SOPS + age | 1 |
| Observability | OpenTelemetry, Prometheus, Grafana OSS, Loki, Jaeger, Uptime Kuma | 14 |
| Proxy / runtime | Caddy + Docker/Podman Compose | 1 |

**Excluded by the mandatory rule:** OpenAI/Anthropic/Gemini/Azure OpenAI/Bedrock APIs, Pinecone, Firebase, Firestore, MongoDB Atlas, Auth0, Clerk, Okta paid, Supabase Cloud, AWS S3, Azure Blob, GCS, Datadog, New Relic, Splunk Cloud, AG Grid Enterprise, commercial workflow SaaS, commercial OCR.

### Repository layout (master amendment, C5)

```
EvercoatITWRD APP/
├── CLAUDE.md  CONTEXT.md  MEMORY.md  BRAIN.md  SECURITY.md
├── REQUIREMENTS.md  ARCHITECTURE.md  IMPLEMENTATION_PLAN.md
├── DATA_MODEL.md  DATABASE_RELATIONSHIPS.md  WORKFLOWS.md
├── UI_UX.md  NAVIGATION.md  API_CONTRACTS.md  AI_ARCHITECTURE.md
├── TESTING_STRATEGY.md  DEPLOYMENT.md  DECISIONS.md
├── ACCEPTANCE_CRITERIA.md  CHANGELOG.md  TODO.md
├── .claude/
├── apps/
│   ├── web/          # Next.js
│   └── api/          # FastAPI
│       └── app/{api,core,domains,services,repositories,calculations,workflows,agents,integrations}
├── services/         # keycloak realm, garage, valkey, (temporal @ slice 7)
├── workers/          # scheduler/notification worker; temporal workers later
├── packages/         # shared TS types, generated API client, ui-kit
├── infrastructure/   # compose files, caddy, sops, migrations tooling
├── tests/            # e2e (Playwright), load (Locust), api (Bruno)
├── scripts/          # quality-gate.sh, live-suite.sh, seed, backup
└── docs/{architecture,workflows,database,security,testing,ui,adr}
```

### Shared component library — built once in Slices 1–3, reused everywhere

The 14-day target is only reachable through this. Built early, then *composed*:

`StatusBadge` (colour+icon+text, never colour alone) · `TechnicalDataGrid` · `EntityHeader` · `ContextSubmenu` · `ApprovalEngine` (backend) · `ApprovalTimeline` (UI) · `DiscussionPanel` · `AttachmentManager` · `TaskCard` · `NotificationService` · `AuditHook` · `KpiCard` · `ChartWrapper` · `HistoryTimeline` · `AiRecommendationCard` · `RequirementStatus` · `EntityLink` · `MeasurementInput` (value+unit, canonical-unit conversion).

**Rule:** the Pilot module — and Validation, Stability, Quality, Qualification — must add **zero** new approval, discussion, attachment, task, audit, notification, or dashboard infrastructure. If a later slice needs new infrastructure, that is a defect in Slices 1–3, not new scope.

### Navigation (canonical — resolves C7/C8/C9)

**Sidebar**, collapsible (220–260 px expanded, 64–72 px collapsed), RBAC-filtered, with actionable counts:

```
WORK             Dashboard · My Work · Messages · Notifications
DEVELOPMENT      Innovation · R&D Pipeline · Projects · Formulations ·
                 Laboratory · Testing · Failures · DOE & Optimization
RESOURCES        Materials · Suppliers · Knowledge Library
INDUSTRIALIZATION Validation · Stability · Pilot & Scale-Up · Quality · Products
INTELLIGENCE     Analytics · Product Models · Infographics · Reports
GOVERNANCE       Approvals · Administration
```

**Contextual top submenus** (sticky, horizontally scrollable):

- **Project** — Overview | Requirements | Research | Benchmarks | Materials | Formulations | Laboratory | Testing | Failures | DOE | Validation | Stability | Pilot | Qualification | Documents | Risks | Team | Messages | Approvals | History
- **Formula** — Formula | Calculations | Comparison | Lab Batches | Tests | Failures | DOE | Predicted Performance | AI Analysis | Discussion | Documents | Approvals | History
- **Test** — Overview | Sample | Method | Result Entry | Analysis | Comparison | Modeling | Recommendations | Discussion | Approvals | History
- **Failure** — Failure | Evidence | Hypotheses | Root Cause | Actions | Related Formulas | Retests | AI Analysis | Discussion | History
- **Lab Batch** — Overview | Materials | Weighing | Process | Samples | Deviations | Tests | Documents | History
- **Pilot** — Overview | Formula | Equipment | Batch Plan | Process | Execution | Samples | Testing | Comparison | Deviations | Discussion | Decision
- **Product** — Overview | Versions | Master Formula | Specifications | Manufacturing | QC | Documents | Production Performance | Complaints | CAPA | Change Control | History

Plus: global top bar (org selector · global search · Quick Create · MSD · notifications · help · profile), clickable breadcrumbs, right-hand context drawer, `Ctrl/Cmd+K` command palette, unsaved-changes guard on formula/batch/result/DOE forms, and workflow-aware post-action redirects (submit formula → approval status; approve lab → create batch; complete batch → samples/test queue; record failed test → failure investigation).

Evidence-of-completeness note: the Failure submenu deliberately places **Evidence before Root Cause** so the UI itself enforces facts-before-conclusions.

### Test Module — the load-bearing subsystem

Given maximum implementation depth in MVP-1 (source devotes an entire 60-section pass to it).

- `test_purpose` ∈ {screening, oversight, confirmation, improvement} — orthogonal to
- `authority_level` ∈ {preliminary, development, controlled, validation, qualification, release} (C18)
- **Raw measurements are stored per replicate**, never only the aggregate. Statistics computed in-app: mean, min, max, range, variance, SD, CV, confidence interval, % change, pass margin, historical/formula/benchmark/batch comparison, trend, outliers, ANOVA where justified.
- **Status is derived, never picked.** Decision matrix:

| Technical result | Approvals complete | Deviation | Display |
|---|---|---|---|
| Pass | Yes | None | **GREEN** |
| Pass | No | None | **YELLOW** |
| Pass | Yes | Minor concern | **YELLOW** |
| Pass, low margin (inside warning threshold) | Any | Any | **YELLOW** |
| Fail | Any | Any | **RED** |
| Incomplete replicates | No | — | **YELLOW** |
| Excessive variability (CV over limit) | Any | Any | **YELLOW** |
| Oversight in-spec but adverse trend | Any | Any | **YELLOW** |
| Expired-calibration equipment | Any | Any | **YELLOW/RED** by policy |

- **Colour is never the sole indicator** — always colour + icon + text (`✓ PASS`, `✕ FAIL`, `! CONDITIONAL`), and every YELLOW must state *why* and *what is next*.
- Five configurable approval templates: `SCREENING_SIMPLE`, `OVERSIGHT_STANDARD`, `VALIDATION_CONFIRMATION`, `QUALIFICATION_CONFIRMATION`, `RELEASE_CRITICAL`. Sequential **and** parallel. Decisions are richer than approve/reject: Approve · Approve with Condition · Return for Correction · Request Retest · Reject · Escalate · Request Additional Test.
- **Segregation of duties:** for confirmation tests at `qualification`/`release` authority, the executing user may not also supply all mandatory approvals. Enforced server-side.
- `final_confirmed` is server-enforced: required data present, replicates complete, no blocking deviation, all mandatory levels approved, user authorized, audit written.

### MSD — Material Science & Development Assistant (C10, C13)

Persistent, unobtrusive control; side panel and full-screen workspace. Header shows live context. Suggested actions per the Concept Note §33.

**Architectural principle (Concept Note §37):**
`MSD conversation → Permission check → Context identification → R&D knowledge retrieval → Deterministic tools/models where required → Evidence assembly → Response → Optional human-approved action`

**MSD operates under exactly the user's authorization boundary.** If the user cannot open Formula F100 in the app, MSD must not retrieve, summarize, infer, or leak F100 in chat. AI must never become a permission-bypass channel. This is a security test case, not an aspiration (`tests/e2e/rbac/msd_boundary.spec.ts`).

Phased per Concept Note §39 — Slice 4: application guidance, knowledge search, formula retrieval/comparison, material lookup, test explanation, failure history, pending work, context navigation. Slices 6/8/9/10 add failure hypotheses, DOE interpretation, predictive what-if, uncertainty-aware recommendations.

**Outputs are governed:** every MSD answer carries evidence links to source records. Conclusions become controlled records only by explicit human promotion into Technical Decision · Experiment Proposal · Recommendation · Failure Hypothesis · Corrective Action · Task.

---

## F. Database architecture

PostgreSQL 16, **16 logical schemas** (C16):

`core` · `projects` · `materials` · `formulations` · `laboratory` · `testing` · `workflow` · `quality` · `products` · `knowledge` · `messaging` · `analytics` · `modeling` · `ai` · `audit` · `innovation`

### Integrity rules (non-negotiable)

- **NUMERIC, never float**, for percentages, masses, densities and measured values. Floating-point on controlled formulation percentages is a defect.
- **FK delete rules: `RESTRICT` / `NO ACTION`** for projects↔formulas, formula_versions↔batches, batches↔tests, materials-used-in-formulas, released products. **Never cascade-delete R&D history.** Retirement is `inactive` / `obsolete` / `archived` status, never deletion.
- **Composite `ON DELETE SET NULL` is banned** — it nulls every key column including `NOT NULL` tenant keys. Name the column explicitly (PG15+).
- **Unique constraints in the database, not only the app:** `(organization_id, project_code)`, `(formula_id, version_number)`, `(organization_id, raw_material_code)`, `(organization_id, product_code)`, `lab_batch_number`, `sample_number`, `(document_id, revision_number)`.
- **Indexes** on every FK used in joins, plus composites `(organization_id, status)`, `(project_id, current_stage)`, `(formula_version_id, test_date)`, `(raw_material_id, supplier_id)`.
- **RLS on `organization_id`** for every proprietary table, with `FORCE ROW LEVEL SECURITY`. The application connects as a non-superuser role. Migrations, backfills and orphan checks must be written to run *under* that role — a migration that only works as superuser is a latent production failure.
- **Referential traceability rule:** *no released product without a qualified formula; no qualified formula without validation and pilot evidence; no validated formula without lab batches and tests; no test result without traceability to the physical sample.* Enforced in both schema and workflow.
- **Audit is append-only**, unreachable from ordinary UI paths, written by a shared hook — not by each module separately.

### Controlled document numbering

`RDP-2026-001` · `RDP-2026-001-F001` · `RDP-2026-001-LB001` · `RDP-2026-001-T001` · `RDP-2026-001-FA001` · `RDP-2026-001-DOE001` · `RDP-2026-001-P001` · `RDP-2026-001-Q001` · `PRD-2026-001`. Sequences are per-organization and gap-tolerant; codes are immutable once issued.

### Analytics

Views and materialized views under `analytics.*` — `project_health`, `project_pipeline`, `pipeline_duration`, `formula_performance`, `test_status`, `test_performance`, `failure_summary`, `approval_summary`, `team_workload`, `material_dependency`, `pilot_comparison`, `model_performance`, `product_quality`, `portfolio_summary`, `ai_effectiveness`. Refreshed by the scheduler worker (hourly project KPIs, daily portfolio, weekly R&D indicators); critical project status stays real-time. **Dashboards never issue unbounded queries against transactional tables** — and every analytics query is RLS- and project-membership-scoped, so no chart can aggregate records the viewer cannot open.

---

## G. Modules and dependency order

```
0  Foundation ── 1 Identity/RBAC/Audit ── 2 App Shell/Navigation
                        │
                        ├── 3 Projects · Pipeline · Requirements · My Work · Tasks
                        │        │
                        │        ├── 4 Materials · Suppliers · Lots · Documents
                        │        │        │
                        │        │        └── 5 Formulations (versions, calc, compare)
                        │        │                 │
                        │        │                 └── 6 Laboratory (batches, lots, samples)
                        │        │                          │
                        │        │                          └── 7 Testing (raw data, stats,
                        │        │                                   traffic light)
                        │        │                                   │
                        │        │                          8 Approvals (shared engine)
                        │        │                                   │
                        │        │                          9 Failures · Reformulation · Retest
                        │        │
                        │        └── 10 Messaging · Notifications
                        │
                        └── 11 Dashboards · Analytics
                                 │
      12 Knowledge/RAG/MSD ── 13 DOE ── 14 Optimization ── 15 Product Modeling
                                 │
      16 Validation ── 17 Stability ── 18 Pilot/Scale-Up ── 19 Manufacturing Process
                                 │
      20 Quality/QC ── 21 Qualification ── 22 Release ── 23 Product Lifecycle/CAPA
                                 │
                          24 Advanced Analytics · Infographics · Reports
```

**Hard sequencing rationale (source §95, L3385):** the intelligence layer is built *on* reliable structured R&D data. AI is never the foundation. Any proposal to pull DOE, modeling or RAG earlier is rejected.

---

## H. MVP-1 implementation sequence

**Gate:** MVP-1 is complete when the golden end-to-end scenario passes **on the deployed instance**, not locally.

### Slice 1 — Foundation, Identity, Shell
Compose stack (web, api, postgres, keycloak, valkey, caddy) · Alembic baseline · Keycloak realm with 10 roles · JWT verification · permission model · organizations/users/roles/permissions/memberships · **RLS from the first migration, not retrofitted** · audit hook · left sidebar + top bar + contextual submenu + breadcrumbs + role-aware nav · four empty-but-final-architecture role dashboards · shared component library v1 · CI (ruff, mypy, eslint, vitest, pytest, gitleaks, trivy, semgrep).

### Slice 2 — Projects, Pipeline, Requirements, My Work
Opportunities → projects · project members · milestones · risks · stage definitions (8 seeded) · **stage_history preserved, not just `current_stage`** · requirements as structured records with target/min/max/unit/criticality/verification method · Requirements Verification Matrix · tasks + My Work inbox · project dashboard · project context bar.

### Slice 3 — Materials, Suppliers, Formulations
Raw material library with 5 statuses · properties · documents (TDS/SDS/CoA) · lots · suppliers M:M · material usage + performance history · formula workspace · components with NUMERIC wt.% · deterministic calculation engine (total %, batch scaling, theoretical density, binder/filler, resin/hardener, equivalents, solids, VOC estimate, cost) · **hard submission validation** (total outside tolerance, missing material data, restricted material, failed safety check → block) · versioning with `parent_version_id` + branches · difference engine (old/new/Δ/%Δ/reason/expected/observed) · formula approval + lock.

### Slice 4 — Laboratory
Batch from approved formula version · guided flow Material Verification → Lot Selection → Weighing → Charging → Mixing → Process Capture → Sampling → Deviations → Completion · planned vs actual per component with tolerance flagging · process parameters (RPM, temp, time, vacuum) · deviations · samples with full traceability chain · batch review accept/reject.

### Slice 5 — Testing (maximum depth)
Test methods + method versioning · test plans + items · purpose × authority · equipment + calibration check · sample integrity check · **per-replicate raw measurement capture** · statistics engine (Hypothesis-tested) · warning thresholds · derived traffic-light per the decision matrix · Test Result workspace with the 11-item submenu · test dashboard.

### Slice 6 — Approvals, Failures, Reformulation
Shared multi-level approval engine (sequential + parallel, 7 decision types, conditional approval, segregation of duties) · 5 templates · approval timeline UI · electronic decision records · **critical RED auto-opens Failure Investigation** · evidence/hypotheses/root cause with `proposed|under_review|accepted|rejected` · **hypothesis ≠ accepted root cause, enforced** · corrective actions · failure → formula revision link · retest with `parent_test_result_id`.

### Slice 7 — Messaging, Notifications, Dashboards, MVP release
Project channels auto-created with the project · direct messages · technical threads on Formula/Test/Failure/Batch · mentions (user + role) · `#F008` smart record linking · embedded formula/test/failure cards · message→task / →decision / →failure / →experiment / →approval-request · NotificationService (in-app + SMTP adapter) · four completed role dashboards with drill-down to source records · **golden Playwright E2E** · RBAC E2E (attempted unauthorized access, not just hidden buttons) · deploy · **full live suite on the deployed site**.

### The golden scenario (MVP-1 acceptance, master prompt §44)

Director creates/approves project → Lead assigns team → Chemist creates formula → Lead approves lab → Lab creates batch + sample → Engineer creates confirmation test → raw results entered → app analyzes → **RED** → failure investigation opens → Chemist creates revised formula → new batch → retest passes technically → **YELLOW pending approvals** → Engineer/Chemist/Lead approve → **GREEN** → formula becomes validation candidate → **dashboards update**.

Every arrow is asserted in both UI and database state. The YELLOW→GREEN transition is the single most important assertion in the suite: it proves rule 6.

---

## I. Full-build sequence (Slices 8–20)

| Slice | Deliverable |
|---|---|
| 8 | Knowledge Library · Docling/PyMuPDF ingestion · Garage · Sentence Transformers · pgvector hybrid retrieval · Research workspace · **MSD Phase 1–2** with evidence links |
| 9 | Advanced Test Module — dynamic entry schemas, confidence intervals, outliers, control limits, benchmark comparison, result revisions, test analytics |
| 10 | Failure intelligence — cause trees, multi-hypothesis, AI failure analysis, recommendation effectiveness tracking |
| 11 | **Temporal OSS** adapter behind `WorkflowPort` · durable stage gates · escalations · scheduled test points |
| 12 | DOE — pyDOE3 designs, runs↔formula/batch linkage, statsmodels main effects/interactions/significance, response surfaces, contour plots |
| 13 | Optimization — SciPy + Optuna, multi-objective, Pareto candidates, constraint handling |
| 14 | Product Modeling — datasets, scikit-learn, cross-validation, MLflow registry, SHAP, actual-vs-predicted, drift, **model governance states**, Predicted Performance panel (visually separated from measured) |
| 15 | Validation + Stability — repeat batches, reproducibility, requirement coverage, storage conditions, time points, trends vs spec limits |
| 16 | Pilot + Scale-Up — pilot plans, equipment, process parameters, lab-vs-pilot comparison, **non-linear scale-up** (RPM/tip speed/shear/vacuum/addition rate never assumed linear) |
| 17 | Manufacturing Process + Quality — master procedure, 13 controlled steps, QC specs, incoming/in-process/finished/retention QC |
| 18 | Qualification + Release — dossier aggregation, 5-level release route, **master formula lock**, product versions |
| 19 | Product Lifecycle — production results, complaints, field issues, CAPA, change control, improvement projects closing the loop into R&D |
| 20 | Advanced analytics, infographics, reports, observability, hardening, performance, backup/restore, full regression |

---

## J. Security decisions

Detailed in `SECURITY.md`. The decisions that shape the build:

1. **Defence in depth, three independent layers.** Keycloak identity/role → FastAPI permission + resource scope + business rule → PostgreSQL RLS. Any one failing must not expose data.
2. **`FORCE ROW LEVEL SECURITY`, app connects as non-superuser.** Local superuser development hides RLS defects that only appear in production; the test suite runs `SET ROLE evercoat_itw_rd_app`.
3. **Frontend permission checks are cosmetic.** Every control is re-enforced server-side, and Playwright tests *attempted unauthorized access*, not hidden buttons.
4. **MSD inherits the caller's authorization exactly** (C10). Retrieval is filtered before the LLM sees anything — never filtered after generation.
5. **Server-controlled fields are unreachable from the client.** Separate Pydantic schemas per operation (`FormulaCreate`/`FormulaUpdateDraft`/`FormulaRead`/`FormulaSubmit`/…) so `approved_by`, `locked_at`, `release_status`, `final_status`, `display_color` can never be client-set.
6. **Formulation data is high-value IP.** Attachments served via short-lived signed URLs only; no public object URLs; document access audited.
7. **Secrets via SOPS + age**, never plaintext in Git. Gitleaks in CI. *(Operator note: PowerShell pipes add a UTF-16 BOM to secrets — write secret files with explicit UTF-8.)*
8. **Audit immutable and append-only**, covering formula revision/approval, test entry/correction/approval, failure closure, stage transition, qualification, release, role change.
9. **Released master formula is read-only at the database level**, not merely hidden in UI.
10. **Zero-cost rule is itself a security control** — proprietary formulations never leave the organization's infrastructure for a third-party AI API.

---

## K. Risks and missing information

**Risk 1 — LangGraph vs. Google ADK (C11). Needs an operator decision.**
The source mandates LangGraph 5×. The root house rule declares ADK the only permitted agent framework and asserts precedence on governance. Mitigation in place: `AgentOrchestrationPort`, so either is an adapter. But this should be decided consciously rather than defaulted. **Raised in §L.**

**Risk 2 — The 3-day / 14-day schedule is not achievable at the specified depth. This is the largest risk in the document.**
The source asks for 45 hours to deliver: Keycloak + RBAC + RLS + audit + full app shell + projects + pipeline + requirements + materials + suppliers + formulations with versioning and a deterministic calculation engine + laboratory batch execution + the Test Module *at maximum depth* + a configurable multi-level approval engine + failure investigation + reformulation + messaging + four role dashboards + a full Playwright golden path. Then 165 more hours for DOE, optimization, ML modeling with MLflow and SHAP, Temporal, RAG, validation, stability, pilot, scale-up, manufacturing, QC, qualification, release, lifecycle, and observability.

The source's own §49 (L25568) concedes the target holds only "if the team avoids rebuilding infrastructure separately for every module" — which is correct engineering advice and still not sufficient. It also assumed a reference application existed to reuse; §A establishes that none does.

**Adjustment — and it is a re-basing, not a reduction in scope:** the day numbering is retained *as a dependency-ordered slice sequence*, because the ordering is genuinely sound. "Day N" becomes "Slice N", a completion-gated unit. Slices ship in order; each is demonstrable; none is declared done on a green build alone. Nothing is cut from the target end-state. What changes is that calendar dates stop being the completion criterion and **passing gates** become the completion criterion. If the operator needs a hard calendar date, §5 of the source (L23803, "What Must Be Deferred if Schedule Slips") governs, and the defer-first order is: Infographics → Advanced Analytics → Product Modeling → Optimization → DOE → Stability → Lifecycle. The MVP-1 core is never deferred.

**Risk 3 — a green build is not a working feature.** Type-checks, unit tests and a successful deploy have all previously coexisted with a product that could not be used. Every slice gate requires the feature to be exercised in a browser against the deployed instance, and the **full live suite must run against the deployed site after every deploy**, reporting passed / failed / **skipped** as three separate numbers.

**Risk 4 — Windows/Docker environment.** Keycloak, Postgres, Valkey, Garage and later Temporal + Ollama on Docker Desktop is memory-heavy. Slice 1 must measure actual container memory before Slice 8 adds model weights. Ollama model size will be chosen from measured headroom, not assumed.

**Risk 5 — no Evercoat domain data.** No real raw materials, test methods, requirement sets or product families are supplied. Seed data will be **synthetic and clearly labelled as such**, modelled on the source's own worked example (RDP-2026-014 Premium Lightweight Putty, F001→F008, RM-014 talc, adhesion ≥6.0 MPa). No undocumented ITW procedure will be represented as an official requirement — the master prompt (§10) explicitly forbids this.

### Missing information (assumptions stated, build proceeds)

| # | Unknown | Assumption |
|---|---|---|
| M1 | Deployment target — self-hosted server, Render staging, or local only | Docker Compose local + optional Render demo. Real R&D data never on Render free Postgres. |
| M2 | Git remote / repository name | Local git initialised; remote deferred until the operator names one. |
| M3 | Real user list and org name | Seed org "ITW Evercoat (Demo)" + 10 synthetic users, one per role. |
| M4 | SMTP credentials | Console/dev-mail adapter in dev; SMTP config at deploy. Resend optional. |
| M5 | Multi-tenant or single-org | Built multi-tenant (`organization_id` + RLS everywhere) — cheap now, expensive to retrofit. |
| M6 | Actual test methods (ASTM/ISO refs) | Method records are data; seeded with generic method definitions, editable in Administration. |
| M7 | Warning-threshold policy (e.g. 6.0 min / 6.3 warn) | Configurable per requirement; seeded at +5% of the acceptance limit. |

---

## L. Open question for the operator

**AI framework: LangGraph (as the source mandates) or Google ADK (as the house rule mandates)?**
Working assumption is LangGraph, because the instruction for this build was to follow the source prompt strictly. It sits behind `AgentOrchestrationPort`, so switching costs one adapter, not a rewrite — but only if decided before Slice 8. Everything up to Slice 7 is unaffected either way, so **this does not block the start of the build.**

Secondary, non-blocking: the app name is `EvercoatITWRD APP` per the source's explicit mandate, not "ITW Evercoat RD App" as phrased in the request. Reversing it changes branding strings only.

---

## M. Definition of Done (every module, every slice)

A module is **not** complete because CRUD works. Required, where applicable:

database schema · relationships · migrations · indexes · constraints · Pydantic schemas · domain service · validation · business rules · REST API · RBAC + resource scope · frontend list/queue view · detail workspace · contextual submenu · status header · empty/loading/error states · workflow status · approval · tasks/notifications · discussion link · audit · dashboard KPI · analytics · Pytest · Hypothesis (scientific code) · Playwright (critical flows) · accessibility (axe-core, no colour-only status) · documentation · CHANGELOG/CONTEXT/MEMORY/TODO updated.

**And the four governance gates:** Codex CLI review → Supervisor audit → Work Reviewer Agent → Work Scheduler Agent. Plus the live-suite rule: after every deploy, the full suite runs against the **deployed** site and reports passed / failed / skipped as three numbers.
