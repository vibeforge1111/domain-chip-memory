# Tomorrow Start Checklist 2026-03-31

Status: next-start

## Read First

1. [Session Log 2026-03-30](/<domain-chip-memory>/docs/SESSION_LOG_2026-03-30.md)
2. [Architecture Variation Loop 2026-03-29](/<domain-chip-memory>/docs/ARCHITECTURE_VARIATION_LOOP_2026-03-29.md)
3. [Memory System Honest Assessment](/<domain-chip-memory>/docs/MEMORY_SYSTEM_HONEST_ASSESSMENT_2026-03-29.md)
4. [Current Test And Validation Plan](/<domain-chip-memory>/docs/CURRENT_TEST_AND_VALIDATION_PLAN_2026-03-29.md)
5. [Implementation Plan](/<domain-chip-memory>/docs/IMPLEMENTATION_PLAN.md)

## First Goal

Move the current `summary_synthesis_memory` leader on the same public `BEAM` first-3 slice without regressing the gains already won in:

- `abstention`
- `contradiction_resolution`
- `knowledge_update`
- `temporal_reasoning`

## Exact Starting Point

Current leader:

- [official_beam_128k_summary_synthesis_memory_heuristic_v1_first3_v24_scorecard.json](/<domain-chip-memory>/artifacts/benchmark_runs/official_beam_128k_summary_synthesis_memory_heuristic_v1_first3_v24_scorecard.json)

Current headline score:

- `23/60`

Current category profile:

- `abstention = 6/6`
- `contradiction_resolution = 6/6`
- `knowledge_update = 4/6`
- `temporal_reasoning = 4/6`
- `information_extraction = 2/6`
- `multi_session_reasoning = 1/6`
- `event_ordering = 0/6`
- `instruction_following = 0/6`
- `preference_following = 0/6`
- `summarization = 0/6`

## Tomorrow Priorities

1. Instrument the exact remaining misses in:
   - `event_ordering`
   - `summarization`
   - `instruction_following`
   - `multi_session_reasoning`

2. Prefer narrow answer-routing or evidence-selection mutations over another broad baseline rewrite.

3. After each mutation:
   - run targeted tests
   - rerun the public `BEAM` first-3 slice
   - keep only score-improving or clearly architecture-revealing changes

4. Keep committing frequently.

5. If the first-3 score improves again, extend the leader to a broader `BEAM` lane before branching back into other benchmarks.

## If The First Loop Stalls

If the next few focused mutations do not move the score:

1. stop local thrashing
2. inspect exact miss patterns question by question
3. compare the weak categories against the saved research and external memory-system patterns
4. then choose one new architecture direction specifically for:
   - event sequencing
   - multi-session summarization
   - benchmark-shaped instruction following

## Tomorrow Success Condition

Tomorrow is successful if one of these happens:

- the current leader moves above `23/60` on the same honest `BEAM` first-3 slice
- or we produce a clear miss taxonomy for `event_ordering`, `summarization`, `instruction_following`, and `multi_session_reasoning` that makes the next mutation choice obvious
