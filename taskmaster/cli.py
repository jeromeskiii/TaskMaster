"""TaskMaster CLI dispatch.

All business logic lives in the engine modules; this file is
responsible for argument parsing, command dispatch, and output
rendering. Run with ``python3 taskmaster.py <command>``.
"""

from __future__ import annotations

import argparse
import json
from typing import Callable

import taskmaster

SECONDS_PER_DAY = 86400.0


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

    embed_p = sub.add_parser("embed", help="Build or refresh the embedding index")
    embed_p.add_argument("--rebuild", action="store_true", help="Force a full rebuild")

    recommend_p = sub.add_parser("recommend", help="Recommend skills for a task")
    recommend_p.add_argument("task")
    recommend_p.add_argument("--max", type=int, default=5)
    recommend_p.add_argument("--max-risk", choices=["safe", "medium", "high"])
    recommend_p.add_argument("--json", action="store_true")
    recommend_p.add_argument(
        "--keyword-only",
        action="store_true",
        help="Skip embedding index build; use keyword scoring only",
    )

    compose_p = sub.add_parser("compose", help="Compose a dependency-ordered plan")
    compose_p.add_argument("skills", nargs="+", help="Skill names or directories")
    compose_p.add_argument("--json", action="store_true")

    forge_p = sub.add_parser("forge", help="Create an agent-ready build plan")
    forge_p.add_argument("task", help="Task or feature description")
    forge_p.add_argument("--max", type=int, default=5, help="Max skills to recommend")
    forge_p.add_argument("--max-risk", choices=["safe", "medium", "high"])
    forge_p.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    forge_p.add_argument("--out", help="Write a .taskmaster-style workspace to this directory")

    install_p = sub.add_parser("install", help="Install skills to an agent runtime")
    install_p.add_argument("target", choices=["claude", "qwen", "cursor", "all"])
    install_p.add_argument("--scope", choices=["user", "project"], default="project")
    install_p.add_argument("--skills", help="Comma-separated skill names (default: all)")
    install_p.add_argument("--copy", action="store_true", help="Copy instead of symlink")
    install_p.add_argument("--force", action="store_true", help="Overwrite existing")

    uninstall_p = sub.add_parser("uninstall", help="Remove skills from an agent runtime")
    uninstall_p.add_argument("target", choices=["claude", "qwen", "cursor", "all"])
    uninstall_p.add_argument("--scope", choices=["user", "project"], default="project")

    mcp_p = sub.add_parser("mcp", help="MCP server commands")
    mcp_sub = mcp_p.add_subparsers(dest="mcp_command", help="MCP commands")
    _add_mcp_serve_args(
        mcp_sub.add_parser("serve", help="Start MCP server for agent-to-agent access")
    ).set_defaults(mcp_command="serve")

    _add_mcp_serve_args(
        sub.add_parser("mcp-serve", help="Deprecated alias for 'mcp serve'")
    ).set_defaults(mcp_command="serve")

    # Add context subparsers
    context_p = sub.add_parser("context", help="Manage local context budget and storage")
    context_sub = context_p.add_subparsers(dest="context_command", required=True)

    compress_p = context_sub.add_parser("compress", help="Compress context from stdin or file")
    compress_p.add_argument("file", nargs="?", help="File to compress (reads stdin if omitted)")
    compress_p.add_argument("--max-chars", type=int, default=4000)

    retrieve_p = context_sub.add_parser("retrieve", help="Retrieve original context by handle")
    retrieve_p.add_argument("handle")

    context_sub.add_parser("stats", help="Show context store stats")

    prune_p = context_sub.add_parser("prune", help="Prune old context records")
    prune_p.add_argument("--max-age-days", type=float, default=7.0)

    return parser


def _add_mcp_serve_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--sse", action="store_true", help="Use SSE transport instead of stdio")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port for SSE transport (default: 8000)")
    return parser


def _embedding_index(skills, *, rebuild: bool):
    from taskmaster.corpus import CACHE_DIR
    from taskmaster.embeddings import get_default_provider
    from taskmaster.embeddings.index import EmbeddingIndex
    from taskmaster.embeddings.provider import cache_key

    provider = get_default_provider()
    cache_dir = CACHE_DIR / "embeddings" / cache_key(provider)
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
    if not args.keyword_only:
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

    if results and any(r["degraded"] for r in results):
        print("  (degraded mode — semantic embeddings unavailable)")

    print("\nRecommended skills:")
    for i, r in enumerate(results, 1):
        fm = r["skill"]["frontmatter"]
        print(f"{i}. {fm.get('name', r['skill']['dir'])}")

    if results:
        print("\nWhy:")
        # Show top reasons from the first result
        for reason in results[0]["reasons"]:
            print(f"- {reason}")
    return 0


def _cmd_compose(args) -> int:
    skills = taskmaster.get_all_skills()
    from taskmaster.compose import compose_skills
    from taskmaster.errors import CycleError
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
        print("\nExecution plan:")
        for i, step in enumerate(plan.steps, 1):
            print(f"{i}. {step['name']}")

        if plan.warnings:
            print("\nWarnings:")
            for w in plan.warnings:
                print(f"- {w}")
    return 0


def _cmd_forge(args) -> int:
    skills = taskmaster.get_all_skills()
    index = None
    try:
        index, _ = _embedding_index(skills, rebuild=False)
    except RuntimeError:
        index = None
    from taskmaster.forge import create_forge_plan, write_forge_workspace

    plan = create_forge_plan(
        args.task,
        skills=skills,
        index=index,
        max_skills=args.max,
        max_risk=args.max_risk,
    )
    if args.out:
        output_dir = write_forge_workspace(plan, args.out)
        print(f"Forge workspace written to {output_dir}")
        return 0
    if args.json:
        print(json.dumps(plan.to_dict(), indent=2))
        return 0
    print(plan.to_markdown())
    return 0


def _cmd_validate(args) -> int:
    return taskmaster.print_validation_report(
        taskmaster.validate_all(), json_out=bool(getattr(args, "json", False))
    )


def _cmd_list(args) -> int:
    report = taskmaster.validate_all()
    skills = report["skills"]
    if getattr(args, "category", None):
        skills = [s for s in skills if s["frontmatter"].get("category") == args.category]
    if getattr(args, "risk", None):
        skills = [s for s in skills if s["frontmatter"].get("risk") == args.risk]
    skills.sort(key=lambda s: s["frontmatter"].get("name", s["dir"]))
    taskmaster.print_skills_table(skills, long=bool(getattr(args, "long", False)))
    return 0


def _cmd_search(args) -> int:
    taskmaster.print_search_results(
        taskmaster.search_skills(args.query, fuzzy=not bool(getattr(args, "no_fuzzy", False)))
    )
    return 0


def _cmd_suggest(args) -> int:
    results = taskmaster.suggest_skills(args.task, max_results=getattr(args, "max", 5))
    taskmaster.print_search_results(results, show_scores=True)
    if not results:
        print("\n  Tip: Try broader terms like 'web', 'api', 'security', 'data', 'cloud'")
    return 0


def _cmd_stats(args) -> int:
    taskmaster.print_stats(taskmaster.validate_all(), verbose=bool(getattr(args, "verbose", False)))
    return 0


def _cmd_generate_index(_args) -> int:
    taskmaster.generate_index(taskmaster.validate_all())
    return 0


def _cmd_check(args) -> int:
    skill = taskmaster.parse_skill(taskmaster.SKILLS_DIR / args.skill_dir)
    if not skill:
        print(f"Error: no SKILL.md in '{args.skill_dir}'")
        return 1
    fm = skill["frontmatter"]
    print(f"\n  Skill:  {fm.get('name', '?')}")
    print(f"  Dir:    {skill['dir']}")
    print(f"  Cat:    {fm.get('category', '?')}")
    print(f"  Risk:   {fm.get('risk', '?')}")
    print(f"  Source: {fm.get('source', '?')}")
    print(f"  Size:   {skill['size_bytes']} bytes, {skill['line_count']} body lines")
    print(f"  Desc:   {fm.get('description', '?')[:120]}")
    deps = fm.get('depends_on')
    if deps:
        print(f"  Depends on: {', '.join(deps)}")
    composes = fm.get('composes_with')
    if composes:
        print(f"  Composes with: {', '.join(composes)}")
    issues = taskmaster.validate_skill(skill)
    print(f"  Issues: {', '.join(issues)}" if issues else "  Status: valid")
    return 0


def _cmd_export(args) -> int:
    print(
        taskmaster.export_skills(
            as_json=bool(getattr(args, "json", False)),
            skill_name=getattr(args, "skill", None),
        )
    )
    return 0


def _cmd_diff(args) -> int:
    print(taskmaster.diff_skill(args.skill_dir))
    return 0


def _cmd_quality(_args) -> int:
    taskmaster.print_quality_report(taskmaster.get_all_skills())
    return 0


def _cmd_mcp(args) -> int:
    if args.mcp_command != "serve":
        print("Usage: taskmaster mcp serve [--sse] [--host HOST] [--port PORT]")
        return 1
    try:
        from taskmaster.mcp.server import serve as mcp_serve
    except ImportError as e:
        print(f"Error: MCP server requires the 'mcp' extra.\npip install 'taskmaster[mcp]'\n({e})")
        return 1
    transport = "sse" if args.sse else "stdio"
    mcp_serve(transport=transport, host=args.host, port=args.port)
    return 0


def _cmd_install(args) -> int:
    from taskmaster.errors import InstallError, InstallUsageError
    from taskmaster.install import install_skills
    skill_names = args.skills.split(",") if args.skills else None
    try:
        results = install_skills(
            target=args.target,
            scope=args.scope,
            skill_names=skill_names,
            copy=args.copy,
            force=args.force
        )
        for target, info in results.items():
            print(f"Installed {info['count']} skills to {target} ({info['path']})")
    except InstallUsageError as e:
        print(f"Error: {e}")
        return 2
    except InstallError as e:
        print(f"Error: {e}")
        return 1
    return 0


def _cmd_uninstall(args) -> int:
    from taskmaster.errors import InstallError
    from taskmaster.install import uninstall_skills
    try:
        results = uninstall_skills(target=args.target, scope=args.scope)
        for target, info in results.items():
            if info["status"] == "uninstalled":
                print(f"Uninstalled {info['count']} skills from {target}")
            else:
                print(f"Target {target}: {info.get('message', info['status'])}")
    except InstallError as e:
        print(f"Error: {e}")
        return 1
    return 0


def _cmd_context(args) -> int:
    import sys
    from pathlib import Path
    from taskmaster.context_budget_manager.core import ContextBudgetManager
    
    manager = ContextBudgetManager()
    try:
        if args.context_command == "compress":
            if args.file:
                path = Path(args.file)
                text = path.read_text(encoding="utf-8")
                result = manager.compress(text, source_name=str(path), max_chars=args.max_chars)
            else:
                text = sys.stdin.read()
                result = manager.compress(text, max_chars=args.max_chars)

            print(result.compressed_text)
            print("\n---")
            print(f"handle={result.handle}")
            print(f"type={result.content_type.value}")
            print(f"tokens={result.original_tokens}->{result.compressed_tokens}")
            print(f"saved={result.saved_tokens}")
            print(f"ratio={result.compression_ratio:.2f}")
            return 0

        if args.context_command == "retrieve":
            print(manager.retrieve(args.handle))
            return 0

        if args.context_command == "stats":
            print(manager.stats())
            return 0

        if args.context_command == "prune":
            deleted = manager.prune(args.max_age_days * SECONDS_PER_DAY)
            print(f"Successfully pruned {deleted} context payload(s).")
            return 0
    except Exception as exc:
        print(f"cbm error: {exc}", file=sys.stderr)
        return 1
    return 0


_DISPATCH: dict[str, Callable[..., int]] = {
    "validate": _cmd_validate,
    "list": _cmd_list,
    "search": _cmd_search,
    "suggest": _cmd_suggest,
    "stats": _cmd_stats,
    "generate-index": _cmd_generate_index,
    "check": _cmd_check,
    "export": _cmd_export,
    "diff": _cmd_diff,
    "quality": _cmd_quality,
    "embed": _cmd_embed,
    "recommend": _cmd_recommend,
    "compose": _cmd_compose,
    "forge": _cmd_forge,
    "mcp": _cmd_mcp,
    "mcp-serve": _cmd_mcp,
    "install": _cmd_install,
    "uninstall": _cmd_uninstall,
    "context": _cmd_context,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    handler = _DISPATCH.get(args.command)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    main()
