# Benchmark Autoloop Program

Date: 2026-03-22
Status: active

## Intent

The memory chip exists to reach benchmark leadership.

Not to publish a nice architecture diagram.
Not to ship a vague "memory SDK."
Not to stop when the first decent score appears.

It exists to keep iterating until the benchmark stack is beaten honestly.

## Primary goal

Become `#1` on the target benchmark stack with a reproducible, benchmark-native memory system.

Current ordered target stack:

1. `LongMemEval`
2. `LoCoMo`
3. `GoodAI LTM Benchmark`
4. `BEAM`

Shadow benchmark:

- `ConvoMem`

## Non-negotiable constraints

1. No benchmark leakage.
2. No invented public thresholds.
3. No promotion of a mutation without reruns.
4. No hiding regressions behind overall averages.
5. No architecture complexity that is not buying benchmark signal.

## Program loop

### Loop 1: benchmark pinning

Goal:

- pin exact public frontier numbers and benchmark definitions

Outputs:

- target ledger
- benchmark adapter contract
- evaluation contract

### Loop 2: baseline establishment

Goal:

- beat naive and strong baselines before novelty work

Baselines:

- full context
- vector or BM25 retrieval
- summary-only retrieval
- semantic-atom retrieval without temporal logic

### Loop 3: lightweight core

Goal:

- build the smallest temporal semantic memory that can move the needle

Required pieces:

- raw episode store
- memory atoms
- supersession logic
- temporal fields
- retrieval router

### Loop 4: failure slicing

Goal:

- stop treating memory as one scalar score

Slice failures by:

- stale fact retrieval
- wrong time grounding
- missing evidence
- over-answering
- preference miss
- multi-hop miss

### Loop 5: bounded mutation

Goal:

- mutate only one family at a time

Mutation families:

- extraction
- temporal resolution
- memory atom shape
- retrieval route
- evidence rehydration
- abstention policy
- offline consolidation

### Loop 6: promote or rollback

Promote only if:

- overall score improves
- target category improves
- no major abstention regression
- latency and cost stay acceptable

Otherwise:

- rollback
- record contradiction
- move to next mutation

## Lightweight-first doctrine

If two systems achieve similar accuracy, prefer the one with:

- fewer online model calls
- fewer tokens
- smaller online context assembly
- simpler retrieval path
- lower infra dependence

That means:

- offline consolidation is good
- giant online answer forests are suspicious
- graph databases are optional, not mandatory
- stable compressed context is a first-class contender once `BEAM` pressure enters the program

## What success looks like

The first real success state is:

- `LongMemEval` frontier matched or exceeded
- `LoCoMo` competitive or leading
- `GoodAI LTM Benchmark` strong across the chosen published configuration set
- `BEAM` reproduced on a commit-pinned official public surface and competitive there
- online path still small enough to feel productizable
- `ConvoMem` shadow checks still clean enough that we are not overbuilding retrieval

The first real architecture comparison state is:

- Beam-Ready Temporal Atom Router has been run
- Observational Temporal Memory has been run
- Dual-Store Event Calendar Hybrid has been run
- all three have category-level scorecards and cost traces

## Immediate next actions

1. Pin the exact public `LoCoMo` leader threshold.
2. Track `Supermemory ASMR` as a pending experimental frontier claim until its public release is available.
3. Pin the exact public `BEAM` repo commit, datasets, and evaluation flow.
4. Run the Beam-Ready Temporal Atom Router as the first serious benchmark candidate.
5. Run Observational Temporal Memory as the first compression-first counterexample.
6. Promote the Dual-Store Event Calendar Hybrid only after the first two systems expose the real long-context failure pattern.
