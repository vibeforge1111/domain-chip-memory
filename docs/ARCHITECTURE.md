# Agent Memory Architecture

Date: 2026-03-22
Status: exploratory architecture

## Design goal

Build the smallest system that can honestly compete with public long-term memory leaders.

The system should prove:

- benchmark-native memory beats generic retrieval
- temporal and update handling can be encoded explicitly
- repeated mutation loops can improve benchmark performance without leakage

It should not try to prove:

- universal AGI memory
- million-agent orchestration
- product-market fit for every memory use case

Product direction to preserve:

- the runtime memory substrate should eventually support a user-visible knowledge-base layer above it
- the visible layer should be compiled from governed memory and provenance, not from an unrelated second truth store

## System shape

The first full implementation should stay lightweight and have eight modules.

1. Benchmark adapters
2. Observer ingestion layer
3. Memory atom store
4. Temporal and supersession layer
5. Retrieval router
6. Answer layer with abstention
7. Evaluation and scorecard layer
8. Mutation and promotion loop

## Module definitions

### 1. Benchmark adapters

Input:

- canonical benchmark datasets

Output:

- normalized sessions
- normalized questions
- normalized evidence metadata

Benchmarks to support first:

- `LongMemEval`
- `LoCoMo`
- `GoodAI LTM Benchmark`
- `BEAM`

Shadow benchmark:

- `ConvoMem`

### 2. Observer ingestion layer

Input:

- normalized benchmark sessions

Output:

- extracted memory atoms
- candidate relationships
- provenance back to source sessions

The intended design is parallel observer passes with specialized extraction responsibilities:

- direct facts
- preferences
- events and dates
- updates and contradictions

### 3. Memory atom store

Input:

- extracted observations

Output:

- normalized memory atoms

Each atom should carry:

- canonical text
- source span or source session
- fact type
- entity scope
- timestamp metadata
- confidence

### 4. Temporal and supersession layer

Input:

- memory atoms

Output:

- relations such as `updates`, `extends`, `conflicts_with`, `supports`, `about`
- latest-valid views over mutable facts

This layer can be implemented relationally first.
It should make `knowledge-update` and `temporal-reasoning` first-class instead of incidental.

### 5. Retrieval router

Input:

- question
- memory index

Output:

- ranked evidence set
- retrieval trace
- chosen route type

The retrieval layer should start with:

- full-context route for short histories
- lexical search
- memory-atom search
- temporal filtering
- relation expansion when needed
- question-type-specific routing

Search-agent orchestration is optional later.

### 6. Answer layer with abstention

Input:

- question
- retrieval output

Output:

- one answer
- abstain signal
- rationale trace

The first version should prefer one strong answer policy with explicit abstention support.
Large online answer ensembles are deferred until a lightweight baseline plateaus.

### 7. Evaluation and scorecard layer

Input:

- benchmark outputs
- official scoring logic or benchmark-compatible judge logic

Output:

- benchmark scorecard
- category breakdown
- failure buckets
- regression flags

### 8. Mutation and promotion loop

Input:

- failure slices
- mutation packet

Output:

- promoted improvement
- reverted experiment
- contradiction note

## Data contracts to define first

- `benchmark_run_manifest.json`
- `memory_atom_packet.json`
- `retrieval_trace.json`
- `benchmark_scorecard.json`
- `mutation_packet.json`

## Evidence lane mapping

`research_grounded`

- public system analyses
- benchmark structure notes
- attribution decisions

`benchmark_grounded`

- scorecards
- public target ledger
- reproduced benchmark wins

`exploratory_frontier`

- raw mutation ideas
- unproven agentic retrieval variants
- architecture hypotheses

`realworld_validated`

- later production or shadow-traffic validations

## Guardrails

- no hidden benchmark leakage
- no doctrine from README marketing copy alone
- no public win claims without exact source or reproduced run
- no product borrowing without license review
- no regression-hiding by averaging across categories
- no heavyweight-first drift before the lightweight baseline is measured
