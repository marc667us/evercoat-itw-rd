/**
 * The credential path, tested without a browser and without a Keycloak.
 *
 * These assertions are the reason the flow is hand-written rather than
 * delegated: every one of them is a place where a mistake fails SILENTLY
 * or MISLEADINGLY rather than loudly.
 *
 * - A wrong base64 alphabet does not throw. Keycloak just computes a
 *   different hash and answers `invalid_grant`, which reads as a wrong
 *   password.
 * - `Math.random()` produces a verifier that looks identical to a good
 *   one and is predictable.
 * - A 200 with no `access_token` would otherwise be treated as a session.
 * - An unchecked `returnTo` is an open redirect, and the moment straight
 *   after sign-in is exactly when nobody re-reads the address bar.
 */

import { describe, expect, it, vi } from "vitest";

import { safeReturnTo } from "./flow-state";
import {
  authorizationUrl,
  base64UrlEncode,
  createChallenge,
  exchangeCode,
  randomToken,
  sha256Challenge,
  unverifiedClaims,
} from "./pkce";

describe("base64url", () => {
  it("uses the URL alphabet and drops padding", () => {
    // 0xFB 0xFF encodes to "+/8=" in standard base64. base64url must
    // render the same bytes as "-_8" — different alphabet, no padding.
    expect(base64UrlEncode(new Uint8Array([0xfb, 0xff]))).toBe("-_8");
  });

  it("never emits a character that would need escaping in a URL", () => {
    const bytes = new Uint8Array(256);
    for (let i = 0; i < 256; i += 1) bytes[i] = i;
    expect(base64UrlEncode(bytes)).toMatch(/^[A-Za-z0-9_-]+$/);
  });
});

describe("randomToken", () => {
  it("is long enough for RFC 7636 (43-128 characters)", () => {
    const token = randomToken();
    expect(token.length).toBeGreaterThanOrEqual(43);
    expect(token.length).toBeLessThanOrEqual(128);
  });

  it("does not repeat", () => {
    const seen = new Set(Array.from({ length: 200 }, () => randomToken()));
    expect(seen.size).toBe(200);
  });

  it("draws from crypto.getRandomValues, not Math.random", () => {
    // 🔴 The one property a unit test can actually pin. A verifier from
    // Math.random() is indistinguishable by inspection and predictable in
    // practice, so assert the SOURCE rather than the shape.
    const spy = vi.spyOn(crypto, "getRandomValues");
    const random = vi.spyOn(Math, "random");
    randomToken();
    expect(spy).toHaveBeenCalled();
    expect(random).not.toHaveBeenCalled();
    spy.mockRestore();
    random.mockRestore();
  });
});

describe("sha256Challenge", () => {
  it("matches the worked example in RFC 7636 appendix B", async () => {
    // The specification's own vector. If this passes, the challenge this
    // client sends is the one Keycloak will recompute.
    const verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk";
    await expect(sha256Challenge(verifier)).resolves.toBe(
      "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
    );
  });
});

describe("createChallenge", () => {
  it("gives every attempt its own verifier, state and nonce", async () => {
    const a = await createChallenge();
    const b = await createChallenge();
    expect(a.verifier).not.toBe(b.verifier);
    expect(a.state).not.toBe(b.state);
    expect(a.nonce).not.toBe(b.nonce);
  });

  it("sends the hash, never the verifier", async () => {
    const challenge = await createChallenge();
    expect(challenge.challenge).not.toBe(challenge.verifier);
    await expect(sha256Challenge(challenge.verifier)).resolves.toBe(challenge.challenge);
  });
});

describe("authorizationUrl", () => {
  const challenge = {
    verifier: "the-secret-that-must-not-travel",
    challenge: "the-hash",
    state: "state-value",
    nonce: "nonce-value",
  };

  const url = (prompt?: "none") =>
    new URL(
      authorizationUrl({
        authorizeEndpoint: "https://kc.example/realms/evercoat/protocol/openid-connect/auth",
        clientId: "evercoat-web",
        redirectUri: "https://app.example/auth/callback/",
        challenge,
        prompt,
      }),
    );

  it("requests S256, never plain", () => {
    expect(url().searchParams.get("code_challenge_method")).toBe("S256");
  });

  it("🔴 NEVER puts the verifier in the authorization request", () => {
    // Sending it here is precisely what `plain` does, and it defeats the
    // entire mechanism while still being called PKCE.
    expect(url().toString()).not.toContain(challenge.verifier);
    expect(url().searchParams.get("code_challenge")).toBe("the-hash");
  });

  it("carries state and nonce", () => {
    expect(url().searchParams.get("state")).toBe("state-value");
    expect(url().searchParams.get("nonce")).toBe("nonce-value");
  });

  it("omits prompt unless a silent check was asked for", () => {
    expect(url().searchParams.get("prompt")).toBeNull();
    expect(url("none").searchParams.get("prompt")).toBe("none");
  });
});

describe("exchangeCode", () => {
  const base = {
    tokenEndpoint: "https://kc.example/token",
    clientId: "evercoat-web",
    redirectUri: "https://app.example/auth/callback/",
    code: "the-code",
    verifier: "the-verifier",
  };

  function respond(status: number, payload: unknown): void {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: status >= 200 && status < 300,
        status,
        text: async () => JSON.stringify(payload),
      }),
    );
  }

  it("resolves expiry to an absolute instant", async () => {
    respond(200, { access_token: "at", refresh_token: "rt", expires_in: 300 });
    const result = await exchangeCode({ ...base, now: () => 1_000_000 });
    // 🔴 Not a duration. A caller that has to remember when the duration
    // started is a caller that eventually forgets and treats a long-dead
    // token as fresh.
    expect(result.expiresAt).toBe(1_000_000 + 300_000);
    expect(result.accessToken).toBe("at");
    expect(result.refreshToken).toBe("rt");
  });

  it("sends the verifier and the grant type", async () => {
    respond(200, { access_token: "at", expires_in: 60 });
    await exchangeCode(base);
    const mock = globalThis.fetch as unknown as {
      mock: { calls: [string, { body: string }][] };
    };
    const call = mock.mock.calls[0];
    expect(call).toBeDefined();
    const body = call?.[1].body ?? "";
    expect(body).toContain("code_verifier=the-verifier");
    expect(body).toContain("grant_type=authorization_code");
  });

  it("🔴 refuses a 200 that carries no access token", async () => {
    // Absence must never present as success. This project has already
    // shipped "an empty requirement set rendered ALL REQUIREMENTS PASSED".
    respond(200, { token_type: "Bearer", expires_in: 300 });
    await expect(exchangeCode(base)).rejects.toThrow(/no access_token/);
  });

  it("names the provider's own error description", async () => {
    // `invalid_grant` alone is returned for an expired code, a reused
    // code, a wrong verifier and a mismatched redirect URI alike — so the
    // description is the only thing that distinguishes them.
    respond(400, { error: "invalid_grant", error_description: "Code not valid" });
    await expect(exchangeCode(base)).rejects.toThrow(/invalid_grant.*Code not valid/);
  });

  it("survives a non-JSON body and quotes it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 502, text: async () => "<html>gateway</html>" }),
    );
    await expect(exchangeCode(base)).rejects.toThrow(/HTTP 502.*gateway/s);
  });
});

describe("unverifiedClaims", () => {
  it("reads a payload without needing the signature", () => {
    const payload = btoa(JSON.stringify({ organization_id: "org-1" }))
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
    expect(unverifiedClaims(`header.${payload}.signature`)).toEqual({ organization_id: "org-1" });
  });

  it("returns nothing rather than throwing on rubbish", () => {
    // It feeds a request header, not an authorization decision. The API
    // re-reads membership from the database either way, so an
    // unparseable token must degrade to "no hint", not to a crash.
    expect(unverifiedClaims("not-a-jwt")).toEqual({});
    expect(unverifiedClaims("a.!!!.c")).toEqual({});
  });
});

describe("safeReturnTo", () => {
  const ORIGIN = "https://app.example";

  it("keeps an in-application path, as an absolute URL on this origin", () => {
    expect(safeReturnTo("/formulations?open=F100#tab", ORIGIN)).toBe(
      "https://app.example/formulations?open=F100#tab",
    );
  });

  // 🔴 EVERY ONE OF THESE DEFEATED AN EARLIER VERSION OF THIS FUNCTION.
  //
  // Version one pattern-matched: reject a leading "//", reject a
  // backslash, reject a scheme. The control-character rows walked
  // straight through, because BROWSERS STRIP TAB, LF AND CR FROM A URL
  // BEFORE PARSING -- so a slash, an LF and "/evil.example" reach the
  // parser as "//evil.example", protocol-relative and off-origin.
  //
  // Version two resolved properly and then returned
  // pathname + search + hash. "/..//evil.example" resolves on-origin
  // with a pathname of "//evil.example", and handing THAT to
  // location.replace is protocol-relative all over again.
  //
  // Both were found by attacking the function, not by reading it.
  it.each([
    ["/\n/evil.example", "LF, stripped by the URL parser"],
    ["/\r/evil.example", "CR, likewise"],
    ["/\t/evil.example", "TAB, likewise"],
    ["/\n\t//evil.example", "both, before a protocol-relative host"],
    ["//evil.example", "protocol-relative -- the one people remember"],
    ["//\tevil.example", "protocol-relative with a stripped character"],
    ["https://evil.example/steal", "an absolute URL"],
    ["javascript:alert(1)", "a scheme whose origin parses as null"],
    ["data:text/html,x", "data:, which z.string().url() accepts"],
    ["http://app.example:99/x", "right host, wrong port"],
    ["//app.example.evil.com", "a hostname that merely starts the same"],
    ["", "empty"],
    [null, "absent"],
  ] as readonly (readonly [string | null, string])[])(
    "🔴 refuses %s (%s)",
    (candidate) => {
      // An open redirect immediately after sign-in is a phishing primitive:
      // the link genuinely started on the real site, and nobody re-reads
      // the address bar at that moment.
      expect(safeReturnTo(candidate, ORIGIN)).toBe("https://app.example/");
    },
  );

  it("never returns a value that can be re-read as another origin", () => {
    // The property, rather than a list. Whatever comes back must resolve
    // to this origin when the CALLER uses it -- the step that broke
    // version two.
    const hostile = [
      "/..//evil.example",
      "/../../..//evil.example",
      "/%0a/evil.example",
      "/\\evil.example",
      "/\u0000//evil.example",
    ];
    for (const candidate of hostile) {
      const result = safeReturnTo(candidate, ORIGIN);
      expect(new URL(result, ORIGIN).origin).toBe(ORIGIN);
    }
  });
});
