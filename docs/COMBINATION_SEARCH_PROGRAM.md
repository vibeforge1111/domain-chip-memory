# Combination Search Program

Date: 2026-03-22
Status: active

## Purpose

The memory chip should not test components only in isolation.
It should also test combinations.

But it should not turn combination search into random architecture sprawl.

This document defines:

- which combinations are likely to matter
- which combinations are likely to be wasteful
- how to test combinations while keeping the online path lightweight

## Core doctrine

The right way to search combinations is:

1. lock a strong lightweight baseline
2. mutate one additional capability family at a time
3. measure the combination against the exact baseline it extends
4. keep the combination only if the benchmark gain is worth the added complexity

This means combinations are not free.
Every added component must buy score, robustness, or both.

## V1 component families

These are the main parts we can combine.

1. `EPI`
   Raw episodic store with source provenance.
2. `ATOM`
   Semantic memory atoms for facts, preferences, events, and relations.
3. `TIME`
   Temporal fields and supersession logic.
4. `PROFILE`
   Compact stable profile or persona memory.
5. `ROUTE`
   Query-aware retrieval router.
6. `REHYDRATE`
   Source evidence rehydration after candidate selection.
7. `ABSTAIN`
   Explicit abstention or low-confidence policy.
8. `CONSOLIDATE`
   Offline dedupe, profile refresh, and memory merging.
9. `RELATE`
   Relation expansion across linked atoms.
10. `GRAPH`
   Materialized graph index or graph DB.
11. `SEARCH-AGENT`
   Online search-agent orchestration.
12. `ANSWER-ENSEMBLE`
   Multi-answer voting or judge aggregation.
13. `RL-POLICY`
   Learned memory-write or retrieval policy.

## Combination principles

### 1. Start with complements, not substitutes

Good combinations usually pair:

- one compact retrieval unit
- one disambiguation mechanism
- one selective-routing mechanism

Example:

- `ATOM + TIME + ROUTE`

Bad early combinations usually stack multiple expensive mechanisms that solve the same problem twice.

Example:

- `SEARCH-AGENT + GRAPH + ANSWER-ENSEMBLE`

### 2. Keep online and offline roles separate

Good combinations:

- light online retrieval plus heavier offline consolidation

Bad combinations:

- multiple heavyweight online reasoning layers on every query

### 3. Benchmark slices should decide combinations

Choose combinations by failure bucket:

- stale-fact miss -> add `TIME`
- preference miss -> add `PROFILE`
- multi-hop miss -> add `RELATE`
- over-answering -> add `ABSTAIN`
- short-history underperformance -> strengthen `ROUTE` to preserve the full-context path

## Best first combinations

These are the highest-priority combinations to test.

### Combo A: `EPI + ATOM`

Why:

- strongest simple baseline
- raw provenance plus compact retrieval unit

Likely benefit:

- better than raw full-history retrieval for direct fact recall

Main risk:

- stale fact collisions without time logic

### Combo B: `EPI + ATOM + TIME`

Why:

- this is the most defensible V1 core
- directly targets `LongMemEval`

Likely benefit:

- major gain on changing facts and temporal reasoning

Main risk:

- implementation complexity rises if time semantics are sloppy

### Combo C: `EPI + ATOM + TIME + ROUTE`

Why:

- preserves a lightweight path while avoiding retrieval overuse
- directly addresses shadow slices where full context may still win

Likely benefit:

- better performance across mixed history lengths

Main risk:

- route policy can become brittle if question typing is weak

### Combo D: `EPI + ATOM + TIME + PROFILE + ROUTE`

Why:

- likely strongest lightweight combination for user facts and preferences

Likely benefit:

- better personalization while keeping event memory separate

Main risk:

- profile pollution from transient facts

### Combo E: `EPI + ATOM + TIME + ROUTE + REHYDRATE`

Why:

- keeps candidate units compact but recovers nuance when needed

Likely benefit:

- better answer faithfulness without retrieving too much too early

Main risk:

- rehydration may negate token savings if triggered too aggressively

### Combo F: `EPI + ATOM + TIME + ROUTE + ABSTAIN`

Why:

- the `ConvoMem` shadow and `LongMemEval` both punish wrong confident answers

Likely benefit:

- improved abstention and reduced hallucinated recall

Main risk:

- over-abstention can suppress otherwise correct answers

### Combo G: `EPI + ATOM + TIME + PROFILE + ROUTE + REHYDRATE + ABSTAIN`

Why:

- best current candidate for the first “serious” benchmark-ready lightweight stack

Likely benefit:

- strong cross-benchmark balance without large online orchestration

Main risk:

- routing and threshold tuning become the main failure point

## Second-wave combinations

These should only be tested after the first lightweight stack plateaus.

### Combo H: `G + RELATE`

Why:

- relation expansion can help multi-hop and long-range QA

When to try:

- after repeated multi-hop misses remain on `LoCoMo`

### Combo I: `G + CONSOLIDATE`

Why:

- improves long-run density without bloating the hot path

When to try:

- after memory redundancy or profile drift becomes visible

### Combo J: `G + RELATE + CONSOLIDATE`

Why:

- likely strongest “still-lightweight” second-wave architecture

When to try:

- only after G is measured and stable

## Heavy combinations to treat skeptically

These are not banned forever.
They are just guilty until proven necessary.

### Skeptical Combo 1: `GRAPH + SEARCH-AGENT`

Risk:

- retrieval complexity explosion before the lightweight baseline is exhausted

### Skeptical Combo 2: `SEARCH-AGENT + ANSWER-ENSEMBLE`

Risk:

- online token and latency blow-up

### Skeptical Combo 3: `GRAPH + SEARCH-AGENT + ANSWER-ENSEMBLE`

Risk:

- architecture theater
- very hard to attribute gains cleanly

### Skeptical Combo 4: `RL-POLICY + weak heuristic baseline`

Risk:

- learning noise over an underdesigned system

## Combination testing method

Every combination experiment should specify:

1. parent baseline
2. added component or components
3. benchmark target
4. target failure slice
5. online cost delta
6. token delta
7. latency delta
8. keep or rollback rule

Recommended order:

1. full context
2. `EPI + ATOM`
3. `EPI + ATOM + TIME`
4. `EPI + ATOM + TIME + ROUTE`
5. `EPI + ATOM + TIME + PROFILE + ROUTE`
6. `EPI + ATOM + TIME + ROUTE + REHYDRATE`
7. `EPI + ATOM + TIME + ROUTE + ABSTAIN`
8. `G`
9. `G + RELATE`
10. `G + CONSOLIDATE`

## Cost discipline

Any new combination should be judged with three questions.

1. Does it raise the relevant benchmark slice?
2. Does it avoid regressing the other slices materially?
3. Is the gain large enough to justify the extra online cost?

If the answer to question 3 is no, the combination is not a keeper even if it improves accuracy slightly.

## What the best systems teach us

The current frontier systems suggest these reusable combination lessons.

### Supermemory lesson

- `ATOM + TIME + hybrid retrieval + source rehydration` is a real frontier pattern

### ConvoMem lesson

- `ROUTE` matters because memory retrieval is not always the right move

### GoodAI LTM Benchmark lesson

- the stack must remain stable under very long memory spans and dynamic memory upkeep, not only under benchmark-specific QA formats

### SimpleMem and LightMem lesson

- `compact retrieval units + offline consolidation` is one of the best ways to stay lightweight

### O-Mem lesson

- `PROFILE + event memory separation` is useful, especially for personalization-heavy questions

### Graphiti and A-Mem lesson

- relation structure helps, but it should be added only after the core temporal-semantic stack is measured

## Recommendation

The main search frontier for this chip should be:

1. lightweight temporal-semantic combinations first
2. relation and consolidation combinations second
3. heavyweight online orchestration only if the lighter combinations plateau below the target frontier

## Sources

- `Supermemory`: `https://supermemory.ai/research/`, `https://github.com/supermemoryai/supermemory`
- `LongMemEval`: `https://arxiv.org/abs/2410.10813`, `https://github.com/xiaowu0162/LongMemEval`
- `LoCoMo`: `https://github.com/snap-research/locomo`
- `GoodAI LTM Benchmark`: `https://github.com/GoodAI/goodai-ltm-benchmark`
- `ConvoMem`: `https://arxiv.org/abs/2511.10523`, `https://huggingface.co/datasets/Salesforce/ConvoMem`
- `Mem0`: `https://arxiv.org/abs/2504.19413`
- `Graphiti`: `https://github.com/getzep/graphiti`
- `A-Mem`: `https://arxiv.org/abs/2502.12110`
- `O-Mem`: `https://arxiv.org/abs/2511.13593`
- `SimpleMem`: `https://arxiv.org/abs/2601.02553`
- `LightMem`: `https://arxiv.org/abs/2510.18866`
- `RF-Mem`: `https://arxiv.org/abs/2603.09250`
- `D-MEM`: `https://arxiv.org/abs/2603.14597`
