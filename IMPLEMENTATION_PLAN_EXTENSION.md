# IMPLEMENTATION_PLAN_EXTENSION.md — EvercoatITWRD APP

**Extension v1, 2026-08-22.** Additive to `IMPLEMENTATION_PLAN.md` (v3).
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
| Rate limiting | **Zero implementation.** No middleware, no dependency, no counter. Confirms I18 |
| Object storage client | **None.** Garage is in `docker-compose.yml` and in `config.py` (`garage_endpoint`, `garage_bucket`, keys) and has **no client, no upload route, no `UploadFile` anywhere in `app/api/`** |
| Upload security | **None.** No ClamAV, no quarantine, no MIME-magic validation, no filename sanitisation |
| Storybook | **Absent.** Not in `apps/web/package.json`, no `.storybook/` |
| Research Center | **Absent.** Migrations stop at `031`; no research schema, no `documents` domain |
| Web screens | **15** page routes. Research Center needs ~18 more |
| MSD today | 1 conductor, 5 tool modules (`guidance` `records` `safety` `formulation` `work`), 4 routes |

### 🔴 The measurement that is a defect, not a gap

`materials.material_documents` **exists** (migration 015) with `storage_key`,
`content_type`, `byte_size`, `checksum_sha256`. Nothing writes bytes to that
key, because there is no object-store client and no upload route.

And `formulations/service.py:1265` and `msd_conductor.py:517` both gate on
`requires_sds AND sds_count == 0`. **They count rows.**

So a `material_documents` row with a `storage_key` pointing at nothing
satisfies the SDS safety control — the control the golden scenario exists to
demonstrate — while no SDS was ever stored, scanned, or read by anybody. The
row *is* the safety evidence. This is the same shape as every "which
production path writes it?" finding this project has logged, asked of a
**file** rather than a role or a status, and it is exactly the surface the new
security file's upload pipeline lands on. Raised as **I41**.

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
  ships with exactly one runtime (Oracle-local) and a **hard policy gate**: a
  runtime declared `external: true` may not receive a prompt carrying any
  evidence item classified above `INTERNAL`. The gate is a test, not a
  comment.
- If an external runtime is ever wanted, it is a **separate ADR** with the
  sanitisation boundary of §35 built and tested first.

Recorded as **ADR-029**. Raised as **I42** (build the classification gate
before any router exists to bypass it).

### Y6 — Rate limiting: I18's blocker is answered by these files

**I18 has been blocked, correctly, on one question that was never a code
question:** what does the limiter key on? Behind a proxy,
`request.client.host` is the proxy for every caller (one bucket for the whole
internet, fails closed on the first burst); trusting `X-Forwarded-For` lets an
attacker mint unlimited keys and defeats the limit entirely.

`itw evercoat security.txt` answers it by fixing the topology:

```
Internet → Cloudflare (proxied, DNSSEC) → Cloudflare Tunnel → Caddy → FastAPI
```

§2 requires the origin to be unreachable except through Cloudflare — *"Use
Cloudflare Tunnel or firewall rules so users cannot bypass Cloudflare"* — and
§13 requires trusted-proxy configuration rather than blanket header trust.

**With exactly one trusted hop, the key is `CF-Connecting-IP`, accepted only
from Cloudflare's published IP ranges and rejected otherwise.** That is a
decidable rule, so **I18 is unblocked** and moves into E4.

⚠️ It is unblocked *conditionally*: it is only true once the origin genuinely
cannot be reached directly. **Ship the limiter and the origin lock-down in the
same slice**, or the limiter is keyed on a header anyone can set. A limiter
keyed wrongly is worse than none — that was I18's own finding and it survives.

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

## 4. Security: what the 53 sections ask for, against what is built

Not a restatement. Only the delta, measured.

### Already satisfied by v3 (no work)

§16 explicit authorization chain · §17 IDOR/BOLA resource-level checks · §18
Pydantic validation · §19 parameterized SQL · §26 separate DB users · §27 RLS
· §30 SOPS+age · §33 audit trail · §35 MSD never exceeds the caller · §37 tool
allowlist (5 tool modules, no generic SQL tool) · §38 MSD proposes, humans act
· §41 Semgrep/Gitleaks/Trivy in CI.

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
knowledge graph. v3's whole MVP-1 was estimated at 700–1,050 engineering
hours. **This is not a slice. On the same basis it is 250–400 hours**, and
saying otherwise now would repeat exactly the fidelity failure v3's §K
recorded and corrected.

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

| # | Slice | Depends on | Gate |
|---|---|---|---|
| **E1** | **Neon + Oracle feasibility, measured** — throwaway Neon project, `alembic upgrade head`, run `tests/db/` **against Neon**; provision the Oracle A1 VM; exercise a Neon→Oracle `pg_dump`/restore | D1 | **passed/failed/skipped against Neon, as three numbers.** Red ⇒ Neon refused, PostgreSQL on Oracle (Y1 pass 1), and that is a **success** for this slice |
| **E2** | **Oracle production host** — Ubuntu, Docker Compose, Caddy, `ufw`, SSH keys, `fail2ban`, container hardening, `restic` encrypted backups, Uptime Kuma, **quota monitor** (Y4) with GREEN/YELLOW/RED thresholds | E1 | A restore drill succeeds from an encrypted backup. The quota monitor shows real numbers, not placeholders |
| **E3** | **`ObjectStoragePort` + the document pipeline** — port with Garage and Oracle OS adapters; upload route; size → extension → MIME magic → UUID filename → **ClamAV** → quarantine → approved; formula IP classification + `formula.export` + export audit | E2 | **I41 closed:** the SDS gate counts documents whose bytes exist and passed a scan. Proved by falsification — a row with a dangling `storage_key` must **fail** the gate |
| **E4** | **The edge and the API's own limits** — Cloudflare DNSSEC/proxy/WAF/Bot Fight/Turnstile/Tunnel; origin unreachable directly; `CF-Connecting-IP` trusted-proxy config; **Valkey rate limiting**; CSP + security headers; MFA for the four roles | E2, D3 | **I18 closed.** Direct-to-origin is refused (measured, not configured). A forged `CF-Connecting-IP` from a non-Cloudflare source does **not** mint a new bucket |
| **E5** | **Design system + Storybook** — `packages/design-tokens`, 8 named stories, axe per story, traffic-light and MSD-provenance components | — | Every existing screen consumes tokens. Zero axe violations at component level, and **a deliberately broken contrast is caught** |
| **E6** | **Research Center R-A** — 7 tables, Findings register, Notebook, Materials/Test/Failure Intelligence, evidence grading, confidence | v3 Slices 5–7 | A real cross-project question answered from seeded records, every claim sourced, **with no LLM running** |
| **E7** | **Research Center R-B** — pgvector, ingestion, embeddings, reranker, knowledge graph, hybrid retrieval, prompt-injection boundary | E3, E6 | `msd_boundary.spec.ts` green **and proved by falsification** |
| **E8** | **MSD multi-agent** — Research / Formulation / Materials / Testing / DOE / Failure / Modeling / Evidence agents under the existing §0.2 orchestrator→conductor topology; AI Model Router with **one** runtime and the Y5 classification gate | E7 | An external-flagged runtime **cannot** receive above-`INTERNAL` evidence. Test, not comment |
| **E9** | **Admin Security Dashboard** — anomaly detection, `SECURITY_*` events, failed logins, blocked IPs, rate-limit events, formula exports, role changes | E4 | A simulated mass-export raises `SECURITY_HIGH` and appears on the dashboard |
| **E10** | **Research Center R-C** — external gateway, patents, literature, standards, benchmarks, Deep Research, Research Inbox, analytics | E3, E8 | A sanitised external query is proved to carry **no** proprietary identifier — falsification test on the sanitiser |
| **E11** | **Zero-cost governance** — `infrastructure/ZERO_COST_POLICY.md`, `FREE_TIER_LIMITS.md`, the ZERO-COST GUARD, CI check that refuses a non-free resource | E2 | CI **fails** on a deliberately introduced paid-tier resource |
| **E12** | **Live suite on the deployed Oracle instance** | all | **passed / failed / skipped as three numbers** against the deployed URL |

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
| **D1** | 🔴 **Are the four signups authorised?** Oracle (card verification), Neon, Cloudflare, Hugging Face | The standing rule is that no task may be assigned to the operator. These files spend that rule. **If the answer is no, E1–E4 and E10–E12 are all unreachable** and the app stays local-plus-tunnel. Everything else in this extension still ships |
| **D2** | **Own hardware, or Oracle?** Y1 pass 1 prefers a machine the operator already owns; pass 2 and the "use this" file prefer Oracle | They are genuinely different operational commitments (uptime, electricity, a home IP vs a cloud tenancy). Oracle is assumed above; say so if it is wrong |
| **D3** | **Does ADR-025 (browser PKCE + static export) change?** §9 says tokens should not sit in browser storage; that implies a server session and therefore a Next.js runtime | Reversing ADR-025 changes the deploy artefact for the whole web tier. **Do it deliberately or not at all** — this would be the fourth time this project found a defect that began as a quiet drift between two documents |
| **D4** | **Confirm Y5.** Hugging Face = model repository only; no external inference path for internal evidence | Recorded as ADR-029 on the strength of the folder's own §35 and §39. It **contradicts** pass 2 §10, which makes HF the *preferred* runtime. If the operator wants HF inference, the sanitisation boundary must be built first, and that is a slice of its own |
| **D5** | **Does the Research Center enter MVP-1, or follow it?** | v3's MVP-1 gate is the golden scenario. Adding 250–400 hours inside that gate moves it by months. Recommendation: **MVP-1 ships as scoped; E6 follows immediately.** But it is a scope decision and it is the operator's |

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
