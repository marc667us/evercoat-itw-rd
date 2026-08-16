-- 001_core_tenancy.sql
-- =====================================================================
-- EvercoatITWRD APP — Slice 1 foundation: roles, schemas, tenancy, RLS.
--
-- This is the migration the whole build rests on. Both reviewers named
-- the authorization and tenancy model as the highest-risk decision in
-- the project (Codex Q3): if it is wrong, every table, analytics view,
-- materialized view, search index, MSD retrieval path, cache, document
-- link and model dataset needs retrofitting, and by Slice 12 the wrong
-- assumption is embedded across DOE, RAG, modeling and reporting.
--
-- It therefore lands first, not last.
--
-- Pattern reused from Solar PV Designer Lite migrations 003/015/018-020
-- (ADR-022): GUC-based context, four-part split so a half-apply leaves
-- a defined state, permissive parallel-run policy, hard FORCE cutover
-- deferred to a later migration, fully idempotent.
--
-- EXTENDED beyond Solar in three ways that Solar did not need:
--
--   1. TWO context GUCs, not one. Solar scopes to tenant only, which is
--      correct for an installer whose staff may all see company work.
--      Here a Chemist who is not on project RDP-019 must not see that
--      project's formulations, and Concept Note §36 requires
--      resource-level access control, not organization isolation alone.
--      Organization RLS + application-only project scope would make the
--      "three independent layers" claim false (Codex F32, BLOCKER).
--
--   2. COMPOSITE tenant-qualified keys. RLS stops cross-tenant reads;
--      it does NOT stop cross-tenant references, because referential
--      integrity bypasses RLS even under FORCE (Codex F14). Every
--      tenant-scoped table therefore declares UNIQUE (id, organization_id)
--      and every child->parent FK carries both columns.
--
--      That unique constraint is mandatory, not an optimisation:
--      PostgreSQL requires a unique index on the referenced columns, so
--      without it a composite FK fails outright with "there is no unique
--      constraint matching given keys for referenced table" (Supervisor
--      S7). The predictable reaction under time pressure is to drop the
--      composite FK — which is the exact defect the rule prevents.
--
--   3. SHA-256 audit hash chain from row one, not bolted on later
--      (Codex F22, Solar migration 016).
--
-- PARTS
--   1  Extensions and database roles
--   2  Logical schemas
--   3  Session-context helpers (the GUC layer)
--   4  Core tables — organizations, users, roles, permissions, membership
--   5  Projects and project membership (the resource-scope anchor)
--   6  Audit with hash chain
--   7  RLS policies — organization AND project membership
--   8  Grants
--
-- Idempotent throughout: IF NOT EXISTS / DROP ... IF EXISTS. The same
-- file ships to development, staging and production.
--
-- NOT in this migration, deliberately: FORCE ROW LEVEL SECURITY. Like
-- Solar, the hard cut is a separate migration once the application is
-- proven to set context on every path. A permissive parallel-run policy
-- here means a missing GUC fails open during Slice 1 development and
-- fails CLOSED from the cutover onward — see 0NN_force_rls.sql.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- PART 1 — Extensions and roles
-- ---------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid, digest
CREATE EXTENSION IF NOT EXISTS citext;     -- case-insensitive email

-- Five roles, separating DDL from runtime (ADR-017). An earlier draft
-- wrongly required migrations to run as the runtime role; that needs DDL
-- privileges the runtime must never hold (Codex F19).
DO $$
BEGIN
    -- Owner: schema owner, DDL and migrations only. Never used by the app.
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'evercoat_owner') THEN
        CREATE ROLE evercoat_owner NOLOGIN;
    END IF;

    -- Runtime: the application. Non-superuser, subject to FORCE RLS.
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'evercoat_app') THEN
        CREATE ROLE evercoat_app NOLOGIN;
    END IF;

    -- Worker: Celery — scheduler, notifications, analytics refresh.
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'evercoat_worker') THEN
        CREATE ROLE evercoat_worker NOLOGIN;
    END IF;

    -- Reporting: read-only analytics. Still RLS-subject — a reporting
    -- role that bypasses RLS is a cross-tenant aggregate waiting to
    -- happen (Codex F20).
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'evercoat_report') THEN
        CREATE ROLE evercoat_report NOLOGIN;
    END IF;

    -- Break-glass: audited emergency access. No login by default.
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'evercoat_breakglass') THEN
        CREATE ROLE evercoat_breakglass NOLOGIN;
    END IF;
END
$$;


-- ---------------------------------------------------------------------
-- PART 2 — Logical schemas
-- ---------------------------------------------------------------------
-- Sixteen schemas, each with a declared owner (ADR-011). Master §37 says
-- "such as" and is non-exhaustive, so the union is permitted — but
-- namespace count without ownership boundaries is complexity for
-- nothing (Codex F23), so ownership is declared here, not deferred.

CREATE SCHEMA IF NOT EXISTS core         AUTHORIZATION evercoat_owner;
CREATE SCHEMA IF NOT EXISTS innovation   AUTHORIZATION evercoat_owner;
CREATE SCHEMA IF NOT EXISTS projects     AUTHORIZATION evercoat_owner;
CREATE SCHEMA IF NOT EXISTS materials    AUTHORIZATION evercoat_owner;
CREATE SCHEMA IF NOT EXISTS formulations AUTHORIZATION evercoat_owner;
CREATE SCHEMA IF NOT EXISTS laboratory   AUTHORIZATION evercoat_owner;
CREATE SCHEMA IF NOT EXISTS testing      AUTHORIZATION evercoat_owner;
CREATE SCHEMA IF NOT EXISTS workflow     AUTHORIZATION evercoat_owner;
CREATE SCHEMA IF NOT EXISTS quality      AUTHORIZATION evercoat_owner;
CREATE SCHEMA IF NOT EXISTS products     AUTHORIZATION evercoat_owner;
CREATE SCHEMA IF NOT EXISTS knowledge    AUTHORIZATION evercoat_owner;
CREATE SCHEMA IF NOT EXISTS messaging    AUTHORIZATION evercoat_owner;
CREATE SCHEMA IF NOT EXISTS analytics    AUTHORIZATION evercoat_owner;
CREATE SCHEMA IF NOT EXISTS modeling     AUTHORIZATION evercoat_owner;
CREATE SCHEMA IF NOT EXISTS ai           AUTHORIZATION evercoat_owner;
CREATE SCHEMA IF NOT EXISTS audit        AUTHORIZATION evercoat_owner;


-- ---------------------------------------------------------------------
-- PART 3 — Session context
-- ---------------------------------------------------------------------
-- Two GUCs. Solar carries one; the second is what makes resource-level
-- authorization enforceable in the database rather than only in FastAPI.
--
-- Both MUST be set with SET LOCAL inside a transaction, never SET.
-- A plain SET persists on a pooled connection and leaks the previous
-- request's identity into the next one — the classic way RLS silently
-- fails (Codex F34). The application's session dependency asserts this.

CREATE OR REPLACE FUNCTION core.current_org_id() RETURNS UUID
    LANGUAGE plpgsql STABLE AS $$
DECLARE
    v TEXT;
BEGIN
    -- 'true' = missing_ok: return NULL rather than raising when unset.
    v := current_setting('app.current_org', true);
    IF v IS NULL OR v = '' THEN
        RETURN NULL;
    END IF;
    RETURN v::UUID;
EXCEPTION WHEN invalid_text_representation THEN
    -- A malformed GUC must never be read as "no restriction". Treat a
    -- corrupt value as no organization, which denies everything once
    -- FORCE RLS is on.
    RETURN NULL;
END
$$;

CREATE OR REPLACE FUNCTION core.current_user_id() RETURNS UUID
    LANGUAGE plpgsql STABLE AS $$
DECLARE
    v TEXT;
BEGIN
    v := current_setting('app.current_user_id', true);
    IF v IS NULL OR v = '' THEN
        RETURN NULL;
    END IF;
    RETURN v::UUID;
EXCEPTION WHEN invalid_text_representation THEN
    RETURN NULL;
END
$$;

-- Parallel-run switch. While TRUE (Slice 1 development), a missing GUC
-- means "no restriction" so the stack is usable before every code path
-- sets context. The FORCE cutover migration sets it FALSE permanently
-- and the policies below then deny by default.
CREATE OR REPLACE FUNCTION core.rls_permissive() RETURNS BOOLEAN
    LANGUAGE sql IMMUTABLE AS $$ SELECT TRUE $$;


-- ---------------------------------------------------------------------
-- PART 4 — Core tables
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS core.organizations (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code         TEXT        NOT NULL,
    name         TEXT        NOT NULL,
    status       TEXT        NOT NULL DEFAULT 'active'
                 CHECK (status IN ('active', 'inactive', 'archived')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT organizations_code_key UNIQUE (code)
);

CREATE TABLE IF NOT EXISTS core.users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    keycloak_sub    TEXT        NOT NULL,
    email           CITEXT      NOT NULL,
    display_name    TEXT        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'inactive', 'archived')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Keycloak owns credentials; there is deliberately no password column.
    CONSTRAINT users_keycloak_sub_key UNIQUE (keycloak_sub),
    CONSTRAINT users_email_key        UNIQUE (email)
);

-- Permissions are the unit of authorization. Roles are seeded bundles.
-- Authorizing on role names cannot express "QA approval may not come
-- from someone who gave a development-side approval" (ADR-019).
CREATE TABLE IF NOT EXISTS core.permissions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        TEXT NOT NULL,   -- e.g. 'formula.approve_lab', 'test.confirm'
    domain      TEXT NOT NULL,   -- e.g. 'formula', 'test', 'admin'
    description TEXT NOT NULL,
    CONSTRAINT permissions_code_key UNIQUE (code)
);

CREATE TABLE IF NOT EXISTS core.roles (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code         TEXT    NOT NULL,   -- matches the Keycloak realm role
    name         TEXT    NOT NULL,
    is_seeded    BOOLEAN NOT NULL DEFAULT FALSE,
    description  TEXT,
    CONSTRAINT roles_code_key UNIQUE (code)
);

CREATE TABLE IF NOT EXISTS core.role_permissions (
    role_id       UUID NOT NULL REFERENCES core.roles(id)       ON DELETE RESTRICT,
    permission_id UUID NOT NULL REFERENCES core.permissions(id) ON DELETE RESTRICT,
    PRIMARY KEY (role_id, permission_id)
);

-- Organization membership carries the roles. A user may belong to more
-- than one organization with different roles in each.
CREATE TABLE IF NOT EXISTS core.organization_members (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
    user_id         UUID NOT NULL REFERENCES core.users(id)         ON DELETE RESTRICT,
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'inactive')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT organization_members_unique UNIQUE (organization_id, user_id),
    -- The mandatory composite candidate key. Without this, composite FKs
    -- into this table are impossible (Supervisor S7).
    CONSTRAINT organization_members_id_org_key UNIQUE (id, organization_id)
);

CREATE TABLE IF NOT EXISTS core.member_roles (
    member_id UUID NOT NULL REFERENCES core.organization_members(id) ON DELETE RESTRICT,
    role_id   UUID NOT NULL REFERENCES core.roles(id)                ON DELETE RESTRICT,
    PRIMARY KEY (member_id, role_id)
);


-- ---------------------------------------------------------------------
-- PART 5 — Projects and project membership
-- ---------------------------------------------------------------------
-- Project membership is the resource-scope anchor. Every project-scoped
-- table in every later slice — formulas, batches, tests, failures, DOE,
-- validation, pilot — inherits its RLS predicate from this table.

CREATE TABLE IF NOT EXISTS projects.projects (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
    project_code        TEXT NOT NULL,              -- RDP-2026-014
    name                TEXT NOT NULL,
    product_family      TEXT,
    status              TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','active','on_hold','completed','cancelled')),
    -- Confidentiality classification is enforced in the database, not
    -- only in the API (ADR-016). 'restricted' means members only, even
    -- for users who would otherwise have org-wide read.
    confidentiality     TEXT NOT NULL DEFAULT 'normal'
                        CHECK (confidentiality IN ('normal','restricted')),
    current_stage       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT projects_org_code_key UNIQUE (organization_id, project_code),
    CONSTRAINT projects_id_org_key   UNIQUE (id, organization_id)
);

CREATE TABLE IF NOT EXISTS projects.project_members (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id      UUID NOT NULL,
    user_id         UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    project_role    TEXT NOT NULL
                    CHECK (project_role IN ('lead','chemist','engineer','technician',
                                            'qa','director','observer')),
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','inactive')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT project_members_unique UNIQUE (project_id, user_id),
    CONSTRAINT project_members_id_org_key UNIQUE (id, organization_id),
    -- THE COMPOSITE FK. Both columns, so a project_member row cannot
    -- reference a project in another organization. This is the pattern
    -- every child table in every later slice repeats.
    CONSTRAINT project_members_project_fk
        FOREIGN KEY (project_id, organization_id)
        REFERENCES projects.projects (id, organization_id)
        ON DELETE RESTRICT
);

-- Membership predicate, used by every project-scoped RLS policy from
-- here to Slice 20. Defined once so the rule cannot drift between
-- tables — the "two literals in two files" trap applied to security.
CREATE OR REPLACE FUNCTION core.is_project_member(p_project_id UUID) RETURNS BOOLEAN
    LANGUAGE sql STABLE SECURITY DEFINER
    -- SECURITY DEFINER so the predicate can read project_members without
    -- recursing through project_members' own policy. It does NOT exempt
    -- anything from FORCE RLS elsewhere.
    SET search_path = projects, core, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM projects.project_members pm
        WHERE pm.project_id = p_project_id
          AND pm.user_id    = core.current_user_id()
          AND pm.status     = 'active'
    )
$$;


-- ---------------------------------------------------------------------
-- PART 6 — Audit, with a SHA-256 hash chain
-- ---------------------------------------------------------------------
-- Reused from Solar migration 016 (ADR-022 / REUSE.md R2). An
-- application-level append-only convention is bypassable by SQL,
-- scripts, failed code paths and compromised service credentials
-- (Codex F22). The chain makes tampering detectable rather than merely
-- discouraged: editing any row invalidates its own row_hash AND breaks
-- every subsequent link; deleting a row breaks the chain at the next
-- row. The verifier walks id ASC and reports the first break.
--
-- Both PostgreSQL (here) and the Python writer compute the hash from
-- the same canonical serialisation, so each side can verify the other.

CREATE TABLE IF NOT EXISTS audit.events (
    id               BIGSERIAL PRIMARY KEY,
    organization_id  UUID,
    user_id          UUID,
    role_code        TEXT,
    action           TEXT        NOT NULL,
    entity_type      TEXT        NOT NULL,
    entity_id        TEXT,
    previous_state   JSONB,
    new_state        JSONB,
    reason           TEXT,
    session_id       TEXT,
    ip_address       INET,
    occurred_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    prev_hash        TEXT        NOT NULL,
    row_hash         TEXT        NOT NULL,
    -- Nothing will ever reference audit.events with a composite FK -- it
    -- is an append-only log, not a parent. The constraint is here anyway
    -- so the rule "every table carrying organization_id declares
    -- UNIQUE (id, organization_id)" holds without exception. A rule with
    -- an exception list is a rule people erode, and the invariant is
    -- cheap to keep uniform. The tenancy test asserts it globally rather
    -- than maintaining a skip list.
    CONSTRAINT events_id_org_key UNIQUE (id, organization_id)
);

-- Canonical content: pipe-joined, COALESCE-to-empty-string. Column order
-- here is part of the contract — the Python writer must serialise these
-- fields in exactly this order or the two sides disagree and every row
-- reads as tampered.
CREATE OR REPLACE FUNCTION audit.canonical_content(
    p_organization_id UUID, p_user_id UUID, p_role_code TEXT,
    p_action TEXT, p_entity_type TEXT, p_entity_id TEXT,
    p_previous_state JSONB, p_new_state JSONB, p_reason TEXT,
    p_occurred_at TIMESTAMPTZ
) RETURNS TEXT LANGUAGE sql IMMUTABLE AS $$
    SELECT concat_ws('|',
        COALESCE(p_organization_id::TEXT, ''),
        COALESCE(p_user_id::TEXT, ''),
        COALESCE(p_role_code, ''),
        COALESCE(p_action, ''),
        COALESCE(p_entity_type, ''),
        COALESCE(p_entity_id, ''),
        COALESCE(p_previous_state::TEXT, ''),
        COALESCE(p_new_state::TEXT, ''),
        COALESCE(p_reason, ''),
        -- Fixed format: a locale-dependent timestamp rendering would
        -- make the hash unreproducible across hosts.
        COALESCE(to_char(p_occurred_at AT TIME ZONE 'UTC',
                         'YYYY-MM-DD"T"HH24:MI:SS.US'), '')
    )
$$;

CREATE OR REPLACE FUNCTION audit.chain_row() RETURNS TRIGGER
    LANGUAGE plpgsql AS $$
DECLARE
    v_prev TEXT;
BEGIN
    -- Serialise chain construction. Without this, two concurrent inserts
    -- can both read the same tail and produce a fork that the verifier
    -- reports as tampering.
    PERFORM pg_advisory_xact_lock(hashtext('audit.events.chain'));

    SELECT row_hash INTO v_prev
    FROM audit.events
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

DROP TRIGGER IF EXISTS audit_events_chain ON audit.events;
CREATE TRIGGER audit_events_chain
    BEFORE INSERT ON audit.events
    FOR EACH ROW EXECUTE FUNCTION audit.chain_row();

-- Append-only, enforced by the database rather than by convention.
CREATE OR REPLACE FUNCTION audit.deny_mutation() RETURNS TRIGGER
    LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION
        'audit.events is append-only; % is not permitted', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END
$$;

DROP TRIGGER IF EXISTS audit_events_no_update ON audit.events;
CREATE TRIGGER audit_events_no_update
    BEFORE UPDATE OR DELETE ON audit.events
    FOR EACH ROW EXECUTE FUNCTION audit.deny_mutation();


-- ---------------------------------------------------------------------
-- PART 7 — RLS policies
-- ---------------------------------------------------------------------
-- Organization isolation AND project membership. Organization alone
-- would leave a colleague inside the same company protected from
-- another team's proprietary formulations by application code only
-- (Codex F32, BLOCKER).
--
-- FORCE is deliberately NOT set here — see the header.

ALTER TABLE core.organizations        ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects.projects         ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects.project_members  ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit.events              ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS org_isolation ON core.organizations;
CREATE POLICY org_isolation ON core.organizations
    USING (core.rls_permissive() AND core.current_org_id() IS NULL
           OR id = core.current_org_id());

DROP POLICY IF EXISTS org_member_isolation ON core.organization_members;
CREATE POLICY org_member_isolation ON core.organization_members
    USING (core.rls_permissive() AND core.current_org_id() IS NULL
           OR organization_id = core.current_org_id());

-- Projects: in-organization AND (not restricted OR a member).
DROP POLICY IF EXISTS project_scope ON projects.projects;
CREATE POLICY project_scope ON projects.projects
    USING (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR (
            organization_id = core.current_org_id()
            AND (
                confidentiality = 'normal'
                OR core.is_project_member(id)
            )
        )
    );

DROP POLICY IF EXISTS project_member_scope ON projects.project_members;
CREATE POLICY project_member_scope ON projects.project_members
    USING (core.rls_permissive() AND core.current_org_id() IS NULL
           OR organization_id = core.current_org_id());

-- Audit is readable only within the organization, and never mutable.
DROP POLICY IF EXISTS audit_org_isolation ON audit.events;
CREATE POLICY audit_org_isolation ON audit.events
    FOR SELECT
    USING (core.rls_permissive() AND core.current_org_id() IS NULL
           OR organization_id = core.current_org_id());

DROP POLICY IF EXISTS audit_insert ON audit.events;
CREATE POLICY audit_insert ON audit.events
    FOR INSERT WITH CHECK (true);


-- ---------------------------------------------------------------------
-- PART 8 — Grants
-- ---------------------------------------------------------------------
-- Least privilege. The runtime role gets DML on data schemas, INSERT
-- only on audit, and no DDL anywhere.

GRANT USAGE ON SCHEMA core, innovation, projects, materials, formulations,
    laboratory, testing, workflow, quality, products, knowledge, messaging,
    analytics, modeling, ai, audit
    TO evercoat_app, evercoat_worker, evercoat_report;

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA core, projects
    TO evercoat_app;
GRANT SELECT ON ALL TABLES IN SCHEMA core, projects
    TO evercoat_worker, evercoat_report;

-- Audit: insert only. UPDATE/DELETE are additionally blocked by trigger,
-- so a grant mistake alone cannot make audit mutable.
GRANT INSERT, SELECT ON audit.events TO evercoat_app, evercoat_worker;
GRANT SELECT ON audit.events TO evercoat_report;
GRANT USAGE, SELECT ON SEQUENCE audit.events_id_seq
    TO evercoat_app, evercoat_worker;

-- Future tables inherit these grants, so a later migration cannot
-- accidentally ship a table the app cannot read.
ALTER DEFAULT PRIVILEGES FOR ROLE evercoat_owner IN SCHEMA core, projects
    GRANT SELECT, INSERT, UPDATE ON TABLES TO evercoat_app;
ALTER DEFAULT PRIVILEGES FOR ROLE evercoat_owner IN SCHEMA core, projects
    GRANT SELECT ON TABLES TO evercoat_worker, evercoat_report;

COMMIT;

-- =====================================================================
-- Verified by tests/db/test_001_core_tenancy.py, which asserts:
--   * every tenant-scoped table declares UNIQUE (id, organization_id)
--   * every FK into a tenant-scoped table is composite
--   * a cross-organization project_members insert is REJECTED by the FK
--   * a restricted project is invisible to a non-member under SET ROLE
--   * audit UPDATE and DELETE both raise
--   * breaking a row's content invalidates the chain from that row on
--   * a plain SET (not SET LOCAL) of app.current_org fails the pool test
-- A migration that only works as superuser is a latent production
-- failure, so the suite runs under SET ROLE evercoat_app.
-- =====================================================================
