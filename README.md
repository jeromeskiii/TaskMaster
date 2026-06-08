# TaskMaster — 269 Curated AI Agent Skills

**A production-ready catalog of 269 agent skills for AI coding assistants.** Each skill is a self-contained markdown file with YAML frontmatter containing activation rules, procedures, patterns, and domain knowledge. Designed for Claude Code, Qwen Code, and other AI agent platforms.

## Quick Start

```bash
# Validate all 269 skills
python3 taskmaster.py validate

# Search for skills
python3 taskmaster.py search postgres
python3 taskmaster.py search "code review"

# List all skills by category
python3 taskmaster.py list --category security
python3 taskmaster.py list --risk high

# Show stats and distributions
python3 taskmaster.py stats

# Deep-check a specific skill
python3 taskmaster.py check bug-hunter

# Regenerate the index
python3 taskmaster.py generate-index

# Suggest skills for a task
python3 taskmaster.py suggest "debug production issue"

# Score all skills by quality
python3 taskmaster.py quality

# Export skills as JSON
python3 taskmaster.py export --json > skills.json
```

## Python API

Validation, quality scoring, and corpus hygiene analysis now live in `taskmaster.validation`.

```python
from taskmaster.corpus import get_all_skills
from taskmaster.validation import (
    build_hygiene_report,
    build_normalization_report,
    score_skill_quality,
    validate_all,
)

skills = get_all_skills()
validation = validate_all(skills)
hygiene = build_hygiene_report(skills)
normalization = build_normalization_report(skills)
quality = score_skill_quality(skills[0])
```

`build_hygiene_report()` surfaces duplicate names, near-duplicate descriptions, tag-shape inconsistencies, parse-error rollups, and category/risk anomaly counts. `build_normalization_report()` proposes canonical metadata cleanups such as converting scalar tag strings into normalized tag lists.

## MCP Setup

Expose TaskMaster as an MCP server so Claude Code, Cursor, and other MCP clients can call its tools directly. Requires the `mcp` extra.

### Install

```bash
pip install "taskmaster[mcp]"
```

### Verify the server starts

```bash
python3 -m taskmaster.mcp serve
```

(The server blocks on stdio. Press Ctrl-C to stop. To test end-to-end, wire it into a client — see below.)

### Claude Code

Add a `.mcp.json` at your project root (or `~/.claude/mcp.json` for user scope):

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

Restart Claude Code. The TaskMaster tools (`validate_all`, `search_skills`, `list_skills`, `list_categories`, `get_skill`, `suggest`, `recommend_skills`, `compose_skills`, `check_skill`, `validate_skill`, `corpus_stats`, `install_skill`) should appear in the tool picker.

### Cursor

Add to `~/.cursor/mcp.json`:

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

Restart Cursor. The same 12 tools become available.

## Structure

Each skill lives in its own directory:

```
task-intelligence/
└── SKILL.md   # YAML frontmatter + markdown body
```

### Frontmatter Fields

| Field | Required | Values |
|-------|----------|--------|
| `name` | ✓ | Kebab-case identifier |
| `description` | ✓ | 30+ word description of when to use |
| `category` | ✓ | 20 predefined categories |
| `risk` | ✓ | `safe`, `medium`, `high` |
| `source` | — | Origin (community, GitHub, etc.) |
| `date_added` | — | ISO date |
| `tags` | — | Keywords for search |

### Categories

| Category | Count |
|----------|-------|
| development | 176 |
| ai | 33 |
| cloud | 16 |
| security | 12 |
| frontend | 5 |
| mcp | 5 |
| backend | 3 |
| networking | 3 |
| automation, data-ai, framework, media | 2 each |
| agent-behavior, ai-agents, ai-research, browser-automation, data, memory, meta, voice-agents | 1 each |

### Risk Levels

- 🟢 **safe** (118) — Read-only, no destructive operations
- 🟡 **medium** (132) — Code modifications, network calls
- 🔴 **high** (19) — Git operations, shell execution, infrastructure changes

## Total Stats

- **269 skills** across 20 categories
- **79,384 lines** of body content
- **~2.5 MB** total (averaging 9.4 KB per skill)

## Adding a Skill

```bash
# Create the directory
mkdir my-new-skill

# Write SKILL.md with required frontmatter
cat > my-new-skill/SKILL.md << 'EOF'
---
name: my-new-skill
description: A clear 30+ character description of when and why to use this skill
category: development
risk: safe
---

# My New Skill

## When to Use
...
EOF

# Validate
python3 taskmaster.py check my-new-skill

# Regenerate index
python3 taskmaster.py generate-index
```

## Agent-Native Skill OS

TaskMaster is an agent-native Skill OS that helps AI agents discover, load, compose, and execute the right skills for a task. It provides a local intelligence layer for Claude Code, Cursor, Qwen, and other AI coding assistants.

### 1. Discovery & Recommendation
Recommend the top-K skills for a free-form task with explainable scoring.
```bash
python3 taskmaster.py recommend "debug a production API timeout"
```

### 2. Composition
Compose a topologically ordered plan from multiple skills based on `depends_on` and `composes_with` rules.
```bash
python3 taskmaster.py compose error-detective distributed-tracing incident-responder
```

### 3. Agent Integration (MCP)
Expose the 269-skill catalog as an MCP server.
```bash
python3 taskmaster.py mcp-serve
```
Exposes tools like `search_skills`, `recommend_skills`, `compose_skills`, `get_skill`, `list_skills`, and `install_skill`.

### 4. Installation
Install or symlink skills into local agent runtimes (Claude, Cursor, Qwen).
```bash
# Install specific skills to Claude (project scope)
python3 taskmaster.py install claude --skills error-detective,distributed-tracing

# Install all skills to Cursor (user scope)
python3 taskmaster.py install cursor --scope user
```

## Phase 1 — Agent-Native Engine

The 269-skill catalog now ships with a hybrid recommender, a dependency-graph composer, and a pluggable embedding system. Three new CLI subcommands are available:

```bash
# Build (or rebuild) the embedding index. Uses sentence-transformers locally
# by default; set OPENAI_API_KEY and install the openai extra to use OpenAI.
python3 taskmaster.py embed
python3 taskmaster.py embed --rebuild

# Recommend the top-K skills for a free-form task.
python3 taskmaster.py recommend "debug a postgres deadlock" --max 5
python3 taskmaster.py recommend "design a multi-tenant API" --json

# Compose a topologically ordered plan from a set of skills.
python3 taskmaster.py compose postgres-tuning error-detective --json
```

The recommender combines semantic similarity (0.55), keyword overlap (0.30), and tag overlap (0.15). When the embedding extra is not installed, it falls back to keyword-only and tags every result with `degraded: true` so the caller can see the lower-quality mode.

The composer reads the optional `depends_on` frontmatter list, returns a topologically ordered plan, and surfaces missing dependencies with closest-match suggestions. Cycles raise an error.

### Optional Frontmatter Fields

| Field | Type | Semantics |
|---|---|---|
| `depends_on` | list[string] | Skills that must load first (used by `compose`). |
| `composes_with` | list[string] | Skills commonly used together (used by `recommend`). |

These fields are optional. Existing skills that omit them continue to validate and behave as before.

### Installation

The base install (`pip install taskmaster`) requires no new dependencies. To enable the full Agent OS features (MCP + semantic search):

```bash
pip install "taskmaster[all]"
```

For OpenAI-backed embeddings:

```bash
pip install "taskmaster[semantic,openai]"
export OPENAI_API_KEY=...
```

## License

MIT — see LICENSE file.
