from __future__ import annotations

from taskmaster.embeddings.text import build_skill_text


def _skill(name: str, description: str, tags, body: str) -> dict:
    return {
        "dir": name,
        "path": f"{name}/SKILL.md",
        "frontmatter": {"name": name, "description": description, "tags": tags},
        "frontmatter_valid": True,
        "frontmatter_error": None,
        "body": body,
        "line_count": body.count("\n") + 1,
        "size_bytes": len(body),
    }


def test_build_skill_text_includes_name_desc_tags():
    s = _skill("postgres-tuning", "Tune Postgres for OLTP workloads.", ["postgres", "sql"], "body")
    text = build_skill_text(s)
    assert "postgres-tuning" in text
    assert "Tune Postgres" in text
    assert "postgres" in text and "sql" in text


def test_build_skill_text_truncates_body():
    s = _skill("x", "x" * 50, [], "B" * 5000)
    text = build_skill_text(s)
    # body should be capped at 1000 chars
    assert text.count("B") <= 1000


def test_build_skill_text_handles_missing_fields():
    s = {"dir": "x", "path": "x/SKILL.md", "frontmatter": {}, "body": ""}
    text = build_skill_text(s)
    assert isinstance(text, str)


def test_build_skill_text_normalizes_tags_scalar():
    s = _skill("x", "x" * 50, "postgres, sql", "")
    text = build_skill_text(s)
    assert "postgres" in text and "sql" in text
