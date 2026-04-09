import importlib
import json
import subprocess
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
from domain_chip_memory.spark_kb import build_spark_kb_health_report
from domain_chip_memory.spark_kb import scaffold_spark_knowledge_base
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
    assert (output_dir / "wiki" / "outputs" / "_index.md").exists()
    assert (output_dir / "wiki" / "sources" / "spark-memory-snapshot-latest.md").exists()
    assert (output_dir / "wiki" / "sources" / "session-spark-kb-demo.md").exists()
    assert (output_dir / "wiki" / "syntheses" / "runtime-memory-overview.md").exists()
    assert (output_dir / "wiki" / "syntheses" / "timeline-overview.md").exists()
    assert (output_dir / "wiki" / "outputs" / "maintenance-report.md").exists()
    assert (output_dir / "wiki" / "outputs" / "query-user-location-answer.md").exists()
    assert written["compile_result"]["source_page_count"] >= 1
    assert written["compile_result"]["synthesis_page_count"] >= 1
    assert written["compile_result"]["output_page_count"] >= 1
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
    assert payload["repo_source_pages_missing_raw_copy"] == []
    assert payload["raw_repo_files_without_source_pages"] == []
    assert payload["output_pages_missing_sections"] == []
    assert "wiki/current-state/user-location.md" not in payload["orphan_pages"]
    assert "wiki/sources/spark-memory-snapshot-latest.md" not in payload["orphan_pages"]
    assert "wiki/outputs/maintenance-report.md" not in payload["orphan_pages"]
    assert written["trace"]["operation"] == "spark_kb_health_check"


def test_demo_spark_kb_can_ingest_explicit_repo_source(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}
    output_dir = tmp_path / "spark_kb_vault"
    summary_file = tmp_path / "artifacts" / "spark_kb_demo.json"
    repo_source = tmp_path / "NOTES.md"
    repo_source.write_text("# Notes\n\nRepo-native source for KB ingest.\n", encoding="utf-8")

    monkeypatch.setattr(cli, "_print", lambda payload: captured.setdefault("payload", payload))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "demo-spark-kb",
            str(output_dir),
            "--repo-source",
            str(repo_source),
            "--write",
            str(summary_file),
        ],
    )

    cli.main()

    written = json.loads(summary_file.read_text(encoding="utf-8"))
    assert written["compile_result"]["repo_source_count"] == 1
    assert written["compile_result"]["filed_output_count"] == 1
    assert (output_dir / "raw" / "repos" / "01-NOTES.md").exists()
    assert (output_dir / "wiki" / "sources" / "repo-notes.md").exists()


def test_spark_kb_health_report_tracks_repo_and_output_surfaces(tmp_path: Path):
    output_dir = tmp_path / "spark_kb_vault"
    repo_source = tmp_path / "NOTES.md"
    repo_source.write_text("# Notes\n\nRepo-native source for KB ingest.\n", encoding="utf-8")
    snapshot = {
        "runtime_class": "SparkMemorySDK",
        "generated_at": "2025-03-10T00:00:00+00:00",
        "counts": {
            "session_count": 1,
            "current_state_count": 1,
            "observation_count": 1,
            "event_count": 0,
        },
        "sessions": [
            {
                "session_id": "session-health",
                "timestamp": "2025-03-10T00:00:00+00:00",
                "turns": [
                    {"turn_id": "session-health:t1", "speaker": "user", "text": "I live in Dubai."},
                ],
            }
        ],
        "current_state": [
            {
                "memory_role": "current_state",
                "subject": "user",
                "predicate": "location",
                "text": "user location Dubai",
                "session_id": "session-health",
                "turn_ids": ["session-health:t1"],
                "timestamp": "2025-03-10T00:00:00+00:00",
                "metadata": {"value": "Dubai", "observation_id": "obs-health-1"},
            }
        ],
        "observations": [
            {
                "memory_role": "structured_evidence",
                "subject": "user",
                "predicate": "location",
                "text": "user location Dubai",
                "session_id": "session-health",
                "turn_ids": ["session-health:t1"],
                "timestamp": "2025-03-10T00:00:00+00:00",
                "metadata": {"value": "Dubai", "observation_id": "obs-health-1"},
            }
        ],
        "events": [],
        "trace": {"operation": "export_knowledge_base_snapshot"},
    }

    scaffold_spark_knowledge_base(
        output_dir,
        snapshot,
        repo_sources=[repo_source],
        filed_outputs=[
            {
                "slug": "health-answer",
                "title": "Health Answer",
                "question": "Where does the user live?",
                "answer": "The user lives in Dubai.",
                "provenance": ["[[sources/spark-memory-snapshot-latest]]"],
            }
        ],
    )

    payload = build_spark_kb_health_report(output_dir)

    assert payload["valid"] is True
    assert payload["repo_source_page_count"] == 1
    assert payload["raw_repo_file_count"] == 1
    assert payload["query_output_page_count"] == 1
    assert payload["repo_source_pages_missing_raw_copy"] == []
    assert payload["raw_repo_files_without_source_pages"] == []
    assert payload["output_pages_missing_sections"] == []


def test_spark_kb_health_report_surfaces_repo_and_output_integrity_gaps(tmp_path: Path):
    output_dir = tmp_path / "spark_kb_vault"
    repo_source = tmp_path / "NOTES.md"
    repo_source.write_text("# Notes\n\nRepo-native source for KB ingest.\n", encoding="utf-8")
    snapshot = {
        "runtime_class": "SparkMemorySDK",
        "generated_at": "2025-03-10T00:00:00+00:00",
        "counts": {
            "session_count": 1,
            "current_state_count": 1,
            "observation_count": 1,
            "event_count": 0,
        },
        "sessions": [
            {
                "session_id": "session-health-negative",
                "timestamp": "2025-03-10T00:00:00+00:00",
                "turns": [
                    {"turn_id": "session-health-negative:t1", "speaker": "user", "text": "I live in Dubai."},
                ],
            }
        ],
        "current_state": [
            {
                "memory_role": "current_state",
                "subject": "user",
                "predicate": "location",
                "text": "user location Dubai",
                "session_id": "session-health-negative",
                "turn_ids": ["session-health-negative:t1"],
                "timestamp": "2025-03-10T00:00:00+00:00",
                "metadata": {"value": "Dubai", "observation_id": "obs-health-negative-1"},
            }
        ],
        "observations": [
            {
                "memory_role": "structured_evidence",
                "subject": "user",
                "predicate": "location",
                "text": "user location Dubai",
                "session_id": "session-health-negative",
                "turn_ids": ["session-health-negative:t1"],
                "timestamp": "2025-03-10T00:00:00+00:00",
                "metadata": {"value": "Dubai", "observation_id": "obs-health-negative-1"},
            }
        ],
        "events": [],
        "trace": {"operation": "export_knowledge_base_snapshot"},
    }

    scaffold_spark_knowledge_base(
        output_dir,
        snapshot,
        repo_sources=[repo_source],
        filed_outputs=[
            {
                "slug": "health-answer-negative",
                "title": "Health Answer Negative",
                "question": "Where does the user live?",
                "answer": "The user lives in Dubai.",
                "provenance": ["[[sources/spark-memory-snapshot-latest]]"],
            }
        ],
    )

    (output_dir / "raw" / "repos" / "01-NOTES.md").unlink()
    (output_dir / "raw" / "repos" / "99-orphan.md").write_text("orphan raw repo file\n", encoding="utf-8")
    query_output_path = output_dir / "wiki" / "outputs" / "query-health-answer-negative.md"
    query_output_path.write_text(
        query_output_path.read_text(encoding="utf-8").replace("## Answer", "## Response"),
        encoding="utf-8",
    )

    payload = build_spark_kb_health_report(output_dir)

    assert payload["valid"] is False
    assert payload["repo_source_page_count"] == 1
    assert payload["raw_repo_file_count"] == 1
    assert payload["query_output_page_count"] == 1
    assert payload["repo_source_pages_missing_raw_copy"] == [
        {
            "source": "wiki/sources/repo-notes.md",
            "target": "raw/repos/01-NOTES.md",
        }
    ]
    assert payload["raw_repo_files_without_source_pages"] == ["raw/repos/99-orphan.md"]
    assert payload["output_pages_missing_sections"] == [
        {
            "path": "wiki/outputs/query-health-answer-negative.md",
            "missing_sections": ["## Answer"],
        }
    ]


def test_build_spark_kb_command_compiles_from_snapshot_file(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}
    output_dir = tmp_path / "spark_kb_vault"
    summary_file = tmp_path / "artifacts" / "spark_kb_build.json"
    snapshot_file = tmp_path / "snapshot.json"
    repo_source = tmp_path / "README_SNIPPET.md"
    filed_output_file = tmp_path / "filed_output.json"
    repo_source.write_text("# Repo Snippet\n\nUseful repo context.\n", encoding="utf-8")
    filed_output_file.write_text(
        json.dumps(
            {
                "title": "Location Answer",
                "slug": "location-answer",
                "question": "Where does the user live?",
                "answer": "Dubai",
                "explanation": "Resolved from current state.",
                "memory_role": "current_state",
                "provenance": ["`session-build` turns `session-build:t1`"],
            }
        ),
        encoding="utf-8",
    )
    snapshot_file.write_text(
        json.dumps(
            {
                "runtime_class": "SparkMemorySDK",
                "generated_at": "2025-03-10T00:00:00+00:00",
                "counts": {
                    "session_count": 1,
                    "current_state_count": 1,
                    "observation_count": 1,
                    "event_count": 0,
                },
                "sessions": [
                    {
                        "session_id": "session-build",
                        "timestamp": "2025-03-10T00:00:00+00:00",
                        "turns": [
                            {"turn_id": "session-build:t1", "speaker": "user", "text": "I live in Dubai."}
                        ],
                    }
                ],
                "current_state": [
                    {
                        "memory_role": "current_state",
                        "subject": "user",
                        "predicate": "location",
                        "text": "user location Dubai",
                        "session_id": "session-build",
                        "turn_ids": ["session-build:t1"],
                        "timestamp": "2025-03-10T00:00:00+00:00",
                        "metadata": {"value": "Dubai"},
                    }
                ],
                "observations": [
                    {
                        "memory_role": "structured_evidence",
                        "subject": "user",
                        "predicate": "location",
                        "text": "user location Dubai",
                        "session_id": "session-build",
                        "turn_ids": ["session-build:t1"],
                        "timestamp": "2025-03-10T00:00:00+00:00",
                        "metadata": {"value": "Dubai", "observation_id": "obs-build-1"},
                    }
                ],
                "events": [],
                "trace": {"operation": "export_knowledge_base_snapshot"},
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
            "build-spark-kb",
            str(snapshot_file),
            str(output_dir),
            "--repo-source",
            str(repo_source),
            "--filed-output-file",
            str(filed_output_file),
            "--write",
            str(summary_file),
        ],
    )

    cli.main()

    written = json.loads(summary_file.read_text(encoding="utf-8"))
    assert written["snapshot_file"] == str(snapshot_file)
    assert written["filed_output_file_count"] == 1
    assert written["compile_result"]["current_state_page_count"] >= 1
    assert written["compile_result"]["filed_output_count"] == 1
    assert (output_dir / "wiki" / "current-state" / "user-location.md").exists()
    assert (output_dir / "wiki" / "sources" / "repo-readme-snippet.md").exists()
    assert (output_dir / "wiki" / "outputs" / "query-location-answer.md").exists()


def test_build_spark_kb_command_ingests_repo_sources_from_manifest(tmp_path: Path, monkeypatch):
    output_dir = tmp_path / "compiled_vault"
    snapshot_file = tmp_path / "snapshot.json"
    repo_source_a = tmp_path / "sources" / "docs-note.md"
    repo_source_b = tmp_path / "sources" / "src-snippet.py"
    repo_source_manifest_dir = tmp_path / "manifests"
    repo_source_manifest_file = repo_source_manifest_dir / "repo-sources.json"
    summary_file = tmp_path / "summary.json"
    captured: dict[str, object] = {}

    repo_source_a.parent.mkdir()
    repo_source_manifest_dir.mkdir()
    repo_source_a.write_text("# Notes\n\nRepo context for KB.\n", encoding="utf-8")
    repo_source_b.write_text("print('repo source')\n", encoding="utf-8")
    repo_source_manifest_file.write_text(
        json.dumps({"repo_sources": ["../sources/docs-note.md", "../sources/src-snippet.py"]}),
        encoding="utf-8",
    )
    snapshot_file.write_text(
        json.dumps(
            {
                "runtime_class": "SparkMemorySDK",
                "generated_at": "2025-03-10T00:00:00+00:00",
                "counts": {
                    "session_count": 1,
                    "current_state_count": 1,
                    "observation_count": 1,
                    "event_count": 0,
                },
                "sessions": [
                    {
                        "session_id": "session-manifest",
                        "timestamp": "2025-03-10T00:00:00+00:00",
                        "turns": [
                            {
                                "turn_id": "session-manifest:t1",
                                "speaker": "user",
                                "text": "Remember my preferred city is Dubai.",
                            }
                        ],
                    }
                ],
                "current_state": [
                    {
                        "memory_role": "current_state",
                        "subject": "user",
                        "predicate": "location",
                        "text": "user location Dubai",
                        "session_id": "session-manifest",
                        "turn_ids": ["session-manifest:t1"],
                        "timestamp": "2025-03-10T00:00:00+00:00",
                        "metadata": {"value": "Dubai", "observation_id": "obs-manifest-1"},
                    }
                ],
                "observations": [
                    {
                        "memory_role": "structured_evidence",
                        "subject": "user",
                        "predicate": "location",
                        "text": "user location Dubai",
                        "session_id": "session-manifest",
                        "turn_ids": ["session-manifest:t1"],
                        "timestamp": "2025-03-10T00:00:00+00:00",
                        "metadata": {"value": "Dubai", "observation_id": "obs-manifest-1"},
                    }
                ],
                "events": [],
                "trace": {"operation": "export_knowledge_base_snapshot"},
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
            "build-spark-kb",
            str(snapshot_file),
            str(output_dir),
            "--repo-source-manifest",
            str(repo_source_manifest_file),
            "--write",
            str(summary_file),
        ],
    )

    cli.main()

    written = json.loads(summary_file.read_text(encoding="utf-8"))
    assert written["snapshot_file"] == str(snapshot_file)
    assert written["repo_source_manifest_file_count"] == 1
    assert written["compile_result"]["repo_source_count"] == 2
    assert written["compile_result"]["filed_output_count"] == 0
    assert (output_dir / "wiki" / "sources" / "repo-docs-note.md").exists()
    assert (output_dir / "wiki" / "sources" / "repo-src-snippet.md").exists()
    assert (output_dir / "raw" / "repos" / "01-docs-note.md").exists()
    assert (output_dir / "raw" / "repos" / "02-src-snippet.py").exists()


def test_build_spark_kb_command_ingests_filed_outputs_from_manifest(tmp_path: Path, monkeypatch):
    output_dir = tmp_path / "compiled_vault"
    snapshot_file = tmp_path / "snapshot.json"
    filed_output_dir = tmp_path / "outputs"
    filed_output_file = filed_output_dir / "answer.json"
    filed_output_manifest_dir = tmp_path / "manifests"
    filed_output_manifest_file = filed_output_manifest_dir / "filed-outputs.json"
    summary_file = tmp_path / "summary.json"
    captured: dict[str, object] = {}

    filed_output_dir.mkdir()
    filed_output_manifest_dir.mkdir()
    filed_output_file.write_text(
        json.dumps(
            {
                "slug": "manifest-answer",
                "title": "Manifest Answer",
                "question": "Where does the user live?",
                "answer": "The user lives in Dubai.",
                "sources": [{"title": "Snapshot", "link": "[[sources/runtime-memory-snapshot]]"}],
                "generated_at": "2025-03-10T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    filed_output_manifest_file.write_text(
        json.dumps({"filed_output_files": ["../outputs/answer.json"]}),
        encoding="utf-8",
    )
    snapshot_file.write_text(
        json.dumps(
            {
                "runtime_class": "SparkMemorySDK",
                "generated_at": "2025-03-10T00:00:00+00:00",
                "counts": {
                    "session_count": 1,
                    "current_state_count": 1,
                    "observation_count": 1,
                    "event_count": 0,
                },
                "sessions": [
                    {
                        "session_id": "session-filed-manifest",
                        "timestamp": "2025-03-10T00:00:00+00:00",
                        "turns": [
                            {
                                "turn_id": "session-filed-manifest:t1",
                                "speaker": "user",
                                "text": "My preferred city is Dubai.",
                            }
                        ],
                    }
                ],
                "current_state": [
                    {
                        "memory_role": "current_state",
                        "subject": "user",
                        "predicate": "location",
                        "text": "user location Dubai",
                        "session_id": "session-filed-manifest",
                        "turn_ids": ["session-filed-manifest:t1"],
                        "timestamp": "2025-03-10T00:00:00+00:00",
                        "metadata": {"value": "Dubai", "observation_id": "obs-filed-manifest-1"},
                    }
                ],
                "observations": [
                    {
                        "memory_role": "structured_evidence",
                        "subject": "user",
                        "predicate": "location",
                        "text": "user location Dubai",
                        "session_id": "session-filed-manifest",
                        "turn_ids": ["session-filed-manifest:t1"],
                        "timestamp": "2025-03-10T00:00:00+00:00",
                        "metadata": {"value": "Dubai", "observation_id": "obs-filed-manifest-1"},
                    }
                ],
                "events": [],
                "trace": {"operation": "export_knowledge_base_snapshot"},
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
            "build-spark-kb",
            str(snapshot_file),
            str(output_dir),
            "--filed-output-manifest",
            str(filed_output_manifest_file),
            "--write",
            str(summary_file),
        ],
    )

    cli.main()

    written = json.loads(summary_file.read_text(encoding="utf-8"))
    assert written["snapshot_file"] == str(snapshot_file)
    assert written["filed_output_manifest_file_count"] == 1
    assert written["filed_output_file_count"] == 1
    assert written["compile_result"]["filed_output_count"] == 1
    assert (output_dir / "wiki" / "outputs" / "query-manifest-answer.md").exists()


def test_validate_spark_kb_inputs_command_reports_valid_bundle(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}
    snapshot_file = tmp_path / "snapshot.json"
    repo_source_dir = tmp_path / "sources"
    repo_source_dir.mkdir()
    repo_source = repo_source_dir / "NOTES.md"
    repo_source.write_text("# Notes\n\nRepo-native source for KB ingest.\n", encoding="utf-8")
    repo_source_manifest_dir = tmp_path / "manifests"
    repo_source_manifest_dir.mkdir()
    repo_source_manifest_file = repo_source_manifest_dir / "repo-sources.json"
    repo_source_manifest_file.write_text(json.dumps({"repo_sources": ["../sources/NOTES.md"]}), encoding="utf-8")
    filed_output_dir = tmp_path / "outputs"
    filed_output_dir.mkdir()
    filed_output_file = filed_output_dir / "answer.json"
    filed_output_file.write_text(
        json.dumps(
            {
                "slug": "validation-answer",
                "title": "Validation Answer",
                "question": "Where does the user live?",
                "answer": "The user lives in Dubai.",
            }
        ),
        encoding="utf-8",
    )
    filed_output_manifest_file = repo_source_manifest_dir / "filed-outputs.json"
    filed_output_manifest_file.write_text(
        json.dumps({"filed_output_files": ["../outputs/answer.json"]}),
        encoding="utf-8",
    )
    summary_file = tmp_path / "artifacts" / "spark_kb_validation.json"
    snapshot_file.write_text(
        json.dumps(
            {
                "runtime_class": "SparkMemorySDK",
                "generated_at": "2025-03-10T00:00:00+00:00",
                "counts": {
                    "session_count": 1,
                    "current_state_count": 1,
                    "observation_count": 1,
                    "event_count": 0,
                },
                "sessions": [],
                "current_state": [],
                "observations": [],
                "events": [],
                "trace": {"operation": "export_knowledge_base_snapshot"},
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
            "validate-spark-kb-inputs",
            str(snapshot_file),
            "--repo-source-manifest",
            str(repo_source_manifest_file),
            "--filed-output-manifest",
            str(filed_output_manifest_file),
            "--write",
            str(summary_file),
        ],
    )

    cli.main()

    written = json.loads(summary_file.read_text(encoding="utf-8"))
    assert written["valid"] is True
    assert written["snapshot_valid"] is True
    assert written["repo_source_file_count"] == 1
    assert written["filed_output_file_count"] == 1
    assert written["filed_output_record_count"] == 1
    assert written["missing_repo_source_files"] == []
    assert written["missing_filed_output_files"] == []
    assert written["repo_source_manifest_errors"] == []
    assert written["filed_output_manifest_errors"] == []
    assert written["filed_output_file_errors"] == []


def test_validate_spark_kb_inputs_command_surfaces_invalid_bundle(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}
    snapshot_file = tmp_path / "snapshot.json"
    snapshot_file.write_text(json.dumps(["not-an-object"]), encoding="utf-8")
    repo_source_manifest_file = tmp_path / "repo-sources.json"
    repo_source_manifest_file.write_text(json.dumps({"repo_sources": ["missing-note.md"]}), encoding="utf-8")
    filed_output_file = tmp_path / "bad-output.json"
    filed_output_file.write_text("5", encoding="utf-8")
    filed_output_manifest_file = tmp_path / "filed-outputs.json"
    filed_output_manifest_file.write_text(json.dumps({"wrong_key": ["missing-answer.json"]}), encoding="utf-8")
    summary_file = tmp_path / "artifacts" / "spark_kb_validation_invalid.json"

    monkeypatch.setattr(cli, "_print", lambda payload: captured.setdefault("payload", payload))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "validate-spark-kb-inputs",
            str(snapshot_file),
            "--repo-source-manifest",
            str(repo_source_manifest_file),
            "--filed-output-file",
            str(filed_output_file),
            "--filed-output-manifest",
            str(filed_output_manifest_file),
            "--write",
            str(summary_file),
        ],
    )

    cli.main()

    written = json.loads(summary_file.read_text(encoding="utf-8"))
    assert written["valid"] is False
    assert written["snapshot_valid"] is False
    assert written["snapshot_errors"] == ["Spark KB snapshot file must contain a JSON object."]
    assert written["missing_repo_source_files"] == [str(tmp_path / "missing-note.md")]
    assert written["filed_output_manifest_errors"] == [
        {
            "file": str(filed_output_manifest_file),
            "error": "Filed output manifest file must contain a JSON list of strings or an object with a 'filed_output_files' list.",
        }
    ]
    assert written["filed_output_file_errors"] == [
        {
            "file": str(filed_output_file),
            "error": "Filed output file must contain a JSON object or list of objects.",
        }
    ]


def test_spark_kb_maintenance_report_surfaces_contradictions_and_staleness(tmp_path: Path):
    output_dir = tmp_path / "spark_kb_vault"
    snapshot = {
        "runtime_class": "SparkMemorySDK",
        "generated_at": "2025-03-10T00:00:00+00:00",
        "counts": {
            "session_count": 1,
            "current_state_count": 1,
            "observation_count": 2,
            "event_count": 0,
        },
        "sessions": [
            {
                "session_id": "session-1",
                "timestamp": "2025-01-01T00:00:00+00:00",
                "turns": [
                    {"turn_id": "session-1:t1", "speaker": "user", "text": "I live in London."},
                    {"turn_id": "session-1:t2", "speaker": "user", "text": "I live in Dubai now."},
                ],
            }
        ],
        "current_state": [
            {
                "memory_role": "current_state",
                "subject": "user",
                "predicate": "location",
                "text": "user location Dubai",
                "session_id": "session-1",
                "turn_ids": ["session-1:t2"],
                "timestamp": "2025-01-01T00:00:00+00:00",
                "metadata": {"value": "Dubai"},
            }
        ],
        "observations": [
            {
                "memory_role": "structured_evidence",
                "subject": "user",
                "predicate": "location",
                "text": "user location London",
                "session_id": "session-1",
                "turn_ids": ["session-1:t1"],
                "timestamp": "2025-01-01T00:00:00+00:00",
                "metadata": {"value": "London", "observation_id": "obs-1"},
            },
            {
                "memory_role": "structured_evidence",
                "subject": "user",
                "predicate": "location",
                "text": "user location Dubai",
                "session_id": "session-1",
                "turn_ids": ["session-1:t2"],
                "timestamp": "2025-01-02T00:00:00+00:00",
                "metadata": {"value": "Dubai", "observation_id": "obs-2"},
            },
        ],
        "events": [],
        "trace": {"operation": "export_knowledge_base_snapshot"},
    }

    scaffold_spark_knowledge_base(output_dir, snapshot)

    maintenance = (output_dir / "wiki" / "outputs" / "maintenance-report.md").read_text(encoding="utf-8")
    assert "## Contradiction Candidates" in maintenance
    assert "`user.location` has multiple observed values" in maintenance
    assert "## Stale Current-State Candidates" in maintenance
    assert "older than `30` days" in maintenance
    assert "## Gap Signals" in maintenance


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


def test_checked_in_spark_kb_examples_validate_via_cli(tmp_path: Path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    example_dir = repo_root / "docs" / "examples" / "spark_kb"
    validation_output = tmp_path / "artifacts" / "spark_kb_validation.json"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "validate-spark-kb-inputs",
            str(example_dir / "snapshot.json"),
            "--repo-source-manifest",
            str(example_dir / "manifests" / "repo_sources.json"),
            "--filed-output-manifest",
            str(example_dir / "manifests" / "filed_outputs.json"),
            "--write",
            str(validation_output),
        ],
    )
    cli.main()

    payload = json.loads(validation_output.read_text(encoding="utf-8"))
    assert payload["valid"] is True
    assert payload["snapshot_valid"] is True
    assert payload["repo_source_file_count"] == 1
    assert payload["filed_output_file_count"] == 1
    assert payload["filed_output_record_count"] == 1
    assert payload["missing_repo_source_files"] == []
    assert payload["missing_filed_output_files"] == []


def test_checked_in_spark_kb_examples_build_and_health_check_via_cli(tmp_path: Path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    example_dir = repo_root / "docs" / "examples" / "spark_kb"
    output_dir = tmp_path / "spark_kb_vault"
    build_output = tmp_path / "artifacts" / "spark_kb_build.json"
    health_output = tmp_path / "artifacts" / "spark_kb_health.json"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "build-spark-kb",
            str(example_dir / "snapshot.json"),
            str(output_dir),
            "--repo-source-manifest",
            str(example_dir / "manifests" / "repo_sources.json"),
            "--filed-output-manifest",
            str(example_dir / "manifests" / "filed_outputs.json"),
            "--write",
            str(build_output),
        ],
    )
    cli.main()

    build_payload = json.loads(build_output.read_text(encoding="utf-8"))
    assert build_payload["compile_result"]["repo_source_count"] == 1
    assert build_payload["compile_result"]["filed_output_count"] == 1
    assert (output_dir / "wiki" / "sources" / "repo-repo-notes.md").exists()
    assert (output_dir / "wiki" / "outputs" / "query-example-location-answer.md").exists()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "spark-kb-health-check",
            str(output_dir),
            "--write",
            str(health_output),
        ],
    )
    cli.main()

    health_payload = json.loads(health_output.read_text(encoding="utf-8"))
    assert health_payload["valid"] is True
    assert health_payload["repo_source_page_count"] == 1
    assert health_payload["query_output_page_count"] == 1
    assert health_payload["repo_source_pages_missing_raw_copy"] == []
    assert health_payload["output_pages_missing_sections"] == []


def test_checked_in_invalid_spark_kb_examples_fail_validation_via_cli(tmp_path: Path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    example_dir = repo_root / "docs" / "examples" / "spark_kb_invalid"
    validation_output = tmp_path / "artifacts" / "spark_kb_invalid_validation.json"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "validate-spark-kb-inputs",
            str(example_dir / "snapshot.json"),
            "--repo-source-manifest",
            str(example_dir / "repo-sources.json"),
            "--filed-output-file",
            str(example_dir / "bad-output.json"),
            "--filed-output-manifest",
            str(example_dir / "filed-outputs.json"),
            "--write",
            str(validation_output),
        ],
    )
    cli.main()

    payload = json.loads(validation_output.read_text(encoding="utf-8"))
    assert payload["valid"] is False
    assert payload["snapshot_valid"] is False
    assert payload["snapshot_errors"] == ["Spark KB snapshot file must contain a JSON object."]
    assert payload["missing_repo_source_files"] == [str(example_dir / "missing-note.md")]
    assert payload["filed_output_manifest_errors"] == [
        {
            "file": str(example_dir / "filed-outputs.json"),
            "error": "Filed output manifest file must contain a JSON list of strings or an object with a 'filed_output_files' list.",
        }
    ]
    assert payload["filed_output_file_errors"] == [
        {
            "file": str(example_dir / "bad-output.json"),
            "error": "Filed output file must contain a JSON object or list of objects.",
        }
    ]


def test_checked_in_spark_kb_smoke_script_runs(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "docs" / "examples" / "spark_kb" / "run_smoke.py"
    output_dir = tmp_path / "spark_kb_vault"
    write_dir = tmp_path / "artifacts"

    subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--output-dir",
            str(output_dir),
            "--write-dir",
            str(write_dir),
        ],
        check=True,
        cwd=str(repo_root),
    )

    summary = json.loads((write_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["validation_valid"] is True
    assert summary["build_repo_source_count"] == 1
    assert summary["build_filed_output_count"] == 1
    assert summary["health_valid"] is True
    assert (write_dir / "validation.json").exists()
    assert (write_dir / "build.json").exists()
    assert (write_dir / "health.json").exists()


def test_checked_in_invalid_spark_kb_failure_script_runs(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "docs" / "examples" / "spark_kb_invalid" / "run_validate_failure.py"
    write_dir = tmp_path / "artifacts"

    subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--write-dir",
            str(write_dir),
        ],
        check=True,
        cwd=str(repo_root),
    )

    summary = json.loads((write_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["validation_valid"] is False
    assert summary["snapshot_valid"] is False
    assert summary["missing_repo_source_file_count"] == 1
    assert summary["filed_output_manifest_error_count"] == 1
    assert summary["filed_output_file_error_count"] == 1
    assert (write_dir / "validation.json").exists()


def test_checked_in_example_smoke_index_script_runs(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "docs" / "examples" / "run_smokes.py"
    write_dir = tmp_path / "artifacts"

    subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--write-dir",
            str(write_dir),
        ],
        check=True,
        cwd=str(repo_root),
    )

    summary = json.loads((write_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["all_expected_results_observed"] is True
    assert summary["runs"]["spark_kb"]["validation_valid"] is True
    assert summary["runs"]["spark_kb"]["health_valid"] is True
    assert summary["runs"]["spark_kb_invalid"]["validation_valid"] is False
    assert summary["runs"]["spark_kb_invalid"]["snapshot_valid"] is False
    assert (write_dir / "spark_kb" / "summary.json").exists()
    assert (write_dir / "spark_kb_invalid" / "summary.json").exists()


def test_example_smoke_workflow_exists_and_runs_top_level_script():
    repo_root = Path(__file__).resolve().parents[1]
    workflow_path = repo_root / ".github" / "workflows" / "example-smokes.yml"
    workflow_text = workflow_path.read_text(encoding="utf-8")

    assert "name: Example Smokes" in workflow_text
    assert "actions/setup-python@v5" in workflow_text
    assert 'python-version: "3.13"' in workflow_text
    assert "python -m pip install -e ." in workflow_text
    assert "python docs/examples/run_smokes.py --write-dir tmp/example_smoke_artifacts_ci" in workflow_text


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


def test_benchmark_runs_git_report_cli_groups_file_families_and_noisy_statuses(tmp_path: Path, monkeypatch):
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    output_file = tmp_path / "artifacts" / "benchmark_runs_git_report.json"

    debug_file = benchmark_runs_dir / "_debug_example.json"
    longmemeval_file = benchmark_runs_dir / "longmemeval_offset225_limit25_source.json"
    scorecard_file = benchmark_runs_dir / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10_v1_scorecard.json"
    official_eval_file = benchmark_runs_dir / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json"
    other_file = benchmark_runs_dir / "misc_snapshot.json"
    benchmark_runs_dir.mkdir(parents=True)
    for path in [debug_file, longmemeval_file, scorecard_file, official_eval_file, other_file]:
        path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        cli,
        "_git_status_by_path",
        lambda paths, repo_root: {
            "artifacts/benchmark_runs/_debug_example.json": "??",
            "artifacts/benchmark_runs/longmemeval_offset225_limit25_source.json": "??",
            "artifacts/benchmark_runs/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10_v1_scorecard.json": "M",
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "benchmark-runs-git-report",
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--write",
            str(output_file),
        ],
    )

    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["source_mode"] == "benchmark_runs_git_report"
    assert payload["family_filter"] is None
    assert payload["available_families"] == ["debug", "longmemeval", "official_eval_manifest", "other", "scorecard"]
    assert payload["noisy_family_counts"] == {"debug": 1, "longmemeval": 1, "scorecard": 1}
    assert payload["only_noisy"] is False
    assert payload["top_series_limit"] == 10
    assert payload["summary_only"] is False
    assert payload["current_command"] == [
        "python",
        "-m",
        "domain_chip_memory.cli",
        "benchmark-runs-git-report",
        "--benchmark-runs-dir",
        str(benchmark_runs_dir),
        "--repo-root",
        str(tmp_path),
        "--top-series-limit",
        "10",
    ]
    assert "benchmark-runs-git-report" in payload["current_command_shell"]
    assert payload["paths_included"] is True
    assert payload["file_count"] == 5
    assert payload["family_count"] == 5
    assert payload["git_status_counts"] == {"??": 2, "M": 1, "clean": 2}
    assert payload["reported_file_count"] == 5
    assert payload["reported_family_count"] == 5
    assert payload["reported_git_status_counts"] == {"??": 2, "M": 1, "clean": 2}
    assert payload["reported_series_count"] == 5
    assert payload["noisy_file_count"] == 3
    assert payload["listed_noisy_file_count"] == 3
    assert [row["family"] for row in payload["family_commands"]] == ["debug", "longmemeval", "scorecard"]
    assert all("--only-noisy" in row["command"] for row in payload["family_commands"])
    assert all("benchmark-runs-git-report" in row["command_shell"] for row in payload["family_commands"])
    assert payload["family_hotspots"] == [
        {
            "family": "debug",
            "family_file_count": 1,
            "series_count": 1,
            "top_series_prefix": "_debug",
            "top_series_file_count": 1,
            "top_series_share": 1.0,
            "average_series_size": 1.0,
            "concentration_label": "concentrated",
            "focus_mode": "series_first",
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "debug",
                "--series-prefix",
                "_debug",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family debug --series-prefix _debug --top-series-limit 10"
            ),
        },
        {
            "family": "longmemeval",
            "family_file_count": 1,
            "series_count": 1,
            "top_series_prefix": "longmemeval_offset225_limit25_source",
            "top_series_file_count": 1,
            "top_series_share": 1.0,
            "average_series_size": 1.0,
            "concentration_label": "concentrated",
            "focus_mode": "series_first",
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "longmemeval",
                "--series-prefix",
                "longmemeval_offset225_limit25_source",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family longmemeval --series-prefix longmemeval_offset225_limit25_source --top-series-limit 10"
            ),
        },
        {
            "family": "official_eval_manifest",
            "family_file_count": 1,
            "series_count": 1,
            "top_series_prefix": "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9",
            "top_series_file_count": 1,
            "top_series_share": 1.0,
            "average_series_size": 1.0,
            "concentration_label": "concentrated",
            "focus_mode": "series_first",
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "official_eval_manifest",
                "--series-prefix",
                "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family official_eval_manifest --series-prefix official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9 --top-series-limit 10"
            ),
        },
        {
            "family": "other",
            "family_file_count": 1,
            "series_count": 1,
            "top_series_prefix": "misc_snapshot",
            "top_series_file_count": 1,
            "top_series_share": 1.0,
            "average_series_size": 1.0,
            "concentration_label": "concentrated",
            "focus_mode": "series_first",
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "other",
                "--series-prefix",
                "misc_snapshot",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family other --series-prefix misc_snapshot --top-series-limit 10"
            ),
        },
        {
            "family": "scorecard",
            "family_file_count": 1,
            "series_count": 1,
            "top_series_prefix": "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10",
            "top_series_file_count": 1,
            "top_series_share": 1.0,
            "average_series_size": 1.0,
            "concentration_label": "concentrated",
            "focus_mode": "series_first",
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "scorecard",
                "--series-prefix",
                "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family scorecard --series-prefix official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10 --top-series-limit 10"
            ),
        },
    ]
    assert payload["recommended_hotspot"] == next(
        row for row in payload["family_hotspots"] if row["family"] == "scorecard"
    )
    assert payload["series_commands"] == [
        {
            "family": "debug",
            "series_prefix": "_debug",
            "noisy_file_count": 1,
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "debug",
                "--series-prefix",
                "_debug",
                "--only-noisy",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family debug --series-prefix _debug --only-noisy --top-series-limit 10"
            ),
        },
        {
            "family": "longmemeval",
            "series_prefix": "longmemeval_offset225_limit25_source",
            "noisy_file_count": 1,
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "longmemeval",
                "--series-prefix",
                "longmemeval_offset225_limit25_source",
                "--only-noisy",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family longmemeval --series-prefix longmemeval_offset225_limit25_source --only-noisy --top-series-limit 10"
            ),
        },
        {
            "family": "official_eval_manifest",
            "series_prefix": "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9",
            "noisy_file_count": 1,
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "official_eval_manifest",
                "--series-prefix",
                "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9",
                "--only-noisy",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family official_eval_manifest --series-prefix official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9 --only-noisy --top-series-limit 10"
            ),
        },
        {
            "family": "other",
            "series_prefix": "misc_snapshot",
            "noisy_file_count": 1,
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "other",
                "--series-prefix",
                "misc_snapshot",
                "--only-noisy",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family other --series-prefix misc_snapshot --only-noisy --top-series-limit 10"
            ),
        },
        {
            "family": "scorecard",
            "series_prefix": "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10",
            "noisy_file_count": 1,
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "scorecard",
                "--series-prefix",
                "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10",
                "--only-noisy",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family scorecard --series-prefix official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10 --only-noisy --top-series-limit 10"
            ),
        },
    ]
    assert payload["recommended_focus"] == {
        "scope": "family",
        "reason": "largest_noisy_family",
        "family": "scorecard",
        "noisy_file_count": 1,
        "command": [
            "python",
            "-m",
            "domain_chip_memory.cli",
            "benchmark-runs-git-report",
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--family",
            "scorecard",
            "--only-noisy",
            "--top-series-limit",
            "10",
        ],
        "command_shell": (
            f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
            f"--repo-root {tmp_path} --family scorecard --only-noisy --top-series-limit 10"
        ),
    }
    assert payload["recommended_drilldown"] == {
        "scope": "series",
        "reason": "largest_series_in_recommended_family",
        "family": "scorecard",
        "series_prefix": "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10",
        "noisy_file_count": 1,
        "command": [
            "python",
            "-m",
            "domain_chip_memory.cli",
            "benchmark-runs-git-report",
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--family",
            "scorecard",
            "--series-prefix",
            "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10",
            "--only-noisy",
            "--top-series-limit",
            "10",
        ],
        "command_shell": (
            f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
            f"--repo-root {tmp_path} --family scorecard --series-prefix official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10 "
            f"--only-noisy --top-series-limit 10"
        ),
    }
    assert payload["recommended_followups"] == [
        payload["recommended_focus"],
        payload["recommended_drilldown"],
    ]
    family_rows = {row["family"]: row for row in payload["families"]}
    series_rows = {(row["family"], row["series"]): row for row in payload["series"]}
    assert family_rows["debug"]["paths"] == ["artifacts/benchmark_runs/_debug_example.json"]
    assert family_rows["debug"]["git_status_counts"] == {"??": 1}
    assert family_rows["debug"]["reported_file_share"] == 0.2
    assert family_rows["debug"]["dominance_label"] == "minor"
    assert family_rows["debug"]["family_rank"] == 1
    assert family_rows["longmemeval"]["paths"] == ["artifacts/benchmark_runs/longmemeval_offset225_limit25_source.json"]
    assert family_rows["longmemeval"]["git_status_counts"] == {"??": 1}
    assert family_rows["longmemeval"]["reported_file_share"] == 0.2
    assert family_rows["longmemeval"]["dominance_label"] == "minor"
    assert family_rows["longmemeval"]["family_rank"] == 2
    assert family_rows["scorecard"]["paths"] == [
        "artifacts/benchmark_runs/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10_v1_scorecard.json"
    ]
    assert family_rows["scorecard"]["git_status_counts"] == {"M": 1}
    assert family_rows["scorecard"]["reported_file_share"] == 0.2
    assert family_rows["scorecard"]["dominance_label"] == "minor"
    assert family_rows["scorecard"]["family_rank"] == 5
    assert family_rows["official_eval_manifest"]["paths"] == [
        "artifacts/benchmark_runs/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json"
    ]
    assert family_rows["official_eval_manifest"]["git_status_counts"] == {"clean": 1}
    assert family_rows["official_eval_manifest"]["reported_file_share"] == 0.2
    assert family_rows["official_eval_manifest"]["dominance_label"] == "minor"
    assert family_rows["official_eval_manifest"]["family_rank"] == 3
    assert family_rows["other"]["paths"] == ["artifacts/benchmark_runs/misc_snapshot.json"]
    assert family_rows["other"]["git_status_counts"] == {"clean": 1}
    assert family_rows["other"]["reported_file_share"] == 0.2
    assert family_rows["other"]["dominance_label"] == "minor"
    assert family_rows["other"]["family_rank"] == 4
    assert payload["recommended_family"] == family_rows["scorecard"]
    assert payload["recommended_family_gap"] == {
        "scope": "gap_to_next_family",
        "family": "scorecard",
        "next_family": "longmemeval",
        "next_family_noisy_file_count": 1,
        "noisy_file_count_gap": 0,
        "noisy_share_gap": 0.0,
        "lead_label": "narrow",
        "next_family_command": [
            "python",
            "-m",
            "domain_chip_memory.cli",
            "benchmark-runs-git-report",
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--family",
            "longmemeval",
            "--only-noisy",
            "--top-series-limit",
            "10",
        ],
        "next_family_command_shell": (
            f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
            f"--repo-root {tmp_path} --family longmemeval --only-noisy --top-series-limit 10"
        ),
        "next_family_series_prefix": "longmemeval_offset225_limit25_source",
        "next_family_series_noisy_file_count": 1,
        "next_family_drilldown_command": [
            "python",
            "-m",
            "domain_chip_memory.cli",
            "benchmark-runs-git-report",
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--family",
            "longmemeval",
            "--series-prefix",
            "longmemeval_offset225_limit25_source",
            "--only-noisy",
            "--top-series-limit",
            "10",
        ],
        "next_family_drilldown_command_shell": (
            f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
            f"--repo-root {tmp_path} --family longmemeval --series-prefix longmemeval_offset225_limit25_source --only-noisy --top-series-limit 10"
        ),
    }
    assert payload["recommended_family_competition_window"] == {
        "scope": "competition_window",
        "family": "scorecard",
        "current": payload["family_competition"][0],
        "previous": None,
        "next": payload["family_competition"][1],
    }
    assert payload["recommended_family_competition_summary"] == {
        "scope": "competition_summary",
        "family": "scorecard",
        "rank": 1,
        "top_series_prefix": "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10",
        "top_series_noisy_file_count": 1,
        "competition_position_label": "contested_leader",
        "command": payload["family_competition"][0]["command"],
        "command_shell": payload["family_competition"][0]["command_shell"],
        "top_series_command": payload["family_competition"][0]["top_series_command"],
        "top_series_command_shell": payload["family_competition"][0]["top_series_command_shell"],
        "recommended_next_step": {
            "reason": "compare_nearest_competitor_top_series",
            "target": "nearest_competitor_top_series",
            "family": "longmemeval",
            "rank": 2,
            "top_series_prefix": "longmemeval_offset225_limit25_source",
            "top_series_noisy_file_count": 1,
            "command": payload["family_competition"][0]["nearest_competitor_top_series_command"],
            "command_shell": payload["family_competition"][0]["nearest_competitor_top_series_command_shell"],
        },
        "nearest_competitor": {
            "direction": "next",
            "family": "longmemeval",
            "rank": 2,
            "noisy_file_count_gap": 0,
            "noisy_share_gap": 0.0,
            "top_series_prefix": "longmemeval_offset225_limit25_source",
            "top_series_noisy_file_count": 1,
            "command": payload["family_competition"][1]["command"],
            "command_shell": payload["family_competition"][1]["command_shell"],
            "top_series_command": payload["family_competition"][1]["top_series_command"],
            "top_series_command_shell": payload["family_competition"][1]["top_series_command_shell"],
        },
    }
    assert payload["recommended_next_step"] == payload["recommended_family_competition_summary"]["recommended_next_step"]
    assert payload["recommended_sequence"] == [
        payload["recommended_focus"],
        payload["recommended_drilldown"],
        payload["recommended_next_step"],
    ]
    assert payload["recommended_sequence_targets"] == [
        {"type": "family", "family": "scorecard"},
        {
            "type": "series",
            "family": "scorecard",
            "series_prefix": "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10",
        },
        {
            "type": "top_series",
            "target": "nearest_competitor_top_series",
            "family": "longmemeval",
            "rank": 2,
            "series_prefix": "longmemeval_offset225_limit25_source",
        },
    ]
    assert payload["recommended_sequence_labels"] == [
        "focus family scorecard",
        "focus series scorecard / official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10",
        "compare longmemeval rank 2 / longmemeval_offset225_limit25_source",
    ]
    assert payload["recommended_sequence_preview"] == (
        "focus family scorecard -> "
        "focus series scorecard / official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10 -> "
        "compare longmemeval rank 2 / longmemeval_offset225_limit25_source"
    )
    assert payload["recommended_sequence_commands"] == [
        payload["recommended_focus"]["command"],
        payload["recommended_drilldown"]["command"],
        payload["recommended_next_step"]["command"],
    ]
    assert payload["recommended_sequence_shells"] == [
        payload["recommended_focus"]["command_shell"],
        payload["recommended_drilldown"]["command_shell"],
        payload["recommended_next_step"]["command_shell"],
    ]
    assert payload["recommended_sequence_steps"] == [
        {
            "step": 1,
            "phase": "focus",
            "label": payload["recommended_sequence_labels"][0],
            "target": payload["recommended_sequence_targets"][0],
            "command": payload["recommended_focus"]["command"],
            "command_shell": payload["recommended_focus"]["command_shell"],
        },
        {
            "step": 2,
            "phase": "drilldown",
            "label": payload["recommended_sequence_labels"][1],
            "target": payload["recommended_sequence_targets"][1],
            "command": payload["recommended_drilldown"]["command"],
            "command_shell": payload["recommended_drilldown"]["command_shell"],
        },
        {
            "step": 3,
            "phase": "next_step",
            "label": payload["recommended_sequence_labels"][2],
            "target": payload["recommended_sequence_targets"][2],
            "command": payload["recommended_next_step"]["command"],
            "command_shell": payload["recommended_next_step"]["command_shell"],
        },
    ]
    assert payload["recommended_sequence_by_phase"] == {
        "focus": payload["recommended_sequence_steps"][0],
        "drilldown": payload["recommended_sequence_steps"][1],
        "next_step": payload["recommended_sequence_steps"][2],
    }
    assert payload["family_competition"] == [
        {
            "rank": 1,
            "family": "scorecard",
            "noisy_file_count": 1,
            "noisy_file_share": 0.3333,
            "noisy_file_count_gap_from_leader": 0,
            "noisy_share_gap_from_leader": 0.0,
            "previous_family": None,
            "previous_noisy_file_count_gap": None,
            "previous_noisy_share_gap": None,
            "next_family": "longmemeval",
            "next_noisy_file_count_gap": 0,
            "next_noisy_share_gap": 0.0,
            "nearest_competitor_direction": "next",
            "nearest_competitor_family": "longmemeval",
            "nearest_competitor_rank": 2,
            "nearest_competitor_noisy_file_count_gap": 0,
            "nearest_competitor_noisy_share_gap": 0.0,
            "nearest_competitor_top_series_prefix": "longmemeval_offset225_limit25_source",
            "nearest_competitor_top_series_noisy_file_count": 1,
            "nearest_competitor_command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "longmemeval",
                "--only-noisy",
                "--top-series-limit",
                "10",
            ],
            "nearest_competitor_command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family longmemeval --only-noisy --top-series-limit 10"
            ),
            "nearest_competitor_top_series_command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "longmemeval",
                "--series-prefix",
                "longmemeval_offset225_limit25_source",
                "--only-noisy",
                "--top-series-limit",
                "10",
            ],
            "nearest_competitor_top_series_command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family longmemeval --series-prefix longmemeval_offset225_limit25_source "
                f"--only-noisy --top-series-limit 10"
            ),
            "competition_position_label": "contested_leader",
            "gap_label": "leader",
            "top_series_prefix": "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10",
            "top_series_noisy_file_count": 1,
            "top_series_command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "scorecard",
                "--series-prefix",
                "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10",
                "--only-noisy",
                "--top-series-limit",
                "10",
            ],
            "top_series_command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family scorecard --series-prefix official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10 "
                f"--only-noisy --top-series-limit 10"
            ),
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "scorecard",
                "--only-noisy",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family scorecard --only-noisy --top-series-limit 10"
            ),
        },
        {
            "rank": 2,
            "family": "longmemeval",
            "noisy_file_count": 1,
            "noisy_file_share": 0.3333,
            "noisy_file_count_gap_from_leader": 0,
            "noisy_share_gap_from_leader": 0.0,
            "previous_family": "scorecard",
            "previous_noisy_file_count_gap": 0,
            "previous_noisy_share_gap": 0.0,
            "next_family": "debug",
            "next_noisy_file_count_gap": 0,
            "next_noisy_share_gap": 0.0,
            "nearest_competitor_direction": "previous",
            "nearest_competitor_family": "scorecard",
            "nearest_competitor_rank": 1,
            "nearest_competitor_noisy_file_count_gap": 0,
            "nearest_competitor_noisy_share_gap": 0.0,
            "nearest_competitor_top_series_prefix": "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10",
            "nearest_competitor_top_series_noisy_file_count": 1,
            "nearest_competitor_command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "scorecard",
                "--only-noisy",
                "--top-series-limit",
                "10",
            ],
            "nearest_competitor_command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family scorecard --only-noisy --top-series-limit 10"
            ),
            "nearest_competitor_top_series_command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "scorecard",
                "--series-prefix",
                "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10",
                "--only-noisy",
                "--top-series-limit",
                "10",
            ],
            "nearest_competitor_top_series_command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family scorecard --series-prefix official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10 "
                f"--only-noisy --top-series-limit 10"
            ),
            "competition_position_label": "neck_and_neck",
            "gap_label": "narrow",
            "top_series_prefix": "longmemeval_offset225_limit25_source",
            "top_series_noisy_file_count": 1,
            "top_series_command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "longmemeval",
                "--series-prefix",
                "longmemeval_offset225_limit25_source",
                "--only-noisy",
                "--top-series-limit",
                "10",
            ],
            "top_series_command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family longmemeval --series-prefix longmemeval_offset225_limit25_source "
                f"--only-noisy --top-series-limit 10"
            ),
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "longmemeval",
                "--only-noisy",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family longmemeval --only-noisy --top-series-limit 10"
            ),
        },
        {
            "rank": 3,
            "family": "debug",
            "noisy_file_count": 1,
            "noisy_file_share": 0.3333,
            "noisy_file_count_gap_from_leader": 0,
            "noisy_share_gap_from_leader": 0.0,
            "previous_family": "longmemeval",
            "previous_noisy_file_count_gap": 0,
            "previous_noisy_share_gap": 0.0,
            "next_family": None,
            "next_noisy_file_count_gap": None,
            "next_noisy_share_gap": None,
            "nearest_competitor_direction": "previous",
            "nearest_competitor_family": "longmemeval",
            "nearest_competitor_rank": 2,
            "nearest_competitor_noisy_file_count_gap": 0,
            "nearest_competitor_noisy_share_gap": 0.0,
            "nearest_competitor_top_series_prefix": "longmemeval_offset225_limit25_source",
            "nearest_competitor_top_series_noisy_file_count": 1,
            "nearest_competitor_command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "longmemeval",
                "--only-noisy",
                "--top-series-limit",
                "10",
            ],
            "nearest_competitor_command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family longmemeval --only-noisy --top-series-limit 10"
            ),
            "nearest_competitor_top_series_command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "longmemeval",
                "--series-prefix",
                "longmemeval_offset225_limit25_source",
                "--only-noisy",
                "--top-series-limit",
                "10",
            ],
            "nearest_competitor_top_series_command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family longmemeval --series-prefix longmemeval_offset225_limit25_source "
                f"--only-noisy --top-series-limit 10"
            ),
            "competition_position_label": "neck_and_neck",
            "gap_label": "narrow",
            "top_series_prefix": "_debug",
            "top_series_noisy_file_count": 1,
            "top_series_command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "debug",
                "--series-prefix",
                "_debug",
                "--only-noisy",
                "--top-series-limit",
                "10",
            ],
            "top_series_command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family debug --series-prefix _debug --only-noisy --top-series-limit 10"
            ),
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "debug",
                "--only-noisy",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family debug --only-noisy --top-series-limit 10"
            ),
        },
    ]
    assert payload["recommended_family_comparison"] == {
        "scope": "leader_vs_runner_up",
        "leader_hotspot": {
            "family": "scorecard",
            "family_noisy_file_count": 1,
            "series_count": 1,
            "top_series_prefix": "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10",
            "top_series_noisy_file_count": 1,
            "top_series_share": 1.0,
            "average_series_size": 1.0,
            "concentration_label": "concentrated",
            "focus_mode": "series_first",
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "scorecard",
                "--series-prefix",
                "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10",
                "--only-noisy",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family scorecard --series-prefix official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10 "
                f"--only-noisy --top-series-limit 10"
            ),
        },
        "runner_up_hotspot": {
            "family": "longmemeval",
            "family_noisy_file_count": 1,
            "series_count": 1,
            "top_series_prefix": "longmemeval_offset225_limit25_source",
            "top_series_noisy_file_count": 1,
            "top_series_share": 1.0,
            "average_series_size": 1.0,
            "concentration_label": "concentrated",
            "focus_mode": "series_first",
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "longmemeval",
                "--series-prefix",
                "longmemeval_offset225_limit25_source",
                "--only-noisy",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family longmemeval --series-prefix longmemeval_offset225_limit25_source "
                f"--only-noisy --top-series-limit 10"
            ),
        },
        "gap": payload["recommended_family_gap"],
    }
    assert series_rows[("debug", "_debug")]["git_status_counts"] == {"??": 1}
    assert series_rows[("longmemeval", "longmemeval_offset225_limit25_source")]["git_status_counts"] == {"??": 1}
    assert series_rows[("scorecard", "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10")]["git_status_counts"] == {"M": 1}
    assert series_rows[("official_eval_manifest", "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9")]["git_status_counts"] == {"clean": 1}
    assert payload["top_noisy_series"] == [
        {
            "family": "debug",
            "series": "_debug",
            "file_count": 1,
            "git_status_counts": {"??": 1},
            "paths": ["artifacts/benchmark_runs/_debug_example.json"],
        },
        {
            "family": "longmemeval",
            "series": "longmemeval_offset225_limit25_source",
            "file_count": 1,
            "git_status_counts": {"??": 1},
            "paths": ["artifacts/benchmark_runs/longmemeval_offset225_limit25_source.json"],
        },
        {
            "family": "official_eval_manifest",
            "series": "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9",
            "file_count": 1,
            "git_status_counts": {"clean": 1},
            "paths": ["artifacts/benchmark_runs/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json"],
        },
        {
            "family": "other",
            "series": "misc_snapshot",
            "file_count": 1,
            "git_status_counts": {"clean": 1},
            "paths": ["artifacts/benchmark_runs/misc_snapshot.json"],
        },
        {
            "family": "scorecard",
            "series": "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10",
            "file_count": 1,
            "git_status_counts": {"M": 1},
            "paths": ["artifacts/benchmark_runs/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10_v1_scorecard.json"],
        },
    ]
    assert payload["noisy_files"] == [
        {
            "path": "artifacts/benchmark_runs/_debug_example.json",
            "git_status": "??",
            "family": "debug",
        },
        {
            "path": "artifacts/benchmark_runs/longmemeval_offset225_limit25_source.json",
            "git_status": "??",
            "family": "longmemeval",
        },
        {
            "path": "artifacts/benchmark_runs/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10_v1_scorecard.json",
            "git_status": "M",
            "family": "scorecard",
        },
    ]


def test_benchmark_runs_git_report_cli_only_noisy_filters_clean_families(tmp_path: Path, monkeypatch):
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    output_file = tmp_path / "artifacts" / "benchmark_runs_git_report.json"

    debug_file = benchmark_runs_dir / "_debug_example.json"
    scorecard_file = benchmark_runs_dir / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10_v1_scorecard.json"
    official_eval_file = benchmark_runs_dir / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json"
    benchmark_runs_dir.mkdir(parents=True)
    for path in [debug_file, scorecard_file, official_eval_file]:
        path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        cli,
        "_git_status_by_path",
        lambda paths, repo_root: {
            "artifacts/benchmark_runs/_debug_example.json": "??",
            "artifacts/benchmark_runs/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10_v1_scorecard.json": "M",
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "benchmark-runs-git-report",
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--only-noisy",
            "--write",
            str(output_file),
        ],
    )

    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["only_noisy"] is True
    assert payload["family_filter"] is None
    assert payload["noisy_family_counts"] == {"debug": 1, "scorecard": 1}
    assert payload["top_series_limit"] == 10
    assert payload["summary_only"] is False
    assert payload["paths_included"] is True
    assert payload["file_count"] == 3
    assert payload["git_status_counts"] == {"??": 1, "M": 1, "clean": 1}
    assert payload["reported_file_count"] == 2
    assert payload["reported_family_count"] == 2
    assert payload["reported_git_status_counts"] == {"??": 1, "M": 1}
    assert payload["reported_series_count"] == 2
    assert [row["family"] for row in payload["families"]] == ["debug", "scorecard"]
    assert [row["series"] for row in payload["top_noisy_series"]] == ["_debug", "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10"]
    assert payload["noisy_file_count"] == 2
    assert payload["listed_noisy_file_count"] == 2


def test_benchmark_runs_git_report_cli_groups_versions_into_series(tmp_path: Path, monkeypatch):
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    output_file = tmp_path / "artifacts" / "benchmark_runs_git_report.json"

    paths = [
        benchmark_runs_dir / "_debug_abc123.json",
        benchmark_runs_dir / "_debug_gpt4_def456.json",
        benchmark_runs_dir / "_debug_gpt4_ghi789.json",
        benchmark_runs_dir / "longmemeval_summary_synthesis_offset225_limit25_v1.json",
        benchmark_runs_dir / "longmemeval_summary_synthesis_offset225_limit25_v2.json",
        benchmark_runs_dir / "official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5_v2_scorecard.json",
        benchmark_runs_dir / "official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5_v3_scorecard.json",
    ]
    benchmark_runs_dir.mkdir(parents=True)
    for path in paths:
        path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        cli,
        "_git_status_by_path",
        lambda paths, repo_root: {
            "artifacts/benchmark_runs/_debug_abc123.json": "??",
            "artifacts/benchmark_runs/_debug_gpt4_def456.json": "??",
            "artifacts/benchmark_runs/_debug_gpt4_ghi789.json": "??",
            "artifacts/benchmark_runs/longmemeval_summary_synthesis_offset225_limit25_v1.json": "??",
            "artifacts/benchmark_runs/longmemeval_summary_synthesis_offset225_limit25_v2.json": "??",
            "artifacts/benchmark_runs/official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5_v2_scorecard.json": "??",
            "artifacts/benchmark_runs/official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5_v3_scorecard.json": "??",
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "benchmark-runs-git-report",
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--only-noisy",
            "--write",
            str(output_file),
        ],
    )

    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["reported_file_count"] == 7
    assert payload["reported_series_count"] == 4
    series_rows = {(row["family"], row["series"]): row for row in payload["series"]}
    assert series_rows[("debug", "_debug")]["file_count"] == 1
    assert series_rows[("debug", "_debug_gpt4")]["file_count"] == 2
    assert series_rows[("longmemeval", "longmemeval_summary_synthesis_offset225_limit25")]["file_count"] == 2
    assert series_rows[("scorecard", "official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5")]["file_count"] == 2


def test_benchmark_runs_git_report_cli_limits_top_series(tmp_path: Path, monkeypatch):
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    output_file = tmp_path / "artifacts" / "benchmark_runs_git_report.json"

    paths = [
        benchmark_runs_dir / "_debug_abc123.json",
        benchmark_runs_dir / "_debug_gpt4_def456.json",
        benchmark_runs_dir / "_debug_gpt4_ghi789.json",
        benchmark_runs_dir / "longmemeval_summary_synthesis_offset225_limit25_v1.json",
        benchmark_runs_dir / "longmemeval_summary_synthesis_offset225_limit25_v2.json",
        benchmark_runs_dir / "longmemeval_summary_synthesis_offset225_limit25_v3.json",
    ]
    benchmark_runs_dir.mkdir(parents=True)
    for path in paths:
        path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        cli,
        "_git_status_by_path",
        lambda paths, repo_root: {
            "artifacts/benchmark_runs/_debug_abc123.json": "??",
            "artifacts/benchmark_runs/_debug_gpt4_def456.json": "??",
            "artifacts/benchmark_runs/_debug_gpt4_ghi789.json": "??",
            "artifacts/benchmark_runs/longmemeval_summary_synthesis_offset225_limit25_v1.json": "??",
            "artifacts/benchmark_runs/longmemeval_summary_synthesis_offset225_limit25_v2.json": "??",
            "artifacts/benchmark_runs/longmemeval_summary_synthesis_offset225_limit25_v3.json": "??",
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "benchmark-runs-git-report",
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--only-noisy",
            "--top-series-limit",
            "1",
            "--write",
            str(output_file),
        ],
    )

    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["top_series_limit"] == 1
    assert payload["reported_series_count"] == 3
    assert [row["series"] for row in payload["top_noisy_series"]] == ["longmemeval_summary_synthesis_offset225_limit25"]


def test_benchmark_runs_git_report_cli_summary_only_omits_paths_and_full_noisy_file_list(tmp_path: Path, monkeypatch):
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    output_file = tmp_path / "artifacts" / "benchmark_runs_git_report.json"

    paths = [
        benchmark_runs_dir / "_debug_abc123.json",
        benchmark_runs_dir / "longmemeval_summary_synthesis_offset225_limit25_v1.json",
        benchmark_runs_dir / "longmemeval_summary_synthesis_offset225_limit25_v2.json",
    ]
    benchmark_runs_dir.mkdir(parents=True)
    for path in paths:
        path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        cli,
        "_git_status_by_path",
        lambda paths, repo_root: {
            "artifacts/benchmark_runs/_debug_abc123.json": "??",
            "artifacts/benchmark_runs/longmemeval_summary_synthesis_offset225_limit25_v1.json": "??",
            "artifacts/benchmark_runs/longmemeval_summary_synthesis_offset225_limit25_v2.json": "??",
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "benchmark-runs-git-report",
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--only-noisy",
            "--summary-only",
            "--top-series-limit",
            "1",
            "--write",
            str(output_file),
        ],
    )

    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["summary_only"] is True
    assert payload["paths_included"] is False
    assert payload["noisy_file_count"] == 3
    assert payload["listed_noisy_file_count"] == 0
    assert payload["noisy_files"] == []
    assert all("paths" not in row for row in payload["families"])
    assert all("paths" not in row for row in payload["series"])
    assert all("paths" not in row for row in payload["top_noisy_series"])
    assert [row["series"] for row in payload["top_noisy_series"]] == ["longmemeval_summary_synthesis_offset225_limit25"]


def test_benchmark_runs_git_report_cli_filters_to_one_family(tmp_path: Path, monkeypatch):
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    output_file = tmp_path / "artifacts" / "benchmark_runs_git_report.json"

    paths = [
        benchmark_runs_dir / "_debug_abc123.json",
        benchmark_runs_dir / "longmemeval_summary_synthesis_offset225_limit25_v1.json",
        benchmark_runs_dir / "longmemeval_summary_synthesis_offset225_limit25_v2.json",
        benchmark_runs_dir / "official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5_v2_scorecard.json",
    ]
    benchmark_runs_dir.mkdir(parents=True)
    for path in paths:
        path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        cli,
        "_git_status_by_path",
        lambda paths, repo_root: {
            "artifacts/benchmark_runs/_debug_abc123.json": "??",
            "artifacts/benchmark_runs/longmemeval_summary_synthesis_offset225_limit25_v1.json": "??",
            "artifacts/benchmark_runs/longmemeval_summary_synthesis_offset225_limit25_v2.json": "??",
            "artifacts/benchmark_runs/official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5_v2_scorecard.json": "??",
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "benchmark-runs-git-report",
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--only-noisy",
            "--summary-only",
            "--family",
            "longmemeval",
            "--write",
            str(output_file),
        ],
    )

    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["family_filter"] == "longmemeval"
    assert payload["available_families"] == ["debug", "longmemeval", "scorecard"]
    assert payload["noisy_family_counts"] == {"debug": 1, "longmemeval": 2, "scorecard": 1}
    assert payload["file_count"] == 4
    assert payload["reported_file_count"] == 2
    assert payload["reported_family_count"] == 1
    assert payload["reported_series_count"] == 1
    assert payload["reported_git_status_counts"] == {"??": 2}
    assert payload["noisy_file_count"] == 2
    assert payload["listed_noisy_file_count"] == 0
    assert payload["families"] == [
        {
            "family": "longmemeval",
            "file_count": 2,
            "git_status_counts": {"??": 2},
            "reported_file_share": 1.0,
            "dominance_label": "dominant",
            "family_rank": 1,
        }
    ]
    assert payload["top_noisy_series"] == [
        {
            "family": "longmemeval",
            "series": "longmemeval_summary_synthesis_offset225_limit25",
            "file_count": 2,
            "git_status_counts": {"??": 2},
        }
    ]
    assert payload["recommended_focus"] == {
        "scope": "series",
        "reason": "largest_series_in_family",
        "family": "longmemeval",
        "series_prefix": "longmemeval_summary_synthesis_offset225_limit25",
        "noisy_file_count": 2,
        "command": [
            "python",
            "-m",
            "domain_chip_memory.cli",
            "benchmark-runs-git-report",
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--family",
            "longmemeval",
            "--series-prefix",
            "longmemeval_summary_synthesis_offset225_limit25",
            "--only-noisy",
            "--summary-only",
            "--top-series-limit",
            "10",
        ],
        "command_shell": (
            f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
            f"--repo-root {tmp_path} --family longmemeval --series-prefix longmemeval_summary_synthesis_offset225_limit25 "
            f"--only-noisy --summary-only --top-series-limit 10"
        ),
    }
    assert payload["recommended_drilldown"] == payload["recommended_focus"]
    assert payload["recommended_family"] == {
        "family": "longmemeval",
        "file_count": 2,
        "git_status_counts": {"??": 2},
        "reported_file_share": 1.0,
        "dominance_label": "dominant",
        "family_rank": 1,
    }
    assert payload["recommended_family_gap"] == {
        "scope": "gap_to_next_family",
        "family": "longmemeval",
        "next_family": "scorecard",
        "next_family_noisy_file_count": 1,
        "noisy_file_count_gap": 1,
        "noisy_share_gap": 0.25,
        "lead_label": "wide",
        "next_family_command": [
            "python",
            "-m",
            "domain_chip_memory.cli",
            "benchmark-runs-git-report",
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--family",
            "scorecard",
            "--only-noisy",
            "--summary-only",
            "--top-series-limit",
            "10",
        ],
        "next_family_command_shell": (
            f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
            f"--repo-root {tmp_path} --family scorecard --only-noisy --summary-only --top-series-limit 10"
        ),
        "next_family_series_prefix": "official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5",
        "next_family_series_noisy_file_count": 1,
        "next_family_drilldown_command": [
            "python",
            "-m",
            "domain_chip_memory.cli",
            "benchmark-runs-git-report",
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--family",
            "scorecard",
            "--series-prefix",
            "official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5",
            "--only-noisy",
            "--summary-only",
            "--top-series-limit",
            "10",
        ],
        "next_family_drilldown_command_shell": (
            f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
            f"--repo-root {tmp_path} --family scorecard --series-prefix official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5 "
            f"--only-noisy --summary-only --top-series-limit 10"
        ),
    }
    assert payload["recommended_family_competition_window"] == {
        "scope": "competition_window",
        "family": "longmemeval",
        "current": payload["family_competition"][0],
        "previous": None,
        "next": payload["family_competition"][1],
    }
    assert payload["recommended_family_competition_summary"] == {
        "scope": "competition_summary",
        "family": "longmemeval",
        "rank": 1,
        "top_series_prefix": "longmemeval_summary_synthesis_offset225_limit25",
        "top_series_noisy_file_count": 2,
        "competition_position_label": "dominant_leader",
        "command": payload["family_competition"][0]["command"],
        "command_shell": payload["family_competition"][0]["command_shell"],
        "top_series_command": payload["family_competition"][0]["top_series_command"],
        "top_series_command_shell": payload["family_competition"][0]["top_series_command_shell"],
        "recommended_next_step": {
            "reason": "inspect_current_top_series",
            "target": "current_top_series",
            "family": "longmemeval",
            "rank": 1,
            "top_series_prefix": "longmemeval_summary_synthesis_offset225_limit25",
            "top_series_noisy_file_count": 2,
            "command": payload["family_competition"][0]["top_series_command"],
            "command_shell": payload["family_competition"][0]["top_series_command_shell"],
        },
        "nearest_competitor": {
            "direction": "next",
            "family": "scorecard",
            "rank": 2,
            "noisy_file_count_gap": 1,
            "noisy_share_gap": 0.25,
            "top_series_prefix": "official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5",
            "top_series_noisy_file_count": 1,
            "command": payload["family_competition"][1]["command"],
            "command_shell": payload["family_competition"][1]["command_shell"],
            "top_series_command": payload["family_competition"][1]["top_series_command"],
            "top_series_command_shell": payload["family_competition"][1]["top_series_command_shell"],
        },
    }
    assert payload["recommended_next_step"] == payload["recommended_family_competition_summary"]["recommended_next_step"]
    assert payload["recommended_sequence"] == [
        payload["recommended_focus"],
        payload["recommended_next_step"],
    ]
    assert payload["recommended_sequence_targets"] == [
        {
            "type": "series",
            "family": "longmemeval",
            "series_prefix": "longmemeval_summary_synthesis_offset225_limit25",
        },
        {
            "type": "top_series",
            "target": "current_top_series",
            "family": "longmemeval",
            "rank": 1,
            "series_prefix": "longmemeval_summary_synthesis_offset225_limit25",
        },
    ]
    assert payload["recommended_sequence_labels"] == [
        "focus series longmemeval / longmemeval_summary_synthesis_offset225_limit25",
        "inspect longmemeval rank 1 / longmemeval_summary_synthesis_offset225_limit25",
    ]
    assert payload["recommended_sequence_preview"] == (
        "focus series longmemeval / longmemeval_summary_synthesis_offset225_limit25 -> "
        "inspect longmemeval rank 1 / longmemeval_summary_synthesis_offset225_limit25"
    )
    assert payload["recommended_sequence_commands"] == [
        payload["recommended_focus"]["command"],
    ]
    assert payload["recommended_sequence_shells"] == [
        payload["recommended_focus"]["command_shell"],
    ]
    assert payload["recommended_sequence_steps"] == [
        {
            "step": 1,
            "phase": "focus",
            "label": payload["recommended_sequence_labels"][0],
            "target": payload["recommended_sequence_targets"][0],
            "command": payload["recommended_focus"]["command"],
            "command_shell": payload["recommended_focus"]["command_shell"],
        },
        {
            "step": 2,
            "phase": "next_step",
            "label": payload["recommended_sequence_labels"][1],
            "target": payload["recommended_sequence_targets"][1],
            "command": payload["recommended_next_step"]["command"],
            "command_shell": payload["recommended_next_step"]["command_shell"],
        },
    ]
    assert payload["recommended_sequence_by_phase"] == {
        "focus": payload["recommended_sequence_steps"][0],
        "next_step": payload["recommended_sequence_steps"][1],
    }
    assert payload["family_competition"] == [
        {
            "rank": 1,
            "family": "longmemeval",
            "noisy_file_count": 2,
            "noisy_file_share": 0.5,
            "noisy_file_count_gap_from_leader": 0,
            "noisy_share_gap_from_leader": 0.0,
            "previous_family": None,
            "previous_noisy_file_count_gap": None,
            "previous_noisy_share_gap": None,
            "next_family": "scorecard",
            "next_noisy_file_count_gap": 1,
            "next_noisy_share_gap": 0.25,
            "nearest_competitor_direction": "next",
            "nearest_competitor_family": "scorecard",
            "nearest_competitor_rank": 2,
            "nearest_competitor_noisy_file_count_gap": 1,
            "nearest_competitor_noisy_share_gap": 0.25,
            "nearest_competitor_top_series_prefix": "official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5",
            "nearest_competitor_top_series_noisy_file_count": 1,
            "nearest_competitor_command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "scorecard",
                "--only-noisy",
                "--summary-only",
                "--top-series-limit",
                "10",
            ],
            "nearest_competitor_command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family scorecard --only-noisy --summary-only --top-series-limit 10"
            ),
            "nearest_competitor_top_series_command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "scorecard",
                "--series-prefix",
                "official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5",
                "--only-noisy",
                "--summary-only",
                "--top-series-limit",
                "10",
            ],
            "nearest_competitor_top_series_command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family scorecard --series-prefix official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5 "
                f"--only-noisy --summary-only --top-series-limit 10"
            ),
            "competition_position_label": "dominant_leader",
            "gap_label": "leader",
            "top_series_prefix": "longmemeval_summary_synthesis_offset225_limit25",
            "top_series_noisy_file_count": 2,
            "top_series_command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "longmemeval",
                "--series-prefix",
                "longmemeval_summary_synthesis_offset225_limit25",
                "--only-noisy",
                "--summary-only",
                "--top-series-limit",
                "10",
            ],
            "top_series_command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family longmemeval --series-prefix longmemeval_summary_synthesis_offset225_limit25 "
                f"--only-noisy --summary-only --top-series-limit 10"
            ),
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "longmemeval",
                "--only-noisy",
                "--summary-only",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family longmemeval --only-noisy --summary-only --top-series-limit 10"
            ),
        },
        {
            "rank": 2,
            "family": "scorecard",
            "noisy_file_count": 1,
            "noisy_file_share": 0.25,
            "noisy_file_count_gap_from_leader": 1,
            "noisy_share_gap_from_leader": 0.25,
            "previous_family": "longmemeval",
            "previous_noisy_file_count_gap": 1,
            "previous_noisy_share_gap": 0.25,
            "next_family": "debug",
            "next_noisy_file_count_gap": 0,
            "next_noisy_share_gap": 0.0,
            "nearest_competitor_direction": "next",
            "nearest_competitor_family": "debug",
            "nearest_competitor_rank": 3,
            "nearest_competitor_noisy_file_count_gap": 0,
            "nearest_competitor_noisy_share_gap": 0.0,
            "nearest_competitor_top_series_prefix": "_debug",
            "nearest_competitor_top_series_noisy_file_count": 1,
            "nearest_competitor_command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "debug",
                "--only-noisy",
                "--summary-only",
                "--top-series-limit",
                "10",
            ],
            "nearest_competitor_command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family debug --only-noisy --summary-only --top-series-limit 10"
            ),
            "nearest_competitor_top_series_command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "debug",
                "--series-prefix",
                "_debug",
                "--only-noisy",
                "--summary-only",
                "--top-series-limit",
                "10",
            ],
            "nearest_competitor_top_series_command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family debug --series-prefix _debug --only-noisy --summary-only --top-series-limit 10"
            ),
            "competition_position_label": "neck_and_neck",
            "gap_label": "wide",
            "top_series_prefix": "official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5",
            "top_series_noisy_file_count": 1,
            "top_series_command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "scorecard",
                "--series-prefix",
                "official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5",
                "--only-noisy",
                "--summary-only",
                "--top-series-limit",
                "10",
            ],
            "top_series_command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family scorecard --series-prefix official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5 "
                f"--only-noisy --summary-only --top-series-limit 10"
            ),
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "scorecard",
                "--only-noisy",
                "--summary-only",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family scorecard --only-noisy --summary-only --top-series-limit 10"
            ),
        },
        {
            "rank": 3,
            "family": "debug",
            "noisy_file_count": 1,
            "noisy_file_share": 0.25,
            "noisy_file_count_gap_from_leader": 1,
            "noisy_share_gap_from_leader": 0.25,
            "previous_family": "scorecard",
            "previous_noisy_file_count_gap": 0,
            "previous_noisy_share_gap": 0.0,
            "next_family": None,
            "next_noisy_file_count_gap": None,
            "next_noisy_share_gap": None,
            "nearest_competitor_direction": "previous",
            "nearest_competitor_family": "scorecard",
            "nearest_competitor_rank": 2,
            "nearest_competitor_noisy_file_count_gap": 0,
            "nearest_competitor_noisy_share_gap": 0.0,
            "nearest_competitor_top_series_prefix": "official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5",
            "nearest_competitor_top_series_noisy_file_count": 1,
            "nearest_competitor_command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "scorecard",
                "--only-noisy",
                "--summary-only",
                "--top-series-limit",
                "10",
            ],
            "nearest_competitor_command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family scorecard --only-noisy --summary-only --top-series-limit 10"
            ),
            "nearest_competitor_top_series_command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "scorecard",
                "--series-prefix",
                "official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5",
                "--only-noisy",
                "--summary-only",
                "--top-series-limit",
                "10",
            ],
            "nearest_competitor_top_series_command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family scorecard --series-prefix official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5 "
                f"--only-noisy --summary-only --top-series-limit 10"
            ),
            "competition_position_label": "neck_and_neck",
            "gap_label": "wide",
            "top_series_prefix": "_debug",
            "top_series_noisy_file_count": 1,
            "top_series_command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "debug",
                "--series-prefix",
                "_debug",
                "--only-noisy",
                "--summary-only",
                "--top-series-limit",
                "10",
            ],
            "top_series_command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family debug --series-prefix _debug --only-noisy --summary-only --top-series-limit 10"
            ),
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "debug",
                "--only-noisy",
                "--summary-only",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family debug --only-noisy --summary-only --top-series-limit 10"
            ),
        },
    ]
    assert payload["recommended_family_comparison"] == {
        "scope": "leader_vs_runner_up",
        "leader_hotspot": {
            "family": "longmemeval",
            "family_noisy_file_count": 2,
            "series_count": 1,
            "top_series_prefix": "longmemeval_summary_synthesis_offset225_limit25",
            "top_series_noisy_file_count": 2,
            "top_series_share": 1.0,
            "average_series_size": 2.0,
            "concentration_label": "concentrated",
            "focus_mode": "series_first",
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "longmemeval",
                "--series-prefix",
                "longmemeval_summary_synthesis_offset225_limit25",
                "--only-noisy",
                "--summary-only",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family longmemeval --series-prefix longmemeval_summary_synthesis_offset225_limit25 "
                f"--only-noisy --summary-only --top-series-limit 10"
            ),
        },
        "runner_up_hotspot": {
            "family": "scorecard",
            "family_noisy_file_count": 1,
            "series_count": 1,
            "top_series_prefix": "official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5",
            "top_series_noisy_file_count": 1,
            "top_series_share": 1.0,
            "average_series_size": 1.0,
            "concentration_label": "concentrated",
            "focus_mode": "series_first",
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "scorecard",
                "--series-prefix",
                "official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5",
                "--only-noisy",
                "--summary-only",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family scorecard --series-prefix official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5 "
                f"--only-noisy --summary-only --top-series-limit 10"
            ),
        },
        "gap": payload["recommended_family_gap"],
    }
    assert payload["recommended_followups"] == [payload["recommended_focus"]]
    assert payload["recommended_hotspot"] == payload["family_hotspots"][0]
    assert payload["family_hotspots"] == [
        {
            "family": "longmemeval",
            "family_file_count": 2,
            "series_count": 1,
            "top_series_prefix": "longmemeval_summary_synthesis_offset225_limit25",
            "top_series_file_count": 2,
            "top_series_share": 1.0,
            "average_series_size": 2.0,
            "concentration_label": "concentrated",
            "focus_mode": "series_first",
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "longmemeval",
                "--series-prefix",
                "longmemeval_summary_synthesis_offset225_limit25",
                "--only-noisy",
                "--summary-only",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family longmemeval --series-prefix longmemeval_summary_synthesis_offset225_limit25 "
                f"--only-noisy --summary-only --top-series-limit 10"
            ),
        }
    ]
    assert payload["series_commands"] == [
        {
            "family": "longmemeval",
            "series_prefix": "longmemeval_summary_synthesis_offset225_limit25",
            "noisy_file_count": 2,
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "longmemeval",
                "--series-prefix",
                "longmemeval_summary_synthesis_offset225_limit25",
                "--only-noisy",
                "--summary-only",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family longmemeval --series-prefix longmemeval_summary_synthesis_offset225_limit25 "
                f"--only-noisy --summary-only --top-series-limit 10"
            ),
        }
    ]
    assert [row["family"] for row in payload["family_commands"]] == ["debug", "longmemeval", "scorecard"]
    longmemeval_command = next(row for row in payload["family_commands"] if row["family"] == "longmemeval")
    assert "--family" in longmemeval_command["command"]
    assert "longmemeval" in longmemeval_command["command"]
    assert "--summary-only" in longmemeval_command["command"]


def test_benchmark_runs_git_report_cli_filters_to_series_prefix(tmp_path: Path, monkeypatch):
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    output_file = tmp_path / "artifacts" / "benchmark_runs_git_report.json"

    paths = [
        benchmark_runs_dir / "longmemeval_summary_synthesis_offset225_limit25_v1.json",
        benchmark_runs_dir / "longmemeval_summary_synthesis_offset225_limit25_v2.json",
        benchmark_runs_dir / "longmemeval_summary_synthesis_offset275_limit25_v1.json",
        benchmark_runs_dir / "official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5_v2_scorecard.json",
    ]
    benchmark_runs_dir.mkdir(parents=True)
    for path in paths:
        path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        cli,
        "_git_status_by_path",
        lambda paths, repo_root: {
            "artifacts/benchmark_runs/longmemeval_summary_synthesis_offset225_limit25_v1.json": "??",
            "artifacts/benchmark_runs/longmemeval_summary_synthesis_offset225_limit25_v2.json": "??",
            "artifacts/benchmark_runs/longmemeval_summary_synthesis_offset275_limit25_v1.json": "??",
            "artifacts/benchmark_runs/official_beam_500k_summary_synthesis_memory_heuristic_v1_conv1_5_v2_scorecard.json": "??",
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "benchmark-runs-git-report",
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--only-noisy",
            "--summary-only",
            "--series-prefix",
            "longmemeval_summary_synthesis_offset225_limit25",
            "--write",
            str(output_file),
        ],
    )

    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["series_prefix"] == "longmemeval_summary_synthesis_offset225_limit25"
    assert payload["file_count"] == 4
    assert payload["reported_file_count"] == 2
    assert payload["reported_family_count"] == 1
    assert payload["reported_series_count"] == 1
    assert payload["reported_git_status_counts"] == {"??": 2}
    assert payload["noisy_file_count"] == 2
    assert payload["listed_noisy_file_count"] == 0
    assert payload["families"] == [
        {
            "family": "longmemeval",
            "file_count": 2,
            "git_status_counts": {"??": 2},
            "reported_file_share": 1.0,
            "dominance_label": "dominant",
            "family_rank": 1,
        }
    ]
    assert payload["series"] == [
        {
            "family": "longmemeval",
            "series": "longmemeval_summary_synthesis_offset225_limit25",
            "file_count": 2,
            "git_status_counts": {"??": 2},
        }
    ]
    assert payload["top_noisy_series"] == [
        {
            "family": "longmemeval",
            "series": "longmemeval_summary_synthesis_offset225_limit25",
            "file_count": 2,
            "git_status_counts": {"??": 2},
        }
    ]
    assert "--series-prefix" in payload["current_command"]
    assert "longmemeval_summary_synthesis_offset225_limit25" in payload["current_command"]
    assert payload["recommended_focus"] == {
        "scope": "series",
        "status": "already_focused",
        "family": None,
        "series_prefix": "longmemeval_summary_synthesis_offset225_limit25",
        "reported_file_count": 2,
    }
    assert payload["recommended_drilldown"] == payload["recommended_focus"]
    assert payload["recommended_family"] == {
        "family": "longmemeval",
        "file_count": 2,
        "git_status_counts": {"??": 2},
        "reported_file_share": 1.0,
        "dominance_label": "dominant",
        "family_rank": 1,
    }
    assert payload["recommended_family_gap"] == {
        "scope": "single_family_view",
        "family": "longmemeval",
        "reported_file_share": 1.0,
        "dominance_label": "dominant",
    }
    assert payload["recommended_family_competition_window"] == {
        "scope": "competition_window",
        "family": "longmemeval",
        "current": payload["family_competition"][0],
        "previous": None,
        "next": None,
    }
    assert payload["recommended_family_competition_summary"] == {
        "scope": "competition_summary",
        "family": "longmemeval",
        "rank": 1,
        "top_series_prefix": "longmemeval_summary_synthesis_offset225_limit25",
        "top_series_noisy_file_count": 2,
        "competition_position_label": "solo",
        "command": payload["family_competition"][0]["command"],
        "command_shell": payload["family_competition"][0]["command_shell"],
        "top_series_command": payload["family_competition"][0]["top_series_command"],
        "top_series_command_shell": payload["family_competition"][0]["top_series_command_shell"],
        "recommended_next_step": {
            "reason": "inspect_current_top_series",
            "target": "current_top_series",
            "family": "longmemeval",
            "rank": 1,
            "top_series_prefix": "longmemeval_summary_synthesis_offset225_limit25",
            "top_series_noisy_file_count": 2,
            "command": payload["family_competition"][0]["top_series_command"],
            "command_shell": payload["family_competition"][0]["top_series_command_shell"],
        },
        "nearest_competitor": {
            "direction": None,
            "family": None,
            "rank": None,
            "noisy_file_count_gap": None,
            "noisy_share_gap": None,
            "top_series_prefix": None,
            "top_series_noisy_file_count": None,
            "command": None,
            "command_shell": None,
            "top_series_command": None,
            "top_series_command_shell": None,
        },
    }
    assert payload["recommended_next_step"] == payload["recommended_family_competition_summary"]["recommended_next_step"]
    assert payload["recommended_sequence"] == [
        payload["recommended_focus"],
        payload["recommended_next_step"],
    ]
    assert payload["recommended_sequence_targets"] == [
        {
            "type": "series",
            "family": None,
            "series_prefix": "longmemeval_summary_synthesis_offset225_limit25",
        },
        {
            "type": "top_series",
            "target": "current_top_series",
            "family": "longmemeval",
            "rank": 1,
            "series_prefix": "longmemeval_summary_synthesis_offset225_limit25",
        },
    ]
    assert payload["recommended_sequence_labels"] == [
        "focus series longmemeval_summary_synthesis_offset225_limit25",
        "inspect longmemeval rank 1 / longmemeval_summary_synthesis_offset225_limit25",
    ]
    assert payload["recommended_sequence_preview"] == (
        "focus series longmemeval_summary_synthesis_offset225_limit25 -> "
        "inspect longmemeval rank 1 / longmemeval_summary_synthesis_offset225_limit25"
    )
    assert payload["recommended_sequence_commands"] == [
        payload["recommended_next_step"]["command"],
    ]
    assert payload["recommended_sequence_shells"] == [
        payload["recommended_next_step"]["command_shell"],
    ]
    assert payload["recommended_sequence_steps"] == [
        {
            "step": 1,
            "phase": "focus",
            "label": payload["recommended_sequence_labels"][0],
            "target": payload["recommended_sequence_targets"][0],
            "command": payload["recommended_focus"].get("command"),
            "command_shell": payload["recommended_focus"].get("command_shell"),
        },
        {
            "step": 2,
            "phase": "next_step",
            "label": payload["recommended_sequence_labels"][1],
            "target": payload["recommended_sequence_targets"][1],
            "command": payload["recommended_next_step"]["command"],
            "command_shell": payload["recommended_next_step"]["command_shell"],
        },
    ]
    assert payload["recommended_sequence_by_phase"] == {
        "focus": payload["recommended_sequence_steps"][0],
        "next_step": payload["recommended_sequence_steps"][1],
    }
    assert payload["family_competition"] == [
        {
            "rank": 1,
            "family": "longmemeval",
            "noisy_file_count": 2,
            "noisy_file_share": 1.0,
            "noisy_file_count_gap_from_leader": 0,
            "noisy_share_gap_from_leader": 0.0,
            "previous_family": None,
            "previous_noisy_file_count_gap": None,
            "previous_noisy_share_gap": None,
            "next_family": None,
            "next_noisy_file_count_gap": None,
            "next_noisy_share_gap": None,
            "nearest_competitor_direction": None,
            "nearest_competitor_family": None,
            "nearest_competitor_rank": None,
            "nearest_competitor_noisy_file_count_gap": None,
            "nearest_competitor_noisy_share_gap": None,
            "nearest_competitor_top_series_prefix": None,
            "nearest_competitor_top_series_noisy_file_count": None,
            "nearest_competitor_command": None,
            "nearest_competitor_command_shell": None,
            "nearest_competitor_top_series_command": None,
            "nearest_competitor_top_series_command_shell": None,
            "competition_position_label": "solo",
            "gap_label": "leader",
            "top_series_prefix": "longmemeval_summary_synthesis_offset225_limit25",
            "top_series_noisy_file_count": 2,
            "top_series_command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "longmemeval",
                "--series-prefix",
                "longmemeval_summary_synthesis_offset225_limit25",
                "--only-noisy",
                "--summary-only",
                "--top-series-limit",
                "10",
            ],
            "top_series_command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family longmemeval --series-prefix longmemeval_summary_synthesis_offset225_limit25 "
                f"--only-noisy --summary-only --top-series-limit 10"
            ),
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "longmemeval",
                "--only-noisy",
                "--summary-only",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family longmemeval --only-noisy --summary-only --top-series-limit 10"
            ),
        },
    ]
    assert payload["recommended_family_comparison"] == {
        "scope": "single_family_view",
        "leader_hotspot": {
            "family": "longmemeval",
            "family_noisy_file_count": 3,
            "series_count": 2,
            "top_series_prefix": "longmemeval_summary_synthesis_offset225_limit25",
            "top_series_noisy_file_count": 2,
            "top_series_share": 0.6667,
            "average_series_size": 1.5,
            "concentration_label": "concentrated",
            "focus_mode": "series_first",
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "longmemeval",
                "--series-prefix",
                "longmemeval_summary_synthesis_offset225_limit25",
                "--only-noisy",
                "--summary-only",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family longmemeval --series-prefix longmemeval_summary_synthesis_offset225_limit25 "
                f"--only-noisy --summary-only --top-series-limit 10"
            ),
        },
    }
    assert payload["recommended_followups"] == []
    assert payload["recommended_hotspot"] == payload["family_hotspots"][0]
    assert payload["family_hotspots"] == [
        {
            "family": "longmemeval",
            "family_file_count": 2,
            "series_count": 1,
            "top_series_prefix": "longmemeval_summary_synthesis_offset225_limit25",
            "top_series_file_count": 2,
            "top_series_share": 1.0,
            "average_series_size": 2.0,
            "concentration_label": "concentrated",
            "focus_mode": "series_first",
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "longmemeval",
                "--series-prefix",
                "longmemeval_summary_synthesis_offset225_limit25",
                "--only-noisy",
                "--summary-only",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family longmemeval --series-prefix longmemeval_summary_synthesis_offset225_limit25 "
                f"--only-noisy --summary-only --top-series-limit 10"
            ),
        }
    ]
    assert payload["series_commands"] == [
        {
            "family": "longmemeval",
            "series_prefix": "longmemeval_summary_synthesis_offset225_limit25",
            "noisy_file_count": 2,
            "command": [
                "python",
                "-m",
                "domain_chip_memory.cli",
                "benchmark-runs-git-report",
                "--benchmark-runs-dir",
                str(benchmark_runs_dir),
                "--repo-root",
                str(tmp_path),
                "--family",
                "longmemeval",
                "--series-prefix",
                "longmemeval_summary_synthesis_offset225_limit25",
                "--only-noisy",
                "--summary-only",
                "--top-series-limit",
                "10",
            ],
            "command_shell": (
                f"python -m domain_chip_memory.cli benchmark-runs-git-report --benchmark-runs-dir {benchmark_runs_dir} "
                f"--repo-root {tmp_path} --family longmemeval --series-prefix longmemeval_summary_synthesis_offset225_limit25 "
                f"--only-noisy --summary-only --top-series-limit 10"
            ),
        }
    ]
    assert [row["family"] for row in payload["family_commands"]] == ["longmemeval"]
    longmemeval_command = next(row for row in payload["family_commands"] if row["family"] == "longmemeval")
    assert "--series-prefix" in longmemeval_command["command"]
    assert "longmemeval_summary_synthesis_offset225_limit25" in longmemeval_command["command"]


def test_git_status_by_path_batches_large_path_sets(tmp_path: Path, monkeypatch):
    paths = []
    for index in range(205):
        path = tmp_path / "artifacts" / "benchmark_runs" / f"file_{index:03d}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
        paths.append(path)

    batch_lengths: list[int] = []

    def fake_run(cmd, check, capture_output, text):
        batch = cmd[6:]
        batch_lengths.append(len(batch))
        stdout = "\n".join(f"?? {path}" for path in batch[:1])
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    payload = cli._git_status_by_path(paths, repo_root=tmp_path)

    assert batch_lengths == [100, 100, 5]
    assert payload["artifacts/benchmark_runs/file_000.json"] == "??"
    assert payload["artifacts/benchmark_runs/file_100.json"] == "??"
    assert payload["artifacts/benchmark_runs/file_200.json"] == "??"


def test_beam_judged_cleanup_report_cli_summarizes_artifact_state(tmp_path: Path, monkeypatch):
    answers_root = tmp_path / "beam_public_results"
    benchmark_runs_dir = tmp_path / "benchmark_runs"
    upstream_repo_dir = tmp_path / "beam_upstream"
    output_file = tmp_path / "artifacts" / "beam_cleanup_report.json"

    conv1_dir = answers_root / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9" / "100K" / "1"
    conv2_dir = answers_root / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv2_v2" / "100K" / "2"
    eval_one = conv1_dir / "evaluation-domain_chip_memory_answers.json"
    eval_two = conv2_dir / "evaluation-domain_chip_memory_answers.json"
    answers_one = conv1_dir / "domain_chip_memory_answers.json"
    answers_two = conv2_dir / "domain_chip_memory_answers.json"
    eval_one.parent.mkdir(parents=True)
    eval_two.parent.mkdir(parents=True)
    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions").mkdir(parents=True)
    (upstream_repo_dir / "chats" / "100K" / "2" / "probing_questions").mkdir(parents=True)
    eval_one.write_text(
        json.dumps(
            {
                "information_extraction": [{"llm_judge_score": 1.0}],
                "event_ordering": [{"tau_norm": 0.5}],
            }
        ),
        encoding="utf-8",
    )
    eval_two.write_text(
        json.dumps(
            {
                "information_extraction": [{"llm_judge_score": 0.5}],
                "event_ordering": [{"tau_norm": 1.0}],
            }
        ),
        encoding="utf-8",
    )
    answers_one.write_text(
        json.dumps(
            {
                "information_extraction": [{"question": "q1", "llm_response": "a1"}],
                "event_ordering": [{"question": "q2", "llm_response": "a2"}],
            }
        ),
        encoding="utf-8",
    )
    answers_two.write_text(
        json.dumps(
            {
                "information_extraction": [{"question": "q3", "llm_response": "a3"}],
                "event_ordering": [{"question": "q4", "llm_response": "a4"}],
            }
        ),
        encoding="utf-8",
    )
    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps(
            {
                "information_extraction": [{"rubric": ["extract"]}],
                "event_ordering": [{"rubric": ["order"]}],
            }
        ),
        encoding="utf-8",
    )
    (upstream_repo_dir / "chats" / "100K" / "2" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps(
            {
                "information_extraction": [{"rubric": ["extract"]}],
                "event_ordering": [{"rubric": ["order"]}],
            }
        ),
        encoding="utf-8",
    )

    benchmark_runs_dir.mkdir(parents=True)
    (benchmark_runs_dir / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "upstream_repo_dir": str(upstream_repo_dir),
                "official_chat_size_dir": "100K",
                "conversation_ids": ["1"],
                "input_directory": str(conv1_dir.parent),
                "result_file_name": "domain_chip_memory_answers.json",
                "judge_config": {"provider": "official_openai"},
                "evaluation_files": [str(eval_one)],
                "aggregate_summary": {"overall_average": 0.75},
            }
        ),
        encoding="utf-8",
    )
    (benchmark_runs_dir / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv10_v1_scorecard.json").write_text(
        json.dumps({"run_manifest": {"benchmark_name": "BEAM"}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "beam-judged-cleanup-report",
            "--artifact-prefix",
            "official_beam_128k_summary_synthesis_memory_heuristic_v1_",
            "--answers-root",
            str(answers_root),
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["benchmark_name"] == "BEAM"
    assert payload["artifact_prefix"] == "official_beam_128k_summary_synthesis_memory_heuristic_v1_"
    assert payload["answer_variant_count"] == 2
    assert payload["evaluation_file_count"] == 2
    assert payload["official_eval_manifest_count"] == 1
    assert payload["runnable_official_eval_manifest_count"] == 1
    assert payload["blocked_official_eval_manifest_count"] == 0
    assert payload["blocked_missing_env_vars"] == []
    assert payload["promotable_untracked_official_eval_manifest_count"] == 0
    assert payload["promotable_untracked_official_eval_manifests"] == []
    assert payload["scorecard_count"] == 1
    assert payload["aggregate_evaluation_summary"]["evaluation_file_count"] == 2
    assert payload["aggregate_evaluation_summary"]["overall_average"] == 0.75
    assert payload["category_universe"] == ["event_ordering", "information_extraction"]
    assert payload["max_category_count_seen"] == 2
    assert payload["evaluation_files"][0]["path"].endswith("conv1_v9/100K/1/evaluation-domain_chip_memory_answers.json")
    assert payload["official_eval_manifests"][0]["status"] == "completed"
    assert payload["official_eval_manifests"][0]["expected_categories"] == ["event_ordering", "information_extraction"]
    assert payload["official_eval_manifests"][0]["answer_categories"] == ["event_ordering", "information_extraction"]
    assert payload["official_eval_manifests"][0]["completed_category_order"] == ["information_extraction", "event_ordering"]
    assert payload["official_eval_manifests"][0]["expected_category_order"] == ["information_extraction", "event_ordering"]
    assert payload["official_eval_manifests"][0]["answer_category_order"] == ["information_extraction", "event_ordering"]
    assert payload["official_eval_manifests"][0]["category_progress"] == [
        {
            "category": "information_extraction",
            "expected_question_count": 1,
            "answer_question_count": 1,
            "completed_question_count": 1,
            "status": "completed",
        },
        {
            "category": "event_ordering",
            "expected_question_count": 1,
            "answer_question_count": 1,
            "completed_question_count": 1,
            "status": "completed",
        },
    ]
    assert payload["official_eval_manifests"][0]["last_completed_category"] == "event_ordering"
    assert payload["official_eval_manifests"][0]["last_completed_question_index"] == 0
    assert payload["official_eval_manifests"][0]["next_pending_category"] == ""
    assert payload["official_eval_manifests"][0]["next_pending_question_index"] is None
    assert payload["official_eval_manifests"][0]["diagnostic_classification"] == "completed"
    assert payload["official_eval_manifests"][0]["promotable_candidate"] is True
    assert payload["official_eval_manifests"][0]["judge_provider"] == "official_openai"
    assert payload["official_eval_manifests"][0]["required_judge_env"] == ""
    assert payload["official_eval_manifests"][0]["judge_env_ready"] is True
    assert payload["official_eval_manifests"][0]["cleanup_blocked_reason"] == ""


def test_beam_judged_cleanup_report_distinguishes_timeout_from_partial_coverage(tmp_path: Path, monkeypatch):
    answers_root = tmp_path / "artifacts" / "beam_public_results"
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    upstream_repo_dir = tmp_path / "beam_upstream"
    output_file = tmp_path / "artifacts" / "beam_cleanup_report.json"

    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions").mkdir(parents=True)
    (upstream_repo_dir / "chats" / "100K" / "3" / "probing_questions").mkdir(parents=True)
    timeout_eval = (
        answers_root
        / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9"
        / "100K"
        / "1"
        / "evaluation-domain_chip_memory_answers.json"
    )
    timeout_answers = timeout_eval.parent / "domain_chip_memory_answers.json"
    timeout_eval.parent.mkdir(parents=True)
    timeout_eval.write_text(
        json.dumps(
            {
                "information_extraction": [{"llm_judge_score": 1.0}],
                "event_ordering": [{"tau_norm": 0.5}],
            }
        ),
        encoding="utf-8",
    )
    timeout_answers.write_text(
        json.dumps(
            {
                "information_extraction": [{"question": "q1", "llm_response": "a1"}],
                "event_ordering": [{"question": "q2", "llm_response": "a2"}],
                "summarization": [{"question": "q3", "llm_response": "a3"}],
            }
        ),
        encoding="utf-8",
    )
    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps(
            {
                "information_extraction": [{"rubric": ["extract"]}],
                "event_ordering": [{"rubric": ["order"]}],
                "summarization": [{"rubric": ["summary"]}],
            }
        ),
        encoding="utf-8",
    )

    partial_eval = (
        answers_root
        / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv3_v2"
        / "100K"
        / "3"
        / "evaluation-domain_chip_memory_answers.json"
    )
    partial_answers = partial_eval.parent / "domain_chip_memory_answers.json"
    partial_eval.parent.mkdir(parents=True)
    partial_eval.write_text(
        json.dumps(
            {
                "information_extraction": [{"llm_judge_score": 1.0}],
                "event_ordering": [{"tau_norm": 0.5}],
            }
        ),
        encoding="utf-8",
    )
    partial_answers.write_text(
        json.dumps(
            {
                "information_extraction": [{"question": "q1", "llm_response": "a1"}],
                "event_ordering": [{"question": "q2", "llm_response": "a2"}],
                "multi_session_reasoning": [{"question": "q3", "llm_response": "a3"}],
            }
        ),
        encoding="utf-8",
    )
    (upstream_repo_dir / "chats" / "100K" / "3" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps(
            {
                "information_extraction": [{"rubric": ["extract"]}],
                "event_ordering": [{"rubric": ["order"]}],
                "multi_session_reasoning": [{"rubric": ["reason"]}],
            }
        ),
        encoding="utf-8",
    )

    benchmark_runs_dir.mkdir(parents=True)
    (benchmark_runs_dir / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json").write_text(
        json.dumps(
            {
                "status": "partial",
                "upstream_repo_dir": str(upstream_repo_dir),
                "official_chat_size_dir": "100K",
                "conversation_ids": ["1"],
                "input_directory": str(timeout_eval.parent.parent),
                "result_file_name": "domain_chip_memory_answers.json",
                "evaluation_files": [str(timeout_eval)],
                "missing_evaluation_files": [],
                "stdout_tail": ["Question Type: event_ordering", "Question Index: 0"],
                "stderr_tail": ["Timed out waiting for MiniMax BEAM evaluation worker after 900 seconds."],
                "aggregate_summary": {"overall_average": 0.75},
            }
        ),
        encoding="utf-8",
    )
    (benchmark_runs_dir / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv3_v2_official_eval.json").write_text(
        json.dumps(
            {
                "status": "partial",
                "upstream_repo_dir": str(upstream_repo_dir),
                "official_chat_size_dir": "100K",
                "conversation_ids": ["3"],
                "input_directory": str(partial_eval.parent.parent),
                "result_file_name": "domain_chip_memory_answers.json",
                "evaluation_files": [str(partial_eval)],
                "missing_evaluation_files": [],
                "stdout_tail": ["Question Type: multi_session_reasoning", "Question Index: 0"],
                "stderr_tail": ["3: TypeError: list indices must be integers or slices, not str"],
                "aggregate_summary": {"overall_average": 1.0},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("MINIMAX_API_KEY", "")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "beam-judged-cleanup-report",
            "--artifact-prefix",
            "official_beam_128k_summary_synthesis_memory_heuristic_v1_",
            "--answers-root",
            str(answers_root),
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    manifest_rows = {Path(item["path"]).name: item for item in payload["official_eval_manifests"]}
    assert payload["runnable_official_eval_manifest_count"] == 0
    assert payload["blocked_official_eval_manifest_count"] == 2
    assert payload["blocked_missing_env_vars"] == ["MINIMAX_API_KEY"]
    assert payload["promotable_untracked_official_eval_manifest_count"] == 0
    assert payload["promotable_untracked_official_eval_manifests"] == []

    timeout_row = manifest_rows["official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json"]
    assert timeout_row["diagnostic_classification"] == "timeout_partial_coverage"
    assert timeout_row["required_judge_env"] == "MINIMAX_API_KEY"
    assert timeout_row["judge_env_ready"] is False
    assert timeout_row["cleanup_blocked_reason"] == "missing_judge_env"
    assert timeout_row["expected_categories"] == ["event_ordering", "information_extraction", "summarization"]
    assert timeout_row["answer_categories"] == ["event_ordering", "information_extraction", "summarization"]
    assert timeout_row["missing_categories"] == ["summarization"]
    assert timeout_row["missing_answer_categories"] == ["summarization"]
    assert timeout_row["category_progress"] == [
        {
            "category": "information_extraction",
            "expected_question_count": 1,
            "answer_question_count": 1,
            "completed_question_count": 1,
            "status": "completed",
        },
        {
            "category": "event_ordering",
            "expected_question_count": 1,
            "answer_question_count": 1,
            "completed_question_count": 1,
            "status": "completed",
        },
        {
            "category": "summarization",
            "expected_question_count": 1,
            "answer_question_count": 1,
            "completed_question_count": 0,
            "status": "pending",
        },
    ]
    assert timeout_row["last_completed_category"] == "event_ordering"
    assert timeout_row["last_completed_question_index"] == 0
    assert timeout_row["next_pending_category"] == "summarization"
    assert timeout_row["next_pending_question_index"] == 0
    assert timeout_row["last_logged_question_type"] == "event_ordering"
    assert timeout_row["last_logged_question_index"] == 0
    assert timeout_row["promotable_candidate"] is False

    partial_row = manifest_rows["official_beam_128k_summary_synthesis_memory_heuristic_v1_conv3_v2_official_eval.json"]
    assert partial_row["diagnostic_classification"] == "worker_error_partial_coverage"
    assert partial_row["required_judge_env"] == "MINIMAX_API_KEY"
    assert partial_row["judge_env_ready"] is False
    assert partial_row["cleanup_blocked_reason"] == "missing_judge_env"
    assert partial_row["expected_categories"] == ["event_ordering", "information_extraction", "multi_session_reasoning"]
    assert partial_row["missing_categories"] == ["multi_session_reasoning"]
    assert partial_row["missing_answer_categories"] == ["multi_session_reasoning"]
    assert partial_row["category_progress"] == [
        {
            "category": "information_extraction",
            "expected_question_count": 1,
            "answer_question_count": 1,
            "completed_question_count": 1,
            "status": "completed",
        },
        {
            "category": "event_ordering",
            "expected_question_count": 1,
            "answer_question_count": 1,
            "completed_question_count": 1,
            "status": "completed",
        },
        {
            "category": "multi_session_reasoning",
            "expected_question_count": 1,
            "answer_question_count": 1,
            "completed_question_count": 0,
            "status": "pending",
        },
    ]
    assert partial_row["last_completed_category"] == "event_ordering"
    assert partial_row["last_completed_question_index"] == 0
    assert partial_row["next_pending_category"] == "multi_session_reasoning"
    assert partial_row["next_pending_question_index"] == 0
    assert partial_row["last_logged_question_type"] == "multi_session_reasoning"
    assert partial_row["last_logged_question_index"] == 0
    assert partial_row["promotable_candidate"] is False


def test_beam_judged_cleanup_report_surfaces_tracked_evaluation_drift(tmp_path: Path, monkeypatch):
    answers_root = tmp_path / "artifacts" / "beam_public_results"
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    output_file = tmp_path / "artifacts" / "beam_cleanup_report.json"

    eval_path = (
        answers_root
        / "official_beam_128k_summary_synthesis_memory_heuristic_v1_first20_v3"
        / "100K"
        / "1"
        / "evaluation-domain_chip_memory_answers.json"
    )
    eval_path.parent.mkdir(parents=True)
    eval_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"llm_judge_score": 1.0}],
                "event_ordering": [{"tau_norm": 0.1789}],
                "abstention": [{"llm_judge_score": 1.0}],
                "contradiction_resolution": [{"llm_judge_score": 0.75}],
            }
        ),
        encoding="utf-8",
    )

    display_path = "artifacts/beam_public_results/official_beam_128k_summary_synthesis_memory_heuristic_v1_first20_v3/100K/1/evaluation-domain_chip_memory_answers.json"
    monkeypatch.setattr(cli, "_git_status_by_path", lambda paths, repo_root: {display_path: "M"})
    monkeypatch.setattr(
        cli,
        "_load_json_from_git_revision",
        lambda repo_root, revision, path: {
            "information_extraction": [{"llm_judge_score": 1.0}],
            "event_ordering": [{"tau_norm": 0.8622}],
            "abstention": [{"llm_judge_score": 1.0}],
            "contradiction_resolution": [{"llm_judge_score": 0.75}],
            "summarization": [{"llm_judge_score": 0.9}],
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "beam-judged-cleanup-report",
            "--artifact-prefix",
            "official_beam_128k_summary_synthesis_memory_heuristic_v1_",
            "--answers-root",
            str(answers_root),
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["modified_evaluation_drift_count"] == 1
    drift_row = payload["modified_evaluation_drift_files"][0]
    assert drift_row["path"] == display_path
    assert drift_row["git_status"] == "M"
    assert drift_row["head_present"] is True
    assert drift_row["current_overall_average"] == 0.7322
    assert drift_row["head_overall_average"] == 0.9024
    assert drift_row["overall_average_delta"] == -0.1702
    assert drift_row["current_category_count"] == 4
    assert drift_row["head_category_count"] == 5
    assert drift_row["missing_from_current"] == ["summarization"]
    assert drift_row["added_in_current"] == []
    assert drift_row["changed_category_count"] == 2
    changed_by_category = {row["category"]: row for row in drift_row["changed_categories"]}
    assert changed_by_category["event_ordering"]["head_average_score"] == 0.8622
    assert changed_by_category["event_ordering"]["current_average_score"] == 0.1789
    assert changed_by_category["event_ordering"]["average_score_delta"] == -0.6833
    assert changed_by_category["event_ordering"]["changed_question_count"] == 1
    assert changed_by_category["event_ordering"]["changed_questions"] == [
        {
            "question_index": 0,
            "head_metric": "tau_norm",
            "current_metric": "tau_norm",
            "head_score": 0.8622,
            "current_score": 0.1789,
            "score_delta": -0.6833,
            "head_question": "",
            "current_question": "",
        }
    ]
    assert changed_by_category["summarization"]["head_average_score"] == 0.9
    assert changed_by_category["summarization"]["current_average_score"] is None
    assert changed_by_category["summarization"]["changed_question_count"] == 1
    assert changed_by_category["summarization"]["changed_questions"] == [
        {
            "question_index": 0,
            "head_metric": "llm_judge_score",
            "current_metric": "",
            "head_score": 0.9,
            "current_score": None,
            "score_delta": None,
            "head_question": "",
            "current_question": "",
        }
    ]


def test_beam_judged_cleanup_report_surfaces_promotable_untracked_manifests(tmp_path: Path, monkeypatch):
    answers_root = tmp_path / "artifacts" / "beam_public_results"
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    upstream_repo_dir = tmp_path / "beam_upstream"
    output_file = tmp_path / "artifacts" / "beam_cleanup_report.json"

    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions").mkdir(parents=True)
    eval_path = (
        answers_root
        / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9"
        / "100K"
        / "1"
        / "evaluation-domain_chip_memory_answers.json"
    )
    answers_path = eval_path.parent / "domain_chip_memory_answers.json"
    eval_path.parent.mkdir(parents=True)
    eval_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"llm_judge_score": 1.0}],
                "event_ordering": [{"tau_norm": 0.5}],
            }
        ),
        encoding="utf-8",
    )
    answers_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"question": "q1", "llm_response": "a1"}],
                "event_ordering": [{"question": "q2", "llm_response": "a2"}],
            }
        ),
        encoding="utf-8",
    )
    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps(
            {
                "information_extraction": [{"rubric": ["extract"]}],
                "event_ordering": [{"rubric": ["order"]}],
            }
        ),
        encoding="utf-8",
    )

    benchmark_runs_dir.mkdir(parents=True)
    manifest_path = benchmark_runs_dir / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json"
    manifest_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "upstream_repo_dir": str(upstream_repo_dir),
                "official_chat_size_dir": "100K",
                "requested_chat_size": "128K",
                "conversation_ids": ["1"],
                "input_directory": str(eval_path.parent.parent),
                "result_file_name": "domain_chip_memory_answers.json",
                "judge_config": {
                    "provider": "minimax",
                    "model": "MiniMax-M2.7",
                    "base_url": "https://api.minimax.io/v1",
                    "api_key_env": "MINIMAX_API_KEY",
                },
                "evaluation_files": [str(eval_path)],
                "aggregate_summary": {"overall_average": 0.75},
            }
        ),
        encoding="utf-8",
    )

    display_eval_path = "artifacts/beam_public_results/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9/100K/1/evaluation-domain_chip_memory_answers.json"
    display_manifest_path = "artifacts/benchmark_runs/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json"
    monkeypatch.setattr(
        cli,
        "_git_status_by_path",
        lambda paths, repo_root: {
            display_eval_path: "clean",
            display_manifest_path: "??",
        },
    )
    monkeypatch.setenv("MINIMAX_API_KEY", "minimax-test-key")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "beam-judged-cleanup-report",
            "--artifact-prefix",
            "official_beam_128k_summary_synthesis_memory_heuristic_v1_",
            "--answers-root",
            str(answers_root),
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["promotable_untracked_official_eval_manifest_count"] == 1
    assert payload["promotable_untracked_official_eval_manifests"] == [
        {
            "path": display_manifest_path,
            "git_status": "??",
            "diagnostic_classification": "completed",
            "overall_average": 0.75,
            "evaluation_file_count": 1,
        }
    ]


def test_beam_judged_promotion_plan_cli_emits_git_add_commands(tmp_path: Path, monkeypatch):
    answers_root = tmp_path / "artifacts" / "beam_public_results"
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    upstream_repo_dir = tmp_path / "beam_upstream"
    output_file = tmp_path / "artifacts" / "beam_promotion_plan.json"

    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions").mkdir(parents=True)
    eval_path = (
        answers_root
        / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9"
        / "100K"
        / "1"
        / "evaluation-domain_chip_memory_answers.json"
    )
    answers_path = eval_path.parent / "domain_chip_memory_answers.json"
    drift_eval_path = (
        answers_root
        / "official_beam_128k_summary_synthesis_memory_heuristic_v1_first20_v3"
        / "100K"
        / "1"
        / "evaluation-domain_chip_memory_answers.json"
    )
    eval_path.parent.mkdir(parents=True)
    drift_eval_path.parent.mkdir(parents=True)
    eval_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"llm_judge_score": 1.0}],
                "event_ordering": [{"tau_norm": 0.5}],
            }
        ),
        encoding="utf-8",
    )
    answers_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"question": "q1", "llm_response": "a1"}],
                "event_ordering": [{"question": "q2", "llm_response": "a2"}],
            }
        ),
        encoding="utf-8",
    )
    drift_eval_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"llm_judge_score": 1.0}],
                "event_ordering": [{"tau_norm": 0.1789}],
            }
        ),
        encoding="utf-8",
    )
    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps(
            {
                "information_extraction": [{"rubric": ["extract"]}],
                "event_ordering": [{"rubric": ["order"]}],
            }
        ),
        encoding="utf-8",
    )

    benchmark_runs_dir.mkdir(parents=True)
    manifest_path = benchmark_runs_dir / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json"
    manifest_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "upstream_repo_dir": str(upstream_repo_dir),
                "official_chat_size_dir": "100K",
                "requested_chat_size": "128K",
                "conversation_ids": ["1"],
                "input_directory": str(eval_path.parent.parent),
                "result_file_name": "domain_chip_memory_answers.json",
                "judge_config": {
                    "provider": "minimax",
                    "model": "MiniMax-M2.7",
                    "base_url": "https://api.minimax.io/v1",
                    "api_key_env": "MINIMAX_API_KEY",
                },
                "evaluation_files": [str(eval_path)],
                "aggregate_summary": {"overall_average": 0.75},
            }
        ),
        encoding="utf-8",
    )

    display_eval_path = "artifacts/beam_public_results/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9/100K/1/evaluation-domain_chip_memory_answers.json"
    display_manifest_path = "artifacts/benchmark_runs/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json"
    display_drift_path = "artifacts/beam_public_results/official_beam_128k_summary_synthesis_memory_heuristic_v1_first20_v3/100K/1/evaluation-domain_chip_memory_answers.json"
    monkeypatch.setattr(
        cli,
        "_git_status_by_path",
        lambda paths, repo_root: {
            display_eval_path: "clean",
            display_manifest_path: "??",
            display_drift_path: "M",
        },
    )
    monkeypatch.setattr(
        cli,
        "_load_json_from_git_revision",
        lambda repo_root, revision, path: {
            "information_extraction": [{"llm_judge_score": 1.0}],
            "event_ordering": [{"tau_norm": 0.8622}],
        }
        if str(path).endswith("first20_v3\\100K\\1\\evaluation-domain_chip_memory_answers.json")
        else None,
    )
    monkeypatch.setenv("MINIMAX_API_KEY", "minimax-test-key")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "beam-judged-promotion-plan",
            "--artifact-prefix",
            "official_beam_128k_summary_synthesis_memory_heuristic_v1_",
            "--answers-root",
            str(answers_root),
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["benchmark_name"] == "BEAM"
    assert payload["source_mode"] == "official_public_evaluation_promotion_plan"
    assert payload["promotion_target_count"] == 1
    assert payload["excluded_modified_evaluation_drift_count"] == 1
    target = payload["promotion_targets"][0]
    assert target["manifest_path"] == display_manifest_path
    assert target["evaluation_files"] == [display_eval_path]
    assert target["git_add_paths"] == [display_manifest_path, display_eval_path]
    assert target["git_add_command"] == ["git", "add", "--", display_manifest_path, display_eval_path]
    assert "git add --" in target["git_add_command_shell"]


def test_beam_judged_drift_plan_cli_emits_inspection_and_restore_commands(tmp_path: Path, monkeypatch):
    answers_root = tmp_path / "artifacts" / "beam_public_results"
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    output_file = tmp_path / "artifacts" / "beam_drift_plan.json"

    eval_path = (
        answers_root
        / "official_beam_128k_summary_synthesis_memory_heuristic_v1_first20_v3"
        / "100K"
        / "1"
        / "evaluation-domain_chip_memory_answers.json"
    )
    eval_path.parent.mkdir(parents=True)
    eval_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"llm_judge_score": 1.0}],
                "event_ordering": [{"tau_norm": 0.1789}],
            }
        ),
        encoding="utf-8",
    )

    display_path = "artifacts/beam_public_results/official_beam_128k_summary_synthesis_memory_heuristic_v1_first20_v3/100K/1/evaluation-domain_chip_memory_answers.json"
    monkeypatch.setattr(cli, "_git_status_by_path", lambda paths, repo_root: {display_path: "M"})
    monkeypatch.setattr(
        cli,
        "_load_json_from_git_revision",
        lambda repo_root, revision, path: {
            "information_extraction": [{"llm_judge_score": 1.0}],
            "event_ordering": [{"tau_norm": 0.8622}],
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "beam-judged-drift-plan",
            "--artifact-prefix",
            "official_beam_128k_summary_synthesis_memory_heuristic_v1_",
            "--answers-root",
            str(answers_root),
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["benchmark_name"] == "BEAM"
    assert payload["source_mode"] == "official_public_evaluation_drift_plan"
    assert payload["drift_target_count"] == 1
    target = payload["drift_targets"][0]
    assert target["path"] == display_path
    assert target["git_diff_command"] == ["git", "diff", "--", display_path]
    assert target["git_show_head_command"] == ["git", "show", f"HEAD:{display_path}"]
    assert target["git_restore_command"] == ["git", "restore", "--source=HEAD", "--", display_path]
    assert "git diff --" in target["git_diff_command_shell"]
    assert "git show" in target["git_show_head_command_shell"]
    assert "git restore --source=HEAD --" in target["git_restore_command_shell"]


def test_beam_judged_drift_batch_cli_writes_powershell_script(tmp_path: Path, monkeypatch):
    answers_root = tmp_path / "artifacts" / "beam_public_results"
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    output_file = tmp_path / "artifacts" / "beam_drift_batch.json"
    script_file = tmp_path / "artifacts" / "beam_drift_batch.ps1"

    eval_path = (
        answers_root
        / "official_beam_128k_summary_synthesis_memory_heuristic_v1_first20_v3"
        / "100K"
        / "1"
        / "evaluation-domain_chip_memory_answers.json"
    )
    eval_path.parent.mkdir(parents=True)
    eval_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"llm_judge_score": 1.0}],
                "event_ordering": [{"tau_norm": 0.1789}],
            }
        ),
        encoding="utf-8",
    )

    display_path = "artifacts/beam_public_results/official_beam_128k_summary_synthesis_memory_heuristic_v1_first20_v3/100K/1/evaluation-domain_chip_memory_answers.json"
    monkeypatch.setattr(cli, "_git_status_by_path", lambda paths, repo_root: {display_path: "M"})
    monkeypatch.setattr(
        cli,
        "_load_json_from_git_revision",
        lambda repo_root, revision, path: {
            "information_extraction": [{"llm_judge_score": 1.0}],
            "event_ordering": [{"tau_norm": 0.8622}],
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "beam-judged-drift-batch",
            "--artifact-prefix",
            "official_beam_128k_summary_synthesis_memory_heuristic_v1_",
            "--answers-root",
            str(answers_root),
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--script-file",
            str(script_file),
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["benchmark_name"] == "BEAM"
    assert payload["source_mode"] == "official_public_evaluation_drift_batch"
    assert payload["drift_target_count"] == 1
    assert payload["script_file"] == str(script_file)
    assert payload["script_line_count"] >= 6
    assert payload["script_lines"][0] == "$ErrorActionPreference = 'Stop'"
    assert "git diff --" in payload["script_text"]
    assert "git show" in payload["script_text"]
    assert "# git restore --source=HEAD --" in payload["script_text"]
    assert script_file.read_text(encoding="utf-8") == payload["script_text"]


def test_beam_judged_drift_batch_cli_writes_empty_script_when_no_targets(tmp_path: Path, monkeypatch):
    output_file = tmp_path / "artifacts" / "beam_drift_batch.json"
    script_file = tmp_path / "artifacts" / "beam_drift_batch.ps1"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "beam-judged-drift-batch",
            "--artifact-prefix",
            "official_beam_128k_summary_synthesis_memory_heuristic_v1_",
            "--answers-root",
            str(tmp_path / "artifacts" / "beam_public_results"),
            "--benchmark-runs-dir",
            str(tmp_path / "artifacts" / "benchmark_runs"),
            "--repo-root",
            str(tmp_path),
            "--script-file",
            str(script_file),
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["drift_target_count"] == 0
    assert payload["script_file"] == str(script_file)
    assert payload["script_lines"] == [
        "$ErrorActionPreference = 'Stop'",
        "# Generated by beam-judged-drift-batch for official_beam_128k_summary_synthesis_memory_heuristic_v1_",
    ]
    assert payload["script_text"] == "$ErrorActionPreference = 'Stop'\n# Generated by beam-judged-drift-batch for official_beam_128k_summary_synthesis_memory_heuristic_v1_\n"
    assert script_file.read_text(encoding="utf-8") == payload["script_text"]


def test_beam_judged_drift_batch_cli_can_execute_inspection_targets(tmp_path: Path, monkeypatch):
    answers_root = tmp_path / "artifacts" / "beam_public_results"
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    output_file = tmp_path / "artifacts" / "beam_drift_batch.json"

    eval_path = (
        answers_root
        / "official_beam_128k_summary_synthesis_memory_heuristic_v1_first20_v3"
        / "100K"
        / "1"
        / "evaluation-domain_chip_memory_answers.json"
    )
    eval_path.parent.mkdir(parents=True)
    eval_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"llm_judge_score": 1.0}],
                "event_ordering": [{"tau_norm": 0.1789}],
            }
        ),
        encoding="utf-8",
    )

    display_path = "artifacts/beam_public_results/official_beam_128k_summary_synthesis_memory_heuristic_v1_first20_v3/100K/1/evaluation-domain_chip_memory_answers.json"
    monkeypatch.setattr(cli, "_git_status_by_path", lambda paths, repo_root: {display_path: "M"})
    monkeypatch.setattr(
        cli,
        "_load_json_from_git_revision",
        lambda repo_root, revision, path: {
            "information_extraction": [{"llm_judge_score": 1.0}],
            "event_ordering": [{"tau_norm": 0.8622}],
        },
    )

    class FakeCompletedProcess:
        def __init__(self, stdout: str):
            self.returncode = 0
            self.stdout = stdout
            self.stderr = ""

    captured_commands = []

    def fake_run(command, *, cwd, capture_output, text, check):
        captured_commands.append(
            {
                "command": command,
                "cwd": cwd,
                "capture_output": capture_output,
                "text": text,
                "check": check,
            }
        )
        if command[1] == "diff":
            return FakeCompletedProcess("diff output\n")
        return FakeCompletedProcess("head output\n")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "beam-judged-drift-batch",
            "--artifact-prefix",
            "official_beam_128k_summary_synthesis_memory_heuristic_v1_",
            "--answers-root",
            str(answers_root),
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--execute",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["execute_requested"] is True
    assert payload["executed_target_count"] == 1
    assert payload["execution_status_counts"] == {"completed": 1}
    assert payload["completed_execution_count"] == 1
    assert payload["failed_execution_count"] == 0
    assert payload["execution_results"][0]["status"] == "completed"
    assert len(payload["execution_results"][0]["command_results"]) == 2
    assert payload["execution_results"][0]["command_results"][0]["stdout_tail"] == ["diff output"]
    assert payload["execution_results"][0]["command_results"][1]["stdout_tail"] == ["head output"]
    assert captured_commands[0]["command"] == ["git", "diff", "--", display_path]
    assert captured_commands[1]["command"] == ["git", "show", f"HEAD:{display_path}"]
    assert captured_commands[0]["cwd"] == str(tmp_path.resolve())
    assert captured_commands[0]["capture_output"] is True
    assert captured_commands[0]["text"] is True
    assert captured_commands[0]["check"] is False


def test_beam_judged_promotion_plan_cli_normalizes_relative_repo_root(tmp_path: Path, monkeypatch):
    answers_root = tmp_path / "artifacts" / "beam_public_results"
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    upstream_repo_dir = tmp_path / "beam_upstream"
    output_file = tmp_path / "artifacts" / "beam_promotion_plan.json"

    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions").mkdir(parents=True)
    eval_path = (
        answers_root
        / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9"
        / "100K"
        / "1"
        / "evaluation-domain_chip_memory_answers.json"
    )
    answers_path = eval_path.parent / "domain_chip_memory_answers.json"
    eval_path.parent.mkdir(parents=True)
    eval_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"llm_judge_score": 1.0}],
                "event_ordering": [{"tau_norm": 0.5}],
            }
        ),
        encoding="utf-8",
    )
    answers_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"question": "q1", "llm_response": "a1"}],
                "event_ordering": [{"question": "q2", "llm_response": "a2"}],
            }
        ),
        encoding="utf-8",
    )
    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps(
            {
                "information_extraction": [{"rubric": ["extract"]}],
                "event_ordering": [{"rubric": ["order"]}],
            }
        ),
        encoding="utf-8",
    )

    benchmark_runs_dir.mkdir(parents=True)
    manifest_path = benchmark_runs_dir / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json"
    manifest_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "upstream_repo_dir": str(upstream_repo_dir),
                "official_chat_size_dir": "100K",
                "requested_chat_size": "128K",
                "conversation_ids": ["1"],
                "input_directory": str(eval_path.parent.parent),
                "result_file_name": "domain_chip_memory_answers.json",
                "judge_config": {
                    "provider": "minimax",
                    "model": "MiniMax-M2.7",
                    "base_url": "https://api.minimax.io/v1",
                    "api_key_env": "MINIMAX_API_KEY",
                },
                "evaluation_files": [str(eval_path.resolve())],
                "aggregate_summary": {"overall_average": 0.75},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        cli,
        "_git_status_by_path",
        lambda paths, repo_root: {
            "artifacts/beam_public_results/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9/100K/1/evaluation-domain_chip_memory_answers.json": "clean",
            "artifacts/benchmark_runs/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json": "??",
        },
    )
    monkeypatch.setenv("MINIMAX_API_KEY", "minimax-test-key")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "beam-judged-promotion-plan",
            "--artifact-prefix",
            "official_beam_128k_summary_synthesis_memory_heuristic_v1_",
            "--repo-root",
            ".",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    target = payload["promotion_targets"][0]
    assert target["evaluation_files"] == [
        "artifacts/beam_public_results/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9/100K/1/evaluation-domain_chip_memory_answers.json"
    ]


def test_beam_judged_promotion_batch_cli_writes_powershell_script(tmp_path: Path, monkeypatch):
    answers_root = tmp_path / "artifacts" / "beam_public_results"
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    upstream_repo_dir = tmp_path / "beam_upstream"
    output_file = tmp_path / "artifacts" / "beam_promotion_batch.json"
    script_file = tmp_path / "artifacts" / "beam_promotion_batch.ps1"

    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions").mkdir(parents=True)
    eval_path = (
        answers_root
        / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9"
        / "100K"
        / "1"
        / "evaluation-domain_chip_memory_answers.json"
    )
    answers_path = eval_path.parent / "domain_chip_memory_answers.json"
    eval_path.parent.mkdir(parents=True)
    eval_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"llm_judge_score": 1.0}],
                "event_ordering": [{"tau_norm": 0.5}],
            }
        ),
        encoding="utf-8",
    )
    answers_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"question": "q1", "llm_response": "a1"}],
                "event_ordering": [{"question": "q2", "llm_response": "a2"}],
            }
        ),
        encoding="utf-8",
    )
    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps(
            {
                "information_extraction": [{"rubric": ["extract"]}],
                "event_ordering": [{"rubric": ["order"]}],
            }
        ),
        encoding="utf-8",
    )

    benchmark_runs_dir.mkdir(parents=True)
    manifest_path = benchmark_runs_dir / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json"
    manifest_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "upstream_repo_dir": str(upstream_repo_dir),
                "official_chat_size_dir": "100K",
                "requested_chat_size": "128K",
                "conversation_ids": ["1"],
                "input_directory": str(eval_path.parent.parent),
                "result_file_name": "domain_chip_memory_answers.json",
                "judge_config": {
                    "provider": "minimax",
                    "model": "MiniMax-M2.7",
                    "base_url": "https://api.minimax.io/v1",
                    "api_key_env": "MINIMAX_API_KEY",
                },
                "evaluation_files": [str(eval_path)],
                "aggregate_summary": {"overall_average": 0.75},
            }
        ),
        encoding="utf-8",
    )

    display_eval_path = "artifacts/beam_public_results/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9/100K/1/evaluation-domain_chip_memory_answers.json"
    display_manifest_path = "artifacts/benchmark_runs/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json"
    monkeypatch.setattr(
        cli,
        "_git_status_by_path",
        lambda paths, repo_root: {
            display_eval_path: "clean",
            display_manifest_path: "??",
        },
    )
    monkeypatch.setenv("MINIMAX_API_KEY", "minimax-test-key")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "beam-judged-promotion-batch",
            "--artifact-prefix",
            "official_beam_128k_summary_synthesis_memory_heuristic_v1_",
            "--answers-root",
            str(answers_root),
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--script-file",
            str(script_file),
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["benchmark_name"] == "BEAM"
    assert payload["source_mode"] == "official_public_evaluation_promotion_batch"
    assert payload["promotion_target_count"] == 1
    assert payload["excluded_modified_evaluation_drift_count"] == 0
    assert payload["script_file"] == str(script_file)
    assert payload["script_line_count"] >= 3
    assert payload["script_lines"][0] == "$ErrorActionPreference = 'Stop'"
    assert "conv1_v9_official_eval.json" in payload["script_lines"][2]
    assert "git add --" in payload["script_text"]
    assert script_file.read_text(encoding="utf-8") == payload["script_text"]


def test_beam_judged_promotion_batch_cli_writes_empty_script_when_no_targets(tmp_path: Path, monkeypatch):
    output_file = tmp_path / "artifacts" / "beam_promotion_batch.json"
    script_file = tmp_path / "artifacts" / "beam_promotion_batch.ps1"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "beam-judged-promotion-batch",
            "--artifact-prefix",
            "official_beam_128k_summary_synthesis_memory_heuristic_v1_",
            "--answers-root",
            str(tmp_path / "artifacts" / "beam_public_results"),
            "--benchmark-runs-dir",
            str(tmp_path / "artifacts" / "benchmark_runs"),
            "--repo-root",
            str(tmp_path),
            "--script-file",
            str(script_file),
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["promotion_target_count"] == 0
    assert payload["script_file"] == str(script_file)
    assert payload["script_lines"] == [
        "$ErrorActionPreference = 'Stop'",
        "# Generated by beam-judged-promotion-batch for official_beam_128k_summary_synthesis_memory_heuristic_v1_",
    ]
    assert payload["script_text"] == "$ErrorActionPreference = 'Stop'\n# Generated by beam-judged-promotion-batch for official_beam_128k_summary_synthesis_memory_heuristic_v1_\n"
    assert script_file.read_text(encoding="utf-8") == payload["script_text"]


def test_beam_judged_promotion_batch_cli_can_execute_targets(tmp_path: Path, monkeypatch):
    answers_root = tmp_path / "artifacts" / "beam_public_results"
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    upstream_repo_dir = tmp_path / "beam_upstream"
    output_file = tmp_path / "artifacts" / "beam_promotion_batch.json"

    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions").mkdir(parents=True)
    eval_path = (
        answers_root
        / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9"
        / "100K"
        / "1"
        / "evaluation-domain_chip_memory_answers.json"
    )
    answers_path = eval_path.parent / "domain_chip_memory_answers.json"
    eval_path.parent.mkdir(parents=True)
    eval_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"llm_judge_score": 1.0}],
                "event_ordering": [{"tau_norm": 0.5}],
            }
        ),
        encoding="utf-8",
    )
    answers_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"question": "q1", "llm_response": "a1"}],
                "event_ordering": [{"question": "q2", "llm_response": "a2"}],
            }
        ),
        encoding="utf-8",
    )
    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps(
            {
                "information_extraction": [{"rubric": ["extract"]}],
                "event_ordering": [{"rubric": ["order"]}],
            }
        ),
        encoding="utf-8",
    )

    benchmark_runs_dir.mkdir(parents=True)
    manifest_path = benchmark_runs_dir / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json"
    manifest_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "upstream_repo_dir": str(upstream_repo_dir),
                "official_chat_size_dir": "100K",
                "requested_chat_size": "128K",
                "conversation_ids": ["1"],
                "input_directory": str(eval_path.parent.parent),
                "result_file_name": "domain_chip_memory_answers.json",
                "judge_config": {
                    "provider": "minimax",
                    "model": "MiniMax-M2.7",
                    "base_url": "https://api.minimax.io/v1",
                    "api_key_env": "MINIMAX_API_KEY",
                },
                "evaluation_files": [str(eval_path)],
                "aggregate_summary": {"overall_average": 0.75},
            }
        ),
        encoding="utf-8",
    )

    display_eval_path = "artifacts/beam_public_results/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9/100K/1/evaluation-domain_chip_memory_answers.json"
    display_manifest_path = "artifacts/benchmark_runs/official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json"
    monkeypatch.setattr(
        cli,
        "_git_status_by_path",
        lambda paths, repo_root: {
            display_eval_path: "clean",
            display_manifest_path: "??",
        },
    )

    class FakeCompletedProcess:
        def __init__(self):
            self.returncode = 0
            self.stdout = "staged promotion target\n"
            self.stderr = ""

    captured_commands = []

    def fake_run(command, *, cwd, capture_output, text, check):
        captured_commands.append(
            {
                "command": command,
                "cwd": cwd,
                "capture_output": capture_output,
                "text": text,
                "check": check,
            }
        )
        return FakeCompletedProcess()

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setenv("MINIMAX_API_KEY", "minimax-test-key")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "beam-judged-promotion-batch",
            "--artifact-prefix",
            "official_beam_128k_summary_synthesis_memory_heuristic_v1_",
            "--answers-root",
            str(answers_root),
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--execute",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["execute_requested"] is True
    assert payload["promotion_target_count"] == 1
    assert payload["executed_target_count"] == 1
    assert payload["execution_status_counts"] == {"completed": 1}
    assert payload["completed_execution_count"] == 1
    assert payload["failed_execution_count"] == 0
    assert payload["execution_results"][0]["status"] == "completed"
    assert payload["execution_results"][0]["return_code"] == 0
    assert payload["execution_results"][0]["stdout_tail"] == ["staged promotion target"]
    assert captured_commands[0]["command"] == [
        "git",
        "add",
        "--",
        display_manifest_path,
        display_eval_path,
    ]
    assert captured_commands[0]["cwd"] == str(tmp_path.resolve())
    assert captured_commands[0]["capture_output"] is True
    assert captured_commands[0]["text"] is True
    assert captured_commands[0]["check"] is False


def test_beam_judged_resume_plan_cli_emits_exact_rerun_command(tmp_path: Path, monkeypatch):
    answers_root = tmp_path / "artifacts" / "beam_public_results"
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    upstream_repo_dir = tmp_path / "beam_upstream"
    output_file = tmp_path / "artifacts" / "beam_resume_plan.json"

    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions").mkdir(parents=True)
    conv1_dir = answers_root / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9" / "100K" / "1"
    eval_path = conv1_dir / "evaluation-domain_chip_memory_answers.json"
    answers_path = conv1_dir / "domain_chip_memory_answers.json"
    conv1_dir.mkdir(parents=True)
    eval_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"llm_judge_score": 1.0}],
                "event_ordering": [{"tau_norm": 0.5}],
            }
        ),
        encoding="utf-8",
    )
    answers_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"question": "q1", "llm_response": "a1"}],
                "event_ordering": [{"question": "q2", "llm_response": "a2"}],
                "summarization": [{"question": "q3", "llm_response": "a3"}],
            }
        ),
        encoding="utf-8",
    )
    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps(
            {
                "information_extraction": [{"rubric": ["extract"]}],
                "event_ordering": [{"rubric": ["order"]}],
                "summarization": [{"rubric": ["summary"]}],
            }
        ),
        encoding="utf-8",
    )

    benchmark_runs_dir.mkdir(parents=True)
    manifest_path = benchmark_runs_dir / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json"
    manifest_path.write_text(
        json.dumps(
            {
                "status": "partial",
                "upstream_repo_dir": str(upstream_repo_dir),
                "answers_root": str(conv1_dir.parent.parent),
                "official_chat_size_dir": "100K",
                "requested_chat_size": "128K",
                "conversation_ids": ["1"],
                "input_directory": str(conv1_dir.parent),
                "result_file_name": "domain_chip_memory_answers.json",
                "start_index": 0,
                "end_index": 1,
                "max_workers": 10,
                "judge_config": {
                    "provider": "minimax",
                    "model": "MiniMax-M2.7",
                    "base_url": "https://api.minimax.io/v1",
                    "api_key_env": "MISSING_MINIMAX_API_KEY",
                },
                "evaluation_files": [str(eval_path)],
                "missing_evaluation_files": [],
                "stdout_tail": ["Question Type: event_ordering", "Question Index: 1"],
                "stderr_tail": ["Timed out waiting for MiniMax BEAM evaluation worker after 900 seconds."],
                "aggregate_summary": {"overall_average": 0.75},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv("MISSING_MINIMAX_API_KEY", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "beam-judged-resume-plan",
            "--artifact-prefix",
            "official_beam_128k_summary_synthesis_memory_heuristic_v1_",
            "--answers-root",
            str(answers_root),
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["benchmark_name"] == "BEAM"
    assert payload["source_mode"] == "official_public_evaluation_resume_plan"
    assert payload["resume_target_count"] == 1
    assert payload["runnable_target_count"] == 0
    assert payload["blocked_target_count"] == 1
    assert payload["blocked_missing_env_vars"] == ["MISSING_MINIMAX_API_KEY"]
    target = payload["resume_targets"][0]
    assert target["path"].endswith("conv1_v9_official_eval.json")
    assert target["diagnostic_classification"] == "timeout_partial_coverage"
    assert target["next_pending_category"] == "summarization"
    assert target["next_pending_question_index"] == 0
    assert target["chat_size"] == "128K"
    assert target["answers_dir"] == str(conv1_dir.parent.parent)
    assert target["judge_provider"] == "minimax"
    assert target["judge_model"] == "MiniMax-M2.7"
    assert target["required_judge_env"] == "MISSING_MINIMAX_API_KEY"
    assert target["judge_env_ready"] is False
    assert target["resume_blocked_reason"] == "missing_judge_env"
    assert target["resume_command"] == [
        "python",
        "-m",
        "domain_chip_memory.cli",
        "run-beam-official-evaluation",
        str(upstream_repo_dir),
        str(conv1_dir.parent.parent),
        "--chat-size",
        "128K",
        "--result-file-name",
        "domain_chip_memory_answers.json",
        "--start-index",
        "0",
        "--end-index",
        "1",
        "--max-workers",
        "10",
        "--judge-provider",
        "minimax",
        "--judge-model",
        "MiniMax-M2.7",
        "--judge-base-url",
        "https://api.minimax.io/v1",
        "--judge-api-key-env",
        "MISSING_MINIMAX_API_KEY",
        "--write",
        str(manifest_path),
    ]
    assert "run-beam-official-evaluation" in target["resume_command_shell"]


def test_beam_judged_resume_plan_cli_only_runnable_filters_blocked_targets(tmp_path: Path, monkeypatch):
    answers_root = tmp_path / "artifacts" / "beam_public_results"
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    upstream_repo_dir = tmp_path / "beam_upstream"
    output_file = tmp_path / "artifacts" / "beam_resume_plan.json"

    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions").mkdir(parents=True)
    conv1_dir = answers_root / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9" / "100K" / "1"
    eval_path = conv1_dir / "evaluation-domain_chip_memory_answers.json"
    answers_path = conv1_dir / "domain_chip_memory_answers.json"
    conv1_dir.mkdir(parents=True)
    eval_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"llm_judge_score": 1.0}],
                "event_ordering": [{"tau_norm": 0.5}],
            }
        ),
        encoding="utf-8",
    )
    answers_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"question": "q1", "llm_response": "a1"}],
                "event_ordering": [{"question": "q2", "llm_response": "a2"}],
                "summarization": [{"question": "q3", "llm_response": "a3"}],
            }
        ),
        encoding="utf-8",
    )
    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps(
            {
                "information_extraction": [{"rubric": ["extract"]}],
                "event_ordering": [{"rubric": ["order"]}],
                "summarization": [{"rubric": ["summary"]}],
            }
        ),
        encoding="utf-8",
    )

    benchmark_runs_dir.mkdir(parents=True)
    manifest_path = benchmark_runs_dir / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json"
    manifest_path.write_text(
        json.dumps(
            {
                "status": "partial",
                "upstream_repo_dir": str(upstream_repo_dir),
                "answers_root": str(conv1_dir.parent.parent),
                "official_chat_size_dir": "100K",
                "requested_chat_size": "128K",
                "conversation_ids": ["1"],
                "input_directory": str(conv1_dir.parent),
                "result_file_name": "domain_chip_memory_answers.json",
                "start_index": 0,
                "end_index": 1,
                "max_workers": 10,
                "judge_config": {
                    "provider": "minimax",
                    "model": "MiniMax-M2.7",
                    "base_url": "https://api.minimax.io/v1",
                    "api_key_env": "MISSING_MINIMAX_API_KEY",
                },
                "evaluation_files": [str(eval_path)],
                "missing_evaluation_files": [],
                "stderr_tail": ["Timed out waiting for MiniMax BEAM evaluation worker after 900 seconds."],
                "aggregate_summary": {"overall_average": 0.75},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv("MISSING_MINIMAX_API_KEY", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "beam-judged-resume-plan",
            "--artifact-prefix",
            "official_beam_128k_summary_synthesis_memory_heuristic_v1_",
            "--answers-root",
            str(answers_root),
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--only-runnable",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["only_runnable"] is True
    assert payload["discovered_target_count"] == 1
    assert payload["resume_target_count"] == 0
    assert payload["filtered_out_target_count"] == 1
    assert payload["runnable_target_count"] == 0
    assert payload["blocked_target_count"] == 1
    assert payload["blocked_missing_env_vars"] == ["MISSING_MINIMAX_API_KEY"]
    assert payload["resume_targets"] == []


def test_beam_judged_resume_batch_cli_blocks_on_default_minimax_env(tmp_path: Path, monkeypatch):
    answers_root = tmp_path / "artifacts" / "beam_public_results"
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    upstream_repo_dir = tmp_path / "beam_upstream"
    output_file = tmp_path / "artifacts" / "beam_resume_batch.json"

    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions").mkdir(parents=True)
    conv1_dir = answers_root / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9" / "100K" / "1"
    eval_path = conv1_dir / "evaluation-domain_chip_memory_answers.json"
    answers_path = conv1_dir / "domain_chip_memory_answers.json"
    conv1_dir.mkdir(parents=True)
    eval_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"llm_judge_score": 1.0}],
                "event_ordering": [{"tau_norm": 0.5}],
            }
        ),
        encoding="utf-8",
    )
    answers_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"question": "q1", "llm_response": "a1"}],
                "event_ordering": [{"question": "q2", "llm_response": "a2"}],
                "summarization": [{"question": "q3", "llm_response": "a3"}],
            }
        ),
        encoding="utf-8",
    )
    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps(
            {
                "information_extraction": [{"rubric": ["extract"]}],
                "event_ordering": [{"rubric": ["order"]}],
                "summarization": [{"rubric": ["summary"]}],
            }
        ),
        encoding="utf-8",
    )

    benchmark_runs_dir.mkdir(parents=True)
    manifest_path = benchmark_runs_dir / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json"
    manifest_path.write_text(
        json.dumps(
            {
                "status": "partial",
                "upstream_repo_dir": str(upstream_repo_dir),
                "answers_root": str(conv1_dir.parent.parent),
                "official_chat_size_dir": "100K",
                "requested_chat_size": "128K",
                "conversation_ids": ["1"],
                "input_directory": str(conv1_dir.parent),
                "result_file_name": "domain_chip_memory_answers.json",
                "start_index": 0,
                "end_index": 1,
                "max_workers": 10,
                "judge_config": {
                    "provider": "minimax",
                    "model": "MiniMax-M2.7",
                    "base_url": "https://api.minimax.io/v1",
                },
                "evaluation_files": [str(eval_path)],
                "missing_evaluation_files": [],
                "stderr_tail": ["Timed out waiting for MiniMax BEAM evaluation worker after 900 seconds."],
                "aggregate_summary": {"overall_average": 0.75},
            }
        ),
        encoding="utf-8",
    )

    def fail_run(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called when default MiniMax env is missing")

    monkeypatch.setattr(cli.subprocess, "run", fail_run)
    monkeypatch.setenv("MINIMAX_API_KEY", "")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "beam-judged-resume-batch",
            "--artifact-prefix",
            "official_beam_128k_summary_synthesis_memory_heuristic_v1_",
            "--answers-root",
            str(answers_root),
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--execute",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["execute_requested"] is True
    assert payload["runnable_target_count"] == 0
    assert payload["blocked_target_count"] == 1
    assert payload["blocked_missing_env_vars"] == ["MINIMAX_API_KEY"]
    assert payload["executed_target_count"] == 1
    assert payload["execution_status_counts"] == {"blocked_missing_env": 1}
    assert payload["completed_execution_count"] == 0
    assert payload["failed_execution_count"] == 0
    assert payload["blocked_execution_count"] == 1
    assert payload["execution_results"][0]["status"] == "blocked_missing_env"
    assert payload["execution_results"][0]["missing_env_var"] == "MINIMAX_API_KEY"
    assert payload["execution_results"][0]["executed_command"] == []
    assert payload["execution_results"][0]["stderr_tail"] == ["Missing required environment variable: MINIMAX_API_KEY"]


def test_beam_judged_resume_batch_cli_only_runnable_filters_blocked_targets(tmp_path: Path, monkeypatch):
    answers_root = tmp_path / "artifacts" / "beam_public_results"
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    upstream_repo_dir = tmp_path / "beam_upstream"
    output_file = tmp_path / "artifacts" / "beam_resume_batch.json"
    script_file = tmp_path / "artifacts" / "beam_resume_batch.ps1"

    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions").mkdir(parents=True)
    conv1_dir = answers_root / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9" / "100K" / "1"
    eval_path = conv1_dir / "evaluation-domain_chip_memory_answers.json"
    answers_path = conv1_dir / "domain_chip_memory_answers.json"
    conv1_dir.mkdir(parents=True)
    eval_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"llm_judge_score": 1.0}],
                "event_ordering": [{"tau_norm": 0.5}],
            }
        ),
        encoding="utf-8",
    )
    answers_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"question": "q1", "llm_response": "a1"}],
                "event_ordering": [{"question": "q2", "llm_response": "a2"}],
                "summarization": [{"question": "q3", "llm_response": "a3"}],
            }
        ),
        encoding="utf-8",
    )
    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps(
            {
                "information_extraction": [{"rubric": ["extract"]}],
                "event_ordering": [{"rubric": ["order"]}],
                "summarization": [{"rubric": ["summary"]}],
            }
        ),
        encoding="utf-8",
    )

    benchmark_runs_dir.mkdir(parents=True)
    manifest_path = benchmark_runs_dir / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json"
    manifest_path.write_text(
        json.dumps(
            {
                "status": "partial",
                "upstream_repo_dir": str(upstream_repo_dir),
                "answers_root": str(conv1_dir.parent.parent),
                "official_chat_size_dir": "100K",
                "requested_chat_size": "128K",
                "conversation_ids": ["1"],
                "input_directory": str(conv1_dir.parent),
                "result_file_name": "domain_chip_memory_answers.json",
                "start_index": 0,
                "end_index": 1,
                "max_workers": 10,
                "judge_config": {
                    "provider": "minimax",
                    "model": "MiniMax-M2.7",
                    "base_url": "https://api.minimax.io/v1",
                    "api_key_env": "MISSING_MINIMAX_API_KEY",
                },
                "evaluation_files": [str(eval_path)],
                "missing_evaluation_files": [],
                "stderr_tail": ["Timed out waiting for MiniMax BEAM evaluation worker after 900 seconds."],
                "aggregate_summary": {"overall_average": 0.75},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv("MISSING_MINIMAX_API_KEY", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "beam-judged-resume-batch",
            "--artifact-prefix",
            "official_beam_128k_summary_synthesis_memory_heuristic_v1_",
            "--answers-root",
            str(answers_root),
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--only-runnable",
            "--script-file",
            str(script_file),
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["only_runnable"] is True
    assert payload["discovered_target_count"] == 1
    assert payload["resume_target_count"] == 0
    assert payload["filtered_out_target_count"] == 1
    assert payload["runnable_target_count"] == 0
    assert payload["blocked_target_count"] == 1
    assert payload["blocked_missing_env_vars"] == ["MISSING_MINIMAX_API_KEY"]
    assert payload["resume_targets"] == []
    assert payload["script_file"] == str(script_file)
    assert payload["script_lines"] == [
        "$ErrorActionPreference = 'Stop'",
        "# Generated by beam-judged-resume-batch for official_beam_128k_summary_synthesis_memory_heuristic_v1_",
    ]
    assert payload["script_text"] == "$ErrorActionPreference = 'Stop'\n# Generated by beam-judged-resume-batch for official_beam_128k_summary_synthesis_memory_heuristic_v1_\n"
    assert script_file.read_text(encoding="utf-8") == payload["script_text"]


def test_beam_judged_resume_batch_cli_writes_powershell_script(tmp_path: Path, monkeypatch):
    answers_root = tmp_path / "artifacts" / "beam_public_results"
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    upstream_repo_dir = tmp_path / "beam_upstream"
    output_file = tmp_path / "artifacts" / "beam_resume_batch.json"
    script_file = tmp_path / "artifacts" / "beam_resume_batch.ps1"

    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions").mkdir(parents=True)
    conv1_dir = answers_root / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9" / "100K" / "1"
    eval_path = conv1_dir / "evaluation-domain_chip_memory_answers.json"
    answers_path = conv1_dir / "domain_chip_memory_answers.json"
    conv1_dir.mkdir(parents=True)
    eval_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"llm_judge_score": 1.0}],
                "event_ordering": [{"tau_norm": 0.5}],
            }
        ),
        encoding="utf-8",
    )
    answers_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"question": "q1", "llm_response": "a1"}],
                "event_ordering": [{"question": "q2", "llm_response": "a2"}],
                "summarization": [{"question": "q3", "llm_response": "a3"}],
            }
        ),
        encoding="utf-8",
    )
    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps(
            {
                "information_extraction": [{"rubric": ["extract"]}],
                "event_ordering": [{"rubric": ["order"]}],
                "summarization": [{"rubric": ["summary"]}],
            }
        ),
        encoding="utf-8",
    )

    benchmark_runs_dir.mkdir(parents=True)
    manifest_path = benchmark_runs_dir / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json"
    manifest_path.write_text(
        json.dumps(
            {
                "status": "partial",
                "upstream_repo_dir": str(upstream_repo_dir),
                "answers_root": str(conv1_dir.parent.parent),
                "official_chat_size_dir": "100K",
                "requested_chat_size": "128K",
                "conversation_ids": ["1"],
                "input_directory": str(conv1_dir.parent),
                "result_file_name": "domain_chip_memory_answers.json",
                "start_index": 0,
                "end_index": 1,
                "max_workers": 10,
                "judge_config": {
                    "provider": "minimax",
                    "model": "MiniMax-M2.7",
                    "base_url": "https://api.minimax.io/v1",
                    "api_key_env": "MINIMAX_API_KEY",
                },
                "evaluation_files": [str(eval_path)],
                "missing_evaluation_files": [],
                "stderr_tail": ["Timed out waiting for MiniMax BEAM evaluation worker after 900 seconds."],
                "aggregate_summary": {"overall_average": 0.75},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "beam-judged-resume-batch",
            "--artifact-prefix",
            "official_beam_128k_summary_synthesis_memory_heuristic_v1_",
            "--answers-root",
            str(answers_root),
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--script-file",
            str(script_file),
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["benchmark_name"] == "BEAM"
    assert payload["source_mode"] == "official_public_evaluation_resume_batch"
    assert payload["resume_target_count"] == 1
    assert payload["runnable_target_count"] == 1
    assert payload["blocked_target_count"] == 0
    assert payload["blocked_missing_env_vars"] == []
    assert payload["script_file"] == str(script_file)
    assert payload["script_line_count"] >= 3
    assert payload["script_lines"][0] == "$ErrorActionPreference = 'Stop'"
    assert "conv1_v9_official_eval.json" in payload["script_lines"][2]
    assert "run-beam-official-evaluation" in payload["script_text"]
    assert script_file.read_text(encoding="utf-8") == payload["script_text"]


def test_beam_judged_resume_batch_cli_can_execute_targets(tmp_path: Path, monkeypatch):
    answers_root = tmp_path / "artifacts" / "beam_public_results"
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    upstream_repo_dir = tmp_path / "beam_upstream"
    output_file = tmp_path / "artifacts" / "beam_resume_batch.json"

    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions").mkdir(parents=True)
    conv1_dir = answers_root / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9" / "100K" / "1"
    eval_path = conv1_dir / "evaluation-domain_chip_memory_answers.json"
    answers_path = conv1_dir / "domain_chip_memory_answers.json"
    conv1_dir.mkdir(parents=True)
    eval_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"llm_judge_score": 1.0}],
                "event_ordering": [{"tau_norm": 0.5}],
            }
        ),
        encoding="utf-8",
    )
    answers_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"question": "q1", "llm_response": "a1"}],
                "event_ordering": [{"question": "q2", "llm_response": "a2"}],
                "summarization": [{"question": "q3", "llm_response": "a3"}],
            }
        ),
        encoding="utf-8",
    )
    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps(
            {
                "information_extraction": [{"rubric": ["extract"]}],
                "event_ordering": [{"rubric": ["order"]}],
                "summarization": [{"rubric": ["summary"]}],
            }
        ),
        encoding="utf-8",
    )

    benchmark_runs_dir.mkdir(parents=True)
    manifest_path = benchmark_runs_dir / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json"
    manifest_path.write_text(
        json.dumps(
            {
                "status": "partial",
                "upstream_repo_dir": str(upstream_repo_dir),
                "answers_root": str(conv1_dir.parent.parent),
                "official_chat_size_dir": "100K",
                "requested_chat_size": "128K",
                "conversation_ids": ["1"],
                "input_directory": str(conv1_dir.parent),
                "result_file_name": "domain_chip_memory_answers.json",
                "start_index": 0,
                "end_index": 1,
                "max_workers": 10,
                "judge_config": {
                    "provider": "minimax",
                    "model": "MiniMax-M2.7",
                    "base_url": "https://api.minimax.io/v1",
                    "api_key_env": "MINIMAX_API_KEY",
                },
                "evaluation_files": [str(eval_path)],
                "missing_evaluation_files": [],
                "stderr_tail": ["Timed out waiting for MiniMax BEAM evaluation worker after 900 seconds."],
                "aggregate_summary": {"overall_average": 0.75},
            }
        ),
        encoding="utf-8",
    )

    class FakeCompletedProcess:
        def __init__(self):
            self.returncode = 0
            self.stdout = "Question Type: summarization\nQuestion Index: 0\n"
            self.stderr = ""

    captured_commands = []

    def fake_run(command, *, cwd, capture_output, text, check):
        captured_commands.append(
            {
                "command": command,
                "cwd": cwd,
                "capture_output": capture_output,
                "text": text,
                "check": check,
            }
        )
        return FakeCompletedProcess()

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "beam-judged-resume-batch",
            "--artifact-prefix",
            "official_beam_128k_summary_synthesis_memory_heuristic_v1_",
            "--answers-root",
            str(answers_root),
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--execute",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["execute_requested"] is True
    assert payload["runnable_target_count"] == 1
    assert payload["blocked_target_count"] == 0
    assert payload["blocked_missing_env_vars"] == []
    assert payload["executed_target_count"] == 1
    assert payload["execution_status_counts"] == {"completed": 1}
    assert payload["completed_execution_count"] == 1
    assert payload["failed_execution_count"] == 0
    assert payload["blocked_execution_count"] == 0
    assert payload["execution_results"][0]["status"] == "completed"
    assert payload["execution_results"][0]["return_code"] == 0
    assert payload["execution_results"][0]["stdout_tail"] == ["Question Type: summarization", "Question Index: 0"]
    assert captured_commands[0]["command"][0] == sys.executable
    assert captured_commands[0]["command"][3] == "run-beam-official-evaluation"
    assert captured_commands[0]["cwd"] == str(tmp_path.resolve())
    assert captured_commands[0]["capture_output"] is True
    assert captured_commands[0]["text"] is True
    assert captured_commands[0]["check"] is False


def test_beam_judged_resume_batch_cli_blocks_execution_when_judge_env_missing(tmp_path: Path, monkeypatch):
    answers_root = tmp_path / "artifacts" / "beam_public_results"
    benchmark_runs_dir = tmp_path / "artifacts" / "benchmark_runs"
    upstream_repo_dir = tmp_path / "beam_upstream"
    output_file = tmp_path / "artifacts" / "beam_resume_batch.json"

    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions").mkdir(parents=True)
    conv1_dir = answers_root / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9" / "100K" / "1"
    eval_path = conv1_dir / "evaluation-domain_chip_memory_answers.json"
    answers_path = conv1_dir / "domain_chip_memory_answers.json"
    conv1_dir.mkdir(parents=True)
    eval_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"llm_judge_score": 1.0}],
                "event_ordering": [{"tau_norm": 0.5}],
            }
        ),
        encoding="utf-8",
    )
    answers_path.write_text(
        json.dumps(
            {
                "information_extraction": [{"question": "q1", "llm_response": "a1"}],
                "event_ordering": [{"question": "q2", "llm_response": "a2"}],
                "summarization": [{"question": "q3", "llm_response": "a3"}],
            }
        ),
        encoding="utf-8",
    )
    (upstream_repo_dir / "chats" / "100K" / "1" / "probing_questions" / "probing_questions.json").write_text(
        json.dumps(
            {
                "information_extraction": [{"rubric": ["extract"]}],
                "event_ordering": [{"rubric": ["order"]}],
                "summarization": [{"rubric": ["summary"]}],
            }
        ),
        encoding="utf-8",
    )

    benchmark_runs_dir.mkdir(parents=True)
    manifest_path = benchmark_runs_dir / "official_beam_128k_summary_synthesis_memory_heuristic_v1_conv1_v9_official_eval.json"
    manifest_path.write_text(
        json.dumps(
            {
                "status": "partial",
                "upstream_repo_dir": str(upstream_repo_dir),
                "answers_root": str(conv1_dir.parent.parent),
                "official_chat_size_dir": "100K",
                "requested_chat_size": "128K",
                "conversation_ids": ["1"],
                "input_directory": str(conv1_dir.parent),
                "result_file_name": "domain_chip_memory_answers.json",
                "start_index": 0,
                "end_index": 1,
                "max_workers": 10,
                "judge_config": {
                    "provider": "minimax",
                    "model": "MiniMax-M2.7",
                    "base_url": "https://api.minimax.io/v1",
                    "api_key_env": "MISSING_MINIMAX_API_KEY",
                },
                "evaluation_files": [str(eval_path)],
                "missing_evaluation_files": [],
                "stderr_tail": ["Timed out waiting for MiniMax BEAM evaluation worker after 900 seconds."],
                "aggregate_summary": {"overall_average": 0.75},
            }
        ),
        encoding="utf-8",
    )

    def fail_run(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called when judge env is missing")

    monkeypatch.setattr(cli.subprocess, "run", fail_run)
    monkeypatch.delenv("MISSING_MINIMAX_API_KEY", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "beam-judged-resume-batch",
            "--artifact-prefix",
            "official_beam_128k_summary_synthesis_memory_heuristic_v1_",
            "--answers-root",
            str(answers_root),
            "--benchmark-runs-dir",
            str(benchmark_runs_dir),
            "--repo-root",
            str(tmp_path),
            "--execute",
            "--write",
            str(output_file),
        ],
    )
    cli.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["execute_requested"] is True
    assert payload["runnable_target_count"] == 0
    assert payload["blocked_target_count"] == 1
    assert payload["blocked_missing_env_vars"] == ["MISSING_MINIMAX_API_KEY"]
    assert payload["executed_target_count"] == 1
    assert payload["execution_status_counts"] == {"blocked_missing_env": 1}
    assert payload["completed_execution_count"] == 0
    assert payload["failed_execution_count"] == 0
    assert payload["blocked_execution_count"] == 1
    assert payload["execution_results"][0]["status"] == "blocked_missing_env"
    assert payload["execution_results"][0]["missing_env_var"] == "MISSING_MINIMAX_API_KEY"
    assert payload["execution_results"][0]["executed_command"] == []
    assert payload["execution_results"][0]["stderr_tail"] == ["Missing required environment variable: MISSING_MINIMAX_API_KEY"]


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


def test_resume_openai_compatible_single_conversation_evaluation_normalizes_list_judge_response_for_remaining_rubric_categories(
    tmp_path: Path,
):
    probing_questions_path = tmp_path / "probing_questions.json"
    answers_path = tmp_path / "answers.json"
    output_path = tmp_path / "evaluation-answers.json"

    probing_questions_path.write_text(
        json.dumps(
            {
                "multi_session_reasoning": [{"rubric": ["combine prior sessions"]}],
                "summarization": [{"rubric": ["summarize the work so far"]}],
                "temporal_reasoning": [{"rubric": ["state the elapsed time"]}],
            }
        ),
        encoding="utf-8",
    )
    answers_path.write_text(
        json.dumps(
            {
                "multi_session_reasoning": [
                    {
                        "question": "How do these threads connect?",
                        "llm_response": "LLM response should include: combine prior sessions",
                    }
                ],
                "summarization": [
                    {
                        "question": "Summarize the work.",
                        "llm_response": "LLM response should include: summarize the work so far",
                    }
                ],
                "temporal_reasoning": [
                    {
                        "question": "How much time elapsed?",
                        "llm_response": "LLM response should include: state the elapsed time",
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
            assert "LLM response should include:" in prompt
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
            rubric_map = {
                "multi_session_reasoning": ["combine prior sessions"],
                "summarization": ["summarize the work so far"],
                "temporal_reasoning": ["state the elapsed time"],
            }
            return rubric_map[kwargs["key"]]

    beam_official_eval._resume_openai_compatible_single_conversation_evaluation(
        probing_questions_address=probing_questions_path,
        answers_file=answers_path,
        output_file=output_path,
        model=FakeModel(),
        compute_metrics_module=FakeComputeMetricsModule(),
        run_evaluation_module=FakeRunEvaluationModule(),
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["multi_session_reasoning"][0]["llm_judge_score"] == 1.0
    assert payload["multi_session_reasoning"][0]["llm_judge_responses"][0]["score"] == 1
    assert payload["summarization"][0]["llm_judge_score"] == 1.0
    assert payload["summarization"][0]["llm_judge_responses"][0]["score"] == 1
    assert payload["temporal_reasoning"][0]["llm_judge_score"] == 1.0
    assert payload["temporal_reasoning"][0]["llm_judge_responses"][0]["score"] == 1


def test_resume_openai_compatible_single_conversation_evaluation_coerces_empty_object_response(
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
            return FakeResponse("{}")

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
