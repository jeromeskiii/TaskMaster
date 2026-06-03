import io
import runpy
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import taskmaster.cli as cli
import taskmaster as entrypoint


class TestCompatibilityEntryPoint(unittest.TestCase):
    def test_taskmaster_entrypoint_calls_package_main(self):
        with patch.object(cli, "main") as mock_main:
            entrypoint.main()
        mock_main.assert_called_once_with()

    def test_taskmaster_script_main_keeps_legacy_cli_path(self):
        script_path = Path(__file__).resolve().parent.parent / "taskmaster.py"
        stdout = io.StringIO()

        with patch.object(cli, "main", side_effect=AssertionError("package CLI should not run")) as mock_main:
            with patch("sys.argv", [str(script_path), "--help"]):
                with self.assertRaises(SystemExit) as exc:
                    with redirect_stdout(stdout):
                        runpy.run_path(str(script_path), run_name="__main__")

        self.assertEqual(exc.exception.code, 0)
        self.assertIn("TaskMaster CLI", stdout.getvalue())
        mock_main.assert_not_called()
