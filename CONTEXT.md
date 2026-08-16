# CONTEXT.md — EvercoatITWRD APP

Concise orientation for a new engineer or a future Claude session. Read alongside `CLAUDE.md` (rules) and `BRAIN.md` (reasoning and domain model).

**Last updated:** 2026-08-16 — planning pass 1, pre-Codex-review.

---

## Product purpose

A controlled digital R&D operating environment for formulated chemical products (automotive putties, body fillers, epoxy systems, adhesives, sealants, primers, coatings, UV-curing repair products). It digitizes the complete product-development lifecycle from innovation opportunity through commercial release and post-market continuous improvement, and preserves an unbroken **digital thread** linking every requirement, material, formula version, batch, sample, test, failure, approval, pilot, qualification and released product.

Two complementary intelligence mechanisms:
- **Structured computational intelligence** — deterministic formula calculations, statistics, DOE, optimization, predictive models.
- **MSD conversational intelligence** — natural technical language over the same controlled data, under the same authorization boundary.

Operating philosophy: *The application records and controls. Scientific engines calculate and model. MSD retrieves, explains, compares and recommends. Laboratory testing produces physical evidence. R&D professionals exercise technical judgment. Authorized personnel approve. The organization retains and learns from the resulting knowledge.*

---

## Users

Four principal roles drive the workflow:

| Role | Owns |
|---|---|
| **Product Development Chemist** | Formulation, revisions, material selection, reformulation hypotheses, DOE participation, validation nomination |
| **Product Development Engineer** | Test plans and methods, engineering analysis, processability, pilot planning, scale-up, lab-vs-pilot, production readiness |
| **Product Development Lead** | Projects, team assignment, pipeline, stage gates, formula progression, risk, validation/pilot gates |
| **Product Development Director** | Portfolio, innovation approval, resources, critical risk, qualification oversight, release authorization |

Six supporting roles: QA/Compliance Officer, Laboratory Technician, Procurement Specialist, Production Engineer, Executive Viewer, Administrator.

The four-role handoff: Director approves strategy → Lead controls gates → Chemist formulates ↔ Engineer tests and industrializes → Lead controls validation/pilot progression → Engineer controls scale-up → Chemist confirms equivalence → Lead prepares qualification → Director approves release.

---

## Core workflows

1. **Innovation** — opportunity → feasibility → Director decision → project.
2. **Development loop (the heart of the system)** — requirements → research → benchmark → materials → formula → lab batch → sample → test → analysis → traffic-light status → multi-level approval → **fail: failure investigation → root cause → corrective action → new formula version → retest** / **pass: validation candidate**.
3. **Industrialization** — validation → stability → pilot → scale-up → manufacturing process → QC → qualification dossier → release → locked master formula.
4. **Post-market** — production results → complaints/field issues → CAPA → improvement project → back into the development loop.

Cross-cutting: My Work task inbox, multi-level approvals, notifications and escalation, messaging attached to technical records, audit on every controlled action, role dashboards, analytics with drill-down to source records, MSD.

---

## Current build status

| | |
|---|---|
| **Phase** | Planning — review pass 1 complete, plan at **v3** |
| **Code written** | None yet |
| **Files that exist** | `CLAUDE.md` · `CONTEXT.md` · `MEMORY.md` · `BRAIN.md` · `SECURITY.md` · `DECISIONS.md` (ADR-001…024) · `REUSE.md` · `IMPLEMENTATION_PLAN.md` · `docs/REVIEW_PASS1_ADJUDICATION.md` · `.gitignore`. Local git repo, no remote |
| **Still to create** | `REQUIREMENTS.md` · `ARCHITECTURE.md` · `DATA_MODEL.md` · `DATABASE_RELATIONSHIPS.md` · `WORKFLOWS.md` · `UI_UX.md` · `NAVIGATION.md` · `API_CONTRACTS.md` · `AI_ARCHITECTURE.md` · `TESTING_STRATEGY.md` · `DEPLOYMENT.md` · `ACCEPTANCE_CRITERIA.md` · `CHANGELOG.md` · `TODO.md`. Until these exist, cross-references to them in other files are forward declarations, not descriptions of reality |
| **Completed** | Both reference documents read in full (29,862 + 944 lines) · plan drafted, reviewed and revised twice · Solar PV Designer Lite inspected and reuse decided (`REUSE.md`, ADR-022) |
| **Review outcome** | Codex **FAIL** (43 findings, 5 BLOCKER) → Supervisor **FAIL upheld** (40 upheld, 3 overturned/narrowed, 1 escalated) → v2 → Supervisor code-review (13 findings, 9 new) → v3 |
| **Next** | Slice 1 — Foundation, Identity, Administration §1, Shell, Observability |

> **Discipline note.** An earlier version of this table stated that `MEMORY.md` and `DECISIONS.md` had been created when they had not. The Supervisor caught it. *Measure the repo; do not quote the handover.* The "Still to create" row exists so this file cannot make that mistake again.

### Modules outstanding

All of them. Build order is the slice sequence in `IMPLEMENTATION_PLAN.md` §H/§I:

Foundation/Identity/Shell → Projects/Pipeline/Requirements → Materials/Suppliers/Formulations → Laboratory → Testing → Approvals/Failures → Messaging/Dashboards **(= MVP-1)** → Knowledge/RAG/MSD → Advanced Test → Failure Intelligence → Temporal → DOE → Optimization → Product Modeling → Validation/Stability → Pilot/Scale-Up → Manufacturing/Quality → Qualification/Release → Lifecycle → Advanced Analytics/Hardening.

---

## Key architecture decisions

Full records in `DECISIONS.md`. The ones that shape daily work:

1. **Monorepo**: `apps/web` (Next.js) + `apps/api` (FastAPI) + `services/` + `workers/` + `packages/` + `infrastructure/` + `tests/` + `docs/`.
2. **Three independent authorization layers** — Keycloak identity/role, FastAPI permission + resource scope + business rule, PostgreSQL RLS on `organization_id`. Any one failing must not expose data.
3. **Permissions, not role names**, drive authorization.
4. **NUMERIC not float** for all controlled quantities; **RESTRICT not CASCADE** on R&D history.
5. **One shared approval engine, one discussion panel, one audit hook, one notification service, one chart wrapper** — built in Slices 1–3, composed thereafter. This is what makes the schedule survivable.
6. **Ports for the heavy or contested dependencies** — `WorkflowPort` (DB state machine now, Temporal later), `AgentOrchestrationPort` (LangGraph, ADK possible), `ObjectStoragePort` (Garage, MinIO possible), `EmailPort` (SMTP, Resend possible). Business logic never imports a vendor.
7. **Test status is derived**, and `calculated_result` is separate from `approved_result`.
8. **Docker Compose is the deployment path.** Render is optional demo staging and must never hold real R&D records.

---

## Critical domain terminology

| Term | Meaning — do not blur these |
|---|---|
| **Formula** | The logical formulation identity |
| **Formula Version** | One controlled revision (F001, F002, F004-A…). Versions are immutable once approved |
| **Lab Batch** | One physical execution of one formula version |
| **Material Lot** | The specific supplier lot consumed by a batch — the link that makes failures explainable |
| **Sample** | Physical specimen produced by a batch, tested by test results |
| **Test Purpose** | Why: screening / oversight / confirmation / improvement |
| **Authority Level** | How much the result counts: preliminary / development / controlled / validation / qualification / release |
| **`calculated_result`** | Automatic evaluation against acceptance criteria |
| **`approved_result`** | The result after all mandatory approvals — only this can be GREEN |
| **Hypothesis** | Proposed cause (human or AI). Never a fact |
| **Accepted Root Cause** | Human-verified and approved. Only humans promote hypothesis → root cause |
| **Calculated / Predicted / Measured** | Three distinct property values. Never merge or visually conflate them |
| **Validation Candidate** | A formula version nominated after passing critical tests |
| **Qualification Dossier** | Aggregated evidence assembled before release |
| **Master Formula** | The released, locked formulation. Read-only |
| **MSD** | Material Science & Development Assistant — the conversational layer |

---

## Known constraints

- **Zero-cost open-source core is mandatory.** No paid SaaS or paid AI API may become essential.
- Windows 10 host, PowerShell 5.1 primary shell, Docker Desktop. `no &&`/`||` in PowerShell; use Bash for POSIX one-liners.
- Node at `C:\Users\USER\nodejs` (not on default PATH).
- Docker memory is the binding constraint once Ollama arrives — measure before adding model weights.
- No real Evercoat domain data supplied. Seed data is synthetic and labelled as such; no undocumented ITW procedure may be represented as an official requirement.
- Render free PostgreSQL expires after 30 days — unusable for R&D IP.

---

## Current risks

| | Risk | Status |
|---|---|---|
| 1 | **LangGraph (source-mandated) vs Google ADK (house rule)** | Open — escalated to operator. Mitigated by `AgentOrchestrationPort`. Must be decided before Slice 8 |
| 2 | **3-day MVP / 14-day full build is not achievable at the specified depth** | Re-based to gate-completed slices; nothing cut from the end state. Defer-first order defined |
| 3 | **A green build is not a working feature** | Every slice gate requires browser exercise on the deployed instance + full live suite reporting passed/failed/skipped |
| 4 | Docker memory headroom on Windows | Measure at Slice 1, before Slice 8 |
| 5 | No real domain data | Synthetic seed, clearly labelled |
| 6 | Test Module is the highest-complexity subsystem and lands in MVP-1 | Given maximum depth and the largest share of Slice 5–6 effort |
