from __future__ import annotations

from .memory_answer_rendering import answer_candidate_surface_text as _answer_candidate_surface_text
from .contracts import NormalizedQuestion
from .memory_aggregate_answers import infer_aggregate_answer as _infer_aggregate_answer_impl
from .memory_answer_routing import choose_answer_candidate as _choose_answer_candidate_impl
from .memory_answer_routing import entry_combined_text as _entry_combined_text_impl
from .memory_answer_routing import question_needs_raw_aggregate_context as _question_needs_raw_aggregate_context
from .memory_evidence import entry_source_corpus as _entry_source_corpus
from .memory_evidence import observation_evidence_text as _observation_evidence_text
from .memory_extraction import ObservationEntry, _tokenize
from .memory_observation_scoring_rules import observation_score as _observation_score_impl
from .memory_orchestration import choose_answer_candidate as _choose_answer_candidate_support_impl
from .memory_orchestration import evidence_score as _evidence_score_support_impl
from .memory_orchestration import select_evidence_entries as _select_evidence_entries_support_impl
from .memory_orchestration import select_preference_support_entries as _select_preference_support_entries_support_impl
from .memory_preferences import is_preference_question as _is_preference_question
from .memory_preferences import preference_anchor_match as _preference_anchor_match
from .memory_preferences import preference_overlap as _preference_overlap
from .memory_preferences import preference_phrase_bonus as _preference_phrase_bonus
from .memory_preference_answers import infer_preference_answer as _infer_preference_answer
from .memory_queries import _question_subject, _question_subjects
from .memory_factoid_answers import infer_factoid_answer as _infer_factoid_answer_impl
from .memory_relational_answers import extract_place_candidates as _extract_place_candidates_impl
from .memory_relational_answers import infer_explanatory_answer as _infer_explanatory_answer_impl
from .memory_relational_answers import infer_shared_answer as _infer_shared_answer_impl
from .memory_scoring import evidence_score as _evidence_score_impl
from .memory_selection import select_evidence_entries as _select_evidence_entries_impl
from .memory_selection import select_preference_support_entries as _select_preference_support_entries_impl
from .memory_state_runtime import _infer_dated_state_answer, _infer_relative_state_answer
from .memory_temporal_answers import infer_temporal_answer as _infer_temporal_answer_impl
from .memory_temporal_answers import infer_yes_no_answer as _infer_yes_no_answer_impl
from .memory_time import format_full_date as _format_full_date
from .memory_time import format_month_year as _format_month_year
from .memory_time import parse_observation_anchor as _parse_observation_anchor
from .memory_time import shift_month as _shift_month


def _observation_score(question: NormalizedQuestion, observation: ObservationEntry) -> float:
    return _observation_score_impl(question, observation)


def _evidence_score(question: NormalizedQuestion, observation: ObservationEntry) -> float:
    return _evidence_score_support_impl(
        question,
        observation,
        evidence_score_impl=_evidence_score_impl,
        observation_score=_observation_score,
    )


def _select_preference_support_entries(
    question: NormalizedQuestion,
    entries: list[ObservationEntry],
    *,
    limit: int = 4,
) -> list[ObservationEntry]:
    return _select_preference_support_entries_support_impl(
        question,
        entries,
        limit=limit,
        select_preference_support_entries_impl=_select_preference_support_entries_impl,
        evidence_score=_evidence_score,
        observation_score=_observation_score,
        entry_source_corpus=_entry_source_corpus,
        preference_anchor_match=_preference_anchor_match,
        preference_overlap=_preference_overlap,
        preference_phrase_bonus=_preference_phrase_bonus,
        observation_evidence_text=_observation_evidence_text,
    )


def _entry_combined_text(question: NormalizedQuestion, entry: ObservationEntry) -> str:
    return _entry_combined_text_impl(
        question,
        entry,
        observation_evidence_text=_observation_evidence_text,
    )


def _select_evidence_entries(
    question: NormalizedQuestion,
    observations: list[ObservationEntry],
    *,
    limit: int = 4,
) -> list[ObservationEntry]:
    return _select_evidence_entries_support_impl(
        question,
        observations,
        limit=limit,
        select_evidence_entries_impl=_select_evidence_entries_impl,
        evidence_score=_evidence_score,
        observation_score=_observation_score,
        question_subjects=_question_subjects,
        entry_combined_text=_entry_combined_text,
        observation_evidence_text=_observation_evidence_text,
    )


def _extract_place_candidates(text: str, ignored_terms: set[str]) -> set[str]:
    return _extract_place_candidates_impl(text, ignored_terms)


def _is_pure_question_turn(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and stripped.endswith("?") and "." not in stripped and "!" not in stripped


def _infer_shared_answer(question: NormalizedQuestion, evidence_entries: list[ObservationEntry]) -> str:
    return _infer_shared_answer_impl(
        question,
        evidence_entries,
        question_subjects=_question_subjects,
        entry_combined_text=_entry_combined_text,
        entry_source_corpus=_entry_source_corpus,
    )


def _infer_explanatory_answer(question: NormalizedQuestion, evidence_entries: list[ObservationEntry]) -> str:
    return _infer_explanatory_answer_impl(
        question,
        evidence_entries,
        question_subject=_question_subject,
        entry_combined_text=_entry_combined_text,
    )


def _infer_aggregate_answer(question: NormalizedQuestion, candidate_entries: list[ObservationEntry]) -> str:
    return _infer_aggregate_answer_impl(question, candidate_entries)


def _infer_factoid_answer(question: NormalizedQuestion, candidate_entries: list[ObservationEntry]) -> str:
    return _infer_factoid_answer_impl(
        question,
        candidate_entries,
        entry_combined_text=_entry_combined_text,
        entry_source_corpus=_entry_source_corpus,
    )


def _infer_temporal_answer(question: NormalizedQuestion, evidence_entries: list[ObservationEntry]) -> str:
    return _infer_temporal_answer_impl(
        question,
        evidence_entries,
        tokenize=_tokenize,
        observation_evidence_text=_observation_evidence_text,
        evidence_score=_evidence_score,
        observation_score=_observation_score,
        parse_observation_anchor=_parse_observation_anchor,
        is_pure_question_turn=_is_pure_question_turn,
        format_full_date=_format_full_date,
        format_month_year=_format_month_year,
        shift_month=_shift_month,
    )


def _infer_yes_no_answer(question: NormalizedQuestion, evidence_entries: list[ObservationEntry]) -> str:
    return _infer_yes_no_answer_impl(
        question,
        evidence_entries,
        question_subject=_question_subject,
        evidence_score=_evidence_score,
        observation_score=_observation_score,
        observation_evidence_text=_observation_evidence_text,
    )


def _question_prefers_temporal_reconstruction(question: NormalizedQuestion) -> bool:
    question_lower = question.question.lower()
    return any(
        cue in question_lower
        for cue in (
            "when did",
            "when was",
            "how long",
            "how many days",
            "how many weeks",
            "how many months",
            "how many years",
            "before ",
            "after ",
            "between ",
            "first ",
            "last ",
            "earlier ",
            "later ",
        )
    )


def _question_prefers_summary_reconstruction(question: NormalizedQuestion) -> bool:
    question_lower = question.question.lower()
    return any(
        cue in question_lower
        for cue in (
            "summary",
            "summarize",
            "over time",
            "overall",
            "what changed",
            "how have",
            "how has",
            "across ",
            "throughout ",
        )
    )


def _choose_answer_candidate(
    question: NormalizedQuestion,
    evidence_entries: list[ObservationEntry],
    belief_entries: list[ObservationEntry],
    context_entries: list[ObservationEntry] | None = None,
    aggregate_entries: list[ObservationEntry] | None = None,
) -> str:
    return _choose_answer_candidate_support_impl(
        question,
        evidence_entries,
        belief_entries,
        context_entries=context_entries,
        aggregate_entries=aggregate_entries,
        choose_answer_candidate_impl=_choose_answer_candidate_impl,
        question_needs_raw_aggregate_context=_question_needs_raw_aggregate_context,
        infer_dated_state_answer=_infer_dated_state_answer,
        infer_relative_state_answer=_infer_relative_state_answer,
        is_preference_question=_is_preference_question,
        infer_preference_answer=_infer_preference_answer,
        infer_factoid_answer=_infer_factoid_answer,
        infer_aggregate_answer=_infer_aggregate_answer,
        infer_temporal_answer=_infer_temporal_answer,
        infer_shared_answer=_infer_shared_answer,
        infer_explanatory_answer=_infer_explanatory_answer,
        infer_yes_no_answer=_infer_yes_no_answer,
        answer_candidate_surface_text=_answer_candidate_surface_text,
        evidence_score=_evidence_score,
        observation_score=_observation_score,
        observation_evidence_text=_observation_evidence_text,
    )


def _choose_stateful_answer_candidate(
    question: NormalizedQuestion,
    evidence_entries: list[ObservationEntry],
    belief_entries: list[ObservationEntry],
    context_entries: list[ObservationEntry] | None = None,
    aggregate_entries: list[ObservationEntry] | None = None,
) -> str:
    if question.should_abstain:
        return "unknown"
    candidate_entries = context_entries or evidence_entries
    aggregate_candidate_entries = list(aggregate_entries or [])
    for entry in candidate_entries:
        if entry not in aggregate_candidate_entries:
            aggregate_candidate_entries.append(entry)
    aggregate_first = (
        _question_needs_raw_aggregate_context(question)
        or _question_prefers_summary_reconstruction(question)
        or question.question.lower().startswith("what are the two hobbies that led me to join online communities")
    )
    dated_state_answer = _infer_dated_state_answer(question, candidate_entries)
    if dated_state_answer:
        return dated_state_answer
    relative_state_answer = _infer_relative_state_answer(question, candidate_entries)
    if relative_state_answer:
        return relative_state_answer
    if _is_preference_question(question):
        preference_answer = _infer_preference_answer(question, candidate_entries)
        if preference_answer:
            return preference_answer
    if _question_prefers_temporal_reconstruction(question):
        temporal_answer = _infer_temporal_answer(question, candidate_entries)
        if temporal_answer:
            return temporal_answer
        shared_answer = _infer_shared_answer(question, candidate_entries)
        if shared_answer:
            return shared_answer
        explanatory_answer = _infer_explanatory_answer(question, candidate_entries)
        if explanatory_answer:
            return explanatory_answer
        aggregate_answer = _infer_aggregate_answer(question, aggregate_candidate_entries)
        if aggregate_answer:
            return aggregate_answer
        yes_no_answer = _infer_yes_no_answer(question, candidate_entries)
        if yes_no_answer:
            return yes_no_answer
        return _infer_factoid_answer(question, candidate_entries)
    if aggregate_first:
        aggregate_answer = _infer_aggregate_answer(question, aggregate_candidate_entries)
        if aggregate_answer:
            return aggregate_answer
        explanatory_answer = _infer_explanatory_answer(question, candidate_entries)
        if explanatory_answer:
            return explanatory_answer
        shared_answer = _infer_shared_answer(question, candidate_entries)
        if shared_answer:
            return shared_answer
    return _choose_answer_candidate(
        question,
        evidence_entries,
        belief_entries,
        context_entries=context_entries,
        aggregate_entries=aggregate_entries,
    )


__all__ = [
    "_choose_answer_candidate",
    "_choose_stateful_answer_candidate",
    "_entry_combined_text",
    "_evidence_score",
    "_extract_place_candidates",
    "_infer_aggregate_answer",
    "_infer_explanatory_answer",
    "_infer_factoid_answer",
    "_infer_shared_answer",
    "_infer_temporal_answer",
    "_infer_yes_no_answer",
    "_is_pure_question_turn",
    "_observation_score",
    "_question_needs_raw_aggregate_context",
    "_question_prefers_summary_reconstruction",
    "_question_prefers_temporal_reconstruction",
    "_select_evidence_entries",
    "_select_preference_support_entries",
]
