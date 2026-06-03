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
