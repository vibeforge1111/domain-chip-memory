# AI Memory Research Base

Date: 2026-03-22
Status: research-grounded

## Why this document exists

This repo should not start by building "a memory system" in the abstract.
It should start by understanding:

- what kinds of memory AI systems have actually used
- what each memory type is good at
- where each memory type fails
- which parts matter most for benchmark performance
- which lightweight design choices are most likely to win first

The north star is not architectural novelty.
The north star is:

- become `#1` on the benchmark stack
- with the lightest online memory path that still wins honestly

## Executive conclusions

### 1. There is no single memory type that wins alone

The strongest systems combine multiple memory forms:

- a small in-context working memory
- a persistent episodic trace or raw source archive
- a distilled semantic memory for facts and preferences
- explicit temporal or version handling
- query-aware retrieval

### 2. Retrieval quality is still the main bottleneck

Across `LongMemEval`, `LoCoMo`, and the latest memory-system papers, the primary failure is not "the answer prompt was weak."
It is:

- stale evidence
- noisy evidence
- wrong evidence granularity
- missing temporal disambiguation
- loss of provenance

### 3. Lightweight systems can be very strong if they compress intelligently

Recent work like `LightMem` and `SimpleMem` points to an important direction:

- keep the online path small
- push heavy consolidation offline
- retrieve compact memory units instead of raw verbose history

This is directly aligned with our goal.

### 4. Full context is still a serious baseline

`ConvoMem` is the strongest warning here.
Its core claim is that for the first roughly `30` to `150` conversations, simple full-context methods can stay surprisingly competitive.

Implication:

- a memory system that loses to full context on shorter histories is not yet good enough

### 5. The most defensible winning pattern is temporal semantic memory with provenance

The best current evidence points toward a system with:

- append-only raw episodes
- extracted memory atoms
- explicit supersession/version rules
- event time and document time
- lightweight hybrid retrieval
- optional offline consolidation

Start there.

## Memory taxonomy

Below is the practical memory taxonomy that matters for modern AI agents.

### 1. Parametric or implicit memory

What it is:

- knowledge stored in model weights

Examples:

- base model facts
- fine-tuned habits
- instruction-tuned response preferences

Benefits:

- zero retrieval latency at inference
- very compact at usage time
- great for broad, stable knowledge

Problems:

- stale knowledge is hard to update
- poor provenance and traceability
- hard to personalize per user without extra layers
- not enough by itself for interactive long-term memory

Usefulness for our chip:

- background capability only
- not the main design surface

### 2. Working memory

What it is:

- the currently active context window
- recent messages, instructions, scratchpad, immediate task state

Evidence:

- `Empowering Working Memory for Large Language Model Agents`
- Letta’s stateful-agent model

Benefits:

- fastest and most faithful memory access
- ideal for current task state
- no retrieval ambiguity because context is already present

Problems:

- expensive at long horizons
- context window pressure
- easy to pollute with redundant or stale state

Usefulness for our chip:

- essential
- should stay small and high-signal

### 3. Raw episodic memory

What it is:

- append-only record of past interactions or sessions

Evidence:

- `Generative Agents`
- LoCoMo raw conversation histories
- Letta messages and archival history

Benefits:

- highest fidelity
- preserves nuance and exact wording
- best source of truth when retrieval is correct

Problems:

- noisy and expensive to search directly
- poor information density
- hard to reason over if the system only uses semantic similarity

Usefulness for our chip:

- mandatory as ground truth
- should exist, but not be the main online retrieval unit

### 4. Summarized episodic memory

What it is:

- per-session or rolling summaries of episodes

Evidence:

- LoCoMo `session_summary`
- LongMemEval session-level expansions
- Letta summary blocks

Benefits:

- much smaller than raw logs
- good for quick recall
- strong intermediate compression layer

Problems:

- details get dropped
- summaries can lock in wrong interpretations
- weak for exact evidence or subtle updates

Usefulness for our chip:

- useful as an auxiliary memory view
- dangerous if it becomes the only view

### 5. Semantic fact memory

What it is:

- distilled facts, preferences, traits, events, and other atomic memory units

Evidence:

- Supermemory memory generation
- Mem0 memory layer
- LangMem extraction and consolidation

Benefits:

- high information density
- easy to search
- much better for personalization than raw logs
- good base for benchmark categories like user facts and preferences

Problems:

- fact extraction can hallucinate or oversimplify
- loses local conversational nuance
- can retain stale versions if no update logic exists

Usefulness for our chip:

- central memory form
- probably the best online retrieval unit

### 6. Profile or persona memory

What it is:

- compact stable representation of user traits, preferences, identity, or agent identity

Evidence:

- Mem0 multi-level memory
- Letta `human` and `persona` blocks
- ID-RAG style identity grounding for long-horizon coherence

Benefits:

- cheap to keep in context
- excellent for personalization
- helps coherence and identity stability

Problems:

- easy to over-generalize
- may not reflect recent updates
- can become bloated if mixed with transient details

Usefulness for our chip:

- very useful
- should stay separate from changing facts

### 7. Archival searchable memory

What it is:

- persistent external store queried on demand

Evidence:

- Letta archival memory
- vector stores and external passage stores
- many RAG-style systems

Benefits:

- effectively unbounded storage
- removes pressure from the context window
- good for background facts and historical support

Problems:

- retrieval quality becomes everything
- semantic search alone is weak on time and contradictions
- can surface plausible but wrong context

Usefulness for our chip:

- required
- should be query-routed carefully

### 8. Vector or chunk memory

What it is:

- text split into chunks and retrieved by embeddings or hybrid search

Evidence:

- standard RAG baselines
- LongMemEval retrieval baselines

Benefits:

- simple and well understood
- good default for large unstructured corpora
- easy to deploy

Problems:

- weak on stale vs updated facts
- weak on temporal ordering
- chunk boundaries often destroy meaning
- lower precision for conversational memory than distilled atoms

Usefulness for our chip:

- baseline only
- should not be the final architecture

### 9. Temporal or versioned memory

What it is:

- memories with timestamps, validity windows, and supersession

Evidence:

- Supermemory relational versioning and event/document dates
- Graphiti and Zep temporal context graph
- LongMemEval time-aware retrieval and pruning

Benefits:

- directly addresses knowledge updates
- directly addresses temporal reasoning
- reduces stale fact collisions
- improves provenance and historical querying

Problems:

- more complex ingestion
- needs careful invalidation rules
- can become overengineered if every fact becomes a graph project

Usefulness for our chip:

- non-negotiable for benchmark leadership

### 10. Graph memory

What it is:

- entities, facts, and relations stored as graph structures

Evidence:

- Graphiti / Zep
- PlugMem knowledge-centric graph
- A-Mem dynamic linking

Benefits:

- supports multi-hop reasoning
- traceable relation structure
- can unify semantic, temporal, and relational views

Problems:

- graph construction can be brittle
- higher implementation and ops complexity
- graph DB is not automatically better than a strong lightweight relational design

Usefulness for our chip:

- maybe
- start with graph ideas, not necessarily a graph database

### 11. Reflective memory

What it is:

- higher-level lessons, abstractions, and synthesized insights from repeated episodes

Evidence:

- `Generative Agents` reflections
- Reflexion-style memory
- MemBench’s distinction between factual and reflective memory

Benefits:

- converts repeated experience into reusable guidance
- useful for self-improvement and policy learning
- can reduce repeated mistakes

Problems:

- highly lossy
- can overfit or create false generalizations
- weak as primary evidence for QA-style memory benchmarks

Usefulness for our chip:

- important for the autoloop
- secondary for first benchmark wins

### 12. Procedural memory

What it is:

- rules, workflows, skills, policies, and action habits

Evidence:

- Letta memory blocks for policies and workflows
- LangMem background refinement
- PlugMem prescriptive knowledge

Benefits:

- crucial for agent behavior consistency
- useful for tool use and repeated workflows
- strong for self-improvement loops

Problems:

- not the same as factual memory
- can contaminate user memory if mixed together
- easy to bloat if all behavior gets pinned in context

Usefulness for our chip:

- important for the flywheel
- separate from user memory

### 13. Explicit model-side memory

What it is:

- learned memory modules outside the base model weights

Evidence:

- `LongMem`
- `Memory^3`

Benefits:

- can reduce dependence on huge base models
- promising for scale and cost in model-centric systems
- offers a cleaner separation between parameters and retrievable memory

Problems:

- not the lightest path for an external agent-memory product
- often requires model-side training or special architecture
- weaker fit for fast product iteration

Usefulness for our chip:

- conceptually important
- not the first implementation path

### 14. Agentic retrieval and multi-agent memory

What it is:

- specialized agents or planners that search, reason over, and assemble memory context

Evidence:

- the Supermemory experimental ASMR direction described by the user
- E-mem episodic context reconstruction
- A-Mem dynamic organization

Benefits:

- can rescue hard temporal and multi-hop cases
- good when naive similarity search fails
- can reason over memory structure instead of just ranking text

Problems:

- can explode latency and cost
- easy to win via brute-force orchestration rather than elegant memory design
- harder to productionize cleanly

Usefulness for our chip:

- use sparingly
- should arrive after a strong lightweight baseline, not before

## What makes a memory system actually good

The most important properties are not "vector" versus "graph."
They are:

### 1. Provenance

Every memory unit should trace back to raw source data.

Why it matters:

- benchmark questions often require exact evidence
- wrong abstractions need a path back to truth

### 2. Temporal grounding

You need both:

- when the information was stated
- when the referenced event occurred

Why it matters:

- `LongMemEval` punishes systems that confuse old and new facts

### 3. Supersession and invalidation

A system needs explicit rules for:

- updates
- corrections
- stale information

Why it matters:

- semantic similarity alone cannot resolve contradictions well

### 4. Information density

The retrieval unit should be compact enough to fit many candidates, but rich enough to preserve meaning.

Why it matters:

- raw logs are too noisy
- summaries are too lossy
- memory atoms with provenance are the best compromise

### 5. Query-aware retrieval

Different questions need different memory routes.

Examples:

- preference query
- temporal query
- multi-session synthesis
- abstention case

### 6. Separation of memory roles

Do not mix:

- current working memory
- persistent user memory
- procedural rules
- raw historical archive

### 7. Abstention support

A memory system is bad if it confidently answers from weak matches.

### 8. Offline consolidation

The best lightweight designs move expensive cleanup and abstraction out of the hot path.

## Industry and open-source systems

### Supermemory

What it does differently:

- extracts memories from chunks instead of only retrieving chunks
- uses relationships like updates and extends
- tracks both conversation time and event time
- retrieves atomic memories, then rehydrates source chunks

Benefits:

- strong on `LongMemEval`
- directly attacks stale-fact and temporal problems

Problems:

- public frontier claims are partly ahead of reproducible public detail
- the more agentic retrieval variants may be heavier than the simplest winning path

### Zep / Graphiti

What it does differently:

- builds temporal context graphs
- stores facts with validity windows
- preserves episodes as provenance
- uses hybrid retrieval across semantic, keyword, and graph traversal

Benefits:

- strong temporal and contradiction handling
- very interpretable retrieval path

Problems:

- graph construction and graph infra add complexity
- may be heavier than needed for an initial benchmark-winning core

### Mem0

What it does differently:

- production-facing memory layer
- multi-level memory across user, session, and agent state
- strong latency and token-efficiency positioning

Benefits:

- pragmatic product framing
- good example of memory as a reusable service layer

Problems:

- public benchmark framing has been contested by competitors
- architecture emphasis is less obviously benchmark-specialized than temporal-first systems

### Letta

What it does differently:

- separates memory blocks pinned in context from searchable archival memory
- newer Letta Code adds `MemFS`, a git-backed memory filesystem

Benefits:

- very clear distinction between core memory and archival memory
- strong stateful-agent abstraction
- strong support for agent self-edit and procedural memory

Problems:

- memory blocks can bloat if used for everything
- core block editing is not itself a benchmark-optimized retrieval architecture

### LangMem

What it does differently:

- supports both hot-path memory actions and background consolidation
- storage-agnostic API

Benefits:

- clean architecture
- useful pattern for keeping the online path light and the consolidation path asynchronous

Problems:

- genericity can trade off against peak benchmark specialization

### A-Mem

What it does differently:

- uses note-like memory organization and dynamic linking
- memory network evolves as new notes arrive

Benefits:

- good for relational organization
- good inspiration for evolving semantic memory

Problems:

- can become more organizationally elegant than benchmark-efficient

### SimpleMem

What it does differently:

- semantic structured compression
- online synthesis
- intent-aware retrieval planning

Benefits:

- very aligned with our lightweight goal
- explicitly optimizes information density

Problems:

- compressed systems always risk detail loss

### LightMem

What it does differently:

- sensory filtering
- topic-aware short-term memory
- offline sleep-time long-term consolidation

Benefits:

- strongest lightweight-first research signal in the current sweep
- explicitly separates online and offline cost

Problems:

- newer research path, so product maturity is still unclear

### PlugMem

What it does differently:

- turns episodic memory into a knowledge-centric graph of propositional and prescriptive knowledge

Benefits:

- strong conceptual separation between raw experience and decision-relevant knowledge

Problems:

- more architectural machinery than we likely need at the start

### MemoryOS

What it does differently:

- explicitly treats agent memory like an operating-system hierarchy
- separates short-term, mid-term, and long-term persona memory
- focuses on controlled memory updates between tiers

Benefits:

- good framing for memory lifecycle management
- strong reminder that storage, update, retrieval, and generation should be different subsystems
- useful for personalization-heavy agents

Problems:

- hierarchy can become process-heavy if every write must move across multiple tiers
- reported gains are benchmark-relative rather than yet becoming the clearest public overall frontier

### MemOS

What it does differently:

- broadens memory beyond plaintext retrieval into a memory operating system with `MemCube` units
- unifies plaintext, activation, and parameter memory under one framework
- emphasizes provenance, versioning, migration, and evolution across memory forms

Benefits:

- best current systems-level framing for long-term memory as infrastructure rather than only retrieval
- strong conceptual fit for future continual-learning and skill-memory work
- useful language for provenance and memory lifecycle design

Problems:

- much broader than what we need for a first benchmark-winning online path
- too much systems ambition too early could slow down benchmark progress

### O-Mem

What it does differently:

- centers active user profiling
- separates persona attributes from topic or event context
- claims better LoCoMo and PERSONAMEM results through hierarchical retrieval

Benefits:

- strong signal that profile memory and event memory should stay separate
- good inspiration for personalization-specific retrieval paths
- claims efficiency gains, not only accuracy gains

Problems:

- profile-heavy designs risk overfitting to persona-style benchmarks
- active profile extraction can amplify mistakes if correction paths are weak

## Benchmark implications

### LongMemEval

Winning traits:

- temporal grounding
- update handling
- multi-session synthesis
- low-noise retrieval

Bad fit:

- pure vector chunk search
- summary-only memory

### LoCoMo

Winning traits:

- episodic fidelity
- multi-hop relation support
- long-range temporal consistency

Bad fit:

- overly compressed memory that loses context

### ConvoMem

Winning traits:

- preference extraction
- changing-fact handling
- abstention
- not overusing retrieval when context is still manageable

Bad fit:

- heavy memory machinery for short histories

## The lightest-weight path likely to win

This is the design I would start with.

### Layer 1: append-only raw episode store

Store:

- every session
- turn timestamps
- session IDs
- raw messages

Use:

- provenance
- source rehydration

Implementation bias:

- file or SQLite/Postgres table

### Layer 2: extracted memory atoms

Store:

- fact
- preference
- event
- relationship
- source session
- source turn
- confidence

Use:

- primary retrieval unit

Implementation bias:

- lightweight relational store first

### Layer 3: temporal and supersession table

Store:

- `document_time`
- `event_time`
- `valid_from`
- `valid_to`
- `supersedes`
- `conflicts_with`

Use:

- update handling
- temporal reasoning

Implementation bias:

- relational constraints first
- graph DB optional later

### Layer 4: compact profile blocks

Store:

- stable traits
- persistent preferences
- high-level current state

Use:

- tiny in-context personalization memory

Implementation bias:

- one or a few pinned blocks

### Layer 5: retrieval router

Route by question type:

- full context if history is still small
- profile block for stable preference or persona queries
- atom retrieval for direct fact questions
- temporal filter plus atom retrieval for update questions
- rehydrate raw evidence only after candidate atoms are chosen

Implementation bias:

- deterministic or mostly deterministic routing first

### Layer 6: offline consolidation

Do offline:

- redundancy cleanup
- fact merging
- profile refresh
- reflective lesson extraction

Do not do this in the hot path unless necessary.

## What not to build first

Do not start with:

- a giant graph database
- a multi-agent search forest
- expensive prompt ensembles
- summary-only memory
- vector search as the only retrieval mode

Those can come later if the lightweight core plateaus.

## Recommendation for this chip

The starting architecture should be:

1. raw episodes
2. extracted semantic atoms
3. explicit time and supersession
4. small pinned profile memory
5. lightweight hybrid retrieval
6. offline consolidation
7. benchmark-specific routing

That is the strongest path I see for a lightweight system that still has a credible shot at `#1`.

## Sources

- LongMemEval paper and repo: `https://arxiv.org/abs/2410.10813`, `https://github.com/xiaowu0162/LongMemEval`
- LoCoMo repo: `https://github.com/snap-research/locomo`
- ConvoMem paper page and dataset: `https://huggingface.co/papers/2511.10523`, `https://huggingface.co/datasets/Salesforce/ConvoMem`
- Supermemory research: `https://supermemory.ai/research/`
- Supermemory repo: `https://github.com/supermemoryai/supermemory`
- MemoryBench repo: `https://github.com/supermemoryai/memorybench`
- Mem0 paper and repo: `https://arxiv.org/abs/2504.19413`, `https://github.com/mem0ai/mem0`
- Letta docs and repo: `https://docs.letta.com/`, `https://github.com/letta-ai/letta`
- LangMem repo: `https://github.com/langchain-ai/langmem`
- Graphiti repo: `https://github.com/getzep/graphiti`
- MemoryOS paper and repo: `https://arxiv.org/abs/2506.06326`, `https://github.com/BAI-LAB/MemoryOS`
- MemOS paper and repo: `https://arxiv.org/abs/2507.03724`, `https://github.com/MemTensor/MemOS`
- MemGPT paper: `https://arxiv.org/abs/2310.08560`
- LongMem paper: `https://arxiv.org/abs/2306.07174`
- Generative Agents paper: `https://arxiv.org/abs/2304.03442`
- Empowering Working Memory paper: `https://arxiv.org/abs/2312.17259`
- A-Mem paper: `https://arxiv.org/abs/2502.12110`
- O-Mem paper: `https://arxiv.org/abs/2511.13593`
- PlugMem paper: `https://arxiv.org/abs/2603.03296`
- SimpleMem paper: `https://arxiv.org/abs/2601.02553`
- E-mem paper: `https://arxiv.org/abs/2601.21714`
- LightMem paper and repo: `https://arxiv.org/abs/2510.18866`, `https://github.com/zjunlp/LightMem`
- Memory^3 paper: `https://arxiv.org/abs/2407.01178`
- MemBench paper: `https://arxiv.org/abs/2506.21605`
- MemoryAgentBench paper: `https://arxiv.org/abs/2507.05257`
