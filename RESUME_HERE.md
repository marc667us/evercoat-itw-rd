# ▶ RESUME HERE — EvercoatITWRD APP

**Session closed 2026-08-18. Read this file first, then `TODO.md`.**

Repository: **https://github.com/marc667us/evercoat-itw-rd** (PUBLIC),
branch `master`. Tip **`6f8e078`**, working tree clean, pushed.

---

## ✅ LIVE, AND IT IS A PRODUCT NOW

# https://itwevercoatrd.aiappinvent.com
# https://itwevercoat.aiappinvent.com

Both hostnames, each with its own certificate. **Slices 1, 2 and 3 are
deployed.** Do not re-plan any of this.

| | |
|---|---|
| Live suite, against the DEPLOYED site | **25 passed · 0 failed · 1 skipped** |
| Alignment (local ↔ origin ↔ live) | **ALIGNED** — `./scripts/verify-alignment.sh <url>` |
| CI | **ALL FOUR JOBS GREEN** — API ✓ Web ✓ E2E ✓ Security ✓ |
| Engine tests | **35** (Hypothesis property-based) |
| API tests collected | **229** (from 155) — the new DB ones UNRUN locally, see 4 below |
| API routes | **60** (from 51) |
| Web unit tests | **54** · E2E **25** (axe-core on 9 pages) |
| Certificates | Google Trust Services · valid to **2026-11-16** · auto-renewing |
| Cost | **zero** |

```bash
./scripts/live-suite.sh https://itwevercoatrd.aiappinvent.com web   # 25/0/1
./scripts/verify-alignment.sh https://itwevercoatrd.aiappinvent.com # local == live?
gh workflow run render-setup.yml -f mode=apply -f confirm=APPLY     # deploy
gh workflow run render-audit.yml                                    # read-only inventory
```

---

## 🔴 OUTSTANDING — IN PRIORITY ORDER

### 1. ROTATE `RENDER_API_KEY` — needs the operator, not Claude
Render has **no API for key management**; it is dashboard-only, so this
cannot be automated. The key was pasted into chat on 2026-08-17 and is
still live.

**Three repos hold a Render key** — check Render → Account Settings → API
Keys to see whether they share ONE value:

| Repo | secret set |
|---|---|
| `marc667us/evercoat-itw-rd` | 2026-08-17 ← the exposed one |
| `marc667us/autoworkshop-ai` | 2026-07-27 |
| `marc667us/solar-pv-designer-lite` | 2026-05-23 |

If there is only one key listed, **revoking it breaks AutoWorkshop and
Solar deploys** unless all three secrets are updated first. Order: create
new key → update the repo secrets in **GitHub's web UI** → then revoke the
old one. **Never paste the new key into a chat or a terminal in an agent
session** — that is the entire reason this rotation exists.

### 2. ⏰ `autoworkshop-postgres` is FREE-TIER and EXPIRES 2026-09-01
Render deletes expired free databases **and their data**. Not this
project's, but it lives on the same workspace and it has a date on it.
Confirmed by `render-audit.yml`. Databases do **not** appear in
`/services`, which is why a service list is not a workspace review.

### 3. The live suite's 1 skip — the API is not deployed
`render.yaml` is web-only (ADR-009). The skip is a coverage gap reported
honestly, not a pass. It closes when the API ships, which is Slice 3's
back half (below).

### 4. ~~Slice 3 back-end~~ — BUILT 2026-08-18 pt3, NOT YET VERIFIED ON A DATABASE
Migrations 015 and 016, two domain services, 17 routes, and
`evaluate_version` as the engine's first runtime caller.

🔴 **NONE OF IT HAS TOUCHED A DATABASE.** Docker on this host is wedged:
`docker exec` returns HTTP 500, `docker restart evercoat-postgres` fails
with *"tried to kill container, but did not receive an exit event"*, and
port 55432 accepts a TCP connection and then never answers (proven with a
90-second `connect_timeout`). **Migration 015 has never been applied.**

What actually ran: `ruff`, `mypy`, an app-boot check, and **43 passed /
0 failed / 0 skipped** on the database-free tests. CI is the verification
— it starts a clean `pgvector/pg16`, runs `alembic upgrade head` twice and
the whole suite. **Check the Release run before trusting any of this.**

The demonstration on the live site still uses figures baked at BUILD time,
because the deployed site is a static export with no API (below).

### 4b. ~~THE WEB APP HAS NEVER MADE AN API CALL~~ — WIRED 2026-08-18 pt4

`apps/web` now calls the API. `tests/e2e/shell/api-wiring.spec.ts` asserts
it in a real browser: the top bar's health probe reaches uvicorn and
PostgreSQL **with nothing stubbed**, and `/materials` issues its own
request carrying both headers the API requires.

What exists now:

- `lib/api/client.ts` — the one place this app talks to the API. Typed
  errors, **no fallbacks**, `X-Organization-Id` + bearer on every call.
- `lib/api/materials.ts` — zod-parsed responses, so a renamed field is a
  NAMED error instead of a column of blank cells.
- `lib/api/hooks.ts` — returns `source` alongside `data`, so a page
  cannot render figures without also saying where they came from.
- `components/ui/data-source-banner.tsx` — LIVE or DEMONSTRATION, always
  visible; and a failed request renders the failure rather than
  substituting synthetic rows.
- `components/nav/api-status.tsx` — the API's reachability on every page.

🔴 **THE SIGN-IN FLOW IS STILL MISSING, AND IT IS THE LAST BLOCKER.**
No Keycloak is deployed anywhere — not on Render, not in CI, not on this
host — so no authenticated call can succeed against a real server. The
deployed site therefore still shows the demonstration dataset, now behind
a banner that says exactly why. `lib/api/session.ts` is the seam the OIDC
implementation drops into; nothing above it changes when it does.

The E2E suite establishes a client-side session through a hook that is
**compiled out of production builds** (`NEXT_PUBLIC_E2E_SESSION_HOOK`) and
that grants nothing, because the API verifies every token against the
realm's JWKS and reads permissions from the database. Read the comment in
`session.ts` before touching it.

**Still true:** the live site is a Render STATIC site with no API beside
it, and a free Render *web* service was quota-refused. Wiring the deployed
site to a deployed API is a spend decision and therefore the operator's.

### 5. Slice 4 — Laboratory
Guided batch flow, planned-vs-actual with tolerance flagging, samples with
traceability. `CURRENT_SLICE = 3` in `apps/web/lib/navigation.ts`.

### 6. Two stale `next start` servers (ports 3200, 13099)
Predate this session, not this project's. Deliberately left alone.

---

## 🔴 THINGS MOST LIKELY TO BITE THE NEXT PERSON

**PYTHON OWNS THE ARITHMETIC — INCLUDING THE EASY ARITHMETIC.** The static
export shows engine output baked at build time by
`scripts/build_demo_formulations.py`. If a figure is missing, fix the
engine or the build script. **Never add a calculation to a React
component** — that includes percentage deltas and `fraction * 100`, both
of which were caught in review this session.

**THE BAKED FIGURES CAN GO STALE.**
`tests/calculations/test_demo_formulations_are_current.py` recomputes into
a temp copy and diffs the whole document. After editing any formula or
material: `python scripts/build_demo_formulations.py`.

**A CARRIAGE RETURN HAS BROKEN THREE SCRIPTS.** Python on Windows prints
CRLF, so the LAST field a `read` takes carries a `\r`. It has silently
zeroed the live-suite counts and produced a false "the live site is not
this tree". Twice the fix itself went in as a literal CR byte inside the
`tr -d` quotes. **Verify by reading the bytes back, not by looking at the
rendered line** — `cat -A` shows what you expect.

**RENDER DOES NO CLEAN-URL FALLBACK**, and **never applies a rule to a path
where a resource exists**. The export writes directory indexes because of
`trailingSlash`; do not remove it.

**`NODE_ENV=production` MUST NOT BE A RENDER SERVICE VARIABLE.** It applies
to `npm ci`, which npm reads as `omit=dev`, so typescript and tailwind
never install. It is set inline on the build command.

**`renderSubdomainPolicy` must stay `enabled` and the service must keep its
name** — both custom domains are CNAMEs to
`evercoat-itw-rd-web.onrender.com`.

**A FREE RENDER WEB SERVICE IS REFUSED** on this account; a **static site**
has no instance, draws on no quota, and is free. `render-setup.yml` has no
input that can cost money.

---

## 🔴 THE STANDING CONSTRAINT

**The operator's words: *"if i find the autoworkshop in issues you will be
responsible for breaking it."*** Do not touch `aw-postgres`,
`aw-keycloak`, or any `aw-*` container. Database work uses
**`evercoat-postgres` on port 55432**. `render-setup.yml` refuses to run if
AutoWorkshop's own domain is not intact before and after.

---

## Start the environment

```bash
docker start evercoat-postgres          # host port 55432

cd apps/api
export MIGRATION_DATABASE_URL="postgresql+psycopg://postgres:dev-superuser-pw@localhost:55432/evercoat_itw_rd"
export DATABASE_URL="postgresql+psycopg://evercoat_app:dev-app-pw@localhost:55432/evercoat_itw_rd"
export KEYCLOAK_ISSUER="http://x/realms/y"
python -m alembic upgrade head
python -m pytest tests -q -rs
```

> **`mypy` and `hypothesis` ARE installable here** — both were installed
> this session and both pass locally. The older note in this file saying
> mypy could not run was wrong.

---

## What this session built

**Slice 3 — Materials, Suppliers, Formulations**, and the half of it that
did not exist at all: `apps/api/app/calculations/` was **absent** while
`CLAUDE.md` rule 2 gives deterministic scientific calculation to Python.

The engine is pure, `Decimal` throughout, and **refuses a `float` at the
boundary rather than converting it**. Total percentage, normalisation,
batch scaling, theoretical density, binder:filler, solids, VOC, cost,
epoxy stoichiometry, and §8's hard submission validation.

Density is **volume-additive**, `1/ρ = Σ(wᵢ/ρᵢ)`, with a test separating it
from the mass-weighted average it is commonly confused with — 50/50 of 1.0
and 3.0 is **1.5, not 2.0**. The wrong formula overstates the density of
any blend containing a light filler, which is the case this product exists
to optimise.

The stated invariant is property-tested over 250 generated formulas: the
component masses sum **exactly** to the batch mass.

**What the demo shows:** density falling 1.579 → 1.300 → 1.164 → 1.092
across four versions as microspheres go in, VOC dropping 210 → 91 g/L,
cost rising as the trade-off, and a draft **blocked on two counts** —
§8's hard validation working in front of a viewer.

---

## Governance record

- **Codex** — 3 findings, all fixed, including §8's fourth hard block being
  listed in a docstring and absent from the code (a formula could fail a
  critical safety check and still report SUBMITTABLE), and the materials
  table doing `Number(fraction) * 100` in JavaScript inside the very commit
  whose premise is that the frontend does no arithmetic.
- **Supervisor** — 9 findings, all fixed, and every one reproduced rather
  than asserted. Chiefly: `scale_to_batch` silently renormalised an
  off-100% formula, so a component stated at 36.00% printed as 9.137 kg of
  25 kg — 36.55% — with the two numbers in adjacent columns. And the
  freshness guard **erased its own evidence**, passing on the rerun because
  the failing run had already rewritten the file.
- **Neither reviewer alone was enough — eight sessions running.**
- **A FIX CAN BE WRONG:** clamping the remainder at zero (Supervisor's
  first suggested option) broke the exact-sum invariant, and Hypothesis
  caught it within seconds. The remainder now lands on the largest line.
- **Live-test rule** — satisfied: **25 / 0 / 1** against the deployed site.
- **Not used, by operator instruction:** Google ADK, Stitch, Cloudflare.
