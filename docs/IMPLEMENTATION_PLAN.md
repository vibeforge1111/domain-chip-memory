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
- `BEAM` scorecard contract that can track million-token stress slices separately from shorter benchmark slices

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
- implement it in a way that can extend to `BEAM` without sacrificing already-closed `LongMemEval_s` and `LoCoMo` slices

Current lead lane as of 2026-03-23:

- `observational_temporal_memory + MiniMax-M2.7` is the active `LongMemEval` optimization path
- real rerun on March 23, 2026 over the first 25 `LongMemEval_s` samples: `25/25` (`1.00`)
- real rerun on March 23, 2026 over the first 50 `LongMemEval_s` samples: `50/50` (`1.00`)
- current bounded `LoCoMo` same-provider ladder on the first 25 `conv-26` questions:
  - `observational_temporal_memory`: `24/25` raw, `24/24` audited
  - `dual_store_event_calendar_hybrid`: `23/25` raw, `23/24` audited
  - `beam_temporal_atom_router`: `6/25` raw, `6/24` audited
- real rerun on March 24, 2026 over the next 25 `LoCoMo` `conv-26` questions (`q26-50`):
  - `observational_temporal_memory`: `25/25` raw, `25/25` audited
- real rerun on March 24, 2026 over the next bounded `LoCoMo` `conv-26` questions (`q51-75`):
  - `observational_temporal_memory`: `25/25` raw, `25/25` audited
- real rerun on March 24, 2026 over the next bounded `LoCoMo` `conv-26` questions (`q76-100`):
  - `observational_temporal_memory`: `25/25` raw, `25/25` audited
- real rerun on March 24, 2026 over the next bounded `LoCoMo` `conv-26` questions (`q101-125`):
  - `observational_temporal_memory`: `25/25` raw, `25/25` audited
  - measured progression on the same slice: `1/25 -> 23/25 -> 25/25`
- real rerun on March 24, 2026 over the next bounded `LoCoMo` `conv-26` questions (`q126-150`):
  - `observational_temporal_memory`: `25/25` raw, `25/25` audited
  - measured progression on the same slice: `3/25 -> 23/25 -> 24/25 -> 25/25`

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

## Phase 3A: BEAM readiness track

Goal:

- restructure the winning lane so it can survive million-token pressure while preserving current benchmark wins

Required constraints:

- keep `LongMemEval_s` and `LoCoMo` as regression gates
- do not treat current partial coverage as full-benchmark victory

Deliverables:

- explicit working-memory, episodic-memory, stable-memory, and scratchpad-memory role separation
- stronger hybridization path between observational memory and temporal-event structure
- offline consolidation hooks for large-context pressure
- compaction and rehydration rules that preserve exact answer-bearing spans
- architecture ablations that test whether `BEAM`-oriented changes keep current `LongMemEval_s` and `LoCoMo` wins intact

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
