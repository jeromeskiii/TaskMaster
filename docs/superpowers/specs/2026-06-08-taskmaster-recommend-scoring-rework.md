# TaskMaster Recommend Scoring Rework — Follow-up Spec

## Status

Filed from v1.1.1 Gap E (bounded scoring investigation). The v1.1.1
release took the documentation branch for Gap E — adding a
`--keyword-only` flag, documenting the degraded-mode limitation, and
filing this spec for a fuller scoring rework.

## Problem

The keyword-only scoring path in `taskmaster/recommend.py` is a simple
bag-of-words overlap between the user's task tokens and a skill's
`name + description + first 1000 chars of body + tags`. It produces
noisy results for short or generic queries:

- "debug a production API timeout" → top result `comfyui-gateway`
  (matched on the literal word "api" in its description), with
  `bug-hunter`, `error-detective`, and other debugging skills ranked
  lower.

This is a real quality bug: a developer asking for help debugging an
API timeout does not want a ComfyUI image-generation gateway as the
top recommendation.

## Why this is hard

A v1.1.1-sized fix (weight name matches 2x or 3x over description
matches) improves things marginally but does not solve the problem,
because:

- Tag-only matches (e.g. `tags: [api-gateway]` matching `api` in the
  query) are not name matches and don't get the boost.
- A skill whose name is a long hyphenated string (e.g.
  `distributed-debugging-debug-trace`) tokenizes to many tokens,
  inflating its name-overlap count.
- Description tokens for unrelated skills often share a single
  high-frequency word with the query (e.g. "api", "data", "system").

A proper fix needs a different signal: either real semantic similarity
(requires the `[semantic]` extra) or a smarter keyword scorer (TF-IDF,
BM25, or learned weights).

## Out of scope for v1.1.1

This work was explicitly deferred to its own spec because:

- A real fix likely requires new dependencies (e.g. `rank_bm25`,
  `scikit-learn`) or model changes.
- The behavioral change risks regressing the 70+ existing tests.
- The user's primary workflow uses MCP clients with the full
  `[semantic]` extra, so the keyword path is a degraded fallback, not
  the main path.

## Candidate approaches

1. **TF-IDF over name + description + tags** — pure Python, no model
   dependencies. Requires `collections.Counter` + IDF table built from
   the corpus at module init.
2. **BM25** — well-understood, requires `rank_bm25` or hand-rolling.
3. **Stronger name-match signal** — name match required for any
   skill to enter the top 3 unless the corpus has a strong alternative.
4. **Pre-computed skill embeddings cached on disk** — already half-built
   in the `[semantic]` path; the keyword path can use a deterministic
   fallback based on hashed token embeddings.
5. **LLM re-rank** — out of scope (defeats the local-first design).

## Acceptance criteria (to be defined when this spec is picked up)

- `recommend "debug a production API timeout"` puts `bug-hunter` or
  `error-detective` in the top 3 in degraded mode.
- All existing tests in `tests/test_recommend.py` continue to pass.
- The fix ships behind the same `degraded: true` envelope so callers
  can detect they are getting keyword-only results.
- No new required dependencies; the `[semantic]` extra stays optional.
