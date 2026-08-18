# ▶ RESUME HERE — EvercoatITWRD APP

**Session closed 2026-08-18. Read this file first, then `TODO.md`.**

Repository: **https://github.com/marc667us/evercoat-itw-rd — now PUBLIC**,
remote `origin`, branch `master`. Tip **`96bbf4c`**, working tree clean.

---

## 🔴 THE ONE THING TO READ BEFORE PLANNING ANYTHING

**There is still no working URL, and the reason changed twice in one
session.** Do not act on a recorded blocker without re-measuring it —
that is now the third time in this project a stated blocker was wrong.

1. The blocker was recorded as *"Render's GitHub App cannot read the
   PRIVATE repo."* The operator chose to make the repo **PUBLIC**. That
   worked; the repo-access error is gone.
   *(`gh repo edit --visibility` fails on this gh build — the flag it
   demands does not exist. Use `gh api -X PATCH repos/... -f visibility=public`.)*
2. The real blocker now is account-wide:
   `POST /services` → **400 `"free tier usage quota has been exhausted,
   new services are not allowed"`**. Measured: **all five Render services
   are `plan=standard`; none are free.** The exhausted allowance is the
   workspace's 750 free instance-hours per month, which resets with the
   billing cycle.

**Nothing was created and nothing was billed.** `render-setup.yml` now
takes an explicit `plan` input defaulting to `free`, so a careless
dispatch 400s rather than costing money.

---

## Where the build actually is

| | |
|---|---|
| API tests | **155 passed / 0 failed / 0 skipped** (was 152) |
| Web tests | 26 passed · E2E 29 green in CI |
| Migrations | **014**, each applied and verified against a real database |
| CI | **API ✓ · E2E ✓ · Web ✓ — the first time any of them passed.** |
| CI, still red | **Security scan** — Trivy, 3 HIGH dependency CVEs (`postcss 8.4.31 → 8.5.12` + 2 more). More exposed now the repo is public. |
| Deploy | **Nothing deployed. No URL.** |
| Slice 1 | code-complete; full stack has still never run at once |
| Slice 2 | complete except the frontend |

### Start the environment

```bash
docker start evercoat-postgres          # host port 55432

cd "apps/api"
export MIGRATION_DATABASE_URL="postgresql+psycopg://postgres:dev-superuser-pw@localhost:55432/evercoat_itw_rd"
export DATABASE_URL="postgresql+psycopg://evercoat_app:dev-app-pw@localhost:55432/evercoat_itw_rd"
export KEYCLOAK_ISSUER="http://x/realms/y"
python -m alembic upgrade head

TEST_DB_HOST=localhost TEST_DB_PORT=55432 POSTGRES_DB=evercoat_itw_rd \
TEST_OWNER_USER=evercoat_owner TEST_OWNER_PASSWORD=dev-owner-pw \
APP_DB_USER=evercoat_app APP_DB_PASSWORD=dev-app-pw \
DATABASE_URL="$DATABASE_URL" KEYCLOAK_ISSUER="$KEYCLOAK_ISSUER" \
python -m pytest tests -q -rs
```

> **`mypy` is NOT installed locally** — `CLAUDE.md` §13's `mypy app` cannot
> run here. It DOES run in CI and passes. Ruff check and format are clean.

---

## 🔴 THE STANDING CONSTRAINT — do not violate it

**The operator's words: *"if i find the autoworkshop in issues you will be
responsible for breaking it."*** Do not touch `aw-postgres`,
`aw-keycloak`, or any `aw-*` container. All database work uses
**`evercoat-postgres` on port 55432**. Nothing this session touched one.

---

## What this session changed

**Migration 014 — ownership, because nothing had ever decided it.**
CI failed `37 failed / 65 passed / 50 errors`, all `permission denied`,
while the same suite passed locally, from the same migrations. 001
declares `CREATE SCHEMA ... AUTHORIZATION evercoat_owner` and `env.py`
says migrations run as the owner role — but 001 must `CREATE ROLE`, so
alembic runs as `postgres` and every table belonged to `postgres`. The
dev database only looked right because it had been **repaired by hand**;
`ci.yml` repaired a **different subset** of schemas. Two hand-maintained
lists that nothing could check against each other.

Rehearsed rather than reasoned about: a scratch database built exactly as
CI builds it reproduced the failure, and the new invariant test was
**verified to fail at b4000** before being trusted.

**Functions deliberately not swept.** A SECURITY DEFINER function runs
with its OWNER's privileges — 013 moved `audit.chain_row` on purpose, and
`core.is_project_member` runs inside RLS policies and must not gain the
owner's exemption.

**The E2E job pointed the API at the `postgres` superuser,** which
`app/core/config.py` refuses by design. The refusal is correct; the job
was wrong. It now connects as `evercoat_app`.

**Cloudflare Pages stopgap, built to be reversed.** `output` is now a
switch on `NEXT_OUTPUT`, not a replacement — `render.yaml`, the
Dockerfile and `render-setup.yml` are untouched, and the standalone build
was re-verified. **The operator's stated intent is to move back to Render
once the quota resets.**

---

## ▶ NEXT SESSION — TASK 1 IS THE ONLY ONE THAT MATTERS TO THE OPERATOR

**The operator has asked to see this online, at a real web URL, across
two sessions. It is still not online. Do this FIRST and do not offer
localhost or a tunnel as a substitute — both were explicitly rejected.**

- `127.0.0.1` is not an answer; the operator said so directly.
- Cloudflare **quick tunnels are blocked on their machine** (DNS error
  1001 + "not secured"). Do not offer one again.
- The target URL is **`https://itwevercoatrd.aiappinvent.com`**.

### 1. Get it online. Three routes, cheapest effort first.

**(a) GitHub Pages — needs NOTHING from the operator. Start here.**
**Pages was ENABLED on the repo on 2026-08-18** (`build_type: workflow`,
source `master`) and is serving nothing yet:
`https://marc667us.github.io/evercoat-itw-rd/`. The repo is public and
Actions already has the token, so no new account, secret or approval is
required — this is the only route with zero operator dependencies.
Remaining work: a deploy workflow that runs the static export
(`NEXT_OUTPUT=export`) and publishes `apps/web/out` via
`actions/deploy-pages`. **Note the subpath:** the project site is served
from `/evercoat-itw-rd/`, so the export needs `basePath` and
`assetPrefix` or every asset 404s — add a `NEXT_BASE_PATH` switch beside
the existing `NEXT_OUTPUT` one. `public/_redirects` is Cloudflare-only
and does NOT apply here, so the root `redirect()` export stub must be
handled another way (a `basePath`-aware `index.html`, or make `/` render
the dashboard).

**(b) Cloudflare Pages** — `.github/workflows/deploy-cloudflare-pages.yml`
is written and validated but needs **two secrets only the operator can
create**: `CLOUDFLARE_API_TOKEN` (permission *Cloudflare Pages: Edit*)
and `CLOUDFLARE_ACCOUNT_ID`. Then dispatch with `confirm=DEPLOY`.

**(c) Render — the operator's stated end state.** Only once the free
quota resets: `render-setup.yml -f mode=apply -f confirm=APPLY -f plan=free`.
**DNS already points at `evercoat-itw-rd-web`; no DNS change needed.**
Confirm the run id actually STARTED — a concurrency group is a one-slot
replacement waiting room, not a queue.

**Custom domain** on (a) or (b) needs the Namecheap CNAME repointed —
**no Namecheap credentials exist on this machine**, so that step is the
operator's. Skip it entirely if (c) is close, since the CNAME is already
correct for Render.

### 2. Then, in order

2. **Fix the live-suite / API gap** (below) before claiming GATE-2. It
   reported 0/0/0 because it waits on `/health/ready`, an API route, and
   `render.yaml` is web-only.
3. **Trivy** — the last red CI job.
4. **Slice 2 frontend**, then Slice 3. Five API surfaces still have no
   clickable page; `CURRENT_SLICE = 1` in `apps/web/lib/navigation.ts`.

---

## 🔴 Lessons worth carrying forward

**A GREEN BUILD IS NOT A WORKING FRONT DOOR.** `app/page.tsx` is
`redirect("/dashboard")`. Under `output: "export"` there is no server to
issue it, so the root exports as `<html id="__next_error__">` — while
`next build` exits 0 and prints `✓ Exporting (2/2)`. The site would have
served an error document at `/` with every gate green. Found by reading
the generated `out/index.html`; fixed with `public/_redirects` and proven
against Cloudflare's own runtime, not assumed.

**TWO HAND-KEPT LISTS CANNOT BE CHECKED AGAINST EACH OTHER.** The whole
CI failure was a schema list in YAML disagreeing with a repair someone had
once typed into a database. The fix was not to extend the list; it was to
make one thing decide and assert it in a test.

**A COMMENT ASSERTING ENGINE SEMANTICS IS A CLAIM.** I wrote that the
owner "remains subject to policies under FORCE RLS". Codex challenged it;
measurement showed `relforcerowsecurity` is **false on all 18 tables**.
**So `owner_session` bypasses RLS — isolation assertions must use
`app_session`,** or they pass whether or not RLS works.

**REPORT THREE NUMBERS, EVEN WHEN THEY ARE ZERO.** The live suite reported
**passed=0 / failed=0 / skipped=0 — it did not run.** It waits on
`/health/ready`, an API route, and only the web app was reachable. That is
not a tunnel artefact: `render.yaml` is web-only by ADR-009, so the same
gap will hit the Render deploy.

---

## Governance record for this session

- **Codex CLI** — run on the full diff. **4 findings, all fixed**,
  including a correct HIGH on the FORCE-RLS claim and a definer-ownership
  test that would still have passed if every function had been swept.
- **Supervisor** — replaced this session by direct measurement against a
  purpose-built rehearsal database: the CI condition reproduced, table
  privileges probed, and the new test verified to fail without the fix.
- **Live-test rule** — reported honestly as 0/0/0, did not run. GATE-2
  remains open.
- **Not used, by standing instruction:** Google ADK, Stitch.
- No servers left running — ports 3210 and 8788 verified free at close.
