/**
 * Sign in, sign out, and which organization you are acting in.
 *
 * 🔴 THE ORGANIZATION SELECTOR IS NOT DECORATION.
 *
 * Every API request carries `X-Organization-Id`, and the server refuses a
 * tenant the user is not a member of. Until `GET /api/me` existed the
 * browser had no way to learn even one valid value, so this control could
 * not have been built — it rendered as a disabled placeholder reading
 * "ITW Evercoat (Demo)" for three slices.
 *
 * It offers ONLY organizations the API itself returned. A free-text
 * tenant id would be refused server-side anyway, but presenting one as a
 * choice would imply it was one.
 */

"use client";

import { useAuth } from "@/components/providers/auth-provider";

export function AccountMenu() {
  const { session, configured, signIn, signOut, organizations, selectOrganization } = useAuth();

  // No identity provider in this build. Say why, rather than showing a
  // button that does nothing — a dead control is indistinguishable from
  // a broken one, and this deployment genuinely has no Keycloak.
  if (!configured) {
    return (
      <span
        className="rounded border border-slate-200 px-2.5 py-1.5 text-xs text-slate-500"
        title="No identity provider is configured for this build"
      >
        Not signed in
      </span>
    );
  }

  if (session.status !== "authenticated") {
    return (
      <div className="flex items-center gap-2">
        {/* The reason is shown, not swallowed. "You are signed in but
            belong to no organization" and "your session expired" are
            different problems with different answers, and a generic
            "signed out" hides both. */}
        <span className="hidden max-w-xs truncate text-xs text-slate-500 sm:inline" title={session.reason}>
          {session.reason}
        </span>
        <button
          type="button"
          onClick={() => void signIn()}
          className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700"
        >
          Sign in
        </button>
      </div>
    );
  }

  const active = session.credentials.organizationId;

  return (
    <div className="flex items-center gap-2">
      <label htmlFor="organization" className="sr-only">
        Active organization
      </label>
      <select
        id="organization"
        value={active}
        onChange={(event) => selectOrganization(event.target.value)}
        className="rounded border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-800"
      >
        {organizations.map((org) => (
          <option key={org.organizationId} value={org.organizationId}>
            {org.name}
          </option>
        ))}
      </select>

      <button
        type="button"
        onClick={signOut}
        className="rounded border border-slate-300 px-2.5 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
      >
        Sign out
      </button>
    </div>
  );
}
