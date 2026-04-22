# Typed Temporal Graph Memory 2026-04-22

## Purpose

This adds the first graph-oriented sidecar on top of the existing conversational index.

It is additive only:

- runtime is unchanged
- `summary_synthesis_memory` remains the backbone
- this layer exists to preserve typed social and temporal facts with exact provenance spans

## Why

Current summary memory is strong when broad synthesis is enough.

It is weak when the task needs:

- exact person-to-person relationship facts
- preserved temporal expressions
- exact source spans from conversational turns
- slot-filling from raw chat instead of compacted summaries

The conversational index already emits typed atoms:

- `relationship_edge`
- `loss_event`
- `gift_event`
- `support_event`

This layer promotes those atoms into a graph-shaped memory surface with:

- entities
- relationship facts
- temporal events
- normalized time anchors
- provenance spans

## Data Model

Main types in [typed_temporal_graph_memory.py](/C:/Users/USER/Desktop/domain-chip-memory/src/domain_chip_memory/typed_temporal_graph_memory.py):

- `PersonEntity`
- `RelationshipFact`
- `TemporalMemoryEvent`
- `TimeAnchor`
- `ProvenanceSpan`
- `TypedTemporalGraphMemory`

Key properties:

- every fact/event keeps a provenance span
- temporal events preserve normalized time when available
- the graph is built per sample, which keeps it cheap and eval-friendly

## Current Scope

Implemented:

- speaker entities
- relationship facts from `relationship_edge`
- temporal events from `loss_event`, `gift_event`, `support_event`
- helper filters for subject/event-family queries
- normalization guard against obvious noisy object labels such as sentence-start verb bleed

Not implemented yet:

- alias binding
- commitment records
- negation records
- reported speech
- bi-temporal validity windows
- graph retrieval integration

## Validation

Covered by [test_typed_temporal_graph_memory.py](/C:/Users/USER/Desktop/domain-chip-memory/tests/test_typed_temporal_graph_memory.py):

- `conv-48` preserves mother-loss provenance and normalized time
- `conv-48` preserves pendant gift provenance and year anchor
- `conv-48` exposes support events and relationship filtering
- `conv-49` avoids carrying a bogus `Got` entity into the graph sidecar

## Next Step

Use this sidecar as the substrate for:

1. exact-span lane promotion
2. temporal/relationship retrieval over graph facts
3. later alias/commitment/privacy layers

Do not route runtime through it yet.
