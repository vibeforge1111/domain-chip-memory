# Spark KB Example Bundle

This directory is a checked-in Spark KB fixture for CLI smoke tests.

## Files

- `snapshot.json`: example exported Spark memory snapshot
- `sources/repo-notes.md`: example repo-native source file
- `outputs/location-answer.json`: example filed output payload
- `manifests/repo_sources.json`: manifest for repo-source ingest
- `manifests/filed_outputs.json`: manifest for filed-output ingest

## Smoke Flow

```powershell
python docs\examples\spark_kb\run_smoke.py
python -m domain_chip_memory.cli validate-spark-kb-inputs docs\examples\spark_kb\snapshot.json --repo-source-manifest docs\examples\spark_kb\manifests\repo_sources.json --filed-output-manifest docs\examples\spark_kb\manifests\filed_outputs.json
python -m domain_chip_memory.cli build-spark-kb docs\examples\spark_kb\snapshot.json tmp\spark_kb_example --repo-source-manifest docs\examples\spark_kb\manifests\repo_sources.json --filed-output-manifest docs\examples\spark_kb\manifests\filed_outputs.json
python -m domain_chip_memory.cli spark-kb-health-check tmp\spark_kb_example
```
