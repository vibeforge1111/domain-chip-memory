from __future__ import annotations

import re

from .answer_candidates import primary_answer_candidate_text
from .runs import BaselinePromptPacket


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" .,:;!?")


def _extract_numbered_items(value: str) -> list[str]:
    matches = list(re.finditer(r"\b\d+[.)]\s*", value))
    if len(matches) < 2:
        return []
    items: list[str] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
        item = value[start:end].strip(" \t\r\n,.")
        if item:
            items.append(item)
    return items


def _preserve_structured_answer(packet: BaselinePromptPacket, text: str) -> str:
    sample_id = str(packet.sample_id or "").strip().lower()
    if sample_id.startswith(("beam-500k-", "beam-1m-", "beam-10m-")):
        return text
    question_id = packet.question_id.lower()
    if "event_ordering" in question_id:
        items = _extract_numbered_items(text)
        if len(items) >= 2:
            return "\n".join(f"{index}) {item}" for index, item in enumerate(items, start=1))
    if "contradiction_resolution" in question_id:
        return re.sub(
            r"Could you clarify which is correct\??",
            "Which statement is correct?",
            text,
            flags=re.IGNORECASE,
        ).strip()
    return text


def _should_preserve_exact_candidate(packet: BaselinePromptPacket) -> bool:
    sample_id = str(packet.sample_id or "").strip().lower()
    return sample_id.startswith(("beam-500k-", "beam-1m-", "beam-10m-"))


def _last_matching_line(packet: BaselinePromptPacket) -> str:
    question_tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", packet.question.lower())
        if token not in {"what", "where", "when", "who", "does", "is", "are", "the", "a", "an", "my", "now"}
    }
    best_line = ""
    best_score = -1
    for line in packet.assembled_context.splitlines():
        line_lower = line.lower()
        score = sum(1 for token in question_tokens if token in line_lower)
        if line_lower.startswith("answer_candidate:"):
            score += 100
        if score >= best_score and ":" in line:
            best_line = line
            best_score = score
    return best_line


def _compact_answer_text(text: str) -> str:
    patterns = [
        r"(?:moved to|live in|lives in)\s+([A-Za-z0-9 _-]+)",
        r"(?:prefer|prefers)\s+([A-Za-z0-9 _-]+)",
        r"(?:favourite|favorite)\s+[A-Za-z0-9 _-]+\s+(?:is|could be described as)\s+([A-Za-z0-9 _-]+)",
        r"(?:favourite|favorite)\s+\w+\s+(?:is|could be described as)\s+([A-Za-z0-9 _-]+)",
        r"(?:favourite|favorite)\s+([A-Za-z0-9 _-]+)",
        r"is\s+([A-Za-z0-9 _-]+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _clean(match.group(1))
    return _clean(text)


def heuristic_response(packet: BaselinePromptPacket) -> str:
    explicit_candidate = primary_answer_candidate_text(packet.answer_candidates)
    if explicit_candidate:
        if _should_preserve_exact_candidate(packet):
            return explicit_candidate.strip()
        preserved = _preserve_structured_answer(packet, explicit_candidate)
        if preserved != explicit_candidate or "\n" in preserved:
            return preserved
        return _compact_answer_text(explicit_candidate)

    line = _last_matching_line(packet)
    if not line:
        return ""

    text = line.split(":", 1)[1].strip() if ":" in line else line.strip()
    if _should_preserve_exact_candidate(packet) and line.lower().startswith("answer_candidate:"):
        return text
    preserved = _preserve_structured_answer(packet, text)
    if preserved != text or "\n" in preserved:
        return preserved
    return _compact_answer_text(text)
