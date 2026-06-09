from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from taskmaster.embeddings import EmbeddingProvider
from taskmaster.embeddings.index import EmbeddingIndex


class _StubProvider(EmbeddingProvider):
    """Deterministic fake provider for index tests.

    Each unique text token maps to a unit vector via a stable hash so
    vectors are reproducible across instances. Vectors are L2
    normalized so cosine similarity == inner product.
    """

    @property
    def name(self) -> str:
        return "stub"

    @property
    def model_id(self) -> str:
        return "stub/v1"

    @property
    def dim(self) -> int:
        return 8

    def _token_idx(self, token: str) -> int:
        return int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % self.dim

    def embed(self, texts):
        rows = []
        for t in texts:
            v = np.zeros(self.dim, dtype=np.float32)
            for token in set(t.lower().split()):
                v[self._token_idx(token)] = 1.0
            n = np.linalg.norm(v)
            if n > 0:
                v = v / n
            rows.append(v)
        return np.stack(rows).astype(np.float32)


class _NoDimProvider(_StubProvider):
    @property
    def dim(self) -> int:
        raise AssertionError("build() should use embedded vector width, not provider.dim")

    def embed(self, texts):
        rows = []
        for t in texts:
            v = np.zeros(8, dtype=np.float32)
            for token in set(t.lower().split()):
                v[int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % 8] = 1.0
            n = np.linalg.norm(v)
            if n > 0:
                v = v / n
            rows.append(v)
        return np.stack(rows).astype(np.float32)


def _skill(name: str, body: str) -> dict:
    return {
        "dir": name,
        "path": f"{name}/SKILL.md",
        "frontmatter": {"name": name, "description": f"description {name}", "tags": [name]},
        "frontmatter_valid": True,
        "frontmatter_error": None,
        "body": body,
        "line_count": 1,
        "size_bytes": len(body),
    }


@pytest.fixture
def skills():
    return [
        _skill("postgres", "tune postgres oltp indexes vacuum"),
        _skill("redis", "redis cache eviction ttl"),
        _skill("react", "react component hooks state"),
    ]


def test_index_build_save_load_roundtrip(tmp_path: Path, skills):
    cache_dir = tmp_path / "emb"
    idx = EmbeddingIndex(provider=_StubProvider(), cache_dir=cache_dir)
    idx.build(skills)
    assert idx.count == 3

    # Save (build does it automatically when cache_dir set).
    assert (cache_dir / "index.faiss").exists()
    assert (cache_dir / "manifest.json").exists()

    # Load into a fresh index and confirm we can query.
    idx2 = EmbeddingIndex(provider=_StubProvider(), cache_dir=cache_dir)
    idx2.load()
    assert idx2.count == 3
    hits = idx2.query("postgres index", k=2)
    assert hits
    top_name = hits[0]["dir"]
    assert top_name == "postgres"


def test_index_incremental_add(tmp_path: Path, skills):
    idx = EmbeddingIndex(provider=_StubProvider(), cache_dir=tmp_path / "emb")
    idx.build(skills[:2])
    idx.load()
    idx.add(skills[2])
    assert idx.count == 3
    hits = idx.query("react hooks", k=1)
    assert hits[0]["dir"] == "react"


def test_index_query_returns_score_and_dir(tmp_path: Path, skills):
    idx = EmbeddingIndex(provider=_StubProvider(), cache_dir=tmp_path / "emb")
    idx.build(skills)
    idx.load()
    hits = idx.query("postgres vacuum", k=3)
    assert all("dir" in h and "score" in h for h in hits)
    assert len(hits) == 3


def test_index_build_does_not_depend_on_provider_dim(tmp_path: Path, skills):
    idx = EmbeddingIndex(provider=_NoDimProvider(), cache_dir=tmp_path / "emb")
    idx.build(skills)
    assert idx.count == 3


def test_index_handles_null_provider(tmp_path: Path, skills):
    from taskmaster.embeddings.provider import NullProvider
    idx = EmbeddingIndex(provider=NullProvider(), cache_dir=tmp_path / "emb")
    with pytest.raises(RuntimeError, match="degraded"):
        idx.build(skills)
