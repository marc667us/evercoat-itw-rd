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
import { useMaterialWrites, useSuppliers } from "@/lib/api/hooks";
import { MATERIAL_TRANSITIONS, type Supplier } from "@/lib/api/materials";
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
  const supplierRows = suppliers.data ?? [];
  const needsRestrictionReason = target === "restricted";

  if (moves.length === 0 && !maySupplier) {
    return (
      <p className="text-xs text-slate-600">
        Your roles hold none of the permissions that change {materialCode} — its
        status ladder and its suppliers are both someone else&rsquo;s to manage.
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
