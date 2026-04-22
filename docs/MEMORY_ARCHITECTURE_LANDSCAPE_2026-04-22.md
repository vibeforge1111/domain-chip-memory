# Memory Architecture Landscape

Date: 2026-04-22

This memo summarizes a repo-first research pass across open memory systems that are relevant to Spark's conversational memory problem, especially LoCoMo-style multi-party chat memory.

The goal is not to copy a leaderboard blindly. The goal is to identify which architectural ideas actually appear in source code, which ones plausibly drive LoCoMo gains, and which ones map cleanly into `domain-chip-memory`.

## Systems Reviewed

- Graphiti / Zep
  - Repo: `https://github.com/getzep/graphiti`
  - Local source inspected:
    - `graphiti/README.md`
    - `graphiti/graphiti_core/graphiti.py`
- Mem0
  - Repo: `https://github.com/mem0ai/mem0`
  - Local source/docs inspected:
    - `mem0/docs/changelog/highlights.mdx`
    - `mem0/docs/migration/oss-v2-to-v3.mdx`
    - `mem0/mem0/memory/main.py`
    - `mem0/mem0/utils/scoring.py`
    - `mem0/mem0/utils/entity_extraction.py`
    - `mem0/mem0/vector_stores/qdrant.py`
- SimpleMem
  - Repo: `https://github.com/aiming-lab/SimpleMem`
  - Local source/docs inspected:
    - `simplemem/README.md`
    - `simplemem/core/hybrid_retriever.py`
    - `simplemem/cross/README.md`
- LightMem / StructMem
  - Repo: `https://github.com/zjunlp/LightMem`
  - Local source/docs inspected:
    - `lightmem/StructMem.md`
    - `lightmem/experiments/locomo/readme.md`
    - `lightmem/experiments/locomo/prompts.py`

## Executive Read

There is no single SOTA memory architecture. The better systems separate memory into layers:

- raw provenance / episodes
- typed extraction
- entity or symbolic structure
- temporal handling
- multi-signal retrieval
- answer-time projection

That matches what LoCoMo is punishing in our current system. Summary-only retrieval is not enough for conversational memory.

The strongest reusable ideas for Spark are:

- Graphiti: temporal facts with provenance and validity windows
- Mem0: ADD-only extraction plus hybrid retrieval and entity linking
- SimpleMem: retrieval planning and semantic + lexical + symbolic fusion
- StructMem: event-level extraction and cross-event summarization

## What Each System Actually Does

## Graphiti / Zep

Graphiti is the clearest open reference for a temporal graph memory system.

What the repo shows:

- `README.md` defines a context graph as:
  - entities
  - facts / relationships with validity windows
  - episodes as provenance
  - optional custom ontology types
- `graphiti_core/graphiti.py` wires:
  - graph driver
  - LLM client
  - embedder
  - cross-encoder reranker
  - search recipes such as:
    - `COMBINED_HYBRID_SEARCH_CROSS_ENCODER`
    - `EDGE_HYBRID_SEARCH_NODE_DISTANCE`
    - `EDGE_HYBRID_SEARCH_RRF`
- The README explicitly claims:
  - incremental graph construction
  - fact invalidation instead of deletion
  - hybrid retrieval across semantic, keyword, and graph traversal
  - historical queries over what was true at different times

What matters for us:

- Graphiti treats conversational memory as a graph of evolving facts, not as one merged summary.
- Episodes are first-class provenance. Derived memory always traces back to raw support.
- It has a real notion of temporal history, not just timestamps attached to snippets.

What to steal:

- typed entity / fact / episode separation
- temporal validity windows
- provenance-first storage
- graph retrieval as a distinct lane, not as a post-processing trick

What not to copy blindly:

- full graph-database-first runtime for every memory query
- heavy ontology work before we have cleaner write-time extraction

Best lesson:

- Graphiti is the best reference for how conversational memory should be structured once facts are worth promoting.

## Mem0

Mem0's latest OSS design is more interesting than many people assume. The repo/docs show that the current direction is not "graph everything."

What the repo/docs show:

- `docs/changelog/highlights.mdx` claims:
  - LoCoMo `71.4 -> 91.6`
  - LongMemEval `67.8 -> 93.4`
  - ADD-only extraction
  - hybrid retrieval
  - entity linking
- `docs/migration/oss-v2-to-v3.mdx` explicitly says:
  - extraction is now single-pass ADD-only
  - retrieval is semantic + BM25 + entity matching
  - graph memory was removed from OSS
- `mem0/utils/scoring.py` contains hybrid scoring that combines:
  - semantic
  - BM25
  - entity boost
- `mem0/utils/entity_extraction.py` and the changelog show entity extraction / linking as a real pipeline component
- `mem0/vector_stores/qdrant.py` shows concrete support for:
  - dense vectors
  - BM25 sparse vectors
  - collection-level hybrid search behavior

What matters for us:

- Mem0 is strongest on practical memory engineering:
  - keep writes simple
  - keep old facts
  - use entity linking
  - fuse retrieval signals
- Their newest OSS architecture improved LoCoMo without leaning on graph traversal as the core retrieval primitive.

What to steal:

- ADD-only extraction for conversational facts
- entity linking as a first-class retrieval signal
- hybrid score fusion
- BM25 / lexical support instead of pure embedding dependence

What not to copy blindly:

- dropping explicit typed temporal graph structure in our case

Reason:

- Spark's target problem is Telegram-style social memory.
- We need relation and temporal querying more directly than Mem0 OSS currently exposes.

Best lesson:

- Mem0 is the best reference for our write path and rank fusion.

## SimpleMem

SimpleMem is important because its repo is unusually explicit about what it thinks drives LoCoMo gains.

What the repo shows:

- `README.md` reports:
  - LoCoMo-10 with GPT-4.1-mini:
    - SimpleMem `43.24 F1`
    - Mem0 `34.20 F1`
  - Cross-session SimpleMem:
    - `48` vs Claude-Mem `29.3`
  - Omni-SimpleMem:
    - LoCoMo `0.613 F1`
- The README describes text memory as:
  - semantic structured compression
  - memory units indexed in three layers:
    - semantic
    - lexical
    - symbolic metadata
- `core/hybrid_retriever.py` is the key file:
  - query analysis
  - retrieval planning
  - semantic search
  - keyword search
  - structured search
  - dedup / merge
  - optional reflection rounds
- `cross/README.md` shows the cross-session system:
  - session manager
  - context injector
  - consolidation worker
  - vector store with semantic, keyword, and structured metadata
  - provenance fields

What matters for us:

- SimpleMem is not just "better embeddings."
- It is explicitly:
  - compact memory units
  - hybrid retrieval
  - symbolic metadata
  - retrieval planning

What to steal:

- query planning before retrieval
- semantic + lexical + structured retrieval lanes
- provenance-preserving compact memory units
- consolidation as a separate phase

What not to copy blindly:

- reflection-heavy retrieval loops in the hot path

Reason:

- Spark needs fast operational memory, not repeated LLM retrieval loops for every query.

Best lesson:

- SimpleMem is the strongest reference for query-time planning and retrieval fusion.

## LightMem / StructMem

LightMem itself is useful, but StructMem is the more relevant part for LoCoMo.

What the repo shows:

- `StructMem.md` defines:
  - event-level extraction
  - factual components
  - relational components
  - temporal binding
  - cross-event summarization
- `experiments/locomo/readme.md` includes:
  - LightMem LoCoMo results in the high 40s F1 range
  - StructMem ablation showing:
    - `flat` extraction
    - `event` extraction
    - `event + summary`
  - the best row in the shown ablation is `event + summary`

What matters for us:

- This is the cleanest open evidence that event-structured extraction plus summary memory helps LoCoMo.
- It supports our current additive direction:
  - keep summary memory
  - add event structure

What to steal:

- event extraction mode
- separate factual and relational extraction prompts
- cross-event summary layer as its own store

What not to copy blindly:

- benchmark-specific extraction prompts without generalizing them into reusable typed schemas

Best lesson:

- StructMem is the best reference for why summary memory and event memory should coexist.

## Comparative Read

If we simplify the landscape:

- Graphiti solves: temporal graph memory
- Mem0 solves: write-time extraction + hybrid retrieval + entity linking
- SimpleMem solves: query planning + multi-lane retrieval
- StructMem solves: event extraction + cross-event summarization

Those are complementary, not contradictory.

## Why They Beat Summary-Only Systems On LoCoMo

The common pattern is:

- they do not rely on a single compressed summary representation
- they preserve provenance
- they preserve typed structure
- they use multiple retrieval signals
- they separate write-time structuring from answer-time generation

LoCoMo especially rewards:

- relation tracking
- temporal anchoring
- exact fact recall
- event linking
- support for abstention / uncertainty

That is why our current path is directionally right, but still incomplete.

## What Spark Should Build

The best additive design for `domain-chip-memory` is:

1. Keep `summary_synthesis_memory` as the backbone.
2. Keep raw conversational episode retention.
3. Expand typed write-time extraction.
4. Build an entity + temporal graph sidecar.
5. Add retrieval fusion across:
   - summary
   - exact turn
   - graph
   - temporal
   - lexical / BM25
6. Project typed graph hits into clean answer candidates.

That last point is a missing layer today. We already extract:

- alias bindings
- commitments
- reported speech
- negation
- unknown
- temporal events

But the provider often still sees raw support text instead of a normalized answer value.

That is below the bar set by the better systems.

## Concrete Architecture Delta From Today

Current Spark/domain direction:

- good:
  - summary backbone
  - typed conversational sidecar
  - exact-turn shadow retrieval
  - typed graph shadow retrieval
  - provenance preserved
- weak:
  - no real retrieval fusion at runtime
  - no lexical lane
  - no temporal validity windows
  - no mature entity linking
  - weak answer projection from typed hits

## Recommended Next Build Order

1. Typed answer projection
- turn graph hits into normalized answer candidates
- examples:
  - alias binding -> `Jo`
  - reported speech -> reported content only
  - negation -> `No`
  - unknown -> `unknown`
  - temporal event -> normalized time answer

2. Retrieval fusion
- add lexical retrieval and entity-linked boosts
- fuse:
  - summary score
  - graph score
  - exact-turn score
  - lexical score

3. Stronger entity linking
- explicit alias / canonical person resolution
- cross-turn pronoun carryover
- relation normalization across `mom`, `mother`, `her mother`

4. Temporal validity
- facts should support:
  - valid from
  - valid until
  - superseded by
- avoid flattening old and new facts into one current-state summary

5. Cross-event synthesis
- keep a separate summary layer generated from related event clusters
- do not collapse event memory into the only memory layer

## What Not To Do

- do not replace `summary_synthesis_memory`
- do not overfit to a handful of LoCoMo questions with bespoke answer heuristics
- do not move everything into a graph runtime before write-time structure and answer projection are clean

## Practical Conclusion

The best external architectural inspiration is:

- Graphiti for memory shape
- Mem0 for write path and retrieval fusion
- SimpleMem for retrieval planning
- StructMem for event extraction plus summary coexistence

Spark should become a hybrid of those ideas, not a clone of any single repo.

The highest-yield next step remains:

- finish typed answer projection from graph memory
- then add lexical + entity-linked hybrid retrieval

That should improve LoCoMo and production Telegram memory at the same time.
