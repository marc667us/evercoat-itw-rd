import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./features/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Traffic-light tokens. Named by MEANING, not by colour, so a
        // component cannot render "green" for a result that is only
        // technically passing but not yet approved (CLAUDE.md §10).
        status: {
          pass: "#15803d",
          fail: "#b91c1c",
          conditional: "#a16207",
          invalid: "#7f1d1d",
          neutral: "#475569",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
