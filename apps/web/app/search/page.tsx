"use client";

/**
 * Global search results — spec §29.
 *
 * 🔴 THE POINT OF THIS SCREEN IS THAT IT SAYS WHAT IT DID NOT SEARCH.
 *
 * Fifteen record types are searchable and each is gated on the permission that
 * governs it, so two people typing the same word get different answers. If
 * this page rendered only `results`, a chemist who cannot see failures would
 * read "nothing found" and conclude no failure matches — which is false, and
 * false in the direction that hides a problem from the person chasing it.
 *
 * So there are three sections and all three always render:
 *   1. what was found,
 *   2. which record types were NOT searched, because this caller may not,
 *   3. which record types this system does not hold at all (patents,
 *      released products) — §29 names them and they have no table.
 *
 * ⚠️ THIS IS NOT THE KNOWLEDGE LIBRARY SEARCH at `/knowledge`. That one quotes
 * passages out of documents by shared words; this one finds records by code
 * and name, and an exact code match wins. Both exist deliberately — see
 * `apps/api/app/domains/search/service.py`.
 */

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { LiveOnlyPage } from "@/components/ui/data-source-banner";
import { useGlobalSearch } from "@/lib/api/hooks";
import { MIN_SEARCH_LENGTH, PLURAL_LABEL, type SearchHit } from "@/lib/api/search";

function SearchScreen() {
  const params = useSearchParams();
  const router = useRouter();
  const queryFromUrl = params.get("q") ?? "";
  const [draft, setDraft] = useState(queryFromUrl);

  // The URL is the source of truth so a result page can be linked and
  // reloaded. The input follows it rather than owning it.
  useEffect(() => {
    setDraft(queryFromUrl);
  }, [queryFromUrl]);

  const { data, isLoading, error, unavailable } = useGlobalSearch(queryFromUrl);

  const grouped = new Map<string, SearchHit[]>();
  for (const hit of data?.results ?? []) {
    const list = grouped.get(hit.label);
    if (list) list.push(hit);
    else grouped.set(hit.label, [hit]);
  }

  const withheld = (data?.searched ?? []).filter((t) => !t.permitted);

  return (
    <LiveOnlyPage
      title="Search"
      lede="Every record type you are permitted to see, matched on code and name."
      unavailable={unavailable}
      notInvented="search results"
    >
      <form
        className="mb-6 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          const next = draft.trim();
          // The API refuses fewer than MIN_SEARCH_LENGTH characters. Submitting
          // anyway turned a too-short query into a red error alert instead of
          // the guidance paragraph below. Same guard as the top-bar box.
          if (next.length === 0) router.push("/search");
          else if (next.length >= MIN_SEARCH_LENGTH) {
            router.push(`/search?q=${encodeURIComponent(next)}`);
          }
        }}
      >
        <label htmlFor="search-q" className="sr-only">
          Search records
        </label>
        <input
          id="search-q"
          type="search"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Project code, formula code, material name…"
          minLength={MIN_SEARCH_LENGTH}
          className="w-full max-w-lg rounded border border-slate-300 px-3 py-2 text-sm"
        />
        <button
          type="submit"
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
        >
          Search
        </button>
      </form>

      {queryFromUrl.trim().length === 0 && (
        <p className="text-sm text-slate-600">
          Type a record code or name — at least {MIN_SEARCH_LENGTH} characters.
          Matching is on the words you type; this searches records, not the text
          inside documents. For that, use the{" "}
          <Link href="/knowledge" className="underline">
            Knowledge Library
          </Link>
          .
        </p>
      )}

      {isLoading && <p className="text-sm text-slate-600">Searching…</p>}

      {error && (
        <p role="alert" className="text-sm text-red-700">
          ✕ The search could not be run: {error.message}
        </p>
      )}

      {data && (
        <>
          <p className="mb-4 text-sm text-slate-700">
            <strong>{data.result_count}</strong>{" "}
            {data.result_count === 1 ? "record" : "records"} matched{" "}
            <span className="font-mono">{data.query}</span>
            {data.truncated && " — the list is capped; narrow the search to see more"}
          </p>

          {[...grouped.entries()].map(([label, hits]) => (
            <section key={label} className="mb-6">
              <h2 className="mb-2 text-sm font-semibold text-slate-900">
                {label} <span className="font-normal text-slate-500">({hits.length})</span>
              </h2>
              <ul className="divide-y divide-slate-200 rounded border border-slate-200">
                {hits.map((hit) => (
                  <li key={`${hit.record_type}-${hit.id}`} className="px-3 py-2">
                    <Hit hit={hit} />
                  </li>
                ))}
              </ul>
            </section>
          ))}

          {/* 🔴 NOT AN AFTERTHOUGHT. See the header comment: an empty section
              and an unsearched one are different answers, and only one of them
              is "there is nothing there". */}
          {withheld.length > 0 && (
            <section className="mb-6 rounded border border-amber-300 bg-amber-50 p-3">
              <h2 className="text-sm font-semibold text-amber-900">
                ! Not searched — you do not hold the permission
              </h2>
              <p className="mt-1 text-xs text-amber-900">
                These record types were excluded from the search above. There may be
                matching records; this search cannot tell you.
              </p>
              <ul className="mt-2 text-xs text-amber-900">
                {withheld.map((t) => (
                  <li key={t.record_type}>
                    {t.label} — needs <span className="font-mono">{t.permission}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {data.absent.length > 0 && (
            <section className="rounded border border-slate-200 bg-slate-50 p-3">
              <h2 className="text-sm font-semibold text-slate-800">
                Not held in this system
              </h2>
              <ul className="mt-2 space-y-1 text-xs text-slate-700">
                {data.absent.map((a) => (
                  <li key={a.record_type}>
                    <span className="font-mono">{a.record_type}</span> — {a.reason}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </LiveOnlyPage>
  );
}

/**
 * One result row.
 *
 * 🔴 A HIT IS A LINK ONLY WHERE A DETAIL SCREEN EXISTS.
 *
 * Most record types in this product have a list screen and no detail screen,
 * so `path` is null for them. Rendering a link anyway is the defect
 * `components/ui/record-link.tsx` was written for — "a dead link is worse than
 * no link; it looks like a working product until it is clicked, and then it
 * looks broken rather than unfinished".
 *
 * The record is still shown, and the type's list screen is offered, so the
 * result is useful without being a lie about where it goes.
 */
function Hit({ hit }: { hit: SearchHit }) {
  const body = (
    <>
      <span className="font-medium text-slate-900">{hit.title}</span>
      {hit.code && <span className="ml-2 font-mono text-xs text-slate-600">{hit.code}</span>}
      {hit.subtitle && <span className="ml-2 text-xs text-slate-600">{hit.subtitle}</span>}
      {hit.state && <span className="ml-2 text-xs text-slate-500">· {hit.state}</span>}
    </>
  );

  if (hit.path) {
    return (
      <Link href={hit.path} className="block hover:bg-slate-50">
        {body}
      </Link>
    );
  }

  return (
    <div data-testid="hit-without-detail-page">
      {body}
      <span className="ml-2 text-xs text-slate-500">
        — no detail screen for this record type yet;{" "}
        <Link href={hit.list_path} className="underline">
          open {PLURAL_LABEL[hit.record_type] ?? hit.list_path}
        </Link>
      </span>
    </div>
  );
}

export default function SearchPage() {
  // `useSearchParams` requires a Suspense boundary in the app router, or the
  // whole route opts out of static rendering with a build-time warning.
  return (
    <Suspense fallback={<p className="p-6 text-sm text-slate-600">Loading search…</p>}>
      <SearchScreen />
    </Suspense>
  );
}
