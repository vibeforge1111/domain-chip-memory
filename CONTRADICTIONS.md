# Memory Chip Contradictions

Date: 2026-03-22
Status: open

## Known contradictions to resolve

1. Public Supermemory evidence is internally inconsistent.
   The official indexed research page exposes `81.6%` with `gpt-4o` and `85.2%` with `gemini-3-pro` on `LongMemEval_s`, while the user-shared April teaser claims an experimental `~99%` flow. Treat `~99%` as unpinned until the source code and article are fully public and reproducible.

2. LoCoMo is a strong benchmark, but its public code and data are under `CC BY-NC 4.0`.
   That makes it useful for research benchmarking and architecture study, but unsafe to treat as a drop-in commercial training asset.

3. ConvoMem argues that full context remains strong for the first 30 to 150 conversations.
   A memory system that only beats weak RAG baselines but loses to direct long-context prompting in that range is not actually winning the product trade.

4. MemoryBench is useful for normalized comparisons, but it is still a framework, not the benchmark ground truth itself.
   Final claims should still be tied back to the canonical benchmark datasets and official scoring methods.

