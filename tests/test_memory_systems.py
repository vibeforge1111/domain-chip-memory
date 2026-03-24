from pathlib import Path

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
        "0862e8bf_abs": "answer_candidate: unknown",
        "15745da0_abs": "answer_candidate: unknown",
        "bc8a6e93_abs": "answer_candidate: unknown",
        "19b5f2b3_abs": "answer_candidate: unknown",
        "29f2956b_abs": "answer_candidate: unknown",
        "f4f1d8a4_abs": "answer_candidate: unknown",
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


def test_longmemeval_aggregate_candidates_cover_count_and_duration_cases():
    samples = load_longmemeval_json(Path("benchmark_data/official/LongMemEval/data/longmemeval_s_cleaned.json"))
    keep = {
        "0a995998": "answer_candidate: 3",
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
