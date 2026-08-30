-- =====================================================================
-- 059 — A PUBLIC SURFACE IS A SEPARATE CONNECTION, NOT A FLAG
-- =====================================================================
--
-- The owner asked for a public landing page carrying a Global Competitor
-- Product Marketplace and a Global Competitor Industry News Feed, readable
-- by anyone, with sign-up and sign-in.
--
-- This application had NO public surface. Every route was behind
-- `get_principal`, every table tenant-scoped, every policy FORCE RLS.
--
-- ---------------------------------------------------------------------
-- 🔴 WHY THIS IS A NEW SCHEMA AND NOT A FLAG ON `competitors.products`
-- ---------------------------------------------------------------------
--
-- `competitors.products` (056) is tenant-scoped in its bones: NOT NULL
-- `organization_id`, a tenant-qualified unique key, and composite FKs to
-- projects, documents, samples, evidence and benchmarks. Its own comment
-- already refused a global unique key, for the I83 reason:
--
--     "a globally unique one would stop org B registering a product org A
--      already has, and the refusal itself would disclose org A's record"
--
-- Adding `is_global`, or making `organization_id` nullable, would break
-- ADR-014's mandatory tenant-qualified key, every composite child FK, the
-- RLS policies and audit attribution -- and re-open that oracle.
--
-- So the public catalogue is a SEPARATE, NON-TENANTED schema. A tenant may
-- POINT at a public row (`competitors.products.public_product_id`, added
-- below). Nothing copies automatically; drift is reconciled by a reviewed
-- action, never a sync job.
--
-- ---------------------------------------------------------------------
-- 🔴 WHY A SEPARATE SCHEMA AND NOT A SEPARATE DATABASE
-- ---------------------------------------------------------------------
--
-- Raised by Codex: a separate database removes cross-schema joins and most
-- catalog exposure, and is genuinely safer. It was rejected for one
-- concrete reason -- PostgreSQL CANNOT ENFORCE A FOREIGN KEY ACROSS
-- DATABASES, and `public_product_id` is the single referential link
-- between a tenant's private dossier and the public catalogue. Stated as a
-- trade that was measured, not a preference.
--
-- ---------------------------------------------------------------------
-- 🔴 WHY VIEWS, AND WHY `security_invoker` IS **NOT** SET HERE
-- ---------------------------------------------------------------------
--
-- 037 makes `security_invoker = true` load-bearing so `usable_documents`
-- runs as the CALLER and RLS applies per tenant. These views need the
-- OPPOSITE -- the default -- so they run as `evercoat_owner` and
-- `evercoat_public` needs NO privilege on any base table.
--
-- ⚠️ THAT IS ONLY SAFE BECAUSE THESE VIEWS TOUCH NOTHING TENANTED, AND
--    "only" IS DOING REAL WORK. An owner-owned view runs with the owner's
--    privileges, so a LATER JOIN from one of these views to a tenant table
--    would read across every tenant -- anonymously. A comment asking the
--    next person not to do that is not a control, so §6 below asserts it
--    from `pg_depend`: every `public_intel` view depends only on
--    `public_intel` relations. Add a join to `materials.*` and the
--    migration fails.
--
-- ---------------------------------------------------------------------
-- ⚠️ THE ROLE IS CREATED **NOLOGIN**, like 001 and 053
-- ---------------------------------------------------------------------
--
-- LOGIN and a password are the deployment's job (CI `ALTER ROLE`, compose
-- from `.env`). A migration that baked in a password would put a
-- credential in the repository.
--
-- `CREATE ROLE IF NOT EXISTS` is idempotent about EXISTENCE and SILENT
-- ABOUT CAPABILITY, so the attributes are normalised unconditionally.
-- `NOINHERIT` is load-bearing: without it a membership in some group hands
-- this role that group's privileges on a connection that has no tenant.
--
-- ---------------------------------------------------------------------
-- 🔴 PUBLICATION IS AN INVARIANT, NOT A BOOLEAN
-- ---------------------------------------------------------------------
--
-- The first draft of this migration carried
--     CHECK (NOT (synthetic AND published) OR is_demonstration_data)
-- which CANNOT FAIL when `is_demonstration_data` is NULL: the expression
-- evaluates to NULL and PostgreSQL accepts a NULL CHECK. Codex found it.
-- Every column in the invariant is now NOT NULL and the logic is explicit.
-- A row may be published only if it is honest about where it came from.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1. The schema and the role
-- ---------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS public_intel;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'evercoat_public') THEN
        CREATE ROLE evercoat_public NOLOGIN;
    END IF;
END
$$;

ALTER ROLE evercoat_public
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION NOINHERIT;

-- A fixed search_path, so an unqualified name in any future function or
-- default cannot be resolved to something the caller planted.
ALTER ROLE evercoat_public SET search_path = public_intel, pg_catalog;

-- ---------------------------------------------------------------------
-- 2. Provenance — the shape every published row must carry
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
                    WHERE n.nspname = 'public_intel' AND t.typname = 'content_origin') THEN
        CREATE TYPE public_intel.content_origin AS ENUM
            ('synthetic', 'source_derived', 'verified');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
                    WHERE n.nspname = 'public_intel' AND t.typname = 'verification_status') THEN
        CREATE TYPE public_intel.verification_status AS ENUM
            ('unreviewed', 'reviewed', 'verified', 'rejected');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
                    WHERE n.nspname = 'public_intel' AND t.typname = 'publication_status') THEN
        CREATE TYPE public_intel.publication_status AS ENUM
            ('draft', 'published', 'withdrawn');
    END IF;
END
$$;

-- ---------------------------------------------------------------------
-- 3. Tables. No `organization_id` anywhere: these rows have no tenant.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public_intel.manufacturers (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                  TEXT NOT NULL,
    country               TEXT,
    website_url           TEXT,
    -- Provenance. Every column NOT NULL so the invariant cannot be NULL.
    content_origin        public_intel.content_origin      NOT NULL,
    verification_status   public_intel.verification_status NOT NULL DEFAULT 'unreviewed',
    publication_status    public_intel.publication_status  NOT NULL DEFAULT 'draft',
    is_demonstration_data BOOLEAN NOT NULL DEFAULT false,
    source_url            TEXT,
    generated_by          TEXT,
    generated_at          TIMESTAMPTZ,
    reviewed_by           UUID REFERENCES core.users (id) ON DELETE RESTRICT,
    reviewed_at           TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT manufacturers_name_key UNIQUE (name),
    -- 🔴 THE PUBLICATION INVARIANT. Explicit, and every operand NOT NULL.
    CONSTRAINT manufacturers_publication_is_honest CHECK (
        publication_status <> 'published'
        OR (
            (content_origin = 'synthetic'      AND is_demonstration_data)
         OR (content_origin = 'source_derived' AND source_url IS NOT NULL
                                              AND verification_status IN ('reviewed', 'verified'))
         OR (content_origin = 'verified'       AND source_url IS NOT NULL
                                              AND verification_status = 'verified'
                                              AND reviewed_by IS NOT NULL
                                              AND reviewed_at IS NOT NULL)
        )
    )
);

CREATE TABLE IF NOT EXISTS public_intel.products (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manufacturer_id       UUID NOT NULL REFERENCES public_intel.manufacturers (id) ON DELETE RESTRICT,
    product_name          TEXT NOT NULL,
    product_code          TEXT,
    category              TEXT,
    chemistry             TEXT,
    region                TEXT,
    description           TEXT,
    -- Pricing did not exist anywhere before this migration.
    -- ⚠️ NUMERIC, and it must reach the client as a STRING. FastAPI encodes
    -- Decimal as a float, which is how `get_material` broke its own client
    -- on 2026-08-29. The schema asserts the JSON type.
    price_amount          NUMERIC(14, 4),
    price_currency        CHAR(3),          -- ISO code, never a symbol
    price_as_of           DATE,
    price_source_url      TEXT,
    content_origin        public_intel.content_origin      NOT NULL,
    verification_status   public_intel.verification_status NOT NULL DEFAULT 'unreviewed',
    publication_status    public_intel.publication_status  NOT NULL DEFAULT 'draft',
    is_demonstration_data BOOLEAN NOT NULL DEFAULT false,
    source_url            TEXT,
    generated_by          TEXT,
    generated_at          TIMESTAMPTZ,
    reviewed_by           UUID REFERENCES core.users (id) ON DELETE RESTRICT,
    reviewed_at           TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT products_manufacturer_name_key UNIQUE (manufacturer_id, product_name),
    -- A price is a claim like any other: it needs a date and a source, or
    -- it is not shown. A price with no `as_of` is a number with no meaning.
    CONSTRAINT products_price_is_complete CHECK (
        price_amount IS NULL
        OR (price_currency IS NOT NULL AND price_as_of IS NOT NULL)
    ),
    CONSTRAINT products_price_is_not_negative CHECK (
        price_amount IS NULL OR price_amount >= 0
    ),
    CONSTRAINT products_publication_is_honest CHECK (
        publication_status <> 'published'
        OR (
            (content_origin = 'synthetic'      AND is_demonstration_data)
         OR (content_origin = 'source_derived' AND source_url IS NOT NULL
                                              AND verification_status IN ('reviewed', 'verified'))
         OR (content_origin = 'verified'       AND source_url IS NOT NULL
                                              AND verification_status = 'verified'
                                              AND reviewed_by IS NOT NULL
                                              AND reviewed_at IS NOT NULL)
        )
    )
);

CREATE INDEX IF NOT EXISTS products_published_idx
    ON public_intel.products (publication_status, manufacturer_id);

CREATE TABLE IF NOT EXISTS public_intel.product_documents (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id            UUID NOT NULL REFERENCES public_intel.products (id) ON DELETE CASCADE,
    -- The spec's four link kinds, plus the published SDS.
    document_kind         TEXT NOT NULL
        CHECK (document_kind IN ('datasheet', 'label', 'literature', 'sds')),
    title                 TEXT NOT NULL,
    -- 🔴 A URL, NOT BYTES. §14 says one document repository, and that one is
    -- `materials.material_documents`. This table holds PUBLISHED LINKS to a
    -- manufacturer's own public documents; it does not store or scan files
    -- and must never become a second repository.
    url                   TEXT NOT NULL,
    content_origin        public_intel.content_origin      NOT NULL,
    publication_status    public_intel.publication_status  NOT NULL DEFAULT 'draft',
    is_demonstration_data BOOLEAN NOT NULL DEFAULT false,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT product_documents_kind_key UNIQUE (product_id, document_kind, url),
    CONSTRAINT product_documents_publication_is_honest CHECK (
        publication_status <> 'published'
        OR content_origin <> 'synthetic'
        OR is_demonstration_data
    )
);

CREATE TABLE IF NOT EXISTS public_intel.news_sources (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    homepage_url  TEXT,
    source_type   TEXT,
    -- The spec's source governance, ranked like the existing evidence model.
    tier          SMALLINT NOT NULL CHECK (tier BETWEEN 1 AND 4),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT news_sources_name_key UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS public_intel.news_categories (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        TEXT NOT NULL,
    label       TEXT NOT NULL,
    sort_order  SMALLINT NOT NULL DEFAULT 0,
    CONSTRAINT news_categories_slug_key UNIQUE (slug)
);

CREATE TABLE IF NOT EXISTS public_intel.news_items (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id             UUID NOT NULL REFERENCES public_intel.news_sources (id) ON DELETE RESTRICT,
    category_id           UUID NOT NULL REFERENCES public_intel.news_categories (id) ON DELETE RESTRICT,
    headline              TEXT NOT NULL,
    -- ⚠️ THE SUMMARY IS LABELLED AS A SUMMARY, ALWAYS. The spec is explicit:
    -- "AI-generated summaries must be labelled as summaries and should never
    -- replace the original source article."
    summary               TEXT,
    summary_is_ai_generated BOOLEAN NOT NULL DEFAULT false,
    -- The source link is not optional. Storing an article without a way back
    -- to it is how a summary quietly becomes the record.
    source_url            TEXT NOT NULL,
    published_at          TIMESTAMPTZ,
    retrieved_at          TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    region                TEXT,
    country               TEXT,
    -- 🔴 PUBLIC LINKS ONLY. These two FKs are what make the product News tab
    -- and the brand/manufacturer filters real rather than promised. They
    -- point at PUBLIC rows. There is deliberately NO FK to any tenant table:
    -- one would make an anonymous read a tenant read.
    manufacturer_id       UUID REFERENCES public_intel.manufacturers (id) ON DELETE SET NULL,
    product_id            UUID REFERENCES public_intel.products (id) ON DELETE SET NULL,
    relevance_score       NUMERIC(5, 4),
    content_origin        public_intel.content_origin      NOT NULL,
    verification_status   public_intel.verification_status NOT NULL DEFAULT 'unreviewed',
    publication_status    public_intel.publication_status  NOT NULL DEFAULT 'draft',
    is_demonstration_data BOOLEAN NOT NULL DEFAULT false,
    generated_by          TEXT,
    generated_at          TIMESTAMPTZ,
    reviewed_by           UUID REFERENCES core.users (id) ON DELETE RESTRICT,
    reviewed_at           TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT news_items_source_url_key UNIQUE (source_id, source_url),
    CONSTRAINT news_items_relevance_range CHECK (
        relevance_score IS NULL OR (relevance_score >= 0 AND relevance_score <= 1)
    ),
    CONSTRAINT news_items_publication_is_honest CHECK (
        publication_status <> 'published'
        OR (
            (content_origin = 'synthetic'      AND is_demonstration_data)
         OR (content_origin = 'source_derived' AND verification_status IN ('reviewed', 'verified'))
         OR (content_origin = 'verified'       AND verification_status = 'verified'
                                              AND reviewed_by IS NOT NULL
                                              AND reviewed_at IS NOT NULL)
        )
    )
);

CREATE INDEX IF NOT EXISTS news_items_feed_idx
    ON public_intel.news_items (publication_status, published_at DESC);

-- ---------------------------------------------------------------------
-- 4. Access requests — "Sign Up" creates a REQUEST, not an account
-- ---------------------------------------------------------------------
--
-- Keycloak self-registration is off and stays off. Registration into a
-- tenanted R&D system needs an approval path, not an open form. This table
-- is the queue; an administrator holding `admin.users` reads it and uses
-- the EXISTING bind route to create and bind the identity.
--
-- ⚠️ THIS IS AN UNAUTHENTICATED WRITE ON AN API WITH NO RATE LIMITER.
-- That is stated rather than papered over: this repository has no
-- rate-limiting mechanism at all (the only mention is a comment recording
-- its absence, I18). The exposure is bounded -- the row has no side effect
-- and grants nothing until a human acts -- and `source_ip` is recorded so
-- abuse is at least attributable. Writing "rate-limited" here would be a
-- comment asserting a control that does not exist.
CREATE TABLE IF NOT EXISTS public_intel.access_requests (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name     TEXT NOT NULL CHECK (length(btrim(full_name)) BETWEEN 1 AND 200),
    work_email    TEXT NOT NULL CHECK (length(btrim(work_email)) BETWEEN 3 AND 320),
    company       TEXT NOT NULL CHECK (length(btrim(company)) BETWEEN 1 AND 200),
    reason        TEXT CHECK (reason IS NULL OR length(reason) <= 2000),
    status        TEXT NOT NULL DEFAULT 'new'
        CHECK (status IN ('new', 'approved', 'rejected')),
    source_ip     INET,
    user_agent    TEXT CHECK (user_agent IS NULL OR length(user_agent) <= 500),
    decided_by    UUID REFERENCES core.users (id) ON DELETE RESTRICT,
    decided_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS access_requests_status_idx
    ON public_intel.access_requests (status, created_at DESC);

-- ---------------------------------------------------------------------
-- 5. The tenant-side link. ONE nullable column, pointing outward.
-- ---------------------------------------------------------------------
--
-- ⚠️ THE LINK IS ONE-WAY ON PURPOSE. There is no reverse public projection,
-- no public count of how many tenants link a public product, and no public
-- exposure of any tenant product field. Each of those would turn a
-- convenience column into a cross-tenant signal. The column stays under
-- `competitors.products`' existing FORCE RLS policy, untouched here.
ALTER TABLE competitors.products
    ADD COLUMN IF NOT EXISTS public_product_id UUID
        REFERENCES public_intel.products (id) ON DELETE SET NULL;

-- ---------------------------------------------------------------------
-- 6. The published projections
-- ---------------------------------------------------------------------
--
-- `security_invoker` is DELIBERATELY NOT SET -- see the header. These run
-- as `evercoat_owner` so `evercoat_public` needs no base-table privilege.
-- The `published` predicate lives HERE, in the view definition, where a
-- caller cannot argue with it.
--
-- 🔴 Internal columns are projected away, not merely filtered: no
-- `generated_by`, no `reviewed_by`, no `verification_status`. A public
-- reader learns that a row is demonstration data, and nothing about who
-- reviewed it.

CREATE OR REPLACE VIEW public_intel.v_manufacturers AS
    SELECT id, name, country, website_url,
           content_origin, is_demonstration_data
      FROM public_intel.manufacturers
     WHERE publication_status = 'published';

CREATE OR REPLACE VIEW public_intel.v_products AS
    SELECT p.id, p.manufacturer_id, m.name AS manufacturer_name,
           p.product_name, p.product_code, p.category, p.chemistry,
           p.region, p.description,
           p.price_amount, p.price_currency, p.price_as_of, p.price_source_url,
           p.content_origin, p.is_demonstration_data, p.source_url
      FROM public_intel.products p
      JOIN public_intel.manufacturers m ON m.id = p.manufacturer_id
     WHERE p.publication_status = 'published'
       AND m.publication_status = 'published';

CREATE OR REPLACE VIEW public_intel.v_product_documents AS
    SELECT id, product_id, document_kind, title, url,
           content_origin, is_demonstration_data
      FROM public_intel.product_documents
     WHERE publication_status = 'published';

CREATE OR REPLACE VIEW public_intel.v_news_categories AS
    SELECT id, slug, label, sort_order
      FROM public_intel.news_categories;

CREATE OR REPLACE VIEW public_intel.v_news_items AS
    SELECT n.id, n.headline, n.summary, n.summary_is_ai_generated,
           n.source_url, n.published_at, n.region, n.country,
           n.manufacturer_id, n.product_id, n.category_id,
           c.slug AS category_slug, c.label AS category_label,
           s.name AS source_name, s.source_type, s.tier AS source_tier,
           n.content_origin, n.is_demonstration_data
      FROM public_intel.news_items n
      JOIN public_intel.news_categories c ON c.id = n.category_id
      JOIN public_intel.news_sources     s ON s.id = n.source_id
     WHERE n.publication_status = 'published';

-- ---------------------------------------------------------------------
-- 6a. 🔴 OWNERSHIP. THE MOST IMPORTANT STATEMENTS IN THIS FILE.
-- ---------------------------------------------------------------------
--
-- Migrations run as the SUPERUSER (`MIGRATION_DATABASE_URL`), so everything
-- created above is owned by `postgres` unless it is reassigned. The first
-- version of this migration did not reassign it, and the header above
-- claimed the views "run as `evercoat_owner`". THAT WAS FALSE. They ran as
-- the superuser.
--
-- Why that is not cosmetic: these views deliberately do not set
-- `security_invoker`, so they execute with their OWNER's privileges. A
-- superuser-owned view bypasses Row Level Security on everything it reads --
-- including FORCE RLS, which nothing else in this database can bypass. Today
-- they read only `public_intel`, which has no RLS and no tenant, so nothing
-- leaked. But it left the `pg_depend` probe as the only thing between a
-- future join and an anonymous read of every tenant AS SUPERUSER, and it made
-- `evercoat_owner` unable to manage objects in its own database.
--
-- Every other schema here -- core, materials, competitors, safety -- is owned
-- by `evercoat_owner`. So is this one now, and §8 asserts it rather than
-- trusting these lines to have run.
ALTER SCHEMA public_intel OWNER TO evercoat_owner;

DO $$
DECLARE
    obj RECORD;
BEGIN
    FOR obj IN
        SELECT c.relname, c.relkind
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public_intel' AND c.relkind IN ('r', 'v')
    LOOP
        IF obj.relkind = 'r' THEN
            EXECUTE format('ALTER TABLE public_intel.%I OWNER TO evercoat_owner', obj.relname);
        ELSE
            EXECUTE format('ALTER VIEW public_intel.%I OWNER TO evercoat_owner', obj.relname);
        END IF;
    END LOOP;
END
$$;

DO $$
DECLARE
    t RECORD;
BEGIN
    FOR t IN
        SELECT typ.typname FROM pg_type typ
          JOIN pg_namespace n ON n.oid = typ.typnamespace
         WHERE n.nspname = 'public_intel' AND typ.typtype = 'e'
    LOOP
        EXECUTE format('ALTER TYPE public_intel.%I OWNER TO evercoat_owner', t.typname);
    END LOOP;
END
$$;

-- ---------------------------------------------------------------------
-- 7. Privileges. REVOKE FROM PUBLIC FIRST — a narrower revoke does nothing
-- ---------------------------------------------------------------------
--
-- 🔴 047 revoked at column level against a table-level grant and closed
-- nothing; 053 revoked at role level against a grant to PUBLIC and closed
-- nothing. PUBLIC is revoked here BEFORE anything is granted, and §8
-- asserts the resulting PRIVILEGE rather than asserting these statements
-- ran.
REVOKE ALL ON SCHEMA public_intel FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public_intel FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public_intel FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public_intel FROM PUBLIC;

GRANT USAGE ON SCHEMA public_intel TO evercoat_public;

GRANT SELECT ON
      public_intel.v_manufacturers,
      public_intel.v_products,
      public_intel.v_product_documents,
      public_intel.v_news_categories,
      public_intel.v_news_items
   TO evercoat_public;

-- The one write an anonymous caller may make. INSERT only: it may not read
-- back the queue, so it cannot enumerate who else has applied.
GRANT INSERT ON public_intel.access_requests TO evercoat_public;

-- The authenticated application role curates the catalogue.
GRANT USAGE ON SCHEMA public_intel TO evercoat_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public_intel TO evercoat_app;

-- ⚠️ `evercoat_owner` OWNS these objects but a schema owner is not
-- automatically granted USAGE on its own schema in every path that matters,
-- and the maintenance role needs to read the queue an administrator acts on.
-- Granted explicitly so a test or a backfill running as the owner does not
-- fail with "permission denied for schema public_intel" -- which is how the
-- missing ownership above was found.
GRANT USAGE ON SCHEMA public_intel TO evercoat_owner;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public_intel TO evercoat_owner;

COMMIT;
