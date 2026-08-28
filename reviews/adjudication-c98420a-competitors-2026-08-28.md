# Adjudication — `c98420a` (Phase 3 competitor vertical), 2026-08-28

Two reviewers, run independently and in parallel. **Codex raised 4 findings, the
Supervisor raised 11, and they overlap on exactly two.** That is the 22nd
consecutive session in which neither reviewer alone would have been enough.

- Codex: `reviews/codex-c98420a-competitors-2026-08-28.md` — **VERDICT: FAIL**
- Supervisor: `/code-review c98420a medium` — 3 HIGH, 4 MEDIUM, 4 LOW

Every finding was **measured against the running database or the source before
being accepted**, per the standing rule that a reviewer's claim is evidence, not
a verdict. One of Codex's was right about the defect and wrong about its
direction; it is recorded as such rather than restated.

---

## The one that mattered most, and it was mine

🔴 **`composition_evidence_sample_fk` was tenant-scoped while the document key
beside it was product-scoped** (Supervisor 7).

056 bound `source_document_id` to the competitor product with a three-column
key, and wrote the reason next to it in as many words: *"a label uploaded for
product A could be cited as evidence for product B and every other constraint
would still hold."* That sentence is true of samples verbatim, and the sample
key was left `(sample_id, organization_id)`.

**It was latent only because nothing had ever sent `sample_id`.** The commit
under review added the sample picker — which is to say, *this commit made a
dormant schema gap reachable from a browser*. Neither the reviewer that reviewed
migration 056 nor Codex on this commit found it.

Closed by **migration 057 / `p1000`**, written in both trees, which adds
`samples_id_product_org_key` and re-points the foreign key through the product.
The revision **asserts the resulting constraint definition** rather than that
the DDL ran: a two-column key would leave the hole open while the migration log
read exactly like a fix.

> **Lesson, and it is a new one for this project:** *ask what a change makes
> REACHABLE, not only what it changes.* Adding a client for an existing field is
> not a client-side change — it is the first time the field's constraints are
> load-bearing.

---

## Findings, and their disposition

| # | Source | Finding | Disposition |
|---|---|---|---|
| P1 | Codex | `POST /benchmarks` gated on `test.view` | **Accepted.** A read permission on a write route. Now `require_permission("material.edit", "test.view", require_all=True)`. Measured: `product_development_chemist` holds both; `procurement_specialist` holds `material.edit` without `test.view` and is correctly excluded. |
| 6 | Supervisor | same finding, independently | — |
| P2 | Codex | cross-tenant loop counts zero because the fixture creates rows only in `products` | **Accepted, and it was the sharpest finding of the four.** A guard that passes because it cannot see — the exact failure this file's own header warns about. The fixture now writes one row into all four tables and the positive control checks all four. **Falsified: disabling RLS on `competitors.samples` now turns it red; before the fix it stayed green.** |
| P2 | Codex | manual observation does not require a sample | **Accepted.** Offering the citation without requiring it left the default doing what it always did. |
| P2 | Codex | `laboratory` source has no test selector | **Accepted as a defect, REJECTED as described.** Codex said an uncited laboratory claim could be created and later verified. Measured: `composition_evidence_laboratory_shape` requires a sample *or* a test, so the row **cannot be created at all** — the menu option was unusable, not permissive. Two permanent guards added, one per direction. |
| 1 | Supervisor | `verify_evidence` is the only write with no `guarded_write` and no `except DBAPIError` | **Accepted.** Two of 056's own guards refuse that UPDATE, and both escaped as a raw `DBAPIError` past `post_grade`'s `except CompetitorError` → HTTP 500 over an aborted transaction instead of 409. Proof it was meant to be translated: `_translate` already carried branches for both refusals and **both were unreachable**. |
| 2 | Supervisor | `ProductWorkspace` never renders `writes.error` | **Accepted.** The page's only alert was bound to the *separate* mutation instance on the parent. Upload, sample, evidence, grade and benchmark all failed in silence — including the **503 raised when no malware verdict could be obtained**, the one status the route's docstring insists must never read as success. |
| 3 | Supervisor | `POST /evidence/{id}/grade` has no caller | **Accepted, and it is the same defect class this commit set out to fix.** I removed it for samples and benchmarks and did not notice the third instance sitting beside them. The client function and the hook both existed; **a client function is not a caller.** Every claim stayed `possible` forever, four of the five `CONFIDENCE` branches could never render, and `compliance.review_sds` had no browser path. |
| 5 | Supervisor | `_translate` leaks raw PostgreSQL text | **Accepted.** Four constraints fell through to `CompetitorError(detail)`, returning schema, table and constraint expression as the response body. Entering From=50/To=10 was enough. Four branches added, plus one for 057's new key. |
| 8 | Supervisor | `projectList.error` unsurfaced | **Accepted.** A 403 for a caller without `project.view` rendered as an empty menu and a dead button — a working feature reading as a broken one. |
| 9 | Supervisor | file input never reset | **Accepted.** Re-selecting the *same* file fires no `change` event, so a failed upload could not be retried without choosing a different file first. |
| 10 | Supervisor | `is_balance` rendered, settable by nothing | **Accepted.** A rendering path with no writer. Checkbox added; it clears the range, because the constraint forbids both. |
| 11 | Supervisor | all new tests are DB-level; no route or service coverage | **Accepted as an issue, not fixed here** — filed as **I112**. It is why findings 1, 4 and 5 were green. Real, and larger than this commit. |

---

## What the tests measured that reasoning had got wrong

Recorded because in each case the reasoning was confident and the measurement disagreed.

1. **`core.roles` has no `organization_id`.** A role is platform-level; the
   *membership* binds it to a tenant — which is why the verifier trigger joins
   through `core.organization_members`.
2. **A `BEFORE INSERT` trigger runs before row CHECKs.** So
   `composition_evidence_verification_complete` is unreachable until the named
   verifier actually holds the permission. Without the grant the test would have
   passed while measuring an entirely different mechanism.
3. **Triggers fire in NAME order.** `material_documents_evidence_write_once`
   (038) sorts before `material_documents_owner_write_once` (056), so 056's
   `material_id` branch is unreachable defence-in-depth. Its
   `competitor_product_id` branch **is** load-bearing — 038 checks material,
   organization and document type only.
4. **`alembic_version` is owned by `postgres` here, not `evercoat_owner`.**
   `alembic upgrade head` needs `MIGRATION_DATABASE_URL` with the superuser on
   this host; both `DATABASE_URL` roles are refused on the version table.

## Falsification performed

Guards are not trusted for passing. Two were broken on purpose **in the
database**, not in the code:

| Broken | Result | Restored |
|---|---|---|
| `DROP TRIGGER material_documents_supersedes_same_owner` | 2 red, including the one asserting the SDS stays in `usable_documents` and the formula stays submittable | ✅ verified |
| `ALTER TABLE competitors.samples DISABLE ROW LEVEL SECURITY` | 2 red, including the cross-tenant loop Codex had shown was a false positive | ✅ verified, `force=true` re-asserted |
