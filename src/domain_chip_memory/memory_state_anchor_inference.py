from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime

from .contracts import NormalizedQuestion
from .memory_extraction import EventCalendarEntry, ObservationEntry


def infer_anchor_time_from_phrase(
    anchor_phrase: str,
    candidate_entries: list[ObservationEntry | EventCalendarEntry],
    *,
    include_location_entries: bool = False,
    parse_question_state_anchor: Callable[[str], tuple[datetime | None, datetime | None, datetime | None]],
    tokenize: Callable[[str], list[str]],
    token_bigrams: Callable[[str], set[tuple[str, str]]],
    parse_observation_anchor: Callable[[str], datetime | None],
) -> datetime | None:
    if not anchor_phrase.strip():
        return None

    anchor_phrase_lower = anchor_phrase.lower()
    target_anchor, target_start, target_end = parse_question_state_anchor(anchor_phrase_lower)
    normalized_anchor_phrase = re.sub(
        r"\s+at\s+\d{1,2}(?::\d{2})?\s*[ap]m\s+on\s+\d{1,2}\s+"
        r"(?:january|february|march|april|may|june|july|august|september|october|november|december)"
        r"\s+\d{4}\b",
        "",
        anchor_phrase_lower,
    )
    normalized_anchor_phrase = re.sub(
        r"\s+on\s+\d{1,2}\s+"
        r"(?:january|february|march|april|may|june|july|august|september|october|november|december)"
        r"\s+\d{4}\b",
        "",
        normalized_anchor_phrase,
    )
    normalized_anchor_phrase = re.sub(
        r"\s+in\s+"
        r"(?:january|february|march|april|may|june|july|august|september|october|november|december)"
        r"\s+\d{4}\b",
        "",
        normalized_anchor_phrase,
    )
    normalized_anchor_phrase = re.sub(r"\s+", " ", normalized_anchor_phrase).strip()

    question_tokens = set(tokenize(normalized_anchor_phrase or anchor_phrase_lower))
    question_bigrams = token_bigrams(normalized_anchor_phrase or anchor_phrase_lower)
    location_anchor_phrase = bool(
        include_location_entries
        and re.search(r"\b(?:live|lived|living|move|moved|moving)\b", normalized_anchor_phrase or anchor_phrase_lower)
    )
    best_anchor: datetime | None = None
    best_score: tuple[int, int, int] | None = None

    for entry in candidate_entries:
        if entry.predicate == "location" and not include_location_entries:
            continue
        anchor = parse_observation_anchor(entry.timestamp or "")
        if anchor is None:
            continue
        if target_anchor is not None and anchor != target_anchor:
            continue
        if target_start is not None and target_end is not None and not (target_start <= anchor < target_end):
            continue
        entry_corpus = " ".join(
            part
            for part in (
                entry.text,
                str(entry.metadata.get("source_text", "")),
                str(entry.metadata.get("value", "")),
            )
            if part
        )
        entry_tokens = set(tokenize(entry_corpus))
        token_overlap = len(question_tokens.intersection(entry_tokens))
        value_tokens = set(tokenize(str(entry.metadata.get("value", ""))))
        location_value_overlap = len(question_tokens.intersection(value_tokens))
        if location_anchor_phrase and entry.predicate == "location" and location_value_overlap:
            token_overlap = max(token_overlap, 2)
        if token_overlap == 0:
            continue
        bigram_overlap = len(question_bigrams.intersection(token_bigrams(entry_corpus)))
        score = (bigram_overlap, token_overlap, len(entry_corpus))
        if best_score is None or score > best_score:
            best_score = score
            best_anchor = anchor

    if best_score is None:
        return None
    if best_score[0] == 0 and best_score[1] < 2:
        return None
    return best_anchor


def infer_event_anchored_state_time(
    question: NormalizedQuestion,
    candidate_entries: list[ObservationEntry | EventCalendarEntry],
    *,
    infer_anchor_time_from_phrase: Callable[..., datetime | None],
) -> datetime | None:
    question_lower = question.question.lower()
    patterns = (
        r"^where (?:did i live|was i living) when\s+(.+)$",
        r"^what did i prefer when\s+(.+)$",
        r"^what was my favou?rite colou?r when\s+(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, question_lower)
        if not match:
            continue
        anchor_phrase = match.group(1).strip().rstrip(".!?")
        if anchor_phrase:
            return infer_anchor_time_from_phrase(
                anchor_phrase,
                candidate_entries,
                include_location_entries=True,
            )
    return None
