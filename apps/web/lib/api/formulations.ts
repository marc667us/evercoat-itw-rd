/**
 * Formulas, over HTTP.
 *
 * `GET /api/formulations` returns each formula WITH its latest version
 * (`list_formulas`, a LEFT JOIN LATERAL). That matters for the shape: the
 * latest-version fields are nullable not because the API is sloppy but
 * because a formula can exist with no version yet, and the list must be
 * able to say so rather than omit the formula.
 *
 * 🔴 `version_count` IS A COUNT AND `latest_version_number` IS A VERSION.
 *
 * They are both integers and they are not interchangeable. A formula with
 * versions 1, 2 and 4 (3 having been deleted — which this schema forbids,
 * but the reasoning is the point) has a count of 3 and a latest number of
 * 4. Rendering one under the other's heading is the kind of error nobody
 * notices because both are small plausible numbers.
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";

export const formulaSchema = z.object({
  id: z.string(),
  formula_code: z.string(),
  name: z.string(),
  product_family: z.string().nullable(),
  status: z.string(),
  project_id: z.string(),
  project_code: z.string(),
  owner_user_id: z.string().nullable(),
  updated_at: z.string().nullable(),
  // Null when the formula has no version yet. Not an error, and not zero.
  latest_version_code: z.string().nullable(),
  latest_version_number: z.number().nullable(),
  latest_version_status: z.string().nullable(),
  version_count: z.number(),
});

export type Formula = z.infer<typeof formulaSchema>;

const formulaList = z.array(formulaSchema);

export function fetchFormulas(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<Formula[]> {
  return apiRequest({ path: "/api/formulations", credentials, signal }, (payload) =>
    formulaList.parse(payload),
  );
}
