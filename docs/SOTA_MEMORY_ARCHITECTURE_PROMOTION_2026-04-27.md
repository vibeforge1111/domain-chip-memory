# SOTA Memory Architecture Promotion 2026-04-27

This is the current build decision for moving Spark memory beyond one-off Telegram tests.

## Decision

Use `summary_synthesis_memory + heuristic_v1` as the active runtime leader, with `dual_store_event_calendar_hybrid` retained as the top challenger and `typed_temporal_graph` promoted as an additive sidecar for temporal/entity evidence.

This is not a claim that `summary_synthesis_memory` is the final architecture. It is the best proven live leader in our current Builder validation evidence, and it should become the stable backbone while we import stronger SOTA layers around it.

## Why This Architecture

Our own benchmark and soak docs already show:

- `summary_synthesis_memory` is the active Builder runtime leader.
- `dual_store_event_calendar_hybrid` is still a strong top-two challenger.
- `typed_temporal_graph` is implemented as an eval-only sidecar for relationship, alias, temporal, negation, reported-speech, and provenance cases.
- The live Telegram failures are not only storage failures. They are routing, source-priority, temporal conflict, and context-assembly failures.

That matches the outside SOTA pattern: the best systems are not just a vector DB or a hand-authored profile table. They use a layered memory stack with provenance, temporal state, ranking, and compact context assembly.

## External Systems Reviewed

### Graphiti / Zep

What to copy:

- temporal context graph
- validity windows for changing facts
- episodes as ground-truth provenance
- hybrid retrieval over semantic, keyword, and graph traversal
- current vs historical truth as first-class behavior

Spark mapping:

- `MemoryWriteRequest.valid_from`, `valid_to`, `supersedes`, `conflicts_with`
- `CurrentStateRequest` and `HistoricalStateRequest`
- `typed_temporal_graph` sidecar
- new `entity_key` scoped current/historical reads

### Mem0

What to copy:

- single-pass extraction path for speed
- add-only retention as a default until consolidation is confident
- agent-generated facts as first-class memory
- multi-signal retrieval: semantic, BM25, entity matching, rerank/fusion

Spark mapping:

- keep raw evidence and current-state snapshots separate
- do not delete/supersede without provenance
- add ranking/fusion to the Builder retrieval adapter before broad Telegram rollout

### Letta / MemGPT

What to copy:

- memory hierarchy: core memory, recall memory, archival memory
- context-window rebuilding as an explicit runtime process
- agent-visible memory operations with clear memory block boundaries

Spark mapping:

- capsule compiler v2 should assemble compact groups:
  - current state
  - active focus/plan
  - recent conversation
  - relevant evidence
  - events
  - diagnostics/maintenance only when relevant
  - advisory workflow residue last

### SmartSearch

What to copy:

- ranking is often the bottleneck, not recall volume
- deterministic lexical/entity retrieval can be very strong
- score-adaptive truncation matters because evidence can be retrieved and then lost before generation

Spark mapping:

- do not overbuild graph extraction before fixing rank/fusion and context-budget selection
- make retrieval traces show which evidence survived into the actual answer context

### SGMem and Event-Centric Memory

What to copy:

- fine-grained sentence/event memory reduces fragmentation
- retrieve raw dialogue and generated memories together
- preserve source turn attribution

Spark mapping:

- event/evidence units should be atomic and attributed
- generated summaries must not become the only truth store
- entity/state slots should link back to source observations

### APEX-MEM

What to copy:

- append-only storage
- property graph over entity-centric, temporally grounded events
- retrieval-time conflict resolution instead of destructive overwrite

Spark mapping:

- do not treat maintenance compaction as semantic deletion
- current-state reads choose the current value, but historical reads must still recover previous values
- conflict handling belongs in retrieval/context assembly, not only ingestion

### Hindsight / BrainBench-Style Evals

What to copy:

- memory quality should be tested as a system, not as isolated recall prompts
- source-swamp, identity resolution, temporal queries, provenance, and adapter contracts need dedicated tests

Spark mapping:

- Telegram live tests become acceptance checks after the architecture layer is wired
- benchmark packs should include current-vs-stale conflicts, open-ended recall, source explanation, and noisy workflow residue

## Current Gaps In Spark

- The SDK contract default was still advertising `dual_store_event_calendar_hybrid` while Builder pins `summary_synthesis_memory`.
- Builder has a `MemoryKernelAdapter`, but not every live route uses the strongest domain-chip read shape.
- `typed_temporal_graph` exists, but it is still eval/shadow oriented instead of part of the live retrieval adapter.
- Current-state slots collapse too much unless reads can scope by entity.
- Source explanation exists, but context assembly is not yet one ranked evidence packet.
- Diagnostics and workflow residue can still appear in answers when the user asks broad next-step questions.

## Patch Started

This session changed the SDK contract to make the selected live leader explicit:

- default runtime architecture: `summary_synthesis_memory`
- retained challenger metadata: `dual_store_event_calendar_hybrid`
- sidecar metadata: `typed_temporal_graph`
- added `entity_key` to current and historical state read requests
- added Builder adapter pass-through for entity-scoped reads

This is the first architecture-level plug. It gives Spark a real path toward Graphiti/APEX-style temporal entity memory without replacing the current proven runtime backbone.

## Next Build Gates

1. Add a live Builder route that writes generic entity-state observations, not test-fact-specific observations.
2. Add retrieval fusion in Builder over:
   - current state
   - historical state
   - evidence retrieval
   - event retrieval
   - typed temporal graph sidecar
3. Add a capsule compiler v2 test that proves diagnostics and workflow residue cannot outrank current state unless directly relevant.
4. Add BrainBench/gbrain-style source-swamp tests against Spark artifacts.
5. Run Telegram acceptance only after those plugs:
   - open-ended recall
   - stale/current conflict
   - previous value query
   - source explanation
   - broad "what next?" without deterministic route words

## Sources

- https://github.com/getzep/graphiti
- https://arxiv.org/abs/2501.13956
- https://github.com/mem0ai/mem0
- https://arxiv.org/abs/2504.19413
- https://github.com/letta-ai/letta
- https://docs.letta.com/
- https://github.com/vectorize-io/hindsight
- https://github.com/garrytan/gbrain-evals
- https://arxiv.org/abs/2402.17753
- https://arxiv.org/abs/2511.17208
- https://arxiv.org/abs/2603.15599
- https://arxiv.org/html/2509.21212v1
- https://arxiv.org/abs/2604.14362
- https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
