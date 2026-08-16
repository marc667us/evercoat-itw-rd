/**
 * KpiCard — a dashboard metric that leads somewhere.
 *
 * Source rule (Dashboard narrative §3): every dashboard must answer
 * *what is happening*, *why*, and *what action is required*. A number on
 * its own answers only the first, and "Adhesion Failures: 7" has never
 * caused anyone to do anything.
 *
 * So `href` is required, not optional. Every KPI drills down to the
 * records behind it — that traceability is called essential in the
 * source, and a card that cannot be clicked is decoration.
 *
 * Counts here are ACTIONABLE items, never total rows. "Failures 3" means
 * three awaiting me, not three in the database. A badge that counts
 * everything trains people to ignore the badge.
 */

import Link from "next/link";
import type { ReactNode } from "react";

import type { DisplayStatus } from "./status-badge";

export interface KpiCardProps {
  label: string;
  value: number | string;
  /** Where this number came from. Required — see above. */
  href: string;
  /** Optional one-line "why", e.g. "2 blocking pilot progression". */
  context?: string;
  /** Tints the value only. Never the sole signal; the label still reads plainly. */
  tone?: DisplayStatus;
  /** Renders a loading skeleton instead of a misleading zero. */
  loading?: boolean;
}

const TONE: Record<DisplayStatus, string> = {
  green: "text-status-pass",
  red: "text-status-fail",
  yellow: "text-status-conditional",
  neutral: "text-slate-900",
};

export function KpiCard({
  label,
  value,
  href,
  context,
  tone = "neutral",
  loading = false,
}: KpiCardProps): ReactNode {
  if (loading) {
    // A skeleton, not a zero. Rendering "0" while data is in flight is
    // indistinguishable from "nothing needs your attention" — which is
    // precisely the wrong thing to tell someone about failed tests.
    return (
      <div className="rounded border border-slate-200 bg-white p-4">
        <div className="h-3 w-24 animate-pulse rounded bg-slate-100" />
        <div className="mt-3 h-7 w-12 animate-pulse rounded bg-slate-100" />
      </div>
    );
  }

  return (
    <Link
      href={href}
      className="group block rounded border border-slate-200 bg-white p-4 transition-colors hover:border-slate-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-900"
    >
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
        {label}
      </div>
      <div className={`mt-1.5 text-2xl font-semibold tabular-nums ${TONE[tone]}`}>
        {value}
      </div>
      {context && (
        <div className="mt-1 text-[11px] leading-snug text-slate-500">{context}</div>
      )}
      <span className="sr-only">View the records behind {label}</span>
    </Link>
  );
}

/**
 * KPI row. Dashboards open with actionable figures, not charts — the
 * source is explicit that the first row is KPIs, the second is work
 * needing intervention, and analytics come after (UI narrative,
 * Dashboard UI).
 */
export function KpiRow({ children }: { children: ReactNode }): ReactNode {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
      {children}
    </div>
  );
}
