/**
 * The Intelligence department, over HTTP.
 *
 * 🔴 THESE TWO ENDPOINTS HAD NO BROWSER CALLER AT ALL.
 *
 * `GET /api/analysis/reports/test-results` shipped on 2026-08-25 and gave
 * `report.generate` its first enforcement point anywhere. Nothing in
 * `apps/web` called it — the Reports destination renders DISABLED, because
 * `navigation.ts` puts it at slice 20 and `CURRENT_SLICE` is 5. So the API
 * half of the Intelligence group existed, was tested, and no production path
 * reached it. **A route with no caller is the same defect as a table with no
 * writer**, and this project found 23 of those on 08-24; this was the
 * twenty-fourth, one day old.
 *
 * `GET /api/analysis/analytics` is new and arrives WITH its caller, which is
 * the point.
 *
 * ---------------------------------------------------------------------------
 * 🔴 NOTHING HERE DERIVES A STATUS, AND THE TYPES ARE SHAPED TO MAKE THAT HARD
 * ---------------------------------------------------------------------------
 *
 * §10: the traffic light is server-owned, produced by one ordered
 * first-match-wins algorithm, and *"never a field a user picks"*. The server
 * sends `by_colour` already counted. This module parses those counts; it must
 * never build them by inspecting rows, and the row schema deliberately does
 * not carry the inputs (`cv`, `margin`, `trend_alert`, replicate statistics)
 * that would let a browser try.
 *
 * The same trap `lib/api/testing.ts` documents at length, one level up.
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";

/**
 * A counted breakdown: bucket name → how many.
 *
 * `z.record` rather than an enum of the known values on purpose. The
 * dispositions are `green` / `yellow` / `red`, and `unknown` is a real bucket
 * the server emits when a test has no derived colour yet. A closed enum would
 * fail the whole response the first time a legitimate new bucket appeared —
 * turning a display gap into an outage — and this schema's job is to refuse
 * the WRONG SHAPE, not to second-guess the server's vocabulary.
 */
const counts = z.record(z.string(), z.number());

/**
 * One test, as an analytics figure that can be opened.
 *
 * §2: *"Dashboards must drill down to real source records."* `test_id` and
 * `test_number` are here so a count is traceable to the tests behind it
 * rather than being an aggregate nobody can open.
 *
 * ⚠️ `calculated_result` AND `disposition` ARE BOTH PRESENT, SEPARATELY, and
 * a screen must render both. §10: a low-margin pass awaiting approval is both
 * a pass and not final, and one field cannot say that. Rendering only the
 * colour would hide the automatic evaluation; rendering only the evaluation
 * would show a green tick for something not yet approved.
 */
export const analysisRowSchema = z
  .object({
    test_id: z.string(),
    test_number: z.string(),
    project_id: z.string().nullable(),
    method_code: z.string().nullable(),
    test_purpose: z.string().nullable(),
    authority_level: z.string().nullable(),
    calculated_result: z.string().nullable(),
    disposition: z.object({
      colour: z.string(),
      label: z.string().nullable(),
      reason: z.string().nullable(),
      next_action: z.string().nullable(),
      rule: z.number().nullable(),
    }),
  })
  .passthrough();

export type AnalysisRow = z.infer<typeof analysisRowSchema>;

// ---------------------------------------------------------------------------
// The report — GET /api/analysis/reports/test-results
// ---------------------------------------------------------------------------

/**
 * Tests grouped by their derived disposition.
 *
 * `truncated` is not decoration. The server runs one `get_test` per row to
 * read the derivation rather than copy it, so the report is bounded at 200
 * and says when it hit the cap. **A total that silently stopped at 200 is a
 * number that means something other than what it says** — the screen must
 * show this, and `reports/page.tsx` does.
 */
export const testResultsReportSchema = z
  .object({
    organization_id: z.string(),
    project_id: z.string().nullable(),
    counted: z.number(),
    truncated: z.boolean(),
    limit: z.number(),
    by_colour: counts,
    /** Which of §10's fourteen ordered rules fired, and how often. */
    by_rule: counts,
    rows: z.array(analysisRowSchema),
  })
  .passthrough();

export type TestResultsReport = z.infer<typeof testResultsReportSchema>;

export function fetchTestResultsReport(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<TestResultsReport> {
  return apiRequest(
    { path: "/api/analysis/reports/test-results", credentials, signal },
    (payload) => testResultsReportSchema.parse(payload),
  );
}

// ---------------------------------------------------------------------------
// Analytics — GET /api/analysis/analytics
// ---------------------------------------------------------------------------

/** One project's line in the organization-wide breakdown. */
export const portfolioProjectSchema = z
  .object({
    project_id: z.string(),
    project_code: z.string(),
    name: z.string(),
    current_stage: z.string().nullable(),
    status: z.string(),
    tests: z.number(),
    truncated: z.boolean(),
    limit: z.number(),
    by_colour: counts,
  })
  .passthrough();

export type PortfolioProject = z.infer<typeof portfolioProjectSchema>;

/**
 * Testing and laboratory activity, counted.
 *
 * 🔴 `by_project` IS `null` WHEN THE CALLER LACKS `analytics.portfolio`, AND
 * `null` IS NOT `[]`. The distinction is the whole contract: an empty array
 * says "this organization has no projects", which is a different claim and
 * usually a false one. `portfolio_included` states which happened, so the
 * screen can say *"you do not hold analytics.portfolio"* rather than draw an
 * empty table.
 *
 * This is the schema-level half of the lesson from 2026-08-19, when a failed
 * `/api/me` became demonstration data: an absence must stay legible as an
 * absence all the way to the pixel.
 */
export const analyticsSchema = z
  .object({
    scope: z.string(),
    project_id: z.string().nullable(),
    testing: z
      .object({
        counted: z.number(),
        truncated: z.boolean(),
        /** The cap the SERVER applied. Never assumed by the client — see below. */
        limit: z.number(),
        by_colour: counts,
        by_rule: counts,
        by_calculated_result: counts,
        by_authority_level: counts,
        by_test_purpose: counts,
      })
      .passthrough(),
    laboratory: z
      .object({
        total: z.number(),
        by_status: counts,
      })
      .passthrough(),
    portfolio_included: z.boolean(),
    by_project: z.array(portfolioProjectSchema).nullable(),
    /**
     * True when projects were left out of `by_project` by the server's cap.
     *
     * 🔴 NO SILENT CAPS. `portfolio_by_project` runs one report per project
     * and each of those costs a detail read per test, so the server bounds
     * the number of projects at 25. A portfolio table that stopped at 25 and
     * did not say so would read as "this organization has 25 projects".
     */
    portfolio_truncated: z.boolean(),
    /**
     * Why the portfolio is absent despite the caller holding the permission.
     *
     * A portfolio view is organization-wide, so it is omitted rather than
     * mixed in when a `project_id` filter narrows the rest of the response —
     * one response must not carry two different scopes under one `scope`.
     */
    portfolio_omitted_reason: z.string().nullable(),
  })
  .passthrough();

/**
 * 🔴 THERE IS NO `rows` FIELD HERE, AND THAT IS AN AUTHORIZATION BOUNDARY.
 *
 * The first version of the endpoint returned `test_results_report`'s rows
 * verbatim — every `test_id`, `test_number` and disposition. Those rows are
 * the payload of `GET /api/analysis/reports/test-results`, which is gated on
 * `report.generate`; this endpoint is gated on `analytics.view`. Measured
 * against the seed, FOUR roles hold `analytics.view` without
 * `report.generate` (procurement_specialist, production_engineer,
 * executive_viewer, administrator), so each was refused at the report route
 * and handed the same data here. Raised by the Supervisor.
 *
 * Drill-down to source records is the REPORT's job, behind the REPORT's
 * permission. Analytics shows counts. If a future screen needs the rows,
 * call the report endpoint — and be refused when it should be.
 */

export type Analytics = z.infer<typeof analyticsSchema>;

export function fetchAnalytics(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<Analytics> {
  return apiRequest(
    { path: "/api/analysis/analytics", credentials, signal },
    (payload) => analyticsSchema.parse(payload),
  );
}
