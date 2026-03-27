import json
import sys
from pathlib import Path

from domain_chip_memory import cli
from domain_chip_memory.baselines import build_baseline_contract_summary
from domain_chip_memory.adapters import build_adapter_contract_summary
from domain_chip_memory.canonical_configs import get_canonical_configs
from domain_chip_memory.loaders import build_loader_contract_summary
from domain_chip_memory.experiments import build_experiment_contract_summary, run_candidate_comparison
from domain_chip_memory.memory_systems import build_memory_system_contract_summary
from domain_chip_memory.packets import build_strategy_packet
from domain_chip_memory.providers import ProviderResponse
from domain_chip_memory.providers import build_provider_contract_summary
from domain_chip_memory.providers import get_provider
from domain_chip_memory.runner import build_runner_contract_summary
from domain_chip_memory.scorecards import build_scorecard_contract_summary
from domain_chip_memory.sample_data import demo_samples
from domain_chip_memory.watchtower import build_watchtower_summary


def test_strategy_packet_shape():
    packet = build_strategy_packet()
    assert packet["packet_type"] == "memory_system_strategy_packet"
    assert packet["priority_mutations"]
    assert packet["candidate_combinations"]
    assert packet["combination_search_doctrine"]
    assert packet["initial_system_ladder"]
    assert len(packet["initial_system_ladder"]) == 3
    assert packet["experimental_frontier_claims"]
    assert packet["ten_system_variants"]


def test_watchtower_detects_docs(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in [
        "PRD.md",
        "ARCHITECTURE.md",
        "IMPLEMENTATION_PLAN.md",
        "BENCHMARK_STRATEGY.md",
        "AUTOLOOP_FLYWHEEL.md",
        "OPEN_SOURCE_ATTRIBUTION_PLAN.md",
    ]:
        (docs / name).write_text("# x\n", encoding="utf-8")
    payload = build_watchtower_summary(tmp_path)
    assert payload["docs_ready"]["missing_count"] == 0


def test_adapter_contract_summary_has_official_adapters():
    payload = build_adapter_contract_summary()
    assert payload["official_benchmark_adapters"]


def test_baseline_contract_summary_has_baselines():
    payload = build_baseline_contract_summary()
    assert payload["baselines"]


def test_scorecard_contract_summary_has_fields():
    payload = build_scorecard_contract_summary()
    assert payload["scorecard_fields"]


def test_spark_shadow_contracts_command_runs(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(cli, "_print", lambda payload: captured.setdefault("payload", payload))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "spark-shadow-contracts",
        ],
    )

    cli.main()

    payload = captured["payload"]
    assert payload["ingest"]["runtime_class"] == "SparkShadowIngestAdapter"
    assert payload["replay"]["single_file_shape"]["required_fields"] == ["conversations"]
    assert payload["replay"]["batch_shape"]["default_glob"] == "*.json"


def test_canonical_configs_exist():
    payload = get_canonical_configs()
    assert payload


def test_loader_provider_and_runner_contracts_exist():
    assert build_loader_contract_summary()["loaders"]
    assert build_experiment_contract_summary()["default_systems"]
    assert build_memory_system_contract_summary()["candidate_memory_systems"]
    assert build_provider_contract_summary()["providers"]
    assert build_runner_contract_summary()["supported_baselines"]


def test_candidate_comparison_summary_runs():
    payload = run_candidate_comparison(demo_samples(), provider=get_provider("heuristic_v1"))
    assert payload["systems"]["beam_temporal_atom_router"]["overall"]["total"] >= 1
    assert payload["systems"]["beam_temporal_atom_router"]["audited_overall"]["total"] >= 1
    assert "question_ids" not in payload["systems"]["beam_temporal_atom_router"]["run_manifest"]


def test_demo_product_memory_scorecards_command_runs(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(cli, "_print", lambda payload: captured.setdefault("payload", payload))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "demo-product-memory-scorecards",
        ],
    )

    cli.main()

    payload = captured["payload"]
    assert payload["observational_temporal_memory"]["run_manifest"]["benchmark_name"] == "ProductMemory"
    assert payload["observational_temporal_memory"]["overall"]["total"] == 1266
    assert payload["observational_temporal_memory"]["benchmark_slices"]["product_memory_task"]


def test_demo_spark_shadow_report_command_runs_and_can_write(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}
    output_file = tmp_path / "artifacts" / "spark_shadow_report.json"

    monkeypatch.setattr(cli, "_print", lambda payload: captured.setdefault("payload", payload))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "demo-spark-shadow-report",
            "--write",
            str(output_file),
        ],
    )

    cli.main()

    payload = captured["payload"]
    written = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["report"]["run_count"] == 2
    assert payload["report"]["summary"]["accepted_writes"] == 3
    assert payload["report"]["summary"]["rejected_writes"] == 1
    assert payload["report"]["summary"]["skipped_turns"] == 1
    assert payload["report"]["summary"]["probe_rows"]
    assert written["report"]["conversation_rows"][0]["conversation_id"] == "spark-shadow-demo-1"


def test_run_spark_shadow_report_cli_can_write_report(tmp_path: Path, monkeypatch):
    data_file = tmp_path / "spark_shadow.json"
    output_file = tmp_path / "artifacts" / "spark_shadow_report.json"
    data_file.write_text(
        json.dumps(
            {
                "writable_roles": ["user"],
                "conversations": [
                    {
                        "conversation_id": "shadow-1",
                        "turns": [
                            {
                                "message_id": "m1",
                                "role": "user",
                                "content": "Hello there.",
                                "timestamp": "2025-01-01T09:00:00Z",
                            },
                            {
                                "message_id": "m2",
                                "role": "assistant",
                                "content": "Noted.",
                                "timestamp": "2025-01-01T09:01:00Z",
                            },
                            {
                                "message_id": "m3",
                                "role": "user",
                                "content": "I moved to Dubai.",
                                "timestamp": "2025-03-01T09:00:00Z",
                            },
                        ],
                        "probes": [
                            {
                                "probe_id": "p1",
                                "probe_type": "current_state",
                                "subject": "user",
                                "predicate": "location",
                                "expected_value": "Dubai",
                            },
                            {
                                "probe_id": "p2",
                                "probe_type": "evidence",
                                "subject": "user",
                                "predicate": "location",
                                "expected_value": "Dubai",
                                "min_results": 1,
                            },
                        ],
                    },
                    {
                        "conversation_id": "shadow-2",
                        "turns": [
                            {
                                "message_id": "m1",
                                "role": "user",
                                "content": "I live in London.",
                                "timestamp": "2025-01-01T09:00:00Z",
                            },
                            {
                                "message_id": "m2",
                                "role": "user",
                                "content": "I moved to Abu Dhabi.",
                                "timestamp": "2025-06-01T09:00:00Z",
                            },
                        ],
                        "probes": [
                            {
                                "probe_id": "p3",
                                "probe_type": "historical_state",
                                "subject": "user",
                                "predicate": "location",
                                "as_of": "2025-07-01T00:00:00Z",
                                "expected_value": "Abu Dhabi",
                            }
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "run-spark-shadow-report",
            str(data_file),
            "--write",
            str(output_file),
        ],
    )

    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["report"]["run_count"] == 2
    assert payload["report"]["summary"]["accepted_writes"] == 3
    assert payload["report"]["summary"]["rejected_writes"] == 1
    assert payload["report"]["summary"]["skipped_turns"] == 1
    assert payload["report"]["summary"]["probe_rows"] == [
        {
            "probe_type": "current_state",
            "hits": 1,
            "total": 1,
            "hit_rate": 1.0,
            "expected_matches": 1,
            "expected_total": 1,
            "expected_match_rate": 1.0,
        },
        {
            "probe_type": "evidence",
            "hits": 1,
            "total": 1,
            "hit_rate": 1.0,
            "expected_matches": 1,
            "expected_total": 1,
            "expected_match_rate": 1.0,
        },
        {
            "probe_type": "historical_state",
            "hits": 1,
            "total": 1,
            "hit_rate": 1.0,
            "expected_matches": 1,
            "expected_total": 1,
            "expected_match_rate": 1.0,
        },
    ]
    assert payload["report"]["conversation_rows"][0]["conversation_id"] == "shadow-1"


def test_run_spark_shadow_report_batch_cli_can_aggregate_directory(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "shadow_runs"
    output_file = tmp_path / "artifacts" / "spark_shadow_batch_report.json"
    data_dir.mkdir()

    (data_dir / "slice_a.json").write_text(
        json.dumps(
            {
                "conversations": [
                    {
                        "conversation_id": "shadow-a",
                        "turns": [
                            {
                                "message_id": "m1",
                                "role": "user",
                                "content": "I moved to Dubai.",
                                "timestamp": "2025-03-01T09:00:00Z",
                            }
                        ],
                        "probes": [
                            {
                                "probe_id": "p1",
                                "probe_type": "current_state",
                                "subject": "user",
                                "predicate": "location",
                                "expected_value": "Dubai",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (data_dir / "slice_b.json").write_text(
        json.dumps(
            {
                "conversations": [
                    {
                        "conversation_id": "shadow-b",
                        "turns": [
                            {
                                "message_id": "m1",
                                "role": "user",
                                "content": "Hello there.",
                                "timestamp": "2025-01-01T09:00:00Z",
                            },
                            {
                                "message_id": "m2",
                                "role": "assistant",
                                "content": "Noted.",
                                "timestamp": "2025-01-01T09:01:00Z",
                            },
                            {
                                "message_id": "m3",
                                "role": "user",
                                "content": "I moved to Abu Dhabi.",
                                "timestamp": "2025-06-01T09:00:00Z",
                            },
                        ],
                        "probes": [
                            {
                                "probe_id": "p2",
                                "probe_type": "evidence",
                                "subject": "user",
                                "predicate": "location",
                                "expected_value": "Abu Dhabi",
                                "min_results": 1,
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "run-spark-shadow-report-batch",
            str(data_dir),
            "--write",
            str(output_file),
        ],
    )

    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["report"]["run_count"] == 2
    assert payload["report"]["summary"]["accepted_writes"] == 2
    assert payload["report"]["summary"]["rejected_writes"] == 1
    assert payload["report"]["summary"]["skipped_turns"] == 1
    assert payload["source_files"] == [
        str(data_dir / "slice_a.json"),
        str(data_dir / "slice_b.json"),
    ]
    assert payload["source_reports"][0]["summary"]["accepted_writes"] == 1
    assert payload["source_reports"][1]["summary"]["unsupported_reasons"] == [
        {"reason": "no_structured_memory_extracted", "count": 1}
    ]
    assert payload["report"]["summary"]["probe_rows"] == [
        {
            "probe_type": "current_state",
            "hits": 1,
            "total": 1,
            "hit_rate": 1.0,
            "expected_matches": 1,
            "expected_total": 1,
            "expected_match_rate": 1.0,
        },
        {
            "probe_type": "evidence",
            "hits": 1,
            "total": 1,
            "hit_rate": 1.0,
            "expected_matches": 1,
            "expected_total": 1,
            "expected_match_rate": 1.0,
        },
    ]


def test_run_longmemeval_cli_can_write_scorecard(tmp_path: Path, monkeypatch):
    data_file = tmp_path / "longmemeval.json"
    output_file = tmp_path / "artifacts" / "scorecard.json"
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

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "run-longmemeval-baseline",
            str(data_file),
            "--baseline",
            "observational_temporal_memory",
            "--provider",
            "heuristic_v1",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["overall"]["total"] == 1
    assert payload["predictions"][0]["predicted_answer"].lower() == "dubai"


def test_run_beam_cli_can_write_scorecard(tmp_path: Path, monkeypatch):
    data_file = tmp_path / "beam.json"
    output_file = tmp_path / "artifacts" / "beam_scorecard.json"
    data_file.write_text(
        json.dumps(
            [
                {
                    "sample_id": "beam-1",
                    "sessions": [
                        {
                            "session_id": "beam-session-1",
                            "turns": [
                                {"turn_id": "t1", "speaker": "user", "text": "I live in Dubai."},
                                {"turn_id": "t2", "speaker": "assistant", "text": "Noted."},
                            ],
                        }
                    ],
                    "questions": [
                        {
                            "question_id": "beam-1-q-1",
                            "question": "Where do I live now?",
                            "answer": "Dubai",
                            "category": "episodic_memory",
                            "evidence_session_ids": ["beam-session-1"],
                            "evidence_turn_ids": ["t1"],
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "run-beam-baseline",
            str(data_file),
            "--baseline",
            "observational_temporal_memory",
            "--provider",
            "heuristic_v1",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["overall"]["total"] == 1
    assert payload["run_manifest"]["benchmark_name"] == "BEAM"
    assert payload["benchmark_slices"]["temporal_scope"][0]["label"] == "undated"


def test_run_locomo_cli_question_limit_can_write_scorecard(tmp_path: Path, monkeypatch):
    data_file = tmp_path / "locomo.json"
    output_file = tmp_path / "artifacts" / "locomo_scorecard.json"
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

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "run-locomo-baseline",
            str(data_file),
            "--baseline",
            "full_context",
            "--provider",
            "heuristic_v1",
            "--question-limit",
            "1",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["overall"]["total"] == 1
    assert payload["run_manifest"]["question_count"] == 1


def test_run_locomo_cli_question_offset_can_write_shifted_slice(tmp_path: Path, monkeypatch):
    data_file = tmp_path / "locomo.json"
    output_file = tmp_path / "artifacts" / "locomo_offset_scorecard.json"
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
                            {"speaker": "Alice", "dia_id": "d3", "text": "I like hiking."},
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
                        {
                            "question": "What hobby does Alice like?",
                            "answer": "hiking",
                            "category": "single-hop",
                            "evidence": ["d3"],
                        },
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "run-locomo-baseline",
            str(data_file),
            "--baseline",
            "full_context",
            "--provider",
            "heuristic_v1",
            "--question-offset",
            "1",
            "--question-limit",
            "1",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["overall"]["total"] == 1
    assert payload["run_manifest"]["question_count"] == 1
    assert payload["run_manifest"]["question_ids"] == ["locomo-1-qa-2"]


def test_run_locomo_cli_can_resume_and_checkpoint_progress(tmp_path: Path, monkeypatch):
    data_file = tmp_path / "locomo.json"
    output_file = tmp_path / "artifacts" / "locomo_scorecard.json"
    resume_file = tmp_path / "artifacts" / "resume_scorecard.json"
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
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text(
        json.dumps(
            {
                "predictions": [
                    {
                        "benchmark_name": "LoCoMo",
                        "baseline_name": "full_context",
                        "sample_id": "locomo-1",
                        "question_id": "locomo-1-qa-1",
                        "category": "single-hop",
                        "predicted_answer": "jazz",
                        "expected_answers": ["jazz"],
                        "is_correct": True,
                        "metadata": {"provider_name": "stub", "route": "full_context"},
                    }
                ]
            }
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
    write_calls: list[Path] = []
    original_write_json = cli._write_json

    def tracking_write_json(path: Path, payload: dict) -> None:
        write_calls.append(path)
        original_write_json(path, payload)

    monkeypatch.setattr(cli, "get_provider", lambda _: provider)
    monkeypatch.setattr(cli, "_write_json", tracking_write_json)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "run-locomo-baseline",
            str(data_file),
            "--baseline",
            "full_context",
            "--provider",
            "stub",
            "--question-limit",
            "2",
            "--write",
            str(output_file),
            "--resume-from",
            str(resume_file),
        ],
    )

    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert provider.calls == ["locomo-1-qa-2"]
    assert payload["overall"]["total"] == 2
    assert payload["overall"]["correct"] == 2
    assert len(write_calls) >= 2
