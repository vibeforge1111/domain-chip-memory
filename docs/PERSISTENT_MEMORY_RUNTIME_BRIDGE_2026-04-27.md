# Persistent Memory Runtime Bridge 2026-04-27

This note translates the latest memory research scan and the live Telegram tests into the next Spark build path. It should be read as the bridge between `domain-chip-memory` experiments and `spark-intelligence-builder` runtime behavior.

## Research Patterns To Import

- LoCoMo shows that long-term chat memory must handle multi-session facts, temporal event graphs, event summaries, and causal consistency, not only direct fact lookup.
- The event-centric baseline argues for short, attributed event-like discourse units instead of opaque summaries or isolated triples.
- SmartSearch is a warning against over-structuring too early: high recall is not enough if ranking loses decisive evidence before the context budget.
- SGMem and Engrama both point toward graph-shaped retrieval over sentences/entities/spaces/time, with evidence kept inspectable.
- Chronos makes temporal state first-class through event tuples, entity aliases, datetime ranges, and query-specific retrieval guidance.
- Cognis combines BM25, vector search, RRF, temporal boosts, context-aware extraction, and reranking while preserving memory history.
- Memoria reinforces the practical hybrid: session summaries for coherence plus a weighted graph for long-term profile and behavior.
- Anthropic's context-engineering guidance favors compact just-in-time retrieval and structured notes over dumping raw history into every turn.
- BrainBench/gbrain-evals adds the evaluation shape we need: graph ablations, temporal queries, identity resolution, provenance, robustness, source-swamp resistance, and adapter-to-adapter scorecards.

## What Spark Already Has

- A benchmark-first domain chip with LoCoMo, LongMemEval, BEAM, typed temporal graph, entity-linked retrieval, exact-turn lanes, lexical lanes, and shadow evals.
- Builder-side current-state writes and reads for focus, plan, profile facts, diagnostics, and maintenance summaries.
- A first `MemoryKernelAdapter` path in Builder that gives current-state reads a shared result schema and trace metadata.
- Telegram live tests for natural recall, stale/current replacement, source explanation, and current-state priority.

## The Gap

Spark has many of the right mechanisms, but they are split:

- `domain-chip-memory` owns stronger retrieval experiments and benchmark evidence.
- Builder owns the live Telegram path and still uses many narrow deterministic routes.
- The capsule can say which source class was used, but it is not yet compiled from one ranked evidence result.

The live Mira to Sol test exposed the exact missing layer: current value recall worked, but historical value recall for a named object did not surface the superseded value.

## Runtime Bridge We Should Build

1. Entity-state memory
   - Normalize facts into `entity`, `attribute`, `value`, `valid_from`, `valid_to`, `superseded_by`, `source_turn`.
   - Example: `tiny desk plant.name = Mira`, later superseded by `tiny desk plant.name = Sol`.

2. Temporal state reads
   - Support `current`, `previous`, `as_of`, and `changed_since` queries as first-class memory operations.
   - Current answers must ignore stale records unless the question is historical.

3. Hybrid retrieval adapter
   - Fuse exact predicate lookup, lexical/BM25, entity alias hits, recency/temporal boosts, and eventually vector/semantic search.
   - Return ranked evidence with source class, lifecycle, and provenance.

4. Evidence-unit capture
   - Promote natural conversation into atomic evidence units, not only regex-backed current-state slots.
   - Keep the current strict gates for active user state; do not promote operational residue.

5. Capsule compiler v2
   - Build every Telegram context from compact groups: current state, active focus/plan, recent dynamic facts, relevant evidence units, events, diagnostics/maintenance only when relevant, and advisory workflow state.

## Immediate Patch Taken

Builder now treats natural named-object corrections as temporal entity-state history for the current low-stakes test fact path:

- Current query: `What did I name the plant?` returns the latest name.
- Historical query: `What was the plant called before?` returns the superseded name.

This is not the final architecture. It is the first runtime shard of the architecture above, anchored in the live failure we observed.

## Next Promotion Gates

- Generalize named-object state beyond the low-stakes test predicate.
- Add provenance/source explanation for historical named-object answers.
- Port the entity-state read shape into `domain-chip-memory` as a benchmarkable adapter contract.
- Add BrainBench-style source-swamp and graph-ablation tests against Spark memory artifacts.
- Run Telegram live probes after restart:
  - `Actually, the tiny desk plant is named Sol.`
  - `What did I name the plant?`
  - `What was the plant called before?`
  - `Why did you answer that?`

## Sources

- https://arxiv.org/abs/2402.17753
- https://arxiv.org/abs/2511.17208
- https://arxiv.org/abs/2604.11628
- https://arxiv.org/abs/2603.15599
- https://arxiv.org/html/2509.21212v1
- https://arxiv.org/abs/2603.16862
- https://arxiv.org/abs/2604.19771
- https://arxiv.org/html/2604.21229v1
- https://arxiv.org/abs/2512.12686
- https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- https://github.com/garrytan/gbrain-evals
