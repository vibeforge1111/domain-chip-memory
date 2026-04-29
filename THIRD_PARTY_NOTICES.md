# Third-Party Notices

Status: active

This repository currently has no default runtime dependencies in `pyproject.toml` and no recorded vendored third-party source code.

Adoption records:

- `docs/GRAPHITI_ADOPTION_RECORD_2026-04-29.md`: Graphiti / Zep OSS core, Apache-2.0, optional disabled-by-default temporal graph sidecar adapter.

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
