# ▶ RESUME HERE — EvercoatITWRD APP

**Session 2026-08-20. Read this file, then `TODO.md`.**

Repository: **https://github.com/marc667us/evercoat-itw-rd** (PUBLIC),
branch `master`. Tip **`4598fc8`**, working tree clean, pushed.
**CI 5 of 5 green. Live suite 31 / 0 / 2 against the deployed site.**

Run `./scripts/handover.sh` first — it prints the repo tip, CI conclusion,
what production is actually serving, and the next command to run.

---

## ✅ WHAT SHIPPED TODAY — 12 COMMITS, 5 DEPLOYS, EACH WITH A LIVE SUITE

| | |
|---|---|
| `fcc1093` | API security audit — 5 defects fixed |
| `dc08863` | CI: a test pinned a framework internal; Semgrep blocked an f-string SQL |
| `9caa774` | Laboratory + Testing screens; a controlled batch mass was shipping as a float |
| `e3d9ffe` | Two navigation tests named Laboratory as their "unbuilt" example |
| `26bd487` | **MSD** — agent tier, 4 routes, side panel, migration 026 |
| `59a7c79` | `formula` vs `formula_version`, made a permanent cross-file invariant |
| `84733a9` | MSD safety data (§11) + formulation equations (§8/§17) |
| `24c5917` | **I20** — project membership cannot be self-granted (migration 027) |
| `a5ac4e0` | That escalation test matched zero rows and could not fail |
| `42b4cc9` | MSD formula comparison (§9) |
| `7ca3d1c` | An additive-only Render provisioner |
| `4598fc8` | I13 measured against the real Render API |

---

## 🔴 FIRST THING NEXT SESSION — I13, AND IT IS NOW MEASURED

**This is the only thing between the repository and a working product.**
Sign-in, Laboratory, Testing and MSD are all built and CI-proven against a
real PostgreSQL. None of them can do anything on the live site, because
the deployed artefact is a static export with no API and no Keycloak.

I built `.github/workflows/render-provision.yml` — POST/GET only, no
DELETE anywhere, name-scoped to `evercoat-itw-rd-*`, and it refuses rather
than overwrites — and **ran it against the real Render API**. Both halves
were refused, verbatim:

```
POST /postgres         -> 400  "cannot have more than one active free tier database"
POST /services free    -> 400  "free tier usage quota has been exhausted,
                                new services are not allowed"
```

🔴 **THE API KEY WORKS. THOSE ARE 400s, NOT 401s.** `GET /owners` returned
200 (`tea-d86fu8mk1jcs7397i70g`, `marc667us@yahoo.com`), `GET /services`
and `GET /postgres` both 200. Render authenticated the request and then
refused on a workspace quota. **A new or rotated key produces the identical
two errors.** Do not spend a session rotating credentials.

**Credential inventory — this decides what is possible:**

| Credential | State |
|---|---|
| `RENDER_API_KEY` | **The only repository secret.** Works. |
| `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` | Referenced by `deploy-cloudflare-pages.yml`, **NOT set** — that workflow cannot run |
| Railway CLI (installed on the dev host) | **Unauthenticated** (`railway whoami` → Unauthorized) |

**Workspace as it stands:** five `standard` web services (3 AutoWorkshop,
2 Solar) + the Evercoat static site; `solarpro-postgres` on
`basic_256mb`; `autoworkshop-postgres` on `free`.

**One command from done, once there is capacity:**

```bash
gh workflow run render-provision.yml \
  -f resource=postgres    -f plan=<paid plan> -f confirm=CREATE
gh workflow run render-provision.yml \
  -f resource=api-service -f plan=<paid plan> -f confirm=CREATE
```

Then: `DATABASE_URL` on the non-superuser app role, `alembic upgrade head`
as a role that owns `alembic_version`, a Keycloak service from
`services/keycloak/evercoat-realm.json`, and a web rebuild with
`NEXT_PUBLIC_API_BASE_URL` + `NEXT_PUBLIC_KEYCLOAK_URL` — both are
**BUILD-time**, so setting them on a running service changes nothing.

⚠️ **`autoworkshop-postgres` is the free-tier database and EXPIRES
2026-09-01.** A different app loses its database that day unless it moves
to a paid plan first. Same workspace, so it will surface here.

---

## 🔴 FOUR CONFIDENTIALITY BOUNDARIES CLOSED — ALL THE SAME SHAPE

Every one had a comment stating the correct rule sitting above a schema
that implemented a weaker one. **The words were less protected than the
room.**

| Migration | What it closed |
|---|---|
| **025** | `messaging.messages` was organization-scoped while `channels` carried the project predicate — and `list_messages` never joined `channels`. Restricted-project conversations **and other people's direct messages** were readable by anyone holding a channel id. |
| **025, 2nd round** | Found by instructing a reviewer to **refute my own fix**: self-enrolment into `channel_members`, and retyping a channel out of `direct` with one UPDATE. 🔴 **Its proposed fix would have broken direct messages entirely** — a `WITH CHECK` subquery cannot see the row its own command is inserting, so the creator's first membership row is refused. Bootstraps off the channel's immutable `created_by` instead. |
| **026** | `ai.msd_turns` / `ai.msd_evidence` were organization-scoped while `msd_threads` was owner-scoped. `msd_evidence` stores **500-character excerpts of cited records** — retrieval was filtered before the model saw anything, and the record of what it saw was not. |
| **027** | `projects.project_members` had `USING` and **no `WITH CHECK`**. One INSERT made `core.is_project_member()` answer TRUE, and **every** project-scoped policy in the database reads `confidentiality='normal' OR is_project_member(p.id)` — so one row opened formulas, batches, tests, failures, approvals and messaging. |

🔴 **On 027 I was wrong, and it cost a day.** I recorded it as unfixable
without a database because "`projects.projects` has no bootstrap column".
**`lead_user_id` exists**, and migration 006 already used it for exactly
that purpose on the read side. I had read that file the same day.
**Read the adjacent migration before declaring something impossible.**

---

## 🔴 THE LESSON OF THE DAY: EVERYTHING WAS HIDING BEHIND GREEN

Six times, twice in my own work:

1. **axe-core reported ZERO violations across an unreadable sidebar.**
   17 of 26 nav items rendered at `text-slate-300` — **1.48:1**, where AA
   needs 4.5:1. `isDisabled()` returns true for anything carrying
   `aria-disabled="true"`, and `color-contrast` skips disabled nodes.
   *The attribute that correctly described the state silenced the check.*
2. **A metrics comment promised "route template, not the concrete path"
   while the code did the opposite** — `scope["route"]` was read BEFORE
   `call_next`, so the raw-path fallback fired on every request. Anonymous
   unbounded Prometheus cardinality.
3. **`Decimal` → float.** `planned_quantity_kg` and `measured_value`
   (`NUMERIC(18,6)` — a physical measurement) shipped with their scale
   destroyed. Fixed **generically** rather than with a key list.
4. **`"weigh"` matched inside `"lightweight"`** — MSD answered a question
   about lightweight fillers with an explanation of laboratory batches.
5. **An exit code reported a deploy FAILURE for a deploy that succeeded** —
   a transient `api.github.com` timeout made `gh run list` return an empty
   id, so `gh run watch ""` failed.
6. **My own UPDATE escalation test matched ZERO rows**, so no `WITH CHECK`
   was ever evaluated. A check that cannot fail, in a test written to catch
   exactly that. It only surfaced because I used `pytest.raises`.

Each of those is now an instrument that fails if the condition returns.

---

## MSD — WHAT IT IS AND WHAT IT REFUSES

§0.2 tier: Root Orchestrator → MSD Conductor → six plain-Python tools.
Four routes under `/api/msd`, and a side panel on the top-bar control that
had been a disabled placeholder for four slices.

🔴 **The model may only `rephrase()` an already-composed answer.**
`LanguageModelPort` has exactly one method and **no method that takes a
question and returns an answer**, so a model cannot introduce a formula
code or a measurement. A test asserts the port's shape. MSD therefore
works identically with **no model at all** — which is what CI runs, what
the deployed site would run, and what §7's zero-cost rule requires.

The guarantee is stated precisely rather than overclaimed: a badly-behaved
model *can* corrupt the prose, and a test demonstrates exactly that while
showing the citations survive intact.

**Capabilities:** application guidance · pending work (delegates to
`my_work` — a third definition of the inbox was written and deleted) ·
record search · **material safety (§11, all four founder questions)** ·
**the formulation equations (§8/§17, delegating to `evaluate_version`)** ·
**formula comparison (§9)**.

**It refuses to say:** *"there are no formulas like that"* (it sees only
what the asker can read) · *"you are all caught up"* over an inbox it
could not fill · *"nothing uses RM-104"* during a recall · anything at all
without a session.

**Percentages are shown as a PAIR, never a delta** — subtracting two
percentages is arithmetic, and a number MSD prints is a number a chemist
may quote. A test asserts no computed difference appears in the output.

**Not built:** test-result explanation (§17 — `replicate_statistics` and
`derive_disposition` already exist) and knowledge/RAG search (Slice 8,
needs pgvector). Both are wiring, not new engineering. `TODO.md` I23.

---

## Constraints that must not be forgotten

- 🔴 **Solar is never part of this app.** Its workflows run on their own
  cron schedule; activity there has nothing to do with this repository.
- 🔴 **Do not touch any `aw-*` container.** This project's DB is
  `evercoat-postgres` on port **55432**.
- ⚠️ **Docker on this host is wedged.** Nothing answers on 5432 or 55432,
  so every database test's first execution is CI. Say that plainly rather
  than reporting a local pass that did not happen.
- ⚠️ **CI has a one-run-per-ref concurrency group.** Pushing evicts an
  in-progress run — a `cancelled` conclusion on the previous commit is
  usually this, not a failure.
- ⚠️ **Never** use `render-setup.yml` apply mode to force a deploy: it
  issues `DELETE` against **AutoWorkshop** custom domains. Use
  `gh workflow run "Deploy web (manual)"`.
- ⚠️ **CodeRabbit CLI 0.7.5** is installed at
  `%LOCALAPPDATA%\Programs\coderabbit` and signature-verified, but has
  **never been authenticated** — it has reviewed none of these 12 commits.
  `coderabbit auth login` is interactive.
