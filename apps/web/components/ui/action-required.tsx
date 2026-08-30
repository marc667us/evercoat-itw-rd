/**
 * "Action required — and by whom."
 *
 * Owner instruction, 2026-08-30: *"all new innovation upload must have red
 * button indicate action required by who must action."*
 *
 * 🔴 THE SCREEN SAID WHAT STATE AN IDEA WAS IN AND NEVER WHO WAS HOLDING IT.
 *
 * An opportunity sat in `awaiting_decision` and the card said
 * "awaiting_decision". True, and useless: the person reading it could not tell
 * whether they were the blocker or waiting on somebody else, so an idea
 * uploaded from the marketplace could sit for a week with everyone assuming it
 * was on someone else's desk.
 *
 * ⚠️ RED, PLUS AN ICON, PLUS WORDS — NEVER RED ALONE.
 *
 * `CLAUDE.md` §11 forbids colour-only status and §10 spells out why: pass and
 * fail measure deltaE 4.2 under deuteranopia, so roughly 8% of men cannot
 * separate the traffic-light hues by hue at all. A red button that is only red
 * carries no information for them. Every marker here renders `●` + the role +
 * the verb, and would still say everything it needs to in greyscale.
 *
 * ⚠️ IT USES `status-fail`, THE DOMAIN TOKEN, NOT A RAW `red-600`.
 *
 * The traffic-light tokens are validated for contrast and MOVE WITH THE THEME —
 * held fixed they measured as low as 2.25 on the dark surface, below AA. A
 * hand-picked red would be an unvalidated colour on the one theme most likely
 * to be used late in the day, and would not survive the theme guard.
 *
 * 🔴 THE ROLE NAMES ARE MEASURED FROM THE SEED, NOT GUESSED — see
 * `action-required.drift.test.ts`, which reads `002_seed_roles_permissions.sql`
 * and fails if a permission moves to a different role. Naming the wrong role
 * on a red banner is worse than naming none: it sends people to someone who
 * cannot act, and they have no reason to doubt it.
 */

/** A permission, and the role the seed actually grants it to. */
export interface Actionable {
  /** The permission the server gates the act on. */
  permission: string;
  /** The role that holds it, as `002_seed_roles_permissions.sql` grants it. */
  role: string;
  /** What that person must do. A verb phrase: "decide it", "submit it". */
  verb: string;
}

/**
 * The red marker. Rendered ONLY when something is genuinely blocked on a
 * person — never as decoration on a row that is simply in progress.
 */
export function ActionRequired({ on, className = "" }: { on: Actionable; className?: string }) {
  return (
    <p
      // `role="status"` and not `alert`: this is a standing condition on a
      // list row, not an interruption. An alert on every blocked card would
      // make a screen reader announce the whole list as urgent.
      role="status"
      className={`mt-2 flex flex-wrap items-center gap-1.5 text-xs font-medium text-status-fail ${className}`}
    >
      <span aria-hidden="true">●</span>
      <span>Action required — {on.role} must {on.verb}.</span>
    </p>
  );
}

/**
 * The button classes for the act that is currently blocking a record.
 *
 * ⚠️ ONE BUTTON PER CARD CARRIES THIS. If every control were red, red would
 * mean "button" rather than "this is the one waiting on you", and the marker
 * above would be the only thing left saying anything.
 */
export const ACTION_REQUIRED_BUTTON =
  "rounded border-2 border-status-fail px-3 py-1.5 text-sm font-semibold " +
  "text-status-fail hover:bg-status-fail hover:text-white " +
  "disabled:cursor-not-allowed disabled:border-slate-300 disabled:text-slate-400 " +
  "disabled:hover:bg-transparent";
