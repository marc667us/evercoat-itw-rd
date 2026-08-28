-- 057 — a sample backs a claim about ITS OWN product
--
-- 🔴 THE HOLE THE DOCUMENT FK CLOSED AND THE SAMPLE FK DID NOT.
--
-- 056 bound `source_document_id` to the product with a three-column key, and
-- the comment beside it says exactly why:
--
--     "Without the product in the key, a label uploaded for product A could
--      be cited as evidence for product B and every other constraint would
--      still hold."
--
-- That sentence is true of samples word for word, and `composition_evidence_
-- sample_fk` was written `(sample_id, organization_id)` — tenant-scoped only.
-- So product A's tin could be recorded as the physical source of a claim about
-- product B, and nothing anywhere would refuse it.
--
-- ⚠️ IT WAS LATENT UNTIL 2026-08-28 AND IS NOT ANY MORE. No client had ever
-- sent `sample_id`; the commit that added the sample picker to the Composition
-- Evidence Matrix made the field reachable from a browser for the first time,
-- which turned a dormant schema gap into a live one. Found by the Supervisor
-- reviewing that commit, not by the reviewer that reviewed the migration.
--
-- The fix is the same shape as the document fix: give `competitors.samples`
-- the three-column unique key PostgreSQL requires on a referenced side, then
-- re-point the foreign key at it.
--
-- `MATCH SIMPLE` (the default) means the constraint is skipped entirely when
-- `sample_id IS NULL`, which is the common case — a document-sourced or
-- inferred claim cites no tin. Only rows that actually name a sample are
-- constrained, which is the intent.

-- ---------------------------------------------------------------------
-- The referenced side needs the product in its unique key
-- ---------------------------------------------------------------------
ALTER TABLE competitors.samples
    DROP CONSTRAINT IF EXISTS samples_id_product_org_key;
ALTER TABLE competitors.samples
    ADD CONSTRAINT samples_id_product_org_key
    UNIQUE (id, competitor_product_id, organization_id);

-- ---------------------------------------------------------------------
-- Re-point the evidence foreign key through the product
-- ---------------------------------------------------------------------
ALTER TABLE competitors.composition_evidence
    DROP CONSTRAINT IF EXISTS composition_evidence_sample_fk;
ALTER TABLE competitors.composition_evidence
    ADD CONSTRAINT composition_evidence_sample_fk
    FOREIGN KEY (sample_id, competitor_product_id, organization_id)
    REFERENCES competitors.samples (id, competitor_product_id, organization_id)
    ON DELETE RESTRICT;
