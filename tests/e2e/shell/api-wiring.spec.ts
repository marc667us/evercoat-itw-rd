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

// ---------------------------------------------------------------------
// The screens S2 wired
// ---------------------------------------------------------------------
//
// 🔴 ONE PAGE PROVING THE SEAM DOES NOT PROVE THE OTHER FOUR USE IT.
//
// Before S2 only the materials page issued a real request, and these
// assertions existed only for it. Four more pages were then wired through
// the same hook — and "the same hook" is exactly the kind of claim that is
// true of four files and false of the fifth, because a page can import a
// hook and still render the fixture it was handed.
//
// So each newly wired screen is driven in a real browser: the request is
// intercepted, a row is returned whose identifiers appear NOWHERE in
// demo-data.json, and the page must show that row AND declare itself live.
// A page that quietly rendered the bundle would pass a test that only
// checked a request had been made.

test.describe("the screens wired in S2", () => {
  const LIVE_PROJECT = {
    id: "00000000-0000-0000-0000-0000000000a1",
    project_code: "RDP-LIVE-01",
    name: "A project that only exists in the API",
    product_family: "polyester filler",
    status: "active",
    priority: "high",
    current_stage: "development",
    confidentiality: "restricted",
    target_release_date: "2026-12-01",
  };

  const LIVE_FORMULA = {
    id: "00000000-0000-0000-0000-0000000000b1",
    formula_code: "FRM-LIVE-01",
    name: "A formula that only exists in the API",
    product_family: "polyester filler",
    status: "active",
    project_id: LIVE_PROJECT.id,
    project_code: LIVE_PROJECT.project_code,
    // NOT NULL in formulations.formulas, and the schema now enforces it.
    owner_user_id: "44444444-4444-4444-4444-444444444444",
    updated_at: "2026-08-01T10:00:00Z",
    latest_version_code: "FRM-LIVE-01-v7",
    latest_version_number: 7,
    latest_version_status: "draft",
    version_count: 7,
  };

  const LIVE_TASK = {
    id: "00000000-0000-0000-0000-0000000000c1",
    task_type: "approval",
    title: "A task that only exists in the API",
    description: null,
    priority: "high",
    status: "open",
    due_date: "2026-01-01",
    required_action: "Approve or return",
    entity_type: null,
    entity_id: null,
    project_id: LIVE_PROJECT.id,
    assigned_user_id: null,
    assigned_role: "product_development_lead",
    // NOT NULL in workflow.tasks.
    created_at: "2026-08-01T10:00:00Z",
    project_code: LIVE_PROJECT.project_code,
    project_name: LIVE_PROJECT.name,
    is_overdue: true,
  };

  const LIVE_SUPPLIER = {
    id: "00000000-0000-0000-0000-0000000000d1",
    supplier_code: "SUP-LIVE-01",
    name: "A supplier that only exists in the API",
    country: "DE",
    status: "approved",
    quality_rating: "A",
    contact_name: null,
    contact_email: null,
    material_count: 4,
    updated_at: null,
  };

  async function stub(page: Page, path: string, body: unknown): Promise<void> {
    await page.route(`**${path}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(body),
      });
    });
  }

  test("projects renders API rows and declares itself live", async ({ page }) => {
    await signIn(page);
    await stub(page, "/api/projects", [LIVE_PROJECT]);
    await page.goto("/projects/");

    await expect(page.getByText("RDP-LIVE-01")).toBeVisible();
    await expect(page.getByRole("note", { name: "Data source notice" })).toContainText(
      /live data/i,
    );
    // Confidentiality is rendered because it changes who can see the row
    // at all — a reader comparing two lists must be able to tell why a
    // colleague sees a different number of projects.
    await expect(page.getByText("RESTRICTED")).toBeVisible();
  });

  test("formulations shows the LATEST version WITH its own status", async ({ page }) => {
    // 🔴 The index leads with the latest version, which §8 says is often an
    // unapproved draft. The badge is what stops that reading as approval,
    // so assert the badge and not merely the version code.
    await signIn(page);
    await stub(page, "/api/formulations", [LIVE_FORMULA]);
    await page.goto("/formulations/");

    await expect(page.getByText("FRM-LIVE-01", { exact: true })).toBeVisible();
    await expect(page.getByText(/FRM-LIVE-01-v7 . DRAFT/)).toBeVisible();
  });

  test("my work separates unclaimed role work from your own", async ({ page }) => {
    // `assigned_user_id: null` is unclaimed role work. It must appear under
    // the unclaimed heading and NOT under "Assigned to you" — putting it in
    // both is how five people end up working the same item.
    await signIn(page);
    await stub(page, "/api/my-work", [LIVE_TASK]);
    await page.goto("/my-work/");

    await expect(
      page.getByRole("table", { name: /Unclaimed tasks addressed to your role/i }),
    ).toContainText("A task that only exists in the API");
    // 🔴 A POSITIVE ASSERTION, NOT `.not.toContainText`.
    //
    // The first version asserted the "Assigned to you" table did NOT
    // contain the task -- and that table does not RENDER at all when it is
    // empty, so the locator resolved to nothing and the assertion failed
    // for the wrong reason. Worse, had the grid rendered an empty table,
    // `.not.toContainText` would have passed whether the row was misfiled
    // or the section was simply broken. Assert the empty state by name.
    await expect(page.getByText("Nothing assigned to you.")).toBeVisible();
  });

  test("my work shows the SERVER's overdue verdict, not one it derived", async ({ page }) => {
    // due_date is 2026-01-01 and is_overdue is true. The browser takes the
    // server's word: re-deriving it crosses a time-zone boundary and
    // produces a page that disagrees with the database.
    await signIn(page);
    await stub(page, "/api/my-work", [LIVE_TASK]);
    await page.goto("/my-work/");

    await expect(page.getByText(/2026-01-01 . OVERDUE/)).toBeVisible();
  });

  test("suppliers says the sole-source analysis was NOT run", async ({ page }) => {
    // 🔴 THE MOST IMPORTANT ASSERTION ON THAT SCREEN. The live endpoint
    // returns a count, not names, so the risk cannot be computed — and a
    // supplier showing no flag must never be read as "not sole-sourced".
    // An absence of analysis has to be stated, not inferred from an absent
    // badge.
    await signIn(page);
    await stub(page, "/api/suppliers", [LIVE_SUPPLIER]);
    await page.goto("/suppliers/");

    await expect(page.getByText("SUP-LIVE-01")).toBeVisible();
    await expect(
      page.getByRole("note", { name: "Sole-source analysis not available" }),
    ).toContainText(/not computed on this screen/i);
  });

  test("a failed request shows the failure on EVERY wired screen", async ({ page }) => {
    // The rule the whole seam exists for: a request that was MADE and
    // failed must not fall back to demonstration rows. Asserted per page,
    // because the fallback is decided per page.
    await signIn(page);
    const screens = [
      ["/api/projects", "/projects/"],
      ["/api/formulations", "/formulations/"],
      ["/api/my-work", "/my-work/"],
      ["/api/suppliers", "/suppliers/"],
    ] as const;

    for (const [path, url] of screens) {
      await page.route(`**${path}`, (route) =>
        route.fulfill({ status: 500, contentType: "application/json", body: "{}" }),
      );
      await page.goto(url);
      await expect(page.getByTestId("data-source-error")).toBeVisible();
    }
  });
});
