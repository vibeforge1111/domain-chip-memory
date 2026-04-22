# Telegram Probe Baseline Read

Date: 2026-04-23

This note captures the current baseline read from:

- `docs/examples/spark_shadow/telegram_multi_party_probe_pack.json`

using:

```powershell
python -m domain_chip_memory.cli run-spark-shadow-report docs/examples/spark_shadow/telegram_multi_party_probe_pack.json
```

## Current Read

- replay validation passed cleanly
- the shadow report ran end to end over all `6` conversations
- evidence retrieval is now materially stronger:
  - evidence hit rate: `10/10`
  - evidence expected-match rate: `8/10`
- state handling remains strong:
  - historical state: `1/1`
  - current state hit rate: `1/1`

## What Improved

The product-facing shadow path now cleanly retrieves:

- alias binding
- commitment extraction
- negation
- uncertainty / memory-gap
- reported speech
- multi-party relationship edges
- grief/support evidence

This happened because typed conversational bridge observations are now retained on the runtime retrieval surface instead of only helping write acceptance.

## Remaining Gaps

The pack is not fully clean yet. The main misses are now answer-surface quality rather than empty retrieval:

- `loss_event` time grounding is still too coarse for the expected value surface
- relative-time mail evidence currently retrieves the wrong commitment-shaped fact
- current-state location still hits, but its exact expected surface is not yet normalized in the probe readout
- a few turns are still rejected as `no_structured_memory_extracted`, which means product-facing conversational coverage is still incomplete

## What This Means

The probe pack is already useful because it separates:

- benchmark-oriented progress
- real Telegram-style memory readiness

Current honest read:

- the typed conversational work has now propagated into the shadow replay/product-facing lane
- retrieval coverage is strong on the checked Telegram conversational families
- the next product-facing work is answer-surface tightening and broader write coverage, not basic conversational retrieval

## Next Product-Facing Priorities

1. tighten answer surfaces for `loss_event` and relative-time commitment questions
2. improve current-state expected-value normalization in the Telegram probe read
3. widen write coverage so fewer conversational turns fall through as `no_structured_memory_extracted`
4. rerun the same probe pack after each product-facing bridge step

## Promotion Implication

This pack should now be treated as a product-facing gate.

Runtime promotion should not rely only on LoCoMo improvements while this pack still has answer-surface misses and uncovered conversational turns.
