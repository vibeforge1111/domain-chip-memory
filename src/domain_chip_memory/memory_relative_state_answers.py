from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from .contracts import NormalizedQuestion
from .memory_extraction import EventCalendarEntry, ObservationEntry
from .memory_state_anchor_inference import infer_anchor_time_from_phrase


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
