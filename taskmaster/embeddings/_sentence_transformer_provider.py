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
_KNOWN_MODEL_DIMS = {
    "all-MiniLM-L6-v2": 384,
    "all-MiniLM-L12-v2": 384,
    "all-mpnet-base-v2": 768,
    "multi-qa-MiniLM-L6-cos-v1": 384,
}


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
        known_dim = _KNOWN_MODEL_DIMS.get(self._model_name)
        if known_dim is not None:
            return known_dim
        model = self._load_model(local_files_only=True)
        if model is None:
            return 0
        get_dim = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
        return int(get_dim())

    def _load_model(self, *, local_files_only: bool) -> Any | None:
        if self._model is not None and not local_files_only:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(self._model_name, local_files_only=local_files_only)
        except Exception:
            return None
        if not local_files_only:
            self._model = model
        return model

    def _ensure_loaded(self) -> None:
        if self._model is None:
            self._model = self._load_model(local_files_only=False)

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
