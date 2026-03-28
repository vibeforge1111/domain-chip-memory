from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from .contracts import NormalizedQuestion
from .memory_extraction import EventCalendarEntry, ObservationEntry
from .memory_state_anchor_inference import infer_event_anchored_state_time


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
