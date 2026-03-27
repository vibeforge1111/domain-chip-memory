# Spark First Shadow Trace Handoff

This is the exact handoff for the first real Spark Intelligence Builder shadow trace export.

## Goal

Export the first real Builder shadow replay file in a shape this repo can validate and replay immediately.

## What Spark Should Export

Export one JSON file with this root shape:

- `conversations`
- optional `writable_roles`

Each conversation should include:

- `conversation_id`
- optional `session_id`
- optional `metadata`
- `turns`
- optional `probes`

Each turn should include:

- `message_id`
- `role`
- `content`
- optional `timestamp`
- optional `metadata`

Each probe should include:

- `probe_id`
- `probe_type`
- optional `subject`
- optional `predicate`
- optional `query`
- optional `as_of`
- optional `expected_value`
- optional `min_results`

Supported probe types right now:

- `current_state`
- `historical_state`
- `evidence`

## Minimum Export Standard

For the first batch, require:

- non-empty `conversation_id`
- non-empty `message_id`
- non-empty `role`
- non-empty `content`
- deterministic `timestamp` when available
- enough metadata to preserve provenance

If Spark knows the write scope, include it in turn metadata. For example:

- `memory_kind`
- entity hints
- predicate hints
- source tags

## What Spark Should Run First

Before sending the batch to replay, run:

```bash
python -m domain_chip_memory.cli validate-spark-shadow-replay <file>
```

The file is ready for replay only if:

- `valid` is `true`
- `errors` is empty

Warnings are allowed, but they should be reviewed.

## What We Will Run Here

After validation, replay with:

```bash
python -m domain_chip_memory.cli run-spark-shadow-report <file> --write <report.json>
```

For a directory of files:

```bash
python -m domain_chip_memory.cli validate-spark-shadow-replay-batch <dir>
```

```bash
python -m domain_chip_memory.cli run-spark-shadow-report-batch <dir> --write <report.json>
```

## What We Need From The First Batch

The first batch does not need to be large. It needs to be useful.

Target:

- 5 to 20 conversations
- at least a few accepted writes
- at least a few rejected or skipped cases
- at least one current-state probe
- at least one evidence probe
- preferably one historical-state probe

This is enough to tell whether Builder is exporting trace data in a way the SDK can use.

## Exact Message To Send

Use this message:

```text
Please export the first Spark shadow replay JSON batch for the memory SDK integration.

Use the replay shape documented in:
- docs/SPARK_SHADOW_REPLAY_EXAMPLES_2026-03-27.md
- docs/examples/spark_shadow/single_replay.json

Before handing the file back, run:
python -m domain_chip_memory.cli validate-spark-shadow-replay <file>

The batch should only be sent forward if:
- valid=true
- errors=[]

For the first pass, a small but representative batch is enough:
- 5 to 20 conversations
- real Builder turns
- non-empty conversation_id, message_id, role, and content
- timestamps when available
- current_state, evidence, and ideally historical_state probes

Once exported, we will run:
- python -m domain_chip_memory.cli run-spark-shadow-report <file> --write <report.json>

This batch is for shadow evaluation only, not live promotion.
```

## Why This Matters

If the first exported batch is malformed, we lose time debugging file shape instead of memory behavior.

The validator is now the boundary:

- Spark proves the file is structurally valid
- this repo proves whether the memory behavior is good
