# Current Test And Validation Plan

Date: 2026-03-29
Status: active validation doctrine

## Purpose

This document defines:

- what is currently tested
- what is only partially tested
- what is not yet tested
- what tests are required for each type of mutation

It exists to keep the program honest.

## Validation Principles

1. No benchmark claim without a reproducible artifact.
2. No architecture claim without cross-benchmark transfer evidence.
3. No runtime claim without direct runtime measurement.
4. No product-memory claim without explicit lifecycle tests.

## Current Tested Surface

### 1. Local ProductMemory

This is the strongest currently explicit validation lane for memory lifecycle behavior.

Currently stressed:

- correction
- deletion
- restore behavior
- stale-state drift handling
- evidence preservation
- ambiguity abstention
- cross-facet disambiguation
- operation disambiguation
- dense-turn disambiguation
- pronoun-turn disambiguation
- pronoun referential ambiguity
- temporal wording disambiguation

Interpretation:

- this is our best current proof that the system behaves like a real mutable memory layer

### 2. LongMemEval_s

Currently stressed:

- contiguous measured coverage through the documented active frontier
- exactness on the active measured lane
- multi-session retrieval
- temporal recovery
- preference recovery on the measured slices

Interpretation:

- strong proof on the measured slice
- not yet full benchmark closure

### 3. Clean LoCoMo

Currently stressed:

- clean bounded active slices
- conversational linkage
- temporal linkage
- object and profile retrieval

Interpretation:

- strong bounded proof
- not yet broad clean dataset proof

### 4. Local BEAM pilot

Currently stressed:

- `BEAM`-style pressure slices
- architecture behavior under higher-context and role-separation pressure
- adapter, loader, runner, and scorecard path

Interpretation:

- real pressure lane
- not yet equivalent to complete official `BEAM` reproduction

## Partially Tested Surface

These are areas with meaningful signal but incomplete proof:

- full `LongMemEval`
- broader clean `LoCoMo`
- full official `BEAM`
- benchmark transfer to real runtime quality
- maintenance stability over longer-running use
- real product traffic replay

## Untested Or Under-Measured Surface

These are the highest-priority unknowns:

- first canonical `GoodAI` reproduction
- p50 latency
- p95 latency
- memory growth rate
- correction success rate as a direct measured metric
- deletion reliability as a direct measured metric
- memory drift rate across maintenance cycles
- Spark Builder trace replay quality on real trace batches
- unsupported-write taxonomy from real product traces

## Test Classes

Use these test classes for every serious change.

### Class A: Architecture safety gates

Run when:

- retrieval logic changes
- packet assembly changes
- memory-role logic changes
- lifecycle logic changes

Required:

- local `ProductMemory`
- local `BEAM`
- targeted `LongMemEval_s`
- targeted clean `LoCoMo`

### Class B: Benchmark expansion gates

Run when:

- closing new benchmark slices
- pinning new benchmark paths
- changing answer-shaping logic that affects benchmark behavior

Required:

- the benchmark being extended
- at least one cross-check benchmark
- local `ProductMemory`

### Class C: Runtime quality gates

Run when:

- maintenance behavior changes
- runtime SDK behavior changes
- compaction or reconsolidation changes
- provider behavior changes cost or latency

Required:

- latency capture
- token capture
- memory growth capture
- local `ProductMemory`
- local `BEAM`

### Class D: Spark shadow gates

Run when:

- SDK/runtime surfaces change
- write acceptance logic changes
- maintenance behavior changes

Required:

- replayable shadow traces
- probe hit-rate reporting
- unsupported-write reporting
- benchmark safety gates after replay-driven mutations

## Anti-Overfit Rules

Treat a benchmark gain as suspicious until it passes these checks:

- does it transfer to at least one other benchmark family
- does it preserve local `ProductMemory`
- does it reduce or increase provider rescue dependence
- does it improve substrate clarity or only answer shaping
- does it preserve abstention honesty

## Current Validation Gaps To Close Next

1. Pin the official `BEAM` reproduction path and separate it from the local pilot path.
2. Extend the measured `LongMemEval_s` frontier beyond the current contiguous coverage.
3. Move `LoCoMo` onto the next clean lane beyond the current bounded active slices.
4. Lock the first canonical `GoodAI` run.
5. Add direct runtime metric capture into serious comparison artifacts.
6. Run the first real Spark shadow trace batch.

## Decision Rule

Use this language in future docs and reports:

- `tested`: directly measured with a reproducible artifact
- `partially tested`: meaningful but bounded or incomplete coverage
- `untested`: not directly measured yet
- `unknown`: current evidence is too weak to justify a confidence claim

