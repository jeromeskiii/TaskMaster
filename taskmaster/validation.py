from __future__ import annotations

import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from typing import Any

from .corpus import SkillRecord, _as_list

REQUIRED_FIELDS = ["name", "description", "category", "risk"]
VALID_RISKS = {"safe", "medium", "high"}
RISK_ORDER = {"safe": 0, "medium": 1, "high": 2}
KNOWN_CATEGORIES = {
    "agent-behavior", "ai", "ai-agents", "ai-research", "automation",
    "backend", "browser-automation", "cloud", "data", "data-ai",
    "development", "framework", "frontend", "mcp", "media", "memory",
    "meta", "networking", "security", "voice-agents",
}
MIN_SIZE = 500
MIN_LINES = 10
MIN_DESC_LEN = 30
OPTIONAL_LIST_FIELDS = ("depends_on", "composes_with")


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


def _coerce_skills(skills: list[SkillRecord] | list[dict[str, Any]]) -> list[SkillRecord]:
    return [_coerce_skill(skill) for skill in skills]


def _normalize_whitespace(text: object) -> str:
    return re.sub(r"\s+", " ", str(text).strip())


def _normalize_description(text: object) -> str:
    normalized = _normalize_whitespace(text).lower()
    return re.sub(r"[^a-z0-9 ]+", "", normalized)


def _tag_shape(value: object) -> str:
    if isinstance(value, list):
        return "list"
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("[") and text.endswith("]"):
            return "yaml-list-string"
        if "," in text:
            return "csv-string"
        if text:
            return "scalar-string"
    if value in (None, ""):
        return "empty"
    return type(value).__name__


def validate_skill(skill: SkillRecord | dict[str, Any]) -> list[str]:
    record = _coerce_skill(skill)
    issues = []
    fm = record.frontmatter

    if not record.frontmatter_valid:
        return [record.frontmatter_error or "missing YAML frontmatter"]

    for field in REQUIRED_FIELDS:
        if field not in fm or not fm[field]:
            issues.append(f"missing field '{field}'")

    risk = fm.get("risk", "")
    if risk and risk not in VALID_RISKS:
        issues.append(f"invalid risk '{risk}'")

    category = fm.get("category", "")
    if category and category not in KNOWN_CATEGORIES:
        issues.append(f"unknown category '{category}'")

    if record.size_bytes < MIN_SIZE:
        issues.append(f"too small ({record.size_bytes} bytes)")

    if record.line_count < MIN_LINES:
        issues.append(f"too short ({record.line_count} lines)")

    description = str(fm.get("description", ""))
    if len(description) < MIN_DESC_LEN:
        issues.append(f"description too short ({len(description)} chars)")

    issues.extend(_validate_optional_lists(record))

    return issues


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


def validate_all(skills: list[SkillRecord] | list[dict[str, Any]]) -> dict[str, Any]:
    records = _coerce_skills(skills)
    issues = []
    stats = {k: 0 for k in [
        "total", "valid", "missing_frontmatter", "missing_required_fields",
        "invalid_risk", "unknown_category", "skeleton_skills", "short_descriptions",
        "frontmatter_parse_errors",
    ]}

    for record in records:
        skill_issues = validate_skill(record)
        if skill_issues:
            issues.append({"dir": record.dir, "issue": "; ".join(skill_issues)})
            for issue in skill_issues:
                if not record.frontmatter_valid and record.frontmatter_error:
                    stats["frontmatter_parse_errors"] += 1
                    break
                if "frontmatter" in issue:
                    stats["missing_frontmatter"] += 1
                    break
                if "field" in issue:
                    stats["missing_required_fields"] += 1
                elif "risk" in issue:
                    stats["invalid_risk"] += 1
                elif "category" in issue:
                    stats["unknown_category"] += 1
                elif "description" in issue:
                    stats["short_descriptions"] += 1
                elif "small" in issue or "short" in issue:
                    stats["skeleton_skills"] += 1
        stats["total"] += 1

    stats["valid"] = stats["total"] - len(issues)
    return {"stats": stats, "issues": issues, "skills": [record.to_dict() for record in records]}


def score_skill_quality(skill: SkillRecord | dict[str, Any]) -> dict[str, Any]:
    record = _coerce_skill(skill)
    fm = record.frontmatter
    score = 0.0
    details = {}

    frontmatter_bonus = 0
    for field in ["name", "description", "category", "risk", "source", "date_added", "tags", "depends_on", "composes_with"]:
        if field in fm and fm[field]:
            frontmatter_bonus += 8 if field in {"name", "description"} else 4
    details["frontmatter_completeness"] = min(frontmatter_bonus, 50)
    score += details["frontmatter_completeness"]

    description = str(fm.get("description", ""))
    details["description_length"] = len(description)
    if len(description) >= 100:
        score += 15
    elif len(description) >= 50:
        score += 10
    elif len(description) >= MIN_DESC_LEN:
        score += 5

    body_ratio = record.line_count / 50 if record.line_count > 0 else 0
    details["body_lines"] = record.line_count
    score += min(body_ratio * 30, 30)

    has_headings = bool(re.search(r"^#{1,3}\s+\w+", record.body, re.MULTILINE))
    has_code_blocks = "```" in record.body
    details["has_structure"] = has_headings
    details["has_examples"] = has_code_blocks
    score += 5 if has_headings else 0
    score += 5 if has_code_blocks else 0

    return {"score": min(score, 100), "details": details}


def build_hygiene_report(skills: list[SkillRecord] | list[dict[str, Any]]) -> dict[str, Any]:
    records = _coerce_skills(skills)
    name_buckets: dict[str, list[str]] = defaultdict(list)
    description_buckets: dict[str, list[SkillRecord]] = defaultdict(list)
    tag_buckets: dict[tuple[str, ...], set[str]] = defaultdict(set)
    parse_error_buckets: Counter[str] = Counter()
    issues = {
        "duplicate_names": [],
        "near_duplicate_descriptions": [],
        "tag_shape_inconsistencies": [],
        "parse_error_rollups": [],
        "category_anomalies": [],
        "risk_anomalies": [],
    }

    for record in records:
        fm = record.frontmatter
        name = _normalize_whitespace(fm.get("name", record.dir))
        if name:
            name_buckets[name.lower()].append(record.dir)

        description = _normalize_description(fm.get("description", ""))
        if description:
            description_buckets[description].append(record)

        tags = tuple(_as_list(fm.get("tags")))
        if tags:
            tag_buckets[tags].add(_tag_shape(fm.get("tags")))

        if not record.frontmatter_valid and record.frontmatter_error:
            parse_error_buckets[_normalize_whitespace(record.frontmatter_error)] += 1

        category = fm.get("category")
        if category and category not in KNOWN_CATEGORIES:
            issues["category_anomalies"].append({"dir": record.dir, "category": category})

        risk = fm.get("risk")
        if risk and risk not in VALID_RISKS:
            issues["risk_anomalies"].append({"dir": record.dir, "risk": risk})

    for name, dirs in sorted(name_buckets.items()):
        if len(dirs) > 1:
            issues["duplicate_names"].append({"name": name, "dirs": sorted(dirs)})

    for description, bucket in description_buckets.items():
        if len(bucket) > 1:
            issues["near_duplicate_descriptions"].append(
                {"dirs": sorted(record.dir for record in bucket), "description_bucket": description}
            )

    seen_pairs: set[tuple[str, str]] = set()
    normalized_descriptions = list(description_buckets.items())
    for index, (left_desc, left_bucket) in enumerate(normalized_descriptions):
        for right_desc, right_bucket in normalized_descriptions[index + 1:]:
            if abs(len(left_desc) - len(right_desc)) > 20:
                continue
            similarity = SequenceMatcher(None, left_desc, right_desc).ratio()
            if similarity < 0.92:
                continue
            dirs = tuple(sorted({record.dir for record in left_bucket + right_bucket}))
            if len(dirs) < 2 or dirs in seen_pairs:
                continue
            seen_pairs.add(dirs)
            issues["near_duplicate_descriptions"].append({"dirs": list(dirs), "similarity": round(similarity, 3)})

    for tags, shapes in sorted(tag_buckets.items()):
        if len(shapes) > 1:
            issues["tag_shape_inconsistencies"].append(
                {"tags": list(tags), "shapes": sorted(shapes)}
            )

    for error, count in parse_error_buckets.most_common():
        issues["parse_error_rollups"].append({"error": error, "count": count})

    stats = {
        "total_skills": len(records),
        "duplicate_names": len(issues["duplicate_names"]),
        "near_duplicate_descriptions": len(issues["near_duplicate_descriptions"]),
        "tag_shape_inconsistencies": len(issues["tag_shape_inconsistencies"]),
        "parse_error_rollups": len(issues["parse_error_rollups"]),
        "category_anomalies": len(issues["category_anomalies"]),
        "risk_anomalies": len(issues["risk_anomalies"]),
    }
    return {"stats": stats, "issues": issues}


def build_normalization_report(skills: list[SkillRecord] | list[dict[str, Any]]) -> dict[str, Any]:
    records = _coerce_skills(skills)
    changes = []
    _LIST_FIELDS = ("tags",) + OPTIONAL_LIST_FIELDS

    for record in records:
        for field in _LIST_FIELDS:
            raw = record.frontmatter.get(field)
            normalized = _as_list(raw)
            if isinstance(raw, str) and normalized and raw != normalized:
                changes.append(
                    {
                        "dir": record.dir,
                        "field": field,
                        "current": raw,
                        "normalized": normalized,
                        "reason": f"scalar {field} string can be normalized to canonical list form",
                    }
                )

    stats = {
        "total_skills": len(records),
        "total_changes": len(changes),
        "tag_normalizations": sum(1 for c in changes if c["field"] == "tags"),
        "list_field_normalizations": sum(1 for c in changes if c["field"] in ("depends_on", "composes_with")),
    }
    return {"stats": stats, "changes": changes}
