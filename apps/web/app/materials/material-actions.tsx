"use client";

/**
 * What a person can DO to a material: move it along its status ladder, and
 * link a supplier to it.
 *
 * 🔴 BOTH ROUTES HAD NO CONTROL, AND TWO ROLES HELD THE PERMISSIONS.
 *
 * `POST /materials/{id}/status` and `POST /materials/{id}/suppliers` existed
 * with nothing in the application to press. `supplier.manage` is held by the
 * procurement specialist and the chemist; `material.restrict` by QA. Those
 * people could not do the thing their permission names.
 *
 * 🔴 THE LADDER IS OFFERED, NOT ENUMERATED FREELY.
 *
 * The server resolves the permission PER TRANSITION, not per endpoint — QA
 * holding `material.restrict` must not thereby be able to promote a material
 * to `preferred`. So this offers only the moves valid FROM the material's
 * current status, and only those whose permission the caller holds. A select
 * listing all five statuses would be four refusals waiting to happen.
 *
 * `MATERIAL_TRANSITIONS` is a mirror of the server's table and
 * `materials.drift.test.ts` reads the Python to prove it still matches.
 *
 * ⚠️ RESTRICTING HARD-BLOCKS EVERY FORMULA THAT USES THE MATERIAL, so the
 * reason field is required by the service AND by a CHECK constraint. The form
 * asks for it up front rather than letting the refusal arrive at the end.
 */

import { useState } from "react";

import { CREATE_INPUT, CREATE_LABEL } from "@/components/ui/create-form";
import { serverMessage } from "@/lib/api/client";
import { useMaterial, useMaterialWrites, useSuppliers } from "@/lib/api/hooks";
import {
  MATERIAL_ROLES,
  MATERIAL_TRANSITIONS,
  type MaterialDetail,
  type Supplier,
} from "@/lib/api/materials";
import { permits, usePermissions } from "@/lib/permissions";

export function MaterialActions({
  materialId,
  materialCode,
  status,
}: {
  readonly materialId: string;
  readonly materialCode: string;
  readonly status: string;
}) {
  const permissions = usePermissions();
  const writes = useMaterialWrites(materialId);
  const suppliers = useSuppliers<Supplier[]>([], (live) => live);

  const [target, setTarget] = useState("");
  const [reason, setReason] = useState("");
  const [restrictionReason, setRestrictionReason] = useState("");

  const [supplierId, setSupplierId] = useState("");
  const [partCode, setPartCode] = useState("");
  const [leadTime, setLeadTime] = useState("");
  const [primary, setPrimary] = useState(false);
  const [primaryTouched, setPrimaryTouched] = useState(false);

  // Only the moves this caller can actually make.
  const moves = (MATERIAL_TRANSITIONS[status] ?? []).filter((move) =>
    permits(permissions, move.permission),
  );
  const maySupplier = permits(permissions, "supplier.manage");
  const mayEdit = permits(permissions, "material.edit");
  const supplierRows = suppliers.data ?? [];
  const needsRestrictionReason = target === "restricted";

  if (moves.length === 0 && !maySupplier && !mayEdit) {
    return (
      <p className="text-xs text-slate-600">
        Your roles hold none of the permissions that change {materialCode} — its
        data, its status ladder and its suppliers are all someone else&rsquo;s to
        manage.
      </p>
    );
  }

  return (
    <div className="grid gap-4">
      {moves.length > 0 && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            writes.changeStatus(
              {
                status: target,
                reason,
                restriction_reason:
                  needsRestrictionReason && restrictionReason !== ""
                    ? restrictionReason
                    : undefined,
              },
              () => {
                setTarget("");
                setReason("");
                setRestrictionReason("");
              },
            );
          }}
        >
          <h4 className="text-sm font-semibold text-slate-900">Change status</h4>
          <p className="mt-1 text-xs text-slate-600">
            Currently <strong>{status}</strong>. Only the moves your roles allow
            from here are listed.
          </p>
          <div className="mt-2 grid gap-3 sm:grid-cols-2">
            <label className={CREATE_LABEL}>
              Move to
              <select
                className={CREATE_INPUT}
                required
                value={target}
                onChange={(event) => setTarget(event.target.value)}
              >
                <option value="">Choose…</option>
                {moves.map((move) => (
                  <option key={move.to} value={move.to}>
                    {move.to}
                  </option>
                ))}
              </select>
            </label>
            <label className={CREATE_LABEL}>
              Reason
              <input
                className={CREATE_INPUT}
                required
                minLength={3}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            </label>
            {needsRestrictionReason && (
              <label className={`${CREATE_LABEL} sm:col-span-2`}>
                Why it is being restricted
                <input
                  className={CREATE_INPUT}
                  required
                  value={restrictionReason}
                  onChange={(event) => setRestrictionReason(event.target.value)}
                />
                <span className="mt-1 block text-xs font-normal text-amber-900">
                  Restricting this material hard-blocks every formula that uses
                  it. The reason is stored and shown wherever that block appears.
                </span>
              </label>
            )}
          </div>
          <button
            type="submit"
            className="mt-3 rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={writes.isPending || target === ""}
          >
            {writes.isPending ? "Saving…" : "Change status"}
          </button>
        </form>
      )}

      {maySupplier && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            writes.linkSupplier(
              {
                supplier_id: supplierId,
                supplier_part_code: partCode === "" ? undefined : partCode,
                lead_time_days: leadTime === "" ? undefined : Number(leadTime),
                // 🔴 SENT ONLY IF SOMEBODY TOUCHED IT. The endpoint is an
                // upsert and `undefined` means "leave the flag alone" — a
                // plain `false` here silently demoted the primary supplier
                // whenever anybody edited a lead time, which the API's own
                // comment records as a Supervisor finding.
                is_primary: primaryTouched ? primary : undefined,
              },
              () => {
                setPartCode("");
                setLeadTime("");
                setPrimaryTouched(false);
              },
            );
          }}
        >
          <h4 className="text-sm font-semibold text-slate-900">Link a supplier</h4>
          <div className="mt-2 grid gap-3 sm:grid-cols-2">
            <label className={CREATE_LABEL}>
              Supplier
              <select
                className={CREATE_INPUT}
                required
                value={supplierId}
                onChange={(event) => setSupplierId(event.target.value)}
              >
                <option value="">
                  {supplierRows.length === 0 ? "No suppliers on file" : "Choose…"}
                </option>
                {supplierRows.map((supplier) => (
                  <option key={supplier.id} value={supplier.id}>
                    {supplier.name}
                  </option>
                ))}
              </select>
            </label>
            <label className={CREATE_LABEL}>
              Their part code
              <input
                className={CREATE_INPUT}
                value={partCode}
                onChange={(event) => setPartCode(event.target.value)}
              />
            </label>
            <label className={CREATE_LABEL}>
              Lead time (days)
              <input
                className={CREATE_INPUT}
                inputMode="numeric"
                value={leadTime}
                onChange={(event) => setLeadTime(event.target.value)}
              />
            </label>
            <label className="flex items-center gap-2 self-end text-xs font-medium text-slate-700">
              <input
                type="checkbox"
                checked={primary}
                onChange={(event) => {
                  setPrimary(event.target.checked);
                  setPrimaryTouched(true);
                }}
              />
              Make this the primary supplier
            </label>
          </div>
          <button
            type="submit"
            className="mt-3 rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={writes.isPending || supplierId === "" || supplierRows.length === 0}
          >
            {writes.isPending ? "Saving…" : "Link supplier"}
          </button>
        </form>
      )}

      {mayEdit && <EditMaterial materialId={materialId} materialCode={materialCode} />}

      {writes.error !== null && (
        <p role="alert" className="text-sm text-rose-700">
          {serverMessage(writes.error)}
        </p>
      )}
      {writes.error === null && writes.lastAction && (
        <p role="status" className="text-sm text-slate-700">
          {writes.lastAction}
        </p>
      )}
    </div>
  );
}
/**
 * Which record the edit form is holding -- the user's unsaved edits, the record
 * that arrived, or nothing yet.
 *
 * 🔴 A PURE FUNCTION BECAUSE THE FIRST VERSION OF THIS RULE WAS WRONG IN A WAY
 * THAT LOOKED FINE ON SCREEN.
 *
 * It adopted the fetched record whenever the record's id changed, and held the
 * previous draft otherwise. Choosing a different material in the picker changes
 * `materialId` immediately, but the new record is a new query key, so
 * `detail.data` is `undefined` for as long as that request takes. In that gap
 * the form went on showing the PREVIOUS material's name, description and
 * quantities -- under the newly-chosen material's heading and code -- and
 * pressing Save would have written one material's data onto another. The PUT
 * replaces the row, so that is not a partial update; it is a substitution.
 *
 * The fix is to key the answer on `materialId` and not on what arrived: a
 * record is only shown while it BELONGS to the material currently chosen.
 *
 * ⚠️ UNSAVED EDITS SURVIVE A ROUND TRIP THROUGH ANOTHER MATERIAL, by design --
 * `held` is returned whenever it is still the right material, so A → B → A
 * comes back to A's edits rather than silently discarding typing. What it must
 * never do is show them under B.
 */
export function heldMaterialDraft(
  materialId: string,
  loaded: MaterialDetail | undefined,
  held: MaterialDetail | null,
): MaterialDetail | null {
  if (held !== null && held.id === materialId) return held;
  if (loaded !== undefined && loaded.id === materialId) return loaded;
  return null;
}

/** A blank input clears the column, so "" and undefined are the same request. */
function orUndefined(value: string): string | undefined {
  return value.trim() === "" ? undefined : value.trim();
}

/**
 * Edit a material's data.
 *
 * 🔴 `PUT /api/materials/{id}` HAD NO CLIENT AT ALL. Not an ungated control --
 * no request function, no hook, nothing. `material.edit` is held by the
 * procurement specialist and the chemist, and neither could correct a typo in
 * a material name through the product. The role audit reported the permission
 * as held-with-no-control, and this was why.
 *
 * 🔴 IT LOADS FROM THE DETAIL ENDPOINT, AND THAT IS NOT A PREFERENCE.
 *
 * The PUT replaces the whole editable row -- the service sets every column in
 * one UPDATE -- and `GET /api/materials` does not return `description`,
 * `notes`, `epoxy_equivalent_weight` or `amine_hydrogen_equivalent_weight`.
 * A form built from the grid rows already in memory would have looked correct,
 * saved successfully, and erased all four every time anybody fixed a name.
 *
 * ⚠️ THE CODE AND THE STATUS ARE NOT HERE. `material_code` is echoed back
 * because the server's schema requires the field and `update_material` then
 * ignores it -- the code is the identity formula components point at. Status
 * is a separately-permissioned decision and lives in the ladder above; folding
 * it in would let `material.edit` promote a material to `preferred`.
 */
function EditMaterial({
  materialId,
  materialCode,
}: {
  readonly materialId: string;
  readonly materialCode: string;
}) {
  const detail = useMaterial(materialId);
  const writes = useMaterialWrites(materialId);

  // Only what the person has TYPED lives in state; what the form shows is
  // derived, so there is no moment where the two can disagree. `null` until
  // the record arrives, so the inputs are not created empty and then
  // repopulated -- which would discard anything typed in the gap, and briefly
  // show a form full of blanks that reads as a material with no data recorded
  // rather than one still loading.
  const [edited, setEdited] = useState<MaterialDetail | null>(null);
  const draft = heldMaterialDraft(materialId, detail.data, edited);

  if (detail.error !== null) {
    return (
      <div>
        <h4 className="text-sm font-semibold text-slate-900">Edit this material</h4>
        <p role="alert" className="mt-1 text-sm text-rose-700">
          {serverMessage(detail.error)}
        </p>
      </div>
    );
  }

  if (draft === null) {
    return (
      <div>
        <h4 className="text-sm font-semibold text-slate-900">Edit this material</h4>
        <p className="mt-1 text-sm text-slate-600">
          {detail.isLoading ? "Loading this material…" : "Nothing to edit."}
        </p>
      </div>
    );
  }

  const current = draft;

  const set = <K extends keyof MaterialDetail>(key: K, value: MaterialDetail[K]) =>
    setEdited({ ...current, [key]: value });

  const textOf = (key: keyof MaterialDetail): string => {
    const value = current[key];
    return typeof value === "string" ? value : "";
  };

  const field = (
    label: string,
    key: keyof MaterialDetail,
    hint?: string,
  ) => (
    <label className={CREATE_LABEL}>
      {label}
      <input
        className={CREATE_INPUT}
        inputMode="decimal"
        value={textOf(key)}
        onChange={(event) => set(key, event.target.value as MaterialDetail[typeof key])}
      />
      {hint !== undefined && (
        <span className="mt-1 block text-[11px] font-normal text-slate-600">{hint}</span>
      )}
    </label>
  );

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        // 🔴 THE SNAPSHOT IS DROPPED ON SUCCESS, OR THE NEXT SAVE RE-SENDS IT.
        //
        // Both reviewers found this independently. `heldMaterialDraft` prefers
        // what was typed over what arrived, which is right while editing and
        // wrong once saved: the refetch `useMaterialWrites` triggers would land
        // and be ignored, leaving a pre-save snapshot in the form. Because the
        // PUT REPLACES the row, pressing Save a second time then writes that
        // stale snapshot over anything a colleague changed in between -- a lost
        // update, with nothing on screen to say it happened.
        //
        // Clearing it shows the saved record again, and makes the invalidation
        // in `useMaterialWrites` mean what its comment claims.
        writes.edit(
          {
            // Echoed, not edited. See the note above.
          material_code: materialCode,
            name: current.name.trim(),
            category: current.category.trim(),
            role: current.role,
            description: orUndefined(textOf("description")),
            cas_number: orUndefined(textOf("cas_number")),
            density_g_cm3: orUndefined(textOf("density_g_cm3")),
            solids_fraction: orUndefined(textOf("solids_fraction")),
            voc_fraction: orUndefined(textOf("voc_fraction")),
            cost_per_kg: orUndefined(textOf("cost_per_kg")),
            epoxy_equivalent_weight: orUndefined(textOf("epoxy_equivalent_weight")),
            amine_hydrogen_equivalent_weight: orUndefined(
              textOf("amine_hydrogen_equivalent_weight"),
            ),
            hazard_summary: orUndefined(textOf("hazard_summary")),
            requires_sds: current.requires_sds,
            notes: orUndefined(textOf("notes")),
          },
          () => setEdited(null),
        );
      }}
    >
      <h4 className="text-sm font-semibold text-slate-900">Edit this material</h4>
      <p className="mt-1 text-xs text-slate-600">
        {/* Said plainly because the endpoint really does replace the row: an
            emptied field is a cleared field, not an untouched one. */}
        Every field here is saved together. Emptying one <strong>clears</strong> it
        rather than leaving it as it was. The code <code>{materialCode}</code> and the
        status are not editable here.
      </p>

      <div className="mt-2 grid gap-3 sm:grid-cols-2">
        <label className={CREATE_LABEL}>
          Name
          <input
            className={CREATE_INPUT}
            required
            value={current.name}
            onChange={(event) => set("name", event.target.value)}
          />
        </label>
        <label className={CREATE_LABEL}>
          Category
          <input
            className={CREATE_INPUT}
            required
            value={current.category}
            onChange={(event) => set("category", event.target.value)}
          />
        </label>
        <label className={CREATE_LABEL}>
          Role
          <select
            className={CREATE_INPUT}
            value={current.role}
            onChange={(event) => set("role", event.target.value)}
          >
            {/* The server's own pattern, mirrored. Free text here would be a
                422 the person only sees after filling the rest in. */}
            {MATERIAL_ROLES.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </select>
        </label>
        <label className={CREATE_LABEL}>
          CAS number
          <input
            className={CREATE_INPUT}
            value={textOf("cas_number")}
            onChange={(event) => set("cas_number", event.target.value)}
          />
        </label>
        {field("Density (g/cm³)", "density_g_cm3")}
        {field("Cost per kg", "cost_per_kg")}
        {/* Fractions, not percentages: the engine consumes the fraction, and a
            browser that divided by 100 would be doing arithmetic on a
            controlled quantity. CLAUDE.md §5. */}
        {field("Solids fraction (0–1)", "solids_fraction", "A fraction, not a percentage — 0.65, not 65.")}
        {field("VOC fraction (0–1)", "voc_fraction", "A fraction, not a percentage.")}
        {field("Epoxy equivalent weight", "epoxy_equivalent_weight")}
        {field("Amine hydrogen equivalent weight", "amine_hydrogen_equivalent_weight")}
      </div>

      <div className="mt-3 grid gap-3">
        <label className={CREATE_LABEL}>
          Description
          <textarea
            className={CREATE_INPUT}
            rows={2}
            value={textOf("description")}
            onChange={(event) => set("description", event.target.value)}
          />
        </label>
        <label className={CREATE_LABEL}>
          Hazard summary
          <textarea
            className={CREATE_INPUT}
            rows={2}
            value={textOf("hazard_summary")}
            onChange={(event) => set("hazard_summary", event.target.value)}
          />
        </label>
        <label className={CREATE_LABEL}>
          Notes
          <textarea
            className={CREATE_INPUT}
            rows={2}
            value={textOf("notes")}
            onChange={(event) => set("notes", event.target.value)}
          />
        </label>
        <label className="flex items-center gap-2 text-xs font-medium text-slate-700">
          <input
            type="checkbox"
            checked={current.requires_sds}
            onChange={(event) => set("requires_sds", event.target.checked)}
          />
          A Safety Data Sheet is required for this material
        </label>
      </div>

      <button
        type="submit"
        className="mt-3 rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        disabled={
          writes.isPending || current.name.trim() === "" || current.category.trim() === ""
        }
      >
        {writes.isPending ? "Saving…" : "Save changes"}
      </button>
    </form>
  );
}
