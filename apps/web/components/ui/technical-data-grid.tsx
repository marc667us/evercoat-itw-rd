"use client";

/**
 * TechnicalDataGrid — the shared grid for every technical table.
 *
 * Formulation sheets, raw-material libraries, batch quantities, test
 * results, DOE matrices, stability measurements, QC specifications and
 * qualification matrices all behave more like spreadsheets than web
 * pages. They get one grid, not eight.
 *
 * TanStack Table + Virtual, never AG Grid: Enterprise is commercial and
 * the zero-cost rule is mandatory (ADR-005).
 *
 * Two domain rules are enforced here rather than left to callers:
 *
 * 1. **Numeric columns are right-aligned and tabular-figured.** A column
 *    of formulation percentages where 8.5 and 12.25 do not line up at the
 *    decimal is genuinely harder to scan for the error, and scanning for
 *    the error is the entire job.
 *
 * 2. **Empty is not zero.** A missing measurement renders as an em dash,
 *    never as 0. "We did not measure it" and "we measured zero" are
 *    different facts, and conflating them in a test result is a data
 *    integrity failure, not a formatting choice.
 */

import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useRef, useState, type ReactNode } from "react";

export interface TechnicalDataGridProps<T> {
  data: T[];
  columns: ColumnDef<T, unknown>[];
  /** Shown when data is empty. Say what would put rows here. */
  emptyMessage?: string;
  loading?: boolean;
  /** Row height in px. Virtualization needs a fixed estimate. */
  rowHeight?: number;
  /** Above this many rows, switch to virtualized rendering. */
  virtualizeAbove?: number;
  onRowClick?: (row: T) => void;
  caption?: string;
}

export function TechnicalDataGrid<T>({
  data,
  columns,
  emptyMessage = "No records.",
  loading = false,
  rowHeight = 36,
  virtualizeAbove = 100,
  onRowClick,
  caption,
}: TechnicalDataGridProps<T>): ReactNode {
  const [sorting, setSorting] = useState<SortingState>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const rows = table.getRowModel().rows;
  const virtualize = rows.length > virtualizeAbove;

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => rowHeight,
    overscan: 12,
    enabled: virtualize,
  });

  if (loading) {
    return (
      <div className="rounded border border-slate-200 bg-white p-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="mb-2 h-6 animate-pulse rounded bg-slate-100" />
        ))}
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="rounded border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
        {emptyMessage}
      </div>
    );
  }

  const virtualRows = virtualize ? virtualizer.getVirtualItems() : null;

  return (
    // overflow-x-auto on the wrapper, so a 20-column DOE matrix scrolls
    // inside its own container instead of making the whole page scroll
    // sideways.
    <div
      ref={scrollRef}
      className="max-h-[70vh] overflow-auto rounded border border-slate-200 bg-white"
    >
      <table className="w-full border-collapse text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead className="sticky top-0 z-10 bg-slate-50">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((header) => {
                const sortable = header.column.getCanSort();
                const dir = header.column.getIsSorted();
                return (
                  <th
                    key={header.id}
                    scope="col"
                    aria-sort={
                      dir === "asc"
                        ? "ascending"
                        : dir === "desc"
                          ? "descending"
                          : sortable
                            ? "none"
                            : undefined
                    }
                    className="whitespace-nowrap border-b border-slate-200 px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-600"
                  >
                    {sortable ? (
                      <button
                        type="button"
                        onClick={header.column.getToggleSortingHandler()}
                        className="flex items-center gap-1 hover:text-slate-900"
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        <span aria-hidden className="text-slate-400">
                          {dir === "asc" ? "▲" : dir === "desc" ? "▼" : "⇅"}
                        </span>
                      </button>
                    ) : (
                      flexRender(header.column.columnDef.header, header.getContext())
                    )}
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>

        <tbody>
          {(virtualRows ?? rows.map((_, i) => ({ index: i, start: 0, size: 0 }))).map(
            (v) => {
              const row = rows[v.index];
              if (!row) return null;
              return (
                <tr
                  key={row.id}
                  onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                  className={[
                    "border-b border-slate-100",
                    onRowClick ? "cursor-pointer hover:bg-slate-50" : "",
                  ].join(" ")}
                  style={
                    virtualize
                      ? { height: `${v.size}px`, transform: `translateY(${v.start}px)` }
                      : undefined
                  }
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-3 py-1.5 text-slate-700">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              );
            },
          )}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Numeric cell.
 *
 * Renders an em dash for null/undefined — never 0. In a test result,
 * "not measured" and "measured zero" are different facts, and a grid that
 * shows 0 for both has quietly destroyed the distinction.
 */
export function NumericCell({
  value,
  decimals = 2,
  unit,
}: {
  value: number | null | undefined;
  decimals?: number;
  unit?: string;
}): ReactNode {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return (
      <span className="block text-right tabular-nums text-slate-400">
        <span aria-hidden>—</span>
        <span className="sr-only">not measured</span>
      </span>
    );
  }
  return (
    <span className="block text-right tabular-nums">
      {value.toFixed(decimals)}
      {unit && <span className="ml-1 text-slate-400">{unit}</span>}
    </span>
  );
}
