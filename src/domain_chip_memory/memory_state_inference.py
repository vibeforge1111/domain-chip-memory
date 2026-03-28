from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime

from .contracts import NormalizedQuestion
from .memory_extraction import EventCalendarEntry, ObservationEntry
from .memory_state_anchor_inference import infer_anchor_time_from_phrase
from .memory_state_anchor_inference import infer_event_anchored_state_time


def has_ambiguous_relative_state_anchor(
    question: NormalizedQuestion,
    candidate_entries: list[ObservationEntry | EventCalendarEntry],
    *,
    extract_relative_state_anchor: Callable[[str], tuple[str | None, str, list[str]]],
    specialize_relative_state_anchor_phrase: Callable[..., str],
    has_ambiguous_generic_relative_anchor: Callable[[str, list[str], list[ObservationEntry | EventCalendarEntry]], bool],
) -> bool:
    question_lower = question.question.lower()
    mode, anchor_phrase, target_predicates = extract_relative_state_anchor(question_lower)
    if mode is None or not anchor_phrase or not target_predicates:
        return False
    specialized_anchor_phrase = specialize_relative_state_anchor_phrase(
        question,
        anchor_phrase,
        target_predicates,
        candidate_entries,
    )
    return has_ambiguous_generic_relative_anchor(
        specialized_anchor_phrase,
        target_predicates,
        candidate_entries,
    )


def has_referential_ambiguity(
    question: NormalizedQuestion,
    candidate_entries: list[ObservationEntry | EventCalendarEntry],
    *,
    question_predicates: Callable[[NormalizedQuestion], list[str]],
) -> bool:
    predicates = set(question_predicates(question))
    if not predicates:
        return False
    for entry in candidate_entries:
        if entry.predicate != "referential_ambiguity":
            continue
        target_predicates = {
            str(predicate).strip()
            for predicate in entry.metadata.get("target_predicates", [])
            if str(predicate).strip()
        }
        if predicates.intersection(target_predicates):
            return True
    return False


def dated_state_target_predicates(question: NormalizedQuestion) -> list[str]:
    question_lower = question.question.lower()
    if question_lower.startswith("what did i prefer"):
        return ["preference"]
    if question_lower.startswith(
        (
            "what was my favorite color",
            "what was my favourite color",
            "what was my favorite colour",
            "what was my favourite colour",
        )
    ):
        return ["favorite_color"]
    return ["location"]


def infer_relative_state_answer(
    question: NormalizedQuestion,
    candidate_entries: list[ObservationEntry | EventCalendarEntry],
    *,
    extract_relative_state_anchor: Callable[[str], tuple[str | None, str, list[str]]],
    specialize_relative_state_anchor_phrase: Callable[..., str],
    has_ambiguous_generic_relative_anchor: Callable[[str, list[str], list[ObservationEntry | EventCalendarEntry]], bool],
    infer_generic_relative_anchor_time: Callable[[str, list[str], list[ObservationEntry | EventCalendarEntry]], datetime | None],
    infer_anchor_time_from_phrase: Callable[..., datetime | None],
    parse_observation_anchor: Callable[[str], datetime | None],
    answer_candidate_surface_text: Callable[[str, str, str, str], str],
) -> str:
    question_lower = question.question.lower()
    mode, anchor_phrase, target_predicates = extract_relative_state_anchor(question_lower)
    if mode is None or not anchor_phrase or not target_predicates:
        return ""
    specialized_anchor_phrase = specialize_relative_state_anchor_phrase(
        question,
        anchor_phrase,
        target_predicates,
        candidate_entries,
    )
    if has_ambiguous_generic_relative_anchor(specialized_anchor_phrase, target_predicates, candidate_entries):
        return "unknown"

    anchor = infer_generic_relative_anchor_time(specialized_anchor_phrase, target_predicates, candidate_entries)
    if anchor is None:
        anchor = infer_anchor_time_from_phrase(
            anchor_phrase,
            candidate_entries,
            include_location_entries=True,
        )
    if anchor is None:
        return ""

    dated_states = sorted(
        [
            entry
            for entry in candidate_entries
            if entry.predicate in target_predicates and parse_observation_anchor(entry.timestamp or "")
        ],
        key=lambda entry: (
            parse_observation_anchor(entry.timestamp or ""),
            getattr(entry, "observation_id", getattr(entry, "event_id", "")),
        ),
    )
    selected: ObservationEntry | EventCalendarEntry | None = None
    if mode == "before":
        for entry in dated_states:
            state_anchor = parse_observation_anchor(entry.timestamp or "")
            if state_anchor is None:
                continue
            if state_anchor < anchor:
                selected = entry
            elif state_anchor >= anchor:
                break
    else:
        for entry in dated_states:
            state_anchor = parse_observation_anchor(entry.timestamp or "")
            if state_anchor is None:
                continue
            if state_anchor > anchor:
                selected = entry
                break

    if selected is None:
        return ""
    value = str(selected.metadata.get("value", "")).strip()
    if value:
        return value
    return answer_candidate_surface_text(
        selected.subject,
        selected.predicate,
        selected.metadata.get("value", ""),
        selected.text,
    )


def infer_dated_state_answer(
    question: NormalizedQuestion,
    candidate_entries: list[ObservationEntry | EventCalendarEntry],
    *,
    is_dated_state_question: Callable[[NormalizedQuestion], bool],
    dated_state_target_predicates: Callable[[NormalizedQuestion], list[str]],
    infer_event_anchored_state_time: Callable[[NormalizedQuestion, list[ObservationEntry | EventCalendarEntry]], datetime | None],
    parse_question_state_anchor: Callable[[str], tuple[datetime | None, datetime | None, datetime | None]],
    parse_observation_anchor: Callable[[str], datetime | None],
    answer_candidate_surface_text: Callable[[str, str, str, str], str],
) -> str:
    question_lower = question.question.lower()
    if not is_dated_state_question(question):
        return ""
    target_predicates = dated_state_target_predicates(question)
    if not target_predicates:
        return ""

    event_anchor = infer_event_anchored_state_time(question, candidate_entries)
    target_anchor, target_start, target_end = parse_question_state_anchor(question_lower)
    if event_anchor is not None:
        target_anchor = event_anchor
        target_start = None
        target_end = None
    elif target_anchor is None and (target_start is None or target_end is None):
        return ""

    dated_locations = sorted(
        [
            entry
            for entry in candidate_entries
            if entry.predicate in target_predicates and parse_observation_anchor(entry.timestamp or "")
        ],
        key=lambda entry: (
            parse_observation_anchor(entry.timestamp or ""),
            getattr(entry, "observation_id", getattr(entry, "event_id", "")),
        ),
    )
    selected: ObservationEntry | EventCalendarEntry | None = None
    for entry in dated_locations:
        anchor = parse_observation_anchor(entry.timestamp or "")
        if anchor is None:
            continue
        if target_anchor is not None:
            if anchor <= target_anchor:
                selected = entry
            elif anchor > target_anchor:
                break
        elif anchor < target_end:
            selected = entry
        elif anchor >= target_end:
            break
    if selected is None:
        return ""
    value = str(selected.metadata.get("value", "")).strip()
    if value:
        return value
    return answer_candidate_surface_text(
        selected.subject,
        selected.predicate,
        selected.metadata.get("value", ""),
        selected.text,
    )
