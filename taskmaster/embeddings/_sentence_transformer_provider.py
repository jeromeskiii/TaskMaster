"""Local SentenceTransformer-backed embedding provider.

The model is loaded lazily on first call to :meth:`embed` so that
importing this module is cheap and CI environments without network
access can still run unit tests that use :class:`NullProvider`.
"""

from __future__ import annotations

import os
from typing import Any

import numpy as np

from .provider import EmbeddingProvider

_DEFAULT_MODEL = os.environ.get("TASKMASTER_EMBED_MODEL", "all-MiniLM-L6-v2")


class SentenceTransformerProvider(EmbeddingProvider):
    def __init__(self, model_name: str = _DEFAULT_MODEL) -> None:
        self._model_name = model_name
        self._model: Any | None = None

    @property
    def name(self) -> str:
        return "sentence-transformers"

    @property
    def model_id(self) -> str:
        return f"sentence-transformers/{self._model_name}"

    @property
    def dim(self) -> int:
        self._ensure_loaded()
        assert self._model is not None
        get_dim = getattr(self._model, "get_embedding_dimension", None) or self._model.get_sentence_embedding_dimension
        return int(get_dim())

    def _ensure_loaded(self) -> None:
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)

    def embed(self, texts: list[str]) -> np.ndarray:
        self._ensure_loaded()
        assert self._model is not None
        vectors = self._model.encode(
            list(texts),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)
