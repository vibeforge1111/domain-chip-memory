# Answer Candidate Precedence Rule - 2026-03-26

Status: active consolidation doctrine

## Explicit rule

If packet assembly emits an explicit primary `answer_candidate`, deterministic responder logic must treat that candidate as authoritative.

That means:

- `BaselinePromptPacket.answer_candidates[0]` beats weaker overlap with raw evidence lines
- responder selection is not allowed to re-decide the answer from assembled context if a primary packet candidate already exists
- provider-side rescue may normalize or preserve that candidate, but it must not silently replace it with weaker overlap-only text

## What Is Now Explicit In Code

- `src/domain_chip_memory/answer_candidates.py`
  - shared helpers now expose the primary packet candidate and context candidate extraction
- `src/domain_chip_memory/responders.py`
  - `heuristic_response(...)` now returns the packet-level primary candidate before any line scoring

## Next Consolidation Boundary

The next named boundary is provider normalization in:

- `src/domain_chip_memory/providers.py`
  - especially `_expand_answer_from_context(...)`

That function still contains question-shaped rescue logic and context-ranked candidate handling. The next pass should make it consume typed answer-candidate metadata more directly instead of relying on scattered string heuristics.
