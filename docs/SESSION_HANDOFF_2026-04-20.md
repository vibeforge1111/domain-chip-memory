# Session Handoff 2026-04-20

## Executive Summary

Today was a `domain-chip-memory` quality-hardening session focused on Spark
Builder memory behavior, not harness work.

The main result is that the write side and replay-truth side are now in good
shape, and the remaining live problem is much narrower:

- governed memory exists
- replay probe truth is clean
- synthetic Builder read leakage is removed
- the remaining live failures are now correctly classified as Builder
  `supported_fact_unanswered` read gaps

That means the next move is no longer memory coverage work. It is Builder read
integration work.

---

## Repo State At Stop

Path:

- `<workspace>\\domain-chip-memory`

Current HEAD before this handoff doc commit:

- `67b09c6`

Latest functional commits in order:

- `67b09c6` `Add Builder SDK read adapter`
- `9fcc047` `Harden SDK read answer materialization`
- `a7a0eef` `Normalize Builder human identity for reads`
- `eec0aa1` `Split Builder read sessions by human`
- `03ead48` `Classify supported Builder read abstentions`
- `66f3779` `Canonicalize Builder replay probe subjects`
- `6890be4` `Collapse duplicate Builder sim writes in replay`
- `162acca` `Extract Spark mission writes and quarantine fragments`
- `daeddef` `Quarantine collaborative Builder meta chat`
- `c7ed1e1` `Quarantine Builder directives and confirmations`
- `7cf331a` `Quarantine non-memory Builder chat after failed writes`
- `db39d22` `Keep organic Builder sim writes in replay cohorts`

Unrelated dirty tracked files still present and intentionally untouched:

- `src/domain_chip_memory/__init__.py`
- `src/domain_chip_memory/memory_dual_store_builder.py`
- `tests/test_sdk.py`

There are also many unrelated untracked benchmark and audit artifacts under:

- `artifacts/benchmark_runs`
- `artifacts/live_builder_state_audit`
- `artifacts/live_builder_state_audit_backfill`
- `artifacts/live_builder_state_audit_next`

---

## What Improved

### 1. Builder write quality

The real Builder replay no longer has write rejection pressure.

Earlier in the lane, the live Builder cohort moved to:

- `rejected_writes: 0`

That came from:

- stronger residue quarantine
- duplicate `sim:` write collapse
- mission extraction for project-history statements
- better organic vs synthetic cohort handling

### 2. Replay truth

Replay probes are now honest and clean.

Latest live replay on the real Builder state DB reached:

- `current_state` expected-match `1.0`
- `evidence` expected-match `1.0`
- `historical_state` expected-match `1.0`

This removed the old `probe_quality_gap`.

### 3. Read-path diagnosis is now honest

The remaining live failures are no longer mislabeled as memory coverage misses.

After human-identity normalization and Builder read-session cleanup, the live
organic abstentions became:

- `How do you know where I live?`
- `What do you know about me?`

And they now classify as:

- `read_abstention_gap`
- dominant reason `supported_fact_unanswered`

So the memory is there, but Builder is still not materializing the answer path
correctly.

### 4. Canonical Builder read adapter now exists

A new explicit integration helper was added:

- [builder_read_adapter.py](<domain-chip-memory>/src/domain_chip_memory/builder_read_adapter.py)

This gives Builder a canonical way to:

- call `SparkMemorySDK`
- emit `memory_read_succeeded`
- emit `memory_read_abstained`
- preserve SDK retrieval traces
- preserve abstention for invalid requests

This is the most important handoff artifact for the next session.

---

## Current Live Stop Point

Live replay artifact used repeatedly during this session:

- `<domain-chip-memory>\\artifacts\live_builder_state_audit_backfill\builder_state_backfill.json`

Real Builder source:

- `$SPARK_HOME\state.db`

Current live failure-taxonomy state from the replay:

- issue labels:
  - `role_scope_gap`
  - `residue_quarantine`
  - `read_abstention_gap`
- dominant read abstention reason:
  - `supported_fact_unanswered`
- `read_abstention_gap_count: 2`
- `read_coverage_gap_count: 0`

Current remaining organic abstentions:

1. `How do you know where I live?`
2. `What do you know about me?`

Current replay classification of both:

- `read_outcome: gap`
- `contract_reason: supported_fact_unanswered`

This is the correct diagnosis now.

---

## Why The Remaining Problem Is Builder Integration

The current state of the system is:

- replay confirms governed facts exist before the read
- SDK now normalizes bare `telegram:` subjects
- SDK now supports broad identity-summary evidence queries like
  `What do you know about me?`
- a canonical Builder adapter now exists that turns successful SDK reads into
  `memory_read_succeeded` payloads

So if live Builder is still logging `memory_read_abstained` for those reads,
the likely bug is upstream of replay and downstream of pure memory semantics:

- Builder is not yet calling the canonical adapter path
- or Builder is shaping the read request/result payload differently from the
  adapter contract

That is the narrow continuation target.

---

## Files To Open First Next Time

Open these first:

- [builder_read_adapter.py](<domain-chip-memory>/src/domain_chip_memory/builder_read_adapter.py)
- [sdk.py](<domain-chip-memory>/src/domain_chip_memory/sdk.py)
- [cli.py](<domain-chip-memory>/src/domain_chip_memory/cli.py)
- [test_builder_read_adapter.py](<domain-chip-memory>/tests/test_builder_read_adapter.py)
- [test_sdk_read_materialization.py](<domain-chip-memory>/tests/test_sdk_read_materialization.py)
- [builder_state_backfill.json](<domain-chip-memory>/artifacts/live_builder_state_audit_backfill/builder_state_backfill.json)

If cross-checking the older integration story, also open:

- `<workspace>\\spark-agent-harness\HANDOFF_2026-04-13_RUNTIME_REALIGNMENT.md`
- `<workspace>\\spark-agent-harness\REALIGNMENT_STATUS.md`

---

## Exact Resume Plan

1. Compare live Builder `memory_read_abstained` rows against the payload shape
   produced by `execute_builder_memory_read(...)`.
2. Identify where Builder diverges:
   - request shape
   - method selection
   - subject normalization
   - result-to-event materialization
3. If the Builder event shape is missing fields, patch the Builder caller or
   bridge to emit the adapter contract exactly.
4. Replay the same real `state.db` cohort.
5. Success condition:
   - the two remaining organic reads become `memory_read_succeeded`
   - `read_abstention_gap_count` drops to `0`
   - remaining live labels are only intentional ones like
     `role_scope_gap` and `residue_quarantine`

---

## Useful Verification Commands

Commands already used successfully in this lane:

```powershell
python -m pytest tests\test_cli.py -k "normalizes_bare_telegram_human_ids or splits_shared_memory_retrieval_sessions_by_human or flags_supported_identity_reads_as_read_gap or supported_fact_explanations_as_read_gap or reads_memory_read_only_builder_state_db"
python -m pytest tests\test_sdk_read_materialization.py
python -m pytest tests\test_builder_read_adapter.py tests\test_sdk_read_materialization.py
python -m domain_chip_memory.cli run-spark-builder-state-telegram-intake "$SPARK_HOME" "<domain-chip-memory>\\artifacts\live_builder_state_audit_backfill" --limit 25 --write "<domain-chip-memory>\\artifacts\live_builder_state_audit_backfill\builder_state_backfill.json"
```

---

## Bottom Line

The memory system is no longer the blocker.

The next session should treat this as a Builder read-materialization problem:

- facts exist
- replay sees them
- SDK can answer them
- adapter can emit the right success payload

The remaining work is to make live Builder use that path consistently.
