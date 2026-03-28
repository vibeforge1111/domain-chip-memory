# Frontier Status

Date: 2026-03-28
Status: active measured snapshot

## Purpose

This document is the current source of truth for the repo's measured frontier state.

It exists to prevent drift between:

- historical session logs
- narrower local lane memos
- the full currently checked-in benchmark and product-memory corpus

Historical logs should remain historical.
This file records the current measured state of the repo as of today.

## Current Measured State

### Local ProductMemory

Measured on the current checked-in `product_memory_samples()` corpus:

- sample count: `215`
- question count: `1266`

Current measured result on the full local lane:

- `observational_temporal_memory`: `1266/1266` (`1.00`)
- `dual_store_event_calendar_hybrid`: `1266/1266` (`1.00`)

Current source-alignment state on the same full local lane:

- `observational_temporal_memory`: `1266/1266` aligned (`1.00`)
- `dual_store_event_calendar_hybrid`: `1266/1266` aligned (`1.00`)

Important interpretation:

- the `690/690 -> 706/706` language in recent handoff docs refers to a narrower promoted frontier ladder inside the local product-memory family
- it does **not** replace the full currently checked-in local `ProductMemory` corpus total
- the full active checked-in local truth is still `1266/1266`

### LongMemEval_s

Current measured contiguous coverage:

- `200/200` on the measured frontier currently documented in-repo

Important interpretation:

- this is strong partial coverage
- it is not the same thing as full-benchmark closure

### LoCoMo

Current measured clean bounded coverage remains strong on the active lead lane.

Important interpretation:

- the repo has strong bounded clean slices
- it does not yet claim broad full-dataset closure

### Local BEAM

The local `BEAM` pilot ladder remains an active internal stress track and should still be treated as:

- real local pressure
- not equivalent to full official `BEAM` reproduction

## Measurement Commands

The current local `ProductMemory` total can be inspected with:

```powershell
python -c "from domain_chip_memory.sample_data import product_memory_samples; print(sum(len(s.questions) for s in product_memory_samples()))"
```

The current full-lane score check can be reproduced with:

```powershell
python -c "from domain_chip_memory.sample_data import product_memory_samples; from domain_chip_memory.runner import run_baseline; from domain_chip_memory.providers import get_provider; samples=product_memory_samples(); baselines=['observational_temporal_memory','dual_store_event_calendar_hybrid']; [print(b, run_baseline(samples, baseline_name=b, provider=get_provider('heuristic_v1'), top_k_sessions=2, fallback_sessions=1)['overall'], run_baseline(samples, baseline_name=b, provider=get_provider('heuristic_v1'), top_k_sessions=2, fallback_sessions=1)['product_memory_summary']['measured_metrics']['primary_answer_candidate_source_alignment']) for b in baselines]"
```

## Decision Rule

When there is a conflict between:

- a historical ladder count in a session log
- a narrower family-specific frontier note
- the currently checked-in full local corpus

prefer the currently measured full local corpus for current-state planning.

## Immediate Implication

The repo should now operate with two explicit truths:

1. the full local `ProductMemory` checked-in corpus currently measures at `1266/1266`
2. narrower `690/706` ladder notes remain useful historical handoff context, but should not be mistaken for the full active local total
