# Next Phase Spark Memory, KB, And Benchmark Program

Date: 2026-04-10
Status: active next-phase source-of-truth

## 2026-04-11 Cross-Repo Update

The chip-side benchmark story and the Builder-side live story are now aligned enough to drive one runtime decision again.

Current honest state:

<!-- AUTO_BUILDER_BASELINE_NEXT_PHASE_START -->
- the latest offline `ProductMemory` comparison between `summary_synthesis_memory` and `dual_store_event_calendar_hybrid` is tied at `1156/1266`
- the latest clean live Builder full validation root is `$SPARK_HOME\artifacts\memory-validation-runs\20260412-023241`
- the latest clean live Builder full-run pointer is `$SPARK_HOME\artifacts\memory-validation-runs\latest-full-run.json`
- the chip-side freshness against that Builder baseline is `clean`
- the latest clean live Builder soak is fully green at `14/14`, `0` failed
- that live Builder soak still favors `summary_synthesis_memory` at `92/92` overall and `64/64` on selector packs
- the latest clean live Builder timings are benchmark `13.543s`, regression `23.724s`, soak `339.130s`, total `376.594s`
- because the offline side is now a tie instead of a loss, Builder has repinned the runtime selector to `summary_synthesis_memory`
<!-- AUTO_BUILDER_BASELINE_NEXT_PHASE_END -->

Important boundary:

- this does not mean the benchmark program is finished
- it means the current runtime pin is now justified by an offline tie plus a live lead, instead of by live evidence alone

## 2026-04-12 Spark Restart Check

The first restart step from the checklist below has now been re-confirmed against the real Builder home:

- `python -m domain_chip_memory.cli run-spark-builder-state-telegram-intake $SPARK_HOME tmp\state_telegram_restart_check_limit100_v2 --limit 100 --write tmp\state_telegram_restart_check_limit100_v2.json`
- source path: `$SPARK_HOME\state.db`
- processed `28` conversations with `121` accepted writes, `0` rejected writes, `0` skipped turns, and `380` reference turns
- compiled KB health stayed clean with `valid: true`

That is enough to treat the direct Builder `state.db` Telegram intake path as working end to end again.

The honest follow-up matters:

- this widened replay still did not surface any rejected writes or unsupported reasons
- the zero-write cleanroom and regression threads are not currently true failure-taxonomy examples yet
- they are query-only traces where Builder asks for a profile fact, then records a `tool_result_received` summary with no accepted write

The important metadata lesson from this restart is now explicit:

- the raw Builder `tool_result_received` rows already carry `bridge_mode`, `routing_decision`, `fact_name`, `label`, `predicate`, `evidence_summary`, and `value_found`
- the replay normalizer had been dropping those fields on normalized assistant turns, which made missing-fact abstentions look like generic reference turns
- the normalizer now preserves that query metadata, so future taxonomy and dossier work can distinguish `value_found: false` query misses from actual rejected writes

So the truthful next step after this restart check is:

- use the preserved query metadata to document clean abstentions versus missing-fact query misses
- then choose the first `memory only` vs `memory + KB` slice with that distinction in view
- only call something a Spark failure dossier when it is backed by a real rejection, skip, or explicit miss signal instead of a generic summary line

## 2026-04-12 First Narrow Memory-Only Versus Memory-Plus-KB Result

The first combined-system comparison now exists on a narrow Spark-shaped replay slice.

Command:

- `python -m domain_chip_memory.cli run-spark-memory-kb-ablation tmp\state_telegram_restart_check_limit100_v2.json --write tmp\spark_memory_kb_ablation_limit100_v1.json`
- latest scenario-aware rerun: `python -m domain_chip_memory.cli run-spark-memory-kb-ablation tmp\state_telegram_restart_check_limit100_v2.json --write tmp\spark_memory_kb_ablation_limit100_v8.json`

Slice definition:

- input source: the real Builder `state.db` replay captured in `tmp\state_telegram_restart_check_limit100_v2.json`
- query set: the replayed Spark profile-fact query turns extracted from that intake artifact
- `memory only`: replay the normalized conversations back through governed memory and answer each extracted query with the SDK explanation path
- `memory + KB`: answer the same query set, then check whether the compiled KB current-state page and supporting evidence pages exist for that same subject and predicate

Current result:

- query count: `125`
- `memory only` answered: `113`
- `memory + KB` answered: `113`
- answer delta count: `0`
- KB-supported query count: `113`
- missing-fact query count: `11`
- classified outcomes:
  - `answered_with_kb_support`: `113`
  - `missing_fact_query`: `11`
  - `query_abstention_without_kb_support`: `1`
- missing-fact predicates:
  - `profile.spark_role`: `4`
  - `profile.hack_actor`: `4`
  - `profile.timezone`: `2`
  - `profile.home_country`: `1`
- missing-fact scenarios:
  - `regression`: `4`
  - `boundary_abstention_cleanroom`: `4`
  - `quality_lane_gauntlet`: `3`
- missing-fact predicates by scenario:
  - `regression`: `profile.spark_role` `2`, `profile.hack_actor` `2`
  - `boundary_abstention_cleanroom`: one each of `profile.spark_role`, `profile.hack_actor`, `profile.timezone`, `profile.home_country`
  - `quality_lane_gauntlet`: one each of `profile.spark_role`, `profile.hack_actor`, `profile.timezone`
- operator action buckets:
  - `expected_cleanroom_boundary`: `4`
  - `regression_candidate`: `4`
  - `gauntlet_candidate`: `3`
- actionable predicates outside the cleanroom boundary lane:
  - `regression_candidate`: `profile.spark_role` `2`, `profile.hack_actor` `2`
  - `gauntlet_candidate`: `profile.spark_role` `1`, `profile.hack_actor` `1`, `profile.timezone` `1`
- replay source coverage on missing-fact queries:
  - `without_replay_source_evidence`: `11`
- source-backed answered counts for the same missing predicates elsewhere in the replay:
  - `profile.hack_actor`: `5`
  - `profile.home_country`: `26`
  - `profile.spark_role`: `2`
  - `profile.timezone`: `8`
- average `memory only` latency: `0.208 ms`
- average `memory + KB` latency: `0.467 ms`

Interpretation:

- this first narrow slice does **not** show an answer-quality lift from the KB layer yet
- it does show that the KB layer is lining up with the governed memory state on the answered queries
- on this slice, the KB is currently improving inspectability and support visibility, not changing the answer itself
- the unanswered slice is now classified instead of flat:
  - most misses are true `value_found: false` missing-fact queries
  - one remaining unanswered query is a query-abstention path with no KB support, not a confirmed missing fact
- the dominant missing-fact predicates are now explicit too:
  - Spark role and hack actor are the main uncovered fields
  - timezone and home country are secondary uncovered fields on this slice
- the ablation summary now also carries compact example conversations and questions for each missing predicate, so the operator does not need to scan the full comparisons list to see representative misses
- the ablation summary now also exposes which lane each miss came from:
  - regression misses are concentrated in `profile.spark_role` and `profile.hack_actor`
  - the cleanroom boundary lane is carrying the only `profile.home_country` miss and one of each other missing predicate
  - the gauntlet lane is missing Spark role, hack actor, and timezone, but not home country on this slice
- the latest rerun also adds an operator action bucket:
  - treat the four cleanroom-boundary misses as expected boundary behavior until a product requirement says otherwise
  - treat the four regression misses and three gauntlet misses as the current coverage-target slice worth sourcing next
- the more important correction is replay source coverage:
  - all `11` missing-fact queries have zero replayed current-state or observation evidence for that exact subject and predicate
  - that means this slice is currently showing zero-source-evidence abstentions, not a proven runtime or KB compilation failure on an actually-known fact
  - the non-cleanroom `regression_candidate` and `gauntlet_candidate` buckets are still useful coverage targets, but they should not be described as confirmed product regressions without a source-backed replay slice
- the new sourcing summary removes the ambiguity about where to get that next slice:
  - every missing predicate family already has answered, source-backed examples elsewhere in the same replay
  - that means the next benchmark step should be constructing a compact source-backed target slice, not hunting for new predicates
  - the current best source-backed exemplars are:
    - `profile.spark_role`: regression threads answering "What role will Spark play in this?" with `important part of the rebuild`
    - `profile.hack_actor`: regression threads answering "Who hacked us?" with `North Korea`
    - `profile.timezone`: regression and core-profile threads answering "What is my timezone?" with `Asia/Dubai`
    - `profile.home_country`: many answered threads exist, but the only current miss is still a cleanroom boundary case

## 2026-04-12 Compact Source-Backed Target Slice

The first compact sourcing slice now exists and is replay-ready.

Commands:

- `python -m domain_chip_memory.cli build-spark-memory-kb-sourcing-slice tmp\spark_memory_kb_ablation_limit100_v8.json --write tmp\spark_memory_kb_sourcing_slice_limit100_v1.json`
- `python -m domain_chip_memory.cli run-spark-memory-kb-ablation tmp\spark_memory_kb_sourcing_slice_limit100_v1.json --write tmp\spark_memory_kb_ablation_sourcing_slice_limit100_v1.json`

Slice result:

- predicates covered: `4`
- selected conversations: `8`
- missing-from-source conversations: `0`
- slice query count: `26`
- slice answered with KB support: `19`
- slice missing-fact query count: `7`
- slice missing-fact predicates:
  - `profile.hack_actor`: `2`
  - `profile.spark_role`: `2`
  - `profile.timezone`: `2`
  - `profile.home_country`: `1`

Interpretation:

- this is now the compact benchmark surface for sourcing work
- the slice keeps one answered source-backed exemplar lane for each missing predicate family while retaining the actual missing conversations
- the remaining misses on this compact slice are still all zero-source-evidence abstentions for those exact subject/predicate pairs
- the next productive move is to build or normalize a truly source-backed version of those seven miss conversations, then rerun this compact slice instead of the full `125`-query replay

## 2026-04-12 Source-Backed Compact Slice

The first truly source-backed compact slice now exists too.

Commands:

- `python -m domain_chip_memory.cli build-spark-memory-kb-source-backed-slice tmp\spark_memory_kb_sourcing_slice_limit100_v1.json tmp\spark_memory_kb_source_backed_slice_limit100_v2 --write tmp\spark_memory_kb_source_backed_slice_limit100_v2.json`
- `python -m domain_chip_memory.cli run-spark-memory-kb-ablation tmp\spark_memory_kb_source_backed_slice_limit100_v2.json --write tmp\spark_memory_kb_ablation_source_backed_slice_limit100_v2.json`

Source-backed build result:

- injected write count: `7`
- target conversation count: `7`
- missing source count: `0`

Source-backed compact-slice result:

- query count: `26`
- `memory only` answered: `26`
- `memory + KB` answered: `26`
- KB-supported query count: `26`
- original missing-fact query count: `7`
- resolved missing-fact query count: `7`
- unresolved missing-fact query count: `0`
- missing-fact source coverage: `with_replay_source_evidence: 7`
- classification counts:
  - `answered_with_kb_support`: `26`

Interpretation:

- the compact source-backed slice now demonstrates the exact point of the previous analysis
- the seven compact-slice misses were not runtime incapability; they were zero-source-evidence abstentions
- once the same predicates are backed by replayed write evidence inside those target conversations, all seven queries become answerable and KB-supported
- the remaining work is no longer to prove the memory or KB layer can answer these predicates; it is to decide which production lanes should actually receive that source evidence and under what product rules

## 2026-04-12 Compact Slice Transition Ledger

The before-versus-after comparison is now explicit too.

Command:

- `python -m domain_chip_memory.cli compare-spark-memory-kb-ablation tmp\spark_memory_kb_ablation_sourcing_slice_limit100_v1.json tmp\spark_memory_kb_ablation_source_backed_slice_limit100_v2.json --write tmp\spark_memory_kb_ablation_compare_source_backed_limit100_v1.json`

Transition result:

- shared queries: `26`
- unchanged non-missing queries: `19`
- unresolved-missing to resolved-missing transitions: `7`
- before-only queries: `0`
- after-only queries: `0`
- still unresolved after sourcing: `0`

Resolved transitions by predicate:

- `profile.hack_actor`: `2`
- `profile.spark_role`: `2`
- `profile.timezone`: `2`
- `profile.home_country`: `1`

Resolved transitions by scenario:

- `regression`: `4`
- `boundary_abstention_cleanroom`: `2`
- `quality_lane_gauntlet`: `1`

Interpretation:

- the transition ledger removes the last ambiguity from the compact proof
- every previously unresolved compact-slice miss transitioned cleanly once replay source evidence was injected
- there is no residual unresolved query left on the source-backed compact slice

## 2026-04-12 Policy Verdict

The transition ledger now has an operator-facing policy verdict too.

Command:

- `python -m domain_chip_memory.cli build-spark-memory-kb-policy-verdict tmp\spark_memory_kb_ablation_compare_source_backed_limit100_v1.json --write tmp\spark_memory_kb_policy_verdict_limit100_v1.json`

Correction:

- the original verdict artifact sampled up to three example rows per action bucket
- that was enough for policy explanation, but it underpowered the downstream promotion plan because `regression_candidate` actually had `4` resolved targets
- the fixed artifact is `tmp\spark_memory_kb_policy_verdict_limit100_v2.json`, which now keeps short `examples` plus the full `resolved_queries` list for each bucket

Verdict summary:

- resolved missing queries: `7`
- still unresolved queries: `0`
- action buckets with explicit recommendations: `3`

Bucket recommendations:

- `expected_cleanroom_boundary` resolved: `2`
  - verdict: retain boundary by default
  - implication: the cleanroom boundary misses are resolvable technically, but should not automatically become production promotion lanes
- `regression_candidate` resolved: `4`
  - verdict: promotable if the source path is legitimate
  - implication: hack-actor and Spark-role regression misses now look like upstream sourcing-policy candidates, not memory/KB capability problems
- `gauntlet_candidate` resolved: `1`
  - verdict: expand coverage only if the product wants that recall behavior
  - implication: the gauntlet timezone miss is optional product scope, not a correctness blocker

Practical next step:

- if the goal is product behavior, stop building benchmark plumbing here
- the next implementation question is which regression-candidate source paths should be allowed to write into the target conversation in production, while keeping the cleanroom boundary lane intentionally abstention-safe

## 2026-04-12 Promotion Plan

The repo now carries a concrete promotion-plan artifact too.

Command:

- `python -m domain_chip_memory.cli build-spark-memory-kb-promotion-plan tmp\spark_memory_kb_policy_verdict_limit100_v2.json tmp\spark_memory_kb_source_backed_slice_limit100_v2.json --write tmp\spark_memory_kb_promotion_plan_limit100_v2.json`

Plan summary:

- promotable regression targets: `4`
- optional gauntlet targets: `1`
- excluded cleanroom-boundary targets: `2`
- missing lineage rows: `0`

Promotable targets:

- `session:telegram:dm:spark-memory-regression-user-2c339238-hack_actor_query_missing`
  - predicate: `profile.hack_actor`
  - source conversation: `session:telegram:dm:spark-memory-regression-user-2c339238`
  - source message: `sim:1775946706394651`
  - value: `North Korea`
- `session:telegram:dm:spark-memory-regression-user-2c339238-spark_role_abstention`
  - predicate: `profile.spark_role`
  - source conversation: `session:telegram:dm:spark-memory-regression-user-2c339238`
  - source message: `sim:1775946707065672`
  - value: `important part of the rebuild`
- `session:telegram:dm:spark-memory-regression-user-6742ae87-hack_actor_query_missing`
  - predicate: `profile.hack_actor`
  - source conversation: `session:telegram:dm:spark-memory-regression-user-2c339238`
  - source message: `sim:1775946706394651`
  - value: `North Korea`
- `session:telegram:dm:spark-memory-regression-user-6742ae87-spark_role_abstention`
  - predicate: `profile.spark_role`
  - source conversation: `session:telegram:dm:spark-memory-regression-user-2c339238`
  - source message: `sim:1775946707065672`
  - value: `important part of the rebuild`

Policy implication:

- this is now the smallest concrete implementation list for production-policy follow-through
- if a product lane is approved, these exact regression targets have traceable source-write lineage ready for audit
- the cleanroom boundary targets remain explicitly excluded unless product policy changes

## 2026-04-12 Approved Promotion Slice

The repo now has a first production-candidate artifact too.

Commands:

- `python -m domain_chip_memory.cli build-spark-memory-kb-approved-promotion-slice tmp\spark_memory_kb_promotion_plan_limit100_v2.json tmp\spark_memory_kb_source_backed_slice_limit100_v2.json tmp\spark_memory_kb_approved_promotion_slice_limit100_v2 --write tmp\spark_memory_kb_approved_promotion_slice_limit100_v2.json`
- `python -m domain_chip_memory.cli run-spark-memory-kb-ablation tmp\spark_memory_kb_approved_promotion_slice_limit100_v2.json --write tmp\spark_memory_kb_ablation_approved_promotion_slice_limit100_v2.json`

Approved-slice summary:

- selected promotable targets: `4`
- selected conversations after retaining source lineage: `5`
- optional gauntlet targets included: `false`
- missing selected conversations: `0`

Approved-slice A/B summary:

- queries: `23`
- memory-only answered: `23`
- memory-plus-KB answered: `23`
- answer delta: `0`
- KB-supported queries: `23`
- original missing-fact queries inside this slice: `4`
- resolved missing-fact queries: `4`
- unresolved missing-fact queries: `0`

Approved promotable misses carried into the slice:

- `profile.hack_actor`: `2`
- `profile.spark_role`: `2`

Interpretation:

- the repo now has a filtered, policy-applied slice instead of only a recommendation artifact
- the default production-candidate path stays narrow: regression candidates only, with no cleanroom-boundary or optional gauntlet targets included
- all four promotable regression misses now resolve cleanly once their approved source lineage is retained
- if product wants the gauntlet lane later, `--include-optional` is the controlled expansion path rather than widening the default slice

## 2026-04-12 Promotion Policy Manifest

The repo now has an upstream-consumable decision file too.

Command:

- `python -m domain_chip_memory.cli build-spark-memory-kb-promotion-policy tmp\spark_memory_kb_promotion_plan_limit100_v2.json --write tmp\spark_memory_kb_promotion_policy_limit100_v1.json`

Policy summary:

- `allow`: `4`
- `defer`: `1`
- `block`: `2`
- distinct target conversations covered: `7`
- distinct source messages referenced: `4`

Manifest interpretation:

- the four regression targets are now represented as exact `allow` rows keyed by target conversation, predicate, source conversation, and source message
- the gauntlet timezone lane is preserved as an explicit `defer` row instead of disappearing from the output
- the two cleanroom-boundary targets are preserved as explicit `block` rows
- the next upstream Builder integration no longer needs to reconstruct policy from benchmark prose or example-only artifacts; it can consume one concrete manifest

## 2026-04-12 Policy-Gated Runtime Replay

The repo now has a governed replay too, not just a static manifest.

Command:

- `python -m domain_chip_memory.cli run-spark-memory-kb-ablation tmp\spark_memory_kb_source_backed_slice_limit100_v2.json --promotion-policy-file tmp\spark_memory_kb_promotion_policy_limit100_v1.json --write tmp\spark_memory_kb_ablation_source_backed_slice_policy_limit100_v1.json`

Governed replay summary:

- `26` queries
- `23` answered by governed runtime replay
- `26` answered by the existing compiled KB
- `3` answer deltas
- `7` original missing-fact queries
- `7` resolved when the KB is consulted
- runtime-side source coverage on the missing slice is now `with_replay_source_evidence: 4` and `without_replay_source_evidence: 3`

Governed replay interpretation:

- the `4` `allow` rows behave as intended: those regression-candidate promotions still resolve in runtime replay
- the `2` cleanroom-boundary rows and `1` gauntlet row now abstain again in governed runtime replay
- the current compiled KB still answers those three non-allowed lanes because the source-backed KB snapshot was compiled before policy was applied
- that produces a real alignment bug: governed runtime memory is narrower than the visible KB surface on the same source-backed slice

So the next implementation target is now concrete:

- policy enforcement is no longer hypothetical; the replay layer already honors the manifest
- the remaining gap is KB compilation and/or KB serving alignment so blocked or deferred promotions do not stay answerable through an ungated snapshot

## 2026-04-12 Policy-Aligned KB Replay

That alignment gap now has a concrete remediation path too.

Command:

- `python -m domain_chip_memory.cli run-spark-memory-kb-ablation tmp\spark_memory_kb_source_backed_slice_limit100_v2.json --promotion-policy-file tmp\spark_memory_kb_promotion_policy_limit100_v1.json --recompile-kb-output-dir tmp\spark_memory_kb_source_backed_slice_policy_aligned_limit100_v1 --write tmp\spark_memory_kb_ablation_source_backed_slice_policy_aligned_limit100_v1.json`

Policy-aligned summary:

- `26` queries
- `23` answered by governed runtime replay
- `23` answered by the policy-aligned KB
- `0` answer deltas
- `7` original missing-fact queries
- `4` resolved missing-fact queries
- `3` unresolved missing-fact queries
- `23` KB-supported queries

Policy-aligned interpretation:

- the `4` allowed regression promotions remain answerable and KB-supported
- the `2` blocked cleanroom-boundary lanes plus the `1` deferred gauntlet lane stay unanswered in both runtime replay and KB output
- the alignment bug is therefore not a replay limitation; it was a KB-compilation-policy mismatch
- the practical requirement is now explicit: any production KB refresh that includes source-backed promotion data needs to compile from the same governed replay surface, or an equivalent policy-filtered snapshot

## 2026-04-12 Policy-Aligned Slice Artifact

The repo now has a direct builder command for that governed output too.

Command:

- `python -m domain_chip_memory.cli build-spark-memory-kb-policy-aligned-slice tmp\spark_memory_kb_source_backed_slice_limit100_v2.json tmp\spark_memory_kb_promotion_policy_limit100_v1.json tmp\spark_memory_kb_policy_aligned_slice_limit100_v1 --write tmp\spark_memory_kb_policy_aligned_slice_payload_limit100_v1.json`

Artifact summary:

- replayed conversations: `8`
- accepted writes: `16`
- skipped turns: `3`
- policy-skipped turns: `3`
- policy skip reasons: `block: 2`, `defer: 1`
- compiled current-state pages: `16`
- compiled evidence pages: `16`

Artifact interpretation:

- this is now a direct consumable governed KB artifact, not only an ablation mode
- the policy manifest, shadow replay summary, governed snapshot, and compiled KB are now emitted together
- upstream integration no longer has to infer which cloned writes were suppressed; the artifact carries the exact skip counts and reasons alongside the compiled output

## 2026-04-12 Refresh Manifest

The repo now has a compact upstream refresh manifest on top of that governed artifact.

Command:

- `python -m domain_chip_memory.cli build-spark-memory-kb-refresh-manifest tmp\spark_memory_kb_policy_aligned_slice_payload_limit100_v1.json --write tmp\spark_memory_kb_refresh_manifest_limit100_v1.json`

Refresh-manifest summary:

- governed KB dir: `tmp\spark_memory_kb_policy_aligned_slice_limit100_v1`
- governed snapshot file: `tmp\spark_memory_kb_policy_aligned_slice_limit100_v1\raw\memory-snapshots\latest.json`
- health valid: `true`
- replayed conversations: `8`
- accepted writes: `16`
- skipped turns: `3`
- policy-skipped turns: `3`
- decision counts: `allow 4`, `block 2`, `defer 1`
- target conversations covered: `7`
- source conversations covered: `1`
- source messages referenced: `4`

Refresh-manifest interpretation:

- this is the smallest current handoff surface for an upstream refresher
- it points directly at the governed KB and governed snapshot instead of requiring the caller to parse a larger benchmark artifact
- it keeps the policy envelope explicit through compact `policy_targets_by_decision` rows, so upstream code can both locate the compiled output and verify which promotions were allowed, blocked, or deferred

## 2026-04-12 Refresh Materialization

The repo now has a direct consumer path too.

Command:

- `python -m domain_chip_memory.cli materialize-spark-memory-kb-refresh-manifest tmp\spark_memory_kb_refresh_manifest_limit100_v1.json tmp\spark_memory_kb_refresh_materialized_limit100_v1 --write tmp\spark_memory_kb_refresh_materialized_payload_limit100_v1.json`

Materialization summary:

- source governed KB dir: `tmp\spark_memory_kb_policy_aligned_slice_limit100_v1`
- materialized KB dir: `tmp\spark_memory_kb_refresh_materialized_limit100_v1`
- materialized snapshot file: `tmp\spark_memory_kb_refresh_materialized_limit100_v1\raw\memory-snapshots\latest.json`
- health valid: `true`
- replayed conversations: `8`
- accepted writes: `16`
- skipped turns: `3`
- decision counts: `allow 4`, `block 2`, `defer 1`

Materialization interpretation:

- an upstream refresher no longer needs to reconstruct or recompile the governed KB to consume it
- the manifest can now be turned into a fresh output directory with one command while preserving the governed snapshot and health report
- this is still intentionally copy-based, not merge-based, so the consumer path stays explicit and does not silently overwrite an existing target

## 2026-04-12 Refresh Publish

The repo now has an activation-style publish step too.

Command:

- `python -m domain_chip_memory.cli publish-spark-memory-kb-refresh-manifest tmp\spark_memory_kb_refresh_manifest_limit100_v1.json tmp\spark_memory_kb_refresh_publish_limit100_v1 --write tmp\spark_memory_kb_refresh_publish_payload_limit100_v1.json`

Publish summary:

- publish root: `tmp\spark_memory_kb_refresh_publish_limit100_v1`
- release dir: `tmp\spark_memory_kb_refresh_publish_limit100_v1\releases\spark-kb-8dea2cb4d9dd`
- active refresh file: `tmp\spark_memory_kb_refresh_publish_limit100_v1\active-refresh.json`
- health valid: `true`
- replayed conversations: `8`
- accepted writes: `16`
- skipped turns: `3`
- decision counts: `allow 4`, `block 2`, `defer 1`

Publish interpretation:

- this turns the governed refresh into a stable release directory plus one active pointer file
- the release directory uses a short stable slug instead of the full source KB directory name; that change was necessary because the longer nested publish path tripped a real Windows path-depth failure during copy
- an upstream Builder-side consumer can now point at `active-refresh.json` and avoid guessing which governed release directory is current

## 2026-04-12 Active Refresh Resolution

The repo now has a direct reader for that published pointer too.

Command:

- `python -m domain_chip_memory.cli resolve-spark-memory-kb-active-refresh tmp\spark_memory_kb_refresh_publish_limit100_v1\active-refresh.json --write tmp\spark_memory_kb_active_resolution_limit100_v1.json`

Resolution summary:

- resolved KB dir: `tmp\spark_memory_kb_refresh_publish_limit100_v1\releases\spark-kb-8dea2cb4d9dd`
- resolved snapshot file: `tmp\spark_memory_kb_refresh_publish_limit100_v1\releases\spark-kb-8dea2cb4d9dd\raw\memory-snapshots\latest.json`
- health valid: `true`
- replayed conversations: `8`
- accepted writes: `16`
- skipped turns: `3`
- decision counts: `allow 4`, `block 2`, `defer 1`

Resolution interpretation:

- a downstream Builder-side caller no longer needs to parse the publish payload or infer which release is active
- one command now resolves the active governed KB and validates that the released directory still exists and still passes the KB health check
- this is the narrowest current consumer surface in the repo for live governed KB lookup

## 2026-04-12 Active Refresh Reads

The repo now has a direct KB lookup path on top of the active refresh too.

Commands:

- `python -m domain_chip_memory.cli read-spark-memory-kb-active-refresh-support tmp\spark_memory_kb_refresh_publish_limit100_v1\active-refresh.json human:telegram:spark-memory-regression-user-2c339238-hack_actor_query_missing profile.hack_actor --write tmp\spark_memory_kb_active_support_hack_actor_limit100_v1.json`
- `python -m domain_chip_memory.cli read-spark-memory-kb-active-refresh-support tmp\spark_memory_kb_refresh_publish_limit100_v1\active-refresh.json human:telegram:spark-memory-soak-user-ed0c3cbc-boundary_abstention-0005-timezone_query_missing_cleanroom profile.timezone --write tmp\spark_memory_kb_active_support_cleanroom_timezone_limit100_v1.json`

Read summaries:

- allowed regression lane:
  - found: `true`
  - value: `North Korea`
  - supporting evidence count: `1`
- blocked cleanroom lane:
  - found: `false`
  - value: `null`
  - supporting evidence count: `0`

Read interpretation:

- this is now the first direct repo-local read surface that behaves like a Builder-side governed KB consumer instead of a benchmark-only artifact generator
- the same published active refresh can now serve both a positive allowed lookup and a clean abstention on a blocked lane
- that makes the policy effect visible at the final lookup boundary, not just during replay and compile steps

## 2026-04-12 Active Policy Verification

The repo now has a direct final-boundary verification step too.

Command:

- `python -m domain_chip_memory.cli verify-spark-memory-kb-active-refresh-policy tmp\spark_memory_kb_refresh_publish_limit100_v1\active-refresh.json tmp\spark_memory_kb_policy_aligned_slice_payload_limit100_v1.json --write tmp\spark_memory_kb_active_policy_verification_limit100_v1.json`

Verification summary:

- policy rows checked: `7`
- checked rows: `7`
- subject-missing rows: `0`
- honored counts: `allow 4`, `block 2`, `defer 1`
- violation count: `0`
- policy honored: `true`

Verification interpretation:

- the published governed KB is no longer only assumed to honor policy; the repo now checks that explicitly against the original policy-aligned source rows
- this verifies the final published lookup surface, not just replay-time skips or compile-time counts
- if a future refresh accidentally reintroduces blocked or deferred facts, this command will surface the regression as a policy violation instead of relying on manual inspection

## 2026-04-12 Conversation-Level Active Reads

The repo now has a Builder-shaped read surface too.

Command:

- `python -m domain_chip_memory.cli read-spark-memory-kb-active-refresh-conversation-support tmp\spark_memory_kb_refresh_publish_limit100_v1\active-refresh.json tmp\spark_memory_kb_policy_aligned_slice_payload_limit100_v1.json session:telegram:dm:spark-memory-regression-user-2c339238-hack_actor_query_missing profile.hack_actor --write tmp\spark_memory_kb_active_conversation_support_hack_actor_limit100_v1.json`

Conversation-read summary:

- conversation id: `session:telegram:dm:spark-memory-regression-user-2c339238-hack_actor_query_missing`
- resolved subject: `human:telegram:spark-memory-regression-user-2c339238-hack_actor_query_missing`
- predicate: `profile.hack_actor`
- found: `true`
- value: `North Korea`
- supporting evidence count: `1`

Conversation-read interpretation:

- a downstream caller no longer needs to know the internal `human_id` format to perform a governed KB lookup
- the published active refresh can now be queried with the same conversation identifier family used throughout the Spark/Builder artifacts
- this is the closest repo-local approximation so far to a real Builder-side active KB read path

## 2026-04-12 Active Read Report

The repo now has a batch version of that published read surface too.

Command:

- `python -m domain_chip_memory.cli run-spark-memory-kb-active-refresh-read-report tmp\spark_memory_kb_refresh_publish_limit100_v1\active-refresh.json tmp\spark_memory_kb_policy_aligned_slice_payload_limit100_v1.json --write tmp\spark_memory_kb_active_read_report_limit100_v1.json`

Active-read summary:

- query count: `26`
- found count: `23`
- missing count: `3`
- resolved original missing-fact queries: `4`
- unresolved original missing-fact queries: `3`
- found by scenario: `regression 23`
- missing by scenario: `boundary_abstention_cleanroom 2`, `quality_lane_gauntlet 1`

Active-read interpretation:

- this is now the published-surface equivalent of the earlier replay ablations
- the final active governed KB exposes only the regression lane and cleanly omits the blocked and deferred lanes
- that makes the live published surface easy to audit in one artifact instead of checking single lookups one by one

## 2026-04-12 Active Release Summary

The repo now has a one-file release-readiness summary for the published governed surface.

Command:

- `python -m domain_chip_memory.cli build-spark-memory-kb-active-release-summary tmp\spark_memory_kb_refresh_publish_limit100_v1\active-refresh.json tmp\spark_memory_kb_policy_aligned_slice_payload_limit100_v1.json --write tmp\spark_memory_kb_active_release_summary_limit100_v1.json`

Release-summary result:

- health valid: `true`
- policy honored: `true`
- policy rows checked: `7`
- policy violations: `0`
- query count: `26`
- found count: `23`
- missing count: `3`
- resolved original missing-fact queries: `4`
- unresolved original missing-fact queries: `3`
- found by action bucket: `regression_candidate 23`
- missing by action bucket: `expected_cleanroom_boundary 2`, `gauntlet_candidate 1`

Release-summary interpretation:

- this is now the highest-signal single artifact in the repo for downstream integration
- it combines active resolution, policy verification, and final published-surface read coverage in one place
- a Builder-side integration can use this as its release gate without replaying the entire benchmark chain

## 2026-04-12 Active Release Gate

The repo now has a direct pass/fail gate on top of that release summary.

Command:

- `python -m domain_chip_memory.cli check-spark-memory-kb-active-release-summary tmp\spark_memory_kb_active_release_summary_limit100_v1.json --write tmp\spark_memory_kb_active_release_gate_limit100_v1.json`

Gate result:

- ready: `true`
- failure reason count: `0`
- health valid: `true`
- policy honored: `true`
- policy violations: `0`
- found count: `23`
- missing count: `3`
- allowed missing action buckets: `expected_cleanroom_boundary 2`, `gauntlet_candidate 1`

Gate interpretation:

- this is the narrowest machine-friendly release decision artifact in the repo now
- it encodes the current rule that regression candidates must be exposed while cleanroom-boundary and deferred gauntlet lanes may remain absent
- a downstream Builder release step can consume this one file and stop on any future regression leak or policy violation without understanding the full benchmark pipeline

## 2026-04-12 Active Release Assert

The repo now has a shell-friendly assert command on top of that gate.

Command:

- `python -m domain_chip_memory.cli assert-spark-memory-kb-active-release-ready tmp\spark_memory_kb_active_release_summary_limit100_v1.json --write tmp\spark_memory_kb_active_release_assert_limit100_v1.json`

Assert result:

- exit status: `0`
- ready: `true`
- failure reason count: `0`
- health valid: `true`
- policy honored: `true`

Assert interpretation:

- this is the first repo-local command in the chain that is directly usable as CI or release-step control flow
- success returns the same gate payload and failure will now terminate the process with the failure reasons in the error text
- a downstream Builder release script no longer needs to parse JSON just to decide whether the governed KB publish is acceptable

## 2026-04-12 Governed Ship Command

The repo now has a one-command governed release ship path too.

Command:

- `python -m domain_chip_memory.cli ship-spark-memory-kb-governed-release tmp\spark_memory_kb_refresh_manifest_limit100_v1.json tmp\spark_memory_kb_policy_aligned_slice_payload_limit100_v1.json tmp\spark_memory_kb_governed_ship_limit100_v1 --write tmp\spark_memory_kb_governed_ship_payload_limit100_v1.json`

Ship result:

- ready: `true`
- release output dir: `tmp\spark_memory_kb_governed_ship_limit100_v1\releases\spark-kb-8dea2cb4d9dd`
- active refresh file: `tmp\spark_memory_kb_governed_ship_limit100_v1\active-refresh.json`
- active release summary file: `tmp\spark_memory_kb_governed_ship_limit100_v1\active-release-summary.json`
- active release gate file: `tmp\spark_memory_kb_governed_ship_limit100_v1\active-release-gate.json`
- governed release file: `tmp\spark_memory_kb_governed_ship_limit100_v1\governed-release.json`

Ship interpretation:

- this is now the shortest end-to-end governed release path in the repo
- one command publishes the governed KB, writes the active pointer, builds the release summary, and emits the machine-friendly release gate
- rerunning the ship command against the same publish root now safely replaces the hashed release directory instead of failing on the existing stable slug
- the ship root now also keeps a stable top-level `governed-release.json`, so downstream automation does not need the optional external `--write` payload just to discover the shipped artifact set
- this is the closest repo-local artifact yet to what an actual Builder-side release job would need to call

## 2026-04-12 Governed Release Resolution

The top-level governed release manifest is now consumable directly too.

Commands:

- `python -m domain_chip_memory.cli resolve-spark-memory-kb-governed-release tmp\spark_memory_kb_governed_ship_limit100_v1\governed-release.json --write tmp\spark_memory_kb_governed_release_resolution_limit100_v1.json`
- `python -m domain_chip_memory.cli assert-spark-memory-kb-governed-release-ready tmp\spark_memory_kb_governed_ship_limit100_v1\governed-release.json --write tmp\spark_memory_kb_governed_release_assert_limit100_v1.json`

Resolution result:

- ready: `true`
- publish root dir: `tmp\spark_memory_kb_governed_ship_limit100_v1`
- active refresh file: `tmp\spark_memory_kb_governed_ship_limit100_v1\active-refresh.json`
- active release summary file: `tmp\spark_memory_kb_governed_ship_limit100_v1\active-release-summary.json`
- active release gate file: `tmp\spark_memory_kb_governed_ship_limit100_v1\active-release-gate.json`
- release output dir: `tmp\spark_memory_kb_governed_ship_limit100_v1\releases\spark-kb-8dea2cb4d9dd`
- snapshot file: `tmp\spark_memory_kb_governed_ship_limit100_v1\releases\spark-kb-8dea2cb4d9dd\raw\memory-snapshots\latest.json`
- health valid: `true`
- policy honored: `true`
- failure reason count: `0`

Resolution interpretation:

- downstream automation can now start from the single top-level `governed-release.json` file instead of discovering the inner active files itself
- the governed ship artifact is now self-describing enough to support both path resolution and shell-friendly readiness assertion from one entrypoint

## 2026-04-12 Governed Release Reads

The top-level governed release manifest now supports direct reads too.

Commands:

- `python -m domain_chip_memory.cli read-spark-memory-kb-governed-release-support tmp\spark_memory_kb_governed_ship_limit100_v1\governed-release.json human:telegram:spark-memory-regression-user-2c339238-hack_actor_query_missing profile.hack_actor --write tmp\spark_memory_kb_governed_release_support_hack_actor_limit100_v1.json`
- `python -m domain_chip_memory.cli read-spark-memory-kb-governed-release-conversation-support tmp\spark_memory_kb_governed_ship_limit100_v1\governed-release.json session:telegram:dm:spark-memory-regression-user-2c339238-hack_actor_query_missing profile.hack_actor --write tmp\spark_memory_kb_governed_release_conversation_support_hack_actor_limit100_v1.json`
- `python -m domain_chip_memory.cli run-spark-memory-kb-governed-release-read-report tmp\spark_memory_kb_governed_ship_limit100_v1\governed-release.json --write tmp\spark_memory_kb_governed_release_read_report_limit100_v1.json`

Read result:

- subject support found: `true`
- conversation support found: `true`
- subject and conversation values: `North Korea`
- subject and conversation supporting evidence count: `1`
- batch query count: `26`
- batch found count: `23`
- batch missing count: `3`
- missing by action bucket: `expected_cleanroom_boundary 2`, `gauntlet_candidate 1`

Read interpretation:

- the top-level governed release manifest is now a complete repo-local lookup entrypoint, not just a release gate
- downstream callers can resolve release state, assert readiness, read one fact, read one conversation fact, or audit the full published surface without manually passing `active-refresh.json` or the policy-aligned slice file

## 2026-04-12 Governed Release Summary

The ship command now persists top-level governed release audit files too.

Commands:

- `python -m domain_chip_memory.cli ship-spark-memory-kb-governed-release tmp\spark_memory_kb_refresh_manifest_limit100_v1.json tmp\spark_memory_kb_policy_aligned_slice_payload_limit100_v1.json tmp\spark_memory_kb_governed_ship_limit100_v1 --write tmp\spark_memory_kb_governed_ship_payload_limit100_v1.json`
- `python -m domain_chip_memory.cli build-spark-memory-kb-governed-release-summary tmp\spark_memory_kb_governed_ship_limit100_v1\governed-release.json --write tmp\spark_memory_kb_governed_release_summary_limit100_v1.json`

Summary result:

- governed release read report file: `tmp\spark_memory_kb_governed_ship_limit100_v1\governed-release-read-report.json`
- governed release summary file: `tmp\spark_memory_kb_governed_ship_limit100_v1\governed-release-summary.json`
- governed release gate file: `tmp\spark_memory_kb_governed_ship_limit100_v1\governed-release-gate.json`
- ready: `true`
- health valid: `true`
- policy honored: `true`
- query count: `26`
- found count: `23`
- missing count: `3`
- missing by action bucket: `expected_cleanroom_boundary 2`, `gauntlet_candidate 1`

Summary interpretation:

- a single ship run now leaves the top-level manifest, top-level read audit, and top-level compact summary together in the publish root
- downstream automation no longer needs to synthesize a post-ship report itself just to inspect the published governed surface

Top-level gate commands:

- `python -m domain_chip_memory.cli check-spark-memory-kb-governed-release-summary tmp\spark_memory_kb_governed_ship_limit100_v1\governed-release-summary.json --write tmp\spark_memory_kb_governed_release_gate_limit100_v1.json`
- `python -m domain_chip_memory.cli assert-spark-memory-kb-governed-release-summary-ready tmp\spark_memory_kb_governed_ship_limit100_v1\governed-release-summary.json --write tmp\spark_memory_kb_governed_release_assert_summary_limit100_v1.json`

Top-level gate result:

- ready: `true`
- failure reason count: `0`
- upstream ready: `true`
- upstream failure reason count: `0`
- allowed missing action buckets: `expected_cleanroom_boundary 2`, `gauntlet_candidate 1`

Top-level gate interpretation:

- the publish root now contains a full top-level machine gate alongside the manifest, read audit, and compact summary
- downstream automation can stop at `governed-release-summary.json` / `governed-release-gate.json` without traversing into the active release artifacts at all

So the honest claim after this first A/B is:

- the first Spark-shaped `memory only` versus `memory + KB` comparison is now real
- the current result is neutral on answer quality
- the KB is currently an auditability and support layer on this slice, not a measured answer-improvement layer yet

## Purpose

This document exists to prevent the next phase from fragmenting into:

- Spark integration work with no benchmark follow-through
- benchmark work with no product integration
- KB work with no runtime connection
- docs that describe aspiration instead of actual repo state

This is the practical handoff for:

1. where the system actually stands today
2. what materially improved in the last cycle
3. what is still missing
4. how Spark, runtime memory, and the Karpathy-style KB should connect
5. what the next several days should do in order

## Executive Summary

The project is now in a stronger position than the repo had even a day ago, but the nature of the progress matters.

The core runtime memory architecture did not undergo a radical mutation. The main winning lane is still:

- `summary_synthesis_memory`
- `heuristic_v1`

As of the 2026-04-11 cross-repo reruns, that lane is also the current Builder runtime selector again.

What improved materially is:

- benchmark closure and benchmark confidence
- KB scaffold reality
- Spark shadow tooling
- the first real bridges between Spark-shaped replay data and the KB compiler

The honest state is now:

- the memory system is benchmark-serious
- the Spark integration surface is real but still shadow-first
- the KB layer is real but still early
- the combined `memory + KB` answer path is not yet benchmark-proven as a joint system

This means the next phase should not be another generic architecture brainstorm.

It should be:

1. connect real Spark exports into the governed memory and KB workflow
2. make the KB materially useful on top of that runtime
3. preserve the closed benchmark lanes as regression gates
4. then run controlled benchmark work for the remaining open proof surfaces

## What Actually Shipped In This Cycle

This section is here so the next phase does not flatten all recent work into vague phrases like
"we improved Spark" or "we improved the KB."

### Runtime and benchmark substrate

The core winning runtime lane is still:

- `summary_synthesis_memory`
- `heuristic_v1`

The biggest benchmark realities now locked in are:

- local `ProductMemory`: `1266/1266`
- `LongMemEval_s`: `500/500`
- local official-public `BEAM 128K` latest checked-in leader variants: `400/400`
- alternate judged official-public `BEAM` closure at:
  - `128K`
  - `500K`
  - `1M`
  - `10M`

The current cross-repo decision surface is narrower than that historical closure summary:

- for the active Builder runtime choice, the live comparison is now `summary_synthesis_memory` vs `dual_store_event_calendar_hybrid`
- on that exact head-to-head ProductMemory comparison, the current result is tied at `1156/1266`

### Spark-facing integration upgrades

The repo now has concrete Spark-facing bridges instead of disconnected tools:

- `build-spark-kb-from-shadow-replay`
- `build-spark-kb-from-shadow-replay-batch`
- `normalize-spark-builder-export`
- `normalize-spark-builder-export-batch`
- `normalize-spark-telegram-export`
- `normalize-spark-telegram-export-batch`
- `run-spark-shadow-report-from-builder-export`
- `run-spark-shadow-report-from-builder-export-batch`
- `run-spark-shadow-report-from-telegram-export`
- `run-spark-shadow-report-from-telegram-export-batch`
- `build-spark-shadow-failure-taxonomy-from-builder-export`
- `build-spark-shadow-failure-taxonomy-from-builder-export-batch`
- `build-spark-shadow-failure-taxonomy-from-telegram-export`
- `build-spark-shadow-failure-taxonomy-from-telegram-export-batch`
- `build-spark-kb-from-builder-export`
- `build-spark-kb-from-builder-export-batch`
- `build-spark-kb-from-telegram-export`
- `build-spark-kb-from-telegram-export-batch`
- `run-spark-builder-intake-batch`
- `run-spark-telegram-intake-batch`
- `run-spark-builder-telegram-intake`
- `run-spark-builder-state-telegram-intake`

This means the repo can now:

- accept Spark-style shadow replay JSON
- accept Builder-style exports with common alias fields
- normalize them into the replay contract
- replay them through governed memory
- export a governed snapshot
- compile a visible KB vault from that snapshot

### KB scaffold upgrades

The KB layer is materially more real than it was at the start of the cycle:

- real snapshot-based `build-spark-kb`
- real `validate-spark-kb-inputs`
- real `spark-kb-health-check`
- checked-in valid and invalid example bundles
- smoke wrappers under `docs/examples/`
- CI smoke coverage
- filed outputs under `wiki/outputs/`
- repo-source ingest into `raw/repos/`
- first contradiction and stale-state signals in the maintenance output
- replay failure taxonomy now files into the KB itself, not only separate JSON diagnostics

### Benchmark observability upgrades

The benchmark-report CLI was heavily enriched so noisy artifact churn can be treated as an
operator visibility problem instead of a reasoning burden.

That work improved:

- noisy-family ranking
- noisy-series drilldown
- next-step recommendations
- compact sequence summaries
- transition summaries
- family competition summaries

It matters, but it should still be classified correctly:

- benchmark observability improvement
- not a direct mutation of the memory substrate

## What Is Actually Strong Right Now

### 1. Core benchmark evidence

Current strong measured lanes:

- local `ProductMemory`: `1266/1266`
- `LongMemEval_s`: `500/500`
- local official-public `BEAM 128K` latest checked-in leader variants: `400/400`
- alternate judged official-public `BEAM` closure at:
  - `500K`
  - `1M`
  - `10M`

Interpretation:

- current-state reconstruction is strong
- correction and contradiction handling are strong
- temporal and multi-session recall are strong
- the architecture is not speculative anymore

Important honesty boundary:

- the judged official-public `BEAM` closure is on the alternate OpenAI-compatible MiniMax judge path
- exact upstream OpenAI judge parity is still open

### 2. Spark integration surface

The repo now has real Spark-facing runtime surface, not just doctrine:

- `SparkMemorySDK`
- `SparkShadowIngestAdapter`
- shadow replay validation commands
- shadow replay report commands
- KB compile commands
- maintenance commands

More importantly, the repo now has first bridges instead of isolated surfaces:

- `build-spark-kb-from-shadow-replay`
- `build-spark-kb-from-shadow-replay-batch`
- `normalize-spark-builder-export`
- `normalize-spark-builder-export-batch`
- `normalize-spark-telegram-export`
- `normalize-spark-telegram-export-batch`
- `run-spark-shadow-report-from-builder-export`
- `run-spark-shadow-report-from-builder-export-batch`
- `run-spark-shadow-report-from-telegram-export`
- `run-spark-shadow-report-from-telegram-export-batch`
- `build-spark-shadow-failure-taxonomy-from-builder-export`
- `build-spark-shadow-failure-taxonomy-from-builder-export-batch`
- `build-spark-shadow-failure-taxonomy-from-telegram-export`
- `build-spark-shadow-failure-taxonomy-from-telegram-export-batch`
- `build-spark-kb-from-builder-export`
- `build-spark-kb-from-builder-export-batch`
- `build-spark-kb-from-telegram-export`
- `build-spark-kb-from-telegram-export-batch`
- `run-spark-builder-intake-batch`
- `run-spark-telegram-intake-batch`
- `run-spark-builder-telegram-intake`

Interpretation:

- we can accept Spark-shaped exported conversations
- normalize them into the replay contract
- replay them through governed memory
- export one combined snapshot
- compile a visible KB vault from the result

This is still export-driven, not live product wiring, but it is no longer a conceptual gap.

### 3. Karpathy-style KB direction

The KB is no longer just a document or idea. The repo now has:

- `raw/` as intake shelf
- `wiki/` as compiled markdown layer
- generated `CLAUDE.md`
- compiled source pages
- compiled timeline syntheses
- maintenance report output
- filed output pages under `wiki/outputs/`
- KB validation
- KB health checks
- checked-in examples
- CI smoke coverage

Interpretation:

- the KB layer is real
- it is inspectable
- it is downstream of governed memory rather than a second truth store

## What Materially Improved In The Last Cycle

This section matters because not all improvements had the same architectural weight.

### A. What improved benchmark confidence

The repo strengthened proof more than it changed the algorithm.

The biggest benchmark realities are:

- official-public judged `BEAM` evidence is now much stronger across the large-context scales
- the local strong lanes remain intact
- the benchmark-report CLI can now summarize noisy benchmark artifact churn much more precisely

The long benchmark-report enrichment lane improved:

- observability
- drilldown quality
- artifact triage
- recommended follow-up navigation

That work is useful, but it mostly improves benchmark hygiene and operator visibility, not the memory substrate itself.

### B. What improved product integration readiness

The most important product-adjacent improvement is that Spark shadow replay and the KB compiler are now connectable.

Before:

- Spark shadow replay existed
- KB compile existed
- they were adjacent tools

Now:

- a shadow replay can directly produce a governed memory snapshot
- that snapshot can directly compile a KB vault
- a batch of replay slices can accumulate into one vault
- a Builder export with common alias fields can be normalized into that path

This is the first real bridge from Builder-shaped traffic to a visible external-brain surface.

The new Telegram path matters because it gives us a lightweight real-chat proving lane before deeper Spark product wiring:

- Telegram bot messages can now be normalized into the same shadow replay contract
- those messages can be replayed through governed memory
- the replay can emit the same shadow report, failure taxonomy, and KB vault as the Builder path
- this creates a practical operator loop for testing memory behavior with a handful of real conversations before broader benchmark resumption

The most practical version of that loop now targets Builder's own Telegram runtime artifacts directly:

- Builder already owns live Telegram polling
- Builder already writes `.tmp-telegram-*.json` update artifacts during local/runtime verification
- `run-spark-builder-telegram-intake <builder_dir> <output_dir>` now scans those artifacts directly and pushes them through the same memory report, failure taxonomy, and KB compile path
- this is now the shortest path from "send a few messages to the Telegram bot" to "inspect memory behavior and a human-readable KB surface"

We now also have a stronger Builder-native replay bridge that reads the persisted runtime event log instead of temp files:

- Builder homes persist `state.db`
- `telegram_runtime` writes `intent_committed` and `delivery_succeeded` events there
- `run-spark-builder-state-telegram-intake <builder_home> <output_dir>` now reconstructs conversations from those events and pushes them through the same memory report, failure taxonomy, and KB compile path
- `run-spark-builder-state-telegram-intake <builder_home> <output_dir> --chat-id <telegram_chat_id>` now scopes replay to one live Telegram thread, which is the most practical way to test a few fresh bot messages without replaying the full Builder Telegram history
- this is the best current bridge for real Telegram memory testing because it captures both inbound user text and outbound delivered replies from the Builder runtime itself

### C. What did not improve enough yet

These still remain materially underbuilt:

- real Spark traffic evidence
- direct runtime metrics
- KB-as-answer-path integration
- cross-source syntheses inside the KB
- benchmarked proof that `memory + KB` beats memory alone

## Current Completion Matrix

This is the shortest high-signal read of the system right now.

### A. Memory runtime

Status: strong

What is true:

- benchmark-serious on multiple surfaces
- correction and contradiction handling are strong
- long-horizon reconstruction is strong
- the runtime already has governed writes, reads, maintenance hooks, and snapshot export

What is not yet true:

- not every public evidence class is closed
- exact-official `BEAM` judge parity is still open
- runtime metrics are not yet first-class

### B. Spark connection

Status: real but still shadow-first

What is true:

- replay contract exists
- Builder-export alias normalization exists
- single-file and batch replay-to-KB bridges exist
- Spark-shaped data can already enter the governed-memory-plus-KB path

What is not yet true:

- no live Spark API or DB wiring
- no persistent real-traffic replay backlog yet
- no measured failure taxonomy on real Builder exports yet
- no promotion gate based on real Spark usage metrics yet

### C. KB / LLM wiki layer

Status: real but still early

What is true:

- there is a visible compiled markdown layer
- the KB is downstream of governed memory
- the KB is inspectable and health-checkable
- the KB already supports source pages, syntheses, filed outputs, and maintenance reports

What is not yet true:

- it is not yet a rich external-brain product
- it does not yet have broad cross-source research ingest
- it does not yet have broad query-answer filing against the wiki itself
- it is not yet part of a proven answer-time improvement loop

### D. Combined memory plus KB system

Status: hypothesis stage

What is true:

- memory is strong
- KB is real
- Spark-shaped data can feed the KB

What is not yet true:

- there is no clean A/B proving `memory + KB` beats `memory only`
- no stable read-time integration doctrine has been proven under benchmark load
- no latency-versus-quality tradeoff has been measured honestly yet

## Current Architecture Read

### The correct architecture split

Spark should own:

- conversation flow
- user intent interpretation
- policy and permissions
- final answer assembly
- product-specific orchestration

The memory runtime should own:

- typed writes
- typed reads
- provenance-bearing retrieval
- abstention
- maintenance hooks
- governed snapshot export

The KB layer should own:

- human-readable compiled pages
- provenance surfaces
- timeline and state inspection
- filed answer pages
- contradiction, staleness, and gap visibility

The KB should not own truth.

The KB should be:

- compiled from governed memory
- inspectable by users and operators
- a product surface
- an external-brain layer

That is the right Karpathy-style shape for this repo.

### What the architecture is still missing

The strongest missing architectural pieces are:

1. a real Spark-side entity and field normalizer
2. a real Spark-side memory write gate
3. a real Spark-side query router
4. runtime metrics emitted from actual Spark usage
5. a first-class compile loop from governed memory plus approved sources into richer wiki pages
6. a benchmarked read path that can use the KB layer when it helps

## What Is Still Missing

### 1. Remaining benchmark proof gaps

These are still open:

- broader clean `LoCoMo`
- canonical `GoodAI`
- exact-official upstream OpenAI judge parity for `BEAM`

Interpretation:

- the system is strong
- the proof stack is not fully complete

### 2. Remaining Spark gaps

Still missing:

- replayable real Builder trace batches from product traffic
- longitudinal shadow reports on actual traffic
- product failure taxonomy from real traces
- live promotion criteria backed by measured Spark behavior

### 3. Remaining KB gaps

Still missing:

- incremental ingest of external articles, repos, papers, and datasets
- cross-source concept pages beyond runtime memory pages
- broad filed query outputs generated against the wiki itself
- scheduled compile loops
- richer contradiction and gap-filling passes
- Obsidian-native dashboard surfaces

### 4. Remaining combined-system gap

Most important missing truth:

- we do not yet have a clean measured claim that `memory + KB together` improves benchmark results over memory alone

That is not a philosophical gap. It is an experimental gap.

## What Must Be True Before We Can Honestly Claim Memory Plus KB Improvement

The repo should not claim that the combined system is better until all of these are true:

1. the KB is wired into the actual answer path being evaluated, not only compiled after the fact
2. there is a clear `memory only` baseline on the same slice
3. there is a clear `memory + KB` run on that same slice
4. latency and cost deltas are measured alongside answer quality
5. the comparison is narrow enough that failures can still be explained mechanistically

Until then, the correct language is:

- the KB improves inspectability and human readability now
- it may improve answer quality later
- that answer-quality claim is not proven yet

## What We Know About Memory Plus KB Right Now

The honest answer today is:

- the KB layer is real
- the memory layer is strong
- the combined system has not yet been benchmarked cleanly as a combined answer path

What we do know:

- the KB can now be compiled from governed memory snapshots
- Spark-shaped shadow and Builder-export conversations can feed that path
- the KB improves inspectability, human readability, and post-hoc synthesis potential

What we do not know yet:

- how much it helps retrieval quality on benchmarked answers
- whether it improves difficult temporal, contradiction, or summarization categories
- whether it adds latency or drift that outweighs benefits

So the next phase should treat `memory + KB` as a hypothesis to test, not as a claim already proven.

## Where We Are Lacking Most

If we are ruthless about leverage, the main deficiencies are:

### A. Product-shaped evidence is weaker than benchmark evidence

We have stronger benchmark proof than Spark product proof.

That means the next best move is not another benchmark-only detour.

It is:

- get real Spark exports through the new bridges
- inspect the resulting runtime and KB surfaces
- learn from that

### B. Human-readable knowledge still lags behind memory quality

The memory runtime is more mature than the KB product surface.

Right now, the system knows more than the user-facing or operator-facing KB exposes.

That is exactly where the Karpathy-style wiki layer should help:

- turn hidden state into visible pages
- turn replay evidence into inspectable history
- turn benchmark failures into dossiers
- turn mutation rationale into durable product knowledge

### C. The mutation loop is still more benchmark-centric than Spark-centric

The next serious architecture mutations should be informed by both:

- benchmark failure clusters
- Spark trace failure clusters

If we only optimize for benchmarks, the product can still fail.
If we only optimize for product traces, benchmark rigor can degrade.

The next loop has to use both.

## Exact Recommended Next Phase

This is the recommended sequence for the next few days.

## Day 1: Lock the Spark export bridge as the new intake path

Goal:

- prove we can take real Spark Builder exports and compile a real KB vault without hand editing

Required actions:

1. obtain one real Spark Builder export batch
2. run:
   - `run-spark-builder-intake-batch`
3. inspect:
   - accepted vs rejected writes
   - missing structured hints
   - unsupported reasons
   - generated current-state pages
   - generated evidence pages
   - generated filed outputs
4. document failures as a first Spark failure taxonomy

Definition of success:

- real Builder export enters the repo path cleanly
- KB compile succeeds
- health checks pass
- we know exactly what Builder metadata is still missing

## Day 2: Make the KB materially more useful

Goal:

- upgrade the KB from "correct scaffold" to "useful operator and user surface"

Required actions:

1. add richer filed outputs from Spark replay:
   - per-conversation summaries
   - current-state deltas
   - unsupported-write dossiers
2. add first cross-source syntheses:
   - runtime memory overview
   - Spark replay summary
   - benchmark proof status
3. add first mutation dossier pages:
   - what failed
   - why it failed
   - what to test next

Definition of success:

- the KB becomes a useful readable workspace
- it starts to tell operators what happened, not just mirror files

## Day 3: Start the first combined-system experiment

Goal:

- measure whether the KB can help the answer path instead of just documenting it

Required actions:

1. choose a narrow evaluation slice
2. define two modes:
   - memory only
   - memory plus compiled KB support
3. run a controlled comparison
4. inspect:
   - answer quality change
   - provenance quality
   - latency cost
   - failure mode shifts

Definition of success:

- one honest A/B result exists
- even a negative result is useful if it clarifies where KB helps and where it does not

## Day 4 And After: Resume the open benchmark lanes with stronger product context

Once Spark integration is less speculative, return to the remaining proof stack:

1. exact-official `BEAM` judge parity
2. broader clean `LoCoMo`
3. canonical `GoodAI`

But do it with a better loop:

- benchmark failures become KB dossiers
- Spark failures become KB dossiers
- mutations are justified by both

## Workstream Done Criteria

These are the stop conditions that should prevent the next few days from drifting.

### Spark connection workstream

This workstream is done enough for the next phase when:

- at least one real Builder export batch passes through the repo without hand editing
- the resulting KB compile is healthy
- we have a written failure taxonomy from that real export
- we know which Builder fields or metadata still need to be exported or normalized

### KB workstream

This workstream is done enough for the next phase when:

- the KB tells a readable story about what happened in a replay batch
- filed outputs include more than one demo answer page
- benchmark failures and Spark failures can both be represented as KB pages
- a human operator can inspect provenance, contradictions, and stale claims without reading raw JSON

### Combined-system experiment workstream

This workstream is done enough for the next phase when:

- one narrow A/B exists
- the repo has a written answer about quality delta, latency delta, and failure-mode shift
- we know whether to continue widening the KB answer path or keep it as an inspection layer longer

### Benchmark workstream

This workstream is done enough for the next phase when:

- the currently closed lanes remain stable as regression gates
- one next evidence class is chosen explicitly instead of mixing several at once
- resumed benchmark work is informed by Spark and KB findings, not isolated from them

## Concrete Gaps To Close In Spark

These are the concrete Spark-side requirements that should now be treated as implementation targets, not vague doctrine:

1. stable subject/predicate normalization
2. explicit write-worthiness gating
3. explicit read routing
4. provenance-preserving rendering
5. replay batch export on demand
6. batch report persistence over time
7. periodic maintenance execution
8. artifact storage for replay and KB outputs

The current repo now gives Spark a clean place to plug into these targets.

## Concrete Gaps To Close In The KB

These are the most valuable KB upgrades next:

1. richer filed outputs from real Spark traces
2. benchmark failure pages
3. mutation dossier pages
4. cross-source concept and entity pages
5. scheduled compile loops
6. contradiction and stale-claim dashboards
7. Dataview or Obsidian-native readable rollups

The guiding rule is:

- the KB should make the system more readable to humans and more useful to downstream LLM reasoning

It should not become another opaque storage layer.

## Concrete Gaps To Close In Benchmarks

### Preserve first

Do not casually disturb:

- `ProductMemory`
- `LongMemEval_s`
- local `BEAM 128K`
- alternate judged `BEAM` closure

These should behave like regression gates.

### Then close remaining evidence classes

In order:

1. exact-official `BEAM` judge parity
2. next clean `LoCoMo` lane
3. first canonical `GoodAI`

### Then test the combined story

After the Spark and KB path is cleaner:

1. memory only
2. Spark-shaped memory path
3. memory plus KB

That is the honest way to claim improvement.

## General Insights For The Next Few Days

These are the biggest strategic insights from the current repo state.

### 1. The best next move is Spark-first, not benchmark-first

The benchmark story is already good enough to justify product integration work.

The bigger uncertainty now is:

- how this behaves in Spark-shaped use
- what Builder metadata is missing
- how readable and useful the KB is on real traces

So the next move should be Spark-first.

### 2. The KB is now strategically important

The KB is no longer optional polish.

It is the layer that can:

- make memory inspectable
- support human trust
- preserve mutation reasoning
- expose failures and provenance
- potentially support stronger answer-time synthesis later

That is exactly why the Karpathy-style wiki layer matters here.

### 3. The next architecture improvements should be small and evidence-led

Do not broad-rewrite the memory engine now.

Instead:

1. identify failure clusters
2. map them to mechanisms
3. define a small mutation
4. rerun the relevant lane

This is now the right maturity model for the repo.

### 4. Human readability is a real product goal

Human readability is not secondary to benchmark quality.

In this system it is part of quality because:

- it makes state auditable
- it makes errors legible
- it makes corrections explainable
- it makes the KB an actual external brain instead of a file dump

The next KB work should explicitly optimize for this.

## Practical Restart Order

If work resumes later, this should be the order:

1. get a real Spark Builder export batch
2. run `build-spark-kb-from-builder-export`
3. inspect the replay and KB outputs
4. write the first Spark failure taxonomy
5. upgrade the KB pages based on what is missing
6. define the first memory-only vs memory-plus-KB comparison
7. then return to the remaining open benchmark closures

## Resume Checklist After Spark Connection Work

Once the immediate Spark connection push is complete, the next restart should be:

1. confirm the real-export path still works end to end
2. capture the missing Builder metadata and unsupported-write reasons in documentation
3. convert the first real Spark failures into KB dossier pages
4. decide whether the first A/B slice should be Spark-shaped replay, benchmark slice, or both
5. run the first `memory only` vs `memory + KB` comparison
6. only after that, resume the next open benchmark evidence lane

This ordering matters.

The bad order would be:

- go straight back into broad benchmark work
- leave Spark integration ambiguous
- leave the KB readable but non-operational

The correct order is:

- Spark intake first
- KB usefulness second
- combined-system measurement third
- wider benchmark closure fourth

## Questions This Document Should Still Answer Later

If someone returns to this repo after the Spark push, this file should still answer:

1. what was already strong before touching Spark again
2. what actually shipped in the recent cycle
3. whether the KB was already real or still hypothetical
4. what was still missing before a truthful `memory + KB` claim
5. what exact order to resume in

If any of those answers becomes unclear, this file should be updated rather than replaced by another overlapping roadmap.

## Commands To Remember

### Builder and Spark replay

```powershell
python -m domain_chip_memory.cli normalize-spark-builder-export <builder_export.json> --write <normalized.json>
python -m domain_chip_memory.cli normalize-spark-builder-export-batch <builder_export_dir> --write <normalized.json>
python -m domain_chip_memory.cli run-spark-shadow-report-from-builder-export <builder_export.json> --write <report.json>
python -m domain_chip_memory.cli run-spark-shadow-report-from-builder-export-batch <builder_export_dir> --write <report.json>
python -m domain_chip_memory.cli build-spark-shadow-failure-taxonomy-from-builder-export <builder_export.json> --write <taxonomy.json>
python -m domain_chip_memory.cli build-spark-shadow-failure-taxonomy-from-builder-export-batch <builder_export_dir> --write <taxonomy.json>
python -m domain_chip_memory.cli build-spark-kb-from-builder-export <builder_export.json> <output_dir> --write <summary.json>
python -m domain_chip_memory.cli build-spark-kb-from-builder-export-batch <builder_export_dir> <output_dir> --write <summary.json>
python -m domain_chip_memory.cli run-spark-builder-intake-batch <builder_export_dir> <output_dir> --write <intake.json>
python -m domain_chip_memory.cli build-spark-kb-from-shadow-replay <shadow.json> <output_dir> --write <summary.json>
python -m domain_chip_memory.cli build-spark-kb-from-shadow-replay-batch <shadow_dir> <output_dir> --write <summary.json>
```

### KB validation

```powershell
python -m domain_chip_memory.cli validate-spark-kb-inputs <snapshot_file>
python -m domain_chip_memory.cli build-spark-kb <snapshot_file> <output_dir>
python -m domain_chip_memory.cli spark-kb-health-check <output_dir>
```

### Benchmark artifact triage

```powershell
python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir artifacts/benchmark_runs --repo-root . --only-noisy --summary-only --top-series-limit 5
```

## Worktree Reminder

The repo still tends to accumulate unrelated untracked benchmark and tmp artifacts under:

- `artifacts/benchmark_runs/`
- `artifacts/tmp/`
- `tmp/`

These should continue to be treated as separate from the narrow tracked implementation line unless a specific cleanup or promotion lane is active.

## Bottom Line

The project is now strong enough that the next phase should not be "more theory."

The right next phase is:

- connect real Spark exports
- make the KB genuinely readable and useful
- use Spark and benchmark failures together to guide mutations
- then finish the remaining benchmark proof surfaces

The memory system is already serious.
The KB is real but early.
The Spark bridge is now real enough to start using.

The next job is to turn those three truths into one coherent product and one coherent proof story.
