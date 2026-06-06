from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
OFFICIAL_LOCOMO_PATH = ROOT / "benchmark_data" / "official" / "LoCoMo" / "data" / "locomo10.json"
OFFICIAL_LONGMEMEVAL_PATH = (
    ROOT / "benchmark_data" / "official" / "LongMemEval" / "data" / "longmemeval_s_cleaned.json"
)

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


_OFFICIAL_LOCOMO_FILES = (
    "tests/test_conversational_index.py",
    "tests/test_typed_temporal_graph_memory.py",
    "tests/test_typed_temporal_graph_retrieval.py",
)

_OFFICIAL_LOCOMO_MEMORY_TESTS = {
    "test_extract_memory_atoms_adds_typed_conversational_events_for_locomo_social_memory",
    "test_locomo_question_relevant_window_surfaces_fifth_slice_object_and_meaning_facts",
    "test_locomo_evidence_and_belief_split_prefers_exact_evidence_for_scoreable_seventh_slice_questions",
    "test_locomo_yes_no_subject_grounding_prefers_no_when_other_speaker_made_object",
    "test_locomo_conv30_temporal_candidates_are_normalized_from_anchor_time",
    "test_locomo_conv30_shared_and_explanatory_candidates_are_synthesized",
    "test_locomo_conv30_temporal_candidates_cover_future_relative_and_anchor_dates",
    "test_locomo_conv26_scoreable_tail_yes_no_candidates_are_preserved",
    "test_summary_synthesis_locomo_unseen_scoreable_questions_prefer_exact_support_over_aggregate_chatter",
    "test_summary_synthesis_locomo_unseen_conv47_recovers_exact_supportable_answers",
    "test_summary_synthesis_locomo_conv49_typed_fact_and_count_questions_recover_exact_answers",
    "test_summary_synthesis_locomo_conv42_temporal_anchor_questions_recover_older_event_grounding",
    "test_summary_synthesis_locomo_conv48_social_memory_questions_recover_exact_lists_and_anchors",
    "test_locomo_question_relevant_window_surfaces_sixth_slice_music_poetry_and_roadtrip_facts",
}

_OFFICIAL_LONGMEMEVAL_TESTS = {
    "tests/test_memory_systems.py::test_longmemeval_factoid_and_abs_candidates_are_short_or_unknown",
    "tests/test_memory_systems.py::test_longmemeval_preference_packets_surface_domain_anchors",
    "tests/test_memory_systems.py::test_longmemeval_aggregate_candidates_cover_count_and_duration_cases",
    "tests/test_memory_systems.py::test_longmemeval_operator_candidates_cover_201_225_frontier_slice",
    "tests/test_memory_systems.py::test_longmemeval_summary_synthesis_candidates_cover_226_250_frontier_slice",
    "tests/test_memory_systems.py::test_longmemeval_preference_candidates_cover_151_175_single_session_lane",
    "tests/test_memory_systems.py::test_longmemeval_aggregate_candidates_cover_176_200_slice",
    "tests/test_providers.py::test_expand_answer_from_context_preserves_longmemeval_summary_synthesis_operator_candidates",
}


def pytest_collection_modifyitems(config, items):
    missing_locomo = not OFFICIAL_LOCOMO_PATH.exists()
    missing_longmemeval = not OFFICIAL_LONGMEMEVAL_PATH.exists()
    if not missing_locomo and not missing_longmemeval:
        return
    skip_official_locomo = (
        pytest.mark.skip(reason=f"official LoCoMO benchmark data not present: {OFFICIAL_LOCOMO_PATH}")
        if missing_locomo
        else None
    )
    skip_official_longmemeval = (
        pytest.mark.skip(reason=f"official LongMemEval benchmark data not present: {OFFICIAL_LONGMEMEVAL_PATH}")
        if missing_longmemeval
        else None
    )
    for item in items:
        nodeid = item.nodeid.replace("\\", "/")
        if skip_official_locomo is not None and nodeid.startswith(_OFFICIAL_LOCOMO_FILES):
            item.add_marker(skip_official_locomo)
            continue
        if skip_official_locomo is not None and nodeid.startswith("tests/test_memory_systems.py::"):
            test_name = nodeid.split("::", 1)[1].split("[", 1)[0]
            if test_name in _OFFICIAL_LOCOMO_MEMORY_TESTS:
                item.add_marker(skip_official_locomo)
                continue
        if skip_official_longmemeval is not None:
            base_nodeid = nodeid.split("[", 1)[0]
            if base_nodeid in _OFFICIAL_LONGMEMEVAL_TESTS:
                item.add_marker(skip_official_longmemeval)
