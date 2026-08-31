/**
 * Messaging and notifications, over HTTP — I12.
 *
 * 🔴 EIGHT ENDPOINTS HAD NO CLIENT AT ALL, AND THAT IS WHY THIS FILE EXISTS.
 *
 * `apps/api/app/api/messaging.py` has shipped channels, threads, messages,
 * `#reference` and `@mention` resolution, message→task promotion and
 * notifications since Slice 7. `apps/web` had no client, no hook and no
 * screen — measured, not assumed: `apps/web/app` contained no `messages` or
 * `notifications` route, and `lib/api` contained no messaging module.
 *
 * *A route with no caller is the same defect as a table with no writer*, and
 * this repository has counted twenty-three of those. This was the last MVP-1
 * slice still in that state.
 *
 * ⚠️ SEVEN OF THE EIGHT ROUTES ARE GATED ON AUTHENTICATION ONLY. Only
 * `POST /messaging/promotion` names a permission (`project.edit`), because
 * promoting a message into a TASK creates a controlled record. Reading and
 * posting in a channel you are a member of is not permission-gated — channel
 * membership and RLS are the boundary, and `list_messages` enforces it in two
 * independent mechanisms (see its docstring; a defect there once let any
 * organization member read a direct channel).
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";

export const channelSchema = z.object({
  id: z.string(),
  /** `project`, `direct` or `thread` — a thread is a record's discussion. */
  channel_type: z.string(),
  /** Null for a direct channel, which is named by its members, not by a title. */
  name: z.string().nullable(),
  project_id: z.string().nullable(),
  /** Set only for a `thread` channel: the record being discussed. */
  entity_type: z.string().nullable(),
  entity_id: z.string().nullable(),
  created_at: z.string(),
  /**
   * Excludes deleted messages. Carried so the list can say "opened and never
   * used" rather than making every row a round trip — the same reasoning
   * `knowledge.documents.chunks` carries.
   */
  message_count: z.number(),
});

export type Channel = z.infer<typeof channelSchema>;

export const messageSchema = z.object({
  id: z.string(),
  body: z.string(),
  author_id: z.string(),
  /**
   * Read from the ORGANIZATION MEMBERSHIP, not from `core.users` — migration
   * 052 took the global identity away from `evercoat_app` entirely.
   */
  author_name: z.string(),
  posted_at: z.string(),
  edited_at: z.string().nullable(),
  is_deleted: z.boolean(),
  reply_to_id: z.string().nullable(),
});

export type Message = z.infer<typeof messageSchema>;

export const notificationSchema = z.object({
  id: z.string(),
  notification_type: z.string(),
  title: z.string(),
  body: z.string().nullable(),
  entity_type: z.string().nullable(),
  entity_id: z.string().nullable(),
  /**
   * Whether this asks the reader to DO something, as opposed to telling them
   * something happened. The screen must not render the two identically.
   */
  is_actionable: z.boolean(),
  /** Null means unread. The API never deletes a notification. */
  read_at: z.string().nullable(),
  created_at: z.string(),
});

export type Notification = z.infer<typeof notificationSchema>;

const channelList = z.array(channelSchema);
const messageList = z.array(messageSchema);
const notificationList = z.array(notificationSchema);

/**
 * What `POST /channels/{id}/messages` actually answers.
 *
 * 🔴 READ OFF THE SERVICE, NOT GUESSED. The first draft of this file invented
 * `{ entity_type, entity_id, reference }` for a link and omitted `mentions`
 * entirely. `_resolve_references` returns `{code, entity_type, entity_id}` and
 * `post_message` returns `{id, links, mentions}`. Zod strips unknown keys, so
 * the omission would have been silent and the WRONG KEY NAME would have made
 * every link render blank -- the shape of the three live-only contract bugs
 * this project hit in one afternoon on 2026-08-29.
 */
const postedMessageSchema = z.object({
  id: z.string(),
  /**
   * The `#F008`-style references the server resolved out of the body. Surfaced
   * so the author can see what was linked rather than guess whether their
   * reference was understood.
   *
   * `entity_id` is nullable: a code that matches nothing is still recorded as
   * having been WRITTEN, which is how "why did my link not work?" stays
   * answerable.
   */
  links: z.array(
    z.object({
      /** The literal code matched, e.g. "F008". */
      code: z.string(),
      entity_type: z.string(),
      entity_id: z.string().nullable(),
    }),
  ),
  /**
   * `@mentions`, and whether each person was actually notified.
   *
   * ⚠️ `notified: false` IS A REAL AND IMPORTANT STATE — the handle resolved to
   * a person who is not a member of this channel, so no notification was sent.
   * A screen that hides it tells the author their message reached somebody it
   * did not.
   */
  mentions: z.array(
    z.object({
      handle: z.string(),
      user_id: z.string(),
      notified: z.boolean(),
    }),
  ),
});

export type PostedMessage = z.infer<typeof postedMessageSchema>;

export function fetchChannels(
  credentials: ApiCredentials,
  signal?: AbortSignal,
): Promise<Channel[]> {
  return apiRequest({ path: "/api/messaging/channels", credentials, signal }, (payload) =>
    channelList.parse(payload),
  );
}

export function fetchMessages(
  credentials: ApiCredentials,
  channelId: string,
  signal?: AbortSignal,
): Promise<Message[]> {
  return apiRequest(
    {
      path: `/api/messaging/channels/${encodeURIComponent(channelId)}/messages`,
      credentials,
      signal,
    },
    (payload) => messageList.parse(payload),
  );
}

export interface PostMessageRequest {
  readonly body: string;
  readonly reply_to_id?: string;
}

export function postMessage(
  credentials: ApiCredentials,
  channelId: string,
  request: PostMessageRequest,
): Promise<PostedMessage> {
  return apiRequest(
    {
      path: `/api/messaging/channels/${encodeURIComponent(channelId)}/messages`,
      method: "POST",
      credentials,
      body: request,
    },
    (payload) => postedMessageSchema.parse(payload),
  );
}

export interface PromoteRequest {
  readonly task_type: string;
  readonly title: string;
  readonly assigned_user_id?: string;
}

/**
 * Promote a message into a controlled record.
 *
 * 🔴 THE ONLY PERMISSION-GATED ROUTE IN THIS MODULE (`project.edit`), because
 * this one leaves a task behind. §7's shape applied to people rather than to
 * AI: informal discussion becomes an authoritative record only by an explicit
 * act, never by being said.
 */
export function promoteMessage(
  credentials: ApiCredentials,
  messageId: string,
  request: PromoteRequest,
): Promise<{ task_id: string; message_id: string }> {
  return apiRequest(
    {
      path: `/api/messaging/messages/${encodeURIComponent(messageId)}/promote`,
      method: "POST",
      credentials,
      body: request,
    },
    // `{task_id, message_id}` -- NOT `{id, task_type}`, which is what this was
    // written as first. Read off `promote_message`'s own return statement.
    (payload) =>
      z.object({ task_id: z.string(), message_id: z.string() }).parse(payload),
  );
}

export function fetchNotifications(
  credentials: ApiCredentials,
  unreadOnly: boolean,
  signal?: AbortSignal,
): Promise<Notification[]> {
  // 🔴 THE QUERY GOES INLINE AFTER `?`, AND NOT IN A NESTED TEMPLATE.
  //
  // This was written as `` `/api/messaging/notifications${query ? `?${query}` :
  // ""}` `` and it broke CI. `tests/e2e/api/serving.spec.ts` reads every
  // `path:` out of this directory with `/path:\s*[`"]([^`"]*)[`"]/` and checks
  // it against the served OpenAPI — and that regex stops at the FIRST backtick,
  // which a nested template puts in the middle of the path. The guard saw
  // `/api/messaging/notifications${query` and correctly reported a route the
  // API does not serve.
  //
  // The guard is right and the code was the unusual shape: every other client
  // here writes the query inline so it splits cleanly at `?`. An empty
  // `URLSearchParams` yields a trailing `?`, which is a no-op.
  const params = new URLSearchParams();
  if (unreadOnly) params.set("unread_only", "true");
  return apiRequest(
    {
      path: `/api/messaging/notifications?${params.toString()}`,
      credentials,
      signal,
    },
    (payload) => notificationList.parse(payload),
  );
}

export function markNotificationRead(
  credentials: ApiCredentials,
  notificationId: string,
): Promise<{ id: string; read_at: string }> {
  return apiRequest(
    {
      path: `/api/messaging/notifications/${encodeURIComponent(notificationId)}/read`,
      method: "POST",
      credentials,
    },
    (payload) => z.object({ id: z.string(), read_at: z.string() }).parse(payload),
  );
}
