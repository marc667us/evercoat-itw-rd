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
import { useRouter } from "next/navigation";

import { MsdPanel } from "@/components/msd/msd-panel";

import { AccountMenu } from "@/components/nav/account-menu";
import { UserMenu } from "@/components/nav/user-menu";
import { ApiStatus } from "@/components/nav/api-status";
import { permits, useCallerIsKnown, usePermissions } from "@/lib/permissions";
import { MIN_SEARCH_LENGTH } from "@/lib/api/search";

export function TopBar() {
  const [query, setQuery] = useState("");
  const router = useRouter();
  // 🔴 MSD IS REAL NOW, AND THIS CONTROL WAS A DISABLED PLACEHOLDER FOR
  // FOUR SLICES. Concept Note §33 asks for a "persistent but unobtrusive
  // chatbot control"; a control that has never done anything is not
  // unobtrusive, it is a promise the product does not keep.
  const [msdOpen, setMsdOpen] = useState(false);

  // 🔴 THE MSD CONTROL WAS OFFERED TO EVERY CALLER, AND TWO ROLES CANNOT USE
  // IT. All four `/api/msd` routes are `msd.use`; the administrator and the
  // executive viewer do not hold it, so opening the panel got them a 403 in
  // place of a conversation. The role audit reported `msd.use` as
  // held-with-no-control -- eight roles, no gate -- and this is the other half
  // of that: no gate means nobody was filtered, not that nobody could press it.
  //
  // ⚠️ `useCallerIsKnown` IS LOAD-BEARING HERE, AND OMITTING IT WOULD HAVE BEEN
  // A REGRESSION OF THE ONE THE SUPERVISOR ALREADY CAUGHT ON `ContextSubmenu`.
  // With no session `usePermissions` falls back to `ALL_NAV_PERMISSIONS`, which
  // holds only the codes a SIDEBAR ITEM asks for. MSD is a top-bar control and
  // has no nav item, so `msd.use` is not in that set -- gating on the
  // permission alone would have deleted MSD from the demonstration build, which
  // is the state this application is shown in. So: offered when there is no
  // caller to filter by, filtered the moment there is one.
  const callerIsKnown = useCallerIsKnown();
  const permissions = usePermissions();
  const mayUseMsd = !callerIsKnown || permits(permissions, "msd.use");

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
          (Expanded Requirements §48; MSD spec §29).

          🔴 THIS WAS `disabled` FOR SEVEN SLICES. A search box that cannot be
          typed into is the most-used control in the chrome promising something
          the product did not have — and §29 asks to EXTEND global search, which
          could not be done while there was no global search to extend.

          It submits rather than searching as you type. Fifteen tables are
          queried per request, and firing that on every keystroke would put a
          fan-out query behind an autocomplete; the results page owns the
          query, so a search can be linked, reloaded and gone back to. */}
      <form
        className="min-w-0 flex-1"
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          const next = query.trim();
          // 🔴 THE API REFUSES FEWER THAN TWO CHARACTERS, SO THE BOX MUST TOO.
          // SUPERVISOR. Submitting "F" fired a request that 422s and the
          // results page rendered a red "could not be run" alert -- a user
          // typing one letter and pressing Enter met an error message, not
          // guidance. The minimum is in the placeholder rather than only in
          // this check, so the rule is visible before it is hit.
          if (next.length >= MIN_SEARCH_LENGTH) {
            router.push(`/search?q=${encodeURIComponent(next)}`);
          }
        }}
      >
        <label htmlFor="global-search" className="sr-only">
          Search projects, formulas, materials, tests
        </label>
        <input
          id="global-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search records… (2 characters minimum)"
          className="w-full max-w-md rounded border border-slate-200 px-3 py-1.5 text-sm placeholder:text-slate-500"
        />
      </form>

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
            unobtrusive, per Concept Note §33. Absent, not disabled, for a
            caller without `msd.use`: a greyed control in this bar means "not
            built yet" — that is what `TopBarButton` beside it means — and
            saying that about a feature which exists and is simply not theirs
            is a different and wrong message. */}
        {mayUseMsd && (
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
        )}
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
      {msdOpen && mayUseMsd && (
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
