"use client";

/**
 * Roles — the ten the realm ships with, and exactly what each one may do.
 *
 * 🔴 READ-ONLY, AND THAT IS THE API's SHAPE RATHER THAN A SHORTCUT.
 *
 * `GET /api/admin/roles` exists. There is no endpoint that creates a role,
 * renames one, or changes which permissions it carries — the ten roles and
 * their grants are seeded by migration 002 and §6 fixes them by name. So this
 * screen shows what is there and does not offer a control that would post
 * nowhere.
 *
 * ⚠️ WHICH MEANS "editable in Administration" IS STILL NOT TRUE OF ROLES, and
 * saying so here is the point. §H exists because two plan versions claimed
 * role→permission mapping was editable while nothing built it; a screen that
 * displayed the mapping behind a disabled Edit button would be the third
 * version of that claim. What a person CAN do — grant one of these roles to a
 * colleague — is on `/admin`, and this page says where.
 *
 * 🔴 THE PERMISSIONS ARE LISTED IN FULL, NOT SUMMARISED. "Administrator: 17
 * permissions" tells a reader nothing they can act on. The question this screen
 * answers is *"if I grant this, what have I just allowed?"*, and a count does
 * not answer it.
 */

import Link from "next/link";

import { ContextSubmenu } from "@/components/ui/context-submenu";
import { EntityHeader, headerCount } from "@/components/ui/entity-header";
import { LiveOnlyPage } from "@/components/ui/data-source-banner";
import { serverMessage } from "@/lib/api/client";
import { useRoles } from "@/lib/api/hooks";
import type { Role } from "@/lib/api/admin";
import { permits, usePermissions } from "@/lib/permissions";

import { ADMIN_SECTIONS } from "../sections";

const TAG =
  "rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase " +
  "tracking-wide text-slate-600";

export default function RolesPage() {
  const permissions = usePermissions();
  const mayRead = permits(permissions, "admin.roles");
  const { data, error, isLoading, unavailable } = useRoles();

  const roles: Role[] = data ?? [];

  return (
    <div>
      <EntityHeader
        eyebrow="Governance"
        title="Roles"
        crumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Administration", href: "/admin" },
        ]}
        fields={[{ label: "Roles", value: headerCount(roles, mayRead && !isLoading && error === null && unavailable === null) }]}
      />
      <ContextSubmenu items={ADMIN_SECTIONS} activeHref="/admin/roles" />

      <div className="p-6">
        <LiveOnlyPage
          title="Roles and what they carry"
          lede="Authorization is on permissions, never on role names (§6). A role is
                a named bundle of them, and this is what each bundle contains."
          unavailable={unavailable}
          notInvented="roles"
        >
          {unavailable !== null ? (
            <p className="text-sm text-slate-600">
              Roles cannot be shown until this build is pointed at an API.
            </p>
          ) : !mayRead ? (
            <p className="text-sm text-slate-600">
              Reading the role catalogue needs{" "}
              <code className="text-xs">admin.roles</code>, which this account does
              not hold.
            </p>
          ) : error !== null ? (
            <p role="alert" className="text-sm text-red-700">
              The roles could not be loaded: {serverMessage(error)}
            </p>
          ) : isLoading ? (
            <p className="text-sm text-slate-600">Loading roles…</p>
          ) : (
            <>
              <p
                role="note"
                className="mb-4 rounded border border-slate-300 bg-slate-50 px-4 py-2 text-xs text-slate-800"
              >
                <span aria-hidden>⊘ </span>
                These are <strong>seeded and not editable here</strong>. There is no
                endpoint that creates a role or changes which permissions it
                carries — §6 fixes the ten by name and migration 002 grants them.
                What you can do is grant one to a colleague, on{" "}
                <Link href="/admin" className="underline underline-offset-2">
                  Users &amp; Members
                </Link>
                .
              </p>

              <ul className="space-y-3">
                {roles.map((role) => (
                  <li key={role.code} className="rounded border border-slate-200 bg-white p-4">
                    <div className="flex flex-wrap items-baseline gap-2">
                      <h2 className="text-sm font-semibold text-slate-900">{role.name}</h2>
                      <code className="text-xs text-slate-600">{role.code}</code>
                      {/* The difference between a role the product depends on
                          and one somebody here defined. Today they are all
                          seeded; the flag is shown so that stops being an
                          assumption the moment it stops being true. */}
                      {role.is_seeded && <span className={TAG}>seeded</span>}
                      <span className={TAG}>
                        {role.permissions.length} permission
                        {role.permissions.length === 1 ? "" : "s"}
                      </span>
                    </div>

                    {role.description !== null && (
                      <p className="mt-1 text-sm text-slate-700">{role.description}</p>
                    )}

                    {role.permissions.length === 0 ? (
                      // 🔴 A REAL STATE AND A LOUD ONE. A role carrying nothing
                      // grants nothing — anybody holding only it sees an empty
                      // sidebar, which is exactly what `effectiveNavPermissions`
                      // renders and exactly the report that arrives as "the app
                      // is broken for me".
                      <p className="mt-2 text-sm text-slate-700">
                        Carries no permissions — anybody holding only this role can
                        see nothing.
                      </p>
                    ) : (
                      <ul className="mt-2 flex flex-wrap gap-1.5">
                        {[...role.permissions].sort().map((permission) => (
                          <li key={permission}>
                            <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-800">
                              {permission}
                            </code>
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}
        </LiveOnlyPage>
      </div>
    </div>
  );
}
