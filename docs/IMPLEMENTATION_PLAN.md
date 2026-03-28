# Memory System Implementation Plan

Date: 2026-03-29
Status: active execution doctrine

## Purpose

This is the current implementation plan for `domain-chip-memory`.

It replaces the older scaffold-era implementation framing.

The job now is not to invent a benchmark substrate from scratch.
The job now is to turn the current strong-but-partially-proven system into:

- a benchmark-leading memory architecture
- a trustworthy real memory layer
- a measured runtime system
- a narrow, integration-safe substrate for Spark shadow use

## Planning Doctrine

This plan is governed by three rules:

1. We optimize for truth, not score theater.
2. We optimize for architecture quality, not benchmark-specific hacks.
3. We leave room for intent-driven work, not only rigid checklists.

That means:

- exact tasks matter
- open-ended intent lanes also matter
- any mutation that improves one benchmark but weakens the memory substrate is suspect
- any mutation that improves the substrate but is never benchmark-verified is unfinished

## Current Honest State

What is strongly proven right now:

- local `ProductMemory` on the checked-in corpus is `1266/1266` for both promoted lead systems
- local `ProductMemory` is source-aligned on that same full lane for both promoted lead systems
- contiguous measured `LongMemEval_s` coverage is currently `200/200`
- clean bounded `LoCoMo` slices are strong on the active lead lane
- the local `BEAM` pilot ladder is active and green on the promoted slices
- the monolith breakup is materially real; `memory_systems.py` is now only a compatibility shell

What is strong but not fully proven:

- `LoCoMo` beyond the current clean bounded slices
- `BEAM` as full official benchmark proof rather than local pilot pressure
- the amount of win coming from substrate quality versus provider rescue
- real runtime quality under long-running product traffic

What is still unknown or under-measured:

- full-benchmark `LongMemEval`
- broad clean `LoCoMo`
- first canonical `GoodAI LTM Benchmark` reproduction
- true official `BEAM` reproduction path in-repo
- p50/p95 latency under serious runs
- deletion reliability as a measured runtime metric
- correction success rate as a measured runtime metric
- memory drift rate across maintenance cycles
- Spark Builder shadow behavior under real trace batches

## Benchmark Doctrine

Use the benchmark stack this way:

- `BEAM` is the core proof benchmark for architecture quality
- `LongMemEval_s` is the clean long-conversation correctness guardrail
- clean `LoCoMo` is the conversational-linkage and temporal-reasoning guardrail
- local `ProductMemory` is the fastest truth test for memory lifecycle behavior

Interpretation:

- if `BEAM` improves but `LongMemEval_s` or clean `LoCoMo` regresses, we may be building the wrong system
- if `LongMemEval_s` and `LoCoMo` improve but `BEAM` transfer stays weak, we may still be building a benchmark-shaped substrate
- if all three improve but `ProductMemory` degrades, we are not building a real memory layer

## Implementation North Star

Build one memory system that is:

- role-clean
- source-aligned
- correction-safe
- deletion-safe
- supersession-aware
- provenance-visible
- abstention-honest
- large-context capable
- operationally practical

## Architecture Target

The target architecture has these runtime roles:

1. Raw episodic archive
2. Structured evidence memory
3. Current-state and profile memory
4. Temporal-event memory
5. Belief and reflection memory
6. Working memory and scratchpad
7. Offline maintenance and reconsolidation path

These roles must become real runtime truths, not only documentation categories.

## Proven Strengths To Preserve

Do not regress the parts that are already meaningfully strong:

- exact answer-bearing proposition recovery
- current-state answering on the local product-memory lane
- delete and restore handling on the local product-memory lane
- evidence-preserving historical reconstruction
- ambiguity abstention
- dense pronoun and temporal wording disambiguation
- exactness on the measured `LongMemEval_s` coverage
- clean bounded `LoCoMo` linkage behavior

## Main Risks

The current main risks are:

- provider rescue still owns too much correctness
- some benchmark wins may still be answer-shape-sensitive
- `BEAM` local pilot success may be mistaken for official proof
- runtime quality is still more inferred than directly measured
- role separation is still not fully explicit in storage and retrieval behavior

## Workstreams

### Workstream A: Lock The Honest Frontier

Purpose:

- make sure the repo has one truthful current-state snapshot

Required outputs:

- one source-of-truth frontier status doc
- one source-of-truth implementation plan
- one source-of-truth task queue
- one source-of-truth current assessment doc

Definition of done:

- restart paths no longer depend on reading multiple historical handoff notes

### Workstream B: Complete The Proof Stack

Purpose:

- turn partial benchmark strength into an honest complete proof story

Required outputs:

- extend `LongMemEval_s` beyond the currently measured frontier
- broaden clean `LoCoMo` coverage beyond the current bounded slices
- lock the first canonical `GoodAI` run
- maintain local `BEAM` pressure lanes
- pin and reproduce the official `BEAM` path

Definition of done:

- each benchmark has a pinned target, reproducible run path, and honest status

### Workstream C: Finish Role-Clean Memory Architecture

Purpose:

- make the architecture genuinely clean instead of benchmark-shaped

Required outputs:

- explicit lifecycle operators for `create`, `update`, `delete`, `restore`, `supersede`, and `contradict`
- explicit read operators for current state, historical state, evidence, events, and abstention
- role-clean store boundaries
- evidence-versus-belief separation
- reduced correctness burden inside provider rescue

Definition of done:

- provider rescue is a guardrail, not the primary correctness engine

### Workstream D: Measure Real Runtime Quality

Purpose:

- stop inferring runtime quality from benchmark wins

Required outputs:

- p50 latency
- p95 latency
- prompt tokens
- total tokens
- memory growth
- stale-state error rate
- correction success rate
- deletion reliability
- provenance support rate
- abstention honesty
- maintenance stability
- memory drift rate

Definition of done:

- runtime quality can be inspected directly in artifacts

### Workstream E: Spark Shadow Validation

Purpose:

- prove the substrate under real product traces without premature live rollout

Required outputs:

- replayable Builder trace batches
- shadow reports on writes, rejections, probes, and role mix
- trace-backed failure taxonomy
- mutation loop from shadow failures back into substrate fixes

Definition of done:

- Spark promotion gates are evidence-based, not intuition-based

## Intent Lanes

These are deliberately open-ended on purpose.

They are not excuses to wander.
They are where we allow ourselves to push beyond literal checklists when the architecture needs it.

### Intent Lane 1: Make Memory Roles Feel Real

Prompt:

- if this system had to survive messy real users for months, what role boundary would break first

Allowed work:

- new role contracts
- new retrieval operators
- store boundary cleanup
- belief/evidence separation cleanup

### Intent Lane 2: Make Current-State Handling Unbreakable

Prompt:

- what would make delete, correction, restore, and supersession fail under realistic complexity

Allowed work:

- lifecycle stress cases
- operator cleanup
- stale-state diagnostics
- rollback and restore semantics

### Intent Lane 3: Make Large-Context Pressure Honest

Prompt:

- what would fail if context size stopped being forgiving

Allowed work:

- `BEAM`-driven architecture mutations
- retrieval budget discipline
- compaction and maintenance work
- working-memory and scratchpad refinement

### Intent Lane 4: Make Benchmark Wins Transfer

Prompt:

- is this gain true architecture quality or just benchmark convenience

Allowed work:

- ablations
- cross-benchmark reruns
- source-alignment checks
- product-memory transfer checks

## Mutation Acceptance Rules

Keep a change only if it satisfies one of these:

- improves the architecture and survives the active gates
- improves benchmark performance and clearly transfers to product-memory quality
- improves runtime quality without degrading benchmark integrity

Reject or quarantine a change if it:

- only helps one benchmark in a question-shaped way
- weakens source alignment
- increases provider rescue dependence
- regresses deletion, correction, abstention, or provenance behavior

## Required Test Classes

Every serious architecture mutation should be mapped to these test classes:

- local `ProductMemory`
- local `BEAM`
- targeted `LongMemEval_s`
- targeted clean `LoCoMo`
- runtime metrics capture when behavior affects cost or latency
- shadow replay checks when behavior affects SDK/runtime exposure

## Immediate Phase Order

1. Lock the honest current-state docs.
2. Finish the next local `ProductMemory` promotion and keep the full-lane truth explicit.
3. Update the benchmark doctrine around `BEAM`, `LongMemEval_s`, and clean `LoCoMo`.
4. Pin the official `BEAM` reproduction path.
5. Extend the measured `LongMemEval_s` frontier.
6. Choose and close the next clean `LoCoMo` lane.
7. Add direct runtime metrics.
8. Get the first real Spark shadow trace batch.

## Definition Of Success

We should call this program successful only when:

- the benchmark story is broad, honest, and reproducible
- the architecture is role-clean in runtime reality
- provider rescue is only a guardrail
- runtime quality is measured directly
- Spark shadow evidence says the system is safe enough to promote carefully

Until then, the right mindset is:

- strong
- promising
- incomplete

