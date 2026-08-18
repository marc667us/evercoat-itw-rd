# ▶ RESUME HERE — EvercoatITWRD APP

**Session closed 2026-08-18 (pt2). Read this file first, then `TODO.md`.**

Repository: **https://github.com/marc667us/evercoat-itw-rd** (PUBLIC),
remote `origin`, branch `master`. Tip **`5c4973a`**, working tree clean.

---

## ✅ THE APP IS ONLINE

# https://itwevercoatrd.aiappinvent.com
# https://itwevercoat.aiappinvent.com

Two sessions of "there is still no URL" are closed. Do not re-plan this.
Both hostnames are attached to the same service and **each has its own
certificate** — one working proves nothing about the other, which is why
`render-setup.yml` proves every hostname independently.

| | |
|---|---|
| Live suite, against the DEPLOYED site | **passed=14 · failed=0 · skipped=1** |
| Certificate | Google Trust Services WE1 · 2026-08-18 → 2026-11-16 · TLS 1.3 · auto-renewing |
| Render service | `evercoat-itw-rd-web` — `srv-da242g37uimc73dqnmg0`, type **`static_site`** |
| Workspace | 6 services + 2 Postgres, **all belonging to Evercoat / AutoWorkshop / Solar — nothing is removable.** There is no App Factory on Render. Audit it with `render-audit.yml` (read-only). |
| ⏰ **`autoworkshop-postgres` is FREE and EXPIRES 2026-09-01** | Render deletes expired free databases. Not this project's, but it is on this workspace. |
| CI | **ALL FOUR JOBS GREEN** — API ✓ Web ✓ E2E ✓ **Security ✓** (Security had never passed before) |
| Cost | **zero** |

The one skip is the API surface, which is not deployed. It is a coverage
gap reported as a gap, never as a pass.

```bash
# Re-prove the deployment at any time:
./scripts/live-suite.sh https://itwevercoatrd.aiappinvent.com web

# Create/reconcile the Render service (plan mode is read-only and the default):
gh workflow run render-setup.yml -f mode=apply -f confirm=APPLY
```

---

## 🔴 THE THINGS MOST LIKELY TO BITE THE NEXT PERSON

**The certificate failure was never a DNS fault.** Namecheap was correct
throughout — the CNAME resolved, and there are no CAA records blocking
issuance. **No Render service existed**, so the domain was attached to
nothing, so Render never *requested* a certificate. That is what the
browser was reporting as "not secure". Do not go looking in Namecheap.

**A free WEB SERVICE is refused by this account; a STATIC SITE is not.**
`POST /services` with a web service returns
`400 free tier usage quota has been exhausted`. The exhausted allowance is
the workspace's 750 free INSTANCE-hours. A static site has **no instance**,
so it never touches that allowance, is free, does not spin down, and gets
free auto-renewing TLS. `static_site` has **no `plan` field at all**, which
is why the `plan` input was deleted — **no dispatch of `render-setup.yml`
can now cost money.**

**Render does NOT do clean-URL fallback.** There is no implicit `.html`
lookup, so a default Next export (`dashboard.html`) would make `/dashboard`
404. `next.config.mjs` sets `trailingSlash` for the export so it writes
directory indexes. **And Render never applies a redirect/rewrite rule to a
path where a resource already exists** — which is why the broken root could
not be fixed with a rule and had to be fixed in `app/page.tsx`.

**`NODE_ENV=production` must NOT be a Render service variable.** It applies
to `npm ci`, which npm reads as `omit=dev`, so typescript, tailwindcss and
postcss never install and the build fails. It is set inline on the build
command instead — exactly as `ci.yml` sets it on its build step and not its
install step.

**`renderSubdomainPolicy` must stay `enabled` and the service must keep its
name.** `itwevercoatrd.aiappinvent.com` is a CNAME to
`evercoat-itw-rd-web.onrender.com`. Rename the service, or disable the
subdomain, and the custom domain resolves to something Render no longer
serves — the site goes dark and the certificate stops renewing.

---

## 🔴 THE STANDING CONSTRAINT

**The operator's words: *"if i find the autoworkshop in issues you will be
responsible for breaking it."*** Do not touch `aw-postgres`, `aw-keycloak`
or any `aw-*` container. All database work uses **`evercoat-postgres` on
port 55432**. `render-setup.yml` guards AutoWorkshop's own domain and
refuses to run if it is not present before and after.

---

## Start the environment

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
python -m pytest tests -q -rs          # 155 passed / 0 failed / 0 skipped
```

> **`mypy` is NOT installed locally** — `CLAUDE.md` §13's `mypy app` cannot
> run here. It DOES run in CI and passes. Ruff check and format are clean.

---

## What this session changed

1. **Created the Render static site**, attached and verified the domain,
   and got the certificate issued. The setup workflow no longer stops at
   "attached" and calls that success — it waits for the deploy to go LIVE
   and then makes a real validating HTTPS request, which is the only thing
   that can actually prove a certificate exists.

2. **Fixed the front door and `/dashboard` BEFORE deploying** — both were
   broken in the export and both would have shipped green. See above.

3. **Made the live suite able to test a live site.** Playwright's
   `baseURL` was hardcoded to `127.0.0.1:3100` and *nothing read*
   `PLAYWRIGHT_BASE_URL`, so the "live" E2E run tested localhost while
   reporting against the deployed URL — it would have passed with the
   deployment entirely broken. It now has a real live mode and a
   `web|api|full` profile.

4. **Made the setup workflow able to change anything.** It was create-only:
   every re-run reconciled nothing, and the deploy poll found the
   *previous* deploy already live and reported success. It now PATCHes,
   reconciles env vars (a separate endpoint), triggers a deploy and waits
   on *that* deploy id.

5. **Turned the Security job green for the first time.** Trivy's 3 HIGH
   CVEs closed via `overrides`; that revealed **Semgrep had never run**,
   and its 14 findings included the RLS GUC setter interpolating its value
   into SQL. Now parameterised with `set_config`, proven by the full API
   suite against a real database.

---

## ▶ NEXT

1. **Slice 2 frontend** — five API surfaces still have no clickable page;
   `CURRENT_SLICE = 1` in `apps/web/lib/navigation.ts`. Then Slice 3.
2. **At Slice 3 the site must stop being static.** `apps/web` makes no API
   calls today, which is the only reason a static export is honest. Once
   the API is wired in, a static host cannot serve the product — and that
   deployment needs either restored free instance-hours or an explicit,
   operator-approved paid tier. It also closes the live suite's 1 skip.
3. **Rotate `RENDER_API_KEY`** — it was pasted into chat on 2026-08-17 and
   is account-wide across AutoWorkshop, Solar and Evercoat.
4. Two **stale `next start` servers** (ports 3200 and 13099) predate this
   session and were deliberately left running. They are not this project's.

---

## Governance record for this session

- **Codex CLI** — run twice on the full diff. **4 findings, all fixed**,
  including a same-named service being reused without a type check (which
  could have attached the production domain to a BILLED service) and
  env vars never being reconciled — which was **true of the live service**:
  the run log's `env before` proved `NODE_ENV` was missing.
- **Supervisor** (`/code-review`) — **10 findings**, several Codex missed,
  including the create-only workflow and CI never building the export mode.
  One of its claims was **wrong** (`<main>` is supplied by the layout) and
  was checked against the generated HTML before acting.
- **Neither reviewer alone was enough — seven sessions running.**
- **Live-test rule** — satisfied: **14 / 0 / 1** against the deployed site.
- **Not used, by operator instruction:** Google ADK, Stitch, Cloudflare.
