# Memory Lanes And Quality Gates 2026-04-28

This is the human-readable map for Spark memory lanes. It exists so Builder, Telegram, diagnostics, Spawner, Codex, and sidecars all agree on what kind of memory they are touching.

The goal is not to save more. The goal is to save the right things, in the right lane, with the right authority.

## Lane Map

| Lane | Human Meaning | Examples | Authority | Owner | Write Rule | Recall Rule |
| --- | --- | --- | --- | --- | --- | --- |
| Working scratchpad | Useful only right now | "Let's compare two options", temporary brainstorm details | Lowest | Builder runtime | Keep in active turn/session only unless promoted | Use for immediate conversation continuity only |
| Current identity | Who the user is now | preferred name, timezone, home country, role | Highest for identity | Builder + `domain-chip-memory` | Corrections immediately supersede older identity facts | Answer direct identity/profile questions |
| Current user/work state | What the user is actively doing now | current focus, plan, blocker, decision, commitment | Highest for active work | Builder + `domain-chip-memory` | Explicit focus/plan/status updates become current state | Drives "what should we do next?" |
| Entity current state | Current facts about named objects/projects | GTM launch owner, deadline, blocker, metric | High for named entities | Builder + `domain-chip-memory` | Store typed entity facts with `entity_key` and attribute | Answer current project/workflow questions |
| Historical/supersession | What used to be true | previous plant name, prior owner, old blocker | High only for historical questions | `domain-chip-memory` | Never delete meaningful old values; mark superseded/stale | Use only when user asks "before/previous/changed from" |
| Structured evidence | Provenance for a claim | raw source event, tool result, diagnostic note path | Supporting | `domain-chip-memory` | Store only useful support with source metadata | Support answers and explanations |
| Episodic trace | Compressed story of what happened | "Today we built X, fixed Y, left Z open" | Supporting/high for work reconstruction | Builder consolidation | Summarize session/day/project changes, not raw transcript dumps | Answer "what did we build today?" and "what else do you remember?" |
| Procedural/task recovery | Lessons and interrupted work | wrong target repo, timeout point, failed delivery, retry step | Supporting for operations | Builder + Hindsight-style lane | Store failures/corrections as experiences, not user facts | Help avoid repeating mistakes and resume tasks |
| Project/wiki packets | Durable project knowledge | architecture decisions, handoffs, docs, open bugs | Supporting/high for project questions | Builder + Obsidian/wiki | Write semantic summaries and handoffs | Retrieve for project/workflow synthesis |
| Graph sidecar | Relationship and temporal graph | entity relations, validity windows, event ordering | Supporting until promoted | Graphiti adapter | Ingest approved episodes/entity changes | Add relationship/temporal context below current state |
| Diagnostics/maintenance | System health evidence | clean scan, connector health, maintenance summary | Authority for health only | Diagnostics | Store reports as health evidence | Never close user goals by itself |
| Workflow residue | Jobs, missions, routes, old process state | old mission IDs, stale workflow payloads | Advisory | Spawner/Builder | Keep for debugging, not memory truth | Use only when user asks about jobs/workflows |
| Shadow comparator | External memory candidates | Mem0 extraction/search hits | No authority | Mem0 adapter | Compare only | Never answer from it until promoted by Spark gates |
| Quarantine/rejected | Bad or unsafe memory/output | secrets, unlabeled provenance, bad claims, wrong-target residue | Blocking evidence | Observability/policy gates | Record why rejected | Never recall as truth; inspect for debugging |

## Identity Correction Rule

Identity corrections are special.

If the user says a correction such as:

```text
I'm not Maya by the way, I'm Cem.
Actually, my name is Cem.
No, call me Cem.
```

Spark must:

1. classify it as `identity_correction`;
2. promote it directly to `profile.preferred_name` current state;
3. mark the prior identity value stale/superseded;
4. preserve the old value in historical state;
5. store `why_saved=identity_correction_supersession`;
6. record source text, source surface, timestamp, and actor;
7. answer future name questions from current identity, not raw episode text.

It must not:

- store the correction only as an episodic sentence;
- let older workflow/profile residue override it;
- keep both names as equally current;
- require repeated confirmation for direct identity corrections.

## Quality Gate Architecture

Every candidate memory passes through gates before promotion.

```text
candidate event
  -> capture normalization
  -> source/provenance gate
  -> privacy/security gate
  -> target-scope gate
  -> salience/keepability gate
  -> lane classifier
  -> authority/supersession gate
  -> write or quarantine
  -> recall-gate trace
```

## Gate Map

| Gate | Blocks | Allows | Record |
| --- | --- | --- | --- |
| Source/provenance gate | unlabeled claims, missing actor/source, unsupported memory writes | traceable observations and tool outputs | `policy_gate_records`, rejected reason |
| Privacy/security gate | secrets, credentials, sensitive output leaks | redacted or safe summaries | `quarantine_records` |
| Target-scope gate | wrong repo/build target assumptions, stale Spawner payloads | target-confirmed build/workflow facts | procedural memory + policy gate |
| Salience/keepability gate | small talk, transient chatter, low-value residue | important facts, decisions, corrections, repeated signals | salience metadata |
| Lane classifier | facts going to wrong lane | identity/current/entity/episode/procedural/etc. | `memory_lane`, `promotion_stage` |
| Authority/supersession gate | stale value outranking current value | current truth plus historical supersession | current and historical state |
| Claim-quality gate | bad claims, unsupported self-review, hallucinated build quality | answers backed by files/diffs/tests/source packets | bad-claim rejection or evidence refs |
| Delivery gate | unsafe/failed outbound replies | delivered messages with registry status | `delivery_registry` |

## Salience Operator

Builder owns salience. Sidecars can propose, but Builder decides.

Initial scoring dimensions:

- explicitness: did the user ask Spark to remember it?
- active work relevance: does it affect current focus, plan, project, build, startup, workflow, or operation?
- identity/user relevance: does it affect who the user is, how to address them, or durable preferences?
- entity importance: is it about a named project/object/person/workstream?
- decision/action signal: owner, blocker, deadline, metric, next action, priority, decision, status.
- correction/supersession signal: does it replace an older fact?
- recurrence/confirmation: repeated or confirmed facts become stronger.
- source authority: direct user statement beats workflow residue.
- risk penalties: small talk, uncertainty, privacy, stale target, unsupported inference.

Promotion bands:

| Band | Meaning | Example |
| --- | --- | --- |
| `drop` | Not useful or unsafe | random filler, unsafe secret |
| `scratchpad` | Useful only now | temporary brainstorming |
| `raw_episode` | Meaningful event, not durable truth | "we discussed pricing angles" |
| `structured_evidence` | Support/provenance | diagnostic note, tool output |
| `current_state_candidate` | Plausible but needs confirmation | weakly implied preference |
| `current_state_confirmed` | Durable current truth | direct identity correction, explicit plan |
| `procedural_lesson` | Operational learning | wrong repo target, timeout recovery |
| `quarantine` | Blocked from memory/answer | secret-like output, bad claim |

## Human-Readable Recall Explanation

Every memory answer should be explainable in plain language.

Good explanation:

```text
I used current identity memory. Your latest saved preferred name is Cem, and the older Maya value was superseded by your correction.
```

Good source trace:

```text
source_class=current_state
memory_lane=current_identity
read_method=get_current_state
supersession=older_identity_marked_stale
```

Bad explanation:

```text
I answered from memory.
```

Bad behavior:

```text
I found both Maya and Cem, so maybe either.
```

## Builder/Workflow-Creator Keepability

Spark is an agent operating system, not a generic chat memory toy. Keepability must understand work.

High-value builder/workflow memories:

- target repo and active component
- user goal and current plan
- repo ownership and installer provenance
- decisions made while building
- bugs found and fixed
- tests run and their result
- artifacts created and where they live
- blockers, owners, deadlines, metrics
- wrong-target corrections
- timeout recovery steps
- preferences that shape future work

Low-value or risky memories:

- repeated acknowledgements
- casual status chatter with no durable content
- stale mission residue
- unsupported quality claims
- raw log noise
- private/sensitive text without explicit reason
- tool outputs without provenance

## Required Runtime Ledgers

The architecture needs these ledgers populated, not merely present:

- `policy_gate_records`: every blocked memory/output/claim with gate name and reason.
- `quarantine_records`: unsafe or malformed content that must not be recalled as truth.
- `delivery_registry`: outbound delivery attempts, failures, and delivered message IDs.
- salience decision records: keep/drop/rewrite/promotion decision with explanation.
- supersession records: old value, new value, reason, source event, valid windows.
- procedural experience records: task failure or correction plus future lesson.

## Acceptance Tests

- "I'm not Maya by the way, I'm Cem." changes current identity to Cem and marks Maya stale.
- "What was my name before?" can answer Maya only as historical/superseded.
- "What do you remember from today?" returns session/day/project summaries.
- A wrong-target build creates a procedural lesson and a target-confirmation requirement.
- A timeout creates a pending task record with next retry step.
- Unsafe output creates quarantine and policy-gate records, not memory.
- A build-quality answer must inspect repo/diff/tests/demo evidence before rating.
- "Why did you answer that?" names lane, source class, read method, and authority decision.
