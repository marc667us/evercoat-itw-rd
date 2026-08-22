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

import functools
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

# \w with UNICODE, not [a-z0-9]. The ASCII class silently tokenised a
# Cyrillic, Greek or CJK paragraph to NOTHING, and an empty token list
# raises -- so ingesting a non-English document failed the whole document
# mid-loop, and a question in those scripts returned [] with no error at
# all. Accented Latin degraded more quietly still: "Adhäsion" split into
# "adh" and "sion", two tokens that match nothing a reader would expect.
#
# ⚠️ THIS DOES NOT MAKE CJK WORK PROPERLY. Chinese and Japanese are not
# space-delimited, so a sentence becomes one long token and matches only an
# identical one. It converts a hard failure into honest poor recall, which
# is the same bargain the lexical default makes everywhere else. Real CJK
# retrieval needs the neural embedder.
_WORD = re.compile(r"\w+", re.UNICODE)


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

    # 🔴 AN INSTANCE ATTRIBUTE, NOT A CLASS CONSTANT, AND THAT IS THE WHOLE
    # POINT. It was a constant, and Codex found what that costs: the
    # constructor takes `model_name`, so constructing this with any other
    # 384-dim model labelled its vectors `all-MiniLM-L6-v2`. A later retrieval
    # with the REAL MiniLM then matched on `embedder_name`, passed the guard,
    # and ranked by cosine distance between two different models' vectors --
    # which does not raise, returns rows, and is silently meaningless.
    #
    # That is exactly the failure `embedder_name` was added an hour earlier to
    # make impossible: a name that is a literal rather than a measurement
    # cannot disagree with reality loudly enough to be noticed.
    name = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        # The name RECORDED with every vector is the model actually loaded,
        # NORMALISED. HuggingFace resolves "all-MiniLM-L6-v2" and
        # "sentence-transformers/all-MiniLM-L6-v2" to the same weights, so
        # without this the identical model could be stored under two names --
        # and `retrieve()` filters on an exact match, which would make the
        # whole existing index INVISIBLE. Zero results, for every question, with
        # no error: precisely the silent failure `embedder_name` exists to stop.
        self.name = _canonical_model_id(model_name)
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - exercised by absence
            raise EmbeddingUnavailableError(
                "sentence-transformers is not installed; the lexical embedder "
                "is in use and recall is word-overlap only"
            ) from exc

        # 🔴 NOT JUST ImportError. The library imports fine and then fails to
        # LOAD: weights not cached and no network (the ordinary hermetic
        # container and CI case) raises OSError or a huggingface validation
        # error, not ImportError. Only ImportError was translated, so
        # `build_embedder`'s documented fallback never ran -- the exception
        # escaped it, escaped `search_knowledge`, and became a 500 on every
        # question. A fallback that only handles the failure you thought of is
        # not a fallback.
        try:
            self._model = SentenceTransformer(model_name)
        except EmbeddingUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - needs a broken model cache
            raise EmbeddingUnavailableError(
                f"sentence-transformers could not load {model_name!r}: {exc}"
            ) from exc

    def embed(self, text: str) -> list[float]:
        vector = [float(v) for v in self._model.encode(text, normalize_embeddings=True)]
        # The column is vector(384). A 768-dim model would otherwise surface as
        # a pgvector "different vector dimensions" error at INSERT time, far
        # from the choice that caused it, and would not trigger the fallback.
        if len(vector) != DIMENSIONS:
            raise EmbeddingUnavailableError(
                f"{self.name} produces {len(vector)}-dimensional vectors; the "
                f"knowledge.chunks column is vector({DIMENSIONS})"
            )
        return vector


def _canonical_model_id(model_name: str) -> str:
    """One name per set of weights.

    `sentence-transformers/` is the default namespace HuggingFace fills in, so
    the bare id and the qualified id are the same model. Stored as two
    different strings they would partition one index into two halves that
    cannot see each other.
    """
    return model_name.removeprefix("sentence-transformers/")


@functools.lru_cache(maxsize=2)
def build_embedder(*, prefer_neural: bool = True) -> EmbeddingPort:
    """The best embedder available, and it says which one it chose.

    ⚠️ CACHED, AND IT HAS TO BE. `search_knowledge` calls this once per
    question. Uncached, every question asked of a host with
    sentence-transformers installed constructed a fresh `SentenceTransformer`
    -- ~90 MB of weights read from disk and a new torch model allocated, on the
    1.4 GB-free host this module's header is about. The lexical default is
    cheap enough that the cost was invisible in exactly the configuration we
    test in and ruinous in the one we are aiming at.

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
