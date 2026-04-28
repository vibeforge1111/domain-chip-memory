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

## Salience Borrowing Sources

Spark should not invent salience from scratch. The first implementation should borrow the scoring shape from mature permissive agent-memory projects and adapt it to Spark's operating-system workflow.

Primary salience sources:

| Source | License | Borrowed Idea | Spark Adaptation |
| --- | --- | --- | --- |
| `joonspk-research/generative_agents` | Apache-2.0 | Memory stream ranking by recency, importance, and relevance; reflection when important memories accumulate | Base salience score: `importance + relevance + recency`, with Spark-specific weights |
| `mem0ai/mem0` | Apache-2.0 | Single-pass extraction, deduplication, entity linking, multi-signal retrieval | Compare Spark salience/extraction against Mem0 in shadow mode |
| `vectorize-io/hindsight` | MIT | Learn from corrections, failed actions, and repeated mistakes | Feed failure/correction experiences into procedural memory, not durable user facts |
| `getzep/graphiti` | Apache-2.0 | Temporal provenance, entity relationships, validity windows | Use graph provenance and temporal validity as retrieval gates, not direct salience authority |

Reference-only sources:

These are permissively licensed, but should not be copied or treated as authority until they pass code-quality, activity, star/community, and architecture review.

| Source | License | Possible Use | Risk Control |
| --- | --- | --- | --- |
| `joonspk-research/genagents` | MIT | Memory/reflection API shape from later generative-agent simulation work | Ideas only; no runtime dependency; verify maturity before copying code |
| `MemaryAI/MemaryAI` | MIT | Entity frequency and recency tracking for importance | Ideas only; implement recurrence counters ourselves unless deeper review says otherwise |

Initial Spark salience formula:

```text
salience =
  explicitness_signal
  + active_task_relevance
  + entity_importance
  + decision_action_signal
  + correction_signal
  + recurrence_signal
  + source_authority
  - uncertainty_penalty
  - small_talk_penalty
  - privacy_or_sensitivity_penalty
```

Initial promotion bands:

- `drop`: not useful or unsafe to store.
- `scratchpad`: useful only inside this active conversation.
- `raw_episode`: meaningful event, but not yet a durable fact.
- `structured_evidence`: useful support/provenance, not current truth.
- `current_state_candidate`: plausible current fact that needs confirmation or recurrence.
- `current_state_confirmed`: explicit or repeated enough to become active typed state.

Spark-specific rule:

- `for later`, `remember`, and direct `current X is` language can bypass to high explicitness, but should still pass privacy/safety and target-scope checks.
- Corrections such as `Actually, Cem...` or `No, the target repo is spawner-ui` should become authoritative supersession candidates immediately.
- Build/tool failures should not become user facts; they should become Hindsight/procedural experiences.

Salience operator:

- The Builder memory kernel should own the final salience decision before any memory is promoted.
- Telegram, Spawner, diagnostics, and Codex can submit candidate memory events, but they should not directly promote durable memory.
- LLM extraction can propose facts, entities, and importance rationales, but a deterministic policy gate should choose the promotion band.
- Graphiti should enrich entity/time/provenance context; Hindsight-style procedural memory should enrich correction/failure lessons.
- Every promoted item must record `why_saved`, `source_route`, `promotion_stage`, and whether it came from explicit user intent, repeated recurrence, active task relevance, or correction/supersession.

## Non-Negotiable Spark Contracts

- Current state beats graph and episodic memory for active facts.
- Historical state is used only when the user asks historical questions.
- Diagnostics and workflow state are advisory unless directly relevant.
- Target repo/build target must be confirmed before file-writing missions.
- Every memory answer can explain its source class and why it was recalled.
- Every memory write can explain why it was saved or why it was rejected.
