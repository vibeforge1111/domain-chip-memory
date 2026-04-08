# Today Plan 2026-04-08

Status: active restart plan

## Purpose

This is the current restart plan for today.

It replaces the stale March "tomorrow" framing with the real April state:

- the local `summary_synthesis_memory` lane is much stronger than the older `23/60` first-3 snapshot
- the official-public judged `BEAM` continuation is in progress, not finished
- there is an uncommitted temporal retrieval mutation in the worktree
- the repo does not yet have a Karpathy-style LLM knowledge-base layer

## Real Current Restart Point

### 1. Local benchmark truth

What now appears strong:

- local `ProductMemory` remains documented as `1266/1266`
- `LongMemEval_s` is described in [README](../README.md) as measured through sample `500` with the current `summary_synthesis_memory + heuristic_v1` path
- the local official-public `BEAM` `128K` lane for `summary_synthesis_memory` is far beyond the old first-3 frontier:
  - conversations `1-20` all now have a `20/20` checked-in scorecard variant
  - earlier imperfect variants still exist, but the latest promoted variants show full local closure on that `128K` conversation set

Interpretation:

- the current local leader is no longer "can we move first-3 above 23/60"
- the current local leader is "protect the now-strong local `BEAM` lane while finishing broader judged proof and reducing architecture debt"

### 2. Official-public judged `BEAM` truth

Committed judged progress:

- `500K conv1-5`: completed, alternate judged overall `0.8349`
- `500K conv6-10`: completed, alternate judged overall `0.7094`

Current live judged frontier:

- [BEAM_JUDGED_HANDOFF_2026-04-04.md](BEAM_JUDGED_HANDOFF_2026-04-04.md)
- `500K conv11-15` manifest is present but still partial:
  - file: `artifacts/benchmark_runs/official_beam_500k_summary_synthesis_memory_heuristic_v1_conv11_15_v1_official_eval.json`
  - current status: `partial`
  - current partial overall: `0.7778`
  - current blocker: `TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'`

Interpretation:

- today should treat official-public judged `BEAM` as the highest-signal benchmark closure task
- do not confuse the strong local `128K` scorecards with finished judged closure

### 3. Current dirty worktree truth

There is active uncommitted code in:

- `src/domain_chip_memory/memory_aggregate_support.py`
- `src/domain_chip_memory/memory_answer_routing.py`
- `src/domain_chip_memory/memory_selection.py`
- `src/domain_chip_memory/memory_time.py`
- `tests/test_memory_time.py`

What those changes are trying to do:

- improve clause-aware temporal and event-ordering evidence selection
- route more date-delta and ordering questions into aggregate support
- parse `LongMemEval`-style timestamps such as `2023/01/15 (Sun) 00:27`

What is currently verified:

- [test_memory_time.py](../tests/test_memory_time.py) passes with the new parser case

What is not yet honestly verified:

- the broader retrieval mutation has not yet been cleanly validated against the relevant `BEAM` and `LongMemEval` slices in this session

Interpretation:

- the first engineering job today is not "invent a new mutation"
- it is "finish or quarantine the mutation already open in the worktree"

## Today Workstreams

## Workstream 1: Finish Or Quarantine The Open Temporal Mutation

Purpose:

- convert the dirty temporal/event-ordering change into a real measured step instead of leaving it half-live in the worktree

Exact tasks:

1. expand or confirm targeted tests around:
   - event ordering
   - trip ordering
   - `ago` / `since` / `between` deltas
   - `LongMemEval` timestamp parsing
2. rerun the smallest relevant local slices:
   - targeted `BEAM` event-ordering questions
   - targeted `LongMemEval_s` delta/order questions
3. keep the mutation only if it improves or clearly protects the active leader without regressions
4. otherwise revert or park it explicitly instead of carrying silent drift

Success condition:

- the open mutation ends today as either:
  - committed and benchmark-validated
  - or intentionally discarded

## Workstream 2: Close The Next Official-Public Judged `BEAM` Phase

Purpose:

- keep converting the strong local `BEAM` path into a real judged proof story

Exact tasks:

1. inspect the `conv11-15` partial manifest and identify whether the `NoneType` failure is:
   - evaluator parsing
   - missing judge payload normalization
   - one corrupt conversation/category result
2. resume the same judged root exactly as documented in [BEAM_JUDGED_HANDOFF_2026-04-04.md](BEAM_JUDGED_HANDOFF_2026-04-04.md)
3. keep `--max-workers 1`
4. do not touch unrelated artifacts
5. when `conv11-15` finishes cleanly, commit only the scoped manifest plus evaluation files

Success condition:

- either `500K conv11-15` is completed and committed
- or the blocker is reduced to one explicit code/path defect with a minimal reproduction and fix plan

## Workstream 3: Refresh The Honest April Docs

Purpose:

- stop forcing restarts through stale March frontier notes

Exact tasks:

1. update the current-state docs after Workstreams 1 and 2:
   - `docs/FRONTIER_STATUS_2026-03-28.md` or a dated successor
   - `docs/MEMORY_SYSTEM_HONEST_ASSESSMENT_2026-03-29.md` or a dated successor
   - `README.md`
2. explicitly record:
   - local `BEAM 128K` conversation closure status
   - `LongMemEval_s` measured frontier through `500`
   - judged `500K` official-public completion state
   - any still-open unknowns

Success condition:

- the repo has one truthful April restart surface instead of March-only intent documents

## Workstream 4: Add The Karpathy Knowledge-Base Layer

Purpose:

- combine the current memory methodology with an LLM-maintained research and operations wiki so knowledge compounds instead of living only in session logs and artifact filenames

The important design rule:

- this knowledge base is an offline compile-and-query layer on top of the memory system program
- it is not a replacement for the online runtime memory substrate
- for Spark productization, it should be treated as a required companion layer for users with memory, not an optional extra

Why this matters here:

- the repo already has strong benchmark artifacts, handoff notes, scorecards, research docs, and mutation history
- those materials are not yet compiled into a queryable, self-maintaining knowledge graph
- that means we keep rediscovering context instead of compounding it

Proposed first structure:

- `kb/raw/`
  - external papers, posts, benchmark docs, copied issue traces
- `kb/wiki/sources/`
  - one compiled page per source or artifact family
- `kb/wiki/concepts/`
  - one page per reusable idea:
    - role-clean retrieval
    - current-state rebuild
    - contradiction handling
    - event ordering
    - aggregate support
    - benchmark transfer
- `kb/wiki/benchmarks/`
  - one dossier per benchmark family and slice
- `kb/wiki/mutations/`
  - one page per meaningful mutation, what moved, what failed, what transferred
- `kb/wiki/outputs/`
  - filed analyses, benchmark postmortems, next-step syntheses
- `kb/attachments/`
  - charts, tables, derived visuals
- `kb/CLAUDE.md` or equivalent repo-local schema file

First ingest queue from the current repo:

- active docs under `docs/`
- benchmark-grounded research files under `research/`
- latest `README.md`
- the judged handoff doc
- the local `BEAM` scorecards
- the official-public evaluation manifests
- the benchmark run artifacts that define current frontier claims

First compiled pages to create after scaffolding:

1. `summary-synthesis-memory.md`
2. `beam-official-proof-status.md`
3. `temporal-event-ordering-operator.md`
4. `provider-rescue-vs-substrate-correctness.md`
5. `longmemeval-transfer-lessons.md`
6. `mutation-history-summary.md`

Lint loop for this KB:

- missing benchmark claim without artifact link
- stale frontier wording
- contradictions between handoff docs and current artifacts
- concepts mentioned often but lacking a page
- mutations without transfer verdicts

Success condition:

- by end of today we have either:
  - the KB scaffold committed
  - or a fully specified scaffold plan with exact folder/schema choices ready to implement next

## Workstream 5: Use The Knowledge Base To Improve The Memory System

Purpose:

- make the KB a real force multiplier, not a decorative notes folder

The combined system should work like this:

1. raw artifacts and sources enter `kb/raw/`
2. the LLM compiles them into a linked wiki of:
   - benchmark dossiers
   - operator pages
   - failure taxonomies
   - mutation lessons
3. queries against the wiki produce:
   - benchmark-specific miss taxonomies
   - transfer hypotheses
   - mutation candidates
   - rollout criteria
4. those outputs are filed back into the wiki
5. the runtime memory substrate then implements only the ideas that survive benchmark and product-memory validation

This is the "better than both" target:

- the runtime memory system answers and updates memory well
- the KB remembers what we learned about building the runtime memory system

## Execution Order For Today

1. finish or discard the open temporal retrieval mutation
2. resume and close judged `500K conv11-15`
3. refresh the honest current-state docs
4. scaffold the Karpathy-style KB layer
5. ingest the first repo-native sources into the KB
6. use the KB to generate the next mutation shortlist after judged `BEAM` is back under control

## Explicit Do-Not-Do List For Today

- do not start another broad architecture rewrite before closing the open temporal mutation
- do not mix unrelated dirty artifacts into the judged `BEAM` commit
- do not treat local `128K` closure as the end of benchmark proof
- do not let the KB become a second disconnected project
- do not replace benchmark discipline with "research vibes"

## End-Of-Day Success Criteria

Today is successful if most of these are true:

- the open temporal mutation is resolved honestly
- judged `500K conv11-15` is either finished or reduced to one clear blocker
- the repo has an April current-state plan and restart surface
- the KB layer is scaffolded or fully specified
- the next mutation queue is generated from compiled knowledge, not only memory of prior sessions

## Bottom Line

The repo is no longer in a phase where the biggest problem is "can this memory architecture work at all."

The current job is narrower and harder:

- finish judged proof
- keep the architecture honest
- turn accumulated repo knowledge into a maintained LLM knowledge base
- use that KB to compound learning while continuing benchmark pressure
