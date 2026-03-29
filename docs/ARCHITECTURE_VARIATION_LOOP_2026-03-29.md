# Architecture Variation Loop - 2026-03-29

## Why this loop exists

Recent `BEAM` runs showed a consistent pattern:

- retrieval sometimes finds relevant evidence
- abstention can receive partial credit
- multi-session synthesis, contradiction handling, temporal reconstruction, and benchmark-grade summarization remain weak

That means the main bottleneck is not raw memory capture alone. The bottleneck is how retrieved memory is reconstructed into answers.

## Patterns borrowed from prior research

The repo's saved research and today's external review point toward the same architectural themes:

- `Chronos`: explicit event-calendar reasoning, temporal retrieval, date-aware reconstruction
- `Supermemory`: typed memory atoms, supersession and update handling, evidence rehydration
- `Mastra` observational memory: stable observation windows plus background reflection
- `A-Mem` and `Mem0`: selective persistence and memory organization rather than naive transcript replay

The common lesson is that good long-memory systems separate:

1. episodic observations
2. structured state or event memory
3. synthesis or answer reconstruction

Our current system already has pieces of all three, but the synthesis layer is still too weak.

## Variation deployed today

### `stateful_event_reconstruction`

This new baseline was added to the runner and CLI as a clean comparison target.

It changes the architecture in four ways:

1. scores the observation window against the question instead of relying only on recency
2. rehydrates top-ranked `EventCalendarEntry` rows back into evidence candidates
3. rebuilds current-state memory from reflections plus event-derived evidence plus observations
4. uses reconstruction-first routing for temporal and summary-shaped questions before generic factoid fallback

## Measured result on BEAM public `128K` first-3 slice

Artifacts:

- scorecard: `artifacts/benchmark_runs/official_beam_128k_stateful_event_reconstruction_heuristic_v1_first3_scorecard.json`
- export: `artifacts/benchmark_runs/official_beam_128k_stateful_event_reconstruction_heuristic_v1_first3_export.json`
- MiniMax summaries:
  - `artifacts/benchmark_runs/official_beam_128k_stateful_event_reconstruction_heuristic_v1_first3_eval_run_conv1_minimax_summary.json`
  - `artifacts/benchmark_runs/official_beam_128k_stateful_event_reconstruction_heuristic_v1_first3_eval_run_conv2_minimax_summary.json`
  - `artifacts/benchmark_runs/official_beam_128k_stateful_event_reconstruction_heuristic_v1_first3_eval_run_conv3_minimax_summary.json`

Observed outcome:

- local exact-match score stayed at `1/60`
- MiniMax only emitted scored `abstention` categories for this slice
- conversation-level MiniMax summaries were:
  - conv `1`: `1.0`
  - conv `2`: `0.5`
  - conv `3`: `0.5`

## What this teaches us

This variant did not solve the real problem.

What improved:

- event memory is now explicitly present in answer construction
- the system produces cleaner provenance for event-based answers

What did not improve:

- contradiction resolution
- knowledge update
- multi-session reasoning
- summarization
- temporal reasoning exactness

The likely reason is that event rehydration is still too close to raw text. We promoted event memory, but we did not yet promote typed state updates and contradiction-aware synthesis strongly enough.

## Next architecture variants to build

### 1. `typed_state_update_memory`

Goal: convert updates and event rows into compact state tuples that prefer canonical values over long raw text.

Expected gain:

- better contradiction handling
- better knowledge updates
- fewer huge benchmark answers copied from raw turns

### 2. `contradiction_aware_profile_memory`

Goal: track superseded vs current claims explicitly and answer contradictions with clarification instead of replay.

Expected gain:

- contradiction resolution
- current-state questions
- benchmark honesty when evidence conflicts

### 3. `summary_synthesis_memory`

Goal: assemble summary answers from multiple typed evidence packets instead of one dominant retrieved passage.

Expected gain:

- summarization
- multi-session reasoning
- instruction-following style benchmark prompts

## Decision

Keep `stateful_event_reconstruction` as an honest checkpoint, but do not treat it as the winning direction. The next serious push should be toward typed update memory and contradiction-aware synthesis.
