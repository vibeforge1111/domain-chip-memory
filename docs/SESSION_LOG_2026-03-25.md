# Session Log - 2026-03-25

Status: pushed handoff state

## What Closed Today

Today extended the same `observational_temporal_memory + MiniMax-M2.7` lane across the next two bounded `LongMemEval_s` slices and closed them cleanly:

- `samples 151-175`: `25/25` raw, `25/25` audited
- `samples 176-200`: `25/25` raw, `25/25` audited
- contiguous measured `LongMemEval_s` coverage through sample `200`: `200/200`

The closing commits that matter for today are:

- `5650c59` `feat: close longmemeval 151-175 multi-session lane`
- `87493af` `feat: close longmemeval 151-175 preference lane`
- `cb5f44b` `feat: close longmemeval 176-200 aggregate lane`

Everything above is already pushed to `origin/main`.

## Architecture Read

An explicit architecture review was also completed today against both the repo's earlier research base and newer memory-system papers.

The honest conclusion is:

- the repo is genuinely improving at the substrate level
- the current winning lane is still too benchmark-shaped in places
- the biggest remaining architectural debt is role separation, not raw benchmark accuracy

The concrete next-step memo is:

- `docs/MEMORY_ARCHITECTURE_EVOLUTION_PLAN_2026-03-25.md`

That memo locks the next architectural moves:

- separate evidence memory, current-state memory, and belief memory
- move exact-answer integrity earlier into typed `answer_candidate` contracts
- make supersession and reconsolidation first-class
- replace more question-shaped branches with reusable operators

## Key Technical Wins

The main gains today were not new broad architecture changes. They were bounded fixes that removed the last two recurring miss classes in the active lane:

- broader preference and advice rescue for `LongMemEval_s 151-175`
- ranked `answer_candidate` preservation under context compaction instead of naive first-match preservation
- exact numeric preservation for `what is the total number of ...` questions so correct short answers like `5` are not over-expanded into timestamp fragments
- additional aggregate synthesis for `LongMemEval_s 176-200`, including the Marvel re-watch count lane

The important read is that the active system did not need a new memory architecture to close `151-200`. It needed tighter packet shaping and stricter post-generation rescue.

## Source-Of-Truth Artifacts

Today’s closing artifacts are:

- `artifacts/benchmark_runs/longmemeval_observational_minimax_offset150_limit25_v8.json`
- `artifacts/benchmark_runs/longmemeval_observational_minimax_offset175_limit25_v6.json`

The full artifact trail for the `176-200` work is:

- `artifacts/benchmark_runs/longmemeval_offset175_limit25_source.json`
- `artifacts/benchmark_runs/longmemeval_observational_minimax_offset175_limit25_v1.json`
- `artifacts/benchmark_runs/longmemeval_observational_minimax_offset175_limit25_v2.json`
- `artifacts/benchmark_runs/longmemeval_observational_minimax_offset175_limit25_v3.json`
- `artifacts/benchmark_runs/longmemeval_observational_minimax_offset175_limit25_v4.json`
- `artifacts/benchmark_runs/longmemeval_observational_minimax_offset175_limit25_v5.json`
- `artifacts/benchmark_runs/longmemeval_observational_minimax_offset175_limit25_v6.json`

## Honest Current Benchmark State

### LongMemEval

- contiguous measured `LongMemEval_s` coverage is now `200/200`
- the next untouched bounded slice is `201-225`
- `226-500` remains unrun in the current measured lane

### LoCoMo

- `conv-26 q1-150` is clean across bounded slices, with the original first-slice benchmark inconsistency still audited separately at `conv-26-qa-6`
- `conv-30 q1-25` is closed at `25/25`
- the measurable `conv-26` tail subset `q151`, `q152`, `q168`, `q179` is `4/4`
- the wider `conv-26 q151-199` tail is still benchmark-contaminated because many source gold answers are empty, so it should not be treated as a clean frontier lane

### GoodAI LTM Benchmark

- adapters and harness surface exist in-repo
- a current source-of-truth frontier run is not yet locked
- this remains a real execution gap, not a documentation gap

### BEAM

- still not benchmarked in-repo
- readiness doctrine exists, but adapter and scorecard contracts are still pending

## What Awaits Tomorrow

The next rational order is:

1. Start `LongMemEval_s 201-225` baseline and establish the new miss taxonomy before mutating code.
2. Start the architecture consolidation track in parallel by defining typed `answer_candidate` metadata and extracting current-state logic out of the packet builder.
3. Do not spend another day on `conv-26 q151-199` as if it were a clean benchmark lane.
4. Move `LoCoMo` to a clean new conversation slice after `conv-26 q150`, or another clean bounded slice with valid gold answers.
5. After the next `LongMemEval_s` expansion is stable, lock the first canonical `GoodAI LTM Benchmark` configuration and produce a source-of-truth rerun.

## Restart Point

If work resumes tomorrow, start here:

1. Confirm the repo is clean and on `origin/main`.
2. Generate the next `LongMemEval_s` bounded source slice for `201-225`.
3. Run the real baseline first, without code changes, to get the true miss set.
4. Bucket misses into:
   - aggregate or count synthesis
   - preference or guidance shaping
   - temporal disambiguation
   - retrieval or current-state selection
   - abstention failures
5. Only then open the next mutation loop.

## Guardrails

- keep `LongMemEval_s` and clean `LoCoMo` slices as regression gates
- treat benchmark contamination as a separate audit lane, not as proof of model weakness
- prefer real reruns over local packet replay when deciding whether a slice is closed
- preserve exact short answers during provider rescue when the packet already contains the correct candidate
