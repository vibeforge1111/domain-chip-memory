# Tomorrow Start Checklist

Date: 2026-03-26
Status: restart checklist

## Start-of-day order

1. Confirm clean repo state on `origin/main`.
2. Re-read:
   - `docs/SESSION_LOG_2026-03-25.md`
   - `docs/MEMORY_ARCHITECTURE_EVOLUTION_PLAN_2026-03-25.md`
   - `docs/UNIFIED_MEMORY_SYSTEM_PROGRAM_2026-03-25.md`
3. Run the untouched baseline for `LongMemEval_s 201-225`.
4. Bucket the miss set before touching code:
   - current-state or supersession
   - aggregate or count
   - temporal disambiguation
   - preference or guidance
   - abstention
   - answer-shape drift
5. Open the first substrate task in parallel:
   - define typed `answer_candidate` metadata
   - carve current-state logic out of the packet builder
6. Select the next clean `LoCoMo` frontier lane.
7. Decide whether the same day still has time to lock the canonical `GoodAI` run.

## Mandatory guardrails

- do not treat contaminated `LoCoMo conv-26 q151-199` as a clean frontier lane
- do not add question-shaped rescue logic before checking whether the miss is a generic operator failure
- do not let provider rescue become the permanent home for substrate correctness
- preserve closed `LongMemEval_s` and clean `LoCoMo` slices as regression gates

## Concrete first code tasks

### Task 1

Add typed answer-candidate metadata to contracts and packet surfaces.

Target types:

- `exact_numeric`
- `currency`
- `date`
- `location`
- `preference`
- `current_state`
- `abstain`

### Task 2

Create a dedicated current-state and supersession surface.

Initial goal:

- move mutable-fact selection logic out of packet-local heuristics

### Task 3

Define the first generic operator layer.

Start with:

- count and sum
- compare and diff
- temporal before-after
- current-state lookup

## Concrete benchmark tasks

### LongMemEval

- produce the real `201-225` baseline artifact
- identify dominant miss class
- only then mutate

### LoCoMo

- choose a clean bounded slice with valid gold answers
- avoid spending time on contaminated tail bookkeeping

### GoodAI

- pin one canonical config
- produce one source-of-truth run instead of leaving the harness abstract

### BEAM

- if the implementation surface is available, define adapter and scorecard skeletons immediately
- if it is not yet available, document the exact blocker rather than leaving it vague

## End-of-day success criteria

Tomorrow counts as productive if all of these are true:

1. `LongMemEval_s 201-225` baseline exists
2. the next clean `LoCoMo` lane is selected
3. typed `answer_candidate` design is defined
4. the current-state extraction boundary is identified in code
5. `GoodAI` is either pinned or explicitly blocked with evidence
6. `BEAM` is either given a concrete adapter contract or explicitly blocked with evidence
