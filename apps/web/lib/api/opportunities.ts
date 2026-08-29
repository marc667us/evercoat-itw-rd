/**
 * Opportunities — the front of the digital thread.
 *
 * 🔴 THERE WAS NO CLIENT FOR THIS MODULE AT ALL.
 *
 * `/api/opportunities` has five routes and `app/innovation/page.tsx` rendered a
 * STATIC demonstration array. So `opportunity.create` (the lead) and
 * `opportunity.decide` (the director) were permissions two roles held with
 * nothing in the product to press — and the screen showed a list of ideas that
 * no amount of using the application could change.
 *
 * §2 begins the thread at Opportunity → Project. A converted opportunity links
 * FORWARD to the project it produced; without that link the screen is the
 * isolated island the rule forbids, which is why `project_id` and
 * `project_code` come back on the row.
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";

/** The seven states, exactly as the CHECK constraint allows. */
export const OPPORTUNITY_STATUSES = [
  "draft",
  "feasibility",
  "awaiting_decision",
  "approved",
  "rejected",
  "on_hold",
  "converted",
] as const;

export const OPPORTUNITY_PRIORITIES = ["low", "medium", "high", "critical"] as const;

/**
 * The four decisions.
 *
 * ⚠️ `more_information` IS NOT A REJECTION and must not read as one. It sends
 * the idea back for work; a screen that coloured it with the rejections would
 * teach a lead that asking a question kills a proposal.
 */
export const OPPORTUNITY_DECISIONS = [
  { id: "approve", label: "Approve" },
  { id: "reject", label: "Reject" },
  { id: "hold", label: "Hold" },
  { id: "more_information", label: "Ask for more information" },
] as const;

export const opportunitySchema = z.object({
  id: z.string(),
  opportunity_code: z.string(),
  title: z.string(),
  product_family: z.string().nullable(),
  target_application: z.string().nullable(),
  status: z.string(),
  priority: z.string(),
  decision: z.string().nullable(),
  decided_at: z.string().nullable(),
  created_at: z.string(),
  created_by_name: z.string().nullable(),
  // The forward link §2 requires. Null until it is converted.
  project_id: z.string().nullable(),
  project_code: z.string().nullable(),
});

export type Opportunity = z.infer<typeof opportunitySchema>;

export interface OpportunityCreateRequest {
  readonly opportunity_code: string;
  readonly title: string;
  readonly market_need?: string;
  readonly product_family?: string;
  readonly target_application?: string;
  readonly technical_concept?: string;
  readonly priority?: string;
}

export interface OpportunityDecisionRequest {
  readonly decision: string;
  /**
   * 🔴 REQUIRED, AND THE SERVER SAYS WHY IN ITS OWN COMMENT: "a rejected
   * opportunity with no stated reason gets re-proposed every year by somebody
   * who was not in the room."
   */
  readonly rationale: string;
}

export interface OpportunityConversionRequest {
  readonly project_code: string;
  readonly name: string;
}

export function fetchOpportunities(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<Opportunity[]> {
  return apiRequest({ path: "/api/opportunities", credentials, signal }, (payload) =>
    z.array(opportunitySchema).parse(payload),
  );
}

export function createOpportunity(
  credentials: ApiCredentials,
  request: OpportunityCreateRequest,
): Promise<{ id: string; opportunity_code: string }> {
  return apiRequest(
    { path: "/api/opportunities", method: "POST", credentials, body: request },
    (payload) =>
      z.object({ id: z.string(), opportunity_code: z.string() }).passthrough().parse(payload),
  );
}

/** Send a draft for decision. */
export function submitOpportunity(
  credentials: ApiCredentials,
  opportunityId: string,
): Promise<{ status: string }> {
  return apiRequest(
    { path: `/api/opportunities/${opportunityId}/submission`, method: "POST", credentials },
    (payload) => z.object({ status: z.string() }).passthrough().parse(payload),
  );
}

export function decideOpportunity(
  credentials: ApiCredentials,
  opportunityId: string,
  request: OpportunityDecisionRequest,
): Promise<{ status: string; decision: string }> {
  return apiRequest(
    {
      path: `/api/opportunities/${opportunityId}/decision`,
      method: "POST",
      credentials,
      body: request,
    },
    (payload) =>
      z.object({ status: z.string(), decision: z.string() }).passthrough().parse(payload),
  );
}

/**
 * Turn an approved opportunity into a project.
 *
 * ⚠️ GATED ON `project.create`, NOT AN OPPORTUNITY PERMISSION — creating the
 * project is the act being authorized. Somebody who may decide but may not
 * create projects hands over at this point, which the API's own comment calls
 * the correct separation.
 */
export function convertOpportunity(
  credentials: ApiCredentials,
  opportunityId: string,
  request: OpportunityConversionRequest,
): Promise<{ project_id: string; project_code: string }> {
  return apiRequest(
    {
      path: `/api/opportunities/${opportunityId}/convert`,
      method: "POST",
      credentials,
      body: request,
    },
    (payload) =>
      z
        .object({ project_id: z.string(), project_code: z.string() })
        .passthrough()
        .parse(payload),
  );
}
