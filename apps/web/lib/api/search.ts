/**
 * Global search, over HTTP — spec §29.
 *
 * 🔴 `searched` AND `absent` ARE PARSED, NOT DROPPED, AND THE SCREEN MUST USE
 * THEM.
 *
 * "No results" and "not searched" are different answers. A chemist who cannot
 * see failures must be told failures were not searched — rendering an empty
 * failures section tells them this organization holds no matching failure,
 * which is false, and it is false in the direction that hides a real record
 * from someone chasing a problem.
 *
 * `absent` carries the two record types §29 names that have no table in this
 * system at all (patents, released products). Same reason: a search box that
 * silently returns nothing for "patent" is indistinguishable from one that
 * looked and found none.
 *
 * ⚠️ THIS IS NOT `searchKnowledge`. That one retrieves passages from the
 * library by embedding distance and can be approximately right. This finds
 * records by code and name, and an exact code match is meant to win — see
 * `app/domains/search/service.py` for why there are two.
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";

export const searchHitSchema = z.object({
  record_type: z.string(),
  label: z.string(),
  id: z.string(),
  /** Null for record types that have no code of their own — documents. */
  code: z.string().nullable(),
  title: z.string(),
  subtitle: z.string().nullable(),
  state: z.string().nullable(),
  project_id: z.string().nullable(),
  /**
   * The detail screen for this record, or NULL when there is not one.
   *
   * 🔴 NULLABLE ON PURPOSE. Most record types in this product have a list
   * screen and no detail screen, and an earlier draft of the registry linked
   * all fifteen to routes that do not exist -- every result would have 404'd.
   * `components/ui/record-link.tsx` already carries the lesson: a dead link
   * looks like a working product until it is clicked.
   */
  path: z.string().nullable(),
  /** The screen that lists this record type. Always present. */
  list_path: z.string(),
});

export type SearchHit = z.infer<typeof searchHitSchema>;

export const searchableTypeSchema = z.object({
  record_type: z.string(),
  label: z.string(),
  permission: z.string(),
  permitted: z.boolean(),
  has_detail_screen: z.boolean(),
  list_path: z.string(),
});

export type SearchableType = z.infer<typeof searchableTypeSchema>;

export const absentTypeSchema = z.object({
  record_type: z.string(),
  reason: z.string(),
});

export type AbsentType = z.infer<typeof absentTypeSchema>;

export const searchResultsSchema = z.object({
  query: z.string(),
  results: z.array(searchHitSchema),
  result_count: z.number(),
  searched: z.array(searchableTypeSchema),
  absent: z.array(absentTypeSchema),
  /**
   * The page filled exactly to the limit, so there may be more. Reported
   * rather than inferred, because a screen cannot tell a full page from a
   * complete answer and I78 was this same defect in the knowledge list.
   */
  truncated: z.boolean(),
});

export type SearchResults = z.infer<typeof searchResultsSchema>;

export function searchRecords(
  credentials: ApiCredentials,
  query: string,
  types: readonly string[] | undefined,
  signal?: AbortSignal,
): Promise<SearchResults> {
  const params = new URLSearchParams({ q: query });
  for (const type of types ?? []) params.append("types", type);
  return apiRequest(
    { path: `/api/search?${params.toString()}`, credentials, signal },
    (payload) => searchResultsSchema.parse(payload),
  );
}
