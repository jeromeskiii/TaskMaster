import unittest
from unittest.mock import patch

import taskmaster.cli as cli
import taskmaster as entrypoint


class TestCompatibilityEntryPoint(unittest.TestCase):
    def test_taskmaster_entrypoint_calls_package_main(self):
        with patch.object(cli, "main") as mock_main:
            entrypoint.main()
        mock_main.assert_called_once_with()
