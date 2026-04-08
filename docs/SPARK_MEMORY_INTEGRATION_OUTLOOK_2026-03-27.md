# Spark Memory Integration Outlook

Date: 2026-03-27
Status: active integration doctrine

## Why this document exists

Spark Intelligence Builder now has enough runtime surface around the memory SDK that the next failure mode is no longer missing code. The next failure mode is bad orchestration.

This document defines what Spark must understand before it tries to connect the SDK into live Builder flows.

## Short answer

Yes. Spark should have an explicit integration prompt and contract.

Not because the SDK needs a language-model pep talk, but because Spark needs a stable doctrine for:

- what is safe to write
- what read path to use
- when to abstain
- what provenance must be preserved
- what shadow and maintenance systems must exist around the SDK

Without that layer, Spark will tend to over-persist, over-query, and over-trust memory.

## The role split

Spark should own:

- conversation flow
- user intent interpretation
- policy and permission decisions
- final response assembly
- product-specific orchestration

The memory SDK should own:

- typed memory writes
- typed memory reads
- provenance-bearing retrieval
- abstention on unsupported or missing memory
- shadow replay compatibility
- maintenance and reconsolidation hooks

The Spark product should additionally expose a visible knowledge-base layer above the SDK:

- user-visible compiled memory pages
- timeline and provenance views
- LLM-maintained summaries and syntheses
- health checks over contradictions, staleness, and gaps

This is the correct split. The SDK is not the planner. Spark is not the memory engine.

## Required surrounding systems inside Spark

Spark should not connect directly to the SDK unless it has these surrounding systems:

1. Entity and field normalizer
   Spark must map user language into stable subjects and predicates before structured writes become reliable.

2. Memory write gate
   Spark must decide what is durable enough to persist. Raw residue like greetings, filler, or assistant chatter should not be written.

3. Memory query router
   Spark must choose the narrowest valid SDK read method:
   - `get_current_state(...)`
   - `get_historical_state(...)`
   - `retrieve_evidence(...)`
   - `retrieve_events(...)`
   - `explain_answer(...)`

4. Provenance and abstention surface
   Spark must preserve `memory_role`, provenance, and abstentions instead of flattening everything into a single opaque memory answer.

5. Shadow replay runner
   Spark must be able to mirror real Builder traffic through:
   - `run-spark-shadow-report`
   - `run-spark-shadow-report-batch`

6. Shadow report store
   Spark must persist accepted/rejected/skipped write rates, unsupported-write reasons, probe hit rates, and role mix over time.

7. Maintenance scheduler
   Spark must be able to run reconsolidation and inspect before/after results instead of letting manual writes grow forever.

8. Artifact and trace store
   Spark must store replayable request and response traces so failures can be reproduced deterministically.

9. Knowledge-base compiler and workspace
   Spark must compile governed memory into a visible user workspace instead of leaving memory as an invisible backend only.
   This workspace should expose profile, project, timeline, provenance, and synthesized wiki views that are downstream of the memory substrate.

## Integration vectors

### 1. Write vector

Spark receives a Builder turn, normalizes it, decides whether it is memory-worthy, then calls:

- `write_observation(...)`
- `write_event(...)`

Rules:

- never write every turn by default
- write only durable user facts or event facts
- prefer explicit structured writes when `subject`, `predicate`, and `value` are known
- preserve `session_id`, `turn_id`, and `timestamp`
- reject unsupported writes rather than silently forcing them through

### 2. Read vector

Spark should pick the smallest sufficient memory method:

- current profile fact: `get_current_state(...)`
- past state by time: `get_historical_state(...)`
- evidence lookup: `retrieve_evidence(...)`
- event lookup: `retrieve_events(...)`
- debugging or explanation: `explain_answer(...)`

Rules:

- do not query broad evidence if a typed current-state read is enough
- do not turn abstention into hallucinated recall
- keep the returned provenance visible to downstream Spark systems

### 3. Shadow vector

Before any live promotion, Spark should replay real traffic through the shadow adapter and track:

- accepted writes
- rejected writes
- skipped turns
- unsupported-write reasons
- probe hit rates
- memory-role mix

### 4. Maintenance vector

Spark should periodically run maintenance for explicit SDK writes and inspect:

- `manual_observations_before`
- `manual_observations_after`
- `active_deletion_count`
- before/after current-state readback
- historical-state readback

## System prompt template for Spark

Use this as the orchestration prompt for the Builder layer that decides how to use memory:

```text
You are the Spark memory orchestrator.

Use SparkMemorySDK only as a typed memory subsystem.
Do not persist every turn by default.
Write only durable user facts or event records that pass the memory write gate.
Prefer explicit structured writes when subject, predicate, and value are known.

For read requests, choose the narrowest valid method among current state, historical state, evidence, event retrieval, or answer explanation.
If the SDK abstains or returns no supported memory, preserve that uncertainty and do not invent a memory-backed answer.

Always carry session, turn, timestamp, memory role, and provenance forward to downstream Spark systems.
Run shadow evaluation and maintenance reporting before promoting new memory behavior to live traffic.
```

## What “seamless” actually means

Seamless does not mean Spark dumps all conversations into memory and gets a magical answer back.

Seamless means:

- Spark knows what to write and what to reject
- Spark knows which memory read path it is asking for
- the SDK can abstain without being overridden
- provenance survives the trip
- the user can inspect the resulting memory as a visible knowledge base
- shadow and maintenance systems exist around the runtime

That is the difference between a demo integration and a production integration.

## Immediate recommendation

Before deeper live integration, Spark should adopt this outlook as a contract and verify these questions:

1. Can Builder normalize subjects and predicates well enough for structured writes?
2. Can Builder reject conversational residue before persistence?
3. Can Builder preserve abstention and provenance instead of flattening them away?
4. Can Builder run replayable shadow traffic and compare reports over time?
5. Can Builder schedule maintenance and inspect compaction outcomes?

If any of those answers is no, Spark should stay in shadow mode until the missing surrounding system exists.
