# CHANGELOG — EvercoatITWRD APP

## 2026-08-31 — Phase 5: the product could not be searched, and a workspace could not say why it existed

Two of Phase 5's five cross-cutting parts, §29 and §25. Both were the same
kind of gap: a capability the database already supported and no layer above it
carried.

### §29 — global search (`b75f2e9`, `2ca9f22`)

Spec §29 asks to **extend** global search. There was none to extend: the top
bar's box has been `disabled` since Slice 1, and the only `/search` route in
the API was the knowledge library's passage retrieval.

`GET /api/search` covers fifteen record types in one literal statement. It is
gated on **authentication, not one permission** — a top-bar box is reachable by
all ten roles — so authorization is per record type, each branch switched on by
a bound boolean rather than filtered afterwards. A post-filter would leak the
total: *"247 results, 3 shown"* tells an unauthorized caller how many materials
match "isocyanate", which is most of the answer.

🔴 **THE RESPONSE REPORTS WHAT IT DID NOT SEARCH.** "No results" and "not
searched" are different answers, and only one of them is "there is nothing
there". A chemist without `failure.view` who reads "nothing found" concludes no
failure matches — false, in the direction that hides a problem from the person
chasing it. The two §29 record types this system has no table for (patents,
released products) are named as absent rather than returned empty.

🔴 **THE FIRST REGISTRY WOULD HAVE SHIPPED FIFTEEN DEAD LINKS.** Every record
type was given a detail route — `/materials/{id}`, `/suppliers/{id}` and eleven
more — and not one is a route this application serves. Only five workspace
screens take a record id, and as `?id=`, not as a path segment. `record-link.tsx`
already carries the lesson: *a dead link is worse than no link.* `detail_path`
is nullable now, a hit without one renders as text offering its list screen, and
a test reads `apps/web/app` and fails on any path the router would not serve.

### §25 — contextual entry points (`2ca9f22`)

🔴 **THE COLUMNS WERE NEVER MISSING. THE PROJECTION WAS, AT BOTH ENDS.**

`research.investigations` has carried `material_id`, `formula_version_id`,
`test_id` and `failure_id` since migration 058, and `POST /api/research` has
always accepted all four. `list_investigations` projected **none** of them and
the web client's `InvestigationRequest` offered **none** of them — so no browser
could create a linked investigation, and no screen could say what one came from.

Exactly the shape of the dates defect closed the day before. The readable CODE
travels beside each id, because an id alone renders as a UUID nobody can act on
— a back-link that looks like it works and tells the reader nothing.

Materials, Testing and Failures each carry a "Research this →" entry point that
arrives with the record in the query string; the Research Center card says
"Opened from: …" and links back where a detail screen exists.

### What the reviewers added

Codex returned **one P1 and five P2s on `b75f2e9`. Every one was real.**

- **P1** — escaping `%` and `_` closed pattern INJECTION and did nothing about
  pattern COST. `lower(col) LIKE '%a%'` has a leading wildcard, so no ordinary
  index serves it; one common letter makes every permitted branch scan its
  table. `limit <= 50` bounds the RESPONSE, not the WORK. Now bounded by a
  minimum query length **and** a transaction-local `statement_timeout` — the
  minimum is explicitly not claimed as the fix, because "ab" still scans.
  ⚠️ `SET LOCAL statement_timeout = :ms` is a syntax error: SET takes a
  literal, never a bind parameter. `set_config()` is a function, so its
  arguments are values.
- **P2** — `truncated` lied; `len(results) == limit` is also true for an
  exactly-complete answer. Fetch one more row than asked for.
- **P2** — `searched` named a claim it did not compute: with `?types=material`
  fourteen branches did not run and the response said they had.
- **P2** — `market_segment` and `category` sat in the `state` slot and rendered
  where a reader looks for "approved".
- **P2** — the route guard split on `?` and checked only the base route, so
  `?verison=` would have passed it.
- **P2** — two comments were false: "tenancy is NOT done here" while fourteen
  branches enforce `organization_id`, and a claim that the agent tier calls this
  service when nothing does. Both corrected rather than defended.

**Also closed:** **I7** was stale, not open — `revise_version` has called
`record_driver` since the failures work (`formulations/service.py:1421`).

### 🔴 AND THE LIVE SUITE FOUND WHAT NOTHING LOCAL COULD

**Sign-in was broken on the deployed site.** Six tests failed there, all in
`tests/integration/test_auth_end_to_end.py` — a real token from a real Keycloak
got `401 invalid token`. Those six SKIP locally, so a green local run was
reporting on a product nobody could sign into.

The realm's `frontendUrl` is persisted in Keycloak's DATABASE and OVERRIDES
`KC_HOSTNAME`; `demo-up.ps1` moved the client and the container and left that
row naming a tunnel dead for hours. The client's `redirectUris` were two
hostnames stale on top of it.

⚠️ It looks like a proxy problem and is not — the stale issuer was served on
`localhost:18080` with Caddy out of the path. And `kcadm get realms
--fields attributes` returned `{}` while the row sat in `realm_attribute`, so
the new read-back queries the database rather than the interface that hid it.

**And 24 tests had been skipping on a wrong password** — `evercoat_public` and
`evercoat_agent` are `dev-public-pw` / `dev-agent-pw` here, not CI's `ci-*`.
`tests/db/conftest.py` skipped on ANY connection error, so three handovers
quoted "0 failed / 35 skipped" as though the 35 were deliberate. A supplied
credential that is refused now FAILS.

🔴 **LIVE SUITE ON THE DEPLOYED SITE: 1130 passed / 0 failed / 0 SKIPPED**
(api-live 1047/0/0 · e2e 83/0/0). The previous best was 1024/0/0.

apps/api **1036 / 0 / 11** local (was 986 / 0 / 35) · apps/web **286**. Both
new guards falsified by reverting them.

## 2026-08-30 (part 3) — the pipeline could not say WHEN

Every pipeline screen could report what STAGE a record was at and never when it
got there. A repository-wide search for `toLocaleDateString`,
`Intl.DateTimeFormat` and `new Date(` across the whole of `apps/web` returned
**two hits, neither of which displayed a date** — one compared a due date, one
formatted money. The application rendered no date anywhere.

The columns were never missing. `created_at` was NOT NULL on every pipeline
table the entire time; **four of the five list endpoints selected everything
except it**, and nothing failed, because nothing asked.

Fixed end to end, because each layer could silently undo the next:

- **The SQL** — `list_projects`, `list_formulas`, `list_tests`, `list_batches`
  and the requirements query now project `created_at`.
- **The reshaping** — `verification_matrix` REBUILDS its rows, so a column in
  its SELECT does not reach a caller unless the dict names it too.
- **The response model** — `ProjectSummary` drops what it does not declare,
  and supplies a default for what the query omits, so the two can cancel out.
- **The Zod schemas** — strip undeclared keys before any view sees them.
- **The views** — innovation, projects, formulations, testing, laboratory, the
  requirements matrix, the Research Center's four registers, failures,
  approvals and the pipeline board.

🔴 **A REAL OFF-BY-ONE-DAY DEFECT, FOUND BY A TEST RATHER THAN BY READING.**
`target_release_date` is a plain `date` column and arrives as `2026-11-30`.
ECMAScript parses a bare date as **UTC midnight**, and `Intl` then renders it in
the viewer's zone — so on this host it displayed **29 Nov 2026**. Every release
target, and every date-typed column in the product, would have shown a day
early for every user west of UTC. A calendar date is now constructed in local
time; a `timestamptz` keeps the ordinary conversion, because for an instant
"when, in my time" is the right question. A malformed date is rejected rather
than rolled over — `new Date(2026, 12, 45)` silently becomes 2027, and a
rolled-over date renders as a real-looking WRONG day.

**One formatter and one component**, per §12: `lib/format/date.ts` and
`components/ui/event-dates.tsx`. An event with no date is not rendered at all —
"Completed —" beside a running batch claims the step was attempted and not
recorded, which is worse than silence. Unknown renders as an em dash, never as
a blank and never as `Invalid Date`, which is the literal string
`toLocaleDateString` returns rather than throwing.

**Semgrep, closed at the root rather than suppressed.** `dynamic-urllib-use-detected`
blocked CI on the catalogue verifier. The first fix was a `nosemgrep` arguing
the https guard already closed the hole; the argument was sound and the fix was
still wrong, because it leaves a file-reading primitive one edit away from
reachable. Now uses `httpx` — already a declared dependency, and it has no
`file://` handler at all, **measured**: `UnsupportedProtocol`. Verified that the
swap is not a regression — the one host that stopped resolving times out for
`urllib` too, at the same moment.

Ten new formatter tests and six projection assertions inside the golden
scenario — placed there because a standalone test would call the list functions
against whatever org it found, and an org with no rows returns `[]`, over which
every assertion passes while checking nothing. **Every guard falsified by
breaking the thing it watches**: each projection reverted one at a time (red),
the calendar-date branch deleted (red), the rollover check removed (red), the
NaN guard removed (red).

apps/api **985**, apps/web **266 → 276**.

## 2026-08-29 (part 2) — Phase 5 §27, and the forms nobody could reach

`b093726` · `21af227` · `d36aa80` · `c1f46f7` · `dbbd80b` · `0bfc812`.
apps/api **939 → 956**, apps/web **218 → 232**.

**Phase 5 §27**: fifteen widgets across the four existing role dashboards —
§27's own rule is "do not create another disconnected dashboard system".
And then the discovery that **the role dashboard rendered no panels at all**,
for every role: the component walked the response's top-level keys and skipped
`panels`, the one key holding all twenty-one of them. The API suite asserts the
RESPONSE; the component had no test.

**Demonstration data** for the Research Center and Competitor Intelligence,
written through the PRODUCTION SERVICES — fifteen write paths driven end to
end, because a seed that bypasses them proves the screens render and nothing
else.

🔴 **THE COMPOSITION EDITOR.** You could create a formula and never say what
was in it: `PUT /versions/{id}/components` had existed since Slice 3 with no
client function, no hook and no control. Every derived figure on the version
page was computing over nothing. Found by the owner asking which form a chemist
uses — not by any audit, because the audits asked which routes have a caller.

**Create forms** for materials, projects, testing and My Work, on one shared
shell that refuses to render a form the server would refuse. **Material status
ladder** (offered per transition, mirrored with a drift test that reads the
Python) and **supplier link**. **Innovation wired to the API** for the first
time — it had rendered a static array, so `opportunity.create` and
`opportunity.decide` were permissions two roles held with nothing to press.
**The Research Center's controls gated**, which ESLint helped find.

### What a role audit is for

For every role, does it have a control for every write permission it HOLDS —
the inverse of "a permission with no enforcement point". Seven gaps for the
chemist, four for the lead, four for the engineer, three for procurement, in
three different kinds. ⚠️ `msd.use` is held by **8 of 10 roles** and there is
no MSD screen: reported, not built.

## 2026-08-29 — Phase 4: research becomes an experiment

**`e0b2394` + `ef160b3`.** Migration **058 / q1000**, both trees. apps/api
**902 → 939 passed / 0 failed / 11 skipped**. apps/web **218**.

The `research` schema's **eight tables**, their six permissions, the finding
approval route, and the ONE point where research joins the formula world: an
accepted experiment proposal records the version `formulations.revise_version`
returned. Nothing in the module inserts a formula version and there is no
second path that does.

**§19's loop is now pressable end to end** — question → investigation →
evidence → finding → hypothesis → proposal → chemist review → formula
candidate. `/material-safety/research` carries a control for every one of the
15 write routes, and `knowledge.promote` — seeded since migration 002 and read
by nothing for the product's whole history — has its **first enforcement
point**. 29 orphaned permissions → 28.

### Three defects found in the design by measuring, before review

1. **`findings.status` was going to carry `approved`/`rejected` that nothing
   would ever write.** The approval engine settles a route and has no entity
   callback — measured in `_settle_route`. That is the defect Codex found on
   `safety_reviews` in Phase 2. The approval IS the route now, and because it
   lives in another table the promotion guard **could not be a CHECK**: it is a
   SECURITY INVOKER trigger that reads the route.
2. **`knowledge.documents_source_check` did not accept `research_finding`** —
   every promotion would have been refused at runtime, and no test written
   against the service would have caught it, because the service is correct.
3. **`formula_version_drivers_unique` is NULLS DISTINCT** — adding
   `experiment_proposal_id` without adding it to the key would have let one
   proposal drive the same version any number of times.

### And 17 more from the two reviewers, only ONE of them overlapping

**Codex 6 (2 P1), Supervisor 11 (2 HIGH)** — the 23rd consecutive session in
which neither alone was enough. The blockers: proposal acceptance was raceable
and cloned a version per caller; acceptance did not bind the version to the
proposal's project; `owner_user_id` was written from the request body with no
tenant check; and the promotion trigger was **BEFORE UPDATE only** while its
own comment claimed it held against direct SQL — `evercoat_app` holds
table-level INSERT, so one INSERT walked past it.

🔴 **`lpad` TRUNCATES ON THE RIGHT.** `lpad('1000', 3, '0')` is `'100'`. The
1000th proposal in an organization-year would have collided with the 100th and
every retry would recompute the same value — codes permanently un-allocatable,
nothing about the code looking wrong.

🔴 **Two comments asserted rules that do not exist.** The ordinary revision
route requires only `formula.clone`, not two permissions — and measuring that
exposed a lead holding `experiment.accept` who could never have used it. The
grant was withdrawn rather than the gate weakened: *the holder set of an act
must be a subset of the holder set of what the act does.*

Falsified by breaking the DATABASE and restoring: FORCE RLS, the promotion
trigger, and the trigger's INSERT arm. Falsified by breaking the CODE: the
structural permission guard.

## 2026-08-29 — I112: the routes finally have tests, and each one was falsified

**`b06a4d7`.** apps/api **889 → 902 passed / 0 failed / 11 skipped**.

`test_056` has 23 cases and every one is a DATABASE case. That is precisely why
three real defects were green: a 500 where a 409 was intended, an evidence
source the database refused every time, and raw PostgreSQL text — schema, table,
constraint expression — returned as a response body. **All three are route- or
service-level behaviours and invisible from SQL by construction.**

13 new cases drive the real app through FastAPI's dependency graph with real
tokens. Each of the three fixes was **reverted in the source to prove the test
detects it**, then restored — the `verify_evidence` revert reproduced the
original 500 with its `CheckViolation` traceback exactly.

🔴 **THE PERMISSION GUARD IS STRUCTURAL, NOT A LIST OF ROUTES.** It parses every
`@router.post` with its own handler and fails when a write route's permissions
all end in `.view`. A write route added next month is covered without anybody
remembering the file exists — which matters, because the defect it encodes was
found by a reviewer reading a diff, and reviewers do not read every diff.

The fixture commits, because the route runs on its own connection, and therefore
tears down explicitly. Measured: `RT-` orgs 26 before and 26 after, competitor
products 0 before and 0 after.

## 2026-08-28 (late) — Phase 3 finished: the tables that had no control, and the key that had no product

**`c98420a` + the review fixes.** Migration **057 / `p1000`**, both trees.
apps/api **866 → 889 / 0 / 11**; apps/web **218** vitest; ruff, ruff format,
mypy, `tsc` and ESLint all clean.

Earlier today `dcb0c06`, `e4f52e0` and `4e32a54` shipped the safety schema and
the competitor register. Phase 3's **vertical** was unfinished: the services and
screen were uncommitted, and two of 056's four tables had a writer route with
nothing that could press it.

🔴 **`competitors.samples` AND `competitors.benchmarks` HAD A WRITER AND NO
READER.** No GET, no client function, no control — writable only by something
that was never built, readable by nothing. The defect class this project has
counted 23+ instances of, and a breach of the plan's own §10 rule that every
table gets its writer **and** its control in the same phase.

🔴 **THE SERVER HAD ALWAYS ACCEPTED `sample_id` ON EVIDENCE AND NOTHING SENT
IT** — so `manual_observation`, the whole point of the third entry mode, was
recorded unattributable every time.

🔴 **AND ADDING THAT PICKER MADE A DORMANT SCHEMA HOLE LIVE.**
`composition_evidence_sample_fk` was `(sample_id, organization_id)` while the
document key beside it was product-scoped — and 056 had written the reason next
to that one in as many words: *"a label uploaded for product A could be cited as
evidence for product B and every other constraint would still hold."* True of
samples verbatim. **Latent only because no client had ever sent the field.**
Closed by 057, which asserts the resulting constraint definition rather than
that the DDL ran. Found by the Supervisor, on the commit that made it reachable.

> **A NEW LESSON: ASK WHAT A CHANGE MAKES REACHABLE, NOT ONLY WHAT IT CHANGES.**
> Wiring a client to an existing field is not a client-side change — it is the
> first time that field's constraints carry any weight.

**TWO REVIEWERS, 15 FINDINGS, 2 OVERLAPS.** Codex 4 (VERDICT: FAIL), the
Supervisor 11. The 22nd consecutive session in which neither alone sufficed.
Full adjudication: `reviews/adjudication-c98420a-competitors-2026-08-28.md`.

- **A WRITE WAS GATED ON A READ PERMISSION.** `POST /benchmarks` required only
  `test.view`. Now `material.edit` **and** `test.view`. Measured:
  `product_development_chemist` holds both; `procurement_specialist` holds
  `material.edit` without `test.view` and is correctly excluded.
- **`POST /evidence/{id}/grade` HAD NO CALLER** — the third instance of the very
  defect this commit set out to remove, sitting beside the two I fixed. Every
  claim stayed `possible` forever, four of five confidence branches could never
  render, and `compliance.review_sds` had no browser path. **A client function
  is not a caller.**
- **EVERY WORKSPACE WRITE FAILED SILENTLY.** The page's only alert was bound to
  a *different* mutation instance on the parent component — hiding, among
  others, the **503 raised when no malware verdict could be obtained**, the one
  status the upload route insists must never read as success.
- **`verify_evidence` was the only write with no `guarded_write` and no
  `except DBAPIError`**, so two of 056's own guards escaped as a 500 over an
  aborted transaction. The proof it was meant to be caught: `_translate` already
  carried branches for both refusals and **both were unreachable**.
- **`_translate` returned raw PostgreSQL text** — schema, table and constraint
  expression — as the response body for four constraints. From=50, To=10 was
  enough.
- **A GUARD THAT PASSED BECAUSE IT COULD NOT SEE.** My own cross-tenant test
  looped over four tables while the fixture created rows in one, so three
  counted zero whatever their policies did. Codex found it. Fixed, then
  **falsified: disabling RLS on `competitors.samples` now turns it red.**
- Also: `laboratory` was a menu option the database refused every time; the
  project 403 rendered as an empty menu and a dead button; the file input kept
  its filename and would not accept the same file twice; `is_balance` was
  rendered by the matrix and settable by nothing.

**FALSIFIED BY BREAKING THE DATABASE, NOT THE CODE.** Dropping
`material_documents_supersedes_same_owner` turns two tests red including the one
asserting the SDS stays submittable; disabling RLS on `competitors.samples`
turns two more red. Both restored and re-measured.

**THREE THINGS THE TESTS SAID AND REASONING HAD WRONG:** `core.roles` has no
`organization_id` (the membership binds the tenant); a `BEFORE INSERT` trigger
runs before row CHECKs, so a constraint was unreachable until the verifier held
the permission; and triggers fire in **name** order, which makes 056's
`material_id` branch unreachable defence-in-depth while its
`competitor_product_id` branch is the load-bearing one.

**Filed I112** — the vertical has 23 database tests and not one route or service
test, which is exactly why three of the Supervisor's findings were green.

## 2026-08-27 (late) — the review fixes, and the eleven defects they carried

**`722df3d`, `0ea7709`, `91926ca`.** apps/api **846 / 0 / 11** (857 collected);
apps/web **211** vitest (was 182); `tsc`, ESLint, ruff, ruff format and mypy
clean; `next build` and `NEXT_OUTPUT=export` both verified, and the pre-paint
script confirmed in the exported `<head>`.

**Live suite on the deployed demo: 922 passed / 0 failed / 0 skipped**
(`api-live` 857 + e2e 65, two phases, same build).

Applied the 19 findings Codex and the Supervisor raised on `b84a300` /
`ad55d99`. Measuring them found four more. **Reviewing the repair found eleven
more — Codex 1, the Supervisor 10, none overlapping.**

🔴 **THE LIVE E2E SUITE RAN NOTHING AND THE TASK REPORTED EXIT 0.** A duplicate
entry name in `accessibility.spec.ts` makes Playwright refuse the **entire**
run — not a failed test, a refused suite — and the shell chain that invoked it
ended in `tail`, so the exit code reported belonged to `tail`. A new guard
asserts the names are unique, because they are the test titles.

🔴 **A BLANK `display_name` REMOVED THE ONLY ROUTE TO SIGN OUT.** Returning a
null profile for a blank name removed `UserMenu`, whose single mount in
`top-bar.tsx` is the only link in the shell to Settings, Profile and Sign out.
Reachable: the parse maps an absent field to `""`. A cosmetic rule must not be
enforced by removing a control.

🔴 **THE PAPER THEME ERASED EVERY ALERT FILL** — 1.004:1 against its own page,
two in 255 in one channel. Grounds now start at the hue's `200`, which cost the
light status set its margin on them, so Paper has its own status set. The third
surface to need one, and the third time measurement said so.

| what | before | after |
|---|---|---|
| colour tokens the theme covers | 12 of 34 | **34 of 34** |
| Tailwind fallbacks | 60 hand-copied triples under a comment claiming a drift test existed | `tailwind.config.ts` **imports** `PALETTES.light` |
| theme applied | after hydration — a white flash on every load | a pre-paint script in `<head>` |
| `/api/me` identity | `email` + `display_name` from `rows[0]`, ordered by organization NAME | on each **membership**, where migration 052 put them |
| landing preference | written, validated, read by nothing | `app/page.tsx` opens on it |
| pages in the accessibility sweep | 12 | **22**, derived from the filesystem |

**I110 filed:** `SECURITY.md` §13 states a Content-Security-Policy that does not
exist anywhere — measured independently by both reviewers. **I111 filed:**
`next build` rewrites `apps/web/tsconfig.json`, committed three times now.

## 2026-08-26 (part 4) — I82 closed, across three migrations

**Migrations 049 (`h1000`), 050 (`i1000`), 051 (`j1000`).** API suite **771
passed / 0 failed / 11 skipped**; `tests/db` **382 / 0 / 0**; ruff, ruff
format, mypy clean; the `j1000 → i1000 → j1000` downgrade round-trip
exercised. CI **6/6 green on `accda56`**; `87ceffa` pushed at close and **not
yet observed**. ⚠️ **The live suite has NOT been run since these three
migrations.**

🔴 **THREE MIGRATIONS FOR ONE ISSUE, BECAUSE EACH FIX INTRODUCED THE NEXT
DEFECT — AND CI WAS GREEN ON EVERY ONE OF THEM.**

| | fixed | broke |
|---|---|---|
| 049 | removed `user_id_for_subject`'s cross-tenant read | granted a cross-tenant **WRITE** (definer INSERT keyed on a caller-settable GUC) |
| 050 | proved the caller's standing, removed `identity_created` | left the same existence answer in **`user_id`**; refusal escaped as a **500** |
| 051 | returns only `member_id`; refusal is a **403** | I106 + I107 left open, filed |

**The returned identifier WAS the existence answer.** Two rolled-back binds:
the same uuid for a subject that exists in another tenant, different uuids for
one that does not, nothing left behind. I83 was closed by *dropping* its
oracle; 050 *renamed* this one. 051 returns only the membership it minted, and
the route resolves the user through it under 044's policy.

**A database refusal is not an `IntegrityError`.** SQLSTATE 42501 arrives as
`ProgrammingError` — a sibling, not a subclass — so the standing check answered
a revoked administrator with a driver message and a 500. An unrecognised
constraint also returned 409, telling a client to change a request that was
never at fault; now 500.

Three of the tests were weak, two written the same day: a postcondition that
counted through the very session whose reads RLS was hiding, a sign-in guard
that never asserted *which* principal came back, and a mechanical rewrite that
left a duplicate and dropped an identity check. The new guards were falsified
by reverting the **database** to 050 and watching them redden.

**Left open on purpose:** **I106** — a pre-existing foreign identity's stored
email and display name are still readable through the membership before a
rollback; closing it needs tenant-scoped attributes on
`core.organization_members`. **I107** — nothing posts to
`POST /api/admin/members`, which is how the 500 survived.

## 2026-08-26 (part 2) — I105: the gate now consults the database, not the caller

**Migration 048 (`g1000`), ADR-030.** **Live suite on the deployed demo: 798
passed / 0 failed / 0 skipped** (`api-live` 761, e2e `shell` 37). CI **6/6
green** on `fd62969`. API suite **750 passed / 0 failed / 11 skipped**;
`tests/db` **370 / 0 skipped**; ruff, ruff format, mypy clean.

🔴 The live e2e's first attempt reported 7 failed / 24 skipped and that was
VOID — the run was interrupted, 8 passed then everything after skipped, the
signature of an abort. Re-run alone: 37/0/0. *A crashed worker is a void
measurement, not a red.*

I104 made the agent tier's IDENTITY checkable. Codex named the half it left:

> `bind()` validates only organization and user; it never validates roles or
> permissions. A forged principal using the real session identity therefore
> passes `bind()` while claiming arbitrary authorization.

`core.authorization_for_current_session()` returns the caller's role codes and
permission codes from `core.current_user_id()` / `core.current_org_id()` — the
same two GUCs every RLS policy reads — and `authorize()` **replaces** both
sets with its answer. The gate and the rows are derived from one source and
can no longer disagree about who is asking.

### 🔴 Not the design ADR-029 rejected, and the difference is the write

ADR-029 rejected a definer for I82 because a definer that WRITES fires
ADR-028's address guards, which inside a definer run as the table owner and
reopen I83's oracle. Every step of that chain begins with a write. This
function is `STABLE` with a single-SELECT body, so no trigger can fire, and it
takes **zero arguments** — which is what separates a lookup from an oracle.
Both facts are read from `pg_proc` by tests, not asserted in comments. Codex
confirmed it independently: *"the rejected chain required a write and trigger
execution; this function has neither."*

### 🔴 I fixed half of the sentence I quoted

The first draft derived permissions and copied `roles` straight through — half
of *"never validates roles or permissions"*, which I had quoted in the
migration header. Roles are not decorative:
`app/domains/tasks/service.py` matches unclaimed work with
`t.assigned_role = ANY(:roles)` and MSD feeds the caller's codes into it, so a
forged principal with the real identity and an invented role would have
surfaced tasks addressed to a role that person does not hold. Raised by Codex.

### The two reviewers found nine things between them, and neither found the other's

**Codex:** the roles half; a test that checked only `provolatile='s'` (which
PostgreSQL *trusts*, and is not transitive); an ordering test that searched
`ast.dump()` — **which includes docstrings**, and every conductor now discusses
`authorize()` in prose, so a conductor could delete the call and still pass;
a `search_path` assertion that would have accepted `public`; and `verified`
described as stronger than a boolean can be.

**Supervisor:** the `roles` half had **no database coverage at all** —
`_perms()` read only `a.permissions`, so changing the aggregate to
`mr.role_id::text` left everything green while MSD matched on values
`assigned_role` never holds; a test that **committed to shared seeded data**
against conftest's no-residue contract; four live references to a function
name `pg_proc` has never held; a module docstring still explaining a deleted
method; a **dead** `_ExplodingSession` the file docstring still credited as
its enforcing mechanism; `_call_positions` taking the first `ast.walk` match
(**breadth-first, not source order**) and descending into nested defs; and
`REVOKE ALL … FROM PUBLIC` asserted by nothing, while PUBLIC EXECUTE is the
default — I81's *"assert the privilege, not the SQL"*, one object type over.

### ⚠️ One thing attempted and withdrawn

Codex asked that the I56/I58 cutover be pre-empted with a real FORCE-RLS
measurement rather than a warning. It was written and it **hangs**:
`ALTER TABLE ... FORCE` takes ACCESS EXCLUSIVE on six shared `core` tables and
a live API pool holds them — `lock_timeout` and fixture rollback were both
insufficient, and the run had to be killed at 120s. The Supervisor reproduced
it with pids and added that a hard kill would leave FORCE on. **A suite-hanging
test is worse than a documented gap**, so it is withdrawn with the attempt and
the reason written into the test file. The measurement is still owed, and its
home is the cutover itself.


## 2026-08-26 — the orchestrator stopped trusting its arguments, and Intelligence got a screen

No migration. **Pushed at `e8cd7fd`; CI 6/6 green** (run 32982603290 — Auth,
API image, Security scan, E2E, Web lint/type/test, API lint/type/test).
**Live suite on the deployed demo: 784 passed / 0 failed / 0
skipped** (`api-live` 747, e2e `shell` 37), one complete run, over a preflight
that reported all four capabilities CONFIGURED. Local API suite **736 passed /
0 failed / 11 skipped**; web **148 passed / 0 failed**; ruff, ruff format,
mypy (96 files), `tsc` and `next lint` green.

🔴 **The three new Intelligence tests ran in a real Chromium against the
deployed site** and are recorded `STATUS expected` in Playwright's own detail
file — exercised, not merely un-skipped. e2e went 34 → 37, exactly the three
added; `api-live` 720 → 747.

🔴 **And the two analytics gates were MEASURED on the deployed API, per role,
rather than asserted:**

| user | role | analytics | report | by_project |
|---|---|---|---|---|
| `chem.demo` | chemist | 200 | 200 | **null** |
| `proc.demo` | procurement_specialist | 200 | **403** | null |
| `dir.demo` | director | 200 | 200 | **1** |
| `exec.demo` | executive_viewer | 200 | **403** | **1** |
| `tech.demo` | laboratory_technician | **403** | 403 | — |

`executive_viewer` gets the portfolio and is refused the report, which is the
proof the two permissions are independent gates rather than one wearing two
names. `laboratory_technician` holds `project.view` and is still refused, so
`analytics.view` is genuinely a different question.

Four departments existed and one door was ajar in three different ways.

### 🔴 I104 — every entry point took `permissions` as an ordinary argument

`root_orchestrator` took `organization_id`, `user_id`, `role_codes` and
`permissions` as keyword arguments, and a docstring asking callers to pass
real ones:

> EVERY ARGUMENT HERE COMES FROM A VERIFIED PRINCIPAL, NOT FROM THE REQUEST BODY.

That was a **comment asserting a rule the code did not have** — this
repository's most-repeated defect, sitting on top of its authorization
boundary. An in-process caller could pass
`permissions=frozenset({"test.confirm"})` and be believed, or substitute a
colleague's `user_id` and read what was waiting for them. The conductor gate
would then consult the forged set and open. Raised by Codex on 08-25.

`app/agents/principal.py` replaces the four arguments with one
`AgentPrincipal`, and adds the mechanism that is not in Python at all:

```
bind(session) → SELECT current_setting('app.current_org',      true),
                       current_setting('app.current_user_id',  true)
```

Those are the two GUCs `app/core/db.py::set_context` sets and **every RLS
policy reads**. If they disagree with the principal, the rows the session can
see are not the rows the principal may see — which is precisely the state in
which a gate answers for one person while the query answers for another.
Substituting a colleague now means disagreeing with the database, not passing
a different argument.

It also converts three docstrings that *claimed* "the session must be the
caller's own RLS-scoped session" into something checked. `bind` returns the
session, so the check cannot be skipped by forgetting a line.

Falsified in four directions before anything was built on it: an unscoped
session, another tenant's, a colleague's, and the caller's own.

### 🔴 AND THE TYPE CLAIMED MORE THAN IT ENFORCED — CODEX FOUND FOUR BYPASSES

All four were **reproduced against the real code** before anything changed:

| Bypass | Status |
|---|---|
| `of(SimpleNamespace(...))` — duck-typed, so any object could claim anything | **closed** — exact `type(...) is Principal` check |
| `dataclasses.replace(real, permissions=forged)` — replayed the guard out of a legitimate principal | **closed** — the guard is a nonce, minted per construction and consumed on use |
| importing the private `_FACTORY_GUARD` | **closed** — there is no long-lived sentinel any more |
| `object.__new__` + `object.__setattr__` | **OPEN, and asserted open by a test** |

The last cannot be closed in Python. Code that can do it could equally call
`session.execute` and skip the tier entirely. What changed is the *claim*: the
module said "you cannot construct one from loose values" when you could, and
now says plainly that it is a **misuse barrier, not an in-process security
boundary**. A test asserts the open bypass stays open, so that closing it
quietly cannot re-inflate the docstring.

⚠️ **I105 is the half that is NOT closed**, and Codex named it exactly:
`bind()` validates identity and **not permissions**. A forged principal
carrying the real session identity passes it while claiming arbitrary
authorization. The fix — derive the permission set from the GUC-bound user —
needs a `SECURITY DEFINER` returning permissions for a user id, which is the
shape **ADR-029 rejected on measured evidence** for I82. Raised, not
improvised.

### MSD's orchestration layer — three of four doors went around the governed one

§0.2 names this department by name: *"MSD is reached through the
orchestrator."* Only `POST /threads/{id}/ask` did. `GET /threads`,
`POST /threads` and `GET /threads/{id}/turns` imported
`app.domains.msd.service` and called it.

`test_agent_topology.py` could not catch it — a domain service is neither a
conductor nor a tool, so importing one breaks no import rule. What it broke
was the sentence §0.2 actually wrote down.

The two reads now go through the orchestrator; the two writes stay direct,
per §4. MSD is also on `boundary.require` at last — it was the one department
still doing its checks inline, which `boundary.py`'s own docstring had cited
as the pattern it was generalising, and which failed on 08-25 when
`explain_result` called the testing tool with no check at all.

🔴 **And reading a conversation now requires `msd.use`, like asking does.**
The permission is *what an administrator revokes when MSD must be switched off
for somebody*, and it gated asking alone — so a revoked user could still
re-open every answer MSD had ever given them. **Measured before changing it:**
the only seeded roles without `msd.use` are `executive_viewer` and
`administrator`, and `POST /ask` has refused both since it shipped. Neither
can own a thread. Nobody loses a conversation they could have had.

### `analytics.view` and `analytics.portfolio` enforced nothing

Measured against `002_seed_roles_permissions.sql`:

| Permission | Roles holding it | Lines of code reading it |
|---|---|---|
| `analytics.view` | 9 of 10 | **0** |
| `analytics.portfolio` | 2 of 10 | **0** |

`report.generate` was the third of that set and got a home on 08-25; these two
did not. *Ask of every permission which production path enforces it, not only
of every role.*

`app/domains/analytics/service.py` + `GET /api/analysis/analytics` give both a
first enforcement point, as **two distinct gates** — the catalogue reserved two
and described the difference itself (*"in scope"* against *"organization-wide
portfolio"*). Collapsing them onto one would have left the other decorative,
which is the defect being fixed, re-committed.

🔴 **The portfolio section is withheld BEFORE it is computed, not filtered
after.** §7 filters before, never after — and here that is also the bill:
`portfolio_by_project` runs one report per project, each costing a detail read
per test. "Compute then hide" would perform the entire privileged aggregation
for somebody not entitled to its result. `by_project` is `null`, never `[]`:
an empty list claims the organization has no projects.

⚠️ **Nothing in it derives a status.** Every disposition comes from
`test_results_report` → `get_test` → `derive_disposition`, the single caller of
§10's ordered algorithm. The laboratory half groups a *stored* batch lifecycle
column, which is why a `GROUP BY` is legitimate there and never for a test.

### Intelligence now exists in a browser

`/analytics` and `/reports` are real screens. **`GET /api/analysis/reports/test-results`
shipped on 08-25 with no browser caller at all** — Reports sat at slice 20 in
`navigation.ts` and rendered inert, so the endpoint existed, was tested, and no
person could press anything that called it. The twenty-fourth orphaned route,
one day after twenty-three were closed.

Both are `LiveOnly` with **no demonstration fixture, deliberately**: a
fabricated "9 tests GREEN" is a safety claim about physical measurements that
were never made. Both show colour **and** icon **and** word (§11), and both
show the automatic evaluation beside the final disposition, never merged
(§10).

### Three defects the suite and the reviewers caught in this work

1. **An uncast `:project IS NULL` bind.** `tests/test_no_untyped_null_binds.py`
   read the new query and failed it. It would have 500'd on the *unfiltered*
   call — which is the call a browser makes by default — exactly as
   `/api/materials`, `/api/formulations` and `/api/suppliers` did on 08-22
   under a green suite. The eleventh instance of a pattern, caught on the day
   it was written because the rule is instrumented rather than restated.
2. **Two analytics counts over fields the rows do not carry.** The first draft
   counted `review_state` and `validity_status`; `test_results_report` returns
   neither, so both would have come back `{"unknown": n}` — correct-looking,
   plausible, meaningless. `_count` now raises for a key absent from every row.
3. **The screen invented its own truncation limit** — `capped at {"200"}`, a
   literal that merely matched the frontend's default request. `?limit=10`
   would have been reported under a cap of 200. Raised by Codex. The service
   returns the cap it applied, per project too.

### And two of my own new tests could not detect what they named

Found by breaking the code on purpose, which is the only thing that would have
shown either:

* **A set comparison cannot count.** `_route_permissions("msd.py") == {"msd.use"}`
  stayed green with one of four routes ungated — the other three still
  contributed the same single element. The ungated route was invisible to the
  test written to find it.
* **A test a comment can redden is a test nobody trusts.** The truncation test
  searched the page source for `capped at {"200"}` and found it *in the comment
  explaining the fix*. Comments are stripped before the search now; the
  inverse — a comment satisfying an assertion — is the same failure and the
  more dangerous direction.
## 2026-08-24 — twenty-three routes had no caller, and one of them was hiding a float

No migration. API suite **671 passed / 0 failed / 11 skipped**; web **137
passed / 0 failed**; `next lint`, ruff, ruff format and mypy (86 files) green.

Laboratory, Testing, Formulations and MSD were measured route by route against
the code that calls them. Of **37 endpoints across the four modules, 23 had no
production caller** — no browser could reach them at all.

| Module | Endpoints | Reachable before | Reachable now |
|---|---|---|---|
| Laboratory | 11 | 10 | **11** |
| Testing | 9 | 1 | **9** |
| Formulations | 13 | 1 | **13** |
| MSD | 4 | 2 | **4** |

### 🔴 I84 — EVERY MEASUREMENT ON THOSE ROUTES WAS A FLOAT

`jsonable_encoder` maps `Decimal` to float. `app/domains/formulations/service.py`
had **no conversion helper of any kind**, and `testing.get_test` assembled
`statistics` and `automatic_evaluation` *after* its row-level `_decimal_strings`
had run. Measured against the running service, before the fix:

    percentage                 2.5                  float
    density_g_cm3              2.2                  float
    cost_per_kg                6.4                  float
    theoretical_density_g_cm3  1.0906918323011936   float

`CLAUDE.md` §5 — *"NUMERIC, never float, for percentages, masses, densities and
measured values"* — was satisfied in the database, satisfied in the engine, and
satisfied nowhere in between.

**The orphaned route was hiding it.** This is the identical defect
`tests/test_laboratory_testing_serialisation.py` was written for on 2026-08-19,
and that file's own header explains why it had survived: *"no screen was wired
to these routes yet, so no client had ever parsed the response"*. The fix that
day reached exactly as far as the routes wired that day. It was found the same
way again — by wiring a screen to routes nothing had ever called.

Fixed at the **response boundary only**, never at load: the engine needs real
`Decimal`s, and stringifying in `_load_components` would break every
calculation that reads them.

### 🔴 I85 — AND THEN THE STRINGS CARRIED FALSE PRECISION

With I84 fixed, a theoretical density became
`1.092376966584235260696368803` — twenty-eight significant digits asserted from
inputs recorded to four, because the engine divides at full `Decimal` context
precision and deliberately does not round. Rule 3 requires a theoretical
density presented **as calculated**, not dressed up as measured.

Quantized to `0.0001` at the response boundary, never in the engine —
`test_formulation.py` asserts `binder_to_filler_ratio` is exactly
`Decimal("40")/Decimal("60")` and the engine must go on answering that exactly.
Four places is not invented: `scripts/build_demo_formulations.py` already
quantizes these same properties to `"0.0001"`, and the build-time fixture and
the live API render onto the **same screens**.

### 🔴 I86 — THE LIST COULD NOT REACH THE WORKSPACE, WHICH IS WHY THERE WAS NONE

Twelve of the thirteen formulation routes are keyed by `version_id`.
`list_formulas` returned the latest version's code, number and status — and
**not its id**. A `version_code` is unique per formula, not per organization,
so it is a label and not a key.

The browser therefore had no identifier with which to open any version-scoped
route, and `/formulations/[code]` rendered `lib/demo/dataset.ts` instead. This
was never a missing screen; it was a missing column that made the screen
unbuildable, and a build-time fixture quietly stood in for it.

### I87 — the difference engine was missing two of its named columns

§H Slice 3 specifies *"old / new / Δ / %Δ"*. `compare_versions` returned the
two percentages and a categorical `change`, and its docstring explained the
omission: the delta *"is a SUBTRACTION OF TWO PERCENTAGES … the one place that
may subtract them is the engine."* **The refusal was right and no such engine
function was ever written**, so the gap sat behind a correct-sounding comment.

`component_delta` returns percentage-POINT and RELATIVE movement as separate
named fields — 2.5%→5.0% is 2.5 points and 100% relative — and `None` for an
added or removed component, which has no delta rather than a zero one.

### I88 — MSD had a complete memory and no way to read it

`GET /threads` and `GET /threads/{id}/turns` both existed, were tested, and
neither had a caller. `MsdPanel` kept its thread id in a `useRef`, so every
reload began an empty conversation on top of a complete server-side record —
a route with no caller surfacing as *"the assistant forgets everything"*.

The panel now adopts the caller's most recent thread and replays it. **A
replayed answer keeps the disclaimer read from its stored turn**, never a
constant, so §7 holds on history exactly as it does live.

### I89 — the bench could do everything to a batch except create one

Ten of eleven laboratory routes had a caller; `POST /batches` did not. Every
batch on screen had been inserted by a seeding script, so the lifecycle was
demonstrable only on records no user could have produced. Found by Codex.

### The review round — Codex 4, Supervisor 10, one overlap

Thirteenth session running in which neither reviewer alone was enough.

#### 🔴 The central claim of this session's first commit was FALSE

`a14c95f` said all 37 endpoints had a production caller. Codex checked it
rather than believing it, and found `createBatch`, `createTest`,
`createFormula` and `classifyFormula` referenced **nowhere but at their own
definitions**.

**A client function is not a caller.** It is the same defect the commit exists
to remove, moved one layer up, with a function standing where the person
pressing something should be.

It was closed by building the callers, not by editing the claim — and doing
that first required two routes that did not exist:

* `GET /api/testing/methods`
* `GET /api/formulations/classifications`

Without them a planning form has no method to offer and a reclassification
form has no level, so the create routes were **unreachable by construction**.
That is §H's own warning turned on this session: *"every 'editable in
Administration' escape hatch resolved to a screen nobody was scheduled to
create."*

The four controls then went where the digital thread already carries the
identifier they need — plan-a-test on each **sample** of the bench (§5:
no result without the specimen it came from), create-a-batch on the formula
**version** (§2: the one id the batch queue does not have), create-formula
against a chosen project, and reclassify on the workspace.

#### 🔴 Four comments asserted a rule the code did not have

`apiRequest` throws `ApiError` with a generic message and puts the server's
own explanation in `.detail` — which **no screen read**. So the formula
workspace rendered "the API refused this request (422)" beneath a comment
saying *"the server's own sentence … explains why"*, and the test workspace
did the same beneath *"a 403 is surfaced as the sentence the server sent"*,
losing the ADR-019 segregation-of-duties distinction that is the only reason
a 403 there is interesting.

Measured against the running service, a blocked submission returns:

    {"message": "this formula cannot be submitted",
     "blocks": [{"code": "TOTAL_OUT_OF_TOLERANCE", ...},
                {"code": "RESTRICTED_MATERIAL",     ...}]}

**Every block was discarded** — on a route whose own docstring says returning
one at a time *"is how a form teaches people to distrust it."* New
`serverMessage()` handles all three detail shapes and renders all of them.

#### 🔴 The only path that creates a revision returned 422 every time

`RevisionCreate` requires `change_reason`, `technical_hypothesis` **and**
`driver_type`. The client interface declared the first, made the second
optional and omitted the third entirely, so the type system could not catch
it — and the control the workspace itself labels *"the only way a formula
changes"* failed on every press.

#### Four inert mechanisms

An `invalidateQueries` key matching **no query in the application**, under a
comment claiming it kept the failure queue current. A failed `/evaluation`
rendering **"Calculating…" for ever** because the hook's error was discarded.
A submission `note` posted to a route that declares no request body. And
`quantize` sitting **outside** the `try` that exists so this function never
propagates.

#### Three of my own, found while re-verifying rather than by either reviewer

`GET /methods` landed at `/api/testing/tests/methods`, because the testing
router is mounted at `/api/testing/tests` — a method is not a sub-resource of
a test, so it now has its own `reference_router`. Two hooks — `useMsdThreads`
and `useMsdTurns` — that **nothing ever called**, deleted rather than kept.

And deleting them silently took **`useWeighUp`** with them, because it sat
between the deleted block and the next marker. `next lint` caught it. The
typecheck I had already read as "clean" was still being written:

> **An empty output file is not a passing run.**


### Built

* **`/testing/test?id=…`** — the test workspace. Both status fields side by
  side and labelled (F31), the raw replicates with the exclusion control and
  its mandatory reason, the statistics with `null` rendered as a named absence
  rather than a zero, the snapshotted approval ladder showing **undecided**
  steps because an undecided step is the answer to "what requires action?",
  all seven decision types, and the rule number that decided the colour.
* **`/formulations/formula?version=…`** — the formula workspace on live tenant
  data: composition, derived properties (each a value **or** the engine's own
  sentence saying why not), the weigh-up sheet, and the difference against the
  parent with both delta columns.
* Query parameters, not `[id]` segments — under `output: "export"` a dynamic
  segment must enumerate its params at build time, so it would pre-render the
  seeded records and 404 every real one.

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
