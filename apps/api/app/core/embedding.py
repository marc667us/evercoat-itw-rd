"""The port text is turned into a vector through, and what the default is NOT.

🔴 READ THIS BEFORE TRUSTING RECALL.

ADR-013 names **Sentence Transformers / all-MiniLM-L6-v2** for Slice 8. That
model needs PyTorch: roughly 2 GB installed, plus a ~90 MB model download, in
an environment measured at 1.4 GB free and a CI job that installs its
dependencies on every run. It is not installed here.

So the default is `HashingEmbedding`, and it is **lexical, not semantic**. It
places two passages close together when they SHARE WORDS. It does not know
that "adhesion" and "bonding" are related, and it never will — that is what
the neural model is for.

Saying so here, in capitals, is the point. The alternative was to ship a
plausible-looking vector search and let the word "embedding" imply semantic
recall that is not there. This codebase has spent a day finding claims that
were true of one path and false of the system; this is one that would have
been easy to make and hard to notice, because a lexical search returns
*something* for most questions.

WHAT IS STILL REAL
------------------
Everything except the semantics:

  * chunks are stored, retrieved and ranked by vector distance;
  * the authorization boundary is enforced by PostgreSQL BEFORE ranking;
  * the dimensionality is the model's, so swapping the embedder is a class
    change and not a migration;
  * `SentenceTransformerEmbedding` is written and selects automatically when
    the library IS present.

The security property this slice exists to establish is model-independent, and
it is the half that would be expensive to retrofit. The recall quality is the
half that is one `pip install` away.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

__all__ = [
    "DIMENSIONS",
    "EmbeddingPort",
    "EmbeddingUnavailableError",
    "HashingEmbedding",
    "SentenceTransformerEmbedding",
    "build_embedder",
]

# all-MiniLM-L6-v2's width (ADR-013). Fixed here and in the `vector(384)`
# column so the two cannot drift; `test_embedding` asserts they agree.
DIMENSIONS = 384

_WORD = re.compile(r"[a-z0-9]+")


class EmbeddingUnavailableError(RuntimeError):
    """No embedder could be built.

    Raised rather than returning a zero vector. A zero vector is equidistant
    from everything, so a search would return whatever the index happened to
    order first — confident, arbitrary, and indistinguishable from a working
    system. The same reasoning as `MalwareScanUnavailableError`.
    """


class EmbeddingPort(Protocol):
    name: str

    def embed(self, text: str) -> list[float]:
        """A unit-length vector of `DIMENSIONS` floats."""
        ...


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


class HashingEmbedding:
    """Deterministic lexical embedding. NOT semantic. See the module docstring.

    A hashing vectoriser: each token is hashed into a bucket and the vector is
    L2-normalised so cosine distance behaves. Sub-word trigrams are hashed too,
    so "adhesion" and "adhesive" land partly together — morphology, not
    meaning, and the distinction matters.

    Deterministic across processes: `hashlib` rather than Python's `hash()`,
    which is salted per interpreter. A vector written today must still match a
    query embedded tomorrow, or the stored index quietly stops working after a
    restart — a failure with no error message.
    """

    name = "hashing-lexical-v1"

    def __init__(self, dimensions: int = DIMENSIONS) -> None:
        self._dimensions = dimensions

    def _bucket(self, token: str) -> int:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big") % self._dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        tokens = _tokens(text)
        if not tokens:
            # An empty query has no direction. Refusing beats returning a zero
            # vector that would match everything equally.
            raise EmbeddingUnavailableError("cannot embed text with no words in it")

        for token in tokens:
            vector[self._bucket(token)] += 1.0
            # Character trigrams, so related word FORMS land near each other.
            # This is morphology and nothing more -- it does not make the
            # embedding semantic.
            if len(token) > 3:
                for i in range(len(token) - 2):
                    vector[self._bucket(f"#{token[i : i + 3]}")] += 0.35

        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0.0:  # pragma: no cover - unreachable while tokens is non-empty
            raise EmbeddingUnavailableError("embedding collapsed to zero")
        return [v / norm for v in vector]


class SentenceTransformerEmbedding:
    """ADR-013's intended embedder. Used automatically when installed.

    Imported inside `__init__` so the module stays importable without torch,
    and so a missing dependency surfaces when this adapter is CHOSEN rather
    than when the file is read.
    """

    name = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - exercised by absence
            raise EmbeddingUnavailableError(
                "sentence-transformers is not installed; the lexical embedder "
                "is in use and recall is word-overlap only"
            ) from exc
        self._model = SentenceTransformer(model_name)

    def embed(self, text: str) -> list[float]:
        vector = self._model.encode(text, normalize_embeddings=True)
        return [float(v) for v in vector]


def build_embedder(*, prefer_neural: bool = True) -> EmbeddingPort:
    """The best embedder available, and it says which one it chose.

    Falls back rather than failing, because a lexical search that finds
    something is more useful than no knowledge search at all -- and because
    the caller records `embedder_name` alongside every stored vector, so a
    mixed index is detectable rather than silently incoherent.

    🔴 Vectors from two different embedders are NOT comparable. Anything that
    stores a vector must store the name too, and re-embed when it changes.
    """
    if prefer_neural:
        try:
            return SentenceTransformerEmbedding()
        except EmbeddingUnavailableError:
            pass
    return HashingEmbedding()
