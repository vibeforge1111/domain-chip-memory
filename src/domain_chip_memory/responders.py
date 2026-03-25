from __future__ import annotations

import re

from .runs import BaselinePromptPacket


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" .,:;!?")


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


def heuristic_response(packet: BaselinePromptPacket) -> str:
    line = _last_matching_line(packet)
    if not line:
        return ""

    text = line.split(":", 1)[1].strip() if ":" in line else line.strip()
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
