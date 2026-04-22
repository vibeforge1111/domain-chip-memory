# Telegram Memory Probe Pack

This doc defines the first production-facing shadow replay pack for Telegram-style memory.

Primary file:

- `docs/examples/spark_shadow/telegram_multi_party_probe_pack.json`

Why this exists:

- LoCoMo is useful, but it does not fully cover production chat-memory failure modes.
- We need a stable, checked-in probe pack for:
  - aliases
  - commitments
  - negation
  - uncertainty
  - reported speech
  - grief/support
  - relative time
  - multi-party social graph memory

Probe categories in the pack:

- `alias_and_commitment`
- `negation_and_unknown`
- `reported_speech`
- `grief_support_and_peace`
- `relative_time_and_history`
- `multi_party_social_graph`

What this pack is for:

- validate replay shape through the existing Spark shadow contract
- provide a repeatable product-facing sanity lane while LoCoMo evals are being hardened
- force promotion decisions to consider Telegram-style chat memory, not benchmarks only

What this pack is not:

- it is not a substitute for LoCoMo, BEAM, or LongMemEval
- it is not a full production traffic replay
- it is not yet a promotion-grade score by itself

Promotion gates this pack supports:

1. Alias / negation / uncertainty probes should not regress when retrieval fusion changes.
2. Reported-speech probes should route through structured evidence, not broad summary synthesis.
3. Relative-time and historical-state probes should remain readable through the existing shadow replay flow.
4. Multi-party social graph probes should stay supportable by typed relationship memory, not raw-turn luck.

Recommended commands:

```powershell
python -m domain_chip_memory.cli validate-spark-shadow-replay docs/examples/spark_shadow/telegram_multi_party_probe_pack.json
```

```powershell
python -m domain_chip_memory.cli run-spark-shadow-report docs/examples/spark_shadow/telegram_multi_party_probe_pack.json --write artifacts/telegram_multi_party_probe_report.json
```

Current intended use:

- keep this pack small and deterministic
- expand only when a new production failure family is concrete and reusable
- use it alongside LoCoMo fused-family evals, not instead of them

Initial baseline read:

- the pack validates cleanly through the current shadow replay contract
- the report runs end to end
- current shadow results are intentionally mixed:
  - relative-time current/historical state already works better
  - grief/loss has partial support
  - alias, commitment, negation, uncertainty, reported speech, and multi-party relationship probes still expose real gaps

That is useful. This pack is already doing its job as a product-facing gap detector.
