from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .contracts import JsonDict, NormalizedTurn


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "do",
    "does",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "now",
    "of",
    "on",
    "or",
    "the",
    "to",
    "was",
    "what",
    "when",
    "where",
    "who",
    "why",
    "you",
}

IRREGULAR_TOKEN_NORMALIZATIONS = {
    "went": "go",
    "gone": "go",
    "did": "do",
    "done": "do",
    "ran": "run",
    "sang": "sing",
    "bought": "buy",
    "brought": "bring",
    "thought": "think",
    "felt": "feel",
    "met": "meet",
    "took": "take",
    "taken": "take",
    "made": "make",
    "painted": "paint",
    "studied": "study",
    "moved": "move",
    "spoke": "speak",
}


@dataclass(frozen=True)
class MemoryAtom:
    atom_id: str
    subject: str
    predicate: str
    value: str
    session_id: str
    turn_id: str
    timestamp: str | None
    source_text: str
    metadata: JsonDict


@dataclass(frozen=True)
class ObservationEntry:
    observation_id: str
    subject: str
    predicate: str
    text: str
    session_id: str
    turn_ids: list[str]
    timestamp: str | None
    metadata: JsonDict


@dataclass(frozen=True)
class EventCalendarEntry:
    event_id: str
    subject: str
    predicate: str
    text: str
    session_id: str
    turn_ids: list[str]
    timestamp: str | None
    metadata: JsonDict


def _normalize_token(token: str) -> str:
    normalized = token.lower()
    if normalized in IRREGULAR_TOKEN_NORMALIZATIONS:
        return IRREGULAR_TOKEN_NORMALIZATIONS[normalized]
    if len(normalized) > 5 and normalized.endswith("ies"):
        return normalized[:-3] + "y"
    if len(normalized) > 5 and normalized.endswith("ing"):
        return normalized[:-3]
    if len(normalized) > 4 and normalized.endswith("ed"):
        stem = normalized[:-2]
        if len(stem) >= 2 and stem[-1] == stem[-2]:
            stem = stem[:-1]
        return stem
    if len(normalized) > 4 and normalized.endswith("es"):
        return normalized[:-2]
    if len(normalized) > 3 and normalized.endswith("s") and not normalized.endswith("ss"):
        return normalized[:-1]
    return normalized


def _tokenize(text: str) -> list[str]:
    return [
        normalized
        for token in re.findall(r"[a-z0-9]+", text.lower())
        for normalized in [_normalize_token(token)]
        if normalized not in STOPWORDS
    ]


def _token_bigrams(text: str) -> set[tuple[str, str]]:
    tokens = _tokenize(text)
    return set(zip(tokens, tokens[1:]))


def _canonical_subject(turn: NormalizedTurn) -> str:
    speaker = turn.speaker.strip().lower()
    if speaker in {"user", "speaker_a", "speaker b", "speaker_a:", "speaker_b", "speaker_b:"}:
        return "user"
    return speaker


def _normalize_value(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" .,:;!?")


def _subject_to_surface(subject: str) -> str:
    return "I" if subject == "user" else subject.capitalize()


__all__ = [
    "EventCalendarEntry",
    "MemoryAtom",
    "ObservationEntry",
    "_canonical_subject",
    "_normalize_token",
    "_normalize_value",
    "_subject_to_surface",
    "_token_bigrams",
    "_tokenize",
]
