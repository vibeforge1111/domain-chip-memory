# Today Plan - 2026-03-26

Status: active execution plan

## Date note

The current environment date is 2026-03-26.

The repo also contains `docs/TOMORROW_START_CHECKLIST_2026-03-27.md`, which was written on 2026-03-26 as the next-session restart memo. This document converts that handoff into the active plan for the current session.

## What Was Already Done

The implementation plan is no longer in vague planning mode. The repo has already closed substantial benchmark and architecture work:

- benchmark substrate exists for `LongMemEval`, `LoCoMo`, `GoodAI LTM Benchmark`, and the local `BEAM` pilot harness
- baseline comparison paths exist for `full_context`, retrieval, `observational_temporal_memory`, `dual_store_event_calendar_hybrid`, and related candidate systems
- `LongMemEval_s` has contiguous measured closure through sample `200/200`
- `LoCoMo` has clean measured closure through bounded `conv-26 q1-150` plus `conv-30 q1-25`, with the known contaminated `conv-26 q151-199` tail still treated honestly
- the local `BEAM` pilot ladder is closed through `v22`
- recent `BEAM` work exposed real substrate lessons, not only added more slices:
  - timed repeated-anchor routing
  - relative non-location state recall
  - ambiguity abstention
  - location-anchored relative non-location state recall
- typed `answer_candidate` contracts already exist in code, but precedence is still only partially enforced across the full packet -> responder -> provider path

## What Was Remaining

The main remaining work was already named in the 2026-03-26 session log and restart checklist:

- close the next unclosed `BEAM` lane:
  - relative non-location state recall anchored on a non-location state transition
  - target shape: `What did I prefer after I switched back to espresso?`
  - companion shape: `What was my favorite color after I switched back to espresso?`
- turn answer-candidate precedence into explicit implementation doctrine instead of responder/provider spillover
- identify the next code boundary after the immediate responder fix, likely across:
  - packet assembly
  - typed metadata
  - provider normalization

The broader program backlog also remains open, but it is not the first move for this session:

- `LongMemEval_s` expansion beyond sample `200`
- broader clean `LoCoMo` expansion beyond the currently closed bounded slices
- canonical `GoodAI LTM Benchmark` run promotion
- architecture consolidation across extraction, update logic, retrieval, operators, and packet assembly

## Today's Execution Order

1. Add and run the exact `v23` probe in tests first.
2. If both lead systems already pass, promote the lane into `beam_local_pilot_v23_source.json` and record both scorecards.
3. If either lead system fails, fix the shared substrate before promoting the slice.
4. Open the answer-candidate precedence consolidation pass immediately after `v23` is closed or blocked.
5. End the session with updated docs that clearly separate:
   - what closed
   - what remains
   - what should happen next

## Commit Cadence

Commit in small closed units:

- commit 1: session plan and restart alignment
- commit 2: `BEAM v23` probe or blocker capture
- commit 3: answer-candidate precedence consolidation boundary

## Success Criteria For This Session

This session counts as productive if all of these are true:

1. the repo has an explicit `v23` result:
   - either promoted coverage or a documented failing probe
2. both lead systems were checked against that pressure lane
3. answer-candidate precedence is documented as an implementation rule, not only a heuristic behavior
4. at least one code or module boundary for the consolidation pass is named concretely
