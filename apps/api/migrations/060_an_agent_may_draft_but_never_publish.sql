-- =====================================================================
-- 060 — AN AGENT MAY DRAFT, BUT IT MAY NEVER PUBLISH
-- =====================================================================
--
-- The owner's instruction ends: "the global competitor product marketplace
-- must be managed by agents". This is the boundary that makes that safe to
-- say.
--
-- ---------------------------------------------------------------------
-- 🔴 WHAT AN AGENT-MANAGED PUBLIC CATALOGUE ACTUALLY RISKS
-- ---------------------------------------------------------------------
--
-- The marketplace is PUBLIC. It publishes prices, safety-data links and
-- technical claims about named manufacturers. An agent that could publish
-- would be an agent that could put an invented price, or an invented SDS
-- link, in front of anonymous readers as fact — with no human between the
-- generation and the publication.
--
-- Rule 4 of this project is "Humans approve", and §7 forbids AI becoming a
-- permission-bypass channel. The specification says the same thing in its
-- own words: a detected product "creates a reviewable draft rather than
-- automatically publishing an unverified product record".
--
-- So the agent tier writes DRAFTS. A human publishes. That is the whole
-- design, and everything below exists to make it a property of the
-- database rather than a habit of the code.
--
-- ---------------------------------------------------------------------
-- 🔴 WHY THIS IS A TRIGGER ON THE WRITER'S IDENTITY, NOT A CHECK IN A
--    SERVICE FUNCTION
-- ---------------------------------------------------------------------
--
-- This repository has the lesson written down: when a function cannot
-- identify its caller, no check inside it can authorize the call. A guard
-- in Python is a MISUSE BARRIER — it stops the tool being used wrongly by
-- someone reading the code, and stops nothing at all if a different code
-- path, a future route, or an injected statement writes the same row.
--
-- `session_user` is not settable. `SET ROLE` changes `current_user` and
-- leaves `session_user` alone, and `SET SESSION AUTHORIZATION` requires
-- superuser. So the identity this trigger reads is the CONNECTION —
-- exactly the mechanism ADR-032 chose in 053, and the same one 059 used to
-- keep the anonymous reader away from tenant rows.
--
-- ⚠️ IT READS BOTH `current_user` AND `session_user`, DELIBERATELY.
-- `session_user` is what makes it unescapable for a real agent connection.
-- `current_user` is what makes it TESTABLE: a superuser running the probe
-- below can `SET ROLE evercoat_agent` and be refused, so the trigger is
-- falsified here rather than assumed to work. Checking only one would
-- either be untestable or escapable.
--
-- ---------------------------------------------------------------------
-- ⚠️ THE ROLE IS NOLOGIN, LIKE 001, 053 AND 059
-- ---------------------------------------------------------------------
-- Granting LOGIN and a password is the deployment's job. And as ever,
-- `CREATE ROLE IF NOT EXISTS` is idempotent about existence and silent
-- about capability, so the attributes are normalised unconditionally.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1. The role
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'evercoat_agent') THEN
        CREATE ROLE evercoat_agent NOLOGIN;
    END IF;
END
$$;

ALTER ROLE evercoat_agent
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION NOINHERIT;

ALTER ROLE evercoat_agent SET search_path = public_intel, pg_catalog;

-- ---------------------------------------------------------------------
-- 2. The boundary
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public_intel.agent_writes_are_drafts()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- Not `current_user` alone: `SET ROLE` would step around it. Not
    -- `session_user` alone: the probe in the migration wrapper could not
    -- then exercise it. Both, so it is neither escapable nor untestable.
    IF current_user = 'evercoat_agent' OR session_user = 'evercoat_agent' THEN
        IF NEW.publication_status <> 'draft' THEN
            RAISE EXCEPTION
                'an agent may only write drafts: % attempted publication_status=%',
                current_user, NEW.publication_status
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        -- An agent must not claim a human reviewed something. `reviewed_by`
        -- is what the publication invariant reads to accept a 'verified'
        -- row, so an agent able to set it could manufacture the evidence
        -- for its own publication later.
        IF NEW.reviewed_by IS NOT NULL OR NEW.reviewed_at IS NOT NULL THEN
            RAISE EXCEPTION
                'an agent may not record a review: % set reviewed_by/reviewed_at',
                current_user
                USING ERRCODE = 'insufficient_privilege';
        END IF;
    END IF;
    RETURN NEW;
END
$$;

ALTER FUNCTION public_intel.agent_writes_are_drafts() OWNER TO evercoat_owner;

DROP TRIGGER IF EXISTS agent_writes_are_drafts ON public_intel.manufacturers;
CREATE TRIGGER agent_writes_are_drafts
    BEFORE INSERT OR UPDATE ON public_intel.manufacturers
    FOR EACH ROW EXECUTE FUNCTION public_intel.agent_writes_are_drafts();

DROP TRIGGER IF EXISTS agent_writes_are_drafts ON public_intel.products;
CREATE TRIGGER agent_writes_are_drafts
    BEFORE INSERT OR UPDATE ON public_intel.products
    FOR EACH ROW EXECUTE FUNCTION public_intel.agent_writes_are_drafts();

DROP TRIGGER IF EXISTS agent_writes_are_drafts ON public_intel.news_items;
CREATE TRIGGER agent_writes_are_drafts
    BEFORE INSERT OR UPDATE ON public_intel.news_items
    FOR EACH ROW EXECUTE FUNCTION public_intel.agent_writes_are_drafts();

-- `product_documents` has no reviewer columns, so it gets the draft half
-- only. A separate function rather than a branch on TG_TABLE_NAME: a
-- function that behaved differently depending on which table invoked it is
-- one edit away from applying the wrong half to the wrong table.
CREATE OR REPLACE FUNCTION public_intel.agent_documents_are_drafts()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF (current_user = 'evercoat_agent' OR session_user = 'evercoat_agent')
       AND NEW.publication_status <> 'draft' THEN
        RAISE EXCEPTION
            'an agent may only write drafts: % attempted publication_status=%',
            current_user, NEW.publication_status
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$$;

ALTER FUNCTION public_intel.agent_documents_are_drafts() OWNER TO evercoat_owner;

DROP TRIGGER IF EXISTS agent_writes_are_drafts ON public_intel.product_documents;
CREATE TRIGGER agent_writes_are_drafts
    BEFORE INSERT OR UPDATE ON public_intel.product_documents
    FOR EACH ROW EXECUTE FUNCTION public_intel.agent_documents_are_drafts();

-- ---------------------------------------------------------------------
-- 3. Privileges
-- ---------------------------------------------------------------------
--
-- 🔴 REVOKE FROM PUBLIC BEFORE GRANTING, as 047 and 053 both had to learn.
REVOKE ALL ON FUNCTION public_intel.agent_writes_are_drafts() FROM PUBLIC;
REVOKE ALL ON FUNCTION public_intel.agent_documents_are_drafts() FROM PUBLIC;

GRANT USAGE ON SCHEMA public_intel TO evercoat_agent;

GRANT SELECT, INSERT, UPDATE ON
      public_intel.manufacturers,
      public_intel.products,
      public_intel.product_documents,
      public_intel.news_items,
      public_intel.news_sources
   TO evercoat_agent;

GRANT SELECT ON public_intel.news_categories TO evercoat_agent;

-- ⚠️ NO DELETE, ANYWHERE. An agent that could delete could remove the
-- record of what it previously proposed, which is the audit trail a
-- reviewer needs to judge it.
--
-- ⚠️ AND NOTHING AT ALL ON `access_requests`. Those rows are people's names
-- and work addresses, submitted by members of the public. No agent has any
-- business reading them.

COMMIT;
