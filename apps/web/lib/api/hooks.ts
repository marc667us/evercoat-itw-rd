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
  acceptRootCause,
  closeFailure,
  decideStep,
  fetchApprovalQueue,
  fetchApprovalRoute,
  fetchFailure,
  fetchFailures,
  linkEvidence,
  openInvestigation,
  proposeHypothesis,
  raiseAction,
  recordEvidence,
  rejectHypothesis,
  type ActionRequest,
  type ApprovalQueueItem,
  type ApprovalRoute,
  type EvidenceLinkRequest,
  type EvidenceRequest,
  type FailureCreateRequest,
  type FailureDetail,
  type FailureSummary,
  type HypothesisRequest,
  type StepDecisionRequest,
} from "./failures";
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
import {
  fetchKnowledgeDocuments,
  ingestKnowledgeDocument,
  searchKnowledge,
  type IngestRequest,
  type IngestResult,
  type KnowledgeDocumentPage,
  type KnowledgePassage,
} from "./knowledge";
import {
  authorizeBatch,
  completeBatch,
  createBatch,
  createSample,
  fetchBatch,
  fetchBatches,
  raiseDeviation,
  recordProcessParameter,
  recordWeighing,
  reviewBatch,
  startBatch,
  type Batch,
  type BatchCreateRequest,
  type BatchDetail,
  type DeviationRequest,
  type ProcessParameterRequest,
  type ReviewRequest,
  type SampleRequest,
  type WeighingRequest,
} from "./laboratory";
import {
  classifyFormula,
  createFormula,
  createRevision,
  decideVersion,
  fetchClassifications,
  fetchFormulas,
  fetchVersion,
  fetchVersionComparison,
  fetchVersionEvaluation,
  fetchWeighUp,
  putComponents,
  recordObservedEffect,
  submitVersion,
  type Classification,
  type ClassificationRequest,
  type ComponentInput,
  type Formula,
  type FormulaCreateRequest,
  type FormulaVersionDetail,
  type RevisionRequest,
  type VersionComparison,
  type VersionDecisionRequest,
  type VersionEvaluation,
  type WeighUp,
} from "./formulations";
import {
  fetchMaterials,
  fetchSuppliers,
  type Material,
  type Supplier,
} from "./materials";
import {
  fetchAnalytics,
  fetchTestResultsReport,
  type Analytics,
  type TestResultsReport,
} from "./analysis";
import { fetchProjects, type Project } from "./projects";
import { useSession } from "./session";
import { fetchMyWork, type Task } from "./tasks";
import {
  completeTest,
  confirmTest,
  createTest,
  excludeReplicate,
  fetchTest,
  fetchTestMethods,
  fetchTests,
  recordReplicate,
  recordTestDecision,
  startTest,
  type DecisionRequest,
  type ReplicateRequest,
  type Test,
  type TestCreated,
  type TestCreateRequest,
  type TestDetail,
  type TestMethod,
} from "./testing";

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

// ---------------------------------------------------------------------------
// The batch workspace — one query, and every step of the bench lifecycle
// ---------------------------------------------------------------------------

/**
 * One batch, with its weigh-up sheet.
 *
 * 🔴 THE KEY CARRIES `batchId`, `organizationId` **AND** `userId`. The last
 * one is not decoration: a key of `[resource, orgId]` already served one
 * user's rows to another on this project. Two people at the same bench, in the
 * same organization, do not see the same sheet — RLS filters by project
 * membership — so caching on the organization alone would hand a technician a
 * batch they are not a member of the project for.
 */
export function useBatch(batchId: string): LiveOnly<BatchDetail> {
  const resolved = useCredentials();

  const query = useQuery({
    queryKey: [
      "laboratory-batch",
      batchId,
      resolved.ok ? resolved.credentials.organizationId : null,
      resolved.ok ? resolved.credentials.userId : null,
    ],
    enabled: resolved.ok && batchId.length > 0,
    queryFn: ({ signal }) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return fetchBatch(resolved.credentials, batchId, signal);
    },
  });

  if (!resolved.ok) {
    return resolved.failed
      ? { data: undefined, isLoading: false, error: new Error(resolved.reason), unavailable: null }
      : { data: undefined, isLoading: false, error: null, unavailable: resolved.reason };
  }

  return {
    data: query.data,
    isLoading: query.isPending,
    error: (query.error as Error | null) ?? null,
    unavailable: null,
  };
}

/**
 * Every bench action, behind one hook.
 *
 * 🔴 EACH ONE INVALIDATES AND REFETCHES RATHER THAN PATCHING LOCAL STATE.
 * `status`, and the per-line `deviation`, are DERIVED and server-owned (§10).
 * A screen that advanced `status` optimistically would be computing a
 * safety-critical field in the browser, which is the defect §4 exists to
 * prevent. The round trip is the point, not a cost.
 *
 * The batch list is invalidated too: `unweighed_count` and `deviation_count`
 * on the queue are stale the moment any of these succeeds, and a queue that
 * still shows "3 unweighed" after the third line was weighed is the kind of
 * quiet wrongness that makes people stop trusting the screen.
 */
export function useBatchActions(batchId: string): {
  readonly authorize: () => void;
  readonly start: () => void;
  readonly weigh: (componentId: string, request: WeighingRequest) => void;
  readonly addProcessParameter: (request: ProcessParameterRequest) => void;
  readonly addDeviation: (request: DeviationRequest) => void;
  readonly addSample: (request: SampleRequest) => void;
  readonly complete: () => void;
  readonly review: (request: ReviewRequest) => void;
  readonly isPending: boolean;
  readonly error: Error | null;
  readonly lastAction: string | null;
  readonly reset: () => void;
  readonly unavailable: string | null;
} {
  const resolved = useCredentials();
  const queryClient = useQueryClient();

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["laboratory-batch", batchId] });
    void queryClient.invalidateQueries({ queryKey: ["laboratory-batches"] });
    // A sample is what a test cites, so the test queue can change too.
    void queryClient.invalidateQueries({ queryKey: ["testing-tests"] });
  };

  const credentials = () => {
    if (!resolved.ok) {
      throw isApiConfigured
        ? new ApiNoSessionError(resolved.reason)
        : new ApiNotConfiguredError();
    }
    return resolved.credentials;
  };

  const mutation = useMutation({
    mutationFn: async (job: { readonly label: string; readonly run: () => Promise<unknown> }) => {
      await job.run();
      return job.label;
    },
    onSuccess: refresh,
  });

  const run = (label: string, make: () => Promise<unknown>) =>
    mutation.mutate({ label, run: make });

  return {
    authorize: () => run("authorize", () => authorizeBatch(credentials(), batchId)),
    start: () => run("start", () => startBatch(credentials(), batchId)),
    weigh: (componentId, request) =>
      run("weigh", () => recordWeighing(credentials(), batchId, componentId, request)),
    addProcessParameter: (request) =>
      run("process-parameter", () => recordProcessParameter(credentials(), batchId, request)),
    addDeviation: (request) =>
      run("deviation", () => raiseDeviation(credentials(), batchId, request)),
    addSample: (request) => run("sample", () => createSample(credentials(), batchId, request)),
    complete: () => run("complete", () => completeBatch(credentials(), batchId)),
    review: (request) => run("review", () => reviewBatch(credentials(), batchId, request)),
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
    lastAction: mutation.data ?? null,
    reset: mutation.reset,
    unavailable: resolved.ok ? null : resolved.failed ? null : resolved.reason,
  };
}

// ---------------------------------------------------------------------------
// The test workspace — one query, and every step from planning to confirmation
// ---------------------------------------------------------------------------

/**
 * One test, with its raw replicates and BOTH status fields.
 *
 * 🔴 THE KEY CARRIES `userId` FOR THE SAME REASON `useBatch` DOES. A key of
 * `[resource, orgId]` already served one user's rows to another on this
 * project. It matters more here, not less: two engineers in one organization
 * see different tests, because RLS filters by project membership.
 *
 * This is the ONLY place the traffic light exists. `list_tests` withholds it
 * deliberately, so the queue shows the five stored axes and this view shows
 * the derived disposition — computed by the server, on every read, from the
 * axes plus the method's limits and the requirement's threshold.
 */
export function useTest(testId: string): LiveOnly<TestDetail> {
  const resolved = useCredentials();

  const query = useQuery({
    queryKey: [
      "testing-test",
      testId,
      resolved.ok ? resolved.credentials.organizationId : null,
      resolved.ok ? resolved.credentials.userId : null,
    ],
    enabled: resolved.ok && testId.length > 0,
    queryFn: ({ signal }) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return fetchTest(resolved.credentials, testId, signal);
    },
  });

  if (!resolved.ok) {
    return resolved.failed
      ? { data: undefined, isLoading: false, error: new Error(resolved.reason), unavailable: null }
      : { data: undefined, isLoading: false, error: null, unavailable: resolved.reason };
  }

  return {
    data: query.data,
    isLoading: query.isPending,
    error: (query.error as Error | null) ?? null,
    unavailable: null,
  };
}

/**
 * Every test action, behind one hook.
 *
 * 🔴 EVERY ONE REFETCHES RATHER THAN PATCHING LOCAL STATE, and here that is
 * not merely good hygiene — it is the rule. `calculated_result`,
 * `display_color` and `final_status` are DERIVED and server-owned, and there
 * is deliberately no endpoint that sets any of them. A screen that advanced
 * a colour optimistically would be deciding a traffic light in the browser
 * from an incomplete input, which is exactly what §10 forbids.
 *
 * Completing a test can open a failure investigation, so the dashboard
 * queries are invalidated too: a RED result that did not update the
 * investigation queue is a finding nobody is looking at.
 */
export function useTestActions(testId: string): {
  readonly start: () => void;
  readonly addReplicate: (request: ReplicateRequest) => void;
  readonly excludeOne: (replicateId: string, reason: string) => void;
  readonly complete: () => void;
  readonly decide: (request: DecisionRequest) => void;
  readonly confirm: () => void;
  readonly isPending: boolean;
  readonly error: Error | null;
  readonly lastAction: string | null;
  readonly reset: () => void;
  readonly unavailable: string | null;
} {
  const resolved = useCredentials();
  const queryClient = useQueryClient();

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["testing-test", testId] });
    void queryClient.invalidateQueries({ queryKey: ["testing-tests"] });
    // 🔴 THERE IS NO `["dashboards"]` QUERY, AND THERE WAS A LINE INVALIDATING
    // ONE. It matched nothing, under a comment claiming it kept the failure
    // queue current — correct-looking configuration over an inert mechanism,
    // which is exactly the state the comment said it was preventing. Removed
    // rather than left as reassurance. Found by the Supervisor.
    //
    // Completing a test CAN open a failure investigation (§10), so when a
    // dashboard or failure query exists it belongs here. `my-work` does exist
    // and a new investigation is work assigned to somebody.
    void queryClient.invalidateQueries({ queryKey: ["my-work"] });
  };

  const credentials = () => {
    if (!resolved.ok) {
      throw isApiConfigured
        ? new ApiNoSessionError(resolved.reason)
        : new ApiNotConfiguredError();
    }
    return resolved.credentials;
  };

  const mutation = useMutation({
    mutationFn: async (job: { readonly label: string; readonly run: () => Promise<unknown> }) => {
      await job.run();
      return job.label;
    },
    onSuccess: refresh,
  });

  const run = (label: string, make: () => Promise<unknown>) =>
    mutation.mutate({ label, run: make });

  return {
    start: () => run("start", () => startTest(credentials(), testId)),
    addReplicate: (request) =>
      run("replicate", () => recordReplicate(credentials(), testId, request)),
    excludeOne: (replicateId, reason) =>
      run("exclusion", () => excludeReplicate(credentials(), testId, replicateId, reason)),
    complete: () => run("complete", () => completeTest(credentials(), testId)),
    decide: (request) => run("decision", () => recordTestDecision(credentials(), testId, request)),
    confirm: () => run("confirm", () => confirmTest(credentials(), testId)),
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
    lastAction: mutation.data ?? null,
    reset: mutation.reset,
    unavailable: resolved.ok ? null : resolved.failed ? null : resolved.reason,
  };
}

// ---------------------------------------------------------------------------
// The formula workspace — composition, derived properties, and the lifecycle
// ---------------------------------------------------------------------------

/**
 * One version's composition.
 *
 * 🔴 THE COMPOSITION AND THE EVALUATION ARE TWO ENDPOINTS AND THEY STAY TWO
 * HOOKS. `/versions/{id}` returns the components; `/evaluation` runs the
 * engine over them and returns the derived properties plus the submission
 * blocks. Merging them would hide that a property can be UNAVAILABLE WITH A
 * STATED REASON while the composition reads perfectly — "density unknown for:
 * RM-FIL-07" is the most useful sentence on the screen, and it belongs to the
 * evaluation, not to the components.
 */
export function useFormulaVersion(versionId: string): LiveOnly<FormulaVersionDetail> {
  const resolved = useCredentials();

  const query = useQuery({
    queryKey: [
      "formulation-version",
      versionId,
      resolved.ok ? resolved.credentials.organizationId : null,
      resolved.ok ? resolved.credentials.userId : null,
    ],
    enabled: resolved.ok && versionId.length > 0,
    queryFn: ({ signal }) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return fetchVersion(resolved.credentials, versionId, signal);
    },
  });

  if (!resolved.ok) {
    return resolved.failed
      ? { data: undefined, isLoading: false, error: new Error(resolved.reason), unavailable: null }
      : { data: undefined, isLoading: false, error: null, unavailable: resolved.reason };
  }

  return {
    data: query.data,
    isLoading: query.isPending,
    error: (query.error as Error | null) ?? null,
    unavailable: null,
  };
}

/** The engine on that version: properties, submission blocks, submittability. */
export function useFormulaEvaluation(versionId: string): LiveOnly<VersionEvaluation> {
  const resolved = useCredentials();

  const query = useQuery({
    queryKey: [
      "formulation-evaluation",
      versionId,
      resolved.ok ? resolved.credentials.organizationId : null,
      resolved.ok ? resolved.credentials.userId : null,
    ],
    enabled: resolved.ok && versionId.length > 0,
    queryFn: ({ signal }) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return fetchVersionEvaluation(resolved.credentials, versionId, signal);
    },
  });

  if (!resolved.ok) {
    return resolved.failed
      ? { data: undefined, isLoading: false, error: new Error(resolved.reason), unavailable: null }
      : { data: undefined, isLoading: false, error: null, unavailable: resolved.reason };
  }

  return {
    data: query.data,
    isLoading: query.isPending,
    error: (query.error as Error | null) ?? null,
    unavailable: null,
  };
}

/**
 * The difference against another version.
 *
 * Disabled when there is no parent. That is the honest state of a FIRST
 * version rather than an error, and the screen says so rather than showing an
 * empty table that looks like "nothing changed".
 */
export function useFormulaComparison(
  versionId: string,
  againstVersionId: string | null,
): LiveOnly<VersionComparison> {
  const resolved = useCredentials();

  const query = useQuery({
    queryKey: [
      "formulation-comparison",
      versionId,
      againstVersionId,
      resolved.ok ? resolved.credentials.organizationId : null,
      resolved.ok ? resolved.credentials.userId : null,
    ],
    enabled: resolved.ok && versionId.length > 0 && (againstVersionId?.length ?? 0) > 0,
    queryFn: ({ signal }) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return fetchVersionComparison(
        resolved.credentials,
        versionId,
        againstVersionId as string,
        signal,
      );
    },
  });

  if (!resolved.ok) {
    return resolved.failed
      ? { data: undefined, isLoading: false, error: new Error(resolved.reason), unavailable: null }
      : { data: undefined, isLoading: false, error: null, unavailable: resolved.reason };
  }

  return {
    data: query.data,
    isLoading: query.isPending,
    error: (query.error as Error | null) ?? null,
    unavailable: null,
  };
}

/**
 * Every formulation action, behind one hook.
 *
 * The weigh-up sheet is deliberately NOT here: `POST /weigh-up` takes a batch
 * mass and returns a scaled sheet without writing anything, so it is a read
 * with a body rather than a mutation. It lives in the workspace as its own
 * request, and its result is held in component state.
 */
export function useFormulaActions(versionId: string): {
  readonly saveComponents: (components: readonly ComponentInput[]) => void;
  readonly submit: () => void;
  readonly decide: (request: VersionDecisionRequest) => void;
  readonly revise: (request: RevisionRequest) => void;
  readonly recordObserved: (observedEffect: string) => void;
  readonly isPending: boolean;
  readonly error: Error | null;
  readonly lastAction: string | null;
  readonly reset: () => void;
  readonly unavailable: string | null;
} {
  const resolved = useCredentials();
  const queryClient = useQueryClient();

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["formulation-version", versionId] });
    void queryClient.invalidateQueries({ queryKey: ["formulation-evaluation", versionId] });
    void queryClient.invalidateQueries({ queryKey: ["formulation-comparison"] });
    // The list carries `latest_version_code` and `version_count`, and a
    // revision changes both.
    void queryClient.invalidateQueries({ queryKey: ["formulations"] });
  };

  const credentials = () => {
    if (!resolved.ok) {
      throw isApiConfigured
        ? new ApiNoSessionError(resolved.reason)
        : new ApiNotConfiguredError();
    }
    return resolved.credentials;
  };

  const mutation = useMutation({
    mutationFn: async (job: { readonly label: string; readonly run: () => Promise<unknown> }) => {
      await job.run();
      return job.label;
    },
    onSuccess: refresh,
  });

  const run = (label: string, make: () => Promise<unknown>) =>
    mutation.mutate({ label, run: make });

  return {
    saveComponents: (components) =>
      run("components", () => putComponents(credentials(), versionId, components)),
    submit: () => run("submit", () => submitVersion(credentials(), versionId)),
    decide: (request) => run("decision", () => decideVersion(credentials(), versionId, request)),
    revise: (request) => run("revision", () => createRevision(credentials(), versionId, request)),
    recordObserved: (observedEffect) =>
      run("observed-effect", () => recordObservedEffect(credentials(), versionId, observedEffect)),
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
    lastAction: mutation.data ?? null,
    reset: mutation.reset,
    unavailable: resolved.ok ? null : resolved.failed ? null : resolved.reason,
  };
}

/**
 * The weigh-up sheet, on demand.
 *
 * 🔴 A POST THAT WRITES NOTHING, AND THAT IS THE API'S SHAPE RATHER THAN A
 * MISTAKE. `POST /weigh-up` takes a batch mass and returns a scaled sheet; it
 * is a POST because the mass is an INPUT, not because it mutates. So it is
 * neither a query (it has a body the user chooses) nor a mutation (nothing
 * changes), and it is exposed as an explicit `run` the screen calls.
 *
 * It lives here rather than in the page so that `useCredentials` stays private
 * to this module: a screen that reaches for credentials directly is one edit
 * away from building its own request and bypassing the parsing contract every
 * other call goes through.
 *
 * The server REFUSES a formula that does not total 100%, and its sentence is
 * the useful part — "scaling it silently would produce masses that contradict
 * the stated percentages". `serverMessage` is what surfaces it.
 */
export function useWeighUp(versionId: string): {
  readonly run: (batchMassKg: string) => void;
  readonly data: WeighUp | null;
  readonly isPending: boolean;
  readonly error: Error | null;
} {
  const resolved = useCredentials();

  const mutation = useMutation({
    mutationFn: (batchMassKg: string) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return fetchWeighUp(resolved.credentials, versionId, batchMassKg);
    },
  });

  return {
    run: (batchMassKg) => mutation.mutate(batchMassKg),
    data: mutation.data ?? null,
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
  };
}

// ---------------------------------------------------------------------------
// MSD — deliberately NOT wrapped in hooks here
// ---------------------------------------------------------------------------
//
// 🔴 `useMsdThreads` AND `useMsdTurns` LIVED HERE AND NOTHING CALLED THEM.
//
// `MsdPanel` hydrates its history inside an effect, because its unit is an
// EXCHANGE — a question folded together with its answer — and not a rendered
// query result. It therefore calls `fetchThreads` and `fetchTurns` directly.
// The two hooks written beside them were never reached by anything: dead code
// duplicating a live path, which is the same defect this whole commit exists
// to remove, one layer further down.
//
// Deleted rather than left "for later". A second way to load the same data is
// how two screens end up disagreeing about what a conversation contains.

// ---------------------------------------------------------------------------
// Creation — the routes that turn a screen from a viewer into a workspace
// ---------------------------------------------------------------------------
//
// 🔴 THESE EXIST BECAUSE A CLIENT FUNCTION IS NOT A CALLER.
//
// The first version of this work declared `createBatch`, `createTest`,
// `createFormula` and `classifyFormula` in the api-client files and stopped
// there — and then claimed all thirty-seven endpoints had a production
// caller. Codex checked the claim and found the four names appeared nowhere
// but at their own definitions.
//
// That is the very defect the work set out to fix, committed one layer up:
// an unreachable capability with a function standing where the caller should
// be. A route is reachable when a person can press something.

/** The methods a test can be planned against. */
export function useTestMethods(): LiveOnly<TestMethod[]> {
  const resolved = useCredentials();

  const query = useQuery({
    queryKey: [
      "testing-methods",
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
      return fetchTestMethods(resolved.credentials, signal);
    },
  });

  if (!resolved.ok) {
    return resolved.failed
      ? { data: undefined, isLoading: false, error: new Error(resolved.reason), unavailable: null }
      : { data: undefined, isLoading: false, error: null, unavailable: resolved.reason };
  }

  return {
    data: query.data,
    isLoading: query.isPending,
    error: (query.error as Error | null) ?? null,
    unavailable: null,
  };
}

/** The classification ladder, in rank order. */
export function useClassifications(): LiveOnly<Classification[]> {
  const resolved = useCredentials();

  const query = useQuery({
    queryKey: [
      "formulation-classifications",
      resolved.ok ? resolved.credentials.organizationId : null,
    ],
    enabled: resolved.ok,
    queryFn: ({ signal }) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return fetchClassifications(resolved.credentials, signal);
    },
  });

  if (!resolved.ok) {
    return resolved.failed
      ? { data: undefined, isLoading: false, error: new Error(resolved.reason), unavailable: null }
      : { data: undefined, isLoading: false, error: null, unavailable: resolved.reason };
  }

  return {
    data: query.data,
    isLoading: query.isPending,
    error: (query.error as Error | null) ?? null,
    unavailable: null,
  };
}

/**
 * Plan a test against a sample.
 *
 * Returns the created id so the caller can navigate to the workspace. The
 * 201 carries three columns, not a test — see `createTest`.
 */
export function usePlanTest(): {
  readonly plan: (request: TestCreateRequest) => void;
  readonly created: TestCreated | null;
  readonly isPending: boolean;
  readonly error: Error | null;
} {
  const resolved = useCredentials();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (request: TestCreateRequest) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return createTest(resolved.credentials, request);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["testing-tests"] });
    },
  });

  return {
    plan: (request) => mutation.mutate(request),
    created: mutation.data ?? null,
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
  };
}

/**
 * Create a lab batch against a formula VERSION.
 *
 * 🔴 OFFERED FROM THE FORMULA WORKSPACE, NOT FROM THE BATCH QUEUE, AND THAT
 * IS THE DIGITAL THREAD RATHER THAN A LAYOUT PREFERENCE. §2: a batch exists
 * against a formula version, and the version id is the one thing the queue
 * does not have. Putting the control where the version already is means the
 * link is never typed by hand.
 */
export function useCreateBatch(): {
  readonly create: (request: BatchCreateRequest) => void;
  readonly created: { id: string } | null;
  readonly isPending: boolean;
  readonly error: Error | null;
} {
  const resolved = useCredentials();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (request: BatchCreateRequest) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return createBatch(resolved.credentials, request);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["laboratory-batches"] });
    },
  });

  return {
    create: (request) => mutation.mutate(request),
    created: mutation.data ?? null,
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
  };
}

/** Create a formula inside a project. */
export function useCreateFormula(): {
  readonly create: (request: FormulaCreateRequest) => void;
  readonly created: { id: string } | null;
  readonly isPending: boolean;
  readonly error: Error | null;
} {
  const resolved = useCredentials();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (request: FormulaCreateRequest) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return createFormula(resolved.credentials, request);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["formulations"] });
    },
  });

  return {
    create: (request) => mutation.mutate(request),
    created: mutation.data ?? null,
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
  };
}

/**
 * Reclassify a formula.
 *
 * The reason is mandatory server-side and audited: a confidentiality level
 * that changed with no recorded justification cannot be reviewed later.
 */
export function useClassifyFormula(formulaId: string): {
  readonly classify: (request: ClassificationRequest) => void;
  readonly isPending: boolean;
  readonly error: Error | null;
  readonly done: boolean;
} {
  const resolved = useCredentials();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (request: ClassificationRequest) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return classifyFormula(resolved.credentials, formulaId, request);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["formulations"] });
      void queryClient.invalidateQueries({ queryKey: ["formulation-version"] });
    },
  });

  return {
    classify: (request) => mutation.mutate(request),
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
    done: mutation.isSuccess,
  };
}

// ---------------------------------------------------------------------------
// Intelligence — analytics and the test-results report
// ---------------------------------------------------------------------------
//
// 🔴 LIVE OR NOTHING, AND THERE IS NO DEMONSTRATION FIXTURE.
//
// `useSourcedList` exists because some screens have a bundled demonstration
// dataset for a build with no API. These two must not: every figure they show
// is a COUNT OF TEST OUTCOMES, and a fabricated one is materially worse than a
// fabricated supplier row. "Nine tests GREEN" invented by the frontend is a
// safety claim about physical measurements that were never made — §3 keeps
// Calculated, Predicted and Measured visually distinct precisely so this
// cannot happen, and the 08-19 incident (a failed `/api/me` became
// demonstration data) is what the rule is made of.
//
// So both are `LiveOnly`: real numbers, or a page that says why it has none.

/** Testing and laboratory activity, counted. Live or nothing. */
export function useAnalytics<TShown>(
  project: (live: Analytics) => TShown,
): LiveOnly<TShown> {
  return useLiveOnlyList("analysis-analytics", project, fetchAnalytics);
}

/** Tests grouped by their server-derived disposition. Live or nothing. */
export function useTestResultsReport<TShown>(
  project: (live: TestResultsReport) => TShown,
): LiveOnly<TShown> {
  return useLiveOnlyList("analysis-report", project, fetchTestResultsReport);
}

// ---------------------------------------------------------------------------
// Slice 6 — failure investigations and the approval queue
//
// 🔴 ELEVEN WRITE ENDPOINTS SHIPPED WITHOUT ONE OF THESE.
//
// Measured 2026-08-27: every route in `app/api/failures.py` existed, was
// permission-gated and was tested, and not one had a browser caller. So a RED
// confirmation result opened an investigation — §10 does that automatically —
// that no person could then work. The digital thread's most consequential
// link, written by the system and workable by nobody.
// ---------------------------------------------------------------------------

/** The investigation queue. */
export function useFailures<TShown = FailureSummary[]>(
  project: (live: FailureSummary[]) => TShown = (live) => live as unknown as TShown,
): LiveOnly<TShown> {
  return useLiveOnlyList("quality-failures", project, fetchFailures);
}

/** One investigation, with its hypotheses, evidence and actions. */
export function useFailure(failureId: string): LiveOnly<FailureDetail> {
  const resolved = useCredentials();

  const query = useQuery({
    queryKey: [
      "quality-failure",
      failureId,
      resolved.ok ? resolved.credentials.organizationId : null,
      resolved.ok ? resolved.credentials.userId : null,
    ],
    enabled: resolved.ok && failureId.length > 0,
    queryFn: ({ signal }) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return fetchFailure(resolved.credentials, failureId, signal);
    },
  });

  if (!resolved.ok) {
    return resolved.failed
      ? { data: undefined, isLoading: false, error: new Error(resolved.reason), unavailable: null }
      : { data: undefined, isLoading: false, error: null, unavailable: resolved.reason };
  }

  return {
    data: query.data,
    isLoading: query.isPending,
    error: (query.error as Error | null) ?? null,
    unavailable: null,
  };
}

/**
 * The seven writes an investigation supports.
 *
 * One bundled hook rather than seven, matching `useTestActions` and
 * `useBatchActions`: the screen needs a single `isPending` and a single
 * `error`, because two mutations in flight against one record is a state no
 * workspace here wants to render.
 */
export function useFailureActions(failureId: string): {
  readonly propose: (request: HypothesisRequest, after?: () => void) => void;
  readonly addEvidence: (request: EvidenceRequest, after?: () => void) => void;
  readonly link: (
    hypothesisId: string,
    request: EvidenceLinkRequest,
    after?: () => void,
  ) => void;
  readonly accept: (hypothesisId: string, rationale: string, after?: () => void) => void;
  readonly reject: (hypothesisId: string, reason: string, after?: () => void) => void;
  readonly raiseAction: (request: ActionRequest, after?: () => void) => void;
  readonly close: (summary: string) => void;
  readonly isPending: boolean;
  readonly error: Error | null;
  readonly lastAction: string | null;
  readonly reset: () => void;
  readonly unavailable: string | null;
} {
  const resolved = useCredentials();
  const queryClient = useQueryClient();

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["quality-failure", failureId] });
    void queryClient.invalidateQueries({ queryKey: ["quality-failures"] });
    // A corrective action is work assigned to somebody, so My Work and its
    // badge are both stale after `raiseAction`. Listed because that query
    // EXISTS — this project has shipped an invalidation that matched nothing,
    // under a comment claiming it kept a queue current.
    void queryClient.invalidateQueries({ queryKey: ["my-work"] });
  };

  const credentials = () => {
    if (!resolved.ok) {
      throw isApiConfigured
        ? new ApiNoSessionError(resolved.reason)
        : new ApiNotConfiguredError();
    }
    return resolved.credentials;
  };

  // 🔴 `after` RUNS ONLY ON SUCCESS, AND THAT IS WHY IT EXISTS.
  //
  // Raised by the Supervisor. `mutate` is fire-and-forget, so the screen was
  // clearing its inputs on the line AFTER the call — before anything was known.
  // A lead who wrote a long acceptance rationale and hit a 403 from segregation
  // of duties, or a 409 from `failure_hypotheses_one_accepted_idx`, got the
  // error banner and an empty field, with the text nowhere to recover from.
  //
  // Clearing belongs to the outcome, not to the click.
  const mutation = useMutation({
    mutationFn: async (job: {
      readonly label: string;
      readonly run: () => Promise<unknown>;
      readonly after?: () => void;
    }) => {
      await job.run();
      return job.label;
    },
    onSuccess: (_label, job) => {
      refresh();
      job.after?.();
    },
  });

  const run = (label: string, make: () => Promise<unknown>, after?: () => void) =>
    mutation.mutate({ label, run: make, after });

  return {
    propose: (request, after) =>
      run("hypothesis", () => proposeHypothesis(credentials(), failureId, request), after),
    addEvidence: (request, after) =>
      run("evidence", () => recordEvidence(credentials(), failureId, request), after),
    link: (hypothesisId, request, after) =>
      run(
        "evidence link",
        () => linkEvidence(credentials(), failureId, hypothesisId, request),
        after,
      ),
    accept: (hypothesisId, rationale, after) =>
      run(
        "root cause",
        () =>
          acceptRootCause(credentials(), failureId, {
            hypothesis_id: hypothesisId,
            rationale,
          }),
        after,
      ),
    reject: (hypothesisId, reason, after) =>
      run(
        "rejection",
        () => rejectHypothesis(credentials(), failureId, hypothesisId, reason),
        after,
      ),
    raiseAction: (request, after) =>
      run("action", () => raiseAction(credentials(), failureId, request), after),
    close: (summary) => run("closure", () => closeFailure(credentials(), failureId, summary)),
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
    lastAction: mutation.data ?? null,
    reset: mutation.reset,
    unavailable: resolved.ok ? null : resolved.failed ? null : resolved.reason,
  };
}

/**
 * The approval queue: steps this caller could decide RIGHT NOW.
 *
 * 🔴 THE SERVER OWNS "RIGHT NOW" AND THE SCREEN MUST NOT SECOND-GUESS IT.
 * `pending_steps_for` excludes steps whose turn has not come — including,
 * since Codex's finding on that query, groups still blocked by an earlier step
 * that was returned for correction rather than approved. Filtering this
 * further in the browser would hide work; widening it would offer a rung the
 * engine will refuse.
 */
export function useApprovalQueue<TShown = ApprovalQueueItem[]>(
  project: (live: ApprovalQueueItem[]) => TShown = (live) => live as unknown as TShown,
): LiveOnly<TShown> {
  return useLiveOnlyList("approval-queue", project, fetchApprovalQueue);
}

/** One route and its ladder. */
export function useApprovalRoute(routeId: string): LiveOnly<ApprovalRoute> {
  const resolved = useCredentials();

  const query = useQuery({
    queryKey: [
      "approval-route",
      routeId,
      resolved.ok ? resolved.credentials.organizationId : null,
      resolved.ok ? resolved.credentials.userId : null,
    ],
    enabled: resolved.ok && routeId.length > 0,
    queryFn: ({ signal }) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return fetchApprovalRoute(resolved.credentials, routeId, signal);
    },
  });

  if (!resolved.ok) {
    return resolved.failed
      ? { data: undefined, isLoading: false, error: new Error(resolved.reason), unavailable: null }
      : { data: undefined, isLoading: false, error: null, unavailable: resolved.reason };
  }

  return {
    data: query.data,
    isLoading: query.isPending,
    error: (query.error as Error | null) ?? null,
    unavailable: null,
  };
}

/** Record a decision on one rung of one route. */
export function useApprovalDecision(): {
  readonly decide: (routeId: string, stepId: string, request: StepDecisionRequest) => void;
  readonly isPending: boolean;
  readonly error: Error | null;
  readonly lastAction: string | null;
  readonly reset: () => void;
  readonly unavailable: string | null;
} {
  const resolved = useCredentials();
  const queryClient = useQueryClient();

  const credentials = () => {
    if (!resolved.ok) {
      throw isApiConfigured
        ? new ApiNoSessionError(resolved.reason)
        : new ApiNotConfiguredError();
    }
    return resolved.credentials;
  };

  const mutation = useMutation({
    mutationFn: async (job: {
      readonly routeId: string;
      readonly stepId: string;
      readonly request: StepDecisionRequest;
    }) => {
      await decideStep(credentials(), job.routeId, job.stepId, job.request);
      return job.request.decision;
    },
    onSuccess: (_data, job) => {
      void queryClient.invalidateQueries({ queryKey: ["approval-queue"] });
      void queryClient.invalidateQueries({ queryKey: ["approval-route", job.routeId] });
      // A decision can settle a route, and a settled route changes a test's
      // disposition — §10 rule 12 is literally "YELLOW — AWAITING <next
      // approver>". Both test queries exist, so both are invalidated.
      void queryClient.invalidateQueries({ queryKey: ["testing-tests"] });
      void queryClient.invalidateQueries({ queryKey: ["testing-test"] });
    },
  });

  return {
    decide: (routeId, stepId, request) => mutation.mutate({ routeId, stepId, request }),
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
    lastAction: mutation.data ?? null,
    reset: mutation.reset,
    unavailable: resolved.ok ? null : resolved.failed ? null : resolved.reason,
  };
}

/**
 * Open an investigation by hand.
 *
 * Its own hook rather than a member of `useFailureActions`, because that one is
 * keyed by `failureId` and this is the call that CREATES one — there is no id
 * to key it by yet.
 */
export function useOpenInvestigation(): {
  readonly submit: (request: FailureCreateRequest, after?: () => void) => void;
  readonly isPending: boolean;
  readonly error: Error | null;
  /** True once one has been opened, so the screen can say so. */
  readonly opened: boolean;
  readonly unavailable: string | null;
} {
  const resolved = useCredentials();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async (job: {
      readonly request: FailureCreateRequest;
      readonly after?: () => void;
    }) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return openInvestigation(resolved.credentials, job.request);
    },
    onSuccess: (_data, job) => {
      void queryClient.invalidateQueries({ queryKey: ["quality-failures"] });
      // 🔴 THE FORM IS RESET ON SUCCESS, AND ONLY ON SUCCESS. Raised by the
      // Supervisor: nothing acknowledged a create and nothing cleared the
      // failure code, so a user who saw no confirmation pressed Open again and
      // hit `failures_org_code_key` — a refusal that reads as though the FIRST
      // attempt had failed too.
      job.after?.();
    },
  });

  return {
    submit: (request, after) => mutation.mutate({ request, after }),
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
    opened: mutation.isSuccess,
    unavailable: resolved.ok ? null : resolved.failed ? null : resolved.reason,
  };
}
