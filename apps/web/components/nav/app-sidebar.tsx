"use client";

/**
 * The sidebar, with its badge counts computed from the same source as the
 * screen behind them.
 *
 * 🔴 THE BADGE AND THE PAGE MUST NOT DISAGREE.
 *
 * The count was previously computed in `app/layout.tsx` — a SERVER
 * component — from the bundled demonstration fixture. That was correct
 * while My Work was a demonstration screen too. The moment My Work
 * started issuing a real request, the badge became a build-time constant
 * sitting beside a live list: a signed-in chemist with four real tasks
 * would have seen whatever number the fixture happened to contain.
 *
 * A badge that disagrees with the page it points at is worse than no
 * badge, because a reader trusts the smaller number to be a summary of
 * the larger one. This project has already recorded the same shape twice:
 * two literals encoding one rule, and a sidebar count that meant
 * something different from the queue it labelled.
 *
 * So the count comes from `useMyWork` — the same hook, the same query
 * key, the same cache entry the page reads. They cannot drift, because
 * there is only one of them.
 *
 * `CLAUDE.md` §11: a badge counts items needing action BY THE HOLDER,
 * never total rows. `/api/my-work` already filters to actionable statuses,
 * and the demonstration path counts only the viewer's own open tasks.
 */

import { Sidebar } from "@/components/nav/sidebar";
import {
  useAuth,
  type OrganizationChoice,
} from "@/components/providers/auth-provider";
import { useMyWork } from "@/lib/api/hooks";
import { useSession, type SessionState } from "@/lib/api/session";
import { DEMO_VIEWER, tasksAssignedTo } from "@/lib/demo/dataset";

/**
 * Which permission set the sidebar should filter by (I79).
 *
 * A pure function on purpose: the rule below has four cases and three of
 * them are wrong in a way that looks fine on screen, so it needs a test
 * that does not have to stand up two React hooks to reach it.
 *
 * @param session       who the browser currently is.
 * @param organizations every tenant `/api/me` offered, each with its own
 *                      permissions -- membership is per-tenant.
 * @param fallback      what `app/layout.tsx` passes: the whole module map.
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
  // no roles yet holds no permissions, and the sidebar must say so. This is
  // the case the old code got wrong for every caller: it showed the entire
  // module map to a laboratory technician, who then found the limits by
  // pressing a control and receiving a 403.
  return new Set(active.permissions);
}

export function AppSidebar({ permissions }: { permissions: ReadonlySet<string> }) {
  // 🔴 THE SIGNED-IN CALLER'S OWN PERMISSIONS, WHEN THERE IS ONE (I79).
  //
  // `permissions` arrives from `app/layout.tsx`, a SERVER component, which
  // cannot know who is signed in -- `/api/me` is an authenticated call the
  // browser makes. So the prop is `ALL_NAV_PERMISSIONS`, and until now every
  // role saw the entire module map and discovered its limits by pressing a
  // control and receiving a 403.
  //
  // The prop is still exactly right for the case it was written for: a
  // static export with no identity provider, or a reader who has not signed
  // in. `layout.tsx` records what happens if that case gets an EMPTY set
  // instead -- Projects, Innovation and Pipeline vanish from the sidebar and
  // the pages exist but are unreachable. So the fallback stays, and the live
  // set replaces it ONLY when a session actually says who the caller is.
  //
  // Per-organization, not per-user: membership is per-tenant, so the
  // permissions come from the ACTIVE organization rather than the first one
  // in the list. Selecting the first was a real defect in this provider
  // once, and it moved a chemist's writes into the wrong tenant.
  //
  // This is cosmetic and stays cosmetic (§6). It hides controls the caller
  // cannot use; every route re-authorizes server-side regardless.
  const session = useSession();
  const { organizations } = useAuth();
  const effectivePermissions = effectiveNavPermissions(
    session,
    organizations,
    permissions,
  );

  // The demonstration fallback is the viewer's OWN open tasks, which is
  // what `tasksAssignedTo` returns — not `TASKS.length`, and not the
  // organisation's open tasks either, which is what a badge beside the
  // words "My Work" would otherwise have been claiming.
  const { data, error } = useMyWork(tasksAssignedTo(DEMO_VIEWER).length, (live) => live.length);

  // `data` is undefined while a live request is in flight or after it
  // failed. No badge is shown then, deliberately: a zero would be a claim
  // that there is nothing to do, and that is the one wrong answer.
  // 🔴 `error` IS CHECKED, NOT JUST `data`.
  //
  // React Query KEEPS the last successful `data` when a background
  // refetch fails. The page prioritises `error` and shows no rows, so
  // without this the sidebar went on advertising a count for a list that
  // was displaying an error — the badge and the page disagreeing, which
  // is the exact defect this component was created to end. Codex found
  // it.
  const usable = error === null && data !== undefined;
  return (
    <Sidebar
      permissions={effectivePermissions}
      counts={usable ? { "my-work": data } : {}}
    />
  );
}
