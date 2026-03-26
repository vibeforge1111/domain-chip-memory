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

As of 2026-03-26, the two lead memory systems are now `11/11` on this lane:

- `observational_temporal_memory`: `correction` x7, `deletion` x3, `stale_state_drift`
- `dual_store_event_calendar_hybrid`: `correction` x7, `deletion` x3, `stale_state_drift`

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

This is still a local eval, not a public product-memory benchmark claim.

The scorecard now reports this lane at two levels:

- `product_memory_task`
- `memory_operation`

That makes it possible to see whether the architecture is strong on the broad task family but weak on a specific operator such as `delete_one_facet`, `update_after_delete`, or `rollback_to_prior_value`.

## Source

The current local source lives in:

- `src/domain_chip_memory/sample_data.py`

under:

- `product_memory_samples()`
