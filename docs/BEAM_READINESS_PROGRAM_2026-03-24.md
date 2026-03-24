# BEAM Readiness Program 2026-03-24

Status: active execution doctrine

## Why this exists

`LongMemEval_s` and bounded `LoCoMo` slices are already giving strong signal, but they are not the final proof that the memory architecture will survive million-token pressure.

`BEAM` is now an explicit key target because it is the clearest current benchmark for:

- coherent million-token memory pressure
- long-horizon conversational reasoning
- architectures that must combine episodic memory, working memory, and scratchpad support

At the same time, we are not allowed to lie to ourselves:

- we have not yet completed full `LongMemEval_s`
- we have not yet completed full `LoCoMo`
- we therefore cannot treat current slice wins as proof that the architecture is already frontier-complete

## Program doctrine

The program now has a dual mandate:

1. Keep extending and preserving benchmark leadership on `LongMemEval_s` and `LoCoMo`.
2. Structure the architecture now so it can become dominant on `BEAM`.

This means:

- no overfitting to the already-closed slices
- no abandoning the current benchmarks in order to chase a harder benchmark theatrically
- no `BEAM` mutation that breaks already-closed `LongMemEval_s` or `LoCoMo` behavior

## Current truthful status

Current best measured lane:

- `observational_temporal_memory + MiniMax-M2.7`

What that currently proves:

- it is the strongest measured lane in this repo on the benchmark slices actually run
- it is not yet proven as the universally best memory architecture
- it is not yet proven on full `LongMemEval_s`
- it is not yet proven on full `LoCoMo`
- it is not yet proven on `BEAM`

## What BEAM should force us to build

`BEAM` pressure should move the architecture toward explicit memory-role separation.

Required memory roles:

1. working memory
   - tiny, current-task, high-salience context
2. episodic archive
   - raw turn/session ground truth for provenance and rehydration
3. stable compressed memory
   - observation and reflection style memory that can survive huge histories
4. temporal or event memory
   - timestamped event structure, supersession, and temporal disambiguation
5. scratchpad memory
   - transient accumulation of salient facts during hard retrieval or reasoning paths

Program implication:

- the likely `BEAM`-ready winner is not a pure observational system or a pure atom system
- it is likely a hybrid that preserves what currently wins on `LongMemEval_s` and `LoCoMo` while adding stronger large-context structure
- the unified operating memo is now `docs/UNIFIED_MEMORY_SYSTEM_PROGRAM_2026-03-25.md`

## Execution lanes

### Lane A: Coverage and regression

Keep extending real benchmark coverage:

1. finish `LongMemEval_s` beyond the first `200/500`
2. move `LoCoMo` onto a clean post-`q150` lane instead of relying on the contaminated `conv-26 q151-199` tail
3. expand beyond the current bounded `LoCoMo` single-conversation focus

Regression rule:

- every architectural mutation aimed at `BEAM` must preserve closed `LongMemEval_s` and `LoCoMo` slices unless the regression is clearly isolated and intentionally temporary

### Lane B: BEAM-oriented architecture

Prioritize components that should transfer to million-token pressure:

1. stronger separation between profile memory and event memory
2. explicit working-memory and scratchpad layers
3. stable compressed observation windows
4. event-calendar or temporal-store support for long-range disambiguation
5. offline consolidation rather than heavy online fanout
6. exact-span preservation through compaction and rehydration

### Lane C: Honest evaluation

Do not let `BEAM` become a vague aspiration.

Required evaluation structure:

1. maintain source-of-truth artifacts for every closed slice
2. preserve audited views where benchmark inconsistencies exist
3. track when a mutation helps `BEAM`-style pressure but hurts current reproducible benchmarks
4. treat `LongMemEval_s` and `LoCoMo` as non-negotiable regression gates

## Working hypothesis

Current strongest hypothesis:

- `observational_temporal_memory` is the best current measured lane because it surfaces exact answer-bearing propositions cleanly

Current next hypothesis:

- a `BEAM`-ready winner is likely to keep the observational stable-window strengths while adding stronger temporal-event structure and explicit memory-role separation

In repo terms, that suggests:

- keep the observational lane as the current lead
- keep the dual-store event-calendar hybrid as the most likely overtake candidate under harder `BEAM` pressure

## Immediate next moves

1. Extend `LongMemEval_s` coverage from `200/500` to `225/500`.
2. Start the architecture consolidation track in parallel by adding typed `answer_candidate` contracts and explicit current-state separation.
3. Start the next clean `LoCoMo` conversation slice instead of continuing to optimize the contaminated `conv-26 q151-199` tail.
4. Lock the first canonical `GoodAI LTM Benchmark` run instead of leaving that frontier abstract.
5. Add `BEAM` adapter and scorecard contracts as soon as the implementation surface is pin-able.
6. Start testing architecture mutations against the question:
   - does this help million-token-scale memory pressure without breaking the already-closed slices?

## Promotion rule

Do not call the system `BEAM`-ready until all of the following are true:

1. `LongMemEval_s` coverage is materially broader than the current partial slice
2. `LoCoMo` coverage is materially broader than the current bounded `conv-26` slices
3. a `BEAM` evaluation path exists in-repo
4. the architecture shows positive transfer rather than benchmark-specific overfit
