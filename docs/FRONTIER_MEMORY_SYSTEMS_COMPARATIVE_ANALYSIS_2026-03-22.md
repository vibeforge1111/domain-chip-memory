# Frontier Memory Systems Comparative Analysis

Date: 2026-03-22
Status: research-grounded

## Purpose

This document answers four practical questions:

1. which memory systems currently matter most
2. what they appear to be doing right
3. what their likely weaknesses are
4. what we should borrow, reject, or postpone

This is not a vendor leaderboard page.
It is a build-oriented comparative memo.

## Evaluation lens

Each system is judged on:

- benchmark relevance
- retrieval quality strategy
- temporal and update handling
- profile or personalization handling
- online weight
- reuse value for our build

## Systems that matter most right now

### 0. Chronos

Sources:

- arXiv paper

What they appear to do right:

- decompose dialogue into structured subject-verb-object event tuples
- resolve datetime ranges and entity aliases
- maintain an event calendar plus a turn calendar
- use query-time retrieval guidance for temporal filtering and multi-hop reasoning

Why it matters:

- one of the clearest recent temporal-first designs
- paper claims `92.60%` and `95.60%` on `LongMemEvalS`, which is materially above earlier public bars

Likely weaknesses:

- current source is the paper, not yet a pinned public implementation surface
- dynamic prompting and iterative tool-calling may be heavier than our first benchmark baseline should be

What we should borrow:

- event calendar idea
- time-range resolution
- alias handling
- explicit temporal retrieval guidance

What we should postpone:

- heavier iterative query-time orchestration until lighter stacks plateau

### 1. Supermemory

Sources:

- official research page
- public repo
- MemoryBench docs

What they appear to do right:

- treat retrieval as the real bottleneck
- generate compact memory units instead of relying only on raw chunks
- model updates and relations such as `updates`, `extends`, and `derives`
- separate document time from event time
- retrieve compact memory first, then rehydrate source evidence

Why it matters:

- one of the strongest benchmark-native systems on `LongMemEval`
- the clearest current proof that time-aware memory beats naive semantic search

Likely weaknesses:

- some stronger claims are still ahead of fully pinned public reproduction
- the more agentic retrieval variants may be heavier than necessary for our first build

What we should borrow:

- atom-first retrieval
- temporal fields
- supersession logic
- evidence rehydration

What we should not copy blindly:

- multi-agent online orchestration before the lightweight core is exhausted

### 1A. Supermemory ASMR

Sources:

- user-provided writeup of the forthcoming ASMR release
- official research root for tracking the release surface

What they appear to do right:

- parallel observer-style ingestion
- specialized search roles instead of generic retrieval
- source verification before final answer generation
- explicit acknowledgment that retrieval quality is the dominant bottleneck

Why it matters:

- the writeup claims `98.60%` with an 8-variant ensemble and `97.20%` with a 12-variant decision forest on `LongMemEval_s`
- even before public release, it strongly reinforces the benchmark lesson that time-sensitive retrieval quality matters more than naive vector similarity

Likely weaknesses:

- not public yet
- answer ensembles and multi-agent online orchestration may be too heavy for our default path
- benchmark wins from high fanout do not automatically imply product viability

What we should borrow:

- specialized retrieval roles
- targeted ingestion across memory facets
- evidence rehydration and verification

What we should postpone:

- online answer forests
- treating the claim as a pinned reproducible public bar before the release lands

### 1B. Mastra Observational Memory

Sources:

- Mastra research page
- Mastra repo

What they appear to do right:

- maintain a stable, cacheable context window instead of injecting dynamic retrieval every turn
- use background Observer and Reflector agents to convert message history into dense observations
- keep a strong focus on benchmark-driven iteration and reproducibility claims

Why it matters:

- official research page claims `84.23%` on `LongMemEval` with `gpt-4o`
- same page claims `94.87%` with `gpt-5-mini`, which is the highest published LongMemEval result in our current sweep

Likely weaknesses:

- the framework repo is open, but the exact benchmark reproduction path still needs care because Mastra itself is dual-licensed and not every path in the repo is plain Apache
- observational compression may trade off against raw evidence fidelity if the observation layer drifts

What we should borrow:

- stable-context-window doctrine
- background observation pipeline
- memory as dense observations rather than raw chat only

What we should study carefully before adopting:

- whether observation logs outperform explicit retrieval on our chosen benchmark stack, especially outside LongMemEval

### 2. GoodAI LTM agents and benchmark framing

Sources:

- `GoodAI/goodai-ltm-benchmark`

What they appear to do right:

- frame memory as long-span upkeep over very long conversations, not just one benchmark score
- ship a runnable harness with multiple context-span configurations
- test dynamic memory upkeep and integration over long periods

Why it matters:

- gives us a third benchmark harness that stresses memory span and continual upkeep
- useful against overfitting to one benchmark-specific QA format

Likely weaknesses:

- less of a single public headline leaderboard than `LongMemEval`
- configuration sprawl can make claims fuzzy unless we pin a canonical set

What we should borrow:

- configuration-specific score discipline
- long-span stress testing
- internal benchmark harness thinking

### 3. Mem0

Sources:

- paper
- public repo

What they appear to do right:

- production-friendly memory extraction layer
- clear value proposition around memory as a reusable service layer
- simple developer-facing integration surfaces

Why it matters:

- useful model for turning memory extraction into a stable subsystem

Likely weaknesses:

- architecture appears more product-general than benchmark-specialized
- benchmark rhetoric can be noisier than benchmark-native evaluation doctrine

What we should borrow:

- extraction and memory-write ergonomics
- service-boundary clarity

### 4. Letta / MemGPT

Sources:

- MemGPT paper
- Letta docs and repo

What they appear to do right:

- strongly separate in-context memory from archival memory
- make stateful agents tangible and usable
- support editable long-term agent state

Why it matters:

- excellent reference for memory tiers and state surfaces

Likely weaknesses:

- block editing is not itself a benchmark-winning retrieval method
- easy to misuse core blocks as a dumping ground

What we should borrow:

- memory tier separation
- stateful-agent boundaries
- pinned versus searchable memory distinction

### 5. Graphiti / Zep-style temporal graph memory

Sources:

- Graphiti repo
- Zep paper line

What they appear to do right:

- take time and evolving relationships seriously
- keep provenance and relation structure visible
- support temporal and historical queries well

Why it matters:

- one of the cleanest ways to think about relation-aware memory

Likely weaknesses:

- can become infrastructure-heavy too early
- graph-first implementations can outrun the benchmark signal

What we should borrow:

- relation semantics
- temporal historical-query logic

What we should postpone:

- graph DB dependence

### 6. A-Mem

Sources:

- paper
- repo

What they appear to do right:

- organize memory as evolving note-like units
- support dynamic links between memories

Why it matters:

- good inspiration for relation-rich memory without committing to full graph infra

Likely weaknesses:

- organizational elegance can outrun benchmark payoff

What we should borrow:

- note-like memory organization
- lightweight relation building

### 7. O-Mem

Sources:

- paper

What they appear to do right:

- separate profile memory from event memory
- use hierarchical retrieval for personalization-heavy queries

Why it matters:

- one of the best clean signals that profile memory should not be mixed carelessly with event memory

Likely weaknesses:

- profile-heavy systems can overfit personalization tasks

What we should borrow:

- profile versus event separation
- active profile refresh ideas

### 8. SimpleMem

Sources:

- paper

What they appear to do right:

- semantic structured compression
- very strong lightweight-first instincts
- compact retrieval units with better information density

Why it matters:

- one of the strongest papers aligned with our desire to stay lightweight

Likely weaknesses:

- compression can lose nuance if evidence rehydration is weak

What we should borrow:

- compact semantic units
- aggressive hot-path efficiency discipline

### 9. LightMem

Sources:

- paper
- repo

What they appear to do right:

- move heavy consolidation out of the hot path
- use a sleep-time style consolidation story
- keep online memory layers compact

Why it matters:

- strongest current support for online-light, offline-heavy architecture

Likely weaknesses:

- newer line, less battle-tested in public benchmark doctrine than simpler temporal-semantic baselines

What we should borrow:

- offline consolidation
- lightweight online path discipline

## Cross-system lessons

The strongest reusable lessons are not mysterious.

### What the best systems repeatedly do right

1. They separate raw evidence from retrieval units.
2. They model updates and time explicitly.
3. They retrieve compact memory first and raw evidence second.
4. They avoid throwing the whole history into the model every time.
5. They increasingly separate online memory from offline consolidation.

### What weaker or riskier approaches keep getting wrong

1. Vector-only chunk retrieval.
2. Summary-only memory.
3. No explicit supersession logic.
4. Mixing stable profile memory with transient event memory.
5. Adding heavy online orchestration before proving a lightweight baseline.

## What remains unsolved

Even after the research pass, five things remain genuinely open.

1. Exactly how much relation expansion is needed before graph materialization becomes worth it.
2. The best route-to-full-context trigger on short-history slices.
3. The best abstention calibration shared across `LongMemEval` and the `ConvoMem` shadow.
4. The best offline consolidation cadence for long-span memory.
5. The point where learned memory policies beat heuristic routing cleanly.

## Recommended borrowing map

Borrow first:

- `Supermemory`: time, supersession, rehydration
- `SimpleMem`: compact semantic units
- `LightMem`: offline consolidation
- `O-Mem`: profile/event separation
- `Letta`: memory tier boundaries
- `A-Mem`: lightweight relation structure

Borrow carefully:

- `Graphiti`: relation logic without graph-first overcommitment
- `Mem0`: product memory boundaries without inheriting benchmark marketing

Postpone:

- full memory operating system abstractions
- heavyweight online search-agent orchestration
- answer forests
- RL-trained write policies

## Decision

The evidence still points to the same conclusion:

- the best path to beating current systems is not to reinvent memory from zero
- it is to combine the best parts of the strongest systems into a smaller, cleaner, more benchmark-native stack

That stack should begin with:

1. raw episodes
2. semantic atoms
3. temporal and supersession logic
4. profile or event separation
5. query-aware routing
6. source rehydration
7. abstention
8. offline consolidation

## Sources

- `Supermemory`: `https://supermemory.ai/research/`, `https://github.com/supermemoryai/supermemory`
- `GoodAI LTM Benchmark`: `https://github.com/GoodAI/goodai-ltm-benchmark`
- `Mem0`: `https://arxiv.org/abs/2504.19413`, `https://github.com/mem0ai/mem0`
- `MemGPT`: `https://arxiv.org/abs/2310.08560`
- `Letta`: `https://github.com/letta-ai/letta`
- `Graphiti`: `https://github.com/getzep/graphiti`
- `A-Mem`: `https://arxiv.org/abs/2502.12110`, `https://github.com/WujiangXu/A-mem`
- `O-Mem`: `https://arxiv.org/abs/2511.13593`
- `SimpleMem`: `https://arxiv.org/abs/2601.02553`
- `LightMem`: `https://arxiv.org/abs/2510.18866`, `https://github.com/zjunlp/LightMem`
