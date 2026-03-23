# First Version Research Lock

Date: 2026-03-22
Status: active

## Purpose

This document freezes the research-backed doctrine for the first real memory system build.

It exists to stop two failure modes:

1. continuing to research forever without making a build choice
2. jumping into a heavyweight architecture because it sounds frontier-like

The first version should be the smallest system that has a credible path to benchmark leadership.

## Research verdict

The current source sweep supports one dominant conclusion:

- the first version should be a lightweight temporal-semantic memory system with provenance, not a giant graph stack and not an online multi-agent search forest

That conclusion is supported by:

- `LongMemEval` pressure on knowledge updates and temporal reasoning
- `LoCoMo` pressure on long-range evidence recovery and multi-hop recall
- `GoodAI LTM Benchmark` pressure on long-span memory upkeep and integration over very long conversations
- `ConvoMem` pressure against overengineering when full context still works, now treated as a shadow guardrail
- `Supermemory` emphasis on versioned memory and temporal search
- `SimpleMem` and `LightMem` pressure toward small online paths and offline consolidation
- `Mem0`, `Letta`, `Graphiti`, `A-Mem`, `O-Mem`, `MemOS`, and `MemoryOS` as sources of useful patterns, but not proof that the broadest architecture wins the first build

## Hard thesis for V1

The first system should have five mandatory properties.

1. Raw source provenance
   Every memory item must point back to the originating session and turn.

2. Distilled semantic memory atoms
   The primary retrieval unit should be compact facts, preferences, events, and relations rather than only raw chunks.

3. Explicit time and supersession
   The system must know that a newer fact can replace an older one and that event time is not always the same as mention time.

4. Query-aware routing
   The system should not treat every question as the same retrieval problem.

5. Lightweight online path
   Most of the work should happen in extraction, indexing, and offline consolidation, not in large online ensembles.

## V1 architecture choice

The first system should be:

1. raw episode store
2. semantic atom extractor
3. temporal and supersession resolver
4. compact profile memory builder
5. deterministic retrieval router
6. evidence rehydration step
7. single answer policy with abstention support
8. offline consolidation worker

This means:

- relational or document-plus-relational storage is preferred
- graph database infrastructure is optional later, not required now
- one answering pass is preferred before answer forests
- one retrieval router is preferred before specialized search-agent orchestration

## What V1 should not be

Do not build these first:

- vector-only conversational memory
- summary-only memory
- giant online graph traversal stack
- three-search-agent retrieval orchestration
- eight-prompt or twelve-prompt answer ensemble
- RL-trained memory policy before a strong heuristic baseline exists
- product-general memory OS abstractions as the starting surface

These may become later mutations, but they should not define V1.

## Benchmark-specific interpretation

### LongMemEval

V1 must prioritize:

- update resolution
- temporal filtering
- low-noise evidence sets
- source rehydration after compact retrieval

### LoCoMo

V1 must prioritize:

- episodic fidelity
- relation support
- longer-range evidence recovery

Implication:

- do not overcompress away conversation structure

### GoodAI LTM Benchmark

V1 must prioritize:

- long-span memory upkeep
- integration over long periods
- robustness across published context-span configurations

Implication:

- the system should not only answer narrow benchmark questions; it should stay coherent under longer memory-span stress

### ConvoMem Shadow

V1 must prioritize:

- preference handling
- changing-fact handling
- abstention
- route-to-full-context when retrieval is not yet justified

Implication:

- retrieval should be selectively invoked, not forced on every query

## Retrieval doctrine

The retrieval system should route by question family.

Recommended initial routes:

- direct fact query -> semantic atom retrieval
- changed fact query -> temporal filter plus supersession-aware atom retrieval
- profile or preference query -> profile block plus supporting atoms
- multi-hop or relation query -> atom expansion by relation edges plus source rehydration
- short-history query -> direct full-context baseline path
- no-evidence or weak-evidence case -> abstain or low-confidence answer policy

Retrieval ranking should prefer:

- latest valid information
- high provenance confidence
- exact entity match
- evidence diversity without duplication

## Write-path doctrine

Extraction should separate memory writes into at least four classes:

- stable profile facts
- mutable preferences
- events and state transitions
- relationship or linkage records

Every write should track:

- source session
- source turn
- extraction timestamp
- event timestamp if present
- confidence
- superseded-by or conflicts-with links when applicable

## Compression doctrine

Compression is allowed, but only under these rules:

1. raw episodes remain the source of truth
2. compressed memory atoms remain reversible to source evidence
3. summaries are auxiliary, not canonical
4. profile memory stays distinct from event memory

## Offline doctrine

Move these tasks out of the hot path first:

- deduplication
- profile refresh
- multi-atom consolidation
- reflective lesson extraction
- optional memory graph materialization

This is where heavyweight intelligence belongs if V1 is to stay fast.

## Decision on open-source inspiration

High-value inspiration:

- `Supermemory` for versioning and time fields
- `MemoryBench` for benchmark harness patterns
- `Mem0` for practical memory extraction surfaces
- `Graphiti` for temporal relation thinking
- `A-Mem` for memory-note organization
- `SimpleMem` and `LightMem` for lightweight-first design
- `O-Mem` for separating profile from event memory

Lower-priority for V1 implementation:

- `MemOS`
- `MemoryOS`
- heavy online agent ensembles

Reason:

- these are valuable system-level ideas, but they are too broad for the first benchmark race

## Research questions that are still open

These are real open questions, but none should block the first build.

1. Should relation expansion stay relational, or will a graph index be needed after the first plateau?
2. How much offline consolidation helps before it begins to hide useful raw evidence?
3. What is the best abstention thresholding policy across `LongMemEval` and the `ConvoMem` shadow slices?
4. How much profile memory should be pinned in context before it becomes noise?
5. When does route-to-full-context beat memory retrieval on `ConvoMem` shadow slices?

## Research questions that should be deferred

Do not let these distract V1:

- memory as parameter editing
- activation memory systems
- cross-agent shared memory OS abstractions
- robotic on-device memory deployment
- reinforcement-learning memory control before heuristic baselines
- very large online specialist-agent councils

## Immediate build consequences

The next implementation step should be:

1. benchmark adapters
2. full-context baseline
3. naive lexical retrieval baseline
4. semantic-atom baseline without time logic
5. semantic-atom baseline with time and supersession
6. profile-memory route
7. abstention calibration

Only after those are measured should we try:

- relation expansion
- graph materialization
- offline reflective memory
- learned write policies
- agentic retrieval orchestration

Combination search should follow the separate program in `docs/COMBINATION_SEARCH_PROGRAM.md`.

## Promotion rule

Any heavier architecture must beat the lightweight temporal-semantic baseline on the target benchmark slices, not just match it with more latency and more complexity.

## Sources

- `LongMemEval`: `https://arxiv.org/abs/2410.10813`, `https://github.com/xiaowu0162/LongMemEval`
- `LoCoMo`: `https://github.com/snap-research/locomo`
- `GoodAI LTM Benchmark`: `https://github.com/GoodAI/goodai-ltm-benchmark`
- `ConvoMem`: `https://arxiv.org/abs/2511.10523`, `https://huggingface.co/datasets/Salesforce/ConvoMem`
- `Supermemory`: `https://supermemory.ai/research/`, `https://github.com/supermemoryai/supermemory`
- `MemoryBench`: `https://github.com/supermemoryai/memorybench`
- `Mem0`: `https://arxiv.org/abs/2504.19413`, `https://github.com/mem0ai/mem0`
- `MemGPT`: `https://arxiv.org/abs/2310.08560`
- `Letta`: `https://docs.letta.com/`, `https://github.com/letta-ai/letta`
- `Graphiti`: `https://github.com/getzep/graphiti`
- `MemoryOS`: `https://arxiv.org/abs/2506.06326`
- `MemOS`: `https://arxiv.org/abs/2507.03724`, `https://github.com/MemTensor/MemOS`
- `A-Mem`: `https://arxiv.org/abs/2502.12110`
- `O-Mem`: `https://arxiv.org/abs/2511.13593`
- `SimpleMem`: `https://arxiv.org/abs/2601.02553`
- `LightMem`: `https://arxiv.org/abs/2510.18866`
- `MemBench`: `https://arxiv.org/abs/2506.21605`
- `RF-Mem`: `https://arxiv.org/abs/2603.09250`
- `D-MEM`: `https://arxiv.org/abs/2603.14597`
