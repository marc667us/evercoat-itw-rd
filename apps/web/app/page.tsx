"use client";

/**
 * THE PUBLIC LANDING PAGE.
 *
 * 🔴 THIS ROUTE USED TO REDIRECT INTO THE APPLICATION. IT NO LONGER DOES.
 *
 * The owner specified `/` as a public home page carrying sign-in, sign-up, a
 * Global Competitor Product Marketplace and a Global Competitor Industry News
 * Feed. Until now every screen in this application was behind authentication
 * and `/` bounced the visitor to `readLanding()`.
 *
 * That redirect was asserted by NINE call sites across seven Playwright specs.
 * Each was changed deliberately with its reason, none deleted — the ones that
 * used `/` as a synonym for "the app" now navigate to their actual subject,
 * and `navigation.spec.ts` keeps an assertion about `/` itself, inverted to
 * assert this page renders anonymously.
 *
 * ⚠️ THE LANDING PREFERENCE SURVIVES, AND IT TOOK A SECOND CHANGE TO KEEP IT.
 *
 * `readLanding()` is still honoured — but AFTER SIGN-IN, not here. `signIn`
 * stores the current pathname as `returnTo` and the callback returns there, so
 * signing in from this page would have returned the visitor to this page.
 * Codex found that; `auth-provider.tsx` now substitutes the preference when
 * the flow starts at `/`. Without that fix the preference would have had no
 * reader again, which is the defect both reviewers found the first time.
 *
 * ⚠️ WHAT THE `output: "export"` COMMENT ON THE OLD VERSION ACTUALLY MEANT.
 * The old file carried a long warning about static export. Re-read in review:
 * that failure was caused by a SERVER `redirect()` with no server to answer
 * it, which wrote `out/index.html` as an error document while `next build`
 * exited 0. A statically renderable page like this one is exactly what export
 * mode supports, so the warning does not apply here. An exported-HTML smoke
 * test is kept anyway, because "next build exited 0" was never the signal.
 *
 * 🔴 IT NEVER RENDERS THE DEMONSTRATION DATASET AS THE CATALOGUE.
 * When the API is absent this page shows an empty marketplace and says why.
 * Falling back to `lib/demo/dataset` would publish invented products carrying
 * REAL manufacturer names to anonymous visitors as though they were live
 * market intelligence.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ProductCard } from "@/components/public/product-card";
import { useAuth } from "@/components/providers/auth-provider";
import {
  fetchPublicNews,
  fetchPublicProducts,
  submitAccessRequest,
  type PublicNewsItem,
  type PublicProduct,
} from "@/lib/api/public-client";

type LoadState = "loading" | "ready" | "unavailable";

export default function Home() {
  const { session, configured, signIn } = useAuth();
  const signedIn = session.status === "authenticated";

  const [products, setProducts] = useState<PublicProduct[]>([]);
  const [news, setNews] = useState<PublicNewsItem[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [search, setSearch] = useState("");

  const load = useCallback(async (q: string) => {
    setState("loading");
    try {
      const [productPage, newsPage] = await Promise.all([
        fetchPublicProducts({ q: q || undefined, limit: 12 }),
        fetchPublicNews({ limit: 6 }),
      ]);
      setProducts(productPage.products);
      setNews(newsPage.items);
      setState("ready");
    } catch {
      // Named, not swallowed. An empty marketplace and an unreachable one are
      // different facts and the reader is told which.
      setProducts([]);
      setNews([]);
      setState("unavailable");
    }
  }, []);

  useEffect(() => {
    void load("");
  }, [load]);

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-baseline gap-2">
            <span className="text-sm font-black tracking-tight text-slate-900">
              ITW EVERCOAT R&amp;D
            </span>
          </div>
          <nav aria-label="Public sections" className="flex items-center gap-4 text-xs font-semibold">
            <a href="#marketplace" className="text-slate-700 hover:underline">
              Marketplace
            </a>
            <a href="#news" className="text-slate-700 hover:underline">
              Industry News
            </a>
            <a
              href="#access"
              className="rounded-md border border-slate-400 px-3 py-1.5 text-slate-900 hover:bg-slate-100"
            >
              Sign up
            </a>
            {/* Signed in, the honest control is "go to your workspace", not a
                second Sign in that would restart a flow already completed. */}
            {signedIn ? (
              <Link
                href="/dashboard"
                className="rounded-md bg-slate-900 px-3 py-1.5 text-white"
              >
                Go to your workspace
              </Link>
            ) : (
              <button
                type="button"
                onClick={() => void signIn()}
                disabled={!configured}
                title={
                  configured
                    ? undefined
                    : "This deployment has no identity provider configured."
                }
                className="rounded-md bg-slate-900 px-3 py-1.5 text-white disabled:opacity-50"
              >
                Sign in
              </button>
            )}
          </nav>
        </div>
      </header>

      <section className="border-b border-slate-200 bg-white px-4 py-10">
        <div className="mx-auto max-w-6xl">
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-500">
            Research • Benchmark • Monitor • Develop better products
          </p>
          <h1 className="mt-3 max-w-3xl text-2xl font-black leading-tight text-slate-900">
            Global competitor products, materials intelligence and industry
            developments supporting advanced R&amp;D decision-making.
          </h1>
          <div className="mt-5 flex flex-wrap gap-2">
            <a
              href="#marketplace"
              className="rounded-md bg-slate-900 px-4 py-2 text-xs font-semibold text-white"
            >
              Explore products
            </a>
            <a
              href="#news"
              className="rounded-md border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-800"
            >
              Industry news
            </a>
            {/* 🔴 THE WAY IN, REPEATED IN THE HERO.
                The owner could not find sign-in or sign-up on the first
                version: both were in the header, at 12px, at the far right of
                a row that wraps on a narrow window. A control that exists and
                cannot be found has the same value as one that does not. */}
            <a
              href="#access"
              className="rounded-md border border-slate-400 px-4 py-2 text-xs font-semibold text-slate-900"
            >
              Sign up
            </a>
          </div>
        </div>
      </section>

      <main className="mx-auto max-w-6xl px-4 py-8">
        <section id="marketplace" aria-labelledby="marketplace-heading">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h2
              id="marketplace-heading"
              className="text-sm font-black uppercase tracking-wide text-slate-900"
            >
              Global Competitor Product Marketplace
            </h2>
            <Link href="/marketplace" className="text-xs font-semibold text-slate-700 underline">
              View all competitor products
            </Link>
          </div>

          <form
            className="mt-3 flex gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              void load(search);
            }}
          >
            <label htmlFor="marketplace-search" className="sr-only">
              Search competitor products
            </label>
            <input
              id="marketplace-search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by product, manufacturer or code…"
              className="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-2 text-xs"
            />
            <button
              type="submit"
              className="rounded-md bg-slate-900 px-4 py-2 text-xs font-semibold text-white"
            >
              Search
            </button>
          </form>

          <div className="mt-4">
            {state === "loading" ? (
              <p className="text-xs text-slate-600">Loading the catalogue…</p>
            ) : state === "unavailable" ? (
              <CatalogueUnavailable />
            ) : products.length === 0 ? (
              <p className="text-xs text-slate-600">
                No published competitor products match that search.
              </p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {products.map((product) => (
                  <ProductCard key={product.id} product={product} />
                ))}
              </div>
            )}
          </div>
        </section>

        <section id="news" aria-labelledby="news-heading" className="mt-10">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h2
              id="news-heading"
              className="text-sm font-black uppercase tracking-wide text-slate-900"
            >
              Global Competitor Industry News Feed
            </h2>
            <Link href="/industry-news" className="text-xs font-semibold text-slate-700 underline">
              View all industry intelligence
            </Link>
          </div>

          <div className="mt-4">
            {state === "unavailable" ? (
              <CatalogueUnavailable />
            ) : news.length === 0 ? (
              <p className="text-xs text-slate-600">
                No published industry developments yet.
              </p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {news.map((item) => (
                  <NewsCard key={item.id} item={item} />
                ))}
              </div>
            )}
          </div>
        </section>

        <AccessRequestSection />
      </main>

      <footer className="border-t border-slate-200 bg-white px-4 py-6 text-[11px] text-slate-600">
        <div className="mx-auto max-w-6xl">
          ITW Evercoat R&amp;D Platform — Materials · Formulation · Lab · Testing ·
          Research · Analytics. Access to the R&amp;D environment is granted by an
          administrator.
        </div>
      </footer>
    </div>
  );
}

function CatalogueUnavailable() {
  return (
    <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
      <strong className="font-semibold">The public catalogue is unavailable.</strong>{" "}
      This deployment could not reach the intelligence service, so nothing is
      shown. Nothing here has been substituted or estimated.
    </div>
  );
}

function NewsCard({ item }: { item: PublicNewsItem }) {
  return (
    <article className="flex h-full flex-col rounded-lg border border-slate-200 bg-white p-4">
      <p className="text-[10.5px] font-bold uppercase tracking-wide text-slate-500">
        {item.category_label}
        {item.region ? ` · ${item.region}` : ""}
      </p>
      <h3 className="mt-1 text-sm font-bold leading-tight text-slate-900">
        {item.headline}
      </h3>
      <p className="mt-1 text-[11px] text-slate-600">
        {item.source_name} · Tier {item.source_tier}
        {item.published_at ? ` · ${item.published_at.slice(0, 10)}` : ""}
      </p>
      {item.summary ? (
        <p className="mt-2 line-clamp-4 text-xs leading-relaxed text-slate-600">
          {/* 🔴 THE SPEC IS EXPLICIT: an AI summary is labelled as a summary and
              never replaces the source article. The label rides with the text,
              not in a legend somewhere else on the page. */}
          {item.summary_is_ai_generated ? (
            <span className="mr-1 rounded bg-slate-200 px-1 py-0.5 text-[10px] font-bold uppercase text-slate-700">
              AI summary
            </span>
          ) : null}
          {item.summary}
        </p>
      ) : null}
      <div className="mt-auto pt-3">
        <a
          href={item.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[11px] font-semibold text-slate-800 underline"
        >
          Read the source
        </a>
      </div>
    </article>
  );
}

/**
 * "Sign Up" — which creates a REQUEST, not an account.
 *
 * 🔴 SELF-REGISTRATION INTO A TENANTED R&D SYSTEM IS NOT A FORM. Keycloak
 * registration is off and stays off. This queues a request; an administrator
 * holding `admin.users` reviews it and binds the identity to an organization
 * with a least-privilege role through the route that already exists.
 *
 * The button says what it does. Calling it "Sign up" while it grants nothing
 * would be the interface asserting a capability the system does not have.
 */
function AccessRequestSection() {
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  return (
    <section id="access" aria-labelledby="access-heading" className="mt-10">
      <h2
        id="access-heading"
        className="text-sm font-black uppercase tracking-wide text-slate-900"
      >
        Sign up — request access to the R&amp;D environment
      </h2>
      <p className="mt-1 max-w-2xl text-xs text-slate-600">
        Access is granted by an administrator, not automatically. Submitting this
        creates a request for review — it does not create an account.
      </p>

      {sent ? (
        <p className="mt-3 rounded-md border border-emerald-300 bg-emerald-50 p-3 text-xs text-emerald-900">
          Your request has been queued for review.
        </p>
      ) : (
        <form
          className="mt-3 grid max-w-2xl gap-2 sm:grid-cols-2"
          onSubmit={async (event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            setBusy(true);
            setError(null);
            try {
              await submitAccessRequest({
                full_name: String(data.get("full_name") ?? ""),
                work_email: String(data.get("work_email") ?? ""),
                company: String(data.get("company") ?? ""),
                reason: String(data.get("reason") ?? "") || undefined,
              });
              setSent(true);
            } catch {
              setError("The request could not be submitted. Please try again later.");
            } finally {
              setBusy(false);
            }
          }}
        >
          <Field name="full_name" label="Full name" required />
          <Field name="work_email" label="Work email" type="email" required />
          <Field name="company" label="Company" required />
          <Field name="reason" label="Reason for access" />
          <div className="sm:col-span-2">
            <button
              type="submit"
              disabled={busy}
              className="rounded-md bg-slate-900 px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
            >
              {busy ? "Submitting…" : "Request access"}
            </button>
          </div>
          {error ? (
            <p className="text-xs text-red-700 sm:col-span-2">{error}</p>
          ) : null}
        </form>
      )}
    </section>
  );
}

function Field({
  name,
  label,
  type = "text",
  required = false,
}: {
  name: string;
  label: string;
  type?: string;
  required?: boolean;
}) {
  return (
    <div>
      <label htmlFor={name} className="block text-[11px] font-semibold text-slate-700">
        {label}
        {required ? <span aria-hidden="true"> *</span> : null}
      </label>
      <input
        id={name}
        name={name}
        type={type}
        required={required}
        className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-xs"
      />
    </div>
  );
}
