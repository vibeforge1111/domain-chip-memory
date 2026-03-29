# Today Plan - 2026-03-29

Status: active execution plan

## Date note

The current environment date is 2026-03-29.

This document turns the current state of the repo into one visible execution plan for today.
It should be read together with:

- [Memory System Honest Assessment](MEMORY_SYSTEM_HONEST_ASSESSMENT_2026-03-29.md)
- [Current Test And Validation Plan](CURRENT_TEST_AND_VALIDATION_PLAN_2026-03-29.md)
- [BEAM Official 128K Blocker 2026-03-29](BEAM_OFFICIAL_128K_BLOCKER_2026-03-29.md)

## What Is Already True Today

- the first exact official-public `BEAM` `128K` lane was executed on the first public conversation
- the official-public bridge now works through:
  - loader
  - baseline run
  - scorecard artifact
  - upstream-style answer export
  - upstream evaluator wrapper validation
- the remaining exact-official `BEAM` blocker is no longer repo shape
- the remaining exact-official `BEAM` blocker is upstream judge quota:
  - OpenAI `429 insufficient_quota`
- the same lane now also has an alternate explicit MiniMax judged result:
  - evaluation file: `artifacts/beam_public_results/official_beam_128k_observational_heuristic_v1/100K/1/evaluation-domain_chip_memory_answers.json`
  - summary file: `artifacts/benchmark_runs/official_beam_128k_observational_heuristic_v1_eval_run_minimax_summary.json`
  - default BEAM eval CLI judge: `minimax`
  - summary score: `overall_average = 0.125`

## Today's Test Plan

### 1. Keep the official `BEAM` result honest

Required visible artifacts already exist:

- `artifacts/benchmark_runs/official_beam_128k_observational_heuristic_v1_scorecard.json`
- `artifacts/benchmark_runs/official_beam_128k_observational_heuristic_v1_export.json`
- `artifacts/benchmark_runs/official_beam_128k_observational_heuristic_v1_eval_run.json`
- `artifacts/beam_public_results/official_beam_128k_observational_heuristic_v1/100K/1/evaluation-domain_chip_memory_answers.json`
- `artifacts/benchmark_runs/official_beam_128k_observational_heuristic_v1_eval_run_minimax_summary.json`

Today's test rules:

- do not claim an exact-official judged `BEAM` score until the upstream OpenAI path produces real `evaluation-*.json` files
- do treat the MiniMax result as alternate explicit judge evidence, not exact-official comparability

### 2. Re-open the exact official `BEAM` judged lane only if quota is available

If upstream judge quota is restored today:

1. rerun the exact single-conversation `128K` evaluator command
2. run `summarize-beam-evaluation`
3. write the judged artifact back into `artifacts/benchmark_runs/`
4. update the active docs with the measured score

### 3. Since the exact official path is still blocked, move immediately to the next honest benchmark work

Do not spend the day hand-waving about `BEAM`.

The alternate MiniMax run is enough to stop treating the lane as unjudged, but it is not enough to close the exact-official benchmark question.

Instead:

1. extend the next `LongMemEval_s` slice
2. choose the next clean `LoCoMo` lane
3. lock the first canonical `GoodAI` run

### 4. Preserve the safety gates on every real mutation

After every behavior mutation, rerun:

- relevant targeted `pytest` coverage
- local `ProductMemory` gates when memory behavior changes
- the affected benchmark lane

## Execution Priority For Today

1. restore the exact-official OpenAI `BEAM` judge path if that is feasible today
2. otherwise spend the remaining benchmark time on:
   - `LongMemEval_s`
   - clean `LoCoMo`
   - canonical `GoodAI`
3. after benchmark movement, add direct runtime metric capture to serious artifacts

## What We Should Do Next

### Next if we want the shortest path to official `BEAM`

- make the upstream judge runnable:
  - restore OpenAI quota
  - keep the MiniMax lane explicit and separate, but do not relabel it as official

### Next if `BEAM` remains blocked

- run the next honest `LongMemEval_s` extension
- pick the next clean `LoCoMo` slice
- run the first canonical `GoodAI` lane

### Next architecture-quality task after benchmark movement

- add direct runtime metric capture into serious comparison artifacts:
  - p50 latency
  - p95 latency
  - prompt tokens
  - total tokens
  - memory growth

## Success Condition For Today

Today is successful if one of these happens:

1. we land the first exact-official judged official-public `BEAM` `128K` artifact
2. or we keep `BEAM` honestly blocked and move the day into:
   - the next `LongMemEval_s` slice
   - the next clean `LoCoMo` lane
   - the first canonical `GoodAI` run
