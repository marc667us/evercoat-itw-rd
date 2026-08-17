import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone output so the runtime image ships without node_modules.
  output: "standalone",
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
