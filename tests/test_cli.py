import io
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import taskmaster.cli as cli
import taskmaster as entrypoint


def _expected_python(repo_root: Path) -> str:
    return ".venv/bin/python" if (repo_root / ".venv" / "bin" / "python").exists() else "python3"


class TestCompatibilityEntryPoint(unittest.TestCase):
    def test_package_main_delegates_to_cli_main(self):
        with patch.object(cli, "main", return_value=0) as mock_cli_main:
            entrypoint.main()
        mock_cli_main.assert_called_once_with()

    def test_taskmaster_package_main_runs_legacy_cli(self):
        stdout = io.StringIO()

        with patch("sys.argv", ["taskmaster", "--help"]):
            with self.assertRaises(SystemExit) as exc:
                with redirect_stdout(stdout):
                    entrypoint.main()

        self.assertEqual(exc.exception.code, 0)
        self.assertIn("TaskMaster CLI", stdout.getvalue())

    def test_taskmaster_script_main_keeps_legacy_cli_path(self):
        script_path = Path(__file__).resolve().parent.parent / "taskmaster.py"
        stdout = io.StringIO()

        with patch("sys.argv", [str(script_path), "--help"]):
            with self.assertRaises(SystemExit) as exc:
                with redirect_stdout(stdout):
                    runpy.run_path(str(script_path), run_name="__main__")

        self.assertEqual(exc.exception.code, 0)
        self.assertIn("TaskMaster CLI", stdout.getvalue())

    def test_package_import_does_not_depend_on_sibling_script(self):
        package_src = Path(__file__).resolve().parent.parent / "taskmaster"
        with tempfile.TemporaryDirectory() as tmp:
            package_dst = Path(tmp) / "taskmaster"
            shutil.copytree(package_src, package_dst, ignore=shutil.ignore_patterns("__pycache__"))

            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import taskmaster; print(callable(taskmaster.main))",
                ],
                cwd=tmp,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "True")


class TestMakefileWrappers(unittest.TestCase):
    def test_test_wrapper_uses_repo_virtualenv(self):
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            ["make", "-n", "test"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"{_expected_python(repo_root)} -m pytest tests/ -v")

    def test_install_wrapper_uses_repo_virtualenv(self):
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            ["make", "-n", "install"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            f"{_expected_python(repo_root)} -m pip install -e \".[all]\"",
        )

    def test_search_wrapper_preserves_multi_word_query(self):
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            ["make", "-n", "search", "q=code review"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            f"{_expected_python(repo_root)} taskmaster.py search \"code review\"",
        )

    def test_compose_wrapper_splits_comma_separated_skills(self):
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            ["make", "-n", "compose", "s=bug-hunter,error-detective"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            f"{_expected_python(repo_root)} taskmaster.py compose bug-hunter error-detective",
        )


class TestMcpCompatibility(unittest.TestCase):
    def test_legacy_mcp_serve_alias_dispatches_to_mcp_handler(self):
        captured = {}

        def fake_handler(args):
            captured["args"] = args
            return 0

        original = cli._DISPATCH["mcp-serve"]
        cli._DISPATCH["mcp-serve"] = fake_handler
        try:
            result = cli.main(["mcp-serve"])
        finally:
            cli._DISPATCH["mcp-serve"] = original

        self.assertEqual(result, 0)
        args = captured["args"]
        self.assertEqual(args.command, "mcp-serve")
        self.assertEqual(args.mcp_command, "serve")
