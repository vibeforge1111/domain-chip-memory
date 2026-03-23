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
    assert "question_ids" not in payload["systems"]["beam_temporal_atom_router"]["run_manifest"]


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
