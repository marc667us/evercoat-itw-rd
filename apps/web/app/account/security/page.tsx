"use client";

/**
 * Security — your session, and where your credentials actually live.
 *
 * 🔴 THIS PAGE CHANGES NO PASSWORD, AND THAT IS THE ARCHITECTURE RATHER THAN A
 * GAP. Keycloak owns identity: this application cannot create a credential and
 * must not appear able to change one. A password form here would either post
 * nowhere or post somewhere that is not the system of record — and a security
 * screen that lies about where the credential lives is worse than no screen.
 *
 * So it does the two things it honestly can: end the session, and hand the
 * person to the place that does own their credentials. Keycloak's account
 * console is a real, deployed surface — it is where password changes and
 * two-factor enrolment happen.
 *
 * 🔴 AND IT EXPLAINS THE ONE THING EVERY USER OF THIS APPLICATION NOTICES.
 * Reloading the page signs you out. That is ADR-025 working as designed — the
 * token is held in memory, never in `localStorage`, because storage is readable
 * by any script on the origin and one XSS would become a stolen session that
 * outlives the page. Unexplained it reads as a bug; explained it reads as a
 * decision, and the sign-in round trip afterwards usually costs no password
 * because the realm's own cookie is still valid.
 */

import { EntityHeader } from "@/components/ui/entity-header";
import { useAuth } from "@/components/providers/auth-provider";
import { KEYCLOAK_REALM, KEYCLOAK_URL, isAuthConfigured } from "@/lib/auth/config";

export default function SecurityPage() {
  const { profile, signOut, session } = useAuth();

  // The realm's own account console. Built from the SAME constants the sign-in
  // flow uses, so it cannot point at a different realm than the one that
  // issued the session.
  const accountConsole =
    KEYCLOAK_URL === null ? null : `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/account/`;

  return (
    <div>
      <EntityHeader
        eyebrow="Your account"
        title="Security"
        crumbs={[{ label: "Dashboard", href: "/dashboard" }]}
      />

      <div className="space-y-8 p-6">
        <section className="max-w-3xl">
          <h2 className="text-sm font-semibold text-slate-900">This session</h2>
          {profile === null ? (
            <p className="mt-1 text-sm text-slate-600">
              You are not signed in.
            </p>
          ) : (
            <>
              <p className="mt-1 text-sm text-slate-700">
                Signed in as <strong>{profile.displayName}</strong> ({profile.email}).
              </p>
              <button
                type="button"
                className="mt-3 rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700"
                onClick={signOut}
              >
                Sign out
              </button>
              {/* ⚠️ IT ENDS THE SESSION AT THE PROVIDER TOO, not just here.
                  Discarding the token locally while the realm's cookie stays
                  valid means the next "Sign in" returns the same user with no
                  prompt — which looks exactly like sign-out having failed. */}
              <p className="mt-2 text-xs text-slate-600">
                This discards the token held in this tab <em>and</em> ends the
                session at the identity provider, so signing in again asks who
                you are.
              </p>
            </>
          )}
        </section>

        <section className="max-w-3xl">
          <h2 className="text-sm font-semibold text-slate-900">
            Password and two-factor
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-slate-600">
            Your credentials are held by <strong>Keycloak</strong>, not by this
            application. Changing a password, enrolling a second factor and
            reviewing your active devices all happen in its account console.
          </p>
          {accountConsole === null ? (
            <p className="mt-2 text-sm text-slate-600">
              This build has no identity provider compiled in, so there is no
              account console to open. {isAuthConfigured ? "" : "Sign-in is unavailable here too."}
            </p>
          ) : (
            <p className="mt-2 text-sm">
              {/* A plain anchor, not a Link: it leaves the application entirely
                  and belongs to a different origin. */}
              <a
                href={accountConsole}
                target="_blank"
                rel="noreferrer noopener"
                className="underline underline-offset-2"
              >
                Open the Keycloak account console
              </a>{" "}
              <span className="text-xs text-slate-600">(opens in a new tab)</span>
            </p>
          )}
        </section>

        <section className="max-w-3xl">
          <h2 className="text-sm font-semibold text-slate-900">
            Why reloading signs you out
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-slate-600">
            Your access token is held <strong>in memory only</strong>. It is
            never written to browser storage, because anything stored there is
            readable by any script on the page — so a single injected script
            would become a stolen session that outlives your visit. The cost is
            that a page reload has nothing to restore, and you are anonymous
            again.
          </p>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">
            Signing back in is usually a redirect and not a password: the
            identity provider&rsquo;s own session is still valid, so it returns
            you without asking. There is deliberately no hidden-iframe silent
            renew — it depends on a third-party cookie that Safari blocks and
            Chrome is removing, and a mechanism that works in development and
            quietly stops working for some users in production is worse than one
            that visibly asks.
          </p>
          {session.status === "anonymous" && (
            <p className="mt-2 text-xs text-slate-600">
              Right now: {session.reason}.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
