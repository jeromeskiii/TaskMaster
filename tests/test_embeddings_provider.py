from __future__ import annotations

import numpy as np

from taskmaster.embeddings.provider import (
    EmbeddingProvider,
    NullProvider,
    get_default_provider,
)


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


def test_get_default_provider_returns_provider():
    p = get_default_provider()
    assert isinstance(p, EmbeddingProvider)
    assert p.model_id  # non-empty


def test_sentence_transformer_provider_lazy_load():
    from taskmaster.embeddings._sentence_transformer_provider import (
        SentenceTransformerProvider,
    )
    p = SentenceTransformerProvider()
    assert p.name == "sentence-transformers"
    assert p.dim > 0
    assert p.model_id.startswith("sentence-transformers/")


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

    import openai
    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    p = mod.OpenAIProvider(model="text-embedding-3-small")
    assert p.name == "openai"
    assert p.dim == 4
    assert p.model_id == "openai/text-embedding-3-small"
    v = p.embed(["a", "b"])
    assert v.shape == (2, 4)
    assert calls and calls[0] == ["a", "b"]
