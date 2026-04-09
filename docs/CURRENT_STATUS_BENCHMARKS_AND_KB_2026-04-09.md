# Current Status, Remaining Work, And Next Benchmarks

Date: 2026-04-09
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

Important honesty note:

- the current judged `BEAM` closure is on the alternate openai-compatible MiniMax judge path, not the exact upstream OpenAI judge path
- it is still strong official-public evidence, but it should be described as alternate judged evidence, not exact-official final closure

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

This scale is fully closed on the alternate judge path:

- `conv1-5`: completed, `0.8349`
- `conv6-10`: completed, `0.7094`
- `conv11-15`: completed, `0.7598`
- `conv16-20`: completed, `0.7559`

Completion:

- `20/20` conversations judged complete
- tranche completion: `100%`

#### `1M`

This scale is now fully closed on the alternate judge path:

- `conv1-5`: completed, `0.915`
- `conv6-10`: completed, `0.9139`
- `conv11-15`: completed, `0.8889`
- `conv16-20`: completed, `0.9058`

Completion:

- `20/20` conversations judged complete
- tranche completion: `100%`

#### `10M`

This scale is now fully closed on the alternate judge path:

- `conv1-5`: completed, `0.8394`
- `conv6-10`: completed, `0.9108`

Completion:

- `10/10` conversations judged complete
- tranche completion: `100%`

Interpretation:

- the alternate judged official-public `BEAM` story is no longer partial at `500K`, `1M`, or `10M`
- the remaining `BEAM` work is now cleanup and exact-judge closure, not more tranche chasing on this MiniMax path

## What is still missing

### Benchmarks still to close

1. official judged `BEAM 128K`
   - local scorecard strength is already strong
   - alternate judged `500K`, `1M`, and `10M` closure does not replace exact `128K` judged cleanup
2. broader clean `LoCoMo`
   - move beyond the bounded `conv-26` lane
3. first canonical `GoodAI` run
   - still not meaningfully closed
4. exact-official upstream OpenAI judge closure
   - the current `BEAM` judged story is strong alternate evidence
   - exact-judge parity is still a separate evidence class

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
- it now has full alternate judged official-public `BEAM` coverage at `500K`, `1M`, and `10M`

Why it is not finished:

- exact-official judge parity is still open
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
- compiled session source pages in `wiki/sources/`
- compiled timeline synthesis in `wiki/syntheses/timeline-overview.md`
- explicit repo-native ingest into `raw/repos/` plus compiled repo source pages
- filed KB maintenance report in `wiki/outputs/maintenance-report.md`
- filed KB answer pages in `wiki/outputs/query-*.md`
- contradiction and stale-state signals inside the KB maintenance report
- real `build-spark-kb` support for explicit filed-output JSON inputs
- real `build-spark-kb` support for repo-source manifest JSON inputs
- real `build-spark-kb` support for filed-output manifest JSON inputs
- real `validate-spark-kb-inputs` preflight support for snapshot, manifest, and filed-output validation
- compile results now expose both `repo_source_count` and `filed_output_count`

### What is now true after BEAM closure

- benchmark closure is no longer the only credible product story in the repo
- the KB layer is now the clearest remaining user-visible gap
- the next KB work should be real compilation and filing, not only scaffold maintenance

### What still does not exist yet

The system is still not fully Karpathy-complete because it does not yet have:

- incremental ingest of external articles, repos, papers, and datasets into `raw/`
- cross-source concept/entity pages beyond runtime memory pages
- broad filed query answers generated against the wiki itself
- automated contradiction and gap-filling passes over mixed runtime-plus-research sources beyond the first maintenance heuristics
- Obsidian-native dashboards or Dataview views
- scheduled compilation or maintenance loops

## Live KB validation

The KB flow should be validated with the real CLI, not only by reading code.

Minimum live checks:

1. `python -m domain_chip_memory.cli validate-spark-kb-inputs <snapshot_file> [--repo-source ...] [--repo-source-manifest ...] [--filed-output-file ...] [--filed-output-manifest ...]`
2. `python -m domain_chip_memory.cli build-spark-kb <snapshot_file> <output_dir> [--repo-source ...] [--repo-source-manifest ...] [--filed-output-file ...] [--filed-output-manifest ...]`
3. `python -m domain_chip_memory.cli spark-kb-health-check <output_dir>`
4. `python -m domain_chip_memory.cli demo-spark-kb <output_dir>`

Success means:

- the vault is scaffolded
- the source pages and synthesis pages exist
- input manifests and filed-output payloads validate cleanly before compile
- health checks pass cleanly, including repo-source/raw-copy parity and required filed-output sections

Current live result on 2026-04-09:

- `build-spark-kb` now exists as a real non-demo compiler path for snapshot JSON inputs
- `validate-spark-kb-inputs` now exists as a real preflight for snapshot, manifest, and filed-output bundles
- `build-spark-kb` can now merge explicit `--repo-source` files with manifest-driven repo-source lists
- `build-spark-kb` can now merge explicit `--filed-output-file` inputs with manifest-driven filed-output lists
- manifest entries now resolve relative to the manifest file location, not only the current shell directory
- `demo-spark-kb` ran successfully against a real local vault scaffold
- `spark-kb-health-check` returned `valid: true`
- no missing required files
- no broken wikilinks
- repo-source pages are now checked against `raw/repos/` copies, and stray raw repo files are surfaced explicitly
- filed query pages are now checked for required `Question`, `Answer`, and `Provenance` sections
- source, synthesis, and output surfaces now include session pages, timeline overview, repo-source ingest, maintenance report output, filed answer pages, and first contradiction/staleness signals
- only `wiki/log.md` remains orphaned, which is acceptable for now because it is an append-only activity surface rather than a navigational page

## What is done vs remaining right now

### Done

- `ProductMemory`
- `LongMemEval_s`
- bounded `LoCoMo` lane
- alternate judged official-public `BEAM 500K`
- alternate judged official-public `BEAM 1M`
- alternate judged official-public `BEAM 10M`
- first Spark KB scaffold
- first Spark KB health checks
- first Karpathy-alignment upgrade to the Spark KB scaffold

### Remaining

- official judged `BEAM 128K`
- broader clean `LoCoMo`
- canonical `GoodAI`
- exact-official judge parity for `BEAM`
- runtime metrics
- real Spark traces
- KB compiler v2 with query filing and cross-source syntheses

## Next tasks in order

### Immediate benchmark tasks

1. keep the closed alternate judged `BEAM` lanes as regression gates instead of reopening them casually
2. decide whether the next `BEAM` evidence task is exact-official judge parity or official judged `128K` cleanup
3. choose and close the next clean `LoCoMo` lane
4. lock the first canonical `GoodAI` run

### Immediate KB tasks

1. keep the current scaffold green under live CLI checks
2. add richer compiled pages that connect runtime memory to benchmark and repo knowledge
3. broaden filed query outputs beyond the current demo answer page
4. deepen the maintenance report beyond the first contradiction/staleness heuristics into richer gap and contradiction analysis
5. broaden repo-native ingest from explicit file picks into a more complete research and benchmark artifact path

### Next product tasks after that

1. start measuring runtime metrics on the actual Spark-style memory surface
2. connect real shadow traces into the KB as inspectable source material
3. turn benchmark failure clusters into mutation dossiers inside the KB

## Bottom line

The current memory architecture is already benchmark-serious.

The current KB layer is real but still early.

The remaining work is no longer "figure out whether this works."
The remaining work is:

- preserve the now-closed judged proof surface honestly
- finish the remaining benchmark evidence classes that are still open
- turn the Spark KB from a correct scaffold into the visible external-brain product layer
