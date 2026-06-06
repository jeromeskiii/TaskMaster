#!/usr/bin/env python3
"""TaskMaster CLI shim.

The implementation lives in the ``taskmaster`` package. This module is kept
so that ``python3 taskmaster.py <command>`` continues to work as a shortcut
for the installed console script.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the repository root is on sys.path when invoked as a script so that
# the sibling ``taskmaster`` package can be imported.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from taskmaster import (  # noqa: E402  (path setup above must run first)
    CACHE_DIR,
    CACHE_FILE,
    CACHE_TTL,
    KNOWN_CATEGORIES,
    MIN_DESC_LEN,
    MIN_LINES,
    MIN_SIZE,
    REQUIRED_FIELDS,
    SKILLS_DIR,
    VALID_RISKS,
    SkillRecord,
    UniqueKeyLoader,
    _as_list,
    _flatten_text,
    _get_cache_age,
    _normalize_frontmatter_value,
    _parse_frontmatter,
    _read_cache,
    _tokenize_text,
    _write_cache,
    diff_skill,
    export_skills,
    get_all_skills,
    parse_skill,
    related_skills,
    score_skill_quality,
    search_skills,
    suggest_skills,
    validate_all,
    validate_skill,
)
from taskmaster import cli as _cli  # noqa: E402


def main() -> int:
    return _cli.main()


if __name__ == "__main__":
    raise SystemExit(main())
