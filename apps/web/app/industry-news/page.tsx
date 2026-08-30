"use client";

/**
 * The Global Competitor Industry News Feed — public.
 *
 * 🔴 IT IS NOT A NEWS READER, AND THE SPEC IS EXPLICIT ABOUT WHY.
 *
 * Every item is classified against the R&D knowledge structure so intelligence
 * can later become research, benchmarking or product development. What is
 * public is the metadata and the link: headline, source, tier, date, category,
 * brand and a short summary. Relevance to ITW products, linked internal
 * records, affected materials and the MSD interpretation are internal and are
 * not projected here — one record, two projections, not two databases.
 *
 * ⚠️ AN AI SUMMARY IS LABELLED AS ONE, BESIDE THE TEXT.
 * "AI-generated summaries must be labelled as summaries and should never
 * replace the original source article." The label rides with the summary
 * rather than sitting in a legend, and the source link is always present —
 * `news_items.source_url` is NOT NULL for exactly this reason.
 *
 * ⚠️ WHAT IS DELIBERATELY NOT HERE YET. The spec's action drawer (Save to
 * Research / Create Opportunity / Link to Material) is authenticated work that
 * reuses the existing Project, Task, Research and Knowledge services. It is a
 * later slice, and the six link tables it needs are deliberately not created —
 * an empty table built to match a diagram is worse than an absent one.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  fetchPublicNews,
  fetchPublicNewsCategories,
  type PublicNewsCategory,
  type PublicNewsItem,
} from "@/lib/api/public-client";

export default function IndustryNewsPage() {
  const [items, setItems] = useState<PublicNewsItem[]>([]);
  const [categories, setCategories] = useState<PublicNewsCategory[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "unavailable">("loading");

  const load = useCallback(async (category: string | null) => {
    setState("loading");
    try {
      const [feed, cats] = await Promise.all([
        fetchPublicNews({ category: category ?? undefined, limit: 60 }),
        fetchPublicNewsCategories(),
      ]);
      setItems(feed.items);
      setCategories(cats.categories);
      setState("ready");
    } catch {
      setItems([]);
      setState("unavailable");
    }
  }, []);

  useEffect(() => {
    void load(active);
  }, [load, active]);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <header className="border-b border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <Link href="/" className="text-sm font-black text-slate-900 dark:text-slate-100">
            ITW EVERCOAT R&amp;D
          </Link>
          <Link href="/marketplace" className="text-xs font-semibold text-slate-700 underline dark:text-slate-300">
            Marketplace
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        <h1 className="text-sm font-black uppercase tracking-wide text-slate-900 dark:text-slate-100">
          Global Competitor Industry News Feed
        </h1>

        {categories.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-1.5">
            <Chip label="All" active={active === null} onClick={() => setActive(null)} />
            {categories.map((category) => (
              <Chip
                key={category.id}
                label={category.label}
                active={active === category.slug}
                onClick={() => setActive(category.slug)}
              />
            ))}
          </div>
        ) : null}

        <div className="mt-4">
          {state === "loading" ? (
            <p className="text-xs text-slate-600 dark:text-slate-400">Loading the feed…</p>
          ) : state === "unavailable" ? (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-900 dark:text-amber-200">
              <strong className="font-semibold">The industry feed is unavailable.</strong> This
              deployment could not reach the intelligence service. Nothing has
              been substituted.
            </div>
          ) : items.length === 0 ? (
            <p className="text-xs text-slate-600 dark:text-slate-400">
              No published developments in this category yet.
            </p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((item) => (
                <article
                  key={item.id}
                  className="flex h-full flex-col rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
                >
                  <p className="text-[10.5px] font-bold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                    {item.category_label}
                    {item.region ? ` · ${item.region}` : ""}
                  </p>
                  <h2 className="mt-1 text-sm font-bold leading-tight text-slate-900 dark:text-slate-100">
                    {item.headline}
                  </h2>
                  <p className="mt-1 text-[11px] text-slate-600 dark:text-slate-400">
                    {/* The tier is shown, not hidden: the spec ranks sources
                        1–4 and a reader deserves to know whether a claim came
                        from a regulator or from general web information. */}
                    {item.source_name} · Tier {item.source_tier}
                    {item.published_at ? ` · ${item.published_at.slice(0, 10)}` : ""}
                  </p>
                  {item.summary ? (
                    <p className="mt-2 line-clamp-5 text-xs leading-relaxed text-slate-600 dark:text-slate-400">
                      {item.summary_is_ai_generated ? (
                        <span className="mr-1 rounded bg-slate-200 px-1 py-0.5 text-[10px] font-bold uppercase text-slate-700 dark:bg-slate-700 dark:text-slate-200">
                          AI summary
                        </span>
                      ) : null}
                      {item.summary}
                    </p>
                  ) : null}
                  <div className="mt-auto flex flex-wrap gap-3 pt-3">
                    <a
                      href={item.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11px] font-semibold underline"
                    >
                      Read the source
                    </a>
                    {item.product_id ? (
                      <Link
                        href={`/marketplace?product=${item.product_id}`}
                        className="text-[11px] font-semibold underline"
                      >
                        View the product
                      </Link>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

function Chip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-full px-3 py-1 text-[11px] font-semibold ${
        active
          ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
          : "border border-slate-300 text-slate-700 dark:border-slate-700 dark:text-slate-300"
      }`}
    >
      {label}
    </button>
  );
}
