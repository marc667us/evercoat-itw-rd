"use client";

/**
 * What the signed-in caller may actually do — one definition, one import.
 *
 * 🔴 WHY THIS FILE EXISTS RATHER THAN A SECOND COPY OF THE RULE.
 *
 * `effectiveNavPermissions` used to live inside `components/nav/app-sidebar.tsx`,
 * which made it the SIDEBAR's rule rather than the application's. Everything
 * below the sidebar — the contextual submenu, the ingest form, the workspace
 * action bars — then had nowhere to ask the question from, and the answer
 * written into three page comments was that the question could not be asked
 * at all (see the correction below). That is how a second, wrong copy of a
 * permission model gets written: not by someone deciding to duplicate it, but
 * by there being no single place to import it from.
 *
 * So the rule moved here, unchanged, with its tests. `app-sidebar.tsx` imports
 * it like everybody else.
 *
 * 🔴 AND THE COMMENTS IT REPLACES WERE ASSERTING A FACT THAT HAD EXPIRED.
 *
 * `app/knowledge/page.tsx`, `app/testing/test/page.tsx` and
 * `app/laboratory/batch/page.tsx` each carried a variation of *"`/api/me`
 * returns roles, not permissions"* as the stated reason their controls could
 * not be gated. That was true when written and stopped being true on
 * 2026-08-25, when I79 closed and migration 045 added permission codes to
 * `core.memberships_for_subject`. Measured against the deployed demo on
 * 2026-08-27, `/api/me` returns 38 permissions for `lead.demo`, 11 for
 * `tech.demo` and 5 for `exec.demo`.
 *
 * *A comment can assert a rule that does not exist* — this platform's own
 * recorded lesson, and here it had frozen three screens in a shape chosen for
 * a constraint that had been removed two days earlier.
 *
 * ⚠️ THIS STAYS COSMETIC, AND THAT IS NOT A HEDGE.
 *
 * `CLAUDE.md` §6 and `SECURITY.md` §3: hiding a control is a usability and
 * honesty feature; every route re-authorizes server-side regardless, and none
 * of these checks is load-bearing for access. Removing every one of them
 * would change what is offered and nothing about what is permitted.
 */

import {
  useAuth,
  type OrganizationChoice,
} from "@/components/providers/auth-provider";
import { useSession, type SessionState } from "@/lib/api/session";
import { ALL_NAV_PERMISSIONS } from "@/lib/navigation";

/**
 * Which permission set the shell should filter by (I79).
 *
 * A pure function on purpose: the rule below has five cases and three of
 * them are wrong in a way that looks fine on screen, so it needs a test
 * that does not have to stand up two React hooks to reach it.
 *
 * @param session       who the browser currently is.
 * @param organizations every tenant `/api/me` offered, each with its own
 *                      permissions -- membership is per-tenant.
 * @param fallback      what a build with no identity provider must fall back
 *                      to: the whole module map.
 */
export function effectiveNavPermissions(
  session: SessionState,
  organizations: readonly OrganizationChoice[],
  fallback: ReadonlySet<string>,
): ReadonlySet<string> {
  if (session.status !== "authenticated") {
    // 🔴 NOT the empty set. A static export with no identity provider, or a
    // reader who has not signed in, must still see the module map --
    // `layout.tsx` records what an empty set did: Projects, Innovation and
    // Pipeline vanished from the sidebar and the pages existed but were
    // unreachable. Nothing is disclosed by showing a menu; every route
    // re-authorizes server-side (§6).
    return fallback;
  }

  const active = organizations.find(
    (org) => org.organizationId === session.credentials.organizationId,
  );

  if (active === undefined) {
    // 🔴 FAIL CLOSED. The first version returned `fallback` here and called
    // that "we do not know, so we do not pretend to" -- which sounds careful
    // and is backwards. Codex caught it, and it directly contradicts the
    // rule written one file away in `auth-provider.tsx`: an API that cannot
    // report permissions must yield a shell that shows LESS, never one that
    // shows everything.
    //
    // Authenticated with an active tenant that `/api/me` did not return is a
    // BROKEN state -- a stale organization id, a revoked membership, a list
    // that has not loaded. Every request made in it carries an organization
    // header the API will refuse, so showing the full module map offers a
    // menu on which nothing works. Showing nothing is the honest rendering
    // of "you have no access here", and unlike the signed-out case it does
    // not strand a legitimate reader: a signed-in user whose tenant is
    // missing has no working destination to be stranded from.
    //
    // The fallback exists for ABSENCE OF A SESSION, not for a broken one.
    return new Set();
  }

  // 🔴 AN EMPTY SET HERE IS AN ANSWER, NOT AN ABSENCE. A member who holds
  // no roles yet holds no permissions, and the shell must say so. This is
  // the case the old code got wrong for every caller: it showed the entire
  // module map to a laboratory technician, who then found the limits by
  // pressing a control and receiving a 403.
  return new Set(active.permissions);
}

/**
 * The caller's own permissions, for any client component that renders a
 * control.
 *
 * 🔴 THE FALLBACK IS `ALL_NAV_PERMISSIONS`, AND THAT IS DELIBERATE HERE TOO.
 *
 * A build with no identity provider compiled in has no session and never
 * will, and this application is demonstrated in exactly that state. Handing
 * such a build an empty set does not make it safer — it makes every gated
 * control invisible, which is how a demonstration of a working product turns
 * into a demonstration of an empty one. `effectiveNavPermissions` carries the
 * reasoning; this hook simply supplies the same fallback the sidebar uses, so
 * the shell and the workspace inside it cannot disagree about who the caller
 * is.
 *
 * ⚠️ THAT MEANS `ALL_NAV_PERMISSIONS` IS A *NAVIGATION* SET BEING USED AS THE
 * ANONYMOUS FALLBACK FOR NON-NAVIGATION CONTROLS. It contains only the
 * permissions some nav item asks for -- `knowledge.ingest` and `test.confirm`
 * are not in it. So an anonymous reader is offered the modules and NOT the
 * write controls inside them, which is the right way round: the fallback
 * exists so pages are reachable, not so a reader with no identity is offered
 * every action in the product.
 */
export function usePermissions(): ReadonlySet<string> {
  const session = useSession();
  const { organizations } = useAuth();
  return effectiveNavPermissions(session, organizations, ALL_NAV_PERMISSIONS);
}

/**
 * Whether there is a signed-in caller to filter by at all.
 *
 * 🔴 RAISED BY THE SUPERVISOR, AND IT WAS A REGRESSION I INTRODUCED.
 *
 * `usePermissions` falls back to `ALL_NAV_PERMISSIONS` with no session, and
 * that set contains only the codes some NAV ITEM asks for. For a write control
 * that is the right way round — an anonymous reader is offered the modules and
 * not every action in the product. For a NAVIGATION SURFACE it is wrong, and
 * `ContextSubmenu` is one: `admin.roles`, `admin.organization`,
 * `admin.stage_gates`, `admin.reference_data`, `admin.workflow`,
 * `admin.notifications` and `admin.audit` are not in the nav set, so on a build
 * with no identity provider — the demonstration state this application is
 * shown in — Administration's submenu collapsed from nine sections to one,
 * including the five `not-started` entries that exist so nobody re-invents a
 * section already scheduled.
 *
 * Reachability is the reason the anonymous fallback exists at all
 * (`layout.tsx` records Projects, Innovation and Pipeline disappearing when the
 * sidebar was handed an empty set). A submenu is the same class of surface as
 * the sidebar and takes the same answer; a button that writes is not.
 *
 * So the two questions are separated rather than one being bent to fit the
 * other: this reports whether a caller is KNOWN, and the submenu shows
 * everything when nobody is.
 */
export function useCallerIsKnown(): boolean {
  const session = useSession();
  return session.status === "authenticated";
}

/**
 * Whether the caller holds a permission — or `true` when a control names none.
 *
 * A control with no stated permission is visible to any caller, matching
 * `visibleNavigation`'s treatment of a nav item with no `permission`. Stated
 * as one function so that "undefined means visible" is decided in one place
 * rather than re-decided at each call site, which is where the two halves of
 * a rule usually drift apart.
 */
export function permits(
  permissions: ReadonlySet<string>,
  permission: string | undefined,
): boolean {
  return permission === undefined || permissions.has(permission);
}
