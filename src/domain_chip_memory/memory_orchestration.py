from __future__ import annotations

from collections.abc import Callable

from .contracts import NormalizedQuestion
from .memory_extraction import ObservationEntry


def evidence_score(
    question: NormalizedQuestion,
    observation: ObservationEntry,
    *,
    evidence_score_impl: Callable[..., float],
    observation_score: Callable[[NormalizedQuestion, ObservationEntry], float],
) -> float:
    return evidence_score_impl(
        question,
        observation,
        observation_score=observation_score,
    )


def select_preference_support_entries(
    question: NormalizedQuestion,
    entries: list[ObservationEntry],
    *,
    limit: int,
    select_preference_support_entries_impl: Callable[..., list[ObservationEntry]],
    evidence_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    observation_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    entry_source_corpus: Callable[[ObservationEntry], str],
    preference_anchor_match: Callable[..., bool],
    preference_overlap: Callable[..., int],
    preference_phrase_bonus: Callable[..., float],
    observation_evidence_text: Callable[[NormalizedQuestion, ObservationEntry], str],
) -> list[ObservationEntry]:
    return select_preference_support_entries_impl(
        question,
        entries,
        evidence_score=evidence_score,
        observation_score=observation_score,
        entry_source_corpus=entry_source_corpus,
        preference_anchor_match=preference_anchor_match,
        preference_overlap=preference_overlap,
        preference_phrase_bonus=preference_phrase_bonus,
        observation_evidence_text=observation_evidence_text,
        limit=limit,
    )


def select_evidence_entries(
    question: NormalizedQuestion,
    observations: list[ObservationEntry],
    *,
    limit: int,
    select_evidence_entries_impl: Callable[..., list[ObservationEntry]],
    evidence_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    observation_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    question_subjects: Callable[[NormalizedQuestion], list[str]],
    entry_combined_text: Callable[[NormalizedQuestion, ObservationEntry], str],
    observation_evidence_text: Callable[[NormalizedQuestion, ObservationEntry], str],
) -> list[ObservationEntry]:
    return select_evidence_entries_impl(
        question,
        observations,
        evidence_score=evidence_score,
        observation_score=observation_score,
        question_subjects=question_subjects,
        entry_combined_text=entry_combined_text,
        observation_evidence_text=observation_evidence_text,
        limit=limit,
    )


def choose_answer_candidate(
    question: NormalizedQuestion,
    evidence_entries: list[ObservationEntry],
    belief_entries: list[ObservationEntry],
    *,
    context_entries: list[ObservationEntry] | None,
    aggregate_entries: list[ObservationEntry] | None,
    choose_answer_candidate_impl: Callable[..., str],
    question_needs_raw_aggregate_context: Callable[[NormalizedQuestion], bool],
    infer_dated_state_answer: Callable[..., str],
    infer_relative_state_answer: Callable[..., str],
    is_preference_question: Callable[[NormalizedQuestion], bool],
    infer_preference_answer: Callable[..., str],
    infer_factoid_answer: Callable[..., str],
    infer_aggregate_answer: Callable[..., str],
    infer_temporal_answer: Callable[..., str],
    infer_shared_answer: Callable[..., str],
    infer_explanatory_answer: Callable[..., str],
    infer_yes_no_answer: Callable[..., str],
    answer_candidate_surface_text: Callable[[str, str, str, str], str],
    evidence_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    observation_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    observation_evidence_text: Callable[[NormalizedQuestion, ObservationEntry], str],
) -> str:
    return choose_answer_candidate_impl(
        question,
        evidence_entries,
        belief_entries,
        context_entries=context_entries,
        aggregate_entries=aggregate_entries,
        question_needs_raw_aggregate_context=question_needs_raw_aggregate_context,
        infer_dated_state_answer=infer_dated_state_answer,
        infer_relative_state_answer=infer_relative_state_answer,
        is_preference_question=is_preference_question,
        infer_preference_answer=infer_preference_answer,
        infer_factoid_answer=infer_factoid_answer,
        infer_aggregate_answer=infer_aggregate_answer,
        infer_temporal_answer=infer_temporal_answer,
        infer_shared_answer=infer_shared_answer,
        infer_explanatory_answer=infer_explanatory_answer,
        infer_yes_no_answer=infer_yes_no_answer,
        answer_candidate_surface_text=answer_candidate_surface_text,
        evidence_score=evidence_score,
        observation_score=observation_score,
        observation_evidence_text=observation_evidence_text,
    )
