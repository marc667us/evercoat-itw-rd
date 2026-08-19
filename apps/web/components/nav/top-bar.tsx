"use client";

/**
 * Global top bar — visible across the whole application.
 *
 * Navigation narrative §2:
 *   Organization Selector | Global Search | Quick Create | MSD |
 *   Notifications | Help | User Profile
 *
 * The organization selector matters more than it looks. A user may belong
 * to several organizations, and switching must NAVIGATE rather than
 * revalidate in place — an in-place swap leaves stale tenant data on
 * screen while the new context loads, which reads as a cross-tenant leak
 * even when the API behaved correctly.
 */

import { useState } from "react";

import { AccountMenu } from "@/components/nav/account-menu";
import { ApiStatus } from "@/components/nav/api-status";

export function TopBar() {
  const [query, setQuery] = useState("");

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-4">
      {/* Organization selector and sign-in. Slice 1 rendered a disabled
          placeholder here reading "ITW Evercoat (Demo)"; it is real now
          that GET /api/me can tell the browser which tenants it may act
          in. Switching still NAVIGATES rather than revalidating in
          place -- an in-place swap leaves stale tenant data on screen
          while the new context loads, which reads as a cross-tenant leak
          even when the API behaved correctly. */}
      <AccountMenu />

      {/* Global search covers projects, formulas, materials, suppliers,
          batches, samples, tests, failures, products and documents
          (Expanded Requirements §48). */}
      <div className="min-w-0 flex-1">
        <label htmlFor="global-search" className="sr-only">
          Search projects, formulas, materials, tests
        </label>
        <input
          id="global-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search…  (⌘K)"
          disabled
          className="w-full max-w-md rounded border border-slate-200 px-3 py-1.5 text-sm placeholder:text-slate-400 disabled:bg-slate-50"
        />
      </div>

      <div className="flex items-center gap-1.5">
        {/* Whether the API is reachable, at a glance and on every page.
            "showing old figures" and "cannot reach the database" look
            identical to a chemist, and only the second is actionable. */}
        <ApiStatus />
        <TopBarButton label="Quick Create" hint="New project, formula, batch, failure" />
        {/* MSD — Material Science & Development Assistant. Persistent but
            unobtrusive, per Concept Note §33. Arrives in Slice 7. */}
        <TopBarButton label="MSD" hint="Material Science & Development Assistant" />
        <TopBarButton label="Alerts" hint="Notifications" />
        <TopBarButton label="Help" hint="Help" />
        <div
          aria-hidden
          className="ml-1 grid h-8 w-8 place-items-center rounded-full bg-slate-200 text-xs font-semibold text-slate-600"
        >
          —
        </div>
      </div>
    </header>
  );
}

function TopBarButton({ label, hint }: { label: string; hint: string }) {
  return (
    <button
      type="button"
      disabled
      title={hint}
      className="rounded px-2.5 py-1.5 text-sm text-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed"
    >
      {label}
    </button>
  );
}
