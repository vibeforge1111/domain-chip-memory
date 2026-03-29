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

Follow-up patch on `2026-03-30`:

- narrowed `summary_synthesis_memory` answer routing to use a focused update-aware extractor for:
  - date questions
  - updated numeric/count questions
  - project-card count questions
- added targeted regressions covering:
  - focus-aligned first-sprint date selection
  - updated project-card count selection
  - existing updated numeric answer selection

Follow-up result:

- targeted tests passed:
  - `python -m pytest tests/test_cli.py tests/test_memory_systems.py -k "summary_synthesis_memory or summary_synthesis_answer_candidate or contract_summary_exists or run_beam_public_cli_can_write_scorecard"`
  - result: `10 passed`
- reran the same local `BEAM` public `128K` first-3 slice twice:
  - `artifacts/benchmark_runs/official_beam_128k_summary_synthesis_memory_heuristic_v1_first3_v2_scorecard.json`
  - `artifacts/benchmark_runs/official_beam_128k_summary_synthesis_memory_heuristic_v1_first3_v3_scorecard.json`
- honest outcome: still `3/60`

What changed without moving the score:

- the deadline miss for conversation `3` narrowed from a clearly unrelated later date (`May 10, 2024`) to the original first-sprint date (`April 1, 2024`)
- this suggests the focused extractor is helping with topic alignment, but the system still does not reliably surface the superseding update on the real benchmark slice

Decision after the follow-up patch:

- keep the patch because it improves targeted behavior and preserves the current leader
- do not treat it as a benchmark win
- the next high-signal move is no longer generic update extraction
- the next move should target one of these explicitly:
  - benchmark-aligned abstention phrasing for official-public `BEAM`
  - contradiction-only routing with rubric-shaped clarifier text
  - temporal reasoning that computes from two extracted dates instead of replaying one numeric token

Second follow-up patch on `2026-03-30`:

- kept `summary_synthesis_memory` as the active leader branch
- added contradiction-specific answer routing inside `summary_synthesis_memory`
- added question-aligned contradiction claim extraction and second-person claim rewriting in the runtime layer
- added contradiction-specific retrieval shaping in `summary_synthesis_memory` packets so contradiction questions explicitly pull top negated and affirmative raw claims into the packet
- added targeted regressions covering:
  - summary-synthesis contradiction clarification on long mixed prompts
  - contradiction-aware preference for assertive bug-fix claims over help-request text
  - summary-synthesis packet preference for homepage-route evidence over tutorial noise

Second follow-up result:

- targeted tests passed:
  - `python -m pytest tests/test_cli.py tests/test_memory_systems.py -k "summary_synthesis_memory or contradiction or contract_summary_exists or run_beam_public_cli_can_write_scorecard"`
  - result: `13 passed`
- reran the same local `BEAM` public `128K` first-3 slice:
  - `artifacts/benchmark_runs/official_beam_128k_summary_synthesis_memory_heuristic_v1_first3_v4_scorecard.json`
  - `artifacts/benchmark_runs/official_beam_128k_summary_synthesis_memory_heuristic_v1_first3_v5_scorecard.json`
- honest outcome: still `3/60`

What changed without moving the score:

- contradiction answers changed shape and now more reliably emit clarification-style outputs from the `summary_synthesis_memory` path instead of generic synthesis passages
- retrieved aggregate items for contradiction questions increased because contradiction-specific raw claims are now being injected into the packet
- despite that, the real benchmark still selects nearby development-context claims instead of the exact contradictory self-claims the rubric expects
- examples from `v5`:
  - `1:contradiction_resolution:3` paired `you are using Flask 2.3.1` against the negated route claim instead of the stronger `basic homepage route with Flask` evidence
  - `1:contradiction_resolution:4` still paired two help-seeking session-management claims rather than the true integrated-vs-never-integrated contradiction
  - `2:contradiction_resolution:4` still surfaced autocomplete implementation/error-handling instead of the stronger null-check bug-fix evidence

Decision after the second follow-up patch:

- keep the retrieval-shaping patch because it improves the internal path and regression coverage
- do not count it as a benchmark win; the score stayed flat
- the next real move should happen earlier than answer phrasing:
  - extract contradiction-ready claim atoms from raw turns instead of relying on fallback raw-turn summaries
  - type claims as `negated`, `implemented`, `integrated`, `fixed`, `obtained`, `updated`
  - let contradiction retrieval ask for one negated typed claim and one affirmative typed claim before synthesis
  - separately attack `knowledge_update` and `temporal_reasoning`, because those two categories are still limiting the leader almost as much as contradiction resolution

### 4. `contradiction_aware_summary_synthesis_memory`

Goal: merge the contradiction-aware pairing path with synthesis-first answer construction so the system can both clarify conflicts and keep direct update answers concise.

Expected gain:

- contradiction resolution
- knowledge updates
- preserve the small synthesis gains from `summary_synthesis_memory`

Result after implementation:

- baseline added as `contradiction_aware_summary_synthesis_memory`
- local `BEAM` public `128K` first-3 slice scored `2/60`
- this is worse than:
  - `summary_synthesis_memory`: `3/60`
- but still above:
  - `typed_state_update_memory`: `0/60`

Artifact:

- scorecard: `artifacts/benchmark_runs/official_beam_128k_contradiction_aware_summary_synthesis_memory_heuristic_v1_first3_scorecard.json`

What improved:

- targeted unit tests now show better question-aligned contradiction pair selection than the earlier contradiction-only branch
- targeted unit tests also show better deadline disambiguation when unrelated later dates are present

What failed:

- full `BEAM` performance regressed because contradiction and synthesis signals started polluting unrelated answer selection
- contradiction questions still failed local exact-match despite cleaner internal pairing, which means benchmark wording remains too brittle for the current clarifier
- update-aware extraction still picked the wrong evidence on real slices often enough that the local gains did not survive benchmark scale

Decision:

- keep this branch in the repo as a failed combination experiment
- do not promote it over `summary_synthesis_memory`
- the next move should be narrower, not broader:
  - keep contradiction handling isolated to contradiction questions only
  - improve update disambiguation without injecting contradiction context into non-contradiction prompts
  - treat abstention alignment as its own answer-layer problem instead of bundling it into another large memory variant
