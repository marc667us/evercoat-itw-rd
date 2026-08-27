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

import { MsdPanel } from "@/components/msd/msd-panel";

import { AccountMenu } from "@/components/nav/account-menu";
import { UserMenu } from "@/components/nav/user-menu";
import { ApiStatus } from "@/components/nav/api-status";

export function TopBar() {
  const [query, setQuery] = useState("");
  // 🔴 MSD IS REAL NOW, AND THIS CONTROL WAS A DISABLED PLACEHOLDER FOR
  // FOUR SLICES. Concept Note §33 asks for a "persistent but unobtrusive
  // chatbot control"; a control that has never done anything is not
  // unobtrusive, it is a promise the product does not keep.
  const [msdOpen, setMsdOpen] = useState(false);

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
        <TopBarButton
          label="Quick Create"
          hint="New project, formula, batch, failure"
        />
        {/* MSD — Material Science & Development Assistant. Persistent but
            unobtrusive, per Concept Note §33. */}
        <button
          type="button"
          onClick={() => setMsdOpen((open) => !open)}
          aria-expanded={msdOpen}
          aria-controls="msd-panel"
          title="Material Science & Development Assistant"
          className="rounded px-2.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 hover:text-slate-900"
        >
          MSD
        </button>
        <TopBarButton label="Alerts" hint="Notifications" />
        {/* 🔴 THE SIGNED-IN PERSON, BETWEEN ALERTS AND HELP. `/api/me` has
            always returned `display_name`; the auth provider parsed only the
            organizations and threw it away, which is why this spot held a grey
            circle with a dash in it. Renders nothing when signed out —
            `AccountMenu` at the other end of the bar owns that message, and two
            components saying it differently is worse than one saying it. */}
        <UserMenu />
        <TopBarButton label="Help" hint="Help" />
      </div>

      {/* Beside the shell, not over it: a chemist asks MSD ABOUT WHAT
          THEY ARE LOOKING AT, and a full-screen modal removes the thing
          the question is about. */}
      {msdOpen && (
        <div
          id="msd-panel"
          className="fixed bottom-0 right-0 top-14 z-40 w-full max-w-md shadow-lg"
        >
          <MsdPanel onClose={() => setMsdOpen(false)} />
        </div>
      )}
    </header>
  );
}

function TopBarButton({ label, hint }: { label: string; hint: string }) {
  return (
    <button
      type="button"
      disabled
      title={hint}
      // slate-500, not slate-400 — the same correction the sidebar's
      // inert items needed, for the same reason. slate-400 is 2.56:1 on
      // white; slate-500 is 4.76:1.
      //
      // WCAG 1.4.3 does formally exempt an inactive user-interface
      // component, and axe-core skips `<button disabled>` outright, so
      // nothing was going to flag this. It is fixed anyway: "Quick
      // Create", "MSD", "Alerts" and "Help" are four of the seven
      // controls in the global chrome, and a top bar whose labels cannot
      // be read does not look unbuilt, it looks broken. The disabled
      // STATE is still carried by the `disabled` attribute — announced by
      // assistive technology, and visible as the absence of hover and the
      // not-allowed cursor — rather than by how faint the text is.
      className="rounded px-2.5 py-1.5 text-sm text-slate-500 hover:bg-slate-50 disabled:cursor-not-allowed"
    >
      {label}
    </button>
  );
}
