/**
 * The knowledge library, over HTTP.
 *
 * WHY `distance` REACHES THE SCREEN
 * ---------------------------------
 * MSD's tool drops anything past a relevance threshold, because MSD QUOTES
 * what it gets back as though it were responsive — a poor match there becomes
 * a confident wrong answer. This client does not, and the screen shows the
 * figure, because a person scanning a ranked list can judge a weak match for
 * themselves and a hidden result they asked for is worse than a visible bad
 * one.
 *
 * ⚠️ AND THE SCREEN MUST NOT IMPLY UNDERSTANDING. Recall is word-overlap
 * unless a neural embedder is installed (`app/core/embedding.py`). Copy that
 * says "matched" or "found" is honest; copy that says the library
 * "understood" the question is not.
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";

export const knowledgeDocumentSchema = z.object({
  id: z.string(),
  title: z.string(),
  source: z.string(),
  classification: z.string(),
  project_id: z.string().nullable(),
  ingested_at: z.string(),
  // Zero means the document is INVISIBLE to retrieval however healthy the row
  // looks. Parsed and surfaced rather than dropped, because "why does the
  // assistant never quote this?" is otherwise unanswerable from the screen.
  chunks: z.number(),
});

export type KnowledgeDocument = z.infer<typeof knowledgeDocumentSchema>;

export const knowledgePassageSchema = z.object({
  content: z.string(),
  title: z.string(),
  source: z.string(),
  document_id: z.string(),
  ordinal: z.number(),
  classification: z.string(),
  distance: z.number(),
});

export type KnowledgePassage = z.infer<typeof knowledgePassageSchema>;

/**
 * I78. The list arrives WITH its total, because the service caps the page at
 * 100 and used to say nothing about it — past that, the oldest documents
 * simply stopped appearing, with no page two and no count. That is the same
 * unanswerable "why is my document not here?" the `chunks` field above exists
 * to prevent, one level up.
 *
 * `total` is not a promise of pagination and there is still no way to reach
 * document 101 from here. It exists so the screen can say how much of the
 * library it is showing, which is the difference between a limit and a silent
 * omission.
 */
const documentPageSchema = z.object({
  documents: z.array(knowledgeDocumentSchema),
  total: z.number(),
  limit: z.number(),
});

export type KnowledgeDocumentPage = z.infer<typeof documentPageSchema>;
const passageList = z.array(knowledgePassageSchema);

const ingestResultSchema = z.object({
  document_id: z.string(),
  chunks: z.number(),
  embedder: z.string(),
});

export type IngestResult = z.infer<typeof ingestResultSchema>;

export function fetchKnowledgeDocuments(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<KnowledgeDocumentPage> {
  return apiRequest(
    { path: "/api/knowledge/documents", credentials, signal },
    (payload) => documentPageSchema.parse(payload),
  );
}

export function searchKnowledge(
  credentials: ApiCredentials,
  query: string,
  signal?: AbortSignal,
): Promise<KnowledgePassage[]> {
  return apiRequest(
    {
      path: `/api/knowledge/search?q=${encodeURIComponent(query)}`,
      credentials,
      signal,
    },
    (payload) => passageList.parse(payload),
  );
}

export interface IngestRequest {
  readonly title: string;
  readonly body: string;
  readonly source: string;
  /**
   * Omitted, not defaulted.
   *
   * The column and the service both default to `DIRECTOR_CONTROLLED` — the
   * CEILING — and sending a default from the browser is how that ceiling
   * quietly becomes whatever the form happened to preselect. Undefined here
   * means "the user did not choose", which the database answers with the most
   * restrictive value.
   */
  readonly classification?: string;
}

export function ingestKnowledgeDocument(
  credentials: ApiCredentials,
  request: IngestRequest,
  signal?: AbortSignal,
): Promise<IngestResult> {
  return apiRequest(
    {
      path: "/api/knowledge/documents",
      method: "POST",
      body: request,
      credentials,
      signal,
    },
    (payload) => ingestResultSchema.parse(payload),
  );
}
