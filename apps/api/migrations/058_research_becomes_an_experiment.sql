-- =====================================================================
-- 058 — research becomes an experiment
--
-- Phase 4 of the Material Safety Data & Research Center.
--
-- The vertical this migration exists to carry, from the specification's
-- §19 "Research-to-Experiment Workflow":
--
--     Research Question -> Investigation -> Evidence -> Finding ->
--     Hypothesis -> Experiment Proposal -> Chemist Review ->
--     Formula Candidate -> Lab Batch -> Test -> Analysis -> Finding
--     Updated
--
-- Everything from "Formula Candidate" rightwards ALREADY EXISTS. So this
-- migration builds the left half and then JOINS it to the right half at
-- exactly one point: an accepted experiment proposal records the formula
-- version that `formulations.revise_version` returned. It does not insert
-- a formula row, and there is no second way to make one.
--
-- ---------------------------------------------------------------------
-- 🔴 THE PHASE RULE THIS MIGRATION IS BOUND BY
-- ---------------------------------------------------------------------
--
-- `IMPLEMENTATION_PLAN_MATERIAL_SAFETY_DATA.md` §10: *a phase contains a
-- whole vertical, and every table it creates gets its writer and its
-- control in the same phase.* Eight tables are created here and all eight
-- are written by `app/domains/research/service.py` and reachable from a
-- control in `/material-safety/research` in the same commit. A table with
-- no writer is the defect this project has now counted twenty-five of.
--
-- The same rule governs what is NOT here:
--
--   * `experiment_proposal` is NOT added to `approval_routes.entity_type`.
--     A proposal is accepted by a named person holding `experiment.accept`,
--     not routed — §20: *"The Chemist decides whether it becomes an actual
--     experiment."* An accepted enum value nothing can write is the same
--     defect as a table with no writer (055 says so, about this exact
--     constraint).
--   * `competitor_analysis` and `material_qualification` likewise stay out.
--   * No permission is seeded whose enforcement point is not in this commit.
--     055 had to DELETE `safety.export_restricted` for breaking that rule;
--     the six minted below are each read by a route here.
--
-- ---------------------------------------------------------------------
-- 🔴 THE NUMBERING IN THE PLAN IS WRONG, AND SAYING SO IS THE POINT
-- ---------------------------------------------------------------------
--
-- §5's table assigns `research` to 057 and permissions to a separate 059.
-- Neither survived contact: 057 was spent closing the composite-FK hole
-- that Phase 3's sample picker made reachable, and 055/056 seeded their
-- permissions inline because a permission and its enforcement point must
-- ship together. Measured before writing, recorded here rather than left
-- for the next reader to trip over.
--
-- ---------------------------------------------------------------------
-- 🔴 WHAT THIS MIGRATION MAKES REACHABLE THAT WAS NOT REACHABLE BEFORE
-- ---------------------------------------------------------------------
--
-- The lesson 057 was written to record: ask what a change makes REACHABLE,
-- not only what it changes. Three answers, each handled below:
--
--   (a) `knowledge.promote` has been seeded since 002 and enforced NOWHERE.
--       `promote_finding` is its first enforcement point in the product's
--       history. It was already granted to three roles, so this migration
--       grants it to nobody new -- it turns an existing grant live. That
--       is a widening of what those three roles can actually DO, and it is
--       deliberate: the permission's description has always said "Promote
--       a finding to controlled knowledge".
--
--   (b) `formulations.formula_version_drivers` learns a fifth driver kind.
--       Its UNIQUE constraint is `(formula_version_id, driver_type,
--       failure_id, requirement_id)`, and Postgres's default NULLS
--       DISTINCT means a row with NULLs in the trailing columns can never
--       collide. Adding `experiment_proposal_id` without adding it to the
--       key would create a driver kind that can be recorded twice for the
--       same version. The constraint is therefore rebuilt.
--
--   (c) A finding's approval route needs a project, because
--       `approvals.open_route` takes `project_id` as a NOT NULL argument
--       (`approvals/service.py:103`). An investigation MAY be
--       organization-wide (§1.2 -- `project_id` nullable), so a finding on
--       one cannot be routed. That is expressed as a service refusal with
--       a reason, not as a NOT NULL that would forbid organization-wide
--       research outright.
-- =====================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS research;
ALTER SCHEMA research OWNER TO evercoat_owner;


-- ---------------------------------------------------------------------
-- The Research Workspace (§7)
-- ---------------------------------------------------------------------
--
-- §7: *"Every significant investigation should create a Research
-- Workspace"* -- a controlled R&D object rather than disposable chat.
--
-- `project_id` is NULLABLE and that is §1.2's decision, for the reason
-- `competitors.products` is: an investigation into, say, microsphere
-- chemistry belongs to the organization, not to one project. NULL means
-- organization-wide and the policy below reads it exactly as 042:271 does
-- for `knowledge.documents`.
--
-- The five thread columns are §19's list. Every one is NULLABLE and there
-- is deliberately NO "at least one" CHECK: §7's own example workspace
-- names a project and a research question and nothing else. An
-- investigation that starts from a question rather than from a record is
-- the normal case, and forbidding it would make the register describe
-- something other than the work.
CREATE TABLE IF NOT EXISTS research.investigations (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id    UUID NOT NULL REFERENCES core.organizations (id),
    project_id         UUID,
    -- RES-2026-0041, §7. Tenant-scoped like every other code in this
    -- database: a globally unique one would refuse org B a code org A
    -- holds, and the refusal would itself disclose org A's record.
    investigation_code TEXT NOT NULL,
    title              TEXT NOT NULL,
    research_question  TEXT NOT NULL,
    search_strategy    TEXT,
    -- §7's "Approval Status: Draft / Reviewed / Approved" is the status of
    -- the FINDINGS, which carry their own approval route. The workspace's
    -- own lifecycle is whether work is happening in it.
    -- 🔴 `on_hold` WAS HERE AND NOTHING COULD WRITE IT (Codex P2, 058's
    -- own review). An accepted value no production path can reach is the same
    -- defect as a table with no writer -- which this migration's header says in
    -- as many words about `experiment_proposal`, and then committed three times
    -- over in its own CHECKs. Removed rather than given a control: pausing a
    -- workspace is a feature, and a feature belongs to a phase.
    status             TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'closed')),
    -- §19's thread. Typed columns, never a polymorphic (entity_type, id)
    -- pair -- Codex P1-8, and the reason 054 was written the way it was.
    formula_version_id UUID,
    material_id        UUID,
    test_id            UUID,
    failure_id         UUID,
    owner_user_id      UUID NOT NULL REFERENCES core.users (id) ON DELETE RESTRICT,
    opened_by          UUID NOT NULL REFERENCES core.users (id) ON DELETE RESTRICT,
    closed_at          TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT investigations_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT investigations_org_code_key UNIQUE (organization_id, investigation_code),
    -- A closed workspace is closed at a time; an open one is not. Both
    -- directions, so neither state can be half-recorded.
    CONSTRAINT investigations_closure_complete CHECK (
        (status = 'closed') = (closed_at IS NOT NULL)
    ),
    CONSTRAINT investigations_project_fk FOREIGN KEY (project_id, organization_id)
        REFERENCES projects.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT investigations_version_fk FOREIGN KEY (formula_version_id, organization_id)
        REFERENCES formulations.formula_versions (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT investigations_material_fk FOREIGN KEY (material_id, organization_id)
        REFERENCES materials.materials (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT investigations_test_fk FOREIGN KEY (test_id, organization_id)
        REFERENCES testing.tests (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT investigations_failure_fk FOREIGN KEY (failure_id, organization_id)
        REFERENCES quality.failures (id, organization_id) ON DELETE RESTRICT
);


-- ---------------------------------------------------------------------
-- The questions inside a workspace (§18)
-- ---------------------------------------------------------------------
--
-- §7 gives the workspace ONE headline research question; §18 also asks for
-- `research.questions`. They are not duplicates: the headline is the
-- reason the workspace exists (and stays on the workspace, NOT NULL), and
-- these are the answerable sub-questions the work decomposes into. Each
-- can be answered, or recorded as unanswerable, which is what makes a
-- knowledge gap a measured thing rather than an opinion.
CREATE TABLE IF NOT EXISTS research.questions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES core.organizations (id),
    investigation_id UUID NOT NULL,
    sequence_number  INTEGER NOT NULL CHECK (sequence_number > 0),
    question         TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'answered', 'unanswerable')),
    asked_by         UUID NOT NULL REFERENCES core.users (id) ON DELETE RESTRICT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT questions_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT questions_order_key UNIQUE (investigation_id, sequence_number),
    -- The key `research.evidence` and `research.knowledge_gaps` address this
    -- table by. A three-column FK is REFUSED unless this exists first, so it
    -- is declared with the table rather than added afterwards.
    CONSTRAINT questions_id_investigation_org_key
        UNIQUE (id, investigation_id, organization_id),
    CONSTRAINT questions_investigation_fk
        FOREIGN KEY (investigation_id, organization_id)
        REFERENCES research.investigations (id, organization_id) ON DELETE RESTRICT
);


-- ---------------------------------------------------------------------
-- Sources, and the A–X ranking (§6)
-- ---------------------------------------------------------------------
--
-- 🔴 THE GRADE VOCABULARY IS 056's, TO THE LETTER.
--
-- `competitors.composition_evidence.evidence_grade` already implements §6's
-- A/B/C/D/X ranking and `evidence_source` already implements the seven ways
-- a thing can be known. Spelling either of them differently here would be
-- the "two literals in two files cannot be type-checked into agreement"
-- defect, and the copy that drifted would be whichever one had fewer
-- readers. They are repeated verbatim and this comment is why.
--
-- ⚠️ A SOURCE IS NOT EVIDENCE. §28's evidence cards cite sources; the same
-- source can support one conclusion and undercut another. So the grade
-- (how good is this source?) lives here and the strength of a particular
-- citation lives on `research.evidence`.
CREATE TABLE IF NOT EXISTS research.sources (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES core.organizations (id),
    investigation_id UUID NOT NULL,
    source_kind      TEXT NOT NULL
        CHECK (source_kind IN ('document', 'manual_observation', 'laboratory',
                               'literature', 'patent', 'inference', 'model')),
    -- §6's ranking. A is internal validated evidence, an official standard
    -- or manufacturer documentation; X is unverified.
    evidence_grade   TEXT NOT NULL CHECK (evidence_grade IN ('A', 'B', 'C', 'D', 'X')),
    title            TEXT NOT NULL,
    -- Where in the source. §6 asks responses to indicate evidence strength;
    -- a citation nobody can re-check is not evidence, it is an assertion.
    source_locator   TEXT,
    -- The ONE document register (056/ADR-033). A research source that is a
    -- document points AT the register; it does not carry bytes of its own.
    document_id      UUID,
    recorded_by      UUID NOT NULL REFERENCES core.users (id) ON DELETE RESTRICT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT sources_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT sources_id_investigation_org_key
        UNIQUE (id, investigation_id, organization_id),
    -- A source of kind `document` that names no document is a citation of
    -- nothing. Same shape as 056's `composition_evidence_document_shape`.
    CONSTRAINT sources_document_shape CHECK (
        source_kind <> 'document' OR document_id IS NOT NULL
    ),
    CONSTRAINT sources_investigation_fk
        FOREIGN KEY (investigation_id, organization_id)
        REFERENCES research.investigations (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT sources_document_fk FOREIGN KEY (document_id, organization_id)
        REFERENCES knowledge.documents (id, organization_id) ON DELETE RESTRICT
);


-- ---------------------------------------------------------------------
-- Evidence — the cards behind a conclusion (§28)
-- ---------------------------------------------------------------------
--
-- §28: *"Every major technical conclusion should have expandable evidence
-- cards... This prevents [it] from becoming a black box."* Its example
-- cites an internal test, an internal formula, a DOE, a supplier document
-- and a patent, and marks which support (✓) and which are merely related
-- (○). Both halves are stored: WHAT is cited, and WHICH WAY it points.
--
-- A card cites either an external/registered source OR an internal record.
-- Typed nullable columns and an "at least one" CHECK, never a polymorphic
-- pointer.
CREATE TABLE IF NOT EXISTS research.evidence (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id    UUID NOT NULL REFERENCES core.organizations (id),
    investigation_id   UUID NOT NULL,
    question_id        UUID,
    source_id          UUID,
    -- The internal thread. §4 of the revised specification: *"Internal
    -- Research Comes First"* -- released product knowledge, approved
    -- findings, historical formulas, test results, failure investigations.
    formula_version_id UUID,
    test_id            UUID,
    failure_id         UUID,
    -- ✓ / ○ in §28's card, plus the case the example does not draw and
    -- honest research needs: evidence that CONTRADICTS the conclusion.
    stance             TEXT NOT NULL DEFAULT 'supports'
        CHECK (stance IN ('supports', 'related', 'contradicts')),
    summary            TEXT NOT NULL,
    recorded_by        UUID NOT NULL REFERENCES core.users (id) ON DELETE RESTRICT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT evidence_id_org_key UNIQUE (id, organization_id),
    -- A card that cites nothing is an opinion with a border around it.
    CONSTRAINT evidence_cites_something CHECK (
        source_id IS NOT NULL
        OR formula_version_id IS NOT NULL
        OR test_id IS NOT NULL
        OR failure_id IS NOT NULL
    ),
    CONSTRAINT evidence_investigation_fk
        FOREIGN KEY (investigation_id, organization_id)
        REFERENCES research.investigations (id, organization_id) ON DELETE RESTRICT,
    -- 🔴 THREE COLUMNS, NOT TWO. A question belongs to an investigation,
    -- and evidence naming a question from a DIFFERENT investigation would
    -- attach one workspace's reasoning to another's conclusion. This is the
    -- hole 057 closed on `composition_evidence.sample_id` -- written
    -- correctly here at birth rather than found later by a client that
    -- started sending the field.
    CONSTRAINT evidence_question_fk
        FOREIGN KEY (question_id, investigation_id, organization_id)
        REFERENCES research.questions (id, investigation_id, organization_id)
        ON DELETE RESTRICT,
    CONSTRAINT evidence_source_fk
        FOREIGN KEY (source_id, investigation_id, organization_id)
        REFERENCES research.sources (id, investigation_id, organization_id)
        ON DELETE RESTRICT,
    CONSTRAINT evidence_version_fk FOREIGN KEY (formula_version_id, organization_id)
        REFERENCES formulations.formula_versions (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT evidence_test_fk FOREIGN KEY (test_id, organization_id)
        REFERENCES testing.tests (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT evidence_failure_fk FOREIGN KEY (failure_id, organization_id)
        REFERENCES quality.failures (id, organization_id) ON DELETE RESTRICT
);


-- ---------------------------------------------------------------------
-- The Research Findings Register (§9)
-- ---------------------------------------------------------------------
--
-- §9's object, field for field: Finding code, Subject, the finding itself,
-- Evidence, Confidence, Applicability, Limitations, Author, Reviewed by,
-- Status.
--
-- 🔴 CONFIDENCE HERE IS §29's VOCABULARY, AND IT IS *NOT* THE SAME WORD AS
-- 056's, ON PURPOSE.
--
-- `competitors.composition_evidence.confidence` is verified / supported /
-- probable / possible / unknown, and it answers *how well do we know this
-- claim about somebody else's recipe?*. §29 defines a different scale for a
-- different object -- High / Moderate / Low / Unknown, *"based on evidence,
-- not merely model probability"* -- and it answers *how strong is this
-- conclusion?*. The specification uses both, for these two objects. Written
-- out here so that a later consistency pass does not "harmonize" two scales
-- that measure different things.
--
-- ⚠️ §29 also says: *"Never use green PASS for an AI recommendation. Green
-- should remain reserved for validated/approved technical results."* That is
-- a UI rule and it is honoured in the screen, not here; noted so the two
-- halves stay connected.
CREATE TABLE IF NOT EXISTS research.findings (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES core.organizations (id),
    investigation_id UUID NOT NULL,
    finding_code     TEXT NOT NULL,
    subject          TEXT NOT NULL,
    statement        TEXT NOT NULL,
    applicability    TEXT NOT NULL,
    limitations      TEXT,
    confidence       TEXT NOT NULL
        CHECK (confidence IN ('high', 'moderate', 'low', 'unknown')),
    -- 🔴 THREE VALUES, AND `approved` IS DELIBERATELY NOT ONE OF THEM.
    --
    -- The first draft of this table carried `approved` and `rejected`, and
    -- NOTHING WOULD HAVE WRITTEN THEM. The approval engine settles a route;
    -- it has no entity callback, by design, so a finding could have been
    -- approved through `/approvals` while this column read `submitted` for
    -- ever. That is precisely the defect Codex found on `safety_reviews` in
    -- Phase 2 -- a table claiming a status nothing maintained, beside a module
    -- header asserting there was no second notion of "signed off".
    --
    -- So the ROUTE is the approval status, read through
    -- `approvals.route_for_entity`, exactly as `safety_review_status` reads
    -- it. This column carries only the states the research module itself
    -- writes.
    -- `withdrawn` removed for the same reason: no route retracts a submitted
    -- finding, so the value could only ever arrive through direct SQL.
    status           TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted')),
    author_id        UUID NOT NULL REFERENCES core.users (id) ON DELETE RESTRICT,
    -- Set by `promote_finding`, which is `knowledge.promote`'s first
    -- enforcement point. NULL means it has not been promoted; a value is
    -- the document in the ONE knowledge register that carries it.
    promoted_document_id UUID,
    promoted_at      TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT findings_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT findings_org_code_key UNIQUE (organization_id, finding_code),
    CONSTRAINT findings_id_investigation_org_key
        UNIQUE (id, investigation_id, organization_id),
    -- Both directions. A promotion half-recorded is one nobody can audit.
    CONSTRAINT findings_promotion_complete CHECK (
        (promoted_document_id IS NULL) = (promoted_at IS NULL)
    ),
    -- 🔴 ONLY AN APPROVED FINDING MAY BE PROMOTED — and because the approval
    -- lives on the ROUTE rather than in a column here, that cannot be a CHECK.
    -- A trigger below reads the route. A CHECK against a column nothing writes
    -- would have been a guard that cannot fail, which is worse than none.
    CONSTRAINT findings_investigation_fk
        FOREIGN KEY (investigation_id, organization_id)
        REFERENCES research.investigations (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT findings_document_fk FOREIGN KEY (promoted_document_id, organization_id)
        REFERENCES knowledge.documents (id, organization_id) ON DELETE RESTRICT
);


-- ---------------------------------------------------------------------
-- Hypotheses (§18, §19)
-- ---------------------------------------------------------------------
--
-- The step between a finding and an experiment: a statement that an
-- experiment could support or refute. `finding_id` is nullable because a
-- hypothesis often precedes the finding that settles it -- §7 lists
-- Hypothesis above Findings in the workspace for that reason.
CREATE TABLE IF NOT EXISTS research.hypotheses (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES core.organizations (id),
    investigation_id UUID NOT NULL,
    finding_id       UUID,
    statement        TEXT NOT NULL,
    rationale        TEXT,
    status           TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'supported', 'refuted', 'withdrawn')),
    proposed_by      UUID NOT NULL REFERENCES core.users (id) ON DELETE RESTRICT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT hypotheses_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT hypotheses_id_investigation_org_key
        UNIQUE (id, investigation_id, organization_id),
    CONSTRAINT hypotheses_investigation_fk
        FOREIGN KEY (investigation_id, organization_id)
        REFERENCES research.investigations (id, organization_id) ON DELETE RESTRICT,
    -- Three columns again: a hypothesis cannot hang off another
    -- workspace's finding.
    CONSTRAINT hypotheses_finding_fk
        FOREIGN KEY (finding_id, investigation_id, organization_id)
        REFERENCES research.findings (id, investigation_id, organization_id)
        ON DELETE RESTRICT
);


-- ---------------------------------------------------------------------
-- Knowledge gaps (§7, §18)
-- ---------------------------------------------------------------------
--
-- What the work could NOT establish. Recording it is what stops the same
-- dead end being walked twice, and it is why `questions.status` carries
-- `unanswerable`: a gap should be traceable to the question that hit it.
CREATE TABLE IF NOT EXISTS research.knowledge_gaps (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES core.organizations (id),
    investigation_id UUID NOT NULL,
    question_id      UUID,
    description      TEXT NOT NULL,
    impact           TEXT NOT NULL DEFAULT 'moderate'
        CHECK (impact IN ('high', 'moderate', 'low')),
    status           TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'closed')),
    identified_by    UUID NOT NULL REFERENCES core.users (id) ON DELETE RESTRICT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT knowledge_gaps_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT knowledge_gaps_investigation_fk
        FOREIGN KEY (investigation_id, organization_id)
        REFERENCES research.investigations (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT knowledge_gaps_question_fk
        FOREIGN KEY (question_id, investigation_id, organization_id)
        REFERENCES research.questions (id, investigation_id, organization_id)
        ON DELETE RESTRICT
);


-- ---------------------------------------------------------------------
-- The Experiment Proposal (§20) — where research meets the laboratory
-- ---------------------------------------------------------------------
--
-- §20's object, field for field: code, Objective, Basis, Variables,
-- Controlled Variables, Expected Direction, Required Tests, Risks,
-- Confidence, Status.
--
-- 🔴 AND §20's LAST LINE IS THE DESIGN: *"Status: PROPOSAL – NOT APPROVED.
-- The Chemist decides whether it becomes an actual experiment."*
--
-- So a proposal is inert. Acceptance is a person's act, gated on
-- `experiment.accept`, and the ONLY thing acceptance does to the formula
-- world is record the version that `formulations.revise_version` returned.
-- `resulting_formula_version_id` is written from that return value; this
-- schema has no path that inserts a formula version, and the service has
-- no second one.
CREATE TABLE IF NOT EXISTS research.experiment_proposals (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id      UUID NOT NULL REFERENCES core.organizations (id),
    investigation_id     UUID NOT NULL,
    hypothesis_id        UUID,
    proposal_code        TEXT NOT NULL,
    objective            TEXT NOT NULL,
    -- §20's "Basis: RF-021 / DOE-006 / F-088 / T-334" -- the human-readable
    -- citation line. The MACHINE-READABLE basis is `research.evidence` and
    -- `hypothesis_id`; this is the sentence a chemist reads.
    basis                TEXT NOT NULL,
    variables            TEXT NOT NULL,
    controlled_variables TEXT,
    expected_direction   TEXT NOT NULL,
    required_tests       TEXT NOT NULL,
    risks                TEXT,
    confidence           TEXT NOT NULL
        CHECK (confidence IN ('high', 'moderate', 'low', 'unknown')),
    -- `withdrawn` removed: accept and reject are the only decisions the
    -- vertical offers, and §20 gives the decision to the chemist rather than
    -- to the proposer.
    status               TEXT NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'accepted', 'rejected')),
    -- 🔴 THE PROJECT, DENORMALISED FROM THE INVESTIGATION BY A TRIGGER.
    --
    -- Codex P1 against the first version of this table: acceptance bound the
    -- revised formula version to the ORGANIZATION and nothing else, so a
    -- proposal from project A could revise a formula in project B and the
    -- digital thread would record A's research as the driver of B's formula.
    -- The composite key that stops it needs a project on THIS row, and
    -- `formulations.formula_versions` already carries
    -- `UNIQUE (id, project_id, organization_id)` for exactly this.
    --
    -- ⚠️ NULL IS THE ORGANIZATION-WIDE CASE AND IT IS NOT A HOLE. §1.2 makes
    -- an investigation's project nullable on purpose, and a foreign key with a
    -- NULL column passes trivially (MATCH SIMPLE) -- which is the right answer:
    -- research belonging to the whole organization may be applied to any
    -- project the CALLER can reach, and RLS on `formula_versions` is what
    -- decides that. A project-scoped proposal is bound; an org-wide one is not.
    --
    -- The trigger below copies it, so a client cannot declare a project its
    -- investigation does not have.
    project_id           UUID,
    -- The formula version the acceptance produced. NEVER inserted here;
    -- always the id `formulations.revise_version` returned.
    resulting_formula_version_id UUID,
    proposed_by          UUID NOT NULL REFERENCES core.users (id) ON DELETE RESTRICT,
    decided_by           UUID REFERENCES core.users (id) ON DELETE RESTRICT,
    decided_at           TIMESTAMPTZ,
    decision_note        TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT experiment_proposals_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT experiment_proposals_org_code_key UNIQUE (organization_id, proposal_code),
    -- Every decided state has a decider and a time; `proposed` has neither.
    -- Both directions, so a decision cannot be half-recorded and a proposal
    -- cannot carry a decider while still claiming to be open.
    CONSTRAINT experiment_proposals_decision_complete CHECK (
        (status IN ('accepted', 'rejected'))
        = (decided_by IS NOT NULL AND decided_at IS NOT NULL)
    ),
    -- 🔴 ACCEPTANCE *IS* THE FORMULA VERSION. Not "usually accompanied by"
    -- one: an accepted proposal with no version is a decision that produced
    -- nothing, and a version on a proposal nobody accepted is a formula
    -- change with no authority behind it. Both are refused, both directions.
    CONSTRAINT experiment_proposals_acceptance_produced_a_version CHECK (
        (status = 'accepted') = (resulting_formula_version_id IS NOT NULL)
    ),
    CONSTRAINT experiment_proposals_investigation_fk
        FOREIGN KEY (investigation_id, organization_id)
        REFERENCES research.investigations (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT experiment_proposals_hypothesis_fk
        FOREIGN KEY (hypothesis_id, investigation_id, organization_id)
        REFERENCES research.hypotheses (id, investigation_id, organization_id)
        ON DELETE RESTRICT,
    -- \U0001f534 TWO FOREIGN KEYS ON ONE COLUMN, AND THE SECOND IS NOT REDUNDANT.
    --
    -- A composite foreign key is MATCH SIMPLE by default: if ANY referencing
    -- column is NULL the WHOLE constraint is skipped. `project_id` is NULL for
    -- every organization-wide investigation -- \u00a71.2's deliberate case -- so
    -- the three-column key alone would leave those proposals with NO tenant
    -- binding at all, and `resulting_formula_version_id` could name a version
    -- in ANOTHER ORGANIZATION with nothing to refuse it. The Supervisor caught
    -- that the wider key had silently replaced the narrower one.
    --
    -- So both are declared. The two-column key always applies and binds the
    -- tenant; the three-column key applies only when a project is present and
    -- binds the project as well. Together: org-wide research may revise any
    -- version in ITS OWN organization that the caller can reach, and
    -- project-scoped research may revise only its own project's.
    CONSTRAINT experiment_proposals_version_org_fk
        FOREIGN KEY (resulting_formula_version_id, organization_id)
        REFERENCES formulations.formula_versions (id, organization_id)
        ON DELETE RESTRICT,
    CONSTRAINT experiment_proposals_version_fk
        FOREIGN KEY (resulting_formula_version_id, project_id, organization_id)
        REFERENCES formulations.formula_versions (id, project_id, organization_id)
        ON DELETE RESTRICT
);




-- ---------------------------------------------------------------------
-- PART 2 — row-level security, FORCE from birth, policies first
-- ---------------------------------------------------------------------
--
-- `CLAUDE.md:101` requires FORCE for every proprietary table, and these are
-- born with it: there is no I56/I58 entanglement, because the reason the
-- EXISTING tables have not cut over -- an owner-side reader that must keep
-- working -- does not apply to a table nothing has read yet.
--
-- 🔴 POLICIES FIRST, THEN FORCE. 056 confirmed the order matters: enabling
-- FORCE on a table whose policies are not yet installed locks the owner out
-- of its own seeding for the rest of the transaction.
--
-- 🔴 AND BOTH HALVES, ALWAYS. `USING` alone protects reads and leaves
-- writes wide open, because a foreign-key check bypasses RLS. Every policy
-- below is written twice on purpose.
ALTER TABLE research.investigations       ENABLE ROW LEVEL SECURITY;
ALTER TABLE research.questions            ENABLE ROW LEVEL SECURITY;
ALTER TABLE research.sources              ENABLE ROW LEVEL SECURITY;
ALTER TABLE research.evidence             ENABLE ROW LEVEL SECURITY;
ALTER TABLE research.findings             ENABLE ROW LEVEL SECURITY;
ALTER TABLE research.hypotheses           ENABLE ROW LEVEL SECURITY;
ALTER TABLE research.knowledge_gaps       ENABLE ROW LEVEL SECURITY;
ALTER TABLE research.experiment_proposals ENABLE ROW LEVEL SECURITY;

-- The workspace carries the project predicate. §1.2's shape, which is
-- 042:271's shape, which works precisely because `project_id` is nullable:
-- NULL is organization-wide research and everybody in the tenant sees it;
-- a value means the project's own confidentiality decides.
DROP POLICY IF EXISTS investigations_scope ON research.investigations;
CREATE POLICY investigations_scope ON research.investigations
    USING (
        organization_id = core.current_org_id()
        AND (
            project_id IS NULL
            OR EXISTS (
                SELECT 1 FROM projects.projects p
                 WHERE p.id = research.investigations.project_id
                   AND p.organization_id = research.investigations.organization_id
                   AND (p.confidentiality = 'normal' OR core.is_project_member(p.id))
            )
        )
    );
DROP POLICY IF EXISTS investigations_insert ON research.investigations;
CREATE POLICY investigations_insert ON research.investigations
    FOR INSERT WITH CHECK (
        organization_id = core.current_org_id()
        AND (
            project_id IS NULL
            OR EXISTS (
                SELECT 1 FROM projects.projects p
                 WHERE p.id = research.investigations.project_id
                   AND p.organization_id = research.investigations.organization_id
                   AND (p.confidentiality = 'normal' OR core.is_project_member(p.id))
            )
        )
    );

-- 🔴 THE SEVEN CHILDREN INHERIT BY JOINING THE WORKSPACE, NOT BY COPYING IT.
--
-- The join is to `research.investigations`, whose own policy is applied to
-- that subquery for the same role -- so a member outside a restricted
-- project matches no investigation, therefore no question, source,
-- evidence card, finding, hypothesis, gap or proposal. One predicate, one
-- place, and no `project_id` denormalised into seven tables where six
-- copies could drift.
--
-- This is 056's shape (`competitors.samples` -> `competitors.products`),
-- and T3b is what proves the transitive step actually happens rather than
-- being assumed from how RLS is documented.
DROP POLICY IF EXISTS questions_scope ON research.questions;
CREATE POLICY questions_scope ON research.questions
    USING (
        organization_id = core.current_org_id()
        AND EXISTS (SELECT 1 FROM research.investigations i
                     WHERE i.id = research.questions.investigation_id
                       AND i.organization_id = research.questions.organization_id)
    );
DROP POLICY IF EXISTS questions_insert ON research.questions;
CREATE POLICY questions_insert ON research.questions
    FOR INSERT WITH CHECK (
        organization_id = core.current_org_id()
        AND EXISTS (SELECT 1 FROM research.investigations i
                     WHERE i.id = research.questions.investigation_id
                       AND i.organization_id = research.questions.organization_id)
    );

DROP POLICY IF EXISTS sources_scope ON research.sources;
CREATE POLICY sources_scope ON research.sources
    USING (
        organization_id = core.current_org_id()
        AND EXISTS (SELECT 1 FROM research.investigations i
                     WHERE i.id = research.sources.investigation_id
                       AND i.organization_id = research.sources.organization_id)
    );
DROP POLICY IF EXISTS sources_insert ON research.sources;
CREATE POLICY sources_insert ON research.sources
    FOR INSERT WITH CHECK (
        organization_id = core.current_org_id()
        AND EXISTS (SELECT 1 FROM research.investigations i
                     WHERE i.id = research.sources.investigation_id
                       AND i.organization_id = research.sources.organization_id)
    );

DROP POLICY IF EXISTS evidence_scope ON research.evidence;
CREATE POLICY evidence_scope ON research.evidence
    USING (
        organization_id = core.current_org_id()
        AND EXISTS (SELECT 1 FROM research.investigations i
                     WHERE i.id = research.evidence.investigation_id
                       AND i.organization_id = research.evidence.organization_id)
    );
DROP POLICY IF EXISTS evidence_insert ON research.evidence;
CREATE POLICY evidence_insert ON research.evidence
    FOR INSERT WITH CHECK (
        organization_id = core.current_org_id()
        AND EXISTS (SELECT 1 FROM research.investigations i
                     WHERE i.id = research.evidence.investigation_id
                       AND i.organization_id = research.evidence.organization_id)
    );

DROP POLICY IF EXISTS findings_scope ON research.findings;
CREATE POLICY findings_scope ON research.findings
    USING (
        organization_id = core.current_org_id()
        AND EXISTS (SELECT 1 FROM research.investigations i
                     WHERE i.id = research.findings.investigation_id
                       AND i.organization_id = research.findings.organization_id)
    );
DROP POLICY IF EXISTS findings_insert ON research.findings;
CREATE POLICY findings_insert ON research.findings
    FOR INSERT WITH CHECK (
        organization_id = core.current_org_id()
        AND EXISTS (SELECT 1 FROM research.investigations i
                     WHERE i.id = research.findings.investigation_id
                       AND i.organization_id = research.findings.organization_id)
    );

DROP POLICY IF EXISTS hypotheses_scope ON research.hypotheses;
CREATE POLICY hypotheses_scope ON research.hypotheses
    USING (
        organization_id = core.current_org_id()
        AND EXISTS (SELECT 1 FROM research.investigations i
                     WHERE i.id = research.hypotheses.investigation_id
                       AND i.organization_id = research.hypotheses.organization_id)
    );
DROP POLICY IF EXISTS hypotheses_insert ON research.hypotheses;
CREATE POLICY hypotheses_insert ON research.hypotheses
    FOR INSERT WITH CHECK (
        organization_id = core.current_org_id()
        AND EXISTS (SELECT 1 FROM research.investigations i
                     WHERE i.id = research.hypotheses.investigation_id
                       AND i.organization_id = research.hypotheses.organization_id)
    );

DROP POLICY IF EXISTS knowledge_gaps_scope ON research.knowledge_gaps;
CREATE POLICY knowledge_gaps_scope ON research.knowledge_gaps
    USING (
        organization_id = core.current_org_id()
        AND EXISTS (SELECT 1 FROM research.investigations i
                     WHERE i.id = research.knowledge_gaps.investigation_id
                       AND i.organization_id = research.knowledge_gaps.organization_id)
    );
DROP POLICY IF EXISTS knowledge_gaps_insert ON research.knowledge_gaps;
CREATE POLICY knowledge_gaps_insert ON research.knowledge_gaps
    FOR INSERT WITH CHECK (
        organization_id = core.current_org_id()
        AND EXISTS (SELECT 1 FROM research.investigations i
                     WHERE i.id = research.knowledge_gaps.investigation_id
                       AND i.organization_id = research.knowledge_gaps.organization_id)
    );

DROP POLICY IF EXISTS experiment_proposals_scope ON research.experiment_proposals;
CREATE POLICY experiment_proposals_scope ON research.experiment_proposals
    USING (
        organization_id = core.current_org_id()
        AND EXISTS (SELECT 1 FROM research.investigations i
                     WHERE i.id = research.experiment_proposals.investigation_id
                       AND i.organization_id = research.experiment_proposals.organization_id)
    );
DROP POLICY IF EXISTS experiment_proposals_insert ON research.experiment_proposals;
CREATE POLICY experiment_proposals_insert ON research.experiment_proposals
    FOR INSERT WITH CHECK (
        organization_id = core.current_org_id()
        AND EXISTS (SELECT 1 FROM research.investigations i
                     WHERE i.id = research.experiment_proposals.investigation_id
                       AND i.organization_id = research.experiment_proposals.organization_id)
    );

ALTER TABLE research.investigations       FORCE ROW LEVEL SECURITY;
ALTER TABLE research.questions            FORCE ROW LEVEL SECURITY;
ALTER TABLE research.sources              FORCE ROW LEVEL SECURITY;
ALTER TABLE research.evidence             FORCE ROW LEVEL SECURITY;
ALTER TABLE research.findings             FORCE ROW LEVEL SECURITY;
ALTER TABLE research.hypotheses           FORCE ROW LEVEL SECURITY;
ALTER TABLE research.knowledge_gaps       FORCE ROW LEVEL SECURITY;
ALTER TABLE research.experiment_proposals FORCE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------
-- Indexes — every join FK, plus the columns the queues filter on
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS investigations_project_idx
    ON research.investigations (organization_id, project_id);
CREATE INDEX IF NOT EXISTS investigations_status_idx
    ON research.investigations (organization_id, status);
CREATE INDEX IF NOT EXISTS investigations_owner_idx
    ON research.investigations (organization_id, owner_user_id);
CREATE INDEX IF NOT EXISTS questions_investigation_idx
    ON research.questions (organization_id, investigation_id);
CREATE INDEX IF NOT EXISTS sources_investigation_idx
    ON research.sources (organization_id, investigation_id);
CREATE INDEX IF NOT EXISTS sources_grade_idx
    ON research.sources (organization_id, evidence_grade);
CREATE INDEX IF NOT EXISTS evidence_investigation_idx
    ON research.evidence (organization_id, investigation_id);
CREATE INDEX IF NOT EXISTS evidence_question_idx
    ON research.evidence (organization_id, question_id);
CREATE INDEX IF NOT EXISTS findings_investigation_idx
    ON research.findings (organization_id, investigation_id);
-- The register's queue: "what is awaiting review?" is the first question
-- the screen asks, and it asks it by status.
CREATE INDEX IF NOT EXISTS findings_status_idx
    ON research.findings (organization_id, status);
CREATE INDEX IF NOT EXISTS hypotheses_investigation_idx
    ON research.hypotheses (organization_id, investigation_id);
CREATE INDEX IF NOT EXISTS knowledge_gaps_investigation_idx
    ON research.knowledge_gaps (organization_id, investigation_id);
CREATE INDEX IF NOT EXISTS experiment_proposals_investigation_idx
    ON research.experiment_proposals (organization_id, investigation_id);
CREATE INDEX IF NOT EXISTS experiment_proposals_project_idx
    ON research.experiment_proposals (organization_id, project_id);
CREATE INDEX IF NOT EXISTS experiment_proposals_status_idx
    ON research.experiment_proposals (organization_id, status);
CREATE INDEX IF NOT EXISTS experiment_proposals_version_idx
    ON research.experiment_proposals (organization_id, resulting_formula_version_id);


-- ---------------------------------------------------------------------
-- Ownership and grants
-- ---------------------------------------------------------------------
ALTER TABLE research.investigations       OWNER TO evercoat_owner;
ALTER TABLE research.questions            OWNER TO evercoat_owner;
ALTER TABLE research.sources              OWNER TO evercoat_owner;
ALTER TABLE research.evidence             OWNER TO evercoat_owner;
ALTER TABLE research.findings             OWNER TO evercoat_owner;
ALTER TABLE research.hypotheses           OWNER TO evercoat_owner;
ALTER TABLE research.knowledge_gaps       OWNER TO evercoat_owner;
ALTER TABLE research.experiment_proposals OWNER TO evercoat_owner;

GRANT USAGE ON SCHEMA research TO evercoat_app, evercoat_report;

GRANT SELECT, INSERT ON research.investigations       TO evercoat_app;
GRANT SELECT, INSERT ON research.questions            TO evercoat_app;
GRANT SELECT, INSERT ON research.sources              TO evercoat_app;
GRANT SELECT, INSERT ON research.evidence             TO evercoat_app;
GRANT SELECT, INSERT ON research.findings             TO evercoat_app;
GRANT SELECT, INSERT ON research.hypotheses           TO evercoat_app;
GRANT SELECT, INSERT ON research.knowledge_gaps       TO evercoat_app;
GRANT SELECT, INSERT ON research.experiment_proposals TO evercoat_app;

-- 🔴 UPDATE PER COLUMN, NEVER PER TABLE — 047 and 053's rule, and 056
-- follows it for the same reason: a REVOKE written against a broader grant
-- does nothing, so the NARROW grant has to be the one that is written.
--
-- Name each column and ask what the application does with it:
--
--   investigations  — a workspace is closed, or put on hold and resumed.
--                     Its question, its title and its thread are the record
--                     of what was investigated and are NOT updatable: an
--                     investigation that can be re-pointed at another
--                     formula is a workspace whose history means nothing.
--   questions       — answered / unanswerable. The question text is fixed
--                     for the same reason.
--   findings        — submission, withdrawal, and the promotion pointer. The
--                     approval outcome is NOT here: it is the route's. The
--                     STATEMENT is never updatable — §9's register is a
--                     controlled object, and a finding whose text can change
--                     after approval is an approval of something else.
--   hypotheses      — supported / refuted / withdrawn by evidence.
--   knowledge_gaps  — closed when the gap is filled.
--   experiment_proposals — the decision, and the version it produced.
--
-- `sources` and `evidence` get NO update grant at all. An evidence card is
-- what was cited at the time; correcting one means recording a new card,
-- which is also what makes the correction visible.
GRANT UPDATE (status, closed_at)
    ON research.investigations TO evercoat_app;
GRANT UPDATE (status)
    ON research.questions TO evercoat_app;
GRANT UPDATE (status, promoted_document_id, promoted_at)
    ON research.findings TO evercoat_app;
GRANT UPDATE (status)
    ON research.hypotheses TO evercoat_app;
GRANT UPDATE (status)
    ON research.knowledge_gaps TO evercoat_app;
GRANT UPDATE (status, resulting_formula_version_id, decided_by, decided_at, decision_note)
    ON research.experiment_proposals TO evercoat_app;

GRANT SELECT ON ALL TABLES IN SCHEMA research TO evercoat_report;


-- ---------------------------------------------------------------------
-- A proposal's project comes from its investigation, not from its author
-- ---------------------------------------------------------------------
--
-- The composite key above is only worth having if `project_id` is TRUE. A
-- client that could set it freely could declare NULL on a project-scoped
-- investigation and buy back the cross-project revision the key exists to
-- refuse. So it is copied, on INSERT and on UPDATE, from the investigation.
--
-- ⚠️ SECURITY INVOKER. It reads a row the caller can already reach -- the
-- INSERT's own `WITH CHECK` policy has already required that -- so a definer
-- here would add reach without adding safety. 047's rule: scope-explicit.
CREATE OR REPLACE FUNCTION research.proposal_project_follows_the_investigation()
    RETURNS TRIGGER
    LANGUAGE plpgsql
    SECURITY INVOKER
    SET search_path TO 'pg_catalog', 'public', 'pg_temp'
AS $proposal_project$
BEGIN
    SELECT i.project_id INTO NEW.project_id
      FROM research.investigations i
     WHERE i.id = NEW.investigation_id
       AND i.organization_id = NEW.organization_id;
    RETURN NEW;
END
$proposal_project$;

REVOKE ALL ON FUNCTION research.proposal_project_follows_the_investigation() FROM PUBLIC;

DROP TRIGGER IF EXISTS experiment_proposals_project_is_inherited
    ON research.experiment_proposals;
CREATE TRIGGER experiment_proposals_project_is_inherited
    BEFORE INSERT OR UPDATE ON research.experiment_proposals
    FOR EACH ROW
    EXECUTE FUNCTION research.proposal_project_follows_the_investigation();


-- ---------------------------------------------------------------------
-- A promotion may only follow an approval — and the approval is the ROUTE
-- ---------------------------------------------------------------------
--
-- §9: *"MSD should heavily prioritize APPROVED findings when answering future
-- technical questions."* So promoting an unreviewed conclusion into the
-- knowledge register makes it authoritative, which is what `CLAUDE.md` §7
-- forbids: informal work never becomes controlled knowledge automatically.
--
-- 🔴 THIS CANNOT BE A CHECK, AND SAYING WHY MATTERS.
--
-- A CHECK can only see the row. The approval is a row in
-- `workflow.approval_routes`, because a finding IS its route -- the same
-- decision `safety_review_status` records, taken for the same reason. So the
-- guard has to read another table, which means a trigger.
--
-- ⚠️ SECURITY INVOKER, EXPLICITLY. A definer function here would read the
-- route as the OWNER and therefore past RLS, which would let a promotion be
-- justified by a route the caller cannot see. It runs as the caller, and RLS
-- applies to what it reads -- 047's rule: scope-explicit, not scope-assumed.
--
-- ⚠️ AND IT IS A MISUSE BARRIER AS WELL AS A CONTROL. `evercoat_app` holds
-- UPDATE on `promoted_document_id`, so the service is not the only thing that
-- could set it; this makes the rule hold for direct SQL too. What it cannot do
-- is stop somebody who can already approve a route from approving their own
-- finding -- that is what the template's `must_differ_from_group` is for.
CREATE OR REPLACE FUNCTION research.promotion_requires_an_approved_route()
    RETURNS TRIGGER
    LANGUAGE plpgsql
    SECURITY INVOKER
    SET search_path TO 'pg_catalog', 'public', 'pg_temp'
AS $promotion$
BEGIN
    IF NEW.promoted_document_id IS NULL THEN
        RETURN NEW;
    END IF;
    -- Unchanged promotions pass straight through: an UPDATE that touches some
    -- other column must not have to re-satisfy a rule it is not affecting.
    --
    -- \U0001f534 `TG_OP = 'UPDATE'` IS CHECKED FIRST BECAUSE `OLD` DOES NOT EXIST
    -- ON INSERT. See the trigger declaration: this fires on INSERT too now.
    IF TG_OP = 'UPDATE'
       AND OLD.promoted_document_id IS NOT DISTINCT FROM NEW.promoted_document_id THEN
        RETURN NEW;
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM workflow.approval_routes r
         WHERE r.organization_id = NEW.organization_id
           AND r.entity_type = 'research_finding'
           AND r.entity_id = NEW.id
           AND r.status = 'approved'
    ) THEN
        RAISE EXCEPTION
            'finding % has no approved approval route, so it may not be promoted '
            'into the knowledge register', NEW.finding_code
            USING ERRCODE = 'raise_exception';
    END IF;
    RETURN NEW;
END
$promotion$;

REVOKE ALL ON FUNCTION research.promotion_requires_an_approved_route() FROM PUBLIC;

-- \U0001f534 INSERT **AND** UPDATE, AND THE FIRST VERSION HAD ONLY UPDATE.
--
-- The comment above claimed the rule "holds for direct SQL too". It did not:
-- `evercoat_app` holds TABLE-LEVEL INSERT on `research.findings`, so
-- `INSERT ... (promoted_document_id, promoted_at)` wrote a promoted finding
-- with no approved route anywhere, satisfied `findings_promotion_complete` by
-- supplying both columns, and fired no trigger at all. The test exercised
-- UPDATE only, so it was green.
--
-- This project's own name for the shape: *a rule enforced on UPDATE only*.
-- Found by the Supervisor on this commit.
DROP TRIGGER IF EXISTS findings_promotion_follows_approval ON research.findings;
CREATE TRIGGER findings_promotion_follows_approval
    BEFORE INSERT OR UPDATE ON research.findings
    FOR EACH ROW
    EXECUTE FUNCTION research.promotion_requires_an_approved_route();


-- ---------------------------------------------------------------------
-- PART 3 — the permissions, and their enforcement points
-- ---------------------------------------------------------------------
--
-- 🔴 RULE P1 FIRST (§1.2): reuse what exists; mint only for acts with no
-- existing holder. The catalogue was read before any of these were written
-- -- `SELECT code FROM core.permissions`, 88 rows -- and it carries NO
-- `research.*` and NO `experiment.*` code of any kind.
--
-- Phase 3 applied the same rule and minted NOTHING, gating competitor work
-- on `material.view` / `material.edit`, because registering a competitor
-- product genuinely is recording information about a material. The same
-- reasoning does not reach here. Opening a controlled investigation,
-- approving a finding into the register the assistant treats as
-- authoritative, and accepting a proposal that produces a formula version
-- are three acts no existing permission describes. `failure.investigate` is
-- the nearest, and it is specific to a failure investigation, which this is
-- not.
--
-- ⚠️ EVERY ONE OF THE SIX HAS ITS ENFORCEMENT POINT IN THIS COMMIT. That is
-- the rule 055 broke and had to correct with a DELETE, and it is why
-- `safety.export_restricted` no longer exists. There is no seventh
-- permission here waiting for a phase that might not come.
INSERT INTO core.permissions (code, domain, description) VALUES
    ('research.view', 'research',
     'See research workspaces, their evidence and the findings register.'),
    ('research.create', 'research',
     'Open a research workspace and record questions, sources, evidence, '
     'hypotheses, knowledge gaps and draft findings in it.'),
    ('research.review', 'research',
     'Review a submitted research finding — the first step of the finding '
     'approval route. Separate from research.approve because §9 requires the '
     'reviewer and the approver to be able to be different people.'),
    ('research.approve', 'research',
     'Approve a research finding into the register. §9: approved findings are '
     'prioritized when answering future technical questions, so this is the '
     'gate on what becomes authoritative.'),
    ('experiment.propose', 'research',
     'Propose an experiment from research — §20''s structured proposal, which '
     'is inert until somebody accepts it.'),
    ('experiment.accept', 'research',
     'Accept an experiment proposal, which revises a formula version through '
     'the Formulations service. §20: "The Chemist decides whether it becomes '
     'an actual experiment."')
ON CONFLICT (code) DO NOTHING;

-- `core._grant` is 039's helper, recreated for this migration and dropped
-- again at the end (043's rule, enforced by
-- `test_the_grant_helper_did_not_survive_the_migration`).
CREATE OR REPLACE FUNCTION core._grant(p_role TEXT, VARIADIC p_perms TEXT[])
    RETURNS VOID LANGUAGE plpgsql AS $grant$
BEGIN
    INSERT INTO core.role_permissions (role_id, permission_id)
    SELECT r.id, p.id
    FROM core.roles r
    JOIN core.permissions p ON p.code = ANY(p_perms)
    WHERE r.code = p_role
    ON CONFLICT DO NOTHING;
END
$grant$;

-- 🔴 EVERY ROLE THAT CAN ACT ON RESEARCH CAN ALSO SEE IT.
--
-- §1.2's table grants `research.view` to chemist, engineer and lead. Read
-- literally that gives the DIRECTOR approval authority over findings he
-- cannot open and the QA officer review authority over findings she cannot
-- read -- a queue that 403s on the row it is asking you to decide. The
-- table was describing who does research, not who may look at it, so the
-- view grant is widened to everybody the other five grants name. Recorded
-- as a deviation from the plan rather than made silently.
SELECT core._grant('product_development_chemist',  'research.view', 'research.create',
                                                   'experiment.propose', 'experiment.accept');
SELECT core._grant('product_development_engineer', 'research.view', 'research.create',
                                                   'experiment.propose');
-- 🔴 THE LEAD DOES NOT GET `experiment.accept`, AND THE PLAN SAID THEY
-- SHOULD. Recorded as a correction rather than followed.
--
-- §1.2's table reads "experiment:propose / accept -> chemist and lead only".
-- But accepting a proposal IS a formula revision -- it calls
-- `formulations.revise_version` -- and `POST /formulations/.../revise` is gated
-- on `formula.clone`, which was MEASURED and is held by
-- `product_development_chemist` ALONE. So a lead granted `experiment.accept`
-- could never complete the act: the route would refuse them on the formula
-- permission every time. A permission whose holder cannot use it is the same
-- defect as a permission with no holder, one step further along.
--
-- The holder set of an act must be a subset of the holder set of what the act
-- DOES. §20 agrees -- "The Chemist decides whether it becomes an actual
-- experiment" -- so the chemist keeps it and the lead does not.
SELECT core._grant('product_development_lead',     'research.view', 'research.create',
                                                   'research.review', 'research.approve');
SELECT core._grant('product_development_director', 'research.view', 'research.approve');
SELECT core._grant('qa_compliance_officer',        'research.view', 'research.review');


-- ---------------------------------------------------------------------
-- PART 4 — a research finding is an approval
-- ---------------------------------------------------------------------
--
-- 020:140 declares `entity_type` as an INLINE, UNNAMED check, so PostgreSQL
-- generated the name. 055 read it from `pg_constraint` rather than guessing
-- and recorded the answer: `approval_routes_entity_type_check`. Re-measured
-- for this migration, unchanged.
--
-- ⚠️ ONLY `research_finding` IS ADDED — see the header. A proposal is
-- decided by a person, not routed, so `experiment_proposal` would be an
-- accepted value with no writer.
ALTER TABLE workflow.approval_routes
    DROP CONSTRAINT approval_routes_entity_type_check;
ALTER TABLE workflow.approval_routes
    ADD CONSTRAINT approval_routes_entity_type_check CHECK (
        entity_type IN ('test', 'formula_version', 'validation',
                        'pilot', 'qualification', 'product_release',
                        'safety_review', 'research_finding')
    );

-- A finding is not a test at `controlled` authority, and reusing a claimed
-- level would snapshot the wrong ladder: `approval_templates_authority_unique`
-- permits exactly one active template per level and all seven are taken
-- (the six of 030, plus `safety` from 055).
ALTER TABLE workflow.approval_templates
    DROP CONSTRAINT approval_templates_authority_level_check;
ALTER TABLE workflow.approval_templates
    ADD CONSTRAINT approval_templates_authority_level_check CHECK (
        authority_level IS NULL OR authority_level IN
        ('preliminary', 'development', 'controlled', 'validation',
         'qualification', 'release', 'safety', 'research')
    );


-- ---------------------------------------------------------------------
-- The template, for every organization — existing AND future
-- ---------------------------------------------------------------------
--
-- 🔴 A BACKFILL ALONE IS A DEFECT, AND 055 LEARNED IT THE HARD WAY.
--
-- `core.organizations` carries an AFTER INSERT trigger
-- (`organizations_get_approval_templates` -> `workflow.provision_templates_on_new_org()`).
-- A migration that inserts a template for every organization existing WHEN
-- IT RUNS silently expires the moment the next tenant is created: that
-- tenant gets the other seven templates and not this one, and
-- `open_route(authority_level => 'research')` raises "no active template"
-- the first time anybody submits a finding. Nothing about the migration
-- looks wrong.
--
-- So the template is defined ONCE, in a function, and called TWICE — once
-- per existing organization, once per new one.
CREATE OR REPLACE FUNCTION workflow.provision_research_finding_template(p_org UUID)
    RETURNS VOID
    LANGUAGE plpgsql
    SECURITY DEFINER
    -- `pg_temp` LAST — 013's rule.
    SET search_path TO 'pg_catalog', 'public', 'pg_temp'
AS $research_tpl$
DECLARE
    tpl UUID;
BEGIN
    INSERT INTO workflow.approval_templates
        (organization_id, template_code, name, description, authority_level, is_active)
    VALUES (p_org, 'RESEARCH_FINDING', 'Approval of a research finding',
            'Opened when a research finding is submitted to the register. '
            'Reviewed for technical soundness, then approved by somebody who '
            'did not perform the review. An approved finding is prioritized '
            'when answering future technical questions.',
            'research', TRUE)
    -- 🔴 REACTIVATE, DO NOT SKIP. `DO NOTHING` was here and it made this
    -- migration NON-RE-RUNNABLE: the downgrade RETIRES a template it cannot
    -- delete (a surviving route snapshots it), so a second upgrade found the
    -- row present, did nothing, and left the organization with an INACTIVE
    -- template -- `open_route('research')` raising for it for ever. The
    -- revision's own assertion caught it, which is what that assertion is for.
    ON CONFLICT (organization_id, template_code) DO UPDATE
        SET is_active = TRUE, authority_level = 'research'
    RETURNING id INTO tpl;

    -- ⚠️ AND THE STEPS ARE INSERTED ONLY IF THERE ARE NONE. With the
    -- upsert above, `tpl` is now non-NULL on EVERY call, so the old
    -- `IF tpl IS NOT NULL` guard would have duplicated the two steps on every
    -- re-run -- turning one defect into a worse one.
    IF NOT EXISTS (SELECT 1 FROM workflow.approval_template_steps s
                    WHERE s.template_id = tpl) THEN
        INSERT INTO workflow.approval_template_steps
            (organization_id, template_id, step_number, parallel_group,
             permission_required, step_label, is_mandatory, must_differ_from_group)
        VALUES
            -- Step 1 — is the conclusion supported by the evidence cited?
            (p_org, tpl, 1, 1, 'research.review',
             'Technical review of the finding and its evidence', TRUE, NULL),
            -- Step 2 — somebody ELSE puts it in the register.
            --
            -- 🔴 `must_differ_from_group = 1` IS WHY THERE ARE TWO STEPS.
            -- Without it one person reviews and approves and the second
            -- signature records nothing the first did not.
            --
            -- ⚠️ SATISFIABILITY WAS MEASURED, NOT ASSUMED — 055's precedent,
            -- because a segregation rule that makes the route uncompletable
            -- is worse than no rule. In the demonstration organization:
            --   research.review  — lead (Esi), qa_compliance_officer (Akua)
            --   research.approve — lead (Esi), director (Yaw)
            -- Akua reviews and Yaw approves: two distinct people, so the
            -- route completes. The lead holds both and therefore cannot do
            -- both on the same finding, which is the rule working.
            (p_org, tpl, 2, 2, 'research.approve',
             'Approval of the finding into the register', TRUE, 1);
    END IF;
END
$research_tpl$;

-- 🔴 EXECUTE IS TAKEN AWAY FROM PUBLIC FIRST.
--
-- `CREATE FUNCTION` grants EXECUTE to PUBLIC by default. This one is
-- SECURITY DEFINER and takes an organization id as an ARGUMENT, so left as
-- created, `evercoat_app` could call it for ANOTHER TENANT'S id and write
-- approval templates into that tenant's workflow configuration with RLS
-- entirely out of the loop. 055 shipped without this and the security
-- review found it.
REVOKE ALL ON FUNCTION workflow.provision_research_finding_template(UUID) FROM PUBLIC;

-- 🔴 THE OWNER IS DELIBERATELY NOT CHANGED. A SECURITY DEFINER function
-- executes with its OWNER's privileges, so reassigning one changes what it
-- may do while looking like tidying. Its siblings
-- `workflow.provision_approval_templates` and
-- `workflow.provision_safety_review_template` are owned by `postgres`; this
-- one matches them, and
-- `test_security_definer_functions_were_not_swept_along` states that intent
-- so a later consistency pass cannot quietly widen the sweep.

-- The backfill: every organization that already exists.
SELECT workflow.provision_research_finding_template(o.id) FROM core.organizations o;

-- And every organization created from now on. The trigger function is
-- EXTENDED, not replaced -- the seven templates it already provisions keep
-- being provisioned in exactly the same way. It is already SECURITY DEFINER
-- (055 had to make it so, because revoking PUBLIC EXECUTE on the safety
-- function otherwise broke organization creation outright), and the same
-- reasoning covers this third PERFORM.
CREATE OR REPLACE FUNCTION workflow.provision_templates_on_new_org()
    RETURNS TRIGGER
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'public', 'pg_temp'
AS $on_new_org$
BEGIN
    PERFORM workflow.provision_approval_templates(NEW.id);
    PERFORM workflow.provision_safety_review_template(NEW.id);
    PERFORM workflow.provision_research_finding_template(NEW.id);
    RETURN NEW;
END
$on_new_org$;

REVOKE ALL ON FUNCTION workflow.provision_templates_on_new_org() FROM PUBLIC;


-- ---------------------------------------------------------------------
-- The knowledge register learns where a promoted finding came from
-- ---------------------------------------------------------------------
--
-- 🔴 FOUND BY RUNNING IT, NOT BY READING IT. `promote_finding` calls
-- `knowledge.ingest_document(source='research_finding')`, and
-- `documents_source_check` accepts only internal_note / material_document /
-- standard / procedure / external. Every promotion would have been refused at
-- runtime with a raw constraint violation -- and no test written against the
-- SERVICE would have caught it, because the service is correct; the register
-- simply had no word for this kind of document.
--
-- The alternative was to promote findings as `internal_note`, which is what
-- §15 asks the register NOT to do: a promoted finding is Controlled Technical
-- Knowledge and an internal note is Historical Discussion, and `CLAUDE.md` §7
-- requires the RAG layer to tell them apart. Widening the vocabulary is the
-- honest fix.
--
-- ⚠️ ADDITIVE, and the new value HAS A WRITER IN THIS COMMIT -- which is the
-- test 055 applied to `safety.export_restricted` and failed.
ALTER TABLE knowledge.documents
    DROP CONSTRAINT IF EXISTS documents_source_check;
ALTER TABLE knowledge.documents
    ADD CONSTRAINT documents_source_check CHECK (
        source IN ('internal_note', 'material_document', 'standard',
                   'procedure', 'external', 'research_finding')
    );


-- ---------------------------------------------------------------------
-- PART 5 — the formula learns that research drove it
-- ---------------------------------------------------------------------
--
-- §2 of `CLAUDE.md`: *"A new formula revision must show exactly which
-- failure or improvement objective caused it."* Today
-- `formula_version_drivers` can say `failure`, `requirement`,
-- `optimization`, `cost`, `regulatory`, `customer_request` or `other`, and
-- the first two carry a typed FK to the thing itself.
--
-- Without this part, a version created by accepting an experiment proposal
-- would have to record `other` — a category with no link, which is exactly
-- the "data island" §2 forbids. `research.experiment_proposals` already
-- points forwards at the version it produced; this makes the thread
-- traversable BACKWARDS too, which §2 requires in both directions.
--
-- 🔴 AND THE UNIQUE CONSTRAINT HAS TO BE REBUILT, NOT LEFT ALONE.
--
-- `formula_version_drivers_unique` is
-- `(formula_version_id, driver_type, failure_id, requirement_id)`.
-- PostgreSQL's default is NULLS DISTINCT, so adding a column that the new
-- driver kind populates while the key ignores it would let the SAME
-- proposal be recorded as the driver of the same version any number of
-- times. Adding the column to the key is what makes the constraint mean
-- for `research` what it already means for `failure`.
ALTER TABLE formulations.formula_version_drivers
    ADD COLUMN IF NOT EXISTS experiment_proposal_id UUID;

ALTER TABLE formulations.formula_version_drivers
    DROP CONSTRAINT IF EXISTS formula_version_drivers_driver_type_check;
ALTER TABLE formulations.formula_version_drivers
    ADD CONSTRAINT formula_version_drivers_driver_type_check CHECK (
        driver_type IN ('failure', 'requirement', 'optimization', 'cost',
                        'regulatory', 'customer_request', 'other', 'research')
    );

-- The same shape as `..._failure_is_present` and `..._requirement_is_present`:
-- a driver that names its kind and not the thing is a category, not a link.
ALTER TABLE formulations.formula_version_drivers
    DROP CONSTRAINT IF EXISTS formula_version_drivers_research_is_present;
ALTER TABLE formulations.formula_version_drivers
    ADD CONSTRAINT formula_version_drivers_research_is_present CHECK (
        driver_type <> 'research' OR experiment_proposal_id IS NOT NULL
    );

-- Org-scoped and composite, like the requirement FK beside it. RLS stops
-- cross-tenant reads; it does not stop cross-tenant REFERENCES.
ALTER TABLE formulations.formula_version_drivers
    DROP CONSTRAINT IF EXISTS formula_version_drivers_proposal_fk;
ALTER TABLE formulations.formula_version_drivers
    ADD CONSTRAINT formula_version_drivers_proposal_fk
    FOREIGN KEY (experiment_proposal_id, organization_id)
    REFERENCES research.experiment_proposals (id, organization_id) ON DELETE RESTRICT;

ALTER TABLE formulations.formula_version_drivers
    DROP CONSTRAINT IF EXISTS formula_version_drivers_unique;
ALTER TABLE formulations.formula_version_drivers
    ADD CONSTRAINT formula_version_drivers_unique
    UNIQUE (formula_version_id, driver_type, failure_id, requirement_id,
            experiment_proposal_id);

CREATE INDEX IF NOT EXISTS formula_version_drivers_proposal_idx
    ON formulations.formula_version_drivers (experiment_proposal_id);

-- The new column needs the same INSERT reach the rest of the row has.
-- `evercoat_app` holds table-level INSERT here from 026, so the column is
-- covered by it; stated rather than assumed, because a column added to a
-- table whose grants were written per-column would NOT be.
GRANT SELECT, INSERT ON formulations.formula_version_drivers TO evercoat_app;


COMMENT ON TABLE research.investigations IS
    'The Research Workspace of specification §7. A controlled R&D object — '
    'question, strategy, evidence, findings, gaps, proposals — rather than a '
    'conversation. project_id is NULLABLE: an investigation may belong to the '
    'organization rather than to one project, and the RLS policy reads NULL as '
    'organization-wide.';

COMMENT ON TABLE research.findings IS
    'The Research Findings Register of §9. Confidence is §29''s scale (high / '
    'moderate / low / unknown), which measures how strong a CONCLUSION is — '
    'deliberately NOT the same words as competitors.composition_evidence.'
    'confidence, which measures how well a claim about somebody else''s recipe '
    'is known. Two scales, two objects, both from the specification. Only an '
    'approved finding may be promoted into the knowledge register.';

COMMENT ON TABLE research.experiment_proposals IS
    '§20''s structured proposal. INERT until a person holding experiment.accept '
    'accepts it: acceptance calls formulations.revise_version and stores the id '
    'it returns. Nothing here inserts a formula version, and there is no second '
    'path that does.';

-- 🔴 THE HELPER DOES NOT OUTLIVE THE MIGRATION THAT USED IT (043's rule).
DROP FUNCTION IF EXISTS core._grant(TEXT, TEXT[]);

COMMIT;
