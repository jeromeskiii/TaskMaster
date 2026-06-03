import unittest

from taskmaster.corpus import SkillRecord
from taskmaster.validation import build_hygiene_report, build_normalization_report


class TestHygieneReport(unittest.TestCase):
    def test_hygiene_flags_duplicate_names_and_tag_shapes(self):
        skills = [
            SkillRecord("a", "a/SKILL.md", {"name": "dup", "tags": "[x, y]"}, True, None, "# Body\n1\n2\n3\n4\n5\n6\n7\n8\n9\n10", 11, 1000),
            SkillRecord("b", "b/SKILL.md", {"name": "dup", "tags": ["x", "y"]}, True, None, "# Body\n1\n2\n3\n4\n5\n6\n7\n8\n9\n10", 11, 1000),
        ]
        report = build_hygiene_report(skills)
        self.assertEqual(report["stats"]["duplicate_names"], 1)
        self.assertEqual(report["stats"]["tag_shape_inconsistencies"], 1)

    def test_hygiene_flags_near_duplicates_parse_errors_and_anomalies(self):
        skills = [
            SkillRecord("alpha", "alpha/SKILL.md", {"name": "alpha", "description": "Shared description for both skills", "category": "development", "risk": "safe", "tags": ["one"]}, True, None, "# Body\n1\n2\n3\n4\n5\n6\n7\n8\n9\n10", 11, 1000),
            SkillRecord("beta", "beta/SKILL.md", {"name": "beta", "description": "Shared description for both skills!", "category": "unknown-category", "risk": "extreme", "tags": ["two"]}, True, None, "# Body\n1\n2\n3\n4\n5\n6\n7\n8\n9\n10", 11, 1000),
            SkillRecord("broken", "broken/SKILL.md", {}, False, "while parsing a flow sequence\nexpected ',' or ']'", "# Body\n", 1, 100),
        ]

        report = build_hygiene_report(skills)

        self.assertGreaterEqual(report["stats"]["near_duplicate_descriptions"], 1)
        self.assertEqual(report["stats"]["parse_error_rollups"], 1)
        self.assertEqual(report["stats"]["category_anomalies"], 1)
        self.assertEqual(report["stats"]["risk_anomalies"], 1)
        self.assertEqual(report["issues"]["parse_error_rollups"][0]["count"], 1)


class TestNormalizationReport(unittest.TestCase):
    def test_normalization_suggests_tag_list_conversion(self):
        skills = [
            SkillRecord(
                "ddd-context-mapping",
                "ddd-context-mapping/SKILL.md",
                {"name": "ddd-context-mapping", "tags": "[ddd, context-map]"},
                True,
                None,
                "# Body\n1\n2\n3\n4\n5\n6\n7\n8\n9\n10",
                11,
                1000,
            ),
        ]

        report = build_normalization_report(skills)

        self.assertEqual(report["stats"]["total_changes"], 1)
        self.assertEqual(
            report["changes"][0],
            {
                "dir": "ddd-context-mapping",
                "field": "tags",
                "current": "[ddd, context-map]",
                "normalized": ["ddd", "context-map"],
                "reason": "scalar tag string can be normalized to canonical list form",
            },
        )
