# Spark Builder Memory/Wiki Feedback Request

Date: 2026-05-01
Repo: `domain-chip-memory`
Requester: `spark-intelligence-builder`

## Why This Request Exists

Builder is adding Spark self-awareness and LLM wiki cognition. It needs `domain-chip-memory` feedback before Builder hardens those routes, because memory must remain the authority for user/current-state/evidence truth while wiki remains supporting system/project knowledge.

This repo is currently ahead of `origin/main` with memory lifecycle, salience, episodic recall, and dashboard traceability work. That direction looks aligned with Builder's plan, but the contracts need to be made explicit.

## Builder's Current Model

Builder intends this authority order:

1. hot current user turn
2. current-state memory
3. historical memory for requested time windows
4. structured evidence/events
5. pending tasks and procedural lessons
6. LLM wiki as project/system support
7. graph sidecar hints as advisory/supporting
8. older conversation summaries and inferred beliefs

Wiki should help Spark understand systems, tools, routes, projects, and improvement doctrine. Wiki must not decide mutable user facts or live runtime health.

## What Builder Uses Today

Builder calls memory through SDK/bridge surfaces such as:

- current-state lookup
- historical-state lookup
- evidence retrieval
- event retrieval
- human memory inspection
- hybrid memory retrieval
- maintenance reports
- session/day/project summaries
- wiki packet retrieval through `retrieve_markdown_knowledge_packets`

`hybrid_memory_retrieve` is the main fusion point. It already includes current state, evidence, events, recent conversation, pending tasks, procedural lessons, graph sidecar hits, and wiki packets.

## What Builder Needs From This Repo

Please review and advise on these contract needs:

1. Wiki packet metadata
   - expose parsed frontmatter fields instead of making Builder infer from paths
   - include `authority`, `owner_system`, `type`, `status`, `freshness`, `wiki_family`, and source path

2. Memory KB family detection
   - distinguish current-state, evidence, event, synthesis, output, and raw snapshot pages
   - keep Memory KB pages marked as downstream of governed memory

3. Lifecycle export
   - expose stale-preserved, superseded, archived, deleted, resurrected, decay, replacement pointers, and deletion pointers in a stable shape

4. Sidecar status
   - expose Graphiti/Kuzu enabled/configured/disabled status
   - include validity windows, provenance episodes, and fallback/advisory status

5. Dashboard feeds
   - stabilize fields for salience decisions, promotion disposition, context packet source mix, selected/dropped recall items, graph hits, and wiki packet participation

6. Tests
   - current-state memory must outrank wiki for mutable facts
   - supporting-only context should warn before promotion
   - Graphiti remains additive until evals pass
   - wiki candidates cannot become verified memory without evidence

## Feedback Questions

1. Which fields should Builder depend on directly?
2. Which fields should remain internal to `domain-chip-memory`?
3. Should wiki packet family classification live here, in Builder, or both?
4. What shape should the memory dashboard export consume long term?
5. Which ahead-of-main commits are safe to push now?
6. What cross-repo acceptance tests should run before Builder relies on the new memory cognition fields?

## Current Validation

Focused validation from the coordinating terminal:

```text
python -m pytest tests/test_sdk.py tests/test_memory_sidecars.py
43 passed, 1 warning
```

The warning is Graphiti/Pydantic deprecation noise.

## Related Builder Docs

- `C:\Users\USER\AppData\Local\Temp\spark-builder-live-wiki-answer-clean-0fb48574\docs\SPARK_MEMORY_SYSTEM_FEEDBACK_PACKET_2026-05-01.md`
- `C:\Users\USER\AppData\Local\Temp\spark-builder-live-wiki-answer-clean-0fb48574\docs\SPARK_MEMORY_WIKI_COGNITION_INTEGRATION_2026-05-01.md`
- `C:\Users\USER\AppData\Local\Temp\spark-builder-live-wiki-answer-clean-0fb48574\docs\SPARK_SELF_AWARENESS_HARDENING_TASKS_2026-05-01.md`

