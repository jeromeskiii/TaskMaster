from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT

CACHE_DIR = ROOT / ".taskmaster_cache"
CACHE_FILE = CACHE_DIR / "skills_cache.json"
CACHE_TTL = 300


@dataclass(frozen=True)
class SkillRecord:
    dir: str
    path: str
    frontmatter: dict[str, Any]
    frontmatter_valid: bool
    frontmatter_error: Optional[str]
    body: str
    line_count: int
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillRecord":
        return cls(
            dir=str(data["dir"]),
            path=str(data["path"]),
            frontmatter=dict(data.get("frontmatter", {})),
            frontmatter_valid=bool(data.get("frontmatter_valid", False)),
            frontmatter_error=data.get("frontmatter_error"),
            body=str(data.get("body", "")),
            line_count=int(data.get("line_count", 0)),
            size_bytes=int(data.get("size_bytes", 0)),
        )


class UniqueKeyLoader(yaml.SafeLoader):
    """YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(loader: UniqueKeyLoader, node: yaml.nodes.MappingNode, deep: bool = False) -> dict:
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def parse_skill(dirpath: Path) -> Optional[SkillRecord]:
    md_file = dirpath / "SKILL.md"
    if not md_file.exists():
        return None

    text = md_file.read_text(encoding="utf-8")
    fm, body, fm_valid, fm_error = _parse_frontmatter(text)
    size = len(text.encode("utf-8"))
    lines = body.strip().split("\n") if body.strip() else []

    return SkillRecord(
        dir=dirpath.name,
        path=str(md_file),
        frontmatter=fm,
        frontmatter_valid=fm_valid,
        frontmatter_error=fm_error,
        body=body,
        line_count=len(lines),
        size_bytes=size,
    )


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str, bool, Optional[str]]:
    if not text.startswith("---"):
        return {}, text, False, None

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text, False, None

    closing_idx = None
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_idx = idx
            break

    if closing_idx is None:
        return {}, text, False, None

    raw = "".join(lines[1:closing_idx])
    body = "".join(lines[closing_idx + 1 :])

    try:
        parsed = yaml.load(raw, Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        return {}, body, False, str(exc)

    if parsed is None:
        parsed = {}
    if not isinstance(parsed, dict):
        return {}, body, False, "frontmatter must be a YAML mapping"

    return _normalize_frontmatter_value(parsed), body, True, None


def _get_cache_age() -> float:
    if not CACHE_FILE.exists():
        return float("inf")
    return datetime.now(timezone.utc).timestamp() - CACHE_FILE.stat().st_mtime


def _deserialize_cache(data: dict[str, Any]) -> dict[str, Any]:
    skills = data.get("skills", [])
    if isinstance(skills, list):
        data = dict(data)
        data["skills"] = [
            skill if isinstance(skill, SkillRecord) else SkillRecord.from_dict(skill)
            for skill in skills
        ]
    return data


def _read_cache() -> Optional[dict[str, Any]]:
    if _get_cache_age() > CACHE_TTL:
        return None
    try:
        with CACHE_FILE.open(encoding="utf-8") as cache_file:
            return _deserialize_cache(json.load(cache_file))
    except Exception:
        return None


def _serialize_cache(data: dict[str, Any]) -> dict[str, Any]:
    serialized = dict(data)
    skills = serialized.get("skills", [])
    if isinstance(skills, list):
        serialized["skills"] = [
            skill.to_dict() if isinstance(skill, SkillRecord) else skill
            for skill in skills
        ]
    return serialized


def _write_cache(data: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f"{CACHE_FILE.stem}-", suffix=".tmp", dir=CACHE_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as cache_file:
            json.dump(_serialize_cache(data), cache_file)
        Path(tmp_name).replace(CACHE_FILE)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _flatten_text(value: object) -> str:
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(f"{key} {_flatten_text(val)}" for key, val in value.items())
    return str(value)


def _tokenize_text(value: object) -> set[str]:
    return set(re.findall(r"\w+", _flatten_text(value).lower()))


def _as_list(value: object) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = yaml.safe_load(text)
            except yaml.YAMLError:
                parsed = None
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        if "," in text:
            return [part.strip() for part in text.split(",") if part.strip()]
        return text.split()
    return [str(value)]


def _normalize_frontmatter_value(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _normalize_frontmatter_value(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_normalize_frontmatter_value(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def get_all_skills(use_cache: bool = True) -> list[SkillRecord]:
    if use_cache:
        cached = _read_cache()
        if cached:
            return cached["skills"]

    skills = []
    for dirpath in sorted(SKILLS_DIR.iterdir()):
        if not dirpath.is_dir() or dirpath.name.startswith("."):
            continue
        skill = parse_skill(dirpath)
        if skill:
            skills.append(skill)

    _write_cache({"skills": skills, "timestamp": datetime.now(timezone.utc).isoformat()})
    return skills
