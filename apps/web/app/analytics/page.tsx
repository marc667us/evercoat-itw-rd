"use client";

/**
 * Analytics — the Intelligence department's first screen.
 *
 * 🔴 THIS SCREEN EXISTS BECAUSE TWO PERMISSIONS ENFORCED NOTHING.
 *
 * `analytics.view` is granted to nine of the ten seeded roles and
 * `analytics.portfolio` to two, and until this slice no line of application
 * code read either. `navigation.ts` has declared this destination since the
 * navigation was written — `{ id: "analytics", href: "/analytics",
 * permission: "analytics.view" }` — and it rendered DISABLED, so the
 * permission gated a link that went nowhere.
 *
 * ---------------------------------------------------------------------------
 * 🔴 IT SHOWS COLOURS AND DOES NOT DECIDE ONE. THE DISTINCTION IS THE POINT.
 * ---------------------------------------------------------------------------
 *
 * `/testing` renders NO traffic light, and says so at length: the queue
 * endpoint withholds the inputs §10's algorithm needs, so a browser colouring
 * those rows would be deriving a status from an incomplete input — the one
 * thing §10 forbids.
 *
 * This screen is the opposite case and it is worth being exact about why.
 * Every colour here was counted BY THE SERVER, from
 * `derive_disposition`'s own output, and arrives as `by_colour: {green: 9,
 * yellow: 4}`. Nothing on this page inspects a row to decide a colour.
 * Rendering a count the server computed is display; computing one here would
 * be a second answer to "is this test GREEN".
 *
 * The line to hold: if you find yourself writing `rows.filter(r => ...)` to
 * produce a status figure, stop — that is the derivation, and it belongs in
 * `app/calculations/testing.py` where it already is.
 *
 * ⚠️ COLOUR IS NEVER THE SOLE INDICATOR (§11). Every disposition tile carries
 * its word — GREEN / YELLOW / RED — and an icon, because around 8% of men
 * cannot separate amber from green reliably. A row of coloured numbers with
 * no labels would be unreadable for them and would fail axe-core's contrast
 * rules besides.
 *
 * ⚠️ AND THE AUTOMATIC EVALUATION IS SHOWN BESIDE THE DISPOSITION, NEVER
 * MERGED. §10: *"a low-margin pass awaiting approval is both a pass and not
 * final, and one field cannot say that."* `by_calculated_result` and
 * `by_colour` are two separate blocks for exactly that reason.
 */

import Link from "next/link";
import type { ReactNode } from "react";

import { DataSourceError, LiveOnlyPage } from "@/components/ui/data-source-banner";
import { useAnalytics } from "@/lib/api/hooks";
import type { Analytics, PortfolioProject } from "@/lib/api/analysis";

/**
 * The three dispositions, with the word and the icon §11 requires.
 *
 * `unknown` is a real bucket the server emits — a test with no derived colour
 * yet — and it is rendered plainly rather than hidden. A count that silently
 * dropped a bucket would make the tiles disagree with the total for a reason
 * nobody could see.
 */
const DISPOSITION: Record<string, { label: string; icon: string; className: string }> = {
  green: { label: "GREEN", icon: "✓", className: "text-status-pass" },
  yellow: { label: "YELLOW", icon: "!", className: "text-status-conditional" },
  red: { label: "RED", icon: "✕", className: "text-status-fail" },
  unknown: { label: "NOT DERIVED", icon: "–", className: "text-slate-500" },
};

/** A counted breakdown, rendered as a definition list. Empty says so. */
function Breakdown({
  title,
  note,
  counts,
}: {
  title: string;
  note?: string;
  counts: Record<string, number>;
}): ReactNode {
  const entries = Object.entries(counts);
  return (
    <section className="rounded border border-slate-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      {note ? <p className="mt-1 text-xs text-slate-600">{note}</p> : null}
      {entries.length === 0 ? (
        // 🔴 AN EMPTY SECTION IS AN ANSWER; AN INVENTED ONE IS NOT.
        // Never a placeholder figure, never a dash standing in for a number.
        <p className="mt-3 text-sm text-slate-600">Nothing counted in this scope.</p>
      ) : (
        <dl className="mt-3 space-y-1">
          {entries.map(([bucket, n]) => (
            <div key={bucket} className="flex items-baseline justify-between gap-4">
              <dt className="text-sm text-slate-700">{bucket.replace(/_/g, " ")}</dt>
              <dd className="font-mono text-sm tabular-nums text-slate-900">{n}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}

/** The disposition tiles — colour AND word AND icon, never colour alone. */
function Dispositions({ counts }: { counts: Record<string, number> }): ReactNode {
  const buckets = Object.entries(counts);
  if (buckets.length === 0) {
    return <p className="text-sm text-slate-600">No tests counted in this scope.</p>;
  }
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {buckets.map(([colour, n]) => {
        const d = DISPOSITION[colour] ?? {
          label: colour.toUpperCase(),
          icon: "•",
          className: "text-slate-900",
        };
        return (
          <div key={colour} className="rounded border border-slate-200 bg-white p-4">
            <p className="text-xs font-semibold tracking-wide text-slate-600">
              <span aria-hidden className="mr-1">
                {d.icon}
              </span>
              {d.label}
            </p>
            <p className={`mt-2 font-mono text-3xl tabular-nums ${d.className}`}>{n}</p>
          </div>
        );
      })}
    </div>
  );
}

/** The organization-wide breakdown, or an honest statement of its absence. */
function Portfolio({
  included,
  projects,
}: {
  included: boolean;
  projects: readonly PortfolioProject[] | null;
}): ReactNode {
  if (!included || projects === null) {
    // 🔴 ABSENT, NOT EMPTY — and the page SAYS WHICH.
    //
    // The server returns `by_project: null` and `portfolio_included: false`
    // for a caller without `analytics.portfolio`, rather than `[]`. An empty
    // table here would tell a Chemist this organization has no projects,
    // which is a different claim and usually a false one. Naming the missing
    // permission is what makes this a gap somebody can act on rather than a
    // screen that looks broken.
    return (
      <p
        data-testid="portfolio-withheld"
        className="rounded border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700"
      >
        <span aria-hidden className="mr-1 font-bold">
          –
        </span>
        The organization-wide breakdown needs the{" "}
        <code className="font-mono text-xs">analytics.portfolio</code> permission, which this
        account does not hold. This is not an empty result: the figures were never computed.
      </p>
    );
  }

  if (projects.length === 0) {
    return <p className="text-sm text-slate-600">No projects are visible in this organization.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[42rem] border-collapse text-sm">
        <caption className="sr-only">Testing activity by project</caption>
        <thead>
          <tr className="border-b border-slate-300 text-left text-xs uppercase tracking-wide text-slate-600">
            <th scope="col" className="py-2 pr-4">
              Project
            </th>
            <th scope="col" className="py-2 pr-4">
              Stage
            </th>
            <th scope="col" className="py-2 pr-4">
              Status
            </th>
            <th scope="col" className="py-2 pr-4 text-right">
              Tests
            </th>
            <th scope="col" className="py-2 pr-4">
              Dispositions
            </th>
          </tr>
        </thead>
        <tbody>
          {projects.map((p) => (
            <tr key={p.project_id} className="border-b border-slate-100">
              <td className="py-2 pr-4">
                {/* §2: every figure drills down to real source records. */}
                <Link
                  href={`/projects/${p.project_code}`}
                  className="font-medium text-slate-900 underline decoration-slate-300 underline-offset-2"
                >
                  {p.project_code}
                </Link>
                <span className="ml-2 text-slate-600">{p.name}</span>
              </td>
              <td className="py-2 pr-4 text-slate-700">{p.current_stage ?? "—"}</td>
              <td className="py-2 pr-4 text-slate-700">{p.status}</td>
              <td className="py-2 pr-4 text-right font-mono tabular-nums text-slate-900">
                {p.tests}
                {/* The cap is stated per project, not hidden. */}
                {p.truncated ? (
                  <span className="ml-1 text-xs text-slate-500">(capped at {p.limit})</span>
                ) : null}
              </td>
              <td className="py-2 pr-4">
                <span className="font-mono text-xs text-slate-700">
                  {Object.entries(p.by_colour)
                    .map(([c, n]) => `${(DISPOSITION[c]?.label ?? c).toLowerCase()} ${n}`)
                    .join(" · ") || "none"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AnalyticsPage(): ReactNode {
  const { data, isLoading, error, unavailable } = useAnalytics<Analytics>((live) => live);

  return (
    <LiveOnlyPage
      title="Analytics"
      lede="Testing and laboratory activity, counted from records this account can open."
      unavailable={unavailable}
      notInvented="test dispositions and laboratory activity"
    >
      <div className="space-y-6 px-6 py-6">
        {error ? <DataSourceError error={error} /> : null}

        {isLoading ? (
          <p className="text-sm text-slate-600">Loading…</p>
        ) : data === undefined ? null : (
          <>
            <section aria-labelledby="dispositions-heading" className="space-y-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 id="dispositions-heading" className="text-lg font-semibold text-slate-900">
                  Final disposition
                </h2>
                <p className="text-xs text-slate-600">
                  {data.testing.counted} test{data.testing.counted === 1 ? "" : "s"} counted
                  {data.testing.truncated ? (
                    // 🔴 THE SERVER'S CAP, NOT A NUMBER THIS FILE KNOWS.
                    //
                    // This read `capped at {"200"}` — a literal that merely
                    // happened to match the default request. A caller asking
                    // for `?limit=10` would have been told the cap was 200.
                    // The endpoint reports what it enforced; rendering
                    // anything else invents a fact in the one place whose job
                    // is to say the count is incomplete. Raised by Codex.
                    <span className="ml-1 font-semibold text-amber-800">
                      — capped at {data.testing.limit}, more exist
                    </span>
                  ) : null}
                </p>
              </div>
              <p className="text-xs text-slate-600">
                Derived by the server from §10&rsquo;s ordered rules. This screen displays those
                counts; it does not compute a status.
              </p>
              <Dispositions counts={data.testing.by_colour} />
            </section>

            <div className="grid gap-4 lg:grid-cols-3">
              <Breakdown
                title="Automatic evaluation"
                note="What the numbers alone concluded — shown separately from the disposition above, because a low-margin pass awaiting approval is both a pass and not final."
                counts={data.testing.by_calculated_result}
              />
              <Breakdown
                title="Authority"
                note="A green screening test is never qualification evidence."
                counts={data.testing.by_authority_level}
              />
              <Breakdown
                title="Purpose"
                counts={data.testing.by_test_purpose}
              />
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <Breakdown
                title="Which rule decided"
                note="Rule number out of §10's fourteen ordered rules. A traffic light nobody can explain is a traffic light nobody trusts."
                counts={data.testing.by_rule}
              />
              <Breakdown
                title="Laboratory batches"
                note={`${data.laboratory.total} batch${data.laboratory.total === 1 ? "" : "es"} by lifecycle status. This is a stored column, not a traffic light.`}
                counts={data.laboratory.by_status}
              />
            </div>

            <section aria-labelledby="portfolio-heading" className="space-y-3">
              <h2 id="portfolio-heading" className="text-lg font-semibold text-slate-900">
                Portfolio — by project
              </h2>
              <Portfolio included={data.portfolio_included} projects={data.by_project} />
            </section>
          </>
        )}
      </div>
    </LiveOnlyPage>
  );
}
