# Memory SOTA Gap Audit 2026-04-27

This audit compares Spark's `domain-chip-memory` and connected Builder/Telegram runtime against current long-term conversational memory systems and agent context-engineering patterns.

## Executive Verdict

Spark is not starting from zero. `domain-chip-memory` already contains many of the right concepts: current state, historical state, events, provenance, abstention, maintenance, typed temporal graph experiments, benchmark harnesses, and integration contracts.

The main gap is runtime integration. The stronger memory work mostly lives as a benchmark lab, SDK scaffold, shadow path, or targeted route. Telegram/Builder can answer current focus, current plan, and several profile facts because those are routed through deterministic current-state reads. That is useful and should stay. But it is not the same as a general persistent-memory kernel that can extract, rank, explain, and synthesize memory evidence across open-ended conversations.

Short version:

- `domain-chip-memory` is directionally right.
- Spark is using it partially right.
- The live hot path still relies too much on typed current-state shortcuts and regex observation packs.
- The next work should make `domain-chip-memory` the evidence/retrieval kernel behind Builder, not just the active chip or benchmark repo.

## External Systems Inspected

### LoCoMo

Source: https://arxiv.org/abs/2402.17753 and https://github.com/snap-research/locomo

Relevant idea: long-term conversation memory is not only fact lookup. LoCoMo stresses multi-session dialogue, temporal event graphs, social dynamics, event summaries, and long-range causal consistency. The dataset includes conversations, observations, session summaries, event summaries, and QA annotations.

Spark implication: our current current-state tests are too easy. They validate write/read plumbing, not social or temporal memory quality. The LoCoMo unseen-slice docs in Builder already show this: exact current-state recall improved, but unseen relationship/entity/social recall remains weak.

### LongMemEval

Source: https://github.com/xiaowu0162/LongMemEval

Relevant idea: evaluate multiple long-term abilities across timestamped sessions, including user memory, assistant memory, preference updates, knowledge updates, and abstention. The benchmark separates retrieval from answer generation and uses evidence sessions.

Spark implication: Builder should continue using LongMemEval for regression, but we should not overfit to one high headline score. The Phase A decision showed `summary_synthesis_memory` strong on LongMemEval but still weak on LoCoMo.

### EMem

Source: https://github.com/KevinSRR/EMem

Relevant implementation pattern:

- Conversations are decomposed into Elementary Discourse Units (EDUs), not only summarized chunks.
- EDUs carry participants, temporal cues, source sessions, arguments, and provenance.
- Retrieval has a dense-search plus LLM-filter path.
- EMem-G adds a heterogeneous graph over sessions, EDUs, and arguments, then uses Personalized PageRank to propagate relevance.

Spark comparison:

- We have typed atoms and event-like packets, but not a live EDU/evidence-unit layer in Telegram.
- We have typed temporal graph experiments, but not graph propagation or LLM candidate filtering in the runtime hot path.
- We should borrow the non-lossy evidence-unit idea before adding more summary layers.

### Cognis

Source: https://github.com/Lyzr-Cognis/cognis

Relevant implementation pattern:

- Owner, agent, and session scoping are explicit.
- Extracted memories are global to owner/agent.
- Raw messages are session-scoped.
- Search fuses vector retrieval, BM25, immediate raw-message recall, recency boost, temporal boost, and RRF.
- Extraction uses LLM fact extraction plus ADD/UPDATE/DELETE/NONE decisions against similar existing memories.

Spark comparison:

- Spark has current-state supersession and maintenance, but general memory extraction is still much more regex-shaped.
- Spark does not yet have a production-grade hybrid retrieval scorer for user memory.
- Spark should borrow the scoping model and fusion pipeline, but keep stricter write gates than Cognis by default.

### Graphiti / Zep

Source: https://github.com/getzep/graphiti

Relevant implementation pattern:

- Temporal context graph with entities, relationships, facts, validity windows, and episodes.
- Every derived fact links back to raw source episodes.
- Facts are invalidated rather than overwritten.
- Retrieval combines semantic search, BM25, and graph traversal.
- Graph construction is incremental.

Spark comparison:

- `domain-chip-memory` already has typed temporal graph concepts.
- Builder current-state snapshots preserve the latest truth, but runtime answers do not consistently reason over validity windows and invalidations.
- The missing production concept is a graph-backed or graph-like evidence layer with temporal validity and provenance surfaced to answer generation.

### Mem0

Source: https://github.com/mem0ai/mem0

Relevant implementation pattern:

- Agent-generated facts are treated as memory, not only user-authored facts.
- Entity linking boosts retrieval.
- Retrieval combines semantic, BM25 keyword, and entity matching.
- The v3 direction is ADD-only extraction with accumulation plus retrieval filtering, which trades write-time correctness for simpler ingestion.

Spark comparison:

- Spark should not blindly copy ADD-only accumulation because our cleanup/resolution goals are stricter.
- But we should copy the entity-linking and agent-action memory idea. When Spark confirms an action, that can become evidence with provenance and retention class.

### Supermemory

Source: https://github.com/supermemoryai/supermemory

Relevant implementation pattern:

- Memory, RAG, profiles, connectors, and file processing are one context stack.
- It exposes memory, recall, and context surfaces.
- It separates static profile facts from dynamic recent context.
- It treats memory as fact tracking over time, not ordinary RAG chunks.

Spark comparison:

- Spark has diagnostics, connectors, KB export, and context capsules, but they are not yet unified into one memory/context service.
- We need a profile/context API shape that Builder can call once per turn: current profile, active focus/plan, relevant memories, relevant docs/connectors, and source authority.

### Letta

Source: https://github.com/letta-ai/letta

Relevant implementation pattern:

- Agents are stateful and configured with named memory blocks such as human/persona.
- Archival passages and source passages exist as separate durable structures.
- The agent runtime explicitly manages memory as part of state, not a bolt-on afterthought.

Spark comparison:

- Spark has a richer domain-chip idea than simple memory blocks, but the runtime needs the same clarity: stable blocks for human profile, persona, active work, recent dynamic context, archival evidence, and tool/system state.

### Anthropic Context Engineering

Source: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

Relevant idea: context is finite, attention degrades with excess context, and strong agents use just-in-time retrieval plus compact, high-signal context. Claude Code is cited as a hybrid pattern: some context upfront, but most discovery via targeted tools.

Spark implication:

- Do not simply stuff more memory into the prompt.
- Build a retrieval and capsule compiler that returns the smallest useful evidence set with clear authority classes.
- Give Spark tools to inspect deeper memory only when needed.

## What Spark Already Has

### In `domain-chip-memory`

- Benchmark-first memory lab and default Spark memory chip.
- SDK concepts for writes, current state, historical state, evidence retrieval, event retrieval, answer explanation, maintenance, and KB snapshot export.
- Integration contract that says Builder should provide entity normalization, write gates, query routing, provenance, abstention, shadow replay, and maintenance scheduling.
- Typed temporal graph experiments.
- Multiple architecture variants, including `summary_synthesis_memory` and `dual_store_event_calendar_hybrid`.

### In Builder / Telegram

- Live current-state reads for focus, plan, and profile-style facts.
- Context capsule with source authority classes.
- Memory maintenance and audit samples.
- Diagnostics surfaced into Telegram with Markdown note attachment.
- Active memory chip routing.
- Explicit Builder-side runtime pin to `summary_synthesis_memory`.
- Generic observation packs for plan/focus/decision/blocker/status/etc.

## What Is Not Built Right Yet

### 1. The live path is not using the full memory architecture

The Builder docs already say the benchmark work proved stronger retrieval paths, while Builder relies mostly on typed current-state reads for Telegram memory questions. That still matches what the code shows.

Impact: Spark can pass direct recall tests but fail open-ended memory questions, especially if the phrasing does not trigger a deterministic route.

### 2. Extraction is too route/regex-shaped

`generic_observations.py` has useful write gates, but it is a list of explicit patterns. That works for "my current focus is X" and "remember this test fact," but it misses natural, implicit, multi-turn, emotional, social, and project-state memory.

Impact: important user context can remain only in recent conversation, never promoted into durable memory.

### 3. Retrieval is not hybrid enough in the live runtime

The SDK has retrieval methods, but the current implementation is still heuristic/token/subject/predicate oriented compared with Cognis-style RRF, Graphiti-style graph traversal, or EMem-style EDU plus LLM filtering.

Impact: open-ended questions fall back to stale summaries or narrow direct facts instead of ranked evidence.

### 4. Temporal validity is not first-class in answers

Spark has supersession and cleanup, but the answer layer needs explicit "valid now," "was true before," "invalidated by," and "unknown" reasoning.

Impact: old workflow state can leak into answers unless current-state priority rules catch it.

### 5. Domain chip activation is not enough

Having `domain-chip-memory` attached as the active chip does not mean the runtime is using the best memory engine for every memory query. The chip can influence prompts and provide tools, but Builder still decides hot-path routing.

Impact: users see "memory chip active" and expect SOTA memory, while the runtime is often using direct helper routes.

### 6. LoCoMo-style social memory is still weak

Builder's own LoCoMo follow-up docs say the unseen lane remains weak and needs a general unseen retrieval schema. This is the right diagnosis.

Impact: Spark may remember the active focus but miss "who helped with what," "what changed between people," "what happened across sessions," and "why are we doing this now."

### 7. Context capsule needs a stronger compiler

The capsule now has authority classes, which is good. But it should be generated from a ranked, typed memory query result: current_state, recent_dynamic, evidence_units, events, diagnostics, connector context, and open workflow state.

Impact: capsule answers can be clean but still too deterministic or too brittle.

## Target Architecture

Spark should evolve toward a memory kernel with these layers:

1. Capture gate
   - Classifies each turn as discard, raw episode, evidence unit, current state, event, belief candidate, agent-action fact, or diagnostic/system fact.

2. Evidence unit store
   - Stores atomic user/project/social facts with subject, predicate, value, entities, time, source turn, confidence, retention class, and invalidation metadata.

3. Current-state projection
   - Builds the latest profile/focus/plan/preferences/project state from evidence units and explicit state writes.

4. Event timeline
   - Stores actions, commitments, diagnostics, maintenance runs, connector changes, mission events, and user-facing outcomes.

5. Hybrid retriever
   - Combines exact predicate lookup, BM25/FTS, semantic/vector, entity linking, temporal scoring, recency, and graph/relationship expansion.

6. Evidence filter/reranker
   - Uses deterministic filters first, then optional LLM filtering for ambiguous open-ended questions.

7. Capsule compiler
   - Produces compact context grouped by authority:
     - current_state: authoritative
     - active_user_focus: authoritative until user closes/replaces
     - diagnostics/maintenance: authoritative for system health
     - recent_conversation: supporting
     - workflow_state: advisory
     - archive/history: historical, not current unless asked

8. Answer contract
   - Every memory-backed answer can say what it used, what it ignored, and whether it abstained.

## Recommended Build Sequence

### Phase 1: Runtime adapter, not new theory

Make Builder call a single memory-kernel adapter for open-ended memory questions:

- `read_current_state(subject, predicate)`
- `search_memory(query, scope, top_k)`
- `search_events(query, time_window, top_k)`
- `explain_memory_answer(question, answer, evidence_ids)`

Keep current deterministic routes, but make them call the adapter and emit the same evidence format.

### Phase 2: Hybrid local retrieval

Inside `domain-chip-memory`, add a local hybrid scorer before adding infrastructure:

- SQLite FTS/BM25 over evidence text.
- Token/entity exact match.
- Recency and temporal boosts.
- Predicate/current-state boost.
- RRF fusion.
- Provenance-preserving result records.

Vector search can come after this if the schema is right.

### Phase 3: Evidence units from natural conversation

Add an LLM-assisted extractor behind strict gates:

- Input: recent user/assistant turns.
- Output: candidate evidence units with operation ADD/UPDATE/DELETE/NONE.
- Required fields: subject, predicate, value, entities, time, source turn, confidence, retention class.
- Guardrails: no automatic promotion for hypothetical, emotional support-only, unclear, or low-confidence facts.

### Phase 4: Temporal invalidation

Add validity fields and answer rules:

- `valid_from`
- `valid_to`
- `invalidated_by`
- `is_current`
- `source_event_id`
- `confidence`

Old facts remain searchable as historical evidence, but cannot answer "what is current" unless the user asks historically.

### Phase 5: Social/event memory

Port the best typed temporal graph ideas into the runtime:

- entities
- relationships
- commitments
- negations
- reported speech
- shared-time events
- support/help events
- project collaboration events

Then re-run LoCoMo unseen slices and Telegram natural tests.

### Phase 6: Context capsule v2

Compile every Telegram model call from:

- active current state
- focus/plan if open
- recent dynamic facts
- top ranked evidence units
- relevant event timeline entries
- diagnostics/maintenance summary when asked
- explicit source authority labels

The capsule should be short by default and expandable on demand.

## Tests That Should Gate Promotion

1. Natural recall after unrelated turns.
2. Stale context replacement.
3. Current-state beats workflow-state conflict.
4. Historical question asks for old value and gets old value with date/provenance.
5. Open-ended "what should we do next?" uses active focus and recent context, not old diagnostics residue.
6. Social memory: who helped, who owns, who is blocked, who promised what.
7. Temporal event memory: what changed, when, and why.
8. Diagnostic/system memory remains separate from user intent memory.
9. LoCoMo unseen slice improves without regressing LongMemEval.
10. Answer explanation names source classes and abstains when evidence is insufficient.

## Next Commit-Worthy Slice

Build `MemoryKernelAdapter` in Builder and back it with the existing `domain-chip-memory` SDK. Do not replace the current focus/plan helpers yet. Instead, make direct helpers and open-ended memory routes converge on the same result schema:

- `answer`
- `source_class`
- `records`
- `provenance`
- `read_method`
- `abstained`
- `ignored_stale_records`

That gives us one place to add hybrid retrieval, temporal invalidation, and graph expansion without repeatedly patching Telegram-specific routes.

