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

      <div className="flex-1 overflow-y-auto py-2">
        {groups.map((group) => (
          <div key={group.id} className="mb-1">
            {/* The heading is decorative when collapsed, but the group is
                still a real landmark for screen readers, so it stays in
                the accessibility tree either way. */}
            <h2
              className={[
                "px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400",
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
    return (
      <li>
        <span
          className={`${shared} cursor-not-allowed text-slate-300`}
          title={`Available in slice ${item.slice}`}
          aria-disabled="true"
        >
          {body}
        </span>
      </li>
    );
  }

  return (
    <li>
      <Link
        href={item.href}
        aria-current={active ? "page" : undefined}
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
