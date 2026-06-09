from __future__ import annotations

import unittest
from pathlib import Path

import yaml


def _load_ci_workflow() -> dict:
    workflow_path = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"
    return yaml.safe_load(workflow_path.read_text(encoding="utf-8"))


def _step_run(job: dict, step_name: str) -> str:
    for step in job["steps"]:
        if step.get("name") == step_name:
            return step["run"]
    raise AssertionError(f"Missing workflow step: {step_name}")


class TestCIWorkflow(unittest.TestCase):
    def test_validate_job_uses_base_install(self):
        workflow = _load_ci_workflow()
        validate_job = workflow["jobs"]["validate"]

        self.assertEqual(_step_run(validate_job, "Install dependencies"), "pip install -e .")

    def test_phase1_job_keeps_semantic_extras_install(self):
        workflow = _load_ci_workflow()
        phase1_job = workflow["jobs"]["phase1"]

        self.assertIn(
            'python -m pip install -e ".[semantic,dev]"',
            _step_run(phase1_job, "Install with semantic extras"),
        )
