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
import { RadioCards } from "@/components/ui/radio-cards";
import { LANDING_SCREENS, usePreferences, type LandingScreen } from "@/lib/preferences";
import { PALETTES, THEMES, contrast, type ThemeId } from "@/lib/theme";

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

          {/* 🔴 `RadioCards` RATHER THAN A ROW OF BUTTONS WITH A ROLE ON IT.
              This markup used to declare `role="radiogroup"` over five
              ordinary buttons, under a comment arguing that arrow-key
              navigation "is what a screen reader user expects from a
              radiogroup and does not get from a row of buttons" — and it did
              not implement any. The Supervisor found the gap between the
              comment and the widget. */}
          <RadioCards<ThemeId>
            labelledBy="theme-heading"
            value={theme}
            onChange={setTheme}
            options={THEMES.map((option) => ({
              id: option.id,
              label: option.label,
              description: option.description,
              preview: <Swatch theme={option.id} />,
            }))}
          />

          <p className="mt-3 text-xs text-slate-600">
            Measured on the light surface: body text{" "}
            {contrast(PALETTES.light.slate600, PALETTES.light.white).toFixed(1)}:1, and on the dark
            surface {contrast(PALETTES.dark.slate600, PALETTES.dark.white).toFixed(1)}:1. High
            contrast holds every text step above 7:1.
          </p>
        </section>

        <section aria-labelledby="landing-heading" className="max-w-3xl">
          <h2 id="landing-heading" className="text-sm font-semibold text-slate-900">
            Where the application opens
          </h2>
          {/* 🔴 THE HEADING USED TO SAY "AFTER SIGNING IN, OPEN" AND NOTHING
              IMPLEMENTED IT. `readLanding` had no reader anywhere in the
              codebase: the front door redirected to a hard-coded `/dashboard`
              and sign-in returned you to wherever you already were. Both
              reviewers found it, and it is this project's own rule — a setting
              with no enforcement point is a defect — arriving from the user's
              side of the screen.

              It is now the front door's destination, which is also what
              sign-in returns you to when you have not navigated somewhere
              else first. The heading says what happens rather than the
              narrower thing the first version claimed. */}
          <p className="mt-1 text-sm text-slate-600">
            Three screens to choose from. Each one exists — a preference pointing
            at an unbuilt screen would be a setting whose only effect is a 404.
            Opening a link straight to a record still takes you to that record;
            this is where you arrive when you have not asked for anywhere in
            particular.
          </p>

          <RadioCards<LandingScreen>
            labelledBy="landing-heading"
            value={landing}
            onChange={setLanding}
            options={LANDING_SCREENS.map((screen) => ({
              id: screen.id,
              label: screen.label,
              description: screen.description,
            }))}
          />
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
