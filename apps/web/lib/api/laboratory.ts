/**
 * Laboratory batches, over HTTP.
 *
 * Parsed rather than cast, for the reason set out in `materials.ts`: a
 * server that renamed a field would hand back rows whose value is
 * `undefined`, and the grid would render blanks that look exactly like a
 * database with nothing recorded.
 *
 * 🔴 THE MASSES ARE STRINGS, AND THAT IS A CORRECTNESS REQUIREMENT.
 *
 * `planned_quantity_kg` is `NUMERIC(14,4)` and `tolerance_percent` is
 * `NUMERIC(6,4)`. FastAPI's `jsonable_encoder` maps `Decimal` to
 * **float** — measured, `Decimal("12.5000") -> 12.5` — so until this was
 * wired the API was shipping a controlled batch mass with its stored
 * scale destroyed. `CLAUDE.md` §5: *"NUMERIC, never float, for
 * percentages, masses, densities and measured values."*
 *
 * That was fixed server-side (`_decimal_strings` in
 * `app/domains/laboratory/service.py`, and
 * `tests/test_laboratory_testing_serialisation.py` pins it). Typing them
 * as `z.string()` here is the client half of the same contract: if the
 * server ever regresses to a float, these rows fail to parse and the
 * screen says so, rather than silently displaying a rounded mass.
 *
 * **Do not `Number()` these.** No arithmetic happens in the browser —
 * §4 keeps derivation on the server, and `0.1 + 0.2` is why.
 *
 * 🔴 WHAT THE LIST ENDPOINT DOES **NOT** RETURN
 *
 * No components, no weighings, no process parameters, no deviations
 * beyond a COUNT. `list_batches` returns the batch's own columns plus
 * four sub-counts, deliberately — a queue of forty batches must not run
 * forty sub-queries. The weigh-up sheet belongs to the batch detail
 * screen, which does not exist yet.
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";

export const batchSchema = z.object({
  id: z.string(),
  batch_number: z.string(),
  status: z.string(),
  // NOT NULL in the schema, so required here. Strings — see the header.
  planned_quantity_kg: z.string(),
  tolerance_percent: z.string(),
  project_id: z.string(),
  formula_version_id: z.string(),
  // From the joins to `formula_versions` and `formulas`. Both are inner
  // joins on NOT NULL foreign keys, so these are always present.
  version_code: z.string(),
  formula_code: z.string(),
  formula_name: z.string(),
  // A batch that has not started has no `started_at`. Nullable, but the
  // key is always sent, so `.nullable()` and never `.optional()` — the
  // distinction Codex flagged on `target_release_date`.
  started_at: z.string().nullable(),
  completed_at: z.string().nullable(),
  updated_at: z.string(),
  // Sub-counts. Integers, so numbers rather than strings: they are
  // cardinalities, not measurements, and no scale can be lost.
  component_count: z.number(),
  unweighed_count: z.number(),
  deviation_count: z.number(),
  sample_count: z.number(),
});

export type Batch = z.infer<typeof batchSchema>;

const batchList = z.array(batchSchema);

export function fetchBatches(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<Batch[]> {
  return apiRequest(
    { path: "/api/laboratory/batches", credentials, signal },
    (payload) => batchList.parse(payload),
  );
}
