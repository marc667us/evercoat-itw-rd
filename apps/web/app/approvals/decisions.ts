/**
 * §9's seven decision types — its own module, and not by preference.
 *
 * 🔴 A `page.tsx` MAY NOT EXPORT ANYTHING BUT ITS PAGE, AND `tsc` DOES NOT SAY
 * SO. This constant lived in `page.tsx` and `npm run typecheck` was clean, lint
 * was clean, and 173 vitest tests passed. `next build` then refused it:
 *
 *     Type error: Property 'DECISIONS' is incompatible with index signature.
 *
 * Next.js generates its own validator for every route module, allowing only
 * `default`, `metadata`, `generateStaticParams` and a fixed list of others.
 * Nothing short of a real build runs that check — which is this project's
 * standing rule arriving as a measurement: *a green typecheck is not a working
 * build. Build it, run it, look.*
 *
 * The constant is exported because `decisions.test.ts` reads it and compares it
 * against the pattern in `app/api/failures.py`. Somewhere it had to live that a
 * test could import; that place is here.
 */

import type { StepDecisionRequest } from "@/lib/api/failures";

/**
 * §9's seven decisions, with the label a person reads.
 *
 * Exported so a test can assert there are seven of them. A control that
 * quietly offered two would not fail to compile, would not fail any rendering
 * test, and would remove five capabilities from a regulated approval chain.
 */
export const DECISIONS: ReadonlyArray<readonly [StepDecisionRequest["decision"], string]> = [
  ["approve", "Approve"],
  ["approve_with_condition", "Approve with condition"],
  ["return_for_correction", "Return for correction"],
  ["request_retest", "Request retest"],
  ["reject", "Reject"],
  ["escalate", "Escalate"],
  ["request_additional_test", "Request an additional test"],
];

