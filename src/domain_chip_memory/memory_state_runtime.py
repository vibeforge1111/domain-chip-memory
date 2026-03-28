from __future__ import annotations

from datetime import datetime

from .contracts import NormalizedQuestion
from .memory_extraction import EventCalendarEntry, ObservationEntry, _normalize_value, _token_bigrams, _tokenize
from .memory_relative_time import generic_relative_anchor_candidates as _generic_relative_anchor_candidates
from .memory_relative_time import has_ambiguous_generic_relative_anchor as _has_ambiguous_generic_relative_anchor
from .memory_relative_time import infer_generic_relative_anchor_time as _infer_generic_relative_anchor_time
from .memory_rendering import answer_candidate_surface_text as _answer_candidate_surface_text
from .memory_state_inference import dated_state_target_predicates as _dated_state_target_predicates_impl
from .memory_state_inference import has_ambiguous_relative_state_anchor as _has_ambiguous_relative_state_anchor_impl
from .memory_state_inference import has_referential_ambiguity as _has_referential_ambiguity_impl
from .memory_state_inference import infer_anchor_time_from_phrase as _infer_anchor_time_from_phrase_impl
from .memory_state_inference import infer_dated_state_answer as _infer_dated_state_answer_impl
from .memory_state_inference import infer_event_anchored_state_time as _infer_event_anchored_state_time_impl
from .memory_state_inference import infer_relative_state_answer as _infer_relative_state_answer_impl
from .memory_state_queries import extract_relative_state_anchor as _extract_relative_state_anchor_impl
from .memory_state_queries import is_dated_state_question as _is_dated_state_question_impl
from .memory_state_queries import is_relative_state_question as _is_relative_state_question_impl
from .memory_state_queries import normalize_relative_state_anchor_phrase as _normalize_relative_state_anchor_phrase_impl
from .memory_state_queries import should_use_current_state_exact_value as _should_use_current_state_exact_value_impl
from .memory_state_queries import specialize_clause_carry_first_last_anchor_phrase as _specialize_clause_carry_first_last_anchor_phrase_impl
from .memory_state_queries import specialize_relative_state_anchor_phrase as _specialize_relative_state_anchor_phrase_impl
from .memory_time import parse_observation_anchor as _parse_observation_anchor
from .memory_time import parse_question_state_anchor as _parse_question_state_anchor
from .memory_views import is_current_state_question
from .memory_queries import _question_predicates
from .memory_answer_routing import question_needs_raw_aggregate_context as _question_needs_raw_aggregate_context


def _is_dated_state_question(question: NormalizedQuestion) -> bool:
    return _is_dated_state_question_impl(question)


def _extract_relative_state_anchor(question_lower: str) -> tuple[str | None, str, list[str]]:
    return _extract_relative_state_anchor_impl(
        question_lower,
        normalize_relative_state_anchor_phrase=_normalize_relative_state_anchor_phrase,
    )


def _normalize_relative_state_anchor_phrase(anchor_phrase: str, target_predicates: list[str]) -> str:
    return _normalize_relative_state_anchor_phrase_impl(
        anchor_phrase,
        target_predicates,
        normalize_value=_normalize_value,
    )


def _specialize_clause_carry_first_last_anchor_phrase(
    anchor_phrase: str,
    target_predicates: list[str],
    candidate_entries: list[ObservationEntry | EventCalendarEntry],
    *,
    allow_operation_specialization: bool,
) -> str:
    return _specialize_clause_carry_first_last_anchor_phrase_impl(
        anchor_phrase,
        target_predicates,
        candidate_entries,
        allow_operation_specialization=allow_operation_specialization,
        generic_relative_anchor_candidates=_generic_relative_anchor_candidates,
    )


def _specialize_relative_state_anchor_phrase(
    question: NormalizedQuestion,
    anchor_phrase: str,
    target_predicates: list[str],
    candidate_entries: list[ObservationEntry | EventCalendarEntry],
) -> str:
    return _specialize_relative_state_anchor_phrase_impl(
        question,
        anchor_phrase,
        target_predicates,
        candidate_entries,
        specialize_clause_carry_first_last_anchor_phrase=_specialize_clause_carry_first_last_anchor_phrase,
        has_referential_ambiguity=_has_referential_ambiguity,
    )


def _is_relative_state_question(question: NormalizedQuestion) -> bool:
    return _is_relative_state_question_impl(
        question,
        extract_relative_state_anchor=_extract_relative_state_anchor,
    )


def _should_use_current_state_exact_value(question: NormalizedQuestion) -> bool:
    return _should_use_current_state_exact_value_impl(
        question,
        is_current_state_question=is_current_state_question,
        is_dated_state_question=_is_dated_state_question,
        is_relative_state_question=_is_relative_state_question,
        question_needs_raw_aggregate_context=_question_needs_raw_aggregate_context,
    )


def _infer_anchor_time_from_phrase(
    anchor_phrase: str,
    candidate_entries: list[ObservationEntry | EventCalendarEntry],
    *,
    include_location_entries: bool = False,
) -> datetime | None:
    return _infer_anchor_time_from_phrase_impl(
        anchor_phrase,
        candidate_entries,
        include_location_entries=include_location_entries,
        parse_question_state_anchor=_parse_question_state_anchor,
        tokenize=_tokenize,
        token_bigrams=_token_bigrams,
        parse_observation_anchor=_parse_observation_anchor,
    )


def _infer_event_anchored_state_time(
    question: NormalizedQuestion,
    candidate_entries: list[ObservationEntry | EventCalendarEntry],
) -> datetime | None:
    return _infer_event_anchored_state_time_impl(
        question,
        candidate_entries,
        infer_anchor_time_from_phrase=_infer_anchor_time_from_phrase,
    )


def _has_ambiguous_relative_state_anchor(
    question: NormalizedQuestion,
    candidate_entries: list[ObservationEntry | EventCalendarEntry],
) -> bool:
    return _has_ambiguous_relative_state_anchor_impl(
        question,
        candidate_entries,
        extract_relative_state_anchor=_extract_relative_state_anchor,
        specialize_relative_state_anchor_phrase=_specialize_relative_state_anchor_phrase,
        has_ambiguous_generic_relative_anchor=_has_ambiguous_generic_relative_anchor,
    )


def _has_referential_ambiguity(
    question: NormalizedQuestion,
    candidate_entries: list[ObservationEntry | EventCalendarEntry],
) -> bool:
    return _has_referential_ambiguity_impl(
        question,
        candidate_entries,
        question_predicates=_question_predicates,
    )


def _dated_state_target_predicates(question: NormalizedQuestion) -> list[str]:
    return _dated_state_target_predicates_impl(question)


def _infer_relative_state_answer(question: NormalizedQuestion, candidate_entries: list[ObservationEntry | EventCalendarEntry]) -> str:
    return _infer_relative_state_answer_impl(
        question,
        candidate_entries,
        extract_relative_state_anchor=_extract_relative_state_anchor,
        specialize_relative_state_anchor_phrase=_specialize_relative_state_anchor_phrase,
        has_ambiguous_generic_relative_anchor=_has_ambiguous_generic_relative_anchor,
        infer_generic_relative_anchor_time=_infer_generic_relative_anchor_time,
        infer_anchor_time_from_phrase=_infer_anchor_time_from_phrase,
        parse_observation_anchor=_parse_observation_anchor,
        answer_candidate_surface_text=_answer_candidate_surface_text,
    )


def _infer_dated_state_answer(question: NormalizedQuestion, candidate_entries: list[ObservationEntry | EventCalendarEntry]) -> str:
    return _infer_dated_state_answer_impl(
        question,
        candidate_entries,
        is_dated_state_question=_is_dated_state_question,
        dated_state_target_predicates=_dated_state_target_predicates,
        infer_event_anchored_state_time=_infer_event_anchored_state_time,
        parse_question_state_anchor=_parse_question_state_anchor,
        parse_observation_anchor=_parse_observation_anchor,
        answer_candidate_surface_text=_answer_candidate_surface_text,
    )
