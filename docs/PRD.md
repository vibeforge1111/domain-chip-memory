# Agent Memory PRD

Date: 2026-03-22
Status: exploratory
Owner: vibeforge1111

## Product summary

Domain Chip Memory is a benchmark-first operating system for building an agent memory stack that can beat the strongest public systems on:

- `LongMemEval`
- `LoCoMo`
- `GoodAI LTM Benchmark`
- `BEAM`

Shadow benchmark:

- `ConvoMem`

The first product is not a polished API.
It is a research and evaluation machine that answers:

- which memory architecture wins on the hardest public benchmarks
- which components cause the gains
- which open-source codebases are safe to reuse or adapt
- which mutations are worth promoting into a production memory engine

## Problem

Most memory projects still fail in one of four ways:

1. they confuse memory with generic RAG
2. they ignore time, contradictions, and updates
3. they claim wins without benchmark-native reproduction
4. they optimize one prompt and call it architecture

This chip exists to force benchmark honesty and repeated improvement.

## User

Primary user:

- a chip architect or memory researcher trying to build a state-of-the-art long-term memory system

Secondary user:

- an operator deciding which methods deserve promotion into a real memory product

## User jobs

- compare public memory systems and benchmarks using primary sources
- encode sourced benchmark targets into a visible ledger
- design bounded memory architecture mutations
- evaluate changes against benchmark slices and failure classes
- preserve attribution and license boundaries while borrowing ideas
- promote only the methods that survive repeated benchmark pressure

## Non-goals

- shipping a consumer memory product in phase 1
- pretending one benchmark win solves all product memory problems
- training on benchmark leakage
- copying closed or unclear methods without attribution
- giant unbounded multi-agent theater

## Product thesis

The winning system will likely combine:

- structured memory extraction
- temporal grounding
- fact versioning and supersession
- query-aware retrieval routing
- small profile memory distinct from event memory
- offline consolidation for heavier intelligence
- mutation loops driven by failure slices

A single vector index plus a single prompt is unlikely to be enough.
But a heavyweight online ensemble should also be treated as guilty until it clearly beats a lightweight temporal-semantic baseline.

Initial execution ladder:

1. Beam-Ready Temporal Atom Router
2. Observational Temporal Memory
3. Dual-Store Event Calendar Hybrid

## Success metrics

Primary metrics:

- benchmark answer accuracy on `LongMemEval`, `LoCoMo`, `GoodAI LTM Benchmark`, and `BEAM`
- per-category performance, especially `knowledge-update`, `temporal`, and `abstention`
- reproducibility of runs and scorecards

Shadow metric:

- no major regression on `ConvoMem` preference, changing-fact, and abstention slices

Secondary metrics:

- retrieval precision and recall on evidence sessions or turns
- latency and token cost
- stability of results across judges and reader models
- transfer of gains across multiple benchmarks

## Acceptance criteria for phase 1

- benchmark ledger grounded in primary sources
- architecture plan specific to memory benchmarks
- autoloop mutation policy
- attribution plan covering reusable codebases
- local watchtower and evaluator surfaces

## Acceptance criteria for phase 2

- benchmark adapters in-repo
- baseline runners
- at least one honest candidate memory architecture
- per-benchmark scorecards with reproducible artifacts

## Decision gates

Promote a method only if:

- the source benchmark and scoring path are pinned
- the gain survives reruns
- the gain does not depend on benchmark leakage
- the method respects license constraints
- the method does not materially regress abstention or update handling
