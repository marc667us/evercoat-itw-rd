/**
 * The Authorization Code flow with PKCE, as pure functions.
 *
 * 🔴 WHY THIS IS HAND-WRITTEN AND NOT A LIBRARY
 *
 * The whole flow is four operations — make a verifier, hash it, build a
 * URL, exchange a code — and every one of them is specified exactly by
 * RFC 7636. A dependency here would be a supply-chain surface sitting
 * directly on the credential path, in an application whose seventh
 * non-negotiable rule is a zero-cost open-source core. It is written out,
 * commented, and unit-tested instead.
 *
 * 🔴 WHAT PKCE IS ACTUALLY DEFENDING AGAINST
 *
 * A public client cannot keep a secret — anything shipped to a browser is
 * readable. So the authorization code alone must not be enough to obtain
 * a token, or anyone who intercepts the redirect (a malicious extension,
 * a shared machine's history, a referrer leak) can exchange it.
 *
 * PKCE fixes that by having the client invent a high-entropy secret per
 * attempt, send only its SHA-256 hash up front, and reveal the secret
 * only when redeeming the code. An intercepted code is useless without
 * the verifier, which never left this browser.
 *
 * The realm mandates `S256`. **`plain` is not implemented here and must
 * not be added**: it sends the verifier in the authorization request,
 * which defeats the entire mechanism while still being called PKCE.
 *
 * 🔴 `state` IS A SEPARATE DEFENCE AND IS NOT OPTIONAL
 *
 * PKCE proves the token request came from whoever started the flow. It
 * says nothing about whether THIS page started it. Without `state`, an
 * attacker can feed a victim's browser their own authorization code and
 * silently sign the victim into the ATTACKER's account — after which
 * everything the victim does is recorded against it. Both are checked.
 */

/** One attempt's secrets. Created before the redirect, used once after it. */
export interface PkceChallenge {
  /** The high-entropy secret. Never sent until the token exchange. */
  readonly verifier: string;
  /** Its SHA-256, base64url-encoded. Sent in the authorization request. */
  readonly challenge: string;
  /** Ties the callback to this page's request. */
  readonly state: string;
  // 🔴 THERE IS DELIBERATELY NO `nonce`.
  //
  // One was generated, sent on the wire and carried across the redirect
  // -- and never read back, because this flow never requests or parses an
  // id_token. A nonce binds an ID TOKEN to a request; with no ID token it
  // protects exactly nothing while reading, to the next person, as an
  // implemented defence. The Supervisor found it, and it is the same
  // defect as the `prompt=none` path removed above: machinery that
  // implies a feature nobody built.
  //
  // If an ID token is ever consumed here, reinstate the nonce AND
  // validate it. Do not reinstate one without the other.
}

/**
 * base64url — RFC 4648 §5. Not the same alphabet as base64.
 *
 * `+/` become `-_` and the `=` padding goes. Getting this wrong does not
 * throw: Keycloak simply computes a different hash and answers
 * `invalid_grant`, which reads as a wrong password. It is one of the few
 * places in this flow where a silent, misleading failure is easy.
 */
export function base64UrlEncode(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/**
 * A cryptographically random string.
 *
 * `crypto.getRandomValues`, never `Math.random()`. `Math.random()` is not
 * a CSPRNG in any engine and its output is predictable from previous
 * values — a guessable verifier is no verifier at all.
 *
 * 32 bytes is 256 bits, comfortably inside RFC 7636's 43–128 character
 * requirement once base64url-encoded (43 characters).
 */
export function randomToken(bytes = 32): string {
  const buffer = new Uint8Array(bytes);
  crypto.getRandomValues(buffer);
  return base64UrlEncode(buffer);
}

/** SHA-256, base64url-encoded — the `S256` code challenge method. */
export async function sha256Challenge(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return base64UrlEncode(new Uint8Array(digest));
}

/** Everything one sign-in attempt needs, generated fresh each time. */
export async function createChallenge(): Promise<PkceChallenge> {
  const verifier = randomToken();
  return {
    verifier,
    challenge: await sha256Challenge(verifier),
    state: randomToken(16),
  };
}

/**
 * The URL to send the browser to.
 *
 * `redirectUri` is passed in rather than derived here so that the value
 * sent to Keycloak and the value registered in the realm come from ONE
 * place. Two spellings of a redirect URI cannot be type-checked into
 * agreement, and this project has been caught by that shape of defect
 * repeatedly.
 */
export function authorizationUrl(input: {
  readonly authorizeEndpoint: string;
  readonly clientId: string;
  readonly redirectUri: string;
  readonly challenge: PkceChallenge;
  readonly scope?: string;
  // 🔴 THERE IS DELIBERATELY NO `prompt` PARAMETER.
  //
  // It was here, typed `"none"`, for a silent SSO check — and nothing
  // ever passed it. Codex flagged the whole path as unreachable: the only
  // production caller omitted it, `flow.silent` was never read, and a
  // test exercised an argument no application branch could produce. Dead
  // code that implies a feature is worse than an absent feature, because
  // the next reader budgets for behaviour that does not exist. ADR-025
  // explains why silent renew is not attempted at all.
}): string {
  const params = new URLSearchParams({
    client_id: input.clientId,
    redirect_uri: input.redirectUri,
    response_type: "code",
    scope: input.scope ?? "openid profile email",
    state: input.challenge.state,
    code_challenge: input.challenge.challenge,
    code_challenge_method: "S256",
  });
  return `${input.authorizeEndpoint}?${params.toString()}`;
}

/** What Keycloak returns from the token endpoint, narrowed to what is used. */
export interface TokenResponse {
  readonly accessToken: string;
  readonly refreshToken: string | null;
  /** Absolute epoch milliseconds, not a duration — see below. */
  readonly expiresAt: number;
}

/**
 * Exchange the authorization code for tokens.
 *
 * 🔴 THE EXPIRY IS STORED AS AN ABSOLUTE INSTANT, NOT AS `expires_in`.
 *
 * `expires_in` is a duration from the moment the server answered. Keeping
 * it as a duration means every later "is this still valid?" has to
 * remember when it started, and the first caller that forgets treats a
 * long-expired token as fresh. Resolved once, here.
 *
 * A failure names the provider's own `error_description` where there is
 * one. `invalid_grant` with no explanation is the single most misleading
 * message in this whole flow — it is returned for an expired code, a
 * reused code, a wrong verifier and a mismatched redirect URI alike.
 */
export async function exchangeCode(input: {
  readonly tokenEndpoint: string;
  readonly clientId: string;
  readonly redirectUri: string;
  readonly code: string;
  readonly verifier: string;
  readonly now?: () => number;
}): Promise<TokenResponse> {
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: input.clientId,
    redirect_uri: input.redirectUri,
    code: input.code,
    code_verifier: input.verifier,
  });
  return requestToken(input.tokenEndpoint, body, input.now);
}

/** Trade a refresh token for a new access token. */
export async function refreshTokens(input: {
  readonly tokenEndpoint: string;
  readonly clientId: string;
  readonly refreshToken: string;
  readonly now?: () => number;
}): Promise<TokenResponse> {
  const body = new URLSearchParams({
    grant_type: "refresh_token",
    client_id: input.clientId,
    refresh_token: input.refreshToken,
  });
  return requestToken(input.tokenEndpoint, body, input.now);
}

async function requestToken(
  endpoint: string,
  body: URLSearchParams,
  now: (() => number) | undefined,
): Promise<TokenResponse> {
  const clock = now ?? Date.now;
  const issuedAt = clock();

  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
    // No cookies. This is a public client using PKCE; sending credentials
    // would invite the browser to attach the realm's SSO cookie to a
    // cross-origin POST, which is not how this grant is authenticated.
    credentials: "omit",
  });

  const text = await response.text();
  let payload: Record<string, unknown> = {};
  try {
    payload = JSON.parse(text) as Record<string, unknown>;
  } catch {
    // Deliberately swallowed: a non-JSON body is itself the diagnosis,
    // and it is included verbatim in the error below rather than
    // replaced by a parse failure that names nothing.
  }

  if (!response.ok) {
    const error = typeof payload.error === "string" ? payload.error : `HTTP ${response.status}`;
    const detail =
      typeof payload.error_description === "string"
        ? payload.error_description
        : text.slice(0, 200);
    throw new Error(`the identity provider refused the token request: ${error} — ${detail}`);
  }

  const accessToken = payload.access_token;
  if (typeof accessToken !== "string" || accessToken.length === 0) {
    // A 200 with no token is not success. Absence must never present as
    // a value — the same rule the API client layer enforces on every
    // response it parses.
    throw new Error(
      "the identity provider answered 200 with no access_token, so there is no session",
    );
  }

  const expiresIn = typeof payload.expires_in === "number" ? payload.expires_in : 60;
  const refreshToken = typeof payload.refresh_token === "string" ? payload.refresh_token : null;

  return {
    accessToken,
    refreshToken,
    expiresAt: issuedAt + expiresIn * 1000,
  };
}

/**
 * Read the organization id out of an access token.
 *
 * 🔴 THIS IS A CONVENIENCE, NOT A SECURITY DECISION, AND THE DIFFERENCE
 * MATTERS.
 *
 * The value is used to populate `X-Organization-Id` so the first request
 * has a tenant to ask for. The API does NOT trust it: `get_principal`
 * re-reads membership from the database and refuses a tenant the user
 * does not belong to. `CLAUDE.md` §6 requires exactly that, and the auth
 * suite asserts it (`test_a_foreign_organization_is_refused`).
 *
 * So this decodes without verifying the signature — which would be
 * indefensible if anything were being authorized on it, and is fine for
 * choosing which tenant to REQUEST. It is named `unverified` so no future
 * caller can reach for it thinking otherwise.
 */
export function unverifiedClaims(accessToken: string): Record<string, unknown> {
  const parts = accessToken.split(".");
  // `parts[1]` rather than a length check alone: `noUncheckedIndexedAccess`
  // is on, and it is right to be — a JWT arriving from anywhere other than
  // the token endpoint is exactly the input that should not be trusted to
  // have three segments.
  const segment = parts[1];
  if (parts.length !== 3 || segment === undefined) return {};
  try {
    const payload = segment.replace(/-/g, "+").replace(/_/g, "/");
    const padded = payload.padEnd(payload.length + ((4 - (payload.length % 4)) % 4), "=");
    return JSON.parse(atob(padded)) as Record<string, unknown>;
  } catch {
    return {};
  }
}
