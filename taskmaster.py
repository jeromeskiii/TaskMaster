#!/usr/bin/env python3
"""
TaskMaster CLI — manage, validate, search, and index 269 AI agent skills.

Usage:
    python3 taskmaster.py validate          # Audit all skills for issues
    python3 taskmaster.py list              # List all skills as a table
    python3 taskmaster.py search <query>    # Full-text search across all fields
    python3 taskmaster.py stats             # Distribution by category and risk
    python3 taskmaster.py generate-index    # Regenerate INDEX.md from disk
    python3 taskmaster.py check <skill>     # Deep-check a single skill
    python3 taskmaster.py suggest <task>    # Suggest skills for a task
    python3 taskmaster.py export [--json]   # Export all skills as JSON
    python3 taskmaster.py diff <skill>      # Compare skill metadata to schema
    python3 taskmaster.py quality           # Score all skills by completeness
    python3 taskmaster.py bulk-import <dir> # Import skills from another directory
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from difflib import get_close_matches
from pathlib import Path
from typing import Optional

from taskmaster import corpus as _corpus
from taskmaster import validation as _validation

ROOT = Path(__file__).resolve().parent
SKILLS_DIR = _corpus.SKILLS_DIR

CACHE_DIR = _corpus.CACHE_DIR
CACHE_FILE = _corpus.CACHE_FILE
CACHE_TTL = _corpus.CACHE_TTL


REQUIRED_FIELDS = ["name", "description", "category", "risk"]
VALID_RISKS = {"safe", "medium", "high"}
KNOWN_CATEGORIES = {
    "agent-behavior", "ai", "ai-agents", "ai-research", "automation",
    "backend", "browser-automation", "cloud", "data", "data-ai",
    "development", "framework", "frontend", "mcp", "media", "memory",
    "meta", "networking", "security", "voice-agents",
}
MIN_SIZE = 500
MIN_LINES = 10
MIN_DESC_LEN = 30


SkillRecord = _corpus.SkillRecord
UniqueKeyLoader = _corpus.UniqueKeyLoader


def _record_to_dict(record):
    return record.to_dict() if isinstance(record, SkillRecord) else record


def parse_skill(dirpath: Path) -> Optional[dict]:
    return _record_to_dict(_corpus.parse_skill(dirpath))


def _parse_frontmatter(text: str) -> tuple[dict, str, bool, Optional[str]]:
    return _corpus._parse_frontmatter(text)


def _get_cache_age() -> float:
    return _corpus._get_cache_age()


def _read_cache() -> Optional[dict]:
    return _corpus._read_cache()


def _write_cache(data: dict) -> None:
    _corpus._write_cache(data)


def _flatten_text(value: object) -> str:
    return _corpus._flatten_text(value)


def _tokenize_text(value: object) -> set[str]:
    return _corpus._tokenize_text(value)


def _as_list(value: object) -> list[str]:
    return _corpus._as_list(value)


def _normalize_frontmatter_value(value: object) -> object:
    return _corpus._normalize_frontmatter_value(value)


def get_all_skills(use_cache: bool = True) -> list[dict]:
    return [_record_to_dict(skill) for skill in _corpus.get_all_skills(use_cache=use_cache)]


def validate_skill(skill: dict) -> list[str]:
    return _validation.validate_skill(skill)


def validate_all() -> dict:
    return _validation.validate_all(get_all_skills())


def search_skills(query: str, fuzzy: bool = True) -> list[dict]:
    skills = get_all_skills()
    q = query.lower().strip()
    results = []

    for skill in skills:
        searchable = (
            skill["dir"] + " " +
            " ".join(_flatten_text(v) for v in skill["frontmatter"].values()) + " " +
            skill["body"]
        ).lower()

        score = 0
        name = skill["dir"]
        fm = skill["frontmatter"]

        if q in name.lower():
            score += 20
        elif fuzzy:
            matches = get_close_matches(q, [name.lower()], n=1, cutoff=0.6)
            if matches:
                score += 10

        if q in fm.get("description", "").lower():
            score += 8
        if q in fm.get("category", "").lower():
            score += 4
        if q in _flatten_text(fm.get("tags", "")).lower():
            score += 6

        body_words = set(re.findall(r'\w+', searchable))
        query_words = set(re.findall(r'\w+', q))
        overlap = len(body_words & query_words)
        score += min(overlap * 0.5, 10)

        if score > 0:
            skill["relevance"] = score
            results.append(skill)

    results.sort(key=lambda s: s["relevance"], reverse=True)
    return results


def suggest_skills(task: str, max_results: int = 5) -> list[dict]:
    suggestions = []

    category_hints = {
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
    related_terms = {
        "debug": {"bug", "bugs", "debugging", "troubleshooting"},
        "test": {"test", "tests", "testing", "qa"},
        "deploy": {"deploy", "deployment", "release", "shipping"},
        "architecture": {"architecture", "architect"},
        "api": {"api", "rest", "graphql", "endpoint"},
    }

    task_lower = task.lower()
    task_terms = _tokenize_text(task_lower)
    matched_cats = set()
    expanded_terms = set(task_terms)

    for keyword, cats in category_hints.items():
        if keyword in task_terms:
            matched_cats.update(cats)
    for keyword, terms in related_terms.items():
        if keyword in task_terms:
            expanded_terms.update(terms)

    all_skills = get_all_skills()
    for skill in all_skills:
        fm = skill["frontmatter"]
        cat = fm.get("category", "")
        name = fm.get("name", skill["dir"])
        name_terms = _tokenize_text(name)
        searchable_terms = _tokenize_text(
            f"{name} {fm.get('description', '')} {_flatten_text(fm.get('tags', []))} {skill['body']}"
        )

        relevance = 0
        if cat in matched_cats:
            relevance += 5
        if name_terms & expanded_terms:
            relevance += 8
        overlap = searchable_terms & expanded_terms
        relevance += min(len(overlap) * 2, 8)

        if relevance > 0:
            skill["relevance"] = relevance
            suggestions.append(skill)

    suggestions.sort(key=lambda s: s["relevance"], reverse=True)
    return suggestions[:max_results]


def score_skill_quality(skill: dict) -> dict:
    return _validation.score_skill_quality(skill)


def export_skills(as_json: bool = False, skill_name: Optional[str] = None) -> str:
    skills = get_all_skills()

    if skill_name:
        skills = [s for s in skills if skill_name in s["dir"]]
        if not skills:
            return f"Error: No skill found matching '{skill_name}'"

    skill_data = []
    for s in skills:
        fm = s["frontmatter"]
        skill_data.append({
            "name": fm.get("name", s["dir"]),
            "category": fm.get("category", "?"),
            "risk": fm.get("risk", "?"),
            "description": fm.get("description", ""),
            "source": fm.get("source", ""),
            "tags": _as_list(fm.get("tags")),
            "path": s["path"],
            "size_bytes": s["size_bytes"],
            "line_count": s["line_count"],
            "frontmatter_valid": s.get("frontmatter_valid", False),
            "frontmatter_error": s.get("frontmatter_error"),
        })

    if as_json:
        return json.dumps({"skills": skill_data, "total": len(skill_data)}, indent=2)
    else:
        lines = ["# TaskMaster Export", f"# {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", f"# Total: {len(skill_data)} skills\n"]
        for s in skill_data:
            lines.append(f"## {s['name']} ({s['category']}) - {s['risk']}")
            if s["frontmatter_valid"]:
                lines.append(f"{s['description'][:200]}...")
            else:
                lines.append(f"Frontmatter parse error: {s['frontmatter_error']}")
            lines.append(f"- Path: {s['path']}")
            lines.append("")
        return "\n".join(lines)


def diff_skill(skill_dir: str) -> str:
    d = SKILLS_DIR / skill_dir
    if not d.is_dir():
        return f"Error: '{skill_dir}' not found"

    skill = parse_skill(d)
    if not skill:
        return f"Error: No SKILL.md in '{skill_dir}'"

    fm = skill["frontmatter"]
    lines = [f"=== {skill_dir} ===", ""]

    if not skill["frontmatter_valid"]:
        lines.append("--- Frontmatter Error ---")
        lines.append(f"  {skill.get('frontmatter_error') or 'missing YAML frontmatter'}")
        lines.append("")

    lines.append("--- Required Fields ---")
    for field in REQUIRED_FIELDS:
        status = "✓" if fm.get(field) else "✗ MISSING"
        lines.append(f"  {field}: {fm.get(field, 'NOT SET')} {status}")

    lines.append("\n--- Optional Fields ---")
    for field in ["source", "date_added", "tags"]:
        val = fm.get(field, "")
        formatted = ", ".join(_as_list(val)) if field == "tags" else val
        lines.append(f"  {field}: {formatted if formatted else '(not set)'}")

    lines.append("\n--- Quality Metrics ---")
    quality = score_skill_quality(skill)
    lines.append(f"  Quality Score: {quality['score']}/100")
    for k, v in quality["details"].items():
        lines.append(f"    {k}: {v}")

    lines.append("\n--- Content Stats ---")
    lines.append(f"  Size: {skill['size_bytes']} bytes")
    lines.append(f"  Body lines: {skill['line_count']}")
    lines.append(f"  Frontmatter valid: {skill['frontmatter_valid']}")

    return "\n".join(lines)


def print_validation_report(report: dict, json_out: bool = False) -> int:
    if json_out:
        print(json.dumps(report["stats"], indent=2))
        for issue in report["issues"]:
            print(json.dumps(issue))
        return 1 if report["issues"] else 0

    stats = report["stats"]
    issues = report["issues"]

    print(f"\n{'='*60}")
    print(f"  TaskMaster Validation Report")
    print(f"  {stats['total']} skills checked  |  {stats['valid']} valid  |  {len(issues)} issues")
    print(f"{'='*60}\n")

    for key, label in [
        ("missing_frontmatter", "Missing frontmatter"),
        ("missing_required_fields", "Missing required fields"),
        ("frontmatter_parse_errors", "Frontmatter parse errors"),
        ("invalid_risk", "Invalid risk values"),
        ("unknown_category", "Unknown categories"),
        ("skeleton_skills", "Skeleton/short skills"),
        ("short_descriptions", "Short descriptions"),
    ]:
        if stats[key]:
            print(f"  {label}: {stats[key]}")

    if issues:
        print(f"\n  --- Issues ---")
        for issue in issues:
            print(f"  [{issue['dir']}] {issue['issue']}")
        print()

    return 1 if issues else 0


def print_skills_table(skills: list[dict], long: bool = False) -> None:
    if long:
        print(f"\n{'Skill':<35} {'Category':<22} {'Risk':<8} {'Lines':>6} {'Size':>10}")
        print("-" * 90)
        for s in skills:
            fm = s["frontmatter"]
            name = fm.get("name", s["dir"])[:34]
            cat = fm.get("category", "?")[:21]
            risk = fm.get("risk", "?")[:7]
            print(f"  {name:<33}  {cat:<20}  {risk:<6}  {s['line_count']:>5}  {s['size_bytes']:>8}B")
    else:
        print(f"\n{'Skill':<35} {'Cat':<22} {'Risk':<8}")
        print("-" * 70)
        for s in skills:
            fm = s["frontmatter"]
            name = fm.get("name", s["dir"])[:34]
            cat = fm.get("category", "?")[:21]
            risk = fm.get("risk", "?")[:7]
            print(f"  {name:<33}  {cat:<20}  {risk:<6}")


def print_search_results(results: list[dict], show_scores: bool = True) -> None:
    if not results:
        print("No skills found matching your query.")
        return
    print(f"\n{'Skill':<35} {'Category':<22} {'Risk':<8} {'Match'}")
    print("-" * 80)
    for s in results:
        fm = s["frontmatter"]
        name = fm.get("name", s["dir"])[:34]
        cat = fm.get("category", "?")[:21]
        risk = fm.get("risk", "?")[:7]
        if show_scores:
            score = s.get("relevance", 0)
            bar = "█" * min(int(score / 3), 10)
            print(f"  {name:<33}  {cat:<20}  {risk:<6}  {bar}")
        else:
            print(f"  {name:<33}  {cat:<20}  {risk:<6}")


def print_stats(report: dict, verbose: bool = False) -> None:
    skills = report["skills"]
    cat_counts = Counter(s["frontmatter"].get("category", "?") for s in skills)
    risk_counts = Counter(s["frontmatter"].get("risk", "?") for s in skills)
    total_size = sum(s["size_bytes"] for s in skills)
    total_lines = sum(s["line_count"] for s in skills)

    print(f"\n  --- Category Distribution ---")
    for cat, count in cat_counts.most_common():
        bar = "█" * (count // 5)
        print(f"  {cat:<22} {count:>3} {bar}")

    print(f"\n  --- Risk Distribution ---")
    for risk in ["safe", "medium", "high"]:
        count = risk_counts.get(risk, 0)
        bar = "█" * (count // 5)
        icon = {"safe": "🟢", "medium": "🟡", "high": "🔴"}.get(risk, "⚪")
        print(f"  {icon} {risk:<8} {count:>3} {bar}")

    print(f"\n  --- Totals ---")
    print(f"  Skills:     {len(skills)}")
    print(f"  Total size: {total_size:,} bytes ({total_size/1024:.0f} KB)")
    print(f"  Total body: {total_lines:,} lines")
    print(f"  Avg size:   {total_size//max(len(skills),1)} bytes/skill")

    if verbose:
        print(f"\n  --- Cache ---")
        cached = _read_cache()
        if cached:
            print(f"  Cached:     Yes")
            print(f"  Timestamp:  {cached.get('timestamp', 'Unknown')}")
        else:
            print(f"  Cached:     No (will be generated on next run)")


def generate_index(report: dict) -> None:
    skills = report["skills"]
    by_category: dict[str, list[dict]] = {}
    for s in skills:
        cat = s["frontmatter"].get("category", "uncategorized")
        by_category.setdefault(cat, []).append(s)

    lines = []
    lines.append("---\n")
    lines.append(f"# TaskMaster - Skill Index\n\n")
    lines.append(f"**Total Skills:** {len(skills)}\n")
    lines.append(f"**Categories:** {len(by_category)}\n")
    lines.append(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC\n\n")
    lines.append("## Quick Stats\n\n")
    lines.append("| Category | Count |\n")
    lines.append("|----------|-------|\n")
    for cat in sorted(by_category.keys()):
        lines.append(f"| {cat} | {len(by_category[cat])} |\n")

    for cat in sorted(by_category.keys()):
        cat_skills = sorted(by_category[cat], key=lambda s: s["frontmatter"].get("name", s["dir"]))
        lines.append(f"\n## {cat.title().replace('-', ' ')} ({len(cat_skills)} skills)\n\n")
        lines.append("| Skill | Risk | Description |\n")
        lines.append("|-------|------|-------------|\n")
        for s in cat_skills:
            fm = s["frontmatter"]
            name = fm.get("name", s["dir"])
            risk = fm.get("risk", "?")
            desc = fm.get("description", "")[:80]
            link = f"[{name}]({s['dir']}/SKILL.md)"
            lines.append(f"| {link} | {risk} | {desc}... |\n")

    index_path = SKILLS_DIR / "INDEX.md"
    index_path.write_text("".join(lines))
    print(f"✓ INDEX.md regenerated ({len(skills)} skills, {len(by_category)} categories)")


def print_quality_report(skills: list[dict]) -> None:
    scored = []
    for skill in skills:
        q = score_skill_quality(skill)
        skill["quality_score"] = q["score"]
        skill["quality_details"] = q["details"]
        scored.append(skill)

    scored.sort(key=lambda s: s["quality_score"], reverse=True)

    print(f"\n{'Skill':<35} {'Score':>6} {'Lines':>6} {'Desc':>6} {'Struct'}")
    print("-" * 65)
    for s in scored:
        fm = s["frontmatter"]
        name = fm.get("name", s["dir"])[:34]
        q = s["quality_score"]
        details = s["quality_details"]
        desc_len = min(len(fm.get("description", "")), 999)
        struct = "Y" if details.get("has_structure") else "N"
        print(f"  {name:<33}  {q:>5}  {details.get('body_lines', 0):>5}  {desc_len:>5}  {struct}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="TaskMaster CLI — manage 269 AI agent skills",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 taskmaster.py validate
  python3 taskmaster.py search "postgres"
  python3 taskmaster.py suggest "I need to debug a production issue"
  python3 taskmaster.py quality
  python3 taskmaster.py export --json > skills.json
  python3 taskmaster.py diff bug-hunter
        """
    )
    sub = parser.add_subparsers(dest="command", help="Commands")

    validate_p = sub.add_parser("validate", help="Validate all skills")
    validate_p.add_argument("--json", action="store_true", help="JSON output")

    list_p = sub.add_parser("list", help="List all skills")
    list_p.add_argument("--long", action="store_true", help="Show sizes and line counts")
    list_p.add_argument("--category", help="Filter by category")
    list_p.add_argument("--risk", help="Filter by risk level")

    search_p = sub.add_parser("search", help="Search skills")
    search_p.add_argument("query", help="Search query")
    search_p.add_argument("--no-fuzzy", action="store_true", help="Disable fuzzy matching")

    suggest_p = sub.add_parser("suggest", help="Suggest skills for a task")
    suggest_p.add_argument("task", help="Task description")
    suggest_p.add_argument("--max", type=int, default=5, help="Max results")

    stats_p = sub.add_parser("stats", help="Show distribution statistics")
    stats_p.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    gen_p = sub.add_parser("generate-index", help="Regenerate INDEX.md")

    check_p = sub.add_parser("check", help="Deep-check a single skill")
    check_p.add_argument("skill_dir", help="Skill directory name")

    export_p = sub.add_parser("export", help="Export skills")
    export_p.add_argument("--json", action="store_true", help="JSON output")
    export_p.add_argument("--skill", help="Export specific skill")

    diff_p = sub.add_parser("diff", help="Compare skill to schema")
    diff_p.add_argument("skill_dir", help="Skill directory name")

    quality_p = sub.add_parser("quality", help="Score all skills by completeness")

    args = parser.parse_args()

    if args.command == "validate":
        report = validate_all()
        sys.exit(print_validation_report(report, json_out=getattr(args, "json", False)))

    elif args.command == "list":
        report = validate_all()
        skills = report["skills"]
        if getattr(args, "category", None):
            skills = [s for s in skills if s["frontmatter"].get("category") == args.category]
        if getattr(args, "risk", None):
            skills = [s for s in skills if s["frontmatter"].get("risk") == args.risk]
        skills.sort(key=lambda s: s["frontmatter"].get("name", s["dir"]))
        print_skills_table(skills, long=getattr(args, "long", False))

    elif args.command == "search":
        results = search_skills(args.query, fuzzy=not getattr(args, "no_fuzzy", False))
        print_search_results(results)

    elif args.command == "suggest":
        results = suggest_skills(args.task, max_results=getattr(args, "max", 5))
        print_search_results(results, show_scores=True)
        if not results:
            print("\n  Tip: Try broader terms like 'web', 'api', 'security', 'data', 'cloud'")

    elif args.command == "stats":
        report = validate_all()
        print_stats(report, verbose=getattr(args, "verbose", False))

    elif args.command == "generate-index":
        report = validate_all()
        generate_index(report)

    elif args.command == "check":
        d = SKILLS_DIR / args.skill_dir
        if not d.is_dir():
            print(f"Error: '{args.skill_dir}' not found")
            sys.exit(1)
        skill = parse_skill(d)
        if not skill:
            print(f"Error: no SKILL.md in '{args.skill_dir}'")
            sys.exit(1)
        fm = skill["frontmatter"]
        print(f"\n  Skill:  {fm.get('name', '?')}")
        print(f"  Dir:    {skill['dir']}")
        print(f"  Cat:    {fm.get('category', '?')}")
        print(f"  Risk:   {fm.get('risk', '?')}")
        print(f"  Source: {fm.get('source', '?')}")
        print(f"  Size:   {skill['size_bytes']} bytes, {skill['line_count']} body lines")
        print(f"  Desc:   {fm.get('description', '?')[:120]}")
        issues = validate_skill(skill)
        if issues:
            print(f"  Issues: {', '.join(issues)}")
        else:
            print(f"  Status: ✓ valid")

    elif args.command == "export":
        output = export_skills(as_json=getattr(args, "json", False), skill_name=getattr(args, "skill", None))
        print(output)

    elif args.command == "diff":
        print(diff_skill(args.skill_dir))

    elif args.command == "quality":
        skills = get_all_skills()
        print_quality_report(skills)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
