# ▶ RESUME HERE — EvercoatITWRD APP

**Session 2026-08-19. Read this file, then `TODO.md`.**

Repository: **https://github.com/marc667us/evercoat-itw-rd** (PUBLIC),
branch `master`. Tip **`bc156da`**, working tree clean, pushed.
**CI 5 of 5 green. S1 (sign-in) and S2 (read screens) are built and DEPLOYED.**

---

## ✅ B1 IS CLOSED. CI IS GREEN, INCLUDING AUTH.

**`Auth — real Keycloak, real tokens`: passed=7 failed=0 skipped=0.**

Authentication has now been proven end-to-end against a real identity
provider for the first time in this project's life. Nothing is skipped —
the count is asserted, not inferred from an exit code.

### What the `exit 6` actually was

The `bash -x` trace answered in one line what reading the source had got
wrong twice:

```
+ status=204000
##[error]Process completed with exit code 6.
```

`keycloak-bootstrap.sh` carried a **literal `\n`** where a line
continuation was intended. Bash strips the backslash from an unquoted
`\n`, leaving the bare word `n`, which **curl accepts as a second URL**.
It fetched the real endpoint (204), failed to resolve `"n"` (**exit 6**),
and `-w '%{http_code}'` **prints once per URL** — hence `204000`.

**Nothing to do with DNS.** Both candidate causes recorded in the last
handover were wrong.

### Four more defects were hiding behind that one symptom

| # | Defect | Why it mattered |
|---|---|---|
| 1 | `expect_status` matched `case "$got" in 2*)`, so it **accepted `204000` as success** | Only curl's exit code stopped the run. Had the stray URL resolved, a failed role mapping would have passed the gate silently and surfaced four steps later as `invalid_grant` |
| 2 | `api_status` had **no failure branch** | Why nothing printed. It now names the request and RETURNS the rc |
| 3 | `api_status` called **`curl -s`**, which silences the error TEXT | The new diagnostic would have printed `curl said: ` and nothing else — **on the exact incident it was written for**. Measured: `-s` → empty stderr, `-sS` → the message |
| 4 | The audience-mapper POST ended **`>/dev/null \|\| true`** | Swallowed 400/401/500 alongside the 409 it meant to tolerate, while the comment fifty lines above called that mapper NOT optional. A skipped mapper rejects every genuine token with the same flat "invalid token" a forged one gets |

Defect 3 was found by the **Supervisor** and missed by Codex. Defect 4
was found by **Codex** and missed by the Supervisor. **Seventh session
running in which neither reviewer alone was sufficient.**

### And the five "authentication failures" were one wrong URL

With the bootstrap fixed, the auth job got further and reported 5 of 6
tests failing with `404 != 401`, `404 != 400`, `404 != 403`. That reads
as five authentication defects. It was **one typo repeated five times**:
the tests called `/api/my-work/tasks`, and the route is `/api/my-work`
(`main.py:175` prefix + `tasks.py:96` `@router.get("")`). The one test
that passed is the one calling `/api/projects` — which is the proof that
tokens, the audience mapper, the subject binding and the principal
lookup all work.

The path is now **one constant**, and a guard runs first that says which
of the two things went wrong.

---

## ✅ THE LIVE SUITE HAS RUN AGAINST THE DEPLOYED SITE

```
LIVE SUITE — https://itwevercoatrd.aiappinvent.com
   passed  : 25
   failed  : 0
   skipped : 2
```

Both skips are **named**: the API surface (not deployed) and
`api-wiring.spec.ts`.

Two defects were found by running it rather than by trusting CI:

1. **The documented invocation tested nothing.** `./scripts/live-suite.sh <url>`
   with no second argument defaulted to profile `full`, waited 300s on
   `/health/ready` (an API route) against a web-only deployment, and
   reported `passed=0 failed=0 skipped=0, the suite did not run`. The
   script's own comment already said `web` matches production; the code
   did not. The default is now **`auto`**, which measures it: an API
   health route answers JSON, a static site answers its own HTML 404.
   Measured here — `/health/ready` returns `Content-Type: text/html`,
   16KB body.

2. **8 permanent false reds.** The first real run reported 25 passed /
   8 failed, and the 8 were the whole of `api-wiring.spec.ts` —
   accessibility 13/13 and navigation 12/12 passed. The deployed page
   carries **no `api-status` element and no `data-source-error` element
   at all**, because that seam is compiled OUT of production builds. The
   spec was asserting against something that does not exist at that URL.
   It is now excluded in LIVE mode and counted as a **named skip**.

---

## ⚠️ THE DEMONSTRATION DATA IS SHOWING ON THE LIVE SITE

Confirmed by measurement on 2026-08-19, on `/dashboard`, `/projects`,
`/formulations`, `/materials` and `/my-work` — an amber banner, visible
text, outside any `<script>`:

> ⚠ **Demonstration data** — every project, requirement, measurement and
> person shown here is synthetic. Nothing on this site is a real R&D
> record.

This is **by design today** (11 of 12 screens render `demo-data.json`;
`CLAUDE.md` §15 records it), not a regression. It goes away when the
screens are wired to the real API — S2 — which is blocked behind S1.
**The operator has flagged it. Treat removing it as a goal, not a
detail.**

---

## ✅ S1 IS BUILT — SIGN-IN EXISTS

**ADR-025: browser-side OIDC Authorization Code + PKCE, not next-auth.**
The deploy is a Render **static site** (`NEXT_OUTPUT=export`) — no server,
no route handlers — and NextAuth v5 requires them. The realm was already
configured for the flow that does work: `evercoat-web` is `publicClient`
with `pkce.code.challenge.method: S256` and carries the API audience
mapper. `next-auth` is removed from `package.json` and the lockfile.

| Built | Where |
|---|---|
| PKCE, four RFC 7636 operations as pure functions | `apps/web/lib/auth/pkce.ts` |
| Flow store — verifier only, never the token | `apps/web/lib/auth/flow-state.ts` |
| Sign-in / sign-out / refresh / org selection | `components/providers/auth-provider.tsx` |
| The redirect target, with the `state` check | `app/auth/callback/page.tsx` |
| Real organization switcher (was a disabled placeholder for 3 slices) | `components/nav/account-menu.tsx` |
| **`GET /api/me`** | `apps/api/app/api/me.py` + migration **024** |

### 🔴 The gap that made sign-in useless, and nobody had asked about it

`get_principal` requires `X-Organization-Id`, and **every** authenticated
route depends on it. So a browser that had just signed in held a valid
token and **no way to discover a tenant to ask for** — every request it
could make returned 400 demanding a header whose value nothing supplied.

This project has asked *"which production path WRITES this?"* of roles six
times. It had never been asked of the organization id. The CI auth suite
could not catch it: the workflow computes `TEST_ORGANIZATION_ID` from the
seeder and injects it, so the tests were handed the answer a real browser
has no way to obtain. The new tests deliberately do not send the header.

**Auth job: passed=11 failed=0 skipped=0**, including
`test_the_organization_from_me_is_accepted_by_a_real_route` — the id
handed out by `/api/me` is spent immediately on a route that enforces
membership, so the circularity is provably broken.

### Migration 023 had never run

Written, reviewed, committed and pushed last session with **no Alembic
revision**. CI applies `alembic upgrade head`, not a glob over
`migrations/*.sql`, so it was applied to no database anywhere. Now wired
as `c5000`, and `tests/test_migration_coverage.py` is the instrument that
would have caught it — verified to fail against the prior state.

### What the two reviewers found, and why both were needed

**Codex (11 findings):** the active tenant was silently reset to the first
organization on every token refresh — a green path writing to the wrong
tenant; `safeReturnTo` bypassable; the SECURITY DEFINER owner unpinned;
`evercoat_worker` granted EXECUTE it never needed; `takeFlow` not
take-once when storage throws; dead `prompt=none` machinery.

**Supervisor (7 findings), including one Codex missed and I missed:**
🔴 **the callback called `window.location.replace()` — a full document
navigation — and the token is memory-only, so it destroyed the session one
statement after creating it. Sign-in could never have worked, and every
test passed.** Now `router.replace()`. Also: sign-out skipped the IdP
logout when no refresh token was issued; StrictMode double-mount consumed
the flow; the `nonce` was sent and never verified; a network failure was
reported as an expired session.

**Eighth session running in which neither reviewer alone was sufficient.**

---

## ✅ S2 IS BUILT AND THE SITE IS DEPLOYED AGAIN

Five list screens now issue real requests: **Projects, Formulations, My
Work, Suppliers, Materials.** New `lib/api/{projects,formulations,tasks}.ts`,
zod-parsed and never cast, behind the existing `Sourced<T>` seam. Six new
Playwright tests drive each screen in a real browser with a row that
appears nowhere in the fixture.

**Live suite against the CURRENT build: passed 25 · failed 0 · skipped 2.**

### Where a live endpoint means something narrower than the fixture did

Each is stated on the screen, not papered over — I14–I17 in `TODO.md`.
Projects lost gate progress / requirement counts / lead; the formulations
index leads with the LATEST version (badged, so a draft says DRAFT) and
lost the computed figures; My Work lost "elsewhere in the organisation";
Suppliers lost sole-source risk and says so in a `role="note"`.

### What the two reviewers caught, and neither caught alone

**Codex — the materials endpoint could never have worked.**
`_with_percentages` stringified the two derived percentages and left every
stored quantity a `Decimal`. FastAPI encodes Decimal as **float**
(`jsonable_encoder(Decimal("1.1000")) -> 1.1`), so a density recorded to
four places went out with one, and the client — which correctly requires
strings — would have rejected **every live material row**. The end-to-end
test could not see it because it STUBS the response with the shape the
client wants. **A test that supplies its own contract cannot detect a
contract mismatch.** Fixed server-side; `tests/test_material_serialisation.py`
asserts the server's half through the real encoder.

**Supervisor — every live row linked to a 404.** The detail screens still
build routes from `generateStaticParams()` over the fixture, so under
`NEXT_OUTPUT=export` a database code has no exported page. `RecordLink`
now links only where a page exists and says why otherwise.

Also fixed: a failed `/api/me` was turning into demonstration data across
every screen; the query cache could serve one user's rows to another;
the demo path used the APPROVED version under a "Latest version" heading;
the sidebar kept a stale count after a failed refetch; six columns lost
their sort buttons; live stage codes were labelled from the fixture's
stage names.

---

## 🔴 FIRST THING TO DO NEXT SESSION

### B4 — Render's push webhook is not firing (root cause still open)

`render-audit` reports the service correct in every respect, and it had
not deployed since **2026-08-18T20:09:24Z** — a day and a half of green
CI on top of a site nobody was updating.

**A manual lever now exists and works:**

```bash
gh workflow run "Deploy web (manual)"
```

`.github/workflows/deploy-web.yml` resolves the service BY NAME, refuses
unless it finds exactly one `evercoat-itw-rd-web`, issues one POST, waits
for a terminal state, then PROVES the edge changed by requiring
`/auth/callback/` to answer 200. Ran it; the site now serves
`last-modified: 2026-08-20 00:50:31 UTC`.

**Reconnecting the GitHub integration in Render's dashboard is the real
fix, and it is the operator's.** Until then, deploy by hand after every
push.

⚠️ **Never** use `render-setup.yml` apply mode to force a deploy — it
issues `DELETE` against **AutoWorkshop** custom domains.

### B5 — why the live site still shows no Sign in button

Not a defect. Three causes, one fixed:

1. ~~The site was serving an 08-18 build.~~ Fixed above.
2. **`render.yaml` sets no `NEXT_PUBLIC_KEYCLOAK_URL`**, and `NEXT_PUBLIC_*`
   is inlined at BUILD time — so the deployed bundle has no identity
   provider and honestly renders "Not signed in" with the reason.
3. **No Keycloak is deployed to point it at.**

Setting the variable without (3) compiles in an address that answers
nothing, which `render.yaml` already argues is worse than an absent one.
The button appears when a Keycloak exists, the variable is set, and the
site is rebuilt. Deploying Keycloak needs a Render web service —
**spend, and the operator's decision.**

**Operator is considering Railway** as an alternative host on cost
grounds. For a fair comparison: the static site costs nothing on Render
today and B4 is a webhook fault, not a billing one. The cost pressure is
entirely the **API + Keycloak** needing paid instances — that is what a
Railway move would actually be about.

---

## Constraints that must not be forgotten

- 🔴 **NEVER propose spending.** The API + Keycloak deploy is blocked on
  Render's free web-service quota. The CI `auth` job exists precisely so
  the work is not blocked on it — and it now passes.
- 🔴 **Do not touch any `aw-*` container.** This project's DB is
  `evercoat-postgres` on port **55432**.
- 🔴 **`RENDER_API_KEY` is still unrotated** since 2026-08-17.
  Dashboard-only; operator action.
- ⚠️ **`autoworkshop-postgres` is FREE tier and EXPIRES 2026-09-01.**
- ⚠️ **Docker on this host is wedged.** CI is the verification path. For
  fast local skips point `TEST_DB_PORT` at a dead port — psycopg's
  default connect timeout is infinite, so `pytest` otherwise hangs.
- ⚠️ **CI has a one-run-per-ref concurrency group.** Pushing evicts an
  in-progress run; do not push while waiting on a result you need.
