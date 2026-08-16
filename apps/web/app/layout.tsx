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
  // Slice 1 renders the shell with an empty permission set so the
  // structure can be reviewed before Keycloak wiring lands. Slice 2
  // replaces this with the verified principal. It is deliberately empty
  // rather than permissive: a shell that shows everything by default
  // would make the RBAC filter look like it works when it has never
  // been exercised.
  const permissions = new Set<string>();

  return (
    <html lang="en">
      <body className="bg-slate-50 text-slate-900 antialiased">
        <div className="flex h-screen overflow-hidden">
          <Sidebar permissions={permissions} />
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
