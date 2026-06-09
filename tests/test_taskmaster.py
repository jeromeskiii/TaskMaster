#!/usr/bin/env python3
"""Tests for TaskMaster CLI."""

import json
import sys
import unittest
import tempfile
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import taskmaster as tm

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
        self.assertEqual(results[0]["skill"].dir, "postgres-skill")
        self.assertIn("name term match", results[0]["reasons"])

    def test_search_by_description(self):
        results = tm.search_skills("optimization")
        self.assertTrue(any(r["skill"].dir == "postgres-skill" for r in results))
        self.assertTrue(any("description overlap" in r["reasons"] for r in results))

    def test_fuzzy_search(self):
        results = tm.search_skills("postgrsql")
        self.assertTrue(len(results) >= 1)

    def test_no_results(self):
        results = tm.search_skills("xyznonexistent")
        self.assertEqual(len(results), 0)


class TestSuggestSkills(unittest.TestCase):
    def setUp(self):
        self.original_get_all = tm.get_all_skills
        tm.get_all_skills = lambda use_cache=True: [
            {
                "dir": "bug-hunter",
                "frontmatter": {
                    "name": "bug-hunter",
                    "description": "Systematically finds and fixes bugs in production systems.",
                    "category": "development",
                    "tags": ["bugs", "troubleshooting"],
                },
                "body": "## When to Use\n- Production incidents\n",
            },
            {
                "dir": "blockchain-developer",
                "frontmatter": {
                    "name": "blockchain-developer",
                    "description": "Build blockchain products and smart contract systems.",
                    "category": "development",
                    "tags": ["solidity", "web3"],
                },
                "body": "## Smart Contracts\n- Protocol design\n",
            },
            {
                "dir": "frontend-skill",
                "frontmatter": {
                    "name": "frontend-skill",
                    "description": "Build user interfaces.",
                    "category": "frontend",
                    "tags": ["ui"],
                },
                "body": "## UI\n",
            },
            {
                "dir": "apify-market-research",
                "frontmatter": {
                    "name": "apify-market-research",
                    "description": "Run market research workflows with Apify actors.",
                    "category": "development",
                    "tags": ["scraping", "research"],
                },
                "body": "## Actors\n",
            },
            {
                "dir": "zapier-make-patterns",
                "frontmatter": {
                    "name": "zapier-make-patterns",
                    "description": "Automation patterns for Zapier and Make.",
                    "category": "automation",
                    "tags": ["automation", "workflow"],
                },
                "body": "## Automation\n",
            },
            {
                "dir": "api-patterns",
                "frontmatter": {
                    "name": "api-patterns",
                    "description": "Best practices for REST and GraphQL API design.",
                    "category": "development",
                    "tags": ["api", "rest", "graphql"],
                },
                "body": "## API Design\n",
            },
        ]

    def tearDown(self):
        tm.get_all_skills = self.original_get_all

    def test_debug_queries_match_development_skills(self):
        results = tm.suggest_skills("debug production issue")
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["skill"].dir, "bug-hunter")
        self.assertIn("name term match", results[0]["reasons"])

    def test_unrelated_development_skill_is_not_suggested_for_debug_query(self):
        results = tm.suggest_skills("debug production issue")
        ranked = [result["skill"].dir for result in results]
        self.assertEqual(ranked[0], "bug-hunter")
        self.assertNotIn("blockchain-developer", ranked)

    def test_architecture_query_does_not_match_generic_development_skills(self):
        results = tm.suggest_skills("architecture review")
        self.assertEqual(results, [])

    def test_api_query_does_not_match_names_by_substring_only(self):
        results = tm.suggest_skills("api")
        ranked = [result["dir"] for result in results]
        self.assertIn("api-patterns", ranked)
        self.assertNotIn("apify-market-research", ranked)
        self.assertNotIn("zapier-make-patterns", ranked)


class TestExportSkills(unittest.TestCase):
    def setUp(self):
        self.original_get_all = tm.get_all_skills
        tm.get_all_skills = lambda use_cache=True: [
            {
                "dir": "foo",
                "frontmatter": {
                    "name": "foo",
                    "category": "dev",
                    "risk": "safe",
                    "description": "bar",
                    "source": "",
                    "tags": ["alpha", "beta"],
                },
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
        self.assertEqual(data["skills"][0]["tags"], ["alpha", "beta"])

    def test_markdown_export(self):
        output = tm.export_skills(as_json=False)
        self.assertIn("# TaskMaster Export", output)
        self.assertIn("foo", output)

    def test_json_export_normalizes_scalar_tag_strings(self):
        tm.get_all_skills = lambda use_cache=True: [
            {
                "dir": "foo",
                "frontmatter": {
                    "name": "foo",
                    "category": "dev",
                    "risk": "safe",
                    "description": "bar",
                    "source": "",
                    "tags": "[alpha, beta, gamma]",
                },
                "size_bytes": 1000,
                "line_count": 10,
                "path": "foo/SKILL.md",
                "frontmatter_valid": True,
                "frontmatter_error": None,
            }
        ]
        output = tm.export_skills(as_json=True)
        data = json.loads(output)
        self.assertEqual(data["skills"][0]["tags"], ["alpha", "beta", "gamma"])


class TestIntegration(unittest.TestCase):
    """Integration tests against the real skills directory."""

    def test_validate_all_counts_parse_errors_from_fixture(self):
        self.addCleanup(setattr, tm, "get_all_skills", tm.get_all_skills)
        tm.get_all_skills = lambda use_cache=True: [
            {
                "dir": "valid-skill",
                "path": "valid-skill/SKILL.md",
                "frontmatter": {
                    "name": "valid-skill",
                    "description": "A valid skill description that is over thirty characters long.",
                    "category": "development",
                    "risk": "safe",
                },
                "frontmatter_valid": True,
                "frontmatter_error": None,
                "body": "# Body\nMore than enough lines\n1\n2\n3\n4\n5\n6\n7\n8\n9\n",
                "line_count": 11,
                "size_bytes": 1000,
            },
            {
                "dir": "broken-skill",
                "path": "broken-skill/SKILL.md",
                "frontmatter": {},
                "frontmatter_valid": False,
                "frontmatter_error": "found duplicate key 'category'",
                "body": "# Body\n",
                "line_count": 1,
                "size_bytes": 100,
            },
        ]

        report = tm.validate_all()
        self.assertEqual(report["stats"]["total"], 2)
        self.assertEqual(report["stats"]["valid"], 1)
        self.assertEqual(report["stats"]["frontmatter_parse_errors"], 1)
        self.assertTrue(any(issue["dir"] == "broken-skill" for issue in report["issues"]))

    def test_validate_all_counts_non_mapping_yaml_parse_errors(self):
        self.addCleanup(setattr, tm, "get_all_skills", tm.get_all_skills)
        tm.get_all_skills = lambda use_cache=True: [
            {
                "dir": "broken-yaml",
                "path": "broken-yaml/SKILL.md",
                "frontmatter": {},
                "frontmatter_valid": False,
                "frontmatter_error": "while parsing a flow sequence\nexpected ',' or ']'",
                "body": "# Body\n",
                "line_count": 1,
                "size_bytes": 100,
            },
        ]

        report = tm.validate_all()
        self.assertEqual(report["stats"]["total"], 1)
        self.assertEqual(report["stats"]["valid"], 0)
        self.assertEqual(report["stats"]["frontmatter_parse_errors"], 1)

    def test_validate_all_counts_short_descriptions_separately(self):
        self.addCleanup(setattr, tm, "get_all_skills", tm.get_all_skills)
        tm.get_all_skills = lambda use_cache=True: [
            {
                "dir": "short-desc",
                "path": "short-desc/SKILL.md",
                "frontmatter": {
                    "name": "short-desc",
                    "description": "too short",
                    "category": "development",
                    "risk": "safe",
                },
                "frontmatter_valid": True,
                "frontmatter_error": None,
                "body": "# Body\n1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n",
                "line_count": 11,
                "size_bytes": 1000,
            },
        ]

        report = tm.validate_all()
        self.assertEqual(report["stats"]["short_descriptions"], 1)
        self.assertEqual(report["stats"]["skeleton_skills"], 0)

    def test_generate_index_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = tm.ROOT
            original_skills_dir = tm.SKILLS_DIR
            self.addCleanup(setattr, tm, "ROOT", original_root)
            self.addCleanup(setattr, tm, "SKILLS_DIR", original_skills_dir)

            tm.ROOT = Path(tmpdir)
            tm.SKILLS_DIR = Path(tmpdir) / "skills"

            report = {
                "skills": [
                    {
                        "dir": "demo-skill",
                        "frontmatter": {
                            "name": "demo-skill",
                            "description": "A deterministic example skill for index generation.",
                            "category": "development",
                            "risk": "safe",
                        },
                    }
                ]
            }

            tm.generate_index(report)
            first = (Path(tmpdir) / "INDEX.md").read_text(encoding="utf-8")
            tm.generate_index(report)
            second = (Path(tmpdir) / "INDEX.md").read_text(encoding="utf-8")

            self.assertEqual(first, second)
            self.assertNotIn("Generated:", first)


if __name__ == "__main__":
    unittest.main(verbosity=2)
