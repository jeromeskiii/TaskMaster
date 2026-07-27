import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import taskmaster.corpus as corpus
from taskmaster.corpus import SkillRecord, _as_list, _parse_frontmatter


class TestCorpusParsing(unittest.TestCase):
    def test_parse_frontmatter_rejects_duplicate_keys(self):
        text = "---\nname: foo\ncategory: ai\ncategory: development\nrisk: safe\n---\n# Body\n"
        fm, _, valid, error = _parse_frontmatter(text)
        self.assertFalse(valid)
        self.assertEqual(fm, {})
        self.assertIn("duplicate key", error)

    def test_as_list_parses_yamlish_tags(self):
        self.assertEqual(
            _as_list("[ddd, context-map, anti-corruption-layer]"),
            ["ddd", "context-map", "anti-corruption-layer"],
        )

    def test_parse_frontmatter_supports_multiline_yaml(self):
        text = (
            "---\n"
            "name: foo\n"
            "description: >-\n"
            "  Line one\n"
            "  line two\n"
            "tags:\n"
            "  - alpha\n"
            "  - beta\n"
            "category: development\n"
            "risk: safe\n"
            "---\n"
            "# Body\n"
        )
        fm, body, valid, error = _parse_frontmatter(text)
        self.assertTrue(valid)
        self.assertIsNone(error)
        self.assertEqual(fm["description"], "Line one line two")
        self.assertEqual(fm["tags"], ["alpha", "beta"])
        self.assertEqual(body.strip(), "# Body")


class TestCorpusCache(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cache_dir = corpus.CACHE_DIR
        self.orig_cache_file = corpus.CACHE_FILE
        corpus.CACHE_DIR = Path(self.tmpdir)
        corpus.CACHE_FILE = corpus.CACHE_DIR / "test_cache.json"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        corpus.CACHE_DIR = self.orig_cache_dir
        corpus.CACHE_FILE = self.orig_cache_file

    def test_cache_roundtrip_preserves_skill_records(self):
        record = SkillRecord(
            dir="foo",
            path="foo/SKILL.md",
            frontmatter={"name": "foo"},
            frontmatter_valid=True,
            frontmatter_error=None,
            body="# Body\n",
            line_count=1,
            size_bytes=10,
        )
        corpus._write_cache({"skills": [record], "timestamp": "2026-01-01T00:00:00+00:00"})
        cached = corpus._read_cache()
        self.assertIsNotNone(cached)
        self.assertEqual(cached["skills"], [record])

    def test_cache_ttl_expired(self):
        corpus._write_cache({"skills": [], "timestamp": "2000-01-01T00:00:00+00:00"})
        past = datetime.now().timestamp() - corpus.CACHE_TTL - 10
        os.utime(corpus.CACHE_FILE, (past, past))
        age = corpus._get_cache_age()
        self.assertGreater(age, corpus.CACHE_TTL)


class TestCorpusIntegration(unittest.TestCase):
    def test_all_skills_parsable(self):
        skills = corpus.get_all_skills(use_cache=False)
        self.assertGreater(len(skills), 0)
        for skill in skills:
            self.assertIsInstance(skill, SkillRecord)
            self.assertTrue(skill.path.endswith("SKILL.md"))

    def test_repository_skills_subdir_precedes_parent_catalog(self):
        package_src = Path(__file__).resolve().parent.parent / "taskmaster"
        with tempfile.TemporaryDirectory() as tmp:
            workspace_dir = Path(tmp)
            repo_dir = workspace_dir / "repo"
            skills_dir = repo_dir / "skills"
            shutil.copytree(
                package_src,
                repo_dir / "taskmaster",
                ignore=shutil.ignore_patterns("__pycache__"),
            )
            (skills_dir / "repo-skill").mkdir(parents=True)
            (skills_dir / "repo-skill" / "SKILL.md").write_text("# Repo skill\n", encoding="utf-8")
            (workspace_dir / "sibling-skill").mkdir()
            (workspace_dir / "sibling-skill" / "SKILL.md").write_text(
                "# Sibling skill\n",
                encoding="utf-8",
            )

            env = {key: value for key, value in os.environ.items() if key != "TASKMASTER_SKILLS_DIR"}
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import taskmaster.corpus as c; print(c.SKILLS_DIR)",
                ],
                cwd=repo_dir,
                env={**env, "PYTHONPATH": str(repo_dir)},
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout.strip()).resolve(), skills_dir.resolve())

    def test_installed_package_uses_catalog_working_directory(self):
        package_src = Path(__file__).resolve().parent.parent / "taskmaster"
        with tempfile.TemporaryDirectory() as tmp:
            site_dir = Path(tmp) / "site"
            catalog_dir = Path(tmp) / "catalog"
            shutil.copytree(package_src, site_dir / "taskmaster", ignore=shutil.ignore_patterns("__pycache__"))
            skill_dir = catalog_dir / "example-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: example-skill\ncategory: development\nrisk: safe\n"
                "description: Example skill with a long enough description.\n---\n"
                "# Body\n1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import taskmaster.corpus as c; print(c.SKILLS_DIR)",
                ],
                cwd=catalog_dir,
                env={**os.environ, "PYTHONPATH": str(site_dir)},
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout.strip()).resolve(), catalog_dir.resolve())

    def test_installed_package_uses_catalog_from_nested_working_directory(self):
        package_src = Path(__file__).resolve().parent.parent / "taskmaster"
        with tempfile.TemporaryDirectory() as tmp:
            site_dir = Path(tmp) / "site"
            catalog_dir = Path(tmp) / "catalog"
            nested_dir = catalog_dir / "nested" / "deeper"
            shutil.copytree(package_src, site_dir / "taskmaster", ignore=shutil.ignore_patterns("__pycache__"))
            skill_dir = catalog_dir / "example-skill"
            skill_dir.mkdir(parents=True)
            nested_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: example-skill\ncategory: development\nrisk: safe\n"
                "description: Example skill with a long enough description.\n---\n"
                "# Body\n1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import taskmaster.corpus as c; print(c.SKILLS_DIR)",
                ],
                cwd=nested_dir,
                env={**os.environ, "PYTHONPATH": str(site_dir)},
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout.strip()).resolve(), catalog_dir.resolve())


class TestTaskmasterScriptDelegation(unittest.TestCase):
    def test_taskmaster_script_get_all_skills_delegates_to_corpus_module(self):
        script_path = Path(__file__).resolve().parent.parent / "taskmaster.py"
        spec = spec_from_file_location("taskmaster_script_for_test", script_path)
        module = module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        record = SkillRecord(
            dir="foo",
            path="foo/SKILL.md",
            frontmatter={"name": "foo"},
            frontmatter_valid=True,
            frontmatter_error=None,
            body="# Body\n",
            line_count=1,
            size_bytes=10,
        )
        with patch.object(corpus, "get_all_skills", return_value=[record]) as mock_get_all:
            skills = module.get_all_skills(use_cache=False)

        mock_get_all.assert_called_once_with(use_cache=False)
        self.assertEqual(skills, [record.to_dict()])
