# Review Pass 1 — Codex findings and Supervisor adjudication

**Artifact under review:** `IMPLEMENTATION_PLAN.md` DRAFT v1 (commit `116cc64`)
**Codex Reviewer:** codex-cli 0.147.0, ChatGPT Plus auth, read-only sandbox, full source read
**Codex verdict:** **FAIL** — 43 findings, 5 BLOCKER
**Date:** 2026-08-16

Every Codex finding was verified against the source documents before ruling. Reviewers are not oracles; three findings are overturned or narrowed below. The great majority are upheld, and several are materially better than what the plan had.

Ruling key: **UPHELD** · **UPHELD (narrowed)** · **OVERTURNED** · **ESCALATED**

---

## The five BLOCKERs

### F1 / F8 / F42 — Initial MSD + knowledge retrieval belong in MVP-1 · **UPHELD**

Verified. Concept Note §38 (L858) lists the MVP contents and ends: *"...audit history, **knowledge retrieval, and an initial MSD chatbot**."* L860–878 then names what the first MSD must do: application guidance · R&D knowledge search · formula retrieval · formula comparison · material lookup · test-result explanation · failure-history retrieval · pending-work queries · context-aware navigation.

Plan v1 (C13) reduced this to "application-guidance mode only… no LLM weights". That is a genuine fidelity violation. Codex is right.

**Codex also found the contradiction the plan missed (F8)**, and it is real: Concept Note §38 puts initial MSD in the MVP, while Master Prompt §46 (MVP-1 SCOPE, L29,474) omits AI entirely and §47 (FOLLOW-UP, L29,503) explicitly assigns "Knowledge/RAG" to the second build.

**Adjudication — the resolution is better than either side's.** Codex framed this as "pick the Concept Note"; the plan framed it as "pick the Master Prompt". Neither is necessary, because the two documents are only in conflict if MSD is assumed to require RAG. It does not. Of the nine mandated first-MSD capabilities, **eight are structured queries over the digital thread the MVP already builds** — formula retrieval, comparison, material lookup, test explanation, failure history, pending work, navigation, guidance. Only *"R&D knowledge search"* requires document ingestion and pgvector.

**Ruling:** MVP-1 ships MSD with a local Ollama runtime and structured tool-calls over controlled records, with evidence links and the full authorization boundary. **Document RAG (Docling/pgvector/embeddings) stays in Slice 8.** This satisfies Concept Note §38 and Master §47 simultaneously. Recorded as **ADR-013**.

### F14 — Tenant integrity is not enforced relationally · **UPHELD**

Verified and correct. `organization_id` + RLS prevents *reading* across tenants; it does **not** prevent a foreign key from *referencing* across tenants, because referential integrity checks bypass RLS even under FORCE.

Notably, `SECURITY.md` §4 already stated this ("RI bypasses RLS… foreign keys must be composite") while `IMPLEMENTATION_PLAN.md` §F did not. **The plan was internally inconsistent with its own security document** — exactly the class of defect this review exists to catch.

**Ruling:** composite tenant-qualified keys `(id, organization_id)` with composite FKs on every child→parent link in the thread. Plan §F amended. **ADR-014.**

### F24 — Technically invalid results can be marked YELLOW · **UPHELD (narrowed)**

Verified. Master §24 (L28,723): *"RED — Failed requirement or technically invalid."* The plan's matrix routed expired calibration to "YELLOW/RED by policy" and excessive variability always to YELLOW.

Narrowing: Codex overstates slightly on calibration. L17,399 says *"A result generated using an invalid calibration may automatically become yellow or red depending on severity"* — so severity-graded is the source's own position. But Codex's structural point is correct and better than the plan's: **validity is a separate axis from performance.** A test that is *invalid* has no performance result to grade.

**Ruling:** introduce `validity_status ∈ {valid, minor_deviation, invalid}`. Blocking method/calibration/sample-integrity failures ⇒ **RED — INVALID**. Only assessable, non-blocking concerns remain YELLOW. **ADR-015.**

### F32 — Organization RLS does not satisfy resource-level authorization · **UPHELD — and this is the most important finding in the review**

Verified. Plan §J claimed three layers where *"any one layer failing must not expose data."* **That claim is false as designed.** RLS scopes to `organization_id` only. A Chemist inside the organization who is not a member of project RDP-019 is protected from it by FastAPI code alone. One missing dependency injection on one route exposes another team's formulations to a colleague — and Concept Note §36 (L828–840) requires *"role-based and resource-level access controls"*, not organization isolation alone.

**Ruling:** add database-enforced project-membership and formula-confidentiality policies (RLS policies over a membership predicate, plus `security_barrier` views for the analytics surface). The three-layer claim is corrected in both `SECURITY.md` and the plan rather than quietly dropped. **ADR-016.** This is also Codex's answer to Q3 and I agree with it — see §Q3 below.

### F39 / F40 — Re-basing "Day" to "Slice" is itself a fidelity change · **UPHELD**

Codex accepts that the schedule is not credible but objects — correctly — that silently redefining the unit is not a resolution. Master §45 (L29,449) and the final amendment (L29,853) explicitly ask for a 3-day MVP and a 14-day plan.

Codex's independent estimate for a hardened MVP-1: **700–1,050 engineering hours** (~5–8 weeks for four experienced engineers; 18–26 working weeks solo), versus the source's 45 hours.

**Ruling:** stop redefining the unit. The plan now carries **both**, explicitly labelled: the mandated 3-day/14-day schedule as specified, *and* an honest independent estimate beside it, with the gap stated plainly for the operator to decide. Slices keep the source's day numbering and ordering. What a slice cannot do is be declared complete on a green build.

---

## Findings overturned or narrowed

### F3 — "The role merge collapses distinct governance functions" · **OVERTURNED (substance already satisfied)**

Codex's recommended fix is *"model capabilities independently… a combined default role may be seeded, but the authorization/data model must not assume they are one actor."* **That is already the plan's design** — §B states authorization is by permission, not role name, and roles are data-driven permission sets. Merging two *seeded realm roles* does not merge their *capabilities*.

The legitimate residue is F12's independent-person requirement, which is upheld separately. Plan wording clarified so the distinction is not readable as a capability merge.

### F37 — "§J omits refresh tokens, CSRF, upload scanning, rate limiting, TLS, log redaction, backup encryption" · **OVERTURNED in part, one real gap**

Codex reviewed §J of the plan — a ten-point summary — and not `SECURITY.md`, which covers every item listed: sessions/refresh (§5), CSRF (§9), upload validation (§6), rate limiting (§10), TLS and headers (§13), log redaction (§11), backup encryption and tested restore (§14).

**One item is genuinely absent and is upheld: SSRF.** Document ingestion via Docling/PyMuPDF may fetch remote URLs; nothing in the design constrains that. Real gap, added to `SECURITY.md`.

### F7 (C4, C15, C16, C17) — "these are not contradictions" · **UPHELD**

Correct, and a fair criticism of the register's construction. AG Grid (C4) was never a stated requirement; Forgejo-vs-GitHub (C15) is explicitly permitted by the source; the schema list (C16) says "such as" and is non-exhaustive; the 8→18 pipeline (C17) is deliberate staged refinement, not drift.

**Ruling:** the register is rebuilt in four labelled classes — **true contradictions** · **deliberate staged refinement** · **renames/relabels** · **ordinary architecture decisions**. Conflating them overstated the reconciliation work and obscured the ones that mattered.

---

## Findings upheld without qualification

| # | Finding | Consequence |
|---|---|---|
| F2, F4 | Test module "maximum depth" contradicted by deferring mandated behavior to Slice 9 | Publish an explicit MVP test-capability table; anything in Master §23/26/46 stays in Slice 5 |
| F5, F6 | Laboratory + QA dashboards and the 13 named reports never enumerated | Enumerate both, with source records and delivery slice |
| F9 | Two distinct test navigation models — module-level vs entity-context — only one captured | Implement both; document the reconciliation |
| F10, F30, F31 | GREEN is authority-ambiguous; a screening pass must not read like confirmed evidence | Status is authority-qualified: `GREEN — Screening Passed (preliminary authority)`. Display automatic evaluation and final disposition as separate fields |
| F11 | "Critical RED opens a failure" vs "confirmation RED opens a failure" | Configure by purpose × authority × criticality × deviation class; no single global RED rule |
| F12, F27 | Segregation of duties too weak — executor could still supply a key approval | Configurable incompatible-duty rules: executor≠reviewer, author≠final approver, QA≠development approver, distinct-person counts, no self-approval, delegation controls |
| F13, F41 | Temporal ownership ambiguity; conversion is a migration, not an adapter swap | Name which workflows must be Temporal-owned; model stable domain commands/events; treat cutover as a migration |
| F15 | `lab_batch_number` / `sample_number` globally unique | Tenant-scope both |
| F16 | "NUMERIC everywhere" is necessary but scientifically incomplete | Measurement model gains: canonical unit, entered unit, precision, significant figures, uncertainty, qualifier (`<`, `>`, ND), instrument resolution, method revision, conversion provenance |
| F17 | Blanket RESTRICT prevents deletion, not illegal transitions or historical mutation | Transition constraints + immutable link snapshots on approved components, methods, criteria, samples, qualifications, releases |
| F18 | Release traceability cannot be a declarative constraint | Transactional release command: lock rows, evaluate an immutable evidence snapshot, record dossier version, create the product atomically |
| F19 | Migrations must not run as the runtime app role | Separate owner/migrator · runtime · worker · reporting · break-glass roles. Runtime tests exercise FORCE RLS; DDL runs as a controlled owner |
| F20 | Materialized views do not inherit source RLS | Materialize `organization_id` + scope dimensions, apply RLS to the matview, refresh under a controlled role, test cross-tenant aggregates |
| F21 | Numbering lacks concurrency and revision semantics | Numbering-policy table, atomic allocator, uniqueness by tenant/type/year, immutable issued-number ledger, document identity separate from revision identity |
| F22 | Audit immutability asserted, not enforced | DB triggers / append-only procedures; revoke UPDATE/DELETE from runtime roles; tamper evidence |
| F23 | 16 schemas without ownership boundaries | Define owners, grants and dependency direction — or reduce the count |
| F25, F26 | "Approvals complete" as a boolean cannot express awaiting review, returned, conditional, retest requested, escalated | Publish a state dictionary and transition table; derive display from a state machine, not three columns |
| F28 | Approval templates unversioned — editing a template retroactively changes what a live test required | Version templates; snapshot an immutable route instance onto each test at release |
| F29 | Improvement tests do not fit PASS/FAIL | Separate outcome vocabulary (Improved / No Significant Change / Worsened) from traffic-light disposition |
| F33 | MSD boundary underspecified across derived data | Carry authorization provenance through chunks, embeddings, caches, conversation memory, tool outputs, model datasets; recheck at retrieval and at source-open; purge derived artifacts on revocation |
| F34 | Connection-pool tenant-context leakage — the classic RLS failure | Transaction-scoped `SET LOCAL`, reset pooled connections, fail closed when context absent, forbid user-controlled session variables, test cross-request tenant switching |
| F35 | Released-formula immutability does not cover indirect mutation | Freeze a full release snapshot: components, quantities, units, material revisions, calculations, specifications, procedures, documents, approvals |
| F36 | Server-controlled fields protected only at DTO level | Enforce via domain commands + DB constraints/triggers; deny direct column updates to runtime roles |
| F38 | Signed URLs outlive revocation | Very short expiry, audience/object binding, download audit, revocation strategy, authorization-checking download proxy for formulations |
| F43 | Observability arrives at Slice 20 but a deployed-instance gate exists from Slice 1 | Health checks, structured logs, metrics, error tracking, backup + restore smoke test move to Slice 1 |

---

## Codex's three direct answers

**Q1 — LangGraph vs Google ADK.** Codex judges the `AgentOrchestrationPort` abstraction **insufficient on its own**, and lists ten leak paths: graph/state representation, checkpoint and resume semantics, tool schemas and invocation, streaming event formats, conversation persistence, human-in-the-loop interrupts, retry/error semantics, tracing and evaluation metadata, agent handoff conventions, and serialization of framework state. It recommends **Google ADK**, on the reasoning that a platform-wide "only permitted framework" rule outranks a project-level technology preference, and that ADK can satisfy every functional requirement the source states — advising that an explicit exception be obtained before choosing LangGraph.

**Adjudication: ESCALATED — operator decision, unchanged.** But Codex's leak analysis materially changes the stakes and is accepted: the port makes switching a **bounded migration, not a free swap**, so this must be decided **before Slice 8**, not discovered at Slice 12. Mitigations adopted regardless of the answer: framework-neutral domain tools, an application-owned conversation/event model, normalized streamed events, externalized checkpoints, and contract tests runnable against either adapter.

**Q2 — Greenfield.** Codex confirms the conclusion and says the plan **underestimates the consequences**: no tested domain invariants, no validated calculation routines, no established authorization model or Keycloak configuration, no UI components or accessibility baseline, no CI, no seed data, no golden fixture — and, sharply, that *synthetic data cannot validate scientific correctness.* **Upheld.** The plan adds a calculation-verification strategy, test-method configuration validation, and a requirements→acceptance traceability matrix, and records that subject-matter review by an actual formulation chemist is required before any calculation is trusted in production.

**Q3 — Highest-risk decision.** Codex names the authorization and tenancy model — organization-level RLS with resource scope left to application code. **Agreed, and adopted as the plan's stated top risk.** If it is wrong, every table, analytics view, materialized view, search index, MSD retrieval path, cache, document link and model dataset needs retrofitting, and by Slice 12 the wrong assumption is embedded across DOE, RAG, modeling, reporting and workflow history. It is simultaneously the most expensive rewrite and the most serious IP-exposure risk. This is why F32 and F14 are fixed **before** Slice 1 rather than after.

---

## SUPERVISOR VERDICT: **FAIL** — Codex verdict upheld

`IMPLEMENTATION_PLAN.md` v1 must not proceed to build.

**Upheld:** 40 of 43 findings, including all five BLOCKERs.
**Overturned or narrowed:** 3 — F3 (substance already met), F37 (partially; SSRF gap real), F24 (narrowed on calibration severity).
**Escalated to operator:** 1 — LangGraph vs ADK.

**Required before Slice 1 may start**

1. MSD + structured knowledge retrieval restored to MVP-1 (F1/F8/F42).
2. Composite tenant-qualified keys and FKs specified (F14).
3. Project-membership and formula-confidentiality enforced **at the database layer**; the three-layer claim corrected (F32).
4. `validity_status` separated from performance status; the traffic-light matrix rebuilt as a state machine (F24/F25/F26).
5. Approval-template versioning and route snapshotting (F28); incompatible-duty rules (F27).
6. Both schedules presented honestly side by side; no silent redefinition of the unit (F39/F40).
7. Reconciliation register rebuilt in four labelled classes (F7).
8. Observability, health checks and a restore smoke test moved into Slice 1 (F43).
9. SSRF control added for document ingestion (F37 residue).
10. Operator decision on LangGraph vs ADK captured in `DECISIONS.md` before Slice 8.

Codex earned its keep on this pass. F32 and F14 in particular would each have become an expensive retrofit, and F8 found a document-level contradiction the first pass missed entirely.

---

# Part 2 — Supervisor independent review

Run separately, on the committed baseline, **not** shown Codex's findings first. That independence is the point: memory records six consecutive sessions where Codex missed what the Supervisor found and vice versa. It held again — **9 of 13 findings are new**, and three of those survive into v2.

Findings are numbered **S1–S13**. All are upheld; five overlap Codex and were already fixed in v2.

| # | Finding | Status |
|---|---|---|
| **S1** | **The stack table's "Slice introduced" column contradicts the slice plan.** It listed Garage=2, NotificationService=3, pgvector/LangGraph/Ollama=4, Reports=6, DOE=8, Observability=14, while §H/§I say Slice 2=Projects, 3=Formulations, 4=Laboratory, 8=Knowledge/RAG, 12=DOE, 20=Observability. An engineer starting Slice 4 (Laboratory) would read the table and provision pgvector + Ollama + LangGraph **inside MVP-1** — precisely the inversion §G calls non-negotiable. The column had been written against §G's *module* numbering, a third scheme colliding with "Slice N" everywhere else | **NEW — fixed.** Column rebuilt against §H/§I, with an explicit note that §G is a dependency graph and never a schedule |
| **S2** | MSD/RAG placed at "Slice 4" in one place and Slice 8 in another, while both escalation deadlines say "before Slice 8" and "everything up to Slice 7 is unaffected". If Slice 4 really pulled in LangGraph, the unresolved framework conflict would block MVP-1 and the risk register's central mitigation would be false under its own plan | **NEW — fixed.** ADR-013 settles it: MSD at Slice 7 over structured tool-calls, document RAG and LangGraph at Slice 8 |
| **S3** | **The traffic-light matrix derives two different colours for the same test.** A passing, fully-approved, no-deviation result with a low margin matches both `Pass\|Yes\|None → GREEN` and `Pass, low margin\|Any\|Any → YELLOW`. Same for the excessive-CV and adverse-trend rows, also `Any/Any`. Since `display_color` is purely derived, the API and the UI could legitimately disagree. Related: "YELLOW/RED by policy" named no configuration key anywhere, so it was not implementable | **NEW — fixed.** Replaced by a 14-step ordered algorithm, first match wins, RED predicates before all YELLOW. Config keys now named: `test_method.calibration_breach_policy`, `method.cv_limit`, `requirement.warning_threshold`, `method.trend_rule` |
| **S4** | **Three different column names for the same safety-critical decomposition** across four files — `calculated_status`/`technical_status`/`final_status` in one, `calculated_result`/`approved_result` in another, `final_status` protected in a third, `final_confirmed` in a fourth. The repo's own "two literals in two files cannot be type-checked into agreement" trap, applied to the single most safety-critical column set. A field absent from the server-controlled blocklist **under its actual name** is client-settable | **NEW — fixed.** Five canonical axes fixed in ADR-007 and propagated to `CLAUDE.md`; `approved_result`, `technical_status`, `calculated_status` explicitly forbidden |
| **S5** | **`CONTEXT.md` claimed `MEMORY.md` and `DECISIONS.md` had been created. They had not.** Five further documents were cross-referenced but never written, and the Definition of Done required updating `MEMORY.md`/`CHANGELOG.md`/`TODO.md` on day one — unsatisfiable | **NEW — fixed.** `MEMORY.md`, `DECISIONS.md` and `REUSE.md` now exist; `CONTEXT.md` gains an explicit "still to create" row so forward declarations cannot masquerade as reality again |
| **S6** | `lab_batch_number` and `sample_number` globally unique while every other code is tenant-scoped — Org B cannot create `LB001` because Org A has one, and **the constraint violation itself discloses another tenant's record** | Overlaps Codex F15; already fixed in v2. The cross-tenant *inference channel* is the Supervisor's addition and is the sharper reason |
| **S7** | **The composite-FK rule was unimplementable as written.** PostgreSQL requires a unique index on referenced columns, so composite FKs need `UNIQUE (id, organization_id)` on every parent — which appeared in no constraint list. The first migration following the rule fails with *"there is no unique constraint matching given keys for referenced table"*, and the predictable reaction under time pressure is to drop the composite FK, which is the exact defect the rule exists to prevent | **NEW — fixed.** `UNIQUE (id, organization_id)` is now a mandatory column of the table-creation checklist, with a Slice 1 migration test that fails if any tenant-scoped table lacks it |
| **S8** | **No slice delivered the Administration module**, yet role→permission mapping, test methods, stage gates and units were all described as "editable in Administration", and the sidebar shipped an Administration entry. Seeding a Keycloak realm is not a write path. This is the operator's own most-repeated lesson — *ask of every role: which production path **writes** it?* — reproduced inside the plan | **NEW — fixed.** ADR-021: Administration is a thread across Slices 1, 2, 3, 5, 7, 8, 20, with the standing rule that any configuration value must have an Administration screen in the same slice or earlier |
| **S9** | **The "ignore the second messaging copy" instruction deleted the head of a different section.** The duplicate ends at L21,329; *Updated MVP Build and Follow-Up Full Build Plan* begins at **L21,330**, inside the range marked as discardable — and §A compounded it by claiming that section starts at 21,336. Applying R1 as written drops that section's title and opening paragraph: the text mandating dashboards as **core MVP components** rather than a later reporting feature, which is the justification for Slice 7's dashboards | **NEW — fixed.** Boundary corrected in §A and §C, with the consequence stated |
| **S10** | "Ten concatenated passes" followed by a fifteen-item enumeration with mismatched section counts. Since §A is the provenance record the whole reconciliation register cites, an inconsistent inventory undermines the "later supersedes earlier" arbitration rule | **NEW — fixed.** §A rebuilt as a fifteen-row table with verified anchors. *(The Supervisor spot-checked nine individual line anchors — 18455, 19887, 23803, 25622, 29736, 16528, 5045, 9108 — and found all accurate, so this was a summary error, not bad sourcing.)* |
| **S11** | **CORS listed as the CSRF control**, and the CSRF token made conditional on a cookie flow that §5 already mandates as primary. CORS is not a CSRF defence — a cross-origin form `POST` is still *sent* with cookies; CORS only blocks reading the response, which is irrelevant for state change. As written, an implementer could conclude CSRF tokens were optional | **NEW — fixed.** Double-submit token mandatory and unconditional; `SameSite=Lax` demoted to defence in depth, with its top-level-POST gap noted |
| **S12** | Segregation of duties satisfiable by the executor approving five of six levels; on the two-step screening route it degenerates to "one other person clicks once" | Overlaps Codex F27; fixed in v2 by naming the excluded levels |
| **S13** | **`AttachmentManager` is a Slice 1–3 shared component and Slice 3 delivers TDS/SDS/CoA, but no MVP slice provisioned object storage** — the stack table said Garage at Slice 2, §I said Slice 8, and the Slice 1 compose stack listed none. Meanwhile `SECURITY.md` forbids files in database rows. Slices 3–7 would ship material documents with no permitted storage backend | **NEW — fixed.** Garage joins the Slice 1 compose stack (ADR-004) |

**Cleared on inspection:** the source line anchors throughout §A/§D are accurate (nine verified against `ITWRD App.txt`); the 16-schema list is consistent between `CLAUDE.md` and the plan; the `.gitignore` negation `!.env.example` works correctly against `.env.*`.

---

## Combined outcome

| | Codex | Supervisor | Total |
|---|---:|---:|---:|
| Findings | 43 | 13 | 56 |
| BLOCKER | 5 | — | 5 |
| Unique to that reviewer | 39 | 9 | — |
| Upheld | 40 | 13 | 53 |
| Overturned / narrowed | 3 | 0 | 3 |
| Escalated to operator | 1 | 0 | 1 |

**Neither reviewer alone was enough — seventh consecutive session.** Codex found the tenancy BLOCKER (F32), the relational tenant-integrity gap (F14) and the Concept-Note/Master-Prompt contradiction the plan missed entirely (F8). The Supervisor independently found the unimplementable composite-FK rule (S7), the missing Administration write path (S8), the ambiguous traffic-light precedence (S3), the drifting status column names (S4) and a status file asserting files that did not exist (S5). There is no meaningful overlap in what each caught alone.

**Plan v3 addresses all 53 upheld findings.** One item remains open by design: ADR-002, the LangGraph-vs-ADK decision, which is the operator's to make and is required before Slice 8.
