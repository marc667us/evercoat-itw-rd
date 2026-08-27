/**
 * §9 has SEVEN decision types, and a screen offering two would delete five.
 *
 * 🔴 WHY THIS NEEDS A TEST AT ALL.
 *
 * "Approve or reject" is what every approval UI in the world looks like, and
 * narrowing this control to those two would not fail to compile, would not fail
 * a rendering test, and would look entirely reasonable to a reviewer. It would
 * also remove five capabilities from a regulated approval chain — including
 * `approve_with_condition`, which §9 says yields YELLOW *with the stated
 * limitation preserved*, and `escalate`, which exists so an escalation has
 * somewhere to land. The server would go on accepting all seven; the screen
 * would simply stop offering them, and nothing anywhere would notice.
 *
 * 🔴 AND IT READS THE SERVER'S OWN PATTERN, NOT A COPY OF IT.
 *
 * The first version of this file hand-copied the seven values into a
 * `SERVER_ACCEPTS` array under a comment claiming they came from the server.
 * Codex caught it: that compares one frontend constant with another, so a
 * backend change leaves the test green. It is the same defect the Supervisor
 * found in `context-submenu.test.ts` earlier the same day — repeated within
 * hours, in a different file, by the person who had just fixed it. *Two
 * literals in two files cannot be type-checked into agreement*, and writing
 * the second copy inside a test does not change that.
 *
 * So the pattern is parsed out of `apps/api/app/api/failures.py`, where
 * `StepDecision.decision` declares it. Reading across the tier boundary is
 * deliberate, for the reason `sections.catalogue.test.ts` reads the seed SQL:
 * the two halves live in two languages, and the only alternative to reading one
 * from the other is a third copy.
 *
 * ⚠️ THE PARSE IS ASSERTED BEFORE ANYTHING IS COMPARED TO IT. A regex that
 * matched nothing would yield an empty list, against which "the UI offers
 * exactly what the server accepts" is vacuously true.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { DECISIONS } from "./page";

/** Where `StepDecision.decision` declares the vocabulary. */
const ROUTES = join(process.cwd(), "..", "..", "apps", "api", "app", "api", "failures.py");

/**
 * The decisions the server's own pattern accepts.
 *
 * The `Field(pattern=...)` spans two source lines, so `[\s\S]` is used rather
 * than a line-bound match: a single-line regex would find only the first half
 * and this test would then "prove" the UI offers too many.
 */
function serverAccepts(): string[] {
  const source = readFileSync(ROUTES, "utf8");
  const decisionField = source.slice(source.indexOf("class StepDecision"));
  const pattern = /pattern="\^\(([\s\S]*?)\)\$"/.exec(decisionField);
  if (pattern === null || pattern[1] === undefined) {
    return [];
  }
  return pattern[1]
    .replace(/["\s]/g, "")
    .split("|")
    .filter((value) => value !== "");
}

describe("the approval decision vocabulary", () => {
  it("🔴 finds the server's pattern and reads seven values out of it", () => {
    // The guard on the guard. If `failures.py` moves, or the field becomes an
    // Enum, this fails HERE with a message naming the file — rather than
    // turning the comparison below into a match against nothing.
    const accepted = serverAccepts();

    expect(
      accepted.length,
      `read no decision values out of ${ROUTES} — the file moved or the Field pattern changed shape`,
    ).toBe(7);
    expect(accepted).toContain("approve_with_condition");
  });

  it("offers exactly what the server accepts, in its order", () => {
    expect(DECISIONS.map(([value]) => value)).toEqual(serverAccepts());
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
