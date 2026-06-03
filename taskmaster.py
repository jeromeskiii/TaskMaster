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
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from difflib import get_close_matches
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent
SKILLS_DIR = ROOT

CACHE_DIR = ROOT / ".taskmaster_cache"
CACHE_FILE = CACHE_DIR / "skills_cache.json"
CACHE_TTL = 300


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


def parse_skill(dirpath: Path) -> Optional[dict]:
    md_file = dirpath / "SKILL.md"
    if not md_file.exists():
        return None

    text = md_file.read_text(encoding="utf-8")
    fm, body, fm_valid = _parse_frontmatter(text)

    size = len(text.encode("utf-8"))
    lines = body.strip().split("\n") if body.strip() else []

    return {
        "dir": dirpath.name,
        "path": str(md_file),
        "frontmatter": fm,
        "frontmatter_valid": fm_valid,
        "body": body,
        "line_count": len(lines),
        "size_bytes": size,
    }


def _parse_frontmatter(text: str) -> tuple[dict, str, bool]:
    if not text.startswith("---"):
        return {}, text, False
    idx = text.find("---", 3)
    if idx == -1:
        return {}, text, False
    raw = text[3:idx].strip()
    body = text[idx + 3:]
    fm = {}
    for line in raw.splitlines():
        line = line.strip()
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"').strip("'")
    return fm, body, True


def _get_cache_age() -> float:
    if not CACHE_FILE.exists():
        return float("inf")
    return (datetime.now(timezone.utc).timestamp() - CACHE_FILE.stat().st_mtime)


def _read_cache() -> Optional[dict]:
    if _get_cache_age() > CACHE_TTL:
        return None
    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def _write_cache(data: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    tmp = CACHE_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f)
    tmp.replace(CACHE_FILE)


def get_all_skills(use_cache: bool = True) -> list[dict]:
    if use_cache:
        cached = _read_cache()
        if cached:
            return cached["skills"]

    skills = []
    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        skill = parse_skill(d)
        if skill:
            skills.append(skill)

    _write_cache({"skills": skills, "timestamp": datetime.now(timezone.utc).isoformat()})
    return skills


def validate_skill(skill: dict) -> list[str]:
    issues = []
    fm = skill["frontmatter"]

    if not skill["frontmatter_valid"]:
        return ["missing YAML frontmatter"]

    for field in REQUIRED_FIELDS:
        if field not in fm or not fm[field]:
            issues.append(f"missing field '{field}'")

    risk = fm.get("risk", "")
    if risk and risk not in VALID_RISKS:
        issues.append(f"invalid risk '{risk}'")

    cat = fm.get("category", "")
    if cat and cat not in KNOWN_CATEGORIES:
        issues.append(f"unknown category '{cat}'")

    if skill["size_bytes"] < MIN_SIZE:
        issues.append(f"too small ({skill['size_bytes']} bytes)")

    if skill["line_count"] < MIN_LINES:
        issues.append(f"too short ({skill['line_count']} lines)")

    desc = fm.get("description", "")
    if len(desc) < MIN_DESC_LEN:
        issues.append(f"description too short ({len(desc)} chars)")

    return issues


def validate_all() -> dict:
    skills = get_all_skills()
    issues = []
    stats = {k: 0 for k in [
        "total", "valid", "missing_frontmatter", "missing_required_fields",
        "invalid_risk", "unknown_category", "skeleton_skills", "short_descriptions"
    ]}

    for skill in skills:
        skill_issues = validate_skill(skill)
        if skill_issues:
            issues.append({"dir": skill["dir"], "issue": "; ".join(skill_issues)})
            for issue in skill_issues:
                if "frontmatter" in issue:
                    stats["missing_frontmatter"] += 1
                    break
                elif "field" in issue:
                    stats["missing_required_fields"] += 1
                elif "risk" in issue:
                    stats["invalid_risk"] += 1
                elif "category" in issue:
                    stats["unknown_category"] += 1
                elif "small" in issue or "short" in issue:
                    stats["skeleton_skills"] += 1
                elif "description" in issue:
                    stats["short_descriptions"] += 1
        stats["total"] += 1

    stats["valid"] = stats["total"] - len(issues)
    return {"stats": stats, "issues": issues, "skills": skills}


def search_skills(query: str, fuzzy: bool = True) -> list[dict]:
    skills = get_all_skills()
    q = query.lower().strip()
    results = []

    for skill in skills:
        searchable = (
            skill["dir"] + " " +
            " ".join(str(v) for v in skill["frontmatter"].values()) + " " +
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
        if q in fm.get("tags", "").lower():
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

    task_keywords = {
        "web": ["frontend", "browser-automation"],
        "api": ["backend", "api-patterns"],
        "database": ["backend", "data"],
        "security": ["security"],
        "cloud": ["cloud"],
        "ai": ["ai", "ml"],
        "test": ["testing", "quality"],
        "deploy": ["devops", "automation"],
        "frontend": ["frontend"],
        "backend": ["backend"],
        "data": ["data-ai"],
        "code": ["development"],
        "debug": ["debugging", "error-detective"],
        "architecture": ["architecture"],
    }

    task_lower = task.lower()
    matched_cats = set()
    for keyword, cats in task_keywords.items():
        if keyword in task_lower:
            matched_cats.update(cats)

    all_skills = get_all_skills()
    for skill in all_skills:
        fm = skill["frontmatter"]
        cat = fm.get("category", "")
        name = fm.get("name", skill["dir"])

        relevance = 0
        if cat in matched_cats:
            relevance += 5
        if any(kw in name.lower() for kw in task_lower.split()):
            relevance += 8
        if any(kw in fm.get("description", "").lower() for kw in task_lower.split()):
            relevance += 3

        if relevance > 0:
            skill["relevance"] = relevance
            suggestions.append(skill)

    suggestions.sort(key=lambda s: s["relevance"], reverse=True)
    return suggestions[:max_results]


def score_skill_quality(skill: dict) -> dict:
    fm = skill["frontmatter"]
    score = 0
    max_score = 100
    details = {}

    frontmatter_bonus = 0
    for field in ["name", "description", "category", "risk", "source", "date_added", "tags"]:
        if field in fm and fm[field]:
            frontmatter_bonus += 8 if field in ["name", "description"] else 4
    details["frontmatter_completeness"] = min(frontmatter_bonus, 50)
    score += details["frontmatter_completeness"]

    desc = fm.get("description", "")
    details["description_length"] = len(desc)
    if len(desc) >= 100:
        score += 15
    elif len(desc) >= 50:
        score += 10
    elif len(desc) >= MIN_DESC_LEN:
        score += 5

    body_ratio = skill["line_count"] / 50 if skill["line_count"] > 0 else 0
    details["body_lines"] = skill["line_count"]
    score += min(body_ratio * 30, 30)

    has_headings = bool(re.search(r'^#{1,3}\s+\w+', skill["body"], re.MULTILINE))
    has_code_blocks = bool(re.search(r'```', skill["body"]))
    details["has_structure"] = has_headings
    details["has_examples"] = has_code_blocks
    score += 5 if has_headings else 0
    score += 5 if has_code_blocks else 0

    return {"score": min(score, max_score), "details": details}


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
            "tags": fm.get("tags", "").split() if fm.get("tags") else [],
            "path": s["path"],
            "size_bytes": s["size_bytes"],
            "line_count": s["line_count"],
        })

    if as_json:
        return json.dumps({"skills": skill_data, "total": len(skill_data)}, indent=2)
    else:
        lines = ["# TaskMaster Export", f"# {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", f"# Total: {len(skill_data)} skills\n"]
        for s in skill_data:
            lines.append(f"## {s['name']} ({s['category']}) - {s['risk']}")
            lines.append(f"{s['description'][:200]}...")
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

    lines.append("--- Required Fields ---")
    for field in REQUIRED_FIELDS:
        status = "✓" if fm.get(field) else "✗ MISSING"
        lines.append(f"  {field}: {fm.get(field, 'NOT SET')} {status}")

    lines.append("\n--- Optional Fields ---")
    for field in ["source", "date_added", "tags"]:
        val = fm.get(field, "")
        lines.append(f"  {field}: {val if val else '(not set)'}")

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
