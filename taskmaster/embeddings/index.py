"""Persistent FAISS index over skill embeddings.

The index is keyed by the embedding provider's ``model_id`` and stored
under ``.taskmaster_cache/embeddings/{cache_key}/``. Each skill's
content is hashed (sha256) and recorded in ``manifest.json`` so
subsequent runs can incrementally update only what changed.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .provider import EmbeddingProvider, NullProvider, cache_key
from .text import build_skill_text


@dataclass
class IndexMeta:
    provider: str
    model_id: str
    dim: int
    count: int
    built_at: float
    version: int = 1


@dataclass
class IndexManifest:
    skills: dict[str, dict[str, Any]] = field(default_factory=dict)
    """Map skill dir -> {sha256, mtime}."""

    def update(self, skill_dir: str, sha: str, mtime: float) -> None:
        self.skills[skill_dir] = {"sha256": sha, "mtime": mtime}

    def missing(self, current: dict[str, tuple[str, float]]) -> list[str]:
        return [d for d, (sha, _) in current.items() if d not in self.skills or self.skills[d]["sha256"] != sha]


class EmbeddingIndex:
    def __init__(self, provider: EmbeddingProvider, cache_dir: Path) -> None:
        self._provider = provider
        self._cache_dir = Path(cache_dir)
        self._index = None  # faiss index, lazily imported
        self._meta: IndexMeta | None = None
        self._manifest = IndexManifest()
        self._dir_to_pos: dict[str, int] = {}
        self._loaded = False

    @property
    def count(self) -> int:
        return self._meta.count if self._meta else 0

    def _ensure_faiss(self):
        if self._index is None:
            try:
                import faiss  # type: ignore
            except ImportError as e:
                raise RuntimeError(
                    "faiss-cpu is required for the embedding index. "
                    "Install with: pip install 'taskmaster[semantic]'"
                ) from e
            self._faiss = faiss
            dim = self._provider.dim
            self._index = faiss.IndexFlatIP(dim)
        return self._index

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).digest().hex()

    def _skills_to_texts(self, skills: list[dict[str, Any]]) -> tuple[list[str], dict[str, tuple[str, float]]]:
        texts: list[str] = []
        meta: dict[str, tuple[str, float]] = {}
        for s in skills:
            d = s["dir"]
            text = build_skill_text(s)
            texts.append(text)
            meta[d] = (self._hash(text), float(s.get("size_bytes", 0)))
        return texts, meta

    def build(self, skills: list[dict[str, Any]]) -> None:
        if isinstance(self._provider, NullProvider) or self._provider.dim == 0:
            raise RuntimeError(
                "Cannot build an embedding index in degraded (NullProvider) mode. "
                "Install the 'semantic' extra or set TASKMASTER_EMBEDDINGS=stub for tests."
            )
        texts, meta = self._skills_to_texts(skills)
        vectors = self._provider.embed(texts)
        faiss_index = self._ensure_faiss()
        faiss_index.reset()
        faiss_index.add(vectors)
        self._dir_to_pos = {s["dir"]: i for i, s in enumerate(skills)}
        for d, (sha, _) in meta.items():
            self._manifest.update(d, sha, 0.0)
        self._meta = IndexMeta(
            provider=self._provider.name,
            model_id=self._provider.model_id,
            dim=self._provider.dim,
            count=len(skills),
            built_at=time.time(),
        )
        self._loaded = True
        self.save()

    def add(self, skill: dict[str, Any]) -> None:
        if not self._loaded:
            raise RuntimeError("Index must be loaded before incremental add()")
        text = build_skill_text(skill)
        vector = self._provider.embed([text])
        self._ensure_faiss().add(vector)
        self._dir_to_pos[skill["dir"]] = self._meta.count
        self._manifest.update(skill["dir"], self._hash(text), 0.0)
        self._meta.count += 1
        self.save()

    def save(self) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        assert self._meta is not None
        import faiss  # type: ignore
        faiss.write_index(self._ensure_faiss(), str(self._cache_dir / "index.faiss"))
        (self._cache_dir / "meta.json").write_text(
            json.dumps(self._meta.__dict__, indent=2), encoding="utf-8"
        )
        (self._cache_dir / "manifest.json").write_text(
            json.dumps(self._manifest.skills, indent=2), encoding="utf-8"
        )

    def load(self) -> None:
        import faiss  # type: ignore
        meta_path = self._cache_dir / "meta.json"
        manifest_path = self._cache_dir / "index_path"  # safety: see below
        # Correct path:
        manifest_path = self._cache_dir / "manifest.json"
        if not (self._cache_dir / "index.faiss").exists() or not meta_path.exists():
            raise FileNotFoundError(f"No index at {self._cache_dir}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self._meta = IndexMeta(**meta)
        self._index = faiss.read_index(str(self._cache_dir / "index.faiss"))
        if manifest_path.exists():
            self._manifest.skills = json.loads(manifest_path.read_text(encoding="utf-8"))
        # Reconstruct dir -> pos from manifest order.
        self._dir_to_pos = {d: i for i, d in enumerate(self._manifest.skills.keys())}
        self._loaded = True

    def query(self, text: str, k: int = 5) -> list[dict[str, Any]]:
        if not self._loaded or self._index is None or self._meta is None or self._meta.count == 0:
            return []
        vector = self._provider.embed([text])
        if vector.shape[1] != self._meta.dim:
            return []
        k = min(k, self._meta.count)
        scores, positions = self._index.search(vector, k)
        results: list[dict[str, Any]] = []
        inv_pos = {pos: d for d, pos in self._dir_to_pos.items()}
        for score, pos in zip(scores[0].tolist(), positions[0].tolist()):
            if pos < 0:
                continue
            results.append({"dir": inv_pos.get(pos, f"pos:{pos}"), "score": float(score)})
        return results
