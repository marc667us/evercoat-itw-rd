/**
 * Where Keycloak sends the browser back to.
 *
 * A real page in the static export, not a route handler — there are none,
 * and that is the whole reason this application does not use next-auth
 * (ADR-025). Its deployed URL is `/auth/callback/` because `next.config`
 * sets `trailingSlash`, and the realm must be told that exact string.
 *
 * 🔴 THE `state` CHECK HERE IS NOT A FORMALITY.
 *
 * PKCE proves the token request came from whoever began the flow. It says
 * nothing about whether THIS browser began it. Without the `state` check,
 * an attacker can hand a victim a callback URL carrying the attacker's
 * own authorization code, and the victim is silently signed in to the
 * ATTACKER's account — after which every formula they open and every
 * approval they give is recorded against it. In an application whose
 * records are controlled and audited, that is worse than a stolen
 * session.
 *
 * So a mismatch is a hard stop with a named reason, never a retry.
 */

"use client";

import { useEffect, useState } from "react";

import Link from "next/link";

import { KEYCLOAK_CLIENT_ID, endpoints, isAuthConfigured } from "@/lib/auth/config";
import { safeReturnTo, takeFlow } from "@/lib/auth/flow-state";
import { exchangeCode } from "@/lib/auth/pkce";
import { redirectUri } from "@/components/providers/auth-provider";

type Phase =
  | { readonly kind: "working" }
  | { readonly kind: "failed"; readonly reason: string };

export default function AuthCallbackPage() {
  const [phase, setPhase] = useState<Phase>({ kind: "working" });

  useEffect(() => {
    let cancelled = false;
    const fail = (reason: string) => {
      if (!cancelled) setPhase({ kind: "failed", reason });
    };

    void (async () => {
      if (!isAuthConfigured) {
        fail("this build has no identity provider configured, so there is nothing to complete");
        return;
      }

      const params = new URLSearchParams(window.location.search);

      // The provider's own refusal, surfaced verbatim. `access_denied`
      // means the user pressed cancel and is not an error to apologise
      // for; anything else is worth reading.
      const providerError = params.get("error");
      if (providerError !== null) {
        const description = params.get("error_description");
        fail(
          providerError === "access_denied"
            ? "sign-in was cancelled"
            : `the identity provider refused: ${providerError}${description ? ` — ${description}` : ""}`,
        );
        return;
      }

      const code = params.get("code");
      const state = params.get("state");
      // Take-once: the verifier is cleared here whether or not the rest
      // succeeds, so a failed attempt cannot leave one behind to be
      // replayed against a second intercepted code.
      const flow = takeFlow();

      if (code === null || state === null) {
        fail("this page was opened directly rather than by the identity provider");
        return;
      }
      if (flow === null) {
        fail(
          "no sign-in was in progress in this tab — start again from the " +
            "application rather than reloading this page",
        );
        return;
      }
      if (state !== flow.state) {
        // 🔴 Hard stop. See the header: this is the check that stops a
        // victim being signed into somebody else's account.
        fail("the sign-in response did not match the request this tab started");
        return;
      }

      try {
        const tokens = await exchangeCode({
          tokenEndpoint: endpoints().token,
          clientId: KEYCLOAK_CLIENT_ID,
          redirectUri: redirectUri(),
          code,
          verifier: flow.verifier,
        });

        const adopt = (
          window as unknown as {
            __evercoatAdoptTokens?: (t: {
              accessToken: string;
              refreshToken: string | null;
              expiresAt: number;
            }) => Promise<void>;
          }
        ).__evercoatAdoptTokens;

        if (adopt === undefined) {
          fail("the application shell is not running, so the session cannot be handed over");
          return;
        }

        await adopt(tokens);
        if (cancelled) return;
        // replace(), not assign(): the callback URL carries a spent
        // authorization code, and leaving it in history means Back
        // re-runs a flow that can only fail.
        window.location.replace(safeReturnTo(flow.returnTo, window.location.origin));
      } catch (error) {
        fail(error instanceof Error ? error.message : "the token exchange failed");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="mx-auto flex max-w-lg flex-col gap-4 px-6 py-16">
      <h1 className="text-xl font-semibold text-slate-900">
        {phase.kind === "working" ? "Completing sign-in…" : "Sign-in did not complete"}
      </h1>

      {phase.kind === "working" ? (
        <p className="text-sm text-slate-600" role="status">
          Exchanging the authorization code for a session.
        </p>
      ) : (
        <>
          {/* role="alert" so a screen reader is told, rather than a
              sighted-only colour change. §11 requires this and axe-core
              checks it. */}
          <p className="text-sm text-slate-700" role="alert">
            {phase.reason}
          </p>
          <Link
            href="/"
            className="w-fit rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Return to the application
          </Link>
        </>
      )}
    </main>
  );
}
