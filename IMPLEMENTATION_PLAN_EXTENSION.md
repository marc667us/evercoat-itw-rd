# IMPLEMENTATION_PLAN_EXTENSION.md — EvercoatITWRD APP

**Extension v2, 2026-08-22 — post review.** Additive to
`IMPLEMENTATION_PLAN.md` (v3).

> **v1 → Codex: FAIL, 30 findings, 3 BLOCKERs → Supervisor: 11 further
> findings, and the two reviewers overlapped on almost nothing — the ninth
> consecutive session in which neither alone sufficed.** v2 is the result.
> Three of my own measurements were **wrong** and are corrected below, one of
> them (§2, the upload route) in a direction that makes I41 worse rather than
> smaller. Full adjudication in `docs/REVIEW_EXTENSION_ADJUDICATION.md`.

Nothing in v3 is deleted by this document. Where the two disagree, the
disagreement is named in §3 and resolved there, never silently.

**Source read for this extension:** `C:\Users\USER\Documents\ITW Evercoat 23\`
— five plain-text documents, 121 KB total, all dated 2026-08-22:

| File | Bytes | Subject |
|---|---:|---|
| `new production foundation use this.txt` | 17,810 | Oracle + Neon + Hugging Face + Cloudflare production foundation, 27 numbered sections |
| `zero cost build foundation evision 1.txt` | 35,902 | Two consecutive passes: self-hosted-first (30 §), then the "final zero-cost option" Oracle/Neon/HF (31 §) |
| `itw evercoat security.txt` | 24,409 | Defence-in-depth security architecture, 53 numbered sections |
| `revised msd and reseach.txt` | 31,093 | MSD promoted from chatbot to R&D Intelligence + Research Center, 42 § |
| `ui ux zerocost.txt` | 12,010 | Penpot → Storybook → shadcn/ui → Next.js design layer |

**Precedence applied.** The folder is dated after every source v3 was built
from, so on matters it addresses it supersedes v3 — with one exception
recorded at Y1: the folder contradicts *itself* across two passes of
`zero cost build foundation evision 1.txt`, and a later statement inside one
file does not automatically beat an earlier statement in another when the two
were plainly written as alternatives rather than as a revision.

---

## 1. What this extension actually changes

v3 built a product. These five files change four things *around* it, and add
one thing *inside* it that is large enough to be its own MVP.

| Pillar | v3 position | Extension position |
|---|---|---|
| **P1 — Production foundation** | ADR-027: *"under the current rules there is no provider on which this app's API and Keycloak can be deployed."* Dead end. | Oracle Cloud Always Free (2 OCPU / 12 GB / 200 GB block / 20 GB object) as permanent compute, Neon Free as managed PostgreSQL, Cloudflare Free as the security edge, Hugging Face Hub as a **model repository only**. **ADR-027's conclusion is superseded — see Y2 for what it costs.** |
| **P2 — Security** | `SECURITY.md`, 11 sections, application-and-database centric. | A named 9-layer defence-in-depth chain with an **edge tier that does not exist today**, an upload/malware pipeline that does not exist today, and IP-classification of formula data that does not exist today. 53 sections; §4 measures which are already met. |
| **P3 — Research Center + MSD** | MSD = Slice 7 structured tool-calls, Slice 8 document RAG. One conductor, five tool modules. | MSD becomes the conversational surface of a **Research Center**: 18 sub-areas, ~25 new tables, 10 specialist agents, hybrid retrieval (SQL + vector + metadata + knowledge graph + rerank), evidence grading, Deep Research mode, experiment proposals. The largest single addition in the folder. |
| **P4 — UI/UX** | Tailwind + shadcn/ui + Radix named in the stack table; no design system, no component workshop. | Penpot design system → Storybook → shadcn/ui → Next.js, with a named engineering-density visual language, an MSD panel specification, and a **traffic light that is never colour alone**. |

There is a fifth thing, and it is the one worth reading first:

> 🔴 **P1 is not free of owner action.** Oracle, Neon, Cloudflare and Hugging
> Face are four signups, and Oracle account creation requires card
> verification. The standing operator rule since 2026-08-21 is that **no task
> may be assigned to the operator** — no signup, no interactive login, no
> dashboard action. These files are the operator handing me a foundation that
> begins with four of them. I am reading that as the rule being *spent
> deliberately on this*, not as the rule being forgotten. It is stated here
> rather than assumed because if the reading is wrong, every slice below P1 is
> unreachable and I would rather be told now. See §8 D1.

---

## 2. What was measured in the repository today

Not quoted from the last handover. Run 2026-08-22 against tip `f337761` and a
live local PostgreSQL.

| Question | Measured answer |
|---|---|
| Local API suite | **507 passed / 0 failed / 11 skipped** (102 s) |
| Database size | **19 MB**, 59 tables, 13 schemas, seeded |
| Extensions installed | `plpgsql`, `pgcrypto`, `citext` — **all three are on Neon's allow-list** |
| Event triggers in use | **0** — so the append-only audit is trigger + `REVOKE` based, not DDL-event based. **This is the single reason the Neon move is survivable** (see Y3) |
| Database roles | All five exist: `evercoat_owner` `evercoat_app` `evercoat_worker` `evercoat_report` `evercoat_breakglass` |
| Rate limiting | **Valkey capability exists (`redis>=5.2` declared and configured); request-rate ENFORCEMENT does not.** No middleware, no dependency, no counter. Confirms I18. *(Phrased this way after Codex F19 so nobody provisions another cache instead of writing the policy.)* |
| Object storage client | **`boto3>=1.35` is DECLARED in `pyproject.toml` — commented *"S3-compatible client for Garage, behind a port"* — and is never imported anywhere in `app/`.** Garage is in `docker-compose.yml` and `config.py` (`garage_endpoint`, `garage_bucket`, keys). So: a client library, a container and four settings, with **no port, no adapter, no byte-write path, no retrieval path and no `UploadFile` anywhere in `app/api/`**. *(Corrected after Codex F17 — my first phrasing said "no client", which is false and makes the gap sound smaller than it is: the dependency has sat unused since Slice 1.)* |
| Upload route | 🔴 **CORRECTED — one EXISTS, and I said it did not.** `POST /api/materials/{material_id}/documents` → `register_document` (`app/api/materials.py:357`), gated on `material.edit` **or** `supplier.manage`. Its own docstring calls it *"THE ROUTE WITHOUT WHICH NO FORMULA COULD EVER BE SUBMITTED"* — it was added precisely because the SDS gate had no writer. **It registers metadata; it accepts no bytes.** *(Raised by the Supervisor. This correction makes I41 worse: the defect is reachable by a real authenticated user, not theoretical.)* |
| Upload security | **None.** No ClamAV, no quarantine, no MIME-magic validation, no filename sanitisation, no byte transfer of any kind |
| Storybook | **Absent.** Not in `apps/web/package.json`, no `.storybook/` |
| Research Center | **Absent.** Migrations stop at `031`; no research schema, no `documents` domain |
| Web screens | **15** page routes. Research Center needs ~18 more |
| MSD today | 1 conductor, 5 tool modules (`guidance` `records` `safety` `formulation` `work`), 4 routes |

### 🔴 The measurement that is a defect, not a gap

`materials.material_documents` **exists** (migration 015) with `storage_key`,
`content_type`, `byte_size`, `checksum_sha256`. A route writes the **row** —
`POST /api/materials/{id}/documents`, permission-gated, shipped deliberately
because the SDS gate previously had no writer at all. **Nothing writes the
bytes**, because `boto3` is declared and never imported and no adapter exists.

And `formulations/service.py:1265` and `msd_conductor.py:517` both gate on
`requires_sds AND sds_count == 0`. **They count rows.**

So a `material_documents` row with a `storage_key` pointing at nothing
satisfies the SDS safety control — the control the golden scenario exists to
demonstrate — while no SDS was ever stored, scanned, or read by anybody. The
row *is* the safety evidence.

🔴 **And it is reachable, not theoretical.** Any user holding `material.edit`
can register `storage_key = "sds/anything.pdf"` and unblock submission of a
formula whose SDS does not exist. The previous question was *"which production
path writes it?"*; the question this raises is one level further in — **"which
production path writes the thing the row is a POINTER to?"** Nothing does.

⚠️ **`scripts/seed.py:412` and `test_golden_scenario.py:236` both insert
exactly such rows**, and the seed carries a comment saying it does so to avoid
reproducing the submission deadlock. So the demonstration data and the
acceptance scenario both **canonise the broken evidence model**. E3 cannot
simply tighten the gate — see E3's revised gate. Raised as **I41**.

---

## 3. Reconciliation register — Y-class

v3's contradiction register uses X1–X15 and its finding register uses F/S
numbers. This extension uses **Y** so nothing collides.

### Y1 — 🔴 The source folder contradicts itself about where production runs

`zero cost build foundation evision 1.txt` contains **two consecutive passes**
and they do not agree.

- Pass 1 (§1–§30): *"The only architecture you control indefinitely is
  open-source software + hardware you control."* Preference order stated
  explicitly: **own hardware first, Oracle Always Free second.** PostgreSQL
  self-hosted. Garage self-hosted. Temporal OSS self-hosted.
- Pass 2 (§1–§31, introduced as *"below is the final zercost options to
  use"*): Oracle Always Free as the foundation, **Neon Free as the primary
  database**, Hugging Face for models, explicitly *"Do Not Put PostgreSQL on
  Oracle Initially."*

`new production foundation use this.txt` agrees with pass 2 and is the file
the operator named *"use this"*.

**Resolution: pass 2 / Oracle + Neon, with pass 1 retained as the fallback it
is written to be.** The two are only compatible because pass 2 itself demands
the fallback: §22 *"If Neon limit reached → do not pay → restore database on
Oracle → change `DATABASE_URL`"*. So pass 1 is not superseded, it is the
**documented exit**, and the exit must be **tested, not asserted** — a restore
drill is already Slice 1's requirement in v3 (F43) and now has a second
purpose. **E1 gate: a Neon→Oracle restore is exercised before Neon holds
anything that matters.**

### Y2 — ADR-027 is superseded, and this is what it costs

ADR-027 concluded no provider could host this app at zero cost under the
no-owner-action rule. The extension does not refute the measurement; it
**changes the rule's application** (§1, D1). Recorded as **ADR-028**, with
ADR-027's measurements left intact — Render is still refused, Railway still
has no free tier, and neither becomes viable again.

⚠️ **`RESUME_HERE.md` and `TODO.md` I13 both currently state that no
deployment path exists.** They become wrong the moment ADR-028 is accepted and
must be corrected in the same commit, not later. Two copies of a fact in two
files disagreeing is this repository's most repeated defect.

### Y3 — Neon is not PostgreSQL-with-a-URL, and the security model is what tests it

Pass 2 says the application *"should never contain Neon-specific business
logic"* and *"knows only `DATABASE_URL`"*. For business logic that is true.
**For this application's security model it is not obviously true**, and the
plan must not proceed as though it were.

v3's `SECURITY.md` requires, on the database:

1. Five distinct roles (`CREATE ROLE`)
2. `ALTER TABLE … FORCE ROW LEVEL SECURITY` across every tenant-scoped table
3. `UPDATE`/`DELETE` revoked from runtime roles on audit tables
4. Append-only audit enforced by **triggers**
5. `SET LOCAL` transaction-scoped tenant GUCs over a **pooled** connection

Neon provides `neon_superuser`, which is **not** a PostgreSQL superuser.
Items 1–4 are believed to work under `neon_superuser`; item 5 interacts with
Neon's own pooler.

🔴 **None of that is verified, and it must not be assumed.** The single most
expensive possible outcome of this extension is discovering at deploy time
that FORCE RLS or `SET LOCAL` behaves differently through Neon's pooler —
because that is the layer v3 named *"highest risk in the project"*.

**E1's first task is a falsifiable measurement**, not a migration: a throwaway
Neon project, `alembic upgrade head`, then run `tests/db/` **against Neon**
and report passed/failed/skipped. If it is not green, Neon is refused and pass
1 (PostgreSQL on Oracle) is taken — which costs 1–2 GB of the 12 GB budget and
nothing else. **The measurement is cheap; the assumption is not.**

The one thing already known to be in our favour is measured above: **0 event
triggers**. The audit design uses ordinary triggers and `REVOKE`, both of
which `neon_superuser` can create. Had it used DDL event triggers, Neon would
already be refused.

### Y4 — 0.5 GB, with numbers

Neon Free is **0.5 GB storage per project**; pass 2 sets an operational target
of **< 350 MB**. Measured today: **19 MB** — but with no documents, no
embeddings, and a demo-sized audit trail.

The three things that grow without bound are named, because a storage ceiling
that nobody budgeted is a ceiling that gets hit at the worst moment:

| Consumer | Policy |
|---|---|
| **Documents** (SDS/TDS/CoA/patents/reports/images) | **Never in PostgreSQL.** Oracle Object Storage, 20 GB. Already the design — `material_documents` stores a `storage_key`, not bytes |
| **Embeddings** | 384-dim `float32` ≈ 1.5 KB + index overhead ≈ **~2 KB per chunk**. A 150 MB vector budget ≈ **~75,000 chunks** ≈ roughly 1,500–3,000 technical PDFs at typical chunking. Adequate for MVP; **not** adequate for "embed everything". Pass 2 §14 says so directly: *"Do not create embeddings for repetitive boilerplate."* Enforced as a rule, with a chunk-count metric on the admin dashboard |
| **Audit** | Append-only with before/after row state is the fastest-growing table in a system like this. **Budget it explicitly and measure it in E1**, or it silently eats the vector budget |

**A storage budget with no monitor is a wish.** E2 ships the monitor.

### Y5 — 🔴 The Hugging Face Space execution path is a confidentiality leak, and the folder says so itself

`zero cost build foundation evision 1.txt` pass 2 §10 proposes an **AI Model
Router** whose *preferred* path is a **Hugging Face free CPU Space**, falling
back to Oracle-local inference when the Space sleeps.

`revised msd and reseach.txt` §35 says, of the same system:

> *"When MSD searches the internet, never send: complete proprietary formulas,
> exact proprietary ratios, confidential test data, internal project names,
> customer-confidential information to external search/model services."*

and `itw evercoat security.txt` §39:

> *"Do not allow the model to receive formula records from projects the user
> cannot access."*

**A Hugging Face Space is an external model service.** Every MSD answer worth
having carries an evidence pack of internal formulas, test results and project
names — that is the entire design. Routing that to a free public Space sends
ITW Evercoat's most valuable IP to a third party, and it does so *by default*,
because §10 makes HF the **preferred** path.

**Resolution — and this one is not a preference:**

- **Hugging Face is a model repository. Full stop.** Download open weights to
  Oracle block storage; run inference locally on Oracle. This is what
  `new production foundation use this.txt` §7 independently concludes:
  *"Hugging Face should not be your production compute foundation."*
- The AI Model Router **is still built**, because a router with one
  registered runtime today is how a second one gets added safely later. It
  ships with exactly one runtime (Oracle-local) and a **hard policy gate**.

  🔴 **REVISED after Codex review, and the correction matters.** My first
  threshold was *"nothing above `INTERNAL`"*. **That was wrong, and it
  leaked.** The source forbids sending **internal project names** and
  **confidential test data** externally (`revised msd §35`) — and both of
  those *are* `INTERNAL`. A threshold that permits `INTERNAL` permits exactly
  what the sentence prohibits.

  The gate is therefore: an external runtime receives **`PUBLIC` only**, plus
  an independently allow-listed **sanitised query object** — a typed outbound
  structure assembled from permitted fields, never an internal prompt with
  redactions applied. **A missing or unknown classification is DENY.**
  Construction, not redaction: redaction is a blocklist, and a blocklist
  cannot enumerate every way a ratio, alias, trade name, filename, citation or
  free-text fragment carries the same fact.
- If an external runtime is ever wanted, it is a **separate ADR** with the
  sanitisation boundary of §35 built and tested first.

Recorded as **ADR-029**. Raised as **I42** (build the classification gate
before any router exists to bypass it).

### Y6 — 🔴 Rate limiting: I18 is NOT unblocked, and my first answer was wrong

**v1 claimed I18's blocker was answered.** It is not, and the reason is worth
recording because it is a good example of a fix that reads correct and cannot
work.

I18 has been blocked on one question that was never a code question: **what
does the limiter key on?** Behind a proxy, `request.client.host` is the proxy
for every caller (one bucket for the whole internet, fails closed on the first
burst); trusting `X-Forwarded-For` lets an attacker mint unlimited keys.

v1's answer was: put Cloudflare in front, then key on `CF-Connecting-IP`,
accepted **only from Cloudflare's published IP ranges**.

🔴 **That rule can never match in the topology v1 itself specified.** The chain
is `Cloudflare → Cloudflare Tunnel → Caddy → FastAPI`. With `cloudflared`, the
origin never sees a Cloudflare **edge** address at all — the connection is
opened outbound by the local tunnel daemon, so the peer address is loopback or
the container network. An IP allow-list against Cloudflare's ranges matches
**nothing**, and "exactly one trusted hop" was also wrong: Caddy is a second
hop, which is why `apps/api/tests/test_reverse_proxy_contract.py` already
exists. The limiter would have shipped keyed on a header with a guard that is
inert — **which is precisely I18's own finding, that a limiter keyed wrongly is
worse than none.** *(Raised by the Supervisor.)*

**Revised resolution — the question narrows, it does not disappear.** The
trust decision moves from *"is the peer a Cloudflare IP"* to *"is this request
provably ours":*

1. **Cloudflare Tunnel is the only ingress**, and the origin has no public
   application port at all (Y13's default-deny). Then the peer address proves
   nothing and is not asked to.
2. **Caddy is the single header authority.** It strips every inbound
   `X-Forwarded-*` and `CF-*` header and re-sets exactly one client-identity
   header from Cloudflare's own, so FastAPI trusts a header **Caddy** wrote,
   not one the internet wrote. `test_reverse_proxy_contract.py` is the file
   that must assert this.
3. **Prefer identity over address wherever there is one.** Authenticated
   limits key on the subject claim, which cannot be forged past token
   verification and is what §20's per-user quotas (MSD 20/min, search 60/min,
   upload 10/min) are actually stated in. **Only anonymous endpoints need an
   address at all** — and this API has almost none.
4. **Cloudflare's own edge rate limit** stays as the outer layer, where the
   real client address genuinely is known.

So I18 moves into E4 **with a decided design**, but it is decided differently
from v1 and the difference is not cosmetic. Raised as **I51**.

### Y7 — Object storage: the port survives, the adapter changes

v3 X4 chose **Garage behind `ObjectStoragePort`** and moved it into Slice 1.
The extension names **Oracle Object Storage** (20 GB Always Free).

No conflict, because both speak S3. **Resolution: the port is the decision;
Garage and Oracle OS are two adapters.** Garage stays as the local-compose and
self-hosted-fallback adapter (Y1's exit needs it); Oracle OS is the production
adapter.

🔴 **But §2 measured that neither exists.** `ObjectStoragePort` was specified
in v3 and never written; Garage runs in compose serving nobody. So this is not
"swap an adapter" — **it is building the port for the first time**, with two
adapters, against a table (`material_documents`) that already promises files
it cannot store. E3.

### Y8 — Temporal moves further out, and the extension agrees with v3's reasoning

v3 X10 assigned four named durable workflows to Temporal from Slice 11.
`new production foundation use this.txt` §15 and pass 2 §28 both say: **do not
run a Temporal server on a 12 GB box** — use PostgreSQL workflow tables + a
Python worker + APScheduler, and *"design the workflow abstraction so Temporal
can be inserted later without changing the business modules."*

**Resolution: v3's ownership boundary is unchanged; the runtime is deferred.**
The four workflows stay named and stay Temporal-owned *in design*; the
implementation is the DB state machine until the RAM budget permits otherwise.
v3 already recorded that the cutover is a **migration, not an adapter swap**
(F13/F41) — that finding is unaffected and still true.

### Y9 — Penpot is a design tool and must not become a runtime tenant

`ui ux zerocost.txt` offers Penpot self-hosted *or* its free hosted
Professional plan.

Self-hosted Penpot is a full stack of its own (frontend, backend, exporter,
its own PostgreSQL and Redis) and would take **~2 GB** from a 12 GB budget
that pass 2 §29 has already spent down to ~9–10 GB with 3–4 GB of it reserved
for the local LLM.

**Resolution: Penpot never runs on the production host.** Use the free hosted
plan, or run it locally on demand. The file's own framing supports this —
*"a development/design tool rather than a production runtime dependency"* and
*"the production application still runs if Penpot disappears entirely."*

What ships into the repository is **not Penpot** — it is the artefact Penpot
produces: **design tokens**, checked in, with Storybook as the executable
contract. That is the part that survives the tool.

### Y10 — Role vocabulary drift

`itw evercoat security.txt` §11 lists eight primary roles including
**Material Specialist**. v3 seeds ten Keycloak roles including
`procurement_specialist`, `production_engineer`, `executive_viewer`, and no
`material_specialist`.

**Resolution: v3's ten stand.** The security file's list is prose framing, not
a realm specification, and v3's set is a superset in intent
(`procurement_specialist` covers the material-sourcing capability).
**No realm churn.**

⚠️ But the file's §31 *is* a real requirement and is **not** satisfied by role
names: *"The Director should not automatically receive edit access merely
because the Director has high organizational rank"*, and **view / edit /
approve / release / export must be separate permissions.** That is v3's own §6
rule (a role is not an authorization) and it needs `formula.export` to exist.
Raised as **I43**.

---

### Y11 — 🔴 There are TWO classification taxonomies and they are not the same

**Missed in v1 of this extension; raised by Codex.** The folder defines data
classification twice, in two files, with two vocabularies:

| Source | Levels |
|---|---|
| `itw evercoat security.txt` §31 | `PUBLIC` · `INTERNAL` · `CONFIDENTIAL` · `R&D RESTRICTED` · **`MASTER FORMULA`** |
| `revised msd and reseach.txt` §34 | `INTERNAL` · `CONFIDENTIAL` · `R&D RESTRICTED` · **`FORMULA RESTRICTED`** · **`DIRECTOR CONTROLLED`** |

They are **not interchangeable**. One has `PUBLIC` and the other does not —
which matters enormously, because Y5's outbound gate is *defined* in terms of
`PUBLIC`. One ends at `MASTER FORMULA`, the other at `DIRECTOR CONTROLLED`,
and nothing states whether those are one level under two names.

**Resolution — one canonical lattice, totally ordered, deny-by-default:**

```
PUBLIC < INTERNAL < CONFIDENTIAL < R&D_RESTRICTED < FORMULA_RESTRICTED < DIRECTOR_CONTROLLED
```

- `MASTER FORMULA` maps to **`FORMULA_RESTRICTED`** — §31 describes it as the
  released master recipe, which is what the research file's
  `FORMULA_RESTRICTED` names.
- `DIRECTOR_CONTROLLED` is the ceiling and has no counterpart in the security
  file. It is additive, not conflicting.
- **`PUBLIC` exists**, and is the *only* level Y5's outbound gate accepts.
- **Classification is not an access group and not a permission.** It is a
  property of the DATA. *Who* may see a level is a separate question answered
  by permissions and project membership. Collapsing the two is the §6 defect
  this project has already found six times — a role standing in for an
  authorization.
- **An unset classification is `DIRECTOR_CONTROLLED`, not `INTERNAL`.** Fail
  closed. A NULL defaulting to the middle of a lattice is a disclosure waiting
  for the first row somebody forgets to label.

Raised as **I48**.

### Y12 — 🔴 Retention and deletion are absent from the entire extension

**Missed in v1; raised by Codex.** `revised msd §34` requires every research
object to carry a **retention policy**. The extension creates research notes,
findings, evidence, documents, embeddings, caches, graph edges and externally
ingested material — and specifies **no retention, no legal hold, no deletion
propagation, no purge**.

This is not a tidiness gap. It is dangerous precisely *because* of two
decisions already taken:

- the audit trail is **append-only** by design, and
- embeddings, caches and graph edges are **derived** copies of source content.

So "delete the document" does not delete the content. It survives in the
vector index, the rerank cache, the conversation memory, the knowledge-graph
edges and the object store's earlier versions. v3 already committed to
*"derived artifacts are purged when access is revoked"* (F33) — **that promise
has no implementation and no owning slice.**

**Resolution: retention is acceptance criteria on E6 and E7, not a later
slice.** Retrofitting deletion onto a populated vector index is the same shape
of rework as retrofitting authorization onto one. Each research table declares
a retention class; deletion and reclassification **propagate** to embeddings,
caches, graph edges and object versions; audit is preserved deliberately and
separately; and the gate is that deleted or reclassified content is **no
longer retrievable by any route**, proved the way E7's boundary is proved.

Raised as **I49**.

### Y13 — The backup destination is unnamed, and that is most of the control

**Raised by Codex.** E2 said *"`restic` encrypted backups"*. `itw evercoat
security.txt` §46 says a backup holding every formula *"can be more valuable to
an attacker than the live application"* and requires it stored **separately**.

A restic repository on the same Oracle tenancy, reachable with the same
credentials, is not a backup against the two failure modes that actually
threaten this application: **account compromise**, and **Oracle reclaiming
Always Free capacity** — which pass 2 §24 explicitly warns can happen.

**Resolution: name the destination, the credential boundary and the key
custody, or the control does not exist.** Credentials distinct from the
production host, an encryption key not stored on it, and a **failure-domain
test**: restore with the Oracle tenancy treated as unavailable. The zero-cost
candidate is owned disks — which is pass 1's own recommendation of at least
two physical copies — not a second paid tier. Raised as **I50**.

### Y14 — Navigation ownership is assigned to no slice

**Raised by Codex.** `ui ux zerocost.txt` requires MSD **permanently in the
global header**; `revised msd §40` defines an 11-item Research Center submenu.
The extension named components and a visual language, and assigned the
**navigation structure itself** to nothing.

**Resolution: the shell belongs to E5, the Research Center submenu to E6** —
each with keyboard operation, responsive collapse, permission-based
visibility, deep links and preserved project context. A submenu rendered for a
user who cannot use it is the §6 defect again, in the navigation.

### Y15 — "Temporal owns it in design" is not a durability contract

**Raised by Codex.** Y8 deferred the Temporal runtime and said the four named
workflows stay Temporal-owned *in design*. That is not implementable: an
engineer can satisfy "PostgreSQL workflow tables plus a worker" with
APScheduler, Celery, or a polling loop, and those differ in retries,
idempotency, leases, cancellation and recovery.

**Resolution: `WorkflowPort` specifies the durability contract before document
ingestion, embedding generation, alerts or Deep Research depend on it** — at
minimum at-least-once execution, idempotency keys, visible retry state, lease
ownership, cancellation, and recovery after worker death. That specification
is a **prerequisite of E7**, because ingestion is the first long-running job
whose partial failure is invisible.

---

### Y16 — 🔴 Two different Oracle capacities, and the number is load-bearing

**Raised by the Supervisor.** The source folder says Oracle Always Free gives
**2 OCPU / 12 GB**. Three documents already in this repository — `DECISIONS.md`
(ADR-027), `RESUME_HERE.md` and `TODO.md` I13 — record **4 ARM cores / 24 GB**
from the measurement taken on 2026-08-21.

v1 took 12 GB from the source and never noticed the repo said otherwise. That
is the *"two copies of a fact in two files disagreeing"* defect this document
names twice in its own text, committed inside the document that names it.

**And the number decides two conclusions:**

- **Y9** excluded self-hosted Penpot because ~2 GB will not fit.
- **R2** concluded *"12 GB is genuinely tight"* and that if Neon is refused,
  PostgreSQL's 1–2 GB must come out of the local LLM.

**At 24 GB both conclusions change.**

**Resolution: neither number is adopted until E1 measures it, and the plan is
written so that either is survivable.** The reconciling fact is that Oracle's
A1 Always Free *allowance* is 4 OCPU / 24 GB **for the tenancy**, divisible
across up to four instances — so "2 OCPU / 12 GB" is a plausible description
of one conservatively-sized VM, and "4 cores / 24 GB" of the whole allowance.
They may not be in conflict at all. **But that is a reading, not a
measurement**, and the RAM budget is not a place to guess.

**E1 reports the actual shape provisioned**, and the RAM budget in R2 is
recomputed from it before E2 places anything on the host. Until then this plan
**assumes 12 GB** — the pessimistic figure — because a plan that fits the
small box also fits the large one. Raised as **I52**.

⚠️ E1 must also carry the two caveats ADR-027 measured and v1 dropped:
**Oracle ARM capacity is frequently unavailable by region**, and the API image
**needs an ARM or multi-architecture build**. An `amd64`-only image fails at
E2, after E1 was signed off green. Raised as **I53**.

---

## 4. Security: what the 53 sections ask for, against what is built

Not a restatement. Only the delta, measured.

### Already satisfied by v3 (no work)

§16 explicit authorization chain · §17 IDOR/BOLA resource-level checks · §18
Pydantic validation · §19 parameterized SQL · §26 separate DB users · §30
SOPS+age · §33 audit trail (**event capture only** — see the gap table) · §37
tool allowlist (5 tool modules, no generic SQL tool) · §38 MSD proposes,
humans act · §41 Semgrep/Gitleaks/Trivy in CI.

🔴 **Two entries were removed from this list after review, because v1 listed
each as satisfied here and as an open gap nine lines later.** A reader scanning
a "no work" list skips exactly the item the rest of the document calls
critical:

- **§27 RLS is NOT satisfied.** Policies exist, but `core.rls_permissive()` is
  `SELECT TRUE` (`migrations/001_core_tenancy.sql:184`), so every policy opens
  when the GUC is absent. RLS is not an independent barrier today. **I19.**
- **§35 is HALF satisfied.** *"MSD never exceeds the caller"* holds. The other
  half of §35 — **outbound sanitisation**, never sending proprietary data to an
  external service — is an **unbuilt security control**, and Y5 and §5 R-C both
  depend on it. Ticking §35 whole would close it by checklist.

### Partially satisfied — named gaps

| § | Requirement | Gap |
|---|---|---|
| §27 | RLS as an independent barrier | 🔴 **`core.rls_permissive()` is still `SELECT TRUE`** — every policy opens when no GUC is set, so today the application layer is the *sole* enforcement. This is **I19** and the extension does not change it; it raises its priority, because §1's *"if one control fails, the next layer still blocks"* is **false while I19 is open** |
| §39 | Permission filtering **before** vector retrieval | No retrieval exists yet. Must be built filter-first from line one — retrofitting authorization onto a populated index means re-embedding everything |
| §33 | Audit records IP and session | Audit exists; IP and session are not captured. Cheap now, unrecoverable retrospectively |

### Absent entirely — new work

| § | Requirement | Slice |
|---|---|---|
| §2–§7, §49 | Cloudflare edge: DNSSEC, proxied records, WAF managed ruleset, Bot Fight Mode, Turnstile on login/reset, edge rate limit, Tunnel | E4 |
| §7, §20 | FastAPI rate limiting, Valkey-backed, per-role and per-operation (MSD 20/min/user, search 60/min, upload 10/min, login 5/min/IP) | E4 (**I18**) |
| §8 | Nonce-based CSP, HSTS, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, `frame-ancestors` | E4 |
| §9, §10 | Tokens out of `localStorage`; CSRF on cookie-session state changes | E4 — ⚠️ **ADR-025 chose browser PKCE with a static export.** Moving tokens out of browser storage is an architecture change, not a config change. **Decide it (D3), do not drift into it** |
| §14 | MFA required for Director / Lead / QA / Administrator | E4 |
| §21–§23, §51 | Upload pipeline: size → extension → **MIME magic** → filename→UUID → **ClamAV** → quarantine → approved → parse | E3 (**I41**) |
| §31, §32 | Formula IP classification (`PUBLIC` `INTERNAL` `CONFIDENTIAL` `R&D RESTRICTED` `MASTER FORMULA`), separate view/edit/approve/release/**export**, every export logged, second approval for full-formula export | E3 (**I43**) |
| §34, §47, §48 | Behavioural anomaly detection (mass downloads, ID enumeration, cross-project MSD probing) → `SECURITY_WARNING/HIGH/CRITICAL` → Admin Security Dashboard | E9 |
| §36 | Prompt-injection defence: retrieved document text is **data, never instructions**; a document may never redefine MSD's tools or permissions | E7 |
| §40, §43–§46 | Container hardening (non-root, read-only fs, dropped caps, limits), `ufw`, SSH keys only, `fail2ban`, encrypted `restic` backups with a **tested** restore | E2 |

---

## 5. Research Center + MSD — the largest addition, staged honestly

`revised msd and reseach.txt` is ~25 tables, 18 screens, 10 agents and a
knowledge graph. v3's whole MVP-1 was estimated at 700–1,050 engineering hours.

🔴 **v1 put this at 250–400 hours. Codex refuted that and is right.** The
addition has **nearly half the table count of the entire existing database**,
**more new screens than the existing UI has**, two new trust boundaries,
document ingestion, vector retrieval, a knowledge graph, ten agents, patent and
literature workflows, and new authorization semantics. It is comparable to
MVP-1, not one third of it — and 250–400 also omitted deployment validation,
data migration, evaluation datasets, retrieval-quality work, operational
tooling and security testing.

**Revised planning range: 800–1,400 hours**, estimated per tranche rather than
in one number, and treated as a range to be replaced by measurement — spikes on
ingestion, retrieval quality, authorization and graph maintenance — not as a
commitment. Understating this would have repeated precisely the fidelity
failure v3's §K recorded and corrected, one document later.

It is therefore staged in three tranches, each independently useful and
independently shippable. **The ordering is not negotiable, and the reason is
the file's own §4:** *internal knowledge first*. A Research Center that
reaches the internet before it can search its own test history is a liability,
not a feature.

### R-A — Research Center over data that already exists (E6)

No new retrieval technology. No internet. Everything below already sits in
PostgreSQL and is unreachable today because nothing aggregates it.

- `research_projects`, `research_questions`, `research_notes`,
  `research_findings`, `research_evidence`, `research_hypotheses`,
  `experiment_proposals`
- **Research Finding register** (§9) — the object MSD prioritises forever
  after. Evidence links to real `formula_versions` / `tests` / `failures` /
  `doe_studies` rows, so a finding cannot cite something that does not exist
- **Research Notebook** (§8) — timestamped, attributable, promotable to a
  Finding after review
- **Materials Intelligence** (§13) — the material page becomes a knowledge
  page: usage history, formula occurrences, successful vs failed formulas,
  test correlations, substitutes. Every input is an existing table
- **Test Intelligence** (§17) + **Failure Knowledge Base** (§18) — *"show all
  adhesion failures involving this resin family"*. Institutional memory out of
  records already written
- **Evidence grading A/B/C/D/X** (§6) and the **confidence system** (§29),
  derived from evidence count and grade — **never from model probability**.
  🔴 And never green: §29 reserves GREEN for validated technical results,
  which is v3's rule 6 restated. An AI recommendation that renders green is a
  defect

**Gate:** a Chemist answers a real cross-project question, from real seeded
records, with every claim carrying a clickable source — **with no LLM running
at all.** That gate is deliberate: `zero cost build foundation evision 1.txt`
pass 2 §11 requires MSD's core to work without a generative model, and a gate
that needs the LLM cannot prove it.

### R-B — Retrieval and the knowledge graph (E7)

- pgvector, Docling/PyMuPDF ingestion, Sentence Transformers, local reranker
- `knowledge_entities` / `knowledge_relationships` / `knowledge_gaps` (§24)
- **Hybrid retrieval** (§25): SQL + vector + metadata filter + graph → rerank
  → evidence pack
- 🔴 **Authorization filters before retrieval, always** (§39, v3 F33).
  Authorization provenance carried on every chunk, embedding and cache entry;
  re-checked at retrieval *and* at source-open; purged on revocation
- `tests/e2e/rbac/msd_boundary.spec.ts` — **required, and still unwritten**
- Prompt-injection boundary (§36): system policy / tools / user request /
  retrieved untrusted content are four separate channels

**Gate:** a user with no access to project P cannot obtain P's content through
MSD by any route — direct question, similarity, summary, or citation —
**proved by falsification**, with the guard removed and the test failing.

### R-C — External research gateway (E10, after MVP-1)

Patents, literature, standards, supplier and competitor intelligence, the
controlled ingestion pipeline (§5), Deep Research mode (§26/§27), Research
Inbox (§32), Research Analytics (§31).

🔴 **Blocked until the E3 upload pipeline and the Y5 classification gate both
exist**, because this is the first feature that moves bytes *and questions*
across the trust boundary in both directions. §35's sanitisation — turning
*"why did F107 with 23.75% RM-X fail?"* into *"factors affecting adhesion in
polyester body filler systems"* — is a **security control**, and one that
fails silently and invisibly if it is wrong.

⚠️ **Patent analysis must render as technical research assistance and never as
freedom-to-operate advice** (§10). That is a legal-exposure statement and it
belongs in the UI, not in a comment.

---

## 6. UI/UX — what ships into the repository

Penpot itself does not (Y9). These do:

- **`packages/design-tokens/`** — colour, spacing, type scale, elevation,
  status semantics, exported to CSS variables + a Tailwind preset. **One
  source. Two literals in two files disagreeing is this repository's most
  repeated defect, and a design system is the easiest place in the world to
  create one**
- **Storybook** in `apps/web`, with the stories the file names:
  `FormulaTable` `TestStatusCard` `ApprovalTimeline` `FailureCard`
  `ProjectHealth` `MSDChatPanel` `MaterialCard` `PipelineStage`
- **axe-core runs inside Storybook**, per story. v3 already learned that
  `opacity-80` silently rescales contrast, and that axe reported zero
  violations over a **1.48:1** sidebar because `aria-disabled` silences its
  own contrast rule. Component-level a11y catches what a page sweep cannot
- 🔴 **The traffic light is never colour alone** — `✓ PASS` / `✕ FAIL` /
  `! REVIEW REQUIRED`, icon **and** text, in every rendering including print.
  v3 already requires the automatic evaluation and the final disposition to be
  **two separately displayed fields**; this makes each legible without colour
- **MSD response provenance is visual and mandatory** — Verified data /
  Calculated result / Prediction / AI recommendation / Warning are five
  distinct visual treatments. §29: *"never use green PASS for an AI
  recommendation."* A user who mistakes a recommendation for an approved test
  conclusion is the single worst outcome this UI can produce
- **Visual language:** neutral workspace, high information density, large
  technical tables, persistent project context, sticky action bars, right
  drawers, **limited animation**. An engineering instrument, not a consumer app
- **Excalidraw** for `docs/architecture/*.excalidraw` — checked in, editable,
  no runtime dependency

---

## 7. Extension slices

Numbered **E1–E12** so nothing collides with v3's 1–20. Each has a gate that
can fail.

> 🔴 **Every gate below was rewritten after review.** Codex found that
> **eleven of twelve gates could pass against broken work** — E1's could pass
> on nothing but skips, and could not fail at all because both outcomes were
> declared success. That is this project's most-repeated defect (a gate that
> cannot fail, shipped three times, twice in one day) found in the document
> that names it. The rule applied throughout: **a gate states an expected
> result and a way to be wrong.**

| # | Slice | Depends on | Gate |
|---|---|---|---|
| **E1a** | **Neon feasibility, measured** — throwaway Neon project, `alembic upgrade head`, run `tests/db/` against **both** the direct and the pooled endpoint | D1 | 🔴 **`failed == 0` AND `skipped == 0` AND `passed == the expected manifest count`.** `tests/db/conftest.py` calls `pytest.skip()` on *any* connection error, so a wrong URL, a dead pooler or an unusable role yields "0 failed" and a pile of skips — v1's gate accepted that as success. Plus a preflight asserting: server is Neon, `current_user` is each intended login, all five role memberships exist, `rolbypassrls` and `rolsuper` are false on every app login, objects are owned by `evercoat_owner`. Plus lifecycle: forced idle suspend/wake, killed backend mid-transaction, pool saturation, and **tenant context re-established after reconnect** |
| **E1b** | **Oracle host provisioned** — A1 shape, **architecture recorded**, capacity measured | D1, D2 | The actual OCPU/RAM shape is **reported as numbers** (Y16) and R2's budget recomputed from it. An **ARM/multi-arch image builds and runs** (I53). Region capacity obtained, or the refusal recorded |
| **E1c** | **The exit is proven** — Neon→Oracle `pg_dump`/restore | E1a, E1b | Full `tests/db/` green against the restored Oracle database, `failed == 0`, `skipped == 0`. 🔴 **E1a red does NOT auto-pass as "architectural refusal".** A refusal counts only when *diagnosed*: a connection or config error is a defect to fix, not a verdict |
| **E2** | **Production host hardening** — Ubuntu, Compose, Caddy, `ufw` **default-deny**, SSH keys, `fail2ban`, non-root/read-only containers, `restic` to a **named, separately-credentialed destination** (Y13), Uptime Kuma, quota monitor (Y4) | E1 | 🔴 **No public application port is reachable** — measured against the origin address, not read from a config. Restore succeeds **with the Oracle tenancy treated as unavailable**. The quota monitor is compared against provider/database queries within a tolerance, a threshold crossing is **injected**, and it **fails closed** on a stale reading |
| **E3** | **`ObjectStoragePort` + document lifecycle** — port, Garage + Oracle OS adapters, byte upload, MIME magic, UUID names, **ClamAV**, quarantine→approved; **replaces** `register_document`'s contract rather than sitting beside it; classification lattice (Y11); `formula.export` + export audit + **export-volume detection**; **upload rate limit** | E2 | 🔴 **The SDS gate accepts only an approved, retrievable, checksum-matching, current, unexpired SDS object** — and a **dangling row FAILS**, proved by falsification. ⚠️ **And a backfill/grandfathering path ships with it**: `seed.py:412` and `test_golden_scenario.py:236` both insert dangling rows today, so tightening the gate alone makes every seeded formula permanently unsubmittable — the exact deadlock `service.py:1071` records. The seed must upload real bytes |
| **E4** | **Edge + API limits** — Cloudflare DNSSEC/proxy/WAF/Bot Fight/Turnstile/Tunnel; **Caddy as sole header authority** (Y6); Valkey rate limiting keyed on **subject** where authenticated; CSP + headers; MFA for four roles | E2, D3 | **I18 closed.** An inbound forged `CF-*`/`X-Forwarded-*` header is **stripped by Caddy** and cannot influence a bucket — asserted in `test_reverse_proxy_contract.py`. Direct-to-origin refused, measured. Turnstile and MFA exercised by a real sign-in |
| **E5** | **Design system + Storybook + the shell** — `packages/design-tokens` (**built**), 8 named stories, axe per story, traffic-light and MSD-provenance components, **global nav + persistent MSD header** (Y14) | — | Contrast **computed on rendered colour**, not inferred from axe — `verify_contrast.py` runs in CI and is **proved by falsification** (already done: 31 checks, 3 falsifications). Plus keyboard/focus order, **print snapshots**, a lint refusing raw hex in components, and an assertion that **every status rendering carries icon + text** |
| **E6** | **Research Center R-A** — 7 tables, Findings register, Notebook, Materials/Test/Failure Intelligence, evidence grading, confidence, retention classes (Y12), Research submenu | v3 Slices 5–7, **I19 closed** | 🔴 **I19 is now a hard prerequisite.** E6 is the highest-value cross-project aggregation surface in the product, and shipping it while `rls_permissive()` is `SELECT TRUE` leaves the application layer as the sole tenant barrier. Gate: a **fixed seeded question** with expected facts, **forbidden facts**, minimum recall and exact source ids; answered **with no LLM**; plus FORCE-RLS and project-membership tests on every new table; plus a mutation removing the provenance join, which must fail it |
| **E7** | **Research Center R-B** — pgvector, ingestion, embeddings, reranker, knowledge graph, hybrid retrieval, prompt-injection boundary, **deletion propagation** (Y12), **`WorkflowPort` durability contract** (Y15) | E3, E6 | 🔴 **A route matrix, not one spec file.** Every retrieval channel — SQL, vector, graph, metadata, cache, citation, source-open, reranker input, logs, generated summary — under membership revocation, reclassification and cross-org id collision. Each row **names the guard removed** to prove it fails. Plus: deleted content is unretrievable **by every one of those routes** |
| **E8** | **MSD multi-agent** — specialist agents under the existing §0.2 topology; AI Model Router, one runtime, Y5 gate | E7 | 🔴 **Force selection of a mock external adapter** and assert at the **transport boundary** that nothing above `PUBLIC` reaches the request body, headers, logs, traces, retry queue or fallback prompt. A router that simply never calls the external path makes "cannot receive" vacuously true |
| **E9** | **Admin Security Dashboard** — anomaly detection, `SECURITY_*` events | **E3**, E4 | 🔴 **Depends on E3**, because "formula exports" is one of its panels and the export audit lives there — built on E4 alone it renders **empty forever**, which is the 2026-08-21 lesson exactly. Gate: exports performed **through the real API as a real user** until the threshold trips; no direct event insertion by the test; dashboard visibility itself authorization-scoped |
| **E10** | **Research Center R-C** — external gateway, patents, literature, standards, benchmarks, Deep Research, Inbox, analytics | E3, E8 | 🔴 **The outbound object is allow-list-constructed, not redacted**, and adversarial fixtures cover exact and rounded ratios, aliases, trade names, Unicode, encodings, filenames, quotations, citations and **multi-turn reconstruction** — because a query naming no project can still disclose a unique material combination |
| **E11** | **Zero-cost governance** — `ZERO_COST_POLICY.md`, `FREE_TIER_LIMITS.md`, the guard | E2 | An **allow-list of provider/resource/SKU/region**; unknown resources are refused, not ignored; validated against IaC **and** runtime inventory; multiple forbidden **and unknown** fixtures |
| **E12** | **Live suite on the deployed instance** | all | 🔴 **An expected manifest, `failed == 0`, zero connectivity skips, and each remaining skip named and reviewed.** "Report three numbers" alone is satisfied by `0 passed / 500 failed` |

### Where the extension folds into v3's own slices

E5 amends Slices 1–7 rather than following them (a design system applied after
the screens is a rewrite). E3 belongs to v3's Slice 3 and was measured missing.
E4's rate limiting is I18, already in v3's register. **E6–E10 sit at and after
v3 Slice 8** and do not move MVP-1's gate, which stays exactly where §H put
it: the golden scenario on the deployed instance, asserted in UI **and**
database state.

---

## 8. Decisions the operator must make — nothing below is mine to assume

| # | Decision | Why it cannot be defaulted |
|---|---|---|
| **D1** | 🔴 **Are the four signups authorised?** Oracle (card verification), Neon, Cloudflare, Hugging Face | The standing rule is that no task may be assigned to the operator. These files spend that rule. 🔴 **v1 said "everything else still ships" and that was false** — E7 depends on E3, E8 on E7, E9 on E3+E4, so a *no* leaves only E5 and E6 (Supervisor). **The plan has been re-cut so that is no longer true:** see the note below the table — the provider-independent work is now separated out and does not wait on an answer |
| **D2** | **Own hardware, or Oracle?** Y1 pass 1 prefers a machine the operator already owns; pass 2 and the "use this" file prefer Oracle | They are genuinely different operational commitments (uptime, electricity, a home IP vs a cloud tenancy). Oracle is assumed above; say so if it is wrong |
| **D3** | **Does ADR-025 (browser PKCE + static export) change?** §9 says tokens should not sit in browser storage; that implies a server session and therefore a Next.js runtime | Reversing ADR-025 changes the deploy artefact for the whole web tier. **Do it deliberately or not at all** — this would be the fourth time this project found a defect that began as a quiet drift between two documents |
| **D4** | **Confirm Y5.** Hugging Face = model repository only; no external inference path for internal evidence | Recorded as ADR-029 on the strength of the folder's own §35 and §39. It **contradicts** pass 2 §10, which makes HF the *preferred* runtime. If the operator wants HF inference, the sanitisation boundary must be built first, and that is a slice of its own |
| **D5** | **Does the Research Center enter MVP-1, or follow it?** | v3's MVP-1 gate is the golden scenario. Adding **800–1,400 hours** inside that gate moves it by many months. Recommendation: **MVP-1 ships as scoped; E6 follows immediately.** A scope decision, and the operator's |

### 🔴 What proceeds regardless of D1 — re-cut after review

v1 gated almost everything behind four signups. Two of the sharpest defects in
this plan are **pure code and need no provider at all**, and it would be wrong
to leave them open waiting for an account:

| Work | Why it needs nothing from D1 |
|---|---|
| **E3-local — `ObjectStoragePort` + Garage adapter + real byte upload + MIME magic + ClamAV + quarantine + the classification lattice + `formula.export`** | Garage is **already in `docker-compose.yml`**, `boto3` is **already a declared dependency**, and ClamAV is a container. This closes **I41** (P1) and **I43** with no cloud account in existence |
| **E5 — design system, Storybook, the shell, the traffic light** | Entirely local. Already begun this session: `packages/design-tokens` with 31 computed contrast checks, proved by falsification |
| **E6 — Research Center R-A** (after I19) | Runs against the local PostgreSQL that has worked since 2026-08-21 |
| **I19 — close `rls_permissive()`** | A migration. It is also E6's prerequisite and the reason §1's defence-in-depth claim is currently false |
| **Y15 — the `WorkflowPort` durability contract** | A specification |

**Only the deployment tiers wait on D1**: E1, E2, E4, E9, E10, E12. That is the
honest split, and it means a *no* costs the deployment, not the product.

---

## 9. New issues raised by this extension

| # | Issue | Priority |
|---|---|---|
| **I41** | 🔴 **The SDS safety gate counts rows, not files.** `material_documents.storage_key` points at a store with no client, no upload route and no scanner — so a row *is* the safety evidence for the control the golden scenario exists to demonstrate | P1 |
| **I42** | **The AI Model Router must not exist before the evidence-classification gate does.** Building the router first creates the bypass and then asks for a guard | P1 |
| **I43** | **`formula.export` does not exist**, so export is not separable from read, is not logged, and cannot require a second approval (§31/§32) | P2 |
| **I44** | **Audit records no IP and no session id** (§33). Cheap to add now, unrecoverable retrospectively | P2 |
| **I45** | **Neon compatibility of FORCE RLS, five roles and `SET LOCAL` over the pooler is unverified.** Y3 — the measurement, not the assumption | P1 (E1) |
| **I46** | **No storage-quota monitor exists**, so Y4's 0.5 GB ceiling has no early warning | P2 |
| **I47** | **`RESUME_HERE.md` and `TODO.md` I13 state that no deployment path exists.** They become wrong the moment ADR-028 lands and must change in the same commit | P2 |
| **I48** | 🔴 **Two data-classification taxonomies (Y11)** with different levels, and Y5's outbound gate is defined in terms of `PUBLIC`, which only one of them has. One lattice, deny-by-default, unset = ceiling | P1 |
| **I49** | 🔴 **No retention or deletion anywhere (Y12).** Deleting a document leaves the content in embeddings, caches, graph edges and prior object versions. v3's F33 already promised purge-on-revocation; nothing implements it | P1 |
| **I50** | **The backup destination is unnamed (Y13)** — restic on the same tenancy with the same credentials is not a backup against account compromise or Oracle reclaiming capacity | P2 |
| **I51** | 🔴 **I18's fix in v1 could not work (Y6).** `CF-Connecting-IP` from Cloudflare IP ranges never matches behind `cloudflared`, and Caddy is a second hop. Re-designed around Caddy as sole header authority and subject-keyed limits | P1 |
| **I52** | **Oracle capacity is recorded as 2 OCPU/12 GB in the source and 4 cores/24 GB in three repo documents (Y16)**, and the number decides the Penpot exclusion and the LLM's RAM. Measure it in E1 | P2 |
| **I53** | **Oracle ARM caveats dropped from v1** — regional capacity is frequently unavailable, and the API image needs an ARM or multi-arch build. An `amd64`-only image fails at E2 after E1 signed off green | P2 |
| **I54** | **~14 of the source's 24 research tables have no owning slice.** E6 names 7, E7 names 3; `research_plans`, `research_sessions`, `research_sources`, `research_documents`, the literature/patent/competitor/benchmark tables and the `msd_*` evidence/recommendation/tool-call records are unassigned. Needs a table→slice ownership matrix, or an explicit rejection per table | P2 |

Carried forward unchanged and **not** superseded by this extension: **I3**
(golden E2E, UI half), **I19** (`rls_permissive()` is still `SELECT TRUE` —
and §1's defence-in-depth claim is false while it is open), **I21**, **I23**,
**I24**, **I27**, **I28**, **I29**, **I39**.

---

## 10. Risks

**R1 — Neon is a single point of measurement.** Mitigated by E1 running the
real suite against a real Neon project before anything depends on it, and by
Y1's exit being tested rather than described.

**R2 — 12 GB is genuinely tight.** The folder's own budget reaches ~9–10 GB
with ClamAV at ~1 GB and the local LLM at 3–4.5 GB. **It only works because
Neon takes PostgreSQL off the box.** If E1 refuses Neon, the RAM budget must
be re-cut in the same breath — PostgreSQL costs 1–2 GB and the LLM is where it
comes from. Do not discover this at E8.

**R3 — The Research Center is a second product.** Named at 250–400 hours,
staged R-A/R-B/R-C, and explicitly **outside** MVP-1's gate unless D5 says
otherwise.

**R4 — Edge security has a failure mode that looks like success.** A WAF, Bot
Fight Mode and a rate limiter all report healthy while the origin is directly
reachable and every one of them is bypassed. **E4's gate is a measurement
against the origin IP, not a screenshot of a dashboard.**

**R5 — Prompt injection scales with ingestion.** Every external document is
untrusted input to a system holding formula IP. R-C is deliberately last.

**R6 — This extension is 121 KB of prose that has not been built.** v3 was
reviewed to FAIL by Codex and adjudicated by the Supervisor before a line was
written, and that is why it survived. **This document goes to Codex and the
Supervisor before E1 starts**, and the four gates apply to it exactly as they
apply to code.
