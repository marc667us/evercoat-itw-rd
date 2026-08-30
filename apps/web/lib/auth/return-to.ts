/**
 * Where sign-in sends you back to.
 *
 * 🔴 EXTRACTED SO IT CAN BE TESTED, AND BECAUSE IT CARRIES A REAL DECISION.
 *
 * `signIn` stores "where you were" and the callback returns there, which is
 * right everywhere in the application: sign in from a deep link and you land
 * back on it.
 *
 * `/` is the one place that is wrong. It is the PUBLIC landing page now — the
 * marketplace and the news feed — not a screen anybody meant to be working on.
 * Returning there after a successful sign-in would deposit the visitor back on
 * the page they signed in to get past.
 *
 * ⚠️ AND IT IS WHAT KEEPS THE LANDING PREFERENCE ALIVE. `readLanding()` was
 * once written by Settings, validated on the way out, and read by NOTHING —
 * both reviewers found it, and it is this project's own rule about a setting
 * with no enforcement point. The redirect on `/` used to be its reader. This
 * function is its reader now, and `return-to.test.ts` is the guard that goes
 * red if the substitution is removed.
 */

/** The bare public front door. Only this exact path is substituted. */
const PUBLIC_ROOT = "/";

/**
 * The path sign-in should return to.
 *
 * @param current  `pathname + search` at the moment sign-in was pressed.
 * @param landing  The validated landing preference, from `readLanding()`.
 *
 * A path carrying a query string is a real destination somebody linked to and
 * is never substituted, even at the root — `/?invite=abc` means something and
 * throwing it away would lose the caller's context.
 */
export function returnToForSignIn(current: string, landing: string): string {
  return current === PUBLIC_ROOT ? landing : current;
}
