from __future__ import annotations

from .provider_context_text import line_payload, question_tokens


def candidate_payloads(question: str, context: str, *, max_lines: int = 8) -> list[str]:
    lines = [line.strip() for line in context.splitlines() if line.strip()]
    if not lines:
        return []

    tokens = question_tokens(question)
    scored: list[tuple[float, int, str]] = []
    for idx, line in enumerate(lines):
        payload = line_payload(line)
        lower = payload.lower()
        token_score = sum(1 for token in tokens if token in lower)
        if not token_score and not any(
            marker in line.lower()
            for marker in {"answer_candidate:", "belief:", "reflection:", "evidence:", "observation:", "memory:"}
        ):
            continue
        bonus = 0.0
        if "answer_candidate:" in line.lower():
            bonus += 2.0
        if "belief:" in line.lower() or "reflection:" in line.lower():
            bonus += 0.75
        if "evidence:" in line.lower():
            bonus += 1.0
        if "observation:" in line.lower() or "memory:" in line.lower():
            bonus += 0.25
        scored.append((token_score + bonus, idx, payload))

    if not scored:
        return [line_payload(line) for line in lines[:max_lines]]

    top = sorted(scored, key=lambda item: (-item[0], item[1]))[:max_lines]
    return [payload for _, _, payload in sorted(top, key=lambda item: item[1])]
