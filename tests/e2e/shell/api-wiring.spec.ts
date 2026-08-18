import { expect, test, type Page } from "@playwright/test";

/**
 * The web application talks to the API.
 *
 * WHY THIS FILE IS THE POINT OF THE WHOLE CHANGE
 * ----------------------------------------------
 * Until now, `playwright.config.ts` opened with a paragraph explaining
 * that the golden end-to-end scenario could not be written because
 * "`apps/web` makes no API calls at all — there is no `fetch`, no
 * `next-auth` wiring and no sign-in flow in the application today, so a
 * browser physically cannot drive the thread."
 *
 * That was true for three slices. Every one of the twelve pages rendered
 * `demo-data.json`, so the back end could have been deleted entirely and
 * every gate would have stayed green. These tests are what make the
 * statement false, and they are written to fail loudly if it becomes true
 * again.
 *
 * WHAT EACH TEST PROVES, AND WHAT IT DOES NOT
 * -------------------------------------------
 * The health probe crosses the browser/API boundary FOR REAL: a genuine
 * cross-origin request to a uvicorn process, answered by a real
 * PostgreSQL. Nothing is stubbed.
 *
 * The materials tests stub the API RESPONSE but not the request. What is
 * asserted is what the browser actually sent — the URL, the bearer token,
 * the organization header — which is the half that can be wrong. A real
 * authenticated round trip is impossible anywhere today because no
 * Keycloak is deployed, and a test that pretended otherwise would be
 * testing a fiction.
 */

const ORG = "11111111-1111-1111-1111-111111111111";

/**
 * Put the browser into an authenticated state.
 *
 * Uses the build-time seam described in `lib/api/session.ts`. It grants
 * nothing — the API validates every token independently — it only lets a
 * test reach the code paths that require a session to exist.
 *
 * `addInitScript` rather than `evaluate`, because the session has to be
 * set BEFORE React hydrates and issues its first query. Setting it
 * afterwards produces a race in which the assertion sometimes runs against
 * the anonymous first render.
 */
async function signIn(page: Page, token = "a-token-the-api-will-reject"): Promise<void> {
  await page.addInitScript(
    ([t, org]) => {
      const install = () => {
        const setSession = (window as unknown as Record<string, unknown>)
          .__evercoatSetSession as
          | ((s: {
              status: "authenticated";
              credentials: { token: string; organizationId: string };
            }) => void)
          | undefined;
        if (setSession) {
          setSession({
            status: "authenticated",
            credentials: { token: t as string, organizationId: org as string },
          });
          return true;
        }
        return false;
      };
      // The seam is installed when the session module first evaluates,
      // which is after this script runs. Poll briefly rather than assume
      // an ordering the bundler is free to change.
      if (!install()) {
        const timer = setInterval(() => {
          if (install()) clearInterval(timer);
        }, 10);
        setTimeout(() => clearInterval(timer), 5000);
      }
    },
    [token, ORG] as const,
  );
}

test.describe("the browser reaches the API", () => {
  test("the APPLICATION's own health probe reaches the API", async ({ page }) => {
    // NOTHING IS STUBBED. The request is issued by `ApiStatus` in the top
    // bar — the application's own code — to uvicorn, which queries
    // PostgreSQL. It is the first call this application has ever made to
    // its API, and it is provable today only because /health/ready needs
    // no token.
    //
    // Deliberately NOT `page.evaluate(fetch(...))`. That would prove the
    // browser can reach the API and say nothing about whether the
    // application does — which is the entire claim under test, and the
    // difference between a wired app and a wired test.
    await page.goto("/dashboard/");

    const status = page.getByTestId("api-status");
    await expect(status).toHaveAttribute("data-state", "reachable", {
      timeout: 15_000,
    });
    // `degraded` would mean the API answered 503 — reached, but reporting
    // a database problem. The E2E job provisions PostgreSQL, so that is a
    // real failure here rather than an acceptable alternative, and the
    // assertion above is exact rather than "not unreachable".
    await expect(status).toContainText(/API ready/i);
  });

  test("the status indicator says NO API when none was compiled in", async ({
    page,
  }) => {
    // The permanent state of the deployed static site. It must be visible
    // rather than absent: a missing indicator reads as "fine".
    //
    // Simulated by blocking the health endpoint rather than by rebuilding
    // without the variable — the build address is baked in at compile
    // time, so the reachable/unreachable distinction is the one a running
    // page can actually be driven through.
    await page.route("**/health/ready", (route) => route.abort());
    await page.goto("/dashboard/");

    await expect(page.getByTestId("api-status")).toHaveAttribute(
      "data-state",
      "unreachable",
      { timeout: 15_000 },
    );
  });

  test("CORS actually permits the web origin", async ({ page }) => {
    // Worth its own test because a CORS refusal surfaces in application
    // code as a bare TypeError with no detail — indistinguishable from the
    // network being down. If this breaks, every other test in this file
    // fails with a misleading message.
    //
    // 🔴 THE OBVIOUS ASSERTION IS IMPOSSIBLE, AND CI PROVED IT.
    //
    // The first version read `Access-Control-Allow-Origin` off the
    // response and compared it to the web origin. It came back `null` —
    // not because the header was missing, but because a browser exposes
    // only the CORS-SAFELISTED response headers to script (Cache-Control,
    // Content-Language, Content-Type, Expires, Last-Modified, Pragma).
    // `Access-Control-Allow-Origin` is not one of them and never will be
    // unless the server adds it to `Access-Control-Expose-Headers`.
    //
    // So the assertion was checking something the platform guarantees a
    // script cannot see, against an API that was working correctly.
    //
    // What actually proves CORS permits this origin is that the request
    // RESOLVES. A browser refuses a disallowed cross-origin response
    // before script sees it, and `fetch` rejects with a bare TypeError.
    // Reaching a status code at all is the permission.
    await page.goto("/dashboard/");

    const result = await page.evaluate(async () => {
      try {
        const response = await fetch("http://127.0.0.1:8100/health/ready", {
          credentials: "omit",
        });
        return { ok: true as const, status: response.status };
      } catch (error) {
        return { ok: false as const, message: String(error) };
      }
    });

    expect(result).toMatchObject({ ok: true, status: 200 });
  });
});

test.describe("the materials page", () => {
  test("shows demonstration data, and says so, when there is no session", async ({
    page,
  }) => {
    // The deployed state of the product today. It must be OBVIOUS, not
    // silent: a page of synthetic figures with no notice is
    // indistinguishable from a working one.
    await page.goto("/materials/");

    const banner = page.getByRole("note", { name: "Demonstration data notice" });
    await expect(banner).toBeVisible();
    await expect(banner).toContainText(/no identity provider is deployed/i);

    // And the grid still has rows, because the demonstration dataset is
    // bundled — an empty screen would be a worse answer than a labelled
    // synthetic one.
    await expect(page.getByText("RM-RES-01")).toBeVisible();
  });

  test("issues a real request with the bearer token AND the organization header", async ({
    page,
  }) => {
    // THE ASSERTION THAT ENDS "apps/web makes no API calls at all".
    //
    // The response is stubbed; the REQUEST is the application's own. Both
    // headers are checked because the API requires both — it answers 401
    // without the token and 400 without the organization — so a client
    // that sent one would fail in production while passing a test that
    // only looked for the other.
    await signIn(page);

    const seen: { authorization: string | null; organization: string | null }[] = [];
    await page.route("**/api/materials", async (route) => {
      const headers = route.request().headers();
      seen.push({
        authorization: headers["authorization"] ?? null,
        organization: headers["x-organization-id"] ?? null,
      });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "00000000-0000-0000-0000-000000000001",
            material_code: "RM-LIVE-01",
            name: "A material that only exists in the API",
            category: "Resin",
            role: "resin",
            status: "approved",
            density_g_cm3: "1.1000",
            solids_fraction: "0.6500",
            voc_fraction: "0.3500",
            solids_percent: "65.0000",
            voc_percent: "35.0000",
            cost_per_kg: "2.8000",
            cas_number: null,
            restriction_reason: null,
            requires_sds: true,
            hazard_summary: null,
            supplier_count: 2,
            updated_at: null,
          },
        ]),
      });
    });

    await page.goto("/materials/");

    // The row came from the API, so it cannot have come from the bundle:
    // this code appears nowhere in demo-data.json.
    await expect(page.getByText("RM-LIVE-01")).toBeVisible();
    await expect(
      page.getByRole("note", { name: "Data source notice" }),
    ).toContainText(/live data/i);

    expect(seen.length).toBeGreaterThan(0);
    expect(seen[0]?.authorization).toBe("Bearer a-token-the-api-will-reject");
    expect(seen[0]?.organization).toBe(ORG);
  });

  test("renders percentages the SERVER computed, not ones the browser derived", async ({
    page,
  }) => {
    // `0.35 * 100` is 35.000000000000004 in JavaScript, and a solids
    // content ends up on a technical datasheet. The engine sends the
    // percentage; the browser prints it.
    //
    // The stub deliberately sends a percentage that does NOT match its own
    // fraction. If the page ever starts deriving the figure itself, this
    // test fails — which no amount of reading the component would reveal.
    await signIn(page);
    await page.route("**/api/materials", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "00000000-0000-0000-0000-000000000002",
            material_code: "RM-CHECK-01",
            name: "Percentage provenance probe",
            category: "Filler",
            role: "filler",
            status: "approved",
            density_g_cm3: "2.7000",
            solids_fraction: "0.5000",
            voc_fraction: "0.0000",
            // Deliberately inconsistent with the fraction above.
            solids_percent: "77.7700",
            voc_percent: "0.0000",
            cost_per_kg: "0.4200",
            cas_number: null,
            restriction_reason: null,
            requires_sds: false,
            hazard_summary: null,
            supplier_count: 0,
            updated_at: null,
          },
        ]),
      }),
    );

    await page.goto("/materials/");

    await expect(page.getByText("77.7700 %")).toBeVisible();
    await expect(page.getByText("50 %")).toHaveCount(0);
  });

  test("a failed request shows the failure and NOT demonstration figures", async ({
    page,
  }) => {
    // The defect this whole layer is built to prevent. A page that fell
    // back to synthetic rows on an API error would make an outage
    // indistinguishable from a working product — and this project has
    // already shipped a screen where absence rendered as success.
    await signIn(page);
    await page.route("**/api/materials", (route) =>
      route.fulfill({ status: 500, contentType: "application/json", body: "{}" }),
    );

    await page.goto("/materials/");

    // `getByTestId`, not `getByRole("alert")`: Next.js renders its own
    // empty `role="alert"` route announcer on every page, so the role is
    // ambiguous here by construction.
    await expect(page.getByTestId("data-source-error")).toContainText(
      /could not be loaded/i,
    );
    // The demonstration dataset's first material must NOT appear. Its
    // presence would mean the page had silently substituted the bundle.
    await expect(page.getByText("RM-RES-01")).toHaveCount(0);
  });

  test("an unknown response shape is an error, not a page of blank cells", async ({
    page,
  }) => {
    // A renamed field would otherwise render as `undefined` in every cell,
    // which looks exactly like a library of materials with nothing
    // recorded. The client parses rather than casts, so this is a named
    // failure instead.
    await signIn(page);
    await page.route("**/api/materials", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([{ code: "renamed", title: "wrong shape" }]),
      }),
    );

    await page.goto("/materials/");

    await expect(page.getByTestId("data-source-error")).toContainText(/disagree/i);
  });
});
