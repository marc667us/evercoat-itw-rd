/**
 * The material library, over HTTP.
 *
 * WHY EVERY RESPONSE IS PARSED RATHER THAN CAST
 * ---------------------------------------------
 * `as Material[]` costs nothing and proves nothing: a server that renamed
 * `density_g_cm3` would hand back rows whose density is `undefined`, and
 * the grid would render a column of blanks that looks exactly like a
 * library of materials with no densities recorded. That is not a
 * hypothetical failure on this project — an empty requirement set once
 * rendered "ALL REQUIREMENTS PASSED", and `Number("")` is 0.
 *
 * Parsing turns that into a named error on the screen that consumes it:
 * "the client and the server disagree about this endpoint".
 *
 * WHY THE NUMBERS ARE STRINGS
 * ---------------------------
 * `density_g_cm3`, `cost_per_kg`, the percentages: all NUMERIC in
 * PostgreSQL and all serialised as JSON strings, and they stay strings all
 * the way to the screen. `CLAUDE.md` §5 forbids float for a controlled
 * quantity, and JSON numbers ARE IEEE 754 doubles — parsing "34.75" into a
 * JavaScript number and formatting it back is exactly the round trip the
 * whole `Decimal` discipline in the engine exists to avoid.
 *
 * The web app therefore never computes with these. It displays them. Any
 * arithmetic belongs in `app/calculations`, which is the rule that has
 * already caught a `fraction * 100` and a percentage delta in review here.
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";

/**
 * A quantity as the API sends it: a string, or null when unknown.
 *
 * `null` is a real and common state — a material whose density nobody has
 * measured — and it is NOT zero. The engine refuses to compute rather than
 * assume one, and this type carries that distinction to the UI so a screen
 * cannot render an unknown as a figure.
 */
const quantity = z.string().nullable();

export const materialSchema = z.object({
  id: z.string(),
  material_code: z.string(),
  name: z.string(),
  category: z.string(),
  role: z.string(),
  status: z.string(),
  density_g_cm3: quantity,
  solids_fraction: quantity,
  voc_fraction: quantity,
  // The percentage forms, computed by the ENGINE and sent alongside the
  // fractions precisely so the browser never multiplies by 100. In
  // JavaScript `0.35 * 100` is 35.000000000000004, and a solids content
  // is a figure that ends up on a technical datasheet.
  solids_percent: quantity,
  voc_percent: quantity,
  cost_per_kg: quantity,
  cas_number: z.string().nullable(),
  restriction_reason: z.string().nullable(),
  requires_sds: z.boolean(),
  hazard_summary: z.string().nullable(),
  // `supplier_count` is a bigint from `count(*)`; psycopg renders it as a
  // JSON number, which is safe here because a supplier count cannot reach
  // 2^53. Stated rather than assumed, because the same reasoning does NOT
  // hold for the quantities above.
  supplier_count: z.number(),
  updated_at: z.string().nullable(),
});

export type Material = z.infer<typeof materialSchema>;

export const supplierSchema = z.object({
  id: z.string(),
  supplier_code: z.string(),
  name: z.string(),
  country: z.string().nullable(),
  status: z.string(),
  quality_rating: z.string().nullable(),
  contact_name: z.string().nullable(),
  contact_email: z.string().nullable(),
  material_count: z.number(),
  updated_at: z.string().nullable(),
});

export type Supplier = z.infer<typeof supplierSchema>;

const materialList = z.array(materialSchema);
const supplierList = z.array(supplierSchema);

export function fetchMaterials(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<Material[]> {
  return apiRequest({ path: "/api/materials", credentials, signal }, (payload) =>
    materialList.parse(payload),
  );
}

export function fetchSuppliers(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<Supplier[]> {
  return apiRequest({ path: "/api/suppliers", credentials, signal }, (payload) =>
    supplierList.parse(payload),
  );
}

/**
 * A new raw material.
 *
 * 🔴 EVERY NUMBER IS A STRING ON THE WIRE.
 *
 * `density_g_cm3`, `solids_fraction`, `cost_per_kg` and the two equivalent
 * weights are `NUMERIC` in PostgreSQL and `Decimal` in Pydantic. Sending them
 * as JavaScript numbers would push a controlled value through binary floating
 * point before the server ever saw it — `CLAUDE.md` §5 forbids exactly that,
 * and the API's own comment says the boundary is where the guarantee is made.
 * The form collects text and it is sent as text.
 *
 * ⚠️ `status` IS NOT HERE. Creation always yields `development`; the server
 * says so and offering the field would imply a choice that does not exist.
 */
export interface MaterialCreateRequest {
  readonly material_code: string;
  readonly name: string;
  readonly category: string;
  readonly role: string;
  readonly description?: string;
  readonly cas_number?: string;
  readonly density_g_cm3?: string;
  readonly solids_fraction?: string;
  readonly cost_per_kg?: string;
  readonly hazard_summary?: string;
  readonly requires_sds?: boolean;
  readonly notes?: string;
}

/** The roles a material can play, exactly as the server's pattern allows. */
export const MATERIAL_ROLES = [
  "resin",
  "binder",
  "hardener",
  "catalyst",
  "filler",
  "extender",
  "pigment",
  "additive",
  "solvent",
  "other",
] as const;

export function createMaterial(
  credentials: ApiCredentials,
  request: MaterialCreateRequest,
): Promise<{ id: string; material_code: string }> {
  return apiRequest(
    { path: "/api/materials", method: "POST", credentials, body: request },
    (payload) =>
      z.object({ id: z.string(), material_code: z.string() }).passthrough().parse(payload),
  );
}
