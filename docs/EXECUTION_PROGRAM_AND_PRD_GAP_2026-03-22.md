# Execution Program And PRD Gap

Date: 2026-03-22
Status: active

## Purpose

This document translates the PRD into remaining work.

It answers:

- what the vision is
- what still remains incomplete
- which systems we build first
- how the auto loop and variation loop should work
- what the phases are from here

## Vision

Build a benchmark-first agent memory system that reaches `#1`-class performance through a lightweight online path, explicit time and supersession handling, and disciplined benchmark mutation loops.

The goal is not:

- to imitate any one vendor
- to ship a generic memory SDK first
- to call one promising experiment "done"

The goal is:

- reproduce and beat the strongest relevant benchmark-native patterns
- isolate which components drive gains
- keep the winning path as lightweight and productizable as possible

## What remains from the PRD

The PRD is directionally correct, but the actual remaining work is more specific.

### Already in place

- benchmark choice
- initial research base
- benchmark doctrine
- combination doctrine
- attribution plan
- mutation packet structure
- strategy packet generation
- benchmark adapters and normalized contracts
- benchmark run manifest contract
- deterministic `full_context` and `lexical` baseline packet builders
- local scorecard contract and deterministic heuristic baseline executor
- first canonical `GoodAI LTM Benchmark` configuration lock
- `BEAM` added to the benchmark doctrine as a frontier higher-context target pending public implementation pinning

### Not yet built

1. canonical scorecards per benchmark
2. model-executed full-context baseline on real benchmark data
3. model-executed lexical baseline on real benchmark data
4. first semantic-atom baseline
5. temporal and supersession baseline
6. profile-aware routing baseline
7. shadow benchmark checks
8. ablation runner
9. promotion and rollback logging over real runs

### Still under-defined before implementation

1. exact `LoCoMo` public threshold pin
2. the retrieval trace format
3. the per-slice score aggregation format
4. the public implementation surface for `BEAM`

## Three initial systems to build

We should not start with one giant system.
We should start with three deliberately chosen systems.

### System 1: Beam-Ready Temporal Atom Router

Definition:

- `EPI + ATOM + TIME + ROUTE + REHYDRATE + ABSTAIN`

Purpose:

- establish the first lightweight serious stack that can still survive larger-context pressure

Strengths:

- should move `LongMemEval` meaningfully
- simple enough to debug
- has a direct path to `LoCoMo`, `GoodAI`, and early `BEAM` slices

Risks:

- may still lose to stable compressed-context systems on very large windows
- may need stronger evidence routing once contexts approach `BEAM` scale

### System 2: Observational Temporal Memory

Definition:

- `OBSERVE + REFLECT + TIME + PROFILE + ABSTAIN`

Purpose:

- test whether stable compressed context beats retrieval-first systems as context scales

Strengths:

- naturally aligned with `Mastra OM` style benchmark pressure
- directly relevant to `BEAM`
- stable prompt window and compression may improve product viability

Risks:

- observation drift can hide evidence loss
- compression policy can become too lossy if not evaluated carefully

### System 3: Dual-Store Event Calendar Hybrid

Definition:

- `OBSERVE + ATOM + TIME + EVENTS + ROUTE + REHYDRATE + RELATE + ABSTAIN`

Purpose:

- combine the strongest ideas from temporal atoms, event calendars, and observational compression without jumping straight to online search forests

Strengths:

- strongest upside for `LoCoMo` multi-hop slices
- strongest upside for `BEAM` if single-store systems plateau
- still less extreme than ASMR-style orchestration

Risks:

- easiest place to overcomplicate the system
- requires disciplined ablation to prove both stores are pulling their weight

## Why these three systems

This three-system ladder is useful because:

1. System 1 proves the first strong lightweight retrieval path.
2. System 2 tests whether stable compressed context is the better answer as context grows.
3. System 3 tests whether a dual-store hybrid is actually needed for frontier long-context pressure.

If System 3 still plateaus, only then do we earn the right to test heavier directions.

## Auto loop system

The loop should operate on benchmark slices, not on architecture vibes.

### Loop A: baseline loop

Build baseline -> run benchmark -> collect scorecard -> record failure slices

### Loop B: mutation loop

Pick one failure slice -> add one component family -> rerun -> compare to direct parent baseline

### Loop C: ablation loop

Take a better system -> remove one component -> rerun -> check if the component is actually necessary

### Loop D: combination loop

Combine two component families that should complement each other -> rerun -> keep only if gain exceeds cost

### Loop E: promotion loop

Only promote a system if:

- it improves the target benchmark slices
- it does not materially regress other slices
- the online cost remains justifiable
- the gain survives reruns

## Variation system

Variation should be constrained.

Allowed variation axes:

- extraction policy
- atom schema
- time and supersession logic
- profile write policy
- retrieval routing
- relation expansion
- rehydration threshold
- abstention threshold
- offline consolidation

Disallowed early variation axes:

- giant multi-agent online orchestration
- answer-ensemble forests
- RL-trained memory policy before strong heuristics
- graph-database-first redesign

Pending but not default:

- `Supermemory ASMR` style agentic search orchestration after public release and only after the three-system ladder is honestly measured

## Methodology

The program should follow this sequence.

### Phase 1: substrate

Deliver:

- benchmark adapters
- normalized contracts
- scorecard contract
- retrieval trace contract

### Phase 2: baselines

Deliver:

- model-executed full-context baseline
- model-executed lexical baseline
- semantic-atom baseline
- temporal-semantic baseline

### Phase 3: three-system ladder

Deliver:

- System 1 run
- System 2 run
- System 3 run
- ablation reports for their major components

### Phase 4: combination and ablation pressure

Deliver:

- route variants
- observation variants
- reflection and consolidation variants
- relation-expansion variants
- dual-store interaction variants

### Phase 5: heavy-path qualification

Deliver:

- proof that lighter and medium-weight systems plateau first
- only then test graph materialization, search agents, answer forests, or learned policies

### Phase 6: doctrine promotion

Deliver:

- final promoted architecture
- rejected variants with reasons
- benchmark-grounded doctrine update

## Success conditions

We should consider the program healthy if:

1. every benchmark run produces a reproducible scorecard
2. every stronger system has a direct parent comparison
3. every promoted component survives ablation review
4. no heavier system is kept on style points alone

## Immediate next build steps

Current active lane:

- `observational_temporal_memory + MiniMax-M2.7`
- real internal result on the first 25 `LongMemEval_s` samples: `13/25` (`0.52`)
- current same-slice comparison: `beam_temporal_atom_router + MiniMax-M2.7` at `3/25` (`0.12`)

Immediate next build steps:

1. Write the 25-sample scorecards into stable benchmark artifacts.
2. Bucket the 12 remaining `observational_temporal_memory` misses by failure type.
3. Optimize for exact-span entity, numeric, and short categorical answers before scaling to larger slices.
4. Re-run the same 25-sample slice after each bounded mutation.
5. Expand the lead system to a larger `LongMemEval` slice once the 25-sample miss rate improves.
6. Only then shift the same provider path onto `LoCoMo`.

## Sources

- [PRD.md](/C:/Users/USER/Desktop/domain-chip-memory/docs/PRD.md)
- [FIRST_VERSION_RESEARCH_LOCK.md](/C:/Users/USER/Desktop/domain-chip-memory/docs/FIRST_VERSION_RESEARCH_LOCK.md)
- [COMBINATION_SEARCH_PROGRAM.md](/C:/Users/USER/Desktop/domain-chip-memory/docs/COMBINATION_SEARCH_PROGRAM.md)
- [BENCHMARK_AUTOLOOP_PROGRAM.md](/C:/Users/USER/Desktop/domain-chip-memory/docs/BENCHMARK_AUTOLOOP_PROGRAM.md)
- [FRONTIER_MEMORY_SYSTEMS_COMPARATIVE_ANALYSIS_2026-03-22.md](/C:/Users/USER/Desktop/domain-chip-memory/docs/FRONTIER_MEMORY_SYSTEMS_COMPARATIVE_ANALYSIS_2026-03-22.md)
