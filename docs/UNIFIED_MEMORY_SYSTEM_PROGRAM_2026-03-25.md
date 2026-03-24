# Unified Memory System Program

Date: 2026-03-25
Status: active execution doctrine

## Why this document exists

The repo should stop thinking in separate silos:

- close `LongMemEval`
- then close `LoCoMo`
- then someday become `BEAM`-ready

That sequencing is too weak.

The correct target is one memory architecture that can:

- keep winning bounded `LongMemEval_s` slices
- generalize across clean `LoCoMo` conversation slices
- survive the larger-context pressure that `BEAM` will impose

This document defines that unified target.

## Core principle

`BEAM` is not just a bigger context benchmark.

It is pressure for:

- memory selection
- memory governance
- compression quality
- update and supersession
- selective rehydration
- exactness preservation under long-horizon compaction

If we only keep adding local benchmark rescues, we may continue to improve on bounded slices while still building the wrong substrate for `BEAM`.

## Unified win condition

The system should be treated as strong only if all three are true:

1. it continues to close real `LongMemEval_s` slices without regression
2. it generalizes across clean `LoCoMo` slices and conversations
3. it becomes structurally compatible with `BEAM`-scale context pressure without needing a different architecture

## Target architecture

The target architecture is:

- small online working memory
- immutable raw episodic archive
- structured evidence memory
- current-state and profile memory
- derived belief and reflection memory
- temporal-event layer
- reusable reasoning operators
- selective rehydration path
- offline consolidation path

This means the repo should no longer treat the active winner as just one packet builder. It should become a governed memory system with explicit roles.

## Benchmark-to-architecture mapping

### LongMemEval

What it rewards most:

- current-state selection
- exact fact retrieval
- temporal disambiguation
- compact exact answers
- abstention discipline

What that should force architecturally:

- strong current-state memory
- typed exact answer candidates
- temporal filtering
- exact-span preservation

### LoCoMo

What it rewards most:

- long-range conversational linkage
- causal and temporal relation handling
- entity continuity across sessions
- multi-hop recall

What that should force architecturally:

- stronger event and relation memory
- better entity alias handling
- explicit evidence versus belief separation
- better multi-hop operators

### BEAM

What it should reward most:

- long-horizon memory governance
- strong compression without irreversible answer loss
- low-noise durable storage
- budgeted retrieval and rehydration
- scalable update and consolidation

What that should force architecturally:

- explicit memory tiers
- write policy
- reconsolidation policy
- offline consolidation worker
- compaction invariants

## What the system must do well simultaneously

### 1. Write less, but write better

Every remembered unit should pass stronger keepability filters.

That means:

- not every mention becomes durable memory
- exact answer-bearing spans remain recoverable
- stable traits are separated from transient events
- conflicting updates are tracked, not flattened

### 2. Preserve exactness through compression

Recent benchmark wins made this obvious.

The system must preserve:

- short numerics
- money amounts
- dates
- locations
- current-state values

This should happen in the substrate before provider rescue.

### 3. Distinguish evidence from inference

The system should know whether a retrieved unit is:

- raw evidence
- structured extracted evidence
- current-state view
- derived belief

That distinction is necessary for both benchmark honesty and large-context reliability.

### 4. Make temporal reasoning first-class

We need:

- event time
- document time
- date-range normalization
- alias resolution
- before-after operators
- supersession-aware current-state selectors

### 5. Rehydrate only when necessary

The durable online path should stay compact.

The full raw archive should be consulted only when:

- a precise span is needed
- a conflict must be resolved
- a count or comparison needs exact grounding
- a belief needs source verification

## What to build next in code

### Module separation

Break the current monolith into:

- `memory_extraction.py`
- `memory_updates.py`
- `memory_views.py`
- `memory_operators.py`
- `packet_builders.py`

### Stronger contracts

Add typed answer candidates:

- `exact_numeric`
- `currency`
- `date`
- `location`
- `preference`
- `current_state`
- `abstain`

Add role labels for retrieved units:

- `raw_episode`
- `structured_evidence`
- `current_state`
- `belief`
- `event`

### Evaluation changes

Every mutation should be tagged as:

- benchmark closure only
- substrate improvement
- `BEAM` transfer improvement
- answer-rescue improvement

That will keep us honest about where gains are coming from.

## Tomorrow-first implementation priorities

The next build day should not be a vague continuation.

It should begin with these concrete goals:

1. establish the real miss set for `LongMemEval_s 201-225`
2. define typed `answer_candidate` metadata in contracts
3. extract current-state and supersession logic from packet-local heuristics into a dedicated module surface
4. choose the next clean `LoCoMo` lane after `conv-26 q150`
5. pin the first canonical `GoodAI LTM Benchmark` configuration
6. define the first `BEAM` adapter and scorecard contract skeleton if the implementation surface is available

## What success would look like one week from now

At the end of the next serious block of work, the repo should ideally have:

- `LongMemEval_s` extended beyond `200`
- another clean `LoCoMo` slice closed on a different conversation or post-`q150` lane
- typed answer-candidate contracts in code
- a dedicated current-state/supersession module
- the first generic operator layer for:
  - count and sum
  - compare and diff
  - temporal before-after
  - preference synthesis
- a pinned `GoodAI` source-of-truth run
- a real `BEAM` contract surface, even if not yet fully executed

## Bottom line

The repo should now operate under one thesis:

- every benchmark mutation should either improve the current benchmark frontier or make the architecture more transferable to `BEAM`

If it does neither, it is likely the wrong work.
