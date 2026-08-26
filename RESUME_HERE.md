# ▶ RESUME HERE — EvercoatITWRD APP

## ▶▶ SESSION 2026-08-26 (part 2) — I105 CLOSED

Migration **048 (`g1000`)**, **ADR-030**. API suite **750 / 0 / 11**; ruff,
format, mypy clean.

**I105 is closed.** `core.authorization_for_current_session()` derives the
caller's roles AND permissions from the same two GUCs RLS reads, and
`AgentPrincipal.authorize()` replaces both sets with its answer. The gate and
the rows can no longer disagree about who is asking.

🔴 **It is not the design ADR-029 rejected**: that rejection was about a
definer that WRITES (the write fires ADR-028's guards as owner and reopens
I83). This one is `STABLE` with a single-SELECT body and takes **zero
arguments** — no write to start the chain, no parameter to aim it with.

### 🔴 A PUSH TO `master` DID NOT TRIGGER CI

Actions enabled, commit on GitHub as head, triggers `branches: [master, main]`
— and **no run in ~20 minutes**. `gh workflow run ci.yml --ref master` started
one immediately, so the runner is fine and the push event missed.

⚠️ **CHECK THE RUN'S `headSha` AGAINST YOUR TIP.** `gh run list` puts the
previous commit's green run at the top, which reads as success. That is the
shape `ci.yml`'s own comment warns about: *a workflow that reports nothing
while it happens.*

### ⚠️ WHAT IS STILL OWED

**The I56/I58 FORCE cutover's effect on this function is UNMEASURED.** The
test was written and withdrawn — `ALTER TABLE ... FORCE` needs ACCESS
EXCLUSIVE on six shared `core` tables and hangs against a live API pool
(`lock_timeout` and fixture rollback both insufficient; killed at 120s;
reproduced independently). Measure it **during** the cutover, when those
tables are being altered anyway.

### ▶▶ NEXT — I82

`core.user_id_for_subject(TEXT)` hands out a uuid for an arbitrary subject —
**the oracle shape ADR-030 deliberately avoided by taking no arguments.**
🔴 Its original fix is REJECTED on evidence (ADR-029). ⚠️ **But re-measure
that rejection before designing around it:** ADR-029's mechanism was a
definer's WRITE firing ADR-028's guards as owner, and **047 then made both
guards scope-explicit**, which may have removed the reason. Measure it; do not
assume in either direction.

Then: I76/I77 · I56/I58 (with the owed measurement above) · I78 · I101 ·
**D1 on/after 2026-09-01** — do NOT delete `autoworkshop-postgres` early.

---


## ▶▶ SESSION 2026-08-26 — I104 CLOSED, INTELLIGENCE SHIPPED, I105 RAISED

Tip **`2d343c3`** on `master`, pushed, tree clean, 0 ahead / 0 behind,
**CI 6/6 green** (run 32982603290 on `e8cd7fd`) — Auth, API image, Security
scan, E2E, Web lint/type/test, API lint/type/test. Semgrep, which is CI-only
and has blocked a locally-green commit before, passed on the new raw SQL in
`app/domains/analytics/service.py`.

Closed today: **I104** (the orchestrator trusted its arguments),
**MSD's orchestration layer** (three of four doors went around the governed
one), and **`analytics.view` / `analytics.portfolio`** — held by nine and two
of ten seeded roles and read by **no line of code** until now.

**Intelligence has a browser surface**: `/analytics` and `/reports`.
`GET /api/analysis/reports/test-results` shipped on 08-25 with **no browser
caller at all** — the twenty-fourth orphaned route, one day after
twenty-three were closed.

### ▶ LIVE SUITE ON THE DEPLOYED DEMO — three numbers, one complete run

| phase | passed | failed | skipped |
|---|---|---|---|
| `api-live` | **747** | 0 | 0 |
| e2e (Playwright `shell`) | **37** | 0 | 0 |
| **TOTAL** | **784** | **0** | **0** |

Preflight reported all four capabilities **CONFIGURED**, so these numbers
cover the whole suite rather than a partial one — no `--allow-partial`.
Counts read from each tool's own summary line (`747 passed ... in 180.16s`),
not from the harness.

🔴 **AND THE NEW SCREENS WERE DRIVEN IN A REAL BROWSER**, recorded
`STATUS expected` in Playwright's own detail file — exercised, not merely
un-skipped:

    shell/navigation.spec.ts :: Analytics is an enabled link and the page renders
    shell/navigation.spec.ts :: Reports is an enabled link and the page renders
    shell/navigation.spec.ts :: neither Intelligence screen invents a figure when it has no data
    shell/sign-in.spec.ts    :: a person can press Sign in, authenticate, and come back signed in

e2e went 34 → 37: exactly the three tests added. `api-live` 720 → 747.

**Demo URL:** `https://radios-mayor-reduces-overcome.trycloudflare.com`
(users `lead.demo` … `exec.demo` / `EvercoatDemo-2026!`,
org `c6031e4b-eff3-4aa6-a87b-697b6941c6e9`).

🔴 **THE TWO ANALYTICS GATES, MEASURED ON THE DEPLOYED API, NOT ASSERTED:**

| user | role | analytics | report | by_project |
|---|---|---|---|---|
| `chem.demo` | chemist | 200 | 200 | **null** |
| `proc.demo` | procurement_specialist | 200 | **403** | null |
| `dir.demo` | director | 200 | 200 | **1** |
| `exec.demo` | executive_viewer | 200 | **403** | **1** |
| `tech.demo` | laboratory_technician | **403** | 403 | — |

`executive_viewer` is the proof the two permissions are independent gates: it
gets the portfolio and is refused the report. `laboratory_technician` holds
`project.view` and is still refused, so `analytics.view` is not `project.view`
under another name.

### ▶▶ EXACT NEXT ACTION — I105

🔴 **`bind()` VALIDATES IDENTITY AND NOT PERMISSIONS.**
`AgentPrincipal.bind()` asks PostgreSQL whether `app.current_org` /
`app.current_user_id` match the caller. It does **not** validate
`caller.permissions`. A forged principal carrying the real session identity
therefore passes `bind()` while claiming arbitrary authorization, and the
conductor gate consults the forged set. **Codex named this exactly and it is
the half of I104 that is not closed.**

The fix is to derive the effective permission set from the GUC-bound user at
the bound-session boundary and gate on that. 🔴 **It is a design task, not a
patch:** it needs a `SECURITY DEFINER` returning permissions for a user id,
which is the shape **ADR-029 rejected on measured evidence** for I82 — an
atomic bind inside a definer re-opened I83. **Do I105 and I82 together, with
the I83 precedent in front of you.**

### 🔴 What the AgentPrincipal type is worth — measured, not assumed

Codex enumerated four forgeries. All four were **reproduced against the real
code**; three are closed (exact type check; the guard is a nonce consumed on
use, so `dataclasses.replace` can no longer replay it; no long-lived sentinel
to import). **`object.__new__` remains open, cannot be closed in Python, and
has a test asserting it stays open** — so that closing it quietly cannot
re-inflate the docstring's claim.

The module now says plainly that it is a **misuse barrier, not an in-process
security boundary**. The first version said "you cannot construct one from
loose values" and you could, which is this repository's most-repeated defect
sitting on top of its authorization boundary.

### 🔴 Lessons from today

> **A SET COMPARISON CANNOT COUNT.** My test read
> `_route_permissions("msd.py") == {"msd.use"}` and stayed GREEN with one of
> four routes ungated — the other three contributed the same element. The
> ungated route was invisible to the test written to find it.

> **A TEST A COMMENT CAN REDDEN IS A TEST NOBODY TRUSTS** — mine failed on
> its own explanation. The inverse, a comment SATISFYING an assertion, is the
> same failure and the more dangerous direction.

> **AN UNCAST `:x IS NULL` BIND FAILS ONLY ON THE UNFILTERED CALL** — which
> is the call a browser makes by default. Caught by
> `tests/test_no_untyped_null_binds.py` on the day the query was written,
> because that rule is instrumented rather than restated.

> **`.get()` RETURNING A DEFAULT IS HOW A WRONG NUMBER SURVIVES REVIEW.** Two
> analytics counts were over fields the rows do not carry; both would have
> read `{"unknown": n}` — correct-looking, plausible, meaningless.

> **A SCREEN THAT INVENTS ITS TRUNCATION LIMIT IS WORSE THAN ONE THAT HIDES
> IT.** `capped at {"200"}` was a literal matching the default request;
> `?limit=10` would have been reported under a cap of 200. Raised by Codex.

---

## SESSION CLOSE 2026-08-25 (part 5)

Tip **`e9e471e`**, pushed, **CI 6/6 green**.
Closed today: **I100**, **I83**, **I81**, **I102** — and §0.2's conductor tier
is complete.

▶ **Live suite on the deployed demo — three numbers, ONE complete run:**

| phase | passed | failed | skipped |
|---|---|---|---|
| `api-live` | **716** | 0 | 0 |
| e2e (Playwright `shell`) | **34** | 0 | 0 |
| **TOTAL** | **750** | **0** | **0** |

Both sign-in tests recorded as `STATUS expected` — exercised, not un-skipped.

⚠️ **The API process must be restarted after any change under `apps/api/app/`.**
`scripts/demo-up.ps1` starts it detached; the conductor work needed a restart
and the I81 work did not (grants only). Check the LISTENER on :18000, not the
log.

---

### ✅ I102 CLOSED — the suite locked itself out and blamed the password

The realm sets `bruteForceProtected: true`, `failureFactor: 5`, and the auth
tests made **twelve** direct-grant calls per run. The client was told
*"invalid_grant — Invalid user credentials"* with the CORRECT password, while
Keycloak's log said `error="user_temporarily_disabled"`.

🔴 **Keycloak returns the same error for a lockout as for a wrong
password.** Fixed two ways: `_token()` caches per username, and
`live-suite.sh` clears the lockout before each run — **hygiene, not
coverage**, so it warns and proceeds rather than failing the preflight.
Proven by deliberately locking `lead.demo` and running 750/0/0 from that
state.

---

### ✅ §0.2's conductor tier is complete

Four departments: **laboratory**, **testing**, **MSD**, and a new
**analysis**. Each is structural — a permission gate plus dispatch to the
domain service — with `app/agents/boundary.py` owning §7's rule that the
agent tier runs under the caller's own authorization boundary.

🔴 **AND THE REVIEW FOUND MY GATE GUARDED A DOOR NOBODY USED.**
`msd_conductor`'s `explain_result` called the testing tool with **no**
permission check, so `msd.use` without `test.view` returned raw replicates,
statistics and the final disposition. I wrote a testing conductor gating on
`test.view` and the real path went around it. **The third instance of that
shape in that file**, after `knowledge.view` and `formula.view_cost` — the
precedent was thirty lines below the bug. Now gated, falling through to the
refusal as `knowledge_search` does.

Two more, one of which I caught first: the analysis department was gated on
`analytics.view` while the route has always required `project.view`, and
measured against the seeded roles those come apart **both ways** — a
`procurement_specialist` would have been *granted* a dashboard the route
refuses. And omitting `held_permissions` returned the same dashboard with
panels silently missing.

---

### ▶▶ EXACT NEXT ACTION — I103

🔴 **Nothing routes through the new conductors.** The three orchestrator
entry points have no callers; routes still reach their domain services
directly. Codex raised it and it is true: **a layer with no caller is the
same defect as a route with no caller.** Either route something through it —
the obvious candidate is `app/api/dashboards.py`, whose permission the
analysis conductor now matches exactly — or state plainly what the tier is
for and stop implying it is the single door.

Then **I104** (the orchestrator trusts its `permissions`/`user_id`
arguments), **I82**, I76/I77, I56/I58, I78, I101, and **D1 on or after
2026-09-01**.

---

### Carried forward

* ⚠️ **Do not run the live e2e beside pytest or Codex** — Chromium dies with
  `0xC0000142` on this 8 GB host and the failures read like app defects. **A
  crashed worker is a VOID measurement.**
* ⚠️ **`scripts/live-suite.sh` holds a deliberate literal CR** inside
  `$'<CR>'` — read/write it with `open(..., newline="")`.
* ⚠️ **Local migrations run as `postgres`**; password in the container env.
  Local is superuser, **Render is not**.
* ⚠️ **A column-level REVOKE against a table-level GRANT does nothing.**
* ⏳ **D1 waits for 2026-09-01.** Do NOT delete `autoworkshop-postgres` early.

---

## ▶▶ SESSION CLOSE 2026-08-25 (part 4) — START HERE

Tip **`d929293`**, pushed, **CI 6/6 green**. I100, I83 and I81 all closed today.

▶ **Restart the demo — one command:**
`powershell -File scripts\demo-up.ps1`. The stack has been up all session;
only the API process was restarted (for I83), and I81 changed no application
code at all — it is grants and a function body.

▶ **Live suite on the deployed demo — three numbers, ONE complete run:**

| phase | passed | failed | skipped |
|---|---|---|---|
| `api-live` | **702** | 0 | 0 |
| e2e (Playwright `shell`) | **34** | 0 | 0 |
| **TOTAL** | **736** | **0** | **0** |

---

### ✅ I81 CLOSED — an authentication identifier is not a readable column

Migration **047 / f2000**, **ADR-029**.

044's read policy hands over the whole `core.users` row where its
justification — attribution in eleven joins — needs only the name.

🔴 **THE OBJECTION WAS MEASURED, NOT ACCEPTED, AND IT WAS TWO-THIRDS
RIGHT.** `display_name` has eleven readers. `email` has **two production paths
that deliberately return it** — `admin.list_members`, and
`projects.list_members`, which documents that it lists FORMER members on
purpose — so removing it would break stated behaviour. `keycloak_sub` is read
by **no application query anywhere**. Only that one is over-granted, and RLS
cannot take a column away; column privileges can.

⚠️ **A column-level REVOKE against a table-level GRANT does nothing.** The
table grant must be dropped and replaced by an explicit column list. Written
the other way the migration reads exactly like a fix and changes nothing —
which is why the test asserts the PRIVILEGE, not the SQL.

Sign-in is unaffected because the three readers are owner-owned SECURITY
DEFINER functions. That is an argument, so it is also a test.

---

### 🔴 What the review round found

**Codex: FAIL, one blocker.** I had reached it independently; Codex supplied
the consequence I had not stated.

* **I granted a CROSS-TENANT WRITE while removing a cross-tenant read.** The
  first draft granted `UPDATE (email, display_name, status)`. `status` was
  speculative — the same reflex 047 exists to correct on `keycloak_sub`.
  `core.users` is GLOBAL, so a session scoped to ONE shared organization
  could set a multi-organization user to `inactive` and disable that identity
  **in every other tenant**. Now `(email, display_name)`, pinned by a test.

Non-blockers, all acted on: the claim was broader than the code (047 makes
the value unreadable, it does **not** make subject existence confidential —
that residue is I82); a future view projecting `keycloak_sub` would inherit
001's default privileges and hand it straight back, so a test now watches for
one; the downgrade left 047's COMMENT sitting on f1000's body; the 044 upsert
assertion accepted any "permission denied"; and two tests that cannot fail
when 047 is reverted now say so in their own docstrings.

🔴 **And measuring I82 found 046's rename guard was scoped by the CALLER,
not by itself.** Its `mine` side relied on the RLS policy, and a trigger runs
as whatever the current user is — inside a SECURITY DEFINER owned by the
table owner, that user bypasses RLS. Measured: `INVOKER path ACCEPTED` /
`DEFINER path REFUSED`, refusing on another tenant's row, which makes the
refusal a cross-tenant existence answer — I83 rebuilt inside its own
replacement. The predicate is explicit now.

⚠️ **My first probe tested the OTHER trigger and came back clean.** Check
which mechanism is load-bearing before a comment credits one.

---

### 🔴 I102 — the live suite can lock itself out, and the failure lies

Found during this task's live run, which reported **700 passed / 2 failed**:

    "Keycloak refused the direct grant for lead.demo:
     401 invalid_grant — Invalid user credentials"

The password was correct. Keycloak's own log, same second:

    type="LOGIN_ERROR" error="user_temporarily_disabled" username="lead.demo"

The realm sets `bruteForceProtected: true`, `failureFactor: 5`,
`permanentLockout: false`, `maxFailureWaitSeconds: 900`, and the suite
authenticates the same user repeatedly by direct grant — so one slow or
timed-out run trips the lock and everything after it is refused with a message
that says *wrong password*. **That makes the standing live-test rule
non-deterministic and its failures misleading.**

Cleared by hand and the suite then ran 736/0/0:

```bash
TOK=$(curl -s -X POST "$U/auth/realms/master/protocol/openid-connect/token" \
  -d client_id=admin-cli -d username=admin -d password=demo-admin-pw \
  -d grant_type=password | python -c "import json,sys;print(json.load(sys.stdin)['access_token'])")
curl -X DELETE "$U/auth/admin/realms/evercoat/attack-detection/brute-force/users" \
  -H "Authorization: Bearer $TOK"        # 204
```

**It is now task 1.** Two honest fixes: clear the lockout in `live-suite.sh`
before the run, and/or mint one token per user per session instead of one per
test.

---

### ▶▶ EXACT NEXT ACTION

**I102** — make the live suite deterministic, per above. It is small, and
everything else this project measures depends on those three numbers meaning
something.

Then **I82**, whose proposed design is now recorded as **rejected on
evidence** in ADR-029 — an atomic bind inside a SECURITY DEFINER would have
re-opened I83. It needs a different design, not the one in the plan.

Then I76/I77, I56/I58, I78, I101, and **D1 on or after 2026-09-01**.

---

### Carried forward

* ⚠️ **Do not run the live e2e beside pytest or Codex.** Chromium crashes on
  this 8 GB host with `0xC0000142` and the failures read like application
  defects. A crashed worker is a VOID measurement, not a red.
* ⚠️ **`next build` rewrites `apps/web/tsconfig.json` every demo build.**
* ⚠️ **Local migrations run as `postgres`**; the superuser password is in the
  container environment. Local is superuser, **Render is not**.
* ⏳ **D1 waits for 2026-09-01.** Do NOT delete `autoworkshop-postgres` early.

---

## ▶▶ SESSION CLOSE 2026-08-25 (part 3) — START HERE

Tip **`552112d`**, pushed, **CI 6/6 green**. Two commits, both I83.

▶ **Restart the demo — one command:**
`powershell -File scripts\demo-up.ps1` (prints the URL, writes
`tmp/tunnel_url.txt`). The stack has been up since part 1; only the API
process was restarted, to put the I83 fix on the deployed instance before the
live suite ran.

▶ **Live suite on the deployed demo — three numbers:**

| phase | passed | failed | skipped |
|---|---|---|---|
| `api-live` | **693** | 0 | 0 |
| e2e (Playwright `shell`) | **34** | 0 | 0 |
| **TOTAL** | **727** | **0** | **0** |

693, not 682: eleven auth-integration tests that need a live Keycloak run
here and skip locally, and eleven new tests shipped with I83.

---

### ✅ I83 CLOSED — the cross-tenant email existence oracle

Migration **046 / f1000**, **ADR-028**.

`core.users.email` carried `users_email_key`, **globally unique** — and unique
constraints are enforced **outside RLS**. Measured as `evercoat_app` scoped to
organization A: inserting an address held in organization B was **REFUSED**,
an unused address **ACCEPTED**. The route turns those into **409** and
**201**, so any `admin.users` holder in any tenant read platform-wide
existence from a status code, with a throwaway subject and no row left behind.
Squatting confirmed in the same run.

🔴 **The constraint is dropped, not disguised.** Migration 044 had
already made that refusal generic and **the oracle survived**, because the
attacker reads the status code. A creating endpoint cannot make *created*
indistinguishable from *not created*. Identity is `keycloak_sub`; the address
is an attribute mirrored from the identity provider.

**Replaced by two SECURITY INVOKER constraint triggers**, both advisory-locked:
`organization_members_one_address_per_organization` (the INSERT path) and
`users_address_stays_unique_in_organization` (the rename path).

---

### 🔴 What the review round found — the replacement was not a constraint, twice

**Codex: FAIL, three blockers.**

* **A trigger that decides by SELECT is not a unique index.** Found
  independently before Codex answered. Two concurrent transactions both
  committed and one organization ended with two active members at one address
  — measured on two connections. My own comments and ADR-028 said
  *"enforced"*. `pg_advisory_xact_lock` on (organization, address) is the
  mechanism, the same one `audit.chain_row()` has used since 013.
* **A rule enforced on INSERT and not on UPDATE.** Codex's catch, and the one
  I missed. The address lives on `core.users` and the trigger was on
  `core.organization_members`; `UPDATE core.users SET email = <a colleague's
  address>` was **ACCEPTED** with no membership row moved. On that path 046
  was **weaker than the constraint it removed**, because `users_email_key`
  covered updates.
* **The tests certified the rule while permitting both counterexamples.**
  Three added, each falsified by removing its mechanism.

🔴 **And the question Codex did not ask: does the replacement answer
across tenants?** A guard that refuses on a row you cannot see is the oracle
rebuilt inside its own replacement. Proven with a user active in BOTH
organizations, renamed onto an address held only in the one the caller cannot
see: **ACCEPTED**. It misses rather than answers — the trade ADR-028 now
states plainly instead of glossing.

---

### Also found while falsifying

* 🔴 **`test_023_messaging`'s fixture leaked an identity every run for
  months** — it deleted `author` and `outsider` and not `member`. **595
  orphaned rows against 782 users**, so any measurement over `core.users` is
  mostly measuring test debris. Fixed; the debris is now **I101**.
* 🔴 **A fixture that could DEADLOCK the suite.** A failing test never
  reaches its final `rollback()`, and its row locks then block the owner-side
  cleanup `DELETE` forever. It wedged exactly that way and had to be killed.
  A suite that hangs on a failure never reports the failure.
* ⚠️ **`INSERT ... RETURNING id` fails for a brand-new identity** —
  `RETURNING` applies 044's SELECT policy and a user with no membership is
  invisible to the connection that just created it.
* ⚠️ **`SET LOCAL app.current_org = :param` is a syntax error.** Use
  `set_config`, as `app/core/db.py` already says.

---

### ▶▶ EXACT NEXT ACTION

**I81 / I82.** 044's read policy grants the whole row where its justification
needs only the display name — every one of the eleven joins that resolve an
actor selects `display_name` and none selects `email` or `keycloak_sub`, so
the policy hands out contact details and an authentication identifier for a
former member of your own organization. I82's narrower design — fold subject
resolution into a single atomic bind so the uuid is returned only after the
membership exists — changes the route's transaction shape, which is why the
two belong together.

Then: I76/I77, I56/I58, I78, I101, and **D1 on or after 2026-09-01**.

⚠️ **I56/I58 now has more in scope.** 046 adds two SECURITY INVOKER trigger
functions that read `core.users` and `core.organization_members`. Under FORCE
RLS they must still see their own tenant's rows, or the address guards
silently stop guarding.

---

### Carried forward

* ⚠️ **`next build` rewrites `apps/web/tsconfig.json` every demo build.**
* ⚠️ **Local migrations run as `postgres`** (`alembic_version` denies
  `evercoat_owner`); the superuser password is in the container's environment.
  Local is superuser, **Render is not**.
* ⏳ **D1 deploy waits for 2026-09-01.** Do NOT delete `autoworkshop-postgres`
  early — its app data is unarchived.
* 🔴 **THE E2E SUITE CRASHED TWICE ON HOST PRESSURE, AND THE FAILURES LOOKED
  LIKE APPLICATION DEFECTS.** `browserContext.newPage: Target crashed`, then
  `worker process exited unexpectedly (code=3221225794)` — that is
  `0xC0000142`, STATUS_DLL_INIT_FAILED, a process failing to initialise.
  Reported **721/6/2** and then **700/7/22** with sign-in among the
  casualties. The same two sign-in tests then passed **in 30 seconds in
  isolation**, and the whole shell project passed 34/34 alone. Nothing was
  wrong with the application. ⚠️ **Do not run the live e2e beside pytest
  suites or Codex** — this host is 8 GB with Docker holding ~900 MB, and
  Chromium loses. Run it alone, and treat a crashed worker as a VOID
  measurement rather than a red.

---

## ▶▶ SESSION CLOSE 2026-08-25 (part 2) — START HERE

Tip **`8edee9b`**, tree clean. Two commits, both I100.

▶ **Restart the demo — one command:**
`powershell -File scripts\demo-up.ps1` (prints the URL, writes
`tmp/tunnel_url.txt`). The stack from part 1 was still up at the start of
this session and was never restarted.

▶ **Live suite on the deployed demo — three numbers:**

| phase | passed | failed | skipped |
|---|---|---|---|
| `api-live` | **682** | 0 | 0 |
| e2e (Playwright `shell`) | **34** | 0 | 0 |
| **TOTAL** | **716** | **0** | **0** |

Run twice, before and after the review round; identical both times. Counts
read from each tool's own summary line.

🔴 **AND FOR THE FIRST TIME THOSE NUMBERS DEFEND THEMSELVES.**
`tmp/live-suite/e2e-detail.txt` records both tests in `sign-in.spec.ts` as
`STATUS expected` — the flow was EXERCISED, not merely un-skipped. The
incantation is now in `CLAUDE.md` §13; the script refuses to run without it.

---

### ✅ I100 CLOSED — the suite no longer reports green over coverage it lacks

Every green number this script had ever printed depended on environment
variables typed by hand. It exported none and checked none, so running it as
`CLAUDE.md` documented it gave **290 passed / 0 failed / 392 skipped**: a
zero-failure report over 290 of 682 tests, sign-in never exercised.

`scripts/live-suite.sh` now opens with a **PREFLIGHT** that names every
capability, the variables it needs and the tests it governs, and classifies
each one:

| | meaning | if it happens |
|---|---|---|
| **CONFIGURED** | every variable present | if its tests skip anyway that is a **FAILURE**, not a gap — the promise is closed after the run, because only the run knows whether the credentials, database name or realm users were right |
| **ABSENT** | none present | a legitimate absence is possible — a deployed site has no local database — so it fails unless the operator passes `--allow-partial`, which **names every gap in the report** |
| **PARTIAL** | some present | **always** a hard failure. Nobody half-configures a capability on purpose, and a half-configured one skips exactly like an absent one while looking, at the prompt, like it was set up. `--allow-partial` does not cover it |

**Not defaults.** Hard-coding `TEST_DB_PORT=55432` would aim the suite at
whatever database the author had in mind and call the result live coverage.

Two probes separate absence from misconfiguration:

* a database **answering at an address this run is already configured to
  use** — parsed out of `DATABASE_URL`, not a guessed port list — while
  `db-suite` is unset. Unwaivable.
* `db-suite` set but **nothing answering** on `TEST_DB_HOST:TEST_DB_PORT`.
  That is the exact 290/0/392 shape, now caught in three seconds.

After the run: pytest's `-rs` reasons are printed instead of buried in a log
nobody opened; a CONFIGURED capability that skips anyway is counted FAILED;
the Playwright projects that ran are read from **Playwright's own report**
(`--project=api` does not exist in LIVE mode); every skipped e2e test is
listed by file; and capability-level skips are NAMED — `1 skipped` used to
stand for 682 absent tests.

---

### 🔴 What the reviewers found — seventeenth session, neither alone was enough

**Codex: FAIL, two blockers.**

* 🔴 **My own comment asserted a rule the code did not implement.**
  *“`--allow-partial` does NOT cover a database that is present but
  unused”* sat one screen above code that probed three hard-coded ports. A
  database on 15432 answers none of them. Fixed by DERIVING the probe from
  `DATABASE_URL`; falsified with a listener on `127.0.0.1:15432`, which the
  preflight names and no port list would have reached. This is the
  repository's most repeated defect and I had just written another one.
* **A guard that passed when it could not see.** The sign-in guard grepped
  for a skip; an empty detail file — dead parser, missing python, spec never
  collected — produced no skip and therefore no complaint about a flow it
  never looked at. **Found independently by my own Supervisor pass before
  Codex answered.** Both directions are asserted now, falsified four ways.

Non-blockers, all real and all fixed: `tcp_answers` interpolated unvalidated
values into `bash -c` (proven: `TEST_DB_PORT='55432; touch /tmp/pwned'` is
refused and no file appears); its fallback is unbounded without `timeout`,
now announced rather than denied; the skip-reason guards grepped the whole
log where a traceback carrying the same phrase would fail the run, and now
ask pytest's `-rs` lines; and `e2e-detail.txt` was truncated inside the
parser rather than before it, so with python absent the guards would have
read the **previous** run's file — `tmp/live-suite/` still holds an artifact
from 08-18.

🔴 **AND MY OWN PREFLIGHT UNDERSTATED WHAT ITS ABSENCE COSTS**, which is a
quieter version of the defect it exists to catch. `db-suite` was labelled
*“tests/db — 341 tests”* because that is what collection said. Measured:
`tests/auth/conftest.py` uses the same fixtures, and `pytest tests/auth`
without them reports **12 passed / 58 skipped**. The run that exposed I100
skipped **392**. Corrected everywhere it appears.

> **Falsify the guard, not the happy path.** Eleven runs, each removing one
> thing: nothing set → 5 failures, all named; `TEST_DB_PORT` alone unset →
> PARTIAL, `--allow-partial` refused; db block unset + `--allow-partial` →
> still fails, a database answers; db set on the wrong port → fails;
> `TEST_KEYCLOAK_PASSWORD` unset → fails twice; whole auth block unset +
> `--allow-partial` → proceeds with both gaps named; and the sign-in guard
> exercised in four states in isolation.

---

### ▶▶ EXACT NEXT ACTION

**I83 (P1) — the cross-tenant email existence oracle.** `core.users.email` is
`citext` with a **globally unique** constraint, and unique constraints are
enforced OUTSIDE RLS: a holder of `admin.users` in any tenant can POST
`/api/admin/members` with a throwaway `keycloak_sub` and read existence from
201 vs 409. Emails are guessable where a subject UUID is not. The probe
leaves no row behind, so it repeats without limit, and it doubles as a
squatting path. **It needs a schema decision, not a patch** — the two honest
remedies are in `TODO.md` under I83. I81/I82 fold into whichever is chosen.

Ranked queue after that: I81/I82, I76/I77, I56/I58, I78, then **D1 on or
after 2026-09-01**.

---

### Carried forward

* ⚠️ **`next build` rewrites `apps/web/tsconfig.json` every demo build.**
  Still undecided: commit the generated form, or ignore it.
* ⚠️ **Local migrations run as `postgres`** — `alembic_version` denies
  `evercoat_owner`. Local is superuser, **Render is not**; 09-01 meets this.
* ⏳ **D1 deploy waits for 2026-09-01.** Do NOT delete
  `autoworkshop-postgres` early — its app data is unarchived.
* ⚠️ **A misconfigured run is SLOW, not just wrong.** Each connection to a
  dead port costs ~21s here, so the 290/0/392 run crawled. If a suite is
  inexplicably slow, check what it is failing to connect to.

---

## ▶▶ SESSION CLOSE 2026-08-25 — START HERE

Tip **`2d26b2a`**, pushed, tree clean, **CI 6/6 green**. Eight commits.

▶ **Restart the demo — one command:**
`powershell -File scripts\demo-up.ps1` (prints the URL, writes
`tmp/tunnel_url.txt`). 🔴 **The launcher was BROKEN TWO WAYS at the start of
today and one half had never run at all** — both fixed, see I99 below.

▶ **Live suite on the deployed demo — three numbers:**

| phase | passed | failed | skipped |
|---|---|---|---|
| `api-live` | **682** | 0 | 0 |
| e2e (Playwright `shell`) | **34** | 0 | 0 |
| **TOTAL** | **716** | **0** | **0** |

Counts read from each tool's OWN summary line.

---

### 🔴 READ THIS FIRST — I100: THE LIVE SUITE REPORTS GREEN WHILE MOST OF IT NEVER RUNS

**Every number above depends on environment variables I supplied BY HAND.**
`scripts/live-suite.sh` exports none of them. Run it as documented and you get
a confident green covering **290 of 682** tests with sign-in unverified.

Three independent gaps, none of them a code defect:

1. **`tests/db/conftest.py` reads `TEST_DB_PORT`, defaulting to `5432`** — this
   machine's database is on **55432**. It times out and **skips**. First run
   today: **290 passed / 0 failed / 392 skipped.** 392 of 682 tests silently
   absent, zero failures reported.
2. **`tests/e2e/shell/sign-in.spec.ts` self-skips without
   `TEST_KEYCLOAK_PASSWORD`** — so the test written on 08-24 *specifically to
   stop sign-in breaking silently* **does not run in the live suite that
   exists to catch it.** Its own header says so: *"if the round trip skips in
   a LIVE run, the sign-in flow was NOT verified."*
3. **`--project=api` does not exist against a deployed URL**
   (`Available projects: "shell"`), so any total assuming both Playwright
   projects ran is wrong. Live browser coverage is the 34 `shell` tests; the
   deployed API surface is `api-live`.

**The incantation that actually works** (also at `RESUME_HERE.md` §db-suite):

```bash
cd apps/api
TEST_DB_HOST=localhost TEST_DB_PORT=55432 POSTGRES_DB=evercoat_itw_rd \
TEST_OWNER_USER=evercoat_owner TEST_OWNER_PASSWORD=ci-owner \
APP_DB_USER=evercoat_app APP_DB_PASSWORD=ci-app \
DATABASE_URL="postgresql+psycopg://evercoat_app:ci-app@localhost:55432/evercoat_itw_rd" \
KEYCLOAK_ISSUER="<tunnel>/auth/realms/evercoat" LIVE_BASE_URL="<tunnel>" \
TEST_KEYCLOAK_URL="<tunnel>/auth" TEST_API_URL="http://localhost:18000" \
TEST_KEYCLOAK_PASSWORD='EvercoatDemo-2026!' \
TEST_ORGANIZATION_ID='c6031e4b-eff3-4aa6-a87b-697b6941c6e9' \
python -m pytest tests -m "live or not live" -q --no-header -rs
```

```bash
TEST_KEYCLOAK_PASSWORD='EvercoatDemo-2026!' \
PLAYWRIGHT_BASE_URL="<tunnel>" npx playwright test --project=shell
```

▶ **THE FIX IS TO MAKE THE SCRIPT DEMAND WHAT IT NEEDS AND FAIL LOUDLY**, not
to remember to export it. That is the top task next session.

#### ▶▶ EXACT NEXT ACTION — the I100 fix, designed but NOT started

Nothing has been changed. `scripts/live-suite.sh` is untouched (587 lines) and
the tree is clean at `2d26b2a`. Resume by editing that file:

**Add a PREFLIGHT section after the profile block (~line 146, before
`echo " LIVE SUITE -- "`)** that names every capability and what its absence
costs, then decides:

| capability | required env | if missing |
|---|---|---|
| api-live imports | `DATABASE_URL`, `KEYCLOAK_ISSUER` | already handled at `run_pytest` (~line 248) — but it counts **one** skip for **392 tests** |
| `tests/db/*` | `TEST_DB_HOST` `TEST_DB_PORT` `POSTGRES_DB` `TEST_OWNER_USER` `TEST_OWNER_PASSWORD` `APP_DB_USER` `APP_DB_PASSWORD` | **392 tests skip silently** |
| sign-in round trip | `TEST_KEYCLOAK_PASSWORD` | **the flow is NOT verified** |
| auth integration | `TEST_KEYCLOAK_URL` `TEST_API_URL` `TEST_KEYCLOAK_PASSWORD` `TEST_ORGANIZATION_ID` | 11 tests skip |

🔴 **THE DESIGN DECISION THAT MATTERS.** Do **not** simply export defaults —
against a genuinely deployed site there is no local database, so those 392
tests legitimately cannot run, and hard-coding a port would aim the suite at
whatever database the author had in mind. Instead:

1. **Preflight prints a coverage table** — each capability CONFIGURED or
   ABSENT, with the test count it governs.
2. **Half-configured is a hard FAIL**, because it is a misconfiguration rather
   than a legitimate absence: if a database ANSWERS on `TEST_DB_PORT` (or on
   55432) while the test variables are unset, exit non-zero and say so.
3. **`TEST_KEYCLOAK_PASSWORD` unset must not report success.** Either exit
   non-zero, or require an explicit `--allow-partial` flag to proceed — the
   suite must never print a clean three-number report while the sign-in round
   trip skipped.
4. `run_pytest`'s current gate counts **one** skip for a whole suite. Make the
   skip count reflect the tests actually not run, or name them; `1 skipped`
   for 392 absent tests is the number that hid this.

**Verify by falsification, as everything else this session was:** run it with
each variable removed in turn and confirm it FAILS and names the gap. A
preflight that cannot fail is the third guard this session that read as
verification and was not.

**The 11 auth integration tests that had NEVER ONCE RUN now run and pass.**
`evercoat-test` was already in the realm as a public direct-grant client; the
demo org is `c6031e4b-eff3-4aa6-a87b-697b6941c6e9` (`EVERCOAT-DEMO`, all ten
`*.demo` users).

---

### What shipped

**I95 + I98 — the server's sentence now reaches every READ path.**
`DataSourceError` rendered `{error.message}` and is called from **fifteen
sites across eleven screens**, so every failed read showed *"the API refused
this request (403)"* instead of the reason, discarding a blocked submission's
entire block list. I91 fixed the four WRITE screens on 08-24 and missed the
shared read component. 🔴 **Codex was asked this exact question on 08-24 and
answered NONE** — it matched the literal `.error.message` while the component
reads `{error.message}`. The Supervisor pass found it.

🔴 **AND THE REASON IT COULD HIDE: NO COMPONENT HAD EVER BEEN RENDERED BY A
TEST.** `vitest.config.ts` was `environment: "node"` with no React plugin and
there were **zero `.test.tsx` files**, while `@testing-library/react`, `jsdom`
and `@vitejs/plugin-react` had been devDependencies all along — installed,
never wired.

**I98b — my own fix regressed the commonest error on a tunnelled demo.**
`serverMessage` mines `error.detail`, but `detail` is not always a response
body: `ApiUnreachableError` stores the caught `TypeError` there and
`ApiShapeError` a `SyntaxError`/`ZodError`. All carry `.message`, so the
component began rendering the browser's raw **"Failed to fetch"** in place of
*"the API could not be reached"*. Guarded at source.

**I99 — `scripts/demo-up.ps1` was broken two ways, and one half had NEVER RUN.**
(a) Line 207 held a literal **BEL byte (0x07)** where `\a` belongs —
`Set-Location '$RepoRoot<BEL>pps\web'` — introduced by `c98290f` at 08-24
12:52, **four minutes after the last successful web build**. (b) The Keycloak
repoint **could not work from PowerShell 5.1**: embedded double quotes passed
to a native exe are stripped by the `CommandLineToArgvW` round-trip and
`kcadm` answered `Cannot parse the JSON`. Now a `docker cp`'d ASCII JSON file
applied with `-f`. **The read-back guard is what caught (b).**

**I99b/c — TWO SUCCESSIVE GUARDS THAT READ AS VERIFICATION AND COULD NOT FAIL.**
Codex found the first (`-notlike "*$PublicUrl*"` never looked at `webOrigins`,
passed with three of four URIs missing, and with a NAMED tunnel would pass on
stale config). My fix for it **still walked through the empty-`webOrigins`
case**, because every webOrigin is a PREFIX of a redirect URI — a substring
test cannot say WHICH FIELD a value came from. Now `ConvertFrom-Json` with
per-field `-notcontains`, falsified four ways.

**I79 — a membership carries its permissions.** Migration **045 / e9000**.
`core.memberships_for_subject` returns permission codes per organization,
resolved through the same chain `core.principal_for_subject` (033) walks — ONE
definition rather than a TypeScript copy. Measured: `lead.demo` **38**,
`tech.demo` **11**. Proven **e9000 → e8000 → e9000** with shape, owner, ACL and
comment asserted at each end; **the downgrade had never been run before**.

---

### 🔴 What the reviewers found — sixteenth session, neither alone was enough

**Round 1 (I98):** Codex FAIL, 2 blockers — the `ApiUnreachableError` trap
(which I had found independently) extended to `ApiShapeError`, and the weak
read-back guard. It also **corrected my call-site count, 19 → 15**; I had
counted import lines.

**Round 2 (I79):** Codex FAIL, 2 blockers, and the round split THREE ways:

* 🔴 **Codex was RIGHT and I had contradicted myself.** Authenticated with an
  active tenant absent from `/api/me` returned the FULL module map, justified
  in my own comment as *"we do not know, so we do not pretend to"* — which
  directly contradicts what I had written one file away in
  `auth-provider.tsx`: an API that cannot report permissions must show
  **LESS, never everything**. Failing open on an authorization-shaped
  decision, beside my own note not to. Now fails closed.
* 🔴 **Codex was WRONG on the facts, and the measurement says so.** It argued
  `roles` might reorder because `array_agg(DISTINCT)` has no `ORDER BY`.
  Measured on PG 16.14: DISTINCT aggregation **must sort to deduplicate**, so
  reversing the input leaves the output identical. It does not reproduce.
  **But its reasoning was right** — that is behaviour, not contract — so the
  `ORDER BY` is now explicit. *A guarantee must be a mechanism, not an
  argument.*
* Two non-blockers, both real: the downgrade lost 024's `COMMENT`, and the
  `/api/me` contract test never asserted `permissions`.

🔴 **AND MY OWN SUPERVISOR PASS FOUND THAT MY VERIFICATION PROVED LESS THAN IT
READ.** *"747 users checked, 0 role-set mismatches"* sounds conclusive. That
population contains **no** user with two roles in one organization, **no** user
in two organizations and **no** role with zero permissions — exactly the shapes
a missing DISTINCT breaks. Built all three synthetically in a rolled-back
transaction to get a real answer.

> **A measurement over a population that cannot exercise the risk is not
> evidence, however large the number is.**

---

### 🔴 The composition, not the parts

Every LAYER of I79 was verified and the JOIN between them was not — which is
the shape that produced 713/0/0 alongside a 404 sign-in on 08-24. So
`tests/e2e/shell/permissions.spec.ts` drives the real path: `tech.demo` signs
in through the real realm and the sidebar is read.

It asserts **both directions** — Laboratory must be PRESENT (`batch.view`) as
well as Administration ABSENT (`admin.users`), because an absence-only test
passes against an empty or broken sidebar. And it deliberately does **not**
use `TEST_SIGNIN_USER`, which defaults to `lead.demo` and would have passed
against the unfixed code.

**Falsified end to end, with a full rebuild and redeploy per direction:**

| bundle | result |
|---|---|
| I79 fixed | 1 passed |
| reverted to the pre-I79 pass-through, rebuilt, redeployed | **1 FAILED**, with its own diagnostic and a screenshot |
| restored, rebuilt | **34 passed** |

---

### ⚠️ Carried forward

* **`next build` rewrites `apps/web/tsconfig.json` on EVERY demo build.**
  Reverted four times today; `cab4c1c` reverted it last session. It will keep
  returning until someone commits the generated form or ignores it
  deliberately. Right now it is a trap that invites an unreviewed change into
  a commit.
* **Local migrations run as `postgres`, not `evercoat_owner`** —
  `alembic_version` is owned by `postgres` and denies `evercoat_owner`
  outright. Local is superuser; **Render is not**, so the 09-01 deploy meets
  that ownership question for real.
* **The tunnel is still a QUICK tunnel** — the hostname lives only as long as
  that `cloudflared` process. `cloudflared tunnel login` once ends the
  repointing tax.


---

## SESSION CLOSE 2026-08-24

Tip **`cab4c1c`**, pushed, tree clean, **CI 6/6 green**. Eight commits.

▶ **Restart the demo — ONE command now:**
`powershell -File scripts\demo-up.ps1` (prints the URL, writes
`tmp/tunnel_url.txt`). Full notes and every trap:
`Documents/session-archives/2026-08-24/RESTART_THE_DEMO.md`
Session record: `.../2026-08-24/README.md` · Progress report (PDF):
`Desktop/Evercoat-Progress-2026-08-24.pdf`

▶ **Next session's ranked task list is at the top of `TODO.md`.**

### What shipped

**23 of 37 endpoints across Laboratory, Testing, Formulations and MSD had no
browser caller.** All 37 do now — Laboratory 10→11, Testing **1→9**,
Formulations **1→13**, MSD 2→4. New workspaces at `/testing/test?id=…` and
`/formulations/formula?version=…`, plus plan-a-test, create-batch,
create-formula and reclassify.

### ✅ THE LIVE SUITE — 713 / 0 / 0, AND THE STACK IS STILL UP

Against **`https://file-dawn-trailer-corners.trycloudflare.com`** (read
`tmp/tunnel_url.txt` — a QUICK tunnel, so the hostname holds only while that
`cloudflared` process lives):

| phase | passed | failed | skipped |
|---|---|---|---|
| `api-live` | **682** | 0 | 0 |
| e2e (Playwright) | **31** | 0 | 0 |
| **TOTAL** | **713** | **0** | **0** |

Counts verified against each tool's OWN output — pytest's `682 passed`, and
Playwright's JSON decoded ONE DOCUMENT AT A TIME (it writes one per project;
a strict `json.load` dying on the second is how a green 31-test run reported
nothing and passed on 08-23).

### 🔴 713 GREEN AND SIGN-IN WAS 404 — READ I97

Every one of those assertions passed **while browser sign-in was broken**
(I96: Caddy's `/auth/*` identity prefix swallowed the app's own
`/auth/callback/`). `api-live` authenticates by DIRECT GRANT; the e2e shell
suite uses a seam compiled out of production builds. **Neither traverses the
callback.** The number was true and did not mean a human could log in.

**I97 is open for exactly this**: no test drives authorize → login form →
callback. Verified by hand instead — 302 with a real code, callback 200.

### The stack OUTLIVES the session now

`scripts/demo-up.ps1` starts cloudflared, the API and the web tier
**detached**, and the containers carry `--restart unless-stopped`. It derives
the tunnel hostname from cloudflared's own log, repoints all four things that
carry it, and **verifies the Keycloak client by reading it back** — four
self-inflicted bugs are written up in its header, including `next start`
printing "✓ Ready" while binding nothing.

Sign in as any of the ten roles with **`EvercoatDemo-2026!`**: `lead.demo`
`chem.demo` `eng.demo` `tech.demo` `dir.demo` `qa.demo` `admin.demo`
`proc.demo` `prod.demo` `exec.demo`.

### 🔴 The review round — read this before trusting a claim of mine

**Codex 4 findings, Supervisor 10, one overlap.** Thirteenth session running
where neither alone was enough.

* **I90 — the first commit's central claim was FALSE, and Codex checked it
  rather than believing it.** `createBatch`, `createTest`, `createFormula`
  and `classifyFormula` existed only as declarations in `lib/api/*.ts`.
  **A client function is not a caller** — the same defect the commit exists
  to remove, one layer up. Closing it needed `GET /api/testing/methods` and
  `GET /api/formulations/classifications` first: without them a planning form
  has no method to offer, so the create routes were unreachable **by
  construction**. §H's own warning, turned on this session.
* **I91 — four comments I wrote asserted a rule the code did not have.** The
  server's explanation sits in `.detail` and no screen read it, so every
  refusal rendered "the API refused this request (422)". A blocked
  submission's blocks were discarded **wholesale**. New `serverMessage()`.
* **I92 — the only UI path that creates a revision returned 422 on every
  press**, on the control the page calls "the only way a formula changes".
* **I93 — four inert mechanisms**, including an `invalidateQueries` key
  matching no query, under a comment claiming it prevented exactly that.
* **I94 — three of my own**, found by re-verifying rather than by a reviewer.
* **I95 — left open on purpose:** `app/knowledge/page.tsx` has I91's defect in
  three places. Out of the four modules under review, so **named rather than
  silently fixed**.

🔴 **AN EMPTY OUTPUT FILE IS NOT A PASSING RUN.** I read a still-being-written
`tsc` output as clean. It had silently taken `useWeighUp` with a block I
deleted. `next lint` caught it; the typecheck I trusted did not.

### ⚠️ Two operational findings

* **Last session's dev server was still running and holding ~2 GB** of this
  3.78 GB host. It starved Keycloak into `BlockedThreadChecker` warnings and
  made every gate crawl. **Check for a stale `next dev` before blaming the
  machine.**
* **Two pytest runs against the same database disagreed with each other** —
  one reported an error on `test_audit_update_and_delete_are_refused` that
  the other did not. Concurrent suites on one database produce numbers that
  are not evidence. Run the suite alone.

### Built

* **`/testing/test?id=…`** — both status fields side by side and labelled
  (F31), raw replicates with the mandatory exclusion reason, statistics with
  `null` rendered as a named absence rather than zero, the snapshotted
  approval ladder including **undecided** steps, all seven decision types,
  and the number of the rule that decided the colour.
* **`/formulations/formula?version=…`** — live composition, derived
  properties (each a value **or** the engine's own sentence saying why not),
  the weigh-up sheet, and the parent difference with both delta columns.
* Query parameters, not `[id]` — under `output: "export"` a dynamic segment
  must enumerate params at build time, so it would pre-render the seeded
  records and 404 every real one.

---

## SESSION CLOSE 2026-08-23

Tip **`ab9621e`**, tree clean, all pushed. **Nine commits.**

▶ **Restart procedure for the demo tunnel:**
`Documents/session-archives/2026-08-23/RESTART_THE_DEMO.md`
Full session record: `.../2026-08-23/README.md`

### The one thing outstanding

A **confirming live-suite run**. The last COMPLETE run was
**699 passed / 2 failed / 0 skipped** with `api-live` a clean **670 / 0 / 0**.
Those 2 e2e failures were a timeout budget sized for a local origin; the fix
landed in `playwright.config.ts` (180s live / 60s local) and both tests were
verified individually against the tunnel in 1.5m — but the full run confirming
it was **killed mid-flight and its numbers are void** (it showed 668/2, both
`httpx.ReadTimeout` against the API as it was shut down).

Expected on a clean run: **~701 / 0 / 0**.

### What shipped

* **Migration 044** — RLS on `core.users` (**I55**: 571 rows of cross-tenant
  PII readable with no context) and the cross-tenant WRITE in `invite_member`
  (**I80**, new: it renamed another tenant's user and returned their real email).
* 🔴 **A defect neither reviewer found.** `core.user_id_for_subject` was owned
  by `postgres` — `rolsuper`, `rolbypassrls` — while 044's own comment claimed
  `evercoat_owner`. I56's exact shape, three migrations after 033 wrote the
  warning. **`pg_proc` found it, not Codex and not the Supervisor**;
  `test_object_ownership.py` structurally could not, because its sweep only
  flags definers wrongly moved *to* `evercoat_owner`.
* **Laboratory workspace** at `/laboratory/batch?id=…` — eleven API routes that
  no browser could reach now have a caller.
* **I78** — the knowledge list reports what it truncates.
* **MSD relevance** — the distance threshold had stopped separating relevant
  from irrelevant (ranges OVERLAP: related 0.554–0.716, unrelated 0.664–0.859).
  Replaced with a shared-vocabulary requirement, which is what a LEXICAL
  embedder can actually attest to. **I77 still open** for a neural embedder.
* **Eight harness defects**, none in the product — see the archive README.
  The sharpest: a fully green 31-test Playwright run **reported nothing and
  passed**, and the pytest parser **deleted the passed count on every green
  run** (accurate when broken, wrong when clean).
* **`evercoat-test` Keycloak client** — the 11 auth round-trip tests had
  **never once executed** since they were written. They now pass (11 in 55.82s).

### Proven by hand, not by the suite

The full batch lifecycle driven end to end over the tunnel with real tokens:
create → authorise → start → 8/8 weighed → deviation → sample → complete →
accept. Authorization refused correctly three times, including **the technician
who executed a batch may not review it** (§9 segregation of duties).

⚠️ `evercoat-web`'s direct grant was temporarily enabled for that and
**disabled again, verified**. `evercoat-test` exists so nobody is tempted to
leave it on.

### 🔴 Read before touching the demo

* **localtunnel is unusable** — 15 of 15 concurrent requests → HTTP 429.
* **A Cloudflare QUICK tunnel changes hostname every restart**, and four things
  carry it (Keycloak `KC_HOSTNAME`, client redirect URIs, API issuer, the web
  bundle). **A named tunnel removes all of it and needs one browser login.**
* **Keycloak `start-dev` must NOT be memory-capped** — 512 MB + tuned heap is a
  Render `start` measurement; here it sticks at 497/512 and never boots.

---

## 🔴 RENDER IS RETIRED. THIS APP RUNS LOCALLY, SHARED BY TUNNEL.

**Owner decision, 2026-08-21: $0 on Render.** Settled by measurement, not
preference: Keycloak 26 in production mode under a hard 512 MB cap is
**OOM-killed at 451.6 MiB (exit 137)**, and Render has nothing between Starter
($7 / 512 MB) and Standard ($25 / 2 GB). Evercoat on Render is API $7 +
Keycloak $25 + Postgres $6 = **$38/month** against a $30 ceiling.

All apps here are prototypes and zero-cost is a hard rule. **Do not re-open
the Render hosting question without new information.**

The free **static site** stays — `itwevercoatrd.aiappinvent.com` costs nothing
and keeps a working certificate.

### Run it locally, share it with a client

```bash
"C:/Users/USER/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe" start evercoat-postgres
docker compose -f infrastructure/compose/docker-compose.yml up -d
C:/Users/USER/cloudflared.exe tunnel --url http://localhost:18081
```

Caddy fronts web + api + keycloak on **18081**, so a client needs **one** URL.

⚠️ `NEXT_PUBLIC_*` is inlined at **BUILD** time, so a random quick-tunnel URL
means rebuilding the web bundle each restart. One `cloudflared tunnel login`
gives a stable named tunnel and ends that — a browser step, the owner's to do.

✅ Full session record and every script:
`C:\Users\USER\Documents\session-archives\2026-08-21\`

---

**Session 2026-08-21. Read this file, then `TODO.md`.**

Repository: **https://github.com/marc667us/evercoat-itw-rd** (PUBLIC), branch
`master`. Tip **`cafb34f`**, working tree clean, pushed.
**CI 5 of 5 GREEN.** Local API suite **507 passed / 0 failed / 0 skipped**
(that number INCLUDES `tests/auth`, which runs without Keycloak - its conftest
says so in its first paragraph, and it was excluded all session on the
opposite assumption).

Run `./scripts/handover.sh` first — it prints the repo tip, CI conclusion,
what production is actually serving, and the next command to run.

---

## ▶ THE THREE THINGS THAT CHANGED TODAY

### 1. 🔴 THE LOCAL DATABASE WORKS. IT ALWAYS COULD HAVE.

Every previous session recorded *"Docker on this host is WEDGED — nothing
answers on 5432 or 55432, so every database test's first execution is CI."*

**That was wrong.** Docker Desktop had simply never been started, and it is
not at the standard path — it is a user-level install at
`%LOCALAPPDATA%\Programs\DockerDesktop\`. `evercoat-postgres` existed the
whole time, exited 137 (OOM-killed).

```bash
"C:/Users/USER/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe" start evercoat-postgres
```

It comes up healthy on port **55432**. The database is now at migration head.
To run the db suite:

```bash
cd apps/api
TEST_DB_HOST=localhost TEST_DB_PORT=55432 POSTGRES_DB=evercoat_itw_rd \
TEST_OWNER_USER=evercoat_owner TEST_OWNER_PASSWORD=ci-owner \
APP_DB_USER=evercoat_app APP_DB_PASSWORD=ci-app \
DATABASE_URL="postgresql+psycopg://evercoat_app:ci-app@localhost:55432/evercoat_itw_rd" \
KEYCLOAK_ISSUER="http://127.0.0.1:1/realms/evercoat" \
python -m pytest tests/ -q --ignore=tests/auth --ignore=tests/integration
```

The role passwords are set on the container to match CI's (`ci-owner` /
`ci-app`); the superuser is `postgres` / `dev-superuser-pw`. To migrate:
`MIGRATION_DATABASE_URL="postgresql+psycopg://postgres:dev-superuser-pw@localhost:55432/evercoat_itw_rd" python -m alembic upgrade head`

⚠️ **Host RAM is 7.92 GB with very little free.** The 7 `aw-*` containers
auto-start with Docker. A stray `nginxdemos/hello` container
(`adoring_lederberg`) was stopped to make room — it belongs to nothing.

**CORRECTED 2026-08-21: the `aw-*` containers are now deliberately STOPPED.**
AutoWorkshop is being retired and the owner confirmed nobody uses it; stopping
them freed **834 MiB** (`aw-keycloak` alone was 568 MiB). `docker start` brings
them back. The old rule said never to touch them, which was right while it was
running and is no longer.

**This matters more than it sounds.** Three defects found today were found
*only* because the suite could run locally against a real PostgreSQL — CI had
been green over all three.

### 2. 🔴 THE DEPLOY BLOCKER IS STRUCTURAL, NOT A WAITING GAME — ADR-027

The operator's rules as of today: **zero cost, strictly**, and **no task may
be assigned to them** (no signup, no interactive login, no dashboard action).
Under those two rules:

| | |
|---|---|
| **Railway (ADR-026)** | 🔴 **REVERSED.** It has **no free tier** — $5 of credit for 30 days, then $1/month, then Hobby at $5/month minimum for anything with a database. It was never zero-cost compliant. **Do not restart this path.** |
| **Render free web service** | Re-measured today: `POST /services plan=free` → **400 "free tier usage quota has been exhausted"** |
| **Render free database** | **400 "cannot have more than ONE active free tier database"** — `autoworkshop-postgres` holds it and expires **2026-09-01**, when a live AutoWorkshop needs it back |

🔴 **The database limit is per WORKSPACE, so waiting for the monthly
instance-hour reset does not help.** Evercoat can obtain a free Render
database only by taking the slot another running application depends on.
Waiting changes *who* is broken, not *whether*.

**Consequence, plainly: under the current rules there is no provider on which
this app's API and Keycloak can be deployed.** The web tier stays on Render
as a static site with a working certificate.

Best measured alternative for whenever that constraint changes: **Coolify
(open source) on Oracle Cloud Always Free** — permanent, 4 ARM cores, 24 GB,
no deploy cap, no sleep, no cold start. Costs exactly one signup. Full
compliance matrix (zero cost / no card / no owner action / supports an
iterative loop) in `Desktop\Evercoat-Hosting-Options-2026-08-21.pdf`.

⚠️ There is **exactly one** Render workspace, `tea-d86fu8mk1jcs7397i70g`
"My Workspace". Solar, AutoWorkshop and Evercoat's web tier are all already
in it. The operator's "no new workspace" rule is structurally satisfied.

### 3. THE DIGITAL THREAD'S TWO OPEN ENDS ARE CLOSED — I6 AND I7

Both functions existed, were correct, and **had no caller**.

* **I6** — `open_failure_for_failed_test` is now called from
  `complete_execution`, the only writer of `calculated_result`. A RED
  confirmation result opens its Failure Investigation, as §10 has always said.
* **I7** — `revise_version` now writes `formula_version_drivers`, so §29's
  *"why was F008 created?"* has an answer. `driver_type` is **required** on
  the revision endpoint — a **breaking change** to that route, made because §2
  says a revision must show which failure or objective caused it, and
  `change_reason` is prose that explains without linking.

---

## 🔴 WHAT THE REVIEWERS FOUND — SEVENTH SESSION, NEITHER ALONE WAS ENOUGH

**Codex found the transaction hazard. The Supervisor found five defects Codex
did not, two of them permanent lockouts.** Run both, every time.

### Codex

1. **`open_failure` called `session.rollback()`**, which rolls back the
   TOPMOST transaction and discards nested ones. Once `complete_execution`
   called it, a duplicate failure code would have destroyed the test
   completion and its audit event. Now `begin_nested()` — placed **outside**
   the `try`, because entering it flushes pending state before the savepoint
   exists.
2. 🔴 **My own test for that could not fail.** It asserted the session was
   still usable — but `session.rollback()` leaves a Session perfectly usable,
   so it would have passed against the broken code. It now asserts the
   caller's work *survived*, and was **proved by falsification**: the old
   implementation was temporarily restored and the test fails against it.
3. **Migration 028 claimed more than it delivers.** `clock_timestamp()` plus a
   random-UUID tiebreaker is a *stable display order*, not a guaranteed
   insertion order. The same defect the last two sessions kept finding — a
   comment stating a stronger rule than the code — this time in my own comment
   one commit after writing it.

### Supervisor

1. `post_completion` didn't map the failure domain's exceptions → **HTTP 500**
   instead of the 409 its sibling routes give the same condition.
2. 🔴 **PERMANENT LOCKOUT.** No uniqueness on `(organization_id, test_id)`, and
   `POST /api/failures` accepts any `test_id` — so two engineers opening an
   investigation for one test made the link lookup raise
   `MultipleResultsFound` on **every retry**. That test could never be
   completed again. Fixed at both layers (service uses `LIMIT 1`; migration
   029 adds the partial unique index, which **refuses to build** over existing
   duplicates and names them).
3. 🔴 **PERMANENT LOCKOUT, second one.** One squatted `FI-<test_number>` code
   made a test uncompletable forever — `failure_code` has no rename path.
   `_free_failure_code` now takes the first free suffix.
4. 🔴 **`list_messages` returned the OLDEST page.** `ORDER BY posted_at ASC …
   LIMIT 100` with no cursor: past 100 messages a reader was pinned to the
   opening of the conversation permanently and nothing new was reachable.
5. 028's `id` tiebreaker made the sort unservable by 022's index → full sort
   on every channel read. 029 adds a matching index.

### And one found by simply running the suite

🔴 **`now()` IS TRANSACTION-START TIME.** `messaging.messages.posted_at`
defaulted to `now()`, so every message written in one transaction got an
**identical** timestamp and `ORDER BY posted_at` had nothing to order by. A
conversation had *no defined order* and a reply could render above the message
it answered. `test_023_messaging` failed locally while passing in CI — **CI
had been green on heap luck.** Migration 028.

---

## ▶ NEXT

1. **I5** — `record_decision` writes `testing.test_decisions` directly instead
   of driving `workflow.approval_routes`. Two approval records for one event;
   §9 says one shared engine.
2. **I8** — notifications have no producer outside mentions, so §11's sidebar
   counts read zero.
3. 🔴 **I30** — **22 more `session.rollback()` calls inside IntegrityError
   handlers, across 9 modules.** Full inventory in `TODO.md`. Every one is a
   latent transaction-destroyer the moment §12's reuse rule composes it into a
   larger unit of work; two have already bitten. They are also **redundant
   even standalone** — `session_scope` already rolls back on any exception —
   so the sweep only removes risk. One reviewed slice with a shared helper.
4. **I3** — the golden Playwright E2E. Now genuinely reachable for the first
   time, because a real database is available locally.

---

## Constraints that must not be forgotten

- 🔴 **Zero cost, strictly. And no task may be assigned to the operator** —
  no signup, no interactive login, no dashboard action. A path whose first
  step is an owner action is not a path.
- 🔴 **Solar is never part of this app**, and Solar has **no running Docker
  container on this machine** — measured. Only a `factory/intelligent-pv-solar`
  image, exited three months ago. Solar is Render-only.
- 🔴 **Do not touch any `aw-*` container.** This project's DB is
  `evercoat-postgres` on port **55432**.
- ⚠️ **CI has a one-run-per-ref concurrency group.** Pushing evicts an
  in-progress run — a `cancelled` conclusion on the previous commit is usually
  this, not a failure.
- ⚠️ **Never** use `render-setup.yml` apply mode to force a deploy: it issues
  `DELETE` against **AutoWorkshop** custom domains. Use
  `gh workflow run "Deploy web (manual)"`.
- ⚠️ **Codex `exec` cannot take a long prompt as an argument on Windows** —
  the command line is limited to ~8 KB. Pipe it on **stdin** instead:
  `codex.cmd exec --skip-git-repo-check - < prompt.txt`. That also closes
  stdin, which is what stops it hanging.
- ⚠️ **CodeRabbit CLI 0.7.5** is installed and signature-verified but has
  **never been authenticated**; `coderabbit auth login` is interactive and is
  therefore blocked by the no-assignment rule.
