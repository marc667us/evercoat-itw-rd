/**
 * The sign-in flow, wired to the session the rest of the app already reads.
 *
 * `lib/api/session.ts` was written before there was an implementation and
 * predicted this exactly: *"When Keycloak is deployed, `readSession` gains
 * an OIDC implementation and nothing else in the application changes — the
 * hooks, the client and the pages are already written against this
 * interface."* This is that implementation. No hook, no page and no
 * request changes.
 *
 * 🔴 THE TOKEN LIVES IN MEMORY, AND A RELOAD SIGNS YOU OUT.
 *
 * That is a decision, not an omission. `session.ts` recorded the rule
 * first: an access token in browser storage is readable by any script on
 * the origin, so one XSS becomes a stolen session that outlives the page.
 *
 * The cost is real and is stated plainly: after a reload the user is
 * ANONYMOUS and must press Sign in. Nothing happens automatically. What
 * makes that acceptable rather than merely tolerable is that the redirect
 * usually returns without a password prompt, because Keycloak's own SSO
 * cookie is still valid — so it costs a round trip, not a login.
 *
 * (An earlier version of this paragraph described that as "silent" and as
 * "a flicker, not a login form". Codex pointed out that no code performed
 * any silent check — the `prompt=none` path was never wired up — so the
 * comment promised behaviour the file did not have. Corrected rather than
 * implemented, because the silent path is deliberately declined below.)
 *
 * 🔴 WHY THERE IS NO HIDDEN-IFRAME SILENT RENEW.
 *
 * The classic answer is a `prompt=none` request in a hidden iframe. It is
 * deliberately not used: it depends on the realm's cookie being sent in a
 * third-party context, which Safari's ITP blocks outright and Chrome is
 * removing. A mechanism that works in development and silently stops
 * working for some users in production is worse than one that visibly
 * asks — this codebase has already been caught by config that "read
 * correct while the mechanism was INERT". `signIn()` is a full redirect,
 * and it is honest.
 *
 * See ADR-025.
 */

"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { API_BASE_URL } from "@/lib/api/config";
import { readSession, setSession, useSession, type SessionState } from "@/lib/api/session";
import {
  AUTH_UNCONFIGURED_REASON,
  CALLBACK_PATH,
  KEYCLOAK_CLIENT_ID,
  endpoints,
  isAuthConfigured,
} from "@/lib/auth/config";
import { safeReturnTo, saveFlow } from "@/lib/auth/flow-state";
import { authorizationUrl, createChallenge, refreshTokens } from "@/lib/auth/pkce";

/**
 * Who the signed-in person is, as `/api/me` reports them.
 *
 * 🔴 THE API HAS ALWAYS SENT THIS AND THE PROVIDER THREW IT AWAY.
 * `GET /api/me` returns `user_id`, `email` and `display_name` at the top level
 * beside `organizations`, and the parse below read only `organizations`. So the
 * application knew the caller's name on every load and had nowhere to put it —
 * which is why the top bar showed a grey circle with a dash in it.
 *
 * ⚠️ THIS IS THE ORGANIZATION'S VIEW OF THE PERSON, not a global identity.
 * Migration 052 moved `email` and `display_name` onto the membership (I106);
 * `/api/me` resolves them through the same path, so what arrives here is the
 * name THIS tenant knows them by.
 */
export interface UserProfile {
  readonly userId: string;
  readonly email: string;
  readonly displayName: string;
}

export interface AuthContextValue {
  readonly session: SessionState;
  /** The signed-in person, or null when there is no session. */
  readonly profile: UserProfile | null;
  /** True when this build has an identity provider to talk to. */
  readonly configured: boolean;
  /** Begin sign-in. A full-page redirect; this function does not return. */
  readonly signIn: () => Promise<void>;
  /** Discard the session locally and end it at the provider. */
  readonly signOut: () => void;
  /** The active organization, and the ability to change it. */
  readonly organizations: readonly OrganizationChoice[];
  readonly selectOrganization: (organizationId: string) => void;
}

export interface OrganizationChoice {
  readonly organizationId: string;
  readonly name: string;
  readonly code: string;
  readonly roles: readonly string[];
  /**
   * Permission codes held in THIS organization (I79).
   *
   * 🔴 PERMISSIONS, NOT ROLES, AND THEY ARE PER-TENANT LIKE THE ROLES ARE.
   * §6 authorizes on permissions and never on role names; before migration
   * 045 `/api/me` returned only roles, so the shell could either show every
   * control or re-derive the mapping in TypeScript. It showed every control.
   *
   * Empty is a legitimate value and must not be confused with "unknown":
   * a member holding no roles yet has no permissions, and the sidebar
   * should say so rather than showing the whole module map. `undefined`
   * organizations -- no session at all -- is the different case, handled
   * where the sidebar chooses its fallback.
   */
  readonly permissions: readonly string[];
}

/** The ordinary signed-out state of a build that CAN sign in. */
export const NOT_SIGNED_IN = "you are not signed in";

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * The full redirect URI, built from the browser's own origin.
 *
 * A static export cannot know its deployed origin at build time, so it is
 * read at run time — and it MUST match a `redirectUris` entry in the
 * realm exactly, or Keycloak refuses with `invalid_redirect_uri` before
 * issuing anything. Building it in one place is deliberate: two spellings
 * of a redirect URI cannot be type-checked into agreement, which is the
 * defect shape this project keeps hitting.
 */
export function redirectUri(): string {
  return `${window.location.origin}${CALLBACK_PATH}`;
}

/** In-memory refresh material. Never written to storage — see the header. */
interface LiveTokens {
  readonly accessToken: string;
  readonly refreshToken: string | null;
  readonly expiresAt: number;
}

/**
 * Which organization stays active across a token refresh.
 *
 * 🔴 A REFRESH MUST NOT SILENTLY MOVE THE USER TO ANOTHER TENANT.
 *
 * `establish()` runs on sign-in AND on every refresh. The first version
 * always took `choices[0]`, so a chemist working in their second
 * organization was silently switched back to the first roughly once per
 * token lifetime — and every write after that went to the WRONG TENANT,
 * with the correct name shown only in a corner nobody was watching. In an
 * application whose records are controlled and audited, that is a
 * data-integrity defect, not a UI annoyance. Codex found it.
 *
 * Falling back to the first when the preferred one is gone is deliberate:
 * that means the membership was revoked, and staying on it is not an
 * option. Extracted and exported so the rule is testable on its own
 * rather than reachable only through a network call.
 */
export function chooseOrganization(
  choices: readonly OrganizationChoice[],
  preferred: string | undefined,
): OrganizationChoice {
  const kept = choices.find((org) => org.organizationId === preferred);
  if (kept !== undefined) return kept;
  const first = choices[0];
  if (first === undefined) {
    throw new Error("chooseOrganization called with no organizations");
  }
  return first;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const session = useSession();
  const [organizations, setOrganizations] = useState<readonly OrganizationChoice[]>([]);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const tokens = useRef<LiveTokens | null>(null);
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 🔴 clearTimeout CANNOT STOP A REFRESH THAT IS ALREADY IN FLIGHT.
  //
  // The cleanup clears the pending timer, but if the callback has already
  // fired it is sitting in `await refreshTokens(...)`, and when that
  // resolves it sets state and schedules the NEXT timer -- after unmount.
  // The result is a React warning, a token refreshed for a tree nobody is
  // rendering, and a timer that outlives the provider. Codex found it.
  const mounted = useRef(true);

  /**
   * Ask the API who we are, and which tenants we may act in.
   *
   * 🔴 THIS CALL IS WHAT MAKES SIGNING IN USEFUL. Every other route
   * requires `X-Organization-Id`, and until `GET /api/me` existed nothing
   * told the browser what to put in it — a valid token bought 400s and
   * nothing else. It is therefore NOT optional and NOT best-effort: if it
   * fails there is no usable session, and saying so is better than an
   * application that renders empty.
   */
  /**
   * @returns true when a usable session was established.
   *
   * 🔴 IT USED TO RETURN void AND "SUCCEED" ON EVERY FAILURE.
   *
   * A 401, 404 or 500 from `/api/me` set an anonymous session and then
   * resolved normally, so the caller went on to schedule another refresh.
   * A deprovisioned user was therefore left holding live tokens that the
   * application kept refreshing indefinitely, while the UI insisted there
   * was no session. Codex found it. The caller now stops, and drops the
   * tokens.
   */
  const establish = useCallback(async (accessToken: string): Promise<boolean> => {
    if (API_BASE_URL === null) {
      setSession({
        status: "anonymous",
        reason:
          "signed in, but this build was compiled without an API address, so " +
          "there is nothing to sign in to",
      });
      return false;
    }

    const response = await fetch(`${API_BASE_URL}/api/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });

    if (response.status === 404) {
      // The single most useful diagnostic in the whole auth path: the
      // token is genuine and its subject matches no user. Historically
      // this exact state was produced by seed.py writing
      // `keycloak_sub = 'demo-chem.demo'` while a real token carries a
      // UUID. Naming it saves the next reader a day.
      setSession({
        status: "anonymous",
        reason:
          "you signed in successfully, but this application has no account for " +
          "you yet — your identity is valid and your access is not provisioned",
        failed: true,
      });
      return false;
    }

    if (!response.ok) {
      setSession({
        status: "anonymous",
        reason: `the API refused to identify you (HTTP ${response.status})`,
        // A request WAS made and it failed. Not an absence -- see the
        // `failed` field on SessionState.
        failed: true,
      });
      return false;
    }

    const body = (await response.json()) as {
      user_id?: string;
      email?: string;
      display_name?: string;
      organizations?: {
        organization_id: string;
        name: string;
        code: string;
        roles?: string[];
        permissions?: string[];
      }[];
    };

    const choices: OrganizationChoice[] = (body.organizations ?? []).map((org) => ({
      organizationId: org.organization_id,
      name: org.name,
      code: org.code,
      roles: org.roles ?? [],
      // `?? []` and not `?? ALL_NAV_PERMISSIONS`: an API too old to send
      // permissions must yield a shell that shows LESS, never one that shows
      // everything. Failing open on an authorization-shaped field is how a
      // cosmetic filter turns into a claim the server never made.
      permissions: org.permissions ?? [],
    }));

    // 🔴 ONLY WHEN ALL THREE ARE PRESENT. A half-populated profile would put an
    // empty string where a name goes, and "signed in as ''" is worse than no
    // name at all — it looks like a rendering bug rather than an absent field.
    setProfile(
      body.user_id !== undefined &&
        body.email !== undefined &&
        body.display_name !== undefined
        ? {
            userId: body.user_id,
            email: body.email,
            displayName: body.display_name,
          }
        : null,
    );

    const first = choices[0];
    if (first === undefined) {
      // Absence must never present as success. An empty list would render
      // as a working sign-in into an application with nothing in it.
      setSession({
        status: "anonymous",
        reason: "you are signed in but belong to no organization, so there is nothing to show",
        failed: true,
      });
      return false;
    }

    // 🔴 A TOKEN REFRESH MUST NOT SILENTLY MOVE THE USER TO ANOTHER TENANT.
    //
    // This function runs on sign-in AND on every refresh. The first
    // version always selected `choices[0]`, so a chemist working in their
    // second organization was silently switched back to the first roughly
    // once every token lifetime -- and every write after that point went
    // to the wrong tenant, with the UI showing the wrong name in a corner
    // nobody was looking at. Codex found it.
    //
    // The active organization is therefore CARRIED unless it has gone
    // away, in which case falling back to the first is correct: the
    // membership was revoked and staying on it is not an option.
    const currently = readSession();
    const chosen = chooseOrganization(
      choices,
      currently.status === "authenticated" ? currently.credentials.organizationId : undefined,
    );

    const userId = typeof body.user_id === "string" ? body.user_id : "";
    if (userId === "") {
      // A principal with no id cannot scope a cache entry, and a cache
      // entry that cannot be scoped is one that can be served to the
      // wrong person. Refuse rather than fall back to a shared key.
      setSession({
        status: "anonymous",
        reason: "the API did not identify who you are",
        failed: true,
      });
      return false;
    }

    setOrganizations(choices);
    setSession({
      status: "authenticated",
      credentials: {
        token: accessToken,
        organizationId: chosen.organizationId,
        userId,
      },
    });
    return true;
  }, []);

  /** Keep the access token fresh while the tab is open. */
  const scheduleRefresh = useCallback(
    (live: LiveTokens) => {
      if (refreshTimer.current !== null) clearTimeout(refreshTimer.current);
      if (live.refreshToken === null) return;

      // 30 seconds of margin. Refreshing exactly at expiry races the
      // clock against network latency and loses often enough to matter,
      // and the failure looks like a random 401 rather than a timing bug.
      const delay = Math.max(5_000, live.expiresAt - Date.now() - 30_000);
      refreshTimer.current = setTimeout(() => {
        void (async () => {
          try {
            const next = await refreshTokens({
              tokenEndpoint: endpoints().token,
              clientId: KEYCLOAK_CLIENT_ID,
              refreshToken: live.refreshToken as string,
            });
            if (!mounted.current) return;
            tokens.current = next;
            // 🔴 SEPARATED FROM THE REFRESH FAILURE ON PURPOSE.
            //
            // `establish()` reaches the API, and a thrown fetch -- API
            // host down, DNS, a refused CORS preflight -- used to
            // propagate into the catch below and report "your session
            // expired", nulling a refresh token that was perfectly
            // valid. The user was signed out and told the wrong reason.
            // The Supervisor found it.
            let usable = false;
            try {
              usable = await establish(next.accessToken);
            } catch {
              if (!mounted.current) return;
              setSession({
                status: "anonymous",
                reason:
                  "you are signed in, but the application cannot be reached right " +
                  "now. Your session is intact -- retry in a moment.",
                failed: true,
              });
              // Tokens are KEPT and the timer is rescheduled: the
              // credential is fine, the network is not.
              scheduleRefresh(next);
              return;
            }
            if (!mounted.current) return;
            if (!usable) {
              // The token still refreshes, but it buys nothing: the API
              // will not identify this subject. Holding and re-refreshing
              // a credential for a session that does not exist is the
              // defect Codex named. Stop, and drop it.
              tokens.current = null;
              return;
            }
            scheduleRefresh(next);
          } catch {
            // The refresh token has expired or been revoked. Signing the
            // user out is the honest outcome; retrying would produce a
            // session that appears live and 401s on every request.
            if (!mounted.current) return;
            tokens.current = null;
            setSession({
              status: "anonymous",
              reason: "your session expired, please sign in again",
            });
          }
        })();
      }, delay);
    },
    [establish],
  );

  /**
   * Adopt tokens produced by the callback page.
   *
   * Exposed on `window` rather than through context because the callback
   * is a separate route that mounts its own tree, and threading a
   * provider through a page whose only job is to hand over a token would
   * be more machinery than the handover is worth.
   */
  useEffect(() => {
    const adopt = async (live: LiveTokens) => {
      tokens.current = live;
      const usable = await establish(live.accessToken);
      if (!usable) {
        tokens.current = null;
        return;
      }
      scheduleRefresh(live);
    };
    mounted.current = true;
    (window as unknown as Record<string, unknown>).__evercoatAdoptTokens = adopt;
    return () => {
      mounted.current = false;
      if (refreshTimer.current !== null) clearTimeout(refreshTimer.current);
      delete (window as unknown as Record<string, unknown>).__evercoatAdoptTokens;
    };
  }, [establish, scheduleRefresh]);

  /** Tell the reader why there is no sign-in, rather than showing a dead button.
   *
   * 🔴 IT MUST NOT CLOBBER A SESSION SOMEBODY ELSE ALREADY SET.
   *
   * The first version set the anonymous reason unconditionally on mount,
   * and broke five end-to-end tests: the suite establishes a session
   * through the compiled-out test seam, and this effect then overwrote
   * it. `readSession()` rather than the `session` prop, so the check sees
   * the store's current value and not a render-time snapshot.
   */
  useEffect(() => {
    if (readSession().status === "authenticated") return;
    // 🔴 THE DEFAULT REASON LIED IN A CONFIGURED BUILD.
    //
    // `session.ts` seeds the store with NO_IDENTITY_PROVIDER ("no
    // identity provider is deployed for this environment"), and this
    // effect only overwrote it when the build was UNconfigured. So a
    // build that HAD a Keycloak showed that sentence beside a working
    // Sign in button, telling the reader the deployment has no identity
    // provider while they look at the control that uses it. The
    // Supervisor found it. Both branches are now stated.
    setSession({
      status: "anonymous",
      reason: isAuthConfigured ? NOT_SIGNED_IN : AUTH_UNCONFIGURED_REASON,
    });
  }, []);

  const signIn = useCallback(async () => {
    if (!isAuthConfigured) return;
    const challenge = await createChallenge();
    const returnTo = safeReturnTo(
      window.location.pathname + window.location.search,
      window.location.origin,
    );

    // 🔴 DO NOT REDIRECT IF THE FLOW COULD NOT BE STORED.
    //
    // Without the verifier the callback cannot complete, so redirecting
    // would send the user to Keycloak, have them authenticate for real,
    // and then fail with "no sign-in was in progress" — every time, with
    // no way forward. Storage is genuinely unavailable in Safari private
    // mode and under some enterprise policies. Codex found it.
    if (!saveFlow(challenge, returnTo)) {
      setSession({
        status: "anonymous",
        reason:
          "this browser is blocking session storage, which sign-in needs to " +
          "complete securely. Try a normal window, or allow storage for this site.",
      });
      return;
    }

    window.location.assign(
      authorizationUrl({
        authorizeEndpoint: endpoints().authorize,
        clientId: KEYCLOAK_CLIENT_ID,
        redirectUri: redirectUri(),
        challenge,
      }),
    );
  }, []);

  const signOut = useCallback(() => {
    // Local state first. If the redirect below fails for any reason, the
    // browser must not be left holding a live token while believing it
    // has signed out.
    if (refreshTimer.current !== null) clearTimeout(refreshTimer.current);
    tokens.current = null;
    setOrganizations([]);
    setSession({ status: "anonymous", reason: "you have signed out" });

    // 🔴 GATED ON CONFIGURATION ONLY.
    //
    // It used to also require `refreshToken !== null` -- a condition with
    // nothing to do with logging out, since the request below sends only
    // `client_id` and `post_logout_redirect_uri`. If Keycloak's response
    // had omitted a refresh token, Sign out cleared local state and left
    // the realm's SSO cookie alive, so the next Sign in silently returned
    // the previous user. On the shared machine the comment below names,
    // that is the wrong person. The Supervisor found it.
    if (!isAuthConfigured) return;
    // Ends the session at Keycloak too. Without this the SSO cookie
    // survives and the next "Sign in" silently returns the same user —
    // which on a shared machine is the wrong person.
    const params = new URLSearchParams({
      client_id: KEYCLOAK_CLIENT_ID,
      post_logout_redirect_uri: window.location.origin,
    });
    window.location.assign(`${endpoints().endSession}?${params.toString()}`);
  }, []);

  const selectOrganization = useCallback(
    (organizationId: string) => {
      const token = tokens.current?.accessToken;
      if (token === undefined) return;
      // Only an organization the API itself listed. A tenant id typed in
      // from anywhere else would be refused server-side anyway, but
      // offering it at all would imply it was a choice.
      if (!organizations.some((org) => org.organizationId === organizationId)) return;
      // Read the store, not the render-time `session` prop: this callback
      // is memoised on `organizations` and would otherwise close over a
      // stale session.
      const active = readSession();
      const userId = active.status === "authenticated" ? active.credentials.userId : "";
      if (userId === "") return;
      setSession({
        status: "authenticated",
        credentials: { token, organizationId, userId },
      });
    },
    [organizations],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      configured: isAuthConfigured,
      signIn,
      signOut,
      profile,
      organizations,
      selectOrganization,
    }),
    [session, signIn, signOut, profile, organizations, selectOrganization],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    // A hook that silently returned a signed-out value outside its
    // provider would make a missing <AuthProvider> look like a user who
    // had not signed in — indistinguishable, and wrong.
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return context;
}
