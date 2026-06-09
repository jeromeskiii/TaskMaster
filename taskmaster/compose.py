"""Dependency-graph composer for skills.

Reads the optional ``depends_on`` frontmatter list and produces a
topologically ordered plan. Cycles raise :class:`CycleError`.
Missing dependencies are returned in the plan's ``warnings`` list
alongside a fuzzy closest-match suggestion; the resolvable subset of
the plan is still returned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import get_close_matches
from typing import Any

from .errors import CycleError


@dataclass
class ComposePlan:
    steps: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan": [
                {"order": i + 1, "name": step["name"], "depends_on": step["depends_on"]}
                for i, step in enumerate(self.steps)
            ],
            "warnings": list(self.warnings),
        }


def compose_skills(names: list[str], skills: list[dict[str, Any]]) -> ComposePlan:
    by_dir = {s["dir"]: s for s in skills}
    unknown = [n for n in names if n not in by_dir]
    if unknown:
        raise KeyError(f"Unknown skill(s): {unknown}")

    warnings: list[str] = []
    adjacency: dict[str, list[str]] = {}

    seen: set[str] = set()
    queue: list[str] = list(names)
    while queue:
        name = queue.pop(0)
        if name in seen:
            continue
        seen.add(name)
        skill = by_dir[name]
        deps = skill.get("frontmatter", {}).get("depends_on") or []
        deps = [d for d in deps if isinstance(d, str)]
        valid_deps: list[str] = []
        for dep in deps:
            if dep in by_dir:
                valid_deps.append(dep)
                if dep not in seen:
                    queue.append(dep)
            else:
                suggestion = _closest(dep, list(by_dir.keys()))
                msg = f"'{name}' depends on missing skill '{dep}'"
                if suggestion:
                    msg += f" (did you mean '{suggestion}'?)"
                warnings.append(msg)
        adjacency[name] = valid_deps

    visited: set[str] = set()
    on_stack: set[str] = set()
    order: list[str] = []

    def visit(node: str, path: list[str]) -> None:
        if node in on_stack:
            cycle = path[path.index(node):] + [node]
            raise CycleError(cycle)
        if node in visited:
            return
        on_stack.add(node)
        for dep in adjacency.get(node, []):
            visit(dep, path + [node])
        on_stack.discard(node)
        visited.add(node)
        order.append(node)

    for name in names:
        visit(name, [])

    steps = [{"name": n, "depends_on": adjacency.get(n, [])} for n in order]
    return ComposePlan(steps=steps, warnings=warnings)


def _closest(needle: str, haystack: list[str]) -> str | None:
    matches = get_close_matches(needle, haystack, n=1, cutoff=0.6)
    return matches[0] if matches else None
