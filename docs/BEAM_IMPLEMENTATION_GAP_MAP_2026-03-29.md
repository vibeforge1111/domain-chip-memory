# BEAM Implementation Gap Map 2026-03-29

Status: active

## Purpose

This file answers one practical question:

- what is the difference between our current in-repo `BEAM` support and a real official `BEAM` reproduction path

## Current in-repo support

What we already have:

- `BEAMAdapter.normalize_instance` in [adapters.py](/<domain-chip-memory>/src/domain_chip_memory/adapters.py)
- `load_beam_json` in [loaders.py](/<domain-chip-memory>/src/domain_chip_memory/loaders.py)
- `load_beam_public_dir` in [loaders.py](/<domain-chip-memory>/src/domain_chip_memory/loaders.py)
- `run-beam-baseline` in [cli.py](/<domain-chip-memory>/src/domain_chip_memory/cli.py)
- `run-beam-public-baseline` in [cli.py](/<domain-chip-memory>/src/domain_chip_memory/cli.py)
- `export-beam-public-answers` in [cli.py](/<domain-chip-memory>/src/domain_chip_memory/cli.py)
- `run-beam-official-evaluation` in [cli.py](/<domain-chip-memory>/src/domain_chip_memory/cli.py)
- `summarize-beam-evaluation` in [cli.py](/<domain-chip-memory>/src/domain_chip_memory/cli.py)
- `BEAM` scorecard handling in [scorecards.py](/<domain-chip-memory>/src/domain_chip_memory/scorecards.py)
- local regression tests in [tests/test_adapters.py](/<domain-chip-memory>/tests/test_adapters.py) and [tests/test_cli.py](/<domain-chip-memory>/tests/test_cli.py)

What that support actually means:

- we can run our baselines over an internal normalized `BEAM`-shaped JSON slice
- we can run our baselines over an unpacked official-public `BEAM` chats directory
- we can score that slice with our own scorecard contract
- we can export official-public `BEAM` scorecards into the per-conversation answer JSON shape expected by upstream `run_evaluation.py`
- we can validate and invoke the pinned upstream `run_evaluation.py` path against exported answer files
- we can summarize upstream evaluation JSON back into a compact in-repo view
- we can use the local pilot lane as a fast regression benchmark

What it does not mean:

- we do not yet reproduce the official upstream answer-generation flow
- we do not yet reproduce the official upstream answer-generation flow
- we still need a first measured exact small-lane run artifact, not just the wrapper

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
- `load_beam_public_dir` can ingest unpacked official-public conversation directories and normalize them into our contracts

Missing:

- richer normalization of upstream metadata such as profiles, seeds, and narrative labels when needed
- validation on real `500K`, `1M`, and `10M` fixtures, not only the first official-style shape
- any loader path we may need for Hugging Face-native artifacts before local unpacking

### Gap 2: Official answer-generation contract

Current:

- our runner calls our own baselines directly against normalized samples

Missing:

- exact mapping from our baselines to the official upstream answer-generation interface
- commit-pinned documentation for upstream environment variables and result file naming beyond the export bridge
- clear distinction between:
  - our native baselines on official BEAM data
  - exact reproduction of upstream LIGHT or baseline flows

### Gap 3: Official evaluation contract

Current:

- our scorecard contract measures correctness inside our own benchmark substrate
- `run-beam-official-evaluation` can validate and invoke the upstream `run_evaluation.py` surface against exported result files
- `summarize-beam-evaluation` can read upstream evaluation outputs into a compact in-repo summary

Missing:

- pinned judge settings used by the official evaluation path
- mapping from upstream evaluation outputs into our scorecard fields
- explicit policy for comparing our scores against upstream reported numbers

### Gap 4: One honest CLI path

Current:

- `run-beam-baseline` means `run our baseline on a local BEAM-style slice`
- `run-beam-public-baseline` means `run our baseline on an unpacked official-public BEAM chats directory`

Missing:

- command naming that makes it impossible to confuse:
  - internal local pilot
  - official public reproduction

### Gap 5: Reproducible artifact contract

Current:

- local `BEAM` artifacts live under `artifacts/benchmark_runs/beam_local_pilot_*`

Missing:

- one official artifact naming scheme
- one manifest field for evaluation mode and judge configuration inside the final measured artifact
- one checked-in exact small-lane artifact proving the wrapper against the pinned upstream repo

## Recommended implementation order

1. Add official-public `BEAM` loader contracts without touching the local pilot lane.
2. Add explicit `BEAM` source metadata to manifests:
   - `source_mode=local_pilot|official_public`
   - `upstream_commit`
   - `dataset_scale`
3. Add separate CLI entrypoints for official-public `BEAM`.
4. Add result normalization for upstream evaluation outputs.
5. Run one exact small official lane first through the new wrapper.
6. Pin the judge configuration used for that run.
7. Only then broaden the scale ladder.

## Decision rule

Do not collapse local-pilot and official-public `BEAM` into one fuzzy path.

Keep them separate:

- local pilot = fast internal regression
- official public BEAM = external proof benchmark
