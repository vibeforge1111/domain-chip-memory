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

Result after implementation:

- baseline added as `typed_state_update_memory`
- local `BEAM` public `128K` first-3 slice scored `0/60`
- this is worse than both:
  - `observational_temporal_memory`: `1/60`
  - `stateful_event_reconstruction`: `1/60`

What failed:

- compact typed updates became over-dominant and repeated generic high-level preference or summary fragments
- contradiction handling did not improve
- temporal or multi-session reconstruction did not improve

Decision:

- keep the variant in the repo as a failed but informative experiment
- do not spend MiniMax judge cycles on it until retrieval and routing are narrowed enough to stop generic typed updates from dominating unrelated questions

### 2. `contradiction_aware_profile_memory`

Goal: track superseded vs current claims explicitly and answer contradictions with clarification instead of replay.

Expected gain:

- contradiction resolution
- current-state questions
- benchmark honesty when evidence conflicts

Result after implementation:

- baseline added as `contradiction_aware_profile_memory`
- local `BEAM` public `128K` first-3 slice scored `1/60`
- that ties:
  - `observational_temporal_memory`: `1/60`
  - `stateful_event_reconstruction`: `1/60`
- contradiction answers are qualitatively closer to benchmark intent because they now produce clarification-style responses instead of picking one side outright

MiniMax judged status:

- raw eval files were produced
- the resulting summaries only populated `abstention` for conversations `1-3`
- judged summaries therefore remain incomplete and cannot be treated as a full-category improvement signal

Decision:

- keep this branch as a partial win in answer behavior, but not yet a measured score win
- if we revisit it, the next refinement should narrow contradiction pairing so the clarifier selects the actual conflicting claim pair rather than merely any negated-versus-affirmative high-overlap pair

### 3. `summary_synthesis_memory`

Goal: assemble summary answers from multiple typed evidence packets instead of one dominant retrieved passage.

Expected gain:

- summarization
- multi-session reasoning
- instruction-following style benchmark prompts

Result after implementation:

- baseline added as `summary_synthesis_memory`
- local `BEAM` public `128K` first-3 slice scored `3/60`
- this beats:
  - `observational_temporal_memory`: `1/60`
  - `stateful_event_reconstruction`: `1/60`
  - `typed_state_update_memory`: `0/60`
  - `contradiction_aware_profile_memory`: `1/60`

Artifact:

- scorecard: `artifacts/benchmark_runs/official_beam_128k_summary_synthesis_memory_heuristic_v1_first3_scorecard.json`

What improved:

- direct answer synthesis got cleaner for some extraction/update-shaped questions
- the variant recovered an extra multi-session count question instead of only one isolated extraction hit
- retrieved context now consistently surfaces aggregate-role synthesis support instead of only raw replay

What did not improve:

- contradiction handling still needs the contradiction-aware path, not just synthesis
- event ordering summaries are still too literal and too close to raw turns
- abstention remains benchmark-misaligned because `unknown` still does not match the official abstention phrasing
- knowledge-update questions still drift when multiple dates or counts are present and the synthesis layer picks the wrong updated fact

Decision:

- keep `summary_synthesis_memory` as the current local leader on the first `BEAM` public first-3 slice
- do not call it good enough yet; the gain is real but still small
- the next serious move should combine:
  - contradiction-aware claim pairing from `contradiction_aware_profile_memory`
  - synthesis-first answer routing from `summary_synthesis_memory`
  - stronger update disambiguation so later facts beat earlier ones without needing question-specific fallback rules
