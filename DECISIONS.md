# DECISIONS.md — EvercoatITWRD APP

Architecture Decision Records. One per material decision. Status: **Accepted** · **Provisional** · **Open** · **Superseded**.

---

### ADR-001 — Application name and workspace layout · Accepted
`EvercoatITWRD APP` (display + folder), slug `evercoat-itw-rd`, DB id `evercoat_itw_rd`.
The source amendment (L29,736–29,817) mandates it and forbids renaming. The operator's phrasing "ITW Evercoat RD App" was flagged, not adopted; reversal touches branding strings only. Workspace holds `ITERDRD App/` (read-only reference copies) beside `EvercoatITWRD APP/`, per the mandated layout.

### ADR-002 — AI orchestration framework: **LangGraph OSS** · Accepted (operator decision, 2026-08-16)
**Decision: LangGraph OSS, as the source documents mandate.**

> **⚠ EXPLICIT, OPERATOR-GRANTED EXCEPTION TO PLATFORM GOVERNANCE.**
> `C:\Users\USER\CLAUDE.md` §0.1 (Agentic ADK Extension) declares Google ADK the **only** permitted agent framework across every app in this home folder, and states that root wins on platform-wide governance. **This project departs from that rule by explicit operator instruction.** It is recorded here loudly and deliberately, because the root file also says a project that *silently* contradicts a platform-wide rule is a defect. This is not silent.

**Basis.** The source documents mandate LangGraph OSS five times, including MASTER PROMPT §36, the zero-cost stack pass, and the explicit division of responsibility: *"Temporal owns durable R&D workflow state. LangGraph owns bounded AI reasoning."* The operator's standing instruction for this build is to follow the prompt in the files strictly, and — after being shown both the governance conflict and Codex's contrary recommendation — reaffirmed LangGraph directly.

**What was weighed and set aside.** Codex recommended ADK, reasoning that a platform-wide "only permitted framework" rule outranks a project technology preference and advising that an explicit exception be obtained first. That exception is exactly what this ADR records. Codex also judged the `AgentOrchestrationPort` **insufficient on its own**, naming ten leak paths: graph/state representation, checkpoint and resume semantics, tool schemas and invocation, streaming event formats, conversation persistence, human-in-the-loop interrupts, retry/error semantics, tracing metadata, agent handoff conventions, and framework state serialisation.

**That analysis stands and is acted on, not discarded.** Because the port is not a free swap, the leak paths are constrained deliberately:

- **Framework-neutral domain tools.** Every MSD capability is a plain Python function with a Pydantic signature in `app/agents/tools/`, callable and testable with no agent framework imported. LangGraph binds to them; it does not define them.
- **Application-owned conversation and event model.** Threads, turns, evidence links and tool invocations are our tables in the `ai` schema, not LangGraph checkpoint state. LangGraph state is derived from ours and is disposable.
- **Externalized checkpoints.** Persisted through our own store, so an interrupted MSD session survives a framework change.
- **Normalized streamed events.** The web client consumes our event shape, never LangGraph's, so the UI is unaffected by a framework swap.
- **Contract tests** run against the tool layer directly, independent of any orchestrator.

The consequence: if this exception is ever revisited, the migration is bounded to `app/agents/graphs/` rather than spreading through the domain, the API and the frontend.

**What is retained from the Agentic ADK Extension.** §0.1 is the only clause waived. The architectural discipline in §0.2 and §0.3 is genuinely framework-independent and is kept in full:

- **§0.2 — orchestration first.** A Root Orchestrator at `app/agents/orchestrators/root_orchestrator.py`, department Conductors at `app/agents/conductors/<dept>_conductor.py`, implemented as LangGraph graphs. **Specialists never call other agents. API routes never call specialists directly.** MSD is reached through the orchestrator.
- **§0.3 — reusability.** `pyproject.toml` + pip-installable; public API in `__all__`; no hardcoded paths in business logic; no cross-department imports between specialists; `docs/REUSABILITY.md` lists exports and consumers.

**Zero-cost rule is unaffected either way** — LangGraph OSS is Apache-2.0 and runs against local Ollama. No paid AI API becomes essential.

Flagged to the Supervisor gate as a governance exception, with the operator's instruction as its basis.

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

### ADR-024 — Build at full depth, gate by gate · Accepted (operator decision, 2026-08-16)
**Decision: every slice is built to the Definition of Done, in the source's dependency order. Nothing is cut. No calendar date is promised.**

Plan v1 silently re-based "Day N" to "Slice N". Codex correctly called that a fidelity change rather than a resolution (F39), since master §45 and the final amendment explicitly request 3-day and 14-day plans. Both numbers were therefore put side by side — the mandated 45 h MVP / 210 h full build, and an independent estimate of 700–1,050 h for a hardened MVP-1 — and the operator chose **full depth, gate by gate**.

Consequences, stated plainly so they are not rediscovered later:

- **A slice ships when its gate passes, not when a day ends.** The gate is the Definition of Done in `CLAUDE.md` §15 plus the four governance gates plus the feature exercised in a browser on the deployed instance.
- **The source's defer order is not used.** Infographics, Advanced Analytics, Product Modeling, Optimization, DOE, Stability and Lifecycle all remain in scope.
- **The 45-hour and 14-day figures are retained in the plan as recorded source requirements**, not as commitments. Reporting progress against them would be dishonest in both directions.
- **Depth is bought through reuse, not haste.** The shared component library and the Solar infrastructure reuse (ADR-022) are what make full depth reachable; if a later slice needs new approval, discussion, attachment, task, audit, notification or dashboard infrastructure, that is a defect in Slices 1–3, not new scope.
- **No slice is declared complete on a green build.** Type-checks, unit tests and a successful deploy have coexisted with features that never worked.

### ADR-025 — Sign-in is browser-side OIDC + PKCE, not next-auth · Accepted (2026-08-19)

**Decision: the web application authenticates with an OpenID Connect Authorization Code flow with PKCE, executed entirely in the browser against the existing public `evercoat-web` client. `next-auth` is removed.**

`TODO.md` scheduled S1 as "next-auth Keycloak provider in `apps/web`". That cannot work on the artefact this project deploys, and building it would have produced a green CI run and a deployed site with no sign-in — which is S1's own exit condition.

**The measurement.** `render.yaml:80` builds with `NEXT_OUTPUT=export` and publishes `staticPublishPath: out` — a Render **static site**. A static export has no server and no route handlers; there is no `apps/web/app/api/` directory at all. **NextAuth v5 requires server route handlers** (`app/api/auth/[...nextauth]/route.ts`) for its callback, session and CSRF endpoints. `next-auth@5.0.0-beta.25` was a declared dependency that nothing imported, in a build that could never have run it.

**The realm was already configured for the flow that does work.** `evercoat-web` is `publicClient: true`, `standardFlowEnabled: true`, carries `pkce.code.challenge.method: S256`, and holds the `evercoat-api-audience` mapper so its tokens are accepted by the API. The only thing pointing at next-auth was the redirect URI path. The realm did not need convincing; the plan did.

**Why this is architecturally sound here and not a compromise.** `CLAUDE.md` §6 already states that frontend permission checks are cosmetic and that every control is re-enforced server-side, and `get_principal` reads permissions from the database rather than from the token's claims. A public client that cannot keep a secret is therefore not holding one: the browser proves possession of a code verifier, and every authorization decision is made by the API against a token whose signature it verifies independently.

**The alternative was a Render web service, which is spend.** That is the operator's decision and is never proposed by the build. This route keeps the deployment on the free static tier.

Consequences, stated plainly:

- **The access token lives in memory only.** `lib/api/session.ts` already recorded this constraint before there was an implementation: `localStorage` is readable by any script on the origin, so one XSS becomes a stolen session that outlives the page. A reload therefore ends the in-memory session, and the user presses Sign in again -- which normally returns without a password prompt, because Keycloak's own SSO cookie is still valid. **No silent `prompt=none` check is performed.** This sentence originally said one was; it was never implemented, Codex caught the whole path as unreachable, and it is now deliberately declined rather than built: a hidden-iframe check depends on the realm cookie in a third-party context, which Safari blocks and Chrome is removing. A mechanism that works in development and quietly stops working for some users in production is worse than one that visibly asks.
- **The PKCE code verifier does go in `sessionStorage`, and that is not the same claim.** It must survive exactly one redirect, it is single-use, it is useless without the matching authorization code, and it is cleared the moment the exchange completes. Storing it is what makes the flow safe; storing the token is what would make it unsafe.
- **The redirect URI is a real page in the export** (`/auth/callback/`), not a route handler. The realm's `redirectUris` and `webOrigins` change with it, and must list every deployed origin — a static export cannot compute them at runtime.
- **`next-auth` is removed from `package.json`.** A dependency that is imported by nothing and cannot work in this build is a trap for the next reader, and it is the reason S1 was scheduled wrongly in the first place.
- **This does not by itself put sign-in on the deployed site.** Keycloak still has no public URL, because deploying it needs a web service. What this changes is that the blocker is now **one configuration value**, not an architecture, and the flow is provable in CI against the real Keycloak that already runs there.

### ADR-026 — Railway free tier replaces Render as this app's deployment target · 🔴 **SUPERSEDED BY ADR-027 (2026-08-21) — ITS PREMISE WAS FALSE**

> ⚠️ **Do not act on this ADR.** It was accepted on the belief that Railway has a free tier. Verified 2026-08-21 against Railway's own pricing: it does not. See **ADR-027** at the end of this file. Everything below is retained as the record of a decision that was made, not as guidance.

**Original heading:** Accepted (operator decision, 2026-08-20)

**Decision: Railway's free offering is the SELECTED TARGET for the API, PostgreSQL and Keycloak tiers of EvercoatITWRD APP; Render is retired as the target for this app. Nothing is deployed there yet — this ADR records the choice, not an accomplished migration.** Operator, 2026-08-20, verbatim: *"we replace render with railway free version for this app"*.

**This is a provider change, not an architecture change.** Every technical prerequisite already exists and none of it is Render-specific: `apps/api/Dockerfile`, `services/keycloak/evercoat-realm.json`, the Alembic migration chain, the seeder, and a CI suite that already proves all of it against a real PostgreSQL and a real Keycloak. What changes is where the containers run.

**Why — and it was measured, not assumed (I13).** `render-provision.yml` was run against the real Render API with the repository's `RENDER_API_KEY`. Render refused both halves, verbatim:

```
POST /postgres        -> 400  "cannot have more than one active free tier database"
POST /services free   -> 400  "free tier usage quota has been exhausted,
                               new services are not allowed"
```

🔴 **The key works — those are 400s, not 401s.** `GET /owners` returned 200. **A new or rotated key produces the identical errors.** The Render workspace is shared with AutoWorkshop and Solar and is full: five `standard` web services, `solarpro-postgres` on `basic_256mb`, and `autoworkshop-postgres` holding the single free database slot. This is a plan/billing boundary, and no amount of engineering on this repository moves it.

**What is NOT yet done, stated plainly so it is not mistaken for progress.** Nothing has been provisioned on Railway. The work has not started. It is blocked on one owner action:

- The Railway CLI on the dev host is **unauthenticated** — `railway whoami` → `Unauthorized` (v4.66.0, `C:/Users/USER/nodejs/railway`). It needs an interactive `railway login`, which only the owner can complete.
- There is **no `RAILWAY_TOKEN` repository secret**. `RENDER_API_KEY` remains the only one.

⚠️ **Verify the free allowance before provisioning anything.** Railway withdrew its perpetual free tier in 2023 in favour of a one-time trial credit, with a paid Hobby plan beyond it. Whether a genuinely free allowance exists on this account must be confirmed **at sign-in, before any resource is created** — not discovered afterwards. If it turns out to require payment, that is an owner decision under the standing zero-cost rule and must be surfaced, never assumed.

**Sequencing — do not retire Render early.**

1. The web front end stays on Render for now. It is a **static site**, it is unaffected by the quota that blocks the API, and `itwevercoatrd.aiappinvent.com` is already CNAME'd to it with a working certificate. Moving it is a separate decision with a DNS change attached, and there are no Namecheap credentials on this machine.
2. Provision Postgres → run `alembic upgrade head` → API service → Keycloak from the shipped realm, on Railway.
3. Only then rebuild the web tier with `NEXT_PUBLIC_API_BASE_URL` and `NEXT_PUBLIC_KEYCLOAK_URL` pointing at the Railway hosts. 🔴 **Both are BUILD-time** — setting them on a running service changes nothing.
4. Keep `render-audit.yml` and `render-provision.yml` in the repository until Railway is serving. They are read-mostly and `render-provision.yml` has no DELETE path. Retire them in the same commit that proves the Railway deploy live.

**Supersedes ADR-009** ("Render is optional demo staging only") only as to which provider hosts this app's runtime tiers. ADR-009's substantive point — that the deployed instance is demonstration staging and not production — is unchanged.


---

### ADR-027 — Railway is rejected on the zero-cost rule; Render is retained under a measured ceiling · Accepted 2026-08-21

**Supersedes ADR-026.**

**Decision: Railway is NOT a viable target for this app. ADR-026 is reversed.** Its
premise — that Railway offers a free tier — is false.

**What was verified, 2026-08-21, against Railway's published pricing:**

* **$5 of one-time credit, valid for 30 days.** A trial, not a tier.
* After it expires, a Free plan with **$1 of credit per month**.
* Anything beyond a single lightweight service **with no database** requires
  **Hobby at $5 per month minimum**.

EvercoatITWRD APP needs three runtime tiers and a PostgreSQL database. Under
Railway the trial is exhausted inside a month and the account then bills. That
violates rule 7 of the seven non-negotiables and the platform-wide zero-cost
rule. **ADR-026 was never zero-cost compliant** — the error was accepting a
provider's marketing word "free" without checking what it expires into.

**A second, independent disqualifier.** Railway requires an interactive
`railway login` and a `RAILWAY_TOKEN`, both of which only the operator can
produce. The operator's standing rule of 2026-08-21 is that **no task may be
assigned to them**. A path whose first step is an owner action is not a path.

**What was measured on Render the same day**, with the repository's own key:

```
POST /services  plan=free   -> 400  "free tier usage quota has been exhausted,
                                     new services are not allowed"
POST /postgres  plan=free   -> 400  "cannot have more than one active free
                                     tier database"
```

Both are **400s, not 401s**; `GET /owners` returns 200. This is a capacity and
plan boundary, not authentication. Rotating the key changes nothing.

🔴 **The ceiling is structural, not temporal.** The instance-hour quota resets
monthly, but the free-database limit is **one per workspace**, and
`autoworkshop-postgres` holds it until it expires 2026-09-01 — at which point a
live AutoWorkshop needs it back. **Evercoat can obtain a free Render database
only by taking the slot another running application depends on.** Waiting for
the reset does not solve this; it only changes who is broken.

**Consequence, stated plainly rather than softened:** under strict zero-cost
with no owner action, **there is no provider on which this app's API and
Keycloak can be deployed today.** The web tier stays on Render as a static site
with a working certificate on `itwevercoatrd.aiappinvent.com`.

**The best alternative measured, for when that constraint changes:** **Coolify
(open source) on Oracle Cloud Always Free** — permanent, 4 ARM cores, 24 GB RAM,
200 GB disk, no deploy cap, no sleep, no cold start. It would hold the API,
Keycloak, PostgreSQL and pgvector at once and would outlive the AutoWorkshop
database expiry. It costs exactly one signup, which is why it is recorded here
rather than actioned. Caveats: Oracle's ARM capacity is frequently unavailable
by region, and the API image would need an ARM or multi-architecture build.

Full compliance matrix — every option scored against zero cost, no card, no
owner action, and support for an iterative deploy loop — is in
`Desktop\Evercoat-Hosting-Options-2026-08-21.pdf`.

**Do not restart the Railway path.** If a future session finds ADR-026 and not
this ADR, that is the failure mode this record exists to prevent.

---

### ADR-028 — an email address is an attribute, not a global key · Accepted 2026-08-25

**Closes I83.** Implemented by migration 046 (`f1000`).

**Context — measured, not assumed.** `core.users.email` was CITEXT carrying
`users_email_key`, a **globally unique** constraint. Unique constraints are
enforced **outside row-level security**: the index is consulted whatever the
reader may see. Measured as `evercoat_app` scoped to organization A, against an
address belonging to a member of organization B:

```
INSERT INTO core.users (keycloak_sub, email, display_name)
VALUES ('throwaway', 'victim@competitor.example', 'throwaway');
  -->  REFUSED by "users_email_key"        --> POST /api/admin/members answers 409

... the same statement with an address nobody holds:
  -->  ACCEPTED                            --> the route answers 201
```

So a holder of `admin.users` in **any** tenant — including a self-service one —
read platform-wide existence from a status code, with a throwaway subject and no
row left behind, repeatable without limit. **Emails are guessable where a subject
UUID is not.** The same run confirmed the squatting half: organization A can
pre-insert a junk identity holding a competitor's address, after which
organization B can never onboard that person.

**Decision: drop `users_email_key`. Identity is `keycloak_sub`; email is an
attribute mirrored from the identity provider.** One-address-per-organization is
enforced instead by a SECURITY INVOKER constraint trigger on
`core.organization_members`.

**Why not the alternative — a definer plus one indistinguishable 409.** It was on
the table and it does not work, and the evidence is in the record rather than in
an argument: **migration 044 had already made that refusal generic**, and the
oracle survived. It survived because the attacker does not read the message; they
read **201 against 409**, and no wording closes that gap while a globally enforced
constraint decides which one they get. A creating endpoint cannot make "created"
indistinguishable from "not created". That option also leaves the squatting path
completely untouched.

**A global unique constraint on an attribute is a cross-tenant channel by
construction, not by accident.** §5 already says every code is tenant-scoped and
that a globally unique batch number "would stop Org B creating LB001 because Org A
has one — and the constraint violation itself discloses another tenant's record".
`core.users.email` was the same rule, unnoticed because `core.users` is not
tenant-keyed.

**The stated cost did not exist.** `TODO.md` recorded that dropping the constraint
"reaches messaging/service.py's @mention resolution, which matches on the local
part of core.users.email". Measured: that query matches `split_part(email,'@',1)`
and the constraint is on the **whole address**, so it never protected it. Two
members of one organization at `chris@one.example` and `chris@two.example` — both
always permitted — already returned 2 rows into a `.one_or_none()`, a **latent 500
on posting a message**, independent of this ADR and fixed in the same commit. An
ambiguous handle now resolves to nobody, because notifying the wrong person is
worse than an unresolved handle.

**The replacement is deliberately not a SECURITY DEFINER.** It refuses a write
based on rows it can read; as a definer it would read every tenant and refuse on
what it found there, rebuilding the oracle inside a trigger. As an invoker it sees
only what the writing role may see — within one organization, every member — so it
does not miss in practice, and where RLS does hide a row it passes silently rather
than answering. **Prefer a guard that can miss inside your own tenant over one that
can answer across tenants.** `tests/db/test_046` asserts `pg_proc.prosecdef` is
false, because a comment claiming INVOKER proves nothing.

**Consequences.**

* Two identities may now hold the same address. That is the point, and Keycloak —
  where identity lives — is where realm-wide address uniqueness belongs.
* One organization still cannot hold the same address twice among **active**
  members. Scoped to active so offboarding somebody does not lock their address
  out of the tenant.

  🔴 **CORRECTED AFTER REVIEW — the first version of this ADR claimed that
  and the code did not implement it, two ways.** Codex found both; both were
  then measured rather than argued about.

  **(a) A trigger that decides by SELECT is not a unique index.** Under READ
  COMMITTED neither of two concurrent transactions sees the other's
  uncommitted row, so both `EXISTS` came back empty and both committed —
  measured on two connections, two active members of one organization ended
  up holding the address. `pg_advisory_xact_lock` on (organization, address)
  is the mechanism that makes the claim true; the second writer waits, then
  sees the committed row and is refused. Same pattern as `audit.chain_row()`
  in migration 013, for the same reason.

  **(b) The address lives on `core.users`, and the trigger was on
  `core.organization_members`.** `evercoat_app` holds UPDATE on `core.users`
  and 044's policy admits a user sharing your organization, so
  `UPDATE core.users SET email = <a colleague's address>` was accepted and no
  membership row moved. Measured: accepted, two active holders. On that path
  046 was briefly **weaker than the constraint it removed**, because
  `users_email_key` covered updates too. A second trigger,
  `users_address_stays_unique_in_organization`, closes it. **A rule enforced
  on INSERT and not on UPDATE is a shape this repository has shipped before.**

  What remains, stated rather than glossed: both guards are SECURITY INVOKER,
  so they enforce within organizations the writer can see and **miss** a
  collision in an organization they cannot. That is the deliberate trade —
  missing inside your own tenant beats answering across one — and it is a
  weaker guarantee than a unique index, not an equal one.
* `POST /api/admin/members` gained a second, distinguishable 409: "another active
  member of this organization already uses that email address". Naming it is safe
  **here** and was not safe before, because `list_members` already shows this
  caller every member of their own organization with their address. That is the
  whole difference between this message and the constraint being removed.
* **The downgrade can legitimately fail** and says so, naming the duplicate
  addresses. It will not delete user records to make a constraint fit.
* I81 and I82 are unchanged by this and still stand.

---

### ADR-029 — an authentication identifier is not a readable column, and a guard's tenant scope must be its own predicate · Accepted 2026-08-25

**Closes I81.** Hardens ADR-028's rename guard. Implemented by migration 047 (`f2000`).

**Context.** 044's read policy admits a user when the reader shares an
organization with them, with no `status` filter — deliberately, because eleven
INNER joins resolve an actor through `core.users` and filtering would drop the
*records* from every list rather than merely blanking a name. The objection
recorded as I81 was that those joins need only the NAME while the policy hands
over the whole row, including `email` and `keycloak_sub`.

🔴 **The objection was measured, not accepted, and it was only two-thirds
right.**

| column | readers | verdict |
|---|---|---|
| `display_name` | all eleven joins | attribution — correct |
| `email` | **two production paths that deliberately return it** — `admin.list_members`, and `projects.list_members`, which documents that it lists FORMER members on purpose because "who has ever had access" is the question asked after an incident. Messaging also matches on its local part. | has real consumers; removing it would break stated behaviour |
| `keycloak_sub` | **none. No application query selects it anywhere.** | over-granted |

**Decision: revoke SELECT and UPDATE on `core.users.keycloak_sub` from
`evercoat_app`, `evercoat_report` and `evercoat_worker`.** RLS is row-level and
cannot express "the name but not the identifier"; column privileges can. INSERT
keeps the column, because `invite_member` creates identities and that is the one
path that legitimately sets it. UPDATE goes because no production code updates
`core.users` at all, and rewriting a subject would repoint an existing row at a
different identity — an identity swap performed by the runtime role.

⚠️ **A column-level REVOKE against a table-level GRANT does nothing.**
PostgreSQL treats `GRANT SELECT ON core.users` as covering every column, so
`REVOKE SELECT (keycloak_sub)` on top of it is silently ineffective. The
table-level grant is dropped and replaced by an explicit column list. A
migration written the other way reads exactly like this one and changes nothing.

The three functions that DO read the column — `principal_for_subject`,
`memberships_for_subject`, `user_id_for_subject` — are SECURITY DEFINER owned by
`evercoat_owner`, so sign-in is unaffected. That is an argument, so it is also a
test: `test_047` resolves a real subject as `evercoat_app` after the revoke.

**Consequence, found by the test suite rather than by reasoning.** 044's
cross-tenant upsert test uses `ON CONFLICT (keycloak_sub)`, whose inference
clause needs SELECT on that column. It is now refused by privilege *before* RLS
is consulted — a stronger refusal, and **a reduction in what that test proves**,
since a boundary it can no longer reach is not exercised by it. The RLS half is
now asserted separately on a plain `UPDATE display_name`, which 047 leaves
granted: 0 rows cross-tenant, 1 row inside your own organization.

---

**And a second finding, from measuring I82 rather than I81.**

I82 proposes folding subject resolution into "a single atomic bind so the id is
returned only after the membership exists". The obvious implementation is a
SECURITY DEFINER. **Measured before building it, and it would have re-opened
I83.**

ADR-028's two guards are SECURITY INVOKER so they cannot answer for another
tenant. But `deny_duplicate_address_in_organization` scopes itself
(`om.organization_id = NEW.organization_id`) while
`deny_address_collision_on_rename` did **not** — its `mine` side was restricted
only by the RLS policy on `core.organization_members`. A trigger runs as
whatever the current user is, and inside a definer owned by the table owner that
user bypasses RLS while FORCE is off. Same data, both paths:

```
INVOKER path  : ACCEPTED  <- tenant-scoped, correct
DEFINER path  : REFUSED   <- refused on organization B's row
```

The refusal then discloses that the address exists somewhere — I83's oracle,
rebuilt inside the guard that replaced it, by any future definer that writes to
`core.users`.

🔴 **Check which mechanism is load-bearing before a comment credits one.** RLS
was doing the scoping and ADR-028 credited the INVOKER choice. Both were true;
only one survives being wrapped. 047 makes the predicate explicit, so the scope
travels with the function rather than with the caller's role — and it is equally
correct under the FORCE RLS cutover of I56/I58, which would otherwise have
changed this behaviour a third time.

**I82 remains open**, and its proposed design is now recorded as rejected on
evidence rather than left to be discovered by whoever builds it.
