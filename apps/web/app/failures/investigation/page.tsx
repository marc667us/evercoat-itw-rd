"use client";

/**
 * One failure investigation — the workspace.
 *
 * 🔴 THIS IS WHERE §7's MOST CONSEQUENTIAL RULE IS EITHER KEPT OR LOST.
 *
 * *"AI hypothesis ≠ accepted root cause. Only a human moves it to accepted."*
 * Every hypothesis carries `origin` (`human` | `msd`) and `status`, and this
 * screen renders BOTH on every one, because a confidently-worded machine
 * suggestion sitting in a list beside three human ones, with nothing to tell
 * them apart, is the single worst thing this module can put in front of a
 * chemist. An MSD hypothesis is labelled, in words, not by a colour.
 *
 * The database agrees and enforces it: `failure_hypotheses_accepted_names_a_human`
 * refuses a row whose status is `accepted` with no `accepted_by`, so there is
 * no path — service, script or owner role — that produces an accepted root
 * cause with nobody's name on it.
 *
 * 🔴 EVIDENCE IS SHOWN WITH HOW IT BEARS, NOT MERELY THAT IT EXISTS.
 * `get_failure`'s own docstring says why: *"a screen showing only supporting
 * evidence would make every hypothesis look well-founded."* So each link
 * renders `supports` / `contradicts` / `inconclusive` beside the summary, and
 * contradicting evidence is not tucked away.
 *
 * 🔴 AND `accepted_root_cause` COMES FROM THE SERVER, not from a filter here.
 * Re-deriving it in the browser would be a second implementation of the most
 * consequential field in the module, free to disagree with the database — and
 * `failure_hypotheses_one_accepted_idx` guarantees the server's answer is
 * singular, which a client-side `.find()` could not.
 *
 * ⚠️ CONTROLS ARE GATED ON THE PERMISSION THEIR OWN ENDPOINT DECLARES, and the
 * server still decides. `failure.investigate` proposes, links and raises;
 * `failure.accept_root_cause` accepts; `failure.close` closes. Measured on the
 * seeded realm 2026-08-27, those are held by different sets of roles — the
 * chemist who investigates does NOT hold `failure.accept_root_cause`, which is
 * the separation this screen has to make visible rather than flatten.
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { DataSourceError, LiveOnlyPage } from "@/components/ui/data-source-banner";
import { Absent } from "@/components/ui/record-link";
import { serverMessage } from "@/lib/api/client";
import { useFailure, useFailureActions } from "@/lib/api/hooks";
import type {
  Evidence,
  FailureDetail,
  Hypothesis,
  HypothesisEvidence,
} from "@/lib/api/failures";
import { permits, usePermissions } from "@/lib/permissions";

const INPUT =
  "mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm text-slate-900 " +
  "focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";
const LABEL = "block text-xs font-medium text-slate-700";
const BUTTON =
  "rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 " +
  "disabled:cursor-not-allowed disabled:bg-slate-300";
const BUTTON_QUIET =
  "rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 " +
  "hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400";

function words(value: string): string {
  return value.replace(/_/g, " ");
}

/**
 * Where a hypothesis came from, in words.
 *
 * 🔴 A WORD, NEVER A COLOUR OR A GLYPH ALONE. §11 forbids colour-only status
 * and the reason applies with more force here than to a traffic light: a
 * reader who misses that a hypothesis is machine-proposed may accept it as a
 * root cause, and §7 exists to stop exactly that.
 */
function OriginTag({ origin }: { origin: "human" | "msd" }) {
  if (origin === "human") {
    return (
      <span className="rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600">
        proposed by a person
      </span>
    );
  }
  return (
    <span className="rounded border border-amber-400 bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-900">
      MSD suggestion — requires technical review
    </span>
  );
}

/** How one piece of evidence bears on one hypothesis. */
function RelationTag({ relationship }: { relationship: string }) {
  const label =
    relationship === "supports"
      ? "supports"
      : relationship === "contradicts"
        ? "contradicts"
        : "inconclusive";
  return (
    <span className="rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-700">
      {label}
    </span>
  );
}

/**
 * One linked piece of evidence, and the control that corrects it.
 *
 * 🔴 A WRONG RELATIONSHIP USED TO BE PERMANENT. `UNIQUE (hypothesis_id,
 * evidence_id)` refused a re-link and nothing else could change it, so an
 * observation recorded as `supports` when it actually `contradicts` stayed that
 * way. On a screen whose header argues that showing only supporting evidence
 * makes every hypothesis look well-founded, that is the failure itself rather
 * than an inconvenience: the reading that FLATTERS the hypothesis was the one
 * that could not be taken back.
 *
 * ⚠️ CORRECTING IS NOT DELETING, AND THE SCREEN SAYS SO. The previous reading
 * and its author go into the append-only, hash-chained audit record; nothing is
 * erased. There is deliberately no unlink — removing an assertion is a delete of
 * investigation history, which §5 governs and which needs a retire column and a
 * migration. Evidence linked to the wrong hypothesis altogether is corrected to
 * `inconclusive` with a note saying so, which leaves a reader the truth rather
 * than a gap.
 */
function LinkedEvidence({
  link,
  hypothesisId,
  mayCorrect,
  pending,
  onRelabel,
}: {
  link: HypothesisEvidence;
  hypothesisId: string;
  mayCorrect: boolean;
  pending: boolean;
  onRelabel: (
    hypothesisId: string,
    evidenceId: string,
    relationship: "supports" | "contradicts" | "inconclusive",
    note: string,
    after: () => void,
  ) => void;
}) {
  const [correcting, setCorrecting] = useState(false);
  const [relationship, setRelationship] = useState(link.relationship);
  const [note, setNote] = useState(link.note ?? "");

  return (
    <li className="text-xs">
      <div className="flex flex-wrap items-baseline gap-2">
        <RelationTag relationship={link.relationship} />
        <span className="text-slate-800">{link.summary}</span>
        <span className="text-slate-500">({words(link.evidence_type)})</span>
        {link.origin === "msd" && <OriginTag origin="msd" />}
        {link.note !== null && <span className="text-slate-600">— {link.note}</span>}
        {mayCorrect && !correcting && (
          <button
            type="button"
            className="text-slate-700 underline underline-offset-2 hover:text-slate-900"
            onClick={() => setCorrecting(true)}
          >
            Correct how it bears
          </button>
        )}
      </div>

      {correcting && (
        <div className="mt-1 flex flex-wrap items-end gap-2">
          <div className="w-40">
            <label className={LABEL} htmlFor={`relabel-${hypothesisId}-${link.evidence_id}`}>
              How it bears
            </label>
            <select
              id={`relabel-${hypothesisId}-${link.evidence_id}`}
              className={INPUT}
              value={relationship}
              onChange={(e) =>
                setRelationship(e.target.value as "supports" | "contradicts" | "inconclusive")
              }
            >
              <option value="supports">supports</option>
              <option value="contradicts">contradicts</option>
              <option value="inconclusive">inconclusive</option>
            </select>
          </div>
          <div className="min-w-[14rem] flex-1">
            <label
              className={LABEL}
              htmlFor={`relabel-note-${hypothesisId}-${link.evidence_id}`}
            >
              Why the reading changed
            </label>
            <input
              id={`relabel-note-${hypothesisId}-${link.evidence_id}`}
              className={INPUT}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
          <button
            type="button"
            className={BUTTON_QUIET}
            disabled={pending}
            onClick={() =>
              onRelabel(hypothesisId, link.evidence_id, relationship, note.trim(), () =>
                setCorrecting(false),
              )
            }
          >
            Correct
          </button>
          <button
            type="button"
            className={BUTTON_QUIET}
            onClick={() => {
              // Restore what the server holds, so cancelling does not leave a
              // half-typed correction sitting in the control next time.
              setRelationship(link.relationship);
              setNote(link.note ?? "");
              setCorrecting(false);
            }}
          >
            Cancel
          </button>
          <p className="w-full text-slate-600">
            The previous reading, and who gave it, stay in the audit record.
            Nothing is deleted.
          </p>
        </div>
      )}
    </li>
  );
}

function HypothesisCard({
  hypothesis,
  evidencePool,
  mayInvestigate,
  mayAccept,
  pending,
  onAccept,
  onReject,
  onLink,
  onRelabel,
}: {
  hypothesis: Hypothesis;
  evidencePool: readonly Evidence[];
  mayInvestigate: boolean;
  mayAccept: boolean;
  pending: boolean;
  onAccept: (hypothesisId: string, rationale: string, after: () => void) => void;
  onReject: (hypothesisId: string, reason: string, after: () => void) => void;
  onLink: (
    hypothesisId: string,
    evidenceId: string,
    relationship: string,
    note: string,
    after: () => void,
  ) => void;
  onRelabel: (
    hypothesisId: string,
    evidenceId: string,
    relationship: "supports" | "contradicts" | "inconclusive",
    note: string,
    after: () => void,
  ) => void;
}) {
  const [rationale, setRationale] = useState("");
  const [reason, setReason] = useState("");
  const [evidenceId, setEvidenceId] = useState("");
  const [relationship, setRelationship] = useState("supports");
  const [note, setNote] = useState("");

  const settled = hypothesis.status === "accepted" || hypothesis.status === "rejected";

  // 🔴 EVIDENCE ALREADY LINKED TO THIS HYPOTHESIS IS NOT OFFERED AGAIN.
  //
  // Raised by the Supervisor. `quality.hypothesis_evidence` carries
  // `UNIQUE (hypothesis_id, evidence_id)` (migration 021) and `link_evidence`
  // does a plain INSERT with no ON CONFLICT — so re-linking the same piece,
  // which is what somebody does when they realise they labelled it `supports`
  // and it actually `contradicts`, came back as a raw constraint violation.
  //
  // ⚠️ AND THIS ONLY HALF-FIXES IT, WHICH IS WORTH SAYING PLAINLY. Offering an
  // already-linked item was the visible defect; the real gap is that there is
  // no UNLINK and no relabel, so a wrong relationship is permanent. On a screen
  // whose whole argument is that hiding contradicting evidence makes every
  // hypothesis look well-founded, a relationship that cannot be corrected is in
  // scope — and it needs a DELETE endpoint that does not exist. Filed rather
  // than invented here.
  const alreadyLinked = new Set(hypothesis.evidence.map((e) => e.evidence_id));
  const linkable = evidencePool.filter((e) => !alreadyLinked.has(e.id));

  return (
    <li className="rounded border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-baseline gap-2">
        <h3 className="flex-1 text-sm font-medium text-slate-900">{hypothesis.possible_cause}</h3>
        <OriginTag origin={hypothesis.origin} />
        <span className="rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600">
          {words(hypothesis.status)}
        </span>
        <span className="rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600">
          confidence {hypothesis.confidence}
        </span>
      </div>

      {hypothesis.mechanism !== null && (
        <p className="mt-1 text-sm text-slate-700">{hypothesis.mechanism}</p>
      )}
      {hypothesis.rejection_reason !== null && (
        <p className="mt-1 text-sm text-slate-700">
          <span className="font-medium">Rejected: </span>
          {hypothesis.rejection_reason}
        </p>
      )}

      {/* 🔴 CONTRADICTING EVIDENCE IS NOT HIDDEN. Listing only what supports a
          hypothesis is how every hypothesis comes to look well-founded. */}
      <div className="mt-3">
        <h4 className="text-xs font-semibold text-slate-700">Evidence</h4>
        {hypothesis.evidence.length === 0 ? (
          <p className="mt-1 text-xs text-slate-600">
            None linked. A hypothesis with no evidence is a suggestion.
          </p>
        ) : (
          <ul className="mt-1 space-y-1">
            {hypothesis.evidence.map((e) => (
              <LinkedEvidence
                key={e.evidence_id}
                link={e}
                hypothesisId={hypothesis.id}
                mayCorrect={mayInvestigate && !settled}
                pending={pending}
                onRelabel={onRelabel}
              />
            ))}
          </ul>
        )}
      </div>

      {mayInvestigate && !settled && linkable.length > 0 && (
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <div className="min-w-[14rem] flex-1">
            <label className={LABEL} htmlFor={`link-${hypothesis.id}`}>
              Link evidence
            </label>
            <select
              id={`link-${hypothesis.id}`}
              className={INPUT}
              value={evidenceId}
              onChange={(e) => setEvidenceId(e.target.value)}
            >
              <option value="">Choose a piece of evidence</option>
              {linkable.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.summary}
                </option>
              ))}
            </select>
          </div>
          <div className="w-40">
            <label className={LABEL} htmlFor={`rel-${hypothesis.id}`}>
              How it bears
            </label>
            {/* All three, never a supports-only control. The schema requires
                the field; offering one value would make it a formality. */}
            <select
              id={`rel-${hypothesis.id}`}
              className={INPUT}
              value={relationship}
              onChange={(e) => setRelationship(e.target.value)}
            >
              <option value="supports">supports</option>
              <option value="contradicts">contradicts</option>
              <option value="inconclusive">inconclusive</option>
            </select>
          </div>
          <div className="min-w-[12rem] flex-1">
            <label className={LABEL} htmlFor={`note-${hypothesis.id}`}>
              Note
            </label>
            <input
              id={`note-${hypothesis.id}`}
              className={INPUT}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
          <button
            type="button"
            className={BUTTON_QUIET}
            disabled={pending || evidenceId === ""}
            // 🔴 CLEARED ON SUCCESS, NOT ON CLICK. A failed link used to
            // discard the note with it.
            onClick={() =>
              onLink(hypothesis.id, evidenceId, relationship, note.trim(), () => {
                setEvidenceId("");
                setNote("");
              })
            }
          >
            Link
          </button>
        </div>
      )}

      {mayInvestigate && !settled && (
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <div className="min-w-[16rem] flex-1">
            <label className={LABEL} htmlFor={`reject-${hypothesis.id}`}>
              Reject this hypothesis — the reason stays on the record
            </label>
            <input
              id={`reject-${hypothesis.id}`}
              className={INPUT}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
          <button
            type="button"
            className={BUTTON_QUIET}
            disabled={pending || reason.trim().length < 3}
            onClick={() => onReject(hypothesis.id, reason.trim(), () => setReason(""))}
          >
            Reject
          </button>
        </div>
      )}

      {/* 🔴 ACCEPTANCE IS A SEPARATE PERMISSION AND A SEPARATE PERSON.
          `failure.accept_root_cause` is held by the Lead and the Director;
          `failure.investigate` by the Chemist and the Engineer. Measured
          2026-08-27. The chemist who proposed a cause does not sign it off,
          and this screen shows that by not offering the control. */}
      {mayAccept && !settled && (
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <div className="min-w-[16rem] flex-1">
            <label className={LABEL} htmlFor={`accept-${hypothesis.id}`}>
              Accept as root cause — rationale required
            </label>
            <input
              id={`accept-${hypothesis.id}`}
              className={INPUT}
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              placeholder="why the evidence supports this cause"
            />
          </div>
          <button
            type="button"
            className={BUTTON}
            // The server requires at least 3 characters. Matching it here is a
            // courtesy that avoids a round trip, never the enforcement.
            disabled={pending || rationale.trim().length < 3}
            // A refused acceptance keeps the rationale. A 403 from segregation
            // of duties is the common case and the text is the expensive part.
            onClick={() => onAccept(hypothesis.id, rationale.trim(), () => setRationale(""))}
          >
            Accept as root cause
          </button>
        </div>
      )}
    </li>
  );
}

function InvestigationWorkspace({ failure }: { failure: FailureDetail }) {
  const actions = useFailureActions(failure.id);
  const permissions = usePermissions();

  // Read off `app/api/failures.py`: hypotheses, evidence, evidence links,
  // rejections and actions all declare `failure.investigate`; the root cause
  // declares `failure.accept_root_cause`; closure declares `failure.close`.
  const mayInvestigate = permits(permissions, "failure.investigate");
  const mayAccept = permits(permissions, "failure.accept_root_cause");
  const mayClose = permits(permissions, "failure.close");

  const [cause, setCause] = useState("");
  const [mechanism, setMechanism] = useState("");
  const [confidence, setConfidence] = useState<"low" | "medium" | "high">("medium");
  const [evidenceType, setEvidenceType] = useState("previous_experiment");
  const [summary, setSummary] = useState("");
  const [actionType, setActionType] = useState("formula_revision");
  const [actionText, setActionText] = useState("");
  const [closure, setClosure] = useState("");

  // 🔴 `cancelled` IS SETTLED TOO. Raised by Codex: this read
  // `status !== "closed"`, so a cancelled investigation kept every control and
  // each one 409'd. `quality.failures.status` has six values (migration 021).
  const open = failure.status !== "closed" && failure.status !== "cancelled";

  // 🔴 AND ACCEPTANCE IS OFFERED ONCE PER INVESTIGATION, NOT ONCE PER
  // HYPOTHESIS. Also raised by Codex. Each card gated only on its OWN settled
  // state, so once a root cause was accepted the remaining `proposed`
  // hypotheses still showed "Accept as root cause" — and pressing one hits
  // `failure_hypotheses_one_accepted_idx`, which is a partial unique index and
  // therefore a hard refusal rather than a supersede.
  //
  // ⚠️ THIS IS COSMETIC, LIKE EVERY GATE ON THIS SCREEN. The index is the
  // guarantee; hiding the control just stops offering an action that cannot
  // work.
  const rootCauseSettled = failure.accepted_root_cause !== null;

  return (
    <div className="space-y-6">
      <section>
        <div className="flex flex-wrap items-baseline gap-2">
          <span className="text-xs font-medium tabular-nums text-slate-500">
            {failure.failure_code}
          </span>
          <h1 className="flex-1 text-lg font-semibold text-slate-900">{failure.title}</h1>
          <span className="rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600">
            {words(failure.severity)}
          </span>
          <span className="rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600">
            {words(failure.status)}
          </span>
        </div>
        {failure.description !== null && (
          <p className="mt-2 max-w-3xl text-sm text-slate-700">{failure.description}</p>
        )}

        <dl className="mt-3 grid gap-x-6 gap-y-1 text-xs text-slate-600 sm:grid-cols-3">
          <div className="flex gap-1.5">
            <dt className="font-medium text-slate-500">Opened</dt>
            <dd className="tabular-nums">{failure.opened_at.slice(0, 10)}</dd>
          </div>
          <div className="flex gap-1.5">
            <dt className="font-medium text-slate-500">Test</dt>
            <dd>
              {failure.test_id === null ? (
                <Absent what="not linked to a test" />
              ) : (
                // §2: a failed test must always be traceable to the formula and
                // batch that produced it. The link is that traceability made
                // usable rather than merely stored.
                <Link
                  href={`/testing/test?id=${failure.test_id}`}
                  className="underline underline-offset-2"
                >
                  open the test
                </Link>
              )}
            </dd>
          </div>
          <div className="flex gap-1.5">
            <dt className="font-medium text-slate-500">Formula version</dt>
            <dd>
              {failure.formula_version_id === null ? (
                <Absent what="not linked to a version" />
              ) : (
                <Link
                  href={`/formulations/formula?version=${failure.formula_version_id}`}
                  className="underline underline-offset-2"
                >
                  open the version
                </Link>
              )}
            </dd>
          </div>
        </dl>

        {/* 🔴 THE ACCEPTED ROOT CAUSE, STATED ONCE AND BY THE SERVER. */}
        <div className="mt-4 rounded border border-slate-300 bg-slate-50 p-3">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-700">
            Root cause
          </h2>
          {failure.accepted_root_cause === null ? (
            <p className="mt-1 text-sm text-slate-700">
              Not accepted. Hypotheses below are <strong>proposals</strong>, whatever
              their confidence — including any proposed by MSD.
            </p>
          ) : (
            <>
              <p className="mt-1 text-sm text-slate-900">
                {failure.accepted_root_cause.possible_cause}
              </p>
              <p className="mt-1 text-xs text-slate-600">
                Accepted by a person on{" "}
                {failure.accepted_root_cause.accepted_at?.slice(0, 10) ?? "an unrecorded date"}.
                Originally <OriginTag origin={failure.accepted_root_cause.origin} />
              </p>
            </>
          )}
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      <section>
        <h2 className="text-sm font-semibold text-slate-900">Hypotheses</h2>
        {failure.hypotheses.length === 0 ? (
          <p className="mt-1 text-sm text-slate-600">None proposed yet.</p>
        ) : (
          <ul className="mt-2 grid gap-3">
            {failure.hypotheses.map((h) => (
              <HypothesisCard
                key={h.id}
                hypothesis={h}
                evidencePool={failure.evidence}
                mayInvestigate={mayInvestigate && open}
                mayAccept={mayAccept && open && !rootCauseSettled}
                pending={actions.isPending}
                onAccept={actions.accept}
                onReject={actions.reject}
                onRelabel={(hypothesisId, evidenceId, relationship, note, after) =>
                  actions.relabel(
                    hypothesisId,
                    evidenceId,
                    relationship,
                    note === "" ? undefined : note,
                    after,
                  )
                }
                onLink={(hypothesisId, id, relationship, note, after) =>
                  actions.link(
                    hypothesisId,
                    {
                      evidence_id: id,
                      relationship: relationship as "supports" | "contradicts" | "inconclusive",
                      ...(note === "" ? {} : { note }),
                    },
                    after,
                  )
                }
              />
            ))}
          </ul>
        )}

        {mayInvestigate && open && (
          <div className="mt-3 grid max-w-2xl gap-2 rounded border border-slate-200 p-3">
            <p className="text-xs font-medium text-slate-700">Propose a hypothesis</p>
            <div>
              <label className={LABEL} htmlFor="cause">
                Possible cause
              </label>
              <input
                id="cause"
                className={INPUT}
                value={cause}
                onChange={(e) => setCause(e.target.value)}
              />
            </div>
            <div>
              <label className={LABEL} htmlFor="mechanism">
                Mechanism — how it would produce this failure
              </label>
              <input
                id="mechanism"
                className={INPUT}
                value={mechanism}
                onChange={(e) => setMechanism(e.target.value)}
              />
            </div>
            <div className="w-40">
              <label className={LABEL} htmlFor="confidence">
                Confidence
              </label>
              <select
                id="confidence"
                className={INPUT}
                value={confidence}
                onChange={(e) => setConfidence(e.target.value as "low" | "medium" | "high")}
              >
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
              </select>
            </div>
            {/* ⚠️ NO `origin` FIELD, DELIBERATELY. The server defaults it to
                `human`, and a form that could send `msd` would let a person
                file a machine's opinion under the machine's name — or the
                reverse. The label can only be wrong by a caller asserting it. */}
            <div>
              <button
                type="button"
                className={BUTTON}
                disabled={actions.isPending || cause.trim().length < 3}
                onClick={() =>
                  actions.propose(
                    {
                      possible_cause: cause.trim(),
                      confidence,
                      ...(mechanism.trim() === "" ? {} : { mechanism: mechanism.trim() }),
                    },
                    () => {
                      setCause("");
                      setMechanism("");
                    },
                  )
                }
              >
                Propose
              </button>
            </div>
          </div>
        )}
      </section>

      {/* ---------------------------------------------------------------- */}
      <section>
        <h2 className="text-sm font-semibold text-slate-900">Evidence</h2>
        {failure.evidence.length === 0 ? (
          <p className="mt-1 text-sm text-slate-600">None recorded.</p>
        ) : (
          <ul className="mt-2 space-y-2">
            {failure.evidence.map((e) => (
              <li key={e.id} className="rounded border border-slate-200 bg-white p-3">
                <div className="flex flex-wrap items-baseline gap-2">
                  <span className="text-sm text-slate-900">{e.summary}</span>
                  <span className="rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600">
                    {words(e.evidence_type)}
                  </span>
                  {e.origin === "msd" && <OriginTag origin="msd" />}
                </div>
                {e.detail !== null && <p className="mt-1 text-xs text-slate-700">{e.detail}</p>}
              </li>
            ))}
          </ul>
        )}

        {mayInvestigate && open && (
          <div className="mt-3 flex max-w-2xl flex-wrap items-end gap-2">
            <div className="w-52">
              <label className={LABEL} htmlFor="evidence-type">
                Type
              </label>
              <select
                id="evidence-type"
                className={INPUT}
                value={evidenceType}
                onChange={(e) => setEvidenceType(e.target.value)}
              >
                {[
                  "previous_experiment",
                  "literature",
                  "batch_deviation",
                  "material_lot_issue",
                  "test_trend",
                  "photograph",
                  "other",
                ].map((t) => (
                  <option key={t} value={t}>
                    {words(t)}
                  </option>
                ))}
              </select>
            </div>
            <div className="min-w-[16rem] flex-1">
              <label className={LABEL} htmlFor="evidence-summary">
                Summary
              </label>
              <input
                id="evidence-summary"
                className={INPUT}
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
              />
            </div>
            <button
              type="button"
              className={BUTTON_QUIET}
              disabled={actions.isPending || summary.trim().length < 3}
              onClick={() =>
                actions.addEvidence(
                  { evidence_type: evidenceType, summary: summary.trim() },
                  () => setSummary(""),
                )
              }
            >
              Record evidence
            </button>
          </div>
        )}
      </section>

      {/* ---------------------------------------------------------------- */}
      <section>
        <h2 className="text-sm font-semibold text-slate-900">Corrective actions</h2>
        {failure.actions.length === 0 ? (
          <p className="mt-1 text-sm text-slate-600">None raised.</p>
        ) : (
          <ul className="mt-2 space-y-2">
            {failure.actions.map((a) => (
              <li key={a.id} className="rounded border border-slate-200 bg-white p-3 text-sm">
                <div className="flex flex-wrap items-baseline gap-2">
                  <span className="rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600">
                    {words(a.action_type)}
                  </span>
                  <span className="rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600">
                    {words(a.status)}
                  </span>
                  {a.due_date !== null && (
                    <span className="text-xs tabular-nums text-slate-600">due {a.due_date}</span>
                  )}
                </div>
                <p className="mt-1 text-slate-800">{a.description}</p>
              </li>
            ))}
          </ul>
        )}

        {mayInvestigate && open && (
          <div className="mt-3 flex max-w-2xl flex-wrap items-end gap-2">
            <div className="w-52">
              <label className={LABEL} htmlFor="action-type">
                Action
              </label>
              <select
                id="action-type"
                className={INPUT}
                value={actionType}
                onChange={(e) => setActionType(e.target.value)}
              >
                {[
                  "formula_revision",
                  "repeat_test",
                  "process_change",
                  "material_change",
                  "start_doe",
                  "other",
                ].map((t) => (
                  <option key={t} value={t}>
                    {words(t)}
                  </option>
                ))}
              </select>
            </div>
            <div className="min-w-[16rem] flex-1">
              <label className={LABEL} htmlFor="action-description">
                What is to be done
              </label>
              <input
                id="action-description"
                className={INPUT}
                value={actionText}
                onChange={(e) => setActionText(e.target.value)}
              />
            </div>
            <button
              type="button"
              className={BUTTON_QUIET}
              disabled={actions.isPending || actionText.trim().length < 3}
              onClick={() =>
                actions.raiseAction(
                  { action_type: actionType, description: actionText.trim() },
                  () => setActionText(""),
                )
              }
            >
              Raise action
            </button>
          </div>
        )}
      </section>

      {/* ---------------------------------------------------------------- */}
      {failure.closure_summary !== null && (
        <section>
          <h2 className="text-sm font-semibold text-slate-900">Closure</h2>
          <p className="mt-1 max-w-3xl text-sm text-slate-700">{failure.closure_summary}</p>
        </section>
      )}

      {mayClose && open && (
        <section>
          <h2 className="text-sm font-semibold text-slate-900">Close this investigation</h2>
          <div className="mt-2 flex max-w-2xl flex-wrap items-end gap-2">
            <div className="min-w-[18rem] flex-1">
              <label className={LABEL} htmlFor="closure">
                Summary — what was concluded
              </label>
              <input
                id="closure"
                className={INPUT}
                value={closure}
                onChange={(e) => setClosure(e.target.value)}
              />
            </div>
            <button
              type="button"
              className={BUTTON}
              disabled={actions.isPending || closure.trim().length < 3}
              onClick={() => actions.close(closure.trim())}
            >
              Close
            </button>
          </div>
        </section>
      )}

      {/* 🔴 A CALLER WITH NONE OF THE THREE IS TOLD SO, rather than shown a
          page of headings with nothing under them. The three permissions are
          named because "why can I not do anything here?" has an answer a
          reader can take to an administrator. */}
      {!mayInvestigate && !mayAccept && !mayClose && (
        <p className="text-sm text-slate-600">
          You hold none of <code className="text-xs">failure.investigate</code>,{" "}
          <code className="text-xs">failure.accept_root_cause</code> or{" "}
          <code className="text-xs">failure.close</code>, so this investigation is
          read-only from here. The record above is complete; only the controls are
          withheld.
        </p>
      )}

      {actions.error !== null && (
        <p
          role="alert"
          className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900"
        >
          {serverMessage(actions.error)}
        </p>
      )}
      {actions.error === null && actions.lastAction !== null && (
        <p role="status" className="text-sm text-slate-700">
          Recorded: {actions.lastAction}.
        </p>
      )}
    </div>
  );
}

function InvestigationScreen() {
  const params = useSearchParams();
  const failureId = params.get("id") ?? "";
  const { data, isLoading, error, unavailable } = useFailure(failureId);

  return (
    <LiveOnlyPage
      title="Failure investigation"
      lede="Hypotheses, the evidence for and against each one, and the corrective
            actions raised from them. An AI hypothesis is never an accepted root
            cause — only a person accepts one, and the record says who."
      unavailable={unavailable}
      notInvented="failure investigations"
    >
      {failureId === "" ? (
        <p className="text-sm text-slate-600">
          No investigation chosen.{" "}
          <Link href="/failures" className="underline underline-offset-2">
            Open one from the queue.
          </Link>
        </p>
      ) : error !== null ? (
        <DataSourceError error={error} />
      ) : unavailable !== null ? (
        <p className="text-sm text-slate-600">
          This investigation cannot be shown until this build is pointed at an API.
        </p>
      ) : data === undefined ? (
        <p className="text-sm text-slate-600">
          {isLoading ? "Loading the investigation…" : "Not found."}
        </p>
      ) : (
        <InvestigationWorkspace failure={data} />
      )}
    </LiveOnlyPage>
  );
}

export default function InvestigationPage() {
  // `useSearchParams` needs a Suspense boundary in an exported build, exactly
  // as `/testing/test` and `/laboratory/batch` do.
  return (
    <Suspense fallback={<p className="p-6 text-sm text-slate-600">Loading…</p>}>
      <InvestigationScreen />
    </Suspense>
  );
}
