"use client";

/**
 * MSD — the Material Science & Development Assistant, as a side panel.
 *
 * Concept Note §33: *"MSD should be accessible through a persistent but
 * unobtrusive chatbot control within the application. Opening MSD should
 * display a conversational side panel … containing the current technical
 * context."*
 *
 * 🔴 THREE RULES ARE STRUCTURAL HERE, NOT COSMETIC.
 *
 * 1. **Every answer carries its label.** §7 requires AI output to be
 *    marked "AI-generated recommendation — requires technical review".
 *    The disclaimer is a REQUIRED field on the parsed response
 *    (`lib/api/msd.ts`) and is rendered from that field — never from a
 *    constant in this file, which could drift from what the server
 *    actually stored, and never conditionally.
 *
 * 2. **Evidence is shown, not summarised.** §34: responses show the
 *    records used. A confident answer with no visible sources is the
 *    thing this product exists not to produce.
 *
 * 3. **It is a panel, not a page.** A chemist asks MSD *about what they
 *    are looking at*. Navigating away to a chat screen loses the context
 *    that makes the question worth asking.
 *
 * 🔴 THE CONVERSATION IS RESUMED, NOT RESTARTED — AND IT ALWAYS COULD HAVE
 * BEEN.
 *
 * This panel used to hold its thread id in a `useRef` and its exchanges in
 * component state, so closing the panel or reloading the page began an empty
 * conversation. Meanwhile `ai.msd_threads` and `ai.msd_turns` were faithfully
 * recording every exchange, and `GET /threads` and `GET /threads/{id}/turns`
 * existed to read them back — with **no caller anywhere in the application**.
 * The assistant appeared to have no memory while the memory existed and was
 * simply unreachable: a route with no caller, showing up as a product defect
 * a user would describe as "it forgets everything".
 *
 * On open, the panel now adopts the caller's most recent thread and hydrates
 * its history. "New conversation" is an explicit control, because starting a
 * fresh thread is a choice rather than an accident of navigation.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { serverMessage } from "@/lib/api/client";
import { useSession } from "@/lib/api/session";
import {
  askMsd,
  fetchThreads,
  fetchTurns,
  openThread,
  type MsdAnswer,
  type MsdTurn,
} from "@/lib/api/msd";

interface Exchange {
  readonly question: string;
  readonly answer: MsdAnswer | null;
  readonly error: string | null;
}

/**
 * Stored turns, folded back into question/answer pairs.
 *
 * A `user` turn opens an exchange; the `assistant` turn that follows closes
 * it. An assistant turn with no preceding question — which the schema permits
 * even if the service does not produce it — becomes its own exchange with an
 * empty question rather than being attached to an unrelated one or dropped.
 * Silently discarding a stored AI answer would make the history disagree with
 * the audit record.
 */
function pairTurns(turns: readonly MsdTurn[]): Exchange[] {
  const ordered = [...turns].sort((a, b) => a.turn_number - b.turn_number);
  const out: Exchange[] = [];

  for (const turn of ordered) {
    if (turn.role === "user") {
      out.push({ question: turn.body, answer: null, error: null });
      continue;
    }

    // 🔴 NO FALLBACK. THE LABEL IS THE RECORD'S OR THERE IS NO ANSWER.
    //
    // This used to read `turn.disclaimer ?? "AI-generated recommendation …"`
    // under a comment claiming it never used a constant. Codex caught the
    // contradiction. Substituting the text would make an unlabelled AI answer
    // look exactly like a labelled one — the single distinction §7 exists to
    // protect — so a turn that somehow lacks its label is surfaced as an
    // error and its body is NOT rendered. `msdTurnSchema` already refuses
    // such a row, so this is the second of two locks rather than the first.
    // Bound to a local so TypeScript actually narrows it. `(x ?? "").trim()`
    // reads as a guard and narrows nothing — the Supervisor caught the build
    // breaking on exactly that, which is the useful kind of failure: the
    // compiler refusing to let an unlabelled answer through.
    const label = turn.disclaimer;
    if (label === null || label.trim() === "") {
      out.push({
        question: "",
        answer: null,
        error:
          "A stored assistant turn is missing the label it was recorded with, " +
          "so it is not shown. AI output is never displayed unlabelled.",
      });
      continue;
    }

    const answer: MsdAnswer = {
      turn_id: turn.id,
      body: turn.body,
      // The record's own label, and nothing else.
      disclaimer: label,
      // Not stored per turn. `intent`, `href` and `suggestions` shape the LIVE
      // response's follow-up controls; replaying them from a past conversation
      // would offer navigation decided for a question asked hours ago.
      intent: "history",
      href: null,
      suggestions: [],
      evidence: turn.evidence,
    };

    const open = out.at(-1);
    if (open !== undefined && open.answer === null && open.error === null) {
      out[out.length - 1] = { ...open, answer };
    } else {
      out.push({ question: "", answer, error: null });
    }
  }

  return out;
}

export function MsdPanel({ onClose }: { onClose: () => void }) {
  const session = useSession();
  const [question, setQuestion] = useState("");
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [busy, setBusy] = useState(false);
  const [restoring, setRestoring] = useState(true);
  const threadId = useRef<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  // Focus moves INTO the panel when it opens. A dialog that opens behind
  // the keyboard user's focus is a dialog they cannot find.
  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  /**
   * Adopt the most recent thread and replay it.
   *
   * 🔴 THE TURNS ARE PAIRED BACK INTO EXCHANGES RATHER THAN LISTED FLAT. The
   * server stores one row per turn — a `user` turn then an `assistant` turn —
   * and this panel's unit is the exchange. Rendering the rows flat would put a
   * question and its answer side by side as two equal blocks, and an assistant
   * turn separated from its question is exactly the shape in which an
   * AI-generated sentence gets quoted as if it were a record.
   *
   * ⚠️ A REPLAYED ANSWER IS STILL AN AI ANSWER AND KEEPS ITS LABEL. The
   * disclaimer is read from the stored turn, never supplied here — a history
   * view that dropped the label would be the one place §7 did not hold.
   *
   * Failure is SILENT and leaves an empty panel, deliberately: a person
   * opening the assistant to ask a question does not need an error about a
   * conversation they had yesterday. The ask path reports its own failures.
   */
  useEffect(() => {
    if (session.status !== "authenticated") {
      setRestoring(false);
      return;
    }
    let cancelled = false;
    const controller = new AbortController();

    void (async () => {
      try {
        const threads = await fetchThreads(session.credentials, controller.signal);
        // `list_threads` orders newest first; the caller's current
        // conversation is the one they were last having.
        const [latest] = threads;
        if (latest === undefined || cancelled) return;
        const turns = await fetchTurns(
          session.credentials,
          latest.id,
          controller.signal,
        );
        if (cancelled) return;
        threadId.current = latest.id;
        setExchanges(pairTurns(turns));
      } catch {
        // See the note above.
      } finally {
        if (!cancelled) setRestoring(false);
      }
    })();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [session]);

  // Escape closes it, which every dialog is expected to do.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const ask = useCallback(
    async (text: string) => {
      const asked = text.trim();
      if (!asked || busy) return;
      if (session.status !== "authenticated") {
        setExchanges((prior) => [
          ...prior,
          {
            question: asked,
            answer: null,
            error:
              "MSD needs a signed-in session. It answers only from records " +
              "you personally have access to, so there is no anonymous mode.",
          },
        ]);
        setQuestion("");
        return;
      }

      setBusy(true);
      setQuestion("");
      try {
        if (threadId.current === null) {
          const thread = await openThread(
            session.credentials,
            asked.slice(0, 200),
          );
          threadId.current = thread.id;
        }
        const answer = await askMsd(
          session.credentials,
          threadId.current,
          asked,
        );
        setExchanges((prior) => [
          ...prior,
          { question: asked, answer, error: null },
        ]);
      } catch (error) {
        setExchanges((prior) => [
          ...prior,
          {
            question: asked,
            answer: null,
            // `serverMessage`, not `.message` (I98) -- MSD's refusals are the
            // ones most worth reading, because §7's authorization boundary is
            // what produces them and "the API refused this request (403)"
            // does not say a boundary was hit. The non-Error branch keeps its
            // own fallback, which `serverMessage` would replace with
            // `String(error)`.
            error:
              error instanceof Error
                ? serverMessage(error)
                : "MSD could not answer.",
          },
        ]);
      } finally {
        setBusy(false);
        inputRef.current?.focus();
      }
    },
    [busy, session],
  );

  return (
    <aside
      role="dialog"
      aria-modal="false"
      aria-label="MSD — Material Science and Development Assistant"
      className="flex h-full w-full max-w-md flex-col border-l border-slate-200 bg-white"
    >
      <header className="flex items-start gap-2 border-b border-slate-200 px-4 py-3">
        <div className="min-w-0 flex-1">
          <h2
            ref={headingRef}
            tabIndex={-1}
            className="text-sm font-semibold text-slate-900 outline-none"
          >
            MSD
          </h2>
          <p className="text-[11px] leading-snug text-slate-600">
            Material Science &amp; Development Assistant
          </p>
        </div>
        {/*
          Starting a fresh thread is an explicit choice. It used to happen by
          accident on every reload, which is how a conversation with a complete
          server-side record looked like an assistant with amnesia.
        */}
        <button
          type="button"
          onClick={() => {
            threadId.current = null;
            setExchanges([]);
          }}
          disabled={busy || exchanges.length === 0}
          className="rounded px-2 py-1 text-xs text-slate-600 hover:bg-slate-50 hover:text-slate-900 disabled:text-slate-300"
        >
          New
        </button>
        <button
          type="button"
          onClick={onClose}
          className="rounded px-2 py-1 text-xs text-slate-600 hover:bg-slate-50 hover:text-slate-900"
        >
          Close
        </button>
      </header>

      {/* Stated once, at the top, in addition to the per-answer label.
          §7 is about every OUTPUT being labelled; this is about the
          reader knowing what they are talking to before they start. */}
      <div
        role="note"
        aria-label="What MSD can and cannot do"
        className="border-b border-amber-300 bg-amber-50 px-4 py-2 text-[11px] leading-snug text-amber-900"
      >
        <span aria-hidden>⚠ </span>
        MSD answers only from records <strong>you</strong> can already open, and
        it never approves anything, changes a formula, or moves a result from
        yellow to green. Every answer needs technical review.
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3">
        {restoring ? (
          <p className="text-xs text-slate-600">Restoring your conversation…</p>
        ) : exchanges.length === 0 ? (
          <div className="text-xs text-slate-600">
            <p>
              Ask about your work, the records you can see, or how the
              application works.
            </p>
            <ul className="mt-3 space-y-1.5">
              {[
                "What is waiting for me?",
                "What does yellow mean on a test?",
                "Show me the batches on the bench",
                "How do I create a formula revision?",
              ].map((suggestion) => (
                <li key={suggestion}>
                  <button
                    type="button"
                    onClick={() => void ask(suggestion)}
                    className="w-full rounded border border-slate-200 px-2 py-1.5 text-left hover:bg-slate-50"
                  >
                    {suggestion}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <ol className="space-y-4">
            {exchanges.map((exchange, index) => (
              <li key={index} className="space-y-2">
                <p className="text-xs font-medium text-slate-900">
                  {exchange.question}
                </p>

                {exchange.error !== null ? (
                  <div
                    role="alert"
                    className="rounded border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-900"
                  >
                    {exchange.error}
                  </div>
                ) : exchange.answer !== null ? (
                  <div className="rounded border border-slate-200 bg-slate-50 px-3 py-2">
                    <p className="whitespace-pre-line text-xs text-slate-800">
                      {exchange.answer.body}
                    </p>

                    {/* Rendered from the RESPONSE, unconditionally. */}
                    <p className="mt-2 border-t border-slate-200 pt-1.5 text-[10px] font-medium uppercase tracking-wide text-amber-800">
                      <span aria-hidden>⚠ </span>
                      {exchange.answer.disclaimer}
                    </p>

                    {exchange.answer.evidence.length > 0 && (
                      <div className="mt-2">
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                          Evidence — {exchange.answer.evidence.length} record
                          {exchange.answer.evidence.length === 1 ? "" : "s"}
                        </p>
                        <ul className="mt-1 space-y-0.5">
                          {exchange.answer.evidence.map((item) => (
                            <li
                              key={item.entity_id}
                              className="text-[11px] text-slate-700"
                            >
                              <span className="text-slate-500">
                                {item.entity_type.replace(/_/g, " ")}:
                              </span>{" "}
                              {item.label ?? item.entity_id}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/*
                      🔴 `href` WAS PARSED AND NEVER RENDERED.

                      Every intent that has somewhere to go sets it -- my work,
                      formulations, and now the knowledge library -- and
                      `lib/api/msd.ts` has always parsed it. Nothing displayed
                      it, so the field round-tripped from the conductor to the
                      client and was dropped, and the "go here next" step of
                      every answer simply did not exist. Found while checking
                      whether restoring `href="/knowledge"` had accomplished
                      anything; it had not.

                      A plain `<a>`, not a router push: these destinations are
                      real pages and a middle-click or a bookmark should work.
                    */}
                    {exchange.answer.href && (
                      <p className="mt-2">
                        <a
                          href={exchange.answer.href}
                          className="text-[11px] font-medium text-slate-800 underline underline-offset-2 hover:text-slate-950"
                        >
                          Open {exchange.answer.href}
                          <span aria-hidden> →</span>
                        </a>
                      </p>
                    )}

                    {exchange.answer.suggestions.length > 0 && (
                      <ul className="mt-2 space-y-1">
                        {exchange.answer.suggestions.map((suggestion) => (
                          <li key={suggestion}>
                            <button
                              type="button"
                              onClick={() => void ask(suggestion)}
                              className="text-[11px] text-slate-700 underline hover:text-slate-900"
                            >
                              {suggestion}
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ) : null}
              </li>
            ))}
          </ol>
        )}
      </div>

      <form
        className="border-t border-slate-200 p-3"
        onSubmit={(event) => {
          event.preventDefault();
          void ask(question);
        }}
      >
        <label htmlFor="msd-question" className="sr-only">
          Ask MSD a question
        </label>
        <div className="flex gap-2">
          <input
            id="msd-question"
            ref={inputRef}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask MSD…"
            maxLength={2000}
            className="min-w-0 flex-1 rounded border border-slate-300 px-2.5 py-1.5 text-xs text-slate-900 placeholder:text-slate-500"
          />
          <button
            type="submit"
            disabled={busy || question.trim().length === 0}
            className="rounded bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {busy ? "Asking…" : "Ask"}
          </button>
        </div>
      </form>
    </aside>
  );
}
