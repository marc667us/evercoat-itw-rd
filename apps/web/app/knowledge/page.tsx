"use client";

/**
 * The knowledge library — the screen MSD's answers link to.
 *
 * 🔴 THIS SCREEN MUST NEVER IMPLY THE LIBRARY UNDERSTOOD THE QUESTION.
 *
 * The default embedder is LEXICAL (`apps/api/app/core/embedding.py`): it
 * places two passages together when they SHARE WORDS. It does not know that
 * "adhesion" and "bonding" are related and it never will until the neural
 * model ADR-013 names is installed. Every word of copy here is chosen against
 * that constraint — "matched on shared words", never "found what you meant" —
 * because a search box is exactly the surface where a user supplies the
 * assumption of comprehension for free.
 *
 * 🔴 AND IT MUST NEVER PRESENT A PASSAGE AS A CONCLUSION.
 *
 * Results are QUOTATIONS from documents somebody uploaded. §7 requires MSD's
 * answers to carry evidence links precisely so a reader can disbelieve them;
 * the same reasoning applies to a raw search, so every result names its
 * document, its position in it, and its classification.
 *
 * WHY THERE IS NO DEMONSTRATION FALLBACK
 * --------------------------------------
 * `LiveOnlyPage`, not `DataPage`. `demo-data.json` has no knowledge documents
 * and must not gain any: this is the text the assistant quotes back as sourced
 * evidence, so a fabricated "standard" would reach an answer wearing a real
 * document's clothes. An empty screen that explains itself is the honest
 * state, and it is the same judgement Laboratory and Testing already make
 * about invented measurements.
 */

import { useMemo, useState } from "react";

import { LiveOnlyPage } from "@/components/ui/data-source-banner";
import { ApiError, serverMessage } from "@/lib/api/client";
import {
  useIngestKnowledgeDocument,
  useKnowledgeDocuments,
  useKnowledgeSearch,
} from "@/lib/api/hooks";
import type {
  KnowledgeDocument,
  KnowledgeDocumentPage,
  KnowledgePassage,
} from "@/lib/api/knowledge";

/** Matches `documents_source_check` in migration 042 and `SOURCES` in the route. */
const SOURCES = [
  "internal_note",
  "material_document",
  "standard",
  "procedure",
  "external",
] as const;

/**
 * The lattice, ordered, from migration 039.
 *
 * "" is offered FIRST and means "I have not decided", which the server answers
 * with the ceiling. That is not a UI nicety: preselecting a value here would
 * make whatever the form happened to default to the effective classification
 * of every document nobody thought about, and the whole point of the column's
 * `DIRECTOR_CONTROLLED` default is that an undecided document is maximally
 * restricted rather than conveniently readable.
 */
const CLASSIFICATIONS = [
  "PUBLIC",
  "INTERNAL",
  "CONFIDENTIAL",
  "R&D_RESTRICTED",
  "FORMULA_RESTRICTED",
  "DIRECTOR_CONTROLLED",
] as const;

/**
 * How a cosine distance is described to a person.
 *
 * 🔴 THREE BANDS, NOT A PERCENTAGE. Rendering `(1 - distance) * 100` as a
 * "relevance score" would be a precise-looking number with nothing behind it:
 * the value depends entirely on which embedder produced the vectors, and the
 * lexical default's distances are not comparable to a neural model's. A band
 * says what can honestly be said — this matched a lot of words, or few.
 *
 * The boundaries are the ones MEASURED for `HashingEmbedding` when the
 * assistant's own threshold was calibrated: related queries landed at
 * 0.496–0.719 and unrelated at 0.767–0.816.
 */
function overlapBand(distance: number): { label: string; tone: string } {
  if (distance <= 0.6) {
    return { label: "Strong word overlap", tone: "text-emerald-700" };
  }
  if (distance <= 0.74) {
    return { label: "Some word overlap", tone: "text-amber-700" };
  }
  return { label: "Weak word overlap", tone: "text-slate-500" };
}

/**
 * A classification, as a plain chip.
 *
 * 🔴 DELIBERATELY *NOT* `StatusBadge`. That component renders §10's derived
 * green/yellow/red test disposition, and it carries screen-reader prefixes
 * like "Failed" and "Conditional". A CONFIDENTIAL document is not a failing
 * test, and borrowing the traffic light for it would put safety-critical
 * vocabulary on a field that has nothing to do with whether a result passed.
 *
 * The lattice is ordered — PUBLIC < INTERNAL < CONFIDENTIAL < R&D_RESTRICTED
 * < FORMULA_RESTRICTED < DIRECTOR_CONTROLLED (migration 039) — so the shading
 * ascends with sensitivity. §11 forbids colour as the sole indicator, and the
 * label is always the text of the code itself, so the colour only reinforces
 * something already written.
 *
 * 🔴 AND IT IS A HANDLING LABEL, NOT A LOCK. Nothing filters reads on it.
 *
 * No RLS policy in this schema consults `classification` — migration 039 §2
 * decides that deliberately: classification is a property of the DATA, while
 * WHO may see it is answered by permissions and project membership, and
 * collapsing the two is a defect this project has found six times. There is no
 * per-user clearance level for it to be compared against.
 *
 * So an organization-wide DIRECTOR_CONTROLLED document IS readable by every
 * `knowledge.view` holder in the organization. A reviewer read this screen's
 * first draft as implying otherwise, which is why the tooltip says what the
 * chip means rather than leaving a coloured badge to suggest it.
 */
const CLASSIFICATION_TONE: Record<string, string> = {
  PUBLIC: "bg-slate-100 text-slate-700 border-slate-300",
  INTERNAL: "bg-sky-50 text-sky-800 border-sky-200",
  CONFIDENTIAL: "bg-amber-50 text-amber-900 border-amber-200",
  // 🔴 "R&D_RESTRICTED", with an ampersand. It was written R_AND_D_RESTRICTED
  // here and matched NOTHING -- migration 039 line 110 seeds the ampersand
  // form. The chip fell through to the `??` default, which is the
  // DIRECTOR_CONTROLLED purple, so rank 40 and rank 60 rendered identically
  // and the "shading ascends with sensitivity" claim below was false for
  // exactly the tier that carries formulas and test evidence.
  "R&D_RESTRICTED": "bg-orange-50 text-orange-900 border-orange-200",
  FORMULA_RESTRICTED: "bg-rose-50 text-rose-900 border-rose-200",
  DIRECTOR_CONTROLLED: "bg-purple-50 text-purple-900 border-purple-200",
};

function Classification({ code }: { code: string }) {
  // An UNKNOWN code falls back to the most cautious styling rather than the
  // most neutral. A classification this build has never heard of is more
  // likely to be a new, more restrictive one than a new public one.
  const tone =
    CLASSIFICATION_TONE[code] ?? "bg-purple-50 text-purple-900 border-purple-200";
  return (
    <span
      title="How this document must be handled. It is a label, not an access control: what you can see is decided by your project membership."
      className={`inline-block whitespace-nowrap rounded border px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-wide ${tone}`}
    >
      <span className="sr-only">Handling classification: </span>
      {code.replace(/_/g, " ")}
    </span>
  );
}

function DocumentRow({ document }: { document: KnowledgeDocument }) {
  return (
    <tr className="border-b border-slate-200 last:border-0">
      <td className="py-2.5 pr-4 align-top">
        <span className="font-medium text-slate-900">{document.title}</span>
      </td>
      <td className="py-2.5 pr-4 align-top text-slate-600">
        {document.source.replace(/_/g, " ")}
      </td>
      <td className="py-2.5 pr-4 align-top">
        <Classification code={document.classification} />
      </td>
      <td className="py-2.5 pr-4 align-top tabular-nums text-slate-600">
        {/*
          🔴 ZERO IS CALLED OUT, NOT PRINTED AS "0".
          A document with no chunks is INVISIBLE to every search however
          healthy its row looks — the ingestion failed partway, or the body had
          no text in it. Printed as a bare 0 among other numbers it reads as a
          small document rather than a broken one, and "why does the assistant
          never quote this?" becomes unanswerable from the screen.
        */}
        {document.chunks === 0 ? (
          <span className="font-medium text-red-700">
            0 — not searchable
          </span>
        ) : (
          document.chunks
        )}
      </td>
      <td className="py-2.5 align-top text-slate-500">
        {document.ingested_at.slice(0, 10)}
      </td>
    </tr>
  );
}

function PassageCard({ passage }: { passage: KnowledgePassage }) {
  const band = overlapBand(passage.distance);
  return (
    <li className="rounded border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-medium text-slate-900">
          {passage.title}{" "}
          <span className="font-normal text-slate-500">
            · passage {passage.ordinal}
          </span>
        </p>
        <div className="flex items-center gap-2">
          <Classification code={passage.classification} />
          <span className={`text-xs ${band.tone}`}>{band.label}</span>
        </div>
      </div>
      {/*
        A QUOTATION, marked up as one. `<blockquote>` is not decoration: it is
        what tells a screen reader that these words are the document's and not
        the application's, which is the same distinction the visual quote marks
        make for everyone else.
      */}
      <blockquote className="mt-2 border-l-2 border-slate-300 pl-3 text-sm leading-relaxed text-slate-700">
        {passage.content}
      </blockquote>
    </li>
  );
}

/**
 * Adding a document — the production write path, reachable by a person.
 *
 * 🔴 THE ROUTE EXISTED A COMMIT BEFORE THIS FORM DID, AND THAT WAS NOT ENOUGH.
 *
 * `POST /api/knowledge/documents` shipped with no caller: the client function
 * was exported and invoked from nowhere, so the only way to put a document in
 * the library was to construct an HTTP request by hand. I74 was marked closed
 * on the strength of the route alone, which is the "which production path
 * writes it?" defect committed while closing an instance of itself.
 *
 * ⚠️ SHOWN TO EVERYONE, BECAUSE THE CLIENT DOES NOT KNOW ITS OWN PERMISSIONS.
 *
 * `/api/me` returns roles, not permissions, and the sidebar is handed the full
 * module map rather than the caller's grants. So this form cannot be hidden
 * from a Chemist the way a permission-aware UI would hide it. §6 is explicit
 * that frontend checks are cosmetic and every control is re-enforced
 * server-side — which it is, with `knowledge.ingest` — so the honest thing is
 * to let the server answer and then SAY what the answer means, rather than
 * render a dead form and let a 403 look like a bug.
 */
function AddDocument() {
  const ingest = useIngestKnowledgeDocument();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [source, setSource] = useState<string>("internal_note");
  const [classification, setClassification] = useState("");
  const [open, setOpen] = useState(false);

  const forbidden = ingest.error instanceof ApiError && ingest.error.status === 403;

  return (
    <section aria-labelledby="knowledge-add-heading" className="mt-10">
      <h2 id="knowledge-add-heading" className="text-sm font-semibold text-slate-900">
        Add a document
      </h2>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((was) => !was)}
        className="mt-1 text-sm text-slate-700 underline underline-offset-2 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-500"
      >
        {open ? "Cancel" : "Add technical text to the library"}
      </button>

      {open && (
        <form
          className="mt-3 grid max-w-2xl gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            ingest.submit({
              title: title.trim(),
              body,
              source,
              // "" means the author did not choose. Omitted entirely so the
              // SERVER applies the ceiling -- never sent as a default.
              ...(classification === "" ? {} : { classification }),
            });
          }}
        >
          <div>
            <label htmlFor="doc-title" className="block text-xs font-medium text-slate-700">
              Title
            </label>
            <input
              id="doc-title"
              required
              maxLength={200}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="doc-source" className="block text-xs font-medium text-slate-700">
                Source
              </label>
              <select
                id="doc-source"
                value={source}
                onChange={(event) => setSource(event.target.value)}
                className="mt-1 w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              >
                {SOURCES.map((value) => (
                  <option key={value} value={value}>
                    {value.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label
                htmlFor="doc-classification"
                className="block text-xs font-medium text-slate-700"
              >
                Classification
              </label>
              <select
                id="doc-classification"
                value={classification}
                onChange={(event) => setClassification(event.target.value)}
                className="mt-1 w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              >
                <option value="">Not decided — most restrictive</option>
                {CLASSIFICATIONS.map((value) => (
                  <option key={value} value={value}>
                    {value.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label htmlFor="doc-body" className="block text-xs font-medium text-slate-700">
              Text
            </label>
            <textarea
              id="doc-body"
              required
              rows={8}
              value={body}
              onChange={(event) => setBody(event.target.value)}
              placeholder="Paste the technical sections worth retrieving — not a whole standards library."
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2 font-mono text-xs text-slate-900 placeholder:text-slate-400 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            />
            <p className="mt-1 text-xs text-slate-500">
              Blank lines separate passages. Text is stored and quoted verbatim —
              a classification is a <strong>handling label</strong>, not an access
              control, so anyone in your organization with access to this library
              can read what you paste here.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={ingest.isPending || title.trim() === "" || body.trim() === ""}
              className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-1 disabled:opacity-50"
            >
              {ingest.isPending ? "Indexing…" : "Add to library"}
            </button>
            {ingest.result && (
              <p role="status" className="text-sm text-emerald-700">
                Added — {ingest.result.chunks} searchable passage
                {ingest.result.chunks === 1 ? "" : "s"}.
              </p>
            )}
          </div>

          {ingest.error && (
            <p role="alert" className="text-sm text-red-700">
              {forbidden
                ? "You do not have permission to add documents to the knowledge library (knowledge.ingest). A Lead, Director, QA or Administrator can."
                : `The document was not added: ${serverMessage(ingest.error)}`}
            </p>
          )}
        </form>
      )}
    </section>
  );
}

export default function KnowledgePage() {
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");

  const documents = useKnowledgeDocuments(
    (live: KnowledgeDocumentPage) => live,
  );
  const search = useKnowledgeSearch(query);

  const unavailable = documents.unavailable ?? search.unavailable;
  const rows = useMemo(() => documents.data?.documents ?? [], [documents.data]);

  // I78. The API caps this list at `limit` and used to say nothing about it,
  // so past that point the oldest documents just stopped appearing. There is
  // still no page two — this tells the reader what they are looking at rather
  // than pretending the list is the library.
  const total = documents.data?.total ?? rows.length;
  const truncated = total > rows.length;

  return (
    <LiveOnlyPage
      title="Knowledge library"
      lede="Technical documents MSD can quote from. Every passage is filtered by your own project membership before it is ranked, so two people searching the same words see different results. Classification is a handling label that travels with the text — it is not what decides who can read it."
      unavailable={unavailable}
      notInvented="technical documents MSD would quote as evidence"
    >
      <section aria-labelledby="knowledge-search-heading">
        <h2
          id="knowledge-search-heading"
          className="text-sm font-semibold text-slate-900"
        >
          Search passages
        </h2>
        <form
          className="mt-2 flex max-w-2xl gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            setQuery(draft);
          }}
        >
          <label htmlFor="knowledge-q" className="sr-only">
            Search the knowledge library
          </label>
          <input
            id="knowledge-q"
            type="search"
            value={draft}
            onChange={(event) => {
              const next = event.target.value;
              setDraft(next);
              // 🔴 CLEARING THE BOX MUST CLEAR THE RESULTS.
              //
              // Only `draft` changed on input, so emptying the field (or the
              // native ✕ on a `type="search"`) left the previous `query` in
              // place and its passages on screen under an empty box -- results
              // with no visible question, which read as the current answer.
              // Codex found it. Submitting an empty query is still blocked;
              // this only tears down what is no longer being asked.
              if (next.trim().length === 0) {
                setQuery("");
              }
            }}
            placeholder="e.g. cure schedule, substrate abrasion"
            className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          />
          <button
            type="submit"
            className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-1 disabled:opacity-50"
            disabled={draft.trim().length === 0}
          >
            Search
          </button>
        </form>
        {/*
          🔴 THE HONEST LIMITATION, ON THE SCREEN AND NOT ONLY IN THE CODE.
          The commit that built this could have shipped a plausible-looking
          "semantic search" and let the word "embedding" do the implying. A
          user who believes the library understood them reads an empty result
          as "we have nothing on this", when it may only mean they used a
          different word than the document did.
        */}
        <p className="mt-2 max-w-2xl text-xs text-slate-500">
          Matching is on <strong>shared words</strong>, not meaning — a search
          for &ldquo;bonding&rdquo; will not find a document that only says
          &ldquo;adhesion&rdquo;. Try the words the document itself would use.
        </p>

        {search.error && (
          <p role="alert" className="mt-3 text-sm text-red-700">
            The search failed: {serverMessage(search.error)}
          </p>
        )}
        {search.isLoading && (
          <p className="mt-3 text-sm text-slate-500">Searching…</p>
        )}
        {search.data && search.data.length === 0 && (
          <p className="mt-3 max-w-2xl text-sm text-slate-600">
            No passages matched those words <strong>that you have access to</strong>.
            {" "}
            {/*
              NOT "there are nothing on this topic". MSD's own composer is held
              to this rule and the screen is held to the same one: the library
              may well hold the answer inside a project this person is not a
              member of, and saying it does not exist would be both false and a
              disclosure of the shape of what does.
            */}
            A document held in a project you are not a member of would not
            appear here.
          </p>
        )}
        {search.data && search.data.length > 0 && (
          <ul className="mt-3 grid max-w-3xl gap-2">
            {search.data.map((passage) => (
              <PassageCard
                key={`${passage.document_id}-${passage.ordinal}`}
                passage={passage}
              />
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="knowledge-documents-heading" className="mt-10">
        <h2
          id="knowledge-documents-heading"
          className="text-sm font-semibold text-slate-900"
        >
          Documents
        </h2>

        {documents.error && (
          <p role="alert" className="mt-2 text-sm text-red-700">
            The library could not be loaded: {serverMessage(documents.error)}
          </p>
        )}
        {documents.isLoading && (
          <p className="mt-2 text-sm text-slate-500">Loading…</p>
        )}
        {!documents.isLoading && !documents.error && rows.length === 0 && (
          <p className="mt-2 max-w-2xl text-sm text-slate-600">
            No documents you have access to. The library is filled by ingesting
            technical text; until something is in it, MSD will answer knowledge
            questions by saying it could not find anything.
          </p>
        )}
        {rows.length > 0 && (
          <p className="mt-2 text-sm text-slate-600">
            {truncated ? (
              <>
                <span className="font-medium text-amber-800">
                  Showing the {rows.length} most recent of {total} documents.
                </span>{" "}
                The rest are not reachable from this screen yet — there is no
                page two. Search covers the whole library, not just this list.
              </>
            ) : (
              <>
                {total} document{total === 1 ? "" : "s"}, newest first — the
                whole library you have access to.
              </>
            )}
          </p>
        )}
        {rows.length > 0 && (
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[42rem] text-left text-sm">
              <caption className="sr-only">
                Knowledge documents you have access to, newest first
              </caption>
              <thead>
                <tr className="border-b border-slate-300 text-xs uppercase tracking-wide text-slate-500">
                  <th scope="col" className="py-2 pr-4 font-medium">
                    Title
                  </th>
                  <th scope="col" className="py-2 pr-4 font-medium">
                    Source
                  </th>
                  <th scope="col" className="py-2 pr-4 font-medium">
                    Classification
                  </th>
                  <th scope="col" className="py-2 pr-4 font-medium">
                    Passages
                  </th>
                  <th scope="col" className="py-2 font-medium">
                    Ingested
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((document) => (
                  <DocumentRow key={document.id} document={document} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <AddDocument />
    </LiveOnlyPage>
  );
}
