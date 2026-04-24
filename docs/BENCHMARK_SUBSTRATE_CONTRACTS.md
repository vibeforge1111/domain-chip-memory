# Benchmark Substrate Contracts

Date: 2026-03-22
Status: active

## Purpose

This document defines the first implementation substrate for the benchmark stack.

The goal is not to implement full benchmark runners yet.
The goal is to normalize the benchmark shapes into one internal contract so every later baseline and memory system can run against the same objects.

## Contract objects

The package now defines:

1. `NormalizedBenchmarkConfig`
2. `NormalizedBenchmarkSample`
3. `NormalizedSession`
4. `NormalizedTurn`
5. `NormalizedQuestion`
6. `BenchmarkRunManifest`
7. `BaselinePromptPacket`
8. `RetrievedContextItem`

These live in:

- `src/domain_chip_memory/contracts.py`

## Why this matters

The three official benchmarks do not have the same source shape.

- `LongMemEval` is a question-centric dataset where each instance includes the haystack history and a single question.
- `LoCoMo` is a conversation-centric dataset where each sample contains sessions plus many QA annotations.
- `GoodAI LTM Benchmark` is a benchmark harness with published configurations and generated test definitions.

Without normalization, every baseline becomes benchmark-specific glue code.

## Adapter layer

The package now defines:

- `LongMemEvalAdapter.normalize_instance`
- `LoCoMoAdapter.normalize_instance`
- `GoodAILTMBenchmarkAdapter.normalize_configuration`
- `GoodAILTMBenchmarkAdapter.normalize_definition`
- `BEAMAdapter.normalize_instance`
- `ConvoMemShadowAdapter.normalize_instance`

These live in:

- `src/domain_chip_memory/adapters.py`

## Source-backed assumptions

### LongMemEval

Grounded in the public README:

- instances include `question_id`, `question_type`, `question`, `answer`, `question_date`
- sessions are in `haystack_sessions`
- session ids are in `haystack_session_ids`
- session dates are in `haystack_dates`
- evidence sessions are in `answer_session_ids`
- turn-level evidence is marked by `has_answer: true`

Adapter choice:

- one normalized sample per benchmark instance
- one normalized question per sample

### LoCoMo

Grounded in the public README:

- one sample is one conversation
- session blocks are named `session_<num>`
- timestamps are `session_<num>_date_time`
- QA annotations live in `qa`
- evidence is a list of dialog ids

Adapter choice:

- one normalized sample per conversation
- many normalized questions per sample

### GoodAI LTM Benchmark

Grounded in the public README and published benchmark files:

- benchmark identity is carried by published config files such as `benchmark-v3-500k.yml`
- datasets are a family list inside the config
- generated test definitions contain `script`, `is_question`, `time_jumps`, `token_spacings`, and `expected_responses`

Adapter choice:

- one normalized config per published configuration
- one normalized sample per generated test definition
- one synthetic session per definition script
- one normalized question per question turn in the script

## Current limitations

The current substrate now includes two deterministic baselines:

- `full_context`
- `lexical`

It also now includes three deterministic candidate memory systems:

- `beam_temporal_atom_router`
- `observational_temporal_memory`
- `dual_store_event_calendar_hybrid`

These build canonical prompt packets and run manifests.
The package also includes:

- a deterministic heuristic responder for local scorecard smoke tests
- an env-gated OpenAI chat-completions provider for bounded real runs
- a scorecard builder over baseline predictions
- a locked first canonical GoodAI configuration choice
- a temporal-memory path with atom extraction, recency-aware routing, and source rehydration
- a stable compressed-context path with observation logging and reflection
- a hybrid path that combines stable observations with an explicit event calendar

The stack still does not:

- download benchmark data
- run official scoring
- build full retrieval traces
- reproduce full official `BEAM` yet; current support now includes an unpacked official-public chats loader, upstream answer export, an upstream evaluation wrapper, and evaluation summary bridges, but not the upstream answer-generation flow or a checked-in exact small-lane official run artifact

## Schemas

The repo now includes:

- `schemas/normalized_benchmark_config.schema.json`
- `schemas/normalized_benchmark_sample.schema.json`
- `schemas/normalized_session.schema.json`
- `schemas/normalized_question.schema.json`
- `schemas/benchmark_run_manifest.schema.json`
- `schemas/baseline_prompt_packet.schema.json`

## CLI surface

To inspect the substrate summary:

```powershell
python -m domain_chip_memory.cli benchmark-contracts
```

To inspect the baseline packet and manifest surface:

```powershell
python -m domain_chip_memory.cli baseline-contracts
```

To inspect the scorecard contract and canonical config choice:

```powershell
python -m domain_chip_memory.cli scorecard-contracts
python -m domain_chip_memory.cli canonical-configs
```

To inspect file-loader, provider, and runner surfaces:

```powershell
python -m domain_chip_memory.cli loader-contracts
python -m domain_chip_memory.cli provider-contracts
python -m domain_chip_memory.cli runner-contracts
python -m domain_chip_memory.cli memory-system-contracts
```

The CLI now loads [.env](/<domain-chip-memory>/.env) automatically, so provider credentials can live there instead of being exported manually.

To run a bounded real-provider smoke test once `OPENAI_API_KEY` is available:

```powershell
python -m domain_chip_memory.cli run-longmemeval-baseline path\\to\\longmemeval_s_cleaned.json --baseline beam_temporal_atom_router --provider openai:gpt-4.1-mini --limit 1
python -m domain_chip_memory.cli run-longmemeval-baseline path\\to\\longmemeval_s_cleaned.json --baseline beam_temporal_atom_router --provider minimax:YOUR_MINIMAX_MODEL --limit 1
```

To run local demo scorecards:

```powershell
python -m domain_chip_memory.cli demo-scorecards
```

To run on real benchmark files once they are available locally:

```powershell
python -m domain_chip_memory.cli run-longmemeval-baseline path\\to\\longmemeval_s_cleaned.json --baseline lexical --provider heuristic_v1 --limit 10
python -m domain_chip_memory.cli run-longmemeval-baseline path\\to\\longmemeval_s_cleaned.json --baseline beam_temporal_atom_router --provider heuristic_v1 --limit 10
python -m domain_chip_memory.cli run-longmemeval-baseline path\\to\\longmemeval_s_cleaned.json --baseline observational_temporal_memory --provider heuristic_v1 --limit 10
python -m domain_chip_memory.cli run-longmemeval-baseline path\\to\\longmemeval_s_cleaned.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --limit 10
python -m domain_chip_memory.cli run-beam-baseline artifacts\\benchmark_runs\\beam_local_pilot_v1_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\\benchmark_runs\\beam_local_pilot_observational_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-public-baseline path\\to\\chats --chat-size 128K --baseline observational_temporal_memory --provider heuristic_v1 --limit 1 --upstream-commit 3e12035532eb85768f1a7cd779832b650c4b2ef9
python -m domain_chip_memory.cli export-beam-public-answers artifacts\\benchmark_runs\\beam_public_scorecard.json artifacts\\beam_results --result-file-name domain_chip_memory_answers.json
python -m domain_chip_memory.cli run-beam-official-evaluation path\\to\\beam_upstream_repo artifacts\\beam_results --chat-size 128K --result-file-name domain_chip_memory_answers.json --dry-run
python -m domain_chip_memory.cli run-locomo-baseline path\\to\\locomo10.json --baseline full_context --provider heuristic_v1 --limit 3
python -m domain_chip_memory.cli run-goodai-baseline path\\to\\benchmark-v3-32k.yml path\\to\\definitions --baseline lexical --provider heuristic_v1 --dataset-name Colours --limit 5
python -m domain_chip_memory.cli compare-longmemeval-local path\\to\\longmemeval_s_cleaned.json --provider heuristic_v1 --write artifacts\\benchmark_runs\\longmemeval_s_system_comparison.json
```
