# Tasks

Date: 2026-03-29
Status: active

## Objective

Turn `domain-chip-memory` into a memory system that:

- wins the benchmark stack honestly across `BEAM`, `LongMemEval`, and clean `LoCoMo`
- functions as a true memory layer with correction, deletion, supersession, provenance, abstention, and historical reconstruction
- remains lightweight enough for real runtime use
- reaches Spark only through shadow-mode evidence first

## Program Rules

- Do not optimize for score theater.
- Do not split benchmark memory and product memory into separate stacks.
- Keep provider rescue as a shrinking guardrail, not the main source of correctness.
- Treat `BEAM` as the core architecture proof benchmark.
- Treat `LongMemEval_s` and clean `LoCoMo` as non-negotiable guardrails around `BEAM`.
- Re-run the relevant benchmark and product-memory gates after every real behavior mutation.

## Current Truth

What is strongly proven:

- local `ProductMemory`
- bounded `LongMemEval_s`
- clean bounded `LoCoMo`
- local `BEAM` pilot pressure

What is not fully proven:

- full benchmark closure
- fully role-clean runtime architecture
- runtime quality metrics
- real Spark trace replay quality

## Exact Workstreams

### 1. Keep The Frontier Honest

- Keep [FRONTIER_STATUS_2026-03-28.md](docs/FRONTIER_STATUS_2026-03-28.md) or its successor as the single measured snapshot.
- Keep [MEMORY_SYSTEM_HONEST_ASSESSMENT_2026-03-29.md](docs/MEMORY_SYSTEM_HONEST_ASSESSMENT_2026-03-29.md) current.
- Reconcile any drift between handoff docs and the active measured truth.

### 2. Finish The Benchmark Proof Stack

- Extend `LongMemEval_s` beyond the currently measured frontier.
- Broaden clean `LoCoMo` coverage beyond the currently bounded slices.
- Lock the first canonical `GoodAI` run.
- Maintain the local `BEAM` pilot lane.
- Pin and reproduce the official `BEAM` path.

### 3. Finish The Memory Architecture

- Make memory roles runtime-real:
  - raw episodic archive
  - structured evidence
  - current-state/profile
  - temporal-event memory
  - belief/reflection
  - working memory
  - offline maintenance
- Make lifecycle operators explicit:
  - `create`
  - `update`
  - `delete`
  - `restore`
  - `supersede`
  - `contradict`
- Reduce correctness dependence inside provider rescue.

### 4. Prove Runtime Quality

- Add direct reporting for:
  - p50 latency
  - p95 latency
  - prompt tokens
  - total tokens
  - memory growth
  - stale-state error rate
  - correction success rate
  - deletion reliability
  - provenance support rate
  - abstention honesty
  - maintenance stability
  - memory drift rate

### 5. Keep Spark In Shadow

- Keep Builder integration on `shadow-only`.
- Require replayable traces.
- Turn shadow failures into substrate fixes.
- Do not promote from intuition.

## Intent Lanes

These are intentionally open-ended.

Use them when the architecture needs exploration that a literal checklist would miss.

### Intent Lane A: Make Memory Roles Feel Real

Question:

- what role boundary would break first under real product use

### Intent Lane B: Make Current-State Handling Unbreakable

Question:

- what would still break delete, correction, restore, or supersession under realistic complexity

### Intent Lane C: Make BEAM Pressure Transfer

Question:

- what fails when context stops being forgiving

### Intent Lane D: Make Benchmark Wins Transfer

Question:

- is this gain true architecture quality or just benchmark convenience

## Immediate Next Actions

- keep the current docs organized around one honest current-state view
- pin the official `BEAM` reproduction path
- extend the next honest `LongMemEval_s` slice
- choose the next clean `LoCoMo` lane
- lock the first canonical `GoodAI` run
- add direct runtime metric capture to serious artifacts
- get the first real Spark shadow trace batch

## Definition Of Done

- the benchmark story is broad, honest, and reproducible
- the architecture is role-clean in runtime reality
- runtime quality is measured directly
- benchmark wins transfer to product-memory behavior
- Spark shadow evidence is good enough to define rollout gates

