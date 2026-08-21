# TODO — EvercoatITWRD APP

**Updated 2026-08-20 (session close), tip `945b2fe`. CI 5/5 GREEN. S1 + S2 BUILT and DEPLOYED. Live suite 31 / 0 / 2 against the deployed site.** Read `RESUME_HERE.md` first.

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
| ~~I20~~ | ~~`projects.project_members` has a `USING` clause and NO `WITH CHECK`.~~ | ✅ **CLOSED 2026-08-20 — migration 027** (`24c5917`). One INSERT made `core.is_project_member()` answer TRUE, and every project-scoped policy reads `confidentiality='normal' OR is_project_member(p.id)` — so one row opened formulas, batches, tests, failures, approvals and messaging. The `WITH CHECK` bootstraps off `projects.projects.lead_user_id`, which already existed and which migration 006 already used for exactly this purpose on the read side. 🔴 I had recorded this as *unfixable without a database* and was wrong — read the adjacent migration before declaring something impossible. ⚠️ The first escalation test **matched zero rows**, so no `WITH CHECK` was ever evaluated and it could not fail; fixed in `a5ac4e0` with `pytest.raises`. |

| **I21** | **A `technical_thread` channel may carry `project_id IS NULL`, and is then visible organization-wide.** | `022`'s `channels_project_channel_has_a_project` CHECK constrains only `channel_type = 'project'`, and `POST /api/messaging/channels` accepts `technical_thread` with a null project. `thread_for_record` is find-or-create keyed on `(entity_type, entity_id)`, so somebody holding a restricted record's UUID could pre-create an org-visible thread for it and have later "discuss this" clicks land there. Pre-existing, not touched by the 2026-08-20 audit, and the precondition — knowing a restricted record's UUID without being able to read it — is what keeps it below the fix-now bar. The fix is a CHECK constraint requiring `project_id` on `technical_thread` too. Raised as N1 by the Supervisor. |

### 🟡 P3 — worth doing, not blocking

| # | Issue | Detail |
|---|---|---|
| **I10** | Realm JSON has mojibake (`�`) where em-dashes and `§` were. | Cosmetic in the file; the `_comment` keys carrying it are gone, but check `displayName` and any description strings. |
| **I11** | `promote_message` cannot target a decision/experiment/failure. | It creates a task only. §7 lists six promotion targets. Task first was deliberate; the rest is real scope. |
| **I12** | No `/api/messaging` UI. | The routes exist; `DiscussionPanel` is in the §12 reuse list and is unbuilt. |
| 🔴 **I13** | **Deploy of API + Keycloak — the only thing between this repository and a working product. MEASURED 2026-08-20, and now RE-TARGETED (see ADR-026).** | **What was measured.** `.github/workflows/render-provision.yml` (POST/GET only, no DELETE, name-scoped to `evercoat-itw-rd-*`, refuses rather than overwrites) was run against the real Render API with the repository's `RENDER_API_KEY`. Render refused both halves, verbatim: `POST /postgres` → **400 `"cannot have more than one active free tier database"`** (`autoworkshop-postgres` holds that slot and **expires 2026-09-01**), and `POST /services` plan=free → **400 `"free tier usage quota has been exhausted, new services are not allowed"`**. 🔴 **The key WORKS — those are 400s, not 401s.** `GET /owners` returned 200 (`tea-d86fu8mk1jcs7397i70g`). A new or rotated key produces the identical errors: this is a plan/billing boundary, not auth and not technical. **Do not spend a session rotating credentials.** ▶ **THE DECISION (operator, 2026-08-20): replace Render with Railway's free tier for this app — ADR-026.** Every technical prerequisite already exists (`apps/api/Dockerfile`, `services/keycloak/evercoat-realm.json`, migrations, seed, CI-proven suite); what changes is the provider, not the artefact. ⚠️ **Not started, and it is blocked on one owner action:** the Railway CLI on this host is **unauthenticated** (`railway whoami` → `Unauthorized`, CLI v4.66.0 at `C:/Users/USER/nodejs/railway`), and there is **no `RAILWAY_TOKEN` repository secret** — `RENDER_API_KEY` is still the only one. |
| **I24** | **`projects.project_members` READ visibility is still organization-wide.** | Who is on a *restricted* project is readable by anyone in the organization. Held out of migration 027 deliberately — 027 closed the WRITE escalation, which was the one that opened every other table. This is a disclosure of membership, not of content. |
| 🔴 **I25** | **`TODO.md` — this file — was destroyed by its own last two updates, and recovered from git history.** | At tip `945b2fe` the file was **15,794,988 bytes across 63 lines**, with single lines up to **1.8 M characters**: the I13 table row concatenated into itself ~1,369 times. **Every issue except I13 had been deleted** — I3–I12, I14–I21 and I23 were all gone. Damage began at `24c5917` (11,940 bytes, I10–I13/I20/I21 already lost) and completed at `4598fc8` (15.8 MB). Recovered here from **`84733a9:TODO.md`** (17,815 bytes, register intact) with the I13 and I20 updates re-applied by hand. ⚠️ **Root cause not yet established** — it is almost certainly an append/rewrite step in the docs-update path that re-emits the whole file into one row. Find it before the next docs commit, or this recurs silently. It is not periodic repetition, so it cannot be un-done mechanically; only git history recovers it. |

---

## 2. Schedule to complete MVP-1

**Basis:** the owner's own budget — `ITWRD App.txt` L22,665 — 3 sessions/day
× 5 hours = **15 dev hours/day**, MVP-1 = 3 days = **9 sessions = 45 hours**.

Slices 1–7 backend is built. What remains is almost entirely the **browser
half**, which is what the acceptance gate actually measures.

| # | Session | Work | Hours | Exit condition |
|---|---|---|---|---|
| ~~S1~~ | ~~Auth, end to end~~ | ✅ **DONE**, except its exit condition, which needs a deployed Keycloak (I13, spend) and a working deploy (B4). Built: PKCE flow, callback, provider, org switcher, `GET /api/me`, migration 024. **NOT** next-auth — ADR-025. | 5 | ⚠️ Exit condition NOT met: a human cannot sign in on the deployed shell, because no Keycloak is deployed. Everything below that line is proven in CI. |
| **S2** | Wire the read screens | Projects, Requirements, Materials, Formulations, Batches, Tests — swap `demo-data.json` for TanStack Query against the real routes. Keep the demo banner only where no route exists yet. | 5 | Six screens render database rows. `demo-data.json` referenced by ≤ 6 files. |
| **S3** | Wire the write paths | Create project → create formula → submit → approve lab. Forms with React Hook Form + Zod against the existing routes. | 5 | The first four golden-scenario arrows are drivable by hand in a browser. |
| **S4** | Lab + Test entry | Batch creation, sample, test creation, **raw per-replicate entry**. Derived status displayed as two separate fields (automatic evaluation *beside* final disposition). | 5 | A RED result can be produced through the UI. |
| **S5** | Approvals + failure UI | `ApprovalTimeline`, the 7 decision types, failure investigation screen, hypothesis states. **Fix I5, I6, I7 here** — the UI is what makes those holes visible. | 5 | YELLOW→GREEN happens by human approval, and a RED opens a failure. |
| **S6** | Dashboards (I4) | Four role dashboards, KPI cards, drill-down to real source records. **Fix I8** so counts are actionable items, not totals. | 5 | Every KPI drills to a real record. No panel can only ever show zero. |
| **S7** | Golden E2E (I3) | The 15-arrow scenario, asserted in UI **and** DB. Plus RBAC E2E and the MSD boundary suite. | 5 | Golden suite green in CI against a real Keycloak. |
| **S8** | Deploy + live suite | Deploy web (already static). API + Keycloak **only if the operator authorises the spend** — otherwise ship the browser-provable half and say so plainly. Run the full suite against the deployed site. | 5 | **passed / failed / skipped reported as three numbers** against the deployed URL. |
| **S9** | Governance + hardening | Codex 5-pass, Supervisor, `MEMORY.md` / `BRAIN.md` / `CHANGELOG.md` / `CONTEXT.md`, a11y sweep with axe on every new screen, `docs/REUSABILITY.md`. | 5 | Four gates pass. MVP-1 declared with evidence, not assertion. |

**Total: 45 hours = 9 sessions = 3 days at the owner's stated rate.**

### Two risks that would blow this schedule

1. **S8 is not fully in our control.** The API and Keycloak need an
   instance; Render's free web quota is exhausted. If the operator does
   not authorise spend, the deployed artefact stays the static site and
   the *full* golden scenario is provable only in CI. **Say that plainly
   rather than reporting a green that means something narrower.**
2. **Docker on this host is wedged.** Everything is verified through CI,
   which is slower per iteration. Restarting Docker Desktop would fix it
   but restarts the `aw-*` stack — **which the operator has forbidden.**

---

## 3. Done this session — do not re-plan

- Messaging service + 6 routes (103 total). Schema 022 finally has a writer.
- Migration **023** — `audit.deny_mutation()` named the wrong table.
- **Keycloak runs, for the first time**, in CI: bootstrap script, subject
  binding, 6 auth integration tests, 14 realm invariant tests.
- **The shipped realm was unimportable since Slice 1** — seven `_comment`
  keys, four of them nested. Fixed; commentary moved to
  `services/keycloak/realm/README.md`.
- Mention-notification leak fixed (author's session vs recipient's access).
- All four Codex findings fixed.
- `scripts/assert-suite-ran.py` — three numbers, never an exit code.
