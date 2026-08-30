"use client";

/**
 * Left sidebar — selects the business domain.
 *
 * The top contextual submenu selects the workflow area within it, and the
 * workspace holds the actual task. This two-level model is what makes the
 * application feel like one continuous R&D environment rather than a
 * collection of screens (Navigation narrative §73).
 *
 * Every destination comes from lib/navigation.ts. No path strings here.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import {
  isAvailable,
  visibleNavigation,
  type NavItem,
} from "@/lib/navigation";

interface SidebarProps {
  /** Permissions of the authenticated user, from the verified principal. */
  permissions: ReadonlySet<string>;
  /** Actionable counts, keyed by badge id. Never total row counts. */
  counts?: Readonly<Record<string, number>>;
}

export function Sidebar({ permissions, counts = {} }: SidebarProps) {
  // 220–260px expanded, 64–72px collapsed, per the source. Formulation
  // tables, DOE matrices and analytics need the width back.
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
  const groups = visibleNavigation(permissions);

  return (
    <nav
      aria-label="Main navigation"
      data-collapsed={collapsed}
      className={[
        "flex h-screen flex-col border-r border-slate-200 bg-white",
        "transition-[width] duration-150 ease-out",
        collapsed ? "w-[68px]" : "w-[244px]",
      ].join(" ")}
    >
      <div className="flex h-14 items-center gap-2 border-b border-slate-200 px-3">
        <span
          aria-hidden
          className="grid h-8 w-8 shrink-0 place-items-center rounded bg-slate-900 text-xs font-bold text-white"
        >
          EV
        </span>
        {!collapsed && (
          <span className="truncate text-sm font-semibold text-slate-900">
            EvercoatITWRD
          </span>
        )}
      </div>

      {/* 🔴 THE TWO PUBLIC SURFACES, BESIDE THE APP NAME.
          A signed-in user could not reach the marketplace or the news feed at
          all: both are public routes with no entry point anywhere inside the
          application, so the only way in was to type the URL. A page with no
          caller is the same defect as a route with no caller, arriving from
          the user's side of the screen.

          They sit here rather than in a navigation GROUP because they are not
          modules of the R&D application — they are the public surface the same
          product serves, and grouping them under "Work" or "Resources" would
          say otherwise.

          ⚠️ These carry no `permission`. Both routes are public: gating them on
          a grant would hide from a signed-in chemist what an anonymous visitor
          can already see. */}
      {!collapsed && (
        <div className="flex gap-1 border-b border-slate-200 px-3 py-2">
          <Link
            href="/marketplace"
            className="rounded border border-slate-300 px-2 py-1 text-[11px] font-semibold text-slate-700 hover:bg-slate-50"
          >
            Marketplace
          </Link>
          <Link
            href="/industry-news"
            className="rounded border border-slate-300 px-2 py-1 text-[11px] font-semibold text-slate-700 hover:bg-slate-50"
          >
            Industry News
          </Link>
        </div>
      )}

      <div className="flex-1 overflow-y-auto py-2">
        {groups.map((group) => (
          <div key={group.id} className="mb-1">
            {/* The heading is decorative when collapsed, but the group is
                still a real landmark for screen readers, so it stays in
                the accessibility tree either way. */}
            {/* slate-500, not slate-400. At 11px this is normal text, so
                WCAG 2.1 AA wants 4.5:1 and slate-400 on white gives about
                2.9:1. Found by the first axe-core run in this project;
                the group headings had failed since Slice 1. Hierarchy is
                still carried by size, weight, caps and tracking rather
                than by making the text too faint to read. */}
            <h2
              className={[
                "px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500",
                collapsed ? "sr-only" : "",
              ].join(" ")}
            >
              {group.label}
            </h2>
            <ul role="list">
              {group.items.map((item) => (
                <SidebarLink
                  key={item.id}
                  item={item}
                  collapsed={collapsed}
                  active={
                    pathname === item.href || pathname.startsWith(`${item.href}/`)
                  }
                  count={item.badge ? counts[item.badge] : undefined}
                />
              ))}
            </ul>
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        aria-expanded={!collapsed}
        className="border-t border-slate-200 px-3 py-2.5 text-left text-xs text-slate-500 hover:bg-slate-50 hover:text-slate-900"
      >
        {collapsed ? "»" : "« Collapse"}
      </button>
    </nav>
  );
}

function SidebarLink({
  item,
  collapsed,
  active,
  count,
}: {
  item: NavItem;
  collapsed: boolean;
  active: boolean;
  count?: number;
}) {
  const available = isAvailable(item);

  const body = (
    <>
      <span className={collapsed ? "sr-only" : "truncate"}>{item.label}</span>
      {collapsed && (
        <span aria-hidden className="text-xs font-semibold">
          {item.label.slice(0, 2)}
        </span>
      )}
      {/* 🔴 THE STATE IS CARRIED BY A WORD, NOT BY A COLOUR.
          Two thirds of this sidebar is not built yet, and the only thing
          that used to distinguish those items was how faint they were.
          Colour alone is not an indicator — the same rule `StatusBadge`
          enforces for the traffic light applies to navigation. Hidden
          when collapsed only because there is no room; the `sr-only`
          sentence below still says it in both states. */}
      {!available && !collapsed && (
        <span
          aria-hidden
          className="ml-auto shrink-0 rounded border border-slate-300 px-1 py-px text-[10px] font-medium uppercase tracking-wide text-slate-500"
        >
          Planned
        </span>
      )}
      {/* Only render a badge for a positive count. A grey "0" is visual
          noise that trains people to ignore the badge entirely. */}
      {available && count !== undefined && count > 0 && (
        <span
          className="ml-auto rounded-full bg-slate-900 px-1.5 py-0.5 text-[10px] font-semibold text-white"
          aria-label={`${count} items needing attention`}
        >
          {count > 99 ? "99+" : count}
        </span>
      )}
    </>
  );

  const shared = [
    "flex items-center gap-2 px-3 py-1.5 text-sm",
    collapsed ? "justify-center" : "",
  ].join(" ");

  if (!available) {
    // Not yet built. Rendered inert rather than linking into a 404 —
    // a dead link in the shell reads as a broken product, not as an
    // unfinished slice.
    //
    // 🔴 `text-slate-300` WAS 1.48:1 AGAINST WHITE, AND AXE COULD NOT SEE IT.
    //
    // WCAG 2.1 AA wants 4.5:1 for normal text. Measured: slate-300 is
    // **1.48:1**, slate-400 is 2.56:1, and slate-500 — used by the group
    // headings a few lines above for exactly this reason — is 4.76:1.
    // SEVENTEEN of this sidebar's twenty-six items are in this state, so
    // two thirds of the primary navigation was illegible.
    //
    // The accessibility suite was green over all of it. axe-core's
    // `color-contrast` rule SKIPS anything it considers disabled, and
    // `isDisabled()` (axe.js:25440) returns true for any element — or
    // ancestor — carrying `aria-disabled="true"`. So the attribute that
    // correctly describes the state also silenced the check that would
    // have caught the colour. **A check that cannot fail**, which is this
    // platform's signature defect, wearing an accessibility hat.
    //
    // `aria-disabled` stays, because it is the truth. The colour is
    // fixed, the distinction moves to the "Planned" chip, and
    // `tests/e2e/shell/accessibility.spec.ts` now measures this contrast
    // ratio directly instead of trusting a rule that opts out.
    return (
      <li>
        <span
          className={`${shared} cursor-not-allowed text-slate-500`}
          // Plain language, not "slice 15". The slice number is a build
          // schedule; nobody using this application knows what it means.
          title={`${item.label} — planned, not yet available`}
          aria-disabled="true"
        >
          {body}
          <span className="sr-only"> — planned, not yet available</span>
        </span>
      </li>
    );
  }

  return (
    <li>
      <Link
        href={item.href}
        aria-current={active ? "page" : undefined}
        // The collapsed rail shows two letters and nothing else, so
        // "Materials" and "My Work" both read as "Ma"/"My" with no way to
        // tell them apart. The accessible name was already correct via
        // the sr-only label; this gives sighted users the same fact.
        title={collapsed ? item.label : undefined}
        className={[
          shared,
          "border-l-2 transition-colors",
          active
            ? "border-slate-900 bg-slate-50 font-medium text-slate-900"
            : "border-transparent text-slate-600 hover:bg-slate-50 hover:text-slate-900",
        ].join(" ")}
      >
        {body}
      </Link>
    </li>
  );
}
