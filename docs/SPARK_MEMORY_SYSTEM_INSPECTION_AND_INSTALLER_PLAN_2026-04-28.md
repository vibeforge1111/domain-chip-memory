# Spark Memory System Inspection And Installer Plan 2026-04-28

This pass answers a specific integration question: have we inspected the live Spark systems enough to know where the memory stack should plug in, and which open-source systems should become installer-managed dependencies?

Short answer: not fully before. Now the core shape is clear enough to build from without guessing.

## Repos Inspected

| Repo | Role | Integration Finding |
| --- | --- | --- |
| `domain-chip-memory` | Spark memory authority SDK and benchmark pack | Owns current-state, entity-state, historical state, evidence/event records, retention, sidecar contracts, and benchmark doctrine. |
| `spark-intelligence-builder` | Runtime memory kernel behind Telegram/Researcher | Owns routing, profile/entity writes, hybrid retrieval, capsules, source explanations, and the future salience gate. |
| `spark-cli` | Installer/operator CLI | Installs `telegram-starter`, which already includes `domain-chip-memory`; no memory-sidecar bundle/profile exists yet. |

## What Is Already Real

- `domain-chip-memory` is already installed by the default Spark starter bundle.
- `SparkMemorySDK` is the right authority/control-plane boundary.
- Generic entity-state memory now handles current and previous values for workflow-like objects: owner, status, location, deadline, preference, blocker, priority, decision, next action, and metric.
- `MemorySidecarAdapter` exists in `domain-chip-memory` with disabled-by-default Graphiti-compatible and Mem0 shadow adapters.
- Builder already has `hybrid_memory_retrieve` with current-state, historical-state, evidence, events, recent-conversation, wiki packet, and sidecar-shadow lanes.
- Telegram/source-explanation acceptance has proven current-state priority, stale/current conflict handling, previous-value recall, and entity summaries.
- `spark-cli` has a registry/bundle model, so optional memory sidecars can be added cleanly as bundle members or install profiles.

## What Is Not Yet Real

- Graphiti is not a live backend yet. The adapter is a contract/stub, not a real `graphiti-core` integration.
- Mem0 is not a live shadow comparator yet. The adapter is a contract/stub, not a real `mem0ai` integration.
- Builder writes still need a first-class salience gate before durable promotion.
- `for later` is still doing too much work as an explicit save command.
- The installer has only `telegram-starter`; it does not expose `memory-graphiti`, `memory-sidecars`, or a similar optional profile.
- Sidecar health is not yet visible in `spark status`, `spark verify`, or diagnostics.
- Hindsight-style procedural memory is not integrated. We only have the plan for wrong-target, timeout, failed-tool, correction, and self-review lessons.
- Episodic recall is still thin. In `spark-intelligence-builder`, `src/spark_intelligence/context/capsule.py` currently renders a 5,000-character capsule by default, includes only 3 recent same-session turn pairs, and compacts each recent turn to 260 characters.
- Repo resolution and local computer traversal are still not treated as first-class memory/capability context, which is why wrong-target builds and stale repo assumptions can recur.

## Critical Memory Queue

These items are now P0/P1 because they determine whether Spark feels continuous across real work, not just whether slot recall passes.

| Queue Item | Priority | Required Layer | Build Direction |
| --- | --- | --- | --- |
| Episodic recall | P0 | Semantic consolidation + episodic trace | Store session/day/project summaries so Spark can answer "what did we build today?", "what changed?", and "what else do you remember?" without raw transcript replay. |
| Source-aware recall | P0 | Retrieval packet + answer trace | Every answer should distinguish current state, older memory, raw episode, graph sidecar, diagnostics, workflow residue, inference, and unverified claims. |
| Timeout/task recovery memory | P0 | Procedural lane + pending task ledger | Store original request, target repo/component, active command/mission, timeout point, last evidence, and next retry step. |
| Semantic compression | P0 | Daily/project summarizer | Move beyond archive/delete/supersede into durable summaries of decisions, bugs, promises, open tasks, and changed facts. |
| Larger context memory | P0 | Capsule compiler v2 + retrieval budget manager | Support 200k+ total available memory context through external packets and selective assembly, not by dumping 200k tokens into every Telegram reply. |
| Repo resolution | P0 | Local environment index + target confirmation gate | Maintain a live map of known repos, module ownership, installer state, dirty worktrees, active targets, and capability permissions. |
| Computer traversal | P1 | Local project index + operator capability state | Spark should know what it can inspect through Spawner/Codex/local tools and should not underclaim or hallucinate filesystem access. |

The 200k+ target means "Spark can search, rank, and assemble from a large external context reservoir." The per-answer packet should stay compact unless the user asks for a deep reconstruction.

## Dependency Decision

Do not add heavy memory systems to the default `telegram-starter` install yet.

Default Spark should stay light and reliable:

- `spark-intelligence-builder`
- `domain-chip-memory`
- `spark-telegram-bot`
- `spark-character`
- `spark-researcher`
- `spawner-ui`

Add sidecars as optional installer-managed modules or extras:

| System | Current Package/Install Shape | License | Spark Decision |
| --- | --- | --- | --- |
| Graphiti | `graphiti-core`, with extras such as `graphiti-core[kuzu]` or `graphiti-core[falkordb]` | Apache-2.0 | First real temporal graph sidecar, disabled by default, below current-state authority. |
| Mem0 | `mem0ai`, optional `mem0ai[nlp]` | Apache-2.0 | Shadow comparator for extraction, entity linking, deduplication, and retrieval quality. Not authority. |
| Hindsight | Self-hosted Docker/MCP/API service; repo is MIT | MIT | Procedural/experience memory candidate for failures, corrections, target-binding, and self-review lessons. Integrate as service sidecar later. |
| Cognee | Defer | License/version to verify before import | Possible document/connector graph-RAG lane only if wiki packets plus Graphiti are not enough. |

References checked:

- Graphiti repo/docs: `https://github.com/getzep/graphiti`, `https://help.getzep.com/graphiti/getting-started/quick-start`
- Mem0 repo/PyPI/docs: `https://github.com/mem0ai/mem0`, `https://pypi.org/project/mem0ai/`, `https://docs.mem0.ai/open-source/python-quickstart`
- Hindsight repo/docs: `https://github.com/vectorize-io/hindsight`, `https://hindsight.vectorize.io/blog/2026/03/04/mcp-agent-memory`

## Installer Shape

Use three levels:

1. Core default: `telegram-starter`
   - No new heavy dependencies.
   - Must keep working on a normal machine.

2. Optional sidecar bundle/profile: `memory-sidecars`
   - Adds Graphiti sidecar module first.
   - Later adds Mem0 shadow and Hindsight procedural sidecar when ready.
   - Can be installed with a future command such as `spark setup memory-sidecars` or `spark setup telegram-starter --memory-sidecars graphiti`.

3. Development extras in `domain-chip-memory`
   - Add optional dependency groups, not required dependencies:
     - `graphiti-kuzu`
     - `graphiti-falkordb`
     - `mem0-shadow`
     - `memory-sidecars`
   - Builder should not import these packages directly. Builder should call `domain-chip-memory` sidecar contracts.

## Correct Ownership

Builder owns salience.

`domain-chip-memory` owns memory records and sidecar contracts.

Spark CLI owns installation, environment wiring, health visibility, and rollback switches.

Graphiti owns temporal graph indexing only after Spark has decided a record is worth exporting.

Mem0 owns shadow comparison only until it earns promotion through scorecards.

Hindsight-style memory owns procedural lessons, not user/profile facts.

## Immediate Build Plan

1. Builder salience gate
   - Add a deterministic policy module before durable writes.
   - Promotion bands: `drop`, `scratchpad`, `raw_episode`, `structured_evidence`, `current_state_candidate`, `current_state_confirmed`.
   - Store `salience_score`, `confidence`, `promotion_stage`, `why_saved`, `decay_after`, and `source_route`.

2. Domain optional extras
   - Add optional dependency groups in `domain-chip-memory`.
   - Keep default `dependencies = []` or equally light.
   - Add attribution/notice docs for Apache-2.0 and MIT dependencies.

3. Graphiti live adapter
   - Implement behind feature flag.
   - Prefer Kuzu first if local embedded behavior is stable enough; otherwise FalkorDB/Neo4j as a managed service dependency.
   - Export Spark evidence/entity events as episodes.
   - Return graph hits as supporting candidates with provenance and validity windows.

4. Spark CLI installer profile
   - Add a registry entry for the sidecar module or an optional memory bundle.
   - Add generated env for sidecar config under `.spark/state`.
   - Add `spark status` and `spark verify` visibility.
   - Add rollback switches to disable sidecar retrieval without disabling core memory.

5. Mem0 shadow comparator
   - Add after Graphiti live adapter is stable.
   - Run scorecards only; no authoritative answers from Mem0.

6. Hindsight procedural lane
   - Add as a separate service/adapter for repeated operational mistakes.
   - Feed wrong target builds, stale repo context, timeouts, failed tool calls, and bad self-review as experiences.

7. Episodic consolidation lane
   - Add session/day/project summary writers.
   - Preserve "what changed", "what was decided", "what remains open", "what Spark promised", "repos touched", and "artifacts created".
   - Feed summaries into the authority ledger, Graphiti episodes, and Obsidian/wiki packets.

8. Context reservoir and capsule v2
   - Keep a large searchable context reservoir with a 200k+ target budget for deep reconstruction.
   - Compile small answer packets by default.
   - Add an explicit deep-context mode for "what did we build today?", "recover this project", and "show the whole thread of work".

9. Repo and capability index
   - Index known local Spark repos and installed modules.
   - Track ownership boundaries, dirty state, active target, installer provenance, and capability state.
   - Require target confirmation before file-writing missions when repo evidence is ambiguous.

## Non-Negotiables

- Current state and entity current state stay authoritative for active facts.
- Sidecars cannot override current state.
- Every memory write must have a reason saved or reason rejected.
- Every memory answer must have a source explanation.
- Installer-managed sidecars must fail open: if Graphiti/Mem0/Hindsight is down, Spark falls back to core memory.
- Do not copy large OSS code into Spark unless dependency/service integration is impossible and license attribution is recorded.

## Next Commit Target

The next real implementation should happen in Builder first:

```text
spark-intelligence-builder
  -> memory/salience.py
  -> write_profile_fact_to_memory / entity-state write path
  -> tests for natural important fact, small talk rejection, correction supersession
```

Then wire optional sidecar dependencies in `domain-chip-memory` and `spark-cli`.
