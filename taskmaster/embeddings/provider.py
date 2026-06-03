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
from typing import Iterable

import numpy as np


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
    def embed(self, texts: list[str]) -> np.ndarray:
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

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.zeros((len(texts), 0), dtype=np.float32)


def _is_semantic_installed() -> bool:
    try:
        import sentence_transformers  # noqa: F401
        import faiss  # noqa: F401
        return True
    except Exception:
        return False


def _make_sentence_transformer_provider() -> EmbeddingProvider:
    from ._sentence_transformer_provider import SentenceTransformerProvider
    return SentenceTransformerProvider()


def get_default_provider() -> EmbeddingProvider:
    """Return the best available provider for the current environment."""
    if os.environ.get("TASKMASTER_EMBEDDINGS") == "null":
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
