"use client";

/**
 * The shared "create new" form shell.
 *
 * 🔴 WHY THIS EXISTS RATHER THAN NINE COPIES.
 *
 * `CLAUDE.md` §12 is explicit: do not rebuild infrastructure per module. Nine
 * pages needed a create form on the same day, and nine hand-rolled ones would
 * have produced nine spellings of "saving…", nine different error placements
 * and nine chances to forget the disabled state — which is exactly how the
 * status-colour rules drifted before they were centralised.
 *
 * 🔴 IT REFUSES TO RENDER A FORM NOBODY CAN SUBMIT.
 *
 * Every create route is permission-gated server-side. A form rendered to
 * somebody without the permission is a control that always 403s, and this
 * project's own rule is that a gate on an unused path is decoration: the
 * honest thing is to say who may do this, not to let a person fill in eight
 * fields and then be refused. `permission` is checked against the caller's
 * held set and the form is replaced by a sentence naming what is required.
 *
 * ⚠️ FRONTEND PERMISSION CHECKS ARE COSMETIC (§6) AND THIS IS NOT A CONTROL.
 * The server re-enforces every one of these. Hiding the form is a courtesy to
 * the reader, never the thing that keeps the endpoint safe.
 *
 * 🔴 AND IT IS COLLAPSED BY DEFAULT.
 *
 * These sit above a list somebody came to READ. An always-open eight-field
 * form pushes the content off the screen, which is how "create" gets in the
 * way of the ninety-nine percent of visits that are not creating anything.
 */

import { useId, useState, type ReactNode } from "react";

import { serverMessage } from "@/lib/api/client";
import { permits, usePermissions } from "@/lib/permissions";

export const CREATE_INPUT =
  "mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm text-slate-900 " +
  "focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";
export const CREATE_LABEL = "block text-xs font-medium text-slate-700";

export function CreateForm({
  title,
  permission,
  permissionLabel,
  submitLabel,
  onSubmit,
  isPending,
  error,
  done,
  disabled = false,
  children,
}: {
  /** "New material", "Open a failure investigation" — a verb and a noun. */
  readonly title: string;
  /** The permission the SERVER requires. Not a substitute for it. */
  readonly permission: string;
  /** How to say that permission to a person, if the code is opaque. */
  readonly permissionLabel?: string;
  readonly submitLabel: string;
  readonly onSubmit: () => void;
  readonly isPending: boolean;
  readonly error: Error | null;
  /** What to say after a successful create — usually the new record's code. */
  readonly done?: string | null;
  /** A reason this cannot be submitted yet, e.g. "no approved version". */
  readonly disabled?: false | string;
  readonly children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const permissions = usePermissions();
  const headingId = useId();

  // 🔴 `permits`, NOT `.has`, AND THE FALLBACK IS THE POINT.
  //
  // `usePermissions` hands an anonymous caller `ALL_NAV_PERMISSIONS` — the set
  // some nav item asks for — so a build with no identity provider still shows
  // its modules. That set contains no WRITE permissions, so an anonymous
  // reader is offered the pages and not the create controls inside them, which
  // is the right way round and is why this check needs no special case for
  // "not signed in".
  if (!permits(permissions, permission)) {
    return (
      <section
        aria-labelledby={headingId}
        className="rounded border border-slate-200 bg-white p-4"
      >
        <h3 id={headingId} className="text-sm font-semibold text-slate-900">
          {title}
        </h3>
        <p className="mt-1 text-xs text-slate-600">
          This needs the {permissionLabel ?? permission} permission, which your
          roles do not hold. Nothing is hidden from you here — the form is not
          shown because the server would refuse it.
        </p>
      </section>
    );
  }

  return (
    <section aria-labelledby={headingId} className="rounded border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-baseline gap-2">
        <h3 id={headingId} className="flex-1 text-sm font-semibold text-slate-900">
          {title}
        </h3>
        <button
          type="button"
          className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100"
          aria-expanded={open}
          onClick={() => setOpen((wasOpen) => !wasOpen)}
        >
          {open ? "Cancel" : title}
        </button>
      </div>

      {open && (
        <form
          className="mt-3"
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
        >
          <div className="grid gap-3 sm:grid-cols-2">{children}</div>

          {disabled !== false && (
            <p className="mt-2 text-xs text-amber-900">{disabled}</p>
          )}

          <button
            type="submit"
            className="mt-3 rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={isPending || disabled !== false}
          >
            {isPending ? "Saving…" : submitLabel}
          </button>

          {/* 🔴 THE SERVER'S OWN WORDS. `serverMessage` unwraps the API's
              `detail`, which for these routes is a domain sentence written to
              be read — "that material code is already used in this
              organization", not a constraint name. Replacing it with a generic
              "could not save" throws away the only part a person can act on. */}
          {error !== null && (
            <p role="alert" className="mt-2 text-sm text-rose-700">
              {serverMessage(error)}
            </p>
          )}
          {error === null && done && (
            <p role="status" className="mt-2 text-sm text-slate-700">
              {done}
            </p>
          )}
        </form>
      )}
    </section>
  );
}
