# Context Budget Manager Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the Context Budget Manager as a vendored subpackage of TaskMaster, with full CLI exposure and testing.

**Architecture:** Copy the standalone `context_budget_manager` modules into `taskmaster/context_budget_manager/`, override default SQLite database location to `.taskmaster_cache/context.db`, expose subparsers in `taskmaster/cli.py`, and port existing tests.

**Tech Stack:** Python 3.10+, SQLite, pytest.

---

### Task 1: Create subpackage structure and copy vendored modules

**Files:**
- Create:
  - `taskmaster/context_budget_manager/__init__.py`
  - `taskmaster/context_budget_manager/core.py`
  - `taskmaster/context_budget_manager/store.py`
  - `taskmaster/context_budget_manager/compressors.py`
  - `taskmaster/context_budget_manager/detectors.py`
  - `taskmaster/context_budget_manager/tokens.py`
  - `taskmaster/context_budget_manager/models.py`
- Test: `tests/test_context_imports.py`

- [ ] **Step 1: Write the failing test**
  Write a test trying to import the new modules.
  Create `tests/test_context_imports.py`:
  ```python
  def test_context_budget_manager_imports():
      from taskmaster.context_budget_manager.core import ContextBudgetManager
      from taskmaster.context_budget_manager.models import ContentType
      assert ContextBudgetManager is not None
      assert ContentType is not None
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `.venv/bin/pytest tests/test_context_imports.py -v`
  Expected: FAIL with `ModuleNotFoundError: No module named 'taskmaster.context_budget_manager'`

- [ ] **Step 3: Copy context budget manager source modules**
  Create the folder and copy the files from the standalone project (excluding cli.py):
  Run:
  ```bash
  mkdir -p taskmaster/context_budget_manager
  cp /Users/ohmskiii/Documents/Builds/context-budget-manager/src/context_budget_manager/__init__.py taskmaster/context_budget_manager/
  cp /Users/ohmskiii/Documents/Builds/context-budget-manager/src/context_budget_manager/core.py taskmaster/context_budget_manager/
  cp /Users/ohmskiii/Documents/Builds/context-budget-manager/src/context_budget_manager/store.py taskmaster/context_budget_manager/
  cp /Users/ohmskiii/Documents/Builds/context-budget-manager/src/context_budget_manager/compressors.py taskmaster/context_budget_manager/
  cp /Users/ohmskiii/Documents/Builds/context-budget-manager/src/context_budget_manager/detectors.py taskmaster/context_budget_manager/
  cp /Users/ohmskiii/Documents/Builds/context-budget-manager/src/context_budget_manager/tokens.py taskmaster/context_budget_manager/
  cp /Users/ohmskiii/Documents/Builds/context-budget-manager/src/context_budget_manager/models.py taskmaster/context_budget_manager/
  ```

- [ ] **Step 4: Run test to verify it passes**
  Run: `.venv/bin/pytest tests/test_context_imports.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  Run:
  ```bash
  git add taskmaster/context_budget_manager/ tests/test_context_imports.py
  git commit -m "feat: vendor context_budget_manager subpackage"
  ```

---

### Task 2: Configure default database path in core.py

**Files:**
- Modify: `taskmaster/context_budget_manager/core.py`
- Test: `tests/test_context_path.py`

- [ ] **Step 1: Write the failing test**
  Write a test verifying the default database resolves to `.taskmaster_cache/context.db`.
  Create `tests/test_context_path.py`:
  ```python
  from taskmaster.context_budget_manager.core import ContextBudgetManager
  from taskmaster import CACHE_DIR
  
  def test_default_database_resolves_to_taskmaster_cache():
      manager = ContextBudgetManager()
      assert manager.store.db_path == CACHE_DIR / "context.db"
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `.venv/bin/pytest tests/test_context_path.py -v`
  Expected: FAIL (resolves to `.cbm/context.db` instead of `.taskmaster_cache/context.db`)

- [ ] **Step 3: Modify core.py default path**
  Modify [taskmaster/context_budget_manager/core.py](file:///Users/ohmskiii/Documents/Builds/TaskMaster/taskmaster/context_budget_manager/core.py) to import `CACHE_DIR` and set it as the default `db_path`:
  Replace lines 15-17 in `core.py`:
  ```python
      def __init__(self, db_path: str | Path | None = None, default_max_chars: int = 4_000) -> None:
          from taskmaster import CACHE_DIR
          self.store = OriginalStore(db_path or (CACHE_DIR / "context.db"))
          self.default_max_chars = default_max_chars
  ```

- [ ] **Step 4: Run test to verify it passes**
  Run: `.venv/bin/pytest tests/test_context_path.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  Run:
  ```bash
  git add taskmaster/context_budget_manager/core.py tests/test_context_path.py
  git commit -m "chore: default context db path to .taskmaster_cache"
  ```

---

### Task 3: Integrate context commands in taskmaster/cli.py

**Files:**
- Modify: `taskmaster/cli.py`
- Test: `tests/test_context_cli.py`

- [ ] **Step 1: Write the failing test**
  Write a test verifying the CLI correctly routes subcommands and fails on unknown inputs.
  Create `tests/test_context_cli.py`:
  ```python
  import contextlib
  import io
  from taskmaster import cli
  
  def test_context_cli_subparsers():
      parser = cli.build_parser()
      # Parse "context stats" args and verify they map correctly
      args = parser.parse_args(["context", "stats"])
      assert args.command == "context"
      assert args.context_command == "stats"
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `.venv/bin/pytest tests/test_context_cli.py -v`
  Expected: FAIL with `SystemExit: 2` (invalid choice 'context')

- [ ] **Step 3: Modify cli.py to add context parser and dispatch**
  Add subparsers inside `build_parser()` in `taskmaster/cli.py`:
  ```python
      # Add context subparsers
      context_p = sub.add_parser("context", help="Manage local context budget and storage")
      context_sub = context_p.add_subparsers(dest="context_command", required=True)
  
      compress_p = context_sub.add_parser("compress", help="Compress context from stdin or file")
      compress_p.add_argument("file", nargs="?", help="File to compress (reads stdin if omitted)")
      compress_p.add_argument("--max-chars", type=int, default=4000)
  
      retrieve_p = context_sub.add_parser("retrieve", help="Retrieve original context by handle")
      retrieve_p.add_argument("handle")
  
      context_sub.add_parser("stats", help="Show context store stats")
  
      prune_p = context_sub.add_parser("prune", help="Prune old context records")
      prune_p.add_argument("--max-age-days", type=float, default=7.0)
  ```
  Add dispatch helper `_cmd_context(args)` and bind the command parser:
  ```python
  def _cmd_context(args) -> int:
      import sys
      from pathlib import Path
      from taskmaster.context_budget_manager.core import ContextBudgetManager
      
      manager = ContextBudgetManager()
      try:
          if args.context_command == "compress":
              if args.file:
                  path = Path(args.file)
                  text = path.read_text(encoding="utf-8")
                  result = manager.compress(text, source_name=str(path), max_chars=args.max_chars)
              else:
                  text = sys.stdin.read()
                  result = manager.compress(text, max_chars=args.max_chars)
  
              print(result.compressed_text)
              print("\n---")
              print(f"handle={result.handle}")
              print(f"type={result.content_type.value}")
              print(f"tokens={result.original_tokens}->{result.compressed_tokens}")
              print(f"saved={result.saved_tokens}")
              print(f"ratio={result.compression_ratio:.2f}")
              return 0
  
          if args.context_command == "retrieve":
              print(manager.retrieve(args.handle))
              return 0
  
          if args.context_command == "stats":
              print(manager.stats())
              return 0
  
          if args.context_command == "prune":
              deleted = manager.prune(args.max_age_days * 86400.0)
              print(f"Successfully pruned {deleted} context payload(s).")
              return 0
      except Exception as exc:
          print(f"cbm error: {exc}", file=sys.stderr)
          return 1
      return 0
  ```
  Bind parser dispatch logic in `cli.py` `main()`:
  ```python
      # inside main():
      # map command to function
      # if args.command == "context": return _cmd_context(args)
  ```

- [ ] **Step 4: Run test to verify it passes**
  Run: `.venv/bin/pytest tests/test_context_cli.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  Run:
  ```bash
  git add taskmaster/cli.py tests/test_context_cli.py
  git commit -m "feat: add context command to cli.py"
  ```

---

### Task 4: Port Context Manager unit tests to TaskMaster

**Files:**
- Create:
  - `tests/test_context_core.py`
  - `tests/test_context_store.py`

- [ ] **Step 1: Copy test files**
  Copy tests from standalone project to TaskMaster tests directory:
  Run:
  ```bash
  cp /Users/ohmskiii/Documents/Builds/context-budget-manager/tests/test_core.py tests/test_context_core.py
  cp /Users/ohmskiii/Documents/Builds/context-budget-manager/tests/test_store.py tests/test_context_store.py
  ```

- [ ] **Step 2: Update imports**
  Modify [tests/test_context_core.py](file:///Users/ohmskiii/Documents/Builds/TaskMaster/tests/test_context_core.py) and [tests/test_context_store.py](file:///Users/ohmskiii/Documents/Builds/TaskMaster/tests/test_context_store.py):
  Replace:
  `from context_budget_manager import ...`
  With:
  `from taskmaster.context_budget_manager import ...`
  And inside `test_context_store.py`, replace:
  `from context_budget_manager.store import OriginalStore`
  With:
  `from taskmaster.context_budget_manager.store import OriginalStore`

- [ ] **Step 3: Run pytest to verify all tests pass**
  Run: `.venv/bin/pytest tests/ -v`
  Expected: PASS (105 original tests + new context manager tests)

- [ ] **Step 4: Clean up temporary test files**
  Remove `tests/test_context_imports.py` and `tests/test_context_path.py` (since their logic is fully covered by the ported tests):
  Run:
  ```bash
  git rm tests/test_context_imports.py tests/test_context_path.py
  ```

- [ ] **Step 5: Final Commit**
  Run:
  ```bash
  git add tests/test_context_core.py tests/test_context_store.py
  git commit -m "test: port context budget manager unit tests"
  ```
