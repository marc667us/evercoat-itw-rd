"use client";

/**
 * ContextSubmenu — the SECOND level of navigation, and the level that was
 * never gated.
 *
 * Navigation narrative §73: the sidebar selects the business domain, this
 * selects the workflow area within it, and the workspace holds the task.
 * `CLAUDE.md` §11 states the same two-level model, and §12 names this
 * component as shared infrastructure that every workspace reuses.
 *
 * 🔴 WHY IT MOVED OUT OF `entity-header.tsx`, AND WHAT WAS WRONG WITH IT.
 *
 * I79 gave the SIDEBAR the caller's own permissions on 2026-08-25. It did not
 * give them to anything else, and this component had no permission concept at
 * all — no field on `SubmenuItem`, no filter, no test. So the first level of
 * navigation was role-scoped and the second level was identical for everybody
 * who could reach the page: Administration offered Roles, Permissions,
 * Organization, Stage Gates, Test Methods, Approval Templates, Notifications
 * and Audit to any caller holding `admin.users`, although the API behind those
 * sections requires `admin.roles`, `admin.organization`, `admin.stage_gates`,
 * `admin.reference_data`, `admin.workflow`, `admin.notifications` and
 * `admin.audit` respectively — seven distinct permissions, one undifferentiated
 * menu.
 *
 * Filtering needs the caller, the caller comes from a hook, and a hook needs a
 * client component — while `EntityHeader` is rendered by server components
 * that export `metadata`. Splitting the file is what lets the submenu know who
 * is asking without making every workspace header a client component too.
 *
 * ⚠️ COSMETIC, AND DELIBERATELY SO (§6, SECURITY.md §3). Hiding a section does
 * not protect it; the route behind it re-authorizes server-side and refuses
 * regardless. What this fixes is honesty: a menu that offers eight sections of
 * which one works is not a smaller product than a menu that offers one, it is
 * a broken-looking one.
 */

import Link from "next/link";
import type { ReactNode } from "react";

import { permits, usePermissions } from "@/lib/permissions";

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
  /**
   * Permission required to see this section at all.
   *
   * Same contract as `NavItem.permission` in `lib/navigation.ts`, and the
   * same treatment of absence: a section naming no permission is offered to
   * any caller who reached the page. Stated as one shared rule in `permits`
   * so the two levels of navigation cannot answer differently for one
   * caller.
   *
   * 🔴 NAME THE PERMISSION THE ROUTE BEHIND IT ACTUALLY REQUIRES. A section
   * gated on a permission its endpoint does not check is decoration, and a
   * section gated on a permission nobody holds is invisible forever — this
   * repository has shipped both shapes before.
   */
  permission?: string;
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

/**
 * Which sections this caller is offered.
 *
 * Pure, exported and tested separately from the component, for the reason
 * `effectiveNavPermissions` is: the interesting cases are about absence, and
 * absence is exactly what a rendering test is worst at telling apart from a
 * component that failed to render.
 */
export function visibleSubmenu(
  items: readonly SubmenuItem[],
  permissions: ReadonlySet<string>,
): SubmenuItem[] {
  return items.filter((item) => permits(permissions, item.permission));
}

export function ContextSubmenu({
  items,
  activeHref,
}: {
  items: readonly SubmenuItem[];
  activeHref: string;
}): ReactNode {
  const permissions = usePermissions();
  const visible = visibleSubmenu(items, permissions);

  // Every section filtered out. Render nothing rather than an empty sticky
  // bar with a border and no content — the same reasoning `visibleNavigation`
  // applies when it drops a group whose items all went: a heading over
  // nothing reads as a page that failed to load.
  if (visible.length === 0) {
    return null;
  }

  return (
    <nav
      aria-label="Section navigation"
      // Sticky while scrolling, and horizontally scrollable rather than
      // wrapping: the Project submenu has 20 items and wrapping it would
      // push the workspace below the fold on a laptop.
      className="sticky top-0 z-10 overflow-x-auto border-b border-slate-200 bg-white px-6"
    >
      <ul role="list" className="flex min-w-max items-center gap-1">
        {visible.map((item) => {
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
