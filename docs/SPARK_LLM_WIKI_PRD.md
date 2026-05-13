# Spark LLM Wiki PRD

## Product Intent

Spark LLM Wiki is the readable learning journal for Spark's agent brain. It turns governed Spark KB packets, recursive run capsules, specialization path history, benchmark movement, and review boundaries into a surface that a non-technical operator can inspect without reading logs.

The Wiki is not runtime truth. It is supporting historical context. Current runtime status, Workspace state, benchmark recompute reports, and review gates still decide what is true now.

## Users

- Local Spark operators who want to understand what their agent learned.
- Builders creating specialization paths, domain chips, benchmark packs, autoloops, or creator missions.
- Reviewers deciding whether a local packet is safe to promote later.
- Telegram-first users who need compact answers with a deeper evidence link.

## First Viewport Job

The first viewport should answer four questions:

1. What did Spark learn recently?
2. Which specialization paths changed?
3. What needs review or stronger evidence?
4. What should I do next?

It should not lead with raw artifact counts, filesystem paths, trace IDs, stack traces, or command dumps.

## Core Surfaces

### Dashboard

The dashboard is the front door. It should show:

- Spark logo and `/wiki` lockup.
- Dark and light mode.
- Learning journal summary.
- Recent recursive path updates.
- Agent Brain connections.
- Search over wiki packets, timeline items, and recursive run summaries.
- Clear local/private boundary.

### Path Pages

Every specialization path can have a path-level page. The page should be generated from recursive run metadata and must remain path-agnostic.

Each page should show:

- Current score and best score when available.
- Recent score movement.
- Latest lesson or mutation intent.
- Kept/reverted candidate counts.
- Benchmark gaps or next useful move.
- Review/privacy state.
- Links to detailed run capsules when available.

### Run Capsules

Run capsules should read like learning notes:

- What happened.
- What changed.
- Score movement.
- Candidate or mutation tried.
- Evidence used.
- What Spark learned.
- What was kept or reverted.
- Next useful move.

Raw logs and audit paths stay in safe metadata, not in the main human-facing page.

### Telegram Bridge

Telegram should stay compact and link to the Wiki for depth.

Supported user intents:

- "show me what Spark learned about QA Operator"
- "what changed in today's recursive runs?"
- "compare this run to yesterday"
- "save this as a wiki note under QA Operator"
- "what should we improve next?"
- "open my LLM wiki"
- "summarize recent agent brain changes"

Telegram replies should answer:

- What happened?
- Is it good, neutral, blocked, or bad?
- What matters now?
- Where can I inspect the full evidence?

If the conversation context is ambiguous, Spark should ask one short clarifying question before routing to a recursive or Wiki action.

## Privacy And Review States

Every human-facing page or packet should make one of these states visible:

- `local/private`: only local operator evidence.
- `needs redaction`: not safe to share.
- `review required`: human or system review gate needed.
- `safe to share`: no obvious sensitive material, but still local unless policy opens sharing.
- `network-ready later`: shaped for future Spark Swarm sharing, not currently public.

Spark Swarm public sharing is not open yet. The Wiki must not imply public publishing is available.

## Source-Aware Search

Search should eventually distinguish:

- current truth
- historical context
- supporting evidence
- generated interpretation
- private/local-only items

The first implementation may use local indexed summaries, but the UI copy must preserve the authority boundary.

## Benchmark And QA Expectations

Spark QA Operator should test the Wiki and Telegram flow for:

- stale score claims
- wrong Workspace evidence
- wrong specialization path attribution
- confusing current/best score wording
- raw path or token leakage
- private/public boundary mistakes
- polished Telegram copy that hides wrong evidence
- recursive run pages missing "what Spark learned"

Clean wording is not enough. QA should reward source-backed truthful reporting.

## Success Metrics

- A non-technical user can understand the latest learning state in under 10 seconds.
- Recursive path pages are generated for every valid path record.
- Run capsules and path pages contain no tokens, local paths, command dumps, or stack traces in the visible body.
- Telegram replies remain compact and link to the Wiki only when useful.
- Malformed or stale recursive metadata does not break the dashboard.
- The implementation works for any specialization path, not only Spark QA Operator.

## Non-Goals For This Slice

- Public Spark Swarm publishing.
- Live mutation controls from the Wiki UI.
- Treating Wiki prose as authoritative memory.
- Replacing Workspace, benchmark reports, or review gates.
