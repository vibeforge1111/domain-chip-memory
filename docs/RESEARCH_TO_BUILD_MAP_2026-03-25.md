# Research To Build Map

Date: 2026-03-25
Status: active synthesis

## Purpose

This memo consolidates the March 24-25 research and program docs into one execution-facing map.

It answers:

- what the recent research changed
- which ideas are already part of repo doctrine
- which ideas are still not implemented in code
- what the next build order should be

This is not a new benchmark claim.
It is a translation layer between the research stack and the next code changes.

## Current local truth

The current local lead remains:

- `observational_temporal_memory + MiniMax-M2.7`

What is actually proven locally:

- contiguous measured `LongMemEval_s` coverage through `200/200`
- clean bounded `LoCoMo` coverage through `conv-26 q150`
- clean `LoCoMo conv-30 q1-25`

What is not yet proven locally:

- full `LongMemEval_s`
- a broader clean `LoCoMo` frontier beyond the current bounded lanes
- a canonical `GoodAI LTM Benchmark` run
- any in-repo `BEAM` evaluation path

The repo should keep using that distinction.

## What The Recent Research Changed

The March 24-25 research stack converged on six practical conclusions.

### 1. Retrieval quality is still the main bottleneck

The research refresh and deep scan both reinforce that the decisive gains come from:

- better evidence selection
- better update handling
- better temporal routing
- better rehydration discipline

Not from more answer-side prompt cleverness alone.

### 2. Evidence, current state, and belief must be separated

The strongest recurring lesson from `Hindsight`, `MIRIX`, `O-Mem`, and the repo's own failures is:

- raw evidence should not be mixed casually with reflections
- current-state answers need their own surface
- belief or reflection memory should stay explicitly derived

This is now a core architecture requirement, not a stylistic preference.

### 3. Temporal memory and supersession must be first-class

`Chronos`, `Supermemory`, and the repo's own `LongMemEval_s` wins all point the same way:

- dual time fields matter
- mutable facts need explicit supersession
- current-state selectors should not stay embedded in packet-local heuristics

### 4. The hot path must stay small

`Mastra OM`, `LightMem`, `SimpleMem`, and the `BEAM` memo all support:

- bounded visible memory
- compact stable windows
- retrieve small units first
- rehydrate raw evidence only when needed

This is the clearest path toward `BEAM` pressure without turning every query into prompt sprawl.

### 5. Generic operators are better than question-shaped branches

The research and the March 25 architecture memos both reject the same failure mode:

- benchmark-shaped local rescues can close slices
- but they become architecture debt if they do not collapse into reusable operators

The first operator layer should center on:

- current-state lookup
- count and sum
- compare and diff
- temporal before-after
- preference synthesis
- abstention

### 6. Offline maintenance will matter once scale grows

`All-Mem`, `FadeMem`, `LightMem`, `MemoryOS`, and `MemOS` all push the same direction:

- merge, split, update, and supersede memory offline
- introduce forgetting or decay carefully
- keep immutable evidence recoverable even when the visible memory topology changes

This is not the first code task, but it is the main scale-up direction after the current substrate cleanup.

## Highest-Value Borrow Queue

These are the most actionable research borrow paths from the recent scan.

### `Hindsight`

Borrow:

- evidence versus belief separation
- explicit `retain`, `recall`, and `reflect` thinking

Closest repo mutation:

- `M3` evidence-versus-belief packet split

### `Mnemis`

Borrow:

- dual-route retrieval
- global selection for hard questions

Closest repo mutation:

- `M2` dual-route retrieval

### `Membox`

Borrow:

- topic continuity at write time
- topical episode grouping before atomization

Closest repo mutation:

- `M1` topic continuity write path

### `O-Mem` and `MIRIX`

Borrow:

- stronger profile versus event separation
- explicit memory-role separation

Closest repo mutation:

- `M6` profile-versus-event separation

### `E-mem`

Borrow:

- episodic reconstruction
- tiny targeted rehydration instead of wider packet growth

Closest repo mutation:

- `M7` episodic reconstruction lane

### `All-Mem` and `FadeMem`

Borrow:

- offline maintenance
- merge, split, update, supersede
- bounded forgetting and decay

Closest repo mutations:

- `M4` offline maintenance
- `M5` bounded forgetting and decay

### `Chronos` and `Supermemory`

Borrow:

- event-calendar and time-range logic
- dual time fields
- alias-aware temporal routing
- atom-first retrieval with rehydration

Closest repo effect:

- strengthens the active `LongMemEval_s` lane without requiring a new baseline family first

## What Is Already Encoded In Repo Doctrine

These ideas are already accepted in the docs, even if code is lagging.

### Accepted architecture direction

- explicit memory-role separation
- typed `answer_candidate` metadata
- current-state and supersession extraction
- reusable reasoning operators
- `BEAM` as architecture pressure
- `LongMemEval_s` and clean `LoCoMo` as regression gates

Primary docs:

- `docs/UNIFIED_MEMORY_SYSTEM_PROGRAM_2026-03-25.md`
- `docs/MEMORY_ARCHITECTURE_EVOLUTION_PLAN_2026-03-25.md`
- `docs/BEAM_READINESS_PROGRAM_2026-03-24.md`
- `docs/MEMORY_MUTATION_MATRIX_2026-03-24.md`

### Accepted benchmark doctrine

- treat contaminated `LoCoMo conv-26 q151-199` as a separate audit lane
- run real baselines before mutation
- preserve source-of-truth artifacts
- do not confuse public claims with local reproduction

Primary docs:

- `docs/TOMORROW_START_CHECKLIST_2026-03-26.md`
- `docs/SESSION_LOG_2026-03-25.md`
- `research/benchmark_grounded/benchmark_summary.json`
- `docs/RESEARCH_SOURCING_DOCTRINE_2026-03-24.md`

## What Is Still Missing In Code

The current codebase still lags behind the doctrine in four obvious places.

### 1. `answer_candidate` metadata is still mostly untyped

Current surface:

- `src/domain_chip_memory/contracts.py`

Missing:

- explicit `answer_candidate_type`
- exact short-answer classes such as:
  - `exact_numeric`
  - `currency`
  - `date`
  - `location`
  - `preference`
  - `current_state`
  - `abstain`

### 2. Current-state logic is still too implicit

Current surface:

- `src/domain_chip_memory/memory_systems.py`

Missing:

- a dedicated current-state or supersession module
- explicit mutable-fact selection boundaries

### 3. Evidence and belief are not fully separated in packet construction

Current surfaces:

- `src/domain_chip_memory/memory_systems.py`
- `src/domain_chip_memory/providers.py`

Missing:

- packet sections that clearly distinguish:
  - immutable evidence
  - derived belief
  - current answer candidate

### 4. Too much exact-answer integrity still lives in provider rescue

Current surface:

- `src/domain_chip_memory/providers.py`

Missing:

- stronger substrate-level answer typing
- operator outputs that preserve exact spans before generation

## Recommended Build Order From Here

This is the clean synthesis of the research stack and the March 25 restart plan.

1. Run the untouched `LongMemEval_s 201-225` baseline and record the true miss set.
2. Add typed `answer_candidate` metadata in contracts and packet metadata surfaces.
3. Extract current-state and supersession logic into a dedicated module boundary.
4. Split evidence, current-state, and belief packet sections more explicitly.
5. Add `M1` topic continuity write-path support.
6. Add `M2` dual-route retrieval only for hard or low-confidence cases.
7. Choose the next clean `LoCoMo` frontier lane after `conv-26 q150`.
8. Lock the first canonical `GoodAI LTM Benchmark` run.
9. Define the first `BEAM` adapter and scorecard contract skeleton.
10. Only after the substrate is cleaner, begin offline maintenance and forgetting experiments.

## What Not To Do

- do not keep growing question-shaped rescue logic before checking whether a generic operator can solve the miss class
- do not keep using provider rescue as the permanent home for correctness
- do not treat public paper claims as local proof
- do not jump into graph-database-first or multi-agent-heavy infra before the simpler structural fixes are measured
- do not reorganize for `BEAM` in ways that break already-closed `LongMemEval_s` or clean `LoCoMo` slices

## Bottom Line

The recent research does not say the current lane is wrong.

It says the current lane is good enough to justify consolidation.

The repo should now evolve from:

- a strong benchmark-closing packet builder

toward:

- a memory system with explicit evidence memory
- explicit current-state memory
- explicit belief memory
- stronger temporal and supersession handling
- generic reasoning operators
- a bounded online path with offline maintenance ready for `BEAM` pressure
