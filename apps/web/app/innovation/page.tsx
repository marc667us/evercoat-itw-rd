import type { Metadata } from "next";

import Link from "next/link";

import { DemoPage } from "@/components/ui/demo-banner";
import { StatusBadge } from "@/components/ui/status-badge";
import { OPPORTUNITIES } from "@/lib/demo/dataset";

export const metadata: Metadata = { title: "Innovation" };

/**
 * Opportunities — the front of the digital thread.
 *
 * `CLAUDE.md` §2 begins the thread at Opportunity → Project, and requires
 * that no record becomes an isolated island. So a converted opportunity
 * links FORWARD to the project it produced; without that link this screen
 * would be a list of ideas with no way to see what became of them, which
 * is precisely the island the rule forbids.
 */
export default function InnovationPage() {
  return (
    <DemoPage
      title="Innovation"
      lede="Opportunities under evaluation, with the decision taken on each. A
            converted opportunity links forward to the project it produced — the
            first link in the digital thread."
    >
      <ul className="space-y-3">
        {OPPORTUNITIES.map((o) => (
          <li
            key={o.opportunity_code}
            className="rounded border border-slate-200 bg-white p-4"
          >
            <div className="flex flex-wrap items-baseline gap-3">
              <span className="text-xs font-medium tabular-nums text-slate-500">
                {o.opportunity_code}
              </span>
              <h2 className="flex-1 text-sm font-semibold text-slate-900">
                {o.title}
              </h2>
              {o.status === "converted" ? (
                <StatusBadge status="green" label="CONVERTED" size="sm" />
              ) : o.status === "under_review" ? (
                <StatusBadge
                  status="yellow"
                  label="UNDER REVIEW"
                  reason="Awaiting a documented decision before it can convert."
                  size="sm"
                />
              ) : (
                <StatusBadge status="neutral" label="PROPOSED" size="sm" />
              )}
            </div>

            <dl className="mt-3 grid gap-x-6 gap-y-2 text-xs md:grid-cols-2">
              <div>
                <dt className="font-medium text-slate-500">Market need</dt>
                <dd className="text-slate-700">{o.market_need}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-500">Technical concept</dt>
                <dd className="text-slate-700">{o.technical_concept}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-500">Product family</dt>
                <dd className="text-slate-700">{o.product_family}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-500">Target application</dt>
                <dd className="text-slate-700">{o.target_application}</dd>
              </div>
            </dl>

            {o.rationale && (
              <p className="mt-3 border-l-2 border-slate-200 pl-3 text-xs text-slate-600">
                <span className="font-medium">Decision rationale:</span>{" "}
                {o.rationale}
              </p>
            )}

            {o.converted_to_project && (
              <p className="mt-3 text-xs">
                Became{" "}
                <Link
                  href={`/projects/${o.converted_to_project}`}
                  className="font-medium underline underline-offset-2"
                >
                  {o.converted_to_project}
                </Link>
              </p>
            )}
          </li>
        ))}
      </ul>
    </DemoPage>
  );
}
