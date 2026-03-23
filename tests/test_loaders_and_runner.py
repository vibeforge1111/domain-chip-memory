import json
from pathlib import Path

from domain_chip_memory.loaders import (
    build_loader_contract_summary,
    load_goodai_config,
    load_goodai_definitions,
    load_locomo_json,
    load_longmemeval_json,
)
from domain_chip_memory.providers import build_provider_contract_summary, get_provider
from domain_chip_memory.runner import build_runner_contract_summary, run_baseline


def test_longmemeval_loader_and_runner(tmp_path: Path):
    data_file = tmp_path / "longmemeval.json"
    data_file.write_text(
        json.dumps(
            [
                {
                    "question_id": "q-1",
                    "question_type": "knowledge-update",
                    "question": "Where do I live now?",
                    "answer": "Dubai",
                    "question_date": "2024-05-01",
                    "haystack_session_ids": ["s1", "s2"],
                    "haystack_dates": ["2024-04-01", "2024-04-20"],
                    "haystack_sessions": [
                        [{"role": "user", "content": "I live in London."}],
                        [{"role": "user", "content": "I moved to Dubai."}],
                    ],
                    "answer_session_ids": ["s2"],
                }
            ]
        ),
        encoding="utf-8",
    )

    samples = load_longmemeval_json(data_file)
    scorecard = run_baseline(
        samples,
        baseline_name="full_context",
        provider=get_provider("heuristic_v1"),
    )

    assert samples[0].benchmark_name == "LongMemEval"
    assert scorecard["overall"]["total"] == 1


def test_locomo_loader(tmp_path: Path):
    data_file = tmp_path / "locomo.json"
    data_file.write_text(
        json.dumps(
            [
                {
                    "sample_id": "locomo-1",
                    "conversation": {
                        "speaker_a": "Alice",
                        "speaker_b": "Bob",
                        "session_1_date_time": "2024-01-01",
                        "session_1": [{"speaker": "Alice", "dia_id": "d1", "text": "I like jazz."}],
                    },
                    "qa": [
                        {
                            "question": "What music does Alice like?",
                            "answer": "jazz",
                            "category": "single-hop",
                            "evidence": ["d1"],
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    samples = load_locomo_json(data_file)
    assert samples[0].benchmark_name == "LoCoMo"
    assert samples[0].questions[0].expected_answers == ["jazz"]


def test_goodai_loader_and_runner(tmp_path: Path):
    config_file = tmp_path / "benchmark-v3-32k.yml"
    config_file.write_text(
        "\n".join(
            [
                "config:",
                '  run_name: "Benchmark 3 - 32k"',
                "datasets:",
                "    args:",
                "      memory_span: 32000",
                "      dataset_examples: 3",
                "    datasets:",
                '      - name: "colours"',
            ]
        ),
        encoding="utf-8",
    )
    definitions_dir = tmp_path / "definitions" / "Colours"
    definitions_dir.mkdir(parents=True)
    (definitions_dir / "0.def.json").write_text(
        json.dumps(
            {
                "script": [
                    "My favourite colour is Purple.",
                    "My favourite colour is Blue.",
                    "What is my favourite colour?",
                ],
                "is_question": [False, False, True],
                "time_jumps": [0.0, 0.0, 0.0],
                "token_spacings": [32000, 32000, 32000],
                "expected_responses": ["Blue"],
                "evaluation_fn": "evaluate_correct",
                "uses_callback": False,
                "can_be_interleaved": True,
                "is_temporal": False,
            }
        ),
        encoding="utf-8",
    )

    config = load_goodai_config(config_file)
    samples = load_goodai_definitions(definitions_dir.parent, config=config)
    scorecard = run_baseline(
        samples,
        baseline_name="lexical",
        provider=get_provider("heuristic_v1"),
        top_k_sessions=1,
    )

    assert config.config_id == "benchmark-v3-32k.yml"
    assert samples[0].benchmark_name == "GoodAI LTM Benchmark"
    assert scorecard["overall"]["total"] == 1


def test_runner_supports_temporal_atom_router(tmp_path: Path):
    data_file = tmp_path / "longmemeval.json"
    data_file.write_text(
        json.dumps(
            [
                {
                    "question_id": "q-1",
                    "question_type": "knowledge-update",
                    "question": "Where do I live now?",
                    "answer": "Dubai",
                    "question_date": "2024-05-01",
                    "haystack_session_ids": ["s1", "s2"],
                    "haystack_dates": ["2024-04-01", "2024-04-20"],
                    "haystack_sessions": [
                        [{"role": "user", "content": "I live in London."}],
                        [{"role": "user", "content": "I moved to Dubai."}],
                    ],
                    "answer_session_ids": ["s2"],
                }
            ]
        ),
        encoding="utf-8",
    )

    samples = load_longmemeval_json(data_file)
    scorecard = run_baseline(
        samples,
        baseline_name="beam_temporal_atom_router",
        provider=get_provider("heuristic_v1"),
        top_k_sessions=2,
        fallback_sessions=1,
    )

    assert scorecard["overall"]["total"] == 1
    assert scorecard["predictions"][0]["predicted_answer"].lower() == "dubai"


def test_runner_supports_observational_temporal_memory(tmp_path: Path):
    data_file = tmp_path / "longmemeval.json"
    data_file.write_text(
        json.dumps(
            [
                {
                    "question_id": "q-1",
                    "question_type": "knowledge-update",
                    "question": "Where do I live now?",
                    "answer": "Dubai",
                    "question_date": "2024-05-01",
                    "haystack_session_ids": ["s1", "s2"],
                    "haystack_dates": ["2024-04-01", "2024-04-20"],
                    "haystack_sessions": [
                        [{"role": "user", "content": "I live in London."}],
                        [{"role": "user", "content": "I moved to Dubai."}],
                    ],
                    "answer_session_ids": ["s2"],
                }
            ]
        ),
        encoding="utf-8",
    )

    samples = load_longmemeval_json(data_file)
    scorecard = run_baseline(
        samples,
        baseline_name="observational_temporal_memory",
        provider=get_provider("heuristic_v1"),
        top_k_sessions=2,
        fallback_sessions=1,
    )

    assert scorecard["overall"]["total"] == 1
    assert scorecard["predictions"][0]["predicted_answer"].lower() == "dubai"


def test_runner_supports_dual_store_event_calendar_hybrid(tmp_path: Path):
    data_file = tmp_path / "longmemeval.json"
    data_file.write_text(
        json.dumps(
            [
                {
                    "question_id": "q-1",
                    "question_type": "knowledge-update",
                    "question": "Where do I live now?",
                    "answer": "Dubai",
                    "question_date": "2024-05-01",
                    "haystack_session_ids": ["s1", "s2"],
                    "haystack_dates": ["2024-04-01", "2024-04-20"],
                    "haystack_sessions": [
                        [{"role": "user", "content": "I live in London."}],
                        [{"role": "user", "content": "I moved to Dubai."}],
                    ],
                    "answer_session_ids": ["s2"],
                }
            ]
        ),
        encoding="utf-8",
    )

    samples = load_longmemeval_json(data_file)
    scorecard = run_baseline(
        samples,
        baseline_name="dual_store_event_calendar_hybrid",
        provider=get_provider("heuristic_v1"),
        top_k_sessions=2,
        fallback_sessions=1,
    )

    assert scorecard["overall"]["total"] == 1
    assert scorecard["predictions"][0]["predicted_answer"].lower() == "dubai"


def test_loader_provider_and_runner_contracts_exist():
    assert build_loader_contract_summary()["loaders"]
    assert build_provider_contract_summary()["providers"]
    assert build_runner_contract_summary()["supported_baselines"]
