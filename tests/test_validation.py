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
