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
