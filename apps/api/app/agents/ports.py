"""The port a language model is reached through, and the null one.

🔴 THE MODEL MAY PHRASE. IT MAY NEVER INTRODUCE A FACT.

This is the single most important rule in the agent tier, and it is why
the port's method takes the ANSWER ALREADY COMPOSED and returns only a
rewording of it. There is no method that takes a question and returns an
answer, so there is no seam through which a model could invent a formula
code, a measurement, or a conclusion.

That follows directly from the seven non-negotiable rules:

  1. PostgreSQL owns verified technical facts. AI is never the system of
     record.
  2. Python owns deterministic scientific calculation. "The LLM may CALL
     calculation tools and EXPLAIN results; it must never perform the
     arithmetic."
  3. Physical testing verifies; models only predict.
  4. Humans approve.

A model that generates the answer text from a prompt containing the
records is doing something subtly different from explaining them: it is
producing prose whose claims nobody checked. `verify_evidence_within_boundary`
can prove which RECORDS were cited; nothing can prove a sentence was
entailed by them.

CONSEQUENCE, AND IT IS A FEATURE
--------------------------------
MSD works with **no model at all**. CI has no Ollama, the deployed site
has no API, and the zero-cost rule (§7) forbids depending on a paid one.
So the null implementation is not a stub for tests — it is the supported
configuration, and the model is an optional improvement to wording.
"""

from __future__ import annotations

from typing import Protocol

__all__ = ["LanguageModelPort", "NullLanguageModel"]


class LanguageModelPort(Protocol):
    """Rewords an already-composed answer. Nothing else."""

    def rephrase(self, *, composed: str, question: str) -> str:
        """Return `composed` in more natural prose.

        Implementations MUST NOT add information. A caller is entitled to
        assume every claim in the result was already present in
        `composed`, because that is the only property that makes the
        answer's evidence list honest.

        Any failure — model absent, timeout, refusal — must return
        `composed` unchanged rather than raising. A wording improvement is
        never worth failing a request that already has its answer.
        """
        ...


class NullLanguageModel:
    """No model. Returns the composed answer verbatim.

    The default, and the configuration CI and the deployed site run in.
    """

    def rephrase(self, *, composed: str, question: str) -> str:
        _ = question
        return composed
