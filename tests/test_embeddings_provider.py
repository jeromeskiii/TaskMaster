from __future__ import annotations

import numpy as np
import pytest

from taskmaster.embeddings.provider import (
    EmbeddingProvider,
    NullProvider,
    get_default_provider,
)

_SENTENCE_TRANSFORMERS_AVAILABLE = False
try:
    import sentence_transformers  # noqa: F401
    import faiss  # noqa: F401
    import torch  # noqa: F401
    _SENTENCE_TRANSFORMERS_AVAILABLE = True
except Exception:
    pass


def test_null_provider_is_embedding_provider():
    p = NullProvider()
    assert isinstance(p, EmbeddingProvider)


def test_null_provider_name_and_dim():
    p = NullProvider()
    assert p.name == "null"
    assert p.dim == 0
    assert p.model_id == "null/v0"


def test_null_provider_embed_returns_zeros():
    p = NullProvider()
    v = p.embed(["hello world", "second text"])
    assert isinstance(v, np.ndarray)
    assert v.shape == (2, 0)


@pytest.mark.skipif(
    not _SENTENCE_TRANSFORMERS_AVAILABLE,
    reason="sentence-transformers / faiss / torch not available on this platform",
)
def test_get_default_provider_returns_provider():
    p = get_default_provider()
    assert isinstance(p, EmbeddingProvider)
    assert p.model_id  # non-empty


@pytest.mark.skipif(
    not _SENTENCE_TRANSFORMERS_AVAILABLE,
    reason="sentence-transformers / faiss / torch not available on this platform",
)
def test_sentence_transformer_provider_lazy_load():
    from taskmaster.embeddings._sentence_transformer_provider import (
        SentenceTransformerProvider,
    )
    p = SentenceTransformerProvider()
    assert p.name == "sentence-transformers"
    assert p.dim > 0
    assert p.model_id.startswith("sentence-transformers/")


@pytest.mark.skipif(
    not _SENTENCE_TRANSFORMERS_AVAILABLE,
    reason="sentence-transformers / faiss / torch not available on this platform",
)
def test_sentence_transformer_provider_dim_does_not_load_model(monkeypatch):
    from taskmaster.embeddings._sentence_transformer_provider import (
        SentenceTransformerProvider,
    )
    import sentence_transformers

    def _boom(*_args, **_kwargs):
        raise AssertionError("dim() should not load the model")

    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", _boom)

    p = SentenceTransformerProvider()
    assert p.dim == 384


@pytest.mark.skipif(
    not _SENTENCE_TRANSFORMERS_AVAILABLE,
    reason="sentence-transformers / faiss / torch not available on this platform",
)
def test_sentence_transformer_provider_dim_uses_local_only_fallback(monkeypatch):
    from taskmaster.embeddings._sentence_transformer_provider import (
        SentenceTransformerProvider,
    )
    import sentence_transformers

    calls: list[dict[str, object]] = []

    class FakeModel:
        def get_sentence_embedding_dimension(self):
            return 1024

    def fake_sentence_transformer(model_name, **kwargs):
        calls.append({"model_name": model_name, **kwargs})
        assert kwargs.get("local_files_only") is True
        return FakeModel()

    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", fake_sentence_transformer)

    p = SentenceTransformerProvider(model_name="custom-local-model")
    assert p.dim == 1024
    assert calls == [{"model_name": "custom-local-model", "local_files_only": True}]


def test_get_default_provider_fallback_when_semantic_unavailable(monkeypatch):
    monkeypatch.setenv("TASKMASTER_EMBEDDINGS", "null")
    p = get_default_provider()
    assert isinstance(p, NullProvider)
    assert p.model_id == "null/v0"


def test_openai_provider_lazy_load(monkeypatch):
    """OpenAIProvider must not import openai until embed() is called."""
    from taskmaster.embeddings import _openai_provider as mod

    # Ensure the openai import inside embed() hits our fake.
    calls: list[list[str]] = []

    class FakeEmbeddings:
        def create(self, model, input):  # noqa: A002
            calls.append(list(input))
            n = len(input)

            class R:
                def __init__(self, n):
                    self.data = [type("E", (), {"embedding": [0.0] * 4})() for _ in range(n)]
            return R(n)

    class FakeClient:
        def __init__(self, *a, **kw):
            self.embeddings = FakeEmbeddings()

    import sys
    from unittest.mock import MagicMock
    fake_openai = MagicMock()
    fake_openai.OpenAI = FakeClient
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    p = mod.OpenAIProvider(model="text-embedding-3-small")
    assert p.name == "openai"
    assert p.dim == 1536
    assert p.model_id == "openai/text-embedding-3-small"
    v = p.embed(["a", "b"])
    assert v.shape == (2, 4)
    assert calls and calls[0] == ["a", "b"]
