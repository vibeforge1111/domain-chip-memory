## Conversational Memory Layer Plan

Date: 2026-04-22
Status: active implementation plan
Scope:
- `domain-chip-memory`
- layered on top of existing `summary_synthesis_memory`

## Why This Exists

The current architecture is now strong on:

- BEAM
- LongMemEval
- internal Builder regression and soak gates

But LoCoMo and Telegram-style conversational memory expose a different failure class:

- multi-speaker social memory
- exact list and count questions
- kinship and relationship resolution
- relative and older temporal anchoring
- noisy chat turns where semantic similarity alone is not enough

The substrate currently does too much of this work at answer time from raw or weakly typed observations.
That produces plausible nearby chatter instead of grounded conversational recall.

This plan does not replace the current architecture.
It adds a conversational precision layer on top of the working backbone.

## External Design Signals

These open-source systems converge on the same pattern:

1. Keep raw provenance.
2. Extract typed memories at ingest.
3. Preserve entity and temporal structure.
4. Retrieve with multiple signals, not embeddings alone.

Primary sources:

- Mem0 repo: https://github.com/mem0ai/mem0
- Mem0 graph memory docs: https://docs.mem0.ai/open-source/features/graph-memory
- Graphiti repo: https://github.com/getzep/graphiti
- Graphiti episodes docs: https://help.getzep.com/graphiti/core-concepts/adding-episodes
- LangMem repo: https://github.com/langchain-ai/langmem
- LangMem semantic extraction guide: https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/
- Letta repo: https://github.com/letta-ai/letta
- Letta memory blocks docs: https://docs.letta.com/guides/core-concepts/memory/memory-blocks

Key takeaways:

- Mem0 emphasizes add-only extraction, entity linking, and fused retrieval signals.
- Graphiti models episodes, entities, and temporal facts with validity windows and provenance.
- LangMem uses explicit schemas so extraction yields structured memories instead of ambiguous text blobs.
- Letta is strongest for always-visible core memory blocks, which is useful for stable profile memory but is not the primary fix for conversational evidence retrieval.

## Design Goal

Add an ingest-time conversational memory layer that promotes raw dialogue into typed conversational atoms with provenance and temporal metadata, then route relevant questions through typed retrieval before summary synthesis.

## Architectural Position

Keep:

- raw episode capture
- observation log
- event calendar
- summary synthesis runtime
- current benchmarked architecture pin

Add:

- typed conversational atoms
- normalized temporal metadata
- relationship-aware retrieval
- timeline-aware retrieval
- question-type routing that prefers typed evidence for social and temporal questions

This is an additive layer.
The current summary path remains the fallback.

## New Typed Conversational Atoms

The first layer should introduce typed atoms that can ride through the existing observation pipeline without requiring a full store rewrite.

Candidate predicates:

- `relationship_edge`
- `family_edge`
- `loss_event`
- `gift_event`
- `visit_event`
- `support_event`
- `shared_activity`
- `personal_preference_typed`
- `conversation_anchor`

Required metadata on typed conversational atoms:

- `entity_type`
- `other_entity`
- `other_entity_aliases`
- `relation_type`
- `event_type`
- `object_type`
- `place`
- `time_expression_raw`
- `time_anchor`
- `time_kind`
- `time_normalized`
- `time_interval_start`
- `time_interval_end`
- `source_span`
- `confidence`

Important constraint:

If normalization is uncertain, preserve the original phrase and store an interval or coarse description instead of hallucinating an exact timestamp.

Examples:

- `a few years ago` relative to `23 January 2023`
  - `time_expression_raw=a few years ago`
  - `time_anchor=2023-01-23`
  - `time_normalized=a few years before 2023`
- `last year`
  - `time_expression_raw=last year`
  - `time_anchor=2023-01-23`
  - `time_normalized=in 2022`

## Retrieval Model

The retrieval model should become question-type aware before synthesis.

### 1. Temporal fact questions

Examples:

- `When did Deborah's mother pass away?`
- `When did Jolene's mom gift her a pendant?`

Preferred retrieval:

- `loss_event` / `gift_event` atoms
- exact source spans containing temporal cues
- timeline-aware ranking over generic semantic ranking

### 2. Relation and kinship questions

Examples:

- `Which of Deborah's family and friends have passed away?`
- `What did both speakers have in common?`

Preferred retrieval:

- `relationship_edge`, `family_edge`, `support_event`, `shared_activity`
- entity alias and kinship expansion
- typed aggregation over matching atoms

### 3. List and count questions

Examples:

- hobbies
- gifts
- places visited
- number of visits

Preferred retrieval:

- typed aggregation over `gift_event`, `visit_event`, `shared_activity`, `personal_preference_typed`
- dedupe by typed object and provenance

### 4. Open synthesis questions

Keep the current summary-synthesis path, but feed it better candidate evidence when typed retrieval has a confident answer lane.

## Phased Implementation

### Phase 1: Typed atoms on top of the existing observation store

Files:

- `src/domain_chip_memory/memory_atom_extraction.py`
- `src/domain_chip_memory/memory_extraction.py`
- `src/domain_chip_memory/memory_queries.py`
- `src/domain_chip_memory/memory_selection.py`
- `src/domain_chip_memory/memory_evidence.py`
- `src/domain_chip_memory/memory_temporal_answers.py`
- `tests/test_memory_systems.py`

What changes:

- extend extraction to emit typed conversational atoms
- preserve typed metadata in `ObservationEntry.metadata`
- add query classification helpers for temporal, relation, and typed list/count questions
- add selection helpers that prefer typed atoms and source spans over generic summary entries
- use typed temporal metadata before fallback heuristics

Why this phase first:

- no new persistence contract required
- low regression risk to existing benchmarked lanes
- immediate impact on LoCoMo and Telegram-like chat memory

### Phase 2: Lightweight conversational indexes

Files to add:

- `src/domain_chip_memory/memory_conversational_index.py`
- `src/domain_chip_memory/memory_timeline_index.py`

What changes:

- materialize typed observation subsets into:
  - entity-to-atom adjacency
  - relation adjacency
  - time-sorted event views
- expose helper functions for graph-like and timeline-like retrieval without replacing the current architecture

### Phase 3: Validity windows and contradiction-aware typed state

Goal:

- allow typed conversational facts to expire or be superseded without deleting provenance
- move toward Graphiti-style validity windows where it helps mutable social facts and stateful relations

## Codebase Mapping

### `memory_atom_extraction.py`

Current role:

- manual and fallback atom extraction from turns

Required upgrade:

- emit typed conversational predicates and metadata from raw turns
- capture source span fragments, not only whole-turn text
- emit coarse temporal normalization at extraction time

### `memory_extraction.py`

Current role:

- transforms `MemoryAtom` into `ObservationEntry` and event entries

Required upgrade:

- preserve typed metadata untouched
- optionally elevate `source_span` for evidence display and downstream ranking

### `memory_queries.py`

Current role:

- string-pattern question understanding

Required upgrade:

- add question families:
  - `temporal_social_fact`
  - `relation_graph`
  - `typed_list_or_count`
  - `open_synthesis`

### `memory_selection.py`

Current role:

- ranked evidence selection from observations

Required upgrade:

- add typed-first candidate selection before generic ranking
- prefer entries whose metadata aligns on:
  - `relation_type`
  - `other_entity`
  - `event_type`
  - `time_kind`
  - `source_span`

### `memory_evidence.py`

Current role:

- evidence surface shaping and ranking bonuses

Required upgrade:

- use `source_span` and typed temporal cues directly
- reduce whole-turn contamination from greetings and unrelated clauses

### `memory_temporal_answers.py`

Current role:

- answer-time temporal inference

Required upgrade:

- trust typed temporal metadata first
- fall back to raw-pattern temporal inference only when typed metadata is absent

## Anti-Overfit Rules

To avoid turning this into another benchmark-specific patch stack:

1. No question-id checks in runtime code.
2. New logic must trigger off typed predicates, relation metadata, or question family classification.
3. New tests should include:
   - current targeted LoCoMo slices
   - at least one unseen-conversation slice
   - no regressions on the current internal health gates
4. Do not hardcode unsupported gold text when the source evidence does not contain it.
5. Preserve abstention when typed evidence is weak or conflicting.

## Success Criteria

The first phase is successful if it does all of the following:

- improves unseen LoCoMo social and temporal slices beyond the current hand-patched baseline
- reduces answer-time dependence on ad hoc surface heuristics
- preserves current BEAM / LongMemEval / internal regression behavior
- gives us a usable substrate for Telegram-style conversational memory

## Immediate Build Order

1. Add typed conversational predicates and metadata to `memory_atom_extraction.py`.
2. Add question-family classification in `memory_queries.py`.
3. Add typed-first evidence selection in `memory_selection.py`.
4. Teach temporal answers to read typed temporal metadata before fallback heuristics.
5. Add real regression tests from unseen LoCoMo slices.

## Explicit Non-Goals For This Pass

- replacing `summary_synthesis_memory`
- rewriting the observation store
- introducing a heavyweight external graph database
- solving every LoCoMo category in one commit

The target is a durable conversational precision layer that improves both benchmark generalization and real chat memory quality.
