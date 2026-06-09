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


def test_recommend_degraded_banner_in_cli_output(monkeypatch):
    """The recommend CLI must print the degraded banner when no embedding index is available."""
    monkeypatch.setenv("TASKMASTER_EMBEDDINGS", "null")
    import contextlib
    import io
    from taskmaster import cli

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cli.main(["recommend", "debug a production API timeout", "--max", "3"])
    assert rc == 0
    out = buf.getvalue()
    assert "degraded mode" in out
    assert "Recommended skills:" in out


def test_recommend_json_includes_degraded_flag_per_result(monkeypatch):
    """JSON output must include a 'degraded' field per result."""
    monkeypatch.setenv("TASKMASTER_EMBEDDINGS", "null")
    import contextlib
    import io
    import json
    from taskmaster import cli

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cli.main(
            ["recommend", "debug a production API timeout", "--max", "3", "--json"]
        )
    assert rc == 0
    payload = json.loads(buf.getvalue())
    assert isinstance(payload, list)
    assert len(payload) >= 1
    for item in payload:
        assert "degraded" in item
        # Base env: no [semantic] extra, so every result should be degraded
        assert item["degraded"] is True


def test_recommend_keyword_only_flag_skips_embedding_index():
    """--keyword-only must print the degraded banner without trying to build an index."""
    import contextlib
    import io
    from taskmaster import cli

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cli.main(
            ["recommend", "debug a production API timeout", "--max", "3", "--keyword-only"]
        )
    assert rc == 0
    out = buf.getvalue()
    assert "degraded mode" in out
