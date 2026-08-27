"use client";

/**
 * Permissions — the whole vocabulary, grouped by the domain that owns it.
 *
 * 🔴 THIS IS THE LIST §6 SAYS EVERYTHING IS AUTHORIZED AGAINST.
 *
 * *"Authorize on permissions, not role names."* Every gate in the product names
 * one of these codes: every route's `require_permission`, every conductor's
 * department gate, every control this browser hides. Until now the catalogue
 * existed only in a migration and an endpoint nobody called.
 *
 * ⚠️ READ-ONLY, BECAUSE A PERMISSION IS NOT DATA. It is a name that code
 * checks. Adding a row here would produce a code no `require_permission` reads
 * and no conductor gates on — a permission with no enforcement point, which
 * this project already has four of and records as a deliberate, written-down
 * exception rather than a thing to make more of.
 *
 * 🔴 GROUPED BY DOMAIN BECAUSE 88 IS TOO MANY TO READ FLAT. The server returns
 * `domain` on every row for exactly this reason, and grouping in the browser
 * from a field the server supplies is not a second definition of anything.
 */

import Link from "next/link";

import { ContextSubmenu } from "@/components/ui/context-submenu";
import { EntityHeader, headerCount } from "@/components/ui/entity-header";
import { LiveOnlyPage } from "@/components/ui/data-source-banner";
import { serverMessage } from "@/lib/api/client";
import { usePermissionCatalogue } from "@/lib/api/hooks";
import type { Permission } from "@/lib/api/admin";
import { permits, usePermissions } from "@/lib/permissions";

import { ADMIN_SECTIONS } from "../sections";

export default function PermissionsPage() {
  const held = usePermissions();
  const mayRead = permits(held, "admin.roles");
  const { data, error, isLoading, unavailable } = usePermissionCatalogue();

  const catalogue: Permission[] = data ?? [];

  // Grouped from the server's own `domain`, in the order the domains first
  // appear — which is the order the seed defines them in, and therefore roughly
  // the order of the digital thread rather than the alphabet.
  const byDomain = new Map<string, Permission[]>();
  for (const permission of catalogue) {
    byDomain.set(permission.domain, [...(byDomain.get(permission.domain) ?? []), permission]);
  }

  return (
    <div>
      <EntityHeader
        eyebrow="Governance"
        title="Permissions"
        crumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Administration", href: "/admin" },
        ]}
        fields={[
          {
            label: "Permissions",
            value: headerCount(
              catalogue,
              mayRead && !isLoading && error === null && unavailable === null,
            ),
          },
          { label: "Domains", value: String(byDomain.size) },
        ]}
      />
      <ContextSubmenu items={ADMIN_SECTIONS} activeHref="/admin/permissions" />

      <div className="p-6">
        <LiveOnlyPage
          title="The permission catalogue"
          lede="Every gate in this product names one of these codes — each route,
                each department conductor, and each control the browser hides."
          unavailable={unavailable}
          notInvented="the permission catalogue"
        >
          {unavailable !== null ? (
            <p className="text-sm text-slate-600">
              The catalogue cannot be shown until this build is pointed at an API.
            </p>
          ) : !mayRead ? (
            <p className="text-sm text-slate-600">
              Reading the permission catalogue needs{" "}
              <code className="text-xs">admin.roles</code>, which this account does
              not hold.
            </p>
          ) : error !== null ? (
            <p role="alert" className="text-sm text-red-700">
              The catalogue could not be loaded: {serverMessage(error)}
            </p>
          ) : isLoading ? (
            <p className="text-sm text-slate-600">Loading the catalogue…</p>
          ) : (
            <>
              <p
                role="note"
                className="mb-4 rounded border border-slate-300 bg-slate-50 px-4 py-2 text-xs text-slate-800"
              >
                <span aria-hidden>⊘ </span>
                A permission is <strong>a name that code checks</strong>, not a row
                somebody adds. There is no endpoint to create one, and a code no
                route reads would grant nothing. To see which are bundled into
                which role, open{" "}
                <Link href="/admin/roles" className="underline underline-offset-2">
                  Roles
                </Link>
                ; to see what you yourself hold, open{" "}
                <Link href="/account/profile" className="underline underline-offset-2">
                  your profile
                </Link>
                .
              </p>

              <div className="space-y-6">
                {[...byDomain.entries()].map(([domain, items]) => (
                  <section key={domain}>
                    <h2 className="text-sm font-semibold text-slate-900">
                      {domain}{" "}
                      <span className="text-xs font-normal text-slate-600">
                        ({items.length})
                      </span>
                    </h2>
                    <ul className="mt-2 space-y-1">
                      {items.map((permission) => (
                        <li
                          key={permission.code}
                          className="flex flex-wrap items-baseline gap-2 text-sm"
                        >
                          <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-800">
                            {permission.code}
                          </code>
                          {/* The description is what makes the code readable to
                              somebody deciding whether to grant a role that
                              carries it. `admin.workflow` means nothing on its
                              own. */}
                          <span className="text-slate-700">{permission.description}</span>
                        </li>
                      ))}
                    </ul>
                  </section>
                ))}
              </div>
            </>
          )}
        </LiveOnlyPage>
      </div>
    </div>
  );
}
