import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./features/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Traffic-light tokens. Named by MEANING, not by colour, so a
        // component cannot render "green" for a result that is only
        // technically passing but not yet approved (CLAUDE.md §10).
        // Validated, not chosen by eye. Measured on the light surface,
        // pass vs fail is deltaE 4.2 under deuteranopia -- roughly 8% of
        // men cannot tell them apart by hue. That is the measurement
        // behind CLAUDE.md 10's colour + icon + text rule, and why
        // components take domain state rather than a colour prop.
        //
        // `invalid` shares the fail hue deliberately: the domain has
        // THREE states and ADR-015 routes invalid to RED. A fourth hue
        // would imply a fourth state, and the darker red tried first
        // failed the lightness band at L 0.396.
        status: {
          pass: "#15803d",
          fail: "#b91c1c",
          conditional: "#a16207",
          invalid: "#b91c1c",
          neutral: "#52514e",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
