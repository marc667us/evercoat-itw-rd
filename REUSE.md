# REUSE.md — what EvercoatITWRD APP takes from Solar PV Designer Lite

**Instruction:** reuse the Solar app's technology stack partly, topped with the rest recommended in the owner docs.

**Source:** `C:\Users\USER\Desktop\solar-pv-designer-lite` — Flask SaaS, live at `solarpro.aiappinvent.com`, Postgres cutover 2026-06-13, Keycloak migration complete, SOC 2 controls M3.2/M3.4 shipped.

**Method:** inspected the actual repository rather than assuming from memory — manifests, 28+ migrations, workflow files, logging and secrets modules. What follows is measured, not recalled.

---

## Why this matters more than it looks

The single highest-risk item in this project, per both reviewers, is the **authorization and tenancy model** (Codex Q3). Solar has already run **FORCE ROW LEVEL SECURITY multi-tenancy on production PostgreSQL**, through a phased cutover, with a tamper-evident audit chain on top. That is precisely the hardest, most expensive-to-retrofit part of the EvercoatITWRD build, and it exists in working form eleven metres away.

Reusing it converts the project's top risk from *unproven design* into *proven pattern plus a known extension*.

**But it must be extended, not copied.** See §3 — Solar's RLS is tenant-scoped only, which is exactly the defect Codex flagged as BLOCKER F32.

---

## 1. Reused directly — high value

| # | Asset | Solar location | Use here |
|---|---|---|---|
| R1 | **Phased RLS migration pattern** — `current_tenant_id()` GUC helper, 4-part split so a half-apply leaves a defined state, permissive parallel-run policy, hard `FORCE` cutover deferred to a later migration, fully idempotent (`IF NOT EXISTS` throughout), same file to staging and prod | `migrations/003_rls_tenant.sql`, `015`, `018`, `019`, `020`, `022`, `023` | The Slice 1 RLS foundation. Rename `tenant_id` → `organization_id`, GUC `app.current_tenant` → `app.current_org`. **Then extend** — §3 |
| R2 | **SHA-256 audit hash chain** — `prev_hash`/`row_hash` per row, `GENESIS` seed, canonical pipe-joined serialisation recomputed independently by PostgreSQL *and* the Python writer so each verifies the other; editing any row breaks that row's hash and every subsequent link; deletion breaks the chain at the next row; verifier walks `id ASC` and reports the first break | `migrations/016_audit_log_hash_chain.sql` + `app/security/audit.py` | **Supersedes the plan's weaker "append-only triggers".** This answers Codex F22 (audit immutability must be database-enforced and tamper-evident, not an app hook) with a shipped implementation |
| R3 | **Two-step foreign-key addition** — add FKs `NOT VALID`, then `VALIDATE CONSTRAINT` in a separate migration, so a large live table is never long-locked | `migrations/013_add_foreign_keys.sql` + `021_validate_foreign_keys.sql` | Every composite tenant FK in Slice 1, and every later FK added to a populated table |
| R4 | **Keycloak JWT verification** via `python-jose[cryptography]` — chosen over `python-keycloak` to avoid a heavy dependency tree; RS256 against realm JWKS | `requirements.txt` + Keycloak wiring patches | Same library, same approach. Flask decorator becomes a FastAPI dependency |
| R5 | **Tenant-aware structured JSON logging** with typed channels — `app`, `audit`, `security`, `engineering`, `economic`, `ai`, `queue`, `error` | `logging_config/structured_logger.py` | Slice 1 observability baseline (Codex F43). Channels remap to this domain: `app`, `audit`, `security`, `formulation`, `laboratory`, `testing`, `ai`, `queue`, `error` |
| R6 | **Secrets encrypted at rest** — `.env` encrypted with Fernet, with the deliberate note that `cryptography` is a *direct* dependency because "a transitive dependency that a security feature relies on is one refactor from vanishing" | `secrets_file.py`, `secrets_broker.py` | Complements SOPS + age. The reasoning about direct-vs-transitive security dependencies is adopted as a standing rule |
| R7 | **Prometheus `/metrics`** — `prometheus-client`, stateless, module-global registries reset per process | `requirements.txt`, monitoring wiring | Slice 1 metrics |
| R8 | **Resend email adapter** — a working provider implementation | `resend` usage | Drops straight into `NotificationService` as the optional `ResendProvider` behind `EmailPort` |
| R9 | **Celery + Redis background worker** | `celery==5.4.0`, `redis==5.0.7` | Celery on **Valkey** (Redis wire-compatible) becomes the Slice 1 `WorkflowPort` implementation — the scheduler/notification/analytics-refresh worker, before Temporal arrives at Slice 11. Removes the need to hand-roll a polling worker |
| R10 | **Gated migration-apply GitHub workflows** — one workflow per migration, manual dispatch, confirmation input | `.github/workflows/apply-migration-*.yml` (25+) | Same pattern. **With two known traps carried forward:** a step gated on `confirm == APPLY` may never have actually run, and a GitHub concurrency group is a one-slot replacement waiting room, not a queue — after dispatching, confirm the run id actually started |
| R11 | **Codex review harness** — `codex-review.sh`, `codex-security-review.sh`, `codex-db-review.sh`, `codex-performance-review.sh`, `codex-test-review.sh`, plus `ai-coworkers/` and `reviews/` | `scripts/codex-*.sh` | The four-gate quality process, already proven on this repo pair |
| R12 | **`apply_postgres_migrations.sh`** and `tenant_inventory.py` | `scripts/` | Migration runner and a tenant-coverage auditor that answers "which tables are missing tenant scoping" — directly useful as the Slice 1 RLS-coverage test |
| R13 | **`markdown-pdf`** for document generation | `requirements.txt` | Matches the operator's known-good toolchain (pandoc, wkhtmltopdf, reportlab and weasyprint are **not** installed on this machine). Adopted for reports in place of WeasyPrint — see §4 |

---

## 2. Not reused, and why

| Asset | Reason |
|---|---|
| Flask app, routing, Jinja templates | Owner docs mandate **Next.js + React + TypeScript** frontend and **FastAPI** backend. Non-negotiable — the zero-cost stack pass names them five times |
| `auth/*_window.py` | Tkinter **desktop** windows (`login_window`, `dashboard_window`, `chatbot_window`). Not web auth; not applicable |
| Domain code — PV design, BOQ, shading, cable sizing, marketplace | Different domain entirely |
| SQLite mirror layer (`001_mirror_sqlite.sql`) | Legacy migration artefact; EvercoatITWRD is PostgreSQL-native from migration 001 |
| `k8s/` | Owner docs explicitly say **do not introduce Kubernetes in the first implementation** |
| Anthropic SDK | Zero-cost rule forbids a mandatory paid AI API. Local Ollama only |
| Solar's `tenant_id`-only RLS **as-is** | **Carries the exact defect Codex flagged as BLOCKER F32.** See §3 |

---

## 3. The critical caveat — Solar's RLS is not sufficient here

Solar's RLS scopes to **`tenant_id` only**. Every row a tenant owns is visible to every user of that tenant.

For Solar that is correct: a solar installer's staff may all see that company's projects.

**For EvercoatITWRD it is not.** Codex F32 (BLOCKER) established that organization-level RLS with project scope left to application code makes the "three independent layers" claim false — a Chemist inside the organization who is not on project RDP-019 would be protected from another team's formulations by FastAPI code alone. One missing dependency on one route exposes proprietary formulations to a colleague. Concept Note §36 requires *"role-based and **resource-level** access controls"*.

**So the reuse is: take Solar's mechanism, extend its policy.**

- Keep: the GUC helper, the 4-part phased migration, parallel-run permissiveness, the deferred `FORCE` cutover, idempotency, the same-file-to-both-environments discipline.
- Change: `tenant_id` → `organization_id`; add a **second GUC** `app.current_user_id`; add **project-membership predicates** to every policy on project-scoped tables; add `security_barrier` views for the analytics surface; add formula-confidentiality classification.
- Add, which Solar did not need: **composite tenant-qualified foreign keys** with `UNIQUE (id, organization_id)` on every parent (Supervisor S7), because referential integrity bypasses RLS even under FORCE.
- Add: **transaction-scoped `SET LOCAL`** with pooled-connection reset and **fail-closed when context is absent** (Codex F34). Solar's `apply_tenant_guc(conn)` is the right shape; the fail-closed behaviour and pool-reset discipline must be explicit in SQLAlchemy.

Reusing Solar's RLS without this extension would import the project's single highest risk rather than retire it.

---

## 4. Stack after reuse — what changed in the owner-doc stack

The owner docs remain authoritative. Three substitutions, each justified:

| Layer | Owner doc | Adopted | Why |
|---|---|---|---|
| Background worker (pre-Temporal) | hand-rolled polling worker | **Celery on Valkey** | Proven in Solar; Valkey is Redis wire-compatible, so the pattern ports unchanged. Still behind `WorkflowPort`; Temporal still arrives at Slice 11 for the named durable workflows |
| PDF generation | WeasyPrint | **`markdown-pdf`** | WeasyPrint is **not installed** on this machine and neither are pandoc, wkhtmltopdf or reportlab. `markdown-pdf` is the operator's proven toolchain. Jinja2 + python-docx + OpenPyXL unchanged |
| Audit immutability | append-only triggers | **SHA-256 hash chain** (R2) | Strictly stronger — tamper-*evident*, not merely tamper-*resistant*, and independently verifiable from both PostgreSQL and Python |

Everything else in the owner-doc stack stands unchanged: Next.js, React, TypeScript, Tailwind, shadcn/ui, Radix, TanStack Table/Virtual/Query, React Hook Form, Zod, Apache ECharts, FastAPI, Python, Pydantic, SQLAlchemy, Alembic, PostgreSQL, pgvector, Keycloak, Garage, Valkey, Ollama, Sentence Transformers, Docling, PyMuPDF, NumPy, SciPy, Pandas, Polars, statsmodels, pyDOE3, Optuna, scikit-learn, SHAP, MLflow, Pytest, Hypothesis, Vitest, Playwright, axe-core, Locust, Bruno, Trivy, Semgrep, Gitleaks, SOPS+age, Caddy, Docker Compose.

---

## 5. What this buys

| Plan risk | Before | After |
|---|---|---|
| **Risk 1 — tenancy/authorization** (top risk) | Unproven design, most expensive possible rewrite | Proven mechanism + a scoped, well-understood extension |
| Codex **F22** — audit immutability only asserted | Design intent | Shipped SOC-2 hash chain |
| Codex **F34** — connection-pool context leak | Identified, unsolved | `apply_tenant_guc` pattern exists; needs fail-closed + pool reset |
| Codex **F43** — observability too late | Slice 20 | Structured logger + Prometheus available at Slice 1 |
| Supervisor **S7** — composite FK needs unique index | Would have failed the first migration | Two-step `NOT VALID` → `VALIDATE` pattern available |
| Schedule (Risk 2) | Every foundation piece greenfield | Foundation materially de-risked; the **Slice 1 estimate drops meaningfully**, though §A's finding stands — the *domain* (formulation, testing, approvals, DOE, modeling) has no precedent in Solar and remains fully greenfield |

**Honest limit:** the reuse is concentrated in infrastructure — tenancy, audit, auth, logging, secrets, CI, worker, review harness. **None of the R&D domain is reusable.** Formulation, laboratory, the Test Module, approvals, failures, DOE, modeling, validation, stability, pilot, qualification and lifecycle are all still built from nothing, and they are where the bulk of the effort sits (Codex F40: the Test Module alone is 150–220 h). §A's greenfield conclusion is narrowed, not overturned.
