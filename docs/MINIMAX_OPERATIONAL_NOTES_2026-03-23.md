# MiniMax Operational Notes 2026-03-23

This note records what `MiniMax-M2.7` is doing well in this repo, where it is failing, and which guardrails should now be treated as default rather than optional.

## Current source-of-truth artifacts

- `artifacts/benchmark_runs/longmemeval_observational_minimax_limit50_rerun_v4.json`
  - `50/50`
- `artifacts/benchmark_runs/locomo10_observational_minimax_limit1_question25_rerun_v3.json`
  - `19/25`

## Where MiniMax is working well

- Short exact-span answers once the right evidence is in context
  - dates
  - counts
  - short entities
  - normalized short categorical answers
- LongMemEval after context compaction and exact-span rescue
  - the provider is strong when the packet already isolates the winning fact
- LoCoMo single-hop and bounded list questions once structured predicates are present
  - activities
  - camp locations
  - kids' interests
  - de-stress habits
- Support-conditioned inference when the packet makes the latent relation explicit
  - example: `Likely no`

## Where MiniMax is faltering

- Silent or slow benchmark execution without live checkpointing
  - earlier runs could hang for minutes and produce no artifact
- Weakness when the packet contains only semantically related chatter instead of the exact evidence turn
  - the model will not reliably reconstruct the missing temporal span
- Benchmark-span normalization drift
  - `Trans woman` instead of `Transgender woman`
  - `unknown` instead of anchored month-year answers like `June 2023`
- Relative-time grounding when the packet only includes a compressed phrase instead of the anchored source turn
  - `next month`
  - `last year`
  - `yesterday`
- Multi-answer recovery when one answer component is only available through image/query metadata or implicit multimodal cues
  - current LoCoMo example: `"Nothing is Impossible", "Charlotte's Web"`
- Some gold-label disagreements cannot be fixed honestly in the provider layer
  - current LoCoMo example: context says `last Saturday`, gold expects `The sunday before 25 May 2023`

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
- Treat multimodal-title recovery as a separate lane
  - do not overfit text-only rescue logic to hallucinate missing title names

## Practical interpretation

- MiniMax is not the main blocker on `LongMemEval` anymore.
- On `LoCoMo`, MiniMax is good enough to validate retrieval and packet improvements, but only if the packet is sharply grounded.
- The dominant failure mode is no longer "the model is weak."
- The dominant failure mode is "the packet did not contain the exact answer-bearing representation the model needed."

## What to do before blaming MiniMax again

1. Check the live checkpoint artifact and identify the exact stalled or wrong question IDs.
2. Inspect the packet context for those IDs.
3. Decide whether the miss is:
   - missing evidence turn
   - missing structured predicate
   - answer normalization drift
   - likely benchmark inconsistency
   - likely multimodal ceiling
4. Only then mutate the provider or the memory substrate.

## Current open MiniMax-specific issues

- `conv-26-qa-24`
  - text-only path currently recovers only `Charlotte's Web`
  - likely needs multimodal/title recovery to reach the full gold string
- `conv-26-qa-6`
  - likely benchmark inconsistency rather than provider weakness
