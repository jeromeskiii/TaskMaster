# TaskMaster Evolution Design

Date: 2026-06-02

## Goal

Evolve TaskMaster from a capable single-file CLI into a human-first operational console for the skill corpus, while preserving scriptability and future UI/API optionality.

The first wave should improve three areas together:

1. Discovery: better search, suggestion quality, and adjacent-skill navigation.
2. Maintenance: better hygiene reporting and safe metadata normalization.
3. Operator UX: clearer health summaries, consistent JSON, and explainable rankings.

This is an incremental architecture and feature upgrade, not a rewrite.

## Non-Goals

1. No web UI in this wave.
2. No service/server deployment model.
3. No change to the primary product surface: the CLI remains the main interface.
4. No mass auto-edit of the corpus without explicit dry-run and user-invoked commands.

## Current Problems

1. Core logic is concentrated in one file, which makes feature growth and regression control harder.
2. Output shapes are inconsistent across commands, especially for JSON-capable flows.
3. Search and suggestion ranking work, but they do not explain why a result matched.
4. Corpus hygiene issues are partly visible through `validate`, but there is no dedicated maintenance view for duplicates, malformed tag shapes, or normalization candidates.
5. Several commands still mutate skill dictionaries in-place to attach scores, which makes behavior harder to reason about and test.

## Product Direction

TaskMaster should remain CLI-first and human-first, but with a structured engine underneath. Each command should build structured results first, then render either concise text or normalized JSON from the same data.

That yields three benefits:

1. Better interactive UX without losing shell ergonomics.
2. Cleaner internal boundaries for future improvements.
3. A stable path to future agents, APIs, or a local UI without revisiting the core logic.

## Approach Options

### Option 1: Keep the single-file CLI and add features directly

Pros:

1. Lowest short-term implementation cost.
2. Minimal file churn.

Cons:

1. Discovery, maintenance, and reporting logic will become more tightly coupled.
2. Test organization will continue to lag the product surface.
3. JSON contracts and renderer behavior will stay inconsistent unless manually enforced everywhere.

### Option 2: Full rewrite into a multi-module package with a larger product reshape

Pros:

1. Cleanest theoretical architecture.
2. Maximum freedom to redesign abstractions.

Cons:

1. Too much churn relative to current product maturity.
2. High regression risk.
3. Delays user-visible improvements.

### Option 3: Incremental modularization behind the existing CLI

Pros:

1. Preserves the current command surface.
2. Improves maintainability immediately.
3. Enables feature upgrades across discovery, maintenance, and UX in one controlled wave.
4. Keeps compatibility with current operator habits and shell usage.

Cons:

1. Requires a staged migration rather than a single clean cut.
2. Some temporary adapter code will exist during the transition.

Recommended: Option 3.

## Proposed Architecture

Create a small `taskmaster/` package and keep `taskmaster.py` as a compatibility entrypoint.

### Modules

1. `taskmaster/corpus.py`
   - skill loading
   - YAML frontmatter parsing
   - cache read/write
   - metadata normalization helpers
   - canonical skill record creation

2. `taskmaster/validation.py`
   - per-skill validation
   - corpus-wide validation aggregation
   - hygiene checks
   - duplicate and near-duplicate detection
   - normalization candidate discovery

3. `taskmaster/discovery.py`
   - full-text search
   - suggestion ranking
   - related-skill ranking
   - scoring explanations

4. `taskmaster/reporting.py`
   - text rendering
   - JSON shaping
   - validation and health summaries
   - quality and dashboard reports

5. `taskmaster/cli.py`
   - argument parsing
   - command dispatch
   - output selection and exit code handling

6. `taskmaster.py`
   - thin shim that calls `taskmaster.cli.main()`

## Data Model

Use normalized records across all modules.

### SkillRecord

Required fields:

1. `dir`
2. `path`
3. `frontmatter`
4. `frontmatter_valid`
5. `frontmatter_error`
6. `body`
7. `line_count`
8. `size_bytes`

Derived fields may be computed but should not be mutated ad hoc during rendering.

### RankedMatch

For search, suggest, and related-style results:

1. `skill`
2. `score`
3. `reasons`

`reasons` is a short list of explicit match drivers such as:

1. `name term match`
2. `tag overlap: api, graphql`
3. `category hint: backend`
4. `description overlap`

### Report Shapes

Validation and hygiene commands should use consistent structured reports:

1. `stats`
2. `issues`
3. `highlights`
4. `skills` or `matches` when relevant

## First-Wave Feature Set

### Discovery

Upgrade `search`:

1. Support `--category`, `--risk`, and `--tag` filters.
2. Return match reasons.
3. Improve ranking with term overlap and weighted field matches while avoiding substring-noise regressions.

Upgrade `suggest`:

1. Return explicit reasons for the match.
2. Preserve the task-to-skill intent heuristics, but make the output explainable.
3. Keep relevance scoring deterministic and easy to inspect in tests.

Add `related`:

1. Input: skill name or directory.
2. Output: adjacent skills based on category, tags, description terms, and title tokens.
3. Use case: “I found one relevant skill, what else should I inspect?”

### Maintenance

Add `hygiene`:

1. Duplicate name detection.
2. Near-duplicate description detection.
3. Tag-shape inconsistency detection.
4. Frontmatter parse-error rollups.
5. Category/risk anomaly summaries.

Add `normalize`:

1. Dry-run by default.
2. Surface mechanical metadata cleanups that are safe to apply.
3. Initial scope:
   - normalize scalar tag strings into canonical list form for export/reporting logic
   - highlight malformed date-like values
   - flag invalid or suspicious metadata shapes

This command should not silently rewrite the corpus on ordinary CLI flows.

### Operator UX

Upgrade `stats` into a health dashboard:

1. category distribution
2. risk distribution
3. validation breakdown
4. parse-error counts
5. lowest-quality skills
6. highest-priority hygiene findings

Standardize JSON:

1. Commands that produce report-like output should support `--json`.
2. JSON shape should be stable and derived from the same internal records as text output.

Explainability:

1. ranked commands show why results matched
2. health commands show why counts exist
3. normalization commands show what would change and why

## Command Surface

Preserve existing commands:

1. `validate`
2. `list`
3. `search`
4. `stats`
5. `generate-index`
6. `check`
7. `suggest`
8. `export`
9. `diff`
10. `quality`

Add:

1. `hygiene`
2. `related`
3. `normalize`

The new commands should feel native to the existing CLI rather than a separate subsystem.

## Migration Plan

### Phase 1: Internal split without product expansion

1. Create the package modules.
2. Move existing logic into the correct module boundaries.
3. Keep behavior equivalent where possible.
4. Keep `taskmaster.py` as a stable entrypoint.

### Phase 2: Discovery upgrades

1. Introduce structured ranked results.
2. Upgrade `search` and `suggest`.
3. Add `related`.

### Phase 3: Maintenance upgrades

1. Add `hygiene`.
2. Add dry-run `normalize`.
3. Expand validation highlights.

### Phase 4: Operator UX upgrades

1. standardize JSON
2. improve dashboard output
3. unify report rendering

## Error Handling

1. Invalid skills remain visible records.
2. Parse failures are surfaced explicitly in both text and JSON.
3. Ranking commands should skip unusable inputs only when required, and should state why.
4. Maintenance commands should separate:
   - parse failures
   - validation failures
   - normalization candidates
   - suspicious duplicates

## Testing Strategy

Split the focused suite by responsibility:

1. `tests/test_corpus.py`
2. `tests/test_validation.py`
3. `tests/test_discovery.py`
4. `tests/test_reporting.py`
5. `tests/test_cli.py`

Coverage goals for this wave:

1. YAML parsing and duplicate-key rejection
2. cache behavior
3. tag normalization edge cases
4. search and suggest ranking explanations
5. related-skill ranking
6. duplicate and near-duplicate hygiene checks
7. JSON contract shape for report-producing commands
8. text rendering smoke tests for major commands

## Risks

1. Refactor drift: architecture cleanup can accidentally change CLI behavior.
   - Mitigation: preserve command names and add CLI-level regression tests.

2. Over-scoring or under-scoring in discovery upgrades.
   - Mitigation: fixture-driven ranking tests and explicit explanation outputs.

3. Scope expansion into a UI/API too early.
   - Mitigation: keep this wave strictly CLI-first.

4. Unsafe automatic metadata changes.
   - Mitigation: dry-run default and explicit apply mode only for mechanical fixes.

## Success Criteria

1. Existing CLI workflows still work through `taskmaster.py`.
2. Search and suggest results are more explainable and easier to trust.
3. Operators can see corpus health beyond simple validation counts.
4. Maintenance issues such as duplicate names and malformed tag shapes have dedicated visibility.
5. JSON outputs become consistent enough for future agent or UI consumers.
6. The codebase is modular enough that future work does not require expanding a single monolithic file.
