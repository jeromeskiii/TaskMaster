"""Skill installer for agent runtimes.

Supports symlinking (default) or copying skills into Claude, Cursor, and Qwen
expected skill directories.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from difflib import get_close_matches
from pathlib import Path
from typing import Any

from .errors import InstallError, InstallUsageError

TARGET_PATHS = {
    "user": {
        "claude": "~/.claude/skills",
        "qwen": "~/.qwen/skills",
        "cursor": "~/.cursor/skills",
    },
    "project": {
        "claude": ".claude/skills",
        "qwen": ".qwen/skills",
        "cursor": ".cursor/skills",
    },
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _closest_matches(needle: str, haystack: list[str], n: int = 3) -> list[str]:
    """Return up to ``n`` closest matches for ``needle`` in ``haystack``.

    Uses ``difflib.SequenceMatcher.ratio`` with a low cutoff so that
    substring overlaps (e.g. needle "python" vs haystack
    "temporal-python-pro") surface as suggestions.
    """
    return get_close_matches(needle, haystack, n=n, cutoff=0.3)


def _resolve_project_path(path: str | Path) -> Path:
    resolved = Path(path)
    if resolved.is_absolute():
        return resolved
    return PROJECT_ROOT / resolved


def _skill_source_dir(skill: dict[str, Any]) -> Path:
    source_path = skill.get("path")
    if source_path:
        return _resolve_project_path(source_path).parent
    return _resolve_project_path(skill["dir"])


def install_skills(
    target: str,
    scope: str,
    skill_names: list[str] | None = None,
    all_skills: list[dict[str, Any]] | None = None,
    copy: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Install skills to target agent runtimes."""
    if target not in ["claude", "qwen", "cursor", "all"]:
        raise InstallError(f"Unknown target: {target}")
    if scope not in ["user", "project"]:
        raise InstallError(f"Unknown scope: {scope}")

    if target == "all":
        targets = list(TARGET_PATHS[scope].keys())
    else:
        targets = [target]

    if all_skills is None:
        import taskmaster

        all_skills = taskmaster.get_all_skills()

    by_dir = {s["dir"]: s for s in all_skills}

    if skill_names:
        by_dir_names = list(by_dir.keys()) + [
            s.get("frontmatter", {}).get("name", "")
            for s in all_skills
        ]
        by_dir_names = [n for n in by_dir_names if n]

        selected_skills: list[dict[str, Any]] = []
        errors: list[str] = []
        for name in skill_names:
            if name in by_dir:
                selected_skills.append(by_dir[name])
                continue
            matched = None
            for s in all_skills:
                if s.get("frontmatter", {}).get("name") == name:
                    matched = s
                    break
            if matched is not None:
                selected_skills.append(matched)
                continue
            suggestions = _closest_matches(name, by_dir_names, n=3)
            if suggestions:
                errors.append(
                    f"Unknown skill '{name}'. Did you mean: {', '.join(suggestions)}?"
                )
            else:
                errors.append(f"Unknown skill '{name}'.")

        if errors:
            raise InstallUsageError("\n".join(errors))
    else:
        selected_skills = all_skills

    results = {}
    for t in targets:
        dest_path_str = TARGET_PATHS[scope][t]
        if scope == "user":
            dest_path_str = os.path.expanduser(dest_path_str)
            dest_path = Path(dest_path_str)
        else:
            dest_path = _resolve_project_path(dest_path_str)

        try:
            dest_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise InstallError(f"Could not create directory {dest_path}: {e}")

        installed_info = []
        for skill in selected_skills:
            skill_dir_name = skill["dir"]
            source_path = _skill_source_dir(skill)
            link_path = dest_path / skill_dir_name

            if link_path.exists() or link_path.is_symlink():
                if not force:
                    continue
                if link_path.is_symlink() or link_path.is_file():
                    link_path.unlink()
                else:
                    shutil.rmtree(link_path)

            if copy:
                shutil.copytree(source_path, link_path)
            else:
                try:
                    os.symlink(source_path, link_path)
                except OSError as e:
                    raise InstallError(f"Failed to create symlink at {link_path}: {e}")

            installed_info.append({
                "name": skill.get("frontmatter", {}).get("name", skill_dir_name),
                "source_path": str(source_path.resolve()),
                "skill_dir": skill_dir_name,
                "installed_path": str(link_path),
                "link_path": str(link_path),
            })

        manifest_path = dest_path / ".taskmaster-manifest.json"
        manifest = {
            "installed_at": datetime.now().isoformat(),
            "source_root": str(PROJECT_ROOT),
            "scope": scope,
            "target": t,
            "skills": installed_info,
        }

        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        results[t] = {
            "path": str(dest_path),
            "count": len(installed_info),
        }

    return results


def uninstall_skills(target: str, scope: str) -> dict[str, Any]:
    """Remove installed skills and cleanup target directories."""
    if target not in ["claude", "qwen", "cursor", "all"]:
        raise InstallError(f"Unknown target: {target}")
    if scope not in ["user", "project"]:
        raise InstallError(f"Unknown scope: {scope}")

    if target == "all":
        targets = list(TARGET_PATHS[scope].keys())
    else:
        targets = [target]

    results = {}
    for t in targets:
        dest_path_str = TARGET_PATHS[scope][t]
        if scope == "user":
            dest_path_str = os.path.expanduser(dest_path_str)
            dest_path = Path(dest_path_str)
        else:
            dest_path = _resolve_project_path(dest_path_str)

        manifest_path = dest_path / ".taskmaster-manifest.json"
        if not manifest_path.exists():
            results[t] = {"status": "not_installed"}
            continue

        try:
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
        except (json.JSONDecodeError, OSError):
            results[t] = {"status": "error", "message": "Corrupt manifest"}
            continue

        removed = 0
        for skill in manifest.get("skills", []):
            raw_installed_path = skill.get("installed_path") or skill.get("link_path")
            if raw_installed_path:
                installed_path = Path(raw_installed_path)
                if not installed_path.is_absolute():
                    installed_path = manifest_path.parent / installed_path
            else:
                installed_path = manifest_path.parent / skill.get("skill_dir", "")
            if installed_path.exists() or installed_path.is_symlink():
                if installed_path.is_symlink() or installed_path.is_file():
                    installed_path.unlink()
                else:
                    shutil.rmtree(installed_path)
                removed += 1

        manifest_path.unlink()
        results[t] = {"status": "uninstalled", "count": removed}

    return results
