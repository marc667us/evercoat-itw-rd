"use client";

/**
 * Competitor intelligence — register a product, upload its label or a
 * photograph, and build the Composition Evidence Matrix from them.
 *
 * 🔴 THIS SCREEN NEVER SHOWS A COMPETITOR RECIPE.
 *
 * The specification is explicit that the application *"shall NEVER
 * automatically present an inferred competitor recipe as a known or verified
 * formula"*. What it shows is a matrix of CLAIMS, strongest first, each
 * carrying how it is known and how far it can be trusted — and the server's
 * own disclaimer rendered verbatim above it. Reading the matrix gives a
 * candidate composition, which is what was asked for; no line of it pretends
 * to be more than it is.
 *
 * 🔴 THREE ENTRY MODES, AS PEERS.
 *
 *   1. Upload the LABEL.
 *   2. Upload a PHOTOGRAPH of the product.
 *   3. Type what you read, with no document at all.
 *
 * All three land in the same matrix. The third is `manual_observation` — not
 * `inference`, because a person reading a tin is observing, not reasoning.
 * What it cannot be is `verified`, since there is nothing anybody else can
 * re-check, and the database refuses that combination outright.
 *
 * ⚠️ UPLOADING DOES NOT FILL THE MATRIX IN. There is no automatic extraction:
 * that was a deliberate choice on 2026-08-28 (no OCR dependency, and neither
 * installed Ollama model reads images). The file is stored as evidence a claim
 * can CITE, and a person records what it says. A screen that implied otherwise
 * would be inventing components on somebody's product.
 */

import { useState } from "react";

import { DataSourceError, LiveOnlyPage } from "@/components/ui/data-source-banner";
import { serverMessage } from "@/lib/api/client";
import {
  useCompetitorBenchmarks,
  useCompetitorDocuments,
  useCompetitorProducts,
  useCompetitorSamples,
  useCompetitorWrites,
  useCompositionMatrix,
  useProjects,
} from "@/lib/api/hooks";
import type { Project } from "@/lib/api/projects";
import {
  EVIDENCE_GRADES,
  EVIDENCE_SOURCES,
  type CompetitorProduct,
  type EvidenceRow,
} from "@/lib/api/competitors";
import { permits, usePermissions } from "@/lib/permissions";

/**
 * What each act on this screen requires, mirrored from `app/api/competitors.py`.
 *
 * 🔴 THIS SCREEN HAD NO PERMISSION CHECK ANYWHERE IN IT. Six controls, all live
 * for every reader, including the grading select -- which is `compliance.review_sds`,
 * held by ONE of the ten roles. Nine people out of ten could pick a confidence
 * level off a dropdown and watch the row snap back on a 403.
 *
 * ⚠️ `benchmark` NEEDS BOTH, AND THE SERVER MEANS *BOTH*. `POST /{id}/benchmarks`
 * is `require_permission("material.edit", "test.view", require_all=True)`, unlike
 * every other route here, which take ANY of the codes they name. Mirroring it as
 * one code would have offered the control to somebody holding just one -- so it is
 * two checks, and the shape of the constant says which.
 *
 * A mirror, and mirrors drift: this exists so the screen can avoid offering a
 * control the server will refuse, never as the thing that decides.
 */
const MAY = {
  /** Register a product, upload a document, register a sample, record evidence. */
  record: "material.edit",
  /** Grade a piece of evidence. */
  grade: "compliance.review_sds",
  /** Record a benchmark -- ALL of these, not any. */
  benchmark: ["material.edit", "test.view"],
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
 * Confidence, as colour AND icon AND word.
 *
 * CLAUDE.md §11 forbids colour-only status, and here it matters more than
 * usual: the difference between a verified disclosure and a model's guess is
 * the entire point of the matrix, and a reader who cannot see colour must get
 * the same answer.
 */
const CONFIDENCE: Record<
  EvidenceRow["confidence"],
  { icon: string; label: string; className: string }
> = {
  verified: {
    icon: "✓",
    label: "Verified",
    className: "border-emerald-300 bg-emerald-50 text-emerald-900",
  },
  supported: {
    icon: "+",
    label: "Supported",
    className: "border-sky-300 bg-sky-50 text-sky-900",
  },
  probable: {
    icon: "~",
    label: "Probable",
    className: "border-amber-300 bg-amber-50 text-amber-900",
  },
  possible: {
    icon: "?",
    label: "Possible",
    className: "border-slate-300 bg-slate-50 text-slate-800",
  },
  unknown: {
    icon: "·",
    label: "Unknown",
    className: "border-slate-300 bg-white text-slate-600",
  },
};

function concentration(row: EvidenceRow): string {
  if (row.is_balance) return "the balance";
  const { concentration_low: low, concentration_high: high } = row;
  if (low === null && high === null) return "not disclosed";
  if (low !== null && high !== null) return low === high ? `${low}%` : `${low}–${high}%`;
  return `${low ?? high}%`;
}

const CONFIDENCE_ORDER: readonly EvidenceRow["confidence"][] = [
  "unknown",
  "possible",
  "probable",
  "supported",
  "verified",
];

function MatrixRow({
  row,
  onGrade,
  isPending,
}: {
  row: EvidenceRow;
  onGrade: (evidenceId: string, confidence: string) => void;
  isPending: boolean;
}) {
  const mayGrade = permits(usePermissions(), MAY.grade);
  const confidence = CONFIDENCE[row.confidence];
  const source = EVIDENCE_SOURCES.find((s) => s.id === row.evidence_source);
  return (
    <li className="rounded border border-slate-200 bg-white p-3">
      <div className="flex flex-wrap items-baseline gap-2">
        <span
          className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${confidence.className}`}
        >
          <span aria-hidden="true">{confidence.icon}</span> {confidence.label}
        </span>
        <h3 className="flex-1 text-sm font-semibold text-slate-900">{row.component_name}</h3>
        <span className="text-sm tabular-nums text-slate-800">{concentration(row)}</span>
      </div>
      <p className="mt-1 text-xs text-slate-600">
        {source?.label ?? row.evidence_source} · grade {row.evidence_grade}
        {row.cas_number !== null ? ` · CAS ${row.cas_number}` : ""}
        {row.component_function !== null ? ` · ${row.component_function}` : ""}
      </p>
      {row.source_document_title !== null && (
        <p className="mt-1 text-xs text-slate-600">
          From {row.source_document_type}: {row.source_document_title}
          {row.source_locator !== null ? ` (${row.source_locator})` : ""}
        </p>
      )}
      {row.rationale !== null && (
        <p className="mt-1 text-xs text-slate-700">{row.rationale}</p>
      )}

      {/* 🔴 THE REVIEW CONTROL. `POST /evidence/{id}/grade` HAD NO CALLER AT
          ALL (Supervisor, 2026-08-28): the client function and the hook both
          existed and nothing rendered either, so every claim stayed `possible`
          forever, four of the five CONFIDENCE branches above could never
          appear, and `compliance.review_sds` -- the permission this slice
          exists to give an enforcement point -- had no browser path.

          Shown to everybody on purpose. §6: frontend permission checks are
          cosmetic and the server re-enforces; the database additionally
          refuses unless the named verifier actually holds the permission. */}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <label className="text-xs text-slate-600" htmlFor={`grade-${row.id}`}>
          Confidence
        </label>
        <select
          id={`grade-${row.id}`}
          className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-900"
          value={row.confidence}
          disabled={isPending || !mayGrade}
          onChange={(event) => onGrade(row.id, event.target.value)}
        >
          {CONFIDENCE_ORDER.map((level) => (
            <option key={level} value={level}>
              {CONFIDENCE[level].label}
            </option>
          ))}
        </select>
        {row.confidence !== "verified" && (
          <span className="text-[11px] text-slate-500">
            Verified needs a document or laboratory source and a reviewer holding
            compliance.review_sds.
          </span>
        )}
      </div>
    </li>
  );
}

function ProductWorkspace({ product }: { product: CompetitorProduct }) {
  const permissions = usePermissions();
  const mayRecord = permits(permissions, MAY.record);
  // Both, because the route is `require_all=True`. See `MAY`.
  const mayBenchmark = MAY.benchmark.every((code) => permits(permissions, code));
  const matrix = useCompositionMatrix(product.id);
  const documents = useCompetitorDocuments(product.id);
  const samples = useCompetitorSamples(product.id);
  const benchmarks = useCompetitorBenchmarks(product.id);
  // 🔴 A BENCHMARK NEEDS A PROJECT, AND ASKING FOR A UUID IS NOT ASKING.
  // The register-a-member form on Projects still demands one typed by hand
  // and it is a standing complaint; this form does not repeat it.
  const projectList = useProjects<Project[]>([], (live) => live);
  const writes = useCompetitorWrites();

  const [file, setFile] = useState<File | null>(null);
  // 🔴 REMOUNTS THE FILE INPUT AFTER A SUCCESSFUL UPLOAD. An uncontrolled
  // `<input type="file">` keeps displaying the chosen filename, and
  // re-selecting the SAME file fires no `change` event -- so a user whose
  // upload failed could not retry it without picking a different file first.
  const [uploadNonce, setUploadNonce] = useState(0);
  const [documentType, setDocumentType] = useState("label");
  const [docTitle, setDocTitle] = useState("");

  const [component, setComponent] = useState("");
  const [cas, setCas] = useState("");
  const [low, setLow] = useState("");
  const [high, setHigh] = useState("");
  const [isBalance, setIsBalance] = useState(false);
  const [evidenceSource, setEvidenceSource] = useState("manual_observation");
  const [grade, setGrade] = useState("C");
  const [sourceDocumentId, setSourceDocumentId] = useState("");
  const [sampleId, setSampleId] = useState("");
  const [locator, setLocator] = useState("");
  const [rationale, setRationale] = useState("");

  const [sampleReference, setSampleReference] = useState("");
  const [acquiredOn, setAcquiredOn] = useState("");
  const [batchMarking, setBatchMarking] = useState("");
  const [sampleNotes, setSampleNotes] = useState("");

  const [benchProject, setBenchProject] = useState("");
  const [benchAttribute, setBenchAttribute] = useState("");
  const [benchTheirs, setBenchTheirs] = useState("");
  const [benchOurs, setBenchOurs] = useState("");
  const [benchGap, setBenchGap] = useState("");

  const needsDocument = evidenceSource === "document";
  // 🔴 BOTH SOURCES MUST CITE A SAMPLE, AND ONE OF THEM COULD NOT BE WRITTEN
  // AT ALL (Codex P2, 2026-08-28).
  //
  // `composition_evidence_laboratory_shape` requires a sample OR a test on
  // every `laboratory` row. This form has no test selector and was not
  // sending a sample either, so choosing "Our own laboratory result" produced
  // a request the DATABASE REFUSED every time — an option on the menu that
  // could never succeed.
  //
  // And an observation with no sample is the unattributable row this screen
  // was changed to eliminate. Offering the citation but not requiring it left
  // the default doing exactly what it always did.
  const needsSample =
    evidenceSource === "manual_observation" || evidenceSource === "laboratory";
  const docs = documents.data ?? [];
  const tins = samples.data ?? [];
  const comparisons = benchmarks.data ?? [];
  const projects = projectList.data ?? [];

  return (
    <div className="grid gap-6">
      {/* 🔴 THIS COMPONENT'S OWN `useCompetitorWrites()` HAD NO ERROR OUTPUT
          (Supervisor, 2026-08-28). The page's only alert is bound to the
          SEPARATE mutation instance that registers products, so upload,
          sample, evidence, grade and benchmark all failed in silence: the
          button simply re-enabled. That hid a duplicate sample reference, a
          constraint refusal, and worst of all the 503 the upload route raises
          when NO MALWARE VERDICT COULD BE OBTAINED -- the one status the API
          docstring insists must never read as success. */}
      {writes.error !== null && (
        <p
          role="alert"
          className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900"
        >
          {serverMessage(writes.error)}
        </p>
      )}

      <section aria-labelledby="upload-heading">
        <h3 id="upload-heading" className="text-sm font-semibold text-slate-900">
          Upload a label or a photograph
        </h3>
        <p className="mt-1 text-xs text-slate-600">
          Stored through the same controlled document register a Safety Data Sheet
          goes through: validated against its real bytes, malware-scanned,
          checksummed. It is kept as evidence a claim can <em>cite</em> — it does
          not fill the matrix in by itself.
        </p>
        <div className="mt-3 grid gap-3 rounded border border-slate-200 bg-white p-4 sm:grid-cols-2">
          <div>
            <label className={LABEL} htmlFor="doc-kind">
              What is it
            </label>
            <select
              id="doc-kind"
              className={INPUT}
              value={documentType}
              onChange={(event) => setDocumentType(event.target.value)}
            >
              <option value="label">The product label</option>
              <option value="product_image">A photograph of the product</option>
              <option value="SDS">Their published Safety Data Sheet</option>
              <option value="TDS">Their technical data sheet</option>
              <option value="literature">Product literature</option>
              <option value="patent">A patent</option>
            </select>
          </div>
          <div>
            <label className={LABEL} htmlFor="doc-title">
              Title
            </label>
            <input
              id="doc-title"
              className={INPUT}
              value={docTitle}
              onChange={(event) => setDocTitle(event.target.value)}
              placeholder="Label, 1L tin, 2026 packaging"
            />
          </div>
          <div className="sm:col-span-2">
            <label className={LABEL} htmlFor="doc-file">
              The file
            </label>
            <input
              key={uploadNonce}
              id="doc-file"
              type="file"
              className={`${INPUT} file:mr-3 file:rounded file:border-0 file:bg-slate-100 file:px-3 file:py-1 file:text-sm`}
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </div>
          <div className="sm:col-span-2">
            <button
              type="button"
              className={BUTTON}
              disabled={
                writes.isPending || file === null || docTitle.trim() === "" || !mayRecord
              }
              onClick={() => {
                if (file === null) return;
                writes.upload(product.id, file, documentType, docTitle.trim(), () => {
                  setFile(null);
                  setDocTitle("");
                  setUploadNonce((n) => n + 1);
                });
              }}
            >
              Upload
            </button>
          </div>
        </div>

        {docs.length > 0 && (
          <ul className="mt-3 grid gap-2">
            {docs.map((doc) => (
              <li key={doc.id} className="text-xs text-slate-700">
                <span className="rounded border border-slate-300 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-600">
                  {doc.document_type}
                </span>{" "}
                {doc.title}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="samples-heading">
        <h3 id="samples-heading" className="text-sm font-semibold text-slate-900">
          Physical samples held
        </h3>
        <p className="mt-1 text-xs text-slate-600">
          The tins we actually have. Registering one is what lets an observation
          say <em>which</em> tin it was read from — a claim that cannot name its
          source cannot be re-checked by anybody else.
        </p>
        <div className="mt-3 grid gap-3 rounded border border-slate-200 bg-white p-4 sm:grid-cols-2">
          <div>
            <label className={LABEL} htmlFor="sample-ref">
              Reference
            </label>
            <input
              id="sample-ref"
              className={INPUT}
              value={sampleReference}
              onChange={(event) => setSampleReference(event.target.value)}
              placeholder="COMP-2026-014"
            />
          </div>
          <div>
            <label className={LABEL} htmlFor="sample-acquired">
              Acquired on
            </label>
            <input
              id="sample-acquired"
              type="date"
              className={INPUT}
              value={acquiredOn}
              onChange={(event) => setAcquiredOn(event.target.value)}
            />
          </div>
          <div>
            <label className={LABEL} htmlFor="sample-batch">
              Batch or lot marking
            </label>
            <input
              id="sample-batch"
              className={INPUT}
              value={batchMarking}
              onChange={(event) => setBatchMarking(event.target.value)}
              placeholder="As printed on the tin"
            />
          </div>
          <div>
            <label className={LABEL} htmlFor="sample-notes">
              Condition and provenance
            </label>
            <input
              id="sample-notes"
              className={INPUT}
              value={sampleNotes}
              onChange={(event) => setSampleNotes(event.target.value)}
              placeholder="Sealed, bought at retail"
            />
          </div>
          <div className="sm:col-span-2">
            <button
              type="button"
              className={BUTTON}
              disabled={writes.isPending || sampleReference.trim() === "" || !mayRecord}
              onClick={() =>
                writes.registerSample(
                  product.id,
                  {
                    sample_reference: sampleReference.trim(),
                    ...(acquiredOn ? { acquired_on: acquiredOn } : {}),
                    ...(batchMarking.trim() ? { batch_marking: batchMarking.trim() } : {}),
                    ...(sampleNotes.trim() ? { observations: sampleNotes.trim() } : {}),
                  },
                  () => {
                    setSampleReference("");
                    setAcquiredOn("");
                    setBatchMarking("");
                    setSampleNotes("");
                  },
                )
              }
            >
              Register the sample
            </button>
          </div>
        </div>

        {samples.error !== null ? (
          <DataSourceError error={samples.error} />
        ) : tins.length === 0 ? (
          <p className="mt-3 text-sm text-slate-600">
            No samples registered. An observation recorded now cannot name what
            it was read from.
          </p>
        ) : (
          <ul className="mt-3 grid gap-2">
            {tins.map((tin) => (
              <li
                key={tin.id}
                className="rounded border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700"
              >
                <span className="font-medium text-slate-900">{tin.sample_reference}</span>
                {tin.acquired_on !== null && <> · acquired {tin.acquired_on}</>}
                {tin.batch_marking !== null && <> · batch {tin.batch_marking}</>}{" "}
                · {tin.evidence_count} claim{tin.evidence_count === 1 ? "" : "s"} cite
                {tin.evidence_count === 1 ? "s" : ""} it
                {tin.observations !== null && (
                  <span className="mt-1 block text-slate-600">{tin.observations}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="claim-heading">
        <h3 id="claim-heading" className="text-sm font-semibold text-slate-900">
          Record what it contains
        </h3>
        <p className="mt-1 text-xs text-slate-600">
          Every claim is recorded as <strong>possible</strong>. Only a reviewer
          holding <code className="text-[11px]">compliance.review_sds</code> can
          raise one to verified, and only when it cites a document or a
          laboratory result.
        </p>
        <div className="mt-3 grid gap-3 rounded border border-slate-200 bg-white p-4 sm:grid-cols-2">
          <div>
            <label className={LABEL} htmlFor="ev-component">
              Component
            </label>
            <input
              id="ev-component"
              className={INPUT}
              value={component}
              onChange={(event) => setComponent(event.target.value)}
              placeholder="Styrene"
            />
          </div>
          <div>
            <label className={LABEL} htmlFor="ev-cas">
              CAS number
            </label>
            <input
              id="ev-cas"
              className={INPUT}
              value={cas}
              onChange={(event) => setCas(event.target.value)}
              placeholder="100-42-5"
            />
          </div>
          <div>
            <label className={LABEL} htmlFor="ev-low">
              From (%)
            </label>
            {/* Text, not number: a float would round the disclosed range. */}
            <input
              id="ev-low"
              className={INPUT}
              inputMode="decimal"
              value={low}
              onChange={(event) => setLow(event.target.value)}
            />
          </div>
          <div>
            <label className={LABEL} htmlFor="ev-high">
              To (%)
            </label>
            <input
              id="ev-high"
              className={INPUT}
              inputMode="decimal"
              value={high}
              onChange={(event) => setHigh(event.target.value)}
            />
          </div>
          <div>
            <label className={LABEL} htmlFor="ev-source">
              How is this known
            </label>
            <select
              id="ev-source"
              className={INPUT}
              value={evidenceSource}
              onChange={(event) => setEvidenceSource(event.target.value)}
            >
              {EVIDENCE_SOURCES.map((source) => (
                <option key={source.id} value={source.id}>
                  {source.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={LABEL} htmlFor="ev-grade">
              Evidence grade
            </label>
            <select
              id="ev-grade"
              className={INPUT}
              value={grade}
              onChange={(event) => setGrade(event.target.value)}
            >
              {EVIDENCE_GRADES.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.label}
                </option>
              ))}
            </select>
          </div>

          {needsDocument && (
            <div className="sm:col-span-2">
              <label className={LABEL} htmlFor="ev-doc">
                Which document
              </label>
              <select
                id="ev-doc"
                className={INPUT}
                value={sourceDocumentId}
                onChange={(event) => setSourceDocumentId(event.target.value)}
              >
                <option value="">Choose one of the uploads above…</option>
                {docs.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.document_type} — {doc.title}
                  </option>
                ))}
              </select>
              {docs.length === 0 && (
                <p className="mt-1 text-xs text-slate-600">
                  Nothing is uploaded yet, so no claim can cite a document.
                </p>
              )}
            </div>
          )}

          {needsSample && (
            <div className="sm:col-span-2">
              <label className={LABEL} htmlFor="ev-sample">
                Which sample {evidenceSource === "laboratory" ? "was tested" : "did you read"}
              </label>
              <select
                id="ev-sample"
                className={INPUT}
                value={sampleId}
                onChange={(event) => setSampleId(event.target.value)}
              >
                {/* No "not recorded" option: the row is refused without one. */}
                <option value="">
                  {tins.length === 0
                    ? "Register a sample above first"
                    : "Choose the sample"}
                </option>
                {tins.map((tin) => (
                  <option key={tin.id} value={tin.id}>
                    {tin.sample_reference}
                    {tin.batch_marking !== null ? ` — batch ${tin.batch_marking}` : ""}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="sm:col-span-2">
            <label className={LABEL} htmlFor="ev-locator">
              Where exactly {needsDocument ? "in the document" : "on the product"}
            </label>
            <input
              id="ev-locator"
              className={INPUT}
              value={locator}
              onChange={(event) => setLocator(event.target.value)}
              placeholder="Section 3, ingredient table / back of tin, small print"
            />
          </div>
          <div className="sm:col-span-2">
            {/* "The balance" is a real disclosure and is not a number. The
                matrix has always rendered it and no control ever set it. */}
            <label className="flex items-center gap-2 text-xs text-slate-700">
              <input
                type="checkbox"
                checked={isBalance}
                onChange={(event) => {
                  setIsBalance(event.target.checked);
                  if (event.target.checked) {
                    // The constraint forbids a range alongside it, so the form
                    // clears the range rather than sending a refused row.
                    setLow("");
                    setHigh("");
                  }
                }}
              />
              This component is stated as &ldquo;the balance&rdquo;, not a percentage
            </label>
          </div>
          <div className="sm:col-span-2">
            <label className={LABEL} htmlFor="ev-rationale">
              What you saw, or what you reasoned from
            </label>
            <textarea
              id="ev-rationale"
              className={INPUT}
              rows={2}
              value={rationale}
              onChange={(event) => setRationale(event.target.value)}
            />
          </div>

          <div className="sm:col-span-2">
            <button
              type="button"
              className={BUTTON}
              disabled={
                writes.isPending ||
                !mayRecord ||
                component.trim() === "" ||
                (needsDocument && sourceDocumentId === "") ||
                // Refused by the database without it, so the form refuses too
                // rather than sending a request that cannot succeed.
                (needsSample && sampleId === "") ||
                /* An observation or an inference must say what it rests on --
                   the database refuses it otherwise, so the form should too
                   rather than sending a request that cannot succeed. */
                (["manual_observation", "inference", "model"].includes(evidenceSource) &&
                  rationale.trim() === "")
              }
              onClick={() =>
                writes.recordEvidence(
                  product.id,
                  {
                    component_name: component.trim(),
                    evidence_source: evidenceSource,
                    evidence_grade: grade,
                    ...(cas.trim() ? { cas_number: cas.trim() } : {}),
                    ...(isBalance ? { is_balance: true } : {}),
                    ...(!isBalance && low.trim() ? { concentration_low: low.trim() } : {}),
                    ...(!isBalance && high.trim() ? { concentration_high: high.trim() } : {}),
                    ...(needsDocument ? { source_document_id: sourceDocumentId } : {}),
                    ...(needsSample ? { sample_id: sampleId } : {}),
                    ...(locator.trim() ? { source_locator: locator.trim() } : {}),
                    ...(rationale.trim() ? { rationale: rationale.trim() } : {}),
                  },
                  () => {
                    setComponent("");
                    setSampleId("");
                    setIsBalance(false);
                    setCas("");
                    setLow("");
                    setHigh("");
                    setLocator("");
                    setRationale("");
                  },
                )
              }
            >
              Add to the evidence matrix
            </button>
          </div>
        </div>
      </section>

      <section aria-labelledby="matrix-heading">
        <h3 id="matrix-heading" className="text-sm font-semibold text-slate-900">
          Composition Evidence Matrix
        </h3>
        {matrix.error !== null ? (
          <DataSourceError error={matrix.error} />
        ) : matrix.data === undefined ? (
          <p className="mt-2 text-sm text-slate-600">
            {matrix.isLoading ? "Loading the matrix…" : ""}
          </p>
        ) : (
          <>
            {/* 🔴 THE SERVER'S OWN WORDS, RENDERED VERBATIM. Not a sentence
                this screen composes: a screen that forgot it would be
                presenting an inferred recipe as a known one. */}
            <p className="mt-2 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              {matrix.data.disclaimer}
            </p>

            {Object.keys(matrix.data.summary).length > 0 && (
              <p className="mt-2 text-xs text-slate-700">
                {Object.entries(matrix.data.summary)
                  .map(([key, count]) => `${count} ${key}`)
                  .join(" · ")}
              </p>
            )}

            {matrix.data.rows.length === 0 ? (
              <p className="mt-3 text-sm text-slate-600">
                Nothing recorded yet. Upload a label or type what you can read,
                above.
              </p>
            ) : (
              <ul className="mt-3 grid gap-2">
                {matrix.data.rows.map((row) => (
                  <MatrixRow
                    key={row.id}
                    row={row}
                    onGrade={writes.grade}
                    isPending={writes.isPending}
                  />
                ))}
              </ul>
            )}
          </>
        )}
      </section>

      <section aria-labelledby="benchmark-heading">
        <h3 id="benchmark-heading" className="text-sm font-semibold text-slate-900">
          Measured comparisons
        </h3>
        <p className="mt-1 text-xs text-slate-600">
          How our work compares on one attribute. ⚠️ The gap is stated in
          words and no verdict colour is shown: Testing owns GREEN, YELLOW and
          RED, and a second disposition invented here would drift from it.
        </p>
        <div className="mt-3 grid gap-3 rounded border border-slate-200 bg-white p-4 sm:grid-cols-2">
          <div>
            <label className={LABEL} htmlFor="bm-project">
              Project
            </label>
            {/* A caller with `material.view` but not `project.view` gets a 403
                here. Unsurfaced, that rendered as an empty menu beside a
                permanently disabled button -- a working feature reading as a
                broken one. */}
            {projectList.error !== null && (
              <p className="mt-1 text-xs text-red-800">
                The project list could not be loaded, so a comparison cannot be
                recorded: {serverMessage(projectList.error)}
              </p>
            )}
            <select
              id="bm-project"
              className={INPUT}
              value={benchProject}
              onChange={(event) => setBenchProject(event.target.value)}
            >
              <option value="">Choose the project</option>
              {projects.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.project_code} — {item.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={LABEL} htmlFor="bm-attribute">
              Attribute
            </label>
            <input
              id="bm-attribute"
              className={INPUT}
              value={benchAttribute}
              onChange={(event) => setBenchAttribute(event.target.value)}
              placeholder="Sand-through time"
            />
          </div>
          <div>
            <label className={LABEL} htmlFor="bm-theirs">
              Theirs
            </label>
            <input
              id="bm-theirs"
              className={INPUT}
              value={benchTheirs}
              onChange={(event) => setBenchTheirs(event.target.value)}
              placeholder="18 min"
            />
          </div>
          <div>
            <label className={LABEL} htmlFor="bm-ours">
              Ours
            </label>
            <input
              id="bm-ours"
              className={INPUT}
              value={benchOurs}
              onChange={(event) => setBenchOurs(event.target.value)}
              placeholder="22 min"
            />
          </div>
          <div className="sm:col-span-2">
            <label className={LABEL} htmlFor="bm-gap">
              What the gap is, in words
            </label>
            <textarea
              id="bm-gap"
              className={INPUT}
              rows={2}
              value={benchGap}
              onChange={(event) => setBenchGap(event.target.value)}
              placeholder="Theirs sands about four minutes sooner at 20 °C."
            />
          </div>
          <div className="sm:col-span-2">
            <button
              type="button"
              className={BUTTON}
              disabled={
                writes.isPending ||
                !mayBenchmark ||
                benchProject === "" ||
                benchAttribute.trim() === "" ||
                benchGap.trim() === ""
              }
              onClick={() =>
                writes.recordBenchmark(
                  product.id,
                  {
                    project_id: benchProject,
                    attribute: benchAttribute.trim(),
                    gap_summary: benchGap.trim(),
                    ...(benchTheirs.trim() ? { competitor_value: benchTheirs.trim() } : {}),
                    ...(benchOurs.trim() ? { our_value: benchOurs.trim() } : {}),
                  },
                  () => {
                    setBenchAttribute("");
                    setBenchTheirs("");
                    setBenchOurs("");
                    setBenchGap("");
                  },
                )
              }
            >
              Record the comparison
            </button>
          </div>
        </div>

        {benchmarks.error !== null ? (
          <DataSourceError error={benchmarks.error} />
        ) : comparisons.length === 0 ? (
          <p className="mt-3 text-sm text-slate-600">No comparisons recorded yet.</p>
        ) : (
          <ul className="mt-3 grid gap-2">
            {comparisons.map((row) => (
              <li
                key={row.id}
                className="rounded border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700"
              >
                <span className="font-medium text-slate-900">{row.attribute}</span>
                {row.project_code !== null && <> · {row.project_code}</>}
                <span className="mt-1 block">
                  Theirs {row.competitor_value ?? "not stated"} · ours{" "}
                  {row.our_value ?? "not stated"}
                </span>
                <span className="mt-1 block text-slate-600">{row.gap_summary}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

export default function CompetitorsPage() {
  const mayRecord = permits(usePermissions(), MAY.record);
  const products = useCompetitorProducts();
  const writes = useCompetitorWrites();
  const [openId, setOpenId] = useState<string | null>(null);
  const [manufacturer, setManufacturer] = useState("");
  const [productName, setProductName] = useState("");

  const rows: CompetitorProduct[] = products.data ?? [];
  const open = rows.find((p) => p.id === openId);

  return (
    <LiveOnlyPage
      title="Competitor Intelligence"
      lede="Register a competitor product, upload its label or a photograph of it,
            and build an evidence-based picture of what it contains. Every claim
            records how it is known — this is never presented as a known formula."
      unavailable={products.unavailable}
      notInvented="competitor products"
    >
      {products.error !== null ? (
        <DataSourceError error={products.error} />
      ) : products.unavailable !== null ? (
        <p className="text-sm text-slate-600">
          No competitor data can be shown until this build is pointed at an API.
        </p>
      ) : (
        <div className="grid gap-6">
          {writes.error !== null && (
            <p
              role="alert"
              className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900"
            >
              {serverMessage(writes.error)}
            </p>
          )}

          <section aria-labelledby="register-heading">
            <h2 id="register-heading" className="text-sm font-semibold text-slate-900">
              Register a competitor product
            </h2>
            <div className="mt-3 grid gap-3 rounded border border-slate-200 bg-white p-4 sm:grid-cols-3">
              <div>
                <label className={LABEL} htmlFor="cp-manufacturer">
                  Manufacturer
                </label>
                <input
                  id="cp-manufacturer"
                  className={INPUT}
                  value={manufacturer}
                  onChange={(event) => setManufacturer(event.target.value)}
                />
              </div>
              <div>
                <label className={LABEL} htmlFor="cp-name">
                  Product
                </label>
                <input
                  id="cp-name"
                  className={INPUT}
                  value={productName}
                  onChange={(event) => setProductName(event.target.value)}
                />
              </div>
              <div className="flex items-end">
                <button
                  type="button"
                  className={BUTTON}
                  disabled={
                    writes.isPending ||
                    !mayRecord ||
                    manufacturer.trim() === "" ||
                    productName.trim() === ""
                  }
                  onClick={() =>
                    writes.registerProduct(
                      {
                        manufacturer: manufacturer.trim(),
                        product_name: productName.trim(),
                      },
                      () => {
                        setManufacturer("");
                        setProductName("");
                      },
                    )
                  }
                >
                  Register
                </button>
              </div>
            </div>
          </section>

          <section aria-labelledby="products-heading">
            <h2 id="products-heading" className="text-sm font-semibold text-slate-900">
              Competitor products
            </h2>
            {rows.length === 0 ? (
              <p className="mt-3 text-sm text-slate-600">
                {products.isLoading
                  ? "Loading…"
                  : "None registered yet. Register one above, then upload its label."}
              </p>
            ) : (
              <ul className="mt-3 grid gap-3">
                {rows.map((product) => (
                  <li
                    key={product.id}
                    className="rounded border border-slate-200 bg-white p-4"
                  >
                    <div className="flex flex-wrap items-baseline gap-2">
                      <h3 className="flex-1 text-sm font-semibold text-slate-900">
                        {product.manufacturer} — {product.product_name}
                      </h3>
                      <span className="text-xs text-slate-600">
                        {product.document_count} document(s) ·{" "}
                        {product.evidence_count} claim(s)
                      </span>
                      <button
                        type="button"
                        className={SECONDARY}
                        onClick={() =>
                          setOpenId(openId === product.id ? null : product.id)
                        }
                      >
                        {openId === product.id ? "Close" : "Open"}
                      </button>
                    </div>
                    {openId === product.id && open !== undefined && (
                      <div className="mt-4 border-t border-slate-200 pt-4">
                        <ProductWorkspace product={open} />
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </LiveOnlyPage>
  );
}
