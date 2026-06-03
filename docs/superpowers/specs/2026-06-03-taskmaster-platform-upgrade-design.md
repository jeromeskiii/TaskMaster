# TaskMaster Platform Upgrade — Agent-Native MCP + Semantic

Date: 2026-06-03
Status: Proposed (supersedes the "no service/server" constraint from `2026-06-02-taskmaster-evolution-design.md` for the new components introduced here)
Builds on: `2026-06-02-taskmaster-evolution-design.md` (the modular `taskmaster/` package and discovery/validation refactor are already in place)

## Goal

Evolve TaskMaster from a CLI-only skill validator into an **agent-native skill platform**. The primary new surface is an **MCP server** that exposes the 269-skill catalog to any Model Context Protocol client (Claude Code, Qwen Code, Cursor, Continuum, custom agents). A **semantic search index** powers retrieval and an **auto-activation recommender** that suggests the right skills for a free-form task. New CLI commands drive the same engines for human use, and a one-command **installer** deploys skills into popular agent runtimes.

The CLI remains fully supported. Existing commands keep their names, flags, and output shapes. The MCP server is a strict superset of the same capabilities, not a replacement.

## Non-Goals

1. No web UI in this wave (explicitly deferred per the prior spec).
2. No multi-tenant cloud deployment. The MCP server is a local stdio process.
3. No mass auto-edit of the corpus. `normalize` and installer write only to the install target, never to the source `SKILL.md` files.
4. No new required frontmatter fields. New fields are optional and backward-compatible.
5. No breaking changes to the existing Python API (`taskmaster.search_skills`, `suggest_skills`, etc.).

## Current State (carried over from prior spec)

- `taskmaster/` package modules exist: `corpus.py`, `discovery.py`, `validation.py`, `cli.py`, `__init__.py`.
- CLI commands: `validate`, `list`, `search`, `suggest`, `stats`, `generate-index`, `check`, `export`, `diff`, `quality`, `hygiene`, `normalize`, `related`.
- Python API exposes `SkillRecord`, `parse_skill`, `get_all_skills`, `search_skills`, `suggest_skills`, `related_skills`, `validate_all`, `score_skill_quality`, `build_hygiene_report`, `build_normalization_report`.
- 269 skills across 20 categories, 79,384 body lines, ~2.5 MB. Risk distribution: 118 safe, 132 medium, 19 high.
- Tests: `tests/test_{corpus,validation,discovery,cli,taskmaster}.py`. CI runs `python3 taskmaster.py validate` and `python3 -m unittest discover`.

## Approach Options Considered

### Option A: Keep CLI-only, add semantic search as an in-process enhancement

Pros: Smallest surface, no new transport, no new dependency tree.
Cons: Other agents (Claude Code, Qwen Code, Continuum) cannot call into TaskMaster at all. The corpus remains hidden behind a CLI. Auto-activation has no protocol for external agents to subscribe to recommendations.

### Option B: Add an MCP server in front of the existing engine (chosen)

Pros: Native consumption from any MCP client. Same engine powers CLI, MCP, and a future web/API layer. Local stdio, no deployment overhead. The `mcp` Python SDK is small and well-maintained.
Cons: New dependency (`mcp`), new failure modes (transport, protocol), new test surface.

### Option C: Build a REST/HTTP API instead of MCP

Pros: Language-agnostic, easy to call from non-MCP agents.
Cons: HTTP server brings deployment, port management, auth, and CORS concerns. The user's agent stack (Claude Code, Qwen Code, Continuum) is MCP-native. HTTP is a poor fit for tool/agent use cases that MCP was designed for.

**Recommended: Option B.** MCP is the right protocol for the stated consumers, and the local stdio model avoids the deployment complexity of HTTP.

## Architecture

```mermaid
flowchart LR
    Agent[MCP Client<br/>Claude Code / Qwen Code / Cursor / Continuum]
    Human[Human via CLI]
    Agent -->|stdio JSON-RPC| Server[TaskMaster MCP Server]
    Human --> CLI[taskmaster.py]
    CLI --> Engine
    Server --> Engine

    subgraph Engine
        Corpus[corpus.py<br/>parsing + cache]
        Embed[embeddings/<br/>provider + FAISS]
        Index[(.taskmaster_cache/<br/>embeddings/{model_hash}/)]
        Rec[recommend.py<br/>hybrid rank]
        Compose[compose.py<br/>dep resolution]
        Install[install.py<br/>target deploys]
    end

    Engine --> Skills[(269 SKILL.md files)]
    Install --> Targets[.claude/skills/<br/>.qwen/skills/<br/>.cursor/skills/]
```

The CLI and the MCP server are thin front-ends over the same engine. Embeddings are an optional, lazy dependency; if `sentence-transformers` is not installed, search and recommendation fall back to keyword-only with a `degraded: true` flag surfaced in both text and JSON output.

## Components

| Component | Module | Responsibility | Deps |
|---|---|---|---|
| **Embedding provider** | `taskmaster/embeddings/__init__.py`, `provider.py` | Pluggable provider interface. Local default (`SentenceTransformerProvider` using `all-MiniLM-L6-v2`). Optional `OpenAIProvider` (text-embedding-3-small). | `sentence-transformers` (extra), `openai` (extra), `numpy` (extra) |
| **Embedding index** | `taskmaster/embeddings/index.py` | FAISS index over skill name + description + tags + body excerpt. Persists to `.taskmaster_cache/embeddings/{model_hash}/index.faiss` + `manifest.json` (sha256 → skill dir). Incremental rebuild on SKILL.md mtime/sha change. | `faiss-cpu` (extra) |
| **Recommender** | `taskmaster/recommend.py` | Hybrid score `0.55·cosine + 0.30·keyword + 0.15·tag_overlap`. Filters by `risk` and `category`. Returns `RankedMatch` with `reasons` (explainable). | uses `embeddings` + `discovery` |
| **Composer** | `taskmaster/compose.py` | Reads optional `depends_on` and `composes_with` frontmatter lists. Resolves the dependency graph into a topologically ordered plan. Detects cycles. Surfaces missing dependencies with closest-match suggestions. | uses `corpus` |
| **Installer** | `taskmaster/install.py` | Symlinks (default) or copies (`--copy`) skill directories into target agent dirs. Supports `--target {claude,qwen,cursor,all}` and `--scope {user,project}`. Writes `.taskmaster-manifest.json` for uninstall. | stdlib only |
| **MCP server** | `taskmaster/mcp/__init__.py`, `server.py` | stdio JSON-RPC server using the `mcp` Python SDK. Exposes the 7 tools listed below. Loads corpus once at startup; lazy-loads the embedding index. | `mcp` (extra) |
| **CLI** | `taskmaster/cli.py` | Adds 5 subcommands: `embed`, `mcp serve`, `recommend`, `compose`, `install`. Preserves all existing commands. | stdlib + existing |
| **Discovery / Validation** | `taskmaster/discovery.py`, `validation.py` | Extended to accept new optional frontmatter fields (`depends_on`, `composes_with`) without rejecting skills that omit them. | stdlib |

## Frontmatter Extensions (Optional, Backward-Compatible)

| Field | Type | Semantics |
|---|---|---|
| `depends_on` | list[string] | Skills that must be loaded before this one. Used by `compose`. |
| `composes_with` | list[string] | Skills commonly used together. Used by `recommend` and `related`. |

Existing skills that omit these fields continue to validate and behave as before. `compose` treats skills with no `depends_on` as roots. `recommend` falls back to description-based similarity when `composes_with` is absent.

## MCP Tools (the public agent surface)

All tools return JSON-serializable dicts. Errors raise `mcp` `ToolError` with a stable `code` and a human-readable `message`.

| Tool | Inputs | Returns |
|---|---|---|
| `search_skills` | `query: string, k: int = 8, category?: string, risk?: "safe"|"medium"|"high"` | `{"results": [{"name", "category", "risk", "score", "reasons", "snippet"}], "degraded": bool}` |
| `get_skill` | `name: string` | `{"name", "frontmatter", "body", "path", "size_bytes", "line_count", "quality"}` or `ToolError(code="not_found")` |
| `list_skills` | `category?: string, risk?: string, limit?: int` | `{"skills": [...], "total": int}` |
| `recommend_skills` | `task_description: string, k: int = 5` | `{"results": [{"name", "score", "rationale", "composes_with"}], "degraded": bool}` |
| `compose_skills` | `names: list[string]` | `{"plan": [{"order", "name", "depends_on"}], "warnings": [...], "errors": [...]}` |
| `check_skill` | `name: string` | `{"issues": [...], "hygiene": {...}, "quality": {...}}` |
| `corpus_stats` | — | `{"totals": {...}, "categories": {...}, "risks": {...}, "index": {...}}` |

`corpus_stats["index"]` reports `{present, model, count, built_at}` so clients can detect a cold vs. warm index.

## Data Flow

### Embedding build (lazy, one-time)

1. `taskmaster embed` (or first call to `search_skills` / `recommend_skills` from CLI or MCP) checks `.taskmaster_cache/embeddings/{model_hash}/`.
2. If missing or `--rebuild`, iterate all skills, concatenate `name + " " + description + " " + tags + " " + first_1000_body_chars`, embed with the active provider, write FAISS index + manifest (sha256 → dir).
3. If present, verify every skill's sha256 is in the manifest. For skills whose content changed, re-embed and incrementally update. For new skills, append. For removed skills, mark stale and rebuild if more than 10% of the index is stale.
4. Cold build on CPU: ~30–90s for 269 skills with `all-MiniLM-L6-v2`. Warm incremental update: <1s per changed skill.

### Search and recommendation

1. Caller invokes `search_skills(query)` (CLI or MCP).
2. Embed the query.
3. FAISS top-2k nearest neighbors.
4. Rerank with keyword overlap (description + tags) and tag overlap.
5. Apply optional category/risk filters.
6. Return top-`k` with `reasons` (e.g., `"cosine 0.82"`, `"tag overlap: postgres, sql"`, `"name term: 'debug'"`).

### Compose

1. Caller invokes `compose_skills(names=[...])`.
2. Build the subgraph of named skills and their `depends_on` closures.
3. Topological sort. Detect cycles → `ToolError(code="cycle", message="a → b → c → a")`.
4. For each `depends_on` not in the input set, return a `warning` with the closest matching skill name (using keyword search) and the option to expand the plan.
5. Return the ordered plan.

### Install

1. Caller invokes `taskmaster install claude --scope project` (or similar).
2. For each skill, create a symlink (or copy with `--copy`) at `<target>/<skill_dir>` pointing to the absolute path of the source skill directory.
3. Write `<target>/.taskmaster-manifest.json` with `{installed_at, source_root, scope, skills: [{name, source_path, link_path}]}`.
4. `taskmaster uninstall <target>` reads the manifest and removes the links. `taskmaster install` on an already-installed target refreshes links and reports the delta.

## Storage Layout

```
.taskmaster_cache/
├── skills_cache.json          # existing, unchanged
└── embeddings/
    └── {model_hash}/          # sha256 of provider name + model name
        ├── index.faiss        # FAISS IndexFlatIP over L2-normalized vectors
        ├── manifest.json      # {skill_dir: {sha256, mtime, embedded_at}}
        └── meta.json          # {provider, model, dim, count, built_at, version}
```

The model-hash subdirectory lets multiple embedding providers coexist (e.g., switching from local to OpenAI keeps the old index around).

## Error Handling

| Condition | Behavior |
|---|---|
| `sentence-transformers` not installed | `embeddings` raises `EmbeddingsUnavailable` with install hint. Search/recommend fall back to keyword-only and set `degraded: true` in CLI JSON and MCP responses. |
| Embedding model download fails (offline) | Same as above. |
| FAISS index corrupt | Log warning, delete index, rebuild on next call. |
| `compose_skills` cycle | `ToolError(code="cycle", message="<path>")`. |
| `compose_skills` missing dep | Returned in `warnings`, not raised. The plan is still returned for the resolvable subset. |
| `install` target dir not writable | `InstallError` with the exact path and the underlying OS error. |
| MCP transport error | Standard MCP `ToolError`. Server logs to stderr (never stdout — that would corrupt the JSON-RPC stream). |
| Skill frontmatter parse error | Existing behavior: surfaced in `validate` and `get_skill` outputs. Not blocking. |

## Testing Strategy

New tests (target: 30+, organized by component):

- `tests/test_embeddings.py` — provider interface, FAISS round-trip (build, save, load, query), incremental update on changed sha, degraded fallback when provider missing.
- `tests/test_recommend.py` — hybrid scoring math, reason generation, category/risk filters, empty query, ties.
- `tests/test_compose.py` — linear chain, diamond, cycle detection, missing dep with closest-match, single skill, empty input.
- `tests/test_install.py` — symlink vs. copy modes, manifest write, idempotent re-install, uninstall, project vs. user scope, target dir creation.
- `tests/test_mcp_server.py` — protocol-level tests using the `mcp` client SDK: `list_tools`, each tool with representative inputs, error paths, `degraded` flag.
- `tests/test_cli_new.py` — `embed`, `mcp serve` (boot smoke), `recommend`, `compose`, `install` argparse paths and output shapes.
- Regression: all existing tests must pass unchanged. New CI step: `pytest tests/test_mcp_server.py -k boot_and_list_tools` to fail fast on protocol breakage.

Coverage goals:
- FAISS index survives a process restart (save/load round-trip).
- `compose` is deterministic for the same input.
- `install` is reversible via `uninstall`.
- MCP `corpus_stats` reports index state correctly cold vs. warm.

## Dependencies

All new runtime dependencies are **optional extras**:

```toml
[project.optional-dependencies]
semantic = ["sentence-transformers>=2.2", "faiss-cpu>=1.7", "numpy>=1.24"]
mcp = ["mcp>=1.0"]
openai = ["openai>=1.0"]
all = ["taskmaster[semantic,mcp,openai]"]
```

Base install remains `pip install taskmaster` with no extra dependencies. The `semantic` and `mcp` extras are required to use the corresponding features. The `openai` extra is only needed if the user opts into the OpenAI embedding provider.

The `pyproject.toml` `[project.scripts]` entry is unchanged. New CLI subcommands work without any extras (they print a helpful "install `taskmaster[semantic]` to enable" message and return non-zero if the relevant extra is missing).

## CI Changes

Add to `.github/workflows/ci.yml`:

1. A `semantic-boot` job: `pip install -e ".[semantic,mcp]"` then `python3 taskmaster.py mcp serve &` with a 10s timeout, sending an `initialize` + `tools/list` request via the `mcp` client SDK, asserting all 7 tools are present, then killing the process.
2. A `compose-and-install-smoke` job: `pytest tests/test_compose.py tests/test_install.py -q`.
3. The existing `validate` and `quality` jobs are unchanged.

Local CI script (`scripts/dev-setup.sh` or new `scripts/test-mcp.sh`) mirrors the same boot check for developer use.

## Migration / Rollout

This is an additive change. No existing CLI command, Python API, or frontmatter field is removed or renamed.

### Phase 1: Engine (semantic + recommend + compose)

- Add `taskmaster/embeddings/`, `taskmaster/recommend.py`, `taskmaster/compose.py`.
- Add `embed`, `recommend`, `compose` CLI subcommands.
- Extend `validation.py` to accept new optional frontmatter fields.
- Tests + CI step for `embed` and `compose`.

### Phase 2: MCP server

- Add `taskmaster/mcp/`.
- Implement 7 tools over the engine.
- Add `mcp serve` CLI subcommand.
- Add `mcp` extra and CI boot check.

### Phase 3: Installer

- Add `taskmaster/install.py`.
- Add `install` and `uninstall` CLI subcommands.
- Tests for symlink/copy, manifest, idempotency.

### Phase 4: Polish

- Add a `docs/superpowers/specs/` follow-up doc if the API surface needs to change.
- Update `README.md` with the new commands, MCP section, and Continuum integration example.
- Tag `v1.1.0` (minor bump — additive, no breaking changes).

Each phase is independently shippable. Phases 1, 2, and 3 can ship in any order; Phase 4 follows.

## Risks

1. **Embedding cold-start cost surprises users.** Mitigation: lazy build on first call, clear progress output in CLI, `--rebuild` is opt-in, model is cached in `~/.cache/huggingface/` after first download.
2. **MCP SDK breaking changes.** Mitigation: pin minimum version, integration test boots the server in CI on every PR, `mcp` is an extra so base install is unaffected.
3. **Symlink portability across OSes.** Mitigation: `--copy` fallback, manifest tracks the link source so a failed symlink is detectable, install smoke test runs on macOS (existing CI is Ubuntu-only, so we add a macOS job for the install tests).
4. **Frontmatter ambiguity with new optional fields.** Mitigation: optional fields default to empty list / empty string. `validation.py` accepts their absence. No existing skill is modified.
5. **Degraded mode silently downgrades quality.** Mitigation: `degraded: true` is set in every response and surfaced in CLI text. README documents the offline-first behavior. Users who want the full experience install the extra.
6. **Installer writes outside the project tree for `--scope user`.** Mitigation: `--scope` is required for any target that writes outside `cwd`; user-scope paths are explicit (`~/.claude/skills/`, etc.) and the manifest records them.

## Success Criteria

1. `pip install taskmaster[semantic,mcp]` followed by `python3 taskmaster.py mcp serve` exposes all 7 tools to any MCP client.
2. `python3 taskmaster.py recommend "debug a postgres deadlock"` returns relevant skills (e.g., `dbos-python`, `error-detective`, `dispatching-parallel-agents`) with explainable reasons.
3. `python3 taskmaster.py compose incident-response postgres-tuning` returns a topologically ordered plan and surfaces any missing `depends_on` warnings.
4. `python3 taskmaster.py install claude --scope project` makes every skill available in Claude Code's `.claude/skills/` via symlink; `uninstall` reverses it.
5. All 221 existing tests pass. 30+ new tests pass. CI `semantic-boot` job passes.
6. README has a new "Agent-Native Usage" section with a working Claude Code and a working Continuum integration snippet.
7. Offline mode works: with no `sentence-transformers` installed, `search`, `recommend`, and the MCP server still function using keyword fallback, and responses carry `degraded: true`.
