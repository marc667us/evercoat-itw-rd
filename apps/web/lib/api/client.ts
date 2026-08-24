/**
 * The one place this application talks to the API.
 *
 * Until now `apps/web` made **no API calls at all** — no `fetch`, no
 * `next-auth` wiring, no sign-in — and every one of its twelve pages
 * rendered `demo-data.json`. `playwright.config.ts` says so in its own
 * header, and it is why the golden end-to-end scenario could not be
 * written: a browser had no means of driving the digital thread.
 *
 * WHAT THIS MODULE REFUSES TO DO
 * ------------------------------
 * It never falls back. A failed request raises a typed error and the
 * caller decides what to show; it does not quietly substitute
 * demonstration data, an empty array, or a zero. Every one of those would
 * render as a working screen, which is the failure mode this project has
 * hit repeatedly — `Number("")` is 0, and a blank measurement once
 * rendered a GREEN PASS.
 *
 * It never retries a 401 or a 403. An expired session and a forbidden
 * resource are answers, not transient faults, and retrying them turns one
 * refusal into four.
 *
 * WHAT IT ALWAYS SENDS
 * --------------------
 * `Authorization: Bearer <token>` and `X-Organization-Id`. The API
 * requires BOTH — `get_principal` refuses with 401 for a missing token
 * and 400 for a missing organization header, and it validates the
 * requested organization against real membership rather than trusting it.
 * A request built here without both is a request that cannot succeed, so
 * the types make it impossible to build one.
 */

import { API_BASE_URL } from "./config";

/** Base class, so a caller can catch everything from this layer at once. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
    readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * The build has no API address. Distinct from every other failure because
 * it is not a fault: it is the normal state of the static deployment, and
 * the caller should show the demonstration dataset with a banner rather
 * than an error.
 */
export class ApiNotConfiguredError extends ApiError {
  constructor() {
    super("no API address was compiled into this build", null);
    this.name = "ApiNotConfiguredError";
  }
}

/**
 * There is no session to authorize with. Distinct from a 401: nothing was
 * sent, so nothing was rejected. Showing "access denied" for this would
 * be a lie about what happened.
 */
export class ApiNoSessionError extends ApiError {
  constructor(readonly reason: string) {
    super(reason, null);
    this.name = "ApiNoSessionError";
  }
}

/** 401 or 403 — the request was made and refused. */
export class ApiAuthError extends ApiError {
  constructor(status: number, detail?: unknown) {
    super(
      status === 401
        ? "the API did not accept this session"
        : "this account is not permitted to see that",
      status,
      detail,
    );
    this.name = "ApiAuthError";
  }
}

/** The request never reached the API: DNS, CORS, offline, refused. */
export class ApiUnreachableError extends ApiError {
  constructor(cause: unknown) {
    super("the API could not be reached", null, cause);
    this.name = "ApiUnreachableError";
  }
}

/** The response arrived but was not the shape the caller expected. */
export class ApiShapeError extends ApiError {
  constructor(path: string, detail: unknown) {
    super(
      `the API returned something ${path} did not expect — the client and the ` +
        "server disagree about this endpoint",
      null,
      detail,
    );
    this.name = "ApiShapeError";
  }
}

/** The credentials every authenticated call needs. Both, or neither. */
export interface ApiCredentials {
  readonly token: string;
  readonly organizationId: string;
  /**
   * Who the token belongs to.
   *
   * 🔴 NOT SENT ON THE WIRE. It exists so a cached response cannot cross
   * users: the query key was `[resource, organizationId]`, so Alice could
   * load My Work, sign out, and Bob could sign in to the SAME
   * organization and be served Alice's tasks out of the cache, under a
   * LIVE banner, until a refetch replaced them. If the refetch stalled,
   * they stayed. Codex found it.
   *
   * The API still decides everything from the token; this only scopes the
   * browser's cache.
   */
  readonly userId: string;
}

export interface ApiRequest {
  readonly path: string;
  readonly method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  readonly body?: unknown;
  readonly credentials: ApiCredentials;
  readonly signal?: AbortSignal;
}

/**
 * Issue one authenticated request.
 *
 * `parse` is required rather than optional, and it is why the return type
 * is trustworthy. Without it this would return `any` dressed as `T`, and a
 * server that renamed a field would surface as `undefined` rendering into
 * a blank cell — the exact "absence presenting as a value" failure the
 * layer exists to prevent. With it, a shape change is a NAMED error on the
 * screen that consumes it.
 */
export async function apiRequest<T>(
  request: ApiRequest,
  parse: (payload: unknown) => T,
): Promise<T> {
  if (API_BASE_URL === null) {
    throw new ApiNotConfiguredError();
  }

  const url = `${API_BASE_URL}${request.path}`;
  const headers: Record<string, string> = {
    Accept: "application/json",
    Authorization: `Bearer ${request.credentials.token}`,
    // Required by the API on EVERY authenticated route. A user may belong
    // to several organizations, so the active one is a request that the
    // server validates against membership -- never a claim it trusts.
    "X-Organization-Id": request.credentials.organizationId,
  };
  if (request.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method: request.method ?? "GET",
      headers,
      body: request.body === undefined ? undefined : JSON.stringify(request.body),
      signal: request.signal,
      // No cookies. This API authenticates by bearer token only, and
      // sending credentials would make every response subject to CORS
      // credential rules for no benefit.
      credentials: "omit",
      // `no-store`, because a formulation is a controlled record and a
      // cached copy of one is a second, stale source of truth.
      cache: "no-store",
    });
  } catch (cause) {
    // A CORS refusal reaches here as an ordinary TypeError with no detail,
    // indistinguishable from the network being down. Both mean the same
    // thing to the reader — the API could not be reached — so they are
    // reported as one state rather than guessed between.
    throw new ApiUnreachableError(cause);
  }

  if (response.status === 401 || response.status === 403) {
    throw new ApiAuthError(response.status, await readDetail(response));
  }

  if (!response.ok) {
    throw new ApiError(
      `the API refused this request (${response.status})`,
      response.status,
      await readDetail(response),
    );
  }

  if (response.status === 204) {
    return parse(null);
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch (cause) {
    throw new ApiShapeError(request.path, cause);
  }

  try {
    return parse(payload);
  } catch (cause) {
    throw new ApiShapeError(request.path, cause);
  }
}

/**
 * An UNAUTHENTICATED probe of the API's health endpoint.
 *
 * Separate from `apiRequest` on purpose: it takes no credentials, because
 * `/health/*` takes none. Folding it into the authenticated path would
 * have meant inventing a token for it, and a client that can build a
 * request with no real credentials is a client that will eventually send
 * one somewhere that matters.
 *
 * It exists because it is the ONLY end-to-end proof available today. There
 * is no deployed Keycloak, so no authenticated call can succeed anywhere —
 * but this one crosses the browser/API boundary for real, which is the
 * thing that had never once happened in this application.
 */
export async function apiHealth(
  signal?: AbortSignal,
): Promise<{ reachable: boolean; status: number | null; detail: string }> {
  if (API_BASE_URL === null) {
    return {
      reachable: false,
      status: null,
      detail: "no API address was compiled into this build",
    };
  }
  try {
    const response = await fetch(`${API_BASE_URL}/health/ready`, {
      signal,
      cache: "no-store",
      credentials: "omit",
    });
    // NOT `response.ok`. `/health/ready` answers 503 when the database is
    // unreachable, and that is a REACHED api reporting a real problem --
    // treating it as unreachable would blame the network for a database
    // fault. The status is carried through so the caller can say which.
    return {
      reachable: true,
      status: response.status,
      detail:
        response.status === 200
          ? "the API is reachable and reports itself ready"
          : `the API is reachable and reports ${response.status}`,
    };
  } catch {
    return {
      reachable: false,
      status: null,
      detail: "the API could not be reached from this browser",
    };
  }
}

/** Best-effort detail from an error response; never throws. */
/**
 * What the SERVER said, not what this client guessed.
 *
 * 🔴 THE SENTENCE WAS BEING THROWN AWAY WHILE FOUR SCREENS CLAIMED TO SHOW IT.
 *
 * `apiRequest` throws `ApiError` with a generic message — "the API refused
 * this request (422)" — and puts the server's own explanation in `detail`,
 * which nothing read. So a formulation screen rendered `error.message` under a
 * comment saying *"the server's own sentence … explains why"*, and displayed
 * the status code instead. The test workspace did the same under *"a 403 is
 * surfaced as the sentence the server sent"*, losing the ADR-019
 * segregation-of-duties distinction that is the entire reason a 403 there is
 * interesting. Found by the Supervisor; it is this codebase's most-repeated
 * defect — a comment asserting a rule the code does not have.
 *
 * FastAPI's `detail` takes three shapes here and all three matter:
 *
 *   "a plain sentence"                          — most routes
 *   {"message": "...", "blocks": [{...}, ...]}  — a blocked submission, whose
 *                                                 blocks were discarded entirely
 *   undefined                                   — a non-JSON body
 *
 * Falls back to the generic message rather than inventing one, so a caller
 * always has something to render.
 */
export function serverMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return error instanceof Error ? error.message : String(error);
  }

  const detail = (error.detail as { detail?: unknown } | undefined)?.detail ?? error.detail;

  if (typeof detail === "string" && detail.trim() !== "") {
    return detail;
  }

  if (detail !== null && typeof detail === "object") {
    const shaped = detail as { message?: unknown; blocks?: unknown };
    const message = typeof shaped.message === "string" ? shaped.message : null;
    // EVERY block, not the first. The route says so itself: returning one
    // "would make the chemist discover them one request at a time, which is
    // how a form teaches people to distrust it."
    const blocks = Array.isArray(shaped.blocks)
      ? shaped.blocks
          .map((b) => {
            const row = b as { code?: unknown; message?: unknown };
            const code = typeof row.code === "string" ? row.code : null;
            const text = typeof row.message === "string" ? row.message : null;
            return code && text ? `${code} — ${text}` : (text ?? code);
          })
          .filter((line): line is string => typeof line === "string")
      : [];

    if (message !== null && blocks.length > 0) {
      return `${message}: ${blocks.join("; ")}`;
    }
    if (message !== null) return message;
    if (blocks.length > 0) return blocks.join("; ");
  }

  return error.message;
}

async function readDetail(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return undefined;
  }
}
