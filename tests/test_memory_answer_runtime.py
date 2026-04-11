from __future__ import annotations

from domain_chip_memory.contracts import NormalizedQuestion
from domain_chip_memory.memory_answer_runtime import (
    _detect_profile_memory_query,
    _infer_profile_memory_answer,
)
from domain_chip_memory.memory_extraction import EventCalendarEntry, ObservationEntry


def _question(text: str) -> NormalizedQuestion:
    return NormalizedQuestion(
        question_id="q1",
        question=text,
        category="profile_query",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={},
    )


def _entry(
    *,
    observation_id: str,
    predicate: str,
    value: str,
    timestamp: str,
    text: str | None = None,
    source_text: str | None = None,
) -> ObservationEntry:
    return ObservationEntry(
        observation_id=observation_id,
        subject="user",
        predicate=predicate,
        text=text or value,
        session_id="s1",
        turn_ids=["t1"],
        timestamp=timestamp,
        metadata={
            "value": value,
            "source_text": source_text or text or value,
        },
    )


def _event_entry(
    *,
    event_id: str,
    predicate: str,
    value: str,
    timestamp: str,
) -> EventCalendarEntry:
    return EventCalendarEntry(
        event_id=event_id,
        subject="user",
        predicate=predicate,
        text=value,
        session_id="s1",
        turn_ids=["t1"],
        timestamp=timestamp,
        metadata={"value": value},
    )


def test_detect_profile_memory_query_maps_created_startup_to_founder_fact():
    assert _detect_profile_memory_query(_question("What startup did I create?")) == ("single_fact", "founder_of")


def test_detect_profile_memory_query_maps_mission_explanation_to_fact_explanation():
    assert _detect_profile_memory_query(_question("How do you know what I'm trying to do now?")) == (
        "fact_explanation",
        "current_mission",
    )


def test_infer_profile_memory_answer_returns_previous_city_for_history_prompt():
    answer = _infer_profile_memory_answer(
        _question("Where did I live before?"),
        [
            _entry(observation_id="o1", predicate="city", value="Dubai", timestamp="2026-04-10T00:00:00Z"),
            _entry(observation_id="o2", predicate="city", value="Abu Dhabi", timestamp="2026-04-10T01:00:00Z"),
        ],
    )

    assert answer == "Before Abu Dhabi, you lived in Dubai."


def test_infer_profile_memory_answer_returns_city_event_timeline():
    answer = _infer_profile_memory_answer(
        _question("What memory events do you have about where I live?"),
        [
            _entry(observation_id="o1", predicate="city", value="Dubai", timestamp="2026-04-10T00:00:00Z"),
            _entry(observation_id="o2", predicate="city", value="Abu Dhabi", timestamp="2026-04-10T01:00:00Z"),
        ],
    )

    assert answer == "I have 2 saved city events: Dubai then Abu Dhabi."


def test_infer_profile_memory_answer_accepts_event_calendar_entries_for_history_queries():
    answer = _infer_profile_memory_answer(
        _question("Where did I live before?"),
        [
            _event_entry(event_id="e1", predicate="city", value="Dubai", timestamp="2026-04-10T00:00:00Z"),
            _event_entry(event_id="e2", predicate="city", value="Abu Dhabi", timestamp="2026-04-10T01:00:00Z"),
        ],
    )

    assert answer == "Before Abu Dhabi, you lived in Dubai."


def test_infer_profile_memory_answer_returns_profile_fact_explanation_with_source_text():
    answer = _infer_profile_memory_answer(
        _question("How do you know what I'm trying to do now?"),
        [
            _entry(
                observation_id="o1",
                predicate="current_mission",
                value="survive the hack and revive the companies",
                text="survive the hack and revive the companies",
                source_text="I am trying to survive the hack and revive the companies.",
                timestamp="2026-04-10T00:00:00Z",
            ),
        ],
    )

    assert answer == (
        'Because I have a saved memory record from when you said: "I am trying to survive the hack and revive the companies." '
        "Your current mission is to survive the hack and revive the companies."
    )


def test_infer_profile_memory_answer_prefers_startup_fact_for_startup_explanation():
    answer = _infer_profile_memory_answer(
        _question("How do you know my startup?"),
        [
            _entry(
                observation_id="o1",
                predicate="startup_name",
                value="Seedify",
                text="Seedify",
                source_text="My startup is Seedify.",
                timestamp="2026-04-10T00:00:00Z",
            ),
            _entry(
                observation_id="o2",
                predicate="founder_of",
                value="Spark Swarm",
                text="Spark Swarm",
                source_text="I am the founder of Spark Swarm.",
                timestamp="2026-04-10T01:00:00Z",
            ),
        ],
    )

    assert answer == (
        'Because I have a saved memory record from when you said: "My startup is Seedify." '
        "Your startup is Seedify."
    )
