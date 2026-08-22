# Review adjudication — IMPLEMENTATION_PLAN_EXTENSION.md

**2026-08-22.** v1 committed at `f72905e`, reviewed before any of it was built.

| Reviewer | Findings | Verdict |
|---|---:|---|
| **Codex CLI** (adversarial plan review, read all five source files + the repo) | **30** — 3 BLOCKER, 15 HIGH, 11 MEDIUM, 1 LOW | **FAIL** |
| **Supervisor** (`/code-review`, independent, verified ~20 measurements against the code) | **11** — 4 HIGH, 5 MEDIUM, 2 LOW | findings reported inline |
| **Total** | **41** | **38 upheld, 3 narrowed** |

## 🔴 The two reviewers overlapped on almost nothing — ninth consecutive session

Codex worked the *source documents and the logic of the gates*. The Supervisor
worked the *repository*, and caught three things Codex did not because they
required reading code Codex did not open.

**Of 41 findings, exactly one pair overlaps** (Codex F18 and Supervisor #2 both
reach the golden scenario's dangling SDS row — from opposite directions: Codex
said the scenario *canonises* the broken model, the Supervisor said tightening
the gate *deadlocks the seed*). Everything else is disjoint.

This is now the ninth session running in which neither reviewer alone would
have sufficed. **Run both, every time**, remains correct and is now evidenced on
a document rather than on code.

## Three of my own measurements were wrong

The point of §2 was to measure rather than quote the handover. Two of the
measurements were still wrong, and one materially.

| Claim in v1 | Truth | Found by |
|---|---|---|
| *"no upload route"* | 🔴 **False.** `POST /api/materials/{id}/documents` → `register_document` exists, gated on `material.edit`/`supplier.manage`, and its docstring calls it *"the route without which no formula could ever be submitted"* | Supervisor |
| *"no object storage client"* | **Imprecise.** `boto3>=1.35` is declared in `pyproject.toml` and never imported. The gap is the port/adapter/byte path, not the library | Codex F17 |
| *"Oracle 2 OCPU / 12 GB"* | **Contradicts three repo documents** recording 4 ARM cores / 24 GB from the ADR-027 measurement | Supervisor |

**The first correction makes I41 worse, not smaller.** v1 described a table
nothing wrote. The truth is a table a **permission-gated production route**
writes, with no bytes behind it — so any holder of `material.edit` can satisfy
the SDS safety control with `storage_key = "sds/anything.pdf"`. The defect is
*reachable*, not theoretical. That is the single most valuable thing either
review produced.

## The three BLOCKERs

**B1 — E1's gate could pass on nothing but skips, and could not fail at all.**
`tests/db/conftest.py` calls `pytest.skip()` on any connection exception, so a
wrong Neon URL yields `0 failed` and a pile of skips. And v1 declared *both*
outcomes success ("red ⇒ Neon refused, and that is a success for this slice"),
so **every possible result passed**. Split into E1a/E1b/E1c with
`failed == 0 AND skipped == 0 AND passed == manifest`, a role/ownership/BYPASSRLS
preflight, pooler lifecycle tests, and the rule that a refusal counts only when
**diagnosed** — a connection error is a defect, not a verdict.

**B2 — E6 aggregated cross-project data while I19 was open.** `rls_permissive()`
is still `SELECT TRUE`, so the application layer is the sole tenant barrier.
E6 is the highest-value aggregation surface in the product. **I19 is now a hard
prerequisite of E6**, with FORCE-RLS and membership tests on every new table.

**B3 — Y5's threshold leaked.** v1 blocked evidence *"above `INTERNAL`"*. The
source forbids sending **internal project names** and **confidential test
data** externally — and both are `INTERNAL`. Revised to **`PUBLIC` only**, plus
an allow-list-**constructed** outbound object rather than a redacted internal
prompt, unset classification denied.

## Findings that became new reconciliations

v1 had ten Y-items. Review added six.

| New | Source | Substance |
|---|---|---|
| **Y11** | Codex | **Two classification taxonomies** in two source files, with different levels — and only one contains `PUBLIC`, which is what Y5's gate is defined in terms of. One lattice, deny-by-default |
| **Y12** | Codex | **Retention and deletion absent entirely.** Deleting a document leaves the content in embeddings, caches, graph edges and prior object versions. v3's F33 promised purge-on-revocation and nothing implements it |
| **Y13** | Codex | **Backup destination unnamed.** Restic on the same tenancy with the same credentials is not a backup against the two threats that matter |
| **Y14** | Codex | **Navigation structure owned by no slice**, though the sources specify a persistent MSD header and an 11-item submenu |
| **Y15** | Codex | *"Temporal owns it in design"* **is not a durability contract** — retries, idempotency, leases, cancellation, recovery |
| **Y16** | Supervisor | **Two Oracle capacities**, and the number decides both the Penpot exclusion and the LLM's RAM budget |

## Sequencing defects — a control shipped after the surface it protects

v1 caught one of these itself (I42). Review found five more, all the same shape:

- E3 exposed **upload** before E4 supplied **upload rate limiting** → limit moved into E3
- E2 provisioned the host before E4 **locked the origin** → E2 is now default-deny
- E3 shipped **formula export** before E9 detected **mass export** → detection moved into E3
- E9's "formula exports" panel depended only on E4, so it would have rendered **empty forever** — the 2026-08-21 lesson exactly → **E9 now depends on E3**
- E7 depended on ingestion with **no durable-workflow contract** → Y15 is an E7 prerequisite

## Gates rewritten: eleven of twelve could pass against broken work

Codex checked every gate for falsifiability. Beyond B1, the ones worth naming:

- **E2** — *"the monitor shows real numbers"*: hard-coded plausible numbers pass. Now compared against provider queries, with an **injected** threshold crossing and fail-closed on staleness.
- **E5** — *"zero axe violations"*: this document itself records axe missing a 1.48:1 contrast defect. Now **computed** contrast on rendered colour, plus print snapshots and an icon+text assertion. **Already built and falsified this session.**
- **E6** — *"a real question, every claim sourced"*: a refusal contains no unsourced claims. Now a fixed seeded question with expected facts, **forbidden facts**, and minimum recall.
- **E7** — one boundary spec cannot cover SQL, vector, graph, cache, citation, reranker and log channels. Now a **route matrix**, each row naming the guard removed.
- **E8** — a mock external runtime that is never invoked makes *"cannot receive"* vacuously true. Now **forced selection** with assertions at the transport boundary.
- **E9** — a test inserting `SECURITY_HIGH` directly proves nothing. Now exports through the **real API as a real user**.
- **E12** — *"report three numbers"* is satisfied by `0 passed / 500 failed`. Now an expected manifest with `failed == 0`.

## Narrowed rather than upheld

- **Codex F16 (estimate).** Accepted in substance — 250–400 h revised to **800–1,400 h**. Narrowed only in that it stays a planning *range* to be replaced by spike measurement, not a commitment.
- **Codex F27 (24 tables unassigned).** Accepted as **I54**; a full table→slice matrix belongs with E6/E7 detailed design rather than in a plan-level document.
- **Supervisor #10 (Y5 decided vs D4 deferred).** Both framings kept deliberately: Y5 is **recorded as ADR-029 and built as though decided**, because the safe default must not wait on an answer; D4 exists so the operator can overturn it knowingly. A gate that ships open is the defect; a decision the operator may reverse is not.

## Y5 — the argument for the other side, as requested

Codex was asked to argue against my refusal of the Hugging Face inference path.
It found a genuinely safe construction, and it is narrower than the source's
*"preferred runtime"*: a Space processing **exclusively public, synthetic or
fully generalised** prompts, built from allow-listed fields, with no evidence
pack, conversation history, citation metadata or telemetry crossing the
boundary, and local inference remaining mandatory for internal evidence.

That makes HF usable for public literature summarisation. **It does not make it
safe as the default MSD path.** Codex's own conclusion: *"Y5's basic refusal is
right; its `above INTERNAL` threshold is not strict enough."* Both halves
adopted.

---

**Outcome: v1 FAIL → v2.** 41 findings, 38 upheld and addressed, 3 narrowed.
Six new reconciliations, seven new issues (I48–I54), every gate rewritten, and
three of my own measurements corrected — one of which made the plan's sharpest
finding sharper.
