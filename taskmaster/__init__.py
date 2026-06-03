"""TaskMaster compatibility package."""

from pathlib import Path


def _load_legacy_module() -> None:
    legacy_path = Path(__file__).resolve().parent.parent / "taskmaster.py"
    globals()["__file__"] = str(legacy_path)
    with legacy_path.open(encoding="utf-8") as legacy_file:
        legacy_code = compile(legacy_file.read(), str(legacy_path), "exec")
    exec(legacy_code, globals())


_load_legacy_module()

from . import corpus as _corpus
from . import validation as _validation


def _record_to_dict(record):
    return record.to_dict() if isinstance(record, _corpus.SkillRecord) else record


SkillRecord = _corpus.SkillRecord
UniqueKeyLoader = _corpus.UniqueKeyLoader
SKILLS_DIR = _corpus.SKILLS_DIR
CACHE_DIR = _corpus.CACHE_DIR
CACHE_FILE = _corpus.CACHE_FILE
CACHE_TTL = _corpus.CACHE_TTL
_parse_frontmatter = _corpus._parse_frontmatter
_get_cache_age = _corpus._get_cache_age
_read_cache = _corpus._read_cache
_write_cache = _corpus._write_cache
_flatten_text = _corpus._flatten_text
_tokenize_text = _corpus._tokenize_text
_as_list = _corpus._as_list
_normalize_frontmatter_value = _corpus._normalize_frontmatter_value


def parse_skill(dirpath):
    return _record_to_dict(_corpus.parse_skill(dirpath))


def get_all_skills(use_cache=True):
    return [_record_to_dict(skill) for skill in _corpus.get_all_skills(use_cache=use_cache)]


def validate_skill(skill):
    return _validation.validate_skill(skill)


def validate_all():
    return _validation.validate_all(get_all_skills())


def score_skill_quality(skill):
    return _validation.score_skill_quality(skill)


build_hygiene_report = _validation.build_hygiene_report
build_normalization_report = _validation.build_normalization_report
