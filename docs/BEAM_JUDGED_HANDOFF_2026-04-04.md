# BEAM Judged Handoff

This is the exact handoff for the MiniMax-judged BEAM official-public continuation as of 2026-04-04.

## Goal

Finish the judged BEAM `500K` exports conversation block by conversation block, committing each completed phase cleanly, then continue through the remaining `500K`, `1M`, and `10M` judged roots.

## What Landed Today

Committed on `main`:

- `9605135` `Normalize list-shaped BEAM judge responses`
- `eef8157` `Handle nested BEAM judge score payloads`
- `87f368a` `Commit BEAM 500K conv6-10 judged results`

These were real worker-hardening changes in:

- `src/domain_chip_memory/beam_official_eval.py`
- `tests/test_cli.py`

Focused verification that passed:

```bash
python -m pytest tests\test_cli.py -k "beam_official_evaluation_cli or openai_compatible_upstream_evaluation or sets_request_timeout_and_retries or resume_openai_compatible_single_conversation"
```

## Confirmed Finished Judged Phases

`500K conv1-5` is finished and committed:

- commit: `08883f3`
- manifest:
  - `artifacts/benchmark_runs/official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5_v7_official_eval.json`

`500K conv6-10` is finished and committed:

- commit: `87f368a`
- manifest:
  - `artifacts/benchmark_runs/official_beam_500k_summary_synthesis_memory_heuristic_v1_conv6_10_v1_official_eval.json`

Current judged aggregate for `500K conv6-10`:

- `status=completed`
- `exit_code=0`
- `overall_average=0.7094`

## Current Honest Frontier

Active judged root:

- `artifacts/beam_public_results/official_beam_500k_summary_synthesis_memory_heuristic_v1_conv11_15_v1`

Live status at stop:

- `500K/11`: started and advanced to 10/10 categories in
  - `artifacts/beam_public_results/official_beam_500k_summary_synthesis_memory_heuristic_v1_conv11_15_v1/500K/11/evaluation-domain_chip_memory_answers.json`
- `500K/12`: started and currently has 2 categories in
  - `artifacts/beam_public_results/official_beam_500k_summary_synthesis_memory_heuristic_v1_conv11_15_v1/500K/12/evaluation-domain_chip_memory_answers.json`
- `500K/13-15`: not started yet

The main manifest for this phase is still in-progress:

- `artifacts/benchmark_runs/official_beam_500k_summary_synthesis_memory_heuristic_v1_conv11_15_v1_official_eval.json`

That manifest should not be committed until the full `conv11-15` root finishes cleanly.

## Exact Next Step Tomorrow

Resume the same judged phase:

```powershell
$env:MINIMAX_API_KEY = "<set key in shell>"
python -m domain_chip_memory.cli run-beam-official-evaluation `
  benchmark_data/official/BEAM-upstream `
  artifacts/beam_public_results/official_beam_500k_summary_synthesis_memory_heuristic_v1_conv11_15_v1 `
  --chat-size 500K `
  --max-workers 1 `
  --write artifacts/benchmark_runs/official_beam_500k_summary_synthesis_memory_heuristic_v1_conv11_15_v1_official_eval.json
```

Important:

- keep `--max-workers 1`
- keep using the resumable path
- do not delete partial `evaluation-domain_chip_memory_answers.json` files

## Commit Rule For Tomorrow

When `conv11-15` finishes cleanly:

1. Stage only:
   - `artifacts/benchmark_runs/official_beam_500k_summary_synthesis_memory_heuristic_v1_conv11_15_v1_official_eval.json`
   - the five `evaluation-domain_chip_memory_answers.json` files under `500K/11` through `500K/15`
2. Commit with:

```bash
git commit -m "Commit BEAM 500K conv11-15 judged results"
```

Then open `500K conv16-20` on the same judged path.

## Known Repo State To Avoid Touching

There are unrelated dirty tracked files and many unrelated untracked benchmark/debug artifacts in the worktree. They were not part of this judged-run work and should stay untouched unless explicitly addressed.

The note above is the real restart point.
