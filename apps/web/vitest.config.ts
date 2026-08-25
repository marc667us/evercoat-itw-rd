import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  // `tsconfig.json` sets `jsx: "preserve"` for Next, so esbuild alone leaves
  // JSX untransformed and every `.test.tsx` fails to parse. The plugin was
  // already a devDependency alongside `@testing-library/react` and `jsdom`
  // and had never been wired in -- which is why NO component in this
  // application had ever been rendered by a test, and why `DataSourceError`
  // could show the wrong sentence at nineteen call sites undetected (I98).
  plugins: [react()],
  test: {
    // Node stays the default so the existing pure-logic suites keep their
    // speed. A component test opts in with `@vitest-environment jsdom`.
    environment: "node",
    include: ["**/*.test.ts", "**/*.test.tsx"],
    exclude: ["node_modules/**", ".next/**"],
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, ".") },
  },
});
