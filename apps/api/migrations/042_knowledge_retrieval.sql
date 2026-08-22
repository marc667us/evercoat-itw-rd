-- =====================================================================
-- 042 — knowledge retrieval, with authorization on every chunk
--
-- Slice 8's foundation, and the remaining half of I23.
--
-- ---------------------------------------------------------------------
-- 🔴 THE ONE RULE THIS SCHEMA EXISTS TO MAKE POSSIBLE
-- ---------------------------------------------------------------------
--
-- `IMPLEMENTATION_PLAN.md` §E, and Codex's F33 before it:
--
--     Filter before retrieval, never after generation. Authorization
--     provenance is carried through every chunk, embedding, cache entry,
--     conversation memory, tool output and model dataset.
--
-- The tempting shape is a chunks table keyed only on a document id, with the
-- authorization decided when the document is opened. That fails in the one way
-- that matters: a similarity search returns the CHUNK, the chunk's text goes
-- into an answer, and the check that would have refused it never runs. Nothing
-- about the answer would look wrong.
--
-- So every chunk carries its own `organization_id`, `project_id` and
-- `classification`, and its RLS policy is the same predicate the projects
-- themselves use. The caller's boundary is applied by PostgreSQL, as part of
-- the scan, rather than by application code after an answer exists.
--
-- ⚠️ AND THE PREDICATE IS ORGANIZATION + PROJECT. NOT CLASSIFICATION.
--
-- The chunk carries `classification` so the label travels with the text -- to
-- the screen, to MSD's citations, and to ADR-029's outbound gate. The policies
-- below do NOT consult it, deliberately: migration 039 §2 states that
-- classification is a property of the DATA and not an access group, there is
-- no per-user clearance in this schema for it to be compared against, and
-- merging the two axes is the §6 defect this project has found six times.
--
-- Listing the three columns in one sentence made it easy to read the third as
-- part of the boundary, and a reviewer did exactly that. An organization-wide
-- (`project_id IS NULL`) DIRECTOR_CONTROLLED document is readable by every
-- `knowledge.view` holder in the organization; the classification tells them
-- how to handle it, it does not stop them.
--
-- ⚠️ AND THE PRECISE CLAIM MATTERS, BECAUSE THE FIRST VERSION OF IT WAS WRONG.
--
-- This comment used to say the rows were filtered "BEFORE ORDER BY". That is
-- not how an HNSW scan executes. The index yields approximately
-- `hnsw.ef_search` candidate rows (default 40) ordered by distance, and the
-- RLS qual is applied as a FILTER over those candidates. The Supervisor
-- caught it -- the codebase's own "a comment asserting engine semantics the
-- engine does not have" pattern.
--
-- The SECURITY property is unaffected: a row the policy rejects is never
-- returned, whatever order the candidates arrive in. What is affected is
-- RECALL, and only for restricted users: if the 40 nearest chunks in an
-- organization all sit in projects the asker is not a member of, the search
-- returns NOTHING even though a permitted, relevant passage exists further
-- down the index. The asker sees the ordinary "I found nothing" refusal.
--
-- That is a fail-CLOSED degradation, which is the right direction, but it is
-- invisible -- so it is written down here rather than discovered later by
-- somebody wondering why the knowledge base "does not work for engineers".
-- The fix, when the corpus is large enough to need it, is to raise
-- `hnsw.ef_search` for this query or to fall back to an exact scan; neither is
-- justified over a corpus this small, and both need measuring, not guessing.
--
-- ⚠️ `project_id` IS NULLABLE AND THAT IS NOT A LOOPHOLE. A document may be
-- organization-wide (a standard, a policy). A NULL project means "visible to
-- the organization", which is a decision the policy states explicitly rather
-- than a gap it leaves open -- and the classification column still applies.
--
-- ---------------------------------------------------------------------
-- WHY 384 DIMENSIONS
-- ---------------------------------------------------------------------
--
-- It is `all-MiniLM-L6-v2`'s width -- the model ADR-013 names -- so the column
-- does not have to change when a real sentence-transformer replaces the
-- default embedder. `app/core/embedding.py` explains what that default is and,
-- more importantly, what it is NOT.
--
-- Y4's budget: a 384-dim float32 vector is ~1.5 KB plus index overhead, so a
-- 150 MB allowance is roughly 75,000 chunks. The plan's rule stands -- embed
-- selected technical sections, never "everything" -- and the ingestion service
-- enforces a per-document chunk cap rather than trusting it.
-- =====================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS knowledge;
ALTER SCHEMA knowledge OWNER TO evercoat_owner;

-- ---------------------------------------------------------------------
-- Documents
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS knowledge.documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES core.organizations (id),
    -- NULL = organization-wide. See the header: a stated decision, not a gap.
    project_id      UUID,
    title           TEXT NOT NULL,
    source          TEXT NOT NULL,
    -- Where the bytes are, when they came from a file. The knowledge tier
    -- never holds content that has not been through I41's pipeline.
    storage_key     TEXT,
    classification  TEXT NOT NULL DEFAULT 'DIRECTOR_CONTROLLED'
                    REFERENCES core.classifications (code),
    ingested_by     UUID NOT NULL REFERENCES core.users (id),
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT documents_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT documents_project_fk FOREIGN KEY (project_id, organization_id)
        REFERENCES projects.projects (id, organization_id),
    CONSTRAINT documents_source_check CHECK (
        source IN ('internal_note', 'material_document', 'standard', 'procedure', 'external')
    )
);

-- ---------------------------------------------------------------------
-- Chunks — each one independently authorized
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS knowledge.chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES core.organizations (id),
    document_id     UUID NOT NULL,
    -- 🔴 DENORMALISED DELIBERATELY. These three repeat the document's values
    -- so the RLS policy on THIS table can decide without a join, and so a
    -- similarity search is filtered before it ranks. A join through
    -- `documents` would work and would put the authorization one hop away
    -- from the row a retrieval actually returns.
    --
    -- Kept honest by a trigger below: they are copied from the document and
    -- may not be set independently.
    project_id      UUID,
    classification  TEXT NOT NULL REFERENCES core.classifications (code),
    ordinal         INT  NOT NULL,
    content         TEXT NOT NULL,
    embedding       vector(384),
    -- 🔴 WHICH EMBEDDER PRODUCED THAT VECTOR.
    --
    -- Vectors from two different embedders are not comparable, and mixing
    -- them does not raise: cosine distance is still a number, the search
    -- still returns rows, and the ranking is quietly meaningless. Storing the
    -- name makes a mixed index DETECTABLE and re-embedding possible.
    --
    -- Added because `app/core/embedding.py` said the caller records this and
    -- the column did not exist -- the overclaiming comment this codebase
    -- keeps finding, caught in the same hour it was written.
    embedder_name   TEXT NOT NULL,
    -- The platform invariant (tests/db/test_001_core_tenancy.py): every
    -- tenant-scoped table carries UNIQUE (id, organization_id) so that
    -- anything referencing it can use a COMPOSITE foreign key. Omitted here
    -- at first, and the full suite caught it -- chunks is precisely the table
    -- a later citation / provenance / relevance-feedback row will point at,
    -- and without this key that FK cannot be composite. The predictable
    -- reaction is a single-column FK, which reintroduces exactly the
    -- cross-tenant reference the rest of this migration exists to prevent.
    CONSTRAINT chunks_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT chunks_document_fk FOREIGN KEY (document_id, organization_id)
        REFERENCES knowledge.documents (id, organization_id) ON DELETE CASCADE,
    CONSTRAINT chunks_ordinal_unique UNIQUE (document_id, ordinal),
    CONSTRAINT chunks_content_not_blank CHECK (length(btrim(content)) > 0)
);

-- The chunk's authorization is the document's. Copied by trigger rather than
-- trusted from the caller: a chunk that disagreed with its document would be
-- exactly the "child less restrictive than its parent" defect I69 names, and
-- here the child is the row a retrieval returns.
CREATE OR REPLACE FUNCTION knowledge.chunk_inherits_document()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = knowledge, pg_temp AS $fn$
DECLARE
    d RECORD;
BEGIN
    SELECT project_id, classification, organization_id INTO d
      FROM knowledge.documents
     WHERE id = NEW.document_id;

    IF d IS NULL THEN
        RAISE EXCEPTION 'chunk references a document that does not exist';
    END IF;

    NEW.organization_id := d.organization_id;
    NEW.project_id      := d.project_id;
    NEW.classification  := d.classification;
    RETURN NEW;
END $fn$;

ALTER FUNCTION knowledge.chunk_inherits_document() OWNER TO evercoat_owner;

DROP TRIGGER IF EXISTS chunks_inherit_authorization ON knowledge.chunks;
CREATE TRIGGER chunks_inherit_authorization
    BEFORE INSERT OR UPDATE ON knowledge.chunks
    FOR EACH ROW EXECUTE FUNCTION knowledge.chunk_inherits_document();

-- ---------------------------------------------------------------------
-- 🔴 AND THE DOCUMENT CAN CHANGE AFTER ITS CHUNKS EXIST.
--
-- The trigger above fires on the CHUNK. That covers ingestion and nothing
-- else, which left the denormalisation one-way: reclassify a document to
-- CONFIDENTIAL, or move it into a restricted project, and its already-stored
-- chunks kept the OLD project_id and the OLD classification indefinitely.
--
-- Codex found it. It matters more here than a stale copy usually would,
-- because this schema's entire argument is that the CHUNK is independently
-- authorized -- the comment above literally says the policy on this table can
-- decide "without a join". That claim was true only until the first document
-- update. `retrieve()` happens to join `documents` today, and that join is
-- what kept the defect from being a live disclosure; but a correctness
-- property that survives only because of an unrelated JOIN in one caller is
-- not the property the schema advertises, and the next caller to take the
-- comment at its word is the one who gets hurt.
--
-- So the propagation runs in both directions. Re-stating the chunks' columns
-- fires `chunk_inherits_document()` on each row, which re-reads the document
-- and therefore cannot disagree with it.
--
-- ⚠️ INVOKER, NOT SECURITY DEFINER, AND IT FAILS CLOSED. If the new project
-- is one the updater cannot see, the chunk UPDATE violates the chunks policy
-- and the whole transaction aborts -- so a document cannot be moved somewhere
-- that would leave its own passages unreachable to the person moving it. The
-- alternative, a DEFINER trigger that always succeeds, would silently hand
-- rows to a scope the actor could not verify.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION knowledge.document_repropagates_to_chunks()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = knowledge, pg_temp AS $fn$
BEGIN
    UPDATE knowledge.chunks
       SET organization_id = NEW.organization_id,
           project_id      = NEW.project_id,
           classification  = NEW.classification
     WHERE document_id = NEW.id;
    RETURN NULL;
END $fn$;

ALTER FUNCTION knowledge.document_repropagates_to_chunks() OWNER TO evercoat_owner;

DROP TRIGGER IF EXISTS documents_repropagate ON knowledge.documents;
CREATE TRIGGER documents_repropagate
    AFTER UPDATE ON knowledge.documents
    FOR EACH ROW
    WHEN (
        OLD.organization_id IS DISTINCT FROM NEW.organization_id
        OR OLD.project_id     IS DISTINCT FROM NEW.project_id
        OR OLD.classification IS DISTINCT FROM NEW.classification
    )
    EXECUTE FUNCTION knowledge.document_repropagates_to_chunks();

-- ---------------------------------------------------------------------
-- Row-level security — the same predicate the projects use
-- ---------------------------------------------------------------------
-- ⚠️ ENABLE, NOT FORCE -- DELIBERATELY, AND TRACKED AS I58.
--
-- Codex flagged the absence of FORCE ROW LEVEL SECURITY here. It is right
-- about the property (both tables are owned by `evercoat_owner`, and an owner
-- is exempt from a policy that is not FORCED) and wrong about the remedy for
-- THIS migration. `relforcerowsecurity` is FALSE on every table in this
-- schema by design, and `tests/db/test_024_memberships_for_subject.py` and
-- `test_011_audit_chain_scope.py` are tripwires asserting it stays FALSE
-- until the I58 cutover: forcing it piecemeal breaks
-- `core.memberships_for_subject`, and with it `GET /api/me` and sign-in for
-- every user.
--
-- The application connects as `evercoat_app`, which owns nothing and holds no
-- BYPASSRLS, so the retrieval path IS policy-bound today. What is missing is
-- the owner-path defence in depth, and it is missing schema-wide rather than
-- here. These two tables are named in I58's scope so the cutover does not
-- reach head with the knowledge tier left out of it.

ALTER TABLE knowledge.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge.chunks    ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS documents_scope ON knowledge.documents;
CREATE POLICY documents_scope ON knowledge.documents
    USING (
        organization_id = core.current_org_id()
        AND (
            project_id IS NULL
            OR EXISTS (
                SELECT 1 FROM projects.projects p
                 WHERE p.id = knowledge.documents.project_id
                   AND p.organization_id = knowledge.documents.organization_id
                   AND (p.confidentiality = 'normal' OR core.is_project_member(p.id))
            )
        )
    );

-- 🔴 THE POLICY THAT MAKES "FILTER BEFORE RETRIEVAL" TRUE.
-- Identical predicate, on the chunks themselves, so a vector search is scoped
-- by PostgreSQL before it orders by distance.
DROP POLICY IF EXISTS chunks_scope ON knowledge.chunks;
CREATE POLICY chunks_scope ON knowledge.chunks
    USING (
        organization_id = core.current_org_id()
        AND (
            project_id IS NULL
            OR EXISTS (
                SELECT 1 FROM projects.projects p
                 WHERE p.id = knowledge.chunks.project_id
                   AND p.organization_id = knowledge.chunks.organization_id
                   AND (p.confidentiality = 'normal' OR core.is_project_member(p.id))
            )
        )
    );

DROP POLICY IF EXISTS documents_insert ON knowledge.documents;
CREATE POLICY documents_insert ON knowledge.documents
    FOR INSERT WITH CHECK (organization_id = core.current_org_id());
DROP POLICY IF EXISTS chunks_insert ON knowledge.chunks;
CREATE POLICY chunks_insert ON knowledge.chunks
    FOR INSERT WITH CHECK (organization_id = core.current_org_id());

-- ---------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS chunks_document_idx ON knowledge.chunks (document_id, ordinal);
CREATE INDEX IF NOT EXISTS chunks_scope_idx    ON knowledge.chunks (organization_id, project_id);
CREATE INDEX IF NOT EXISTS documents_scope_idx ON knowledge.documents (organization_id, project_id);

-- Cosine distance, matching the embedder's normalisation. HNSW rather than
-- IVFFlat: IVFFlat needs training data to build a useful list structure, and
-- an index built over an empty table would have to be rebuilt later -- the
-- kind of thing nobody remembers to do.
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON knowledge.chunks USING hnsw (embedding vector_cosine_ops);

ALTER TABLE knowledge.documents OWNER TO evercoat_owner;
ALTER TABLE knowledge.chunks    OWNER TO evercoat_owner;

-- 🔴 SCHEMA USAGE FIRST. Table grants are INERT without it: PostgreSQL
-- refuses "permission denied for schema knowledge" before it ever consults
-- the table privileges below. Measured -- every retrieval as `evercoat_app`
-- failed on this, with GRANTs on both tables already in place.
GRANT USAGE ON SCHEMA knowledge TO evercoat_app, evercoat_report;

GRANT SELECT, INSERT, UPDATE, DELETE ON knowledge.documents TO evercoat_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON knowledge.chunks    TO evercoat_app;
GRANT SELECT ON knowledge.documents, knowledge.chunks TO evercoat_report;

COMMENT ON TABLE knowledge.chunks IS
    'Retrievable passages. Each carries its OWN organization, project and '
    'classification -- copied from its document by trigger -- so a similarity '
    'search is filtered by RLS BEFORE it ranks. Deciding authorization when '
    'the document is opened would be too late: the chunk''s text is already in '
    'the answer by then. See IMPLEMENTATION_PLAN.md §E and Codex F33.';

COMMIT;


-- ---------------------------------------------------------------------
-- Prove the inheritance trigger, then roll it back.
-- ---------------------------------------------------------------------
DO $probe$
DECLARE
    v_org  UUID;
    v_user UUID;
    v_doc  UUID;
    v_got  TEXT;
BEGIN
    SELECT o.id, u.id INTO v_org, v_user
      FROM core.organizations o
      JOIN core.organization_members m ON m.organization_id = o.id
      JOIN core.users u ON u.id = m.user_id
     LIMIT 1;

    IF v_org IS NULL THEN
        RAISE NOTICE '042: no organization to probe against; tests/db covers it';
        RETURN;
    END IF;

    INSERT INTO knowledge.documents
        (organization_id, title, source, classification, ingested_by)
    VALUES (v_org, '042 probe', 'internal_note', 'CONFIDENTIAL', v_user)
    RETURNING id INTO v_doc;

    -- Deliberately claim a WEAKER classification than the document.
    INSERT INTO knowledge.chunks
        (organization_id, document_id, classification, ordinal, content, embedder_name)
    VALUES (v_org, v_doc, 'PUBLIC', 1, 'probe', 'probe');

    SELECT classification INTO v_got FROM knowledge.chunks WHERE document_id = v_doc;

    IF v_got <> 'CONFIDENTIAL' THEN
        RAISE EXCEPTION
            '042: a chunk kept its own classification (%). A chunk less '
            'restrictive than its document is the row a retrieval RETURNS, so '
            'that gap would be the disclosure.', v_got;
    END IF;

    RAISE EXCEPTION 'rollback the probe';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLERRM <> 'rollback the probe' THEN
            RAISE;
        END IF;
END $probe$;
