/**
 * @vitest-environment jsdom
 *
 * ⚠️ jsdom, and only for the last case. `returnToForSignIn` is pure and needs
 * nothing — but the assertion that MATTERS is that it and `readLanding()` work
 * as a PAIR, because the defect being guarded against is a preference with no
 * reader. Testing the pure function against a hand-written string would prove
 * the substitution happens and say nothing about whether the stored preference
 * ever reaches it. `vitest.config` runs `node` by default for speed and
 * documents this opt-in.
 *
 * The guard that keeps the landing preference from losing its reader again.
 *
 * 🔴 THIS FILE IS NAMED IN THREE COMMENTS. `app/page.tsx`,
 * `tests/e2e/shell/theme.spec.ts` and `tests/e2e/shell/navigation.spec.ts` all
 * point here for the coverage that moved when `/` stopped redirecting. If it
 * is deleted, those comments become claims about a test that does not exist —
 * the exact defect this repository has caught repeatedly.
 *
 * The behaviour it protects: `readLanding()` had NO reader once, while
 * Settings offered the choice and claimed it worked. The front-door redirect
 * became its reader; the front door is now a public page, so sign-in is its
 * reader. Remove the substitution and these go red.
 */

import { describe, expect, it } from "vitest";

import { returnToForSignIn } from "./return-to";
import { DEFAULT_LANDING, LANDING_SCREENS, readLanding } from "../preferences";

describe("returnToForSignIn", () => {
  it("substitutes the landing preference when signing in from the public root", () => {
    expect(returnToForSignIn("/", "/testing")).toBe("/testing");
  });

  it("falls back to the default when nothing has been chosen", () => {
    // The default must be unchanged for anybody who never opens Settings —
    // one of the three assertions that moved here from theme.spec.ts.
    expect(returnToForSignIn("/", DEFAULT_LANDING)).toBe(DEFAULT_LANDING);
  });

  it("does NOT substitute any other path", () => {
    // Sign in from a deep link and you land back on it. This is the behaviour
    // the substitution must not damage.
    for (const path of ["/dashboard", "/materials/RM-014", "/testing?tab=queue"]) {
      expect(returnToForSignIn(path, "/testing")).toBe(path);
    }
  });

  it("does not substitute a root path that carries a query string", () => {
    // `/?invite=abc` is a destination somebody linked to. Throwing the query
    // away would lose the caller's context on the one path where it is most
    // likely to matter.
    expect(returnToForSignIn("/?invite=abc", "/testing")).toBe("/?invite=abc");
  });

  it("never returns a path outside the offered screens when the root is substituted", () => {
    // 🔴 THE SUBSTITUTED VALUE IS ONLY EVER `readLanding()`, which validates
    // against the offered list. Asserted here because a preference read that
    // accepted any stored string would be an open redirect with a friendly
    // name — the third assertion that moved from theme.spec.ts.
    const offered = LANDING_SCREENS.map((screen) => screen.id);

    // A stored value that is a real page but NOT one of the three offered.
    window.localStorage.setItem("evercoat.landing", "/formulations");
    expect(offered).not.toContain("/formulations");
    expect(returnToForSignIn("/", readLanding())).toBe(DEFAULT_LANDING);

    // And a valid one is honoured, so the fallback above is not simply
    // "always the default".
    window.localStorage.setItem("evercoat.landing", "/testing");
    expect(returnToForSignIn("/", readLanding())).toBe("/testing");

    window.localStorage.removeItem("evercoat.landing");
  });
});
