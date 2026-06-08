# TaskMaster v1.1.1 Gap-Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship TaskMaster v1.1.1 — close the four real v1.1 DoD gaps (A–D) with tests, and run a bounded investigation of the degraded-mode scoring quality (Gap E).

**Architecture:** TDD per gap. All new tests run in the base env (no `[semantic]`, `[mcp]`, `[openai]` extras). Changes are confined to the install module, the MCP server module, the CLI dispatch, and the README. Gap E is a time-boxed research task with a clear "if no fix, document" branch.

**Tech Stack:** Python 3.10+, pytest, argparse, `difflib.get_close_matches`, FastMCP (not required for tests), markdown README.

**Repo root:** `/Users/ohmskiii/Documents/Builds/TaskMaster`
**Spec file:** `docs/superpowers/specs/2026-06-08-taskmaster-v1.1.1-gap-fix-design.md`

---

## File map (changes per gap)

| Gap | Files touched |
|---|---|
| A — install closest-match | `taskmaster/install.py` (refactor + add validator), `tests/test_install.py` |
| B — MCP tool tests | `taskmaster/mcp/server.py` (extract pure tool functions), `tests/test_mcp_tools.py` (new) |
| C — Degraded-mode test | `tests/test_recommend.py` (or `tests/test_cli_phase1.py`) |
| D — README MCP setup | `README.md` |
| E — Scoring investigation | `taskmaster/recommend.py` (only if fix found), `tests/test_recommend.py`, `README.md` |

---

## Task 1: Gap A — install closest-match suggestions (TDD)

**Files:**
- Modify: `taskmaster/install.py:60-73` (skill resolution block)
- Modify: `taskmaster/install.py:1-20` (imports, new helper)
- Test: `tests/test_install.py`

### Step 1: Write the failing test

Open `tests/test_install.py` and add this test inside `class TestInstall(unittest.TestCase)`:

```python
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
```

### Step 2: Run the new tests to verify they fail

Run:
```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && .venv/bin/pytest tests/test_install.py::TestInstall::test_install_unknown_skill_suggests_closest tests/test_install.py::TestInstall::test_install_multiple_unknowns_reported_together -v
```

Expected: FAIL with `AssertionError: 'Did you mean' not found in 'Skill not found: python'` (or similar — current message has no suggestion).

### Step 3: Add the closest-match helper and rewrite the resolution block

In `taskmaster/install.py`, add this import at the top with the others:

```python
from difflib import get_close_matches
```

Add the new error class to `taskmaster/errors.py` (after the existing `InstallError` class, before `EmbeddingError`):

```python
class InstallUsageError(InstallError):
    """Raised when ``install`` is called with invalid arguments (e.g. unknown skill name)."""
    code = "install_usage"
    recoverable = False
```

Update the import in `taskmaster/install.py` (line 17) to bring in the new class:

```python
from .errors import InstallError, InstallUsageError
```

In `taskmaster/cli.py` `_cmd_install` (lines 290-307), update the `except` block to also catch `InstallUsageError` and return exit code 2 (usage error, distinct from runtime errors). Replace lines 304-306:

```python
    except InstallUsageError as e:
        print(f"Error: {e}")
        return 2
    except InstallError as e:
        print(f"Error: {e}")
        return 1
```

Add a CLI-level test for exit code 2 in `tests/test_install.py` (inside `class TestInstall`): (Note: this test is dropped in favor of the simpler exception-class test below.)

```python
def test_install_cli_exit_code_on_unknown_skill(self):
    from taskmaster import cli
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()) as _out, contextlib.redirect_stderr(buf):
        rc = cli.main(["install", "claude", "--skills", "pyhton"])
    self.assertEqual(rc, 2)
    self.assertIn("Did you mean", buf.getvalue())
```

(Note: install also tries to write to `~/.claude/skills` — to make this test hermetic, the `_cmd_install` flow would normally need a working dir. If it does I/O before the validation, monkey-patch `install_skills` to raise the usage error directly. A simpler alternative: the test invokes `install_skills` directly and asserts `InstallUsageError` is raised; the CLI-level exit code test is then covered by the engine-level test. Use the simpler form — drop the CLI-exit-code test and just assert the exception class.)

Add this simpler test instead:

```python
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
```

Also update the existing `test_install_invalid_skill` (line 110 in `tests/test_install.py`) to assert `InstallUsageError` instead of `InstallError`, so it documents the new contract:

```python
def test_install_invalid_skill(self):
    from taskmaster.install import InstallUsageError
    with self.assertRaises(InstallUsageError):
        install_skills(
            target="claude",
            scope="project",
            skill_names=["non-existent"],
            all_skills=self.mock_skills
        )
```

Add this module-level helper after `TARGET_PATHS` (after line 31):

```python
def _closest_matches(needle: str, haystack: list[str], n: int = 3) -> list[str]:
    """Return up to ``n`` closest matches for ``needle`` in ``haystack``."""
    return get_close_matches(needle, haystack, n=n, cutoff=0.5)
```

Replace the `if skill_names:` block (lines 60-73) with this:

```python
    selected_skills: list[dict[str, Any]] = []
    if skill_names:
        by_dir_names = list(by_dir.keys()) + [
            s.get("frontmatter", {}).get("name", "")
            for s in all_skills
        ]
        by_dir_names = [n for n in by_dir_names if n]

        errors: list[str] = []
        for name in skill_names:
            if name in by_dir:
                selected_skills.append(by_dir[name])
                continue
            # Try matching by frontmatter name
            matched = None
            for s in all_skills:
                if s.get("frontmatter", {}).get("name") == name:
                    matched = s
                    break
            if matched is not None:
                selected_skills.append(matched)
                continue
            # Unknown — gather suggestion
            suggestions = _closest_matches(name, by_dir_names, n=3)
            if suggestions:
                errors.append(
                    f"Unknown skill '{name}'. Did you mean: {', '.join(suggestions)}?"
                )
            else:
                errors.append(f"Unknown skill '{name}'.")

        if errors:
            raise InstallUsageError("\n".join(errors))
    else:
        selected_skills = all_skills
```

The rest of the function (the `results = {}` block and the per-target loop) is unchanged and still returns the `results` dict as before.

### Step 4: Run the install tests to verify they pass

Run:
```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && .venv/bin/pytest tests/test_install.py -v
```

Expected: all install tests pass (the 5 existing + 2 new = 7).

### Step 5: Run the full base test suite to confirm no regression

Run:
```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && .venv/bin/pytest --ignore=tests/test_embeddings_provider.py --ignore=tests/test_embeddings_index.py -q
```

Expected: ≥ 70 passed (72 total, 2 collection errors remain on the `numpy`-dependent files — out of scope).

### Step 6: Commit

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && git add taskmaster/install.py tests/test_install.py && git -c user.name=ohmskiii -c user.email=ohmskiii@local commit -m "feat(install): suggest closest matches for unknown skill names (closes Gap A)"
```

---

## Task 2: Gap C — degraded-mode test assertion (TDD)

**Files:**
- Test: `tests/test_recommend.py` (existing) or `tests/test_cli_phase1.py`

### Step 1: Read the existing recommend test to know its style

Run:
```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && head -40 tests/test_recommend.py
```

Note the test class/fixture pattern. The test below must match.

### Step 2: Add the degraded-mode test

Append to the existing test class in `tests/test_recommend.py` (do **not** create a new file — keep all recommend tests together):

```python
    def test_recommend_degraded_mode_banner_on_stdout(self):
        """In degraded mode, the CLI prints the degraded banner to stdout."""
        import io
        import contextlib
        from taskmaster import cli

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cli.main(["recommend", "debug a production API timeout", "--max", "3"])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("degraded mode", out)
        self.assertIn("Recommended skills:", out)

    def test_recommend_json_includes_degraded_flag(self):
        """JSON output must include a 'degraded' field per result."""
        import io
        import contextlib
        import json
        from taskmaster import cli

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cli.main(["recommend", "debug a production API timeout", "--max", "3", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertIsInstance(payload, list)
        self.assertGreaterEqual(len(payload), 1)
        for item in payload:
            self.assertIn("degraded", item)
            # In base env (no [semantic] extra), every result should be degraded
            self.assertTrue(item["degraded"])
```

### Step 3: Run the new tests to verify they pass

Run:
```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && .venv/bin/pytest tests/test_recommend.py -v
```

Expected: existing tests + 2 new tests pass.

### Step 4: Commit

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && git add tests/test_recommend.py && git -c user.name=ohmskiii -c user.email=ohmskiii@local commit -m "test(recommend): assert degraded-mode banner and JSON degraded flag (closes Gap C)"
```

---

## Task 3: Gap B — MCP tool tests via refactor (TDD)

**Files:**
- Modify: `taskmaster/mcp/server.py` (extract tool bodies)
- Create: `tests/test_mcp_tools.py`

### Step 1: Write the failing test file

Create `tests/test_mcp_tools.py`:

```python
"""Tests for MCP tool function bodies.

The MCP tools are registered inside ``_make_server()`` (which requires
the ``mcp`` extra). To test without that dependency, this file exercises
the pure-function wrappers that ``_make_server()`` calls. If those
wrappers do not exist yet, the imports below will fail.
"""

import unittest


class TestMcpToolFunctions(unittest.TestCase):
    def test_list_categories_returns_non_empty_dict(self):
        from taskmaster.mcp.server import tool_list_categories
        result = tool_list_categories()
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)
        # All values are counts
        for v in result.values():
            self.assertIsInstance(v, int)
            self.assertGreater(v, 0)

    def test_get_skill_returns_frontmatter_and_body(self):
        from taskmaster.mcp.server import tool_get_skill
        # Use a skill that is definitely in the corpus
        result = tool_get_skill("bug-hunter")
        self.assertNotIn("error", result)
        self.assertIn("frontmatter", result)
        self.assertIn("body", result)
        self.assertIn("name", result["frontmatter"])
        self.assertEqual(result["frontmatter"]["name"], "bug-hunter")

    def test_get_skill_missing_returns_error(self):
        from taskmaster.mcp.server import tool_get_skill
        result = tool_get_skill("definitely-not-a-real-skill-xyz")
        self.assertIn("error", result)
        self.assertEqual(result["error"], "not_found")

    def test_recommend_skills_degraded_in_base_env(self):
        from taskmaster.mcp.server import tool_recommend_skills
        result = tool_recommend_skills("debug a production API timeout", max_results=3)
        self.assertIsInstance(result, str)
        # In base env, no semantic index → degraded mode
        self.assertIn("degraded mode", result)

    def test_compose_skills_topological_order(self):
        from taskmaster.mcp.server import tool_compose_skills
        result = tool_compose_skills(["error-detective", "distributed-tracing", "incident-responder"], json_output=True)
        import json
        plan = json.loads(result)
        self.assertIn("plan", plan)
        self.assertGreaterEqual(len(plan["plan"]), 3)
        # Topological order: dependents come AFTER dependencies.
        # The "order" field is 1-indexed.
        order = {step["name"]: step["order"] for step in plan["plan"]}
        for step in plan["plan"]:
            for dep in step["depends_on"]:
                self.assertLess(order[dep], order[step["name"]],
                                f"Dependency '{dep}' must come before '{step['name']}'")

    def test_validate_skill_known_bad_returns_error(self):
        from taskmaster.mcp.server import tool_validate_skill
        # A skill that doesn't exist on disk
        result = tool_validate_skill("definitely-not-a-real-skill-xyz")
        self.assertIn("Error", result)
```

### Step 2: Run the test file to verify it fails (collection error)

Run:
```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && .venv/bin/pytest tests/test_mcp_tools.py -v
```

Expected: collection error `ImportError: cannot import name 'tool_list_categories' from 'taskmaster.mcp.server'`.

### Step 3: Refactor `taskmaster/mcp/server.py` — extract tool bodies

This is a mechanical refactor. For each `@mcp.tool(name=...)` block, copy the function body into a new module-level function named `tool_<name>` (no `@mcp.tool` decorator), and have the in-server function delegate to it.

Add these module-level functions **before** `_make_server()` (after the existing imports and `_build_index`):

```python
def tool_list_categories() -> dict[str, int]:
    """MCP tool: list_categories — pure function, no mcp import needed."""
    skills = taskmaster.get_all_skills()
    from collections import Counter
    return dict(Counter(s["frontmatter"].get("category", "?") for s in skills).most_common())


def tool_get_skill(name: str) -> dict[str, Any]:
    """MCP tool: get_skill — pure function, no mcp import needed."""
    all_skills = taskmaster.get_all_skills()
    skill = None
    for s in all_skills:
        if s["dir"] == name or s["frontmatter"].get("name") == name:
            skill = s
            break
    if not skill:
        return {"error": "not_found", "message": f"Skill '{name}' not found"}
    return {
        "name": skill["frontmatter"].get("name", skill["dir"]),
        "frontmatter": skill["frontmatter"],
        "body": skill.get("body", ""),
        "path": str(skill.get("path", "")),
        "size_bytes": skill.get("size_bytes"),
        "line_count": skill.get("line_count"),
        "quality": taskmaster.score_skill_quality(skill),
    }


def tool_recommend_skills(task: str, max_results: int = 5, max_risk: str | None = None) -> str:
    """MCP tool: recommend_skills — pure function, no mcp import needed."""
    skills = taskmaster.get_all_skills()
    index = _build_index()
    from taskmaster.recommend import recommend_skills as engine_recommend
    results = engine_recommend(task, skills=skills, index=index, k=max_results, max_risk=max_risk)
    if not results:
        return "No recommendations found."
    lines = [f"Recommendations for '{task}':"]
    if index is None:
        lines.append("  (degraded mode — semantic embeddings unavailable)")
    for r in results:
        fm = r["skill"]["frontmatter"]
        name = fm.get("name", r["skill"]["dir"])
        reasons = " | ".join(r["reasons"])
        lines.append(f"  {name:<35} score={r['score']:.3f}  {reasons}")
    return "\n".join(lines)


def tool_compose_skills(skills: list[str], json_output: bool = False) -> str:
    """MCP tool: compose_skills — pure function, no mcp import needed."""
    all_skills = taskmaster.get_all_skills()
    from taskmaster.compose import compose_skills as engine_compose
    from taskmaster.errors import CycleError
    try:
        plan = engine_compose(skills, skills=all_skills)
    except CycleError as e:
        return f"Error: Dependency cycle detected — {' -> '.join(e.cycle)}"
    except KeyError as e:
        return f"Error: {e}"
    if json_output:
        return json.dumps(plan.to_dict(), indent=2)
    lines = ["Composed plan:"]
    for step in plan.steps:
        deps = ", ".join(step["depends_on"]) if step["depends_on"] else "-"
        lines.append(f"  {step['name']:<35} depends_on: {deps}")
    for w in plan.warnings:
        lines.append(f"  warning: {w}")
    return "\n".join(lines)


def tool_validate_skill(skill_dir: str) -> str:
    """MCP tool: validate_skill — pure function, no mcp import needed."""
    skill = taskmaster.parse_skill(taskmaster.SKILLS_DIR / skill_dir)
    if not skill:
        return f"Error: no SKILL.md in '{skill_dir}'"
    fm = skill["frontmatter"]
    issues = taskmaster.validate_skill(skill)
    if issues:
        return f"Issues: {'; '.join(issues)}"
    return f"Status: valid ({fm.get('name', skill_dir)})"
```

Now, inside `_make_server()`, replace each `@mcp.tool(...) def <name>(...)` body to delegate to the new module-level functions. Example — replace:

```python
    @mcp.tool(name="list_categories", description="List all skill categories and their counts")
    def list_categories() -> dict[str, int]:
        skills = taskmaster.get_all_skills()
        from collections import Counter
        return dict(Counter(s["frontmatter"].get("category", "?") for s in skills).most_common())
```

with:

```python
    @mcp.tool(name="list_categories", description="List all skill categories and their counts")
    def list_categories() -> dict[str, int]:
        return tool_list_categories()
```

Do the same for `get_skill`, `recommend_skills`, `compose_skills`, `validate_skill`. The other tools (`validate_all`, `search_skills`, `list_skills`, `suggest`, `check_skill`, `corpus_stats`, `install_skill`) keep their bodies inline — they are not in the test's required set.

### Step 4: Run the test file to verify it passes

Run:
```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && .venv/bin/pytest tests/test_mcp_tools.py -v
```

Expected: 6 tests pass.

### Step 5: Confirm the MCP server still loads (requires `mcp` extra, but import should not crash)

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && .venv/bin/python -c "from taskmaster.mcp.server import _make_server, tool_list_categories, tool_get_skill, tool_recommend_skills, tool_compose_skills, tool_validate_skill; print('ok')"
```

Expected: prints `ok` and exits 0. (Note: `_make_server` itself imports `mcp`, which will fail if the extra isn't installed — that's expected and out of scope; the test only needs the tool functions.)

If the import fails because `mcp` is not installed, that's fine. Verify just the tool functions import:

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && .venv/bin/python -c "from taskmaster.mcp.server import tool_list_categories, tool_get_skill, tool_recommend_skills, tool_compose_skills, tool_validate_skill; print('ok')"
```

Expected: `ok`.

### Step 6: Run the full base test suite

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && .venv/bin/pytest --ignore=tests/test_embeddings_provider.py --ignore=tests/test_embeddings_index.py -q
```

Expected: ≥ 76 passed (70 prior + 2 install + 2 recommend + 6 mcp − 4 if any old tests broken).

### Step 7: Commit

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && git add taskmaster/mcp/server.py tests/test_mcp_tools.py && git -c user.name=ohmskiii -c user.email=ohmskiii@local commit -m "refactor(mcp): extract tool bodies into testable pure functions; add MCP tool tests (closes Gap B)"
```

---

## Task 4: Gap D — README MCP setup section

**Files:**
- Modify: `README.md`

### Step 1: Verify the MCP server invocation path

Run:
```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && .venv/bin/pip install 'taskmaster[mcp]' 2>&1 | tail -3
```

Then verify the server starts (it will block; use timeout):

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && timeout 2 .venv/bin/python -m taskmaster.mcp.server serve </dev/null; echo "exit=$?"
```

Expected: server starts (no error), then is killed by timeout, prints `exit=124`. If `python -m taskmaster.mcp.server` is wrong, try `python -m taskmaster.mcp` (drop `.server`). The README snippet must use whichever one works.

If neither works as a module, fall back to the existing CLI subcommand:

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && .venv/bin/python -c "from taskmaster.mcp.server import serve; print('serve importable')"
```

Then in the README, use the form `python3 -m taskmaster.mcp.server` (or whichever is verified).

### Step 2: Add the MCP Setup section to README.md

Insert a new section between the "Quick Start" block and the "Project layout" block (or wherever the README currently transitions from "Quick Start" to "Project layout"). The exact line numbers shift, so search first:

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && grep -n "^## " README.md
```

Pick an insertion point that flows naturally. Recommended placement: immediately after the "Quick Start" `bash` block (so a new user reads the CLI quick start, then learns the MCP option). The new section is:

```markdown
## MCP Setup

Expose TaskMaster as an MCP server so Claude Code, Cursor, and other
MCP clients can call its tools directly. Requires the `mcp` extra.

### Install

```bash
pip install "taskmaster[mcp]"
```

### Verify the server starts

```bash
python3 -m taskmaster.mcp.server serve
```

(The server blocks on stdio. Press Ctrl-C to stop. To test end-to-end,
wire it into a client — see below.)

### Claude Code

Add a `.mcp.json` at your project root (or `~/.claude/mcp.json` for
user-scope):

```json
{
  "mcpServers": {
    "taskmaster": {
      "command": "python3",
      "args": ["-m", "taskmaster.mcp.server", "serve"]
    }
  }
}
```

Restart Claude Code. The TaskMaster tools (12 of them:
`validate_all`, `search_skills`, `list_skills`, `list_categories`,
`get_skill`, `suggest`, `recommend_skills`, `compose_skills`,
`check_skill`, `validate_skill`, `corpus_stats`, `install_skill`)
should appear in the tool picker.

### Cursor

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "taskmaster": {
      "command": "python3",
      "args": ["-m", "taskmaster.mcp.server", "serve"]
    }
  }
}
```

Restart Cursor. The same 12 tools become available.
```

### Step 3: Render-check the README

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && .venv/bin/python -c "
import re
with open('README.md') as f:
    text = f.read()
# Check JSON blocks parse
for m in re.finditer(r'\`\`\`json\\n(.*?)\\n\`\`\`', text, re.DOTALL):
    import json
    json.loads(m.group(1))
    print('json block ok:', m.group(1)[:60])
print('total lines:', len(text.splitlines()))
"
```

Expected: two `json block ok` lines printed, plus the line count.

### Step 4: Commit

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && git add README.md && git -c user.name=ohmskiii -c user.email=ohmskiii@local commit -m "docs(readme): add MCP setup section with Claude Code and Cursor config snippets (closes Gap D)"
```

---

## Task 5: Gap E — Bounded scoring investigation

**Files:**
- Possibly modify: `taskmaster/recommend.py`
- Possibly modify: `tests/test_recommend.py`
- Possibly modify: `README.md`

**Time-box: 2 hours.** If the fix takes longer, stop and ship the documentation branch instead.

### Step 1: Reproduce the bug

Run:
```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && .venv/bin/python taskmaster.py recommend "debug a production API timeout" --max 5
```

Expected output (current, broken):
```
  (degraded mode — semantic embeddings unavailable)

Recommended skills:
1. comfyui-gateway
2. bug-hunter
...
```

Record the actual top 5 names into a comment in `tests/test_recommend.py` (this is the regression baseline).

### Step 2: Diagnose

The keyword scorer in `taskmaster/recommend.py:89-102` counts token overlap between the task and a skill's `name + description + first 1000 chars of body`. The task `"debug a production API timeout"` tokenizes to roughly `{debug, production, api, timeout}`. `comfyui-gateway`'s description starts with "REST API gateway for ComfyUI servers…" — the token `api` matches, giving it the same `keyword` score as any other skill mentioning "api".

**Hypothesis to test:** Adding a small bias toward skills whose **name** matches a task token (and away from incidental description matches) should put `bug-hunter` (name match on `debug` / `bug`) above `comfyui-gateway`.

### Step 3: Try a minimal fix

In `taskmaster/recommend.py`, modify `_keyword_score` to give a small bonus when the name tokens overlap. Replace the function (lines 89-102) with:

```python
def _keyword_score(task_tokens: set[str], skill: dict[str, Any]) -> float:
    if not task_tokens:
        return 0.0
    fm = skill.get("frontmatter", {}) or {}
    name = str(fm.get("name") or "")
    name_tokens = _tokenize_text(name)
    name_overlap = task_tokens & name_tokens

    text_parts = [
        str(fm.get("description") or ""),
        str(skill.get("body") or "")[:1000],
    ]
    haystack_tokens = _tokenize_text(" ".join(text_parts))
    if not haystack_tokens:
        return 0.0
    desc_overlap = (task_tokens & haystack_tokens) - name_overlap
    overlap = len(name_overlap) * 2 + len(desc_overlap)  # name matches count double
    return overlap / max(len(task_tokens) * 2, 1)
```

(The name is weighted 2x because incidental description matches like "api" are weak signals.)

### Step 4: Run the canonical query and the full suite

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && .venv/bin/python taskmaster.py recommend "debug a production API timeout" --max 5
```

**If `bug-hunter` or `error-detective` is in the top 3** → fix is good. Add a regression test:

```python
def test_recommend_debug_query_ranks_debugging_skills_highly(self):
    from taskmaster.recommend import recommend_skills
    results = recommend_skills("debug a production API timeout", skills=taskmaster.get_all_skills(), index=None, k=5)
    top3 = [r["skill"]["dir"] for r in results[:3]]
    self.assertTrue(
        any(name in top3 for name in ("bug-hunter", "error-detective", "distributed-tracing")),
        f"Expected a debugging-related skill in top 3, got {top3}",
    )
```

Run full base suite:
```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && .venv/bin/pytest --ignore=tests/test_embeddings_provider.py --ignore=tests/test_embeddings_index.py -q
```

**If ≥ 78 tests still pass** → ship the fix. Commit:
```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && git add taskmaster/recommend.py tests/test_recommend.py && git -c user.name=ohmskiii -c user.email=ohmskiii@local commit -m "fix(recommend): weight name-token matches 2x over incidental description matches (closes Gap E)"
```

Then proceed to Task 6.

**If `bug-hunter` is not in the top 3, OR ≥ 1 test regresses** → revert the change with `git checkout taskmaster/recommend.py` and go to the documentation branch (Step 5).

### Step 5 (documentation branch — only if Step 4 fix fails): add `--keyword-only` flag + README note

**5a.** In `taskmaster/cli.py`, add a `--keyword-only` flag to the `recommend` subcommand. Find line ~64 and add:

```python
    recommend_p.add_argument("--keyword-only", action="store_true",
                             help="Skip embedding index build; use keyword scoring only")
```

Modify `_cmd_recommend` to honor the flag. Replace the `_embedding_index` call (lines 122-126):

```python
    index = None
    if not args.keyword_only:
        try:
            index, _ = _embedding_index(skills, rebuild=False)
        except RuntimeError:
            index = None
```

(Below this, the existing `index is None` check at line 141 already prints the degraded banner, so `--keyword-only` gets the same behavior without trying to build an index.)

**5b.** Add a test:

```python
    def test_recommend_keyword_only_flag(self):
        from taskmaster import cli
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cli.main(["recommend", "debug a production API timeout", "--max", "3", "--keyword-only"])
        self.assertEqual(rc, 0)
        self.assertIn("degraded mode", buf.getvalue())
```

**5c.** Add a README note. In `README.md`, inside the "## Phase 1 — Agent-Native Engine" section, after the `recommend` examples, add:

```markdown
#### Note on degraded mode

When the `[semantic]` extra is not installed, `recommend` falls back to
keyword-only scoring. This is a best-effort mode — results may be
noisy for short queries (e.g. `comfyui-gateway` may match "API" in
descriptions). For production routing, install the semantic extra:

```bash
pip install "taskmaster[semantic]"
```

You can also force keyword-only mode explicitly with `--keyword-only`
(useful in CI or when the embedding index is intentionally absent).
```

**5d.** Run full suite, then commit:
```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && .venv/bin/pytest --ignore=tests/test_embeddings_provider.py --ignore=tests/test_embeddings_index.py -q
cd /Users/ohmskiii/Documents/Builds/TaskMaster && git add taskmaster/cli.py tests/test_recommend.py README.md && git -c user.name=ohmskiii -c user.email=ohmskiii@local commit -m "docs(recommend): document degraded-mode limitation and add --keyword-only flag (Gap E, doc branch)"
```

**5e.** File a follow-up spec. Create `docs/superpowers/specs/2026-06-08-taskmaster-recommend-scoring-rework-design.md` with a one-paragraph stub: "Rewrite the recommend keyword scorer to use TF-IDF weighting and a name-match bonus. Out of scope for v1.1.1; tracked here."

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && git add docs/superpowers/specs/2026-06-08-taskmaster-recommend-scoring-rework-design.md && git -c user.name=ohmskiii -c user.email=ohmskiii@local commit -m "docs(spec): file follow-up spec for recommend scoring rework"
```

---

## Task 6: Final integration — bump version, update CHANGELOG, run full suite

**Files:**
- Modify: `pyproject.toml` (version bump)
- Modify: `README.md` (add CHANGELOG entry, or note it)
- (Optional) Create: `CHANGELOG.md`

### Step 1: Bump version

In `pyproject.toml` line 7, change `version = "1.1.0"` to `version = "1.1.1"`.

### Step 2: Add a CHANGELOG entry

If `CHANGELOG.md` exists at the repo root, prepend a v1.1.1 section. If not, create it with just the v1.1.1 section:

```markdown
# Changelog

## v1.1.1 — 2026-06-08

Gap-fix patch against the v1.1 "Agent-Native Skill Router" DoD:

- **install:** unknown skill names now suggest the 3 closest matches (e.g. `python` → `temporal-python-pro, dbos-python, temporal-python-testing`).
- **mcp:** 5 core MCP tools now have direct unit tests (`list_categories`, `get_skill`, `recommend_skills`, `compose_skills`, `validate_skill`). Tool bodies were extracted into pure module-level functions to make them testable without the `mcp` extra.
- **recommend (test):** degraded-mode banner and JSON `degraded` flag are now asserted.
- **readme:** new "MCP Setup" section with copy-paste `.mcp.json` snippets for Claude Code and Cursor.
- **recommend (scoring):** name-token matches are now weighted 2x over incidental description matches; `bug-hunter` and `error-detective` rank in the top 3 for "debug a production API timeout". (Or, if the doc branch was taken: `--keyword-only` flag added; README documents the degraded-mode limitation; a follow-up spec is filed for a fuller scoring rework.)
```

### Step 3: Run the full base suite one more time

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && .venv/bin/pytest --ignore=tests/test_embeddings_provider.py --ignore=tests/test_embeddings_index.py -q
```

Expected: ≥ 79 passed. Note the actual count in the commit message.

### Step 4: Verify CLI reports new version

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && grep '^version' pyproject.toml
```

Expected: `version = "1.1.1"`.

### Step 5: Commit

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && git add pyproject.toml CHANGELOG.md && git -c user.name=ohmskiii -c user.email=ohmskiii@local commit -m "chore(release): bump to v1.1.1 with CHANGELOG entry"
```

### Step 6: Final summary

Run:
```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster && git log --oneline main~6..main
```

Expected: 6 new commits (one per task, plus the spec commit from brainstorming is already on main). Verify each commit message matches the gap it closes.

Report the final test count in the PR description.

---

## Definition of done (checked against spec)

- [ ] Gap A: `install` exits 2 with closest-match suggestions on unknown names
- [ ] Gap B: `tests/test_mcp_tools.py` has 5+ tests, all pass in base env
- [ ] Gap C: degraded-mode banner and JSON `degraded` are asserted
- [ ] Gap D: README has `## MCP Setup` section with Claude Code + Cursor snippets, snippet verified to start the server
- [ ] Gap E: either scoring fix ships (with regression test, all tests pass) OR `--keyword-only` + README note + follow-up spec ships
- [ ] `pytest` (base env) reports ≥ 79 passed
- [ ] `pyproject.toml` reports `1.1.1`
- [ ] CHANGELOG entry added
- [ ] 6 atomic commits on the branch
