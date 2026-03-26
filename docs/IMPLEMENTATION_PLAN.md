# Agent Memory Implementation Plan

Date: 2026-03-22
Status: phase planning

## Phase 0: Research scaffold

Goal:

- establish the same repo shape as the other Spark domain chips
- lock the first build thesis with enough source-backed research to constrain implementation

Deliverables:

- manifests
- docs
- research lanes
- schemas
- watchtower and evaluator
- first-version research lock

## Phase 1: Benchmark substrate

Goal:

- make the benchmarks first-class local objects

Deliverables:

- benchmark adapters for `LongMemEval`, `LoCoMo`, and `GoodAI LTM Benchmark`
- normalized session and question contracts
- baseline runner
- public target ledger refresh command

Shadow deliverable:

- `ConvoMem` regression adapter or compatible evaluator path

Frontier deliverable:

- `BEAM` adapter contract once the public implementation surface is pinned
- `BEAM` scorecard contract that can track million-token stress slices separately from shorter benchmark slices

## Phase 2: Baseline memory systems

Goal:

- establish honest comparison points before novel architecture work

Deliverables:

- full-context baseline
- naive retrieval baseline
- memory-atom baseline
- category-level reports

## Phase 3: Candidate memory engine

Goal:

- implement a memory system that can reasonably challenge public leaders
- implement it in a way that can extend to `BEAM` without sacrificing already-closed `LongMemEval_s` and `LoCoMo` slices

Current lead lane as of 2026-03-25:

- `observational_temporal_memory + MiniMax-M2.7` is the active `LongMemEval` optimization path
- real rerun on March 23, 2026 over the first 25 `LongMemEval_s` samples: `25/25` (`1.00`)
- real rerun on March 23, 2026 over the first 50 `LongMemEval_s` samples: `50/50` (`1.00`)
- real rerun on March 24, 2026 over `LongMemEval_s` samples `51-75`: `25/25` (`1.00`)
- real rerun on March 24, 2026 over `LongMemEval_s` samples `76-100`: `25/25` (`1.00`)
- real rerun on March 24, 2026 over `LongMemEval_s` samples `101-125`: `25/25` (`1.00`)
- real rerun on March 24, 2026 over `LongMemEval_s` samples `126-150`: `25/25` (`1.00`)
- real rerun on March 25, 2026 over `LongMemEval_s` samples `151-175`: `25/25` (`1.00`)
- real rerun on March 25, 2026 over `LongMemEval_s` samples `176-200`: `25/25` (`1.00`)
- contiguous measured `LongMemEval_s` coverage through sample `200`: `200/200` (`1.00`)
- current bounded `LoCoMo` same-provider ladder on the first 25 `conv-26` questions:
  - `observational_temporal_memory`: `24/25` raw, `24/24` audited
  - `dual_store_event_calendar_hybrid`: `23/25` raw, `23/24` audited
  - `beam_temporal_atom_router`: `6/25` raw, `6/24` audited
- real rerun on March 24, 2026 over the next 25 `LoCoMo` `conv-26` questions (`q26-50`):
  - `observational_temporal_memory`: `25/25` raw, `25/25` audited
- real rerun on March 24, 2026 over the next bounded `LoCoMo` `conv-26` questions (`q51-75`):
  - `observational_temporal_memory`: `25/25` raw, `25/25` audited
- real rerun on March 24, 2026 over the next bounded `LoCoMo` `conv-26` questions (`q76-100`):
  - `observational_temporal_memory`: `25/25` raw, `25/25` audited
- real rerun on March 24, 2026 over the next bounded `LoCoMo` `conv-26` questions (`q101-125`):
  - `observational_temporal_memory`: `25/25` raw, `25/25` audited
  - measured progression on the same slice: `1/25 -> 23/25 -> 25/25`
- real rerun on March 24, 2026 over the next bounded `LoCoMo` `conv-26` questions (`q126-150`):
  - `observational_temporal_memory`: `25/25` raw, `25/25` audited
  - measured progression on the same slice: `3/25 -> 23/25 -> 24/25 -> 25/25`
- real rerun on March 25, 2026 over `LoCoMo conv-30 q1-25`:
  - `observational_temporal_memory`: `25/25` raw, `25/25` audited
- measured `LoCoMo conv-26` tail status after `q150`:
  - scoreable subset `q151`, `q152`, `q168`, `q179`: `4/4`
  - the wider `q151-199` tail is benchmark-contaminated because many gold answers are empty in the source file
- current clean `LoCoMo` limitation:
  - the remaining first-slice audited-open issue is still the benchmark inconsistency on `conv-26-qa-6`
- current local `BEAM` pilot ladder as of 2026-03-26:
  - `observational_temporal_memory`: `60/60`
  - `dual_store_event_calendar_hybrid`: `60/60`
  - currently closed pressure families include:
    - dated state recall at month, day, and clock-time granularity
    - event-anchored state recall
    - relative non-location state recall
    - timed repeated-anchor state recall
    - ambiguity abstention
    - location-anchored relative non-location state recall
    - non-location-transition-anchored relative non-location state recall
- current local `ProductMemory` lane as of 2026-03-26:
  - `observational_temporal_memory`: `446/446`
  - `dual_store_event_calendar_hybrid`: `446/446`
  - covered operation families now include:
    - explicit correction
    - explicit deletion with and without restated value
    - stale-state drift / re-entry
    - historical evidence preservation after current-state deletion and later update
    - non-location historical evidence preservation after explicit correction, including broader change/update-style phrasing
    - pre-delete historical evidence recall for both location and non-location facts
    - slot-explicit pre-delete historical recall such as `before I deleted where I live`
    - mixed slot-plus-target historical recall such as `before I changed where I live to Sharjah`
    - fronted-clause historical recall such as `Before I changed my favorite color to green, what was my favorite color?`
    - longer multi-clause historical recall with extra discourse filler
    - anaphoric historical recall such as `What was my favorite color before that update?`
    - explicit ambiguity abstention when generic anchors like `that update` or `that move` have more than one plausible target
    - cross-facet generic-anchor binding when another facet changed nearby but the asked facet remains unambiguous
    - operation-specific anchor binding when `that deletion` or similar phrasing must bind to a delete event instead of a later update on the same facet
    - dense-turn clause binding when delete/update operations are mentioned in the same utterance but must stay distinguishable
    - pronoun-scoped turn binding when a turn says `forget it` / `change it` after locally scoping the target facet
    - explicit referential-ambiguity abstention when a pronoun-scoped turn points to more than one plausible facet
    - temporal wording disambiguation when questions use phrases like `that earlier change`, `that later update`, or `that later deletion`
    - first/last temporal wording disambiguation when questions use phrases like `that first change`, `that last update`, or `that last deletion`
    - clause-heavy temporal wording disambiguation when questions add conversational suffixes like `we talked about`, `we mentioned`, or month phrases like `in May`
    - competing clause-modifier disambiguation when questions combine discourse filler with `earlier` or `later` delete anchors on the same facet
    - mixed operation wording disambiguation when questions combine discourse filler with update-vs-delete operator selection on the same facet
    - multi-update ambiguity abstention when `earlier` or `later` update wording names more than two plausible same-facet update targets
    - cross-facet temporal wording disambiguation when nearby updates on another facet should not poison same-facet `earlier` or `later` delete-anchor binding
    - cross-facet update wording disambiguation when nearby updates on another facet should not poison same-facet `earlier` or `later` update-anchor binding
    - cross-facet update ambiguity abstention when the asked facet already has more than two plausible updates and another facet is also active nearby
    - mixed operation ambiguity disambiguation when same-facet delete anchors stay answerable even while same-facet `later update` wording must abstain under multi-update pressure and nearby other-facet activity
    - delete-side ambiguity escalation when same-facet `earlier` or `later` deletion wording must abstain under multi-deletion pressure even with dense nearby updates on another facet
    - mixed delete-overload competition when same-facet `later update` wording stays answerable but same-facet `later deletion` wording abstains under delete overload even with nearby other-facet deletions
    - first/last mixed-operation overload when same-facet `first` or `last` update/deletion wording must keep the correct operator family under mixed update/delete pressure
    - clause-heavy first/last overload when conversational suffixes like `we talked about` or `we mentioned` should not break `first` or `last` operator binding under mixed update/delete pressure
    - anaphoric first/last ambiguity when underspecified forms like `that first one` or `that last one` must abstain under mixed update/delete pressure instead of borrowing the latest evidence path
    - clause-carry anaphoric ambiguity when forms like `that first one we changed` or `that last one we removed` must also abstain under mixed update/delete pressure instead of falling back to generic evidence
    - dense clause-carry ambiguity when multi-clause forms like `before that first one we changed, and before that last one we removed` must abstain under mixed update/delete pressure instead of inheriting a stray evidence span
    - pronoun plus clause-carry ambiguity when the same multi-clause forms must still abstain under mixed update/delete pressure even if the underlying history was created from scoped `change it` / `forget it` turns
    - mixed-facet pronoun plus clause-carry competition when those same scoped turns target more than one plausible facet and must surface `referential_ambiguity` instead of drifting into the wrong slot
    - value-bearing mixed-facet ambiguity when clause-carry wording includes target values like `changed to green` but still leaves the facet under-specified and must surface `referential_ambiguity`
    - chronology-bearing mixed-facet ambiguity when clause-carry wording includes chronology cues like `changed in February` or `removed later` but still leaves the facet under-specified and must surface `referential_ambiguity`
    - fronted mixed-facet chronology-bearing ambiguity when questions start with clauses like `Before the one we changed in February...` or `Before the one we removed later...` and must still surface `referential_ambiguity` instead of drifting into a slot
    - fronted mixed-facet value-bearing ambiguity when questions start with clauses like `Before the one we changed to green...` or `Before the one we removed...` and must still surface `referential_ambiguity` instead of drifting into a slot
    - fronted mixed-facet pronoun plus clause-carry ambiguity when questions start with clauses like `Before the first one we changed and the last one we removed...` and must still surface `referential_ambiguity` instead of borrowing scoped discourse from one facet
    - fronted mixed-facet chronology-bearing pronoun ambiguity when questions start with clauses like `Before the first one we changed in January and the last one we removed later...` and must still surface `referential_ambiguity` instead of borrowing scoped discourse from one facet
    - delete-specific fronted pronoun ambiguity when questions start with clauses like `Before the one we removed later...` on scoped `forget it` histories and must still surface `referential_ambiguity` instead of borrowing one facet's delete trace
    - update-specific fronted pronoun ambiguity when questions start with clauses like `Before the one we changed...` on scoped `change it` histories and must still surface `referential_ambiguity` instead of borrowing one facet's update trace
    - lean fronted first/last pronoun ambiguity when questions start with clauses like `Before the first one...` or `Before the last one...` on scoped histories and must still surface `referential_ambiguity` instead of silently binding to one facet
    - lean fronted earlier/later pronoun ambiguity when questions start with clauses like `Before the earlier one...` or `Before the later one...` on scoped histories and must still surface `referential_ambiguity` instead of silently binding to one facet
    - clause-carry lean fronted earlier/later pronoun ambiguity when questions start with clauses like `Before the earlier one we changed...` or `Before the later one we removed...` on scoped histories and must still surface `referential_ambiguity` instead of silently binding to one facet
    - selective facet-preserving edits plus historical recall when deleting one facet and later updating another must preserve current-state separation and historical recall for both facets
    - rollback/edit sequences plus historical recall when rolling one facet back and later editing another must preserve current-state separation and historical recall for both facets
    - delete-plus-rollback sequences plus historical recall when deleting one facet after rolling another back must preserve current-state separation and historical recall for both facets
    - restore-after-delete plus other-facet-edit sequences when restoring one deleted facet and later editing another must preserve current-state separation and historical recall for both facets
    - three-facet restore/edit stability when restoring one deleted facet, editing a second facet, and leaving a third facet untouched must preserve all three current-state boundaries plus historical recall for the edited facets
    - three-facet restore-to-new-value stability when restoring a deleted facet to a different value, editing a second facet, and leaving a third facet untouched must preserve all three current-state boundaries plus historical recall for the edited facets
    - three-facet delete-plus-rollback stability when rolling one facet back, deleting a second facet, and leaving a third facet untouched must preserve all three current-state boundaries plus historical recall for the changed facets
    - three-facet delete-plus-restore-to-new-value stability when restoring one deleted facet to a different value, deleting a second facet, and leaving a third facet untouched must preserve all three current-state boundaries plus historical recall for the changed facets
    - explicit correction of a previously deleted facet plus another-facet rollback history must preserve current-state separation, third-facet stability, and the other facet's historical chain in the same sample
    - delete-after-correction plus another-facet rollback history must preserve the corrected facet's pre-delete state, current-state deletion, third-facet stability, and the other facet's historical chain in the same sample
    - contradictory correction on a previously deleted facet plus another-facet delete/restore history must preserve both lifecycle chains independently while keeping a third facet stable
    - mixed-lifecycle ambiguity across multiple facets must abstain cleanly when lean `before that change` phrasing leaves the asked facet's own lifecycle overdetermined instead of binding to the wrong chain
    - mixed-lifecycle disambiguation across multiple facets must bind the intended chain when the question names the target operation or target value explicitly enough
    - dense same-turn mixed lifecycles must still bind delete/update history by facet even when multiple facets mutate inside one user turn
    - pronoun-heavy same-turn mixed lifecycles must still bind delete/update history by facet even when scoped `forget it` / `change it` references are used across multiple facets
    - pronoun-heavy same-turn mixed-lifecycle ambiguity must abstain through `referential_ambiguity` when a scoped pronoun turn mutates more than one facet and a later history question asks `before that change`
    - pronoun-heavy same-turn mixed-lifecycle value-target disambiguation must still bind the intended facet when a later history question names the target value explicitly enough, like `before that change to green` or `before that change to Sharjah`
    - pronoun-heavy same-turn mixed-lifecycle value-bearing ambiguity must still abstain through `referential_ambiguity` when a later history question names a value like `before that change to blue` but the scoped pronoun turn still leaves the facet under-specified
    - pronoun-heavy same-turn mixed-lifecycle chronology-bearing ambiguity must still abstain through `referential_ambiguity` when a later history question names a time cue like `before that change in February` but the scoped pronoun turn still leaves the facet under-specified
    - pronoun-heavy same-turn mixed-lifecycle chronology-bearing value-target disambiguation must still bind the intended facet when a later history question combines both the time cue and the target value, like `before that change to green in February`
    - pronoun-heavy same-turn delete chronology disambiguation must still bind the intended facet when a later history question asks about `before that deletion in February` on a mixed-facet scoped-pronoun turn
    - pronoun-heavy same-turn delete chronology ambiguity must still abstain through `referential_ambiguity` when a later history question asks about `before that deletion in February` but the scoped pronoun turn itself still leaves the facet under-specified
    - pronoun-heavy same-turn earlier/later delete disambiguation must still bind the intended facet when a later history question asks about `before that earlier deletion` or `before that later deletion` on a mixed-facet scoped-pronoun turn
    - pronoun-heavy same-turn earlier/later delete ambiguity must still abstain through `referential_ambiguity` when `earlier` or `later` selects a turn but the scoped pronoun turn itself still leaves the facet under-specified
    - pronoun-heavy same-turn earlier/later update disambiguation must still bind the intended facet when a later history question asks about `before that earlier change` or `before that later update` on a mixed-facet scoped-pronoun turn
    - pronoun-heavy same-turn earlier/later update ambiguity must still abstain through `referential_ambiguity` when `earlier` or `later` selects a turn but the scoped pronoun turn itself still leaves the facet under-specified
    - pronoun-heavy same-turn clause-carry earlier/later update disambiguation must still bind the intended facet when a later history question asks about `before that earlier one we changed` or `before that later one we updated` on a mixed-facet scoped-pronoun turn
    - pronoun-heavy same-turn clause-carry earlier/later update ambiguity must still abstain through `referential_ambiguity` when those same clause-carry forms select a turn but the scoped pronoun turn itself still leaves the facet under-specified
    - pronoun-heavy same-turn clause-carry earlier/later delete disambiguation must still bind the intended facet when a later history question asks about `before that earlier one we removed` or `before that later one we deleted` on a mixed-facet scoped-pronoun turn
    - pronoun-heavy same-turn clause-carry earlier/later delete ambiguity must still abstain through `referential_ambiguity` when those same clause-carry forms select a turn but the scoped pronoun turn itself still leaves the facet under-specified
    - pronoun-heavy same-turn fronted clause-carry earlier/later disambiguation must still bind the intended facet when a later history question asks about `Before that earlier one we changed...` or `Before that later one we deleted...` on a mixed-facet scoped-pronoun turn
    - pronoun-heavy same-turn fronted clause-carry earlier/later ambiguity must still abstain through `referential_ambiguity` when those same fronted clause-carry forms select a turn but the scoped pronoun turn itself still leaves the facet under-specified
    - pronoun-heavy same-turn fronted clause-carry first/last ambiguity must still abstain through `referential_ambiguity` when those same fronted clause-carry forms select a turn but the scoped pronoun turn itself still leaves the facet under-specified
    - pronoun-heavy same-turn fronted clause-carry first/last disambiguation must still bind the intended facet when a later history question asks about `Before that first one we changed...` or `Before that last one we deleted...` on a mixed-facet scoped-pronoun history whose operation family is uniquely recoverable
    - pronoun-heavy same-turn fronted value-bearing clause-carry first/last wording must still bind on the single-facet scoped-turn surface while abstaining through `referential_ambiguity` on the mixed-facet scoped-turn surface when the later question asks about `Before that first one we changed to green...` or `Before that last one we changed to Sharjah...`
    - pronoun-heavy same-turn fronted chronology-bearing clause-carry first/last wording must still bind on the single-facet scoped-turn surface while abstaining through `referential_ambiguity` on the mixed-facet scoped-turn surface when the later question asks about `Before that first one we changed in January...` or `Before that last one we deleted later...`
    - dense fronted same-turn chronology-bearing clause-carry first/last wording must still bind on the single-facet scoped-turn surface while abstaining through `referential_ambiguity` on the mixed-facet scoped-turn surface when the later question combines both anchors in one clause
    - dense fronted same-turn value-bearing clause-carry first/last wording must still bind on the single-facet scoped-turn surface while abstaining through `referential_ambiguity` on the mixed-facet scoped-turn surface when the later question combines both anchors with explicit values in one clause
    - dense fronted same-turn value-bearing clause-carry earlier/later wording must still bind on the single-facet scoped-turn surface while abstaining through `referential_ambiguity` on the mixed-facet scoped-turn surface when the later question combines comparative anchors with explicit values in one clause
    - dense fronted same-turn chronology-bearing clause-carry earlier/later wording must still bind on the single-facet scoped-turn surface while abstaining through `referential_ambiguity` on the mixed-facet scoped-turn surface when the later question combines comparative anchors with explicit timing cues in one clause
    - dense fronted same-turn mixed-operation value-bearing clause-carry earlier/later wording must still bind on the single-facet scoped-turn surface while abstaining through `referential_ambiguity` on the mixed-facet scoped-turn surface when the later question combines an explicit target value on one anchor and a delete anchor on the other
    - dense fronted same-turn mixed-operation value-plus-chronology clause-carry earlier/later wording must still bind on the single-facet scoped-turn surface while abstaining through `referential_ambiguity` on the mixed-facet scoped-turn surface when the later question combines an explicit target value on one anchor and a chronology-qualified delete anchor on the other
    - three-facet same-turn scoped-pronoun binding must preserve current-state separation and historical recall when one clause updates favorite color, another deletes and restores location, and a third updates preference in the same turn
    - three-facet same-turn scoped-pronoun ambiguity must still surface `referential_ambiguity` when one mixed clause scopes favorite color, location, and preference together instead of cleanly separating the facets
    - mixed three-facet scoped-pronoun partial clause separability must preserve current-state updates and historical recall for the cleanly scoped clauses while keeping the genuinely mixed clause on `referential_ambiguity` instead of collapsing the whole turn
    - overlapping-scope three-facet scoped-pronoun partial clause separability must preserve current-state updates and historical recall for the cleanly scoped clauses even when one of those facets also appears inside a separate mixed clause that should remain on `referential_ambiguity`
    - inverse-overlap three-facet scoped-pronoun partial clause separability must preserve both clean updates and their historical anchors when the ambiguous middle clause overlaps each clean clause on opposite sides instead of letting the middle ambiguity wipe out both edges
    - value-bearing ambiguous-middle three-facet scoped-pronoun partial clause separability must preserve the clean edge clauses even when the ambiguous middle clause names a target value like `change it to blue`, with the middle clause still routed to `referential_ambiguity`
    - chronology-bearing ambiguous-middle three-facet scoped-pronoun partial clause separability must preserve the clean edge clauses even when the ambiguous middle clause carries a cue like `change it in February`, with the middle clause still routed to `referential_ambiguity`
    - delete-oriented chronology-bearing ambiguous-middle three-facet scoped-pronoun partial clause separability must preserve the clean edge clauses even when the ambiguous middle clause says `forget it in February`, with the middle clause still routed to `referential_ambiguity`
    - comparative delete/update ambiguous-middle three-facet scoped-pronoun partial clause separability must preserve the clean edge clauses even when the ambiguous middle clause says `forget it later`, with the middle clause still routed to `referential_ambiguity`
    - comparative update ambiguous-middle three-facet scoped-pronoun partial clause separability must preserve the clean edge clauses even when the ambiguous middle clause says `update it later`, with the middle clause still routed to `referential_ambiguity`
    - four-facet same-turn scoped-pronoun overlap stability must preserve clean favorite-color, location, and preference updates while the ambiguous middle clause still routes to `referential_ambiguity` and an untouched dog-breed facet remains stable in current-state answering
    - four-facet same-turn scoped-pronoun inverse-overlap stability must preserve clean favorite-color and location edge updates while the ambiguous middle clause overlaps favorite color plus preference, with dog-breed staying untouched and the middle clause still routing to `referential_ambiguity`
    - four-facet delete-side scoped-pronoun inverse-overlap stability must preserve clean favorite-color deletion state and pre-delete history while the ambiguous middle delete clause overlaps favorite color plus preference, a far-edge clean location update still binds, and dog-breed stays untouched
    - four-facet delete-side value-bearing scoped-pronoun inverse-overlap stability must preserve the same clean delete/history split even when the ambiguous middle clause carries an explicit target value like `update it to blue later`
    - four-facet delete-side chronology-bearing scoped-pronoun inverse-overlap stability must preserve the same clean delete/history split even when the ambiguous middle clause carries a timing cue like `update it later in February`
    - relearn after deletion
    - selective deletion with unrelated-facet preservation
    - contradictory correction with explicit rollback to a prior value
    - restore a deleted value, including reasserting the exact same value
  - scorecards now slice this lane by `product_memory_task`, `memory_operation`, and `memory_scope`
  - scorecards now also expose primary answer-candidate source/type so product-memory wins can be checked against the intended memory role
  - local product-memory questions now declare `expected_answer_candidate_source`, and scorecards measure `primary_answer_candidate_source_alignment`
  - current instrumentation note:
    - both lead systems answer this lane through `current_state_memory` x90, `current_state_deletion` x14, `evidence_memory` x174, `temporal_ambiguity` x33, and `referential_ambiguity` x135
    - both lead systems are now `446/446` source-aligned on the local lane

Candidate components:

- multi-pass observer ingestion
- temporal and supersession layer
- retrieval router
- single answer layer with abstention
- offline consolidation worker

Initial candidate systems:

- System 1: `EPI + ATOM + TIME + ROUTE + REHYDRATE + ABSTAIN`
- System 2: `OBSERVE + REFLECT + TIME + PROFILE + ABSTAIN`
- System 3: `OBSERVE + ATOM + TIME + EVENTS + ROUTE + REHYDRATE + RELATE + ABSTAIN`

Deferred until after the lightweight baseline is measured:

- search-agent ensembles
- answer forests
- graph-database-first infra
- learned memory-control policies

## Phase 3A: BEAM readiness track

Goal:

- restructure the winning lane so it can survive million-token pressure while preserving current benchmark wins

Required constraints:

- keep `LongMemEval_s` and `LoCoMo` as regression gates
- do not treat current partial coverage as full-benchmark victory

Deliverables:

- explicit working-memory, episodic-memory, stable-memory, and scratchpad-memory role separation
- stronger hybridization path between observational memory and temporal-event structure
- offline consolidation hooks for large-context pressure
- compaction and rehydration rules that preserve exact answer-bearing spans
- architecture ablations that test whether `BEAM`-oriented changes keep current `LongMemEval_s` and `LoCoMo` wins intact

Current operating read as of 2026-03-26:

- the repo is no longer blocked on a vague `BEAM` adapter story
- the local `BEAM` pilot ladder is now the active frontier pressure track
- the next step is not adding random new slices; it is using each new slice to expose shared substrate debt
- the most recent exposed debt was answer-candidate obedience across packet assembly and heuristic response

## Phase 3B: Architecture consolidation track

Goal:

- turn the current winning lane into a cleaner memory substrate instead of an ever-growing benchmark rescue layer

Why now:

- the repo has enough measured wins to justify consolidation work
- `LongMemEval_s` is closed through sample `200`
- recent wins exposed real architectural debt in `memory_systems.py` and `providers.py`

Primary doctrine:

- keep the benchmark flywheel running
- start substrate consolidation in parallel
- prefer generic operators over question-shaped branches

Required architecture moves:

- separate raw episodic evidence, structured evidence memory, current-state memory, and derived belief memory
- make supersession and current-state selection explicit instead of packet-local heuristics
- introduce typed `answer_candidate` metadata so exact numeric, currency, date, and abstention answers are preserved before provider rescue
- split extraction, update logic, operators, and packet assembly into separate module surfaces
- add architecture ablations that distinguish:
  - extraction gains
  - update and supersession gains
  - retrieval gains
  - operator gains
  - provider-rescue gains

Reference memo:

- `docs/MEMORY_ARCHITECTURE_EVOLUTION_PLAN_2026-03-25.md`
- `docs/UNIFIED_MEMORY_SYSTEM_PROGRAM_2026-03-25.md`
- `docs/HARMONIZED_MEMORY_DOCTRINE_2026-03-26.md`

Implementation path as of 2026-03-26:

1. Continue expanding the local `BEAM` ladder one honest pressure family at a time.
2. Prefer pressure families that test state anchors, supersession, and answer integrity, not only more location chronology.
3. After each new closed lane, capture the architectural lesson and decide whether the fix belongs in:
   - extraction
   - anchor resolution
   - typed answer-candidate metadata
   - packet assembly
   - responder or provider normalization
4. Use the first post-`v22` consolidation pass to turn answer-candidate precedence into explicit doctrine instead of heuristic spillover.
5. Only return to older benchmark expansion memos if the `BEAM`-first path stops yielding transferable substrate lessons.

## Phase 4: Mutation flywheel

Goal:

- improve by repeated benchmark pressure, not vibes

Deliverables:

- mutation packet schema
- evaluation packet schema
- automatic failure bucketing
- rollback policy

## Phase 5: Promotion discipline

Goal:

- decide what actually deserves to become product doctrine

Promotion gates:

- benchmark improvement
- no major category regression
- attribution satisfied
- implementation understandable enough to maintain
