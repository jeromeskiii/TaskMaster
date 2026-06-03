from __future__ import annotations

from taskmaster.recommend import recommend_skills


def _skill(name: str, desc: str, tags, body: str = "") -> dict:
    return {
        "dir": name,
        "path": f"{name}/SKILL.md",
        "frontmatter": {"name": name, "description": desc, "tags": tags, "category": "development", "risk": "safe"},
        "frontmatter_valid": True,
        "frontmatter_error": None,
        "body": body,
        "line_count": 1,
        "size_bytes": 0,
    }


def test_recommend_keyword_only_when_no_index():
    skills = [
        _skill("postgres", "Postgres tuning and indexing.", ["postgres", "sql"]),
        _skill("react", "React components and hooks.", ["react", "frontend"]),
        _skill("redis", "Redis caching strategies.", ["redis", "cache"]),
    ]
    results = recommend_skills("postgres vacuum", skills=skills, index=None, k=2)
    assert results[0]["skill"]["dir"] == "postgres"
    assert "reasons" in results[0]
    assert any("postgres" in r.lower() for r in results[0]["reasons"])


def test_recommend_risk_filter_excludes_high():
    skills = [
        _skill("safe", "Safe skill.", ["x"], "x" * 50),
        _skill("risky", "Risky business.", ["x"], "x" * 50),
    ]
    skills[1]["frontmatter"]["risk"] = "high"
    results = recommend_skills("skill", skills=skills, index=None, k=5, max_risk="medium")
    dirs = [r["skill"]["dir"] for r in results]
    assert "risky" not in dirs
    assert "safe" in dirs


def test_recommend_returns_k_results():
    skills = [_skill(f"s{i}", f"description number {i}", [f"t{i}"]) for i in range(10)]
    results = recommend_skills("number 5", skills=skills, index=None, k=3)
    assert len(results) == 3


def test_recommend_degraded_flag_false_when_keyword_only():
    skills = [_skill("a", "alpha alpha alpha", ["x"])]
    results = recommend_skills("alpha", skills=skills, index=None, k=1)
    assert results[0].get("degraded") is True
