import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

// One switch, read once. `output` and `trailingSlash` must agree about which
// build this is — deriving both from the same constant is what stops them
// drifting apart.
const isExport = process.env.NEXT_OUTPUT === "export";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone output so the runtime image ships without node_modules.
  //
  // `NEXT_OUTPUT=export` switches to a static export, which is how the site is
  // hosted today: a RENDER STATIC SITE at itwevercoatrd.aiappinvent.com.
  //
  // Why static. Creating a free Render WEB SERVICE is refused by this account —
  // 400 "free tier usage quota has been exhausted", measured 2026-08-18; all
  // five existing services are `standard`. A static site has no instance, so it
  // does not draw on the 750 free instance-hours, it is free of charge, and
  // Render issues its TLS certificate automatically. The operator's rule is
  // zero cost, so this is the only route that both works and spends nothing.
  //
  // It is written as a SWITCH, not a replacement: `apps/web/Dockerfile` and the
  // standalone output are untouched, so reverting to a container is a config
  // change rather than a rewrite.
  //
  // A static export is honest for this app today rather than a compromise:
  // `apps/web` makes no API calls at all — no fetch, no next-auth wiring — and
  // has three pages. There is no server-side behaviour to lose. That stops
  // being true at Slice 3, when the API is wired in; at that point a static
  // host cannot serve the product and this switch should go away rather than
  // be worked around.
  // 🔴 THE BUILD DIRECTORY IS OVERRIDABLE, SO TWO BUILDS CANNOT CLOBBER EACH
  // OTHER.
  //
  // `next build` regenerates `.next/` INCLUDING `.next/standalone/`, which is
  // what the running demonstration server serves. So a Playwright local run --
  // which builds before starting its own web server -- silently overwrote the
  // demo's bundle with one built WITHOUT `NEXT_PUBLIC_*`. Twice. The site kept
  // returning 200 on every page and simply announced "no identity provider is
  // deployed for this environment", because those values are inlined at BUILD
  // time and nothing at runtime can notice they are missing.
  //
  // `scripts/demo-up.ps1` now sets `NEXT_DIST_DIR=.next-demo`, so the demo and
  // the test suite own separate directories and neither can destroy the other.
  // Default unchanged, so CI and ordinary `next build` behave exactly as before.
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  output: isExport ? "export" : "standalone",
  // Directory-index output (`/dashboard/index.html`) instead of
  // `/dashboard.html`, and ONLY for the static export.
  //
  // This is not cosmetic. Render does not do clean-URL fallback: its
  // documentation states it serves the resource at a path if one exists and
  // otherwise applies rules, and it has no implicit ".html" lookup. With the
  // default `trailingSlash: false` the export writes `out/dashboard.html`, and
  // a request for `/dashboard` — which is what every link in lib/navigation.ts
  // points at — matches no resource and 404s. The build would be green, the
  // certificate valid, and every page but the root broken.
  //
  // A directory index is the one convention every static host serves, so this
  // keeps the deployment from depending on host-specific routing. Scoped to
  // the export because the standalone server resolves routes itself and does
  // not need it; changing it there would alter live URLs for no benefit.
  trailingSlash: isExport,
  // The repository root carries its own package.json for the end-to-end
  // suite, so there are two lockfiles above this app. Without this, Next
  // guesses which one marks the workspace root, warns on every build, and
  // can trace the WRONG tree into the standalone output — which would
  // show up as a runtime "module not found" in the container, long after
  // the build went green.
  outputFileTracingRoot: dirname(fileURLToPath(import.meta.url)),
  poweredByHeader: false,
  eslint: { ignoreDuringBuilds: false },
  typescript: { ignoreBuildErrors: false },
};

export default nextConfig;
