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

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ApiNoSessionError,
  ApiNotConfiguredError,
  type ApiCredentials,
} from "./client";
import {
  API_UNCONFIGURED_REASON,
  isApiConfigured,
  type DataSource,
} from "./config";
import { fetchFormulas, type Formula } from "./formulations";
import {
  fetchKnowledgeDocuments,
  ingestKnowledgeDocument,
  searchKnowledge,
  type IngestRequest,
  type IngestResult,
  type KnowledgeDocumentPage,
  type KnowledgePassage,
} from "./knowledge";
import { fetchBatches, type Batch } from "./laboratory";
import {
  fetchMaterials,
  fetchSuppliers,
  type Material,
  type Supplier,
} from "./materials";
import { fetchProjects, type Project } from "./projects";
import { useSession } from "./session";
import { fetchMyWork, type Task } from "./tasks";
import { fetchTests, type Test } from "./testing";

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
    return {
      ok: false,
      reason: session.reason,
      failed: session.failed === true,
    };
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
  fetcher: (
    credentials: ApiCredentials,
    signal?: AbortSignal,
  ) => Promise<TLive>,
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

/**
 * A resource that has NO demonstration equivalent.
 *
 * 🔴 WHY THESE SCREENS DO NOT FALL BACK TO A FIXTURE.
 *
 * `demo-data.json` carries organizations, users, stages, opportunities,
 * projects, tasks, suppliers, materials and formulas. It carries **no
 * batches, no samples, no tests and no methods** — so Laboratory and
 * Testing have nothing to fall back TO.
 *
 * That absence is worth keeping. The operator has flagged the
 * demonstration banner on the live site as a thing to remove, not to
 * spread; and fabricating laboratory batches and physical test results
 * for a formulated-chemicals platform is materially worse than
 * fabricating a supplier list. A synthetic adhesion measurement sitting
 * in a queue labelled "Testing" is exactly the kind of record §3 rule 3
 * exists to keep separable from a real one — *"physical testing verifies;
 * models only predict"* — and a reader who scrolls past a banner sees a
 * measurement, not a fixture.
 *
 * So these screens have two honest states and no third: rows from the
 * database, or a plain statement that this build has no API to ask.
 *
 * This does NOT introduce a third `DataSource`. `config.ts` argues
 * correctly that a screen which cannot say where its numbers came from
 * must not display numbers — and this screen displays none. It knows
 * exactly where its zero rows came from and says so.
 */
export interface LiveOnly<T> {
  readonly data: T | undefined;
  readonly isLoading: boolean;
  readonly error: Error | null;
  /**
   * Why this build cannot serve the screen at all, or null when it can.
   *
   * An ABSENCE, never a failure — no API address compiled in, or nobody
   * to act as. A request that was made and failed lands in `error`, and
   * the two must not be conflated: one is a deployment that was never
   * given an API, the other is an outage.
   */
  readonly unavailable: string | null;
}

function useLiveOnlyList<TLive, TShown>(
  key: string,
  project: (live: TLive) => TShown,
  fetcher: (
    credentials: ApiCredentials,
    signal?: AbortSignal,
  ) => Promise<TLive>,
): LiveOnly<TShown> {
  const resolved = useCredentials();

  const query = useQuery({
    queryKey: [
      key,
      resolved.ok ? resolved.credentials.organizationId : null,
      resolved.ok ? resolved.credentials.userId : null,
    ],
    enabled: resolved.ok,
    queryFn: ({ signal }) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return fetcher(resolved.credentials, signal);
    },
  });

  if (!resolved.ok) {
    // The same distinction `useSourcedList` draws, and for the same
    // reason: a failed `/api/me` is an outage and must not render as a
    // tidy "not available on this build" notice.
    return resolved.failed
      ? {
          data: undefined,
          isLoading: false,
          error: new Error(resolved.reason),
          unavailable: null,
        }
      : {
          data: undefined,
          isLoading: false,
          error: null,
          unavailable: resolved.reason,
        };
  }

  return {
    data: query.data === undefined ? undefined : project(query.data),
    isLoading: query.isPending,
    error: (query.error as Error | null) ?? null,
    unavailable: null,
  };
}

/** Laboratory batches. Live or nothing — see `LiveOnly`. */
export function useBatches<TShown>(
  project: (live: Batch[]) => TShown,
): LiveOnly<TShown> {
  return useLiveOnlyList("laboratory-batches", project, fetchBatches);
}

/** The test queue. Live or nothing — see `LiveOnly`. */
export function useTests<TShown>(
  project: (live: Test[]) => TShown,
): LiveOnly<TShown> {
  return useLiveOnlyList("testing-tests", project, fetchTests);
}

/**
 * The knowledge library. Live or nothing — see `LiveOnly`.
 *
 * 🔴 NO DEMONSTRATION FIXTURE, DELIBERATELY. `demo-data.json` has no knowledge
 * documents and must not gain any. A synthetic "standard" or "procedure" is
 * materially worse than a synthetic supplier: this library is the text MSD
 * QUOTES back as sourced evidence, so a fabricated passage would arrive in an
 * answer wearing a real document's clothes. An empty screen that says why is
 * the honest state.
 */
export function useKnowledgeDocuments<TShown>(
  project: (live: KnowledgeDocumentPage) => TShown,
): LiveOnly<TShown> {
  return useLiveOnlyList("knowledge-documents", project, fetchKnowledgeDocuments);
}

/**
 * A knowledge search, run only when there is something to search for.
 *
 * `enabled` is the whole design here. `useLiveOnlyList` fires on mount, which
 * is right for a list and wrong for a search: it would query the library for
 * the empty string on every visit, and the API answers an unsearchable query
 * with `[]` — so the screen would render "no matches" before the user had
 * typed anything, which reads as an empty library.
 */
export function useKnowledgeSearch(query: string): LiveOnly<KnowledgePassage[]> {
  const resolved = useCredentials();
  const trimmed = query.trim();

  const result = useQuery({
    queryKey: [
      "knowledge-search",
      trimmed,
      resolved.ok ? resolved.credentials.organizationId : null,
      resolved.ok ? resolved.credentials.userId : null,
    ],
    enabled: resolved.ok && trimmed.length > 0,
    queryFn: ({ signal }) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return searchKnowledge(resolved.credentials, trimmed, signal);
    },
  });

  if (!resolved.ok) {
    return resolved.failed
      ? {
          data: undefined,
          isLoading: false,
          error: new Error(resolved.reason),
          unavailable: null,
        }
      : {
          data: undefined,
          isLoading: false,
          error: null,
          unavailable: resolved.reason,
        };
  }

  return {
    data: trimmed.length === 0 ? undefined : result.data,
    // `isPending` is TRUE for a disabled query that has never run, so asking
    // it directly would leave the screen spinning before anything was typed.
    isLoading: trimmed.length > 0 && result.isPending,
    error: (result.error as Error | null) ?? null,
    unavailable: null,
  };
}

/**
 * Add a document to the knowledge library.
 *
 * 🔴 THIS HOOK IS THE REASON I74 IS ACTUALLY CLOSED.
 *
 * The route existed a commit earlier and NOTHING CALLED IT: the client
 * function was written, exported, and reachable only by hand-constructing an
 * HTTP request. Closing "the tier has no production write path" with a path no
 * user of the application can walk is the same defect one level up, and the
 * Supervisor said so. Asking the standing question of a ROUTE, not just of a
 * table, is what this hook answers.
 *
 * On success the document list is invalidated rather than optimistically
 * appended: the server decides the classification when the caller omitted one,
 * counts the chunks, and may return fewer than the author expects. Rendering a
 * guess and correcting it a moment later would show a classification the
 * database never agreed to.
 */
export function useIngestKnowledgeDocument(): {
  readonly submit: (request: IngestRequest) => void;
  readonly isPending: boolean;
  readonly error: Error | null;
  readonly result: IngestResult | undefined;
  readonly reset: () => void;
  readonly unavailable: string | null;
} {
  const resolved = useCredentials();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (request: IngestRequest) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return ingestKnowledgeDocument(resolved.credentials, request);
    },
    onSuccess: () => {
      // Both lists are now stale: the document list obviously, and any search
      // whose words the new text happens to match.
      void queryClient.invalidateQueries({ queryKey: ["knowledge-documents"] });
      void queryClient.invalidateQueries({ queryKey: ["knowledge-search"] });
    },
  });

  return {
    submit: mutation.mutate,
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
    result: mutation.data,
    reset: mutation.reset,
    unavailable: resolved.ok ? null : resolved.failed ? null : resolved.reason,
  };
}
