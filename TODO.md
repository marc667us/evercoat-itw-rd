# TODO — EvercoatITWRD APP

**Updated 2026-08-19, tip `b892995`. CI is 5 of 5 GREEN. S1 is BUILT.** Read `RESUME_HERE.md` first.

---

## 0. Blocking — do these before anything else

| # | Task | Why it blocks |
|---|---|---|
| ~~B1~~ | ~~Read the `bash -x` trace in the Auth job.~~ | ✅ **CLOSED 2026-08-19.** A literal `\n` became a bare word `n`, which curl read as a second URL — exit 6, status `204000`. Four more defects sat behind it. **Auth is now green: passed=7 failed=0 skipped=0.** |
| ~~B0~~ | ~~Decide S1's auth architecture.~~ | ✅ **CLOSED 2026-08-19 — ADR-025.** Browser-side OIDC Authorization Code + PKCE against the existing public `evercoat-web` client. next-auth removed: it needs server route handlers and this deploys as a static export. |
| 🔴 **B4** | **RENDER HAS NOT DEPLOYED SINCE 2026-08-18. Every commit in this session is un-deployed.** | Measured, not guessed. `render-audit` reports the service correctly configured — `autoDeploy: yes`, `branch: master`, right repo, not suspended — and **`last deploy live at 2026-08-18T20:09:24Z`**. The live site serves `last-modified: Tue, 18 Aug 2026 20:09:25 UTC`, and `/auth/callback/` 404s there after 14 minutes of polling while `/` returns 200. So the site is UP and serving an OLD build; the push webhook is not reaching Render. **This is a dashboard action (reconnect the GitHub integration, or Manual Deploy) and therefore the operator's.** Do NOT run `render-setup.yml` in apply mode to force it: that workflow DELETEs custom domains on the AutoWorkshop service. |
| **B2** | **Establish whether the out-of-state client can reach the site *now*, and which URL they were given.** | Every server-side check passed again 2026-08-19: live suite **25/0/2** against the deployed URL; root, `/dashboard/` and `/admin/` all 200. `www.` fails — no record. Do not change the deployment before proving it is broken for them. |
| **B3** | **The demonstration-data banner is on every live screen.** | Confirmed by measurement — visible text on `/dashboard`, `/projects`, `/formulations`, `/materials`, `/my-work`. By design today (I2) and the operator has flagged it. It clears when S2 wires the screens, which is blocked behind S1, which is blocked behind B0. |


---

## 1. Issues — open defects and gaps, ranked

### 🔴 P1 — gates the MVP acceptance criterion

| # | Issue | Detail |
|---|---|---|
| ~~I1~~ | ~~No sign-in flow.~~ | ✅ **BUILT 2026-08-19 (ADR-025).** Browser-side OIDC + PKCE: `lib/auth/*`, `AuthProvider`, `/auth/callback/`, `AccountMenu` with a real organization switcher. `GET /api/me` + migration 024 close the circularity that made a valid token useless. Auth job **11/0/0** against a real Keycloak, including "the organization id from /api/me is accepted by a real route". **Not yet exercisable by a human: no Keycloak is deployed (I13), and see B4 — the site has not deployed at all since 08-18.** |
| **I2** | **11 of 12 web screens render `demo-data.json`.** | Only `tests/e2e/shell/api-wiring.spec.ts` proves a real request. A backend with no UI cannot demonstrate the digital thread. |
| **I3** | **The golden Playwright E2E does not exist.** | It *is* MVP-1's acceptance gate. 15 arrows, every one asserted in UI **and** database state. The YELLOW→GREEN transition is the single most important assertion. |
| **I4** | **No dashboards.** | Chemist, Engineer, Lead, Director — four role dashboards with drill-down to real source records. Slice 7 scope. |

### 🟠 P2 — real defects in shipped code

| # | Issue | Detail |
|---|---|---|
| **I5** | **`record_decision` writes `testing.test_decisions` directly** instead of driving `workflow.approval_routes`. | Two approval records now exist for the same event. §9 says one shared approval engine, never re-implemented per module. |
| **I6** | **`open_failure_for_failed_test` has no caller.** | `complete_execution` must invoke it. §10: "A RED confirmation result automatically opens or links a Failure Investigation." Today nothing does. |
| **I7** | **`revise_version` never writes `formula_version_drivers`.** | So "which failure caused this revision?" has no answer — a hole straight through the digital thread. |
| **I8** | **Notifications have no producer outside mentions.** | `notify()` is the single writer and only `_resolve_mentions` calls it. Approvals, failures and task assignment should all notify. §11 sidebar counts are actionable-item counts and will read zero. |
| **I9** | **CI seed gate does not cover `laboratory.*`, `testing.*`, `quality.*`, approval or messaging tables.** | The gate counts what the seeder wrote for Slices 1–3 only, so a seeder that silently stopped writing Slice 4–7 data would still pass. |

### 🟡 P3 — worth doing, not blocking

| # | Issue | Detail |
|---|---|---|
| **I10** | Realm JSON has mojibake (`�`) where em-dashes and `§` were. | Cosmetic in the file; the `_comment` keys carrying it are gone, but check `displayName` and any description strings. |
| **I11** | `promote_message` cannot target a decision/experiment/failure. | It creates a task only. §7 lists six promotion targets. Task first was deliberate; the rest is real scope. |
| **I12** | No `/api/messaging` UI. | The routes exist; `DiscussionPanel` is in the §12 reuse list and is unbuilt. |
| **I13** | Deploy of API + Keycloak. | Blocked on Render free web-service quota. **Operator decision — never propose spending.** The CI `auth` job deliberately removes this from the critical path. |

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
