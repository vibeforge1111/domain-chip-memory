from __future__ import annotations

import re

from .contracts import NormalizedBenchmarkSample, NormalizedSession
from .memory_extraction import ObservationEntry


def session_lookup(sample: NormalizedBenchmarkSample) -> dict[str, NormalizedSession]:
    return {session.session_id: session for session in sample.sessions}


def dedupe_observations(entries: list[ObservationEntry]) -> list[ObservationEntry]:
    deduped: list[ObservationEntry] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for entry in entries:
        if entry.predicate == "raw_turn":
            entity_key = entry.observation_id
        else:
            entity_key = str(entry.metadata.get("entity_key", "")).strip()
            if entity_key and entry.predicate in {"activity", "trip_duration"} and entry.timestamp:
                entity_key = f"{entity_key}|{entry.timestamp}"
            if not entity_key:
                entity_key = entry.text.strip().lower() or entry.observation_id
        key = (entry.subject, entry.predicate, entity_key)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(entry)
    return deduped


def candidate_sentences(text: str) -> list[str]:
    candidates = [
        re.sub(r"\s+", " ", sentence).strip(" .,:;!?")
        for sentence in re.split(r"(?<=[.!?])\s+", text.strip())
    ]
    return [candidate for candidate in candidates if candidate]
