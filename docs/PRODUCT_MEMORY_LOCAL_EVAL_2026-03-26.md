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

As of 2026-03-26, the two lead memory systems are now `834/834` on this lane:

- `observational_temporal_memory`: `correction` x31, `deletion` x8, `stale_state_drift`, `evidence_preservation` x38, `ambiguity_abstention` x61, `cross_facet_disambiguation` x12, `operation_disambiguation` x2, `dense_turn_disambiguation` x10, `pronoun_turn_disambiguation` x189, `pronoun_referential_ambiguity` x214, `temporal_wording_disambiguation` x42
- `dual_store_event_calendar_hybrid`: `correction` x31, `deletion` x8, `stale_state_drift`, `evidence_preservation` x38, `ambiguity_abstention` x61, `cross_facet_disambiguation` x12, `operation_disambiguation` x2, `dense_turn_disambiguation` x10, `pronoun_turn_disambiguation` x189, `temporal_wording_disambiguation` x42, `pronoun_referential_ambiguity` x214

The deletion closure came from substrate work, not responder-only cleanup:

- extraction now emits explicit `state_deletion` observations for delete intents on current-state facts
- predicate-level delete intents like `forget my favorite color` are handled even when the deleted value is not restated
- current-state reflection suppresses deleted predicates until a newer explicit update arrives
- later explicit updates clear the deletion tombstone and restore normal current-state answering
- direct pet statements like `My dog is a beagle` now materialize `dog_breed` observations instead of falling through to an unrelated current-state answer path
- five-facet inverse mixed-lifecycle scoped-pronoun turns now explicitly cover the clean-delete edge, ambiguous location-plus-preference middle clause, far-edge clean location update, and untouched dog-breed plus bike-count stability split
- five-facet value-bearing inverse mixed-lifecycle scoped-pronoun turns now also cover the same inverse structure when the ambiguous middle clause carries an explicit target value like `update it to blue later`
- five-facet chronology-bearing inverse mixed-lifecycle scoped-pronoun turns now also cover the same inverse structure when the ambiguous middle clause carries a timing cue like `update it in February later`
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
- mixed-facet same-turn pronoun history ambiguity is now explicit too, so questions like `What was my favorite color before that change?` and `Where did I live before that change?` abstain through `referential_ambiguity` when the underlying scoped pronoun turn mutated more than one facet
- value-bearing mixed-facet same-turn pronoun history ambiguity is now explicit too, so questions like `What was my favorite color before that change to blue?` and `Where did I live before that change to blue?` still abstain through `referential_ambiguity` when a scoped pronoun turn leaves the facet under-specified
- chronology-bearing mixed-facet same-turn pronoun history ambiguity is now explicit too, so questions like `What was my favorite color before that change in February?` and `Where did I live before that change in February?` still abstain through `referential_ambiguity` when a scoped pronoun turn leaves the facet under-specified
- chronology-bearing value-target disambiguation on mixed-facet same-turn pronoun history is now explicit too, so questions like `What was my favorite color before that change to green in February?` and `Where did I live before that change to Sharjah in February?` bind the intended facet instead of abstaining
- delete-specific chronology-bearing disambiguation on mixed-facet same-turn pronoun history is now explicit too, so questions like `What was my favorite color before that deletion in February?` and `Where did I live before that deletion in February?` bind the intended facet instead of drifting across the mixed turn
- delete-specific chronology-bearing ambiguity on mixed-facet same-turn pronoun history is now explicit too, so those same `before that deletion in February` questions abstain through `referential_ambiguity` when the scoped pronoun turn itself still leaves the facet under-specified
- delete-specific earlier/later ambiguity on mixed-facet same-turn pronoun history is now explicit too, so questions like `What was my favorite color before that earlier deletion?` and `Where did I live before that later deletion?` still abstain through `referential_ambiguity` when `earlier` or `later` selects a turn but the scoped pronoun turn still leaves the facet under-specified
- delete-specific earlier/later disambiguation on mixed-facet same-turn pronoun history is now explicit too, so questions like `What was my favorite color before that earlier deletion?` and `Where did I live before that later deletion?` bind the intended facet instead of drifting across the mixed turn
- update-specific earlier/later ambiguity on mixed-facet same-turn pronoun history is now explicit too, so questions like `What was my favorite color before that earlier change?` and `Where did I live before that later update?` still abstain through `referential_ambiguity` when `earlier` or `later` selects a turn but the scoped pronoun turn still leaves the facet under-specified
- update-specific earlier/later disambiguation on mixed-facet same-turn pronoun history is now explicit too, so questions like `What was my favorite color before that earlier change?` and `Where did I live before that later update?` bind the intended facet instead of drifting across the mixed turn
- clause-carry earlier/later update disambiguation on mixed-facet same-turn pronoun history is now explicit too, so questions like `What was my favorite color before that earlier one we changed?` and `Where did I live before that later one we updated?` bind the intended facet instead of collapsing into generic `that one` ambiguity
- clause-carry earlier/later update ambiguity on mixed-facet same-turn pronoun history is now explicit too, so those same `that earlier one we changed` and `that later one we updated` forms still abstain through `referential_ambiguity` when `earlier` or `later` selects a turn but the scoped pronoun turn still leaves the facet under-specified
- clause-carry earlier/later delete disambiguation on mixed-facet same-turn pronoun history is now explicit too, so questions like `What was my favorite color before that earlier one we removed?` and `Where did I live before that later one we deleted?` bind the intended facet instead of collapsing into generic `that one` ambiguity
- clause-carry earlier/later delete ambiguity on mixed-facet same-turn pronoun history is now explicit too, so those same `that earlier one we removed` and `that later one we deleted` forms still abstain through `referential_ambiguity` when `earlier` or `later` selects a turn but the scoped pronoun turn still leaves the facet under-specified
- value-target disambiguation on mixed-facet same-turn pronoun history is now explicit too, so questions like `What was my favorite color before that change to green?` and `Where did I live before that change to Sharjah?` bind the intended facet instead of abstaining or leaking across slots
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
- fronted clause-carry earlier/later pronoun disambiguation is now explicit too, so forms like `Before that earlier one we changed...` and `Before that later one we deleted...` on mixed-facet scoped-pronoun histories now bind the intended facet instead of collapsing into fronted `that one` ambiguity
- fronted clause-carry earlier/later pronoun ambiguity is now explicit too, so those same `Before that earlier one we changed...` and `Before that later one we deleted...` forms now abstain through `referential_ambiguity` when the mixed-facet scoped-pronoun turn still does not uniquely identify the facet
- fronted clause-carry first/last pronoun ambiguity is now explicit too, so those same `Before that first one we changed...` and `Before that last one we deleted...` forms also abstain through `referential_ambiguity` when the mixed-facet scoped-pronoun turn still does not uniquely identify the facet
- fronted clause-carry first/last pronoun disambiguation is now explicit too, so those same `Before that first one we changed...` and `Before that last one we deleted...` forms bind the intended facet when the scoped-pronoun history is single-facet per turn and the operation family is uniquely recoverable
- fronted value-bearing clause-carry first/last pronoun competition is now explicit too, so forms like `Before that first one we changed to green...` and `Before that last one we changed to Sharjah...` bind the intended facet on single-facet scoped turns but still abstain through `referential_ambiguity` on the mixed-facet scoped-pronoun surface
- fronted chronology-bearing clause-carry first/last pronoun competition is now explicit too, so forms like `Before that first one we changed in January...` and `Before that last one we deleted later...` bind the intended facet on single-facet scoped turns but still abstain through `referential_ambiguity` on the mixed-facet scoped-pronoun surface
- dense fronted chronology-bearing clause-carry first/last pronoun competition is now explicit too, so forms like `Before that first one we changed in January, and before that last one we deleted later...` still bind the intended facet on single-facet scoped turns but abstain through `referential_ambiguity` on the mixed-facet scoped-pronoun surface
- dense fronted value-bearing clause-carry first/last pronoun competition is now explicit too, so forms like `Before that first one we changed to green, and before that last one we changed to Sharjah...` still bind the intended facet on single-facet scoped turns but abstain through `referential_ambiguity` on the mixed-facet scoped-pronoun surface
- dense fronted value-bearing clause-carry earlier/later pronoun competition is now explicit too, so forms like `Before that earlier one we changed to green, and before that later one we changed to Sharjah...` still bind the intended facet on single-facet scoped turns but abstain through `referential_ambiguity` on the mixed-facet scoped-pronoun surface
- dense fronted chronology-bearing clause-carry earlier/later pronoun competition is now explicit too, so forms like `Before that earlier one we changed in January, and before that later one we deleted later...` still bind the intended facet on single-facet scoped turns but abstain through `referential_ambiguity` on the mixed-facet scoped-pronoun surface
- dense fronted mixed-operation value-bearing clause-carry earlier/later pronoun competition is now explicit too, so forms like `Before that earlier one we changed to green, and before that later one we deleted...` still bind the intended facet on single-facet scoped turns but abstain through `referential_ambiguity` on the mixed-facet scoped-pronoun surface
- dense fronted mixed-operation value-plus-chronology clause-carry earlier/later pronoun competition is now explicit too, so forms like `Before that earlier one we changed to green, and before that later one we deleted later...` still bind the intended facet on single-facet scoped turns but abstain through `referential_ambiguity` on the mixed-facet scoped-pronoun surface
- three-facet same-turn scoped-pronoun binding is now explicit too, so one turn can independently update favorite color, delete-and-restore location, and update preference without collapsing current-state tracking back to the pre-turn values
- three-facet same-turn scoped-pronoun ambiguity is now explicit too, so a single mixed clause that scopes favorite color, location, and preference together still abstains through `referential_ambiguity` instead of pretending one facet was singled out
- mixed three-facet scoped-pronoun partial clause separability is now explicit too, so two clean scoped clauses can still materialize current-state updates and history anchors while a third mixed clause stays ambiguous instead of collapsing the whole turn into one ambiguity blob
- overlapping-scope three-facet scoped-pronoun partial clause separability is now explicit too, so a facet can appear in both a clean scoped clause and a separate mixed clause without breaking the clean clause's current-state update or history binding, while the mixed clause still abstains through `referential_ambiguity`
- inverse-overlap three-facet scoped-pronoun partial clause separability is now explicit too, so two clean scoped clauses can still survive when the ambiguous middle clause overlaps the first clean facet on one side and the second clean facet on the other, instead of wiping out both clean updates
- value-bearing ambiguous-middle three-facet scoped-pronoun partial clause separability is now explicit too, so an ambiguous middle clause that names a target value like `change it to blue` still fails safely through `referential_ambiguity` while the clean edge clauses keep their current-state updates and historical bindings
- chronology-bearing ambiguous-middle three-facet scoped-pronoun partial clause separability is now explicit too, so an ambiguous middle clause that carries a cue like `change it in February` still fails safely through `referential_ambiguity` while the clean edge clauses keep their current-state updates and historical bindings
- delete-oriented chronology-bearing ambiguous-middle three-facet scoped-pronoun partial clause separability is now explicit too, so an ambiguous middle clause that says `forget it in February` still fails safely through `referential_ambiguity` while the clean edge clauses keep their current-state updates and historical bindings
- comparative delete/update ambiguous-middle three-facet scoped-pronoun partial clause separability is now explicit too, so an ambiguous middle clause that says `forget it later` still fails safely through `referential_ambiguity` while the clean edge clauses keep their current-state updates and historical bindings
- comparative update ambiguous-middle three-facet scoped-pronoun partial clause separability is now explicit too, so an ambiguous middle clause that says `update it later` still fails safely through `referential_ambiguity` while the clean edge clauses keep their current-state updates and historical bindings
- four-facet scoped-pronoun overlap stability is now explicit too, so favorite color, location, and preference can all survive a same-turn clean-plus-mixed scoped update pattern while an untouched dog-breed facet still answers from current-state memory instead of leaking to another facet
- four-facet scoped-pronoun inverse-overlap stability is now explicit too, so two clean edge clauses can still preserve current-state updates and historical anchors when the ambiguous middle clause overlaps one clean facet plus another mutable facet, while an untouched dog-breed facet remains stable in current-state answering
- four-facet delete-side scoped-pronoun inverse-overlap stability is now explicit too, so a clean edge deletion can preserve current-state deletion and pre-delete history while the ambiguous middle delete clause overlaps that same facet plus another mutable facet, a far-edge clean location update still binds, and an untouched dog-breed facet remains stable
- four-facet delete-side value-bearing scoped-pronoun inverse-overlap stability is now explicit too, so a clean edge deletion can preserve current-state deletion and pre-delete history while the ambiguous middle value-bearing clause overlaps that same facet plus another mutable facet, the far-edge clean location update still binds, and untouched dog-breed stability remains intact
- four-facet delete-side chronology-bearing scoped-pronoun inverse-overlap stability is now explicit too, so the same clean delete/history split holds even when the ambiguous middle clause carries a timing cue like `update it later in February`, while the far-edge clean location update still binds and untouched dog-breed stability remains intact
- four-facet delete-side comparative scoped-pronoun inverse-overlap stability is now explicit too, so the same clean delete/history split holds when the ambiguous middle clause carries `earlier` or `later` wording, while the far-edge clean location update still binds and untouched dog-breed stability remains intact
- four-facet mixed-lifecycle scoped-pronoun overlap stability is now explicit too, so one clean edge deletion, one clean edge location update, one ambiguous mixed lifecycle clause, and one untouched dog-breed facet can coexist without breaking current-state separation, pre-delete history, or safe abstention on the overlapping clause
- four-facet mixed-lifecycle scoped-pronoun inverse-overlap stability is now explicit too, so the same delete plus update plus untouched-facet structure still holds when the ambiguous overlap clause sits between the clean delete edge and the far-edge clean update instead of after them
- four-facet mixed-lifecycle value-bearing scoped-pronoun inverse-overlap stability is now explicit too, so the same inverse overlap structure still holds when the ambiguous middle clause carries an explicit target value like `update it to blue later` instead of a lean update phrasing
- four-facet mixed-lifecycle chronology-bearing scoped-pronoun inverse-overlap stability is now explicit too, so the same inverse overlap structure still holds when the ambiguous middle clause carries a timing cue like `update it in February later` instead of a lean update phrasing
- four-facet mixed-lifecycle comparative scoped-pronoun inverse-overlap stability is now explicit too, so the same inverse overlap structure still holds when the ambiguous middle clause carries comparative wording like `update it earlier instead` instead of a lean update phrasing
- five-facet scoped-pronoun overlap stability is now explicit too, so a clean favorite-color deletion, a clean location update, an ambiguous location-plus-preference overlap clause, and untouched dog-breed plus bike-count facets can coexist without cross-facet leakage
- five-facet scoped-pronoun inverse-overlap stability is now explicit too, so a clean favorite-color deletion, an ambiguous favorite-color-plus-preference middle clause, a far-edge clean location update, and untouched dog-breed plus bike-count facets can coexist without cross-facet leakage
- five-facet value-bearing scoped-pronoun inverse-overlap stability is now explicit too, so the same clean delete edge, far-edge clean update, and untouched dog-breed plus bike-count facets still hold when the ambiguous middle clause carries an explicit target value like `update it to blue later`
- five-facet chronology-bearing scoped-pronoun inverse-overlap stability is now explicit too, so the same clean delete edge, far-edge clean update, and untouched dog-breed plus bike-count facets still hold when the ambiguous middle clause carries a timing cue like `update it in February later`
- five-facet comparative scoped-pronoun inverse-overlap stability is now explicit too, so the same clean delete edge, far-edge clean update, and untouched dog-breed plus bike-count facets still hold when the ambiguous middle clause carries comparative wording like `update it earlier instead`
- five-facet comparative inverse mixed-lifecycle scoped-pronoun stability is now explicit too, so the same clean delete edge, far-edge clean location update, and untouched dog-breed plus bike-count facets still hold when the ambiguous middle clause carries comparative wording like `update it earlier instead`
- six-facet comparative inverse mixed-lifecycle scoped-pronoun stability is now explicit too, so the same clean delete edge, far-edge clean location update, untouched dog-breed plus bike-count facets, and an untouched playlist facet still hold when the ambiguous middle clause carries comparative wording like `update it earlier instead`
- five-facet chronology-bearing scoped-pronoun overlap stability is now explicit too, so a clean favorite-color deletion, a clean location update, an ambiguous location-plus-preference overlap clause, and untouched dog-breed plus bike-count facets still hold when the overlapping clause carries a timing cue like `update it in February later`
- five-facet comparative scoped-pronoun overlap stability is now explicit too, so a clean favorite-color deletion, a clean location update, an ambiguous location-plus-preference overlap clause, and untouched dog-breed plus bike-count facets still hold when the overlapping clause carries comparative wording like `update it earlier instead`
- six-facet comparative scoped-pronoun overlap stability is now explicit too, so a clean favorite-color deletion, a clean location update, an ambiguous location-plus-preference overlap clause, and untouched dog-breed plus bike-count plus playlist facets still hold when the overlapping clause carries comparative wording like `update it earlier instead`
- six-facet value-bearing scoped-pronoun overlap stability is now explicit too, so the same clean favorite-color deletion, clean location update, ambiguous location-plus-preference overlap clause, and untouched dog-breed plus bike-count plus playlist facets still hold when the overlapping clause carries an explicit target value like `update it to blue later`
- six-facet chronology-bearing scoped-pronoun overlap stability is now explicit too, so the same clean favorite-color deletion, clean location update, ambiguous location-plus-preference overlap clause, and untouched dog-breed plus bike-count plus playlist facets still hold when the overlapping clause carries a timing cue like `update it in February later`
- six-facet comparative delete/update scoped-pronoun overlap stability is now explicit too, so the same clean favorite-color deletion, clean location update, ambiguous location-plus-preference overlap clause, and untouched dog-breed plus bike-count plus playlist facets still hold when the overlapping clause carries comparative delete wording like `please forget it later`
- six-facet comparative update scoped-pronoun overlap stability is now explicit too, so the same clean favorite-color deletion, clean location update, ambiguous location-plus-preference overlap clause, and untouched dog-breed plus bike-count plus playlist facets still hold when the overlapping clause carries comparative update wording like `update it later`
- seven-facet comparative update scoped-pronoun overlap stability is now explicit too, so the same clean favorite-color deletion, clean location update, ambiguous location-plus-preference overlap clause, and untouched dog-breed plus bike-count plus playlist plus instrument facets still hold when the overlapping clause carries comparative update wording like `update it later`
- current-state bike-count questions like `How many bikes do I own now?` now stay source-aligned on `current_state_memory` instead of being forced onto the generic aggregate/evidence path by the broad count-question gate
- selective facet-preserving edits plus historical recall are now explicit too, so deleting one facet and later updating another facet still preserves current-state separation and historical recall for both the deleted facet and the edited facet
- rollback/edit sequences plus historical recall are now explicit too, so rolling one facet back and later editing another facet still preserves current-state separation and historical recall for both facets
- delete-plus-rollback sequences plus historical recall are now explicit too, so deleting one facet after rolling another back still preserves current-state separation and historical recall for both facets
- restore-after-delete plus other-facet-edit sequences are now explicit too, so restoring one deleted facet and later editing another facet still preserves current-state separation and historical recall for both facets
- three-facet restore/edit stability is now explicit too, so restoring one deleted facet, editing a second facet, and leaving a third facet untouched still preserves all three current-state boundaries plus historical recall for the edited facets
- three-facet restore-to-new-value stability is now explicit too, so restoring a deleted facet to a different value, editing a second facet, and leaving a third facet untouched still preserves all three current-state boundaries plus historical recall for the edited facets
- three-facet delete-plus-rollback stability is now explicit too, so rolling one facet back, deleting a second facet, and leaving a third facet untouched still preserves all three current-state boundaries plus historical recall for the changed facets
- three-facet delete-plus-restore-to-new-value stability is now explicit too, so restoring one deleted facet to a different value, deleting a second facet, and leaving a third facet untouched still preserves all three current-state boundaries plus historical recall for the changed facets
- explicit correction of a previously deleted facet plus another-facet rollback history is now explicit too, so correcting one deleted facet while another facet carries its own rollback chain still preserves current-state separation, third-facet stability, and the other facet's historical chain in the same sample
- delete-after-correction plus another-facet rollback history is now explicit too, so correcting one facet, then deleting it later, still preserves the corrected facet's pre-delete state, current-state deletion, third-facet stability, and the other facet's historical chain in the same sample
- contradictory correction on a previously deleted facet plus another-facet delete/restore history is now explicit too, so one facet can carry a conflicting correction chain while another carries a delete/restore chain without contaminating either lifecycle or a stable third facet
- mixed-lifecycle ambiguity across multiple facets is now explicit too, so lean `before that change` phrasing abstains cleanly when the asked facet's own lifecycle is overdetermined instead of borrowing the wrong chain
- mixed-lifecycle disambiguation across multiple facets is now explicit too, so naming the target change precisely enough still binds the right chain even when another facet has a competing lifecycle active nearby
- dense same-turn mixed lifecycles are now explicit too, so delete/update history still binds by facet even when multiple facets mutate inside one conversational turn
- pronoun-heavy same-turn mixed lifecycles are now explicit too, so delete/update history still binds by facet even when scoped `forget it` / `change it` references are used across multiple facets

This is still a local eval, not a public product-memory benchmark claim.

The scorecard now reports this lane at two levels:

- `product_memory_task`
- `memory_operation`
- `memory_scope`

That makes it possible to see whether the architecture is strong on the broad task family but weak on a specific operator such as `delete_one_facet`, `update_after_delete`, or `rollback_to_prior_value`.

It also now reports the primary answer-candidate source and type, which is useful for architecture honesty:

- `observational_temporal_memory` is fully source-aligned on this local lane:
  - `current_state_memory` x286
  - `current_state_deletion` x62
  - `evidence_memory` x222
  - `temporal_ambiguity` x33
  - `referential_ambiguity` x231
- `dual_store_event_calendar_hybrid` is now also source-aligned on this local lane:
  - `current_state_memory` x286
  - `current_state_deletion` x62
  - `evidence_memory` x222
  - `temporal_ambiguity` x33
  - `referential_ambiguity` x231

That does not prove the role separation problem is solved globally, but it does mean the local product-memory lane no longer depends on an event-memory fallback for a current-state recovery.

The lane now also carries an explicit expected source contract per question via `expected_answer_candidate_source`.

That lets the scorecard measure `primary_answer_candidate_source_alignment` directly instead of relying on manual inspection.

As of the current local lane:

- `observational_temporal_memory`: `690/690` source-aligned
- `dual_store_event_calendar_hybrid`: `690/690` source-aligned

This is the first local product-memory check in the repo that directly tests memory-role hygiene rather than answer correctness alone.

## Source

The current local source lives in:

- `src/domain_chip_memory/sample_data.py`

under:

- `product_memory_samples()`
