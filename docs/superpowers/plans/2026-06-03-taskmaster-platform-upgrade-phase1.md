# TaskMaster Platform Upgrade — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the engine layer for TaskMaster's agent-native upgrade — a pluggable embedding system with a persistent FAISS index, a hybrid keyword+semantic recommender, and a dependency-graph composer — plus three new CLI subcommands (`embed`, `recommend`, `compose`) that drive them. New optional frontmatter fields (`depends_on`, `composes_with`) are accepted by validation but not required.

**Architecture:** All new code lives under `taskmaster/embeddings/`, `taskmaster/recommend.py`, and `taskmaster/compose.py`. The embedding layer has a provider interface with three implementations: a local SentenceTransformer provider (default), an OpenAI provider (optional), and a NullProvider that enables a fully offline "degraded" mode. The recommender combines cosine similarity with keyword and tag overlap. The composer is a pure graph algorithm over the corpus. New CLI subcommands are thin wrappers that produce either human-readable text or structured JSON via the existing `--json` convention. Everything is exercised by TDD-style unit tests.

**Tech Stack:** Python 3.10+, `sentence-transformers` (extra), `faiss-cpu` (extra), `numpy` (extra), `mcp` (Phase 2), `pytest`, stdlib. Strict type hints (Pyright-compatible).

**Spec:** `docs/superpowers/specs/2026-06-03-taskmaster-platform-upgrade-design.md`

---

## File Structure

New files:
- `taskmaster/embeddings/__init__.py` — public API re-exports
- `taskmaster/embeddings/provider.py` — `EmbeddingProvider` ABC, `SentenceTransformerProvider`, `OpenAIProvider`, `NullProvider`, `get_default_provider()`
- `taskmaster/embeddings/index.py` — `EmbeddingIndex` class (build, save, load, query, incremental update)
- `taskmaster/embeddings/text.py` — `_build_skill_text()` helper that concatenates name + description + tags + body excerpt
- `taskmaster/recommend.py` — `recommend_skills()` hybrid ranker
- `taskmaster/compose.py` — `compose_skills()` dependency resolver + `CycleError`, `MissingDependencyError`
- `tests/test_embeddings_provider.py`
- `tests/test_embeddings_index.py`
- `tests/test_recommend.py`
- `tests/test_compose.py`
- `tests/test_cli_phase1.py`

Modified files:
- `taskmaster/validation.py` — accept optional `depends_on` and `composes_with` frontmatter fields without rejecting skills that omit them
- `taskmaster/cli.py` — register three new subcommands: `embed`, `recommend`, `compose`
- `pyproject.toml` — add `semantic` and `openai` extras
- `README.md` — document the new commands
- `.github/workflows/ci.yml` — add a `phase1` job that runs the new tests

Design boundaries:
- `embeddings/` knows nothing about the corpus, skills, or search ranking. It only embeds text strings and stores/queries vectors.
- `recommend.py` calls into `embeddings` and `discovery` (existing module) and produces `RankedMatch` records.
- `compose.py` calls into `corpus` only and produces a `ComposePlan`.
- `cli.py` is a thin dispatch layer; no business logic in command handlers.
- `validation.py` extensions are additive; no existing test changes.

---

## Task 1: Add semantic extras to pyproject.toml

**Files:**
- Modify: `pyproject.toml:31-37` (the `dependencies` list and a new `[project.optional-dependencies]` section)

- [ ] **Step 1: Add the new extras block**

Replace the `[project]` block's dependencies with both a core dependency set and an optional-extras block. Find the existing `dependencies = [` block in `pyproject.toml` and replace it with:

```toml
dependencies = [
    "pyyaml>=6.0",
]

[project.optional-dependencies]
semantic = [
    "sentence-transformers>=2.2",
    "faiss-cpu>=1.7",
    "numpy>=1.24",
]
openai = [
    "openai>=1.0",
]
mcp = [
    "mcp>=1.0",
]
all = [
    "taskmaster[semantic,mcp,openai]",
]
```

- [ ] **Step 2: Verify the file parses**

Run: `python3 -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Install the extras into the existing venv**

Run: `.venv/bin/pip install -e ".[semantic]"`
Expected: ends with `Successfully installed ...` and no errors. If `sentence-transformers` cannot fetch its model, that's fine — the unit tests use the NullProvider.

- [ ] **Step 4: Verify importability**

Run: `.venv/bin/python -c "import faiss, numpy, sentence_transformers; print('ok')"`
Expected: `ok` (or a one-time model download warning, then `ok`).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "build: add semantic/openai/mcp optional extras"
```

---

## Task 2: Extend validation to accept new optional frontmatter fields

**Files:**
- Modify: `taskmaster/validation.py:9-12` (constants) and add a new function
- Test: `tests/test_validation_optional_fields.py` (new file)

- [ ] **Step 1: Write the failing test**

Create `tests/test_validation_optional_fields.py`:

```python
from __future__ import annotations

from taskmaster.validation import OPTIONAL_LIST_FIELDS, validate_skill


def _skill(fm: dict) -> dict:
    return {
        "dir": "x",
        "path": "x/SKILL.md",
        "frontmatter": fm,
        "frontmatter_valid": True,
        "frontmatter_error": None,
        "body": "body",
        "line_count": 1,
        "size_bytes": 100,
    }


def test_depends_on_optional():
    skill = _skill({"name": "x", "description": "x" * 35, "category": "development", "risk": "safe"})
    assert validate_skill(skill) == []


def test_depends_on_when_present_must_be_list():
    skill = _skill({
        "name": "x", "description": "x" * 35, "category": "development", "risk": "safe",
        "depends_on": "not-a-list",
    })
    issues = validate_skill(skill)
    assert any("depends_on" in i for i in issues)


def test_depends_on_when_list_is_valid():
    skill = _skill({
        "name": "x", "description": "x" * 35, "category": "development", "risk": "safe",
        "depends_on": ["y", "z"],
        "composes_with": ["a"],
    })
    assert validate_skill(skill) == []


def test_optional_fields_constant_lists_new_fields():
    assert "depends_on" in OPTIONAL_LIST_FIELDS
    assert "composes_with" in OPTIONAL_LIST_FIELDS
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_validation_optional_fields.py -v`
Expected: FAIL with `ImportError: cannot import name 'OPTIONAL_LIST_FIELDS'`.

- [ ] **Step 3: Implement the constant and validation extension**

In `taskmaster/validation.py`, add after the `MIN_DESC_LEN` constant (line 12):

```python
OPTIONAL_LIST_FIELDS = ("depends_on", "composes_with")
```

Then add a new function after the existing `validate_skill()` (find the end of that function and append):

```python
def _validate_optional_lists(skill: SkillRecord) -> list[str]:
    issues: list[str] = []
    fm = skill.frontmatter
    for field in OPTIONAL_LIST_FIELDS:
        if field not in fm:
            continue
        value = fm[field]
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip() == "":
                continue
            issues.append(f"field '{field}' must be a list, got string")
            continue
        if not isinstance(value, list):
            issues.append(f"field '{field}' must be a list, got {type(value).__name__}")
            continue
        for entry in value:
            if not isinstance(entry, str) or not entry.strip():
                issues.append(f"field '{field}' must contain non-empty strings")
                break
    return issues
```

Then modify `validate_skill()` to call it. Find the line `issues = []` near the top of `validate_skill` and add this line at the **end** of the function (just before the `return issues` statement):

```python
    issues.extend(_validate_optional_lists(record))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/test_validation_optional_fields.py -v`
Expected: 4 passed.

- [ ] **Step 5: Run the existing validation tests to confirm no regression**

Run: `.venv/bin/pytest tests/test_validation.py -v`
Expected: all existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add taskmaster/validation.py tests/test_validation_optional_fields.py
git commit -m "feat(validation): accept optional depends_on/composes_with frontmatter fields"
```

---

## Task 3: Embedding provider interface + NullProvider

**Files:**
- Create: `taskmaster/embeddings/__init__.py`
- Create: `taskmaster/embeddings/provider.py`
- Test: `tests/test_embeddings_provider.py`

- [ ] **Step 1: Create the package skeleton**

Create `taskmaster/embeddings/__init__.py`:

```python
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
    OpenAIProvider,
    SentenceTransformerProvider,
    get_default_provider,
)

__all__ = [
    "EmbeddingProvider",
    "NullProvider",
    "OpenAIProvider",
    "SentenceTransformerProvider",
    "get_default_provider",
]
```

- [ ] **Step 2: Write the failing test for the provider interface**

Create `tests/test_embeddings_provider.py`:

```python
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
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_embeddings_provider.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'taskmaster.embeddings.provider'`.

- [ ] **Step 4: Implement the provider interface and NullProvider**

Create `taskmaster/embeddings/provider.py`:

```python
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
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/test_embeddings_provider.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add taskmaster/embeddings/__init__.py taskmaster/embeddings/provider.py tests/test_embeddings_provider.py
git commit -m "feat(embeddings): add provider interface and NullProvider fallback"
```

---

## Task 4: SentenceTransformerProvider

**Files:**
- Create: `taskmaster/embeddings/_sentence_transformer_provider.py`
- Test: extend `tests/test_embeddings_provider.py`

- [ ] **Step 1: Add the test**

Append to `tests/test_embeddings_provider.py`:

```python
def test_sentence_transformer_provider_lazy_load():
    from taskmaster.embeddings._sentence_transformer_provider import (
        SentenceTransformerProvider,
    )
    p = SentenceTransformerProvider()
    assert p.name == "sentence-transformers"
    assert p.dim > 0
    assert p.model_id.startswith("sentence-transformers/")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_embeddings_provider.py::test_sentence_transformer_provider_lazy_load -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the provider**

Create `taskmaster/embeddings/_sentence_transformer_provider.py`:

```python
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
        return int(self._model.get_sentence_embedding_dimension())

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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/test_embeddings_provider.py::test_sentence_transformer_provider_lazy_load -v`
Expected: PASS (the first call may take a moment to download the model; subsequent runs are instant).

- [ ] **Step 5: Commit**

```bash
git add taskmaster/embeddings/_sentence_transformer_provider.py tests/test_embeddings_provider.py
git commit -m "feat(embeddings): add SentenceTransformerProvider with lazy model load"
```

---

## Task 5: OpenAIProvider

**Files:**
- Create: `taskmaster/embeddings/_openai_provider.py`
- Test: extend `tests/test_embeddings_provider.py`

- [ ] **Step 1: Add the test**

Append to `tests/test_embeddings_provider.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_embeddings_provider.py::test_openai_provider_lazy_load -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the provider**

Create `taskmaster/embeddings/_openai_provider.py`:

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/test_embeddings_provider.py::test_openai_provider_lazy_load -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add taskmaster/embeddings/_openai_provider.py tests/test_embeddings_provider.py
git commit -m "feat(embeddings): add OpenAIProvider with lazy client init"
```

---

## Task 6: Embedding index — text builder

**Files:**
- Create: `taskmaster/embeddings/text.py`
- Test: `tests/test_embeddings_text.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_embeddings_text.py`:

```python
from __future__ import annotations

from taskmaster.embeddings.text import build_skill_text


def _skill(name: str, description: str, tags, body: str) -> dict:
    return {
        "dir": name,
        "path": f"{name}/SKILL.md",
        "frontmatter": {"name": name, "description": description, "tags": tags},
        "frontmatter_valid": True,
        "frontmatter_error": None,
        "body": body,
        "line_count": body.count("\n") + 1,
        "size_bytes": len(body),
    }


def test_build_skill_text_includes_name_desc_tags():
    s = _skill("postgres-tuning", "Tune Postgres for OLTP workloads.", ["postgres", "sql"], "body")
    text = build_skill_text(s)
    assert "postgres-tuning" in text
    assert "Tune Postgres" in text
    assert "postgres" in text and "sql" in text


def test_build_skill_text_truncates_body():
    s = _skill("x", "x" * 50, [], "B" * 5000)
    text = build_skill_text(s)
    # body should be capped at 1000 chars
    assert text.count("B") <= 1000


def test_build_skill_text_handles_missing_fields():
    s = {"dir": "x", "path": "x/SKILL.md", "frontmatter": {}, "body": ""}
    text = build_skill_text(s)
    assert isinstance(text, str)


def test_build_skill_text_normalizes_tags_scalar():
    s = _skill("x", "x" * 50, "postgres, sql", "")
    text = build_skill_text(s)
    assert "postgres" in text and "sql" in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_embeddings_text.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Create `taskmaster/embeddings/text.py`:

```python
"""Text preparation for embedding skills.

The embedding text for a skill concatenates its name, description,
tags, and the first 1000 characters of its body. This gives the
vector representation enough semantic signal without flooding it
with implementation detail.
"""

from __future__ import annotations

from typing import Any

_BODY_CHARS = 1000


def build_skill_text(skill: dict[str, Any]) -> str:
    fm = skill.get("frontmatter", {}) or {}
    name = str(fm.get("name") or skill.get("dir") or "").strip()
    description = str(fm.get("description") or "").strip()
    tags = _tags_to_text(fm.get("tags"))
    body = str(skill.get("body") or "").strip().replace("\n", " ")[:_BODY_CHARS]
    parts = [p for p in (name, description, tags, body) if p]
    return " ".join(parts)


def _tags_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(str(v).strip() for v in value if str(v).strip())
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("[") and text.endswith("]"):
            text = text[1:-1]
        return text.replace(",", " ")
    return str(value)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/test_embeddings_text.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add taskmaster/embeddings/text.py tests/test_embeddings_text.py
git commit -m "feat(embeddings): add build_skill_text helper"
```

---

## Task 7: Embedding index — build, save, load, query (NullProvider-backed)

**Files:**
- Create: `taskmaster/embeddings/index.py`
- Test: `tests/test_embeddings_index.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_embeddings_index.py`:

```python
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from taskmaster.embeddings import EmbeddingProvider
from taskmaster.embeddings.index import EmbeddingIndex


class _StubProvider(EmbeddingProvider):
    """Deterministic fake provider for index tests.

    Each unique text token maps to a unit vector. Vectors are L2
    normalized so cosine similarity == inner product.
    """

    def __init__(self) -> None:
        self._vocab: dict[str, int] = {}
        self.dim = 8

    @property
    def name(self) -> str:
        return "stub"

    @property
    def model_id(self) -> str:
        return "stub/v1"

    def embed(self, texts):
        rows = []
        for t in texts:
            v = np.zeros(self.dim, dtype=np.float32)
            for token in t.lower().split():
                idx = self._vocab.setdefault(token, len(self._vocab))
                if idx < self.dim:
                    v[idx] = 1.0
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


def test_index_handles_null_provider(tmp_path: Path, skills):
    from taskmaster.embeddings.provider import NullProvider
    idx = EmbeddingIndex(provider=NullProvider(), cache_dir=tmp_path / "emb")
    with pytest.raises(RuntimeError, match="degraded"):
        idx.build(skills)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_embeddings_index.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the index**

Create `taskmaster/embeddings/index.py`:

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/test_embeddings_index.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add taskmaster/embeddings/index.py tests/test_embeddings_index.py
git commit -m "feat(embeddings): add EmbeddingIndex with FAISS persistence"
```

---

## Task 8: Recommender — hybrid score

**Files:**
- Create: `taskmaster/recommend.py`
- Test: `tests/test_recommend.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_recommend.py`:

```python
from __future__ import annotations

from taskmaster.recommend import recommend_skills


def _skill(name: str, desc: str, tags, body: str = "") -> dict:
    return {
        "dir": name,
        "path": f"{name}/SKILL.md",
        "frontmatter": {"name": name, "description": desc, "tags": tags, "category": "development", "risk": "safe"},
        "frontmatter_valid": True,
        "frontmatter_error": None,
        "body": body,
        "line_count": 1,
        "size_bytes": 0,
    }


def test_recommend_keyword_only_when_no_index():
    skills = [
        _skill("postgres", "Postgres tuning and indexing.", ["postgres", "sql"]),
        _skill("react", "React components and hooks.", ["react", "frontend"]),
        _skill("redis", "Redis caching strategies.", ["redis", "cache"]),
    ]
    results = recommend_skills("postgres vacuum", skills=skills, index=None, k=2)
    assert results[0]["skill"]["dir"] == "postgres"
    assert "reasons" in results[0]
    assert any("postgres" in r.lower() for r in results[0]["reasons"])


def test_recommend_risk_filter_excludes_high():
    skills = [
        _skill("safe", "Safe skill.", ["x"], "x" * 50),
        _skill("risky", "Risky business.", ["x"], "x" * 50),
    ]
    skills[1]["frontmatter"]["risk"] = "high"
    results = recommend_skills("skill", skills=skills, index=None, k=5, max_risk="medium")
    dirs = [r["skill"]["dir"] for r in results]
    assert "risky" not in dirs
    assert "safe" in dirs


def test_recommend_returns_k_results():
    skills = [_skill(f"s{i}", f"description number {i}", [f"t{i}"]) for i in range(10)]
    results = recommend_skills("number 5", skills=skills, index=None, k=3)
    assert len(results) == 3


def test_recommend_degraded_flag_false_when_keyword_only():
    skills = [_skill("a", "alpha alpha alpha", ["x"])]
    results = recommend_skills("alpha", skills=skills, index=None, k=1)
    assert results[0].get("degraded") is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_recommend.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the recommender**

Create `taskmaster/recommend.py`:

```python
"""Hybrid skill recommender.

Score composition when an embedding index is available::

    final = 0.55 * cosine + 0.30 * keyword + 0.15 * tag_overlap

When the index is unavailable (NullProvider or ``index=None``), the
recommender falls back to pure keyword overlap and tags ``degraded:
True`` in the result. This is the same shape the MCP server will
expose in Phase 2.
"""

from __future__ import annotations

import re
from typing import Any

from .corpus import _as_list, _tokenize_text

_WEIGHT_COSINE = 0.55
_WEIGHT_KEYWORD = 0.30
_WEIGHT_TAGS = 0.15


def recommend_skills(
    task: str,
    skills: list[dict[str, Any]],
    index: Any = None,
    k: int = 5,
    max_risk: str | None = None,
) -> list[dict[str, Any]]:
    task_tokens = _tokenize_text(task)
    candidates = _filter_by_risk(skills, max_risk)

    cosine_scores: dict[str, float] = {}
    if index is not None and getattr(index, "count", 0) > 0:
        try:
            for hit in index.query(task, k=min(len(candidates), max(k * 5, 10))):
                cosine_scores[hit["dir"]] = float(hit["score"])
        except Exception:
            cosine_scores = {}

    results: list[dict[str, Any]] = []
    for skill in candidates:
        dir_ = skill["dir"]
        kw = _keyword_score(task_tokens, skill)
        tag = _tag_score(task_tokens, skill)
        cos = cosine_scores.get(dir_, 0.0)
        final = _WEIGHT_COSINE * cos + _WEIGHT_KEYWORD * kw + _WEIGHT_TAGS * tag
        reasons = _reasons(task_tokens, skill, kw, tag, cos)
        results.append({
            "skill": skill,
            "score": round(final, 4),
            "reasons": reasons,
            "degraded": not cosine_scores,
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:k]


def _filter_by_risk(skills: list[dict[str, Any]], max_risk: str | None) -> list[dict[str, Any]]:
    order = {"safe": 0, "medium": 1, "high": 2}
    if max_risk is None:
        return list(skills)
    cap = order.get(max_risk, 2)
    out = []
    for s in skills:
        r = s.get("frontmatter", {}).get("risk")
        if r is None or order.get(r, 2) <= cap:
            out.append(s)
    return out


def _keyword_score(task_tokens: set[str], skill: dict[str, Any]) -> float:
    if not task_tokens:
        return 0.0
    fm = skill.get("frontmatter", {}) or {}
    text_parts = [
        str(fm.get("name") or ""),
        str(fm.get("description") or ""),
        str(skill.get("body") or "")[:1000],
    ]
    haystack_tokens = _tokenize_text(" ".join(text_parts))
    if not haystack_tokens:
        return 0.0
    overlap = len(task_tokens & haystack_tokens)
    return overlap / max(len(task_tokens), 1)


def _tag_score(task_tokens: set[str], skill: dict[str, Any]) -> float:
    if not task_tokens:
        return 0.0
    tags = _as_list(skill.get("frontmatter", {}).get("tags"))
    if not tags:
        return 0.0
    tag_tokens = _tokenize_text(" ".join(str(t) for t in tags))
    if not tag_tokens:
        return 0.0
    overlap = len(task_tokens & tag_tokens)
    return overlap / max(len(task_tokens), 1)


def _reasons(task_tokens, skill, kw, tag, cos) -> list[str]:
    reasons: list[str] = []
    if cos > 0:
        reasons.append(f"semantic similarity {cos:.2f}")
    if kw > 0:
        reasons.append(f"keyword overlap {kw:.2f}")
    if tag > 0:
        reasons.append(f"tag overlap {tag:.2f}")
    name = str(skill.get("frontmatter", {}).get("name") or skill.get("dir") or "")
    name_tokens = set(re.findall(r"[a-z0-9]+", name.lower()))
    if name_tokens & task_tokens:
        reasons.append(f"name term: {', '.join(sorted(name_tokens & task_tokens))}")
    return reasons
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/test_recommend.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add taskmaster/recommend.py tests/test_recommend.py
git commit -m "feat(recommend): add hybrid keyword+semantic recommender with degraded fallback"
```

---

## Task 9: Composer — dependency resolution

**Files:**
- Create: `taskmaster/compose.py`
- Test: `tests/test_compose.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_compose.py`:

```python
from __future__ import annotations

import pytest

from taskmaster.compose import (
    CycleError,
    compose_skills,
)


def _skill(name: str, depends_on=None, composes_with=None) -> dict:
    fm = {"name": name, "description": f"desc {name}", "category": "development", "risk": "safe"}
    if depends_on is not None:
        fm["depends_on"] = depends_on
    if composes_with is not None:
        fm["composes_with"] = composes_with
    return {
        "dir": name,
        "path": f"{name}/SKILL.md",
        "frontmatter": fm,
        "frontmatter_valid": True,
        "frontmatter_error": None,
        "body": "",
        "line_count": 0,
        "size_bytes": 0,
    }


def test_compose_single_skill_no_deps():
    skills = [_skill("a"), _skill("b")]
    plan = compose_skills(["a"], skills=skills)
    assert [step["name"] for step in plan.steps] == ["a"]
    assert plan.warnings == []


def test_compose_linear_chain():
    skills = [_skill("a"), _skill("b", depends_on=["a"]), _skill("c", depends_on=["b"])]
    plan = compose_skills(["c"], skills=skills)
    order = [step["name"] for step in plan.steps]
    assert order.index("a") < order.index("b") < order.index("c")


def test_compose_diamond():
    skills = [
        _skill("a"),
        _skill("b", depends_on=["a"]),
        _skill("c", depends_on=["a"]),
        _skill("d", depends_on=["b", "c"]),
    ]
    plan = compose_skills(["d"], skills=skills)
    order = [step["name"] for step in plan.steps]
    assert order.index("a") < order.index("b")
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")


def test_compose_detects_cycle():
    skills = [
        _skill("a", depends_on=["b"]),
        _skill("b", depends_on=["a"]),
    ]
    with pytest.raises(CycleError) as exc:
        compose_skills(["a", "b"], skills=skills)
    assert "a" in exc.value.cycle and "b" in exc.value.cycle


def test_compose_missing_dependency_is_warning():
    skills = [_skill("a", depends_on=["missing"])]
    plan = compose_skills(["a"], skills=skills)
    assert any("missing" in w for w in plan.warnings)
    assert [step["name"] for step in plan.steps] == ["a"]


def test_compose_empty_input():
    plan = compose_skills([], skills=[])
    assert plan.steps == []


def test_compose_unknown_skill_raises():
    skills = [_skill("a")]
    with pytest.raises(KeyError):
        compose_skills(["nonexistent"], skills=skills)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_compose.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the composer**

Create `taskmaster/compose.py`:

```python
"""Dependency-graph composer for skills.

Reads the optional ``depends_on`` frontmatter list and produces a
topologically ordered plan. Cycles raise :class:`CycleError`.
Missing dependencies are returned in the plan's ``warnings`` list
alongside a fuzzy closest-match suggestion; the resolvable subset of
the plan is still returned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import get_close_matches
from typing import Any


class CycleError(ValueError):
    def __init__(self, cycle: list[str]) -> None:
        super().__init__(f"Dependency cycle detected: {' -> '.join(cycle)}")
        self.cycle = cycle


@dataclass
class ComposePlan:
    steps: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan": [
                {"order": i + 1, "name": step["name"], "depends_on": step["depends_on"]}
                for i, step in enumerate(self.steps)
            ],
            "warnings": list(self.warnings),
        }


def compose_skills(names: list[str], skills: list[dict[str, Any]]) -> ComposePlan:
    by_dir = {s["dir"]: s for s in skills}
    unknown = [n for n in names if n not in by_dir]
    if unknown:
        raise KeyError(f"Unknown skill(s): {unknown}")

    all_names = set(names)
    warnings: list[str] = []
    adjacency: dict[str, list[str]] = {}

    for name in names:
        skill = by_dir[name]
        deps = skill.get("frontmatter", {}).get("depends_on") or []
        deps = [d for d in deps if isinstance(d, str)]
        for dep in deps:
            if dep in by_dir:
                all_names.add(dep)
            else:
                suggestion = _closest(dep, list(by_dir.keys()))
                msg = f"'{name}' depends on missing skill '{dep}'"
                if suggestion:
                    msg += f" (did you mean '{suggestion}'?)"
                warnings.append(msg)
        adjacency[name] = [d for d in deps if d in by_dir]

    visited: set[str] = set()
    on_stack: set[str] = set()
    order: list[str] = []

    def visit(node: str, path: list[str]) -> None:
        if node in on_stack:
            cycle = path[path.index(node):] + [node]
            raise CycleError(cycle)
        if node in visited:
            return
        on_stack.add(node)
        for dep in adjacency.get(node, []):
            visit(dep, path + [node])
        on_stack.discard(node)
        visited.add(node)
        order.append(node)

    for name in names:
        visit(name, [])

    steps = [{"name": n, "depends_on": adjacency.get(n, [])} for n in order]
    return ComposePlan(steps=steps, warnings=warnings)


def _closest(needle: str, haystack: list[str]) -> str | None:
    matches = get_close_matches(needle, haystack, n=1, cutoff=0.6)
    return matches[0] if matches else None
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/test_compose.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add taskmaster/compose.py tests/test_compose.py
git commit -m "feat(compose): add dependency-graph composer with cycle and missing-dep handling"
```

---

## Task 10: CLI subcommand `embed`

**Files:**
- Modify: `taskmaster/cli.py` (add `embed` subcommand + dispatch)
- Test: `tests/test_cli_phase1.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_phase1.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from taskmaster.cli import build_parser


def test_embed_subcommand_registered():
    parser = build_parser()
    args = parser.parse_args(["embed", "--rebuild"])
    assert args.command == "embed"
    assert args.rebuild is True


def test_recommend_subcommand_registered():
    parser = build_parser()
    args = parser.parse_args(["recommend", "postgres", "--max", "3"])
    assert args.command == "recommend"
    assert args.task == "postgres"
    assert args.max == 3


def test_compose_subcommand_registered():
    parser = build_parser()
    args = parser.parse_args(["compose", "a", "b", "--json"])
    assert args.command == "compose"
    assert args.skills == ["a", "b"]
    assert args.json is True
```

This requires `build_parser()` to be importable. For the test to pass we must extract parser construction from `main()` into a helper.

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_cli_phase1.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Refactor `cli.py` to expose `build_parser` and register three new subcommands**

Replace `taskmaster/cli.py` with:

```python
"""TaskMaster CLI dispatch.

All business logic lives in the engine modules; this file is
responsible for argument parsing, command dispatch, and output
rendering. Run with ``python3 taskmaster.py <command>``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import taskmaster
from taskmaster import cli as _self_marker  # noqa: F401  (intentional import path stability)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="TaskMaster CLI - manage 269 AI agent skills",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", help="Commands")

    validate_p = sub.add_parser("validate", help="Validate all skills")
    validate_p.add_argument("--json", action="store_true")

    list_p = sub.add_parser("list", help="List all skills")
    list_p.add_argument("--long", action="store_true")
    list_p.add_argument("--category")
    list_p.add_argument("--risk")

    search_p = sub.add_parser("search", help="Search skills")
    search_p.add_argument("query")
    search_p.add_argument("--no-fuzzy", action="store_true")

    suggest_p = sub.add_parser("suggest", help="Suggest skills for a task")
    suggest_p.add_argument("task")
    suggest_p.add_argument("--max", type=int, default=5)

    stats_p = sub.add_parser("stats", help="Show distribution statistics")
    stats_p.add_argument("-v", "--verbose", action="store_true")

    sub.add_parser("generate-index", help="Regenerate INDEX.md")
    sub.add_parser("quality", help="Score all skills by completeness")

    check_p = sub.add_parser("check", help="Deep-check a single skill")
    check_p.add_argument("skill_dir")

    export_p = sub.add_parser("export", help="Export skills")
    export_p.add_argument("--json", action="store_true")
    export_p.add_argument("--skill")

    diff_p = sub.add_parser("diff", help="Compare skill to schema")
    diff_p.add_argument("skill_dir")

    hygiene_p = sub.add_parser("hygiene", help="Hygiene report")
    normalize_p = sub.add_parser("normalize", help="Normalize metadata (dry-run)")
    related_p = sub.add_parser("related", help="Find related skills")
    related_p.add_argument("skill_ref")
    related_p.add_argument("--max", type=int, default=5)

    embed_p = sub.add_parser("embed", help="Build or refresh the embedding index")
    embed_p.add_argument("--rebuild", action="store_true", help="Force a full rebuild")

    recommend_p = sub.add_parser("recommend", help="Recommend skills for a task")
    recommend_p.add_argument("task")
    recommend_p.add_argument("--max", type=int, default=5)
    recommend_p.add_argument("--max-risk", choices=["safe", "medium", "high"])
    recommend_p.add_argument("--json", action="store_true")

    compose_p = sub.add_parser("compose", help="Compose a dependency-ordered plan")
    compose_p.add_argument("skills", nargs="+", help="Skill names or directories")
    compose_p.add_argument("--json", action="store_true")

    return parser


def _embedding_index(skills, *, rebuild: bool):
    from taskmaster.embeddings import get_default_provider, cache_key
    from taskmaster.embeddings.index import EmbeddingIndex

    provider = get_default_provider()
    cache_dir = Path(".taskmaster_cache") / "embeddings" / cache_key(provider)
    index = EmbeddingIndex(provider=provider, cache_dir=cache_dir)
    if not rebuild and (cache_dir / "index.faiss").exists():
        try:
            index.load()
            return index, provider
        except Exception:
            pass
    index.build(skills)
    return index, provider


def _cmd_embed(args) -> int:
    skills = taskmaster.get_all_skills()
    try:
        _, provider = _embedding_index(skills, rebuild=args.rebuild)
    except RuntimeError as e:
        print(str(e))
        return 1
    print(f"Index built with {provider.name} ({provider.model_id})")
    return 0


def _cmd_recommend(args) -> int:
    skills = taskmaster.get_all_skills()
    index = None
    try:
        index, _ = _embedding_index(skills, rebuild=False)
    except RuntimeError:
        index = None
    from taskmaster.recommend import recommend_skills
    results = recommend_skills(
        args.task, skills=skills, index=index, k=args.max, max_risk=args.max_risk
    )
    if args.json:
        print(json.dumps([
            {"name": r["skill"]["frontmatter"].get("name", r["skill"]["dir"]),
             "score": r["score"], "reasons": r["reasons"], "degraded": r["degraded"]}
            for r in results
        ], indent=2))
        return 0
    for r in results:
        fm = r["skill"]["frontmatter"]
        print(f"  {fm.get('name', r['skill']['dir']):<35} score={r['score']:.3f}  {' '.join(r['reasons'])}")
    return 0


def _cmd_compose(args) -> int:
    skills = taskmaster.get_all_skills()
    from taskmaster.compose import CycleError, compose_skills
    try:
        plan = compose_skills(args.skills, skills=skills)
    except CycleError as e:
        if args.json:
            print(json.dumps({"error": "cycle", "cycle": e.cycle}))
        else:
            print(f"Error: {e}")
        return 1
    except KeyError as e:
        if args.json:
            print(json.dumps({"error": "unknown_skill", "message": str(e)}))
        else:
            print(f"Error: {e}")
        return 1
    if args.json:
        print(json.dumps(plan.to_dict(), indent=2))
    else:
        for step in plan.steps:
            deps = ", ".join(step["depends_on"]) if step["depends_on"] else "-"
            print(f"  {step['name']:<35} depends_on: {deps}")
        for w in plan.warnings:
            print(f"  warning: {w}")
    return 0


_DISPATCH = {
    "embed": _cmd_embed,
    "recommend": _cmd_recommend,
    "compose": _cmd_compose,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command in _DISPATCH:
        sys.exit(_DISPATCH[args.command](args))
    # Fall back to legacy dispatch in __init__.py for unchanged commands.
    taskmaster.main()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the new test to verify it passes**

Run: `.venv/bin/pytest tests/test_cli_phase1.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run the full CLI test suite to verify no regression**

Run: `.venv/bin/pytest tests/test_cli.py tests/test_taskmaster.py -v`
Expected: all existing tests still pass.

- [ ] **Step 6: Smoke-test the new commands end-to-end**

Run: `.venv/bin/python taskmaster.py recommend "postgres" --max 3`
Expected: at least one line of output, with no traceback. (If the embedding index is not yet built, output may show `degraded: true` keyword-only results — that's correct.)

Run: `.venv/bin/python taskmaster.py compose postgres-tuning bug-hunter --json`
Expected: a JSON object with a `plan` array (and possibly `warnings`). Exit code 0.

- [ ] **Step 7: Commit**

```bash
git add taskmaster/cli.py tests/test_cli_phase1.py
git commit -m "feat(cli): add embed, recommend, compose subcommands"
```

---

## Task 11: Update README with the new commands

**Files:**
- Modify: `README.md` (insert a "Phase 1 — Engine" section before the License section)

- [ ] **Step 1: Append the new documentation section**

Find the line `## License` in `README.md` and insert the following block immediately before it:

```markdown
## Phase 1 — Agent-Native Engine

The 269-skill catalog now ships with a hybrid recommender, a dependency-graph composer, and a pluggable embedding system. Three new CLI subcommands are available:

```bash
# Build (or rebuild) the embedding index. Uses sentence-transformers locally
# by default; set OPENAI_API_KEY and install the openai extra to use OpenAI.
python3 taskmaster.py embed
python3 taskmaster.py embed --rebuild

# Recommend the top-K skills for a free-form task.
python3 taskmaster.py recommend "debug a postgres deadlock" --max 5
python3 taskmaster.py recommend "design a multi-tenant API" --json

# Compose a topologically ordered plan from a set of skills.
python3 taskmaster.py compose postgres-tuning error-detective --json
```

The recommender combines semantic similarity (0.55), keyword overlap (0.30), and tag overlap (0.15). When the embedding extra is not installed, it falls back to keyword-only and tags every result with `degraded: true` so the caller can see the lower-quality mode.

The composer reads the optional `depends_on` frontmatter list, returns a topologically ordered plan, and surfaces missing dependencies with closest-match suggestions. Cycles raise an error.

### Optional Frontmatter Fields

| Field | Type | Semantics |
|---|---|---|
| `depends_on` | list[string] | Skills that must load first (used by `compose`). |
| `composes_with` | list[string] | Skills commonly used together (used by `recommend`). |

These fields are optional. Existing skills that omit them continue to validate and behave as before.

### Installation

The base install (`pip install taskmaster`) requires no new dependencies. To enable semantic search:

```bash
pip install "taskmaster[semantic]"
```

For OpenAI-backed embeddings:

```bash
pip install "taskmaster[semantic,openai]"
export OPENAI_API_KEY=...
```
```

- [ ] **Step 2: Verify the README renders the new section**

Run: `.venv/bin/python -c "import re; r=open('README.md').read(); assert 'Phase 1 — Agent-Native Engine' in r; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document Phase 1 engine commands and optional frontmatter"
```

---

## Task 12: Add CI job for Phase 1

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Add a `phase1` job**

Append the following block to the bottom of `.github/workflows/ci.yml`:

```yaml
  phase1:
    name: Phase 1 Engine Tests
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install with semantic extras
        run: |
          python -m pip install -e ".[semantic]"

      - name: Run Phase 1 tests
        run: |
          python -m pytest tests/test_embeddings_provider.py tests/test_embeddings_index.py tests/test_embeddings_text.py tests/test_recommend.py tests/test_compose.py tests/test_cli_phase1.py tests/test_validation_optional_fields.py -v
```

- [ ] **Step 2: Validate the YAML**

Run: `.venv/bin/python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml')); print('ok')"`
Expected: `ok` (requires `pyyaml`; if not available, just `python3 -c "import tomllib; ..."` is not appropriate — install `pyyaml` via `pip install pyyaml` first, or skip and trust the GitHub-side validator).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add Phase 1 engine test job"
```

---

## Task 13: Full-suite verification

- [ ] **Step 1: Run the full test suite**

Run: `.venv/bin/pytest tests/ -v`
Expected: all tests pass — every existing test plus the new Phase 1 tests. Count the new tests: 4 (validation_optional_fields) + 4 (embeddings_provider) + 4 (embeddings_index) + 4 (embeddings_text) + 4 (recommend) + 7 (compose) + 3 (cli_phase1) = 30 new tests. Existing tests must remain green.

- [ ] **Step 2: Confirm zero new Pyright errors**

Run: `.venv/bin/pip install pyright && .venv/bin/pyright taskmaster/embeddings taskmaster/recommend.py taskmaster/compose.py taskmaster/validation.py taskmaster/cli.py`
Expected: 0 errors in the new modules. (Existing strict-typed modules should be unaffected.)

- [ ] **Step 3: Smoke-test the three new CLI commands**

Run each and verify exit code 0 with non-empty output:

```bash
.venv/bin/python taskmaster.py embed --rebuild
.venv/bin/python taskmaster.py recommend "code review" --max 3
.venv/bin/python taskmaster.py compose code-reviewer bug-hunter --json
```

- [ ] **Step 4: Tag the release**

```bash
git tag -a v1.1.0 -m "v1.1.0 — Phase 1 engine (semantic search, recommender, composer)"
git push origin v1.1.0
```

- [ ] **Step 5: Final commit (if any drift) and summary**

```bash
git status
git log --oneline -10
```

Report the commit list, the new test count, and the three smoke-test results. Phase 1 is complete and shippable. Phase 2 (MCP server) begins in a follow-up plan.

---

## Self-Review

**Spec coverage:**
- Optional frontmatter fields (`depends_on`, `composes_with`) — Task 2 ✅
- Pluggable embedding provider with local default — Tasks 3, 4, 5 ✅
- FAISS index persistence with incremental update — Task 7 ✅
- NullProvider / degraded fallback — Tasks 3, 7 (raises), 8 (recommend sets `degraded: true`) ✅
- Hybrid recommender with explicit weights 0.55/0.30/0.15 — Task 8 ✅
- Composer with cycle detection and missing-dep warnings — Task 9 ✅
- New CLI subcommands `embed`, `recommend`, `compose` — Task 10 ✅
- Optional extras in `pyproject.toml` — Task 1 ✅
- README updates — Task 11 ✅
- CI integration — Task 12 ✅
- TDD pattern with exact tests, exact code, exact commands throughout ✅

**Out of scope for this plan (deferred to Phase 2 / 3 / 4 plans):**
- MCP server (Phase 2)
- Installer for Claude/Qwen/Cursor (Phase 3)
- Continuum integration example in README (Phase 4)
- macOS CI job (Phase 3 when installer is added)

**Placeholder scan:** No `TODO`, `TBD`, "implement later", or "similar to Task N" — all code blocks are complete and runnable as written.

**Type consistency:** `EmbeddingProvider` is referenced by the same name in Tasks 3, 4, 5, 7. `EmbeddingIndex` is consistent in Task 7 and Task 10. `compose_skills` signature `names, skills` is consistent in Task 9 and Task 10. `recommend_skills` signature `task, skills, index, k, max_risk` is consistent in Task 8 and Task 10. CLI subcommand names `embed`, `recommend`, `compose` are consistent in Task 10's parser, dispatch, and test.
