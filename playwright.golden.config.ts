import { defineConfig, devices } from "@playwright/test";

/**
 * §39's golden scenario, in a browser — CI ONLY, and deliberately so.
 *
 * 🔴 WHY THIS IS A SEPARATE CONFIG AND NOT A PROJECT IN `playwright.config.ts`.
 *
 * §39 asks for the scenario "on the deployed instance ... in UI and database
 * state", and the walk writes REAL R&D records to get there: a workspace, a
 * question, a source, an evidence card, a finding and a proposal. §5 is
 * explicit that R&D history is retired and never deleted, and every FK into it
 * is `RESTRICT` — so against a long-lived deployed database these accumulate
 * on every run and nothing is permitted to clean them up.
 *
 * ⚠️ The walk stops at the proposal, before the approval engine, and that
 * boundary is deliberate: `workflow.approval_route_steps` is append-only
 * **even to the superuser** — measured, *"approval_route_steps is append-only;
 * DELETE is not permitted"*. Submitting a finding would be irreversible
 * anywhere, CI included. Those hops stay with the database half.
 *
 * The owner chose: run it in CI only. CI builds its database fresh from
 * migrations on every run, so the records go with the runner.
 *
 * ⚠️ THAT IS A REAL GAP AND IT IS NAMED RATHER THAN PAPERED OVER: CI is not
 * "the deployed instance", so **§39 is not closed by this file**, exactly as
 * `test_golden_scenario_research.py` is not closed by being green. What this
 * buys is continuous regression cover on every commit, which the deployed-only
 * reading buys never.
 *
 * 🔴 AND WHY IT IS NOT IN THE MAIN CONFIG AT ALL.
 *
 * Two of the three ways Playwright runs in this repository CANNOT run this
 * walk, and adding it as a project would have made both of them wrong:
 *
 *   · the `e2e` CI job sets `KEYCLOAK_ISSUER: http://127.0.0.1:1/...` on
 *     purpose, so every authenticated route refuses before it reaches JWKS.
 *     A walk that must CREATE records would fail there for a reason that has
 *     nothing to do with the walk.
 *   · `scripts/live-suite.sh` points Playwright at the DEPLOYED site. That is
 *     the one place this must never run.
 *
 * A separate config cannot be reached by either. `--config` is required, and
 * only the `auth` CI job passes it — the one job that stands up a real
 * Keycloak with the shipped realm, seeds an organization and binds real realm
 * subjects.
 *
 * ⚠️ NO `webServer` HERE. The `auth` job starts the API and the web build
 * itself, against the Keycloak it created. Starting servers from this file
 * would give the walk a DIFFERENT API from the one the job authenticated
 * against, which is the "proving something about neither" failure the main
 * config's live-mode comment already records.
 */

// 🔴 `localhost`, NOT `127.0.0.1`, AND THE REALM DECIDES THAT — NOT TASTE.
//
// The walk signs in for real, and `evercoat-web` in `evercoat-realm.json`
// registers exactly `http://localhost:3000/auth/callback/`. To Keycloak
// `http://127.0.0.1:3000` is a DIFFERENT ORIGIN, so the same server on the same
// port would be refused with "Invalid parameter: redirect_uri" — which renders
// as a 200 page with no username field, the exact failure `sign-in.spec.ts`
// documents. Serving on localhost:3000 is what lets CI use the SHIPPED realm
// unmodified, rather than a realm edited to make the test pass.
const WEB_BASE_URL = process.env.GOLDEN_WEB_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "tests/golden",

  // One scenario, walked in order. Each step depends on the record the
  // previous one created, so parallelism here would not be faster — it would
  // be wrong.
  fullyParallel: false,
  workers: 1,

  forbidOnly: !!process.env.CI,

  // 🔴 NO RETRIES, UNLIKE THE SHELL SUITE.
  //
  // The shell suite retries once because a tunnel hop can genuinely drop. This
  // walk WRITES, and every step is append-only or otherwise irreversible — a
  // retry would re-run half a scenario on top of the rows the first attempt
  // already committed, and the second failure would be a consequence of the
  // first rather than a finding. A flaky walk here is a defect to read, not to
  // paper over.
  retries: 0,

  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report-golden" }]],

  // The walk crosses many screens and waits on real approval state. The budget
  // is per TEST, and this is one long test rather than many short ones.
  timeout: 600_000,
  expect: { timeout: 20_000 },

  use: {
    baseURL: WEB_BASE_URL,

    // \U0001f534 A CAP ON ACTIONS, BECAUSE EVERY WRITE CONTROL CAN BE DISABLED.
    //
    // Each submit on the research screen is `disabled={writes.isPending ||
    // !may}`. If `chem.demo` ever loses `research.create` or
    // `experiment.propose`, a click would wait for the TEST budget — ten
    // minutes — and the job would report a timeout rather than a permissions
    // regression. Thirty seconds turns that into a fast failure that names the
    // control it could not press.
    actionTimeout: 30_000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },

  projects: [
    {
      name: "golden",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
