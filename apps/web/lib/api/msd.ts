/**
 * MSD, over HTTP.
 *
 * 🔴 THE DISCLAIMER IS A REQUIRED FIELD, NOT AN OPTIONAL ONE.
 *
 * `CLAUDE.md` §7 requires AI output to be labelled "AI-generated
 * recommendation — requires technical review", and the database enforces
 * it: `msd_turns_assistant_is_labelled` refuses an assistant turn whose
 * `disclaimer` is NULL, so an unlabelled answer cannot exist to be
 * fetched.
 *
 * Typing it as `z.string()` rather than `z.string().nullable()` carries
 * that rule to the client: a response without one fails to parse and the
 * panel shows an error, instead of rendering an unlabelled AI answer.
 * The alternative — accepting null and rendering the label "when present"
 * — is precisely how a safety label becomes optional in practice.
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";

export const msdEvidenceSchema = z.object({
  entity_type: z.string(),
  entity_id: z.string(),
  label: z.string().nullable().optional(),
  excerpt: z.string().nullable().optional(),
});

export const msdAnswerSchema = z.object({
  turn_id: z.string(),
  body: z.string(),
  // Required. See the header.
  disclaimer: z.string(),
  intent: z.string(),
  href: z.string().nullable(),
  suggestions: z.array(z.string()),
  evidence: z.array(msdEvidenceSchema),
});

export type MsdAnswer = z.infer<typeof msdAnswerSchema>;

export const msdThreadSchema = z.object({
  id: z.string(),
  title: z.string().nullable(),
  project_id: z.string().nullable(),
  created_at: z.string(),
  // Present on a listed thread, absent on the one just created. `.optional()`
  // rather than a second schema: the two responses differ by exactly this
  // field, and demanding it would reject a perfectly correct 201.
  updated_at: z.string().optional(),
});

export type MsdThread = z.infer<typeof msdThreadSchema>;

/**
 * One turn of a conversation, as stored.
 *
 * 🔴 `disclaimer` IS REQUIRED ON AN ASSISTANT TURN AND ABSENT ON A USER ONE,
 * so it is nullable HERE and not in `msdAnswerSchema`. The difference is
 * real: `msd_turns_assistant_is_labelled` refuses an unlabelled assistant
 * turn at the database, and a user's own question is not an AI output and
 * has nothing to label. A screen rendering history must therefore key the
 * label off `role`, and must never render an assistant turn without one.
 *
 * `turn_number` is an ordinal, not a measurement — a number, and the history
 * is ordered by it rather than by `created_at`, which two turns written in
 * the same transaction can share.
 */
export const msdTurnSchema = z.object({
  id: z.string(),
  turn_number: z.number(),
  role: z.string(),
  body: z.string(),
  disclaimer: z.string().nullable(),
  evidence: z.array(msdEvidenceSchema),
  created_at: z.string(),
});

export type MsdTurn = z.infer<typeof msdTurnSchema>;

/**
 * The caller's own conversations.
 *
 * 🔴 THIS ROUTE HAD NO CALLER, AND THE CONSEQUENCE WAS VISIBLE: a browser
 * could open a thread and ask a question, and could not list threads or read
 * one back. Every reload therefore started an empty conversation on top of a
 * table that was faithfully recording all of them. The assistant appeared to
 * have no memory while the memory existed and was unreachable.
 *
 * No permission argument is sent because the route takes none: threads are
 * owner-scoped in the database, so this returns nobody else's regardless.
 */
export function fetchThreads(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<MsdThread[]> {
  return apiRequest(
    { path: "/api/msd/threads", credentials, signal },
    (payload) => z.array(msdThreadSchema).parse(payload),
  );
}

/** One thread's history, oldest first. The other half of the same gap. */
export function fetchTurns(
  credentials: ApiCredentials,
  threadId: string,
  signal?: AbortSignal,
): Promise<MsdTurn[]> {
  return apiRequest(
    { path: `/api/msd/threads/${threadId}/turns`, credentials, signal },
    (payload) => z.array(msdTurnSchema).parse(payload),
  );
}

export function openThread(
  credentials: ApiCredentials,
  title: string | null,
  signal?: AbortSignal,
): Promise<MsdThread> {
  return apiRequest(
    {
      path: "/api/msd/threads",
      method: "POST",
      body: { title },
      credentials,
      signal,
    },
    (payload) => msdThreadSchema.parse(payload),
  );
}

export function askMsd(
  credentials: ApiCredentials,
  threadId: string,
  question: string,
  signal?: AbortSignal,
): Promise<MsdAnswer> {
  return apiRequest(
    {
      path: `/api/msd/threads/${threadId}/ask`,
      method: "POST",
      body: { question },
      credentials,
      signal,
    },
    (payload) => msdAnswerSchema.parse(payload),
  );
}
