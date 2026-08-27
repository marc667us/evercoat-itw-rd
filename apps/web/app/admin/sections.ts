/**
 * Administration's sections — the one definition, so a test can read it.
 *
 * 🔴 RAISED BY CODEX AGAINST THE FIRST PASS OF THE SUBMENU GATE, AND IT WAS
 * RIGHT.
 *
 * `context-submenu.test.ts` originally built its own `ADMIN_SECTIONS` fixture
 * that resembled the real list and omitted four of its entries. That proves the
 * generic filter and nothing about THIS menu: a wrong permission code, or a
 * missing one, in the production array left every test green. It is this
 * repository's most repeated defect — *two literals in two files cannot be
 * type-checked into agreement* — committed inside the change that was closing
 * an instance of it.
 *
 * So the array lives here, `page.tsx` renders it and the test imports it. There
 * is one list. A section added without a permission, or with a code no route
 * checks, now fails a test rather than a client demonstration.
 */

import type { SubmenuItem } from "@/components/ui/context-submenu";

/**
 * Each section gated on the permission its own endpoint requires.
 *
 * 🔴 `admin.users` IS WHAT PUTS ADMINISTRATION IN THE SIDEBAR. It is NOT what
 * the sections behind it require: Roles and Permissions are served by
 * `GET /api/admin/roles` and `GET /api/admin/permissions`, both of which demand
 * `admin.roles`, and Stage Gates demands `admin.stage_gates`. So a caller
 * holding `admin.users` alone was offered eight sections of which one answered
 * — the shape §6 calls cosmetic and a reader calls broken.
 *
 * ⚠️ FOUR OF THESE NAME A PERMISSION NO ROUTE CHECKS YET. `admin.organization`,
 * `admin.workflow`, `admin.notifications` and `admin.audit` are seeded and held
 * (the administrator role holds all four, measured 2026-08-27) and no endpoint
 * reads them, because those sections are `not-started`. That is deliberate and
 * written down rather than hidden: naming the permission the section WILL
 * require keeps the menu honest today and makes the endpoint's gate a one-line
 * agreement rather than a decision to re-make later. It is the "permission with
 * no enforcement point" shape, held open on purpose with the reason stated —
 * not an oversight.
 */
export const ADMIN_SECTIONS: readonly SubmenuItem[] = [
  { label: "Users & Members", href: "/admin", state: "active", permission: "admin.users" },
  // GET /api/admin/roles and GET /api/admin/permissions both require
  // `admin.roles` — not `admin.users`, which is what reaches this page.
  { label: "Roles", href: "/admin/roles", state: "active", unavailable: true, permission: "admin.roles" },
  { label: "Permissions", href: "/admin/permissions", state: "active", unavailable: true, permission: "admin.roles" },
  { label: "Organization", href: "/admin/organization", state: "active", unavailable: true, permission: "admin.organization" },
  // Ship with the slice that first depends on them (ADR-021). Shown as
  // not-started rather than hidden, so the shape of Administration is
  // visible and nobody re-invents a section that is already scheduled.
  // ✅ BUILT 2026-08-27. Both were `not-started` and `unavailable`, which was
  // honest and had been true for four slices past the point §H schedules them.
  { label: "Stage Gates", href: "/admin/stage-gates", state: "active", permission: "admin.stage_gates" },
  { label: "Reference Data", href: "/admin/reference-data", state: "active", permission: "admin.reference_data" },
  // Test methods live under `/api/testing`, not under `/api/admin`, so this is
  // a different section from Reference Data despite sharing its permission.
  // Left not-started rather than folded in, because folding it in would claim
  // the endpoint is wired when it is not.
  { label: "Test Methods", href: "/admin/test-methods", state: "not-started", unavailable: true, permission: "admin.reference_data" },
  { label: "Approval Templates", href: "/admin/approval-templates", state: "not-started", unavailable: true, permission: "admin.workflow" },
  { label: "Notifications", href: "/admin/notifications", state: "not-started", unavailable: true, permission: "admin.notifications" },
  { label: "Audit", href: "/admin/audit", state: "not-started", unavailable: true, permission: "admin.audit" },
];
