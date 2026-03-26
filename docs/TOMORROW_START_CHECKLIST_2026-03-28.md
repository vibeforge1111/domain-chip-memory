# Tomorrow Start Checklist

Date: 2026-03-28
Status: active restart checklist

## Important reset

This checklist supersedes `docs/TOMORROW_START_CHECKLIST_2026-03-27.md`.

The active frontier is now the local `ProductMemory` lane at `690/690`, not the older BEAM-only restart memo.

## Start-of-day order

1. Confirm clean repo state on `origin/main`.
2. Confirm `HEAD` includes:
   - `716e909` `Add five-facet chronology inverse mixed-lifecycle coverage`
   - `5aec83a` `Update plan with five-facet chronology inverse mixed-lifecycle lane`
3. Re-read:
   - `docs/SESSION_LOG_2026-03-27.md`
   - `docs/IMPLEMENTATION_PLAN.md`
   - `docs/PRODUCT_MEMORY_LOCAL_EVAL_2026-03-26.md`
4. Start with one promotion only:
   - five-facet comparative inverse mixed-lifecycle scoped-pronoun lane
   - target middle clause: `About where I live and what I prefer, update it earlier instead.`
5. Decide immediately:
   - if both lead systems still pass, promote the lane as the next sample pair
   - if either system fails, fix the shared substrate first
6. Only after that lane is closed, decide whether to keep expanding this family or pivot to substrate consolidation.

## Exact first benchmark task

Promote the already-green next local lane:

- edge clause 1: `About my favorite color, please forget it.`
- middle clause: `About where I live and what I prefer, update it earlier instead.`
- edge clause 2: `About where I live, change it to Sharjah.`

Expected post-promotion state:

- `observational_temporal_memory`: `706/706`
- `dual_store_event_calendar_hybrid`: `706/706`
- expected source mix:
  - `current_state_memory` x214
  - `current_state_deletion` x48
  - `evidence_memory` x208
  - `temporal_ambiguity` x33
  - `referential_ambiguity` x203

## Exact first implementation task

Add the next pair as:

- `product-memory-pronoun-turn-43`
- `product-memory-pronoun-ambiguity-43`

Use the same five-facet inverse mixed-lifecycle structure as the last three lanes, but swap the ambiguous middle clause to the comparative form.

## Mandatory guardrails

- do not skip the already-probed next lane and jump straight to a new family
- do not accept a current-state win without source-alignment confirmation
- do not let documentation drift behind the promoted lane count
- do not mix unrelated artifact noise into the commit unless it has real semantic changes

## End-of-day success criteria

Tomorrow counts as productive if all of these are true:

1. the comparative inverse mixed-lifecycle lane is either promoted or blocked by one documented failing probe
2. both lead systems were rerun on the full local `ProductMemory` scorecard
3. the lane total is either explicitly advanced to `706/706` or the blocker is documented honestly
4. the next move after that lane is named clearly:
   - either a new structural family
   - or the first real consolidation pass on the shared memory substrate
