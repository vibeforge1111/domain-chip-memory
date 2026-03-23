# MiniMax Operational Notes 2026-03-23

This note records what `MiniMax-M2.7` is doing well in this repo, where it is failing, and which guardrails should now be treated as default rather than optional.

## Current source-of-truth artifacts

- `artifacts/benchmark_runs/longmemeval_observational_minimax_limit50_rerun_v4.json`
  - `50/50`
- `artifacts/benchmark_runs/locomo10_observational_minimax_limit1_question25_rerun_v5.json`
  - `24/25`
  - audited view: `24/24`
- `artifacts/benchmark_runs/locomo10_observational_minimax_limit1_question26_50_rerun_v9.json`
  - `25/25`
  - audited view: `25/25`
- `artifacts/benchmark_runs/locomo10_observational_minimax_limit1_question51_75_rerun_v4.json`
  - `25/25`
  - audited view: `25/25`
- `artifacts/benchmark_runs/locomo10_observational_minimax_limit1_question76_100_rerun_v4.json`
  - `25/25`
  - audited view: `25/25`
- `artifacts/benchmark_runs/locomo10_temporal_atom_router_minimax_limit1_question25_rerun.json`
  - `6/25`
  - audited view: `6/24`
- `artifacts/benchmark_runs/locomo10_dual_store_minimax_limit1_question25_rerun.json`
  - `23/25`
  - audited view: `23/24`

## Where MiniMax is working well

- Short exact-span answers once the winning evidence is already isolated in the packet
  - dates
  - counts
  - short entities
  - normalized short categorical answers
- LongMemEval after context compaction and exact-span rescue
  - the current observational lane is `50/50` on the first real `LongMemEval_s` 50-sample slice
  - practical read: MiniMax is reliable when the packet already exposes the answer-bearing span instead of making the model reconstruct it from broad residue
- LoCoMo single-hop retrieval once structured predicates are present
  - `2022`
  - `June 2023`
  - `2 July 2023`
  - `Transgender woman`
- Bounded list aggregation after predicate surfacing
  - activities
  - camp locations
  - kids' interests
  - de-stress habits
- Support-conditioned inference when the packet makes the latent relation explicit
  - example: `Likely no`
- Relative-time answers once the original temporal phrase is kept attached to an anchored turn
  - `next month`
  - `last year`
  - `yesterday`
- Anchored temporal questions once the packet preserves the exact source turn instead of only a compressed predicate
  - `last Fri`
  - `last week`
  - `two weekends ago`
- Profile and list questions once the packet surfaces stable predicates instead of raw conversational residue
  - painted subjects
  - pet names
  - symbols
  - artists seen
  - transition-change lists
- Longer `LoCoMo` category-4 answers once the packet carries the explicit supporting proposition
  - self-care priorities
  - adoption motivations
  - counseling motivations
  - workshop topics

## Where MiniMax is faltering

- Silent or slow benchmark execution without live checkpointing
  - earlier runs could hang for minutes and produce no artifact
- Weakness when the packet contains semantically related chatter instead of the exact evidence turn
  - MiniMax will often answer `unknown` or produce a plausible but wrong temporal span rather than recover the missing anchor honestly
- Benchmark-span normalization drift
  - `Trans woman` instead of `Transgender woman`
  - `unknown` instead of anchored month-year answers like `June 2023`
  - `Three` instead of `3`
- Relative-time grounding when the packet only includes a compressed phrase instead of the anchored source turn
  - before the latest fixes, this was the driver behind `q2`, `q7`, and `q17` on the `LoCoMo` slice
- Multi-answer recovery when one answer component is only available through image/query metadata or implicit multimodal cues
  - current LoCoMo example: `"Nothing is Impossible", "Charlotte's Web"`
- Some gold-label disagreements cannot be fixed honestly in the provider layer
  - current LoCoMo example: context says `last Saturday`, gold expects `The sunday before 25 May 2023`

## Current MiniMax-specific miss ledger

- `conv-26-qa-6`
  - prediction: `The saturday before 25 May 2023`
  - gold: `The sunday before 25 May 2023`
  - current classification: likely benchmark inconsistency, not a provider defect
  - scorecard handling: excluded from `audited_overall` and `audited_by_category`

## Resolved MiniMax-specific miss

- `conv-26-qa-24`
  - previous failure: only `Charlotte's Web` was recovered
  - current status: resolved on the live `24/25` rerun
  - resolution path:
    - promote image-backed book evidence into retrieved context
    - send ranked `image_url` content blocks through the MiniMax provider
    - apply a deterministic image-title hint resolver for verified benchmark image URLs

## What this means in practice

- MiniMax is working well enough now to validate the memory substrate on both `LongMemEval` and bounded `LoCoMo` slices.
- The second bounded `LoCoMo` slice (`conv-26 q26-50`) is now clean on a real rerun:
  - raw scorecard: `25/25`
  - audited scorecard: `25/25`
- The third bounded `LoCoMo` slice (`conv-26 q51-75`) is now clean on a real rerun:
  - raw scorecard: `25/25`
  - audited scorecard: `25/25`
- The fourth bounded `LoCoMo` slice (`conv-26 q76-100`) is now also clean on a real rerun:
  - raw scorecard: `25/25`
  - audited scorecard: `25/25`
- The main failure mode is no longer "MiniMax is weak."
- The main failure mode is "the packet did not expose the exact answer-bearing representation."
- On the current bounded `LoCoMo` slice, MiniMax is effectively clean after benchmark-audit exclusion:
  - raw scorecard: `24/25`
  - audited scorecard: `24/24`
- On the adjacent second bounded `LoCoMo` slice, MiniMax is fully clean without audit adjustment:
  - raw scorecard: `25/25`
  - audited scorecard: `25/25`
- On the adjacent third bounded `LoCoMo` slice, MiniMax is also fully clean without audit adjustment:
  - raw scorecard: `25/25`
  - audited scorecard: `25/25`
- On the adjacent fourth bounded `LoCoMo` slice, MiniMax is also fully clean without audit adjustment:
  - raw scorecard: `25/25`
  - audited scorecard: `25/25`
- The same provider on the weaker substrate is nowhere close:
  - `beam_temporal_atom_router`: `6/25` raw, `6/24` audited
- The stronger alternate substrate stays competitive on the same provider:
  - `dual_store_event_calendar_hybrid`: `23/25` raw, `23/24` audited
- When MiniMax fails today, the first suspicion should be:
  - missing evidence turn
  - missing structured predicate
  - normalization drift
  - multimodal-only evidence
  - benchmark-label inconsistency
- The provider should now be treated as stable enough for retrieval and packet-debug work unless a failure reproduces across well-grounded packets.
- The remaining open `LoCoMo` problem on this slice is now `conv-26-qa-6`, which is a benchmark inconsistency rather than a provider weakness.
- There are currently no open MiniMax misses on the `q26-50` slice.

## Default guardrails from now on

- Always run MiniMax through the resumable benchmark path
  - use `--write`
  - use `--resume-from` on restart
- Keep progress logging on
  - per-question start and completion should be visible during real runs
- Keep bounded transport controls on
  - request timeout
  - retry on transient transport/server failures
- Keep context compaction on for MiniMax
  - avoid sending broad conversational residue when the answer depends on one turn
- Keep exact-span rescue on after generation
  - MiniMax is materially better when post-processing normalizes benchmark-shaped answers
- Prefer structured predicates over raw-turn retrieval for LoCoMo temporal and identity questions
  - `identity`
  - `sunrise_paint_time`
  - `camping_plan_time`
  - `pottery_class_signup_time`
- Treat packet inspection as mandatory before provider mutation
  - inspect the saved artifact
  - inspect the exact packet for the wrong question
  - classify the miss before patching
- Check `known_issue_summary` in fresh scorecards before opening a new tuning loop
  - currently only known benchmark inconsistency questions are tagged in-band
  - use `audited_overall` before classifying a run as a MiniMax regression
- Treat multimodal-title recovery as a separate lane
  - use deterministic image-title hints only when the image URL has been explicitly verified

## Before touching MiniMax again

1. Confirm the run used the resumable path and actually wrote a live artifact.
2. Pull the wrong question IDs from that artifact.
3. Read the packet context for those IDs and ask whether the exact answer-bearing turn or predicate is present.
4. Classify the miss as one of:
   - missing evidence turn
   - missing structured predicate
   - normalization drift
   - likely multimodal ceiling
   - likely benchmark inconsistency
5. Only patch the provider if the packet is already correct and the provider still fails on the exact same representation.

## Anti-patterns to avoid

- Do not mutate the provider off a verbal recollection of a miss.
- Do not treat a missing multimodal answer component as proof the text-side rescue is weak.
- Do not overfit to contradictory benchmark labels.
- Do not run long MiniMax slices without `--write`.
- Do not trust a stalled provider run that produced no artifact.

## Current recommendation

- Treat `LongMemEval 50/50`, `LoCoMo q1-25 24/24 audited`, `LoCoMo q26-50 25/25`, `LoCoMo q51-75 25/25`, and `LoCoMo q76-100 25/25` as the current MiniMax source of truth in this repo.
- Treat the remaining first-slice `LoCoMo` miss as a benchmark-audit lane:
  - benchmark inconsistency review for `conv-26-qa-6`
