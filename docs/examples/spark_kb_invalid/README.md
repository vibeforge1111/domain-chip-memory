# Invalid Spark KB Example Bundle

This directory is a checked-in negative fixture for `validate-spark-kb-inputs`.

It is intentionally invalid:

- `snapshot.json` is not a JSON object
- `repo-sources.json` points to a missing repo source file
- `bad-output.json` is not a valid filed-output object or list
- `filed-outputs.json` uses the wrong manifest key

## Failure Flow

```powershell
python docs\examples\spark_kb_invalid\run_validate_failure.py
python -m domain_chip_memory.cli validate-spark-kb-inputs docs\examples\spark_kb_invalid\snapshot.json --repo-source-manifest docs\examples\spark_kb_invalid\repo-sources.json --filed-output-file docs\examples\spark_kb_invalid\bad-output.json --filed-output-manifest docs\examples\spark_kb_invalid\filed-outputs.json
```
