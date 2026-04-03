import json

from domain_chip_memory.adapters import (
    BEAMAdapter,
    ConvoMemShadowAdapter,
    GoodAILTMBenchmarkAdapter,
    LoCoMoAdapter,
    LongMemEvalAdapter,
    build_adapter_contract_summary,
)
from domain_chip_memory.loaders import load_beam_public_dir


def test_longmemeval_adapter_normalizes_question_centric_instance():
    payload = {
        "question_id": "q-1",
        "question_type": "knowledge-update",
        "question": "Where does the user live now?",
        "answer": "Dubai",
        "question_date": "2024-05-01",
        "haystack_session_ids": ["s1", "s2"],
        "haystack_dates": ["2024-04-01", "2024-04-20"],
        "haystack_sessions": [
            [
                {"role": "user", "content": "I live in London."},
                {"role": "assistant", "content": "Noted."},
            ],
            [
                {"role": "user", "content": "I moved to Dubai.", "has_answer": True},
                {"role": "assistant", "content": "Updated."},
            ],
        ],
        "answer_session_ids": ["s2"],
    }

    sample = LongMemEvalAdapter.normalize_instance(payload)

    assert sample.benchmark_name == "LongMemEval"
    assert sample.sample_id == "q-1"
    assert len(sample.sessions) == 2
    assert sample.questions[0].category == "knowledge-update"
    assert sample.questions[0].evidence_session_ids == ["s2"]
    assert sample.questions[0].evidence_turn_ids == ["s2:turn-1"]


def test_locomo_adapter_normalizes_conversation_and_qa():
    payload = {
        "sample_id": "locomo-1",
        "conversation": {
            "speaker_a": "Alice",
            "speaker_b": "Bob",
            "session_1_date_time": "2024-01-01",
            "session_1": [
                {"speaker": "Alice", "dia_id": "d1", "text": "I like jazz."},
                {"speaker": "Bob", "dia_id": "d2", "text": "Cool."},
            ],
            "session_2_date_time": "2024-01-10",
            "session_2": [
                {"speaker": "Alice", "dia_id": "d3", "text": "I now prefer techno."}
            ],
        },
        "qa": [
            {
                "question": "What music does Alice prefer now?",
                "answer": "techno",
                "category": "temporal",
                "evidence": ["d3"],
            }
        ],
    }

    sample = LoCoMoAdapter.normalize_instance(payload)

    assert sample.benchmark_name == "LoCoMo"
    assert sample.sample_id == "locomo-1"
    assert len(sample.sessions) == 2
    assert sample.questions[0].evidence_session_ids == ["session_2"]
    assert sample.questions[0].evidence_turn_ids == ["d3"]
    assert sample.questions[0].metadata["speaker_a"] == "Alice"
    assert sample.questions[0].metadata["speaker_b"] == "Bob"


def test_goodai_adapter_normalizes_config_and_definition():
    config_payload = {
        "config": {"run_name": "Benchmark 3 - 500k", "incompatibilities": [["a", "b"]]},
        "datasets": {
            "args": {"memory_span": 500000, "dataset_examples": 3},
            "datasets": [
                {"name": "colours", "args": {"colour_changes": 3}},
                {"name": "shopping", "args": {"item_changes": 6}},
            ],
        },
    }
    config = GoodAILTMBenchmarkAdapter.normalize_configuration(
        "benchmark-v3-500k.yml", config_payload
    )
    assert config.benchmark_name == "GoodAI LTM Benchmark"
    assert config.memory_span_tokens == 500000
    assert config.dataset_family_names == ["colours", "shopping"]

    definition_payload = {
        "script": [
            "The name of my favourite colour is Purple.",
            "The name of my favourite colour is Blue.",
            "What is my favourite colour?",
        ],
        "is_question": [False, False, True],
        "time_jumps": [0.0, 0.0, 0.0],
        "token_spacings": [10000, 10000, 10000],
        "expected_responses": ["Blue"],
        "can_be_interleaved": True,
        "evaluation_fn": "evaluate_correct",
        "is_temporal": False,
        "uses_callback": False,
    }
    sample = GoodAILTMBenchmarkAdapter.normalize_definition(
        definition_payload,
        config_id="benchmark-v3-500k.yml",
        run_name="Benchmark 3 - 500k",
        dataset_name="Colours",
        definition_id="0.def.json",
        memory_span_tokens=500000,
    )

    assert sample.benchmark_name == "GoodAI LTM Benchmark"
    assert sample.questions[0].expected_answers == ["Blue"]
    assert sample.metadata["memory_span_tokens"] == 500000
    assert sample.sessions[0].turns[2].metadata["is_question"] is True


def test_shadow_adapter_and_contract_summary_are_available():
    sample = ConvoMemShadowAdapter.normalize_instance(
        {
            "sample_id": "shadow-1",
            "question_id": "shadow-q-1",
            "question": "What food does the user prefer?",
            "answer": "sushi",
            "category": "preferences",
            "conversation": [{"speaker": "user", "text": "I love sushi."}],
        }
    )
    summary = build_adapter_contract_summary()

    assert sample.benchmark_name == "ConvoMem"
    assert summary["official_benchmark_adapters"]
    assert summary["shadow_benchmark_adapters"]


def test_beam_adapter_normalizes_local_slice_instance():
    payload = {
        "sample_id": "beam-1",
        "slice_status": "paper_pinned_local_slice",
        "sessions": [
            {
                "session_id": "beam-session-1",
                "timestamp": "2026-03-25T12:00:00Z",
                "turns": [
                    {"turn_id": "t1", "speaker": "user", "text": "I live in Dubai."},
                    {"turn_id": "t2", "speaker": "assistant", "text": "Noted."},
                ],
            }
        ],
        "questions": [
            {
                "question_id": "beam-1-q-1",
                "question": "Where do I live?",
                "answer": "Dubai",
                "category": "episodic_memory",
                "evidence_session_ids": ["beam-session-1"],
                "evidence_turn_ids": ["t1"],
            }
        ],
    }

    sample = BEAMAdapter.normalize_instance(payload)
    summary = build_adapter_contract_summary()

    assert sample.benchmark_name == "BEAM"
    assert sample.sample_id == "beam-1"
    assert sample.questions[0].expected_answers == ["Dubai"]
    assert sample.questions[0].evidence_turn_ids == ["t1"]
    assert sample.metadata["source_mode"] == "local_pilot"
    assert sample.metadata["slice_status"] == "paper_pinned_local_slice"
    assert any(item["benchmark_name"] == "BEAM" for item in summary["official_benchmark_adapters"])


def test_load_beam_public_dir_normalizes_official_style_fixture(tmp_path):
    conversation_dir = tmp_path / "100K" / "1"
    probing_dir = conversation_dir / "probing_questions"
    probing_dir.mkdir(parents=True)
    (conversation_dir / "chat.json").write_text(
        """
[
  {
    "batch_number": 1,
    "time_anchor": "March-15-2024",
    "turns": [
      [
        {"role": "user", "id": 1, "content": "I live in Dubai."},
        {"role": "assistant", "id": 2, "content": "Noted."}
      ]
    ]
  }
]
""".strip(),
        encoding="utf-8",
    )
    (probing_dir / "probing_questions.json").write_text(
        """
{
  "information_extraction": [
    {
      "question": "Where do I live?",
      "answer": "Dubai",
      "source_chat_ids": [1],
      "rubric": ["Dubai"]
    }
  ],
  "abstention": [
    {
      "question": "What is my favorite food?",
      "ideal_response": "Based on the provided chat, there is no information related to your favorite food.",
      "rubric": ["Based on the provided chat, there is no information related to your favorite food."]
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    samples = load_beam_public_dir(tmp_path, chat_size="128K", upstream_commit="abc123")

    assert len(samples) == 1
    sample = samples[0]
    assert sample.benchmark_name == "BEAM"
    assert sample.metadata["source_mode"] == "official_public"
    assert sample.metadata["dataset_scale"] == "128K"
    assert sample.metadata["upstream_commit"] == "abc123"
    assert sample.questions[0].evidence_turn_ids == ["1:batch-1:msg-1"]
    assert sample.questions[1].should_abstain is True


def test_load_beam_public_dir_appends_rubric_requirements_to_expected_answers(tmp_path):
    conversation_dir = tmp_path / "100K" / "1"
    probing_dir = conversation_dir / "probing_questions"
    probing_dir.mkdir(parents=True)
    (conversation_dir / "chat.json").write_text(
        json.dumps(
            [
                {
                    "batch_number": 1,
                    "time_anchor": "March-15-2024",
                    "turns": [
                        [
                            {
                                "role": "user",
                                "id": 1,
                                "content": "I have never written any Flask routes or handled HTTP requests in this project.",
                            },
                            {
                                "role": "user",
                                "id": 2,
                                "content": "I implemented a basic homepage route with Flask.",
                            },
                        ]
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    (probing_dir / "probing_questions.json").write_text(
        json.dumps(
            {
                "contradiction_resolution": [
                    {
                        "question": "Have I worked with Flask routes and handled HTTP requests in this project?",
                        "ideal_answer": "I notice you've mentioned contradictory information about this. You said you have never written any Flask routes or handled HTTP requests in this project, but you also mentioned implementing a basic homepage route with Flask. Could you clarify which is correct?",
                        "source_chat_ids": [1, 2],
                        "rubric": [
                            "LLM response should state: there is contradictory information",
                            "LLM response should mention: which statement is correct?",
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    samples = load_beam_public_dir(tmp_path, chat_size="128K")

    assert samples[0].questions[0].expected_answers == [
        "I notice you've mentioned contradictory information about this. You said you have never written any Flask routes or handled HTTP requests in this project, but you also mentioned implementing a basic homepage route with Flask. Could you clarify which is correct?",
        "LLM response should state: there is contradictory information",
        "LLM response should mention: which statement is correct?",
    ]


def test_load_beam_public_dir_stamps_scale_metadata_on_questions(tmp_path):
    conversation_dir = tmp_path / "500K" / "5"
    probing_dir = conversation_dir / "probing_questions"
    probing_dir.mkdir(parents=True)
    (conversation_dir / "chat.json").write_text(
        json.dumps(
            [
                {
                    "batch_number": 1,
                    "time_anchor": "March-15-2024",
                    "turns": [
                        [
                            {"role": "user", "id": 1, "content": "I prefer lightweight dependencies."},
                            {"role": "assistant", "id": 2, "content": "Noted."},
                        ]
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    (probing_dir / "probing_questions.json").write_text(
        json.dumps(
            {
                "preference_following": [
                    {
                        "question": "What should I optimize for in the stack recommendation?",
                        "source_chat_ids": [1],
                        "question_type": "preference_following",
                        "expected_compliance": "avoid heavy frameworks",
                        "preference_being_tested": "lightweight dependencies",
                        "compliance_indicators": ["lightweight libraries", "no heavy frameworks"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    samples = load_beam_public_dir(tmp_path, chat_size="500K")
    metadata = samples[0].questions[0].metadata

    assert metadata["sample_id"] == "beam-500k-5"
    assert metadata["dataset_scale"] == "500K"
    assert metadata["conversation_id"] == "5"
    assert metadata["expected_compliance"] == "avoid heavy frameworks"
    assert metadata["preference_being_tested"] == "lightweight dependencies"
    assert metadata["compliance_indicators"] == ["lightweight libraries", "no heavy frameworks"]


def test_load_beam_public_dir_sorts_conversation_ids_numerically(tmp_path):
    for conversation_id in ("1", "2", "10"):
        conversation_dir = tmp_path / "100K" / conversation_id
        probing_dir = conversation_dir / "probing_questions"
        probing_dir.mkdir(parents=True)
        (conversation_dir / "chat.json").write_text(
            json.dumps(
                [
                    {
                        "batch_number": 1,
                        "time_anchor": "March-15-2024",
                        "turns": [
                            [
                                {"role": "user", "id": 1, "content": f"Conversation {conversation_id}."},
                                {"role": "assistant", "id": 2, "content": "Noted."},
                            ]
                        ],
                    }
                ]
            ),
            encoding="utf-8",
        )
        (probing_dir / "probing_questions.json").write_text(
            json.dumps(
                {
                    "information_extraction": [
                        {
                            "question": "Which conversation is this?",
                            "answer": conversation_id,
                            "source_chat_ids": [1],
                            "rubric": [conversation_id],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

    samples = load_beam_public_dir(tmp_path, chat_size="128K", limit=2)

    assert [sample.metadata["conversation_id"] for sample in samples] == ["1", "2"]
