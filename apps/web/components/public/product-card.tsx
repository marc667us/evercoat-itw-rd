"use client";

/**
 * The competitor product card.
 *
 * 🔴 ADOPTED FROM SOLARPRO'S MARKETPLACE CARD, NOT INVENTED.
 *
 * The owner's instruction was explicit: "read solarpro market place product
 * card and adopt". Its shape, from
 * `Desktop/solar-pv-designer-lite/templates/marketplace.html`:
 *
 *   category eyebrow → product name → brand · model → status badge →
 *   price right-aligned with unit → spec line → literature/datasheet link
 *   row → footer with supplier and actions
 *
 * 🔴 AND THE MOST VALUABLE THING IT DOES IS WHAT IT SHOWS WHEN SIGNED OUT.
 *
 * SolarPro renders the CARD PUBLICLY and routes gated actions through an
 * action gate (`marketplace_action_gate`) rather than hiding the card. That is
 * the whole pattern for "public marketplace, sign in to act", and it is
 * already proven in production there. Copied deliberately: an anonymous
 * visitor sees the product and the price, and the actions that need an
 * account say so instead of vanishing.
 *
 * 🔴 THE DETAIL LINK IS A QUERY PARAMETER, NOT `/marketplace/[id]`.
 *
 * This deployment builds with `output: "export"` when `isExport` is set, and a
 * dynamic segment there needs `generateStaticParams` — a list of ids known at
 * BUILD time. A live global catalogue does not have one.
 *
 * `/projects/[code]` is what that looks like when it is done anyway: it renders
 * from `lib/demo/dataset` and 404s for every live record. The implementation
 * plan for this feature predicted the same wall for "a card linking through to
 * the formulation", so the card does not walk into it. `?product=<id>` resolves
 * at run time, from the API, for any id — including one created after the
 * build.
 *
 * ⚠️ THE PROVENANCE BADGE IS NOT DECORATION. `DemoBanner`'s header says it for
 * the internal app: a screen of invented figures is indistinguishable from a
 * working one at a glance. Here the stakes are higher, because these cards
 * carry REAL manufacturer names. A row whose content is synthetic says so on
 * the card itself, every time, and the badge is not dismissable.
 */

import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/components/providers/auth-provider";
import { apiRequest } from "@/lib/api/client";
import { formatPrice, type PublicProduct } from "@/lib/api/public-client";

export function ProvenanceBadge({
  origin,
  isDemo,
}: {
  origin: PublicProduct["content_origin"];
  isDemo: boolean;
}) {
  if (origin === "verified") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-300 bg-emerald-50 px-2 py-0.5 text-[10.5px] font-semibold text-emerald-800">
        ✓ Verified against source
      </span>
    );
  }
  if (origin === "source_derived") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-sky-300 bg-sky-50 px-2 py-0.5 text-[10.5px] font-semibold text-sky-800">
        ↗ From a published source
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border border-amber-400 bg-amber-50 px-2 py-0.5 text-[10.5px] font-semibold text-amber-900"
      title={
        isDemo
          ? "Demonstration content. Not a real market record — generated to show the shape of the catalogue."
          : "Synthetic content."
      }
    >
      {/* Text, not colour alone — §11 forbids colour-only status, and this is
          the most important thing on the card to get across. */}
      ! Demonstration data — not a real market record
    </span>
  );
}


/**
 * The signed-in half of a public card: bring this product into the pipeline.
 *
 * 🔴 IT ADOPTS AN IDENTITY. IT DOES NOT REVERSE-ENGINEER A FORMULA.
 *
 * The owner asked for a link that pulls the product's formulation into the
 * pipeline. What this creates is the tenant's own competitor record, linked to
 * the public row — the FIRST STEP of a teardown, and the point at which the
 * Composition Evidence Matrix, the benchmark and the improvement-opportunity
 * workflow become available for it.
 *
 * What it deliberately does not do is assert what is in the product. Migration
 * 056 settled that for this schema: *"THE MATRIX IS NOT A FORMULA. There is
 * deliberately no competitor-recipe table."* Evidence accrues from an SDS, a
 * label, a sample and lab work, each claim carrying its source and a
 * confidence — and "verified" needs a named human holding `compliance.review_sds`.
 *
 * A screen that showed a competitor's recipe would be presenting an inference
 * as a known fact about a named company's trade secret. Rule 3 forbids the
 * first half; the second half is worse.
 *
 * ⚠️ SHOWN ONLY WHEN SIGNED IN, and not hidden by permission. `material.edit`
 * is what the server requires; a chemist without it gets a refusal in words
 * rather than a control that silently is not there. §6: frontend checks are
 * cosmetic and the server re-enforces.
 */
function AdoptIntoPipeline({ product }: { product: PublicProduct }) {
  const { session } = useAuth();
  const [state, setState] = useState<"idle" | "working" | "done" | "failed">("idle");
  const [message, setMessage] = useState<string | null>(null);

  if (session.status !== "authenticated") return null;

  if (state === "done") {
    return (
      <p className="mt-2 text-[11px] font-semibold text-emerald-800">
        Added to your pipeline — open Competitor Intelligence to record evidence.
      </p>
    );
  }

  return (
    <div className="mt-2">
      <button
        type="button"
        disabled={state === "working"}
        onClick={async () => {
          setState("working");
          setMessage(null);
          try {
            await apiRequest(
              {
                path: "/api/competitors/from-public",
                method: "POST",
                body: { public_product_id: product.id },
                credentials: session.credentials,
              },
              (payload) => payload,
            );
            setState("done");
          } catch (error) {
            setState("failed");
            setMessage(
              error instanceof Error
                ? error.message
                : "the request could not be completed",
            );
          }
        }}
        className="w-full rounded-md border border-slate-400 px-3 py-1.5 text-[11px] font-semibold text-slate-900 hover:bg-slate-50 disabled:opacity-50"
        title="Creates your own competitor record linked to this product. No composition claim is made."
      >
        {state === "working" ? "Adding…" : "Bring into the R&D pipeline"}
      </button>
      {state === "failed" && message ? (
        <p className="mt-1 text-[11px] text-red-700">{message}</p>
      ) : null}
    </div>
  );
}

export function ProductCard({ product }: { product: PublicProduct }) {
  const price = formatPrice(product.price_amount, product.price_currency);

  return (
    <article className="flex h-full flex-col rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10.5px] font-bold uppercase tracking-wide text-slate-500">
            {product.category ?? "Uncategorised"}
            {product.chemistry ? ` · ${product.chemistry}` : ""}
          </p>
          <h3 className="mt-1 text-sm font-bold leading-tight text-slate-900">
            <Link href={`/marketplace?product=${product.id}`} className="hover:underline">
              {product.product_name}
            </Link>
          </h3>
          <p className="text-xs text-slate-600">
            {product.manufacturer_name}
            {product.product_code ? ` · ${product.product_code}` : ""}
          </p>
        </div>

        <div className="shrink-0 text-right">
          {/* ⚠️ A MISSING PRICE SAYS SO. It does not render as 0, and it does
              not render as blank — `Number("")` is 0, and this project has
              already shipped a blank measurement as a GREEN PASS. */}
          {price ? (
            <>
              <p className="text-base font-black text-slate-900">{price}</p>
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

      <div className="mt-2">
        <ProvenanceBadge
          origin={product.content_origin}
          isDemo={product.is_demonstration_data}
        />
      </div>

      {product.description ? (
        <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-slate-600">
          {product.description}
        </p>
      ) : null}

      <div className="mt-auto flex items-center justify-between gap-2 border-t border-slate-200 pt-3">
        <span className="text-[11px] text-slate-500">
          {product.region ?? "Global"}
        </span>
        <Link
          href={`/marketplace?product=${product.id}`}
          className="rounded-md border border-slate-300 px-3 py-1 text-[11px] font-semibold text-slate-800 hover:bg-slate-50"
        >
          Details, data sheet &amp; safety data
        </Link>
      </div>
      <AdoptIntoPipeline product={product} />
    </article>
  );
}
