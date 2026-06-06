"""TaskMaster package API and CLI entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import corpus as _corpus
from . import discovery as _discovery
from . import validation as _validation

SkillRecord = _corpus.SkillRecord
UniqueKeyLoader = _corpus.UniqueKeyLoader
SKILLS_DIR = _corpus.SKILLS_DIR
CACHE_DIR = _corpus.CACHE_DIR
CACHE_FILE = _corpus.CACHE_FILE
CACHE_TTL = _corpus.CACHE_TTL
REQUIRED_FIELDS = _validation.REQUIRED_FIELDS
VALID_RISKS = _validation.VALID_RISKS
KNOWN_CATEGORIES = _validation.KNOWN_CATEGORIES
MIN_SIZE = _validation.MIN_SIZE
MIN_LINES = _validation.MIN_LINES
MIN_DESC_LEN = _validation.MIN_DESC_LEN

_parse_frontmatter = _corpus._parse_frontmatter
_get_cache_age = _corpus._get_cache_age
_read_cache = _corpus._read_cache
_write_cache = _corpus._write_cache
_flatten_text = _corpus._flatten_text
_tokenize_text = _corpus._tokenize_text
_as_list = _corpus._as_list
_normalize_frontmatter_value = _corpus._normalize_frontmatter_value


def _record_to_dict(record):
    return record.to_dict() if isinstance(record, SkillRecord) else record


def parse_skill(dirpath: str | Path) -> Optional[dict]:
    record = _corpus.parse_skill(Path(dirpath))
    return _record_to_dict(record) if record else None


def get_all_skills(use_cache: bool = True) -> list[dict]:
    return [_record_to_dict(skill) for skill in _corpus.get_all_skills(use_cache=use_cache)]


def validate_skill(skill: SkillRecord | dict) -> list[str]:
    return _validation.validate_skill(skill)


def validate_all() -> dict:
    return _validation.validate_all(get_all_skills())


def search_skills(query: str, fuzzy: bool = True) -> list[dict]:
    return _discovery.search_skills(get_all_skills(), query, fuzzy=fuzzy)


def suggest_skills(task: str, max_results: int = 5) -> list[dict]:
    return _discovery.suggest_skills(get_all_skills(), task, max_results=max_results)


def related_skills(skill_ref: str, max_results: int = 5) -> list[dict]:
    return _discovery.related_skills(get_all_skills(), skill_ref, max_results=max_results)


def score_skill_quality(skill: SkillRecord | dict) -> dict:
    return _validation.score_skill_quality(skill)


def export_skills(as_json: bool = False, skill_name: Optional[str] = None) -> str:
    skills = get_all_skills()
    if skill_name:
        skills = [skill for skill in skills if skill_name in skill["dir"]]
        if not skills:
            return f"Error: No skill found matching '{skill_name}'"

    skill_data = []
    for skill in skills:
        fm = skill["frontmatter"]
        skill_data.append(
            {
                "name": fm.get("name", skill["dir"]),
                "category": fm.get("category", "?"),
                "risk": fm.get("risk", "?"),
                "description": fm.get("description", ""),
                "source": fm.get("source", ""),
                "tags": _as_list(fm.get("tags")),
                "path": skill["path"],
                "size_bytes": skill["size_bytes"],
                "line_count": skill["line_count"],
                "frontmatter_valid": skill.get("frontmatter_valid", False),
                "frontmatter_error": skill.get("frontmatter_error"),
            }
        )

    if as_json:
        return json.dumps({"skills": skill_data, "total": len(skill_data)}, indent=2)

    lines = [
        "# TaskMaster Export",
        f"# {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"# Total: {len(skill_data)} skills\n",
    ]
    for skill in skill_data:
        lines.append(f"## {skill['name']} ({skill['category']}) - {skill['risk']}")
        if skill["frontmatter_valid"]:
            lines.append(f"{skill['description'][:200]}...")
        else:
            lines.append(f"Frontmatter parse error: {skill['frontmatter_error']}")
        lines.append(f"- Path: {skill['path']}")
        lines.append("")
    return "\n".join(lines)


def diff_skill(skill_dir: str) -> str:
    skill_path = SKILLS_DIR / skill_dir
    if not skill_path.is_dir():
        return f"Error: '{skill_dir}' not found"

    skill = parse_skill(skill_path)
    if not skill:
        return f"Error: No SKILL.md in '{skill_dir}'"

    fm = skill["frontmatter"]
    lines = [f"=== {skill_dir} ===", ""]
    if not skill["frontmatter_valid"]:
        lines.extend(["--- Frontmatter Error ---", f"  {skill.get('frontmatter_error') or 'missing YAML frontmatter'}", ""])

    lines.append("--- Required Fields ---")
    for field in REQUIRED_FIELDS:
        status = "OK" if fm.get(field) else "MISSING"
        lines.append(f"  {field}: {fm.get(field, 'NOT SET')} {status}")

    lines.append("\n--- Optional Fields ---")
    for field in ["source", "date_added", "tags"]:
        value = fm.get(field, "")
        formatted = ", ".join(_as_list(value)) if field == "tags" else value
        lines.append(f"  {field}: {formatted if formatted else '(not set)'}")

    quality = score_skill_quality(skill)
    lines.append("\n--- Quality Metrics ---")
    lines.append(f"  Quality Score: {quality['score']}/100")
    for key, value in quality["details"].items():
        lines.append(f"    {key}: {value}")

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
    print(f"\n{'=' * 60}")
    print("  TaskMaster Validation Report")
    print(f"  {stats['total']} skills checked  |  {stats['valid']} valid  |  {len(issues)} issues")
    print(f"{'=' * 60}\n")

    labels = [
        ("missing_frontmatter", "Missing frontmatter"),
        ("missing_required_fields", "Missing required fields"),
        ("frontmatter_parse_errors", "Frontmatter parse errors"),
        ("invalid_risk", "Invalid risk values"),
        ("unknown_category", "Unknown categories"),
        ("skeleton_skills", "Skeleton/short skills"),
        ("short_descriptions", "Short descriptions"),
    ]
    for key, label in labels:
        if stats[key]:
            print(f"  {label}: {stats[key]}")

    if issues:
        print("\n  --- Issues ---")
        for issue in issues:
            print(f"  [{issue['dir']}] {issue['issue']}")
        print()

    return 1 if issues else 0


def print_skills_table(skills: list[dict], long: bool = False) -> None:
    if long:
        print(f"\n{'Skill':<35} {'Category':<22} {'Risk':<8} {'Lines':>6} {'Size':>10}")
        print("-" * 90)
        for skill in skills:
            fm = skill["frontmatter"]
            print(
                f"  {fm.get('name', skill['dir'])[:34]:<33}  "
                f"{fm.get('category', '?')[:21]:<20}  "
                f"{fm.get('risk', '?')[:7]:<6}  "
                f"{skill['line_count']:>5}  {skill['size_bytes']:>8}B"
            )
        return

    print(f"\n{'Skill':<35} {'Cat':<22} {'Risk':<8}")
    print("-" * 70)
    for skill in skills:
        fm = skill["frontmatter"]
        print(f"  {fm.get('name', skill['dir'])[:34]:<33}  {fm.get('category', '?')[:21]:<20}  {fm.get('risk', '?')[:7]:<6}")


def print_search_results(results: list[dict], show_scores: bool = True) -> None:
    if not results:
        print("No skills found matching your query.")
        return

    print(f"\n{'Skill':<35} {'Category':<22} {'Risk':<8} {'Match'}")
    print("-" * 80)
    for result in results:
        skill = result.get("skill", result)
        fm = skill["frontmatter"] if isinstance(skill, dict) else skill.frontmatter
        skill_dir = skill["dir"] if isinstance(skill, dict) else skill.dir
        name = fm.get("name", skill_dir)[:34]
        category = fm.get("category", "?")[:21]
        risk = fm.get("risk", "?")[:7]
        if show_scores:
            score = result.get("relevance", 0)
            bar = "#" * min(int(score / 3), 10)
            print(f"  {name:<33}  {category:<20}  {risk:<6}  {bar}")
        else:
            print(f"  {name:<33}  {category:<20}  {risk:<6}")


def print_stats(report: dict, verbose: bool = False) -> None:
    skills = report["skills"]
    cat_counts = Counter(skill["frontmatter"].get("category", "?") for skill in skills)
    risk_counts = Counter(skill["frontmatter"].get("risk", "?") for skill in skills)
    total_size = sum(skill["size_bytes"] for skill in skills)
    total_lines = sum(skill["line_count"] for skill in skills)

    print("\n  --- Category Distribution ---")
    for category, count in cat_counts.most_common():
        print(f"  {category:<22} {count:>3} {'#' * (count // 5)}")

    print("\n  --- Risk Distribution ---")
    for risk in ["safe", "medium", "high"]:
        count = risk_counts.get(risk, 0)
        print(f"  {risk:<8} {count:>3} {'#' * (count // 5)}")

    print("\n  --- Totals ---")
    print(f"  Skills:     {len(skills)}")
    print(f"  Total size: {total_size:,} bytes ({total_size / 1024:.0f} KB)")
    print(f"  Total body: {total_lines:,} lines")
    print(f"  Avg size:   {total_size // max(len(skills), 1)} bytes/skill")

    if verbose:
        cached = _read_cache()
        print("\n  --- Cache ---")
        print(f"  Cached:     {'Yes' if cached else 'No (will be generated on next run)'}")
        if cached:
            print(f"  Timestamp:  {cached.get('timestamp', 'Unknown')}")


def generate_index(report: dict) -> None:
    skills = report["skills"]
    by_category: dict[str, list[dict]] = {}
    for skill in skills:
        category = skill["frontmatter"].get("category", "uncategorized")
        by_category.setdefault(category, []).append(skill)

    lines = [
        "---\n",
        "# TaskMaster - Skill Index\n\n",
        f"**Total Skills:** {len(skills)}\n",
        f"**Categories:** {len(by_category)}\n",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC\n\n",
        "## Quick Stats\n\n",
        "| Category | Count |\n",
        "|----------|-------|\n",
    ]
    for category in sorted(by_category):
        lines.append(f"| {category} | {len(by_category[category])} |\n")

    for category in sorted(by_category):
        category_skills = sorted(by_category[category], key=lambda item: item["frontmatter"].get("name", item["dir"]))
        lines.append(f"\n## {category.title().replace('-', ' ')} ({len(category_skills)} skills)\n\n")
        lines.append("| Skill | Risk | Description |\n")
        lines.append("|-------|------|-------------|\n")
        for skill in category_skills:
            fm = skill["frontmatter"]
            name = fm.get("name", skill["dir"])
            link = f"[{name}]({skill['dir']}/SKILL.md)"
            lines.append(f"| {link} | {fm.get('risk', '?')} | {fm.get('description', '')[:80]}... |\n")

    (SKILLS_DIR / "INDEX.md").write_text("".join(lines), encoding="utf-8")
    print(f"INDEX.md regenerated ({len(skills)} skills, {len(by_category)} categories)")


def print_quality_report(skills: list[dict]) -> None:
    scored = []
    for skill in skills:
        quality = score_skill_quality(skill)
        skill = dict(skill)
        skill["quality_score"] = quality["score"]
        skill["quality_details"] = quality["details"]
        scored.append(skill)

    scored.sort(key=lambda skill: skill["quality_score"], reverse=True)
    print(f"\n{'Skill':<35} {'Score':>6} {'Lines':>6} {'Desc':>6} {'Struct'}")
    print("-" * 65)
    for skill in scored:
        fm = skill["frontmatter"]
        details = skill["quality_details"]
        print(
            f"  {fm.get('name', skill['dir'])[:34]:<33}  "
            f"{skill['quality_score']:>5}  "
            f"{details.get('body_lines', 0):>5}  "
            f"{min(len(fm.get('description', '')), 999):>5}  "
            f"{'Y' if details.get('has_structure') else 'N'}"
        )


build_hygiene_report = _validation.build_hygiene_report
build_normalization_report = _validation.build_normalization_report


def main() -> int:
    from taskmaster import cli as _cli

    return _cli.main()

