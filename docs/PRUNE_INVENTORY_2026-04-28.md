# Prune Inventory 2026-04-28

This is the first dependency-safe cleanup map for `domain-chip-memory`.

It does not delete anything yet. It tells us what to keep, freeze, archive, or inspect before deletion.

## Repo Shape

- Tracked docs: 96 files.
- Tracked artifacts: 2 files.
- Runtime source: `src/domain_chip_memory`.
- Runtime tests: `tests`.
- Research notes: `research`.
- Examples and smoke data: `docs/examples`.

The main clutter risk is not large binary artifacts. It is parallel strategy/history docs and old architecture loops competing with the current decision.

## Keep

Keep these as active project truth:

- `tasks.md`
- `README.md`
- `docs/OPEN_SOURCE_MEMORY_STACK_AND_PRUNE_PLAN_2026-04-28.md`
- `docs/MEMORY_SOTA_GAP_AUDIT_2026-04-27.md`
- `docs/SOTA_MEMORY_ARCHITECTURE_PROMOTION_2026-04-27.md`
- `docs/PERSISTENT_MEMORY_RUNTIME_BRIDGE_2026-04-27.md`
- `docs/CONVERSATIONAL_MEMORY_LAYER_PLAN_2026-04-22.md`
- `docs/TYPED_TEMPORAL_GRAPH_MEMORY_2026-04-22.md`
- `docs/BENCHMARK_SUBSTRATE_CONTRACTS.md`
- `docs/examples/**`
- `schemas/**`
- `templates/**`
- `research/research_grounded/**`

Keep these source/runtime areas:

- `src/domain_chip_memory/sdk.py`
- `src/domain_chip_memory/builder_read_adapter.py`
- `src/domain_chip_memory/spark_integration.py`
- `src/domain_chip_memory/memory_state_runtime.py`
- `src/domain_chip_memory/memory_state_queries.py`
- `src/domain_chip_memory/memory_evidence.py`
- `src/domain_chip_memory/memory_stateful_event_builder.py`
- `src/domain_chip_memory/typed_temporal_graph_memory.py`
- `src/domain_chip_memory/typed_temporal_graph_retrieval.py`
- `src/domain_chip_memory/memory_conversational_*`
- `src/domain_chip_memory/memory_summary_synthesis_builder.py`
- `src/domain_chip_memory/memory_dual_store_builder.py`
- `src/domain_chip_memory/memory_systems.py`
- `src/domain_chip_memory/runner.py`
- `src/domain_chip_memory/cli.py`

Keep all tests until the sidecar migration is green.

## Freeze

Freeze these unless they are needed for regression, provenance, or architecture history:

- `docs/ARCHITECTURE_VARIATION_LOOP_2026-03-29.md`
- `docs/COMBINATION_SEARCH_PROGRAM.md`
- `docs/NEXT_MEMORY_SYSTEM_PLAN_2026-03-28.md`
- `docs/UNIFIED_MEMORY_SYSTEM_PROGRAM_2026-03-25.md`
- `docs/MEMORY_ARCHITECTURE_EVOLUTION_PLAN_2026-03-25.md`
- `docs/MEMORY_VARIATION_MAP_AND_THREE_BUILDS_2026-03-23.md`
- `docs/PRODUCT_MEMORY_LOCAL_EVAL_2026-03-26.md`
- `docs/NEXT_PHASE_SPARK_MEMORY_KB_BENCHMARK_PROGRAM_2026-04-10.md`
- `docs/CURRENT_STATUS_BENCHMARKS_AND_KB_2026-04-09.md`

Freeze these code paths as challengers, not active runtime targets:

- `dual_store_event_calendar_hybrid`
- old BEAM-specific optimization paths
- local typed graph prototype behavior once the Graphiti-compatible sidecar contract exists

## Archive Candidates

Archive into a historical docs folder or summarize into a consolidated history doc after checking for unique evidence:

- old `SESSION_LOG_*`
- old `SESSION_HANDOFF_*`
- old `TODAY_PLAN_*`
- old `TOMORROW_START_CHECKLIST_*`
- older benchmark handoffs where `tasks.md` and the 2026-04-28 stack plan now supersede the action items

Do not archive if the file contains a unique command, artifact pointer, scorecard, or failed experiment that is not captured elsewhere.

## Deletion Candidates After Checks

Only delete after import/test/reference checks:

- scratch scripts that are not imported and not referenced by docs
- duplicate generated result files where a consolidated scorecard exists
- obsolete generated benchmark reports under untracked local artifact folders
- stale `__pycache__` directories if they are untracked
- old graph prototype files only after the sidecar adapter has equivalent tests

## First Safe Cleanup Batch

This is the first cleanup batch I would run once we are ready to delete:

1. Confirm untracked/generated clutter with `git status --short --ignored`.
2. Remove untracked `__pycache__` and `.pytest_cache` only.
3. Keep tracked docs untouched.
4. Commit the generated-cache cleanup.

## Second Cleanup Batch

After sidecar contract tests pass:

1. Move obsolete session/plan handoffs into `docs/archive/` or summarize them.
2. Keep only the newest active architecture docs at the top level.
3. Add an archive index so the evidence is still searchable.

## Third Cleanup Batch

After Graphiti-compatible sidecar shadow retrieval is passing:

1. Mark local typed graph prototype code as reference or remove replaced dead paths.
2. Keep tests that prove alias, temporal, negation, and provenance behavior.
3. Delete only code proven unused by import checks and tests.

## Checks Before Any Deletion

Run these before deleting tracked files:

```powershell
git status --short --branch
git grep "<candidate-name>"
python -m pytest tests/test_sdk.py tests/test_builder_read_adapter.py tests/test_typed_temporal_graph_memory.py tests/test_typed_temporal_graph_retrieval.py
```

For docs archive moves:

```powershell
git grep "<doc-name>"
```

If a doc is linked from `tasks.md`, `README.md`, or a current architecture decision, do not delete it.
