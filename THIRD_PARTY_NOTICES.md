# Third-Party Notices

Status: active

This repository currently has no default runtime dependencies in `pyproject.toml` and no recorded vendored third-party source code.

Default install:

- No external memory-system package is installed by default.
- No benchmark dataset is vendored in this repository.
- No third-party source files from Graphiti, Mem0, Hindsight, Cognee, LongMemEval, LoCoMo, or related systems are copied into the product runtime.

Optional install surface:

| Source | Local surface | License status | Default enabled | Notes |
|---|---|---|---|---|
| Graphiti / Zep OSS core | `domain-chip-memory[graphiti-kuzu]`, `domain-chip-memory[graphiti-neo4j]` | Apache-2.0 | No | Optional temporal graph sidecar adapter. Spark-owned code calls public package APIs; no Graphiti source is vendored. |

Research, benchmark, and inspiration surfaces:

| Source | License recorded | Current Spark use | Shipping boundary |
|---|---|---|---|
| Mem0 OSS | Apache-2.0 | Planned shadow comparator / extraction-retrieval baseline | Not installed by default; no source copied. |
| Hindsight | MIT | Planned procedural/experience memory sidecar or adapter | Not installed by default; no source copied. |
| Generative Agents | Apache-2.0 | Salience/reflection pattern inspiration | Pattern inspiration only. |
| Cognee | Deferred; re-verify before adoption | Possible document/connector graph-RAG lane | Not adopted. Do not ship until license/runtime surface is re-verified. |
| LongMemEval | MIT | Benchmark adapter and evaluation structure | Dataset is not vendored; keep benchmark use separate from product runtime. |
| LoCoMo | CC BY-NC 4.0 | Benchmark adapter and evaluation structure | Non-commercial benchmark/data lane only unless legal approval changes the boundary. |

Adoption records:

- `docs/GRAPHITI_ADOPTION_RECORD_2026-04-29.md`: Graphiti / Zep OSS core, Apache-2.0, optional disabled-by-default temporal graph sidecar adapter.
- `docs/OPEN_SOURCE_ATTRIBUTION_PLAN.md`: broader registry for memory-system inspiration, benchmark-only sources, and future adoption boundaries.

Before adding an external memory system, benchmark harness, copied source file, or service sidecar, update this file or a linked adoption record with:

- Source name and repository URL
- License and upstream copyright notice
- Upstream release, tag, or commit
- Local package/module that uses it
- Borrow mode: inspiration, runtime dependency, sidecar service, benchmark-only artifact, or vendored code
- Whether source code was copied
- Whether NOTICE, SPDX, or file headers were preserved
- Runtime feature flag and fallback path
- Telemetry setting, if any

Planned memory-system candidates are not shipped default dependencies until they are added to package metadata, installer profiles, or vendored source paths. The current planned candidates include:

- Graphiti / Zep OSS core: Apache-2.0, optional temporal graph sidecar via `domain-chip-memory[graphiti-kuzu]` or `domain-chip-memory[graphiti-neo4j]`, disabled by default.
- Mem0 OSS: Apache-2.0, planned shadow comparator or extraction/retrieval baseline.
- Hindsight: MIT, planned procedural/experience memory sidecar or adapter.
- Generative Agents: Apache-2.0, salience and reflection pattern inspiration.
- Cognee: deferred; license and runtime shape must be re-verified before adoption.

Do not add GPL/AGPL/copyleft runtime dependencies or non-commercial datasets to product runtime without explicit owner approval.
