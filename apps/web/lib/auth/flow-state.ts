/**
 * The one thing that must survive the redirect, and nothing else.
 *
 * 🔴 THE VERIFIER GOES IN `sessionStorage`. THE TOKEN NEVER DOES.
 *
 * `lib/api/session.ts` recorded the rule before there was an
 * implementation: an access token in browser storage is readable by any
 * script on the origin, so one XSS becomes a stolen session that outlives
 * the page. That rule is kept — the token lives in memory only.
 *
 * This file is the deliberate, bounded exception, and the distinction is
 * not a technicality:
 *
 *   * The verifier is **useless on its own.** It authorizes nothing. It
 *     only proves that whoever redeems the authorization code is whoever
 *     requested it.
 *   * It is **single-use and short-lived** — one redirect, then cleared,
 *     whether the exchange succeeded or failed.
 *   * It **has to** outlive a full-page navigation to another origin and
 *     back. Memory cannot do that. Storing it is what makes PKCE work;
 *     storing the token is what would make the application unsafe.
 *
 * `sessionStorage` rather than `localStorage` because it is scoped to the
 * tab and dies with it — a verifier left behind in a shared browser
 * profile is a loose end even if it is not a credential.
 *
 * See ADR-025.
 */

import type { PkceChallenge } from "./pkce";

const KEY = "evercoat.auth.flow";

/** What is put aside for the duration of one redirect. */
export interface FlowState {
  readonly verifier: string;
  readonly state: string;
  readonly nonce: string;
  /** Where the user was, so they land back there and not on a dashboard. */
  readonly returnTo: string;
  /** True when this was a background `prompt=none` check. */
  readonly silent: boolean;
}

/** True when this code is running somewhere with a DOM. */
function storage(): Storage | null {
  // Not `typeof window` alone. A static export is prerendered in Node,
  // where `window` is absent, and Safari in private mode has thrown on
  // `sessionStorage` access historically. Both are "no storage", and
  // neither should crash a render.
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

export function saveFlow(challenge: PkceChallenge, returnTo: string, silent: boolean): void {
  const store = storage();
  if (store === null) return;
  const value: FlowState = {
    verifier: challenge.verifier,
    state: challenge.state,
    nonce: challenge.nonce,
    returnTo,
    silent,
  };
  store.setItem(KEY, JSON.stringify(value));
}

/**
 * Read the pending flow and CLEAR it in the same breath.
 *
 * Take-once, deliberately. A verifier that survives its exchange is a
 * verifier that can be replayed against a second intercepted code, and
 * leaving cleanup to the caller means the one error path that forgets
 * leaves it behind forever.
 */
export function takeFlow(): FlowState | null {
  const store = storage();
  if (store === null) return null;
  const raw = store.getItem(KEY);
  store.removeItem(KEY);
  if (raw === null) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<FlowState>;
    if (
      typeof parsed.verifier !== "string" ||
      typeof parsed.state !== "string" ||
      typeof parsed.nonce !== "string"
    ) {
      return null;
    }
    return {
      verifier: parsed.verifier,
      state: parsed.state,
      nonce: parsed.nonce,
      returnTo: typeof parsed.returnTo === "string" ? parsed.returnTo : "/",
      silent: parsed.silent === true,
    };
  } catch {
    return null;
  }
}

/**
 * Confine a post-sign-in redirect to this application.
 *
 * 🔴 AN OPEN REDIRECT IS A PHISHING PRIMITIVE, AND `returnTo` IS EXACTLY
 * THE SHAPE THAT PRODUCES ONE. A path taken from the current URL and
 * later handed to `location.replace` will happily send the user to
 * `https://evil.example` — from a link that genuinely started on the real
 * site, immediately after a genuine sign-in, which is when a person is
 * least likely to re-read the address bar.
 *
 * 🔴 THE FIRST VERSION OF THIS FUNCTION WAS BYPASSED, BY ITS AUTHOR,
 * WITHIN THE HOUR. It pattern-matched for bad values — reject a leading
 * `//`, reject a backslash, reject a scheme — and it let this through:
 *
 *     "/\nevil" → safeReturnTo says fine → resolves to https://evil.example/
 *
 * because **browsers strip TAB (\t), LF (\n) and CR (\r) out of a URL
 * before parsing it.** `"/" + "\n" + "/evil.example"` is delivered to the
 * parser as `//evil.example`, which is protocol-relative and off-origin.
 * `\r` and `\t` do the same. A blocklist did not know that; the URL
 * parser does.
 *
 * So this no longer tries to recognise hostile values. It RESOLVES the
 * candidate with the same parser the browser will use, and keeps it only
 * if the result is on this origin. Anything else — another origin, a
 * `javascript:` URL (whose origin parses as "null"), an unparseable
 * string — collapses to `/`.
 *
 * The related lesson already recorded on this platform is the same shape:
 * `z.string().url()` accepts `javascript:` and `data:text/html`. Validate
 * by construction, not by exclusion.
 *
 * 🔴 AND THE SECOND VERSION WAS BYPASSED TOO, THE SAME WAY.
 *
 * It resolved correctly and then returned `pathname + search + hash` — a
 * RELATIVE path. `"/..//evil.example"` resolves on-origin with a pathname
 * of `"//evil.example"`, and handing *that* to `location.replace` is
 * protocol-relative all over again. Verifying a value and then returning
 * a different, re-interpretable one is not verification.
 *
 * So it returns an ABSOLUTE, same-origin URL. There is nothing left for a
 * later resolution step to reinterpret, and the caller cannot reintroduce
 * the bug by using the result in a slightly different way.
 *
 * @param origin The application's own origin, e.g. `window.location.origin`.
 *   Required rather than read from `window` inside, so the function stays
 *   pure and can be attacked directly by a test.
 * @returns An absolute URL on `origin`. Never a relative path.
 */
export function safeReturnTo(candidate: string | null | undefined, origin: string): string {
  const home = safeHome(origin);
  if (typeof candidate !== "string" || candidate.length === 0) return home;
  try {
    const resolved = new URL(candidate, origin);
    // `origin` comparison, not `hostname`: it also pins the scheme and
    // port, so http://app:8080 cannot be talked into https://app:443.
    if (resolved.origin !== new URL(origin).origin) return home;
    return resolved.href;
  } catch {
    return home;
  }
}

/** The application root on this origin, absolute. The safe fallback. */
function safeHome(origin: string): string {
  try {
    return new URL("/", origin).href;
  } catch {
    // An unusable origin is not something to paper over with a relative
    // path that might resolve anywhere. "/" is the only honest answer
    // left, and it is same-document by definition.
    return "/";
  }
}
