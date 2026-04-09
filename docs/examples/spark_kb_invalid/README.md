# Invalid Spark KB Example Bundle

This directory is a checked-in negative fixture for `validate-spark-kb-inputs`.

It is intentionally invalid:

- `snapshot.json` is not a JSON object
- `repo-sources.json` points to a missing repo source file
- `bad-output.json` is not a valid filed-output object or list
- `filed-outputs.json` uses the wrong manifest key
