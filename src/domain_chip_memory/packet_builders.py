from __future__ import annotations

from . import memory_runtime_bindings as _runtime
from .contracts import NormalizedBenchmarkSample
from .memory_beam_builder import build_beam_ready_temporal_atom_router_packets as _build_beam_ready_temporal_atom_router_packets_impl
from .memory_contract_summary import build_memory_system_contract_summary
from .memory_dual_store_builder import build_dual_store_event_calendar_hybrid_packets as _build_dual_store_event_calendar_hybrid_packets_impl
from .memory_observational_builder import build_observational_temporal_memory_packets as _build_observational_temporal_memory_packets_impl
from .memory_roles import strategy_memory_role
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
        build_observation_log=_runtime.build_observation_log,
        reflect_observations=_runtime.reflect_observations,
        raw_user_turn_entries=_runtime._raw_user_turn_entries,
        has_active_current_state_deletion=_runtime.has_active_current_state_deletion,
        is_current_state_question=_runtime.is_current_state_question,
        question_subjects=_runtime._question_subjects,
        question_predicates=_runtime._question_predicates,
        question_aware_observation_limits=_runtime._question_aware_observation_limits,
        is_preference_question=_runtime._is_preference_question,
        select_preference_support_entries=_runtime._select_preference_support_entries,
        observation_score=_runtime._observation_score,
        select_current_state_entries=_runtime.select_current_state_entries,
        topical_episode_support=_runtime._topical_episode_support,
        dedupe_observations=_runtime._dedupe_observations,
        select_evidence_entries=_runtime._select_evidence_entries,
        question_needs_raw_aggregate_context=_runtime._question_needs_raw_aggregate_context,
        select_aggregate_support_entries=_runtime._select_aggregate_support_entries,
        observation_evidence_text=_runtime._observation_evidence_text,
        evidence_score=_runtime._evidence_score,
        entry_source_corpus=_runtime._entry_source_corpus,
        choose_answer_candidate=_runtime._choose_answer_candidate,
        is_dated_state_question=_runtime._is_dated_state_question,
        is_relative_state_question=_runtime._is_relative_state_question,
        has_ambiguous_relative_state_anchor=_runtime._has_ambiguous_relative_state_anchor,
        has_referential_ambiguity=_runtime._has_referential_ambiguity,
        should_use_current_state_exact_value=_runtime._should_use_current_state_exact_value,
        build_answer_candidate=_runtime.build_answer_candidate,
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
        extract_memory_atoms=_runtime.extract_memory_atoms,
        session_lookup=_runtime._session_lookup,
        choose_atoms=_runtime._choose_atoms,
        atom_score=_runtime._atom_score,
        serialize_session=_runtime._serialize_session,
        should_use_current_state_exact_value=_runtime._should_use_current_state_exact_value,
        answer_candidate_surface_text=_runtime._answer_candidate_surface_text,
        build_answer_candidate=_runtime.build_answer_candidate,
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
        build_observation_log=_runtime.build_observation_log,
        reflect_observations=_runtime.reflect_observations,
        build_event_calendar=_runtime.build_event_calendar,
        has_active_current_state_deletion=_runtime.has_active_current_state_deletion,
        is_current_state_question=_runtime.is_current_state_question,
        question_subjects=_runtime._question_subjects,
        question_predicates=_runtime._question_predicates,
        observation_score=_runtime._observation_score,
        event_score=_runtime._event_score,
        select_current_state_entries=_runtime.select_current_state_entries,
        topical_episode_support=_runtime._topical_episode_support,
        select_evidence_entries=_runtime._select_evidence_entries,
        dedupe_observations=_runtime._dedupe_observations,
        observation_evidence_text=_runtime._observation_evidence_text,
        evidence_score=_runtime._evidence_score,
        choose_answer_candidate=_runtime._choose_answer_candidate,
        is_dated_state_question=_runtime._is_dated_state_question,
        is_relative_state_question=_runtime._is_relative_state_question,
        has_ambiguous_relative_state_anchor=_runtime._has_ambiguous_relative_state_anchor,
        has_referential_ambiguity=_runtime._has_referential_ambiguity,
        should_use_current_state_exact_value=_runtime._should_use_current_state_exact_value,
        answer_candidate_surface_text=_runtime._answer_candidate_surface_text,
        build_answer_candidate=_runtime.build_answer_candidate,
        build_run_manifest=build_run_manifest,
        strategy_memory_role=strategy_memory_role,
    )


__all__ = [
    "build_beam_ready_temporal_atom_router_packets",
    "build_dual_store_event_calendar_hybrid_packets",
    "build_memory_system_contract_summary",
    "build_observational_temporal_memory_packets",
]
