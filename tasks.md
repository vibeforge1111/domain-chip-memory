# Tasks

Date: 2026-04-22

This file tracks the active conversational-memory hardening program for Spark.

Primary goal:

- make conversational / Telegram-style memory genuinely strong, not benchmark-patched

Success bar:

- LoCoMo improves materially on unseen slices
- no regression on BEAM / LongMemEval
- the same architecture changes help real multi-party chat memory, not just benchmark packs

## Current Program

## Phase 1: Typed Answer Projection

Status: completed

Problem:

- typed graph retrieval often finds the right fact
- providers still see raw support text like `Hey Jo` instead of a clean answer value like `Jo`

Tasks:

- [x] add typed graph sidecar for alias / commitment / negation / reported speech / unknown / temporal events
- [x] add eval-only typed graph retrieval
- [x] project typed graph hits into normalized answer candidates
- [x] verify alias questions return normalized alias values, not support spans
- [x] verify reported-speech questions return reported content, not full support sentences
- [x] verify negation / unknown questions surface `No` / `unknown` cleanly
- [x] rerun targeted real-provider probes after projection

## Phase 2: Retrieval Fusion

Status: pending

Problem:

- current shadow lanes are mostly summary vs exact-turn vs typed-graph
- stronger systems fuse semantic + lexical + symbolic/entity signals

Tasks:

- [ ] add lexical / BM25 retrieval lane
- [ ] add entity / alias boost lane
- [ ] define fusion policy across:
  - summary
  - exact-turn
  - typed-graph
  - lexical
  - entity-linked
- [ ] run shadow retrieval coverage comparison on unseen LoCoMo slice
- [ ] run shadow answer comparison with real providers

## Phase 3: Entity Linking Hardening

Status: pending

Problem:

- conversational questions rely on alias resolution, kinship resolution, and pronoun carryover

Tasks:

- [ ] strengthen alias binding resolution beyond greeting-only cases
- [ ] normalize family / kinship references across `mom`, `mother`, `her mother`, `my mom`
- [ ] add longer-range person resolution across sessions
- [ ] add tests for unseen social-reference questions

## Phase 4: Temporal Validity

Status: pending

Problem:

- current temporal normalization is useful but shallow
- we do not yet model fact validity windows strongly enough

Tasks:

- [ ] add valid-from / valid-until style temporal fact handling
- [ ] preserve superseded facts instead of flattening into one current answer
- [ ] improve historical queries over older relative-time expressions
- [ ] verify no regression on LongMemEval / BEAM temporal slices

## Phase 5: Cross-Event Synthesis

Status: pending

Problem:

- summary memory is still useful, but it should be synthesized from related event clusters rather than standing alone

Tasks:

- [ ] build cross-event summary lane over typed conversational events
- [ ] keep it separate from raw episode memory
- [ ] compare event-summary hybrid against current summary-only lane

## Evaluation Gates

These gates must hold before any runtime promotion:

- [ ] targeted LoCoMo alias / relation / temporal probes improve
- [ ] unseen LoCoMo slice improves with real providers
- [ ] BEAM regression stays clean
- [ ] LongMemEval regression stays clean
- [ ] no benchmark-only heuristics added without a production-memory justification

## Real-World Validation

The benchmark is not enough. We also need production-shaped checks.

Tasks:

- [ ] create Telegram-style multi-party memory probes
- [ ] include commitments, aliases, social graph, grief/support, negation, uncertainty
- [ ] verify retrieval and answer quality on those probes

## Operating Rules

- do not replace `summary_synthesis_memory`
- do not overfit to single LoCoMo conversations
- prefer additive layers over rewrites
- commit in small checkpoints
- only promote runtime after real-provider evidence is clearly better
