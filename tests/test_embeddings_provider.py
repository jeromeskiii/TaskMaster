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
