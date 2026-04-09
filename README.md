# domain-chip-memory

`domain-chip-memory` is a Spark-style domain chip lab for one narrow goal:

- build a benchmark-first agent memory system that can beat the strongest systems on `BEAM`, `LongMemEval`, `LoCoMo`, and `GoodAI LTM Benchmark`

Shadow benchmark:

- keep `ConvoMem` as a regression guardrail for short-history and full-context-competitive slices

This repo is not framed as a generic memory SDK yet.
It is a research instrument and operating scaffold for memory-system design, benchmarking, mutation, and promotion.

## Why this chip exists

The current public landscape is good enough that hand-wavy memory architecture is no longer useful.

What matters now:

- benchmark-native ingestion and retrieval
- explicit handling of time, contradictions, and fact updates
- apples-to-apples evaluation against the public benchmark stack
- repeatable mutation loops instead of one-off prompt tinkering
- attribution discipline when borrowing from MIT and Apache 2.0 codebases

This chip exists to govern that work honestly.

## Current status

Current status: `exploratory`

Current most complete measured path as of 2026-04-03:

- `summary_synthesis_memory + heuristic_v1`
- bounded real reruns over the remaining `LongMemEval_s` samples `201-500`: `300/300` (`1.00`)
- contiguous measured `LongMemEval_s` coverage through sample `500`: `500/500` (`1.00`)
- this now clears the currently pinned public `LongMemEval_s` threshold on the same official dataset surface

Historical internal lead as of 2026-03-24:

- `observational_temporal_memory + MiniMax-M2.7`
- real rerun on March 23, 2026 over the first 25 `LongMemEval_s` samples: `25/25` (`1.00`)
- real rerun on March 23, 2026 over the first 50 `LongMemEval_s` samples: `50/50` (`1.00`)
- real rerun on March 24, 2026 over `LongMemEval_s` samples `51-75`: `25/25` (`1.00`)
- real rerun on March 24, 2026 over `LongMemEval_s` samples `76-100`: `25/25` (`1.00`)
- real rerun on March 24, 2026 over `LongMemEval_s` samples `101-125`: `25/25` (`1.00`)
- real rerun on March 24, 2026 over `LongMemEval_s` samples `126-150`: `25/25` (`1.00`)
- real rerun on March 25, 2026 over `LongMemEval_s` samples `151-175`: `25/25` (`1.00`)
- real rerun on March 25, 2026 over `LongMemEval_s` samples `176-200`: `25/25` (`1.00`)
  - category split on the same artifact: `multi-session` `13/13` (`1.00`), `single-session-preference` `12/12` (`1.00`)
- contiguous measured `LongMemEval_s` coverage through sample `200`: `200/200` (`1.00`)
- real rerun on March 23, 2026 over the first 25 `LoCoMo` `conv-26` questions: `24/25` (`0.96`)
  - audited scorecard view on the same artifact: `24/24` (`1.00`) after excluding the one known benchmark inconsistency
- real rerun on March 24, 2026 over the next 25 `LoCoMo` `conv-26` questions (`q26-50`): `25/25` (`1.00`)
  - audited scorecard view on the same artifact: `25/25` (`1.00`) with no exclusions
- real rerun on March 24, 2026 over the next bounded `LoCoMo` `conv-26` questions (`q51-75`): `25/25` (`1.00`)
  - audited scorecard view on the same artifact: `25/25` (`1.00`) with no exclusions
- real rerun on March 24, 2026 over the next bounded `LoCoMo` `conv-26` questions (`q76-100`): `25/25` (`1.00`)
  - audited scorecard view on the same artifact: `25/25` (`1.00`) with no exclusions
- real rerun on March 24, 2026 over the next bounded `LoCoMo` `conv-26` questions (`q101-125`): `25/25` (`1.00`)
  - progression on the same slice: baseline `1/25` -> rerun `23/25` -> rerun `25/25`
  - audited scorecard view on the source-of-truth artifact: `25/25` (`1.00`) with no exclusions
- real rerun on March 24, 2026 over the next bounded `LoCoMo` `conv-26` questions (`q126-150`): `25/25` (`1.00`)
  - progression on the same slice: baseline `3/25` -> rerun `23/25` -> rerun `24/25` -> rerun `25/25`
  - audited scorecard view on the source-of-truth artifact: `25/25` (`1.00`) with no exclusions
- bounded `LoCoMo` same-provider ladder on the same first-25 `conv-26` slice:
  - `observational_temporal_memory`: `24/25` raw, `24/24` audited
  - `dual_store_event_calendar_hybrid`: `23/25` raw, `23/24` audited
  - `beam_temporal_atom_router`: `6/25` raw, `6/24` audited
- MiniMax operating notes and default guardrails now live in `docs/MINIMAX_OPERATIONAL_NOTES_2026-03-23.md`

Current MiniMax frontier on that `LoCoMo` slice is now explicit:

- MiniMax is working well when the packet already contains the exact answer-bearing turn or structured predicate
- MiniMax is no longer the limiting factor on the current bounded `LoCoMo` slice once benchmark inconsistencies are excluded
- scorecards now annotate these known issue classes directly in `known_issue_summary` and expose `audited_overall` so future reruns do not look like generic model regressions
- the only remaining miss on the first bounded `24/25` run is:
  - `conv-26-qa-6`: likely benchmark inconsistency, with context pointing to `Saturday` while gold expects `Sunday`
- the adjacent `q26-50` slice is now clean on a real rerun:
  - `25/25` raw
  - `25/25` audited
- the adjacent `q51-75` slice is now also clean on a real rerun:
  - `25/25` raw
  - `25/25` audited
- the adjacent `q76-100` slice is now also clean on a real rerun:
  - `25/25` raw
  - `25/25` audited
- the adjacent `q101-125` slice is now also clean on a real rerun:
  - `25/25` raw
  - `25/25` audited
- the adjacent `q126-150` slice is now also clean on a real rerun:
  - `25/25` raw
  - `25/25` audited
- the newest MiniMax-specific lesson is explicit:
  - object/meaning questions close cleanly once the packet surfaces exact structured predicates
  - MiniMax compaction must preserve `answer_candidate` lines or the model can drift back to nearby but wrong abstractions like `it` or `mental health`
  - on the sixth bounded `LoCoMo` slice, the last real misses were answer-shape drift, not evidence gaps:
    - possessive/location normalization like `in my slipper` -> `In Melanie's slipper`
    - punctuation normalization like `Read a book and paint` -> `Read a book and paint.`

The repo now has the standard Spark domain-chip scaffold:

- project manifest
- chip manifest
- researcher config
- benchmark and research lanes
- docs for architecture, strategy, and autoloops
- schemas and templates
- a small Python package for watchtower packets and mutation suggestions
- a local evaluator for readiness scoring

It now contains a benchmark substrate, baseline packet builders, local deterministic execution, file loaders, and an env-gated OpenAI provider path for bounded real benchmark runs.
It does **not** yet contain full official benchmark reproduction across the whole stack or a production-grade memory engine.

## Docs

Start here instead of scanning the repo manually:

- docs index: `docs/README.md`
- research index: `research/README.md`
- research-to-build map: `docs/RESEARCH_TO_BUILD_MAP_2026-03-25.md`

Most important current execution docs:

- honest current-state assessment: `docs/MEMORY_SYSTEM_HONEST_ASSESSMENT_2026-03-29.md`
- implementation plan: `docs/IMPLEMENTATION_PLAN.md`
- current test and validation plan: `docs/CURRENT_TEST_AND_VALIDATION_PLAN_2026-03-29.md`
- frontier status: `docs/FRONTIER_STATUS_2026-03-28.md`
- BEAM official reproduction plan: `docs/BEAM_OFFICIAL_REPRODUCTION_PLAN_2026-03-29.md`
- memory architecture evolution plan: `docs/MEMORY_ARCHITECTURE_EVOLUTION_PLAN_2026-03-25.md`
- unified memory system program: `docs/UNIFIED_MEMORY_SYSTEM_PROGRAM_2026-03-25.md`
- spark memory sdk implementation path: `docs/SPARK_MEMORY_SDK_IMPLEMENTATION_PATH_2026-03-27.md`

Repo structure surfaces:

- benchmark-grounded summary: `research/benchmark_grounded/benchmark_summary.json`
- schemas: `schemas/`
- templates: `templates/`

## Quick start

Install editable:

```powershell
pip install -e .
```

Fill in provider credentials in [.env](/C:/Users/USER/Desktop/domain-chip-memory/.env) or copy from [.env.example](/C:/Users/USER/Desktop/domain-chip-memory/.env.example). The CLI now loads `.env` automatically.

Run the local chip evaluator:

```powershell
python evaluate_chip.py
```

Build the watchtower summary:

```powershell
python -m domain_chip_memory.cli watchtower --write
```

Build the strategy packet:

```powershell
python -m domain_chip_memory.cli packets --write
```

See the current benchmark target ledger:

```powershell
python -m domain_chip_memory.cli benchmark-targets
```

Inspect the normalized benchmark substrate contracts:

```powershell
python -m domain_chip_memory.cli benchmark-contracts
```

Inspect the baseline packet and manifest contracts:

```powershell
python -m domain_chip_memory.cli baseline-contracts
```

Inspect the scorecard contracts and canonical benchmark config lock:

```powershell
python -m domain_chip_memory.cli scorecard-contracts
python -m domain_chip_memory.cli canonical-configs
```

Inspect loader, provider, and runner contracts:

```powershell
python -m domain_chip_memory.cli loader-contracts
python -m domain_chip_memory.cli provider-contracts
python -m domain_chip_memory.cli runner-contracts
python -m domain_chip_memory.cli memory-system-contracts
```

Build a real Spark KB vault from a snapshot file or scaffold the demo vault:

```powershell
python -m domain_chip_memory.cli validate-spark-kb-inputs path\\to\\snapshot.json --repo-source-manifest path\\to\\repo_sources.json --filed-output-manifest path\\to\\filed_outputs.json
python -m domain_chip_memory.cli build-spark-kb path\\to\\snapshot.json path\\to\\vault --repo-source path\\to\\README.md --repo-source-manifest path\\to\\repo_sources.json --filed-output-file path\\to\\answer.json --filed-output-manifest path\\to\\filed_outputs.json
python -m domain_chip_memory.cli demo-spark-kb path\\to\\demo_vault
python -m domain_chip_memory.cli spark-kb-health-check path\\to\\vault
```

Manifest entries are resolved relative to the manifest file location.
`validate-spark-kb-inputs` now gives a preflight report for snapshot shape, manifest resolution, missing files, and filed-output payload parsing.
`spark-kb-health-check` now also validates repo-source pages against `raw/repos/` copies and checks that filed query pages still contain their expected sections.
`build-spark-kb` compile results now expose both `repo_source_count` and `filed_output_count`.
There is now a checked-in example bundle under `docs/examples/spark_kb/` for validator and compiler smoke checks.

Run a bounded real-provider smoke test once `OPENAI_API_KEY` is set:

```powershell
python -m domain_chip_memory.cli run-longmemeval-baseline path\\to\\longmemeval_s_cleaned.json --baseline beam_temporal_atom_router --provider openai:gpt-4.1-mini --limit 1
python -m domain_chip_memory.cli run-longmemeval-baseline path\\to\\longmemeval_s_cleaned.json --baseline beam_temporal_atom_router --provider minimax:YOUR_MINIMAX_MODEL --limit 1
```

Run local demo scorecards:

```powershell
python -m domain_chip_memory.cli demo-scorecards
```

Run the first candidate memory system on local benchmark files:

```powershell
python -m domain_chip_memory.cli run-longmemeval-baseline path\\to\\longmemeval_s_cleaned.json --baseline beam_temporal_atom_router --provider heuristic_v1 --limit 10
python -m domain_chip_memory.cli run-longmemeval-baseline path\\to\\longmemeval_s_cleaned.json --baseline observational_temporal_memory --provider heuristic_v1 --limit 10
python -m domain_chip_memory.cli run-longmemeval-baseline path\\to\\longmemeval_s_cleaned.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --limit 10
```

Run a first official-public `BEAM` smoke lane once you have an unpacked upstream chats directory:

```powershell
python -m domain_chip_memory.cli run-beam-public-baseline path\\to\\chats --chat-size 128K --baseline observational_temporal_memory --provider heuristic_v1 --limit 1 --upstream-commit 3e12035532eb85768f1a7cd779832b650c4b2ef9
```

Export those results into upstream-style answer files and summarize upstream evaluation output:

```powershell
python -m domain_chip_memory.cli export-beam-public-answers artifacts\\benchmark_runs\\beam_public_scorecard.json artifacts\\beam_results --result-file-name domain_chip_memory_answers.json
python -m domain_chip_memory.cli run-beam-official-evaluation path\\to\\beam_upstream_repo artifacts\\beam_results --chat-size 128K --result-file-name domain_chip_memory_answers.json --dry-run
python -m domain_chip_memory.cli summarize-beam-evaluation path\\to\\evaluation-domain_chip_memory_answers.json
```

Generate compact comparison artifacts across all current systems:

```powershell
python -m domain_chip_memory.cli compare-longmemeval-local path\\to\\longmemeval_s_cleaned.json --provider heuristic_v1 --write artifacts\\benchmark_runs\\longmemeval_s_system_comparison.json
python -m domain_chip_memory.cli compare-locomo-local path\\to\\locomo10.json --provider heuristic_v1 --write artifacts\\benchmark_runs\\locomo10_system_comparison.json
python -m domain_chip_memory.cli compare-goodai-local path\\to\\benchmark-v3-32k.yml path\\to\\definitions --provider heuristic_v1 --write artifacts\\benchmark_runs\\goodai_32k_system_comparison.json
```

Generate bounded mutation suggestions:

```powershell
python -m domain_chip_memory.cli suggest
```

Run tests:

```powershell
python -m pytest
```

## What is different about this chip

Unlike the other domain chips, this one is not centered on a business lane or a content lane.
It is centered on a **benchmark suite**.

The operating unit is:

1. benchmark slice
2. failure trace
3. mutation packet
4. re-run
5. promotion or rollback

That means the chip should eventually own:

- benchmark adapters
- baseline runners
- retrieval traces
- answer-policy variants
- per-category scorecards
- regression gates

## Standard

Keep these evidence classes separate:

- `research_grounded`
- `benchmark_grounded`
- `exploratory_frontier`
- `realworld_validated`

Do not promote a memory doctrine because it sounds elegant.
Promote it only if it improves benchmark behavior, survives contradiction review, and keeps attribution honest.
