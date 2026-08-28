# Implementation Plan — Material Safety Data & Research Center

**Revision 2**, after Codex review pass 1 returned `FAIL` with nine P1 findings.
Every one was verified against the repository before being accepted; the
disposition of each is in §11.

Source of truth: `C:\Users\USER\Documents\ITW Evercoat 23\material safety data feature.txt`
(1,316 lines, §1–40). Where this plan and that file disagree, **the file wins**.
Where the file's *illustrative directory layout* and the repository disagree, the
file settles it itself (§32, §33: *"the existing ITW Evercoat R&D App structure
wins"*). That clause covers directory conventions **only** — it is not licence to
replace the binding data model in §18.

Every file:line below was measured in this repository by this plan's author.
Revision 1 inherited citations from a review summary without checking them and
six were wrong; they are corrected here.

---

## 0. THE NAMING RULE

**The specification never abbreviates.** Measured: `MSD` appears **0 times** in
1,316 lines. It writes the name out — "Material Safety Data" 48×, "Material
Safety Data & Research Center" 29×, "Material Safety Data Assistant" 9×.

| | Name | Identifiers | Status |
|---|---|---|---|
| Existing | **MSD** — Material Science & Development Assistant | `msd.use`, `/api/msd`, `ai.msd_threads/msd_turns/msd_evidence`, `app/api/msd.py:1`, `domains/msd/`, `conductors/msd_conductor.py`, `components/msd` | **UNTOUCHED** |
| New | **Material Safety Data & Research Center**, written in full | `safety.*`, `research.*`, `competitors.*`; `domains/material_safety/`, `domains/research/`, `domains/competitor_intelligence/`; `/api/material-safety`, `/api/research`, `/api/competitors`; `/material-safety` | New |

No new identifier contains `msd`. That removes the *namespace* collision.

🔴 **It does not remove the PRODUCT collision, and Codex was right to say so.**
Two assistants whose names both begin "Material S…" will confuse users no matter
how the code is spelled. So the copy is fixed here as a contract, not left to
whoever writes a heading:

- MSD is always **"MSD — Material Science & Development Assistant"** on first use
  in any screen, and answers *"what does the science say?"*
- The new capability is always **"Material Safety Data & Research Center"**,
  never shortened, and answers *"what is hazardous, what is documented, what has
  been researched, what is the competitor doing?"*
- Neither screen links to the other without naming which it is going to.

**T7** (§9) enforces the identifier half across **every** new or changed path —
migrations, API, web, tests, permission codes — not merely the three new domain
directories, which was Codex's P2 and is correct.

---

## 1. Phase C — collision check, measured

| Question | Answer | Evidence |
|---|---|---|
| `safety` / `research` / `competitors` schema exists? | **NO** — 16 schemas exist, none of these | `CREATE SCHEMA` sweep over `apps/api/migrations/*.sql` |
| SDS functionality exists? | 🔴 **YES, substantially** | §1.1 |
| Research bounded domain exists? | **NO** — the word appears in comments and as a planned thread stage only | `DATA_MODEL.md:245` |
| Competitor functionality exists? | **NO** — hits are comments/examples | `043_knowledge_permissions.sql:135` |
| Duplicate routes? | **NO** — the three prefixes are free | `apps/api/app/main.py:241-289` |
| Duplicate nav paths? | **NO** — `/material-safety` is free | `apps/web/lib/navigation.ts` |
| Permissions the spec asks for already exist? | 🔴 **THREE DO** | §1.2 |

### 1.1 🔴 The SDS record already exists. We add interpretation, not storage.

| Already exists | Where |
|---|---|
| `materials.materials.requires_sds` | `015:173` |
| `materials.material_documents`, `document_type IN ('TDS','SDS','CoA','regulatory','other')` | `015:195`, `015:199` |
| Revision chaining `supersedes_id` | `015:211` |
| `issued_on`/`expires_on`, `checksum_sha256`, `byte_size`, `storage_key` | `015:205-210` |
| Live upload + list routes | `apps/api/app/api/materials.py:371`, `:383` |
| Writer / reader services | `store_document` `domains/materials/service.py:1072`; `list_material_documents` `:1218` |
| Malware scan verdict + approved-document integrity CHECK | `036:69`, `036:112` |
| **`materials.usable_documents`** — approved ∧ scan-clean ∧ present ∧ unexpired ∧ **unsuperseded**, `security_invoker = true` | `037:48`, `037:68-84` |
| Document evidence + verdicts **write-once** | `038:64`, `038:115` |
| SDS ⇒ `INTERNAL`, regulatory ⇒ `CONFIDENTIAL` | `039:70`, `039:142` |

The formula-submission gate **and** the existing MSD safety tool already consume
`usable_documents` (`037:11` states this in as many words). A second opinion
about SDS validity would let submission block while this module reports the
paperwork fine.

> **RULE S1.** `materials.material_documents` owns the controlled document — file,
> validity, revision chain, scan verdict, classification.
> `materials.usable_documents` is the **only** definition of usable. This module
> owns **only interpretation**. It stores no storage key, checksum, expiry or
> supersedes pointer, and never decides usability.

🔴 **S1 HAS A TRAP.** `usable_documents` excludes a document that a newer approved
revision supersedes (`037:79-84`). So revision N leaves the view the instant N+1
is approved — and comparison needs N. Hence three parts:

- **S1a — creation.** An interpretation may be created only for a document the
  view returns **at that moment**.
- **S1b — persistence.** It is **never deleted** when its document later leaves
  the view. `CLAUDE.md:95`: never cascade-delete R&D history. This is what makes
  `compare_revisions` possible at all.
- **S1c — currency is DERIVED, NEVER STORED.**

🔴 **S1a and S1c are enforced by the DATABASE, not by the service** — Codex P1-3,
and it is correct: *a service check cannot make a direct SQL `INSERT` fail*, and
between reading the view and inserting, another transaction can approve a
superseding revision.

- **S1a** → a `BEFORE INSERT` trigger on `safety.sds_versions` that refuses a
  `document_id` absent from `materials.usable_documents`. Precedent for the
  trigger shape: `knowledge.chunk_inherits_document()` at `042:167`.

  🔴 **THE RACE IS NOT CLOSED, AND DOES NOT NEED TO BE.** Revision 2 claimed
  `SELECT … FOR SHARE` on the document row closed it. Codex pass 2 showed that is
  false, and it is right: a share lock on document D does not conflict with
  *inserting* a new row D′ that supersedes D, nor with approving D′. So S1a can
  pass while D is ceasing to be usable.

  The honest answer is that **S1c makes the race benign**. If D is superseded a
  microsecond after the interpretation is created, the result is an interpretation
  of a now-superseded document — which is exactly the **legal S1b state** that
  every revision reaches the moment its successor lands. It is history, and no
  consumer treats it as current, because every consumer re-joins
  `usable_documents`. Nothing false is recorded and nothing stale is shown.

  A lock would therefore buy nothing except the illusion of a boundary. **T1e**
  asserts this rather than assuming it: create an interpretation and supersede its
  document in an interleaved transaction, then assert the row exists, is readable
  by `compare_revisions`, and is absent from the current-position query.
- **S1c** → **there is no `status` column.** Revision 1 had one and Codex was
  right that a mutable status is a second opinion waiting to drift. Currency is a
  join to `materials.usable_documents`, every time, by every consumer — the
  current-position query, the review queue, alerts, exports and the record
  endpoints. The only stored state is `review_state`, named so it cannot be
  mistaken for document currency, and it describes the *human review workflow*,
  never the document.

### 1.2 🔴 Three requested permissions already exist — enforced nowhere

**29 seeded permissions have no enforcement point anywhere in `apps/api/app`**
(measured: seeded set minus every string named in the code). Three are ours:

| Permission | Catalogue description | Enforced today | Held by |
|---|---|---|---|
| `compliance.review_sds` | "Review SDS and safety documentation" | **Nowhere** | `qa_compliance_officer` (`002:275`) |
| `compliance.review_formula` | — | **Nowhere** | `qa_compliance_officer` |
| `regulatory.review` | — | **Nowhere** | `qa_compliance_officer` |

Defined at `002:127`. The spec §30 asks for `safety:view`/`safety:review`/
`safety:approve`; adding those verbatim would be a synonym for a fact the
catalogue already carries, in a colon convention this repo does not use
(`002:39` uses `domain.action`).

> **RULE P1.** Reuse what exists; mint only for acts with no existing holder.

🔴 **Codex P1-4 was right that revision 1 conflated review with approve.** §30
asks for three distinct acts. Full mapping, every §30 act to a real permission:

| §30 act | Permission | New? | Granted to |
|---|---|---|---|
| `safety:view` | `material.view` (safety data is information about a material) | existing | 9 roles |
| `safety:review` | `compliance.review_sds` | existing, **first enforcement point** | qa_compliance_officer |
| `safety:approve` | **`safety.approve`** | **new** | qa_compliance_officer, product_development_lead |
| `research:view` / `create` / `review` | `research.view` / `research.create` / `research.review` | new | chemist, engineer, lead / lead, qa |
| `research:approve` | approval-route step, permission `research.approve` | new | lead, director |
| `competitor:view` / `create` | `competitor.view` / `competitor.create` | new | chemist, engineer, lead, director |
| `experiment:propose` / `accept` | `experiment.propose` / `experiment.accept` | new | chemist, engineer / **chemist and lead only** |
| `restricted_safety:export` | `safety.export_restricted` | new | **lead, qa only — not the director** |

`safety.export_restricted` follows the asymmetry `039` established for
`formula.export`: seniority is not a need to remove hazard dossiers from the
building. Every new permission is granted to at least one seeded role in the same
migration — a permission with no holder is the defect this project has caught
five times.

🔴 **Resource scope is a SEPARATE GATE** (`SECURITY.md:39-40`, `CLAUDE.md:119`).
Permission answers *may this role*; scope answers *may this role, on this
project*.

Codex pass 2 was right that revision 2 *asserted* this without expressing it.
Written out, the predicate is the one `042:271` already uses for
`knowledge.documents`, and it works precisely because `project_id` is nullable:

```sql
organization_id = core.current_org_id()
AND ( project_id IS NULL                       -- organization-wide, by design
      OR EXISTS (SELECT 1 FROM projects.projects p
                  WHERE p.id = <table>.project_id
                    AND p.organization_id = <table>.organization_id
                    AND (p.confidentiality = 'normal'
                         OR core.is_project_member(p.id))) )
```

| Table | Carries `project_id`? | Scope |
|---|---|---|
| `safety.sds_versions`, `sds_sections`, `hazard_classifications`, `chemical_components` | no | organization; a material is org-wide |
| `safety.storage_rules`, `incompatibility_rules` | no | organization |
| `safety.safety_reviews`, `safety_alerts` | **yes, NOT NULL** | project predicate. `approvals.open_route` requires a `project_id` anyway (`approvals/service.py:103`), so a review without one could not open a route |
| `competitors.products` | **yes, nullable** | spec: *"may be registered against an existing Project"*. NULL = a competitor the whole organization may see, which is the normal case for a public product |
| `competitors.samples`, `composition_evidence` | inherited from the product | denormalized and trigger-maintained, exactly as `knowledge.chunks` does it (`042:167`), so the policy decides without a join |
| `competitors.benchmarks` | **yes, NOT NULL** | it names an internal formula version, which is project-scoped |
| `research.*` | **yes, nullable on `investigations`**, inherited by children | an investigation may be organization-wide research |

**T3b** is therefore testable everywhere it matters, which was Codex's point:
a member outside a restricted project must reach none of its alerts, reviews,
benchmarks, investigations, or the competitor products registered against it.

---

## 2. Phase B — ownership matrix, citations re-measured

🔴 Six citations in revision 1 were wrong. Corrected and verified:

| Information | Owner | Contract, measured |
|---|---|---|
| Project / Requirement | Projects | routes at `api/projects.py` — *no consolidated domain service; the routes are the contract* |
| Material identity, SDS file + validity | Materials | `get_material` `service.py:724`; `store_document` `:1072`; `list_material_documents` `:1218`; view `materials.usable_documents` |
| Supplier | Materials | `list_suppliers` `:932`; `link_supplier` `:958` |
| Formula / version | Formulations | `create_formula` `:193`; `compare_versions` `:954`; **`revise_version` `:1256`** — the contract experiment acceptance calls |
| Lab batch / sample | Laboratory | `create_batch` `:169`; `create_sample` `:876` |
| Test result, GREEN/YELLOW/RED | Testing | `get_test` `:1039`; `list_tests` `:1207` — **read only** |
| Root cause | Failures | `link_evidence` `:531`; `accept_root_cause` `:581` |
| Approval workflow | Approvals | `open_route` `:103` — ⚠️ **`project_id` is a required argument**, so every route we open is project-scoped |
| Discussion | Messaging | `thread_for_record` `:256` — idempotent |
| Notification | core | `notify()` `core/notifications.py:43` — the single writer |
| Knowledge | Knowledge | `ingest_document` `:132`; `retrieve` `:296` |
| Audit | core | `write_audit` `core/audit.py:135` |
| Prediction | Modeling | 🔴 **`modeling` schema has no tables.** No service exists. Out of scope; the screen says so rather than inventing one |
| **SDS interpretation, research, competitor intelligence, findings, experiment proposals** | **Material Safety Data & Research Center** | new |

---

## 3. Table inventory — reconciled to spec §18

Codex P1-1: revision 1 renamed and omitted tables from §18's "Add only" list.
Corrected. §18's names are used. Two deviations remain, and each is stated as a
deviation with its reason rather than made silently:

| §18 says | This plan | Why |
|---|---|---|
| `safety.sds_records` | **omitted** | 🔴 It already exists. `materials.material_documents` (`015:195`) *is* the SDS record — file, revision chain, dates, checksum, scan verdict, classification. Creating `sds_records` beside it is precisely what §20 forbids ("Do not copy those into sds_records. Reference `material_id`") and what §14 forbids ("Do not build a second document repository") |
| `safety.sds_versions` | **kept, as the interpretation of one revision** | The revision itself is a `material_documents` row; this is its normalized reading |
| `safety.sds_sections`, `hazard_classifications`, `chemical_components`, `storage_rules`, `incompatibility_rules`, `safety_reviews`, `safety_alerts` | kept, as written | genuinely new |
| `research.investigations`, `questions`, `sources`, `evidence`, `findings`, `hypotheses`, `knowledge_gaps`, `experiment_proposals` | kept, **all eight** — `questions` was missing in revision 1 | |
| `competitors.products`, `samples`, `composition_evidence`, `benchmarks` | kept | |
| — | `competitors.product_documents` | 🔴 **DROPPED. See §4.** Codex P1-2 was right |

---

## 4. 🔴 ONE document repository — the competitor label lives in the existing one

Revision 1 proposed `competitors.product_documents`, justified because
`materials.material_documents.material_id` is `NOT NULL` (`015:198`). The
observation is true; the conclusion was wrong. Duplicating `storage_key`,
`checksum_sha256`, `scan_status`, classification and revision invariants **is**
the second document register §14 forbids, and it would fork the write-once rules
of `038` and the usability definition of `037`. Reusing the object-storage
adapter is not reusing document ownership.

**Instead — additively extend the existing register** (migration 056):

```
ALTER TABLE materials.material_documents
    ALTER COLUMN material_id DROP NOT NULL,
    ADD COLUMN competitor_product_id UUID;

-- exactly one owner, never zero, never both
ADD CONSTRAINT material_documents_one_owner CHECK (
    (material_id IS NOT NULL) <> (competitor_product_id IS NOT NULL)
);
ADD CONSTRAINT material_documents_competitor_fk
    FOREIGN KEY (competitor_product_id, organization_id)
    REFERENCES competitors.products (id, organization_id) ON DELETE RESTRICT;

-- document_type gains the two entry modes
--   ... existing ('TDS','SDS','CoA','regulatory','other')
--   ... plus     ('label','product_image','literature','patent')
```

`materials.usable_documents` is recreated to carry `competitor_product_id`
through. Everything else it guarantees is unchanged, so a competitor label gets
the **same** malware scan, checksum, expiry and supersession rules as an SDS, and
there is still exactly one answer to "is this document usable".

🔴 **AND THREE THINGS THE FIRST DRAFT OF §4 GOT WRONG.** Codex pass 2, all three
confirmed by querying the live schema:

**(a) Supersession must be same-owner.** Measured:

```
material_documents_supersedes_fk
  FOREIGN KEY (supersedes_id, organization_id)
  REFERENCES materials.material_documents(id, organization_id)
```

Nothing constrains the *owner*. The moment a document can belong to a competitor
product, **a competitor label could supersede a material's SDS** — and because
`usable_documents` excludes a document with a newer approved successor
(`037:79-84`), that SDS would silently leave the view and change whether formula
submission is blocked. A cross-owner integrity hole introduced by the column this
plan adds. 056 therefore adds a trigger asserting the superseded row has the
**same owner** (both `material_id` or both `competitor_product_id`, equal), since
a CHECK cannot read another row.

**(b) Both owner columns join the write-once set.** `deny_document_evidence_rewrite()`
(`038:64`) names `status`, `scan_status`, `checksum_sha256`, `byte_size`,
`storage_key` — **not the owner**. Without this, an approved scanned label could
be re-pointed at a different competitor product, carrying its clean verdict.
Re-owning a document is superseding it, and supersession creates a new row.

**(c) The composite FK of §6 needs a unique key that does not exist yet.**
`material_documents` has `UNIQUE (id, organization_id)` and
`UNIQUE (organization_id, storage_key)` — measured. PostgreSQL requires a unique
key on exactly the referenced columns, so 056 adds
**`UNIQUE (id, competitor_product_id, organization_id)`** for §6's product-bound
reference to be expressible at all.

### 4.2 🔴 The writer must be generalized — extending the CHECK is not enough

Codex pass 2, confirmed at source. `store_document` (`domains/materials/service.py:1072`)
takes `material_id: uuid.UUID` as a **required positional** and opens with:

```python
if spec.document_type not in ("TDS", "SDS", "CoA", "regulatory", "other"):
    raise MaterialInvalidError(f"'{spec.document_type}' is not a document type")
```

So relaxing the column and extending the database CHECK would produce a schema
that permits a competitor label and a writer that refuses to write one — a
capability the migration claims and the code lacks.

Its own docstring states the rule to follow: *"THIS REPLACES `register_document`,
IT DOES NOT SIT BESIDE IT. A second entry point would be the I5/I36 shape this
codebase has already logged twice."* Adding a competitor-specific writer would be
that defect a third time.

**So `store_document` is generalized in place**: the owner becomes one argument
that is either a material or a competitor product, the type list is derived from
the database CHECK rather than duplicated as a Python literal (two literals in two
files cannot be type-checked into agreement), and both entry points delegate to
it. Validation, scanning, byte-limit, storage, checksum, audit and the cleanup
path are untouched and shared — which is the whole point of §14.

### 4.1 Measured against the live database, not reasoned about

Queried `pg_constraint`, `pg_policy` and `pg_get_functiondef` on
`evercoat-postgres:55432/evercoat_itw_rd`:

| Question | Measured answer | Consequence |
|---|---|---|
| Is the material FK `MATCH SIMPLE`? | `material_documents_material_fk FOREIGN KEY (material_id, organization_id) REFERENCES materials.materials(id, organization_id) ON DELETE RESTRICT` — no `MATCH FULL` | A NULL `material_id` skips the check. Relaxing `NOT NULL` is safe |
| Does the RLS policy reference `material_id`? | `org_scope` reads **only** `organization_id` | Policy unaffected |
| Does the write-once trigger reference `material_id`? | `deny_document_evidence_rewrite()` names `status`, `scan_status`, `checksum_sha256`, `byte_size`, `storage_key` — **not the owner columns** | Trigger unaffected — **and that is a gap, see below** |
| Is there a unique constraint to hang a composite FK on? | `material_documents_id_org_key UNIQUE (id, organization_id)`; `material_documents_storage_key_unique UNIQUE (organization_id, storage_key)` | §6's product-bound FK needs a **new** `UNIQUE (id, competitor_product_id, organization_id)` |
| Is `document_type`'s CHECK named? | `material_documents_document_type_check` | Extend by name, not by guess |
| Is `status` already able to say superseded? | `material_documents_status_check` allows `quarantined, approved, rejected, superseded, legacy_unverified` | Supersession is tracked **twice** — by `status` and by the `supersedes_id` chain that `usable_documents` walks. Do not add a third |

🔴 **THE MEASUREMENT FOUND A DEFECT IN THIS PLAN.** The write-once trigger
protects the *bytes and the verdict* but **not the owner**. As written, migration
056 would allow an approved, scanned competitor label to be silently re-pointed at
a different competitor product — carrying its clean verdict and checksum with it.
That is precisely the failure `storage_key`'s write-once rule exists to prevent,
reintroduced through the column this plan adds.

**So 056 also adds `material_id` and `competitor_product_id` to the write-once
set**, with the same error style as its neighbours: *re-owning a document is
superseding it, and supersession creates a new row.*

Composite FK is safe with a NULL: `MATCH SIMPLE` skips the check when any column
is NULL, and `organization_id` remains `NOT NULL`, so tenancy is unaffected.

⚠️ **Recorded as ADR-033**, because relaxing a `NOT NULL` on a hardened table is
exactly the kind of change that must be a decision with a name, not a diff.
Existing queries filter `WHERE material_id = :x` and are unaffected by rows where
it is NULL — verified by reading every consumer of the table and the view.

---

## 4a. 🔴 THREE FACTS MEASURED AFTER REVISION 2 THAT CHANGE THE BUILD

Found by measuring rather than reasoning. Each would have produced a defect.

### 4a.1 There are TWO migration trees, and CI applies the one I was not going to write

| Measured | Value |
|---|---|
| `apps/api/migrations/*.sql` | **53** files |
| `apps/api/migrations_alembic/versions/*.py` | **53** revisions, one-to-one |
| What CI actually runs | **`alembic upgrade head`** — `.github/workflows/ci.yml:84`, `:402`, `:625` |

The `.sql` files are the readable twin; **Alembic is the applied path**. Writing
only the `.sql` file produces a green CI over a schema that never existed — the
"a migration is not applied because a file exists" failure this project has
already recorded.

⚠️ **Corrected after Codex pass 2.** Revision 2 said CI's second
`alembic upgrade head` (`ci.yml:89-91`) means "every revision must be idempotent".
That does not follow, and Codex was right: Alembic's version table makes the
second invocation a no-op regardless. What the double run actually proves is that
the first run left `alembic_version` at head and nothing re-applies — a check on
the *revision chain*, not on the SQL's idempotency. The real requirement is that
the new revision chains correctly onto `l1000` (`053`) and that `down_revision` is
right.

**Every migration in §5 is written in BOTH trees**, with the Alembic revision
chained onto `l1000` (`053`) and carrying the same prose header
(`migrations_alembic/versions/2026_08_26_0053-l1000_sign_in_is_not_the_runtime_role.py:1`).

### 4a.2 A safety tool ALREADY EXISTS in the agent tier

`apps/api/app/agents/tools/safety.py` (161 lines) — `material_safety:47`,
`formula_safety:82`, `formulas_containing:119`. It already reads
`materials.usable_documents`.

🔴 **It carries a hard limit this module must not break.** Its header:
*"THIS TOOL REPORTS RECORD STATE. IT DOES NOT ASSESS HAZARD … 'RM-104 is safe to
use at 4%' is a compliance determination, and nothing here produces one."*

That rule now applies to the whole Material Safety Data & Research Center: it
reports what is documented, what is missing and what changed. **It never renders
a safety conclusion.** Hazard determination stays with the `compliance.review_sds`
holder through the review workflow, which is what §1.2's permission mapping
exists to route.

### 4a.3 The impact chain's first hop already exists — call it, do not rewrite it

`materials.material_usage()` at `domains/materials/service.py:771` takes a
`material_id` and returns `formula_version_id`, `formula_id`, `formula_code`,
`version_status` **and `project_id`** — hops 1 and 2 of §23's chain (*"find every
active formula using RM-0042 → find projects using those formulas"*), already
RLS-scoped, already indexed by `formula_components_material_idx`.

So `impact_of_revision` **calls `material_usage`** and adds only hop 3 (open
laboratory batches for those versions). Re-implementing the component join would
be the duplication `CLAUDE.md:241` forbids, and would drift from the query an
approver already relies on before restricting a material.

⚠️ `agents/tools/safety.py:119`'s `formulas_containing` does the same join on a
**fuzzy string**; it stays where it is, for the assistant. The domain service uses
the id-keyed `material_usage`, because an impact analysis that matched materials
by `ILIKE` would silently miss or over-report.

---

## 5. Migrations — additive, in dependency order

Every new table carries, without exception (`CLAUDE.md:96-101`,
`DATA_MODEL.md:51,57`): `organization_id NOT NULL`; `UNIQUE (id, organization_id)`;
**composite** child→parent FKs carrying `(id, organization_id)`; `NUMERIC` for
every concentration; `RESTRICT` deletes; no composite `ON DELETE SET NULL`;
`ALTER … OWNER TO evercoat_owner`; `GRANT` to `evercoat_app`; indexes on every
join FK and `(organization_id, review_state)`.

🔴 **AND `FORCE ROW LEVEL SECURITY` FROM BIRTH.** Codex P1-7. `CLAUDE.md:101`
requires it for every proprietary table; revision 1 waived it to match weaker
neighbours, which is not an exception to a current non-negotiable. These are new
tables with no owner-side reader, so there is no I56/I58 entanglement — the
reason the *existing* tables have not cut over does not apply to tables being
born today. Migration seeding runs before `FORCE` is enabled, or sets the GUCs.
Asserted by a test that connects **as `evercoat_app`** and by one that confirms
even the owner is refused.

| # | Contents |
|---|---|
| **054** | `safety` schema. `sds_versions` (+ `BEFORE INSERT` trigger enforcing S1a with `FOR SHARE`), `sds_sections`, `hazard_classifications`, `chemical_components`, `storage_rules`, `incompatibility_rules`, `safety_reviews`, `safety_alerts` |
| **055** | `competitors` schema: `products`, `samples`, `composition_evidence`, `benchmarks` |
| **056** | The document-register extension of §4 + `usable_documents` recreated + ADR-033 |
| **057** | `research` schema, all eight tables |
| **058** | Approval + notification integration (§6) |
| **059** | Permissions of §1.2, each granted to a role via the existing `core._grant` helper (`039`) |

### 5.1 No polymorphic pointers

Codex P1-8. `safety_alerts` in revision 1 pointed at an "affected entity" as
`(entity_type, entity_id)` — text with no referential integrity. Replaced by
**typed nullable composite FKs** (`material_id`, `formula_version_id`,
`project_id`, `batch_id`) plus a CHECK that **at least one** is present. Same for
`research.investigations`: all context links stay nullable individually, but a
CHECK requires at least one, so an investigation cannot exist detached from the
digital thread (§19, §39, §40). `benchmarks` links to real Testing rows;
`samples` links to real Laboratory rows.

### 5.2 The approval CHECK extension

Codex P1-9. `workflow.approval_routes.entity_type` is a closed list of six
(`020:140-142`). Extension is done **by name, in one transaction, after a
preflight**:

```sql
BEGIN;
SELECT DISTINCT entity_type FROM workflow.approval_routes;   -- preflight
ALTER TABLE workflow.approval_routes
    DROP CONSTRAINT approval_routes_entity_type_check;       -- named, not guessed
ALTER TABLE workflow.approval_routes
    ADD CONSTRAINT approval_routes_entity_type_check CHECK (entity_type IN (
        'test','formula_version','validation','pilot','qualification','product_release',
        'safety_review','research_finding','experiment_proposal',
        'competitor_analysis','material_qualification'));
COMMIT;
```

The exact constraint name is read from `pg_constraint` first, not assumed. In the
same migration: approval **templates and steps** for each new entity type, each
step naming the permission it requires and a role that holds it — Codex P1-4's
point that a seeded template whose steps nobody can satisfy is a queue that never
moves.

`notification_type` has **no CHECK** (`022:174` — free `TEXT` with a comment), so
the new types are purely additive: `sds.updated`, `safety.alert`,
`safety.review_required`, `research.assigned`, `research.review_required`,
`experiment.proposed`, `competitor.benchmark_complete`,
`material.restriction_changed`.

---

## 6. 🔴 The Composition Evidence Matrix — typed provenance

Codex P1-5 and P1-6 both landed here, and both were right. Revision 1's design
let a row claim `verified` while pointing at an unrelated document, let a
competitor A document back a competitor B row, forced honest manual transcription
into a category that misdescribed it, and recorded no locator.

**Two independent columns, not one.** Revision 1 confused *what kind of document*
with *what kind of evidence*:

```
evidence_source ∈ (
    document,            -- backed by a row in the document register
    manual_observation,  -- a person read the physical product/label. HONEST, and
                         -- not a synonym for inference
    laboratory,          -- backed by a real Laboratory sample / Testing result
    literature, patent,
    inference,           -- reasoned from the above
    model                -- hypothesised
)
evidence_grade ∈ (A, B, C, D, X)          -- the ranking in the research source doc
confidence     ∈ (verified, supported, probable, possible, unknown)
```

**Typed provenance, one shape per source, enforced:**

| `evidence_source` | Must reference | Constraint |
|---|---|---|
| `document` | `source_document_id` → `materials.material_documents` | composite FK **carrying `competitor_product_id`**, so a document owned by product A cannot back a row on product B |
| `laboratory` | `sample_id` / `test_id` → the Laboratory / Testing owner | composite FK |
| `manual_observation` | nothing, but **`rationale` and `observed_by` are `NOT NULL`** | CHECK |
| `inference` / `model` | nothing | `rationale NOT NULL` |

Plus `source_locator TEXT` — page, section, the quoted label field, the image
region, or the test result — because "the SDS says so" is not evidence anybody
can re-check.

🔴 **`confidence = 'verified'` is NOT self-selectable.** Codex's sharpest point: a
CHECK cannot inspect the referenced document's type or owner, and a user ticking
a box proves nothing. So `verified` is the **outcome of a controlled review
transition**, exactly like a root cause (`CLAUDE.md:56`: only a human moves a
hypothesis to accepted):

- A row is created at `probable` / `possible` / `unknown`.
- `verified_by` is `NOT NULL` whenever `confidence = 'verified'` — a CHECK, so the
  state cannot exist without a person's name on it.
- The typed reference must be present and `evidence_source ∈ (document, laboratory)`.

🔴 **AND THE TRIGGER CHECKS THAT `verified_by` ACTUALLY HOLDS THE PERMISSION.**
Codex pass 2 was right that revision 2's rule was still defeatable: anything able
to write the table could set `confidence`, a qualifying `evidence_source` and a
`verified_by` in one statement, and every stated constraint would pass. A service
function cannot prevent that, because the service is not what is executing.

What the database *can* check is whether the named person is actually entitled to
have verified it. The trigger joins `core.member_roles` → `core.role_permissions`
→ `core.permissions` and refuses unless `verified_by` holds **`compliance.review_sds`
in this organization**. Forging a verification then requires naming a real
compliance officer, in the right tenant, in the audit record — which is no longer
a quiet lie but an attributable one.

⚠️ **Stated as what it is: a misuse barrier, not a boundary** — the same
distinction this project drew for I109/ADR-032. A role that can already write
arbitrary SQL is inside the trust boundary; nothing in the row can exclude it.
The barrier raises the cost and removes every *accidental* path, and the honest
claim stops there.

**The three entry modes, honestly:**

| Mode | What actually happens | Resulting rows |
|---|---|---|
| Upload a **label** | `material_documents` row, `document_type='label'`, scanned + checksummed. **It does not populate the matrix** — extraction is out of scope (§10) and pretending otherwise was Codex P1-6 | operator then adds rows with `evidence_source='document'` pointing at it, each with a `source_locator` |
| Upload a **product image** | identical, `document_type='product_image'` | same |
| **Manual entry** | no document at all | `evidence_source='manual_observation'`, `observed_by` + `rationale` required |

All three converge on one matrix. A `manual_observation` row **can** be promoted
to `verified` only once a document or laboratory result is attached to it — which
is the rule doing its job.

---

## 7. Backend

`app/domains/material_safety/service.py`, `competitor_intelligence/service.py`,
`research/service.py` — plain functions, `__all__`, no framework import, mirroring
the existing services.

- `interpret_sds(document_id, …)` — S1a is the trigger's job; the service gives the friendly refusal.
- `compare_revisions(previous_id, current_id)` → new components, changed ranges, changed hazard classes, changed PPE, changed storage.
- `impact_of_revision(...)` — §23: material → active formula versions containing it → projects → open lab batches. Reads the owning modules' tables; writes only `safety_alerts` and `notify()`.
- `open_safety_review(...)` — gated `compliance.review_sds`; opens a route via `approvals.open_route`, **once per affected project**, because `open_route` requires a `project_id` (`approvals/service.py:103`).
- `register_competitor_product`, `attach_competitor_document`, `record_composition_evidence`, `verify_composition_evidence` (the controlled transition), `composition_matrix(product_id)`.
- `benchmark_against(version_id, product_id)` — reads Testing, computes the gap, **writes no status**.
- `create_investigation`, `record_evidence`, `record_finding`, `propose_experiment`.
- `accept_experiment_proposal(...)` — gated `experiment.accept`; **calls `formulations.revise_version` (`:1256`)** and stores the returned id in `resulting_formula_version_id`. It never inserts a formula row.
- `promote_finding(...)` — gated on the existing, currently unenforced `knowledge.promote`; calls `knowledge.ingest_document` (`:132`).

Routes in `app/api/material_safety.py`, `competitors.py`, `research.py`,
registered in `main.py` beside the others.

**No new agent specialist this slice** (§10) — §0.2 requires the root
orchestrator, and adding tools around it is the defect `test_agent_topology.py`
exists to catch.

---

## 8. Frontend

Sidebar group `Resources` becomes **`Resources & Research`** (spec §3), gaining
**Material Safety Data & Research Center** → `/material-safety`, between Suppliers
and Knowledge Library. Added to `NAVIGATION` and `BUILT_AHEAD` in
`lib/navigation.ts`; `navigation.test.ts` fails the build if an available item has
no `page.tsx`.

Pages: `/material-safety` (alerts, pending reviews, investigations, proposals),
`/material-safety/competitors/[id]` (matrix + benchmark + propose improvement),
`/material-safety/research/[code]`. Material detail gains a **Safety Data** tab.

Clients `lib/api/material-safety.ts`, `competitors.ts`, `research.ts` with zod
schemas mirroring **the response, not the SQL** — three wrong client types shipped
in two days from reading the query instead of the return value. Hooks reuse
`useLiveOnlyList` / `useLiveOnlyRecord` / the mutation shape in `lib/api/hooks.ts`.

🔴 **Every write endpoint ships with a control a person can press, in the same
commit.** 🔴 **The matrix renders grade + confidence on every row and never a bare
recipe** — colour **plus** icon **plus** text (`CLAUDE.md:233`, no colour-only
status).

---

## 9. Tests — each must fail first

- **T1a** An interpretation cannot be created for a document `usable_documents` excludes — **four cases**: superseded, unscanned, expired, unapproved.
- **T1b** An interpretation **survives** supersession and `compare_revisions` still reads it.
- **T1c** The current-position query returns nothing for a material whose only interpreted document is superseded, **though the interpretation still exists**.
- **T1d** 🔴 The refusal holds against a **direct SQL INSERT as `evercoat_app`**, not merely through the service — the assertion Codex P1-3 demanded.
- **T2a** `confidence='verified'` cannot be set on insert; only the review transition sets it, and only with a document or laboratory reference. **Both directions.**
- **T2b** A document owned by competitor product A cannot back a composition row on product B.
- **T2c** `verified` cannot exist with a null `verified_by`.
- **T3a** Cross-**organization**: org B reaches none of it. Counted as *what a user can reach*, never by reading a policy.
- **T3b** 🔴 Cross-**project, same organization**: a member without access to a restricted project reaches none of its investigations, alerts, benchmarks or competitor products. Codex P1-4.
- **T4** `accept_experiment_proposal` yields a version id the **Formulations** service returns, matching `resulting_formula_version_id`.
- **T5** Revision impact finds the right formulas/projects/batches — and **none** for a material used nowhere.
- **T6** Every new write route is reachable from a browser control (Playwright) and refuses anonymously (api project).
- **T7** No identifier under **any** new or changed path contains `msd`. Reads the filesystem.
- **T8** FORCE RLS: the suite runs **as `evercoat_app`**, and the table owner is refused too.
- **T9** Accessibility: new pages registered in `tests/e2e/shell/accessibility.spec.ts`; `lib/accessibility-coverage.test.ts` fails the build otherwise and refuses duplicate names — a duplicate title takes out the **entire** Playwright run.

---

## 10. Scope — this is a FOUNDATION slice, and says so

Codex P2: revision 1 presented a whole-feature slice while deferring much of
§§22–31, which overstated it. Restated using Codex's cut. **Nothing is split from
its control**: no writer without its UI, no approval control without its seeded
template and permission holders, no upload without central scanning.

🔴 **RE-CUT AFTER CODEX PASS 2.** Revision 2's phase 1 created competitor and
research tables whose services and screens were deferred — tables with no writer,
which is the defect this project has counted 23 of. And it deferred §31's audit
events to phase 5 while phase 2 claimed to include audit. Both were incoherent.

The cut now follows one rule: **a phase contains a whole vertical, and every
table it creates gets its writer and its control in the same phase.**

| Phase | Contents | Migrations |
|---|---|---|
| **1 — Safety schema** | `safety` schema only — the eight tables the safety vertical needs, FORCE RLS, policies, permissions of §1.2, approval `entity_type` extension + seeded templates whose steps name a permission a real role holds. **Verified on its own**: migration applies in both trees, RLS asserted as `evercoat_app`, no service or UI yet | 054, 058, 059 |
| **2 — Safety vertical, end to end** | SDS interpretation → revision comparison → current position → impact alerts (calling `material_usage`) → review + approval → notifications → **all §31 safety audit events** → routes → screens → tests. Every write endpoint gets its control | — |
| **3 — Document register + competitor evidence** | The §4 register extension incl. same-owner supersession, owner write-once, the new unique key, and the §4.2 **generalized writer**; then `competitors` tables, the typed matrix, the three entry modes, and their UI | 055, 056 |
| **4 — Research / formulation vertical** | `research` tables → investigation → finding → approval → experiment proposal → **existing** Formulations `revise_version` → Knowledge promotion | 057 |
| **5 — Cross-cutting** | §22 events, §25 contextual entry points, §27 dashboard widgets, §29 global search, §38/§39 golden scenario | — |

**Phase 1 and 2 are separable and phase 2 depends on nothing deferred.** Phase 3
is where the riskiest change lives — relaxing `NOT NULL` on a hardened table that
the formula-submission gate reads — and it is deliberately *not* mixed into a
phase that also ships a vertical, so it can be reviewed and falsified on its own.

**Explicit non-goals, as decisions:**

1. **No Material Safety Data Assistant tools.** §17 needs the root orchestrator (§0.2).
2. **No automatic extraction.** Chosen 2026-08-28: assisted manual entry, zero new dependencies. Ollama has `mistral` and `llama3.2` — measured, **neither is a vision model** — and the API declares no PDF or OCR library. The port is defined; no adapter.
3. **No product-model prediction.** `modeling` has no tables. The screen says so.
4. **No DOE integration.** Slice 12; nothing to call.
5. **No external research gateway.** Fetching the public internet is untrusted-content and prompt-injection surface needing its own review.
6. **No FORCE RLS cutover of EXISTING tables.** I56/I58 carries an owed measurement. New tables are born with it; old ones are not touched.

---

## 11. Disposition of Codex pass 1

| # | Finding | Disposition |
|---|---|---|
| P1-1 | Table inventory departs from §18 | **Accepted** — §18 names restored, `research.questions` added, two deviations named with reasons (§3) |
| P1-2 | `competitors.product_documents` is the forbidden second document repository | **Accepted in full** — table dropped; the existing register is extended additively (§4, ADR-033) |
| P1-3 | RULE S1 unenforceable; service check cannot stop direct SQL; status can drift | **Accepted in full** — DB trigger with `FOR SHARE`; the mutable `status` column **deleted**; currency derived by every consumer (§1.1) |
| P1-4 | No approve permission; resource scope missing | **Accepted** — every §30 act mapped, `safety.approve` added, template steps name permission + holder, T3b added (§1.2, §5.2) |
| P1-5 | The `verified` CHECK proves nothing | **Accepted in full** — typed provenance, composite FK binding document to the same product, `verified` only via controlled review with `verified_by NOT NULL` (§6) |
| P1-6 | The three entry modes do not converge | **Accepted** — `product_image` and `manual_observation` added, `evidence_source` split from `document_type`, `source_locator` added, upload described honestly (§6) |
| P1-7 | FORCE RLS waived | **Accepted** — FORCE from birth on every new table; T8 (§5) |
| P1-8 | Polymorphic text relationships | **Accepted** — typed nullable composite FKs + "at least one" CHECK (§5.1) |
| P1-9 | Approval CHECK drop/recreate underspecified | **Accepted** — named constraint read from `pg_constraint`, preflight, one transaction, templates seeded with holders (§5.2) |
| P2 | Six citations wrong | **Accepted** — all re-measured (§2). Revision 1 inherited them from a review summary instead of measuring, which is the failure mode this project already has a rule against |
| P2 | Naming fixes identifiers, not product confusion; T7 too narrow | **Accepted** — copy contract in §0, T7 widened to all changed paths |
| P2 | Missing §22–31 deliverables vs Definition of Done | **Accepted** — restated as a foundation slice with a named phase table (§10) |
| P2 | Too large for one session | **Accepted** — Codex's cut adopted verbatim (§10) |

---

## 11a. Disposition of Codex pass 2 (revision 3)

Verdict `FAIL`: 4 FIXED, 2 PARTIAL, 3 NOT FIXED, 2 new P1. Every finding was
re-measured against the live database or the source before being accepted.

| # | Codex pass 2 | Disposition |
|---|---|---|
| P1-1 | PARTIAL — `sds_records` still omitted | **Wording corrected, decision kept.** §11 overclaimed "§18 names restored"; the omission is one of two *stated deviations* (§3) and is right: `materials.material_documents` **is** the SDS record, and creating a second is what §14 and §20 forbid |
| P1-2 | NOT FIXED — cross-owner supersession; owner not write-once | **Accepted, both.** Measured `material_documents_supersedes_fk` — it constrains tenant, not owner, so a competitor label could supersede a material's SDS and remove it from `usable_documents`. Same-owner trigger added; both owner columns added to the write-once set (§4.1a, §4.1b) |
| P1-3 | NOT FIXED — `FOR SHARE` does not close the race | **Accepted, and the claim withdrawn.** A share lock on D does not conflict with inserting or approving D′. The fix is not a bigger lock: **S1c makes the race benign**, because the losing outcome is the legal S1b history state. Stated plainly, asserted by T1e (§1.1) |
| P1-4 | PARTIAL — scope asserted, not expressed | **Accepted.** The predicate is written out per table (§1.2), reusing `042:271`'s shape, including which tables carry `project_id` and which inherit it |
| P1-5 | NOT FIXED — FK not expressible; `verified` still settable by SQL | **Accepted, both.** The required `UNIQUE (id, competitor_product_id, organization_id)` is added (§4.1c). The trigger now checks `verified_by` **actually holds `compliance.review_sds`** — and the claim is downgraded to *misuse barrier, not boundary* (§6) |
| P1-6 | FIXED | — |
| P1-7 | FIXED — and confirms policies must be installed before `FORCE` in the same migration | noted in §5 |
| P1-8 | FIXED | — |
| P1-9 | FIXED — and independently confirmed: the live name **is** `approval_routes_entity_type_check` | — |
| new P1 | `store_document` requires `material_id` and rejects the new types | **Accepted.** Confirmed at `service.py:1072`, `:1114`. The writer is generalized in place, not duplicated — its own docstring forbids a second entry point (§4.2) |
| new P1 | 038 assumes a document belongs immutably to a material | **Accepted** — same fix as P1-2 (§4.1b) |
| P2 | §4a's measurements verified; but the idempotency inference is wrong | **Accepted** — corrected in §4a.1. Alembic's version table makes the second run a no-op regardless |
| P2 | Scope still incoherent — phase 1 built tables whose services were deferred; audit split across phases | **Accepted** — phases re-cut so each contains a whole vertical and every table gets its writer in the same phase (§10) |

---

## 12. Gates

Codex pass 2 on this revision → build → Codex on the diff → Supervisor
`/code-review` + `/security-review` → the four-gate bar (`CLAUDE.md:355`). Then
the live-test rule: full suite against the deployed site, reported as
**passed / failed / skipped**, never an exit code.
