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
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { useSession } from "@/lib/api/session";
import { askMsd, openThread, type MsdAnswer } from "@/lib/api/msd";

interface Exchange {
  readonly question: string;
  readonly answer: MsdAnswer | null;
  readonly error: string | null;
}

export function MsdPanel({ onClose }: { onClose: () => void }) {
  const session = useSession();
  const [question, setQuestion] = useState("");
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [busy, setBusy] = useState(false);
  const threadId = useRef<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  // Focus moves INTO the panel when it opens. A dialog that opens behind
  // the keyboard user's focus is a dialog they cannot find.
  useEffect(() => {
    headingRef.current?.focus();
  }, []);

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
            error:
              error instanceof Error ? error.message : "MSD could not answer.",
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
        {exchanges.length === 0 ? (
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
