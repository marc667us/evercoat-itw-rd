/**
 * What an investigation row needs somebody to do next.
 *
 * 🔴 ITS OWN MODULE BECAUSE A `page.tsx` MAY NOT EXPORT ANYTHING BUT ITS PAGE,
 * and `tsc --noEmit` does not enforce that — only `next build` does. See
 * `app/approvals/decisions.ts` for the measurement; both constants were caught
 * by the same failed build, after a clean typecheck, a clean lint and 173
 * passing tests.
 *
 * Exported because `next-step.test.ts` pins its ORDER, which is the only thing
 * about it that can be wrong.
 */

import type { FailureSummary } from "@/lib/api/failures";

/**
 * What this row needs somebody to do, in words.
 *
 * 🔴 DERIVED FROM COUNTS THE SERVER RETURNED, AND NOTHING ELSE. Each branch
 * restates a fact already on the row; none of them decides whether the
 * investigation is going well. "No hypothesis yet" is a count of zero said in
 * English — it is not a criticism, and it is not a status.
 *
 * ⚠️ ORDERED, first match wins, because more than one can be true at once. An
 * investigation with an accepted root cause and three open actions is waiting
 * on the ACTIONS; saying "root cause accepted" and stopping would read as
 * finished work.
 */
export function nextStep(row: FailureSummary): string {
  // 🔴 SIX STATUSES, NOT TWO. Raised by Codex. `quality.failures.status` is
  // CHECKed against open · investigating · root_cause_accepted ·
  // action_in_progress · closed · cancelled (migration 021), and this rule
  // recognised only `closed` — so a CANCELLED investigation was described as
  // needing a hypothesis and offered mutation controls that then 409'd.
  //
  // Both are SETTLED and neither needs work, but they are not the same
  // sentence: "closed" means somebody concluded it, "cancelled" means nobody
  // will. Collapsing them would lose the difference a reader is looking for.
  if (row.status === "closed") {
    return "Closed";
  }
  if (row.status === "cancelled") {
    return "Cancelled";
  }
  if (row.open_actions > 0) {
    return `${row.open_actions} corrective action${row.open_actions === 1 ? "" : "s"} open`;
  }
  if (row.has_root_cause) {
    return "Root cause accepted — no open actions";
  }
  if (row.hypothesis_count === 0) {
    return "No hypothesis yet";
  }
  return `${row.hypothesis_count} hypothes${row.hypothesis_count === 1 ? "is" : "es"}, none accepted`;
}
