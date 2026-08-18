import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone output so the runtime image ships without node_modules.
  //
  // `NEXT_OUTPUT=export` switches to a static export for Cloudflare Pages,
  // which is where this is hosted TEMPORARILY: Render refused a new free
  // service with 400 "free tier usage quota has been exhausted", and the
  // operator's standing rule is zero cost. **The intent is to move back to
  // Render once that quota resets** — so this is written as a switch and
  // not as a replacement. Reverting is: stop passing NEXT_OUTPUT. The
  // Dockerfile, render.yaml and render-setup.yml are untouched and still
  // describe the Render deployment.
  //
  // A static export is honest for this app today rather than a compromise:
  // `apps/web` makes no API calls at all — no fetch, no next-auth wiring —
  // and has three pages. There is no server-side behaviour to lose.
  // That stops being true at Slice 3, when the API is wired in; at that
  // point a static host cannot serve the product and this switch should go
  // away rather than be worked around.
  output: process.env.NEXT_OUTPUT === "export" ? "export" : "standalone",
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
