# Open Source Attribution Plan

Date: 2026-03-22
Status: active

## Purpose

This repo is allowed to learn from and selectively reuse open-source memory systems and benchmark tooling, but it must keep attribution explicit and license boundaries visible.

## Current implementation status

- No Graphiti, Mem0, Hindsight, Cognee, MemMachine, or Generative Agents runtime dependency is currently declared in `pyproject.toml`.
- No vendored source code from those systems is recorded in this repo for the current Spark memory-sidecar plan.
- Current use is architecture study, benchmarking study, adapter planning, and attribution planning unless a later adoption record says otherwise.
- `THIRD_PARTY_NOTICES.md` is the top-level notice surface for future dependency, sidecar, benchmark, or vendored-code adoption.

Use exact distinction language:

- `inspired by` means no code copied.
- `adapter for` means Spark-owned integration code calls another package or service.
- `runtime dependency on` means the package is installed and imported in Spark code.
- `sidecar service` means an external process or database is managed beside Spark.
- `vendored from` means source code was copied and needs file-level attribution.
- `benchmark-only` means the code or data is not part of product runtime.

## Source registry

| Source | License | Planned use | Boundary |
|---|---|---|---|
| `supermemoryai/memorybench` | MIT | Benchmark harness patterns, normalized benchmark adapters, compare workflow ideas | Reuse is allowed with attribution; keep our evaluation claims separate from their leaderboard |
| `supermemoryai/supermemory` | MIT | Architecture inspiration for memory atoms, versioning, temporal grounding, hybrid search | Do not copy benchmark claims without exact reproduction |
| `xiaowu0162/LongMemEval` | MIT | Official benchmark structure and scoring flow | Do not leak benchmark answers into training or prompt templates |
| `mem0ai/mem0` | Apache 2.0 | Memory-layer architecture ideas and extraction patterns | Preserve notices if code is reused directly |
| `WujiangXu/A-mem` | MIT | Agentic memory organization ideas and LoCoMo-facing experiment structure | Treat as inspiration unless a direct code import is intentional and attributed |
| `snap-research/locomo` | CC BY-NC 4.0 | Research benchmarking and structure study | Do not assume commercial reuse rights; keep it benchmark-only unless legal stance is clarified |
| `GoodAI/goodai-ltm-benchmark` | MIT | Official benchmark harness, published configuration ideas, and internal long-span stress evaluation | Keep our score claims configuration-specific because the benchmark is a living harness |
| `mastra-ai/mastra` | Apache 2.0 core + enterprise-licensed `ee/` paths | Framework and observational-memory implementation study | Reuse only from the Apache-covered core paths unless enterprise-licensed code is explicitly excluded |
| `Chronos` paper (`arXiv:2603.16862`) | paper source only | Temporal-memory architecture study | Do not imply code reuse or exact reproducibility until public code exists |
| `Supermemory ASMR` forthcoming release | pending public release | Agentic retrieval and benchmark-frontier study | Do not imply code reuse or pinned benchmark reproducibility until the release and exact implementation surface are public |
| `mohammadtavakoli78/BEAM` plus `Mohammadta/BEAM` and `Mohammadta/BEAM-10M` | MIT code plus CC BY-SA 4.0 datasets | Official BEAM benchmark reproduction, architecture study, and score comparison | Keep code and dataset attribution explicit, and do not imply reproduction unless repo commit, dataset path, and eval flow are pinned |
| `Salesforce/ConvoMem` | CC BY-NC 4.0 | Benchmark evaluation target | Treat as benchmark and research use unless a commercial-rights position is explicitly cleared |
| `getzep/graphiti` | Apache-2.0 | Temporal graph sidecar dependency/adapter for entities, relationships, validity windows, and episode provenance | Preserve license/notice requirements; disable optional telemetry by default in Spark-managed local launches |
| `vectorize-io/hindsight` | MIT | Experience/procedural memory lane for corrections, failed tool calls, and repeated operational mistakes | Treat as shadow/adapter first; do not let procedural lessons override typed current state without source explanation |
| `MemMachine/MemMachine` | Apache-2.0 | Multi-layer working/profile/episodic memory architecture study and possible adapter | Borrow layer design first; direct runtime import needs dependency/operations review |
| `letta-ai/letta` / MemGPT lineage | license to verify per imported component | Memory hierarchy, context rebuilding, and explicit memory-operation design study | Verify exact component license before any code copy; use patterns first |

## Policy

1. Prefer re-implementation of ideas over blind code copying.
2. If code is copied, record exact source path and license.
3. Keep benchmark data and benchmark-driven prompts isolated from training artifacts.
4. Never promote a doctrine based only on a vendor README claim.
5. Prefer dependency/adapter integration over vendoring source.
6. When vendoring source, preserve SPDX/header/NOTICE text and record upstream commit.
7. Do not add Graphiti, Mem0, Hindsight, Cognee, or similar systems to default install without a dependency adoption record.
8. Keep optional telemetry disabled by default in Spark-managed local launches.
9. Do not add GPL/AGPL/copyleft runtime dependencies or non-commercial datasets to product runtime without explicit owner approval.

## Dependency adoption record template

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
