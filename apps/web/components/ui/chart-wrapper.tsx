"use client";

/**
 * ChartWrapper — every chart in the application goes through here.
 *
 * The source is explicit that dashboards are the decision layer, not
 * decoration, and that every chart must drill down to real records. This
 * component enforces the parts that are easy to skip under deadline.
 *
 * Four rules it makes structural rather than advisory:
 *
 * 1. **A table view always exists.** Three of the validated series
 *    colours sit below 3:1 contrast on the light surface, which the
 *    palette method permits only under the "relief rule" — visible
 *    direct labels or a table view. It is also the only form a screen
 *    reader can actually read, and the only one that survives being
 *    printed in greyscale for a qualification dossier.
 *
 * 2. **A legend appears for two or more series.** Identity is never
 *    carried by colour alone. One series needs no legend — the title
 *    names it.
 *
 * 3. **No dual axis, ever.** `option.yAxis` being an array throws in
 *    development. Two y-scales on one plot let the author imply any
 *    correlation they like by choosing the scales, and lab-versus-pilot
 *    comparison is exactly the chart where someone will reach for it.
 *    Two charts, small multiples, or index to a common base.
 *
 * 4. **Empty is stated, not drawn.** An axis-only plot reads as "the
 *    values are zero" rather than "there is no data yet", and on a
 *    failures chart those mean opposite things.
 */

import ReactECharts from "echarts-for-react";
import { useMemo, useState, type ReactNode } from "react";

import { baseOption, type ThemeMode } from "./chart-theme";

export interface ChartTableColumn {
  key: string;
  label: string;
  numeric?: boolean;
}

export interface ChartWrapperProps {
  /** Names what the chart shows. Also the accessible name. */
  title: string;
  /** One sentence of interpretation: what this means, or what to do. */
  caption?: string;
  /** ECharts option, minus the theme — merged over `baseOption`. */
  option: Record<string, unknown>;
  /** Rows behind the chart. Required: see rule 1. */
  tableColumns: ChartTableColumn[];
  tableRows: Record<string, string | number | null>[];
  height?: number;
  mode?: ThemeMode;
  loading?: boolean;
  /** Where clicking through leads. Dashboards drill down to real records. */
  drillDownHref?: string;
  emptyMessage?: string;
}

export function ChartWrapper({
  title,
  caption,
  option,
  tableColumns,
  tableRows,
  height = 280,
  mode = "light",
  loading = false,
  drillDownHref,
  emptyMessage = "No data yet.",
}: ChartWrapperProps): ReactNode {
  const [showTable, setShowTable] = useState(false);

  const merged = useMemo(() => {
    if (process.env.NODE_ENV !== "production" && Array.isArray(option.yAxis)) {
      throw new Error(
        `ChartWrapper "${title}": dual-axis charts are not permitted. ` +
          "Two y-scales let the author imply any correlation they like by " +
          "choosing the scales. Use two charts, small multiples, or index " +
          "both series to a common base.",
      );
    }
    return { ...baseOption(mode), ...option };
  }, [option, mode, title]);

  const isEmpty = tableRows.length === 0;

  return (
    <figure className="rounded border border-slate-200 bg-white p-4">
      <figcaption className="mb-2 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
          {caption && (
            <p className="mt-0.5 text-[11px] leading-snug text-slate-500">{caption}</p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {!isEmpty && (
            <button
              type="button"
              onClick={() => setShowTable((v) => !v)}
              aria-pressed={showTable}
              className="rounded border border-slate-200 px-2 py-1 text-[11px] text-slate-600 hover:bg-slate-50"
            >
              {showTable ? "Chart" : "Table"}
            </button>
          )}
          {drillDownHref && (
            <a
              href={drillDownHref}
              className="rounded border border-slate-200 px-2 py-1 text-[11px] text-slate-600 hover:bg-slate-50"
            >
              Records
            </a>
          )}
        </div>
      </figcaption>

      {loading ? (
        <div
          className="animate-pulse rounded bg-slate-100"
          style={{ height }}
          aria-label={`${title} loading`}
        />
      ) : isEmpty ? (
        <div
          className="flex items-center justify-center rounded border border-dashed border-slate-300 text-sm text-slate-500"
          style={{ height }}
        >
          {emptyMessage}
        </div>
      ) : showTable ? (
        <ChartTable columns={tableColumns} rows={tableRows} caption={title} />
      ) : (
        <>
          <div role="img" aria-label={`${title}. Tabular data available via the Table button.`}>
            <ReactECharts
              option={merged}
              style={{ height }}
              opts={{ renderer: "svg" }}
              notMerge
            />
          </div>
          {/* The same numbers, always present for assistive technology,
              so the table button is a convenience rather than the only
              route to the data. */}
          <div className="sr-only">
            <ChartTable columns={tableColumns} rows={tableRows} caption={title} />
          </div>
        </>
      )}
    </figure>
  );
}

function ChartTable({
  columns,
  rows,
  caption,
}: {
  columns: ChartTableColumn[];
  rows: Record<string, string | number | null>[];
  caption: string;
}): ReactNode {
  return (
    <div className="max-h-72 overflow-auto">
      <table className="w-full border-collapse text-xs">
        <caption className="sr-only">{caption} — tabular data</caption>
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                scope="col"
                className={`sticky top-0 border-b border-slate-200 bg-white px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600 ${
                  c.numeric ? "text-right" : "text-left"
                }`}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-slate-100">
              {columns.map((c) => {
                const value = row[c.key];
                return (
                  <td
                    key={c.key}
                    className={`px-2 py-1 text-slate-700 ${
                      c.numeric ? "text-right tabular-nums" : ""
                    }`}
                  >
                    {value === null || value === undefined ? (
                      <>
                        <span aria-hidden>—</span>
                        <span className="sr-only">no value</span>
                      </>
                    ) : (
                      value
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
