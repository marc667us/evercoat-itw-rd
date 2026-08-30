"use client";

/**
 * The application chrome — and the routes that must NOT have it.
 *
 * 🔴 THE PUBLIC LANDING PAGE WAS RENDERING INSIDE THE SIGNED-IN SHELL.
 *
 * The root layout wrapped every route in the sidebar, the top bar and a
 * scrolling `<main>`. When `/` became the public landing page it inherited all
 * of it, so an anonymous visitor was served the internal navigation —
 * Dashboard, My Work, Messages, Notifications, the whole module map — beside a
 * marketplace they had not signed in to see. It also nested a second `<main>`
 * inside the shell's one.
 *
 * Nothing caught it until a browser looked: typecheck passed, ESLint passed,
 * 262 unit tests passed, `next build` produced 43 static pages, and
 * `navigation.spec.ts` passed because the headings it asserts were present —
 * inside the wrong chrome. **axe-core found it**, through the duplicate
 * landmark, which is the second time an accessibility sweep has been the thing
 * that noticed a structural defect in this project.
 *
 * ⚠️ WHY A PATHNAME CHECK RATHER THAN A `(public)` ROUTE GROUP.
 *
 * The idiomatic Next.js answer is to move the shell into an `(app)/` route
 * group layout and leave `(public)/` bare. That is the better structure and it
 * is not what this does, deliberately: it would move every existing page in
 * the application into a new directory, which is a large diff touching
 * everything, for a change whose whole purpose is to add three routes.
 *
 * The cost of the cheaper fix is that this list has to stay correct. That is
 * why it is asserted rather than trusted — `app-chrome.test.ts` checks that
 * every path here is a real public route and that no authenticated route
 * matches, so a page moved or renamed fails a test instead of quietly
 * regaining or losing the sidebar.
 */

import { usePathname } from "next/navigation";

import { AppSidebar } from "@/components/nav/app-sidebar";
import { TopBar } from "@/components/nav/top-bar";

/**
 * Routes served to callers with no session.
 *
 * Exact matches only. A prefix test would give `/marketplace-admin` the public
 * treatment by accident, and "starts with /" would match everything.
 */
export const PUBLIC_ROUTES = ["/", "/marketplace", "/industry-news"] as const;

export function isPublicRoute(pathname: string): boolean {
  // The export build sets `trailingSlash`, so the same route arrives as
  // `/marketplace/` there and `/marketplace` under the standalone build. Both
  // are the same page, and a check that handled only one would put the sidebar
  // back on the public site in exactly one build mode — the kind of
  // mode-dependent difference this project has already been bitten by.
  const normalised =
    pathname.length > 1 && pathname.endsWith("/") ? pathname.slice(0, -1) : pathname;
  return (PUBLIC_ROUTES as readonly string[]).includes(normalised);
}

export function AppChrome({
  permissions,
  children,
}: {
  permissions: ReadonlySet<string>;
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  // The public pages bring their own header, main and footer. Rendering them
  // bare is the point: they are a different product surface, not a screen of
  // the application.
  if (isPublicRoute(pathname)) return <>{children}</>;

  return (
    <div className="flex h-screen overflow-hidden">
      <AppSidebar permissions={permissions} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        {/* min-w-0 above and here is what lets wide technical tables scroll
            inside the workspace instead of pushing the page into a horizontal
            scroll.

            tabIndex={0} because this element SCROLLS. axe-core reports
            `scrollable-region-focusable` (serious) for a scroll container a
            keyboard cannot reach, and it surfaced the first time a page
            shipped with no focusable content of its own — /suppliers is
            entirely static cards, so there was nothing to tab to and the
            region below the fold was unreachable.

            Fixed here rather than by adding a link to that one page: the next
            static page would have reintroduced it. A scroll container needs
            keyboard access as a property of scrolling, not as a side effect of
            what happens to be inside it. */}
        <main tabIndex={0} className="min-w-0 flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
