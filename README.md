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

## License

MIT — see LICENSE file.