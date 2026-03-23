from domain_chip_memory.adapters import (
    ConvoMemShadowAdapter,
    GoodAILTMBenchmarkAdapter,
    LoCoMoAdapter,
    LongMemEvalAdapter,
    build_adapter_contract_summary,
)


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
