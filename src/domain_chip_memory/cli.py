from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

from .adapters import build_adapter_contract_summary
from .baselines import build_baseline_contract_summary
from .benchmark_registry import build_benchmark_scorecard, suggest_mutations
from .canonical_configs import get_canonical_configs
from .env import load_dotenv
from .experiments import build_experiment_contract_summary, run_candidate_comparison
from .loaders import (
    build_loader_contract_summary,
    load_goodai_config,
    load_goodai_definitions,
    load_locomo_json,
    load_longmemeval_json,
)
from .memory_systems import build_memory_system_contract_summary
from .packets import build_strategy_packet
from .providers import build_provider_contract_summary, get_provider
from .runner import build_runner_contract_summary, run_baseline
from .sample_data import demo_samples
from .scorecards import build_scorecard_contract_summary
from .baselines import build_full_context_packets, build_lexical_packets
from .watchtower import build_watchtower_summary
from .contracts import NormalizedBenchmarkSample


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _print(payload: dict | list[dict]) -> None:
    print(json.dumps(payload, indent=2))


def _limit_questions(
    samples: list[NormalizedBenchmarkSample],
    *,
    question_limit: int | None,
) -> list[NormalizedBenchmarkSample]:
    if question_limit is None:
        return samples
    return [replace(sample, questions=sample.questions[:question_limit]) for sample in samples]


def main() -> None:
    load_dotenv(Path.cwd() / ".env")

    parser = argparse.ArgumentParser(prog="domain_chip_memory.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("evaluate", help="Build the benchmark scorecard.")

    watchtower_parser = subparsers.add_parser("watchtower", help="Build the watchtower summary.")
    watchtower_parser.add_argument("--write", action="store_true")

    packets_parser = subparsers.add_parser("packets", help="Build the memory strategy packet.")
    packets_parser.add_argument("--write", action="store_true")

    subparsers.add_parser("suggest", help="List bounded mutation suggestions.")
    subparsers.add_parser("benchmark-targets", help="List the public benchmark target ledger.")
    subparsers.add_parser("benchmark-contracts", help="Show normalized benchmark contract and adapter summary.")
    subparsers.add_parser("baseline-contracts", help="Show baseline run manifest and baseline packet summary.")
    subparsers.add_parser("scorecard-contracts", help="Show scorecard contract summary.")
    subparsers.add_parser("canonical-configs", help="Show the canonical benchmark configuration choices.")
    subparsers.add_parser("demo-scorecards", help="Run local demo scorecards for baselines and candidate memory systems.")
    subparsers.add_parser("loader-contracts", help="Show benchmark file loader summary.")
    subparsers.add_parser("provider-contracts", help="Show model-provider interface summary.")
    subparsers.add_parser("runner-contracts", help="Show executable baseline runner summary.")
    subparsers.add_parser("memory-system-contracts", help="Show candidate memory-system contract summary.")
    subparsers.add_parser("experiment-contracts", help="Show compact benchmark comparison contract summary.")

    run_longmemeval = subparsers.add_parser("run-longmemeval-baseline", help="Run a baseline over a LongMemEval JSON file.")
    run_longmemeval.add_argument("data_file")
    run_longmemeval.add_argument("--baseline", choices=("full_context", "lexical", "beam_temporal_atom_router", "observational_temporal_memory", "dual_store_event_calendar_hybrid"), default="full_context")
    run_longmemeval.add_argument("--provider", default="heuristic_v1")
    run_longmemeval.add_argument("--limit", type=int)
    run_longmemeval.add_argument("--top-k-sessions", type=int, default=2)
    run_longmemeval.add_argument("--fallback-sessions", type=int, default=1)
    run_longmemeval.add_argument("--write")

    run_locomo = subparsers.add_parser("run-locomo-baseline", help="Run a baseline over a LoCoMo JSON file.")
    run_locomo.add_argument("data_file")
    run_locomo.add_argument("--baseline", choices=("full_context", "lexical", "beam_temporal_atom_router", "observational_temporal_memory", "dual_store_event_calendar_hybrid"), default="full_context")
    run_locomo.add_argument("--provider", default="heuristic_v1")
    run_locomo.add_argument("--limit", type=int)
    run_locomo.add_argument("--question-limit", type=int)
    run_locomo.add_argument("--top-k-sessions", type=int, default=2)
    run_locomo.add_argument("--fallback-sessions", type=int, default=1)
    run_locomo.add_argument("--write")

    run_goodai = subparsers.add_parser("run-goodai-baseline", help="Run a baseline over GoodAI config and definitions.")
    run_goodai.add_argument("config_file")
    run_goodai.add_argument("definitions_dir")
    run_goodai.add_argument("--dataset-name")
    run_goodai.add_argument("--baseline", choices=("full_context", "lexical", "beam_temporal_atom_router", "observational_temporal_memory", "dual_store_event_calendar_hybrid"), default="full_context")
    run_goodai.add_argument("--provider", default="heuristic_v1")
    run_goodai.add_argument("--limit", type=int)
    run_goodai.add_argument("--top-k-sessions", type=int, default=2)
    run_goodai.add_argument("--fallback-sessions", type=int, default=1)
    run_goodai.add_argument("--write")

    compare_longmemeval = subparsers.add_parser("compare-longmemeval-local", help="Run all default systems over a LongMemEval JSON file and emit a compact comparison.")
    compare_longmemeval.add_argument("data_file")
    compare_longmemeval.add_argument("--provider", default="heuristic_v1")
    compare_longmemeval.add_argument("--limit", type=int)
    compare_longmemeval.add_argument("--top-k-sessions", type=int, default=2)
    compare_longmemeval.add_argument("--fallback-sessions", type=int, default=1)
    compare_longmemeval.add_argument("--write")

    compare_locomo = subparsers.add_parser("compare-locomo-local", help="Run all default systems over a LoCoMo JSON file and emit a compact comparison.")
    compare_locomo.add_argument("data_file")
    compare_locomo.add_argument("--provider", default="heuristic_v1")
    compare_locomo.add_argument("--limit", type=int)
    compare_locomo.add_argument("--question-limit", type=int)
    compare_locomo.add_argument("--top-k-sessions", type=int, default=2)
    compare_locomo.add_argument("--fallback-sessions", type=int, default=1)
    compare_locomo.add_argument("--write")

    compare_goodai = subparsers.add_parser("compare-goodai-local", help="Run all default systems over GoodAI config and definitions and emit a compact comparison.")
    compare_goodai.add_argument("config_file")
    compare_goodai.add_argument("definitions_dir")
    compare_goodai.add_argument("--dataset-name")
    compare_goodai.add_argument("--provider", default="heuristic_v1")
    compare_goodai.add_argument("--limit", type=int)
    compare_goodai.add_argument("--top-k-sessions", type=int, default=2)
    compare_goodai.add_argument("--fallback-sessions", type=int, default=1)
    compare_goodai.add_argument("--write")

    args = parser.parse_args()
    root = Path.cwd()

    if args.command == "evaluate":
        _print(build_benchmark_scorecard())
        return

    if args.command == "watchtower":
        payload = build_watchtower_summary(root)
        if args.write:
            _write_json(root / "artifacts" / "watchtower_summary.json", payload)
        _print(payload)
        return

    if args.command == "packets":
        payload = build_strategy_packet()
        if args.write:
            _write_json(root / "artifacts" / "memory_system_strategy_packet.json", payload)
        _print(payload)
        return

    if args.command == "suggest":
        _print(suggest_mutations())
        return

    if args.command == "benchmark-targets":
        _print(build_benchmark_scorecard()["public_targets"])
        return

    if args.command == "benchmark-contracts":
        _print(build_adapter_contract_summary())
        return

    if args.command == "baseline-contracts":
        _print(build_baseline_contract_summary())
        return

    if args.command == "scorecard-contracts":
        _print(build_scorecard_contract_summary())
        return

    if args.command == "canonical-configs":
        _print(get_canonical_configs())
        return

    if args.command == "demo-scorecards":
        samples = demo_samples()
        _print(
            {
                "full_context": run_baseline(
                    samples,
                    baseline_name="full_context",
                    provider=get_provider("heuristic_v1"),
                ),
                "lexical": run_baseline(
                    samples,
                    baseline_name="lexical",
                    provider=get_provider("heuristic_v1"),
                    top_k_sessions=1,
                ),
                "beam_temporal_atom_router": run_baseline(
                    samples,
                    baseline_name="beam_temporal_atom_router",
                    provider=get_provider("heuristic_v1"),
                    top_k_sessions=2,
                    fallback_sessions=1,
                ),
                "observational_temporal_memory": run_baseline(
                    samples,
                    baseline_name="observational_temporal_memory",
                    provider=get_provider("heuristic_v1"),
                    top_k_sessions=2,
                    fallback_sessions=1,
                ),
                "dual_store_event_calendar_hybrid": run_baseline(
                    samples,
                    baseline_name="dual_store_event_calendar_hybrid",
                    provider=get_provider("heuristic_v1"),
                    top_k_sessions=2,
                    fallback_sessions=1,
                ),
            }
        )
        return

    if args.command == "loader-contracts":
        _print(build_loader_contract_summary())
        return

    if args.command == "provider-contracts":
        _print(build_provider_contract_summary())
        return

    if args.command == "runner-contracts":
        _print(build_runner_contract_summary())
        return

    if args.command == "memory-system-contracts":
        _print(build_memory_system_contract_summary())
        return

    if args.command == "experiment-contracts":
        _print(build_experiment_contract_summary())
        return

    if args.command == "run-longmemeval-baseline":
        samples = load_longmemeval_json(args.data_file, limit=args.limit)
        payload = run_baseline(
            samples,
            baseline_name=args.baseline,
            provider=get_provider(args.provider),
            top_k_sessions=args.top_k_sessions,
            fallback_sessions=args.fallback_sessions,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "run-locomo-baseline":
        samples = _limit_questions(
            load_locomo_json(args.data_file, limit=args.limit),
            question_limit=args.question_limit,
        )
        payload = run_baseline(
            samples,
            baseline_name=args.baseline,
            provider=get_provider(args.provider),
            top_k_sessions=args.top_k_sessions,
            fallback_sessions=args.fallback_sessions,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "run-goodai-baseline":
        config = load_goodai_config(args.config_file)
        samples = load_goodai_definitions(
            args.definitions_dir,
            config=config,
            dataset_name=args.dataset_name,
            limit=args.limit,
        )
        payload = run_baseline(
            samples,
            baseline_name=args.baseline,
            provider=get_provider(args.provider),
            top_k_sessions=args.top_k_sessions,
            fallback_sessions=args.fallback_sessions,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "compare-longmemeval-local":
        samples = load_longmemeval_json(args.data_file, limit=args.limit)
        payload = run_candidate_comparison(
            samples,
            provider=get_provider(args.provider),
            top_k_sessions=args.top_k_sessions,
            fallback_sessions=args.fallback_sessions,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "compare-locomo-local":
        samples = _limit_questions(
            load_locomo_json(args.data_file, limit=args.limit),
            question_limit=args.question_limit,
        )
        payload = run_candidate_comparison(
            samples,
            provider=get_provider(args.provider),
            top_k_sessions=args.top_k_sessions,
            fallback_sessions=args.fallback_sessions,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "compare-goodai-local":
        config = load_goodai_config(args.config_file)
        samples = load_goodai_definitions(
            args.definitions_dir,
            config=config,
            dataset_name=args.dataset_name,
            limit=args.limit,
        )
        payload = run_candidate_comparison(
            samples,
            provider=get_provider(args.provider),
            top_k_sessions=args.top_k_sessions,
            fallback_sessions=args.fallback_sessions,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return


if __name__ == "__main__":
    main()
