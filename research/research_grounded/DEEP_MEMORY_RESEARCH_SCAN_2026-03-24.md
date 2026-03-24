# Deep Memory Research Scan 2026-03-24

Status: research-grounded deep-cut scan

## Purpose

This memo extends the main landscape refresh with a deeper sweep across:

- paper-first memory systems that are not yet commoditized
- newer 2025-2026 memory benchmarks that may expose failure modes our current stack has not faced yet
- adjacent retrieval or storage substrates that are not memory systems by themselves but could matter later
- a deeper glossary for techniques that keep recurring across frontier memory work

This is not a claim that all systems below are real winners.
Some are strong ideas, some are paper-first claims, some are product surfaces, and some are infrastructure bets.
The point is to keep a broader and more honest option set available when the current winning lane stops being enough.

## Evidence rule

Keep four things separate:

1. paper claim
2. official repo or product surface
3. benchmark score pinned from a source
4. local reproduction in this repo

For this repo, the current local truth is still:

- best measured local lane: `observational_temporal_memory + MiniMax-M2.7`
- this is a benchmark lead on tested slices, not proof of a universal best architecture

## Deep-Cut Glossary

### System-1 retrieval

Fast similarity-style retrieval.
Usually embedding, keyword, or graph-neighbor based.
Great for cheap recall.
Weak when the right answer requires broad structural coverage instead of nearest-neighbor relevance.

### System-2 retrieval

Deliberate search over memory structure.
Often tree traversal, hierarchical routing, graph expansion, or planner-guided search.
Usually slower, but better for global reasoning.

### Global selection

A retrieval mode that explicitly tries to choose a globally coherent set of memories rather than the top few locally similar ones.
Important when many pieces of evidence must be jointly present.

### Episodic context reconstruction

Instead of only storing compressed facts, reconstruct a larger local episode around a candidate memory at answer time.
Useful when compression destroys causal flow.

### Topic continuity

The idea that adjacent turns can form a coherent topical segment whose meaning is lost if each turn is stored independently.
Likely important for long conversational memory.

### Dynamic topology evolution

An offline or background process that edits the memory graph itself by splitting, merging, updating, or relinking memory units.
Promising for lifelong memory without summary collapse.

### Selective forgetting

The system intentionally lets low-value or stale memory decay, merge, or disappear rather than preserving everything forever.
Important for scale, noise control, and realistic long-horizon agents.

### Evidence-anchored reward

A training signal that gives credit to the memory operations that produced the evidence actually used downstream.
Important for learning better memory management policies.

### Memory manager agent

A specialized controller whose job is not answering the user directly, but deciding what to write, merge, retrieve, forget, or surface.

### Topic loom

A storage-time mechanism that watches a sliding dialogue window and groups turns by evolving theme before retrieval ever happens.

### Knowledge vault

A separated store for stable, generalized knowledge distinct from live conversational memory.
Useful when procedural, semantic, and episodic memories should not all compete in one index.

### Bounded visible surface

A design where retrieval always starts from a small, stable visible set, then expands only if needed.
This matters for `BEAM`-like latency and token constraints.

## Research Families Worth Watching

| Family | Core move | Why it matters | Main risk |
|---|---|---|---|
| Hierarchical graph memory | store entities, relations, and semantic layers in a hierarchy | better temporal and multi-hop retrieval than flat stores | graph quality can drift and become expensive |
| Reflective structured memory | separate evidence, summaries, and beliefs | stronger traceability and less evidence/inference blur | reflection quality becomes a new failure point |
| Multi-agent memory control | specialized memory agents manage distinct stores | cleaner role separation, especially for multimodal or long-horizon tasks | orchestration cost and complexity |
| Lifelong topology editing | memory graph evolves via merge, split, update | better long-term maintenance than one-shot summarization | hard to validate offline edits safely |
| Selective forgetting | memory decays or is consolidated deliberately | necessary for scale and noise control | forgetting policy can discard future-critical details |
| RL-trained memory management | memory writes and retrieval are policy-learned | promising for long-horizon agents and adaptive control | benchmark overfitting and training complexity |
| Topic-continuity storage | group turns into topical episodes at write time | protects narrative and causal flow | topic segmentation errors can pollute retrieval |
| Episodic reconstruction | recall larger local episodes instead of only atoms | preserves causality for System-2 tasks | token cost if uncontrolled |
| Retrieval substrate innovation | better vector, graph, sparsification, or routing substrate | could improve memory search quality under scale | substrate hype can outpace memory QA evidence |

## Deep-Cut System Map

### `RuVector`

Type: retrieval substrate, not a full memory architecture.

Official surface:

- repo describes it as a self-learning vector graph neural network and database in Rust
- repo claims graph queries, self-optimizing routing, local model execution, and PostgreSQL integration
- repo says it powers `Cognitum`

Why it matters:

- if any of the graph plus self-learning retrieval claims hold up, it could become an interesting substrate for a future memory index rather than a memory system by itself
- the strongest possible fit for us would be as a lower-layer retrieval engine under a memory architecture that already handles temporal supersession and answer-bearing packet construction

What to borrow:

- not the marketing layer
- the idea of a memory substrate that can mix graph traversal, vector retrieval, and online adaptation
- any genuinely reproducible low-latency support for graph-aware retrieval

Cautions:

- current public surface is much stronger on systems claims than on memory-benchmark evidence
- there is no pinned `LoCoMo`, `LongMemEval_s`, or `BEAM` result to treat as proof of memory quality
- treat this as an infra exploration candidate, not a benchmark winner

License:

- repo surface says `MIT`

Primary sources:

- `https://github.com/ruvnet/RuVector`
- `https://raw.githubusercontent.com/ruvnet/RuVector/main/LICENSE`

### `MIRIX`

Type: multimodal multi-agent memory system.

Core idea:

- six memory types: `Core`, `Episodic`, `Semantic`, `Procedural`, `Resource`, `Knowledge Vault`
- memory agents manage different stores instead of collapsing everything into one flat memory layer
- designed for screen observation, multimodal capture, and local-first storage

Why it matters:

- one of the clearest 2025 pushes toward memory-role separation
- valuable if `BEAM`-style scale or multimodal pressure later breaks a single-store memory design

Pinned public evidence:

- paper claims `35%` higher accuracy than a RAG baseline on `ScreenshotVQA` while reducing storage by `99.9%`
- paper claims `85.4%` on `LoCoMo`

What to borrow:

- memory-type separation
- explicit procedural memory lane
- knowledge-vault idea for durable non-conversational knowledge
- local-first privacy posture for future product surfaces

Cautions:

- strong paper claims, but not reproduced here
- multimodal setup may hide substantial engineering overhead

License:

- repo and license file show `Apache-2.0`

Primary sources:

- `https://arxiv.org/abs/2507.07957`
- `https://github.com/Mirix-AI/MIRIX`
- `https://raw.githubusercontent.com/Mirix-AI/MIRIX/main/LICENSE`

### `Hindsight`

Type: reflective structured memory system.

Core idea:

- four logical networks separate world facts, agent experiences, entity summaries, and beliefs
- three operations: retain, recall, reflect
- aims to stop blurring evidence and inference

Why it matters:

- one of the strongest newer arguments for separating raw evidence from synthesized beliefs
- aligns closely with the pressure we already see in our own packeting: the answer improves when evidence and reflected abstraction are both present but not confused

Pinned public evidence:

- paper claims `83.6%` over a full-context `39%` baseline with the same open 20B model
- paper claims `91.4%` on `LongMemEval`
- paper claims up to `89.61%` on `LoCoMo`

What to borrow:

- evidence network versus belief network separation
- reflection as an explicit operation rather than an accidental byproduct
- traceable update path for changed information

Cautions:

- benchmark strength is compelling but still external to this repo
- belief layers can hallucinate if update discipline is weak

License:

- repo and license file show `MIT`

Primary sources:

- `https://arxiv.org/abs/2512.12818`
- `https://github.com/vectorize-io/hindsight`
- `https://raw.githubusercontent.com/vectorize-io/hindsight/main/LICENSE`

### `LiCoMemory`

Type: lightweight hierarchical graph memory.

Core idea:

- `CogniGraph` separates semantic indexing from graph structure
- uses temporal and hierarchy-aware search plus reranking
- claims to be lightweight relative to heavier graph systems

Why it matters:

- could be a better fit than full graph-heavy systems if we want stronger structure without jumping to a graph-database-first stack

Pinned public evidence:

- arXiv abstract claims outperformance on `LoCoMo` and `LongMemEval`
- repo presents the system as SOTA on QA accuracy and recall with lower latency and token consumption

What to borrow:

- lightweight hierarchical indexing
- time-aware reranking over entity-level and session-level signals
- graph structure without overcommitting to giant infra

Cautions:

- external claim quality looks promising, but numeric headline scores are not pinned in the abstract we reviewed
- repo does not clearly surface an `MIT` or `Apache-2.0` license on the page we reviewed

License:

- not clearly surfaced as `MIT` or `Apache-2.0` in the repo view reviewed during this scan

Primary sources:

- `https://arxiv.org/abs/2511.01448`
- `https://huggingface.co/papers/2511.01448`
- `https://github.com/EverM0re/LiCoMemory`

### `Mnemis`

Type: hierarchical graph memory with dual-route retrieval.

Core idea:

- `System-1` similarity search over a base graph
- `System-2` global selection over a hierarchical graph
- explicitly designed to beat flat similarity retrieval on globally structured questions

Why it matters:

- this is one of the sharpest recent architectural answers to the weakness of top-k similarity retrieval
- if our current lane starts failing on multi-hop or broader evidence coverage, this is a serious direction

Pinned public evidence:

- paper claims `93.9` on `LoCoMo`
- paper claims `91.6` on `LongMemEval-S`
- repo repeats the same figures and notes implementation on top of `Graphiti`

What to borrow:

- dual-route retrieval
- global selection as an explicit retrieval mode
- top-down traversal over memory hierarchies

Cautions:

- graph extraction quality is critical
- system can become expensive if System-2 search is overused

License:

- repo surface shows `MIT`

Primary sources:

- `https://arxiv.org/abs/2602.15313`
- `https://github.com/microsoft/Mnemis`
- `https://raw.githubusercontent.com/microsoft/Mnemis/main/LICENSE`

### `All-Mem`

Type: lifelong memory with dynamic topology editing.

Core idea:

- online bounded visible surface for cheap retrieval
- offline diagnoser proposes `SPLIT`, `MERGE`, and `UPDATE` edits
- immutable evidence remains available for traceability

Why it matters:

- this is one of the clearest newer answers to the question: how do you keep memory healthy over very long horizons without destroying evidence through summary collapse?

Pinned public evidence:

- paper reports improved retrieval and QA on `LoCoMo` and `LongMemEval`
- no exact scalar was pinned from the abstract we reviewed

What to borrow:

- non-destructive consolidation
- bounded visible surface
- explicit topology edits as an offline maintenance operation

Cautions:

- offline editor quality is a new failure surface
- requires stricter auditability than simple summarization

Primary source:

- `https://arxiv.org/abs/2603.19595`

### `FadeMem`

Type: selective-forgetting memory system.

Core idea:

- dual-layer memory hierarchy with adaptive decay
- retention depends on relevance, access frequency, and temporal patterns
- conflict resolution plus memory fusion

Why it matters:

- selective forgetting is likely unavoidable under `BEAM`-like scale
- this is a strong reminder that “store everything” is not a complete doctrine

Pinned public evidence:

- paper claims better multi-hop reasoning and retrieval on `Multi-Session Chat`, `LoCoMo`, and `LTI-Bench`
- paper claims `45%` storage reduction

What to borrow:

- explicit forgetting policy
- decay and fusion as first-class operations
- storage budget discipline

Cautions:

- forgetting errors are hard to notice until much later
- likely dangerous unless paired with immutable evidence or rehydration

Primary source:

- `https://arxiv.org/abs/2601.18642`

### `Membox`

Type: topic-continuity memory architecture.

Core idea:

- `Topic Loom` groups adjacent same-topic turns into coherent memory boxes at write time
- `Trace Weaver` links boxes into longer event traces

Why it matters:

- this directly attacks a real weakness of turn-by-turn memory extraction
- especially relevant for `LoCoMo`, where temporal and narrative continuity matter

Pinned public evidence:

- paper claims up to `68%` F1 improvement on temporal reasoning in `LoCoMo`
- paper claims lower context-token usage than baselines

What to borrow:

- storage-time topic segmentation
- preserving short narrative arcs before atomization
- event-trace linking

Cautions:

- topic segmentation mistakes can pollute whole memory boxes
- may work better as an optional write-time transform, not the only storage mode

Primary source:

- `https://arxiv.org/abs/2601.03785`

### `E-mem`

Type: episodic context reconstruction system.

Core idea:

- assistant agents preserve uncompressed episodic context
- a master agent coordinates which episode fragments activate
- local reasoning happens inside activated segments before evidence is aggregated

Why it matters:

- strong answer to the failure mode where heavy preprocessing destroys the exact evidence chain needed for harder reasoning

Pinned public evidence:

- paper claims over `54%` F1 on `LoCoMo`
- paper claims `7.75%` better than `GAM`
- paper claims over `70%` token-cost reduction

What to borrow:

- targeted episodic rehydration
- assistant-local reasoning on activated evidence
- “preprocess less, reconstruct more” discipline

Cautions:

- can become expensive if many episodes activate
- requires tight routing or it degenerates into prompt sprawl

Primary source:

- `https://arxiv.org/abs/2601.21714`

### `Fine-Mem`

Type: memory-management training framework.

Core idea:

- chunk-level step rewards
- evidence-anchored reward attribution
- aligns local memory operations with downstream utility

Why it matters:

- if we later train or tune a memory controller rather than hand-designing it, this is one of the most relevant recent methods

Pinned public evidence:

- paper reports consistent wins on `Memalpha` and `MemoryAgentBench`
- no single benchmark scalar was pinned from the abstract we reviewed

What to borrow:

- evidence-anchored credit assignment
- reward shaping around memory operations, not only final task score

Cautions:

- this is a training-framework idea, not an immediately deployable memory system
- risk of overfitting to benchmark-specific reward structure

Primary sources:

- `https://arxiv.org/abs/2601.08435`
- `https://huggingface.co/papers/2601.08435`

### `MemEvolve` and `EvolveLab`

Type: meta-evolution framework and design-space substrate.

Core idea:

- jointly evolve agent experience and memory architecture
- distill many existing systems into a modular space: `encode`, `store`, `retrieve`, `manage`

Why it matters:

- useful for search over memory doctrine itself, not just memory contents
- especially relevant if we want our benchmark loop to become architecture-search rather than single-lane tuning

Pinned public evidence:

- paper claims up to `17.06%` gains over strong agent frameworks

What to borrow:

- design-space framing
- modular decomposition of memory systems
- meta-search over architecture, not only parameter values

Cautions:

- easily becomes too large and abstract for near-term benchmark iteration
- use as research framing first, not immediate implementation doctrine

Primary sources:

- `https://arxiv.org/abs/2512.18746`
- `https://huggingface.co/papers/2512.18746`

### `MemEngine`

Type: research implementation substrate.

Core idea:

- unified modular library that implements many memory models under one framework

Why it matters:

- good reference surface for memory operations, function boundaries, and comparative implementation structure
- useful as a sanity check when deciding how to modularize our own next-generation memory substrate

Pinned public evidence:

- not a benchmark winner claim
- main value is implementation breadth and modularity

What to borrow:

- clearer separation between memory operations and memory models
- easier swapability between write, retrieve, optimize, and display layers

Cautions:

- framework breadth is not the same as benchmark strength

Primary sources:

- `https://arxiv.org/abs/2505.02099`
- `https://github.com/nuster1128/MemEngine`

## Benchmark Innovations We Should Track

### `MemoryAgentBench`

What it adds:

- focuses on four competencies: accurate retrieval, test-time learning, long-range understanding, and selective forgetting
- evaluates memory in incremental multi-turn form rather than static long-context QA only

Why it matters:

- good pressure test for memory managers and forgetting policies
- more aligned with long-lived agent behavior than pure offline QA

Primary sources:

- `https://arxiv.org/abs/2507.05257`
- `https://huggingface.co/papers/2507.05257`

### `MemoryArena`

What it adds:

- interdependent multi-session agentic tasks
- memory acquisition and action are coupled instead of benchmarked separately

Why it matters:

- explicitly shows that near-saturated `LoCoMo` performance does not mean the agent actually uses memory well in action loops
- strong candidate for the next benchmark layer after `BEAM`

Primary sources:

- `https://arxiv.org/abs/2602.16313`
- `https://huggingface.co/papers/2602.16313`

### `RealMem`

What it adds:

- project-oriented memory benchmark instead of casual conversation only
- realistic evolving goals, schedules, and longer project states

Why it matters:

- may expose a weakness in systems that remember facts but not evolving project state

License on official benchmark repo:

- `Apache-2.0`

Primary sources:

- `https://arxiv.org/abs/2601.06966`
- `https://github.com/AvatarMemory/RealMemBench`
- `https://raw.githubusercontent.com/AvatarMemory/RealMemBench/main/LICENSE`

### `M3-Agent` and `M3-Bench`

What it adds:

- multimodal long-term memory with entity-centric episodic and semantic memory
- benchmark pressure on long-video and multimodal recall, not just text conversation

Why it matters:

- if our future memory chip wants to leave pure text behind, this is a serious direction

Pinned public evidence:

- paper claims `6.7%`, `7.7%`, and `5.3%` accuracy gains over the strongest prompting baseline across its benchmark splits

Primary source:

- `https://arxiv.org/abs/2508.09736`

## Company or Product Surface Reality

The newer and deeper the paper, the less likely there is a real production surface yet.
That matters because benchmark strength and deployability are different things.

| System | Public product or company surface | Honest read |
|---|---|---|
| `RuVector` | repo claims it powers `Cognitum` | interesting substrate bet, but not memory-benchmark proof |
| `MIRIX` | packaged assistant and dashboard with local storage | strongest productized multimodal memory surface in this scan |
| `Hindsight` | open-source memory system, cloud surface, repo claims Fortune 500 production use | plausible strong productization path, but repo usage claim is still external |
| `Mnemis` | research repo from Microsoft | clearly research-first |
| `LiCoMemory` | research repo | research-first |
| `All-Mem` | paper-first | research-first |
| `FadeMem` | paper-first | research-first |
| `Membox` | paper-first | research-first |
| `E-mem` | paper-first | research-first |
| `Fine-Mem` | paper-first | training-framework idea, not product surface |
| `MemEvolve` | paper-first | research program, not production memory surface |
| `MemEngine` | open-source library | useful research substrate, not evidence of a winning memory model |

## What Looks Most Useful For Our Chip

### Highest-value borrow candidates

1. `Hindsight`
   - reason: evidence network versus belief network separation directly matches a real local pain point
2. `Mnemis`
   - reason: dual-route retrieval is one of the strongest concrete answers to top-k similarity weakness
3. `All-Mem`
   - reason: offline topology edits are a serious candidate for `BEAM`-style memory upkeep
4. `Membox`
   - reason: topic continuity is probably under-modeled in our current write path
5. `FadeMem`
   - reason: selective forgetting will matter once memory volume grows
6. `MIRIX`
   - reason: memory-role separation and knowledge-vault thinking are useful beyond multimodal work
7. `E-mem`
   - reason: episodic reconstruction is a useful hedge against over-compression

### Useful but second-order

- `RuVector`
  - substrate candidate, not a direct memory architecture
- `Fine-Mem`
  - more useful once we are ready to train memory control policies
- `MemEvolve`
  - more useful once our benchmark loop becomes architecture search
- `MemEngine`
  - best as an implementation reference and comparative substrate

## Practical Research Doctrine From This Scan

1. Preserve immutable evidence even when adding reflections, beliefs, or merged memories.
2. Separate profile, event, procedure, and semantic knowledge more aggressively under harder scale.
3. Add a second retrieval mode for global or structured selection instead of relying only on local similarity.
4. Treat storage-time segmentation as a first-class design space, not just retrieval-time reranking.
5. Add offline maintenance lanes before turning to heavier online orchestration.
6. Expect future benchmarks to reward memory-use-in-action, not only offline recall.
7. Treat retrieval substrate bets like `RuVector` as optional lower-layer experiments, not memory-system doctrine.

## Immediate Follow-Up Options

If we want to turn this research into code, the cleanest order is:

1. add a `topic continuity` write-path experiment inspired by `Membox`
2. add a `dual-route retrieval` experiment inspired by `Mnemis`
3. add an `evidence vs belief` packet split inspired by `Hindsight`
4. add an `offline merge/split/update` maintenance experiment inspired by `All-Mem`
5. add a bounded `forgetting / decay` lane inspired by `FadeMem`

## Sources

- RuVector repo: `https://github.com/ruvnet/RuVector`
- RuVector license: `https://raw.githubusercontent.com/ruvnet/RuVector/main/LICENSE`
- MIRIX paper: `https://arxiv.org/abs/2507.07957`
- MIRIX repo: `https://github.com/Mirix-AI/MIRIX`
- MIRIX license: `https://raw.githubusercontent.com/Mirix-AI/MIRIX/main/LICENSE`
- Hindsight paper: `https://arxiv.org/abs/2512.12818`
- Hindsight repo: `https://github.com/vectorize-io/hindsight`
- Hindsight license: `https://raw.githubusercontent.com/vectorize-io/hindsight/main/LICENSE`
- LiCoMemory paper: `https://arxiv.org/abs/2511.01448`
- LiCoMemory paper page: `https://huggingface.co/papers/2511.01448`
- LiCoMemory repo: `https://github.com/EverM0re/LiCoMemory`
- Mnemis paper: `https://arxiv.org/abs/2602.15313`
- Mnemis repo: `https://github.com/microsoft/Mnemis`
- Mnemis license: `https://raw.githubusercontent.com/microsoft/Mnemis/main/LICENSE`
- All-Mem paper: `https://arxiv.org/abs/2603.19595`
- FadeMem paper: `https://arxiv.org/abs/2601.18642`
- Membox paper: `https://arxiv.org/abs/2601.03785`
- E-mem paper: `https://arxiv.org/abs/2601.21714`
- Fine-Mem paper: `https://arxiv.org/abs/2601.08435`
- Fine-Mem paper page: `https://huggingface.co/papers/2601.08435`
- MemEvolve paper: `https://arxiv.org/abs/2512.18746`
- MemEvolve paper page: `https://huggingface.co/papers/2512.18746`
- MemEngine paper: `https://arxiv.org/abs/2505.02099`
- MemEngine repo: `https://github.com/nuster1128/MemEngine`
- MemoryAgentBench paper: `https://arxiv.org/abs/2507.05257`
- MemoryAgentBench paper page: `https://huggingface.co/papers/2507.05257`
- MemoryArena paper: `https://arxiv.org/abs/2602.16313`
- MemoryArena paper page: `https://huggingface.co/papers/2602.16313`
- RealMem paper: `https://arxiv.org/abs/2601.06966`
- RealMem benchmark repo: `https://github.com/AvatarMemory/RealMemBench`
- RealMem license: `https://raw.githubusercontent.com/AvatarMemory/RealMemBench/main/LICENSE`
- M3-Agent paper: `https://arxiv.org/abs/2508.09736`
