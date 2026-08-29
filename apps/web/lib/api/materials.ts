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

/**
 * Which status a material may move to, and what that move requires.
 *
 * 🔴 THIS IS A MIRROR OF `TRANSITION_PERMISSION` IN
 * `apps/api/app/domains/materials/service.py`, AND `materials.drift.test.ts`
 * READS THE PYTHON TO PROVE IT.
 *
 * Two literals in two files cannot be type-checked into agreement. The server
 * resolves the permission per TRANSITION — not per endpoint — because "whoever
 * may make any status change may make every status change" was the defect the
 * table exists to prevent: QA holds `material.restrict` and must not thereby
 * be able to promote a material to `preferred`.
 *
 * ⚠️ THE SERVER DECIDES. This exists so the screen can offer only the moves a
 * person can actually make, instead of listing five and refusing four.
 */
export const MATERIAL_TRANSITIONS: Readonly<
  Record<string, ReadonlyArray<{ to: string; permission: string }>>
> = {
  development: [
    { to: "approved", permission: "material.approve_lab" },
    { to: "restricted", permission: "material.restrict" },
    { to: "obsolete", permission: "material.restrict" },
  ],
  approved: [
    { to: "preferred", permission: "material.approve_production" },
    { to: "development", permission: "material.edit" },
    { to: "restricted", permission: "material.restrict" },
    { to: "obsolete", permission: "material.restrict" },
  ],
  preferred: [
    // Demotion one rung at a time — never `preferred` straight to
    // `development`, because reversing two decisions in one action hides
    // which of them was actually reversed.
    { to: "approved", permission: "material.approve_lab" },
    { to: "restricted", permission: "material.restrict" },
    { to: "obsolete", permission: "material.restrict" },
  ],
  restricted: [
    { to: "development", permission: "material.restrict" },
    { to: "obsolete", permission: "material.restrict" },
  ],
  obsolete: [{ to: "development", permission: "material.edit" }],
};

export interface MaterialStatusRequest {
  readonly status: string;
  /** Required by the service AND a CHECK constraint when moving to restricted. */
  readonly restriction_reason?: string;
  readonly reason: string;
}

export function changeMaterialStatus(
  credentials: ApiCredentials,
  materialId: string,
  request: MaterialStatusRequest,
): Promise<{ status: string }> {
  return apiRequest(
    {
      path: `/api/materials/${materialId}/status`,
      method: "POST",
      credentials,
      body: request,
    },
    (payload) => z.object({ status: z.string() }).passthrough().parse(payload),
  );
}

export interface SupplierLinkRequest {
  readonly supplier_id: string;
  readonly supplier_part_code?: string;
  /**
   * 🔴 `undefined` MEANS "LEAVE IT ALONE", NOT `false`.
   *
   * The endpoint is an UPSERT, and the API's own comment records that a plain
   * boolean defaulting to false "silently demoted the primary supplier
   * whenever somebody edited a lead time". So the form sends the flag only
   * when somebody actually set it.
   */
  readonly is_primary?: boolean;
  readonly lead_time_days?: number;
  readonly quoted_price_per_kg?: string;
  readonly currency?: string;
  readonly notes?: string;
}

export function linkSupplier(
  credentials: ApiCredentials,
  materialId: string,
  request: SupplierLinkRequest,
): Promise<{ id: string }> {
  return apiRequest(
    {
      path: `/api/materials/${materialId}/suppliers`,
      method: "POST",
      credentials,
      body: request,
    },
    (payload) => z.object({ id: z.string() }).passthrough().parse(payload),
  );
}
/**
 * ONE material, with every editable field on it.
 *
 * 🔴 THIS EXISTS BECAUSE THE LIST IS NOT ENOUGH TO EDIT FROM, AND EDITING
 * FROM THE LIST WOULD HAVE DESTROYED DATA.
 *
 * `PUT /api/materials/{id}` is a complete replacement — the service sets
 * every editable column in one UPDATE, so a field absent from the request
 * is not "left alone", it is written to null. `GET /api/materials` does
 * not return `description`, `notes`, `epoxy_equivalent_weight` or
 * `amine_hydrogen_equivalent_weight`; a form prefilled from the grid would
 * therefore have silently erased all four every time anybody corrected a
 * material's name.
 *
 * The detail endpoint returns all of them, so the form loads from here.
 * That is the whole reason this schema is separate rather than
 * `materialSchema.extend(...)` on the list shape.
 */
export const materialDetailSchema = z.object({
  id: z.string(),
  material_code: z.string(),
  name: z.string(),
  category: z.string(),
  role: z.string(),
  status: z.string(),
  description: z.string().nullable(),
  cas_number: z.string().nullable(),
  density_g_cm3: quantity,
  solids_fraction: quantity,
  voc_fraction: quantity,
  cost_per_kg: quantity,
  epoxy_equivalent_weight: quantity,
  amine_hydrogen_equivalent_weight: quantity,
  hazard_summary: z.string().nullable(),
  requires_sds: z.boolean(),
  restriction_reason: z.string().nullable(),
  notes: z.string().nullable(),
  updated_at: z.string().nullable(),
});

export type MaterialDetail = z.infer<typeof materialDetailSchema>;

export function fetchMaterial(
  credentials: ApiCredentials,
  materialId: string,
  signal?: AbortSignal,
): Promise<MaterialDetail> {
  return apiRequest(
    { path: `/api/materials/${materialId}`, credentials, signal },
    // `.passthrough()` on purpose: the endpoint also attaches `suppliers`
    // and `created_at`, which this screen does not read and must not
    // reject. Parsing is here to catch a RENAMED field, not an extra one.
    (payload) => materialDetailSchema.passthrough().parse(payload),
  );
}

/**
 * The complete editable state of a material.
 *
 * ⚠️ `material_code` IS SENT AND IS NOT EDITABLE. The server's `MaterialCreate`
 * schema requires the field, and `update_material` then ignores it — the code
 * is the identity every formula component points at through a foreign key.
 * So the form shows it, read-only, and echoes back what it was given. Offering
 * it as an input would be a control whose effect is nothing.
 *
 * `status` is absent for the same class of reason and a stronger one: it is a
 * separately-permissioned decision, and folding it in here would let anybody
 * holding `material.edit` promote a material to `preferred` without holding
 * `material.approve_production`. The status ladder above is where that lives.
 */
export interface MaterialEditRequest {
  readonly material_code: string;
  readonly name: string;
  readonly category: string;
  readonly role: string;
  readonly description?: string;
  readonly cas_number?: string;
  readonly density_g_cm3?: string;
  readonly solids_fraction?: string;
  readonly voc_fraction?: string;
  readonly cost_per_kg?: string;
  readonly epoxy_equivalent_weight?: string;
  readonly amine_hydrogen_equivalent_weight?: string;
  readonly hazard_summary?: string;
  /**
   * 🔴 REQUIRED, UNLIKE EVERY OTHER FIELD HERE, BECAUSE OMITTING IT IS NOT
   * "CLEAR IT" -- IT IS `true`.
   *
   * The server declares `requires_sds: bool = True`, so a caller that leaves
   * it out silently turns the Safety Data Sheet requirement back ON for a
   * material somebody deliberately exempted -- and the formula-submission gate
   * reads this column, so that blocks submissions. Every other optional here
   * defaults to `None`, which IS the clear the form intends; this one defaults
   * to the opposite of an omission's meaning, so the type refuses to let a
   * caller omit it. `MaterialCreateRequest` leaves it optional on purpose: at
   * creation the server's `True` is the intended default rather than a flip.
   */
  readonly requires_sds: boolean;
  readonly notes?: string;
}

export function updateMaterial(
  credentials: ApiCredentials,
  materialId: string,
  request: MaterialEditRequest,
): Promise<{ id: string; material_code: string }> {
  return apiRequest(
    {
      path: `/api/materials/${materialId}`,
      method: "PUT",
      credentials,
      body: request,
    },
    (payload) =>
      z.object({ id: z.string(), material_code: z.string() }).passthrough().parse(payload),
  );
}
