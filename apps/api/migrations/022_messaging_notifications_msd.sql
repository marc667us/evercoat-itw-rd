-- 022_messaging_notifications_msd.sql
-- =====================================================================
-- Slice 7 -- Messaging, Notifications and MSD. The last MVP-1 slice.
--
-- 🔴 THE ONE RULE THIS MIGRATION EXISTS TO MAKE STRUCTURAL
-- ---------------------------------------------------------
-- `CLAUDE.md` §7: "MSD operates under EXACTLY the calling user's
-- authorization boundary. If the user cannot open Formula F100 through
-- the app, MSD must not retrieve, summarize, infer or expose F100 in
-- chat. FILTER RETRIEVAL BEFORE THE MODEL SEES ANYTHING -- never filter
-- after generation. AI must never become a permission-bypass channel."
--
-- Filtering after generation is the failure mode, and it is seductive
-- because it looks like it works: the model is handed everything, writes
-- an answer, and a redaction pass removes the parts the user should not
-- see. What survives is an answer SHAPED by data the user has no right
-- to -- a summary that is subtly different because F100 existed, a
-- confidence that came from a formulation in another project. Nothing in
-- the output names the leak and nothing detects it.
--
-- So the boundary is a property of RETRIEVAL, and retrieval here is
-- ordinary RLS-scoped SQL run as the calling user's session. There is no
-- privileged reader anywhere in this schema. `ai.msd_evidence` records
-- exactly which rows were retrieved, which is what makes the boundary
-- AUDITABLE rather than merely asserted -- an answer whose evidence
-- includes a row the user could not read is a detectable defect.
--
-- MSD IS NOT A USER, AND HAS NO PERMISSIONS
-- ------------------------------------------
-- There is no service account, no `msd` role and no bypass. Every turn
-- records the human who asked, and retrieval runs in their session.
-- §7 also forbids MSD from concluding anything: `failure_hypotheses`
-- already refuses an `accepted` status without a human, and MSD holds no
-- permission that could reach `failure.accept_root_cause`.
--
-- PARTS
--   1  Messaging -- channels, messages, mentions, entity links
--   2  Notifications
--   3  MSD -- threads, turns, and the evidence that proves the boundary
--   4  Immutability
--   5  Indexes, RLS, ownership, grants
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- PART 1 -- Messaging
-- ---------------------------------------------------------------------
-- The digital thread's rule applies here too: "no major technical record
-- may become an isolated data island". A discussion about a formula that
-- lives only in a chat window IS an island, so a message may attach
-- itself to the record it is about.

CREATE TABLE IF NOT EXISTS messaging.channels (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
    -- NULL for a direct message or an organization-wide channel. Present
    -- for a project channel, and it is what makes RLS able to apply the
    -- project's confidentiality to the conversation about it.
    project_id          UUID,
    channel_type        TEXT NOT NULL
                        CHECK (channel_type IN ('project','direct','technical_thread',
                                                'announcement')),
    name                TEXT,
    -- For a technical thread: the record it is about.
    entity_type         TEXT
                        CHECK (entity_type IS NULL OR entity_type IN
                               ('project','formula_version','batch','test','failure',
                                'material','requirement')),
    entity_id           UUID,
    created_by          UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_archived         BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (id),
    CONSTRAINT channels_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT channels_project_fk FOREIGN KEY (project_id, organization_id)
        REFERENCES projects.projects (id, organization_id) ON DELETE RESTRICT,
    -- A technical thread must say what it is about, or it is just a
    -- channel with a confusing name.
    CONSTRAINT channels_thread_names_its_subject CHECK (
        channel_type <> 'technical_thread'
        OR (entity_type IS NOT NULL AND entity_id IS NOT NULL)
    ),
    CONSTRAINT channels_reference_complete CHECK (
        (entity_type IS NULL) = (entity_id IS NULL)
    ),
    -- A PROJECT channel must name its project: it is the only thing that
    -- lets RLS apply that project's confidentiality to the conversation.
    -- Without it, a discussion of a restricted formulation would be
    -- readable by the whole organization.
    CONSTRAINT channels_project_channel_has_a_project CHECK (
        channel_type <> 'project' OR project_id IS NOT NULL
    )
);

CREATE TABLE IF NOT EXISTS messaging.channel_members (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    channel_id          UUID NOT NULL,
    user_id             UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    joined_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_read_at        TIMESTAMPTZ,
    PRIMARY KEY (id),
    CONSTRAINT channel_members_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT channel_members_pair_key UNIQUE (channel_id, user_id),
    CONSTRAINT channel_members_channel_fk FOREIGN KEY (channel_id, organization_id)
        REFERENCES messaging.channels (id, organization_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS messaging.messages (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    channel_id          UUID NOT NULL,
    body                TEXT NOT NULL,
    -- `#F008` smart linking, resolved at write time and stored. Resolving
    -- at READ time would mean a message rendering differently after the
    -- record it names is renamed or deleted, and a conversation must say
    -- what it said when it was written.
    reply_to_id         UUID,
    author_id           UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    posted_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    edited_at           TIMESTAMPTZ,
    is_deleted          BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (id),
    CONSTRAINT messages_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT messages_channel_fk FOREIGN KEY (channel_id, organization_id)
        REFERENCES messaging.channels (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT messages_reply_fk FOREIGN KEY (reply_to_id, organization_id)
        REFERENCES messaging.messages (id, organization_id) ON DELETE RESTRICT
);

-- A message's links to records: `#F008`, an @mention, an embedded card.
-- A separate table rather than parsing the body on every read, because a
-- link is a fact about the conversation and the body is prose.
CREATE TABLE IF NOT EXISTS messaging.message_links (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    message_id          UUID NOT NULL,
    link_type           TEXT NOT NULL
                        CHECK (link_type IN ('mention','record','promotion')),
    -- For a mention.
    mentioned_user_id   UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    -- For a record link or a promotion.
    entity_type         TEXT
                        CHECK (entity_type IS NULL OR entity_type IN
                               ('project','formula_version','batch','test','failure',
                                'material','requirement','task','decision')),
    entity_id           UUID,
    label               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT message_links_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT message_links_message_fk FOREIGN KEY (message_id, organization_id)
        REFERENCES messaging.messages (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT message_links_mention_has_a_user CHECK (
        link_type <> 'mention' OR mentioned_user_id IS NOT NULL
    ),
    CONSTRAINT message_links_record_has_an_entity CHECK (
        link_type = 'mention' OR (entity_type IS NOT NULL AND entity_id IS NOT NULL)
    )
);


-- ---------------------------------------------------------------------
-- PART 2 -- Notifications
-- ---------------------------------------------------------------------
-- One NotificationService, in the same sense as one approval engine:
-- every module writes here rather than growing its own.

CREATE TABLE IF NOT EXISTS messaging.notifications (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
    recipient_id        UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    notification_type   TEXT NOT NULL,          -- approval.awaiting, failure.opened...
    title               TEXT NOT NULL,
    body                TEXT,
    -- What to open. §11: a notification a reader cannot act on from is a
    -- notification that wastes their attention.
    entity_type         TEXT,
    entity_id           UUID,
    -- `actionable` distinguishes "you must do something" from "this
    -- happened". §11 requires sidebar counts to represent ACTIONABLE
    -- items, not total rows, and that distinction has to exist in the
    -- data or every count is a total.
    is_actionable       BOOLEAN NOT NULL DEFAULT FALSE,
    read_at             TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT notifications_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT notifications_reference_complete CHECK (
        (entity_type IS NULL) = (entity_id IS NULL)
    )
);


-- ---------------------------------------------------------------------
-- PART 3 -- MSD
-- ---------------------------------------------------------------------
-- Threads, turns, and the evidence that makes the authorization boundary
-- auditable.
--
-- These are OUR tables. `CLAUDE.md` §4 is explicit: "Threads, turns,
-- evidence links and checkpoints are our tables in the `ai` schema --
-- LangGraph state is derived from ours and disposable." So nothing here
-- references a framework, and swapping the orchestrator changes no row.

CREATE TABLE IF NOT EXISTS ai.msd_threads (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
    -- NULL for a general question. When present, the conversation is
    -- scoped to a project and RLS applies that project's
    -- confidentiality to the whole thread.
    project_id          UUID,
    title               TEXT,
    -- 🔴 WHOSE BOUNDARY THIS THREAD RUNS UNDER.
    -- Not "who created it" as bookkeeping: retrieval for every turn runs
    -- in this user's session, so this column IS the authorization scope.
    -- A thread cannot be handed to another user, because that would
    -- silently re-scope every future retrieval.
    owner_id            UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT msd_threads_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT msd_threads_project_fk FOREIGN KEY (project_id, organization_id)
        REFERENCES projects.projects (id, organization_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS ai.msd_turns (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    thread_id           UUID NOT NULL,
    turn_number         INTEGER NOT NULL CHECK (turn_number > 0),
    role                TEXT NOT NULL CHECK (role IN ('user','assistant')),
    body                TEXT NOT NULL,
    -- Which tools ran, as OUR record. A turn that called a tool and a
    -- turn that guessed look identical in prose.
    tool_calls          JSONB,
    -- 🔴 EVERY ASSISTANT TURN IS LABELLED, ALWAYS.
    -- §7: AI recommendations are labelled "AI-generated recommendation —
    -- requires technical review". Stored rather than added by a template,
    -- so a turn exported, printed or read through the API carries the
    -- label too.
    disclaimer          TEXT,
    asked_by            UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT msd_turns_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT msd_turns_number_key UNIQUE (thread_id, turn_number),
    CONSTRAINT msd_turns_thread_fk FOREIGN KEY (thread_id, organization_id)
        REFERENCES ai.msd_threads (id, organization_id) ON DELETE RESTRICT,
    -- An assistant turn without the label is the defect §7 forbids.
    CONSTRAINT msd_turns_assistant_is_labelled CHECK (
        role <> 'assistant' OR disclaimer IS NOT NULL
    )
);

-- 🔴 THE TABLE THAT MAKES THE BOUNDARY AUDITABLE.
--
-- Every row MSD retrieved in order to answer, recorded. Two things follow
-- that would otherwise be impossible:
--
--   * §7 requires answers to carry "evidence links to source records" --
--     a conclusion whose sources cannot be opened is not reviewable.
--   * an answer built on a record the asker could not read becomes
--     DETECTABLE: the evidence is on file, and a check can compare it
--     against what that user's session can see.
--
-- Without this, "MSD respected the boundary" is a claim about code that
-- nobody can verify after the fact.
CREATE TABLE IF NOT EXISTS ai.msd_evidence (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    turn_id             UUID NOT NULL,
    entity_type         TEXT NOT NULL
                        CHECK (entity_type IN ('project','formula_version','batch','test',
                                               'failure','material','requirement',
                                               'knowledge_document')),
    entity_id           UUID NOT NULL,
    -- What was actually used from it, so a reviewer can see whether the
    -- answer is supported by the source or merely near it.
    excerpt             TEXT,
    relevance_note      TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT msd_evidence_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT msd_evidence_turn_fk FOREIGN KEY (turn_id, organization_id)
        REFERENCES ai.msd_turns (id, organization_id) ON DELETE RESTRICT
);


-- ---------------------------------------------------------------------
-- PART 4 -- Immutability
-- ---------------------------------------------------------------------

-- A conversation is a record of what was said. A message may be edited
-- by its author (and says so) or withdrawn, and never silently rewritten
-- by anybody else.
CREATE OR REPLACE FUNCTION messaging.deny_message_rewrite() RETURNS TRIGGER
    LANGUAGE plpgsql AS $fn$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            'messages are withdrawn, not deleted; a conversation with holes in it '
            'cannot be read'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.author_id IS DISTINCT FROM OLD.author_id
       OR NEW.channel_id IS DISTINCT FROM OLD.channel_id
       OR NEW.posted_at IS DISTINCT FROM OLD.posted_at
    THEN
        RAISE EXCEPTION 'a message cannot be re-attributed or moved'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    -- An edit must SHOW as an edit.
    IF NEW.body IS DISTINCT FROM OLD.body AND NEW.edited_at IS NULL THEN
        RAISE EXCEPTION
            'a message body cannot change without recording that it was edited'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS messages_are_a_record ON messaging.messages;
CREATE TRIGGER messages_are_a_record
    BEFORE UPDATE OR DELETE ON messaging.messages
    FOR EACH ROW EXECUTE FUNCTION messaging.deny_message_rewrite();

-- 🔴 A THREAD'S OWNER IS ITS AUTHORIZATION SCOPE AND CANNOT CHANGE.
-- Handing a thread to another user would silently re-scope every future
-- retrieval against a different boundary, and the earlier turns -- built
-- under the first user's scope -- would still be sitting in it.
CREATE OR REPLACE FUNCTION ai.deny_thread_reassignment() RETURNS TRIGGER
    LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.owner_id IS DISTINCT FROM OLD.owner_id THEN
        RAISE EXCEPTION
            'an MSD thread cannot be reassigned; its owner is the authorization '
            'boundary every retrieval in it runs under (CLAUDE.md §7)'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.project_id IS DISTINCT FROM OLD.project_id
       OR NEW.organization_id IS DISTINCT FROM OLD.organization_id THEN
        RAISE EXCEPTION 'an MSD thread cannot be moved between projects or organizations'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS msd_threads_owner_immutable ON ai.msd_threads;
CREATE TRIGGER msd_threads_owner_immutable
    BEFORE UPDATE ON ai.msd_threads
    FOR EACH ROW EXECUTE FUNCTION ai.deny_thread_reassignment();

-- Turns and their evidence are append-only. An answer whose evidence
-- could be edited afterwards is an answer nobody can audit.
DROP TRIGGER IF EXISTS msd_turns_append_only ON ai.msd_turns;
CREATE TRIGGER msd_turns_append_only
    BEFORE UPDATE OR DELETE ON ai.msd_turns
    FOR EACH ROW EXECUTE FUNCTION audit.deny_mutation();

DROP TRIGGER IF EXISTS msd_evidence_append_only ON ai.msd_evidence;
CREATE TRIGGER msd_evidence_append_only
    BEFORE UPDATE OR DELETE ON ai.msd_evidence
    FOR EACH ROW EXECUTE FUNCTION audit.deny_mutation();


-- ---------------------------------------------------------------------
-- PART 5 -- Indexes, RLS, ownership, grants
-- ---------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS channels_project_idx
    ON messaging.channels (project_id, channel_type) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS channels_entity_idx
    ON messaging.channels (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS channel_members_user_idx
    ON messaging.channel_members (user_id);
CREATE INDEX IF NOT EXISTS messages_channel_time_idx
    ON messaging.messages (channel_id, posted_at DESC);
CREATE INDEX IF NOT EXISTS message_links_message_idx
    ON messaging.message_links (message_id);
-- "What is linked to this record?" -- the query that keeps a discussion
-- from being an island.
CREATE INDEX IF NOT EXISTS message_links_entity_idx
    ON messaging.message_links (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS message_links_mention_idx
    ON messaging.message_links (mentioned_user_id) WHERE mentioned_user_id IS NOT NULL;
-- The badge: MY unread ACTIONABLE notifications. §11 -- a count of
-- everything is not a count of what needs doing.
CREATE INDEX IF NOT EXISTS notifications_unread_actionable_idx
    ON messaging.notifications (recipient_id, is_actionable)
    WHERE read_at IS NULL;
CREATE INDEX IF NOT EXISTS msd_threads_owner_idx
    ON ai.msd_threads (owner_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS msd_turns_thread_idx
    ON ai.msd_turns (thread_id, turn_number);
CREATE INDEX IF NOT EXISTS msd_evidence_turn_idx
    ON ai.msd_evidence (turn_id);
-- "Which MSD answers cited this record?" -- the audit direction.
CREATE INDEX IF NOT EXISTS msd_evidence_entity_idx
    ON ai.msd_evidence (entity_type, entity_id);

ALTER TABLE messaging.channels        ENABLE ROW LEVEL SECURITY;
ALTER TABLE messaging.channel_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE messaging.messages        ENABLE ROW LEVEL SECURITY;
ALTER TABLE messaging.message_links   ENABLE ROW LEVEL SECURITY;
ALTER TABLE messaging.notifications   ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai.msd_threads            ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai.msd_turns              ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai.msd_evidence           ENABLE ROW LEVEL SECURITY;

-- 🔴 A PROJECT CHANNEL INHERITS ITS PROJECT'S CONFIDENTIALITY.
-- A conversation about a restricted formulation is at least as sensitive
-- as the formulation. `project_id IS NULL` covers direct messages and
-- announcements, which are governed by channel membership instead.
DROP POLICY IF EXISTS project_scope ON messaging.channels;
CREATE POLICY project_scope ON messaging.channels
    USING (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR (
            organization_id = core.current_org_id()
            AND (
                project_id IS NULL
                OR EXISTS (
                    SELECT 1 FROM projects.projects p
                    WHERE p.id = channels.project_id
                      AND (p.confidentiality = 'normal' OR core.is_project_member(p.id))
                )
            )
        )
    )
    WITH CHECK (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR organization_id = core.current_org_id()
    );

DO $policies$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'messaging.channel_members', 'messaging.messages', 'messaging.message_links',
        'messaging.notifications', 'ai.msd_turns', 'ai.msd_evidence'
    ]
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS org_scope ON %s', t);
        EXECUTE format($p$
            CREATE POLICY org_scope ON %s
            USING (
                core.rls_permissive() AND core.current_org_id() IS NULL
                OR organization_id = core.current_org_id()
            )
            WITH CHECK (
                core.rls_permissive() AND core.current_org_id() IS NULL
                OR organization_id = core.current_org_id()
            )
        $p$, t);
    END LOOP;
END
$policies$;

-- An MSD thread is visible to its OWNER and to nobody else, even inside
-- the same project. A conversation in which somebody explored their own
-- half-formed ideas is not a shared record, and §7's boundary is
-- per-user rather than per-project.
DROP POLICY IF EXISTS owner_scope ON ai.msd_threads;
CREATE POLICY owner_scope ON ai.msd_threads
    USING (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR (
            organization_id = core.current_org_id()
            AND owner_id = core.current_user_id()
        )
    )
    WITH CHECK (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR organization_id = core.current_org_id()
    );

DO $ownership$
DECLARE r RECORD;
BEGIN
    IF NOT (SELECT rolsuper FROM pg_roles WHERE rolname = current_user)
       AND NOT pg_has_role(current_user, 'evercoat_owner', 'MEMBER') THEN
        RAISE EXCEPTION
            'role % can neither bypass ownership checks nor act as evercoat_owner',
            current_user;
    END IF;

    FOR r IN
        SELECT n.nspname AS schema_name, c.relname AS object_name, c.relkind AS kind
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname IN ('messaging', 'ai')
          AND c.relkind IN ('r', 'p', 'S', 'v', 'm')
          AND pg_get_userbyid(c.relowner) <> 'evercoat_owner'
    LOOP
        IF r.kind = 'S' THEN
            EXECUTE format('ALTER SEQUENCE %I.%I OWNER TO evercoat_owner',
                           r.schema_name, r.object_name);
        ELSE
            EXECUTE format('ALTER TABLE %I.%I OWNER TO evercoat_owner',
                           r.schema_name, r.object_name);
        END IF;
    END LOOP;
END
$ownership$;

GRANT USAGE ON SCHEMA messaging, ai TO evercoat_app, evercoat_worker, evercoat_report;

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA messaging, ai TO evercoat_app;
GRANT SELECT ON ALL TABLES IN SCHEMA messaging, ai
    TO evercoat_worker, evercoat_report;

ALTER DEFAULT PRIVILEGES FOR ROLE evercoat_owner IN SCHEMA messaging, ai
    GRANT SELECT, INSERT, UPDATE ON TABLES TO evercoat_app;
ALTER DEFAULT PRIVILEGES FOR ROLE evercoat_owner IN SCHEMA messaging, ai
    GRANT SELECT ON TABLES TO evercoat_worker, evercoat_report;

COMMIT;
