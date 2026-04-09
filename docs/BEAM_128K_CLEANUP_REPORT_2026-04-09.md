# BEAM 128K Cleanup Report 2026-04-09

This note captures the current exact-judge cleanup surface for the official-public `BEAM 128K` lane without changing any existing benchmark artifacts.

## Command Used

```powershell
python -m domain_chip_memory.cli beam-judged-cleanup-report --artifact-prefix official_beam_128k_summary_synthesis_memory_heuristic_v1_ --write tmp\beam_128k_cleanup_report.json
```

## Current State

- answer variant directories found: `22`
- judged evaluation files found: `15`
- official-eval manifests found: `3`
- scorecards found: `124`
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

1. decide whether the modified tracked `first20_v3/100K/1/evaluation-domain_chip_memory_answers.json` is intentional
2. if it is intentional, stage it explicitly with the three untracked exact-judge eval files and the three matching official-eval manifests
3. leave the untracked predecessor local scorecards alone unless there is a separate promotion or deletion decision for them

This keeps the cleanup lane focused on exact judged evidence instead of mixing it with local scorecard churn.
