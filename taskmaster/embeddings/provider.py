"""Embedding provider abstraction.

Providers convert a list of strings into a 2-D ``numpy.ndarray`` of
shape ``(len(texts), dim)``. Implementations are responsible for any
model download, batching, and cost.

The default provider is the local :class:`SentenceTransformerProvider`
when the ``semantic`` extra is installed; otherwise a
:class:`NullProvider` is returned and TaskMaster operates in
keyword-only "degraded" mode.
"""

from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod
from typing import Any

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore


class EmbeddingProvider(ABC):
    """Convert text to vectors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short provider name (e.g. ``'sentence-transformers'``)."""

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Stable identifier used to namespace the on-disk index cache."""

    @property
    @abstractmethod
    def dim(self) -> int:
        """Vector dimensionality. ``0`` means the provider cannot embed."""

    @abstractmethod
    def embed(self, texts: list[str]) -> Any:
        """Embed a batch of strings. Returns shape ``(n, dim)`` float32."""


class NullProvider(EmbeddingProvider):
    """No-op provider used when no embedding backend is available.

    ``embed()`` returns a ``(n, 0)`` array. Callers detect this shape
    and fall back to keyword-only behavior.
    """

    @property
    def name(self) -> str:
        return "null"

    @property
    def model_id(self) -> str:
        return "null/v0"

    @property
    def dim(self) -> int:
        return 0

    def embed(self, texts: list[str]) -> Any:
        if np is None:
            return [[0.0] * 0] * len(texts)
        return np.zeros((len(texts), 0), dtype=np.float32)


class StubProvider(EmbeddingProvider):
    """Deterministic fake provider for testing.

    Returns a hash-based embedding so that identical texts produce
    identical vectors.  Activate by setting ``TASKMASTER_EMBEDDINGS=stub``.
    Dimension defaults to 4 (override with ``TASKMASTER_STUB_DIM``).
    """

    def __init__(self, dim: int | None = None) -> None:
        self._dim = dim or int(os.environ.get("TASKMASTER_STUB_DIM", "4"))

    @property
    def name(self) -> str:
        return "stub"

    @property
    def model_id(self) -> str:
        return f"stub/d={self._dim}"

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> Any:
        if np is None:
            raise ImportError("StubProvider requires numpy")
        out = np.zeros((len(texts), self._dim), dtype=np.float32)
        for i, t in enumerate(texts):
            seed = int(hashlib.sha256(t.encode()).hexdigest()[:8], 16)
            rng = np.random.RandomState(seed)
            out[i] = rng.randn(self._dim).astype(np.float32)
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        out /= norms
        return out


def _is_semantic_installed() -> bool:
    try:
        import faiss  # noqa: F401
        import sentence_transformers  # noqa: F401
        return True
    except Exception:
        return False


def _make_sentence_transformer_provider() -> EmbeddingProvider:
    from ._sentence_transformer_provider import SentenceTransformerProvider
    return SentenceTransformerProvider()


def get_default_provider() -> EmbeddingProvider:
    """Return the best available provider for the current environment."""
    mode = os.environ.get("TASKMASTER_EMBEDDINGS", "")
    if mode == "stub":
        return StubProvider()
    if mode == "null":
        return NullProvider()
    if _is_semantic_installed():
        try:
            return _make_sentence_transformer_provider()
        except Exception:
            return NullProvider()
    return NullProvider()


def cache_key(provider: EmbeddingProvider) -> str:
    """Stable cache key for the on-disk index, derived from model_id."""
    return hashlib.sha256(provider.model_id.encode("utf-8")).hexdigest()[:16]
