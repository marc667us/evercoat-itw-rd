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
import { useKnowledgeDocuments, useKnowledgeSearch } from "@/lib/api/hooks";
import type { KnowledgeDocument, KnowledgePassage } from "@/lib/api/knowledge";

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
 */
const CLASSIFICATION_TONE: Record<string, string> = {
  PUBLIC: "bg-slate-100 text-slate-700 border-slate-300",
  INTERNAL: "bg-sky-50 text-sky-800 border-sky-200",
  CONFIDENTIAL: "bg-amber-50 text-amber-900 border-amber-200",
  R_AND_D_RESTRICTED: "bg-orange-50 text-orange-900 border-orange-200",
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
      className={`inline-block whitespace-nowrap rounded border px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-wide ${tone}`}
    >
      <span className="sr-only">Classification: </span>
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

export default function KnowledgePage() {
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");

  const documents = useKnowledgeDocuments(
    (live: KnowledgeDocument[]) => live,
  );
  const search = useKnowledgeSearch(query);

  const unavailable = documents.unavailable ?? search.unavailable;
  const rows = useMemo(() => documents.data ?? [], [documents.data]);

  return (
    <LiveOnlyPage
      title="Knowledge library"
      lede="Technical documents MSD can quote from. Every passage is filtered by your own project membership and classification before it is ranked, so two people searching the same words see different results."
      unavailable={unavailable}
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
            onChange={(event) => setDraft(event.target.value)}
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
            The search failed: {search.error.message}
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
            The library could not be loaded: {documents.error.message}
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
    </LiveOnlyPage>
  );
}
