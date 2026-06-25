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

<!-- SPARK FLEET STANDARD BLOCK v1 — canonical source: spark-compete/fleet/AGENT_GUIDE.md.
     This same block is mirrored into every repo's AGENTS.md and CLAUDE.md. Keep in sync. -->
## How agents work in this repo (Claude, Codex, Gemini — every LLM)

Many agents and sessions work these repos at the same time. There is a tiny **automatic**
workflow that keeps you from colliding. **There are no human-review steps — CI is the only
gate, and it is automatic.** This is coordination, not bureaucracy: claim, work, PR.

### Start of work — one command, then just work normally
```
python3 ~/spark-compete/scripts/fleet.py claim <this-repo-path> <area> <task>
```
You get your **own private worktree + branch + a lease** on `<area>`, so no other agent
edits the same files. It prints the folder to `cd` into. Work there and commit as usual —
a pre-commit hook **auto-checks and renews your lease**; you never manage it by hand.

- `fleet board` — see who's working on what, right now
- `fleet handoff <agent> --note "..."` — pass your work to another agent (with context)
- `fleet release --here` — done (frees the area + removes the worktree)

### Landing work — fully automatic, no human approval
1. Open a PR to the default branch.
2. **CI is the gate.** When it's green, the PR merges. No human reviews anything.
3. Never push directly to the protected branch; never commit from the shared checkout —
   always from your worktree.

### The rules (enforced by CI, not by people)
Full ruleset: **`spark-cli/docs/harness-discipline/`** — `01_RULESET.md` (7 Prime
Directives · Red Lines RL-01..21 · Rules R-01..28) and `07_FLEET_DISCIPLINE.md` (this
workflow). The day-to-day essentials:
- A real fix targets the **root cause**, not a symptom (R-05).
- No regex / keyword / canned answer **owns authority** — it is evidence only (RL-01).
- A failure **surfaces** with a clear reason; it never becomes a fake success (RL-08).
- One worktree per task; PRs only; nothing bypasses the CI gate (F-01 / F-09).

That's the whole contract. The system handles coordination and the gate for you —
automatically, with no human in the loop.
<!-- END SPARK FLEET STANDARD BLOCK v1 -->
