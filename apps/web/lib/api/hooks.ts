"use client";

/**
 * The hooks a page uses, and the one place the live-or-demonstration
 * decision is made.
 *
 * 🔴 THE SHAPE OF THE RETURN VALUE IS THE WHOLE POINT.
 *
 * Every hook returns `source`, and it is not optional. A page cannot
 * render rows without also being handed the answer to "where did these
 * come from", so it cannot forget to say. That is deliberate defensive
 * design against this project's most-repeated UI failure: a screen of
 * plausible figures that is indistinguishable from a working one.
 *
 * The fallback is NOT "the request failed, show demo data". That would
 * hide an outage behind a working-looking screen. It is narrower and it is
 * stated: demonstration data is used when there is nothing to call or
 * no one to call as — a build with no API address, or a deployment with no
 * identity provider. Those are properties of the environment, known before
 * any request is made, and neither is a failure.
 *
 * A request that IS made and fails stays failed. The page shows the error.
 */

import { useQuery } from "@tanstack/react-query";

import {
  ApiNoSessionError,
  ApiNotConfiguredError,
  type ApiCredentials,
} from "./client";
import { API_UNCONFIGURED_REASON, isApiConfigured, type DataSource } from "./config";
import { fetchMaterials, fetchSuppliers, type Material, type Supplier } from "./materials";
import { useSession } from "./session";

/**
 * What every screen receives.
 *
 * `source` and `sourceReason` travel together: a demonstration screen must
 * be able to say WHY it is one, or the banner is a shrug.
 */
export interface Sourced<T> {
  readonly data: T | undefined;
  readonly source: DataSource;
  readonly sourceReason: string | null;
  readonly isLoading: boolean;
  readonly error: Error | null;
}

/**
 * Decide, before any request, whether this environment can serve live
 * data at all.
 *
 * Returns the credentials when it can, or the reason it cannot. Doing this
 * up front rather than catching a failure afterwards is what keeps
 * "nothing to call" distinguishable from "the call failed".
 */
function useCredentials():
  | { ok: true; credentials: ApiCredentials }
  | { ok: false; reason: string } {
  // `useSession()` is called UNCONDITIONALLY and before any branch.
  //
  // The first version of this returned early when the API was
  // unconfigured and called the hook afterwards. `isApiConfigured` is a
  // build-time constant so the branch never actually varies at runtime --
  // which is precisely what makes it the dangerous kind of hook bug: it
  // would have worked, passed every test, and broken the first time
  // anything above it became conditional. Hooks are ordered by call, not
  // by reachability.
  //
  // Named `use*` for the same reason: the lint rule cannot police a
  // helper it does not recognise as a hook.
  const session = useSession();

  if (!isApiConfigured) {
    return { ok: false, reason: API_UNCONFIGURED_REASON };
  }
  if (session.status !== "authenticated") {
    return { ok: false, reason: session.reason };
  }
  return { ok: true, credentials: session.credentials };
}

/**
 * One list resource, live when possible and demonstration otherwise.
 *
 * `demo` is a value the caller already has -- the demonstration dataset is
 * bundled, so there is nothing to load and no state in which the screen is
 * empty while it decides.
 */
function useSourcedList<TLive, TShown>(
  key: string,
  demo: TShown,
  project: (live: TLive) => TShown,
  fetcher: (credentials: ApiCredentials, signal?: AbortSignal) => Promise<TLive>,
): Sourced<TShown> {
  const resolved = useCredentials();

  const query = useQuery({
    queryKey: [key, resolved.ok ? resolved.credentials.organizationId : null],
    // `enabled` is what stops a request that cannot succeed from being
    // made at all. Without it the hook would fire, fail, and the page would
    // show "the API did not accept this session" on a deployment that has
    // no session by design -- an error message for a non-error.
    enabled: resolved.ok,
    queryFn: ({ signal }) => {
      if (!resolved.ok) {
        // Unreachable while `enabled` is false, and it throws rather than
        // returning empty so that if `enabled` is ever changed carelessly
        // the result is a loud failure and not silent empty rows.
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return fetcher(resolved.credentials, signal);
    },
  });

  if (!resolved.ok) {
    return {
      data: demo,
      source: "demonstration",
      sourceReason: resolved.reason,
      isLoading: false,
      error: null,
    };
  }

  return {
    // On error, `data` is undefined -- NOT the demonstration rows. A
    // screen whose request failed must show that it failed.
    data: query.data === undefined ? undefined : project(query.data),
    source: "live",
    sourceReason: null,
    isLoading: query.isPending,
    error: (query.error as Error | null) ?? null,
  };
}

export function useMaterials<TShown>(
  demo: TShown,
  project: (live: Material[]) => TShown,
): Sourced<TShown> {
  return useSourcedList("materials", demo, project, fetchMaterials);
}

export function useSuppliers<TShown>(
  demo: TShown,
  project: (live: Supplier[]) => TShown,
): Sourced<TShown> {
  return useSourcedList("suppliers", demo, project, fetchSuppliers);
}
