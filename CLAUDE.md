# Domain Chip Memory Codex Rules

## Live Telegram Safety

`domain-chip-memory` must not take down the live `@SparkAGI_bot` while memory tests or runtime improvements are in progress.

Operational rule:

- one bot token
- one active receiver
- all memory tooling stays behind that receiver

Canonical Telegram owner:

- repo: `spark-telegram-bot`
- inspect the supported gateway status/config output before any Telegram-adjacent test
- do not assume webhook or polling mode from stale docs; verify the current launch posture

Before running any Telegram-adjacent memory test or integration:

1. inspect the gateway status/config output without copying secret values
2. confirm only one `spark-telegram-bot` process is running
3. confirm Telegram ownership through the supported bot healthcheck
4. if webhook is active, do not start polling
5. if polling is active, do not start any second receiver

Never:

- start the old Builder Telegram poller for `@SparkAGI_bot`
- start another Telegraf or Telegram receiver with the same token
- delete or replace the live webhook unless explicitly doing coordinated gateway recovery
- re-enable webhook mode, tunnel work, or alternate ingress ownership unless explicitly coordinated
- point Spawner directly at Telegram instead of the canonical gateway owner

Testing rule:

- real Telegram testing must go through the canonical `spark-telegram-bot` owner
- Builder and memory improvements must stay downstream of that receiver
- if unsure about live ingress ownership, stop and inspect before running anything
