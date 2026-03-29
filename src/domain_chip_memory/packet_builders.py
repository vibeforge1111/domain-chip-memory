from __future__ import annotations

from .answer_candidates import build_answer_candidate
from .contracts import NormalizedBenchmarkSample
from .memory_answer_rendering import answer_candidate_surface_text as _answer_candidate_surface_text
from .memory_answer_runtime import (
    _choose_answer_candidate,
    _choose_stateful_answer_candidate,
    _evidence_score,
    _observation_score,
    _question_needs_raw_aggregate_context,
    _select_evidence_entries,
    _select_preference_support_entries,
)
from .memory_atom_runtime import (
    _atom_score,
    _choose_atoms,
    _raw_user_turn_entries,
    _select_aggregate_support_entries,
    extract_memory_atoms,
)
from .memory_beam_builder import build_beam_ready_temporal_atom_router_packets as _build_beam_ready_temporal_atom_router_packets_impl
from .memory_contract_summary import build_memory_system_contract_summary
from .memory_dual_store_builder import build_dual_store_event_calendar_hybrid_packets as _build_dual_store_event_calendar_hybrid_packets_impl
from .memory_observational_builder import build_observational_temporal_memory_packets as _build_observational_temporal_memory_packets_impl
from .memory_stateful_event_builder import build_stateful_event_reconstruction_packets as _build_stateful_event_reconstruction_packets_impl
from .memory_typed_state_builder import build_typed_state_update_memory_packets as _build_typed_state_update_memory_packets_impl
from .memory_evidence import entry_source_corpus as _entry_source_corpus
from .memory_evidence import observation_evidence_text as _observation_evidence_text
from .memory_observation_runtime import (
    _topical_episode_support,
    build_event_calendar,
    build_observation_log,
    reflect_observations,
)
from .memory_observation_utils import dedupe_observations as _dedupe_observations
from .memory_observation_utils import session_lookup as _session_lookup
from .memory_packet_utils import event_score as _event_score
from .memory_packet_utils import question_aware_observation_limits as _question_aware_observation_limits
from .memory_preferences import is_preference_question as _is_preference_question
from .memory_queries import _question_predicates, _question_subjects
from .memory_roles import strategy_memory_role
from .memory_session_rendering import serialize_session as _serialize_session
from .memory_state_runtime import (
    _has_ambiguous_relative_state_anchor,
    _has_referential_ambiguity,
    _is_dated_state_question,
    _is_relative_state_question,
    _should_use_current_state_exact_value,
)
from .memory_updates import build_current_state_view as _build_current_state_view
from .memory_updates import has_active_current_state_deletion
from .memory_views import is_current_state_question, select_current_state_entries
from .runs import BaselinePromptPacket, build_run_manifest


def build_observational_temporal_memory_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    max_observations: int = 8,
    max_reflections: int = 4,
    max_topic_support: int = 2,
    run_id: str = "observational-temporal-memory-v1",
) -> tuple[dict[str, object], list[BaselinePromptPacket]]:
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
) -> tuple[dict[str, object], list[BaselinePromptPacket]]:
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
) -> tuple[dict[str, object], list[BaselinePromptPacket]]:
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


def build_stateful_event_reconstruction_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    max_observations: int = 8,
    max_reflections: int = 4,
    top_k_events: int = 4,
    max_topic_support: int = 2,
    run_id: str = "stateful-event-reconstruction-v1",
) -> tuple[dict[str, object], list[BaselinePromptPacket]]:
    return _build_stateful_event_reconstruction_packets_impl(
        samples,
        max_observations=max_observations,
        max_reflections=max_reflections,
        top_k_events=top_k_events,
        max_topic_support=max_topic_support,
        run_id=run_id,
        build_observation_log=build_observation_log,
        reflect_observations=reflect_observations,
        build_event_calendar=build_event_calendar,
        raw_user_turn_entries=_raw_user_turn_entries,
        has_active_current_state_deletion=has_active_current_state_deletion,
        is_current_state_question=is_current_state_question,
        question_subjects=_question_subjects,
        question_predicates=_question_predicates,
        question_aware_observation_limits=_question_aware_observation_limits,
        is_preference_question=_is_preference_question,
        select_preference_support_entries=_select_preference_support_entries,
        observation_score=_observation_score,
        event_score=_event_score,
        select_current_state_entries=select_current_state_entries,
        topical_episode_support=_topical_episode_support,
        dedupe_observations=_dedupe_observations,
        select_evidence_entries=_select_evidence_entries,
        question_needs_raw_aggregate_context=_question_needs_raw_aggregate_context,
        select_aggregate_support_entries=_select_aggregate_support_entries,
        observation_evidence_text=_observation_evidence_text,
        evidence_score=_evidence_score,
        entry_source_corpus=_entry_source_corpus,
        choose_answer_candidate=_choose_stateful_answer_candidate,
        is_dated_state_question=_is_dated_state_question,
        is_relative_state_question=_is_relative_state_question,
        has_ambiguous_relative_state_anchor=_has_ambiguous_relative_state_anchor,
        has_referential_ambiguity=_has_referential_ambiguity,
        should_use_current_state_exact_value=_should_use_current_state_exact_value,
        build_answer_candidate=build_answer_candidate,
        build_run_manifest=build_run_manifest,
        strategy_memory_role=strategy_memory_role,
    )


def build_typed_state_update_memory_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    max_observations: int = 8,
    max_reflections: int = 4,
    top_k_events: int = 4,
    max_topic_support: int = 2,
    run_id: str = "typed-state-update-memory-v1",
) -> tuple[dict[str, object], list[BaselinePromptPacket]]:
    return _build_typed_state_update_memory_packets_impl(
        samples,
        max_observations=max_observations,
        max_reflections=max_reflections,
        top_k_events=top_k_events,
        max_topic_support=max_topic_support,
        run_id=run_id,
        build_observation_log=build_observation_log,
        reflect_observations=reflect_observations,
        build_event_calendar=build_event_calendar,
        raw_user_turn_entries=_raw_user_turn_entries,
        build_current_state_view=_build_current_state_view,
        has_active_current_state_deletion=has_active_current_state_deletion,
        is_current_state_question=is_current_state_question,
        question_subjects=_question_subjects,
        question_predicates=_question_predicates,
        question_aware_observation_limits=_question_aware_observation_limits,
        is_preference_question=_is_preference_question,
        select_preference_support_entries=_select_preference_support_entries,
        observation_score=_observation_score,
        event_score=_event_score,
        select_current_state_entries=select_current_state_entries,
        topical_episode_support=_topical_episode_support,
        dedupe_observations=_dedupe_observations,
        select_evidence_entries=_select_evidence_entries,
        question_needs_raw_aggregate_context=_question_needs_raw_aggregate_context,
        select_aggregate_support_entries=_select_aggregate_support_entries,
        observation_evidence_text=_observation_evidence_text,
        evidence_score=_evidence_score,
        entry_source_corpus=_entry_source_corpus,
        choose_answer_candidate=_choose_stateful_answer_candidate,
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


__all__ = [
    "build_beam_ready_temporal_atom_router_packets",
    "build_dual_store_event_calendar_hybrid_packets",
    "build_memory_system_contract_summary",
    "build_observational_temporal_memory_packets",
    "build_stateful_event_reconstruction_packets",
    "build_typed_state_update_memory_packets",
]
