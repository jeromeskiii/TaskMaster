"""OpenAI embedding provider.

Activated when ``OPENAI_API_KEY`` is set and the user installs the
``openai`` extra. The SDK client is created on first call to
:meth:`embed`.
"""

from __future__ import annotations

import os
from typing import Any

import numpy as np

from .provider import EmbeddingProvider

_DEFAULT_MODEL = "text-embedding-3-small"


class OpenAIProvider(EmbeddingProvider):
    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        self._model_name = model
        self._client: Any | None = None

    @property
    def name(self) -> str:
        return "openai"

    @property
    def model_id(self) -> str:
        return f"openai/{self._model_name}"

    @property
    def dim(self) -> int:
        # text-embedding-3-small -> 1536; text-embedding-3-large -> 3072
        return {"text-embedding-3-small": 1536, "text-embedding-3-large": 3072}.get(
            self._model_name, 1536
        )

    def _ensure_client(self) -> None:
        if self._client is None:
            import openai
            self._client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    def embed(self, texts: list[str]) -> np.ndarray:
        self._ensure_client()
        assert self._client is not None
        response = self._client.embeddings.create(model=self._model_name, input=list(texts))
        matrix = np.asarray([item.embedding for item in response.data], dtype=np.float32)
        # L2-normalize for cosine via inner product.
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms
