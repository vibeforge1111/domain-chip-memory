# Spark Persistent Memory Integration Tasks

Last updated: 2026-04-28

This file is the build checklist for turning `domain-chip-memory` into Spark's live persistent memory system. It decides the architecture, names the remaining integration work, and defines the acceptance gates before we go back to heavy Telegram testing.

## Architecture Decision

Spark Persistent Memory v1 is:

```text
Telegram / Spark runtime
  -> Builder memory gate
  -> SparkMemorySDK
  -> append-only evidence log
  -> current-state projection
  -> entity-state temporal layer
  -> typed temporal graph sidecar
  -> hybrid retrieval and rank fusion
  -> capsule compiler v2
  -> final answer with source explanation
```

Chosen backbone:

- Active runtime leader: `summary_synthesis_memory + heuristic_v1`
- Strong challenger kept in eval: `dual_store_event_calendar_hybrid + heuristic_v1`
- Additive sidecar: `typed_temporal_graph`
- Runtime principle: append first, project current state second, resolve conflicts at retrieval time.

This means we are not replacing the proven leader with a new graph system wholesale. We are promoting a layered architecture:

- `summary_synthesis_memory` remains the answer/context backbone.
- Current-state reads handle exact active facts like focus, plan, profile, and active task.
- Entity-state reads handle mutable named entities and attributes with `entity_key`.
- Typed temporal graph handles relationships, aliases, event ordering, negation, reported speech, and provenance-heavy recall.
- Hybrid retrieval fuses current state, historical state, evidence, events, lexical/entity hits, and graph sidecar hits.
- Capsule compiler v2 decides what survives into the actual Telegram answer context.

## Authority Order

When sources conflict, Spark should use this order:

1. Explicit current state
2. Entity-scoped current state
3. Historical state, only for historical questions
4. Recent conversation
5. Retrieved evidence and events
6. Typed temporal graph sidecar
7. Diagnostics and maintenance summaries, only when relevant
8. Workflow state and mission residue, advisory only

Clean diagnostics never close a user focus by themselves. Maintenance success never means user-level work is done unless the user explicitly closes it.

## SOTA Patterns We Are Importing

- Graphiti/Zep: temporal context graph, validity windows, provenance episodes, hybrid retrieval.
- Mem0: fast single-pass extraction, entity linking, multi-signal retrieval, rerank/fusion.
- Letta/MemGPT: memory hierarchy, context-window rebuilding, explicit memory operations.
- SmartSearch: rank/fusion and token-budget selection matter more than merely retrieving more.
- SGMem/event-centric memory: fine-grained evidence units reduce fragmentation.
- APEX-MEM: append-only history plus retrieval-time conflict resolution.
- Hindsight/gbrain-evals: source-swamp, temporal, identity, provenance, and adapter-contract tests.

## Open Source Stack And Pruning Decision

Current decision doc: `docs/OPEN_SOURCE_MEMORY_STACK_AND_PRUNE_PLAN_2026-04-28.md`.

Current prune inventory: `docs/PRUNE_INVENTORY_2026-04-28.md`.

Current architecture diagrams: `docs/MEMORY_STACK_DIAGRAMS_2026-04-28.md`.

Runtime decision:

- Keep `domain-chip-memory` as Spark's memory authority/control plane.
- Adopt a Graphiti-compatible temporal graph as the first serious sidecar.
- Use Mem0 only as a shadow baseline or extraction/search inspiration until it proves value behind our authority rules.
- Use Cognee later only for connector/document graph-RAG needs.
- Use gbrain/BrainBench-style evals to decide promotion, not as runtime memory.

Pruning decision:

- Keep the active runtime path and SDK contracts.
- Freeze old architecture variants as challengers or regression oracles.
- Delete or archive only after dependency checks prove files are unused.
- Do not delete append-only evidence, migration/replay utilities, or tests that encode known Telegram failures.

## Existing Domain-Chip Progress Folded In

The previous `tasks.md` program is not discarded. It is now treated as already-built substrate for this full integration plan.

Completed or partially completed:

- [x] Typed graph sidecar for aliases, commitments, negation, reported speech, unknown records, and temporal events.
- [x] Eval-only typed graph retrieval.
- [x] Typed answer projection so graph hits can become normalized answer candidates.
- [x] Telegram-style multi-party probe pack for commitments, aliases, social graph, grief/support, negation, uncertainty, reported speech, and relative time.
- [x] Lexical/BM25 retrieval lane.
- [x] Entity/alias boost lane.
- [x] Fusion policy draft across summary, exact-turn, typed-graph, lexical, and entity-linked lanes.

Still carried forward:

- [ ] Run shadow retrieval coverage comparison on unseen LoCoMo slices.
- [ ] Run shadow answer comparison with real providers.
- [ ] Strengthen alias binding beyond greeting-only cases.
- [ ] Normalize kinship references such as `mom`, `mother`, `her mother`, and `my mom`.
- [ ] Add longer-range person resolution across sessions.
- [ ] Add validity-window handling for mutable facts.
- [ ] Preserve superseded facts instead of flattening them into one current answer.
- [ ] Build cross-event summary lane over typed conversational events.

Carried-forward operating rules:

- Keep `summary_synthesis_memory` as the backbone.
- Prefer additive layers over rewrites.
- Do not promote runtime behavior from a single offline score.
- Only promote a new memory layer after real-provider and live-regression evidence.

## Phase 0: Architecture Contract

- [x] Select active architecture leader: `summary_synthesis_memory + heuristic_v1`.
- [x] Keep `dual_store_event_calendar_hybrid` as challenger, not runtime default.
- [x] Promote `typed_temporal_graph` as additive sidecar.
- [x] Update SDK contract default to selected leader.
- [x] Add SDK `entity_key` support to current and historical state reads.
- [x] Add Builder pass-through for entity-scoped state reads.
- [x] Document the selected architecture and SOTA mapping.

## Phase 1: Generic Entity-State Writes

Goal: stop treating natural user facts as test-specific profile slots.

- [x] Add a generic entity-state extractor in Builder for named-object facts.
- [x] Capture facts like `the tiny desk plant is named Sol` as:
  - `subject = human:<id>`
  - `predicate = entity.name`
  - `value = Sol`
  - `entity_key = named-object:tiny-desk-plant`
  - provenance = source session, turn, timestamp, raw text
- [x] Support more attributes beyond names:
  - status
  - location
  - owner
  - deadline
  - relation
- [ ] Extend entity attributes further:
  - preference
  - active project
- [x] Keep the original profile/evidence observation append-only while adding the entity projection.
- [x] Project latest active named-object value through entity-scoped current state.
- [x] Let open recall consider `entity.*` current-state records.
- [x] Add tests for broader current value, unrelated entity isolation, and entity-scoped deletion markers.
- [x] Add historical previous-value tests for generic entity attributes.

Acceptance:

- Current question returns the newest value.
- Historical question returns the previous value.
- Another entity using the same predicate does not collide.
- Source explanation can name the entity-state source.

## Phase 2: Hybrid Retrieval Adapter

Goal: make Builder use the full domain-chip read surface instead of narrow deterministic routes.

- [x] Add a `hybrid_memory_retrieve` adapter in Builder.
- [ ] Query these lanes in parallel or deterministic sequence:
  - [x] `get_current_state`
  - [x] `get_historical_state` when an `as_of` is supplied
  - [x] `retrieve_evidence`
  - [x] `retrieve_events`
  - [x] typed temporal graph sidecar shadow lane
  - [ ] typed temporal graph sidecar live backend hits
  - lexical/entity query over recent raw turns
- [ ] Score evidence with:
  - [x] source authority
  - [x] query intent match
  - [x] entity match
  - [ ] recency where relevant
  - [ ] temporal validity
  - [x] provenance quality
  - [x] stale/superseded penalty
- [x] Add rank-fusion trace fields:
  - candidate source
  - candidate score
  - reason selected
  - reason discarded
  - survived_context_budget
- [x] Add score-adaptive truncation so decisive evidence is not retrieved then lost before answer generation.

Acceptance:

- Open-ended questions use memory without exact helper phrases.
- Current-state facts outrank stale workflow residue.
- Broad "what should we do next?" answers from active focus, plan, and relevant evidence, not old diagnostics handoff text.

## Phase 3: Capsule Compiler v2

Goal: compile one compact, source-aware Telegram context packet per turn.

- [x] Define initial hybrid-memory capsule sections:
  - active current state
  - historical state
  - relevant evidence
  - relevant events
  - compiled project knowledge
  - graph sidecar hits
  - supporting context
- [ ] Add explicit entity-state and recent-conversation sections when those lanes are live.
- [ ] Add diagnostics-only-if-relevant section.
- [ ] Keep workflow residue advisory only through source authority and stale penalties.
- [x] Add source authority labels to every section.
- [x] Add conflict notes when stale and current facts both exist.
- [x] Add a hard budget per section.
- [x] Add a final context budget allocator.
- [x] Ensure hybrid-memory answers can explain which section they used.

Acceptance:

- New conversation turns preserve focus, plan, diagnostics, and maintenance summaries without collapsing them into done.
- Clean diagnostics do not auto-close user-level focus.
- Old workflow state never outranks current state.

## Phase 4: Typed Temporal Graph Runtime Bridge

Goal: stop leaving the graph layer in eval-only mode.

- [ ] Define graph sidecar runtime contract:
  - input: evidence/event records
  - output: ranked graph hits with provenance
  - no direct final answer generation
- [ ] Promote existing graph capabilities:
  - alias binding
  - relationship facts
  - commitment records
  - negation records
  - reported speech records
  - temporal events
  - unknown records
- [x] Add Builder shadow bridge for graph sidecar retrieval.
- [ ] Add Builder live backend bridge for graph sidecar retrieval.
- [ ] Add source explanation labels for graph hits.
- [ ] Keep graph sidecar additive until live eval beats or ties current path.

Acceptance:

- Relationship, alias, negation, and event-ordering questions get graph evidence.
- Graph evidence does not override current state unless the query asks for historical/relational context.

## Phase 5: Memory Hygiene And Consolidation

Goal: preserve history while keeping active context clean.

- [ ] Keep append-only evidence as ground truth.
- [ ] Make maintenance update projections, not erase meaning.
- [ ] Keep archived/superseded records recoverable.
- [ ] Add sample audits for:
  - archived
  - superseded
  - deletion markers
  - still-current
- [ ] Add strategic-value review gates for memories the system cannot judge.

Acceptance:

- Maintenance can reduce active footprint without losing historical recall.
- Deleted and archived samples are inspectable.
- User can ask what changed and why.

## Phase 6: Evaluation Harness

Goal: evaluate persistent memory quality before we rely on Telegram vibes.

- [ ] Add gbrain/BrainBench-style test categories:
  - source-swamp resistance
  - identity resolution
  - current vs stale conflict
  - historical value recall
  - provenance explanation
  - open-ended synthesis
  - noisy workflow residue
  - maintenance safety
- [ ] Add LoCoMo/LongMemEval style local slices for:
  - temporal reasoning
  - multi-session reasoning
  - knowledge updates
  - abstention
  - event ordering
- [ ] Compare:
  - current runtime
  - current runtime plus entity-state
  - current runtime plus graph sidecar
  - full hybrid retrieval
- [ ] Publish scorecards under artifacts, not docs.

Acceptance:

- Full hybrid path beats or ties current runtime on selected live-regression packs.
- No regression on current focus/plan, diagnostics, and maintenance routes.
- Source-swamp pack blocks promotion if stale residue wins.

## Phase 7: Telegram Acceptance Tests

Goal: test real user experience after the architecture is wired.

- [ ] Natural recall:
  - seed a normal fact
  - distract for 3 to 5 turns
  - ask naturally
- [ ] Stale conflict:
  - set old value
  - replace with new value
  - ask current and previous
- [ ] Source explanation:
  - ask why it answered that way
  - confirm source class and route
- [ ] Open-ended next action:
  - ask without route words like diagnostics/status/checklist
  - confirm it reasons from active focus and plan
- [ ] New conversation survival:
  - confirm focus, plan, latest diagnostics, and maintenance summary survive correctly
- [ ] Restart behavior:
  - confirm code changes require restart only when process-loaded code changes
  - confirm memory data changes do not require restart

Acceptance:

- Spark feels continuous across turns.
- It remembers useful facts without becoming noisy.
- It handles corrected facts naturally.
- It explains sources without over-answering.
- It stops looping on old diagnostics when the active focus has moved.

## Phase 8: Launch Readiness

- [ ] Add `spark-intelligence diagnostics scan` checks for memory architecture alignment.
- [ ] Add doctor check for SDK runtime architecture mismatch.
- [ ] Add startup log line showing active memory architecture and sidecars.
- [ ] Add operator command to inspect capsule source mix.
- [ ] Add one-command memory quality smoke.
- [ ] Add rollback switch to disable hybrid retrieval and graph sidecar separately.

Acceptance:

- We can inspect what memory architecture is live.
- We can disable risky sidecars without disabling core memory.
- Diagnostics catches stale runtime contracts.

## Build Order

1. Lock the OSS-sidecar architecture and prune map.
2. Generate repo inventory and classify keep/freeze/delete candidates.
3. Add a `MemorySidecarAdapter` contract.
4. Add a Graphiti-compatible sidecar behind a disabled feature flag.
5. Feed evidence/events into the sidecar in shadow mode.
6. Wire Graphiti shadow retrieval into Builder hybrid memory.
7. Finish capsule compiler v2 and score-adaptive truncation.
8. Add gbrain/BrainBench-style promotion gates.
9. Run Telegram acceptance after runtime wiring, not as discovery.
10. Diagnostics and operator polish.

## Fast Integration Protocol

The purpose of the architecture decision is to avoid re-litigating the whole memory system on every small failure. Each integration step should move through this fast path:

1. Use the selected architecture unless new evidence beats it:
   - backbone: `summary_synthesis_memory`
   - challenger: `dual_store_event_calendar_hybrid`
   - sidecar: `typed_temporal_graph`
2. Plug behind an existing contract first:
   - SDK request/response contract
   - Builder memory kernel contract
   - capsule compiler contract
   - retrieval trace contract
3. Add narrow contract tests for the new plug.
4. Run a short regression slice only:
   - touched unit tests
   - one source-swamp/stale-current check
   - one open-ended recall check
5. Run Telegram only as acceptance, not discovery.
6. Promote only if the trace proves:
   - current state kept authority
   - stale/advisory sources stayed advisory
   - provenance survived
   - answer context used the intended memory lane

Do not spend hours on broad testing before the contract-level plug exists. Broad benchmarks are for promotion gates, not for deciding every wiring step.

## Stop Conditions

Do not promote a memory layer if:

- it lacks provenance;
- it makes stale workflow residue outrank current state;
- it deletes history instead of superseding or archiving it;
- it improves one scripted Telegram test but fails source-swamp or open-ended recall;
- it cannot explain which source class it used;
- it increases context volume without measured answer-quality gain.

## Current Next Task

Build the next capsule completion layer:

> Add a live recent-conversation retrieval lane or adapter so the capsule's recent-conversation section has real candidates instead of only section support.

This is the next real integration step before another Telegram test loop or broad benchmark run.

## Current Build Progress

- [x] Add OSS memory stack decision.
- [x] Add dependency-safe prune inventory.
- [x] Add architecture diagrams.
- [x] Add `MemorySidecarAdapter` contract and disabled no-op adapter.
- [x] Add Graphiti-compatible adapter stub behind a disabled feature flag.
- [x] Add evidence/event episode export into sidecar contract shape.
- [x] Add Graphiti shadow retrieval lane to `hybrid_memory_retrieve`.
- [x] Add Obsidian / LLM-wiki packet reader source.
- [x] Add Mem0 shadow adapter.
- [x] Add initial hybrid-memory context packet with source labels and score-adaptive budgets.
- [x] Add explicit entity-state / recent-conversation / diagnostics capsule sections.
- [x] Add operator capsule source-mix inspector.
- [ ] Add live recent-conversation retrieval lane or adapter.
