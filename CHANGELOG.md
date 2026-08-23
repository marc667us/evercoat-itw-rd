# CHANGELOG — EvercoatITWRD APP

## 2026-08-23 — the user directory was global, and one route wrote across tenants

Migration **044**. API suite **654 passed / 0 failed / 11 skipped**
(`tests/db` skips zero). ruff, ruff format, mypy (86 files) green.
Downgrade/upgrade roundtrip verified.

### 🔴 I55 — `core.users` HAD NO RLS AT ALL, SO 032 NEVER TOUCHED IT

Migration 032 closed I19 by making `core.rls_permissive()` FALSE, which
collapsed every policy to its real predicate. `core.users` had **no policy to
collapse**. Measured as `evercoat_app` with no tenant context:

    SELECT count(*) FROM core.organization_members;   -->    0
    SELECT count(*) FROM core.users;                  -->  571

Tenant *records* failed closed. The user *directory* did not — 571 rows, every
tenant, email addresses and display names.

⚠️ **The register said 290.** It had been quoted from a handover rather than
re-measured, and the development database had grown since. The defect was real
either way, but the number in front of it was stale.

### 🔴 I80 — FOUND WHILE MEASURING I55: A CROSS-TENANT WRITE

`invite_member` ran `INSERT ... ON CONFLICT (keycloak_sub) DO UPDATE SET
display_name`. Replayed as `evercoat_app` under organization A's GUC against a
subject belonging only to organization B:

    id            54648e11-...
    email         owner-08f856f3@example.test      <-- B's real address
    display_name  PWNED BY ORG A                   <-- overwritten

An `admin.users` holder in any organization could rename a user in any other,
and `RETURNING` disclosed that user's real email even though the caller had
supplied a different one. One statement, both directions.

### What 044 does

- **RLS on `core.users`**, predicate: readable if the reader shares an
  organization with that user, or is that user.
- **`core.user_id_for_subject`** — because 044's read policy makes an existing
  user in another organization invisible and `keycloak_sub` is globally unique,
  so without it an administrator could neither find nor create them. Removing a
  disclosure by deleting a feature is not a fix. It returns one uuid and no
  personal data.
- **`invite_member` no longer upserts** — resolve, insert only when absent,
  never touch an existing row's email or display name, and return the STORED
  values rather than the submitted ones.

MEASURED AFTER: unscoped read **571 → 0**; the replayed rename is refused.

### 🔴 THE MEMBERSHIP `status` IS NOT IN THE PREDICATE, DELIBERATELY

Filtering on `core.organization_members.status` looks like hardening and is a
data-loss bug. Eleven INNER joins resolve an actor through `core.users`
(`projects/dashboard.py`, `opportunities/service.py`, `messaging/service.py`,
`tasks/service.py`, `pipeline/service.py`), so a leaver would not merely lose
their name — **the records they created would drop out of every list.**
Whether somebody may sign in is `status` and Keycloak; whether their name
renders on a record they made is this policy.

### 🔴 THE COMMENT CLAIMED A BOUNDARY THE CODE DOES NOT HOLD

The first version said the UPDATE policy is what closes I80 and that "both are
required". Both false. The matrix was measured:

    SELECT policy | UPDATE policy | result
    --------------+---------------+-----------------------------------
    restrictive   | restrictive   | refused              (shipped)
    restrictive   | permissive    | refused
    permissive    | restrictive   | refused
    permissive    | permissive    | 'PWNED BY ORG A'     (pre-044)

Either alone refuses it. A direct `UPDATE ... WHERE` with the UPDATE policy
made permissive still changed **0 rows**, because PostgreSQL applies the SELECT
policy to rows an UPDATE reads through its WHERE clause. The read policy does
this work. The UPDATE policy exists so the table is not read-only, and its
predicate is defence in depth against the read policy ever being widened.

### 🔴 THE GUARD TEST COULD NOT FAIL — FOURTH TIME IN THIS PROJECT

`test_the_cross_tenant_rename_is_refused` passed with the UPDATE policy
dropped (no policy denies everyone) **and** with it made fully permissive. The
falsification that actually reddens it is making the READ policy permissive —
the pre-044 state. Both real failure modes are now covered:

- read policy permissive (the pre-044 hole) → **3 tests red**
- no UPDATE policy (deny-all read-only) → **2 tests red**

The second is caught by a test that did not exist: **a same-organization
rename must SUCCEED.** Every cross-tenant assertion in the file passes
vacuously against a read-only table.

### 🔴 THE REVIEW FOUND A DEFECT NEITHER REVIEWER FOUND, AND `pg_proc` DID

`core.user_id_for_subject` was **owned by `postgres`** — `rolsuper = true`,
`rolbypassrls = true` — while migration 044's own comment stated it was owned
by `evercoat_owner`, "matching the three definers that already exist".

SECURITY DEFINER runs as the owner, and the owner is whoever executed
`CREATE FUNCTION` unless it is pinned. This database applies migrations as
`postgres`. So the migration created a **fourth superuser-owned definer** —
I56's exact shape, permanently outside RLS including after the I58 cutover —
three migrations after 033 wrote the warning and the idiom.

Found by reading `pg_proc`, not the diff. `test_object_ownership.py` could not
have caught it: its sweep only flags definers wrongly moved **to**
`evercoat_owner`, so a superuser-owned one is invisible to it. It went red the
moment the owner was pinned, which is the acknowledgement now recorded there.

### Codex — 4 findings

| # | Finding | Outcome |
|---|---|---|
| 1 | Concurrent invites are not race-safe | **FIXED.** Independently found first; `guarded_write` + retry on `core.users`, and the **pre-existing** `organization_members_unique` half translated to the same 409 |
| 2 | The `status` justification covers the NAME; the policy grants the ROW | **ACCEPTED, recorded as I81.** Correct: all eleven joins select `display_name`, none selects `email`. RLS cannot express column granularity |
| 3 | `user_id_for_subject` discloses more than the UNIQUE constraint | **ACCEPTED, comment corrected, recorded as I82.** It hands over the uuid, which feeds the FK-reference hole `tenancy.py` guards in Python |
| 4 | Guard tests pass against broken implementations | **FIXED.** Policy-shape assertions (`polcmd` + non-constant predicates), a real INNER-join query for the `status` claim, the disconnected row-unchanged test merged into the refusal test, full definer/ACL/volatility/`search_path` assertions, and sign-in re-run as `evercoat_app` with no GUC instead of as the owner |

### Supervisor — 3 findings, disjoint from Codex except one

| # | Finding | Outcome |
|---|---|---|
| 1 | **Cross-tenant email existence oracle** through `users_email_key` | **ACCEPTED, recorded as I83 (P1).** Measured. The same channel as `keycloak_sub` but over a **guessable** identifier — a domain can be swept. Closing it is a schema decision reaching `@mention` resolution |
| 2 | The definer is owned by `postgres` | Confirms the defect found above, 10/10 confidence |
| 3 | "Return the STORED values" was **unreachable** | **FIXED.** The read sat where 044's policy makes the row invisible, so every 201 echoed the caller's submission and the audit recorded an email never written. Moved **after** the membership INSERT, where the policy's `EXISTS` matches — proved: `<<invisible>>` before the bind, the real address after |

**Two reviewers, near-disjoint again — the 12th session running.**



## 2026-08-20 (pt2) — Laboratory and Testing have screens, and a controlled mass was a float

**21 static pages** (from 19). Web typecheck + lint clean · **130 Vitest**
passed · **142** database-free backend tests passed · **4 passed** in a real
Chromium, including axe-core WCAG 2.1 AA on both new screens.

### 🔴 FOUND BEFORE WRITING ANY UI: A BATCH MASS WAS SHIPPING AS A FLOAT

`jsonable_encoder` maps `Decimal` to `float`. Measured:
`Decimal("12.5000") -> 12.5`, `Decimal("2.00") -> 2.0`.

`materials` was fixed for this on 2026-08-19 and **nowhere else was**. So:

- `laboratory.batches.planned_quantity_kg` — `NUMERIC(14,4)`, the planned
  mass of a controlled formulation batch — went out with its stored scale
  destroyed, and
- `testing.test_replicates.measured_value` — `NUMERIC(18,6)`, the raw
  physical measurement this platform exists to record faithfully — did the
  same.

`CLAUDE.md` §5: *"NUMERIC, never float, for percentages, masses, densities
and measured values."* Nothing had caught it because no screen was wired to
these routes, so no client had ever parsed the response. Found by reading
the contract before writing against it.

Both modules now carry `_decimal_strings`. **Generic, not a key list** —
`materials` enumerates its quantity columns by name, which works until
somebody adds a NUMERIC column and forgets the tuple, which is exactly how
this class of bug survives. `tests/test_laboratory_testing_serialisation.py`
pins it through the real encoder with no database.

### Laboratory and Testing

Two screens wired to `/api/laboratory/batches` and `/api/testing/tests`,
with zod-parsed clients that require the masses as **strings** — the client
half of the same contract, so a server regression fails to parse rather
than silently rounding a mass.

🔴 **Testing shows NO traffic light, deliberately.** `list_tests` withholds
the disposition on purpose — deriving it per row costs a statistics query
per test. Four of §10's fourteen rules need inputs this endpoint does not
return (`cv_limit`, requirement margin, `trend_alert`, replicate
statistics). A browser colouring these rows would be deciding a traffic
light on the client from an incomplete input, which is the one thing §10
forbids — and `calculated_result: "pass"` looks like a green light while
§6 says a technically passing test stays YELLOW until approvals complete.
So the five stored axes are shown as facts and the page states, in a
`role="note"`, that the disposition is not computed there.

🔴 **Neither screen has a demonstration fallback, and that is deliberate.**
`demo-data.json` has no batches, samples, tests or methods. Rather than
invent them, a new `LiveOnly` seam gives these screens two honest states:
rows from the database, or a plain statement that this build has no API to
ask. Fabricating laboratory batches and physical test results is materially
worse than fabricating a supplier list — §3 rule 3 exists to keep predicted
and measured separable, and a reader who scrolls past a banner sees a
measurement. This does **not** add a third `DataSource`: the screen shows
no numbers, and knows exactly where its zero rows came from.

### The sidebar can no longer promise a page that does not exist

`CURRENT_SLICE` 3 → 5, exposing exactly Laboratory (4) and Testing (5).

That constant's comment warned that raising it without building the pages
would turn items into live links into 404s — a comment asking the next
person to remember, which is the shape of every "two literals in two files"
defect here. It is now **enforced**: `navigation.test.ts` reads the
filesystem and fails if any available item has no `page.tsx`. Verified by
raising the constant to 6, which immediately named `failures -> /failures`
and `approvals -> /approvals`.

### Still not built, stated plainly

Batch detail (the weigh-up sheet), per-replicate test entry, the derived
disposition view, approvals and failure UI — and **MSD, which has no HTTP
route at all**, only `app/domains/msd/retrieval.py`. None of it works
against the deployed site regardless, because the live artefact is a static
export with no API and no Keycloak (`TODO.md` I13).

## 2026-08-20 — API security audit, and two thirds of the navigation was illegible

Three reviewers: **Codex CLI** (independent read-only sweep of `apps/api`),
the **Supervisor**, and an adversarial review pointed at the audit's own
fix. **CodeRabbit CLI 0.7.5 was installed and signature-verified** on this
host but is not yet authenticated, so its pass is still outstanding.

🔴 **THE DATABASE TESTS IN THIS CHANGE HAVE NOT BEEN RUN.** Docker on this
host is still wedged and nothing answers on 5432 or 55432, so
`tests/db/test_025_message_visibility.py` (9 tests) has never executed.
It compiles and lints; **CI is its first run.** Stated rather than implied.

**What DID run here:** `ruff check`, `ruff format --check` and `mypy app`
clean · **117 passed** on every database-free backend test · web
`typecheck` and `lint` clean · **128 passed** on Vitest · **3 passed** in a
real Chromium against a real production build for the new navigation
accessibility tests. Every fix below was additionally **verified to fail
against the prior state**, not merely to pass against the new one.

### Security — five defects fixed

- 🔴 **Any organization member could read any channel's messages.**
  `messaging.messages` carried an organization-only RLS policy while
  `messaging.channels` carried the project-confidentiality predicate, and
  `list_messages` filtered by `channel_id` **without ever joining
  `channels`** — so the channel's protection was never consulted at all.
  Restricted-project conversations and other people's **direct messages**
  were both readable by anyone holding a channel id. Fixed in the service
  *and* in the database (**migration 025**, `core.can_read_channel()`).
  Codex did not find this one.
- 🔴 **Unbounded Prometheus label cardinality, anonymously reachable.**
  The middleware read `request.scope["route"]` *before* `call_next`, and
  the router is what writes that key — so the `request.url.path` fallback
  fired on every request. Found by Codex.
- 🟠 **A signed token with no `exp` was accepted and never expired.**
  `verify_exp` validates an `exp` that is present; `require_exp` is what
  makes its absence a failure, and it defaults to `False`. Found by Codex.
- 🟠 **The reverse proxy stripped a prefix the API expects.** Caddy did
  `uri strip_prefix /api` while FastAPI mounts every router under `/api`,
  so **every API route would have 404'd through the proxy** — and
  `/api/metrics` reached the unauthenticated Prometheus endpoint.
- 🟠 `GET /api/projects` and `GET /api/opportunities` returned every
  visible row. Now capped at 200, like every other collection.

### The audit's own fix was then reviewed adversarially, and leaked twice

Migration 025 tightened the read side of `messaging.messages` and left the
**write** side of the two tables its predicate *reads* at
organization-only. `evercoat_app` holds INSERT/UPDATE on all of
`messaging`, so the predicate could be fed a different answer: **self-
enrolment** into someone else's direct channel, and **retyping** a channel
out of `direct` with one UPDATE. Both closed. Neither was reachable over
HTTP — which is the point, since that layer exists for when the
application layer is bypassed.

🔴 **The reviewer's own proposed fix would have broken direct messages
entirely** — a `WITH CHECK` subquery cannot see the row its own command is
inserting, so the creator's first membership row would be refused and no
direct message could ever be created. The shipped policy uses the
channel's immutable `created_by` to bootstrap instead.

**Left open deliberately:** `projects.project_members` has a `USING`
clause and no `WITH CHECK`, so self-enrolment there defeats **every**
project-scoped policy at once (`TODO.md` **I20**). It is a strictly larger
hole, it is also unreachable over HTTP, and it is **not** fixed blind: the
obvious fix hits the same bootstrap problem and `projects.projects` has no
`created_by` to escape through. It needs a live database.

Also recorded honestly rather than half-built: **there is no rate limiting
of any kind** (`TODO.md` **I18**), which `SECURITY.md` §10 had described in
detail as though it existed, and **`core.rls_permissive()` is still
`SELECT TRUE`** (**I19**), so the database is not independently
fail-closed. `SECURITY.md` §9's CSRF claim was corrected too: no token
exists, and none is needed while no credential is ambient.

### UI/UX — the accessibility suite was green over an illegible sidebar

- 🔴 **17 of the sidebar's 26 items rendered at `text-slate-300` —
  measured 1.48:1 against white, where WCAG 2.1 AA asks 4.5:1.** Two
  thirds of the primary navigation could not be read, and **every axe-core
  scan reported zero violations**: `isDisabled()` returns true for
  anything carrying `aria-disabled="true"`, and the `color-contrast` rule
  skips disabled nodes. The attribute that correctly described the state
  also silenced the check. *A check that cannot fail.*
- The distinction moved off colour entirely onto a **"Planned"** chip, so
  raising the contrast does not make unbuilt items look live.
- **"Available in slice 15" is gone.** A slice number is a build schedule;
  nobody using this application knows what one is.
- The collapsed rail showed two ambiguous letters — "Ma", "My", "Me" —
  with no tooltip. The accessible name was already correct; sighted users
  now get the same fact.
- Top-bar controls were `text-slate-400` (2.56:1). Same correction. axe
  skips `<button disabled>` outright, so nothing was going to flag it.
- **New instrument:** `accessibility.spec.ts` now computes the contrast
  ratio from the browser's own computed styles rather than asking axe —
  a test using the same rule would inherit the same blind spot.
- **Verified, not changed:** every traffic-light token passes AA on its
  badge background (pass 4.76:1, fail 5.91:1, conditional 4.75:1, neutral
  7.59:1).

## 2026-08-18 (pt3) — Slice 3's back half: the engine finally has callers

**229 tests collected** (from 155). **60 API routes** (from 51). Migrations
through **016**. `ruff check`, `ruff format` and `mypy` all clean.

🔴 **THE DATABASE TESTS IN THIS CHANGE HAVE NOT BEEN RUN LOCALLY.** The
Docker daemon on this host is wedged — `docker exec` returns HTTP 500,
`docker restart evercoat-postgres` fails with *"tried to kill container,
but did not receive an exit event"*, and a TCP connection to port 55432 is
accepted by the port proxy and then never answered (proven with a 90-second
`connect_timeout`, not assumed from a short one). Migration 015 has never
been applied on this machine. **Verification is CI's**, which starts a
clean `pgvector/pg16`, runs `alembic upgrade head` twice and the full
suite. What DID run here: `ruff`, `mypy`, an app-boot check confirming all
17 new routes register, and **43 passed / 0 failed / 0 skipped** on the
database-free tests.

Recorded this plainly because the alternative — reporting a green lint run
as though it were a green test run — is the exact failure this project's
own rules exist to prevent.

### What was built

`apps/web` has shipped `/materials`, `/suppliers` and
`/formulations/[code]` since Slice 3's front half, and
`app/calculations/formulation.py` has been pure, exact and
property-tested. **Nothing connected them.** There was no `materials`
table, no `formulas` table, no service and no route, and every figure on
the live formulation workspace is baked at BUILD time by
`scripts/build_demo_formulations.py`.

That is this codebase's most-repeated defect running backwards: normally a
table exists with no write path; here a screen existed with no table. The
question is the same one — *which production path WRITES this?* — and the
answer for the whole workspace was "a build script".

- **Migration 015** — `materials` (library, documents, lots, suppliers,
  the M:M) and `formulations` (formulas, versions, components), plus
  Administration section 3's `units` and `product_families`.
- **`app/domains/materials/service.py`** and
  **`app/domains/formulations/service.py`**.
- **17 routes** across `/api/materials`, `/api/suppliers`,
  `/api/formulations` and `/api/admin`.
- **`evaluate_version` is the first runtime caller of the engine** in this
  product's history.

### One vocabulary, not three

The status and role literals in migration 015 are taken from
`apps/web/lib/demo/demo-data.json`, which the deployed pages already
render — `development` / `approved` / `preferred` / `restricted` /
`obsolete` — rather than the `evaluation` / `lab_approved` /
`production_approved` that the permission names suggest. Inventing a
second set would have had the API return statuses the shipped UI has no
badge for. `test_015_materials_formulations.py` reads the CHECK constraint
out of `pg_constraint` and compares it against that JSON, so the two
cannot drift in silence.

### 🔴 `material.approve_production` existed and NO ROLE HELD IT

Found by asking the standing question of a *permission* rather than of a
role. Migration 002 defines the code and grants it to none of the ten
seeded roles: Chemist has create/edit, Lead has `approve_lab`, QA has
`restrict`, Procurement has create/edit. Nobody had it.

So **`preferred`, one of the five material statuses the deployed site
already renders, was a state no user of this system could ever set** —
not hidden, not permission-denied for most people; unreachable, for
everyone, permanently. This is the sixth instance of that defect class on
this platform, and the mirror image of the other five: a write path with
no holder rather than a role with no write path.

Migration 016 grants it to `qa_compliance_officer`, which already holds
`material.restrict` — the negative control over the same judgement.
Procurement was rejected as the holder for a stated reason: it holds
`material.create` and `material.edit`, so the same person would enter a
material's data and declare it fit for commercial production.

### 🔴 `tests/db/test_002_roles_permissions.py` DID NOT EXIST

Migration 002 has ended with this comment since Slice 1:

```
-- Verified by tests/db/test_002_roles_permissions.py:
--   * every permission code referenced in application source exists here
--   * every permission here is referenced somewhere in source
--   ...
```

**None of those five properties was checked by anything.** A comment
asserting a safety net made of prose, sitting at the bottom of the file
that defines the entire authorization model — which is the worst possible
place for it, because every other security claim in the product is
downstream of these grants. It is also how the orphaned permission above
survived.

The file is now written, with a sixth property the original comment did
not claim and which is the one that would have caught it: **every
permission must have at least one holder.**

### Immutability is the database's, not the service's

`CLAUDE.md` section 8 requires a released master formula to be read-only
*at the database level, not merely hidden in the UI*. Three triggers:
`formula_code` is immutable once issued; a version that has left `draft`
is frozen except for `status`, the approval columns and `observed_effect`;
and **components follow their version** — freezing the version row while
leaving its component rows writable would let an approved formula be
changed without a single column of the version ever being touched.

The component trigger is SECURITY DEFINER with a pinned `search_path`, so
its own lookup cannot be defeated by a session whose RLS view of
`formula_versions` is empty. A guard that passes when it cannot see its
subject is the "check that walks through its own gap" already recorded
twice against this platform. The FORCE-RLS cutover will need to revisit
it, and that is written in the migration next to the existing tripwire.

### Governance — three findings from Codex, all real, all fixed

Checked against source before acting, as the standing rule requires.

1. **HIGH — a non-member could WRITE into a restricted project.**
   `create_formula` inserted with the caller's `project_id` and no
   membership check. Migration 005 deliberately made the project-scoped
   `WITH CHECK` organization-only (requiring membership to WRITE makes the
   first row of a restricted project impossible to create), so the INSERT
   **succeeded** for a non-member and the row merely became invisible to
   them afterwards. Invisible is not refused: it landed in another team's
   confidential project. **And the module docstring asserted the opposite
   guarantee** — a comment claiming a rule the code did not implement,
   committed inside the docstring making the claim. Now an
   `INSERT ... SELECT` whose source row is the project under the same
   predicate the RLS `USING` clause applies.
2. **HIGH — `formula.view_cost` was bypassable one URL away.**
   `GET /versions/{id}` requires only `formula.view` and returned every
   component's `cost_per_kg` alongside its percentage — the whole cost of
   the formula, to a caller who lacked the cost permission. The key is now
   removed (not nulled: a null would say "no cost on file", which is a
   different and false claim).
3. **MEDIUM — production approval could skip laboratory approval.** QA
   holds both `material.restrict` and, since migration 016,
   `material.approve_production`, so QA could take a brand-new
   `development` material straight to `preferred`, never passing through
   `approved` or the Lead who holds `material.approve_lab`. Permission
   answers "may this person ever do this"; it cannot answer "may it be
   done from where the material is now". `ALLOWED_TRANSITIONS` now does,
   enforced inside the UPDATE's own WHERE clause rather than checked in a
   preceding SELECT.

Two further defects were found in self-review before Codex ran: a dead
branch in `compare_versions` reading a `_components` key that never
existed, and a weigh-up sheet ordered by the engine's return dict — which
places the largest line last because it absorbs the rounding remainder —
rather than by the formula's own display order.

### Administration section 3, in the same change that needed it

Migration 015 creates `materials.units` and `materials.product_families`.
Shipping two configuration tables with no writer, in the very change that
criticises exactly that pattern, would have made them the seventh and
eighth instances. `app/api/admin_reference_data.py` is their write path.

Material statuses are deliberately NOT editable rows: each one is reachable
through a distinct permission and rendered by a specific badge, so an
added status would be one no permission grants and no component draws.

## 2026-08-17 — Audit chain scope, milestone/risk/member write paths

**146 passed / 0 failed / 0 skipped** (from 124). **51 API routes** (from
42). Migrations through **012**, each applied and verified against a real
database. `ruff check` and `ruff format` clean. `mypy` is not installed
in this environment and could not be run.

### A recorded defect whose stated CAUSE was wrong

`TODO.md` carried the audit chain as "a single GLOBAL hash chain that
forks under concurrency: two transactions each read the tail before
either commits". That cannot happen — `audit.chain_row()` already took
`pg_advisory_xact_lock()`, which is transaction-scoped, and the tail read
after it takes a fresh READ COMMITTED snapshot.

Established by experiment instead of argument. Six interleaved inserts on
a live database:

```
label     id    org        prev_hash points at
A1       681   org A       GENESIS
B1       682   org B       GENESIS      <- org B starts its own chain
A2       683   org A       A1           <- skips B1 entirely
B2       684   org B       B1
UNSCOPED 685   NULL        B2           <- splices across chains
A3       686   org A       A2
```

The trigger was SECURITY INVOKER, so its tail read was filtered by the
`audit_org_isolation` RLS policy: the chain was **already
per-organization, by accident**. The genuine defect was row 685 — a
writer with no `app.current_org` saw every row and spliced one tenant's
chain onto another's, non-deterministically.

**Second defect found on the way:** the insert policy was
`WITH CHECK (true)`. Any session could write audit rows attributed to any
organization — forging entries in another tenant's tamper-evident log.

**Migration 011** chains per organization in the trigger's own predicate,
makes `chain_row()` SECURITY DEFINER with a pinned `search_path`, locks
the advisory lock per organization, replaces the insert policy, and
records the regime change as an audit row of its own so a break at a
pre-011 row reads as a known migration rather than as tampering.
`verify_chain` now **requires** an `organization_id`.

A FORCE-RLS cutover would reintroduce the same class of defect. That is
covered by a test that fails the moment the cutover lands, not by a
comment.

### Two counters that could only ever show zero

`projects.milestones` and `projects.risks` shipped in Slice 2 with
tables, indexes, RLS policies and dashboard counters — and no writer.
`milestones` had none even in a test fixture, so its counters had never
been non-zero. `projects.risks` had exactly one INSERT, in a test.
`project.assign_member` was a granted permission that no route used.

The permissions for milestones and risks **did not exist in the
catalogue**: migration 002 seeded codes for every future domain and none
for these. **Migration 012** adds `milestone.manage`, `risk.create` and
`risk.manage` — split for risks the way `failure.create` and
`failure.close` already are — plus two invariants enforced in the
database: a milestone that is met or missed records *when*, and a risk
marked `mitigating` must state its mitigation.

The tests assert the **dashboard counter moves**, not merely that the
endpoint returns 201. A create endpoint whose result is invisible is the
state this work was fixing.

Project membership is the RLS predicate, so adding a member *is* the
access grant; the test asserts it from the colleague's own token. Removal
deactivates rather than deletes, and the project's own lead cannot be
removed — migration 006 rescues their view of the project row only, while
every child policy tests `core.is_project_member` and nothing else, so
removing them from a restricted project leaves the header and none of its
contents.

### GATE-1 corrected

The golden E2E was recorded as blocked by Docker VM memory. It is not
runnable at any amount of memory: eleven of the scenario's fifteen arrows
have no table, route, service or page, and Playwright has no config and
no spec files anywhere in the repository. Re-filed to Slice 7, where
`IMPLEMENTATION_PLAN.md:436` already put it. Detail in `TODO.md`.

### Documentation

`DATA_MODEL.md` written — the test-status state dictionary, the ordered
derivation, and the transition table that `CLAUDE.md` §10 and ADR-007
both promise, and that Slice 5 needs. Every section is marked **BUILT**
or **SPECIFIED**, because mixing the two is how the artifacts above went
wrong.

### Codex review — 10 findings, 8 fixed, 2 documented

Codex confirmed the audit-chain diagnosis independently and returned ten
findings on the work itself. The serious one is worth naming:

- **HIGH — child mutations were not bound to the project in the URL.**
  `set_milestone_status` and `update_risk` filtered on child id and
  organization only. `require_project_member()` authorises the project in
  the *path*, and the service then ignored it — so a member of project A
  could pass A's id in the URL with project B's milestone id and mutate
  it. RLS does not repair this: the child policy admits rows from any
  `normal` project in the organization. **Fixed**, and the regression test
  was verified to fail without the fix and pass with it.
- **HIGH — `verify_chain` never authenticated the head of the walk.**
  The first row's `prev_hash` was skipped, so deleting a chain's genesis
  event promoted its second event to first-returned and the walk reported
  the chain intact. Deleting a row is exactly what the chain exists to
  detect. **Fixed**: a full walk must begin at `GENESIS`; a bounded walk
  seeds from the last row of the same chain at or before the boundary.
- **HIGH — the audit insert policy from 011 was still fail-open in one
  direction.** `organization_id IS NULL` was unconditional, letting any
  tenant session append to the platform's SYSTEM chain, and
  `current_org_id() IS NULL` made any accidentally unscoped connection
  trusted for every organization. **Fixed by migration 013.**
- **MEDIUM — the duplicate-risk race still became a 500.** My own comment
  said the constraint "still fires if two requests race here", and nothing
  caught it. **Fixed** by translating `risks_org_code_key` at the insert.
- **MEDIUM — member removal locked only the membership row**, so a
  concurrent lead assignment could defeat the lead guard. **Fixed** with
  `FOR UPDATE OF pm, p`.
- **LOW — repeated removal wrote a false audit transition**, claiming a
  move from `active` that never happened. **Fixed**: only an active
  membership can be removed.
- **LOW — the definer `search_path` did not name `pg_temp` last.**
  **Fixed by migration 013.** `public` must stay: pgcrypto's `digest()`
  lives there, verified in the live catalogue.
- **HIGH — `SECURITY DEFINER` does not survive a FORCE RLS cutover.**
  Correct, and 011's comment overclaimed by implying it did. **The comment
  is corrected in 013**; the condition was already covered by a test that
  fails the moment the cutover lands.

**Documented rather than fixed, deliberately:**

- **Migration 011 uses `CREATE OR REPLACE FUNCTION` before its
  `ALTER ... OWNER`.** On a deployment whose migration role is not a
  superuser and does not hold membership in the owning role, that fails.
  It does not affect this host (migrations run as `postgres`) and no
  deployment exists. Recorded in `TODO.md` as a deployment prerequisite.
- **Migration 012's CHECK constraints are validated immediately.** On a
  database with pre-existing violating rows the migration would roll
  back. Both tables were empty here. The `NOT VALID` → clean →
  `VALIDATE` pattern is recorded in `TODO.md` for the first real
  deployment.

---

## Slice 1 — Foundation, Identity, Administration §1, Shell, Observability

**Status: code-complete, GATE-INCOMPLETE.** The golden end-to-end
scenario has never run — see `TODO.md` GATE-1. Deferred by the operator
on 2026-08-16, not cancelled.

### Verified

| | |
|---|---|
| API tests | **37 passed / 0 failed / 0 skipped** |
| Web tests | **26 passed** |
| Migrations | `alembic upgrade head` twice from empty, second run a no-op |
| API over HTTP | `/health/live` 200 · `/health/ready` 503 (correct, no DB) · `/api/admin/roles` 401 · `/metrics` 200 |
| Web build | `next build` exit 0, 4 routes · `tsc` 0 errors · eslint clean |
| Lint | `ruff check` + `ruff format` clean, 17 files |

### Defects found by running things, not by reading them

1. **`SET LOCAL app.current_user` is a syntax error.** `current_user` is
   a reserved SQL keyword; PostgreSQL rejects it even inside a qualified
   custom GUC name. Would have broken every authenticated request.
2. **The app could not import.** `EmailStr` needs `email-validator` at
   class-definition time and it was undeclared — the container would not
   have started. Syntax checks passed.
3. **The app aborted during startup.** `structlog.stdlib.add_logger_name`
   reads `logger.name`, which `PrintLogger` lacks. It raised on the first
   log line, before binding a port, buried in a structlog traceback.
4. **`audit.events` lacked its composite tenant key**, which the rule
   requires without exception.
5. **Alembic's version table could not live in `audit`.** Fixing it by
   pre-creating the schema introduced a worse bug: the schema became
   owned by the migration user, so `AUTHORIZATION evercoat_owner` silently
   became a no-op and the owner role lost `USAGE`.

### Measured, not assumed

- Pass-green vs fail-red is **ΔE 4.2 under deuteranopia**. Roughly 8% of
  men cannot distinguish them by hue. This is the measurement behind the
  colour + icon + text rule.
- Three series colours validated all-pairs both modes; a fourth fails.
- Docker VM cannot fit a ninth container: exit 137, VM-level OOM.

### Added

Migrations 001–002 · Alembic · five DB roles · RLS on organization **and**
project membership · composite tenant keys · SHA-256 audit hash chain ·
session context with fail-closed guard · Keycloak JWT verification ·
permission + resource-scope dependencies · Administration §1 (7 routes) ·
Celery worker · health/metrics/structured logging · Next.js shell ·
sidebar from a single navigation source · 8 shared components ·
CI (3 jobs) · Keycloak realm · compose stack.

### Decisions

ADR-001…024 in `DECISIONS.md`. Two settled by the operator: **ADR-002**
LangGraph (an explicit exception to root §0.1) and **ADR-024** full
depth, gate by gate.

### Review

56 findings raised across Codex and Supervisor; 53 upheld and addressed.
Record in `docs/REVIEW_PASS1_ADJUDICATION.md`.
