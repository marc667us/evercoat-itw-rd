import type { ReactNode } from "react";

import { DEMO_NOTICE } from "@/lib/demo/dataset";

/**
 * Standing notice that everything on screen is synthetic.
 *
 * NOT DECORATION, AND NOT A FOOTNOTE. `CLAUDE.md` rule 3 requires that
 * predicted or modelled values are never mistaken for measured ones, and
 * §10 makes the same point about dashboards: a screen of invented figures
 * is indistinguishable from a working one at a glance. This deployment
 * shows a client real-looking projects, requirements and measurements, so
 * the only thing keeping that honest is a label that cannot be missed.
 *
 * Consequences of that, deliberately:
 *
 *   · It renders at the TOP of every page, not in a footer. A viewer who
 *     screenshots the top half of a screen must still capture it.
 *   · It is not dismissible. A notice that can be closed is absent for
 *     exactly the audience that most needs it.
 *   · It carries an icon and the word "Demonstration" as well as colour.
 *     Amber alone is not a message — around 8% of men cannot separate
 *     amber from green reliably, and §11 forbids colour-only status.
 *   · `role="note"` so assistive technology announces it as an aside
 *     about the page rather than as navigation or an alert. It is
 *     persistent context, not an interruption, so `role="alert"` would be
 *     wrong: that would re-announce on every route change.
 */
export function DemoBanner(): ReactNode {
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
        — {DEMO_NOTICE}
      </p>
    </div>
  );
}

/**
 * Standard page frame: the banner, a heading, an optional lede.
 *
 * Every Slice 2 screen uses this rather than repeating the markup, so the
 * notice cannot be forgotten on a page added later — the only way to build
 * a page without it is to deliberately not use the frame.
 */
export function DemoPage({
  title,
  lede,
  children,
}: {
  title: string;
  lede?: string;
  children: ReactNode;
}): ReactNode {
  return (
    <>
      <DemoBanner />
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
