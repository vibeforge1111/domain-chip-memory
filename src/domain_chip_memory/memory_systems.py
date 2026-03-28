from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

from .answer_candidates import build_answer_candidate
from .contracts import AnswerCandidate, JsonDict, NormalizedBenchmarkSample, NormalizedQuestion, NormalizedSession, NormalizedTurn
from .memory_evidence import entry_source_corpus as _entry_source_corpus
from .memory_evidence import observation_evidence_text as _observation_evidence_text
from .memory_evidence import raw_evidence_span as _raw_evidence_span
from .memory_aggregate_support import raw_user_turn_entries as _raw_user_turn_entries_impl
from .memory_aggregate_support import select_aggregate_support_entries as _select_aggregate_support_entries_impl
from .memory_answer_inference import extract_place_candidates as _extract_place_candidates_impl
from .memory_answer_inference import infer_explanatory_answer as _infer_explanatory_answer_impl
from .memory_answer_inference import infer_aggregate_answer as _infer_aggregate_answer_impl
from .memory_answer_inference import infer_factoid_answer as _infer_factoid_answer_impl
from .memory_answer_inference import infer_shared_answer as _infer_shared_answer_impl
from .memory_answer_routing import choose_answer_candidate as _choose_answer_candidate_impl
from .memory_answer_routing import entry_combined_text as _entry_combined_text_impl
from .memory_answer_routing import question_needs_raw_aggregate_context as _question_needs_raw_aggregate_context
from .memory_atom_extraction import extract_memory_atoms
from .memory_atom_routing import atom_score as _atom_score_impl
from .memory_atom_routing import choose_atoms as _choose_atoms_impl
from .memory_beam_builder import build_beam_ready_temporal_atom_router_packets as _build_beam_ready_temporal_atom_router_packets_impl
from .memory_contract_summary import build_memory_system_contract_summary as _build_memory_system_contract_summary_impl
from .memory_dual_store_builder import build_dual_store_event_calendar_hybrid_packets as _build_dual_store_event_calendar_hybrid_packets_impl
from .memory_observational_builder import build_observational_temporal_memory_packets as _build_observational_temporal_memory_packets_impl
from .memory_extraction import (
    EventCalendarEntry,
    MemoryAtom,
    ObservationEntry,
    _canonical_subject,
    _normalize_value,
    _token_bigrams,
    _tokenize,
    _turn_order_key,
    build_event_calendar as _build_event_calendar,
    build_observation_log as _build_observation_log,
)
from .memory_queries import _question_predicates, _question_subject, _question_subjects
from .memory_numbers import extract_first_numeric_match as _extract_first_numeric_match
from .memory_numbers import format_count_value as _format_count_value
from .memory_numbers import parse_small_number as _parse_small_number
from .memory_observation_support import build_event_calendar as _build_event_calendar_support_impl
from .memory_observation_support import build_observation_log as _build_observation_log_support_impl
from .memory_observation_support import reflect_observations as _reflect_observations_impl
from .memory_observation_support import topical_episode_support as _topical_episode_support_impl
from .memory_orchestration import choose_answer_candidate as _choose_answer_candidate_support_impl
from .memory_orchestration import evidence_score as _evidence_score_support_impl
from .memory_orchestration import select_evidence_entries as _select_evidence_entries_support_impl
from .memory_orchestration import select_preference_support_entries as _select_preference_support_entries_support_impl
from .memory_packet_utils import event_score as _event_score
from .memory_packet_utils import question_aware_observation_limits as _question_aware_observation_limits
from .memory_observation_utils import dedupe_observations as _dedupe_observations
from .memory_observation_utils import session_lookup as _session_lookup
from .memory_preferences import is_generic_followup_preference_text as _is_generic_followup_preference_text
from .memory_preferences import is_preference_question as _is_preference_question
from .memory_preferences import is_recommendation_request_text as _is_recommendation_request_text
from .memory_preference_answers import infer_preference_answer as _infer_preference_answer
from .memory_preferences import preference_anchor_match as _preference_anchor_match
from .memory_preferences import preference_domain_tokens as _preference_domain_tokens
from .memory_preferences import preference_overlap as _preference_overlap
from .memory_preferences import preference_phrase_bonus as _preference_phrase_bonus
from .memory_relative_time import generic_relative_anchor_candidates as _generic_relative_anchor_candidates
from .memory_relative_time import has_ambiguous_generic_relative_anchor as _has_ambiguous_generic_relative_anchor
from .memory_relative_time import infer_generic_relative_anchor_time as _infer_generic_relative_anchor_time
from .memory_relative_time import parse_generic_relative_anchor_phrase as _parse_generic_relative_anchor_phrase
from .memory_observation_scoring import observation_score as _observation_score_impl
from .memory_rendering import answer_candidate_surface_text as _answer_candidate_surface_text
from .memory_rendering import observation_surface_text as _observation_surface_text
from .memory_rendering import serialize_session as _serialize_session
from .memory_scoring import evidence_score as _evidence_score_impl
from .memory_selection import select_evidence_entries as _select_evidence_entries_impl
from .memory_selection import select_preference_support_entries as _select_preference_support_entries_impl
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
from .memory_temporal_answers import infer_temporal_answer as _infer_temporal_answer_impl
from .memory_temporal_answers import infer_yes_no_answer as _infer_yes_no_answer_impl
from .memory_roles import strategy_memory_role
from .memory_time import format_full_date as _format_full_date
from .memory_time import format_month_year as _format_month_year
from .memory_time import parse_observation_anchor as _parse_observation_anchor
from .memory_time import parse_question_state_anchor as _parse_question_state_anchor
from .memory_time import shift_month as _shift_month
from .memory_updates import build_current_state_view, has_active_current_state_deletion
from .memory_views import is_current_state_question, select_current_state_entries
from .runs import BaselinePromptPacket, RetrievedContextItem, build_run_manifest


def build_observation_log(sample: NormalizedBenchmarkSample) -> list[ObservationEntry]:
    return _build_observation_log_support_impl(
        sample,
        build_observation_log_impl=_build_observation_log,
        extract_memory_atoms=extract_memory_atoms,
        observation_surface_text=_observation_surface_text,
    )


def reflect_observations(observations: list[ObservationEntry]) -> list[ObservationEntry]:
    return _reflect_observations_impl(
        observations,
        build_current_state_view=build_current_state_view,
    )


def _topical_episode_support(
    question: NormalizedQuestion,
    stable_window: list[ObservationEntry],
    observations: list[ObservationEntry],
    *,
    max_support: int = 2,
) -> tuple[str, list[ObservationEntry]]:
    return _topical_episode_support_impl(
        question,
        stable_window,
        observations,
        max_support=max_support,
        observation_score=_observation_score,
        turn_order_key=_turn_order_key,
    )


def build_event_calendar(sample: NormalizedBenchmarkSample) -> list[EventCalendarEntry]:
    return _build_event_calendar_support_impl(
        sample,
        build_event_calendar_impl=_build_event_calendar,
        extract_memory_atoms=extract_memory_atoms,
        observation_surface_text=_observation_surface_text,
    )


def _atom_score(question: NormalizedQuestion, atom: MemoryAtom) -> float:
    return _atom_score_impl(
        question,
        atom,
        question_subject=_question_subject,
        question_subjects=_question_subjects,
        question_predicates=_question_predicates,
        tokenize=_tokenize,
        token_bigrams=_token_bigrams,
    )


def _choose_atoms(question: NormalizedQuestion, atoms: list[MemoryAtom], limit: int) -> list[MemoryAtom]:
    return _choose_atoms_impl(
        question,
        atoms,
        limit,
        question_predicates=_question_predicates,
        question_subjects=_question_subjects,
        atom_score=_atom_score,
    )


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


def _entry_combined_text(question: NormalizedQuestion, entry: ObservationEntry) -> str:
    return _entry_combined_text_impl(
        question,
        entry,
        observation_evidence_text=_observation_evidence_text,
    )


def _raw_user_turn_entries(sample: NormalizedBenchmarkSample) -> list[ObservationEntry]:
    return _raw_user_turn_entries_impl(sample)


def _select_aggregate_support_entries(
    question: NormalizedQuestion,
    aggregate_entries: list[ObservationEntry],
    *,
    limit: int = 4,
) -> list[ObservationEntry]:
    return _select_aggregate_support_entries_impl(
        question,
        aggregate_entries,
        limit=limit,
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


def _observation_score(question: NormalizedQuestion, observation: ObservationEntry) -> float:
    return _observation_score_impl(question, observation)


def build_observational_temporal_memory_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    max_observations: int = 8,
    max_reflections: int = 4,
    max_topic_support: int = 2,
    run_id: str = "observational-temporal-memory-v1",
) -> tuple[dict[str, Any], list[BaselinePromptPacket]]:
    return _build_observational_temporal_memory_packets_impl(
        samples,
        max_observations=max_observations,
        max_reflections=max_reflections,
        max_topic_support=max_topic_support,
        run_id=run_id,
        build_observation_log=build_observation_log,
        reflect_observations=reflect_observations,
        raw_user_turn_entries=_raw_user_turn_entries,
        has_active_current_state_deletion=has_active_current_state_deletion,
        is_current_state_question=is_current_state_question,
        question_subjects=_question_subjects,
        question_predicates=_question_predicates,
        question_aware_observation_limits=_question_aware_observation_limits,
        is_preference_question=_is_preference_question,
        select_preference_support_entries=_select_preference_support_entries,
        observation_score=_observation_score,
        select_current_state_entries=select_current_state_entries,
        topical_episode_support=_topical_episode_support,
        dedupe_observations=_dedupe_observations,
        select_evidence_entries=_select_evidence_entries,
        question_needs_raw_aggregate_context=_question_needs_raw_aggregate_context,
        select_aggregate_support_entries=_select_aggregate_support_entries,
        observation_evidence_text=_observation_evidence_text,
        evidence_score=_evidence_score,
        entry_source_corpus=_entry_source_corpus,
        choose_answer_candidate=_choose_answer_candidate,
        is_dated_state_question=_is_dated_state_question,
        is_relative_state_question=_is_relative_state_question,
        has_ambiguous_relative_state_anchor=_has_ambiguous_relative_state_anchor,
        has_referential_ambiguity=_has_referential_ambiguity,
        should_use_current_state_exact_value=_should_use_current_state_exact_value,
        build_answer_candidate=build_answer_candidate,
        build_run_manifest=build_run_manifest,
        strategy_memory_role=strategy_memory_role,
    )


def build_beam_ready_temporal_atom_router_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    top_k_atoms: int = 3,
    include_rehydrated_sessions: int = 1,
    run_id: str = "beam-temporal-atom-router-v1",
) -> tuple[dict[str, Any], list[BaselinePromptPacket]]:
    return _build_beam_ready_temporal_atom_router_packets_impl(
        samples,
        top_k_atoms=top_k_atoms,
        include_rehydrated_sessions=include_rehydrated_sessions,
        run_id=run_id,
        extract_memory_atoms=extract_memory_atoms,
        session_lookup=_session_lookup,
        choose_atoms=_choose_atoms,
        atom_score=_atom_score,
        serialize_session=_serialize_session,
        should_use_current_state_exact_value=_should_use_current_state_exact_value,
        answer_candidate_surface_text=_answer_candidate_surface_text,
        build_answer_candidate=build_answer_candidate,
        build_run_manifest=build_run_manifest,
        strategy_memory_role=strategy_memory_role,
    )


def build_dual_store_event_calendar_hybrid_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    max_observations: int = 6,
    top_k_events: int = 3,
    max_topic_support: int = 2,
    run_id: str = "dual-store-event-calendar-hybrid-v1",
) -> tuple[dict[str, Any], list[BaselinePromptPacket]]:
    return _build_dual_store_event_calendar_hybrid_packets_impl(
        samples,
        max_observations=max_observations,
        top_k_events=top_k_events,
        max_topic_support=max_topic_support,
        run_id=run_id,
        build_observation_log=build_observation_log,
        reflect_observations=reflect_observations,
        build_event_calendar=build_event_calendar,
        has_active_current_state_deletion=has_active_current_state_deletion,
        is_current_state_question=is_current_state_question,
        question_subjects=_question_subjects,
        question_predicates=_question_predicates,
        observation_score=_observation_score,
        event_score=_event_score,
        select_current_state_entries=select_current_state_entries,
        topical_episode_support=_topical_episode_support,
        select_evidence_entries=_select_evidence_entries,
        dedupe_observations=_dedupe_observations,
        observation_evidence_text=_observation_evidence_text,
        evidence_score=_evidence_score,
        choose_answer_candidate=_choose_answer_candidate,
        is_dated_state_question=_is_dated_state_question,
        is_relative_state_question=_is_relative_state_question,
        has_ambiguous_relative_state_anchor=_has_ambiguous_relative_state_anchor,
        has_referential_ambiguity=_has_referential_ambiguity,
        should_use_current_state_exact_value=_should_use_current_state_exact_value,
        answer_candidate_surface_text=_answer_candidate_surface_text,
        build_answer_candidate=build_answer_candidate,
        build_run_manifest=build_run_manifest,
        strategy_memory_role=strategy_memory_role,
    )

def build_memory_system_contract_summary() -> dict[str, Any]:
    return _build_memory_system_contract_summary_impl()






