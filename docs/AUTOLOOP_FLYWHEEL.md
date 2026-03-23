# Agent Memory Autoloop Flywheel

Date: 2026-03-22

## Core principle

This chip should improve through benchmark slices, not one giant self-edit loop.

Each flywheel needs:

- owner
- benchmark scope
- mutation surface
- evaluation surface
- rollback rule

## Flywheel stack

### 1. Benchmark intake flywheel

Benchmark source -> adapter -> normalized packet -> target ledger -> watchtower

Owner:

- `Research Owner`

### 2. Retrieval flywheel

Failure case -> retrieval trace -> mutation packet -> rerun -> keep or revert

Owner:

- `Memory Research Owner`

### 2B. Combination flywheel

Baseline stack -> add one component family -> rerun benchmark slice -> compare cost and score -> keep or revert

Owner:

- `Architecture Owner`

### 3. Answer-policy flywheel

Question-type failures -> prompt or policy variant -> shadow run -> category report

Owner:

- `Evaluation Owner`

### 3B. Ablation flywheel

Winning stack -> remove one component family -> rerun benchmark slice -> confirm necessity or remove dead weight

Owner:

- `Architecture Owner`

### 3C. Variation flywheel

One system family -> multiple bounded variants on one axis -> compare against direct parent -> keep top variant only

Owner:

- `Research Owner`

### 4. Attribution flywheel

Source repo -> license check -> allowed borrowing decision -> attribution record

Owner:

- `Attribution Steward`

### 5. Promotion flywheel

Repeated win -> contradiction review -> benchmark-grounded doctrine candidate -> promote or block

Owner:

- `Factory Owner`

## Routing rule

The chip should only self-edit on bounded mutation families:

- ingestion
- schema
- retrieval
- answer policy
- evaluation

Never allow one mutation packet to rewrite the entire system at once.
Never allow a combination packet to add more than one new heavyweight online family at once.
