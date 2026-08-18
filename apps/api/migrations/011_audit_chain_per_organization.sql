-- 011_audit_chain_per_organization.sql
-- =====================================================================
-- Make the audit hash chain per-organization BY CONSTRUCTION rather than
-- by accident, and stop an unscoped writer splicing one tenant's chain
-- onto another's.
--
-- WHAT THE PREVIOUS RECORD SAID, AND WHY IT WAS WRONG
-- ---------------------------------------------------
-- TODO.md recorded this as "a single GLOBAL hash chain" that "forks under
-- concurrency", because "two transactions that each read the tail before
-- either commits will both write prev_hash = 'GENESIS'".
--
-- The SYMPTOM was observed correctly. The CAUSE was not, and the fix that
-- follows from the wrong cause is the wrong fix.
--
-- audit.chain_row() already takes pg_advisory_xact_lock(), which is
-- TRANSACTION-scoped: a second writer blocks until the first COMMITs or
-- ROLLBACKs. Under READ COMMITTED the tail SELECT that runs after the
-- lock is acquired takes a fresh snapshot, so it sees the row the first
-- writer just committed. Concurrency alone cannot fork this chain.
--
-- The real mechanism is ROW LEVEL SECURITY. audit.chain_row() is
-- SECURITY INVOKER, so its tail read --
--
--     SELECT row_hash FROM audit.events ORDER BY id DESC LIMIT 1
--
-- -- is filtered by the audit_org_isolation policy from migration 001.
-- A writer with app.current_org set therefore sees ONLY ITS OWN
-- organization's rows and chains onto its own tail. The chain has been
-- per-organization all along; nobody wrote that down because nobody
-- chose it.
--
-- Measured on a live database (six interleaved inserts, one per line):
--
--     label     id    org        prev_hash points at
--     A1       681   org A       GENESIS
--     B1       682   org B       GENESIS      <- org B starts its own chain
--     A2       683   org A       A1           <- skips B1 entirely
--     B2       684   org B       B1
--     UNSCOPED 685   NULL        B2           <- splices across chains
--     A3       686   org A       A2
--
-- TWO CONSEQUENCES, and the second is the actual defect:
--
--   1. A GLOBAL walk of the table reports a break at the first row of the
--      second organization. That is not tampering; it is two independent
--      chains interleaved in one id sequence. Any verifier that walks the
--      whole table raises a false alarm, and a tamper alarm that cries
--      wolf is one that stops being read.
--
--   2. A writer with NO organization context -- a migration, a backfill,
--      a maintenance script, anything using unscoped_session_scope() --
--      falls through to the permissive branch of the policy, sees EVERY
--      row, and chains onto whichever organization happened to write
--      last. Row 685 above did exactly that. That splice is
--      NON-DETERMINISTIC: it depends on inter-tenant write interleaving,
--      so the same sequence of application actions produces a different
--      chain shape on every run, and the row it lands after belongs to a
--      tenant that had nothing to do with it.
--
-- THE FIX
-- -------
-- Three changes, each closing one route to a chain whose shape depends on
-- WHO IS LOOKING rather than on what was written.
--
--   * Name the organization in the tail read. The chain is per
--     organization because the query says so, not because a policy
--     happened to hide the other rows. IS NOT DISTINCT FROM, not `=`,
--     because system rows carry organization_id IS NULL and must form
--     their own chain rather than attaching to an arbitrary tenant's.
--
--   * SECURITY DEFINER on chain_row(), so the tail read no longer depends
--     on the caller's RLS context at all. Without this, a session scoped
--     to org A that inserts a row for org B would find org B's tail
--     hidden and silently restart that chain at GENESIS.
--
--   * A real WITH CHECK on the insert policy. It was `true`, which let a
--     session scoped to one organization write audit rows attributed to
--     another -- forging entries in someone else's tamper-evident log.
--     Unscoped writers are still permitted (that is how migrations and
--     the system actor write), and NULL-organization system rows remain
--     legal; what is refused is a SCOPED session claiming a DIFFERENT
--     organization.
--
-- THE DISCONTINUITY THIS MIGRATION ITSELF INTRODUCES
-- --------------------------------------------------
-- Rows written BEFORE this migration were chained under the old rule. For
-- scoped writers the old and new rules agree, so those rows continue to
-- verify. They disagree exactly where an UNSCOPED writer spliced across
-- organizations: such a row's prev_hash names a row in a different
-- organization's chain, and a per-organization walk cannot reproduce it.
--
-- Those rows are NOT rewritten. audit.events is append-only and
-- retro-fitting hashes to make a verifier happy is precisely the tampering
-- the chain exists to detect. Instead the boundary is recorded as an audit
-- event of its own (below), so a break found at a pre-boundary row can be
-- read as a known regime change rather than as an attack.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- PART 0 — audit.events must be OWNED by evercoat_owner
-- ---------------------------------------------------------------------
-- Added after CI caught what a developer machine could not.
--
-- Migration 001 creates the schemas `AUTHORIZATION evercoat_owner`, but the
-- TABLES inside them are created by whoever runs the migration — the
-- `postgres` superuser — and schema ownership is not table ownership. So on
-- a FRESH database `audit.events` is owned by the migration role, while on
-- this project's long-lived development database it had come to be owned by
-- `evercoat_owner`. The two environments disagreed, silently.
--
-- That matters here specifically because PART 1 makes `chain_row()`
-- SECURITY DEFINER owned by `evercoat_owner`. On a fresh database that
-- function then could not read the table at all:
--
--     psycopg.errors.InsufficientPrivilege: permission denied for table events
--
-- A bare GRANT SELECT would silence that error and quietly destroy the
-- point of the change. A non-owner is subject to RLS, so the tail read
-- would be filtered by the CALLER's organization context again — which is
-- exactly the context-dependence this migration exists to remove. The
-- guarantee needs ownership, not permission.
--
-- Idempotent: re-assigning an owner that is already the owner is a no-op,
-- so this is safe on the development database where it already holds.
ALTER TABLE audit.events OWNER TO evercoat_owner;

-- ---------------------------------------------------------------------
-- PART 1 — Chain per organization, explicitly
-- ---------------------------------------------------------------------

CREATE OR REPLACE FUNCTION audit.chain_row() RETURNS TRIGGER
    LANGUAGE plpgsql
    SECURITY DEFINER
    -- Pinned so a caller-supplied search_path cannot redirect the
    -- audit.events reference or the digest() call in a SECURITY DEFINER
    -- function. Standard hardening; without it this function is a
    -- privilege-escalation surface.
    SET search_path = pg_catalog, audit, public
    AS $$
DECLARE
    v_prev TEXT;
BEGIN
    -- Serialise chain construction PER ORGANIZATION. Two organizations
    -- build independent chains and have no reason to block each other;
    -- two writers within one organization must not interleave.
    --
    -- The two-argument form keys the lock on the organization. NULL (the
    -- system chain) hashes to its own key rather than colliding with a
    -- tenant's.
    PERFORM pg_advisory_xact_lock(
        hashtext('audit.events.chain'),
        hashtext(COALESCE(NEW.organization_id::TEXT, '<system>'))
    );

    -- The predicate is what makes this per-organization. Previously the
    -- same effect arose only because RLS hid the other rows, which meant
    -- the chain's shape depended on the writer's session context.
    SELECT row_hash INTO v_prev
    FROM audit.events
    WHERE organization_id IS NOT DISTINCT FROM NEW.organization_id
    ORDER BY id DESC
    LIMIT 1;

    NEW.prev_hash := COALESCE(v_prev, 'GENESIS');
    NEW.row_hash := encode(
        digest(
            NEW.prev_hash || '|' || audit.canonical_content(
                NEW.organization_id, NEW.user_id, NEW.role_code,
                NEW.action, NEW.entity_type, NEW.entity_id,
                NEW.previous_state, NEW.new_state, NEW.reason,
                NEW.occurred_at),
            'sha256'),
        'hex');
    RETURN NEW;
END
$$;

-- Owned by the schema owner, not by whoever ran the migration. The
-- migration role is the `postgres` superuser on this host and a
-- deployment role elsewhere; pinning the owner makes the function's
-- effective privileges the same either way.
ALTER FUNCTION audit.chain_row() OWNER TO evercoat_owner;

COMMENT ON FUNCTION audit.chain_row() IS
    'BEFORE INSERT trigger for audit.events. Chains PER ORGANIZATION: '
    'prev_hash resolves against the last row with the same '
    'organization_id (NULL forming its own system chain). SECURITY '
    'DEFINER so the tail read does not depend on the caller''s RLS '
    'context -- under SECURITY INVOKER the chain shape varied with who '
    'was writing, and an unscoped writer spliced across tenants.';

-- ---------------------------------------------------------------------
-- PART 2 — An organization may not write another's audit rows
-- ---------------------------------------------------------------------
-- The old policy was `WITH CHECK (true)`: any session could insert an
-- audit row attributed to any organization. Since audit.events is the
-- record used to establish who did what, that is the ability to forge
-- entries in another tenant's tamper-evident log.

DROP POLICY IF EXISTS audit_insert ON audit.events;
CREATE POLICY audit_insert ON audit.events
    FOR INSERT WITH CHECK (
        -- System rows, written by the platform rather than on behalf of a
        -- tenant. They form their own chain.
        organization_id IS NULL
        -- Unscoped writers: migrations, backfills, the bootstrap path.
        -- These legitimately have no organization context. They are still
        -- constrained by PART 1, which chains them onto the correct
        -- organization's tail rather than onto whoever wrote last.
        OR core.current_org_id() IS NULL
        -- A scoped session may only write its OWN organization's rows.
        OR organization_id = core.current_org_id()
    );

-- ---------------------------------------------------------------------
-- PART 3 — Record the regime change in the log itself
-- ---------------------------------------------------------------------
-- Written through the table's own trigger, so it is chained like any
-- other row. It is a system row (organization_id IS NULL), which means it
-- lands on the system chain and does not interrupt any tenant's.
--
-- The point is that a future investigator who finds a break at a row
-- older than this one can distinguish "the rules changed here, by
-- migration, on purpose" from "somebody altered this row".

INSERT INTO audit.events
    (organization_id, user_id, role_code, action, entity_type, entity_id,
     new_state, reason, prev_hash, row_hash)
VALUES
    (NULL, NULL, NULL, 'audit.chain_regime_change', 'audit.events',
     '011_audit_chain_per_organization',
     '{"chained_by": "organization_id", "previously": "whatever RLS showed the writer"}'::JSONB,
     'Migration 011: chain scope made explicit. Rows written before this '
     'point were chained by whatever audit.chain_row() could SEE under the '
     'writer''s RLS context. For scoped writers that is identical to the '
     'new rule and they still verify. Rows written by an UNSCOPED writer '
     'may name a prev_hash belonging to a different organization; such a '
     'break is this migration, not tampering. Nothing was rewritten -- '
     'editing history to satisfy a verifier is the attack the chain '
     'exists to detect.',
     '', '');

COMMENT ON TABLE audit.events IS
    'Append-only audit log with a SHA-256 hash chain PER ORGANIZATION '
    '(migration 011). Verification must name an organization: a walk of '
    'the whole table sees several independent chains interleaved in one '
    'id sequence and reports their boundaries as breaks.';

COMMIT;
