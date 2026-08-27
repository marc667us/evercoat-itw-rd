"use client";

/**
 * Front door. Sends the visitor to the screen they chose to open on.
 *
 * WHY THIS IS A CLIENT REDIRECT AND NOT `redirect("/dashboard")`.
 *
 * This page used to be a server component calling `redirect()`. That works
 * under `output: "standalone"`, where a Node server is there to answer 307.
 * It does NOT survive `output: "export"`: there is no server, so Next has
 * nothing to emit for this route and writes an error document —
 * `out/index.html` came out as `<html id="__next_error__">` while
 * `next build` exited 0 and printed `✓ Exporting (2/2)`. The front door
 * was an error page with every gate green.
 *
 * The obvious repair — a Render redirect rule for `/` — does not work
 * either. Render's rule engine is documented as: "Render does not apply
 * redirect or rewrite rules to a path if a resource exists at that path."
 * `out/index.html` exists, so the rule would never fire. Deleting the file
 * after the build would work and is exactly the kind of second mechanism
 * that later disagrees with the first.
 *
 * So the redirect is expressed once, here, in a form that holds in BOTH
 * build modes: a real page that navigates on mount. The cost is one frame
 * of "Redirecting…" on the server build, which previously got a 307. That
 * is the deliberate trade — one mechanism that cannot drift, over two that
 * can.
 *
 * The visible link is not decoration: it is the whole page for a visitor
 * with JavaScript disabled or still loading, who would otherwise sit on a
 * blank screen with no way forward.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { DEFAULT_LANDING, readLanding } from "@/lib/preferences";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    // 🔴 THE CHOSEN SCREEN, NOT A CONSTANT. Settings offers three destinations
    // under "After signing in, open"; this used to be a hard `/dashboard`, so
    // the preference had no reader anywhere in the application and the screen
    // asserted a behaviour nothing implemented. Both reviewers found it — and
    // it is the project's own rule about a setting with no enforcement point,
    // reached from the other side.
    //
    // Read here rather than in a provider because this is the front door: it
    // is where "where does the application open" is actually decided, and it
    // works signed in or out.
    //
    // `replace`, not `push` — the front door should not become a back-button
    // trap that bounces the visitor straight back out to it.
    router.replace(readLanding());
  }, [router]);

  return (
    <div className="p-6">
      {/* A real <h1>, not an aria-live paragraph.
          The first version used aria-live="polite" on text that is present
          at first render and never changes. A live region announces
          CHANGES to its contents, so static text inside one is never
          announced — the accessibility benefit claimed in the comment did
          not exist. Every other route has a heading; this one had none, so
          a screen-reader user landing here got an unlabelled page.
          The layout already supplies the <main> landmark. */}
      <h1 className="text-sm font-medium text-slate-600">
        Opening the application…
      </h1>
      {/* ⚠️ THE DEFAULT, NOT THE PREFERENCE, AND DELIBERATELY SO. This link is
          the whole page for a visitor with JavaScript disabled or still
          loading. The preference lives in `localStorage`, which is only
          readable by script, so a link that claimed to honour it would be a
          link that could not — and rendering it from the preference after
          hydration would change the destination under a reader mid-click. */}
      <Link
        href={DEFAULT_LANDING}
        className="mt-2 inline-block text-sm font-medium text-slate-900 underline"
      >
        Continue to the dashboard
      </Link>
    </div>
  );
}
