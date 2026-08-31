"use client";

/**
 * Messages and notifications — I12, the last MVP-1 slice with no browser surface.
 *
 * 🔴 EIGHT ENDPOINTS, ZERO CONTROLS, SINCE SLICE 7.
 *
 * The API has shipped channels, threads, messages, `#reference` and `@mention`
 * resolution, message→task promotion and notifications for weeks. Nothing in
 * `apps/web` called any of it, and the sidebar entry for "Messages" pointed at
 * a route that did not exist — held back by `isAvailable`, which is exactly
 * what that gate is for. *A route with no caller is the same defect as a table
 * with no writer.*
 *
 * 🔴 WHAT THE SERVER RESOLVED IS SHOWN BACK, AND THAT IS THE POINT OF THE
 * POST CONFIRMATION.
 *
 * Posting a message returns `links` (the `#F008` codes it matched) and
 * `mentions` (each `@handle`, and **whether that person was actually
 * notified**). A mention resolves to a real person who is NOT a member of this
 * channel without notifying them — `notified: false`. A screen that hides that
 * tells the author their message reached somebody it did not, which is worse
 * than showing nothing at all.
 *
 * ⚠️ NO DEMONSTRATION FALLBACK. `LiveOnlyPage`, not `DataPage`. Invented
 * conversation between named colleagues would be indistinguishable from real
 * discussion in screenshots, and this screen's whole subject is who said what.
 */

import { useState } from "react";

import { LiveOnlyPage } from "@/components/ui/data-source-banner";
import { serverMessage } from "@/lib/api/client";
import {
  useChannelMessages,
  useChannels,
  useMessagingWrites,
  useNotifications,
} from "@/lib/api/hooks";
import type { Channel, Notification, PostedMessage } from "@/lib/api/messaging";
import { formatInstant } from "@/lib/format/date";
import { permits, usePermissions } from "@/lib/permissions";

const BUTTON =
  "rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 " +
  "disabled:cursor-not-allowed disabled:bg-slate-300";
const SECONDARY =
  "rounded border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-800 " +
  "hover:bg-slate-100 disabled:cursor-not-allowed disabled:text-slate-500";
const INPUT =
  "mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm text-slate-900 " +
  "focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

/** What a channel is called when it has no title of its own. */
function channelLabel(channel: Channel): string {
  if (channel.name) return channel.name;
  if (channel.channel_type === "direct") return "Direct message";
  if (channel.entity_type) return `Discussion — ${channel.entity_type}`;
  return "Channel";
}

export default function MessagesPage() {
  const [openId, setOpenId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [unreadOnly, setUnreadOnly] = useState(true);

  const channels = useChannels();
  const messages = useChannelMessages(openId);
  const notifications = useNotifications(unreadOnly);
  const writes = useMessagingWrites(openId);

  // A mirror of the server's gate, and cosmetic like every mirror here: the
  // route requires `project.edit` and is authoritative. This only avoids
  // offering a control that would be refused.
  const mayPromote = permits(usePermissions(), "project.edit");

  const rows = channels.data ?? [];

  return (
    <LiveOnlyPage
      title="Messages"
      lede="Project channels, record discussions and direct messages — and the
            notifications they raise."
      unavailable={channels.unavailable}
      notInvented="conversations between named colleagues"
    >
      {channels.error && (
        <p role="alert" className="mb-4 text-sm text-rose-700">
          ✕ {serverMessage(channels.error)}
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-[18rem_1fr]">
        {/* ── channels ─────────────────────────────────────────────── */}
        <section aria-labelledby="channels-heading">
          <h2 id="channels-heading" className="text-sm font-semibold text-slate-900">
            Channels{" "}
            <span className="font-normal text-slate-600">({rows.length})</span>
          </h2>

          {channels.isLoading && <p className="mt-2 text-sm text-slate-600">Loading…</p>}

          {!channels.isLoading && rows.length === 0 && (
            <p className="mt-2 text-sm text-slate-600">
              No channels yet. A project channel is opened with its project, and a
              record&rsquo;s discussion thread is opened the first time somebody
              discusses it.
            </p>
          )}

          <ul className="mt-2 space-y-1">
            {rows.map((channel) => (
              <li key={channel.id}>
                <button
                  type="button"
                  onClick={() => {
                    setOpenId(channel.id);
                    setDraft("");
                  }}
                  aria-current={openId === channel.id ? "true" : undefined}
                  className={
                    "w-full rounded border px-3 py-2 text-left text-sm " +
                    (openId === channel.id
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-200 text-slate-800 hover:bg-slate-50")
                  }
                >
                  <span className="font-medium">{channelLabel(channel)}</span>
                  <span
                    className={
                      "ml-2 text-xs " +
                      (openId === channel.id ? "text-slate-200" : "text-slate-600")
                    }
                  >
                    {channel.channel_type} · {channel.message_count}{" "}
                    {channel.message_count === 1 ? "message" : "messages"}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>

        {/* ── the open channel ─────────────────────────────────────── */}
        <section aria-labelledby="messages-heading">
          <h2 id="messages-heading" className="text-sm font-semibold text-slate-900">
            {openId === null
              ? "Choose a channel"
              : channelLabel(rows.find((c) => c.id === openId) ?? ({} as Channel))}
          </h2>

          {openId === null && (
            <p className="mt-2 text-sm text-slate-600">
              Select a channel to read it and post to it.
            </p>
          )}

          {openId !== null && (
            <>
              {messages.isLoading && (
                <p className="mt-2 text-sm text-slate-600">Loading messages…</p>
              )}
              {messages.error && (
                <p role="alert" className="mt-2 text-sm text-rose-700">
                  ✕ {serverMessage(messages.error)}
                </p>
              )}

              <ul className="mt-3 space-y-3">
                {(messages.data ?? []).map((message) => (
                  <li
                    key={message.id}
                    className="rounded border border-slate-200 bg-white p-3"
                  >
                    <p className="text-xs text-slate-600">
                      <span className="font-medium text-slate-900">
                        {message.author_name}
                      </span>{" "}
                      · {formatInstant(message.posted_at)}
                      {message.edited_at && " · edited"}
                    </p>

                    {/* 🔴 A DELETED MESSAGE IS NOT REMOVED, IT IS MARKED.
                        `is_deleted` rows still come back, and rendering the body
                        anyway would defeat the deletion; rendering nothing at all
                        would hide that a message ever existed, which a
                        conversation's participants can see happened. */}
                    {message.is_deleted ? (
                      <p className="mt-1 text-sm italic text-slate-500">
                        This message was deleted.
                      </p>
                    ) : (
                      <p className="mt-1 whitespace-pre-wrap text-sm text-slate-900">
                        {message.body}
                      </p>
                    )}

                    {mayPromote && !message.is_deleted && (
                      <PromoteControl
                        messageId={message.id}
                        writes={writes}
                        defaultTitle={message.body.slice(0, 80)}
                      />
                    )}
                  </li>
                ))}
              </ul>

              {(messages.data ?? []).length === 0 && !messages.isLoading && (
                <p className="mt-2 text-sm text-slate-600">
                  Nothing has been said in this channel yet.
                </p>
              )}

              <form
                className="mt-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  const body = draft.trim();
                  if (body.length > 0) writes.post(body, () => setDraft(""));
                }}
              >
                <label className="block text-xs font-medium text-slate-700">
                  Post a message
                  <textarea
                    className={INPUT}
                    rows={3}
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    placeholder="Use #F008 to reference a record and @name to mention someone."
                  />
                </label>
                <button type="submit" className={`${BUTTON} mt-2`} disabled={writes.isPending}>
                  {writes.isPending ? "Posting…" : "Post"}
                </button>
              </form>

              {writes.error && (
                <p role="alert" className="mt-2 text-sm text-rose-700">
                  ✕ {serverMessage(writes.error)}
                </p>
              )}
              {writes.lastAction && !writes.error && (
                <p role="status" className="mt-2 text-sm text-slate-700">
                  {writes.lastAction}
                </p>
              )}

              <ResolvedSummary posted={writes.lastPosted} />
            </>
          )}
        </section>
      </div>

      {/* ── notifications ──────────────────────────────────────────── */}
      <section aria-labelledby="notifications-heading" className="mt-8">
        <div className="flex flex-wrap items-baseline gap-3">
          <h2 id="notifications-heading" className="text-sm font-semibold text-slate-900">
            Notifications
          </h2>
          <label className="text-xs text-slate-700">
            <input
              type="checkbox"
              className="mr-1.5"
              checked={unreadOnly}
              onChange={(event) => setUnreadOnly(event.target.checked)}
            />
            Unread only
          </label>
        </div>

        {notifications.isLoading && (
          <p className="mt-2 text-sm text-slate-600">Loading notifications…</p>
        )}
        {(notifications.data ?? []).length === 0 && !notifications.isLoading && (
          <p className="mt-2 text-sm text-slate-600">
            {unreadOnly ? "Nothing unread." : "No notifications."}
          </p>
        )}

        <ul className="mt-2 space-y-2">
          {(notifications.data ?? []).map((notification) => (
            <NotificationRow
              key={notification.id}
              notification={notification}
              onRead={() => writes.markRead(notification.id)}
            />
          ))}
        </ul>
      </section>
    </LiveOnlyPage>
  );
}

/**
 * What the server resolved out of the body just posted.
 *
 * 🔴 `notified: false` IS RENDERED, AND IN WORDS. A mention can resolve to a
 * real person who is not in this channel — the handle is right and nobody was
 * told. Icon + text, never colour alone (§11).
 */
function ResolvedSummary({ posted }: { posted: PostedMessage | undefined }) {
  const value = posted;
  if (!value) return null;
  if (value.links.length === 0 && value.mentions.length === 0) return null;

  return (
    <div
      className="mt-3 rounded border border-slate-200 bg-slate-50 p-3 text-xs"
      data-testid="resolved-summary"
    >
      {value.links.length > 0 && (
        <p className="text-slate-800">
          Linked:{" "}
          {value.links.map((link, i) => (
            <span key={link.code}>
              {i > 0 ? ", " : ""}
              <span className="font-mono">{link.code}</span>{" "}
              {link.entity_id ? (
                <span className="text-slate-600">({link.entity_type})</span>
              ) : (
                /* A code that matched nothing is recorded as written, so that
                   "why did my link not work?" stays answerable. */
                <span className="text-amber-900">! matched no record</span>
              )}
            </span>
          ))}
        </p>
      )}
      {value.mentions.length > 0 && (
        <p className="mt-1 text-slate-800">
          Mentioned:{" "}
          {value.mentions.map((mention, i) => (
            <span key={mention.handle}>
              {i > 0 ? ", " : ""}
              <span className="font-mono">@{mention.handle}</span>{" "}
              {mention.notified ? (
                <span className="text-slate-600">✓ notified</span>
              ) : (
                <span className="text-amber-900">
                  ! not notified — not a member of this channel
                </span>
              )}
            </span>
          ))}
        </p>
      )}
    </div>
  );
}

function NotificationRow({
  notification,
  onRead,
}: {
  notification: Notification;
  onRead: () => void;
}) {
  const unread = notification.read_at === null;
  return (
    <li
      className={
        "rounded border p-3 " +
        (unread ? "border-slate-300 bg-white" : "border-slate-200 bg-slate-50")
      }
    >
      <div className="flex flex-wrap items-baseline gap-2">
        {/* Icon + word + colour, never colour alone. An actionable notification
            asks the reader to DO something; the two must not look identical. */}
        {notification.is_actionable && (
          <span className="rounded bg-amber-200 px-1.5 py-0.5 text-[10px] font-medium text-amber-900">
            ! Action required
          </span>
        )}
        <span className="flex-1 text-sm font-medium text-slate-900">
          {notification.title}
        </span>
        <span className="text-xs text-slate-600">
          {formatInstant(notification.created_at)}
        </span>
        {unread ? (
          <button type="button" className={SECONDARY} onClick={onRead}>
            Mark read
          </button>
        ) : (
          <span className="text-xs text-slate-500">✓ read</span>
        )}
      </div>
      {notification.body && (
        <p className="mt-1 text-sm text-slate-700">{notification.body}</p>
      )}
    </li>
  );
}

function PromoteControl({
  messageId,
  writes,
  defaultTitle,
}: {
  messageId: string;
  writes: ReturnType<typeof useMessagingWrites>;
  defaultTitle: string;
}) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState(defaultTitle);

  if (!open) {
    return (
      <button type="button" className={`${SECONDARY} mt-2`} onClick={() => setOpen(true)}>
        Promote to a task →
      </button>
    );
  }

  return (
    <form
      className="mt-2 rounded border border-slate-200 bg-slate-50 p-2"
      onSubmit={(event) => {
        event.preventDefault();
        const trimmed = title.trim();
        if (trimmed.length === 0) return;
        writes.promote(messageId, { task_type: "follow_up", title: trimmed }, () =>
          setOpen(false),
        );
      }}
    >
      <label className="block text-xs font-medium text-slate-700">
        Task title
        <input
          className={INPUT}
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          required
        />
      </label>
      <p className="mt-1 text-xs text-slate-600">
        This creates a controlled record in My Work. Discussion becomes an
        authoritative record only by this explicit act.
      </p>
      <div className="mt-2 flex gap-2">
        <button type="submit" className={BUTTON} disabled={writes.isPending}>
          Create task
        </button>
        <button type="button" className={SECONDARY} onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </form>
  );
}
