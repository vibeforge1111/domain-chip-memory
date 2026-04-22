# Telegram Probe Baseline Read

Date: 2026-04-23

This note captures the first baseline read from:

- `docs/examples/spark_shadow/telegram_multi_party_probe_pack.json`

using:

```powershell
python -m domain_chip_memory.cli run-spark-shadow-report docs/examples/spark_shadow/telegram_multi_party_probe_pack.json
```

## What Worked

- replay validation passed cleanly
- the shadow report ran end to end over all `6` conversations
- relative-time state handling was the strongest area:
  - historical location probe hit
  - current location probe hit
- grief/loss has partial traction:
  - the `loss_event` probe hit

## What Failed

These families still showed weak or empty evidence retrieval in the current product-facing shadow path:

- alias binding
- commitment extraction
- negation
- uncertainty / memory-gap
- reported speech
- multi-party relationship edges
- grief/support retrieval beyond the loss event itself

## What This Means

The probe pack is already useful because it separates:

- benchmark-oriented progress
- real Telegram-style memory readiness

Current honest read:

- state-like temporal updates are ahead
- richer conversational structure is still behind
- the typed conversational work we added for LoCoMo has not yet propagated cleanly into the shadow replay/product-facing lane

## Next Product-Facing Priorities

1. bridge alias / commitment / negation / uncertainty / reported-speech extraction into the shadow replay ingestion lane
2. add relationship-edge support for simple multi-party social facts
3. rerun the same probe pack after each bridge step

## Promotion Implication

This pack should now be treated as a product-facing gate.

Runtime promotion should not rely only on LoCoMo improvements while this pack still shows broad conversational-structure misses.
