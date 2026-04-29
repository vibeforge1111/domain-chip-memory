# Memory And Dashboard Status - 2026-04-29

This is the current handoff point for Spark persistent memory and the standalone memory-quality dashboard.

## Architecture State

Spark is now on the hybrid memory path we selected:

- Builder remains the runtime authority for salience, promotion, current state, entity state, source order, and Telegram answer routing.
- `domain-chip-memory` owns benchmark surfaces, memory-system contracts, sidecar adapters, and Graphiti/Kuzu support.
- Graphiti is connected as an optional shadow sidecar, not as an authority that can override current state.
- `spark-memory-quality-dashboard` is the standalone operator UI for memory quality, traces, scorecards, salience lanes, and graph-sidecar visibility.

Authority order is unchanged:

1. explicit current state
2. entity-scoped current state
3. historical state for historical questions
4. recent conversation
5. retrieved evidence/events
6. Graphiti/typed-temporal sidecar
7. diagnostics/maintenance when relevant
8. workflow residue as advisory only

## What Is Connected

- Telegram memory writes now pass through salience gating for durable generic/project/entity facts.
- Entity current and previous recall works across practical workflow attributes: owner, location, status, deadline, relation, preference, project, blocker, priority, decision, next action, and metric.
- Graphiti/Kuzu direct structured upserts are available through `domain-chip-memory`.
- Builder hybrid retrieval exports entity-state records to the graph sidecar and reads graph hits as shadow/supporting evidence.
- The memory-quality dashboard exports from the real Builder state DB and shows:
  - recall events
  - memory lane counts
  - policy gates
  - context packet budget
  - memory read roles/methods
  - route/source trace map
  - source-explanation links
  - Graphiti shadow lane status/hits
  - domain-chip scorecards
  - salience lane audit samples

## Live State Snapshot

Latest dashboard export from the local Spark state DB:

- `event_log`: 15364 rows
- `memory_lane_records`: 4542 rows
- `policy_gate_records`: 31 rows
- `quarantine_records`: 0 rows
- `delivery_registry`: 0 rows
- Graph sidecar: `graphiti_temporal_graph`, authority `shadow_not_authoritative`
- Graph sidecar live lane events: 8
- Graph sidecar hits: 4
- Latest context packet: 4948 chars
- Source-aware trace ratio: 0.625
- Latest lane audit sample: 1 promoted, 15 blocked, 0 raw episodes, 16 policy blocks, 31.2% salience coverage

## Validation Status

Green:

- `spark-memory-quality-dashboard`: `npm run export:spark`
- `spark-memory-quality-dashboard`: `npm run typecheck`
- `spark-memory-quality-dashboard`: `npm test -- --run` -> 18 passed
- `spark-memory-quality-dashboard`: `npm run build`
- live dashboard DOM smoke at `http://127.0.0.1:5174/`
- `spark-intelligence-builder`: focused memory suite -> 251 passed
- `domain-chip-memory`: targeted regression pack for discovered candidate issues -> 9 passed
- `domain-chip-memory`: full suite -> 931 passed, 1 upstream Graphiti/Pydantic deprecation warning

## Last Fixes Before Unit-Test Expansion

The readiness pass found and fixed domain-chip benchmark regressions:

- Abstention answer candidates now stay `unknown` in observational and dual-store packets instead of leaking BEAM-style public abstention wording into product-memory/local lanes.
- Temporal/referential ambiguity source labels are preserved when the answer is `unknown`; the fix no longer collapses them into generic `abstention`.
- Summary-synthesis "when does" questions now prefer the focus-aligned date from source text before falling back to broader temporal reconstruction.
- LoCoMo scoreable yes/no tail candidates preserve the expected yes/no surface when the heuristic would otherwise flip a supported tail answer.

## Still Open

These are not blockers to start unit-test expansion, but they remain real architecture work:

- universal source labels for graph hits, raw episodes, older memory, inference, diagnostics, and workflow residue
- richer live Builder streams beyond exported local snapshots
- quarantine and delivery ledgers are still empty in the current local state
- episodic/day/project consolidation is not yet producing rich "what did we build today?" summaries
- pending-task recovery needs deeper timeout/mission continuity coverage
- one-command memory quality smoke still needs to exist in the operator path
- graph-sidecar acceptance probes need coverage for aliases, relationships, validity windows, provenance, and project dependencies

## Recommended Next Mode

Stop adding architecture for the moment. Move into unit-test expansion and acceptance-pack hardening:

1. Add focused tests for salience promotion/drop decisions.
2. Add dashboard export fixture tests for graph hits, salience coverage, empty quarantine/delivery, and source-aware trace gaps.
3. Add Builder tests for natural memory without `for later`.
4. Add Builder tests for source explanation labels on graph-sidecar and raw-episode answers.
5. Add end-to-end memory-quality smoke that runs export, focused Builder tests, focused domain-chip tests, and live dashboard DOM checks.
