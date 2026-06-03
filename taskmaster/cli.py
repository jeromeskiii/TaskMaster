"""TaskMaster CLI dispatch.

All business logic lives in the engine modules; this file is
responsible for argument parsing, command dispatch, and output
rendering. Run with ``python3 taskmaster.py <command>``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import taskmaster
from taskmaster import cli as _self_marker  # noqa: F401  (intentional import path stability)


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

    hygiene_p = sub.add_parser("hygiene", help="Hygiene report")
    normalize_p = sub.add_parser("normalize", help="Normalize metadata (dry-run)")
    related_p = sub.add_parser("related", help="Find related skills")
    related_p.add_argument("skill_ref")
    related_p.add_argument("--max", type=int, default=5)

    embed_p = sub.add_parser("embed", help="Build or refresh the embedding index")
    embed_p.add_argument("--rebuild", action="store_true", help="Force a full rebuild")

    recommend_p = sub.add_parser("recommend", help="Recommend skills for a task")
    recommend_p.add_argument("task")
    recommend_p.add_argument("--max", type=int, default=5)
    recommend_p.add_argument("--max-risk", choices=["safe", "medium", "high"])
    recommend_p.add_argument("--json", action="store_true")

    compose_p = sub.add_parser("compose", help="Compose a dependency-ordered plan")
    compose_p.add_argument("skills", nargs="+", help="Skill names or directories")
    compose_p.add_argument("--json", action="store_true")

    return parser


def _embedding_index(skills, *, rebuild: bool):
    from taskmaster.embeddings import get_default_provider
    from taskmaster.embeddings.index import EmbeddingIndex
    from taskmaster.embeddings.provider import cache_key

    provider = get_default_provider()
    cache_dir = Path(".taskmaster_cache") / "embeddings" / cache_key(provider)
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
    for r in results:
        fm = r["skill"]["frontmatter"]
        print(f"  {fm.get('name', r['skill']['dir']):<35} score={r['score']:.3f}  {' '.join(r['reasons'])}")
    return 0


def _cmd_compose(args) -> int:
    skills = taskmaster.get_all_skills()
    from taskmaster.compose import CycleError, compose_skills
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
        for step in plan.steps:
            deps = ", ".join(step["depends_on"]) if step["depends_on"] else "-"
            print(f"  {step['name']:<35} depends_on: {deps}")
        for w in plan.warnings:
            print(f"  warning: {w}")
    return 0


_DISPATCH = {
    "embed": _cmd_embed,
    "recommend": _cmd_recommend,
    "compose": _cmd_compose,
}


def main() -> None:
    parser = build_parser()
    argv = sys.argv[1:]
    if argv and not argv[0].startswith("-"):
        first = argv[0]
        valid: set[str] = set()
        for action in _subparsers_actions(parser):
            if action.choices:
                valid.update(action.choices.keys())
        if first in valid:
            args = parser.parse_args()
            if args.command in _DISPATCH:
                sys.exit(_DISPATCH[args.command](args))
    # Fall back to legacy dispatch in __init__.py for unchanged commands
    # (or when this entrypoint is invoked without a real CLI argv).
    taskmaster.main()


def _subparsers_actions(parser: argparse.ArgumentParser):
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            yield action


if __name__ == "__main__":
    main()
