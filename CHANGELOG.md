# Changelog

## v1.1.1 — 2026-06-08

Gap-fix patch against the v1.1 "Agent-Native Skill Router" DoD:

- **install:** unknown skill names now suggest the 3 closest matches
  (e.g. `python` → `temporal-python-pro, dbos-python, temporal-python-testing`)
  and exit with code 2 (`InstallUsageError`, distinct from runtime
  `InstallError` at code 1).
- **mcp:** 5 core MCP tools now have direct unit tests
  (`list_categories`, `get_skill`, `recommend_skills`, `compose_skills`,
  `validate_skill`). Tool bodies were extracted into pure module-level
  functions so they can be tested without the `[mcp]` extra. The
  `FastMCP` import is now lazy inside `_make_server()`.
- **mcp entry point:** new `taskmaster/mcp/__main__.py` enables
  `python -m taskmaster.mcp serve` for MCP clients that prefer the
  `python -m` invocation style.
- **recommend (test):** degraded-mode banner and JSON `degraded` flag
  per result are now asserted by tests.
- **readme:** new "MCP Setup" section with copy-paste `.mcp.json`
  snippets for Claude Code and Cursor.
- **recommend (cli):** new `--keyword-only` flag skips the embedding
  index build (useful in CI or when the index is intentionally absent).
- **recommend (scoring):** the doc branch was taken for this gap —
  a fuller scoring rework is tracked in
  `docs/superpowers/specs/2026-06-08-taskmaster-recommend-scoring-rework.md`.

82 tests pass in the base environment.
