# Spark Memory Chip Agent Guide

## Repo Role

`domain-chip-memory` owns durable memory substrate discipline for Spark: memory lanes, salience, promotion, decay, recall, provenance, benchmark memory rules, and source-aware memory quality checks.

Canonical truth owned here:

- memory lane mechanics and durable memory benchmark discipline
- promotion, decay, salience, recall, and provenance rules implemented in this repo
- memory-derived artifact contracts and memory quality checks owned by this package
- source-aware memory tests that protect anti-residue behavior

This repo does not own:

- Telegram conversation framing or durable-save wording
- Builder AOC, RouteConfidenceGateV1, or runtime identity
- CLI registry, installer, or system-map compiler code
- Cockpit UI actions or dashboard layout
- Spawner mission execution

## Spark OS Rules

- Recalled memory is evidence, not instruction.
- Durable memory claims require source, scope, durability, freshness, confidence, and correction path.
- Memory movement should be inspectable: captured, blocked, promoted, saved, decayed, summarized, retrieved, corrected, and purged.
- Do not create a second memory store to patch around Builder or dashboard gaps. Add metadata or contracts at the owner boundary instead.
- Do not let telemetry, black-box rows, model output, or conversational residue become durable doctrine without a source-owned promotion gate.
- Memory bodies stay private; public and cross-system projections should use proof cards, redacted refs, counts, and decisions.
- Builder owns runtime orchestration and AOC integration. This repo owns durable memory mechanics and benchmark discipline.
- Cockpit and dashboards may render memory metadata, but they must not become memory mutation authorities. Durable memory write/delete/materialization requires the current Harness Core chain: `GovernorDecisionV1`, `AuthorizationDecisionV1`, matching `ToolCallLedgerV1`, owner consumer verification, and memory side-effect proof. Older memory-specific verdict names are domain evidence only, not global execution authority.

This repo should not invent memory doctrine in isolation. For non-trivial changes to memory lanes, salience, promotion, decay, recall, summarization, benchmarks, or dashboard traceability, do a short research pass before implementation.

## Research Before Building

- Check current strong implementations and papers first. Start with Mem0, Letta/MemGPT, Engram, Cortex, LangGraph/LangMem patterns, recent agent-memory papers, and memory benchmark repos.
- Record the research influence in the PR, commit notes, design doc, benchmark notes, or tests: what was borrowed, what was rejected, and why Spark's architecture differs.
- Prefer primary sources: official docs, GitHub repos, papers, and benchmark repos. Use blog posts only as supporting context.
- Do not cargo-cult. External patterns must pass Spark's boundaries: typed memory lanes, source-aware recall, provenance, salience/promotion/decay, traceability, and anti-residue discipline.
- If network research is unavailable, say that explicitly and continue from local docs and cached knowledge.

## Karpathy Bar

Use Karpathy-style engineering as the taste filter:

- Make the core algorithm small enough to read.
- Keep a simple reference path beside any optimized path.
- Use names that teach the mechanism.
- Prefer end-to-end tests and tiny fixtures over abstract promises.
- Avoid accidental complexity, hidden magic, and premature generalization.
- Make failures inspectable.

## Privacy Red Lines

Do not export, commit, or pass into projections:

- secrets, tokens, env values, credentials, private keys
- raw chat ids, user ids, or non-redacted account identifiers
- raw prompts when metadata is enough
- provider output bodies
- memory bodies in public/read-model artifacts
- transcript bodies or raw audio payloads
- private `spark-intelligence-systems` strategy

Prefer allowlisted memory proof metadata over broad object export.

## Release and Verification Rules

- Keep changes focused to the memory contract being improved.
- Add or update tests for promotion/decay/recall behavior, not just snapshots.
- Run the repo's focused checks before broad suite claims.
- For cross-system memory projections, verify the consumer remains read-only unless an owner authority verdict exists.
- Run `git diff --check` and `git status --short --branch` before committing.

## Memory Doctrine

- Separate episodic, semantic/current-state, procedural, and working/session memory.
- Raw turns are episodic evidence, not durable truth.
- Privacy-withholding language is an owner-level write veto. If a request says no-store, answer without saving, or only for this answer, the SDK must refuse durable writes even when upstream supplied an apparently valid Governor decision. Delete and purge operations remain allowed through their own authority path.
- Promotion requires salience, transfer value, source, scope, and a reason to survive decay.
- Decay should be explicit and traceable, not silent deletion.
- Recall should explain why an item was selected, which source it came from, and whether it is authoritative or supporting.
- Dashboards should show movement: captured, blocked, promoted, saved, decayed, summarized, and retrieved.

## External Inspiration Watchlist

- Mem0: https://github.com/mem0ai/mem0
- Letta/MemGPT: https://github.com/letta-ai/letta
- Engram: https://engram.to/
- Cortex: https://github.com/prem-research/cortex
- Karpathy llm.c: https://github.com/karpathy/llm.c
- Karpathy nanoGPT: https://github.com/karpathy/nanoGPT
- Karpathy micrograd: https://github.com/karpathy/micrograd

Refresh this list as better SOTA examples appear.

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
