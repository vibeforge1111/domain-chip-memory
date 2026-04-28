# Open Source Memory Stack And Prune Plan 2026-04-28

This is the working architecture decision for moving Spark memory from "many promising pieces" to one clean persistent-memory stack.

## Decision

Use a hybrid stack:

```text
Spark Telegram / Builder
  -> memory capture gate
  -> domain-chip-memory authority ledger
  -> current-state and entity-state projections
  -> hybrid retrieval adapter
     -> local exact/current/historical/evidence/event lanes
     -> Graphiti-compatible temporal graph sidecar
     -> optional Mem0/Cognee shadow adapters
  -> capsule compiler v2
  -> answer with source explanation
```

`domain-chip-memory` remains Spark's control plane. It owns authority, provenance, source classes, current-state priority, retention policy, evaluation gates, and Telegram-facing answer contracts.

Open-source systems are imported as sidecars or baselines, not as the source of truth.

## Why Hybrid

We do not have time to rebuild everything from scratch, but replacing Spark's memory core wholesale would throw away the parts that are already working:

- explicit current-state authority
- append-only evidence
- entity-scoped state
- historical reads
- maintenance and auditability
- source explanation
- Spark-specific workflow and diagnostics separation

The fastest path is to keep those as the authority layer and borrow mature retrieval/graph pieces where they fill real gaps.

## External Stack Choice

### Adopt First: Graphiti-Compatible Temporal Graph Sidecar

Use Graphiti's architecture as the first serious sidecar target.

What it gives us:

- temporal graph shape for evolving facts
- entities, relationships, episodes, and provenance
- validity windows and invalidation behavior
- hybrid retrieval across semantic, keyword, and graph signals

Spark use:

- feed it Spark evidence/events as episodes
- retrieve graph hits into `hybrid_memory_retrieve`
- never let it directly override `current_state`
- require every graph hit to return provenance and validity metadata

### Shadow Baseline: Mem0

Use Mem0 as a comparison and possible extraction/retrieval helper, not as Spark's authority store.

What it gives us:

- production-shaped personal memory API
- user/session/agent memory levels
- entity-aware memory search
- hybrid search patterns

Spark use:

- run it in shadow on selected conversation slices
- compare recall quality against our adapter
- copy useful extraction/search behavior only when it preserves provenance

### Optional Later: Cognee

Use Cognee only if we need broader knowledge graph/RAG ingestion across files, connectors, and project docs.

What it gives us:

- graph/RAG memory engine
- multi-format ingestion
- data pipeline orientation

Spark use:

- connector/document memory experiments
- not the first conversational memory runtime dependency

### Evaluation Inspiration: gbrain-evals / BrainBench

Use the evaluation shape, not the runtime.

What to copy:

- adapter-vs-adapter scorecards
- graph-disabled ablations
- source-swamp resistance
- temporal, identity, provenance, and workflow tests
- reproducible qrels and artifacts

## What We Keep

These stay in the runtime path:

- `summary_synthesis_memory + heuristic_v1` as the selected local backbone until a promoted hybrid path beats it.
- `SparkMemorySDK` contracts.
- append-only evidence log.
- current-state projection.
- entity-scoped current and historical state.
- event retrieval.
- `hybrid_memory_retrieve` adapter.
- source authority ordering.
- maintenance/audit summaries.
- Telegram answer source explanations.

These stay as benchmark/eval substrate:

- LongMemEval slices.
- LoCoMo slices.
- BEAM history that explains why the current leader was selected.
- source-swamp and stale-current regression packs.

## What We Freeze

Freeze means no new feature work unless the code is needed as a challenger, adapter, or regression oracle.

- `dual_store_event_calendar_hybrid`: keep as challenger only.
- local `typed_temporal_graph` experiments: keep as adapter-contract reference while the Graphiti-compatible sidecar is introduced.
- old architecture variation loops: keep as historical docs, do not let them reopen the selected runtime architecture.
- broad benchmark-autoloop scripts: use only for promotion gates, not day-to-day wiring.
- deterministic Telegram helper routes: keep temporarily, but route them through the shared memory-kernel result schema when touched.

## What We Delete Or Archive After Dependency Check

Do not delete these until `git grep`/`Select-String`, tests, and import checks prove they are unused.

Fast deletion/archive candidates:

- obsolete generated benchmark output files not referenced by docs or tests
- duplicate scorecards from superseded first-N runs where a later consolidated scorecard exists
- one-off scratch scripts that are not imported and not documented as replay tools
- old docs that repeat the same architecture decision without unique evidence
- local graph prototype paths that are fully replaced by the Graphiti-compatible sidecar and covered by tests

Do not delete:

- append-only memory/event data
- migration/replay utilities
- tests encoding known Telegram failures
- diagnostics and maintenance docs
- benchmark artifacts that justify architecture promotion
- docs with unique source mapping or acceptance gates

## Runtime Authority Contract

When sources conflict:

1. explicit current state
2. entity-scoped current state
3. historical state, only for historical questions
4. recent conversation
5. retrieved evidence/events
6. graph sidecar hits
7. diagnostics/maintenance, only when relevant
8. workflow/mission residue, advisory only
9. shadow Mem0/Cognee results, never authoritative until promoted

Clean diagnostics never close a user focus. Maintenance success never closes a user plan. Shadow sidecars never become source-of-truth without promotion evidence.

## Sidecar Adapter Contract

Every sidecar must implement this shape before runtime use:

```text
upsert_episode(record) -> sidecar_ids
retrieve(query, subject, scope, time_window, top_k) -> ranked_hits
explain(hit) -> source, provenance, validity, confidence
health() -> status
shadow_compare(query, local_hits, sidecar_hits) -> scorecard
```

Every returned hit must include:

- source class
- source record id
- raw evidence pointer
- entity keys
- valid_from / valid_to when known
- confidence
- reason selected
- reason discarded when not selected

## Fast Build Sequence

### Step 1: Lock The Architecture

- Add this plan as the current memory stack decision.
- Update `tasks.md` so new work points at the hybrid OSS-sidecar plan.
- Stop reopening old architecture variants unless a benchmark beats the current path.

### Step 2: Inventory And Prune Map

- Generate a dependency map for docs, scripts, tests, and runtime imports.
- Classify files into keep, freeze, archive/delete candidate.
- Remove only untracked/generated clutter first.
- Commit pruning in small batches.

### Step 3: Sidecar Interface

- Add a `memory_sidecars` interface in `domain-chip-memory`.
- Implement a no-op/local adapter first so tests lock the contract.
- Add Graphiti-compatible adapter behind a feature flag.

### Step 4: Shadow Graphiti

- Feed existing evidence/event records to the sidecar as episodes.
- Retrieve graph hits in shadow inside `hybrid_memory_retrieve`.
- Trace selected/discarded reasons.
- Keep current-state authority above graph hits.

### Step 5: Optional Mem0/Cognee Shadows

- Add only if Graphiti sidecar leaves clear gaps.
- Use Mem0 for personal memory extraction/search comparison.
- Use Cognee for connector/document graph-RAG experiments.

### Step 6: Promotion Gates

Promote a sidecar lane only if it beats or ties current runtime on:

- current vs stale conflicts
- previous-value recall
- open-ended recall
- source-swamp resistance
- identity/entity resolution
- temporal event ordering
- source explanation
- Telegram acceptance probes

## Immediate Next Tasks

1. Update `tasks.md` so the current next task is OSS sidecar adoption plus pruning, not more Telegram testing.
2. Add a repo inventory script/report that classifies keep/freeze/delete candidates without deleting anything.
3. Add `MemorySidecarAdapter` contract tests.
4. Add a Graphiti-compatible adapter stub behind a disabled feature flag.
5. Run focused tests and commit.

## Sources Checked

- Graphiti / Zep temporal graph memory: https://github.com/getzep/graphiti
- Mem0 open-source memory layer: https://github.com/mem0ai/mem0
- Cognee memory engine: https://www.cognee.ai/
- gbrain/gbrain-evals evaluation approach: https://github.com/garrytan/gbrain
- Zep temporal graph paper: https://arxiv.org/abs/2501.13956
- Mem0 paper: https://arxiv.org/abs/2504.19413
