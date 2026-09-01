import type { Metadata } from "next";

import { ADMIN_SECTIONS } from "@/app/admin/sections";
import { ContextSubmenu } from "@/components/ui/context-submenu";
import { EntityHeader } from "@/components/ui/entity-header";

import { AccessRequestsAdministration } from "./access-requests";
import { MembersAdministration } from "./members";

export const metadata: Metadata = { title: "Administration" };

/**
 * Administration — section 1.
 *
 * This screen exists in Slice 1 on purpose. ADR-021 was written because
 * both earlier plan versions described configuration as "editable in
 * Administration" while no slice ever built the screen — the operator's
 * own most-repeated lesson turned on itself: *ask of every role, which
 * production path **writes** it?*
 *
 * The seven endpoints behind these tabs are live (`/api/admin/*`). The
 * tables below are wired in Slice 2 once authentication supplies a
 * principal; until then this renders the structure and says so, rather
 * than showing invented rows. A screen full of plausible fake members is
 * indistinguishable from a working one at a glance, which is precisely
 * how a feature ships having never worked.
 */

export default function AdministrationPage() {
  return (
    <div>
      <EntityHeader
        eyebrow="Governance"
        title="Administration"
        crumbs={[{ label: "Dashboard", href: "/dashboard" }]}
        fields={[
          { label: "Organization", value: "ITW Evercoat (Demo)" },
          { label: "Section", value: "1 of 7" },
        ]}
      />
      <ContextSubmenu items={ADMIN_SECTIONS} activeHref="/admin" />

      <div className="p-6">
        {/* ✅ CONNECTED 2026-08-27. This block read: "Not yet connected. The API
            is live at /api/admin/members; this table is wired in Slice 2, once
            authentication supplies a verified principal. No placeholder rows are
            shown, because invented data is indistinguishable from real data at a
            glance."

            🔴 THE HONESTY WAS RIGHT AND THE WAIT WAS TOO LONG. Authentication
            arrived on 2026-08-19 and the table did not — so a sentence written
            to avoid faking a screen became a sentence describing a gap nobody
            was scheduled to close, which is the exact failure §H wrote this page
            to record. Four member write endpoints, zero controls, for four
            slices after their precondition was met. */}
        <MembersAdministration />

        {/* 🔴 ADDED 2026-09-01, CLOSING L1. `public_intel.access_requests` had
            had a writer since migration 059 and no reader anywhere — so the
            landing page told every visitor "your request has been queued for
            review" and no screen in the product could open the queue. Same
            defect as a route with no caller, seen from the other side. */}
        <AccessRequestsAdministration />

        <section className="mt-8 max-w-3xl">
          <h3 className="text-sm font-semibold text-slate-900">
            Two guards worth knowing about
          </h3>
          <ul className="mt-2 space-y-2 text-sm leading-relaxed text-slate-600">
            <li>
              <strong className="font-medium text-slate-900">
                The last administrator cannot be demoted.
              </strong>{" "}
              Revoking the final role that holds{" "}
              <code className="rounded bg-slate-100 px-1 text-xs">admin.roles</code>{" "}
              is refused. An organization that can no longer grant any role
              needs direct database access to recover — the same dead end as a
              role with no write path.
            </li>
            <li>
              <strong className="font-medium text-slate-900">
                Members are deactivated, never deleted.
              </strong>{" "}
              Removing the row would orphan every audit event and approval that
              names it. R&amp;D history is retired by status, not destroyed.
            </li>
          </ul>
        </section>
      </div>
    </div>
  );
}
