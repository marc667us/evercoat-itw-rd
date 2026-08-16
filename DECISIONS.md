# DECISIONS.md — EvercoatITWRD APP

Architecture Decision Records. One per material decision. Status: **Accepted** · **Provisional** · **Open** · **Superseded**.

---

### ADR-001 — Application name and workspace layout · Accepted
`EvercoatITWRD APP` (display + folder), slug `evercoat-itw-rd`, DB id `evercoat_itw_rd`.
The source amendment (L29,736–29,817) mandates it and forbids renaming. The operator's phrasing "ITW Evercoat RD App" was flagged, not adopted; reversal touches branding strings only. Workspace holds `ITERDRD App/` (read-only reference copies) beside `EvercoatITWRD APP/`, per the mandated layout.

### ADR-002 — AI orchestration framework: LangGraph vs Google ADK · **Open — operator decision required before Slice 8**
The source mandates LangGraph OSS five times, including master §36. The platform-wide house rule declares Google ADK the only permitted agent framework and asserts precedence on governance.
Working default is LangGraph, behind `AgentOrchestrationPort`. **Codex judges the port insufficient on its own**, naming ten leak paths: graph/state representation, checkpoint and resume semantics, tool schemas and invocation, streaming event formats, conversation persistence, human-in-the-loop interrupts, retry/error semantics, tracing metadata, agent handoff conventions, and framework state serialisation. It recommends ADK.
Mitigations adopted regardless of the answer: framework-neutral domain tools, application-owned conversation/event model, normalized streamed events, externalized checkpoints, contract tests runnable against either adapter. **Switching is a bounded migration, not a free swap** — which is why this must be decided before Slice 8, not discovered at Slice 12.

### ADR-003 — Apache ECharts for all application charts · Accepted
Blueprint §2 said "Recharts or Plotly"; stack §6 and master §15 say ECharts. Later + explicit wins. One `<ChartWrapper>`. Matplotlib/Plotly only for server-side static plots embedded in PDFs.

### ADR-004 — Garage for object storage, behind `ObjectStoragePort` · Accepted
Blueprint §6 said MinIO; stack §19 and master §36 say Garage. **Not claimed drop-in** — multipart, signing, versioning and retention differ between S3 implementations (Codex F7/C3). Garage ships in the **Slice 1** compose stack, not later, because Slice 3 delivers TDS/SDS/CoA and files may not live in database rows.

### ADR-005 — TanStack Table + Virtual; AG Grid forbidden · Accepted
AG Grid Enterprise is commercial and the zero-cost rule is mandatory. Reclassified after review from "contradiction" to "technology decision" — AG Grid was never a stated requirement.

### ADR-006 — Repository layout per the master amendment · Accepted
`apps/ services/ workers/ packages/ infrastructure/ tests/ docs/` supersedes Blueprint §9's `frontend/ backend/ database/`. Last statement in the source, stated as "must contain".

### ADR-007 — Test status is five stored axes with ordered derivation · Accepted
Supersedes Blueprint §29's single `pass_fail`, which structurally cannot express YELLOW.
Stored: `execution_status`, `validity_status`, `calculated_result`, `review_state`, `approval_state`. Derived and server-owned: `display_color`, `final_status`, `final_confirmed`.
Derivation is an **ordered algorithm, first match wins** — an unordered table produced two valid colours for the same record (Supervisor S3). `validity_status = invalid` short-circuits to RED and performance is not graded, because "technically invalid" is a RED cause distinct from failure (Codex F24).
Names are canonical. `approved_result`, `technical_status` and `calculated_status` are forbidden — the drift across four documents would have left a safety-critical field off the server-controlled blocklist under its real name (Supervisor S4).

### ADR-008 — Temporal deferred to Slice 11, for named workflows only · Accepted
The source both mandates Temporal for durable state and qualifies it as "where justified", and puts it in Phase 0 while allocating it zero hours. Resolved by naming ownership: stability time points, escalation timers, long-running qualification and announcement acknowledgement are Temporal-owned. Everything else stays transactional DB workflow permanently.
**Cutover is a migration, not an adapter swap** (Codex F41) — approval history, timers, signals, retries, idempotency and compensation semantics leak into the domain. Domain commands and events are modelled stably now so the leak is bounded.

### ADR-009 — Render is optional demo staging only · Accepted
The source itself states free Render PostgreSQL expires after 30 days and cannot hold R&D IP. Docker/Podman Compose is the deployment path. Render and Resend remain replaceable adapters, never architectural dependencies.

### ADR-010 — GitHub Actions, with CI logic in `scripts/*.sh` · Accepted
Forgejo Actions is the source's self-hosted default; the source explicitly permits GitHub as a convenience. Keeping logic in shell scripts makes the runner swappable. Reclassified after review from "contradiction" to "deployment choice". Repository hosting policy still to be confirmed with the operator.

### ADR-011 — Sixteen logical schemas, each justified · Accepted with condition
Master §37 says "such as" and is non-exhaustive, so the union is permitted. **Condition (Codex F23):** every schema declares an owner role, grants and dependency direction, or it is merged. Namespace count without ownership boundaries is complexity for nothing.

### ADR-012 — Six test authority levels · Accepted
Master §23 lists six; the Test narrative lists five, omitting `validation`. Six wins — `validation` is required because `VALIDATION_CONFIRMATION` is a distinct approval template.

### ADR-013 — MSD in MVP-1 over structured tool-calls; document RAG at Slice 8 · Accepted
Resolves a document-level contradiction Codex found and the first plan missed (F8): Concept Note §38 requires "knowledge retrieval and an initial MSD chatbot" **in the MVP**, while master §46 omits AI from MVP-1 and §47 assigns Knowledge/RAG to the follow-up build.
Neither has to lose. Eight of the nine mandated first-MSD capabilities — application guidance, formula retrieval, formula comparison, material lookup, test explanation, failure history, pending work, context navigation — are **structured queries over the digital thread the MVP already builds**. Only "R&D knowledge search" needs document ingestion and pgvector.
MVP-1 therefore ships MSD with a local Ollama runtime and structured tool-calls, with evidence links and the full authorization boundary. Document RAG stays at Slice 8.

### ADR-014 — Composite tenant-qualified keys and foreign keys · Accepted
RLS prevents cross-tenant *reads* but not cross-tenant *references* — referential integrity bypasses RLS even under FORCE (Codex F14).
Every tenant-scoped table carries `(id, organization_id)` as a composite candidate key and **declares `UNIQUE (id, organization_id)`**. That unique constraint is mandatory, not an optimisation: PostgreSQL requires a unique index on referenced columns, so without it the first composite-FK migration fails with *"there is no unique constraint matching given keys for referenced table"* (Supervisor S7). Slice 1 ships a migration test that fails if any tenant-scoped table lacks it.

### ADR-015 — `validity_status` separated from performance · Accepted
Master §24 puts "technically invalid" under RED. A blocking calibration, method or sample-integrity failure means there is no result to grade. Configuration key `test_method.calibration_breach_policy ∈ {invalidate, deviate}` — named, not implied, so it is implementable.

### ADR-016 — RLS enforces organization **and** project membership · Accepted · **supersedes the v1 three-layer claim**
Plan v1 asserted three independent layers where "any one failing must not expose data". **That was false** (Codex F32, BLOCKER): RLS scoped only to `organization_id`, so project confidentiality rested on application code alone, and one missing dependency on one route would expose a colleague's formulations. Concept Note §36 requires resource-level access controls, not organization isolation alone.
RLS now enforces both, via policies over a membership predicate plus `security_barrier` views for the analytics surface, with database-enforced formula-confidentiality classification. Materialized views carry their own `organization_id` and policies, since matviews do not inherit source RLS (Codex F20).
This is the project's **highest-risk decision** (Codex Q3) and is therefore settled before Slice 1, not after.

### ADR-017 — Five database roles · Accepted
`evercoat_owner` (DDL/migrations) · `evercoat_app` (runtime, non-superuser, FORCE RLS) · `evercoat_worker` · `evercoat_report` · `evercoat_breakglass` (audited, off by default).
Corrects v1, which wrongly required migrations to run as the runtime role — that needs DDL privileges it must not have (Codex F19). The genuine hazard v1 was groping at survives: migration **data backfills and orphan checks** are still validated against RLS semantics.

### ADR-018 — Approval templates versioned; route snapshotted onto each test · Accepted
Editing a template must never retroactively change what a live test required (Codex F28). At test release an immutable route instance is copied onto the test — mandatory/optional stages, parallel groups, ordering, role and person constraints.

### ADR-019 — Incompatible-duty rules name the excluded levels · Accepted
"The executor may not supply *all* approvals" is satisfiable by approving five of six on `RELEASE_CRITICAL`, and degenerates to "one other person clicks once" on `SCREENING_SIMPLE` (Codex F27, Supervisor S12). Replaced with explicit exclusions — at `qualification`/`release` authority the executor may supply **no** approval; at `validation`/`controlled` the executor may supply neither Level-1 review nor final approval; QA approval may never come from anyone who supplied a development-side approval; author ≠ final approver; `min_distinct_approvers` on the route template.

### ADR-020 — Release is a transactional command, not a declarative constraint · Accepted
The traceability invariant spans many tables and time, so it cannot be a check constraint (Codex F18). Release locks the relevant rows, evaluates an immutable evidence snapshot, records the qualification dossier version, freezes the full release snapshot — components, quantities, units, material revisions, calculations, specifications, procedures, documents, approvals (Codex F35) — and creates the released product atomically. Partial release is impossible by construction.

### ADR-021 — Administration is a thread through the build, not a slice · Accepted
Both plan versions said configuration was "editable in Administration" while no slice built it (Supervisor S8) — the operator's own most-repeated lesson turned on itself. Administration ships incrementally beside whatever first depends on it: users/roles/permissions at Slice 1, stage gates at 2, units/families at 3, test methods and approval templates at 5, notification templates at 7, AI config at 8, audit browser and feature flags at 20.
**Standing rule:** a configuration value referenced anywhere in the plan must have an Administration screen in the same slice or earlier, and the slice gate checks it.

### ADR-022 — Reuse Solar PV Designer Lite infrastructure; extend its RLS · Accepted
Full analysis in `REUSE.md`. Adopted: phased RLS migration pattern with GUC helper and deferred FORCE cutover · **SHA-256 audit hash chain** (supersedes the weaker "append-only triggers", and answers Codex F22 with shipped code) · two-step `NOT VALID` → `VALIDATE` foreign-key addition · Keycloak JWT verification via `python-jose[cryptography]` · tenant-aware structured JSON logging · Fernet-encrypted secrets at rest · Prometheus metrics · Resend adapter · **Celery on Valkey** as the Slice 1 `WorkflowPort` implementation · gated migration-apply workflows · the Codex review harness.
Rejected: Flask/Jinja (owner docs mandate Next.js + FastAPI) · Tkinter desktop auth windows · PV/BOQ domain code · SQLite mirror · `k8s/` (source forbids Kubernetes initially) · Anthropic SDK (zero-cost rule).
**Critical condition:** Solar's RLS is tenant-scoped only, which is exactly ADR-016's defect. Take the mechanism, extend the policy — reusing it unchanged would import this project's highest risk rather than retire it.

### ADR-023 — `markdown-pdf` for PDF generation · Accepted
WeasyPrint is named in the source but is **not installed** on this machine, and neither are pandoc, wkhtmltopdf or reportlab. `markdown-pdf` is the operator's proven toolchain. Jinja2, python-docx and OpenPyXL are unchanged.

### ADR-024 — Both schedules stated; the unit is not redefined · Accepted
Plan v1 silently re-based "Day N" to "Slice N". Codex correctly called that a fidelity change rather than a resolution (F39), since master §45 and the final amendment explicitly request 3-day and 14-day plans.
The mandated schedule (45 h MVP / 210 h full build) and an independent estimate (700–1,050 h for a hardened MVP-1) now stand side by side, with the source's own defer order available if scope must be cut: Infographics → Advanced Analytics → Product Modeling → Optimization → DOE → Stability → Lifecycle. **The MVP-1 core is never deferred.** The operator chooses.
