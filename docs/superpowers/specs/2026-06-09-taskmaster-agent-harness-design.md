---
title: TaskMaster Agent Harness
date: 2026-06-09
status: approved
---

# TaskMaster Agent Harness

## Purpose

Add a local, LLM-in-the-loop agent to TaskMaster that consumes the existing
skill catalog end-to-end. Given a free-form task, the harness:

1. Uses the existing `recommend` and `compose` engines to pick and order
   relevant skills.
2. Loads the selected `SKILL.md` bodies into a budgeted system prompt.
3. Runs a tool-calling agent loop against a provider-agnostic LLM client
   with a small built-in tool set.
4. Prints a final answer (and, optionally, a structured trace).

The harness is a **consumer** of the existing engines. It does not modify
`recommend`, `compose`, `corpus`, or `validation`.

## Non-goals (v1)

- No autonomous long-running daemon — the agent runs to completion (or
  step cap) and exits.
- No network/HTTP tool, no write/edit tool. v1 is read-only plus
  optional `shell` and `install_skill` (both risk-gated).
- No streaming UI — a single final answer plus a transcript file. v1 is
  CLI-first; richer UX is a follow-up.
- No multi-agent orchestration. One runtime, one provider, one model.
- No persistence between runs. Each `taskmaster run` is independent.

## Architecture

A new package `taskmaster/agent/` with four isolated units:

| Unit | Responsibility | Depends on |
|---|---|---|
| `agent/providers.py` | Abstract `LLMProvider` protocol + `OpenAIProvider`, `AnthropicProvider`, `OllamaProvider`, `EchoProvider`. Returns a uniform `Message` (role, content, tool_calls). | `httpx` (and optional provider SDKs) |
| `agent/tools.py` | Built-in tool implementations (`read_file`, `list_dir`, `shell`, `install_skill`, `retrieve_context`) and the risk-gated dispatcher. | stdlib + existing `taskmaster.install` + `agent.context_compression` |
| `agent/context_compression.py` | Thin wrapper over the vendored `taskmaster.context_budget_manager.ContextBudgetManager` that compresses tool outputs before they reach the LLM and exposes retrieval handles. | `taskmaster.context_budget_manager` (already vendored) |
| `agent/runtime.py` | The agent loop. Owns skill selection, system-prompt construction, tool-call dispatch, step/cost caps, and final-answer emission. | `providers`, `tools`, `context_compression`, existing `recommend`/`compose`/`corpus`/`validation` |
| `agent/cli.py` | `argparse` shim for the `run` subcommand. | `runtime` |

All five units are importable and testable in isolation. The runtime
never reaches into provider internals — it only consumes the protocol.

### Boundaries rationale

- Providers in their own file → adding a new provider is a 30-line,
  one-file change. Test fixtures (`EchoProvider`) live alongside real
  providers so test ergonomics don't leak into production code.
- Tools in their own file → risk gating, audit logging, and tool
  schema definition live in one place; the runtime stays focused on
  loop control.
- Context compression in its own file → the cbm wrapper is the
  single boundary between the harness and the vendored cbm package,
  so a future swap (or upgrade of the vendored copy) touches one
  file. Tools and runtime both depend on this unit, not on cbm
  directly.
- Runtime in their own file → the loop is the most testable unit and
  can be exercised with `EchoProvider` + a fake tool layer, no network
  or LLM needed.

## The agent loop

`runtime.run(task, provider, *, max_steps=12, max_risk="medium",
max_cost_usd=None, transcript_path=None) -> RunResult`:

```
1.  skills = corpus.get_all_skills()
2.  recs   = recommend.recommend_skills(task, skills, k=5, max_risk=max_risk)
3.  plan   = compose.compose_skills([r["skill"]["dir"] for r in recs], skills)
4.  system = build_system_prompt(task, recs, plan)   # budgeted, see below
5.  msgs   = [system, user(task)]
6.  for step in range(max_steps):
        reply = provider.chat(msgs, tools=TOOL_SCHEMAS,
                              temperature=temperature)
        msgs.append(reply)
        append to transcript (if path set)
        if reply has no tool_calls:
            return RunResult(answer=reply.content, steps=step+1, plan=plan,
                             compression_stats=compression.summary())
        for call in reply.tool_calls:
            raw_result = dispatch(call, risk_gate=max_risk)
            compressed = compression.compress_tool_result(call, raw_result)
            msgs.append(tool_result(call.id, compressed.to_model_text()))
            append to transcript (compressed.handle, ratio, bytes)
7.  return RunResult(answer=partial_with_truncation_notice(),
                     steps=max_steps, plan=plan, truncated=True,
                     compression_stats=compression.summary())
```

`compression.compress_tool_result` is a no-op for short results (below
`--compress-threshold-chars`, default 1000) and a real cbm compression
for longer ones. The model always sees a `to_model_text()` string; if
it later needs the exact original it calls the `retrieve_context`
tool with the handle.

### Skill context budget

`build_system_prompt` concatenates the selected skill bodies, capped at
`max_skill_tokens` (default 8000, configurable via `--max-skill-tokens`).
When the total exceeds the budget, the runtime keeps the top-N skills
by recommendation score, prefers skills whose `composes_with` is in the
selected set, and appends a one-line `Skill manifest:` block so the
model knows which skills are loaded and which were dropped.

### Risk gate

`tools.dispatch` consults the existing `RISK_ORDER` constant from
`taskmaster.validation` and the per-tool risk table. A tool call that
exceeds `--max-risk` returns a structured refusal (not an exception):

```json
{"error": "risk_refused", "tool": "shell", "required_risk": "high",
 "max_risk": "medium", "hint": "rerun with --max-risk high"}
```

The model sees this as a normal tool result and can route around it.

### Step and cost caps

- Hard `max_steps` default 12.
- Optional `max_cost_usd` estimated from a small pricing table keyed by
  provider+model. Estimated cost is summed per call from prompt +
  completion tokens. When the estimate exceeds the cap, the loop
  returns `truncated=True` with the last partial answer.

### Determinism

With a fixed provider, `temperature=0` (default), and stubbed tools,
the loop is reproducible. This is what the test suite relies on.

## Provider abstraction

```python
class Message(TypedDict):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: list[ToolCall]      # assistant only
    tool_call_id: str | None        # tool only

class LLMProvider(Protocol):
    name: str
    def chat(self, messages: list[Message], *,
             tools: list[dict] | None = None,
             temperature: float = 0.0,
             max_tokens: int = 1024) -> Message: ...
    def estimate_cost_usd(self, prompt_tokens: int,
                          completion_tokens: int) -> float: ...
```

### Concrete providers

| Provider | Extra | Notes |
|---|---|---|
| `OpenAIProvider` | existing `openai` extra | Translates tool schema to OpenAI format; uses `gpt-4o-mini` by default, override with `--model`. |
| `AnthropicProvider` | new `anthropic` extra | Translates system/user/tool messages to Anthropic format; uses `claude-3-5-haiku-latest` by default. |
| `OllamaProvider` | none (uses `httpx`) | Talks to `OLLAMA_HOST` (default `http://localhost:11434`); uses whatever model is passed via `--model`. |
| `EchoProvider` | none (always available) | Returns scripted replies from a fixture file. Used by tests and for offline dev. |

### Selection

`--provider openai|anthropic|ollama|echo`. If omitted, auto-detect in
order: `ANTHROPIC_API_KEY` → `OPENAI_API_KEY` → `OLLAMA_HOST` → error
with a clear message.

The CLI never imports a provider SDK unless that provider is requested.

## Built-in tools

| Tool | Risk | Args | Returns |
|---|---|---|---|
| `read_file` | safe | `path: str, max_bytes: int = 20000` | `{path, content, truncated, bytes_read}` |
| `list_dir` | safe | `path: str, glob: str \| None = None` | `{path, entries: [{name, is_dir, size}]}` |
| `shell` | high | `cmd: str, timeout: int = 10` | `{cmd, exit_code, stdout, stderr, duration_s}`; uses `subprocess.run` with `shell=False` (argv list) and `cwd=pwd`. |
| `install_skill` | medium | `name: str` | delegates to `taskmaster.install`; returns `{name, status, path}`. |
| `retrieve_context` | safe | `handle: str, max_chars: int \| None = None` | `{handle, content, truncated}`; delegates to `ContextBudgetManager.retrieve`. |

All tool results are JSON-encoded strings (matching the OpenAI/Anthropic
tool-result convention). When `transcript_path` is set, every
`shell`/`install_skill` call is appended to `transcript.jsonl` with
`{ts, tool, args, result, cost_so_far}`.

The tool dispatcher is the only place that enforces risk gating. The
runtime is intentionally ignorant of risk levels.

## Context compression

`agent/context_compression.py` is a thin wrapper around the already-
vendored `taskmaster.context_budget_manager.ContextBudgetManager`. It
exists so the harness has a single, testable boundary against cbm —
upgrading or swapping the vendored copy later touches one file.

### Public surface

```python
@dataclass
class CompressionSummary:
    total_tool_results: int
    compressed: int            # how many went through cbm
    bypassed: int              # below threshold, no compression
    original_tokens: int
    compressed_tokens: int
    saved_tokens: int

class ContextCompression:
    def __init__(self, *, db_path: Path | None = None,
                 threshold_chars: int = 1000,
                 max_chars: int = 4000) -> None: ...

    def compress_tool_result(self, call: ToolCall, raw_text: str) -> CompressedResult: ...
    def retrieve(self, handle: str) -> str: ...
    def summary(self) -> CompressionSummary: ...
```

### Behavior

- `compress_tool_result` is a no-op for tool results shorter than
  `threshold_chars` — the raw text is passed through, and a
  `CompressionSummary` counter is incremented under `bypassed`.
- For longer results, it calls
  `ContextBudgetManager.compress(raw_text, source_name=call.name)`.
  The returned `CompressionResult.compressed_text` (which already
  includes the cbm header with the handle) is what the model sees.
  The original is stored in cbm's SQLite DB and retrievable later
  via the `retrieve_context` tool.
- The `CompressThreshold` is a per-call opt-in: a tool may force
  compression by returning `{"_force_compress": true}` from its
  handler. v1 always respects the threshold; per-tool opt-in is a
  follow-up.

### Why compress tool results (not the whole context)

The model context already consists of small, well-formed messages
(system, user, assistant, tool-result strings). The expensive part
is when a tool returns a 200KB JSON dump, a 50KB log, or a 30KB file.
Compressing only tool results (and only when they're large) is the
highest-leverage, lowest-risk application of cbm. The skill-selection
budget on the system prompt side stays deterministic and is handled
by `runtime.build_system_prompt` as before.

## CLI surface

```bash
# Basic
taskmaster run "explain the postgres deadlock in this repo"

# Provider + safety
taskmaster run "design a multi-tenant API" \
  --provider openai --max-steps 12 --max-risk medium

# Anthropic
taskmaster run "review the diff for security issues" \
  --provider anthropic --model claude-3-5-sonnet-latest

# Local model
taskmaster run "what does this file do?" \
  --provider ollama --model llama3.1 --max-risk safe

# Structured output + trace
taskmaster run "summarize the test failures" \
  --provider openai --json --transcript .run.jsonl
```

### Flags

| Flag | Default | Notes |
|---|---|---|
| `--provider` | auto-detect | `openai`, `anthropic`, `ollama`, `echo` |
| `--model` | provider default | free-form; provider validates |
| `--max-steps` | 12 | hard cap on loop iterations |
| `--max-risk` | `medium` | `safe`, `medium`, `high` |
| `--max-skill-tokens` | 8000 | system-prompt budget for skill bodies |
| `--max-cost-usd` | none | soft cap; loop exits with truncation when exceeded |
| `--compress-threshold-chars` | 1000 | tool results shorter than this are sent to the model as-is |
| `--compress-max-chars` | 4000 | target size for cbm compression |
| `--cbm-db` | `<CACHE_DIR>/context.db` | path to cbm's SQLite store |
| `--no-compress` | false | disable cbm entirely (all tool results pass through) |
| `--temperature` | 0.0 | passed through to provider |
| `--transcript` | none | path to append a JSONL trace |
| `--json` | false | emit `RunResult` as JSON, not prose |
| `--verbose` | false | print each step's tool calls and short results |

`RunResult` shape:

```python
{
  "answer": str,
  "steps": int,
  "max_steps": int,
  "truncated": bool,
  "plan": {"steps": [...], "warnings": [...]},
  "skills_loaded": [str, ...],
  "skills_dropped": [str, ...],
  "estimated_cost_usd": float | None,
  "provider": str,
  "model": str,
  "compression": {
    "total_tool_results": int,
    "compressed": int,
    "bypassed": int,
    "original_tokens": int,
    "compressed_tokens": int,
    "saved_tokens": int,
  } | None,
}
```

## Dependencies & packaging

New optional extras in `pyproject.toml`:

```toml
anthropic = ["anthropic>=0.30"]   # new
agent = ["httpx>=0.27"]            # new; required for Ollama + provider-agnostic bits
all = ["taskmaster[semantic,mcp,openai,anthropic,agent]"]  # extend
```

The base install does not pull in any LLM SDK. `pip install
taskmaster[agent]` adds `httpx`; `pip install taskmaster[anthropic]`
adds the Anthropic SDK. Providers that are not installed raise a clear
error at CLI dispatch time ("install with `pip install
taskmaster[anthropic]`").

`taskmaster.context_budget_manager` is already vendored under the
`taskmaster` package (no new install step required for compression to
work). The `[agent]` extra only adds `httpx` for the Ollama provider
and for cbm's own (optional) HTTP probes; cbm itself runs locally on
SQLite and has no external dependencies.

## Testing strategy

All tests live in `tests/agent/`. TDD per project conventions:
write the failing test first, then the implementation.

1. **`test_providers.py`** — protocol conformance for all 4 providers.
   - `EchoProvider` round-trip.
   - `OpenAIProvider`/`AnthropicProvider` cassette test (skipped
     without API key; gated by env var).
   - `OllamaProvider` HTTP test against a `respx` mock.
   - `estimate_cost_usd` numeric table test.

2. **`test_runtime.py`** — drives the loop with `EchoProvider` + a
   fake tool layer.
   - Step cap triggers `truncated=True`.
   - Risk refusal returns a structured tool result the model can see.
   - Skill context budget drops the lowest-scored skill first.
   - Final answer extraction when the model emits no tool calls.
   - Transcript JSONL is well-formed when `--transcript` is set.
   - Compression is applied to long tool results and the model sees
     the cbm handle; short results pass through unchanged.
   - `retrieve_context` tool call resolves the handle and returns the
     original text.

3. **`test_tools.py`** — unit tests for each built-in tool.
   - `read_file` truncation, missing file.
   - `list_dir` glob filter.
   - `shell` timeout, non-zero exit, refused commands (deny list:
     command starts with `rm -rf /`, `sudo `, `mkfs`, `dd if=`,
     `shutdown`, `reboot`, `halt`, or contains `> /dev/`; case- and
     whitespace-normalized).
   - `install_skill` delegates to `taskmaster.install`.
   - `retrieve_context` returns the cbm-stored original; unknown
     handle returns a structured error.

4. **`test_context_compression.py`** — unit tests for the cbm wrapper.
   - Short result below `threshold_chars` → no cbm call, `bypassed`
     counter increments.
   - Long result above threshold → cbm called once, original stored,
     `compressed_tokens < original_tokens` for the JSON fixture.
   - `summary()` rolls up the counters correctly across multiple
     calls.
   - `--no-compress` makes `compress_tool_result` a pure passthrough
     and `summary()` returns `None`.

5. **`test_cli.py`** — `argparse` smoke + `--json` output shape +
   provider auto-detect.

6. **Integration** — one end-to-end test gated by `RUN_AGENT_E2E=1`
   that runs the real loop against `EchoProvider` with a tiny skill
   fixture in `tests/fixtures/skills/`. CI does not run this; it's a
   manual/local check.

Coverage target: ≥ 90% for the new package.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| LLM providers change SDK shapes | Each provider has a single translation shim; tests use recorded cassettes, not live calls, so SDK drift is caught locally. |
| Tool-call loops (model keeps calling the same tool) | Step cap + tool-call deduplication (consecutive identical calls are short-circuited with a "this didn't help" message). |
| Skill context overflow | Budget cap with deterministic drop order; `skills_dropped` is reported in `RunResult` so the user can adjust `--max-skill-tokens`. |
| Shell-injection via `shell` tool | `shell=False` with argv list, deny list for obviously destructive commands, 10s default timeout, optional `--max-risk high` only. |
| Cost runaway | `max_cost_usd` cap (soft) + `max_steps` (hard). Cost is estimated, not exact — over by < 5% for known models. |

## Open questions (to revisit after v1)

- Streaming output (`--stream` flag) — deferred.
- Persistent session/state across `run` invocations — deferred.
- Sub-agent delegation (one agent spawning another) — deferred; the
  `compose` engine already gives us static plans, runtime delegation is
  the next step.
- A web UI on top of the same runtime — natural follow-up.
