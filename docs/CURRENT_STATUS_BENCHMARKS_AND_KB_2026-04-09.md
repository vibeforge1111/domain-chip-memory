# Current Status, Remaining Work, And Next Benchmarks

Date: 2026-04-09
Status: active current-state checkpoint

## Purpose

This document is the shortest honest answer to five questions:

1. where the memory system stands right now
2. what is already benchmark-strong
3. what is still incomplete
4. how aligned the current Spark KB layer is with the Karpathy LLM knowledge-base pattern
5. what should happen next

## What the checkpoint commits mean

The recent benchmark checkpoint commits are not arbitrary artifact dumps.

They are the judged outputs of the current memory architecture on the official-public `BEAM` evaluation path:

- the memory system first produces `domain_chip_memory_answers.json`
- the official-public evaluator then judges those answers category by category
- when one conversation finishes cleanly, that judged evaluation file is committed
- when a whole tranche finishes, the top-level official-eval manifest is reconstructed from the completed judged files and committed

So each checkpoint is evidence that the current memory system is surviving live benchmark evaluation, not only unit tests or local scorecards.

Important honesty note:

- the current judged `BEAM` closure is on the alternate openai-compatible MiniMax judge path, not the exact upstream OpenAI judge path
- it is still strong official-public evidence, but it should be described as alternate judged evidence, not exact-official final closure

## Current benchmark map

### Tier 1: strongest measured paths

- local `ProductMemory`: `1266/1266`
- `LongMemEval_s`: `500/500`
- local official-public `BEAM 128K` latest checked-in leader variants: `400/400`

Interpretation:

- current-state reconstruction is strong
- correction and contradiction handling are strong
- temporal and multi-session recall are strong
- the current `summary_synthesis_memory + heuristic_v1` architecture is real, not speculative

### Tier 2: strong but bounded

- bounded clean `LoCoMo`
  - first active slice: `24/25` raw with one known inconsistency
  - later `conv-26` slices through `q126-150`: repeated `25/25` clean reruns

Interpretation:

- conversational linkage is strong on the measured lane
- broader clean `LoCoMo` closure is still not honest to claim yet

### Tier 3: official-public judged `BEAM`

#### `500K`

This scale is fully closed on the alternate judge path:

- `conv1-5`: completed, `0.8349`
- `conv6-10`: completed, `0.7094`
- `conv11-15`: completed, `0.7598`
- `conv16-20`: completed, `0.7559`

Completion:

- `20/20` conversations judged complete
- tranche completion: `100%`

#### `1M`

This scale is now fully closed on the alternate judge path:

- `conv1-5`: completed, `0.915`
- `conv6-10`: completed, `0.9139`
- `conv11-15`: completed, `0.8889`
- `conv16-20`: completed, `0.9058`

Completion:

- `20/20` conversations judged complete
- tranche completion: `100%`

#### `10M`

This scale is now fully closed on the alternate judge path:

- `conv1-5`: completed, `0.8394`
- `conv6-10`: completed, `0.9108`

Completion:

- `10/10` conversations judged complete
- tranche completion: `100%`

Interpretation:

- the alternate judged official-public `BEAM` story is no longer partial at `500K`, `1M`, or `10M`
- the alternate judged official-public `BEAM` story is now also closed at `128K`
- the remaining `BEAM` work is now exact-official judge parity, not MiniMax-path artifact cleanup

## What is still missing

### Benchmarks still to close

1. broader clean `LoCoMo`
   - move beyond the bounded `conv-26` lane
2. first canonical `GoodAI` run
   - still not meaningfully closed
3. exact-official upstream OpenAI judge closure
   - the current `BEAM` judged story is now strong alternate evidence across `128K`, `500K`, `1M`, and `10M`
   - exact-judge parity is still a separate evidence class

### Product and systems work still missing

1. direct runtime metrics
   - latency
   - token cost
   - memory growth
   - drift rate
   - correction success rate
   - deletion reliability
2. real Spark shadow traces
   - replayable batches from actual traffic
   - failure taxonomy from product traces
3. full knowledge-base product layer
   - current scaffold exists
   - the full compile/query/filing loop does not yet exist

## How good the current memory architecture is

The honest answer is:

- already strong enough to call concrete
- not yet finished enough to call complete

Why it is strong:

- it closes local `ProductMemory`
- it closes `LongMemEval_s`
- it is strong on bounded `LoCoMo`
- it now has alternate judged official-public `BEAM` closure at `128K`
- it now has full alternate judged official-public `BEAM` coverage at `500K`, `1M`, and `10M`

Why it is not finished:

- exact-official judge parity is still open
- the broad `LoCoMo` and canonical `GoodAI` surfaces remain open
- the user-visible KB layer is still early

## Karpathy KB alignment: current verdict

Current verdict: partially aligned, not fully there yet.

### What is already aligned

The repo now has a real Spark KB scaffold that matches the shape of the Karpathy idea in the following ways:

- `raw/` exists as the intake shelf
- `wiki/` exists as the compiled markdown layer
- `CLAUDE.md` is generated as an LLM-facing schema
- the KB is downstream of governed memory, not a second truth store
- the vault is Obsidian-friendly
- query outputs have a reserved filing location under `wiki/outputs/`
- health checks exist

### What is specifically implemented

- `SparkMemorySDK.export_knowledge_base_snapshot()` in [sdk.py](../src/domain_chip_memory/sdk.py)
- KB scaffold in [spark_kb.py](../src/domain_chip_memory/spark_kb.py)
- CLI entrypoints in [cli.py](../src/domain_chip_memory/cli.py)
- integration contract in [spark_integration.py](../src/domain_chip_memory/spark_integration.py)
- compiled session source pages in `wiki/sources/`
- compiled timeline synthesis in `wiki/syntheses/timeline-overview.md`
- explicit repo-native ingest into `raw/repos/` plus compiled repo source pages
- filed KB maintenance report in `wiki/outputs/maintenance-report.md`
- filed KB answer pages in `wiki/outputs/query-*.md`
- contradiction and stale-state signals inside the KB maintenance report
- real `build-spark-kb` support for explicit filed-output JSON inputs
- real `build-spark-kb` support for repo-source manifest JSON inputs
- real `build-spark-kb` support for filed-output manifest JSON inputs
- real `validate-spark-kb-inputs` preflight support for snapshot, manifest, and filed-output validation
- compile results now expose both `repo_source_count` and `filed_output_count`
- checked-in Spark KB example inputs now exist under `docs/examples/spark_kb/`
- the checked-in Spark KB example bundle now has a real validate-build-health smoke test path
- the checked-in Spark KB example bundle is now self-described in `docs/examples/spark_kb/README.md`
- a checked-in invalid Spark KB validator fixture now exists under `docs/examples/spark_kb_invalid/`
- `docs/examples/README.md` now indexes the checked-in fixture bundles
- `docs/examples/spark_kb/run_smoke.py` now runs the checked-in valid Spark KB example end-to-end
- `docs/examples/spark_kb_invalid/run_validate_failure.py` now runs the checked-in invalid Spark KB validator flow
- `docs/examples/run_smokes.py` now runs the checked-in valid and invalid Spark KB wrappers together
- `.github/workflows/example-smokes.yml` now runs the checked-in top-level example smoke runner in CI

### What is now true after BEAM closure

- benchmark closure is no longer the only credible product story in the repo
- the KB layer is now the clearest remaining user-visible gap
- the next KB work should be real compilation and filing, not only scaffold maintenance

### What still does not exist yet

The system is still not fully Karpathy-complete because it does not yet have:

- incremental ingest of external articles, repos, papers, and datasets into `raw/`
- cross-source concept/entity pages beyond runtime memory pages
- broad filed query answers generated against the wiki itself
- automated contradiction and gap-filling passes over mixed runtime-plus-research sources beyond the first maintenance heuristics
- Obsidian-native dashboards or Dataview views
- scheduled compilation or maintenance loops

## Live KB validation

The KB flow should be validated with the real CLI, not only by reading code.

Minimum live checks:

1. `python -m domain_chip_memory.cli validate-spark-kb-inputs <snapshot_file> [--repo-source ...] [--repo-source-manifest ...] [--filed-output-file ...] [--filed-output-manifest ...]`
2. `python -m domain_chip_memory.cli build-spark-kb <snapshot_file> <output_dir> [--repo-source ...] [--repo-source-manifest ...] [--filed-output-file ...] [--filed-output-manifest ...]`
3. `python -m domain_chip_memory.cli spark-kb-health-check <output_dir>`
4. `python -m domain_chip_memory.cli demo-spark-kb <output_dir>`

Success means:

- the vault is scaffolded
- the source pages and synthesis pages exist
- input manifests and filed-output payloads validate cleanly before compile
- health checks pass cleanly, including repo-source/raw-copy parity and required filed-output sections

Current live result on 2026-04-09:

- `build-spark-kb` now exists as a real non-demo compiler path for snapshot JSON inputs
- `validate-spark-kb-inputs` now exists as a real preflight for snapshot, manifest, and filed-output bundles
- `build-spark-kb` can now merge explicit `--repo-source` files with manifest-driven repo-source lists
- `build-spark-kb` can now merge explicit `--filed-output-file` inputs with manifest-driven filed-output lists
- manifest entries now resolve relative to the manifest file location, not only the current shell directory
- `docs/examples/spark_kb/` now provides a checked-in validator fixture bundle
- `docs/examples/spark_kb/` now also supports a checked-in build plus health-check smoke flow
- `docs/examples/spark_kb/run_smoke.py` now wraps that valid example flow in one command
- `docs/examples/spark_kb_invalid/` now provides a checked-in failing validator fixture bundle
- `docs/examples/spark_kb_invalid/run_validate_failure.py` now wraps that failing validator flow in one command
- `docs/examples/run_smokes.py` now acts as the top-level checked-in examples smoke runner
- `.github/workflows/example-smokes.yml` now executes that checked-in examples smoke runner on pushes and PRs
- `demo-spark-kb` ran successfully against a real local vault scaffold
- `spark-kb-health-check` returned `valid: true`
- no missing required files
- no broken wikilinks
- repo-source pages are now checked against `raw/repos/` copies, and stray raw repo files are surfaced explicitly
- filed query pages are now checked for required `Question`, `Answer`, and `Provenance` sections
- source, synthesis, and output surfaces now include session pages, timeline overview, repo-source ingest, maintenance report output, filed answer pages, and first contradiction/staleness signals
- only `wiki/log.md` remains orphaned, which is acceptable for now because it is an append-only activity surface rather than a navigational page

## What is done vs remaining right now

### Done

- `ProductMemory`
- `LongMemEval_s`
- bounded `LoCoMo` lane
- alternate judged official-public `BEAM 128K`
- alternate judged official-public `BEAM 500K`
- alternate judged official-public `BEAM 1M`
- alternate judged official-public `BEAM 10M`
- first Spark KB scaffold
- first Spark KB health checks
- first Karpathy-alignment upgrade to the Spark KB scaffold

### Remaining

- broader clean `LoCoMo`
- canonical `GoodAI`
- exact-official judge parity for `BEAM`
- runtime metrics
- real Spark traces
- KB compiler v2 with query filing and cross-source syntheses

## Next tasks in order

### Immediate benchmark tasks

1. keep the closed alternate judged `BEAM` lanes as regression gates instead of reopening them casually
2. use `python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir artifacts/benchmark_runs --repo-root . --only-noisy --summary-only --top-series-limit 5` before treating residual artifact churn as a real regression signal
   - current live residual noise in `artifacts/benchmark_runs/` is `60` untracked JSON files across `3` noisy families
   - split: `6` debug files, `23` `longmemeval` files, `31` scorecards
   - the same noisy surface collapses to `35` series instead of a flat `60`-file list
   - current top-series slice is capped in the payload by `top_series_limit`
   - `summary_only` now keeps the counts and ranked series while omitting the giant `paths` arrays and full `noisy_files` dump
   - add `--family longmemeval` or `--family scorecard` when the full noisy surface is still too mixed to reason about cleanly
   - add `--series-prefix <series>` when one noisy cluster still needs a tighter read; current live example: `--family longmemeval --series-prefix longmemeval_summary_synthesis_offset225_limit25`
   - the payload now includes `recommended_focus`, so the next best follow-up command is explicit instead of inferred
   - the payload now includes `recommended_drilldown`, so the broad summary can expose the deepest recommended slice directly instead of making callers pick the last item from `recommended_followups`
   - the payload now also includes `recommended_sequence`, so callers can consume the ordered focus -> drilldown -> next-step guidance as one deduplicated list instead of stitching those top-level fields together by hand
   - the payload now also includes `recommended_sequence_targets`, so callers can consume that same ordered path as compact machine-readable family/series/top-series references without parsing labels or shell strings
   - the payload now also includes `recommended_sequence_labels`, so callers can render that same ordered path as concise readable labels without parsing shell commands or nested command arrays
   - the payload now also includes `recommended_sequence_preview`, so callers can render the whole ordered path as one joined human-readable summary string without formatting the label list themselves
   - the payload now also includes `recommended_sequence_commands`, so callers that want raw argv-style commands can consume the same deduplicated path without parsing shell strings or unpacking nested recommendation objects
   - the payload now also includes `recommended_sequence_shells`, so callers that only need runnable commands can consume the same ordered path as a deduplicated shell-command list without walking nested command arrays
   - the payload now also includes `recommended_sequence_steps`, so callers can consume one numbered ordered path that bundles each step's semantic phase, label, target ref, raw argv command, and shell command together
   - the payload now also includes `recommended_sequence_by_phase`, so callers can jump straight to the `focus`, `drilldown`, or `next_step` row without scanning the numbered sequence
   - the payload now also includes `recommended_sequence_summary`, so callers can read the sequence length, explicit command-step and non-command-step counts, normalized command coverage, a categorical command-coverage label, runnable-phase order, report-only-phase order, joined runnable/report-only phase signatures, phase order, compact phase signature, explicit entry/terminal step indices, entry phase, terminal phase, entry label, terminal label, entry target, terminal target, entry/terminal commands, explicit entry/terminal command-availability flags, the joined preview, and drilldown/next-step presence flags from one compact object
   - the payload now also includes `recommended_sequence_endpoints`, so callers that only care about the entry hop and terminal action can read the first and last sequence rows directly
   - the payload now also includes `recommended_sequence_transitions`, so callers can read the ordered edges between the sequence phases without diffing adjacent step rows themselves
   - the payload now also includes `recommended_sequence_transition_summary`, so callers can read compact transition counts split into fully runnable, mixed, and non-runnable edges, plus a nested `transition_mode_counts` block, a nested `transition_mode_competition` block for dominant-vs-runner-up comparison, `dominant_transition_mode`, `dominant_transition_mode_count`, `dominant_transition_mode_gap`, `dominant_transition_mode_gap_share`, `dominant_transition_mode_share`, runner-up mode/count/share accessors, a full deterministic `transition_mode_rank_order`, and a contested-vs-clear mode flag, plus normalized runnable-edge coverage, a categorical coverage label, an ordered transition-mode list, a joined transition-mode signature, the compact set of transition modes present, a uniformity flag, and per-mode phase-signature lists alongside the overall phase-signature list
   - the payload now also includes `recommended_sequence_transition_summary`, so callers can read the transition count and compact phase signatures without walking the full edge list
   - the payload now includes `recommended_family`, so the active family recommendation resolves to the enriched family row instead of only exposing a command wrapper
   - the payload now includes `recommended_family_gap`, so the report can say how far ahead the current recommended family is from the next noisy candidate without recomputing margins
   - `recommended_family_gap` now also carries both the exact runner-up family command and that family's top-series drilldown, and that runner-up series is resolved from the full noisy-series universe rather than only the current filtered slice
   - the payload now includes `recommended_family_comparison`, so callers can read the current leader hotspot, runner-up hotspot, and the already-computed family gap from one block instead of stitching together `family_hotspots` and `recommended_family_gap`; unlike the currently filtered `family_hotspots` view, those comparison hotspots are resolved from the full noisy-family universe so the leader and runner-up stay directly comparable
   - the payload now includes `family_competition`, so the broad report exposes a ranked noisy-family leaderboard with per-family leader gaps, local previous/next competition gaps, nearest-competitor routing, explicit nearest rank/top-series identity, clean family-only jump commands, direct top-series drilldown commands, the nearest competitor's own family jump, and the nearest competitor's own drilldown command instead of forcing callers to infer those comparisons from `family_commands` and `recommended_family_gap`
   - the payload now includes `recommended_family_competition_window`, so callers can read the current recommended family's competition row plus its immediate neighbors without scanning the whole `family_competition` array
   - the payload now includes `recommended_family_competition_summary`, so callers can read the current family rank, dominant series, nearest-competitor comparison, both sides' exact family and top-series jump commands, and a compact `recommended_next_step` routing hint with explicit target rank and series identity in one block without unpacking the broader window or leaderboard structures
   - the payload now also includes a top-level `recommended_next_step`, so callers that only need the next action do not need to unpack `recommended_family_competition_summary` first
   - the payload now includes `recommended_followups`, so the broad report can emit a two-step drilldown path instead of only the first hop
   - the payload now includes `family_hotspots`, so each noisy family carries its own dominant series and exact jump command
   - family rows now carry `reported_file_share`, `dominance_label`, and `family_rank`, so the broad summary says how much of the current noisy surface each family actually owns and where it sits in the current family ordering
   - `family_hotspots` now also carries concentration signals via `top_series_share` and `average_series_size`
   - `family_hotspots` now also carries `concentration_label` and `focus_mode`, so the report says whether to jump directly to the top series or stay at the family slice first
   - the payload now also includes `recommended_hotspot`, so the report can point at the hotspot row that best matches the current recommended focus instead of making callers recompute that mapping
   - the payload now includes exact `series_commands` for the ranked top-series slice, so the summary view can jump straight into a concrete series command
   - the payload now includes exact `family_commands` so the next focused slice can be copied directly instead of reconstructed by hand
   - largest live series: `longmemeval_summary_synthesis_offset225_limit25` (`4`), `longmemeval_summary_synthesis_offset275_limit25` (`4`), `official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5` (`4`), `_debug` (`3`), `_debug_gpt4` (`3`)
   - current live `recommended_focus` points to `--family scorecard`, because scorecards are the largest remaining noisy family at `31` files
   - current live `recommended_drilldown` points directly to `--family scorecard --series-prefix official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5`
   - current live `recommended_sequence` now packages that same path directly as `[--family scorecard, --family scorecard --series-prefix official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5, compare nearest competitor top series]`
   - current live `recommended_sequence_targets` now renders that path structurally as `[family scorecard, series scorecard / official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5, nearest competitor top series longmemeval / longmemeval_summary_synthesis_offset225_limit25]`
   - current live `recommended_sequence_labels` now renders that path readably as `[focus family scorecard, focus series scorecard / official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5, compare longmemeval rank 2 / longmemeval_summary_synthesis_offset225_limit25]`
   - current live `recommended_sequence_preview` now joins that same path into one string: `focus family scorecard -> focus series scorecard / official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5 -> compare longmemeval rank 2 / longmemeval_summary_synthesis_offset225_limit25`
   - current live `recommended_sequence_commands` now exposes those same three steps as raw argv arrays in the same order
   - current live `recommended_sequence_shells` now flattens that path into three runnable commands: jump to the `scorecard` family, drill into `official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5`, then compare the nearest competitor top series
   - current live `recommended_sequence_steps` now packages those same three steps as numbered rows with explicit phases (`focus`, `drilldown`, `next_step`), so the report has one ordered structure that already ties each label to its target ref and command forms
   - current live `recommended_sequence_by_phase` now exposes that same structure as a direct phase-indexed map, so `focus`, `drilldown`, and `next_step` can be read without iterating the steps array
   - current live `recommended_sequence_summary` now compresses that same path to `step_count = 3`, `command_step_count = 3`, `non_command_step_count = 0`, `command_coverage = 1.0`, `command_coverage_label = full`, `command_phase_order = [focus, drilldown, next_step]`, `non_command_phase_order = []`, `command_phase_signature = focus->drilldown->next_step`, `non_command_phase_signature = ""`, phase order `[focus, drilldown, next_step]`, phase signature `focus->drilldown->next_step`, explicit `entry_step = 1` and `terminal_step = 3`, `entry_phase = focus`, `terminal_phase = next_step`, `entry_label = focus family scorecard`, `terminal_label = compare longmemeval rank 2 / longmemeval_summary_synthesis_offset225_limit25`, matching entry/terminal targets and commands for those same endpoints, explicit `entry_has_command = true` and `terminal_has_command = true` flags for that broad path, the joined preview string, and flags showing that both a drilldown hop and a next-step comparison are present
   - current live `recommended_sequence_endpoints` now exposes the first `focus` row and the last `next_step` row directly, so the starting hop and terminal comparison can be read without scanning the full ordered path
   - current live `recommended_sequence_transitions` now renders the same path as ordered edges `focus -> drilldown` and `drilldown -> next_step`
   - current live `recommended_sequence_transition_summary` now compresses that edge view to `transition_count = 2`, `command_transition_count = 2`, `mixed_transition_count = 0`, `non_command_transition_count = 0`, `transition_mode_counts = {command: 2, mixed: 0, non_command: 0}`, `transition_mode_competition = {dominant_mode: command, dominant_count: 2, dominant_share: 1.0, runner_up_mode: mixed, runner_up_count: 0, runner_up_share: 0.0, gap: 2, gap_share: 1.0, is_contested: false}`, `dominant_transition_mode = command`, `dominant_transition_mode_count = 2`, `dominant_transition_mode_gap = 2`, `dominant_transition_mode_gap_share = 1.0`, `runner_up_transition_mode = mixed`, `runner_up_transition_mode_count = 0`, `runner_up_transition_mode_share = 0.0`, `transition_mode_rank_order = [command, mixed, non_command]`, `is_contested_transition_mode = false`, `dominant_transition_mode_share = 1.0`, `command_transition_coverage = 1.0`, `command_transition_coverage_label = full`, `transition_mode_order = [command, command]`, `transition_mode_signature = command->command`, `present_transition_modes = [command]`, `is_uniform_transition_mode = true`, `command_phase_signatures = [focus->drilldown, drilldown->next_step]`, `mixed_phase_signatures = []`, `non_command_phase_signatures = []`, and phase signatures `[focus->drilldown, drilldown->next_step]`
   - current live `recommended_sequence_transition_summary` now compresses that edge view to `transition_count = 2` and phase signatures `[focus->drilldown, drilldown->next_step]`
   - current live `recommended_family` is `scorecard`, with `reported_file_share = 0.5167` and `dominance_label = dominant`
   - current live `recommended_family_gap` shows `scorecard` ahead of `longmemeval` by `8` noisy files and `0.1334` noisy-share points, which classifies as a `clear` lead
   - the same live `recommended_family_gap` now includes the exact runner-up jump command `--family longmemeval` and the runner-up top-series drilldown `--family longmemeval --series-prefix longmemeval_summary_synthesis_offset225_limit25`, even when the current report view is narrower than the full noisy-family competition
   - current live `recommended_family_comparison` packages that same leader-versus-runner-up view directly: leader hotspot `scorecard -> official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5` (`4` noisy files across `23` scorecard series), runner-up hotspot `longmemeval -> longmemeval_summary_synthesis_offset225_limit25` (`4` noisy files across `10` longmemeval series), plus the existing `recommended_family_gap` block
   - current live `family_competition` now ranks the same noisy-family race directly: `scorecard` rank `1` at `31` files / `0.5167` share (`leader`), `longmemeval` rank `2` at `23` files / `0.3833` share (`clear` gap), and `debug` rank `3` at `6` files / `0.1000` share (`wide` gap); each row now carries previous/next family gap context, nearest-competitor routing, explicit nearest competitor rank/top-series identity, plus both a family-only command, a dominant-series drilldown command, the nearest competitor's family jump, and the nearest competitor's own top-series drilldown command
   - current live `recommended_family_competition_window` now lifts the local neighborhood around `scorecard` directly: current row `scorecard`, no previous competitor, next competitor `longmemeval`
   - current live `recommended_family_competition_summary` now compresses that same view to the essentials: `scorecard` rank `1`, dominant series `official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5`, nearest competitor `longmemeval` rank `2`, nearest share gap `0.1334`, plus direct family-jump and top-series drilldown commands for both the current family and that nearest competitor; because the live position label is `contested_leader`, the summary's new `recommended_next_step` now points at comparing the nearest competitor top series instead of only re-opening the current family top series, and it names that exact target as longmemeval rank `2` / `longmemeval_summary_synthesis_offset225_limit25`
   - that same live comparison target is now exposed again at top level via `recommended_next_step`, so the report's best next action can be read directly without unpacking the summary block
   - current live `recommended_hotspot` points at the `scorecard` hotspot row, which jumps directly to `--family scorecard --series-prefix official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5`
   - current live `recommended_followups` then drills from `--family scorecard` into `--family scorecard --series-prefix official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5`
   - current live family shares are `debug: 0.1000 / minor`, `longmemeval: 0.3833 / major`, `scorecard: 0.5167 / dominant`
   - current live `family_hotspots` are `debug -> _debug` (`3` across `2` series), `longmemeval -> longmemeval_summary_synthesis_offset225_limit25` (`4` across `10` series), and `scorecard -> official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5` (`4` across `23` series)
   - current live hotspot concentration is `debug: 0.5000 share / 3.0000 avg series size`, `longmemeval: 0.1739 / 2.3000`, `scorecard: 0.1290 / 1.3478`
   - current live hotspot classification is `debug: concentrated / series_first`, `longmemeval: diffuse / family_first`, `scorecard: diffuse / family_first`
   - current live `series_commands` starts with `longmemeval_summary_synthesis_offset225_limit25`, `longmemeval_summary_synthesis_offset275_limit25`, and `official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5`
   - current live `--family longmemeval` slice is `23` files across `10` series, with top clusters at offsets `225`, `275`, `325`, `350`, and `300`
   - current live `--family longmemeval --series-prefix longmemeval_summary_synthesis_offset225_limit25` slice collapses to `4` files in exactly `1` series
3. decide whether the next `BEAM` evidence task is exact-official judge parity or a different scale/provider validation lane
4. choose and close the next clean `LoCoMo` lane
5. lock the first canonical `GoodAI` run

### Immediate KB tasks

1. keep the current scaffold green under live CLI checks
2. add richer compiled pages that connect runtime memory to benchmark and repo knowledge
3. broaden filed query outputs beyond the current demo answer page
4. deepen the maintenance report beyond the first contradiction/staleness heuristics into richer gap and contradiction analysis
5. broaden repo-native ingest from explicit file picks into a more complete research and benchmark artifact path

### Next product tasks after that

1. start measuring runtime metrics on the actual Spark-style memory surface
2. connect real shadow traces into the KB as inspectable source material
3. turn benchmark failure clusters into mutation dossiers inside the KB

## Bottom line

The current memory architecture is already benchmark-serious.

The current KB layer is real but still early.

The remaining work is no longer "figure out whether this works."
The remaining work is:

- preserve the now-closed judged proof surface honestly
- finish the remaining benchmark evidence classes that are still open
- turn the Spark KB from a correct scaffold into the visible external-brain product layer
