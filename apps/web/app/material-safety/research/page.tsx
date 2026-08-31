"use client";

/**
 * The Research Center — §7's workspace, §9's findings register, §20's proposals.
 *
 * 🔴 THE LOOP THIS SCREEN HAS TO MAKE PRESSABLE
 *
 * §19: Research Question → Investigation → Evidence → Finding → Hypothesis →
 * Experiment Proposal → Chemist Review → Formula Candidate. Every arrow on the
 * left of "Formula Candidate" is a control on this page; the last one hands off
 * to Formulations, which already exists, and the message says which version it
 * made so a chemist can follow the thread rather than go hunting.
 *
 * 🔴 GREEN IS NOT AVAILABLE TO A FINDING, AND THAT IS A RULE, NOT A PREFERENCE.
 *
 * §29: *"Never use green PASS for an AI recommendation. Green should remain
 * reserved for validated/approved technical results."* A finding is a
 * conclusion drawn from evidence — it is not a test that passed. So confidence
 * renders in slate and amber with an icon and a word, never in the green
 * Testing owns. `CLAUDE.md` §11 forbids colour-only status independently, and
 * every badge here carries icon + word as well.
 *
 * 🔴 THERE IS NO APPROVE BUTTON HERE, DELIBERATELY.
 *
 * A finding is approved in `/approvals`, in the one approval engine, where the
 * queue and the segregation-of-duties rule already live. "Submit" opens the
 * route; the badge afterwards reads the ROUTE's status, and `null` means never
 * submitted — rendered as "Draft", not as a failure.
 */

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { formatDay, formatInstant } from "@/lib/format/date";
import { DataSourceError, LiveOnlyPage } from "@/components/ui/data-source-banner";
import { serverMessage } from "@/lib/api/client";
import {
  useEvidenceCards,
  useExperimentProposals,
  useInvestigations,
  useProjects,
  useResearchFindings,
  useResearchGaps,
  useResearchHypotheses,
  useKnowledgeDocuments,
  useResearchQuestions,
  useResearchSources,
  useResearchWrites,
} from "@/lib/api/hooks";
import type { Project } from "@/lib/api/projects";
import { permits, usePermissions } from "@/lib/permissions";
import {
  EVIDENCE_STANCES,
  FINDING_CONFIDENCES,
  RESEARCH_GRADES,
  RESEARCH_SOURCE_KINDS,
  type Finding,
  type Investigation,
} from "@/lib/api/research";

/**
 * What each act on this screen requires, mirrored from `app/api/research.py`.
 *
 * ⚠️ A MIRROR, AND MIRRORS DRIFT. It is here so the screen can avoid offering a
 * control the server will refuse — never as the thing that decides.
 * `tests/auth/test_research_routes.py` asserts the server side; if the two ever
 * disagree, the server is right and this is the bug.
 */
const MAY = {
  create: "research.create",
  propose: "experiment.propose",
  accept: "experiment.accept",
  promote: "knowledge.promote",
} as const;

const BUTTON =
  "rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 " +
  "disabled:cursor-not-allowed disabled:bg-slate-300";
const SECONDARY =
  "rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-800 " +
  "hover:bg-slate-100 disabled:cursor-not-allowed disabled:text-slate-400";
const INPUT =
  "mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm text-slate-900 " +
  "focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";
const LABEL = "block text-xs font-medium text-slate-700";
const PANEL = "rounded border border-slate-200 bg-white p-4";

interface Badge {
  readonly icon: string;
  readonly label: string;
  readonly className: string;
}

/**
 * What a confidence value reads as when the server sends one this screen does
 * not know. `noUncheckedIndexedAccess` is on, and it is right to be: a record
 * lookup can miss, and a badge rendering `undefined undefined` would be worse
 * than one that says plainly that the confidence is not known.
 */
const UNKNOWN_CONFIDENCE: Badge = {
  icon: "?",
  label: "Confidence unknown",
  className: "bg-amber-200 text-amber-900",
};

/** Confidence as icon AND word AND colour — never colour alone, never green. */
const CONFIDENCE: Record<string, Badge> = {
  high: { icon: "◆", label: "High confidence", className: "bg-slate-800 text-white" },
  moderate: {
    icon: "◈",
    label: "Moderate confidence",
    className: "bg-slate-200 text-slate-900",
  },
  low: { icon: "◇", label: "Low confidence", className: "bg-amber-200 text-amber-900" },
  unknown: UNKNOWN_CONFIDENCE,
};

/**
 * What a finding's approval badge says.
 *
 * `null` from the server means no route was ever opened. Rendering that as
 * anything other than "Draft" would tell a chemist their work had been refused.
 */
function approvalLabel(finding: Finding): { icon: string; text: string; className: string } {
  if (finding.approval_status === null) {
    return { icon: "✎", text: "Draft — not submitted", className: "bg-slate-100 text-slate-700" };
  }
  if (finding.approval_status === "approved") {
    // 🔴 NOT GREEN, AND CODEX WAS RIGHT TO CATCH IT. §29: "Never use green PASS
    // for an AI recommendation. Green should remain reserved for validated /
    // approved TECHNICAL results." An approved finding is a reviewed
    // conclusion, not a test that passed, and this file's own header says so —
    // then painted it emerald anyway. Slate reads as "settled" without
    // borrowing Testing's meaning.
    return { icon: "✓", text: "Approved", className: "bg-slate-800 text-white" };
  }
  if (finding.approval_status === "rejected") {
    return { icon: "✕", text: "Rejected", className: "bg-rose-200 text-rose-900" };
  }
  return {
    icon: "!",
    text: "Awaiting review in Approvals",
    className: "bg-amber-200 text-amber-900",
  };
}

function Feedback({
  writes,
}: {
  writes: { readonly error: Error | null; readonly lastAction: string | null };
}) {
  if (writes.error) {
    return (
      <p role="alert" className="mt-2 text-sm text-rose-700">
        {serverMessage(writes.error)}
      </p>
    );
  }
  if (writes.lastAction) {
    return (
      <p role="status" className="mt-2 text-sm text-slate-700">
        {writes.lastAction}
      </p>
    );
  }
  return null;
}

/* ------------------------------------------------------------------------ */

/**
 * §25 — the record a contextual entry point arrived with.
 *
 * The entry points ("Research this material", "Deep research" on a failure)
 * navigate here with the record in the query string. Read once, here, so the
 * form and its notice cannot disagree about what is being linked.
 *
 * ⚠️ ONLY ONE IS HONOURED, AND THE FIRST ONE WINS. `research.investigations`
 * can hold all four at once, but an entry point sends exactly one, and
 * accepting several from a hand-edited URL would attach an investigation to a
 * combination no screen offers and no reviewer expects.
 */
const ENTRY_POINTS = [
  { param: "material", field: "material_id", label: "material" },
  { param: "version", field: "formula_version_id", label: "formula version" },
  { param: "test", field: "test_id", label: "test" },
  { param: "failure", field: "failure_id", label: "failure" },
] as const;

function useEntryPoint(): { field: string; label: string; id: string } | null {
  const params = useSearchParams();
  for (const entry of ENTRY_POINTS) {
    const id = params.get(entry.param);
    if (id) return { field: entry.field, label: entry.label, id };
  }
  return null;
}

function OpenWorkspaceForm({ projects }: { projects: readonly Project[] }) {
  const may = permits(usePermissions(), MAY.create);
  const writes = useResearchWrites();
  const entry = useEntryPoint();
  const [title, setTitle] = useState("");
  const [question, setQuestion] = useState("");
  const [strategy, setStrategy] = useState("");
  const [projectId, setProjectId] = useState("");

  return (
    <form
      className={PANEL}
      onSubmit={(event) => {
        event.preventDefault();
        writes.open(
          {
            title,
            research_question: question,
            project_id: projectId === "" ? undefined : projectId,
            search_strategy: strategy === "" ? undefined : strategy,
            ...(entry ? { [entry.field]: entry.id } : {}),
          },
          () => {
            setTitle("");
            setQuestion("");
            setStrategy("");
          },
        );
      }}
    >
      <h3 className="text-sm font-semibold text-slate-900">Open a research workspace</h3>
      {entry && (
        <p
          className="mt-2 rounded border border-sky-300 bg-sky-50 px-3 py-2 text-xs text-sky-900"
          data-testid="research-entry-point"
        >
          → This workspace will be linked to the {entry.label} you came from. It will
          say so on the workspace card, and the {entry.label} is how somebody
          finds this research later.
        </p>
      )}
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className={LABEL}>
          Title
          <input
            className={INPUT}
            required
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>
        <label className={LABEL}>
          Project
          <select
            className={INPUT}
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
          >
            {/* 🔴 THE EMPTY OPTION IS A REAL CHOICE, NOT A PLACEHOLDER.
                §1.2 makes an investigation's project nullable on purpose: an
                investigation into a chemistry belongs to the organization. The
                label says so, because "— none —" would read as "not chosen". */}
            <option value="">Organization-wide (no project)</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.project_code} — {project.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className={`${LABEL} mt-3`}>
        Research question
        <textarea
          className={INPUT}
          required
          rows={2}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
        />
      </label>
      <label className={`${LABEL} mt-3`}>
        Search strategy (optional)
        <textarea
          className={INPUT}
          rows={2}
          value={strategy}
          onChange={(event) => setStrategy(event.target.value)}
        />
      </label>
      <p className="mt-2 text-xs text-slate-600">
        A finding from an organization-wide workspace cannot be sent for
        approval: each project&apos;s lead approves for their own work, so the
        approval route needs a project.
      </p>
      <button type="submit" className={`${BUTTON} mt-3`} disabled={writes.isPending || !may}>
        {writes.isPending ? "Opening…" : "Open workspace"}
      </button>
      <Feedback writes={writes} />
    </form>
  );
}

function QuestionsPanel({ investigationId }: { investigationId: string }) {
  const may = permits(usePermissions(), MAY.create);
  const questions = useResearchQuestions(investigationId);
  const writes = useResearchWrites();
  const [text, setText] = useState("");
  const rows = questions.data ?? [];

  return (
    <section className={PANEL}>
      <h4 className="text-sm font-semibold text-slate-900">Questions</h4>
      {questions.error ? (
        <DataSourceError error={questions.error} />
      ) : rows.length === 0 ? (
        <p className="mt-2 text-sm text-slate-600">No questions recorded yet.</p>
      ) : (
        <ul className="mt-2 grid gap-2">
          {rows.map((row) => (
            <li key={row.id} className="flex flex-wrap items-baseline gap-2 text-sm">
              <span className="font-medium text-slate-900">Q{row.sequence_number}</span>
              <span className="flex-1 text-slate-800">{row.question}</span>
              <span className="text-xs text-slate-600">
                {row.evidence_count} card(s) · {row.status}
              </span>
              <span className="text-xs text-slate-500" title={formatInstant(row.created_at)}>
                {formatDay(row.created_at)}
              </span>
              {row.status === "open" && (
                <>
                  <button
                    type="button"
                    className={SECONDARY}
                    disabled={writes.isPending || !may}
                    onClick={() => writes.settleQuestion(row.id, "answered")}
                  >
                    Answered
                  </button>
                  <button
                    type="button"
                    className={SECONDARY}
                    disabled={writes.isPending || !may}
                    onClick={() => writes.settleQuestion(row.id, "unanswerable")}
                  >
                    Cannot answer
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      <form
        className="mt-3 flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          writes.askQuestion(investigationId, text, () => setText(""));
        }}
      >
        <label className={`${LABEL} flex-1`}>
          Add a question
          <input
            className={INPUT}
            required
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
        </label>
        <button type="submit" className={BUTTON} disabled={writes.isPending || !may}>
          Add
        </button>
      </form>
      <Feedback writes={writes} />
    </section>
  );
}

function SourcesPanel({ investigationId }: { investigationId: string }) {
  const may = permits(usePermissions(), MAY.create);
  const sources = useResearchSources(investigationId);
  // 🔴 THE DOCUMENT PICKER EXISTS BECAUSE THE MENU OPTION DID.
  //
  // "A document on file" was offered and the form sent no `document_id`, so
  // choosing it was refused EVERY time by `sources_document_shape` — a menu
  // option nobody could use, which is precisely the defect the Supervisor
  // found on the competitor evidence form in Phase 3 and found again here.
  // `needsDocument` is now READ rather than merely declared.
  // The hook returns the PAGE (documents / total / limit), not a bare
  // array -- the knowledge list is paginated and I78 records that it
  // truncates at 100 silently. The projector takes the rows.
  const documents = useKnowledgeDocuments((live) => live.documents);
  const writes = useResearchWrites();
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<string>(RESEARCH_SOURCE_KINDS[3].id);
  const [grade, setGrade] = useState<string>("B");
  const [locator, setLocator] = useState("");
  const [documentId, setDocumentId] = useState("");
  const rows = sources.data ?? [];
  const documentRows = documents.data ?? [];
  const needsDocument =
    RESEARCH_SOURCE_KINDS.find((option) => option.id === kind)?.needsDocument ?? false;

  return (
    <section className={PANEL}>
      <h4 className="text-sm font-semibold text-slate-900">Sources</h4>
      <p className="mt-1 text-xs text-slate-600">
        The grade describes the source, not the conclusion: an A-grade standard
        can be cited by evidence that contradicts a finding.
      </p>
      {sources.error ? (
        <DataSourceError error={sources.error} />
      ) : rows.length === 0 ? (
        <p className="mt-2 text-sm text-slate-600">No sources recorded yet.</p>
      ) : (
        <ul className="mt-2 grid gap-1 text-sm">
          {rows.map((row) => (
            <li key={row.id} className="flex flex-wrap items-baseline gap-2">
              <span className="rounded bg-slate-200 px-1.5 text-xs font-semibold text-slate-900">
                {row.evidence_grade}
              </span>
              <span className="flex-1 text-slate-800">{row.title}</span>
              <span className="text-xs text-slate-600">
                {row.source_kind}
                {row.source_locator ? ` · ${row.source_locator}` : ""}
              </span>
              <span className="text-xs text-slate-500" title={formatInstant(row.created_at)}>
                {formatDay(row.created_at)}
              </span>
            </li>
          ))}
        </ul>
      )}
      <form
        className="mt-3 grid gap-2 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          writes.addSource(
            investigationId,
            {
              source_kind: kind,
              evidence_grade: grade,
              title,
              source_locator: locator === "" ? undefined : locator,
              document_id: documentId === "" ? undefined : documentId,
            },
            () => {
              setTitle("");
              setLocator("");
              setDocumentId("");
            },
          );
        }}
      >
        <label className={LABEL}>
          Source title
          <input
            className={INPUT}
            required
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>
        <label className={LABEL}>
          Where in it (optional)
          <input
            className={INPUT}
            value={locator}
            onChange={(event) => setLocator(event.target.value)}
          />
        </label>
        <label className={LABEL}>
          Kind
          <select
            className={INPUT}
            value={kind}
            onChange={(event) => setKind(event.target.value)}
          >
            {RESEARCH_SOURCE_KINDS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className={LABEL}>
          Evidence grade
          <select
            className={INPUT}
            value={grade}
            onChange={(event) => setGrade(event.target.value)}
          >
            {RESEARCH_GRADES.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        {needsDocument && (
          <label className={`${LABEL} sm:col-span-2`}>
            Which document
            <select
              className={INPUT}
              required
              value={documentId}
              onChange={(event) => setDocumentId(event.target.value)}
            >
              <option value="">Choose a document…</option>
              {documentRows.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.title}
                </option>
              ))}
            </select>
          </label>
        )}
        <div className="sm:col-span-2">
          <button
            type="submit"
            className={BUTTON}
            disabled={
              writes.isPending || !may || (needsDocument && documentRows.length === 0)
            }
          >
            Record source
          </button>
          {needsDocument && documentRows.length === 0 && (
            <span className="ml-2 text-xs text-slate-600">
              There are no documents in the Knowledge Library to cite yet.
            </span>
          )}
        </div>
      </form>
      <Feedback writes={writes} />
    </section>
  );
}

function EvidencePanel({ investigationId }: { investigationId: string }) {
  const may = permits(usePermissions(), MAY.create);
  const cards = useEvidenceCards(investigationId);
  const questions = useResearchQuestions(investigationId);
  const sources = useResearchSources(investigationId);
  const writes = useResearchWrites();
  const [summary, setSummary] = useState("");
  const [stance, setStance] = useState<string>("supports");
  const [sourceId, setSourceId] = useState("");
  const [questionId, setQuestionId] = useState("");
  const rows = cards.data ?? [];
  const sourceRows = sources.data ?? [];

  return (
    <section className={PANEL}>
      <h4 className="text-sm font-semibold text-slate-900">Evidence cards</h4>
      {cards.error ? (
        <DataSourceError error={cards.error} />
      ) : rows.length === 0 ? (
        <p className="mt-2 text-sm text-slate-600">No evidence recorded yet.</p>
      ) : (
        <ul className="mt-2 grid gap-2 text-sm">
          {rows.map((row) => {
            const mark = EVIDENCE_STANCES.find((option) => option.id === row.stance);
            return (
              <li key={row.id} className="rounded border border-slate-200 p-2">
                <div className="flex flex-wrap items-baseline gap-2">
                  {/* Icon AND word: §11 forbids a mark alone carrying meaning. */}
                  <span className="font-semibold text-slate-900">
                    {mark?.mark} {mark?.label}
                  </span>
                  {row.evidence_grade && (
                    <span className="rounded bg-slate-200 px-1.5 text-xs font-semibold text-slate-900">
                      {row.evidence_grade}
                    </span>
                  )}
                  {row.question_number !== null && (
                    <span className="text-xs text-slate-600">Q{row.question_number}</span>
                  )}
                </div>
                <p className="mt-1 text-slate-800">{row.summary}</p>
                <p className="mt-1 text-xs text-slate-600">
                  {[
                    row.source_title,
                    row.version_code,
                    row.test_number,
                    row.failure_code,
                  ]
                    .filter(Boolean)
                    .join(" · ") || "cited record not visible to you"}
                </p>
              </li>
            );
          })}
        </ul>
      )}
      <form
        className="mt-3 grid gap-2 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          writes.addEvidence(
            investigationId,
            {
              summary,
              stance,
              source_id: sourceId === "" ? undefined : sourceId,
              question_id: questionId === "" ? undefined : questionId,
            },
            () => setSummary(""),
          );
        }}
      >
        <label className={`${LABEL} sm:col-span-2`}>
          What the evidence says
          <textarea
            className={INPUT}
            required
            rows={2}
            value={summary}
            onChange={(event) => setSummary(event.target.value)}
          />
        </label>
        <label className={LABEL}>
          Which way it points
          <select
            className={INPUT}
            value={stance}
            onChange={(event) => setStance(event.target.value)}
          >
            {EVIDENCE_STANCES.map((option) => (
              <option key={option.id} value={option.id}>
                {option.mark} {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className={LABEL}>
          Source it rests on
          <select
            className={INPUT}
            required
            value={sourceId}
            onChange={(event) => setSourceId(event.target.value)}
          >
            <option value="">Choose a source…</option>
            {sourceRows.map((row) => (
              <option key={row.id} value={row.id}>
                {row.evidence_grade} — {row.title}
              </option>
            ))}
          </select>
        </label>
        <label className={LABEL}>
          Question it answers (optional)
          <select
            className={INPUT}
            value={questionId}
            onChange={(event) => setQuestionId(event.target.value)}
          >
            <option value="">Not tied to one question</option>
            {(questions.data ?? []).map((row) => (
              <option key={row.id} value={row.id}>
                Q{row.sequence_number} — {row.question}
              </option>
            ))}
          </select>
        </label>
        <div className="sm:col-span-2">
          {/* A card must cite something: the database refuses one that does
              not, so the source select is `required` rather than letting the
              refusal arrive as a constraint violation. */}
          <button
            type="submit"
            className={BUTTON}
            disabled={writes.isPending || !may || sourceRows.length === 0}
          >
            Record evidence
          </button>
          {sourceRows.length === 0 && (
            <span className="ml-2 text-xs text-slate-600">
              Record a source first — an evidence card must cite one.
            </span>
          )}
        </div>
      </form>
      <Feedback writes={writes} />
    </section>
  );
}

function HypothesesPanel({ investigationId }: { investigationId: string }) {
  const may = permits(usePermissions(), MAY.create);
  const hypotheses = useResearchHypotheses(investigationId);
  const writes = useResearchWrites();
  const [statement, setStatement] = useState("");
  const rows = hypotheses.data ?? [];

  return (
    <section className={PANEL}>
      <h4 className="text-sm font-semibold text-slate-900">Hypotheses</h4>
      {hypotheses.error ? (
        <DataSourceError error={hypotheses.error} />
      ) : rows.length === 0 ? (
        <p className="mt-2 text-sm text-slate-600">No hypotheses stated yet.</p>
      ) : (
        <ul className="mt-2 grid gap-2 text-sm">
          {rows.map((row) => (
            <li key={row.id} className="flex flex-wrap items-baseline gap-2">
              <span className="flex-1 text-slate-800">{row.statement}</span>
              <span className="text-xs text-slate-600">
                {row.status} · {row.proposal_count} proposal(s)
              </span>
              <span className="text-xs text-slate-500" title={formatInstant(row.created_at)}>
                {formatDay(row.created_at)}
              </span>
              {row.status === "open" && (
                <>
                  <button
                    type="button"
                    className={SECONDARY}
                    disabled={writes.isPending || !may}
                    onClick={() => writes.decideHypothesis(row.id, "supported")}
                  >
                    Supported
                  </button>
                  {/* Refuted is a first-class outcome, not a failure: what did
                      not work is evidence the next person needs. */}
                  <button
                    type="button"
                    className={SECONDARY}
                    disabled={writes.isPending || !may}
                    onClick={() => writes.decideHypothesis(row.id, "refuted")}
                  >
                    Refuted
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      <form
        className="mt-3 flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          writes.addHypothesis(investigationId, { statement }, () => setStatement(""));
        }}
      >
        <label className={`${LABEL} flex-1`}>
          State a hypothesis
          <input
            className={INPUT}
            required
            value={statement}
            onChange={(event) => setStatement(event.target.value)}
          />
        </label>
        <button type="submit" className={BUTTON} disabled={writes.isPending || !may}>
          Add
        </button>
      </form>
      <Feedback writes={writes} />
    </section>
  );
}

function GapsPanel({ investigationId }: { investigationId: string }) {
  const may = permits(usePermissions(), MAY.create);
  const gaps = useResearchGaps(investigationId);
  const writes = useResearchWrites();
  const [description, setDescription] = useState("");
  const [impact, setImpact] = useState("moderate");
  const rows = gaps.data ?? [];

  return (
    <section className={PANEL}>
      <h4 className="text-sm font-semibold text-slate-900">Knowledge gaps</h4>
      <p className="mt-1 text-xs text-slate-600">
        What the work could not establish. Recording it is what stops the same
        dead end being walked twice.
      </p>
      {gaps.error ? (
        <DataSourceError error={gaps.error} />
      ) : rows.length === 0 ? (
        <p className="mt-2 text-sm text-slate-600">No gaps recorded yet.</p>
      ) : (
        <ul className="mt-2 grid gap-2 text-sm">
          {rows.map((row) => (
            <li key={row.id} className="flex flex-wrap items-baseline gap-2">
              <span className="rounded bg-slate-200 px-1.5 text-xs font-semibold text-slate-900">
                {row.impact} impact
              </span>
              <span className="flex-1 text-slate-800">{row.description}</span>
              <span className="text-xs text-slate-600">{row.status}</span>
              <span className="text-xs text-slate-500" title={formatInstant(row.created_at)}>
                {formatDay(row.created_at)}
              </span>
              {row.status === "open" && (
                <button
                  type="button"
                  className={SECONDARY}
                  disabled={writes.isPending || !may}
                  onClick={() => writes.resolveGap(row.id)}
                >
                  Close gap
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      <form
        className="mt-3 flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          writes.addGap(investigationId, { description, impact }, () => setDescription(""));
        }}
      >
        <label className={`${LABEL} flex-1`}>
          Record a gap
          <input
            className={INPUT}
            required
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </label>
        <label className={LABEL}>
          Impact
          <select
            className={INPUT}
            value={impact}
            onChange={(event) => setImpact(event.target.value)}
          >
            <option value="high">High</option>
            <option value="moderate">Moderate</option>
            <option value="low">Low</option>
          </select>
        </label>
        <button type="submit" className={BUTTON} disabled={writes.isPending || !may}>
          Add
        </button>
      </form>
      <Feedback writes={writes} />
    </section>
  );
}

function DraftFindingForm({ investigationId }: { investigationId: string }) {
  const may = permits(usePermissions(), MAY.create);
  const writes = useResearchWrites();
  const [subject, setSubject] = useState("");
  const [statement, setStatement] = useState("");
  const [applicability, setApplicability] = useState("");
  const [limitations, setLimitations] = useState("");
  const [confidence, setConfidence] = useState("moderate");

  return (
    <form
      className={PANEL}
      onSubmit={(event) => {
        event.preventDefault();
        writes.draftFinding(
          investigationId,
          {
            subject,
            statement,
            applicability,
            confidence,
            limitations: limitations === "" ? undefined : limitations,
          },
          () => {
            setSubject("");
            setStatement("");
            setApplicability("");
            setLimitations("");
          },
        );
      }}
    >
      <h4 className="text-sm font-semibold text-slate-900">Draft a finding</h4>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <label className={LABEL}>
          Subject
          <input
            className={INPUT}
            required
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
          />
        </label>
        <label className={LABEL}>
          Confidence
          <select
            className={INPUT}
            value={confidence}
            onChange={(event) => setConfidence(event.target.value)}
          >
            {FINDING_CONFIDENCES.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className={`${LABEL} sm:col-span-2`}>
          The finding
          <textarea
            className={INPUT}
            required
            rows={2}
            value={statement}
            onChange={(event) => setStatement(event.target.value)}
          />
        </label>
        <label className={LABEL}>
          Applicability
          <input
            className={INPUT}
            required
            value={applicability}
            onChange={(event) => setApplicability(event.target.value)}
          />
        </label>
        <label className={LABEL}>
          Limitations (optional)
          <input
            className={INPUT}
            value={limitations}
            onChange={(event) => setLimitations(event.target.value)}
          />
        </label>
      </div>
      <button type="submit" className={`${BUTTON} mt-3`} disabled={writes.isPending || !may}>
        Draft finding
      </button>
      <Feedback writes={writes} />
    </form>
  );
}

function ProposeExperimentForm({ investigationId }: { investigationId: string }) {
  const may = permits(usePermissions(), MAY.propose);
  const hypotheses = useResearchHypotheses(investigationId);
  const writes = useResearchWrites();
  const [objective, setObjective] = useState("");
  const [basis, setBasis] = useState("");
  const [variables, setVariables] = useState("");
  const [direction, setDirection] = useState("");
  const [tests, setTests] = useState("");
  const [risks, setRisks] = useState("");
  const [confidence, setConfidence] = useState("moderate");
  const [hypothesisId, setHypothesisId] = useState("");

  return (
    <form
      className={PANEL}
      onSubmit={(event) => {
        event.preventDefault();
        writes.propose(
          investigationId,
          {
            objective,
            basis,
            variables,
            expected_direction: direction,
            required_tests: tests,
            confidence,
            risks: risks === "" ? undefined : risks,
            hypothesis_id: hypothesisId === "" ? undefined : hypothesisId,
          },
          () => {
            setObjective("");
            setBasis("");
            setVariables("");
            setDirection("");
            setTests("");
            setRisks("");
          },
        );
      }}
    >
      <h4 className="text-sm font-semibold text-slate-900">Propose an experiment</h4>
      <p className="mt-1 text-xs text-slate-600">
        A proposal changes nothing on its own. A chemist decides whether it
        becomes an actual experiment, and accepting it creates a formula
        revision.
      </p>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <label className={LABEL}>
          Objective
          <input
            className={INPUT}
            required
            value={objective}
            onChange={(event) => setObjective(event.target.value)}
          />
        </label>
        <label className={LABEL}>
          Basis
          <input
            className={INPUT}
            required
            value={basis}
            onChange={(event) => setBasis(event.target.value)}
          />
        </label>
        <label className={LABEL}>
          Variables
          <input
            className={INPUT}
            required
            value={variables}
            onChange={(event) => setVariables(event.target.value)}
          />
        </label>
        <label className={LABEL}>
          Expected direction
          <input
            className={INPUT}
            required
            value={direction}
            onChange={(event) => setDirection(event.target.value)}
          />
        </label>
        <label className={LABEL}>
          Required tests
          <input
            className={INPUT}
            required
            value={tests}
            onChange={(event) => setTests(event.target.value)}
          />
        </label>
        <label className={LABEL}>
          Risks (optional)
          <input
            className={INPUT}
            value={risks}
            onChange={(event) => setRisks(event.target.value)}
          />
        </label>
        <label className={LABEL}>
          Confidence
          <select
            className={INPUT}
            value={confidence}
            onChange={(event) => setConfidence(event.target.value)}
          >
            {FINDING_CONFIDENCES.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className={LABEL}>
          From a hypothesis (optional)
          <select
            className={INPUT}
            value={hypothesisId}
            onChange={(event) => setHypothesisId(event.target.value)}
          >
            <option value="">Not tied to one hypothesis</option>
            {(hypotheses.data ?? []).map((row) => (
              <option key={row.id} value={row.id}>
                {row.statement}
              </option>
            ))}
          </select>
        </label>
      </div>
      <button type="submit" className={`${BUTTON} mt-3`} disabled={writes.isPending || !may}>
        Propose experiment
      </button>
      <Feedback writes={writes} />
    </form>
  );
}

/**
 * §25 — the record that motivated this workspace, and the way back to it.
 *
 * 🔴 THE LINK IS THE POINT, AND IT IS ONLY OFFERED WHERE ONE EXISTS.
 *
 * A material, a test and a failure can all motivate an investigation. Only two
 * of those have a detail screen in this product: `/testing/test?id=` and
 * `/failures/investigation?id=`. Materials do not, and neither does a formula
 * version outside its workspace — so those render as the CODE, not as a link
 * to a route that would 404. Same judgement as `components/ui/record-link.tsx`
 * and as the global search results, for the same reason.
 *
 * Renders nothing at all when an investigation was opened from no record. That
 * is a real and ordinary state — an organization-wide question — and an empty
 * "Opened from: —" row would suggest something was lost.
 */
function MotivatedBy({ investigation }: { investigation: Investigation }) {
  const items: React.ReactNode[] = [];

  if (investigation.material_id) {
    items.push(
      <span key="material">
        Material{" "}
        <span className="font-mono">{investigation.material_code ?? investigation.material_id}</span>
        {investigation.material_name ? ` — ${investigation.material_name}` : ""}
      </span>,
    );
  }
  if (investigation.formula_version_id) {
    items.push(
      <Link
        key="version"
        href={`/formulations/formula?version=${investigation.formula_version_id}`}
        className="underline"
      >
        Formula version{" "}
        <span className="font-mono">
          {investigation.version_code ?? investigation.formula_version_id}
        </span>
      </Link>,
    );
  }
  if (investigation.test_id) {
    items.push(
      <Link key="test" href={`/testing/test?id=${investigation.test_id}`} className="underline">
        Test <span className="font-mono">{investigation.test_number ?? investigation.test_id}</span>
      </Link>,
    );
  }
  if (investigation.failure_id) {
    items.push(
      <Link
        key="failure"
        href={`/failures/investigation?id=${investigation.failure_id}`}
        className="underline"
      >
        Failure{" "}
        <span className="font-mono">{investigation.failure_code ?? investigation.failure_id}</span>
        {investigation.failure_title ? ` — ${investigation.failure_title}` : ""}
      </Link>,
    );
  }

  if (items.length === 0) return null;

  return (
    <p className="mt-1 text-xs text-slate-600" data-testid="investigation-motivated-by">
      Opened from:{" "}
      {items.map((item, i) => (
        <span key={i}>
          {i > 0 ? " · " : ""}
          {item}
        </span>
      ))}
    </p>
  );
}

function Workspace({ investigation }: { investigation: Investigation }) {
  const may = permits(usePermissions(), MAY.create);
  const writes = useResearchWrites();
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-baseline gap-2">
        <p className="flex-1 text-sm text-slate-700">{investigation.research_question}</p>
        {investigation.status !== "closed" && (
          <button
            type="button"
            className={SECONDARY}
            disabled={writes.isPending || !may}
            onClick={() => writes.close(investigation.id)}
          >
            Close workspace
          </button>
        )}
      </div>
      <QuestionsPanel investigationId={investigation.id} />
      <SourcesPanel investigationId={investigation.id} />
      <EvidencePanel investigationId={investigation.id} />
      <HypothesesPanel investigationId={investigation.id} />
      <GapsPanel investigationId={investigation.id} />
      <DraftFindingForm investigationId={investigation.id} />
      <ProposeExperimentForm investigationId={investigation.id} />
    </div>
  );
}

function FindingsRegister() {
  const permissions = usePermissions();
  // Submitting your own work for review is part of doing the work; PROMOTING
  // it into the register the assistant treats as authoritative is not.
  const may = permits(permissions, MAY.create);
  const mayPromote = permits(permissions, MAY.promote);
  const findings = useResearchFindings();
  const writes = useResearchWrites();
  const rows = findings.data ?? [];

  return (
    <section>
      <h2 className="text-base font-semibold text-slate-900">Findings register</h2>
      <p className="mt-1 text-sm text-slate-600">
        Approved findings are prioritised when answering future technical
        questions, so approval happens in Approvals — not here.
      </p>
      {findings.error ? (
        <DataSourceError error={findings.error} />
      ) : rows.length === 0 ? (
        <p className="mt-3 text-sm text-slate-600">No findings recorded yet.</p>
      ) : (
        <ul className="mt-3 grid gap-2">
          {rows.map((row) => {
            const badge = approvalLabel(row);
            // A lookup that can miss falls back to the honest answer,
            // never to a badge reading `undefined`.
            const confidence = CONFIDENCE[row.confidence] ?? UNKNOWN_CONFIDENCE;
            return (
              <li key={row.id} className={PANEL}>
                <div className="flex flex-wrap items-baseline gap-2">
                  <h3 className="flex-1 text-sm font-semibold text-slate-900">
                    {row.finding_code} — {row.subject}
                  </h3>
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-medium ${confidence.className}`}
                  >
                    {confidence.icon} {confidence.label}
                  </span>
                  <span className={`rounded px-2 py-0.5 text-xs font-medium ${badge.className}`}>
                    {badge.icon} {badge.text}
                  </span>
                </div>
                <p className="mt-2 text-sm text-slate-800">{row.statement}</p>
                <p className="mt-1 text-xs text-slate-600">
                  Applies to {row.applicability} · from {row.investigation_code}
                  {row.limitations ? ` · limitations: ${row.limitations}` : ""}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {row.status === "draft" && (
                    <button
                      type="button"
                      className={BUTTON}
                      disabled={writes.isPending || !may}
                      onClick={() => writes.submit(row.id)}
                    >
                      Submit for approval
                    </button>
                  )}
                  {row.approval_status === "approved" &&
                    row.promoted_document_id === null && (
                      <button
                        type="button"
                        className={BUTTON}
                        disabled={writes.isPending || !mayPromote}
                        onClick={() => writes.promote(row.id)}
                      >
                        Promote to Knowledge Library
                      </button>
                    )}
                  {row.promoted_document_id !== null && (
                    <span className="text-xs text-slate-600">
                      In the Knowledge Library since{" "}
                      {row.promoted_at?.slice(0, 10) ?? "recently"}.
                    </span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
      <Feedback writes={writes} />
    </section>
  );
}

function ProposalsRegister() {
  // 🔴 ACCEPT AND REJECT ARE ONE AUTHORITY. Deciding is deciding, and the
  // server gates both on `experiment.accept` for that reason.
  const may = permits(usePermissions(), MAY.accept);
  const proposals = useExperimentProposals();
  const writes = useResearchWrites();
  const [openId, setOpenId] = useState<string | null>(null);
  const [versionId, setVersionId] = useState("");
  const [reason, setReason] = useState("");
  const [hypothesis, setHypothesis] = useState("");
  const [note, setNote] = useState("");
  const rows = proposals.data ?? [];

  return (
    <section>
      <h2 className="text-base font-semibold text-slate-900">Experiment proposals</h2>
      {proposals.error ? (
        <DataSourceError error={proposals.error} />
      ) : rows.length === 0 ? (
        <p className="mt-3 text-sm text-slate-600">No proposals yet.</p>
      ) : (
        <ul className="mt-3 grid gap-2">
          {rows.map((row) => (
            <li key={row.id} className={PANEL}>
              <div className="flex flex-wrap items-baseline gap-2">
                <h3 className="flex-1 text-sm font-semibold text-slate-900">
                  {row.proposal_code} — {row.objective}
                </h3>
                <span className="rounded bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-900">
                  {row.status === "proposed"
                    ? "◷ Proposed — not approved"
                    : row.status === "accepted"
                      ? `✓ Accepted — ${row.resulting_version_code ?? "version created"}`
                      : `✕ ${row.status}`}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-600">
                Basis {row.basis} · variables {row.variables} · expected{" "}
                {row.expected_direction} · tests {row.required_tests}
                {row.risks ? ` · risks ${row.risks}` : ""}
              </p>
              {row.decision_note && (
                <p className="mt-1 text-xs text-slate-700">Decision: {row.decision_note}</p>
              )}
              {row.status === "proposed" && (
                <div className="mt-3">
                  {/* 🔴 OPENING A DIFFERENT PROPOSAL CLEARS THE FORM.
                      Without this, the four fields are shared across every row:
                      after accepting proposal A, opening B showed A's version
                      id already filled and the Accept button already enabled,
                      and one click revised the WRONG formula version — recorded
                      in `formula_version_drivers` as authorised by B's
                      research. Found by the Supervisor. */}
                  <button
                    type="button"
                    className={SECONDARY}
                    disabled={!may}
                    onClick={() => {
                      const next = openId === row.id ? null : row.id;
                      setOpenId(next);
                      setVersionId("");
                      setReason("");
                      setHypothesis("");
                      setNote("");
                    }}
                  >
                    {openId === row.id ? "Cancel" : "Decide"}
                  </button>
                  {openId === row.id && (
                    <div className="mt-3 grid gap-2 border-t border-slate-200 pt-3">
                      <p className="text-xs text-slate-600">
                        Accepting revises a formula version through Formulations.
                        The revision must say what drove it and what you expect —
                        the database requires both of every version after the
                        first.
                      </p>
                      <label className={LABEL}>
                        Formula version to revise
                        <input
                          className={INPUT}
                          placeholder="version id"
                          value={versionId}
                          onChange={(event) => setVersionId(event.target.value)}
                        />
                      </label>
                      <label className={LABEL}>
                        Change reason
                        <input
                          className={INPUT}
                          value={reason}
                          onChange={(event) => setReason(event.target.value)}
                        />
                      </label>
                      <label className={LABEL}>
                        Technical hypothesis
                        <input
                          className={INPUT}
                          value={hypothesis}
                          onChange={(event) => setHypothesis(event.target.value)}
                        />
                      </label>
                      <label className={LABEL}>
                        Decision note
                        <input
                          className={INPUT}
                          value={note}
                          onChange={(event) => setNote(event.target.value)}
                        />
                      </label>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          className={BUTTON}
                          disabled={
                            writes.isPending ||
                            versionId === "" ||
                            reason === "" ||
                            hypothesis === ""
                          }
                          onClick={() =>
                            writes.accept(
                              row.id,
                              {
                                version_id: versionId,
                                change_reason: reason,
                                technical_hypothesis: hypothesis,
                                decision_note: note === "" ? undefined : note,
                              },
                              () => setOpenId(null),
                            )
                          }
                        >
                          Accept and revise
                        </button>
                        <button
                          type="button"
                          className={SECONDARY}
                          disabled={writes.isPending || note === ""}
                          onClick={() =>
                            writes.reject(row.id, note, () => setOpenId(null))
                          }
                        >
                          Reject
                        </button>
                      </div>
                      {note === "" && (
                        <p className="text-xs text-slate-600">
                          A rejection must say why — otherwise the next person
                          proposes the same thing.
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      <Feedback writes={writes} />
    </section>
  );
}

function ResearchCenterScreen() {
  const investigations = useInvestigations();
  const projects = useProjects<Project[]>([], (live) => live);
  const [openId, setOpenId] = useState<string | null>(null);
  const rows = investigations.data ?? [];
  const open = rows.find((row) => row.id === openId);

  return (
    <LiveOnlyPage
      title="Research Center"
      lede="Open a research workspace, gather graded evidence, record what it
            establishes and what it does not, and turn a hypothesis into an
            experiment proposal a chemist can accept."
      unavailable={investigations.unavailable}
      notInvented="research findings and experiment proposals"
    >
      {investigations.error ? (
        <DataSourceError error={investigations.error} />
      ) : investigations.unavailable !== null ? (
        <p className="text-sm text-slate-600">
          No research data can be shown until this build is pointed at an API.
        </p>
      ) : (
        <div className="grid gap-6">
          <OpenWorkspaceForm projects={projects.data ?? []} />

          <section>
            <h2 className="text-base font-semibold text-slate-900">Research workspaces</h2>
            {rows.length === 0 ? (
              <p className="mt-3 text-sm text-slate-600">
                {investigations.isLoading
                  ? "Loading workspaces…"
                  : "No research workspaces yet."}
              </p>
            ) : (
              <ul className="mt-3 grid gap-3">
                {rows.map((row) => (
                  <li key={row.id} className="rounded border border-slate-200 bg-white p-4">
                    <div className="flex flex-wrap items-baseline gap-2">
                      <h3 className="flex-1 text-sm font-semibold text-slate-900">
                        {row.investigation_code} — {row.title}
                      </h3>
                      <span className="text-xs text-slate-600">
                        {row.project_code ?? "Organization-wide"} · {row.status} ·{" "}
                        {row.question_count} question(s) · {row.evidence_count} card(s) ·{" "}
                        {row.finding_count} finding(s) · {row.proposal_count} proposal(s)
                      </span>
                      <button
                        type="button"
                        className={SECONDARY}
                        onClick={() => setOpenId(openId === row.id ? null : row.id)}
                      >
                        {openId === row.id ? "Close" : "Open"}
                      </button>
                    </div>
                    <MotivatedBy investigation={row} />
                    {openId === row.id && open !== undefined && (
                      <div className="mt-4 border-t border-slate-200 pt-4">
                        <Workspace investigation={open} />
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <FindingsRegister />
          <ProposalsRegister />
        </div>
      )}
    </LiveOnlyPage>
  );
}

export default function ResearchCenterPage() {
  // `useSearchParams` needs a Suspense boundary in an exported build, exactly
  // as `/failures/investigation`, `/testing/test` and `/laboratory/batch` do.
  // It is read here by the §25 contextual entry points.
  return (
    <Suspense fallback={<p className="p-6 text-sm text-slate-600">Loading…</p>}>
      <ResearchCenterScreen />
    </Suspense>
  );
}
