# BEAM Official 128K Blocker 2026-03-29

Status: exact official blocker logged, alternate judge lane available

## Exact lane executed

- benchmark: official-public `BEAM`
- scale: `128K` public lane via upstream `100K` directory
- conversation slice: first conversation only (`end_index=1`)
- upstream repo commit: `3e12035532eb85768f1a7cd779832b650c4b2ef9`
- baseline: `observational_temporal_memory`
- provider: `heuristic_v1`
- upstream judge model path: `gpt-4.1-mini` from upstream `src/llm.py`

## What completed successfully

These steps are now proven in-repo on the exact public lane:

1. load official-public upstream chats from `benchmark_data/official/BEAM-upstream/chats`
2. run our baseline on the first `128K` conversation
3. write an official-public scorecard artifact
4. export upstream-style per-conversation answer files
5. validate the upstream evaluator command path

Artifacts produced:

- scorecard: `artifacts/benchmark_runs/official_beam_128k_observational_heuristic_v1_scorecard.json`
- export manifest: `artifacts/benchmark_runs/official_beam_128k_observational_heuristic_v1_export.json`
- evaluator dry-run manifest: `artifacts/benchmark_runs/official_beam_128k_observational_heuristic_v1_eval_run_dry.json`
- evaluator run manifest: `artifacts/benchmark_runs/official_beam_128k_observational_heuristic_v1_eval_run.json`
- exported answers root: `artifacts/beam_public_results/official_beam_128k_observational_heuristic_v1`

## In-repo bridge fixes required to reach the blocker honestly

These were real repo bugs exposed by the first official run attempt:

1. official-public BEAM timestamps can be `None`
2. official-public BEAM dates use `Month-DD-YYYY`
3. scorecard predictions needed top-level `question` text for upstream answer export
4. the upstream evaluator wrapper needed:
   - module invocation via `python -m src.evaluation.run_evaluation`
   - absolute paths for answer roots
   - honest failure status when upstream writes no evaluation files

Those fixes are now covered by regression tests.

## Exact blocker

The first real upstream evaluation call is blocked by judge quota, not by loader/export/wrapper shape anymore.

Observed failure from `artifacts/benchmark_runs/official_beam_128k_observational_heuristic_v1_eval_run.json`:

- upstream stage reached OpenAI judge invocation
- upstream judge returned `429 insufficient_quota`
- no `evaluation-domain_chip_memory_answers.json` file was produced
- wrapper now records this honestly as `status=failed`

The blocker is therefore:

- official-public `BEAM` exact small-lane answer generation works
- official-public `BEAM` exact small-lane upstream evaluation is currently blocked by unavailable OpenAI judge quota

## Alternate explicit judge path completed today

An alternate non-official judge path now exists for the same first-conversation lane.

Judge configuration:

- provider: `minimax`
- model: `MiniMax-M2.7`
- base URL: `https://api.minimax.io/v1`
- comparability: `alternate_openai_compatible_judge_not_exact_official`
- current repo default for `run-beam-official-evaluation`: `minimax`
- exact official OpenAI path remains available only when explicitly requested with `--judge-provider official_openai`

Artifacts produced from the alternate judge path:

- raw evaluation: `artifacts/beam_public_results/official_beam_128k_observational_heuristic_v1/100K/1/evaluation-domain_chip_memory_answers.json`
- summary: `artifacts/benchmark_runs/official_beam_128k_observational_heuristic_v1_eval_run_minimax_summary.json`

Measured alternate-judge result on the first conversation:

- overall average: `0.125`
- `abstention`: `0.0`
- `contradiction_resolution`: `0.25`

This is useful benchmark evidence, but it is not the exact official upstream OpenAI judge path.

## Decision

Do not claim the first official `BEAM` measured score yet.

What is now true:

- the official-public reproduction bridge is working through export
- the upstream evaluator command path is valid
- the exact remaining blocker is official OpenAI judge quota
- an explicit MiniMax alternate judge path can score the same exported answers

What is still not true:

- there is still no exact-official judged `BEAM` score artifact yet

## Next exact move when unblocked

1. restore sufficient OpenAI quota for the upstream judge path or pin a different explicit judge configuration
2. rerun `artifacts/benchmark_runs/official_beam_128k_observational_heuristic_v1_eval_run.json` command
3. summarize the resulting upstream evaluation JSON with `summarize-beam-evaluation`
4. update the active current-state docs with the measured score, not just the blocker

## Next practical move today

1. keep the exact official OpenAI path marked blocked
2. treat the MiniMax run as alternate benchmark evidence, not official comparability
3. move benchmark time into the next `LongMemEval_s` slice, the next clean `LoCoMo` lane, and the first canonical `GoodAI` run
