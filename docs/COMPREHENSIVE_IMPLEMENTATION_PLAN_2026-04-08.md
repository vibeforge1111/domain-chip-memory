# Comprehensive Implementation Plan 2026-04-08

Status: active source-of-truth plan

## Purpose

This is the current comprehensive implementation plan for finishing `domain-chip-memory` into:

- a benchmark-leading memory system
- a real Spark memory substrate
- a user-visible LLM knowledge-base product layer on top of that substrate

This document exists to prevent drift between:

- older March handoff docs
- benchmark-only planning
- product-only planning
- the new knowledge-base direction

## Executive Summary

The project is now materially concrete.

It already has strong measured evidence on multiple serious memory lanes:

- local `ProductMemory`: `1266/1266`
- local official-public `BEAM 128K` conversation lane: latest checked-in variants sum to `400/400`
- `LongMemEval_s`: `500/500` is claimed in [README](../README.md) as the current measured contiguous frontier
- bounded clean `LoCoMo`: strong on the active `conv-26` slices, with one known inconsistency on the first 25-question block and multiple later `25/25` clean slices

But the system is not finished yet.

The main unfinished parts are:

- official-public judged `BEAM` closure
- canonical `GoodAI` closure
- broader clean `LoCoMo` closure beyond the bounded active lane
- direct runtime metrics
- real Spark shadow traces
- the actual implementation of the knowledge-base layer as a product surface, not only a doctrine

## Current Honest State

## What is currently strongest

### 1. Local ProductMemory

This is still the strongest explicit proof of real memory behavior in the repo.

Current checked-in truth from [FRONTIER_STATUS_2026-03-28.md](FRONTIER_STATUS_2026-03-28.md):

- full checked-in local corpus: `1266/1266`
- source alignment on the same lane: `1266/1266`

Why this matters:

- correction handling is strong
- deletion and restore behavior are strong
- stale-state handling is strong
- provenance-bearing retrieval is strong
- ambiguity abstention is strong

### 2. Local official-public `BEAM 128K`

This is now much stronger than the older March docs imply.

Current checked-in truth from the latest per-conversation scorecards:

- conversations `1-20` each have a latest checked-in `20/20` variant
- aggregate of the latest variants: `400/400`

Interpretation:

- the current local `summary_synthesis_memory` lane is not just "promising" on `BEAM`
- it is locally very strong on the official-public `128K` conversation set

Important boundary:

- this is local scorecard closure, not the same thing as judged official-public closure

### 3. `LongMemEval_s`

Current checked-in program truth in [README](../README.md):

- contiguous measured coverage through sample `500`
- current stated result: `500/500`

Interpretation:

- this is one of the repo's strongest cross-session proof lanes
- it is also the clearest currently pinned public target lane from the benchmark ledger

### 4. Bounded clean `LoCoMo`

Current checked-in program truth in [README](../README.md):

- first active bounded slice: `24/25` raw, with one known inconsistency
- later bounded `conv-26` slices `q26-150`: repeated `25/25` clean reruns

Interpretation:

- the architecture is strong on conversational linkage and temporal linkage on the measured bounded lane
- but the repo still does not honestly claim broad clean `LoCoMo` closure

## What is partially closed but not finished

### 1. Official-public judged `BEAM`

Current measured judged state:

- `500K conv1-5`: completed, alternate judged overall `0.8349`
- `500K conv6-10`: completed, alternate judged overall `0.7094`
- `500K conv11-15`: partial, current manifest overall `0.7778`, blocked by a `NoneType` judge/eval failure
- `500K conv16-20`: validated export path exists, not yet judged complete
- `1M` manifests exist in validated form, not yet carrying finished judged aggregate summaries
- `10M` manifests exist in validated form, not yet carrying finished judged aggregate summaries

Interpretation:

- local `BEAM` is strong
- official-public judged `BEAM` is the biggest benchmark-closure gap still open

### 2. Spark integration

Current truth:

- SDK surfaces, shadow tooling, and replay paths exist in the repo
- real Spark shadow evidence is still missing

Interpretation:

- architecture is integration-aware
- product rollout proof is not there yet

### 3. Knowledge-base layer

Current truth:

- doctrine is now written
- implementation is not yet scaffolded

Interpretation:

- the product direction is set
- the system is not yet shipping the visible KB layer

## What is still weak or missing

### 1. Canonical `GoodAI` run

Current repo truth:

- there is an old system comparison artifact:
  - `artifacts/benchmark_runs/goodai_32k_system_comparison.json`
- it shows `0/33` comparison outputs and is not the canonical serious run we want

Interpretation:

- `GoodAI` is not meaningfully closed
- this remains one of the clearest missing benchmark proofs

### 2. Broad clean `LoCoMo`

Current repo truth:

- strong bounded slices exist
- broad clean closure across chosen conversations is not yet locked as a current-state claim

### 3. Direct runtime metrics

Still not directly measured in the serious source-of-truth docs:

- p50 latency
- p95 latency
- prompt tokens
- total tokens
- memory growth
- stale-state error rate
- correction success rate
- deletion reliability
- memory drift rate
- maintenance stability

### 4. Real Spark shadow traces

Still missing:

- replayable real Builder trace batches
- shadow quality reports on actual traffic
- failure taxonomy from product traces

## Benchmark Ranking Right Now

This is the honest ranking by current repo confidence, not by ambition.

### Tier 1: Strongest measured lanes

1. local `ProductMemory`
2. local official-public `BEAM 128K`
3. `LongMemEval_s`

Why:

- these have the clearest measured success with the strongest current evidence

### Tier 2: Strong but bounded lanes

4. bounded clean `LoCoMo`

Why:

- strong on the measured active slices
- not yet broad enough to call fully closed

### Tier 3: Important but unfinished proof lanes

5. official-public judged `BEAM`
6. `GoodAI LTM Benchmark`

Why:

- these matter heavily to the final story
- but they are not yet honestly closed

## Remaining Benchmark Tests

These are the remaining benchmark tasks that matter most before we can say the memory system is broadly finished.

## A. `BEAM`

### Local regression lane

Keep green:

- latest local `128K conv1-20` leader at `400/400`

Required ongoing tests after real behavior mutations:

- targeted `BEAM` slices for changed categories
- local `BEAM` sanity reruns before promotion

### Official-public judged lane

Remaining tests:

1. finish `500K conv11-15`
2. finish `500K conv16-20`
3. convert `1M` validated exports into real judged completed artifacts
4. convert `10M` validated exports into real judged completed artifacts
5. produce one clean judged summary table across all finished official-public scales

## B. `LongMemEval_s`

Current measured frontier is already strong.

Remaining tests:

1. verify the claimed `500/500` path remains reproducible on demand
2. rerun targeted slices after any temporal, current-state, or answer-routing mutations
3. preserve exactness when introducing KB-driven or maintenance-driven changes

## C. `LoCoMo`

Remaining tests:

1. choose the next clean lane beyond the current bounded `conv-26` success path
2. lock the next serious clean slice or conversation family
3. make the current-state docs explicit about exactly what is measured versus still open

## D. `GoodAI`

Remaining tests:

1. choose the first canonical configuration set
2. reproduce the published harness path
3. lock the scorecard contract
4. establish the first real baseline and first serious candidate run

## E. Shadow regression benchmark

`ConvoMem` is still a guardrail, not the main win benchmark.

Remaining tests:

1. keep it as a regression lane when changes could weaken preference, changing-fact, or abstention behavior
2. add it into the serious promotion gates once the product-facing KB layer begins affecting answer behavior

## What Still Needs To Be Built

## Workstream 1: Finish Official-Public Judged `BEAM`

This is the most important benchmark-completion workstream.

Required work:

- fix the `500K conv11-15` `NoneType` judge/eval blocker
- resume the same resumable path cleanly
- commit each completed official-public judged phase in isolation
- then finish `500K conv16-20`
- then promote `1M` from validated exports to judged artifacts
- then promote `10M` from validated exports to judged artifacts

Definition of done:

- official-public judged `BEAM` is no longer a partial proof story

## Workstream 2: Turn Role-Clean Memory Into Runtime Truth

Required work:

- keep `memory_systems.py` as a compatibility shell, not the architecture center
- finish explicit role boundaries:
  - raw episodic archive
  - structured evidence
  - current state
  - temporal-event memory
  - belief/reflection memory
  - working memory
  - maintenance path
- finish explicit lifecycle operators:
  - create
  - update
  - delete
  - restore
  - supersede
  - contradict

Definition of done:

- provider rescue is a guardrail, not the main correctness engine

## Workstream 3: Add Direct Runtime Quality Measurement

Required work:

- emit latency metrics into serious benchmark artifacts
- emit token and context metrics into serious benchmark artifacts
- measure stale-state, deletion, correction, and maintenance metrics directly
- add memory-growth and drift reporting

Definition of done:

- runtime quality is inspectable and cannot hide behind benchmark scores

## Workstream 4: Build The KB Layer For Spark Memory

This is now part of the intended product, not optional polish.

Product rule:

- if a Spark user has memory, they should also have a visible KB workspace on top of that memory

Required first implementation steps:

1. scaffold a `kb/` directory in-repo
2. define the KB schema and page conventions
3. ingest repo-native sources:
   - docs
   - scorecards
   - benchmark manifests
   - handoff notes
   - research files
4. compile the first wiki pages:
   - memory system overview
   - benchmark proof status
   - mutation history
   - provider rescue versus substrate correctness
   - `BEAM` official status
   - `LongMemEval` transfer lessons
5. define the lint loop:
   - contradictions
   - stale claims
   - missing pages
   - unsupported benchmark claims without artifact linkage

Definition of done:

- the repo has a real knowledge-base scaffold and first compiled pages
- the product shape "memory + KB" exists in implementation, not only documentation

## Workstream 5: Spark Shadow Proof

Required work:

- gather real Builder trace batches
- replay them through the memory SDK
- track accepted writes, rejected writes, skipped turns, unsupported write reasons, probe hit rates, and role mix
- use those traces to test the KB compiler path as well, not only the runtime memory path

Definition of done:

- Spark promotion gates are evidence-based

## Product Shape We Are Actually Building

The final system is not:

- just a benchmark runner
- just a hidden memory SDK
- just a wiki product

It is:

1. a benchmark-proven runtime memory engine
2. a Spark-facing governed SDK
3. a user-visible LLM knowledge-base workspace built from that memory

This is the combined product logic:

- runtime memory keeps state correct
- the KB keeps knowledge visible and compounding
- benchmark pressure keeps the whole system honest

## Promotion Gates

Do not call the system finished until all of these are true:

1. benchmark story
   - `LongMemEval_s` remains reproducible at the current frontier
   - clean `LoCoMo` is broadened beyond the current bounded lane
   - first canonical `GoodAI` run is locked
   - official-public judged `BEAM` is completed across the intended scales

2. architecture story
   - role boundaries are runtime-real
   - lifecycle operators are explicit
   - provider rescue is no longer the main home of correctness

3. runtime story
   - latency, token, growth, deletion, correction, and drift metrics are directly measured

4. Spark product story
   - replayable shadow traces exist
   - promotion criteria are explicit
   - memory is visible to the user through the KB layer

## Sequence From Here

This is the concrete recommended order.

### Phase 1: Close the open benchmark blocker

1. finish or discard the current dirty temporal mutation
2. close `500K conv11-15`

### Phase 2: complete the judged `BEAM` story

3. finish `500K conv16-20`
4. convert `1M` into real judged closure
5. convert `10M` into real judged closure

### Phase 3: fill the missing benchmark proofs

6. lock the first canonical `GoodAI` run
7. choose and close the next clean `LoCoMo` lane

### Phase 4: build product-completion surfaces

8. add direct runtime metrics
9. scaffold the KB layer
10. ingest repo-native sources into the KB

### Phase 5: prove Spark-readiness

11. run real Spark shadow traces
12. test both runtime memory and KB compilation against those traces
13. define rollout gates

## Immediate Next Actions

If we want the cleanest non-drifting execution path, the next concrete actions should be:

1. resolve the open temporal retrieval mutation in the dirty worktree
2. resume `500K conv11-15` judged `BEAM`
3. scaffold `kb/`
4. lock the first canonical `GoodAI` execution plan
5. choose the next clean `LoCoMo` lane explicitly

## Bottom Line

The project is no longer trying to prove that it has some vague memory idea.

It already has:

- strong memory behavior
- strong benchmark evidence
- a credible product direction

The remaining job is disciplined closure:

- finish the benchmark proof stack
- finish the runtime architecture
- implement the KB layer as part of Spark memory
- prove the whole thing under real Spark shadow evidence
