# Memory Systems Landscape Refresh 2026-03-24

Status: research-grounded refresh

## Purpose

This document refreshes the repo's memory-systems map so future benchmark work can rely on:

- grounded benchmark facts
- a shared glossary
- a categorized map of the major memory-system families
- an honest system-by-system assessment of strengths, weaknesses, and public evidence
- a borrowing queue that distinguishes inspiration from reproduced proof

This is not a claim that the repo has reproduced every public score below.
It is a source-backed research map for deciding what to borrow, what to test, and what to postpone.

## Ground rules

Four evidence classes must stay separate:

1. public paper or product claim
2. open-source implementation surface
3. local reproduction in this repo
4. promoted doctrine for this chip

Current local status:

- current best measured lane in this repo: `observational_temporal_memory + MiniMax-M2.7`
- this is the best measured lane on the slices we have actually run
- it is not yet proof that we have the best universal memory architecture
- it is not yet proof that we have completed `LongMemEval_s`, `LoCoMo`, or `BEAM`

## Benchmark snapshot

| Benchmark | What it stresses | Public or local scale | Why it matters now |
|---|---|---|---|
| `LongMemEval_s` | knowledge updates, temporal reasoning, multi-session recall, abstention | `500` questions overall; the local file in this repo has `500` items | still the clearest benchmark for stale-fact replacement and time-aware retrieval |
| `LoCoMo` | long conversational recall, temporal consistency, multi-hop reasoning, adversarial QA | local `locomo10` file here has `10` conversations and `1,986` questions | strong pressure on long-range conversational evidence recovery |
| `BEAM` | coherent million-token and multi-million-token memory | paper benchmark: `100` conversations and `2,000` validated questions up to roughly `10M` tokens | best current stress test for whether a memory architecture survives true scale |
| `GoodAI LTM Benchmark` | long-span memory upkeep and continual integration | multiple published configs from `4k` to `500k` spans | strong internal durability harness rather than a single public scalar |
| `ConvoMem` | preferences, changing facts, implicit links, abstention | `75,336` QA pairs | guardrail against overengineering memory when full context still works well |

## Glossary

### Working memory

The tiny active context used for the current task.
Best for immediate coherence.
Weak at long horizons if it absorbs too much state.

### Episodic archive

Raw sessions or turns kept for provenance.
Best source of truth.
Too noisy to serve as the only retrieval surface.

### Memory atom

Compact fact, event, preference, or relation extracted from raw interactions.
Best online retrieval unit when backed by provenance.

### Profile memory

Stable user traits, preferences, identity, and long-lived persona attributes.
Should stay separate from transient event memory.

### Event memory

Timestamped event or situation memory with temporal anchors.
Especially useful for temporal reasoning and update handling.

### Reflection memory

Compressed higher-level abstraction or synthesized observation derived from repeated or dense evidence.
Useful for stable windows and low-token recall.
Risky if it drifts away from raw evidence.

### Rehydration

Retrieve compact memory first, then pull raw evidence only for the shortlisted candidates.
This is one of the strongest recurring design patterns in frontier systems.

### Supersession

Explicit logic for updates, corrections, and invalidated facts.
Critical for `LongMemEval_s`.

### Scratchpad memory

Temporary task-local accumulation of salient facts for a hard reasoning path.
Likely important for `BEAM`-style pressure.

### Offline consolidation

Asynchronous cleanup, deduplication, merging, abstraction, or profile refresh performed outside the hot path.
Important for scale and efficiency.

### Agentic retrieval

Using specialized roles, planners, or multi-step search over memory rather than only static ranking.
Powerful but easy to overbuild.

### Memory operating system

A systems-level framing where memory is treated as a managed resource with storage tiers, scheduling, migration, and lifecycle rules.
Conceptually strong, but often heavier than a first benchmark-winning stack needs.

## Family map

| Family | Core idea | Excels at | Usually fails at | Most relevant benchmarks |
|---|---|---|---|---|
| Full-context control | keep history in prompt | honesty baseline, short histories | scale, token cost, noise | `ConvoMem`, short `LongMemEval_s` slices |
| Vector or chunk retrieval | embed and search chunks | simple factual recall | updates, temporal ambiguity, noisy long histories | baseline only |
| Temporal atom memory | retrieve compact timestamped units | updates, temporal reasoning, provenance | can miss broader relational context if too sparse | `LongMemEval_s`, `GoodAI` |
| Observational stable-window memory | compress history into stable observations and reflections | stable prompt window, cacheability, low-noise recall | observation drift, evidence loss if compression is weak | `LongMemEval_s`, `BEAM` |
| Event-calendar memory | explicit temporal structure and event indexing | anchored time questions, temporal multi-hop | heavier query planning | `LongMemEval_s`, `LoCoMo`, `BEAM` |
| Profile-separated memory | isolate stable persona from transient events | personalization, changing facts, user coherence | overfitting profile tasks if event handling is weak | `LoCoMo`, `ConvoMem` |
| Dual-store or OS-style memory | separate hot online memory from slower consolidated memory | long-range growth, lifecycle management, scale | implementation complexity | `BEAM`, `GoodAI`, later `LoCoMo` |
| Agentic search memory | retrieval roles, verification, orchestration | hardest multi-hop or ambiguous cases | latency, token blow-up, brute-force risk | frontier-only lane |

## System map

### Chronos

- organization: academic paper, not yet a pinned public code surface in our current sweep
- core idea:
  - structured subject-verb-object event tuples
  - event calendar plus turn calendar
  - alias and datetime-range resolution
  - iterative temporal retrieval guidance
- verified public benchmark evidence:
  - `92.60%` for Chronos Low on `LongMemEvalS`
  - `95.60%` for Chronos High on `LongMemEvalS`
- where it clearly excels:
  - temporal grounding
  - update handling
  - anchored retrieval guidance
  - multi-hop temporal reasoning
- main caution:
  - heavier query-time orchestration than a first lightweight baseline
  - paper-first surface, not yet a fully pinned reproduction path in our repo
- what to borrow:
  - event calendar
  - datetime-range logic
  - alias handling
  - temporal retrieval guidance

### Supermemory

- organization: Supermemory research + open-source MIT repo + product API
- license surface:
  - `supermemoryai/supermemory`: `MIT`
- core idea:
  - extract compact memories from chunks
  - track relations such as updates, extends, derives
  - separate document time and event time
  - retrieve atomic memories first, then rehydrate source evidence
- verified public benchmark evidence from official research page:
  - `81.6%` on `LongMemEval_s` with `gpt-4o`
  - `84.6%` with `gpt-5`
  - `85.2%` with `gemini-3-pro`
- public but not fully pinned in our source sweep:
  - repo README claims `#1` on `LongMemEval`, `LoCoMo`, and `ConvoMem`
  - exact current `LoCoMo` and `ConvoMem` threshold values still need pinning before we treat them as fixed bars
- company or product usage surface:
  - app, API, connectors, MCP integration, browser extension, and MemoryBench
- where it clearly excels:
  - high-signal retrieval units
  - temporal versioning
  - rehydration discipline
  - benchmark-native framing
- main caution:
  - some stronger frontier claims remain ahead of fully pinned public reproduction
- what to borrow:
  - atom-first retrieval
  - dual time fields
  - supersession logic
  - rehydrate-after-retrieve discipline

### Supermemory ASMR

- organization: pending frontier release tracked from official research root and prior writeup
- core idea:
  - specialized search roles
  - parallel ingestion or observer-style decomposition
  - source verification before final answer
  - heavy focus on retrieval quality
- public claim currently tracked:
  - about `98.60%` with an 8-variant ensemble on `LongMemEval_s`
  - about `97.20%` with a 12-variant decision forest
- where it clearly excels conceptually:
  - retrieval specialization
  - verification before answer
  - explicit acknowledgment that retrieval is the main bottleneck
- main caution:
  - not yet public as a clean reproducible implementation
  - likely too heavy for the default online path
- what to borrow:
  - specialist retrieval roles
  - verification before answer
- what to postpone:
  - answer forests
  - multi-agent online fanout as default behavior

### Mastra Observational Memory

- organization: Mastra research + open framework from the team behind Gatsby
- license surface:
  - `mastra-ai/mastra`: dual-license
  - Apache-2.0 for the core framework and most of the codebase
  - enterprise license for `ee/` paths
- core idea:
  - stable cacheable context window
  - Observer and Reflector background agents
  - dense observation logs instead of dynamic retrieval every turn
- verified public benchmark evidence from official research page:
  - `84.23%` on `LongMemEval` with `gpt-4o`
  - `94.87%` on `LongMemEval` with `gpt-5-mini`
- company or product usage surface:
  - framework-level long-term + working memory support inside Mastra's agent stack
- where it clearly excels:
  - stable prompt window
  - compression-first memory
  - strong `LongMemEval` results without per-turn retrieval injection
- main caution:
  - observation compression can drift if evidence fidelity is weak
  - must keep licensing boundaries clear when borrowing from the repo
- what to borrow:
  - observation and reflection pipeline
  - stable-window doctrine
  - compression as a first-class design surface

### Zep / Graphiti

- organization: Zep product + Graphiti open-source temporal graph framework
- license surface:
  - `getzep/graphiti`: `Apache-2.0`
- core idea:
  - temporally-aware knowledge graph
  - incremental updates
  - precise historical queries
  - graph, semantic, and keyword search
- public product usage surface:
  - Graphiti powers the core of Zep's memory layer and context engineering platform
- verified public benchmark evidence:
  - no single pinned benchmark score from official sources in this refresh
- where it clearly excels:
  - relation structure
  - temporal history queries
  - provenance visibility
- main caution:
  - graph-first systems can get heavy fast
  - not obviously the first lightweight benchmark winner by default
- what to borrow:
  - temporal relation logic
  - historical query semantics
  - relation-aware retrieval without forcing a graph database too early

### Mem0

- organization: Mem0 product + open-source Apache memory layer
- license surface:
  - `mem0ai/mem0`: `Apache-2.0`
- core idea:
  - memory extraction, consolidation, retrieval
  - graph-aware memory variant
  - production-facing universal memory layer
- verified public benchmark evidence from paper page:
  - `26%` relative improvement in LLM-as-Judge metric over OpenAI on `LOCOMO`
  - graph-memory variant about `2%` higher overall than the base configuration
  - major latency and token savings versus full-context
- company or product usage surface:
  - memory layer product
  - MCP server
  - Chrome extension and OpenMemory-adjacent tooling
- where it clearly excels:
  - product packaging
  - extraction ergonomics
  - practical latency and cost framing
- main caution:
  - more product-general than benchmark-native
  - graph framing can distract from the simpler retrieval wins
- what to borrow:
  - memory-write ergonomics
  - consolidation pipeline discipline
  - clear memory API boundaries

### Letta / MemGPT line

- organization: Letta platform and MemGPT-style stateful-agent lineage
- license surface:
  - `letta-ai/letta`: `Apache-2.0`
- core idea:
  - stateful agents
  - explicit memory tiers
  - archival memory plus in-context memory blocks
  - self-improving long-running agents
- public product usage surface:
  - Letta positions itself as a platform for stateful agents with long-term memory
  - official docs expose archival memory, leaderboards, and memory SDKs
- verified public benchmark evidence:
  - no single public benchmark scalar from the official docs used here
- where it clearly excels:
  - memory tier separation
  - agent state surfaces
  - long-running stateful-agent framing
- main caution:
  - block editing itself is not a benchmark-winning retrieval method
- what to borrow:
  - separation between pinned working state and searchable archival memory
  - stateful-agent boundaries

### LangMem

- organization: LangChain open-source memory library for LangGraph agents
- license surface:
  - `langchain-ai/langmem`: `MIT`
- core idea:
  - hot-path memory tools
  - background memory manager
  - storage-agnostic core API
  - native integration with LangGraph memory stores
- public product usage surface:
  - memory tools and background extraction for LangGraph deployments
- verified public benchmark evidence:
  - no pinned public benchmark scalar in the sources used here
- where it clearly excels:
  - clear API boundaries
  - hot-path vs background split
  - pragmatic integration for agent stacks
- main caution:
  - broad framework ergonomics do not automatically imply benchmark leadership
- what to borrow:
  - separation of online and background memory operations
  - memory tools for explicit write and search

### A-Mem

- organization: research system with open MIT reproduction repo
- license surface:
  - `WujiangXu/AgenticMemory`: `MIT`
- core idea:
  - dynamic note-like memory organization
  - Zettelkasten-inspired linking
  - adaptive memory evolution
- verified public benchmark evidence:
  - paper abstract claims superior improvement over existing SOTA baselines across six foundation models
  - no single scalar score pinned in the abstract used here
- where it clearly excels:
  - memory organization
  - dynamic linking
  - adaptive note evolution
- main caution:
  - elegant organization is not automatically the highest-payoff benchmark mutation
- what to borrow:
  - lightweight relation building
  - note-style memory structure

### O-Mem

- organization: OPPO Personal AI Lab research
- core idea:
  - active user profiling
  - explicit persona memory plus topic or event context
  - hierarchical retrieval
- verified public benchmark evidence from paper page:
  - `51.67%` on public `LoCoMo`
  - `62.99%` on `PERSONAMEM`
  - paper says this is nearly `3%` above prior `LangMem` on `LoCoMo`
- where it clearly excels:
  - personalization
  - profile versus event separation
  - efficient hierarchical retrieval
- main caution:
  - profile-heavy designs can overfit persona tasks if event handling is weak
- what to borrow:
  - active profile refresh
  - strict profile/event separation

### SimpleMem

- organization: aiming-lab research + MIT repo + MCP service surface
- license surface:
  - `aiming-lab/SimpleMem`: `MIT`
- core idea:
  - semantic structured compression
  - recursive memory consolidation
  - adaptive query-aware retrieval
- verified public benchmark evidence:
  - paper page reports average `26.4%` F1 improvement over baselines and up to `30x` lower inference-time token use
  - official repo highlights `LoCoMo` task F1 gains over Mem0 on `gpt-4.1-mini`
- company or product usage surface:
  - cloud-hosted MCP memory service
- where it clearly excels:
  - information density
  - efficiency-aware compression
  - query-aware retrieval planning
- main caution:
  - compression systems need strong rehydration or they lose nuance
- what to borrow:
  - semantic structured compression
  - recursive consolidation
  - query-aware retrieval scope control

### LightMem

- organization: Zhejiang University / ZJUNLP research + MIT repo
- license surface:
  - `zjunlp/LightMem`: `MIT`
- core idea:
  - sensory filtering
  - topic-aware short-term memory
  - offline sleep-time long-term consolidation
- verified public benchmark evidence from paper page:
  - up to `10.9%` accuracy gains on `LongMemEval`
  - up to `117x` lower token use
  - up to `159x` fewer API calls
  - runtime reduction greater than `12x`
- where it clearly excels:
  - lightweight online path
  - offline-heavy design
  - efficiency discipline
- main caution:
  - newer line that still needs more cross-benchmark pressure
- what to borrow:
  - sensory filtering
  - sleep-time consolidation
  - aggressive hot-path efficiency

### MemoryOS

- organization: BAI-LAB research + Apache-2.0 repo
- license surface:
  - `BAI-LAB/MemoryOS`: `Apache-2.0`
- core idea:
  - memory operating system for personalized agents
  - hierarchical storage
  - dynamic updates between memory levels
  - explicit storage, updating, retrieval, and generation modules
- verified public benchmark evidence:
  - official paper page reports average improvement of `49.11%` on F1 and `46.18%` on BLEU-1 over baselines on `LoCoMo` with `GPT-4o-mini`
- company or product usage surface:
  - playground, Docker image, and eval scripts for personalization-oriented agents
- where it clearly excels:
  - memory lifecycle framing
  - tiered storage logic
  - personalization-heavy memory management
- main caution:
  - hierarchy can become process-heavy if every write crosses multiple tiers
- what to borrow:
  - lifecycle management
  - controlled tier movement
  - separation of storage, update, retrieval, and generation

### MemOS

- organization: MemTensor open-source memory operating system
- license surface:
  - `MemTensor/MemOS`: `Apache-2.0`
- core idea:
  - treat memory as a managed system resource
  - unify plaintext, activation, and parameter memory
  - scheduling, migration, preloading, and evolution of memories
- verified public benchmark evidence:
  - paper page reports `159%` improvement in temporal reasoning over OpenAI's global memory on `LoCoMo`
  - overall accuracy gain of `38.97%`
  - `60.95%` reduction in token overhead
  - current repo README advertises `LoCoMo 75.80` and `LongMemEval +40.43%` style relative gains, but those should be treated as repo claims until pinned against canonical benchmark setup
- company or product usage surface:
  - cloud and local plugins for OpenClaw and related agent systems
- where it clearly excels:
  - systems-level thinking
  - memory scheduling
  - proactive preload ideas
- main caution:
  - broad systems ambition can outrun immediate benchmark payoff
- what to borrow:
  - scheduler language
  - memory lifecycle terms
  - selective preload concepts

## Newer or especially relevant 2026 ideas to watch

### BEAM + LIGHT

- `BEAM` is not just another benchmark.
- It introduces `100` coherent conversations and `2,000` validated questions up to roughly `10M` tokens.
- The associated `LIGHT` system uses:
  - long-term episodic memory
  - short-term working memory
  - a scratchpad for salient facts
- the paper reports `3.5%` to `12.69%` improvements over the strongest baselines depending on backbone model

Why this matters for us:

- it pressures memory-role separation directly
- it is the strongest current argument that our next architecture must distinguish working memory, episodic archive, stable compressed memory, and scratchpad memory

### All-Mem

- fresh March 20, 2026 paper
- proposes topology-structured memory with explicit non-destructive consolidation
- online bounded visible surface
- offline `SPLIT`, `MERGE`, and `UPDATE` topology edits with gating
- abstract reports improved retrieval and QA on `LoCoMo` and `LongMemEval`

Why it matters:

- this is one of the clearest recent attempts to combine online bounded retrieval with offline structured evolution
- it is highly relevant to `BEAM` pressure

## Product and company usage surfaces

This section is about how systems are being packaged and used by the organizations behind them, not about unverified third-party customer deployment claims.

| System | Company or org usage surface | Why this matters for us |
|---|---|---|
| `Supermemory` | app, API, connectors, browser extension, MCP, MemoryBench | proves a benchmark-native system can also ship as a product memory layer |
| `Mastra` | framework-level long-term + working memory for agents and apps | shows stable memory can live inside a broader agent framework |
| `Zep / Graphiti` | Graphiti powers Zep's context engineering platform | strong example of graph-backed memory as product infrastructure |
| `Mem0` | universal memory layer, MCP server, Chrome extension | best example of productizing memory extraction and retrieval as a service boundary |
| `Letta` | stateful-agent platform with archival memory, SDKs, and leaderboards | useful reference for stateful agent surfaces and memory tiers |
| `LangMem` | LangGraph-native hot-path and background memory tooling | useful reference for practical agent integration rather than benchmark marketing |
| `SimpleMem` | repo plus cloud-hosted MCP service | useful example of compression-first research shipping as a usable service |
| `MemOS` | cloud and local plugins for memory-native agent systems | shows OS-style memory ideas moving into toolable agent infrastructure |

## Benchmark score reality table

Only include a score as "pinned" when the source we reviewed states it clearly.

| System | Benchmark | Public score or claim | Pin status |
|---|---|---|---|
| `Chronos High` | `LongMemEvalS` | `95.60%` | pinned from paper abstract |
| `Chronos Low` | `LongMemEvalS` | `92.60%` | pinned from paper abstract |
| `Mastra OM` + `gpt-5-mini` | `LongMemEval` | `94.87%` | pinned from official research page |
| `Mastra OM` + `gpt-4o` | `LongMemEval` | `84.23%` | pinned from official research page |
| `Supermemory` + `gemini-3-pro` | `LongMemEval_s` | `85.2%` | pinned from official research page |
| `Supermemory` + `gpt-5` | `LongMemEval_s` | `84.6%` | pinned from official research page |
| `Supermemory` + `gpt-4o` | `LongMemEval_s` | `81.6%` | pinned from official research page |
| `MemoryOS` | `LoCoMo` | average `+49.11%` F1 and `+46.18%` BLEU-1 over baselines on `GPT-4o-mini` | pinned from paper page summary |
| `O-Mem` | public `LoCoMo` | `51.67%` | pinned from paper page summary |
| `O-Mem` | `PERSONAMEM` | `62.99%` | pinned from paper page summary |
| `SimpleMem` | mixed benchmark suite | average `+26.4%` F1 and up to `30x` lower token use | pinned from paper page summary |
| `LightMem` | `LongMemEval` | up to `+10.9%` accuracy gain, up to `117x` lower token use | pinned from paper page summary |
| `MemOS` | `LoCoMo` | `159%` temporal reasoning gain over OpenAI global memory, `+38.97%` overall accuracy, `-60.95%` token overhead | pinned from paper page summary |
| `Supermemory` | `LoCoMo`, `ConvoMem` | repo claims `#1` | not yet pinned numerically in this refresh |
| `BEAM / LIGHT` | `BEAM` | `+3.5%` to `+12.69%` over strongest baselines depending on backbone | pinned from paper abstract |

## What this means for our chip

### The strongest recurring lessons

1. Retrieval quality is still the main bottleneck.
2. Time and supersession must be explicit.
3. Compact retrieval units beat raw noisy chunks.
4. Rehydration is better than retrieving huge raw context by default.
5. Stable profile memory should not be mixed carelessly with event memory.
6. Offline consolidation is becoming table stakes.
7. `BEAM` pressure favors memory-role separation, not just better search.

### Current interpretation of our own position

- our current best measured lane is still `observational_temporal_memory + MiniMax-M2.7`
- the reason it is winning locally is not that observational memory is universally best
- the reason is that it currently exposes exact answer-bearing propositions to the model better than the alternatives we have measured
- the strongest likely overtake candidate under harder `BEAM` pressure is still a hybrid that combines:
  - stable observational compression
  - stronger temporal or event structure
  - explicit profile versus event separation
  - scratchpad or working-memory control

### Immediate borrowing queue

Borrow first:

- `Supermemory`:
  - memory atoms
  - dual time fields
  - rehydrate-after-retrieve
  - license status in current repo sweep: `MIT`
- `Mastra OM`:
  - observation and reflection pipeline
  - stable window doctrine
  - license status: Apache-2.0 core plus enterprise `ee/` carve-out
- `Chronos`:
  - event calendar
  - alias and temporal range logic
  - source surface is still paper-first
- `O-Mem`:
  - profile/event separation
  - active profile refresh
- `SimpleMem`:
  - semantic structured compression
  - recursive consolidation
  - license status: `MIT`
- `LightMem`:
  - offline sleep-time consolidation
  - sensory filtering
  - license status: `MIT`
- `Graphiti`:
  - temporal relation logic
  - history-aware retrieval
  - license status: `Apache-2.0`

Borrow carefully:

- `Mem0`:
  - memory write ergonomics
  - graph-aware extraction
  - license status: `Apache-2.0`
- `Letta`:
  - tiered memory surfaces
  - archival memory patterns
  - license status: `Apache-2.0`
- `MemoryOS` and `MemOS`:
  - lifecycle and scheduler thinking
  - both are `Apache-2.0`

Postpone:

- heavyweight answer forests
- graph-database-first infra
- complex memory operating system behavior in the hot path
- any benchmark trick that improves `BEAM` while breaking already-closed `LongMemEval_s` or `LoCoMo` slices

## Research sources

Primary or official sources used for this refresh:

- BEAM paper: `https://arxiv.org/abs/2510.27246`
- Chronos paper: `https://arxiv.org/abs/2603.16862`
- LongMemEval paper page: `https://huggingface.co/papers/2410.10813`
- Mastra OM research: `https://mastra.ai/research/observational-memory`
- Mastra agents surface: `https://mastra.ai/agents`
- Supermemory research: `https://supermemory.ai/research/`
- Supermemory MemoryBench docs: `https://supermemory.ai/docs/memorybench/overview`
- Supermemory benchmark integrations page: `https://supermemory.ai/docs/memorybench/integrations`
- Supermemory repo: `https://github.com/supermemoryai/supermemory`
- Graphiti repo: `https://github.com/getzep/graphiti`
- Zep overview docs: `https://help.getzep.com/overview`
- Graphiti overview docs: `https://help.getzep.com/graphiti/graphiti/overview`
- Mem0 paper page: `https://huggingface.co/papers/2504.19413`
- Mem0 GitHub org surface: `https://github.com/mem0ai`
- Letta repo: `https://github.com/letta-ai/letta`
- Letta archival memory docs: `https://docs.letta.com/guides/core-concepts/memory/archival-memory/`
- Letta leaderboard docs: `https://docs.letta.com/leaderboard`
- LangMem repo: `https://github.com/langchain-ai/langmem`
- A-Mem paper page: `https://huggingface.co/papers/2502.12110`
- A-Mem paper: `https://arxiv.org/abs/2502.12110`
- A-Mem reproduction repo: `https://github.com/WujiangXu/AgenticMemory`
- O-Mem paper page: `https://huggingface.co/papers/2511.13593`
- SimpleMem paper page: `https://huggingface.co/papers/2601.02553`
- SimpleMem repo: `https://github.com/aiming-lab/SimpleMem`
- LightMem paper page: `https://huggingface.co/papers/2510.18866`
- LightMem repo: `https://github.com/zjunlp/LightMem`
- MemoryOS paper page: `https://huggingface.co/papers/2506.06326`
- MemoryOS repo: `https://github.com/BAI-LAB/MemoryOS`
- MemOS paper page: `https://huggingface.co/papers/2507.03724`
- MemOS repo: `https://github.com/MemTensor/MemOS`
- MemOS evaluation results dataset card: `https://huggingface.co/datasets/MemTensor/MemOS_eval_result`
- All-Mem paper: `https://arxiv.org/abs/2603.19595`
