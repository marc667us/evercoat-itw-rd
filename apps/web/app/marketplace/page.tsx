"use client";

/**
 * The Global Competitor Product Marketplace — public, and its product detail.
 *
 * 🔴 ONE ROUTE, NOT `/marketplace` PLUS `/marketplace/[id]`.
 *
 * A dynamic segment under `output: "export"` needs `generateStaticParams`, and
 * that means knowing every product id at BUILD time. A live global catalogue
 * does not have one. `/projects/[code]` is this repository's own example of
 * doing it anyway: it renders from `lib/demo/dataset` and 404s for every live
 * record.
 *
 * So the detail is `?product=<id>`, resolved at run time from the API, and it
 * works for any id — including one an agent adds after the build.
 *
 * ⚠️ PUBLIC, AND NOTHING HERE IS SUBSTITUTED. When the API cannot be reached
 * the page says so and shows nothing. The demonstration dataset is never
 * rendered as the catalogue: these cards carry REAL manufacturer names, and an
 * invented price beside a real brand, served anonymously, is the failure this
 * whole feature was designed around.
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { ProductCard, ProvenanceBadge } from "@/components/public/product-card";
import {
  fetchPublicProduct,
  fetchPublicProducts,
  formatPrice,
  type PublicProduct,
  type PublicProductDetail,
} from "@/lib/api/public-client";

export default function MarketplacePage() {
  // `useSearchParams` must sit inside a Suspense boundary or the static export
  // build fails outright ("missing suspense boundary with useSearchParams").
  return (
    <Suspense fallback={<Shell><p className="text-xs text-slate-600">Loading…</p></Shell>}>
      <Marketplace />
    </Suspense>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-4 py-3">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <Link href="/" className="text-sm font-black text-slate-900">
            ITW EVERCOAT R&amp;D
          </Link>
          <Link href="/industry-news" className="text-xs font-semibold text-slate-700 underline">
            Industry news
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}

function Marketplace() {
  const params = useSearchParams();
  const productId = params.get("product");

  if (productId) return <ProductDetail id={productId} />;
  return <ProductList />;
}

function ProductList() {
  const [products, setProducts] = useState<PublicProduct[]>([]);
  const [total, setTotal] = useState(0);
  const [state, setState] = useState<"loading" | "ready" | "unavailable">("loading");
  const [search, setSearch] = useState("");

  const load = useCallback(async (q: string) => {
    setState("loading");
    try {
      const page = await fetchPublicProducts({ q: q || undefined, limit: 60 });
      setProducts(page.products);
      setTotal(page.total);
      setState("ready");
    } catch {
      setProducts([]);
      setState("unavailable");
    }
  }, []);

  useEffect(() => {
    void load("");
  }, [load]);

  return (
    <Shell>
      <h1 className="text-sm font-black uppercase tracking-wide text-slate-900">
        Global Competitor Product Marketplace
      </h1>
      <form
        className="mt-3 flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void load(search);
        }}
      >
        <label htmlFor="q" className="sr-only">
          Search competitor products
        </label>
        <input
          id="q"
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

      {state === "ready" ? (
        <p className="mt-3 text-[11px] text-slate-600">
          {/* The count is the SERVED total, not `products.length`. A page of 60
              out of 300 saying "60 products" would be a quiet lie. */}
          Showing {products.length} of {total} published products.
        </p>
      ) : null}

      <div className="mt-4">
        {state === "loading" ? (
          <p className="text-xs text-slate-600">Loading the catalogue…</p>
        ) : state === "unavailable" ? (
          <Unavailable />
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
    </Shell>
  );
}

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "sds", label: "Material Safety Data" },
  { id: "datasheets", label: "Datasheets" },
  { id: "labels", label: "Labels" },
  { id: "literature", label: "Literature" },
  { id: "news", label: "News & Developments" },
] as const;

type TabId = (typeof TABS)[number]["id"];

const KIND_FOR_TAB: Partial<Record<TabId, string>> = {
  sds: "sds",
  datasheets: "datasheet",
  labels: "label",
  literature: "literature",
};

function ProductDetail({ id }: { id: string }) {
  const [product, setProduct] = useState<PublicProductDetail | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "missing" | "unavailable">("loading");
  const [tab, setTab] = useState<TabId>("overview");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setState("loading");
      try {
        const detail = await fetchPublicProduct(id);
        if (!cancelled) {
          setProduct(detail);
          setState("ready");
        }
      } catch (error) {
        if (cancelled) return;
        // 🔴 404 AND "UNREACHABLE" ARE DIFFERENT ANSWERS. Collapsing them would
        // tell a visitor a product does not exist when the service is down.
        const status = (error as { status?: number | null }).status ?? null;
        setState(status === 404 ? "missing" : "unavailable");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (state === "loading") {
    return (
      <Shell>
        <p className="text-xs text-slate-600">Loading the product…</p>
      </Shell>
    );
  }
  if (state === "unavailable") {
    return (
      <Shell>
        <Unavailable />
      </Shell>
    );
  }
  if (state === "missing" || product === null) {
    return (
      <Shell>
        <p className="text-xs text-slate-700">
          That product is not in the published catalogue.
        </p>
        <Link href="/marketplace" className="mt-2 inline-block text-xs font-semibold underline">
          Back to the marketplace
        </Link>
      </Shell>
    );
  }

  const price = formatPrice(product.price_amount, product.price_currency);
  const kind = KIND_FOR_TAB[tab];
  const documents = kind ? product.documents.filter((d) => d.document_kind === kind) : [];

  return (
    <Shell>
      <Link href="/marketplace" className="text-xs font-semibold text-slate-700 underline">
        ← Marketplace
      </Link>

      <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[10.5px] font-bold uppercase tracking-wide text-slate-500">
            {product.category ?? "Uncategorised"}
            {product.chemistry ? ` · ${product.chemistry}` : ""}
          </p>
          <h1 className="mt-1 text-lg font-black text-slate-900">
            {product.product_name}
          </h1>
          <p className="text-xs text-slate-600">
            {product.manufacturer_name}
            {product.product_code ? ` · ${product.product_code}` : ""}
          </p>
          <div className="mt-2">
            <ProvenanceBadge
              origin={product.content_origin}
              isDemo={product.is_demonstration_data}
            />
          </div>
        </div>
        <div className="text-right">
          {price ? (
            <>
              <p className="text-lg font-black text-slate-900">{price}</p>
              {product.price_as_of ? (
                <p className="text-[10.5px] text-slate-500">
                  as of {product.price_as_of}
                </p>
              ) : null}
            </>
          ) : (
            <p className="text-xs font-medium text-slate-500">
              No published price
            </p>
          )}
        </div>
      </div>

      {/* The spec's tab set, minus the ones that need an account. Those are not
          rendered-and-disabled: an anonymous visitor is told where they live,
          rather than shown a control that refuses. */}
      <div role="tablist" aria-label="Product information" className="mt-4 flex flex-wrap gap-1 border-b border-slate-200">
        {TABS.map((entry) => (
          <button
            key={entry.id}
            role="tab"
            type="button"
            aria-selected={tab === entry.id}
            onClick={() => setTab(entry.id)}
            className={`rounded-t-md px-3 py-1.5 text-xs font-semibold ${
              tab === entry.id
                ? "border-x border-t border-slate-200 bg-white text-slate-900"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            {entry.label}
          </button>
        ))}
      </div>

      <div className="mt-4 text-xs text-slate-700">
        {tab === "overview" ? (
          <>
            <p>{product.description ?? "No published description."}</p>
            <dl className="mt-3 grid gap-2 sm:grid-cols-2">
              <Detail label="Region" value={product.region} />
              <Detail label="Chemistry" value={product.chemistry} />
              <Detail label="Manufacturer" value={product.manufacturer_name} />
              <Detail label="Source" value={product.source_url} isLink />
            </dl>
            <p className="mt-4 rounded-md border border-slate-200 bg-white p-3 text-[11px]">
              Internal benchmarking, composition evidence, similar formulas and
              test results are part of the R&amp;D environment.{" "}
              <Link href="/#access" className="font-semibold underline">
                Request access
              </Link>{" "}
              to reach them.
            </p>
          </>
        ) : tab === "news" ? (
          product.news.length === 0 ? (
            <p>No published developments are linked to this product yet.</p>
          ) : (
            <ul className="space-y-2">
              {product.news.map((item) => (
                <li key={item.id} className="rounded-md border border-slate-200 bg-white p-3">
                  <p className="font-semibold text-slate-900">{item.headline}</p>
                  <p className="mt-0.5 text-[11px] text-slate-600">
                    {item.source_name} · Tier {item.source_tier}
                    {item.published_at ? ` · ${item.published_at.slice(0, 10)}` : ""}
                  </p>
                  <a
                    href={item.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1 inline-block text-[11px] font-semibold underline"
                  >
                    Read the source
                  </a>
                </li>
              ))}
            </ul>
          )
        ) : documents.length === 0 ? (
          <p>No published {TABS.find((t) => t.id === tab)?.label.toLowerCase()} for this product.</p>
        ) : (
          <ul className="space-y-2">
            {documents.map((doc) => (
              <li key={doc.id}>
                <a
                  href={doc.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-semibold underline"
                >
                  {doc.title}
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Shell>
  );
}

function Detail({ label, value, isLink = false }: { label: string; value: string | null; isLink?: boolean }) {
  return (
    <div>
      <dt className="text-[10.5px] font-bold uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="text-xs text-slate-800">
        {value === null || value === "" ? (
          <span className="text-slate-500">Not published</span>
        ) : isLink ? (
          <a href={value} target="_blank" rel="noopener noreferrer" className="underline">
            {value}
          </a>
        ) : (
          value
        )}
      </dd>
    </div>
  );
}

function Unavailable() {
  return (
    <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
      <strong className="font-semibold">The public catalogue is unavailable.</strong> This
      deployment could not reach the intelligence service. Nothing has been
      substituted or estimated.
    </div>
  );
}
