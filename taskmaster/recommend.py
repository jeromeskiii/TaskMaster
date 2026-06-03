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
