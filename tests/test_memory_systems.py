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
                ],
            ),
            NormalizedSession(
                session_id="session_6",
                timestamp="12:09 am on 13 September, 2023",
                turns=[
                    NormalizedTurn(
                        turn_id="d12",
                        speaker="Melanie",
                        text="We even went on another camping trip in the forest.",
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
                evidence_session_ids=["session_4"],
                evidence_turn_ids=["d9"],
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
