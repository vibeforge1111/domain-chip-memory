from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

from .adapters import build_adapter_contract_summary
from .baselines import build_baseline_contract_summary
from .benchmark_registry import build_benchmark_scorecard, suggest_mutations
from .canonical_configs import get_canonical_configs
from .env import load_dotenv
from .experiments import build_experiment_contract_summary, run_candidate_comparison
from .loaders import (
    build_loader_contract_summary,
    load_beam_json,
    load_beam_public_dir,
    load_goodai_config,
    load_goodai_definitions,
    load_locomo_json,
    load_longmemeval_json,
)
from .memory_contract_summary import build_memory_system_contract_summary
from .packets import build_strategy_packet
from .providers import build_provider_contract_summary, get_provider
from .runner import build_runner_contract_summary, run_baseline
from .sample_data import demo_samples, product_memory_samples
from .scorecards import BaselinePrediction, build_scorecard, build_scorecard_contract_summary
from .sdk import (
    AnswerExplanationRequest,
    CurrentStateRequest,
    HistoricalStateRequest,
    MemoryWriteRequest,
    SparkMemorySDK,
    build_sdk_contract_summary,
    build_sdk_maintenance_replay_contract_summary,
)
from .baselines import build_full_context_packets, build_lexical_packets
from .beam_official_eval import (
    export_beam_public_answers_from_scorecard,
    run_beam_official_evaluation,
    summarize_beam_official_evaluation,
)
from .spark_shadow import (
    SparkShadowIngestAdapter,
    SparkShadowIngestRequest,
    SparkShadowProbe,
    SparkShadowTurn,
    build_shadow_ingest_contract_summary,
    build_shadow_report,
    build_shadow_replay_contract_summary,
    validate_shadow_replay_payload,
)
from .spark_integration import build_spark_integration_contract_summary
from .spark_kb import build_spark_kb_contract_summary, build_spark_kb_health_report, scaffold_spark_knowledge_base
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
    question_offset: int = 0,
    question_limit: int | None,
) -> list[NormalizedBenchmarkSample]:
    if question_offset < 0:
        raise ValueError("question_offset must be non-negative.")
    if question_limit is not None and question_limit < 0:
        raise ValueError("question_limit must be non-negative.")
    if question_offset == 0 and question_limit is None:
        return samples
    return [
        replace(
            sample,
            questions=sample.questions[question_offset : question_offset + question_limit]
            if question_limit is not None
            else sample.questions[question_offset:],
        )
        for sample in samples
    ]


def _load_resume_predictions(path: Path | None) -> list[BaselinePrediction]:
    if path is None or not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_predictions = payload.get("predictions", [])
    if not isinstance(raw_predictions, list):
        raise ValueError("Resume artifact must contain a predictions list.")
    predictions: list[BaselinePrediction] = []
    for item in raw_predictions:
        if not isinstance(item, dict):
            continue
        predictions.append(
            BaselinePrediction(
                benchmark_name=str(item.get("benchmark_name", "")),
                baseline_name=str(item.get("baseline_name", "")),
                sample_id=str(item.get("sample_id", "")),
                question_id=str(item.get("question_id", "")),
                category=str(item.get("category", "")),
                predicted_answer=str(item.get("predicted_answer", "")),
                expected_answers=[str(answer) for answer in item.get("expected_answers", [])],
                is_correct=bool(item.get("is_correct")),
                question=str(item.get("question", "")),
                metadata=dict(item.get("metadata", {})),
            )
        )
    return predictions


def _run_with_progress(
    samples: list[NormalizedBenchmarkSample],
    *,
    baseline_name: str,
    provider_name: str,
    top_k_sessions: int,
    fallback_sessions: int,
    write_path: Path | None,
    resume_path: Path | None,
) -> dict:
    existing_predictions = _load_resume_predictions(resume_path)

    def progress_callback(manifest: dict, predictions: list[BaselinePrediction], event: dict) -> None:
        if event["event"] == "resume":
            print(
                f"[resume] {event['completed']}/{event['total']} completed; {event['remaining']} remaining",
                file=sys.stderr,
            )
        elif event["event"] == "start":
            print(
                f"[start] {event['index']}/{event['total']} {event['question_id']}",
                file=sys.stderr,
            )
        elif event["event"] == "completed":
            verdict = "correct" if event["is_correct"] else "wrong"
            print(
                f"[done] {event['completed']}/{event['total']} {event['question_id']} -> {verdict}",
                file=sys.stderr,
            )
        elif event["event"] == "error":
            print(
                f"[error] {event['completed']}/{event['total']} stopped at {event['question_id']}: {event['error']}",
                file=sys.stderr,
            )
        if write_path and event["event"] in {"resume", "completed", "error"}:
            partial_payload = build_scorecard(manifest, predictions)
            partial_payload["run_manifest"].setdefault("metadata", {})["completion_status"] = (
                "complete" if len(predictions) >= int(manifest.get("question_count", len(predictions))) else "partial"
            )
            _write_json(write_path, partial_payload)

    return run_baseline(
        samples,
        baseline_name=baseline_name,
        provider=get_provider(provider_name),
        top_k_sessions=top_k_sessions,
        fallback_sessions=fallback_sessions,
        existing_predictions=existing_predictions,
        progress_callback=progress_callback,
    )


def _build_demo_shadow_report_payload() -> dict:
    adapter = SparkShadowIngestAdapter()
    evaluations = []

    first_ingest = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="spark-shadow-demo-1",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="Hello there.",
                    timestamp="2025-01-01T09:00:00Z",
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="assistant",
                    content="Noted.",
                    timestamp="2025-01-01T09:01:00Z",
                ),
                SparkShadowTurn(
                    message_id="m3",
                    role="user",
                    content="I moved to Dubai.",
                    timestamp="2025-03-01T09:00:00Z",
                ),
            ],
        )
    )
    evaluations.append(
        adapter.evaluate_ingest(
            first_ingest,
            probes=[
                SparkShadowProbe(
                    probe_id="demo-p1",
                    probe_type="current_state",
                    subject="user",
                    predicate="location",
                    expected_value="Dubai",
                ),
                SparkShadowProbe(
                    probe_id="demo-p2",
                    probe_type="evidence",
                    subject="user",
                    predicate="location",
                    expected_value="Dubai",
                    min_results=1,
                ),
            ],
        )
    )

    second_ingest = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="spark-shadow-demo-2",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="I live in London.",
                    timestamp="2025-01-01T09:00:00Z",
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="user",
                    content="I moved to Abu Dhabi.",
                    timestamp="2025-06-01T09:00:00Z",
                ),
            ],
        )
    )
    evaluations.append(
        adapter.evaluate_ingest(
            second_ingest,
            probes=[
                SparkShadowProbe(
                    probe_id="demo-p3",
                    probe_type="historical_state",
                    subject="user",
                    predicate="location",
                    as_of="2025-05-01T00:00:00Z",
                    expected_value="London",
                )
            ],
        )
    )

    report = build_shadow_report(evaluations)
    return {
        "evaluations": [asdict(evaluation) for evaluation in evaluations],
        "report": asdict(report),
    }


def _load_shadow_evaluations(data_file: str) -> list:
    payload = json.loads(Path(data_file).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Shadow replay file must contain a JSON object.")
    raw_conversations = payload.get("conversations", [])
    if not isinstance(raw_conversations, list):
        raise ValueError("Shadow replay file must contain a conversations list.")

    writable_roles = payload.get("writable_roles")
    if isinstance(writable_roles, list):
        adapter = SparkShadowIngestAdapter(writable_roles=tuple(str(role) for role in writable_roles))
    else:
        adapter = SparkShadowIngestAdapter()

    evaluations = []
    for index, item in enumerate(raw_conversations):
        if not isinstance(item, dict):
            raise ValueError(f"Conversation at index {index} must be an object.")
        conversation_id = str(item.get("conversation_id", "")).strip()
        if not conversation_id:
            raise ValueError(f"Conversation at index {index} must include conversation_id.")
        turns = [
            SparkShadowTurn(
                message_id=str(turn.get("message_id", "")),
                role=str(turn.get("role", "")),
                content=str(turn.get("content", "")),
                timestamp=str(turn.get("timestamp")) if turn.get("timestamp") is not None else None,
                metadata=dict(turn.get("metadata", {})),
            )
            for turn in item.get("turns", [])
            if isinstance(turn, dict)
        ]
        probes = [
            SparkShadowProbe(
                probe_id=str(probe.get("probe_id", "")),
                probe_type=str(probe.get("probe_type", "")),
                subject=str(probe.get("subject")) if probe.get("subject") is not None else None,
                predicate=str(probe.get("predicate")) if probe.get("predicate") is not None else None,
                query=str(probe.get("query")) if probe.get("query") is not None else None,
                as_of=str(probe.get("as_of")) if probe.get("as_of") is not None else None,
                expected_value=str(probe.get("expected_value")) if probe.get("expected_value") is not None else None,
                min_results=int(probe.get("min_results", 1) or 1),
            )
            for probe in item.get("probes", [])
            if isinstance(probe, dict)
        ]
        ingest_result = adapter.ingest_conversation(
            SparkShadowIngestRequest(
                conversation_id=conversation_id,
                session_id=str(item.get("session_id")) if item.get("session_id") is not None else None,
                turns=turns,
                metadata=dict(item.get("metadata", {})),
            )
        )
        evaluations.append(adapter.evaluate_ingest(ingest_result, probes=probes))

    return evaluations


def _build_shadow_report_payload_from_evaluations(evaluations: list) -> dict:
    report = build_shadow_report(evaluations)
    return {
        "evaluations": [asdict(evaluation) for evaluation in evaluations],
        "report": asdict(report),
    }


def _load_shadow_report_payload(data_file: str) -> dict:
    return _build_shadow_report_payload_from_evaluations(_load_shadow_evaluations(data_file))


def _validate_shadow_replay_payload(data_file: str) -> dict:
    payload = json.loads(Path(data_file).read_text(encoding="utf-8"))
    summary = validate_shadow_replay_payload(payload)
    summary["file"] = str(Path(data_file))
    return summary


def _validate_shadow_replay_batch_payload(data_dir: str, *, glob_pattern: str = "*.json") -> dict:
    root = Path(data_dir)
    files = sorted(path for path in root.glob(glob_pattern) if path.is_file())
    if not files:
        raise ValueError(f"No shadow replay files matched '{glob_pattern}' in {root}.")

    validations = [_validate_shadow_replay_payload(str(path)) for path in files]
    invalid_files = [item["file"] for item in validations if not item["valid"]]
    total_errors = sum(len(item["errors"]) for item in validations)
    total_warnings = sum(len(item["warnings"]) for item in validations)
    return {
        "valid": not invalid_files,
        "file_count": len(validations),
        "valid_file_count": len(validations) - len(invalid_files),
        "invalid_file_count": len(invalid_files),
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "invalid_files": invalid_files,
        "source_files": [str(path) for path in files],
        "source_validations": validations,
    }


def _load_shadow_report_batch_payload(data_dir: str, *, glob_pattern: str = "*.json") -> dict:
    root = Path(data_dir)
    files = sorted(path for path in root.glob(glob_pattern) if path.is_file())
    if not files:
        raise ValueError(f"No shadow replay files matched '{glob_pattern}' in {root}.")

    all_evaluations = []
    source_reports = []
    for path in files:
        evaluations = _load_shadow_evaluations(str(path))
        source_payload = _build_shadow_report_payload_from_evaluations(evaluations)
        source_reports.append(
            {
                "file": str(path),
                "run_count": source_payload["report"]["run_count"],
                "summary": source_payload["report"]["summary"],
            }
        )
        all_evaluations.extend(evaluations)

    payload = _build_shadow_report_payload_from_evaluations(all_evaluations)
    payload["source_files"] = [str(path) for path in files]
    payload["source_reports"] = source_reports
    return payload


def _build_demo_sdk_maintenance_payload() -> dict:
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="user",
            predicate="location",
            value="London",
            timestamp="2025-01-01T09:00:00Z",
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="update",
            subject="user",
            predicate="location",
            value="Dubai",
            timestamp="2025-03-01T09:00:00Z",
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="delete",
            subject="user",
            predicate="location",
            timestamp="2025-04-01T09:00:00Z",
        )
    )
    sdk.write_event(
        MemoryWriteRequest(
            text="",
            operation="event",
            subject="user",
            predicate="move",
            value="Dubai",
            timestamp="2025-03-01T09:00:00Z",
        )
    )

    before_current = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))
    before_historical = sdk.get_historical_state(
        HistoricalStateRequest(subject="user", predicate="location", as_of="2025-03-15T00:00:00Z")
    )
    maintenance = sdk.reconsolidate_manual_memory()
    after_current = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))
    after_historical = sdk.get_historical_state(
        HistoricalStateRequest(subject="user", predicate="location", as_of="2025-03-15T00:00:00Z")
    )

    return {
        "maintenance": asdict(maintenance),
        "before": {
            "current_state": asdict(before_current),
            "historical_state": asdict(before_historical),
        },
        "after": {
            "current_state": asdict(after_current),
            "historical_state": asdict(after_historical),
        },
    }


def _build_demo_spark_kb_payload(output_dir: str, repo_sources: list[str] | None = None) -> dict:
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="user",
            predicate="location",
            value="Dubai",
            timestamp="2025-03-01T09:00:00Z",
            session_id="spark-kb-demo",
            turn_id="spark-kb-demo:1",
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="user",
            predicate="favorite_coffee",
            value="flat white",
            timestamp="2025-03-02T09:00:00Z",
            session_id="spark-kb-demo",
            turn_id="spark-kb-demo:2",
        )
    )
    sdk.write_event(
        MemoryWriteRequest(
            text="",
            operation="event",
            subject="user",
            predicate="move",
            value="Dubai",
            timestamp="2025-03-01T09:00:00Z",
            session_id="spark-kb-demo",
            turn_id="spark-kb-demo:3",
        )
    )
    explanation = sdk.explain_answer(
        AnswerExplanationRequest(
            question="Where does the user live right now?",
            subject="user",
            predicate="location",
        )
    )
    snapshot = sdk.export_knowledge_base_snapshot()
    compile_result = scaffold_spark_knowledge_base(
        output_dir,
        snapshot,
        vault_title="Spark Demo Knowledge Base",
        repo_sources=repo_sources,
        filed_outputs=[
            {
                "title": "User Location Answer",
                "slug": "user-location-answer",
                "question": explanation.trace.get("question"),
                "answer": explanation.answer,
                "explanation": explanation.explanation,
                "memory_role": explanation.memory_role,
                "provenance": [
                    f"`{record.session_id}` turns `{', '.join(record.turn_ids)}`"
                    for record in explanation.provenance
                ],
            }
        ],
    )
    return {
        "contract": build_spark_kb_contract_summary(),
        "snapshot": snapshot,
        "compile_result": compile_result,
    }


def _run_sdk_maintenance_checks(sdk: SparkMemorySDK, checks: dict | None) -> dict:
    payload = dict(checks or {})
    current_requests = payload.get("current_state", [])
    historical_requests = payload.get("historical_state", [])
    return {
        "current_state": [
            {
                "request": dict(item),
                "result": asdict(
                    sdk.get_current_state(
                        CurrentStateRequest(
                            subject=str(item.get("subject", "")),
                            predicate=str(item.get("predicate", "")),
                        )
                    )
                ),
            }
            for item in current_requests
            if isinstance(item, dict)
        ],
        "historical_state": [
            {
                "request": dict(item),
                "result": asdict(
                    sdk.get_historical_state(
                        HistoricalStateRequest(
                            subject=str(item.get("subject", "")),
                            predicate=str(item.get("predicate", "")),
                            as_of=str(item.get("as_of", "")),
                        )
                    )
                ),
            }
            for item in historical_requests
            if isinstance(item, dict)
        ],
    }


def _load_sdk_maintenance_payload(data_file: str) -> dict:
    payload = json.loads(Path(data_file).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("SDK maintenance replay file must contain a JSON object.")
    raw_writes = payload.get("writes", [])
    if not isinstance(raw_writes, list):
        raise ValueError("SDK maintenance replay file must contain a writes list.")

    sdk = SparkMemorySDK()
    write_results = []
    for index, item in enumerate(raw_writes):
        if not isinstance(item, dict):
            raise ValueError(f"Write at index {index} must be an object.")
        write_kind = str(item.get("write_kind", "observation")).strip().lower() or "observation"
        request = MemoryWriteRequest(
            text=str(item.get("text", "")),
            speaker=str(item.get("speaker", "user")),
            timestamp=str(item.get("timestamp")) if item.get("timestamp") is not None else None,
            session_id=str(item.get("session_id")) if item.get("session_id") is not None else None,
            turn_id=str(item.get("turn_id")) if item.get("turn_id") is not None else None,
            operation=str(item.get("operation", "auto")),
            subject=str(item.get("subject")) if item.get("subject") is not None else None,
            predicate=str(item.get("predicate")) if item.get("predicate") is not None else None,
            value=str(item.get("value")) if item.get("value") is not None else None,
            metadata=dict(item.get("metadata", {})),
        )
        if write_kind == "event":
            write_result = sdk.write_event(request)
        else:
            write_result = sdk.write_observation(request)
        write_results.append(
            {
                "write_kind": write_kind,
                "request": dict(item),
                "result": asdict(write_result),
            }
        )

    checks = payload.get("checks")
    before = _run_sdk_maintenance_checks(sdk, checks if isinstance(checks, dict) else None)
    maintenance = sdk.reconsolidate_manual_memory()
    after = _run_sdk_maintenance_checks(sdk, checks if isinstance(checks, dict) else None)
    return {
        "write_results": write_results,
        "maintenance": asdict(maintenance),
        "before": before,
        "after": after,
    }


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
    subparsers.add_parser("demo-product-memory-scorecards", help="Run local product-memory scorecards for correction, deletion, and stale-state drift.")
    demo_spark_shadow = subparsers.add_parser("demo-spark-shadow-report", help="Run a local Spark shadow ingest/report demo.")
    demo_spark_shadow.add_argument("--write")
    demo_sdk_maintenance = subparsers.add_parser("demo-sdk-maintenance", help="Run a local SDK maintenance and reconsolidation demo.")
    demo_sdk_maintenance.add_argument("--write")
    demo_spark_kb = subparsers.add_parser("demo-spark-kb", help="Export a demo Spark KB snapshot and scaffold an Obsidian-friendly vault.")
    demo_spark_kb.add_argument("output_dir")
    demo_spark_kb.add_argument("--repo-source", action="append", default=[])
    demo_spark_kb.add_argument("--write")
    spark_kb_health = subparsers.add_parser("spark-kb-health-check", help="Run health checks over a scaffolded Spark KB vault.")
    spark_kb_health.add_argument("output_dir")
    spark_kb_health.add_argument("--write")
    run_sdk_maintenance = subparsers.add_parser("run-sdk-maintenance-report", help="Replay explicit SDK writes from JSON and emit a maintenance report.")
    run_sdk_maintenance.add_argument("data_file")
    run_sdk_maintenance.add_argument("--write")
    subparsers.add_parser("sdk-maintenance-contracts", help="Show the SDK runtime and maintenance replay contract summary.")
    run_spark_shadow = subparsers.add_parser("run-spark-shadow-report", help="Replay Builder-style shadow traffic from JSON and emit a shadow report.")
    run_spark_shadow.add_argument("data_file")
    run_spark_shadow.add_argument("--write")
    validate_spark_shadow = subparsers.add_parser("validate-spark-shadow-replay", help="Validate a Builder-style shadow replay JSON file without running replay.")
    validate_spark_shadow.add_argument("data_file")
    validate_spark_shadow.add_argument("--write")
    validate_spark_shadow_batch = subparsers.add_parser("validate-spark-shadow-replay-batch", help="Validate a directory of Builder-style shadow replay JSON files without running replay.")
    validate_spark_shadow_batch.add_argument("data_dir")
    validate_spark_shadow_batch.add_argument("--glob", default="*.json")
    validate_spark_shadow_batch.add_argument("--write")
    run_spark_shadow_batch = subparsers.add_parser("run-spark-shadow-report-batch", help="Replay a directory of Builder-style shadow JSON files and emit one aggregate report.")
    run_spark_shadow_batch.add_argument("data_dir")
    run_spark_shadow_batch.add_argument("--glob", default="*.json")
    run_spark_shadow_batch.add_argument("--write")
    subparsers.add_parser("spark-shadow-contracts", help="Show the Spark shadow replay and ingest contract summary.")
    subparsers.add_parser("spark-integration-contracts", help="Show the Spark integration outlook and orchestration contract summary.")
    subparsers.add_parser("spark-kb-contracts", help="Show the Spark knowledge-base layer contract summary.")
    subparsers.add_parser("loader-contracts", help="Show benchmark file loader summary.")
    subparsers.add_parser("provider-contracts", help="Show model-provider interface summary.")
    subparsers.add_parser("runner-contracts", help="Show executable baseline runner summary.")
    subparsers.add_parser("memory-system-contracts", help="Show candidate memory-system contract summary.")
    subparsers.add_parser("experiment-contracts", help="Show compact benchmark comparison contract summary.")

    run_longmemeval = subparsers.add_parser("run-longmemeval-baseline", help="Run a baseline over a LongMemEval JSON file.")
    run_longmemeval.add_argument("data_file")
    run_longmemeval.add_argument("--baseline", choices=("full_context", "lexical", "beam_temporal_atom_router", "observational_temporal_memory", "contradiction_aware_profile_memory", "contradiction_aware_summary_synthesis_memory", "dual_store_event_calendar_hybrid", "stateful_event_reconstruction", "summary_synthesis_memory", "typed_state_update_memory"), default="full_context")
    run_longmemeval.add_argument("--provider", default="heuristic_v1")
    run_longmemeval.add_argument("--limit", type=int)
    run_longmemeval.add_argument("--top-k-sessions", type=int, default=2)
    run_longmemeval.add_argument("--fallback-sessions", type=int, default=1)
    run_longmemeval.add_argument("--write")
    run_longmemeval.add_argument("--resume-from")

    run_locomo = subparsers.add_parser("run-locomo-baseline", help="Run a baseline over a LoCoMo JSON file.")
    run_locomo.add_argument("data_file")
    run_locomo.add_argument("--baseline", choices=("full_context", "lexical", "beam_temporal_atom_router", "observational_temporal_memory", "contradiction_aware_profile_memory", "contradiction_aware_summary_synthesis_memory", "dual_store_event_calendar_hybrid", "stateful_event_reconstruction", "summary_synthesis_memory", "typed_state_update_memory"), default="full_context")
    run_locomo.add_argument("--provider", default="heuristic_v1")
    run_locomo.add_argument("--limit", type=int)
    run_locomo.add_argument("--question-offset", type=int, default=0)
    run_locomo.add_argument("--question-limit", type=int)
    run_locomo.add_argument("--top-k-sessions", type=int, default=2)
    run_locomo.add_argument("--fallback-sessions", type=int, default=1)
    run_locomo.add_argument("--write")
    run_locomo.add_argument("--resume-from")

    run_goodai = subparsers.add_parser("run-goodai-baseline", help="Run a baseline over GoodAI config and definitions.")
    run_goodai.add_argument("config_file")
    run_goodai.add_argument("definitions_dir")
    run_goodai.add_argument("--dataset-name")
    run_goodai.add_argument("--baseline", choices=("full_context", "lexical", "beam_temporal_atom_router", "observational_temporal_memory", "contradiction_aware_profile_memory", "contradiction_aware_summary_synthesis_memory", "dual_store_event_calendar_hybrid", "stateful_event_reconstruction", "summary_synthesis_memory", "typed_state_update_memory"), default="full_context")
    run_goodai.add_argument("--provider", default="heuristic_v1")
    run_goodai.add_argument("--limit", type=int)
    run_goodai.add_argument("--top-k-sessions", type=int, default=2)
    run_goodai.add_argument("--fallback-sessions", type=int, default=1)
    run_goodai.add_argument("--write")
    run_goodai.add_argument("--resume-from")

    run_beam = subparsers.add_parser("run-beam-baseline", help="Run a baseline over a local BEAM slice JSON file.")
    run_beam.add_argument("data_file")
    run_beam.add_argument("--baseline", choices=("full_context", "lexical", "beam_temporal_atom_router", "observational_temporal_memory", "contradiction_aware_profile_memory", "contradiction_aware_summary_synthesis_memory", "dual_store_event_calendar_hybrid", "stateful_event_reconstruction", "summary_synthesis_memory", "typed_state_update_memory"), default="full_context")
    run_beam.add_argument("--provider", default="heuristic_v1")
    run_beam.add_argument("--limit", type=int)
    run_beam.add_argument("--top-k-sessions", type=int, default=2)
    run_beam.add_argument("--fallback-sessions", type=int, default=1)
    run_beam.add_argument("--write")
    run_beam.add_argument("--resume-from")

    run_beam_public = subparsers.add_parser("run-beam-public-baseline", help="Run a baseline over an unpacked official-public BEAM chats directory.")
    run_beam_public.add_argument("data_dir")
    run_beam_public.add_argument("--chat-size", required=True)
    run_beam_public.add_argument("--baseline", choices=("full_context", "lexical", "beam_temporal_atom_router", "observational_temporal_memory", "contradiction_aware_profile_memory", "contradiction_aware_summary_synthesis_memory", "dual_store_event_calendar_hybrid", "stateful_event_reconstruction", "summary_synthesis_memory", "typed_state_update_memory"), default="full_context")
    run_beam_public.add_argument("--provider", default="heuristic_v1")
    run_beam_public.add_argument("--limit", type=int)
    run_beam_public.add_argument("--top-k-sessions", type=int, default=2)
    run_beam_public.add_argument("--fallback-sessions", type=int, default=1)
    run_beam_public.add_argument("--upstream-commit")
    run_beam_public.add_argument("--write")
    run_beam_public.add_argument("--resume-from")

    export_beam_public = subparsers.add_parser("export-beam-public-answers", help="Export an official-public BEAM scorecard into upstream-style per-conversation answer files.")
    export_beam_public.add_argument("scorecard_file")
    export_beam_public.add_argument("output_dir")
    export_beam_public.add_argument("--result-file-name", default="domain_chip_memory_answers.json")
    export_beam_public.add_argument("--write")

    summarize_beam_eval = subparsers.add_parser("summarize-beam-evaluation", help="Summarize an upstream BEAM evaluation JSON file into a compact in-repo view.")
    summarize_beam_eval.add_argument("evaluation_file")
    summarize_beam_eval.add_argument("--write")

    run_beam_official_eval = subparsers.add_parser("run-beam-official-evaluation", help="Run the pinned upstream BEAM evaluation script over exported official-public answer files.")
    run_beam_official_eval.add_argument("upstream_repo_dir")
    run_beam_official_eval.add_argument("answers_dir")
    run_beam_official_eval.add_argument("--chat-size", required=True)
    run_beam_official_eval.add_argument("--result-file-name", default="domain_chip_memory_answers.json")
    run_beam_official_eval.add_argument("--start-index", type=int, default=0)
    run_beam_official_eval.add_argument("--end-index", type=int)
    run_beam_official_eval.add_argument("--max-workers", type=int, default=10)
    run_beam_official_eval.add_argument("--python-executable")
    run_beam_official_eval.add_argument("--judge-provider", choices=("official_openai", "minimax"), default="minimax")
    run_beam_official_eval.add_argument("--judge-model")
    run_beam_official_eval.add_argument("--judge-base-url")
    run_beam_official_eval.add_argument("--judge-api-key-env")
    run_beam_official_eval.add_argument("--dry-run", action="store_true")
    run_beam_official_eval.add_argument("--write")

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
    compare_locomo.add_argument("--question-offset", type=int, default=0)
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
                "contradiction_aware_profile_memory": run_baseline(
                    samples,
                    baseline_name="contradiction_aware_profile_memory",
                    provider=get_provider("heuristic_v1"),
                    top_k_sessions=2,
                    fallback_sessions=1,
                ),
                "contradiction_aware_summary_synthesis_memory": run_baseline(
                    samples,
                    baseline_name="contradiction_aware_summary_synthesis_memory",
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
                "stateful_event_reconstruction": run_baseline(
                    samples,
                    baseline_name="stateful_event_reconstruction",
                    provider=get_provider("heuristic_v1"),
                    top_k_sessions=2,
                    fallback_sessions=1,
                ),
                "summary_synthesis_memory": run_baseline(
                    samples,
                    baseline_name="summary_synthesis_memory",
                    provider=get_provider("heuristic_v1"),
                    top_k_sessions=2,
                    fallback_sessions=1,
                ),
                "typed_state_update_memory": run_baseline(
                    samples,
                    baseline_name="typed_state_update_memory",
                    provider=get_provider("heuristic_v1"),
                    top_k_sessions=2,
                    fallback_sessions=1,
                ),
            }
        )
        return

    if args.command == "demo-product-memory-scorecards":
        samples = product_memory_samples()
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
                "observational_temporal_memory": run_baseline(
                    samples,
                    baseline_name="observational_temporal_memory",
                    provider=get_provider("heuristic_v1"),
                    top_k_sessions=2,
                    fallback_sessions=1,
                ),
                "contradiction_aware_profile_memory": run_baseline(
                    samples,
                    baseline_name="contradiction_aware_profile_memory",
                    provider=get_provider("heuristic_v1"),
                    top_k_sessions=2,
                    fallback_sessions=1,
                ),
                "contradiction_aware_summary_synthesis_memory": run_baseline(
                    samples,
                    baseline_name="contradiction_aware_summary_synthesis_memory",
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
                "stateful_event_reconstruction": run_baseline(
                    samples,
                    baseline_name="stateful_event_reconstruction",
                    provider=get_provider("heuristic_v1"),
                    top_k_sessions=2,
                    fallback_sessions=1,
                ),
                "summary_synthesis_memory": run_baseline(
                    samples,
                    baseline_name="summary_synthesis_memory",
                    provider=get_provider("heuristic_v1"),
                    top_k_sessions=2,
                    fallback_sessions=1,
                ),
                "typed_state_update_memory": run_baseline(
                    samples,
                    baseline_name="typed_state_update_memory",
                    provider=get_provider("heuristic_v1"),
                    top_k_sessions=2,
                    fallback_sessions=1,
                ),
            }
        )
        return

    if args.command == "demo-spark-shadow-report":
        payload = _build_demo_shadow_report_payload()
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "demo-sdk-maintenance":
        payload = _build_demo_sdk_maintenance_payload()
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "demo-spark-kb":
        payload = _build_demo_spark_kb_payload(args.output_dir, repo_sources=args.repo_source)
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "spark-kb-health-check":
        payload = build_spark_kb_health_report(args.output_dir)
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "run-sdk-maintenance-report":
        payload = _load_sdk_maintenance_payload(args.data_file)
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "sdk-maintenance-contracts":
        _print(
            {
                "sdk": build_sdk_contract_summary(),
                "replay": build_sdk_maintenance_replay_contract_summary(),
            }
        )
        return

    if args.command == "run-spark-shadow-report":
        payload = _load_shadow_report_payload(args.data_file)
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "validate-spark-shadow-replay":
        payload = _validate_shadow_replay_payload(args.data_file)
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "validate-spark-shadow-replay-batch":
        payload = _validate_shadow_replay_batch_payload(args.data_dir, glob_pattern=args.glob)
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "run-spark-shadow-report-batch":
        payload = _load_shadow_report_batch_payload(args.data_dir, glob_pattern=args.glob)
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "spark-shadow-contracts":
        _print(
            {
                "ingest": build_shadow_ingest_contract_summary(),
                "replay": build_shadow_replay_contract_summary(),
            }
        )
        return

    if args.command == "spark-integration-contracts":
        _print(build_spark_integration_contract_summary())
        return

    if args.command == "spark-kb-contracts":
        _print(build_spark_kb_contract_summary())
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
        write_path = Path(args.write) if args.write else None
        payload = _run_with_progress(
            samples,
            baseline_name=args.baseline,
            provider_name=args.provider,
            top_k_sessions=args.top_k_sessions,
            fallback_sessions=args.fallback_sessions,
            write_path=write_path,
            resume_path=Path(args.resume_from) if args.resume_from else None,
        )
        if args.write:
            _write_json(write_path, payload)
        _print(payload)
        return

    if args.command == "run-locomo-baseline":
        samples = _limit_questions(
            load_locomo_json(args.data_file, limit=args.limit),
            question_offset=args.question_offset,
            question_limit=args.question_limit,
        )
        write_path = Path(args.write) if args.write else None
        payload = _run_with_progress(
            samples,
            baseline_name=args.baseline,
            provider_name=args.provider,
            top_k_sessions=args.top_k_sessions,
            fallback_sessions=args.fallback_sessions,
            write_path=write_path,
            resume_path=Path(args.resume_from) if args.resume_from else None,
        )
        if args.write:
            _write_json(write_path, payload)
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
        write_path = Path(args.write) if args.write else None
        payload = _run_with_progress(
            samples,
            baseline_name=args.baseline,
            provider_name=args.provider,
            top_k_sessions=args.top_k_sessions,
            fallback_sessions=args.fallback_sessions,
            write_path=write_path,
            resume_path=Path(args.resume_from) if args.resume_from else None,
        )
        if args.write:
            _write_json(write_path, payload)
        _print(payload)
        return

    if args.command == "run-beam-baseline":
        samples = load_beam_json(args.data_file, limit=args.limit)
        write_path = Path(args.write) if args.write else None
        payload = _run_with_progress(
            samples,
            baseline_name=args.baseline,
            provider_name=args.provider,
            top_k_sessions=args.top_k_sessions,
            fallback_sessions=args.fallback_sessions,
            write_path=write_path,
            resume_path=Path(args.resume_from) if args.resume_from else None,
        )
        if args.write:
            _write_json(write_path, payload)
        _print(payload)
        return

    if args.command == "run-beam-public-baseline":
        samples = load_beam_public_dir(
            args.data_dir,
            chat_size=args.chat_size,
            limit=args.limit,
            upstream_commit=args.upstream_commit,
        )
        write_path = Path(args.write) if args.write else None
        payload = _run_with_progress(
            samples,
            baseline_name=args.baseline,
            provider_name=args.provider,
            top_k_sessions=args.top_k_sessions,
            fallback_sessions=args.fallback_sessions,
            write_path=write_path,
            resume_path=Path(args.resume_from) if args.resume_from else None,
        )
        if args.write:
            _write_json(write_path, payload)
        _print(payload)
        return

    if args.command == "export-beam-public-answers":
        payload = export_beam_public_answers_from_scorecard(
            args.scorecard_file,
            args.output_dir,
            result_file_name=args.result_file_name,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "summarize-beam-evaluation":
        payload = summarize_beam_official_evaluation(args.evaluation_file)
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "run-beam-official-evaluation":
        payload = run_beam_official_evaluation(
            args.upstream_repo_dir,
            args.answers_dir,
            chat_size=args.chat_size,
            result_file_name=args.result_file_name,
            start_index=args.start_index,
            end_index=args.end_index,
            max_workers=args.max_workers,
            python_executable=args.python_executable,
            judge_provider=args.judge_provider,
            judge_model=args.judge_model,
            judge_base_url=args.judge_base_url,
            judge_api_key_env=args.judge_api_key_env,
            dry_run=args.dry_run,
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
            question_offset=args.question_offset,
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
