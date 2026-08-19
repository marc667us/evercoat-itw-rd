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
 * The cost is that a refresh ends the session. The recovery is a redirect
 * to Keycloak which, if its own SSO cookie is still alive, returns
 * without asking for a password — so the user experiences a flicker, not
 * a login form.
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

export interface AuthContextValue {
  readonly session: SessionState;
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
}

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
  const establish = useCallback(async (accessToken: string): Promise<void> => {
    if (API_BASE_URL === null) {
      setSession({
        status: "anonymous",
        reason:
          "signed in, but this build was compiled without an API address, so " +
          "there is nothing to sign in to",
      });
      return;
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
      });
      return;
    }

    if (!response.ok) {
      setSession({
        status: "anonymous",
        reason: `the API refused to identify you (HTTP ${response.status})`,
      });
      return;
    }

    const body = (await response.json()) as {
      organizations?: {
        organization_id: string;
        name: string;
        code: string;
        roles?: string[];
      }[];
    };

    const choices: OrganizationChoice[] = (body.organizations ?? []).map((org) => ({
      organizationId: org.organization_id,
      name: org.name,
      code: org.code,
      roles: org.roles ?? [],
    }));

    const first = choices[0];
    if (first === undefined) {
      // Absence must never present as success. An empty list would render
      // as a working sign-in into an application with nothing in it.
      setSession({
        status: "anonymous",
        reason: "you are signed in but belong to no organization, so there is nothing to show",
      });
      return;
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

    setOrganizations(choices);
    setSession({
      status: "authenticated",
      credentials: { token: accessToken, organizationId: chosen.organizationId },
    });
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
            await establish(next.accessToken);
            if (!mounted.current) return;
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
      await establish(live.accessToken);
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
    if (!isAuthConfigured && readSession().status !== "authenticated") {
      setSession({ status: "anonymous", reason: AUTH_UNCONFIGURED_REASON });
    }
  }, []);

  const signIn = useCallback(async () => {
    if (!isAuthConfigured) return;
    const challenge = await createChallenge();
    const returnTo = safeReturnTo(
      window.location.pathname + window.location.search,
      window.location.origin,
    );
    saveFlow(challenge, returnTo, false);
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
    const refreshToken = tokens.current?.refreshToken ?? null;
    tokens.current = null;
    setOrganizations([]);
    setSession({ status: "anonymous", reason: "you have signed out" });

    if (!isAuthConfigured || refreshToken === null) return;
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
      setSession({ status: "authenticated", credentials: { token, organizationId } });
    },
    [organizations],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      configured: isAuthConfigured,
      signIn,
      signOut,
      organizations,
      selectOrganization,
    }),
    [session, signIn, signOut, organizations, selectOrganization],
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
