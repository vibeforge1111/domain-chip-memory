# Open Source Attribution Plan

Date: 2026-03-22
Status: active

## Purpose

This repo is allowed to learn from and selectively reuse open-source memory systems and benchmark tooling, but it must keep attribution explicit and license boundaries visible.

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
| `BEAM` paper (`arXiv:2510.27246`) | paper source only | Frontier benchmark tracking and architecture study | Do not imply a public code harness exists until code or dataset artifacts are pinned |
| `Salesforce/ConvoMem` | CC BY-NC 4.0 | Benchmark evaluation target | Treat as benchmark and research use unless a commercial-rights position is explicitly cleared |

## Policy

1. Prefer re-implementation of ideas over blind code copying.
2. If code is copied, record exact source path and license.
3. Keep benchmark data and benchmark-driven prompts isolated from training artifacts.
4. Never promote a doctrine based only on a vendor README claim.
