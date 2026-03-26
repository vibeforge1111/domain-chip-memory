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
- `pronoun_turn_disambiguation`
  - if a turn scopes a facet and then says `forget it` or `change it`, the system should carry that local reference to the right slot instead of dropping back to generic evidence text
- `pronoun_referential_ambiguity`
  - if a turn scopes multiple possible referents and then says `forget it`, the system should abstain explicitly instead of binding the pronoun to the first facet it saw
- `temporal_wording_disambiguation`
  - if a historical question uses relative-time modifiers like `that earlier change` or `that later deletion`, the system should bind the right transition instead of collapsing into generic ambiguity

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

As of 2026-03-26, the two lead memory systems are now `180/180` on this lane:

- `observational_temporal_memory`: `correction` x13, `deletion` x5, `stale_state_drift`, `evidence_preservation` x24, `ambiguity_abstention` x59, `cross_facet_disambiguation` x10, `operation_disambiguation` x2, `dense_turn_disambiguation` x4, `pronoun_turn_disambiguation` x4, `pronoun_referential_ambiguity` x16, `temporal_wording_disambiguation` x42
- `dual_store_event_calendar_hybrid`: `correction` x13, `deletion` x5, `stale_state_drift`, `evidence_preservation` x24, `ambiguity_abstention` x59, `cross_facet_disambiguation` x10, `operation_disambiguation` x2, `dense_turn_disambiguation` x4, `pronoun_turn_disambiguation` x4, `temporal_wording_disambiguation` x42, `pronoun_referential_ambiguity` x16

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
- pronoun-heavy same-turn phrasing is now covered as well, so scoped turns like `About my favorite color, please forget it, and after that change it to green` materialize the right slot operations instead of falling back to generic evidence text
- mixed-facet pronoun scope is now handled explicitly too, so `About my favorite color and where I live, please forget it` surfaces `referential_ambiguity` instead of silently binding the deletion to the first scoped facet
- mixed-facet multi-operation pronoun scope is now also locked down, so turns like `About my favorite color and where I live, please forget it, and after that change it to green` abstain across both delete/update anchors instead of partially hallucinating one operation
- earlier/later temporal wording is now locked down too, so questions like `What was my favorite color before that earlier change?`, `What was my favorite color before that later update?`, `Where did I live before that earlier move?`, and `Where did I live before that later deletion?` bind to the right transition instead of being misclassified as `temporal_ambiguity` because of duplicate packet entries
- first/last temporal wording is now also locked down, so multi-update and multi-delete histories answer `before that first change`, `before that last update`, `before that first deletion`, and `before that last deletion` from `evidence_memory` instead of relying on whichever transition happened to be most recent
- clause-heavy temporal wording is now covered as well, so conversational forms like `before that first change we talked about`, `before that first move we mentioned`, and `before that later deletion in May` normalize back into the same generic temporal operators instead of falling through to latest-evidence retrieval
- competing clause modifiers on the same facet are now covered too, so forms like `before that earlier deletion we talked about` and `before that later deletion in August` still bind the intended delete event instead of collapsing the modifier away or defaulting to latest evidence
- mixed operation wording on the same facet is now covered too, so `before that earlier update we talked about` and `before that later deletion in October` still honor both the operation type and the chronology instead of only binding one of them
- the three-update ambiguity boundary is now explicit too, so `before that earlier update we talked about` and `before that later move in December` abstain through `temporal_ambiguity` once there are more than two plausible same-facet update targets
- cross-facet temporal wording is now locked down too, so nearby updates and deletions on another facet do not poison same-facet `earlier/later deletion` resolution even when the question adds discourse filler like `we talked about` or `in January`
- cross-facet update wording is now locked down as well, so nearby update histories on another facet do not poison same-facet `earlier/later update` resolution when the question adds discourse filler like `we talked about` or `in February`
- cross-facet update ambiguity is now explicit too, so once the asked facet itself has more than two plausible updates, `earlier/later update` wording abstains through `temporal_ambiguity` even if another facet has nearby updates that could have caused a false cross-slot leak
- mixed operation ambiguity is now explicit too, so once the asked facet itself has more than two plausible updates, `later update` wording still abstains through `temporal_ambiguity` even when delete anchors are present nearby, while `later deletion` wording on the same facet still binds to the delete event instead of inheriting update ambiguity
- delete-side ambiguity escalation is now explicit too, so once the asked facet itself has more than two plausible deletions, `earlier/later deletion` wording abstains through `temporal_ambiguity` even when another facet has dense nearby updates that could have caused a false operator leak
- mixed delete-overload competition is now explicit too, so with same-facet delete overload and nearby other-facet deletions, `later update` or `later move` wording still binds to the update family while `later deletion` wording abstains through `temporal_ambiguity` instead of leaking across operation families
- first/last mixed-operation overload is now explicit too, so `first/last update` and `first/last deletion` wording still bind to the correct operation family under mixed same-facet update/delete pressure instead of collapsing into the wrong chronology or the wrong operator
- clause-heavy first/last overload is now explicit too, so conversational suffixes like `we talked about` and `we mentioned` do not break `first/last` operator binding under the same mixed update/delete pressure
- anaphoric first/last wording is now explicit too, so underspecified forms like `that first one` and `that last one` abstain through `temporal_ambiguity` under mixed update/delete pressure instead of silently borrowing the latest evidence path
- clause-carry anaphoric wording is now explicit too, so forms like `that first one we changed` and `that last one we removed` also abstain through `temporal_ambiguity` instead of leaking back onto the generic evidence path
- dense clause-carry ambiguity is now explicit too, so multi-clause forms like `before that first one we changed, and before that last one we removed` also abstain through `temporal_ambiguity` instead of inheriting a stray evidence span
- pronoun plus clause-carry ambiguity is now explicit too, so the same multi-clause forms stay attributed to `temporal_ambiguity` even when the underlying history was built from scoped `change it` / `forget it` turns rather than explicit slot restatements
- mixed-facet pronoun plus clause-carry competition is now explicit too, so when those same scoped turns target more than one plausible facet, the local lane now requires `referential_ambiguity` instead of letting the system drift into the wrong slot
- value-bearing mixed-facet competition is now explicit too, so even when clause-carry wording mentions a target value like `changed to green`, the local lane still requires `referential_ambiguity` if the surface leaves the facet under-specified
- chronology-bearing mixed-facet competition is now explicit too, so chronology cues like `the one we changed in February` or `the one we removed later` still require `referential_ambiguity` when the facet remains under-specified
- fronted mixed-facet chronology-bearing competition is now explicit too, so fronted forms like `Before the one we changed in February, what was my favorite color?` and `Before the one we removed later, where did I live?` still require `referential_ambiguity` when the facet remains under-specified
- fronted mixed-facet value-bearing competition is now explicit too, so fronted forms like `Before the one we changed to green, what was my favorite color?` and `Before the one we removed, where did I live?` still require `referential_ambiguity` when the facet remains under-specified
- fronted mixed-facet pronoun plus clause-carry competition is now explicit too, so fronted forms built on scoped `change it` / `forget it` histories still require `referential_ambiguity` instead of borrowing discourse scope from one facet
- fronted mixed-facet chronology-bearing pronoun competition is now explicit too, so fronted forms built on scoped `change it` / `forget it` histories with month or later-style cues still require `referential_ambiguity` instead of borrowing discourse scope from one facet
- delete-specific fronted pronoun competition is now explicit too, so leaner fronted forms like `Before the one we removed later...` on scoped `forget it` histories still require `referential_ambiguity` instead of borrowing one facet’s delete trace
- update-specific fronted pronoun competition is now explicit too, so leaner fronted forms like `Before the one we changed...` on scoped `change it` histories still require `referential_ambiguity` instead of borrowing one facet’s update trace
- lean fronted first/last pronoun competition is now explicit too, so underspecified forms like `Before the first one...` and `Before the last one...` on scoped histories still require `referential_ambiguity` instead of silently binding to one facet
- lean fronted earlier/later pronoun competition is now explicit too, so underspecified forms like `Before the earlier one...` and `Before the later one...` on scoped histories still require `referential_ambiguity` instead of silently binding to one facet
- clause-carry lean fronted earlier/later pronoun competition is now explicit too, so forms like `Before the earlier one we changed...` and `Before the later one we removed...` on scoped histories still require `referential_ambiguity` instead of silently binding to one facet
- selective facet-preserving edits plus historical recall are now explicit too, so deleting one facet and later updating another facet still preserves current-state separation and historical recall for both the deleted facet and the edited facet
- rollback/edit sequences plus historical recall are now explicit too, so rolling one facet back and later editing another facet still preserves current-state separation and historical recall for both facets
- delete-plus-rollback sequences plus historical recall are now explicit too, so deleting one facet after rolling another back still preserves current-state separation and historical recall for both facets
- restore-after-delete plus other-facet-edit sequences are now explicit too, so restoring one deleted facet and later editing another facet still preserves current-state separation and historical recall for both facets

This is still a local eval, not a public product-memory benchmark claim.

The scorecard now reports this lane at two levels:

- `product_memory_task`
- `memory_operation`
- `memory_scope`

That makes it possible to see whether the architecture is strong on the broad task family but weak on a specific operator such as `delete_one_facet`, `update_after_delete`, or `rollback_to_prior_value`.

It also now reports the primary answer-candidate source and type, which is useful for architecture honesty:

- `observational_temporal_memory` is fully source-aligned on this local lane:
  - `current_state_memory` x14
  - `current_state_deletion` x5
  - `evidence_memory` x86
  - `temporal_ambiguity` x31
  - `referential_ambiguity` x44
- `dual_store_event_calendar_hybrid` is now also source-aligned on this local lane:
  - `current_state_memory` x14
  - `current_state_deletion` x5
  - `evidence_memory` x86
  - `temporal_ambiguity` x31
  - `referential_ambiguity` x44

That does not prove the role separation problem is solved globally, but it does mean the local product-memory lane no longer depends on an event-memory fallback for a current-state recovery.

The lane now also carries an explicit expected source contract per question via `expected_answer_candidate_source`.

That lets the scorecard measure `primary_answer_candidate_source_alignment` directly instead of relying on manual inspection.

As of the current local lane:

- `observational_temporal_memory`: `180/180` source-aligned
- `dual_store_event_calendar_hybrid`: `180/180` source-aligned

This is the first local product-memory check in the repo that directly tests memory-role hygiene rather than answer correctness alone.

## Source

The current local source lives in:

- `src/domain_chip_memory/sample_data.py`

under:

- `product_memory_samples()`
