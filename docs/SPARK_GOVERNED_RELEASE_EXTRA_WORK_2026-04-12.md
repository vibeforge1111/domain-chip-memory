# Spark Governed Release Extra Work

This file tracks worthwhile follow-on work around the governed Spark memory KB
surface that is not required for the first harness and TUI integration pass.

## Immediate Integration Lane

- expose the governed release surface to `spark-agent-harness` as an honest
  memory-bridge status instead of a hidden local convention
- surface that status inside `spark-tui-lab` so `domain-chip-memory` shows as
  connected when the bridge and governed release are actually ready
- add cross-repo tests that prove the harness reports governed memory readiness
  and the TUI renders the connected state honestly

## Near-Term Product Work

- let Builder-side release/load jobs consume `governed-release.json` or
  `governed-release-gate.json` directly instead of reaching into repo-local tmp
  paths
- replace the current local-only governed release discovery with an explicit
  configured publish root
- add rollover support for multiple governed releases and one stable "current"
  pointer that is not version-suffixed
- record publish metadata like source commit, publish timestamp, and originating
  ablation artifacts in the top-level manifest

## Operational Hardening

- add stale-release detection so old governed publishes fail closed instead of
  looking permanently healthy
- add explicit schema versions for `governed-release.json`,
  `governed-release-summary.json`, and `governed-release-gate.json`
- add one compact CLI smoke command that verifies publish root, summary, gate,
  and representative fact reads together
- add path-config tests for Windows and non-Windows publish roots instead of
  relying on the current Desktop-local assumptions

## Product Signal Expansion

- attach predicate-level coverage summaries to the top-level governed release
  summary so downstream clients can explain what the publish actually covers
- add promoted-target lineage details to the top-level summary for audit views
- expose cleanroom and gauntlet boundary counts separately in a client-friendly
  shape instead of only via nested action-bucket fields
- add optional example queries to the publish root so UIs can demo supported
  reads without bespoke fixtures

## Benchmark Follow-Ons

- move from the current compact Spark slice to a larger governed replay slice
  once the Builder-side consumer exists
- add repeatable regression probes for the four currently promoted predicates:
  `profile.hack_actor`, `profile.spark_role`, `profile.timezone`,
  `profile.home_country`
- add a governed release regression that fails if a cleanroom or gauntlet lane
  becomes exposed by default

## Non-Goals For This Pass

- changing benchmark scoring methodology
- widening the allowed policy surface beyond the current four promoted
  regression targets
- replacing the existing `active-release-*` artifacts inside
  `domain-chip-memory`
