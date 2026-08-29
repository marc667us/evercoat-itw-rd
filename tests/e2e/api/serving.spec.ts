import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

/**
 * The API under a real ASGI server, over real HTTP.
 *
 * The 152-test Python suite drives the application through Starlette's
 * `TestClient`, which calls the ASGI app in-process. That is the right
 * tool for domain and authorization logic, and it does not prove the
 * thing this file proves: that the process starts, binds a port and
 * serves.
 *
 * The distinction is not theoretical here. This application has already
 * failed to start twice while its type-check, its lint and its entire
 * unit suite were green — once because a dependency was missing at
 * class-definition time, once because structlog raised on the first log
 * line, before a port was ever bound. Neither was visible to TestClient.
 *
 * These tests are deliberately UNAUTHENTICATED. There is no Keycloak on
 * this host for this application, and standing one up would mean adding a
 * ninth container to a Docker VM that has already OOM-killed one — or
 * borrowing the AutoWorkshop realm, which is off limits. Refusal is
 * therefore what gets asserted, and refusal is worth asserting: a route
 * that forgets its dependency answers 200 to an anonymous caller.
 */

test.describe("the server is actually serving", () => {
  test("liveness answers without touching the database", async ({ request }) => {
    const response = await request.get("/health/live");
    expect(response.status()).toBe(200);
    expect(await response.json()).toMatchObject({ status: "alive" });
  });

  test("readiness reports the real state of the database", async ({ request }) => {
    const response = await request.get("/health/ready");
    const body = await response.json();

    expect(body).toHaveProperty("status");

    // Where a database is guaranteed — CI provisions one as a service
    // container — 503 means something is genuinely broken and must fail
    // the run. Accepting 503 unconditionally, as this first did, meant a
    // wrong DATABASE_URL or an unapplied migration left the suite green:
    // it tested the endpoint's response SHAPE while claiming to test the
    // database's state.
    if (process.env.E2E_REQUIRE_DB_READY === "1") {
      expect(
        response.status(),
        `readiness returned ${response.status()} while a database was ` +
          `guaranteed to be available: ${JSON.stringify(body)}`,
      ).toBe(200);
      return;
    }

    // Locally there may genuinely be no database, so both answers are
    // legitimate — but which one occurred is recorded, so a green run is
    // still diagnosable.
    expect([200, 503]).toContain(response.status());
    test.info().annotations.push({
      type: "readiness",
      description:
        response.status() === 200
          ? "200 — database reachable"
          : `503 — database NOT reachable: ${JSON.stringify(body)}`,
    });
  });

  test("metrics are exposed for scraping", async ({ request }) => {
    const response = await request.get("/metrics");
    expect(response.status()).toBe(200);
    // Prometheus text exposition, not JSON.
    expect(await response.text()).toContain("# HELP");
  });
});

test.describe("authentication is enforced at the edge", () => {
  const PROTECTED = [
    "/api/projects",
    "/api/opportunities",
    "/api/my-work",
    "/api/admin/roles",
    "/api/admin/stage-gates",
  ];

  for (const path of PROTECTED) {
    test(`${path} refuses an anonymous caller`, async ({ request }) => {
      const response = await request.get(path);
      expect(
        response.status(),
        `${path} answered an anonymous request — a route that forgot its ` +
          `dependency looks entirely normal in review`,
      ).toBe(401);
    });
  }

  test("credentials that cannot be verified never grant access", async ({ request }) => {
    const response = await request.get("/api/projects", {
      headers: { Authorization: "Bearer not-a-jwt" },
    });

    // This first ran expecting a flat 401 and got 503, which turned out to
    // be the API being MORE honest than the test.
    //
    // An anonymous request short-circuits at "no credentials" and is 401.
    // A request that DOES carry a token reaches signature verification,
    // which needs the realm's JWKS — and this suite deliberately points
    // at an issuer that resolves to nothing, so the keys cannot be
    // fetched. 503 "identity provider unavailable" is the truthful answer
    // there: 401 would assert "your token is invalid" when the API means
    // "I am unable to check".
    //
    // So the assertion is the property that must hold either way, rather
    // than a status code that silently encodes whether Keycloak happened
    // to be up: an unverifiable credential is never accepted.
    expect(
      response.status(),
      "a token that could not be verified was accepted",
    ).not.toBe(200);
    expect([401, 503]).toContain(response.status());

    // Recorded so a reader of a green run can tell which regime it ran
    // under. With a reachable Keycloak this becomes 401.
    test.info().annotations.push({
      type: "auth",
      description:
        response.status() === 503
          ? "503 — no reachable identity provider, so signature verification could not run"
          : "401 — the identity provider was reachable and rejected the token",
    });
  });

  test("an anonymous caller is refused as unauthenticated, never as a bad request", async ({
    request,
  }) => {
    // Scope, stated honestly: this proves ORDERING for an anonymous
    // caller — authentication is decided before the organization header
    // is read, so a missing header cannot become a way to probe which
    // organizations exist.
    //
    // It does NOT prove that an AUTHENTICATED caller without
    // `X-Organization-Id` is refused. That needs a signed token, which
    // needs a reachable Keycloak, which this host does not have for this
    // application. It is covered where tokens can be minted:
    // apps/api/tests/auth/test_token_verification.py. An earlier version
    // of this test claimed the authenticated case and would have passed
    // even if it were broken.
    const response = await request.get("/api/projects");
    expect(response.status()).toBe(401);
    expect(response.status()).not.toBe(400);
  });

  test("the error body does not leak whether a resource exists", async ({ request }) => {
    const real = await request.get("/api/projects");
    const fabricated = await request.get(
      "/api/projects/00000000-0000-4000-8000-000000000000/dashboard",
    );

    expect(real.status()).toBe(401);
    expect(fabricated.status()).toBe(401);

    // The BODIES are the point, and comparing only status codes was the
    // defect in the first version of this test: both could answer 401
    // while one body said "not found" and the other said "forbidden",
    // which is exactly the discovery channel being guarded against.
    // "You may not see it" and "it does not exist" must be
    // indistinguishable to the caller.
    expect(await fabricated.json()).toEqual(await real.json());
  });
});

test.describe("the route surface is what the application claims", () => {
  test("OpenAPI is served and carries the product identity", async ({ request }) => {
    const response = await request.get("/openapi.json");
    expect(response.status()).toBe(200);

    const schema = await response.json();
    expect(schema.info.title).toContain("EvercoatITWRD");
    expect(JSON.stringify(schema.info)).not.toMatch(/ITERDRD/i);
  });

  test("the Slice 2 write paths are registered and reachable", async ({ request }) => {
    // These are the endpoints whose absence made two dashboard counters
    // structurally incapable of being non-zero. A route present in the
    // schema is not proof it works, but a route ABSENT from the schema is
    // proof it does not — and that is the failure being guarded against.
    const schema = await (await request.get("/openapi.json")).json();
    const paths = Object.keys(schema.paths);

    const required = [
      "/api/projects/{project_id}/milestones",
      "/api/projects/{project_id}/milestones/{milestone_id}/status",
      "/api/projects/{project_id}/risks",
      "/api/projects/{project_id}/risks/{risk_id}",
      "/api/projects/{project_id}/members",
      "/api/projects/{project_id}/members/{user_id}/remove",
    ];

    for (const path of required) {
      expect(paths, `${path} is missing from the served OpenAPI schema`).toContain(path);
    }
  });

  test("every registered API operation declares authentication, including writes", async ({
    request,
  }) => {
    // The probing test below can only safely exercise GET. That left 26
    // POST/PUT/PATCH/DELETE operations completely uncovered, so a mutation
    // route shipped without its permission dependency would not have been
    // caught by anything here.
    //
    // Reading each operation's declared security out of the OpenAPI
    // schema covers every method without writing a single row. It is a
    // weaker signal than a live probe — it proves the dependency is
    // DECLARED, not that it refuses — but paired with the live GET sweep
    // below, a route has to fail both to slip through.
    const schema = await (await request.get("/openapi.json")).json();
    const WRITE = ["post", "put", "patch", "delete"];

    const undeclared: string[] = [];
    let writeOps = 0;

    for (const [path, ops] of Object.entries<Record<string, any>>(schema.paths)) {
      if (!path.startsWith("/api/")) continue;

      for (const [method, op] of Object.entries<any>(ops)) {
        if (!WRITE.includes(method) && method !== "get") continue;
        if (WRITE.includes(method)) writeOps += 1;

        // FastAPI emits `security` on an operation whose dependency tree
        // includes a security scheme — which for this app means the
        // HTTPBearer behind get_principal, and therefore the whole
        // authorization chain.
        const declared = op.security ?? schema.security;
        if (!declared || declared.length === 0) {
          undeclared.push(`${method.toUpperCase()} ${path}`);
        }
      }
    }

    // Guard against the schema shape changing underneath this test and
    // quietly reducing it to zero assertions.
    expect(writeOps, "no write operations found — this test stopped testing").toBeGreaterThan(0);
    expect(undeclared, "these API operations declare no authentication").toEqual([]);
  });

  /**
   * 🔴 EVERY PATH THE BROWSER CALLS MUST BE A PATH THE SERVER SERVES.
   *
   * `createTask` posted to `/api/tasks` for as long as it existed. The router
   * is mounted at `/api/my-work` -- `main.py` names the SCREEN, not the table
   * -- so every press returned 404, and two more clients written beside it
   * inherited the same wrong base. Nothing below the browser was wrong, and
   * nothing caught it: `typecheck` sees a string, vitest stubs the response,
   * and a 404 from a path that does not exist looks exactly like a refusal
   * from one that does.
   *
   * This reads the client source and the SERVED OpenAPI. It needs no session:
   * whether a route exists is not a question about who is asking.
   *
   * ⚠️ IT COMPARES SHAPES, NOT STRINGS. A client path is a template literal
   * (`/api/materials/${id}/documents`); OpenAPI writes `{material_id}`. Both
   * collapse to a placeholder so the comparison is about the ROUTE, and a
   * renamed path parameter is correctly not a failure.
   */
  test("every path the web client calls is a path the API serves", async ({ request }) => {
    const spec = await (await request.get("/openapi.json")).json();
    const served = new Set(
      Object.keys(spec.paths as Record<string, unknown>).map((p) =>
        p.replace(/\{[^}]*\}/g, "{}"),
      ),
    );

    const clientDir = join(__dirname, "..", "..", "..", "apps", "web", "lib", "api");
    const files = readdirSync(clientDir).filter(
      (f) => f.endsWith(".ts") && !f.includes(".test."),
    );
    expect(files.length, "no client modules found — has lib/api moved?").toBeGreaterThan(5);

    const called = new Map<string, string>();
    for (const file of files) {
      const source = readFileSync(join(clientDir, file), "utf8");
      // `path: "/api/x"` and `path: `/api/x/${id}`` alike.
      for (const m of source.matchAll(/path:\s*[`"]([^`"]*)[`"]/g)) {
        const raw = m[1];
        if (raw === undefined || !raw.startsWith("/api")) continue;
        // The query string is not part of the route. Four clients carry one
        // inline (`/api/knowledge/search?q=${term}`), and comparing it against
        // OpenAPI -- which keys on the path alone -- reported four routes as
        // missing that are served perfectly well.
        const route = raw.split("?")[0] ?? raw;
        called.set(route.replace(/\$\{[^}]*\}/g, "{}"), file);
      }
    }
    expect(called.size, "no /api paths parsed out of the client").toBeGreaterThan(20);

    const missing = [...called.entries()]
      .filter(([path]) => !served.has(path))
      .map(([path, file]) => `${path}  (${file})`);
    expect(
      missing,
      "the browser calls these and the API does not serve them — every press is a 404",
    ).toEqual([]);
  });

  test("every registered API GET refuses an anonymous caller", async ({ request }) => {
    // A property over the whole surface rather than a maintained list, so
    // a new route added without its permission dependency fails here
    // instead of shipping. Health and metrics are excluded because they
    // are deliberately public; anything else answering anonymously is a
    // finding.
    const schema = await (await request.get("/openapi.json")).json();

    const unprotected: string[] = [];

    for (const [path, methods] of Object.entries<Record<string, unknown>>(schema.paths)) {
      if (!path.startsWith("/api/")) continue;
      if (!("get" in methods)) continue;
      // Only GETs are probed: a POST/PATCH that answered anonymously
      // would be a far worse finding, but probing them blind would write
      // data if one of them were open.
      const probe = path
        .replace(/\{[^}]+\}/g, "00000000-0000-4000-8000-000000000000");
      const response = await request.get(probe);
      if (response.status() !== 401) {
        unprotected.push(`${probe} → ${response.status()}`);
      }
    }

    expect(unprotected, "these API routes answered an anonymous GET").toEqual([]);
  });
});
