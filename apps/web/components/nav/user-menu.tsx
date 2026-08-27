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

import { useAuth } from "@/components/providers/auth-provider";

/** The three things a person can do about their own account. */
const ITEMS = [
  { href: "/account/profile", label: "Profile", hint: "Who you are here, and what you may do" },
  { href: "/account/settings", label: "Settings", hint: "Theme, and where you land after signing in" },
  { href: "/account/security", label: "Security", hint: "Your session, password and sign-out" },
] as const;

export function UserMenu() {
  const { profile } = useAuth();
  const [open, setOpen] = useState(false);
  const container = useRef<HTMLDivElement>(null);

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
      if (event.key === "Escape") setOpen(false);
    };

    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (profile === null) {
    return null;
  }

  return (
    <div ref={container} className="relative">
      <button
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
          {/* Initials, and only as decoration — the name itself is beside it,
              so this never has to be the thing a reader relies on. */}
          {profile.displayName
            .split(/\s+/)
            .slice(0, 2)
            .map((part) => part.charAt(0).toUpperCase())
            .join("")}
        </span>
        <span className="max-w-[10rem] truncate">{profile.displayName}</span>
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
            <p className="truncate text-sm font-medium text-slate-900">{profile.displayName}</p>
            {/* The address this ORGANIZATION knows them by. Migration 052 moved
                it onto the membership, so it is not a global identity. */}
            <p className="truncate text-xs text-slate-600">{profile.email}</p>
          </div>

          {ITEMS.map((item) => (
            <Link
              key={item.href}
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
