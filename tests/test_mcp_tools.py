"""Tests for MCP tool function bodies.

The MCP tools are registered inside ``_make_server()`` (which requires
the ``mcp`` extra). To test without that dependency, this file exercises
the pure-function wrappers that ``_make_server()`` calls. If those
wrappers do not exist yet, the imports below will fail.
"""


def test_list_categories_returns_non_empty_dict():
    from taskmaster.mcp.server import tool_list_categories
    result = tool_list_categories()
    assert isinstance(result, dict)
    assert len(result) > 0
    for v in result.values():
        assert isinstance(v, int)
        assert v > 0


def test_get_skill_returns_frontmatter_and_body():
    from taskmaster.mcp.server import tool_get_skill
    result = tool_get_skill("bug-hunter")
    assert "error" not in result
    assert "frontmatter" in result
    assert "body" in result
    assert "name" in result["frontmatter"]
    assert result["frontmatter"]["name"] == "bug-hunter"


def test_get_skill_missing_returns_error():
    from taskmaster.mcp.server import tool_get_skill
    result = tool_get_skill("definitely-not-a-real-skill-xyz")
    assert "error" in result
    assert result["error"] == "not_found"


def test_recommend_skills_degraded_in_base_env():
    from taskmaster.mcp.server import tool_recommend_skills
    result = tool_recommend_skills("debug a production API timeout", max_results=3)
    assert isinstance(result, str)
    # In base env, no semantic index -> degraded mode
    assert "degraded mode" in result


def test_compose_skills_topological_order():
    import json
    from taskmaster.mcp.server import tool_compose_skills
    result = tool_compose_skills(
        ["error-detective", "distributed-tracing", "incident-responder"],
        json_output=True,
    )
    plan = json.loads(result)
    assert "plan" in plan
    assert len(plan["plan"]) >= 3
    order = {step["name"]: step["order"] for step in plan["plan"]}
    for step in plan["plan"]:
        for dep in step["depends_on"]:
            assert order[dep] < order[step["name"]], (
                f"Dependency '{dep}' must come before '{step['name']}'"
            )


def test_validate_skill_known_bad_returns_error():
    from taskmaster.mcp.server import tool_validate_skill
    result = tool_validate_skill("definitely-not-a-real-skill-xyz")
    assert "Error" in result
