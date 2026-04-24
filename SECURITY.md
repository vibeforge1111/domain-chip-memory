# Security

`domain-chip-memory` is the default Spark memory/domain chip for launch. It is a local research and benchmark package, not a public network service.

## Launch Boundaries

- Does not own Telegram ingress.
- Does not own Spawner mission control.
- Does not need the Telegram bot token.
- May use provider keys only for explicit benchmark or evaluation runs.

## Secrets

Never commit:

- `.env`, `.env.*`
- provider API keys
- benchmark artifacts containing private user data
- generated local state or logs

Some tracked benchmark fixtures intentionally contain words such as `api_key`, `secret`, or `password` as test data. Treat those as fixtures, not live credentials, and keep real secrets out of fixture files.

## Verification

Run:

```bash
python -m pytest tests -q
```

Before publishing a package, inspect package contents and confirm no local `.env`, state, cache, or private benchmark artifact is included.
