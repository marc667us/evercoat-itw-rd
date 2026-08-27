"use client";

/**
 * What this person prefers — theme, and where the application opens.
 *
 * 🔴 STORED IN THE BROWSER, AND THAT IS A DECISION RATHER THAN A SHORTCUT.
 *
 * There is no user-preference endpoint, and inventing one would mean a
 * migration, a table, a route and a permission for something that is not a
 * technical record. §1 is explicit that PostgreSQL owns *verified technical
 * facts*; a colour scheme is not one, and putting it in the same database as
 * formula compositions would be the beginning of treating it like one.
 *
 * ⚠️ SO IT DOES NOT FOLLOW THE PERSON BETWEEN MACHINES, and the settings screen
 * says so. That is the honest trade, not an omission — the alternative is a
 * server round trip on every page load to decide a colour.
 *
 * 🔴 AND `localStorage` IS SAFE FOR THIS AND WOULD NOT BE FOR A TOKEN.
 * `lib/api/session.ts` records the rule: an access token in `localStorage` is
 * readable by any script on the origin, so one XSS becomes a stolen session
 * that outlives the page. A theme is not a credential. The distinction is the
 * whole reason this file may use storage and that one may not.
 */

import { useCallback, useEffect, useState } from "react";

import { DEFAULT_THEME, THEME_STORAGE_KEY, isThemeId, type ThemeId } from "./theme";

// 🔴 IMPORTED, NOT REPEATED. The pre-paint script in `app/layout.tsx` reads the
// same key before this module exists, and two spellings of a storage key cannot
// be type-checked into agreement — the reader would simply find nothing and
// paint the default, forever, with every test green.
const THEME_KEY = THEME_STORAGE_KEY;
const LANDING_KEY = "evercoat.landing";

/**
 * Where the application opens.
 *
 * Three, and each is a real destination that exists today — a preference
 * pointing at an unbuilt screen would be a setting whose only effect is a 404.
 *
 * 🔴 ITS READER IS `app/page.tsx`, AND FOR A WHILE IT HAD NONE. The front door
 * redirected to a hard-coded `/dashboard`, so this value was written by the
 * settings screen, validated on the way back out, and consulted by nothing.
 * Both reviewers found it. Because `/` resolves here before anybody presses
 * Sign in, it is also what sign-in returns you to — `signIn()` remembers where
 * you were, and where you were is this.
 */
export const LANDING_SCREENS = [
  {
    id: "/dashboard",
    label: "Dashboard",
    description: "The overview for your role — what is moving and what is waiting.",
  },
  {
    id: "/my-work",
    label: "My Work",
    description: "Only what is assigned to you or your role, and nothing else.",
  },
  {
    id: "/testing",
    label: "Testing queue",
    description: "Straight to the test queue, for a day spent on the bench.",
  },
] as const;

export type LandingScreen = (typeof LANDING_SCREENS)[number]["id"];

export const DEFAULT_LANDING: LandingScreen = "/dashboard";

export function isLandingScreen(value: string): value is LandingScreen {
  return LANDING_SCREENS.some((screen) => screen.id === value);
}

/**
 * Read a stored preference, defensively.
 *
 * 🔴 EVERY BRANCH HERE IS A REAL STATE. `localStorage` throws outright in a
 * private window with site data blocked, is absent during the server render of
 * a static export, and returns whatever a previous version of this application
 * wrote — including a theme id that no longer exists. A preference that cannot
 * be read is not an error worth surfacing; it is the default.
 */
function read<T extends string>(key: string, valid: (value: string) => value is T, fallback: T): T {
  if (typeof window === "undefined") {
    return fallback;
  }
  try {
    const stored = window.localStorage.getItem(key);
    return stored !== null && valid(stored) ? stored : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // A preference that cannot be saved still applies for this session. Failing
    // the change because it could not be remembered would be worse than
    // forgetting it.
  }
}

export function readTheme(): ThemeId {
  return read(THEME_KEY, isThemeId, DEFAULT_THEME);
}

export function readLanding(): LandingScreen {
  return read(LANDING_KEY, isLandingScreen, DEFAULT_LANDING);
}

/**
 * The stored preferences, and the ability to change them.
 *
 * ⚠️ IT STARTS AT THE DEFAULT AND CORRECTS ON MOUNT, deliberately. A static
 * export renders on the server where there is no `localStorage`, so reading it
 * during render would make the server and client markup disagree — React's
 * hydration mismatch, which in this application would show as the settings page
 * flickering to a different answer than the one painted.
 */
export function usePreferences(): {
  readonly theme: ThemeId;
  readonly landing: LandingScreen;
  readonly setTheme: (theme: ThemeId) => void;
  readonly setLanding: (landing: LandingScreen) => void;
} {
  const [theme, setThemeState] = useState<ThemeId>(DEFAULT_THEME);
  const [landing, setLandingState] = useState<LandingScreen>(DEFAULT_LANDING);

  useEffect(() => {
    setThemeState(readTheme());
    setLandingState(readLanding());
  }, []);

  const setTheme = useCallback((next: ThemeId) => {
    setThemeState(next);
    write(THEME_KEY, next);
    // 🔴 TELL THE PROVIDER, RATHER THAN LETTING IT POLL. `storage` fires only in
    // OTHER tabs, never the one that wrote — so a same-tab change would repaint
    // nothing without this. Found the way everybody finds it.
    window.dispatchEvent(new CustomEvent("evercoat:theme", { detail: next }));
  }, []);

  const setLanding = useCallback((next: LandingScreen) => {
    setLandingState(next);
    write(LANDING_KEY, next);
  }, []);

  return { theme, landing, setTheme, setLanding };
}
