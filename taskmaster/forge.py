"""TaskMaster Forge planning engine.

Turns a natural-language build task into a small-PR execution plan,
recommended skill stack, safety checklist, and agent prompt pack.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .compose import compose_skills
from .errors import CycleError
from .recommend import recommend_skills
from .validation import RISK_ORDER


@dataclass(frozen=True)
class ForgeSkill:
    """A recommended skill with score and selection reasons."""

    name: str
    dir: str
    path: str
    category: str
    risk: str
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PRChunk:
    """A small reviewable PR unit."""

    title: str
    goal: str
    deliverables: list[str]
    done_when: list[str]


@dataclass(frozen=True)
class ForgePlan:
    """Complete agent-ready build plan."""

    task: str
    recommended_skills: list[ForgeSkill]
    composed_skill_order: list[str]
    pr_plan: list[PRChunk]
    safety_rules: list[str]
    agent_prompts: dict[str, str]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        lines = [
            "# TaskMaster Forge Plan",
            "",
            f"## Task\n{self.task}",
            "",
            "## Recommended Skills",
        ]
        for idx, skill in enumerate(self.recommended_skills, start=1):
            reason = "; ".join(skill.reasons) if skill.reasons else "matched task intent"
            lines.append(
                f"{idx}. **{skill.name}** `{skill.category}` `{skill.risk}` "
                f"score={skill.score:.3f} — {reason}"
            )

        lines.extend(["", "## Composed Skill Order"])
        if self.composed_skill_order:
            for idx, name in enumerate(self.composed_skill_order, start=1):
                lines.append(f"{idx}. {name}")
        else:
            lines.append("No skill composition order was available.")

        lines.extend(["", "## Small PR Plan"])
        for idx, chunk in enumerate(self.pr_plan, start=1):
            lines.extend([
                f"### PR {idx}: {chunk.title}",
                f"**Goal:** {chunk.goal}",
                "",
                "**Deliverables:**",
                *[f"- {item}" for item in chunk.deliverables],
                "",
                "**Done when:**",
                *[f"- {item}" for item in chunk.done_when],
                "",
            ])

        lines.extend(["## Safety Rules", *[f"- {rule}" for rule in self.safety_rules]])

        if self.warnings:
            lines.extend(["", "## Warnings", *[f"- {warning}" for warning in self.warnings]])

        lines.extend(["", "## Agent Prompt Pack"])
        for role, prompt in self.agent_prompts.items():
            lines.extend([f"### {role.title()}", "```text", prompt.strip(), "```", ""])
        return "\n".join(lines).rstrip() + "\n"


def create_forge_plan(
    task: str,
    skills: list[dict[str, Any]],
    *,
    index: Any = None,
    max_skills: int = 5,
    max_risk: str | None = None,
) -> ForgePlan:
    """Create a Forge plan for a task using the available skill corpus."""
    clean_task = " ".join(task.split())
    if not clean_task:
        raise ValueError("task must not be empty")

    recommendations = recommend_skills(
        clean_task,
        skills=skills,
        index=index,
        k=max(len(skills), max_skills),
        max_risk=max_risk,
    )
    selected = _select_skills(clean_task, recommendations, skills, max_skills=max_skills, max_risk=max_risk)
    selected_dirs = [skill.dir for skill in selected]

    warnings: list[str] = []
    composed_order: list[str] = []
    if selected_dirs:
        try:
            composed = compose_skills(selected_dirs, skills=skills)
            composed_order = [step["name"] for step in composed.steps]
            warnings.extend(composed.warnings)
        except (CycleError, KeyError) as exc:
            warnings.append(f"Skill composition skipped: {exc}")
            composed_order = [skill.name for skill in selected]

    pr_plan = _build_pr_plan(clean_task)
    safety_rules = _safety_rules(clean_task)
    agent_prompts = _agent_prompts(clean_task, selected, pr_plan, safety_rules)

    return ForgePlan(
        task=clean_task,
        recommended_skills=selected,
        composed_skill_order=composed_order,
        pr_plan=pr_plan,
        safety_rules=safety_rules,
        agent_prompts=agent_prompts,
        warnings=warnings,
    )


def write_forge_workspace(plan: ForgePlan, output_dir: str | Path) -> Path:
    """Write a Forge plan into a .taskmaster-style workspace folder."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    (root / "forge_plan.md").write_text(plan.to_markdown(), encoding="utf-8")
    (root / "forge_plan.json").write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")
    (root / "selected_skills.md").write_text(_selected_skills_markdown(plan), encoding="utf-8")
    (root / "pr_plan.md").write_text(_pr_plan_markdown(plan), encoding="utf-8")
    (root / "safety_rules.md").write_text(_safety_markdown(plan), encoding="utf-8")

    prompts_dir = root / "agent_prompts"
    prompts_dir.mkdir(exist_ok=True)
    for role, prompt in plan.agent_prompts.items():
        (prompts_dir / f"{_slug(role)}.md").write_text(prompt.strip() + "\n", encoding="utf-8")

    return root


def _select_skills(
    task: str,
    recommendations: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    *,
    max_skills: int,
    max_risk: str | None,
) -> list[ForgeSkill]:
    """Blend domain hints with recommender output while preserving ranking."""
    by_name = {str((s.get("frontmatter") or {}).get("name") or s.get("dir")): s for s in skills}
    cap = RISK_ORDER.get(max_risk, 2) if max_risk else 2

    selected: list[ForgeSkill] = []
    seen: set[str] = set()

    def allowed(skill: dict[str, Any]) -> bool:
        risk = str((skill.get("frontmatter") or {}).get("risk") or "high")
        return RISK_ORDER.get(risk, 2) <= cap

    def add(skill_name: str, *, hinted: bool = False) -> None:
        if len(selected) >= max_skills or skill_name in seen:
            return
        skill = by_name.get(skill_name)
        if not skill or not allowed(skill):
            return
        selected.append(_forge_skill({
            "skill": skill,
            "score": 1.0 if hinted else 0.0,
            "reasons": ["domain hint"] if hinted else [],
        }))
        seen.add(skill_name)

    for hinted_name in _hint_skill_names(task):
        add(hinted_name, hinted=True)

    for result in recommendations:
        skill = _forge_skill(result)
        if len(selected) >= max_skills:
            break
        if skill.name not in seen and allowed(result["skill"]):
            selected.append(skill)
            seen.add(skill.name)

    return selected


def _hint_skill_names(task: str) -> list[str]:
    tokens = set(re.findall(r"\w+", task.lower()))
    hints = ["software-architecture"]
    if tokens & {"websocket", "coinbase", "feed", "market", "trading", "snapshot", "backtest"}:
        hints.extend(["quant-analyst", "risk-metrics-calculation", "test-driven-development"])
    if tokens & {"api", "backend", "endpoint", "rest", "graphql", "auth"}:
        hints.extend(["api-patterns", "test-driven-development", "zod-validation-expert"])
    if tokens & {"ui", "frontend", "dashboard", "component", "screen"}:
        hints.extend(["shadcn", "ui-visual-validator", "test-driven-development"])
    if len(hints) == 1:
        hints.extend(["test-driven-development", "clean-code"])
    return hints


def _forge_skill(result: dict[str, Any]) -> ForgeSkill:
    skill = result["skill"]
    fm = skill.get("frontmatter", {}) or {}
    name = str(fm.get("name") or skill.get("dir"))
    dir_ = str(skill.get("dir", name))
    return ForgeSkill(
        name=name,
        dir=dir_,
        path=str(skill.get("path", f"{dir_}/SKILL.md")),
        category=str(fm.get("category", "?")),
        risk=str(fm.get("risk", "?")),
        score=float(result.get("score", 0.0)),
        reasons=[str(reason) for reason in result.get("reasons", [])],
    )


def _build_pr_plan(task: str) -> list[PRChunk]:
    tokens = set(re.findall(r"\w+", task.lower()))
    chunks: list[PRChunk] = [
        PRChunk(
            title="Define scope and interfaces",
            goal="Lock the smallest shippable shape before implementation.",
            deliverables=[
                "Create or update a short implementation spec",
                "Define public interfaces, data models, and expected inputs/outputs",
                "List non-goals to keep the first PR small",
            ],
            done_when=[
                "The implementation boundary is clear",
                "The agent can explain what files it will touch before editing",
            ],
        )
    ]

    if tokens & {"websocket", "coinbase", "feed", "market", "trading", "snapshot"}:
        chunks.extend([
            PRChunk(
                title="Add market snapshot domain model",
                goal="Create the stable data contract before connecting live data.",
                deliverables=[
                    "Add MarketSnapshot or equivalent typed model",
                    "Add validation for price, size, timestamp, product, and source fields",
                    "Add unit tests for valid and invalid snapshots",
                ],
                done_when=[
                    "Model tests pass locally",
                    "No live exchange connection is required for tests",
                ],
            ),
            PRChunk(
                title="Build feed adapter with dry-run path",
                goal="Implement the connector behind a narrow adapter interface.",
                deliverables=[
                    "Add feed client/adapter module",
                    "Normalize raw exchange messages into snapshots",
                    "Add dry-run logging mode with no trade execution",
                ],
                done_when=[
                    "Adapter can run without secrets in dry-run mode",
                    "Malformed messages are skipped or surfaced safely",
                ],
            ),
            PRChunk(
                title="Add resilience and replay tests",
                goal="Make the feed safe against disconnects and bad data.",
                deliverables=[
                    "Add reconnect, heartbeat, timeout, and backoff behavior",
                    "Add fixture-based replay tests",
                    "Add basic observability logs or counters",
                ],
                done_when=[
                    "Replay tests cover normal, disconnect, and malformed payloads",
                    "No live credentials are needed in CI",
                ],
            ),
        ])
    if tokens & {"ui", "frontend", "dashboard", "page", "component", "screen"}:
        chunks.extend([
            PRChunk(
                title="Create UI shell",
                goal="Ship a minimal usable surface without backend coupling.",
                deliverables=[
                    "Add route/page/component skeleton",
                    "Add loading, empty, and error states",
                    "Use existing design components where available",
                ],
                done_when=["The screen renders with mock data", "No unrelated styling refactor is included"],
            ),
            PRChunk(
                title="Wire data and interactions",
                goal="Connect the UI to real data behind a small boundary.",
                deliverables=["Add data loader/client call", "Add form/action handling", "Add basic validation"],
                done_when=["Happy path and error path are tested", "The UI stays responsive on failure"],
            ),
        ])
    if tokens & {"api", "backend", "service", "database", "db", "endpoint"}:
        chunks.extend([
            PRChunk(
                title="Add backend contract",
                goal="Define the schema and service boundary first.",
                deliverables=["Add schema/model changes", "Add service interface", "Document request/response shape"],
                done_when=["Contract tests or unit tests cover validation", "Migration risk is documented"],
            ),
            PRChunk(
                title="Implement endpoint/service logic",
                goal="Add the behavior behind the contract with tests.",
                deliverables=["Add endpoint or command handler", "Add service implementation", "Add error handling"],
                done_when=["Unit/integration tests pass", "Errors return stable messages or codes"],
            ),
        ])
    if len(chunks) == 1:
        chunks.extend([
            PRChunk(
                title="Implement core behavior",
                goal="Build the smallest useful vertical slice.",
                deliverables=["Add core module/functionality", "Keep changes limited to the planned boundary", "Add basic user-facing output"],
                done_when=["The feature works for one realistic happy path", "The diff is small enough to review in one pass"],
            ),
            PRChunk(
                title="Add tests and edge cases",
                goal="Make the slice safe to change later.",
                deliverables=["Add unit tests", "Add at least one edge-case test", "Document known limitations"],
                done_when=["Tests pass", "Known gaps are tracked instead of hidden"],
            ),
        ])

    chunks.append(
        PRChunk(
            title="Refactor, document, and prepare launch",
            goal="Clean up duplicated mechanics and make the next agent session easier.",
            deliverables=[
                "Run focused refactor only inside touched areas",
                "Update README or usage notes",
                "Add a launch/checklist note for follow-up work",
            ],
            done_when=[
                "No broad unrelated cleanup is included",
                "The next task has clear handoff notes",
            ],
        )
    )
    return chunks


def _safety_rules(task: str) -> list[str]:
    rules = [
        "Keep every PR small enough to review in one pass.",
        "Do not commit secrets, tokens, API keys, private URLs, or local .env files.",
        "Never install a package younger than 14 days without explicit human approval.",
        "Do not run destructive shell commands unless the user explicitly approves the exact command.",
        "Start a fresh agent session when context becomes bloated instead of compacting blindly.",
    ]
    tokens = set(re.findall(r"\w+", task.lower()))
    if tokens & {"trading", "coinbase", "market", "order", "buy", "sell"}:
        rules.extend([
            "Default to dry-run mode; do not enable live trading in the first implementation pass.",
            "Separate market-data ingestion from order execution with a hard interface boundary.",
        ])
    if tokens & {"security", "auth", "login", "payment", "billing"}:
        rules.append("Add explicit auth, permissions, and audit-log checks before launch.")
    return rules


def _agent_prompts(task: str, skills: list[ForgeSkill], pr_plan: list[PRChunk], safety_rules: list[str]) -> dict[str, str]:
    skill_lines = "\n".join(f"- {skill.name} ({skill.category}, {skill.risk})" for skill in skills) or "- No skills selected"
    pr_lines = "\n".join(f"{idx}. {chunk.title}: {chunk.goal}" for idx, chunk in enumerate(pr_plan, start=1))
    safety = "\n".join(f"- {rule}" for rule in safety_rules)

    shared = f"""
Task: {task}

Recommended skills:
{skill_lines}

Small PR plan:
{pr_lines}

Safety rules:
{safety}
""".strip()

    return {
        "architect": f"""
You are the architect. Turn the task into a minimal implementation design.

{shared}

Output:
1. files likely touched
2. interfaces/data models
3. risks and non-goals
4. the smallest first PR
Do not write code yet.
""",
        "implementer": f"""
You are the implementer. Execute only the current PR chunk, not the whole roadmap.

{shared}

Before editing, state which PR chunk you are implementing and which files you will touch.
After editing, summarize the diff and tests run.
""",
        "reviewer": f"""
You are the reviewer. Review the diff against the task, selected skills, and safety rules.

{shared}

Score the PR from 1 to 5.
Require fixes for correctness, security, scope creep, missing tests, or unclear boundaries.
Approve only if the PR is small, tested, and aligned with the selected PR chunk.
""",
        "tester": f"""
You are the tester. Build a focused validation plan for this task.

{shared}

Output unit tests, integration tests, fixture/replay tests where relevant, and one manual smoke test.
Prefer deterministic tests that do not require live credentials or external services.
""",
    }


def _selected_skills_markdown(plan: ForgePlan) -> str:
    lines = ["# Selected Skills", ""]
    for skill in plan.recommended_skills:
        lines.append(f"- **{skill.name}** — `{skill.category}` `{skill.risk}` score={skill.score:.3f}")
        lines.append(f"  - Path: `{skill.path}`")
        if skill.reasons:
            lines.append(f"  - Reasons: {'; '.join(skill.reasons)}")
    return "\n".join(lines).rstrip() + "\n"


def _pr_plan_markdown(plan: ForgePlan) -> str:
    lines = ["# Small PR Plan", ""]
    for idx, chunk in enumerate(plan.pr_plan, start=1):
        lines.extend([f"## PR {idx}: {chunk.title}", "", chunk.goal, "", "### Deliverables"])
        lines.extend(f"- {item}" for item in chunk.deliverables)
        lines.extend(["", "### Done When"])
        lines.extend(f"- {item}" for item in chunk.done_when)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _safety_markdown(plan: ForgePlan) -> str:
    return "# Safety Rules\n\n" + "\n".join(f"- {rule}" for rule in plan.safety_rules) + "\n"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "prompt"
