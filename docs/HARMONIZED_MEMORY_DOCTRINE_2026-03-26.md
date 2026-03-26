# Harmonized Memory Doctrine

Date: 2026-03-26
Status: active build doctrine

## Purpose

This repo should not split into:

- one architecture for benchmark wins
- another architecture for real product memory

That is how memory systems become confused, heavy, and hard to trust.

The correct target is one lightweight memory architecture that:

- closes real benchmark pressure honestly
- generalizes to real user-facing memory UX
- preserves exactness and trust under compression
- stays cheap enough to run as a practical system

## Core thesis

Benchmark leadership and real-world usability should come from the same substrate.

If a change helps benchmarks but does not improve a reusable memory role, operator, update rule, or trust surface, it is probably a local patch, not architecture progress.

If a change helps UX but weakens benchmark truthfulness, it is probably masking memory weakness instead of solving it.

The repo should accept mutations that improve both, or clearly improve one without damaging the other.

## Non-negotiable architecture principles

### 1. One architecture, not two

Do not maintain a benchmark path and a product path with different memory logic.

The same memory roles should power both:

- raw episodic archive
- structured evidence memory
- current-state and profile memory
- reflection and belief memory
- temporal-event memory
- selective rehydration
- offline consolidation

### 2. Lightweight online path

The hot path must stay small.

Online memory should prefer:

- working memory
- current-state views
- typed answer candidates
- compact structured evidence

Heavier work should move off the hot path:

- reflection
- reconsolidation
- compaction
- duplicate cleanup
- archive-level summarization

### 3. Trust is a product feature

Real users do not only care whether the answer is right once.

They care whether the system is:

- editable
- debuggable
- deletable
- provenance-aware
- supersession-aware
- willing to abstain

The memory system should therefore make it easy to answer:

- why was this remembered?
- what evidence supports this?
- what changed?
- what is current versus historical?
- can this memory be corrected or removed?

### 4. Generic operators beat question-shaped hacks

Prefer reusable operators over benchmark-specific branches.

The main operators worth promoting are:

- exact fact lookup
- current-state lookup
- temporal before-after lookup
- event-anchored lookup
- compare and diff
- count and sum
- preference synthesis
- abstention
- selective rehydration

### 5. Guardrails are allowed, dependency is not

Provider rescue and response cleanup may remain as guardrails.

But correctness should increasingly live in:

- typed answer candidates
- operator outputs
- update logic
- memory-role separation

Not mainly in:

- provider-side heuristics
- overlap-based post-hoc answer correction
- benchmark-specific prompt shaping

## How to judge competitors

The repo should aim to beat benchmark-native systems in usability and beat product-native systems in memory quality.

### Benchmark-native competitors

Strengths:

- stronger evaluation discipline
- better temporal and retrieval pressure
- stronger benchmark optimization loops

Likely weaknesses:

- product UX can be thin
- editing and provenance controls are often weak
- heavy orchestration can become expensive

### Product-native competitors

Strengths:

- easier integration
- better developer ergonomics
- more obvious end-user memory features

Likely weaknesses:

- weaker temporal reasoning
- weaker supersession handling
- weaker abstention discipline
- more likely to rely on generic retrieval instead of governed memory

## Product advantages the repo should explicitly pursue

The system should compete on more than answer accuracy.

Target real-world advantages:

- low latency
- low token cost
- exact current-state handling
- explicit history versus current-state separation
- strong correction and deletion semantics
- provenance and evidence visibility
- predictable abstention
- low stale-memory drift

## Mutation acceptance rule

Every meaningful memory mutation should be described as improving one or more of:

- benchmark closure
- substrate quality
- `BEAM` transfer readiness
- product UX
- latency or cost
- trust and controllability

If a mutation improves only one benchmark edge case and does not improve any reusable memory property, it should face a higher bar.

## Lightweight rule

Do not add heavy machinery by default.

Postpone unless clearly required:

- graph-database-first infrastructure
- online search-agent forests
- large-answer ensembles
- always-on full-history prompting
- learned memory policies without strong measured wins

Prefer first:

- compact structured evidence
- explicit supersession
- typed answer candidates
- event and temporal operators
- selective raw-evidence rehydration
- offline consolidation

## Evaluation rule

Benchmark scorecards are necessary but insufficient.

The repo should also treat these as first-class product memory metrics:

- latency
- token cost
- stale-state error rate
- correction success rate
- deletion reliability
- provenance quality
- abstention honesty
- memory drift rate

## Decision rule for next work

When choosing between two plausible next tasks, prefer the one that:

1. improves a reusable operator or memory role
2. preserves lightweight operation
3. helps both benchmark closure and real-world memory UX

## Bottom line

The repo should pursue one outcome:

- a lightweight, trustworthy, benchmark-winning memory architecture that is also better to use in real life than heavier or shallower competitors

That is the standard.
