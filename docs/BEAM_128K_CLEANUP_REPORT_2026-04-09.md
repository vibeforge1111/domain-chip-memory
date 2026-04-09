# BEAM 128K Cleanup Report 2026-04-09

This note captures the current exact-judge cleanup surface for the official-public `BEAM 128K` lane as of April 9, 2026.

## Commands Used

```powershell
python -m domain_chip_memory.cli beam-judged-cleanup-report --artifact-prefix official_beam_128k_summary_synthesis_memory_heuristic_v1_ --write tmp\beam_128k_cleanup_report_live.json
```

```powershell
python -m domain_chip_memory.cli beam-judged-resume-plan --artifact-prefix official_beam_128k_summary_synthesis_memory_heuristic_v1_ --write tmp\beam_128k_resume_plan_live_full.json
```

```powershell
python -m domain_chip_memory.cli beam-judged-resume-batch --artifact-prefix official_beam_128k_summary_synthesis_memory_heuristic_v1_ --only-runnable --write tmp\beam_128k_resume_batch_only_runnable_live.json
```

## Current State

- answer variant directories found: `22`
- judged evaluation files found: `15`
- tracked modified evaluation drift files: `1`
- official-eval manifests found: `3`
- runnable official-eval manifests: `3`
- blocked official-eval manifests: `0`
- blocked missing env vars: none
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

## Official Eval Manifests

All three live `128K` official-eval manifests are now `completed`.

- `conv1_v9`
  - git status: `??`
  - classification: `completed`
  - overall average: `0.9517`
  - category count: `10`
  - next pending category: none
- `conv2_v2`
  - git status: `??`
  - classification: `completed`
  - overall average: `0.9517`
  - category count: `10`
  - next pending category: none
- `conv3_v2`
  - git status: `??`
  - classification: `completed`
  - overall average: `0.9237`
  - category count: `10`
  - next pending category: none

That means the earlier timeout and partial-coverage state has been cleared in the working tree artifacts.

## Resume Surface

There are currently no partial manifests left to resume.

- `beam-judged-resume-plan`
  - `only_runnable`: `false`
  - `discovered_target_count`: `0`
  - `resume_target_count`: `0`
  - `filtered_out_target_count`: `0`
  - `runnable_target_count`: `0`
  - `blocked_target_count`: `0`
- `beam-judged-resume-batch --only-runnable`
  - `discovered_target_count`: `0`
  - `resume_target_count`: `0`
  - generated script contains only the PowerShell header comment
  - `executed_target_count`: `0`

The new `--only-runnable` flag is still useful for future partial states because it can emit only env-ready reruns, but on the live `128K` lane today it correctly collapses to an empty plan.

## Remaining Cleanup Question

The main unresolved cleanup item is no longer the three `conv*_official_eval.json` manifests. It is the tracked modified file:

- `artifacts/beam_public_results/official_beam_128k_summary_synthesis_memory_heuristic_v1_first20_v3/100K/1/evaluation-domain_chip_memory_answers.json`
  - git status: `M`
  - drift row present in `modified_evaluation_drift_files`
  - current category count: `4`
  - `HEAD` category count: `4`
  - current overall average: `0.7322`
  - `HEAD` overall average: `0.9031`
  - overall average delta: `-0.1709`
  - changed category count: `1`
  - `event_ordering` average at `HEAD`: `0.8622`
  - `event_ordering` average in working tree: `0.1789`
  - `event_ordering` average delta: `-0.6833`

That is still substantive drift, not judge-reason wording churn.

## Practical Next Step

The clean next move is:

1. treat `conv1_v9`, `conv2_v2`, and `conv3_v2` as completed working-tree artifacts rather than blocked resume targets
2. decide whether to promote, ignore, or discard those untracked completed `official_eval` artifacts
3. separately investigate the tracked `first20_v3/100K/1` drift before staging any `128K` evaluation file changes
