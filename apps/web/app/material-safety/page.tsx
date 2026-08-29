"use client";

/**
 * Material Safety Data & Research Center — the landing workspace.
 *
 * 🔴 WRITTEN OUT IN FULL, EVERYWHERE, AND THAT IS A CONTRACT.
 *
 * `MSD` in this product means the **Material Science & Development
 * Assistant** — a different capability, with its own tables, its own
 * permission and its own stored conversations. The specification for this one
 * writes "Material Safety Data" out all 48 times it uses it, and so does every
 * heading here. Two things that both abbreviate to MSD would make
 * authorization, audit and conversation history ambiguous forever.
 *
 * 🔴 THIS SCREEN REPORTS RECORD STATE. IT DOES NOT ASSESS HAZARD.
 *
 * The rule comes from `agents/tools/safety.py` and binds the whole
 * capability: *"'RM-104 is restricted, its SDS is missing' are facts read out
 * of columns. 'RM-104 is safe to use at 4%' is a compliance determination."*
 * So an alert says what CHANGED — "2 hazard classification(s) added" — and
 * never what it means. The meaning is the `compliance.review_sds` holder's
 * act, recorded through the approval engine, and this screen is where they
 * start it.
 *
 * 🔴 EVERY WRITE ENDPOINT HAS A CONTROL HERE, AND THE FIRST VERSION DID NOT.
 *
 * It shipped `POST /interpretations`, `POST .../alerts` and
 * `POST .../safety-reviews` with nothing in the browser able to reach them —
 * "a route with no caller is the same defect as a table with no writer", which
 * this project counted 23 instances of on 2026-08-24, reintroduced by the very
 * slice whose plan forbade it in red letters. Codex found it in review.
 *
 * ⚠️ `compliance.review_sds` HAS EXISTED, UNENFORCED, SINCE SLICE 1. It was
 * seeded in migration 002 and read by nothing. The queue below is its first
 * enforcement point in the product's history.
 */

import { useState } from "react";

import { DataSourceError, LiveOnlyPage } from "@/components/ui/data-source-banner";
import { serverMessage } from "@/lib/api/client";
import {
  useComparableRevisions,
  useInterpretableDocuments,
  usePendingInterpretations,
  useSafetyActions,
  useSafetyAlerts,
  useSafetyWrites,
} from "@/lib/api/hooks";
import type {
  ComparableRevision,
  ComponentInput,
  HazardInput,
  InterpretableDocument,
  PendingInterpretation,
  SafetyAlert,
} from "@/lib/api/material-safety";
import { permits, usePermissions } from "@/lib/permissions";

/**
 * What each act on this screen requires, mirrored from `app/api/material_safety.py`.
 *
 * 🔴 EVERY CONTROL ON THIS SCREEN WAS OFFERED TO EVERY READER. The prose above
 * each section already said "Requires `material.edit`" / "Requires
 * `compliance.review_sds`" -- and then the buttons were live for everybody, so
 * the screen stated the rule and did not apply it. `compliance.review_sds` is
 * held by ONE role of ten; nine people out of ten were being handed four
 * controls that answer 403 after they have typed the form in.
 *
 * ⚠️ A MIRROR, AND MIRRORS DRIFT. This exists so the screen can avoid offering
 * a control the server will refuse, never as the thing that decides.
 * `tests/auth/test_material_safety_routes.py` asserts the server side; if the
 * two disagree the server is right and this is the bug.
 */
const MAY = {
  /** `POST /interpretations` -- transcribe a sheet. */
  record: "material.edit",
  /** Confirming a reading, raising alerts, opening a safety review. */
  review: "compliance.review_sds",
  /** Acknowledging is deliberately the READ permission -- see `AlertRow`. */
  acknowledge: "material.view",
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

/**
 * Severity, as colour AND icon AND text.
 *
 * CLAUDE.md §11: no colour-only status. A reader with deuteranopia, or one
 * printing the page, must get the same answer — so the glyph and the word do
 * the work and the colour reinforces them.
 */
const SEVERITY: Record<
  SafetyAlert["severity"],
  { icon: string; label: string; className: string }
> = {
  critical: { icon: "✕", label: "Critical", className: "border-red-300 bg-red-50 text-red-900" },
  high: { icon: "!", label: "High", className: "border-amber-300 bg-amber-50 text-amber-900" },
  informational: {
    icon: "i",
    label: "Informational",
    className: "border-slate-300 bg-slate-50 text-slate-800",
  },
};

/**
 * Record what a Safety Data Sheet says.
 *
 * 🔴 THE DOCUMENT IS CHOSEN FROM A LIST, NEVER TYPED AS A UUID.
 *
 * The endpoint takes a `document_id` and a `material_id`. Two text boxes would
 * have been a control nobody could realistically operate — this project has
 * already logged that as a defect on the screen that adds a project member.
 * `/interpretations/candidates` returns only documents `materials.usable_documents`
 * still returns, so the form cannot offer a choice the database will refuse.
 *
 * ⚠️ CONCENTRATIONS ARE TEXT INPUTS AND STAY STRINGS. `type="number"` hands
 * back a JavaScript float and would round a disclosed range before it reached
 * PostgreSQL's `NUMERIC(7,4)`. CLAUDE.md §5 forbids float on a controlled
 * record, and "10.0000" is also what the manufacturer actually disclosed.
 */
function RecordReading({
  documents,
  pending,
  onRecord,
}: {
  documents: readonly InterpretableDocument[];
  pending: boolean;
  onRecord: (
    doc: InterpretableDocument,
    revision: string,
    manufacturer: string,
    hazards: HazardInput[],
    components: ComponentInput[],
    clear: () => void,
  ) => void;
}) {
  const may = permits(usePermissions(), MAY.record);
  const [documentId, setDocumentId] = useState("");
  const [revision, setRevision] = useState("");
  const [manufacturer, setManufacturer] = useState("");
  const [hazardClass, setHazardClass] = useState("");
  const [hazardCode, setHazardCode] = useState("");
  const [componentName, setComponentName] = useState("");
  const [low, setLow] = useState("");
  const [high, setHigh] = useState("");

  const chosen = documents.find((d) => d.document_id === documentId);

  const clear = () => {
    setDocumentId("");
    setRevision("");
    setManufacturer("");
    setHazardClass("");
    setHazardCode("");
    setComponentName("");
    setLow("");
    setHigh("");
  };

  return (
    <div className="rounded border border-slate-200 bg-white p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className={LABEL} htmlFor="sds-document">
            Safety Data Sheet
          </label>
          <select
            id="sds-document"
            className={INPUT}
            value={documentId}
            onChange={(event) => setDocumentId(event.target.value)}
          >
            <option value="">Choose a sheet that has not been read yet…</option>
            {documents.map((doc) => (
              <option key={doc.document_id} value={doc.document_id}>
                {doc.material_code} — {doc.material_name} · {doc.title}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className={LABEL} htmlFor="sds-revision">
            Revision, as the manufacturer labels it
          </label>
          <input
            id="sds-revision"
            className={INPUT}
            value={revision}
            onChange={(event) => setRevision(event.target.value)}
            placeholder="Rev 4.1"
          />
        </div>
        <div>
          <label className={LABEL} htmlFor="sds-manufacturer">
            Manufacturer named on the sheet
          </label>
          <input
            id="sds-manufacturer"
            className={INPUT}
            value={manufacturer}
            onChange={(event) => setManufacturer(event.target.value)}
          />
        </div>

        <div>
          <label className={LABEL} htmlFor="sds-hazard-class">
            Hazard classification
          </label>
          <input
            id="sds-hazard-class"
            className={INPUT}
            value={hazardClass}
            onChange={(event) => setHazardClass(event.target.value)}
            placeholder="Skin sensitisation"
          />
        </div>
        <div>
          <label className={LABEL} htmlFor="sds-hazard-code">
            H-code
          </label>
          <input
            id="sds-hazard-code"
            className={INPUT}
            value={hazardCode}
            onChange={(event) => setHazardCode(event.target.value)}
            placeholder="H317"
          />
        </div>

        <div className="sm:col-span-2">
          <label className={LABEL} htmlFor="sds-component">
            Disclosed component
          </label>
          <input
            id="sds-component"
            className={INPUT}
            value={componentName}
            onChange={(event) => setComponentName(event.target.value)}
            placeholder="Styrene"
          />
        </div>
        <div>
          <label className={LABEL} htmlFor="sds-low">
            Concentration from (%)
          </label>
          {/* Text, not number. See the component header. */}
          <input
            id="sds-low"
            className={INPUT}
            inputMode="decimal"
            value={low}
            onChange={(event) => setLow(event.target.value)}
            placeholder="10"
          />
        </div>
        <div>
          <label className={LABEL} htmlFor="sds-high">
            Concentration to (%)
          </label>
          <input
            id="sds-high"
            className={INPUT}
            inputMode="decimal"
            value={high}
            onChange={(event) => setHigh(event.target.value)}
            placeholder="25"
          />
        </div>
      </div>

      <p className="mt-3 text-xs text-slate-600">
        A range, not a value: a sheet disclosing &ldquo;10&ndash;25%&rdquo; is recorded as
        both bounds. Storing the midpoint would invent a precision the manufacturer
        withheld.
      </p>

      <button
        type="button"
        className={`${BUTTON} mt-3`}
        disabled={pending || chosen === undefined || !may}
        onClick={() => {
          if (chosen === undefined) return;
          const hazards: HazardInput[] = hazardClass.trim()
            ? [
                {
                  hazard_class: hazardClass.trim(),
                  ...(hazardCode.trim() ? { hazard_code: hazardCode.trim() } : {}),
                },
              ]
            : [];
          const components: ComponentInput[] = componentName.trim()
            ? [
                {
                  component_name: componentName.trim(),
                  ...(low.trim() ? { concentration_low: low.trim() } : {}),
                  ...(high.trim() ? { concentration_high: high.trim() } : {}),
                },
              ]
            : [];
          onRecord(chosen, revision.trim(), manufacturer.trim(), hazards, components, clear);
        }}
      >
        Record the reading
      </button>
      <p className="mt-1 text-xs text-slate-600">
        It is stored as <strong>pending technical review</strong>. Recording a sheet is
        not confirming it.
      </p>
    </div>
  );
}

function AlertRow({
  alert,
  pending,
  onAcknowledge,
  onOpenReview,
}: {
  alert: SafetyAlert;
  pending: boolean;
  onAcknowledge: (id: string) => void;
  onOpenReview: (alert: SafetyAlert) => void;
}) {
  const permissions = usePermissions();
  // 🔴 THE TWO BUTTONS IN THIS ROW ARE NOT THE SAME ACT AND ARE NOT THE SAME
  // GATE. Acknowledging is `material.view` -- anyone who can SEE the alert may
  // record that they have seen it, which is the point of an acknowledgement.
  // Opening a safety review is `compliance.review_sds`, held by one role.
  // Gating the row on one permission would either hide an acknowledgement from
  // the eight roles it exists for, or offer a review to all of them.
  const mayAcknowledge = permits(permissions, MAY.acknowledge);
  const mayReview = permits(permissions, MAY.review);
  const severity = SEVERITY[alert.severity];
  return (
    <li className="rounded border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-baseline gap-2">
        <span
          className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${severity.className}`}
        >
          <span aria-hidden="true">{severity.icon}</span> {severity.label}
        </span>
        <h3 className="flex-1 text-sm font-semibold text-slate-900">
          {alert.material_code ?? "A material"}
          {alert.material_name ? ` — ${alert.material_name}` : ""}
        </h3>
        <span className="text-xs text-slate-600">
          {alert.project_code} · {alert.project_name}
        </span>
      </div>

      {/* WHAT CHANGED, not what it means. See the file header. */}
      <p className="mt-2 text-sm text-slate-800">{alert.change_summary}</p>

      <p className="mt-1 text-xs text-slate-600">
        A revised Safety Data Sheet affects work in this project. This is a record of
        the change; the hazard assessment is the compliance review.
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        {alert.acknowledged_at === null ? (
          <button
            type="button"
            className={SECONDARY}
            disabled={pending || !mayAcknowledge}
            onClick={() => onAcknowledge(alert.id)}
          >
            Acknowledge
          </button>
        ) : (
          <p role="status" className="text-xs text-slate-600">
            {/* Acknowledging is not clearing: the alert stays, with a name and a
                time on it, so a change nobody acted on cannot disappear. */}
            Acknowledged. This alert stays on the record.
          </p>
        )}
        {/* 🔴 THE CONTROL FOR `POST .../safety-reviews`, WHICH HAD NONE.
            It opens a route through the ONE shared approval engine and lands in
            /approvals beside every other pending signature. Requires
            `compliance.review_sds`; the server refuses anybody else. */}
        <button
          type="button"
          className={SECONDARY}
          disabled={pending || !mayReview}
          onClick={() => onOpenReview(alert)}
        >
          Open a safety review on {alert.project_code}
        </button>
      </div>
    </li>
  );
}

function PendingRow({
  item,
  pending,
  onReview,
}: {
  item: PendingInterpretation;
  pending: boolean;
  onReview: (id: string, accept: boolean) => void;
}) {
  const may = permits(usePermissions(), MAY.review);
  return (
    <li className="rounded border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-baseline gap-2">
        <h3 className="flex-1 text-sm font-semibold text-slate-900">
          {item.material_code} — {item.material_name}
        </h3>
        {item.supplier_revision !== null && (
          <span className="rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600">
            {item.supplier_revision}
          </span>
        )}
      </div>
      <p className="mt-1 text-xs text-slate-600">
        {item.manufacturer ?? "Manufacturer not stated"}
        {item.effective_date !== null ? ` · effective ${item.effective_date}` : ""}
      </p>
      <p className="mt-2 text-xs text-slate-700">
        Recorded from the sheet and <strong>not yet confirmed</strong>. Until a reviewer
        accepts it, it is a transcription rather than confirmed safety data.
      </p>
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          className={BUTTON}
          disabled={pending || !may}
          onClick={() => onReview(item.id, true)}
        >
          Confirm reading
        </button>
        <button
          type="button"
          className={SECONDARY}
          disabled={pending || !may}
          onClick={() => onReview(item.id, false)}
        >
          Reject reading
        </button>
      </div>
    </li>
  );
}

export default function MaterialSafetyPage() {
  const mayReview = permits(usePermissions(), MAY.review);
  const alerts = useSafetyAlerts();
  const queue = usePendingInterpretations();
  const candidates = useInterpretableDocuments();
  const comparable = useComparableRevisions();
  const actions = useSafetyActions();
  const writes = useSafetyWrites();
  const [actedOn, setActedOn] = useState<string | null>(null);

  const alertRows: SafetyAlert[] = alerts.data ?? [];
  const queueRows: PendingInterpretation[] = queue.data ?? [];
  const candidateRows: InterpretableDocument[] = candidates.data ?? [];
  const comparableRows: ComparableRevision[] = comparable.data ?? [];
  const busy = actions.isPending || writes.isPending;

  return (
    <LiveOnlyPage
      title="Material Safety Data &amp; Research Center"
      lede="Safety Data Sheets read into structured hazard information, what
            changed between revisions, and which projects, formulas and open
            laboratory batches a change reaches. This screen reports what is on
            record; the hazard assessment is the compliance review."
      unavailable={alerts.unavailable}
      notInvented="safety data"
    >
      {alerts.error !== null ? (
        <DataSourceError error={alerts.error} />
      ) : alerts.unavailable !== null ? (
        <p className="text-sm text-slate-600">
          No safety data can be shown until this build is pointed at an API.
        </p>
      ) : (
        <div className="grid gap-8">
          {/* Beside the controls rather than at the foot of the page: a queue can
              be a hundred rows long, and a refusal nobody can see reads as a
              button that did nothing. */}
          {(actions.error !== null || writes.error !== null) && (
            <p
              role="alert"
              className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900"
            >
              {serverMessage(actions.error ?? writes.error!)}
            </p>
          )}
          {writes.error === null && writes.lastResult !== null && (
            <p
              role="status"
              className="rounded border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-800"
            >
              {writes.lastResult.kind === "recorded" &&
                "Reading recorded. It is pending technical review."}
              {writes.lastResult.kind === "review" &&
                "Safety review opened. It is now in the approvals queue."}
              {/* 🔴 ZERO IS A REAL ANSWER AND IS SAID PLAINLY. Raising alerts on
                  a revision that changed nothing substantive returns none, and a
                  screen that said "done" would hide that. */}
              {writes.lastResult.kind === "alerts" &&
                (writes.lastResult.count === 0
                  ? "No alerts raised — nothing substantive changed between those two readings."
                  : `${writes.lastResult.count} safety alert(s) raised, one per affected project.`)}
            </p>
          )}

          <section aria-labelledby="record-heading">
            <h2 id="record-heading" className="text-sm font-semibold text-slate-900">
              Record a Safety Data Sheet reading
            </h2>
            <p className="mt-1 text-xs text-slate-600">
              Requires <code className="text-[11px]">material.edit</code>. Only sheets
              that are approved, scanned clean, unexpired and not superseded can be
              read — the database refuses anything else.
            </p>
            <div className="mt-3">
              {candidates.error !== null ? (
                <p className="text-sm text-slate-600">{serverMessage(candidates.error)}</p>
              ) : candidateRows.length === 0 ? (
                <p className="text-sm text-slate-600">
                  {candidates.isLoading
                    ? "Loading sheets…"
                    : "Every usable Safety Data Sheet on file has already been read."}
                </p>
              ) : (
                <RecordReading
                  documents={candidateRows}
                  pending={busy}
                  onRecord={(doc, revision, manufacturer, hazards, components, clear) => {
                    setActedOn(doc.document_id);
                    writes.record(
                      {
                        document_id: doc.document_id,
                        material_id: doc.material_id,
                        ...(revision ? { supplier_revision: revision } : {}),
                        ...(manufacturer ? { manufacturer } : {}),
                        ...(hazards.length ? { hazards } : {}),
                        ...(components.length ? { components } : {}),
                      },
                      clear,
                    );
                  }}
                />
              )}
            </div>
          </section>

          <section aria-labelledby="revision-heading">
            <h2 id="revision-heading" className="text-sm font-semibold text-slate-900">
              Compare a revision and raise alerts
            </h2>
            <p className="mt-1 text-xs text-slate-600">
              Requires <code className="text-[11px]">compliance.review_sds</code>. Finds
              which formulas contain the material, which projects those belong to, and
              which laboratory batches are still open — then raises one alert per
              affected project and notifies its lead.
            </p>
            {comparable.error !== null ? (
              <p className="mt-3 text-sm text-slate-600">{serverMessage(comparable.error)}</p>
            ) : comparableRows.length === 0 ? (
              <p className="mt-3 text-sm text-slate-600">
                {comparable.isLoading
                  ? "Loading revisions…"
                  : /* Not "no revisions exist" — it means no material has TWO
                       readings yet, so there is nothing to compare against. */
                    "No material has two recorded readings yet, so there is no revision to compare."}
              </p>
            ) : (
              <ul className="mt-3 grid gap-3">
                {comparableRows.map((row) => (
                  <li
                    key={row.current_id}
                    className="rounded border border-slate-200 bg-white p-4"
                  >
                    <h3 className="text-sm font-semibold text-slate-900">
                      {row.material_code} — {row.material_name}
                    </h3>
                    <p className="mt-1 text-xs text-slate-600">
                      {row.previous_revision ?? "an earlier reading"} →{" "}
                      {row.current_revision ?? "the newest reading"}
                    </p>
                    <button
                      type="button"
                      className={`${SECONDARY} mt-3`}
                      disabled={busy || !mayReview}
                      onClick={() => {
                        setActedOn(row.current_id);
                        writes.raise(row.current_id, row.previous_id);
                      }}
                    >
                      Compare and raise alerts
                    </button>
                    {row.current_review_state === "pending_review" && (
                      <p className="mt-1 text-xs text-slate-600">
                        This reading has not been confirmed yet. Alerts raised from an
                        unconfirmed transcription say what changed, not that it is
                        correct.
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="alerts-heading">
            <h2 id="alerts-heading" className="text-sm font-semibold text-slate-900">
              Safety alerts
            </h2>
            <p className="mt-1 text-xs text-slate-600">
              Raised when a revised Safety Data Sheet changes hazard information for a
              material used in an active project.
            </p>
            {alertRows.length === 0 ? (
              <p className="mt-3 text-sm text-slate-600">
                {alerts.isLoading
                  ? "Loading alerts…"
                  : /* An empty list is "none you can reach", not "none exist".
                       Alerts are scoped by project membership, so a restricted
                       project's alerts are invisible here by design. */
                    "No safety alerts on projects you can reach. Alerts on restricted projects you are not a member of are not shown."}
              </p>
            ) : (
              <ul className="mt-3 grid gap-3">
                {alertRows.map((alert) => (
                  <AlertRow
                    key={alert.id}
                    alert={alert}
                    pending={busy && actedOn === alert.id}
                    onAcknowledge={(id) => {
                      setActedOn(id);
                      actions.acknowledge(id);
                    }}
                    onOpenReview={(item) => {
                      setActedOn(item.id);
                      // 🔴 `sds_version_id`, NOT `item.id`. The review is opened
                      // against the REVISION; sending the alert's own id failed
                      // the foreign key on every press.
                      writes.openReview(
                        item.sds_version_id,
                        item.project_id,
                        `Safety data sheet change: ${item.change_summary}`,
                      );
                    }}
                  />
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="queue-heading">
            <h2 id="queue-heading" className="text-sm font-semibold text-slate-900">
              Awaiting technical review
            </h2>
            <p className="mt-1 text-xs text-slate-600">
              Requires <code className="text-[11px]">compliance.review_sds</code>. A
              transcription stays pending until a reviewer confirms it — it is never
              treated as confirmed safety data on the strength of having been typed in.
            </p>
            {queue.error !== null ? (
              /* A 403 here is the ordinary case for nine of ten roles, and it is not
                 an outage. The server's own message is surfaced, not translated. */
              <p className="mt-3 text-sm text-slate-600">{serverMessage(queue.error)}</p>
            ) : queueRows.length === 0 ? (
              <p className="mt-3 text-sm text-slate-600">
                {queue.isLoading ? "Loading the queue…" : "Nothing is awaiting review."}
              </p>
            ) : (
              <ul className="mt-3 grid gap-3">
                {queueRows.map((item) => (
                  <PendingRow
                    key={item.id}
                    item={item}
                    pending={busy && actedOn === item.id}
                    onReview={(id, accept) => {
                      setActedOn(id);
                      actions.review(id, accept);
                    }}
                  />
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </LiveOnlyPage>
  );
}
