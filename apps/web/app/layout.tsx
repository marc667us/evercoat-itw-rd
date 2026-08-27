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

import { AuthProvider } from "@/components/providers/auth-provider";
import { ThemeProvider } from "@/components/providers/theme-provider";
import { QueryProvider } from "@/components/providers/query-provider";
import { AppSidebar } from "@/components/nav/app-sidebar";
import { TopBar } from "@/components/nav/top-bar";
import { ALL_NAV_PERMISSIONS } from "@/lib/navigation";
import { prePaintScript } from "@/lib/theme";

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

  // 🔴 THE BADGE COUNT MOVED OUT OF THIS FILE.
  //
  // It used to be computed here, in a SERVER component, from the bundled
  // demonstration fixture. That was right while My Work was a
  // demonstration screen. Now that My Work issues a real request, a
  // build-time constant beside a live list would mean a signed-in chemist
  // with four real tasks saw whatever number the fixture contained.
  //
  // `AppSidebar` reads the count from the same hook, query key and cache
  // entry the page reads, so the two cannot drift.

  return (
    <html lang="en">
      <head>
        {/* 🔴 BEFORE THE FIRST PAINT, NOT AFTER HYDRATION.
 
            The themed variables were only ever set by `ThemeProvider`, which is
            React and therefore runs after the document has already been
            painted. A reader who had chosen dark got a full white page and then
            their theme — on a static export served from a CDN, that flash is
            the whole first impression, and it lands hardest on the people who
            chose dark because a bright screen bothers them. Both reviewers
            found it.

            `dangerouslySetInnerHTML` because there is no other way to inline a
            script in the document head from a server component. The content is
            generated from this application's own constants — no request, no
            user input, nothing interpolated from outside the build. */}
        <script dangerouslySetInnerHTML={{ __html: prePaintScript() }} />
      </head>
      <body className="bg-slate-50 text-slate-900 antialiased">
        {/* TanStack Query, for the whole tree. It wraps the shell rather
            than each page so that a query started on one screen is still
            cached when the reader navigates back to it — and so that a
            page added later is wired by existing, not by remembering. */}
        {/* AuthProvider outside QueryProvider: a query fired before
            the session is known would run anonymously and cache the
            refusal. */}
        {/* 🔴 OUTSIDE EVERYTHING, INCLUDING THE AUTH PROVIDER. The theme is a
            property of the BROWSER, not of the session: a signed-out reader
            looking at the sign-in screen has already chosen dark, and a theme
            that only applied once somebody was authenticated would flash white
            at exactly the moment they are least expecting it. */}
        <ThemeProvider>
        <AuthProvider>
        <QueryProvider>
        <div className="flex h-screen overflow-hidden">
          <AppSidebar permissions={permissions} />
          <div className="flex min-w-0 flex-1 flex-col">
            <TopBar />
            {/* min-w-0 above and here is what lets wide technical tables
                scroll inside the workspace instead of pushing the page
                into a horizontal scroll.

                tabIndex={0} because this element SCROLLS. axe-core reports
                `scrollable-region-focusable` (serious) for a scroll
                container a keyboard cannot reach, and it surfaced the first
                time a page shipped with no focusable content of its own —
                /suppliers is entirely static cards, so there was nothing to
                tab to and the region below the fold was unreachable.

                Fixed here rather than by adding a link to that one page: the
                next static page would have reintroduced it. A scroll
                container needs keyboard access as a property of scrolling,
                not as a side effect of what happens to be inside it. */}
            <main tabIndex={0} className="min-w-0 flex-1 overflow-y-auto">
              {children}
            </main>
          </div>
        </div>
        </QueryProvider>
        </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
