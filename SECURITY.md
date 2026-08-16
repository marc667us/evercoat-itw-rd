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

## 5. Session and token management

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
- **CSRF: a double-submit token is mandatory on every state-changing request, unconditionally.**
  An earlier draft said "the API is token-authenticated and CORS-restricted to known origins", with a CSRF token only for "any cookie-based flow". **Both halves of that were wrong.** CORS is not a CSRF defence — the browser still *sends* a cross-origin form `POST` with cookies attached; CORS only stops the attacker reading the *response*, which is irrelevant when the goal is the state change itself. And §5 mandates httpOnly `SameSite=Lax` cookies, so the cookie-based flow **is** the primary path, not a hypothetical one. As written, an implementer could reasonably conclude CSRF tokens were optional.
  `SameSite=Lax` is defence in depth, not the control: it does not cover top-level cross-site `POST` in older browsers. State-changing operations are never `GET`.
- All input validated twice — Zod on the client for UX, **Pydantic on the server for truth.** Client validation is never load-bearing.
- Database constraints are the final backstop: check constraints on ranges and enums, unique constraints, NOT NULL, NUMERIC precision.

## 10. Rate limiting and abuse

- Valkey-backed rate limits per user and per IP on: authentication, search, MSD/AI endpoints, report generation, exports and file uploads.
- AI inference is separately throttled and queued — it is the most expensive endpoint and the easiest to weaponise.
- Bulk export of formulas or test results is permission-gated **and** audited as a distinct high-sensitivity event.

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
