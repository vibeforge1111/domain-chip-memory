# Tasks

Date: 2026-03-27
Status: active

## Objective

Turn the current memory SDK and Spark integration surface into a production-safe rollout path without losing benchmark strength.

## Phase 1: Keep Spark In Shadow Mode

- Keep the Spark Intelligence Builder integration on `shadow-only`.
- Do not promote the memory SDK to the primary live memory layer yet.
- Use the orchestration prompt and integration contract as the current Builder doctrine.
- Require replayable traces and reports before any broader rollout decision.

## Phase 2: Finish The Maintenance Contract Surface

- Add the SDK maintenance replay contract summary.
- Add checked-in example maintenance replay payloads.
- Add a docs page for the maintenance replay schema and usage.
- Add a CLI contract command for maintenance replay, parallel to the Spark shadow contract commands.

## Phase 3: Get Real Spark Shadow Trace Batches

- Have Spark export Builder-style shadow replay files.
- Require each replay file to include:
- `turns`
- normalized write attempts
- probes
- `session_id`
- `turn_id`
- `timestamp`
- Preserve enough metadata for deterministic replay and provenance inspection.

## Phase 4: Replay Spark Traces In This Repo

- Run `run-spark-shadow-report` on single trace files.
- Run `run-spark-shadow-report-batch` on trace directories.
- Run `run-sdk-maintenance-report` on explicit SDK write traces.
- Collect:
- accepted writes
- rejected writes
- skipped turns
- unsupported write reasons
- probe hit rates
- memory-role mix
- maintenance before/after results

## Phase 5: Turn Shadow Failures Into Runtime Fixes

- Fix bad write gating.
- Fix wrong read routing.
- Fix stale current-state behavior.
- Fix missing abstentions.
- Fix weak provenance propagation.
- Fix reconsolidation gaps.
- Prefer narrow, benchmark-backed fixes over broad rewrites.

## Phase 6: Re-Run Benchmark Safety Gates After Behavior Changes

- After each real runtime mutation, rerun:
- local `ProductMemory`
- local `BEAM`
- targeted `LoCoMo`
- targeted `LongMemEval_s`
- Do not merge behavior changes that regress the active benchmark baseline without explicit documentation.

## Phase 7: Add A Spark Rollout Gate

- Define promotion criteria from shadow evidence, not intuition.
- Require:
- high accepted-write precision
- low residue persistence
- correct abstentions
- stable provenance
- maintenance that preserves current-state and historical read quality

## Phase 8: Move To Limited Assist Mode

- First live scope should stay narrow.
- Start with:
- explicit profile facts
- explicit preferences
- explicit events
- Do not begin with broad conversational memory.

## Immediate Next Actions

- Here in this repo:
- build the maintenance replay contract summary
- add maintenance replay docs and examples
- prepare the replay analysis workflow for incoming Spark traces

- On the Spark side:
- finish adapter wiring
- emit the first shadow trace batch

- After the first trace batch lands:
- replay it here
- inspect the reports
- convert failures into substrate fixes
- rerun benchmark safety gates

## Definition Of Done For This Stage

- Spark can export shadow traces reliably.
- This repo can replay Spark traces and produce stable reports.
- We can identify memory failures from those reports and fix them safely.
- Benchmark strength remains intact after runtime fixes.
- Only then do we consider limited live rollout.
