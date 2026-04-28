# OSS Memory Borrowing Plan

Date: 2026-04-28

This document decides how Spark should borrow from open-source memory systems without reinventing every layer. The goal is speed with clean ownership: use existing permissive systems where they solve a real layer, keep Spark-specific contracts where our product and safety requirements are different.

## Policy

- Prefer permissive licenses: MIT, Apache-2.0, BSD, ISC, MPL-2.0 only after file-level obligations are understood.
- Avoid GPL/AGPL/copyleft runtime dependencies unless the user explicitly approves that tradeoff.
- Prefer dependency or adapter integration over copying source files.
- Vendor source only when the copied surface is small, stable, and easier than adding a service dependency.
- Every borrowed code path needs:
  - source repository URL
  - license
  - upstream version or commit
  - local owner module
  - reason for borrowing
  - attribution/notice handling
  - feature flag or rollback path
- External systems must not replace Spark authority order, salience gates, target-repo binding, or source explanation contracts.

## Candidate Stack

| System | License | Borrow Mode | Spark Role | Do Not Use For |
| --- | --- | --- | --- | --- |
| Graphiti / Zep OSS core | Apache-2.0 | dependency or sidecar adapter | Temporal graph sidecar: entities, relationships, episodes, validity windows, provenance | Primary current-state authority |
| Hindsight | MIT | dependency/API adapter and pattern borrowing | Experience/procedural memory: learn from corrections, failed tool calls, repeated mistakes | Replacing typed facts or capsule authority |
| MemMachine | Apache-2.0 | architecture borrowing, optional adapter | Multi-layer working/profile/episodic memory model, ground-truth-preserving retrieval ideas | Immediate runtime replacement |
| Mem0 OSS | Apache-2.0 | shadow baseline and extraction/rerank inspiration | Compare extraction, entity linking, and multi-signal retrieval against Spark | Unreviewed automatic writes |
| Letta/MemGPT | license depends on component/version; verify before code import | pattern borrowing first | Memory hierarchy, context-window rebuilding, explicit memory operations | Copying code without version/license review |
| gbrain / BrainBench-style evals | verify per repo/artifact | test inspiration | Source-swamp, temporal, identity, provenance, and adapter-contract eval packs | Runtime dependency |

## Build Order

1. Salience Gate v1 in Builder
   - Decide `drop`, `scratchpad`, `raw_episode`, `structured_evidence`, `current_state_candidate`, or `current_state_confirmed`.
   - Add `salience_score`, `confidence`, `promotion_stage`, `mention_count`, `decay_after`, and `why_saved`.
   - Keep explicit phrases such as `for later` as high-confidence signals, not the only memory path.

2. Graphiti Sidecar v1
   - Ingest only clean episodes and typed entity-state changes.
   - Store Graphiti IDs/provenance back on Spark records.
   - Disable optional telemetry by default.
   - Return graph hits as advisory candidates with validity windows and source labels.

3. Hindsight Experience Lane
   - Capture user corrections, failed builds, wrong target selection, timeout recovery, and bad self-review as experiences.
   - Retrieve procedural lessons before repeating the same operational mistake.

4. Semantic Consolidation
   - Generate daily/project summaries: decisions, open bugs, target repos, promises, pending tasks, completed work.
   - Feed those summaries to episodic trace and Graphiti, not raw transcripts.

5. Memory Quality Dashboard Integration
   - Move useful standalone dashboard pieces into `spawner-ui`.
   - Wire it to real ledgers: salience decisions, promotions, quarantines, delivery registry, graph sidecar hits, capsule packets.

## Copying Code Checklist

Before copying code from any OSS repo:

- [ ] Confirm exact license from repository root.
- [ ] Confirm no copied file has a different header/license.
- [ ] Add or update `NOTICE`/attribution when needed.
- [ ] Preserve SPDX/header where present.
- [ ] Record upstream commit or release.
- [ ] Add local tests proving the borrowed code works in Spark's contract.
- [ ] Wrap runtime behavior behind a feature flag if it can affect memory writes or recall.

## Adapter Checklist

Before adding a dependency/service:

- [ ] Confirm install path on Windows.
- [ ] Confirm local/offline mode if available.
- [ ] Confirm telemetry settings.
- [ ] Confirm state location under `.spark/state`.
- [ ] Confirm backup/export path.
- [ ] Confirm failure mode: Spark must degrade to current-state/evidence memory if the sidecar is down.
- [ ] Add `spark status` visibility.
- [ ] Add diagnostics scan checks.

## First Concrete Imports

1. Graphiti adapter stub in `domain-chip-memory`
   - `add_episode`
   - `search`
   - `health`
   - Spark-to-Graphiti episode mapper
   - Graphiti-to-Spark candidate mapper

2. Builder salience module
   - no external dependency initially
   - later compare against Mem0/Hindsight extraction behavior

3. Hindsight experiment lane
   - start as shadow/prototype
   - test on wrong-build-target, stale-repo-context, timeout-recovery, and bad-self-review cases

## Non-Negotiable Spark Contracts

- Current state beats graph and episodic memory for active facts.
- Historical state is used only when the user asks historical questions.
- Diagnostics and workflow state are advisory unless directly relevant.
- Target repo/build target must be confirmed before file-writing missions.
- Every memory answer can explain its source class and why it was recalled.
- Every memory write can explain why it was saved or why it was rejected.
