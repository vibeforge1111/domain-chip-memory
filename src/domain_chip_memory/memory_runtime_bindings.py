from __future__ import annotations

import re
from datetime import timedelta

from .answer_candidates import build_answer_candidate
from .contracts import AnswerCandidate, JsonDict, NormalizedBenchmarkSample, NormalizedQuestion, NormalizedSession, NormalizedTurn
from .memory_evidence import entry_source_corpus as _entry_source_corpus
from .memory_evidence import observation_evidence_text as _observation_evidence_text
from .memory_evidence import raw_evidence_span as _raw_evidence_span
from .memory_aggregate_support import raw_user_turn_entries as _raw_user_turn_entries_impl
from .memory_aggregate_support import select_aggregate_support_entries as _select_aggregate_support_entries_impl
from .memory_answer_runtime import (
    _choose_answer_candidate,
    _entry_combined_text,
    _evidence_score,
    _extract_place_candidates,
    _infer_aggregate_answer,
    _infer_explanatory_answer,
    _infer_factoid_answer,
    _infer_shared_answer,
    _infer_temporal_answer,
    _infer_yes_no_answer,
    _is_pure_question_turn,
    _observation_score,
    _question_needs_raw_aggregate_context,
    _select_evidence_entries,
    _select_preference_support_entries,
)
from .memory_atom_extraction import extract_memory_atoms
from .memory_atom_routing import atom_score as _atom_score_impl
from .memory_atom_routing import choose_atoms as _choose_atoms_impl
from .memory_observation_runtime import (
    _observation_score,
    _topical_episode_support,
    build_event_calendar,
    build_observation_log,
    reflect_observations,
)
from .memory_extraction import (
    MemoryAtom,
    ObservationEntry,
    _token_bigrams,
    _tokenize,
)
from .memory_queries import _question_predicates, _question_subject, _question_subjects
from .memory_packet_utils import event_score as _event_score
from .memory_packet_utils import question_aware_observation_limits as _question_aware_observation_limits
from .memory_observation_utils import dedupe_observations as _dedupe_observations
from .memory_observation_utils import session_lookup as _session_lookup
from .memory_preferences import is_generic_followup_preference_text as _is_generic_followup_preference_text
from .memory_preferences import is_preference_question as _is_preference_question
from .memory_preferences import is_recommendation_request_text as _is_recommendation_request_text
from .memory_preference_answers import infer_preference_answer as _infer_preference_answer
from .memory_preferences import preference_domain_tokens as _preference_domain_tokens
from .memory_relative_time import has_ambiguous_generic_relative_anchor as _has_ambiguous_generic_relative_anchor
from .memory_relative_time import parse_generic_relative_anchor_phrase as _parse_generic_relative_anchor_phrase
from .memory_rendering import answer_candidate_surface_text as _answer_candidate_surface_text
from .memory_rendering import serialize_session as _serialize_session
from .memory_state_runtime import (
    _dated_state_target_predicates,
    _extract_relative_state_anchor,
    _has_ambiguous_relative_state_anchor,
    _has_referential_ambiguity,
    _infer_anchor_time_from_phrase,
    _infer_dated_state_answer,
    _infer_event_anchored_state_time,
    _infer_relative_state_answer,
    _is_dated_state_question,
    _is_relative_state_question,
    _normalize_relative_state_anchor_phrase,
    _should_use_current_state_exact_value,
    _specialize_clause_carry_first_last_anchor_phrase,
    _specialize_relative_state_anchor_phrase,
)
from .memory_roles import strategy_memory_role
from .memory_updates import has_active_current_state_deletion
from .memory_views import is_current_state_question, select_current_state_entries


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








