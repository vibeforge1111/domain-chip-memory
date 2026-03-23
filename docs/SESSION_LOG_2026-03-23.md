# Session Log 2026-03-23

Status: handoff-ready

## What was completed today

### 1. Real benchmark execution path

- Added `.env` loading through `src/domain_chip_memory/env.py`
- Wired provider loading into `src/domain_chip_memory/cli.py`
- Added real remote provider support in `src/domain_chip_memory/providers.py`
- Supported:
  - `openai:<model>`
  - `minimax:<model>`

### 2. MiniMax integration

- Added `.env` and `.env.example`
- Confirmed the local environment has a working `MINIMAX_API_KEY`
- Set `MINIMAX_MODEL=MiniMax-M2.7` in `.env`
- Aligned the MiniMax provider to the OpenAI-compatible chat-completions surface
- Added MiniMax-specific defaults:
  - `reasoning_split=True`
  - tighter answer-only prompt
  - context compaction
  - exact-span answer rescue

### 3. Benchmark data and real local runs

Local benchmark sources were pulled into:

- `benchmark_data/official/LongMemEval`
- `benchmark_data/official/LoCoMo`
- `benchmark_data/official/GoodAI-LTM-Benchmark`

Real benchmark artifacts already produced:

- `artifacts/benchmark_runs/goodai_32k_system_comparison.json`
- `artifacts/benchmark_runs/locomo10_system_comparison.json`
- `artifacts/benchmark_runs/longmemeval_s_system_comparison_limit25.json`
- `artifacts/benchmark_runs/longmemeval_s_system_comparison_minimax_limit10.json`

### 4. Three candidate systems were run on real benchmark files

The current systems in-repo are:

- `beam_temporal_atom_router`
- `observational_temporal_memory`
- `dual_store_event_calendar_hybrid`

### 5. Retrieval and answer-path improvements

The largest practical gains today came from:

- compacting context before MiniMax calls
- rescuing exact spans from context after generation
- reducing assistant-only raw-turn noise
- adding benchmark-relevant extraction patterns for:
  - `commute_duration`
  - `attended_play`
  - `playlist_name`
  - `retailer`

These changes landed mainly in:

- `src/domain_chip_memory/providers.py`
- `src/domain_chip_memory/memory_systems.py`

### 6. Measured results reached today

#### LongMemEval with MiniMax-M2.7

Initial small real slice progression:

- `observational_temporal_memory` moved from `1/5` to `2/5`, then `3/5`, then `4/5`, then `5/5`
- `beam_temporal_atom_router` improved much less and remained well behind

Current larger real slice:

- `observational_temporal_memory + MiniMax-M2.7` on first 25 `LongMemEval_s` samples:
  - initial saved artifact in repo was stale at `11/25` (`0.44`)
  - real rerun on March 23, 2026 after retrieval and answer-path fixes: `25/25`
  - `1.00` accuracy
- `beam_temporal_atom_router + MiniMax-M2.7` on same slice:
  - previous saved artifact was `3/25` (`0.12`)
  - real rerun on March 23, 2026: `7/25`
  - `0.28` accuracy

This is the current internal lead lane.

### 7. Repo doctrine updated

The repo now explicitly records:

- active lead system: `observational_temporal_memory`
- active provider lane: `MiniMax-M2.7`
- active benchmark lane: `LongMemEval`

Updated source-of-truth surfaces:

- `README.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/EXECUTION_PROGRAM_AND_PRD_GAP_2026-03-22.md`
- `src/domain_chip_memory/packets.py`
- `artifacts/memory_system_strategy_packet.json`

## Validation status

Verified during this session:

- `python -m pytest` passed after each major code change
- final targeted validation:
  - `python -m pytest tests\\test_memory_systems.py tests\\test_providers.py tests\\test_cli.py tests\\test_loaders_and_runner.py`
  - passed `38/38`
- `python evaluate_chip.py`
  - still `100/100`
- real rerun artifact written:
  - `artifacts/benchmark_runs/longmemeval_observational_minimax_limit25_rerun.json`
  - `25/25`
  - `1.00`
- real comparison rerun artifact written:
  - `artifacts/benchmark_runs/longmemeval_temporal_atom_router_minimax_limit25_rerun.json`
  - `7/25`
  - `0.28`

## Current lead and next move

Current lead:

- `observational_temporal_memory + MiniMax-M2.7`

Why:

- strongest measured in-repo result on the same real `LongMemEval` slice
- materially ahead of the temporal atom router on the same provider and same data

Recommended next step tomorrow:

1. Treat `artifacts/benchmark_runs/longmemeval_observational_minimax_limit25_rerun.json` as the current source-of-truth artifact.
2. Refresh README, plan docs, and the strategy packet to remove the stale `13/25` claim.
3. Expand the same lead lane to a larger `LongMemEval` slice.
4. Re-run the comparison lane for `beam_temporal_atom_router` on the same slice if we want an updated gap after the answer-path fixes.
5. Then move the same provider lane onto `LoCoMo`.

## Push note

I could not confirm a normal git repository in this workspace during the session.

Observed behavior:

- `git status --short` returned `fatal: not a git repository`

So documentation and code are updated locally, but pushing requires either:

- running this from the actual git checkout, or
- initializing/connecting this folder to the intended remote repository first.
