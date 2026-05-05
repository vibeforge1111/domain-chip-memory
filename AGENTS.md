# Spark Memory Chip Agent Guide

This repo should not invent memory doctrine in isolation. For non-trivial changes to memory lanes, salience, promotion, decay, recall, summarization, benchmarks, or dashboard traceability, do a short research pass before implementation.

## Research Before Building

- Check current strong implementations and papers first. Start with Mem0, Letta/MemGPT, Engram, Cortex, LangGraph/LangMem patterns, recent agent-memory papers, and memory benchmark repos.
- Record the research influence in the PR, commit notes, design doc, benchmark notes, or tests: what was borrowed, what was rejected, and why Spark's architecture differs.
- Prefer primary sources: official docs, GitHub repos, papers, and benchmark repos. Use blog posts only as supporting context.
- Do not cargo-cult. External patterns must pass Spark's boundaries: typed memory lanes, source-aware recall, provenance, salience/promotion/decay, traceability, and anti-residue discipline.
- If network research is unavailable, say that explicitly and continue from local docs and cached knowledge.

## Karpathy Bar

Use Karpathy-style engineering as the taste filter:

- Make the core algorithm small enough to read.
- Keep a simple reference path beside any optimized path.
- Use names that teach the mechanism.
- Prefer end-to-end tests and tiny fixtures over abstract promises.
- Avoid accidental complexity, hidden magic, and premature generalization.
- Make failures inspectable.

## Memory Doctrine

- Separate episodic, semantic/current-state, procedural, and working/session memory.
- Raw turns are episodic evidence, not durable truth.
- Promotion requires salience, transfer value, source, scope, and a reason to survive decay.
- Decay should be explicit and traceable, not silent deletion.
- Recall should explain why an item was selected, which source it came from, and whether it is authoritative or supporting.
- Dashboards should show movement: captured, blocked, promoted, saved, decayed, summarized, and retrieved.

## External Inspiration Watchlist

- Mem0: https://github.com/mem0ai/mem0
- Letta/MemGPT: https://github.com/letta-ai/letta
- Engram: https://engram.to/
- Cortex: https://github.com/prem-research/cortex
- Karpathy llm.c: https://github.com/karpathy/llm.c
- Karpathy nanoGPT: https://github.com/karpathy/nanoGPT
- Karpathy micrograd: https://github.com/karpathy/micrograd

Refresh this list as better SOTA examples appear.
