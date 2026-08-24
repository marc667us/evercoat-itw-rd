/**
 * The sign-in round trip — the one flow every human uses and no test drove.
 *
 * 🔴 WHY THIS FILE EXISTS: 713 TESTS PASSED WHILE SIGN-IN RETURNED 404.
 *
 * On 2026-08-24 the live suite reported 713 passed / 0 failed / 0 skipped
 * against a deployment where **every browser sign-in ended on a 404 page after
 * authenticating successfully** (I96). `Caddyfile.tunnel` routes `/auth/*` to
 * Keycloak with the prefix stripped, and the application's own OIDC callback
 * is `/auth/callback/` — so Keycloak was asked for `/callback/` and answered
 * 404. Measured: `:3000/auth/callback` → 200, `:18081/auth/callback/` → 404.
 * The application was fine; the PROXY had no route to it.
 *
 * Not one of those 713 assertions could have caught it:
 *
 *   - `api-live` authenticates by DIRECT GRANT (`evercoat-test`), which never
 *     touches a redirect URI or a callback.
 *   - the e2e shell suite establishes a session through a seam that is
 *     compiled OUT of production builds.
 *
 * So the defect was invisible to the number that exists to stop a bad deploy,
 * and it reached a human instead. *"Proven by hand with real tokens"* was true
 * in every previous session and never meant sign-in worked.
 *
 * This test closes that by doing what a person does: press Sign in, type a
 * password into the real Keycloak form, and land back in the application
 * signed in. It asserts the WHOLE chain — the authorize redirect, the realm's
 * acceptance of the redirect_uri, the proxy's route back to the callback, and
 * the application's own token exchange.
 *
 * ⚠️ ONLY THE ROUND TRIP SKIPS WITHOUT CREDENTIALS, AND A SKIP IS NOT A PASS.
 * `live-suite.sh` reports skipped as its own number for exactly this reason.
 * If the round trip skips in a LIVE run, the sign-in flow was NOT verified —
 * treat that as a gap, not as a green.
 *
 * The callback guard below needs no password and therefore **runs everywhere,
 * including CI**. The two used to skip together, which meant a green CI badge
 * protected the sign-in flow from nothing at all.
 *
 * 🔴 THE PASSWORD IS NEVER HARD-CODED. This repository is public. It comes
 * from `TEST_KEYCLOAK_PASSWORD`, which `live-suite.sh` already exports.
 */

import { expect, test } from "@playwright/test";

const PASSWORD = process.env.TEST_KEYCLOAK_PASSWORD ?? "";
const USERNAME = process.env.TEST_SIGNIN_USER ?? "lead.demo";

/** The realm's own login form, whatever theme it is wearing. */
const USERNAME_FIELD = "#username, input[name='username']";
const PASSWORD_FIELD = "#password, input[name='password']";

test.describe("signing in through the real identity provider", () => {
  /**
   * 🔴 THE SKIP IS ON THIS TEST, NOT ON THE FILE.
   *
   * It used to sit at `describe` level, which skipped the callback guard
   * below with it — so in CI, where `TEST_KEYCLOAK_PASSWORD` is unset, BOTH
   * tests reported `skipped` and a green CI badge protected the sign-in flow
   * from nothing at all. A skip is not a pass, and a skip that takes an
   * unrelated test with it is worse: it is invisible.
   *
   * The round trip genuinely needs a live realm and a password. The guard
   * does not, so it runs everywhere.
   */
  test("a person can press Sign in, authenticate, and come back signed in", async ({
    page,
  }) => {
    test.skip(
      PASSWORD === "",
      "TEST_KEYCLOAK_PASSWORD is not set — the sign-in round trip was NOT verified",
    );
    await page.goto("/");

    // 1 — the control a human actually presses.
    const signIn = page.getByRole("button", { name: "Sign in" });
    await expect(
      signIn,
      "no Sign in button — the deployment may have no identity provider compiled in",
    ).toBeVisible();
    await signIn.click();

    // 2 — the browser must arrive at the REALM, not at a 404 and not back at
    // the application. A wrong `KEYCLOAK_URL` in the bundle lands somewhere
    // else entirely, and that is a compile-time value, so it fails here.
    await page.waitForURL(/\/realms\/[^/]+\/protocol\/openid-connect\/auth/, {
      timeout: 60_000,
    });

    // 3 — the realm accepted the redirect_uri. If the client is registered
    // against a different hostname, Keycloak renders "Invalid parameter:
    // redirect_uri" INSTEAD of the form — which is what a stale tunnel
    // registration looks like, and it is a 200, so only the form proves it.
    await expect(
      page.locator(USERNAME_FIELD),
      "no username field — the realm most likely rejected redirect_uri",
    ).toBeVisible({ timeout: 30_000 });

    await page.locator(USERNAME_FIELD).fill(USERNAME);
    await page.locator(PASSWORD_FIELD).fill(PASSWORD);
    await page.locator(PASSWORD_FIELD).press("Enter");

    // 4 — 🔴 BACK IN THE APPLICATION. This is the assertion that would have
    // failed on 2026-08-24 while everything else stayed green: the callback
    // is under `/auth/`, the identity proxy claims that prefix, and the round
    // trip dies on a 404 the moment the more specific route is lost.
    //
    // Waiting for the ORIGIN rather than a specific path, because the app may
    // legitimately land on `/`, `/dashboard/` or the deep link it started
    // from. What matters is that it is OUR page and not the realm's.
    await page.waitForURL(
      (url) => !/\/realms\/|\/protocol\/openid-connect\//.test(url.pathname),
      { timeout: 60_000 },
    );

    // 5 — and the application actually completed the exchange. `Sign in`
    // disappearing is the honest signal: the account menu only renders the
    // organization switcher once a session exists.
    await expect(
      page.getByRole("button", { name: "Sign in" }),
      "still showing Sign in — the callback was reached but the token " +
        "exchange did not complete",
    ).toBeHidden({ timeout: 60_000 });

    await expect(
      page.getByLabel("Active organization"),
      "no organization switcher — signed in but no organization resolved",
    ).toBeVisible({ timeout: 30_000 });
  });

  /**
   * The narrow regression guard for I96 — and it runs EVERYWHERE, including CI.
   *
   * It asks the deployment for its own callback path and requires the
   * APPLICATION to answer. No realm, no password, no browser session.
   *
   * ⚠️ WHAT IT PROVES DEPENDS ON WHERE IT RUNS, AND THAT IS WORTH BEING EXACT
   * ABOUT RATHER THAN LETTING A GREEN TICK IMPLY MORE THAN IT DOES:
   *
   *   - LIVE (`PLAYWRIGHT_BASE_URL` set, behind Caddy): this is the real I96
   *     guard. Caddy proxies `/auth/*` to Keycloak, and if the more specific
   *     `/auth/callback*` route is ever lost, Keycloak answers 404 and this
   *     fails. Verified by deliberately removing that route: 2 failed.
   *
   *   - CI / local (no proxy in front of Next): there is no Caddy to get
   *     wrong, so this does NOT exercise the proxy. What it still pins is
   *     that the application serves its own `CALLBACK_PATH` — a renamed or
   *     deleted `app/auth/callback/page.tsx`, or a `trailingSlash` change
   *     that stops `/auth/callback/` resolving, fails here. That is a real
   *     regression class and it is not the one I96 was.
   */
  test("the callback path is served by the app, not by the identity proxy", async ({
    request,
  }) => {
    const response = await request.get("/auth/callback/", {
      // The app answers 200, or 308 to the slash-less form under
      // `trailingSlash: false`. Keycloak answers 404. Follow redirects so
      // either shape of the app's own route counts as reaching the app.
      maxRedirects: 5,
    });

    expect(
      response.status(),
      "the OIDC callback did not reach the application — the identity proxy " +
        "is almost certainly claiming /auth/* including /auth/callback (I96)",
    ).toBe(200);

    const body = await response.text();
    expect(
      body,
      "the callback URL answered, but not with the application's page",
    ).toContain("EvercoatITWRD");
  });
});
