# Memory Variation Map And Three Builds

Date: 2026-03-23
Status: active selection

## Purpose

This document narrows the memory-system landscape into a build program.

It answers:

- which memory system varieties matter most
- which ones are actually relevant to benchmark leadership
- which three variations we should build first
- how `BEAM` changes the search space

## Benchmark pressure

Each benchmark rewards something slightly different.

- `LongMemEval` punishes stale fact retrieval, weak temporal grounding, and poor abstention
- `LoCoMo` punishes weak long-range conversational reasoning and multi-hop misses
- `GoodAI LTM Benchmark` punishes poor memory upkeep across long spans
- `BEAM` punishes systems that only work because current benchmark contexts still fit within modern model windows

`BEAM` matters because it creates pressure toward the `10M`-token regime.
That means compression quality, representation stability, and selective rehydration become much more important than they are on smaller benchmarks.

## Ten system varieties that matter

### 1. Full-Context Control

Examples:

- full-context baseline
- oracle-like filtered context baselines

Benefits:

- honesty baseline
- no memory design ambiguity

Problems:

- not scalable to `BEAM`
- does not tell us how to build a real memory engine

Verdict:

- always keep as a control, never mistake it for the target architecture

### 2. Lexical Retrieval Memory

Examples:

- BM25-style or overlap-driven retrieval

Benefits:

- cheap
- easy to debug
- surprisingly strong for direct-fact questions

Problems:

- weak on paraphrase
- weak on temporal updates
- collapses under noisy long histories

Verdict:

- baseline only

### 3. Vector Semantic Retrieval Memory

Examples:

- classic embedding-plus-top-k memory

Benefits:

- general semantic recall
- common production baseline

Problems:

- stale fact confusion
- poor correction handling
- weak time disambiguation

Verdict:

- useful baseline to beat, not the doctrine

### 4. Rolling Summary Memory

Examples:

- periodic summarization
- summary-only compressed history

Benefits:

- lightweight
- low token cost

Problems:

- irreversible information loss
- weak evidence fidelity
- easy to erase timing detail and contradictions

Verdict:

- not enough on its own

### 5. Temporal Atom Memory

Examples:

- `Supermemory` production direction

Benefits:

- strong on updates and supersession
- good benchmark fit for `LongMemEval`
- productizable online path

Problems:

- still depends on retrieval quality and routing quality
- can miss broader relational structure

Verdict:

- foundational family we should build

### 6. Event Calendar Memory

Examples:

- `Chronos`

Benefits:

- excellent fit for time-sensitive and multi-hop questions
- explicit date range and alias handling

Problems:

- query-time planning can become heavier
- public implementation is not yet pinned

Verdict:

- major source of architectural inspiration

### 7. Observational Stable-Window Memory

Examples:

- `Mastra Observational Memory`

Benefits:

- stable prompt window
- strong compression
- naturally aligned with large-context and `BEAM` pressure

Problems:

- observation drift risk
- compression quality becomes the whole game

Verdict:

- must be one of the three first-class build candidates

### 8. Agentic Search Memory

Examples:

- `Supermemory ASMR`

Benefits:

- very high frontier claim
- specialized retrieval roles may reduce noise

Problems:

- not public yet
- likely heavier online fanout
- can win benchmarks in ways that are harder to productize

Verdict:

- frontier inspiration lane, not first default build

### 9. Relation Graph Memory

Examples:

- `Graphiti`
- `A-Mem`
- `O-Mem`

Benefits:

- helps multi-hop reasoning
- helps entity and relationship tracking

Problems:

- graph-first infra can become complexity theater
- not obviously the first unlock on `BEAM`

Verdict:

- second-wave candidate, not V1 default

### 10. Dual-Store Consolidated Memory

Examples:

- `LightMem`
- `SimpleMem`
- `MemoryOS`
- `MemOS`

Benefits:

- combines online lightweight memory with offline consolidation
- strong long-range promise
- better fit for huge contexts than retrieval-only systems

Problems:

- harder implementation
- consolidation lag and policy quality matter

Verdict:

- key hybrid family for later-stage benchmark pressure, especially `BEAM`

## The three builds we should actually implement

These are the best three variations given the current research.

### Build 1: Beam-Ready Temporal Atom Router

Definition:

- `EPI + ATOM + TIME + ROUTE + REHYDRATE + ABSTAIN`

Why this build:

- strongest lightweight cross-benchmark default
- directly attacks `LongMemEval` and `LoCoMo`
- still productizable
- should transfer better than vector or summary memory

Expected best benchmarks:

- `LongMemEval`
- `GoodAI LTM Benchmark`
- early `BEAM` slices once the adapter exists

### Build 2: Observational Temporal Memory

Definition:

- `OBSERVE + REFLECT + TIME + PROFILE + ABSTAIN`

Why this build:

- gives us a true `Mastra OM`-style lane instead of pretending atom memory is the only answer
- important if stable compressed context beats retrieval-heavy systems under larger windows
- probably the most direct path to learning from `BEAM`

Expected best benchmarks:

- `LongMemEval`
- `BEAM`
- shadow checks for preference and profile behavior

### Build 3: Dual-Store Event Calendar Hybrid

Definition:

- `OBSERVE + ATOM + TIME + EVENTS + ROUTE + REHYDRATE + RELATE + ABSTAIN`

Why this build:

- combines the best ideas from `Chronos`, `Mastra OM`, and temporal-atom systems
- highest upside if `BEAM` exposes weaknesses in single-store memory
- likely best second-wave candidate for `LoCoMo` multi-hop slices

Expected best benchmarks:

- `LoCoMo`
- `BEAM`
- later `LongMemEval` frontier pushes once lighter systems plateau

## Explicit non-default builds

Do not start with these as the mainline:

- vector-only memory
- summary-only memory
- graph-database-first memory
- online search-agent forests
- answer ensembles as the default scoring path

Those are comparison points or later escalation paths, not the first doctrine.

## Build order

1. Build `Beam-Ready Temporal Atom Router` and establish honest scorecards on `LongMemEval`, `LoCoMo`, `GoodAI LTM Benchmark`, and `ConvoMem`
2. Build `Observational Temporal Memory` and compare it directly against Build 1, especially on larger-context and compression-sensitive slices
3. Build `Dual-Store Event Calendar Hybrid` only after the first two runs tell us which ingredients actually survive benchmark pressure

## Decision rule

If the first two systems are already strong on `LongMemEval`, `LoCoMo`, and `GoodAI`, and `BEAM` still exposes context-scale weakness, prioritize the hybrid.

If `Observational Temporal Memory` already transfers well to `BEAM`, keep the online path simpler and resist copying `ASMR`-style orchestration too early.
