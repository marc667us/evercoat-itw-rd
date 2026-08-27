"use client";

/**
 * Profile — who you are here, and what that lets you do.
 *
 * 🔴 EVERY FIGURE COMES FROM `/api/me`, AND NOTHING IS INVENTED.
 *
 * There is no profile-editing endpoint and this page does not pretend there is:
 * `display_name` and `email` are the ORGANIZATION's view of the person
 * (migration 052 moved both onto the membership), and identity itself belongs to
 * Keycloak. A form here would either write nowhere or write to a table that is
 * not the system of record.
 *
 * 🔴 THE PERMISSION LIST IS THE POINT OF THE PAGE. §6 authorizes on permissions
 * and never on role names, and until I79 the browser did not know its own — so
 * "why can I not do this?" had no answer anywhere in the product. It has one
 * here, and it is the same list the sidebar and every control are filtered by,
 * read from the same place. Not a second copy that agrees on the day it was
 * written.
 */

import { EntityHeader } from "@/components/ui/entity-header";
import { useAuth } from "@/components/providers/auth-provider";
import { Absent } from "@/components/ui/record-link";

const TAG =
  "rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase " +
  "tracking-wide text-slate-600";

function words(value: string): string {
  return value.replace(/_/g, " ");
}

export default function ProfilePage() {
  const { profile, organizations, session } = useAuth();

  const active =
    session.status === "authenticated"
      ? organizations.find(
          (org) => org.organizationId === session.credentials.organizationId,
        )
      : undefined;

  return (
    <div>
      <EntityHeader
        eyebrow="Your account"
        title="Profile"
        crumbs={[{ label: "Dashboard", href: "/dashboard" }]}
      />

      <div className="space-y-8 p-6">
        {profile === null ? (
          <p className="text-sm text-slate-600">
            You are not signed in, so there is no profile to show. Use{" "}
            <strong>Sign in</strong> at the top left.
          </p>
        ) : (
          <>
            <section className="max-w-3xl">
              <h2 className="text-sm font-semibold text-slate-900">You</h2>
              <dl className="mt-2 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
                    Name
                  </dt>
                  <dd className="text-slate-900">{profile.displayName}</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
                    Email
                  </dt>
                  <dd className="text-slate-900">{profile.email}</dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
                    User id
                  </dt>
                  <dd className="font-mono text-xs text-slate-700">{profile.userId}</dd>
                </div>
              </dl>
              {/* ⚠️ SAY WHY THERE IS NO EDIT CONTROL. An absent button with no
                  explanation reads as an unfinished screen; this is a design
                  decision about who owns identity. */}
              <p className="mt-3 text-xs text-slate-600">
                Your name and address are held by this organization, and your
                credentials by Keycloak. Neither is editable here — this
                application deliberately cannot create or change credentials.
              </p>
            </section>

            <section className="max-w-3xl">
              <h2 className="text-sm font-semibold text-slate-900">
                Where you are working
              </h2>
              {active === undefined ? (
                <p className="mt-1 text-sm text-slate-600">
                  <Absent what="no active organization" />
                </p>
              ) : (
                <>
                  <p className="mt-1 text-sm text-slate-900">
                    {active.name}{" "}
                    <span className="text-xs text-slate-600">({active.code})</span>
                  </p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {active.roles.length === 0 ? (
                      <span className={TAG}>no roles — you hold no permissions here</span>
                    ) : (
                      active.roles.map((role) => (
                        <span key={role} className={TAG}>
                          {words(role)}
                        </span>
                      ))
                    )}
                  </div>
                </>
              )}
              {organizations.length > 1 && (
                <p className="mt-2 text-xs text-slate-600">
                  You belong to {organizations.length} organizations. Switch with
                  the selector at the top left — it navigates rather than
                  swapping in place, so no figure from the previous tenant stays
                  on screen.
                </p>
              )}
            </section>

            <section className="max-w-3xl">
              <h2 className="text-sm font-semibold text-slate-900">
                What you may do here
              </h2>
              <p className="mt-1 text-sm text-slate-600">
                {active === undefined
                  ? "Nothing, until an organization is active."
                  : `${active.permissions.length} permissions, in this organization only. ` +
                    "Membership is per-tenant, so this list changes when you switch."}
              </p>
              {active !== undefined && active.permissions.length > 0 && (
                <ul className="mt-2 flex flex-wrap gap-1.5">
                  {[...active.permissions].sort().map((permission) => (
                    <li key={permission}>
                      <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-800">
                        {permission}
                      </code>
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-3 text-xs text-slate-600">
                This is the same list the menu and every control are filtered by.
                A control you cannot see is one of these codes you do not hold —
                and every route re-checks it on the server regardless.
              </p>
            </section>
          </>
        )}
      </div>
    </div>
  );
}
