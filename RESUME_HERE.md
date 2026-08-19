# ▶ RESUME HERE — EvercoatITWRD APP

**Session 2026-08-19. Read this file, then `TODO.md`.**

Repository: **https://github.com/marc667us/evercoat-itw-rd** (PUBLIC),
branch `master`. Tip **`5cd6d92`**, working tree clean, pushed.

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

## 🔴 FIRST THING TO DO NEXT SESSION — S1 HAS AN ARCHITECTURAL BLOCKER

`TODO.md` S1 says "next-auth Keycloak provider in `apps/web`".
**next-auth cannot run on the deployed artifact.**

- `render.yaml:80` builds with **`NEXT_OUTPUT=export`** and publishes
  **`staticPublishPath: out`** — a Render **static site**, free tier.
- A static export has **no server** and **no route handlers**. There is
  no `apps/web/app/api/` directory at all.
- **NextAuth v5 requires server route handlers** (`app/api/auth/[...nextauth]/route.ts`).
- `next-auth@5.0.0-beta.25` is in `package.json` and **imported by
  nothing** — confirmed again this session.

So S1 as written would work locally and in CI and **would still leave
the deployed site with no sign-in**, which is S1's own exit condition.

**The zero-cost option that fits the deployment:** a browser-side
**OIDC Authorization Code flow with PKCE** against Keycloak's existing
public `evercoat-web` client. That works in a static export, needs no
server, costs nothing, and is architecturally sound here because
`CLAUDE.md` §6 already states frontend checks are cosmetic and the API
re-enforces every decision server-side.

**The alternative is a Render web service, which is spend, which is the
operator's decision and must never be proposed.**

This needs an ADR and an operator decision before S1 starts. Do not
silently build next-auth against a static export.

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
