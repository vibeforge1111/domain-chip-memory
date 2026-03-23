# Agent Memory Implementation Plan

Date: 2026-03-22
Status: phase planning

## Phase 0: Research scaffold

Goal:

- establish the same repo shape as the other Spark domain chips
- lock the first build thesis with enough source-backed research to constrain implementation

Deliverables:

- manifests
- docs
- research lanes
- schemas
- watchtower and evaluator
- first-version research lock

## Phase 1: Benchmark substrate

Goal:

- make the benchmarks first-class local objects

Deliverables:

- benchmark adapters for `LongMemEval`, `LoCoMo`, and `GoodAI LTM Benchmark`
- normalized session and question contracts
- baseline runner
- public target ledger refresh command

Shadow deliverable:

- `ConvoMem` regression adapter or compatible evaluator path

Frontier deliverable:

- `BEAM` adapter contract once the public implementation surface is pinned

## Phase 2: Baseline memory systems

Goal:

- establish honest comparison points before novel architecture work

Deliverables:

- full-context baseline
- naive retrieval baseline
- memory-atom baseline
- category-level reports

## Phase 3: Candidate memory engine

Goal:

- implement a memory system that can reasonably challenge public leaders

Current lead lane as of 2026-03-23:

- `observational_temporal_memory + MiniMax-M2.7` is the active `LongMemEval` optimization path
- internal real run on the first 25 `LongMemEval_s` samples: `13/25` (`0.52`)
- current comparison point on the same slice: `beam_temporal_atom_router + MiniMax-M2.7` at `3/25` (`0.12`)

Candidate components:

- multi-pass observer ingestion
- temporal and supersession layer
- retrieval router
- single answer layer with abstention
- offline consolidation worker

Initial candidate systems:

- System 1: `EPI + ATOM + TIME + ROUTE + REHYDRATE + ABSTAIN`
- System 2: `OBSERVE + REFLECT + TIME + PROFILE + ABSTAIN`
- System 3: `OBSERVE + ATOM + TIME + EVENTS + ROUTE + REHYDRATE + RELATE + ABSTAIN`

Deferred until after the lightweight baseline is measured:

- search-agent ensembles
- answer forests
- graph-database-first infra
- learned memory-control policies

## Phase 4: Mutation flywheel

Goal:

- improve by repeated benchmark pressure, not vibes

Deliverables:

- mutation packet schema
- evaluation packet schema
- automatic failure bucketing
- rollback policy

## Phase 5: Promotion discipline

Goal:

- decide what actually deserves to become product doctrine

Promotion gates:

- benchmark improvement
- no major category regression
- attribution satisfied
- implementation understandable enough to maintain
