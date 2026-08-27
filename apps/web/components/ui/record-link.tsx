/**
 * Linking to a record, and saying so when there is nowhere to link TO.
 *
 * 🔴 EVERY LIVE ROW LINKED TO A 404, AND THE LIST LOOKED FINE.
 *
 * S2 wired the list screens. The detail screens are still built from the
 * bundled fixture: `app/projects/[code]/page.tsx` and
 * `app/formulations/[code]/page.tsx` derive their routes from
 * `generateStaticParams()` over `PROJECTS` and `FORMULAS`, and under
 * `NEXT_OUTPUT=export` — which is what the deployed site is — a code that
 * is not in the fixture has **no exported page at all**.
 *
 * So the moment the list showed database rows, every code in it linked to
 * a page that does not exist. `next.config.mjs` predicted precisely this:
 * *"That stops being true at Slice 3, when the API is wired in; at that
 * point a static host cannot serve the product."* The Supervisor found
 * that the slice had landed without addressing it.
 *
 * A dead link is worse than no link. It looks like a working product
 * until it is clicked, and then it looks broken rather than unfinished —
 * a reader concludes the record is missing, not that the screen has not
 * been built.
 *
 * So a code is a link only when a page for it actually exists in this
 * build, and otherwise it renders as text that says why. The predicate is
 * exact rather than approximate: the exported pages ARE the fixture's
 * codes, so asking the fixture is asking the build.
 *
 * This goes away when the detail screens are wired (S3) — at which point
 * `hasDetailPage` becomes `() => true` and this component collapses to a
 * link. It is deliberately one place so that is a one-line change.
 */

import Link from "next/link";

import { formulaByCode, projectByCode } from "@/lib/demo/dataset";

export type RecordKind = "project" | "formula";

/** True when THIS BUILD exported a detail page for that code. */
export function hasDetailPage(kind: RecordKind, code: string): boolean {
  return kind === "project"
    ? projectByCode(code) !== undefined
    : formulaByCode(code) !== undefined;
}

const HREF: Record<RecordKind, (code: string) => string> = {
  project: (code) => `/projects/${code}`,
  formula: (code) => `/formulations/${code}`,
};

const NOT_BUILT: Record<RecordKind, string> = {
  // ✅ CORRECTED 2026-08-27. This read "the project detail screen is not wired
  // to the database yet", which stopped being true when `/projects/workspace`
  // shipped. The refusal still applies — but for a different reason, and saying
  // the wrong one would send a reader looking for a missing screen rather than
  // a missing record.
  project:
    "this is a demonstration row with no record in the database, so there is nothing for the project workspace to open",
  formula:
    "the formula detail screen is not wired to the database yet, so there is no page for this record",
};

/**
 * A record code: a link when it leads somewhere, plain text when it would
 * not.
 *
 * `title` rather than a visible note, because this appears in a grid cell
 * repeated on every row — a paragraph per row would drown the data. The
 * page-level notice belongs on the screen, not here.
 */
export function RecordLink({
  kind,
  code,
  className,
}: {
  kind: RecordKind;
  code: string;
  className?: string;
}): React.ReactNode {
  if (!hasDetailPage(kind, code)) {
    return (
      <span
        className={className ?? "font-medium text-slate-900"}
        title={NOT_BUILT[kind]}
        data-testid="record-without-detail-page"
      >
        {code}
      </span>
    );
  }
  return (
    <Link
      href={HREF[kind](code)}
      className={className ?? "font-medium text-slate-900 underline underline-offset-2"}
    >
      {code}
    </Link>
  );
}

/**
 * A value that is not there, announced rather than left blank.
 *
 * 🔴 `—` ALONE IS NOT AN ANSWER TO A SCREEN READER.
 *
 * This was written out three times in one commit — twice as a local
 * `Absent` and once inlined — which is the duplication this codebase
 * otherwise refuses (`versionStatus` and `supplierStatus` were narrowed in
 * that very commit for exactly this reason). The Supervisor noted it.
 *
 * `text-slate-500`, NOT `text-slate-400`: slate-400 on white is about
 * 2.9:1 against a required 4.5:1, the exact failure axe-core found on
 * this project's sidebar headings. And axe CANNOT catch it here, because
 * the glyph is `aria-hidden` and axe skips hidden nodes for contrast.
 */
export function Absent({ what }: { what: string }): React.ReactNode {
  return (
    <span className="text-slate-500" title={what}>
      <span aria-hidden>—</span>
      <span className="sr-only">{what}</span>
    </span>
  );
}
