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
 * service and no page. The golden scenario belongs to Slice 7, where
 * `IMPLEMENTATION_PLAN.md:436` already puts it.
 *
 * CORRECTED 2026-08-18. This paragraph used to continue: "Separately,
 * `apps/web` makes **no API calls at all** — there is no `fetch`, no
 * `next-auth` wiring and no sign-in flow in the application today, so a
 * browser physically cannot drive the thread."
 *
 * That was true for three slices and is no longer. `shell/api-wiring.spec.ts`
 * asserts the application issuing real requests: the top bar's health
 * probe reaches uvicorn and PostgreSQL with nothing stubbed, and the
 * materials page sends its own authenticated request with both headers the
 * API requires. What is still absent is a SIGN-IN FLOW — no Keycloak is
 * deployed anywhere, so no authenticated call can succeed against a real
 * server, and the suite establishes a client-side session through a seam
 * that is compiled out of production builds (`lib/api/session.ts`).
 *
 * What this suite does prove, for the first time in this project:
 *
 *   shell/  the web application actually renders in a real browser, the
 *           navigation gating behaves as its unit tests claim, and the
 *           pages pass an axe-core accessibility scan. `CLAUDE.md` §11
 *           requires axe-core in CI; until now it had never run.
 *
 *   shell/api-wiring.spec.ts
 *           the web application CALLS the API — the claim that could not
 *           be made before Slice 3's back half existed. Both directions
 *           are asserted: live rows render and are labelled as live, and a
 *           failed request shows the failure rather than quietly
 *           substituting demonstration figures.
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

// LIVE MODE. When PLAYWRIGHT_BASE_URL is set, the suite runs against an
// ALREADY DEPLOYED site instead of servers it starts itself.
//
// This existed in name only until now: `scripts/live-suite.sh` exported
// PLAYWRIGHT_BASE_URL, and nothing in this file ever read it. The variable
// was ignored, Playwright started its own local servers, and the "live"
// end-to-end run tested 127.0.0.1 while reporting against the deployed URL.
// It would have passed with the deployment completely broken — the precise
// false green the live-test rule exists to prevent.
//
// In live mode the `api` project is dropped rather than pointed somewhere.
// `render.yaml` deploys the web application only (ADR-009), so there is no
// deployed API to talk to; running it against a local uvicorn under a live
// banner would be the same lie in the other direction. The live suite
// counts the API surface as SKIPPED, which is a coverage gap honestly
// reported rather than a pass.
const LIVE_BASE_URL = process.env.PLAYWRIGHT_BASE_URL?.replace(/\/+$/, "");
const LIVE = Boolean(LIVE_BASE_URL);

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

  projects: LIVE
    ? [
        {
          name: "shell",
          testDir: "tests/e2e/shell",
          // 🔴 api-wiring.spec.ts CANNOT PASS AGAINST A DEPLOYED BUILD, AND
          // ITS 8 FAILURES WERE A FALSE RED.
          //
          // Measured against https://itwevercoatrd.aiappinvent.com: the
          // live suite reported 25 passed / 8 failed, and the 8 were the
          // WHOLE of this file — accessibility 13/13 and navigation 12/12
          // passed. The page carries no `api-status` element and no
          // `data-source-error` element at all, because the API-wiring seam
          // is compiled OUT of production builds (see apps/web
          // lib/api/session.ts). The spec is therefore testing a seam that
          // does not exist at this URL, not a defect in the deployment.
          //
          // Excluded here rather than left to fail, because a permanent red
          // is worse than a skip: it trains the reader to ignore the number
          // that is supposed to stop a bad deploy. live-suite.sh counts the
          // exclusion as a SKIP and names it, so the gap stays visible.
          //
          // When the API is deployed, delete this line — the spec becomes a
          // real assertion again.
          testIgnore: ["**/api-wiring.spec.ts"],
          use: { ...devices["Desktop Chrome"], baseURL: LIVE_BASE_URL },
        },
      ]
    : [
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

  // Omitted entirely in live mode. Starting a local server while testing a
  // deployed URL is how a run ends up proving something about neither.
  ...(LIVE ? {} : {
  webServer: [
    {
      // Built every run on purpose. `next start` will happily serve a
      // stale `.next` from a previous commit, and a suite that passes
      // against last week's bundle is a false green — a failure mode this
      // platform has already been bitten by.
      command: `npx next build && npx next start --port ${WEB_PORT} --hostname 127.0.0.1`,
      cwd: "apps/web",
      url: WEB_BASE_URL,
      env: {
        // THE ADDRESS OF THE API THIS BUILD TALKS TO.
        //
        // `NEXT_PUBLIC_*` is inlined at BUILD time, so it has to be here on
        // the build command rather than set beside `next start` — a value
        // supplied to the running server changes nothing, and this platform
        // has already been bitten by exactly that.
        //
        // Setting it is what makes the suite able to prove anything about
        // the wiring at all: without it every page resolves to the
        // demonstration dataset and the tests below would pass against an
        // application that still made no API calls.
        NEXT_PUBLIC_API_BASE_URL: API_BASE_URL,
        // The client-side session seam. Compiled out of every build that
        // does not set this, so the production bundle does not contain it.
        // It grants nothing: the API verifies token signatures against the
        // realm's JWKS and reads permissions from the database, so a
        // session set here with an unissued token is refused exactly as any
        // forgery would be. See lib/api/session.ts.
        NEXT_PUBLIC_E2E_SESSION_HOOK: "1",
      },
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
        // The browser calls this API from a DIFFERENT ORIGIN — the web app
        // is on :3100 and the API on :8100 — so without this every request
        // the suite is meant to observe would be refused by the browser
        // before it was sent, and would surface as "the API could not be
        // reached" with no clue that CORS was the cause.
        //
        // A JSON array because pydantic-settings parses `list[str]` as
        // JSON. A bare comma-separated string is accepted by neither, and
        // fails at startup rather than at request time — which is the
        // better of the two failures but still a confusing one.
        CORS_ALLOWED_ORIGINS: JSON.stringify([WEB_BASE_URL]),
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
  }),
});
