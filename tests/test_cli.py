import importlib
import json
import sys
from pathlib import Path

from domain_chip_memory import cli
from domain_chip_memory import beam_official_eval
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


def test_validate_spark_shadow_replay_command_runs_and_can_write(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}
    data_file = tmp_path / "shadow_replay.json"
    output_file = tmp_path / "artifacts" / "shadow_validation.json"
    data_file.write_text(
        json.dumps(
            {
                "conversations": [
                    {
                        "conversation_id": "conv-1",
                        "turns": [
                            {
                                "message_id": "m1",
                                "role": "user",
                                "content": "I live in Dubai."
                            }
                        ],
                        "probes": [
                            {
                                "probe_id": "p1",
                                "probe_type": "current_state",
                                "subject": "user",
                                "predicate": "location"
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cli, "_print", lambda payload: captured.setdefault("payload", payload))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "validate-spark-shadow-replay",
            str(data_file),
            "--write",
            str(output_file),
        ],
    )

    cli.main()

    payload = captured["payload"]
    written = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["valid"] is True
    assert payload["conversation_count"] == 1
    assert written["file"] == str(data_file)


def test_validate_spark_shadow_replay_batch_command_runs_and_can_write(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}
    data_dir = tmp_path / "shadow_batch"
    output_file = tmp_path / "artifacts" / "shadow_batch_validation.json"
    data_dir.mkdir()
    (data_dir / "slice_a.json").write_text(
        json.dumps(
            {
                "conversations": [
                    {
                        "conversation_id": "conv-a",
                        "turns": [
                            {
                                "message_id": "m1",
                                "role": "user",
                                "content": "I live in Dubai."
                            }
                        ],
                        "probes": [
                            {
                                "probe_id": "p1",
                                "probe_type": "current_state",
                                "subject": "user",
                                "predicate": "location"
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
                        "conversation_id": "",
                        "turns": [
                            {
                                "message_id": "",
                                "role": "user",
                                "content": "Hello."
                            }
                        ],
                        "probes": []
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cli, "_print", lambda payload: captured.setdefault("payload", payload))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "validate-spark-shadow-replay-batch",
            str(data_dir),
            "--write",
            str(output_file),
        ],
    )

    cli.main()

    payload = captured["payload"]
    written = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["valid"] is False
    assert payload["file_count"] == 2
    assert payload["invalid_file_count"] == 1
    assert str(data_dir / "slice_b.json") in payload["invalid_files"]
    assert written["source_files"] == [
        str(data_dir / "slice_a.json"),
        str(data_dir / "slice_b.json"),
    ]


def test_spark_integration_contracts_command_runs(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(cli, "_print", lambda payload: captured.setdefault("payload", payload))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "spark-integration-contracts",
        ],
    )

    cli.main()

    payload = captured["payload"]
    assert payload["sdk_runtime"] == "SparkMemorySDK"
    assert "memory_query_router" in payload["required_builder_systems"]
    assert "Do not persist every turn by default." in payload["system_prompt_template"]


def test_spark_kb_contracts_command_runs(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(cli, "_print", lambda payload: captured.setdefault("payload", payload))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "spark-kb-contracts",
        ],
    )

    cli.main()

    payload = captured["payload"]
    assert payload["layer_name"] == "SparkKnowledgeBase"
    assert "current_state" in payload["required_exports"]
    assert "wiki/index.md" in payload["vault_layout"]["wiki_files"]
    assert "wiki/sources/_index.md" in payload["vault_layout"]["wiki_files"]
    assert "wiki/syntheses/_index.md" in payload["vault_layout"]["wiki_files"]


def test_sdk_maintenance_contracts_command_runs(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(cli, "_print", lambda payload: captured.setdefault("payload", payload))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "sdk-maintenance-contracts",
        ],
    )

    cli.main()

    payload = captured["payload"]
    assert payload["sdk"]["runtime_class"] == "SparkMemorySDK"
    assert payload["replay"]["single_file_shape"]["required_fields"] == ["writes"]
    assert payload["replay"]["maintenance_method"] == "reconsolidate_manual_memory"


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


def test_demo_sdk_maintenance_command_runs_and_can_write(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}
    output_file = tmp_path / "artifacts" / "sdk_maintenance.json"

    monkeypatch.setattr(cli, "_print", lambda payload: captured.setdefault("payload", payload))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "demo-sdk-maintenance",
            "--write",
            str(output_file),
        ],
    )

    cli.main()

    payload = captured["payload"]
    written = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["maintenance"]["manual_observations_before"] == 3
    assert payload["maintenance"]["manual_observations_after"] == 1
    assert payload["maintenance"]["active_deletion_count"] == 1
    assert payload["before"]["current_state"]["memory_role"] == "state_deletion"
    assert payload["after"]["current_state"]["memory_role"] == "state_deletion"
    assert payload["after"]["historical_state"]["value"] == "Dubai"
    assert written["maintenance"]["trace"]["operation"] == "reconsolidate_manual_memory"


def test_demo_spark_kb_command_runs_and_scaffolds_vault(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}
    output_dir = tmp_path / "spark_kb_vault"
    summary_file = tmp_path / "artifacts" / "spark_kb_demo.json"

    monkeypatch.setattr(cli, "_print", lambda payload: captured.setdefault("payload", payload))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "demo-spark-kb",
            str(output_dir),
            "--write",
            str(summary_file),
        ],
    )

    cli.main()

    payload = captured["payload"]
    written = json.loads(summary_file.read_text(encoding="utf-8"))
    assert payload["snapshot"]["runtime_class"] == "SparkMemorySDK"
    assert payload["compile_result"]["current_state_page_count"] >= 1
    assert (output_dir / "CLAUDE.md").exists()
    assert (output_dir / "raw" / "memory-snapshots" / "latest.json").exists()
    assert (output_dir / "wiki" / "index.md").exists()
    assert (output_dir / "wiki" / "current-state" / "_index.md").exists()
    assert (output_dir / "wiki" / "sources" / "_index.md").exists()
    assert (output_dir / "wiki" / "syntheses" / "_index.md").exists()
    assert (output_dir / "wiki" / "sources" / "spark-memory-snapshot-latest.md").exists()
    assert (output_dir / "wiki" / "syntheses" / "runtime-memory-overview.md").exists()
    assert written["compile_result"]["source_page_count"] >= 1
    assert written["compile_result"]["synthesis_page_count"] >= 1
    assert written["compile_result"]["event_page_count"] >= 1


def test_spark_kb_health_check_command_runs_on_demo_vault(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}
    output_dir = tmp_path / "spark_kb_vault"
    health_file = tmp_path / "artifacts" / "spark_kb_health.json"

    monkeypatch.setattr(cli, "_print", lambda payload: captured.setdefault("payload", payload))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "demo-spark-kb",
            str(output_dir),
        ],
    )
    cli.main()

    captured.clear()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "spark-kb-health-check",
            str(output_dir),
            "--write",
            str(health_file),
        ],
    )

    cli.main()

    payload = captured["payload"]
    written = json.loads(health_file.read_text(encoding="utf-8"))
    assert payload["valid"] is True
    assert payload["missing_required_files"] == []
    assert payload["pages_missing_frontmatter"] == []
    assert payload["broken_wikilinks"] == []
    assert "wiki/current-state/user-location.md" not in payload["orphan_pages"]
    assert "wiki/sources/spark-memory-snapshot-latest.md" not in payload["orphan_pages"]
    assert written["trace"]["operation"] == "spark_kb_health_check"


def test_run_sdk_maintenance_report_cli_can_write_report(tmp_path: Path, monkeypatch):
    data_file = tmp_path / "sdk_maintenance.json"
    output_file = tmp_path / "artifacts" / "sdk_maintenance_report.json"
    data_file.write_text(
        json.dumps(
            {
                "writes": [
                    {
                        "write_kind": "observation",
                        "operation": "create",
                        "subject": "user",
                        "predicate": "location",
                        "value": "London",
                        "timestamp": "2025-01-01T09:00:00Z",
                    },
                    {
                        "write_kind": "observation",
                        "operation": "update",
                        "subject": "user",
                        "predicate": "location",
                        "value": "Dubai",
                        "timestamp": "2025-03-01T09:00:00Z",
                    },
                    {
                        "write_kind": "observation",
                        "operation": "delete",
                        "subject": "user",
                        "predicate": "location",
                        "timestamp": "2025-04-01T09:00:00Z",
                    },
                    {
                        "write_kind": "event",
                        "operation": "event",
                        "subject": "user",
                        "predicate": "move",
                        "value": "Dubai",
                        "timestamp": "2025-03-01T09:00:00Z",
                    },
                ],
                "checks": {
                    "current_state": [
                        {"subject": "user", "predicate": "location"}
                    ],
                    "historical_state": [
                        {
                            "subject": "user",
                            "predicate": "location",
                            "as_of": "2025-03-15T00:00:00Z",
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "run-sdk-maintenance-report",
            str(data_file),
            "--write",
            str(output_file),
        ],
    )

    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert len(payload["write_results"]) == 4
    assert payload["write_results"][3]["result"]["trace"]["write_kind"] == "event"
    assert payload["maintenance"]["manual_observations_before"] == 3
    assert payload["maintenance"]["manual_observations_after"] == 1
    assert payload["before"]["current_state"][0]["result"]["memory_role"] == "state_deletion"
    assert payload["after"]["current_state"][0]["result"]["memory_role"] == "state_deletion"
    assert payload["after"]["historical_state"][0]["result"]["value"] == "Dubai"


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


def test_checked_in_spark_shadow_examples_run_via_cli(tmp_path: Path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    single_file = repo_root / "docs" / "examples" / "spark_shadow" / "single_replay.json"
    batch_dir = repo_root / "docs" / "examples" / "spark_shadow" / "batch_replay"
    single_validation_output = tmp_path / "artifacts" / "single_validation.json"
    batch_validation_output = tmp_path / "artifacts" / "batch_validation.json"
    single_output = tmp_path / "artifacts" / "single_report.json"
    batch_output = tmp_path / "artifacts" / "batch_report.json"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "validate-spark-shadow-replay",
            str(single_file),
            "--write",
            str(single_validation_output),
        ],
    )
    cli.main()

    single_validation_payload = json.loads(single_validation_output.read_text(encoding="utf-8"))
    assert single_validation_payload["valid"] is True

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "run-spark-shadow-report",
            str(single_file),
            "--write",
            str(single_output),
        ],
    )
    cli.main()

    single_payload = json.loads(single_output.read_text(encoding="utf-8"))
    assert single_payload["report"]["run_count"] == 2
    assert single_payload["report"]["summary"]["accepted_writes"] == 3

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "validate-spark-shadow-replay-batch",
            str(batch_dir),
            "--write",
            str(batch_validation_output),
        ],
    )
    cli.main()

    batch_validation_payload = json.loads(batch_validation_output.read_text(encoding="utf-8"))
    assert batch_validation_payload["valid"] is True
    assert batch_validation_payload["file_count"] == 2

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "run-spark-shadow-report-batch",
            str(batch_dir),
            "--write",
            str(batch_output),
        ],
    )
    cli.main()

    batch_payload = json.loads(batch_output.read_text(encoding="utf-8"))
    assert batch_payload["report"]["run_count"] == 2
    assert batch_payload["report"]["summary"]["accepted_writes"] == 2
    assert batch_payload["source_files"] == [
        str(batch_dir / "slice_a.json"),
        str(batch_dir / "slice_b.json"),
    ]


def test_checked_in_sdk_maintenance_example_runs_via_cli(tmp_path: Path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    single_file = repo_root / "docs" / "examples" / "sdk_maintenance" / "single_replay.json"
    output_file = tmp_path / "artifacts" / "sdk_maintenance_report.json"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "run-sdk-maintenance-report",
            str(single_file),
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["maintenance"]["manual_observations_before"] == 3
    assert payload["maintenance"]["manual_observations_after"] == 1
    assert payload["maintenance"]["active_deletion_count"] == 1
    assert payload["after"]["historical_state"][0]["result"]["value"] == "Dubai"


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
    assert payload["run_manifest"]["metadata"]["source_modes"] == ["local_pilot"]
    assert payload["run_manifest"]["metadata"]["slice_statuses"] == ["paper_pinned_local_slice"]
    assert payload["benchmark_slices"]["temporal_scope"][0]["label"] == "undated"


def test_run_beam_public_cli_can_write_scorecard(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "beam_public"
    conversation_dir = data_dir / "100K" / "1"
    probing_dir = conversation_dir / "probing_questions"
    output_file = tmp_path / "artifacts" / "beam_public_scorecard.json"
    probing_dir.mkdir(parents=True)
    (conversation_dir / "chat.json").write_text(
        json.dumps(
            [
                {
                    "batch_number": 1,
                    "time_anchor": "March-15-2024",
                    "turns": [
                        [
                            {"role": "user", "id": 1, "content": "I live in Dubai."},
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
                        "question": "Where do I live?",
                        "answer": "Dubai",
                        "source_chat_ids": [1],
                        "rubric": ["Dubai"],
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
            "run-beam-public-baseline",
            str(data_dir),
            "--chat-size",
            "128K",
            "--baseline",
            "observational_temporal_memory",
            "--provider",
            "heuristic_v1",
            "--upstream-commit",
            "abc123",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["overall"]["total"] == 1
    assert payload["run_manifest"]["benchmark_name"] == "BEAM"
    assert payload["run_manifest"]["metadata"]["source_modes"] == ["official_public"]
    assert payload["run_manifest"]["metadata"]["dataset_scales"] == ["128K"]
    assert payload["run_manifest"]["metadata"]["upstream_commits"] == ["abc123"]


def test_run_beam_public_cli_can_write_scorecard_for_stateful_event_reconstruction(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "beam_public"
    conversation_dir = data_dir / "100K" / "1"
    probing_dir = conversation_dir / "probing_questions"
    output_file = tmp_path / "artifacts" / "beam_public_stateful_scorecard.json"
    probing_dir.mkdir(parents=True)
    (conversation_dir / "chat.json").write_text(
        json.dumps(
            [
                {
                    "batch_number": 1,
                    "time_anchor": "March-15-2024",
                    "turns": [
                        [
                            {"role": "user", "id": 1, "content": "I moved to Dubai in February and now work from JLT."},
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
                        "question": "Where do I work now?",
                        "answer": "JLT",
                        "source_chat_ids": [1],
                        "rubric": ["JLT"],
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
            "run-beam-public-baseline",
            str(data_dir),
            "--chat-size",
            "128K",
            "--baseline",
            "stateful_event_reconstruction",
            "--provider",
            "heuristic_v1",
            "--upstream-commit",
            "abc123",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["overall"]["total"] == 1
    assert payload["run_manifest"]["baseline_name"] == "stateful_event_reconstruction"
    assert payload["run_manifest"]["metadata"]["source_modes"] == ["official_public"]
    assert payload["run_manifest"]["metadata"]["dataset_scales"] == ["128K"]
    assert payload["run_manifest"]["metadata"]["upstream_commits"] == ["abc123"]


def test_run_beam_public_cli_can_write_scorecard_for_summary_synthesis_memory(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "beam_public"
    conversation_dir = data_dir / "100K" / "1"
    probing_dir = conversation_dir / "probing_questions"
    output_file = tmp_path / "artifacts" / "beam_public_summary_synthesis_scorecard.json"
    probing_dir.mkdir(parents=True)
    (conversation_dir / "chat.json").write_text(
        json.dumps(
            [
                {
                    "batch_number": 1,
                    "time_anchor": "March-15-2024",
                    "turns": [
                        [
                            {"role": "user", "id": 1, "content": "My API key daily quota was updated to 1,200 calls per day to support testing."},
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
                "knowledge_update": [
                    {
                        "question": "What is the daily call quota for the API key used in my application?",
                        "answer": "1,200 calls per day",
                        "source_chat_ids": [1],
                        "rubric": ["1,200 calls per day"],
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
            "run-beam-public-baseline",
            str(data_dir),
            "--chat-size",
            "128K",
            "--baseline",
            "summary_synthesis_memory",
            "--provider",
            "heuristic_v1",
            "--upstream-commit",
            "abc123",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["overall"]["total"] == 1
    assert payload["run_manifest"]["baseline_name"] == "summary_synthesis_memory"
    assert payload["run_manifest"]["metadata"]["source_modes"] == ["official_public"]
    assert payload["run_manifest"]["metadata"]["dataset_scales"] == ["128K"]
    assert payload["run_manifest"]["metadata"]["upstream_commits"] == ["abc123"]


def test_run_beam_public_cli_summary_synthesis_prefers_contradiction_claims(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "beam_public"
    conversation_dir = data_dir / "100K" / "1"
    probing_dir = conversation_dir / "probing_questions"
    output_file = tmp_path / "artifacts" / "beam_public_summary_contradiction_scorecard.json"
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
                                "content": "I've never written any Flask routes or handled HTTP requests in this project.",
                            },
                            {"role": "assistant", "id": 2, "content": "Noted."},
                        ],
                        [
                            {
                                "role": "user",
                                "id": 3,
                                "content": "Can you help me review Flask routing tutorials and session management examples?",
                            },
                            {"role": "assistant", "id": 4, "content": "Sure."},
                        ],
                        [
                            {
                                "role": "user",
                                "id": 5,
                                "content": "I'm trying to implement the basic homepage route with Flask, and I've managed to return static HTML already.",
                            },
                            {"role": "assistant", "id": 6, "content": "Nice progress."},
                        ],
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
                        "answer": "Please clarify",
                        "source_chat_ids": [1, 3, 5],
                        "rubric": ["implementing a basic homepage route with Flask"],
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
            "run-beam-public-baseline",
            str(data_dir),
            "--chat-size",
            "128K",
            "--baseline",
            "summary_synthesis_memory",
            "--provider",
            "heuristic_v1",
            "--upstream-commit",
            "abc123",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    answer = payload["predictions"][0]["predicted_answer"].lower()
    assert "homepage route with flask" in answer
    assert "tutorials" not in answer


def test_run_beam_public_cli_can_write_scorecard_for_contradiction_aware_summary_synthesis_memory(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "beam_public"
    conversation_dir = data_dir / "100K" / "1"
    probing_dir = conversation_dir / "probing_questions"
    output_file = tmp_path / "artifacts" / "beam_public_contradiction_summary_synthesis_scorecard.json"
    probing_dir.mkdir(parents=True)
    (conversation_dir / "chat.json").write_text(
        json.dumps(
            [
                {
                    "batch_number": 1,
                    "time_anchor": "March-15-2024",
                    "turns": [
                        [
                            {"role": "user", "id": 1, "content": "I have never written any Flask routes or handled HTTP requests in this project."},
                            {"role": "assistant", "id": 2, "content": "Noted."},
                        ],
                        [
                            {"role": "user", "id": 3, "content": "I implemented a basic homepage route with Flask to handle HTTP requests."},
                            {"role": "assistant", "id": 4, "content": "Noted."},
                        ],
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
                        "source_chat_ids": [1, 3],
                        "rubric": ["there is contradictory information"],
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
            "run-beam-public-baseline",
            str(data_dir),
            "--chat-size",
            "128K",
            "--baseline",
            "contradiction_aware_summary_synthesis_memory",
            "--provider",
            "heuristic_v1",
            "--upstream-commit",
            "abc123",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["overall"]["total"] == 1
    assert payload["run_manifest"]["baseline_name"] == "contradiction_aware_summary_synthesis_memory"
    assert payload["run_manifest"]["metadata"]["source_modes"] == ["official_public"]
    assert payload["run_manifest"]["metadata"]["dataset_scales"] == ["128K"]
    assert payload["run_manifest"]["metadata"]["upstream_commits"] == ["abc123"]


def test_run_beam_public_cli_can_write_scorecard_for_typed_state_update_memory(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "beam_public"
    conversation_dir = data_dir / "100K" / "1"
    probing_dir = conversation_dir / "probing_questions"
    output_file = tmp_path / "artifacts" / "beam_public_typed_state_scorecard.json"
    probing_dir.mkdir(parents=True)
    (conversation_dir / "chat.json").write_text(
        json.dumps(
            [
                {
                    "batch_number": 1,
                    "time_anchor": "March-15-2024",
                    "turns": [
                        [
                            {"role": "user", "id": 1, "content": "I moved from Sharjah to Dubai and now work from JLT."},
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
                        "question": "Where do I work now?",
                        "answer": "JLT",
                        "source_chat_ids": [1],
                        "rubric": ["JLT"],
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
            "run-beam-public-baseline",
            str(data_dir),
            "--chat-size",
            "128K",
            "--baseline",
            "typed_state_update_memory",
            "--provider",
            "heuristic_v1",
            "--upstream-commit",
            "abc123",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["overall"]["total"] == 1
    assert payload["run_manifest"]["baseline_name"] == "typed_state_update_memory"
    assert payload["run_manifest"]["metadata"]["source_modes"] == ["official_public"]
    assert payload["run_manifest"]["metadata"]["dataset_scales"] == ["128K"]
    assert payload["run_manifest"]["metadata"]["upstream_commits"] == ["abc123"]


def test_run_beam_public_cli_can_write_scorecard_for_contradiction_aware_profile_memory(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "beam_public"
    conversation_dir = data_dir / "100K" / "1"
    probing_dir = conversation_dir / "probing_questions"
    output_file = tmp_path / "artifacts" / "beam_public_contradiction_profile_scorecard.json"
    probing_dir.mkdir(parents=True)
    (conversation_dir / "chat.json").write_text(
        json.dumps(
            [
                {
                    "batch_number": 1,
                    "time_anchor": "March-15-2024",
                    "turns": [
                        [
                            {"role": "user", "id": 1, "content": "I have never written any Flask routes in this project."},
                            {"role": "assistant", "id": 2, "content": "Noted."},
                        ],
                        [
                            {"role": "user", "id": 3, "content": "I implemented a basic homepage route with Flask to handle requests."},
                            {"role": "assistant", "id": 4, "content": "Noted."},
                        ],
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
                        "answer": "Please clarify",
                        "source_chat_ids": [1, 3],
                        "rubric": ["clarify"],
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
            "run-beam-public-baseline",
            str(data_dir),
            "--chat-size",
            "128K",
            "--baseline",
            "contradiction_aware_profile_memory",
            "--provider",
            "heuristic_v1",
            "--upstream-commit",
            "abc123",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["overall"]["total"] == 1
    assert payload["run_manifest"]["baseline_name"] == "contradiction_aware_profile_memory"
    assert payload["run_manifest"]["metadata"]["source_modes"] == ["official_public"]
    assert payload["run_manifest"]["metadata"]["dataset_scales"] == ["128K"]
    assert payload["run_manifest"]["metadata"]["upstream_commits"] == ["abc123"]


def test_run_beam_public_cli_handles_null_batch_anchor_with_official_date_format(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "beam_public"
    conversation_dir = data_dir / "100K" / "1"
    probing_dir = conversation_dir / "probing_questions"
    output_file = tmp_path / "artifacts" / "beam_public_temporal_scorecard.json"
    export_manifest_file = tmp_path / "artifacts" / "beam_public_export_manifest.json"
    export_dir = tmp_path / "beam_results"
    probing_dir.mkdir(parents=True)
    (conversation_dir / "chat.json").write_text(
        json.dumps(
            [
                {
                    "batch_number": 1,
                    "time_anchor": None,
                    "turns": [
                        [
                            {
                                "role": "user",
                                "id": 1,
                                "time_anchor": "April-15-2024",
                                "content": "My first sprint ends today.",
                            },
                            {
                                "role": "assistant",
                                "id": 2,
                                "time_anchor": "April-15-2024",
                                "content": "Nice, that wraps the sprint on schedule.",
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
                "information_extraction": [
                    {
                        "question": "When does my first sprint end?",
                        "answer": "15 April 2024",
                        "source_chat_ids": [1],
                        "rubric": ["15 April 2024"],
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
            "run-beam-public-baseline",
            str(data_dir),
            "--chat-size",
            "128K",
            "--baseline",
            "observational_temporal_memory",
            "--provider",
            "heuristic_v1",
            "--upstream-commit",
            "abc123",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["overall"]["total"] == 1
    assert payload["predictions"][0]["predicted_answer"] == "15 April 2024"
    assert payload["predictions"][0]["question"] == "When does my first sprint end?"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "export-beam-public-answers",
            str(output_file),
            str(export_dir),
            "--write",
            str(export_manifest_file),
        ],
    )
    cli.main()

    export_manifest = json.loads(export_manifest_file.read_text(encoding="utf-8"))
    exported = json.loads((export_dir / "100K" / "1" / "domain_chip_memory_answers.json").read_text(encoding="utf-8"))
    assert export_manifest["conversation_count"] == 1
    assert exported["information_extraction"][0]["question"] == "When does my first sprint end?"


def test_export_beam_public_answers_cli_writes_upstream_shape(tmp_path: Path, monkeypatch):
    scorecard_file = tmp_path / "beam_scorecard.json"
    output_dir = tmp_path / "beam_results"
    manifest_file = tmp_path / "artifacts" / "beam_export_manifest.json"
    scorecard_file.write_text(
        json.dumps(
            {
                "run_manifest": {
                    "benchmark_name": "BEAM",
                    "metadata": {
                        "source_modes": ["official_public"],
                        "dataset_scales": ["128K"],
                    },
                },
                "predictions": [
                    {
                        "sample_id": "beam-128k-1",
                        "question_id": "1:information_extraction:1",
                        "question": "Where do I live?",
                        "category": "information_extraction",
                        "predicted_answer": "Dubai",
                    },
                    {
                        "sample_id": "beam-128k-1",
                        "question_id": "1:abstention:2",
                        "question": "What is my favorite food?",
                        "category": "abstention",
                        "predicted_answer": "Based on the provided chat, there is no information related to your favorite food.",
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
            "export-beam-public-answers",
            str(scorecard_file),
            str(output_dir),
            "--result-file-name",
            "answers.json",
            "--write",
            str(manifest_file),
        ],
    )
    cli.main()

    manifest_payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    exported_payload = json.loads((output_dir / "100K" / "1" / "answers.json").read_text(encoding="utf-8"))
    assert manifest_payload["conversation_count"] == 1
    assert exported_payload["information_extraction"][0]["llm_response"] == "Dubai"
    assert exported_payload["abstention"][0]["question"] == "What is my favorite food?"


def test_summarize_beam_evaluation_cli_writes_compact_summary(tmp_path: Path, monkeypatch):
    evaluation_file = tmp_path / "evaluation.json"
    output_file = tmp_path / "artifacts" / "beam_eval_summary.json"
    evaluation_file.write_text(
        json.dumps(
            {
                "information_extraction": [
                    {"llm_judge_score": 1.0},
                    {"llm_judge_score": 0.5},
                ],
                "event_ordering": [
                    {"tau_norm": 0.75, "llm_judge_score": 1.0},
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
            "summarize-beam-evaluation",
            str(evaluation_file),
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["benchmark_name"] == "BEAM"
    assert payload["overall_average"] == 0.75
    assert payload["categories"][0]["category"] == "event_ordering"
    assert payload["categories"][1]["average_score"] == 0.75


def test_run_beam_official_evaluation_cli_validates_and_writes_manifest(tmp_path: Path, monkeypatch):
    upstream_repo = tmp_path / "beam_repo"
    answers_dir = tmp_path / "beam_results"
    output_file = tmp_path / "artifacts" / "beam_official_eval_manifest.json"

    (upstream_repo / "src" / "evaluation").mkdir(parents=True)
    (upstream_repo / "src" / "evaluation" / "run_evaluation.py").write_text("print('ok')\n", encoding="utf-8")
    (upstream_repo / "src" / "llms_config.json").write_text(json.dumps({"gpt": {"api_key": "test"}}), encoding="utf-8")
    (upstream_repo / "chats" / "100K" / "1" / "probing_questions").mkdir(parents=True)
    (upstream_repo / "chats" / "100K" / "1" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps({"information_extraction": []}),
        encoding="utf-8",
    )
    (answers_dir / "100K" / "1").mkdir(parents=True)
    (answers_dir / "100K" / "1" / "domain_chip_memory_answers.json").write_text(
        json.dumps({"information_extraction": []}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "run-beam-official-evaluation",
            str(upstream_repo),
            str(answers_dir),
            "--chat-size",
            "128K",
            "--judge-provider",
            "official_openai",
            "--dry-run",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["benchmark_name"] == "BEAM"
    assert payload["status"] == "validated"
    assert payload["official_chat_size_dir"] == "100K"
    assert payload["conversation_ids"] == ["1"]
    assert payload["command"][1] == "-m"
    assert payload["command"][2] == "src.evaluation.run_evaluation"
    assert payload["input_directory"] == str((answers_dir / "100K").resolve())


def test_summarize_beam_official_evaluation_files_aggregates_across_conversations(tmp_path: Path):
    evaluation_one = tmp_path / "evaluation-one.json"
    evaluation_two = tmp_path / "evaluation-two.json"
    evaluation_one.write_text(
        json.dumps(
            {
                "information_extraction": [
                    {"llm_judge_score": 1.0},
                    {"llm_judge_score": 0.5},
                ],
                "event_ordering": [
                    {"tau_norm": 0.5},
                ],
            }
        ),
        encoding="utf-8",
    )
    evaluation_two.write_text(
        json.dumps(
            {
                "information_extraction": [
                    {"llm_judge_score": 0.0},
                ],
                "event_ordering": [
                    {"tau_norm": 1.0},
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = beam_official_eval.summarize_beam_official_evaluation_files([evaluation_one, evaluation_two])

    assert payload["evaluation_file_count"] == 2
    assert payload["overall_average"] == 0.625
    assert payload["categories"][0]["category"] == "event_ordering"
    assert payload["categories"][0]["average_score"] == 0.75
    assert payload["categories"][1]["question_count"] == 3
    assert payload["categories"][1]["average_score"] == 0.5


def test_run_beam_official_evaluation_cli_invokes_upstream_subprocess(tmp_path: Path, monkeypatch):
    upstream_repo = tmp_path / "beam_repo"
    answers_dir = tmp_path / "beam_results"
    output_file = tmp_path / "artifacts" / "beam_official_eval_result.json"

    (upstream_repo / "src" / "evaluation").mkdir(parents=True)
    (upstream_repo / "src" / "evaluation" / "run_evaluation.py").write_text("print('ok')\n", encoding="utf-8")
    (upstream_repo / "src" / "llms_config.json").write_text(json.dumps({"gpt": {"api_key": "test"}}), encoding="utf-8")
    (upstream_repo / "chats" / "100K" / "1" / "probing_questions").mkdir(parents=True)
    (upstream_repo / "chats" / "100K" / "1" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps({"information_extraction": []}),
        encoding="utf-8",
    )
    (answers_dir / "100K" / "1").mkdir(parents=True)
    answer_file = answers_dir / "100K" / "1" / "custom_answers.json"
    answer_file.write_text(
        json.dumps({"information_extraction": [{"question": "x", "llm_response": "y"}]}),
        encoding="utf-8",
    )

    class FakeCompletedProcess:
        def __init__(self):
            self.returncode = 0
            self.stdout = "Question Type: information_extraction\nQuestion Index: 0\n"
            self.stderr = ""

    def fake_run(command, *, cwd, capture_output, text, check):
        assert command[0] == "python-custom"
        assert command[1] == "-m"
        assert command[2] == "src.evaluation.run_evaluation"
        assert command[4] == str((answers_dir / "100K").resolve())
        assert command[-1] == "custom_answers.json"
        assert cwd == str(upstream_repo.resolve())
        assert capture_output is True
        assert text is True
        assert check is False
        (answers_dir / "100K" / "1" / "evaluation-custom_answers.json").write_text(
            json.dumps({"information_extraction": [{"llm_judge_score": 1.0}]}),
            encoding="utf-8",
        )
        return FakeCompletedProcess()

    monkeypatch.setattr(beam_official_eval.subprocess, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "run-beam-official-evaluation",
            str(upstream_repo),
            str(answers_dir),
            "--chat-size",
            "128K",
            "--result-file-name",
            "custom_answers.json",
            "--python-executable",
            "python-custom",
            "--judge-provider",
            "official_openai",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert payload["exit_code"] == 0
    assert payload["evaluation_files"] == [str(answers_dir / "100K" / "1" / "evaluation-custom_answers.json")]
    assert "information_extraction" in payload["stdout_tail"][0]


def test_run_beam_official_evaluation_cli_fails_when_upstream_writes_no_evaluation_files(tmp_path: Path, monkeypatch):
    upstream_repo = tmp_path / "beam_repo"
    answers_dir = tmp_path / "beam_results"
    output_file = tmp_path / "artifacts" / "beam_official_eval_result.json"

    (upstream_repo / "src" / "evaluation").mkdir(parents=True)
    (upstream_repo / "src" / "evaluation" / "run_evaluation.py").write_text("print('ok')\n", encoding="utf-8")
    (upstream_repo / "src" / "llms_config.json").write_text(json.dumps({"gpt": {"api_key": "test"}}), encoding="utf-8")
    (upstream_repo / "chats" / "100K" / "1" / "probing_questions").mkdir(parents=True)
    (upstream_repo / "chats" / "100K" / "1" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps({"information_extraction": []}),
        encoding="utf-8",
    )
    (answers_dir / "100K" / "1").mkdir(parents=True)
    (answers_dir / "100K" / "1" / "custom_answers.json").write_text(
        json.dumps({"information_extraction": [{"question": "x", "llm_response": "y"}]}),
        encoding="utf-8",
    )

    class FakeCompletedProcess:
        def __init__(self):
            self.returncode = 0
            self.stdout = "Error while processing a directory: quota"
            self.stderr = ""

    def fake_run(command, *, cwd, capture_output, text, check):
        return FakeCompletedProcess()

    monkeypatch.setattr(beam_official_eval.subprocess, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "run-beam-official-evaluation",
            str(upstream_repo),
            str(answers_dir),
            "--chat-size",
            "128K",
            "--result-file-name",
            "custom_answers.json",
            "--judge-provider",
            "official_openai",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["exit_code"] == 0
    assert payload["evaluation_files"] == []


def test_run_beam_official_evaluation_cli_supports_minimax_judge_override(tmp_path: Path, monkeypatch):
    upstream_repo = tmp_path / "beam_repo"
    answers_dir = tmp_path / "beam_results"
    output_file = tmp_path / "artifacts" / "beam_official_eval_minimax_result.json"

    (upstream_repo / "src" / "evaluation").mkdir(parents=True)
    (upstream_repo / "src" / "evaluation" / "run_evaluation.py").write_text("print('ok')\n", encoding="utf-8")
    (upstream_repo / "src" / "llms_config.json").write_text(json.dumps({"gpt": {"api_key": "test"}}), encoding="utf-8")
    (upstream_repo / "chats" / "100K" / "1" / "probing_questions").mkdir(parents=True)
    (upstream_repo / "chats" / "100K" / "1" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps({"information_extraction": []}),
        encoding="utf-8",
    )
    (answers_dir / "100K" / "1").mkdir(parents=True)
    answer_file = answers_dir / "100K" / "1" / "custom_answers.json"
    answer_file.write_text(
        json.dumps({"information_extraction": [{"question": "x", "llm_response": "y"}]}),
        encoding="utf-8",
    )

    def fake_run_openai_compatible_upstream_evaluation(**kwargs):
        assert kwargs["judge_config"]["provider"] == "minimax"
        assert kwargs["judge_config"]["model"] == "MiniMax-M2.7"
        assert kwargs["judge_config"]["api_key_env"] == "MINIMAX_API_KEY"
        assert kwargs["judge_config"]["comparability"] == "alternate_openai_compatible_judge_not_exact_official"
        evaluation_path = answers_dir / "100K" / "1" / "evaluation-custom_answers.json"
        evaluation_path.write_text(
            json.dumps({"information_extraction": [{"llm_judge_score": 1.0}]}),
            encoding="utf-8",
        )
        return {
            "exit_code": 0,
            "stdout_tail": ["ok"],
            "stderr_tail": [],
            "evaluation_files": [str(evaluation_path)],
        }

    monkeypatch.setattr(
        beam_official_eval,
        "_run_openai_compatible_upstream_evaluation",
        fake_run_openai_compatible_upstream_evaluation,
    )
    monkeypatch.setenv("MINIMAX_API_KEY", "minimax-test-key")
    monkeypatch.setenv("MINIMAX_MODEL", "MiniMax-M2.7")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "run-beam-official-evaluation",
            str(upstream_repo),
            str(answers_dir),
            "--chat-size",
            "128K",
            "--result-file-name",
            "custom_answers.json",
            "--judge-provider",
            "minimax",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert payload["judge_config"]["provider"] == "minimax"
    assert payload["judge_config"]["model"] == "MiniMax-M2.7"
    assert payload["evaluation_files"] == [str(answers_dir / "100K" / "1" / "evaluation-custom_answers.json")]
    assert payload["aggregate_summary"]["overall_average"] == 1.0


def test_run_beam_official_evaluation_cli_defaults_to_minimax(tmp_path: Path, monkeypatch):
    upstream_repo = tmp_path / "beam_repo"
    answers_dir = tmp_path / "beam_results"
    output_file = tmp_path / "artifacts" / "beam_official_eval_minimax_default_result.json"

    (upstream_repo / "src" / "evaluation").mkdir(parents=True)
    (upstream_repo / "src" / "evaluation" / "run_evaluation.py").write_text("print('ok')\n", encoding="utf-8")
    (upstream_repo / "src" / "llms_config.json").write_text(json.dumps({"gpt": {"api_key": "test"}}), encoding="utf-8")
    (upstream_repo / "chats" / "100K" / "1" / "probing_questions").mkdir(parents=True)
    (upstream_repo / "chats" / "100K" / "1" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps({"information_extraction": []}),
        encoding="utf-8",
    )
    (answers_dir / "100K" / "1").mkdir(parents=True)
    answer_file = answers_dir / "100K" / "1" / "custom_answers.json"
    answer_file.write_text(
        json.dumps({"information_extraction": [{"question": "x", "llm_response": "y"}]}),
        encoding="utf-8",
    )

    def fake_run_openai_compatible_upstream_evaluation(**kwargs):
        assert kwargs["judge_config"]["provider"] == "minimax"
        assert kwargs["judge_config"]["model"] == "MiniMax-M2.7"
        evaluation_path = answers_dir / "100K" / "1" / "evaluation-custom_answers.json"
        evaluation_path.write_text(
            json.dumps({"information_extraction": [{"llm_judge_score": 1.0}]}),
            encoding="utf-8",
        )
        return {
            "exit_code": 0,
            "stdout_tail": ["ok"],
            "stderr_tail": [],
            "evaluation_files": [str(evaluation_path)],
        }

    monkeypatch.setattr(
        beam_official_eval,
        "_run_openai_compatible_upstream_evaluation",
        fake_run_openai_compatible_upstream_evaluation,
    )
    monkeypatch.setenv("MINIMAX_API_KEY", "minimax-test-key")
    monkeypatch.setenv("MINIMAX_MODEL", "MiniMax-M2.7")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "run-beam-official-evaluation",
            str(upstream_repo),
            str(answers_dir),
            "--chat-size",
            "128K",
            "--result-file-name",
            "custom_answers.json",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert payload["judge_config"]["provider"] == "minimax"
    assert payload["judge_config"]["model"] == "MiniMax-M2.7"
    assert payload["aggregate_summary"]["overall_average"] == 1.0


def test_run_openai_compatible_upstream_evaluation_waits_for_worker_exit_before_trusting_incremental_outputs(
    tmp_path: Path,
    monkeypatch,
):
    upstream_repo = tmp_path / "beam_repo"
    answers_dir = tmp_path / "beam_results" / "100K" / "1"
    answers_dir.mkdir(parents=True)
    result_file_name = "custom_answers.json"
    (answers_dir / result_file_name).write_text(json.dumps({"information_extraction": []}), encoding="utf-8")
    evaluation_path = answers_dir / f"evaluation-{result_file_name}"

    class FakeQueue:
        def __init__(self):
            self._items = []

        def put(self, item):
            self._items.append(item)

        def empty(self):
            return not self._items

        def get(self):
            return self._items.pop(0)

    fake_queue = FakeQueue()
    process_holder = {}

    class FakeProcess:
        def __init__(self):
            self.exitcode = 0
            self._poll_count = 0
            self.terminated = False

        def start(self):
            return None

        def is_alive(self):
            self._poll_count += 1
            if self._poll_count == 1:
                evaluation_path.write_text(
                    json.dumps({"abstention": [{"llm_judge_score": 1.0}]}),
                    encoding="utf-8",
                )
                return True
            if self._poll_count == 2:
                evaluation_path.write_text(
                    json.dumps(
                        {
                            "abstention": [{"llm_judge_score": 1.0}],
                            "information_extraction": [{"llm_judge_score": 0.5}],
                        }
                    ),
                    encoding="utf-8",
                )
                fake_queue.put(
                    {
                        "exit_code": 0,
                        "stdout_tail": ["worker finished"],
                        "stderr_tail": [],
                    }
                )
                return False
            return False

        def join(self, timeout=None):
            return None

        def terminate(self):
            self.terminated = True

    class FakeContext:
        def Queue(self):
            return fake_queue

        def Process(self, target, args):
            process = FakeProcess()
            process_holder["process"] = process
            return process

    monkeypatch.setattr(beam_official_eval.multiprocessing, "get_context", lambda _: FakeContext())
    monkeypatch.setattr(beam_official_eval.time, "sleep", lambda _: None)

    result = beam_official_eval._run_openai_compatible_upstream_evaluation(
        upstream_repo_path=upstream_repo,
        answers_scale_dir=answers_dir.parent,
        official_scale_dir="100K",
        start_index=0,
        end_index=1,
        max_workers=10,
        result_file_name=result_file_name,
        judge_config={
            "provider": "minimax",
            "model": "MiniMax-M2.7",
            "base_url": "https://api.minimax.io/v1",
            "api_key": "test-key",
        },
    )

    assert result["exit_code"] == 0
    assert result["evaluation_files"] == [str(evaluation_path)]
    assert process_holder["process"].terminated is False
    assert "information_extraction" in json.loads(evaluation_path.read_text(encoding="utf-8"))


def test_run_openai_compatible_upstream_evaluation_terminates_lingering_worker_after_payload_and_outputs(
    tmp_path: Path,
    monkeypatch,
):
    upstream_repo = tmp_path / "beam_repo"
    answers_dir = tmp_path / "beam_results" / "100K" / "1"
    answers_dir.mkdir(parents=True)
    result_file_name = "custom_answers.json"
    (answers_dir / result_file_name).write_text(json.dumps({"information_extraction": []}), encoding="utf-8")
    evaluation_path = answers_dir / f"evaluation-{result_file_name}"

    class FakeQueue:
        def __init__(self):
            self._items = []

        def put(self, item):
            self._items.append(item)

        def empty(self):
            return not self._items

        def get(self):
            return self._items.pop(0)

    fake_queue = FakeQueue()
    process_holder = {}

    class FakeProcess:
        def __init__(self):
            self.exitcode = 0
            self._poll_count = 0
            self.terminated = False

        def start(self):
            return None

        def is_alive(self):
            self._poll_count += 1
            if self._poll_count == 1:
                evaluation_path.write_text(
                    json.dumps({"abstention": [{"llm_judge_score": 1.0}]}),
                    encoding="utf-8",
                )
                return True
            if self._poll_count == 2:
                evaluation_path.write_text(
                    json.dumps(
                        {
                            "abstention": [{"llm_judge_score": 1.0}],
                            "information_extraction": [{"llm_judge_score": 0.5}],
                        }
                    ),
                    encoding="utf-8",
                )
                fake_queue.put(
                    {
                        "exit_code": 0,
                        "stdout_tail": ["worker finished"],
                        "stderr_tail": [],
                    }
                )
            return not self.terminated

        def join(self, timeout=None):
            return None

        def terminate(self):
            self.terminated = True

    class FakeContext:
        def Queue(self):
            return fake_queue

        def Process(self, target, args):
            process = FakeProcess()
            process_holder["process"] = process
            return process

    monkeypatch.setattr(beam_official_eval.multiprocessing, "get_context", lambda _: FakeContext())
    monkeypatch.setattr(beam_official_eval.time, "sleep", lambda _: None)

    result = beam_official_eval._run_openai_compatible_upstream_evaluation(
        upstream_repo_path=upstream_repo,
        answers_scale_dir=answers_dir.parent,
        official_scale_dir="100K",
        start_index=0,
        end_index=1,
        max_workers=10,
        result_file_name=result_file_name,
        judge_config={
            "provider": "minimax",
            "model": "MiniMax-M2.7",
            "base_url": "https://api.minimax.io/v1",
            "api_key": "test-key",
        },
    )

    assert result["exit_code"] == 0
    assert result["evaluation_files"] == [str(evaluation_path)]
    assert process_holder["process"].terminated is True
    assert any("terminating lingering worker" in line for line in result["stdout_tail"])


def test_run_openai_compatible_evaluation_worker_sets_request_timeout_and_retries(
    tmp_path: Path,
    monkeypatch,
):
    upstream_repo = tmp_path / "beam_repo"
    answers_scale_dir = tmp_path / "beam_results" / "500K"
    conversation_dir = answers_scale_dir / "1"
    (upstream_repo / "chats" / "500K" / "1" / "probing_questions").mkdir(parents=True)
    conversation_dir.mkdir(parents=True)
    (upstream_repo / "chats" / "500K" / "1" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps({"information_extraction": []}),
        encoding="utf-8",
    )
    (conversation_dir / "custom_answers.json").write_text(
        json.dumps({"information_extraction": []}),
        encoding="utf-8",
    )

    class FakeQueue:
        def __init__(self):
            self._items = []

        def put(self, item):
            self._items.append(item)

        def get(self):
            return self._items.pop(0)

    fake_queue = FakeQueue()
    captured_chat_openai_kwargs = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured_chat_openai_kwargs.update(kwargs)

    class FakeComputeMetricsModule:
        SentenceTransformer = object

        def initialize_models(self):
            return None

        @staticmethod
        def evaluate_information_extraction(**kwargs):
            return {"llm_judge_score": 1.0, "llm_judge_responses": []}

    class FakeRunEvaluationModule:
        initialize_models = None

        @staticmethod
        def get_rubric(**kwargs):
            return []

    original_import_module = importlib.import_module

    def fake_import_module(name: str):
        if name == "src.evaluation.compute_metrics":
            return FakeComputeMetricsModule()
        if name == "src.evaluation.run_evaluation":
            return FakeRunEvaluationModule()
        return original_import_module(name)

    monkeypatch.setattr(beam_official_eval, "ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    beam_official_eval._run_openai_compatible_evaluation_worker(
        upstream_repo_dir=str(upstream_repo),
        answers_scale_dir=str(answers_scale_dir),
        official_scale_dir="500K",
        conversation_ids=["1"],
        result_file_name="custom_answers.json",
        judge_config={
            "provider": "minimax",
            "model": "MiniMax-M2.7",
            "base_url": "https://api.minimax.io/v1",
            "api_key": "test-key",
        },
        result_queue=fake_queue,
    )

    worker_payload = fake_queue.get()
    assert worker_payload["exit_code"] == 0
    assert captured_chat_openai_kwargs["request_timeout"] == 60
    assert captured_chat_openai_kwargs["max_retries"] == 2


def test_resume_openai_compatible_single_conversation_evaluation_skips_completed_categories(
    tmp_path: Path,
):
    probing_questions_path = tmp_path / "probing_questions.json"
    answers_path = tmp_path / "answers.json"
    output_path = tmp_path / "evaluation-answers.json"

    probing_questions_path.write_text(
        json.dumps(
            {
                "abstention": [{"rubric": ["no agenda info"]}],
                "information_extraction": [{"rubric": ["march 1"]}],
            }
        ),
        encoding="utf-8",
    )
    answers_path.write_text(
        json.dumps(
            {
                "abstention": [{"question": "q1", "llm_response": "a1"}],
                "information_extraction": [{"question": "q2", "llm_response": "a2"}],
            }
        ),
        encoding="utf-8",
    )
    output_path.write_text(
        json.dumps({"abstention": [{"llm_judge_score": 1.0, "llm_judge_responses": []}]}),
        encoding="utf-8",
    )

    class FakeComputeMetricsModule:
        @staticmethod
        def evaluate_abstention(**kwargs):
            raise AssertionError("completed abstention category should have been skipped")

        @staticmethod
        def evaluate_information_extraction(**kwargs):
            return {"llm_judge_score": 0.5, "llm_judge_responses": [{"score": 0.5}]}

    class FakeRunEvaluationModule:
        @staticmethod
        def get_rubric(**kwargs):
            if kwargs["key"] == "information_extraction":
                return ["march 1"]
            return ["no agenda info"]

    beam_official_eval._resume_openai_compatible_single_conversation_evaluation(
        probing_questions_address=probing_questions_path,
        answers_file=answers_path,
        output_file=output_path,
        model=object(),
        compute_metrics_module=FakeComputeMetricsModule(),
        run_evaluation_module=FakeRunEvaluationModule(),
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert "abstention" in payload
    assert "information_extraction" in payload
    assert payload["information_extraction"][0]["llm_judge_score"] == 0.5


def test_resume_openai_compatible_single_conversation_evaluation_normalizes_list_judge_response(
    tmp_path: Path,
):
    probing_questions_path = tmp_path / "probing_questions.json"
    answers_path = tmp_path / "answers.json"
    output_path = tmp_path / "evaluation-answers.json"

    probing_questions_path.write_text(
        json.dumps(
            {
                "instruction_following": [{"rubric": ["step-by-step algebraic derivation"]}],
            }
        ),
        encoding="utf-8",
    )
    answers_path.write_text(
        json.dumps(
            {
                "instruction_following": [
                    {
                        "question": "How do I find the tangent line?",
                        "llm_response": "LLM response should include: step-by-step algebraic derivation",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    class FakeResponse:
        def __init__(self, content: str):
            self.content = content

    class FakeModel:
        @staticmethod
        def invoke(prompt: str):
            assert "step-by-step algebraic derivation" in prompt
            return FakeResponse('[{"score": 1, "reasoning": "meets rubric"}]')

    class FakeComputeMetricsModule:
        unified_llm_judge_base_prompt = "rubric=<rubric_item>\nresponse=<llm_response>"

        @staticmethod
        def parse_json_response(*, response: str):
            return json.loads(response)

        @staticmethod
        def repair_json(response: str):
            return response

    class FakeRunEvaluationModule:
        @staticmethod
        def get_rubric(**kwargs):
            assert kwargs["key"] == "instruction_following"
            return ["step-by-step algebraic derivation"]

    beam_official_eval._resume_openai_compatible_single_conversation_evaluation(
        probing_questions_address=probing_questions_path,
        answers_file=answers_path,
        output_file=output_path,
        model=FakeModel(),
        compute_metrics_module=FakeComputeMetricsModule(),
        run_evaluation_module=FakeRunEvaluationModule(),
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["instruction_following"][0]["llm_judge_score"] == 1.0
    assert payload["instruction_following"][0]["llm_judge_responses"][0]["score"] == 1


def test_resume_openai_compatible_single_conversation_evaluation_normalizes_nested_score_response(
    tmp_path: Path,
):
    probing_questions_path = tmp_path / "probing_questions.json"
    answers_path = tmp_path / "answers.json"
    output_path = tmp_path / "evaluation-answers.json"

    probing_questions_path.write_text(
        json.dumps(
            {
                "preference_following": [{"rubric": ["breaks down each step clearly"]}],
            }
        ),
        encoding="utf-8",
    )
    answers_path.write_text(
        json.dumps(
            {
                "preference_following": [
                    {
                        "question": "Show the derivative step-by-step.",
                        "llm_response": "LLM response should include: breaks down each step clearly",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    class FakeResponse:
        def __init__(self, content: str):
            self.content = content

    class FakeModel:
        @staticmethod
        def invoke(prompt: str):
            assert "breaks down each step clearly" in prompt
            return FakeResponse('{"result": {"score": 1, "reasoning": "meets rubric"}}')

    class FakeComputeMetricsModule:
        unified_llm_judge_base_prompt = "rubric=<rubric_item>\nresponse=<llm_response>"

        @staticmethod
        def parse_json_response(*, response: str):
            return json.loads(response)

        @staticmethod
        def repair_json(response: str):
            return response

    class FakeRunEvaluationModule:
        @staticmethod
        def get_rubric(**kwargs):
            assert kwargs["key"] == "preference_following"
            return ["breaks down each step clearly"]

    beam_official_eval._resume_openai_compatible_single_conversation_evaluation(
        probing_questions_address=probing_questions_path,
        answers_file=answers_path,
        output_file=output_path,
        model=FakeModel(),
        compute_metrics_module=FakeComputeMetricsModule(),
        run_evaluation_module=FakeRunEvaluationModule(),
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["preference_following"][0]["llm_judge_score"] == 1.0
    assert payload["preference_following"][0]["llm_judge_responses"][0]["score"] == 1


def test_resume_openai_compatible_single_conversation_evaluation_coerces_null_score_response(
    tmp_path: Path,
):
    probing_questions_path = tmp_path / "probing_questions.json"
    answers_path = tmp_path / "answers.json"
    output_path = tmp_path / "evaluation-answers.json"

    probing_questions_path.write_text(
        json.dumps(
            {
                "instruction_following": [
                    {"rubric": ["mention of exact monetary figures"]},
                ],
            }
        ),
        encoding="utf-8",
    )
    answers_path.write_text(
        json.dumps(
            {
                "instruction_following": [
                    {
                        "question": "What should I consider when organizing my upcoming event?",
                        "llm_response": "LLM response should include: mention of exact monetary figures",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    class FakeResponse:
        def __init__(self, content: str):
            self.content = content

    class FakeModel:
        @staticmethod
        def invoke(prompt: str):
            assert "mention of exact monetary figures" in prompt
            return FakeResponse('{"score": null, "reason": "judge returned null"}')

    class FakeComputeMetricsModule:
        unified_llm_judge_base_prompt = "rubric=<rubric_item>\nresponse=<llm_response>"

        @staticmethod
        def parse_json_response(*, response: str):
            return json.loads(response)

        @staticmethod
        def repair_json(response: str):
            return response

    class FakeRunEvaluationModule:
        @staticmethod
        def get_rubric(**kwargs):
            assert kwargs["key"] == "instruction_following"
            return ["mention of exact monetary figures"]

    beam_official_eval._resume_openai_compatible_single_conversation_evaluation(
        probing_questions_address=probing_questions_path,
        answers_file=answers_path,
        output_file=output_path,
        model=FakeModel(),
        compute_metrics_module=FakeComputeMetricsModule(),
        run_evaluation_module=FakeRunEvaluationModule(),
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["instruction_following"][0]["llm_judge_score"] == 0.0
    assert payload["instruction_following"][0]["llm_judge_responses"][0]["score"] == 0.0


def test_resume_openai_compatible_single_conversation_evaluation_coerces_missing_score_response(
    tmp_path: Path,
):
    probing_questions_path = tmp_path / "probing_questions.json"
    answers_path = tmp_path / "answers.json"
    output_path = tmp_path / "evaluation-answers.json"

    probing_questions_path.write_text(
        json.dumps(
            {
                "preference_following": [
                    {"rubric": ["breaks down each step clearly"]},
                ],
            }
        ),
        encoding="utf-8",
    )
    answers_path.write_text(
        json.dumps(
            {
                "preference_following": [
                    {
                        "question": "Show the derivative step-by-step.",
                        "llm_response": "LLM response should include: breaks down each step clearly",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    class FakeResponse:
        def __init__(self, content: str):
            self.content = content

    class FakeModel:
        @staticmethod
        def invoke(prompt: str):
            assert "breaks down each step clearly" in prompt
            return FakeResponse('{"reason": "judge forgot the score field"}')

    class FakeComputeMetricsModule:
        unified_llm_judge_base_prompt = "rubric=<rubric_item>\nresponse=<llm_response>"

        @staticmethod
        def parse_json_response(*, response: str):
            return json.loads(response)

        @staticmethod
        def repair_json(response: str):
            return response

    class FakeRunEvaluationModule:
        @staticmethod
        def get_rubric(**kwargs):
            assert kwargs["key"] == "preference_following"
            return ["breaks down each step clearly"]

    beam_official_eval._resume_openai_compatible_single_conversation_evaluation(
        probing_questions_address=probing_questions_path,
        answers_file=answers_path,
        output_file=output_path,
        model=FakeModel(),
        compute_metrics_module=FakeComputeMetricsModule(),
        run_evaluation_module=FakeRunEvaluationModule(),
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["preference_following"][0]["llm_judge_score"] == 0.0
    assert payload["preference_following"][0]["llm_judge_responses"][0]["score"] == 0.0
    assert payload["preference_following"][0]["llm_judge_responses"][0]["reason"] == "judge forgot the score field"


def test_resume_openai_compatible_single_conversation_evaluation_normalizes_list_response_for_abstention(
    tmp_path: Path,
):
    probing_questions_path = tmp_path / "probing_questions.json"
    answers_path = tmp_path / "answers.json"
    output_path = tmp_path / "evaluation-answers.json"

    probing_questions_path.write_text(
        json.dumps(
            {
                "abstention": [{"rubric": ["no concrete date provided"]}],
            }
        ),
        encoding="utf-8",
    )
    answers_path.write_text(
        json.dumps(
            {
                "abstention": [
                    {
                        "question": "When exactly is the event?",
                        "llm_response": "There is no concrete date provided.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    class FakeResponse:
        def __init__(self, content: str):
            self.content = content

    class FakeModel:
        @staticmethod
        def invoke(prompt: str):
            assert "no concrete date provided" in prompt
            return FakeResponse('[{"score": 1, "reasoning": "correct abstention"}]')

    class FakeComputeMetricsModule:
        unified_llm_judge_base_prompt = "rubric=<rubric_item>\nresponse=<llm_response>"

        @staticmethod
        def parse_json_response(*, response: str):
            return json.loads(response)

        @staticmethod
        def repair_json(response: str):
            return response

    class FakeRunEvaluationModule:
        @staticmethod
        def get_rubric(**kwargs):
            assert kwargs["key"] == "abstention"
            return ["no concrete date provided"]

    beam_official_eval._resume_openai_compatible_single_conversation_evaluation(
        probing_questions_address=probing_questions_path,
        answers_file=answers_path,
        output_file=output_path,
        model=FakeModel(),
        compute_metrics_module=FakeComputeMetricsModule(),
        run_evaluation_module=FakeRunEvaluationModule(),
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["abstention"][0]["llm_judge_score"] == 1.0
    assert payload["abstention"][0]["llm_judge_responses"][0]["score"] == 1


def test_resume_openai_compatible_single_conversation_evaluation_normalizes_event_ordering_judge_response(
    tmp_path: Path,
):
    probing_questions_path = tmp_path / "probing_questions.json"
    answers_path = tmp_path / "answers.json"
    output_path = tmp_path / "evaluation-answers.json"

    probing_questions_path.write_text(
        json.dumps(
            {
                "event_ordering": [{"rubric": ["Alice left home", "Alice reached the station"]}],
            }
        ),
        encoding="utf-8",
    )
    answers_path.write_text(
        json.dumps(
            {
                "event_ordering": [
                    {
                        "question": "List the travel events in order.",
                        "llm_response": "Alice left home\nAlice reached the station",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    class FakeResponse:
        def __init__(self, content: str):
            self.content = content

    class FakeModel:
        @staticmethod
        def invoke(prompt: str):
            assert "Alice left home" in prompt
            return FakeResponse('{"result": {"score": 1, "reasoning": "order is correct"}}')

    class FakeComputeMetricsModule:
        unified_llm_judge_base_prompt = "rubric=<rubric_item>\nresponse=<llm_response>"

        @staticmethod
        def parse_json_response(*, response: str):
            return json.loads(response)

        @staticmethod
        def repair_json(response: str):
            return response

        @staticmethod
        def event_ordering_score(*, reference_list, system_list, align_type, llm):
            assert reference_list == ["Alice left home", "Alice reached the station"]
            assert system_list == ["Alice left home", "Alice reached the station"]
            assert align_type == "llm"
            assert llm is not None
            return {"tau_norm": 1.0, "precision": 1.0, "recall": 1.0, "f1": 1.0, "final_score": 1.0}

    class FakeRunEvaluationModule:
        @staticmethod
        def get_rubric(**kwargs):
            assert kwargs["key"] == "event_ordering"
            return ["Alice left home", "Alice reached the station"]

    beam_official_eval._resume_openai_compatible_single_conversation_evaluation(
        probing_questions_address=probing_questions_path,
        answers_file=answers_path,
        output_file=output_path,
        model=FakeModel(),
        compute_metrics_module=FakeComputeMetricsModule(),
        run_evaluation_module=FakeRunEvaluationModule(),
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["event_ordering"][0]["tau_norm"] == 1.0
    assert payload["event_ordering"][0]["llm_judge_score"] == 1.0
    assert payload["event_ordering"][0]["llm_judge_responses"][0]["score"] == 1


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
