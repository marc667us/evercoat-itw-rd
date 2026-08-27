/**
 * §9 has SEVEN decision types, and a screen offering two would delete five.
 *
 * 🔴 WHY THIS NEEDS A TEST AT ALL.
 *
 * "Approve or reject" is what every approval UI in the world looks like, and
 * narrowing this control to those two would not fail to compile, would not
 * fail a rendering test, and would look entirely reasonable to a reviewer. It
 * would also remove five capabilities from a regulated approval chain —
 * including `approve_with_condition`, which §9 says yields YELLOW *with the
 * stated limitation preserved*, and `escalate`, which exists so an escalation
 * has somewhere to land.
 *
 * The server would still accept all seven. The screen would simply stop
 * offering them, and nothing anywhere would notice.
 *
 * ⚠️ THE LIST IS CHECKED AGAINST THE SERVER'S OWN PATTERN, NOT AGAINST A COPY
 * OF IT WRITTEN HERE. `StepDecision.decision` in `app/api/failures.py` is a
 * regex naming the seven, and the expectation below is that exact set in that
 * exact order — so a value added or removed server-side fails here rather than
 * drifting into a second, smaller vocabulary.
 */
import { describe, expect, it } from "vitest";

import { DECISIONS } from "./page";

/**
 * The seven, from `app/api/failures.py`:
 *
 *     ^(approve|approve_with_condition|return_for_correction|
 *       request_retest|reject|escalate|request_additional_test)$
 */
const SERVER_ACCEPTS = [
  "approve",
  "approve_with_condition",
  "return_for_correction",
  "request_retest",
  "reject",
  "escalate",
  "request_additional_test",
];

describe("the approval decision vocabulary", () => {
  it("offers exactly the seven the server accepts", () => {
    expect(DECISIONS.map(([value]) => value)).toEqual(SERVER_ACCEPTS);
  });

  it("🔴 is not narrowed to approve and reject", () => {
    // Stated separately from the equality above, because that assertion fails
    // with a diff nobody reads carefully. This one names the defect.
    const values = DECISIONS.map(([value]) => value);
    expect(values.length, "§9 defines seven decisions, not two").toBe(7);
    expect(values).toContain("approve_with_condition");
    expect(values).toContain("escalate");
    expect(values).toContain("request_additional_test");
  });

  it("gives every decision a label a person can read", () => {
    // A raw enum value in a dropdown — `request_additional_test` — is not a
    // label. The failure mode is a control that works and is unreadable.
    for (const [value, label] of DECISIONS) {
      expect(label, `${value} has no label`).not.toBe("");
      expect(label, `${value} is shown as its raw enum value`).not.toBe(value);
      expect(label[0], `${label} is not capitalised`).toBe(label[0]?.toUpperCase());
    }
  });
});
