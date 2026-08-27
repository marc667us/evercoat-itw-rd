"use client";

/**
 * Applies the chosen palette to `<html>`.
 *
 * 🔴 IT WRITES CSS VARIABLES RATHER THAN SWAPPING A STYLESHEET, so there is
 * exactly one definition of every palette — `lib/theme.ts` — and no second copy
 * in CSS to drift from it. `tailwind.config` resolves `bg-white`,
 * `text-slate-600` and the rest through those variables, so setting them
 * re-themes every screen at once.
 *
 * ⚠️ IT ALSO SETS `color-scheme`. Without it the browser goes on painting form
 * controls, scrollbars and the space beyond the page in light colours, so a
 * dark theme arrives with white scrollbars and a white overscroll band. That is
 * not cosmetic on a screen this dense — the scrollbar is beside a data grid on
 * most pages.
 *
 * 🔴 `system` KEEPS LISTENING. It is the only option that is not a palette but
 * a rule, and a rule that stopped applying the moment it was chosen would be a
 * setting that lies: choose "match my system", turn the machine dark at dusk,
 * and nothing happens. The media-query listener is what makes the label true.
 */

import { useEffect } from "react";

import { readTheme } from "@/lib/preferences";
import { CSS_VARIABLES, STATUS_VARIABLES, resolvePalette, type ThemeId } from "@/lib/theme";

function apply(theme: ThemeId, prefersDark: boolean): void {
  const palette = resolvePalette(theme, prefersDark);
  const root = document.documentElement;

  for (const [key, variable] of Object.entries(CSS_VARIABLES)) {
    root.style.setProperty(variable, palette[key as keyof typeof CSS_VARIABLES]);
  }
  for (const [key, variable] of Object.entries(STATUS_VARIABLES)) {
    root.style.setProperty(variable, palette.status[key as keyof typeof STATUS_VARIABLES]);
  }

  // Which theme is active, for anything that needs to branch on it — and for a
  // person inspecting the page to see what they are looking at.
  root.dataset["theme"] = theme;
  root.style.colorScheme = (theme === "system" && prefersDark) || theme === "dark" ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    let current = readTheme();

    const repaint = () => apply(current, media.matches);
    repaint();

    // Same tab: the settings screen dispatches this, because `storage` fires
    // only in OTHER tabs and never in the one that wrote.
    const onChosen = (event: Event) => {
      const detail = (event as CustomEvent<ThemeId>).detail;
      current = detail;
      repaint();
    };
    // Other tabs: keep two windows of the same application in agreement.
    const onStorage = () => {
      current = readTheme();
      repaint();
    };

    window.addEventListener("evercoat:theme", onChosen);
    window.addEventListener("storage", onStorage);
    media.addEventListener("change", repaint);

    return () => {
      window.removeEventListener("evercoat:theme", onChosen);
      window.removeEventListener("storage", onStorage);
      media.removeEventListener("change", repaint);
    };
  }, []);

  return <>{children}</>;
}
