/**
 * Where the identity provider is, and whether there is one.
 *
 * 🔴 `NEXT_PUBLIC_*` IS READ AT BUILD TIME, NOT AT RUNTIME.
 *
 * The same rule that governs `lib/api/config.ts` governs this file, and
 * for the same reason: Next.js inlines these values when it compiles.
 * Setting `NEXT_PUBLIC_KEYCLOAK_URL` on a running container changes
 * nothing. Pointing a deployed site at a different realm means REBUILDING
 * it. This platform has been bitten by exactly that before.
 *
 * It matters more here than it does for the API address, because a static
 * export cannot compute its own origin at deploy time either — so the
 * redirect URI is fixed at build time too, and it must match what the
 * realm was told to expect. A mismatch is refused by Keycloak with
 * `invalid_redirect_uri` before any code is issued, which is the correct
 * behaviour and reads as "sign-in is broken".
 *
 * WHY "NOT CONFIGURED" IS A FIRST-CLASS STATE
 * -------------------------------------------
 * There is no Keycloak deployed for the live site today — deploying one
 * needs a web service, which is spend, which is the operator's decision.
 * So a build with no identity provider is the NORMAL condition of the
 * deployed artefact, not a misconfiguration.
 *
 * That makes it dangerous in the same way an absent API is dangerous: a
 * sign-in button that silently did nothing would be indistinguishable
 * from one that was broken. So the absence is named, carried, and
 * rendered — exactly as `API_UNCONFIGURED_REASON` is.
 *
 * See ADR-025 for why this is a browser-side PKCE flow and not next-auth.
 */

import { NO_IDENTITY_PROVIDER } from "@/lib/api/session";

/** Keycloak's origin, without a trailing slash, or `null` when absent. */
export const KEYCLOAK_URL: string | null =
  process.env.NEXT_PUBLIC_KEYCLOAK_URL?.replace(/\/+$/, "") || null;

/** The realm to authenticate against. */
export const KEYCLOAK_REALM: string =
  process.env.NEXT_PUBLIC_KEYCLOAK_REALM || "evercoat";

/**
 * The public client id.
 *
 * `evercoat-web` is the client the realm ships with `publicClient: true`,
 * `standardFlowEnabled: true` and `pkce.code.challenge.method: S256`. It
 * also carries the `evercoat-api-audience` mapper, without which a
 * perfectly genuine token is rejected by the API with the same flat
 * "invalid token" a forged one gets. Do not point this at a client that
 * lacks that mapper.
 */
export const KEYCLOAK_CLIENT_ID: string =
  process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID || "evercoat-web";

/**
 * The path the provider redirects back to.
 *
 * A real page in the static export (`app/auth/callback/page.tsx`), not a
 * route handler — there are none. `next.config` sets `trailingSlash`, so
 * the deployed URL is `/auth/callback/`; the realm must be told the same
 * string, character for character.
 */
export const CALLBACK_PATH = "/auth/callback/";

/** True when this build knows where to sign in. */
export const isAuthConfigured: boolean = KEYCLOAK_URL !== null;

/**
 * Why there is no sign-in, in words that describe the DEPLOYMENT rather
 * than the code. A reader who sees this on screen should understand that
 * nothing is broken and nothing they can do will change it.
 *
 * 🔴 RE-EXPORTED, NOT RE-WORDED.
 *
 * This was briefly its own sentence, and it immediately broke the E2E
 * assertion that the demonstration banner explains WHY there is no
 * session. Two strings saying the same thing in two files is the defect
 * this project keeps catching -- nav vs router, landing vs pack, the
 * callback path in the realm vs the TypeScript. The wording lives in
 * `lib/api/session.ts` beside the state it describes; this is a pointer
 * to it.
 */
export const AUTH_UNCONFIGURED_REASON = NO_IDENTITY_PROVIDER;

/** The realm's OIDC endpoints. Throws when unconfigured, deliberately. */
export function endpoints(): {
  readonly authorize: string;
  readonly token: string;
  readonly endSession: string;
} {
  if (KEYCLOAK_URL === null) {
    // Not a soft failure. Every caller is behind an `isAuthConfigured`
    // check, so reaching here means a caller skipped it — and a sign-in
    // that quietly does nothing is the failure mode this whole file is
    // written to prevent.
    throw new Error(AUTH_UNCONFIGURED_REASON);
  }
  const base = `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect`;
  return {
    authorize: `${base}/auth`,
    token: `${base}/token`,
    endSession: `${base}/logout`,
  };
}
