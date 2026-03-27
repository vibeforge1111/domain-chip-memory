# SDK Maintenance Replay Examples

This page pins the first checked-in examples for the SDK maintenance replay flow.

Use these when Spark Intelligence Builder or adjacent tooling needs a known-good file shape for:

- `python -m domain_chip_memory.cli sdk-maintenance-contracts`
- `python -m domain_chip_memory.cli run-sdk-maintenance-report <file>`

## Example Files

- Single-file replay:
  - `docs/examples/sdk_maintenance/single_replay.json`

## Single-File Shape

The root object contains:

- `writes`
- `checks`

Each write can contain:

- `write_kind`
- `text`
- `speaker`
- `timestamp`
- `session_id`
- `turn_id`
- `operation`
- `subject`
- `predicate`
- `value`
- `metadata`

The optional `checks` object can contain:

- `current_state`
- `historical_state`

Each `current_state` check can contain:

- `subject`
- `predicate`

Each `historical_state` check can contain:

- `subject`
- `predicate`
- `as_of`

Supported write kinds right now:

- `observation`
- `event`

Supported observation operations right now:

- `auto`
- `create`
- `update`
- `delete`

Supported event operations right now:

- `auto`
- `event`

## Example Command

```bash
python -m domain_chip_memory.cli run-sdk-maintenance-report docs/examples/sdk_maintenance/single_replay.json --write artifacts/sdk_maintenance_report.json
```

## Notes

- These files model explicit SDK writes, not Builder conversation turns.
- The replay evaluates checks before and after `reconsolidate_manual_memory()` so maintenance behavior stays visible.
- The checked-in CLI tests exercise this example so the docs stay runnable.
