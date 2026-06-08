# TaskMaster v1.1.1 Gap-Fix Design

## Goal

Ship v1.1.1 — a small, targeted patch that closes the four real gaps (A–D)
between the v1.1 "Agent-Native Skill Router" definition of done and the
current state of the repository, plus a bounded investigation (Gap E) of one
scoring-quality issue. Each gap is backed by evidence from a real CLI
invocation or test run, and each shippable fix is accompanied by a test that
proves it.

## Context

TaskMaster is at v1.1.0. The repository already implements the v1.1 roadmap:

- `recommend` (hybrid semantic + keyword + tag scorer)
- `compose` (topological ordering via `depends_on` / `composes_with`)
- `embed` (local sentence-transformers / OpenAI embedding index)
- `mcp serve` (12 MCP tools over stdio)
- `install` / `uninstall` (Claude, Cursor, Qwen targets, user/project scope)
- Optional frontmatter `depends_on` and `composes_with`
- 269-skill corpus across 20 categories

This spec does **not** redesign any of that. It fixes specific gaps surfaced by
auditing the v1.1 DoD against actual CLI behavior and the test suite.

## Evidence (audit findings)

| DoD claim | Evidence | Verdict |
|---|---|---|
| `recommend` works with explainable scoring | `taskmaster recommend "debug a production API timeout"` returns `comfyui-gateway` as #1 in degraded mode | Broken in degraded mode — see Gap E |
| `compose` works with dependency ordering | `taskmaster compose error-detective distributed-tracing incident-responder` returns a topologically valid plan | Works |
| `embed` builds a local semantic index | `taskmaster embed` requires `[semantic]` extra; `numpy` is not in the base env | Works, but unreadable from base install — docs gap only |
| `mcp serve` exposes ≥5 tools | 12 tools registered: `validate_all`, `search_skills`, `list_skills`, `list_categories`, `get_skill`, `suggest`, `recommend_skills`, `compose_skills`, `check_skill`, `validate_skill`, `corpus_stats`, `install_skill` | Works, but zero test coverage — see Gap B |
| README has copy-paste setup for Claude Code/Cursor | README shows CLI install only; no MCP config snippets | Missing — see Gap D |
| Tests cover recommend/compose/MCP/invalid skills/degraded mode | 70 base tests pass; 2 collections error on missing `numpy`; no MCP tool test; degraded-mode banner not asserted | Partial — see Gaps B and C |

Bonus issue surfaced during audit: `taskmaster install claude --skills error-detective,python`
exits with `Error: Skill not found: python` and no closest-match hint. The
`compose` command already has closest-match suggestions for missing dependencies;
`install` does not. See Gap A.

## Scope

### In scope

- Gap A: `install` closest-match suggestions for unknown skill names
- Gap B: MCP tool-response test coverage
- Gap C: Degraded-mode test assertion (banner + JSON `degraded` field)
- Gap D: README MCP setup section with Claude Code and Cursor snippets
- Gap E: Bounded investigation of degraded-mode `recommend` scoring quality

### Out of scope (tracked elsewhere)

- Phase 2: MCP server hardening (lazy embeddings, error codes, transport options)
- Phase 3: `.taskmaster-manifest.json`, project-level vs user-level installer improvements
- Phase 4: Skill workbench (duplicate detector, quality dashboard, canonical generator)
- Phase 5: Harness integration
- Vision/positioning doc
- Qwen MCP client documentation (Qwen MCP support is less standardized; deferred)
- Scoring algorithm changes that require retraining or model swaps

## Gap A — Install command needs closest-match suggestions

### Current behavior

```
$ taskmaster install claude --skills error-detective,python
Error: Skill not found: python
```

The user gets no hint that `temporal-python-pro`, `dbos-python`, or
`temporal-python-testing` exist. The `compose` command already has this
functionality in `taskmaster.compose.suggest_closest`; `install` should
reuse it.

### Fix

In `taskmaster/install.py`, validate `--skills` before doing any I/O. For each
unknown name, look up the closest 3 matches using the same algorithm
`compose` uses. Emit a non-zero exit with a clear stderr message.

### Acceptance criteria

- `taskmaster install claude --skills error-detective,python` exits with code `2`
  and writes to stderr:
  `Unknown skill 'python'. Did you mean: temporal-python-pro, dbos-python, temporal-python-testing?`
- `taskmaster install claude --skills error-detective,bug-hunter` exits `0`.
- Multiple unknown names are reported in one error, not one at a time.
- New unit tests in `tests/test_install.py` cover: single unknown, multiple
  unknowns, no unknowns (regression), and exit-code assertion.

## Gap B — MCP tool-response tests

### Current state

`taskmaster/mcp/server.py` registers 12 tools. No test exercises any of them.
The existing test suite passes 70/72 (2 collection errors on missing `numpy`).

### Fix

Add `tests/test_mcp_tools.py` that calls the underlying tool functions directly
(importing them from `taskmaster.mcp.server` or a thin re-export module). For
each tool, the test calls it with a small fixture and asserts the response
shape.

### Tools that must be tested

1. `list_categories` — returns a non-empty dict mapping category → count
2. `get_skill` — given a known skill name, returns frontmatter + body
3. `recommend_skills` — given a task string, returns ≥1 result with
   `degraded: true` when embeddings are absent
4. `compose_skills` — given a list of skill names, returns a plan in
   topological order
5. `validate_skill` — given a known-bad fixture, returns a structured error
   list

### Acceptance criteria

- New file `tests/test_mcp_tools.py` with at least 5 test functions.
- All tests pass in the base environment (no `[semantic]`, `[mcp]`, or
  `[openai]` extras installed).
- All tests pass in CI on Python 3.10, 3.11, 3.12 (the classifiers in
  `pyproject.toml`).

## Gap C — Degraded-mode test assertion

### Current state

`recommend` prints `(degraded mode — semantic embeddings unavailable)` to
stderr in degraded mode, and `--json` output is expected to include
`"degraded": true`. Neither is asserted by any test.

### Fix

Add a test that runs `taskmaster recommend` in a subprocess (or invokes the
CLI via `argparse`) without the `[semantic]` extra installed and asserts:

1. Stderr contains the literal string `degraded mode`.
2. The JSON output (when `--json` is passed) contains a top-level `degraded: true`
   field per result, OR a top-level `degraded: true` envelope (whichever the
   current implementation uses — match the existing shape, do not invent one).

### Acceptance criteria

- New test in `tests/test_recommend.py` (or `tests/test_cli_phase1.py` if it
  fits better with the existing layout).
- Test passes in base env.
- Test fails loudly if the degraded banner is removed by accident.

## Gap D — README MCP setup section

### Current state

The README documents CLI usage of `install` but not MCP server setup. The
"wow" feature — agents calling TaskMaster via MCP — is unreachable for a
user who has never wired an MCP server into Claude Code or Cursor.

### Fix

Add a new section `## MCP Setup` to `README.md` (placement: between the
existing "Quick Start" / "Python API" section and the "Agent-Native Skill OS"
section). The section must contain:

1. **Install the MCP extra**: `pip install "taskmaster[mcp]"`
2. **Start the server** (one-line test): `python3 -m taskmaster.mcp serve`
3. **Claude Code config** — a copy-paste JSON block for `.mcp.json`:
   ```json
   {
     "mcpServers": {
       "taskmaster": {
         "command": "python3",
         "args": ["-m", "taskmaster.mcp", "serve"]
       }
     }
   }
   ```
4. **Cursor config** — a copy-paste JSON block for `~/.cursor/mcp.json`:
   ```json
   {
     "mcpServers": {
       "taskmaster": {
         "command": "python3",
         "args": ["-m", "taskmaster.mcp", "serve"]
       }
     }
   }
   ```
5. **Verify**: a one-liner to confirm the server starts and lists tools.

The exact import path (`-m taskmaster.mcp` vs `-m taskmaster.mcp.server`)
must be confirmed against `taskmaster/__init__.py` and
`taskmaster/mcp/__init__.py` before the README is updated. This is a
precondition for the README change.

### Acceptance criteria

- README has a working `## MCP Setup` section with the four blocks above.
- A new doc test (or one-line manual check recorded in the PR description)
  confirms `python3 -m taskmaster.mcp serve` is the right invocation.
- The README snippet has been copy-pasted and the server actually starts
  (manual verification, recorded in the PR).

## Gap E — Bounded investigation: degraded-mode scoring quality

### Evidence

```
$ taskmaster recommend "debug a production API timeout" --max 5
  (degraded mode — semantic embeddings unavailable)

Recommended skills:
1. comfyui-gateway
2. bug-hunter
3. chrome-extension-developer
4. distributed-debugging-debug-trace
5. distributed-tracing
```

`comfyui-gateway` and `chrome-extension-developer` are obviously wrong
results for a "debug production timeout" query. The expected top results
would be `error-detective`, `bug-hunter`, `distributed-tracing`,
`incident-responder`, or `performance-profiling`.

### Hypothesis

The keyword scorer in `taskmaster.recommend` is matching on tags or
substrings that don't reflect the actual task intent. The user's claim
"timeout implies performance + tracing" in the v1.1 DoD is not being met
by the keyword-only path.

### Fix (bounded)

This is a **time-boxed investigation**, not a full scoring rewrite. The
investigation must answer one question:

> Can the existing keyword scorer (with no model changes) be tuned or
> guarded such that `error-detective` or `bug-hunter` appears in the top
> 3 for the canonical "debug a production API timeout" query, **without
> regressing** on the existing 70 passing tests?

**If yes** (≤ 2 hours of work): implement the fix and add a regression
test asserting the top-3 result for that canonical query.

**If no**: do not ship a fix. Instead:
1. Add a `--keyword-only` flag to `recommend` so the caller knows what
   mode they are in.
2. Document the limitation in the README: "Degraded mode is best-effort;
   for production routing, install `[semantic]`."
3. File a follow-up spec for the scoring rework (out of scope here).

### Acceptance criteria

- A short written summary of the investigation is included in the PR.
- Either: a regression test exists asserting the top-3 result for the
  canonical query, **and all 70+ existing tests still pass**.
- Or: the `--keyword-only` flag ships, README is updated, and a follow-up
  issue is filed (linked from the PR).

## Risk register

| Risk | Mitigation |
|---|---|
| Gap E investigation runs long | Hard 2-hour time-box. If it doesn't pay off, ship the `--keyword-only` flag and document. |
| MCP tests require `mcp` extra | Tests must call underlying tool functions directly, not the FastMCP transport. No `[mcp]` required to run tests. |
| README MCP config path is wrong | Verify `python3 -m taskmaster.mcp serve` works in a fresh shell before merging. |
| `install` exit code change breaks scripts | Use exit code `2` (standard "usage error"). Document in `--help`. |

## Test strategy

- New tests are added alongside existing ones in the same files where
  possible (`tests/test_install.py`, `tests/test_recommend.py`).
- New file `tests/test_mcp_tools.py` for Gap B.
- All new tests must run in the base environment (no optional extras).
- All 70 existing base-env tests must continue to pass.
- The 2 collection errors on `numpy` are **not** in scope to fix here —
  they belong to the optional-extras install flow, which is documented
  elsewhere.

## Definition of done

- [ ] Gap A: `install` returns exit 2 with closest-match suggestions on
      unknown skill names; tests added.
- [ ] Gap B: `tests/test_mcp_tools.py` exists with ≥5 tests, all passing
      in base env.
- [ ] Gap C: degraded-mode banner is asserted by a test.
- [ ] Gap D: README `## MCP Setup` section exists with Claude Code and
      Cursor copy-paste blocks; the snippet has been verified to start
      the server.
- [ ] Gap E: investigation summary in PR; either a regression test ships
      or `--keyword-only` + README note + follow-up issue.
- [ ] `pytest` passes (≥ 75 tests in base env, no new collection errors).
- [ ] `taskmaster --version` reports `1.1.1`.
- [ ] CHANGELOG entry added.
- [ ] PR description references this spec file.

## Out-of-scope follow-ups (for future specs)

1. Vision/positioning document
2. Phase 2 MCP server hardening (lazy embeddings, transport options, error codes)
3. Phase 3 installer improvements (`.taskmaster-manifest.json`, project-level)
4. Phase 4 skill workbench (duplicate detector, quality dashboard)
5. Phase 5 harness integration
6. Qwen MCP client documentation
7. Recommend scoring rework (if Gap E cannot be closed with a small fix)
