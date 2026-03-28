from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .contracts import JsonDict, NormalizedBenchmarkSample, NormalizedTurn


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


def _turn_order_key(turn_ids: list[str]) -> tuple[int, str]:
    first_turn_id = turn_ids[0] if turn_ids else ""
    match = re.search(r"(\d+)(?!.*\d)", first_turn_id)
    if match:
        return int(match.group(1)), first_turn_id
    return 10**9, first_turn_id


def _observation_topic_tokens(observation: ObservationEntry) -> set[str]:
    basis = " ".join(
        part
        for part in (
            observation.subject,
            observation.predicate.replace("_", " "),
            str(observation.metadata.get("value", "")),
            str(observation.metadata.get("source_text", "")),
        )
        if part
    )
    return set(_tokenize(basis))


def _annotate_topic_continuity(observations: list[ObservationEntry]) -> list[ObservationEntry]:
    if not observations:
        return observations

    ordered = sorted(
        observations,
        key=lambda entry: (entry.session_id, *_turn_order_key(entry.turn_ids), entry.observation_id),
    )
    topic_members: dict[str, list[ObservationEntry]] = {}
    topic_counter_by_session: dict[str, int] = {}
    topic_id_by_observation: dict[str, str] = {}
    current_by_session: dict[str, dict[str, Any]] = {}

    for observation in ordered:
        session_id = observation.session_id
        tokens = _observation_topic_tokens(observation)
        turn_index, _ = _turn_order_key(observation.turn_ids)
        entity_key = str(observation.metadata.get("entity_key", ""))
        current = current_by_session.get(session_id)
        topic_id: str | None = None

        if current is not None:
            turn_gap = max(0, turn_index - int(current["last_turn_index"]))
            token_overlap = len(tokens.intersection(current["tokens"]))
            same_subject = observation.subject == current["subject"]
            same_predicate = observation.predicate == current["predicate"]
            same_entity = bool(entity_key) and entity_key == current["entity_key"]
            if turn_gap <= 2 and (
                same_entity
                or token_overlap >= 2
                or (same_subject and token_overlap >= 1)
                or same_predicate
            ):
                topic_id = str(current["topic_id"])

        if topic_id is None:
            topic_counter_by_session[session_id] = topic_counter_by_session.get(session_id, 0) + 1
            topic_id = f"{session_id}:topic:{topic_counter_by_session[session_id]}"

        topic_id_by_observation[observation.observation_id] = topic_id
        topic_members.setdefault(topic_id, []).append(observation)
        current_by_session[session_id] = {
            "topic_id": topic_id,
            "tokens": tokens if current is None or topic_id != current.get("topic_id") else current["tokens"].union(tokens),
            "last_turn_index": turn_index,
            "subject": observation.subject,
            "predicate": observation.predicate,
            "entity_key": entity_key,
        }

    topic_metadata: dict[str, JsonDict] = {}
    for topic_id, members in topic_members.items():
        sorted_members = sorted(
            members,
            key=lambda entry: (_turn_order_key(entry.turn_ids), entry.observation_id),
        )
        representative_texts: list[str] = []
        for member in sorted_members:
            if member.text not in representative_texts:
                representative_texts.append(member.text)
            if len(representative_texts) >= 2:
                break
        topic_metadata[topic_id] = {
            "topic_summary": " / ".join(representative_texts),
            "topic_turn_ids": [turn_id for member in sorted_members for turn_id in member.turn_ids],
            "topic_member_count": len(sorted_members),
        }

    annotated: list[ObservationEntry] = []
    for observation in observations:
        topic_id = topic_id_by_observation.get(observation.observation_id)
        metadata = dict(observation.metadata)
        if topic_id is not None:
            metadata["topic_id"] = topic_id
            metadata.update(topic_metadata[topic_id])
        annotated.append(
            ObservationEntry(
                observation_id=observation.observation_id,
                subject=observation.subject,
                predicate=observation.predicate,
                text=observation.text,
                session_id=observation.session_id,
                turn_ids=observation.turn_ids,
                timestamp=observation.timestamp,
                metadata=metadata,
            )
        )
    return annotated


def build_observation_log(
    sample: NormalizedBenchmarkSample,
    *,
    extract_memory_atoms: Callable[[NormalizedBenchmarkSample], list[MemoryAtom]],
    observation_surface_text: Callable[[str, str, str, str], str],
) -> list[ObservationEntry]:
    observations: list[ObservationEntry] = []
    for atom in extract_memory_atoms(sample):
        if atom.predicate == "raw_turn":
            speaker = _subject_to_surface(atom.subject)
            if atom.timestamp:
                text = f"On {atom.timestamp}, {speaker} said: {atom.source_text}"
            else:
                text = f"{speaker} said: {atom.source_text}"
            image_evidence: list[str] = []
            blip_caption = atom.metadata.get("blip_caption")
            if blip_caption:
                image_evidence.append(f"image_caption: {blip_caption}")
            search_query = atom.metadata.get("search_query")
            if search_query:
                image_evidence.append(f"image_query: {search_query}")
            img_url = atom.metadata.get("img_url")
            if img_url:
                if isinstance(img_url, list) and img_url:
                    image_evidence.append(f"image_url: {img_url[0]}")
                elif isinstance(img_url, str):
                    image_evidence.append(f"image_url: {img_url}")
            if image_evidence:
                text = f"{text} Image evidence: {'; '.join(image_evidence)}"
        else:
            text = observation_surface_text(atom.subject, atom.predicate, atom.value, atom.source_text)
            if atom.timestamp and atom.predicate in {
                "school_event_time",
                "support_network_meetup_time",
                "charity_race_time",
                "museum_visit_time",
                "sunrise_paint_time",
                "camping_plan_time",
                "pottery_class_signup_time",
            }:
                text = f"On {atom.timestamp}, {text}"
        observations.append(
            ObservationEntry(
                observation_id=f"{atom.atom_id}:obs",
                subject=atom.subject,
                predicate=atom.predicate,
                text=text,
                session_id=atom.session_id,
                turn_ids=[atom.turn_id],
                timestamp=atom.timestamp,
                metadata={"source_text": atom.source_text, "value": atom.value, **atom.metadata},
            )
        )
    return _annotate_topic_continuity(observations)


def build_event_calendar(
    sample: NormalizedBenchmarkSample,
    *,
    extract_memory_atoms: Callable[[NormalizedBenchmarkSample], list[MemoryAtom]],
    observation_surface_text: Callable[[str, str, str, str], str],
) -> list[EventCalendarEntry]:
    events: list[EventCalendarEntry] = []
    for atom in extract_memory_atoms(sample):
        if atom.predicate in {"raw_turn", "state_deletion"}:
            continue
        text = observation_surface_text(atom.subject, atom.predicate, atom.value, atom.source_text)
        events.append(
            EventCalendarEntry(
                event_id=f"{atom.atom_id}:event",
                subject=atom.subject,
                predicate=atom.predicate,
                text=text,
                session_id=atom.session_id,
                turn_ids=[atom.turn_id],
                timestamp=atom.timestamp,
                metadata={"source_text": atom.source_text, "value": atom.value, **atom.metadata},
            )
        )
    return sorted(events, key=lambda entry: (entry.timestamp or "", entry.event_id))


__all__ = [
    "EventCalendarEntry",
    "MemoryAtom",
    "ObservationEntry",
    "_annotate_topic_continuity",
    "_observation_topic_tokens",
    "_canonical_subject",
    "_normalize_token",
    "_normalize_value",
    "_subject_to_surface",
    "_token_bigrams",
    "_tokenize",
    "_turn_order_key",
    "build_event_calendar",
    "build_observation_log",
]
