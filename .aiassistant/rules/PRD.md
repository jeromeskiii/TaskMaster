---
apply: always
---

TaskMaster Agent-Native Skill Router - PRD

Version: 1.0  
Date: June 6, 2026  
Product Type: Local developer tool + MCP agent platform  
Status: Draft for build planning  

1. Project Overview

TaskMaster is an agent-native skill routing platform that helps AI coding agents discover, load, compose, validate, and install the right operational skills for a task. The product turns a large skill corpus into an intelligent local system that can be used directly by developers through a CLI and by AI agents through an MCP server.

The current TaskMaster system already has a modular Python package, CLI entrypoint, skill validation, discovery, search, suggestion, quality, hygiene, normalization, and related-skill commands. The next product leap is to evolve it from a CLI-only skill manager into a skill operating layer for Claude Code, Cursor, Qwen Code, Continuum, and custom agent harnesses.

The core product promise is simple: given a free-form task, TaskMaster recommends the right skills, explains why, orders them into a usable execution plan, and makes them available to the agent runtime.

2. Problem Statement

AI agents are powerful but often start tasks with generic behavior. Developers may have hundreds of skills, prompts, runbooks, or workflow instructions, but agents do not reliably know which ones to load, how to combine them, or when a task needs a safer operating procedure.

TaskMaster solves this by acting as the local routing brain for skill activation. Instead of forcing users to manually browse skill folders, TaskMaster converts task intent into ranked skill recommendations and executable skill plans.

3. Goals & Non-Goals

Goals

Turn TaskMaster into a local agent-native skill platform.
Preserve all existing CLI behavior and command compatibility.
Add semantic search, hybrid recommendation, and explainable ranking.
Add skill composition through dependency-aware ordering.
Expose the same core engine through MCP tools for external agents.
Add an installer that deploys skills into supported agent runtimes.
Keep optional dependencies isolated through package extras.
Support degraded offline mode when semantic dependencies are unavailable.

Non-Goals

No web UI for this release.
No cloud SaaS or multi-tenant hosted platform.
No marketplace, payment, or account system.
No automatic mass editing of source SKILL.md files.
No breaking changes to existing Python APIs or CLI commands.
No mandatory new frontmatter fields.

4. Target Users

Primary Persona: AI Power Developer

Name: Solo Builder Sam  
Profile: Developer using Claude Code, Cursor, Qwen Code, or a custom local agent harness.  
Goal: Get agents to behave like focused experts instead of generic assistants.  
Pain Points: Too many skills to manage manually, inconsistent agent behavior, weak task-specific context loading, no good way to compose procedures.  
Success Moment: Sam runs taskmaster recommend "debug a postgres deadlock" and receives a ranked set of useful skills with reasons and a clean execution order.

Secondary Persona: Agent Platform Builder

Name: Harness Builder Jordan  
Profile: Building a custom AI agent runtime or internal developer assistant.  
Goal: Expose a high-quality skill catalog to agents through a stable protocol.  
Pain Points: Needs searchable skill access, stable JSON outputs, local-first execution, and clear error handling.  
Success Moment: Jordan connects TaskMaster MCP to an agent and the agent can call recommend_skills, compose_skills, and get_skill directly.

5. Product Positioning

Product Name: TaskMaster  
Tagline: Skill routing and execution memory for AI agents.  

Positioning Statement

TaskMaster is a local Skill OS for AI agents. It helps developers and agent runtimes find the right expert procedure, compose multiple skills into a plan, and install those skills into the tools where agents actually work.

Wedge

Auto-load the right expert behavior before the agent starts working.

6. MVP Scope

The MVP release is TaskMaster v1.1 — Agent-Native Skill Router.

Core Features

Feature	Description	Priority
Skill Registry	Parse, validate, and load all skills as structured records.	P0
Semantic Index	Build local embedding index over skill name, description, tags, and body excerpt.	P0
Hybrid Recommender	Recommend skills using semantic similarity, keyword overlap, and tag overlap.	P0
Skill Composer	Order selected skills based on depends_on and related metadata.	P0
MCP Server	Expose skill tools through local stdio MCP server.	P0
Installer	Symlink or copy skills into Claude, Cursor, Qwen, or project targets.	P1
Degraded Mode	Fall back to keyword-only mode when semantic dependencies are missing.	P0
JSON Contracts	Stable machine-readable outputs for CLI and MCP.	P0
	7. User Stories

CLI User Stories

As a developer, I want to run taskmaster recommend "<task>" so I can quickly find the right skills.
As a developer, I want ranked results with reasons so I can trust why a skill was selected.
As a developer, I want to run taskmaster compose skill-a skill-b so I can get the correct loading order.
As a developer, I want TaskMaster to work even without embeddings installed so basic routing still functions.
As a developer, I want --json output so I can pipe results into scripts.

Agent Runtime User Stories

As an agent, I want to call search_skills so I can find relevant procedures.
As an agent, I want to call recommend_skills so I can decide which skills to load for a task.
As an agent, I want to call compose_skills so I can load multiple skills in a safe order.
As an agent, I want to call get_skill so I can retrieve the full content of a selected skill.
As an agent platform, I want stable error codes so failures can be handled programmatically.

8. Functional Requirements

8.1 Skill Registry

TaskMaster must parse every SKILL.md file into a SkillRecord containing:

name
description
category
risk
tags or metadata when available
source path
body excerpt
validation status
parse errors, if any
optional depends_on
optional composes_with

Invalid skills must remain visible instead of disappearing from the corpus.

8.2 Semantic Index

TaskMaster must support an optional local semantic index.

Requirements:

Default local provider: sentence-transformers using all-MiniLM-L6-v2.
Optional OpenAI embedding provider.
Index storage path: .taskmaster_cache/embeddings/{model_hash}/.
Store FAISS index and manifest.
Manifest maps skill path or ID to content hash.
Incremental rebuild when a skill changes.
--rebuild flag forces a full rebuild.
Corrupt index should be detected and safely rebuilt.

8.3 Recommender

The recommender must accept a free-form task and return ranked skills.

Default scoring:

score = 0.55 * semantic_similarity
      + 0.30 * keyword_overlap
      + 0.15 * tag_overlap

When semantic mode is unavailable:

score = 0.70 * keyword_overlap
      + 0.30 * tag_overlap

Every result must include:

skill name
path
category
risk
score
reasons
degraded flag

Supported filters:

max results
category
max risk
include/exclude high-risk skills

8.4 Composer

The composer must accept a list of skill names or paths and return an ordered execution plan.

Requirements:

Read optional depends_on field.
Read optional composes_with field for related suggestions.
Return topological order.
Detect cycles and return a stable error.
Return missing dependency warnings without failing the whole plan.
Suggest closest matching skill names when a dependency is missing.
Deterministic output for the same input.

8.5 MCP Server

TaskMaster must expose a local stdio MCP server.

Command:

taskmaster mcp serve

Required MCP tools:

Tool	Purpose
search_skills	Search skill catalog by text query.
recommend_skills	Recommend skills for a free-form task.
compose_skills	Return ordered skill execution plan.
get_skill	Return full skill metadata and body.
validate_skill	Validate one skill.
corpus_stats	Return catalog statistics and index state.
install_skill	Install selected skills into target runtime.
	MCP must never write logs to stdout because stdout is reserved for JSON-RPC transport. Logs must go to stderr.

8.6 Installer

Command examples:

taskmaster install claude --scope project
taskmaster install cursor --scope user --skills error-detective,pytest
taskmaster uninstall claude --scope project

Requirements:

Support targets: claude, cursor, qwen, all.
Support scopes: project, user.
Default behavior: symlink.
Fallback: --copy.
Write .taskmaster-manifest.json for tracking installs.
Uninstall must reverse only TaskMaster-managed installs.
Never mutate source skill files.

9. CLI Requirements

Existing commands must remain supported:

validate
list
search
suggest
stats
generate-index
check
export
diff
quality
hygiene
normalize
related

New commands:

embed
recommend
compose
mcp serve
install
uninstall

Example outputs:

taskmaster recommend "debug a production API timeout"

Recommended skills:
1. error-detective        score: 0.91
2. distributed-tracing    score: 0.84
3. performance-profiling  score: 0.79
4. incident-responder     score: 0.72

Reasons:
- matched debugging terms
- matched production reliability category
- timeout suggests tracing and performance profiling

10. Technical Architecture

flowchart TD
    A[User Task] --> B[CLI or MCP Tool]
    B --> C[TaskMaster Core Engine]
    C --> D[Skill Registry]
    C --> E[Discovery + Keyword Search]
    C --> F[Semantic Embedding Index]
    D --> G[Hybrid Recommender]
    E --> G
    F --> G
    G --> H[Ranked Skill Matches]
    H --> I[Skill Composer]
    I --> J[Execution Plan]
    J --> K[CLI JSON/Text Output]
    J --> L[MCP Response]
    J --> M[Installer]

Proposed Module Layout

taskmaster/
  __init__.py
  cli.py
  corpus.py
  discovery.py
  validation.py
  recommend.py
  compose.py
  install.py
  errors.py
  embeddings/
    __init__.py
    provider.py
    text.py
    index.py
    _sentence_transformer_provider.py
    _openai_provider.py
  mcp/
    __init__.py
    server.py

11. Data Contracts

Ranked Skill Match

{
  "name": "error-detective",
  "path": "error-detective/SKILL.md",
  "category": "development",
  "risk": "safe",
  "score": 0.91,
  "reasons": [
    "matched keyword: debug",
    "matched keyword: error",
    "semantic similarity above threshold"
  ],
  "degraded": false
}

Compose Result

{
  "input": ["incident-responder", "error-detective", "distributed-tracing"],
  "plan": [
    {"name": "incident-responder", "reason": "initial triage first"},
    {"name": "error-detective", "reason": "debugging after triage"},
    {"name": "distributed-tracing", "reason": "depends on error context"}
  ],
  "warnings": [],
  "degraded": false
}

Error Contract

{
  "error": {
    "code": "cycle",
    "message": "Dependency cycle detected: a -> b -> a",
    "recoverable": true
  }
}

12. Non-Functional Requirements

Performance

Cold corpus load should complete within 2 seconds for the current corpus size.
Warm search and recommend should return within 500 ms when index is loaded.
Embedding rebuild may take longer but must show progress in CLI.
MCP startup should avoid eager embedding rebuild unless explicitly requested.

Reliability

Existing CLI commands must remain backward compatible.
Invalid skills must not crash registry loading.
Missing optional dependencies must produce helpful degraded-mode output.
Installer must be reversible.

Security

Do not execute arbitrary skill content.
Do not follow symlinks outside expected directories during install unless explicitly approved.
Do not print secrets from skill bodies in logs.
MCP errors must not leak local environment variables.
Installer must require explicit --scope user when writing outside the current project.

Maintainability

Keep core logic separate from CLI rendering.
Use stable dataclasses or typed return objects internally.
Use JSON-serializable dicts at public boundaries.
Optional extras must not affect base install.

13. Dependencies

Base install:

pip install taskmaster

Semantic install:

pip install "taskmaster[semantic]"

MCP install:

pip install "taskmaster[mcp]"

All features:

pip install "taskmaster[all]"

Optional dependencies:

semantic = [
  "sentence-transformers>=2.2",
  "faiss-cpu>=1.7",
  "numpy>=1.24"
]
openai = [
  "openai>=1.0"
]
mcp = [
  "mcp>=1.0"
]
all = [
  "taskmaster[semantic,mcp,openai]"
]

14. Success Metrics

Primary KPI

Recommendation Acceptance Rate  
Target: 70% of top-3 recommendations are accepted or used in test scenarios.

Secondary KPIs

KPI	Target
CLI backward compatibility	100% existing tests pass
Recommend latency	<500 ms warm path
MCP tool availability	7/7 tools exposed
Installer reversibility	100% uninstall success in tests
Degraded mode support	Search/recommend/MCP work without semantic extra
Test expansion	30+ new tests
	15. Milestones

Phase 1 — Recommendation Engine

Deliverables:

optional semantic dependencies
embedding provider interface
local sentence-transformer provider
FAISS index
embed command
recommend command
degraded keyword fallback
tests for embedding, index, recommend, degraded mode

Phase 2 — Skill Composer

Deliverables:

optional depends_on and composes_with support
compose command
cycle detection
missing dependency warnings
deterministic topological ordering
tests for chain, diamond, cycle, missing dep, empty input

Phase 3 — MCP Server

Deliverables:

taskmaster mcp serve
7 MCP tools
stderr-only logging
protocol-level tests
README setup for Claude Code and Cursor

Phase 4 — Installer

Deliverables:

install
uninstall
supported targets: Claude, Cursor, Qwen
project and user scope
symlink and copy modes
manifest tracking
macOS install test job

Phase 5 — Polish & Release

Deliverables:

README "Agent-Native Usage" section
release smoke tests
version bump
changelog
tag v1.1.0

16. Testing Strategy

Unit Tests

frontmatter parsing
optional field normalization
tokenization
scoring math
risk/category filters
deterministic tie breaking
compose graph ordering
cycle detection
missing dependency suggestions

Integration Tests

build/save/load FAISS index
recommend with real fixture skills
recommend degraded mode
CLI command output shape
MCP boot and list tools
installer symlink/copy/uninstall

Regression Tests

all existing CLI tests must pass unchanged
taskmaster.py remains valid entrypoint
existing JSON outputs do not break

Smoke Tests

python3 taskmaster.py validate
python3 taskmaster.py recommend "debug a postgres deadlock"
python3 taskmaster.py compose error-detective distributed-tracing
python3 taskmaster.py mcp serve

17. Risks & Mitigations

Risk	Impact	Mitigation
Semantic dependencies make install heavy	Medium	Keep dependencies optional extras
Embedding cold-start surprises users	Medium	Lazy build, progress output, clear docs
MCP protocol breakage	High	Pin version and add MCP boot test in CI
Bad recommendations reduce trust	High	Explainable reasons and fixture-based ranking tests
Installer writes to wrong directory	High	Require explicit scope and manifest tracking
Cycles in skill dependencies	Medium	Detect cycle and return stable error
Degraded mode hides lower quality	Medium	Always include degraded: true
Scope creep into web UI/cloud	Medium	Explicitly defer web and SaaS work
	18. Launch Checklist

Existing test suite passes.
30+ new tests pass.
taskmaster recommend returns explainable ranked results.
taskmaster compose returns deterministic ordered plan.
taskmaster mcp serve exposes all required tools.
Installer supports project-scope install and uninstall.
Degraded mode works without semantic dependencies.
README includes install, recommend, compose, MCP, and installer examples.
CI includes MCP boot smoke test.
Release tagged as v1.1.0.

19. Future Roadmap

v1.2 — Skill Workbench

duplicate detector
skill quality dashboard
broken dependency graph viewer
skill upgrade suggestions
canonical skill generator

v1.3 — Harness Integration

task intake API
context pack generation
execution result validation
memory of which skills worked for which tasks
project-specific skill ranking

v2.0 — Team/Cloud Layer

hosted skill registry
team skill governance
approval workflow
organization-level usage analytics
optional hosted API

20. Open Questions

Should install cursor write to a Cursor-specific skill location or project .cursor/rules adapter format?
Should high-risk skills be excluded by default in recommendations?
Should recommend return only skill names by default or include excerpts?
Should TaskMaster support project-local skill overrides?
Should OpenAI embeddings be configured by environment variable only, or also through taskmaster.toml?
Should MCP expose full skill bodies by default, or require include_body=true?

21. Definition of Done

TaskMaster v1.1 is done when a developer can install the package, ask for skill recommendations from the CLI, compose those skills into an ordered plan, run the MCP server, connect an agent runtime, and install selected skills into that runtime without breaking existing CLI behavior.