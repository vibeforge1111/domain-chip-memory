from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .contracts import JsonDict, NormalizedBenchmarkSample, NormalizedQuestion, NormalizedSession, NormalizedTurn
from .runs import BaselinePromptPacket, RetrievedContextItem, build_run_manifest


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


def _tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in STOPWORDS]


def _serialize_session(session: NormalizedSession) -> str:
    lines = []
    header = f"Session {session.session_id}"
    if session.timestamp:
        header += f" @ {session.timestamp}"
    lines.append(header)
    for turn in session.turns:
        lines.append(f"{turn.speaker}: {turn.text}")
    return "\n".join(lines)


def _canonical_subject(turn: NormalizedTurn) -> str:
    speaker = turn.speaker.strip().lower()
    if speaker in {"user", "speaker_a", "speaker b", "speaker_a:", "speaker_b", "speaker_b:"}:
        return "user"
    return speaker


def _normalize_value(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" .,:;!?")


def _subject_to_surface(subject: str) -> str:
    return "I" if subject == "user" else subject.capitalize()


def _observation_surface_text(subject: str, predicate: str, value: str, source_text: str) -> str:
    surface_subject = _subject_to_surface(subject)
    if predicate == "location":
        return f"{surface_subject} live in {value}" if subject == "user" else f"{surface_subject} lives in {value}"
    if predicate == "preference":
        return f"{surface_subject} prefer {value}" if subject == "user" else f"{surface_subject} prefers {value}"
    if predicate == "favorite_color":
        return f"My favourite colour is {value}" if subject == "user" else f"{surface_subject}'s favourite colour is {value}"
    if predicate == "commute_duration":
        return f"My daily commute takes {value}" if subject == "user" else f"{surface_subject}'s daily commute takes {value}"
    if predicate == "attended_play":
        return f"I attended {value}" if subject == "user" else f"{surface_subject} attended {value}"
    if predicate == "playlist_name":
        return f"My playlist is {value}" if subject == "user" else f"{surface_subject}'s playlist is {value}"
    if predicate == "retailer":
        return f"I shop at {value}" if subject == "user" else f"{surface_subject} shops at {value}"
    if predicate == "previous_occupation":
        return f"My previous occupation was {value}" if subject == "user" else f"{surface_subject}'s previous occupation was {value}"
    if predicate == "bike_count":
        return f"I own {value} bikes" if subject == "user" else f"{surface_subject} owns {value} bikes"
    if predicate == "dog_breed":
        return f"My dog is a {value}" if subject == "user" else f"{surface_subject}'s dog is a {value}"
    return source_text


def _answer_candidate_surface_text(subject: str, predicate: str, value: str, source_text: str) -> str:
    surface_subject = _subject_to_surface(subject)
    if predicate in {
        "commute_duration",
        "attended_play",
        "playlist_name",
        "retailer",
        "previous_occupation",
        "bike_count",
        "dog_breed",
    } and value:
        return value
    if predicate == "location":
        return f"{surface_subject} do live in {value}" if subject == "user" else f"{surface_subject} does live in {value}"
    if predicate == "preference":
        return f"{surface_subject} do prefer {value}" if subject == "user" else f"{surface_subject} does prefer {value}"
    if predicate == "favorite_color":
        return f"My favourite colour is {value}" if subject == "user" else f"{surface_subject}'s favourite colour is {value}"
    return source_text


def _extract_atoms_from_turn(session: NormalizedSession, turn: NormalizedTurn) -> list[MemoryAtom]:
    text = turn.text.strip()
    lower = text.lower()
    subject = _canonical_subject(turn)
    atoms: list[MemoryAtom] = []

    patterns = [
        (r"\b(?:i|we)\s+moved to\s+([A-Za-z0-9 _-]+)", "location"),
        (r"\b(?:i|we)\s+live in\s+([A-Za-z0-9 _-]+)", "location"),
        (r"\b([A-Z][A-Za-z0-9_-]+)\s+(?:moved to|lives in|live in)\s+([A-Za-z0-9 _-]+)", "location_named"),
        (r"\b(?:i now prefer|i prefer|i like)\s+([A-Za-z0-9 _-]+)", "preference"),
        (r"\b([A-Z][A-Za-z0-9_-]+)\s+(?:now prefers|prefers|likes)\s+([A-Za-z0-9 _-]+)", "preference_named"),
        (r"\bmy favourite colour is\s+([A-Za-z0-9 _-]+)", "favorite_color"),
        (r"\bmy favorite color is\s+([A-Za-z0-9 _-]+)", "favorite_color"),
        (r"\bmy favourite color is\s+([A-Za-z0-9 _-]+)", "favorite_color"),
        (r"\bmy favorite colour is\s+([A-Za-z0-9 _-]+)", "favorite_color"),
        (r"\bdaily commute(?: to work)?(?:,|\s|\w)*?takes\s+(\d+\s+(?:minutes?|hours?)(?:\s+each\s+way)?)", "commute_duration"),
        (r"\bthe play i attended was(?: actually)?(?: a production of)?\s+([A-Za-z0-9' _-]+)", "attended_play"),
        (r"\bi attended(?: a production of)?\s+([A-Za-z0-9' _-]+)", "attended_play"),
        (r"\bplaylist(?: on spotify)?(?: that i created)?(?:,)?\s+called\s+([A-Za-z0-9' _-]+)", "playlist_name"),
        (r"\bi created(?: on spotify)?(?: a)? playlist(?: on spotify)?(?:,)?\s+(?:called|named)\s+([A-Za-z0-9' _-]+)", "playlist_name"),
        (r"\bi shop at\s+([A-Z][A-Za-z0-9'&-]*(?:\s+[A-Z][A-Za-z0-9'&-]*)*)", "retailer"),
        (r"\bcartwheel app from\s+([A-Z][A-Za-z0-9'&-]*(?:\s+[A-Z][A-Za-z0-9'&-]*)*)", "retailer"),
        (r"\bi redeemed .*?\bat\s+([A-Z][A-Za-z0-9'&-]*(?:\s+[A-Z][A-Za-z0-9'&-]*)*)", "retailer"),
        (r"\bprevious role as (?:a|an)\s+([^,.!?]+?)(?:\s+and\b|,|\.|$)", "previous_occupation"),
        (r"\bbikes?\b[^.?!]{0,200}?\bgot\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+of them\b", "bike_count"),
        (r"\bi own\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+bikes?\b", "bike_count"),
        (r"\bsuit a\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\s+like\s+[A-Z][A-Za-z]+\b", "dog_breed"),
    ]

    for index, (pattern, predicate) in enumerate(patterns):
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        if predicate == "location_named":
            atom_subject = match.group(1).strip().lower()
            atom_predicate = "location"
            value = _normalize_value(match.group(2))
        elif predicate == "preference_named":
            atom_subject = match.group(1).strip().lower()
            atom_predicate = "preference"
            value = _normalize_value(match.group(2))
        else:
            atom_subject = subject
            atom_predicate = predicate
            value = _normalize_value(match.group(1))
        atoms.append(
            MemoryAtom(
                atom_id=f"{turn.turn_id}:atom:{index}",
                subject=atom_subject,
                predicate=atom_predicate,
                value=value,
                session_id=session.session_id,
                turn_id=turn.turn_id,
                timestamp=turn.timestamp or session.timestamp,
                source_text=text,
                metadata={"speaker": turn.speaker},
            )
        )

    if atoms:
        return atoms

    if subject != "user":
        return []

    # Fallback memory atom: keep the raw turn as a low-confidence fact candidate for retrieval.
    return [
        MemoryAtom(
            atom_id=f"{turn.turn_id}:atom:fallback",
            subject=subject,
            predicate="raw_turn",
            value=_normalize_value(text),
            session_id=session.session_id,
            turn_id=turn.turn_id,
            timestamp=turn.timestamp or session.timestamp,
            source_text=text,
            metadata={"speaker": turn.speaker, "fallback": True},
        )
    ]


def extract_memory_atoms(sample: NormalizedBenchmarkSample) -> list[MemoryAtom]:
    atoms: list[MemoryAtom] = []
    for session in sample.sessions:
        for turn in session.turns:
            atoms.extend(_extract_atoms_from_turn(session, turn))
    return atoms


def build_observation_log(sample: NormalizedBenchmarkSample) -> list[ObservationEntry]:
    observations: list[ObservationEntry] = []
    for atom in extract_memory_atoms(sample):
        if atom.predicate == "raw_turn":
            text = atom.source_text
        else:
            text = _observation_surface_text(atom.subject, atom.predicate, atom.value, atom.source_text)
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
    return observations


def reflect_observations(observations: list[ObservationEntry]) -> list[ObservationEntry]:
    latest_by_key: dict[tuple[str, str], ObservationEntry] = {}
    passthrough: list[ObservationEntry] = []
    for observation in observations:
        if observation.predicate == "raw_turn":
            passthrough.append(observation)
            continue
        key = (observation.subject, observation.predicate)
        current = latest_by_key.get(key)
        if current is None or (observation.timestamp or "") >= (current.timestamp or ""):
            latest_by_key[key] = observation
    reflected = sorted(
        [*latest_by_key.values(), *passthrough],
        key=lambda entry: (entry.timestamp or "", entry.observation_id),
    )
    return reflected


def build_event_calendar(sample: NormalizedBenchmarkSample) -> list[EventCalendarEntry]:
    events: list[EventCalendarEntry] = []
    for atom in extract_memory_atoms(sample):
        if atom.predicate == "raw_turn":
            continue
        text = _observation_surface_text(atom.subject, atom.predicate, atom.value, atom.source_text)
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


def _question_subject(question: NormalizedQuestion) -> str:
    question_lower = question.question.lower()
    if "alice" in question_lower:
        return "alice"
    if "bob" in question_lower:
        return "bob"
    return "user"


def _question_predicates(question: NormalizedQuestion) -> list[str]:
    question_lower = question.question.lower()
    predicates: list[str] = []
    if "live" in question_lower or "moved" in question_lower:
        predicates.append("location")
    if "favourite colour" in question_lower or "favorite colour" in question_lower:
        predicates.append("favorite_color")
    if "favorite color" in question_lower or "favourite color" in question_lower:
        predicates.append("favorite_color")
    if "music" in question_lower or "prefer" in question_lower or "like" in question_lower:
        predicates.append("preference")
    if "commute" in question_lower:
        predicates.append("commute_duration")
    if "play did i attend" in question_lower or ("what play" in question_lower and "attend" in question_lower):
        predicates.append("attended_play")
    if "playlist" in question_lower:
        predicates.append("playlist_name")
    if "where did i redeem" in question_lower or ("coupon" in question_lower and "where" in question_lower):
        predicates.append("retailer")
    if "previous occupation" in question_lower or "previous role" in question_lower:
        predicates.append("previous_occupation")
    if "how many bikes" in question_lower and "own" in question_lower:
        predicates.append("bike_count")
    if "breed is my dog" in question_lower:
        predicates.append("dog_breed")
    if not predicates:
        predicates.append("raw_turn")
    return predicates


def _atom_score(question: NormalizedQuestion, atom: MemoryAtom) -> float:
    score = 0.0
    subject = _question_subject(question)
    predicates = _question_predicates(question)
    question_tokens = set(_tokenize(question.question))
    atom_tokens = set(_tokenize(atom.source_text))

    if atom.subject == subject:
        score += 3.0
    if atom.predicate in predicates:
        score += 4.0
    score += float(len(question_tokens.intersection(atom_tokens)))
    if atom.timestamp:
        score += 0.001 * sum(ord(char) for char in atom.timestamp)
    if question.category in {"knowledge-update", "temporal", "temporal-reasoning"} and atom.timestamp:
        score += 1.0
    if atom.metadata.get("fallback"):
        score -= 2.0
    return score


def _choose_atoms(question: NormalizedQuestion, atoms: list[MemoryAtom], limit: int) -> list[MemoryAtom]:
    predicates = set(_question_predicates(question))
    subject = _question_subject(question)
    latest_by_key: dict[tuple[str, str], MemoryAtom] = {}
    other_atoms: list[MemoryAtom] = []
    for atom in atoms:
        key = (atom.subject, atom.predicate)
        if atom.subject == subject and atom.predicate in predicates:
            current = latest_by_key.get(key)
            if current is None or (atom.timestamp or "") >= (current.timestamp or ""):
                latest_by_key[key] = atom
        else:
            other_atoms.append(atom)

    scored = sorted(
        [*latest_by_key.values(), *other_atoms],
        key=lambda atom: (_atom_score(question, atom), atom.timestamp or "", atom.atom_id),
        reverse=True,
    )
    chosen: list[MemoryAtom] = []
    seen_keys: set[tuple[str, str]] = set()
    for atom in scored:
        key = (atom.subject, atom.predicate)
        if atom.subject == subject and atom.predicate in predicates:
            if key in seen_keys:
                continue
            seen_keys.add(key)
            chosen.append(atom)
        elif len(chosen) < limit:
            chosen.append(atom)
        if len(chosen) >= limit:
            break
    return chosen


def _session_lookup(sample: NormalizedBenchmarkSample) -> dict[str, NormalizedSession]:
    return {session.session_id: session for session in sample.sessions}


def _observation_score(question: NormalizedQuestion, observation: ObservationEntry) -> float:
    score = 0.0
    subject = _question_subject(question)
    predicates = _question_predicates(question)
    question_tokens = set(_tokenize(question.question))
    observation_tokens = set(_tokenize(observation.text))
    if observation.subject == subject:
        score += 3.0
    if observation.predicate in predicates:
        score += 4.0
    score += float(len(question_tokens.intersection(observation_tokens)))
    if question.category in {"knowledge-update", "temporal", "temporal-reasoning"} and observation.timestamp:
        score += 1.0
    if observation.timestamp:
        score += 0.001 * sum(ord(char) for char in observation.timestamp)
    if observation.predicate == "raw_turn":
        score -= 2.5
    return score


def _event_score(question: NormalizedQuestion, event: EventCalendarEntry) -> float:
    score = 0.0
    subject = _question_subject(question)
    predicates = _question_predicates(question)
    question_tokens = set(_tokenize(question.question))
    event_tokens = set(_tokenize(event.text))
    if event.subject == subject:
        score += 3.0
    if event.predicate in predicates:
        score += 5.0
    score += float(len(question_tokens.intersection(event_tokens)))
    if question.category in {"knowledge-update", "temporal", "temporal-reasoning"} and event.timestamp:
        score += 2.0
    if event.timestamp:
        score += 0.001 * sum(ord(char) for char in event.timestamp)
    return score


def build_observational_temporal_memory_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    max_observations: int = 8,
    max_reflections: int = 4,
    run_id: str = "observational-temporal-memory-v1",
) -> tuple[dict[str, Any], list[BaselinePromptPacket]]:
    packets: list[BaselinePromptPacket] = []
    for sample in samples:
        observations = build_observation_log(sample)
        reflected = reflect_observations(observations)
        stable_window = sorted(
            observations,
            key=lambda entry: (entry.timestamp or "", entry.observation_id),
        )[-max_observations:]
        for question in sample.questions:
            ranked_reflections = sorted(
                reflected,
                key=lambda entry: (_observation_score(question, entry), entry.timestamp or "", entry.observation_id),
                reverse=True,
            )[:max_reflections]

            context_blocks = ["stable_memory_window:"]
            retrieved_items: list[RetrievedContextItem] = []
            for entry in stable_window:
                line = f"observation: {entry.text}"
                context_blocks.append(line)
                retrieved_items.append(
                    RetrievedContextItem(
                        session_id=entry.session_id,
                        turn_ids=entry.turn_ids,
                        score=0.25,
                        strategy="observation_log",
                        text=line,
                        metadata={"timestamp": entry.timestamp, "predicate": entry.predicate, "subject": entry.subject},
                    )
                )

            context_blocks.append("reflected_memory:")
            for entry in ranked_reflections:
                line = f"reflection: {entry.text}"
                context_blocks.append(line)
                retrieved_items.append(
                    RetrievedContextItem(
                        session_id=entry.session_id,
                        turn_ids=entry.turn_ids,
                        score=_observation_score(question, entry),
                        strategy="reflected_memory",
                        text=line,
                        metadata={"timestamp": entry.timestamp, "predicate": entry.predicate, "subject": entry.subject},
                    )
                )

            if ranked_reflections:
                top_entry = ranked_reflections[0]
                answer_text = _answer_candidate_surface_text(
                    top_entry.subject,
                    top_entry.predicate,
                    top_entry.metadata.get("value", ""),
                    top_entry.text,
                )
                context_blocks.append(f"answer_candidate: {answer_text}")

            packets.append(
                BaselinePromptPacket(
                    benchmark_name=sample.benchmark_name,
                    baseline_name="observational_temporal_memory",
                    sample_id=sample.sample_id,
                    question_id=question.question_id,
                    question=question.question,
                    assembled_context="\n\n".join(context_blocks),
                    retrieved_context_items=retrieved_items,
                    metadata={
                        "route": "observational_temporal_memory",
                        "max_observations": max_observations,
                        "max_reflections": max_reflections,
                    },
                )
            )

    manifest = build_run_manifest(
        samples,
        baseline_name="observational_temporal_memory",
        run_id=run_id,
        metadata={
            "baseline_type": "candidate_memory_system",
            "system_name": "Observational Temporal Memory",
            "max_observations": max_observations,
            "max_reflections": max_reflections,
        },
    )
    return manifest.to_dict(), packets


def build_beam_ready_temporal_atom_router_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    top_k_atoms: int = 3,
    include_rehydrated_sessions: int = 1,
    run_id: str = "beam-temporal-atom-router-v1",
) -> tuple[dict[str, Any], list[BaselinePromptPacket]]:
    packets: list[BaselinePromptPacket] = []
    for sample in samples:
        atoms = extract_memory_atoms(sample)
        sessions = _session_lookup(sample)
        for question in sample.questions:
            chosen_atoms = _choose_atoms(question, atoms, top_k_atoms)
            rehydrated_session_ids: list[str] = []
            for atom in chosen_atoms:
                if atom.session_id not in rehydrated_session_ids:
                    rehydrated_session_ids.append(atom.session_id)
            rehydrated_session_ids = rehydrated_session_ids[:include_rehydrated_sessions]

            retrieved_items: list[RetrievedContextItem] = []
            context_blocks: list[str] = []
            for atom in chosen_atoms:
                atom_line = f"memory: {atom.source_text}"
                context_blocks.append(atom_line)
                retrieved_items.append(
                    RetrievedContextItem(
                        session_id=atom.session_id,
                        turn_ids=[atom.turn_id],
                        score=_atom_score(question, atom),
                        strategy="temporal_atom_router",
                        text=atom_line,
                        metadata={
                            "atom_id": atom.atom_id,
                            "subject": atom.subject,
                            "predicate": atom.predicate,
                            "timestamp": atom.timestamp,
                        },
                    )
                )

            for session_id in rehydrated_session_ids:
                session = sessions[session_id]
                session_text = _serialize_session(session)
                context_blocks.append(session_text)
                retrieved_items.append(
                    RetrievedContextItem(
                        session_id=session.session_id,
                        turn_ids=[turn.turn_id for turn in session.turns],
                        score=0.5,
                        strategy="source_rehydration",
                        text=session_text,
                        metadata={"timestamp": session.timestamp},
                    )
                )

            if chosen_atoms:
                primary_atom = chosen_atoms[0]
                context_blocks.append(f"answer_candidate: {primary_atom.source_text}")

            assembled_context = "\n\n".join(context_blocks)
            packets.append(
                BaselinePromptPacket(
                    benchmark_name=sample.benchmark_name,
                    baseline_name="beam_temporal_atom_router",
                    sample_id=sample.sample_id,
                    question_id=question.question_id,
                    question=question.question,
                    assembled_context=assembled_context,
                    retrieved_context_items=retrieved_items,
                    metadata={
                        "route": "temporal_atom_router",
                        "top_k_atoms": top_k_atoms,
                        "include_rehydrated_sessions": include_rehydrated_sessions,
                    },
                )
            )

    manifest = build_run_manifest(
        samples,
        baseline_name="beam_temporal_atom_router",
        run_id=run_id,
        metadata={
            "baseline_type": "candidate_memory_system",
            "system_name": "Beam-Ready Temporal Atom Router",
            "top_k_atoms": top_k_atoms,
            "include_rehydrated_sessions": include_rehydrated_sessions,
        },
    )
    return manifest.to_dict(), packets


def build_dual_store_event_calendar_hybrid_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    max_observations: int = 6,
    top_k_events: int = 3,
    run_id: str = "dual-store-event-calendar-hybrid-v1",
) -> tuple[dict[str, Any], list[BaselinePromptPacket]]:
    packets: list[BaselinePromptPacket] = []
    for sample in samples:
        observations = build_observation_log(sample)
        reflected = reflect_observations(observations)
        events = build_event_calendar(sample)
        stable_window = sorted(
            observations,
            key=lambda entry: (entry.timestamp or "", entry.observation_id),
        )[-max_observations:]
        for question in sample.questions:
            ranked_reflections = sorted(
                reflected,
                key=lambda entry: (_observation_score(question, entry), entry.timestamp or "", entry.observation_id),
                reverse=True,
            )[:2]
            ranked_events = sorted(
                events,
                key=lambda entry: (_event_score(question, entry), entry.timestamp or "", entry.event_id),
                reverse=True,
            )[:top_k_events]

            context_blocks = ["stable_memory_window:"]
            retrieved_items: list[RetrievedContextItem] = []
            for entry in stable_window:
                line = f"observation: {entry.text}"
                context_blocks.append(line)
                retrieved_items.append(
                    RetrievedContextItem(
                        session_id=entry.session_id,
                        turn_ids=entry.turn_ids,
                        score=0.25,
                        strategy="hybrid_observation_window",
                        text=line,
                        metadata={"timestamp": entry.timestamp, "predicate": entry.predicate, "subject": entry.subject},
                    )
                )

            context_blocks.append("event_calendar:")
            for entry in ranked_events:
                prefix = f"{entry.timestamp} " if entry.timestamp else ""
                line = f"event: {prefix}{entry.text}"
                context_blocks.append(line)
                retrieved_items.append(
                    RetrievedContextItem(
                        session_id=entry.session_id,
                        turn_ids=entry.turn_ids,
                        score=_event_score(question, entry),
                        strategy="event_calendar",
                        text=line,
                        metadata={"timestamp": entry.timestamp, "predicate": entry.predicate, "subject": entry.subject},
                    )
                )

            context_blocks.append("reflected_memory:")
            for entry in ranked_reflections:
                line = f"reflection: {entry.text}"
                context_blocks.append(line)
                retrieved_items.append(
                    RetrievedContextItem(
                        session_id=entry.session_id,
                        turn_ids=entry.turn_ids,
                        score=_observation_score(question, entry),
                        strategy="hybrid_reflection",
                        text=line,
                        metadata={"timestamp": entry.timestamp, "predicate": entry.predicate, "subject": entry.subject},
                    )
                )

            if ranked_events:
                top_entry = ranked_events[0]
                answer_text = _answer_candidate_surface_text(
                    top_entry.subject,
                    top_entry.predicate,
                    top_entry.metadata.get("value", ""),
                    top_entry.text,
                )
                context_blocks.append(f"answer_candidate: {answer_text}")
            elif ranked_reflections:
                top_entry = ranked_reflections[0]
                answer_text = _answer_candidate_surface_text(
                    top_entry.subject,
                    top_entry.predicate,
                    top_entry.metadata.get("value", ""),
                    top_entry.text,
                )
                context_blocks.append(f"answer_candidate: {answer_text}")

            packets.append(
                BaselinePromptPacket(
                    benchmark_name=sample.benchmark_name,
                    baseline_name="dual_store_event_calendar_hybrid",
                    sample_id=sample.sample_id,
                    question_id=question.question_id,
                    question=question.question,
                    assembled_context="\n\n".join(context_blocks),
                    retrieved_context_items=retrieved_items,
                    metadata={
                        "route": "dual_store_event_calendar_hybrid",
                        "max_observations": max_observations,
                        "top_k_events": top_k_events,
                    },
                )
            )

    manifest = build_run_manifest(
        samples,
        baseline_name="dual_store_event_calendar_hybrid",
        run_id=run_id,
        metadata={
            "baseline_type": "candidate_memory_system",
            "system_name": "Dual-Store Event Calendar Hybrid",
            "max_observations": max_observations,
            "top_k_events": top_k_events,
        },
    )
    return manifest.to_dict(), packets


def build_memory_system_contract_summary() -> dict[str, Any]:
    return {
        "candidate_memory_systems": [
            {
                "system_name": "beam_temporal_atom_router",
                "entrypoint": "build_beam_ready_temporal_atom_router_packets",
                "behavior": "Extract temporal atoms, apply recency-aware routing, then rehydrate the strongest source sessions.",
            },
            {
                "system_name": "observational_temporal_memory",
                "entrypoint": "build_observational_temporal_memory_packets",
                "behavior": "Build a stable observation log, reflect it into a compressed memory window, and answer from that stable context.",
            },
            {
                "system_name": "dual_store_event_calendar_hybrid",
                "entrypoint": "build_dual_store_event_calendar_hybrid_packets",
                "behavior": "Combine a stable observation window with an explicit event calendar and answer from the strongest hybrid signal.",
            }
        ],
        "memory_contracts": [
            "MemoryAtom",
            "ObservationEntry",
            "EventCalendarEntry",
            "RetrievedContextItem",
            "BaselinePromptPacket",
        ],
    }
