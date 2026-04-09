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

```powershell
python -m domain_chip_memory.cli beam-judged-promotion-plan --artifact-prefix official_beam_128k_summary_synthesis_memory_heuristic_v1_ --write tmp\beam_128k_promotion_plan_live.json
```

```powershell
python -m domain_chip_memory.cli beam-judged-promotion-batch --artifact-prefix official_beam_128k_summary_synthesis_memory_heuristic_v1_ --script-file tmp\beam_128k_promotion_batch.ps1 --write tmp\beam_128k_promotion_batch.json
```

```powershell
python -m domain_chip_memory.cli beam-judged-drift-plan --artifact-prefix official_beam_128k_summary_synthesis_memory_heuristic_v1_ --write tmp\beam_128k_drift_plan_live.json
```

```powershell
python -m domain_chip_memory.cli beam-judged-drift-batch --artifact-prefix official_beam_128k_summary_synthesis_memory_heuristic_v1_ --script-file tmp\beam_128k_drift_batch.ps1 --write tmp\beam_128k_drift_batch.json
```

## Current State

- answer variant directories found: `22`
- judged evaluation files found: `15`
- tracked modified evaluation drift files: `0`
- official-eval manifests found: `3`
- runnable official-eval manifests: `3`
- blocked official-eval manifests: `0`
- blocked missing env vars: none
- promotable untracked official-eval manifests: `0`
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
  - git status: `clean`
  - classification: `completed`
  - overall average: `0.9517`
  - category count: `10`
  - next pending category: none
- `conv2_v2`
  - git status: `clean`
  - classification: `completed`
  - overall average: `0.9517`
  - category count: `10`
  - next pending category: none
- `conv3_v2`
  - git status: `clean`
  - classification: `completed`
  - overall average: `0.9237`
  - category count: `10`
  - next pending category: none

That means the earlier timeout and partial-coverage state has been cleared and the three official-eval artifacts are now tracked in git.

The promotion helpers were used to promote the exact six intended paths:

- three manifest files
- three sibling evaluation files
- resulting commit: `46f48f7` `Promote completed BEAM 128K official eval artifacts`

The promotion-batch helper is still useful for future artifact promotion:

- `script_file`: `tmp\beam_128k_promotion_batch.ps1`
- `script_line_count`: `8`
- generated `git add -- ...` lines: `3`
- generated targets:
  - `conv1_v9`
  - `conv2_v2`
  - `conv3_v2`
- tracked modified drift files remain excluded from the batch script too

It also now supports `--execute` for the same exact staged path set:

- execution mode runs the generated `git add -- ...` commands sequentially from the repo root
- execution payload reports `return_code`, `status`, `stdout_tail`, and `stderr_tail` per target
- live `--execute` completed successfully with `execution_status_counts: {"completed": 3}`

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

## Drift Resolution

The previously tracked modified file has now been restored to `HEAD`:

- `artifacts/beam_public_results/official_beam_128k_summary_synthesis_memory_heuristic_v1_first20_v3/100K/1/evaluation-domain_chip_memory_answers.json`
  - current git status: `clean`
  - current overall average: `0.9031`
  - drift row no longer present in `modified_evaluation_drift_files`

The new drift-batch helper turns the same plan into one ordered PowerShell script:

- `script_file`: `tmp\beam_128k_drift_batch.ps1`
- `script_line_count`: `7`
- generated live inspection commands:
  - `git diff -- ...`
  - `git show HEAD:...`
- generated restore command remains commented out by default

It now also supports `--execute` for those same safe inspection commands:

- execution mode runs `git diff -- ...` and `git show HEAD:...` sequentially from the repo root
- restore is still not auto-executed
- live `--execute` completed successfully for the single tracked drift target with `execution_status_counts: {"completed": 1}`

## Practical Next Step

The `BEAM 128K` exact-judge cleanup lane is now in a good stopping state:

1. no partial official-eval manifests remain
2. no tracked modified evaluation drift remains
3. the three completed `conv1_v9`, `conv2_v2`, and `conv3_v2` official-eval artifacts are committed

The next clean move is to leave this lane and pivot to a different benchmark or KB task unless new `128K` artifact drift appears.
