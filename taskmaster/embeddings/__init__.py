"""Embedding providers and vector index for semantic search.

The embedding layer is optional. When the ``semantic`` extra is not
installed, ``get_default_provider()`` returns a :class:`NullProvider`
and the rest of TaskMaster falls back to keyword-only behavior with a
``degraded: true`` flag.
"""

from __future__ import annotations

from .provider import (
    EmbeddingProvider,
    NullProvider,
    StubProvider,
    get_default_provider,
)

_LAZY_NAMES = {
    "OpenAIProvider": "._openai_provider",
    "SentenceTransformerProvider": "._sentence_transformer_provider",
}


def __getattr__(name: str):
    if name in _LAZY_NAMES:
        from importlib import import_module

        module = import_module(_LAZY_NAMES[name], __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_NAMES.keys()))


__all__ = [
    "EmbeddingProvider",
    "NullProvider",
    "OpenAIProvider",
    "SentenceTransformerProvider",
    "StubProvider",
    "get_default_provider",
]
