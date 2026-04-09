from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
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
    _summarize_beam_evaluation_payload,
    export_beam_public_answers_from_scorecard,
    run_beam_official_evaluation,
    summarize_beam_official_evaluation,
    summarize_beam_official_evaluation_files,
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


def _load_string_list_manifest(manifest_file: str, *, key: str, label: str) -> list[str]:
    manifest_path = Path(manifest_file)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_items = payload.get(key) if isinstance(payload, dict) else payload
    if not isinstance(manifest_items, list) or not all(isinstance(item, str) for item in manifest_items):
        raise ValueError(f"{label} must contain a JSON list of strings or an object with a '{key}' list.")
    resolved_items: list[str] = []
    for item in manifest_items:
        item_path = Path(item)
        if not item_path.is_absolute():
            item_path = manifest_path.parent / item_path
        resolved_items.append(str(item_path))
    return resolved_items


def _load_json_file(path: str | Path) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_beam_category_counts(path: str | Path) -> dict[str, int]:
    payload = _load_json_file(path)
    if not isinstance(payload, dict):
        return {}
    return {str(key): len(items) for key, items in payload.items() if isinstance(items, list)}


def _load_beam_evaluation_categories(path: str | Path) -> list[str]:
    return sorted(key for key, count in _load_beam_category_counts(path).items() if count > 0)


def _load_beam_category_keys(path: str | Path) -> list[str]:
    return sorted(_load_beam_category_counts(path))


def _load_beam_category_order(path: str | Path) -> list[str]:
    payload = _load_json_file(path)
    if not isinstance(payload, dict):
        return []
    return [str(key) for key, items in payload.items() if isinstance(items, list)]


def _load_beam_expected_category_order_and_counts_for_manifest(payload: dict[str, object]) -> tuple[list[str], dict[str, int]]:
    upstream_repo_dir = str(payload.get("upstream_repo_dir") or "").strip()
    official_chat_size_dir = str(payload.get("official_chat_size_dir") or "").strip()
    conversation_ids = [str(item).strip() for item in payload.get("conversation_ids", []) if str(item).strip()]
    if not upstream_repo_dir or not official_chat_size_dir or not conversation_ids:
        return [], {}

    ordered_categories: list[str] = []
    category_counts: dict[str, int] = {}
    upstream_repo_path = Path(upstream_repo_dir)
    for conversation_id in conversation_ids:
        probing_questions_path = (
            upstream_repo_path / "chats" / official_chat_size_dir / conversation_id / "probing_questions" / "probing_questions.json"
        )
        if not probing_questions_path.is_file():
            continue
        payload_counts = _load_beam_category_counts(probing_questions_path)
        payload_order = _load_beam_category_order(probing_questions_path)
        for category in payload_order:
            if category not in category_counts:
                ordered_categories.append(category)
                category_counts[category] = int(payload_counts.get(category, 0))
    return ordered_categories, category_counts


def _load_beam_expected_categories_for_manifest(payload: dict[str, object]) -> list[str]:
    ordered_categories, _ = _load_beam_expected_category_order_and_counts_for_manifest(payload)
    return sorted(ordered_categories)


def _load_beam_answer_category_order_and_counts_for_manifest(payload: dict[str, object]) -> tuple[list[str], dict[str, int]]:
    input_directory = str(payload.get("input_directory") or "").strip()
    result_file_name = str(payload.get("result_file_name") or "").strip()
    conversation_ids = [str(item).strip() for item in payload.get("conversation_ids", []) if str(item).strip()]
    if not input_directory or not result_file_name or not conversation_ids:
        return [], {}

    ordered_categories: list[str] = []
    category_counts: dict[str, int] = {}
    input_directory_path = Path(input_directory)
    for conversation_id in conversation_ids:
        answer_path = input_directory_path / conversation_id / result_file_name
        if not answer_path.is_file():
            continue
        payload_counts = _load_beam_category_counts(answer_path)
        payload_order = _load_beam_category_order(answer_path)
        for category in payload_order:
            if category not in category_counts:
                ordered_categories.append(category)
                category_counts[category] = int(payload_counts.get(category, 0))
    return ordered_categories, category_counts


def _load_beam_answer_categories_for_manifest(payload: dict[str, object]) -> list[str]:
    ordered_categories, _ = _load_beam_answer_category_order_and_counts_for_manifest(payload)
    return sorted(ordered_categories)


def _parse_manifest_stdout_progress(stdout_tail: list[str]) -> tuple[str, int | None]:
    last_category = ""
    last_index: int | None = None
    for line in stdout_tail:
        if line.startswith("Question Type: "):
            last_category = line.removeprefix("Question Type: ").strip()
        elif line.startswith("Question Index: "):
            try:
                last_index = int(line.removeprefix("Question Index: ").strip())
            except ValueError:
                continue
    return last_category, last_index


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def _shell_quote_arg(arg: str) -> str:
    escaped = str(arg).replace('"', '`"')
    if any(char.isspace() for char in escaped) or not escaped:
        return f'"{escaped}"'
    return escaped


def _required_beam_judge_env(*, judge_provider: str, judge_api_key_env: str) -> str:
    normalized_provider = str(judge_provider or "").strip().lower()
    explicit_env = str(judge_api_key_env or "").strip()
    if explicit_env:
        return explicit_env
    if normalized_provider == "minimax":
        return "MINIMAX_API_KEY"
    return ""


def _git_status_by_path(paths: list[Path], *, repo_root: Path) -> dict[str, str]:
    if not paths:
        return {}
    try:
        relative_paths = [str(path.relative_to(repo_root)).replace("\\", "/") for path in paths]
    except ValueError:
        return {}
    status_by_path: dict[str, str] = {}
    batch_size = 100
    try:
        for start in range(0, len(relative_paths), batch_size):
            batch = relative_paths[start : start + batch_size]
            result = subprocess.run(
                ["git", "-C", str(repo_root), "status", "--short", "--", *batch],
                check=True,
                capture_output=True,
                text=True,
            )
            for line in result.stdout.splitlines():
                if len(line) < 4:
                    continue
                status = line[:2].strip() or "unknown"
                path = line[3:].strip().replace("\\", "/")
                status_by_path[path] = status
    except Exception:
        return {}
    return status_by_path


def _load_json_from_git_revision(*, repo_root: Path, revision: str, path: Path) -> dict | None:
    try:
        relative_path = str(path.relative_to(repo_root)).replace("\\", "/")
    except ValueError:
        return None
    result = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"{revision}:{relative_path}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _category_summary_by_name(summary: dict) -> dict[str, dict]:
    categories = summary.get("categories", [])
    if not isinstance(categories, list):
        return {}
    rows: dict[str, dict] = {}
    for row in categories:
        if not isinstance(row, dict):
            continue
        category = str(row.get("category") or "").strip()
        if category:
            rows[category] = row
    return rows


def _beam_question_metric_name(category: str, item: dict | None) -> str:
    if not isinstance(item, dict):
        return ""
    if category == "event_ordering" and "tau_norm" in item:
        return "tau_norm"
    if "llm_judge_score" in item:
        return "llm_judge_score"
    return ""


def _beam_question_metric_value(category: str, item: dict | None) -> tuple[str, float | None]:
    metric_name = _beam_question_metric_name(category, item)
    if not metric_name or not isinstance(item, dict):
        return metric_name, None
    raw_value = item.get(metric_name)
    if raw_value is None:
        return metric_name, None
    try:
        return metric_name, float(raw_value)
    except (TypeError, ValueError):
        return metric_name, None


def _build_beam_changed_question_rows(*, category: str, current_payload: dict, head_payload: dict) -> list[dict]:
    current_items = current_payload.get(category, [])
    head_items = head_payload.get(category, [])
    current_list = current_items if isinstance(current_items, list) else []
    head_list = head_items if isinstance(head_items, list) else []
    changed_rows = []
    for question_index in range(max(len(current_list), len(head_list))):
        current_item = current_list[question_index] if question_index < len(current_list) and isinstance(current_list[question_index], dict) else None
        head_item = head_list[question_index] if question_index < len(head_list) and isinstance(head_list[question_index], dict) else None
        current_metric, current_score = _beam_question_metric_value(category, current_item)
        head_metric, head_score = _beam_question_metric_value(category, head_item)
        current_question = str((current_item or {}).get("question") or "")
        head_question = str((head_item or {}).get("question") or "")
        if (
            current_score != head_score
            or current_metric != head_metric
            or current_question != head_question
        ):
            changed_rows.append(
                {
                    "question_index": question_index,
                    "head_metric": head_metric,
                    "current_metric": current_metric,
                    "head_score": round(head_score, 4) if head_score is not None else None,
                    "current_score": round(current_score, 4) if current_score is not None else None,
                    "score_delta": (
                        round(current_score - head_score, 4)
                        if current_score is not None and head_score is not None
                        else None
                    ),
                    "head_question": head_question,
                    "current_question": current_question,
                }
            )
    return changed_rows


def _build_beam_modified_evaluation_drift_row(*, path: Path, repo_root: Path, git_status: str) -> dict | None:
    current_payload = _load_json_file(path)
    if not isinstance(current_payload, dict):
        return None
    head_payload = _load_json_from_git_revision(repo_root=repo_root, revision="HEAD", path=path)
    current_summary = _summarize_beam_evaluation_payload(current_payload)
    head_summary = _summarize_beam_evaluation_payload(head_payload) if isinstance(head_payload, dict) else None
    current_by_category = _category_summary_by_name(current_summary)
    head_by_category = _category_summary_by_name(head_summary or {})
    all_categories = sorted(set(current_by_category) | set(head_by_category))
    changed_categories = []
    for category in all_categories:
        current_row = current_by_category.get(category)
        head_row = head_by_category.get(category)
        current_average = current_row.get("average_score") if current_row else None
        head_average = head_row.get("average_score") if head_row else None
        current_count = current_row.get("question_count") if current_row else None
        head_count = head_row.get("question_count") if head_row else None
        current_metric = current_row.get("metric") if current_row else ""
        head_metric = head_row.get("metric") if head_row else ""
        if (
            current_average != head_average
            or current_count != head_count
            or current_metric != head_metric
        ):
            changed_questions = _build_beam_changed_question_rows(
                category=category,
                current_payload=current_payload,
                head_payload=head_payload or {},
            )
            changed_categories.append(
                {
                    "category": category,
                    "head_average_score": head_average,
                    "current_average_score": current_average,
                    "average_score_delta": (
                        round(float(current_average) - float(head_average), 4)
                        if current_average is not None and head_average is not None
                        else None
                    ),
                    "head_question_count": head_count,
                    "current_question_count": current_count,
                    "head_metric": head_metric,
                    "current_metric": current_metric,
                    "changed_question_count": len(changed_questions),
                    "changed_questions": changed_questions,
                }
            )
    return {
        "path": _display_path(path, repo_root),
        "git_status": git_status,
        "head_present": isinstance(head_payload, dict),
        "current_overall_average": current_summary.get("overall_average"),
        "head_overall_average": head_summary.get("overall_average") if head_summary else None,
        "overall_average_delta": (
            round(float(current_summary.get("overall_average", 0.0)) - float(head_summary.get("overall_average", 0.0)), 4)
            if head_summary
            else None
        ),
        "current_category_count": current_summary.get("category_count"),
        "head_category_count": head_summary.get("category_count") if head_summary else None,
        "current_categories": sorted(current_by_category),
        "head_categories": sorted(head_by_category),
        "missing_from_current": sorted(set(head_by_category) - set(current_by_category)),
        "added_in_current": sorted(set(current_by_category) - set(head_by_category)),
        "changed_category_count": len(changed_categories),
        "changed_categories": changed_categories,
    }


def _classify_beam_cleanup_manifest(
    *,
    status: str,
    missing_evaluation_files: list[str],
    completed_categories: set[str],
    expected_categories: set[str],
    stderr_tail: list[str],
) -> str:
    missing_categories = expected_categories - completed_categories if expected_categories else set()
    timeout_detected = any("Timed out waiting" in line for line in stderr_tail)
    if status == "completed":
        return "completed"
    if missing_evaluation_files:
        return "missing_evaluation_files"
    if status == "partial":
        if timeout_detected and completed_categories and not missing_categories:
            return "timeout_after_complete_write"
        if timeout_detected and missing_categories:
            return "timeout_partial_coverage"
        if stderr_tail and missing_categories:
            return "worker_error_partial_coverage"
        if stderr_tail:
            return "worker_error"
        if missing_categories:
            return "partial_missing_categories"
        if completed_categories:
            return "partial_full_coverage"
    return "unknown"


def _resolve_repo_source_files(
    *,
    repo_sources: list[str] | None = None,
    repo_source_manifest_files: list[str] | None = None,
) -> list[str]:
    resolved_repo_sources = list(repo_sources or [])
    for repo_source_manifest_file in repo_source_manifest_files or []:
        resolved_repo_sources.extend(
            _load_string_list_manifest(
                repo_source_manifest_file,
                key="repo_sources",
                label="Repo source manifest file",
            )
        )
    return resolved_repo_sources


def _resolve_filed_output_files(
    *,
    filed_output_files: list[str] | None = None,
    filed_output_manifest_files: list[str] | None = None,
) -> list[str]:
    resolved_filed_output_files = list(filed_output_files or [])
    for filed_output_manifest_file in filed_output_manifest_files or []:
        resolved_filed_output_files.extend(
            _load_string_list_manifest(
                filed_output_manifest_file,
                key="filed_output_files",
                label="Filed output manifest file",
            )
        )
    return resolved_filed_output_files


def _load_filed_output_records(filed_output_files: list[str]) -> list[dict]:
    filed_outputs: list[dict] = []
    for filed_output_file in filed_output_files:
        payload = _load_json_file(filed_output_file)
        if isinstance(payload, dict):
            filed_outputs.append(payload)
            continue
        if isinstance(payload, list):
            filed_outputs.extend(item for item in payload if isinstance(item, dict))
            continue
        raise ValueError("Filed output file must contain a JSON object or list of objects.")
    return filed_outputs


def _validate_spark_kb_inputs(
    snapshot_file: str,
    *,
    repo_sources: list[str] | None = None,
    repo_source_manifest_files: list[str] | None = None,
    filed_output_files: list[str] | None = None,
    filed_output_manifest_files: list[str] | None = None,
) -> dict:
    snapshot_path = Path(snapshot_file)
    snapshot_errors: list[str] = []
    snapshot_valid = False
    snapshot_payload: dict | None = None
    try:
        payload = _load_json_file(snapshot_path)
        if not isinstance(payload, dict):
            raise ValueError("Spark KB snapshot file must contain a JSON object.")
        snapshot_payload = payload
        snapshot_valid = True
    except Exception as exc:
        snapshot_errors.append(str(exc))

    resolved_repo_sources: list[str] = []
    repo_source_manifest_errors: list[dict[str, str]] = []
    for repo_source_manifest_file in repo_source_manifest_files or []:
        try:
            resolved_repo_sources.extend(
                _load_string_list_manifest(
                    repo_source_manifest_file,
                    key="repo_sources",
                    label="Repo source manifest file",
                )
            )
        except Exception as exc:
            repo_source_manifest_errors.append({"file": str(repo_source_manifest_file), "error": str(exc)})
    resolved_repo_sources = [*(repo_sources or []), *resolved_repo_sources]
    missing_repo_source_files = [
        path
        for path in resolved_repo_sources
        if not Path(path).exists() or not Path(path).is_file()
    ]

    resolved_filed_output_files: list[str] = list(filed_output_files or [])
    filed_output_manifest_errors: list[dict[str, str]] = []
    for filed_output_manifest_file in filed_output_manifest_files or []:
        try:
            resolved_filed_output_files.extend(
                _load_string_list_manifest(
                    filed_output_manifest_file,
                    key="filed_output_files",
                    label="Filed output manifest file",
                )
            )
        except Exception as exc:
            filed_output_manifest_errors.append({"file": str(filed_output_manifest_file), "error": str(exc)})

    missing_filed_output_files = [
        path
        for path in resolved_filed_output_files
        if not Path(path).exists() or not Path(path).is_file()
    ]
    filed_output_file_errors: list[dict[str, str]] = []
    filed_output_record_count = 0
    for filed_output_file in resolved_filed_output_files:
        filed_output_path = Path(filed_output_file)
        if not filed_output_path.exists() or not filed_output_path.is_file():
            continue
        try:
            payload = _load_json_file(filed_output_path)
            if isinstance(payload, dict):
                filed_output_record_count += 1
                continue
            if isinstance(payload, list):
                filed_output_record_count += sum(1 for item in payload if isinstance(item, dict))
                continue
            raise ValueError("Filed output file must contain a JSON object or list of objects.")
        except Exception as exc:
            filed_output_file_errors.append({"file": str(filed_output_file), "error": str(exc)})

    valid = (
        snapshot_valid
        and not repo_source_manifest_errors
        and not missing_repo_source_files
        and not filed_output_manifest_errors
        and not missing_filed_output_files
        and not filed_output_file_errors
    )
    return {
        "contract": build_spark_kb_contract_summary(),
        "snapshot_file": str(snapshot_path),
        "snapshot_valid": snapshot_valid,
        "snapshot_errors": snapshot_errors,
        "snapshot_generated_at": str((snapshot_payload or {}).get("generated_at") or ""),
        "repo_source_manifest_file_count": len(list(repo_source_manifest_files or [])),
        "repo_source_file_count": len(resolved_repo_sources),
        "repo_source_manifest_errors": repo_source_manifest_errors,
        "missing_repo_source_files": missing_repo_source_files,
        "resolved_repo_source_files": resolved_repo_sources,
        "filed_output_manifest_file_count": len(list(filed_output_manifest_files or [])),
        "filed_output_file_count": len(resolved_filed_output_files),
        "filed_output_manifest_errors": filed_output_manifest_errors,
        "missing_filed_output_files": missing_filed_output_files,
        "filed_output_file_errors": filed_output_file_errors,
        "filed_output_record_count": filed_output_record_count,
        "resolved_filed_output_files": resolved_filed_output_files,
        "valid": valid,
    }


def _build_spark_kb_from_snapshot_file(
    snapshot_file: str,
    output_dir: str,
    *,
    repo_sources: list[str] | None = None,
    repo_source_manifest_files: list[str] | None = None,
    filed_output_files: list[str] | None = None,
    filed_output_manifest_files: list[str] | None = None,
) -> dict:
    snapshot_path = Path(snapshot_file)
    snapshot = _load_json_file(snapshot_path)
    if not isinstance(snapshot, dict):
        raise ValueError("Spark KB snapshot file must contain a JSON object.")
    resolved_repo_sources = _resolve_repo_source_files(
        repo_sources=repo_sources,
        repo_source_manifest_files=repo_source_manifest_files,
    )
    resolved_filed_output_files = _resolve_filed_output_files(
        filed_output_files=filed_output_files,
        filed_output_manifest_files=filed_output_manifest_files,
    )
    filed_outputs = _load_filed_output_records(resolved_filed_output_files)
    compile_result = scaffold_spark_knowledge_base(
        output_dir,
        snapshot,
        vault_title="Spark Knowledge Base",
        repo_sources=resolved_repo_sources,
        filed_outputs=filed_outputs,
    )
    return {
        "contract": build_spark_kb_contract_summary(),
        "snapshot_file": str(snapshot_path),
        "snapshot": snapshot,
        "repo_source_manifest_file_count": len(list(repo_source_manifest_files or [])),
        "filed_output_manifest_file_count": len(list(filed_output_manifest_files or [])),
        "filed_output_file_count": len(resolved_filed_output_files),
        "compile_result": compile_result,
    }


def _build_beam_judged_cleanup_report(
    *,
    artifact_prefix: str,
    answers_root: str | Path,
    benchmark_runs_dir: str | Path,
    evaluation_file_name: str,
    repo_root: str | Path,
) -> dict:
    answers_root_path = Path(answers_root)
    benchmark_runs_path = Path(benchmark_runs_dir)
    repo_root_path = Path(repo_root)
    evaluation_file_basename = (
        evaluation_file_name
        if evaluation_file_name.startswith("evaluation-")
        else f"evaluation-{evaluation_file_name}"
    )

    answer_variant_dirs = sorted(
        path for path in answers_root_path.glob(f"{artifact_prefix}*") if path.is_dir()
    )
    evaluation_files = sorted(
        path
        for answer_variant_dir in answer_variant_dirs
        for path in answer_variant_dir.rglob(evaluation_file_basename)
        if path.is_file()
    )
    official_eval_manifests = sorted(
        path for path in benchmark_runs_path.glob(f"{artifact_prefix}*_official_eval.json") if path.is_file()
    )
    scorecard_files = sorted(
        path for path in benchmark_runs_path.glob(f"{artifact_prefix}*_scorecard.json") if path.is_file()
    )

    git_status_by_path = _git_status_by_path(
        [*evaluation_files, *official_eval_manifests, *scorecard_files],
        repo_root=repo_root_path,
    )

    evaluation_rows = []
    evaluation_categories_by_path: dict[str, list[str]] = {}
    category_universe: set[str] = set()
    for path in evaluation_files:
        summary = summarize_beam_official_evaluation(path)
        categories = _load_beam_evaluation_categories(path)
        evaluation_categories_by_path[str(path.resolve())] = categories
        category_universe.update(categories)
        display_path = _display_path(path, repo_root_path)
        evaluation_rows.append(
            {
                "path": display_path,
                "git_status": git_status_by_path.get(display_path, "clean"),
                "overall_average": summary["overall_average"],
                "category_count": summary["category_count"],
                "categories": categories,
            }
        )

    modified_evaluation_drift_rows = []
    for path in evaluation_files:
        display_path = _display_path(path, repo_root_path)
        git_status = git_status_by_path.get(display_path, "clean")
        if git_status != "M":
            continue
        drift_row = _build_beam_modified_evaluation_drift_row(
            path=path,
            repo_root=repo_root_path,
            git_status=git_status,
        )
        if drift_row:
            modified_evaluation_drift_rows.append(drift_row)

    official_eval_rows = []
    for path in official_eval_manifests:
        payload = _load_json_file(path)
        if not isinstance(payload, dict):
            continue
        display_path = _display_path(path, repo_root_path)
        aggregate_summary = payload.get("aggregate_summary") if isinstance(payload.get("aggregate_summary"), dict) else {}
        manifest_evaluation_files = [Path(item) for item in payload.get("evaluation_files", []) if str(item).strip()]
        completed_categories: set[str] = set()
        completed_category_counts: dict[str, int] = {}
        completed_category_order: list[str] = []
        for evaluation_file in manifest_evaluation_files:
            resolved_key = str(evaluation_file.resolve())
            categories = evaluation_categories_by_path.get(resolved_key)
            if categories is None and evaluation_file.is_file():
                categories = _load_beam_evaluation_categories(evaluation_file)
            category_counts = _load_beam_category_counts(evaluation_file) if evaluation_file.is_file() else {}
            category_order = _load_beam_category_order(evaluation_file) if evaluation_file.is_file() else []
            completed_categories.update(categories or [])
            for category in category_order:
                if category not in completed_category_counts:
                    completed_category_order.append(category)
                    completed_category_counts[category] = int(category_counts.get(category, 0))
        missing_evaluation_files = [str(item) for item in payload.get("missing_evaluation_files", []) if str(item).strip()]
        stderr_tail = [str(item) for item in payload.get("stderr_tail", []) if str(item).strip()]
        stdout_tail = [str(item) for item in payload.get("stdout_tail", []) if str(item).strip()]
        expected_category_order, expected_category_counts = _load_beam_expected_category_order_and_counts_for_manifest(payload)
        answer_category_order, answer_category_counts = _load_beam_answer_category_order_and_counts_for_manifest(payload)
        expected_categories = set(expected_category_order)
        answer_categories = set(answer_category_order)
        judge_config = payload.get("judge_config") if isinstance(payload.get("judge_config"), dict) else {}
        judge_provider = str(judge_config.get("provider") or "minimax")
        judge_model = str(judge_config.get("model") or "").strip()
        judge_base_url = str(judge_config.get("base_url") or "").strip()
        judge_api_key_env = str(judge_config.get("api_key_env") or "").strip()
        required_judge_env = _required_beam_judge_env(
            judge_provider=judge_provider,
            judge_api_key_env=judge_api_key_env,
        )
        judge_env_ready = not required_judge_env or bool(os.environ.get(required_judge_env))
        missing_expected_categories = sorted(expected_categories - completed_categories)
        missing_answer_categories = sorted(answer_categories - completed_categories)
        diagnostic_classification = _classify_beam_cleanup_manifest(
            status=str(payload.get("status") or ""),
            missing_evaluation_files=missing_evaluation_files,
            completed_categories=completed_categories,
            expected_categories=expected_categories or answer_categories,
            stderr_tail=stderr_tail,
        )
        progress_order = expected_category_order or answer_category_order or completed_category_order
        category_progress = []
        next_pending_category = ""
        next_pending_question_index: int | None = None
        last_completed_category = ""
        last_completed_question_index: int | None = None
        for category in progress_order:
            expected_count = int(expected_category_counts.get(category, 0))
            answer_count = int(answer_category_counts.get(category, 0))
            completed_count = int(completed_category_counts.get(category, 0))
            target_count = max(expected_count, answer_count)
            status_label = "pending"
            if completed_count and completed_count >= target_count:
                status_label = "completed"
            elif completed_count:
                status_label = "partial"
            category_progress.append(
                {
                    "category": category,
                    "expected_question_count": expected_count,
                    "answer_question_count": answer_count,
                    "completed_question_count": completed_count,
                    "status": status_label,
                }
            )
            if completed_count:
                last_completed_category = category
                last_completed_question_index = max(completed_count - 1, 0)
            if not next_pending_category and completed_count < target_count:
                next_pending_category = category
                next_pending_question_index = completed_count
        last_logged_question_type, last_logged_question_index = _parse_manifest_stdout_progress(stdout_tail)
        official_eval_rows.append(
            {
                "path": display_path,
                "git_status": git_status_by_path.get(display_path, "clean"),
                "status": str(payload.get("status") or ""),
                "overall_average": aggregate_summary.get("overall_average"),
                "evaluation_file_count": len(list(payload.get("evaluation_files") or [])),
                "category_count": len(completed_categories),
                "categories": sorted(completed_categories),
                "completed_category_order": completed_category_order,
                "expected_category_count": len(expected_categories),
                "expected_categories": sorted(expected_categories),
                "expected_category_order": expected_category_order,
                "answer_category_count": len(answer_categories),
                "answer_categories": sorted(answer_categories),
                "answer_category_order": answer_category_order,
                "missing_categories": missing_expected_categories,
                "missing_answer_categories": missing_answer_categories,
                "missing_evaluation_file_count": len(missing_evaluation_files),
                "diagnostic_classification": diagnostic_classification,
                "promotable_candidate": diagnostic_classification in {"completed", "timeout_after_complete_write"},
                "judge_provider": judge_provider,
                "judge_model": judge_model,
                "judge_base_url": judge_base_url,
                "judge_api_key_env": judge_api_key_env,
                "required_judge_env": required_judge_env,
                "judge_env_ready": judge_env_ready,
                "cleanup_blocked_reason": "" if judge_env_ready else "missing_judge_env",
                "category_progress": category_progress,
                "last_completed_category": last_completed_category,
                "last_completed_question_index": last_completed_question_index,
                "next_pending_category": next_pending_category,
                "next_pending_question_index": next_pending_question_index,
                "last_logged_question_type": last_logged_question_type,
                "last_logged_question_index": last_logged_question_index,
                "stdout_tail_last": stdout_tail[-1] if stdout_tail else "",
                "stderr_tail_last": stderr_tail[-1] if stderr_tail else "",
            }
        )

    scorecard_rows = [
        {
            "path": _display_path(path, repo_root_path),
            "git_status": git_status_by_path.get(_display_path(path, repo_root_path), "clean"),
        }
        for path in scorecard_files
    ]

    aggregate_evaluation_summary = (
        summarize_beam_official_evaluation_files(evaluation_files) if evaluation_files else None
    )
    git_status_counts: dict[str, int] = {}
    for row in [*evaluation_rows, *official_eval_rows, *scorecard_rows]:
        status = str(row.get("git_status") or "clean")
        git_status_counts[status] = git_status_counts.get(status, 0) + 1
    blocked_missing_env_vars = sorted(
        {
            str(row.get("required_judge_env") or "").strip()
            for row in official_eval_rows
            if str(row.get("cleanup_blocked_reason") or "") == "missing_judge_env"
            and str(row.get("required_judge_env") or "").strip()
        }
    )
    blocked_official_eval_manifest_count = sum(
        1 for row in official_eval_rows if str(row.get("cleanup_blocked_reason") or "").strip()
    )
    promotable_untracked_official_eval_manifests = [
        {
            "path": str(row.get("path") or ""),
            "git_status": str(row.get("git_status") or ""),
            "diagnostic_classification": str(row.get("diagnostic_classification") or ""),
            "overall_average": row.get("overall_average"),
            "evaluation_file_count": row.get("evaluation_file_count"),
        }
        for row in official_eval_rows
        if row.get("git_status") == "??" and bool(row.get("promotable_candidate"))
    ]

    return {
        "benchmark_name": "BEAM",
        "source_mode": "official_public_evaluation_cleanup",
        "artifact_prefix": artifact_prefix,
        "answers_root": str(answers_root_path),
        "benchmark_runs_dir": str(benchmark_runs_path),
        "repo_root": str(repo_root_path),
        "answer_variant_count": len(answer_variant_dirs),
        "evaluation_file_count": len(evaluation_rows),
        "modified_evaluation_drift_count": len(modified_evaluation_drift_rows),
        "official_eval_manifest_count": len(official_eval_rows),
        "runnable_official_eval_manifest_count": len(official_eval_rows) - blocked_official_eval_manifest_count,
        "blocked_official_eval_manifest_count": blocked_official_eval_manifest_count,
        "blocked_missing_env_vars": blocked_missing_env_vars,
        "promotable_untracked_official_eval_manifest_count": len(promotable_untracked_official_eval_manifests),
        "promotable_untracked_official_eval_manifests": promotable_untracked_official_eval_manifests,
        "scorecard_count": len(scorecard_rows),
        "git_status_counts": git_status_counts,
        "category_universe": sorted(category_universe),
        "max_category_count_seen": max((len(categories) for categories in evaluation_categories_by_path.values()), default=0),
        "aggregate_evaluation_summary": aggregate_evaluation_summary,
        "evaluation_files": evaluation_rows,
        "modified_evaluation_drift_files": modified_evaluation_drift_rows,
        "official_eval_manifests": official_eval_rows,
        "scorecards": scorecard_rows,
    }


def _benchmark_runs_file_family(path: Path) -> str:
    name = path.name
    if name.startswith("_debug_"):
        return "debug"
    if name.startswith("longmemeval_"):
        return "longmemeval"
    if name.endswith("_scorecard.json"):
        return "scorecard"
    if name.endswith("_official_eval.json"):
        return "official_eval_manifest"
    return "other"


def _benchmark_runs_series_key(path: Path) -> str:
    stem = path.stem
    if stem.startswith("_debug_gpt4_"):
        return "_debug_gpt4"
    if stem.startswith("_debug_"):
        return "_debug"
    if stem.endswith("_official_eval"):
        return stem.removesuffix("_official_eval")
    if stem.endswith("_scorecard"):
        stem = stem.removesuffix("_scorecard")
    stem = re.sub(r"_v\d+$", "", stem)
    return stem


def _benchmark_runs_git_report_command(
    *,
    benchmark_runs_dir: Path,
    repo_root: Path,
    only_noisy: bool,
    top_series_limit: int,
    summary_only: bool,
    family_filter: str | None,
    series_prefix: str | None,
) -> list[str]:
    command = [
        "python",
        "-m",
        "domain_chip_memory.cli",
        "benchmark-runs-git-report",
        "--benchmark-runs-dir",
        str(benchmark_runs_dir),
        "--repo-root",
        str(repo_root),
    ]
    if family_filter:
        command.extend(["--family", family_filter])
    if series_prefix:
        command.extend(["--series-prefix", series_prefix])
    if only_noisy:
        command.append("--only-noisy")
    if summary_only:
        command.append("--summary-only")
    command.extend(["--top-series-limit", str(top_series_limit)])
    return command


def _build_benchmark_runs_git_report(
    *,
    benchmark_runs_dir: str | Path,
    repo_root: str | Path,
    only_noisy: bool = False,
    top_series_limit: int = 10,
    summary_only: bool = False,
    family_filter: str | None = None,
    series_prefix: str | None = None,
) -> dict:
    benchmark_runs_path = Path(benchmark_runs_dir)
    repo_root_path = Path(repo_root)
    files = sorted(path for path in benchmark_runs_path.glob("*.json") if path.is_file())
    git_status_by_path = _git_status_by_path(files, repo_root=repo_root_path)
    available_families = sorted({_benchmark_runs_file_family(path) for path in files})

    git_status_counts: dict[str, int] = {}
    for path in files:
        display_path = _display_path(path, repo_root_path)
        git_status = git_status_by_path.get(display_path, "clean")
        git_status_counts[git_status] = git_status_counts.get(git_status, 0) + 1
    noisy_statuses = {"??", "A", "M", "D", "R", "C", "U"}
    noisy_paths = [
        path
        for path in files
        if git_status_by_path.get(_display_path(path, repo_root_path), "clean") in noisy_statuses
    ]
    noisy_files = [
        {
            "path": _display_path(path, repo_root_path),
            "git_status": git_status_by_path.get(_display_path(path, repo_root_path), "clean"),
            "family": _benchmark_runs_file_family(path),
        }
        for path in noisy_paths
    ]
    noisy_family_counts: dict[str, int] = {}
    for row in noisy_files:
        family = row["family"]
        noisy_family_counts[family] = noisy_family_counts.get(family, 0) + 1
    reported_paths = noisy_paths if only_noisy else files
    if family_filter:
        reported_paths = [path for path in reported_paths if _benchmark_runs_file_family(path) == family_filter]
        noisy_files = [row for row in noisy_files if row["family"] == family_filter]
    if series_prefix:
        reported_paths = [path for path in reported_paths if _benchmark_runs_series_key(path).startswith(series_prefix)]
        noisy_files = [row for row in noisy_files if _benchmark_runs_series_key(Path(row["path"])).startswith(series_prefix)]
    family_rows: dict[str, dict] = {}
    reported_git_status_counts: dict[str, int] = {}
    series_rows: dict[tuple[str, str], dict] = {}
    for path in reported_paths:
        display_path = _display_path(path, repo_root_path)
        git_status = git_status_by_path.get(display_path, "clean")
        family = _benchmark_runs_file_family(path)
        series = _benchmark_runs_series_key(path)
        reported_git_status_counts[git_status] = reported_git_status_counts.get(git_status, 0) + 1
        family_row = family_rows.setdefault(
            family,
            {
                "family": family,
                "file_count": 0,
                "git_status_counts": {},
                "paths": [],
            },
        )
        family_row["file_count"] += 1
        family_row["git_status_counts"][git_status] = family_row["git_status_counts"].get(git_status, 0) + 1
        family_row["paths"].append(display_path)
        series_row = series_rows.setdefault(
            (family, series),
            {
                "family": family,
                "series": series,
                "file_count": 0,
                "git_status_counts": {},
                "paths": [],
            },
        )
        series_row["file_count"] += 1
        series_row["git_status_counts"][git_status] = series_row["git_status_counts"].get(git_status, 0) + 1
        series_row["paths"].append(display_path)

    ordered_family_rows = [family_rows[key] for key in sorted(family_rows)]
    ordered_series_rows = [
        series_rows[key]
        for key in sorted(series_rows, key=lambda item: (item[0], item[1]))
    ]
    ranked_series_rows = sorted(
        ordered_series_rows,
        key=lambda row: (-row["file_count"], row["family"], row["series"]),
    )
    top_noisy_series = ranked_series_rows[: max(top_series_limit, 0)]
    noisy_file_count = len(noisy_files)
    family_command_counts = noisy_family_counts
    if series_prefix:
        family_command_counts = {}
        for row in noisy_files:
            family = row["family"]
            family_command_counts[family] = family_command_counts.get(family, 0) + 1
    if summary_only:
        ordered_family_rows = [{k: v for k, v in row.items() if k != "paths"} for row in ordered_family_rows]
        ordered_series_rows = [{k: v for k, v in row.items() if k != "paths"} for row in ordered_series_rows]
        top_noisy_series = [{k: v for k, v in row.items() if k != "paths"} for row in top_noisy_series]
        noisy_files = []
    current_command = _benchmark_runs_git_report_command(
        benchmark_runs_dir=benchmark_runs_path,
        repo_root=repo_root_path,
        only_noisy=only_noisy,
        top_series_limit=top_series_limit,
        summary_only=summary_only,
        family_filter=family_filter,
        series_prefix=series_prefix,
    )
    family_commands = [
        {
            "family": family,
            "noisy_file_count": family_command_counts[family],
            "command": _benchmark_runs_git_report_command(
                benchmark_runs_dir=benchmark_runs_path,
                repo_root=repo_root_path,
                only_noisy=True,
                top_series_limit=top_series_limit,
                summary_only=summary_only,
                family_filter=family,
                series_prefix=series_prefix,
            ),
        }
        for family in sorted(family_command_counts)
    ]
    for row in family_commands:
        row["command_shell"] = " ".join(_shell_quote_arg(part) for part in row["command"])
    recommended_focus = None
    if series_prefix:
        recommended_focus = {
            "scope": "series",
            "status": "already_focused",
            "family": family_filter,
            "series_prefix": series_prefix,
            "reported_file_count": len(reported_paths),
        }
    elif family_filter and top_noisy_series:
        top_series = top_noisy_series[0]
        recommended_command = _benchmark_runs_git_report_command(
            benchmark_runs_dir=benchmark_runs_path,
            repo_root=repo_root_path,
            only_noisy=True,
            top_series_limit=top_series_limit,
            summary_only=summary_only,
            family_filter=family_filter,
            series_prefix=top_series["series"],
        )
        recommended_focus = {
            "scope": "series",
            "reason": "largest_series_in_family",
            "family": family_filter,
            "series_prefix": top_series["series"],
            "noisy_file_count": top_series["file_count"],
            "command": recommended_command,
            "command_shell": " ".join(_shell_quote_arg(part) for part in recommended_command),
        }
    elif family_commands:
        recommended_row = max(
            family_commands,
            key=lambda row: (row["noisy_file_count"], row["family"]),
        )
        recommended_focus = {
            "scope": "family",
            "reason": "largest_noisy_family",
            "family": recommended_row["family"],
            "noisy_file_count": recommended_row["noisy_file_count"],
            "command": recommended_row["command"],
            "command_shell": recommended_row["command_shell"],
        }
    return {
        "source_mode": "benchmark_runs_git_report",
        "benchmark_runs_dir": str(benchmark_runs_path),
        "repo_root": str(repo_root_path),
        "family_filter": family_filter,
        "series_prefix": series_prefix,
        "available_families": available_families,
        "noisy_family_counts": noisy_family_counts,
        "only_noisy": only_noisy,
        "top_series_limit": top_series_limit,
        "summary_only": summary_only,
        "current_command": current_command,
        "current_command_shell": " ".join(_shell_quote_arg(part) for part in current_command),
        "recommended_focus": recommended_focus,
        "family_commands": family_commands,
        "file_count": len(files),
        "family_count": len(ordered_family_rows),
        "git_status_counts": git_status_counts,
        "reported_file_count": len(reported_paths),
        "reported_family_count": len(ordered_family_rows),
        "reported_git_status_counts": reported_git_status_counts,
        "reported_series_count": len(ordered_series_rows),
        "paths_included": not summary_only,
        "families": ordered_family_rows,
        "series": ordered_series_rows,
        "top_noisy_series": top_noisy_series,
        "noisy_file_count": noisy_file_count,
        "listed_noisy_file_count": len(noisy_files),
        "noisy_files": noisy_files,
    }


def _build_beam_judged_resume_plan(
    *,
    artifact_prefix: str,
    answers_root: str | Path,
    benchmark_runs_dir: str | Path,
    evaluation_file_name: str,
    repo_root: str | Path,
    only_runnable: bool = False,
) -> dict:
    repo_root_path = Path(repo_root)
    cleanup_report = _build_beam_judged_cleanup_report(
        artifact_prefix=artifact_prefix,
        answers_root=answers_root,
        benchmark_runs_dir=benchmark_runs_dir,
        evaluation_file_name=evaluation_file_name,
        repo_root=repo_root,
    )

    resume_targets = []
    for manifest_row in cleanup_report["official_eval_manifests"]:
        if str(manifest_row.get("status") or "") != "partial":
            continue
        manifest_path = repo_root_path / Path(str(manifest_row["path"]))
        payload = _load_json_file(manifest_path)
        if not isinstance(payload, dict):
            continue
        upstream_repo_dir = str(payload.get("upstream_repo_dir") or "").strip()
        answers_dir = str(payload.get("answers_root") or "").strip()
        chat_size = str(payload.get("requested_chat_size") or payload.get("official_chat_size_dir") or "").strip()
        result_file_name = str(payload.get("result_file_name") or "domain_chip_memory_answers.json").strip()
        start_index = int(payload.get("start_index", 0) or 0)
        end_index_raw = payload.get("end_index")
        end_index = int(end_index_raw) if end_index_raw is not None else None
        max_workers = int(payload.get("max_workers", 10) or 10)
        judge_config = payload.get("judge_config") if isinstance(payload.get("judge_config"), dict) else {}
        judge_provider = str(judge_config.get("provider") or "minimax")
        judge_model = str(judge_config.get("model") or "").strip()
        judge_base_url = str(judge_config.get("base_url") or "").strip()
        judge_api_key_env = str(judge_config.get("api_key_env") or "").strip()
        required_judge_env = _required_beam_judge_env(
            judge_provider=judge_provider,
            judge_api_key_env=judge_api_key_env,
        )
        judge_env_ready = not required_judge_env or bool(os.environ.get(required_judge_env))
        write_path = str(manifest_path)

        command = [
            "python",
            "-m",
            "domain_chip_memory.cli",
            "run-beam-official-evaluation",
            upstream_repo_dir,
            answers_dir,
            "--chat-size",
            chat_size,
            "--result-file-name",
            result_file_name,
            "--start-index",
            str(start_index),
        ]
        if end_index is not None:
            command.extend(["--end-index", str(end_index)])
        command.extend(["--max-workers", str(max_workers)])
        if judge_provider:
            command.extend(["--judge-provider", judge_provider])
        if judge_model:
            command.extend(["--judge-model", judge_model])
        if judge_base_url:
            command.extend(["--judge-base-url", judge_base_url])
        if judge_api_key_env:
            command.extend(["--judge-api-key-env", judge_api_key_env])
        command.extend(["--write", write_path])

        resume_targets.append(
            {
                "path": manifest_row["path"],
                "status": manifest_row["status"],
                "diagnostic_classification": manifest_row["diagnostic_classification"],
                "overall_average": manifest_row["overall_average"],
                "next_pending_category": manifest_row["next_pending_category"],
                "next_pending_question_index": manifest_row["next_pending_question_index"],
                "last_completed_category": manifest_row["last_completed_category"],
                "last_completed_question_index": manifest_row["last_completed_question_index"],
                "last_logged_question_type": manifest_row["last_logged_question_type"],
                "last_logged_question_index": manifest_row["last_logged_question_index"],
                "missing_categories": manifest_row["missing_categories"],
                "conversation_ids": [str(item) for item in payload.get("conversation_ids", []) if str(item).strip()],
                "upstream_repo_dir": upstream_repo_dir,
                "answers_dir": answers_dir,
                "chat_size": chat_size,
                "result_file_name": result_file_name,
                "start_index": start_index,
                "end_index": end_index,
                "max_workers": max_workers,
                "judge_provider": judge_provider,
                "judge_model": judge_model,
                "judge_base_url": judge_base_url,
                "judge_api_key_env": judge_api_key_env,
                "required_judge_env": required_judge_env,
                "judge_env_ready": judge_env_ready,
                "resume_blocked_reason": "" if judge_env_ready else "missing_judge_env",
                "write_path": write_path,
                "resume_command": command,
                "resume_command_shell": " ".join(_shell_quote_arg(arg) for arg in command),
            }
        )

    blocked_missing_env_vars = sorted(
        {
            str(target.get("required_judge_env") or "").strip()
            for target in resume_targets
            if str(target.get("resume_blocked_reason") or "") == "missing_judge_env"
            and str(target.get("required_judge_env") or "").strip()
        }
    )
    discovered_target_count = len(resume_targets)
    blocked_target_count = sum(
        1 for target in resume_targets if str(target.get("resume_blocked_reason") or "").strip()
    )
    emitted_targets = (
        [target for target in resume_targets if not str(target.get("resume_blocked_reason") or "").strip()]
        if only_runnable
        else resume_targets
    )
    return {
        "benchmark_name": "BEAM",
        "source_mode": "official_public_evaluation_resume_plan",
        "artifact_prefix": artifact_prefix,
        "only_runnable": only_runnable,
        "discovered_target_count": discovered_target_count,
        "resume_target_count": len(emitted_targets),
        "filtered_out_target_count": discovered_target_count - len(emitted_targets),
        "runnable_target_count": discovered_target_count - blocked_target_count,
        "blocked_target_count": blocked_target_count,
        "blocked_missing_env_vars": blocked_missing_env_vars,
        "resume_targets": emitted_targets,
    }


def _build_beam_judged_resume_batch(
    *,
    artifact_prefix: str,
    answers_root: str | Path,
    benchmark_runs_dir: str | Path,
    evaluation_file_name: str,
    repo_root: str | Path,
    script_file: str | None = None,
    execute: bool = False,
    only_runnable: bool = False,
) -> dict:
    repo_root_path = Path(repo_root)
    resume_plan = _build_beam_judged_resume_plan(
        artifact_prefix=artifact_prefix,
        answers_root=answers_root,
        benchmark_runs_dir=benchmark_runs_dir,
        evaluation_file_name=evaluation_file_name,
        repo_root=repo_root,
        only_runnable=only_runnable,
    )

    script_lines = [
        "$ErrorActionPreference = 'Stop'",
        f"# Generated by beam-judged-resume-batch for {artifact_prefix}",
    ]
    for target in resume_plan["resume_targets"]:
        script_lines.append(
            f"# {target['path']} :: {target['diagnostic_classification']} :: next {target['next_pending_category']}[{target['next_pending_question_index']}]"
        )
        script_lines.append(str(target["resume_command_shell"]))

    script_text = "\n".join(script_lines) + "\n"
    if script_file:
        script_path = Path(script_file)
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(script_text, encoding="utf-8")

    execution_results = []
    if execute:
        for target in resume_plan["resume_targets"]:
            required_env = str(target.get("required_judge_env") or "").strip()
            if required_env and not os.environ.get(required_env):
                execution_results.append(
                    {
                        "path": target["path"],
                        "return_code": None,
                        "status": "blocked_missing_env",
                        "missing_env_var": required_env,
                        "executed_command": [],
                        "stdout_tail": [],
                        "stderr_tail": [f"Missing required environment variable: {required_env}"],
                    }
                )
                continue
            command = list(target["resume_command"])
            executed_command = [sys.executable if command and command[0] == "python" else command[0], *command[1:]]
            result = subprocess.run(
                executed_command,
                cwd=str(repo_root_path.resolve()),
                capture_output=True,
                text=True,
                check=False,
            )
            execution_results.append(
                {
                    "path": target["path"],
                    "return_code": int(result.returncode),
                    "status": "completed" if result.returncode == 0 else "failed",
                    "executed_command": executed_command,
                    "stdout_tail": result.stdout.splitlines()[-20:],
                    "stderr_tail": result.stderr.splitlines()[-20:],
                }
            )

    execution_status_counts: dict[str, int] = {}
    for result in execution_results:
        status = str(result.get("status") or "unknown")
        execution_status_counts[status] = execution_status_counts.get(status, 0) + 1

    return {
        "benchmark_name": "BEAM",
        "source_mode": "official_public_evaluation_resume_batch",
        "artifact_prefix": artifact_prefix,
        "only_runnable": bool(resume_plan.get("only_runnable")),
        "discovered_target_count": int(resume_plan.get("discovered_target_count") or 0),
        "resume_target_count": int(resume_plan["resume_target_count"]),
        "filtered_out_target_count": int(resume_plan.get("filtered_out_target_count") or 0),
        "runnable_target_count": int(resume_plan.get("runnable_target_count") or 0),
        "blocked_target_count": int(resume_plan.get("blocked_target_count") or 0),
        "blocked_missing_env_vars": list(resume_plan.get("blocked_missing_env_vars") or []),
        "resume_targets": resume_plan["resume_targets"],
        "script_file": str(script_file) if script_file else "",
        "script_line_count": len(script_lines),
        "script_lines": script_lines,
        "script_text": script_text,
        "execute_requested": execute,
        "executed_target_count": len(execution_results),
        "execution_status_counts": execution_status_counts,
        "completed_execution_count": execution_status_counts.get("completed", 0),
        "failed_execution_count": execution_status_counts.get("failed", 0),
        "blocked_execution_count": execution_status_counts.get("blocked_missing_env", 0),
        "execution_results": execution_results,
    }


def _build_beam_judged_promotion_plan(
    *,
    artifact_prefix: str,
    answers_root: str | Path,
    benchmark_runs_dir: str | Path,
    evaluation_file_name: str,
    repo_root: str | Path,
) -> dict:
    repo_root_path = Path(repo_root)
    repo_root_resolved = repo_root_path.resolve()
    cleanup_report = _build_beam_judged_cleanup_report(
        artifact_prefix=artifact_prefix,
        answers_root=answers_root,
        benchmark_runs_dir=benchmark_runs_dir,
        evaluation_file_name=evaluation_file_name,
        repo_root=repo_root,
    )
    promotion_targets = []
    for manifest_row in cleanup_report["promotable_untracked_official_eval_manifests"]:
        manifest_path = repo_root_path / Path(str(manifest_row["path"]))
        payload = _load_json_file(manifest_path)
        if not isinstance(payload, dict):
            continue
        evaluation_files = [
            _display_path(Path(item), repo_root_resolved)
            for item in payload.get("evaluation_files", [])
            if str(item).strip()
        ]
        git_add_paths = [str(manifest_row["path"]), *evaluation_files]
        promotion_targets.append(
            {
                "manifest_path": str(manifest_row["path"]),
                "diagnostic_classification": str(manifest_row.get("diagnostic_classification") or ""),
                "overall_average": manifest_row.get("overall_average"),
                "evaluation_files": evaluation_files,
                "git_add_paths": git_add_paths,
                "git_add_command": ["git", "add", "--", *git_add_paths],
                "git_add_command_shell": "git add -- " + " ".join(_shell_quote_arg(path) for path in git_add_paths),
            }
        )
    return {
        "benchmark_name": "BEAM",
        "source_mode": "official_public_evaluation_promotion_plan",
        "artifact_prefix": artifact_prefix,
        "promotion_target_count": len(promotion_targets),
        "promotion_targets": promotion_targets,
        "excluded_modified_evaluation_drift_count": int(cleanup_report.get("modified_evaluation_drift_count") or 0),
        "excluded_modified_evaluation_drift_files": list(cleanup_report.get("modified_evaluation_drift_files") or []),
    }


def _build_beam_judged_drift_plan(
    *,
    artifact_prefix: str,
    answers_root: str | Path,
    benchmark_runs_dir: str | Path,
    evaluation_file_name: str,
    repo_root: str | Path,
) -> dict:
    cleanup_report = _build_beam_judged_cleanup_report(
        artifact_prefix=artifact_prefix,
        answers_root=answers_root,
        benchmark_runs_dir=benchmark_runs_dir,
        evaluation_file_name=evaluation_file_name,
        repo_root=repo_root,
    )
    drift_targets = []
    for drift_row in cleanup_report.get("modified_evaluation_drift_files", []):
        path = str(drift_row.get("path") or "").strip()
        if not path:
            continue
        drift_targets.append(
            {
                "path": path,
                "git_status": str(drift_row.get("git_status") or ""),
                "current_overall_average": drift_row.get("current_overall_average"),
                "head_overall_average": drift_row.get("head_overall_average"),
                "overall_average_delta": drift_row.get("overall_average_delta"),
                "changed_category_count": drift_row.get("changed_category_count"),
                "changed_categories": list(drift_row.get("changed_categories") or []),
                "git_diff_command": ["git", "diff", "--", path],
                "git_diff_command_shell": "git diff -- " + _shell_quote_arg(path),
                "git_show_head_command": ["git", "show", f"HEAD:{path.replace('\\', '/')}"],
                "git_show_head_command_shell": "git show " + _shell_quote_arg(f"HEAD:{path.replace('\\', '/')}"),
                "git_restore_command": ["git", "restore", "--source=HEAD", "--", path],
                "git_restore_command_shell": "git restore --source=HEAD -- " + _shell_quote_arg(path),
            }
        )
    return {
        "benchmark_name": "BEAM",
        "source_mode": "official_public_evaluation_drift_plan",
        "artifact_prefix": artifact_prefix,
        "drift_target_count": len(drift_targets),
        "drift_targets": drift_targets,
    }


def _build_beam_judged_drift_batch(
    *,
    artifact_prefix: str,
    answers_root: str | Path,
    benchmark_runs_dir: str | Path,
    evaluation_file_name: str,
    repo_root: str | Path,
    script_file: str | Path | None,
    execute: bool,
) -> dict:
    repo_root_path = Path(repo_root)
    drift_plan = _build_beam_judged_drift_plan(
        artifact_prefix=artifact_prefix,
        answers_root=answers_root,
        benchmark_runs_dir=benchmark_runs_dir,
        evaluation_file_name=evaluation_file_name,
        repo_root=repo_root,
    )

    script_lines = [
        "$ErrorActionPreference = 'Stop'",
        f"# Generated by beam-judged-drift-batch for {artifact_prefix}",
    ]
    for target in drift_plan["drift_targets"]:
        script_lines.append(
            f"# {target['path']} :: overall delta {target['overall_average_delta']} :: changed categories {target['changed_category_count']}"
        )
        script_lines.append(str(target["git_diff_command_shell"]))
        script_lines.append(str(target["git_show_head_command_shell"]))
        script_lines.append("# Optional restore command:")
        script_lines.append(f"# {target['git_restore_command_shell']}")

    script_text = "\n".join(script_lines) + "\n"
    if script_file:
        script_path = Path(script_file)
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(script_text, encoding="utf-8")

    execution_results = []
    if execute:
        for target in drift_plan["drift_targets"]:
            command_results = []
            for command in [target["git_diff_command"], target["git_show_head_command"]]:
                result = subprocess.run(
                    list(command),
                    cwd=str(repo_root_path.resolve()),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                command_results.append(
                    {
                        "executed_command": list(command),
                        "return_code": int(result.returncode),
                        "status": "completed" if result.returncode == 0 else "failed",
                        "stdout_tail": result.stdout.splitlines()[-20:],
                        "stderr_tail": result.stderr.splitlines()[-20:],
                    }
                )
            execution_results.append(
                {
                    "path": target["path"],
                    "status": "completed" if all(item["return_code"] == 0 for item in command_results) else "failed",
                    "command_results": command_results,
                }
            )

    execution_status_counts: dict[str, int] = {}
    for result in execution_results:
        status = str(result.get("status") or "unknown")
        execution_status_counts[status] = execution_status_counts.get(status, 0) + 1

    return {
        "benchmark_name": "BEAM",
        "source_mode": "official_public_evaluation_drift_batch",
        "artifact_prefix": artifact_prefix,
        "drift_target_count": int(drift_plan["drift_target_count"]),
        "drift_targets": drift_plan["drift_targets"],
        "script_file": str(script_file) if script_file else "",
        "script_line_count": len(script_lines),
        "script_lines": script_lines,
        "script_text": script_text,
        "execute_requested": execute,
        "executed_target_count": len(execution_results),
        "execution_status_counts": execution_status_counts,
        "completed_execution_count": execution_status_counts.get("completed", 0),
        "failed_execution_count": execution_status_counts.get("failed", 0),
        "execution_results": execution_results,
    }


def _build_beam_judged_promotion_batch(
    *,
    artifact_prefix: str,
    answers_root: str | Path,
    benchmark_runs_dir: str | Path,
    evaluation_file_name: str,
    repo_root: str | Path,
    script_file: str | Path | None,
    execute: bool,
) -> dict:
    repo_root_path = Path(repo_root)
    promotion_plan = _build_beam_judged_promotion_plan(
        artifact_prefix=artifact_prefix,
        answers_root=answers_root,
        benchmark_runs_dir=benchmark_runs_dir,
        evaluation_file_name=evaluation_file_name,
        repo_root=repo_root,
    )

    script_lines = [
        "$ErrorActionPreference = 'Stop'",
        f"# Generated by beam-judged-promotion-batch for {artifact_prefix}",
    ]
    for target in promotion_plan["promotion_targets"]:
        script_lines.append(
            f"# {target['manifest_path']} :: {target['diagnostic_classification']} :: overall {target['overall_average']}"
        )
        script_lines.append(str(target["git_add_command_shell"]))

    script_text = "\n".join(script_lines) + "\n"
    if script_file:
        script_path = Path(script_file)
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(script_text, encoding="utf-8")

    execution_results = []
    if execute:
        for target in promotion_plan["promotion_targets"]:
            executed_command = list(target["git_add_command"])
            result = subprocess.run(
                executed_command,
                cwd=str(repo_root_path.resolve()),
                capture_output=True,
                text=True,
                check=False,
            )
            execution_results.append(
                {
                    "manifest_path": target["manifest_path"],
                    "return_code": int(result.returncode),
                    "status": "completed" if result.returncode == 0 else "failed",
                    "executed_command": executed_command,
                    "stdout_tail": result.stdout.splitlines()[-20:],
                    "stderr_tail": result.stderr.splitlines()[-20:],
                }
            )

    execution_status_counts: dict[str, int] = {}
    for result in execution_results:
        status = str(result.get("status") or "unknown")
        execution_status_counts[status] = execution_status_counts.get(status, 0) + 1

    return {
        "benchmark_name": "BEAM",
        "source_mode": "official_public_evaluation_promotion_batch",
        "artifact_prefix": artifact_prefix,
        "promotion_target_count": int(promotion_plan["promotion_target_count"]),
        "promotion_targets": promotion_plan["promotion_targets"],
        "excluded_modified_evaluation_drift_count": int(promotion_plan.get("excluded_modified_evaluation_drift_count") or 0),
        "excluded_modified_evaluation_drift_files": list(promotion_plan.get("excluded_modified_evaluation_drift_files") or []),
        "script_file": str(script_file) if script_file else "",
        "script_line_count": len(script_lines),
        "script_lines": script_lines,
        "script_text": script_text,
        "execute_requested": execute,
        "executed_target_count": len(execution_results),
        "execution_status_counts": execution_status_counts,
        "completed_execution_count": execution_status_counts.get("completed", 0),
        "failed_execution_count": execution_status_counts.get("failed", 0),
        "execution_results": execution_results,
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
    build_spark_kb = subparsers.add_parser("build-spark-kb", help="Compile a Spark KB vault from a snapshot JSON file.")
    build_spark_kb.add_argument("snapshot_file")
    build_spark_kb.add_argument("output_dir")
    build_spark_kb.add_argument("--repo-source", action="append", default=[])
    build_spark_kb.add_argument("--repo-source-manifest", action="append", default=[])
    build_spark_kb.add_argument("--filed-output-file", action="append", default=[])
    build_spark_kb.add_argument("--filed-output-manifest", action="append", default=[])
    build_spark_kb.add_argument("--write")
    benchmark_runs_git_report = subparsers.add_parser("benchmark-runs-git-report", help="Summarize benchmark-runs JSON files by git status and file family.")
    benchmark_runs_git_report.add_argument("--benchmark-runs-dir", default="artifacts/benchmark_runs")
    benchmark_runs_git_report.add_argument("--repo-root", default=".")
    benchmark_runs_git_report.add_argument("--family", choices=["debug", "longmemeval", "scorecard", "official_eval_manifest", "other"])
    benchmark_runs_git_report.add_argument("--series-prefix")
    benchmark_runs_git_report.add_argument("--only-noisy", action="store_true")
    benchmark_runs_git_report.add_argument("--top-series-limit", type=int, default=10)
    benchmark_runs_git_report.add_argument("--summary-only", action="store_true")
    benchmark_runs_git_report.add_argument("--write")
    beam_judged_cleanup_report = subparsers.add_parser("beam-judged-cleanup-report", help="Summarize local judged BEAM artifact state for cleanup planning.")
    beam_judged_cleanup_report.add_argument("--artifact-prefix", default="official_beam_128k_")
    beam_judged_cleanup_report.add_argument("--answers-root", default="artifacts/beam_public_results")
    beam_judged_cleanup_report.add_argument("--benchmark-runs-dir", default="artifacts/benchmark_runs")
    beam_judged_cleanup_report.add_argument("--evaluation-file-name", default="evaluation-domain_chip_memory_answers.json")
    beam_judged_cleanup_report.add_argument("--repo-root", default=".")
    beam_judged_cleanup_report.add_argument("--write")
    beam_judged_resume_plan = subparsers.add_parser("beam-judged-resume-plan", help="Build exact rerun commands for partial judged BEAM manifests.")
    beam_judged_resume_plan.add_argument("--artifact-prefix", default="official_beam_128k_")
    beam_judged_resume_plan.add_argument("--answers-root", default="artifacts/beam_public_results")
    beam_judged_resume_plan.add_argument("--benchmark-runs-dir", default="artifacts/benchmark_runs")
    beam_judged_resume_plan.add_argument("--evaluation-file-name", default="evaluation-domain_chip_memory_answers.json")
    beam_judged_resume_plan.add_argument("--repo-root", default=".")
    beam_judged_resume_plan.add_argument("--only-runnable", action="store_true")
    beam_judged_resume_plan.add_argument("--write")
    beam_judged_resume_batch = subparsers.add_parser("beam-judged-resume-batch", help="Build one ordered PowerShell batch script for partial judged BEAM manifests.")
    beam_judged_resume_batch.add_argument("--artifact-prefix", default="official_beam_128k_")
    beam_judged_resume_batch.add_argument("--answers-root", default="artifacts/beam_public_results")
    beam_judged_resume_batch.add_argument("--benchmark-runs-dir", default="artifacts/benchmark_runs")
    beam_judged_resume_batch.add_argument("--evaluation-file-name", default="evaluation-domain_chip_memory_answers.json")
    beam_judged_resume_batch.add_argument("--repo-root", default=".")
    beam_judged_resume_batch.add_argument("--script-file")
    beam_judged_resume_batch.add_argument("--execute", action="store_true")
    beam_judged_resume_batch.add_argument("--only-runnable", action="store_true")
    beam_judged_resume_batch.add_argument("--write")
    beam_judged_promotion_plan = subparsers.add_parser("beam-judged-promotion-plan", help="Build exact git add commands for promotable untracked judged BEAM manifests.")
    beam_judged_promotion_plan.add_argument("--artifact-prefix", default="official_beam_128k_")
    beam_judged_promotion_plan.add_argument("--answers-root", default="artifacts/beam_public_results")
    beam_judged_promotion_plan.add_argument("--benchmark-runs-dir", default="artifacts/benchmark_runs")
    beam_judged_promotion_plan.add_argument("--evaluation-file-name", default="evaluation-domain_chip_memory_answers.json")
    beam_judged_promotion_plan.add_argument("--repo-root", default=".")
    beam_judged_promotion_plan.add_argument("--write")
    beam_judged_drift_plan = subparsers.add_parser("beam-judged-drift-plan", help="Build exact inspection and restore commands for tracked judged BEAM evaluation drift.")
    beam_judged_drift_plan.add_argument("--artifact-prefix", default="official_beam_128k_")
    beam_judged_drift_plan.add_argument("--answers-root", default="artifacts/beam_public_results")
    beam_judged_drift_plan.add_argument("--benchmark-runs-dir", default="artifacts/benchmark_runs")
    beam_judged_drift_plan.add_argument("--evaluation-file-name", default="evaluation-domain_chip_memory_answers.json")
    beam_judged_drift_plan.add_argument("--repo-root", default=".")
    beam_judged_drift_plan.add_argument("--write")
    beam_judged_drift_batch = subparsers.add_parser("beam-judged-drift-batch", help="Build one ordered PowerShell batch script for tracked judged BEAM evaluation drift.")
    beam_judged_drift_batch.add_argument("--artifact-prefix", default="official_beam_128k_")
    beam_judged_drift_batch.add_argument("--answers-root", default="artifacts/beam_public_results")
    beam_judged_drift_batch.add_argument("--benchmark-runs-dir", default="artifacts/benchmark_runs")
    beam_judged_drift_batch.add_argument("--evaluation-file-name", default="evaluation-domain_chip_memory_answers.json")
    beam_judged_drift_batch.add_argument("--repo-root", default=".")
    beam_judged_drift_batch.add_argument("--script-file")
    beam_judged_drift_batch.add_argument("--execute", action="store_true")
    beam_judged_drift_batch.add_argument("--write")
    beam_judged_promotion_batch = subparsers.add_parser("beam-judged-promotion-batch", help="Build one ordered PowerShell batch script for promotable untracked judged BEAM manifests.")
    beam_judged_promotion_batch.add_argument("--artifact-prefix", default="official_beam_128k_")
    beam_judged_promotion_batch.add_argument("--answers-root", default="artifacts/beam_public_results")
    beam_judged_promotion_batch.add_argument("--benchmark-runs-dir", default="artifacts/benchmark_runs")
    beam_judged_promotion_batch.add_argument("--evaluation-file-name", default="evaluation-domain_chip_memory_answers.json")
    beam_judged_promotion_batch.add_argument("--repo-root", default=".")
    beam_judged_promotion_batch.add_argument("--script-file")
    beam_judged_promotion_batch.add_argument("--execute", action="store_true")
    beam_judged_promotion_batch.add_argument("--write")
    validate_spark_kb_inputs = subparsers.add_parser("validate-spark-kb-inputs", help="Validate Spark KB snapshot, repo-source, and filed-output inputs without compiling a vault.")
    validate_spark_kb_inputs.add_argument("snapshot_file")
    validate_spark_kb_inputs.add_argument("--repo-source", action="append", default=[])
    validate_spark_kb_inputs.add_argument("--repo-source-manifest", action="append", default=[])
    validate_spark_kb_inputs.add_argument("--filed-output-file", action="append", default=[])
    validate_spark_kb_inputs.add_argument("--filed-output-manifest", action="append", default=[])
    validate_spark_kb_inputs.add_argument("--write")
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

    if args.command == "build-spark-kb":
        payload = _build_spark_kb_from_snapshot_file(
            args.snapshot_file,
            args.output_dir,
            repo_sources=args.repo_source,
            repo_source_manifest_files=args.repo_source_manifest,
            filed_output_files=args.filed_output_file,
            filed_output_manifest_files=args.filed_output_manifest,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "benchmark-runs-git-report":
        payload = _build_benchmark_runs_git_report(
            benchmark_runs_dir=args.benchmark_runs_dir,
            repo_root=args.repo_root,
            family_filter=args.family,
            series_prefix=args.series_prefix,
            only_noisy=args.only_noisy,
            top_series_limit=args.top_series_limit,
            summary_only=args.summary_only,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "beam-judged-cleanup-report":
        payload = _build_beam_judged_cleanup_report(
            artifact_prefix=args.artifact_prefix,
            answers_root=args.answers_root,
            benchmark_runs_dir=args.benchmark_runs_dir,
            evaluation_file_name=args.evaluation_file_name,
            repo_root=args.repo_root,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "validate-spark-kb-inputs":
        payload = _validate_spark_kb_inputs(
            args.snapshot_file,
            repo_sources=args.repo_source,
            repo_source_manifest_files=args.repo_source_manifest,
            filed_output_files=args.filed_output_file,
            filed_output_manifest_files=args.filed_output_manifest,
        )
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

    if args.command == "beam-judged-resume-plan":
        payload = _build_beam_judged_resume_plan(
            artifact_prefix=args.artifact_prefix,
            answers_root=args.answers_root,
            benchmark_runs_dir=args.benchmark_runs_dir,
            evaluation_file_name=args.evaluation_file_name,
            repo_root=args.repo_root,
            only_runnable=args.only_runnable,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "beam-judged-resume-batch":
        payload = _build_beam_judged_resume_batch(
            artifact_prefix=args.artifact_prefix,
            answers_root=args.answers_root,
            benchmark_runs_dir=args.benchmark_runs_dir,
            evaluation_file_name=args.evaluation_file_name,
            repo_root=args.repo_root,
            script_file=args.script_file,
            execute=args.execute,
            only_runnable=args.only_runnable,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "beam-judged-promotion-plan":
        payload = _build_beam_judged_promotion_plan(
            artifact_prefix=args.artifact_prefix,
            answers_root=args.answers_root,
            benchmark_runs_dir=args.benchmark_runs_dir,
            evaluation_file_name=args.evaluation_file_name,
            repo_root=args.repo_root,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "beam-judged-drift-plan":
        payload = _build_beam_judged_drift_plan(
            artifact_prefix=args.artifact_prefix,
            answers_root=args.answers_root,
            benchmark_runs_dir=args.benchmark_runs_dir,
            evaluation_file_name=args.evaluation_file_name,
            repo_root=args.repo_root,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "beam-judged-drift-batch":
        payload = _build_beam_judged_drift_batch(
            artifact_prefix=args.artifact_prefix,
            answers_root=args.answers_root,
            benchmark_runs_dir=args.benchmark_runs_dir,
            evaluation_file_name=args.evaluation_file_name,
            repo_root=args.repo_root,
            script_file=args.script_file,
            execute=args.execute,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "beam-judged-promotion-batch":
        payload = _build_beam_judged_promotion_batch(
            artifact_prefix=args.artifact_prefix,
            answers_root=args.answers_root,
            benchmark_runs_dir=args.benchmark_runs_dir,
            evaluation_file_name=args.evaluation_file_name,
            repo_root=args.repo_root,
            script_file=args.script_file,
            execute=args.execute,
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
