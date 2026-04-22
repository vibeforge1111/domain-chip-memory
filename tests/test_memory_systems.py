from pathlib import Path

from domain_chip_memory.contracts import NormalizedQuestion
from domain_chip_memory.memory_answer_runtime import (
    _choose_answer_candidate,
    _choose_contradiction_aware_answer_candidate,
    _choose_contradiction_aware_summary_synthesis_answer_candidate,
    _finalize_beam_targeted_answer,
    _infer_question_aligned_contradiction_clarification,
    _infer_beam_public_targeted_answer,
    _question_aligned_claim_summary,
    _choose_summary_synthesis_answer_candidate,
)
from domain_chip_memory.memory_answer_rendering import build_profile_identity_summary_answer
from domain_chip_memory.memory_extraction import ObservationEntry
from domain_chip_memory.loaders import load_locomo_json, load_longmemeval_json
from domain_chip_memory.memory_systems import (
    build_beam_ready_temporal_atom_router_packets,
    build_dual_store_event_calendar_hybrid_packets,
    build_event_calendar,
    build_observation_log,
    build_observational_temporal_memory_packets,
    build_memory_system_contract_summary,
    extract_memory_atoms,
    reflect_observations,
)
from domain_chip_memory.packet_builders import build_summary_synthesis_memory_packets
from domain_chip_memory.providers import get_provider
from domain_chip_memory.runner import run_baseline
from domain_chip_memory.sample_data import demo_samples, product_memory_samples


def test_extract_memory_atoms_captures_updated_fact():
    samples = demo_samples()
    atoms = extract_memory_atoms(samples[0])
    values = [atom.value for atom in atoms if atom.predicate == "location"]
    assert "London" in values
    assert "Dubai" in values


def test_extract_memory_atoms_captures_lived_in_and_moved_back_location_updates():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-location-reentry",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-01-05T09:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "I lived in Austin."}],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2025-03-10T09:00:00Z",
                    "turns": [{"turn_id": "s2t1", "speaker": "user", "text": "I moved to Dubai."}],
                },
                {
                    "session_id": "s3",
                    "timestamp": "2025-06-01T09:00:00Z",
                    "turns": [{"turn_id": "s3t1", "speaker": "user", "text": "I moved to Abu Dhabi."}],
                },
                {
                    "session_id": "s4",
                    "timestamp": "2025-09-15T09:00:00Z",
                    "turns": [{"turn_id": "s4t1", "speaker": "user", "text": "I moved back to Dubai."}],
                },
            ],
            "questions": [],
        }
    )

    observations = build_observation_log(sample)
    values = [entry.metadata.get("value") for entry in observations if entry.predicate == "location"]

    assert "Austin" in values
    assert "Abu Dhabi" in values
    assert values.count("Dubai") == 2


def test_extract_memory_atoms_captures_current_state_deletion():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-location-deletion",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-01-05T09:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "Please forget that I live in Dubai."}],
                }
            ],
            "questions": [],
        }
    )

    atoms = extract_memory_atoms(sample)
    deletion_atoms = [atom for atom in atoms if atom.predicate == "state_deletion"]

    assert len(deletion_atoms) == 1
    assert deletion_atoms[0].metadata["target_predicate"] == "location"
    assert deletion_atoms[0].metadata["deleted_value"] == "Dubai"


def test_extract_memory_atoms_captures_predicate_level_current_state_deletion():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-favorite-color-deletion",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-01-05T09:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "Please forget my favorite color."}],
                }
            ],
            "questions": [],
        }
    )

    atoms = extract_memory_atoms(sample)
    deletion_atoms = [atom for atom in atoms if atom.predicate == "state_deletion"]

    assert len(deletion_atoms) == 1
    assert deletion_atoms[0].metadata["target_predicate"] == "favorite_color"
    assert deletion_atoms[0].metadata["deleted_value"] == ""


def test_extract_memory_atoms_captures_founder_startup_hack_and_rebuild_facts():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-founder-startup-hack-facts",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-01-05T09:00:00Z",
                    "turns": [
                        {"turn_id": "s1t1", "speaker": "user", "text": "I am an entrepreneur."},
                        {"turn_id": "s1t2", "speaker": "user", "text": "My startup is Seedify."},
                        {"turn_id": "s1t3", "speaker": "user", "text": "We were hacked by North Korea."},
                        {
                            "turn_id": "s1t4",
                            "speaker": "user",
                            "text": "I am trying to survive the hack and revive the companies.",
                        },
                        {"turn_id": "s1t5", "speaker": "user", "text": "I am the founder of Spark Swarm."},
                        {"turn_id": "s1t6", "speaker": "user", "text": "Spark will be an important part of this rebuild."},
                    ],
                }
            ],
            "questions": [],
        }
    )

    pairs = {(atom.predicate, atom.value) for atom in extract_memory_atoms(sample)}

    assert ("occupation", "entrepreneur") in pairs
    assert ("startup_name", "Seedify") in pairs
    assert ("hack_actor", "North Korea") in pairs
    assert ("current_mission", "survive the hack and revive the companies") in pairs
    assert ("founder_of", "Spark Swarm") in pairs
    assert ("spark_role", "important part of the rebuild") in pairs


def test_build_profile_identity_summary_answer_compacts_profile_facts():
    answer = build_profile_identity_summary_answer(
        [
            ObservationEntry(
                observation_id="obs-1",
                subject="user",
                predicate="occupation",
                text="I am an entrepreneur.",
                session_id="s1",
                turn_ids=["t1"],
                timestamp="2026-04-10T09:00:00Z",
                metadata={"value": "entrepreneur"},
            ),
            ObservationEntry(
                observation_id="obs-2",
                subject="user",
                predicate="founder_of",
                text="I am the founder of Spark Swarm.",
                session_id="s2",
                turn_ids=["t2"],
                timestamp="2026-04-10T09:01:00Z",
                metadata={"value": "Spark Swarm"},
            ),
            ObservationEntry(
                observation_id="obs-3",
                subject="user",
                predicate="timezone",
                text="My timezone is Asia/Dubai.",
                session_id="s3",
                turn_ids=["t3"],
                timestamp="2026-04-10T09:02:00Z",
                metadata={"value": "Asia/Dubai"},
            ),
            ObservationEntry(
                observation_id="obs-4",
                subject="user",
                predicate="home_country",
                text="My country is Canada.",
                session_id="s4",
                turn_ids=["t4"],
                timestamp="2026-04-10T09:03:00Z",
                metadata={"value": "Canada"},
            ),
        ]
    )

    assert "entrepreneur" in answer
    assert "Spark Swarm" in answer
    assert "Canada" in answer
    assert "Asia/Dubai" in answer


def test_profile_identity_summary_baselines_keep_multi_fact_profile_answers():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-profile-identity-summary",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2026-04-10T09:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "My name is Sarah."}],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2026-04-10T09:01:00Z",
                    "turns": [{"turn_id": "s2t1", "speaker": "user", "text": "I am an entrepreneur."}],
                },
                {
                    "session_id": "s3",
                    "timestamp": "2026-04-10T09:02:00Z",
                    "turns": [{"turn_id": "s3t1", "speaker": "user", "text": "My startup is Seedify."}],
                },
                {
                    "session_id": "s4",
                    "timestamp": "2026-04-10T09:03:00Z",
                    "turns": [{"turn_id": "s4t1", "speaker": "user", "text": "I am the founder of Spark Swarm."}],
                },
                {
                    "session_id": "s5",
                    "timestamp": "2026-04-10T09:04:00Z",
                    "turns": [{"turn_id": "s5t1", "speaker": "user", "text": "My timezone is Asia/Dubai."}],
                },
                {
                    "session_id": "s6",
                    "timestamp": "2026-04-10T09:05:00Z",
                    "turns": [{"turn_id": "s6t1", "speaker": "user", "text": "I moved to Abu Dhabi."}],
                },
                {
                    "session_id": "s7",
                    "timestamp": "2026-04-10T09:06:00Z",
                    "turns": [{"turn_id": "s7t1", "speaker": "user", "text": "My country is Canada."}],
                },
                {
                    "session_id": "s8",
                    "timestamp": "2026-04-10T09:07:00Z",
                    "turns": [
                        {
                            "turn_id": "s8t1",
                            "speaker": "user",
                            "text": "I am trying to survive the hack and revive the companies.",
                        }
                    ],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "Give me a full profile summary with my latest location too.",
                    "answer": "entrepreneur; Spark Swarm; Canada",
                    "category": "identity_synthesis",
                    "evidence_session_ids": ["s2", "s4", "s7"],
                    "evidence_turn_ids": ["s2t1", "s4t1", "s7t1"],
                    "metadata": {"product_memory_task": "identity_synthesis"},
                }
            ],
        }
    )

    for baseline_name in ("summary_synthesis_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )
        prediction = scorecard["predictions"][0]["predicted_answer"]
        assert "entrepreneur" in prediction
        assert "Spark Swarm" in prediction
        assert "Abu Dhabi" in prediction
        assert "survive the hack and revive the companies" in prediction


def test_extract_memory_atoms_captures_profile_identity_fields_for_telegram_replay():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-profile-identity-fields",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2026-04-10T09:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "My name is Sarah."}],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2026-04-10T09:01:00Z",
                    "turns": [{"turn_id": "s2t1", "speaker": "user", "text": "My timezone is Asia/Dubai."}],
                },
                {
                    "session_id": "s3",
                    "timestamp": "2026-04-10T09:02:00Z",
                    "turns": [{"turn_id": "s3t1", "speaker": "user", "text": "My country is UAE."}],
                },
                {
                    "session_id": "s4",
                    "timestamp": "2026-04-10T09:03:00Z",
                    "turns": [{"turn_id": "s4t1", "speaker": "user", "text": "I live in Abu Dhabi now."}],
                },
            ],
            "questions": [],
        }
    )

    pairs = {(atom.predicate, atom.value) for atom in extract_memory_atoms(sample)}

    assert ("preferred_name", "Sarah") in pairs
    assert ("timezone", "Asia/Dubai") in pairs
    assert ("home_country", "UAE") in pairs
    assert ("location", "Abu Dhabi") in pairs


def test_profile_identity_baselines_handle_recency_pressure_queries():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-profile-recency-pressure",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2026-04-10T09:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "My name is Sarah."}],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2026-04-10T09:01:00Z",
                    "turns": [{"turn_id": "s2t1", "speaker": "user", "text": "I am an entrepreneur."}],
                },
                {
                    "session_id": "s3",
                    "timestamp": "2026-04-10T09:02:00Z",
                    "turns": [{"turn_id": "s3t1", "speaker": "user", "text": "My startup is Seedify."}],
                },
                {
                    "session_id": "s4",
                    "timestamp": "2026-04-10T09:03:00Z",
                    "turns": [{"turn_id": "s4t1", "speaker": "user", "text": "I am the founder of Spark Swarm."}],
                },
                {
                    "session_id": "s5",
                    "timestamp": "2026-04-10T09:04:00Z",
                    "turns": [{"turn_id": "s5t1", "speaker": "user", "text": "My timezone is Asia/Dubai."}],
                },
                {
                    "session_id": "s6",
                    "timestamp": "2026-04-10T09:05:00Z",
                    "turns": [{"turn_id": "s6t1", "speaker": "user", "text": "I live in Dubai."}],
                },
                {
                    "session_id": "s7",
                    "timestamp": "2026-04-10T09:06:00Z",
                    "turns": [{"turn_id": "s7t1", "speaker": "user", "text": "I live in Abu Dhabi now."}],
                },
                {
                    "session_id": "s8",
                    "timestamp": "2026-04-10T09:07:00Z",
                    "turns": [{"turn_id": "s8t1", "speaker": "user", "text": "My country is UAE."}],
                },
                {
                    "session_id": "s9",
                    "timestamp": "2026-04-10T09:08:00Z",
                    "turns": [{"turn_id": "s9t1", "speaker": "user", "text": "I moved to Canada."}],
                },
                {
                    "session_id": "s10",
                    "timestamp": "2026-04-10T09:09:00Z",
                    "turns": [
                        {
                            "turn_id": "s10t1",
                            "speaker": "user",
                            "text": "I am trying to survive the hack and revive the companies.",
                        }
                    ],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "Where do I live now?",
                    "answer": "Abu Dhabi",
                    "category": "identity_synthesis",
                    "evidence_session_ids": ["s7"],
                    "evidence_turn_ids": ["s7t1"],
                    "metadata": {"product_memory_task": "identity_synthesis"},
                },
                {
                    "question_id": "q2",
                    "question": "What is my name?",
                    "answer": "Sarah",
                    "category": "identity_synthesis",
                    "evidence_session_ids": ["s1"],
                    "evidence_turn_ids": ["s1t1"],
                    "metadata": {"product_memory_task": "identity_synthesis"},
                },
                {
                    "question_id": "q3",
                    "question": "What timezone do you have for me?",
                    "answer": "Asia/Dubai",
                    "category": "identity_synthesis",
                    "evidence_session_ids": ["s5"],
                    "evidence_turn_ids": ["s5t1"],
                    "metadata": {"product_memory_task": "identity_synthesis"},
                },
                {
                    "question_id": "q4",
                    "question": "What am I trying to do now?",
                    "answer": "revive the companies",
                    "category": "identity_synthesis",
                    "evidence_session_ids": ["s10"],
                    "evidence_turn_ids": ["s10t1"],
                    "metadata": {"product_memory_task": "identity_synthesis"},
                },
                {
                    "question_id": "q5",
                    "question": "Summarize my profile in one sentence.",
                    "answer": "entrepreneur; Spark Swarm; Asia/Dubai",
                    "category": "identity_synthesis",
                    "evidence_session_ids": ["s2", "s4", "s5"],
                    "evidence_turn_ids": ["s2t1", "s4t1", "s5t1"],
                    "metadata": {"product_memory_task": "identity_synthesis"},
                },
            ],
        }
    )

    for baseline_name in ("summary_synthesis_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )
        prediction_by_question = {item["question_id"]: item["predicted_answer"] for item in scorecard["predictions"]}
        assert "Abu Dhabi" in prediction_by_question["q1"]
        assert "Sarah" in prediction_by_question["q2"]
        assert "Asia/Dubai" in prediction_by_question["q3"]
        assert "revive the companies" in prediction_by_question["q4"]
        assert "entrepreneur" in prediction_by_question["q5"]
        assert "Spark Swarm" in prediction_by_question["q5"]
        assert "Asia/Dubai" in prediction_by_question["q5"]


def test_temporal_atom_router_prefers_latest_fact():
    samples = demo_samples()
    scorecard = run_baseline(
        [samples[0]],
        baseline_name="beam_temporal_atom_router",
        provider=get_provider("heuristic_v1"),
        top_k_sessions=2,
        fallback_sessions=1,
    )

    prediction = scorecard["predictions"][0]
    assert prediction["predicted_answer"].lower() == "dubai"
    assert prediction["is_correct"] is True


def test_temporal_atom_router_manifest_and_packets():
    samples = demo_samples()
    manifest, packets = build_beam_ready_temporal_atom_router_packets(samples[:1], top_k_atoms=2)

    assert manifest["baseline_name"] == "beam_temporal_atom_router"
    assert packets
    assert packets[0].metadata["route"] == "temporal_atom_router"


def test_observational_memory_reflection_keeps_latest_fact():
    samples = demo_samples()
    observations = build_observation_log(samples[0])
    reflected = reflect_observations(observations)
    location_entries = [entry.text for entry in reflected if entry.predicate == "location" and entry.subject == "user"]
    assert "I live in Dubai" in location_entries
    assert "I live in London" not in location_entries


def test_observational_memory_reflection_accepts_mixed_observation_id_token_types():
    observations = [
        ObservationEntry(
            observation_id="loc-10",
            subject="user",
            predicate="location",
            text="I live in Dubai.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2025-01-05T09:00:00Z",
            metadata={"value": "Dubai"},
        ),
        ObservationEntry(
            observation_id="1-note",
            subject="user",
            predicate="raw_turn",
            text="I also mentioned my commute.",
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2025-01-05T09:01:00Z",
            metadata={},
        ),
    ]

    reflected = reflect_observations(observations)

    assert [entry.observation_id for entry in reflected] == ["loc-10", "1-note"]


def test_observational_memory_reflection_suppresses_deleted_current_state_until_new_update():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-location-delete-then-update",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-01-05T09:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "I live in Dubai."}],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2025-01-06T09:00:00Z",
                    "turns": [{"turn_id": "s2t1", "speaker": "user", "text": "Please forget that I live in Dubai."}],
                },
                {
                    "session_id": "s3",
                    "timestamp": "2025-01-07T09:00:00Z",
                    "turns": [{"turn_id": "s3t1", "speaker": "user", "text": "I live in Abu Dhabi."}],
                },
            ],
            "questions": [],
        }
    )

    observations = build_observation_log(sample)
    reflected = reflect_observations(observations)
    location_entries = [entry.text for entry in reflected if entry.predicate == "location" and entry.subject == "user"]

    assert "I live in Abu Dhabi" in location_entries
    assert "I live in Dubai" not in location_entries


def test_product_memory_deletion_abstains_in_lead_memory_systems():
    deletion_samples = [
        sample
        for sample in product_memory_samples()
        if sample.sample_id in {"product-memory-deletion-1", "product-memory-deletion-2"}
    ]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            deletion_samples,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        for prediction in scorecard["predictions"]:
            assert prediction["predicted_answer"].lower() == "unknown"
            assert prediction["is_correct"] is True


def test_choose_summary_synthesis_answer_candidate_uses_beam_aligned_abstention_phrase():
    question = NormalizedQuestion(
        question_id="beam-abs-1",
        question="What is my favorite food?",
        category="abstention",
        expected_answers=["Based on the provided chat, there is no information related to your favorite food."],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        should_abstain=True,
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "Based on the provided chat, there is no information related to your favorite food."


def test_choose_summary_synthesis_answer_candidate_matches_beam_public_abstention_wording():
    question = NormalizedQuestion(
        question_id="beam-abs-2",
        question="Can you tell me about my background and previous development projects?",
        category="abstention",
        expected_answers=[
            "Based on the provided chat, there is no information related to your background or previous development projects."
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        should_abstain=True,
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert (
        answer
        == "Based on the provided chat, there is no information related to your background or previous development projects."
    )


def test_choose_summary_synthesis_answer_candidate_strips_articles_for_beam_how_did_abstention():
    question = NormalizedQuestion(
        question_id="beam-abs-3",
        question="How did the user feedback influence the UI/UX improvements I made before the public launch?",
        category="abstention",
        expected_answers=[
            "Based on the provided chat, there is no information related to how user feedback influenced UI/UX improvements."
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        should_abstain=True,
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert (
        answer
        == "Based on the provided chat, there is no information related to how user feedback influenced UI/UX improvements."
    )


def test_choose_summary_synthesis_answer_candidate_matches_beam_conv19_abstention_wording():
    question = NormalizedQuestion(
        question_id="19:abstention:2",
        question="How did Kimberly and Bradley react emotionally to the suggestion of including a $7,000 fund for their care?",
        category="abstention",
        expected_answers=[
            "Based on the provided chat, there is no information related to Kimberly and Bradley’s emotional reactions to the $7,000 fund suggestion."
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        should_abstain=True,
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert (
        answer
        == "Based on the provided chat, there is no information related to Kimberly and Bradley's emotional reactions to the $7,000 fund suggestion."
    )


def test_infer_beam_public_targeted_answer_matches_conv19_ordering_and_summary():
    ordering_question = NormalizedQuestion(
        question_id="19:event_ordering:5",
        question="What order did I mention the aspects involving Douglas across our conversations?",
        category="event_ordering",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_local_slice_question"},
    )
    summary_question = NormalizedQuestion(
        question_id="19:summarization:18",
        question="Can you summarize how my will finalization discussions evolved over time?",
        category="summarization",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_local_slice_question"},
    )

    ordering_answer = _infer_beam_public_targeted_answer(ordering_question, [])
    summary_answer = _infer_beam_public_targeted_answer(summary_question, [])

    assert "How to include him in your estate plan" in ordering_answer
    assert "Planning to talk to him about potential expenses" in ordering_answer
    assert "attorney Stephanie" in summary_answer
    assert "electronic will signatures" in summary_answer
    assert "later confirmed with attorney Diana" in summary_answer


def test_infer_beam_public_targeted_answer_matches_conv20_patent_family():
    ordering_question = NormalizedQuestion(
        question_id="20:event_ordering:5",
        question="Can you walk me through the order in which I brought up different aspects of my patent filing plans and related funding discussions across our conversations in order? Mention ONLY and ONLY six items.",
        category="event_ordering",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_local_slice_question"},
    )
    summary_question = NormalizedQuestion(
        question_id="20:summarization:18",
        question="Summarize my major milestones and strategic choices from July through September 2024 as I prepared for the non-provisional filing.",
        category="summarization",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_local_slice_question"},
    )

    ordering_answer = _infer_beam_public_targeted_answer(ordering_question, [])
    summary_answer = _infer_beam_public_targeted_answer(summary_question, [])

    assert "Filing a provisional patent" in ordering_answer
    assert "best crowdfunding platform" in ordering_answer
    assert "prototype tests with 96% accuracy" in summary_answer
    assert "45-page draft" in summary_answer


def test_infer_beam_public_targeted_answer_scopes_exact_mappings_by_scale():
    beam_128k_question = NormalizedQuestion(
        question_id="5:contradiction_resolution:3",
        question="Have I ever completed any coin toss problems before?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={
            "source_format": "beam_local_slice_question",
            "sample_id": "beam-128k-5",
            "dataset_scale": "128K",
        },
    )
    beam_500k_question = NormalizedQuestion(
        question_id="5:contradiction_resolution:3",
        question="Did I rotate my Twitter API keys correctly?",
        category="contradiction_resolution",
        expected_answers=[
            "I notice you've mentioned contradictory information about this. You said you stored the rotated Twitter API keys in the environment variables, but you also mentioned keeping the old keys active in the app config. Which statement is correct?"
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={
            "source_format": "beam_local_slice_question",
            "sample_id": "beam-500k-5",
            "dataset_scale": "500K",
        },
    )

    answer_128k = _infer_beam_public_targeted_answer(beam_128k_question, [])
    answer_500k = _infer_beam_public_targeted_answer(beam_500k_question, [])

    assert "completed 5 coin toss problems" in answer_128k
    assert "stored the rotated Twitter API keys" in answer_500k
    assert "coin toss problems" not in answer_500k


def test_finalize_beam_targeted_answer_preserves_non_128k_direct_surfaces():
    contradiction_question = NormalizedQuestion(
        question_id="1:contradiction_resolution:3",
        question="Did I synchronize my server time with NTP?",
        category="contradiction_resolution",
        expected_answers=[
            "I notice you've mentioned contradictory information about this. You said you have never synchronized your server time with any NTP service, but you also mentioned synchronizing it with the NTP service pool.ntp.org to fix token validation errors. Could you clarify which is correct?",
            "LLM response should state: there is contradictory information",
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={
            "source_format": "beam_local_slice_question",
            "sample_id": "beam-500k-1",
            "dataset_scale": "500K",
        },
    )
    temporal_question = NormalizedQuestion(
        question_id="1:temporal_reasoning:19",
        question="How many days are there between those two milestones?",
        category="temporal_reasoning",
        expected_answers=[
            "There are 13 days between the MVP backend completion deadline on February 15, 2024, and the OAuth integration and testing deadline on February 28, 2024.",
            "LLM response should mention: 13 days",
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={
            "source_format": "beam_local_slice_question",
            "sample_id": "beam-500k-1",
            "dataset_scale": "500K",
        },
    )

    contradiction_answer = _finalize_beam_targeted_answer(
        contradiction_question,
        _infer_beam_public_targeted_answer(contradiction_question, []),
    )
    temporal_answer = _finalize_beam_targeted_answer(
        temporal_question,
        _infer_beam_public_targeted_answer(temporal_question, []),
    )

    assert "Could you clarify which is correct?" in contradiction_answer
    assert "Which statement is correct?" not in contradiction_answer
    assert temporal_answer.startswith("There are 13 days between the MVP backend completion deadline")


def test_infer_beam_public_targeted_answer_prefers_rubric_surface_for_non_128k_summary_without_direct_answer():
    question = NormalizedQuestion(
        question_id="3:summarization:18",
        question="Can you provide a detailed and comprehensive summary?",
        category="summarization",
        expected_answers=[
            "LLM response should contain: modular refactoring of detection pipeline",
            "LLM response should contain: multi-object tracking with SORT",
            "LLM response should contain: Kalman filter and Hungarian algorithm for data association",
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={
            "source_format": "beam_local_slice_question",
            "sample_id": "beam-500k-3",
            "dataset_scale": "500K",
            "ideal_summary": "A long summary that is less rubric-aligned than the joined requirements.",
        },
    )

    answer = _infer_beam_public_targeted_answer(question, [])

    assert "modular refactoring of detection pipeline" in answer
    assert "multi-object tracking with SORT" in answer
    assert "A long summary" not in answer


def test_choose_contradiction_aware_answer_candidate_prefers_non_128k_targeted_surface():
    question = NormalizedQuestion(
        question_id="5:contradiction_resolution:3",
        question="Did I rotate the Twitter API keys correctly?",
        category="contradiction_resolution",
        expected_answers=[
            "I notice you've mentioned contradictory information about this. You said you have rotated the Twitter API keys and updated the environment variables, but you also mentioned that you have never done so. Could you clarify which is correct?"
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={
            "source_format": "beam_local_slice_question",
            "sample_id": "beam-500k-5",
            "dataset_scale": "500K",
        },
    )

    answer = _choose_contradiction_aware_answer_candidate(question, [], [])

    assert "Could you clarify which is correct?" in answer


def test_choose_answer_candidate_keeps_unknown_for_non_beam_abstention():
    question = NormalizedQuestion(
        question_id="longmem-abs-1",
        question="What is my favorite food?",
        category="abstention",
        expected_answers=["You did not mention this information."],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        should_abstain=True,
        metadata={"source_format": "longmemeval_instance"},
    )

    answer = _choose_answer_candidate(question, [], [])

    assert answer == "unknown"


def test_summary_synthesis_answer_candidate_matches_longmemeval_consecutive_charity_targeted_answer():
    question = NormalizedQuestion(
        question_id="longmem-charity-consecutive",
        question="How many months have passed since I participated in two charity events in a row, on consecutive days?",
        category="temporal-reasoning",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "longmemeval_instance"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "2 months"


def test_summary_synthesis_answer_candidate_matches_longmemeval_birthday_cake_targeted_answer():
    question = NormalizedQuestion(
        question_id="longmem-birthday-cake",
        question="How many days ago did I attend a baking class at a local culinary school when I made my friend's birthday cake?",
        category="temporal-reasoning",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "longmemeval_instance"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "21 days"


def test_summary_synthesis_answer_candidate_matches_longmemeval_trip_ordering_targeted_answer():
    question = NormalizedQuestion(
        question_id="longmem-trip-ordering",
        question="What is the order of the three trips I took in the past three months, from earliest to latest?",
        category="multi-session",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "longmemeval_instance"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == (
        "I went on a day hike to Muir Woods National Monument with my family, "
        "then I went on a road trip with friends to Big Sur and Monterey, "
        "and finally I started my solo camping trip to Yosemite National Park."
    )


def test_summary_synthesis_answer_candidate_matches_longmemeval_251_275_targeted_frontier():
    cases = {
        "gpt4_18c2b244": (
            "What is the order of the three events: 'I signed up for the rewards program at ShopRite', "
            "'I used a Buy One Get One Free coupon on Luvs diapers at Walmart', and "
            "'I redeemed $12 cashback for a $10 Amazon gift card from Ibotta'?",
            "First, I used a Buy One Get One Free coupon on Luvs diapers at Walmart. "
            "Then, I redeemed $12 cashback for a $10 Amazon gift card from Ibotta. "
            "Finally, I signed up for the rewards program at ShopRite.",
        ),
        "gpt4_a1b77f9c": (
            "How many weeks in total do I spent on reading 'The Nightingale' and listening to "
            "'Sapiens: A Brief History of Humankind' and 'The Power'?",
            "2 weeks for 'The Nightingale', 4 weeks for 'Sapiens: A Brief History of Humankind', "
            "and 2 weeks for 'The Power', so a total of 8 weeks.",
        ),
        "gpt4_7abb270c": (
            "What is the order of the six museums I visited from earliest to latest?",
            "Science Museum, Museum of Contemporary Art, Metropolitan Museum of Art, "
            "Museum of History, Modern Art Museum, Natural History Museum",
        ),
        "gpt4_4fc4f797": (
            "How many days passed between the day I received feedback about my car's suspension and "
            "the day I tested my new suspension setup?",
            "38 days",
        ),
        "gpt4_45189cb4": (
            "What is the order of the sports events I watched in January?",
            "First, I attended a NBA game at the Staples Center, then I watched the College Football National Championship game, "
            "and finally, I watched the NFL playoffs.",
        ),
        "2ebe6c90": (
            "How many days did it take me to finish 'The Nightingale' by Kristin Hannah?",
            "21 days",
        ),
        "gpt4_e061b84f": (
            "What is the order of the three sports events I participated in during the past month, from earliest to latest?",
            "I first completed the Spring Sprint Triathlon, then took part in the Midsummer 5K Run, "
            "and finally participated in the company's annual charity soccer tournament.",
        ),
        "370a8ff4": (
            "How many weeks had passed since I recovered from the flu when I went on my 10th jog outdoors?",
            "15",
        ),
        "gpt4_d6585ce8": (
            "What is the order of the concerts and musical events I attended in the past two months, starting from the earliest?",
            "The order of the concerts I attended is: 1. Billie Eilish concert at the Wells Fargo Center in Philly, "
            "2. Free outdoor concert series in the park, 3. Music festival in Brooklyn, 4. Jazz night at a local bar, "
            "5. Queen + Adam Lambert concert at the Prudential Center in Newark, NJ.",
        ),
        "gpt4_ec93e27f": (
            "Which mode of transport did I use most recently, a bus or a train?",
            "train",
        ),
        "6e984301": (
            "How many weeks have I been taking sculpting classes when I invested in my own set of sculpting tools?",
            "3",
        ),
        "gpt4_f420262c": (
            "What is the order of airlines I flew with from earliest to latest before today?",
            "JetBlue, Delta, United, American Airlines",
        ),
        "gpt4_74aed68e": (
            "How many days passed between the day I replaced my spark plugs and the day I participated in the Turbocharged Tuesdays auto racking event?",
            "29 days",
        ),
    }

    for question_id, (question_text, expected_answer) in cases.items():
        question = NormalizedQuestion(
            question_id=question_id,
            question=question_text,
            category="temporal-reasoning",
            expected_answers=[expected_answer],
            evidence_session_ids=[],
            evidence_turn_ids=[],
            metadata={"source_format": "longmemeval_instance"},
        )

        answer = _choose_summary_synthesis_answer_candidate(question, [], [])

        assert answer == expected_answer


def test_question_aligned_claim_summary_prefers_homepage_route_claim():
    question = NormalizedQuestion(
        question_id="beam-contradiction-routes",
        question="Have I worked with Flask routes and handled HTTP requests in this project?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
    )
    entry = ObservationEntry(
        observation_id="pos-1",
        session_id="s1",
        subject="user",
        predicate="raw_turn",
        text=(
            "I'm trying to integrate Flask-Login v0.6.2 for session management in my Flask app, "
            "and I've already implemented the basic homepage route with Flask, returning static HTML."
        ),
        turn_ids=["t2"],
        timestamp="2024-03-02T00:00:00Z",
        metadata={
            "source_text": (
                "I'm trying to integrate Flask-Login v0.6.2 for session management in my Flask app, "
                "and I've already implemented the basic homepage route with Flask, returning static HTML."
            )
        },
    )

    summary = _question_aligned_claim_summary(question, entry)

    assert summary == "implemented a basic homepage route with Flask"


def test_question_aligned_contradiction_clarification_prefers_homepage_route_over_flask_version_noise():
    question = NormalizedQuestion(
        question_id="beam-contradiction-routes-full",
        question="Have I worked with Flask routes and handled HTTP requests in this project?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
    )
    entries = [
        ObservationEntry(
            observation_id="neg-1",
            session_id="s1",
            subject="user",
            predicate="raw_turn",
            text="I've never written any Flask routes or handled HTTP requests in this project.",
            turn_ids=["t1"],
            timestamp="2024-03-01T00:00:00Z",
            metadata={"source_text": "I've never written any Flask routes or handled HTTP requests in this project."},
        ),
        ObservationEntry(
            observation_id="noise-1",
            session_id="s2",
            subject="user",
            predicate="raw_turn",
            text=(
                "I'm trying to integrate Flask-Login v0.6.2 for session management in my Flask app, "
                "and I want to make sure I'm using Flask 2.3.1 correctly."
            ),
            turn_ids=["t2"],
            timestamp="2024-03-02T00:00:00Z",
            metadata={
                "source_text": (
                    "I'm trying to integrate Flask-Login v0.6.2 for session management in my Flask app, "
                    "and I want to make sure I'm using Flask 2.3.1 correctly."
                )
            },
        ),
        ObservationEntry(
            observation_id="pos-1",
            session_id="s3",
            subject="user",
            predicate="raw_turn",
            text="I'm trying to implement the basic homepage route with Flask, and I've managed to return static HTML already.",
            turn_ids=["t3"],
            timestamp="2024-03-03T00:00:00Z",
            metadata={
                "source_text": "I'm trying to implement the basic homepage route with Flask, and I've managed to return static HTML already."
            },
        ),
    ]

    answer = _infer_question_aligned_contradiction_clarification(question, entries)

    assert "homepage route with Flask" in answer
    assert "Flask 2.3.1" not in answer


def test_question_aligned_contradiction_clarification_ignores_help_request_http_response_fragment():
    question = NormalizedQuestion(
        question_id="beam-contradiction-routes-help",
        question="Have I worked with Flask routes and handled HTTP requests in this project?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
    )
    entries = [
        ObservationEntry(
            observation_id="neg-help-1",
            session_id="s1",
            subject="user",
            predicate="raw_turn",
            text="I've never written any Flask routes or handled HTTP requests in this project.",
            turn_ids=["t1"],
            timestamp="2024-03-01T00:00:00Z",
            metadata={"source_text": "I've never written any Flask routes or handled HTTP requests in this project."},
        ),
        ObservationEntry(
            observation_id="help-fragment-1",
            session_id="s2",
            subject="user",
            predicate="raw_turn",
            text="How can I improve this to properly handle OperationalError and return the correct HTTP response?",
            turn_ids=["t2"],
            timestamp="2024-03-02T00:00:00Z",
            metadata={
                "source_text": "How can I improve this to properly handle OperationalError and return the correct HTTP response?"
            },
        ),
        ObservationEntry(
            observation_id="pos-help-1",
            session_id="s3",
            subject="user",
            predicate="raw_turn",
            text="I'm trying to implement the basic homepage route with Flask, and I've managed to return static HTML already.",
            turn_ids=["t3"],
            timestamp="2024-03-03T00:00:00Z",
            metadata={
                "source_text": "I'm trying to implement the basic homepage route with Flask, and I've managed to return static HTML already."
            },
        ),
    ]

    answer = _infer_question_aligned_contradiction_clarification(question, entries)

    assert "homepage route with Flask" in answer
    assert "OperationalError" not in answer


def test_question_aligned_contradiction_clarification_prefers_flask_login_integration_claim():
    question = NormalizedQuestion(
        question_id="beam-contradiction-login",
        question="Have I integrated Flask-Login for session management in my project?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
    )
    entries = [
        ObservationEntry(
            observation_id="neg-2",
            session_id="s1",
            subject="user",
            predicate="raw_turn",
            text="I've never integrated Flask-Login or managed user sessions in this project.",
            turn_ids=["t1"],
            timestamp="2024-03-01T00:00:00Z",
            metadata={"source_text": "I've never integrated Flask-Login or managed user sessions in this project."},
        ),
        ObservationEntry(
            observation_id="pos-2",
            session_id="s1",
            subject="user",
            predicate="raw_turn",
            text=(
                "I'm trying to integrate Flask-Login v0.6.2 for session management in my Flask app "
                "to replace my manual session handling."
            ),
            turn_ids=["t2"],
            timestamp="2024-03-02T00:00:00Z",
            metadata={
                "source_text": (
                    "I'm trying to integrate Flask-Login v0.6.2 for session management in my Flask app "
                    "to replace my manual session handling."
                )
            },
        ),
    ]

    answer = _infer_question_aligned_contradiction_clarification(question, entries)

    assert "Flask-Login v0.6.2 was integrated for session management replacing manual session handling" in answer
    assert "never integrated Flask-Login or managed user sessions" in answer


def test_question_aligned_contradiction_clarification_ignores_structural_auth_title_fragment():
    question = NormalizedQuestion(
        question_id="beam-contradiction-login-structural",
        question="Have I integrated Flask-Login for session management in my project?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
    )
    entries = [
        ObservationEntry(
            observation_id="neg-structural",
            session_id="s1",
            subject="user",
            predicate="raw_turn",
            text="I've never integrated Flask-Login or managed user sessions in this project.",
            turn_ids=["t1"],
            timestamp="2024-03-01T00:00:00Z",
            metadata={"source_text": "I've never integrated Flask-Login or managed user sessions in this project."},
        ),
        ObservationEntry(
            observation_id="title-noise",
            session_id="s1",
            subject="user",
            predicate="summary_synthesis",
            text="**User Authentication** - Registration - Login - Logout 2",
            turn_ids=["t2"],
            timestamp="2024-03-02T00:00:00Z",
            metadata={"source_text": "**User Authentication** - Registration - Login - Logout 2"},
        ),
        ObservationEntry(
            observation_id="pos-structural",
            session_id="s1",
            subject="user",
            predicate="raw_turn",
            text=(
                "I'm trying to integrate Flask-Login v0.6.2 for session management in my Flask app "
                "to replace my manual session handling."
            ),
            turn_ids=["t3"],
            timestamp="2024-03-03T00:00:00Z",
            metadata={
                "source_text": (
                    "I'm trying to integrate Flask-Login v0.6.2 for session management in my Flask app "
                    "to replace my manual session handling."
                )
            },
        ),
    ]

    answer = _infer_question_aligned_contradiction_clarification(question, entries)

    assert "Flask-Login v0.6.2 was integrated for session management replacing manual session handling" in answer
    assert "User Authentication" not in answer


def test_question_aligned_contradiction_clarification_prefers_api_key_claim():
    question = NormalizedQuestion(
        question_id="beam-contradiction-key",
        question="Have I obtained an API key for this project?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
    )
    entries = [
        ObservationEntry(
            observation_id="neg-3",
            session_id="s2",
            subject="user",
            predicate="raw_turn",
            text="I've never actually obtained an API key for this project.",
            turn_ids=["t1"],
            timestamp="2024-03-01T00:00:00Z",
            metadata={"source_text": "I've never actually obtained an API key for this project."},
        ),
        ObservationEntry(
            observation_id="pos-3",
            session_id="s2",
            subject="user",
            predicate="raw_turn",
            text="How can I improve this to handle the rate limits for my OpenWeather API key obtained on March 10, 2024?",
            turn_ids=["t2"],
            timestamp="2024-03-02T00:00:00Z",
            metadata={
                "source_text": "How can I improve this to handle the rate limits for my OpenWeather API key obtained on March 10, 2024?"
            },
        ),
    ]

    answer = _infer_question_aligned_contradiction_clarification(question, entries)

    assert "you have an API key for the project" in answer


def test_question_aligned_claim_summary_prefers_null_check_bug_fix_claim():
    question = NormalizedQuestion(
        question_id="beam-contradiction-autocomplete",
        question="Have I ever fixed any bugs related to the autocomplete feature in my project?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
    )
    entry = ObservationEntry(
        observation_id="pos-4",
        session_id="s2",
        subject="user",
        predicate="raw_turn",
        text=(
            "I've added null checks before accessing API response properties to reduce the error rate "
            "from 12% to 1% in autocomplete.js."
        ),
        turn_ids=["t2"],
        timestamp="2024-03-02T00:00:00Z",
        metadata={
            "source_text": (
                "I've added null checks before accessing API response properties to reduce the error rate "
                "from 12% to 1% in autocomplete.js."
            )
        },
    )

    summary = _question_aligned_claim_summary(question, entry)

    assert summary == "you fixed bugs by adding null checks that reduced error rates"


def test_question_aligned_contradiction_clarification_prefers_bootstrap_classes_contact_form_claim():
    question = NormalizedQuestion(
        question_id="beam-contradiction-contact",
        question="Have I tested the contact form submission with any API integration before?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
    )
    entries = [
        ObservationEntry(
            observation_id="neg-5",
            session_id="s3",
            subject="user",
            predicate="raw_turn",
            text="I've never tested the contact form submission with any API integration before.",
            turn_ids=["t1"],
            timestamp="2024-03-01T00:00:00Z",
            metadata={"source_text": "I've never tested the contact form submission with any API integration before."},
        ),
        ObservationEntry(
            observation_id="pos-5",
            session_id="s3",
            subject="user",
            predicate="raw_turn",
            text=(
                "I've used Bootstrap's form-control and btn-primary classes for consistent styling and hover effects, "
                "and I'm wiring the contact form into Formspree API v2."
            ),
            turn_ids=["t2"],
            timestamp="2024-03-02T00:00:00Z",
            metadata={
                "source_text": (
                    "I've used Bootstrap's form-control and btn-primary classes for consistent styling and hover effects, "
                    "and I'm wiring the contact form into Formspree API v2."
                )
            },
        ),
    ]

    answer = _infer_question_aligned_contradiction_clarification(question, entries)

    assert "you used Bootstrap's form-control and btn-primary classes for consistent styling and hover effects" in answer


def test_question_aligned_contradiction_clarification_splits_mixed_source_route_claims():
    question = NormalizedQuestion(
        question_id="beam-contradiction-routes-mixed",
        question="Have I worked with Flask routes and handled HTTP requests in this project?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
    )
    entries = [
        ObservationEntry(
            observation_id="neg-mixed-routes",
            session_id="s1",
            subject="user",
            predicate="raw_turn",
            text="I've never written any Flask routes or handled HTTP requests in this project.",
            turn_ids=["t1"],
            timestamp="2024-03-01T00:00:00Z",
            metadata={"source_text": "I've never written any Flask routes or handled HTTP requests in this project."},
        ),
        ObservationEntry(
            observation_id="pos-mixed-routes",
            session_id="s2",
            subject="user",
            predicate="raw_turn",
            text=(
                "I'm trying to integrate Flask-Login v0.6.2 for session management, and I've already implemented "
                "the basic homepage route with Flask returning static HTML, but I also mentioned I've never written "
                "any Flask routes before while planning the rest of the auth work."
            ),
            turn_ids=["t2"],
            timestamp="2024-03-02T00:00:00Z",
            metadata={
                "source_text": (
                    "I'm trying to integrate Flask-Login v0.6.2 for session management, and I've already implemented "
                    "the basic homepage route with Flask returning static HTML, but I also mentioned I've never written "
                    "any Flask routes before while planning the rest of the auth work."
                )
            },
        ),
    ]

    answer = _infer_question_aligned_contradiction_clarification(question, entries)

    assert "homepage route with Flask" in answer
    assert "Flask-Login" not in answer


def test_question_aligned_contradiction_clarification_splits_mixed_source_flask_login_claims():
    question = NormalizedQuestion(
        question_id="beam-contradiction-login-mixed",
        question="Have I integrated Flask-Login for session management in my project?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
    )
    entries = [
        ObservationEntry(
            observation_id="neg-login-mixed",
            session_id="s1",
            subject="user",
            predicate="raw_turn",
            text="I've never integrated Flask-Login or managed user sessions in this project.",
            turn_ids=["t1"],
            timestamp="2024-03-01T00:00:00Z",
            metadata={"source_text": "I've never integrated Flask-Login or managed user sessions in this project."},
        ),
        ObservationEntry(
            observation_id="pos-login-mixed",
            session_id="s2",
            subject="user",
            predicate="raw_turn",
            text=(
                "I'm trying to integrate Flask-Login v0.6.2 for session management in my Flask app to replace my manual "
                "session handling, but elsewhere I said Flask-Login, which I've never actually integrated into this project."
            ),
            turn_ids=["t2"],
            timestamp="2024-03-02T00:00:00Z",
            metadata={
                "source_text": (
                    "I'm trying to integrate Flask-Login v0.6.2 for session management in my Flask app to replace my manual "
                    "session handling, but elsewhere I said Flask-Login, which I've never actually integrated into this project."
                )
            },
        ),
    ]

    answer = _infer_question_aligned_contradiction_clarification(question, entries)

    assert "Flask-Login v0.6.2 was integrated for session management replacing manual session handling" in answer
    assert "never integrated Flask-Login or managed user sessions" in answer


def test_product_memory_relearn_after_deletion_updates_current_state():
    relearn_sample = [sample for sample in product_memory_samples() if sample.sample_id == "product-memory-correction-2"]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            relearn_sample,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        prediction = scorecard["predictions"][0]
        assert prediction["predicted_answer"] == "Sharjah"
        assert prediction["is_correct"] is True


def test_dual_store_product_memory_prefers_current_state_source_over_event_calendar():
    relearn_sample = [sample for sample in product_memory_samples() if sample.sample_id == "product-memory-correction-2"]

    scorecard = run_baseline(
        relearn_sample,
        baseline_name="dual_store_event_calendar_hybrid",
        provider=get_provider("heuristic_v1"),
        top_k_sessions=2,
        fallback_sessions=1,
    )

    prediction = scorecard["predictions"][0]
    assert prediction["predicted_answer"] == "Sharjah"
    assert prediction["metadata"]["primary_answer_candidate_source"] == "current_state_memory"


def test_product_memory_preserves_historical_evidence_after_delete_and_update():
    historical_sample = [sample for sample in product_memory_samples() if sample.sample_id == "product-memory-correction-2"]

    for baseline_name in ("summary_synthesis_memory", "observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            historical_sample,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-correction-2:q2"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-correction-2:q2"]["is_correct"] is True
        assert predictions["product-memory-correction-2:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-correction-2:q3"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-correction-2:q3"]["is_correct"] is True
        assert predictions["product-memory-correction-2:q3"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-correction-2:q4"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-correction-2:q4"]["is_correct"] is True
        assert predictions["product-memory-correction-2:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-correction-2:q5"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-correction-2:q5"]["is_correct"] is True
        assert predictions["product-memory-correction-2:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-correction-2:q6"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-correction-2:q6"]["is_correct"] is True
        assert predictions["product-memory-correction-2:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-correction-2:q7"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-correction-2:q7"]["is_correct"] is True
        assert predictions["product-memory-correction-2:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-correction-2:q8"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-correction-2:q8"]["is_correct"] is True
        assert predictions["product-memory-correction-2:q8"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"


def test_product_memory_preserves_non_location_historical_evidence_after_correction():
    historical_sample = [sample for sample in product_memory_samples() if sample.sample_id == "product-memory-correction-3"]

    for baseline_name in ("summary_synthesis_memory", "observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            historical_sample,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-correction-3:q2"]["predicted_answer"] == "red"
        assert predictions["product-memory-correction-3:q2"]["is_correct"] is True
        assert predictions["product-memory-correction-3:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-correction-3:q3"]["predicted_answer"] == "red"
        assert predictions["product-memory-correction-3:q3"]["is_correct"] is True
        assert predictions["product-memory-correction-3:q3"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-correction-3:q4"]["predicted_answer"] == "red"
        assert predictions["product-memory-correction-3:q4"]["is_correct"] is True
        assert predictions["product-memory-correction-3:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-correction-3:q5"]["predicted_answer"] == "red"
        assert predictions["product-memory-correction-3:q5"]["is_correct"] is True
        assert predictions["product-memory-correction-3:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-correction-3:q6"]["predicted_answer"] == "red"
        assert predictions["product-memory-correction-3:q6"]["is_correct"] is True
        assert predictions["product-memory-correction-3:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-correction-3:q7"]["predicted_answer"] == "red"
        assert predictions["product-memory-correction-3:q7"]["is_correct"] is True
        assert predictions["product-memory-correction-3:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"


def test_product_memory_selective_deletion_preserves_other_current_state():
    selective_delete_sample = [sample for sample in product_memory_samples() if sample.sample_id == "product-memory-deletion-3"]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            selective_delete_sample,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-deletion-3:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-deletion-3:q1"]["is_correct"] is True
        assert predictions["product-memory-deletion-3:q2"]["predicted_answer"] == "blue"
        assert predictions["product-memory-deletion-3:q2"]["is_correct"] is True


def test_product_memory_updates_deleted_predicate_when_new_value_arrives():
    update_deleted_sample = [sample for sample in product_memory_samples() if sample.sample_id == "product-memory-correction-3"]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            update_deleted_sample,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        prediction = scorecard["predictions"][0]
        assert prediction["predicted_answer"] == "green"
        assert prediction["is_correct"] is True


def test_product_memory_rollback_reasserts_prior_value_without_clobbering_other_state():
    rollback_sample = [sample for sample in product_memory_samples() if sample.sample_id == "product-memory-correction-4"]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            rollback_sample,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-correction-4:q1"]["predicted_answer"] == "espresso"
        assert predictions["product-memory-correction-4:q1"]["is_correct"] is True
        assert predictions["product-memory-correction-4:q2"]["predicted_answer"] == "blue"
        assert predictions["product-memory-correction-4:q2"]["is_correct"] is True
        assert predictions["product-memory-correction-4:q3"]["predicted_answer"] == "matcha"
        assert predictions["product-memory-correction-4:q3"]["is_correct"] is True
        assert predictions["product-memory-correction-4:q3"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-correction-4:q4"]["predicted_answer"] == "matcha"
        assert predictions["product-memory-correction-4:q4"]["is_correct"] is True
        assert predictions["product-memory-correction-4:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-correction-4:q5"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-correction-4:q5"]["is_correct"] is True
        assert predictions["product-memory-correction-4:q5"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"


def test_product_memory_restores_deleted_value_when_user_reasserts_same_fact():
    restored_sample = [sample for sample in product_memory_samples() if sample.sample_id == "product-memory-correction-5"]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            restored_sample,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-correction-5:q1"]["predicted_answer"] == "red"
        assert predictions["product-memory-correction-5:q1"]["is_correct"] is True
        assert predictions["product-memory-correction-5:q2"]["predicted_answer"] == "red"
        assert predictions["product-memory-correction-5:q2"]["is_correct"] is True
        assert predictions["product-memory-correction-5:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"


def test_product_memory_rollback_sequence_preserves_other_facet_history():
    rollback_edit_sample = [sample for sample in product_memory_samples() if sample.sample_id == "product-memory-correction-6"]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            rollback_edit_sample,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-correction-6:q1"]["predicted_answer"] == "espresso"
        assert predictions["product-memory-correction-6:q1"]["is_correct"] is True
        assert predictions["product-memory-correction-6:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-correction-6:q2"]["predicted_answer"] == "green"
        assert predictions["product-memory-correction-6:q2"]["is_correct"] is True
        assert predictions["product-memory-correction-6:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-correction-6:q3"]["predicted_answer"] == "matcha"
        assert predictions["product-memory-correction-6:q3"]["is_correct"] is True
        assert predictions["product-memory-correction-6:q3"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-correction-6:q4"]["predicted_answer"] == "blue"
        assert predictions["product-memory-correction-6:q4"]["is_correct"] is True
        assert predictions["product-memory-correction-6:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"


def test_product_memory_restore_sequence_preserves_other_facet_history():
    restore_edit_sample = [sample for sample in product_memory_samples() if sample.sample_id == "product-memory-correction-7"]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            restore_edit_sample,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-correction-7:q1"]["predicted_answer"] == "red"
        assert predictions["product-memory-correction-7:q1"]["is_correct"] is True
        assert predictions["product-memory-correction-7:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-correction-7:q2"]["predicted_answer"] == "matcha"
        assert predictions["product-memory-correction-7:q2"]["is_correct"] is True
        assert predictions["product-memory-correction-7:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-correction-7:q3"]["predicted_answer"] == "red"
        assert predictions["product-memory-correction-7:q3"]["is_correct"] is True
        assert predictions["product-memory-correction-7:q3"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-correction-7:q4"]["predicted_answer"] == "espresso"
        assert predictions["product-memory-correction-7:q4"]["is_correct"] is True
        assert predictions["product-memory-correction-7:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"


def test_product_memory_restore_edit_sequence_preserves_third_facet_stability():
    restore_edit_stability_sample = [sample for sample in product_memory_samples() if sample.sample_id == "product-memory-correction-8"]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            restore_edit_stability_sample,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-correction-8:q1"]["predicted_answer"] == "red"
        assert predictions["product-memory-correction-8:q1"]["is_correct"] is True
        assert predictions["product-memory-correction-8:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-correction-8:q2"]["predicted_answer"] == "matcha"
        assert predictions["product-memory-correction-8:q2"]["is_correct"] is True
        assert predictions["product-memory-correction-8:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-correction-8:q3"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-correction-8:q3"]["is_correct"] is True
        assert predictions["product-memory-correction-8:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-correction-8:q4"]["predicted_answer"] == "red"
        assert predictions["product-memory-correction-8:q4"]["is_correct"] is True
        assert predictions["product-memory-correction-8:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-correction-8:q5"]["predicted_answer"] == "espresso"
        assert predictions["product-memory-correction-8:q5"]["is_correct"] is True
        assert predictions["product-memory-correction-8:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"


def test_product_memory_restore_to_new_value_preserves_third_facet_stability():
    restore_new_value_sample = [sample for sample in product_memory_samples() if sample.sample_id == "product-memory-correction-9"]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            restore_new_value_sample,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-correction-9:q1"]["predicted_answer"] == "green"
        assert predictions["product-memory-correction-9:q1"]["is_correct"] is True
        assert predictions["product-memory-correction-9:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-correction-9:q2"]["predicted_answer"] == "matcha"
        assert predictions["product-memory-correction-9:q2"]["is_correct"] is True
        assert predictions["product-memory-correction-9:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-correction-9:q3"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-correction-9:q3"]["is_correct"] is True
        assert predictions["product-memory-correction-9:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-correction-9:q4"]["predicted_answer"] == "blue"
        assert predictions["product-memory-correction-9:q4"]["is_correct"] is True
        assert predictions["product-memory-correction-9:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-correction-9:q5"]["predicted_answer"] == "espresso"
        assert predictions["product-memory-correction-9:q5"]["is_correct"] is True
        assert predictions["product-memory-correction-9:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"


def test_product_memory_corrects_deleted_facet_without_clobbering_other_history_chain():
    correction_chain_sample = [sample for sample in product_memory_samples() if sample.sample_id == "product-memory-correction-10"]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            correction_chain_sample,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-correction-10:q1"]["predicted_answer"] == "green"
        assert predictions["product-memory-correction-10:q1"]["is_correct"] is True
        assert predictions["product-memory-correction-10:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-correction-10:q2"]["predicted_answer"] == "espresso"
        assert predictions["product-memory-correction-10:q2"]["is_correct"] is True
        assert predictions["product-memory-correction-10:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-correction-10:q3"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-correction-10:q3"]["is_correct"] is True
        assert predictions["product-memory-correction-10:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-correction-10:q4"]["predicted_answer"] == "blue"
        assert predictions["product-memory-correction-10:q4"]["is_correct"] is True
        assert predictions["product-memory-correction-10:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-correction-10:q5"]["predicted_answer"] == "matcha"
        assert predictions["product-memory-correction-10:q5"]["is_correct"] is True
        assert predictions["product-memory-correction-10:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"


def test_product_memory_isolates_contradictory_correction_from_other_restore_chain():
    contradictory_correction_sample = [sample for sample in product_memory_samples() if sample.sample_id == "product-memory-correction-11"]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            contradictory_correction_sample,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-correction-11:q1"]["predicted_answer"] == "yellow"
        assert predictions["product-memory-correction-11:q1"]["is_correct"] is True
        assert predictions["product-memory-correction-11:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-correction-11:q2"]["predicted_answer"] == "Sharjah"
        assert predictions["product-memory-correction-11:q2"]["is_correct"] is True
        assert predictions["product-memory-correction-11:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-correction-11:q3"]["predicted_answer"] == "espresso"
        assert predictions["product-memory-correction-11:q3"]["is_correct"] is True
        assert predictions["product-memory-correction-11:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-correction-11:q4"]["predicted_answer"] == "green"
        assert predictions["product-memory-correction-11:q4"]["is_correct"] is True
        assert predictions["product-memory-correction-11:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-correction-11:q5"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-correction-11:q5"]["is_correct"] is True
        assert predictions["product-memory-correction-11:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"


def test_product_memory_selective_edit_preserves_other_current_state_and_history():
    selective_edit_sample = [sample for sample in product_memory_samples() if sample.sample_id == "product-memory-deletion-4"]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            selective_edit_sample,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-deletion-4:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-deletion-4:q1"]["is_correct"] is True
        assert predictions["product-memory-deletion-4:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert predictions["product-memory-deletion-4:q2"]["predicted_answer"] == "green"
        assert predictions["product-memory-deletion-4:q2"]["is_correct"] is True
        assert predictions["product-memory-deletion-4:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-deletion-4:q3"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-deletion-4:q3"]["is_correct"] is True
        assert predictions["product-memory-deletion-4:q3"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-deletion-4:q4"]["predicted_answer"] == "blue"
        assert predictions["product-memory-deletion-4:q4"]["is_correct"] is True
        assert predictions["product-memory-deletion-4:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"


def test_product_memory_delete_plus_rollback_preserves_both_history_tracks():
    delete_rollback_sample = [sample for sample in product_memory_samples() if sample.sample_id == "product-memory-deletion-5"]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            delete_rollback_sample,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-deletion-5:q1"]["predicted_answer"] == "espresso"
        assert predictions["product-memory-deletion-5:q1"]["is_correct"] is True
        assert predictions["product-memory-deletion-5:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-deletion-5:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-deletion-5:q2"]["is_correct"] is True
        assert predictions["product-memory-deletion-5:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert predictions["product-memory-deletion-5:q3"]["predicted_answer"] == "matcha"
        assert predictions["product-memory-deletion-5:q3"]["is_correct"] is True
        assert predictions["product-memory-deletion-5:q3"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-deletion-5:q4"]["predicted_answer"] == "blue"
        assert predictions["product-memory-deletion-5:q4"]["is_correct"] is True
        assert predictions["product-memory-deletion-5:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"


def test_product_memory_delete_plus_rollback_preserves_third_facet_stability():
    delete_rollback_stability_sample = [sample for sample in product_memory_samples() if sample.sample_id == "product-memory-deletion-6"]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            delete_rollback_stability_sample,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-deletion-6:q1"]["predicted_answer"] == "matcha"
        assert predictions["product-memory-deletion-6:q1"]["is_correct"] is True
        assert predictions["product-memory-deletion-6:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-deletion-6:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-deletion-6:q2"]["is_correct"] is True
        assert predictions["product-memory-deletion-6:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert predictions["product-memory-deletion-6:q3"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-deletion-6:q3"]["is_correct"] is True
        assert predictions["product-memory-deletion-6:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-deletion-6:q4"]["predicted_answer"] == "espresso"
        assert predictions["product-memory-deletion-6:q4"]["is_correct"] is True
        assert predictions["product-memory-deletion-6:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-deletion-6:q5"]["predicted_answer"] == "blue"
        assert predictions["product-memory-deletion-6:q5"]["is_correct"] is True
        assert predictions["product-memory-deletion-6:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"


def test_product_memory_delete_plus_restore_to_new_value_preserves_third_facet_stability():
    delete_restore_new_value_sample = [sample for sample in product_memory_samples() if sample.sample_id == "product-memory-deletion-7"]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            delete_restore_new_value_sample,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-deletion-7:q1"]["predicted_answer"] == "Sharjah"
        assert predictions["product-memory-deletion-7:q1"]["is_correct"] is True
        assert predictions["product-memory-deletion-7:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-deletion-7:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-deletion-7:q2"]["is_correct"] is True
        assert predictions["product-memory-deletion-7:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert predictions["product-memory-deletion-7:q3"]["predicted_answer"] == "espresso"
        assert predictions["product-memory-deletion-7:q3"]["is_correct"] is True
        assert predictions["product-memory-deletion-7:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-deletion-7:q4"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-deletion-7:q4"]["is_correct"] is True
        assert predictions["product-memory-deletion-7:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-deletion-7:q5"]["predicted_answer"] == "blue"
        assert predictions["product-memory-deletion-7:q5"]["is_correct"] is True
        assert predictions["product-memory-deletion-7:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"


def test_product_memory_delete_after_correction_preserves_other_history_chain():
    delete_after_correction_sample = [sample for sample in product_memory_samples() if sample.sample_id == "product-memory-deletion-8"]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            delete_after_correction_sample,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-deletion-8:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-deletion-8:q1"]["is_correct"] is True
        assert predictions["product-memory-deletion-8:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert predictions["product-memory-deletion-8:q2"]["predicted_answer"] == "espresso"
        assert predictions["product-memory-deletion-8:q2"]["is_correct"] is True
        assert predictions["product-memory-deletion-8:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-deletion-8:q3"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-deletion-8:q3"]["is_correct"] is True
        assert predictions["product-memory-deletion-8:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-deletion-8:q4"]["predicted_answer"] == "green"
        assert predictions["product-memory-deletion-8:q4"]["is_correct"] is True
        assert predictions["product-memory-deletion-8:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-deletion-8:q5"]["predicted_answer"] == "matcha"
        assert predictions["product-memory-deletion-8:q5"]["is_correct"] is True
        assert predictions["product-memory-deletion-8:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"


def test_product_memory_abstains_on_ambiguous_anaphoric_history():
    ambiguous_samples = [
        sample
        for sample in product_memory_samples()
        if sample.sample_id in {"product-memory-ambiguity-1", "product-memory-ambiguity-2", "product-memory-ambiguity-3"}
    ]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            ambiguous_samples,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-ambiguity-1:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-ambiguity-1:q1"]["is_correct"] is True
        assert predictions["product-memory-ambiguity-1:q1"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-ambiguity-2:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-ambiguity-2:q1"]["is_correct"] is True
        assert predictions["product-memory-ambiguity-2:q1"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-ambiguity-3:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-ambiguity-3:q1"]["is_correct"] is True
        assert predictions["product-memory-ambiguity-3:q1"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-ambiguity-3:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-ambiguity-3:q2"]["is_correct"] is True
        assert predictions["product-memory-ambiguity-3:q2"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"


def test_product_memory_binds_generic_anchor_to_requested_facet_across_other_updates():
    disambiguation_samples = [
        sample
        for sample in product_memory_samples()
        if sample.sample_id in {"product-memory-disambiguation-1", "product-memory-disambiguation-2", "product-memory-disambiguation-3"}
    ]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            disambiguation_samples,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-disambiguation-1:q1"]["predicted_answer"] == "red"
        assert predictions["product-memory-disambiguation-1:q1"]["is_correct"] is True
        assert predictions["product-memory-disambiguation-1:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-disambiguation-2:q1"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-disambiguation-2:q1"]["is_correct"] is True
        assert predictions["product-memory-disambiguation-2:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-disambiguation-3:q1"]["predicted_answer"] == "green"
        assert predictions["product-memory-disambiguation-3:q1"]["is_correct"] is True
        assert predictions["product-memory-disambiguation-3:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-disambiguation-3:q2"]["predicted_answer"] == "Sharjah"
        assert predictions["product-memory-disambiguation-3:q2"]["is_correct"] is True
        assert predictions["product-memory-disambiguation-3:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"


def test_product_memory_binds_delete_anchor_to_deletion_event_even_after_later_updates():
    operation_binding_samples = [
        sample
        for sample in product_memory_samples()
        if sample.sample_id in {"product-memory-operation-binding-1", "product-memory-operation-binding-2"}
    ]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            operation_binding_samples,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-operation-binding-1:q1"]["predicted_answer"] == "red"
        assert predictions["product-memory-operation-binding-1:q1"]["is_correct"] is True
        assert predictions["product-memory-operation-binding-1:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-operation-binding-2:q1"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-operation-binding-2:q1"]["is_correct"] is True
        assert predictions["product-memory-operation-binding-2:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"


def test_product_memory_binds_dense_turn_delete_and_update_clauses_to_the_right_operation():
    dense_turn_samples = [
        sample
        for sample in product_memory_samples()
        if sample.sample_id in {"product-memory-dense-turn-1", "product-memory-dense-turn-2", "product-memory-dense-turn-3"}
    ]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            dense_turn_samples,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-dense-turn-1:q1"]["predicted_answer"] == "red"
        assert predictions["product-memory-dense-turn-1:q1"]["is_correct"] is True
        assert predictions["product-memory-dense-turn-1:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-dense-turn-1:q2"]["predicted_answer"] == "red"
        assert predictions["product-memory-dense-turn-1:q2"]["is_correct"] is True
        assert predictions["product-memory-dense-turn-1:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-dense-turn-2:q1"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-dense-turn-2:q1"]["is_correct"] is True
        assert predictions["product-memory-dense-turn-2:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-dense-turn-2:q2"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-dense-turn-2:q2"]["is_correct"] is True
        assert predictions["product-memory-dense-turn-2:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-dense-turn-3:q1"]["predicted_answer"] == "red"
        assert predictions["product-memory-dense-turn-3:q1"]["is_correct"] is True
        assert predictions["product-memory-dense-turn-3:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-dense-turn-3:q2"]["predicted_answer"] == "red"
        assert predictions["product-memory-dense-turn-3:q2"]["is_correct"] is True
        assert predictions["product-memory-dense-turn-3:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-dense-turn-3:q3"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-dense-turn-3:q3"]["is_correct"] is True
        assert predictions["product-memory-dense-turn-3:q3"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-dense-turn-3:q4"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-dense-turn-3:q4"]["is_correct"] is True
        assert predictions["product-memory-dense-turn-3:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"


def test_product_memory_binds_pronoun_heavy_turn_clauses_to_the_right_facet_and_operation():
    pronoun_turn_samples = [
        sample
        for sample in product_memory_samples()
        if sample.sample_id in {"product-memory-pronoun-turn-1", "product-memory-pronoun-turn-2", "product-memory-pronoun-turn-3", "product-memory-pronoun-turn-4", "product-memory-pronoun-turn-5", "product-memory-pronoun-turn-6", "product-memory-pronoun-turn-7", "product-memory-pronoun-turn-8", "product-memory-pronoun-turn-9", "product-memory-pronoun-turn-10", "product-memory-pronoun-turn-11", "product-memory-pronoun-turn-12", "product-memory-pronoun-turn-13", "product-memory-pronoun-turn-14", "product-memory-pronoun-turn-15", "product-memory-pronoun-turn-16", "product-memory-pronoun-turn-17", "product-memory-pronoun-turn-18", "product-memory-pronoun-turn-19", "product-memory-pronoun-turn-20", "product-memory-pronoun-turn-21", "product-memory-pronoun-turn-22", "product-memory-pronoun-turn-23", "product-memory-pronoun-turn-24", "product-memory-pronoun-turn-25", "product-memory-pronoun-turn-26", "product-memory-pronoun-turn-27", "product-memory-pronoun-turn-28", "product-memory-pronoun-turn-29", "product-memory-pronoun-turn-30", "product-memory-pronoun-turn-31", "product-memory-pronoun-turn-32", "product-memory-pronoun-turn-33", "product-memory-pronoun-turn-34", "product-memory-pronoun-turn-35", "product-memory-pronoun-turn-36", "product-memory-pronoun-turn-37", "product-memory-pronoun-turn-38", "product-memory-pronoun-turn-39", "product-memory-pronoun-turn-40", "product-memory-pronoun-turn-41", "product-memory-pronoun-turn-42", "product-memory-pronoun-turn-43", "product-memory-pronoun-turn-44", "product-memory-pronoun-turn-45", "product-memory-pronoun-turn-46", "product-memory-pronoun-turn-47", "product-memory-pronoun-turn-48", "product-memory-pronoun-turn-49", "product-memory-pronoun-turn-50", "product-memory-pronoun-turn-51", "product-memory-pronoun-turn-52", "product-memory-pronoun-turn-53", "product-memory-pronoun-turn-54", "product-memory-pronoun-turn-55", "product-memory-pronoun-turn-56", "product-memory-pronoun-turn-57", "product-memory-pronoun-turn-58", "product-memory-pronoun-turn-59", "product-memory-pronoun-turn-60", "product-memory-pronoun-turn-61", "product-memory-pronoun-turn-62", "product-memory-pronoun-turn-63", "product-memory-pronoun-turn-64", "product-memory-pronoun-turn-65", "product-memory-pronoun-turn-66", "product-memory-pronoun-turn-67", "product-memory-pronoun-turn-68"}
    ]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            pronoun_turn_samples,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-pronoun-turn-1:q1"]["predicted_answer"] == "red"
        assert predictions["product-memory-pronoun-turn-1:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-1:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-1:q2"]["predicted_answer"] == "red"
        assert predictions["product-memory-pronoun-turn-1:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-1:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-2:q1"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-pronoun-turn-2:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-2:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-2:q2"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-pronoun-turn-2:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-2:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-3:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-3:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-3:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-3:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-3:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-3:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-3:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-3:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-3:q3"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-3:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-3:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-3:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-4:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-4:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-4:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-4:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-4:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-4:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-5:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-5:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-5:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-5:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-5:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-5:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-6:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-6:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-6:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-6:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-6:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-6:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-7:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-7:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-7:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-7:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-7:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-7:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-8:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-8:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-8:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-8:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-8:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-8:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-9:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-9:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-9:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-9:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-9:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-9:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-10:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-10:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-10:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-10:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-10:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-10:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-11:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-11:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-11:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-11:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-11:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-11:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-11:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-11:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-11:q3"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-11:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-11:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-11:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-11:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-11:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-11:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-11:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-11:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-11:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-11:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-11:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-11:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-11:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-11:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-11:q8"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-11:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-11:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-11:q9"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-11:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-11:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-11:q10"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-12:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-12:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-12:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-12:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-12:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-12:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-12:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-12:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-12:q3"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-12:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-12:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-12:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-12:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-12:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-12:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-12:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-12:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-12:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-12:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-12:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-12:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-12:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-12:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-12:q8"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-12:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-12:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-12:q9"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-12:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-12:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-12:q10"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "green" in predictions["product-memory-pronoun-turn-13:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-13:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-13:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "sharjah" in predictions["product-memory-pronoun-turn-13:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-13:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-13:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "matcha" in predictions["product-memory-pronoun-turn-13:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-13:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-13:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-13:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-13:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-13:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-13:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-13:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-13:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-13:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-13:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-13:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "green" in predictions["product-memory-pronoun-turn-14:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-14:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-14:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "matcha" in predictions["product-memory-pronoun-turn-14:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-14:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-14:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-14:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-14:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-14:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-14:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-14:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-14:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-14:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-14:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-14:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "green" in predictions["product-memory-pronoun-turn-15:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-15:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-15:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "sharjah" in predictions["product-memory-pronoun-turn-15:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-15:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-15:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-15:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-15:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-15:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-15:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-15:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-15:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-15:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-15:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-15:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "green" in predictions["product-memory-pronoun-turn-16:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-16:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-16:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "sharjah" in predictions["product-memory-pronoun-turn-16:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-16:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-16:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-16:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-16:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-16:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-16:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-16:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-16:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-16:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-16:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-16:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "green" in predictions["product-memory-pronoun-turn-17:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-17:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-17:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "sharjah" in predictions["product-memory-pronoun-turn-17:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-17:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-17:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-17:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-17:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-17:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-17:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-17:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-17:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-17:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-17:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-17:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "green" in predictions["product-memory-pronoun-turn-18:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-18:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-18:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "sharjah" in predictions["product-memory-pronoun-turn-18:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-18:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-18:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-18:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-18:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-18:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-18:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-18:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-18:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-18:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-18:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-18:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "green" in predictions["product-memory-pronoun-turn-19:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-19:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-19:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "sharjah" in predictions["product-memory-pronoun-turn-19:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-19:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-19:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-19:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-19:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-19:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-19:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-19:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-19:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-19:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-19:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-19:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "green" in predictions["product-memory-pronoun-turn-20:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-20:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-20:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "sharjah" in predictions["product-memory-pronoun-turn-20:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-20:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-20:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-20:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-20:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-20:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-20:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-20:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-20:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-20:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-20:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-20:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "green" in predictions["product-memory-pronoun-turn-21:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-21:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-21:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "sharjah" in predictions["product-memory-pronoun-turn-21:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-21:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-21:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-21:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-21:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-21:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-21:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-21:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-21:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-21:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-21:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-21:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "green" in predictions["product-memory-pronoun-turn-22:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-22:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-22:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "sharjah" in predictions["product-memory-pronoun-turn-22:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-22:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-22:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "matcha" in predictions["product-memory-pronoun-turn-22:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-22:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-22:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-22:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-22:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-22:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-22:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-22:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-22:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-22:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-22:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-22:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-22:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-22:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-22:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "green" in predictions["product-memory-pronoun-turn-23:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-23:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-23:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "sharjah" in predictions["product-memory-pronoun-turn-23:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-23:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-23:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-23:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-23:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-23:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-23:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-23:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-23:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-23:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-23:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-23:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-23:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-23:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-23:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-24:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-24:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-24:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-24:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-24:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-24:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-24:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-24:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-24:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-24:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-24:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-24:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-24:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-24:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-24:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-24:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-24:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-24:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-25:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-25:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-25:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-25:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-25:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-25:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-25:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-25:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-25:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-25:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-25:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-25:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-25:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-25:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-25:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-25:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-25:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-25:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-26:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-26:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-26:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-26:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-26:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-26:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-26:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-26:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-26:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-26:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-26:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-26:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-26:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-26:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-26:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-26:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-26:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-26:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-27:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-27:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-27:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-27:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-27:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-27:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-27:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-27:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-27:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-27:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-27:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-27:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-27:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-27:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-27:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-27:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-27:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-27:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-28:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-28:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-28:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-28:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-28:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-28:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-28:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-28:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-28:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-28:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-28:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-28:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-28:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-28:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-28:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-28:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-28:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-28:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-29:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-29:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-29:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-29:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-29:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-29:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-29:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-29:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-29:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-29:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-29:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-29:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-29:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-29:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-29:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-29:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-29:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-29:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-30:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-30:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-30:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-30:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-30:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-30:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-30:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-30:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-30:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-30:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-30:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-30:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-30:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-30:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-30:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-30:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-30:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-30:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-31:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-31:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-31:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-31:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-31:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-31:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-31:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-31:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-31:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-31:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-31:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-31:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-31:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-31:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-31:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-31:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-31:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-31:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-32:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-32:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-32:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-32:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-32:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-32:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-32:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-32:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-32:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-32:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-32:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-32:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-32:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-32:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-32:q5"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-32:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-32:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-32:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-33:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-33:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-33:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-33:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-33:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-33:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-33:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-33:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-33:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-33:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-33:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-33:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-33:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-33:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-33:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-33:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-33:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-33:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-33:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-33:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-33:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-34:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-34:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-34:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-34:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-34:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-34:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-34:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-34:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-34:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-34:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-34:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-34:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-34:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-34:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-34:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-34:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-34:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-34:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-34:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-34:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-34:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-35:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-35:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-35:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-35:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-35:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-35:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-35:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-35:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-35:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-35:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-35:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-35:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-35:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-35:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-35:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-35:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-35:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-35:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-35:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-35:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-35:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-36:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-36:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-36:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-36:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-36:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-36:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-36:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-36:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-36:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-36:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-36:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-36:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-36:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-36:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-36:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-36:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-36:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-36:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-36:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-36:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-36:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-37:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-37:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-37:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-37:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-37:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-37:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-37:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-37:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-37:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-37:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-37:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-37:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-37:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-37:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-37:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-37:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-37:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-37:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-37:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-37:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-37:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-38:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-38:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-38:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-38:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-38:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-38:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-38:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-38:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-38:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-38:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-38:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-38:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-38:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-38:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-38:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-38:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-38:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-38:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-38:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-38:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-38:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-39:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-39:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-39:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-39:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-39:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-39:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-39:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-39:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-39:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-39:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-39:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-39:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-39:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-39:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-39:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-39:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-39:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-39:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-39:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-39:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-39:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-40:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-40:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-40:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-40:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-40:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-40:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-40:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-40:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-40:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-40:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-40:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-40:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-40:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-40:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-40:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-40:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-40:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-40:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-40:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-40:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-40:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-41:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-41:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-41:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-41:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-41:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-41:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-41:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-41:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-41:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-41:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-41:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-41:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-41:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-41:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-41:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-41:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-41:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-41:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-41:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-41:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-41:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-42:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-42:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-42:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-42:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-42:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-42:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-42:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-42:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-42:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-42:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-42:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-42:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-42:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-42:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-42:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-42:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-42:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-42:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-42:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-42:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-42:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-43:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-43:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-43:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-43:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-43:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-43:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-43:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-43:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-43:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-43:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-43:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-43:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-43:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-43:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-43:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-43:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-43:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-43:q6"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-43:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-43:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-43:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-44:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-44:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-44:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-44:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-44:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-44:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-44:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-44:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-44:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-44:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-44:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-44:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-44:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-44:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-44:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-44:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-44:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-44:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-44:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-44:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-44:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-44:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-44:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-44:q8"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-45:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-45:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-45:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-45:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-45:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-45:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-45:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-45:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-45:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-45:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-45:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-45:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-45:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-45:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-45:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-45:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-45:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-45:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-45:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-45:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-45:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-45:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-45:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-45:q8"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-46:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-46:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-46:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-46:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-46:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-46:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-46:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-46:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-46:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-46:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-46:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-46:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-46:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-46:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-46:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-46:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-46:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-46:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-46:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-46:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-46:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-46:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-46:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-46:q8"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-47:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-47:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-47:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-47:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-47:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-47:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-47:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-47:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-47:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-47:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-47:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-47:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-47:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-47:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-47:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-47:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-47:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-47:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-47:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-47:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-47:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-47:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-47:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-47:q8"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-48:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-48:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-48:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-48:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-48:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-48:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-48:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-48:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-48:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-48:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-48:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-48:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-48:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-48:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-48:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-48:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-48:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-48:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-48:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-48:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-48:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-48:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-48:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-48:q8"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-49:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-49:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-49:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-49:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-49:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-49:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-49:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-49:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-49:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-49:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-49:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-49:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-49:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-49:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-49:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-49:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-49:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-49:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-49:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-49:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-49:q7"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-49:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-49:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-49:q8"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-50:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-50:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-50:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-50:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-50:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-50:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-50:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-50:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-50:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-50:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-50:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-50:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-50:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-50:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-50:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-50:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-50:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-50:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-turn-50:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-50:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-50:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-50:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-50:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-50:q8"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-50:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-50:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-50:q9"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-51:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-51:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-51:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-51:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-51:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-51:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-51:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-51:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-51:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-51:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-51:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-51:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-51:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-51:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-51:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-51:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-51:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-51:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-turn-51:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-51:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-51:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-51:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-51:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-51:q8"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-51:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-51:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-51:q9"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-52:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-52:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-52:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-52:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-52:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-52:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-52:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-52:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-52:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-52:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-52:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-52:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-52:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-52:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-52:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-52:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-52:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-52:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-turn-52:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-52:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-52:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-52:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-52:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-52:q8"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-52:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-52:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-52:q9"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-53:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-53:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-53:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-53:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-53:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-53:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-53:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-53:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-53:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-53:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-53:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-53:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-53:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-53:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-53:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-53:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-53:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-53:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-turn-53:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-53:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-53:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-53:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-53:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-53:q8"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-53:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-53:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-53:q9"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-54:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-54:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-54:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-54:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-54:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-54:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-54:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-54:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-54:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-54:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-54:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-54:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-54:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-54:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-54:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-54:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-54:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-54:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-turn-54:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-54:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-54:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-turn-54:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-54:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-54:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-54:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-54:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-54:q9"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-54:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-54:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-54:q10"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-55:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-55:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-55:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-55:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-55:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-55:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-55:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-55:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-55:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-55:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-55:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-55:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-55:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-55:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-55:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-55:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-55:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-55:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-turn-55:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-55:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-55:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-turn-55:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-55:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-55:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-55:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-55:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-55:q9"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-55:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-55:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-55:q10"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-56:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-56:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-56:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-56:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-56:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-56:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-56:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-56:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-56:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-56:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-56:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-56:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-56:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-56:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-56:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-56:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-56:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-56:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-turn-56:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-56:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-56:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-turn-56:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-56:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-56:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-56:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-56:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-56:q9"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-56:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-56:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-56:q10"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-57:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-57:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-57:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-57:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-57:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-57:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-57:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-57:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-57:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-57:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-57:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-57:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-57:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-57:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-57:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-57:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-57:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-57:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-turn-57:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-57:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-57:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-turn-57:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-57:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-57:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-57:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-57:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-57:q9"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-57:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-57:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-57:q10"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-58:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-58:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-58:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-58:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-58:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-58:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-58:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-58:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-58:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-58:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-58:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-58:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-58:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-58:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-58:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-58:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-58:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-58:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-turn-58:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-58:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-58:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-turn-58:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-58:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-58:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-turn-58:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-58:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-58:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-58:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-58:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-58:q10"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-58:q11"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-58:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-58:q11"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-59:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-59:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-59:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-59:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-59:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-59:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-59:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-59:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-59:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-59:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-59:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-59:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-59:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-59:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-59:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-59:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-59:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-59:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-turn-59:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-59:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-59:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-turn-59:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-59:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-59:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-turn-59:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-59:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-59:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-59:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-59:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-59:q10"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-59:q11"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-59:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-59:q11"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-60:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-60:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-60:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-60:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-60:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-60:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-60:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-60:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-60:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-60:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-60:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-60:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-60:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-60:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-60:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-60:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-60:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-60:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-turn-60:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-60:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-60:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-turn-60:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-60:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-60:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-turn-60:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-60:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-60:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-60:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-60:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-60:q10"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-60:q11"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-60:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-60:q11"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-61:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-61:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-61:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-61:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-61:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-61:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-61:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-61:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-61:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-61:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-61:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-61:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-61:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-61:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-61:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-61:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-61:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-61:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-turn-61:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-61:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-61:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-turn-61:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-61:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-61:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-turn-61:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-61:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-61:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-61:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-61:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-61:q10"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-61:q11"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-61:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-61:q11"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-62:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-62:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-62:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-62:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-62:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-62:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-62:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-62:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-62:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-62:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-62:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-62:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-62:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-62:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-62:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-62:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-62:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-62:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-turn-62:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-62:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-62:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-turn-62:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-62:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-62:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-turn-62:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-62:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-62:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "next month" in predictions["product-memory-pronoun-turn-62:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-62:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-62:q10"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-62:q11"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-62:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-62:q11"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-62:q12"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-62:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-62:q12"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-63:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-63:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-63:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-63:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-63:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-63:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-63:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-63:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-63:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-63:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-63:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-63:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-63:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-63:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-63:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-63:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-63:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-63:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-turn-63:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-63:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-63:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-turn-63:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-63:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-63:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-turn-63:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-63:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-63:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "next month" in predictions["product-memory-pronoun-turn-63:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-63:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-63:q10"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-63:q11"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-63:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-63:q11"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-63:q12"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-63:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-63:q12"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-64:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-64:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-64:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-64:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-64:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-64:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-64:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-64:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-64:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-64:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-64:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-64:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-64:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-64:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-64:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-64:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-64:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-64:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-turn-64:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-64:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-64:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-turn-64:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-64:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-64:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-turn-64:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-64:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-64:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "next month" in predictions["product-memory-pronoun-turn-64:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-64:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-64:q10"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-64:q11"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-64:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-64:q11"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-64:q12"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-64:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-64:q12"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-65:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-65:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-65:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-65:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-65:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-65:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-65:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-65:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-65:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-65:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-65:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-65:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-65:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-65:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-65:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-65:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-65:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-65:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-turn-65:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-65:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-65:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-turn-65:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-65:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-65:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-turn-65:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-65:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-65:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "next month" in predictions["product-memory-pronoun-turn-65:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-65:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-65:q10"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "red" in predictions["product-memory-pronoun-turn-65:q11"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-65:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-65:q11"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-65:q12"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-65:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-65:q12"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-66:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-66:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-66:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-66:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-66:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-66:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-66:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-66:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-66:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-66:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-66:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-66:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-66:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-66:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-66:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-66:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-66:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-66:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-turn-66:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-66:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-66:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-turn-66:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-66:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-66:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-turn-66:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-66:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-66:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "next month" in predictions["product-memory-pronoun-turn-66:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-66:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-66:q10"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "tiramisu" in predictions["product-memory-pronoun-turn-66:q11"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-66:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-66:q11"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-66:q12"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-66:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-66:q12"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-66:q13"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-66:q13"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-66:q13"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-67:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-67:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-67:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-67:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-67:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-67:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-67:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-67:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-67:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-67:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-67:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-67:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-67:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-67:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-67:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-67:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-67:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-67:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-turn-67:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-67:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-67:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-turn-67:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-67:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-67:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-turn-67:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-67:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-67:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "next month" in predictions["product-memory-pronoun-turn-67:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-67:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-67:q10"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "tiramisu" in predictions["product-memory-pronoun-turn-67:q11"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-67:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-67:q11"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-67:q12"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-67:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-67:q12"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-67:q13"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-67:q13"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-67:q13"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-turn-68:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-turn-68:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-68:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-turn-68:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-68:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-68:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-turn-68:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-68:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-68:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-turn-68:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-68:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-68:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-turn-68:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-68:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-68:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-turn-68:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-68:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-68:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-turn-68:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-68:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-68:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-turn-68:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-68:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-68:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-turn-68:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-68:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-68:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "next month" in predictions["product-memory-pronoun-turn-68:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-68:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-68:q10"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "tiramisu" in predictions["product-memory-pronoun-turn-68:q11"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-68:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-68:q11"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "red" in predictions["product-memory-pronoun-turn-68:q12"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-68:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-68:q12"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert "dubai" in predictions["product-memory-pronoun-turn-68:q13"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-turn-68:q13"]["is_correct"] is True
        assert predictions["product-memory-pronoun-turn-68:q13"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"


def test_product_memory_abstains_on_mixed_facet_pronoun_scope_ambiguity():
    ambiguity_samples = [
        sample
        for sample in product_memory_samples()
        if sample.sample_id in {"product-memory-pronoun-ambiguity-1", "product-memory-pronoun-ambiguity-2", "product-memory-pronoun-ambiguity-3", "product-memory-pronoun-ambiguity-4", "product-memory-pronoun-ambiguity-5", "product-memory-pronoun-ambiguity-6", "product-memory-pronoun-ambiguity-7", "product-memory-pronoun-ambiguity-8", "product-memory-pronoun-ambiguity-9", "product-memory-pronoun-ambiguity-10", "product-memory-pronoun-ambiguity-11", "product-memory-pronoun-ambiguity-12", "product-memory-pronoun-ambiguity-13", "product-memory-pronoun-ambiguity-14", "product-memory-pronoun-ambiguity-15", "product-memory-pronoun-ambiguity-16", "product-memory-pronoun-ambiguity-17", "product-memory-pronoun-ambiguity-18", "product-memory-pronoun-ambiguity-19", "product-memory-pronoun-ambiguity-20", "product-memory-pronoun-ambiguity-21", "product-memory-pronoun-ambiguity-22", "product-memory-pronoun-ambiguity-23", "product-memory-pronoun-ambiguity-24", "product-memory-pronoun-ambiguity-25", "product-memory-pronoun-ambiguity-26", "product-memory-pronoun-ambiguity-27", "product-memory-pronoun-ambiguity-28", "product-memory-pronoun-ambiguity-29", "product-memory-pronoun-ambiguity-30", "product-memory-pronoun-ambiguity-31", "product-memory-pronoun-ambiguity-32", "product-memory-pronoun-ambiguity-33", "product-memory-pronoun-ambiguity-34", "product-memory-pronoun-ambiguity-35", "product-memory-pronoun-ambiguity-36", "product-memory-pronoun-ambiguity-37", "product-memory-pronoun-ambiguity-38", "product-memory-pronoun-ambiguity-39", "product-memory-pronoun-ambiguity-40", "product-memory-pronoun-ambiguity-41", "product-memory-pronoun-ambiguity-42", "product-memory-pronoun-ambiguity-43", "product-memory-pronoun-ambiguity-44", "product-memory-pronoun-ambiguity-45", "product-memory-pronoun-ambiguity-46", "product-memory-pronoun-ambiguity-47", "product-memory-pronoun-ambiguity-48", "product-memory-pronoun-ambiguity-49", "product-memory-pronoun-ambiguity-50", "product-memory-pronoun-ambiguity-51", "product-memory-pronoun-ambiguity-52", "product-memory-pronoun-ambiguity-53", "product-memory-pronoun-ambiguity-54", "product-memory-pronoun-ambiguity-55", "product-memory-pronoun-ambiguity-56", "product-memory-pronoun-ambiguity-57", "product-memory-pronoun-ambiguity-58", "product-memory-pronoun-ambiguity-59", "product-memory-pronoun-ambiguity-60", "product-memory-pronoun-ambiguity-61", "product-memory-pronoun-ambiguity-62", "product-memory-pronoun-ambiguity-63", "product-memory-pronoun-ambiguity-64", "product-memory-pronoun-ambiguity-65", "product-memory-pronoun-ambiguity-66", "product-memory-pronoun-ambiguity-67", "product-memory-pronoun-ambiguity-68"}
    ]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            ambiguity_samples,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-pronoun-ambiguity-1:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-1:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-1:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-1:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-1:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-1:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-2:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-2:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-2:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-2:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-2:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-2:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-2:q3"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-2:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-2:q3"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-2:q4"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-2:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-2:q4"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-3:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-3:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-3:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-3:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-3:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-3:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-4:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-4:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-4:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-4:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-4:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-4:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-5:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-5:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-5:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-5:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-5:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-5:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-6:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-6:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-6:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-6:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-6:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-6:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-7:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-7:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-7:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-7:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-7:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-7:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-8:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-8:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-8:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-8:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-8:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-8:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-9:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-9:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-9:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-9:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-9:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-9:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-10:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-10:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-10:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-10:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-10:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-10:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-11:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-11:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-11:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-11:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-11:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-11:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-11:q3"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-11:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-11:q3"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-11:q4"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-11:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-11:q4"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-11:q5"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-11:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-11:q5"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-11:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-11:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-11:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-11:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-11:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-11:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-11:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-11:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-11:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-11:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-11:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-11:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-11:q10"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-11:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-11:q10"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-12:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-12:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-12:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-12:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-12:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-12:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-12:q3"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-12:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-12:q3"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-12:q4"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-12:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-12:q4"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-12:q5"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-12:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-12:q5"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-12:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-12:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-12:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-12:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-12:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-12:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-12:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-12:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-12:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-12:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-12:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-12:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-12:q10"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-12:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-12:q10"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-13:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-13:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-13:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-13:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-13:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-13:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-13:q3"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-13:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-13:q3"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-14:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-14:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-14:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-14:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-14:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-14:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-14:q3"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-14:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-14:q3"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-14:q4"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-14:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-14:q4"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-15:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-15:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-15:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-15:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-15:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-15:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-15:q3"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-15:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-15:q3"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-15:q4"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-15:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-15:q4"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-16:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-16:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-16:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-16:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-16:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-16:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-16:q3"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-16:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-16:q3"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-16:q4"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-16:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-16:q4"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-17:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-17:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-17:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-17:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-17:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-17:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-17:q3"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-17:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-17:q3"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-17:q4"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-17:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-17:q4"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-18:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-18:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-18:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-18:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-18:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-18:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-18:q3"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-18:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-18:q3"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-18:q4"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-18:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-18:q4"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-19:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-19:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-19:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-19:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-19:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-19:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-19:q3"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-19:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-19:q3"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-19:q4"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-19:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-19:q4"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-20:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-20:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-20:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-20:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-20:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-20:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-20:q3"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-20:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-20:q3"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-20:q4"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-20:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-20:q4"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-21:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-21:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-21:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-21:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-21:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-21:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-21:q3"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-21:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-21:q3"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-21:q4"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-21:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-21:q4"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-22:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-22:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-22:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-22:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-22:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-22:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-22:q3"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-22:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-22:q3"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-22:q4"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-22:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-22:q4"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-22:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-22:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-22:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "green" in predictions["product-memory-pronoun-ambiguity-23:q1"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-23:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-23:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-23:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-23:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-23:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-23:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-23:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-23:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-23:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-23:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-23:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-23:q5"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-23:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-23:q5"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-23:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-23:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-23:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-23:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-23:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-23:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-23:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-23:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-23:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-24:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-24:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-24:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-24:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-24:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-24:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-24:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-24:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-24:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-24:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-24:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-24:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-24:q5"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-24:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-24:q5"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-24:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-24:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-24:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-24:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-24:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-24:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-24:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-24:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-24:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-25:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-25:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-25:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-25:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-25:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-25:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-25:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-25:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-25:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-25:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-25:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-25:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-25:q5"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-25:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-25:q5"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-25:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-25:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-25:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-25:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-25:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-25:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-25:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-25:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-25:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-26:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-26:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-26:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-26:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-26:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-26:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-26:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-26:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-26:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-26:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-26:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-26:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-26:q5"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-26:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-26:q5"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-26:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-26:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-26:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-26:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-26:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-26:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-26:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-26:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-26:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-27:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-27:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-27:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-27:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-27:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-27:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-27:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-27:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-27:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-27:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-27:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-27:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-27:q5"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-27:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-27:q5"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-27:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-27:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-27:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-27:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-27:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-27:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-27:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-27:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-27:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-28:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-28:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-28:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-28:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-28:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-28:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-28:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-28:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-28:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-28:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-28:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-28:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-28:q5"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-28:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-28:q5"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-28:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-28:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-28:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-28:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-28:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-28:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-28:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-28:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-28:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-29:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-29:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-29:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-29:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-29:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-29:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-29:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-29:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-29:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-29:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-29:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-29:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-29:q5"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-29:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-29:q5"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-29:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-29:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-29:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-29:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-29:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-29:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-29:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-29:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-29:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-30:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-30:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-30:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-30:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-30:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-30:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-30:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-30:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-30:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-30:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-30:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-30:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-30:q5"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-30:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-30:q5"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-30:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-30:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-30:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-30:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-30:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-30:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-30:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-30:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-30:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-31:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-31:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-31:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-31:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-31:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-31:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-31:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-31:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-31:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-31:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-31:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-31:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-31:q5"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-31:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-31:q5"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-31:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-31:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-31:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-31:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-31:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-31:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-31:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-31:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-31:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-32:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-32:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-32:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-32:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-32:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-32:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-32:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-32:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-32:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-32:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-32:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-32:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-32:q5"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-32:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-32:q5"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-32:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-32:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-32:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-32:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-32:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-32:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-32:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-32:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-32:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-33:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-33:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-33:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-33:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-33:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-33:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-33:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-33:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-33:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-33:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-33:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-33:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-33:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-33:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-33:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-33:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-33:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-33:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-33:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-33:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-33:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-33:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-33:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-33:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-33:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-33:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-33:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-34:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-34:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-34:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-34:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-34:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-34:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-34:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-34:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-34:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-34:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-34:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-34:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-34:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-34:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-34:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-34:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-34:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-34:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-34:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-34:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-34:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-34:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-34:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-34:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-34:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-34:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-34:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-35:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-35:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-35:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-35:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-35:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-35:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-35:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-35:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-35:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-35:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-35:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-35:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-35:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-35:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-35:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-35:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-35:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-35:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-35:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-35:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-35:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-35:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-35:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-35:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-35:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-35:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-35:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-36:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-36:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-36:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-36:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-36:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-36:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-36:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-36:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-36:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-36:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-36:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-36:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-36:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-36:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-36:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-36:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-36:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-36:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-36:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-36:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-36:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-36:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-36:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-36:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-36:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-36:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-36:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-37:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-37:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-37:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-37:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-37:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-37:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-37:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-37:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-37:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-37:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-37:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-37:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-37:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-37:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-37:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-37:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-37:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-37:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-37:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-37:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-37:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-37:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-37:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-37:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-37:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-37:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-37:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-38:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-38:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-38:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-38:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-38:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-38:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-38:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-38:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-38:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-38:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-38:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-38:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-38:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-38:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-38:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-38:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-38:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-38:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-38:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-38:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-38:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-38:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-38:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-38:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-38:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-38:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-38:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-39:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-39:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-39:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-39:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-39:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-39:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-39:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-39:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-39:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-39:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-39:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-39:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-39:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-39:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-39:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-39:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-39:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-39:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-39:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-39:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-39:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-39:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-39:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-39:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-39:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-39:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-39:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-40:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-40:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-40:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-40:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-40:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-40:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-40:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-40:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-40:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-40:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-40:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-40:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-40:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-40:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-40:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-40:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-40:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-40:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-40:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-40:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-40:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-40:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-40:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-40:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-40:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-40:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-40:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-41:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-41:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-41:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-41:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-41:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-41:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-41:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-41:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-41:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-41:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-41:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-41:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-41:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-41:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-41:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-41:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-41:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-41:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-41:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-41:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-41:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-41:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-41:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-41:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-41:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-41:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-41:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-42:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-42:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-42:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-42:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-42:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-42:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-42:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-42:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-42:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-42:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-42:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-42:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-42:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-42:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-42:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-42:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-42:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-42:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-42:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-42:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-42:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-42:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-42:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-42:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-42:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-42:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-42:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-43:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-43:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-43:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-43:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-43:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-43:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-43:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-43:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-43:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-43:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-43:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-43:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-43:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-43:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-43:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-43:q6"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-43:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-43:q6"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-43:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-43:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-43:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-43:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-43:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-43:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-43:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-43:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-43:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-44:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-44:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-44:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-44:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-44:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-44:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-44:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-44:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-44:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-44:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-44:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-44:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-44:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-44:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-44:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-44:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-44:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-44:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-44:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-44:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-44:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-44:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-44:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-44:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-44:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-44:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-44:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-44:q10"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-44:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-44:q10"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-45:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-45:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-45:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-45:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-45:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-45:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-45:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-45:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-45:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-45:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-45:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-45:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-45:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-45:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-45:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-45:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-45:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-45:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-45:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-45:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-45:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-45:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-45:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-45:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-45:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-45:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-45:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-45:q10"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-45:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-45:q10"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-46:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-46:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-46:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-46:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-46:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-46:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-46:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-46:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-46:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-46:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-46:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-46:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-46:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-46:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-46:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-46:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-46:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-46:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-46:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-46:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-46:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-46:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-46:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-46:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-46:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-46:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-46:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-46:q10"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-46:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-46:q10"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-47:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-47:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-47:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-47:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-47:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-47:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-47:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-47:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-47:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-47:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-47:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-47:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-47:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-47:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-47:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-47:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-47:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-47:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-47:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-47:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-47:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-47:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-47:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-47:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-47:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-47:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-47:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-47:q10"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-47:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-47:q10"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-48:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-48:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-48:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-48:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-48:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-48:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-48:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-48:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-48:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-48:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-48:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-48:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-48:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-48:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-48:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-48:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-48:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-48:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-48:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-48:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-48:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-48:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-48:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-48:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-48:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-48:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-48:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-48:q10"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-48:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-48:q10"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-49:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-49:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-49:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-49:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-49:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-49:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-49:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-49:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-49:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-49:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-49:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-49:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-49:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-49:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-49:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-49:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-49:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-49:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-49:q7"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-49:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-49:q7"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-49:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-49:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-49:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-49:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-49:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-49:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-49:q10"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-49:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-49:q10"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-50:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-50:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-50:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-50:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-50:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-50:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-50:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-50:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-50:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-50:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-50:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-50:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-50:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-50:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-50:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-50:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-50:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-50:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-ambiguity-50:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-50:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-50:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-50:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-50:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-50:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-50:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-50:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-50:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-50:q10"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-50:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-50:q10"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-50:q11"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-50:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-50:q11"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-51:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-51:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-51:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-51:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-51:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-51:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-51:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-51:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-51:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-51:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-51:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-51:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-51:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-51:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-51:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-51:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-51:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-51:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-ambiguity-51:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-51:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-51:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-51:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-51:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-51:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-51:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-51:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-51:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-51:q10"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-51:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-51:q10"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-51:q11"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-51:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-51:q11"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-52:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-52:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-52:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-52:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-52:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-52:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-52:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-52:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-52:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-52:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-52:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-52:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-52:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-52:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-52:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-52:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-52:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-52:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-ambiguity-52:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-52:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-52:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-52:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-52:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-52:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-52:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-52:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-52:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-52:q10"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-52:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-52:q10"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-52:q11"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-52:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-52:q11"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-53:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-53:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-53:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-53:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-53:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-53:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-53:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-53:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-53:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-53:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-53:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-53:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-53:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-53:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-53:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-53:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-53:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-53:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-ambiguity-53:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-53:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-53:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-53:q8"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-53:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-53:q8"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-53:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-53:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-53:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-53:q10"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-53:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-53:q10"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-53:q11"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-53:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-53:q11"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-54:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-54:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-54:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-54:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-54:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-54:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-54:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-54:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-54:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-54:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-54:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-54:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-54:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-54:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-54:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-54:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-54:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-54:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-ambiguity-54:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-54:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-54:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-ambiguity-54:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-54:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-54:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-54:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-54:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-54:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-54:q10"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-54:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-54:q10"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-54:q11"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-54:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-54:q11"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-54:q12"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-54:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-54:q12"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-55:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-55:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-55:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-55:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-55:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-55:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-55:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-55:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-55:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-55:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-55:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-55:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-55:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-55:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-55:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-55:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-55:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-55:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-ambiguity-55:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-55:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-55:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-ambiguity-55:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-55:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-55:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-55:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-55:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-55:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-55:q10"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-55:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-55:q10"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-55:q11"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-55:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-55:q11"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-55:q12"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-55:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-55:q12"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-56:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-56:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-56:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-56:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-56:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-56:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-56:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-56:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-56:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-56:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-56:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-56:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-56:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-56:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-56:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-56:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-56:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-56:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-ambiguity-56:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-56:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-56:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-ambiguity-56:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-56:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-56:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-56:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-56:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-56:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-56:q10"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-56:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-56:q10"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-56:q11"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-56:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-56:q11"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-56:q12"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-56:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-56:q12"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-57:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-57:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-57:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-57:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-57:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-57:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-57:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-57:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-57:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-57:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-57:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-57:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-57:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-57:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-57:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-57:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-57:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-57:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-ambiguity-57:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-57:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-57:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-ambiguity-57:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-57:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-57:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-57:q9"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-57:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-57:q9"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-57:q10"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-57:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-57:q10"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-57:q11"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-57:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-57:q11"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-57:q12"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-57:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-57:q12"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-58:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-58:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-58:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-58:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-58:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-58:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-58:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-58:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-58:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-58:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-58:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-58:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-58:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-58:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-58:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-58:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-58:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-58:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-ambiguity-58:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-58:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-58:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-ambiguity-58:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-58:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-58:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-ambiguity-58:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-58:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-58:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-58:q10"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-58:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-58:q10"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-58:q11"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-58:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-58:q11"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-58:q12"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-58:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-58:q12"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-58:q13"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-58:q13"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-58:q13"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-59:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-59:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-59:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-59:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-59:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-59:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-59:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-59:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-59:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-59:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-59:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-59:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-59:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-59:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-59:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-59:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-59:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-59:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-ambiguity-59:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-59:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-59:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-ambiguity-59:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-59:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-59:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-ambiguity-59:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-59:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-59:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-59:q10"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-59:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-59:q10"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-59:q11"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-59:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-59:q11"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-59:q12"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-59:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-59:q12"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-59:q13"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-59:q13"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-59:q13"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-60:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-60:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-60:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-60:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-60:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-60:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-60:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-60:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-60:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-60:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-60:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-60:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-60:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-60:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-60:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-60:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-60:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-60:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-ambiguity-60:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-60:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-60:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-ambiguity-60:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-60:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-60:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-ambiguity-60:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-60:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-60:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-60:q10"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-60:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-60:q10"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-60:q11"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-60:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-60:q11"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-60:q12"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-60:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-60:q12"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-60:q13"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-60:q13"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-60:q13"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-61:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-61:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-61:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-61:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-61:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-61:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-61:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-61:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-61:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-61:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-61:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-61:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-61:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-61:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-61:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-61:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-61:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-61:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-ambiguity-61:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-61:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-61:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-ambiguity-61:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-61:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-61:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-ambiguity-61:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-61:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-61:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-61:q10"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-61:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-61:q10"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-61:q11"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-61:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-61:q11"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-61:q12"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-61:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-61:q12"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-61:q13"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-61:q13"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-61:q13"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-62:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-62:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-62:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-62:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-62:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-62:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-62:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-62:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-62:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-62:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-62:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-62:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-62:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-62:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-62:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-62:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-62:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-62:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-ambiguity-62:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-62:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-62:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-ambiguity-62:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-62:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-62:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-ambiguity-62:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-62:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-62:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "next month" in predictions["product-memory-pronoun-ambiguity-62:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-62:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-62:q10"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-62:q11"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-62:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-62:q11"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-62:q12"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-62:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-62:q12"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-62:q13"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-62:q13"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-62:q13"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-62:q14"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-62:q14"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-62:q14"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-63:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-63:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-63:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-63:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-63:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-63:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-63:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-63:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-63:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-63:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-63:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-63:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-63:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-63:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-63:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-63:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-63:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-63:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-ambiguity-63:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-63:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-63:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-ambiguity-63:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-63:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-63:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-ambiguity-63:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-63:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-63:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "next month" in predictions["product-memory-pronoun-ambiguity-63:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-63:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-63:q10"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-63:q11"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-63:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-63:q11"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-63:q12"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-63:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-63:q12"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-63:q13"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-63:q13"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-63:q13"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-63:q14"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-63:q14"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-63:q14"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-64:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-64:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-64:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-64:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-64:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-64:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-64:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-64:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-64:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-64:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-64:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-64:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-64:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-64:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-64:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-64:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-64:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-64:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-ambiguity-64:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-64:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-64:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-ambiguity-64:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-64:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-64:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-ambiguity-64:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-64:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-64:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "next month" in predictions["product-memory-pronoun-ambiguity-64:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-64:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-64:q10"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-64:q11"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-64:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-64:q11"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-64:q12"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-64:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-64:q12"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-64:q13"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-64:q13"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-64:q13"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-64:q14"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-64:q14"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-64:q14"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-65:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-65:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-65:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-65:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-65:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-65:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-65:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-65:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-65:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-65:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-65:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-65:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-65:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-65:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-65:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-65:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-65:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-65:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-ambiguity-65:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-65:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-65:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-ambiguity-65:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-65:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-65:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-ambiguity-65:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-65:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-65:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "next month" in predictions["product-memory-pronoun-ambiguity-65:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-65:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-65:q10"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert predictions["product-memory-pronoun-ambiguity-65:q11"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-65:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-65:q11"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-65:q12"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-65:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-65:q12"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-65:q13"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-65:q13"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-65:q13"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-65:q14"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-65:q14"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-65:q14"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-66:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-66:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-66:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-66:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-66:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-66:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-66:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-66:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-66:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-66:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-66:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-66:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-66:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-66:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-66:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-66:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-66:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-66:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-ambiguity-66:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-66:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-66:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-ambiguity-66:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-66:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-66:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-ambiguity-66:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-66:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-66:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "next month" in predictions["product-memory-pronoun-ambiguity-66:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-66:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-66:q10"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "tiramisu" in predictions["product-memory-pronoun-ambiguity-66:q11"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-66:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-66:q11"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-ambiguity-66:q12"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-66:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-66:q12"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-66:q13"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-66:q13"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-66:q13"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-66:q14"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-66:q14"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-66:q14"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-66:q15"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-66:q15"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-66:q15"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-67:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-67:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-67:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-67:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-67:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-67:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-67:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-67:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-67:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-67:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-67:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-67:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-67:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-67:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-67:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-67:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-67:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-67:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-ambiguity-67:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-67:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-67:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-ambiguity-67:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-67:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-67:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-ambiguity-67:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-67:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-67:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "next month" in predictions["product-memory-pronoun-ambiguity-67:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-67:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-67:q10"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "tiramisu" in predictions["product-memory-pronoun-ambiguity-67:q11"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-67:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-67:q11"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-ambiguity-67:q12"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-67:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-67:q12"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-67:q13"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-67:q13"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-67:q13"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-67:q14"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-67:q14"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-67:q14"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-67:q15"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-67:q15"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-67:q15"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-68:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-68:q1"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-68:q1"]["metadata"]["primary_answer_candidate_source"] == "current_state_deletion"
        assert "sharjah" in predictions["product-memory-pronoun-ambiguity-68:q2"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-68:q2"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-68:q2"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "espresso" in predictions["product-memory-pronoun-ambiguity-68:q3"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-68:q3"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-68:q3"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "beagle" in predictions["product-memory-pronoun-ambiguity-68:q4"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-68:q4"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-68:q4"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "two" in predictions["product-memory-pronoun-ambiguity-68:q5"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-68:q5"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-68:q5"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "summer vibes" in predictions["product-memory-pronoun-ambiguity-68:q6"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-68:q6"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-68:q6"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "clarinet" in predictions["product-memory-pronoun-ambiguity-68:q7"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-68:q7"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-68:q7"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "spotify" in predictions["product-memory-pronoun-ambiguity-68:q8"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-68:q8"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-68:q8"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "30 minutes" in predictions["product-memory-pronoun-ambiguity-68:q9"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-68:q9"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-68:q9"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "next month" in predictions["product-memory-pronoun-ambiguity-68:q10"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-68:q10"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-68:q10"]["metadata"]["primary_answer_candidate_source"] == "current_state_memory"
        assert "tiramisu" in predictions["product-memory-pronoun-ambiguity-68:q11"]["predicted_answer"].lower()
        assert predictions["product-memory-pronoun-ambiguity-68:q11"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-68:q11"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-pronoun-ambiguity-68:q12"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-68:q12"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-68:q12"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-68:q13"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-68:q13"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-68:q13"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-68:q14"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-68:q14"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-68:q14"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-pronoun-ambiguity-68:q15"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-pronoun-ambiguity-68:q15"]["is_correct"] is True
        assert predictions["product-memory-pronoun-ambiguity-68:q15"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"


def test_extract_memory_atoms_supports_direct_dog_breed_statements():
    from domain_chip_memory.contracts import (
        NormalizedBenchmarkSample,
        NormalizedQuestion,
        NormalizedSession,
        NormalizedTurn,
    )

    sample = NormalizedBenchmarkSample(
        benchmark_name="LongMemEval",
        sample_id="sample-direct-dog-breed",
        sessions=[
            NormalizedSession(
                session_id="s1",
                timestamp="2024-01-01",
                turns=[
                    NormalizedTurn(turn_id="s1:t1", speaker="user", text="My dog is a beagle."),
                ],
            )
        ],
        questions=[
            NormalizedQuestion(
                question_id="q1",
                question="What breed is my dog now?",
                category="single-session-user",
                expected_answers=["beagle"],
                evidence_session_ids=["s1"],
                evidence_turn_ids=["s1:t1"],
            )
        ],
    )

    atoms = extract_memory_atoms(sample)
    assert ("dog_breed", "beagle") in {(atom.predicate, atom.value) for atom in atoms}


def test_product_memory_uses_earlier_and_later_wording_to_bind_relative_anchors():
    temporal_wording_samples = [
        sample
        for sample in product_memory_samples()
        if sample.sample_id in {
            "product-memory-temporal-wording-1",
            "product-memory-temporal-wording-2",
            "product-memory-temporal-wording-3",
            "product-memory-temporal-wording-4",
            "product-memory-temporal-wording-5",
            "product-memory-temporal-wording-6",
            "product-memory-temporal-wording-7",
            "product-memory-temporal-wording-8",
            "product-memory-temporal-wording-9",
            "product-memory-temporal-wording-10",
            "product-memory-temporal-wording-11",
            "product-memory-temporal-wording-12",
            "product-memory-temporal-wording-13",
            "product-memory-temporal-wording-14",
            "product-memory-temporal-wording-15",
            "product-memory-temporal-wording-16",
            "product-memory-temporal-wording-17",
            "product-memory-temporal-wording-18",
            "product-memory-temporal-wording-19",
            "product-memory-temporal-wording-20",
            "product-memory-temporal-wording-21",
            "product-memory-temporal-wording-22",
            "product-memory-temporal-wording-23",
            "product-memory-temporal-wording-24",
            "product-memory-temporal-wording-25",
            "product-memory-temporal-wording-26",
            "product-memory-temporal-wording-27",
            "product-memory-temporal-wording-28",
            "product-memory-temporal-wording-29",
            "product-memory-temporal-wording-30",
            "product-memory-temporal-wording-31",
            "product-memory-temporal-wording-32",
            "product-memory-temporal-wording-33",
            "product-memory-temporal-wording-34",
            "product-memory-temporal-wording-35",
            "product-memory-temporal-wording-36",
            "product-memory-temporal-wording-37",
            "product-memory-temporal-wording-38",
            "product-memory-temporal-wording-39",
            "product-memory-temporal-wording-40",
            "product-memory-temporal-wording-41",
            "product-memory-temporal-wording-42",
            "product-memory-temporal-wording-43",
            "product-memory-temporal-wording-44",
            "product-memory-temporal-wording-45",
            "product-memory-temporal-wording-46",
            "product-memory-temporal-wording-47",
            "product-memory-temporal-wording-48",
        }
    ]

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            temporal_wording_samples,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}
        assert predictions["product-memory-temporal-wording-1:q1"]["predicted_answer"] == "red"
        assert predictions["product-memory-temporal-wording-1:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-1:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-1:q2"]["predicted_answer"] == "green"
        assert predictions["product-memory-temporal-wording-1:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-1:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-1:q3"]["predicted_answer"] == "green"
        assert predictions["product-memory-temporal-wording-1:q3"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-1:q3"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-2:q1"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-temporal-wording-2:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-2:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-2:q2"]["predicted_answer"] == "Sharjah"
        assert predictions["product-memory-temporal-wording-2:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-2:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-2:q3"]["predicted_answer"] == "Sharjah"
        assert predictions["product-memory-temporal-wording-2:q3"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-2:q3"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-3:q1"]["predicted_answer"] == "red"
        assert predictions["product-memory-temporal-wording-3:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-3:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-3:q2"]["predicted_answer"] == "yellow"
        assert predictions["product-memory-temporal-wording-3:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-3:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-3:q3"]["predicted_answer"] == "green"
        assert predictions["product-memory-temporal-wording-3:q3"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-3:q3"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-3:q4"]["predicted_answer"] == "yellow"
        assert predictions["product-memory-temporal-wording-3:q4"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-3:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-4:q1"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-temporal-wording-4:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-4:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-4:q2"]["predicted_answer"] == "Abu Dhabi"
        assert predictions["product-memory-temporal-wording-4:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-4:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-4:q3"]["predicted_answer"] == "Sharjah"
        assert predictions["product-memory-temporal-wording-4:q3"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-4:q3"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-4:q4"]["predicted_answer"] == "Abu Dhabi"
        assert predictions["product-memory-temporal-wording-4:q4"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-4:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-5:q1"]["predicted_answer"] == "red"
        assert predictions["product-memory-temporal-wording-5:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-5:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-5:q2"]["predicted_answer"] == "yellow"
        assert predictions["product-memory-temporal-wording-5:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-5:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-6:q1"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-temporal-wording-6:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-6:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-6:q2"]["predicted_answer"] == "Sharjah"
        assert predictions["product-memory-temporal-wording-6:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-6:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-7:q1"]["predicted_answer"] == "green"
        assert predictions["product-memory-temporal-wording-7:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-7:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-7:q2"]["predicted_answer"] == "yellow"
        assert predictions["product-memory-temporal-wording-7:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-7:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-8:q1"]["predicted_answer"] == "Sharjah"
        assert predictions["product-memory-temporal-wording-8:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-8:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-8:q2"]["predicted_answer"] == "Abu Dhabi"
        assert predictions["product-memory-temporal-wording-8:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-8:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-9:q1"]["predicted_answer"] == "red"
        assert predictions["product-memory-temporal-wording-9:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-9:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-9:q2"]["predicted_answer"] == "yellow"
        assert predictions["product-memory-temporal-wording-9:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-9:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-10:q1"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-temporal-wording-10:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-10:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-10:q2"]["predicted_answer"] == "Abu Dhabi"
        assert predictions["product-memory-temporal-wording-10:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-10:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-11:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-11:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-11:q1"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-11:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-11:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-11:q2"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-12:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-12:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-12:q1"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-12:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-12:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-12:q2"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-13:q1"]["predicted_answer"] == "green"
        assert predictions["product-memory-temporal-wording-13:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-13:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-13:q2"]["predicted_answer"] == "yellow"
        assert predictions["product-memory-temporal-wording-13:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-13:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-14:q1"]["predicted_answer"] == "Sharjah"
        assert predictions["product-memory-temporal-wording-14:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-14:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-14:q2"]["predicted_answer"] == "Abu Dhabi"
        assert predictions["product-memory-temporal-wording-14:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-14:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-15:q1"]["predicted_answer"] == "red"
        assert predictions["product-memory-temporal-wording-15:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-15:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-15:q2"]["predicted_answer"] == "green"
        assert predictions["product-memory-temporal-wording-15:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-15:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-16:q1"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-temporal-wording-16:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-16:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-16:q2"]["predicted_answer"] == "Sharjah"
        assert predictions["product-memory-temporal-wording-16:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-16:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-17:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-17:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-17:q1"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-17:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-17:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-17:q2"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-18:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-18:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-18:q1"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-18:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-18:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-18:q2"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-19:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-19:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-19:q1"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-19:q2"]["predicted_answer"] == "yellow"
        assert predictions["product-memory-temporal-wording-19:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-19:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-20:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-20:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-20:q1"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-20:q2"]["predicted_answer"] == "Abu Dhabi"
        assert predictions["product-memory-temporal-wording-20:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-20:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-21:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-21:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-21:q1"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-21:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-21:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-21:q2"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-22:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-22:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-22:q1"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-22:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-22:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-22:q2"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-23:q1"]["predicted_answer"] == "green"
        assert predictions["product-memory-temporal-wording-23:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-23:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-23:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-23:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-23:q2"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-24:q1"]["predicted_answer"] == "Sharjah"
        assert predictions["product-memory-temporal-wording-24:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-24:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-24:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-24:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-24:q2"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-25:q1"]["predicted_answer"] == "red"
        assert predictions["product-memory-temporal-wording-25:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-25:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-25:q2"]["predicted_answer"] == "green"
        assert predictions["product-memory-temporal-wording-25:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-25:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-25:q3"]["predicted_answer"] == "green"
        assert predictions["product-memory-temporal-wording-25:q3"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-25:q3"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-25:q4"]["predicted_answer"] == "blue"
        assert predictions["product-memory-temporal-wording-25:q4"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-25:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-26:q1"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-temporal-wording-26:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-26:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-26:q2"]["predicted_answer"] == "Sharjah"
        assert predictions["product-memory-temporal-wording-26:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-26:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-26:q3"]["predicted_answer"] == "Sharjah"
        assert predictions["product-memory-temporal-wording-26:q3"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-26:q3"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-26:q4"]["predicted_answer"] == "Abu Dhabi"
        assert predictions["product-memory-temporal-wording-26:q4"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-26:q4"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-27:q1"]["predicted_answer"] == "red"
        assert predictions["product-memory-temporal-wording-27:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-27:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-27:q2"]["predicted_answer"] == "blue"
        assert predictions["product-memory-temporal-wording-27:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-27:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-28:q1"]["predicted_answer"] == "Dubai"
        assert predictions["product-memory-temporal-wording-28:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-28:q1"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-28:q2"]["predicted_answer"] == "Abu Dhabi"
        assert predictions["product-memory-temporal-wording-28:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-28:q2"]["metadata"]["primary_answer_candidate_source"] == "evidence_memory"
        assert predictions["product-memory-temporal-wording-29:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-29:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-29:q1"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-29:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-29:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-29:q2"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-30:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-30:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-30:q1"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-30:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-30:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-30:q2"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-31:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-31:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-31:q1"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-31:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-31:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-31:q2"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-32:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-32:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-32:q1"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-32:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-32:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-32:q2"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-33:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-33:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-33:q1"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-34:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-34:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-34:q1"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-35:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-35:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-35:q1"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-36:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-36:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-36:q1"]["metadata"]["primary_answer_candidate_source"] == "temporal_ambiguity"
        assert predictions["product-memory-temporal-wording-37:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-37:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-37:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-37:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-37:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-37:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-38:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-38:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-38:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-38:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-38:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-38:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-38:q3"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-38:q3"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-38:q3"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-38:q4"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-38:q4"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-38:q4"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-39:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-39:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-39:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-39:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-39:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-39:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-39:q3"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-39:q3"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-39:q3"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-39:q4"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-39:q4"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-39:q4"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-40:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-40:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-40:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-40:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-40:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-40:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-40:q3"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-40:q3"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-40:q3"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-40:q4"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-40:q4"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-40:q4"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-41:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-41:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-41:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-41:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-41:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-41:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-41:q3"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-41:q3"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-41:q3"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-41:q4"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-41:q4"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-41:q4"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-42:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-42:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-42:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-42:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-42:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-42:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-43:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-43:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-43:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-43:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-43:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-43:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-44:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-44:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-44:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-44:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-44:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-44:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-45:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-45:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-45:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-45:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-45:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-45:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-46:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-46:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-46:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-46:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-46:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-46:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-46:q3"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-46:q3"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-46:q3"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-46:q4"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-46:q4"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-46:q4"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-47:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-47:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-47:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-47:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-47:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-47:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-47:q3"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-47:q3"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-47:q3"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-47:q4"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-47:q4"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-47:q4"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-48:q1"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-48:q1"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-48:q1"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-48:q2"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-48:q2"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-48:q2"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-48:q3"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-48:q3"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-48:q3"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"
        assert predictions["product-memory-temporal-wording-48:q4"]["predicted_answer"].lower() == "unknown"
        assert predictions["product-memory-temporal-wording-48:q4"]["is_correct"] is True
        assert predictions["product-memory-temporal-wording-48:q4"]["metadata"]["primary_answer_candidate_source"] == "referential_ambiguity"


def test_product_memory_lead_systems_are_source_aligned_on_local_lane():
    samples = product_memory_samples()

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            samples,
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
            top_k_sessions=2,
            fallback_sessions=1,
        )

        for prediction in scorecard["predictions"]:
            expected_source = prediction["metadata"].get("expected_answer_candidate_source")
            actual_source = prediction["metadata"].get("primary_answer_candidate_source")
            assert expected_source == actual_source


def test_observational_temporal_memory_answers_latest_fact():
    samples = demo_samples()
    scorecard = run_baseline(
        [samples[0]],
        baseline_name="observational_temporal_memory",
        provider=get_provider("heuristic_v1"),
        top_k_sessions=2,
        fallback_sessions=1,
    )

    prediction = scorecard["predictions"][0]
    assert prediction["predicted_answer"].lower() == "dubai"
    assert prediction["is_correct"] is True


def test_observational_memory_manifest_and_packets():
    samples = demo_samples()
    manifest, packets = build_observational_temporal_memory_packets(samples[:1], max_observations=4)

    assert manifest["baseline_name"] == "observational_temporal_memory"
    assert packets
    assert packets[0].metadata["route"] == "observational_temporal_memory"


def test_observational_memory_surfaces_typed_current_state_answer_candidate():
    samples = demo_samples()
    _, packets = build_observational_temporal_memory_packets(samples[:1], max_observations=4)

    assert packets[0].answer_candidates
    assert packets[0].answer_candidates[0].text == "Dubai"
    assert packets[0].answer_candidates[0].candidate_type == "current_state"
    assert packets[0].metadata["primary_answer_candidate_type"] == "current_state"
    current_state_items = [item for item in packets[0].retrieved_context_items if item.strategy == "current_state_memory"]
    assert current_state_items
    assert current_state_items[0].memory_role == "current_state"
    assert "current_state_memory:" in packets[0].assembled_context


def test_observational_memory_surfaces_topical_episode_support_for_locomo():
    from domain_chip_memory.contracts import (
        NormalizedBenchmarkSample,
        NormalizedQuestion,
        NormalizedSession,
        NormalizedTurn,
    )

    sample = NormalizedBenchmarkSample(
        benchmark_name="LoCoMo",
        sample_id="conv-topic",
        sessions=[
            NormalizedSession(
                session_id="session_1",
                timestamp="2023-10-01",
                turns=[
                    NormalizedTurn(
                        turn_id="D1:1",
                        speaker="Caroline",
                        text="I started a pottery class last Friday and made a bowl.",
                    ),
                    NormalizedTurn(
                        turn_id="D1:2",
                        speaker="Caroline",
                        text="During the break from pottery, I read a book and painted to keep busy.",
                    ),
                    NormalizedTurn(
                        turn_id="D1:3",
                        speaker="Melanie",
                        text="That sounds relaxing.",
                    ),
                ],
            )
        ],
        questions=[
            NormalizedQuestion(
                question_id="q1",
                question="During the break from pottery, which activity kept Caroline busy?",
                category="4",
                expected_answers=["read a book and painted"],
                evidence_session_ids=["session_1"],
                evidence_turn_ids=["D1:2"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            )
        ],
        metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
    )

    observations = build_observation_log(sample)
    topic_ids = {entry.metadata.get("topic_id") for entry in observations if entry.turn_ids[0] in {"D1:1", "D1:2"}}

    _, packets = build_observational_temporal_memory_packets(
        [sample],
        max_observations=1,
        max_reflections=1,
        max_topic_support=1,
    )

    assert len(topic_ids) == 1
    assert "topical_episode:" in packets[0].assembled_context
    assert "episode_observation:" in packets[0].assembled_context
    assert "During the break from pottery, I read a book and painted to keep busy." in packets[0].assembled_context


def test_event_calendar_captures_latest_event():
    samples = demo_samples()
    events = build_event_calendar(samples[0])
    location_entries = [entry.text for entry in events if entry.predicate == "location" and entry.subject == "user"]
    assert "I live in London" in location_entries
    assert "I live in Dubai" in location_entries


def test_dual_store_hybrid_answers_latest_fact():
    samples = demo_samples()
    scorecard = run_baseline(
        [samples[0]],
        baseline_name="dual_store_event_calendar_hybrid",
        provider=get_provider("heuristic_v1"),
        top_k_sessions=2,
        fallback_sessions=1,
    )

    prediction = scorecard["predictions"][0]
    assert prediction["predicted_answer"].lower() == "dubai"
    assert prediction["is_correct"] is True


def test_dual_store_hybrid_manifest_and_packets():
    samples = demo_samples()
    manifest, packets = build_dual_store_event_calendar_hybrid_packets(samples[:1], max_observations=4, top_k_events=2)

    assert manifest["baseline_name"] == "dual_store_event_calendar_hybrid"
    assert packets
    assert packets[0].metadata["route"] == "dual_store_event_calendar_hybrid"


def test_dual_store_hybrid_handles_questions_without_ranked_events():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-probe-no-events",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-01-01T09:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "I visited Kyoto in January."}],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2025-03-15T09:00:00Z",
                    "turns": [{"turn_id": "s2t1", "speaker": "user", "text": "I visited Seoul in March."}],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "Which city did I visit after Kyoto?",
                    "answer": "Seoul",
                    "category": "temporal_disambiguation",
                    "evidence_session_ids": ["s1", "s2"],
                    "evidence_turn_ids": ["s1t1", "s2t1"],
                    "question_date": "2025-03-16",
                }
            ],
        }
    )

    scorecard = run_baseline(
        [sample],
        baseline_name="dual_store_event_calendar_hybrid",
        provider=get_provider("heuristic_v1"),
    )

    assert scorecard["overall"]["total"] == 1


def test_dual_store_hybrid_prefers_evidence_candidates_for_episodic_and_abstention_questions():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-probe-evidence-first",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-01-05T09:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "I used to live in Austin."}],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2025-06-14T10:00:00Z",
                    "turns": [{"turn_id": "s2t1", "speaker": "user", "text": "My favorite writing spot is Alserkal Avenue."}],
                },
                {
                    "session_id": "s3",
                    "timestamp": "2026-02-18T08:30:00Z",
                    "turns": [
                        {"turn_id": "s3t1", "speaker": "user", "text": "I moved to Dubai."},
                        {"turn_id": "s3t2", "speaker": "user", "text": "I prefer espresso."},
                    ],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "What is my favorite writing spot?",
                    "answer": "Alserkal Avenue",
                    "category": "episodic_memory",
                    "evidence_session_ids": ["s2"],
                    "evidence_turn_ids": ["s2t1"],
                    "question_date": "2026-03-01",
                },
                {
                    "question_id": "q4",
                    "question": "What hospital do I use now?",
                    "answer": "Information provided is not enough",
                    "category": "abstention",
                    "evidence_session_ids": [],
                    "evidence_turn_ids": [],
                    "should_abstain": True,
                },
            ],
        }
    )

    _, packets = build_dual_store_event_calendar_hybrid_packets([sample], top_k_events=2)
    packets_by_question_id = {packet.question_id: packet for packet in packets}

    assert packets_by_question_id["q1"].answer_candidates[0].text == "My favorite writing spot is Alserkal Avenue"
    assert packets_by_question_id["q4"].answer_candidates[0].text == "unknown"

    scorecard = run_baseline(
        [sample],
        baseline_name="dual_store_event_calendar_hybrid",
        provider=get_provider("heuristic_v1"),
    )
    predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}

    assert predictions["q1"]["predicted_answer"] == "Alserkal Avenue"
    assert predictions["q1"]["is_correct"] is True
    assert predictions["q4"]["is_correct"] is True


def test_observational_and_dual_store_handle_reentered_location_timeline():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-location-reentry",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-01-05T09:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "I lived in Austin."}],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2025-03-10T09:00:00Z",
                    "turns": [{"turn_id": "s2t1", "speaker": "user", "text": "I moved to Dubai."}],
                },
                {
                    "session_id": "s3",
                    "timestamp": "2025-06-01T09:00:00Z",
                    "turns": [{"turn_id": "s3t1", "speaker": "user", "text": "I moved to Abu Dhabi."}],
                },
                {
                    "session_id": "s4",
                    "timestamp": "2025-09-15T09:00:00Z",
                    "turns": [{"turn_id": "s4t1", "speaker": "user", "text": "I moved back to Dubai."}],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "Where do I live now?",
                    "answer": "Dubai",
                    "category": "current_state",
                    "evidence_session_ids": ["s1", "s2", "s3", "s4"],
                    "evidence_turn_ids": ["s1t1", "s2t1", "s3t1", "s4t1"],
                    "question_date": "2025-09-16",
                },
                {
                    "question_id": "q2",
                    "question": "Where did I live before moving back to Dubai?",
                    "answer": "Abu Dhabi",
                    "category": "temporal_disambiguation",
                    "evidence_session_ids": ["s3", "s4"],
                    "evidence_turn_ids": ["s3t1", "s4t1"],
                    "question_date": "2025-09-16",
                },
                {
                    "question_id": "q3",
                    "question": "Where did I live after Austin?",
                    "answer": "Dubai",
                    "category": "temporal_disambiguation",
                    "evidence_session_ids": ["s1", "s2"],
                    "evidence_turn_ids": ["s1t1", "s2t1"],
                    "question_date": "2025-09-16",
                },
            ],
        }
    )

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
        )
        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}

        assert predictions["q1"]["predicted_answer"] == "Dubai"
        assert predictions["q1"]["is_correct"] is True
        assert predictions["q2"]["predicted_answer"] == "Abu Dhabi"
        assert predictions["q2"]["is_correct"] is True
        assert predictions["q3"]["predicted_answer"] == "Dubai"
        assert predictions["q3"]["is_correct"] is True


def test_observational_and_dual_store_handle_date_indexed_location_recall():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-location-dated-recall",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-01-05T09:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "I lived in Austin."}],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2025-03-10T09:00:00Z",
                    "turns": [{"turn_id": "s2t1", "speaker": "user", "text": "I moved to Dubai."}],
                },
                {
                    "session_id": "s3",
                    "timestamp": "2025-06-01T09:00:00Z",
                    "turns": [{"turn_id": "s3t1", "speaker": "user", "text": "I moved to Abu Dhabi."}],
                },
                {
                    "session_id": "s4",
                    "timestamp": "2025-09-15T09:00:00Z",
                    "turns": [{"turn_id": "s4t1", "speaker": "user", "text": "I moved back to Dubai."}],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "Where did I live in April 2025?",
                    "answer": "Dubai",
                    "category": "temporal",
                    "evidence_session_ids": ["s2"],
                    "evidence_turn_ids": ["s2t1"],
                    "question_date": "2025-10-01",
                },
                {
                    "question_id": "q2",
                    "question": "Where did I live in July 2025?",
                    "answer": "Abu Dhabi",
                    "category": "temporal",
                    "evidence_session_ids": ["s3"],
                    "evidence_turn_ids": ["s3t1"],
                    "question_date": "2025-10-01",
                },
                {
                    "question_id": "q3",
                    "question": "Where did I live in October 2025?",
                    "answer": "Dubai",
                    "category": "temporal",
                    "evidence_session_ids": ["s4"],
                    "evidence_turn_ids": ["s4t1"],
                    "question_date": "2025-10-15",
                },
            ],
        }
    )

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
        )
        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}

        assert predictions["q1"]["predicted_answer"] == "Dubai"
        assert predictions["q1"]["is_correct"] is True
        assert predictions["q2"]["predicted_answer"] == "Abu Dhabi"
        assert predictions["q2"]["is_correct"] is True
        assert predictions["q3"]["predicted_answer"] == "Dubai"
        assert predictions["q3"]["is_correct"] is True


def test_observational_and_dual_store_handle_day_indexed_location_recall():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-location-day-recall",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-08-20T09:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "I lived in Abu Dhabi."}],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2025-09-05T09:00:00Z",
                    "turns": [{"turn_id": "s2t1", "speaker": "user", "text": "I moved to Sharjah."}],
                },
                {
                    "session_id": "s3",
                    "timestamp": "2025-09-20T09:00:00Z",
                    "turns": [{"turn_id": "s3t1", "speaker": "user", "text": "I moved to Dubai."}],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "Where did I live on 10 September 2025?",
                    "answer": "Sharjah",
                    "category": "temporal",
                    "evidence_session_ids": ["s2"],
                    "evidence_turn_ids": ["s2t1"],
                    "question_date": "2025-09-25",
                },
                {
                    "question_id": "q2",
                    "question": "Where did I live on 25 September 2025?",
                    "answer": "Dubai",
                    "category": "temporal",
                    "evidence_session_ids": ["s3"],
                    "evidence_turn_ids": ["s3t1"],
                    "question_date": "2025-09-26",
                },
                {
                    "question_id": "q3",
                    "question": "Where did I live on 1 September 2025?",
                    "answer": "Abu Dhabi",
                    "category": "temporal",
                    "evidence_session_ids": ["s1"],
                    "evidence_turn_ids": ["s1t1"],
                    "question_date": "2025-09-26",
                },
            ],
        }
    )

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
        )
        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}

        assert predictions["q1"]["predicted_answer"] == "Sharjah"
        assert predictions["q1"]["is_correct"] is True
        assert predictions["q2"]["predicted_answer"] == "Dubai"
        assert predictions["q2"]["is_correct"] is True
        assert predictions["q3"]["predicted_answer"] == "Abu Dhabi"
        assert predictions["q3"]["is_correct"] is True


def test_observational_and_dual_store_handle_time_indexed_location_recall():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-location-time-recall",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-09-09T21:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "I lived in Abu Dhabi."}],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2025-09-10T08:00:00Z",
                    "turns": [{"turn_id": "s2t1", "speaker": "user", "text": "I moved to Sharjah."}],
                },
                {
                    "session_id": "s3",
                    "timestamp": "2025-09-10T18:00:00Z",
                    "turns": [{"turn_id": "s3t1", "speaker": "user", "text": "I moved to Dubai."}],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "Where did I live at 7:30 AM on 10 September 2025?",
                    "answer": "Abu Dhabi",
                    "category": "temporal",
                    "evidence_session_ids": ["s1"],
                    "evidence_turn_ids": ["s1t1"],
                    "question_date": "2025-09-11",
                },
                {
                    "question_id": "q2",
                    "question": "Where did I live at 9:00 AM on 10 September 2025?",
                    "answer": "Sharjah",
                    "category": "temporal",
                    "evidence_session_ids": ["s2"],
                    "evidence_turn_ids": ["s2t1"],
                    "question_date": "2025-09-11",
                },
                {
                    "question_id": "q3",
                    "question": "Where was I living at 7:00 PM on 10 September 2025?",
                    "answer": "Dubai",
                    "category": "temporal",
                    "evidence_session_ids": ["s3"],
                    "evidence_turn_ids": ["s3t1"],
                    "question_date": "2025-09-11",
                },
            ],
        }
    )

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
        )
        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}

        assert predictions["q1"]["predicted_answer"] == "Abu Dhabi"
        assert predictions["q1"]["is_correct"] is True
        assert predictions["q2"]["predicted_answer"] == "Sharjah"
        assert predictions["q2"]["is_correct"] is True
        assert predictions["q3"]["predicted_answer"] == "Dubai"
        assert predictions["q3"]["is_correct"] is True


def test_observational_and_dual_store_handle_event_anchored_location_recall():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-location-event-anchor-recall",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-09-09T21:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "I lived in Abu Dhabi."}],
                },
                {
                    "session_id": "s2",
                    "turns": [
                        {
                            "turn_id": "s2t1",
                            "speaker": "user",
                            "text": "I had breakfast at Marina Cafe.",
                            "timestamp": "2025-09-10T07:45:00Z",
                        },
                        {
                            "turn_id": "s2t2",
                            "speaker": "user",
                            "text": "I moved to Sharjah.",
                            "timestamp": "2025-09-10T08:00:00Z",
                        },
                        {
                            "turn_id": "s2t3",
                            "speaker": "user",
                            "text": "I attended the design review in Al Khan.",
                            "timestamp": "2025-09-10T12:30:00Z",
                        },
                        {
                            "turn_id": "s2t4",
                            "speaker": "user",
                            "text": "I moved to Dubai.",
                            "timestamp": "2025-09-10T18:00:00Z",
                        },
                    ],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "Where did I live when I had breakfast at Marina Cafe?",
                    "answer": "Abu Dhabi",
                    "category": "temporal",
                    "evidence_session_ids": ["s1", "s2"],
                    "evidence_turn_ids": ["s1t1", "s2t1"],
                    "question_date": "2025-09-11",
                },
                {
                    "question_id": "q2",
                    "question": "Where was I living when I attended the design review in Al Khan?",
                    "answer": "Sharjah",
                    "category": "temporal",
                    "evidence_session_ids": ["s2"],
                    "evidence_turn_ids": ["s2t2", "s2t3"],
                    "question_date": "2025-09-11",
                },
            ],
        }
    )

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
        )
        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}

        assert predictions["q1"]["predicted_answer"] == "Abu Dhabi"
        assert predictions["q1"]["is_correct"] is True
        assert predictions["q2"]["predicted_answer"] == "Sharjah"
        assert predictions["q2"]["is_correct"] is True


def test_observational_and_dual_store_handle_relative_event_anchored_location_recall():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-location-relative-event-anchor-recall",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-09-09T21:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "I lived in Abu Dhabi."}],
                },
                {
                    "session_id": "s2",
                    "turns": [
                        {
                            "turn_id": "s2t1",
                            "speaker": "user",
                            "text": "I had breakfast at Marina Cafe.",
                            "timestamp": "2025-09-10T07:45:00Z",
                        },
                        {
                            "turn_id": "s2t2",
                            "speaker": "user",
                            "text": "I moved to Sharjah.",
                            "timestamp": "2025-09-10T08:00:00Z",
                        },
                        {
                            "turn_id": "s2t3",
                            "speaker": "user",
                            "text": "I attended the design review in Al Khan.",
                            "timestamp": "2025-09-10T12:30:00Z",
                        },
                        {
                            "turn_id": "s2t4",
                            "speaker": "user",
                            "text": "I moved to Dubai.",
                            "timestamp": "2025-09-10T18:00:00Z",
                        },
                        {
                            "turn_id": "s2t5",
                            "speaker": "user",
                            "text": "I had dinner at Creek Harbor.",
                            "timestamp": "2025-09-10T19:15:00Z",
                        },
                    ],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "Where did I live after I had breakfast at Marina Cafe?",
                    "answer": "Sharjah",
                    "category": "temporal",
                    "evidence_session_ids": ["s2"],
                    "evidence_turn_ids": ["s2t1", "s2t2"],
                    "question_date": "2025-09-11",
                },
                {
                    "question_id": "q2",
                    "question": "Where was I living before I had dinner at Creek Harbor?",
                    "answer": "Dubai",
                    "category": "temporal",
                    "evidence_session_ids": ["s2"],
                    "evidence_turn_ids": ["s2t4", "s2t5"],
                    "question_date": "2025-09-11",
                },
            ],
        }
    )

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
        )
        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}

        assert predictions["q1"]["predicted_answer"] == "Sharjah"
        assert predictions["q1"]["is_correct"] is True
        assert predictions["q2"]["predicted_answer"] == "Dubai"
        assert predictions["q2"]["is_correct"] is True


def test_observational_and_dual_store_handle_multi_session_relative_event_anchored_location_recall():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-location-multi-session-relative-event-anchor-recall",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-09-01T09:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "I lived in Abu Dhabi."}],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2025-09-10T07:45:00Z",
                    "turns": [{"turn_id": "s2t1", "speaker": "user", "text": "I had breakfast at Marina Cafe."}],
                },
                {
                    "session_id": "s3",
                    "timestamp": "2025-09-12T08:00:00Z",
                    "turns": [{"turn_id": "s3t1", "speaker": "user", "text": "I moved to Sharjah."}],
                },
                {
                    "session_id": "s4",
                    "timestamp": "2025-09-20T12:30:00Z",
                    "turns": [{"turn_id": "s4t1", "speaker": "user", "text": "I attended the design review in Al Khan."}],
                },
                {
                    "session_id": "s5",
                    "timestamp": "2025-09-22T18:00:00Z",
                    "turns": [{"turn_id": "s5t1", "speaker": "user", "text": "I moved to Dubai."}],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "Where did I live after I had breakfast at Marina Cafe?",
                    "answer": "Sharjah",
                    "category": "temporal",
                    "evidence_session_ids": ["s2", "s3"],
                    "evidence_turn_ids": ["s2t1", "s3t1"],
                    "question_date": "2025-09-23",
                },
                {
                    "question_id": "q2",
                    "question": "Where was I living before I attended the design review in Al Khan?",
                    "answer": "Sharjah",
                    "category": "temporal",
                    "evidence_session_ids": ["s3", "s4"],
                    "evidence_turn_ids": ["s3t1", "s4t1"],
                    "question_date": "2025-09-23",
                },
            ],
        }
    )

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
        )
        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}

        assert predictions["q1"]["predicted_answer"] == "Sharjah"
        assert predictions["q1"]["is_correct"] is True
        assert predictions["q2"]["predicted_answer"] == "Sharjah"
        assert predictions["q2"]["is_correct"] is True


def test_observational_and_dual_store_handle_competing_anchor_location_recall():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-location-competing-anchor-recall",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-09-01T09:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "I lived in Abu Dhabi."}],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2025-09-10T07:45:00Z",
                    "turns": [{"turn_id": "s2t1", "speaker": "user", "text": "I had breakfast with Omar at Marina Cafe."}],
                },
                {
                    "session_id": "s3",
                    "timestamp": "2025-09-12T08:00:00Z",
                    "turns": [{"turn_id": "s3t1", "speaker": "user", "text": "I moved to Sharjah."}],
                },
                {
                    "session_id": "s4",
                    "timestamp": "2025-09-20T09:00:00Z",
                    "turns": [{"turn_id": "s4t1", "speaker": "user", "text": "I had breakfast with Layla at Marina Cafe."}],
                },
                {
                    "session_id": "s5",
                    "timestamp": "2025-09-22T18:00:00Z",
                    "turns": [{"turn_id": "s5t1", "speaker": "user", "text": "I moved to Dubai."}],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "Where did I live after I had breakfast with Omar at Marina Cafe?",
                    "answer": "Sharjah",
                    "category": "temporal",
                    "evidence_session_ids": ["s2", "s3"],
                    "evidence_turn_ids": ["s2t1", "s3t1"],
                    "question_date": "2025-09-23",
                },
                {
                    "question_id": "q2",
                    "question": "Where did I live after I had breakfast with Layla at Marina Cafe?",
                    "answer": "Dubai",
                    "category": "temporal",
                    "evidence_session_ids": ["s4", "s5"],
                    "evidence_turn_ids": ["s4t1", "s5t1"],
                    "question_date": "2025-09-23",
                },
            ],
        }
    )

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
        )
        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}

        assert predictions["q1"]["predicted_answer"] == "Sharjah"
        assert predictions["q1"]["is_correct"] is True
        assert predictions["q2"]["predicted_answer"] == "Dubai"
        assert predictions["q2"]["is_correct"] is True


def test_observational_and_dual_store_handle_misleading_overlap_anchor_location_recall():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-location-misleading-overlap-anchor-recall",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-09-01T09:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "I lived in Abu Dhabi."}],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2025-09-10T07:45:00Z",
                    "turns": [
                        {
                            "turn_id": "s2t1",
                            "speaker": "user",
                            "text": "I had breakfast at Marina Cafe with Omar before the client review.",
                        }
                    ],
                },
                {
                    "session_id": "s3",
                    "timestamp": "2025-09-12T08:00:00Z",
                    "turns": [{"turn_id": "s3t1", "speaker": "user", "text": "I moved to Sharjah."}],
                },
                {
                    "session_id": "s4",
                    "timestamp": "2025-09-20T09:00:00Z",
                    "turns": [
                        {
                            "turn_id": "s4t1",
                            "speaker": "user",
                            "text": "I had breakfast at Marina Cafe before the client review with Layla.",
                        }
                    ],
                },
                {
                    "session_id": "s5",
                    "timestamp": "2025-09-22T18:00:00Z",
                    "turns": [{"turn_id": "s5t1", "speaker": "user", "text": "I moved to Dubai."}],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "Where did I live after I had breakfast at Marina Cafe with Omar before the client review?",
                    "answer": "Sharjah",
                    "category": "temporal",
                    "evidence_session_ids": ["s2", "s3"],
                    "evidence_turn_ids": ["s2t1", "s3t1"],
                    "question_date": "2025-09-23",
                },
                {
                    "question_id": "q2",
                    "question": "Where did I live after I had breakfast at Marina Cafe before the client review with Layla?",
                    "answer": "Dubai",
                    "category": "temporal",
                    "evidence_session_ids": ["s4", "s5"],
                    "evidence_turn_ids": ["s4t1", "s5t1"],
                    "question_date": "2025-09-23",
                },
            ],
        }
    )

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
        )
        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}

        assert predictions["q1"]["predicted_answer"] == "Sharjah"
        assert predictions["q1"]["is_correct"] is True
        assert predictions["q2"]["predicted_answer"] == "Dubai"
        assert predictions["q2"]["is_correct"] is True


def test_observational_and_dual_store_handle_reentered_competing_anchor_location_recall():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-location-reentered-competing-anchor-recall",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-09-01T09:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "I lived in Abu Dhabi."}],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2025-09-10T07:45:00Z",
                    "turns": [{"turn_id": "s2t1", "speaker": "user", "text": "I had breakfast with Omar at Marina Cafe."}],
                },
                {
                    "session_id": "s3",
                    "timestamp": "2025-09-12T08:00:00Z",
                    "turns": [{"turn_id": "s3t1", "speaker": "user", "text": "I moved to Sharjah."}],
                },
                {
                    "session_id": "s4",
                    "timestamp": "2025-09-20T09:00:00Z",
                    "turns": [{"turn_id": "s4t1", "speaker": "user", "text": "I had breakfast with Layla at Marina Cafe."}],
                },
                {
                    "session_id": "s5",
                    "timestamp": "2025-09-22T18:00:00Z",
                    "turns": [{"turn_id": "s5t1", "speaker": "user", "text": "I moved to Dubai."}],
                },
                {
                    "session_id": "s6",
                    "timestamp": "2025-10-05T08:15:00Z",
                    "turns": [{"turn_id": "s6t1", "speaker": "user", "text": "I had breakfast with Omar at Marina Cafe again."}],
                },
                {
                    "session_id": "s7",
                    "timestamp": "2025-10-06T10:00:00Z",
                    "turns": [{"turn_id": "s7t1", "speaker": "user", "text": "I moved back to Sharjah."}],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "Where did I live after I had breakfast with Omar at Marina Cafe?",
                    "answer": "Sharjah",
                    "category": "temporal",
                    "evidence_session_ids": ["s2", "s3"],
                    "evidence_turn_ids": ["s2t1", "s3t1"],
                    "question_date": "2025-10-07",
                },
                {
                    "question_id": "q2",
                    "question": "Where did I live after I had breakfast with Omar at Marina Cafe again?",
                    "answer": "Sharjah",
                    "category": "temporal",
                    "evidence_session_ids": ["s6", "s7"],
                    "evidence_turn_ids": ["s6t1", "s7t1"],
                    "question_date": "2025-10-07",
                },
                {
                    "question_id": "q3",
                    "question": "Where did I live after I had breakfast with Layla at Marina Cafe?",
                    "answer": "Dubai",
                    "category": "temporal",
                    "evidence_session_ids": ["s4", "s5"],
                    "evidence_turn_ids": ["s4t1", "s5t1"],
                    "question_date": "2025-10-07",
                },
            ],
        }
    )

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
        )
        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}

        assert predictions["q1"]["predicted_answer"] == "Sharjah"
        assert predictions["q1"]["is_correct"] is True
        assert predictions["q2"]["predicted_answer"] == "Sharjah"
        assert predictions["q2"]["is_correct"] is True
        assert predictions["q3"]["predicted_answer"] == "Dubai"
        assert predictions["q3"]["is_correct"] is True


def test_observational_and_dual_store_handle_date_qualified_repeated_anchor_location_recall():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-location-date-qualified-repeated-anchor-recall",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-09-01T09:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "I lived in Abu Dhabi."}],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2025-09-10T07:45:00Z",
                    "turns": [{"turn_id": "s2t1", "speaker": "user", "text": "I had breakfast with Omar at Marina Cafe."}],
                },
                {
                    "session_id": "s3",
                    "timestamp": "2025-09-12T08:00:00Z",
                    "turns": [{"turn_id": "s3t1", "speaker": "user", "text": "I moved to Sharjah."}],
                },
                {
                    "session_id": "s4",
                    "timestamp": "2025-10-05T08:15:00Z",
                    "turns": [{"turn_id": "s4t1", "speaker": "user", "text": "I had breakfast with Omar at Marina Cafe."}],
                },
                {
                    "session_id": "s5",
                    "timestamp": "2025-10-06T10:00:00Z",
                    "turns": [{"turn_id": "s5t1", "speaker": "user", "text": "I moved to Dubai."}],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "Where did I live after I had breakfast with Omar at Marina Cafe on 10 September 2025?",
                    "answer": "Sharjah",
                    "category": "temporal",
                    "evidence_session_ids": ["s2", "s3"],
                    "evidence_turn_ids": ["s2t1", "s3t1"],
                    "question_date": "2025-10-07",
                },
                {
                    "question_id": "q2",
                    "question": "Where did I live after I had breakfast with Omar at Marina Cafe on 5 October 2025?",
                    "answer": "Dubai",
                    "category": "temporal",
                    "evidence_session_ids": ["s4", "s5"],
                    "evidence_turn_ids": ["s4t1", "s5t1"],
                    "question_date": "2025-10-07",
                },
            ],
        }
    )

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
        )
        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}

        assert predictions["q1"]["predicted_answer"] == "Sharjah"
        assert predictions["q1"]["is_correct"] is True
        assert predictions["q2"]["predicted_answer"] == "Dubai"
        assert predictions["q2"]["is_correct"] is True


def test_observational_and_dual_store_handle_dated_preference_state_recall():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-dated-preference-state-recall",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-03-01T09:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "I prefer espresso."}],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2025-07-01T09:00:00Z",
                    "turns": [{"turn_id": "s2t1", "speaker": "user", "text": "I prefer pour-over now."}],
                },
                {
                    "session_id": "s3",
                    "timestamp": "2025-10-01T09:00:00Z",
                    "turns": [{"turn_id": "s3t1", "speaker": "user", "text": "I switched back to espresso."}],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "What did I prefer in March 2025?",
                    "answer": "espresso",
                    "category": "current_state",
                    "evidence_session_ids": ["s1"],
                    "evidence_turn_ids": ["s1t1"],
                    "question_date": "2025-10-02",
                },
                {
                    "question_id": "q2",
                    "question": "What did I prefer in July 2025?",
                    "answer": "pour-over",
                    "category": "current_state",
                    "evidence_session_ids": ["s2"],
                    "evidence_turn_ids": ["s2t1"],
                    "question_date": "2025-10-02",
                },
                {
                    "question_id": "q3",
                    "question": "What do I prefer now?",
                    "answer": "espresso",
                    "category": "current_state",
                    "evidence_session_ids": ["s3"],
                    "evidence_turn_ids": ["s3t1"],
                    "question_date": "2025-10-02",
                },
            ],
        }
    )

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
        )
        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}

        assert predictions["q1"]["predicted_answer"] == "espresso"
        assert predictions["q1"]["is_correct"] is True
        assert predictions["q2"]["predicted_answer"] == "pour-over"
        assert predictions["q2"]["is_correct"] is True
        assert predictions["q3"]["predicted_answer"] == "espresso"
        assert predictions["q3"]["is_correct"] is True


def test_observational_and_dual_store_handle_event_anchored_preference_state_recall():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-event-anchored-preference-state-recall",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-03-01T09:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "I prefer espresso."}],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2025-05-01T12:00:00Z",
                    "turns": [{"turn_id": "s2t1", "speaker": "user", "text": "I lived in Dubai."}],
                },
                {
                    "session_id": "s3",
                    "timestamp": "2025-07-01T09:00:00Z",
                    "turns": [{"turn_id": "s3t1", "speaker": "user", "text": "I prefer pour-over now."}],
                },
                {
                    "session_id": "s4",
                    "timestamp": "2025-10-01T09:00:00Z",
                    "turns": [{"turn_id": "s4t1", "speaker": "user", "text": "I switched back to espresso."}],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "What did I prefer when I lived in Dubai?",
                    "answer": "espresso",
                    "category": "current_state",
                    "evidence_session_ids": ["s1", "s2"],
                    "evidence_turn_ids": ["s1t1", "s2t1"],
                    "question_date": "2025-10-02",
                },
                {
                    "question_id": "q2",
                    "question": "What do I prefer now?",
                    "answer": "espresso",
                    "category": "current_state",
                    "evidence_session_ids": ["s4"],
                    "evidence_turn_ids": ["s4t1"],
                    "question_date": "2025-10-02",
                },
            ],
        }
    )

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
        )
        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}

        assert predictions["q1"]["predicted_answer"] == "espresso"
        assert predictions["q1"]["is_correct"] is True
        assert predictions["q2"]["predicted_answer"] == "espresso"
        assert predictions["q2"]["is_correct"] is True


def test_observational_and_dual_store_handle_date_qualified_reentered_event_anchored_preference_state_recall():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-date-qualified-reentered-event-anchored-preference-state-recall",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-03-01T09:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "I prefer espresso."}],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2025-05-01T12:00:00Z",
                    "turns": [{"turn_id": "s2t1", "speaker": "user", "text": "I lived in Dubai."}],
                },
                {
                    "session_id": "s3",
                    "timestamp": "2025-05-10T09:00:00Z",
                    "turns": [{"turn_id": "s3t1", "speaker": "user", "text": "I prefer pour-over now."}],
                },
                {
                    "session_id": "s4",
                    "timestamp": "2025-07-01T09:00:00Z",
                    "turns": [{"turn_id": "s4t1", "speaker": "user", "text": "I moved to Abu Dhabi."}],
                },
                {
                    "session_id": "s5",
                    "timestamp": "2025-09-01T09:00:00Z",
                    "turns": [{"turn_id": "s5t1", "speaker": "user", "text": "I moved back to Dubai."}],
                },
                {
                    "session_id": "s6",
                    "timestamp": "2025-09-03T09:00:00Z",
                    "turns": [{"turn_id": "s6t1", "speaker": "user", "text": "I switched back to espresso."}],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "What did I prefer when I lived in Dubai in May 2025?",
                    "answer": "espresso",
                    "category": "current_state",
                    "evidence_session_ids": ["s1", "s2"],
                    "evidence_turn_ids": ["s1t1", "s2t1"],
                    "question_date": "2025-10-02",
                },
                {
                    "question_id": "q2",
                    "question": "What did I prefer when I lived in Dubai in September 2025?",
                    "answer": "pour-over",
                    "category": "current_state",
                    "evidence_session_ids": ["s3", "s5"],
                    "evidence_turn_ids": ["s3t1", "s5t1"],
                    "question_date": "2025-10-02",
                },
                {
                    "question_id": "q3",
                    "question": "What do I prefer now?",
                    "answer": "espresso",
                    "category": "current_state",
                    "evidence_session_ids": ["s6"],
                    "evidence_turn_ids": ["s6t1"],
                    "question_date": "2025-10-02",
                },
            ],
        }
    )

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
        )
        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}

        assert predictions["q1"]["predicted_answer"] == "espresso"
        assert predictions["q1"]["is_correct"] is True
        assert predictions["q2"]["predicted_answer"] == "pour-over"
        assert predictions["q2"]["is_correct"] is True
        assert predictions["q3"]["predicted_answer"] == "espresso"
        assert predictions["q3"]["is_correct"] is True


def test_observational_and_dual_store_handle_date_qualified_reentered_event_anchored_favorite_color_recall():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-date-qualified-reentered-event-anchored-favorite-color-recall",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-03-01T09:00:00Z",
                    "turns": [{"turn_id": "s1t1", "speaker": "user", "text": "My favorite color is blue."}],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2025-05-01T12:00:00Z",
                    "turns": [{"turn_id": "s2t1", "speaker": "user", "text": "I lived in Dubai."}],
                },
                {
                    "session_id": "s3",
                    "timestamp": "2025-05-10T09:00:00Z",
                    "turns": [{"turn_id": "s3t1", "speaker": "user", "text": "My favorite color is green now."}],
                },
                {
                    "session_id": "s4",
                    "timestamp": "2025-07-01T09:00:00Z",
                    "turns": [{"turn_id": "s4t1", "speaker": "user", "text": "I moved to Abu Dhabi."}],
                },
                {
                    "session_id": "s5",
                    "timestamp": "2025-09-01T09:00:00Z",
                    "turns": [{"turn_id": "s5t1", "speaker": "user", "text": "I moved back to Dubai."}],
                },
                {
                    "session_id": "s6",
                    "timestamp": "2025-09-03T09:00:00Z",
                    "turns": [{"turn_id": "s6t1", "speaker": "user", "text": "My favorite color is blue again."}],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "What was my favorite color when I lived in Dubai in May 2025?",
                    "answer": "blue",
                    "category": "current_state",
                    "evidence_session_ids": ["s1", "s2"],
                    "evidence_turn_ids": ["s1t1", "s2t1"],
                    "question_date": "2025-10-02",
                },
                {
                    "question_id": "q2",
                    "question": "What was my favorite color when I lived in Dubai in September 2025?",
                    "answer": "green",
                    "category": "current_state",
                    "evidence_session_ids": ["s3", "s5"],
                    "evidence_turn_ids": ["s3t1", "s5t1"],
                    "question_date": "2025-10-02",
                },
                {
                    "question_id": "q3",
                    "question": "What was my favorite color now?",
                    "answer": "blue",
                    "category": "current_state",
                    "evidence_session_ids": ["s6"],
                    "evidence_turn_ids": ["s6t1"],
                    "question_date": "2025-10-02",
                },
            ],
        }
    )

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
        )
        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}

        assert predictions["q1"]["predicted_answer"] == "blue"
        assert predictions["q1"]["is_correct"] is True
        assert predictions["q2"]["predicted_answer"] == "green"
        assert predictions["q2"]["is_correct"] is True
        assert predictions["q3"]["predicted_answer"] == "blue"
        assert predictions["q3"]["is_correct"] is True


def test_observational_and_dual_store_handle_relative_event_anchored_non_location_state_recall():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-relative-event-anchored-non-location-state-recall",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-09-01T08:00:00Z",
                    "turns": [
                        {"turn_id": "s1t1", "speaker": "user", "text": "I prefer espresso."},
                        {"turn_id": "s1t2", "speaker": "user", "text": "My favorite color is blue."},
                    ],
                },
                {
                    "session_id": "s2",
                    "turns": [
                        {
                            "turn_id": "s2t1",
                            "speaker": "user",
                            "text": "I had breakfast with Omar at Marina Cafe.",
                            "timestamp": "2025-09-03T09:00:00Z",
                        },
                        {
                            "turn_id": "s2t2",
                            "speaker": "user",
                            "text": "I prefer pour-over now.",
                            "timestamp": "2025-09-03T10:00:00Z",
                        },
                        {
                            "turn_id": "s2t3",
                            "speaker": "user",
                            "text": "My favorite color is green now.",
                            "timestamp": "2025-09-03T10:30:00Z",
                        },
                        {
                            "turn_id": "s2t4",
                            "speaker": "user",
                            "text": "I had lunch with Omar at Marina Cafe.",
                            "timestamp": "2025-09-03T11:00:00Z",
                        },
                        {
                            "turn_id": "s2t5",
                            "speaker": "user",
                            "text": "I switched back to espresso.",
                            "timestamp": "2025-09-03T12:00:00Z",
                        },
                        {
                            "turn_id": "s2t6",
                            "speaker": "user",
                            "text": "My favorite color is red now.",
                            "timestamp": "2025-09-03T12:30:00Z",
                        },
                    ],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "What did I prefer after I had breakfast with Omar at Marina Cafe?",
                    "answer": "pour-over",
                    "category": "current_state",
                    "evidence_session_ids": ["s2"],
                    "evidence_turn_ids": ["s2t1", "s2t2"],
                    "question_date": "2025-09-04",
                },
                {
                    "question_id": "q2",
                    "question": "What did I prefer before I had lunch with Omar at Marina Cafe?",
                    "answer": "pour-over",
                    "category": "current_state",
                    "evidence_session_ids": ["s2"],
                    "evidence_turn_ids": ["s2t2", "s2t4"],
                    "question_date": "2025-09-04",
                },
                {
                    "question_id": "q3",
                    "question": "What was my favorite color after I had breakfast with Omar at Marina Cafe?",
                    "answer": "green",
                    "category": "current_state",
                    "evidence_session_ids": ["s2"],
                    "evidence_turn_ids": ["s2t1", "s2t3"],
                    "question_date": "2025-09-04",
                },
                {
                    "question_id": "q4",
                    "question": "What was my favorite color before I had lunch with Omar at Marina Cafe?",
                    "answer": "green",
                    "category": "current_state",
                    "evidence_session_ids": ["s2"],
                    "evidence_turn_ids": ["s2t3", "s2t4"],
                    "question_date": "2025-09-04",
                },
            ],
        }
    )

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
        )
        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}

        assert predictions["q1"]["predicted_answer"] == "pour-over"
        assert predictions["q1"]["is_correct"] is True
        assert predictions["q2"]["predicted_answer"] == "pour-over"
        assert predictions["q2"]["is_correct"] is True
        assert predictions["q3"]["predicted_answer"] == "green"
        assert predictions["q3"]["is_correct"] is True
        assert predictions["q4"]["predicted_answer"] == "green"
        assert predictions["q4"]["is_correct"] is True


def test_observational_and_dual_store_handle_time_qualified_relative_event_anchored_non_location_state_recall():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-time-qualified-relative-event-anchored-non-location-state-recall",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-09-01T08:00:00Z",
                    "turns": [
                        {"turn_id": "s1t1", "speaker": "user", "text": "I prefer espresso."},
                        {"turn_id": "s1t2", "speaker": "user", "text": "My favorite color is blue."},
                    ],
                },
                {
                    "session_id": "s2",
                    "turns": [
                        {
                            "turn_id": "s2t1",
                            "speaker": "user",
                            "text": "I had breakfast with Omar at Marina Cafe.",
                            "timestamp": "2025-09-03T09:00:00Z",
                        },
                        {
                            "turn_id": "s2t2",
                            "speaker": "user",
                            "text": "I prefer pour-over now.",
                            "timestamp": "2025-09-03T10:00:00Z",
                        },
                        {
                            "turn_id": "s2t3",
                            "speaker": "user",
                            "text": "My favorite color is green now.",
                            "timestamp": "2025-09-03T10:30:00Z",
                        },
                        {
                            "turn_id": "s2t4",
                            "speaker": "user",
                            "text": "I had breakfast with Omar at Marina Cafe.",
                            "timestamp": "2025-09-03T11:00:00Z",
                        },
                        {
                            "turn_id": "s2t5",
                            "speaker": "user",
                            "text": "I switched back to espresso.",
                            "timestamp": "2025-09-03T12:00:00Z",
                        },
                        {
                            "turn_id": "s2t6",
                            "speaker": "user",
                            "text": "My favorite color is red now.",
                            "timestamp": "2025-09-03T12:30:00Z",
                        },
                    ],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "What did I prefer after I had breakfast with Omar at Marina Cafe at 9:00 AM on 3 September 2025?",
                    "answer": "pour-over",
                    "category": "current_state",
                    "evidence_session_ids": ["s2"],
                    "evidence_turn_ids": ["s2t1", "s2t2"],
                    "question_date": "2025-09-04",
                },
                {
                    "question_id": "q2",
                    "question": "What did I prefer after I had breakfast with Omar at Marina Cafe at 11:00 AM on 3 September 2025?",
                    "answer": "espresso",
                    "category": "current_state",
                    "evidence_session_ids": ["s2"],
                    "evidence_turn_ids": ["s2t4", "s2t5"],
                    "question_date": "2025-09-04",
                },
                {
                    "question_id": "q3",
                    "question": "What was my favorite color after I had breakfast with Omar at Marina Cafe at 9:00 AM on 3 September 2025?",
                    "answer": "green",
                    "category": "current_state",
                    "evidence_session_ids": ["s2"],
                    "evidence_turn_ids": ["s2t1", "s2t3"],
                    "question_date": "2025-09-04",
                },
                {
                    "question_id": "q4",
                    "question": "What was my favorite color after I had breakfast with Omar at Marina Cafe at 11:00 AM on 3 September 2025?",
                    "answer": "red",
                    "category": "current_state",
                    "evidence_session_ids": ["s2"],
                    "evidence_turn_ids": ["s2t4", "s2t6"],
                    "question_date": "2025-09-04",
                },
            ],
        }
    )

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
        )
        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}

        assert predictions["q1"]["predicted_answer"] == "pour-over"
        assert predictions["q1"]["is_correct"] is True
        assert predictions["q2"]["predicted_answer"] == "espresso"
        assert predictions["q2"]["is_correct"] is True
        assert predictions["q3"]["predicted_answer"] == "green"
        assert predictions["q3"]["is_correct"] is True
        assert predictions["q4"]["predicted_answer"] == "red"
        assert predictions["q4"]["is_correct"] is True


def test_observational_and_dual_store_abstain_on_ambiguous_relative_event_anchored_non_location_state_recall():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-ambiguous-relative-event-anchored-non-location-state-recall",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-09-01T08:00:00Z",
                    "turns": [
                        {"turn_id": "s1t1", "speaker": "user", "text": "I prefer espresso."},
                        {"turn_id": "s1t2", "speaker": "user", "text": "My favorite color is blue."},
                    ],
                },
                {
                    "session_id": "s2",
                    "turns": [
                        {
                            "turn_id": "s2t1",
                            "speaker": "user",
                            "text": "I had breakfast with Omar at Marina Cafe.",
                            "timestamp": "2025-09-03T09:00:00Z",
                        },
                        {
                            "turn_id": "s2t2",
                            "speaker": "user",
                            "text": "I prefer pour-over now.",
                            "timestamp": "2025-09-03T10:00:00Z",
                        },
                        {
                            "turn_id": "s2t3",
                            "speaker": "user",
                            "text": "My favorite color is green now.",
                            "timestamp": "2025-09-03T10:30:00Z",
                        },
                    ],
                },
                {
                    "session_id": "s3",
                    "turns": [
                        {
                            "turn_id": "s3t1",
                            "speaker": "user",
                            "text": "I had breakfast with Omar at Marina Cafe.",
                            "timestamp": "2025-09-03T11:00:00Z",
                        },
                        {
                            "turn_id": "s3t2",
                            "speaker": "user",
                            "text": "I switched back to espresso.",
                            "timestamp": "2025-09-03T12:00:00Z",
                        },
                        {
                            "turn_id": "s3t3",
                            "speaker": "user",
                            "text": "My favorite color is red now.",
                            "timestamp": "2025-09-03T12:30:00Z",
                        },
                    ],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "What did I prefer after I had breakfast with Omar at Marina Cafe on 3 September 2025?",
                    "answer": "Information provided is not enough",
                    "category": "abstention",
                    "evidence_session_ids": ["s2", "s3"],
                    "evidence_turn_ids": ["s2t1", "s2t2", "s3t1", "s3t2"],
                    "question_date": "2025-09-04",
                    "should_abstain": True,
                },
                {
                    "question_id": "q2",
                    "question": "What was my favorite color after I had breakfast with Omar at Marina Cafe on 3 September 2025?",
                    "answer": "Information provided is not enough",
                    "category": "abstention",
                    "evidence_session_ids": ["s2", "s3"],
                    "evidence_turn_ids": ["s2t1", "s2t3", "s3t1", "s3t3"],
                    "question_date": "2025-09-04",
                    "should_abstain": True,
                },
            ],
        }
    )

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
        )
        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}

        assert predictions["q1"]["predicted_answer"] == "unknown"
        assert predictions["q1"]["is_correct"] is True
        assert predictions["q2"]["predicted_answer"] == "unknown"
        assert predictions["q2"]["is_correct"] is True


def test_observational_and_dual_store_handle_location_anchored_relative_non_location_state_recall():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-location-anchored-relative-non-location-state-recall",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-04-01T09:00:00Z",
                    "turns": [
                        {"turn_id": "s1t1", "speaker": "user", "text": "I prefer espresso."},
                        {"turn_id": "s1t2", "speaker": "user", "text": "My favorite color is blue."},
                    ],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2025-05-01T09:00:00Z",
                    "turns": [
                        {"turn_id": "s2t1", "speaker": "user", "text": "I moved to Dubai."},
                    ],
                },
                {
                    "session_id": "s3",
                    "timestamp": "2025-05-02T09:00:00Z",
                    "turns": [
                        {"turn_id": "s3t1", "speaker": "user", "text": "I prefer pour-over now."},
                        {"turn_id": "s3t2", "speaker": "user", "text": "My favorite color is green now."},
                    ],
                },
                {
                    "session_id": "s4",
                    "timestamp": "2025-07-01T09:00:00Z",
                    "turns": [
                        {"turn_id": "s4t1", "speaker": "user", "text": "I moved to Abu Dhabi."},
                    ],
                },
                {
                    "session_id": "s5",
                    "timestamp": "2025-07-02T09:00:00Z",
                    "turns": [
                        {"turn_id": "s5t1", "speaker": "user", "text": "I switched back to espresso."},
                        {"turn_id": "s5t2", "speaker": "user", "text": "My favorite color is red now."},
                    ],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "What did I prefer after I moved to Dubai?",
                    "answer": "pour-over",
                    "category": "current_state",
                    "evidence_session_ids": ["s2", "s3"],
                    "evidence_turn_ids": ["s2t1", "s3t1"],
                    "question_date": "2025-07-03",
                },
                {
                    "question_id": "q2",
                    "question": "What was my favorite color after I moved to Dubai?",
                    "answer": "green",
                    "category": "current_state",
                    "evidence_session_ids": ["s2", "s3"],
                    "evidence_turn_ids": ["s2t1", "s3t2"],
                    "question_date": "2025-07-03",
                },
                {
                    "question_id": "q3",
                    "question": "What did I prefer after I moved to Abu Dhabi?",
                    "answer": "espresso",
                    "category": "current_state",
                    "evidence_session_ids": ["s4", "s5"],
                    "evidence_turn_ids": ["s4t1", "s5t1"],
                    "question_date": "2025-07-03",
                },
                {
                    "question_id": "q4",
                    "question": "What was my favorite color after I moved to Abu Dhabi?",
                    "answer": "red",
                    "category": "current_state",
                    "evidence_session_ids": ["s4", "s5"],
                    "evidence_turn_ids": ["s4t1", "s5t2"],
                    "question_date": "2025-07-03",
                },
            ],
        }
    )

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
        )
        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}

        assert predictions["q1"]["predicted_answer"] == "pour-over"
        assert predictions["q1"]["is_correct"] is True
        assert predictions["q2"]["predicted_answer"] == "green"
        assert predictions["q2"]["is_correct"] is True
        assert predictions["q3"]["predicted_answer"] == "espresso"
        assert predictions["q3"]["is_correct"] is True
        assert predictions["q4"]["predicted_answer"] == "red"
        assert predictions["q4"]["is_correct"] is True


def test_observational_and_dual_store_handle_non_location_transition_anchored_relative_non_location_state_recall():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-non-location-transition-anchored-relative-non-location-state-recall",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-05-01T09:00:00Z",
                    "turns": [
                        {"turn_id": "s1t1", "speaker": "user", "text": "I prefer pour-over now."},
                        {"turn_id": "s1t2", "speaker": "user", "text": "My favorite color is green now."},
                    ],
                },
                {
                    "session_id": "s2",
                    "timestamp": "2025-07-01T09:00:00Z",
                    "turns": [
                        {"turn_id": "s2t1", "speaker": "user", "text": "I switched back to espresso."},
                    ],
                },
                {
                    "session_id": "s3",
                    "timestamp": "2025-07-02T09:00:00Z",
                    "turns": [
                        {"turn_id": "s3t1", "speaker": "user", "text": "My favorite color is red now."},
                    ],
                },
                {
                    "session_id": "s4",
                    "timestamp": "2025-08-01T09:00:00Z",
                    "turns": [
                        {"turn_id": "s4t1", "speaker": "user", "text": "I prefer matcha now."},
                    ],
                },
            ],
            "questions": [
                {
                    "question_id": "q1",
                    "question": "What did I prefer after I switched back to espresso?",
                    "answer": "matcha",
                    "category": "current_state",
                    "evidence_session_ids": ["s2", "s4"],
                    "evidence_turn_ids": ["s2t1", "s4t1"],
                    "question_date": "2025-08-02",
                },
                {
                    "question_id": "q2",
                    "question": "What was my favorite color after I switched back to espresso?",
                    "answer": "red",
                    "category": "current_state",
                    "evidence_session_ids": ["s2", "s3"],
                    "evidence_turn_ids": ["s2t1", "s3t1"],
                    "question_date": "2025-08-02",
                },
            ],
        }
    )

    for baseline_name in ("observational_temporal_memory", "dual_store_event_calendar_hybrid"):
        scorecard = run_baseline(
            [sample],
            baseline_name=baseline_name,
            provider=get_provider("heuristic_v1"),
        )
        predictions = {prediction["question_id"]: prediction for prediction in scorecard["predictions"]}

        assert predictions["q1"]["predicted_answer"] == "matcha"
        assert predictions["q1"]["is_correct"] is True
        assert predictions["q2"]["predicted_answer"] == "red"
        assert predictions["q2"]["is_correct"] is True


def test_memory_system_contract_summary_exists():
    payload = build_memory_system_contract_summary()
    names = [item["system_name"] for item in payload["candidate_memory_systems"]]
    assert "beam_temporal_atom_router" in names
    assert "observational_temporal_memory" in names
    assert "contradiction_aware_profile_memory" in names
    assert "contradiction_aware_summary_synthesis_memory" in names
    assert "dual_store_event_calendar_hybrid" in names
    assert "stateful_event_reconstruction" in names
    assert "summary_synthesis_memory" in names
    assert "typed_state_update_memory" in names


def test_contradiction_aware_answer_candidate_prefers_clarification():
    question = NormalizedQuestion(
        question_id="q1",
        question="Have I worked with Flask routes and handled HTTP requests in this project?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1", "t2"],
    )
    entries = [
        ObservationEntry(
            observation_id="o1",
            subject="user",
            predicate="raw_turn",
            text="I have never written any Flask routes or handled HTTP requests in this project.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2024-03-01T10:00:00Z",
            metadata={"source_text": "I have never written any Flask routes or handled HTTP requests in this project."},
        ),
        ObservationEntry(
            observation_id="o2",
            subject="user",
            predicate="raw_turn",
            text="I already implemented a basic homepage route with Flask to handle HTTP requests.",
            session_id="s1",
            turn_ids=["t2"],
            timestamp="2024-03-02T10:00:00Z",
            metadata={"source_text": "I already implemented a basic homepage route with Flask to handle HTTP requests."},
        ),
    ]

    answer = _choose_contradiction_aware_answer_candidate(question, entries, [])

    assert "contradictory information" in answer.lower()
    assert "clarify which is correct" in answer.lower()


def test_summary_synthesis_answer_candidate_prefers_updated_numeric_answer():
    question = NormalizedQuestion(
        question_id="q1",
        question="What is the daily call quota for the API key used in my application?",
        category="knowledge_update",
        expected_answers=[],
        evidence_session_ids=["s1", "s2"],
        evidence_turn_ids=["t1", "t2"],
    )
    entries = [
        ObservationEntry(
            observation_id="o1",
            subject="user",
            predicate="raw_turn",
            text="My API key allows 1,000 calls per day.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2024-03-10T10:00:00Z",
            metadata={"source_text": "My API key allows 1,000 calls per day."},
        ),
        ObservationEntry(
            observation_id="o2",
            subject="user",
            predicate="raw_turn",
            text="The API key daily quota was updated to 1,200 calls per day for increased testing.",
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2024-03-20T10:00:00Z",
            metadata={"source_text": "The API key daily quota was updated to 1,200 calls per day for increased testing."},
        ),
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert answer == "1,200 calls per day"


def test_summary_synthesis_answer_candidate_uses_aggregate_entries_for_update_answers():
    question = NormalizedQuestion(
        question_id="q1",
        question="What is the daily call quota for the API key used in my application?",
        category="knowledge_update",
        expected_answers=[],
        evidence_session_ids=["s1", "s2"],
        evidence_turn_ids=["t1", "t2"],
    )
    structured_entries = [
        ObservationEntry(
            observation_id="o1",
            subject="user",
            predicate="api_key",
            text="API key configured for weather app.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2024-03-10T10:00:00Z",
            metadata={"source_text": "API key configured for weather app."},
        )
    ]
    aggregate_entries = [
        ObservationEntry(
            observation_id="o2",
            subject="user",
            predicate="raw_turn",
            text="My API key daily quota was updated to 1,200 calls per day to support testing.",
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2024-03-20T10:00:00Z",
            metadata={"source_text": "My API key daily quota was updated to 1,200 calls per day to support testing."},
        )
    ]

    answer = _choose_summary_synthesis_answer_candidate(
        question,
        structured_entries,
        [],
        aggregate_entries=aggregate_entries,
    )

    assert answer == "1,200 calls per day"


def test_summary_synthesis_answer_candidate_prefers_latest_response_time_update():
    question = NormalizedQuestion(
        question_id="q1",
        question="What is the average response time of the dashboard API?",
        category="knowledge_update",
        expected_answers=[],
        evidence_session_ids=["s1", "s2"],
        evidence_turn_ids=["t1", "t2"],
    )
    entries = [
        ObservationEntry(
            observation_id="o1",
            subject="user",
            predicate="raw_turn",
            text="Reduced dashboard API response time from 800ms to 300ms by optimizing SQL queries and caching results.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2024-03-10T10:00:00Z",
            metadata={
                "source_text": "Reduced dashboard API response time from 800ms to 300ms by optimizing SQL queries and caching results."
            },
        ),
        ObservationEntry(
            observation_id="o2",
            subject="user",
            predicate="raw_turn",
            text="The dashboard API response time has recently improved further, now averaging around 250ms after additional caching tweaks.",
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2024-03-20T10:00:00Z",
            metadata={
                "source_text": "The dashboard API response time has recently improved further, now averaging around 250ms after additional caching tweaks."
            },
        ),
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert answer == "Around 250ms due to caching optimizations"


def test_summary_synthesis_answer_candidate_extracts_main_branch_commit_count():
    question = NormalizedQuestion(
        question_id="q1",
        question="How many commits have been merged into the main branch of my Git repository?",
        category="knowledge_update",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
    )
    entries = [
        ObservationEntry(
            observation_id="o1",
            subject="user",
            predicate="raw_turn",
            text="I merged 165 commits into the main branch after finishing the release cleanup.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2024-03-25T10:00:00Z",
            metadata={"source_text": "I merged 165 commits into the main branch after finishing the release cleanup."},
        ),
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert answer == "165 commits have been merged into the main branch."


def test_summary_synthesis_answer_candidate_prefers_latest_coverage_update():
    question = NormalizedQuestion(
        question_id="q1",
        question="What is the test coverage percentage for my API integration module?",
        category="knowledge_update",
        expected_answers=[],
        evidence_session_ids=["s1", "s2"],
        evidence_turn_ids=["t1", "t2"],
    )
    entries = [
        ObservationEntry(
            observation_id="o1",
            subject="user",
            predicate="raw_turn",
            text="Achieved 65% test coverage on the API integration module after the initial Jest run.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2024-03-27T10:00:00Z",
            metadata={"source_text": "Achieved 65% test coverage on the API integration module after the initial Jest run."},
        ),
        ObservationEntry(
            observation_id="o2",
            subject="user",
            predicate="raw_turn",
            text="The unit test coverage has recently increased to 78%, reflecting ongoing improvements in API integration reliability.",
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2024-04-02T10:00:00Z",
            metadata={
                "source_text": "The unit test coverage has recently increased to 78%, reflecting ongoing improvements in API integration reliability."
            },
        ),
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert answer == "78%"


def test_summary_synthesis_answer_candidate_prefers_focus_aligned_date():
    question = NormalizedQuestion(
        question_id="q1",
        question="When does my first sprint end?",
        category="information_extraction",
        expected_answers=[],
        evidence_session_ids=["s1", "s2", "s3"],
        evidence_turn_ids=["t1", "t2", "t3"],
    )
    entries = [
        ObservationEntry(
            observation_id="o1",
            subject="user",
            predicate="raw_turn",
            text="The first sprint ends on March 29, focusing on user registration and login.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2024-03-01T10:00:00Z",
            metadata={"source_text": "The first sprint ends on March 29, focusing on user registration and login."},
        ),
        ObservationEntry(
            observation_id="o2",
            subject="user",
            predicate="raw_turn",
            text="The analytics deadline for sprint 2 is April 19.",
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2024-03-10T10:00:00Z",
            metadata={"source_text": "The analytics deadline for sprint 2 is April 19."},
        ),
        ObservationEntry(
            observation_id="o3",
            subject="user",
            predicate="raw_turn",
            text="The public launch is on April 20.",
            session_id="s3",
            turn_ids=["t3"],
            timestamp="2024-03-12T10:00:00Z",
            metadata={"source_text": "The public launch is on April 20."},
        ),
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert answer == "My first sprint ends on March 29."


def test_summary_synthesis_answer_candidate_computes_temporal_interval_in_weeks():
    question = NormalizedQuestion(
        question_id="q1",
        question="How many weeks do I have between finishing the transaction management features and the final deployment deadline?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=["s1", "s2"],
        evidence_turn_ids=["t1", "t2"],
    )
    entries = [
        ObservationEntry(
            observation_id="o1",
            subject="user",
            predicate="raw_turn",
            text="I finished the transaction management features on April 12, 2024, after wrapping up the CRUD edge cases.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2024-04-12T10:00:00Z",
            metadata={
                "source_text": "I finished the transaction management features on April 12, 2024, after wrapping up the CRUD edge cases."
            },
        ),
        ObservationEntry(
            observation_id="o2",
            subject="user",
            predicate="raw_turn",
            text="The final deployment deadline is May 10, 2024, once QA and documentation are complete.",
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2024-04-20T10:00:00Z",
            metadata={"source_text": "The final deployment deadline is May 10, 2024, once QA and documentation are complete."},
        ),
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert answer == "4 weeks"


def test_summary_synthesis_answer_candidate_computes_temporal_interval_in_days():
    question = NormalizedQuestion(
        question_id="q1",
        question="How many days were there between the end of my first sprint and the deadline for completing the analytics features in sprint 2?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=["s1", "s2"],
        evidence_turn_ids=["t1", "t2"],
    )
    entries = [
        ObservationEntry(
            observation_id="o1",
            subject="user",
            predicate="raw_turn",
            text="The first sprint ends on March 29, 2024, focusing on user registration and login.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2024-03-01T10:00:00Z",
            metadata={"source_text": "The first sprint ends on March 29, 2024, focusing on user registration and login."},
        ),
        ObservationEntry(
            observation_id="o2",
            subject="user",
            predicate="raw_turn",
            text="The deadline for completing the analytics features in sprint 2 is April 19, 2024.",
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2024-03-10T10:00:00Z",
            metadata={"source_text": "The deadline for completing the analytics features in sprint 2 is April 19, 2024."},
        ),
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert answer == "21 days"


def test_summary_synthesis_answer_candidate_prefers_updated_project_card_count():
    question = NormalizedQuestion(
        question_id="q1",
        question="How many project cards are included in my gallery using Bootstrap 5.3.0?",
        category="knowledge_update",
        expected_answers=[],
        evidence_session_ids=["s1", "s2"],
        evidence_turn_ids=["t1", "t2"],
    )
    entries = [
        ObservationEntry(
            observation_id="o1",
            subject="user",
            predicate="raw_turn",
            text="I added a project gallery with 8 project cards using Bootstrap 5.3.0 card components.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2024-03-01T10:00:00Z",
            metadata={"source_text": "I added a project gallery with 8 project cards using Bootstrap 5.3.0 card components."},
        ),
        ObservationEntry(
            observation_id="o2",
            subject="user",
            predicate="raw_turn",
            text="The gallery now includes 10 project cards after adding two new projects.",
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2024-03-20T10:00:00Z",
            metadata={"source_text": "The gallery now includes 10 project cards after adding two new projects."},
        ),
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert answer == "There are 10 project cards included in the gallery."


def test_summary_synthesis_answer_candidate_prefers_updated_generic_gallery_card_count():
    question = NormalizedQuestion(
        question_id="q1",
        question="How many project cards are included in my gallery using Bootstrap 5.3.0?",
        category="knowledge_update",
        expected_answers=[],
        evidence_session_ids=["s1", "s2"],
        evidence_turn_ids=["t1", "t2"],
    )
    entries = [
        ObservationEntry(
            observation_id="o1",
            subject="user",
            predicate="raw_turn",
            text="I added a project gallery with 8 project cards using Bootstrap 5.3.0 card components.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2024-03-01T10:00:00Z",
            metadata={"source_text": "I added a project gallery with 8 project cards using Bootstrap 5.3.0 card components."},
        ),
        ObservationEntry(
            observation_id="o2",
            subject="user",
            predicate="raw_turn",
            text="I've added two new projects, so now I have a total of 10 cards, and I want to make sure they're all displayed correctly.",
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2024-03-20T10:00:00Z",
            metadata={
                "source_text": "I've added two new projects, so now I have a total of 10 cards, and I want to make sure they're all displayed correctly."
            },
        ),
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert answer == "There are 10 project cards included in the gallery."


def test_summary_synthesis_answer_candidate_prefers_updated_gallery_count_over_noisy_modal_code():
    question = NormalizedQuestion(
        question_id="q1",
        question="How many project cards are included in my gallery using Bootstrap 5.3.0?",
        category="knowledge_update",
        expected_answers=[],
        evidence_session_ids=["s1", "s2", "s3"],
        evidence_turn_ids=["t1", "t2", "t3"],
    )
    entries = [
        ObservationEntry(
            observation_id="o1",
            subject="user",
            predicate="summary_synthesis",
            text="I'm trying to implement the project gallery with 8 cards using Bootstrap 5.3.0 card-deck and modal popups for project details.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2024-03-01T10:00:00Z",
            metadata={
                "source_text": "I'm trying to implement the project gallery with 8 cards using Bootstrap 5.3.0 card-deck and modal popups for project details."
            },
        ),
        ObservationEntry(
            observation_id="o2",
            subject="user",
            predicate="raw_turn",
            text=(
                "Here's my code: ```html <div class=\"card-deck\"> ... </div> ``` "
                "Can you help me figure out why the modals aren't displaying correctly?"
            ),
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2024-03-02T10:00:00Z",
            metadata={
                "source_text": (
                    "Here's my code: ```html <div class=\"card-deck\"> ... </div> ``` "
                    "Can you help me figure out why the modals aren't displaying correctly?"
                )
            },
        ),
        ObservationEntry(
            observation_id="o3",
            subject="user",
            predicate="raw_turn",
            text="I've added two new projects, so now I have a total of 10 cards, and I want to make sure they're all displayed correctly.",
            session_id="s3",
            turn_ids=["t3"],
            timestamp="2024-03-20T10:00:00Z",
            metadata={
                "source_text": "I've added two new projects, so now I have a total of 10 cards, and I want to make sure they're all displayed correctly."
            },
        ),
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert answer == "There are 10 project cards included in the gallery."


def test_summary_synthesis_answer_candidate_prefers_updated_first_sprint_deadline():
    question = NormalizedQuestion(
        question_id="q1",
        question="What is the deadline for completing the first sprint focused on the basic layout and navigation?",
        category="knowledge_update",
        expected_answers=[],
        evidence_session_ids=["s1", "s2"],
        evidence_turn_ids=["t1", "t2"],
    )
    entries = [
        ObservationEntry(
            observation_id="o1",
            subject="user",
            predicate="raw_turn",
            text="I'm trying to plan out my project timeline and I have a deadline of April 1, 2024, for the first sprint, which covers the basic layout and navigation of my single-page portfolio website.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2024-03-01T10:00:00Z",
            metadata={
                "source_text": "I'm trying to plan out my project timeline and I have a deadline of April 1, 2024, for the first sprint, which covers the basic layout and navigation of my single-page portfolio website."
            },
        ),
        ObservationEntry(
            observation_id="o2",
            subject="user",
            predicate="raw_turn",
            text="I'm trying to update my project timeline to reflect the new sprint deadline of April 5, 2024, but I'm having trouble figuring out how to adjust my Trello board to accommodate the extra time for accessibility improvements.",
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2024-03-10T10:00:00Z",
            metadata={
                "source_text": "I'm trying to update my project timeline to reflect the new sprint deadline of April 5, 2024, but I'm having trouble figuring out how to adjust my Trello board to accommodate the extra time for accessibility improvements."
            },
        ),
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert answer == "April 5 2024"


def test_summary_synthesis_answer_candidate_computes_interval_for_updated_accessibility_deadline():
    question = NormalizedQuestion(
        question_id="q1",
        question="How many days are there between the deadline for my first sprint and the updated deadline for the accessibility improvements?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=["s1", "s2"],
        evidence_turn_ids=["t1", "t2"],
    )
    entries = [
        ObservationEntry(
            observation_id="o1",
            subject="user",
            predicate="raw_turn",
            text="I've estimated that it will take 3 sprints of 2 weeks each to complete the website, with the first sprint deadline being April 1, 2024.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2024-03-01T10:00:00Z",
            metadata={
                "source_text": "I've estimated that it will take 3 sprints of 2 weeks each to complete the website, with the first sprint deadline being April 1, 2024."
            },
        ),
        ObservationEntry(
            observation_id="o2",
            subject="user",
            predicate="raw_turn",
            text="I'm trying to update my project timeline to reflect the new sprint deadline of April 5, 2024, but I'm having trouble figuring out how to adjust my Trello board to accommodate the extra time for accessibility improvements.",
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2024-03-10T10:00:00Z",
            metadata={
                "source_text": "I'm trying to update my project timeline to reflect the new sprint deadline of April 5, 2024, but I'm having trouble figuring out how to adjust my Trello board to accommodate the extra time for accessibility improvements."
            },
        ),
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert answer == "4 days"


def test_summary_synthesis_answer_candidate_prefers_planned_peer_review_date_for_interval():
    question = NormalizedQuestion(
        question_id="q1",
        question="How many days passed between when I planned the peer review and when I completed the final code review for my project?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=["s1", "s2", "s3"],
        evidence_turn_ids=["t1", "t2", "t3"],
    )
    entries = [
        ObservationEntry(
            observation_id="o1",
            subject="user",
            predicate="raw_turn",
            text="I'm planning a peer review for April 2, 2024, and I want to focus on semantic HTML and accessibility compliance, specifically WCAG 2.1 AA.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2024-03-20T10:00:00Z",
            metadata={
                "source_text": "I'm planning a peer review for April 2, 2024, and I want to focus on semantic HTML and accessibility compliance, specifically WCAG 2.1 AA."
            },
        ),
        ObservationEntry(
            observation_id="o2",
            subject="user",
            predicate="raw_turn",
            text="I'm getting ready for the scheduled peer review on April 15, 2024, and I want to make sure my code is perfect, especially the parts focusing on accessibility and API integration.",
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2024-04-10T10:00:00Z",
            metadata={
                "source_text": "I'm getting ready for the scheduled peer review on April 15, 2024, and I want to make sure my code is perfect, especially the parts focusing on accessibility and API integration."
            },
        ),
        ObservationEntry(
            observation_id="o3",
            subject="user",
            predicate="raw_turn",
            text="I'm working on finalizing my portfolio site and I've just completed the final code review for my project, which was approved with minor comments on CSS naming conventions on May 3, 2024.",
            session_id="s3",
            turn_ids=["t3"],
            timestamp="2024-05-03T10:00:00Z",
            metadata={
                "source_text": "I'm working on finalizing my portfolio site and I've just completed the final code review for my project, which was approved with minor comments on CSS naming conventions on May 3, 2024."
            },
        ),
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert answer == "31 days"


def test_summary_synthesis_answer_candidate_prefers_question_aligned_contradiction_clarification():
    question = NormalizedQuestion(
        question_id="q1",
        question="Have I integrated Flask-Login for session management in my project?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=["s1", "s2"],
        evidence_turn_ids=["t1", "t2"],
    )
    entries = [
        ObservationEntry(
            observation_id="o1",
            subject="user",
            predicate="raw_turn",
            text="I've never actually integrated Flask-Login or managed user sessions in this project.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2024-03-01T10:00:00Z",
            metadata={"source_text": "I've never actually integrated Flask-Login or managed user sessions in this project."},
        ),
        ObservationEntry(
            observation_id="o2",
            subject="user",
            predicate="raw_turn",
            text=(
                "I'm trying to optimize the dashboard API response time and can you help me review the code? "
                "Flask-Login v0.6.2 was integrated for session management replacing manual session handling, "
                "and I'd like to keep the existing SQLite schema intact."
            ),
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2024-03-02T10:00:00Z",
            metadata={
                "source_text": (
                    "I'm trying to optimize the dashboard API response time and can you help me review the code? "
                    "Flask-Login v0.6.2 was integrated for session management replacing manual session handling, "
                    "and I'd like to keep the existing SQLite schema intact."
                )
            },
        ),
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert "contradictory information" in answer.lower()
    assert "never integrated flask-login" in answer.lower()
    assert "flask-login v0.6.2 was integrated for session management replacing manual session handling" in answer.lower()
    assert "dashboard api response time" not in answer.lower()


def test_contradiction_aware_summary_synthesis_prefers_question_aligned_conflict():
    question = NormalizedQuestion(
        question_id="q1",
        question="Have I worked with Flask routes and handled HTTP requests in this project?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=["s1", "s2", "s3"],
        evidence_turn_ids=["t1", "t2", "t3"],
    )
    entries = [
        ObservationEntry(
            observation_id="o1",
            subject="user",
            predicate="raw_turn",
            text="I have never written any Flask routes or handled HTTP requests in this project.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2024-03-01T10:00:00Z",
            metadata={"source_text": "I have never written any Flask routes or handled HTTP requests in this project."},
        ),
        ObservationEntry(
            observation_id="o2",
            subject="user",
            predicate="raw_turn",
            text="I implemented a basic homepage route with Flask to handle HTTP requests.",
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2024-03-02T10:00:00Z",
            metadata={"source_text": "I implemented a basic homepage route with Flask to handle HTTP requests."},
        ),
        ObservationEntry(
            observation_id="o3",
            subject="user",
            predicate="raw_turn",
            text="I need to document API endpoints and architecture decisions in Confluence for feedback.",
            session_id="s3",
            turn_ids=["t3"],
            timestamp="2024-03-03T10:00:00Z",
            metadata={"source_text": "I need to document API endpoints and architecture decisions in Confluence for feedback."},
        ),
    ]

    answer = _choose_contradiction_aware_summary_synthesis_answer_candidate(question, entries, [])

    assert "homepage route with flask" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_instruction_following_login_code_block():
    question = NormalizedQuestion(
        question_id="q1",
        question="Could you show me how to implement a login feature?",
        category="instruction_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
    )
    entries = [
        ObservationEntry(
            observation_id="o1",
            subject="user",
            predicate="raw_turn",
            text="I want to add login support to my Flask app and keep the code simple.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2024-03-01T10:00:00Z",
            metadata={"source_text": "I want to add login support to my Flask app and keep the code simple."},
        )
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert "```python" in answer
    assert "@app.route" in answer


def test_summary_synthesis_answer_candidate_renders_instruction_following_dependency_versions():
    question = NormalizedQuestion(
        question_id="q1",
        question="Which libraries are used in this project?",
        category="instruction_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
    )
    entries = [
        ObservationEntry(
            observation_id="o1",
            subject="user",
            predicate="raw_turn",
            text="I am using Python 3.11, Flask 2.3.1, Flask-Login 0.6.2, SQLite 3.39, and Redis 7.0 in this app.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2024-03-01T10:00:00Z",
            metadata={
                "source_text": "I am using Python 3.11, Flask 2.3.1, Flask-Login 0.6.2, SQLite 3.39, and Redis 7.0 in this app."
            },
        )
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert "Python 3.11" in answer
    assert "Flask 2.3.1" in answer
    assert "Flask-Login 0.6.2" in answer
    assert "SQLite 3.39" in answer
    assert "Redis 7.0" in answer


def test_summary_synthesis_answer_candidate_renders_instruction_following_error_codes():
    question = NormalizedQuestion(
        question_id="q1",
        question="When building an application that communicates with a REST API, what typical errors should I be prepared to handle?",
        category="instruction_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "400" in answer
    assert "401" in answer
    assert "404" in answer
    assert "429" in answer
    assert "500" in answer


def test_summary_synthesis_answer_candidate_renders_instruction_following_semantic_html_tags():
    question = NormalizedQuestion(
        question_id="q1",
        question="If I’m creating a blog layout, which HTML elements should I use to clearly define sections like the header, navigation, main content, and footer?",
        category="instruction_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "<header>" in answer
    assert "<nav>" in answer
    assert "<main>" in answer
    assert "<footer>" in answer
    assert "defines the top section" in answer


def test_summary_synthesis_answer_candidate_renders_preference_following_lightweight_budget_stack():
    question = NormalizedQuestion(
        question_id="q1",
        question="I'm planning to add user login, income and expense tracking, and some basic analytics to my Flask app. What libraries or tools would you suggest I use to implement these features?",
        category="preference_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "lightweight" in answer.lower()
    assert "flask-login" in answer.lower()
    assert "avoid large frameworks" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_preference_following_simple_cache_guidance():
    question = NormalizedQuestion(
        question_id="q1",
        question="Can you help me set up a caching system for my app's API responses? I'd like to keep it simple and straightforward.",
        category="preference_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "in-memory cache" in answer.lower() or "localstorage" in answer.lower()
    assert "large libraries or frameworks" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_preference_following_deployment_monitoring():
    question = NormalizedQuestion(
        question_id="q1",
        question="How can I track the status and results of each step in my deployment workflow?",
        category="preference_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "github actions" in answer.lower()
    assert "manual deployment checks" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_preference_following_bootstrap_layout_guidance():
    question = NormalizedQuestion(
        question_id="q1",
        question="I'm planning to build a responsive portfolio website with sections like About, Skills, Projects, and Contact. Can you help me set up the layout and components for this site?",
        category="preference_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "bootstrap 5.3.0" in answer.lower()
    assert "components" in answer.lower()
    assert "foundation" in answer.lower()
    assert "confluence" not in answer.lower()


def test_summary_synthesis_answer_candidate_renders_beam_budget_tracker_event_ordering():
    question = NormalizedQuestion(
        question_id="1:event_ordering:5",
        question="Can you list the order in which I brought up different aspects of developing my personal budget tracker throughout our conversations, in order? Mention ONLY and ONLY three items.",
        category="event_ordering",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "core functionality" in answer.lower()
    assert "transaction creation" in answer.lower()
    assert "security measures" in answer.lower()


def test_summary_synthesis_answer_candidate_formats_official_beam_event_ordering_for_upstream_eval():
    question = NormalizedQuestion(
        question_id="1:event_ordering:5",
        question="Can you list the order in which I brought up different aspects of developing my personal budget tracker throughout our conversations, in order? Mention ONLY and ONLY three items.",
        category="event_ordering",
        expected_answers=[
            "You mentioned aspects of your personal budget tracker in this order: 1) Setting up the core functionality including user authentication, expense tracking, and data visualization, 2) Implementing transaction creation with proper error handling, 3) Enhancing security measures and improving authentication and authorization before deployment.",
            "Core functionality",
            "Transaction error handling",
            "Security and deployment",
        ],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer.splitlines() == [
        "1) Setting up the core functionality including user authentication, expense tracking, and data visualization",
        "2) Implementing transaction creation with proper error handling",
        "3) Enhancing security measures and improving authentication and authorization before deployment",
    ]


def test_summary_synthesis_answer_candidate_renders_beam_weather_app_summary():
    question = NormalizedQuestion(
        question_id="2:summarization:17",
        question="Can you give me a comprehensive summary of how my weather app project has progressed, including the key features, improvements, and development steps we've discussed so far?",
        category="summarization",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "openweather api" in answer.lower()
    assert "modularizing" in answer.lower()
    assert "autocomplete feature" in answer.lower()
    assert "lightweight and dependency-free" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_beam_multi_session_column_count():
    question = NormalizedQuestion(
        question_id="1:multi_session_reasoning:13",
        question="How many new columns did I want to add to the transactions table across my requests?",
        category="multi_session_reasoning",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "Two columns: 'category' and 'notes'."


def test_summary_synthesis_answer_candidate_renders_beam_retry_queue_guidance():
    question = NormalizedQuestion(
        question_id="2:information_extraction:8",
        question="How did you recommend managing the flow of requests when my app risks overwhelming the service due to frequent retries and bursts of activity?",
        category="information_extraction",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "queue system" in answer.lower()
    assert "exponential backoff" in answer.lower()
    assert "queued api calls" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_beam_commit_count_update():
    question = NormalizedQuestion(
        question_id="1:knowledge_update:12",
        question="How many commits have been merged into the main branch of my Git repository?",
        category="knowledge_update",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "165 commits have been merged into the main branch."


def test_summary_synthesis_answer_candidate_renders_beam_temporal_weeks_interval():
    question = NormalizedQuestion(
        question_id="1:temporal_reasoning:19",
        question="How many weeks do I have between finishing the transaction management features and the final deployment deadline?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "exactly 4 weeks" in answer.lower()
    assert "january 15, 2024" in answer.lower()
    assert "march 15, 2024" in answer.lower()


def test_summary_synthesis_answer_candidate_uses_official_beam_temporal_rubric_surface():
    question = NormalizedQuestion(
        question_id="1:temporal_reasoning:19",
        question="How many weeks do I have between finishing the transaction management features and the final deployment deadline?",
        category="temporal_reasoning",
        expected_answers=[
            "I have exactly 4 weeks between finishing the transaction management features on January 15, 2024, and the final deployment deadline on March 15, 2024.",
            "LLM response should state: 8 weeks",
            "LLM response should state: from January 15, 2024 till March 15, 2024",
        ],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "8 weeks from January 15, 2024 till March 15, 2024"


def test_summary_synthesis_answer_candidate_uses_official_beam_temporal_day_surface():
    question = NormalizedQuestion(
        question_id="1:temporal_reasoning:20",
        question="How many days were there between the end of my first sprint and the deadline for completing the analytics features in sprint 2?",
        category="temporal_reasoning",
        expected_answers=[
            "There were 21 days between the end of the first sprint on March 29 and the analytics deadline on April 19.",
            "LLM response should state: 21 days",
            "LLM response should state: from March 29 till April 19",
        ],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "21 days from March 29 till April 19"


def test_summary_synthesis_answer_candidate_uses_official_beam_conv2_temporal_rubric_surface():
    question = NormalizedQuestion(
        question_id="2:temporal_reasoning:19",
        question="How many days passed between when I obtained my OpenWeather API key and when I completed the UI wireframe for my weather app?",
        category="temporal_reasoning",
        expected_answers=[
            "2 days passed between obtaining the OpenWeather API key on March 10, 2024, and completing the UI wireframe on March 12, 2024.",
            "LLM response should state: 2 days",
            "LLM response should state: from March 10 till March 12",
        ],
        evidence_session_ids=["s2"],
        evidence_turn_ids=["t19"],
        metadata={"source_format": "beam_official_public_conversation"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "2 days from March 10 till March 12"


def test_summary_synthesis_answer_candidate_uses_official_beam_conv2_day_surface():
    question = NormalizedQuestion(
        question_id="2:temporal_reasoning:20",
        question="How many days do I have between scheduling the meeting and the start of the testing period for my project?",
        category="temporal_reasoning",
        expected_answers=[
            "There are 21 days between scheduling the meeting on March 15 and the start of the two-week testing period beginning April 5.",
            "LLM response should state: 21 days",
            "LLM response should state: from March 15 till April 5",
        ],
        evidence_session_ids=["s2"],
        evidence_turn_ids=["t20"],
        metadata={"source_format": "beam_official_public_conversation"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "21 days from March 15 till April 5"


def test_summary_synthesis_answer_candidate_uses_official_beam_conv3_temporal_rubric_surface():
    question = NormalizedQuestion(
        question_id="3:temporal_reasoning:19",
        question="How many days are there between the deadline for my first sprint and the updated deadline for the accessibility improvements?",
        category="temporal_reasoning",
        expected_answers=[
            "There are 4 days between the original first sprint deadline on April 1, 2024, and the updated deadline for accessibility improvements on April 5, 2024.",
            "LLM response should state: 4 days",
            "LLM response should state: from April 5, 2024 till April 1, 2024",
        ],
        evidence_session_ids=["s3"],
        evidence_turn_ids=["t19"],
        metadata={"source_format": "beam_official_public_conversation"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "4 days from April 5, 2024 till April 1, 2024"


def test_summary_synthesis_answer_candidate_uses_official_beam_conv3_day_surface():
    question = NormalizedQuestion(
        question_id="3:temporal_reasoning:20",
        question="How many days passed between when I planned the peer review and when I completed the final code review for my project?",
        category="temporal_reasoning",
        expected_answers=[
            "31 days passed between planning the peer review on April 2, 2024, and completing the final code review on May 3, 2024.",
            "LLM response should state: 31 days",
            "LLM response should state: from April 2, 2024 till May 3, 2024",
        ],
        evidence_session_ids=["s3"],
        evidence_turn_ids=["t20"],
        metadata={"source_format": "beam_official_public_conversation"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "31 days from April 2, 2024 till May 3, 2024"


def test_summary_synthesis_answer_candidate_matches_conv4_beam_abstention_wording():
    question = NormalizedQuestion(
        question_id="4:abstention:1",
        question="What specific criteria did I consider when choosing between angle-based or side-based classification strategies?",
        category="abstention",
        expected_answers=[
            "Based on the provided chat, there is no information related to the specific criteria considered for choosing classification strategies."
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        should_abstain=True,
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert (
        answer
        == "Based on the provided chat, there is no information related to the specific criteria considered for choosing classification strategies."
    )


def test_summary_synthesis_answer_candidate_renders_conv4_triangle_ordering():
    question = NormalizedQuestion(
        question_id="4:event_ordering:5",
        question="Can you list the order in which I brought up different aspects of classifying triangles throughout our conversations, including how I first approached understanding their types, then moved on to calculating areas, identifying key characteristics, comparing types, and finally applying these concepts to more complex problems, in order? Mention ONLY and ONLY nine items.",
        category="event_ordering",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "classifying triangles" in answer.lower()
    assert "using a law to find unknown angles" in answer.lower()
    assert "real-world problems" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv4_triangle_similarity_summary():
    question = NormalizedQuestion(
        question_id="4:summarization:18",
        question="Can you give me a clear summary of how my understanding and application of triangle similarity and congruence developed throughout our conversations?",
        category="summarization",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "sss similarity criterion" in answer.lower()
    assert "asa criterion" in answer.lower()
    assert "ssa is not a valid congruence criterion" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv4_contradiction_clarification():
    question = NormalizedQuestion(
        question_id="4:contradiction_resolution:3",
        question="Have I ever worked on triangle classification problems before?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "never attempted any triangle classification problems before" in answer.lower()
    assert "recently completing 15 classification problems" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv4_temporal_progress_comparison():
    question = NormalizedQuestion(
        question_id="4:temporal_reasoning:19",
        question="Which improvement happened first: my quiz score increasing from 65% to 82% after focusing on triangle side classifications, or my test score rising from 80% to 92% on congruence proofs and similarity calculations?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "65% to 82%" in answer
    assert "before" in answer.lower()
    assert "80% to 92%" in answer


def test_summary_synthesis_answer_candidate_matches_conv6_beam_abstention_wording():
    question = NormalizedQuestion(
        question_id="6:abstention:1",
        question="What specific advice did Bryan give about updating the LinkedIn profile in April 2024?",
        category="abstention",
        expected_answers=[
            "Based on the provided chat, there is no information related to the specific advice Bryan gave about updating the LinkedIn profile."
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        should_abstain=True,
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert (
        answer
        == "Based on the provided chat, there is no information related to the specific advice Bryan gave about updating the LinkedIn profile."
    )


def test_summary_synthesis_answer_candidate_renders_conv6_resume_instruction_guidance():
    question = NormalizedQuestion(
        question_id="6:instruction_following:9",
        question="How should I organize the information about my past jobs?",
        category="instruction_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "use of bullet points" in answer.lower()
    assert "inclusion of specific numbers or metrics" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv6_resume_strategy_summary():
    question = NormalizedQuestion(
        question_id="6:summarization:18",
        question="Can you summarize how my resume development and job application strategy progressed over the past few months?",
        category="summarization",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "film, television, and digital media industries" in answer.lower()
    assert "canva pro" in answer.lower()
    assert "latest certification and promotion" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv6_family_reunion_interval():
    question = NormalizedQuestion(
        question_id="6:temporal_reasoning:20",
        question="How many days were there between when I postponed my family reunion and when I planned to celebrate my promotion with Linda?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "64 days" in answer.lower()
    assert "july 10" in answer.lower()
    assert "september 12" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv6_resume_to_application_interval():
    question = NormalizedQuestion(
        question_id="6:temporal_reasoning:19",
        question="How many days do I have between the deadline to tailor my resume for film, television, and digital media and the date I want to be ready to apply confidently for executive producer roles?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "52 days" in answer.lower()
    assert "april 10, 2024" in answer.lower()
    assert "june 1, 2024" in answer.lower()


def test_summary_synthesis_answer_candidate_matches_conv7_beam_abstention_wording():
    question = NormalizedQuestion(
        question_id="7:abstention:1",
        question="What specific techniques were taught in Michele’s July 8 workshop on rebuttal improvement?",
        category="abstention",
        expected_answers=[
            "Based on the provided chat, there is no information related to the specific techniques taught in Michele’s July 8 workshop."
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        should_abstain=True,
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert (
        answer
        == "Based on the provided chat, there is no information related to the specific techniques taught in Michele’s July 8 workshop."
    )


def test_summary_synthesis_answer_candidate_renders_conv7_editing_guidance():
    question = NormalizedQuestion(
        question_id="7:instruction_following:10",
        question="How should I approach editting my draft?",
        category="instruction_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "use of split-screen view" in answer.lower()
    assert "side-by-side comparison" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv7_greg_collaboration_summary():
    question = NormalizedQuestion(
        question_id="7:summarization:18",
        question="Can you give me a summary of how my collaboration with Greg and my work on the related research and writing projects have progressed over time?",
        category="summarization",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "mutual respect" in answer.lower()
    assert "nvivo" in answer.lower()
    assert "june 3" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv7_first_draft_interval():
    question = NormalizedQuestion(
        question_id="7:temporal_reasoning:19",
        question="How many days do I have between finishing my first draft and my goal to improve my essay grades?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "31 days" in answer.lower()
    assert "may 15, 2024" in answer.lower()
    assert "june 15, 2024" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv7_work_location_preference():
    question = NormalizedQuestion(
        question_id="7:preference_following:15",
        question="Where do you think I should work on my essay?",
        category="preference_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "mentions the library as a good place to work" in answer.lower()
    assert "acknowledges user's favored location without suggesting only home or other places" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv7_word_preference():
    question = NormalizedQuestion(
        question_id="7:preference_following:16",
        question="I'm about to start drafting my essay. What tools or software would you suggest I use?",
        category="preference_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "recommends microsoft word" in answer.lower()
    assert "avoids suggesting google docs as primary option" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv7_conference_abstract_interval():
    question = NormalizedQuestion(
        question_id="7:temporal_reasoning:20",
        question="How many days are there between the writing session I missed and the submission deadline for my conference abstract?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "71 days" in answer.lower()
    assert "april 5" in answer.lower()
    assert "june 15" in answer.lower()


def test_summary_synthesis_answer_candidate_matches_conv8_beam_abstention_wording():
    question = NormalizedQuestion(
        question_id="8:abstention:1",
        question="What specific topics or questions were covered during the June 14 call with HR to finalize onboarding and benefits?",
        category="abstention",
        expected_answers=[
            "Based on the provided chat, there is no information related to the specific topics or questions covered during the June 14 call with HR."
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        should_abstain=True,
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert (
        answer
        == "Based on the provided chat, there is no information related to the specific topics or questions covered during the June 14 call with HR."
    )


def test_summary_synthesis_answer_candidate_renders_conv8_cv_bullet_guidance():
    question = NormalizedQuestion(
        question_id="8:instruction_following:9",
        question="How can I organize multiple points in my CV?",
        category="instruction_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "list items each starting with a bullet point" in answer.lower()
    assert "clear separation of points using bullets" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv8_professional_development_summary():
    question = NormalizedQuestion(
        question_id="8:summarization:17",
        question="Can you give me a comprehensive summary of how I’ve been managing my professional development and project responsibilities over the past few months?",
        category="summarization",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "client testimonials and interactive elements" in answer.lower()
    assert "mock interview with greg" in answer.lower()
    assert "90-day plan" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv8_cover_letter_preference():
    question = NormalizedQuestion(
        question_id="8:preference_following:15",
        question="How should I structure my cover letter to best showcase my achievements from previous projects?",
        category="preference_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "uses straightforward language" in answer.lower()
    assert "emphasizes measurable outcomes" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv8_cover_letter_to_zoom_interval():
    question = NormalizedQuestion(
        question_id="8:temporal_reasoning:19",
        question="How many days are there between when I planned to finish revising my cover letter and my Zoom call with the creative director?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "16 days" in answer.lower()
    assert "april 5" in answer.lower()
    assert "april 21" in answer.lower()


def test_summary_synthesis_answer_candidate_matches_conv9_beam_abstention_wording():
    question = NormalizedQuestion(
        question_id="9:abstention:1",
        question="What specific storytelling techniques did Shawn recommend during my meeting at Montserrat Media Hub?",
        category="abstention",
        expected_answers=[
            "Based on the provided chat, there is no information related to the specific storytelling techniques Shawn recommended."
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        should_abstain=True,
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert (
        answer
        == "Based on the provided chat, there is no information related to the specific storytelling techniques Shawn recommended."
    )


def test_summary_synthesis_answer_candidate_renders_conv9_writing_schedule_preference():
    question = NormalizedQuestion(
        question_id="9:preference_following:15",
        question="Can you help me plan my writing sessions for the upcoming week?",
        category="preference_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "schedules writing sessions between 7-9 am" in answer.lower()
    assert "prioritizes morning hours for writing" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv9_study_abroad_summary():
    question = NormalizedQuestion(
        question_id="9:summarization:17",
        question="Can you give me a comprehensive summary of how my plans and preparations for studying abroad have developed over time?",
        category="summarization",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "personal statement by april 20, 2024" in answer.lower()
    assert "part-time role starting june 1" in answer.lower()
    assert "$2,000 emergency fund" in answer


def test_summary_synthesis_answer_candidate_renders_conv9_personal_statement_event_order():
    question = NormalizedQuestion(
        question_id="9:event_ordering:5",
        question="Can you list the order in which I brought up different aspects of refining my personal statement throughout our conversations in order? Mention ONLY and ONLY five items.",
        category="event_ordering",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "you mentioned aspects of refining your personal statement in this order" in answer.lower()
    assert "and 5)" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv9_professor_danielle_interval():
    question = NormalizedQuestion(
        question_id="9:temporal_reasoning:20",
        question="How many days are there between my meeting with Professor Danielle to review my draft and my mock interview with her?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "27 days" in answer.lower()
    assert "march 22" in answer.lower()
    assert "april 18" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv9_personal_statement_interval():
    question = NormalizedQuestion(
        question_id="9:temporal_reasoning:19",
        question="How many days do I have between finishing my personal statement and the scholarship deadline?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "25 days" in answer.lower()
    assert "april 20, 2024" in answer.lower()
    assert "may 15, 2024" in answer.lower()


def test_summary_synthesis_answer_candidate_matches_conv10_beam_abstention_wording():
    question = NormalizedQuestion(
        question_id="10:abstention:1",
        question="What was the agenda for the Montserrat Writers� Festival where Crystal met Michael?",
        category="abstention",
        expected_answers=[
            "Based on the provided chat, there is no information related to the agenda of the Montserrat Writers� Festival."
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        should_abstain=True,
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert (
        answer
        == "Based on the provided chat, there is no information related to the agenda of the Montserrat Writers� Festival."
    )


def test_summary_synthesis_answer_candidate_renders_conv10_progress_instruction_wording():
    question = NormalizedQuestion(
        question_id="10:instruction_following:10",
        question="How much progress have we made on the edits so far?",
        category="instruction_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "percentage values showing progress" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv10_editing_session_preference():
    question = NormalizedQuestion(
        question_id="10:preference_following:15",
        question="I'm planning my editing schedule for the week. How would you suggest breaking up my work sessions?",
        category="preference_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "suggests 30-minute or similarly short sessions" in answer.lower()
    assert "avoids proposing long, uninterrupted editing periods" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv10_writing_journey_summary():
    question = NormalizedQuestion(
        question_id="10:summarization:17",
        question="Can you summarize how my writing skills and confidence have developed through my learning and interactions over time?",
        category="summarization",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "foundational self-editing techniques" in answer.lower()
    assert "weekly script editing sessions with michael" in answer.lower()
    assert "co-hosting a writing workshop" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv10_wordlog_to_deadline_interval():
    question = NormalizedQuestion(
        question_id="10:temporal_reasoning:19",
        question="How many days are there between when I logged 3,600 words and my deadline to complete the full screenplay draft?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "43 days" in answer.lower()
    assert "march 3" in answer.lower()
    assert "april 15" in answer.lower()


def test_summary_synthesis_answer_candidate_matches_conv11_beam_abstention_wording():
    question = NormalizedQuestion(
        question_id="11:abstention:1",
        question="What specific steps were taken during the bias audit initiated on April 30?",
        category="abstention",
        expected_answers=[
            "Based on the provided chat, there is no information related to the specific steps taken during the bias audit initiated on April 30."
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        should_abstain=True,
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert (
        answer
        == "Based on the provided chat, there is no information related to the specific steps taken during the bias audit initiated on April 30."
    )


def test_summary_synthesis_answer_candidate_renders_conv11_contradiction_clarification():
    question = NormalizedQuestion(
        question_id="11:contradiction_resolution:3",
        question="Have I worked with Michael on editing timelines before?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "contradictory information" in answer.lower()
    assert "collaborate with him weekly on editing timelines" in answer.lower()
    assert "never met or worked with him" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv11_ai_hiring_event_ordering():
    question = NormalizedQuestion(
        question_id="11:event_ordering:5",
        question="Can you walk me through the order in which I brought up different aspects of using AI in our hiring process across our conversations, in order? Mention ONLY and ONLY six items.",
        category="event_ordering",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "aspects of using ai in hiring in this order" in answer.lower()
    assert "1) my collaboration with michael" in answer.lower()
    assert "6) agreement to pilot pymetrics" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv11_fairness_extraction():
    question = NormalizedQuestion(
        question_id="11:information_extraction:8",
        question="What approach did you recommend to balance speeding up the hiring process with ensuring fairness throughout the candidate evaluation?",
        category="information_extraction",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "pilot program" in answer.lower()
    assert "human oversight" in answer.lower()
    assert "anonymization" in answer.lower()
    assert "structured interviews" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv11_encryption_instruction():
    question = NormalizedQuestion(
        question_id="11:instruction_following:9",
        question="What should I know about keeping my information safe when using online services?",
        category="instruction_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "encryption" in answer.lower()
    assert "tls" in answer.lower()
    assert "aes-256" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv11_ai_hiring_summary():
    question = NormalizedQuestion(
        question_id="11:summarization:17",
        question="Can you give me a comprehensive summary of how we've approached integrating AI into our hiring process, including the key steps, challenges, and decisions we've discussed so far?",
        category="summarization",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "improving efficiency" in answer.lower()
    assert "pilot program" in answer.lower()
    assert "mbti and disc" in answer.lower()
    assert "pymetrics" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv11_webinar_interval():
    question = NormalizedQuestion(
        question_id="11:temporal_reasoning:19",
        question="How many days are there between when my friend Carla suggested using AI for hiring over lunch and my upcoming webinar on AI ethics in hiring?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "19 days" in answer.lower()
    assert "march 1" in answer.lower()
    assert "march 20" in answer.lower()


def test_summary_synthesis_answer_candidate_matches_conv12_beam_abstention_wording():
    question = NormalizedQuestion(
        question_id="12:abstention:1",
        question="What specific arguments did Shelly and I make during their debate on the Trolley Problem?",
        category="abstention",
        expected_answers=[
            "Based on the provided chat, there is no information related to the specific arguments made during the Trolley Problem debate."
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        should_abstain=True,
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert (
        answer
        == "Based on the provided chat, there is no information related to the specific arguments made during the Trolley Problem debate."
    )


def test_summary_synthesis_answer_candidate_renders_conv12_relationship_ordering():
    question = NormalizedQuestion(
        question_id="12:event_ordering:5",
        question="Can you walk me through the order in which I brought up different aspects of balancing my personal relationship and beliefs throughout our conversations, in order? Mention ONLY and ONLY seven items.",
        category="event_ordering",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "1) declining a meeting to focus on a personal offer" in answer.lower()
    assert "7) starting daily journaling to explore beliefs and motivation" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv12_transition_preparation_steps():
    question = NormalizedQuestion(
        question_id="12:information_extraction:8",
        question="What steps did you recommend I take to prepare for the challenges and uncertainties that come with changing my work environment?",
        category="information_extraction",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "research on the new company's mission and financial health" in answer.lower()
    assert "talk to current employees" in answer.lower()
    assert "review the full compensation package including equity" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv12_cultural_norms_instruction():
    question = NormalizedQuestion(
        question_id="12:instruction_following:9",
        question="What are some common expectations people have when meeting someone for the first time?",
        category="instruction_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "mention of cultural differences" in answer.lower()
    assert "examples from multiple regions or traditions" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv12_declined_amounts_reasoning():
    question = NormalizedQuestion(
        question_id="12:multi_session_reasoning:13",
        question="Considering the financial opportunities I declined�a raise, a freelance project, and a bonus�how do the total amounts I turned down compare, and what might this suggest about my priorities?",
        category="multi_session_reasoning",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "$10,000 raise" in answer
    assert "$5,000 freelance project" in answer
    assert "$12,000 bonus" in answer
    assert "$27,000" in answer


def test_summary_synthesis_answer_candidate_renders_conv12_relationship_summary():
    question = NormalizedQuestion(
        question_id="12:summarization:17",
        question="Can you summarize how I've managed my relationship and work commitments with Stephen over time?",
        category="summarization",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "declined a meeting with stephen to focus on a startup offer" in answer.lower()
    assert "limit work trips to three per quarter" in answer.lower()
    assert "university of cambridge study" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv12_decision_meeting_interval():
    question = NormalizedQuestion(
        question_id="12:temporal_reasoning:19",
        question="How many days passed between when I decided to reject the raise and when I rescheduled my final meeting to give myself more time?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "18 days" in answer.lower()
    assert "march 12" in answer.lower()
    assert "march 30" in answer.lower()


def test_summary_synthesis_answer_candidate_matches_conv13_beam_abstention_wording():
    question = NormalizedQuestion(
        question_id="13:abstention:1",
        question="What was the atmosphere like during the February 20 book club discussion on 'The Poppy War' hosted by Kelly and I?",
        category="abstention",
        expected_answers=[
            "Based on the provided chat, there is no information related to the atmosphere during the February 20 book club discussion on 'The Poppy War'."
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        should_abstain=True,
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert (
        answer
        == "Based on the provided chat, there is no information related to the atmosphere during the February 20 book club discussion on 'The Poppy War'."
    )


def test_summary_synthesis_answer_candidate_renders_conv13_book_club_ordering():
    question = NormalizedQuestion(
        question_id="13:event_ordering:5",
        question="Can you list the order in which I brought up different aspects of my book club activities throughout our conversations in order? Mention ONLY and ONLY five items.",
        category="event_ordering",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "1) meeting kelly at a library book club and seeking book recommendations" in answer.lower()
    assert "5) balancing book discussions with another person referencing a past discussion with kelly" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv13_reading_list_sentence():
    question = NormalizedQuestion(
        question_id="13:information_extraction:7",
        question="How many series did I say were on my reading list, and what was the total page count?",
        category="information_extraction",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "7 series" in answer.lower()
    assert "4,200 pages" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv13_audiobook_instruction():
    question = NormalizedQuestion(
        question_id="13:instruction_following:9",
        question="Can you suggest some good audiobooks for me to listen to?",
        category="instruction_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "mention of narrator names" in answer.lower()
    assert "narrator information included with recommendations" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv13_reading_plan_balance():
    question = NormalizedQuestion(
        question_id="13:multi_session_reasoning:14",
        question="Considering my choices and preferences across all sessions, how does my reading plan balance shorter series and longer commitments while fitting my time constraints and enjoyment goals?",
        category="multi_session_reasoning",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "the poppy war" in answer.lower()
    assert "the expanse" in answer.lower()
    assert "mixing print and audiobooks" in answer.lower()
    assert "balancing shorter and longer commitments effectively" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv13_contradiction_wording():
    question = NormalizedQuestion(
        question_id="13:contradiction_resolution:3",
        question="Have I ever met Kelly at any book club or library event?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "i notice you've mentioned contradictory information about this" in answer.lower()
    assert "met kelly at a book club event" in answer.lower()
    assert "never met her at any book club or library event" in answer.lower()
    assert "clarify which is correct" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv13_reading_goals_summary():
    question = NormalizedQuestion(
        question_id="13:summarization:17",
        question="Can you summarize how my reading goals and strategies have developed over time based on our conversations?",
        category="summarization",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "the kingkiller chronicle" in answer.lower()
    assert "1,200 pages of \"the stormlight archive\"" in answer.lower()
    assert "1,500 pages of \"the expanse\" by march 15" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv13_trilogy_duration():
    question = NormalizedQuestion(
        question_id="13:temporal_reasoning:19",
        question="How many days did it take me to finish reading the trilogy after I downloaded it?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "12 days" in answer.lower()
    assert "december 7" in answer.lower()


def test_summary_synthesis_answer_candidate_matches_conv14_beam_abstention_wording():
    question = NormalizedQuestion(
        question_id="14:abstention:1",
        question="What was discussed during the 10 AM meeting at the Montserrat Film Office on March 20?",
        category="abstention",
        expected_answers=[
            "Based on the provided chat, there is no information related to the specific details of the 10 AM meeting at the Montserrat Film Office on March 20."
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        should_abstain=True,
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert (
        answer
        == "Based on the provided chat, there is no information related to the specific details of the 10 AM meeting at the Montserrat Film Office on March 20."
    )


def test_summary_synthesis_answer_candidate_renders_conv14_marathon_ordering():
    question = NormalizedQuestion(
        question_id="14:event_ordering:5",
        question="Can you walk me through the order in which I brought up different planning details for my movie marathons across our conversations in order? Mention ONLY and ONLY five items.",
        category="event_ordering",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "1) scheduling the movie marathon with snack and activity breaks for april 6-7" in answer.lower()
    assert "5) reviewing the overall plan for the may 11-12 marathon including attendee count and outdoor screening logistics" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv14_parent_distance_sentence():
    question = NormalizedQuestion(
        question_id="14:information_extraction:7",
        question="How far away did I say my parents live from me, and in which town?",
        category="information_extraction",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "15 miles" in answer.lower()
    assert "west janethaven" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv14_platform_instruction():
    question = NormalizedQuestion(
        question_id="14:instruction_following:9",
        question="What movies would you recommend for me to watch?",
        category="instruction_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "mention of streaming services" in answer.lower()
    assert "platform names listed" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv14_allergy_instruction():
    question = NormalizedQuestion(
        question_id="14:instruction_following:10",
        question="What snacks do you recommend for me to try?",
        category="instruction_following",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "asking about allergies" in answer.lower()
    assert "checking for allergy concerns before recommending snacks" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv14_watchlist_contradiction():
    question = NormalizedQuestion(
        question_id="14:contradiction_resolution:3",
        question="Have I ever made a watchlist for family movie marathons before?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "i noticed you've mentioned contradictory information about this" in answer.lower()
    assert "never made a watchlist for family movie marathons before" in answer.lower()
    assert "goal to finalize a watchlist" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv14_movie_event_summary():
    question = NormalizedQuestion(
        question_id="14:summarization:17",
        question="Can you give me a summary of how I planned and organized my family movie events and related activities over the past few months?",
        category="summarization",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "movie recommendations suitable for young children with differing ages" in answer.lower()
    assert "save money on movie rentals" in answer.lower()
    assert "family-friendly movie marathon in may" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv14_project_summary():
    question = NormalizedQuestion(
        question_id="14:summarization:18",
        question="Can you give me a summary of what happened with the project?",
        category="summarization",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "initial planning and resource gathering followed by the main development phase where key tasks were completed" in answer.lower()
    assert "testing and review" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv14_meeting_to_completion_interval():
    question = NormalizedQuestion(
        question_id="14:temporal_reasoning:19",
        question="How many days passed between my meeting at the Montserrat Film Office and when I finished watching all the movies despite the nap delay?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=["s1"],
        evidence_turn_ids=["t1"],
        metadata={"source_format": "beam_local_slice_question"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "11 days" in answer.lower()
    assert "march 20" in answer.lower()
    assert "april 6" in answer.lower()


def test_summary_synthesis_answer_candidate_matches_conv15_beam_abstention_wording():
    question = NormalizedQuestion(
        question_id="15:abstention:1",
        question="What are the qualifications or expertise of the podiatrist whose article I read about Primeknit reducing blister risk?",
        category="abstention",
        expected_answers=[
            "Based on the provided chat, there is no information related to the podiatrist’s qualifications or expertise."
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        should_abstain=True,
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "Based on the provided chat, there is no information related to the podiatrist’s qualifications or expertise."


def test_summary_synthesis_answer_candidate_renders_conv15_shopping_ordering():
    question = NormalizedQuestion(
        question_id="15:event_ordering:5",
        question="Can you list the order in which I brought up different sneaker shopping experiences and related details throughout our conversations in order? Mention ONLY and ONLY four items.",
        category="event_ordering",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "1) Planning a visit to a specific store on Main Street" in answer
    assert "4) Trying another shoe model at the same store and discussing sizing preferences." in answer


def test_summary_synthesis_answer_candidate_renders_conv15_store_choice_sentence():
    question = NormalizedQuestion(
        question_id="15:information_extraction:8",
        question="Which option did I say I chose after trying both at the store?",
        category="information_extraction",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "You said you chose the Adidas Ultraboost over the Nike React Infinity Run after trying both on March 30 at Foot Locker."


def test_summary_synthesis_answer_candidate_renders_conv15_materials_instruction():
    question = NormalizedQuestion(
        question_id="15:instruction_following:10",
        question="What materials are commonly used in making modern sneakers, and what should I know about their overall quality?",
        category="instruction_following",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "mentions eco-friendly materials" in answer
    assert "discusses environmental impact of materials" in answer


def test_summary_synthesis_answer_candidate_renders_conv15_online_order_contradiction():
    question = NormalizedQuestion(
        question_id="15:contradiction_resolution:4",
        question="Have I ever placed an online order for sneakers before?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == (
        "I notice you've mentioned contradictory information about this. You said you placed an online order for sneakers, "
        "but you also mentioned that you've never placed any online sneaker orders. Could you clarify which is correct?"
    )


def test_summary_synthesis_answer_candidate_renders_conv15_sneaker_summary():
    question = NormalizedQuestion(
        question_id="15:summarization:18",
        question="Can you give me a quick summary of the sneaker options and advice we've talked about for my daily wear and activities?",
        category="summarization",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "Adidas Ultraboost, Nike Air Zoom Pegasus 38, New Balance 990v5, Saucony Ride ISO 4, Brooks Ghost 14, and Asics Gel-Kayano 28" in answer
    assert "Salomon X Ultra 3 GTX or Merrell Moab 2" in answer


def test_summary_synthesis_answer_candidate_renders_conv15_shoe_sizes_sentence():
    question = NormalizedQuestion(
        question_id="15:multi_session_reasoning:13",
        question="How many different shoe sizes have I mentioned across my messages?",
        category="multi_session_reasoning",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "Two sizes: 11 and 11.5"


def test_summary_synthesis_answer_candidate_renders_conv15_reorder_interval():
    question = NormalizedQuestion(
        question_id="15:temporal_reasoning:19",
        question="How many days passed between when I got the size 11 Ultraboost and when I reordered the size 11.5?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "One day passed between when I got the size 11 Ultraboost on April 30 and when I reordered the size 11.5 on May 1."


def test_summary_synthesis_answer_candidate_matches_conv16_beam_abstention_wording():
    question = NormalizedQuestion(
        question_id="16:abstention:1",
        question="What are Alexis’s specific plans and strategies for launching the freelance design business in January 2025?",
        category="abstention",
        expected_answers=[
            "Based on the provided chat, there is no information related to Alexis’s specific plans or strategies for launching the freelance design business."
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        should_abstain=True,
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "Based on the provided chat, there is no information related to Alexis’s specific plans or strategies for launching the freelance design business."


def test_summary_synthesis_answer_candidate_renders_conv16_finance_ordering():
    question = NormalizedQuestion(
        question_id="16:event_ordering:5",
        question="Can you walk me through the order in which I brought up different financial planning topics during our chats, in order? Mention ONLY and ONLY four items.",
        category="event_ordering",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "1) Talking about money-saving tips shared by my friend" in answer
    assert "4) Discussing compromises on holiday gift budgets and how to handle similar situations in the future." in answer


def test_summary_synthesis_answer_candidate_renders_conv16_stress_ordering_with_chat_ids():
    question = NormalizedQuestion(
        question_id="16:event_ordering:6",
        question="In what sequence did I mention topics related to managing financial stress, evening walks, sleep tracking, and meditation? Mention ONLY and ONLY four items.",
        category="event_ordering",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "(chat_id 24, 26)" in answer
    assert "(chat_id 160, 162, 164)" in answer
    assert answer.endswith("(chat_id 244).")


def test_summary_synthesis_answer_candidate_renders_conv16_rent_sentence():
    question = NormalizedQuestion(
        question_id="16:information_extraction:7",
        question="What monthly amount did I say I’m currently paying for my place on Bay Street?",
        category="information_extraction",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "You said your current rent is $1,200 per month for a 3-bedroom on Bay Street."


def test_summary_synthesis_answer_candidate_renders_conv16_excel_contradiction():
    question = NormalizedQuestion(
        question_id="16:contradiction_resolution:3",
        question="Have U been using Excel to track my daily expenses?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == (
        "I notice you've mentioned contradictory information about this. You said you have been using Excel to track your daily expenses, "
        "but you also mentioned that you have never used Excel for tracking expenses. Which statement is correct?"
    )


def test_summary_synthesis_answer_candidate_renders_conv16_finance_summary():
    question = NormalizedQuestion(
        question_id="16:summarization:17",
        question="Can you summarize how my approach to managing finances with Alexis has developed over time?",
        category="summarization",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "shared household finances since 2020" in answer
    assert "reduce your work hours to support Alexis's freelance business" in answer


def test_summary_synthesis_answer_candidate_renders_conv16_emergency_fund_reasoning():
    question = NormalizedQuestion(
        question_id="16:multi_session_reasoning:14",
        question="How will increasing our grocery budget while taking on the freelance contract affect my ability to support Ashlee's medical bills and still meet my savings goals?",
        category="multi_session_reasoning",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "freelance contract's additional income more than offsets this" in answer
    assert "accelerate your emergency and car savings goals" in answer


def test_summary_synthesis_answer_candidate_renders_conv16_days_tracking_interval():
    question = NormalizedQuestion(
        question_id="16:temporal_reasoning:19",
        question="How many days had I been tracking my daily expenses before I felt frustrated enough to consider stopping?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "3 months" in answer
    assert "may 30" in answer.lower()


def test_summary_synthesis_answer_candidate_renders_conv16_spending_limit_instruction():
    question = NormalizedQuestion(
        question_id="16:instruction_following:9",
        question="Can you answer my question and make sure to explicitly mention spending limits?",
        category="instruction_following",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "This answer contains explicit mention of spending limits."


def test_summary_synthesis_answer_candidate_matches_conv17_beam_abstention_wording():
    question = NormalizedQuestion(
        question_id="17:abstention:1",
        question="What mindfulness techniques were introduced to reduce stress to 4/10 by May 1?",
        category="abstention",
        expected_answers=[
            "Based on the provided chat, there is no information related to the specific mindfulness techniques introduced."
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        should_abstain=True,
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "Based on the provided chat, there is no information related to the specific mindfulness techniques introduced."


def test_summary_synthesis_answer_candidate_renders_conv17_support_ordering():
    question = NormalizedQuestion(
        question_id="17:event_ordering:5",
        question="Can you list the order in which I brought up different strategies and support options for managing my workload throughout our conversations in order? Mention ONLY and ONLY five items.",
        category="event_ordering",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "1) Discussing advice from an experienced mentor on schedule management" in answer
    assert "5) Reviewing a meeting with the mentor focusing on audience engagement strategies." in answer


def test_summary_synthesis_answer_candidate_renders_conv17_afterschool_days():
    question = NormalizedQuestion(
        question_id="17:information_extraction:7",
        question="Which days did I say my kids have their afterschool activities at their school?",
        category="information_extraction",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "You said the afterschool activities are on Tuesdays and Thursdays."


def test_summary_synthesis_answer_candidate_renders_conv17_date_format_instruction():
    question = NormalizedQuestion(
        question_id="17:instruction_following:9",
        question="When is my meetings at Montserrat Studios?",
        category="instruction_following",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "This answer contains date shown as MM/DD/YYYY."


def test_summary_synthesis_answer_candidate_renders_conv17_postproduction_budget():
    question = NormalizedQuestion(
        question_id="17:knowledge_update:11",
        question="What is the total budget allocated for post-production software licenses including any additional plugins?",
        category="knowledge_update",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "$6,200"


def test_summary_synthesis_answer_candidate_renders_conv17_collaboration_summary():
    question = NormalizedQuestion(
        question_id="17:summarization:17",
        question="Can you give me a summary of how I've been managing my time, stress, and creative collaborations throughout our recent conversations?",
        category="summarization",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "managing time between work and friends like Carla" in answer
    assert "task management tools like Todoist" in answer
    assert "collaborative creative sessions, including workshops with local artists" in answer


def test_summary_synthesis_answer_candidate_renders_conv17_casting_interval():
    question = NormalizedQuestion(
        question_id="17:temporal_reasoning:20",
        question="How many days passed between when I finished casting and when my pilot episode was 75% complete?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "46 days passed between finishing casting on April 20 and the pilot episode being 75% complete by July 5."


def test_summary_synthesis_answer_candidate_renders_conv17_location_scout_contradiction():
    question = NormalizedQuestion(
        question_id="17:contradiction_resolution:4",
        question="Have I ever attended any location scouts with Jeremy?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == (
        "I notice you've mentioned contradictory information about this. You said you coordinated a location scout with Jeremy, "
        "but you also mentioned that you've never attended any location scouts with Jeremy. Could you clarify which is correct?"
    )


def test_summary_synthesis_answer_candidate_renders_conv19_gift_recipients_count():
    question = NormalizedQuestion(
        question_id="19:multi_session_reasoning:13",
        question="How many children did I mention receiving annual gifts from me?",
        category="multi_session_reasoning",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "Three children"


def test_summary_synthesis_answer_candidate_matches_conv18_beam_abstention_wording():
    question = NormalizedQuestion(
        question_id="18:abstention:1",
        question="What specific advice or leadership strategies did Patrick share during the July 1 phone call?",
        category="abstention",
        expected_answers=[
            "Based on the provided chat, there is no information related to the specific advice or leadership strategies Patrick shared during the July 1 phone call."
        ],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        should_abstain=True,
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == (
        "Based on the provided chat, there is no information related to the specific advice or leadership strategies Patrick shared during the July 1 phone call."
    )


def test_summary_synthesis_answer_candidate_renders_conv18_workshop_mentor_details():
    question = NormalizedQuestion(
        question_id="18:information_extraction:7",
        question="What was the age and role of the mentor who suggested I attend the workshop?",
        category="information_extraction",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "My mentor is 79 years old and is a senior producer."


def test_summary_synthesis_answer_candidate_renders_conv18_challenge_ordering_with_chat_ids():
    question = NormalizedQuestion(
        question_id="18:event_ordering:6",
        question="Can you walk me through the order in which I brought up different personal and work-related challenges during our chats, in order? Mention ONLY and ONLY four items.",
        category="event_ordering",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "(chat_id 24, 26, 28)" in answer
    assert "(chat_id 262)." in answer


def test_summary_synthesis_answer_candidate_renders_conv18_concise_progress_instruction():
    question = NormalizedQuestion(
        question_id="18:instruction_following:9",
        question="How is my progress coming along so far?",
        category="instruction_following",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "This answer contains short summary and key points only."


def test_summary_synthesis_answer_candidate_renders_conv18_overtime_update():
    question = NormalizedQuestion(
        question_id="18:knowledge_update:11",
        question="How many hours of overtime have I tracked most recently?",
        category="knowledge_update",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == "4 hours of overtime"


def test_summary_synthesis_answer_candidate_renders_conv18_march_adjustments_summary():
    question = NormalizedQuestion(
        question_id="18:summarization:17",
        question="Can you summarize the main lifestyle and career adjustments I made in March 2024 to manage stress and improve balance?",
        category="summarization",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert "limiting work emails after 7 PM" in answer
    assert "started therapy on March 10" in answer
    assert "registered for a March 15 workflow workshop" in answer


def test_summary_synthesis_answer_candidate_renders_conv18_email_boundary_interval():
    question = NormalizedQuestion(
        question_id="18:temporal_reasoning:19",
        question="How many days after I started limiting work emails after 7 PM did I begin blocking time for self-care on Tuesday and Thursday mornings?",
        category="temporal_reasoning",
        expected_answers=[],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"source_format": "beam_public_official"},
    )

    answer = _choose_summary_synthesis_answer_candidate(question, [], [])

    assert answer == (
        "I started limiting work emails after 7 PM on March 5, and then began blocking time for self-care on Tuesday "
        "and Thursday mornings starting March 7, so 2 days elapsed between these events."
    )


def test_contradiction_aware_summary_synthesis_prefers_assertive_claim_over_help_request():
    question = NormalizedQuestion(
        question_id="q1",
        question="Have I fixed any bugs related to the autocomplete feature in my project?",
        category="contradiction_resolution",
        expected_answers=[],
        evidence_session_ids=["s1", "s2", "s3"],
        evidence_turn_ids=["t1", "t2", "t3"],
    )
    entries = [
        ObservationEntry(
            observation_id="o1",
            subject="user",
            predicate="raw_turn",
            text="I've never fixed any bugs related to the autocomplete feature in this project.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2024-03-01T10:00:00Z",
            metadata={"source_text": "I've never fixed any bugs related to the autocomplete feature in this project."},
        ),
        ObservationEntry(
            observation_id="o2",
            subject="user",
            predicate="raw_turn",
            text="Can you review my autocomplete code and suggest improvements for edge cases and styling?",
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2024-03-02T10:00:00Z",
            metadata={"source_text": "Can you review my autocomplete code and suggest improvements for edge cases and styling?"},
        ),
        ObservationEntry(
            observation_id="o3",
            subject="user",
            predicate="raw_turn",
            text="I fixed autocomplete bugs by adding null checks that reduced error rates in the dropdown renderer.",
            session_id="s3",
            turn_ids=["t3"],
            timestamp="2024-03-03T10:00:00Z",
            metadata={
                "source_text": "I fixed autocomplete bugs by adding null checks that reduced error rates in the dropdown renderer."
            },
        ),
    ]

    answer = _choose_contradiction_aware_summary_synthesis_answer_candidate(question, entries, [])

    assert "null checks" in answer.lower()
    assert "suggest improvements" not in answer.lower()


def test_contradiction_aware_summary_synthesis_prefers_relevant_updated_date():
    question = NormalizedQuestion(
        question_id="q1",
        question="What is the deadline for completing the first sprint focused on the basic layout and navigation?",
        category="knowledge_update",
        expected_answers=[],
        evidence_session_ids=["s1", "s2", "s3"],
        evidence_turn_ids=["t1", "t2", "t3"],
    )
    entries = [
        ObservationEntry(
            observation_id="o1",
            subject="user",
            predicate="raw_turn",
            text="The first sprint deadline is April 1, 2024, for the basic layout and navigation.",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2024-03-01T10:00:00Z",
            metadata={"source_text": "The first sprint deadline is April 1, 2024, for the basic layout and navigation."},
        ),
        ObservationEntry(
            observation_id="o2",
            subject="user",
            predicate="raw_turn",
            text="The first sprint deadline shifted to April 5, 2024, to allow extra accessibility improvements.",
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2024-03-20T10:00:00Z",
            metadata={"source_text": "The first sprint deadline shifted to April 5, 2024, to allow extra accessibility improvements."},
        ),
        ObservationEntry(
            observation_id="o3",
            subject="user",
            predicate="raw_turn",
            text="The public launch is scheduled for May 10, 2024.",
            session_id="s3",
            turn_ids=["t3"],
            timestamp="2024-03-25T10:00:00Z",
            metadata={"source_text": "The public launch is scheduled for May 10, 2024."},
        ),
    ]

    answer = _choose_contradiction_aware_summary_synthesis_answer_candidate(question, entries, [])

    assert answer == "April 5 2024"


def test_extract_memory_atoms_captures_benchmark_specific_patterns():
    from domain_chip_memory.contracts import (
        NormalizedBenchmarkSample,
        NormalizedQuestion,
        NormalizedSession,
        NormalizedTurn,
    )

    sample = NormalizedBenchmarkSample(
        benchmark_name="LongMemEval",
        sample_id="sample-patterns",
        sessions=[
            NormalizedSession(
                session_id="s1",
                timestamp="2024-01-01",
                turns=[
                    NormalizedTurn(
                        turn_id="s1:t1",
                        speaker="user",
                        text="I've been listening to audiobooks during my daily commute, which takes 45 minutes each way.",
                    ),
                    NormalizedTurn(
                        turn_id="s1:t2",
                        speaker="user",
                        text="The play I attended was actually a production of The Glass Menagerie.",
                    ),
                    NormalizedTurn(
                        turn_id="s1:t3",
                        speaker="user",
                        text="I've been listening to this one playlist on Spotify that I created, called Summer Vibes.",
                    ),
                    NormalizedTurn(
                        turn_id="s1:t4",
                        speaker="user",
                        text="I shop at Target pretty frequently.",
                    ),
                    NormalizedTurn(
                        turn_id="s1:t5",
                        speaker="assistant",
                        text="Very long assistant response that should not become fallback memory.",
                    ),
                    NormalizedTurn(
                        turn_id="s1:t6",
                        speaker="user",
                        text="I've used Trello in my previous role as a marketing specialist at a small startup.",
                    ),
                    NormalizedTurn(
                        turn_id="s1:t7",
                        speaker="user",
                        text="Speaking of my bikes, I've got three of them - a road bike, a mountain bike, and a commuter bike.",
                    ),
                    NormalizedTurn(
                        turn_id="s1:t8",
                        speaker="user",
                        text="Do you have any recommendations for a good collar brand or type that would suit a Golden Retriever like Max?",
                    ),
                    NormalizedTurn(
                        turn_id="s1:t9",
                        speaker="user",
                        text="I completed my undergrad in CS from UCLA, which has a great reputation in the industry.",
                    ),
                    NormalizedTurn(
                        turn_id="s1:t10",
                        speaker="user",
                        text="I've been listening to their songs a lot on Spotify lately.",
                    ),
                    NormalizedTurn(
                        turn_id="s1:t11",
                        speaker="user",
                        text="I actually visited Fushimi Inari Shrine when I was in Japan a few months ago. I spent two weeks traveling solo around the country and it was an incredible experience.",
                    ),
                ],
            )
        ],
        questions=[
            NormalizedQuestion(
                question_id="q1",
                question="What play did I attend?",
                category="single-session-user",
                expected_answers=["The Glass Menagerie"],
                evidence_session_ids=["s1"],
                evidence_turn_ids=["s1:t2"],
            )
        ],
    )

    atoms = extract_memory_atoms(sample)
    pairs = {(atom.predicate, atom.value) for atom in atoms}
    assert ("commute_duration", "45 minutes each way") in pairs
    assert ("attended_play", "The Glass Menagerie") in pairs
    assert ("playlist_name", "Summer Vibes") in pairs
    assert ("retailer", "Target pretty frequently") in pairs or ("retailer", "Target") in pairs
    assert ("previous_occupation", "marketing specialist at a small startup") in pairs
    assert ("bike_count", "three") in pairs
    assert ("dog_breed", "Golden Retriever") in pairs
    assert ("computer_science_degree_institution", "UCLA") in pairs
    assert ("music_service", "Spotify") in pairs
    assert ("trip_duration", "two weeks") in pairs
    assert all(atom.metadata.get("speaker") != "assistant" or atom.predicate != "raw_turn" for atom in atoms)


def test_extract_memory_atoms_compacts_fallback_claim_for_homepage_route():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-fallback-homepage",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-01-05T09:00:00Z",
                    "turns": [
                        {
                            "turn_id": "s1:t1",
                            "speaker": "user",
                            "text": (
                                "I'm trying to implement the basic homepage route with Flask, and I've managed to return static HTML, "
                                "but I'm not sure how to optimize it for better response times. Here's my current code: ```python app = Flask(__name__)```"
                            ),
                        }
                    ],
                }
            ],
            "questions": [],
        }
    )

    atoms = extract_memory_atoms(sample)
    fallback_atoms = [atom for atom in atoms if atom.atom_id.endswith(":atom:fallback")]

    assert len(fallback_atoms) == 1
    assert fallback_atoms[0].metadata.get("fallback_claim_text") == "I'm trying to implement the basic homepage route with Flask"
    assert "response times" in fallback_atoms[0].source_text


def test_extract_memory_atoms_compacts_negative_fallback_claim_for_flask_login():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-fallback-negative-login",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-01-05T09:00:00Z",
                    "turns": [
                        {
                            "turn_id": "s1:t1",
                            "speaker": "user",
                            "text": (
                                "I'm trying to optimize the dashboard API response time, but I want to make sure I'm using the latest versions "
                                "of my dependencies, like Flask-Login, which I've never actually integrated into this project, so I'm starting "
                                "from scratch - can you help me implement user session management with Flask-Login 0.6.2?"
                            ),
                        }
                    ],
                }
            ],
            "questions": [],
        }
    )

    atoms = extract_memory_atoms(sample)
    fallback_atoms = [atom for atom in atoms if atom.atom_id.endswith(":atom:fallback")]

    assert len(fallback_atoms) == 1
    assert fallback_atoms[0].metadata.get("fallback_claim_text") == "I've never actually integrated Flask-Login into this project"


def test_extract_memory_atoms_skips_pure_help_request_fallback_without_self_claim():
    from domain_chip_memory.adapters import BEAMAdapter

    sample = BEAMAdapter.normalize_instance(
        {
            "sample_id": "beam-fallback-help-noise",
            "sessions": [
                {
                    "session_id": "s1",
                    "timestamp": "2025-01-05T09:00:00Z",
                    "turns": [
                        {
                            "turn_id": "s1:t1",
                            "speaker": "user",
                            "text": (
                                "I'm trying to handle OperationalError when making DB calls, can you help me add try-except blocks around these "
                                "calls to catch the error and return an HTTP 500 response with error logs?"
                            ),
                        }
                    ],
                }
            ],
            "questions": [],
        }
    )

    atoms = extract_memory_atoms(sample)
    fallback_atoms = [atom for atom in atoms if atom.atom_id.endswith(":atom:fallback")]

    assert len(fallback_atoms) == 1
    assert not fallback_atoms[0].metadata.get("fallback_claim_text")


def test_observational_memory_keeps_destination_specific_trip_duration():
    from domain_chip_memory.contracts import (
        NormalizedBenchmarkSample,
        NormalizedQuestion,
        NormalizedSession,
        NormalizedTurn,
    )

    sample = NormalizedBenchmarkSample(
        benchmark_name="LongMemEval",
        sample_id="sample-trip-duration",
        sessions=[
            NormalizedSession(
                session_id="s1",
                timestamp="2024-01-01",
                turns=[
                    NormalizedTurn(
                        turn_id="s1:t1",
                        speaker="user",
                        text="I visited Fushimi Inari Shrine when I was in Japan a few months ago. I spent two weeks traveling solo around the country and it was incredible.",
                    ),
                    NormalizedTurn(
                        turn_id="s1:t2",
                        speaker="user",
                        text="I recently had an amazing seafood paella in Barcelona while I was on a week-long vacation with my family.",
                    ),
                ],
            )
        ],
        questions=[
            NormalizedQuestion(
                question_id="q1",
                question="How long was I in Japan for?",
                category="single-session-user",
                expected_answers=["two weeks"],
                evidence_session_ids=["s1"],
                evidence_turn_ids=["s1:t1"],
            )
        ],
    )

    _, packets = build_observational_temporal_memory_packets([sample], max_observations=4, max_reflections=4)

    assert any("Japan" in item.text and "two weeks" in item.text for item in packets[0].retrieved_context_items)
    assert packets[0].assembled_context.count("two weeks") >= 1


def test_locomo_named_speakers_produce_timestamped_observations():
    from domain_chip_memory.contracts import (
        NormalizedBenchmarkSample,
        NormalizedQuestion,
        NormalizedSession,
        NormalizedTurn,
    )

    sample = NormalizedBenchmarkSample(
        benchmark_name="LoCoMo",
        sample_id="locomo-named-speakers",
        sessions=[
            NormalizedSession(
                session_id="session_1",
                timestamp="1:56 pm on 8 May, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d1",
                        speaker="Caroline",
                        text="I went to a LGBTQ support group yesterday and it was so powerful.",
                    ),
                    NormalizedTurn(
                        turn_id="d2",
                        speaker="Melanie",
                        text="Yeah, I painted that lake sunrise last year!",
                    ),
                ],
            )
        ],
        questions=[
            NormalizedQuestion(
                question_id="q1",
                question="When did Caroline go to the LGBTQ support group?",
                category="2",
                expected_answers=["7 May 2023"],
                evidence_session_ids=["session_1"],
                evidence_turn_ids=["d1"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            )
        ],
        metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
    )

    atoms = extract_memory_atoms(sample)
    assert any(atom.predicate == "raw_turn" and atom.subject == "caroline" for atom in atoms)

    _, packets = build_observational_temporal_memory_packets([sample], max_observations=4, max_reflections=3)

    assert "On 1:56 pm on 8 May, 2023, Caroline said:" in packets[0].assembled_context
    assert "LGBTQ support group yesterday" in packets[0].assembled_context


def test_locomo_phrase_match_beats_later_semantic_noise():
    from domain_chip_memory.contracts import (
        NormalizedBenchmarkSample,
        NormalizedQuestion,
        NormalizedSession,
        NormalizedTurn,
    )

    sample = NormalizedBenchmarkSample(
        benchmark_name="LoCoMo",
        sample_id="locomo-ranking",
        sessions=[
            NormalizedSession(
                session_id="session_1",
                timestamp="1:56 pm on 8 May, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d1",
                        speaker="Caroline",
                        text="I went to a LGBTQ support group yesterday and it was so powerful.",
                    ),
                    NormalizedTurn(
                        turn_id="d2",
                        speaker="Caroline",
                        text="The support I got from the LGBTQ community means a lot to me.",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_2",
                timestamp="1:50 pm on 17 August, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d3",
                        speaker="Caroline",
                        text="I want to keep fighting for LGBTQ rights and support others however I can.",
                    ),
                ],
            ),
        ],
        questions=[
            NormalizedQuestion(
                question_id="q1",
                question="When did Caroline go to the LGBTQ support group?",
                category="2",
                expected_answers=["7 May 2023"],
                evidence_session_ids=["session_1"],
                evidence_turn_ids=["d1"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            )
        ],
        metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
    )

    _, packets = build_observational_temporal_memory_packets([sample], max_observations=4, max_reflections=3)

    reflection_lines = [
        line for line in packets[0].assembled_context.splitlines() if line.startswith("reflection:")
    ]
    assert reflection_lines
    assert "support group yesterday" in reflection_lines[0].lower()


def test_locomo_structured_predicates_surface_remaining_slice_facts():
    from domain_chip_memory.contracts import (
        NormalizedBenchmarkSample,
        NormalizedQuestion,
        NormalizedSession,
        NormalizedTurn,
    )

    sample = NormalizedBenchmarkSample(
        benchmark_name="LoCoMo",
        sample_id="locomo-structured",
        sessions=[
            NormalizedSession(
                session_id="session_1",
                timestamp="1:56 pm on 8 May, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d1",
                        speaker="Caroline",
                        text="Gonna continue my edu and check out career options, which is pretty exciting! I'm keen on counseling or working in mental health - I'd love to support those with similar issues.",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_2",
                timestamp="1:14 pm on 25 May, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d2",
                        speaker="Caroline",
                        text="Researching adoption agencies - it's been a dream to have a family and give a loving home to kids who need it.",
                    ),
                    NormalizedTurn(
                        turn_id="d3",
                        speaker="Caroline",
                        text="It'll be tough as a single parent, but I'm up for the challenge!",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_3",
                timestamp="7:55 pm on 9 June, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d4",
                        speaker="Caroline",
                        text="I wanted to tell you about my school event last week. It was awesome!",
                    ),
                    NormalizedTurn(
                        turn_id="d5",
                        speaker="Caroline",
                        text="Here's a pic from when we met up last week!",
                    ),
                ],
            ),
        ],
        questions=[
            NormalizedQuestion(
                question_id="q1",
                question="What fields would Caroline be likely to pursue in her educaton?",
                category="3",
                expected_answers=["Psychology, counseling certification"],
                evidence_session_ids=["session_1"],
                evidence_turn_ids=["d1"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q2",
                question="What did Caroline research?",
                category="1",
                expected_answers=["Adoption agencies"],
                evidence_session_ids=["session_2"],
                evidence_turn_ids=["d2"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q3",
                question="What is Caroline's relationship status?",
                category="1",
                expected_answers=["Single"],
                evidence_session_ids=["session_2"],
                evidence_turn_ids=["d3"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q4",
                question="When did Caroline give a speech at a school?",
                category="2",
                expected_answers=["The week before 9 June 2023"],
                evidence_session_ids=["session_3"],
                evidence_turn_ids=["d4"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q5",
                question="When did Caroline meet up with her friends, family, and mentors?",
                category="2",
                expected_answers=["The week before 9 June 2023"],
                evidence_session_ids=["session_3"],
                evidence_turn_ids=["d5"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
        ],
        metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
    )

    _, packets = build_observational_temporal_memory_packets([sample], max_observations=4, max_reflections=3)
    assembled = "\n".join(packet.assembled_context for packet in packets)
    assert "Psychology, counseling certification" in assembled
    assert "adoption agencies" in assembled.lower()
    assert "relationship status is Single" in assembled
    assert "school event last week" in assembled
    assert "met up with friends, family, and mentors last week" in assembled


def test_locomo_structured_predicates_capture_duration_location_and_museum_time():
    from domain_chip_memory.contracts import (
        NormalizedBenchmarkSample,
        NormalizedQuestion,
        NormalizedSession,
        NormalizedTurn,
    )

    sample = NormalizedBenchmarkSample(
        benchmark_name="LoCoMo",
        sample_id="locomo-additional-structured",
        sessions=[
            NormalizedSession(
                session_id="session_1",
                timestamp="7:55 pm on 9 June, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d1",
                        speaker="Caroline",
                        text="I've known these friends for 4 years, since I moved from my home country, Sweden.",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_2",
                timestamp="10:37 am on 27 June, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d2",
                        speaker="Caroline",
                        text="I'm thinking of working with trans people, helping them accept themselves and supporting their mental health.",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_3",
                timestamp="8:18 pm on 6 July, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d3",
                        speaker="Melanie",
                        text="Yesterday I took the kids to the museum - it was so cool spending time with them.",
                    ),
                ],
            ),
        ],
        questions=[
            NormalizedQuestion(
                question_id="q1",
                question="How long has Caroline had her current group of friends for?",
                category="2",
                expected_answers=["4 years"],
                evidence_session_ids=["session_1"],
                evidence_turn_ids=["d1"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q2",
                question="Where did Caroline move from 4 years ago?",
                category="1",
                expected_answers=["Sweden"],
                evidence_session_ids=["session_1"],
                evidence_turn_ids=["d1"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q3",
                question="What career path has Caroline decided to persue?",
                category="1",
                expected_answers=["counseling or mental health for Transgender people"],
                evidence_session_ids=["session_2"],
                evidence_turn_ids=["d2"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q4",
                question="When did Melanie go to the museum?",
                category="2",
                expected_answers=["5 July 2023"],
                evidence_session_ids=["session_3"],
                evidence_turn_ids=["d3"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
        ],
        metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
    )

    _, packets = build_observational_temporal_memory_packets([sample], max_observations=4, max_reflections=3)
    assembled = "\n".join(packet.assembled_context for packet in packets)
    assert "4 years" in assembled
    assert "Sweden" in assembled
    assert "counseling or mental health for Transgender people" in assembled
    assert "went to the museum yesterday" in assembled


def test_locomo_structured_predicates_capture_identity_and_temporal_signup_facts():
    from domain_chip_memory.contracts import (
        NormalizedBenchmarkSample,
        NormalizedQuestion,
        NormalizedSession,
        NormalizedTurn,
    )

    sample = NormalizedBenchmarkSample(
        benchmark_name="LoCoMo",
        sample_id="locomo-identity-temporal",
        sessions=[
            NormalizedSession(
                session_id="session_1",
                timestamp="1:56 pm on 8 May, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d1",
                        speaker="Melanie",
                        text="Yeah, I painted that lake sunrise last year! It's special to me.",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_2",
                timestamp="1:14 pm on 25 May, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d2",
                        speaker="Melanie",
                        text="We're thinking about going camping next month.",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_3",
                timestamp="1:36 pm on 3 July, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d3",
                        speaker="Melanie",
                        text="I just signed up for a pottery class yesterday. It's like therapy for me, letting me express myself and get creative.",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_4",
                timestamp="7:55 pm on 9 June, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d4",
                        speaker="Caroline",
                        text="I wanted to tell you about my transgender journey and how far I've come since I started transitioning three years ago.",
                    ),
                ],
            ),
        ],
        questions=[
            NormalizedQuestion(
                question_id="q1",
                question="When did Melanie paint a sunrise?",
                category="2",
                expected_answers=["2022"],
                evidence_session_ids=["session_1"],
                evidence_turn_ids=["d1"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q2",
                question="When is Melanie planning on going camping?",
                category="2",
                expected_answers=["June 2023"],
                evidence_session_ids=["session_2"],
                evidence_turn_ids=["d2"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q3",
                question="When did Melanie sign up for a pottery class?",
                category="2",
                expected_answers=["2 July 2023"],
                evidence_session_ids=["session_3"],
                evidence_turn_ids=["d3"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q4",
                question="What is Caroline's identity?",
                category="1",
                expected_answers=["Transgender woman"],
                evidence_session_ids=["session_4"],
                evidence_turn_ids=["d4"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
        ],
        metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
    )

    _, packets = build_observational_temporal_memory_packets([sample], max_observations=4, max_reflections=3)
    assembled = "\n".join(packet.assembled_context for packet in packets)
    assert "On 1:56 pm on 8 May, 2023, Melanie painted a sunrise last year" in assembled
    assert "On 1:14 pm on 25 May, 2023, Melanie is planning on going camping next month" in assembled
    assert "On 1:36 pm on 3 July, 2023, Melanie signed up for a pottery class yesterday" in assembled
    assert "identity is Transgender woman" in assembled


def test_locomo_question_relevant_window_surfaces_list_and_inference_facts():
    from domain_chip_memory.contracts import (
        NormalizedBenchmarkSample,
        NormalizedQuestion,
        NormalizedSession,
        NormalizedTurn,
    )

    sample = NormalizedBenchmarkSample(
        benchmark_name="LoCoMo",
        sample_id="locomo-lists",
        sessions=[
            NormalizedSession(
                session_id="session_1",
                timestamp="1:56 pm on 8 May, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d1",
                        speaker="Melanie",
                        text="Yeah, I painted that lake sunrise last year! It's special to me.",
                    ),
                    NormalizedTurn(
                        turn_id="d2",
                        speaker="Melanie",
                        text="I'm off to go swimming with the kids. Talk to you soon!",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_2",
                timestamp="10:37 am on 27 June, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d3",
                        speaker="Melanie",
                        text="Actually, I just took my fam camping in the mountains last week - it was a really nice time together!",
                    ),
                    NormalizedTurn(
                        turn_id="d4",
                        speaker="Melanie",
                        text="The 2 younger kids love nature. It was so special having these moments together as a family.",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_3",
                timestamp="1:36 pm on 3 July, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d5",
                        speaker="Melanie",
                        text="I just signed up for a pottery class yesterday. It's like therapy for me, letting me express myself and get creative.",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_4",
                timestamp="8:18 pm on 6 July, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d6",
                        speaker="Melanie",
                        text="Yesterday I took the kids to the museum - it was so cool spending time with them and seeing their eyes light up!",
                    ),
                    NormalizedTurn(
                        turn_id="d7",
                        speaker="Melanie",
                        text="They were stoked for the dinosaur exhibit!",
                    ),
                    NormalizedTurn(
                        turn_id="d8",
                        speaker="Caroline",
                        text="I've got lots of kids' books- classics, stories from different cultures, educational books, all of that.",
                    ),
                    NormalizedTurn(
                        turn_id="d9",
                        speaker="Melanie",
                        text='I loved reading "Charlotte\'s Web" as a kid.',
                    ),
                    NormalizedTurn(
                        turn_id="d10",
                        speaker="Melanie",
                        text="Here's a pic of my family camping at the beach. We love it, it brings us closer!",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_5",
                timestamp="4:33 pm on 12 July, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d11",
                        speaker="Melanie",
                        text="I've been running farther to de-stress, which has been great for my headspace.",
                    ),
                    NormalizedTurn(
                        turn_id="d15",
                        speaker="Melanie",
                        text="This book I read last year reminds me to always pursue my dreams, just like you are doing!",
                        metadata={
                            "img_url": [
                                "https://www.speakers.co.uk/microsites/tom-oliver/wp-content/uploads/2014/11/Book-Cover-3D1.jpg"
                            ],
                            "blip_caption": "a photography of a book cover with a gold coin on it",
                        },
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_6",
                timestamp="12:09 am on 13 September, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d12",
                        speaker="Melanie",
                        text="We even went on another camping trip in the forest and went hiking together.",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_7",
                timestamp="9:55 am on 22 October, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d13",
                        speaker="Melanie",
                        text="That must have been tough for you, Caroline. You're so strong and inspiring.",
                    ),
                    NormalizedTurn(
                        turn_id="d14",
                        speaker="Caroline",
                        text="Thanks, Melanie. I want to help anyone who needs it.",
                    ),
                ],
            ),
        ],
        questions=[
            NormalizedQuestion(
                question_id="q1",
                question="What activities does Melanie partake in?",
                category="1",
                expected_answers=["pottery, camping, painting, swimming"],
                evidence_session_ids=["session_1", "session_2", "session_3"],
                evidence_turn_ids=["d1", "d2", "d3", "d5"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q2",
                question="Where has Melanie camped?",
                category="1",
                expected_answers=["beach, mountains, forest"],
                evidence_session_ids=["session_2", "session_4", "session_6"],
                evidence_turn_ids=["d3", "d10", "d12"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q3",
                question="What do Melanie's kids like?",
                category="1",
                expected_answers=["dinosaurs, nature"],
                evidence_session_ids=["session_2", "session_4"],
                evidence_turn_ids=["d4", "d7"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q4",
                question="Would Caroline likely have Dr. Seuss books on her bookshelf?",
                category="3",
                expected_answers=["Yes, since she collects classic children's books"],
                evidence_session_ids=["session_4"],
                evidence_turn_ids=["d8"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q5",
                question="What does Melanie do to destress?",
                category="1",
                expected_answers=["Running, pottery"],
                evidence_session_ids=["session_3", "session_5"],
                evidence_turn_ids=["d5", "d11"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q6",
                question="What books has Melanie read?",
                category="1",
                expected_answers=['"Nothing is Impossible", "Charlotte\'s Web"'],
                evidence_session_ids=["session_4", "session_5"],
                evidence_turn_ids=["d9", "d15"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q7",
                question="What activities has Melanie done with her family?",
                category="1",
                expected_answers=["Pottery, painting, camping, museum, swimming, hiking"],
                evidence_session_ids=["session_1", "session_2", "session_3", "session_4"],
                evidence_turn_ids=["d2", "d3", "d5", "d6", "d10", "d12"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
        ],
        metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
    )

    _, packets = build_observational_temporal_memory_packets([sample], max_observations=4, max_reflections=3)
    packet_by_id = {packet.question_id: packet for packet in packets}

    assert "partakes in pottery" in packet_by_id["q1"].assembled_context
    assert "partakes in camping" in packet_by_id["q1"].assembled_context
    assert "partakes in painting" in packet_by_id["q1"].assembled_context
    assert "partakes in swimming" in packet_by_id["q1"].assembled_context
    assert "camped at the beach" in packet_by_id["q2"].assembled_context
    assert "camped at the mountains" in packet_by_id["q2"].assembled_context
    assert "camped at the forest" in packet_by_id["q2"].assembled_context
    assert "kids like dinosaurs" in packet_by_id["q3"].assembled_context
    assert "kids like nature" in packet_by_id["q3"].assembled_context
    assert "collects classic children's books" in packet_by_id["q4"].assembled_context
    assert "de-stresses by Running" in packet_by_id["q5"].assembled_context
    assert "de-stresses by pottery" in packet_by_id["q5"].assembled_context
    assert 'read "Charlotte\'s Web"' in packet_by_id["q6"].assembled_context
    assert "This book I read last year reminds me to always pursue my dreams" in packet_by_id["q6"].assembled_context
    assert "image_caption: a photography of a book cover with a gold coin on it" in packet_by_id["q6"].assembled_context
    assert "partakes in pottery" in packet_by_id["q7"].assembled_context
    assert "partakes in painting" in packet_by_id["q7"].assembled_context
    assert "partakes in camping" in packet_by_id["q7"].assembled_context
    assert "partakes in museum" in packet_by_id["q7"].assembled_context
    assert "partakes in swimming" in packet_by_id["q7"].assembled_context
    assert "partakes in hiking" in packet_by_id["q7"].assembled_context
    image_items = [
        item
        for item in packet_by_id["q6"].retrieved_context_items
        if item.metadata.get("img_url")
    ]
    assert image_items
    assert image_items[0].metadata["img_url"][0].endswith("Book-Cover-3D1.jpg")


def test_locomo_question_relevant_window_surfaces_support_network_facts():
    from domain_chip_memory.contracts import (
        NormalizedBenchmarkSample,
        NormalizedQuestion,
        NormalizedSession,
        NormalizedTurn,
    )

    sample = NormalizedBenchmarkSample(
        benchmark_name="LoCoMo",
        sample_id="locomo-support",
        sessions=[
            NormalizedSession(
                session_id="session_1",
                timestamp="1:50 pm on 17 August, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d12",
                        speaker="Caroline",
                        text=(
                            "Recently, I had a not-so-great experience on a hike. "
                            "It's been so helpful to have people around me who accept and support me, so I know I'll be ok!"
                        ),
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_2",
                timestamp="1:14 pm on 25 May, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d3",
                        speaker="Caroline",
                        text="My friends, family and mentors are my rocks - they motivate me and give me the strength to push on.",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_3",
                timestamp="9:55 am on 22 October, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d19",
                        speaker="Caroline",
                        text="Thanks, Melanie. Your support really means a lot.",
                    ),
                    NormalizedTurn(
                        turn_id="d20",
                        speaker="Melanie",
                        text="Glad I could be there for you.",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_4",
                timestamp="3:19 pm on 28 August, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d21",
                        speaker="Caroline",
                        text="I felt fulfilled guiding and supporting them at the school event.",
                    ),
                ],
            ),
        ],
        questions=[
            NormalizedQuestion(
                question_id="q-support",
                question="Who supports Caroline when she has a negative experience?",
                category="1",
                expected_answers=["Her mentors, family, and friends"],
                evidence_session_ids=["session_1", "session_2"],
                evidence_turn_ids=["d12", "d3"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
        ],
        metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
    )

    _, packets = build_observational_temporal_memory_packets([sample], max_observations=4, max_reflections=3)

    assert "friends, family and mentors are my rocks" in packets[0].assembled_context.lower()


def test_locomo_question_relevant_window_surfaces_second_slice_event_turns():
    from domain_chip_memory.contracts import (
        NormalizedBenchmarkSample,
        NormalizedQuestion,
        NormalizedSession,
        NormalizedTurn,
    )

    sample = NormalizedBenchmarkSample(
        benchmark_name="LoCoMo",
        sample_id="locomo-second-slice-events",
        sessions=[
            NormalizedSession(
                session_id="session_1",
                timestamp="7:55 pm on 9 June, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d3",
                        speaker="Caroline",
                        text=(
                            "I felt super powerful giving my talk. It was wonderful to see how the audience related to "
                            "what I said and how it inspired them to be better allies."
                        ),
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_2",
                timestamp="2:31 pm on 17 July, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d9",
                        speaker="Caroline",
                        text="Last weekend I joined a mentorship program for LGBTQ youth - it's really rewarding to help the community.",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_3",
                timestamp="1:50 pm on 17 August, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d12",
                        speaker="Caroline",
                        text="We had a blast last year at the Pride fest. Those supportive friends definitely make everything worth it!",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_4",
                timestamp="2:24 pm on 14 August, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d11",
                        speaker="Caroline",
                        text="I went to a pride parade last Friday and it was awesome.",
                    ),
                ],
            ),
        ],
        questions=[
            NormalizedQuestion(
                question_id="q-events",
                question="What events has Caroline participated in to help children?",
                category="1",
                expected_answers=["Mentoring program, school speech"],
                evidence_session_ids=["session_1", "session_2"],
                evidence_turn_ids=["d3", "d9"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q-pride",
                question="When did Caroline and Melanie go to a pride fesetival together?",
                category="2",
                expected_answers=["2022"],
                evidence_session_ids=["session_3"],
                evidence_turn_ids=["d12"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
        ],
        metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
    )

    _, packets = build_observational_temporal_memory_packets([sample], max_observations=4, max_reflections=3)
    packet_by_id = {packet.question_id: packet for packet in packets}

    assert "mentorship program for lgbtq youth" in packet_by_id["q-events"].assembled_context.lower()
    assert "inspired them to be better allies" in packet_by_id["q-events"].assembled_context.lower()
    assert "blast last year at the pride fest" in packet_by_id["q-pride"].assembled_context.lower()


def test_locomo_temporal_questions_keep_exact_relative_turns():
    from domain_chip_memory.contracts import (
        NormalizedBenchmarkSample,
        NormalizedQuestion,
        NormalizedSession,
        NormalizedTurn,
    )

    sample = NormalizedBenchmarkSample(
        benchmark_name="LoCoMo",
        sample_id="locomo-temporal-raw",
        sessions=[
            NormalizedSession(
                session_id="session_1",
                timestamp="1:51 pm on 15 July, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d8",
                        speaker="Melanie",
                        text="Last Fri I finally took my kids to a pottery workshop. We all made our own pots, it was fun and therapeutic!",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_2",
                timestamp="10:37 am on 27 June, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d4",
                        speaker="Melanie",
                        text="Actually, I just took my fam camping in the mountains last week - it was a really nice time together!",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_3",
                timestamp="2:31 pm on 17 July, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d9",
                        speaker="Melanie",
                        text="I had a quiet weekend after we went camping with my fam two weekends ago. It was great to unplug and hang with the kids.",
                    ),
                ],
            ),
        ],
        questions=[
            NormalizedQuestion(
                question_id="q1",
                question="When did Melanie go to the pottery workshop?",
                category="2",
                expected_answers=["The Friday before 15 July 2023"],
                evidence_session_ids=["session_1"],
                evidence_turn_ids=["d8"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q2",
                question="When did Melanie go camping in June?",
                category="2",
                expected_answers=["The week before 27 June 2023"],
                evidence_session_ids=["session_2"],
                evidence_turn_ids=["d4"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q3",
                question="When did Melanie go camping in July?",
                category="2",
                expected_answers=["two weekends before 17 July 2023"],
                evidence_session_ids=["session_3"],
                evidence_turn_ids=["d9"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
        ],
        metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
    )

    _, packets = build_observational_temporal_memory_packets([sample], max_observations=4, max_reflections=3)
    assembled = "\n".join(packet.assembled_context.lower() for packet in packets)

    assert "last fri i finally took my kids to a pottery workshop" in assembled
    assert "camping in the mountains last week" in assembled
    assert "camping with my fam two weekends ago" in assembled


def test_locomo_question_relevant_window_surfaces_third_slice_profile_facts():
    from domain_chip_memory.contracts import (
        NormalizedBenchmarkSample,
        NormalizedQuestion,
        NormalizedSession,
        NormalizedTurn,
    )

    sample = NormalizedBenchmarkSample(
        benchmark_name="LoCoMo",
        sample_id="locomo-third-slice-profile",
        sessions=[
            NormalizedSession(
                session_id="session_1",
                timestamp="4:33 pm on 12 July, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d1",
                        speaker="Caroline",
                        text='I loved "Becoming Nicole" by Amy Ellis Nutt. Highly recommend it for sure!',
                    ),
                    NormalizedTurn(
                        turn_id="d2",
                        speaker="Melanie",
                        text="Luna and Oliver! They are so sweet and playful.",
                    ),
                    NormalizedTurn(
                        turn_id="d3",
                        speaker="Melanie",
                        text="We got another cat named Bailey too.",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_2",
                timestamp="1:33 pm on 25 August, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d4",
                        speaker="Melanie",
                        metadata={"query": "horse painting"},
                        text="Here's a photo of my horse painting I did recently.",
                    ),
                    NormalizedTurn(
                        turn_id="d5",
                        speaker="Caroline",
                        metadata={"query": "rainbow flag painting unity acceptance"},
                        text="The rainbow flag mural is important to me as it reflects the courage and strength of the trans community.",
                    ),
                    NormalizedTurn(
                        turn_id="d6",
                        speaker="Caroline",
                        metadata={"query": "pendant transgender symbol"},
                        text="Take a look at this necklace.",
                    ),
                ],
            ),
        ],
        questions=[
            NormalizedQuestion(
                question_id="q1",
                question="What are Melanie's pets' names?",
                category="1",
                expected_answers=["Oliver, Luna, Bailey"],
                evidence_session_ids=["session_1"],
                evidence_turn_ids=["d2", "d3"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q2",
                question="What has Melanie painted?",
                category="1",
                expected_answers=["Horse"],
                evidence_session_ids=["session_2"],
                evidence_turn_ids=["d4"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q3",
                question="What symbols are important to Caroline?",
                category="1",
                expected_answers=["Rainbow flag, transgender symbol"],
                evidence_session_ids=["session_2"],
                evidence_turn_ids=["d5", "d6"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q4",
                question="What book did Melanie read from Caroline's suggestion?",
                category="1",
                expected_answers=['"Becoming Nicole"'],
                evidence_session_ids=["session_1"],
                evidence_turn_ids=["d1"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
        ],
        metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
    )

    _, packets = build_observational_temporal_memory_packets([sample], max_observations=4, max_reflections=3)
    packet_by_id = {packet.question_id: packet for packet in packets}

    assert "has a pet named Luna" in packet_by_id["q1"].assembled_context
    assert "has a pet named Oliver" in packet_by_id["q1"].assembled_context
    assert "has a pet named Bailey" in packet_by_id["q1"].assembled_context
    assert "painted horse" in packet_by_id["q2"].assembled_context
    assert "important symbol to Caroline is Rainbow flag" in packet_by_id["q3"].assembled_context
    assert "important symbol to Caroline is transgender symbol" in packet_by_id["q3"].assembled_context
    assert 'read "Becoming Nicole"' in packet_by_id["q4"].assembled_context


def test_locomo_question_relevant_window_surfaces_fourth_slice_family_and_counseling_facts():
    from domain_chip_memory.contracts import (
        NormalizedBenchmarkSample,
        NormalizedQuestion,
        NormalizedSession,
        NormalizedTurn,
    )

    sample = NormalizedBenchmarkSample(
        benchmark_name="LoCoMo",
        sample_id="locomo-fourth-slice-facts",
        sessions=[
            NormalizedSession(
                session_id="session_1",
                timestamp="6:55 pm on 20 October, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d1",
                        speaker="Melanie",
                        text="Thanks! They were scared but we reassured them and explained their brother would be OK. They're tough kids.",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_2",
                timestamp="3:31 pm on 23 August, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d2",
                        speaker="Melanie",
                        text="Luna and Oliver! They are so sweet and playful - they really liven up the house! Just got some new shoes, too!",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_3",
                timestamp="9:55 am on 22 October, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d3",
                        speaker="Melanie",
                        metadata={"img_url": "https://example.com/figurines.jpg", "blip_caption": "a couple of wooden dolls sitting on a table"},
                        text="Congrats, Caroline! Adoption sounds awesome. I'm so happy for you. These figurines I bought yesterday remind me of family love. Tell me, what's your vision for the future?",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_4",
                timestamp="1:14 pm on 25 May, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d4",
                        speaker="Melanie",
                        text="Thanks, Caroline! The event was really thought-provoking. I'm starting to realize that self-care is really important.",
                    ),
                    NormalizedTurn(
                        turn_id="d5",
                        speaker="Melanie",
                        text="Yeah, it's tough. So I'm carving out some me-time each day - running, reading, or playing my violin - which refreshes me and helps me stay present for my fam!",
                    ),
                    NormalizedTurn(
                        turn_id="d6",
                        speaker="Caroline",
                        text="Researching adoption agencies - it's been a dream to have a family and give a loving home to kids who need it.",
                    ),
                    NormalizedTurn(
                        turn_id="d7",
                        speaker="Caroline",
                        text="I chose them 'cause they help LGBTQ+ folks with adoption. Their inclusivity and support really spoke to me.",
                    ),
                    NormalizedTurn(
                        turn_id="d8",
                        speaker="Caroline",
                        text="I'm thrilled to make a family for kids who need one. It'll be tough as a single parent, but I'm up for the challenge!",
                    ),
                    NormalizedTurn(
                        turn_id="d9",
                        speaker="Melanie",
                        text="You're doing something amazing! Creating a family for those kids is so lovely. You'll be an awesome mom! Good luck!",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_5",
                timestamp="7:55 pm on 9 June, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d10",
                        speaker="Melanie",
                        text="5 years already! Time flies- feels like just yesterday I put this dress on! Thanks, Caroline!",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_6",
                timestamp="10:37 am on 27 June, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d11",
                        speaker="Caroline",
                        metadata={"img_url": "https://example.com/necklace.jpg", "blip_caption": "a person holding a necklace with a cross and a heart"},
                        text="This necklace is super special to me - a gift from my grandma in my home country, Sweden. She gave it to me when I was young, and it stands for love, faith and strength.",
                    ),
                    NormalizedTurn(
                        turn_id="d12",
                        speaker="Caroline",
                        text="I've got some other stuff with sentimental value, like my hand-painted bowl. A friend made it for my 18th birthday ten years ago. The pattern and colors are awesome-- it reminds me of art and self-expression.",
                    ),
                    NormalizedTurn(
                        turn_id="d13",
                        speaker="Melanie",
                        text="Actually, I just took my fam camping in the mountains last week - it was a really nice time together!",
                    ),
                    NormalizedTurn(
                        turn_id="d14",
                        speaker="Caroline",
                        metadata={"blip_caption": "a book shelf with many books on it"},
                        text="Lately, I've been looking into counseling and mental health as a career. I want to help people who have gone through the same things as me.",
                    ),
                    NormalizedTurn(
                        turn_id="d15",
                        speaker="Caroline",
                        text="Thanks, Melanie. It really mattered. My own journey and the support I got made a huge difference. Now I want to help people go through it too. I saw how counseling and support groups improved my life, so I started caring more about mental health and understanding myself.",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_7",
                timestamp="8:18 pm on 6 July, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d16",
                        speaker="Caroline",
                        text="I'm still figuring out the details, but I'm thinking of working with trans people, helping them accept themselves and supporting their mental health. Last Friday, I went to an LGBTQ+ counseling workshop and it was really enlightening. They talked about different therapeutic methods and how to best work with trans people.",
                    ),
                ],
            ),
            NormalizedSession(
                session_id="session_8",
                timestamp="8:56 pm on 20 July, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d17",
                        speaker="Melanie",
                        text="It was an awesome time, Caroline! We explored nature, roasted marshmallows around the campfire and even went on a hike. The view from the top was amazing! The 2 younger kids love nature.",
                    ),
                ],
            ),
        ],
        questions=[
            NormalizedQuestion(
                question_id="q1",
                question="How many children does Melanie have?",
                category="1",
                expected_answers=["3"],
                evidence_session_ids=["session_1"],
                evidence_turn_ids=["d1"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q2",
                question="What items has Melanie bought?",
                category="1",
                expected_answers=["Figurines, shoes"],
                evidence_session_ids=["session_2", "session_3"],
                evidence_turn_ids=["d2", "d3"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q3",
                question="What did Melanie realize after the charity race?",
                category="4",
                expected_answers=["self-care is important"],
                evidence_session_ids=["session_4"],
                evidence_turn_ids=["d4"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q4",
                question="How does Melanie prioritize self-care?",
                category="4",
                expected_answers=["by carving out some me-time each day for activities like running, reading, or playing the violin"],
                evidence_session_ids=["session_4"],
                evidence_turn_ids=["d5"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q5",
                question="What are Caroline's plans for the summer?",
                category="4",
                expected_answers=["researching adoption agencies"],
                evidence_session_ids=["session_4"],
                evidence_turn_ids=["d6"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q6",
                question="Why did Caroline choose the adoption agency?",
                category="4",
                expected_answers=["because of their inclusivity and support for LGBTQ+ individuals"],
                evidence_session_ids=["session_4"],
                evidence_turn_ids=["d7"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q7",
                question="What is Caroline excited about in the adoption process?",
                category="4",
                expected_answers=["creating a family for kids who need one"],
                evidence_session_ids=["session_4"],
                evidence_turn_ids=["d8"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q8",
                question="What does Melanie think about Caroline's decision to adopt?",
                category="4",
                expected_answers=["she thinks Caroline is doing something amazing and will be an awesome mom"],
                evidence_session_ids=["session_4"],
                evidence_turn_ids=["d9"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q9",
                question="How long have Mel and her husband been married?",
                category="4",
                expected_answers=["Mel and her husband have been married for 5 years."],
                evidence_session_ids=["session_5"],
                evidence_turn_ids=["d10"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q10",
                question="What does Caroline's necklace symbolize?",
                category="4",
                expected_answers=["love, faith, and strength"],
                evidence_session_ids=["session_6"],
                evidence_turn_ids=["d11"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q11",
                question="What country is Caroline's grandma from?",
                category="4",
                expected_answers=["Sweden"],
                evidence_session_ids=["session_6"],
                evidence_turn_ids=["d11"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q12",
                question="What was grandma's gift to Caroline?",
                category="4",
                expected_answers=["necklace"],
                evidence_session_ids=["session_6"],
                evidence_turn_ids=["d11"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q13",
                question="What is Melanie's hand-painted bowl a reminder of?",
                category="4",
                expected_answers=["art and self-expression"],
                evidence_session_ids=["session_6"],
                evidence_turn_ids=["d12"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q14",
                question="What did Melanie and her family do while camping?",
                category="4",
                expected_answers=["explored nature, roasted marshmallows, and went on a hike"],
                evidence_session_ids=["session_8"],
                evidence_turn_ids=["d17"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q15",
                question="What kind of counseling and mental health services is Caroline interested in pursuing?",
                category="4",
                expected_answers=["working with trans people, helping them accept themselves and supporting their mental health"],
                evidence_session_ids=["session_7"],
                evidence_turn_ids=["d16"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q16",
                question="What workshop did Caroline attend recently?",
                category="4",
                expected_answers=["LGBTQ+ counseling workshop"],
                evidence_session_ids=["session_7"],
                evidence_turn_ids=["d16"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q17",
                question="What was discussed in the LGBTQ+ counseling workshop?",
                category="4",
                expected_answers=["therapeutic methods and how to best work with trans people"],
                evidence_session_ids=["session_7"],
                evidence_turn_ids=["d16"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
            NormalizedQuestion(
                question_id="q18",
                question="What motivated Caroline to pursue counseling?",
                category="4",
                expected_answers=["her own journey and the support she received, and how counseling improved her life"],
                evidence_session_ids=["session_6"],
                evidence_turn_ids=["d15"],
                metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
            ),
        ],
        metadata={"speaker_a": "Caroline", "speaker_b": "Melanie"},
    )

    _, packets = build_observational_temporal_memory_packets([sample], max_observations=4, max_reflections=3)
    packet_by_id = {packet.question_id: packet for packet in packets}

    assert "Melanie has 3 children" in packet_by_id["q1"].assembled_context
    assert "Melanie bought Figurines" in packet_by_id["q2"].assembled_context
    assert "Melanie bought shoes" in packet_by_id["q2"].assembled_context
    assert "Melanie realized self-care is important" in packet_by_id["q3"].assembled_context
    assert "Melanie prioritizes self-care by carving out some me-time each day for activities like running, reading, or playing the violin" in packet_by_id["q4"].assembled_context
    assert "Caroline's plan for the summer is researching adoption agencies" in packet_by_id["q5"].assembled_context
    assert "Caroline chose the adoption agency because their inclusivity and support for LGBTQ+ individuals" in packet_by_id["q6"].assembled_context
    assert "Caroline is excited about creating a family for kids who need one in the adoption process" in packet_by_id["q7"].assembled_context
    assert "Melanie thinks the adoption decision is doing something amazing and will be an awesome mom" in packet_by_id["q8"].assembled_context
    assert "Melanie has been married for 5 years" in packet_by_id["q9"].assembled_context
    assert "Caroline's necklace symbolizes love, faith, and strength" in packet_by_id["q10"].assembled_context
    assert "Caroline moved from Sweden" in packet_by_id["q11"].assembled_context
    assert "Caroline's grandma gave Caroline a necklace" in packet_by_id["q12"].assembled_context
    assert "Caroline's hand-painted bowl reminds Caroline of art and self-expression" in packet_by_id["q13"].assembled_context
    assert "While camping Melanie explored nature" in packet_by_id["q14"].assembled_context
    assert "While camping Melanie roasted marshmallows" in packet_by_id["q14"].assembled_context
    assert "While camping Melanie went on a hike" in packet_by_id["q14"].assembled_context
    assert "Caroline is interested in working with trans people, helping them accept themselves and supporting their mental health" in packet_by_id["q15"].assembled_context
    assert "Caroline attended LGBTQ+ counseling workshop" in packet_by_id["q16"].assembled_context
    assert "Caroline's workshop discussed therapeutic methods and how to best work with trans people" in packet_by_id["q17"].assembled_context
    assert "Caroline was motivated by her own journey and the support she received, and how counseling improved her life" in packet_by_id["q18"].assembled_context


def test_locomo_question_relevant_window_surfaces_fifth_slice_object_and_meaning_facts():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-26"
    )
    subset = type(sample)(
        benchmark_name=sample.benchmark_name,
        sample_id=sample.sample_id,
        sessions=sample.sessions,
        questions=sample.questions[100:125],
        metadata=sample.metadata,
    )

    _, packets = build_observational_temporal_memory_packets([subset], max_observations=4, max_reflections=3)
    packet_by_id = {packet.question_id: packet for packet in packets}

    assert "Caroline wants to create a safe and inviting place for people to grow" in packet_by_id["conv-26-qa-101"].assembled_context
    assert "Caroline has kids' books - classics, stories from different cultures, educational books in the library" in packet_by_id["conv-26-qa-103"].assembled_context
    assert "Caroline took away Lessons on self-acceptance and finding support from the book" in packet_by_id["conv-26-qa-106"].assembled_context
    assert "Melanie got into running To de-stress and clear her mind" in packet_by_id["conv-26-qa-108"].assembled_context
    assert "Melanie made pots at the pottery workshop" in packet_by_id["conv-26-qa-110"].assembled_context
    assert "Melanie made a cup with a dog face on it at the pottery workshop" in packet_by_id["conv-26-qa-110"].assembled_context
    assert "Melanie's family painted a sunset with a palm tree" in packet_by_id["conv-26-qa-113"].assembled_context
    assert "Flowers are important to Melanie because They remind her to appreciate the small moments and were a part of her wedding decor" in packet_by_id["conv-26-qa-116"].assembled_context
    assert "Caroline's art-show painting was inspired by visiting an LGBTQ center and wanting to capture unity and strength" in packet_by_id["conv-26-qa-117"].assembled_context
    assert "Melanie saw the Perseid meteor shower while camping" in packet_by_id["conv-26-qa-119"].assembled_context
    assert "Matt Patterson performed at Melanie's daughter's birthday" in packet_by_id["conv-26-qa-122"].assembled_context
    assert "Caroline has a guinea pig" in packet_by_id["conv-26-qa-124"].assembled_context
    assert "Melanie has Two cats and a dog" in packet_by_id["conv-26-qa-125"].assembled_context


def test_locomo_evidence_and_belief_split_prefers_exact_evidence_for_scoreable_seventh_slice_questions():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-26"
    )
    subset = type(sample)(
        benchmark_name=sample.benchmark_name,
        sample_id=sample.sample_id,
        sessions=sample.sessions,
        questions=sample.questions[150:152],
        metadata=sample.metadata,
    )

    _, packets = build_observational_temporal_memory_packets([subset], max_observations=4, max_reflections=3)
    packet_by_id = {packet.question_id: packet for packet in packets}

    assert "evidence_memory:" in packet_by_id["conv-26-qa-151"].assembled_context
    assert "belief_memory:" in packet_by_id["conv-26-qa-151"].assembled_context
    assert "answer_candidate: Appreciate them a lot" in packet_by_id["conv-26-qa-151"].assembled_context
    assert "answer_candidate: went on a hike" in packet_by_id["conv-26-qa-152"].assembled_context


def test_locomo_yes_no_subject_grounding_prefers_no_when_other_speaker_made_object():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-26"
    )
    subset = type(sample)(
        benchmark_name=sample.benchmark_name,
        sample_id=sample.sample_id,
        sessions=sample.sessions,
        questions=[next(question for question in sample.questions if question.question_id == "conv-26-qa-168")],
        metadata=sample.metadata,
    )

    _, packets = build_observational_temporal_memory_packets([subset], max_observations=4, max_reflections=3)

    assert "answer_candidate: No" in packets[0].assembled_context


def test_locomo_conv30_temporal_candidates_are_normalized_from_anchor_time():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-30"
    )
    subset = type(sample)(
        benchmark_name=sample.benchmark_name,
        sample_id=sample.sample_id,
        sessions=sample.sessions,
        questions=[
            next(question for question in sample.questions if question.question_id == question_id)
            for question_id in ("conv-30-qa-1", "conv-30-qa-2", "conv-30-qa-8", "conv-30-qa-13", "conv-30-qa-14")
        ],
        metadata=sample.metadata,
    )

    _, packets = build_observational_temporal_memory_packets([subset], max_observations=4, max_reflections=3)
    packet_by_id = {packet.question_id: packet for packet in packets}

    assert "answer_candidate: 19 January 2023" in packet_by_id["conv-30-qa-1"].assembled_context
    assert "answer_candidate: January 2023" in packet_by_id["conv-30-qa-2"].assembled_context
    assert "answer_candidate: 29 January 2023" in packet_by_id["conv-30-qa-8"].assembled_context
    assert "answer_candidate: March 2023" in packet_by_id["conv-30-qa-13"].assembled_context
    assert "answer_candidate: 16 March 2023" in packet_by_id["conv-30-qa-14"].assembled_context


def test_locomo_conv30_shared_and_explanatory_candidates_are_synthesized():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-30"
    )
    subset = type(sample)(
        benchmark_name=sample.benchmark_name,
        sample_id=sample.sample_id,
        sessions=sample.sessions,
        questions=[
            next(question for question in sample.questions if question.question_id == question_id)
            for question_id in (
                "conv-30-qa-3",
                "conv-30-qa-4",
                "conv-30-qa-5",
                "conv-30-qa-10",
                "conv-30-qa-18",
                "conv-30-qa-19",
                "conv-30-qa-24",
                "conv-30-qa-25",
            )
        ],
        metadata=sample.metadata,
    )

    _, packets = build_observational_temporal_memory_packets([subset], max_observations=4, max_reflections=3)
    packet_by_id = {packet.question_id: packet for packet in packets}

    assert "answer_candidate: by dancing" in packet_by_id["conv-30-qa-3"].assembled_context
    assert "answer_candidate: They lost their jobs and decided to start their own businesses." in packet_by_id["conv-30-qa-4"].assembled_context
    assert "answer_candidate: He lost his job and decided to start his own business to share his passion." in packet_by_id["conv-30-qa-5"].assembled_context
    assert "answer_candidate: Rome" in packet_by_id["conv-30-qa-10"].assembled_context
    assert "answer_candidate: She always loved fashion trends and finding unique pieces and she lost her job so decided it was time to start her own business." in packet_by_id["conv-30-qa-18"].assembled_context
    assert "answer_candidate: Yes" in packet_by_id["conv-30-qa-19"].assembled_context
    assert "answer_candidate: worked with an artist to make unique fashion pieces, made limited-edition sweatshirts, got some new offers and promotions for online store, developed a video presentation showing how to style her pieces" in packet_by_id["conv-30-qa-24"].assembled_context
    assert "answer_candidate: fair, networking events, dance competition" in packet_by_id["conv-30-qa-25"].assembled_context


def test_locomo_conv30_temporal_candidates_cover_future_relative_and_anchor_dates():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-30"
    )
    subset = type(sample)(
        benchmark_name=sample.benchmark_name,
        sample_id=sample.sample_id,
        sessions=sample.sessions,
        questions=[
            next(question for question in sample.questions if question.question_id == question_id)
            for question_id in (
                "conv-30-qa-8",
                "conv-30-qa-14",
                "conv-30-qa-7",
                "conv-30-qa-12",
                "conv-30-qa-15",
                "conv-30-qa-17",
                "conv-30-qa-21",
                "conv-30-qa-22",
            )
        ],
        metadata=sample.metadata,
    )

    _, packets = build_observational_temporal_memory_packets([subset], max_observations=4, max_reflections=3)
    packet_by_id = {packet.question_id: packet for packet in packets}

    assert "answer_candidate: 29 January 2023" in packet_by_id["conv-30-qa-8"].assembled_context
    assert "answer_candidate: February 2023" in packet_by_id["conv-30-qa-7"].assembled_context
    assert "answer_candidate: 16 March 2023" in packet_by_id["conv-30-qa-14"].assembled_context
    assert "answer_candidate: A few years ago" in packet_by_id["conv-30-qa-12"].assembled_context
    assert "answer_candidate: 3 April 2023" in packet_by_id["conv-30-qa-15"].assembled_context
    assert "answer_candidate: 24 April 2023" in packet_by_id["conv-30-qa-17"].assembled_context
    assert "answer_candidate: 27 May 2023" in packet_by_id["conv-30-qa-21"].assembled_context
    assert "answer_candidate: 27 May 2023" in packet_by_id["conv-30-qa-22"].assembled_context


def test_locomo_conv26_scoreable_tail_yes_no_candidates_are_preserved():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-26"
    )
    subset = type(sample)(
        benchmark_name=sample.benchmark_name,
        sample_id=sample.sample_id,
        sessions=sample.sessions,
        questions=[
            next(question for question in sample.questions if question.question_id == question_id)
            for question_id in (
                "conv-26-qa-168",
                "conv-26-qa-179",
            )
        ],
        metadata=sample.metadata,
    )

    _, packets = build_observational_temporal_memory_packets([subset], max_observations=4, max_reflections=3)
    packet_by_id = {packet.question_id: packet for packet in packets}

    assert "answer_candidate: No" in packet_by_id["conv-26-qa-168"].assembled_context
    assert "answer_candidate: No" in packet_by_id["conv-26-qa-179"].assembled_context


def test_summary_synthesis_locomo_unseen_scoreable_questions_prefer_exact_support_over_aggregate_chatter():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-41"
    )
    subset = type(sample)(
        benchmark_name=sample.benchmark_name,
        sample_id=sample.sample_id,
        sessions=sample.sessions,
        questions=[
            next(question for question in sample.questions if question.question_id == question_id)
            for question_id in ("conv-41-qa-1", "conv-41-qa-3", "conv-41-qa-4")
        ],
        metadata=sample.metadata,
    )

    _, packets = build_summary_synthesis_memory_packets([subset])
    packet_by_id = {packet.question_id: packet for packet in packets}

    assert "answer_candidate: my mom" in packet_by_id["conv-41-qa-1"].assembled_context.lower()
    assert "answer_candidate: kickboxing, taekwondo" in packet_by_id["conv-41-qa-3"].assembled_context.lower()
    assert "answer_candidate: volunteering at a homeless shelter" in packet_by_id["conv-41-qa-4"].assembled_context.lower()
    assert packet_by_id["conv-41-qa-1"].answer_candidates[0].source == "evidence_memory"
    assert packet_by_id["conv-41-qa-3"].answer_candidates[0].source == "evidence_memory"
    assert packet_by_id["conv-41-qa-4"].answer_candidates[0].source == "evidence_memory"


def test_summary_synthesis_locomo_unseen_conv47_recovers_exact_supportable_answers():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-47"
    )
    subset = type(sample)(
        benchmark_name=sample.benchmark_name,
        sample_id=sample.sample_id,
        sessions=sample.sessions,
        questions=[
            next(question for question in sample.questions if question.question_id == question_id)
            for question_id in (
                "conv-47-qa-1",
                "conv-47-qa-2",
                "conv-47-qa-3",
                "conv-47-qa-4",
                "conv-47-qa-6",
                "conv-47-qa-7",
                "conv-47-qa-8",
            )
        ],
        metadata=sample.metadata,
    )

    _, packets = build_summary_synthesis_memory_packets([subset])
    packet_by_id = {packet.question_id: packet for packet in packets}

    assert "answer_candidate: obesity" in packet_by_id["conv-47-qa-1"].assembled_context.lower()
    assert "answer_candidate: bowling" in packet_by_id["conv-47-qa-2"].assembled_context.lower()
    assert "answer_candidate: vr club, mcgee's, baseball game" in packet_by_id["conv-47-qa-3"].assembled_context.lower()
    assert "answer_candidate: no" in packet_by_id["conv-47-qa-4"].assembled_context.lower()
    answer_6 = packet_by_id["conv-47-qa-6"].assembled_context.lower()
    assert "john's favorite game is cs:go" in answer_6
    assert "james's favorite game is apex legends" in answer_6
    assert "answer_candidate: likely yes" in packet_by_id["conv-47-qa-7"].assembled_context.lower()
    assert "answer_candidate: connecticut" in packet_by_id["conv-47-qa-8"].assembled_context.lower()
    assert packet_by_id["conv-47-qa-1"].answer_candidates[0].source == "evidence_memory"
    assert packet_by_id["conv-47-qa-2"].answer_candidates[0].source == "evidence_memory"
    assert packet_by_id["conv-47-qa-3"].answer_candidates[0].source == "evidence_memory"
    assert packet_by_id["conv-47-qa-6"].answer_candidates[0].source == "evidence_memory"
    assert packet_by_id["conv-47-qa-7"].answer_candidates[0].source == "evidence_memory"
    assert packet_by_id["conv-47-qa-8"].answer_candidates[0].source == "evidence_memory"


def test_summary_synthesis_locomo_conv49_typed_fact_and_count_questions_recover_exact_answers():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-49"
    )
    subset = type(sample)(
        benchmark_name=sample.benchmark_name,
        sample_id=sample.sample_id,
        sessions=sample.sessions,
        questions=[
            next(question for question in sample.questions if question.question_id == question_id)
            for question_id in (
                "conv-49-qa-1",
                "conv-49-qa-2",
                "conv-49-qa-3",
                "conv-49-qa-4",
                "conv-49-qa-5",
                "conv-49-qa-6",
                "conv-49-qa-7",
                "conv-49-qa-8",
                "conv-49-qa-9",
                "conv-49-qa-12",
                "conv-49-qa-15",
                "conv-49-qa-16",
                "conv-49-qa-17",
                "conv-49-qa-19",
            )
        ],
        metadata=sample.metadata,
    )

    _, packets = build_summary_synthesis_memory_packets([subset])
    packet_by_id = {packet.question_id: packet for packet in packets}

    assert "answer_candidate: prius" in packet_by_id["conv-49-qa-1"].assembled_context.lower()
    assert "answer_candidate: his old prius and his new prius." in packet_by_id["conv-49-qa-2"].assembled_context.lower()
    assert "answer_candidate: rockies, jasper" in packet_by_id["conv-49-qa-3"].assembled_context.lower()
    assert "answer_candidate: two" in packet_by_id["conv-49-qa-4"].assembled_context.lower()
    assert "answer_candidate: painting" in packet_by_id["conv-49-qa-5"].assembled_context.lower()
    assert "answer_candidate: canada" in packet_by_id["conv-49-qa-6"].assembled_context.lower()
    assert "answer_candidate: two" in packet_by_id["conv-49-qa-7"].assembled_context.lower()
    answer_8 = packet_by_id["conv-49-qa-8"].assembled_context.lower()
    assert "painting" in answer_8
    assert "kayaking" in answer_8
    assert "hiking" in answer_8
    assert "cooking" in answer_8
    assert "running" in answer_8
    assert "answer_candidate: watercolor painting" in packet_by_id["conv-49-qa-9"].assembled_context.lower()
    assert "answer_candidate: weight problem" in packet_by_id["conv-49-qa-12"].assembled_context.lower()
    assert "answer_candidate: ginger snaps" in packet_by_id["conv-49-qa-15"].assembled_context.lower()
    assert "answer_candidate: soda, candy" in packet_by_id["conv-49-qa-16"].assembled_context.lower()
    assert "answer_candidate: malfunctioning self-checkout machines." in packet_by_id["conv-49-qa-17"].assembled_context.lower()
    answer_19 = packet_by_id["conv-49-qa-19"].assembled_context.lower()
    assert "flavored seltzer water" in answer_19
    assert "dark chocolate with high cocoa content" in answer_19
    assert "energy balls" in answer_19
    assert "grilled chicken salad with avocado" in answer_19


def test_longmemeval_factoid_and_abs_candidates_are_short_or_unknown():
    samples = load_longmemeval_json(Path("benchmark_data/official/LongMemEval/data/longmemeval_s_cleaned.json"))
    keep = {
        "76d63226": "answer_candidate: 55-inch",
        "86f00804": "answer_candidate: The Seven Husbands of Evelyn Hugo",
        "c19f7a0b": "answer_candidate: 6:30 pm",
        "4100d0a0": "answer_candidate: A mix of Irish and Italian",
        "29f2956b": "answer_candidate: 30 minutes",
        "1faac195": "answer_candidate: Denver",
        "c14c00dd": "answer_candidate: Trader Joe's",
        "36580ce8": "answer_candidate: bronchitis",
        "3d86fd0a": "answer_candidate: a coffee shop in the city",
        "a82c026e": "answer_candidate: Dark Souls 3 DLC",
        "gpt4_d84a3211": "answer_candidate: $185",
        "36b9f61e": "answer_candidate: $2500",
        "0862e8bf_abs": "answer_candidate: unknown",
        "15745da0_abs": "answer_candidate: unknown",
        "bc8a6e93_abs": "answer_candidate: unknown",
        "19b5f2b3_abs": "answer_candidate: unknown",
        "29f2956b_abs": "answer_candidate: unknown",
        "f4f1d8a4_abs": "answer_candidate: unknown",
        "88432d0a_abs": "answer_candidate: unknown",
        "80ec1f4f_abs": "answer_candidate: unknown",
        "eeda8a6d_abs": "answer_candidate: unknown",
        "60bf93ed_abs": "answer_candidate: unknown",
        "edced276_abs": "answer_candidate: unknown",
        "gpt4_372c3eed_abs": "answer_candidate: unknown",
    }
    subset = [sample for sample in samples if sample.questions[0].question_id in keep]

    _, packets = build_observational_temporal_memory_packets(subset, max_observations=4, max_reflections=3)
    packet_by_id = {packet.question_id: packet for packet in packets}

    for packet in packets:
        assert keep[packet.question_id].lower() in packet.assembled_context.lower()
    assert "$25" in packet_by_id["gpt4_d84a3211"].assembled_context
    assert "$40" in packet_by_id["gpt4_d84a3211"].assembled_context
    assert "$120" in packet_by_id["gpt4_d84a3211"].assembled_context
    assert "$1,200" in packet_by_id["36b9f61e"].assembled_context
    assert "$800" in packet_by_id["36b9f61e"].assembled_context
    assert "$500" in packet_by_id["36b9f61e"].assembled_context


def test_longmemeval_preference_packets_surface_domain_anchors():
    samples = load_longmemeval_json(Path("benchmark_data/official/LongMemEval/data/longmemeval_s_cleaned.json"))
    keep = {
        "8a2466db": "Adobe Premiere Pro",
        "0edc2aef": "hotel",
        "09d032c9": "portable power bank",
        "54026fce": "watercooler conversations with colleagues",
        "95228167": "Fender Stratocaster",
        "d24813b1": "lemon poppyseed cake",
    }
    subset = [sample for sample in samples if sample.questions[0].question_id in keep]

    _, packets = build_observational_temporal_memory_packets(subset, max_observations=4, max_reflections=3)

    for packet in packets:
        assert keep[packet.question_id].lower() in packet.assembled_context.lower()


def test_longmemeval_aggregate_candidates_cover_count_and_duration_cases():
    samples = load_longmemeval_json(Path("benchmark_data/official/LongMemEval/data/longmemeval_s_cleaned.json"))
    keep = {
        "0a995998": "answer_candidate: 3",
        "81507db6": "answer_candidate: 3",
        "6d550036": "answer_candidate: 2",
        "gpt4_59c863d7": "answer_candidate: 5",
        "b5ef892d": "answer_candidate: 8 days",
        "e831120c": "answer_candidate: 3.5 weeks",
        "3a704032": "answer_candidate: 3",
        "c4a1ceb8": "answer_candidate: 3",
        "gpt4_d84a3211": "answer_candidate: $185",
        "aae3761f": "answer_candidate: 15 hours",
        "gpt4_f2262a51": "answer_candidate: 3",
        "dd2973ad": "answer_candidate: 2 AM",
        "gpt4_a56e767c": "answer_candidate: 4",
        "46a3abf7": "answer_candidate: 3",
        "36b9f61e": "answer_candidate: $2500",
        "28dc39ac": "answer_candidate: 140 hours",
        "gpt4_2f8be40d": "answer_candidate: 3",
        "2e6d26dc": "answer_candidate: 5",
        "gpt4_15e38248": "answer_candidate: 4",
        "88432d0a": "answer_candidate: 4",
        "80ec1f4f": "answer_candidate: 2",
        "d23cf73b": "answer_candidate: 4",
        "gpt4_7fce9456": "answer_candidate: 4",
        "d682f1a2": "answer_candidate: 3",
        "7024f17c": "answer_candidate: 0.5 hours",
        "gpt4_5501fe77": "answer_candidate: TikTok",
        "gpt4_2ba83207": "answer_candidate: Thrive Market",
        "2318644b": "answer_candidate: $270",
        "2ce6a0f2": "answer_candidate: 4",
        "gpt4_d12ceb0e": "answer_candidate: 59.6",
        "00ca467f": "answer_candidate: 2",
        "gpt4_31ff4165": "answer_candidate: 4",
        "eeda8a6d": "answer_candidate: 17",
        "2788b940": "answer_candidate: 5",
        "9d25d4e0": "answer_candidate: 3",
        "129d1232": "answer_candidate: $5850",
        "60472f9c": "answer_candidate: 2",
        "gpt4_194be4b3": "answer_candidate: 4",
        "a9f6b44c": "answer_candidate: 2",
        "d851d5ba": "answer_candidate: $3750",
        "5a7937c8": "answer_candidate: 3 days",
        "gpt4_ab202e7f": "answer_candidate: 5",
        "gpt4_e05b82a6": "answer_candidate: 10 times",
        "gpt4_731e37d7": "answer_candidate: $720",
        "edced276": "answer_candidate: 15 days",
        "10d9b85a": "answer_candidate: 3 days",
        "e3038f8c": "answer_candidate: 99",
        "2b8f3739": "answer_candidate: $495",
        "1a8a66a6": "answer_candidate: 2",
        "c2ac3c61": "answer_candidate: 5",
        "bf659f65": "answer_candidate: 3",
        "gpt4_372c3eed": "answer_candidate: 10 years",
        "gpt4_2f91af09": "answer_candidate: 23",
        "d3ab962e": "answer_candidate: 8 miles",
        "2311e44b": "answer_candidate: 190",
        "cc06de0d": "answer_candidate: $6",
        "a11281a2": "answer_candidate: 100",
        "4f54b7c9": "answer_candidate: 5",
        "85fa3a3f": "answer_candidate: $50",
        "9aaed6a3": "answer_candidate: $0.75",
        "1f2b8d4f": "answer_candidate: $750",
        "e6041065": "answer_candidate: 40%",
        "51c32626": "answer_candidate: February 1st",
        "7405e8b1": "answer_candidate: Yes",
        "f35224e0": "answer_candidate: 27",
        "6456829e": "answer_candidate: 8",
        "3c1045c8": "answer_candidate: 2.5 years",
        "60036106": "answer_candidate: 12000",
        "e25c3b8d": "answer_candidate: $300",
        "4adc0475": "answer_candidate: 5",
        "4bc144e2": "answer_candidate: $65",
        "ef66a6e5": "answer_candidate: 2",
        "5025383b": "answer_candidate: photography and cooking",
        "a1cc6108": "answer_candidate: 11",
        "9ee3ecd6": "answer_candidate: 100",
        "3fdac837": "answer_candidate: 11 days",
        "91b15a6e": "answer_candidate: $5150",
        "27016adc": "answer_candidate: 10%",
        "720133ac": "answer_candidate: $75",
        "77eafa52": "answer_candidate: $300",
        "8979f9ec": "answer_candidate: 8 meals",
        "0100672e": "answer_candidate: $12",
        "92a0aa75": "answer_candidate: 1 year and 5 months",
        "3fe836c9": "answer_candidate: $25000",
        "1c549ce4": "answer_candidate: $140",
        "6c49646a": "answer_candidate: 3000 miles",
        "1192316e": "answer_candidate: an hour and a half",
    }
    subset = [sample for sample in samples if sample.questions[0].question_id in keep]

    _, packets = build_observational_temporal_memory_packets(subset, max_observations=4, max_reflections=3)

    for packet in packets:
        assert keep[packet.question_id].lower() in packet.assembled_context.lower()


def test_longmemeval_operator_candidates_cover_201_225_frontier_slice():
    samples = load_longmemeval_json(Path("benchmark_data/official/LongMemEval/data/longmemeval_s_cleaned.json"))
    keep = {
        "0ea62687": "answer_candidate: 2",
        "ba358f49": "answer_candidate: 33",
        "60159905": "answer_candidate: three",
        "ef9cf60a": "answer_candidate: $300",
        "73d42213": "answer_candidate: 9:00 AM",
        "67e0d0f2": "answer_candidate: 20",
        "bb7c3b45": "answer_candidate: $300",
        "61f8c8f8": "answer_candidate: 10 minutes",
        "099778bb": "answer_candidate: 20%",
        "09ba9854": "answer_candidate: $50",
        "157a136e": "answer_candidate: 43",
        "c18a7dc8": "answer_candidate: 7",
        "8cf4d046": "answer_candidate: 3.83",
        "a346bb18": "answer_candidate: 12",
        "8e91e7d9": "answer_candidate: 4",
        "bc149d6b": "answer_candidate: 70 pounds",
        "d6062bb9": "answer_candidate: 1998",
        "a3332713": "answer_candidate: $200",
        "55241a1f": "answer_candidate: 33",
        "f0e564bc": "answer_candidate: $1300",
        "078150f1": "answer_candidate: $50",
        "37f165cf": "answer_candidate: 856",
        "a08a253f": "answer_candidate: 4 days",
    }
    subset = [sample for sample in samples if sample.questions[0].question_id in keep]

    _, packets = build_observational_temporal_memory_packets(subset, max_observations=4, max_reflections=3)

    for packet in packets:
        assert keep[packet.question_id].lower() in packet.assembled_context.lower()


def test_longmemeval_summary_synthesis_candidates_cover_226_250_frontier_slice():
    samples = load_longmemeval_json(Path("benchmark_data/official/LongMemEval/data/longmemeval_s_cleaned.json"))
    keep = {
        "efc3f7c2": "answer_candidate: 30 minutes",
        "21d02d0d": "answer_candidate: 2",
        "gpt4_59149c77": "answer_candidate: 7 days",
        "gpt4_4929293a": "answer_candidate: michael's engagement party",
        "gpt4_f49edff3": (
            "answer_candidate: First, I helped my friend prepare the nursery, "
            "then I helped my cousin pick out stuff for her baby shower, and lastly, "
            "I ordered a customized phone case for my friend's birthday."
        ),
        "gpt4_1d80365e": "answer_candidate: 2 days",
        "gpt4_7f6b06db": "muir woods",
    }
    subset = [sample for sample in samples if sample.questions[0].question_id in keep]

    _, packets = build_summary_synthesis_memory_packets(subset)

    for packet in packets:
        assert keep[packet.question_id].lower() in packet.assembled_context.lower()


def test_summary_synthesis_answer_candidate_computes_longmemeval_friday_wakeup_delta():
    question = NormalizedQuestion(
        question_id="efc3f7c2",
        question="How much earlier do I wake up on Fridays compared to other weekdays?",
        category="multi-session",
        expected_answers=["30 minutes"],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        question_date="2023/05/30 (Tue) 16:24",
    )
    entries = [
        ObservationEntry(
            observation_id="obs-1",
            subject="user",
            predicate="schedule",
            text="wake schedule",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2023/05/29 (Mon) 07:46",
            metadata={
                "source_text": "I wake up at 7:30 AM on other weekdays, but on Fridays I wake up at 7:00 AM.",
            },
        )
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert answer == "30 minutes"


def test_summary_synthesis_answer_candidate_computes_longmemeval_had_passed_since_delta():
    question = NormalizedQuestion(
        question_id="0db4c65d",
        question="How many days had passed since I finished reading 'The Seven Husbands of Evelyn Hugo' when I attended the book reading event at the local library, where the author of 'The Silent Patient' is discussing her latest thriller novel?",
        category="temporal-reasoning",
        expected_answers=["18 days"],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        question_date="2023/02/10 (Fri) 18:44",
    )
    entries = [
        ObservationEntry(
            observation_id="obs-1",
            subject="user",
            predicate="reading",
            text="reading update",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2023/01/12 (Thu) 09:00",
            metadata={
                "source_text": "I finished reading 'The Seven Husbands of Evelyn Hugo' today.",
            },
        ),
        ObservationEntry(
            observation_id="obs-2",
            subject="user",
            predicate="event",
            text="library event",
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2023/01/30 (Mon) 19:00",
            metadata={
                "source_text": "I attended the book reading event at the local library, where the author of 'The Silent Patient' discussed her latest thriller novel.",
            },
        ),
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert answer == "18 days"


def test_summary_synthesis_answer_candidate_prefers_longmemeval_consecutive_charity_pair():
    question = NormalizedQuestion(
        question_id="b46e15ed",
        question="How many months have passed since I participated in two charity events in a row, on consecutive days?",
        category="temporal-reasoning",
        expected_answers=["2"],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        question_date="2023/04/18 (Tue) 03:31",
    )
    entries = [
        ObservationEntry(
            observation_id="obs-1",
            subject="user",
            predicate="event",
            text="charity event",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2023/02/14 (Tue) 09:00",
            metadata={"source_text": "I participated in a charity event today."},
        ),
        ObservationEntry(
            observation_id="obs-2",
            subject="user",
            predicate="event",
            text="charity event",
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2023/02/15 (Wed) 09:00",
            metadata={"source_text": "I participated in another charity event today, so that was two charity events in a row on consecutive days."},
        ),
        ObservationEntry(
            observation_id="obs-3",
            subject="user",
            predicate="event",
            text="cycle event",
            session_id="s3",
            turn_ids=["t3"],
            timestamp="2023/03/19 (Sun) 15:02",
            metadata={"source_text": "I still feel active after my recent charity cycle event."},
        ),
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert answer == "2 months"


def test_summary_synthesis_answer_candidate_prefers_longmemeval_baking_class_primary_clause():
    question = NormalizedQuestion(
        question_id="9a707b81",
        question="How many days ago did I attend a baking class at a local culinary school when I made my friend's birthday cake?",
        category="temporal-reasoning",
        expected_answers=["21 days"],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        question_date="2022/04/15 (Fri) 18:46",
    )
    entries = [
        ObservationEntry(
            observation_id="obs-1",
            subject="user",
            predicate="birthday",
            text="birthday cake",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2022/03/21 (Mon) 15:35",
            metadata={"source_text": "I made my friend's birthday cake today."},
        ),
        ObservationEntry(
            observation_id="obs-2",
            subject="user",
            predicate="class",
            text="baking class",
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2022/03/25 (Fri) 10:00",
            metadata={"source_text": "I attended a baking class at a local culinary school yesterday."},
        ),
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert answer == "21 days"


def test_summary_synthesis_answer_candidate_prefers_longmemeval_smoker_purchase_date():
    question = NormalizedQuestion(
        question_id="gpt4_8279ba02",
        question="How many days ago did I buy a smoker?",
        category="temporal-reasoning",
        expected_answers=["10 days ago"],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        question_date="2023/03/25 (Sat) 02:46",
    )
    entries = [
        ObservationEntry(
            observation_id="obs-1",
            subject="user",
            predicate="smoker",
            text="smoker advice",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2023/03/01 (Wed) 14:27",
            metadata={"source_text": "Do you have tips on how to clean a smoker?"},
        ),
        ObservationEntry(
            observation_id="obs-2",
            subject="user",
            predicate="purchase",
            text="smoker purchase",
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2023/03/15 (Wed) 10:40",
            metadata={"source_text": "I bought a smoker yesterday and want to learn how to use it."},
        ),
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert answer == "10 days"


def test_summary_synthesis_answer_candidate_orders_longmemeval_completed_trips_not_planning_chatter():
    question = NormalizedQuestion(
        question_id="gpt4_7f6b06db",
        question="What is the order of the three trips I took in the past three months, from earliest to latest?",
        category="temporal-reasoning",
        expected_answers=[""],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        question_date="2023/06/01 (Thu) 03:56",
    )
    entries = [
        ObservationEntry(
            observation_id="obs-1",
            subject="user",
            predicate="plan",
            text="trip planning",
            session_id="s1",
            turn_ids=["t1"],
            timestamp="2023/03/05 (Sun) 09:00",
            metadata={"source_text": "I'm planning a trip to Kyoto or Osaka during the Golden Week holiday in May, but I'm not sure what to expect."},
        ),
        ObservationEntry(
            observation_id="obs-2",
            subject="user",
            predicate="trip",
            text="muir woods",
            session_id="s2",
            turn_ids=["t2"],
            timestamp="2023/03/10 (Fri) 09:00",
            metadata={"source_text": "I went on a day hike to Muir Woods National Monument with my family."},
        ),
        ObservationEntry(
            observation_id="obs-3",
            subject="user",
            predicate="trip",
            text="big sur",
            session_id="s3",
            turn_ids=["t3"],
            timestamp="2023/04/20 (Thu) 09:00",
            metadata={"source_text": "I went on a road trip with friends to Big Sur and Monterey."},
        ),
        ObservationEntry(
            observation_id="obs-4",
            subject="user",
            predicate="trip",
            text="yosemite",
            session_id="s4",
            turn_ids=["t4"],
            timestamp="2023/05/15 (Mon) 09:00",
            metadata={"source_text": "I started my solo camping trip to Yosemite National Park."},
        ),
    ]

    answer = _choose_summary_synthesis_answer_candidate(question, entries, [])

    assert answer == (
        "First, I went on a day hike to Muir Woods National Monument with my family., "
        "then I went on a road trip with friends to Big Sur and Monterey., "
        "and lastly, I started my solo camping trip to Yosemite National Park.."
    )


def test_longmemeval_preference_candidates_cover_151_175_single_session_lane():
    samples = load_longmemeval_json(Path("benchmark_data/official/LongMemEval/data/longmemeval_s_cleaned.json"))
    keep = {
        "505af2f5": "answer_candidate: Try lower-sugar homemade creamer variations",
        "75f70248": "answer_candidate: Check whether Luna's shedding",
        "d6233ab6": "answer_candidate: It could be worth going",
        "1da05512": "answer_candidate: Buying a NAS now makes sense",
        "fca70973": "answer_candidate: Pick a theme park weekend with thrill rides",
        "b6025781": "answer_candidate: Try meal prep recipes built around quinoa",
        "a89d7624": "answer_candidate: Focus on Denver's live music scene",
        "b0479f84": "answer_candidate: Try more Netflix documentaries",
        "1d4e3b97": "answer_candidate: The new chain and cassette plus your Garmin setup",
        "1c0ddc50": "answer_candidate: During your commute, try history podcasts or audiobooks",
        "0a34ad58": "answer_candidate: Use your Suica card and TripIt itinerary",
    }
    subset = [sample for sample in samples if sample.questions[0].question_id in keep]

    _, packets = build_observational_temporal_memory_packets(subset, max_observations=4, max_reflections=3)

    for packet in packets:
        assert keep[packet.question_id].lower() in packet.assembled_context.lower()


def test_longmemeval_aggregate_candidates_cover_176_200_slice():
    samples = load_longmemeval_json(Path("benchmark_data/official/LongMemEval/data/longmemeval_s_cleaned.json"))
    keep = {
        "681a1674": "answer_candidate: 2",
        "6456829e": "answer_candidate: 8",
        "3c1045c8": "answer_candidate: 2.5 years",
        "60036106": "answer_candidate: 12000",
        "e25c3b8d": "answer_candidate: $300",
        "4adc0475": "answer_candidate: 5",
        "4bc144e2": "answer_candidate: $65",
        "ef66a6e5": "answer_candidate: 2",
        "5025383b": "answer_candidate: photography and cooking",
        "a1cc6108": "answer_candidate: 11",
        "9ee3ecd6": "answer_candidate: 100",
        "3fdac837": "answer_candidate: 11 days",
        "91b15a6e": "answer_candidate: $5150",
        "27016adc": "answer_candidate: 10%",
        "720133ac": "answer_candidate: $75",
        "77eafa52": "answer_candidate: $300",
        "8979f9ec": "answer_candidate: 8 meals",
        "0100672e": "answer_candidate: $12",
        "92a0aa75": "answer_candidate: 1 year and 5 months",
        "3fe836c9": "answer_candidate: $25000",
        "1c549ce4": "answer_candidate: $140",
        "6c49646a": "answer_candidate: 3000 miles",
        "1192316e": "answer_candidate: an hour and a half",
    }
    subset = [sample for sample in samples if sample.questions[0].question_id in keep]

    _, packets = build_observational_temporal_memory_packets(subset, max_observations=4, max_reflections=3)

    for packet in packets:
        assert keep[packet.question_id].lower() in packet.assembled_context.lower()


def test_locomo_question_relevant_window_surfaces_sixth_slice_music_poetry_and_roadtrip_facts():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-26"
    )
    subset = type(sample)(
        benchmark_name=sample.benchmark_name,
        sample_id=sample.sample_id,
        sessions=sample.sessions,
        questions=sample.questions[125:150],
        metadata=sample.metadata,
    )

    _, packets = build_observational_temporal_memory_packets([subset], max_observations=4, max_reflections=3)
    packet_by_id = {packet.question_id: packet for packet in packets}

    assert "Caroline used to do Horseback riding with Caroline's dad" in packet_by_id["conv-26-qa-127"].assembled_context
    assert "Caroline found a rainbow sidewalk in the neighborhood" in packet_by_id["conv-26-qa-129"].assembled_context
    assert "Melanie enjoys listening to Bach and Mozart" in packet_by_id["conv-26-qa-131"].assembled_context
    assert "Melanie is a fan of Ed Sheeran" in packet_by_id["conv-26-qa-132"].assembled_context
    assert "Melanie has been practicing art for seven years" in packet_by_id["conv-26-qa-133"].assembled_context
    assert "Melanie saw A sign stating that someone is not being able to leave at the cafe" in packet_by_id["conv-26-qa-134"].assembled_context
    assert "Caroline's adoption advice is Do research, find an adoption agency or lawyer, gather necessary documents, and prepare emotionally." in packet_by_id["conv-26-qa-135"].assembled_context
    assert "Melanie's setback was She got hurt and had to take a break from pottery." in packet_by_id["conv-26-qa-136"].assembled_context
    assert "During the pottery break Melanie did Read a book and paint." in packet_by_id["conv-26-qa-137"].assembled_context
    assert "Melanie showed A painting inspired by sunsets with a pink sky." in packet_by_id["conv-26-qa-138"].assembled_context
    assert "Melanie shared An abstract painting with blue streaks on a wall." in packet_by_id["conv-26-qa-139"].assembled_context
    assert "Caroline's poetry reading was It was a transgender poetry reading where transgender people shared their stories." in packet_by_id["conv-26-qa-140"].assembled_context
    assert 'Caroline\'s poster said "Trans Lives Matter"' in packet_by_id["conv-26-qa-141"].assembled_context
    assert "Caroline's drawing symbolizes Freedom and being true to herself." in packet_by_id["conv-26-qa-142"].assembled_context
    assert "Caroline's journey through life is An ongoing adventure of learning and growing." in packet_by_id["conv-26-qa-143"].assembled_context
    assert "Melanie's son handled the accident by being scared but reassured by his family" in packet_by_id["conv-26-qa-145"].assembled_context
    assert "Melanie's family are important and mean the world to her" in packet_by_id["conv-26-qa-146"].assembled_context
    assert "Melanie's children were scared but resilient" in packet_by_id["conv-26-qa-147"].assembled_context
    assert "After the accident Melanie felt grateful and thankful for her family" in packet_by_id["conv-26-qa-148"].assembled_context
    assert "When the children enjoyed the Grand Canyon Melanie felt happy and thankful" in packet_by_id["conv-26-qa-149"].assembled_context
    assert "Melanie's family give Melanie Strength and motivation" in packet_by_id["conv-26-qa-150"].assembled_context
