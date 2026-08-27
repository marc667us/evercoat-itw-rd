"use client";

/**
 * Reference data — units and product families.
 *
 * 🔴 §H SCHEDULES THIS FOR SLICE 3, *"because formulation needs canonical
 * units"*, under the rule that a configuration value referenced anywhere in the
 * plan must have an Administration screen in the same slice or earlier. Slice 3
 * shipped formulation. The screen was never built: measured 2026-08-27, three
 * write endpoints with no client function.
 *
 * §5 is the reason it matters more than a settings page usually would:
 * *"store measurements as value + unit with canonical units… never as free
 * strings."* Every requirement, every test result and every material property
 * points at a row in this table. A unit that cannot be added is a measurement
 * that cannot be recorded.
 *
 * 🔴 RETIRED, NEVER DELETED — AND THE ENDPOINT IS A PATCH FOR THAT REASON.
 * `_RETIRE_SQL` flips `is_active`; there is no DELETE. A unit in use by a
 * historical test result must go on resolving, or the record it belongs to
 * stops meaning anything. Retiring stops it being offered for new work and
 * leaves every existing reference intact.
 *
 * ⚠️ `quantity_kind` IS REQUIRED, and the server's comment says why: *"a unit
 * with no quantity kind cannot be offered as a choice for a requirement — the
 * form has to know that MPa is a stress and minutes are a time, or it lists
 * every unit in the system for every measurement."*
 */

import Link from "next/link";
import { useState } from "react";

import { ContextSubmenu } from "@/components/ui/context-submenu";
import { EntityHeader, headerCount } from "@/components/ui/entity-header";
import { LiveOnlyPage } from "@/components/ui/data-source-banner";
import { serverMessage } from "@/lib/api/client";
import { useAdminActions, useProductFamilies, useUnits } from "@/lib/api/hooks";
import type { ProductFamily, Unit } from "@/lib/api/admin";
import { permits, usePermissions } from "@/lib/permissions";

import { ADMIN_SECTIONS } from "../sections";

const INPUT =
  "mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm text-slate-900 " +
  "focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";
const LABEL = "block text-xs font-medium text-slate-700";
const BUTTON_QUIET =
  "rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 " +
  "hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400";
const TAG =
  "rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase " +
  "tracking-wide text-slate-600";

function ReferenceRow({
  id,
  code,
  name,
  detail,
  isActive,
  pending,
  onToggle,
}: {
  id: string;
  code: string;
  name: string;
  detail: string | null;
  isActive: boolean;
  pending: boolean;
  onToggle: (id: string, isActive: boolean) => void;
}) {
  return (
    <li className="flex flex-wrap items-baseline gap-2 text-sm">
      <span className="font-medium tabular-nums text-slate-900">{code}</span>
      <span className="text-slate-800">{name}</span>
      {detail !== null && <span className="text-xs text-slate-600">{detail}</span>}
      {/* A retired row still appears. It has to: a measurement recorded against
          it in 2024 must still resolve, and an administrator needs to see that
          the row exists before wondering why the code cannot be reused. */}
      {!isActive && <span className={TAG}>retired</span>}
      <button
        type="button"
        className="text-xs text-slate-700 underline underline-offset-2 disabled:cursor-not-allowed disabled:text-slate-400"
        disabled={pending}
        onClick={() => onToggle(id, !isActive)}
      >
        {isActive ? "Retire" : "Restore"}
      </button>
    </li>
  );
}

export default function ReferenceDataPage() {
  const permissions = usePermissions();
  const mayManage = permits(permissions, "admin.reference_data");

  const units = useUnits();
  const families = useProductFamilies();
  const actions = useAdminActions();

  const [unitCode, setUnitCode] = useState("");
  const [unitName, setUnitName] = useState("");
  const [quantityKind, setQuantityKind] = useState("");
  const [familyCode, setFamilyCode] = useState("");
  const [familyName, setFamilyName] = useState("");

  const unitRows: Unit[] = units.data ?? [];
  const familyRows: ProductFamily[] = families.data ?? [];

  return (
    <div>
      <EntityHeader
        eyebrow="Governance"
        title="Reference data"
        crumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Administration", href: "/admin" },
        ]}
        fields={[
          {
            label: "Units",
            value: headerCount(
              unitRows,
              !units.isLoading && units.error === null && units.unavailable === null,
            ),
          },
          {
            label: "Product families",
            value: headerCount(
              familyRows,
              !families.isLoading && families.error === null && families.unavailable === null,
            ),
          },
        ]}
      />
      <ContextSubmenu items={ADMIN_SECTIONS} activeHref="/admin/reference-data" />

      <div className="p-6">
        <LiveOnlyPage
          title="Units and product families"
          lede="Canonical units are what stop a measurement being a free string
                (§5). Every requirement, test result and material property points
                at a row here."
          // The hook's answer, not a hard-coded `null` — see the stage-gates
          // page for the measurement. `units` and `families` share a session,
          // so either one reporting unavailable means the same thing.
          unavailable={units.unavailable}
          notInvented="reference data"
        >
          {units.unavailable !== null ? (
            <p className="text-sm text-slate-600">
              Reference data cannot be shown until this build is pointed at an API.
            </p>
          ) : !mayManage ? (
            <p className="text-sm text-slate-600">
              Managing reference data needs{" "}
              <code className="text-xs">admin.reference_data</code>, which this
              account does not hold.{" "}
              {/* ⚠️ THE READS ARE WIDER THAN THE WRITES, and that is deliberate
                  on the server: `GET /units` accepts `admin.reference_data` OR
                  `material.view`, because a chemist has to see the units to use
                  them. This screen is the WRITE surface, so it asks for the
                  write permission. */}
              The unit list itself is readable with{" "}
              <code className="text-xs">material.view</code>.
            </p>
          ) : (
            <div className="space-y-8">
              <section>
                <h2 className="text-sm font-semibold text-slate-900">Units</h2>
                {units.error !== null ? (
                  <p role="alert" className="mt-1 text-sm text-red-700">
                    The units could not be loaded: {serverMessage(units.error)}
                  </p>
                ) : units.isLoading ? (
                  <p className="mt-1 text-sm text-slate-600">Loading units…</p>
                ) : unitRows.length === 0 ? (
                  <p className="mt-1 text-sm text-slate-600">No units defined.</p>
                ) : (
                  <ul className="mt-2 space-y-1">
                    {unitRows.map((u) => (
                      <ReferenceRow
                        key={u.id}
                        id={u.id}
                        code={u.code}
                        name={u.name}
                        detail={u.quantity_kind}
                        isActive={u.is_active}
                        pending={actions.isPending}
                        onToggle={(id, isActive) =>
                          actions.setItemActive("units", id, isActive)
                        }
                      />
                    ))}
                  </ul>
                )}

                <div className="mt-3 flex max-w-3xl flex-wrap items-end gap-2">
                  <div className="w-40">
                    <label className={LABEL} htmlFor="unit-code">
                      Code
                    </label>
                    <input
                      id="unit-code"
                      className={INPUT}
                      maxLength={50}
                      value={unitCode}
                      onChange={(e) => setUnitCode(e.target.value)}
                      placeholder="MPa"
                    />
                  </div>
                  <div className="min-w-[14rem] flex-1">
                    <label className={LABEL} htmlFor="unit-name">
                      Name
                    </label>
                    <input
                      id="unit-name"
                      className={INPUT}
                      maxLength={200}
                      value={unitName}
                      onChange={(e) => setUnitName(e.target.value)}
                      placeholder="megapascals"
                    />
                  </div>
                  <div className="w-44">
                    <label className={LABEL} htmlFor="unit-kind">
                      Quantity kind
                    </label>
                    <input
                      id="unit-kind"
                      className={INPUT}
                      maxLength={50}
                      value={quantityKind}
                      onChange={(e) => setQuantityKind(e.target.value)}
                      placeholder="stress"
                    />
                  </div>
                  <button
                    type="button"
                    className={BUTTON_QUIET}
                    disabled={
                      actions.isPending ||
                      // Not while the list is still arriving: a code cannot be
                      // checked against rows nobody has seen yet.
                      units.isLoading ||
                      unitCode.trim() === "" ||
                      unitName.trim() === "" ||
                      // Required, not optional — without it the unit cannot be
                      // offered as a choice for a measurement of any kind.
                      quantityKind.trim() === ""
                    }
                    onClick={() =>
                      actions.addUnit(
                        {
                          code: unitCode.trim(),
                          name: unitName.trim(),
                          quantity_kind: quantityKind.trim(),
                        },
                        () => {
                          setUnitCode("");
                          setUnitName("");
                          setQuantityKind("");
                        },
                      )
                    }
                  >
                    Add unit
                  </button>
                </div>
              </section>

              <section>
                <h2 className="text-sm font-semibold text-slate-900">Product families</h2>
                {families.error !== null ? (
                  <p role="alert" className="mt-1 text-sm text-red-700">
                    The product families could not be loaded:{" "}
                    {serverMessage(families.error)}
                  </p>
                ) : families.isLoading ? (
                  <p className="mt-1 text-sm text-slate-600">Loading product families…</p>
                ) : familyRows.length === 0 ? (
                  <p className="mt-1 text-sm text-slate-600">None defined.</p>
                ) : (
                  <ul className="mt-2 space-y-1">
                    {familyRows.map((f) => (
                      <ReferenceRow
                        key={f.id}
                        id={f.id}
                        code={f.code}
                        name={f.name}
                        detail={f.description}
                        isActive={f.is_active}
                        pending={actions.isPending}
                        onToggle={(id, isActive) =>
                          actions.setItemActive("product-families", id, isActive)
                        }
                      />
                    ))}
                  </ul>
                )}

                <div className="mt-3 flex max-w-3xl flex-wrap items-end gap-2">
                  <div className="w-52">
                    <label className={LABEL} htmlFor="family-code">
                      Code
                    </label>
                    <input
                      id="family-code"
                      className={INPUT}
                      maxLength={50}
                      value={familyCode}
                      onChange={(e) => setFamilyCode(e.target.value)}
                      placeholder="EPOXY_PUTTY"
                    />
                  </div>
                  <div className="min-w-[16rem] flex-1">
                    <label className={LABEL} htmlFor="family-name">
                      Name
                    </label>
                    <input
                      id="family-name"
                      className={INPUT}
                      maxLength={200}
                      value={familyName}
                      onChange={(e) => setFamilyName(e.target.value)}
                    />
                  </div>
                  <button
                    type="button"
                    className={BUTTON_QUIET}
                    disabled={
                      actions.isPending ||
                      families.isLoading ||
                      familyCode.trim() === "" ||
                      familyName.trim() === ""
                    }
                    onClick={() =>
                      actions.addFamily(
                        { code: familyCode.trim(), name: familyName.trim() },
                        () => {
                          setFamilyCode("");
                          setFamilyName("");
                        },
                      )
                    }
                  >
                    Add family
                  </button>
                </div>
              </section>

              {actions.error !== null && (
                <p
                  role="alert"
                  className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900"
                >
                  {serverMessage(actions.error)}
                </p>
              )}
              {actions.error === null && actions.lastAction !== null && (
                <p role="status" className="text-sm text-slate-700">
                  Recorded: {actions.lastAction}.
                </p>
              )}

              <p className="text-xs text-slate-600">
                <Link href="/admin" className="underline underline-offset-2">
                  Back to Administration
                </Link>
              </p>
            </div>
          )}
        </LiveOnlyPage>
      </div>
    </div>
  );
}
