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
  - historical facts should remain recoverable from evidence memory even after current-state deletion and later update or correction, including broader correction and deletion phrasing, slot-explicit delete paraphrases, mixed slot-plus-target update phrasing, fronted-clause question forms, longer multi-clause variants, and anaphoric anchors like `that change`
- `ambiguity_abstention`
  - if a generic historical anchor like `that update` or `that move` has more than one plausible target, the system should abstain instead of inventing a chronology
- `cross_facet_disambiguation`
  - if another facet changed nearby, a generic anchor like `that change` should still bind to the asked facet instead of drifting across memory roles
- `operation_disambiguation`
  - if delete and update operations both happened on the same facet, operation-specific anchors like `that deletion` should bind to the right event instead of drifting to the latest state update
- `dense_turn_disambiguation`
  - if delete and update clauses appear in the same conversational turn, the system should still bind the intended operation instead of collapsing them together

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

As of 2026-03-26, the two lead memory systems are now `38/38` on this lane:

- `observational_temporal_memory`: `correction` x7, `deletion` x3, `stale_state_drift`, `evidence_preservation` x16, `ambiguity_abstention` x3, `cross_facet_disambiguation` x2, `operation_disambiguation` x2, `dense_turn_disambiguation` x4
- `dual_store_event_calendar_hybrid`: `correction` x7, `deletion` x3, `stale_state_drift`, `evidence_preservation` x16, `ambiguity_abstention` x3, `cross_facet_disambiguation` x2, `operation_disambiguation` x2, `dense_turn_disambiguation` x4

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
- non-location correction anchors like `before I corrected it to green` and `before I changed it to green` are now normalized into the same relative-state operator instead of requiring separate heuristic lanes
- deletion-history anchors like `before I deleted it`, `before I removed it`, and `before I forgot it` now route into predicate-specific delete anchors instead of collapsing to the latest current-state value
- slot-explicit delete history phrasing like `before I deleted where I live` now also routes into the same delete anchor instead of leaking through current-state retrieval
- mixed slot-plus-target phrasing like `before I changed where I live to Sharjah` and `before I updated my favorite color to green` is now locked into the local lane as regression coverage
- fronted-clause forms like `Before I changed my favorite color to green, what was my favorite color?` now route into the same relative-state operator instead of defaulting to the latest evidence
- longer multi-clause forms like `Before I changed my favorite color to green, when we were still using the old one, what was my favorite color?` are now also covered locally
- anaphoric forms like `What was my favorite color before that update?` and `Before that move, where did I live?` now route through a generic target-change anchor instead of requiring explicit slot restatement
- ambiguous generic anchors like `What did I prefer before that update?` and multi-update histories like `Where did I live before that move?` now abstain explicitly through `temporal_ambiguity` instead of relying on accidental fallback behavior
- cross-facet competition is now locked down locally, so `What was my favorite color before that change?` still binds to favorite-color history even when a location update happened nearby, and the location version behaves symmetrically
- operation-specific binding is now also covered, so `What was my favorite color before that deletion?` and `Where did I live before that deletion?` bind to the actual delete event even after later updates on the same facet
- dense same-turn phrasing is now covered too, so utterances like `Please forget my favorite color, and after that my favorite color is green` still let `that deletion` and `that update` resolve to the right clause

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
  - `evidence_memory` x24
  - `temporal_ambiguity` x3
- `dual_store_event_calendar_hybrid` is now also source-aligned on this local lane:
  - `current_state_memory` x8
  - `current_state_deletion` x3
  - `evidence_memory` x24
  - `temporal_ambiguity` x3

That does not prove the role separation problem is solved globally, but it does mean the local product-memory lane no longer depends on an event-memory fallback for a current-state recovery.

The lane now also carries an explicit expected source contract per question via `expected_answer_candidate_source`.

That lets the scorecard measure `primary_answer_candidate_source_alignment` directly instead of relying on manual inspection.

As of the current local lane:

- `observational_temporal_memory`: `38/38` source-aligned
- `dual_store_event_calendar_hybrid`: `38/38` source-aligned

This is the first local product-memory check in the repo that directly tests memory-role hygiene rather than answer correctness alone.

## Source

The current local source lives in:

- `src/domain_chip_memory/sample_data.py`

under:

- `product_memory_samples()`
