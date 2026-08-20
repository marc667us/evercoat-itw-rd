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
});

export type MsdThread = z.infer<typeof msdThreadSchema>;

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
