# Review + adjudication — public landing page, global marketplace, news feed

**Subject:** `IMPLEMENTATION_PLAN_PUBLIC_LANDING.md` and migration 059 / `r1000`
**Date:** 2026-08-30 · **Base:** `master` `da5c93a`
**Passes:** 2 (owner-capped). Pass 1 Codex read the spec; pass 2 Codex reviewed the plan while the Supervisor pass ran independently.

The raw Codex transcripts were written to `tmp/spec/` which is gitignored; the findings that changed the build are recorded here so the evidence survives.

---

## Codex pass 2 — `CODEX VERDICT: REVISE 1, 2, 5, 6, 8, 9, 10, 11, 12, 13`

| # | Sev | Finding | Disposition |
|---|---|---|---|
| 1 | P1 | View/RLS rationale backwards. An owner-owned view runs with **owner** privilege, so the hazard is a *later join* to a tenant table reading across every tenant anonymously. Dismissing `SECURITY DEFINER` as "cannot identify its caller" was overbroad — a fixed-`search_path` function returning an invariant projection needs no caller identity. | **Accepted, rationale corrected.** Views kept for row/column projection, not because they are intrinsically safer. Enforced by a `pg_depend` probe. |
| 2 | P1 | Privilege test far too narrow. Postgres grants `EXECUTE` to `PUBLIC` on new functions by default; this repo has twice treated that as a live vulnerability (`027:110`, `053:148`). One negative table test passes while the role can call anything. | **Accepted.** Replaced with a full inventory. 🔴 **It failed the migration on first run** — 230 functions matched. |
| 3 | P2 | A separate *database* is materially safer but **Postgres cannot enforce a cross-database FK**, and `public_product_id` needs one. | **Accepted — closes open question 2.** Same database, hardened schema, stated as a measured trade. |
| 4 | P3 | `public_product_id` is not a covert channel today, but the limits must be stated. | **Accepted.** Reverse public projection, public link counts and tenant field exposure explicitly forbidden. |
| 5 | P1 | 🔴 The synthetic-publication CHECK **could not fail**: `NOT (a AND b) OR c` is `NULL` when `c` is NULL, and Postgres accepts a NULL CHECK. | **Accepted.** Every operand `NOT NULL`, explicit boolean logic, and a real publication invariant tying origin + review + provenance. Falsified in the migration. |
| 6 | P1 | Changing `/` breaks more than one spec, **and** sign-in stores the current pathname as `returnTo` (`auth-provider.tsx:541`; callback `page.tsx:175`) — so signing in from the new `/` returns to `/`, not `readLanding()`. The plan's "the preference survives" claim was false. | **Accepted.** A slice must change that flow explicitly. |
| 7 | P3 | The `output: "export"` warning was over-read — the recorded failure was a server `redirect()` with no server. | **Accepted against the author.** Downgraded to a retained smoke test. |
| 8 | P1 | Slice 2 wrote to `access_requests`, a 7th table Slice 1 did not create. | **Accepted.** Moved into Slice 1 (built). |
| 9 | P1 | News link tables deferred while Slice 4 promised a product News tab; and `news_items` columns were never defined, so "nothing dangles" **was not checkable**. | **Accepted.** `news_items` carries nullable FKs to `public_intel.products` and `.manufacturers` only. Material/technology/project filtering explicitly deferred. |
| 10 | P2 | Two guards could pass while the feature was broken (dependency-metadata inspection; "not an error document"). | **Accepted.** Replaced with real anonymous requests asserting a positive projection. |
| 11 | P2 | Two-file migration pattern and Alembic position omitted; `apply_sql` exists to bypass driver placeholder parsing (`:name`, `%`). | **Accepted** (independently found as S1). |
| 12 | P2 | `LOGIN` contradicts 053, which creates connection roles `NOLOGIN` and leaves credentials to deployment. | **Accepted.** Role is `NOLOGIN`. |
| 13 | P2 | Audit and RLS posture absent, not resolved. | **Accepted.** `public_intel` is non-tenanted with no RLS, stated explicitly; the new `competitors.products` column stays under its existing FORCE policy. |

## Supervisor pass (independent, same day)

| # | Sev | Finding |
|---|---|---|
| S1 | P1 | Two migration trees, 58/58 one-to-one; CI runs `alembic upgrade head` and asserts a second run re-applies nothing. "Migration 059" is **two files**. |
| S2 | P1 | **Nine** `goto("/")` call sites across seven specs, not one. |
| S3 | P1 | **No rate limiting exists in this API** — the only mention is a comment recording its absence (`msd.py:57`, I18). Writing "rate-limited" would assert a control that does not exist. |
| S4 | P2 | `security_invoker` is inverted here vs. the house convention in 037. Superseded by C1. |
| S5 | P2 | RLS posture of the new tables unstated. |
| S6 | P1 | `lib/api/client.ts` **cannot construct an anonymous request** — "the types make it impossible". The public surface needs its own client; `client.ts` must not be relaxed. |

## What the review actually changed

Slice 1 grew by a table, a privilege inventory and a view-dependency guard. Two of eight tests were guards that could not fail. The role became `NOLOGIN`. Slice 4's News tab became implementable instead of empty. And an unenforceable CHECK — written hours after this repo catalogued that exact defect class — was caught before a line of application code existed.

**Neither reviewer alone was sufficient**, again: Codex found the NULL CHECK, the `returnTo` flow and the `PUBLIC` EXECUTE default; the Supervisor pass found the two migration trees, the nine `/` call sites, the absent rate limiter and the un-constructable anonymous client.

## Falsification (2026-08-30, against the live database)

```
CASE 1  GRANT USAGE ON SCHEMA core TO evercoat_public
        -> USAGE guard RED, function guard RED (7 core functions reachable)
CASE 2  repoint v_manufacturers at core.users
        -> pg_depend guard RED  [('v_manufacturers','core','users')]
CASE 3  synthetic+published+demo=false -> REFUSE
        synthetic+published+demo=true  -> ACCEPT
        source_derived+published, no source_url -> REFUSE
```

All restored to baseline afterwards.
