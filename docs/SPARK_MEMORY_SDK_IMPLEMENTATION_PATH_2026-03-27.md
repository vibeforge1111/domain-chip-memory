# Spark Memory SDK Implementation Path

Date: 2026-03-27
Status: active execution plan

## Why this document exists

The repo has reached the point where benchmark wins alone are no longer enough.

We now need a build path that turns the current benchmark-winning memory substrate into:

- a cleaner architecture
- a governed runtime
- an integration-safe SDK candidate for Spark Intelligence Builder

This document is the execution path for doing that without destroying the benchmark wins that made the repo valuable in the first place.

## Honest current starting state

What is already strong:

- `LongMemEval_s` contiguous measured coverage through `200/200`
- bounded clean `LoCoMo` slices with strong audited results on the active lead lane
- local `BEAM` pilot ladder at `60/60`
- local `ProductMemory` lane at `1266/1266` and fully source-aligned for both lead systems

What is not done yet:

- the winning system is still too monolithic
- evidence, current-state, belief, and event roles are not fully separated as first-class runtime stores
- reconsolidation is still weaker than the benchmark results make it appear
- the repo is not yet a production SDK or production memory engine

## Program doctrine

We will not connect this directly into Spark Intelligence Builder as the primary live memory system yet.

We will first produce:

1. a benchmark-stable memory substrate
2. a role-clean runtime design
3. a governed update and reconsolidation path
4. a narrow SDK surface
5. a shadow-mode Spark integration

Only then do we allow production rollout decisions.

## Non-negotiable regression gates

Every architecture phase must preserve these gates unless a benchmark issue is explicitly documented:

- `LongMemEval_s`
- clean bounded `LoCoMo`
- local `ProductMemory`
- local `BEAM` pilot ladder

All structural work must be benchmark-backed.

## Phase 0: Freeze The Current Winner

Goal:

- establish a stable baseline before moving the architecture

Required actions:

- keep `observational_temporal_memory` as the lead control lane
- keep `dual_store_event_calendar_hybrid` as the comparison lane
- tag architecture changes as one of:
  - benchmark closure only
  - substrate improvement
  - `BEAM` transfer improvement
  - answer-rescue improvement

Exit criteria:

- a documented baseline frontier for:
  - `LongMemEval_s`
  - bounded `LoCoMo`
  - local `BEAM`
  - local `ProductMemory`

Benchmark policy:

- no broad benchmark rerun required unless behavior changes
- every substrate mutation must run at least the local `ProductMemory` and local `BEAM` gates

## Phase 1: Module Separation

Goal:

- stop routing all memory behavior through one oversized implementation file

Required code moves:

- split packet-building entrypoints behind a dedicated boundary
- move extraction logic toward `memory_extraction.py`
- move lifecycle and supersession logic toward `memory_updates.py`
- keep view logic in `memory_views.py`
- move generic retrieval operators toward `memory_operators.py`
- keep `runner.py` dependent on stable module boundaries rather than the monolith directly

Immediate deliverables:

- `packet_builders.py`
- extraction/update/operator module stubs or first real migrations
- no benchmark behavior change

Exit criteria:

- the runner no longer imports packet builders directly from the monolith
- the first separated boundaries exist in code and are used
- all current benchmark gates remain green

Benchmark policy:

- run local `ProductMemory`
- run local `BEAM`
- run targeted `LongMemEval_s` and `LoCoMo` slices if any packet assembly behavior changes

## Phase 2: Explicit Memory Roles

Goal:

- make memory-role separation a runtime truth, not just repo doctrine

Target stores:

- immutable raw episodic archive
- structured evidence memory
- current-state/profile memory
- derived belief/reflection memory
- temporal-event memory

Required contracts:

- retrieved-unit role labels:
  - `raw_episode`
  - `structured_evidence`
  - `current_state`
  - `belief`
  - `event`
- typed answer candidates:
  - `current_state`
  - `location`
  - `date`
  - `numeric`
  - `preference`
  - `abstain`

Exit criteria:

- packet assembly and scoring can distinguish evidence from belief from current state
- source-alignment checks remain green
- benchmark wins still survive the role separation

Benchmark policy:

- mandatory `ProductMemory` rerun after each role-boundary mutation
- targeted `LoCoMo` reruns for temporal and conversational linkage
- targeted `LongMemEval_s` reruns for exact-value and current-state integrity

## Phase 3: Governed Update Engine

Goal:

- replace implicit benchmark-time lifecycle behavior with a real memory update doctrine

Required capabilities:

- create
- update
- delete
- supersede
- restore
- contradict
- rebuild current-state view from evidence

Required implementation:

- explicit update functions
- explicit tombstone handling
- explicit current-state rebuild logic
- explicit historical reconstruction operators

Exit criteria:

- update behavior is implemented as named lifecycle rules
- current-state reconstruction is no longer hidden inside retrieval heuristics
- deletion and restore behavior stay benchmark-safe

Benchmark policy:

- mandatory local `ProductMemory`
- mandatory local `BEAM`
- targeted `LongMemEval_s` for current-state and stale-state questions

## Phase 4: Reconsolidation And Offline Maintenance

Goal:

- add a real maintenance path that makes the system durable under longer-lived use

Required capabilities:

- reflection invalidation rules
- belief refresh from evidence
- offline compaction
- selective rehydration
- event reconciliation
- provenance-preserving consolidation

Exit criteria:

- online memory stays compact
- exact answer-bearing spans remain recoverable
- the system can explain whether an answer came from evidence, current state, belief, or event memory

Benchmark policy:

- local `BEAM` becomes mandatory here
- rerun `LoCoMo` slices that stress long-range linkage
- rerun `LongMemEval_s` slices that depend on exactness after compression

## Phase 5: Runtime SDK Surface

Goal:

- create a narrow Spark-facing API instead of exposing benchmark-specific internals

Target interface shape:

- `write_observation(...)`
- `write_event(...)`
- `get_current_state(...)`
- `get_historical_state(...)`
- `retrieve_evidence(...)`
- `retrieve_events(...)`
- `explain_answer(...)`

SDK requirements:

- typed request/response contracts
- provenance returned with answers
- abstention-capable interfaces
- replayable traces

Exit criteria:

- Spark can call a stable runtime surface without knowing benchmark packet internals
- SDK contracts are narrow enough to evolve safely

Benchmark policy:

- benchmark reruns only when the SDK surface changes runtime behavior
- local `ProductMemory` remains the fastest safety gate

## Phase 6: Spark Shadow Integration

Goal:

- prove this system on real Spark traffic without making it the live authority yet

Required setup:

- mirror real Builder conversations into the memory runtime
- run memory answers in shadow mode
- compare against current Builder behavior
- log failure classes

Required telemetry:

- stale current-state answer rate
- ambiguity failure rate
- unsupported write rate
- evidence recovery rate
- latency
- memory growth

Exit criteria:

- shadow-mode quality is stable
- operational costs are acceptable
- failure classes are understood and bounded

## Phase 7: Controlled Production Rollout

Goal:

- promote the memory system gradually instead of replacing Builder memory in one jump

Rollout order:

1. read-only assist mode
2. limited field ownership
3. broader state ownership
4. full promoted runtime role

Do not promote before:

- shadow-mode trace quality is acceptable
- provenance is inspectable
- rollback is trivial
- benchmark regressions are absent

## What to benchmark during the build

Use benchmarks based on the type of implementation change:

- current-state lifecycle or deletion behavior:
  - local `ProductMemory`
  - targeted `LongMemEval_s`
- temporal reasoning, event reconciliation, or compaction behavior:
  - local `BEAM`
  - targeted `LoCoMo`
- answer-candidate, packet-shaping, or retrieval-surface behavior:
  - local `ProductMemory`
  - bounded `LoCoMo`
  - targeted `LongMemEval_s`

## Immediate execution order

The next concrete sequence is:

1. complete Phase 1 module separation
2. introduce explicit role-labeled retrieval units and typed answer-candidate contracts
3. extract current-state lifecycle logic into a dedicated update module
4. add reconsolidation and selective rehydration rules
5. expose a narrow runtime SDK
6. run shadow-mode Spark integration

## Current working interpretation

The repo is already strong enough to justify this plan.

It is not yet strong enough to skip it.
