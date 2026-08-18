"use client";

/**
 * Whether this browser can reach the API.
 *
 * WHY A PRODUCT FEATURE AND NOT A DEBUG WIDGET
 * --------------------------------------------
 * This application is about to be one that cannot function without its
 * API, and it is deployed today as a static site with no API beside it.
 * "The screen is showing old figures" and "the screen cannot reach the
 * database" look identical to a chemist, and the second one is the only
 * one they can act on — by telling somebody, rather than by trusting the
 * number in front of them.
 *
 * It is also the ONLY unauthenticated call the application can make, and
 * therefore the only end-to-end proof available while no identity
 * provider is deployed: `/health/ready` needs no token, so this genuinely
 * crosses the browser/API boundary rather than standing in for a call
 * that cannot yet be made.
 *
 * A 503 IS REPORTED AS REACHED. `/health/ready` answers 503 when the
 * database is down, and that is an API that ANSWERED — blaming the
 * network for a database fault would send whoever reads it to the wrong
 * team. The two states are named separately for that reason.
 */

import { useEffect, useState } from "react";

import { apiHealth } from "@/lib/api/client";
import { isApiConfigured } from "@/lib/api/config";

type Health =
  | { state: "checking" }
  | { state: "unconfigured" }
  | { state: "reachable"; detail: string }
  | { state: "degraded"; detail: string }
  | { state: "unreachable"; detail: string };

export function ApiStatus() {
  const [health, setHealth] = useState<Health>(
    // No flicker of "checking" on a build that has no API to check. The
    // static deployment is in this state permanently, and a spinner that
    // never resolves reads as a hang.
    isApiConfigured ? { state: "checking" } : { state: "unconfigured" },
  );

  useEffect(() => {
    if (!isApiConfigured) return;

    const controller = new AbortController();
    let cancelled = false;

    apiHealth(controller.signal).then((result) => {
      if (cancelled) return;
      if (!result.reachable) {
        setHealth({ state: "unreachable", detail: result.detail });
      } else if (result.status === 200) {
        setHealth({ state: "reachable", detail: result.detail });
      } else {
        setHealth({ state: "degraded", detail: result.detail });
      }
    });

    return () => {
      cancelled = true;
      // Abort on unmount so a slow probe cannot resolve into a component
      // that is gone, and so navigating away does not leave the request
      // hanging.
      controller.abort();
    };
  }, []);

  // Colour is never the only signal — §11, and the measured ΔE between
  // this project's pass-green and fail-red is 4.2 under deuteranopia. Each
  // state carries a distinct glyph AND distinct words.
  const presentation: Record<Health["state"], { mark: string; label: string; className: string }> = {
    checking: {
      mark: "…",
      label: "Checking API",
      className: "border-slate-200 text-slate-500",
    },
    unconfigured: {
      mark: "◌",
      label: "No API",
      className: "border-amber-300 bg-amber-50 text-amber-900",
    },
    reachable: {
      mark: "✓",
      label: "API ready",
      className: "border-emerald-300 bg-emerald-50 text-emerald-900",
    },
    degraded: {
      mark: "!",
      label: "API degraded",
      className: "border-amber-300 bg-amber-50 text-amber-900",
    },
    unreachable: {
      mark: "✕",
      label: "API unreachable",
      className: "border-red-300 bg-red-50 text-red-900",
    },
  };

  const shown = presentation[health.state];
  const detail =
    health.state === "unconfigured"
      ? "this build was compiled without an API address"
      : "detail" in health
        ? health.detail
        : "contacting the API";

  return (
    <span
      data-testid="api-status"
      data-state={health.state}
      title={detail}
      className={`shrink-0 rounded border px-2 py-1 text-[11px] font-medium ${shown.className}`}
    >
      <span aria-hidden>{shown.mark}</span>{" "}
      <span>{shown.label}</span>
      {/* The full sentence for assistive technology: a two-word pill is
          not enough to act on, and `title` is not announced reliably. */}
      <span className="sr-only"> — {detail}</span>
    </span>
  );
}
