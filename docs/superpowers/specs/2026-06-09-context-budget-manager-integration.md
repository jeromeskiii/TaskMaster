# Spec: Context Budget Manager Integration in TaskMaster

> **Status**: `FINALIZED`
> **Date**: 2026-06-09
> **Author**: Antigravity

## Vision
Integrate the Context Budget Manager into TaskMaster as a vendored subsystem. This allows TaskMaster to serve as a unified skill operations layer that can also manage local context compression and history logging for AI agents.

## Goals
1. Vendor `context-budget-manager` source files under `taskmaster/context_budget_manager/` (excluding its CLI entrypoint).
2. Configure the database default path to resolve to `.taskmaster_cache/context.db` to keep all local caches unified.
3. Expose the context manager commands natively under `taskmaster context` CLI.
4. Integrate unit tests into TaskMaster's test runner and update all imports to `taskmaster.context_budget_manager`.

## Non-Goals
* No external packaging of `context-budget-manager` as a pyproject dependency for TaskMaster.
* No changes to the original standalone `context-budget-manager` repository files.

## Architecture

```
taskmaster/
  ├── __init__.py
  ├── cli.py
  ├── ...
  └── context_budget_manager/           <-- Vendored Subsystem
        ├── __init__.py
        ├── core.py
        ├── store.py
        ├── compressors.py
        ├── detectors.py
        ├── tokens.py
        └── models.py
```

### Component Adjustments
* **`taskmaster/context_budget_manager/core.py`:**
  - Update default `db_path` in `ContextBudgetManager.__init__` to `taskmaster.CACHE_DIR / "context.db"`.
  - Import sibling modules relatively or via `taskmaster.context_budget_manager`.
* **`taskmaster/cli.py`:**
  - Add `context` subparsers for `compress`, `retrieve`, `stats`, and `prune`.
  - Instantiate `ContextBudgetManager` pointing to `taskmaster.CACHE_DIR / "context.db"`.

## Testing Strategy
* Copy `tests/test_core.py` to `tests/test_context_core.py`.
* Copy `tests/test_store.py` to `tests/test_context_store.py`.
* Update import paths inside the test files to `taskmaster.context_budget_manager`.
* Run the pytest suite to ensure all tests pass.
