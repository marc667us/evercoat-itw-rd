"use client";

/**
 * The signed-in person's name, and what they can do about themselves.
 *
 * 🔴 THE APPLICATION HAS ALWAYS KNOWN THIS NAME AND HAD NOWHERE TO PUT IT.
 * `GET /api/me` returns `display_name` and `email` beside `organizations`, and
 * the auth provider parsed only the organizations — so the top bar showed a
 * grey circle containing a dash while the browser held "Esi Lead" in memory.
 *
 * Navigation narrative §2 puts the user profile at the end of the global bar:
 * *Organization Selector | Global Search | Quick Create | MSD | Notifications |
 * Help | User Profile*. This sits between Alerts and Help, which is where the
 * person asking for it wanted it and is a difference of one position from §2.
 *
 * ⚠️ SIGNED OUT, IT OFFERS NOTHING AND SAYS NOTHING. `AccountMenu` at the other
 * end of the bar already owns "you are not signed in" and the Sign in control;
 * a second, quieter version of that message here would be two components
 * disagreeing about how to say the same thing.
 */

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { profileInitials, profileLabel, useAuth } from "@/components/providers/auth-provider";

/** The three things a person can do about their own account. */
const ITEMS = [
  { href: "/account/profile", label: "Profile", hint: "Who you are here, and what you may do" },
  { href: "/account/settings", label: "Settings", hint: "Theme, and where the application opens" },
  { href: "/account/security", label: "Security", hint: "Your session, password and sign-out" },
] as const;

export function UserMenu() {
  const { profile } = useAuth();
  const [open, setOpen] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const firstItem = useRef<HTMLAnchorElement>(null);

  // 🔴 CLOSES ON OUTSIDE CLICK **AND** ON ESCAPE. A menu that only closes by
  // clicking its own trigger is a keyboard trap: tab into it, and the only way
  // out is the mouse. Escape is the expected key and costs one listener.
  useEffect(() => {
    if (!open) return;

    const onPointer = (event: MouseEvent) => {
      if (container.current !== null && !container.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      // 🔴 AND FOCUS GOES BACK TO THE TRIGGER.
      //
      // ⚠️ AN EARLIER VERSION OF THIS COMMENT DESCRIBED A HISTORY THAT COULD
      // NOT HAVE HAPPENED — that Escape "used to leave focus on an element
      // just removed from the document, so a keyboard user was returned to the
      // top of the page". Before the effect below, focus never ENTERED the
      // menu, so there was nothing to restore and Escape lost nothing. The
      // Supervisor found it. The restore is still correct: it is the other
      // half of moving focus in on open, and without it Escape would now be
      // the thing that drops focus to `<body>`.
      trigger.current?.focus();
    };

    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // 🔴 OPENING A MENU MOVES FOCUS INTO IT. Without this the menu appeared and
  // focus stayed on the trigger, so a screen reader announced a menu the user
  // then had to hunt for, and the next Tab left it entirely. This is the other
  // half of the Escape behaviour above: focus enters on open and returns on
  // close, which is what `aria-haspopup="menu"` promises.
  useEffect(() => {
    if (open) firstItem.current?.focus();
  }, [open]);

  if (profile === null) {
    return null;
  }

  // 🔴 THE LABEL IS NEVER AN EMPTY STRING, AND THE MENU IS NEVER WITHHELD.
  //
  // A blank `display_name` used to remove the profile entirely, which removed
  // this component — and with it the only route in the shell to Settings,
  // Profile and Sign out. See `activeProfile`. What a missing name costs now is
  // the name.
  const label = profileLabel(profile);
  const initials = profileInitials(profile);

  return (
    <div ref={container} className="relative">
      <button
        ref={trigger}
        type="button"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((was) => !was)}
        className="flex items-center gap-2 rounded px-2.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 hover:text-slate-900"
      >
        <span
          aria-hidden
          className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-slate-200 text-[10px] font-semibold text-slate-700"
        >
          {/* Initials, and only as decoration — the label itself is beside it,
              so this never has to be the thing a reader relies on. With no name
              to take them from it stays empty rather than showing a "?", which
              would state something the application does not mean. */}
          {initials}
        </span>
        <span className="max-w-[10rem] truncate">{label}</span>
        <span aria-hidden className="text-[10px] text-slate-500">
          {open ? "▲" : "▼"}
        </span>
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Your account"
          className="absolute right-0 z-50 mt-1 w-72 rounded border border-slate-200 bg-white p-1 shadow-lg"
        >
          <div className="border-b border-slate-200 px-3 py-2">
            <p className="truncate text-sm font-medium text-slate-900">{label}</p>
            {/* The address this ORGANIZATION knows them by. Migration 052 moved
                it onto the membership, so it is not a global identity. */}
            {/* Not when it is already the label — an address printed twice,
                once as a name, reads as a duplicated element rather than as a
                person with no name on file. */}
            {profile.email.trim() !== "" && profile.email.trim() !== label && (
              <p className="truncate text-xs text-slate-600">{profile.email}</p>
            )}
          </div>

          {ITEMS.map((item, index) => (
            <Link
              key={item.href}
              ref={index === 0 ? firstItem : undefined}
              href={item.href}
              role="menuitem"
              onClick={() => setOpen(false)}
              className="block rounded px-3 py-2 hover:bg-slate-50"
            >
              <span className="block text-sm font-medium text-slate-900">{item.label}</span>
              {/* A line of what it does, not a restatement of the label. Three
                  bare words in a menu make a reader open all three to find out
                  which one they wanted. */}
              <span className="block text-xs text-slate-600">{item.hint}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
