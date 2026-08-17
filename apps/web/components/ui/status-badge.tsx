/**
 * StatusBadge — the traffic light.
 *
 * This is the most consequential component in the application, so the
 * rules it enforces are structural rather than conventional.
 *
 * 1. **Colour is never the only indicator.** Every badge renders colour +
 *    icon + text. Reports get printed in greyscale and roughly 1 in 12
 *    men has a colour-vision deficiency; a green dot alone communicates
 *    nothing to either. axe-core enforces the contrast side in CI, but no
 *    linter can catch "the meaning was only in the hue" — so the icon and
 *    text are not optional props.
 *
 * 2. **GREEN is authority-qualified.** A passing screening test and a
 *    passing release-authority test must never look identical. Screening
 *    is not qualification evidence, and a bare green tick invites exactly
 *    that confusion (Codex F10/F30).
 *
 * 3. **Every YELLOW states why and what is next.** A yellow with no
 *    reason is a defect, not a status — the whole point of the state is
 *    that something specific is blocking a conclusion.
 *
 * 4. **Status is derived, never passed as a colour.** The component takes
 *    the domain state and computes the presentation. Accepting a
 *    `color="green"` prop would let a caller paint an unapproved result
 *    green, which is the single failure this design exists to prevent.
 */

import type { ReactNode } from "react";

/** Server-derived display status. Mirrors the SQL derivation exactly. */
export type DisplayStatus = "green" | "red" | "yellow" | "neutral";

/** Test authority, so GREEN can say how much it is worth. */
export type AuthorityLevel =
  | "preliminary"
  | "development"
  | "controlled"
  | "validation"
  | "qualification"
  | "release";

export interface StatusBadgeProps {
  status: DisplayStatus;
  /** Short label, e.g. "PASS", "FAIL", "AWAITING LEAD APPROVAL". */
  label: string;
  /**
   * Why this status, and what happens next.
   *
   * REQUIRED for yellow — TypeScript enforces it via the union below, so
   * an unexplained yellow cannot be written in the first place.
   */
  reason?: string;
  authority?: AuthorityLevel;
  size?: "sm" | "md";
}

/**
 * A yellow badge must carry a reason. This makes rule 3 a compile error
 * rather than a code-review comment.
 */
export type StatusBadgeInput =
  | (Omit<StatusBadgeProps, "status" | "reason"> & {
      status: "yellow";
      reason: string;
    })
  | (Omit<StatusBadgeProps, "status"> & {
      status: Exclude<DisplayStatus, "yellow">;
    });

const PRESENTATION: Record<
  DisplayStatus,
  { icon: string; classes: string; srPrefix: string }
> = {
  green: {
    icon: "✓",
    classes: "bg-emerald-50 text-status-pass border-emerald-200",
    srPrefix: "Successful",
  },
  red: {
    icon: "✕",
    classes: "bg-red-50 text-status-fail border-red-200",
    srPrefix: "Failed",
  },
  yellow: {
    icon: "!",
    classes: "bg-amber-50 text-status-conditional border-amber-200",
    srPrefix: "Conditional",
  },
  neutral: {
    icon: "•",
    classes: "bg-slate-50 text-status-neutral border-slate-200",
    srPrefix: "Status",
  },
};

/** Authority levels that do NOT constitute confirmed evidence. */
const PRELIMINARY_AUTHORITIES: ReadonlySet<AuthorityLevel> = new Set([
  "preliminary",
  "development",
]);

export function StatusBadge(props: StatusBadgeInput): ReactNode {
  const { status, label, authority, size = "md" } = props;
  const reason = "reason" in props ? props.reason : undefined;
  const presentation = PRESENTATION[status];

  // A green result at preliminary authority is qualified inline, so it
  // can never be read as confirmation evidence at a glance.
  const qualifier =
    status === "green" && authority && PRELIMINARY_AUTHORITIES.has(authority)
      ? ` (${authority})`
      : "";

  return (
    <span className="inline-flex flex-col gap-0.5">
      <span
        className={[
          "inline-flex w-fit items-center gap-1.5 rounded border font-medium",
          presentation.classes,
          size === "sm" ? "px-1.5 py-0.5 text-[11px]" : "px-2 py-1 text-xs",
        ].join(" ")}
      >
        {/* aria-hidden: the icon is decorative because the text below
            carries the same meaning. Announcing "✓" adds noise. */}
        <span aria-hidden className="font-bold">
          {presentation.icon}
        </span>
        <span>
          {label}
          {qualifier}
        </span>
        {/* Screen readers get the full sentence, including the reason,
            without it being visually duplicated. */}
        <span className="sr-only">
          {presentation.srPrefix}
          {reason ? `. ${reason}` : ""}
        </span>
      </span>

      {reason && (
        <span className="text-[11px] leading-tight text-slate-500">{reason}</span>
      )}
    </span>
  );
}

/**
 * Test results carry two facts that one badge cannot express: what the
 * measurement said, and whether the organization has accepted it.
 *
 * "6.1 MPa passed the ≥6.0 requirement" and "the Lead has not approved"
 * are both true simultaneously. Collapsing them into a single yellow
 * badge loses the first; collapsing into green loses the second and is
 * the exact failure rule 6 forbids. So both are shown, always.
 */
export function TestResultStatus({
  calculatedResult,
  displayStatus,
  finalLabel,
  reason,
  authority,
}: {
  calculatedResult: string;
  displayStatus: DisplayStatus;
  finalLabel: string;
  reason?: string;
  authority?: AuthorityLevel;
}): ReactNode {
  return (
    <dl className="flex flex-col gap-2">
      <div className="flex items-baseline gap-2">
        <dt className="text-[11px] uppercase tracking-wide text-slate-500">
          Automatic evaluation
        </dt>
        <dd className="text-xs font-medium text-slate-700">{calculatedResult}</dd>
      </div>
      <div className="flex items-baseline gap-2">
        <dt className="text-[11px] uppercase tracking-wide text-slate-500">
          Final disposition
        </dt>
        <dd>
          {displayStatus === "yellow" ? (
            <StatusBadge
              status="yellow"
              label={finalLabel}
              reason={reason ?? "Awaiting review"}
              authority={authority}
            />
          ) : (
            <StatusBadge
              status={displayStatus}
              label={finalLabel}
              reason={reason}
              authority={authority}
            />
          )}
        </dd>
      </div>
    </dl>
  );
}
