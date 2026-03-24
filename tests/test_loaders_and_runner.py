import json
from pathlib import Path

from domain_chip_memory.loaders import (
    build_loader_contract_summary,
    load_goodai_config,
    load_goodai_definitions,
    load_locomo_json,
    load_longmemeval_json,
)
from domain_chip_memory.providers import ProviderResponse, build_provider_contract_summary, get_provider
from domain_chip_memory.runner import _matches_expected_answer, build_runner_contract_summary, run_baseline
from domain_chip_memory.scorecards import BaselinePrediction


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


def test_runner_matches_disjunctive_expected_answers():
    assert _matches_expected_answer("went on a hike", ["Went on a nature walk or hike"]) is True
    assert _matches_expected_answer("appreciate them a lot", ["She appreciated them a lot"]) is True
    assert _matches_expected_answer("no", ["No"]) is True
    assert _matches_expected_answer("yes", ["No"]) is False


def test_runner_matches_month_year_expected_from_specific_date_prediction():
    assert _matches_expected_answer("8 february 2023", ["February, 2023"]) is True


def test_runner_matches_unknown_for_longmemeval_abstention_explanation():
    assert _matches_expected_answer(
        "unknown",
        ["You did not mention this information. You mentioned your cat Luna but not your hamster."],
    ) is True


def test_runner_matches_numeric_how_many_answer_inside_explanatory_gold():
    assert _matches_expected_answer(
        "5",
        ["I have worked on or bought five model kits. The scales of the models are: Revell F-15 Eagle, Tamiya 1/48 scale Spitfire Mk.V."],
    ) is True


def test_runner_matches_numeric_hours_inside_explanatory_gold():
    assert _matches_expected_answer(
        "15 hours",
        ["15 hours for getting to the three destinations (or 30 hours for the round trip)"],
    ) is True


def test_runner_matches_numeric_count_inside_doctor_and_wedding_gold():
    assert _matches_expected_answer(
        "3",
        ["I visited three different doctors: a primary care physician, an ENT specialist, and a dermatologist."],
    ) is True
    assert _matches_expected_answer(
        "3",
        ["I attended three weddings. The couples were Rachel and Mike, Emily and Sarah, and Jen and Tom."],
    ) is True
    assert _matches_expected_answer(
        "4",
        ["I attended four movie festivals."],
    ) is True


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


def test_runner_can_resume_from_existing_predictions(tmp_path: Path):
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
                        "session_1": [
                            {"speaker": "Alice", "dia_id": "d1", "text": "I like jazz."},
                            {"speaker": "Bob", "dia_id": "d2", "text": "I like chess."},
                        ],
                    },
                    "qa": [
                        {
                            "question": "What music does Alice like?",
                            "answer": "jazz",
                            "category": "single-hop",
                            "evidence": ["d1"],
                        },
                        {
                            "question": "What does Bob like?",
                            "answer": "chess",
                            "category": "single-hop",
                            "evidence": ["d2"],
                        },
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    class _StubProvider:
        name = "stub"

        def __init__(self) -> None:
            self.calls: list[str] = []

        def generate_answer(self, packet):
            self.calls.append(packet.question_id)
            return ProviderResponse(answer="chess", metadata={"provider_type": "stub"})

    provider = _StubProvider()
    progress_events: list[dict[str, object]] = []
    samples = load_locomo_json(data_file)
    scorecard = run_baseline(
        samples,
        baseline_name="full_context",
        provider=provider,
        existing_predictions=[
            BaselinePrediction(
                benchmark_name="LoCoMo",
                baseline_name="full_context",
                sample_id="locomo-1",
                question_id="locomo-1-qa-1",
                category="single-hop",
                predicted_answer="jazz",
                expected_answers=["jazz"],
                is_correct=True,
                metadata={"provider_name": "stub", "route": "full_context"},
            )
        ],
        progress_callback=lambda manifest, predictions, event: progress_events.append(event),
    )

    assert provider.calls == ["locomo-1-qa-2"]
    assert progress_events[0]["event"] == "resume"
    assert progress_events[0]["completed"] == 1
    assert scorecard["overall"]["total"] == 2
    assert scorecard["overall"]["correct"] == 2
