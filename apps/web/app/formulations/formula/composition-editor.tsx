"use client";

/**
 * Enter what a formula is made of.
 *
 * 🔴 THIS IS THE FORM THE PRODUCT WAS MISSING.
 *
 * `PUT /api/formulations/versions/{id}/components` has existed since Slice 3.
 * There was no client function for it, no hook and no control anywhere in the
 * application — so a person could create a formula and a version and never say
 * what was in it. Every derived figure on the version page (total percentage,
 * theoretical density, binder/filler ratio, cost, VOC) is computed FROM the
 * composition, so all of them were computing over nothing.
 *
 * A route with no caller, at the centre of a formulation platform.
 *
 * 🔴 PERCENTAGES ARE TEXT, START TO FINISH.
 *
 * `NUMERIC(9,4)` in PostgreSQL, `Decimal` in Pydantic, `string` on the wire and
 * `string` in this component's state. The API's own comment calls its field
 * "the one point where a number enters the system"; parsing to `number` here
 * would round 33.3333 on a controlled formulation share before the server saw
 * it, which §5 names as a defect rather than a rounding choice.
 *
 * The one place a number IS computed is the running total shown to the person
 * typing — and it is computed for DISPLAY only, never sent, never stored, and
 * clearly a guide rather than the server's answer. `total_percentage` comes
 * back from the server after saving, and that is the figure that counts.
 *
 * 🔴 IT REPLACES, IT DOES NOT PATCH.
 *
 * The server takes the WHOLE composition, because a formula is a set of lines
 * that must total 100% and every intermediate state of a partial update is
 * invalid. So this edits a local copy of every line and sends all of them.
 *
 * ⚠️ DRAFTS ONLY. `formula.modify_draft` gates the route, and the database
 * refuses the write on any other status — the trigger fires on the DELETE as
 * well as the INSERT, so even "clearing" an approved formula is refused. The
 * editor says so rather than letting somebody type a composition into a
 * released formula and be turned away at the end.
 */

import { useState } from "react";

import { CREATE_INPUT } from "@/components/ui/create-form";
import { serverMessage } from "@/lib/api/client";
import { useMaterials, useSetComposition } from "@/lib/api/hooks";
import type { ComponentLineRequest } from "@/lib/api/formulations";
import type { Material } from "@/lib/api/materials";
import { permits, usePermissions } from "@/lib/permissions";

/** A line being edited. `percentage` is text; see the header. */
interface Line {
  readonly key: string;
  material_id: string;
  percentage: string;
  notes: string;
}

let nextKey = 0;
function blankLine(): Line {
  nextKey += 1;
  return { key: `line-${nextKey}`, material_id: "", percentage: "", notes: "" };
}

export function CompositionEditor({
  versionId,
  status,
  existing,
}: {
  readonly versionId: string;
  readonly status: string;
  readonly existing: readonly {
    material_id: string;
    percentage: string;
    display_order: number;
  }[];
}) {
  const may = permits(usePermissions(), "formula.modify_draft");
  // 🔴 `[]` AS THE DEMONSTRATION FALLBACK, NOT THE DEMO MATERIAL LIST.
  //
  // `useMaterials` takes a demo value first. Handing it the synthetic
  // catalogue would offer a chemist materials that do not exist in their
  // tenant, and the FK would refuse the save at the end — a picker full of
  // choices that cannot be chosen. An empty list is the honest answer when
  // there is no API: the form then says there is nothing to pick.
  const materials = useMaterials<Material[]>([], (live) => live);
  const writes = useSetComposition(versionId);
  const [open, setOpen] = useState(false);
  const [lines, setLines] = useState<Line[]>([]);

  const isDraft = status === "draft";
  const materialRows = materials.data ?? [];

  function start() {
    // Seed from what is already there, in display order. Starting empty would
    // make "edit one line" mean "retype the whole formula", and the write is
    // wholesale — so an empty start is how a composition gets accidentally
    // truncated to the one line somebody meant to change.
    const seeded = [...existing]
      .sort((a, b) => a.display_order - b.display_order)
      .map((component) => ({
        ...blankLine(),
        material_id: component.material_id,
        percentage: component.percentage,
      }));
    setLines(seeded.length > 0 ? seeded : [blankLine()]);
    setOpen(true);
  }

  function update(key: string, patch: Partial<Line>) {
    setLines((current) =>
      current.map((line) => (line.key === key ? { ...line, ...patch } : line)),
    );
  }

  // 🔴 DISPLAY ONLY. Summed with `Number()` deliberately and never sent: this
  // is the guide a person needs while typing, and the SERVER's
  // `total_percentage` is the answer. Labelled as such on screen so the two
  // are not mistaken for one another.
  const runningTotal = lines.reduce((sum, line) => {
    const value = Number(line.percentage);
    return Number.isFinite(value) ? sum + value : sum;
  }, 0);

  const complete = lines.filter(
    (line) => line.material_id !== "" && line.percentage.trim() !== "",
  );

  if (!may) {
    return (
      <p className="mt-3 text-xs text-slate-600">
        Changing a composition needs the formula.modify_draft permission, which
        your roles do not hold. An engineer triggers a revision through a
        chemist rather than overwriting a composition — migration 002 withholds
        this permission from the engineer role deliberately.
      </p>
    );
  }

  if (!isDraft) {
    return (
      <p className="mt-3 text-xs text-slate-600">
        This version is <strong>{status}</strong>, so its composition is fixed.
        §8: an approved formula is never edited in place — clone it to a new
        draft and change that. The database refuses the write either way.
      </p>
    );
  }

  return (
    <div className="mt-3">
      {!open ? (
        <button
          type="button"
          className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100"
          onClick={start}
        >
          {existing.length === 0 ? "Enter composition" : "Edit composition"}
        </button>
      ) : (
        <form
          className="rounded border border-slate-200 bg-white p-4"
          onSubmit={(event) => {
            event.preventDefault();
            const payload: ComponentLineRequest[] = complete.map((line, index) => ({
              material_id: line.material_id,
              percentage: line.percentage.trim(),
              display_order: (index + 1) * 10,
              notes: line.notes.trim() === "" ? undefined : line.notes.trim(),
            }));
            writes.save(payload, () => setOpen(false));
          }}
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[36rem] text-left text-sm">
              <thead>
                <tr className="border-b border-slate-300 text-xs uppercase tracking-wide text-slate-600">
                  <th className="py-2 pr-3 font-medium">Material</th>
                  <th className="py-2 pr-3 font-medium">%</th>
                  <th className="py-2 pr-3 font-medium">Note</th>
                  <th className="py-2 font-medium sr-only">Remove</th>
                </tr>
              </thead>
              <tbody>
                {lines.map((line) => (
                  <tr key={line.key} className="border-b border-slate-100 align-top">
                    <td className="py-2 pr-3">
                      <label className="sr-only" htmlFor={`material-${line.key}`}>
                        Material
                      </label>
                      <select
                        id={`material-${line.key}`}
                        className={CREATE_INPUT}
                        required
                        value={line.material_id}
                        onChange={(event) =>
                          update(line.key, { material_id: event.target.value })
                        }
                      >
                        <option value="">
                          {materialRows.length === 0
                            ? "No materials available"
                            : "Choose a material…"}
                        </option>
                        {materialRows.map((material) => (
                          <option key={material.id} value={material.id}>
                            {material.material_code} — {material.name}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="py-2 pr-3">
                      <label className="sr-only" htmlFor={`pct-${line.key}`}>
                        Percentage
                      </label>
                      <input
                        id={`pct-${line.key}`}
                        className={`${CREATE_INPUT} tabular-nums`}
                        required
                        // `inputMode`, not `type="number"` — a number input
                        // hands back a coerced value and would undo the string
                        // discipline this whole file exists to keep.
                        inputMode="decimal"
                        placeholder="33.3333"
                        value={line.percentage}
                        onChange={(event) =>
                          update(line.key, { percentage: event.target.value })
                        }
                      />
                    </td>
                    <td className="py-2 pr-3">
                      <label className="sr-only" htmlFor={`note-${line.key}`}>
                        Note
                      </label>
                      <input
                        id={`note-${line.key}`}
                        className={CREATE_INPUT}
                        value={line.notes}
                        onChange={(event) => update(line.key, { notes: event.target.value })}
                      />
                    </td>
                    <td className="py-2">
                      <button
                        type="button"
                        className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-100"
                        onClick={() =>
                          setLines((current) =>
                            current.length === 1
                              ? current
                              : current.filter((row) => row.key !== line.key),
                          )
                        }
                        aria-label="Remove this component"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              type="button"
              className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100"
              onClick={() => setLines((current) => [...current, blankLine()])}
            >
              Add component
            </button>

            {/* 🔴 "as typed", AND THE WORDS MATTER. This is a browser sum shown
                to help somebody entering numbers. The version's real
                `total_percentage` is computed by the Python engine and shown in
                Derived properties; §4 keeps formulation arithmetic there, and a
                screen that presented this as the answer would be doing exactly
                what that rule forbids. */}
            <span className="text-xs text-slate-600 tabular-nums">
              Running total as typed: {runningTotal.toFixed(4)}% — the version&rsquo;s
              total is calculated by the engine after saving.
            </span>
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="submit"
              className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
              disabled={writes.isPending || complete.length === 0}
            >
              {writes.isPending ? "Saving…" : "Save composition"}
            </button>
            <button
              type="button"
              className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100"
              onClick={() => setOpen(false)}
            >
              Cancel
            </button>
          </div>

          {complete.length === 0 && (
            <p className="mt-2 text-xs text-slate-600">
              A formula needs at least one component with a material and a
              percentage.
            </p>
          )}

          {/* The server's own words: "the same material appears more than once",
              "version F-001-V2 is approved; clone it to a new draft", or the
              total-tolerance refusal. Each is a sentence written to be read. */}
          {writes.error !== null && (
            <p role="alert" className="mt-2 text-sm text-rose-700">
              {serverMessage(writes.error)}
            </p>
          )}
          {writes.error === null && writes.saved && (
            <p role="status" className="mt-2 text-sm text-slate-700">
              Composition saved. The engine totals it at {writes.saved.total_percentage}%.
            </p>
          )}
        </form>
      )}
    </div>
  );
}
