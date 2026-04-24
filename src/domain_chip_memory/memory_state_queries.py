from __future__ import annotations

import re
from collections.abc import Callable

from .contracts import NormalizedQuestion
from .memory_queries import _is_profile_memory_query
from .memory_relative_state_queries import extract_relative_state_anchor
from .memory_relative_state_queries import normalize_relative_state_anchor_phrase
from .memory_relative_state_queries import specialize_clause_carry_first_last_anchor_phrase
from .memory_relative_state_queries import specialize_relative_state_anchor_phrase


def is_dated_state_question(question: NormalizedQuestion) -> bool:
    question_lower = question.question.lower()
    if question_lower.startswith(
        (
            "where did i live before ",
            "where was i living before ",
            "where did i live after ",
            "where was i living after ",
            "what did i prefer before ",
            "what did i prefer after ",
            "what was my favorite color before ",
            "what was my favourite color before ",
            "what was my favorite colour before ",
            "what was my favourite colour before ",
            "what was my favorite color after ",
            "what was my favourite color after ",
            "what was my favorite colour after ",
            "what was my favourite colour after ",
        )
    ):
        return False
    return (
        question_lower.startswith(
            (
                "where did i live in ",
                "where was i living in ",
                "where did i live on ",
                "where was i living on ",
                "where did i live at ",
                "where was i living at ",
                "where did i live when ",
                "where was i living when ",
                "what did i prefer in ",
                "what did i prefer on ",
                "what did i prefer at ",
                "what did i prefer when ",
                "what was my favorite color when ",
                "what was my favourite color when ",
                "what was my favorite colour when ",
                "what was my favourite colour when ",
            )
        )
        or bool(
            re.search(
                r"\b(?:at\s+\d{1,2}(?::\d{2})?\s*[ap]m\s+on\s+\d{1,2}\s+"
                r"(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}|"
                r"on\s+\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}|"
                r"in\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4})\b",
                question_lower,
            )
        )
    )


def is_relative_state_question(
    question: NormalizedQuestion,
    *,
    extract_relative_state_anchor: Callable[[str], tuple[str | None, str, list[str]]],
) -> bool:
    mode, anchor_phrase, target_predicates = extract_relative_state_anchor(question.question.lower())
    return mode is not None and bool(anchor_phrase) and bool(target_predicates)


def should_use_current_state_exact_value(
    question: NormalizedQuestion,
    *,
    is_current_state_question: Callable[[NormalizedQuestion], bool],
    is_dated_state_question: Callable[[NormalizedQuestion], bool],
    is_relative_state_question: Callable[[NormalizedQuestion], bool],
    question_needs_raw_aggregate_context: Callable[[NormalizedQuestion], bool],
) -> bool:
    question_lower = question.question.lower()
    if not is_current_state_question(question):
        return False
    exact_location_profile_query = any(
        phrase in question_lower
        for phrase in (
            "where do i live now",
            "where do i live",
            "what city do i live in",
            "which city do i live in",
        )
    )
    if _is_profile_memory_query(question) and not exact_location_profile_query:
        return False
    if is_dated_state_question(question) or is_relative_state_question(question):
        return False
    if question_lower.startswith("how many bikes") and "own" in question_lower:
        return True
    if question_needs_raw_aggregate_context(question):
        return False
    if question_lower.startswith(("how many", "how much", "what is the total", "what was the total")):
        return False
    return True
