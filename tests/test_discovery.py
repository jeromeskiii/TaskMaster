import unittest

from taskmaster.corpus import SkillRecord
from taskmaster.discovery import related_skills, search_skills, suggest_skills


class TestDiscovery(unittest.TestCase):
    def setUp(self):
        self.skills = [
            SkillRecord(
                "api-patterns",
                "api-patterns/SKILL.md",
                {
                    "name": "api-patterns",
                    "description": "REST and GraphQL API design",
                    "category": "development",
                    "risk": "safe",
                    "tags": ["api", "rest", "graphql"],
                },
                True,
                None,
                "## API Design\nUse stable contracts.\n",
                10,
                1000,
            ),
            SkillRecord(
                "bug-hunter",
                "bug-hunter/SKILL.md",
                {
                    "name": "bug-hunter",
                    "description": "Debug production bugs",
                    "category": "development",
                    "risk": "safe",
                    "tags": ["bugs", "troubleshooting"],
                },
                True,
                None,
                "## Incidents\nTrack down regressions.\n",
                10,
                1000,
            ),
            SkillRecord(
                "apify-market-research",
                "apify-market-research/SKILL.md",
                {
                    "name": "apify-market-research",
                    "description": "Run market research workflows with Apify actors.",
                    "category": "development",
                    "risk": "safe",
                    "tags": ["scraping", "research"],
                },
                True,
                None,
                "## Actors\n",
                10,
                1000,
            ),
            SkillRecord(
                "frontend-skill",
                "frontend-skill/SKILL.md",
                {
                    "name": "frontend-skill",
                    "description": "Build user interfaces.",
                    "category": "frontend",
                    "risk": "safe",
                    "tags": ["ui"],
                },
                True,
                None,
                "## UI\n",
                10,
                1000,
            ),
        ]

    def test_search_returns_reasons_and_skill_object(self):
        results = search_skills(self.skills, "api", category=None, risk=None, tag=None)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["skill"].dir, "api-patterns")
        self.assertIn("name term match", results[0]["reasons"])

    def test_search_applies_filters(self):
        results = search_skills(self.skills, "api", category="frontend", risk=None, tag=None)
        self.assertEqual(results, [])

    def test_suggest_prefers_debug_skills_without_substring_false_positives(self):
        results = suggest_skills(self.skills, "debug production issue")
        ranked = [result["skill"].dir for result in results]
        self.assertGreaterEqual(len(ranked), 1)
        self.assertEqual(ranked[0], "bug-hunter")
        self.assertNotIn("apify-market-research", ranked)

    def test_suggest_does_not_broaden_architecture_to_generic_development(self):
        results = suggest_skills(self.skills, "architecture review")
        self.assertEqual(results, [])

    def test_related_skills_returns_adjacent_matches(self):
        results = related_skills(self.skills, "api-patterns")
        self.assertIsInstance(results, list)
        self.assertTrue(all(result["skill"].dir != "api-patterns" for result in results))


if __name__ == "__main__":
    unittest.main(verbosity=2)
