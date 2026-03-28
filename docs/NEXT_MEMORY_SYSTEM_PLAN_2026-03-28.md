# Next Memory System Plan

Date: 2026-03-28
Status: active execution doctrine

## Purpose

This document defines the next serious build phase for `domain-chip-memory`.

The goal is not only to keep closing benchmark slices.
The goal is to turn the repo into:

- a state-of-the-art memory architecture
- a benchmark-winning memory system
- a trustworthy real product memory layer
- a narrow, integration-safe runtime for Spark Intelligence Builder

This plan supersedes the narrower "just finish Spark shadow integration" framing.
Spark shadow work remains important, but it is now one lane inside a larger program:

- win the public benchmark stack honestly
- beat the strongest practical systems in the market on memory quality
- become a real memory layer, not only a benchmark packet machine

## North Star

Build one lightweight, governed memory system that:

- outperforms the strongest pinned public benchmark bars on `LongMemEval`, `LoCoMo`, `GoodAI LTM Benchmark`, and `BEAM`
- stays honest under reruns, audits, and source-alignment checks
- supports real product-memory behavior:
  - correction
  - deletion
  - supersession
  - historical reconstruction
  - abstention
  - provenance
- remains fast and cheap enough to operate as a true online memory layer

## Current Truthful Starting State

What is already strong:

- contiguous measured `LongMemEval_s` coverage through `200/200`
- strong clean bounded `LoCoMo` results on the active lead lane
- local `BEAM` pilot ladder in place and green on the currently promoted slices
- local `ProductMemory` lane already functioning as a real product-memory stress harness
- typed answer-candidate contracts, source-alignment checks, SDK contracts, and Spark shadow replay surfaces already exist
- the repo test suite is stable

What is not finished:

- `memory_systems.py` still holds too much architecture and behavior
- provider-side rescue still carries too much correctness burden
- memory-role separation is doctrinally clear but not fully runtime-clean
- `LongMemEval`, `LoCoMo`, `GoodAI`, and `BEAM` are not all fully closed or fully pinned in-repo
- real-time runtime metrics are only partially measured
- Spark has shadow surfaces, but not enough real trace evidence yet for promotion

## Win Condition

We should only call this next phase successful when all of the following are true:

1. The repo has one explicit memory architecture, not separate benchmark and product stacks.
2. The architecture beats or matches the strongest pinned frontier bars on the target benchmarks with reproducible artifacts.
3. The system remains source-aligned on product-memory tasks and does not rely mainly on provider cleanup.
4. The runtime can handle real product memory operations:
   - write durable facts and events
   - answer current-state questions
   - answer historical-state questions
   - preserve deletions
   - preserve provenance
   - abstain honestly
5. The online path remains operationally practical:
   - bounded latency
   - bounded token use
   - bounded memory growth
   - explicit maintenance path
6. Spark can run the system safely in shadow mode with replayable evidence before any live promotion decision.

## Non-Negotiable Rules

### 1. One architecture, not two

Do not maintain:

- one path for benchmark wins
- another path for product memory

Benchmark strength and product quality must come from the same substrate.

### 2. Keep Spark in shadow mode

Do not promote the memory SDK to the primary live memory layer in Spark until:

- replay traces exist
- shadow reports are stable
- benchmark gates still pass after runtime mutations

### 3. Generic operators beat question-shaped hacks

Prefer:

- current-state lookup
- historical reconstruction
- temporal before-after lookup
- count and sum
- compare and diff
- preference synthesis
- abstention

Do not keep adding benchmark-specific rescue branches if one reusable operator can solve the class.

### 4. Provider rescue is allowed but must shrink over time

Provider normalization may remain as a guardrail.
It must not remain the main home of correctness.

### 5. Every architectural mutation must pass gates

Mandatory safety gates after meaningful behavior changes:

- local `ProductMemory`
- local `BEAM`
- targeted `LongMemEval_s`
- targeted clean `LoCoMo`

## Target Architecture

The target system should have these explicit runtime roles.

### 1. Raw episodic archive

Purpose:

- preserve immutable source truth
- preserve turn and session provenance
- support selective rehydration

### 2. Structured evidence memory

Purpose:

- store extracted factual units
- support exact evidence retrieval
- remain distinct from beliefs and summaries

### 3. Current-state and profile memory

Purpose:

- answer "what is true now"
- govern mutable facts
- respect delete, restore, and supersession rules

### 4. Temporal-event memory

Purpose:

- preserve events, transitions, and anchors
- support temporal disambiguation and event-chain reasoning

### 5. Belief and reflection memory

Purpose:

- store derived summaries and synthesized beliefs
- remain explicitly downstream of evidence
- never masquerade as raw evidence

### 6. Working memory and scratchpad

Purpose:

- keep the hot path small
- support hard retrieval and multi-step reasoning without exploding the default packet size

### 7. Offline maintenance path

Purpose:

- reconsolidate memory
- refresh beliefs
- compact safely
- preserve answer-bearing spans through maintenance

## Workstreams

## Workstream A: Freeze And Normalize The Current Frontier

Goal:

- establish one clean source of truth for where the repo stands today

Required outputs:

- promote the already-green next local `ProductMemory` lane
- reconcile documentation drift around local lane totals and current frontier wording
- keep one baseline ledger for:
  - `LongMemEval_s`
  - `LoCoMo`
  - local `BEAM`
  - local `ProductMemory`

Definition of done:

- the repo has one current-state snapshot doc set
- all future mutations compare against that locked baseline

## Workstream B: Module Separation

Goal:

- stop routing the architecture through one giant monolith

Required code boundaries:

- `memory_extraction.py`
- `memory_updates.py`
- `memory_views.py`
- `memory_operators.py`
- `packet_builders.py`

Required end state:

- `runner.py`, the SDK, and benchmark entrypoints depend on stable module boundaries
- `memory_systems.py` becomes an implementation shell or compatibility layer, not the whole system

Definition of done:

- packet construction, extraction, updates, operators, and views each have explicit homes
- module boundaries are used in the hot path
- behavior is unchanged or explicitly benchmark-justified

## Workstream C: Governed Update Engine

Goal:

- make lifecycle behavior first-class instead of implicit

Required operations:

- create
- update
- delete
- supersede
- restore
- contradict
- rebuild current-state view from evidence

Required behavior:

- explicit tombstones
- explicit restore semantics
- explicit historical reconstruction
- explicit current-state rebuild logic

Definition of done:

- current-state correctness no longer depends on packet-local accident
- deletion and restore logic survive all active product-memory gates

## Workstream D: Role-Clean Retrieval

Goal:

- make memory-role separation a runtime truth

Required read paths:

- `get_current_state(...)`
- `get_historical_state(...)`
- `retrieve_evidence(...)`
- `retrieve_events(...)`
- belief or reflection retrieval where needed
- `explain_answer(...)`

Required guarantees:

- evidence, belief, current-state, event, and ambiguity outputs are distinguishable
- answer-candidate source alignment remains measurable
- abstentions are explicit

Definition of done:

- every answer path can explain what memory role produced the answer
- product-memory and benchmark scorecards keep showing source alignment

## Workstream E: Typed Answer Integrity

Goal:

- move answer correctness earlier into the substrate

Required answer-candidate classes:

- `exact_numeric`
- `currency`
- `date`
- `location`
- `preference`
- `current_state`
- `abstain`

Required behavior:

- packet-level answer candidates are authoritative
- responders do not override them with weaker overlap heuristics
- provider logic consumes typed candidates directly instead of trying to infer too much from strings

Definition of done:

- exact short answers survive compaction and response generation
- provider rescue becomes a guardrail, not the primary correctness engine

## Workstream F: Benchmark Completion

Goal:

- turn strong slices into a truly closed benchmark story

Required tasks:

- extend `LongMemEval_s` beyond the current measured frontier
- broaden clean `LoCoMo` coverage beyond the currently bounded lanes
- lock the first canonical `GoodAI LTM Benchmark` configuration and run
- keep the local `BEAM` pilot moving while the official implementation surface remains unpinned
- pin the official `BEAM` evaluation path as soon as the public surface exists

Definition of done:

- each benchmark has:
  - a pinned target or honest status
  - a reproducible run path
  - source-of-truth artifacts
  - category-level reporting

## Workstream G: Architecture Ablations

Goal:

- understand why gains happen

Every meaningful mutation must be tagged as one of:

- extraction improvement
- update and supersession improvement
- retrieval improvement
- operator improvement
- provider-rescue improvement
- maintenance improvement
- benchmark-closure-only improvement
- `BEAM` transfer improvement

Definition of done:

- we can explain which gains are real substrate gains versus local cleanup
- we stop confusing benchmark rescue with architecture progress

## Workstream H: Real-Time Runtime Readiness

Goal:

- prove this is a true memory layer, not only a benchmark runner

Required metrics:

- p50 and p95 latency
- prompt tokens and total tokens
- memory growth over time
- write acceptance precision
- unsupported write rate
- stale-state error rate
- correction success rate
- deletion reliability
- provenance support rate
- abstention honesty
- maintenance stability before and after reconsolidation

Required test types:

- replay tests
- long-running trace soak tests
- maintenance regression tests
- failure-injection tests for contradictory updates and deletes

Definition of done:

- runtime quality is measured, not assumed
- the online path stays lightweight
- maintenance keeps quality stable over time

## Workstream I: Spark Shadow Evidence

Goal:

- validate the system against real Builder traffic without premature promotion

Required tasks:

- have Spark export real shadow traces
- replay them here
- report:
  - accepted writes
  - rejected writes
  - skipped turns
  - unsupported-write reasons
  - probe hit rates
  - memory-role mix
  - maintenance before/after behavior
- turn real shadow failures into substrate fixes
- rerun benchmark gates after every real runtime mutation

Definition of done:

- Spark shadow evidence is stable enough to define rollout gates
- failure classes are known and bounded
- live promotion remains a conscious decision, not an assumption

## Phase Plan

## Phase 0: Lock The Baseline

Sequence:

1. Promote the already-green next local `ProductMemory` lane.
2. Reconcile active docs and score snapshots.
3. Freeze the current benchmark and product-memory frontier ledger.

Exit criteria:

- one clean documented baseline

## Phase 1: Separate The Architecture

Sequence:

1. create `memory_extraction.py`
2. create `memory_operators.py`
3. move packet entrypoints behind `packet_builders.py`
4. reduce direct `memory_systems.py` ownership

Exit criteria:

- module boundaries are real and used

## Phase 2: Make Lifecycle Logic First-Class

Sequence:

1. extract current-state and supersession logic fully
2. formalize delete, restore, contradict, and rebuild paths
3. expand product-memory lifecycle tests where needed

Exit criteria:

- lifecycle correctness is explicit and benchmark-safe

## Phase 3: Clean Up Retrieval And Answering

Sequence:

1. make role-specific retrieval outputs explicit
2. tighten packet-level answer-candidate authority
3. reduce provider rescue dependency
4. keep exact-answer integrity under compaction

Exit criteria:

- substrate decides more of the answer than provider rescue does

## Phase 4: Finish Benchmark Completion

Sequence:

1. extend `LongMemEval_s`
2. broaden clean `LoCoMo`
3. lock canonical `GoodAI`
4. keep local `BEAM` pilot honest
5. pin official `BEAM` path when possible

Exit criteria:

- the benchmark story is broad, honest, and reproducible

## Phase 5: Add Maintenance And Scale Discipline

Sequence:

1. reflection invalidation
2. belief refresh from evidence
3. offline compaction
4. selective rehydration
5. event reconciliation

Exit criteria:

- the memory layer survives longer-lived use without quality collapse

## Phase 6: Prove Real Runtime Quality

Sequence:

1. add latency and cost reporting to all serious runs
2. measure stale-state, correction, deletion, and drift metrics directly
3. add soak and replay tests

Exit criteria:

- the repo can prove it is a practical memory layer, not just a benchmark machine

## Phase 7: Keep Spark In Shadow Until Ready

Sequence:

1. export real traces from Builder
2. replay and report here
3. fix failures in this substrate
4. rerun benchmark gates
5. define rollout criteria

Exit criteria:

- Spark has a promotion gate driven by shadow evidence

## Priority Task Queue

## Immediate

- promote the next local `ProductMemory` lane and update the active totals
- reconcile docs so one frontier snapshot is authoritative
- create the first true architecture task breakdown per module
- identify the first code migration out of `memory_systems.py`

## Next

- extract current-state and supersession logic completely
- create `memory_operators.py`
- tighten provider normalization around typed answer candidates
- run the next honest `LongMemEval_s` extension slice
- choose the next clean `LoCoMo` lane
- lock the first canonical `GoodAI` run

## After That

- add latency and token reporting to every serious comparison artifact
- measure stale-state, correction, deletion, and drift directly
- get the first real Spark shadow trace batch
- start maintenance and reconsolidation ablations

## What To Stop Doing

- stop expanding wording ladders forever once they stop teaching new substrate lessons
- stop letting provider rescue absorb every substrate weakness
- stop treating partially separated modules as finished architecture
- stop calling `BEAM` readiness finished before the evaluation surface is pinned
- stop assuming benchmark wins automatically imply product-runtime quality

## Decision Rule For Next Work

When choosing between two plausible next tasks, prefer the one that:

1. improves a reusable memory role or operator
2. helps both benchmark strength and product memory quality
3. keeps the online path lightweight
4. reduces dependence on post-hoc heuristics

## Bottom Line

The repo is no longer in the phase where the main question is whether the memory idea works.

It works well enough to justify the harder next step:

- turn the current winning lane into a state-of-the-art memory architecture
- finish the benchmark stack honestly
- prove real runtime quality
- let Spark adopt it only after shadow evidence says it is ready
