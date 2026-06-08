# TaskMaster Minimal Setup Design

## Goal

Establish a clean, minimal local development environment for TaskMaster that supports the core package, CLI entry points, and representative test execution without installing optional semantic, MCP, or OpenAI extras.

## Scope

This setup includes:

- A fresh repo-local virtual environment at `.venv`
- Base dependency installation from `pyproject.toml`
- Editable install of the package for local development
- Verification of Python, package importability, CLI availability, and a targeted test run

This setup excludes:

- Optional extras from `taskmaster[semantic]`, `taskmaster[mcp]`, `taskmaster[openai]`, or `taskmaster[all]`
- Embedding index generation
- MCP server startup
- OpenAI-backed or sentence-transformer-backed workflows

## Recommended Approach

Recreate `.venv` from scratch inside the repository, install the base package in editable mode, and verify the baseline with a lightweight test slice plus a CLI check.

This is preferred over reusing the existing `.venv` because the repository already contains prior local state, and a fresh environment gives a more reliable minimal baseline.

## Environment Design

### Python environment

- Use the system `python3` available on the machine
- Create a new virtual environment at `/Users/ohmskiii/Documents/Builds/TaskMaster/.venv`
- Activate that environment for package installation and verification commands

### Dependency profile

- Install only the base package in editable mode with `pip install -e .`
- Do not install optional extras

The resulting environment should include the package’s declared base dependency set, currently `pyyaml>=6.0`, plus packaging tooling resolved by `pip`.

## Verification Strategy

Verification should prove that the minimal environment is usable without paying the cost of optional integrations.

Run:

1. A Python version check inside the virtual environment
2. An editable install of the base package
3. A targeted pytest invocation against stable core tests
4. A CLI sanity check such as `python3 taskmaster.py --help`

## Test Selection

Prefer core tests that do not depend on optional extras or external services. Start with:

- `tests/test_validation.py`
- `tests/test_corpus.py`

If either test file reveals an unexpected dependency on extras, stop and document the actual failure before broadening scope.

## Failure Handling

- If virtual environment creation fails, capture the interpreter error and stop
- If installation fails because of network or package resolution restrictions, request the minimum approval needed to install dependencies
- If targeted tests fail, do not treat setup as complete; report the exact failure and whether it is environmental or a project regression
- If the CLI sanity check fails after installation, treat that as an incomplete setup and investigate the entry-point or import issue

## Success Criteria

The setup is complete when all of the following are true:

- `.venv` exists and is newly created
- `pip install -e .` succeeds inside `.venv`
- The selected core tests pass inside `.venv`
- A basic CLI command executes successfully from the repository root
