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
from domain_chip_memory.providers import get_provider
from domain_chip_memory.runner import run_baseline
from domain_chip_memory.sample_data import demo_samples


def test_extract_memory_atoms_captures_updated_fact():
    samples = demo_samples()
    atoms = extract_memory_atoms(samples[0])
    values = [atom.value for atom in atoms if atom.predicate == "location"]
    assert "London" in values
    assert "Dubai" in values


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


def test_memory_system_contract_summary_exists():
    payload = build_memory_system_contract_summary()
    names = [item["system_name"] for item in payload["candidate_memory_systems"]]
    assert "beam_temporal_atom_router" in names
    assert "observational_temporal_memory" in names
    assert "dual_store_event_calendar_hybrid" in names


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
