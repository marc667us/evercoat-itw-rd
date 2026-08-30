# IMPLEMENTATION PLAN — Public Landing Page, Global Marketplace, Industry News Feed

**Status: ADJUDICATED v2 — two review passes complete. Building.**
Pass 1: Codex spec read (`tmp/spec/codex_pass1.md`). Pass 2: Codex plan review, 13 findings, `CODEX VERDICT: REVISE 1,2,5,6,8,9,10,11,12,13` (`tmp/spec/codex_pass2_review.md`) + an independent Supervisor pass (S1–S6, below). **All accepted; #1 accepted with a corrected rationale.** See §13.
Author: Claude · 2026-08-30 · Base: `master` `da5c93a`, migration head `q1000` (058)
Source spec: `tmp/spec/landing_page_spec.txt` (owner PDF, 12 pages) + `TODO.md` §1 (owner verbatim, 2026-08-29)

---

## 0. THE ONE-SENTENCE SHAPE

A **new, non-tenanted `public_intel` schema** serves a **new, anonymous, read-only `/api/public/*` router** over a **new low-privilege `evercoat_public` connection**, rendered by a **new public `/` landing page** — and it touches the existing tenanted verticals at exactly one point: an optional, nullable link from a tenant's private dossier to a public catalogue row.

Everything below follows from that sentence. If a reviewer disagrees with it, stop there — the rest is downstream.

---

## 1. WHAT I MEASURED (not inherited from the handover)

| # | Fact | Evidence |
|---|---|---|
| 1 | `competitors.products` is **strictly tenant-scoped** — `organization_id UUID NOT NULL`, tenant-qualified unique key, tenant-qualified FKs to projects/documents/samples/evidence | `apps/api/migrations/056_competitor_intelligence.sql:78-96` |
| 2 | The migration **already rejected a global unique key**, for the I83 oracle reason: *"a globally unique one would stop org B registering a product org A already has, and the refusal itself would disclose org A's record"* | same file, lines 91-94 |
| 3 | **No pricing exists.** Zero matches for `price\|cost\|currency\|msrp` across the competitor migration | measured |
| 4 | `/` is a **client-side redirect honoring a per-user preference**, not `redirect("/dashboard")`. Carries a long comment about `output: "export"` shipping `out/index.html` as an error document while `next build` exited 0 | `apps/web/app/page.tsx:1-40`, `apps/web/lib/preferences.ts:69` |
| 5 | The redirect is **asserted by an e2e test** | `tests/e2e/shell/navigation.spec.ts:40` |
| 6 | The **agent tier already exists** — root orchestrator, 9 conductors, 7 tool modules, LangGraph (ADR-002) | `apps/api/app/agents/` |
| 7 | Keycloak **self-registration is off** | `services/keycloak/realm/evercoat-realm.json:6` |
| 8 | A **synthetic-data labelling precedent already exists** — `dataset.ts` declares every record synthetic, `DemoBanner` is a standing notice, `LiveOnlyPage` renders nothing rather than inventing records | `apps/web/lib/demo/dataset.ts:47`, `components/ui/demo-banner.tsx:6`, `components/ui/data-source-banner.tsx:171` |

**Codex pass-1 read is at `tmp/spec/codex_pass1.md`** and independently reached (1), (2), (7) and (8).

---

## 2. THE SPEC IS BIGGER THAN `TODO.md` RECORDED

`TODO.md` §1 and `RESUME_HERE.md` describe **landing page + marketplace**. The PDF adds a **second public surface** neither mentions: a **Global Competitor Industry News Feed** — 9 tables, ~25 categories, a 10-stage ingestion pipeline, Tier 1–4 source governance, public/internal projections of one record, per-role dashboard surfacing, and an action drawer writing into Research/Project/Material/Knowledge.

**This plan does not attempt all of it.** §7 states what is deferred and why nothing dangles.

---

## 3. DECISION 1 — anonymous read is a CONNECTION, not a flag

**Adopt the ADR-032 pattern** (migration 053, `evercoat_auth`): privilege follows the connection.

```
evercoat_public   NOINHERIT  NOBYPASSRLS  NOCREATEDB  NOCREATEROLE  LOGIN
  · SELECT on public_intel published VIEWS only
  · ZERO privileges on core, materials, formulations, projects,
    competitors, testing, research, messaging, audit
  · never sets a tenant GUC — it has no tenant
```

Served by a **separate SQLAlchemy engine/pool** (`PUBLIC_DATABASE_URL`), mounted at `/api/public/*`, with **no auth dependency at all** — not an optional one.

### Why not `permit_anonymous` on existing routes

`GET /competitors/products` requires `material.view`, derives the organization from the authenticated principal, and calls a tenant-shaped service (`apps/api/app/api/competitors.py:135`, `domains/competitor_intelligence/service.py:225`). Making that dependency optional creates an **authentication-bypass seam on a router that also carries writes, document access, samples, evidence and benchmarks**. One missed projection leaks tenant notes, evidence or project linkage anonymously. It also invites a fabricated default organization context.

### Why views, not `SECURITY DEFINER` functions

Codex proposed `EXECUTE` on read-only functions. **I am deliberately choosing views instead.** A `SECURITY DEFINER` function runs as its owner and *cannot identify its caller* — the exact trap recorded in the I109 lesson ("when a function cannot identify its caller, no check inside it can authorize the call"). A view owned by `evercoat_owner`, granted `SELECT` to `evercoat_public` and to nobody else, carries the `publication_status = 'published'` predicate **in the view definition** where it cannot be argued with, and the boundary is the grant, not a check inside a function.

### 🔴 SUPERVISOR CORRECTION (S4) — `security_invoker` is INVERTED here, and that must be stated

This repo's convention is that `security_invoker = true` is **load-bearing**: migration 037 uses it so `materials.usable_documents` runs as the **caller** and RLS applies per tenant. Without it the view would run as `evercoat_owner` and read across every tenant (`migrations/037_one_definition_of_a_usable_document.sql:28-49`).

**The public views need the OPPOSITE — the default, `security_invoker = false`.** They must run as the owner, precisely so `evercoat_public` needs **no privilege on the base tables**. Setting `security_invoker = true` here would force granting `evercoat_public` `SELECT` on `public_intel` tables directly, dissolving the whole boundary.

This inversion is safe **only because `public_intel` has no tenant** — there is no per-caller row filtering to lose. That reasoning must be written into the migration, because a reviewer applying house convention would otherwise "fix" it into a hole.

### SUPERVISOR CORRECTION (S5) — RLS posture, stated rather than omitted

Recent migrations are **FORCE RLS from birth** (056 has 4 such statements, 058 has 8). `public_intel` tables are **deliberately exempt**: they carry no `organization_id`, so tenant RLS has nothing to filter on and a policy would be decoration. **The boundary is the grant, not a policy** — which is why the migration must assert, in both directions, that `evercoat_public` can read the published views and **cannot** read any base table or any tenant schema.

### The REVOKE that must not be forgotten

Per migration 053's lesson — **a REVOKE against a narrower grant does nothing**. `REVOKE ALL ON SCHEMA public_intel FROM PUBLIC` must run *before* the grant to `evercoat_public`, and the migration must **assert the resulting privilege** via `has_table_privilege`, never assert that the statement ran.

**Falsification:** a test that connects as `evercoat_public` and asserts `SELECT` on `competitors.products` **raises**, and asserts the published view **returns rows**. Both directions.

---

## 4. DECISION 2 — a new schema, not a flag on `competitors`

```
public_intel.manufacturers      -- global, no organization_id
public_intel.products           -- global catalogue; pricing lives here
public_intel.product_documents  -- datasheet / label / literature / SDS links
public_intel.news_sources       -- with tier 1..4
public_intel.news_categories    -- 6-8 to start, not 25
public_intel.news_items
```

`competitors.products` gains **one nullable column**: `public_product_id UUID REFERENCES public_intel.products(id)`. A tenant may *point at* a public row. Nothing copies automatically; drift is reconciled by a reviewed action, never a sync job.

**Rejected:** `is_global` / nullable `organization_id` on `competitors.products`. It breaks ADR-014's mandatory tenant-qualified key, every composite child FK, the RLS policies, audit attribution, and re-opens the I83 oracle the table's own comment closed.

**Pricing** lives on `public_intel.products` as `price_amount NUMERIC(14,4) NULL`, `price_currency CHAR(3) NULL` (**ISO code, never a symbol** — SolarPro's rule), `price_as_of DATE NULL`, `price_source_url TEXT NULL`. Nullable because an unpriced product is honest and a zero is not.

🔴 **`NUMERIC` must not reach the client as a float.** This is the `get_material` defect from 2026-08-29 repeating. Every public schema serialises money as a **string**, and a test asserts the JSON type is `str`.

---

## 5. DECISION 3 — "Sign Up" is **Request Access**, not account creation

Self-registration into a tenanted R&D system is not a form. The landing page's Sign Up opens an **access request** (`public_intel.access_requests`): name, work email, company, reason. It creates **no identity and no membership**.

🔴 **SUPERVISOR CORRECTION (S3). My first draft said "rate-limited". THIS API HAS NO RATE LIMITING.** The only occurrence of the phrase in the entire backend is a comment recording its absence: *"an obvious abuse surface on an API with no rate limiting (I18)"* (`apps/api/app/api/msd.py:57`). Writing "rate-limited" into a docstring for a mechanism that does not exist is precisely the *comment-asserts-a-rule-that-does-not-exist* defect this repo has catalogued repeatedly.

So either:
- **(i)** build a real limit for this one route and say what enforces it, or
- **(ii)** ship without one and **say so in the code**, treating unauthenticated write abuse as a named open risk against I18.

**Recommendation: (ii) for the first slice**, because an unauthenticated `POST` that only inserts a review-queued row with no side effect is a bounded risk, and a fake limit is worse than a named absence. The route's docstring must state it. **Reviewer: overrule me if you disagree — this is an unauthenticated write on an API with no limiter.**

An administrator holding `admin.users` reviews it and uses the **existing** bind route (`apps/api/app/api/admin.py:270`) to create and bind the Keycloak subject to a chosen organization with a least-privilege role.

**Explicitly NOT built:** Keycloak self-registration, automatic tenant creation, automatic membership, a default role. **Sign-in is unchanged** — the existing browser-side OIDC/PKCE flow required by ADR-025.

---

## 6. DECISION 4 — synthetic content carries structured provenance, not a footnote

Every `public_intel` row carries:

| Column | Values |
|---|---|
| `content_origin` | `synthetic` · `source_derived` · `verified` |
| `verification_status` | `unreviewed` · `reviewed` · `verified` · `rejected` |
| `generated_by` | model/agent identifier, nullable |
| `generated_at` / `reviewed_by` / `reviewed_at` | |
| `source_url` | required when `source_derived` (CHECK) |
| `publication_status` | `draft` · `published` · `withdrawn` |

Rules, enforced not merely documented:
- **Only `publication_status='published'` is visible in the public views.** In the view definition.
- Any card whose `content_origin='synthetic'` renders a **persistent, non-dismissable badge**, reusing the `DemoBanner` precedent rather than inventing a second notice.
- 🔴 **Real manufacturer names attached to invented prices, SDS links or technical claims must never be published as fact.** A CHECK forbids `content_origin='synthetic' AND publication_status='published'` unless `is_demonstration_data = true`, which the badge reads.

### 🔴 THE DECISION I WILL NOT MAKE ALONE

The owner asked for **50 competitors and 100+ products, agent-managed**. This repo has **no external network gateway**, and rule 3 / §7 forbid presenting generated content as fact. Three options, none of which I will pick unilaterally:

- **(A)** Seed 50/100+ as **openly-labelled demonstration data** — buildable today, honest, but not real market intelligence.
- **(B)** Build the ingestion pipeline against **real public sources** — needs an outbound network gateway, source allowlist, robots/ToS compliance and licence review. Not a this-session task.
- **(C)** Ship the surface with a **small set of genuinely-sourced rows** and grow it.

**Recommendation: (A) now, structured so (B) drops in without a migration** — the provenance columns above are exactly what (B) needs. **This goes to the owner, not to a reviewer.**

---

## 7. DECISION 5 — the news feed's first slice is THREE tables

Build `news_sources`, `news_categories`, `news_items`. **Defer six whole tables:** `news_entities`, `news_product_links`, `news_material_links`, `news_project_links`, `news_saved_items`, `news_relevance_scores`.

**Nothing dangles**, because none of those tables and none of their inbound FKs are created. Relevance stays a **nullable labelled column** on the item, not an empty scoring table built to match a diagram. Categories start at **6–8 broad ones matching the landing-page filters**, not all 25 taxonomy leaves.

The authenticated action drawer (Save to Research/Project/Material, Create Opportunity/Task) is **Phase 2** and reuses existing Project/Task/Research/Knowledge/Material services — no news-specific substitutes.

---

## 8. DECISION 6 — `/` changes deliberately, and the preference survives

`/` becomes the public landing page.

🔴 **SUPERVISOR CORRECTION (S2). My first draft claimed only `navigation.spec.ts:40` assumes the redirect. That was wrong.** Measured: **nine call sites across seven specs** navigate to `/` and expect to land in the authenticated shell:

```
tests/e2e/shell/create-forms.spec.ts:68
tests/e2e/shell/navigation.spec.ts:43
tests/e2e/shell/permissions.spec.ts:56, :186
tests/e2e/shell/research.spec.ts:60
tests/e2e/shell/sign-in.spec.ts:73
tests/e2e/shell/theme.spec.ts:170, :176, :187
```

Every one is a real assertion about real behaviour. Each is **changed deliberately with a comment saying why — none deleted**. Most should navigate to their actual subject (`/dashboard`, `/settings`) rather than relying on `/` as a synonym for "the app"; `navigation.spec.ts` alone should keep an assertion about `/` itself, inverted to assert the landing page renders anonymously.

The per-user landing preference (`readLanding`, `DEFAULT_LANDING`) **is preserved and moves to post-sign-in**: signing in sends you to your chosen screen. A signed-in visitor hitting `/` sees the landing page with a "Go to your workspace" action, not a forced redirect.

🔴 **The `output: "export"` trap in `page.tsx`'s comment still applies.** The new `/` must be a real static page that renders content in both build modes — verified by checking `out/index.html` is not `<html id="__next_error__">`, because `next build` exits 0 either way.

---

## 9. SLICES — in build order, each shippable

| # | Slice | Contains |
|---|---|---|
| **1** | **Migration 059 — `public_intel` schema + `evercoat_public` role** — 🔴 **TWO FILES, see S1 below** | 6 tables, provenance columns, published views, REVOKE-from-PUBLIC then GRANT, privilege assertions both directions |
| **2** | **Public API + a SEPARATE public web client** — 🔴 **see S6** | separate pool, `/api/public/products`, `/api/public/products/{id}`, `/api/public/news`, `/api/public/categories`, `/api/public/access-requests` (POST). Money as string. |
| **3** | **Landing page `/`** | hero, nav, sign-in/sign-up, marketplace strip, news strip, MSD strip, footer — per the spec's ASCII layout |
| **4** | **Marketplace + product detail** | SolarPro card adopted; tabs Overview / MSD / Chemical & Physical / Literature / Datasheets / Labels / News |
| **5** | **News feed + card** | filters, category chips, source tier + provenance badge |
| **6** | **Agent management** | `market_intelligence_conductor` under the existing root orchestrator + specialists; §0.2 topology, no new framework |
| **7** | **Seed + labelling** | 50 manufacturers, 100+ products as declared demonstration data (pending §6 owner decision) |

### 🔴 SUPERVISOR CORRECTION (S1) — "migration 059" is TWO files, and must be idempotent

This repo has **two migration trees, one-to-one**: `apps/api/migrations/*.sql` (**58**) and `apps/api/migrations_alembic/versions/*.py` (**58**). CI runs `alembic upgrade head` (`ci.yml:84`, `:402`, `:625`) — so **the alembic revision is what actually executes**, and it applies the SQL via `apply_sql("059_....sql")`.

Writing only the `.sql` file produces a migration that **never runs in CI** while looking present in the tree.

CI additionally **re-runs `alembic upgrade head` and fails if anything re-applies** (`ci.yml:89-95`), so every statement must be idempotent (`CREATE TABLE IF NOT EXISTS`, `CREATE OR REPLACE VIEW`, guarded `CREATE ROLE`). 🔴 And per the catalogued lesson: **`CREATE ROLE IF NOT EXISTS` is idempotent about existence and silent about capability** — the migration must assert `evercoat_public`'s actual attributes (`NOINHERIT`, `NOBYPASSRLS`) from `pg_roles`, not assume the `CREATE` shaped them.

### SolarPro card — what is adopted

From `Desktop/solar-pv-designer-lite/templates/marketplace.html:150-260`: category eyebrow → product name → brand · model → status badge → **price right-aligned with unit and reference currency** → spec line → **Literature / Datasheet link row** → footer with supplier and actions.

🔴 **The single most valuable thing to adopt is its signed-out behaviour:** SolarPro shows the **card publicly** and routes gated actions to an **action-gate route** (`marketplace_action_gate`), rather than hiding the card. That is the pattern for "public marketplace + sign-in required to act", and it is already proven in production.

Its **self-healing document resolver** (`marketplace_product_doc_redirect` — serves the cached URL, else finds and caches on first click) is also worth adopting for datasheet/label/literature links, and directly answers the spec's requirement that every card link to them.

---

### 🔴 SUPERVISOR CORRECTION (S6) — the existing web client CANNOT make an anonymous request

`apps/web/lib/api/client.ts` states its own contract in its header:

> *"WHAT IT ALWAYS SENDS — `Authorization: Bearer <token>` and `X-Organization-Id`. The API requires BOTH... **A request built here without both is a request that cannot succeed, so the types make it impossible to build one.**"*

This is deliberate and correct, and it means the public surface **must not reuse this module**. Slice 2 therefore ships `apps/web/lib/api/public-client.ts`: no token, no organization header, its own base URL, its own typed errors.

Two consequences the plan must honour:

- 🔴 **Do not "relax" `client.ts` to make the headers optional.** That would reintroduce, on the web side, exactly the authentication-bypass seam §3 refuses on the API side — and it would weaken a module whose entire stated purpose is that an unauthenticated request cannot be *constructed*.
- `ApiNotConfiguredError` exists because the static export has no API address and callers then render the demonstration dataset behind a banner. The public client needs its **own** answer to "no API address" — and for the landing page the honest answer is an empty marketplace with a notice, **never** silently rendering `lib/demo/dataset` as though it were the live global catalogue.

## 10. TESTS — each must be shown to fail first

1. `evercoat_public` **cannot** read `competitors.products` (raises) **and can** read the published view (returns rows). Both directions.
2. A `draft` row is **absent** from `/api/public/products`; flipping it to `published` makes it appear. Falsified by reverting the view predicate.
3. Money is a **JSON string**, not a float. This is the 2026-08-29 `Decimal` defect pre-empted.
4. `/api/public/*` carries **no auth dependency** — asserted by inspecting the route's dependencies, not by a 200.
5. A `synthetic` + `published` row **without** `is_demonstration_data` is **rejected by the CHECK**.
6. Every path the public client calls is a path the API serves — extend the existing `tests/e2e/api/serving.spec.ts` (127 paths).
7. `/` renders the landing page **anonymously** in a fresh browser context with no token.
8. `out/index.html` is not an error document.

🔴 **Every guard above is falsified by breaking the thing on purpose — and where the guard is about privilege, by reverting the DATABASE, not the code.** Four of my guards could not fail on 2026-08-29; that is not repeating.

---

## 11. WHAT THIS PLAN REFUSES

- Anonymous access via weakened dependencies or RLS on `/api/competitors`.
- `is_global` / nullable `organization_id` on tenant tables.
- Open Keycloak self-registration.
- Publishing invented prices, SDS links or technical claims against **real** manufacturer names without durable provenance and a visible label.
- Creating the six deferred news tables empty to match a diagram.

---

## 13. ADJUDICATION — what changes before a line is written

Every item below is **binding on the build**. Codex numbering `C#`, Supervisor `S#`.

| Ref | Verdict | Binding change |
|---|---|---|
| **C1** | Accept, rationale corrected | Views stay — but **not** because they are "intrinsically safer" than a definer function. That was wrong. An owner-owned view runs with **owner** privilege, so the hazard is a *later join to a tenant table*, which would read across every tenant anonymously. Views are chosen for **row/column projection**. The boundary is enforced by a test: **every `public_intel` view depends only on `public_intel` tables**, checked via `pg_depend`, not by reading the SQL. |
| **C2** | Accept | One negative table test is not enough. Postgres grants `EXECUTE` to `PUBLIC` on new functions **by default** (this repo treats that as live vuln — `027:110`, `053:148`). The migration must assert **zero effective privilege outside an explicit allowlist** across tables, sequences, schemas and functions, and pin `search_path` for the role. |
| **C3** | Accept — **closes open question 2** | Same database, hardened schema. A separate database is genuinely safer but **Postgres cannot enforce a cross-database FK**, and `public_product_id` needs one. Stated as a trade, not a preference. |
| **C4** | Accept — **closes open question 3** | Not a covert channel today. The plan now **explicitly forbids** a reverse public projection, a public count of tenant links, and any public exposure of tenant product fields. |
| **C5** | Accept — **blocker** | 🔴 My CHECK could not fail. `NOT (a AND b) OR c` is **NULL** when `c` is NULL and **Postgres CHECK accepts NULL**. Required: `is_demonstration_data BOOLEAN NOT NULL DEFAULT false`, explicit boolean logic, and a **publication invariant** tying origin + review status + provenance + demo identity — not one mutable flag. `source_derived + published + unreviewed` must also be refused. |
| **C6** | Accept — **blocker** | 🔴 Beyond S2's nine call sites: sign-in stores the current pathname as `returnTo` (`auth-provider.tsx:541`) and the callback returns there (`callback/page.tsx:175`). **Signing in from the new `/` returns to `/`, not `readLanding()`.** My "the preference survives" claim was false. A slice must change that flow explicitly. |
| **C7** | Accept against myself | I over-read the `output: "export"` comment. The recorded failure was a server `redirect()` with no server. A static landing page is what export supports. Downgraded from architectural trap to a retained smoke test. |
| **C8** | Accept — **blocker** | `access_requests` is a **7th** table; §4 lists six and Slice 2 writes to it. It moves **into Slice 1**, with its grants, anti-abuse fields and assertions. |
| **C9** | Accept — **blocker** | 🔴 I deferred the news link tables **and** promised a product News tab in Slice 4. Contradiction. Worse: I never defined `news_items` columns, so my "nothing dangles" claim **was not checkable** — a claim I could not back. Resolution: `news_items` carries a **nullable FK to `public_intel.products` and `public_intel.manufacturers` only** (both public, no tenant FK), which makes the News tab and brand/manufacturer filters real. Material/technology/project filtering is **explicitly deferred and named as deferred**. |
| **C10** | Accept — **blocker** | Test 4 passes if auth is enforced inside the handler, if it 401s, or if it crashes. Test 8 passes on a blank page. Both replaced with **real anonymous requests asserting a positive projection**, and a landing-page content assertion. |
| **C11 / S1** | Accept | Two files: `apps/api/migrations/059_*.sql` **and** the alembic wrapper with `down_revision="q1000"` calling `apply_sql`. `apply_sql` exists precisely to bypass driver placeholder parsing — inline `op.execute` breaks on `:name` and `%`. |
| **C12** | Accept | 🔴 `evercoat_public` is created **`NOLOGIN`**, matching 053. LOGIN and password are deployment concerns (CI, compose, Render), never the migration — otherwise the role is unusable or the credential lands in source. `PUBLIC_DATABASE_URL` needs config + readiness validation. |
| **C13** | Accept | Choose explicitly: **access-request submissions and publication changes write `audit.events`** (nullable `organization_id` already supported, `001:351`); per-GET public reads are **operational logs, not audit events**. And state that `public_intel` tables are deliberately **non-tenanted with no RLS**, while the new `competitors.products` column stays under its existing FORCE policy. |
| **S2** | Accept | Nine `goto("/")` call sites across seven specs, each changed deliberately with a reason. |
| **S3** | Accept | No rate limiting exists. Ship without one and **say so in code** against I18, rather than writing a comment for a mechanism that does not exist. |
| **S4** | Superseded by C1 | |
| **S6** | Accept | A separate `public-client.ts`; `client.ts` is **not** relaxed. |

### What this adjudication changed about the build

Slice 1 grows (access_requests, the privilege inventory, the `pg_depend` view guard). Slice 4's News tab becomes real rather than empty. Two of my eight tests were guards that could not fail and are replaced. The role becomes `NOLOGIN`. And the landing page must carry an explicit post-sign-in redirect change, which no slice previously mentioned.

---

## 12. OPEN QUESTIONS — resolved by adjudication

1. Views vs `SECURITY DEFINER` functions for the public read path — I chose views (§3). Concur or overrule?
2. Is `public_intel` correct, or should the global catalogue live in its own **database** rather than schema, given `evercoat_public` must never reach tenant data?
3. Does the optional `competitors.products.public_product_id` link create a covert channel (does a tenant's choice of link leak anything publicly)? I believe not — the column is tenant-side and never projected publicly — but I want that measured, not assumed.
4. Rate-limiting `POST /api/public/access-requests` with no auth and no tenant: what mechanism exists in this repo today, if any?
5. §6's content-sourcing decision (A/B/C) — owner call, but flag if you think (A) is unshippable.
