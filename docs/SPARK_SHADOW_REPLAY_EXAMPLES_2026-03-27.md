# Spark Shadow Replay Examples

This page pins the first checked-in examples for the Spark shadow replay flow.

Use these when Spark Intelligence Builder needs a known-good file shape for:

- `python -m domain_chip_memory.cli spark-shadow-contracts`
- `python -m domain_chip_memory.cli run-spark-shadow-report <file>`
- `python -m domain_chip_memory.cli run-spark-shadow-report-batch <dir>`

## Example Files

- Single-file replay:
  - `docs/examples/spark_shadow/single_replay.json`
- Batch replay directory:
  - `docs/examples/spark_shadow/batch_replay/`

## Single-File Shape

The root object contains:

- `writable_roles`
- `conversations`

Each conversation can contain:

- `conversation_id`
- `session_id`
- `metadata`
- `turns`
- `probes`

Each turn can contain:

- `message_id`
- `role`
- `content`
- `timestamp`
- `metadata`

Each probe can contain:

- `probe_id`
- `probe_type`
- `subject`
- `predicate`
- `query`
- `as_of`
- `expected_value`
- `min_results`

Supported probe types right now:

- `current_state`
- `historical_state`
- `evidence`

## Example Commands

```bash
python -m domain_chip_memory.cli run-spark-shadow-report docs/examples/spark_shadow/single_replay.json
```

```bash
python -m domain_chip_memory.cli run-spark-shadow-report-batch docs/examples/spark_shadow/batch_replay --write artifacts/spark_shadow_batch_report.json
```

## Notes

- These files are intentionally small and deterministic.
- They are meant to be copied by Spark-side tooling as seed schemas, not treated as production traffic.
- The checked-in CLI tests exercise these examples so the docs stay runnable.
