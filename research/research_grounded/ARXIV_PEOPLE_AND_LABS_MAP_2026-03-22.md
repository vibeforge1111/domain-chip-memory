# arXiv People And Labs Map

Date: 2026-03-22
Status: research-grounded

## Purpose

This file answers a practical question for the memory chip:

- who should we actually track if the goal is to build the strongest benchmark-native agent memory system

This is not a generic "top AI researchers" list.
It is a focused watchlist built from:

- benchmark authorship
- recurring authors across memory-system papers
- retrieval and semantic-search researchers whose work directly affects memory quality
- reinforcement-learning researchers working on learned memory management
- open-source labs and orgs shipping memory systems on GitHub

Selection rule:

- prefer people with direct paper or system evidence in agent memory, long-term conversational memory, retrieval, temporal reasoning, personalization memory, or learned memory control

## Best arXiv categories to monitor

If we want the highest signal-to-noise ratio on arXiv, these are the main lanes:

1. `cs.CL`
   Reason: most agent memory, conversational memory, memory benchmarks, and retrieval-for-LLMs papers land here.
2. `cs.AI`
   Reason: system architecture, agents, memory frameworks, and benchmark papers often appear here.
3. `cs.IR`
   Reason: retrieval quality is still the main bottleneck for memory systems.
4. `cs.LG`
   Reason: learned memory management, RL fine-tuning, test-time memory, and adaptive retrieval often show up here.
5. `cs.MA`
   Reason: multi-agent memory, role-specific memory, and orchestration-heavy systems sometimes land here.

Secondary lanes worth checking:

- `cs.DB` for storage and indexing ideas
- `cs.OS` for operating-system-style memory abstractions
- `stat.ML` for training and optimization work that may not be filed under CS first

## High-signal researcher clusters

The right way to think about "the best people" here is by cluster, not by one universal ranking.

### 1. Benchmark-native conversational memory

These are the people closest to the benchmark definitions we care about.

#### LongMemEval cluster

- `Di Wu`
- `Hongwei Wang`
- `Wenhao Yu`
- `Kai-Wei Chang`
- `Dong Yu`
- `Nanyun Peng`

Why track them:

- `LongMemEval` is one of the clearest public targets for us
- `Di Wu`, `Kai-Wei Chang`, and `Nanyun Peng` also appear on `Self-Routing RAG`, which matters because selective retrieval is directly relevant to memory routing

What they lead to:

- benchmark design
- time-aware retrieval
- selective retrieval
- memory-aware query expansion

#### LoCoMo cluster

- `Adyasha Maharana`
- `Dong-Ho Lee`
- `Sergey Tulyakov`
- `Mohit Bansal`
- `Francesco Barbieri`
- `Yuwei Fang`

Why track them:

- `LoCoMo` remains one of the core long-horizon conversational memory tests
- this cluster is strong on conversational recall, temporal structure, and evidence-grounded QA over long histories

What they lead to:

- long-session conversation design
- evidence-grounded evaluation
- summary versus raw-conversation tradeoffs

#### ConvoMem cluster

- `Egor Pakhomov`
- `Erik Nijkamp`
- `Caiming Xiong`

Why track them:

- `ConvoMem` is a high-signal corrective benchmark because it punishes overbuilt memory systems that lose to full context
- this cluster is especially useful for deciding when not to retrieve

What they lead to:

- transition points between full context and memory retrieval
- abstention behavior
- preference and changing-fact evaluation

### 2. Stateful-agent and memory-system builders

These are the people closest to practical memory systems that developers actually use.

#### MemGPT / Letta cluster

- `Charles Packer`
- `Sarah Wooders`
- `Kevin Lin`
- `Joseph E. Gonzalez`
- `Ion Stoica`

Why track them:

- `MemGPT` and then `Letta` shaped the current stateful-agent framing
- they are strong on memory tiers, persistent agent state, and procedural memory surfaces

What they lead to:

- memory-block design
- archival versus in-context memory separation
- agent memory ergonomics

#### Zep / Graphiti cluster

- `Preston Rasmussen`
- `Pavlo Paliychuk`
- `Daniel Chalef`

Why track them:

- this cluster is one of the clearest temporal-graph memory lines
- they explicitly attack changing relationships and historical queries

What they lead to:

- temporal knowledge graphs
- provenance-aware retrieval
- graph plus semantic hybrid search

#### Mem0 cluster

- `Prateek Chhikara`
- `Dev Khant`
- `Saket Aryan`
- `Taranjeet Singh`
- `Deshraj Yadav`

Why track them:

- Mem0 is one of the main production-facing memory-layer systems
- it matters even when we disagree with benchmark framing because it is influential in practice

What they lead to:

- memory extraction pipelines
- productizable memory layers
- graph-aware production memory

### 3. Retrieval and semantic-memory researchers

These people matter because memory systems fail mostly on retrieval, not on the final answer prompt.

#### HippoRAG cluster

- `Yu Su`
- `Michihiro Yasunaga`
- `Yiheng Shu`
- `Bernal Jimenez Gutierrez`

Why track them:

- `HippoRAG` is one of the strongest examples of retrieval informed by cognitive memory theory
- this cluster sits at the boundary of memory, graph retrieval, and multi-hop reasoning

What they lead to:

- graph retrieval
- knowledge integration over new experiences
- cheaper multi-hop retrieval

#### Selective retrieval cluster

- `Akari Asai`
- `Hannaneh Hajishirzi`
- `Di Wu`
- `Nanyun Peng`

Why track them:

- selective retrieval is critical for memory systems because bad retrieval is often worse than no retrieval
- `Self-RAG` and `Self-Routing RAG` are directly relevant to a lightweight-first memory router

What they lead to:

- retrieve-or-not decisions
- retrieval filtering
- model self-knowledge about when retrieval helps

#### Core IR cluster

- `Omar Khattab`
- `Matei Zaharia`
- `Keshav Santhanam`
- `ChengXiang Zhai`
- `Jiawei Han`
- `Jianfeng Gao`

Why track them:

- these names sit behind some of the highest-leverage retrieval ideas that memory systems can import
- `ColBERT` changed the retrieval quality-efficiency tradeoff
- `PlugMem` connects strong IR instincts to task-agnostic agent memory

What they lead to:

- late-interaction retrieval
- efficient relevance scoring
- knowledge-centric memory graphs
- retrieval abstractions that can beat naive chunk search

### 4. Learned memory management and reinforcement learning

If we want an autoloop flywheel that mutates memory policy instead of only hand-coding it, this cluster matters.

#### Memory-construction RL cluster

- `Yu Wang`
- `Ryuichi Takanobu`
- `Julian McAuley`
- `Xiaojian Wu`

Why track them:

- `Mem-alpha` is directly about learning what to store, how to structure it, and when to update it
- that is very close to our target of benchmark-driven self-improvement

What they lead to:

- reward-driven write policies
- learned update and consolidation policies
- long-context generalization from shorter training traces

#### Memory-use RL cluster

- `Yunpu Ma`
- `Volker Tresp`
- `Hinrich Schutze`
- `Sikuan Yan`

Why track them:

- `Memory-R1` is one of the cleanest recent examples of RL for explicit memory operations
- it pushes beyond static heuristics for add, update, delete, and retrieve

What they lead to:

- memory operation policies
- answer-agent and memory-manager separation
- low-data RL for memory control

#### Adaptive agent RL cluster

- `Jake Grigsby`
- `Linxi Fan`
- `Yuke Zhu`

Why track them:

- `AMAGO` is not a conversational memory system, but it is highly relevant for long-horizon adaptation, meta-learning, and memory under sparse rewards

What they lead to:

- adaptive long-horizon agents
- in-context RL
- memory under exploration pressure

### 5. Memory-OS and hierarchy researchers

This cluster is useful if we want the system to scale beyond a narrow benchmark engine.

#### MemoryOS cluster

- `Jiazheng Kang`
- `Mingming Ji`
- `Zhe Zhao`
- `Ting Bai`

Why track them:

- `MemoryOS` frames memory as a managed hierarchy for personalized agents
- that is useful for lifecycle thinking even if we do not adopt the full architecture

What they lead to:

- memory tiers
- lifecycle management
- personalization-aware memory organization

#### MemOS / Memory^3 / LightMem cluster

- `Zhiyu Li`
- `Shichao Song`
- `Ningyu Zhang`
- `Huajun Chen`
- `Wentao Zhang`
- `Feiyu Xiong`
- `Hongkang Yang`

Why track them:

- this cluster keeps recurring across `Memory^3`, `MemOS`, and `LightMem`
- that recurrence usually signals a lab worth following closely rather than a one-paper event

What they lead to:

- explicit memory outside model parameters
- memory operating systems
- lightweight memory pipelines
- high-efficiency memory design

### 6. Personalization and profile-memory researchers

This matters because user profile handling is one of the easiest places for memory systems to fail badly.

#### O-Mem cluster

- `Wangchunshu Zhou`
- `Piaohong Wang`
- `Motong Tian`

Why track them:

- `O-Mem` directly separates persona attributes from event context
- that is one of the most useful design ideas for personalized agent memory

What they lead to:

- active user profiling
- hierarchical retrieval for persona versus event memory
- personalization benchmarks such as `PERSONAMEM`

#### A-MEM cluster

- `Wujiang Xu`
- `Yongfeng Zhang`

Why track them:

- `A-MEM` is one of the clearest agentic-memory organization papers
- it is valuable when we want evolving links and memory-note structures without jumping immediately to full graph infrastructure

What they lead to:

- note-based memory evolution
- dynamic linking
- agentic indexing

#### SimpleMem cluster

- `Jiaqi Liu`
- `Huaxiu Yao`
- `Mingyu Ding`
- `Cihang Xie`

Why track them:

- `SimpleMem` is one of the strongest lightweight-first memory papers in the current sweep
- if we want benchmark wins with the lightest online path, this cluster matters a lot

What they lead to:

- semantic compression
- asynchronous consolidation
- adaptive retrieval scope

## Follow graph

If the goal is to discover adjacent researchers without scanning everything manually, these are the best chains to follow.

### Chain 1: benchmark-first conversational memory

`Di Wu` -> `LongMemEval` -> `Kai-Wei Chang` / `Dong Yu` / `Nanyun Peng` -> `Self-Routing RAG`

Use this when:

- we want benchmark-native retrieval ideas
- we want people working on time-aware or selective retrieval

### Chain 2: long-horizon conversation and evaluation realism

`Adyasha Maharana` -> `LoCoMo` -> Snap Research memory work  
`Egor Pakhomov` -> `ConvoMem` -> long-context versus memory transition points

Use this when:

- we want better evaluation design
- we want to avoid overfitting to only one benchmark philosophy

### Chain 3: temporal graph memory

`Preston Rasmussen` / `Daniel Chalef` -> `Zep` / `Graphiti` -> temporal retrieval and historical query handling

Use this when:

- we need better update handling
- we need provenance and contradiction logic

### Chain 4: memory plus retrieval science

`Yu Su` / `Michihiro Yasunaga` -> `HippoRAG`  
`Omar Khattab` -> `ColBERT` / `DSPy`  
`ChengXiang Zhai` / `Jiawei Han` -> `PlugMem`

Use this when:

- our bottleneck is retrieval precision
- we need better units of memory access than raw chunks

### Chain 5: memory-control learning

`Julian McAuley` / `Xiaojian Wu` -> `Mem-alpha`  
`Yunpu Ma` / `Volker Tresp` / `Hinrich Schutze` -> `Memory-R1`

Use this when:

- we are ready to train write and update policies instead of hand-coding them

### Chain 6: lightweight-first memory

`Ningyu Zhang` / `Huajun Chen` -> `Memory^3` -> `MemOS` -> `LightMem`  
`Jiaqi Liu` / `Huaxiu Yao` -> `SimpleMem`

Use this when:

- we want the best chance of benchmark leadership with the lightest online path

## Best labs and org feeds to watch on GitHub

These are the orgs or repos most worth checking weekly.

- `supermemoryai/supermemory`
  Reason: benchmark claims and retrieval architecture pressure from a frontier-facing product team.
- `supermemoryai/memorybench`
  Reason: benchmark harness and comparison surface.
- `snap-research/locomo`
  Reason: benchmark changes and evaluation definitions.
- `SalesforceAIResearch/ConvoMem` or the `Salesforce/ConvoMem` dataset page
  Reason: benchmark updates and evaluator assumptions.
- `xiaowu0162/LongMemEval`
  Reason: exact benchmark structure for the current most important target.
- `letta-ai/letta`
  Reason: stateful-agent memory abstractions and practical developer ergonomics.
- `getzep/graphiti`
  Reason: temporal graph memory and evolving relationships.
- `mem0ai/mem0`
  Reason: production memory patterns and benchmark-facing claims.
- `langchain-ai/langmem`
  Reason: hot-path versus background-memory design patterns.
- `OSU-NLP-Group/HippoRAG`
  Reason: graph retrieval and memory-inspired reasoning.
- `BAI-LAB/MemoryOS`
  Reason: memory-hierarchy ideas for personalized agents.
- `MemTensor/MemOS`
  Reason: memory lifecycle and system-resource framing.
- `agiresearch/A-mem`
  Reason: agentic organization and evolving note graphs.
- `aiming-lab/SimpleMem`
  Reason: lightweight-first compression and retrieval.
- `zjunlp/LightMem`
  Reason: strongest current signal for lightweight memory efficiency.
- `TIMAN-group/PlugMem`
  Reason: knowledge-centric memory graphs and task-agnostic memory.
- `nuster1128/MemEngine`
  Reason: fast implementation access to multiple memory patterns.
- `MemBench repo linked from the paper`
  Reason: broader evaluation dimensions for memory systems.

## Recommended priority watchlist for our chip

If we only monitor a small set tightly, this is the highest-value group for the next phase.

Tier 1:

- `Di Wu`
- `Kai-Wei Chang`
- `Dong Yu`
- `Adyasha Maharana`
- `Egor Pakhomov`
- `Preston Rasmussen`
- `Daniel Chalef`
- `Yu Su`
- `Omar Khattab`
- `Julian McAuley`
- `Yunpu Ma`
- `Ningyu Zhang`
- `Huajun Chen`
- `Wangchunshu Zhou`
- `Jiaqi Liu`

Why this set:

- it covers benchmark design, retrieval, temporal memory, profile memory, RL-based memory control, and lightweight-first system design

Tier 2:

- `Charles Packer`
- `Sarah Wooders`
- `Prateek Chhikara`
- `Akari Asai`
- `Hannaneh Hajishirzi`
- `Yuke Zhu`
- `ChengXiang Zhai`
- `Jiawei Han`
- `Wujiang Xu`

Why this set:

- it covers stateful agents, product memory layers, selective retrieval, adaptive RL, and agentic organization

## Implications for our build

The people map suggests five clear design truths.

1. Retrieval remains the bottleneck.
   The retrieval cluster is too strong and too recurrent to ignore.

2. Time and supersession are mandatory.
   Benchmark and system clusters converge on this.

3. Profile memory should stay distinct from event memory.
   `O-Mem` and `ConvoMem` make this especially clear.

4. Lightweight online paths are increasingly credible.
   `SimpleMem`, `LightMem`, and the `ConvoMem` findings all push in this direction.

5. RL for memory policy is now a real lane.
   `Mem-alpha` and `Memory-R1` mean the autoloop should eventually learn write and update policy, not only mutate prompts.

## Emerging 2026 radar

These are not yet the most established names in the space, but they are worth monitoring because they point toward where the field may move next.

### Benchmark pressure

- `Chuanrui Hu`
- `Jian Pei`
- `Yafeng Deng`

Reason:

- `EverMemBench` pushes memory evaluation toward multi-party, multi-group, million-token settings with profile and awareness components.

### Beyond-factual conversational memory

- `Yifei Li`
- `Jun Liu`

Reason:

- `LoCoMo-Plus` pushes beyond factual recall into latent constraint and cognitive-memory evaluation, which is exactly the sort of thing a benchmark-leading system will eventually need to handle.

### Personalized retrieval evolution

- `Yingyi Zhang`
- `Yong Liu`
- `Xiangyu Zhao`

Reason:

- `RF-Mem` is an interesting new retrieval direction because it separates fast familiarity from deeper recollection, which maps well onto lightweight-first memory routing.

### Surprise-gated memory evolution

- `Yuru Song`
- `Qi Xin`

Reason:

- `D-MEM` is one of the more interesting 2026 attempts to reduce memory cost by gating expensive restructuring behind a surprise or contradiction signal.

## Sources

- arXiv on categories and discovery: `https://arxiv.org/`
- `LongMemEval`: `https://arxiv.org/abs/2410.10813`, `https://github.com/xiaowu0162/LongMemEval`
- `LoCoMo`: `https://github.com/snap-research/locomo`
- `ConvoMem`: `https://arxiv.org/abs/2511.10523`, `https://huggingface.co/datasets/Salesforce/ConvoMem`
- `MemGPT`: `https://arxiv.org/abs/2310.08560`
- `Letta`: `https://github.com/letta-ai/letta`
- `Zep`: `https://arxiv.org/abs/2501.13956`
- `Graphiti`: `https://github.com/getzep/graphiti`
- `Mem0`: `https://arxiv.org/abs/2504.19413`
- `HippoRAG`: `https://arxiv.org/abs/2405.14831`
- `Self-RAG`: `https://arxiv.org/abs/2310.11511`
- `Self-Routing RAG`: `https://arxiv.org/abs/2504.01018`
- `ColBERT`: `https://arxiv.org/abs/2004.12832`
- `ColBERTv2`: `https://arxiv.org/abs/2112.01488`
- `DSPy`: `https://arxiv.org/abs/2310.03714`
- `AMAGO`: `https://arxiv.org/abs/2310.09971`
- `Mem-alpha`: `https://arxiv.org/abs/2509.25911`
- `Memory-R1`: `https://arxiv.org/abs/2508.19828`
- `MemoryOS`: `https://arxiv.org/abs/2506.06326`, `https://github.com/BAI-LAB/MemoryOS`
- `MemOS`: `https://arxiv.org/abs/2507.03724`, `https://github.com/MemTensor/MemOS`
- `Memory^3`: `https://arxiv.org/abs/2407.01178`
- `O-Mem`: `https://arxiv.org/abs/2511.13593`
- `A-MEM`: `https://arxiv.org/abs/2502.12110`, `https://github.com/agiresearch/A-mem`
- `SimpleMem`: `https://arxiv.org/abs/2601.02553`
- `LightMem`: `https://arxiv.org/abs/2510.18866`, `https://github.com/zjunlp/LightMem`
- `PlugMem`: `https://arxiv.org/abs/2603.03296`
- `MemEngine`: `https://arxiv.org/abs/2505.02099`
- `MemBench`: `https://arxiv.org/abs/2506.21605`
- `EverMemBench`: `https://arxiv.org/abs/2602.01313`
- `LoCoMo-Plus`: `https://arxiv.org/abs/2602.10715`
- `RF-Mem`: `https://arxiv.org/abs/2603.09250`
- `D-MEM`: `https://arxiv.org/abs/2603.14597`
