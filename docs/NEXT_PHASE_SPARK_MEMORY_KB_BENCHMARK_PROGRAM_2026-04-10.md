# Next Phase Spark Memory, KB, And Benchmark Program

Date: 2026-04-10
Status: active next-phase source-of-truth

## 2026-04-11 Cross-Repo Update

The chip-side benchmark story and the Builder-side live story are now aligned enough to drive one runtime decision again.

Current honest state:

<!-- AUTO_BUILDER_BASELINE_NEXT_PHASE_START -->
- the latest offline `ProductMemory` comparison between `summary_synthesis_memory` and `dual_store_event_calendar_hybrid` is tied at `1156/1266`
- the latest clean live Builder full validation root is `C:\Users\USER\.spark-intelligence\artifacts\memory-validation-runs\20260412-023241`
- the latest clean live Builder full-run pointer is `C:\Users\USER\.spark-intelligence\artifacts\memory-validation-runs\latest-full-run.json`
- the chip-side freshness against that Builder baseline is `clean`
- the latest clean live Builder soak is fully green at `14/14`, `0` failed
- that live Builder soak still favors `summary_synthesis_memory` at `92/92` overall and `64/64` on selector packs
- the latest clean live Builder timings are benchmark `13.543s`, regression `23.724s`, soak `339.130s`, total `376.594s`
- because the offline side is now a tie instead of a loss, Builder has repinned the runtime selector to `summary_synthesis_memory`
<!-- AUTO_BUILDER_BASELINE_NEXT_PHASE_END -->

Important boundary:

- this does not mean the benchmark program is finished
- it means the current runtime pin is now justified by an offline tie plus a live lead, instead of by live evidence alone

## 2026-04-12 Spark Restart Check

The first restart step from the checklist below has now been re-confirmed against the real Builder home:

- `python -m domain_chip_memory.cli run-spark-builder-state-telegram-intake C:\Users\USER\.spark-intelligence tmp\state_telegram_restart_check_limit100_v2 --limit 100 --write tmp\state_telegram_restart_check_limit100_v2.json`
- source path: `C:\Users\USER\.spark-intelligence\state.db`
- processed `28` conversations with `121` accepted writes, `0` rejected writes, `0` skipped turns, and `380` reference turns
- compiled KB health stayed clean with `valid: true`

That is enough to treat the direct Builder `state.db` Telegram intake path as working end to end again.

The honest follow-up matters:

- this widened replay still did not surface any rejected writes or unsupported reasons
- the zero-write cleanroom and regression threads are not currently true failure-taxonomy examples yet
- they are query-only traces where Builder asks for a profile fact, then records a `tool_result_received` summary with no accepted write

The important metadata lesson from this restart is now explicit:

- the raw Builder `tool_result_received` rows already carry `bridge_mode`, `routing_decision`, `fact_name`, `label`, `predicate`, `evidence_summary`, and `value_found`
- the replay normalizer had been dropping those fields on normalized assistant turns, which made missing-fact abstentions look like generic reference turns
- the normalizer now preserves that query metadata, so future taxonomy and dossier work can distinguish `value_found: false` query misses from actual rejected writes

So the truthful next step after this restart check is:

- use the preserved query metadata to document clean abstentions versus missing-fact query misses
- then choose the first `memory only` vs `memory + KB` slice with that distinction in view
- only call something a Spark failure dossier when it is backed by a real rejection, skip, or explicit miss signal instead of a generic summary line

## 2026-04-12 First Narrow Memory-Only Versus Memory-Plus-KB Result

The first combined-system comparison now exists on a narrow Spark-shaped replay slice.

Command:

- `python -m domain_chip_memory.cli run-spark-memory-kb-ablation tmp\state_telegram_restart_check_limit100_v2.json --write tmp\spark_memory_kb_ablation_limit100_v1.json`
- latest scenario-aware rerun: `python -m domain_chip_memory.cli run-spark-memory-kb-ablation tmp\state_telegram_restart_check_limit100_v2.json --write tmp\spark_memory_kb_ablation_limit100_v6.json`

Slice definition:

- input source: the real Builder `state.db` replay captured in `tmp\state_telegram_restart_check_limit100_v2.json`
- query set: the replayed Spark profile-fact query turns extracted from that intake artifact
- `memory only`: replay the normalized conversations back through governed memory and answer each extracted query with the SDK explanation path
- `memory + KB`: answer the same query set, then check whether the compiled KB current-state page and supporting evidence pages exist for that same subject and predicate

Current result:

- query count: `125`
- `memory only` answered: `113`
- `memory + KB` answered: `113`
- answer delta count: `0`
- KB-supported query count: `113`
- missing-fact query count: `11`
- classified outcomes:
  - `answered_with_kb_support`: `113`
  - `missing_fact_query`: `11`
  - `query_abstention_without_kb_support`: `1`
- missing-fact predicates:
  - `profile.spark_role`: `4`
  - `profile.hack_actor`: `4`
  - `profile.timezone`: `2`
  - `profile.home_country`: `1`
- missing-fact scenarios:
  - `regression`: `4`
  - `boundary_abstention_cleanroom`: `4`
  - `quality_lane_gauntlet`: `3`
- missing-fact predicates by scenario:
  - `regression`: `profile.spark_role` `2`, `profile.hack_actor` `2`
  - `boundary_abstention_cleanroom`: one each of `profile.spark_role`, `profile.hack_actor`, `profile.timezone`, `profile.home_country`
  - `quality_lane_gauntlet`: one each of `profile.spark_role`, `profile.hack_actor`, `profile.timezone`
- operator action buckets:
  - `expected_cleanroom_boundary`: `4`
  - `regression_candidate`: `4`
  - `gauntlet_candidate`: `3`
- actionable predicates outside the cleanroom boundary lane:
  - `regression_candidate`: `profile.spark_role` `2`, `profile.hack_actor` `2`
  - `gauntlet_candidate`: `profile.spark_role` `1`, `profile.hack_actor` `1`, `profile.timezone` `1`
- average `memory only` latency: `0.213 ms`
- average `memory + KB` latency: `0.462 ms`

Interpretation:

- this first narrow slice does **not** show an answer-quality lift from the KB layer yet
- it does show that the KB layer is lining up with the governed memory state on the answered queries
- on this slice, the KB is currently improving inspectability and support visibility, not changing the answer itself
- the unanswered slice is now classified instead of flat:
  - most misses are true `value_found: false` missing-fact queries
  - one remaining unanswered query is a query-abstention path with no KB support, not a confirmed missing fact
- the dominant missing-fact predicates are now explicit too:
  - Spark role and hack actor are the main uncovered fields
  - timezone and home country are secondary uncovered fields on this slice
- the ablation summary now also carries compact example conversations and questions for each missing predicate, so the operator does not need to scan the full comparisons list to see representative misses
- the ablation summary now also exposes which lane each miss came from:
  - regression misses are concentrated in `profile.spark_role` and `profile.hack_actor`
  - the cleanroom boundary lane is carrying the only `profile.home_country` miss and one of each other missing predicate
  - the gauntlet lane is missing Spark role, hack actor, and timezone, but not home country on this slice
- the latest rerun also adds an operator action bucket:
  - treat the four cleanroom-boundary misses as expected boundary behavior until a product requirement says otherwise
  - treat the four regression misses and three gauntlet misses as the current candidate gap slice worth targeting next

So the honest claim after this first A/B is:

- the first Spark-shaped `memory only` versus `memory + KB` comparison is now real
- the current result is neutral on answer quality
- the KB is currently an auditability and support layer on this slice, not a measured answer-improvement layer yet

## Purpose

This document exists to prevent the next phase from fragmenting into:

- Spark integration work with no benchmark follow-through
- benchmark work with no product integration
- KB work with no runtime connection
- docs that describe aspiration instead of actual repo state

This is the practical handoff for:

1. where the system actually stands today
2. what materially improved in the last cycle
3. what is still missing
4. how Spark, runtime memory, and the Karpathy-style KB should connect
5. what the next several days should do in order

## Executive Summary

The project is now in a stronger position than the repo had even a day ago, but the nature of the progress matters.

The core runtime memory architecture did not undergo a radical mutation. The main winning lane is still:

- `summary_synthesis_memory`
- `heuristic_v1`

As of the 2026-04-11 cross-repo reruns, that lane is also the current Builder runtime selector again.

What improved materially is:

- benchmark closure and benchmark confidence
- KB scaffold reality
- Spark shadow tooling
- the first real bridges between Spark-shaped replay data and the KB compiler

The honest state is now:

- the memory system is benchmark-serious
- the Spark integration surface is real but still shadow-first
- the KB layer is real but still early
- the combined `memory + KB` answer path is not yet benchmark-proven as a joint system

This means the next phase should not be another generic architecture brainstorm.

It should be:

1. connect real Spark exports into the governed memory and KB workflow
2. make the KB materially useful on top of that runtime
3. preserve the closed benchmark lanes as regression gates
4. then run controlled benchmark work for the remaining open proof surfaces

## What Actually Shipped In This Cycle

This section is here so the next phase does not flatten all recent work into vague phrases like
"we improved Spark" or "we improved the KB."

### Runtime and benchmark substrate

The core winning runtime lane is still:

- `summary_synthesis_memory`
- `heuristic_v1`

The biggest benchmark realities now locked in are:

- local `ProductMemory`: `1266/1266`
- `LongMemEval_s`: `500/500`
- local official-public `BEAM 128K` latest checked-in leader variants: `400/400`
- alternate judged official-public `BEAM` closure at:
  - `128K`
  - `500K`
  - `1M`
  - `10M`

The current cross-repo decision surface is narrower than that historical closure summary:

- for the active Builder runtime choice, the live comparison is now `summary_synthesis_memory` vs `dual_store_event_calendar_hybrid`
- on that exact head-to-head ProductMemory comparison, the current result is tied at `1156/1266`

### Spark-facing integration upgrades

The repo now has concrete Spark-facing bridges instead of disconnected tools:

- `build-spark-kb-from-shadow-replay`
- `build-spark-kb-from-shadow-replay-batch`
- `normalize-spark-builder-export`
- `normalize-spark-builder-export-batch`
- `normalize-spark-telegram-export`
- `normalize-spark-telegram-export-batch`
- `run-spark-shadow-report-from-builder-export`
- `run-spark-shadow-report-from-builder-export-batch`
- `run-spark-shadow-report-from-telegram-export`
- `run-spark-shadow-report-from-telegram-export-batch`
- `build-spark-shadow-failure-taxonomy-from-builder-export`
- `build-spark-shadow-failure-taxonomy-from-builder-export-batch`
- `build-spark-shadow-failure-taxonomy-from-telegram-export`
- `build-spark-shadow-failure-taxonomy-from-telegram-export-batch`
- `build-spark-kb-from-builder-export`
- `build-spark-kb-from-builder-export-batch`
- `build-spark-kb-from-telegram-export`
- `build-spark-kb-from-telegram-export-batch`
- `run-spark-builder-intake-batch`
- `run-spark-telegram-intake-batch`
- `run-spark-builder-telegram-intake`
- `run-spark-builder-state-telegram-intake`

This means the repo can now:

- accept Spark-style shadow replay JSON
- accept Builder-style exports with common alias fields
- normalize them into the replay contract
- replay them through governed memory
- export a governed snapshot
- compile a visible KB vault from that snapshot

### KB scaffold upgrades

The KB layer is materially more real than it was at the start of the cycle:

- real snapshot-based `build-spark-kb`
- real `validate-spark-kb-inputs`
- real `spark-kb-health-check`
- checked-in valid and invalid example bundles
- smoke wrappers under `docs/examples/`
- CI smoke coverage
- filed outputs under `wiki/outputs/`
- repo-source ingest into `raw/repos/`
- first contradiction and stale-state signals in the maintenance output
- replay failure taxonomy now files into the KB itself, not only separate JSON diagnostics

### Benchmark observability upgrades

The benchmark-report CLI was heavily enriched so noisy artifact churn can be treated as an
operator visibility problem instead of a reasoning burden.

That work improved:

- noisy-family ranking
- noisy-series drilldown
- next-step recommendations
- compact sequence summaries
- transition summaries
- family competition summaries

It matters, but it should still be classified correctly:

- benchmark observability improvement
- not a direct mutation of the memory substrate

## What Is Actually Strong Right Now

### 1. Core benchmark evidence

Current strong measured lanes:

- local `ProductMemory`: `1266/1266`
- `LongMemEval_s`: `500/500`
- local official-public `BEAM 128K` latest checked-in leader variants: `400/400`
- alternate judged official-public `BEAM` closure at:
  - `500K`
  - `1M`
  - `10M`

Interpretation:

- current-state reconstruction is strong
- correction and contradiction handling are strong
- temporal and multi-session recall are strong
- the architecture is not speculative anymore

Important honesty boundary:

- the judged official-public `BEAM` closure is on the alternate OpenAI-compatible MiniMax judge path
- exact upstream OpenAI judge parity is still open

### 2. Spark integration surface

The repo now has real Spark-facing runtime surface, not just doctrine:

- `SparkMemorySDK`
- `SparkShadowIngestAdapter`
- shadow replay validation commands
- shadow replay report commands
- KB compile commands
- maintenance commands

More importantly, the repo now has first bridges instead of isolated surfaces:

- `build-spark-kb-from-shadow-replay`
- `build-spark-kb-from-shadow-replay-batch`
- `normalize-spark-builder-export`
- `normalize-spark-builder-export-batch`
- `normalize-spark-telegram-export`
- `normalize-spark-telegram-export-batch`
- `run-spark-shadow-report-from-builder-export`
- `run-spark-shadow-report-from-builder-export-batch`
- `run-spark-shadow-report-from-telegram-export`
- `run-spark-shadow-report-from-telegram-export-batch`
- `build-spark-shadow-failure-taxonomy-from-builder-export`
- `build-spark-shadow-failure-taxonomy-from-builder-export-batch`
- `build-spark-shadow-failure-taxonomy-from-telegram-export`
- `build-spark-shadow-failure-taxonomy-from-telegram-export-batch`
- `build-spark-kb-from-builder-export`
- `build-spark-kb-from-builder-export-batch`
- `build-spark-kb-from-telegram-export`
- `build-spark-kb-from-telegram-export-batch`
- `run-spark-builder-intake-batch`
- `run-spark-telegram-intake-batch`
- `run-spark-builder-telegram-intake`

Interpretation:

- we can accept Spark-shaped exported conversations
- normalize them into the replay contract
- replay them through governed memory
- export one combined snapshot
- compile a visible KB vault from the result

This is still export-driven, not live product wiring, but it is no longer a conceptual gap.

### 3. Karpathy-style KB direction

The KB is no longer just a document or idea. The repo now has:

- `raw/` as intake shelf
- `wiki/` as compiled markdown layer
- generated `CLAUDE.md`
- compiled source pages
- compiled timeline syntheses
- maintenance report output
- filed output pages under `wiki/outputs/`
- KB validation
- KB health checks
- checked-in examples
- CI smoke coverage

Interpretation:

- the KB layer is real
- it is inspectable
- it is downstream of governed memory rather than a second truth store

## What Materially Improved In The Last Cycle

This section matters because not all improvements had the same architectural weight.

### A. What improved benchmark confidence

The repo strengthened proof more than it changed the algorithm.

The biggest benchmark realities are:

- official-public judged `BEAM` evidence is now much stronger across the large-context scales
- the local strong lanes remain intact
- the benchmark-report CLI can now summarize noisy benchmark artifact churn much more precisely

The long benchmark-report enrichment lane improved:

- observability
- drilldown quality
- artifact triage
- recommended follow-up navigation

That work is useful, but it mostly improves benchmark hygiene and operator visibility, not the memory substrate itself.

### B. What improved product integration readiness

The most important product-adjacent improvement is that Spark shadow replay and the KB compiler are now connectable.

Before:

- Spark shadow replay existed
- KB compile existed
- they were adjacent tools

Now:

- a shadow replay can directly produce a governed memory snapshot
- that snapshot can directly compile a KB vault
- a batch of replay slices can accumulate into one vault
- a Builder export with common alias fields can be normalized into that path

This is the first real bridge from Builder-shaped traffic to a visible external-brain surface.

The new Telegram path matters because it gives us a lightweight real-chat proving lane before deeper Spark product wiring:

- Telegram bot messages can now be normalized into the same shadow replay contract
- those messages can be replayed through governed memory
- the replay can emit the same shadow report, failure taxonomy, and KB vault as the Builder path
- this creates a practical operator loop for testing memory behavior with a handful of real conversations before broader benchmark resumption

The most practical version of that loop now targets Builder's own Telegram runtime artifacts directly:

- Builder already owns live Telegram polling
- Builder already writes `.tmp-telegram-*.json` update artifacts during local/runtime verification
- `run-spark-builder-telegram-intake <builder_dir> <output_dir>` now scans those artifacts directly and pushes them through the same memory report, failure taxonomy, and KB compile path
- this is now the shortest path from "send a few messages to the Telegram bot" to "inspect memory behavior and a human-readable KB surface"

We now also have a stronger Builder-native replay bridge that reads the persisted runtime event log instead of temp files:

- Builder homes persist `state.db`
- `telegram_runtime` writes `intent_committed` and `delivery_succeeded` events there
- `run-spark-builder-state-telegram-intake <builder_home> <output_dir>` now reconstructs conversations from those events and pushes them through the same memory report, failure taxonomy, and KB compile path
- `run-spark-builder-state-telegram-intake <builder_home> <output_dir> --chat-id <telegram_chat_id>` now scopes replay to one live Telegram thread, which is the most practical way to test a few fresh bot messages without replaying the full Builder Telegram history
- this is the best current bridge for real Telegram memory testing because it captures both inbound user text and outbound delivered replies from the Builder runtime itself

### C. What did not improve enough yet

These still remain materially underbuilt:

- real Spark traffic evidence
- direct runtime metrics
- KB-as-answer-path integration
- cross-source syntheses inside the KB
- benchmarked proof that `memory + KB` beats memory alone

## Current Completion Matrix

This is the shortest high-signal read of the system right now.

### A. Memory runtime

Status: strong

What is true:

- benchmark-serious on multiple surfaces
- correction and contradiction handling are strong
- long-horizon reconstruction is strong
- the runtime already has governed writes, reads, maintenance hooks, and snapshot export

What is not yet true:

- not every public evidence class is closed
- exact-official `BEAM` judge parity is still open
- runtime metrics are not yet first-class

### B. Spark connection

Status: real but still shadow-first

What is true:

- replay contract exists
- Builder-export alias normalization exists
- single-file and batch replay-to-KB bridges exist
- Spark-shaped data can already enter the governed-memory-plus-KB path

What is not yet true:

- no live Spark API or DB wiring
- no persistent real-traffic replay backlog yet
- no measured failure taxonomy on real Builder exports yet
- no promotion gate based on real Spark usage metrics yet

### C. KB / LLM wiki layer

Status: real but still early

What is true:

- there is a visible compiled markdown layer
- the KB is downstream of governed memory
- the KB is inspectable and health-checkable
- the KB already supports source pages, syntheses, filed outputs, and maintenance reports

What is not yet true:

- it is not yet a rich external-brain product
- it does not yet have broad cross-source research ingest
- it does not yet have broad query-answer filing against the wiki itself
- it is not yet part of a proven answer-time improvement loop

### D. Combined memory plus KB system

Status: hypothesis stage

What is true:

- memory is strong
- KB is real
- Spark-shaped data can feed the KB

What is not yet true:

- there is no clean A/B proving `memory + KB` beats `memory only`
- no stable read-time integration doctrine has been proven under benchmark load
- no latency-versus-quality tradeoff has been measured honestly yet

## Current Architecture Read

### The correct architecture split

Spark should own:

- conversation flow
- user intent interpretation
- policy and permissions
- final answer assembly
- product-specific orchestration

The memory runtime should own:

- typed writes
- typed reads
- provenance-bearing retrieval
- abstention
- maintenance hooks
- governed snapshot export

The KB layer should own:

- human-readable compiled pages
- provenance surfaces
- timeline and state inspection
- filed answer pages
- contradiction, staleness, and gap visibility

The KB should not own truth.

The KB should be:

- compiled from governed memory
- inspectable by users and operators
- a product surface
- an external-brain layer

That is the right Karpathy-style shape for this repo.

### What the architecture is still missing

The strongest missing architectural pieces are:

1. a real Spark-side entity and field normalizer
2. a real Spark-side memory write gate
3. a real Spark-side query router
4. runtime metrics emitted from actual Spark usage
5. a first-class compile loop from governed memory plus approved sources into richer wiki pages
6. a benchmarked read path that can use the KB layer when it helps

## What Is Still Missing

### 1. Remaining benchmark proof gaps

These are still open:

- broader clean `LoCoMo`
- canonical `GoodAI`
- exact-official upstream OpenAI judge parity for `BEAM`

Interpretation:

- the system is strong
- the proof stack is not fully complete

### 2. Remaining Spark gaps

Still missing:

- replayable real Builder trace batches from product traffic
- longitudinal shadow reports on actual traffic
- product failure taxonomy from real traces
- live promotion criteria backed by measured Spark behavior

### 3. Remaining KB gaps

Still missing:

- incremental ingest of external articles, repos, papers, and datasets
- cross-source concept pages beyond runtime memory pages
- broad filed query outputs generated against the wiki itself
- scheduled compile loops
- richer contradiction and gap-filling passes
- Obsidian-native dashboard surfaces

### 4. Remaining combined-system gap

Most important missing truth:

- we do not yet have a clean measured claim that `memory + KB together` improves benchmark results over memory alone

That is not a philosophical gap. It is an experimental gap.

## What Must Be True Before We Can Honestly Claim Memory Plus KB Improvement

The repo should not claim that the combined system is better until all of these are true:

1. the KB is wired into the actual answer path being evaluated, not only compiled after the fact
2. there is a clear `memory only` baseline on the same slice
3. there is a clear `memory + KB` run on that same slice
4. latency and cost deltas are measured alongside answer quality
5. the comparison is narrow enough that failures can still be explained mechanistically

Until then, the correct language is:

- the KB improves inspectability and human readability now
- it may improve answer quality later
- that answer-quality claim is not proven yet

## What We Know About Memory Plus KB Right Now

The honest answer today is:

- the KB layer is real
- the memory layer is strong
- the combined system has not yet been benchmarked cleanly as a combined answer path

What we do know:

- the KB can now be compiled from governed memory snapshots
- Spark-shaped shadow and Builder-export conversations can feed that path
- the KB improves inspectability, human readability, and post-hoc synthesis potential

What we do not know yet:

- how much it helps retrieval quality on benchmarked answers
- whether it improves difficult temporal, contradiction, or summarization categories
- whether it adds latency or drift that outweighs benefits

So the next phase should treat `memory + KB` as a hypothesis to test, not as a claim already proven.

## Where We Are Lacking Most

If we are ruthless about leverage, the main deficiencies are:

### A. Product-shaped evidence is weaker than benchmark evidence

We have stronger benchmark proof than Spark product proof.

That means the next best move is not another benchmark-only detour.

It is:

- get real Spark exports through the new bridges
- inspect the resulting runtime and KB surfaces
- learn from that

### B. Human-readable knowledge still lags behind memory quality

The memory runtime is more mature than the KB product surface.

Right now, the system knows more than the user-facing or operator-facing KB exposes.

That is exactly where the Karpathy-style wiki layer should help:

- turn hidden state into visible pages
- turn replay evidence into inspectable history
- turn benchmark failures into dossiers
- turn mutation rationale into durable product knowledge

### C. The mutation loop is still more benchmark-centric than Spark-centric

The next serious architecture mutations should be informed by both:

- benchmark failure clusters
- Spark trace failure clusters

If we only optimize for benchmarks, the product can still fail.
If we only optimize for product traces, benchmark rigor can degrade.

The next loop has to use both.

## Exact Recommended Next Phase

This is the recommended sequence for the next few days.

## Day 1: Lock the Spark export bridge as the new intake path

Goal:

- prove we can take real Spark Builder exports and compile a real KB vault without hand editing

Required actions:

1. obtain one real Spark Builder export batch
2. run:
   - `run-spark-builder-intake-batch`
3. inspect:
   - accepted vs rejected writes
   - missing structured hints
   - unsupported reasons
   - generated current-state pages
   - generated evidence pages
   - generated filed outputs
4. document failures as a first Spark failure taxonomy

Definition of success:

- real Builder export enters the repo path cleanly
- KB compile succeeds
- health checks pass
- we know exactly what Builder metadata is still missing

## Day 2: Make the KB materially more useful

Goal:

- upgrade the KB from "correct scaffold" to "useful operator and user surface"

Required actions:

1. add richer filed outputs from Spark replay:
   - per-conversation summaries
   - current-state deltas
   - unsupported-write dossiers
2. add first cross-source syntheses:
   - runtime memory overview
   - Spark replay summary
   - benchmark proof status
3. add first mutation dossier pages:
   - what failed
   - why it failed
   - what to test next

Definition of success:

- the KB becomes a useful readable workspace
- it starts to tell operators what happened, not just mirror files

## Day 3: Start the first combined-system experiment

Goal:

- measure whether the KB can help the answer path instead of just documenting it

Required actions:

1. choose a narrow evaluation slice
2. define two modes:
   - memory only
   - memory plus compiled KB support
3. run a controlled comparison
4. inspect:
   - answer quality change
   - provenance quality
   - latency cost
   - failure mode shifts

Definition of success:

- one honest A/B result exists
- even a negative result is useful if it clarifies where KB helps and where it does not

## Day 4 And After: Resume the open benchmark lanes with stronger product context

Once Spark integration is less speculative, return to the remaining proof stack:

1. exact-official `BEAM` judge parity
2. broader clean `LoCoMo`
3. canonical `GoodAI`

But do it with a better loop:

- benchmark failures become KB dossiers
- Spark failures become KB dossiers
- mutations are justified by both

## Workstream Done Criteria

These are the stop conditions that should prevent the next few days from drifting.

### Spark connection workstream

This workstream is done enough for the next phase when:

- at least one real Builder export batch passes through the repo without hand editing
- the resulting KB compile is healthy
- we have a written failure taxonomy from that real export
- we know which Builder fields or metadata still need to be exported or normalized

### KB workstream

This workstream is done enough for the next phase when:

- the KB tells a readable story about what happened in a replay batch
- filed outputs include more than one demo answer page
- benchmark failures and Spark failures can both be represented as KB pages
- a human operator can inspect provenance, contradictions, and stale claims without reading raw JSON

### Combined-system experiment workstream

This workstream is done enough for the next phase when:

- one narrow A/B exists
- the repo has a written answer about quality delta, latency delta, and failure-mode shift
- we know whether to continue widening the KB answer path or keep it as an inspection layer longer

### Benchmark workstream

This workstream is done enough for the next phase when:

- the currently closed lanes remain stable as regression gates
- one next evidence class is chosen explicitly instead of mixing several at once
- resumed benchmark work is informed by Spark and KB findings, not isolated from them

## Concrete Gaps To Close In Spark

These are the concrete Spark-side requirements that should now be treated as implementation targets, not vague doctrine:

1. stable subject/predicate normalization
2. explicit write-worthiness gating
3. explicit read routing
4. provenance-preserving rendering
5. replay batch export on demand
6. batch report persistence over time
7. periodic maintenance execution
8. artifact storage for replay and KB outputs

The current repo now gives Spark a clean place to plug into these targets.

## Concrete Gaps To Close In The KB

These are the most valuable KB upgrades next:

1. richer filed outputs from real Spark traces
2. benchmark failure pages
3. mutation dossier pages
4. cross-source concept and entity pages
5. scheduled compile loops
6. contradiction and stale-claim dashboards
7. Dataview or Obsidian-native readable rollups

The guiding rule is:

- the KB should make the system more readable to humans and more useful to downstream LLM reasoning

It should not become another opaque storage layer.

## Concrete Gaps To Close In Benchmarks

### Preserve first

Do not casually disturb:

- `ProductMemory`
- `LongMemEval_s`
- local `BEAM 128K`
- alternate judged `BEAM` closure

These should behave like regression gates.

### Then close remaining evidence classes

In order:

1. exact-official `BEAM` judge parity
2. next clean `LoCoMo` lane
3. first canonical `GoodAI`

### Then test the combined story

After the Spark and KB path is cleaner:

1. memory only
2. Spark-shaped memory path
3. memory plus KB

That is the honest way to claim improvement.

## General Insights For The Next Few Days

These are the biggest strategic insights from the current repo state.

### 1. The best next move is Spark-first, not benchmark-first

The benchmark story is already good enough to justify product integration work.

The bigger uncertainty now is:

- how this behaves in Spark-shaped use
- what Builder metadata is missing
- how readable and useful the KB is on real traces

So the next move should be Spark-first.

### 2. The KB is now strategically important

The KB is no longer optional polish.

It is the layer that can:

- make memory inspectable
- support human trust
- preserve mutation reasoning
- expose failures and provenance
- potentially support stronger answer-time synthesis later

That is exactly why the Karpathy-style wiki layer matters here.

### 3. The next architecture improvements should be small and evidence-led

Do not broad-rewrite the memory engine now.

Instead:

1. identify failure clusters
2. map them to mechanisms
3. define a small mutation
4. rerun the relevant lane

This is now the right maturity model for the repo.

### 4. Human readability is a real product goal

Human readability is not secondary to benchmark quality.

In this system it is part of quality because:

- it makes state auditable
- it makes errors legible
- it makes corrections explainable
- it makes the KB an actual external brain instead of a file dump

The next KB work should explicitly optimize for this.

## Practical Restart Order

If work resumes later, this should be the order:

1. get a real Spark Builder export batch
2. run `build-spark-kb-from-builder-export`
3. inspect the replay and KB outputs
4. write the first Spark failure taxonomy
5. upgrade the KB pages based on what is missing
6. define the first memory-only vs memory-plus-KB comparison
7. then return to the remaining open benchmark closures

## Resume Checklist After Spark Connection Work

Once the immediate Spark connection push is complete, the next restart should be:

1. confirm the real-export path still works end to end
2. capture the missing Builder metadata and unsupported-write reasons in documentation
3. convert the first real Spark failures into KB dossier pages
4. decide whether the first A/B slice should be Spark-shaped replay, benchmark slice, or both
5. run the first `memory only` vs `memory + KB` comparison
6. only after that, resume the next open benchmark evidence lane

This ordering matters.

The bad order would be:

- go straight back into broad benchmark work
- leave Spark integration ambiguous
- leave the KB readable but non-operational

The correct order is:

- Spark intake first
- KB usefulness second
- combined-system measurement third
- wider benchmark closure fourth

## Questions This Document Should Still Answer Later

If someone returns to this repo after the Spark push, this file should still answer:

1. what was already strong before touching Spark again
2. what actually shipped in the recent cycle
3. whether the KB was already real or still hypothetical
4. what was still missing before a truthful `memory + KB` claim
5. what exact order to resume in

If any of those answers becomes unclear, this file should be updated rather than replaced by another overlapping roadmap.

## Commands To Remember

### Builder and Spark replay

```powershell
python -m domain_chip_memory.cli normalize-spark-builder-export <builder_export.json> --write <normalized.json>
python -m domain_chip_memory.cli normalize-spark-builder-export-batch <builder_export_dir> --write <normalized.json>
python -m domain_chip_memory.cli run-spark-shadow-report-from-builder-export <builder_export.json> --write <report.json>
python -m domain_chip_memory.cli run-spark-shadow-report-from-builder-export-batch <builder_export_dir> --write <report.json>
python -m domain_chip_memory.cli build-spark-shadow-failure-taxonomy-from-builder-export <builder_export.json> --write <taxonomy.json>
python -m domain_chip_memory.cli build-spark-shadow-failure-taxonomy-from-builder-export-batch <builder_export_dir> --write <taxonomy.json>
python -m domain_chip_memory.cli build-spark-kb-from-builder-export <builder_export.json> <output_dir> --write <summary.json>
python -m domain_chip_memory.cli build-spark-kb-from-builder-export-batch <builder_export_dir> <output_dir> --write <summary.json>
python -m domain_chip_memory.cli run-spark-builder-intake-batch <builder_export_dir> <output_dir> --write <intake.json>
python -m domain_chip_memory.cli build-spark-kb-from-shadow-replay <shadow.json> <output_dir> --write <summary.json>
python -m domain_chip_memory.cli build-spark-kb-from-shadow-replay-batch <shadow_dir> <output_dir> --write <summary.json>
```

### KB validation

```powershell
python -m domain_chip_memory.cli validate-spark-kb-inputs <snapshot_file>
python -m domain_chip_memory.cli build-spark-kb <snapshot_file> <output_dir>
python -m domain_chip_memory.cli spark-kb-health-check <output_dir>
```

### Benchmark artifact triage

```powershell
python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir artifacts/benchmark_runs --repo-root . --only-noisy --summary-only --top-series-limit 5
```

## Worktree Reminder

The repo still tends to accumulate unrelated untracked benchmark and tmp artifacts under:

- `artifacts/benchmark_runs/`
- `artifacts/tmp/`
- `tmp/`

These should continue to be treated as separate from the narrow tracked implementation line unless a specific cleanup or promotion lane is active.

## Bottom Line

The project is now strong enough that the next phase should not be "more theory."

The right next phase is:

- connect real Spark exports
- make the KB genuinely readable and useful
- use Spark and benchmark failures together to guide mutations
- then finish the remaining benchmark proof surfaces

The memory system is already serious.
The KB is real but early.
The Spark bridge is now real enough to start using.

The next job is to turn those three truths into one coherent product and one coherent proof story.
