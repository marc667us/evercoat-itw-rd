# TODO — EvercoatITWRD APP

**Updated 2026-08-20, tip `bc156da`. CI 5/5 GREEN. S1 + S2 BUILT and DEPLOYED. Live suite 25/0/2 against the current build.** Read `RESUME_HERE.md` first.

---

## 0. Blocking — do these before anything else

| # | Task | Why it blocks |
|---|---|---|
| ~~B1~~ | ~~Read the `bash -x` trace in the Auth job.~~ | ✅ **CLOSED 2026-08-19.** A literal `\n` became a bare word `n`, which curl read as a second URL — exit 6, status `204000`. Four more defects sat behind it. **Auth is now green: passed=7 failed=0 skipped=0.** |
| ~~B0~~ | ~~Decide S1's auth architecture.~~ | ✅ **CLOSED 2026-08-19 — ADR-025.** Browser-side OIDC Authorization Code + PKCE against the existing public `evercoat-web` client. next-auth removed: it needs server route handlers and this deploys as a static export. |
| ⚠️ **B4** | **Render's push webhook is not firing. A manual lever now exists.** | `render-audit` reports the service correct — `autoDeploy: yes`, `branch: master`, right repo, not suspended — and it had not deployed since **2026-08-18T20:09:24Z**. Every commit for a day and a half was un-deployed while CI went green. **Fixed for now by `.github/workflows/deploy-web.yml`** (`gh workflow run "Deploy web (manual)"`), which resolves the service BY NAME, refuses unless it finds exactly one `evercoat-itw-rd-web`, issues one POST, waits for a terminal state, and then proves the edge changed. Ran it: the site now serves `last-modified: 2026-08-20 00:50:31 UTC` and `/auth/callback/` answers **200**. 🔴 **The ROOT CAUSE is still open** — the webhook. That is a dashboard action (reconnect the GitHub integration) and therefore the operator's. Until then every deploy must be triggered by hand. **Never** use `render-setup.yml` apply mode to force one: it DELETEs AutoWorkshop custom domains. |
| 🔴 **B5** | **The live site shows "Not signed in" and NO Sign in button — by build configuration, not by defect.** | Three causes stacked, and only the first is now fixed. (1) ~~the site was serving an 08-18 build~~ — fixed, see B4. (2) **`render.yaml` sets no `NEXT_PUBLIC_KEYCLOAK_URL`**, and `NEXT_PUBLIC_*` is inlined at BUILD time — so the deployed bundle has no identity provider compiled in and correctly renders "Not signed in" with the reason. (3) **There is no Keycloak deployed to point it at** (I13). Setting the variable without (3) would compile in an address that answers nothing, which is worse than an absent one — the file says so already. So the button appears when a Keycloak exists AND the variable is set AND the site is rebuilt. Deploying Keycloak needs a Render web service — **spend, and the operator's decision.** |
| **B2** | **Establish whether the out-of-state client can reach the site *now*, and which URL they were given.** | Every server-side check passed again 2026-08-19: live suite **25/0/2** against the deployed URL; root, `/dashboard/` and `/admin/` all 200. `www.` fails — no record. Do not change the deployment before proving it is broken for them. |
| **B3** | **The demonstration-data banner is on every live screen.** | Confirmed by measurement — visible text on `/dashboard`, `/projects`, `/formulations`, `/materials`, `/my-work`. By design today (I2) and the operator has flagged it. It clears when S2 wires the screens, which is blocked behind S1, which is blocked behind B0. |


---

## 1. Issues — open defects and gaps, ranked

### 🔴 P1 — gates the MVP acceptance criterion

| # | Issue | Detail |
|---|---|---|
| ~~I1~~ | ~~No sign-in flow.~~ | ✅ **BUILT 2026-08-19 (ADR-025).** Browser-side OIDC + PKCE: `lib/auth/*`, `AuthProvider`, `/auth/callback/`, `AccountMenu` with a real organization switcher. `GET /api/me` + migration 024 close the circularity that made a valid token useless. Auth job **11/0/0** against a real Keycloak, including "the organization id from /api/me is accepted by a real route". **Not yet exercisable by a human: no Keycloak is deployed (I13), and see B4 — the site has not deployed at all since 08-18.** |
| ~~I2~~ | ~~11 of 12 web screens render `demo-data.json`.~~ | ✅ **S2, 2026-08-19.** Five list screens now issue real requests: **Projects, Formulations, My Work, Suppliers, Materials**. The fixture is still IMPORTED by each of them, by design — it is the labelled fallback when there is no API address compiled in or no session. Remaining on the fixture only: Dashboard, Innovation, Pipeline, and the two detail screens. |
| **I3** | **The golden Playwright E2E does not exist.** | It *is* MVP-1's acceptance gate. 15 arrows, every one asserted in UI **and** database state. The YELLOW→GREEN transition is the single most important assertion. |
| **I23** | **MSD's remaining Concept-Note capabilities.** | Built 2026-08-20: application guidance, pending work, record search, **material safety/SDS (§11, all four named questions)** and **the formulation equations (§8/§17, delegating to `evaluate_version`)**. NOT yet built, each with an engine already waiting for it: **formula comparison (§9)** — `compare_versions` exists; **test-result explanation (§17)** — `replicate_statistics` and `derive_disposition` exist; **knowledge/RAG search** — Slice 8 per ADR-013, needs pgvector. Phases 3–6 of Concept Note §39 (formulation recommendations, DOE interpretation, predictive what-if) are beyond MVP-1 by design. |
| ~~I22~~ | ~~MSD has no HTTP route at all.~~ | ✅ **BUILT 2026-08-20.** Root Orchestrator → MSD Conductor → six tools, four routes under `/api/msd`, and a side panel replacing the disabled top-bar placeholder. Migration 026 closed a conversation leak found while building it. |
| **I4** | **No dashboards.** | Chemist, Engineer, Lead, Director — four role dashboards with drill-down to real source records. Slice 7 scope. |

### 🟠 P2 — real defects in shipped code

| # | Issue | Detail |
|---|---|---|
| **I5** | **`record_decision` writes `testing.test_decisions` directly** instead of driving `workflow.approval_routes`. | Two approval records now exist for the same event. §9 says one shared approval engine, never re-implemented per module. |
| **I6** | **`open_failure_for_failed_test` has no caller.** | `complete_execution` must invoke it. §10: "A RED confirmation result automatically opens or links a Failure Investigation." Today nothing does. |
| **I7** | **`revise_version` never writes `formula_version_drivers`.** | So "which failure caused this revision?" has no answer — a hole straight through the digital thread. |
| **I8** | **Notifications have no producer outside mentions.** | `notify()` is the single writer and only `_resolve_mentions` calls it. Approvals, failures and task assignment should all notify. §11 sidebar counts are actionable-item counts and will read zero. |
| **I9** | **CI seed gate does not cover `laboratory.*`, `testing.*`, `quality.*`, approval or messaging tables.** | The gate counts what the seeder wrote for Slices 1–3 only, so a seeder that silently stopped writing Slice 4–7 data would still pass. |
| **I18** | **No rate limiting of any kind exists in the API.** | Founder requirement (`ITWRD App.txt` §69 "rate limiting") and `SECURITY.md` §10, which described Valkey-backed per-user and per-IP limits in detail. Measured 2026-08-20: **zero implementation** — no middleware, no dependency, no counter. Raised independently by Codex and the audit's route sweep. 🔴 **Blocked on ONE decision that is not a code decision:** what the limiter keys on. Behind Caddy, `request.client.host` is the proxy for every caller — one bucket for the whole internet, which fails closed on the first burst; trusting `X-Forwarded-For` instead lets an attacker mint unlimited keys and defeats the limit. Needs the deployed topology (how many hops, which trusted). **A limiter keyed wrongly is worse than none.** Not currently exploitable for disclosure: the API is not deployed (I13/B4) and has no anonymous read or write path. Full reasoning in `SECURITY.md` §10. |
| **I19** | **`core.rls_permissive()` is still `SELECT TRUE`, so the database is not independently fail-closed.** | Every RLS policy opens completely when no request context is set; the only thing preventing a cross-tenant read is `session_scope()` raising in Python. `SECURITY.md` §1 requires any ONE layer failing not to expose data, and today the application layer is the *sole* enforcement whenever the GUC is absent. Deliberate scaffolding — the seeder, migrations and backfills all run with no GUC — so closing it **is** the FORCE-RLS cutover and needs its own migration and review. `tests/db/test_024_memberships_for_subject.py` fails the moment it lands and says what to do. |

### 🟠 P2 — what the live endpoints could NOT answer (opened by S2)

Each of these is stated on the screen itself, not hidden. They close when
a detail route or a richer endpoint exists — none is a defect in the
wiring.

| # | Gap | Detail |
|---|---|---|
| **I14** | **Suppliers: sole-source risk is not computed live.** | `GET /api/suppliers` returns `material_count`, not the material names, so "what breaks if this supplier fails" — the entire point of the screen, and a live risk (RSK-014-01, glass microspheres) — cannot be derived. The page carries a `role="note"` saying the analysis was NOT run, because a supplier showing no flag must not read as "not sole-sourced". Needs a supplier detail route. |
| **I15** | **Formulations index shows the LATEST version, not the current APPROVED one.** | `list_formulas` orders by `version_number DESC`. §8 makes revisions additive, so the newest is often an unapproved draft — which the old fixture page deliberately refused to lead with. Mitigated by always rendering that version's own badge (a draft says DRAFT). A correct "current approved version" needs a query per formula or a new endpoint. |
| **I16** | **Formulations index no longer shows computed figures.** | Theoretical density, solids, VOC, binder:filler and cost need `/versions/{id}/evaluation` — one call per version. They belong on the formula detail screen. §4 forbids the browser deriving them. |
| **I17** | **Projects list no longer shows gate progress, requirement counts or lead.** | `ProjectSummary` returns the project's own columns. Those three live on `/dashboard`, `/requirements/matrix` and `/members`; a list of forty projects must not run forty sub-queries. They belong on the project detail screen. |

### 🔴 P1 — found by adversarially reviewing migration 025

| # | Issue | Detail |
|---|---|---|
| ~~I20~~ | ~~`projects.project_members` has a `USING` clause and NO `WITH CHECK`.~~ | ✅ **CLOSED 2026-08-20 — migration 027.** The largest of the four boundary defects found that day. One INSERT made `core.is_project_member()` answer TRUE, and every project-scoped policy in the database is written as `confidentiality = 'normal' OR core.is_project_member(p.id)` — so a single row opened a restricted project's formulas, batches, tests, failures, approvals and conversations. UPDATE was the same escalation by a different verb. 🔴 **I had recorded this as unfixable without a database because `projects.projects` had no bootstrap column. That was wrong** — `lead_user_id` exists and migration 006 already uses it for exactly this purpose on the read side. The `WITH CHECK` admits two cases: the writer is already a member, or the row materialises the project's DECLARED lead (read via `core.project_lead`, SECURITY DEFINER, registered in the ownership allowlist). Measured against all four writers first: creation, conversion, add_member, remove_member — and there is no DELETE path at all. **`USING` deliberately unchanged**: narrowing who may READ a restricted project's membership list is a separate change with its own blast radius (members screen, dashboards, `my_work`'s role-addressed predicate) and is recorded as I24 rather than bundled into a security fix. |
