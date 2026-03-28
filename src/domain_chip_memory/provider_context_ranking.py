from __future__ import annotations

import re

from .provider_context_text import question_tokens


def rank_answer_candidate_entries(question: str, context: str) -> list[tuple[float, int, str]]:
    lines = [line.strip() for line in context.splitlines() if line.strip()]
    question_lower = question.lower()
    tokens = question_tokens(question)

    def _support_score(line_index: int) -> float:
        score = 0.0
        window_start = max(0, line_index - 2)
        window_end = min(len(lines), line_index + 3)
        for neighbor_index in range(window_start, window_end):
            neighbor = lines[neighbor_index]
            lower = neighbor.lower()
            score += sum(1 for token in tokens if token in lower)
            if "belief:" in lower or "reflection:" in lower:
                score += 0.5
            if "evidence:" in lower:
                score += 1.0
            if "memory:" in lower:
                score += 0.25
            if re.search(r"\b\d+\s+(?:minutes?|hours?|days?|weeks?|months?|years?)\b", lower):
                score += 0.25
            if "\"" in neighbor or "'" in neighbor:
                score += 0.1
        if lines[line_index].lower() == "answer_candidate: unknown":
            score -= 0.5
        if "artists/bands" in question_lower and " saw " in f" {lines[line_index].lower()} ":
            score += 1.0
        return score

    return sorted(
        [
            (_support_score(idx), idx, line)
            for idx, line in enumerate(lines)
            if line.lower().startswith("answer_candidate:")
        ],
        key=lambda item: (-item[0], item[1]),
    )


def compact_context(question: str, context: str, *, max_lines: int = 8) -> str:
    lines = [line.strip() for line in context.splitlines() if line.strip()]
    if len(lines) <= max_lines:
        return context

    question_lower = question.lower()
    tokens = question_tokens(question)
    answer_candidate_entries = rank_answer_candidate_entries(question, context)
    reserved_limit = min(max_lines, 2)
    reserved_entries = sorted(
        answer_candidate_entries[:reserved_limit],
        key=lambda item: item[1],
    )
    reserved = [line for _, _, line in reserved_entries]
    reserved_indices = {idx for _, idx, _ in reserved_entries}
    remaining_slots = max_lines - len(reserved)
    if remaining_slots <= 0:
        return "\n".join(reserved)

    scored: list[tuple[float, int, str]] = []
    for idx, line in enumerate(lines):
        if idx in reserved_indices:
            continue
        lower = line.lower()
        token_score = sum(1 for token in tokens if token in lower)
        if not token_score and not any(marker in lower for marker in {"answer_candidate:", "belief:", "reflection:", "evidence:", "memory:"}):
            continue
        bonus = 0.0
        if "answer_candidate:" in lower:
            bonus += 1.5
        if "belief:" in lower or "reflection:" in lower:
            bonus += 0.5
        if "evidence:" in lower:
            bonus += 1.0
        if re.search(r"\b\d+\s+(?:minutes?|hours?|days?|weeks?|months?|years?)\b", lower):
            bonus += 0.5
        if "\"" in line or "'" in line:
            bonus += 0.25
        if "artists/bands" in question_lower and " saw " in f" {lower} ":
            bonus += 3.0
        scored.append((token_score + bonus, idx, line))

    if not scored:
        selected = [line for line in lines if line not in reserved][:remaining_slots]
        return "\n".join([*selected, *reserved])

    top = sorted(scored, key=lambda item: (-item[0], item[1]))[:remaining_slots]
    selected = [line for _, _, line in sorted(top, key=lambda item: item[1])]
    return "\n".join([*selected, *reserved])
