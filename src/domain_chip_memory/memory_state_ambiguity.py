from __future__ import annotations

from collections.abc import Callable

from .contracts import NormalizedQuestion
from .memory_extraction import EventCalendarEntry, ObservationEntry


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
