# BEAM Implementation Gap Map 2026-03-29

Status: active

## Purpose

This file answers one practical question:

- what is the difference between our current in-repo `BEAM` support and a real official `BEAM` reproduction path

## Current in-repo support

What we already have:

- `BEAMAdapter.normalize_instance` in [adapters.py](/C:/Users/USER/Desktop/domain-chip-memory/src/domain_chip_memory/adapters.py)
- `load_beam_json` in [loaders.py](/C:/Users/USER/Desktop/domain-chip-memory/src/domain_chip_memory/loaders.py)
- `run-beam-baseline` in [cli.py](/C:/Users/USER/Desktop/domain-chip-memory/src/domain_chip_memory/cli.py)
- `BEAM` scorecard handling in [scorecards.py](/C:/Users/USER/Desktop/domain-chip-memory/src/domain_chip_memory/scorecards.py)
- local regression tests in [tests/test_adapters.py](/C:/Users/USER/Desktop/domain-chip-memory/tests/test_adapters.py) and [tests/test_cli.py](/C:/Users/USER/Desktop/domain-chip-memory/tests/test_cli.py)

What that support actually means:

- we can run our baselines over an internal normalized `BEAM`-shaped JSON slice
- we can score that slice with our own scorecard contract
- we can use the local pilot lane as a fast regression benchmark

What it does not mean:

- we do not yet ingest the official upstream `BEAM` dataset shape directly
- we do not yet reproduce the official upstream answer-generation flow
- we do not yet reproduce the official upstream evaluation flow
- we do not yet have one command that can honestly claim `official BEAM reproduction`

## Official upstream surface

Pinned upstream source:

- repo: `https://github.com/mohammadtavakoli78/BEAM`
- commit: `3e12035532eb85768f1a7cd779832b650c4b2ef9`

Relevant upstream paths at that commit:

- dataset download: `src/beam/download_dataset.py`
- dataset pipeline: `src/beam/run_pipeline.sh`
- answer generation: `src/answer_probing_questions/answer_generation.sh`
- LIGHT reference: `src/answer_probing_questions/light.py`
- evaluation: `src/evaluation/run_evaluation.py`
- reporting: `src/evaluation/report_results.py`

## Exact gap

### Gap 1: Official data ingestion

Current:

- `load_beam_json` expects a local JSON list of already-normalized slice instances

Missing:

- loader path for official public `BEAM` dataset objects
- loader path for official public `BEAM-10M` dataset objects
- normalization of official conversation, profile, seed, and probing-question structures into our contracts
- explicit scale metadata for `128K`, `500K`, `1M`, and `10M`

### Gap 2: Official answer-generation contract

Current:

- our runner calls our own baselines directly against normalized samples

Missing:

- exact mapping from our baselines to the official upstream answer-generation interface
- commit-pinned documentation for upstream environment variables and result file naming
- clear distinction between:
  - our native baselines on official BEAM data
  - exact reproduction of upstream LIGHT or baseline flows

### Gap 3: Official evaluation contract

Current:

- our scorecard contract measures correctness inside our own benchmark substrate

Missing:

- explicit wrapper or replay path around upstream `run_evaluation.py`
- pinned judge settings used by the official evaluation path
- mapping from upstream evaluation outputs into our scorecard fields
- explicit policy for comparing our scores against upstream reported numbers

### Gap 4: One honest CLI path

Current:

- `run-beam-baseline` means `run our baseline on a local BEAM-style slice`

Missing:

- a separate command for official public `BEAM` ingestion
- a separate command for official public `BEAM` reproduction
- command naming that makes it impossible to confuse:
  - internal local pilot
  - official public reproduction

### Gap 5: Reproducible artifact contract

Current:

- local `BEAM` artifacts live under `artifacts/benchmark_runs/beam_local_pilot_*`

Missing:

- one official artifact naming scheme
- one manifest field for upstream commit hash
- one manifest field for official dataset scale
- one manifest field for evaluation mode and judge configuration

## Recommended implementation order

1. Add official-public `BEAM` loader contracts without touching the local pilot lane.
2. Add explicit `BEAM` source metadata to manifests:
   - `source_mode=local_pilot|official_public`
   - `upstream_commit`
   - `dataset_scale`
3. Add separate CLI entrypoints for official-public `BEAM`.
4. Add result normalization for upstream evaluation outputs.
5. Run one exact small official lane first.
6. Only then broaden the scale ladder.

## Decision rule

Do not collapse local-pilot and official-public `BEAM` into one fuzzy path.

Keep them separate:

- local pilot = fast internal regression
- official public BEAM = external proof benchmark
