# Today's Memory Improvement Ledger - 2026-05-01

This note saves the honest good/bad read from today's Spark memory work. It is meant to help the next agent, and the human operator, improve both sides instead of only celebrating green tests.

## North Star

Spark should feel like it gets the operator over time:

- it remembers what matters without needing command-like phrasing
- it forgets or downranks short-lived chatter
- it can explain why a memory was kept, blocked, recalled, or ignored
- it keeps current facts current while preserving history for historical questions
- it can summarize the work narrative, not only isolated slot facts
- it exposes memory flow in a dashboard that humans and agents can both inspect

## What Got Better

### Entity-State Memory Is Becoming Useful

Current and previous recall now works for practical operating-system facts such as owner, location, status, deadline, blocker, priority, decision, next action, metric, and preference.

Good examples from Telegram:

- "The tiny desk plant is on the windowsill" and "before that, kitchen shelf."
- "The launch checklist is owned by Maya" and "before that, Omar."
- "The GTM launch blocker is creator approvals."
- "The GTM launch decision is founder-led onboarding."

How to make this stronger:

- keep expanding slot coverage only where the attribute is actually useful in workflows
- preserve the source trace for every current and historical answer
- add regression tests for each new attribute before supervised Telegram testing

### Source Explanations Improved

Several routes now explain themselves with the actual route used instead of a generic context capsule answer:

- `memory_entity_state_current`
- `memory_entity_state_history`
- `memory_entity_state_summary`
- `build_quality_review_direct`
- memory-kernel next-step reads

How to make this stronger:

- make source-aware explanation universal, including raw episodes, older memory, graph sidecar, inference, diagnostics, and workflow residue
- ensure "Why did you answer that?" always reads the previous answer trace, not a generic capsule snapshot

### Write Discipline Is Less Naive

The memory gate now blocks many short-lived questions and check-ins instead of storing them as durable memory. That is correct behavior. The dashboard now exposes examples of blocked records, salience, lane, and reason.

How to make this stronger:

- make salience reasons human-readable by default
- show the original user message more prominently than the internal label
- add "could have been better" review over blocked/accepted decisions

### Identity Correction Was Fixed

Preferred-name corrections such as "my name is Cem not Maya" now parse as authoritative identity supersessions instead of raw episodic text.

Current validation:

- canonical Builder commit: `ad3e264`
- live runtime patch confirmed salience `0.85`
- outcome: `profile.preferred_name = Cem`

How to make this stronger:

- add Telegram acceptance after runtime restart/deploy
- add historical-name tests so old names remain historical and never answer current identity questions

### Dashboard Became More Useful

The standalone memory-quality dashboard now has live export, polling, trace flows, human/agent surfaces, paginated trace lists, blocked/promotion views, scorecards, and route/source maps.

How to make this stronger:

- make accepted durable memories visible with salience/confidence and destination
- make flow cards clickable into full lineage
- add a daily "memory review" page for good/bad/ugly recommendations
- show what is decaying, promoted, blocked, compacted, archived, or still current

## What Still Feels Bad

### Episodic Memory Is Still Too Thin

Spark can remember isolated facts, but it still loses the living story of the day unless those facts were promoted into slots.

Symptoms:

- "What did we build today?" is not yet rich enough.
- "What else do you remember?" is unreliable.
- recent same-session context can be too compact.
- daily/project summaries exist, but are not fully wired into natural Telegram recall.

How to improve:

- wire daily/session/project summaries into recall routes
- add source-aware answers for "what changed today?", "what did we build?", "what is still open?", and "what did we promise?"
- keep a large reconstructable context reservoir separate from compact Telegram packets

### Some Architecture Is Still Shadow-Only

Graphiti/Kuzu and some domain-chip memory architecture are connected as sidecars or benchmarks, but they are not yet always improving the live user experience.

This is good for safety, but not enough for the product goal.

How to improve:

- keep Graphiti advisory, but add acceptance probes for aliases, relationships, validity windows, provenance, and project dependencies
- expose graph hits in source explanations and dashboard traces
- promote sidecar use only when scorecards show it improves recall without violating authority order

### Salience Is Still Pattern-Heavy

`for later` works, but that is too command-like. The real goal is that Spark understands importance from the operator's work, current project, repeated mentions, corrections, promises, and consequences.

How to improve:

- add context-aware salience features: active focus, target repo, repeated entity, correction, commitment, user preference, workflow consequence, and future usefulness
- add a reviewer pass that samples blocked/accepted decisions and says what should have happened
- store salience explanations in language a human can read

### Memory Dashboard Still Needs Better Human Comprehension

Some areas still read like ledger dumps. Humans need a narrative and a visual flow, while agents need raw traceability.

How to improve:

- maintain separate Human and Agent views
- use human-first cards for memory movement: captured -> assessed -> blocked/promoted -> destination -> recall
- show original message as the primary artifact
- add pagination and filters for accepted, blocked, decaying, archived, promoted, and recalled records
- add a memory-flow map that shows movement over time, not only static architecture boxes

### Live Runtime Sync Remains Awkward

Some fixes landed in canonical repos and were also patched into live module checkouts. That is useful for fast testing, but it creates confusion about what is deployed.

How to improve:

- add one command that prints canonical commit, live module commit/path, dirty state, and restart requirement
- show that deployment state on the dashboard
- make Telegram source explanations include runtime build/version when debugging memory behavior

## Next Build Slices

Do these before declaring the memory system excellent:

1. Source-aware episodic/day/project recall.
   - Natural questions should answer from session summaries when appropriate.
   - Answers must say whether they came from current state, daily summary, project summary, raw episode, graph sidecar, or inference.

2. Accepted-memory visibility in the dashboard.
   - Show durable memories with salience, confidence, lane, entity, attribute, current value, previous value, and destination.
   - Add pagination and filters.

3. Memory review / "good, bad, ugly" dashboard section.
   - Sample recent accepted, blocked, decayed, and recalled decisions.
   - Produce concrete improvement notes.
   - Save the review as an artifact and display it in both Human and Agent views.

4. Large context reservoir.
   - Keep compact Telegram packets small.
   - Maintain a reconstructable 200k+ context reservoir for session/project/day continuity.

5. Graph sidecar acceptance probes.
   - Validate aliases, relationships, validity windows, provenance, and dependency recall.
   - Keep Graphiti advisory until the probes pass.

6. Broader workflow tests.
   - Use startup ops, GTM, project build, marketing/content, investor updates, onboarding, debugging, repo handoff, and timeout recovery examples.
   - Avoid testing only tiny artificial facts.

## Current Verdict

Good: the memory system is no longer just a pile of saved snippets. It has lanes, authority order, entity-state, source traces, dashboard visibility, and better write discipline.

Bad: the system still does not consistently preserve the human story of the workday. It remembers slots better than it remembers the evolving collaboration.

Next: build source-aware episodic recall and dashboard accepted-memory visibility, then run broad workflow tests against real Spark use cases.
