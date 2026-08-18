/**
 * Root layout — the persistent application shell.
 *
 * Structure is fixed by the Navigation narrative §1: a global top bar
 * across the width, a persistent left sidebar, and the active workspace.
 * The user must never lose access to the principal modules while working
 * inside a project or technical record.
 *
 * The contextual top submenu is NOT here — it belongs to whichever entity
 * is open (project, formula, batch, test, failure, pilot, product), so it
 * is rendered by that entity's own layout. Putting it here would force
 * every route to know about every other route's submenu.
 */

import type { Metadata } from "next";

import { Sidebar } from "@/components/nav/sidebar";
import { TopBar } from "@/components/nav/top-bar";
import { DEMO_VIEWER, tasksAssignedTo } from "@/lib/demo/dataset";
import { ALL_NAV_PERMISSIONS } from "@/lib/navigation";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "EvercoatITWRD APP",
    template: "%s · EvercoatITWRD APP",
  },
  description:
    "Integrated R&D, Smart Formulation, Laboratory Testing, Product Modeling " +
    "and Product Development Intelligence Platform",
  // Proprietary formulation data. Never indexable, even if a deployment
  // is accidentally exposed.
  robots: { index: false, follow: false },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  // THE DEMONSTRATION PRINCIPAL.
  //
  // Slice 1 passed an EMPTY set, deliberately, so that a shell showing
  // everything could not be mistaken for a working RBAC filter. That was
  // right while nothing was built — and wrong the moment Slice 2 shipped
  // pages: with no permissions, `visibleNavigation` filtered Projects,
  // Innovation and R&D Pipeline out of the sidebar entirely, so the pages
  // existed and were unreachable. Found by looking at the rendered page,
  // not by any test.
  //
  // This is a PRESENTATION set and nothing more. CLAUDE.md §6 and
  // SECURITY.md §3 both state that frontend permission checks are
  // cosmetic and every route is re-authorized server-side; handing the
  // sidebar the full set grants no access to anything. Destinations that
  // are not built yet still render inert via `isAvailable`, so the module
  // map is honest about what exists.
  //
  // When Keycloak is wired in, this becomes the verified principal's own
  // permissions and the RBAC filter is exercised for real.
  const permissions = ALL_NAV_PERMISSIONS;

  // Actionable counts, from the demo dataset. CLAUDE.md §11: a badge shows
  // items needing action BY THE HOLDER, never total rows. So this counts
  // the demonstration viewer's own open tasks — not TASKS.length, and not
  // the organisation's open tasks either, which is what a badge beside the
  // words "My Work" would have been claiming.
  const counts = { "my-work": tasksAssignedTo(DEMO_VIEWER).length };

  return (
    <html lang="en">
      <body className="bg-slate-50 text-slate-900 antialiased">
        <div className="flex h-screen overflow-hidden">
          <Sidebar permissions={permissions} counts={counts} />
          <div className="flex min-w-0 flex-1 flex-col">
            <TopBar />
            {/* min-w-0 above and here is what lets wide technical tables
                scroll inside the workspace instead of pushing the page
                into a horizontal scroll. */}
            <main className="min-w-0 flex-1 overflow-y-auto">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
