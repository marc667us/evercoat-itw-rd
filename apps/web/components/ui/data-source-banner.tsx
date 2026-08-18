import type { ReactNode } from "react";

import type { DataSource } from "@/lib/api/config";
import { DEMO_NOTICE } from "@/lib/demo/dataset";

/**
 * Which database the figures on this page came from — or that there was
 * none.
 *
 * This replaces nothing: `DemoBanner` still exists and still says the data
 * is synthetic. What this adds is the case that did not exist before Slice
 * 3's back half — a page that MIGHT be live — and the rule that a page can
 * never be silent about which it is.
 *
 * Every design choice in `DemoBanner` carries over for the same reasons,
 * and they are worth restating because they are requirements rather than
 * taste:
 *
 *   · TOP of the page, never a footer. A viewer who screenshots the top
 *     half of the screen must still capture it.
 *   · Not dismissible. A notice that can be closed is absent for exactly
 *     the audience that most needs it.
 *   · Icon and words as well as colour. `CLAUDE.md` §11 forbids
 *     colour-only status, and around 8% of men cannot separate amber from
 *     green reliably — the measured ΔE between this project's pass-green
 *     and fail-red is 4.2 under deuteranopia.
 *   · `role="note"`, so assistive technology announces it as context
 *     about the page rather than as an alert that re-fires on every route
 *     change.
 *
 * The live variant is deliberately QUIET — slate, not green. A cheerful
 * green "LIVE" badge is a reward for a normal condition, and it trains a
 * reader to stop looking at the banner, which defeats the amber one.
 */
export function DataSourceBanner({
  source,
  reason,
}: {
  source: DataSource;
  reason: string | null;
}): ReactNode {
  if (source === "live") {
    return (
      <div
        role="note"
        aria-label="Data source notice"
        className="flex items-start gap-2 border-b border-slate-200 bg-slate-100 px-6 py-2 text-slate-700"
      >
        <span aria-hidden className="mt-px shrink-0 font-bold">
          ⛁
        </span>
        <p className="text-[11px] leading-snug">
          <span className="font-semibold uppercase tracking-wide">Live data</span>{" "}
          — read from the application database through the API.
        </p>
      </div>
    );
  }

  return (
    <div
      role="note"
      aria-label="Demonstration data notice"
      className="flex items-start gap-2 border-b border-amber-300 bg-amber-50 px-6 py-2 text-amber-900"
    >
      <span aria-hidden className="mt-px shrink-0 font-bold">
        ⚠
      </span>
      <p className="text-[11px] leading-snug">
        <span className="font-semibold uppercase tracking-wide">
          Demonstration data
        </span>{" "}
        — {reason ?? DEMO_NOTICE}
      </p>
    </div>
  );
}

/**
 * What a page shows when its request failed.
 *
 * 🔴 THIS IS NOT A FALLBACK TO DEMONSTRATION DATA, AND THAT IS THE POINT.
 *
 * A screen that quietly showed synthetic rows whenever the API was
 * unreachable would be indistinguishable from a working product — the
 * single failure mode this project has hit most often. So a failed request
 * renders the failure, names it, and shows no figures at all.
 *
 * `role="alert"` here and not on the banner: this IS an interruption. The
 * reader asked for data and did not get it.
 */
export function DataSourceError({ error }: { error: Error }): ReactNode {
  return (
    <div
      role="alert"
      className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900"
    >
      <p className="font-semibold">
        <span aria-hidden>✕</span> This data could not be loaded
      </p>
      <p className="mt-1 text-red-800">{error.message}</p>
      <p className="mt-2 text-[11px] text-red-700">
        Nothing is shown below rather than something that might be wrong. No
        demonstration figures have been substituted.
      </p>
    </div>
  );
}

/**
 * Standard page frame.
 *
 * `source` is REQUIRED. A page cannot be built through this frame without
 * declaring where its figures came from, which is the mechanism that stops
 * the next page added from quietly omitting the notice — the same reason
 * `DemoPage` exists at all.
 */
export function DataPage({
  title,
  lede,
  source,
  sourceReason,
  children,
}: {
  title: string;
  lede?: string;
  source: DataSource;
  sourceReason: string | null;
  children: ReactNode;
}): ReactNode {
  return (
    <>
      <DataSourceBanner source={source} reason={sourceReason} />
      <div className="p-6">
        <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
        {lede && (
          <p className="mt-1.5 max-w-3xl text-sm text-slate-600">{lede}</p>
        )}
        <div className="mt-6">{children}</div>
      </div>
    </>
  );
}
