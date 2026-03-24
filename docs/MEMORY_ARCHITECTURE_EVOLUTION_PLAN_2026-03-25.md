# Memory Architecture Evolution Plan

Date: 2026-03-25
Status: research-grounded, implementation-directed

## Why this document exists

The repo now has a strong active benchmark lane, but that does not automatically mean the memory architecture is clean.

The current system is good at:

- extracting dense observations
- preserving short exact answers
- synthesizing bounded aggregates
- closing benchmark slices fast

The current system is still weak architecturally in three ways:

- too much logic is concentrated in `memory_systems.py`
- too much answer integrity depends on provider-side rescue in `providers.py`
- evidence, inference, and current-state views are not yet separated as first-class memory roles

This document translates both the repo's earlier research base and fresh 2025-2026 literature into a concrete build program for this codebase.

## Honest current read

The current winning lane is `observational_temporal_memory + MiniMax-M2.7`.

That lane is real. It closed contiguous measured `LongMemEval_s` coverage through `200/200`, and it remains the best working substrate in-repo. But the mechanism of many recent wins matters:

- better `answer_candidate` ranking and preservation
- stronger aggregate synthesis
- preference and guidance rescue
- more question-aware packet shaping

Those are valid improvements, but they are still more benchmark-shaped than architecture-complete.

The main risk is straightforward:

- if we continue only by adding question-shaped rescue logic, the repo becomes a powerful patchwork rather than a durable memory system

## What the research now says

The earlier repo research was directionally correct.

The fresh papers reinforce five points:

### 1. Hierarchy wins

`LongMemEval` frames the design space as `indexing -> retrieval -> reading`, and its main gains come from better structure, not prompt cleverness:

- session decomposition
- fact-augmented indexing
- time-aware query expansion

Source:

- https://arxiv.org/abs/2410.10813

`LightMem` reaches the same conclusion from a different angle: keep online memory small, push heavier consolidation offline, and separate sensory, short-term, and long-term roles.

Source:

- https://arxiv.org/abs/2510.18866

### 2. Temporal memory must be explicit

`LoCoMo` stresses long-range temporal and causal dynamics across many sessions, which means a flat fact store is not enough.

Source:

- https://arxiv.org/abs/2402.17753

`Chronos` strengthens that point further with event tuples, resolved time ranges, alias handling, and event-calendar retrieval.

Source:

- https://arxiv.org/abs/2603.16862

### 3. Evidence and inference must be separated

`Hindsight` is especially important here. It argues that current systems blur evidence and inference, then proposes distinct logical networks plus `retain`, `recall`, and `reflect` operations.

Source:

- https://arxiv.org/abs/2512.12818

This maps directly onto a known weakness in our repo: provider rescue currently protects exact answers, but the substrate itself still mixes:

- raw evidence
- synthesized beliefs
- current-state views

### 4. Memory needs lifecycle management, not only retrieval

`Mem0` and `MemoryOS` both push the same theme:

- memory should be extracted, consolidated, updated, and retrieved as a governed system
- hierarchy and update flow matter as much as retrieval quality

Sources:

- https://arxiv.org/abs/2504.19413
- https://arxiv.org/abs/2506.06326

### 5. Benchmark closure and architecture evolution should run in parallel

The strongest lesson from the repo and the literature is the same:

- benchmark pressure is useful
- benchmark-shaped local fixes are not enough on their own

We should keep the benchmark loop, but we should stop pretending it is the whole architecture program.

## Recommended target architecture for this repo

The repo should evolve from one dominant monolithic packet builder into five explicit memory roles.

### 1. Raw episodic store

Purpose:

- preserve full source truth
- preserve provenance
- support selective rehydration

What lives here:

- normalized turns
- session ids
- timestamps
- raw image-caption metadata
- source spans

Repo implication:

- keep the current normalized benchmark substrate as the base
- treat this as immutable evidence, not as answer logic

### 2. Structured evidence memory

Purpose:

- convert raw turns into reusable, queryable units

What lives here:

- facts
- events
- preferences
- relationships
- numeric observations
- location observations

Important rule:

- these are evidence-bearing units, not beliefs

Repo implication:

- split extraction logic out of `memory_systems.py`
- create explicit extraction and normalization surfaces for:
  - facts
  - events
  - preferences
  - counts and amounts

### 3. Current-state and profile memory

Purpose:

- maintain the latest valid view of mutable user state

What lives here:

- stable profile
- current preference
- latest job, city, project, routine, relationship status
- superseded versus active values

Important rule:

- this layer should answer "what is true now", not store every historical mention equally

Repo implication:

- current supersession handling should become a first-class module instead of remaining embedded in packet selection heuristics

### 4. Reflection and belief memory

Purpose:

- hold derived summaries, synthesized comparisons, and answer-shaped beliefs

What lives here:

- reflected observations
- aggregate summaries
- derived current-state notes
- model-generated candidate beliefs with provenance

Important rule:

- this layer must never be confused with raw evidence

Repo implication:

- belief packets stay useful, but they should be explicitly tagged as derived memory
- answer generation should know whether it is reading evidence or belief

### 5. Retrieval and reasoning operators

Purpose:

- answer from the right memory role with the right operator

Operators to make first-class:

- exact fact lookup
- current-state lookup
- temporal before-after lookup
- event-chain lookup
- count and sum
- compare and diff
- preference synthesis
- abstention

Repo implication:

- move away from question-shaped branches toward reusable operators selected by route type

## What should change in the codebase

### A. Refactor `memory_systems.py` by memory role

Today it carries:

- extraction
- observation building
- reflection
- retrieval scoring
- aggregate synthesis
- question-specific handling
- packet assembly

That is too much.

Recommended split:

- `memory_extraction.py`
- `memory_views.py`
- `memory_updates.py`
- `memory_operators.py`
- `packet_builders.py`

This is not just cleanliness. It will let us answer:

- what is evidence extraction
- what is update logic
- what is retrieval
- what is answer shaping

### B. Move exact-answer integrity closer to the substrate

`providers.py` currently does valuable rescue work, but too much correctness still depends on post-generation correction.

Recommendation:

- keep provider rescue as a guardrail
- move exact numeric, currency, and short-span answer integrity earlier into operator outputs and packet contracts

The system should produce stronger typed answer candidates before model generation:

- `answer_candidate_type: exact_numeric`
- `answer_candidate_type: currency`
- `answer_candidate_type: date`
- `answer_candidate_type: preference`
- `answer_candidate_type: abstain`

### C. Add a real reconsolidation layer

The repo already has reflection-like behavior. It does not yet have strong reconsolidation doctrine.

We should add explicit operations:

- `retain`
- `update`
- `supersede`
- `reflect`
- `retire`

This is the point where the repo can stop accumulating stale duplicate state.

### D. Add explicit temporal structures

The code already has event-calendar elements, but the active winning lane still leans more on observations than on true event-time machinery.

We should add:

- normalized event spans
- document time versus event time
- alias resolution
- time range filters
- current-state versus historical-state selectors

This is the clearest way to generalize beyond the current `LongMemEval_s` closures.

### E. Separate evidence scoring from answer scoring

Right now retrieval score and answer usefulness are often intertwined.

We should separate:

- evidence relevance
- answerability
- belief usefulness

That will make ablations much cleaner and reduce accidental overfitting to benchmark answer shapes.

## Recommended implementation order

This order is meant to preserve current benchmark wins while improving the architecture underneath them.

### Track 1: Keep the benchmark frontier moving

Immediate benchmark work remains:

1. `LongMemEval_s 201-225` baseline
2. clean post-`q150` `LoCoMo` slice
3. canonical `GoodAI LTM Benchmark` run
4. actual `BEAM` adapter and scorecard work

### Track 2: Start substrate consolidation in parallel

This should start immediately, not after all benchmarks are done.

First substrate steps:

1. introduce typed answer-candidate metadata in contracts
2. extract current-state and supersession logic into a dedicated module
3. isolate generic operators for:
   - count and sum
   - compare and diff
   - temporal before-after
   - preference synthesis
4. split evidence memory from belief memory in packet assembly

### Track 3: Run ablations on architecture, not just prompts

Every meaningful improvement should be tagged as one of:

- extraction improvement
- update and supersession improvement
- retrieval improvement
- operator improvement
- provider rescue improvement
- scorer normalization improvement

This will tell us whether the architecture is truly improving or only getting better at answer cleanup.

## What tomorrow should look like

Tomorrow should not be another pure mutation day.

Recommended order:

1. Run `LongMemEval_s 201-225` baseline and collect the real miss set.
2. In parallel, define typed `answer_candidate` metadata and current-state module boundaries.
3. If the new slice exposes more aggregate and current-state failures, fix them through operators first, not new one-off question handlers.
4. Once `201-225` is stable, move to a clean `LoCoMo` slice.
5. Only after that, lock the first canonical `GoodAI` frontier run.

## What to stop doing

- stop letting provider rescue absorb every substrate weakness
- stop adding benchmark-specific branches before checking whether a generic operator can solve the class
- stop treating contaminated benchmark regions as honest frontier lanes
- stop merging evidence, belief, and current-state logic into one retrieval surface

## Bottom line

The repo is already strong enough to prove that the current lane is not fake.

But if the goal is an actually excellent memory architecture, the next phase has to be:

- more explicit memory-role separation
- more lifecycle and reconsolidation
- stronger temporal structure
- generic reasoning operators
- cleaner evidence versus belief boundaries

That is the path from "strong benchmark-closing system" to "strong memory architecture."
