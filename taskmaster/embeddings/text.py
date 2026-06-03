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
