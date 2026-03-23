# Benchmark Strategy

Date: 2026-03-22
Status: active strategy

## Primary objective

Build a memory system that can beat the strongest public benchmarked systems with an honest, reproducible evaluation path.

## Public target order

1. `LongMemEval_s`
2. `LoCoMo`
3. `GoodAI LTM Benchmark`
4. `BEAM`

Reason:

- `LongMemEval_s` is currently the clearest public frontier for knowledge updates and temporal reasoning
- `LoCoMo` stress-tests long conversational recall and reasoning
- `GoodAI LTM Benchmark` stress-tests long-span memory upkeep and integration across very long conversations with published runnable configs
- `BEAM` extends the frontier toward coherent million-token and multi-million-token memory stress

Shadow benchmark:

- `ConvoMem` remains a regression benchmark for short-history slices, preference handling, changing facts, and abstention

## Benchmark-specific requirements

### LongMemEval

Must be strong at:

- `knowledge-update`
- `temporal-reasoning`
- `multi-session`

Failure mode to avoid:

- retrieving stale facts without version resolution

### LoCoMo

Must be strong at:

- multi-hop evidence recovery
- temporal reasoning across sessions
- adversarial or unanswerable handling

Failure mode to avoid:

- retrieving plausible but wrong turns from a very long history

### GoodAI LTM Benchmark

Must be strong at:

- dynamic memory upkeep
- integration over long periods
- long-span conversational memory
- continual-memory behavior

Failure mode to avoid:

- performing well only on benchmark-native QA while failing under longer-span memory pressure

### BEAM

Must be strong at:

- million-token and beyond memory pressure
- coherent long-context reasoning
- balancing episodic memory, working memory, and scratchpad-style support

Failure mode to avoid:

- doing well on shorter long-memory benchmarks while collapsing as coherent context grows toward the million-token regime

### ConvoMem Shadow

Must still be checked for:

- preferences
- changing facts
- implicit connections
- abstention

Failure mode to avoid:

- overbuilding retrieval when full context is still the better trade

## Score policy

Track at least these metrics:

- overall answer accuracy
- per-category accuracy
- abstention accuracy
- retrieval evidence hit rate
- latency
- cost

Do not treat a benchmark as won if only the overall average improves while one of the core memory categories collapses.

## Architecture bet

The initial architecture bet for the chip is:

1. structured extraction into memory atoms
2. temporal and version relations
3. question-type-aware retrieval
4. specialist answer policies
5. mutation loop driven by benchmark failures

## Anti-goals

- tuning only one benchmark category
- evaluating only against weak baselines
- using unclear or non-reproducible judge logic
- hiding behind "experimental" after public win claims
