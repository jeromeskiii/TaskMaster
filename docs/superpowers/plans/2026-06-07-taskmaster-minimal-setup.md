# TaskMaster Minimal Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a clean repo-local Python environment for TaskMaster, install the base package in editable mode, and verify that core tests and CLI commands run without optional extras.

**Architecture:** The setup work is operational rather than application-code changes. The environment will be isolated in `.venv`, installation will use the package metadata already defined in `pyproject.toml`, and verification will rely on existing core tests plus a CLI sanity check from the repository root.

**Tech Stack:** Python 3, `venv`, `pip`, `pytest`, TaskMaster package metadata in `pyproject.toml`

---

## File Structure

- Existing: `/Users/ohmskiii/Documents/Builds/TaskMaster/pyproject.toml`
  Responsibility: Declares base package metadata and dependencies for editable installation.
- Existing: `/Users/ohmskiii/Documents/Builds/TaskMaster/taskmaster.py`
  Responsibility: Script shim for CLI invocation from the repository root.
- Existing: `/Users/ohmskiii/Documents/Builds/TaskMaster/tests/test_validation.py`
  Responsibility: Core validation behavior checks that do not require optional extras.
- Existing: `/Users/ohmskiii/Documents/Builds/TaskMaster/tests/test_corpus.py`
  Responsibility: Core corpus parsing and integration checks for the base package.
- Create/replace at execution time: `/Users/ohmskiii/Documents/Builds/TaskMaster/.venv`
  Responsibility: Local isolated Python environment for this repository.

### Task 1: Capture the pre-setup baseline

**Files:**
- Read: `/Users/ohmskiii/Documents/Builds/TaskMaster/pyproject.toml`
- Read: `/Users/ohmskiii/Documents/Builds/TaskMaster/tests/test_validation.py`
- Read: `/Users/ohmskiii/Documents/Builds/TaskMaster/tests/test_corpus.py`

- [ ] **Step 1: Confirm the interpreter and repository root**

Run:

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster
pwd
python3 --version
```

Expected:

```text
/Users/ohmskiii/Documents/Builds/TaskMaster
Python 3.10+...
```

- [ ] **Step 2: Record whether a local virtual environment already exists**

Run:

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster
ls -ld .venv
```

Expected:

```text
.venv
```

or:

```text
ls: .venv: No such file or directory
```

- [ ] **Step 3: Confirm the targeted verification tests exist**

Run:

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster
python3 - <<'PY'
from pathlib import Path
for path in ["tests/test_validation.py", "tests/test_corpus.py"]:
    print(path, Path(path).exists())
PY
```

Expected:

```text
tests/test_validation.py True
tests/test_corpus.py True
```

### Task 2: Recreate the repo-local virtual environment

**Files:**
- Replace at execution time: `/Users/ohmskiii/Documents/Builds/TaskMaster/.venv`

- [ ] **Step 1: Remove the existing `.venv` if present**

Run:

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster
rm -rf .venv
```

Expected:

```text
```

- [ ] **Step 2: Create a fresh virtual environment**

Run:

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster
python3 -m venv .venv
```

Expected:

```text
```

- [ ] **Step 3: Verify the new environment uses the local interpreter**

Run:

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster
.venv/bin/python --version
.venv/bin/python -c "import sys; print(sys.prefix)"
```

Expected:

```text
Python 3.10+...
/Users/ohmskiii/Documents/Builds/TaskMaster/.venv
```

### Task 3: Install the base package in editable mode

**Files:**
- Read: `/Users/ohmskiii/Documents/Builds/TaskMaster/pyproject.toml`
- Populate environment: `/Users/ohmskiii/Documents/Builds/TaskMaster/.venv`

- [ ] **Step 1: Upgrade packaging tooling inside `.venv`**

Run:

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster
.venv/bin/python -m pip install --upgrade pip setuptools wheel
```

Expected:

```text
Successfully installed ...
```

- [ ] **Step 2: Install the base package without extras**

Run:

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster
.venv/bin/python -m pip install -e .
```

Expected:

```text
Successfully installed taskmaster-1.1.0 ...
```

- [ ] **Step 3: Verify the package imports from the editable install**

Run:

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster
.venv/bin/python - <<'PY'
import taskmaster
print(taskmaster.__file__)
print(taskmaster.SKILLS_DIR)
PY
```

Expected:

```text
/Users/ohmskiii/Documents/Builds/TaskMaster/taskmaster/__init__.py
/Users/ohmskiii/Documents/Builds/TaskMaster
```

### Task 4: Verify core tests in the minimal environment

**Files:**
- Test: `/Users/ohmskiii/Documents/Builds/TaskMaster/tests/test_validation.py`
- Test: `/Users/ohmskiii/Documents/Builds/TaskMaster/tests/test_corpus.py`

- [ ] **Step 1: Run the validation test module**

Run:

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster
.venv/bin/python -m pytest tests/test_validation.py -v
```

Expected:

```text
... passed
```

- [ ] **Step 2: Run the corpus test module**

Run:

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster
.venv/bin/python -m pytest tests/test_corpus.py -v
```

Expected:

```text
... passed
```

- [ ] **Step 3: Stop and classify any failure before proceeding**

Run:

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster
echo "If a test failed, capture whether it is a dependency/setup issue or a project regression before continuing."
```

Expected:

```text
If a test failed, capture whether it is a dependency/setup issue or a project regression before continuing.
```

### Task 5: Verify the CLI entrypoints

**Files:**
- Read/execute: `/Users/ohmskiii/Documents/Builds/TaskMaster/taskmaster.py`
- Read/execute: `/Users/ohmskiii/Documents/Builds/TaskMaster/taskmaster/__init__.py`

- [ ] **Step 1: Run the script shim help output**

Run:

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster
.venv/bin/python taskmaster.py --help
```

Expected:

```text
usage: ...
```

- [ ] **Step 2: Run the installed console script help output**

Run:

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster
.venv/bin/taskmaster --help
```

Expected:

```text
usage: ...
```

- [ ] **Step 3: Run a lightweight core CLI command**

Run:

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster
.venv/bin/python taskmaster.py stats
```

Expected:

```text
Category Distribution
```

### Task 6: Record the result and keep environment changes isolated

**Files:**
- No source file modifications expected

- [ ] **Step 1: Capture the final setup state**

Run:

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster
git status --short
```

Expected:

```text
```

or existing unrelated worktree changes, but no new source-code edits caused by setup beyond local environment artifacts ignored by git.

- [ ] **Step 2: Summarize exact outcomes**

Run:

```bash
cd /Users/ohmskiii/Documents/Builds/TaskMaster
echo "Report: venv created, base package installed, targeted tests status, CLI sanity status."
```

Expected:

```text
Report: venv created, base package installed, targeted tests status, CLI sanity status.
```
