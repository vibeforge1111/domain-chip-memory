# Spark Persistent Memory Integration Tasks

Last updated: 2026-04-29

This file is the build checklist for turning `domain-chip-memory` into Spark's live persistent memory system. It decides the architecture, names the remaining integration work, and defines the acceptance gates before we go back to heavy Telegram testing.

## Task System Rules

This file is the operating system for the memory build. Every memory change should map to a line here before or immediately after implementation.

Rules:

1. Work from the Active Execution Queue first.
2. Commit often, with one meaningful slice per commit when possible.
3. Keep `domain-chip-memory` as the architecture/control-plane tracker.
4. Implement runtime behavior in the owning repo:
   - `spark-intelligence-builder`: memory write/read logic, capsule, ledgers, diagnostics.
   - `domain-chip-memory`: chip contracts, sidecar adapters, eval harnesses, docs.
   - `spark-cli`: installer and local dependency profiles.
   - `spawner-ui`: memory-quality dashboard and operator UI.
   - `spark-telegram-bot`: Telegram ingress/restart/runtime wiring only.
5. Do not add an external dependency, copied source, or sidecar without the pre-implementation license checklist and adoption record.
6. Tests should be contract-first, then Telegram acceptance. Telegram is a final human-facing gate, not the discovery loop.

## Definition Of Done

Spark persistent memory is "great working memory" only when all of these are true:

- Natural conversation can create useful memory without requiring `for later`.
- Explicit save commands still work, but they are not the main UX.
- Current-state facts, entity-state facts, episodes, beliefs, procedural lessons, diagnostics, and workflow residue are separate lanes.
- Identity corrections and target-repo corrections become authoritative supersessions immediately.
- Weak, speculative, emotional, private, or noisy statements stay scratchpad/raw episode or get dropped.
- Every memory write has salience, confidence, promotion stage, why-saved, source route, and gate outcome.
- Every memory answer can name the source class and whether it used current state, older memory, raw episode, graph sidecar, inference, diagnostics, or workflow residue.
- Episodic summaries answer "what did we build today?", "what changed?", and "what is still open?" without raw transcript dumps.
- Timeout/task recovery resumes from a pending-task ledger.
- Repo resolution knows what project/component Spark is touching before build missions.
- Graphiti/Hindsight/Mem0 are optional, licensed, observable sidecars or comparators; they never replace Spark's authority order.
- Maintenance compresses active memory without destroying historical recall.
- The memory-quality dashboard is inside `spawner-ui` and wired to real ledgers.
- Diagnostics show active architecture, sidecars, source mix, context budget, quality gates, and stale/advisory source drift.

## Active Execution Queue

Work in this order unless a production break interrupts it:

### Track A: Write Discipline And Salience

- [x] Add docs/license gate before external sidecar integration.
- [x] Add Builder-side `memory.salience` gate for profile/current-state writes.
- [x] Mark preferred-name corrections as authoritative identity supersessions.
- [x] Extend salience to generic memory candidates: current-state, structured evidence, raw episode, belief, and drop.
- [x] Add salience metadata to structured evidence, raw episode, belief, and memory-candidate assessment events.
- [x] Add live quality-gate records for rejected memory candidates, not only secret-like profile writes.
- [x] Reduce blocked/not-promotable memory-lane rows by routing candidates into the correct lane or explicit drop reason.

### Track B: Authoritative State And Supersession

- [x] Entity-state current and previous recall works for owner/location/status/deadline/relation/preference/project/blocker/priority/decision/next action/metric.
- [x] Entity summary recall answers broad questions like "what do you know about the GTM launch?".
- [x] Preferred-name corrections are entity-keyed current identity writes.
- [ ] Add current-state supersession metadata for target repo, active project, current task, runtime capability, and user identity.
- [ ] Preserve superseded values for historical questions without letting them answer current questions.
- [ ] Add explicit closure markers for focus/plan so clean diagnostics never imply user-level closure.

### Track C: Episodic And Semantic Continuity

- [x] Add session summary writer: what changed, decisions, open questions, repos touched, artifacts created, promises made.
- [x] Add daily/project summary writer.
- [ ] Add semantic consolidation beyond archive/delete/supersede.
- [ ] Increase same-session continuity beyond 3 turn pairs / 260-char compaction.
- [ ] Add large-context reservoir targeting 200k+ reconstructable context, separate from compact Telegram packet.
- [ ] Add "what did we build today?" and "what else do you remember?" source-aware routes.

### Track D: Timeout, Task, And Workflow Recovery

- [ ] Add pending-task ledger: original request, target repo/component, command/mission id, timeout point, last evidence, next retry.
- [ ] Store failed target resolution, wrong build target, bad self-review, and timeout patterns as procedural lessons.
- [ ] Resume after timeout without asking "what happened?".
- [ ] Inject runtime capability state so Spark does not underclaim local file/Spawner/Codex access.

### Track E: Repo Resolution And Builder Safety

- [ ] Add local repo/module/capability index.
- [ ] Add hard target-repo confirmation gate before builds and file-writing missions.
- [ ] Add stale Spawner payload detection and drift warning.
- [ ] Ground build-quality self-review in target repo, diff, tests, route, and demo state.

### Track F: Retrieval, Capsule, And Source Attribution

- [x] Hybrid retrieval uses current state, historical state, evidence, events, recent conversation, wiki packets, and shadow graph lane.
- [x] Capsule source-mix promotion gates exist.
- [ ] Make source-aware recall universal for all memory answers.
- [ ] Add graph sidecar hits with validity windows and provenance as advisory candidates.
- [ ] Add explicit context packet sections for episodic summary, procedural lesson, pending task, repo capability, and graph sidecar.
- [ ] Add operator command to inspect context reservoir budget and selected packet contents.

### Track G: OSS Sidecars And Installer

- [x] Decide hybrid OSS stack: Graphiti first, Mem0 shadow, Hindsight procedural, Cognee deferred.
- [x] Add third-party notice scaffold and adoption checklist.
- [ ] Add optional dependency groups in `domain-chip-memory`, default install light.
- [ ] Add Graphiti adoption record before dependency/import.
- [ ] Add Graphiti live adapter behind disabled feature flag.
- [ ] Add Spark CLI memory-sidecar installer profile for Graphiti.
- [ ] Add Mem0 shadow comparator only after salience/retrieval contracts are stable.
- [ ] Add Hindsight/procedural sidecar prototype for corrections, failed tools, timeouts, and repeated mistakes.
- [ ] Add status/verify/diagnostics visibility for each sidecar and its fallback mode.

### Track H: Memory Lanes, Quality Gates, And Dashboard

- [x] Memory lane and quality-gate architecture documented.
- [ ] Populate policy gate, quarantine, delivery registry, and memory lane records from real memory decisions.
- [ ] Make memory lanes human-readable.
- [ ] Add operator inspect commands for lane decisions, blocked candidates, salience reasons, and promotion outcomes.
- [ ] Migrate memory-quality dashboard into `spawner-ui`.
- [ ] Wire dashboard to actual ledgers, not standalone mock state.

### Track I: Evaluation Harness

- [ ] Add gbrain/BrainBench-style source-swamp, identity, temporal, provenance, and adapter-contract tests.
- [x] Add curated Builder memory unit-test batches so architecture slices can run contract-first before Telegram acceptance.
- [ ] Add LoCoMo/LongMemEval-style local slices for temporal reasoning, multi-session reasoning, updates, abstention, event ordering.
- [ ] Compare current runtime, entity-state runtime, graph sidecar shadow, and full hybrid path.
- [ ] Publish scorecards under artifacts, not docs.
- [ ] Block promotion if stale/advisory sources outrank current state.

### Track J: Telegram Acceptance

- [x] Current and previous entity-state facts pass supervised Telegram tests.
- [x] Source explanations identify entity-state current/history routes.
- [ ] Re-run short Spark AGI/Tester source-explanation check after deployment.
- [ ] Test natural memory without `for later`.
- [ ] Test stale/current conflicts across project, identity, repo, task, preference, and startup workflow scenarios.
- [ ] Test broad workflow recall: project building, startup ops, marketing/content, investor updates, operating-system handoffs.
- [ ] Test restart behavior: code changes require restart, memory data changes do not.

## Current Commit Checkpoints

- `domain-chip-memory`: `732ab81` tracks memory lane cleanup progress.
- `spark-intelligence-builder`: `614515c` adds daily and project memory summaries for semantic continuity.
- Next commit target: pending-task ledger for timeout and workflow recovery in `spark-intelligence-builder`.
- Current fast validation command: `python scripts/run_memory_test_batch.py --batch fast-contract -- --maxfail=1`.

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

## Five-Layer Memory Target

Spark memory should behave as a hierarchy, not as a pile of saved snippets:

1. Working scratchpad: active conversation state. It vanishes unless promoted.
2. Salient facts: discrete, typed, timestamped, queryable slots such as owner, blocker, deadline, identity, preference, and current focus.
3. Episodic trace: compressed records of what changed, what was decided, what was left open, and what Spark promised.
4. Decay and promotion: every natural memory starts with confidence and salience; repetition, correction, explicit confirmation, and task relevance promote it. Unused or weak memories decay.
5. Retrieval gating: active focus, target repo, project, task, and source authority decide what is recalled. Similarity alone is not enough.

`For later` remains an explicit high-confidence save signal, but it is not the product experience we are building toward. Normal conversation must pass through salience scoring and promotion gates before becoming durable memory.

## Live Gap Register

These are the current production-quality gaps surfaced through Telegram, Spawner, and Codex testing:

- [ ] Wrong build target: `/memory-quality` was requested inside `spawner-ui`, but a standalone `spark-memory-quality-dashboard` was built instead.
- [ ] Stale target context: Spawner payloads can point at old repos such as `vibeship-spark-intelligence`; every build needs a hard target-repo confirmation gate.
- [ ] Episodic memory too thin: the live capsule keeps too little same-session flow, so Spark recalls isolated facts but loses the actual work narrative.
- [ ] Identity corrections are not authoritative enough: name corrections must become high-priority identity supersessions, not raw episodic text.
- [ ] Quality gates exist but are empty: policy gates, quarantine records, and delivery registry need live writes.
- [ ] Memory lane is mostly blocked/not-promotable: observations are accumulating without enough useful promotion into durable memory.
- [ ] No semantic daily consolidation: maintenance compresses lifecycle state, but does not yet produce rich daily/project summaries.
- [ ] Timeouts lose task continuity: Spark needs a pending-task ledger with original request, active component, mission id, timeout point, and next retry.
- [ ] Runtime capability state is inconsistent: Spark should know whether it can inspect local files, Spawner, Codex, and repos before answering.
- [ ] Self-review is not grounded: build quality ratings must inspect target repo, diff, tests, route, and demo state before answering.
- [ ] Source attribution is still uneven: answers must distinguish current capsule, older memory, raw episode, inference, and unverified claims.
- [ ] Memory-quality dashboard is standalone: migrate useful pieces into `spawner-ui` and wire them to real ledgers.
- [ ] Episodic recall is missing: Spark needs session/day/project summaries for "what did we build today?" and "what else do you remember?".
- [ ] Source-aware recall needs to be universal: answers should say whether memory came from current state, older memory, raw episode, graph sidecar, inference, diagnostics, or workflow residue.
- [ ] Context memory is too small for real work: live Builder capsule code currently defaults to a 5,000-character rendered capsule, 3 recent same-session turn pairs, and 260-character compacted turns in `src/spark_intelligence/context/capsule.py`.
- [ ] Context reservoir target should support 200k+ available memory context through retrieval and packet assembly, while keeping per-answer Telegram packets compact.
- [ ] Repo resolution is not strong enough: Spark needs a local repo/module/capability index so it knows where things live and what it can inspect before building or answering.

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

Current OSS borrowing plan: `docs/OSS_MEMORY_BORROWING_PLAN_2026-04-28.md`.

Current system connection plan: `docs/SPARK_MEMORY_CONNECTION_PLAN_2026-04-28.md`.

Current system inspection and installer plan: `docs/SPARK_MEMORY_SYSTEM_INSPECTION_AND_INSTALLER_PLAN_2026-04-28.md`.

Current memory lanes and quality gates map: `docs/MEMORY_LANES_AND_QUALITY_GATES_2026-04-28.md`.

Current pre-implementation docs/license checklist: `docs/PRE_IMPLEMENTATION_DOCS_AND_LICENSE_CHECKLIST_2026-04-28.md`.

Runtime decision:

- Keep `domain-chip-memory` as Spark's memory authority/control plane.
- Adopt Graphiti as the first serious temporal graph sidecar.
- Use Mem0 only as a shadow baseline or extraction/search inspiration until it proves value behind our authority rules.
- Use Cognee later only for connector/document graph-RAG needs.
- Use gbrain/BrainBench-style evals to decide promotion, not as runtime memory.

Open-source borrowing policy:

- Prefer permissive OSS that is MIT, Apache-2.0, BSD, or similarly business-compatible.
- Graphiti is Apache-2.0, not MIT; it is approved as a sidecar dependency if license notices and telemetry settings are handled correctly.
- Borrow architecture patterns freely, but do not let external systems replace Spark's authority order or source explanation contract.
- Disable optional telemetry by default for local Spark installs unless the operator explicitly opts in.

Candidate OSS components to evaluate:

- Graphiti / Zep OSS core (Apache-2.0): temporal graph sidecar, entity/relationship history, validity windows, episode provenance, hybrid graph/keyword/semantic retrieval.
- Hindsight (MIT): learned experience/procedural memory, reflection over failures/corrections, memory that improves agent behavior instead of only recalling facts.
- MemMachine (Apache-2.0): multi-layer working/profile/episodic design and ground-truth-preserving retrieval ideas.
- Mem0 OSS (Apache-2.0): extraction/entity-linking/retrieval scoring baseline, useful as a shadow comparator rather than the authority layer.
- Letta/MemGPT concepts: memory hierarchy, self-editing memory, context-window management; borrow patterns unless a clean OSS component fits.
- LongMem-style/MCP memory tools (license to verify per repo): candidate for external recall API patterns and smoke comparisons.

Evaluation rule:

- Use existing OSS where it cleanly provides a layer: graph, learned experience, profile/episodic storage, eval harness, or tooling.
- Keep Spark-owned contracts for target repo binding, source attribution, salience gates, authority order, and Telegram UX.
- Add new systems behind feature flags and scorecards before making them runtime-default.

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
- [x] Extend entity attributes further:
  - preference
  - active project
  - blocker
  - priority
  - decision
  - next action
  - metric
- [x] Keep the original profile/evidence observation append-only while adding the entity projection.
- [x] Project latest active named-object value through entity-scoped current state.
- [x] Let open recall consider `entity.*` current-state records.
- [x] Add tests for broader current value, unrelated entity isolation, and entity-scoped deletion markers.
- [x] Add historical previous-value tests for generic entity attributes.
- [x] Make current entity-state recall source explanations route- and attribute-aware, not just history explanations.
- [x] Separate decisive entity-state support records from wider candidate packets in recall traces.
- [x] Route exact entity current recall through direct `get_current_state(subject, predicate, entity_key)` before broad retrieval.
- [x] Preserve matching provenance metadata, including location prepositions, in direct current-state projection records.
- [x] Route entity history questions through current-state anchoring plus direct `get_historical_state` before event fallback.
- [x] Add broad entity-state summary recall for project/workflow questions such as `what do you know about the GTM launch?`.

Acceptance:

- Current question returns the newest value.
- Historical question returns the previous value.
- Another entity using the same predicate does not collide.
- Source explanation can name the entity-state source, route, and attribute for current and historical reads.
- Exact entity recall traces show `retrieved_roles=entity_state` and a decisive `record_count`, while preserving broader `candidate_record_count`.
- Entity recalls, including location, use `read_method=get_current_state` with `record_count=1` and preserved location prepositions.
- Entity history source explanations show `read_method=get_historical_state` when direct historical state answers.
- Workflow entity recalls cover building and operating scenarios such as launch blockers, startup priorities, investor-update decisions, sprint next actions, and campaign metrics.
- Broad entity summary recalls gather multiple current entity attributes, name the `memory_entity_state_summary_query` route, and do not collapse to a single blocker/metric/owner field.

## Phase 1.5: Salience, Promotion, And Write Discipline

Goal: stop requiring explicit `for later` commands and make natural conversation memory-worthy only when it earns promotion.

- [ ] Use `docs/SPARK_MEMORY_CONNECTION_PLAN_2026-04-28.md` as the build contract for connecting capture, salience, authority ledger, Graphiti, procedural memory, Mem0 shadowing, retrieval, and capsule v2.
- [ ] Use `docs/MEMORY_LANES_AND_QUALITY_GATES_2026-04-28.md` as the human-readable lane and gate contract.
- [ ] Use `docs/PRE_IMPLEMENTATION_DOCS_AND_LICENSE_CHECKLIST_2026-04-28.md` before adding dependencies, sidecars, installer profiles, or copied OSS code.
- [ ] Add a Builder-side `memory.salience` gate before writes.
- [ ] Score each candidate on:
  - explicitness
  - active focus/project relevance
  - entity importance
  - decision/action/owner/blocker/status signal
  - correction or supersession signal
  - repetition or confirmation
  - user preference/identity sensitivity
  - small-talk/emotional/noise risk
- [ ] Emit one of:
  - `drop`
  - `scratchpad`
  - `raw_episode`
  - `structured_evidence`
  - `current_state_candidate`
  - `current_state_confirmed`
- [ ] Store salience metadata:
  - `salience_score`
  - `confidence`
  - `promotion_stage`
  - `mention_count`
  - `last_referenced_at`
  - `decay_after`
  - `why_saved`
- [ ] Treat explicit phrases such as `for later`, `remember`, and `current X is` as high-confidence signals, not the only path.
- [ ] Make identity corrections immediate authoritative supersessions.
  - [ ] Detect `identity_correction` from phrases such as `I'm not X, I'm Y`, `Actually my name is Y`, and `call me Y`.
  - [ ] Promote direct name corrections to `profile.preferred_name` current state.
  - [ ] Mark older identity values stale/superseded while preserving historical recall.
  - [ ] Store `why_saved=identity_correction_supersession` and source provenance.
- [ ] Route uncertain claims and brainstorming to scratchpad/episode unless repeated or confirmed.
- [ ] Promote repeated medium-salience facts into current state after confirmation.
- [ ] Add quality-gate ledgers:
  - policy gate records
  - quarantine records
  - delivery registry records
  - bad-claim/bad-memory rejection reasons
- [ ] Make quality gates live in memory writes, not only outbound security:
  - source/provenance gate
  - privacy/security gate
  - target-scope gate
  - claim-quality gate
  - lane-classification gate
  - authority/supersession gate

Acceptance:

- Spark can save an important natural statement without `for later`.
- Spark does not save ordinary small talk as durable memory.
- Corrections supersede stale identity/project facts immediately.
- Source explanation can say why a memory was saved and why it was recalled.
- Blocked/not-promotable rows shrink as real candidates get correctly promoted or dropped.
- Identity corrections are not stored only as raw episodic text.
- Quality-gate, quarantine, delivery, salience, and supersession ledgers are populated by real memory decisions.

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
  - [ ] lexical/entity query over recent raw turns
  - [x] preserve location preposition metadata in direct current-state projections so location recall can use direct reads too
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
- [ ] Add episodic summary sections for session/day/project recall.
- [ ] Add a large-context reservoir interface targeting 200k+ available context for deep reconstruction, separate from the compact per-answer packet.
- [ ] Increase same-session continuity beyond the current 3 recent turn pairs / 260-character compaction by retrieving ranked recent spans and summaries.
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
- Spark can answer "what did we build today?" from episodic summaries.
- Spark can enter a deep-context mode without flooding normal replies.

## Phase 4: Typed Temporal Graph Runtime Bridge

Goal: stop leaving the graph layer in eval-only mode and use Graphiti for the real temporal graph sidecar.

- [ ] Define graph sidecar runtime contract:
  - input: evidence/event records
  - output: ranked graph hits with provenance
  - no direct final answer generation
- [ ] Add Graphiti as a runtime sidecar behind `domain-chip-memory`, not as the primary memory authority.
- [ ] Choose local backend path:
  - [ ] Kuzu for simplest embedded/local dev path if compatible with current Graphiti support.
  - [ ] FalkorDB or Neo4j for richer graph operations if local service management is acceptable.
- [ ] Disable Graphiti telemetry by default in Spark-managed launches.
- [ ] Map Spark memory records to Graphiti episodes:
  - [ ] raw Telegram turn
  - [ ] structured evidence
  - [ ] entity-state change
  - [ ] decision/action/owner/blocker events
  - [ ] tool/build/mission events
- [ ] Map Graphiti outputs back to Spark candidates:
  - [ ] entity
  - [ ] relationship
  - [ ] temporal fact
  - [ ] validity window
  - [ ] episode provenance
  - [ ] confidence/source score
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
- [ ] Add graph-sidecar acceptance probes for:
  - same entity across aliases
  - previous/current conflict with validity windows
  - owner/decision/action relationships
  - project-to-task dependencies
  - "what changed today?" and "why do you think that?" provenance

Acceptance:

- Relationship, alias, negation, and event-ordering questions get graph evidence.
- Graph evidence does not override current state unless the query asks for historical/relational context.
- Graphiti facts can explain their episode provenance and validity window.
- Graphiti improves broad project/workflow recall without flooding the capsule.

## Phase 4.5: Episodic And Procedural Continuity

Goal: make Spark remember work, interruptions, and project flow rather than isolated facts.

- [x] Add session summary writer:
  - what changed
  - decisions made
  - open questions
  - repos touched
  - artifacts created
  - promises Spark made
- [x] Add daily/project summary writer.
- [ ] Add pending-task ledger:
  - original request
  - target repo/component
  - active command or mission id
  - timeout/interruption point
  - last verified evidence
  - next retry step
- [ ] Add source labels for episodic and procedural recalls.
- [ ] Store procedural lessons for bad memory, bad claims, failed deliveries, stale target context, and wrong build targets.
- [ ] Add "what did we build today?" and "resume what timed out" acceptance probes.

Acceptance:

- Spark can recover after a timeout without asking "what happened?"
- Spark can summarize a day's build work from durable summaries, not raw transcript dumps.
- Spark can distinguish facts, episodes, procedural lessons, and inferences.

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
- [ ] Workflow scenario expansion:
  - project building: owners, blockers, dependencies, decisions, status changes
  - startup operations: assumptions, risks, GTM motions, investor updates, hiring asks
  - marketing/content: campaign goals, audience hypotheses, channel learnings, performance notes
  - operating-system use: task handoffs, artifact locations, preferences, recurring constraints
  - keep the same authority order and query lanes instead of adding route-specific shortcuts

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
- [ ] Add operator command to inspect context reservoir budget and selected packet contents.
- [ ] Add repo/module/capability index visibility to `spark status`, `spark verify`, and diagnostics.
- [ ] Add one-command memory quality smoke.
- [ ] Add rollback switch to disable hybrid retrieval and graph sidecar separately.

Acceptance:

- We can inspect what memory architecture is live.
- We can disable risky sidecars without disabling core memory.
- Diagnostics catches stale runtime contracts.

## Build Order

1. Lock the OSS-sidecar architecture and prune map.
2. Complete the pre-implementation docs/license gate:
   - choose project license or keep license-pending explicit
   - add/update `THIRD_PARTY_NOTICES.md`
   - add adoption record before Graphiti, Mem0, Hindsight, Cognee, or copied OSS code
3. Generate repo inventory and classify keep/freeze/delete candidates.
4. Add a `MemorySidecarAdapter` contract.
5. Add a Graphiti-compatible sidecar behind a disabled feature flag.
6. Feed evidence/events into the sidecar in shadow mode.
7. Wire Graphiti shadow retrieval into Builder hybrid memory.
8. Finish capsule compiler v2 and score-adaptive truncation.
9. Add gbrain/BrainBench-style promotion gates.
10. Run Telegram acceptance after runtime wiring, not as discovery.
11. Diagnostics and operator polish.

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

Move from acceptance probing into integration:

1. Extend the Builder-side salience gate beyond profile/current-state writes into generic candidate memory writes.
2. Make quality gates populate real memory-write ledgers across profile, entity, episodic, and procedural writes.
3. Add optional sidecar dependency groups in `domain-chip-memory`, keeping default install light.
4. Add a Spark CLI memory-sidecar installer profile or bundle for Graphiti first.
5. Implement the Graphiti live adapter behind a disabled feature flag.
6. Add status/verify/diagnostics visibility for active memory architecture and sidecars.
7. Add episodic consolidation and pending-task recovery as the next continuity layer.
8. Add local repo/module/capability indexing before more build automation.

The already-green Telegram acceptance loop remains the fast human-facing gate, not the main discovery path. The entity-state fixes for current/previous values, attribute isolation, source explanations, and workflow-like attributes are accepted substrate. The next layer must plug behind the same current-state authority, stale-conflict, and source-mix promotion checks.

Implementation starts in `spark-intelligence-builder` with `memory.salience`, then moves to `domain-chip-memory` optional extras and `spark-cli` installer wiring.

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
- [x] Add live recent-conversation retrieval lane or adapter.
- [x] Add source-swamp and capsule source-mix promotion gates.
- [x] Surface promotion-gate status in operator/Telegram diagnostics.
- [x] Add Telegram memory-quality acceptance pack backed by promotion-gate assertions.
- [x] Run local Telegram acceptance loop and triage failed memory-quality lanes.
- [x] Promote memory-quality gate failures from trace-only reporting into blocking acceptance criteria.
- [x] Export supervised Spark AGI/Tester Telegram acceptance prompt pack.
- [x] Run the real Spark AGI/Tester Telegram loop after gate promotion.
- [x] Calibrate source-mix stability so clean current-state authority plus supporting evidence passes while supporting-only packets still warn.
- [x] Extend Telegram acceptance with mutable entity conflict recall: `Mira` -> `Sol` -> previous name.
- [x] Add entity-attribute recall gates so location questions cannot be answered from name memories.
- [x] Extend Telegram acceptance with two-entity location isolation and stale/current location history.
- [x] Fix live SDK artifact filtering for metadata-backed `memory_role=current_state` entity records.
- [x] Add route-specific source explanations for entity-state history and open memory recall.
- [x] Fix entity-owner corrections so `Actually, Maya owns the launch checklist` updates `entity.owner`, not `profile.current_owner`.
- [x] Add owner conflict regression for current owner, previous owner, and unrelated owner isolation.
- [x] Make entity-state history source explanations attribute-aware for owner/location/etc.
- [x] Add owner conflict sequence to the CLI Telegram acceptance pack.
- [x] Add status/deadline/relation/preference/project entity-state parsing, current recall, and previous-value recall.
- [x] Extend CLI Telegram acceptance from owner/location into broader mutable entity attributes.
- [x] Complete the docs/license gate before external memory sidecar integration.
- [x] Add Builder-side `memory.salience` gate for profile/current-state writes.
- [x] Add salience metadata on accepted profile writes: score, confidence, promotion stage, and why-saved rationale.
- [x] Populate memory lane records for accepted profile writes through keepability and promotion disposition.
- [x] Block secret-like durable profile writes through the salience policy gate before SDK write.
- [x] Treat identity corrections as high-salience supersession writes.
- [x] Make preferred-name corrections entity-keyed authoritative current identity writes.
- [x] Add deterministic session summary writer for episodic continuity.
- [x] Add daily/project summary writer for semantic continuity.
- [x] Add curated memory unit-test batches: `fast-contract`, `telegram-memory-unit`, `architecture-promotion`, `diagnostics-ledgers`, and `full-memory-local`.
- [ ] Re-run the short Spark AGI/Tester source-explanation check after deploying the source-mix calibration.
