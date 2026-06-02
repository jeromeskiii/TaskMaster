#!/usr/bin/env python3
"""Tests for TaskMaster CLI."""

import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import taskmaster as tm


class TestParseFrontmatter(unittest.TestCase):
    def test_valid_frontmatter(self):
        text = "---\nname: foo\ndescription: A test skill\ncategory: development\nrisk: safe\n---\n# Body"
        fm, body, valid = tm._parse_frontmatter(text)
        self.assertTrue(valid)
        self.assertEqual(fm["name"], "foo")
        self.assertEqual(fm["description"], "A test skill")
        self.assertEqual(body.strip(), "# Body")

    def test_missing_frontmatter(self):
        fm, body, valid = tm._parse_frontmatter("# Just markdown")
        self.assertFalse(valid)
        self.assertEqual(fm, {})

    def test_unclosed_frontmatter(self):
        fm, body, valid = tm._parse_frontmatter("---\nname: foo")
        self.assertFalse(valid)

    def test_quoted_values(self):
        text = '---\nname: "foo"\ndescription: \'bar\'\n---\nbody'
        fm, _, valid = tm._parse_frontmatter(text)
        self.assertTrue(valid)
        self.assertEqual(fm["name"], "foo")
        self.assertEqual(fm["description"], "bar")


class TestValidateSkill(unittest.TestCase):
    def test_valid_skill(self):
        skill = {
            "frontmatter_valid": True,
            "frontmatter": {
                "name": "test",
                "description": "A clear description that is definitely over thirty chars",
                "category": "development",
                "risk": "safe",
            },
            "size_bytes": 1000,
            "line_count": 20,
        }
        issues = tm.validate_skill(skill)
        self.assertEqual(issues, [])

    def test_missing_required_field(self):
        skill = {
            "frontmatter_valid": True,
            "frontmatter": {
                "name": "test",
                "description": "A clear description that is definitely over thirty chars",
                "risk": "safe",
            },
            "size_bytes": 1000,
            "line_count": 20,
        }
        issues = tm.validate_skill(skill)
        self.assertTrue(any("missing field 'category'" in i for i in issues))

    def test_invalid_risk(self):
        skill = {
            "frontmatter_valid": True,
            "frontmatter": {
                "name": "test",
                "description": "A clear description that is definitely over thirty chars",
                "category": "development",
                "risk": "extreme",
            },
            "size_bytes": 1000,
            "line_count": 20,
        }
        issues = tm.validate_skill(skill)
        self.assertTrue(any("invalid risk" in i for i in issues))

    def test_unknown_category(self):
        skill = {
            "frontmatter_valid": True,
            "frontmatter": {
                "name": "test",
                "description": "A clear description that is definitely over thirty chars",
                "category": "unknown-category",
                "risk": "safe",
            },
            "size_bytes": 1000,
            "line_count": 20,
        }
        issues = tm.validate_skill(skill)
        self.assertTrue(any("unknown category" in i for i in issues))

    def test_too_small(self):
        skill = {
            "frontmatter_valid": True,
            "frontmatter": {
                "name": "test",
                "description": "A clear description that is definitely over thirty chars",
                "category": "development",
                "risk": "safe",
            },
            "size_bytes": 100,
            "line_count": 20,
        }
        issues = tm.validate_skill(skill)
        self.assertTrue(any("too small" in i for i in issues))

    def test_short_description(self):
        skill = {
            "frontmatter_valid": True,
            "frontmatter": {
                "name": "test",
                "description": "short",
                "category": "development",
                "risk": "safe",
            },
            "size_bytes": 1000,
            "line_count": 20,
        }
        issues = tm.validate_skill(skill)
        self.assertTrue(any("description too short" in i for i in issues))


class TestScoreQuality(unittest.TestCase):
    def test_high_quality_skill(self):
        skill = {
            "frontmatter": {
                "name": "test",
                "description": "A very detailed description that goes well beyond the minimum requirements",
                "category": "development",
                "risk": "safe",
                "source": "community",
                "date_added": "2026-01-01",
                "tags": "foo bar",
            },
            "line_count": 100,
            "body": "## Heading\n\n```code\n```\n",
        }
        result = tm.score_skill_quality(skill)
        self.assertGreaterEqual(result["score"], 80)
        self.assertTrue(result["details"]["has_structure"])
        self.assertTrue(result["details"]["has_examples"])

    def test_low_quality_skill(self):
        skill = {
            "frontmatter": {"name": "test"},
            "line_count": 5,
            "body": "minimal",
        }
        result = tm.score_skill_quality(skill)
        self.assertLess(result["score"], 50)


class TestSearchSkills(unittest.TestCase):
    def setUp(self):
        # Patch get_all_skills with test data
        self.original_get_all = tm.get_all_skills
        tm.get_all_skills = lambda use_cache=True: [
            {
                "dir": "postgres-skill",
                "frontmatter": {
                    "name": "postgres-skill",
                    "description": "PostgreSQL optimization and query tuning",
                    "category": "backend",
                    "tags": "database sql",
                },
                "body": "## Setup\nInstall postgres...",
            },
            {
                "dir": "react-skill",
                "frontmatter": {
                    "name": "react-skill",
                    "description": "React component patterns and hooks",
                    "category": "frontend",
                    "tags": "ui javascript",
                },
                "body": "## Components\nUse hooks...",
            },
        ]

    def tearDown(self):
        tm.get_all_skills = self.original_get_all

    def test_search_by_name(self):
        results = tm.search_skills("postgres")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["dir"], "postgres-skill")

    def test_search_by_description(self):
        results = tm.search_skills("optimization")
        self.assertTrue(any(r["dir"] == "postgres-skill" for r in results))

    def test_fuzzy_search(self):
        results = tm.search_skills("postgrsql")
        self.assertTrue(len(results) >= 1)

    def test_no_results(self):
        results = tm.search_skills("xyznonexistent")
        self.assertEqual(len(results), 0)


class TestExportSkills(unittest.TestCase):
    def setUp(self):
        self.original_get_all = tm.get_all_skills
        tm.get_all_skills = lambda use_cache=True: [
            {
                "dir": "foo",
                "frontmatter": {"name": "foo", "category": "dev", "risk": "safe", "description": "bar", "source": "", "tags": ""},
                "size_bytes": 1000,
                "line_count": 10,
                "path": "foo/SKILL.md",
            }
        ]

    def tearDown(self):
        tm.get_all_skills = self.original_get_all

    def test_json_export(self):
        output = tm.export_skills(as_json=True)
        data = json.loads(output)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["skills"][0]["name"], "foo")

    def test_markdown_export(self):
        output = tm.export_skills(as_json=False)
        self.assertIn("# TaskMaster Export", output)
        self.assertIn("foo", output)


class TestCache(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cache_dir = tm.CACHE_DIR
        self.orig_cache_file = tm.CACHE_FILE
        tm.CACHE_DIR = Path(self.tmpdir)
        tm.CACHE_FILE = tm.CACHE_DIR / "test_cache.json"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        tm.CACHE_DIR = self.orig_cache_dir
        tm.CACHE_FILE = self.orig_cache_file

    def test_cache_roundtrip(self):
        data = {"skills": [], "timestamp": "2026-01-01T00:00:00+00:00"}
        tm._write_cache(data)
        cached = tm._read_cache()
        self.assertIsNotNone(cached)
        self.assertEqual(cached["skills"], [])

    def test_cache_ttl_expired(self):
        # Write cache then backdate it
        old = {"skills": [], "timestamp": "2000-01-01T00:00:00+00:00"}
        tm._write_cache(old)
        past = datetime.now().timestamp() - tm.CACHE_TTL - 10
        os.utime(tm.CACHE_FILE, (past, past))
        age = tm._get_cache_age()
        self.assertGreater(age, tm.CACHE_TTL)


class TestIntegration(unittest.TestCase):
    """Integration tests against the real skills directory."""

    def test_all_skills_parsable(self):
        skills = tm.get_all_skills(use_cache=False)
        self.assertGreater(len(skills), 0)
        for skill in skills:
            self.assertIn("dir", skill)
            self.assertIn("frontmatter", skill)
            self.assertIn("path", skill)

    def test_validate_all_passes(self):
        report = tm.validate_all()
        self.assertEqual(report["stats"]["total"], len(report["skills"]))
        self.assertEqual(len(report["issues"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
