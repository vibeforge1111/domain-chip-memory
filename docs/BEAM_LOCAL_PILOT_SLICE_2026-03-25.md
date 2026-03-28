# BEAM Local Pilot Slice 2026-03-25

Status: active local pilot

## Purpose

This file pins the first in-repo BEAM pilot slice so the benchmark stops being only an architecture memo.

It is intentionally narrow:

- one local pilot sample
- shaped to the BEAM contract already added in code
- explicitly marked as an internal local slice, not the official public BEAM benchmark

## Truthfulness rule

This slice is not the official public BEAM benchmark path.

It exists to do three honest jobs now:

1. verify that the BEAM adapter, loader, CLI, and scorecard path work end to end
2. force the repo to track BEAM-style pressure slices explicitly
3. give the current lead system a small deterministic BEAM-oriented regression lane while the official public reproduction path is being pinned

Official public surfaces now exist:

- repo: `https://github.com/mohammadtavakoli78/BEAM`
- datasets:
  - `https://huggingface.co/datasets/Mohammadta/BEAM`
  - `https://huggingface.co/datasets/Mohammadta/BEAM-10M`

## Source-of-truth files

- source slice: `artifacts/benchmark_runs/beam_local_pilot_v1_source.json`
- first scorecard target: `artifacts/benchmark_runs/beam_local_pilot_observational_heuristic_v1.json`
- expanded slice: `artifacts/benchmark_runs/beam_local_pilot_v2_source.json`
- expanded scorecard target: `artifacts/benchmark_runs/beam_local_pilot_v2_observational_heuristic_v1.json`
- third slice: `artifacts/benchmark_runs/beam_local_pilot_v3_source.json`
- third-slice scorecard targets:
  - `artifacts/benchmark_runs/beam_local_pilot_v3_observational_heuristic_v1.json`
  - `artifacts/benchmark_runs/beam_local_pilot_v3_dual_store_heuristic_v2.json`
- fourth slice: `artifacts/benchmark_runs/beam_local_pilot_v4_source.json`
- fourth-slice scorecard targets:
  - `artifacts/benchmark_runs/beam_local_pilot_v4_observational_heuristic_v2.json`
  - `artifacts/benchmark_runs/beam_local_pilot_v4_dual_store_heuristic_v2.json`
- fifth slice: `artifacts/benchmark_runs/beam_local_pilot_v5_source.json`
- fifth-slice scorecard targets:
  - `artifacts/benchmark_runs/beam_local_pilot_v5_observational_heuristic_v3.json`
  - `artifacts/benchmark_runs/beam_local_pilot_v5_dual_store_heuristic_v4.json`
- sixth slice: `artifacts/benchmark_runs/beam_local_pilot_v6_source.json`
- sixth-slice scorecard targets:
  - `artifacts/benchmark_runs/beam_local_pilot_v6_observational_heuristic_v3.json`
  - `artifacts/benchmark_runs/beam_local_pilot_v6_dual_store_heuristic_v3.json`
- seventh slice: `artifacts/benchmark_runs/beam_local_pilot_v7_source.json`
- seventh-slice scorecard targets:
  - `artifacts/benchmark_runs/beam_local_pilot_v7_observational_heuristic_v1.json`
  - `artifacts/benchmark_runs/beam_local_pilot_v7_dual_store_heuristic_v1.json`
- eighth slice: `artifacts/benchmark_runs/beam_local_pilot_v8_source.json`
- eighth-slice scorecard targets:
  - `artifacts/benchmark_runs/beam_local_pilot_v8_observational_heuristic_v1.json`
  - `artifacts/benchmark_runs/beam_local_pilot_v8_dual_store_heuristic_v1.json`
- ninth slice: `artifacts/benchmark_runs/beam_local_pilot_v9_source.json`
- ninth-slice scorecard targets:
  - `artifacts/benchmark_runs/beam_local_pilot_v9_observational_heuristic_v1.json`
  - `artifacts/benchmark_runs/beam_local_pilot_v9_dual_store_heuristic_v1.json`
- tenth slice: `artifacts/benchmark_runs/beam_local_pilot_v10_source.json`
- tenth-slice scorecard targets:
  - `artifacts/benchmark_runs/beam_local_pilot_v10_observational_heuristic_v1.json`
  - `artifacts/benchmark_runs/beam_local_pilot_v10_dual_store_heuristic_v1.json`
- eleventh slice: `artifacts/benchmark_runs/beam_local_pilot_v11_source.json`
- eleventh-slice scorecard targets:
  - `artifacts/benchmark_runs/beam_local_pilot_v11_observational_heuristic_v1.json`
  - `artifacts/benchmark_runs/beam_local_pilot_v11_dual_store_heuristic_v1.json`
- twelfth slice: `artifacts/benchmark_runs/beam_local_pilot_v12_source.json`
- twelfth-slice scorecard targets:
  - `artifacts/benchmark_runs/beam_local_pilot_v12_observational_heuristic_v1.json`
  - `artifacts/benchmark_runs/beam_local_pilot_v12_dual_store_heuristic_v1.json`
- thirteenth slice: `artifacts/benchmark_runs/beam_local_pilot_v13_source.json`
- thirteenth-slice scorecard targets:
  - `artifacts/benchmark_runs/beam_local_pilot_v13_observational_heuristic_v1.json`
  - `artifacts/benchmark_runs/beam_local_pilot_v13_dual_store_heuristic_v1.json`
- fourteenth slice: `artifacts/benchmark_runs/beam_local_pilot_v14_source.json`
- fourteenth-slice scorecard targets:
  - `artifacts/benchmark_runs/beam_local_pilot_v14_observational_heuristic_v1.json`
  - `artifacts/benchmark_runs/beam_local_pilot_v14_dual_store_heuristic_v1.json`
- fifteenth slice: `artifacts/benchmark_runs/beam_local_pilot_v15_source.json`
- fifteenth-slice scorecard targets:
  - `artifacts/benchmark_runs/beam_local_pilot_v15_observational_heuristic_v1.json`
  - `artifacts/benchmark_runs/beam_local_pilot_v15_dual_store_heuristic_v1.json`
- sixteenth slice: `artifacts/benchmark_runs/beam_local_pilot_v16_source.json`
- sixteenth-slice scorecard targets:
  - `artifacts/benchmark_runs/beam_local_pilot_v16_observational_heuristic_v1.json`
  - `artifacts/benchmark_runs/beam_local_pilot_v16_dual_store_heuristic_v1.json`
- seventeenth slice: `artifacts/benchmark_runs/beam_local_pilot_v17_source.json`
- seventeenth-slice scorecard targets:
  - `artifacts/benchmark_runs/beam_local_pilot_v17_observational_heuristic_v1.json`
  - `artifacts/benchmark_runs/beam_local_pilot_v17_dual_store_heuristic_v1.json`
- eighteenth slice: `artifacts/benchmark_runs/beam_local_pilot_v18_source.json`
- eighteenth-slice scorecard targets:
  - `artifacts/benchmark_runs/beam_local_pilot_v18_observational_heuristic_v1.json`
  - `artifacts/benchmark_runs/beam_local_pilot_v18_dual_store_heuristic_v1.json`
- nineteenth slice: `artifacts/benchmark_runs/beam_local_pilot_v19_source.json`
- nineteenth-slice scorecard targets:
  - `artifacts/benchmark_runs/beam_local_pilot_v19_observational_heuristic_v1.json`
  - `artifacts/benchmark_runs/beam_local_pilot_v19_dual_store_heuristic_v1.json`
- twentieth slice: `artifacts/benchmark_runs/beam_local_pilot_v20_source.json`
- twentieth-slice scorecard targets:
  - `artifacts/benchmark_runs/beam_local_pilot_v20_observational_heuristic_v1.json`
  - `artifacts/benchmark_runs/beam_local_pilot_v20_dual_store_heuristic_v1.json`
- twenty-first slice: `artifacts/benchmark_runs/beam_local_pilot_v21_source.json`
- twenty-first-slice scorecard targets:
  - `artifacts/benchmark_runs/beam_local_pilot_v21_observational_heuristic_v1.json`
  - `artifacts/benchmark_runs/beam_local_pilot_v21_dual_store_heuristic_v1.json`
- twenty-second slice: `artifacts/benchmark_runs/beam_local_pilot_v22_source.json`
- twenty-second-slice scorecard targets:
  - `artifacts/benchmark_runs/beam_local_pilot_v22_observational_heuristic_v1.json`
  - `artifacts/benchmark_runs/beam_local_pilot_v22_dual_store_heuristic_v1.json`
- twenty-third slice: `artifacts/benchmark_runs/beam_local_pilot_v23_source.json`
- twenty-third-slice scorecard targets:
  - `artifacts/benchmark_runs/beam_local_pilot_v23_observational_heuristic_v1.json`
  - `artifacts/benchmark_runs/beam_local_pilot_v23_dual_store_heuristic_v1.json`

## Pilot coverage

The first pilot covers:

- `single_session` evidence
- `multi_session` evidence
- `dated` questions
- `undated` questions
- `answer` questions
- `should_abstain` questions
- current-state pressure

The expanded pilot adds:

- explicit supersession pressure
- temporal disambiguation over changing locations
- a direct `before X` query over multi-session state transitions

The third pilot adds:

- dated event ordering
- `before` and `after` queries over ordered travel events
- a direct comparison lane for observational memory versus the dual-store hybrid

The fourth pilot adds:

- repeated-value state reentry (`Austin -> Dubai -> Abu Dhabi -> Dubai`)
- current-state recovery after returning to a previous value
- `before moving back to X` and `after X` queries over ordered location transitions

The fifth pilot adds:

- month-indexed state recall over the same changing timeline
- `Where did I live in April/July/October 2025?` pressure
- explicit as-of-date state selection rather than latest-state or nearest-neighbor shortcuts

The sixth pilot adds:

- day-indexed state recall with conflicting updates inside the same month
- `Where did I live on 10/25 September 2025?` pressure
- exact-date selection instead of month-bucket selection

The seventh pilot adds:

- clock-time state recall within the same day
- `Where did I live at 7:30 AM / 9:00 AM / 7:00 PM on 10 September 2025?` pressure
- exact-time selection instead of date-only selection

The eighth pilot adds:

- event-anchored state recall using turn timestamps
- `Where did I live when I had breakfast at Marina Cafe?` pressure
- as-of-event state selection instead of only literal date/time parsing

The ninth pilot adds:

- relative event-anchored state transitions
- `Where did I live after breakfast?` and `Where was I living before dinner?` pressure
- nearest next/prior state selection around a non-location anchor event

The tenth pilot adds:

- multi-session relative event anchoring
- anchor events and resulting state transitions separated across sessions
- pressure on cross-session timeline stitching rather than same-session chronology

The eleventh pilot adds:

- competing anchor disambiguation
- two highly similar breakfast events at the same location with different companions
- pressure on choosing the right anchor event instead of any high-overlap match

The twelfth pilot adds:

- misleading lexical-overlap anchor disambiguation
- two near-duplicate breakfast events sharing most words and structure
- pressure on the decisive token being less prominent than the shared scaffold

The thirteenth pilot adds:

- long-span reentered competing anchors
- repeated anchor phrases across a longer timeline with state reentry
- pressure on distinguishing early anchor, later repeated anchor, and reused state values

The fourteenth pilot adds:

- date-qualified repeated-anchor disambiguation
- repeated identical anchor events whose correct downstream states differ by occurrence
- pressure on using the explicit `on <date>` qualifier inside a relative event query instead of retrieval order

The fifteenth pilot adds:

- dated preference-state recall
- superseding non-location state values across months
- pressure on treating `preference` as real current-state memory instead of location-only date selection

The sixteenth pilot adds:

- event-anchored non-location state recall
- state questions whose anchor is another state-bearing event like `when I lived in Dubai`
- pressure on predicate-agnostic anchored-state selection instead of location-only `when ...` handling

The seventeenth pilot adds:

- date-qualified reentered non-location state recall
- repeated anchor periods with the same location value but different downstream preferences
- pressure on selecting the dated anchor occurrence first, then reading the non-location state at that anchor instead of treating the date as a direct state bucket

The eighteenth pilot adds:

- date-qualified reentered favorite-color recall
- another non-location predicate family with the same repeated-location anchor shape as v17
- pressure on exact slot-value extraction so the system returns `green`, not `green now`

The nineteenth pilot adds:

- relative event-anchored non-location state recall
- `before` and `after` state selection for `preference` and `favorite_color`, not just location
- pressure on choosing the nearest state transition around the anchor event instead of echoing the anchor itself

The twentieth pilot adds:

- time-qualified relative event-anchored non-location state recall
- repeated identical anchor phrases distinguished only by exact clock time on the same day
- pressure on preventing generic dated-state selection from hijacking `before` and `after` questions that include a timestamp inside the anchor phrase

The twenty-first pilot adds:

- ambiguity abstention for relative event-anchored non-location state recall
- repeated identical anchors on the same date where the question omits the decisive clock time
- pressure on returning `unknown` when the anchor occurrence is underspecified instead of choosing one repeated event arbitrarily

The twenty-second pilot adds:

- relative non-location state recall anchored on a location-state transition
- questions like `what did I prefer after I moved to Dubai` where the anchor is itself a structured current-state update
- pressure on letting the relative-anchor resolver match location entries, not only episodic event text

The twenty-third pilot adds:

- relative non-location state recall anchored on a non-location state transition
- questions like `what did I prefer after I switched back to espresso`
- pressure on treating non-location current-state updates as anchorable timeline events instead of only answer-bearing values

## Command

```powershell
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v1_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_observational_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v2_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v2_observational_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v3_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v3_observational_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v3_source.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v3_dual_store_heuristic_v2.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v4_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v4_observational_heuristic_v2.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v4_source.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v4_dual_store_heuristic_v2.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v5_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v5_observational_heuristic_v3.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v5_source.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v5_dual_store_heuristic_v4.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v6_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v6_observational_heuristic_v3.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v6_source.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v6_dual_store_heuristic_v3.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v7_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v7_observational_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v7_source.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v7_dual_store_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v8_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v8_observational_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v8_source.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v8_dual_store_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v9_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v9_observational_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v9_source.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v9_dual_store_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v10_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v10_observational_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v10_source.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v10_dual_store_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v11_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v11_observational_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v11_source.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v11_dual_store_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v12_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v12_observational_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v12_source.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v12_dual_store_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v13_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v13_observational_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v13_source.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v13_dual_store_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v14_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v14_observational_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v14_source.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v14_dual_store_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v15_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v15_observational_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v15_source.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v15_dual_store_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v16_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v16_observational_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v16_source.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v16_dual_store_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v17_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v17_observational_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v17_source.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v17_dual_store_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v18_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v18_observational_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v18_source.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v18_dual_store_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v19_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v19_observational_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v19_source.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v19_dual_store_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v20_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v20_observational_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v20_source.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v20_dual_store_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v21_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v21_observational_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v21_source.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v21_dual_store_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v22_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v22_observational_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v22_source.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v22_dual_store_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v23_source.json --baseline observational_temporal_memory --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v23_observational_heuristic_v1.json
python -m domain_chip_memory.cli run-beam-baseline artifacts\benchmark_runs\beam_local_pilot_v23_source.json --baseline dual_store_event_calendar_hybrid --provider heuristic_v1 --write artifacts\benchmark_runs\beam_local_pilot_v23_dual_store_heuristic_v1.json
```

## Promotion rule

Do not describe this as the main BEAM reproduction.

It remains a fast internal regression lane even after public BEAM release.

The separate official proof lane should be used for external BEAM claims once all of these are true:

- one exact BEAM repo commit is pinned
- one exact dataset path and scale ladder are pinned
- one exact evaluation flow is pinned and reproduced in-repo
