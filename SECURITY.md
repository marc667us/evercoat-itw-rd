# SECURITY.md — EvercoatITWRD APP

**Threat premise.** This system holds proprietary chemical formulations, experimental history, supplier terms, failure knowledge and product-development strategy. That data *is* the company's competitive position. It is more valuable than the software, and it is permanently damaging if leaked — a formula cannot be rotated like a password.

Every control below exists to serve one goal: **proprietary formulation IP is protected at the backend and database layers, never by hidden frontend controls.**

---

## 1. Defence in depth — three independent layers

```
Keycloak            identity, role, session, token
      ↓
FastAPI             permission → resource scope → business rule
      ↓
PostgreSQL          Row Level Security on organization_id
```

**Design requirement: any one layer failing must not expose data.** A bug in a FastAPI dependency must still hit RLS. A misconfigured Keycloak mapping must still hit permission checks.

---

## 2. Authentication

- **Keycloak** provides login, logout, SSO, OAuth 2.0, OpenID Connect, JWT, refresh tokens, password policy, optional MFA, session management and identity federation.
- The API validates JWTs against the realm's published JWKS. **Signature, issuer, audience and expiry are all verified.** Never trust an unverified claim.
- Access tokens short-lived; refresh handled by the web app; refresh token rotation enabled.
- No local password storage in the application database. Keycloak owns credentials.
- Service-to-service calls (workers → API) use a dedicated confidential client, not a human user's token.

## 3. Authorization

Enforced in order, on every request:

```
Authentication → Organization → Role → Permission → Resource Scope → Business Rule
```

- **Authorize on permissions, never on role names.** `project.create`, `project.assign_member`, `formula.create`, `formula.modify_draft`, `formula.submit`, `formula.approve_lab`, `test.execute`, `test.review`, `test.confirm`, `failure.close`, `product.release`, and so on. Role→permission mapping is data, editable in Administration.
- **Resource scope** is a separate check from permission. Holding `test.review` does not grant review of a test in a project you are not a member of.
- **Business rules are the last gate** and are not expressible as permissions: a released formula cannot be edited by anyone; a technically passing test cannot go GREEN with approvals outstanding; the executing user cannot supply all mandatory approvals on a qualification/release test.
- **Segregation of duties** is enforced server-side for high-authority confirmation tests.

### Frontend permission checks are cosmetic
Hiding a button is a usability feature, not a security control. Every action is re-authorized server-side. **Playwright tests attempted unauthorized access** — direct API calls and direct URL navigation — not merely that a control is invisible.

Required negative tests (`tests/e2e/rbac/`):
- Chemist cannot release a product.
- Engineer cannot modify an approved master formula.
- Lead cannot bypass a Director-required gate.
- A user in Organization A cannot read Organization B's project — by URL, by API, or by search.
- A released formula cannot be overwritten.
- Formula percentages outside configured tolerance cannot be submitted.
- A user removed from a project loses access to its future messages.
- **MSD boundary test** — see §7.

## 4. Organization isolation and Row Level Security

- Every proprietary table carries `organization_id`, directly or through a mandatory parent.
- **`ENABLE ROW LEVEL SECURITY` *and* `FORCE ROW LEVEL SECURITY`** on those tables.
- **The application connects as a non-superuser role** (`evercoat_itw_rd_app`). Superuser bypasses RLS, so developing as superuser hides exactly the defects RLS exists to catch.
- Migrations, backfills, orphan checks and analytics refreshes must be written to run **under that role**. A migration that only works as superuser is a latent production failure.
- The test suite runs a dedicated RLS suite under `SET ROLE evercoat_itw_rd_app`.
- **Referential integrity bypasses RLS even under FORCE.** RLS answers reachability for reads, not for references — so foreign keys into tenant-scoped tables must be composite, carrying `(id, organization_id)`, to stop a cross-tenant reference being creatable through an FK.
- Analytics views and materialized views are **also** RLS- and project-membership-scoped. No chart may aggregate records the viewer cannot open.
- **Channel confidentiality reaches the messages, not only the channel row** (migration 025). `messaging.messages` carried an organization-only policy while `messaging.channels` carried the project predicate, so the words were less protected than the room they were said in. See §17.

### 🔴 Open gap — the database is not yet independently fail-closed

`core.rls_permissive()` is still `SELECT TRUE` (migration 001). Every
policy in this database is written as

```sql
USING (core.rls_permissive() AND core.current_org_id() IS NULL
       OR organization_id = core.current_org_id())
```

so **when no request context is set, every policy opens completely.** The
only thing standing between that and a cross-tenant read is
`session_scope()` in `app/core/db.py`, which raises `MissingContextError`
rather than proceeding.

That is one layer, and §1 of this document requires that any *one* layer
failing must not expose data. Today the application layer is not a
backstop for the database layer — it is the *sole* enforcement whenever
the GUC is absent.

It is deliberate scaffolding, not an oversight: the seeder, the
migrations and the backfills all run with no GUC set and would stop
working the moment it flips. Flipping it is the **FORCE-RLS cutover**,
which needs its own migration and its own review — `tests/db/test_024_memberships_for_subject.py`
already fails the moment it lands, and says what to do. Until then, treat
"RLS protects it" as **true only for requests that went through
`get_db`**, and never as a reason to relax an application-layer check.

## 5. Session and token management

> **AS BUILT, 2026-08-19 (ADR-025).** This section described a
> cookie-based session. **No cookie is issued anywhere in this
> application.** The deploy is a Next.js static export with no server and
> no route handlers, so the browser runs OIDC Authorization Code + PKCE
> itself and holds the access token **in memory only** — `apps/web/lib/api/session.ts`.
> `sessionStorage` holds the PKCE **verifier** and never the token
> (`apps/web/lib/auth/flow-state.ts`).
>
> The bullets below are kept because they are the requirement the moment a
> server-side session exists, and §9's CSRF rule depends on which of the
> two is true. Do not read them as a description of today.

- Tokens in memory / httpOnly secure cookies. **Never in `localStorage`.**
- `Secure`, `HttpOnly`, `SameSite=Lax` (or `Strict` where flows allow).
- Idle and absolute session timeouts configured in Keycloak.
- Logout revokes the refresh token at Keycloak, not just client-side.
- Organization switching re-issues context and **re-validates by navigation**, never by in-place revalidation of a stale page.

## 6. Formula confidentiality and document access

- Formula components, percentages and cost are permission-gated fields, not merely hidden columns. Cost is visible only with `formula.view_cost`.
- **Attachments are served exclusively through short-lived signed URLs.** No public object URLs, no guessable paths. Garage buckets are private.
- Every document fetch is authorized against the parent record and **audited**.
- Uploads are validated: extension **and** content sniffing, size caps, filename sanitisation, and storage under generated keys rather than user-supplied names. Archives and executables rejected. Files stored in object storage, never in database rows.
- Documents are versioned; a message linking "SDS RM-014 Revision 4" must keep pointing at Revision 4 after the document is revised.

## 7. AI access boundaries — MSD

**MSD operates under exactly the calling user's authorization boundary.** If the user cannot open Formula F100 through the application, MSD must not retrieve, summarize, infer or expose F100 through chat.

The rule that makes this real: **filter before retrieval, never after generation.** Post-hoc filtering is not a control — the model has already seen the data and can leak it through paraphrase, aggregation or inference.

- Every retrieval tool takes the caller's principal and applies the same permission + scope + RLS path as the REST API. Tools do not have their own database credentials.
- Vector search is filtered by `organization_id` and project membership **in the query**, not after ranking.
- Every AI output passes: Pydantic schema validation → permission validation → evidence check → human review where controlled.
- MSD cannot approve a test, change a controlled formula, move a result from YELLOW to GREEN, confirm a root cause, or release a product.
- Natural-language analytics compiles to a **governed** query builder. Never free-form SQL.
- Prompt-injection posture: retrieved document content is untrusted input. Tool invocation is never driven by text found inside a retrieved document, and tool arguments are schema-validated before execution.
- **No essential dependency on an external AI API** — proprietary formulations never leave the organization's infrastructure. This is a security property first and a cost property second.

## 8. Server-controlled fields

Separate Pydantic schemas per operation — `FormulaCreate`, `FormulaUpdateDraft`, `FormulaRead`, `FormulaSubmit`, `FormulaApprovalRequest`, `FormulaVersionCompare` — so that server-owned values are structurally unreachable from a client payload:

`approved_by` · `approval_date` · `locked_at` · `release_status` · `final_status` · `display_color` · `audit_user` · `organization_id` · every timestamp · every issued code.

Mass-assignment from a generic "update" schema is forbidden.

## 9. Input validation and injection defence

- **SQL injection:** SQLAlchemy parameterised queries only. No string-built SQL. The one dynamic-query surface — the Analytics Center — uses a whitelisted metric/dimension/filter builder, never user-supplied fragments.
- **XSS:** React escapes by default; `dangerouslySetInnerHTML` is banned outside a single audited, sanitised markdown renderer. Messaging content is sanitised server-side on write and escaped on render.
- **CSRF — READ THIS WHOLE BULLET BEFORE CHANGING THE TOKEN TRANSPORT.**

  **Claimed state:** "a double-submit token is mandatory on every state-changing request, unconditionally."

  **Measured state, 2026-08-20:** there is **no CSRF implementation anywhere in this repository.** The only occurrence of the string is `X-CSRF-Token` in the CORS `allow_headers` list at `apps/api/app/main.py:91` — a header the API permits and never verifies. So the paragraph below was describing a control that does not exist, which is worse than describing none: it reads as "handled".

  **Is it exploitable today? No — and not for the reason the old text gave.** CSRF requires the browser to attach the credential *automatically*. This application issues no cookie at all (§5, ADR-025); the access token lives in JavaScript memory and is attached explicitly as an `Authorization: Bearer` header by `apiRequest`. An attacker's page can cause the browser to issue a cross-site `POST`, but it cannot make it carry that header, and it cannot read the victim's memory to obtain one. There is nothing ambient to ride.

  **So the rule is conditional on a fact, and the fact is what must be watched:**

  > 🔴 **The moment ANY credential becomes ambient — a session cookie, HTTP Basic, TLS client certs, or a `SameSite=None` cookie of any kind — a double-submit CSRF token becomes mandatory on every state-changing request, and shipping the ambient credential without it is a defect.**

  The reasoning that was correct in the old text, and still is: **CORS is not a CSRF defence.** The browser still *sends* the cross-origin request; CORS only stops the attacker reading the *response*, which is irrelevant when the goal is the state change itself. `SameSite=Lax` is defence in depth, not the control. State-changing operations are never `GET`.
- All input validated twice — Zod on the client for UX, **Pydantic on the server for truth.** Client validation is never load-bearing.
- Database constraints are the final backstop: check constraints on ranges and enums, unique constraints, NOT NULL, NUMERIC precision.

## 10. Rate limiting and abuse

> 🔴 **NOT IMPLEMENTED. THIS IS A GAP, NOT A DESCRIPTION.**
> Measured 2026-08-20: there is **no limiter, throttle or quota of any
> kind** in `apps/api` — no middleware, no dependency, no Valkey counter.
> `grep -ri "rate.limit\|slowapi\|limiter" apps/api/app/` returns nothing.
> Raised independently by Codex and by the audit's own route sweep.
> Tracked as **I18** in `TODO.md`.
>
> **Why it was not built in the same change as the other fixes.** The
> limit's *key* is the whole control. This API is intended to sit behind
> Caddy (§13), so `request.client.host` is the proxy for every caller —
> one bucket for the entire internet, which fails closed on the first
> burst and takes the application down. Trusting `X-Forwarded-For`
> instead lets an attacker mint an unlimited number of keys and defeats
> the limit entirely. Choosing correctly requires knowing the deployed
> topology — how many proxy hops, which are trusted — and **that is a
> deployment decision, not a code decision.** A limiter keyed wrongly is
> worse than none: it converts an abuse control into a self-inflicted
> outage or a placebo. It is recorded as open rather than half-built.
>
> **Mitigating context, stated so the risk is not overstated either.**
> The API is not deployed anywhere today (`TODO.md` I13/B4): the live
> artefact is the static web export, and every API route requires a
> Keycloak-signed token plus organization membership resolved from the
> database on **every** request. There is no anonymous write path and no
> anonymous read path. The exposure is authenticated abuse and cost, not
> disclosure.
>
> **What closing it requires:** the trusted-proxy decision above, then
> per-subject and per-IP buckets, tighter limits on writes, and `429`
> with `Retry-After`. Enforce at Caddy **as well**, so a limit exists
> even when a request never reaches the application.

The requirement, unchanged:

- Valkey-backed rate limits per user and per IP on: authentication, search, MSD/AI endpoints, report generation, exports and file uploads.
- AI inference is separately throttled and queued — it is the most expensive endpoint and the easiest to weaponise.
- Bulk export of formulas or test results is permission-gated **and** audited as a distinct high-sensitivity event.

**Bounded collections (done 2026-08-20).** Not a rate limit, but the
adjacent failure it prevents: every collection endpoint now caps its
result set at 200 rows in SQL. `GET /api/projects` and
`GET /api/opportunities` returned every visible row and were the only two
that did not.

## 11. Audit logging

`audit.events` is **append-only**: no `UPDATE`, no `DELETE`, unreachable from ordinary application paths, revoked at the role level for the app user.

Each event records: organization · user · role · action · entity type · entity id · previous state · new state · reason · timestamp · session/IP metadata.

Audited actions include: formula creation, revision, submission and approval; test result entry, correction and approval; failure closure; root-cause acceptance; stage transitions; qualification; product release; role and permission changes; document access; bulk export; and every MSD action that touched controlled records.

### Logging security
Logs must never contain formula compositions, component percentages, secrets, tokens or full request bodies from formulation endpoints. Log identifiers and outcomes, not payloads. Loki retention is bounded.

## 12. Secrets management

- **SOPS + age.** Encrypted configuration may be committed; plaintext secrets never may.
- **Gitleaks in CI**, and in pre-commit.
- Never in Git: database passwords, Keycloak client secrets, signing keys, encryption keys, object-storage keys, SMTP/Resend credentials.
- Rotation procedure documented in `DEPLOYMENT.md`; rotation does not require a code change.
- *Operator note:* PowerShell pipelines add a UTF-16 BOM. Write secret files with explicit UTF-8 or the secret silently becomes invalid.

## 13. Transport and production configuration

- **TLS everywhere**, terminated at Caddy with automatic certificates. HTTP redirects to HTTPS.
- HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and a Content-Security-Policy without `unsafe-inline` scripts.
- Only web, api and Keycloak are exposed. **PostgreSQL, Valkey, Garage, the AI runtime and (later) Temporal stay on the internal network** and are never published to the host in production compose.
- `DEBUG=false`, no stack traces to clients, generic error bodies with a correlation id.
- Default credentials changed at provisioning; the Keycloak admin console is not publicly reachable.

## 14. Backup protection

- Scheduled `pg_dump` plus Garage snapshots, **encrypted at rest**, with retention policy and offsite copy.
- **Restore is tested, not assumed** — an untested backup is not a backup. Restore drill is part of the Slice 20 hardening gate.
- Backups contain the company's entire IP; they are protected at least as strictly as production.
- Keycloak realm configuration is backed up alongside the database.
- *Note:* `pg_dump` under FORCE RLS as a non-superuser will silently omit rows it cannot see. The backup role and its policies are explicitly configured and the dump's row counts are verified against source counts.

## 15. Security testing

Automated, in CI:

| Tool | Scope |
|---|---|
| **Gitleaks** | committed secrets |
| **Semgrep Community** | static analysis of Python + TypeScript |
| **Trivy** | container images, OS packages, Python and Node dependencies |
| **Pytest** | permission matrix, business-rule enforcement, RLS under `SET ROLE` |
| **Playwright** | attempted unauthorized access, cross-organization isolation, MSD boundary |
| **axe-core** | accessibility (a correctness requirement, and status-by-colour-alone is a defect) |

A high-severity Trivy finding blocks staging deployment. `/security-review` runs as part of the Supervisor gate.

## 16. Incident posture

- Correlation ids on every request, propagated through OpenTelemetry, so an incident can be reconstructed from the audit trail plus traces.
- The audit trail is the authoritative record of who did what; logs are supporting evidence.
- Suspected formula exposure is treated as an IP incident: identify affected records via the document-access audit, not by guesswork.

---

## 17. API security audit — 2026-08-20

Reviewers: **Codex CLI** (independent, read-only, full `apps/api` sweep),
the **Supervisor** (`/security-review`), and **CodeRabbit CLI 0.7.5**.
Raw Codex output: `reviews/codex-api-security-2026-08-20.md`.

Neither reviewer alone was sufficient, for the ninth session running:
Codex found the metrics-cardinality defect and the JWT expiry gap and
missed the messaging boundary entirely; the route sweep found the
messaging boundary and the reverse-proxy mismatch, which Codex did not
raise.

### Fixed in this pass

| # | Severity | Defect | Fix |
|---|---|---|---|
| **A1** | 🔴 High | **Any organization member could read any channel's messages.** `messaging.messages` carried an organization-only RLS policy while `messaging.channels` carried the project predicate, and `list_messages` filtered by `channel_id` **without ever joining `channels`** — so the channel's protection was not weaker, it was never consulted. Restricted-project conversations and other people's **direct messages** were both readable by anyone holding a channel id. 022's own comment said direct messages are "governed by channel membership instead"; that governance existed only inside the `list_channels` listing query. | Both layers. `list_messages` and `post_message` now join `messaging.channels` and apply the membership predicate; migration **025** adds `core.can_read_channel()` and a `channel_scope` policy on `messaging.messages` plus `parent_message_scope` on `messaging.message_links`. Six tests in `tests/db/test_025_message_visibility.py`, one of which bypasses the service and asks PostgreSQL directly. |
| **A2** | 🔴 High | **Unbounded Prometheus label cardinality, anonymously reachable.** The access-log middleware read `request.scope["route"]` *before* `call_next`, and Starlette's router is what writes that key — so the `request.url.path` fallback fired on **every** request. `/api/projects/<uuid>` minted one time series per project, and an anonymous caller could mint unlimited series with `/whatever/<nonce>`. The line's own comment claimed it did the opposite. | `_metric_label()`, called after `call_next`; unrouted requests collapse into `<unmatched>`. Three tests, verified to fail against the prior mechanism. |
| **A3** | 🟠 Medium | **A signed token with no `exp` was accepted, and never expired.** `verify_exp` validates an `exp` that is present; `require_exp` is what makes its absence a failure, and it defaults to `False`. Measured against python-jose 3.5.0. | `require_exp` and `require_sub` added to the decode options. Two tests, verified to fail against the prior options block. |
| **A4** | 🟠 Medium | **The reverse proxy stripped a prefix the API expects.** `handle /api/*` did `uri strip_prefix /api` while FastAPI mounts every router under `/api` — so **every API route would have 404'd through Caddy**. Unnoticed because CI talks to uvicorn directly and the full compose stack has never been up at once. As a side effect `/api/metrics` reached the API's **unauthenticated** Prometheus endpoint from the internet, contradicting the file's own comment. | `strip_prefix` removed; `/metrics` refused at the edge with `respond 404`. Four tests in `tests/test_reverse_proxy_contract.py` pin the two files together. |
| **A5** | 🟠 Medium | `GET /api/projects` and `GET /api/opportunities` returned every visible row. | Hard SQL `LIMIT 200`, matching every other collection. |

### Open, and why

| # | Item | Status |
|---|---|---|
| **§10** | **No rate limiting of any kind.** | Open — see §10. Blocked on a trusted-proxy decision that is a deployment choice, not a code choice. `TODO.md` **I18**. |
| **§4** | **`core.rls_permissive()` is still `SELECT TRUE`.** | Open by design — the FORCE-RLS cutover. See §4. |
| **§9** | CSRF token absent. | **Not currently exploitable**: no ambient credential exists. Becomes mandatory the moment one does. See §9. |

### Verified working, not merely asserted

JWT algorithm pinned to RS256 with signature, issuer and audience all
checked · permissions read from the database on every request rather than
trusted from token claims, so revocation is immediate · transaction-local
RLS GUCs with `DISCARD ALL` on pool checkin · no string-built SQL
anywhere · dynamic permissions (`material.status`, `batch.review`,
`test.decisions`) enforced in the handler because the required permission
depends on the payload · OpenAPI and `/docs` disabled in production ·
wildcard CORS refused in production · generic error bodies with a
correlation id · request bodies never logged.

**Not run in this pass:** the database-layer tests
(`tests/db/test_025_message_visibility.py`) require PostgreSQL, and Docker
on the development host is wedged. They are written, they compile, and
**CI is their first execution** — that is stated rather than reported as a
pass.

### Second round — the audit's own fix was reviewed adversarially

Migration 025 was then handed to a reviewer whose instruction was to
**refute** it. The parse, the absence of policy recursion, the strictly-
tightened tenant boundary and the `WITH CHECK` behaviour on
`message_links` all held. Two things did not, and both were in the same
blind spot:

**025 tightened the `USING` side of `messaging.messages` and left the
`WITH CHECK` side of the two tables its predicate READS at
organization-only.** `evercoat_app` holds `GRANT SELECT, INSERT, UPDATE
ON ALL TABLES IN SCHEMA messaging`, so the predicate could be fed a
different answer rather than defeated:

| # | Attack | Closed by |
|---|---|---|
| **H1** | **Self-enrolment.** Insert your own `messaging.channel_members` row for somebody else's direct channel; `core.can_read_channel()` then answers TRUE. Channel ids are not secret — the `channels` policy deliberately shows every `direct` row organization-wide. | A `channel_scope` policy on `channel_members` whose `WITH CHECK` demands that the writer can already read the channel **or** created it. |
| **H2** | **Retyping.** `UPDATE messaging.channels SET channel_type = 'announcement'` takes the non-direct branch of the predicate and exposes the whole conversation to the organization. Nothing made `channel_type` immutable and no route updates the table at all. | Trigger `channels_keep_their_scope`: `channel_type`, `project_id`, `organization_id` and `created_by` cannot change. |

🔴 **The reviewer's own proposed fix for H1 would have broken direct
messages entirely.** "You may only add a member to a channel you can
already read" cannot bootstrap: a `WITH CHECK` subquery does not see the
row the same command is inserting, so the creator's first membership row
is refused and no direct message can ever be created. The shipped policy
admits the channel's `created_by` instead — set from the authenticated
actor, made immutable by H2's trigger, and not something a stranger
looking at someone else's conversation can satisfy.
`test_the_creator_can_still_open_a_direct_channel` is the test that tells
the two versions apart.

**Neither attack is reachable over HTTP.** `create_channel` is the only
writer of `channel_members` and inserts only for a channel id it
generated itself; no route updates `channels`. They are database-layer
gaps — which is the entire point, because that layer exists to answer
what happens when the application layer is bypassed.

**A third, larger hole was found and deliberately NOT fixed** — see
`TODO.md` **I20**. `projects.project_members` has a `USING` clause and no
`WITH CHECK`, so PostgreSQL reuses `USING`, which is organization-only.
Self-enrolment there defeats `core.is_project_member()` and therefore
**every project-scoped policy in the database at once**. It is not
reachable over HTTP either. It is left open because the obvious fix has
the same bootstrap problem as H1 and `projects.projects` has **no
`created_by` column** to escape through — it needs a live database to
design against, and Docker on this host is wedged. Fixing core tenancy
blind is how this platform has broken production before.
