"use client";

/**
 * Settings — how the application looks, and where it opens.
 *
 * 🔴 THE PREFERENCES LIVE IN THIS BROWSER, AND THE PAGE SAYS SO.
 *
 * There is no user-preference endpoint. §1 gives PostgreSQL *verified technical
 * facts*; a colour scheme is not one, and putting it beside formula compositions
 * would be the start of treating it like one. So these are stored locally and do
 * not follow a person to another machine — which is a real limitation and is
 * stated on the screen rather than discovered.
 *
 * ⚠️ A CHOICE APPLIES IMMEDIATELY AND THERE IS NO SAVE BUTTON. A theme you
 * cannot see until you press Save is a theme you have to guess at, and a Save
 * button that only writes `localStorage` is a promise about durability this page
 * cannot keep.
 */

import { EntityHeader } from "@/components/ui/entity-header";
import { LANDING_SCREENS, usePreferences } from "@/lib/preferences";
import { PALETTES, THEMES, contrast, type ThemeId } from "@/lib/theme";

const TAG =
  "rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase " +
  "tracking-wide text-slate-600";

/**
 * A miniature of what the theme actually paints.
 *
 * 🔴 BUILT FROM THE PALETTE, NOT PAINTED BY HAND. A swatch with its own
 * hard-coded colours is a second copy of the theme that agrees with it on the
 * day it is written — this reads the same constants the application does, so a
 * preview cannot show something the product will not.
 */
function Swatch({ theme }: { theme: ThemeId }) {
  // `system` has no palette of its own; the light one is shown because that is
  // what most machines resolve to, and the label says it follows the system.
  const palette = theme === "system" ? PALETTES.light : PALETTES[theme];

  return (
    <span
      aria-hidden
      className="flex h-10 w-16 shrink-0 flex-col justify-between rounded border p-1"
      style={{
        backgroundColor: `rgb(${palette.white})`,
        borderColor: `rgb(${palette.slate300})`,
      }}
    >
      <span className="h-1.5 w-9 rounded" style={{ backgroundColor: `rgb(${palette.slate900})` }} />
      <span className="h-1 w-11 rounded" style={{ backgroundColor: `rgb(${palette.slate600})` }} />
      <span className="flex gap-0.5">
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{ backgroundColor: `rgb(${palette.status.pass})` }}
        />
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{ backgroundColor: `rgb(${palette.status.conditional})` }}
        />
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{ backgroundColor: `rgb(${palette.status.fail})` }}
        />
      </span>
    </span>
  );
}

export default function SettingsPage() {
  const { theme, landing, setTheme, setLanding } = usePreferences();

  return (
    <div>
      <EntityHeader
        eyebrow="Your account"
        title="Settings"
        crumbs={[{ label: "Dashboard", href: "/dashboard" }]}
      />

      <div className="space-y-8 p-6">
        <section aria-labelledby="theme-heading" className="max-w-3xl">
          <h2 id="theme-heading" className="text-sm font-semibold text-slate-900">
            Theme
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Five options. Every one is measured rather than chosen by eye — each
            text colour clears WCAG AA against its own surface, and the
            traffic-light colours are checked against every theme.
          </p>

          {/* radiogroup, not a list of buttons: these are one choice among
              five, and arrow-key navigation between them is what a screen
              reader user expects from a radiogroup and does not get from a row
              of buttons. */}
          <div role="radiogroup" aria-labelledby="theme-heading" className="mt-3 grid gap-2">
            {THEMES.map((option) => {
              const chosen = option.id === theme;
              return (
                <button
                  key={option.id}
                  type="button"
                  role="radio"
                  aria-checked={chosen}
                  onClick={() => setTheme(option.id)}
                  className={[
                    "flex items-center gap-3 rounded border p-3 text-left",
                    chosen
                      ? "border-slate-900 bg-slate-50"
                      : "border-slate-200 bg-white hover:bg-slate-50",
                  ].join(" ")}
                >
                  <Swatch theme={option.id} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium text-slate-900">
                      {option.label}
                    </span>
                    <span className="block text-xs text-slate-600">{option.description}</span>
                  </span>
                  {/* 🔴 A WORD, NOT A TICK ALONE. §11 forbids state carried by
                      colour or shape alone, and "which one is selected" is
                      state. `aria-checked` says it assistively; this says it
                      to everyone else. */}
                  {chosen && <span className={TAG}>selected</span>}
                </button>
              );
            })}
          </div>

          <p className="mt-3 text-xs text-slate-600">
            Measured on the light surface: body text{" "}
            {contrast(PALETTES.light.slate600, PALETTES.light.white).toFixed(1)}:1, and on the dark
            surface {contrast(PALETTES.dark.slate600, PALETTES.dark.white).toFixed(1)}:1. High
            contrast holds every text step above 7:1.
          </p>
        </section>

        <section aria-labelledby="landing-heading" className="max-w-3xl">
          <h2 id="landing-heading" className="text-sm font-semibold text-slate-900">
            After signing in, open
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Three screens to choose from. Each one exists — a preference pointing
            at an unbuilt screen would be a setting whose only effect is a 404.
          </p>

          <div role="radiogroup" aria-labelledby="landing-heading" className="mt-3 grid gap-2">
            {LANDING_SCREENS.map((screen) => {
              const chosen = screen.id === landing;
              return (
                <button
                  key={screen.id}
                  type="button"
                  role="radio"
                  aria-checked={chosen}
                  onClick={() => setLanding(screen.id)}
                  className={[
                    "flex items-center gap-3 rounded border p-3 text-left",
                    chosen
                      ? "border-slate-900 bg-slate-50"
                      : "border-slate-200 bg-white hover:bg-slate-50",
                  ].join(" ")}
                >
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium text-slate-900">
                      {screen.label}
                    </span>
                    <span className="block text-xs text-slate-600">{screen.description}</span>
                  </span>
                  {chosen && <span className={TAG}>selected</span>}
                </button>
              );
            })}
          </div>
        </section>

        <section className="max-w-3xl">
          <h2 className="text-sm font-semibold text-slate-900">Where these are kept</h2>
          <p className="mt-1 text-sm leading-relaxed text-slate-600">
            Both settings are stored in <strong>this browser</strong>, not on the
            server, so they do not follow you to another machine. There is no
            user-preference endpoint and adding one would put a colour scheme in
            the database that holds verified technical records. Your access token
            is deliberately <strong>not</strong> stored the same way — that one
            lives only in memory, which is why a page reload signs you out.
          </p>
        </section>
      </div>
    </div>
  );
}
