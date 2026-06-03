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
        "line_count": 10,
        "size_bytes": 500,
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
