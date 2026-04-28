# Pre-Implementation Docs And License Checklist

Date: 2026-04-28
Status: active gate before memory sidecar/code integration

## Why This Exists

Spark is about to connect richer persistent-memory layers: salience gates, Graphiti, Mem0 shadowing, procedural memory, episodic summaries, and installer profiles.

Before that work becomes code, the documentation needs to make four boundaries explicit:

1. What Spark owns.
2. What is borrowed as architecture inspiration.
3. What is used as a dependency or sidecar.
4. What is copied or vendored from another repository.

Those four modes have different license, attribution, testing, and rollback requirements.

## Current Documentation Surface

Use these as the active build trail:

- `tasks.md`: current architecture decision, build phases, acceptance gates, and next work.
- `docs/SPARK_MEMORY_CONNECTION_PLAN_2026-04-28.md`: system connection plan for Builder, SDK, capsule, Graphiti, procedural memory, and retrieval.
- `docs/SPARK_MEMORY_SYSTEM_INSPECTION_AND_INSTALLER_PLAN_2026-04-28.md`: installer and repo inspection plan.
- `docs/MEMORY_LANES_AND_QUALITY_GATES_2026-04-28.md`: human-readable memory lanes and quality gates.
- `docs/OSS_MEMORY_BORROWING_PLAN_2026-04-28.md`: OSS stack decision and borrowing policy.
- `docs/OPEN_SOURCE_ATTRIBUTION_PLAN.md`: source registry and attribution policy.
- `THIRD_PARTY_NOTICES.md`: top-level third-party notice surface.

## Current License Status

- Project license file: missing.
- `pyproject.toml` license metadata: missing.
- Top-level third-party notice file: present as a scaffold.
- Runtime dependencies declared in `pyproject.toml`: none.
- New vendored OSS source from the current memory-sidecar plan: none recorded.

This means the repo should not claim to be open-source licensed until the owner chooses and adds a `LICENSE` file. The README now reflects that.

## Required Decision Before Runtime Integration

The repo owner should choose the project license before we add or publish integration code.

Recommended choices to consider:

- Apache-2.0 if patent grant, compatibility with Apache-licensed memory dependencies, and explicit notice handling matter most.
- MIT if maximum simplicity matters most and the repo does not need Apache's patent language.
- Private/unlicensed for now if this is not meant to grant external reuse rights yet.

Do not infer this choice from the licenses of Graphiti, Mem0, Hindsight, or benchmark repos. Dependency licenses do not automatically license this project.

## Borrowing Modes

Use exact language in docs and code comments:

- Inspired by: no code copied; architecture or scoring idea only.
- Adapter for: Spark-owned code that calls an external system through its API or package.
- Runtime dependency on: package is installed and imported at runtime.
- Sidecar service: external process/service used through API, MCP, socket, or local database.
- Vendored from: source files copied into this repo.
- Benchmark-only: dataset or harness used only for evaluation, not product runtime.

## Adoption Record Template

Every new dependency, sidecar, benchmark, or copied source file needs this record before merge:

```text
Name:
Source URL:
License:
Upstream version/tag/commit:
Borrow mode:
Local owner module:
Install surface:
Default enabled:
Feature flag:
State path:
Telemetry:
Fallback if unavailable:
Code copied:
Headers/SPDX preserved:
NOTICE update:
Tests:
Reason:
Known risks:
```

## Dependency Gates

- [ ] A project `LICENSE` file exists, or README clearly says license is pending/private.
- [ ] `pyproject.toml` license metadata matches the chosen project license.
- [ ] `THIRD_PARTY_NOTICES.md` has an entry before dependency or source-copy merge.
- [ ] Runtime dependencies are optional extras unless they are required for the core chip.
- [ ] Default install remains light: no graph database, hosted memory service, or telemetry-enabled sidecar by default.
- [ ] Graphiti, Mem0, and Hindsight start behind feature flags or installer profiles.
- [ ] Spark degrades to current-state/evidence memory when a sidecar is unavailable.
- [ ] Windows install path and local state path are documented before installer wiring.
- [ ] Telemetry is disabled by default for Spark-managed local launches.
- [ ] Copyleft runtime dependencies require explicit owner approval.
- [ ] Non-commercial or share-alike benchmark datasets stay benchmark-only unless cleared.

## Copying Code Gates

- [ ] Exact upstream file path and commit are recorded.
- [ ] License and file-level headers are preserved.
- [ ] SPDX/header text remains intact if present.
- [ ] Local modifications are marked.
- [ ] Tests prove the copied code satisfies Spark's contract.
- [ ] Copied code is small enough to maintain locally.
- [ ] Prefer dependency/adapter integration if the copied surface would grow.

## Planned Candidate Status

| Candidate | Current status | License posture | Spark use |
| --- | --- | --- | --- |
| Graphiti / Zep OSS core | planned, not default dependency | Apache-2.0; telemetry must be disabled in local managed launches | temporal graph sidecar |
| Mem0 OSS | planned shadow comparator, not authority | Apache-2.0 | extraction/retrieval baseline |
| Hindsight | planned procedural memory sidecar/prototype | MIT | correction/failure/timeout experience memory |
| Generative Agents | inspiration only | Apache-2.0 | salience shape: recency, importance, relevance, reflection |
| MemMachine | architecture/reference candidate | Apache-2.0 | working/profile/episodic layer comparison |
| Cognee | deferred | verify before adoption | document/connector graph-RAG if needed later |

## Documentation To Update With Code

When implementation starts, update these docs in the same commit or a nearby follow-up:

- `tasks.md`: checklist status and acceptance gate changes.
- `docs/OPEN_SOURCE_ATTRIBUTION_PLAN.md`: source registry and current implementation status.
- `docs/OSS_MEMORY_BORROWING_PLAN_2026-04-28.md`: dependency/adoption record.
- `THIRD_PARTY_NOTICES.md`: package, sidecar, or vendored-code notice.
- README: user-facing install, security, and license status if it changes.

## Ready-To-Build Verdict

Architecture docs are ready enough to start coding, but two license gates should be handled deliberately:

1. Choose the project license or keep the repo explicitly license-pending.
2. Add an adoption record before adding any Graphiti, Mem0, Hindsight, Cognee, or copied OSS code.

Until then, it is safe to implement Spark-owned salience gates, memory lanes, quality-gate ledgers, source-aware recall, and capsule logic without external code imports.
