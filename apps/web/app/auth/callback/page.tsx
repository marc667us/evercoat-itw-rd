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
import { useRouter } from "next/navigation";

import { KEYCLOAK_CLIENT_ID, endpoints, isAuthConfigured } from "@/lib/auth/config";
import { safeReturnTo, takeFlow } from "@/lib/auth/flow-state";
import { exchangeCode } from "@/lib/auth/pkce";
import { redirectUri } from "@/components/providers/auth-provider";

type Phase =
  | { readonly kind: "working" }
  | { readonly kind: "failed"; readonly reason: string };

/**
 * 🔴 STRICT MODE MOUNTS EVERY EFFECT TWICE, AND `takeFlow()` IS TAKE-ONCE.
 *
 * `reactStrictMode` is on. In development React runs mount → cleanup →
 * mount, so the effect below ran twice: the first pass consumed and
 * cleared the flow, and the second found nothing and rendered "no
 * sign-in was in progress in this tab" — on a sign-in that had in fact
 * just succeeded. A developer would have chased a phantom.
 *
 * The take-once property is deliberate and must not be relaxed, so the
 * SECOND invocation is suppressed instead. Module scope, not a ref,
 * because StrictMode's two mounts are two component instances; a ref is
 * fresh in each. Keyed on the query string so a genuine second callback
 * — a different code — is still processed. The Supervisor found this.
 */
let consumedQuery: string | null = null;

export default function AuthCallbackPage() {
  const [phase, setPhase] = useState<Phase>({ kind: "working" });
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    const fail = (reason: string) => {
      if (!cancelled) setPhase({ kind: "failed", reason });
    };

    void (async () => {
      if (consumedQuery === window.location.search) return;
      consumedQuery = window.location.search;

      if (!isAuthConfigured) {
        fail("this build has no identity provider configured, so there is nothing to complete");
        return;
      }

      const params = new URLSearchParams(window.location.search);

      // 🔴 THE FLOW IS CONSUMED FIRST, BEFORE ANY EARLY RETURN.
      //
      // It used to be taken after the provider-error branch, so
      // `?error=access_denied` returned with the verifier still sitting in
      // sessionStorage — and an attacker-supplied error callback could
      // therefore leave a pending flow alive to be matched against a
      // later, attacker-chosen code. Genuine Keycloak denials left it
      // behind too. Take-once means take-once on EVERY path, including
      // the ones that look like nothing happened. Codex found it.
      const flow = takeFlow();

      // The provider's own refusal. `access_denied` means the user
      // pressed cancel and is not an error to apologise for.
      //
      // 🔴 THE DESCRIPTION IS NOT RENDERED. It is attacker-influenceable
      // — anyone can put `?error_description=` on this URL — and a
      // misbehaving gateway can echo the submitted form, which on this
      // page would mean the code verifier. The error CODE is a short
      // enumerated token and is safe to show; free text from the query
      // string is not.
      const providerError = params.get("error");
      if (providerError !== null) {
        fail(
          providerError === "access_denied"
            ? "sign-in was cancelled"
            : `the identity provider refused sign-in (${providerError.slice(0, 64)})`,
        );
        return;
      }

      const code = params.get("code");
      const state = params.get("state");

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

        // 🔴 THE ROUTER, NOT `window.location`. THIS IS THE WHOLE FLOW.
        //
        // The first version called `window.location.replace(...)`, which
        // is a FULL DOCUMENT NAVIGATION. The access token is held in
        // memory by design — `auth-provider.tsx` says so in its own
        // header — so tearing down the JS context threw away the session
        // that had just been established, one statement after
        // establishing it. The user landed on the dashboard signed OUT,
        // pressed Sign in, and looped forever.
        //
        // Every test passed. Nothing drives a real redirect round trip,
        // so nothing noticed that the feature could not work at all. The
        // Supervisor caught it; Codex did not. It is this project's
        // oldest lesson in its purest form: A GREEN BUILD IS NOT A
        // WORKING FEATURE.
        //
        // `router.replace` transitions inside the same document, so the
        // module-level session survives. `replace`, not `push`, because
        // the callback URL carries a spent authorization code and leaving
        // it in history means Back re-runs a flow that can only fail.
        router.replace(safeReturnTo(flow.returnTo, window.location.origin));
      } catch (error) {
        // 🔴 THE UNDERLYING MESSAGE GOES TO THE CONSOLE, NOT THE PAGE.
        //
        // `exchangeCode` includes the provider's `error_description` and,
        // failing that, the first 200 characters of the response body —
        // which is right for a developer and wrong for a rendered
        // element. A proxy or gateway that echoes the request would put
        // the code verifier or a refresh token into the visible text of a
        // page that anyone shoulder-surfing can read. Codex found it.
        console.error("evercoat: token exchange failed", error);
        fail(
          "the sign-in could not be completed. The details are in the browser " +
            "console; if this persists, the authorization code has probably expired — " +
            "start again from the application.",
        );
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [router]);

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
