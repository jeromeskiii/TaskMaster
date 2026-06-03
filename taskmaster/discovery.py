from __future__ import annotations

from collections.abc import Iterable
from difflib import SequenceMatcher, get_close_matches
from typing import Any

from .corpus import SkillRecord, _as_list, _flatten_text, _tokenize_text, get_all_skills

_RELATED_TERMS: dict[str, set[str]] = {
    "debug": {"bug", "bugs", "debugging", "troubleshooting", "incident", "incidents"},
    "test": {"test", "tests", "testing", "qa", "quality"},
    "deploy": {"deploy", "deployment", "release", "shipping"},
    "architecture": {"architecture", "architect"},
    "api": {"api", "rest", "graphql", "endpoint", "endpoints"},
}

_CATEGORY_HINTS: dict[str, list[str]] = {
    "web": ["frontend", "browser-automation"],
    "api": ["backend"],
    "database": ["backend", "data"],
    "security": ["security"],
    "cloud": ["cloud"],
    "ai": ["ai", "data-ai"],
    "frontend": ["frontend"],
    "backend": ["backend"],
    "data": ["data-ai"],
}


def _coerce_skill(skill: SkillRecord | dict[str, Any]) -> SkillRecord:
    if isinstance(skill, SkillRecord):
        return skill
    data = dict(skill)
    data.setdefault("dir", str(data.get("frontmatter", {}).get("name", "unknown-skill")))
    data.setdefault("path", f"{data['dir']}/SKILL.md")
    data.setdefault("frontmatter", {})
    data.setdefault("frontmatter_valid", True)
    data.setdefault("frontmatter_error", None)
    data.setdefault("body", "")
    data.setdefault("line_count", 0)
    data.setdefault("size_bytes", 0)
    return SkillRecord.from_dict(data)


def _coerce_skills(skills: Iterable[SkillRecord | dict[str, Any]]) -> list[SkillRecord]:
    return [_coerce_skill(skill) for skill in skills]


def _result(record: SkillRecord, score: float, reasons: list[str]) -> dict[str, Any]:
    payload = record.to_dict()
    payload.update(
        {
            "skill": record,
            "score": round(score, 3),
            "relevance": round(score, 3),
            "reasons": reasons,
        }
    )
    return payload


def _normalize(text: object) -> str:
    return " ".join(_tokenize_text(text))


def _match_tokens(query_terms: set[str], candidate: object) -> set[str]:
    candidate_terms = _tokenize_text(candidate)
    return query_terms & candidate_terms


def _fuzzy_hit(query: str, candidates: Iterable[str]) -> bool:
    target = query.strip().lower()
    if not target:
        return False
    matches = get_close_matches(target, [candidate.lower() for candidate in candidates], n=1, cutoff=0.78)
    if matches:
        return True
    for candidate in candidates:
        if SequenceMatcher(None, target, candidate.lower()).ratio() >= 0.78:
            return True
    return False


def _iter_target_records(
    skills_or_query: Iterable[SkillRecord | dict[str, Any]] | str,
    query: str | None,
) -> tuple[list[SkillRecord], str]:
    if isinstance(skills_or_query, str) and query is None:
        return _coerce_skills(get_all_skills()), skills_or_query
    if query is None:
        raise TypeError("query is required when skills are provided explicitly")
    return _coerce_skills(skills_or_query), query


def search_skills(
    skills_or_query: Iterable[SkillRecord | dict[str, Any]] | str,
    query: str | None = None,
    *,
    category: str | None = None,
    risk: str | None = None,
    tag: str | None = None,
    fuzzy: bool = True,
) -> list[dict[str, Any]]:
    skills, query_text = _iter_target_records(skills_or_query, query)
    query_terms = _tokenize_text(query_text)
    query_text_l = query_text.lower().strip()
    results: list[dict[str, Any]] = []

    for record in skills:
        fm = record.frontmatter
        if category and fm.get("category") != category:
            continue
        if risk and fm.get("risk") != risk:
            continue
        if tag and tag not in _as_list(fm.get("tags")):
            continue

        reasons: list[str] = []
        score = 0.0
        name = fm.get("name", record.dir)
        name_terms = _tokenize_text(name)
        description_terms = _tokenize_text(fm.get("description", ""))
        tag_terms = _tokenize_text(_as_list(fm.get("tags")))
        body_terms = _tokenize_text(record.body)
        searchable_terms = name_terms | description_terms | tag_terms | body_terms | _tokenize_text(record.dir)

        if query_text_l and _fuzzy_hit(query_text_l, [record.dir, str(name)]):
            score += 6
            reasons.append("name term match")
        elif query_terms & name_terms:
            score += 8
            reasons.append("name term match")

        description_overlap = query_terms & description_terms
        if description_overlap:
            score += min(len(description_overlap) * 2.5, 8)
            reasons.append("description overlap")

        tag_overlap = query_terms & tag_terms
        if tag_overlap:
            score += min(len(tag_overlap) * 3, 8)
            reasons.append("tag overlap")

        body_overlap = query_terms & body_terms
        if body_overlap:
            score += min(len(body_overlap) * 1.5, 4)
            reasons.append("body overlap")

        if tag and tag in _as_list(fm.get("tags")):
            score += 5
            reasons.append(f"tag filter: {tag}")

        if not reasons and fuzzy and _fuzzy_hit(query_text_l, searchable_terms):
            score += 3
            reasons.append("fuzzy match")

        if score > 0:
            results.append(_result(record, score, reasons))

    results.sort(key=lambda item: (item["relevance"], item["score"], item["dir"]), reverse=True)
    return results


def suggest_skills(
    skills_or_task: Iterable[SkillRecord | dict[str, Any]] | str,
    task: str | None = None,
    max_results: int = 5,
) -> list[dict[str, Any]]:
    skills, task_text = _iter_target_records(skills_or_task, task)
    task_terms = _tokenize_text(task_text)
    expanded_terms = set(task_terms)
    matched_categories = set()

    for keyword, categories in _CATEGORY_HINTS.items():
        if keyword in task_terms:
            matched_categories.update(categories)

    for keyword, synonyms in _RELATED_TERMS.items():
        if keyword in task_terms:
            expanded_terms.update(synonyms)

    results: list[dict[str, Any]] = []
    for record in skills:
        fm = record.frontmatter
        name = fm.get("name", record.dir)
        name_terms = _tokenize_text(name)
        desc_terms = _tokenize_text(fm.get("description", ""))
        tag_terms = _tokenize_text(_as_list(fm.get("tags")))
        body_terms = _tokenize_text(record.body)
        all_terms = name_terms | desc_terms | tag_terms | body_terms | _tokenize_text(record.dir)

        reasons: list[str] = []
        score = 0.0

        if fm.get("category") in matched_categories:
            score += 5
            reasons.append(f"category hint: {fm.get('category')}")

        if name_terms & expanded_terms:
            score += 8
            reasons.append("name term match")

        desc_overlap = desc_terms & expanded_terms
        if desc_overlap:
            score += min(len(desc_overlap) * 2, 8)
            reasons.append("description overlap")

        tag_overlap = tag_terms & expanded_terms
        if tag_overlap:
            score += min(len(tag_overlap) * 3, 8)
            reasons.append("tag overlap")

        body_overlap = body_terms & expanded_terms
        if body_overlap:
            score += min(len(body_overlap) * 1.5, 4)
            reasons.append("body overlap")

        if not reasons and _fuzzy_hit(task_text, all_terms):
            score += 3
            reasons.append("fuzzy match")

        if score > 0:
            results.append(_result(record, score, reasons))

    results.sort(key=lambda item: (item["relevance"], item["score"], item["dir"]), reverse=True)
    return results[:max_results]


def related_skills(
    skills_or_ref: Iterable[SkillRecord | dict[str, Any]] | str,
    skill_ref: str | None = None,
    max_results: int = 5,
) -> list[dict[str, Any]]:
    skills, reference = _iter_target_records(skills_or_ref, skill_ref)
    target = None
    for record in skills:
        if record.dir == reference or record.frontmatter.get("name") == reference:
            target = record
            break
    if target is None:
        return []

    target_fm = target.frontmatter
    target_terms = (
        _tokenize_text(target.dir)
        | _tokenize_text(target_fm.get("name", target.dir))
        | _tokenize_text(target_fm.get("description", ""))
        | _tokenize_text(_as_list(target_fm.get("tags")))
        | _tokenize_text(target.body)
        | _tokenize_text(target_fm.get("category", ""))
    )

    results: list[dict[str, Any]] = []
    for record in skills:
        if record.dir == target.dir:
            continue

        fm = record.frontmatter
        reasons: list[str] = []
        score = 0.0
        candidate_terms = (
            _tokenize_text(record.dir)
            | _tokenize_text(fm.get("name", record.dir))
            | _tokenize_text(fm.get("description", ""))
            | _tokenize_text(_as_list(fm.get("tags")))
            | _tokenize_text(record.body)
            | _tokenize_text(fm.get("category", ""))
        )

        shared_terms = target_terms & candidate_terms
        if shared_terms:
            score += min(len(shared_terms) * 1.5, 8)
            reasons.append("shared topic overlap")

        if target_fm.get("category") and target_fm.get("category") == fm.get("category"):
            score += 3
            reasons.append("shared category")

        target_tags = set(_as_list(target_fm.get("tags")))
        candidate_tags = set(_as_list(fm.get("tags")))
        shared_tags = target_tags & candidate_tags
        if shared_tags:
            score += min(len(shared_tags) * 2, 6)
            reasons.append("tag overlap")

        if not reasons and _fuzzy_hit(target.dir, [record.dir, str(fm.get("name", ""))]):
            score += 2
            reasons.append("name term match")

        if score > 0:
            results.append(_result(record, score, reasons))

    results.sort(key=lambda item: (item["relevance"], item["score"], item["dir"]), reverse=True)
    return results[:max_results]
