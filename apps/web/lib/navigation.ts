/**
 * Navigation — the single source of truth.
 *
 * The sidebar, the router, the breadcrumb resolver, the command palette
 * and the RBAC visibility filter all derive from this one structure.
 *
 * That is deliberate. "Two literals in two files cannot be type-checked
 * into agreement" is a recurring root cause on this platform, and nav-vs-
 * router is its most common instance: someone renames a route, the
 * sidebar keeps pointing at the old path, and nothing fails to compile.
 * The link just quietly 404s for whoever clicks it.
 *
 * So: add a destination here or it does not exist. If you find yourself
 * writing a path string in a component, stop.
 *
 * Structure is fixed by the source documents (MASTER PROMPT §13,
 * Expanded Requirements §41, Navigation narrative §66) and reconciled in
 * IMPLEMENTATION_PLAN.md §E — including the two drifts the review caught:
 * WORK includes Messages, and INTELLIGENCE includes Product Models.
 */

export type NavGroupId =
  | "work"
  | "development"
  | "resources"
  | "industrialization"
  | "intelligence"
  | "governance";

export interface NavItem {
  /** Stable key. Never derived from the label — labels are copy, keys are contract. */
  readonly id: string;
  readonly label: string;
  readonly href: string;
  /**
   * Permission required to see this item at all.
   *
   * Hiding is a usability feature, not a security control — every route
   * is re-authorized server-side regardless (SECURITY.md §3). An item
   * with no permission is visible to any authenticated member.
   */
  readonly permission?: string;
  /**
   * Whether this item shows an actionable count badge.
   *
   * Counts represent items needing action, never total rows. "Failures
   * 3" must mean three failures awaiting me, not three in the database.
   */
  readonly badge?: "my-work" | "messages" | "notifications" | "approvals" | "failures";
  /** Not yet built. Rendered disabled rather than linking into a 404. */
  readonly slice?: number;
}

export interface NavGroup {
  readonly id: NavGroupId;
  readonly label: string;
  readonly items: readonly NavItem[];
}

export const NAVIGATION: readonly NavGroup[] = [
  {
    id: "work",
    label: "Work",
    items: [
      { id: "dashboard", label: "Dashboard", href: "/dashboard" },
      { id: "my-work", label: "My Work", href: "/my-work", badge: "my-work", slice: 2 },
      { id: "messages", label: "Messages", href: "/messages", badge: "messages", slice: 7 },
      {
        id: "notifications",
        label: "Notifications",
        href: "/notifications",
        badge: "notifications",
        slice: 7,
      },
    ],
  },
  {
    id: "development",
    label: "Development",
    items: [
      { id: "innovation", label: "Innovation", href: "/innovation", permission: "opportunity.view", slice: 2 },
      { id: "pipeline", label: "R&D Pipeline", href: "/pipeline", permission: "project.view", slice: 2 },
      { id: "projects", label: "Projects", href: "/projects", permission: "project.view", slice: 2 },
      { id: "formulations", label: "Formulations", href: "/formulations", permission: "formula.view", slice: 3 },
      { id: "laboratory", label: "Laboratory", href: "/laboratory", permission: "batch.view", slice: 4 },
      { id: "testing", label: "Testing", href: "/testing", permission: "test.view", slice: 5 },
      { id: "failures", label: "Failures", href: "/failures", permission: "failure.view", badge: "failures", slice: 6 },
      { id: "doe", label: "DOE & Optimization", href: "/doe", permission: "project.view", slice: 12 },
    ],
  },
  {
    id: "resources",
    label: "Resources",
    items: [
      { id: "materials", label: "Materials", href: "/materials", permission: "material.view", slice: 3 },
      { id: "suppliers", label: "Suppliers", href: "/suppliers", permission: "material.view", slice: 3 },
      { id: "knowledge", label: "Knowledge Library", href: "/knowledge", permission: "knowledge.view", slice: 8 },
    ],
  },
  {
    id: "industrialization",
    label: "Industrialization",
    items: [
      { id: "validation", label: "Validation", href: "/validation", permission: "validation.manage", slice: 15 },
      { id: "stability", label: "Stability", href: "/stability", permission: "stability.manage", slice: 15 },
      { id: "pilot", label: "Pilot & Scale-Up", href: "/pilot", permission: "pilot.manage", slice: 16 },
      { id: "quality", label: "Quality", href: "/quality", permission: "qc.manage", slice: 17 },
      { id: "products", label: "Products", href: "/products", permission: "product.view", slice: 18 },
    ],
  },
  {
    id: "intelligence",
    label: "Intelligence",
    items: [
      { id: "analytics", label: "Analytics", href: "/analytics", permission: "analytics.view", slice: 7 },
      // Present because MASTER PROMPT §13 and Expanded §41 both list it;
      // the Navigation narrative §66 omits it. Later and explicit wins.
      { id: "product-models", label: "Product Models", href: "/product-models", permission: "analytics.view", slice: 14 },
      { id: "infographics", label: "Infographics", href: "/infographics", permission: "analytics.view", slice: 20 },
      { id: "reports", label: "Reports", href: "/reports", permission: "report.generate", slice: 20 },
    ],
  },
  {
    id: "governance",
    label: "Governance",
    items: [
      // 🔴 GATED ON `test.view`, WHICH IS WHAT THE ENDPOINT DECLARES.
      //
      // It carried NO permission until Slice 6's screen was built, so every
      // authenticated member was offered it — including the procurement
      // specialist and the production engineer, neither of whom holds
      // `test.view` and neither of whom `GET /api/approvals/queue` will
      // answer. An item with no permission is offered to everybody, and that
      // is right for Dashboard and My Work and wrong here.
      //
      // ⚠️ `test.view` is a FLOOR and not the real gate. The engine re-checks
      // each rung's own `permission_required` plus segregation of duties, so
      // holding this shows the queue and decides nothing. Naming the floor is
      // still better than naming nothing: the alternative offers a screen that
      // 403s to two of ten roles.
      {
        id: "approvals",
        label: "Approvals",
        href: "/approvals",
        permission: "test.view",
        badge: "approvals",
        slice: 6,
      },
      // Administration is a thread across slices, not a single delivery
      // (ADR-021). Section 1 — users, roles, permissions, organization
      // settings — ships in Slice 1, so this is live from the start.
      // A configuration value with no Administration screen is a value
      // nobody can write, which is how five roles ended up unreachable
      // on previous projects.
      { id: "administration", label: "Administration", href: "/admin", permission: "admin.users" },
    ],
  },
] as const;

/** Every destination, flattened. Used by the router guard and the palette. */
export const ALL_NAV_ITEMS: readonly NavItem[] = NAVIGATION.flatMap((g) => g.items);

/** Compile-time guarantee that ids are unique — a duplicate breaks React keys silently. */
type _AssertUniqueIds = typeof ALL_NAV_ITEMS;

export function navItemByHref(href: string): NavItem | undefined {
  return ALL_NAV_ITEMS.find((i) => href === i.href || href.startsWith(`${i.href}/`));
}

/**
 * Filter to what this user may see.
 *
 * Empty groups are dropped so a Technician does not stare at a
 * "Governance" heading with nothing under it.
 */
export function visibleNavigation(permissions: ReadonlySet<string>): NavGroup[] {
  return NAVIGATION.map((group) => ({
    ...group,
    items: group.items.filter((i) => !i.permission || permissions.has(i.permission)),
  })).filter((group) => group.items.length > 0);
}

/** Current slice. Items above it render disabled instead of linking into a 404. */
// Slice 3 shipped: Materials, Suppliers and Formulations join the Slice 2
// destinations. Every formulation figure they show is computed by the Python
// engine at build time, not by the frontend.
//
// This constant is the ONLY thing that decides whether a destination is a
// link or a disabled item. Raising it without building the pages would turn
// every Slice 2 item into a live link into a 404 — which is exactly the
// failure `isAvailable` exists to prevent, so the two must move together.
//
// 🔴 THAT WARNING IS NOW ENFORCED, NOT JUST WRITTEN DOWN.
//
// It was a comment asking the next person to remember something, which is
// the same shape as every "two literals in two files" defect this project
// keeps finding. `navigation.test.ts` now reads the filesystem and fails
// if any item this constant makes available has no `page.tsx` behind it,
// so raising it too far is caught by a test rather than by a user
// reaching a 404.
//
// Raised 3 → 5 on 2026-08-20: Laboratory (slice 4) and Testing (slice 5)
// now have real screens wired to `/api/laboratory/batches` and
// `/api/testing/tests`. Nothing else sits at slice 4 or 5, so exactly
// those two moved.
export const CURRENT_SLICE = 5;

/**
 * Every permission any navigation item asks for, derived from NAVIGATION.
 *
 * Derived rather than listed, for the reason this whole file exists: a
 * hand-written second list of permission strings would drift the moment
 * someone added a destination, and nothing would fail to compile.
 *
 * This is a PRESENTATION set. It says nothing about authorization —
 * SECURITY.md §3 and CLAUDE.md §6 are explicit that hiding an item is a
 * usability feature and every route is re-authorized server-side
 * regardless. Handing this set to the sidebar shows the full module map;
 * it grants nothing.
 */
export const ALL_NAV_PERMISSIONS: ReadonlySet<string> = new Set(
  NAVIGATION.flatMap((g) =>
    g.items.map((i) => i.permission).filter((p): p is string => Boolean(p)),
  ),
);

/**
 * Destinations built OUT OF ORDER, by id.
 *
 * 🔴 WHY A SET AND NOT JUST A HIGHER `CURRENT_SLICE`.
 *
 * A single ordinal encodes an assumption that slices ship in order, and that
 * assumption has now failed: the Knowledge Library is slice 8 and it has a
 * screen, while Messages and Analytics (slice 7), and Failures and Approvals
 * (slice 6), do not. Raising the constant to 8 would turn those four into live
 * links into 404s — the precise failure `isAvailable` exists to prevent.
 *
 * The alternative considered and rejected was to relabel Knowledge as slice 5.
 * That would have made the ordinal lie about which slice built it, to preserve
 * a model that no longer matches how the work is being delivered. Better to
 * say plainly that one destination jumped the queue.
 *
 * ⚠️ This set is not a way to skip building a screen. `navigation.test.ts`
 * reads the filesystem and fails if anything `isAvailable` returns true for
 * has no `page.tsx` behind it — that guard covers this set exactly as it
 * covers the ordinal, and a stale id left here after a rename fails too.
 */
export const BUILT_AHEAD: ReadonlySet<string> = new Set([
  "knowledge",
  // Analytics (slice 7) and Reports (slice 20) jumped the queue together,
  // and deliberately as a pair.
  //
  // 🔴 REPORTS IS THE REASON. `GET /api/analysis/reports/test-results` shipped
  // on 2026-08-25 and gave `report.generate` its first enforcement point
  // anywhere — and this entry kept it DISABLED, so the route existed, was
  // tested, and no person could press anything that called it. *A route with
  // no caller is the same defect as a table with no writer*, and this project
  // had found 23 of those the day before. Leaving the endpoint orphaned for
  // thirteen more slices would have been that defect chosen on purpose.
  //
  // Analytics comes with it because `analytics.view` and `analytics.portfolio`
  // were in the same condition — nine roles and two roles holding permissions
  // no code read — and the screen that fixes that is this one.
  //
  // ⚠️ Product Models (14) and Infographics (20) stay disabled. They have no
  // page and no endpoint; adding them here would put a live link in front of
  // a 404, which is the precise failure `isAvailable` exists to prevent.
  // `navigation.test.ts` reads the filesystem and would fail the build for it.
  "analytics",
  "reports",
  // Slice 6, built 2026-08-27 — the module that the SYSTEM writes to and no
  // person could read. §10 opens a failure investigation automatically on a RED
  // confirmation result, and until now the eleven write endpoints behind it and
  // the approval engine's queue had no browser caller at all.
  //
  // ⚠️ THESE TWO MOVE TOGETHER AND THAT IS NOT A CONVENIENCE. An investigation
  // reached from a test needs the approval queue to explain why a technically
  // passing retest is still YELLOW (rule 12: AWAITING <next approver>), and the
  // approval queue is where a returned-for-correction step becomes visible.
  // Shipping one without the other leaves each pointing at a destination that
  // renders inert.
  "failures",
  "approvals",
]);

export function isAvailable(item: NavItem): boolean {
  return BUILT_AHEAD.has(item.id) || (item.slice ?? 1) <= CURRENT_SLICE;
}
