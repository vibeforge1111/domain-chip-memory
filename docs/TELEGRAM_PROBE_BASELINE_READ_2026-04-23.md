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
  - evidence expected-match rate: `10/10`
- state handling remains strong:
  - historical state: `1/1`
  - historical expected-match rate: `1/1`
  - current state hit rate: `1/1`
  - current state expected-match rate: `1/1`
- accepted writes improved to `12/14`
- rejected writes dropped to `0`

## What Improved

The product-facing shadow path now cleanly retrieves:

- alias binding
- commitment extraction
- negation
- uncertainty / memory-gap
- reported speech
- multi-party relationship edges
- grief/support evidence
- relative-time current/historical state
- mail / action evidence from conversational turns

The previously uncovered conversational turns now promote cleanly:

- `Yesterday I mailed an appreciation letter to the community center.`
- `I still feel close to her when I visit the rose garden.`
- `Leo and I are presenting the prototype on Tuesday.`

This happened because typed conversational bridge observations are now retained on the runtime retrieval surface instead of only helping write acceptance.

## Remaining Gaps

This specific Telegram probe pack is now clean.

Remaining work is broader than this pack:

- widen product-facing probes beyond the current `12` checks
- keep the same families green while widening coverage
- preserve BEAM / LongMemEval / LoCoMo gains while the product-facing lane stays clean

## What This Means

The probe pack is already useful because it separates:

- benchmark-oriented progress
- real Telegram-style memory readiness

Current honest read:

- the typed conversational work has now propagated into the shadow replay/product-facing lane
- retrieval and answer quality are both strong on the checked Telegram conversational families
- the next product-facing work is widening probe coverage, not basic conversational retrieval or bridge persistence

## Next Product-Facing Priorities

1. widen the Telegram probe pack beyond the current `12` probes
2. keep this pack green while widening product-facing conversational coverage
3. rerun the same probe pack after each product-facing bridge step

## Promotion Implication

This pack should now be treated as a product-facing gate.

Runtime promotion should not rely only on LoCoMo improvements; this pack should stay green as a standing product-facing regression gate.
