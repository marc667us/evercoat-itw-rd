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
import { fetchFormulas, type Formula } from "./formulations";
import { fetchMaterials, fetchSuppliers, type Material, type Supplier } from "./materials";
import { fetchProjects, type Project } from "./projects";
import { useSession } from "./session";
import { fetchMyWork, type Task } from "./tasks";

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
  | { ok: false; reason: string; failed: boolean } {
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
    // An ABSENCE: this build has nothing to call. Known before any
    // request, and not a failure.
    return { ok: false, reason: API_UNCONFIGURED_REASON, failed: false };
  }
  if (session.status !== "authenticated") {
    // 🔴 `failed` DECIDES WHETHER THE FIXTURE IS ALLOWED.
    //
    // Anonymity from having nobody to sign in as is an absence.
    // Anonymity because `/api/me` returned 500 is a FAILURE, and
    // substituting demonstration rows for it renders a real outage as a
    // full, plausible, synthetic application. Codex found that.
    return { ok: false, reason: session.reason, failed: session.failed === true };
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
    // 🔴 THE USER IS IN THE KEY, NOT JUST THE ORGANIZATION.
    //
    // With `[key, organizationId]` alone, Alice could load My Work, sign
    // out, and Bob could sign in to the SAME organization and be served
    // Alice's rows from the cache — under a LIVE banner — until a refetch
    // replaced them, and indefinitely if it stalled. Codex found it.
    queryKey: [
      key,
      resolved.ok ? resolved.credentials.organizationId : null,
      resolved.ok ? resolved.credentials.userId : null,
    ],
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
    if (resolved.failed) {
      // A request was made and it failed. Show the failure; substitute
      // nothing. This is the same contract the query-error branch below
      // honours, applied one level up.
      return {
        data: undefined,
        source: "live",
        sourceReason: null,
        isLoading: false,
        error: new Error(resolved.reason),
      };
    }
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

export function useProjects<TShown>(
  demo: TShown,
  project: (live: Project[]) => TShown,
): Sourced<TShown> {
  return useSourcedList("projects", demo, project, fetchProjects);
}

export function useFormulas<TShown>(
  demo: TShown,
  project: (live: Formula[]) => TShown,
): Sourced<TShown> {
  return useSourcedList("formulations", demo, project, fetchFormulas);
}

/**
 * The caller's inbox.
 *
 * 🔴 THE QUERY KEY INCLUDES THE ORGANIZATION, WHICH IS WHY THIS IS SAFE.
 *
 * `useSourcedList` keys every query on the active organization id, so
 * switching tenants does not serve the previous tenant's rows out of the
 * cache while the new request is in flight. That matters more here than
 * on a reference list: My Work is per-USER as well as per-tenant, and a
 * stale inbox showing another organization's tasks would read as a
 * cross-tenant leak even though the API had behaved correctly.
 */
export function useMyWork<TShown>(
  demo: TShown,
  project: (live: Task[]) => TShown,
): Sourced<TShown> {
  return useSourcedList("my-work", demo, project, fetchMyWork);
}
