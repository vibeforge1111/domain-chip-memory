# domain-chip-memory Domain Intelligence

> Quality: scaffolded | Doctrines: 0 | Evidence files: 2
> Last updated: 2026-03-22T13:30:00Z

## Domain Identity

**Domain**: agent-memory
**Version**: 0.1.0

This chip provides domain-specific intelligence for the **agent-memory** domain,
following the `spark-chip.v1` contract with four hooks: `evaluate`, `suggest`,
`packets`, and `watchtower`.

## Core Doctrines

Doctrines are not promoted yet.

The current repo only establishes:

- the benchmark stack to beat
- the research loop to use
- the attribution policy to follow

## Frontier Exploration

Allowed mutations:

- ingestion_strategy
- memory_schema
- retrieval_policy
- temporal_reasoning_policy
- answer_ensemble
- evaluation_policy

Open questions:

- Can a temporal-first memory graph beat current public LongMemEval numbers without benchmark leakage?
- Where does full-context prompting still beat explicit memory on ConvoMem-length histories?
- Which mutations improve `knowledge-update` and `temporal-reasoning` without hurting abstention?

