# domain-chip-memory

`domain-chip-memory` is a Spark-style domain chip lab for one narrow goal:

- build a benchmark-first agent memory system that can beat the strongest systems on `LongMemEval`, `LoCoMo`, and `GoodAI LTM Benchmark`

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

Current internal lead as of 2026-03-23:

- `observational_temporal_memory + MiniMax-M2.7`
- first 25 real `LongMemEval_s` samples: `13/25` (`0.52`)
- same-slice comparison: `beam_temporal_atom_router + MiniMax-M2.7` at `3/25` (`0.12`)

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
It does **not** yet contain official benchmark scoring or a production-grade memory engine.

## Deliverables in this folder

- PRD: `docs/PRD.md`
- architecture: `docs/ARCHITECTURE.md`
- implementation plan: `docs/IMPLEMENTATION_PLAN.md`
- benchmark strategy: `docs/BENCHMARK_STRATEGY.md`
- benchmark autoloop program: `docs/BENCHMARK_AUTOLOOP_PROGRAM.md`
- deep research base: `docs/AI_MEMORY_RESEARCH_BASE_2026-03-22.md`
- first-version research lock: `docs/FIRST_VERSION_RESEARCH_LOCK.md`
- combination search program: `docs/COMBINATION_SEARCH_PROGRAM.md`
- frontier systems comparative analysis: `docs/FRONTIER_MEMORY_SYSTEMS_COMPARATIVE_ANALYSIS_2026-03-22.md`
- execution program and PRD gap: `docs/EXECUTION_PROGRAM_AND_PRD_GAP_2026-03-22.md`
- memory variation map and three builds: `docs/MEMORY_VARIATION_MAP_AND_THREE_BUILDS_2026-03-23.md`
- session log for today: `docs/SESSION_LOG_2026-03-23.md`
- benchmark substrate contracts: `docs/BENCHMARK_SUBSTRATE_CONTRACTS.md`
- people and labs map: `research/research_grounded/ARXIV_PEOPLE_AND_LABS_MAP_2026-03-22.md`
- autoloop flywheel: `docs/AUTOLOOP_FLYWHEEL.md`
- attribution plan: `docs/OPEN_SOURCE_ATTRIBUTION_PLAN.md`
- benchmark-grounded summary: `research/benchmark_grounded/benchmark_summary.json`
- research landscape memo: `research/research_grounded/MEMORY_SYSTEMS_LANDSCAPE_2026-03-22.md`
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
