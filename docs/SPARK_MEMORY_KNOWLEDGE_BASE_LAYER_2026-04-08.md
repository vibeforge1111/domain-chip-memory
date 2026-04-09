# Spark Memory Knowledge Base Layer

Date: 2026-04-08
Status: active product doctrine

## Why this document exists

The memory system we are building for Spark should not end at hidden runtime memory writes and reads.

If a user has Spark memory, they should also have a visible LLM-maintained knowledge base layered on top of that memory.

This gives the system two different but connected jobs:

- the runtime memory substrate answers, updates, deletes, restores, and reconstructs memory correctly
- the knowledge-base layer makes that memory legible, inspectable, compounding, and useful beyond one chat turn

This is not a side feature.
It is the intended product shape.

## Product doctrine

Every Spark user with memory should have two connected layers:

1. Runtime memory layer
   - typed writes
   - typed reads
   - current-state reconstruction
   - historical reconstruction
   - provenance
   - abstention
   - maintenance and reconsolidation

2. Knowledge-base layer
   - user-visible wiki or workspace
   - LLM-maintained summaries and syntheses
   - entity, concept, project, and timeline pages
   - filed outputs from important questions
   - health checks for contradictions, gaps, staleness, and missing links

The knowledge-base layer should be downstream of the memory system, not a separate ungoverned notes product.

## Core principle

The user should be able to see what the system knows, why it believes it, what changed, and where it came from.

That means the product should not act like:

- opaque chat memory
- hidden profile fields only
- black-box retrieval with no visible accumulation

It should act like:

- governed runtime memory underneath
- visible personal knowledge system above it

## What the knowledge-base layer is for

The KB layer should help the user:

- inspect important memories and state clearly
- browse timelines, people, projects, preferences, and decisions
- see synthesized summaries instead of only raw fragments
- file important outputs back into persistent knowledge
- notice contradictions or stale beliefs
- build compounding context over weeks and months

This is the "external brain" surface on top of the underlying memory engine.

## What it is not for

The KB layer should not:

- replace the runtime memory substrate
- silently invent unsupported facts
- overwrite raw source truth
- hide provenance
- become a second disconnected storage system with its own truth

The runtime substrate remains the authority for memory operations.
The KB layer is the compiled, visible, user-facing layer.

## Required architecture

For each user, Spark should eventually maintain:

### 1. Source truth

- raw user turns and accepted memory writes
- explicit events
- explicit state updates
- tombstones, restores, and supersessions
- provenance-bearing evidence units

### 2. Runtime memory views

- current state
- historical state
- evidence retrieval
- event retrieval
- answer explanation

### 3. Compiled knowledge-base views

- profile pages
- project pages
- timeline pages
- concept or theme pages
- decision summaries
- relationship maps
- query outputs
- maintenance or health reports

The KB pages should be compilations from the runtime memory and approved artifacts, not independent truth sources.

Current implemented surfaces in this repo now include:

- governed runtime snapshot export into `raw/memory-snapshots/`
- explicit repo-native file ingest into `raw/repos/`
- compiled source pages for snapshot and session inputs under `wiki/sources/`
- compiled runtime timeline synthesis under `wiki/syntheses/`
- filed maintenance and answer pages under `wiki/outputs/`

## Required user-visible surfaces

If Spark memory is enabled, the user should eventually have a visible workspace with at least:

1. A memory home page
   - recent updates
   - important entities
   - active projects
   - current beliefs or summaries

2. A timeline view
   - what changed
   - when it changed
   - what was superseded or deleted

3. A provenance view
   - where a memory came from
   - what evidence supports it
   - whether it is current-state, event, or derived belief

4. A compiled wiki view
   - structured pages maintained by the LLM
   - linked concepts, people, projects, decisions, and outputs

5. A health-check view
   - contradictions
   - stale pages
   - unsupported gaps
   - missing pages or broken links

## Data flow

The intended flow is:

1. Spark decides what is durable enough to write
2. the runtime memory system stores governed memory units
3. maintenance builds or refreshes compiled KB pages
4. user questions can produce new outputs
5. valuable outputs are filed back into the KB
6. the KB compounds over time while staying traceable to runtime memory and source evidence

This keeps the system additive rather than amnesic.

The current repo implementation now exercises this with:

- a demo filed answer page derived from `SparkMemorySDK.explain_answer(...)`
- a maintenance report page emitted into `wiki/outputs/`
- explicit repo-source copies and compiled source pages for selected local files
- manifest-driven repo-source ingest for real `build-spark-kb` compilation flows

## Guardrails

The KB layer must preserve:

- provenance
- memory role labels
- current vs historical distinction
- delete and restore semantics
- abstention honesty
- rebuildability from underlying memory and artifacts

The KB layer must not:

- flatten evidence and belief into one undifferentiated note
- show deleted facts as active current truth
- hide contradictions
- bypass memory write gates

## Spark integration implication

Spark should not expose the memory system only as an invisible SDK.

Spark should expose:

- the narrow runtime SDK for programmatic memory operations
- and a user-visible knowledge-base workspace compiled from that memory

That is the combined product we are aiming for.

## Build implication for this repo

This repo now needs to support both:

1. the benchmarked runtime memory substrate
2. the repo-native knowledge-base compilation pattern that will later become the Spark-visible workspace

The KB work in this repo should therefore be treated as product architecture research, not mere documentation hygiene.
