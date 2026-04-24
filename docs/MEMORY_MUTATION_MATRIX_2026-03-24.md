# Memory Mutation Matrix 2026-03-24

Status: active execution matrix

## Purpose

This document turns the research scans into a benchmark-facing mutation queue.

It is not a list of interesting ideas.
It is a map from:

- benchmark pressure
- expected failure signature
- candidate memory mutation
- implementation surface
- regression risk
- promotion criteria

## Hard rules

1. `LongMemEval_s` and `LoCoMo` stay as regression gates.
2. `BEAM` is the frontier architecture target, not an excuse to break simpler wins.
3. No mutation gets promoted because it sounds advanced.
4. Every mutation must name the failure signature it is supposed to fix.
5. Every mutation must keep immutable evidence recoverable.

## Current baseline

Current best measured local lane:

- `observational_temporal_memory + MiniMax-M2.7`

Current likely overtake candidate under harder scale:

- `dual_store_event_calendar_hybrid`

Current core diagnosis:

- the lead lane wins because it surfaces answer-bearing propositions cleanly
- the next likely failures will come from scale, broader evidence coverage, and maintenance over longer horizons

## Benchmark Pressure Map

| Benchmark | What it will punish first | What a good mutation must improve |
|---|---|---|
| `LongMemEval_s` | stale fact reuse, missing supersession, weak temporal disambiguation | update handling, temporal routing, exact answer preservation |
| `LoCoMo` | wrong but plausible turn retrieval, weak multi-hop coverage, narrative fragmentation | broader evidence coverage, topic continuity, structured multi-hop retrieval |
| `BEAM` | prompt sprawl, memory collapse at scale, too much online fanout, weak memory-role separation | bounded visible surface, offline maintenance, dual retrieval modes, working-memory control |

## Mutation Queue

### `M1` Topic continuity write path

Inspired by:

- `Membox`

What to build:

- segment adjacent turns into short topical episodes before observation extraction
- attach `topic_id`, `episode_span`, and `topic_summary` fields
- allow retrieval to pull both a single observation and its local topical container

Primary target benchmark:

- `LoCoMo`

Secondary target benchmark:

- `BEAM`

Failure signature this should fix:

- answers fail because the winning evidence is spread across neighboring turns that were stored independently
- retrieved facts are individually relevant but collectively incomplete

Implementation surface:

- write path in [src/domain_chip_memory/memory_systems.py](/<domain-chip-memory>/src/domain_chip_memory/memory_systems.py)
- packet assembly logic for observational and hybrid systems

Main regression risk:

- topic segmentation errors can contaminate otherwise clean retrieval

Promotion gate:

- improves `LoCoMo` multi-hop slices without harming closed exact-span slices

### `M2` Dual-route retrieval

Inspired by:

- `Mnemis`

What to build:

- keep the current fast local retrieval path
- add a second retrieval path that explicitly selects a globally coherent set of evidence items
- allow the second path only on detected hard questions or when the first path is low-confidence

Primary target benchmark:

- `LoCoMo`

Secondary target benchmark:

- `BEAM`

Failure signature this should fix:

- top-ranked observations look individually relevant but miss one necessary supporting turn
- retrieval keeps returning local nearest neighbors instead of the globally correct bundle

Implementation surface:

- retrieval ranking code in [src/domain_chip_memory/memory_systems.py](/<domain-chip-memory>/src/domain_chip_memory/memory_systems.py)
- optional question difficulty or low-confidence routing

Main regression risk:

- higher latency and token use on easy questions

Promotion gate:

- materially improves hard `LoCoMo` questions while keeping easy-slice latency under control

### `M3` Evidence versus belief packet split

Inspired by:

- `Hindsight`

What to build:

- separate packet sections for:
  - immutable evidence
  - synthesized reflection
  - current belief or answer candidate
- prevent reflections from masquerading as raw evidence

Primary target benchmark:

- `LongMemEval_s`

Secondary target benchmark:

- `LoCoMo`

Failure signature this should fix:

- the packet contains the right idea but the model drifts because evidence and abstraction are mixed together
- changed facts are not clearly distinguished from old beliefs

Implementation surface:

- packet formatting in [src/domain_chip_memory/memory_systems.py](/<domain-chip-memory>/src/domain_chip_memory/memory_systems.py)
- compaction and preservation logic in [src/domain_chip_memory/providers.py](/<domain-chip-memory>/src/domain_chip_memory/providers.py)

Main regression risk:

- packet becomes too verbose if the split is not tightly bounded

Promotion gate:

- fewer answer-shape and stale-belief misses on `LongMemEval_s` extensions

### `M4` Offline merge, split, and update maintenance

Inspired by:

- `All-Mem`

What to build:

- a maintenance lane that edits memory topology offline
- operations allowed:
  - `merge`
  - `split`
  - `update`
  - `supersede`
- preserve immutable evidence references even when the visible memory graph changes

Primary target benchmark:

- `BEAM`

Secondary target benchmark:

- `LongMemEval_s`

Failure signature this should fix:

- memory quality decays over time because the store grows without cleanup
- multiple nearly-duplicate memories crowd out the best evidence

Implementation surface:

- new maintenance pipeline under [src/domain_chip_memory](/<domain-chip-memory>/src/domain_chip_memory)
- likely new artifact contracts for before/after memory topology snapshots

Main regression risk:

- bad offline edits silently corrupt retrieval quality

Promotion gate:

- better retrieval hit rate under longer histories with no loss of provenance

### `M5` Bounded forgetting and decay lane

Inspired by:

- `FadeMem`

What to build:

- score memories for retention, merge, or decay based on:
  - recency
  - access frequency
  - contradiction status
  - benchmark utility
- forgetting must be reversible at the evidence layer

Primary target benchmark:

- `BEAM`

Secondary target benchmark:

- `GoodAI LTM Benchmark`

Failure signature this should fix:

- the memory system keeps too much low-value residue and retrieval quality degrades as history grows

Implementation surface:

- maintenance policy layer
- retention metadata on observations, events, and profiles

Main regression risk:

- future-critical but infrequent facts disappear too early

Promotion gate:

- lower memory volume and cost without reducing audited answer accuracy

### `M6` Stronger profile versus event separation

Inspired by:

- `O-Mem`
- `MIRIX`

What to build:

- explicit profile store for stable user traits and preferences
- explicit event store for dated or session-bound information
- route questions differently depending on whether they are asking about identity, preference, or event history

Primary target benchmark:

- `LongMemEval_s`

Secondary target benchmark:

- `LoCoMo`

Failure signature this should fix:

- stable facts and transient events compete in the same retrieval pool
- updated event facts leak into what should be stable profile memory, or vice versa

Implementation surface:

- hybrid memory schema and question-aware retrieval logic

Main regression risk:

- overclassification errors send a question to the wrong store

Promotion gate:

- stronger update handling and fewer profile-event confusions on extension slices

### `M7` Episodic reconstruction lane

Inspired by:

- `E-mem`

What to build:

- retrieve compact cues first
- then reconstruct one or two raw evidence episodes around those cues
- let the answering model see the compressed packet plus a tiny rehydrated episode window

Primary target benchmark:

- `LoCoMo`

Secondary target benchmark:

- `BEAM`

Failure signature this should fix:

- compression preserved the right fact but lost the local causal chain needed for correct reasoning

Implementation surface:

- rehydration and packet assembly path

Main regression risk:

- token growth if too many episodes are expanded

Promotion gate:

- better hard-question recall without broad packet inflation

### `M8` Working-memory and scratchpad control

Inspired by:

- `MIRIX`
- `BEAM` program doctrine

What to build:

- a tiny current-task working-memory surface
- a transient scratchpad surface used only during hard retrieval or reasoning
- strict rules for what is allowed into each

Primary target benchmark:

- `BEAM`

Secondary target benchmark:

- `LongMemEval_s`

Failure signature this should fix:

- retrieval returns too much evidence and the answering path loses focus
- hard questions need temporary accumulation but not permanent storage

Implementation surface:

- packet assembly and possibly provider-side orchestration

Main regression risk:

- extra orchestration without actual benchmark benefit

Promotion gate:

- improved hard-case answer quality with bounded prompt growth

### `M9` Training-ready memory credit assignment

Inspired by:

- `Fine-Mem`

What to build:

- log which memory operations contributed to final evidence
- attach reward-ready metadata to writes, retrieval hits, misses, and updates

Primary target benchmark:

- none immediately

Secondary target benchmark:

- future `MemoryAgentBench` or learned-controller work

Failure signature this should fix:

- we cannot tell which memory operation decisions actually helped or hurt downstream answers

Implementation surface:

- scoring and telemetry artifacts

Main regression risk:

- instrumentation cost without immediate benchmark gain

Promotion gate:

- only after the basic architecture mutations are stable

### `M10` Retrieval substrate experiments

Inspired by:

- `RuVector`

What to build:

- optional lower-layer experiments around graph-aware retrieval substrate choices
- no doctrine change until there is benchmark proof

Primary target benchmark:

- none initially

Secondary target benchmark:

- `BEAM`

Failure signature this should fix:

- current retrieval substrate becomes the bottleneck under much larger memory volume

Implementation surface:

- isolated experimental adapter, not the core architecture

Main regression risk:

- time spent on infra novelty without measurable memory gains

Promotion gate:

- only if a substrate swap shows clear retrieval-hit or latency gains on the same memory architecture

## Recommended Execution Order

1. `M1` Topic continuity write path
2. `M3` Evidence versus belief packet split
3. `M2` Dual-route retrieval
4. `M6` Stronger profile versus event separation
5. `M7` Episodic reconstruction lane
6. `M4` Offline merge, split, and update maintenance
7. `M5` Bounded forgetting and decay lane
8. `M8` Working-memory and scratchpad control
9. `M9` Training-ready memory credit assignment
10. `M10` Retrieval substrate experiments

Reason for this order:

- start with the highest-leverage changes that are closest to our current winning lane
- postpone the heavier maintenance and infra bets until simpler structural fixes are measured

## Mutation-to-Benchmark Matrix

| Mutation | LongMemEval_s | LoCoMo | BEAM | GoodAI | Expected leverage |
|---|---|---|---|---|---|
| `M1` Topic continuity | medium | high | medium | low | fixes fragmented conversational evidence |
| `M2` Dual-route retrieval | medium | high | high | low | fixes local-similarity blind spots |
| `M3` Evidence vs belief split | high | medium | medium | low | fixes stale belief and mixed-evidence drift |
| `M4` Offline maintenance | medium | medium | high | medium | fixes memory decay under scale |
| `M5` Forgetting and decay | low | medium | high | high | fixes residue buildup and scale noise |
| `M6` Profile vs event separation | high | medium | medium | low | fixes update and identity-event collisions |
| `M7` Episodic reconstruction | low | high | medium | low | fixes causal-chain loss from compression |
| `M8` Working memory and scratchpad | medium | medium | high | low | fixes focus collapse on hard retrieval |
| `M9` Credit assignment | low | low | medium | medium | prepares training or controller learning |
| `M10` Retrieval substrate | low | low | medium | low | only matters if substrate becomes bottleneck |

## Promotion Rule

Do not promote a mutation into the default lead lane until:

1. it has a clear win on the benchmark pressure it targeted
2. it does not break already-closed audited slices
3. its latency and packet growth stay within acceptable bounds
4. the failure signature it was meant to fix actually shrinks in the artifacts
