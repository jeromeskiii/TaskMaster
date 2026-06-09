import json
import os
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from taskmaster.install import install_skills, uninstall_skills, InstallError


class TestInstall(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.temp_dir.name)
        self.project_root = Path(self.temp_dir.name)

        # Create a mock skills structure
        (Path("skill-a")).mkdir()
        (Path("skill-a") / "SKILL.md").write_text("---\nname: skill-a\n---")

        (Path("skill-b")).mkdir()
        (Path("skill-b") / "SKILL.md").write_text("---\nname: skill-b\n---")

        self.mock_skills = [
            {
                "dir": "skill-a",
                "path": "skill-a/SKILL.md",
                "frontmatter": {"name": "skill-a"},
            },
            {
                "dir": "skill-b",
                "path": "skill-b/SKILL.md",
                "frontmatter": {"name": "skill-b"},
            },
        ]

        # Mock project root and target paths for testing
        import taskmaster.install
        self.original_project_root = taskmaster.install.PROJECT_ROOT
        self.original_targets = taskmaster.install.TARGET_PATHS
        taskmaster.install.PROJECT_ROOT = self.project_root
        taskmaster.install.TARGET_PATHS = {
            "user": {
                "claude": "mock-user/claude",
                "cursor": "mock-user/cursor",
                "qwen": "mock-user/qwen",
            },
            "project": {
                "claude": "mock-project/claude",
                "cursor": "mock-project/cursor",
                "qwen": "mock-project/qwen",
            }
        }

    def tearDown(self):
        import taskmaster.install
        taskmaster.install.PROJECT_ROOT = self.original_project_root
        taskmaster.install.TARGET_PATHS = self.original_targets
        os.chdir(self.old_cwd)
        self.temp_dir.cleanup()

    def test_install_project_scope(self):
        results = install_skills(
            target="claude",
            scope="project",
            skill_names=["skill-a"],
            all_skills=self.mock_skills
        )

        dest_path = Path("mock-project/claude")
        self.assertTrue(dest_path.exists())
        self.assertTrue((dest_path / "skill-a").is_symlink())
        self.assertTrue((dest_path / ".taskmaster-manifest.json").exists())

        with open(dest_path / ".taskmaster-manifest.json") as f:
            manifest = json.load(f)
            self.assertEqual(manifest["target"], "claude")
            self.assertEqual(manifest["scope"], "project")
            self.assertEqual(len(manifest["skills"]), 1)
            self.assertTrue(Path(manifest["skills"][0]["source_path"]).is_absolute())
            self.assertTrue(Path(manifest["skills"][0]["link_path"]).is_absolute())

    def test_install_project_scope_ignores_cwd(self):
        Path("elsewhere").mkdir()
        os.chdir("elsewhere")

        install_skills(
            target="claude",
            scope="project",
            skill_names=["skill-a"],
            all_skills=self.mock_skills
        )

        dest_path = self.project_root / "mock-project/claude"
        self.assertTrue(dest_path.exists())
        self.assertTrue((dest_path / "skill-a").is_symlink())
        self.assertFalse((Path.cwd() / "mock-project/claude/skill-a").exists())

    def test_install_all_targets(self):
        results = install_skills(
            target="all",
            scope="project",
            skill_names=["skill-a"],
            all_skills=self.mock_skills
        )
        self.assertIn("claude", results)
        self.assertIn("cursor", results)
        self.assertIn("qwen", results)
        self.assertTrue(Path("mock-project/cursor/skill-a").is_symlink())

    def test_install_copy(self):
        results = install_skills(
            target="claude",
            scope="project",
            skill_names=["skill-a"],
            all_skills=self.mock_skills,
            copy=True
        )
        dest_path = Path("mock-project/claude")
        self.assertTrue((dest_path / "skill-a").is_dir())
        self.assertFalse((dest_path / "skill-a").is_symlink())

    def test_uninstall(self):
        install_skills(
            target="claude",
            scope="project",
            skill_names=["skill-a"],
            all_skills=self.mock_skills
        )

        results = uninstall_skills(target="claude", scope="project")
        self.assertEqual(results["claude"]["status"], "uninstalled")
        self.assertEqual(results["claude"]["count"], 1)

        dest_path = Path("mock-project/claude")
        self.assertFalse((dest_path / "skill-a").exists())
        self.assertFalse((dest_path / ".taskmaster-manifest.json").exists())
        self.assertTrue((self.project_root / "skill-a").exists())

    def test_uninstall_project_scope_ignores_cwd(self):
        install_skills(
            target="claude",
            scope="project",
            skill_names=["skill-a"],
            all_skills=self.mock_skills
        )

        Path("elsewhere").mkdir()
        os.chdir("elsewhere")

        results = uninstall_skills(target="claude", scope="project")
        self.assertEqual(results["claude"]["status"], "uninstalled")
        self.assertEqual(results["claude"]["count"], 1)

        dest_path = self.project_root / "mock-project/claude"
        self.assertFalse((dest_path / "skill-a").exists())
        self.assertFalse((dest_path / ".taskmaster-manifest.json").exists())

    def test_install_invalid_skill(self):
        from taskmaster.install import InstallUsageError
        with self.assertRaises(InstallUsageError):
            install_skills(
                target="claude",
                scope="project",
                skill_names=["non-existent"],
                all_skills=self.mock_skills
            )

    def test_install_unknown_skill_suggests_closest(self):
        """Unknown skill names should produce a closest-match suggestion."""
        from taskmaster.install import InstallUsageError
        mock_skills = [
            {"dir": "skill-a", "frontmatter": {"name": "skill-a"}},
            {"dir": "temporal-python-pro", "frontmatter": {"name": "temporal-python-pro"}},
            {"dir": "dbos-python", "frontmatter": {"name": "dbos-python"}},
            {"dir": "temporal-python-testing", "frontmatter": {"name": "temporal-python-testing"}},
        ]
        with self.assertRaises(InstallUsageError) as ctx:
            install_skills(
                target="claude",
                scope="project",
                skill_names=["python"],
                all_skills=mock_skills,
            )
        msg = str(ctx.exception)
        self.assertIn("python", msg)
        self.assertIn("Did you mean", msg)
        self.assertIn("temporal-python-pro", msg)


    def test_install_multiple_unknowns_reported_together(self):
        """All unknown names should be reported in one error."""
        from taskmaster.install import InstallUsageError
        mock_skills = [
            {"dir": "skill-a", "frontmatter": {"name": "skill-a"}},
        ]
        with self.assertRaises(InstallUsageError) as ctx:
            install_skills(
                target="claude",
                scope="project",
                skill_names=["pyhton", "kuberntes"],
                all_skills=mock_skills,
            )
        msg = str(ctx.exception)
        self.assertIn("pyhton", msg)
        self.assertIn("kuberntes", msg)


    def test_install_unknown_skill_raises_usage_error(self):
        from taskmaster.install import InstallUsageError
        mock_skills = [
            {"dir": "skill-a", "frontmatter": {"name": "skill-a"}},
        ]
        with self.assertRaises(InstallUsageError) as ctx:
            install_skills(
                target="claude",
                scope="project",
                skill_names=["pyhton"],
                all_skills=mock_skills,
            )
        self.assertIn("pyhton", str(ctx.exception))
