# BEAM Official Reproduction Plan 2026-03-29

Status: active

## Purpose

This file turns `BEAM` from a paper-tracked frontier target into an exact public reproduction program.

The repo already has a useful local pilot lane.
That lane remains valuable, but it is no longer enough to represent `BEAM` honestly now that the official public surface exists.

## Public sources

- paper: `https://arxiv.org/abs/2510.27246`
- official repo: `https://github.com/mohammadtavakoli78/BEAM`
- official dataset: `https://huggingface.co/datasets/Mohammadta/BEAM`
- official 10M dataset: `https://huggingface.co/datasets/Mohammadta/BEAM-10M`

## What the public BEAM surface claims

- `100` conversations
- `2,000` validated probing questions
- scale ladder across `128K`, `500K`, `1M`, and `10M`
- ten memory abilities:
  - abstention
  - contradiction resolution
  - event ordering
  - information extraction
  - instruction following
  - knowledge update
  - multi-session reasoning
  - preference following
  - summarization
  - temporal reasoning

## Repo doctrine

`BEAM` is now the core frontier stress benchmark.

That does not mean:

- optimizing only for `BEAM`
- dropping `LongMemEval_s`
- dropping clean `LoCoMo`
- calling the local pilot lane the official proof

It means:

- `BEAM` is the hardest architecture pressure lane
- `LongMemEval_s` and `LoCoMo` remain mandatory guardrails
- official `BEAM` claims must come from the exact public surface, not our internal pilot artifacts

## Reproduction contract

We should not call any run `official BEAM reproduction` until all of the following are pinned in-repo:

1. one exact upstream repo commit
2. one exact dataset source and scale selection
3. one exact command path for answer generation
4. one exact command path for evaluation
5. one exact result artifact schema
6. one exact baseline/result line to beat

## Immediate execution steps

1. pin the upstream repo commit hash we trust
2. pin the first scale ladder we will reproduce:
   - `128K`
   - `500K`
   - `1M`
   - `10M`
3. pin the official answer-generation flow
4. pin the official evaluation flow
5. map their result schema into our scorecard contract
6. run the first exact reproduction on one scale before broadening
7. compare our local pilot signals against the official run to see what transfers and what does not

## Local pilot relationship

The local pilot in [BEAM Local Pilot Slice](BEAM_LOCAL_PILOT_SLICE_2026-03-25.md) stays alive for a different job:

- fast deterministic regression
- architecture probing
- internal failure slicing

It is not the external proof path.

## Success condition

`BEAM` is considered honestly integrated into this repo when:

- the official public surface is commit-pinned
- at least one full official scale lane is reproduced in-repo
- our result artifacts are reproducible
- benchmark claims are clearly separated between:
  - official BEAM reproduction
  - internal BEAM local pilot
