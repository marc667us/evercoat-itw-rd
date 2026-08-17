import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end configuration.
 *
 * `CLAUDE.md` §13 specifies `npx playwright test` from the repository
 * root against `tests/e2e/`, which is why this file and its own minimal
 * `package.json` live here rather than inside `apps/web`.
 *
 * WHAT THIS SUITE CAN AND CANNOT PROVE, STATED UP FRONT
 * -----------------------------------------------------
 * The golden MVP scenario from the master prompt §44 (formula → lab batch
 * → sample → test → RED → failure investigation → revised formula →
 * retest → YELLOW → approvals → GREEN) is **not** here, and adding a file
 * named after it would be worse than not having one.
 *
 * Eleven of that scenario's fifteen steps have no table, no route, no
 * service and no page. Separately, `apps/web` makes **no API calls at
 * all** — there is no `fetch`, no `next-auth` wiring and no sign-in flow
 * in the application today, so a browser physically cannot drive the
 * thread. The golden scenario belongs to Slice 7, where
 * `IMPLEMENTATION_PLAN.md:436` already puts it.
 *
 * What this suite does prove, for the first time in this project:
 *
 *   shell/  the web application actually renders in a real browser, the
 *           navigation gating behaves as its unit tests claim, and the
 *           pages pass an axe-core accessibility scan. `CLAUDE.md` §11
 *           requires axe-core in CI; until now it had never run.
 *
 *   api/    the API boots under a real ASGI server and serves over real
 *           HTTP — not through Starlette's TestClient. That distinction
 *           has mattered here before: this application has twice failed
 *           to boot while its type-check, lint and full unit suite were
 *           green, because TestClient never exercises startup the way a
 *           server does.
 *
 * Both servers are started by Playwright itself, so a run cannot pass
 * against something a developer happened to leave running with different
 * code in it.
 */

const WEB_PORT = 3100;
const API_PORT = 8100;

export const WEB_BASE_URL = `http://127.0.0.1:${WEB_PORT}`;
export const API_BASE_URL = `http://127.0.0.1:${API_PORT}`;

// The application's own database container, on its own port. Never an
// `aw-*` service: those belong to a different product on this host and
// are off limits.
const DATABASE_URL =
  process.env.DATABASE_URL ??
  "postgresql+psycopg://evercoat_app:dev-app-pw@localhost:55432/evercoat_itw_rd";

// A syntactically valid issuer that resolves to nothing. Every
// authenticated route must refuse before it ever reaches JWKS, so these
// tests never need a running Keycloak — and a test that quietly started
// passing because Keycloak appeared would be testing something else.
const KEYCLOAK_ISSUER = process.env.KEYCLOAK_ISSUER ?? "http://127.0.0.1:1/realms/evercoat";

export default defineConfig({
  testDir: "tests/e2e",

  // A shared database means these must not race each other.
  fullyParallel: false,
  workers: 1,

  // Fail the run rather than let a `.only` committed by accident silently
  // reduce CI to one test.
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,

  // `list` so a failure is legible in a terminal or a CI log, `html` so
  // the trace and screenshot of a failure are actually reachable.
  reporter: [["list"], ["html", { open: "never" }]],

  expect: { timeout: 10_000 },
  timeout: 60_000,

  use: {
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },

  projects: [
    {
      name: "shell",
      testDir: "tests/e2e/shell",
      use: { ...devices["Desktop Chrome"], baseURL: WEB_BASE_URL },
    },
    {
      name: "api",
      testDir: "tests/e2e/api",
      use: { baseURL: API_BASE_URL },
    },
  ],

  webServer: [
    {
      // Built every run on purpose. `next start` will happily serve a
      // stale `.next` from a previous commit, and a suite that passes
      // against last week's bundle is a false green — a failure mode this
      // platform has already been bitten by.
      command: `npx next build && npx next start --port ${WEB_PORT} --hostname 127.0.0.1`,
      cwd: "apps/web",
      url: WEB_BASE_URL,
      // NEVER reuse. `reuseExistingServer: !process.env.CI` is the usual
      // default and it directly contradicts the rebuild above: locally,
      // any process already answering on this port makes Playwright skip
      // the build AND the server command, so the suite silently runs
      // against whatever was there — an old bundle, or an unrelated app.
      // That is the stale-artifact false green this platform has been
      // bitten by before, so the few seconds saved are not worth it.
      reuseExistingServer: false,
      timeout: 300_000,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      command: `python -m uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT}`,
      cwd: "apps/api",
      // /health/live is deliberately the readiness probe for STARTING the
      // server: it answers without touching the database, so Playwright
      // waits for "the process is serving HTTP", not "the database is up".
      // Whether the database is reachable is a thing the tests assert, not
      // a precondition they hide.
      url: `${API_BASE_URL}/health/live`,
      env: {
        DATABASE_URL,
        KEYCLOAK_ISSUER,
        APP_ENV: "development",
        LOG_FORMAT: "console",
        METRICS_ENABLED: "true",
      },
      // NEVER reuse. `reuseExistingServer: !process.env.CI` is the usual
      // default and it directly contradicts the rebuild above: locally,
      // any process already answering on this port makes Playwright skip
      // the build AND the server command, so the suite silently runs
      // against whatever was there — an old bundle, or an unrelated app.
      // That is the stale-artifact false green this platform has been
      // bitten by before, so the few seconds saved are not worth it.
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: "pipe",
      stderr: "pipe",
    },
  ],
});
