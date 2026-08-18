/**
 * Who the browser is, if anyone.
 *
 * 🔴 THERE IS NO SIGN-IN FLOW IN THIS APPLICATION, AND THIS FILE DOES NOT
 * PRETEND OTHERWISE.
 *
 * `next-auth` is a declared dependency that nothing imports. No Keycloak
 * is deployed — not on Render, not in CI, not on the development host.
 * So `useSession()` returns "no session" and names the reason, and every
 * authenticated call refuses before it is made.
 *
 * WHY THIS IS A SEAM AND NOT A STUB
 * ---------------------------------
 * The temptation is a development bypass: a hardcoded token, or an API
 * flag that accepts unsigned JWTs when `APP_ENV=development`. Both were
 * considered and both are refused.
 *
 * `CLAUDE.md` §7 is explicit that AI must never become a permission-bypass
 * channel, and §6 that every control is re-enforced server-side; a client
 * that can mint its own credentials is the same hole wearing different
 * clothes. More practically, a bypass that exists is a bypass that ships:
 * the flag gets set in the wrong environment exactly once, and the failure
 * is silent because everything works.
 *
 * So the seam is typed, the absence is explicit, and the wiring above it
 * is real. When Keycloak is deployed, `readSession` gains an OIDC
 * implementation and nothing else in the application changes — the hooks,
 * the client and the pages are already written against this interface.
 *
 * WHAT MUST NOT HAPPEN NEXT
 * -------------------------
 * Storing an access token in `localStorage`. It is readable by any script
 * on the origin, so one XSS becomes a stolen session that outlives the
 * page. When this is implemented, the token belongs in memory with the
 * refresh handled by the provider — which is also why this returns a value
 * rather than reading a global: there is nowhere for a caller to reach
 * around it.
 */

"use client";

import { useSyncExternalStore } from "react";

import type { ApiCredentials } from "./client";

/** A session, or a stated reason there is not one. */
export type SessionState =
  | { readonly status: "authenticated"; readonly credentials: ApiCredentials }
  | { readonly status: "anonymous"; readonly reason: string };

/**
 * Why there is no session, in words that describe the DEPLOYMENT rather
 * than the code. A reader who sees this on screen should understand that
 * nothing is broken and nothing they can do will change it.
 */
export const NO_IDENTITY_PROVIDER =
  "no identity provider is deployed for this environment, so there is no one " +
  "to sign in as yet";

const ANONYMOUS: SessionState = {
  status: "anonymous",
  reason: NO_IDENTITY_PROVIDER,
};

// A module-level store rather than React state, because the session is a
// property of the browser and not of any one component subtree. It is
// wired through `useSyncExternalStore` so that when a real provider does
// set it, every consumer re-renders — rather than the first implementation
// discovering it needs a context and rewriting every call site.
let current: SessionState = ANONYMOUS;
const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function snapshot(): SessionState {
  return current;
}

/**
 * Replace the current session. The only writer today is the test suite;
 * the OIDC provider becomes the second.
 *
 * Deliberately NOT exported from an index barrel, and deliberately not
 * reading from any browser storage: a function that can be called is a
 * function that must be findable in a review, and `setSession` in a
 * component diff is a thing a reviewer will stop on.
 */
export function setSession(next: SessionState): void {
  current = next;
  for (const listener of listeners) listener();
}

/** The current session. Never null — anonymity is a state, not an absence. */
export function useSession(): SessionState {
  return useSyncExternalStore(subscribe, snapshot, () => ANONYMOUS);
}

/** Read once, outside React. */
export function readSession(): SessionState {
  return current;
}

// ---------------------------------------------------------------------
// A TEST SEAM, COMPILED OUT OF EVERY PRODUCTION BUILD
// ---------------------------------------------------------------------
//
// 🔴 READ THIS BEFORE DECIDING IT IS A BACK DOOR, AND BEFORE ADDING A
// SECOND ONE.
//
// The end-to-end suite has to be able to put the browser into an
// authenticated state, or the only thing it can ever prove about this
// application is that it does nothing. There is no deployed Keycloak to
// sign in against — not on Render, not in CI, not on the development
// host — so the alternative was to leave the wiring untested, which is
// how `apps/web makes no API calls at all` survived three slices.
//
// WHY THIS GRANTS NO ACCESS TO ANYTHING.
//
// It sets a token on the CLIENT. The API verifies every token's signature
// against the realm's JWKS and reads permissions from the database rather
// than from the token's claims (`get_principal`). A session established
// here with a token the identity provider did not issue is refused by the
// API exactly as any other forgery would be. The seam moves no boundary;
// it only lets a test populate the client side of one.
//
// WHY IT IS SAFE IN A WAY A RUNTIME FLAG WOULD NOT BE.
//
// `NEXT_PUBLIC_*` is inlined at BUILD time, so this branch is eliminated
// by the compiler when the variable is absent. The production bundle does
// not contain the code — there is no flag to set in the wrong environment
// and no configuration mistake that can switch it on. That distinction is
// the whole reason it is written this way rather than as
// `if (process.env.APP_ENV === "development")`, which ships the code and
// trusts a runtime value, and which this project has already learned not
// to do (`config reads correct while the mechanism is INERT`).
//
// It is deliberately NOT a way to log in. It takes whatever it is given
// and the API decides.
if (process.env.NEXT_PUBLIC_E2E_SESSION_HOOK === "1" && typeof window !== "undefined") {
  (window as unknown as Record<string, unknown>).__evercoatSetSession = setSession;
}
