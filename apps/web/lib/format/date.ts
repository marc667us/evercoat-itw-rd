/**
 * Dates, for the pipeline views.
 *
 * Owner instruction, 2026-08-30: *"include dates when pipeline item action is
 * taken — when innovation is added the view must have date added, when
 * requirement is defined the view must have date created, and so on across all
 * actions and events on the pipeline and views."*
 *
 * 🔴 BEFORE THIS FILE, THIS APPLICATION RENDERED NO DATE ANYWHERE.
 *
 * A repository-wide search for `toLocaleDateString`, `Intl.DateTimeFormat` and
 * `new Date(` found exactly two hits in the whole of `apps/web`, and neither
 * displayed anything: one compared a due date, one formatted money. Every
 * pipeline screen could say what STAGE a record was at and not when it got
 * there — which is precisely the complaint. The columns existed in PostgreSQL
 * the entire time; four of the five list endpoints simply never returned them.
 *
 * ⚠️ ONE FORMATTER, BECAUSE §12 SAYS SO.
 *
 * `CLAUDE.md` §12 forbids rebuilding shared infrastructure per module. If each
 * view formats its own date, they drift, and a pipeline that shows
 * `30/08/2026` on one screen and `8/30/2026` on the next reads as two systems.
 *
 * 🔴 UNKNOWN IS NOT TODAY, AND IT IS NOT AN EMPTY CELL EITHER.
 *
 * `null` renders as an explicit em dash with a title, never as a blank and
 * never as `Invalid Date`. A blank cell in a date column reads as "no date",
 * which is a claim; "—" reads as "not recorded", which is the truth. This is
 * the same discipline `newsAge` already applies in `public-client.ts`, where an
 * undated item is treated as stale rather than fresh.
 *
 * ⚠️ DAY PRECISION IN THE LIST, FULL TIMESTAMP IN THE TOOLTIP.
 *
 * These screens are dense (§11 calls them data-dense by design). A full
 * timestamp on every row is noise; the exact instant still matters when
 * someone is reconstructing what happened, so it lives in `title=` and is
 * therefore available without cluttering the row.
 */

/** A fixed, unambiguous rendering. `30 Aug 2026` cannot be read as a US or EU date. */
const DAY = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});

const INSTANT = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/**
 * What the API sends. Postgres `timestamptz` arrives as an ISO string, a plain
 * `date` arrives as `YYYY-MM-DD`, and a Pydantic model declared `object | None`
 * can hand back either — so the input type is deliberately wide and the
 * PARSING is what narrows it.
 */
export type DateInput = string | number | Date | null | undefined;

/**
 * A bare calendar date: `2026-11-30`, with no time and no zone.
 *
 * Anchored, not loose: `2026-11-30T14:00:00Z` must NOT match, because that one
 * is an instant and has to be treated as one.
 */
const CALENDAR_DATE = /^\d{4}-\d{2}-\d{2}$/;

function parse(value: DateInput): Date | null {
  if (value === null || value === undefined || value === "") return null;

  // 🔴 A CALENDAR DATE IS NOT AN INSTANT, AND TREATING IT AS ONE SHIFTS IT.
  //
  // This was a live off-by-one-day defect, found by the test below rather than
  // by reading the code. ECMAScript parses a bare `YYYY-MM-DD` as UTC
  // midnight; `Intl` then renders it in the VIEWER's zone. On this host
  // (America/Los_Angeles, UTC-7) `formatDay("2026-11-30")` returned
  // **29 Nov 2026**.
  //
  // `projects.target_release_date` is a plain `date` column and every
  // requirement, milestone and release target in this application is one. So
  // every such date would have displayed a day early for every user west of
  // UTC, and a day early on a release target is not a cosmetic error.
  //
  // A calendar date is therefore constructed in LOCAL time, so it renders as
  // the day it says regardless of where it is read. A `timestamptz` — an
  // actual instant — keeps the ordinary conversion, because for an instant
  // "when did this happen, in my time" is the correct question.
  if (typeof value === "string" && CALENDAR_DATE.test(value)) {
    // ⚠️ INDEXED READS ARE `number | undefined` UNDER THIS TSCONFIG, and the
    // compiler is right to insist: the regex above guarantees three parts, but
    // nothing in the TYPE system says so. Read explicitly rather than silenced
    // with `!` — a non-null assertion here would be a claim the compiler
    // cannot check, on the exact code path that renders release dates.
    const parts = value.split("-");
    const year = Number(parts[0]);
    const month = Number(parts[1]);
    const day = Number(parts[2]);
    const local = new Date(year, month - 1, day);
    // `new Date(2026, 12, 45)` silently ROLLS OVER instead of failing, so a
    // malformed date would render as a real-looking wrong day. Round-tripping
    // the parts is what makes `2026-13-45` reject rather than become 2027.
    if (
      local.getFullYear() !== year ||
      local.getMonth() !== month - 1 ||
      local.getDate() !== day
    ) {
      return null;
    }
    return local;
  }

  const parsed = value instanceof Date ? value : new Date(value);
  // 🔴 `new Date("not a date")` yields an Invalid Date rather than throwing,
  // and `Invalid Date`.toLocaleDateString() renders the literal string
  // "Invalid Date" into the page. Checked, not assumed.
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/** `30 Aug 2026`, or `—` when nothing was recorded. */
export function formatDay(value: DateInput): string {
  const parsed = parse(value);
  return parsed === null ? "—" : DAY.format(parsed);
}

/** `30 Aug 2026, 14:22` — the tooltip form. Empty when unknown, so no tooltip appears. */
export function formatInstant(value: DateInput): string {
  const parsed = parse(value);
  return parsed === null ? "" : INSTANT.format(parsed);
}

/** True when a real date was recorded. Used to decide whether to render an event at all. */
export function hasDate(value: DateInput): boolean {
  return parse(value) !== null;
}
