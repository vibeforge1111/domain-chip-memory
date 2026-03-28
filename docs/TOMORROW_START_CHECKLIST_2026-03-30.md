# Tomorrow Start Checklist 2026-03-30

Status: next-start

## Read First

1. [Memory System Honest Assessment](/C:/Users/USER/Desktop/domain-chip-memory/docs/MEMORY_SYSTEM_HONEST_ASSESSMENT_2026-03-29.md)
2. [Implementation Plan](/C:/Users/USER/Desktop/domain-chip-memory/docs/IMPLEMENTATION_PLAN.md)
3. [Current Test And Validation Plan](/C:/Users/USER/Desktop/domain-chip-memory/docs/CURRENT_TEST_AND_VALIDATION_PLAN_2026-03-29.md)
4. [BEAM Official Reproduction Plan](/C:/Users/USER/Desktop/domain-chip-memory/docs/BEAM_OFFICIAL_REPRODUCTION_PLAN_2026-03-29.md)
5. [BEAM Implementation Gap Map](/C:/Users/USER/Desktop/domain-chip-memory/docs/BEAM_IMPLEMENTATION_GAP_MAP_2026-03-29.md)
6. [Session Log 2026-03-29](/C:/Users/USER/Desktop/domain-chip-memory/docs/SESSION_LOG_2026-03-29.md)

## First Goal

Run the first exact small official-public `BEAM` lane and pin the result honestly.

That means:

- use the pinned upstream repo commit
- use the official-public chats layout
- run our baseline on that lane
- export upstream-style answers
- run the upstream evaluator through the new wrapper
- save the result artifact and judge configuration

## Exact First Steps

1. Confirm the upstream repo checkout is at the pinned commit.
2. Confirm the chats directory exists for the exact scale being tested.
3. Run one small official-public `BEAM` baseline lane.
4. Export answers with `export-beam-public-answers`.
5. Invoke `run-beam-official-evaluation`.
6. Summarize the evaluation JSON with `summarize-beam-evaluation`.
7. Save the measured artifact under `artifacts/benchmark_runs/`.
8. Update the active docs with the measured result, not a verbal claim.

## If BEAM Blocks

If the official run is blocked by judge config, upstream layout mismatch, or missing public chats:

1. document the exact blocker
2. stop broadening `BEAM`
3. extend the next honest `LongMemEval_s` slice
4. choose the next clean `LoCoMo` lane

## Tomorrow Success Condition

Tomorrow is successful if one of these happens:

- we land the first exact small official-public `BEAM` measured artifact
- or we produce a precise blocker log and move the time into `LongMemEval_s` plus `LoCoMo` instead of hand-waving about `BEAM`

