# Current Status, Remaining Work, And Next Benchmarks

Date: 2026-04-08
Status: active current-state checkpoint

## Purpose

This document is the shortest honest answer to five questions:

1. where the memory system stands right now
2. what is already benchmark-strong
3. what is still incomplete
4. how aligned the current Spark KB layer is with the Karpathy LLM knowledge-base pattern
5. what should happen next

## What the checkpoint commits mean

The recent benchmark checkpoint commits are not arbitrary artifact dumps.

They are the judged outputs of the current memory architecture on the official-public `BEAM` evaluation path:

- the memory system first produces `domain_chip_memory_answers.json`
- the official-public evaluator then judges those answers category by category
- when one conversation finishes cleanly, that judged evaluation file is committed
- when a whole tranche finishes, the top-level official-eval manifest is reconstructed from the completed judged files and committed

So each checkpoint is evidence that the current memory system is surviving live benchmark evaluation, not only unit tests or local scorecards.

## Current benchmark map

### Tier 1: strongest measured paths

- local `ProductMemory`: `1266/1266`
- `LongMemEval_s`: `500/500`
- local official-public `BEAM 128K` latest checked-in leader variants: `400/400`

Interpretation:

- current-state reconstruction is strong
- correction and contradiction handling are strong
- temporal and multi-session recall are strong
- the current `summary_synthesis_memory + heuristic_v1` architecture is real, not speculative

### Tier 2: strong but bounded

- bounded clean `LoCoMo`
  - first active slice: `24/25` raw with one known inconsistency
  - later `conv-26` slices through `q126-150`: repeated `25/25` clean reruns

Interpretation:

- conversational linkage is strong on the measured lane
- broader clean `LoCoMo` closure is still not honest to claim yet

### Tier 3: official-public judged `BEAM`

#### `500K`

This scale is fully closed:

- `conv1-5`: completed, `0.8349`
- `conv6-10`: completed, `0.7094`
- `conv11-15`: completed, `0.7598`
- `conv16-20`: completed, `0.7559`

Completion:

- `20/20` conversations judged complete
- tranche completion: `100%`

#### `1M`

This scale is now partially closed:

- `conv1-5`: completed, `0.915`
- `conv6-10`: not closed yet
- `conv11-15`: validated only
- `conv16-20`: validated only

Completion:

- `5/20` conversations judged complete
- tranche completion: `25%`

#### `10M`

This scale is not judged yet:

- `conv1-5`: validated only
- `conv6-10`: validated only

Completion:

- `0/10` conversations judged complete
- tranche completion: `0%`

## What is still missing

### Benchmarks still to close

1. `BEAM 1M`
   - finish `conv6-10`
   - finish `conv11-15`
   - finish `conv16-20`
2. `BEAM 10M`
   - finish `conv1-5`
   - finish `conv6-10`
3. official judged `BEAM 128K`
   - local scorecard strength is already strong
   - official judged closure is still incomplete
4. broader clean `LoCoMo`
   - move beyond the bounded `conv-26` lane
5. first canonical `GoodAI` run
   - still not meaningfully closed

### Product and systems work still missing

1. direct runtime metrics
   - latency
   - token cost
   - memory growth
   - drift rate
   - correction success rate
   - deletion reliability
2. real Spark shadow traces
   - replayable batches from actual traffic
   - failure taxonomy from product traces
3. full knowledge-base product layer
   - current scaffold exists
   - the full compile/query/filing loop does not yet exist

## How good the current memory architecture is

The honest answer is:

- already strong enough to call concrete
- not yet finished enough to call complete

Why it is strong:

- it closes local `ProductMemory`
- it closes `LongMemEval_s`
- it is strong on bounded `LoCoMo`
- it now has real official-public judged `BEAM` evidence at `500K`
- it now has the first judged `1M` tranche closed at `0.915`

Why it is not finished:

- the largest remaining official pressure is still `1M` and `10M`
- the broad `LoCoMo` and canonical `GoodAI` surfaces remain open
- the user-visible KB layer is still early

## Karpathy KB alignment: current verdict

Current verdict: partially aligned, not fully there yet.

### What is already aligned

The repo now has a real Spark KB scaffold that matches the shape of the Karpathy idea in the following ways:

- `raw/` exists as the intake shelf
- `wiki/` exists as the compiled markdown layer
- `CLAUDE.md` is generated as an LLM-facing schema
- the KB is downstream of governed memory, not a second truth store
- the vault is Obsidian-friendly
- query outputs have a reserved filing location under `wiki/outputs/`
- health checks exist

### What is specifically implemented

- `SparkMemorySDK.export_knowledge_base_snapshot()` in [sdk.py](../src/domain_chip_memory/sdk.py)
- KB scaffold in [spark_kb.py](../src/domain_chip_memory/spark_kb.py)
- CLI entrypoints in [cli.py](../src/domain_chip_memory/cli.py)
- integration contract in [spark_integration.py](../src/domain_chip_memory/spark_integration.py)

### What was missing before this update

Before the latest KB alignment pass, the scaffold was too runtime-centric:

- it had current-state, evidence, and event pages
- but it did not yet look enough like `raw -> compiled wiki -> syntheses -> outputs`

### What is now improved

The KB scaffold now better matches the Karpathy pattern:

- reserved `raw/articles/`, `raw/papers/`, `raw/repos/`, `raw/datasets/`, and `raw/assets/`
- compiled `wiki/sources/` pages for governed inputs
- compiled `wiki/syntheses/` pages for memory overviews
- top-level navigation that exposes sources, syntheses, runtime facts, evidence, events, and outputs
- health checks that validate the expanded Karpathy-shaped layout

### What still does not exist yet

The system is still not fully Karpathy-complete because it does not yet have:

- incremental ingest of external articles, repos, papers, and datasets into `raw/`
- cross-source concept/entity pages beyond runtime memory pages
- filed query answers generated against the wiki itself
- automated contradiction and gap-filling passes over mixed runtime-plus-research sources
- Obsidian-native dashboards or Dataview views
- scheduled compilation or maintenance loops

## Live KB validation

The KB flow should be validated with the real CLI, not only by reading code.

Minimum live checks:

1. `python -m domain_chip_memory.cli demo-spark-kb <output_dir>`
2. `python -m domain_chip_memory.cli spark-kb-health-check <output_dir>`

Success means:

- the vault is scaffolded
- the source pages and synthesis pages exist
- health checks pass cleanly

Current live result on 2026-04-08:

- `demo-spark-kb` ran successfully against a real local vault scaffold
- `spark-kb-health-check` returned `valid: true`
- no missing required files
- no broken wikilinks
- only `wiki/log.md` remains orphaned, which is acceptable for now because it is an append-only activity surface rather than a navigational page

## What is done vs remaining right now

### Done

- `ProductMemory`
- `LongMemEval_s`
- bounded `LoCoMo` lane
- official-public judged `BEAM 500K`
- official-public judged `BEAM 1M conv1-5`
- first Spark KB scaffold
- first Spark KB health checks
- first Karpathy-alignment upgrade to the Spark KB scaffold

### Remaining

- `BEAM 1M conv6-10`
- `BEAM 1M conv11-15`
- `BEAM 1M conv16-20`
- `BEAM 10M conv1-5`
- `BEAM 10M conv6-10`
- official judged `BEAM 128K`
- broader clean `LoCoMo`
- canonical `GoodAI`
- runtime metrics
- real Spark traces
- KB compiler v2 with query filing and cross-source syntheses

## Next tasks in order

### Immediate benchmark tasks

1. finish `BEAM 1M conv6-10`
2. finish `BEAM 1M conv11-15`
3. finish `BEAM 1M conv16-20`
4. close `BEAM 10M`

### Immediate KB tasks

1. keep the current scaffold green under live CLI checks
2. add richer compiled pages that connect runtime memory to benchmark and repo knowledge
3. add filed query outputs under `wiki/outputs/`
4. add a maintenance report page that summarizes contradictions, staleness, and missing pages
5. add an ingest path for repo-native research and benchmark artifacts into `raw/`

### Next product tasks after that

1. lock the first canonical `GoodAI` run
2. choose and close the next clean `LoCoMo` lane
3. start measuring runtime metrics on the actual Spark-style memory surface
4. connect real shadow traces into the KB as inspectable source material

## Bottom line

The current memory architecture is already benchmark-serious.

The current KB layer is real but early.

The remaining work is no longer "figure out whether this works."
The remaining work is:

- finish the official judged benchmark closure
- finish broad benchmark honesty beyond the strongest bounded lanes
- turn the Spark KB from a correct scaffold into the full visible external-brain product layer
