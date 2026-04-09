# BEAM 128K Cleanup Report 2026-04-09

This note captures the current exact-judge cleanup surface for the official-public `BEAM 128K` lane without changing any existing benchmark artifacts.

## Command Used

```powershell
python -m domain_chip_memory.cli beam-judged-cleanup-report --artifact-prefix official_beam_128k_summary_synthesis_memory_heuristic_v1_ --write tmp\beam_128k_cleanup_report.json
```

```powershell
python -m domain_chip_memory.cli beam-judged-resume-plan --artifact-prefix official_beam_128k_summary_synthesis_memory_heuristic_v1_ --write tmp\beam_128k_resume_plan.json
```

```powershell
python -m domain_chip_memory.cli beam-judged-resume-batch --artifact-prefix official_beam_128k_summary_synthesis_memory_heuristic_v1_ --script-file tmp\beam_128k_resume_batch.ps1 --write tmp\beam_128k_resume_batch.json
```

```powershell
python -m domain_chip_memory.cli beam-judged-resume-batch --artifact-prefix official_beam_128k_summary_synthesis_memory_heuristic_v1_ --execute --write tmp\beam_128k_resume_batch_execute.json
```

## Current State

- answer variant directories found: `22`
- judged evaluation files found: `15`
- official-eval manifests found: `3`
- scorecards found: `124`
- discovered evaluation-category universe: `10`
  - `abstention`
  - `contradiction_resolution`
  - `event_ordering`
  - `information_extraction`
  - `instruction_following`
  - `knowledge_update`
  - `multi_session_reasoning`
  - `preference_following`
  - `summarization`
  - `temporal_reasoning`
- git status mix across those files:
  - untracked: `27`
  - modified: `1`
  - clean tracked: `114`
- aggregate judged summary across the discovered evaluation files:
  - `overall_average`: `0.8619`
  - `evaluation_file_count`: `15`

## Exact Cleanup Surface

The high-signal exact-judge cleanup files are:

- modified tracked file:
  - `artifacts/beam_public_results/official_beam_128k_summary_synthesis_memory_heuristic_v1_first20_v3/100K/1/evaluation-domain_chip_memory_answers.json`
- untracked judged evaluation files:
  - `artifacts/beam_public_results/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9/100K/1/evaluation-domain_chip_memory_answers.json`
  - `artifacts/beam_public_results/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv2_v2/100K/2/evaluation-domain_chip_memory_answers.json`
  - `artifacts/beam_public_results/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv3_v2/100K/3/evaluation-domain_chip_memory_answers.json`
- untracked official-eval manifests:
  - `artifacts/benchmark_runs/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json`
  - `artifacts/benchmark_runs/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv2_v2_official_eval.json`
  - `artifacts/benchmark_runs/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv3_v2_official_eval.json`

These three untracked exact-judge manifests currently read as `partial`, but each already has one discovered evaluation file and a strong aggregate score:

- `conv1_v9`: `0.9396`
- `conv2_v2`: `0.9396`
- `conv3_v2`: `0.9415`

## Coverage Diagnosis

The new cleanup report now compares each manifest against its own upstream `probing_questions.json` and sibling `domain_chip_memory_answers.json`, so the missing-category diagnosis is per-conversation rather than inferred from a global heuristic.

- `conv1_v9`
  - current classification: `timeout_partial_coverage`
  - stderr tail ends with timeout after `900` seconds
  - expected categories from upstream probing questions: `10`
  - answer categories present in `domain_chip_memory_answers.json`: `10`
  - discovered evaluation categories: `8`
  - missing categories: `summarization`, `temporal_reasoning`
- `conv2_v2`
  - current classification: `timeout_partial_coverage`
  - stderr tail ends with timeout after `900` seconds
  - expected categories from upstream probing questions: `10`
  - answer categories present in `domain_chip_memory_answers.json`: `10`
  - discovered evaluation categories: `8`
  - missing categories: `summarization`, `temporal_reasoning`
- `conv3_v2`
  - current classification: `worker_error_partial_coverage`
  - stderr tail ends with `TypeError: list indices must be integers or slices, not str`
  - expected categories from upstream probing questions: `10`
  - answer categories present in `domain_chip_memory_answers.json`: `10`
  - discovered evaluation categories: `6`
  - missing categories: `multi_session_reasoning`, `preference_following`, `summarization`, `temporal_reasoning`

Current repo status after investigation:

- the resumable openai-compatible evaluator now has explicit regression coverage for list-shaped judge responses in:
  - `multi_session_reasoning`
  - `summarization`
  - `temporal_reasoning`
- that means the recorded `conv3_v2` `TypeError` is not obviously reproducible from today’s rubric-list normalization path
- the remaining uncertainty is whether the historical failure came from an older evaluator revision, a non-list response shape outside the normalized path, or a different category-specific branch before the final four categories were written

## Resume Targets

The cleanup report now exposes ordered per-category progress and the next resume point for each partial manifest:

- `conv1_v9`
  - last completed category: `preference_following`
  - last completed question index: `1`
  - next pending category: `summarization`
  - next pending question index: `0`
- `conv2_v2`
  - last completed category: `preference_following`
  - last completed question index: `1`
  - next pending category: `summarization`
  - next pending question index: `0`
- `conv3_v2`
  - last completed category: `knowledge_update`
  - last completed question index: `1`
  - next pending category: `multi_session_reasoning`
  - next pending question index: `0`
  - last logged worker progress from the historical manifest:
    - category: `multi_session_reasoning`
    - question index: `1`

That `conv3_v2` mismatch between persisted progress and last logged worker progress suggests the failure likely happened while processing `multi_session_reasoning`, before any rows from that category were safely written back to disk.

## Exact Resume Commands

The new resume-plan helper now emits exact rerun commands for the three blocked manifests:

- `conv1_v9`
  ```powershell
  python -m domain_chip_memory.cli run-beam-official-evaluation C:\Users\USER\Desktop\domain-chip-memory\benchmark_data\official\BEAM-upstream C:\Users\USER\Desktop\domain-chip-memory\artifacts\beam_public_results\official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9 --chat-size 128K --result-file-name domain_chip_memory_answers.json --start-index 0 --end-index 1 --max-workers 10 --judge-provider minimax --judge-model MiniMax-M2.7 --judge-base-url https://api.minimax.io/v1 --judge-api-key-env MINIMAX_API_KEY --write artifacts\benchmark_runs\official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json
  ```
- `conv2_v2`
  ```powershell
  python -m domain_chip_memory.cli run-beam-official-evaluation C:\Users\USER\Desktop\domain-chip-memory\benchmark_data\official\BEAM-upstream C:\Users\USER\Desktop\domain-chip-memory\artifacts\beam_public_results\official_beam_128k_summary_synthesis_memory_heuristic_v1_conv2_v2 --chat-size 128K --result-file-name domain_chip_memory_answers.json --start-index 0 --end-index 1 --max-workers 10 --judge-provider minimax --judge-model MiniMax-M2.7 --judge-base-url https://api.minimax.io/v1 --judge-api-key-env MINIMAX_API_KEY --write artifacts\benchmark_runs\official_beam_128k_summary_synthesis_memory_heuristic_v1_conv2_v2_official_eval.json
  ```
- `conv3_v2`
  ```powershell
  python -m domain_chip_memory.cli run-beam-official-evaluation C:\Users\USER\Desktop\domain-chip-memory\benchmark_data\official\BEAM-upstream C:\Users\USER\Desktop\domain-chip-memory\artifacts\beam_public_results\official_beam_128k_summary_synthesis_memory_heuristic_v1_conv3_v2 --chat-size 128K --result-file-name domain_chip_memory_answers.json --start-index 0 --end-index 1 --max-workers 10 --judge-provider minimax --judge-model MiniMax-M2.7 --judge-base-url https://api.minimax.io/v1 --judge-api-key-env MINIMAX_API_KEY --write artifacts\benchmark_runs\official_beam_128k_summary_synthesis_memory_heuristic_v1_conv3_v2_official_eval.json
  ```

## Batch Wrapper

The new batch helper writes one ordered PowerShell script for the current partial set:

- generated script path: `tmp\beam_128k_resume_batch.ps1`
- current script order:
  1. `conv1_v9`
  2. `conv2_v2`
  3. `conv3_v2`

That keeps the two timeout-bound resumptions ahead of the historically noisier `conv3_v2` rerun.

The helper now also supports direct execution:

- `--execute` runs the generated resume commands sequentially from the repo root
- the JSON output captures per-target `return_code`, `status`, `stdout_tail`, and `stderr_tail`
- `--execute` now preflights the configured judge API key env var before spawning a rerun command
- current shell state: `MINIMAX_API_KEY` is unset
- live runtime result from the batch builder in the current shell:
  - `conv1_v9`: `blocked_missing_env`
  - `conv2_v2`: `blocked_missing_env`
  - `conv3_v2`: `blocked_missing_env`
- that means the helper now fails cleanly instead of launching doomed `MiniMax` reruns when the judge key is absent, and the worktree remains free of any new judged-output churn from this helper

The previously modified tracked file also appears materially incomplete relative to the current `128K` category universe:

- `first20_v3/100K/1/evaluation-domain_chip_memory_answers.json`
  - git status: `modified`
  - current categories: `abstention`, `contradiction_resolution`, `event_ordering`, `information_extraction`
  - current overall average: `0.7322`
  - `HEAD` versus working-tree category averages:
    - `abstention`: `1.0` -> `1.0`
    - `contradiction_resolution`: `0.75` -> `0.75`
    - `event_ordering`: `0.8622` -> `0.1789`
    - `information_extraction`: `1.0` -> `1.0`
  - the tracked diff is therefore not just judge-reason wording churn; it materially changes `event_ordering`

## Local Scorecard Noise

Most of the `124` scorecards are already clean tracked history.
The untracked scorecard noise is mostly older or superseded local variants such as:

- `conv10_v1` through `conv20_v2`
- `conv4_v1`
- `conv6_v1` through `conv9_v1`
- extra predecessor variants around `conv16_v2` through `conv20_v2`

The currently promoted clean tracked line is still visible beside those files:

- `conv10_v2`
- `conv11_v2`
- `conv12_v2`
- `conv13_v2`
- `conv14_v2`
- `conv15_v2`
- `conv16_v3`
- `conv17_v3`
- `conv18_v3`
- `conv19_v3`
- `conv20_v3`

## Recommendation

The next disciplined cleanup move should be:

1. treat all three untracked `conv1_v9` to `conv3_v2` official-eval manifests as blocked partials, not ready-to-promote completions
   - `conv1_v9` and `conv2_v2` are timeout-bound partials still missing `summarization` and `temporal_reasoning`
   - `conv3_v2` is a real worker-error partial with a `TypeError` before the last four categories complete
2. decide whether the modified tracked `first20_v3/100K/1/evaluation-domain_chip_memory_answers.json` is intentional, because it is currently only a `4`-category partial against the discovered `10`-category universe and its `event_ordering` average dropped from `0.8622` at `HEAD` to `0.1789` in the working tree
3. only stage judged `128K` artifacts after there is a deliberate decision about missing `summarization` / `temporal_reasoning` coverage and the `conv3_v2` worker `TypeError`
4. leave the untracked predecessor local scorecards alone unless there is a separate promotion or deletion decision for them

This keeps the cleanup lane focused on exact judged evidence instead of mixing it with local scorecard churn.
