import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNERS = (
    ROOT / "skills/apify-lead-generation/reference/scripts/run_actor.js",
    ROOT / "skills/apify-market-research/reference/scripts/run_actor.js",
)
SKILL_FILES = (
    ROOT / "skills/apify-lead-generation/SKILL.md",
    ROOT / "skills/apify-market-research/SKILL.md",
)


class ApifyActorRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("Node.js is required to validate the Actor runners")

    def run_runner(self, runner: Path, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["APIFY_TOKEN"] = "test-token"
        return subprocess.run(
            ["node", str(runner), *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_runners_parse_and_document_required_caps(self) -> None:
        for runner in RUNNERS:
            with self.subTest(runner=runner):
                syntax = subprocess.run(
                    ["node", "--check", str(runner)],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(syntax.returncode, 0, syntax.stderr)

                help_result = self.run_runner(runner, "--help")
                self.assertEqual(help_result.returncode, 0, help_result.stderr)
                self.assertIn("--max-items", help_result.stdout)
                self.assertIn("--max-total-charge-usd", help_result.stdout)

    def test_runners_reject_unsafe_actor_ids_before_network_access(self) -> None:
        for runner in RUNNERS:
            with self.subTest(runner=runner):
                result = self.run_runner(
                    runner,
                    "--actor",
                    "xquik/x-tweet-scraper?token=leak",
                    "--input",
                    "{}",
                    "--max-items",
                    "10",
                    "--max-total-charge-usd",
                    "1",
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("--actor must be", result.stderr)

    def test_runners_reject_invalid_caps_before_network_access(self) -> None:
        for runner in RUNNERS:
            with self.subTest(runner=runner):
                invalid_items = self.run_runner(
                    runner,
                    "--actor",
                    "xquik/x-tweet-scraper",
                    "--input",
                    "{}",
                    "--max-items",
                    "0",
                    "--max-total-charge-usd",
                    "1",
                )
                self.assertEqual(invalid_items.returncode, 1)
                self.assertIn("--max-items must be a positive integer", invalid_items.stderr)

                invalid_charge = self.run_runner(
                    runner,
                    "--actor",
                    "xquik/x-follower-scraper",
                    "--input",
                    "{}",
                    "--max-items",
                    "10",
                    "--max-total-charge-usd",
                    "not-a-number",
                )
                self.assertEqual(invalid_charge.returncode, 1)
                self.assertIn(
                    "--max-total-charge-usd must be a positive number",
                    invalid_charge.stderr,
                )

    def test_runners_use_bearer_auth_instead_of_token_urls(self) -> None:
        for runner in RUNNERS:
            with self.subTest(runner=runner):
                source = runner.read_text(encoding="utf-8")
                self.assertNotIn("?token=", source)
                self.assertIn("Authorization: `Bearer ${token}`", source)

    def test_runner_implementations_stay_in_sync(self) -> None:
        sources = [
            re.sub(
                r"const USER_AGENT = '[^']+';",
                "const USER_AGENT = '<skill-specific>';",
                runner.read_text(encoding="utf-8"),
            )
            for runner in RUNNERS
        ]
        self.assertEqual(sources[0], sources[1])

    def test_apify_skills_document_both_xquik_actor_contracts(self) -> None:
        expected_values = (
            "https://apify.com/xquik/x-tweet-scraper",
            "https://apify.com/xquik/x-follower-scraper",
            "`favoriters`",
            "`community_members`",
            "`snake_case`",
            "`dedupeMode`",
            "Not affiliated with X Corp.",
        )
        for skill_file in SKILL_FILES:
            with self.subTest(skill_file=skill_file):
                content = skill_file.read_text(encoding="utf-8")
                for value in expected_values:
                    self.assertIn(value, content)
                self.assertNotIn("xquik.com", content)


if __name__ == "__main__":
    unittest.main()
