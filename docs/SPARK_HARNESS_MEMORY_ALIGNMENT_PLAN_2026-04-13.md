# Spark Harness Memory Alignment Plan - 2026-04-13

This document defines how `domain-chip-memory` should align with `spark-agent-harness`.

It is not about replacing the harness memory layer.
It is about making the two systems fit together without drift.

## Core Contract

`domain-chip-memory` should be the durable semantic memory substrate for Spark.

It should not be asked to become:

- the harness short-term session buffer
- the runtime event store
- the only execution trace system
- a replacement for follow/retry/run-state context

The harness should provide:

- short-term continuity
- runtime orchestration
- query routing
- write gating
- final response assembly
- event/tracing/approval storage

`domain-chip-memory` should provide:

- typed memory writes
- typed memory reads
- current-state support
- evidence/event retrieval
- provenance-bearing answers
- abstention
- governed publish/release
- maintenance / reconsolidation

## The Required Split

### Harness-local

Owns:

- recent-turn context
- active task continuity
- current loop state
- operational summaries

### Domain-chip-memory

Owns:

- durable user/project facts
- provenance-backed current-state truth
- historical and evidence support
- governed runtime memory

### Future Spark runtime/event store

Owns:

- runs
- steps
- tool calls
- traces
- approvals
- mutations
- rollback points

## What Domain-Chip-Memory Should Expect From Spark

Spark should not call the SDK blindly.
It should provide surrounding systems:

1. subject/predicate normalizer
2. memory write gate
3. memory query router
4. provenance-preserving response assembly
5. shadow reporting
6. maintenance scheduler
7. visible compiled memory workspace

Without those layers, the SDK can still work, but the product experience will be noisy and untrustworthy.

## What Should Improve On The Memory SDK Side

To work great with the harness, the memory side should keep moving toward:

### 1. Narrow stable runtime API

Spark-facing methods should stay clear and typed:

- `write_observation(...)`
- `write_event(...)`
- `get_current_state(...)`
- `get_historical_state(...)`
- `retrieve_evidence(...)`
- `retrieve_events(...)`
- `explain_answer(...)`

### 2. Better role clarity

The repo's role split should remain explicit:

- evidence
- current state
- belief/reflection
- event

Spark should not have to guess which memory role it got back.

### 3. Better publish/readiness surfaces

Governed release usage should get cleaner around:

- stable current release pointer
- stale release detection
- schema versioning
- explicit readiness reporting

### 4. Better integration traces

The SDK side should help Spark surface:

- why a read succeeded
- why it abstained
- what provenance supports a current-state answer
- what write was rejected and why

## What Should Not Happen

Do not let Spark start building a second semantic memory engine because:

- query routing is weak
- write gates are missing
- runtime event storage is being introduced

Those are integration gaps, not reasons to fork the durable memory substrate.

## Shared Roadmap With Spark Harness

This should be the connected plan across both repos:

1. harness tool broker
2. harness memory query router
3. harness memory write gate
4. shadow evaluation/reporting on real traffic
5. compiled user-visible governed memory workspace
6. stronger maintenance/reconsolidation linkage
7. richer promotion policy only after the above are stable

## Final Direction

The best outcome is:

- Spark harness becomes a strong memory orchestrator
- `domain-chip-memory` remains the durable semantic memory substrate
- runtime/event storage becomes explicit and separate
- users get an inspectable governed memory workspace

That is the alignment target.
