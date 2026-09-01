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

import {
  createProductFamily,
  createStage,
  createUnit,
  decideAccessRequest,
  fetchAccessRequests,
  fetchAdminMembers,
  fetchPermissions,
  fetchProductFamilies,
  fetchRoles,
  fetchStageDefinitions,
  fetchUnits,
  grantRole,
  inviteMember,
  reorderStages,
  revokeRole,
  setMemberStatus,
  setReferenceItemActive,
  setStageActive,
  updateStage,
  type AccessRequest,
  type AccessRequestDecisionRequest,
  type AdminMember,
  type MemberInviteRequest,
  type Permission,
  type ProductFamily,
  type Role,
  type StageDefinition,
  type StageWriteRequest,
  type Unit,
} from "./admin";
import {
  addProjectMember,
  advanceStage,
  approveRequirement,
  createMilestone,
  createRequirement,
  createRisk,
  fetchMilestones,
  fetchPipeline,
  fetchProject,
  fetchProjectMembers,
  fetchRequirementMatrix,
  fetchRisks,
  removeProjectMember,
  reviseRequirement,
  setMilestoneStatus,
  updateRisk,
  type Milestone,
  type MilestoneRequest,
  type PipelineStage,
  type ProjectMember,
  type RequirementMatrix,
  type RequirementRequest,
  type Risk,
  type RiskRequest,
} from "./projects";
import {
  convertOpportunity,
  createOpportunity,
  decideOpportunity,
  fetchOpportunities,
  submitOpportunity,
  type Opportunity,
  type OpportunityConversionRequest,
  type OpportunityCreateRequest,
  type OpportunityDecisionRequest,
} from "./opportunities";
import { useState } from "react";

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
  relabelEvidence,
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
  fetchChannels,
  fetchMessages,
  fetchNotifications,
  markNotificationRead,
  postMessage,
  promoteMessage,
  type Channel,
  type Message,
  type Notification,
  type PostedMessage,
  type PostMessageRequest,
  type PromoteRequest,
} from "./messaging";
import { searchRecords, type SearchResults } from "./search";
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
  setComposition,
  type ComponentLineRequest,
} from "./formulations";
import {
  fetchMaterials,
  type Material,
  changeMaterialStatus,
  createMaterial,
  fetchMaterial,
  fetchSuppliers,
  linkSupplier,
  updateMaterial,
  type MaterialCreateRequest,
  type MaterialDetail,
  type MaterialEditRequest,
  type MaterialStatusRequest,
  type Supplier,
  type SupplierLinkRequest,
} from "./materials";
import {
  fetchAnalytics,
  fetchTestResultsReport,
  type Analytics,
  type TestResultsReport,
} from "./analysis";
import {
  acknowledgeAlert,
  createInterpretation,
  fetchComparableRevisions,
  fetchInterpretableDocuments,
  fetchMaterialInterpretations,
  fetchPendingInterpretations,
  openSafetyReview,
  raiseAlerts,
  fetchSafetyAlerts,
  fetchSafetyPosition,
  reviewInterpretation,
  type ComparableRevision,
  type InterpretableDocument,
  type InterpretationRequest,
  type MaterialInterpretation,
  type PendingInterpretation,
  type SafetyAlert,
  type SafetyPosition,
} from "./material-safety";
import {
  useAuth,
  type OrganizationChoice,
} from "@/components/providers/auth-provider";
import {
  fetchCompetitorBenchmarks,
  fetchCompetitorDocuments,
  fetchCompetitorProducts,
  fetchCompetitorSamples,
  fetchCompositionMatrix,
  gradeCompetitorEvidence,
  recordCompetitorBenchmark,
  recordCompetitorEvidence,
  registerCompetitorProduct,
  registerCompetitorSample,
  uploadCompetitorDocument,
  type BenchmarkRequest,
  type CompetitorBenchmark,
  type CompetitorDocument,
  type CompetitorProduct,
  type CompetitorSample,
  type CompositionMatrix,
  type EvidenceRequest as CompetitorEvidenceRequest,
  type ProductRequest,
  // Aliased: laboratory.ts already exports a SampleRequest, and that one is a
  // BATCH sample of our own. Two different things with one name in one file.
  type SampleRequest as CompetitorSampleRequest,
} from "./competitors";
import {
  acceptProposal,
  closeInvestigation,
  decideHypothesis as decideResearchHypothesis,
  fetchEvidenceCards,
  fetchFindings,
  fetchHypotheses,
  fetchInvestigations,
  fetchKnowledgeGaps,
  fetchProposals,
  fetchResearchQuestions,
  fetchResearchSources,
  openInvestigation as openResearchWorkspace,
  promoteFinding,
  proposeExperiment,
  recordEvidenceCard,
  recordFinding,
  recordHypothesis as recordResearchHypothesis,
  recordKnowledgeGap,
  recordResearchQuestion,
  recordResearchSource,
  rejectProposal,
  resolveKnowledgeGap,
  settleResearchQuestion,
  submitFinding,
  type AcceptProposalRequest,
  type EvidenceCard,
  type EvidenceRequest as ResearchEvidenceRequest,
  type ExperimentProposal,
  type Finding as ResearchFinding,
  type Hypothesis,
  type HypothesisRequest as ResearchHypothesisRequest,
  type FindingRequest,
  type GapRequest,
  type Investigation as ResearchInvestigation,
  type InvestigationRequest,
  type KnowledgeGap,
  type ProposalRequest,
  type ResearchQuestion,
  type ResearchSource,
  type SourceRequest as ResearchSourceRequest,
} from "./research";
import {
  dashboardForRoles,
  fetchRoleDashboard,
  type DashboardRole,
  type RoleDashboard,
} from "./dashboards";
import {
  createProject,
  fetchProjects,
  type Project,
  type ProjectCreateRequest,
} from "./projects";
import { useSession } from "./session";
import {
  claimTask,
  completeTask,
  createTask,
  fetchMyWork,
  type Task,
  type TaskCreateRequest,
} from "./tasks";
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

/**
 * One live record, by id — the shape `useTest`, `useFailure` and four project
 * hooks all needed.
 *
 * 🔴 EXTRACTED RATHER THAN COPIED A SIXTH TIME. `useTest`, `useBatch`,
 * `useFailure` and `useApprovalRoute` are the same twenty-five lines with a
 * different key and fetcher: the query key carries the id AND the caller's
 * organization and user (so a cached response cannot cross either), `enabled`
 * waits for both a session and a non-empty id, and the not-ok branch tells a
 * FAILED `/api/me` apart from an absent one — an outage must not render as a
 * tidy "not available on this build" notice.
 *
 * Adding the project workspace would have made six copies of that, and the
 * fourth thing to drift would have been the organization in the key. Written
 * once here; the older four are left alone deliberately rather than rewritten
 * in a slice that is about something else.
 */
function useLiveOnlyRecord<T>(
  key: string,
  id: string,
  fetcher: (credentials: ApiCredentials, signal?: AbortSignal) => Promise<T>,
): LiveOnly<T> {
  const resolved = useCredentials();

  const query = useQuery({
    queryKey: [
      key,
      id,
      resolved.ok ? resolved.credentials.organizationId : null,
      resolved.ok ? resolved.credentials.userId : null,
    ],
    enabled: resolved.ok && id.length > 0,
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
 * Global search across every record type the caller may reach — spec §29.
 *
 * `enabled` matters here for the same reason it does in `useKnowledgeSearch`
 * above, and for one more: this query fans out across fifteen tables, so
 * firing it for the empty string on every mount of the app shell would be a
 * per-navigation cost paid for an answer nobody asked for.
 *
 * ⚠️ THE CALLER MUST RENDER `searched`, NOT JUST `results`. A record type the
 * caller lacks the permission for returns no hits, and an empty section is a
 * claim that none exist. `lib/api/search.ts` says why at more length.
 */
export function useGlobalSearch(
  query: string,
  types?: readonly string[],
): LiveOnly<SearchResults> {
  const resolved = useCredentials();
  const trimmed = query.trim();
  const typeKey = types ? [...types].sort().join(",") : "";

  const result = useQuery({
    queryKey: [
      "global-search",
      trimmed,
      typeKey,
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
      return searchRecords(resolved.credentials, trimmed, types, signal);
    },
  });

  if (!resolved.ok) {
    return resolved.failed
      ? { data: undefined, isLoading: false, error: new Error(resolved.reason), unavailable: null }
      : { data: undefined, isLoading: false, error: null, unavailable: resolved.reason };
  }

  return {
    data: trimmed.length === 0 ? undefined : result.data,
    isLoading: trimmed.length > 0 && result.isPending,
    error: (result.error as Error | null) ?? null,
    unavailable: null,
  };
}

/**
 * Channels this caller can see — I12.
 *
 * 🔴 THE FIRST CALLER THESE EIGHT ENDPOINTS HAVE EVER HAD.
 */
export function useChannels(): LiveOnly<Channel[]> {
  return useLiveOnlyList("messaging-channels", (live: Channel[]) => live, fetchChannels);
}

/**
 * One channel's messages, fetched only when a channel is selected.
 *
 * `enabled` for the same reason the search hooks have it: with no channel
 * chosen there is nothing to ask for, and firing anyway would render "no
 * messages" for a channel nobody opened.
 */
export function useChannelMessages(channelId: string | null): LiveOnly<Message[]> {
  const resolved = useCredentials();

  const result = useQuery({
    queryKey: [
      "messaging-messages",
      channelId,
      resolved.ok ? resolved.credentials.organizationId : null,
      resolved.ok ? resolved.credentials.userId : null,
    ],
    enabled: resolved.ok && channelId !== null,
    queryFn: ({ signal }) => {
      if (!resolved.ok) {
        throw isApiConfigured ? new ApiNoSessionError(resolved.reason) : new ApiNotConfiguredError();
      }
      return fetchMessages(resolved.credentials, channelId!, signal);
    },
  });

  if (!resolved.ok) {
    return resolved.failed
      ? { data: undefined, isLoading: false, error: new Error(resolved.reason), unavailable: null }
      : { data: undefined, isLoading: false, error: null, unavailable: resolved.reason };
  }
  return {
    data: channelId === null ? undefined : result.data,
    isLoading: channelId !== null && result.isPending,
    error: (result.error as Error | null) ?? null,
    unavailable: null,
  };
}

/**
 * This caller's notifications.
 *
 * ⚠️ `unreadOnly` is a PARAMETER rather than a client-side filter, because the
 * server caps the page: filtering after the fact would silently drop unread
 * items past the cap, which is the I78 defect in a different table.
 */
export function useNotifications(unreadOnly: boolean): LiveOnly<Notification[]> {
  const resolved = useCredentials();

  const result = useQuery({
    queryKey: [
      "messaging-notifications",
      unreadOnly,
      resolved.ok ? resolved.credentials.organizationId : null,
      resolved.ok ? resolved.credentials.userId : null,
    ],
    enabled: resolved.ok,
    queryFn: ({ signal }) => {
      if (!resolved.ok) {
        throw isApiConfigured ? new ApiNoSessionError(resolved.reason) : new ApiNotConfiguredError();
      }
      return fetchNotifications(resolved.credentials, unreadOnly, signal);
    },
  });

  if (!resolved.ok) {
    return resolved.failed
      ? { data: undefined, isLoading: false, error: new Error(resolved.reason), unavailable: null }
      : { data: undefined, isLoading: false, error: null, unavailable: resolved.reason };
  }
  return {
    data: result.data,
    isLoading: result.isPending,
    error: (result.error as Error | null) ?? null,
    unavailable: null,
  };
}

/**
 * The write paths: post a message, promote one, mark a notification read.
 *
 * 🔴 EVERY ONE OF THESE HAD A ROUTE AND NO CONTROL. Grouped in one hook so a
 * screen cannot pick up the read paths and quietly leave the writes
 * unreachable — which is the state this module was already in.
 *
 * `lastPosted` is kept so the screen can show what the server RESOLVED out of
 * the body: which `#references` matched, and which `@mentions` were actually
 * notified. An author who cannot see that a mention failed believes it landed.
 */
export function useMessagingWrites(channelId: string | null): {
  readonly post: (body: string, onDone?: () => void) => void;
  readonly promote: (messageId: string, request: PromoteRequest, onDone?: () => void) => void;
  readonly markRead: (notificationId: string) => void;
  readonly isPending: boolean;
  readonly error: Error | null;
  readonly lastPosted: PostedMessage | undefined;
  readonly lastAction: string | null;
  readonly unavailable: string | null;
} {
  const resolved = useCredentials();
  const queryClient = useQueryClient();
  const [lastAction, setLastAction] = useState<string | null>(null);

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["messaging-messages"] });
    void queryClient.invalidateQueries({ queryKey: ["messaging-channels"] });
    void queryClient.invalidateQueries({ queryKey: ["messaging-notifications"] });
  };

  const postMutation = useMutation({
    mutationFn: (request: PostMessageRequest) => {
      if (!resolved.ok || channelId === null) {
        throw isApiConfigured ? new ApiNoSessionError("no channel") : new ApiNotConfiguredError();
      }
      return postMessage(resolved.credentials, channelId, request);
    },
    onSuccess: () => {
      setLastAction("Message posted.");
      invalidate();
    },
  });

  const promoteMutation = useMutation({
    mutationFn: ({ messageId, request }: { messageId: string; request: PromoteRequest }) => {
      if (!resolved.ok) {
        throw isApiConfigured ? new ApiNoSessionError(resolved.reason) : new ApiNotConfiguredError();
      }
      return promoteMessage(resolved.credentials, messageId, request);
    },
    onSuccess: () => {
      // Tasks live in My Work, so that list is stale the moment this returns.
      setLastAction("Message promoted to a task.");
      void queryClient.invalidateQueries({ queryKey: ["my-work"] });
      invalidate();
    },
  });

  const readMutation = useMutation({
    mutationFn: (notificationId: string) => {
      if (!resolved.ok) {
        throw isApiConfigured ? new ApiNoSessionError(resolved.reason) : new ApiNotConfiguredError();
      }
      return markNotificationRead(resolved.credentials, notificationId);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["messaging-notifications"] });
    },
  });

  return {
    post: (body, onDone) =>
      postMutation.mutate({ body }, { onSuccess: () => onDone?.() }),
    promote: (messageId, request, onDone) =>
      promoteMutation.mutate({ messageId, request }, { onSuccess: () => onDone?.() }),
    markRead: (notificationId) => readMutation.mutate(notificationId),
    isPending: postMutation.isPending || promoteMutation.isPending || readMutation.isPending,
    error:
      ((postMutation.error ?? promoteMutation.error ?? readMutation.error) as Error | null) ?? null,
    lastPosted: postMutation.data,
    lastAction,
    unavailable: resolved.ok || resolved.failed ? null : resolved.reason,
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

/**
 * Create a raw material.
 *
 * 🔴 IT INVALIDATES THE MATERIAL LIST AND NOTHING ELSE.
 *
 * A new material is not yet in any formula, so no composition, batch or test
 * answer changes. Invalidating more would refetch six screens to show the same
 * data — and invalidating less would leave the list the person is standing in
 * front of stale, which is how "it did not save" gets reported for a write
 * that worked.
 */
export function useCreateMaterial(): {
  readonly create: (request: MaterialCreateRequest, after?: () => void) => void;
  readonly created: { material_code: string } | null;
  readonly isPending: boolean;
  readonly error: Error | null;
} {
  const resolved = useCredentials();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (job: { request: MaterialCreateRequest; after?: () => void }) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return createMaterial(resolved.credentials, job.request);
    },
    onSuccess: (_data, job) => {
      void queryClient.invalidateQueries({ queryKey: ["materials"] });
      job.after?.();
    },
  });

  return {
    create: (request, after) => mutation.mutate({ request, after }),
    created: mutation.data ?? null,
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
  };
}

/**
 * Create a project — the second link in §2's thread.
 *
 * ⚠️ IT INVALIDATES THE PROJECT LIST *AND* THE PIPELINE. A new project appears
 * in the stage pipeline immediately, and a pipeline that still shows the old
 * set after a create is the same staleness defect one screen along.
 */
export function useCreateProject(): {
  readonly create: (request: ProjectCreateRequest, after?: () => void) => void;
  readonly created: { project_code: string } | null;
  readonly isPending: boolean;
  readonly error: Error | null;
} {
  const resolved = useCredentials();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (job: { request: ProjectCreateRequest; after?: () => void }) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return createProject(resolved.credentials, job.request);
    },
    onSuccess: (_data, job) => {
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      void queryClient.invalidateQueries({ queryKey: ["project-pipeline"] });
      job.after?.();
    },
  });

  return {
    create: (request, after) => mutation.mutate({ request, after }),
    created: mutation.data ?? null,
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
  };
}

/** Raise a task. Invalidates My Work, which is where it will appear. */
/**
 * The second half of a task's life: claim it, finish it, or hand it on.
 *
 * 🔴 ALL THREE ROUTES HAD NO CLIENT AND NO CONTROL. A task could be raised and
 * then never picked up, completed or reassigned through the browser. The
 * queue on `/my-work` showed role-addressed work nobody could take.
 *
 * ⚠️ NEITHER CARRIES A PERMISSION, AND THAT IS THE ROUTE'S OWN DESIGN: what you
 * may claim is already bounded by what the queue shows you, and `my_work`
 * filters that by your roles. `reassign` IS gated (`project.edit`) and is not
 * here -- moving somebody else's work needs a people picker, and the client
 * ships with the control rather than before it. See `lib/api/tasks.ts`.
 */
export function useTaskWrites(): {
  readonly claim: (taskId: string, after?: () => void) => void;
  readonly complete: (taskId: string, outcomeNote?: string, after?: () => void) => void;
  readonly isPending: boolean;
  readonly error: Error | null;
  readonly lastAction: string | null;
} {
  const resolved = useCredentials();
  const queryClient = useQueryClient();

  const credentials = () => {
    if (!resolved.ok) {
      throw isApiConfigured ? new ApiNoSessionError(resolved.reason) : new ApiNotConfiguredError();
    }
    return resolved.credentials;
  };

  const mutation = useMutation({
    mutationFn: async (
      job:
        | { kind: "claim"; taskId: string; after?: () => void }
        | { kind: "complete"; taskId: string; outcomeNote?: string; after?: () => void },
    ) => {
      if (job.kind === "claim") {
        await claimTask(credentials(), job.taskId);
        return "Task claimed. It is yours now.";
      }
      await completeTask(credentials(), job.taskId, job.outcomeNote);
      return "Task completed.";
    },
    onSuccess: (_data, job) => {
      // The queue is the only cached view of these rows. `GET /tasks/counts`
      // has no client yet, so there is no second key to invalidate -- and
      // naming a key nothing registers would have been an invalidation that
      // silently does nothing, which is the same defect as a gate on a path
      // no caller takes.
      void queryClient.invalidateQueries({ queryKey: ["my-work"] });
      job.after?.();
    },
  });

  return {
    claim: (taskId, after) => mutation.mutate({ kind: "claim", taskId, after }),
    complete: (taskId, outcomeNote, after) =>
      mutation.mutate({ kind: "complete", taskId, outcomeNote, after }),
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
    lastAction: mutation.data ?? null,
  };
}

export function useCreateTask(): {
  readonly create: (request: TaskCreateRequest, after?: () => void) => void;
  readonly isPending: boolean;
  readonly error: Error | null;
  readonly created: { id: string } | null;
} {
  const resolved = useCredentials();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (job: { request: TaskCreateRequest; after?: () => void }) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return createTask(resolved.credentials, job.request);
    },
    onSuccess: (_data, job) => {
      void queryClient.invalidateQueries({ queryKey: ["my-work"] });
      job.after?.();
    },
  });

  return {
    create: (request, after) => mutation.mutate({ request, after }),
    created: mutation.data ?? null,
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
  };
}

/**
 * Plan a test against a sample.
 *
 * ⚠️ IT INVALIDATES THE TEST LIST AND THE BATCH THE SAMPLE CAME FROM. A batch
 * carries a `test_count`, so a new test changes what the laboratory queue says
 * about that batch — leaving it stale is the same defect as leaving the list
 * stale, one screen along and harder to notice.
 */
export function useCreateTest(): {
  readonly create: (request: TestCreateRequest, after?: () => void) => void;
  readonly created: { test_number: string } | null;
  readonly isPending: boolean;
  readonly error: Error | null;
} {
  const resolved = useCredentials();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (job: { request: TestCreateRequest; after?: () => void }) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return createTest(resolved.credentials, job.request);
    },
    onSuccess: (_data, job) => {
      void queryClient.invalidateQueries({ queryKey: ["testing-tests"] });
      void queryClient.invalidateQueries({ queryKey: ["laboratory-batches"] });
      void queryClient.invalidateQueries({ queryKey: ["batch"] });
      job.after?.();
    },
  });

  return {
    create: (request, after) => mutation.mutate({ request, after }),
    created: mutation.data ?? null,
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
  };
}

/**
 * Write a draft version's composition.
 *
 * 🔴 IT INVALIDATES THE VERSION *AND* ITS EVALUATION.
 *
 * Total percentage, theoretical density, binder/filler ratio, cost and VOC are
 * all DERIVED from the components (§4 keeps that derivation on the server), so
 * a saved composition changes every one of them. Invalidating only the version
 * would leave the evaluation panel showing figures computed from the previous
 * composition — numbers that look authoritative and describe a formula that no
 * longer exists.
 */
export function useSetComposition(versionId: string): {
  readonly save: (components: readonly ComponentLineRequest[], after?: () => void) => void;
  readonly saved: { total_percentage: string } | null;
  readonly isPending: boolean;
  readonly error: Error | null;
} {
  const resolved = useCredentials();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (job: {
      components: readonly ComponentLineRequest[];
      after?: () => void;
    }) => {
      if (!resolved.ok) {
        throw isApiConfigured
          ? new ApiNoSessionError(resolved.reason)
          : new ApiNotConfiguredError();
      }
      return setComposition(resolved.credentials, versionId, job.components);
    },
    onSuccess: (_data, job) => {
      void queryClient.invalidateQueries({ queryKey: ["formula-version", versionId] });
      void queryClient.invalidateQueries({ queryKey: ["formula-evaluation", versionId] });
      void queryClient.invalidateQueries({ queryKey: ["formulations-formulas"] });
      job.after?.();
    },
  });

  return {
    save: (components, after) => mutation.mutate({ components, after }),
    saved: mutation.data ?? null,
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
  };
}

/**
 * ONE material, with the fields the grid leaves out.
 *
 * 🔴 THE EDIT FORM CANNOT LOAD FROM THE LIST. `PUT /api/materials/{id}` writes
 * every editable column, and `GET /api/materials` omits four of them
 * (`description`, `notes`, and both equivalent weights) — so a form prefilled
 * from the grid would have blanked all four on every save. `lib/api/materials.ts`
 * carries the same note beside the schema.
 */
export function useMaterial(materialId: string): LiveOnly<MaterialDetail> {
  return useLiveOnlyRecord("materials-material", materialId, (credentials, signal) =>
    fetchMaterial(credentials, materialId, signal),
  );
}

/**
 * Edit a material, move it along its status ladder, or link a supplier to it.
 *
 * 🔴 ONE HOOK FOR ALL THREE, because all three change what the materials list
 * says and all three belong to the same row. Three hooks would give the row
 * three pending states and three places to render an error.
 *
 * ⚠️ THEY HAVE DIFFERENT PERMISSIONS AND THE CALLER CHECKS THEM.
 * `material.edit` edits, `supplier.manage` links, and the status ladder
 * resolves its permission PER TRANSITION. Bundling the requests into one hook
 * does not bundle the authorization.
 */
export function useMaterialWrites(materialId: string): {
  readonly changeStatus: (request: MaterialStatusRequest, after?: () => void) => void;
  readonly linkSupplier: (request: SupplierLinkRequest, after?: () => void) => void;
  readonly edit: (request: MaterialEditRequest, after?: () => void) => void;
  readonly isPending: boolean;
  readonly error: Error | null;
  readonly lastAction: string | null;
} {
  const resolved = useCredentials();
  const queryClient = useQueryClient();

  const credentials = () => {
    if (!resolved.ok) {
      throw isApiConfigured ? new ApiNoSessionError(resolved.reason) : new ApiNotConfiguredError();
    }
    return resolved.credentials;
  };

  const mutation = useMutation({
    mutationFn: async (
      job:
        | { kind: "status"; request: MaterialStatusRequest; after?: () => void }
        | { kind: "supplier"; request: SupplierLinkRequest; after?: () => void }
        | { kind: "edit"; request: MaterialEditRequest; after?: () => void },
    ) => {
      if (job.kind === "status") {
        const changed = await changeMaterialStatus(credentials(), materialId, job.request);
        return `Status is now ${changed.status}.`;
      }
      if (job.kind === "edit") {
        await updateMaterial(credentials(), materialId, job.request);
        return "Material saved.";
      }
      await linkSupplier(credentials(), materialId, job.request);
      return "Supplier linked.";
    },
    onSuccess: (_data, job) => {
      void queryClient.invalidateQueries({ queryKey: ["materials"] });
      // A restricted material hard-blocks every formula that uses it, so the
      // formula list's answer changes too. Leaving it stale is how a blocked
      // submission looks like a bug in Formulations.
      void queryClient.invalidateQueries({ queryKey: ["formulations-formulas"] });
      void queryClient.invalidateQueries({ queryKey: ["suppliers"] });
      // The edit form loads from the DETAIL endpoint, which has its own key.
      // Without this the grid updates and the form the person is looking at
      // keeps showing what they just replaced.
      void queryClient.invalidateQueries({ queryKey: ["materials-material", materialId] });
      job.after?.();
    },
  });

  return {
    changeStatus: (request, after) => mutation.mutate({ kind: "status", request, after }),
    linkSupplier: (request, after) => mutation.mutate({ kind: "supplier", request, after }),
    edit: (request, after) => mutation.mutate({ kind: "edit", request, after }),
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
    lastAction: mutation.data ?? null,
  };
}

/** Opportunities this caller can reach. */
export function useOpportunities<TShown = Opportunity[]>(
  project: (live: Opportunity[]) => TShown = (live) => live as unknown as TShown,
): LiveOnly<TShown> {
  return useLiveOnlyList("opportunities", project, fetchOpportunities);
}

/**
 * Every write in the opportunity module.
 *
 * 🔴 THE THREE ACTS HAVE THREE DIFFERENT PERMISSIONS, AND THAT IS THE DESIGN.
 *
 * `opportunity.create` raises and submits, `opportunity.decide` decides, and
 * CONVERSION is gated on `project.create` — because creating the project is the
 * act being authorized. Somebody who may decide but may not create projects
 * hands over at that point. One hook, three gates, checked by the caller.
 */
export function useOpportunityWrites(): {
  readonly raise: (request: OpportunityCreateRequest, after?: () => void) => void;
  readonly submit: (opportunityId: string) => void;
  readonly decide: (
    opportunityId: string,
    request: OpportunityDecisionRequest,
    after?: () => void,
  ) => void;
  readonly convert: (
    opportunityId: string,
    request: OpportunityConversionRequest,
    after?: () => void,
  ) => void;
  readonly isPending: boolean;
  readonly error: Error | null;
  readonly lastAction: string | null;
} {
  const resolved = useCredentials();
  const queryClient = useQueryClient();

  const credentials = () => {
    if (!resolved.ok) {
      throw isApiConfigured ? new ApiNoSessionError(resolved.reason) : new ApiNotConfiguredError();
    }
    return resolved.credentials;
  };

  const mutation = useMutation({
    mutationFn: async (
      job:
        | { kind: "raise"; request: OpportunityCreateRequest; after?: () => void }
        | { kind: "submit"; opportunityId: string }
        | {
            kind: "decide";
            opportunityId: string;
            request: OpportunityDecisionRequest;
            after?: () => void;
          }
        | {
            kind: "convert";
            opportunityId: string;
            request: OpportunityConversionRequest;
            after?: () => void;
          },
    ) => {
      if (job.kind === "raise") {
        const raised = await createOpportunity(credentials(), job.request);
        return `${raised.opportunity_code} raised.`;
      }
      if (job.kind === "submit") {
        const submitted = await submitOpportunity(credentials(), job.opportunityId);
        return `Submitted — now ${submitted.status}.`;
      }
      if (job.kind === "decide") {
        const decided = await decideOpportunity(
          credentials(),
          job.opportunityId,
          job.request,
        );
        return `Decision recorded: ${decided.decision}.`;
      }
      const converted = await convertOpportunity(
        credentials(),
        job.opportunityId,
        job.request,
      );
      // 🔴 NAME THE PROJECT IT PRODUCED. §2's thread only helps if a person can
      // FOLLOW it; "converted" alone leaves them hunting for what it became.
      return `Converted — project ${converted.project_code} created.`;
    },
    onSuccess: (_data, job) => {
      void queryClient.invalidateQueries({ queryKey: ["opportunities"] });
      if (job.kind === "convert") {
        // A conversion creates a PROJECT, so the project list and the stage
        // pipeline both answer differently now.
        void queryClient.invalidateQueries({ queryKey: ["projects"] });
        void queryClient.invalidateQueries({ queryKey: ["project-pipeline"] });
      }
      if ("after" in job) job.after?.();
    },
  });

  return {
    raise: (request, after) => mutation.mutate({ kind: "raise", request, after }),
    submit: (opportunityId) => mutation.mutate({ kind: "submit", opportunityId }),
    decide: (opportunityId, request, after) =>
      mutation.mutate({ kind: "decide", opportunityId, request, after }),
    convert: (opportunityId, request, after) =>
      mutation.mutate({ kind: "convert", opportunityId, request, after }),
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
    lastAction: mutation.data ?? null,
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
  readonly relabel: (
    hypothesisId: string,
    evidenceId: string,
    relationship: "supports" | "contradicts" | "inconclusive",
    note: string | undefined,
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
    relabel: (hypothesisId, evidenceId, relationship, note, after) =>
      run(
        "relabelled evidence",
        () =>
          relabelEvidence(credentials(), failureId, hypothesisId, evidenceId, {
            relationship,
            ...(note === undefined || note === "" ? {} : { note }),
          }),
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

// ---------------------------------------------------------------------------
// Slice 2's project workspace — the ten writes that had no browser caller
// ---------------------------------------------------------------------------

/** One live project, by id. */
export function useProject(projectId: string): LiveOnly<Project> {
  return useLiveOnlyRecord("project", projectId, (credentials, signal) =>
    fetchProject(credentials, projectId, signal),
  );
}

export function useProjectMembers(projectId: string): LiveOnly<ProjectMember[]> {
  return useLiveOnlyRecord("project-members", projectId, (credentials, signal) =>
    fetchProjectMembers(credentials, projectId, signal),
  );
}

export function useMilestones(projectId: string): LiveOnly<Milestone[]> {
  return useLiveOnlyRecord("project-milestones", projectId, (credentials, signal) =>
    fetchMilestones(credentials, projectId, signal),
  );
}

export function useRisks(projectId: string): LiveOnly<Risk[]> {
  return useLiveOnlyRecord("project-risks", projectId, (credentials, signal) =>
    fetchRisks(credentials, projectId, signal),
  );
}

export function usePipeline(projectId: string): LiveOnly<PipelineStage[]> {
  return useLiveOnlyRecord("project-pipeline", projectId, (credentials, signal) =>
    fetchPipeline(credentials, projectId, signal),
  );
}

export function useRequirementMatrix(projectId: string): LiveOnly<RequirementMatrix> {
  return useLiveOnlyRecord("project-requirements", projectId, (credentials, signal) =>
    fetchRequirementMatrix(credentials, projectId, signal),
  );
}

/**
 * The ten writes a project workspace supports.
 *
 * One bundled hook, matching `useTestActions`, `useBatchActions` and
 * `useFailureActions`: the screen needs a single `isPending` and a single
 * `error`, because two mutations in flight against one project is a state no
 * workspace here wants to render.
 *
 * 🔴 EVERY ONE INVALIDATES THE READ IT AFFECTS, AND ONLY THOSE. Advancing a
 * stage changes the pipeline AND the project's `current_stage`, so both go;
 * adding a milestone changes neither. This project has shipped an invalidation
 * that matched nothing under a comment claiming it kept a queue current, so the
 * keys below are the ones the hooks above actually register.
 */
export function useProjectActions(projectId: string): {
  readonly advance: (
    request: { readonly to_stage_code: string; readonly reason: string; readonly force?: boolean },
    after?: () => void,
  ) => void;
  readonly addMilestone: (request: MilestoneRequest, after?: () => void) => void;
  readonly setMilestone: (
    milestoneId: string,
    request: { readonly status: string; readonly actual_date?: string; readonly reason: string },
    after?: () => void,
  ) => void;
  readonly addRisk: (request: RiskRequest, after?: () => void) => void;
  readonly changeRisk: (
    riskId: string,
    request: {
      readonly reason: string;
      readonly status?: string;
      readonly mitigation?: string;
      readonly probability?: "low" | "medium" | "high";
      readonly impact?: "low" | "medium" | "high";
    },
    after?: () => void,
  ) => void;
  readonly addMember: (
    request: { readonly user_id: string; readonly project_role: string },
    after?: () => void,
  ) => void;
  readonly removeMember: (userId: string, reason: string, after?: () => void) => void;
  readonly addRequirement: (request: RequirementRequest, after?: () => void) => void;
  readonly approve: (requirementId: string, after?: () => void) => void;
  readonly revise: (
    requirementId: string,
    request: RequirementRequest & { readonly reason: string },
    after?: () => void,
  ) => void;
  readonly isPending: boolean;
  readonly error: Error | null;
  readonly lastAction: string | null;
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

  const invalidate = (keys: readonly string[]) => {
    for (const key of keys) {
      void queryClient.invalidateQueries({ queryKey: [key, projectId] });
    }
  };

  const mutation = useMutation({
    mutationFn: async (job: {
      readonly label: string;
      readonly keys: readonly string[];
      readonly run: () => Promise<unknown>;
      readonly after?: () => void;
    }) => {
      await job.run();
      return job;
    },
    onSuccess: (job) => {
      invalidate(job.keys);
      job.after?.();
    },
  });

  const run = (
    label: string,
    keys: readonly string[],
    make: () => Promise<unknown>,
    after?: () => void,
  ) => mutation.mutate({ label, keys, run: make, after });

  return {
    advance: (request, after) =>
      // Both: the pipeline gains a stage row and the project's `current_stage`
      // moves, and the header reads the second.
      run(
        "stage advance",
        ["project-pipeline", "project"],
        () => advanceStage(credentials(), projectId, request),
        after,
      ),
    addMilestone: (request, after) =>
      run(
        "milestone",
        ["project-milestones"],
        () => createMilestone(credentials(), projectId, request),
        after,
      ),
    setMilestone: (milestoneId, request, after) =>
      run(
        "milestone status",
        ["project-milestones"],
        () => setMilestoneStatus(credentials(), projectId, milestoneId, request),
        after,
      ),
    addRisk: (request, after) =>
      run("risk", ["project-risks"], () => createRisk(credentials(), projectId, request), after),
    changeRisk: (riskId, request, after) =>
      run(
        "risk update",
        ["project-risks"],
        () => updateRisk(credentials(), projectId, riskId, request),
        after,
      ),
    addMember: (request, after) =>
      run(
        "member",
        ["project-members"],
        () => addProjectMember(credentials(), projectId, request),
        after,
      ),
    removeMember: (userId, reason, after) =>
      run(
        "member removal",
        ["project-members"],
        () => removeProjectMember(credentials(), projectId, userId, reason),
        after,
      ),
    addRequirement: (request, after) =>
      run(
        "requirement",
        ["project-requirements"],
        () => createRequirement(credentials(), projectId, request),
        after,
      ),
    approve: (requirementId, after) =>
      run(
        "requirement approval",
        ["project-requirements"],
        () => approveRequirement(credentials(), projectId, requirementId),
        after,
      ),
    revise: (requirementId, request, after) =>
      run(
        "requirement revision",
        ["project-requirements"],
        () => reviseRequirement(credentials(), projectId, requirementId, request),
        after,
      ),
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
    lastAction: mutation.data?.label ?? null,
    unavailable: resolved.ok ? null : resolved.failed ? null : resolved.reason,
  };
}

// ---------------------------------------------------------------------------
// Administration — the eleven writes the plan's own §H warned about
// ---------------------------------------------------------------------------
//
// 🔴 "AN ADMINISTRATOR WHO CAN BE READ BUT NEVER GRANTED DOES NOT EXIST."
//
// `IMPLEMENTATION_PLAN.md` §H says that, in a section written because two
// earlier plan versions promised things were "editable in Administration" while
// no slice built the screen. The API answered it in Slice 1; the browser did
// not. Measured 2026-08-27: eleven `admin.*` write endpoints, zero client
// functions, zero controls.

export function useAdminMembers(): LiveOnly<AdminMember[]> {
  return useLiveOnlyList("admin-members", (live) => live, fetchAdminMembers);
}

export function useRoles(): LiveOnly<Role[]> {
  return useLiveOnlyList("admin-roles", (live) => live, fetchRoles);
}

export function usePermissionCatalogue(): LiveOnly<Permission[]> {
  return useLiveOnlyList("admin-permissions", (live) => live, fetchPermissions);
}

/**
 * The access-request queue — the reader `public_intel.access_requests` never had.
 *
 * ⚠️ THE QUERY KEY CARRIES THE STATUS. Without it, switching the filter would
 * serve the previous queue out of the cache and an administrator would decide
 * against a list that is not the one on screen.
 */
export function useAccessRequests(
  status: "new" | "approved" | "rejected" | "all" = "new",
): LiveOnly<AccessRequest[]> {
  return useLiveOnlyList<AccessRequest[], AccessRequest[]>(
    `admin-access-requests:${status}`,
    (live) => live,
    (credentials: ApiCredentials, signal?: AbortSignal) =>
      fetchAccessRequests(credentials, signal, status),
  );
}

export function useStageDefinitions(): LiveOnly<StageDefinition[]> {
  return useLiveOnlyList("admin-stage-gates", (live) => live, fetchStageDefinitions);
}

export function useUnits(): LiveOnly<Unit[]> {
  return useLiveOnlyList("admin-units", (live) => live, fetchUnits);
}

export function useProductFamilies(): LiveOnly<ProductFamily[]> {
  return useLiveOnlyList("admin-product-families", (live) => live, fetchProductFamilies);
}

/**
 * Every administration write, in one hook.
 *
 * Matching `useTestActions`, `useBatchActions`, `useFailureActions` and
 * `useProjectActions`: one `isPending`, one `error`, and an `after` callback
 * that runs only on success so a refused write does not clear the reason
 * somebody typed.
 */
export function useAdminActions(): {
  readonly invite: (request: MemberInviteRequest, after?: () => void) => void;
  readonly decide: (
    requestId: string,
    request: AccessRequestDecisionRequest,
    after?: () => void,
  ) => void;
  readonly grant: (
    memberId: string,
    roleCode: string,
    reason: string,
    after?: () => void,
  ) => void;
  readonly revoke: (
    memberId: string,
    roleCode: string,
    reason: string,
    after?: () => void,
  ) => void;
  readonly setStatus: (
    memberId: string,
    status: "active" | "inactive",
    reason: string,
    after?: () => void,
  ) => void;
  readonly addStage: (request: StageWriteRequest, after?: () => void) => void;
  readonly editStage: (
    stageId: string,
    request: StageWriteRequest,
    after?: () => void,
  ) => void;
  readonly setStageActive: (
    stageId: string,
    isActive: boolean,
    reason: string,
    after?: () => void,
  ) => void;
  readonly reorder: (orderedStageIds: readonly string[], after?: () => void) => void;
  readonly addUnit: (
    request: { code: string; name: string; quantity_kind: string },
    after?: () => void,
  ) => void;
  readonly addFamily: (
    request: { code: string; name: string; description?: string },
    after?: () => void,
  ) => void;
  readonly setItemActive: (
    collection: "units" | "product-families",
    itemId: string,
    isActive: boolean,
    after?: () => void,
  ) => void;
  readonly isPending: boolean;
  readonly error: Error | null;
  readonly lastAction: string | null;
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
      readonly label: string;
      readonly keys: readonly string[];
      readonly run: () => Promise<unknown>;
      readonly after?: () => void;
    }) => {
      await job.run();
      return job;
    },
    onSuccess: (job) => {
      for (const key of job.keys) {
        void queryClient.invalidateQueries({ queryKey: [key] });
      }
      job.after?.();
    },
  });

  const run = (
    label: string,
    keys: readonly string[],
    make: () => Promise<unknown>,
    after?: () => void,
  ) => mutation.mutate({ label, keys, run: make, after });

  return {
    invite: (request, after) =>
      run("membership", ["admin-members"], () => inviteMember(credentials(), request), after),
    // 🔴 FOUR KEYS, NOT ONE. An approval writes a membership AND moves the
    // request out of the `new` queue, so a decision that invalidated only its
    // own filter would leave the members table and the other three queues
    // showing the state before the decision — the screen contradicting itself
    // in two places at once.
    decide: (requestId, request, after) =>
      run(
        "access request",
        [
          "admin-members",
          "admin-access-requests:new",
          "admin-access-requests:approved",
          "admin-access-requests:rejected",
          "admin-access-requests:all",
        ],
        () => decideAccessRequest(credentials(), requestId, request),
        after,
      ),
    grant: (memberId, roleCode, reason, after) =>
      run(
        "role grant",
        ["admin-members"],
        () => grantRole(credentials(), memberId, roleCode, reason),
        after,
      ),
    revoke: (memberId, roleCode, reason, after) =>
      run(
        "role revoke",
        ["admin-members"],
        () => revokeRole(credentials(), memberId, roleCode, reason),
        after,
      ),
    setStatus: (memberId, status, reason, after) =>
      run(
        "membership status",
        ["admin-members"],
        () => setMemberStatus(credentials(), memberId, status, reason),
        after,
      ),
    addStage: (request, after) =>
      run("stage", ["admin-stage-gates"], () => createStage(credentials(), request), after),
    editStage: (stageId, request, after) =>
      run(
        "stage update",
        ["admin-stage-gates"],
        () => updateStage(credentials(), stageId, request),
        after,
      ),
    setStageActive: (stageId, isActive, reason, after) =>
      run(
        isActive ? "stage restored" : "stage retired",
        ["admin-stage-gates"],
        () => setStageActive(credentials(), stageId, isActive, reason),
        after,
      ),
    reorder: (orderedStageIds, after) =>
      run(
        "stage order",
        ["admin-stage-gates"],
        () => reorderStages(credentials(), orderedStageIds),
        after,
      ),
    addUnit: (request, after) =>
      run("unit", ["admin-units"], () => createUnit(credentials(), request), after),
    addFamily: (request, after) =>
      run(
        "product family",
        ["admin-product-families"],
        () => createProductFamily(credentials(), request),
        after,
      ),
    setItemActive: (collection, itemId, isActive, after) =>
      run(
        isActive ? "restored" : "retired",
        // Only the collection that changed. `units` and `product-families` are
        // separate queries, and invalidating both on either would refetch a
        // list nothing touched.
        [collection === "units" ? "admin-units" : "admin-product-families"],
        () => setReferenceItemActive(credentials(), collection, itemId, isActive),
        after,
      ),
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
    lastAction: mutation.data?.label ?? null,
    unavailable: resolved.ok ? null : resolved.failed ? null : resolved.reason,
  };
}


// ---------------------------------------------------------------------------
// Material Safety Data & Research Center
//
// Written in FULL, never abbreviated. `MSD` in this codebase is the Material
// Science & Development Assistant -- a different capability with its own
// tables, permission and conversations. Nothing here contains `msd`.
// ---------------------------------------------------------------------------

/** Safety alerts this caller can reach. Live or nothing -- see `LiveOnly`. */
export function useSafetyAlerts<TShown = SafetyAlert[]>(
  project: (live: SafetyAlert[]) => TShown = (live) => live as unknown as TShown,
): LiveOnly<TShown> {
  return useLiveOnlyList("safety-alerts", project, fetchSafetyAlerts);
}

/** Interpretations awaiting technical review -- the compliance queue. */
export function usePendingInterpretations<TShown = PendingInterpretation[]>(
  project: (live: PendingInterpretation[]) => TShown = (live) =>
    live as unknown as TShown,
): LiveOnly<TShown> {
  return useLiveOnlyList("safety-pending", project, fetchPendingInterpretations);
}

/**
 * The safety position for one material.
 *
 * 🔴 `data.current` IS NULLABLE AND THE PAGE MUST SAY SO. Null means no
 * interpreted SDS that `materials.usable_documents` still returns -- none on
 * file, or the one on file expired, was superseded, or failed the scanner.
 * Rendering that as an empty panel would let "no hazard data" read as "no
 * hazards".
 */
export function useSafetyPosition(materialId: string): LiveOnly<SafetyPosition> {
  return useLiveOnlyRecord("safety-position", materialId, (credentials, signal) =>
    fetchSafetyPosition(credentials, materialId, signal),
  );
}

/**
 * The two write actions on the Material Safety Data screen.
 *
 * One hook rather than two, because they invalidate the same queries and a
 * screen showing both wants one `isPending`. `lastAction` names which one
 * happened, so the confirmation can be specific rather than "done".
 */
export function useSafetyActions(): {
  readonly acknowledge: (alertId: string) => void;
  readonly review: (sdsVersionId: string, accept: boolean) => void;
  readonly isPending: boolean;
  readonly error: Error | null;
  readonly lastAction: string | null;
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
    mutationFn: async (
      job:
        | { readonly kind: "acknowledge"; readonly alertId: string }
        | { readonly kind: "review"; readonly sdsVersionId: string; readonly accept: boolean },
    ) => {
      if (job.kind === "acknowledge") {
        await acknowledgeAlert(credentials(), job.alertId);
        return "acknowledged";
      }
      const result = await reviewInterpretation(
        credentials(),
        job.sdsVersionId,
        job.accept,
      );
      return result.review_state;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["safety-alerts"] });
      void queryClient.invalidateQueries({ queryKey: ["safety-pending"] });
      // A confirmed interpretation changes what the material screen shows.
      void queryClient.invalidateQueries({ queryKey: ["safety-position"] });
    },
  });

  return {
    acknowledge: (alertId) => mutation.mutate({ kind: "acknowledge", alertId }),
    review: (sdsVersionId, accept) =>
      mutation.mutate({ kind: "review", sdsVersionId, accept }),
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
    lastAction: mutation.data ?? null,
    unavailable: resolved.ok ? null : resolved.failed ? null : resolved.reason,
  };
}


/** Usable Safety Data Sheets nobody has read yet — what the record form offers. */
export function useInterpretableDocuments<TShown = InterpretableDocument[]>(
  project: (live: InterpretableDocument[]) => TShown = (live) =>
    live as unknown as TShown,
): LiveOnly<TShown> {
  return useLiveOnlyList("safety-candidates", project, fetchInterpretableDocuments);
}

/** Every reading recorded for a material, history included. */
export function useMaterialInterpretations(
  materialId: string,
): LiveOnly<MaterialInterpretation[]> {
  return useLiveOnlyRecord("safety-material-readings", materialId, (credentials, signal) =>
    fetchMaterialInterpretations(credentials, materialId, signal),
  );
}

/**
 * The three writes that had no browser caller.
 *
 * 🔴 THEY SHIP WITH THEIR CONTROLS, IN THE SAME COMMIT. `POST /interpretations`,
 * `POST .../alerts` and `POST .../safety-reviews` existed, were tested, and no
 * person could press anything that called them — "a route with no caller is the
 * same defect as a table with no writer", which this project has counted 23
 * instances of. Codex found it in review.
 *
 * `lastResult` carries the shape each one returns, because they are not
 * interchangeable: raising alerts can legitimately return NONE (nothing
 * substantive changed), and a screen that said "done" would hide that.
 */
export function useSafetyWrites(): {
  readonly record: (request: InterpretationRequest, after?: () => void) => void;
  readonly raise: (sdsVersionId: string, previousVersionId: string) => void;
  readonly openReview: (
    sdsVersionId: string,
    projectId: string,
    reason: string,
    after?: () => void,
  ) => void;
  readonly isPending: boolean;
  readonly error: Error | null;
  readonly lastResult:
    | { readonly kind: "recorded"; readonly id: string }
    | { readonly kind: "alerts"; readonly count: number }
    | { readonly kind: "review"; readonly id: string }
    | null;
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
    mutationFn: async (
      job:
        | { readonly kind: "record"; readonly request: InterpretationRequest; readonly after?: () => void }
        | { readonly kind: "raise"; readonly sdsVersionId: string; readonly previousVersionId: string }
        | {
            readonly kind: "review";
            readonly sdsVersionId: string;
            readonly projectId: string;
            readonly reason: string;
            readonly after?: () => void;
          },
    ) => {
      if (job.kind === "record") {
        const created = await createInterpretation(credentials(), job.request);
        return { kind: "recorded" as const, id: created.id };
      }
      if (job.kind === "raise") {
        const raised = await raiseAlerts(
          credentials(),
          job.sdsVersionId,
          job.previousVersionId,
        );
        return { kind: "alerts" as const, count: raised.length };
      }
      const opened = await openSafetyReview(
        credentials(),
        job.sdsVersionId,
        job.projectId,
        job.reason,
      );
      return { kind: "review" as const, id: opened.id };
    },
    onSuccess: (_data, job) => {
      void queryClient.invalidateQueries({ queryKey: ["safety-alerts"] });
      void queryClient.invalidateQueries({ queryKey: ["safety-pending"] });
      void queryClient.invalidateQueries({ queryKey: ["safety-candidates"] });
      void queryClient.invalidateQueries({ queryKey: ["safety-position"] });
      void queryClient.invalidateQueries({ queryKey: ["safety-material-readings"] });
      // 🔴 THE FORM IS CLEARED ON SUCCESS, AND ONLY ON SUCCESS. The same
      // reasoning as `useOpenInvestigation`: nothing acknowledged the create,
      // so a user who saw no confirmation pressed the button again and hit a
      // uniqueness refusal that reads as though the FIRST attempt had failed.
      if (job.kind === "record" || job.kind === "review") job.after?.();
    },
  });

  return {
    record: (request, after) => mutation.mutate({ kind: "record", request, after }),
    raise: (sdsVersionId, previousVersionId) =>
      mutation.mutate({ kind: "raise", sdsVersionId, previousVersionId }),
    openReview: (sdsVersionId, projectId, reason, after) =>
      mutation.mutate({ kind: "review", sdsVersionId, projectId, reason, after }),
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
    lastResult: mutation.data ?? null,
    unavailable: resolved.ok ? null : resolved.failed ? null : resolved.reason,
  };
}

/** Materials whose newest reading has a predecessor — what "raise alerts" offers. */
export function useComparableRevisions<TShown = ComparableRevision[]>(
  project: (live: ComparableRevision[]) => TShown = (live) => live as unknown as TShown,
): LiveOnly<TShown> {
  return useLiveOnlyList("safety-comparable", project, fetchComparableRevisions);
}

// ---------------------------------------------------------------------------
// Role dashboards — the endpoint that had no browser caller
// ---------------------------------------------------------------------------

/**
 * Which dashboard this caller should see, from the roles their membership
 * carries. `null` means they hold no role that has one.
 *
 * Reads the ACTIVE organization's roles, not the first in the list: membership
 * is per-tenant, and picking the first has already been a real defect in this
 * provider once — it moved a chemist's writes into the wrong tenant.
 */
export function useDashboardRole(): DashboardRole | null {
  const session = useSession();
  const { organizations } = useAuth();
  if (session.status !== "authenticated") return null;
  const active = organizations.find(
    (org: OrganizationChoice) => org.organizationId === session.credentials.organizationId,
  );
  return dashboardForRoles(active?.roles ?? []);
}

/**
 * One role's dashboard, from source records.
 *
 * 🔴 THIS IS THE CALLER `GET /api/dashboards/{role}` NEVER HAD. The endpoint,
 * four builders, the analysis conductor and a db test all existed; nothing in
 * the browser asked for any of it, so every signed-in person saw one fixed
 * screen. Signed in as the director, you got the chemist's.
 *
 * `enabled` waits for a role: requesting `/api/dashboards/null` would be a 404
 * dressed up as an outage.
 */
export function useRoleDashboard(role: DashboardRole | null): LiveOnly<RoleDashboard> {
  return useLiveOnlyRecord("role-dashboard", role ?? "", (credentials, signal) =>
    fetchRoleDashboard(credentials, role ?? "", signal),
  );
}

// ---------------------------------------------------------------------------
// Competitor intelligence
// ---------------------------------------------------------------------------

export function useCompetitorProducts<TShown = CompetitorProduct[]>(
  project: (live: CompetitorProduct[]) => TShown = (live) => live as unknown as TShown,
): LiveOnly<TShown> {
  return useLiveOnlyList("competitor-products", project, fetchCompetitorProducts);
}

/** The Composition Evidence Matrix for one product. */
export function useCompositionMatrix(productId: string): LiveOnly<CompositionMatrix> {
  return useLiveOnlyRecord("competitor-composition", productId, (credentials, signal) =>
    fetchCompositionMatrix(credentials, productId, signal),
  );
}

/** Labels, photographs and literature on file for one product. */
export function useCompetitorDocuments(productId: string): LiveOnly<CompetitorDocument[]> {
  return useLiveOnlyRecord("competitor-documents", productId, (credentials, signal) =>
    fetchCompetitorDocuments(credentials, productId, signal),
  );
}

/**
 * Physical samples held for one competitor product.
 *
 * 🔴 THE LIST EXISTS SO A CLAIM CAN CITE ONE. `manual_observation` means a
 * person read a tin; the matrix stores WHICH tin in `sample_id`, and until
 * this hook existed no screen could offer the choice, so every observation
 * was recorded unattributable.
 */
export function useCompetitorSamples(productId: string): LiveOnly<CompetitorSample[]> {
  return useLiveOnlyRecord("competitor-samples", productId, (credentials, signal) =>
    fetchCompetitorSamples(credentials, productId, signal),
  );
}

/** Measured comparisons recorded against one competitor product. */
export function useCompetitorBenchmarks(productId: string): LiveOnly<CompetitorBenchmark[]> {
  return useLiveOnlyRecord("competitor-benchmarks", productId, (credentials, signal) =>
    fetchCompetitorBenchmarks(credentials, productId, signal),
  );
}

/**
 * Every write in competitor intelligence, including the file upload.
 *
 * 🔴 THE UPLOAD IS IN THE SAME HOOK AS THE REST, so the screen has one
 * `isPending` and one error. A separate upload hook would let a form show
 * "saved" while a file was still in flight.
 */
export function useCompetitorWrites(): {
  readonly registerProduct: (request: ProductRequest, after?: () => void) => void;
  readonly upload: (
    productId: string,
    file: File,
    documentType: string,
    title: string,
    after?: () => void,
  ) => void;
  readonly recordEvidence: (
    productId: string,
    request: CompetitorEvidenceRequest,
    after?: () => void,
  ) => void;
  readonly grade: (evidenceId: string, confidence: string) => void;
  readonly registerSample: (
    productId: string,
    request: CompetitorSampleRequest,
    after?: () => void,
  ) => void;
  readonly recordBenchmark: (
    productId: string,
    request: BenchmarkRequest,
    after?: () => void,
  ) => void;
  readonly isPending: boolean;
  readonly error: Error | null;
  readonly lastAction: string | null;
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
    mutationFn: async (
      job:
        | { readonly kind: "product"; readonly request: ProductRequest; readonly after?: () => void }
        | {
            readonly kind: "upload";
            readonly productId: string;
            readonly file: File;
            readonly documentType: string;
            readonly title: string;
            readonly after?: () => void;
          }
        | {
            readonly kind: "evidence";
            readonly productId: string;
            readonly request: CompetitorEvidenceRequest;
            readonly after?: () => void;
          }
        | {
            readonly kind: "sample";
            readonly productId: string;
            readonly request: CompetitorSampleRequest;
            readonly after?: () => void;
          }
        | {
            readonly kind: "benchmark";
            readonly productId: string;
            readonly request: BenchmarkRequest;
            readonly after?: () => void;
          }
        | { readonly kind: "grade"; readonly evidenceId: string; readonly confidence: string },
    ) => {
      if (job.kind === "product") {
        await registerCompetitorProduct(credentials(), job.request);
        return "product registered";
      }
      if (job.kind === "upload") {
        await uploadCompetitorDocument(
          credentials(),
          job.productId,
          job.file,
          job.documentType,
          job.title,
        );
        return "uploaded";
      }
      if (job.kind === "evidence") {
        await recordCompetitorEvidence(credentials(), job.productId, job.request);
        return "evidence recorded";
      }
      if (job.kind === "sample") {
        await registerCompetitorSample(credentials(), job.productId, job.request);
        return "sample registered";
      }
      if (job.kind === "benchmark") {
        await recordCompetitorBenchmark(credentials(), job.productId, job.request);
        return "benchmark recorded";
      }
      const graded = await gradeCompetitorEvidence(
        credentials(),
        job.evidenceId,
        job.confidence,
      );
      return graded.confidence;
    },
    onSuccess: (_data, job) => {
      void queryClient.invalidateQueries({ queryKey: ["competitor-products"] });
      void queryClient.invalidateQueries({ queryKey: ["competitor-composition"] });
      void queryClient.invalidateQueries({ queryKey: ["competitor-documents"] });
      // A new sample changes what an observation may cite, so the sample list
      // is invalidated by EVERY write here, not only by "sample".
      void queryClient.invalidateQueries({ queryKey: ["competitor-samples"] });
      void queryClient.invalidateQueries({ queryKey: ["competitor-benchmarks"] });
      if (job.kind !== "grade") job.after?.();
    },
  });

  return {
    registerProduct: (request, after) => mutation.mutate({ kind: "product", request, after }),
    upload: (productId, file, documentType, title, after) =>
      mutation.mutate({ kind: "upload", productId, file, documentType, title, after }),
    recordEvidence: (productId, request, after) =>
      mutation.mutate({ kind: "evidence", productId, request, after }),
    grade: (evidenceId, confidence) =>
      mutation.mutate({ kind: "grade", evidenceId, confidence }),
    registerSample: (productId, request, after) =>
      mutation.mutate({ kind: "sample", productId, request, after }),
    recordBenchmark: (productId, request, after) =>
      mutation.mutate({ kind: "benchmark", productId, request, after }),
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
    lastAction: mutation.data ?? null,
    unavailable: resolved.ok ? null : resolved.failed ? null : resolved.reason,
  };
}


/* -------------------------------------------------------------------------
 * The Research Center
 *
 * 🔴 ONE WRITE HOOK, AND WHAT THAT DOES AND DOES NOT GUARANTEE.
 *
 * `useResearchWrites` covers every write in the vertical, so any component
 * that calls it gets one `isPending` and one error for all of them, and the
 * invalidations stay in one place instead of being restated per form.
 *
 * ⚠️ IT DOES NOT MAKE THE WHOLE SCREEN SHARE ONE PENDING STATE, AND AN EARLIER
 * VERSION OF THIS COMMENT CLAIMED IT DID. `research/page.tsx` calls this hook
 * in eleven components, each getting its OWN `useMutation` — so a panel can
 * show "saved" while a sibling write is still in flight, which is exactly what
 * the old wording said was prevented. That is deliberate: per-panel feedback is
 * what a page of independent forms wants, and one shared spinner would grey out
 * six forms because a seventh was saving. The claim is corrected rather than
 * the components restructured to fit it — a comment asserting a rule that does
 * not exist is a defect this project has a standing note about, and the
 * Supervisor found this one.
 * ---------------------------------------------------------------------- */

/** Research workspaces this caller can reach. */
export function useInvestigations<TShown = ResearchInvestigation[]>(
  project: (live: ResearchInvestigation[]) => TShown = (live) => live as unknown as TShown,
): LiveOnly<TShown> {
  return useLiveOnlyList("research-investigations", project, fetchInvestigations);
}

/** The findings register — every finding, with its ROUTE's approval status. */
export function useResearchFindings<TShown = ResearchFinding[]>(
  project: (live: ResearchFinding[]) => TShown = (live) => live as unknown as TShown,
): LiveOnly<TShown> {
  return useLiveOnlyList("research-findings", project, fetchFindings);
}

/** Experiment proposals, including the formula version an accepted one made. */
export function useExperimentProposals<TShown = ExperimentProposal[]>(
  project: (live: ExperimentProposal[]) => TShown = (live) => live as unknown as TShown,
): LiveOnly<TShown> {
  return useLiveOnlyList("research-proposals", project, fetchProposals);
}

export function useResearchQuestions(investigationId: string): LiveOnly<ResearchQuestion[]> {
  return useLiveOnlyRecord("research-questions", investigationId, (credentials, signal) =>
    fetchResearchQuestions(credentials, investigationId, signal),
  );
}

export function useResearchSources(investigationId: string): LiveOnly<ResearchSource[]> {
  return useLiveOnlyRecord("research-sources", investigationId, (credentials, signal) =>
    fetchResearchSources(credentials, investigationId, signal),
  );
}

export function useEvidenceCards(investigationId: string): LiveOnly<EvidenceCard[]> {
  return useLiveOnlyRecord("research-evidence", investigationId, (credentials, signal) =>
    fetchEvidenceCards(credentials, investigationId, signal),
  );
}

export function useResearchHypotheses(investigationId: string): LiveOnly<Hypothesis[]> {
  return useLiveOnlyRecord("research-hypotheses", investigationId, (credentials, signal) =>
    fetchHypotheses(credentials, investigationId, signal),
  );
}

export function useResearchGaps(investigationId: string): LiveOnly<KnowledgeGap[]> {
  return useLiveOnlyRecord("research-gaps", investigationId, (credentials, signal) =>
    fetchKnowledgeGaps(credentials, investigationId, signal),
  );
}

/** Every write in the Research Center. */
export function useResearchWrites(): {
  readonly open: (request: InvestigationRequest, after?: () => void) => void;
  readonly close: (investigationId: string) => void;
  readonly askQuestion: (
    investigationId: string,
    question: string,
    after?: () => void,
  ) => void;
  readonly settleQuestion: (questionId: string, status: string) => void;
  readonly addSource: (
    investigationId: string,
    request: ResearchSourceRequest,
    after?: () => void,
  ) => void;
  readonly addEvidence: (
    investigationId: string,
    request: ResearchEvidenceRequest,
    after?: () => void,
  ) => void;
  readonly addHypothesis: (
    investigationId: string,
    request: ResearchHypothesisRequest,
    after?: () => void,
  ) => void;
  readonly decideHypothesis: (hypothesisId: string, status: string) => void;
  readonly addGap: (investigationId: string, request: GapRequest, after?: () => void) => void;
  readonly resolveGap: (gapId: string) => void;
  readonly draftFinding: (
    investigationId: string,
    request: FindingRequest,
    after?: () => void,
  ) => void;
  readonly submit: (findingId: string) => void;
  readonly promote: (findingId: string) => void;
  readonly propose: (
    investigationId: string,
    request: ProposalRequest,
    after?: () => void,
  ) => void;
  readonly accept: (
    proposalId: string,
    request: AcceptProposalRequest,
    after?: () => void,
  ) => void;
  readonly reject: (proposalId: string, decisionNote: string, after?: () => void) => void;
  readonly isPending: boolean;
  readonly error: Error | null;
  readonly lastAction: string | null;
  readonly unavailable: string | null;
} {
  const resolved = useCredentials();
  const queryClient = useQueryClient();

  const credentials = () => {
    if (!resolved.ok) {
      throw isApiConfigured ? new ApiNoSessionError(resolved.reason) : new ApiNotConfiguredError();
    }
    return resolved.credentials;
  };

  const mutation = useMutation({
    mutationFn: async (
      job:
        | {
            readonly kind: "open";
            readonly request: InvestigationRequest;
            readonly after?: () => void;
          }
        | { readonly kind: "close"; readonly investigationId: string }
        | {
            readonly kind: "question";
            readonly investigationId: string;
            readonly question: string;
            readonly after?: () => void;
          }
        | { readonly kind: "settle"; readonly questionId: string; readonly status: string }
        | {
            readonly kind: "source";
            readonly investigationId: string;
            readonly request: ResearchSourceRequest;
            readonly after?: () => void;
          }
        | {
            readonly kind: "evidence";
            readonly investigationId: string;
            readonly request: ResearchEvidenceRequest;
            readonly after?: () => void;
          }
        | {
            readonly kind: "hypothesis";
            readonly investigationId: string;
            readonly request: ResearchHypothesisRequest;
            readonly after?: () => void;
          }
        | { readonly kind: "decide-hypothesis"; readonly hypothesisId: string; readonly status: string }
        | {
            readonly kind: "gap";
            readonly investigationId: string;
            readonly request: GapRequest;
            readonly after?: () => void;
          }
        | { readonly kind: "resolve-gap"; readonly gapId: string }
        | {
            readonly kind: "finding";
            readonly investigationId: string;
            readonly request: FindingRequest;
            readonly after?: () => void;
          }
        | { readonly kind: "submit"; readonly findingId: string }
        | { readonly kind: "promote"; readonly findingId: string }
        | {
            readonly kind: "propose";
            readonly investigationId: string;
            readonly request: ProposalRequest;
            readonly after?: () => void;
          }
        | {
            readonly kind: "accept";
            readonly proposalId: string;
            readonly request: AcceptProposalRequest;
            readonly after?: () => void;
          }
        | {
            readonly kind: "reject";
            readonly proposalId: string;
            readonly decisionNote: string;
            readonly after?: () => void;
          },
    ) => {
      if (job.kind === "open") {
        const opened = await openResearchWorkspace(credentials(), job.request);
        return `${opened.investigation_code} opened`;
      }
      if (job.kind === "close") {
        await closeInvestigation(credentials(), job.investigationId);
        return "workspace closed";
      }
      if (job.kind === "question") {
        await recordResearchQuestion(credentials(), job.investigationId, job.question);
        return "question added";
      }
      if (job.kind === "settle") {
        const settled = await settleResearchQuestion(
          credentials(),
          job.questionId,
          job.status,
        );
        return `question ${settled.status}`;
      }
      if (job.kind === "source") {
        await recordResearchSource(credentials(), job.investigationId, job.request);
        return "source recorded";
      }
      if (job.kind === "evidence") {
        await recordEvidenceCard(credentials(), job.investigationId, job.request);
        return "evidence recorded";
      }
      if (job.kind === "hypothesis") {
        await recordResearchHypothesis(credentials(), job.investigationId, job.request);
        return "hypothesis recorded";
      }
      if (job.kind === "decide-hypothesis") {
        const decided = await decideResearchHypothesis(credentials(), job.hypothesisId, job.status);
        return `hypothesis ${decided.status}`;
      }
      if (job.kind === "gap") {
        await recordKnowledgeGap(credentials(), job.investigationId, job.request);
        return "knowledge gap recorded";
      }
      if (job.kind === "resolve-gap") {
        await resolveKnowledgeGap(credentials(), job.gapId);
        return "gap closed";
      }
      if (job.kind === "finding") {
        const drafted = await recordFinding(credentials(), job.investigationId, job.request);
        return `${drafted.finding_code} drafted`;
      }
      if (job.kind === "submit") {
        await submitFinding(credentials(), job.findingId);
        return "submitted for approval";
      }
      if (job.kind === "promote") {
        await promoteFinding(credentials(), job.findingId);
        return "promoted to the Knowledge Library";
      }
      if (job.kind === "propose") {
        const proposed = await proposeExperiment(
          credentials(),
          job.investigationId,
          job.request,
        );
        return `${proposed.proposal_code} proposed`;
      }
      if (job.kind === "accept") {
        const accepted = await acceptProposal(credentials(), job.proposalId, job.request);
        // 🔴 THE VERSION CODE IS THE POINT OF THE MESSAGE. "accepted" alone
        // would leave the chemist hunting for what it produced; §19's loop only
        // closes if the person can follow it to the formula.
        return `accepted — ${accepted.version_code} created`;
      }
      await rejectProposal(credentials(), job.proposalId, job.decisionNote);
      return "proposal rejected";
    },
    onSuccess: (_data, job) => {
      void queryClient.invalidateQueries({ queryKey: ["research-investigations"] });
      void queryClient.invalidateQueries({ queryKey: ["research-questions"] });
      void queryClient.invalidateQueries({ queryKey: ["research-sources"] });
      void queryClient.invalidateQueries({ queryKey: ["research-evidence"] });
      void queryClient.invalidateQueries({ queryKey: ["research-hypotheses"] });
      void queryClient.invalidateQueries({ queryKey: ["research-gaps"] });
      void queryClient.invalidateQueries({ queryKey: ["research-findings"] });
      void queryClient.invalidateQueries({ queryKey: ["research-proposals"] });
      // Accepting a proposal creates a formula version and submitting a finding
      // opens an approval route, so both change screens this module does not
      // own. Not invalidating them would leave `/formulations` and `/approvals`
      // showing a stale answer to a question this action just changed.
      if (job.kind === "accept") {
        void queryClient.invalidateQueries({ queryKey: ["formulations-formulas"] });
      }
      if (job.kind === "submit") {
        void queryClient.invalidateQueries({ queryKey: ["approval-queue"] });
      }
      if (job.kind === "promote") {
        void queryClient.invalidateQueries({ queryKey: ["knowledge-documents"] });
      }
      if ("after" in job) job.after?.();
    },
  });

  return {
    open: (request, after) => mutation.mutate({ kind: "open", request, after }),
    close: (investigationId) => mutation.mutate({ kind: "close", investigationId }),
    askQuestion: (investigationId, question, after) =>
      mutation.mutate({ kind: "question", investigationId, question, after }),
    settleQuestion: (questionId, status) =>
      mutation.mutate({ kind: "settle", questionId, status }),
    addSource: (investigationId, request, after) =>
      mutation.mutate({ kind: "source", investigationId, request, after }),
    addEvidence: (investigationId, request, after) =>
      mutation.mutate({ kind: "evidence", investigationId, request, after }),
    addHypothesis: (investigationId, request, after) =>
      mutation.mutate({ kind: "hypothesis", investigationId, request, after }),
    decideHypothesis: (hypothesisId, status) =>
      mutation.mutate({ kind: "decide-hypothesis", hypothesisId, status }),
    addGap: (investigationId, request, after) =>
      mutation.mutate({ kind: "gap", investigationId, request, after }),
    resolveGap: (gapId) => mutation.mutate({ kind: "resolve-gap", gapId }),
    draftFinding: (investigationId, request, after) =>
      mutation.mutate({ kind: "finding", investigationId, request, after }),
    submit: (findingId) => mutation.mutate({ kind: "submit", findingId }),
    promote: (findingId) => mutation.mutate({ kind: "promote", findingId }),
    propose: (investigationId, request, after) =>
      mutation.mutate({ kind: "propose", investigationId, request, after }),
    accept: (proposalId, request, after) =>
      mutation.mutate({ kind: "accept", proposalId, request, after }),
    reject: (proposalId, decisionNote, after) =>
      mutation.mutate({ kind: "reject", proposalId, decisionNote, after }),
    isPending: mutation.isPending,
    error: (mutation.error as Error | null) ?? null,
    lastAction: mutation.data ?? null,
    unavailable: resolved.ok ? null : resolved.failed ? null : resolved.reason,
  };
}
