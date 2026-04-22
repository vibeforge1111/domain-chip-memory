# Example Fixtures

This directory holds checked-in fixtures for CLI smoke tests and contract validation.

## Top-Level Smoke Runner

```powershell
python docs\examples\run_smokes.py
```

This aggregate runner is also what the GitHub Actions workflow executes.

## Spark KB

- `spark_kb/`: valid Spark KB example bundle with validate, build, and health-check smoke paths plus `run_smoke.py`
- `spark_kb_invalid/`: intentionally invalid Spark KB bundle for validator failure coverage plus `run_validate_failure.py`

## Spark Shadow

- `spark_shadow/single_replay.json`: single replay example
- `spark_shadow/batch_replay/`: batch replay examples
- `spark_shadow/telegram_multi_party_probe_pack.json`: Telegram-style multi-party conversational probe pack

## SDK Maintenance

- `sdk_maintenance/single_replay.json`: SDK maintenance replay example
