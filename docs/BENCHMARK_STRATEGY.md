# Benchmark Strategy

Date: 2026-03-22
Status: active strategy

## Primary objective

Build a memory system that can beat the strongest public benchmarked systems with an honest, reproducible evaluation path.

Program structure from March 24, 2026 onward:

1. Keep `LongMemEval_s` and `LoCoMo` as mandatory completion and regression gates.
2. Promote `BEAM` to an explicit frontier benchmark we optimize toward now, not only later.
3. Refuse any `BEAM`-oriented mutation that breaks already-closed `LongMemEval_s` or `LoCoMo` slices.

## Public target order

1. `LongMemEval_s`
2. `LoCoMo`
3. `BEAM`
4. `GoodAI LTM Benchmark`

Reason:

- `LongMemEval_s` is currently the clearest public frontier for knowledge updates and temporal reasoning
- `LoCoMo` stress-tests long conversational recall and reasoning
- `BEAM` is the clearest current stress test for coherent million-token and multi-million-token conversational memory, and is the hardest benchmark in the target stack to fake with shorter-context tricks
- `GoodAI LTM Benchmark` still matters as a harness for long-span memory upkeep and integration across very long conversations with published runnable configs

Interpretation:

- `LongMemEval_s` and `LoCoMo` remain the honesty benchmarks we must actually finish.
- `BEAM` is now the frontier architecture benchmark that should shape what we build next.
- `GoodAI LTM Benchmark` remains an internal durability harness rather than the primary frontier narrative.

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
- staying retrieval-efficient without collapsing into raw full-context dependence
- preserving answer-bearing evidence after aggressive compression and rehydration

Failure mode to avoid:

- doing well on shorter long-memory benchmarks while collapsing as coherent context grows toward the million-token regime
- adding heavy orchestration that wins only by brute-force fanout while regressing the lighter benchmark path

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

BEAM-oriented pressure added now:

1. separate working memory, episodic archive, stable compressed memory, and scratchpad memory explicitly
2. keep the online path lightweight and push consolidation offline wherever possible
3. preserve exact answer-bearing spans through compaction and rehydration
4. treat stable observational compression and temporal event structure as complementary, not mutually exclusive
5. use `LongMemEval_s` and `LoCoMo` as regression locks while evolving toward BEAM-scale memory

## Anti-goals

- tuning only one benchmark category
- evaluating only against weak baselines
- using unclear or non-reproducible judge logic
- hiding behind "experimental" after public win claims
