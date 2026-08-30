/**
 * The dates on a pipeline record, rendered the same way on every screen.
 *
 * Owner instruction, 2026-08-30: every action and event on the pipeline must
 * show when it happened — added, created, defined, decided, executed, started,
 * completed.
 *
 * 🔴 WHY A COMPONENT AND NOT A `formatDay()` CALL PER SCREEN.
 *
 * `CLAUDE.md` §12 lists the shared infrastructure that must not be rebuilt per
 * module, and the reason is on display in this repository's own history: the
 * same idea implemented five times drifts five ways. There are five pipeline
 * list views and a workspace; if each writes its own `<p>Created: …</p>`, the
 * label, the separator, the tooltip and the null case all diverge, and a user
 * moving Opportunity → Project → Requirement → Batch → Test sees four
 * different conventions for the same fact.
 *
 * ⚠️ AN EVENT WITH NO DATE IS NOT RENDERED AT ALL.
 *
 * Only events that actually happened appear. A batch that has not started
 * shows no "Started" at all rather than "Started —", because an em dash beside
 * a label the record has not reached implies the step was attempted and not
 * recorded. That is a different and worse claim than silence.
 *
 * This mirrors rule 10's discipline elsewhere in the product: never let a
 * display imply a state the record is not in.
 *
 * ⚠️ THE FIRST EVENT ALWAYS RENDERS, even when undated.
 *
 * `required` marks the creation event. A record that exists was created at
 * some point, so if that timestamp is missing the view says "—" rather than
 * hiding it: a missing creation date is a DATA problem worth seeing, not a
 * step that has not happened yet.
 */

import { formatDay, formatInstant, hasDate, type DateInput } from "@/lib/format/date";

export interface PipelineEvent {
  /** What happened. "Added", "Defined", "Decided", "Executed", "Completed". */
  label: string;
  at: DateInput;
  /** Render even when undated — true for the creation event. See the header. */
  required?: boolean;
}

export function EventDates({
  events,
  className = "",
}: {
  events: PipelineEvent[];
  className?: string;
}) {
  const shown = events.filter((event) => event.required === true || hasDate(event.at));
  if (shown.length === 0) return null;

  return (
    // A definition list, because these ARE label/value pairs — a screen reader
    // announcing "Added, 30 August 2026" is the point. §11 requires
    // screen-reader semantics, not merely visible text.
    <dl className={`mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600 ${className}`}>
      {shown.map((event) => {
        const exact = formatInstant(event.at);
        return (
          <div key={event.label} className="flex gap-1">
            <dt className="font-medium">{event.label}</dt>
            {/* `title` carries the exact instant. It is omitted rather than set
                to "" when unknown, so no empty tooltip appears on hover. */}
            <dd {...(exact === "" ? {} : { title: exact })}>{formatDay(event.at)}</dd>
          </div>
        );
      })}
    </dl>
  );
}
