# Tomorrow Start Checklist

Date: 2026-03-27
Status: active restart checklist

## Important reset

This checklist supersedes `docs/TOMORROW_START_CHECKLIST_2026-03-26.md`.

The active frontier is now the local `BEAM` pressure ladder through `v22`, not the older `LongMemEval_s 201-225` baseline restart note.

## Start-of-day order

1. Confirm clean repo state on `origin/main`.
2. Confirm `HEAD` is `2779325`.
3. Re-read:
   - `docs/SESSION_LOG_2026-03-26.md`
   - `docs/IMPLEMENTATION_PLAN.md`
   - `docs/BEAM_LOCAL_PILOT_SLICE_2026-03-25.md`
4. Start with one probe only:
   - relative non-location state anchored on a non-location state transition
   - target example: `What did I prefer after I switched back to espresso?`
   - companion example: `What was my favorite color after I switched back to espresso?`
5. Decide immediately:
   - if both lead systems already pass, promote the lane to `beam_local_pilot_v23_source.json`
   - if either system fails, fix the shared substrate first
6. After `v23` is closed, start the first consolidation task from today's lesson:
   - make answer-candidate precedence explicit across packet assembly and responder logic

## Mandatory guardrails

- do not go back to the old `201-225` memo unless the plan is explicitly changed again
- do not add a new BEAM lane before closing the first probe of the day
- do not accept provider or responder overrides that contradict an explicit packet `answer_candidate`
- keep both lead systems on the same slice before calling a lane closed

## Exact first benchmark task

Probe the next BEAM pressure:

- anchor type: non-location state transition
- target state: `preference`
- companion state: `favorite_color`
- question family: relative `after`
- success condition: both lead systems answer correctly on the same bounded mini-slice

## Exact first implementation task

Open the answer-candidate precedence consolidation pass.

Initial target:

- document one explicit rule that packet-level `answer_candidate` beats weaker heuristic overlap
- identify the next code boundary after `responders.py`
- decide whether that contract belongs in typed metadata, packet assembly, or provider normalization

## End-of-day success criteria

Tomorrow counts as productive if all of these are true:

1. `BEAM v23` either exists or is blocked by one documented failing probe
2. both lead systems were rerun on the new pressure lane
3. the answer-candidate precedence rule is documented as implementation doctrine
4. the next consolidation boundary is named in code, not only in prose
