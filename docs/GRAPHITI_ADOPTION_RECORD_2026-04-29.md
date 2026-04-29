# Graphiti Adoption Record

Date: 2026-04-29
Status: optional sidecar adapter, disabled by default

## Source

- Name: Graphiti / Zep OSS core
- Source URL: https://github.com/getzep/graphiti
- Documentation: https://help.getzep.com/graphiti/getting-started/quick-start
- Package: `graphiti-core>=0.28.2`
- License: Apache-2.0
- Borrow mode: optional runtime dependency and sidecar adapter
- Local owner module: `domain_chip_memory.memory_sidecars`

## Install Surface

Graphiti is not a default dependency. The optional extras are:

- `domain-chip-memory[graphiti-kuzu]`
- `domain-chip-memory[graphiti-neo4j]`

The Kuzu path is the preferred local developer path because it can run embedded without a separate graph database. Neo4j is supported as a configured service path.

## Runtime Boundary

- Default enabled: no
- Feature flag: `spark.memory.sidecars.graphiti.enabled`
- Backend config: `spark.memory.sidecars.graphiti.backend`
- Local DB path config: `spark.memory.sidecars.graphiti.db_path`
- Authority: supporting, not authoritative
- Fallback: if Graphiti is missing, unconfigured, or unhealthy, Spark falls back to core current-state/entity-state/evidence/event memory.

Graphiti may contribute temporal graph hits, provenance, and validity windows. It must not override `current_state`, entity current state, or explicit user corrections.

## Telemetry

Spark-managed launches set best-effort telemetry-disable environment variables before creating the client:

- `GRAPHITI_TELEMETRY_ENABLED=false`
- `ZEP_TELEMETRY_DISABLED=true`

## Code Reuse

No Graphiti source code is vendored or copied in this repo. The adapter calls public package APIs for:

- episode ingest via `add_episode`
- graph search via `search`

## Tests

- Disabled/no-backend behavior stays contract-safe.
- Injected fake backend verifies live upsert, search hit mapping, provenance, validity, and non-authoritative status.
- Builder tests verify Graphiti lane telemetry remains shadow/additive.

## Known Risks

- Graphiti API details may shift across versions, so the adapter keeps imports optional and errors observable.
- Live graph hits require a separate promotion/evaluation pass before they can influence answers beyond supporting context.
- Kuzu/Neo4j operational setup belongs in installer work, not the default memory chip install.
