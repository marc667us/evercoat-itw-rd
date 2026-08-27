/**
 * EntityHeader — the top of every detail workspace.
 *
 * Navigation narrative §73: the sidebar selects the business domain, the
 * top submenu selects the workflow area within it, and the workspace
 * holds the task. This is the header above that workspace.
 *
 * ⚠️ `ContextSubmenu` USED TO LIVE HERE AND NOW LIVES IN
 * `components/ui/context-submenu.tsx`. It had to become a client component to
 * filter its sections by the caller's permissions, and this file is rendered
 * by server components that export `metadata`. The split is what keeps both
 * true. See that file for what was wrong with an ungated second level.
 *
 * The header answers the questions the UI narrative says every major
 * page must answer: *where am I in the process*, *what is the current
 * status*, and *what requires action*. It is used by Project, Formula,
 * Lab Batch, Test, Failure, Pilot and Product — seven workspaces, one
 * component. If an eighth needs a different header, the answer is a prop,
 * not a second component.
 */

import Link from "next/link";
import type { ReactNode } from "react";

/**
 * A count for a header field, or an em dash while it is not yet known.
 *
 * 🔴 "0" IS AN ANSWER AND AN EMPTY LIST BEFORE THE RESPONSE ARRIVES IS NOT.
 *
 * Every Administration header rendered `String(rows.length)` over a list that
 * starts empty, so each one reported **0 roles**, **0 permissions**, **0
 * stages** for the whole of the first request — and reported exactly the same
 * thing when the caller lacked the permission to read it, and again when the
 * request failed. A reader cannot tell "there are none" from "nobody has said
 * yet", and this application has already shipped the same shape once, where an
 * empty requirement set rendered ALL REQUIREMENTS PASSED. Codex found it.
 *
 * Absence must never present as an answer.
 */
export function headerCount(rows: { readonly length: number }, known: boolean): string {
  return known ? String(rows.length) : "—";
}

export interface Crumb {
  label: string;
  href: string;
}

export interface HeaderField {
  label: string;
  value: ReactNode;
}

export function EntityHeader({
  eyebrow,
  title,
  crumbs,
  fields,
  status,
  actions,
}: {
  /** Record type + code, e.g. "Formula RDP-2026-014-F008". */
  eyebrow: string;
  title: string;
  crumbs?: Crumb[];
  /** Identity fields kept visible so context is never lost on navigation. */
  fields?: HeaderField[];
  /** A StatusBadge, typically. */
  status?: ReactNode;
  /** Primary actions. Availability is decided by the server, not here. */
  actions?: ReactNode;
}): ReactNode {
  return (
    <header className="border-b border-slate-200 bg-white px-6 pt-4">
      {crumbs && crumbs.length > 0 && (
        <nav aria-label="Breadcrumb" className="mb-2">
          <ol className="flex flex-wrap items-center gap-1 text-[11px] text-slate-500">
            {crumbs.map((c, i) => (
              <li key={c.href} className="flex items-center gap-1">
                {i > 0 && <span aria-hidden>/</span>}
                <Link href={c.href} className="hover:text-slate-900 hover:underline">
                  {c.label}
                </Link>
              </li>
            ))}
          </ol>
        </nav>
      )}

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
            {eyebrow}
          </div>
          <h1 className="mt-0.5 truncate text-lg font-semibold text-slate-900">
            {title}
          </h1>
        </div>
        <div className="flex items-center gap-3">
          {status}
          {actions}
        </div>
      </div>

      {fields && fields.length > 0 && (
        // Project context stays on screen so users do not lose their place
        // moving between formula, laboratory and testing pages
        // (UI narrative, Project Context Bar).
        <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1.5">
          {fields.map((f) => (
            <div key={f.label} className="flex items-baseline gap-1.5">
              <dt className="text-[11px] uppercase tracking-wide text-slate-500">
                {f.label}
              </dt>
              <dd className="text-xs font-medium text-slate-700">{f.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </header>
  );
}
