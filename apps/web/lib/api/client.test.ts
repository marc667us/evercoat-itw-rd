/**
 * The API client's refusals.
 *
 * Almost every test here asserts that something does NOT happen: no
 * fallback, no substituted empty array, no silently-cast response. Those
 * are the behaviours that keep a broken screen looking broken, and they
 * are invisible in a diff — a future edit that adds a `catch { return [] }`
 * would look like defensive programming and would reintroduce this
 * project's single most-repeated defect, a screen of plausible figures
 * indistinguishable from a working one.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiAuthError,
  ApiError,
  ApiShapeError,
  ApiUnreachableError,
  apiRequest,
  type ApiCredentials,
} from "./client";

// The module reads `NEXT_PUBLIC_API_BASE_URL` at import time, so the test
// environment sets it before importing. `vitest.config` does not, which is
// why this is stubbed per-file rather than assumed.
vi.mock("./config", () => ({
  API_BASE_URL: "https://api.test",
  isApiConfigured: true,
  API_UNCONFIGURED_REASON: "unconfigured",
}));

const credentials: ApiCredentials = {
  token: "a-token",
  organizationId: "11111111-1111-1111-1111-111111111111",
  userId: "00000000-0000-0000-0000-0000000000ff",
};

/**
 * The arguments of the single fetch this suite made.
 *
 * Written as a helper that THROWS when there was no call, rather than as
 * `mock.calls[0]!`. A non-null assertion would turn "the client never
 * issued a request" — the most important failure this file can catch —
 * into a confusing undefined-property error several lines later.
 */
function lastFetch(): { url: string; init: RequestInit } {
  const mock = globalThis.fetch as unknown as { mock: { calls: unknown[][] } };
  const call = mock.mock.calls[0];
  if (call === undefined) {
    throw new Error("the client made no request at all");
  }
  return { url: String(call[0]), init: (call[1] ?? {}) as RequestInit };
}

function respond(body: unknown, init: ResponseInit = {}): void {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(body === null ? null : JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
        ...init,
      }),
    ),
  );
}

/**
 * Run something that must reject, and return what it rejected with.
 *
 * Fails loudly if it RESOLVES. `await fn().catch(e => e)` would quietly
 * return the resolved value instead, so a client that stopped throwing
 * would pass every assertion below by handing back a successful response
 * object — a test that cannot fail in the one direction it exists to
 * check.
 */
async function captureError(fn: () => Promise<unknown>): Promise<Error> {
  try {
    await fn();
  } catch (error) {
    return error as Error;
  }
  throw new Error("expected the call to be refused, and it succeeded");
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiRequest", () => {
  it("sends BOTH the bearer token and the organization header", async () => {
    // The API requires both: `get_principal` answers 401 without a token
    // and 400 without X-Organization-Id. A request missing either cannot
    // succeed, so the client must never build one.
    respond([]);

    await apiRequest({ path: "/api/materials", credentials }, (p) => p);

    const { url, init } = lastFetch();
    expect(url).toBe("https://api.test/api/materials");
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer a-token");
    expect(headers["X-Organization-Id"]).toBe(credentials.organizationId);
  });

  it("never sends cookies", async () => {
    // Bearer-token authentication only. Sending credentials would put
    // every response under CORS credential rules for no benefit, and
    // invites a future reader to assume a cookie session exists.
    respond([]);
    await apiRequest({ path: "/api/materials", credentials }, (p) => p);
    const { init } = lastFetch();
    expect(init.credentials).toBe("omit");
    expect(init.cache).toBe("no-store");
  });

  it("raises ApiAuthError on 401 rather than returning nothing", async () => {
    respond({ detail: "missing bearer token" }, { status: 401 });

    await expect(
      apiRequest({ path: "/api/materials", credentials }, (p) => p),
    ).rejects.toBeInstanceOf(ApiAuthError);
  });

  it("raises ApiAuthError on 403, and says something different from 401", async () => {
    // "Not signed in" and "not allowed" are different answers and a reader
    // needs to know which one they got: one is fixed by signing in again
    // and the other never is.
    respond({ detail: "Not permitted" }, { status: 403 });

    const error = await captureError(() =>
      apiRequest({ path: "/api/materials", credentials }, (p) => p),
    );

    expect(error).toBeInstanceOf(ApiAuthError);
    expect((error as ApiAuthError).status).toBe(403);
    expect(error.message).not.toContain("session");
  });

  it("raises on any other non-2xx, carrying the status", async () => {
    respond({ detail: "boom" }, { status: 500 });

    const error = await captureError(() =>
      apiRequest({ path: "/api/materials", credentials }, (p) => p),
    );

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(500);
  });

  it("reports an unreachable API rather than an empty result", async () => {
    // A CORS refusal arrives as a bare TypeError, indistinguishable from
    // the network being down. Both must surface; neither may become [].
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(
      apiRequest({ path: "/api/materials", credentials }, (p) => p),
    ).rejects.toBeInstanceOf(ApiUnreachableError);
  });

  it("raises ApiShapeError when the response is not what the caller expected", async () => {
    // THE TEST THIS LAYER EXISTS FOR. A server that renamed a field hands
    // back rows whose value is `undefined`, and a cast would let that
    // render as a column of blank cells — which looks exactly like a
    // library of materials with nothing recorded.
    respond([{ unexpected: true }]);

    await expect(
      apiRequest({ path: "/api/materials", credentials }, () => {
        throw new Error("field `material_code` is missing");
      }),
    ).rejects.toBeInstanceOf(ApiShapeError);
  });

  it("raises ApiShapeError when the body is not JSON at all", async () => {
    // A proxy returning an HTML error page is the classic case: status
    // 200, content-type lying, body unparseable.
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<html>gateway</html>", {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(
      apiRequest({ path: "/api/materials", credentials }, (p) => p),
    ).rejects.toBeInstanceOf(ApiShapeError);
  });

  it("does not swallow an error response whose body is unreadable", async () => {
    // `readDetail` must not throw and must not turn a 500 into a success.
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("not json", { status: 502 })),
    );

    const error = await captureError(() =>
      apiRequest({ path: "/api/materials", credentials }, (p) => p),
    );

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(502);
  });
});
