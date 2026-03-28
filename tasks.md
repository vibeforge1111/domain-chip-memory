# Tasks

Date: 2026-03-28
Status: active

## Objective

Turn `domain-chip-memory` into a state-of-the-art memory system that:

- beats the strongest practical frontier bars on `LongMemEval`, `LoCoMo`, `GoodAI LTM Benchmark`, and `BEAM`
- functions as a true product memory layer with strong correction, deletion, supersession, provenance, and abstention behavior
- stays lightweight enough for real runtime use
- reaches Spark through shadow-mode evidence, not premature live promotion

## Program Rules

- Keep Spark integration on `shadow-only` until replay evidence says otherwise.
- Do not split the architecture into separate benchmark and product-memory stacks.
- Prefer reusable operators over benchmark-specific rescue logic.
- Keep provider rescue as a guardrail, not the main source of correctness.
- Re-run benchmark and product-memory gates after every real behavior mutation.

## Workstream 1: Lock The Current Frontier

- Promote the already-green next local `ProductMemory` lane.
- Reconcile active docs so one frontier snapshot is authoritative.
- Freeze the current baseline ledger for:
  - `LongMemEval_s`
  - clean `LoCoMo`
  - local `BEAM`
  - local `ProductMemory`

## Workstream 2: Separate The Architecture

- Split extraction logic into `memory_extraction.py`.
- Move generic retrieval logic into `memory_operators.py`.
- Keep lifecycle and supersession logic in `memory_updates.py`.
- Keep view logic in `memory_views.py`.
- Make `packet_builders.py` a real boundary instead of a re-export shell.
- Reduce `memory_systems.py` from architecture center to compatibility shell or orchestrator layer.

## Workstream 3: Govern The Update Engine

- Make these lifecycle operations first-class:
  - `create`
  - `update`
  - `delete`
  - `supersede`
  - `restore`
  - `contradict`
  - current-state rebuild from evidence
- Keep tombstone handling explicit.
- Keep historical reconstruction explicit.
- Prove deletion and restore behavior on local `ProductMemory`.

## Workstream 4: Clean Up Retrieval And Answering

- Keep role-clean read paths:
  - `get_current_state(...)`
  - `get_historical_state(...)`
  - `retrieve_evidence(...)`
  - `retrieve_events(...)`
  - `explain_answer(...)`
- Keep answer-candidate authority explicit.
- Move exact-answer integrity earlier into the substrate.
- Reduce dependence on provider-side rescue.

## Workstream 5: Finish Benchmark Completion

- Extend `LongMemEval_s` beyond the current measured frontier.
- Broaden clean `LoCoMo` coverage beyond the currently bounded lanes.
- Lock the first canonical `GoodAI LTM Benchmark` configuration and run.
- Keep the local `BEAM` pilot lane active while the official evaluation surface remains unpinned.
- Pin the official `BEAM` implementation path as soon as it becomes reproducible in-repo.

## Workstream 6: Add Architecture Ablations

- Tag every meaningful mutation as one of:
  - extraction improvement
  - update and supersession improvement
  - retrieval improvement
  - operator improvement
  - provider-rescue improvement
  - maintenance improvement
  - benchmark-closure-only improvement
  - `BEAM` transfer improvement
- Keep comparison artifacts that explain why gains happened, not only whether they happened.

## Workstream 7: Prove Real Runtime Quality

- Measure and report:
  - p50 and p95 latency
  - prompt and total tokens
  - memory growth
  - stale-state error rate
  - correction success rate
  - deletion reliability
  - provenance support rate
  - abstention honesty
  - maintenance stability
- Add replay tests, soak tests, and maintenance regression tests.

## Workstream 8: Keep Spark In Shadow Mode

- Keep the Spark Intelligence Builder integration on `shadow-only`.
- Require replayable shadow traces with:
  - `turns`
  - normalized write attempts
  - probes
  - `session_id`
  - `turn_id`
  - `timestamp`
- Replay traces here and report:
  - accepted writes
  - rejected writes
  - skipped turns
  - unsupported-write reasons
  - probe hit rates
  - memory-role mix
  - maintenance before/after results
- Turn real shadow failures into substrate fixes.
- Re-run benchmark safety gates after every real runtime mutation.
- Define rollout gates from shadow evidence, not intuition.

## Immediate Next Actions

- Promote the already-green next local `ProductMemory` lane.
- Reconcile docs so one frontier snapshot is authoritative.
- Create the first real code migration plan out of `memory_systems.py`.
- Extract the next architecture boundary into a dedicated module.
- Run the next honest `LongMemEval_s` extension slice.
- Choose the next clean `LoCoMo` lane.
- Lock the first canonical `GoodAI` run.
- Add runtime metric capture to serious comparison artifacts.
- Get the first real Spark shadow trace batch from Builder.

## Definition Of Done For This Program Phase

- The architecture is role-clean and no longer monolithic in practice.
- The benchmark story is broad, honest, and reproducible.
- The system is strong on product-memory behavior, not only benchmark QA.
- Runtime quality is measured directly instead of inferred.
- Spark shadow evidence is stable enough to support a future rollout gate.
- Only then do we consider limited live promotion.
