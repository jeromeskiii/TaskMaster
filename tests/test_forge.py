from __future__ import annotations

import json

from taskmaster.forge import create_forge_plan, write_forge_workspace


def _skill(name: str, desc: str, tags=None, risk: str = "safe") -> dict:
    return {
        "dir": name,
        "path": f"{name}/SKILL.md",
        "frontmatter": {
            "name": name,
            "description": desc,
            "tags": tags or [],
            "category": "development",
            "risk": risk,
        },
        "frontmatter_valid": True,
        "frontmatter_error": None,
        "body": desc,
        "line_count": 1,
        "size_bytes": len(desc),
    }


def test_create_forge_plan_returns_skill_prs_and_prompts():
    skills = [
        _skill("software-architecture", "Design software architecture and implementation plans", ["architecture"]),
        _skill("test-driven-development", "Create tests and TDD workflows", ["tests"]),
        _skill("quant-analyst", "Analyze markets and trading systems", ["trading", "market"]),
    ]

    plan = create_forge_plan("Build a Coinbase WebSocket feed that outputs MarketSnapshot objects", skills=skills)

    assert plan.task.startswith("Build a Coinbase")
    assert plan.recommended_skills
    assert any("MarketSnapshot" in deliverable for chunk in plan.pr_plan for deliverable in chunk.deliverables)
    assert "architect" in plan.agent_prompts
    assert any("dry-run" in rule.lower() for rule in plan.safety_rules)


def test_write_forge_workspace_creates_expected_files(tmp_path):
    skills = [_skill("software-architecture", "Architecture planning", ["architecture"])]
    plan = create_forge_plan("Build an API endpoint", skills=skills)

    output = write_forge_workspace(plan, tmp_path / ".taskmaster" / "forge")

    assert (output / "forge_plan.md").exists()
    assert (output / "forge_plan.json").exists()
    assert (output / "agent_prompts" / "architect.md").exists()
    data = json.loads((output / "forge_plan.json").read_text())
    assert data["task"] == "Build an API endpoint"
