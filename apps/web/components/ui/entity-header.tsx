/**
 * EntityHeader + ContextSubmenu — the top of every detail workspace.
 *
 * Navigation narrative §73: the sidebar selects the business domain, the
 * top submenu selects the workflow area within it, and the workspace
 * holds the task. This component is the second of those.
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

export interface Crumb {
  label: string;
  href: string;
}

export interface HeaderField {
  label: string;
  value: ReactNode;
}

export interface SubmenuItem {
  label: string;
  href: string;
  /**
   * No page exists at this href yet.
   *
   * Rendered as an inert span rather than a link, exactly as the sidebar
   * treats a future-slice destination. Without this every submenu entry was
   * a live anchor regardless of its `state`, so the Administration header
   * advertised /admin/roles, /admin/permissions and five more as working
   * links straight into a 404. Invisible while Administration was filtered
   * out of the sidebar; a client-facing defect the moment it was not.
   * Raised by Codex.
   */
  unavailable?: boolean;
  /** Workflow state, rendered as a marker beside the label. */
  state?: "complete" | "active" | "not-started" | "blocked" | "failed";
  /** Actionable count, e.g. 3 open failures. Never a total row count. */
  count?: number;
}

/**
 * Workflow-state markers from Navigation narrative §59.
 *
 * Paired with text in the accessible name, never shape alone — the same
 * reasoning as StatusBadge: a glyph that only means something visually
 * communicates nothing in a printed report or to a screen reader.
 */
const STATE_MARK: Record<
  NonNullable<SubmenuItem["state"]>,
  { glyph: string; label: string; className: string }
> = {
  complete: { glyph: "✓", label: "complete", className: "text-status-pass" },
  active: { glyph: "●", label: "active", className: "text-slate-900" },
  // slate-500, not slate-300. These glyphs carry workflow state, so they
  // are content, not decoration — and slate-300 on white is about 1.5:1,
  // which is not readable. axe-core does NOT catch this: the marks are
  // `aria-hidden` (their meaning is already given in text for screen
  // readers), and axe skips hidden nodes for contrast. So an automated
  // scan can pass while a sighted user cannot see the state at all.
  // Found by review, not by the scanner.
  "not-started": { glyph: "○", label: "not started", className: "text-slate-500" },
  blocked: { glyph: "!", label: "blocked", className: "text-status-conditional" },
  failed: { glyph: "✕", label: "failed", className: "text-status-fail" },
};

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

export function ContextSubmenu({
  items,
  activeHref,
}: {
  items: SubmenuItem[];
  activeHref: string;
}): ReactNode {
  return (
    <nav
      aria-label="Section navigation"
      // Sticky while scrolling, and horizontally scrollable rather than
      // wrapping: the Project submenu has 20 items and wrapping it would
      // push the workspace below the fold on a laptop.
      className="sticky top-0 z-10 overflow-x-auto border-b border-slate-200 bg-white px-6"
    >
      <ul role="list" className="flex min-w-max items-center gap-1">
        {items.map((item) => {
          const active = item.href === activeHref;
          const mark = item.state ? STATE_MARK[item.state] : undefined;

          return (
            <li key={item.href}>
              {item.unavailable ? (
                <span
                  aria-disabled="true"
                  // slate-500, not slate-400. At this size WCAG 2.1 AA
                  // wants 4.5:1 and slate-400 on white is about 2.9:1 —
                  // the identical contrast failure already corrected in
                  // the sidebar. axe skips it because of aria-disabled, so
                  // CI would have stayed green while seven of the eight
                  // Administration sections were unreadable to a low-vision
                  // reader. Raised by the Supervisor.
                  className="flex items-center gap-1.5 border-b-2 border-transparent px-1 pb-2 text-xs text-slate-500"
                >
                  {mark && (
                    <span aria-hidden className={`text-[11px] ${mark.className}`}>
                      {mark.glyph}
                    </span>
                  )}
                  {item.label}
                  <span className="sr-only"> — not yet available</span>
                </span>
              ) : (
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={[
                  "flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm transition-colors",
                  active
                    ? "border-slate-900 font-medium text-slate-900"
                    : "border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900",
                ].join(" ")}
              >
                {mark && (
                  <span aria-hidden className={`text-[11px] ${mark.className}`}>
                    {mark.glyph}
                  </span>
                )}
                <span>{item.label}</span>
                {mark && <span className="sr-only"> — {mark.label}</span>}
                {item.count !== undefined && item.count > 0 && (
                  <span
                    className="rounded-full bg-slate-200 px-1.5 text-[10px] font-semibold text-slate-700"
                    aria-label={`${item.count} needing attention`}
                  >
                    {item.count > 99 ? "99+" : item.count}
                  </span>
                )}
              </Link>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
