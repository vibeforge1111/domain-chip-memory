# Product Memory Local Eval

Date: 2026-03-26
Status: active local eval lane

## Purpose

This repo now has a first dedicated local `ProductMemory` evaluation lane.

It exists so the architecture can be judged on product-memory behavior with the same runner and scorecard discipline used for benchmark work.

This lane is intentionally local and bounded.

It is not a public benchmark claim.

## Current task families

- `correction`
  - a user updates earlier memory and the system should reflect the corrected current state
- `deletion`
  - a user asks for memory removal and the system should avoid serving stale deleted state
- `stale_state_drift`
  - a value changes, changes again, then re-enters, and the system should return the active state instead of stale intermediate state
- `evidence_preservation`
  - historical facts should remain recoverable from evidence memory even after current-state deletion and later update

## Why this matters

The harmonized doctrine says benchmark wins and real-world UX must come from the same substrate.

This lane makes that test concrete.

The first goal is not to brag about high scores.

The first goal is to create honest visibility into product-memory behavior that normal benchmark slices do not fully capture.

## Entrypoint

```powershell
python -m domain_chip_memory.cli demo-product-memory-scorecards
```

## Current local status

As of 2026-03-26, the two lead memory systems are now `12/12` on this lane:

- `observational_temporal_memory`: `correction` x7, `deletion` x3, `stale_state_drift`, `evidence_preservation`
- `dual_store_event_calendar_hybrid`: `correction` x7, `deletion` x3, `stale_state_drift`, `evidence_preservation`

The deletion closure came from substrate work, not responder-only cleanup:

- extraction now emits explicit `state_deletion` observations for delete intents on current-state facts
- predicate-level delete intents like `forget my favorite color` are handled even when the deleted value is not restated
- current-state reflection suppresses deleted predicates until a newer explicit update arrives
- later explicit updates clear the deletion tombstone and restore normal current-state answering
- deleting one facet does not wipe unrelated current-state facets in the same memory profile
- contradictory corrections can intentionally roll back to an earlier value without treating that older value as stale forever
- rolling back one facet does not clobber unrelated current-state facets that were never edited
- a deleted value can be restored explicitly, including when the restored value is the same as the deleted one
- current-state answer selection now returns `unknown` instead of resurfacing stale deleted state
- superseded historical evidence can still be recovered when the user asks a historical question instead of a current-state question

This is still a local eval, not a public product-memory benchmark claim.

The scorecard now reports this lane at two levels:

- `product_memory_task`
- `memory_operation`
- `memory_scope`

That makes it possible to see whether the architecture is strong on the broad task family but weak on a specific operator such as `delete_one_facet`, `update_after_delete`, or `rollback_to_prior_value`.

It also now reports the primary answer-candidate source and type, which is useful for architecture honesty:

- `observational_temporal_memory` is fully source-aligned on this local lane:
  - `current_state_memory` x8
  - `current_state_deletion` x3
  - `evidence_memory` x1
- `dual_store_event_calendar_hybrid` is now also source-aligned on this local lane:
  - `current_state_memory` x8
  - `current_state_deletion` x3
  - `evidence_memory` x1

That does not prove the role separation problem is solved globally, but it does mean the local product-memory lane no longer depends on an event-memory fallback for a current-state recovery.

The lane now also carries an explicit expected source contract per question via `expected_answer_candidate_source`.

That lets the scorecard measure `primary_answer_candidate_source_alignment` directly instead of relying on manual inspection.

As of the current local lane:

- `observational_temporal_memory`: `12/12` source-aligned
- `dual_store_event_calendar_hybrid`: `12/12` source-aligned

This is the first local product-memory check in the repo that directly tests memory-role hygiene rather than answer correctness alone.

## Source

The current local source lives in:

- `src/domain_chip_memory/sample_data.py`

under:

- `product_memory_samples()`
