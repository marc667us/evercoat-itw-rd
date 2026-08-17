-- 008_opportunity_converted_status.sql
-- =====================================================================
-- Two defects in the opportunity lifecycle, both found while writing the
-- service that drives it. Migration 003 defined the statuses before
-- anything moved an opportunity between them, and neither gap is
-- reachable by type-checking.
--
-- 1. THERE WAS NO 'converted' STATUS.
--
--    The digital thread says Opportunity -> Project. On approval the
--    opportunity becomes a project and must stop appearing in the
--    "approved, awaiting conversion" queue -- otherwise the funnel shows
--    it as outstanding work forever, and a second conversion looks
--    legitimate.
--
--    Leaving it as 'approved' would have made the funnel counts wrong in
--    a way nobody notices until somebody asks why the approved column
--    only ever grows.
--
-- 2. 'on_hold' WAS A ONE-WAY DOOR.
--
--    `on_hold` existed in the CHECK but nothing could leave it: the
--    service only decides opportunities in {feasibility,
--    awaiting_decision}, so a held opportunity was held permanently. The
--    fix is in the service (_DECIDABLE now includes on_hold); it is
--    recorded here because the two halves are one rule and reading only
--    the table would not reveal it.
--
-- WHY A CHECK REBUILD AND NOT AN ENUM. Statuses here are a closed set
-- the application owns. A CHECK constraint can be widened in a migration
-- like this one; a PostgreSQL ENUM cannot have a value removed at all,
-- and this set is still moving.
-- =====================================================================

BEGIN;

ALTER TABLE innovation.opportunities
    DROP CONSTRAINT IF EXISTS opportunities_status_check;

ALTER TABLE innovation.opportunities
    ADD CONSTRAINT opportunities_status_check
    CHECK (status IN ('draft','feasibility','awaiting_decision',
                      'approved','rejected','on_hold','converted'));

COMMENT ON COLUMN innovation.opportunities.status IS
    'Funnel position. ''converted'' is terminal and means a project '
    'exists carrying this opportunity_id -- see projects.projects. '
    '''approved'' means decided but not yet converted, which is the '
    'actionable queue.';

-- An approved opportunity may be converted exactly once. The service
-- checks this, but a service check is advisory the moment a second
-- caller exists -- a background job, a data fix, a later module. The
-- database is where "one project per opportunity" is actually true.
--
-- Partial index: NULL opportunity_id means a project raised directly,
-- which is legitimate and unlimited, so those rows must not collide with
-- each other.
CREATE UNIQUE INDEX IF NOT EXISTS projects_one_per_opportunity_idx
    ON projects.projects (opportunity_id, organization_id)
    WHERE opportunity_id IS NOT NULL;

COMMIT;
