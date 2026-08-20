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
  // Both are NOT NULL in `formulations.formulas` (migration 015:352,357).
  // Typing them nullable would let a real contract regression through
  // while the UI silently rendered a gap. Codex found it.
  owner_user_id: z.string(),
  updated_at: z.string(),
  // Null when the formula has no version yet. Not an error, and not zero.
  latest_version_code: z.string().nullable(),
  latest_version_number: z.number().nullable(),
  latest_version_status: z.string().nullable(),
  version_count: z.number(),
});

/**
 * 🔴 THE THREE LATEST-VERSION FIELDS TRAVEL TOGETHER OR NOT AT ALL.
 *
 * Typed independently, a row with a version code and a null status parsed
 * cleanly — and `VersionBadge` then announced "no version has been created
 * for this formula yet" for a formula that plainly has one. The LEFT JOIN
 * LATERAL either matches a version or it does not; there is no state in
 * which it half-matches. Codex found it.
 */
export const formulaWithCoherentVersion = formulaSchema.refine(
  (f) =>
    (f.latest_version_code === null &&
      f.latest_version_number === null &&
      f.latest_version_status === null) ||
    (f.latest_version_code !== null &&
      f.latest_version_number !== null &&
      f.latest_version_status !== null),
  {
    message:
      "latest_version_code, _number and _status must all be present or all be null — " +
      "a half-populated latest version is not a state this endpoint can produce",
  },
);

export type Formula = z.infer<typeof formulaSchema>;

const formulaList = z.array(formulaWithCoherentVersion);

export function fetchFormulas(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<Formula[]> {
  return apiRequest({ path: "/api/formulations", credentials, signal }, (payload) =>
    formulaList.parse(payload),
  );
}
