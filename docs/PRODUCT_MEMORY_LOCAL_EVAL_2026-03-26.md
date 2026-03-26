# Product Memory Local Eval

Date: 2026-03-26
Status: active local eval lane

## Purpose

This repo now has a first dedicated local `ProductMemory` evaluation lane.

It exists so the architecture can be judged on product-memory behavior with the same runner and scorecard discipline used for benchmark work.

This lane is intentionally local and bounded.

It is not a public benchmark claim.

## Current task families

- `correction`
  - a user updates earlier memory and the system should reflect the corrected current state
- `deletion`
  - a user asks for memory removal and the system should avoid serving stale deleted state
- `stale_state_drift`
  - a value changes, changes again, then re-enters, and the system should return the active state instead of stale intermediate state

## Why this matters

The harmonized doctrine says benchmark wins and real-world UX must come from the same substrate.

This lane makes that test concrete.

The first goal is not to brag about high scores.

The first goal is to create honest visibility into product-memory behavior that normal benchmark slices do not fully capture.

## Entrypoint

```powershell
python -m domain_chip_memory.cli demo-product-memory-scorecards
```

## Source

The current local source lives in:

- `src/domain_chip_memory/sample_data.py`

under:

- `product_memory_samples()`
