"""MCP server for TaskMaster.

Exposes validation, search, suggestion, recommendation, composition,
and skill inspection as MCP tools so that AI coding assistants can
query the skill catalog at runtime.

Usage::

    taskmaster mcp serve           # stdio transport (default)
    taskmaster mcp serve --sse     # SSE transport on port 8000

Requires the ``mcp`` extra (``pip install 'taskmaster[mcp]'``).
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

import taskmaster


def _build_index() -> Any | None:
    """Try to load or build the embedding index, returning None on failure."""
    skills = taskmaster.get_all_skills()
    from taskmaster.embeddings import get_default_provider
    from taskmaster.embeddings.index import EmbeddingIndex
    from taskmaster.embeddings.provider import cache_key

    provider = get_default_provider()
    cache_dir = taskmaster.CACHE_DIR / "embeddings" / cache_key(provider)
    index = EmbeddingIndex(provider=provider, cache_dir=cache_dir)
    try:
        index.load()
    except Exception:
        try:
            index.build(skills)
        except RuntimeError:
            return None
    return index


def _make_server():  # type: ignore[no-untyped-def]
    """Create and configure the FastMCP server instance."""
    from mcp.server.fastmcp import FastMCP  # lazy: requires [mcp] extra

    mcp = FastMCP(
        "TaskMaster",
        instructions="TaskMaster skill catalog — validate, search, suggest, recommend, compose, and inspect AI agent skills.",
        host="127.0.0.1",
        port=8000,
    )

    # ── validate ────────────────────────────────────────────────────
    @mcp.tool(name="validate_all", description="Validate all skills in the catalog")
    def validate_all(json_output: bool = False) -> str:
        report = taskmaster.validate_all()
        if json_output:
            return json.dumps(report["stats"], indent=2)
        stats = report["stats"]
        lines = [
            "TaskMaster Validation Report",
            f"{stats['total']} skills checked | {stats['valid']} valid | {len(report['issues'])} issues",
        ]
        if report["issues"]:
            lines.append("Issues:")
            for issue in report["issues"]:
                lines.append(f"  [{issue['dir']}] {issue['issue']}")
        return "\n".join(lines)

    # ── search_skills ───────────────────────────────────────────────
    @mcp.tool(name="search_skills", description="Search skills by keyword query")
    def search_skills(query: str, max_results: int = 10) -> str:
        results = taskmaster.search_skills(query)
        if not results:
            return "No skills found."
        lines = [f"Search results for '{query}':"]
        for r in results[:max_results]:
            fm = r["frontmatter"]
            name = fm.get("name", r["dir"])
            lines.append(f"  {name} ({fm.get('category', '?')}) — {fm.get('risk', '?')}")
        return "\n".join(lines)

    # ── list_categories ─────────────────────────────────────────────
    @mcp.tool(name="list_categories", description="List all skill categories and their counts")
    def list_categories() -> dict[str, int]:
        return tool_list_categories()

    # ── get_skill ───────────────────────────────────────────────────
    @mcp.tool(name="get_skill", description="Get full details of a skill by name or directory")
    def get_skill(name: str) -> dict[str, Any]:
        return tool_get_skill(name)

    # ── suggest ─────────────────────────────────────────────────────
    @mcp.tool(name="suggest", description="Suggest skills for a free-form task description")
    def suggest(task: str, max_results: int = 5) -> str:
        results = taskmaster.suggest_skills(task, max_results=max_results)
        if not results:
            return "No suggestions found."
        lines = [f"Suggestions for '{task}':"]
        for r in results:
            fm = r["frontmatter"]
            name = fm.get("name", r["dir"])
            desc = fm.get("description", "")[:80]
            lines.append(f"  {name:<35} score={r.get('relevance',0):.2f}  {desc}")
        return "\n".join(lines)

    # ── recommend_skills ────────────────────────────────────────────
    @mcp.tool(name="recommend_skills", description="Recommend skills using hybrid semantic+keyword scoring")
    def recommend_skills(task: str, max_results: int = 5, max_risk: str | None = None) -> str:
        return tool_recommend_skills(task, max_results=max_results, max_risk=max_risk)

    # ── compose_skills ──────────────────────────────────────────────
    @mcp.tool(name="compose_skills", description="Compose a dependency-ordered plan from skill names")
    def compose_skills(skills: list[str], json_output: bool = False) -> str:
        return tool_compose_skills(skills, json_output=json_output)

    # ── check_skill ─────────────────────────────────────────────────
    @mcp.tool(name="check_skill", description="Deep-check a single skill by directory name")
    def check_skill(skill_dir: str) -> str:
        skill = taskmaster.parse_skill(taskmaster.SKILLS_DIR / skill_dir)
        if not skill:
            return f"Error: no SKILL.md in '{skill_dir}'"
        fm = skill["frontmatter"]
        lines = [
            f"Skill:  {fm.get('name', '?')}",
            f"Dir:    {skill['dir']}",
            f"Cat:    {fm.get('category', '?')}",
            f"Risk:   {fm.get('risk', '?')}",
            f"Source: {fm.get('source', '?')}",
            f"Size:   {skill['size_bytes']} bytes, {skill['line_count']} body lines",
            f"Desc:   {fm.get('description', '?')[:120]}",
        ]
        deps = fm.get("depends_on")
        if deps:
            lines.append(f"Deps:   {', '.join(deps)}")
        composes = fm.get("composes_with")
        if composes:
            lines.append(f"Comp:   {', '.join(composes)}")
        issues = taskmaster.validate_skill(skill)
        if issues:
            lines.append(f"Issues: {'; '.join(issues)}")
        else:
            lines.append("Status: valid")
        return "\n".join(lines)

    @mcp.tool(name="validate_skill", description="Check a single skill for issues")
    def validate_skill(skill_dir: str) -> str:
        return tool_validate_skill(skill_dir)

    # ── corpus_stats ────────────────────────────────────────────────
    @mcp.tool(name="corpus_stats", description="Show category and risk distributions")
    def corpus_stats(json_output: bool = False) -> str:
        report = taskmaster.validate_all()
        skills = report["skills"]

        cat_counts = Counter(s["frontmatter"].get("category", "?") for s in skills)
        risk_counts = Counter(s["frontmatter"].get("risk", "?") for s in skills)
        total_size = sum(s["size_bytes"] for s in skills)
        total_lines = sum(s["line_count"] for s in skills)

        index = _build_index()
        index_state = "semantic" if index is not None else "keyword (degraded)"

        if json_output:
            return json.dumps({
                "total": len(skills),
                "categories": dict(cat_counts.most_common()),
                "risks": dict(risk_counts),
                "total_size_bytes": total_size,
                "total_lines": total_lines,
                "index_state": index_state,
            }, indent=2)

        lines = [
            f"Skills: {len(skills)}",
            f"Index:  {index_state}",
            f"Size:   {total_size:,} bytes ({total_size/1024:.0f} KB), {total_lines:,} lines",
            "",
            "Categories:",
        ]
        for cat, count in cat_counts.most_common():
            lines.append(f"  {cat:<22} {count}")
        lines.append("")
        lines.append("Risk levels:")
        for risk in ["safe", "medium", "high"]:
            lines.append(f"  {risk:<8} {risk_counts.get(risk, 0)}")
        return "\n".join(lines)

    # ── install_skill ───────────────────────────────────────────────
    @mcp.tool(name="install_skill", description="Install skills to an agent runtime")
    def install_skill(target: str, skills: list[str], scope: str = "project", copy: bool = False) -> dict[str, Any]:
        from taskmaster.errors import InstallError
        from taskmaster.install import install_skills
        try:
            return install_skills(target=target, scope=scope, skill_names=skills, copy=copy)
        except InstallError as e:
            return {"error": "install_failed", "message": str(e)}

    return mcp


# ── Pure-function tool bodies (importable without the [mcp] extra) ─────


def tool_list_categories() -> dict[str, int]:
    """MCP tool: list_categories — pure function."""
    skills = taskmaster.get_all_skills()
    return dict(Counter(s["frontmatter"].get("category", "?") for s in skills).most_common())


def tool_get_skill(name: str) -> dict[str, Any]:
    """MCP tool: get_skill — pure function."""
    all_skills = taskmaster.get_all_skills()
    skill = None
    for s in all_skills:
        if s["dir"] == name or s["frontmatter"].get("name") == name:
            skill = s
            break
    if not skill:
        return {"error": "not_found", "message": f"Skill '{name}' not found"}
    return {
        "name": skill["frontmatter"].get("name", skill["dir"]),
        "frontmatter": skill["frontmatter"],
        "body": skill.get("body", ""),
        "path": str(skill.get("path", "")),
        "size_bytes": skill.get("size_bytes"),
        "line_count": skill.get("line_count"),
        "quality": taskmaster.score_skill_quality(skill),
    }


def tool_recommend_skills(task: str, max_results: int = 5, max_risk: str | None = None) -> str:
    """MCP tool: recommend_skills — pure function."""
    skills = taskmaster.get_all_skills()
    index = _build_index()
    from taskmaster.recommend import recommend_skills as engine_recommend
    results = engine_recommend(task, skills=skills, index=index, k=max_results, max_risk=max_risk)
    if not results:
        return "No recommendations found."
    lines = [f"Recommendations for '{task}':"]
    if results and any(r["degraded"] for r in results):
        lines.append("  (degraded mode — semantic embeddings unavailable)")
    for r in results:
        fm = r["skill"]["frontmatter"]
        name = fm.get("name", r["skill"]["dir"])
        reasons = " | ".join(r["reasons"])
        lines.append(f"  {name:<35} score={r['score']:.3f}  {reasons}")
    return "\n".join(lines)


def tool_compose_skills(skills: list[str], json_output: bool = False) -> str:
    """MCP tool: compose_skills — pure function."""
    all_skills = taskmaster.get_all_skills()
    from taskmaster.compose import compose_skills as engine_compose
    from taskmaster.errors import CycleError
    try:
        plan = engine_compose(skills, skills=all_skills)
    except CycleError as e:
        return f"Error: Dependency cycle detected — {' -> '.join(e.cycle)}"
    except KeyError as e:
        return f"Error: {e}"
    if json_output:
        return json.dumps(plan.to_dict(), indent=2)
    lines = ["Composed plan:"]
    for step in plan.steps:
        deps = ", ".join(step["depends_on"]) if step["depends_on"] else "-"
        lines.append(f"  {step['name']:<35} depends_on: {deps}")
    for w in plan.warnings:
        lines.append(f"  warning: {w}")
    return "\n".join(lines)


def tool_validate_skill(skill_dir: str) -> str:
    """MCP tool: validate_skill — pure function."""
    skill = taskmaster.parse_skill(taskmaster.SKILLS_DIR / skill_dir)
    if not skill:
        return f"Error: no SKILL.md in '{skill_dir}'"
    fm = skill["frontmatter"]
    issues = taskmaster.validate_skill(skill)
    if issues:
        return f"Issues: {'; '.join(issues)}"
    return f"Status: valid ({fm.get('name', skill_dir)})"


def serve(transport: str = "stdio", host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the MCP server."""
    mcp = _make_server()
    if transport == "sse":
        mcp.run(transport="sse", host=host, port=port)
    else:
        mcp.run(transport="stdio")
