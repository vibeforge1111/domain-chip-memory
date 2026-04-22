from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter

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
from .memory_conversational_shadow_eval import build_multi_shadow_answer_eval
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
from .spark_shadow import (
    SparkShadowIngestAdapter,
    SparkShadowIngestRequest,
    SparkShadowProbe,
    SparkShadowTurn,
    build_builder_shadow_adapter_contract_summary,
    build_shadow_ingest_contract_summary,
    build_shadow_report,
    build_shadow_replay_contract_summary,
    normalize_builder_shadow_export_payload,
    normalize_telegram_bot_export_payload,
    build_telegram_shadow_adapter_contract_summary,
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


def _load_beam_official_eval_exports() -> dict[str, object]:
    from .beam_official_eval import (
        _summarize_beam_evaluation_payload,
        export_beam_public_answers_from_scorecard,
        run_beam_official_evaluation,
        summarize_beam_official_evaluation,
        summarize_beam_official_evaluation_files,
    )

    return {
        "_summarize_beam_evaluation_payload": _summarize_beam_evaluation_payload,
        "export_beam_public_answers_from_scorecard": export_beam_public_answers_from_scorecard,
        "run_beam_official_evaluation": run_beam_official_evaluation,
        "summarize_beam_official_evaluation": summarize_beam_official_evaluation,
        "summarize_beam_official_evaluation_files": summarize_beam_official_evaluation_files,
    }


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


def _filter_locomo_shadow_samples(
    samples: list[NormalizedBenchmarkSample],
    *,
    sample_ids: list[str] | None = None,
    categories: list[str] | None = None,
    question_ids: list[str] | None = None,
    exclude_missing_gold: bool = False,
) -> list[NormalizedBenchmarkSample]:
    requested_ids = {sample_id.strip() for sample_id in (sample_ids or []) if sample_id.strip()}
    requested_categories = {category.strip() for category in (categories or []) if category.strip()}
    requested_question_ids = {question_id.strip() for question_id in (question_ids or []) if question_id.strip()}
    filtered: list[NormalizedBenchmarkSample] = []
    for sample in samples:
        if requested_ids and sample.sample_id not in requested_ids:
            continue
        questions = [
            question
            for question in sample.questions
            if (not requested_categories or question.category in requested_categories)
            and (not requested_question_ids or question.question_id in requested_question_ids)
            and (not exclude_missing_gold or not bool(question.metadata.get("gold_answer_missing")))
        ]
        if not questions:
            continue
        filtered.append(replace(sample, questions=questions))
    return filtered


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


def _execute_shadow_replay_payload(
    payload: object,
    *,
    adapter: SparkShadowIngestAdapter | None = None,
) -> tuple[list, SparkShadowIngestAdapter]:
    if not isinstance(payload, dict):
        raise ValueError("Shadow replay file must contain a JSON object.")
    raw_conversations = payload.get("conversations", [])
    if not isinstance(raw_conversations, list):
        raise ValueError("Shadow replay file must contain a conversations list.")

    active_adapter = adapter
    if active_adapter is None:
        writable_roles = payload.get("writable_roles")
        if isinstance(writable_roles, list):
            active_adapter = SparkShadowIngestAdapter(writable_roles=tuple(str(role) for role in writable_roles))
        else:
            active_adapter = SparkShadowIngestAdapter()

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
        ingest_result = active_adapter.ingest_conversation(
            SparkShadowIngestRequest(
                conversation_id=conversation_id,
                session_id=str(item.get("session_id")) if item.get("session_id") is not None else None,
                turns=turns,
                metadata=dict(item.get("metadata", {})),
            )
        )
        evaluations.append(active_adapter.evaluate_ingest(ingest_result, probes=probes))

    return evaluations, active_adapter


def _execute_shadow_replay(data_file: str) -> tuple[list, SparkShadowIngestAdapter]:
    payload = json.loads(Path(data_file).read_text(encoding="utf-8"))
    return _execute_shadow_replay_payload(payload)


def _load_shadow_evaluations(data_file: str) -> list:
    evaluations, _ = _execute_shadow_replay(data_file)
    return evaluations


def _build_shadow_report_payload_from_evaluations(evaluations: list) -> dict:
    report = build_shadow_report(evaluations)
    return {
        "evaluations": [asdict(evaluation) for evaluation in evaluations],
        "report": asdict(report),
    }


def _load_shadow_report_payload(data_file: str) -> dict:
    return _build_shadow_report_payload_from_evaluations(_load_shadow_evaluations(data_file))


def _build_shadow_report_filed_outputs(shadow_payload: dict) -> list[dict]:
    report = dict(shadow_payload.get("report", {}))
    summary = dict(report.get("summary", {}))
    conversation_rows = list(report.get("conversation_rows", []))
    probe_rows = list(summary.get("probe_rows", []))
    unsupported_reasons = list(summary.get("unsupported_reasons", []))

    probe_lines = [
        (
            f"`{row.get('probe_type', 'unknown')}` "
            f"hits `{row.get('hits', 0)}/{row.get('total', 0)}` "
            f"(match `{row.get('expected_matches', 0)}/{row.get('expected_total', 0)}`)"
        )
        for row in probe_rows
    ]
    unsupported_lines = [
        f"`{row.get('reason', 'unknown')}` x{row.get('count', 0)}"
        for row in unsupported_reasons
    ]
    conversation_lines = [
        (
            f"`{row.get('conversation_id', 'unknown')}` accepted `{row.get('accepted_writes', 0)}`, "
            f"rejected `{row.get('rejected_writes', 0)}`, skipped `{row.get('skipped_turns', 0)}`, "
            f"reference `{row.get('reference_turns', 0)}`"
        )
        for row in conversation_rows
    ]

    filed_outputs: list[dict] = [
        {
            "title": "Spark Shadow Run Summary",
            "slug": "spark-shadow-run-summary",
            "question": "What happened in the current Spark shadow replay run?",
            "answer": (
                f"Processed {report.get('run_count', 0)} conversation runs with "
                f"{summary.get('accepted_writes', 0)} accepted writes, "
                f"{summary.get('rejected_writes', 0)} rejected writes, and "
                f"{summary.get('skipped_turns', 0)} skipped turns, plus "
                f"{summary.get('reference_turns', 0)} reference turns."
            ),
            "explanation": (
                "This filed output summarizes the governed Spark shadow replay so the KB can expose "
                "write acceptance, rejection, and probe coverage alongside the runtime snapshot."
            ),
            "memory_role": "shadow_report",
            "provenance": [
                *conversation_lines,
                *([f"Probe coverage: {line}" for line in probe_lines] or ["Probe coverage: none recorded."]),
                *([f"Unsupported reasons: {line}" for line in unsupported_lines] or ["Unsupported reasons: none recorded."]),
            ],
        }
    ]

    for row in conversation_rows:
        conversation_id = str(row.get("conversation_id") or "unknown").strip() or "unknown"
        filed_outputs.append(
            {
                "title": f"Spark Shadow Conversation {conversation_id}",
                "slug": f"spark-shadow-conversation-{conversation_id}",
                "question": f"How did Spark shadow conversation {conversation_id} perform?",
                "answer": (
                    f"Conversation {conversation_id} produced {row.get('accepted_writes', 0)} accepted writes, "
                    f"{row.get('rejected_writes', 0)} rejected writes, {row.get('skipped_turns', 0)} skipped turns, "
                    f"and {row.get('reference_turns', 0)} reference turns."
                ),
                "explanation": (
                    "This filed output preserves one Spark-facing conversation summary inside the KB so replay results "
                    "and governed memory pages can be inspected together."
                ),
                "memory_role": "shadow_report",
                "provenance": [
                    f"`{conversation_id}`",
                    f"Accepted writes: `{row.get('accepted_writes', 0)}`",
                    f"Rejected writes: `{row.get('rejected_writes', 0)}`",
                    f"Skipped turns: `{row.get('skipped_turns', 0)}`",
                    f"Reference turns: `{row.get('reference_turns', 0)}`",
                ],
            }
        )
    return filed_outputs


def _build_shadow_failure_taxonomy_filed_outputs(shadow_payload: dict) -> list[dict]:
    taxonomy = _build_shadow_failure_taxonomy_payload(
        shadow_payload,
        source_mode="compiled_shadow_report",
    )
    summary = dict(taxonomy.get("summary", {}))
    issue_buckets = list(taxonomy.get("issue_buckets", []))
    conversation_hotspots = list(taxonomy.get("conversation_hotspots", []))
    recommended_next_actions = list(taxonomy.get("recommended_next_actions", []))

    issue_lines = [
        f"`{row.get('label', 'unknown')}` x{row.get('count', 0)} ({row.get('severity', 'unknown')})"
        for row in issue_buckets
    ]
    hotspot_lines = [
        (
            f"`{row.get('conversation_id', 'unknown')}` friction `{row.get('friction_count', 0)}` "
            f"(rejected `{row.get('rejected_writes', 0)}`, skipped `{row.get('skipped_turns', 0)}`)"
        )
        for row in conversation_hotspots[:3]
    ]
    next_action_lines = [
        f"`{row.get('label', 'unknown')}`: {row.get('rationale', '')}"
        for row in recommended_next_actions
    ]
    return [
        {
            "title": "Spark Shadow Failure Taxonomy",
            "slug": "spark-shadow-failure-taxonomy",
            "question": "What are the main Spark shadow replay failure modes right now?",
            "answer": (
                f"The current replay batch has {summary.get('rejected_writes', 0)} rejected writes and "
                f"{summary.get('skipped_turns', 0)} skipped turns, led by "
                f"`{summary.get('dominant_unsupported_reason') or 'no dominant unsupported reason'}`."
            ),
            "explanation": (
                "This filed output turns the replay diagnostics into a compact operator-facing failure dossier "
                "inside the KB so the visible vault carries both the memory state and the current integration gaps."
            ),
            "memory_role": "shadow_report",
            "provenance": [
                *([f"Issue bucket: {line}" for line in issue_lines] or ["Issue bucket: none recorded."]),
                *([f"Conversation hotspot: {line}" for line in hotspot_lines] or ["Conversation hotspot: none recorded."]),
                *([f"Next action: {line}" for line in next_action_lines] or ["Next action: none recorded."]),
            ],
        }
    ]


def _build_shadow_turn_audit_payload(shadow_payload: dict, *, top_n: int = 20) -> dict:
    evaluations = list(shadow_payload.get("evaluations", []))
    turn_rows = _extract_shadow_turn_rows(evaluations)

    rejected_user_turns = [
        row for row in turn_rows if row["role"] == "user" and row["action"] == "rejected_write"
    ]
    skipped_user_turns = [
        row for row in turn_rows if row["role"] == "user" and str(row["action"]).startswith("skipped_")
    ]
    skipped_duplicate_user_turns = [
        row for row in skipped_user_turns if str(row.get("unsupported_reason") or "").strip() == "unchanged_current_state"
    ]
    skipped_assistant_turns = [
        row for row in turn_rows if row["role"] == "assistant" and str(row["action"]).startswith("skipped_")
    ]
    skipped_turns = [row for row in turn_rows if str(row["action"]).startswith("skipped_")]
    reference_turns = [row for row in turn_rows if row["action"] == "reference_turn"]
    accepted_user_turns = [row for row in turn_rows if row["role"] == "user" and row["accepted"]]

    def _rank_key(row: dict) -> tuple[str, str, str]:
        return (
            str(row.get("unsupported_reason") or ""),
            str(row.get("conversation_id") or ""),
            str(row.get("message_id") or ""),
        )

    rejected_user_turns = sorted(rejected_user_turns, key=_rank_key)
    skipped_user_turns = sorted(skipped_user_turns, key=_rank_key)
    skipped_duplicate_user_turns = sorted(skipped_duplicate_user_turns, key=_rank_key)
    skipped_assistant_turns = sorted(skipped_assistant_turns, key=_rank_key)
    skipped_turns = sorted(skipped_turns, key=_rank_key)
    reference_turns = sorted(reference_turns, key=_rank_key)
    accepted_user_turns = sorted(accepted_user_turns, key=_rank_key)

    return {
        "summary": {
            "turn_count": len(turn_rows),
            "accepted_user_turn_count": len(accepted_user_turns),
            "rejected_user_turn_count": len(rejected_user_turns),
            "skipped_turn_count": len(skipped_turns),
            "skipped_user_turn_count": len(skipped_user_turns),
            "skipped_duplicate_user_turn_count": len(skipped_duplicate_user_turns),
            "skipped_assistant_turn_count": len(skipped_assistant_turns),
            "reference_turn_count": len(reference_turns),
        },
        "top_rejected_user_turns": rejected_user_turns[:top_n],
        "top_skipped_user_turns": skipped_user_turns[:top_n],
        "top_skipped_duplicate_user_turns": skipped_duplicate_user_turns[:top_n],
        "top_skipped_assistant_turns": skipped_assistant_turns[:top_n],
        "top_skipped_turns": skipped_turns[:top_n],
        "top_reference_turns": reference_turns[:top_n],
        "top_accepted_user_turns": accepted_user_turns[:top_n],
        "trace": {
            "operation": "build_shadow_turn_audit",
            "top_n": top_n,
        },
    }


def _extract_shadow_turn_rows(evaluations: list[dict]) -> list[dict]:
    turn_rows: list[dict] = []
    for evaluation in evaluations:
        if not isinstance(evaluation, dict):
            continue
        conversation_id = str(evaluation.get("conversation_id") or "unknown")
        session_id = str(evaluation.get("session_id") or conversation_id)
        trace_payload = evaluation.get("trace", {})
        if not isinstance(trace_payload, dict):
            continue
        raw_turn_traces = trace_payload.get("turn_traces", [])
        if not isinstance(raw_turn_traces, list):
            continue
        for item in raw_turn_traces:
            if not isinstance(item, dict):
                continue
            trace = item.get("trace", {})
            trace = trace if isinstance(trace, dict) else {}
            write_trace = trace.get("write_trace", {})
            write_trace = write_trace if isinstance(write_trace, dict) else {}
            turn_rows.append(
                {
                    "conversation_id": conversation_id,
                    "session_id": session_id,
                    "message_id": str(item.get("message_id") or ""),
                    "turn_id": str(item.get("turn_id") or ""),
                    "role": str(item.get("role") or ""),
                    "action": str(item.get("action") or ""),
                    "accepted": bool(item.get("accepted", False)),
                    "unsupported_reason": (
                        str(item.get("unsupported_reason"))
                        if item.get("unsupported_reason") is not None
                        else None
                    ),
                    "content": str(trace.get("content") or ""),
                    "timestamp": str(trace.get("timestamp") or ""),
                    "source_event_type": str(trace.get("source_event_type") or ""),
                    "method": str(trace.get("method") or ""),
                    "reason": str(trace.get("reason") or ""),
                    "query_kind": str(trace.get("query_kind") or ""),
                    "bridge_mode": str(trace.get("bridge_mode") or ""),
                    "routing_decision": str(trace.get("routing_decision") or ""),
                    "memory_role": str(trace.get("memory_role") or ""),
                    "record_count": int(trace.get("record_count", 0) or 0),
                    "read_outcome": str(trace.get("read_outcome") or ""),
                    "retrieval_operation": str(trace.get("retrieval_operation") or ""),
                    "contract_reason": str(trace.get("contract_reason") or ""),
                    "observed_memory_role": str(trace.get("observed_memory_role") or ""),
                    "explanation_text": str(trace.get("explanation_text") or ""),
                    "predicate": str(trace.get("predicate") or ""),
                    "predicate_prefix": str(trace.get("predicate_prefix") or ""),
                    "question": str(trace.get("question") or ""),
                    "query": str(trace.get("query") or ""),
                    "subject": str(trace.get("subject") or ""),
                    "write_kind": str(write_trace.get("write_kind") or ""),
                    "write_operation": str(write_trace.get("write_operation") or ""),
                    "persisted": bool(write_trace.get("persisted", False)),
                }
            )
    return turn_rows


def _build_shadow_turn_audit_filed_outputs(shadow_payload: dict, *, top_n: int = 10) -> list[dict]:
    audit = _build_shadow_turn_audit_payload(shadow_payload, top_n=top_n)
    rejected_turns = list(audit.get("top_rejected_user_turns", []))
    skipped_user_turns = list(audit.get("top_skipped_user_turns", []))
    skipped_duplicate_user_turns = list(audit.get("top_skipped_duplicate_user_turns", []))
    skipped_assistant_turns = list(audit.get("top_skipped_assistant_turns", []))
    skipped_turns = list(audit.get("top_skipped_turns", []))
    reference_turns = list(audit.get("top_reference_turns", []))
    accepted_turns = list(audit.get("top_accepted_user_turns", []))
    summary = dict(audit.get("summary", {}))

    rejected_lines = [
        (
            f"`{row.get('conversation_id', 'unknown')}` `{row.get('message_id', 'unknown')}` "
            f"reason `{row.get('unsupported_reason') or 'unknown'}`: {row.get('content', '')}"
        )
        for row in rejected_turns
    ]
    skipped_lines = [
        (
            f"`{row.get('conversation_id', 'unknown')}` `{row.get('message_id', 'unknown')}` "
            f"role `{row.get('role', 'unknown')}` skipped: {row.get('content', '')}"
        )
        for row in skipped_turns
    ]
    skipped_user_lines = [
        (
            f"`{row.get('conversation_id', 'unknown')}` `{row.get('message_id', 'unknown')}` "
            f"reason `{row.get('unsupported_reason') or 'unknown'}` skipped user write: {row.get('content', '')}"
        )
        for row in skipped_user_turns
    ]
    skipped_duplicate_user_lines = [
        (
            f"`{row.get('conversation_id', 'unknown')}` `{row.get('message_id', 'unknown')}` "
            f"duplicate `{row.get('unsupported_reason') or 'unknown'}`: {row.get('content', '')}"
        )
        for row in skipped_duplicate_user_turns
    ]
    skipped_assistant_lines = [
        (
            f"`{row.get('conversation_id', 'unknown')}` `{row.get('message_id', 'unknown')}` "
            f"assistant skipped `{row.get('action', 'unknown')}`: {row.get('content', '')}"
        )
        for row in skipped_assistant_turns
    ]
    reference_lines = [
        (
            f"`{row.get('conversation_id', 'unknown')}` `{row.get('message_id', 'unknown')}` "
            f"role `{row.get('role', 'unknown')}` reference: {row.get('content', '')}"
        )
        for row in reference_turns
    ]
    accepted_lines = [
        (
            f"`{row.get('conversation_id', 'unknown')}` `{row.get('message_id', 'unknown')}` "
            f"accepted `{row.get('write_kind', 'unknown')}`: {row.get('content', '')}"
        )
        for row in accepted_turns
    ]
    return [
        {
            "title": "Spark Shadow Turn Audit",
            "slug": "spark-shadow-turn-audit",
            "question": "Which Spark shadow turns are being accepted, rejected, or skipped right now?",
            "answer": (
                f"The current replay includes {summary.get('rejected_user_turn_count', 0)} rejected user turns, "
                f"{summary.get('skipped_user_turn_count', 0)} skipped user turns plus "
                f"{summary.get('skipped_assistant_turn_count', 0)} skipped assistant turns, and "
                f"{summary.get('reference_turn_count', 0)} reference turns, plus "
                f"{summary.get('accepted_user_turn_count', 0)} accepted user turns."
            ),
            "explanation": (
                "This filed output lists concrete turn-level examples so operators can inspect which Telegram or Spark "
                "messages are failing structured memory extraction instead of reasoning only from aggregate counts."
            ),
            "memory_role": "shadow_report",
            "provenance": [
                *([f"Rejected turn: {line}" for line in rejected_lines] or ["Rejected turn: none recorded."]),
                *([f"Skipped user turn: {line}" for line in skipped_user_lines] or ["Skipped user turn: none recorded."]),
                *(
                    [f"Skipped duplicate user turn: {line}" for line in skipped_duplicate_user_lines]
                    or ["Skipped duplicate user turn: none recorded."]
                ),
                *(
                    [f"Skipped assistant turn: {line}" for line in skipped_assistant_lines]
                    or ["Skipped assistant turn: none recorded."]
                ),
                *([f"Skipped turn: {line}" for line in skipped_lines] or ["Skipped turn: none recorded."]),
                *([f"Reference turn: {line}" for line in reference_lines] or ["Reference turn: none recorded."]),
                *([f"Accepted turn: {line}" for line in accepted_lines] or ["Accepted turn: none recorded."]),
            ],
        }
    ]


def _build_shadow_failure_taxonomy_payload(
    shadow_payload: dict,
    *,
    source_mode: str,
    source_file: str | None = None,
    source_dir: str | None = None,
    source_files: list[str] | None = None,
    source_reports: list[dict] | None = None,
    contract: dict | None = None,
) -> dict:
    report = dict(shadow_payload.get("report", {}))
    summary = dict(report.get("summary", {}))
    conversation_rows = list(report.get("conversation_rows", []))
    probe_rows = list(summary.get("probe_rows", []))
    unsupported_reasons = list(summary.get("unsupported_reasons", []))
    turn_rows = _extract_shadow_turn_rows(list(shadow_payload.get("evaluations", [])))
    source_reports = list(source_reports or [])
    source_files = list(source_files or [])

    accepted_writes = int(summary.get("accepted_writes", 0) or 0)
    rejected_writes = int(summary.get("rejected_writes", 0) or 0)
    skipped_turns = int(summary.get("skipped_turns", 0) or 0)
    reference_turns = int(summary.get("reference_turns", 0) or 0)
    total_turns = int(summary.get("total_turns", accepted_writes + rejected_writes + skipped_turns + reference_turns) or 0)
    residue_reasons = {"low_signal_residue", "non_memory_chat"}
    duplicate_churn_reasons = {"unchanged_current_state"}
    promotion_policy_reasons = {"missing_policy_row", "missing_policy_decision", "defer", "block"}
    residue_reason_rows = [
        row for row in unsupported_reasons if str(row.get("reason") or "").strip() in residue_reasons
    ]
    duplicate_churn_rows = [
        row for row in unsupported_reasons if str(row.get("reason") or "").strip() in duplicate_churn_reasons
    ]
    structured_gap_reason_rows = [
        row
        for row in unsupported_reasons
        if str(row.get("reason") or "").strip() not in residue_reasons | duplicate_churn_reasons | promotion_policy_reasons
    ]
    unsupported_total = sum(int(row.get("count", 0) or 0) for row in unsupported_reasons)
    residue_total = sum(int(row.get("count", 0) or 0) for row in residue_reason_rows)
    duplicate_churn_total = sum(int(row.get("count", 0) or 0) for row in duplicate_churn_rows)
    duplicate_churn_issue_threshold = 5
    has_material_duplicate_churn = duplicate_churn_total >= duplicate_churn_issue_threshold
    structured_gap_total = sum(int(row.get("count", 0) or 0) for row in structured_gap_reason_rows)
    gate_skip_total = max(skipped_turns - residue_total - duplicate_churn_total, 0)
    probe_quality_rows = [
        row
        for row in probe_rows
        if float(row.get("hit_rate", 0.0) or 0.0) < 1.0
        or float(row.get("expected_match_rate", 1.0) or 1.0) < 1.0
    ]
    probe_expectation_gap_rows = [
        row for row in probe_rows if float(row.get("expected_match_rate", 1.0) or 1.0) < 1.0
    ]

    def _normalized_read_abstention_reason(row: dict) -> str:
        reason = str(row.get("reason") or "").strip()
        contract_reason = str(row.get("contract_reason") or "").strip()
        read_outcome = str(row.get("read_outcome") or "").strip()
        if reason:
            return reason
        if contract_reason:
            return contract_reason
        if read_outcome == "no_supported_answer":
            return "no_supported_answer"
        return "unknown"

    read_abstention_rows = [
        row
        for row in turn_rows
        if row.get("action") == "reference_turn"
        and row.get("role") == "assistant"
        and str(row.get("source_event_type") or "").strip() == "memory_read_abstained"
    ]
    read_success_rows = [
        row
        for row in turn_rows
        if row.get("action") == "reference_turn"
        and row.get("role") == "assistant"
        and str(row.get("source_event_type") or "").strip() == "memory_read_succeeded"
    ]
    read_abstention_gap_rows: list[dict] = []
    read_coverage_gap_rows: list[dict] = []
    for row in read_abstention_rows:
        normalized_reason = _normalized_read_abstention_reason(row)
        if normalized_reason == "no_supported_answer":
            read_coverage_gap_rows.append(row)
        else:
            read_abstention_gap_rows.append(row)
    read_abstention_by_reason: dict[str, int] = {}
    read_abstention_by_method: dict[str, int] = {}
    read_success_by_method: dict[str, int] = {}
    for row in read_abstention_rows:
        reason = _normalized_read_abstention_reason(row)
        method = str(row.get("method") or "").strip() or "unknown"
        read_abstention_by_reason[reason] = read_abstention_by_reason.get(reason, 0) + 1
        read_abstention_by_method[method] = read_abstention_by_method.get(method, 0) + 1
    for row in read_success_rows:
        method = str(row.get("method") or "").strip() or "unknown"
        read_success_by_method[method] = read_success_by_method.get(method, 0) + 1
    read_abstention_reason_rows = [
        {"reason": reason, "count": count}
        for reason, count in sorted(read_abstention_by_reason.items(), key=lambda item: (-item[1], item[0]))
    ]
    read_abstention_method_rows = [
        {"method": method, "count": count}
        for method, count in sorted(read_abstention_by_method.items(), key=lambda item: (-item[1], item[0]))
    ]
    read_success_method_rows = [
        {"method": method, "count": count}
        for method, count in sorted(read_success_by_method.items(), key=lambda item: (-item[1], item[0]))
    ]
    dominant_read_abstention_row = read_abstention_reason_rows[0] if read_abstention_reason_rows else None
    dominant_read_abstention_method_row = read_abstention_method_rows[0] if read_abstention_method_rows else None
    dominant_read_success_method_row = read_success_method_rows[0] if read_success_method_rows else None
    read_abstention_gap_reason_rows = [
        row for row in read_abstention_reason_rows if str(row.get("reason") or "").strip() != "no_supported_answer"
    ]
    dominant_read_gap_row = read_abstention_gap_reason_rows[0] if read_abstention_gap_reason_rows else None
    read_only_replay_gap = not probe_rows and accepted_writes == 0 and bool(read_success_rows)
    dominant_unsupported_row = max(
        unsupported_reasons,
        key=lambda row: (int(row.get("count", 0) or 0), str(row.get("reason", "") or "")),
        default=None,
    )
    dominant_structured_gap_row = max(
        structured_gap_reason_rows,
        key=lambda row: (int(row.get("count", 0) or 0), str(row.get("reason", "") or "")),
        default=None,
    )

    conversation_hotspots = sorted(
        [
            {
                **dict(row),
                "friction_count": int(row.get("rejected_writes", 0) or 0) + int(row.get("skipped_turns", 0) or 0),
                "friction_rate": round(
                    (
                        int(row.get("rejected_writes", 0) or 0) + int(row.get("skipped_turns", 0) or 0)
                    )
                    / max(
                        1,
                        int(row.get("accepted_writes", 0) or 0)
                        + int(row.get("rejected_writes", 0) or 0)
                        + int(row.get("skipped_turns", 0) or 0),
                    ),
                    4,
                ),
            }
            for row in conversation_rows
        ],
        key=lambda row: (
            int(row.get("friction_count", 0) or 0),
            int(row.get("rejected_writes", 0) or 0),
            int(row.get("skipped_turns", 0) or 0),
            str(row.get("conversation_id", "") or ""),
        ),
        reverse=True,
    )

    source_hotspots = sorted(
        [
            {
                **dict(row),
                "friction_count": int(row.get("summary", {}).get("rejected_writes", 0) or 0)
                + int(row.get("summary", {}).get("skipped_turns", 0) or 0),
                "accepted_writes": int(row.get("summary", {}).get("accepted_writes", 0) or 0),
                "rejected_writes": int(row.get("summary", {}).get("rejected_writes", 0) or 0),
                "skipped_turns": int(row.get("summary", {}).get("skipped_turns", 0) or 0),
                "reference_turns": int(row.get("summary", {}).get("reference_turns", 0) or 0),
            }
            for row in source_reports
        ],
        key=lambda row: (
            int(row.get("friction_count", 0) or 0),
            int(row.get("rejected_writes", 0) or 0),
            int(row.get("skipped_turns", 0) or 0),
            str(row.get("file", "") or ""),
        ),
        reverse=True,
    )

    issue_buckets: list[dict] = []
    if rejected_writes:
        issue_buckets.append(
            {
                "label": "write_rejection",
                "count": rejected_writes,
                "severity": "high",
                "summary": f"{rejected_writes} turns were rejected by governed memory writes.",
            }
        )
    if gate_skip_total:
        issue_buckets.append(
            {
                "label": "role_scope_gap",
                "count": gate_skip_total,
                "severity": "medium",
                "summary": (
                    f"{gate_skip_total} turns were skipped before persistence by writable-role or "
                    "promotion-policy gates."
                ),
            }
        )
    if residue_total:
        issue_buckets.append(
            {
                "label": "residue_quarantine",
                "count": residue_total,
                "severity": "low",
                "summary": (
                    f"{residue_total} low-signal turns were quarantined as conversational residue instead of "
                    "being treated as failed memory writes."
                ),
            }
        )
    if has_material_duplicate_churn:
        issue_buckets.append(
            {
                "label": "duplicate_write_churn",
                "count": duplicate_churn_total,
                "severity": "medium",
                "summary": (
                    f"{duplicate_churn_total} writes were skipped because the governed current-state value already "
                    "matched the incoming value."
                ),
            }
        )
    if structured_gap_total:
        issue_buckets.append(
            {
                "label": "structured_extraction_gap",
                "count": structured_gap_total,
                "severity": "high",
                "summary": (
                    f"{structured_gap_total} turns were rejected for unsupported reasons, led by "
                    f"`{(dominant_structured_gap_row or {}).get('reason', 'unknown')}`."
                ),
            }
        )
    if read_only_replay_gap:
        issue_buckets.append(
            {
                "label": "read_only_replay_gap",
                "count": len(read_success_rows),
                "severity": "medium",
                "summary": (
                    f"{len(read_success_rows)} Builder memory reads succeeded, but the replay cohort contains no "
                    "supporting writes, so retrieval probes cannot be validated from this slice alone."
                ),
            }
        )
    elif not probe_rows:
        issue_buckets.append(
            {
                "label": "probe_coverage_gap",
                "count": report.get("run_count", 0),
                "severity": "medium",
                "summary": "No shadow probes were present, so retrieval quality is not being measured yet.",
            }
        )
    elif probe_quality_rows:
        issue_buckets.append(
            {
                "label": "probe_quality_gap",
                "count": len(probe_quality_rows),
                "severity": "high",
                "summary": (
                    "At least one probe type is missing hits or returning values that do not match the "
                    "expected replay target."
                ),
            }
        )
    if read_abstention_gap_rows:
        issue_buckets.append(
            {
                "label": "read_abstention_gap",
                "count": len(read_abstention_gap_rows),
                "severity": "high" if str((dominant_read_gap_row or {}).get("reason") or "") == "sdk_unavailable" else "medium",
                "summary": (
                    f"{len(read_abstention_gap_rows)} Builder memory reads abstained because of read-path gaps, led by "
                    f"`{(dominant_read_gap_row or {}).get('reason', 'unknown')}`."
                ),
            }
        )
    if read_coverage_gap_rows:
        issue_buckets.append(
            {
                "label": "read_coverage_gap",
                "count": len(read_coverage_gap_rows),
                "severity": "medium",
                "summary": (
                    f"{len(read_coverage_gap_rows)} Builder memory reads completed without a supported answer. "
                    "That indicates missing memory coverage rather than a broken read path."
                ),
            }
        )

    recommended_next_actions: list[dict] = []
    if dominant_unsupported_row is not None:
        reason = str(dominant_unsupported_row.get("reason", "") or "")
        if reason in {"low_signal_residue", "non_memory_chat"}:
            recommended_next_actions.append(
                {
                    "label": "confirm_residue_quarantine",
                    "priority": 1,
                    "rationale": (
                        "The dominant skipped reason is quarantined non-memory residue. Confirm the residue gate "
                        "stays conservative and does not suppress real memory-worthy user facts."
                    ),
                }
            )
        elif reason == "unchanged_current_state" and has_material_duplicate_churn:
            recommended_next_actions.append(
                {
                    "label": "confirm_duplicate_write_suppression",
                    "priority": 1,
                    "rationale": (
                        "The dominant skipped reason is unchanged current state. Confirm that repeat Builder writes "
                        "are being collapsed intentionally and that true state transitions still persist."
                    ),
                }
            )
        elif reason == "no_structured_memory_extracted":
            recommended_next_actions.append(
                {
                    "label": "improve_structured_write_extraction",
                    "priority": 1,
                    "rationale": (
                        "The dominant rejection mode is missing structured memory extraction. Spark Builder exports "
                        "should emit clearer subject, predicate, value, or write-intent metadata for memory-worthy turns."
                    ),
                }
            )
        else:
            recommended_next_actions.append(
                {
                    "label": "investigate_dominant_unsupported_reason",
                    "priority": 1,
                    "rationale": f"The dominant unsupported reason is `{reason}` and should be mapped to a concrete Spark-side fix.",
                }
            )
    if gate_skip_total:
        recommended_next_actions.append(
            {
                "label": "confirm_writable_role_policy",
                "priority": 2,
                "rationale": (
                    "Skipped turns are currently being filtered before persistence by writable-role or promotion "
                    "policy. Confirm that this is intended and not masking real user-memory opportunities."
                ),
            }
        )
    if read_only_replay_gap:
        recommended_next_actions.append(
            {
                "label": "materialize_supporting_write_history",
                "priority": 3,
                "rationale": (
                    "This replay slice contains successful read traffic but no accepted writes. Widen the Builder "
                    "cohort or materialize the supporting write history before judging retrieval quality from probes."
                ),
            }
        )
    elif not probe_rows:
        recommended_next_actions.append(
            {
                "label": "add_shadow_probes",
                "priority": 3,
                "rationale": (
                    "No probes were exported, so the replay only measures write acceptance. Add current_state, evidence, "
                    "or historical_state probes to measure retrieval quality."
                ),
            }
        )
    elif probe_expectation_gap_rows:
        recommended_next_actions.append(
            {
                "label": "investigate_probe_value_mismatches",
                "priority": 3,
                "rationale": (
                    "Probe coverage exists, but at least one probe type is returning non-expected values. "
                    "Inspect replay ordering, recency resolution, and evidence selection before calling retrieval healthy."
                ),
            }
        )
    if dominant_read_gap_row is not None:
        reason = str(dominant_read_gap_row.get("reason") or "")
        if reason == "supported_fact_unanswered":
            recommended_next_actions.append(
                {
                    "label": "fix_supported_read_answer_materialization",
                    "priority": 2,
                    "rationale": (
                        "Builder reported no supported answer even though replay already has governed memory for "
                        "the requested fact. Trace the read contract and answer-materialization path before calling "
                        "this a memory coverage issue."
                    ),
                }
            )
        elif reason == "sdk_unavailable":
            recommended_next_actions.append(
                {
                    "label": "restore_memory_read_sdk_availability",
                    "priority": 2,
                    "rationale": (
                        "Builder memory reads are abstaining because the SDK is unavailable. Restore live SDK "
                        "availability before using read-side traffic as a memory quality signal."
                    ),
                }
            )
        elif reason == "invalid_request":
            recommended_next_actions.append(
                {
                    "label": "fix_memory_read_request_shape",
                    "priority": 2,
                    "rationale": (
                        "Builder memory reads are abstaining because the request shape is invalid. Normalize subject, "
                        "predicate, and retrieval parameters before routing the read."
                    ),
                }
            )
        elif reason == "invalid_memory_role":
            recommended_next_actions.append(
                {
                    "label": "fix_memory_read_role_routing",
                    "priority": 2,
                    "rationale": (
                        "Builder memory reads are abstaining because the requested memory role is invalid. Tighten "
                        "role selection before issuing retrieval calls."
                    ),
                }
            )
        else:
            if reason == "unknown" and dominant_read_abstention_method_row is not None:
                recommended_next_actions.append(
                    {
                        "label": "investigate_read_abstention_method",
                        "priority": 2,
                        "rationale": (
                            f"Builder memory reads are abstaining without a reason code; the dominant abstention method "
                            f"is `{dominant_read_abstention_method_row.get('method')}` and should be traced to the "
                            "request builder or SDK contract path."
                        ),
                    }
                )
            else:
                recommended_next_actions.append(
                    {
                        "label": "investigate_read_abstention_reason",
                        "priority": 2,
                        "rationale": (
                            f"Builder memory reads are abstaining for `{reason}` and should be mapped to a concrete "
                            "read-side fix."
                        ),
                    }
                )
    if read_coverage_gap_rows:
        recommended_next_actions.append(
            {
                "label": "expand_memory_coverage_for_read_queries",
                "priority": 3,
                "rationale": (
                    "Builder read traffic is reaching the SDK but returning no supported answer. Add the missing "
                    "profile facts and supporting evidence before treating read-side UX as healthy."
                ),
            }
        )
    top_source_hotspot = source_hotspots[0] if source_hotspots else None
    if top_source_hotspot and int(top_source_hotspot.get("friction_count", 0) or 0) > 0:
        recommended_next_actions.append(
            {
                "label": "inspect_hottest_source_file",
                "priority": 4,
                "rationale": (
                    f"The hottest file is `{top_source_hotspot.get('file')}` with "
                    f"{top_source_hotspot.get('friction_count', 0)} rejected-or-skipped turns."
                ),
            }
        )

    issue_labels = [str(bucket["label"]) for bucket in issue_buckets]
    return {
        "contract": dict(contract or {}),
        "source_mode": source_mode,
        "source_file": source_file,
        "source_dir": source_dir,
        "source_files": source_files,
        "summary": {
            "run_count": int(report.get("run_count", 0) or 0),
            "accepted_writes": accepted_writes,
            "rejected_writes": rejected_writes,
            "skipped_turns": skipped_turns,
            "reference_turns": reference_turns,
            "total_turns": total_turns,
            "accepted_rate": float(summary.get("accepted_rate", 0.0) or 0.0),
            "rejected_rate": float(summary.get("rejected_rate", 0.0) or 0.0),
            "skipped_rate": float(summary.get("skipped_rate", 0.0) or 0.0),
            "reference_rate": float(summary.get("reference_rate", 0.0) or 0.0),
            "unsupported_reason_count": unsupported_total,
            "unsupported_reason_types": len(unsupported_reasons),
            "dominant_unsupported_reason": (
                str(dominant_unsupported_row.get("reason")) if dominant_unsupported_row else None
            ),
            "dominant_unsupported_reason_count": (
                int(dominant_unsupported_row.get("count", 0) or 0) if dominant_unsupported_row else 0
            ),
            "read_abstention_count": len(read_abstention_rows),
            "read_success_count": len(read_success_rows),
            "dominant_read_abstention_reason": (
                str(dominant_read_abstention_row.get("reason")) if dominant_read_abstention_row else None
            ),
            "dominant_read_abstention_method": (
                str(dominant_read_abstention_method_row.get("method")) if dominant_read_abstention_method_row else None
            ),
            "dominant_read_success_method": (
                str(dominant_read_success_method_row.get("method")) if dominant_read_success_method_row else None
            ),
            "read_abstention_gap_count": len(read_abstention_gap_rows),
            "read_coverage_gap_count": len(read_coverage_gap_rows),
            "has_probe_coverage": bool(probe_rows),
            "has_probe_expectation_gap": bool(probe_expectation_gap_rows),
            "issue_labels": issue_labels,
        },
        "issue_buckets": issue_buckets,
        "unsupported_reasons": unsupported_reasons,
        "read_abstention_reasons": read_abstention_reason_rows,
        "read_abstention_methods": read_abstention_method_rows,
        "read_success_methods": read_success_method_rows,
        "probe_rows": probe_rows,
        "conversation_hotspots": conversation_hotspots,
        "source_hotspots": source_hotspots,
        "recommended_next_actions": recommended_next_actions,
        "trace": {
            "operation": "build_shadow_failure_taxonomy",
            "source_mode": source_mode,
        },
    }


def _build_spark_kb_from_shadow_replay(
    data_file: str,
    output_dir: str,
    *,
    repo_sources: list[str] | None = None,
    repo_source_manifest_files: list[str] | None = None,
) -> dict:
    evaluations, adapter = _execute_shadow_replay(data_file)
    shadow_payload = _build_shadow_report_payload_from_evaluations(evaluations)
    snapshot = adapter.sdk.export_knowledge_base_snapshot()
    resolved_repo_sources = _resolve_repo_source_files(
        repo_sources=repo_sources,
        repo_source_manifest_files=repo_source_manifest_files,
    )
    compile_result = scaffold_spark_knowledge_base(
        output_dir,
        snapshot,
        vault_title="Spark Shadow Knowledge Base",
        repo_sources=resolved_repo_sources,
        filed_outputs=_build_shadow_report_filed_outputs(shadow_payload)
        + _build_shadow_failure_taxonomy_filed_outputs(shadow_payload),
    )
    health_report = build_spark_kb_health_report(output_dir)
    return {
        "source_file": str(Path(data_file)),
        "contract": build_spark_integration_contract_summary(),
        "shadow_report": shadow_payload["report"],
        "snapshot": snapshot,
        "repo_source_manifest_file_count": len(list(repo_source_manifest_files or [])),
        "compile_result": compile_result,
        "health_report": health_report,
    }


def _build_spark_kb_from_shadow_replay_batch(
    data_dir: str,
    output_dir: str,
    *,
    glob_pattern: str = "*.json",
    repo_sources: list[str] | None = None,
    repo_source_manifest_files: list[str] | None = None,
) -> dict:
    root = Path(data_dir)
    files = sorted(path for path in root.glob(glob_pattern) if path.is_file())
    if not files:
        raise ValueError(f"No shadow replay files matched '{glob_pattern}' in {root}.")

    adapter: SparkShadowIngestAdapter | None = None
    all_evaluations = []
    source_reports = []
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        evaluations, adapter = _execute_shadow_replay_payload(payload, adapter=adapter)
        source_payload = _build_shadow_report_payload_from_evaluations(evaluations)
        source_reports.append(
            {
                "file": str(path),
                "run_count": source_payload["report"]["run_count"],
                "summary": source_payload["report"]["summary"],
            }
        )
        all_evaluations.extend(evaluations)

    shadow_payload = _build_shadow_report_payload_from_evaluations(all_evaluations)
    if adapter is None:
        raise ValueError(f"No shadow replay files matched '{glob_pattern}' in {root}.")
    snapshot = adapter.sdk.export_knowledge_base_snapshot()
    resolved_repo_sources = _resolve_repo_source_files(
        repo_sources=repo_sources,
        repo_source_manifest_files=repo_source_manifest_files,
    )
    compile_result = scaffold_spark_knowledge_base(
        output_dir,
        snapshot,
        vault_title="Spark Shadow Batch Knowledge Base",
        repo_sources=resolved_repo_sources,
        filed_outputs=_build_shadow_report_filed_outputs(shadow_payload)
        + _build_shadow_failure_taxonomy_filed_outputs(shadow_payload),
    )
    health_report = build_spark_kb_health_report(output_dir)
    return {
        "source_dir": str(root),
        "source_files": [str(path) for path in files],
        "source_reports": source_reports,
        "contract": build_spark_integration_contract_summary(),
        "shadow_report": shadow_payload["report"],
        "snapshot": snapshot,
        "repo_source_manifest_file_count": len(list(repo_source_manifest_files or [])),
        "compile_result": compile_result,
        "health_report": health_report,
    }


def _validate_shadow_replay_payload(data_file: str) -> dict:
    payload = json.loads(Path(data_file).read_text(encoding="utf-8"))
    summary = validate_shadow_replay_payload(payload)
    summary["file"] = str(Path(data_file))
    return summary


def _normalize_builder_shadow_export(data_file: str) -> dict:
    source_path = Path(data_file)
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    normalized_payload = normalize_builder_shadow_export_payload(payload)
    validation = validate_shadow_replay_payload(normalized_payload)
    return {
        "file": str(source_path),
        "contract": build_builder_shadow_adapter_contract_summary(),
        "normalized": normalized_payload,
        "validation": validation,
    }


def _normalize_builder_shadow_export_batch(data_dir: str, *, glob_pattern: str = "*.json") -> dict:
    root = Path(data_dir)
    files = sorted(path for path in root.glob(glob_pattern) if path.is_file())
    if not files:
        raise ValueError(f"No builder export files matched '{glob_pattern}' in {root}.")

    source_normalizations = [_normalize_builder_shadow_export(str(path)) for path in files]
    invalid_files = [item["file"] for item in source_normalizations if not item["validation"]["valid"]]
    total_errors = sum(len(item["validation"]["errors"]) for item in source_normalizations)
    total_warnings = sum(len(item["validation"]["warnings"]) for item in source_normalizations)
    return {
        "contract": build_builder_shadow_adapter_contract_summary(),
        "source_dir": str(root),
        "source_files": [str(path) for path in files],
        "file_count": len(source_normalizations),
        "valid": not invalid_files,
        "valid_file_count": len(source_normalizations) - len(invalid_files),
        "invalid_file_count": len(invalid_files),
        "invalid_files": invalid_files,
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "source_normalizations": source_normalizations,
    }


def _normalize_telegram_shadow_export(data_file: str) -> dict:
    source_path = Path(data_file)
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    normalized_payload = normalize_telegram_bot_export_payload(payload)
    validation = validate_shadow_replay_payload(normalized_payload)
    return {
        "file": str(source_path),
        "contract": build_telegram_shadow_adapter_contract_summary(),
        "normalized": normalized_payload,
        "validation": validation,
    }


def _normalize_telegram_shadow_export_batch(data_dir: str, *, glob_pattern: str = "*.json") -> dict:
    root = Path(data_dir)
    files = sorted(path for path in root.glob(glob_pattern) if path.is_file())
    if not files:
        raise ValueError(f"No Telegram export files matched '{glob_pattern}' in {root}.")

    source_normalizations = [_normalize_telegram_shadow_export(str(path)) for path in files]
    invalid_files = [item["file"] for item in source_normalizations if not item["validation"]["valid"]]
    total_errors = sum(len(item["validation"]["errors"]) for item in source_normalizations)
    total_warnings = sum(len(item["validation"]["warnings"]) for item in source_normalizations)
    return {
        "contract": build_telegram_shadow_adapter_contract_summary(),
        "source_dir": str(root),
        "source_files": [str(path) for path in files],
        "file_count": len(source_normalizations),
        "valid": not invalid_files,
        "valid_file_count": len(source_normalizations) - len(invalid_files),
        "invalid_file_count": len(invalid_files),
        "invalid_files": invalid_files,
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "source_normalizations": source_normalizations,
    }


def _load_shadow_report_payload_from_builder_export(data_file: str) -> dict:
    normalized = _normalize_builder_shadow_export(data_file)["normalized"]
    evaluations, _ = _execute_shadow_replay_payload(normalized)
    return _build_shadow_report_payload_from_evaluations(evaluations)


def _load_shadow_report_payload_from_telegram_export(data_file: str) -> dict:
    normalized = _normalize_telegram_shadow_export(data_file)["normalized"]
    evaluations, _ = _execute_shadow_replay_payload(normalized)
    return _build_shadow_report_payload_from_evaluations(evaluations)


def _load_shadow_report_payload_from_builder_export_batch(data_dir: str, *, glob_pattern: str = "*.json") -> dict:
    root = Path(data_dir)
    files = sorted(path for path in root.glob(glob_pattern) if path.is_file())
    if not files:
        raise ValueError(f"No builder export files matched '{glob_pattern}' in {root}.")

    adapter: SparkShadowIngestAdapter | None = None
    all_evaluations = []
    source_reports = []
    for path in files:
        normalized = _normalize_builder_shadow_export(str(path))["normalized"]
        evaluations, adapter = _execute_shadow_replay_payload(normalized, adapter=adapter)
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
    payload["contract"] = build_builder_shadow_adapter_contract_summary()
    payload["source_dir"] = str(root)
    payload["source_files"] = [str(path) for path in files]
    payload["source_reports"] = source_reports
    return payload


def _load_shadow_report_payload_from_telegram_export_batch(data_dir: str, *, glob_pattern: str = "*.json") -> dict:
    root = Path(data_dir)
    files = sorted(path for path in root.glob(glob_pattern) if path.is_file())
    if not files:
        raise ValueError(f"No Telegram export files matched '{glob_pattern}' in {root}.")

    adapter: SparkShadowIngestAdapter | None = None
    all_evaluations = []
    source_reports = []
    for path in files:
        normalized = _normalize_telegram_shadow_export(str(path))["normalized"]
        evaluations, adapter = _execute_shadow_replay_payload(normalized, adapter=adapter)
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
    payload["contract"] = build_telegram_shadow_adapter_contract_summary()
    payload["source_dir"] = str(root)
    payload["source_files"] = [str(path) for path in files]
    payload["source_reports"] = source_reports
    return payload


def _build_shadow_failure_taxonomy_from_builder_export(data_file: str) -> dict:
    payload = _load_shadow_report_payload_from_builder_export(data_file)
    return _build_shadow_failure_taxonomy_payload(
        payload,
        source_mode="builder_export",
        source_file=str(Path(data_file)),
        contract=build_builder_shadow_adapter_contract_summary(),
    )


def _build_shadow_failure_taxonomy_from_builder_export_batch(data_dir: str, *, glob_pattern: str = "*.json") -> dict:
    payload = _load_shadow_report_payload_from_builder_export_batch(data_dir, glob_pattern=glob_pattern)
    return _build_shadow_failure_taxonomy_payload(
        payload,
        source_mode="builder_export_batch",
        source_dir=str(Path(data_dir)),
        source_files=list(payload.get("source_files", [])),
        source_reports=list(payload.get("source_reports", [])),
        contract=build_builder_shadow_adapter_contract_summary(),
    )


def _build_shadow_failure_taxonomy_from_telegram_export(data_file: str) -> dict:
    payload = _load_shadow_report_payload_from_telegram_export(data_file)
    return _build_shadow_failure_taxonomy_payload(
        payload,
        source_mode="telegram_export",
        source_file=str(Path(data_file)),
        contract=build_telegram_shadow_adapter_contract_summary(),
    )


def _build_shadow_failure_taxonomy_from_telegram_export_batch(data_dir: str, *, glob_pattern: str = "*.json") -> dict:
    payload = _load_shadow_report_payload_from_telegram_export_batch(data_dir, glob_pattern=glob_pattern)
    return _build_shadow_failure_taxonomy_payload(
        payload,
        source_mode="telegram_export_batch",
        source_dir=str(Path(data_dir)),
        source_files=list(payload.get("source_files", [])),
        source_reports=list(payload.get("source_reports", [])),
        contract=build_telegram_shadow_adapter_contract_summary(),
    )


def _build_spark_kb_from_builder_export(
    data_file: str,
    output_dir: str,
    *,
    repo_sources: list[str] | None = None,
    repo_source_manifest_files: list[str] | None = None,
) -> dict:
    normalized = _normalize_builder_shadow_export(data_file)["normalized"]
    evaluations, adapter = _execute_shadow_replay_payload(normalized)
    shadow_payload = _build_shadow_report_payload_from_evaluations(evaluations)
    snapshot = adapter.sdk.export_knowledge_base_snapshot()
    resolved_repo_sources = _resolve_repo_source_files(
        repo_sources=repo_sources,
        repo_source_manifest_files=repo_source_manifest_files,
    )
    compile_result = scaffold_spark_knowledge_base(
        output_dir,
        snapshot,
        vault_title="Spark Builder Knowledge Base",
        repo_sources=resolved_repo_sources,
        filed_outputs=_build_shadow_report_filed_outputs(shadow_payload)
        + _build_shadow_failure_taxonomy_filed_outputs(shadow_payload),
    )
    health_report = build_spark_kb_health_report(output_dir)
    return {
        "source_file": str(Path(data_file)),
        "contract": build_builder_shadow_adapter_contract_summary(),
        "normalized_shadow_replay": normalized,
        "shadow_report": shadow_payload["report"],
        "snapshot": snapshot,
        "repo_source_manifest_file_count": len(list(repo_source_manifest_files or [])),
        "compile_result": compile_result,
        "health_report": health_report,
    }


def _build_spark_kb_from_telegram_export(
    data_file: str,
    output_dir: str,
    *,
    repo_sources: list[str] | None = None,
    repo_source_manifest_files: list[str] | None = None,
) -> dict:
    normalized = _normalize_telegram_shadow_export(data_file)["normalized"]
    evaluations, adapter = _execute_shadow_replay_payload(normalized)
    shadow_payload = _build_shadow_report_payload_from_evaluations(evaluations)
    snapshot = adapter.sdk.export_knowledge_base_snapshot()
    resolved_repo_sources = _resolve_repo_source_files(
        repo_sources=repo_sources,
        repo_source_manifest_files=repo_source_manifest_files,
    )
    compile_result = scaffold_spark_knowledge_base(
        output_dir,
        snapshot,
        vault_title="Spark Telegram Knowledge Base",
        repo_sources=resolved_repo_sources,
        filed_outputs=_build_shadow_report_filed_outputs(shadow_payload)
        + _build_shadow_failure_taxonomy_filed_outputs(shadow_payload),
    )
    health_report = build_spark_kb_health_report(output_dir)
    return {
        "source_file": str(Path(data_file)),
        "contract": build_telegram_shadow_adapter_contract_summary(),
        "normalized_shadow_replay": normalized,
        "shadow_report": shadow_payload["report"],
        "snapshot": snapshot,
        "repo_source_manifest_file_count": len(list(repo_source_manifest_files or [])),
        "compile_result": compile_result,
        "health_report": health_report,
    }


def _build_spark_kb_from_builder_export_batch(
    data_dir: str,
    output_dir: str,
    *,
    glob_pattern: str = "*.json",
    repo_sources: list[str] | None = None,
    repo_source_manifest_files: list[str] | None = None,
) -> dict:
    root = Path(data_dir)
    files = sorted(path for path in root.glob(glob_pattern) if path.is_file())
    if not files:
        raise ValueError(f"No builder export files matched '{glob_pattern}' in {root}.")

    adapter: SparkShadowIngestAdapter | None = None
    all_evaluations = []
    source_reports = []
    for path in files:
        normalized = _normalize_builder_shadow_export(str(path))["normalized"]
        evaluations, adapter = _execute_shadow_replay_payload(normalized, adapter=adapter)
        source_payload = _build_shadow_report_payload_from_evaluations(evaluations)
        source_reports.append(
            {
                "file": str(path),
                "run_count": source_payload["report"]["run_count"],
                "summary": source_payload["report"]["summary"],
            }
        )
        all_evaluations.extend(evaluations)

    if adapter is None:
        raise ValueError(f"No builder export files matched '{glob_pattern}' in {root}.")

    shadow_payload = _build_shadow_report_payload_from_evaluations(all_evaluations)
    snapshot = adapter.sdk.export_knowledge_base_snapshot()
    resolved_repo_sources = _resolve_repo_source_files(
        repo_sources=repo_sources,
        repo_source_manifest_files=repo_source_manifest_files,
    )
    compile_result = scaffold_spark_knowledge_base(
        output_dir,
        snapshot,
        vault_title="Spark Builder Batch Knowledge Base",
        repo_sources=resolved_repo_sources,
        filed_outputs=_build_shadow_report_filed_outputs(shadow_payload)
        + _build_shadow_failure_taxonomy_filed_outputs(shadow_payload),
    )
    health_report = build_spark_kb_health_report(output_dir)
    return {
        "source_dir": str(root),
        "source_files": [str(path) for path in files],
        "source_reports": source_reports,
        "contract": build_builder_shadow_adapter_contract_summary(),
        "shadow_report": shadow_payload["report"],
        "snapshot": snapshot,
        "repo_source_manifest_file_count": len(list(repo_source_manifest_files or [])),
        "compile_result": compile_result,
        "health_report": health_report,
    }


def _build_spark_kb_from_telegram_export_batch(
    data_dir: str,
    output_dir: str,
    *,
    glob_pattern: str = "*.json",
    repo_sources: list[str] | None = None,
    repo_source_manifest_files: list[str] | None = None,
) -> dict:
    root = Path(data_dir)
    files = sorted(path for path in root.glob(glob_pattern) if path.is_file())
    if not files:
        raise ValueError(f"No Telegram export files matched '{glob_pattern}' in {root}.")

    adapter: SparkShadowIngestAdapter | None = None
    all_evaluations = []
    source_reports = []
    for path in files:
        normalized = _normalize_telegram_shadow_export(str(path))["normalized"]
        evaluations, adapter = _execute_shadow_replay_payload(normalized, adapter=adapter)
        source_payload = _build_shadow_report_payload_from_evaluations(evaluations)
        source_reports.append(
            {
                "file": str(path),
                "run_count": source_payload["report"]["run_count"],
                "summary": source_payload["report"]["summary"],
            }
        )
        all_evaluations.extend(evaluations)

    if adapter is None:
        raise ValueError(f"No Telegram export files matched '{glob_pattern}' in {root}.")

    shadow_payload = _build_shadow_report_payload_from_evaluations(all_evaluations)
    snapshot = adapter.sdk.export_knowledge_base_snapshot()
    resolved_repo_sources = _resolve_repo_source_files(
        repo_sources=repo_sources,
        repo_source_manifest_files=repo_source_manifest_files,
    )
    compile_result = scaffold_spark_knowledge_base(
        output_dir,
        snapshot,
        vault_title="Spark Telegram Batch Knowledge Base",
        repo_sources=resolved_repo_sources,
        filed_outputs=_build_shadow_report_filed_outputs(shadow_payload)
        + _build_shadow_failure_taxonomy_filed_outputs(shadow_payload),
    )
    health_report = build_spark_kb_health_report(output_dir)
    return {
        "source_dir": str(root),
        "source_files": [str(path) for path in files],
        "source_reports": source_reports,
        "contract": build_telegram_shadow_adapter_contract_summary(),
        "shadow_report": shadow_payload["report"],
        "snapshot": snapshot,
        "repo_source_manifest_file_count": len(list(repo_source_manifest_files or [])),
        "compile_result": compile_result,
        "health_report": health_report,
    }


def _run_spark_builder_intake_batch(
    data_dir: str,
    output_dir: str,
    *,
    glob_pattern: str = "*.json",
    repo_sources: list[str] | None = None,
    repo_source_manifest_files: list[str] | None = None,
) -> dict:
    normalization = _normalize_builder_shadow_export_batch(data_dir, glob_pattern=glob_pattern)
    shadow_report = _load_shadow_report_payload_from_builder_export_batch(data_dir, glob_pattern=glob_pattern)
    failure_taxonomy = _build_shadow_failure_taxonomy_from_builder_export_batch(data_dir, glob_pattern=glob_pattern)
    kb = _build_spark_kb_from_builder_export_batch(
        data_dir,
        output_dir,
        glob_pattern=glob_pattern,
        repo_sources=repo_sources,
        repo_source_manifest_files=repo_source_manifest_files,
    )
    return {
        "source_dir": str(Path(data_dir)),
        "output_dir": str(Path(output_dir)),
        "source_files": list(normalization.get("source_files", [])),
        "contract": build_builder_shadow_adapter_contract_summary(),
        "normalization": normalization,
        "shadow_report": shadow_report["report"],
        "failure_taxonomy": failure_taxonomy,
        "kb": kb,
        "summary": {
            "file_count": int(normalization.get("file_count", 0) or 0),
            "valid_builder_exports": bool(normalization.get("valid", False)),
            "run_count": int(shadow_report.get("report", {}).get("run_count", 0) or 0),
            "accepted_writes": int(shadow_report.get("report", {}).get("summary", {}).get("accepted_writes", 0) or 0),
            "rejected_writes": int(shadow_report.get("report", {}).get("summary", {}).get("rejected_writes", 0) or 0),
            "skipped_turns": int(shadow_report.get("report", {}).get("summary", {}).get("skipped_turns", 0) or 0),
            "reference_turns": int(shadow_report.get("report", {}).get("summary", {}).get("reference_turns", 0) or 0),
            "dominant_unsupported_reason": failure_taxonomy.get("summary", {}).get("dominant_unsupported_reason"),
            "issue_labels": list(failure_taxonomy.get("summary", {}).get("issue_labels", [])),
            "kb_valid": bool(kb.get("health_report", {}).get("valid", False)),
            "kb_filed_output_count": int(kb.get("compile_result", {}).get("filed_output_count", 0) or 0),
        },
        "trace": {
            "operation": "run_spark_builder_intake_batch",
            "glob": glob_pattern,
        },
    }


def _run_spark_telegram_intake_batch(
    data_dir: str,
    output_dir: str,
    *,
    glob_pattern: str = "*.json",
    repo_sources: list[str] | None = None,
    repo_source_manifest_files: list[str] | None = None,
) -> dict:
    normalization = _normalize_telegram_shadow_export_batch(data_dir, glob_pattern=glob_pattern)
    shadow_report = _load_shadow_report_payload_from_telegram_export_batch(data_dir, glob_pattern=glob_pattern)
    failure_taxonomy = _build_shadow_failure_taxonomy_from_telegram_export_batch(data_dir, glob_pattern=glob_pattern)
    kb = _build_spark_kb_from_telegram_export_batch(
        data_dir,
        output_dir,
        glob_pattern=glob_pattern,
        repo_sources=repo_sources,
        repo_source_manifest_files=repo_source_manifest_files,
    )
    return {
        "source_dir": str(Path(data_dir)),
        "output_dir": str(Path(output_dir)),
        "source_files": list(normalization.get("source_files", [])),
        "contract": build_telegram_shadow_adapter_contract_summary(),
        "normalization": normalization,
        "shadow_report": shadow_report["report"],
        "failure_taxonomy": failure_taxonomy,
        "kb": kb,
        "summary": {
            "file_count": int(normalization.get("file_count", 0) or 0),
            "valid_telegram_exports": bool(normalization.get("valid", False)),
            "run_count": int(shadow_report.get("report", {}).get("run_count", 0) or 0),
            "accepted_writes": int(shadow_report.get("report", {}).get("summary", {}).get("accepted_writes", 0) or 0),
            "rejected_writes": int(shadow_report.get("report", {}).get("summary", {}).get("rejected_writes", 0) or 0),
            "skipped_turns": int(shadow_report.get("report", {}).get("summary", {}).get("skipped_turns", 0) or 0),
            "reference_turns": int(shadow_report.get("report", {}).get("summary", {}).get("reference_turns", 0) or 0),
            "dominant_unsupported_reason": failure_taxonomy.get("summary", {}).get("dominant_unsupported_reason"),
            "issue_labels": list(failure_taxonomy.get("summary", {}).get("issue_labels", [])),
            "kb_valid": bool(kb.get("health_report", {}).get("valid", False)),
            "kb_filed_output_count": int(kb.get("compile_result", {}).get("filed_output_count", 0) or 0),
        },
        "trace": {
            "operation": "run_spark_telegram_intake_batch",
            "glob": glob_pattern,
        },
    }


def _run_spark_builder_telegram_intake(
    builder_dir: str,
    output_dir: str,
    *,
    glob_pattern: str = ".tmp-telegram-*.json",
    repo_sources: list[str] | None = None,
    repo_source_manifest_files: list[str] | None = None,
) -> dict:
    effective_repo_source_manifest_files = _default_builder_repo_source_manifest_files(
        builder_dir,
        repo_source_manifest_files=repo_source_manifest_files,
    )
    payload = _run_spark_telegram_intake_batch(
        builder_dir,
        output_dir,
        glob_pattern=glob_pattern,
        repo_sources=repo_sources,
        repo_source_manifest_files=effective_repo_source_manifest_files,
    )
    payload["builder_source_dir"] = str(Path(builder_dir))
    payload["summary"]["builder_artifact_glob"] = glob_pattern
    payload["trace"] = {
        "operation": "run_spark_builder_telegram_intake",
        "glob": glob_pattern,
    }
    return payload


def _normalize_builder_telegram_state_db(
    builder_home: str,
    *,
    limit: int = 25,
    chat_id: str | None = None,
) -> dict:
    root = Path(builder_home)
    state_db_path = root if root.is_file() else root / "state.db"
    if not state_db_path.exists():
        raise ValueError(f"Builder state DB not found at {state_db_path}.")
    selected_chat_id = str(chat_id) if chat_id is not None else None

    def _format_builder_timestamp(value: object) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        if text.endswith("Z") and "T" in text:
            return text
        if "T" in text:
            return f"{text}Z"
        return f"{text.replace(' ', 'T')}Z"

    def _load_facts(raw: object) -> dict:
        if isinstance(raw, dict):
            return raw
        text = str(raw or "").strip()
        if not text:
            return {}
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _builder_chat_id(*, facts: dict, session_id: object, human_id: object) -> str:
        direct = (
            facts.get("chat_id")
            or facts.get("telegram_chat_id")
            or facts.get("telegram_user_id")
            or facts.get("user_id")
        )
        if direct not in (None, ""):
            return str(direct)
        session_text = str(session_id or "").strip()
        if session_text.startswith("session:telegram:"):
            return session_text.rsplit(":", 1)[-1]
        human_text = _builder_human_id(facts=facts, human_id=human_id) or ""
        if human_text.startswith("human:telegram:"):
            return human_text.rsplit(":", 1)[-1]
        return "unknown"

    def _normalize_builder_human_id(human_id: object) -> str | None:
        clean_human_id = str(human_id or "").strip()
        if not clean_human_id:
            return None
        while clean_human_id.startswith("human:human:"):
            clean_human_id = clean_human_id[len("human:") :]
        if clean_human_id.startswith("telegram:"):
            clean_human_id = f"human:{clean_human_id}"
        return clean_human_id or None

    def _builder_human_id(*, facts: dict, human_id: object) -> str | None:
        direct_human_id = _normalize_builder_human_id(human_id)
        if direct_human_id:
            return direct_human_id
        facts_subject = _normalize_builder_human_id(facts.get("subject"))
        if facts_subject:
            return facts_subject
        retrieval_trace = facts.get("retrieval_trace")
        retrieval_trace_dict = retrieval_trace if isinstance(retrieval_trace, dict) else {}
        retrieval_subject = _normalize_builder_human_id(retrieval_trace_dict.get("subject"))
        if retrieval_subject:
            return retrieval_subject
        telegram_user_id = str(facts.get("telegram_user_id") or facts.get("user_id") or "").strip()
        if telegram_user_id:
            return f"human:telegram:{telegram_user_id}"
        return None

    def _query_message(payload: dict) -> str | None:
        if not isinstance(payload, dict):
            return None
        fact_name = str(payload.get("fact_name") or "").strip()
        label = str(payload.get("label") or "").strip()
        canonical = {
            "profile_preferred_name": "What is my name?",
            "profile_startup_name": "What is my startup?",
            "profile_hack_actor": "Who hacked us?",
            "profile_current_mission": "What is my mission right now?",
            "profile_founder_of": "What company did I found?",
            "profile_occupation": "What do I do?",
            "profile_spark_role": "What role will Spark play in this?",
            "profile_identity_summary": "Who am I?",
            "profile_home_country": "What country do I live in?",
            "profile_timezone": "What is my timezone?",
            "profile_city": "Where do I live?",
        }
        if fact_name:
            return canonical.get(fact_name, f"What is my {label or fact_name}?")
        if label:
            return f"What is my {label}?"
        return None

    def _telegram_event_summary_predicate(predicate: str | None) -> str | None:
        normalized_predicate = str(predicate or "").strip()
        prefix = "telegram.event."
        if not normalized_predicate.startswith(prefix):
            return None
        suffix = normalized_predicate[len(prefix) :].strip()
        if not suffix:
            return None
        return f"telegram.summary.latest_{suffix}"

    def _telegram_event_label(
        predicate: str | None,
        *,
        fallback: str | None = None,
    ) -> str | None:
        clean_fallback = str(fallback or "").strip()
        if clean_fallback:
            if clean_fallback.endswith(" events"):
                return clean_fallback[: -len(" events")].strip() or clean_fallback
            return clean_fallback
        normalized_predicate = str(predicate or "").strip()
        for prefix in ("telegram.event.", "telegram.summary.latest_"):
            if normalized_predicate.startswith(prefix):
                suffix = normalized_predicate[len(prefix) :].strip().replace("_", " ")
                return suffix or None
        return None

    def _event_query_message(payload: dict) -> str | None:
        if not isinstance(payload, dict):
            return None
        message_text = str(payload.get("message_text") or "").strip()
        if message_text:
            return message_text
        predicate = str(payload.get("predicate") or "").strip() or None
        label = _telegram_event_label(predicate, fallback=str(payload.get("label") or "").strip() or None)
        query_kind = str(payload.get("query_kind") or "").strip().lower()
        if query_kind == "latest_event":
            return f"What {label or 'event'} do I have?"
        if predicate:
            plural_label = f"{label} events" if label else "events"
            return f"What {plural_label} did I mention?"
        return "What event did I mention?"

    def _query_message_from_predicate(predicate: str | None, *, predicate_prefix: str | None = None) -> str | None:
        normalized_predicate = str(predicate or "").strip()
        if normalized_predicate:
            mapping = {
                "profile.preferred_name": "What is my name?",
                "profile.startup_name": "What is my startup?",
                "profile.hack_actor": "Who hacked us?",
                "profile.current_mission": "What is my mission right now?",
                "profile.founder_of": "What company did I found?",
                "profile.occupation": "What do I do?",
                "profile.spark_role": "What role will Spark play in this?",
                "profile.home_country": "What country do I live in?",
                "profile.timezone": "What is my timezone?",
                "profile.city": "Where do I live?",
            }
            if normalized_predicate.startswith("telegram.summary.latest_"):
                label = _telegram_event_label(normalized_predicate)
                if label:
                    return f"What {label} do I have?"
            return mapping.get(normalized_predicate, f"What is my {normalized_predicate}?")
        normalized_prefix = str(predicate_prefix or "").strip()
        if normalized_prefix in {"", "profile."}:
            return "Who am I?"
        return "What do you know about me?"

    def _explanation_question(*, predicate: str | None, label: str | None = None) -> str | None:
        normalized_predicate = str(predicate or "").strip()
        mapping = {
            "profile.preferred_name": "How do you know my name?",
            "profile.startup_name": "How do you know my startup?",
            "profile.hack_actor": "How do you know who hacked us?",
            "profile.current_mission": "How do you know what I'm trying to do now?",
            "profile.founder_of": "How do you know what company I founded?",
            "profile.occupation": "How do you know what I do?",
            "profile.spark_role": "How do you know Spark's role?",
            "profile.home_country": "How do you know my country?",
            "profile.timezone": "How do you know my timezone?",
            "profile.city": "How do you know where I live?",
        }
        if normalized_predicate:
            return mapping.get(normalized_predicate)
        clean_label = str(label or "").strip()
        if clean_label:
            return f"How do you know my {clean_label}?"
        return None

    def _query_predicate(payload: dict) -> str | None:
        predicate = str(payload.get("predicate") or "").strip()
        if predicate:
            return predicate
        fact_name = str(payload.get("fact_name") or "").strip()
        mapping = {
            "profile_preferred_name": "profile.preferred_name",
            "profile_startup_name": "profile.startup_name",
            "profile_hack_actor": "profile.hack_actor",
            "profile_current_mission": "profile.current_mission",
            "profile_founder_of": "profile.founder_of",
            "profile_occupation": "profile.occupation",
            "profile_spark_role": "profile.spark_role",
            "profile_home_country": "profile.home_country",
            "profile_timezone": "profile.timezone",
            "profile_city": "profile.city",
        }
        return mapping.get(fact_name)

    def _with_indefinite_article(text: str) -> str:
        normalized = " ".join(str(text or "").strip().split())
        if not normalized:
            return ""
        lowered = normalized.lower()
        if lowered.startswith("a ") or lowered.startswith("an "):
            return normalized
        article = "an" if normalized[:1].lower() in {"a", "e", "i", "o", "u"} else "a"
        return f"{article} {normalized}"

    def _spark_role_sentence(text: str) -> str:
        normalized = " ".join(str(text or "").strip().split())
        if normalized.lower().startswith("important part"):
            return f"Spark will be an {normalized}"
        return f"Spark will be {normalized}"

    def _record_sort_key(timestamp: str | None, message_id: str | None) -> tuple[str, str]:
        return (str(timestamp or ""), str(message_id or ""))

    def _remember_known_value(
        store: dict[str, dict[str, str]],
        *,
        predicate: str,
        value: str,
        timestamp: str | None,
        message_id: str | None,
        evidence_text: str | None = None,
    ) -> None:
        if not predicate or not value:
            return
        store[predicate] = {
            "predicate": predicate,
            "value": value,
            "timestamp": str(timestamp or ""),
            "message_id": str(message_id or ""),
            "evidence_text": str(evidence_text or ""),
        }

    def _forget_known_value(
        store: dict[str, dict[str, str]],
        *,
        predicate: str,
    ) -> None:
        clean_predicate = str(predicate or "").strip()
        if not clean_predicate:
            return
        store.pop(clean_predicate, None)

    def _known_value_matches(
        store: dict[str, dict[str, str]],
        *,
        predicate: str,
        value: str,
    ) -> bool:
        entry = _effective_query_entry(store, predicate)
        if not isinstance(entry, dict):
            return False
        known_value = str(entry.get("value") or "").strip().lower()
        incoming_value = str(value or "").strip().lower()
        return bool(known_value) and bool(incoming_value) and known_value == incoming_value

    def _effective_query_entry(store: dict[str, dict[str, str]], predicate: str | None) -> dict[str, str] | None:
        normalized = str(predicate or "").strip()
        if normalized == "profile.startup_name":
            candidates: list[tuple[tuple[str, str], dict[str, str]]] = []
            for related_predicate in ("profile.startup_name", "profile.founder_of"):
                entry = store.get(related_predicate)
                if not isinstance(entry, dict):
                    continue
                value = str(entry.get("value") or "").strip()
                if not value:
                    continue
                candidates.append(
                    (
                        _record_sort_key(entry.get("timestamp"), entry.get("message_id")),
                        entry,
                    )
                )
            if candidates:
                candidates.sort(key=lambda item: item[0])
                return candidates[-1][1]
        entry = store.get(normalized)
        return entry if isinstance(entry, dict) else None

    def _known_value(store: dict[str, dict[str, str]], predicate: str | None) -> str | None:
        entry = store.get(str(predicate or "").strip())
        if not isinstance(entry, dict):
            return None
        value = str(entry.get("value") or "").strip()
        return value or None

    def _probe_key(value: str | None) -> str:
        text = str(value or "").strip().lower()
        if not text:
            return "unknown"
        return "".join(character if character.isalnum() else "-" for character in text).strip("-") or "unknown"

    def _append_probe(conversation: dict[str, object], probe: dict[str, object]) -> None:
        probe_id = str(probe.get("probe_id") or "").strip()
        probe_type = str(probe.get("probe_type") or "").strip()
        if not probe_id or not probe_type:
            return
        for existing in conversation.get("probes", []):
            if isinstance(existing, dict) and str(existing.get("probe_id") or "") == probe_id:
                return
        cast_probes = conversation.setdefault("probes", [])
        if isinstance(cast_probes, list):
            cast_probes.append(probe)

    def _prune_historical_probes(
        conversation: dict[str, object],
        *,
        predicate: str | None,
        as_of: str | None,
    ) -> None:
        clean_predicate = str(predicate or "").strip()
        clean_as_of = str(as_of or "").strip()
        probes = conversation.get("probes")
        if not clean_predicate or not clean_as_of or not isinstance(probes, list):
            return
        conversation["probes"] = [
            probe
            for probe in probes
            if not (
                isinstance(probe, dict)
                and str(probe.get("probe_type") or "").strip() == "historical_state"
                and str(probe.get("predicate") or "").strip() == clean_predicate
                and str(probe.get("as_of") or "").strip() == clean_as_of
            )
        ]

    def _append_lookup_probes(
        conversation: dict[str, object],
        *,
        base_probe_id: str,
        subject: str | None,
        predicate: str | None,
        expected_value: str | None,
        include_current_state: bool = True,
        include_evidence: bool = True,
    ) -> None:
        clean_subject = str(subject or "").strip()
        clean_predicate = str(predicate or "").strip()
        clean_value = str(expected_value or "").strip()
        if not clean_subject or not clean_predicate or not clean_value:
            return
        if include_current_state:
            _append_probe(
                conversation,
                {
                    "probe_id": f"{base_probe_id}:current",
                    "probe_type": "current_state",
                    "subject": clean_subject,
                    "predicate": clean_predicate,
                    "expected_value": clean_value,
                },
            )
        if include_evidence:
            _append_probe(
                conversation,
                {
                    "probe_id": f"{base_probe_id}:evidence",
                    "probe_type": "evidence",
                    "subject": clean_subject,
                    "predicate": clean_predicate,
                    "expected_value": clean_value,
                    "min_results": 1,
                },
            )

    def _append_historical_probe(
        conversation: dict[str, object],
        *,
        base_probe_id: str,
        subject: str | None,
        predicate: str | None,
        expected_value: str | None,
        as_of: str | None,
        distinct_value_count: int,
    ) -> None:
        clean_subject = str(subject or "").strip()
        clean_predicate = str(predicate or "").strip()
        clean_value = str(expected_value or "").strip()
        clean_as_of = str(as_of or "").strip()
        if distinct_value_count < 2 or not clean_subject or not clean_predicate or not clean_value or not clean_as_of:
            return
        _append_probe(
            conversation,
            {
                "probe_id": f"{base_probe_id}:historical",
                "probe_type": "historical_state",
                "subject": clean_subject,
                "predicate": clean_predicate,
                "as_of": clean_as_of,
                "expected_value": clean_value,
            },
        )

    def _effective_query_value(store: dict[str, dict[str, str]], predicate: str | None, fallback: str | None = None) -> str | None:
        entry = _effective_query_entry(store, predicate)
        direct = str((entry or {}).get("value") or "").strip()
        if direct:
            return direct
        clean_fallback = str(fallback or "").strip()
        return clean_fallback or None

    def _effective_query_evidence_text(store: dict[str, dict[str, str]], predicate: str | None) -> str | None:
        entry = _effective_query_entry(store, predicate)
        evidence_text = str((entry or {}).get("evidence_text") or "").strip()
        return evidence_text or None

    def _resolve_probe_predicate_and_value(
        store: dict[str, dict[str, str]],
        *,
        predicate: str | None,
        expected_value: str | None,
    ) -> tuple[str | None, str | None]:
        normalized_predicate = str(predicate or "").strip() or None
        clean_expected = str(expected_value or "").strip() or None
        if normalized_predicate == "profile.startup_name":
            direct_entry = store.get("profile.startup_name") or {}
            founder_entry = store.get("profile.founder_of") or {}
            direct_value = str(direct_entry.get("value") or "").strip() or None
            founder_value = str(founder_entry.get("value") or "").strip() or None
            if clean_expected and founder_value and clean_expected == founder_value:
                return "profile.founder_of", founder_value
            if clean_expected and direct_value and clean_expected == direct_value:
                return "profile.startup_name", direct_value
            effective_entry = _effective_query_entry(store, normalized_predicate) or {}
            effective_predicate = str(effective_entry.get("predicate") or normalized_predicate).strip() or normalized_predicate
            effective_value = str(effective_entry.get("value") or "").strip() or None
            return effective_predicate, effective_value
        current_entry = store.get(str(normalized_predicate or "").strip()) or {}
        current_value = str(current_entry.get("value") or "").strip() or None
        return normalized_predicate, current_value

    def _query_answer(*, predicate: str | None, value: str | None) -> str | None:
        clean_value = str(value or "").strip()
        if not clean_value:
            return None
        mapping = {
            "profile.preferred_name": lambda text: f"Your name is {text}.",
            "profile.startup_name": lambda text: f"You created {text}.",
            "profile.hack_actor": lambda text: f"You were hacked by {text}.",
            "profile.current_mission": lambda text: f"Right now you're trying to {text}.",
            "profile.founder_of": lambda text: f"You founded {text}.",
            "profile.occupation": lambda text: f"You're {_with_indefinite_article(text)}.",
            "profile.spark_role": lambda text: f"{_spark_role_sentence(text)}.",
            "profile.home_country": lambda text: f"Your country is {text}.",
            "profile.timezone": lambda text: f"Your timezone is {text}.",
            "profile.city": lambda text: f"You live in {text}.",
        }
        renderer = mapping.get(str(predicate or "").strip())
        if renderer is not None:
            return renderer(clean_value)
        return clean_value if clean_value.endswith(".") else f"{clean_value}."

    def _event_history_records(
        histories: dict[str, list[dict[str, str]]],
        *,
        predicate: str | None,
    ) -> list[dict[str, str]]:
        clean_predicate = str(predicate or "").strip()
        records: list[dict[str, str]] = []
        for history_predicate, entries in histories.items():
            normalized_history_predicate = str(history_predicate or "").strip()
            if not normalized_history_predicate.startswith("telegram.event."):
                continue
            if clean_predicate and normalized_history_predicate != clean_predicate:
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                value = str(entry.get("value") or "").strip()
                if not value:
                    continue
                records.append(
                    {
                        "predicate": normalized_history_predicate,
                        "value": value,
                        "timestamp": str(entry.get("timestamp") or "").strip(),
                        "message_id": str(entry.get("message_id") or "").strip(),
                    }
                )
        records.sort(
            key=lambda entry: (
                str(entry.get("timestamp") or ""),
                str(entry.get("message_id") or ""),
                str(entry.get("predicate") or ""),
                str(entry.get("value") or ""),
            )
        )
        return records

    def _ordered_unique_event_values(records: list[dict[str, str]]) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for record in records:
            value = str(record.get("value") or "").strip()
            if not value:
                continue
            dedupe_key = value.casefold()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            values.append(value)
        return values

    def _event_query_answer(
        *,
        predicate: str | None,
        label: str | None,
        query_kind: str | None,
        records: list[dict[str, str]],
    ) -> str | None:
        ordered_values = _ordered_unique_event_values(records)
        normalized_query_kind = str(query_kind or "").strip().lower()
        normalized_label = _telegram_event_label(predicate, fallback=label) or "event"
        if normalized_query_kind == "latest_event":
            if not ordered_values:
                return f"I don't currently have a saved {normalized_label}."
            return f"Your latest saved {normalized_label} is {ordered_values[-1]}."
        if not ordered_values:
            return "I don't currently have any saved events from this chat."
        if len(ordered_values) == 1:
            return f"I have 1 saved event: {ordered_values[0]}."
        if len(ordered_values) == 2:
            return f"I have 2 saved events: {ordered_values[0]} then {ordered_values[1]}."
        preview = ordered_values[:3]
        remainder = len(ordered_values) - len(preview)
        suffix = f", and {remainder} more" if remainder > 0 else ""
        return f"I have {len(ordered_values)} saved events: {' then '.join(preview)}{suffix}."

    def _event_update_answer(predicate: str | None, value: str | None) -> str | None:
        clean_value = str(value or "").strip()
        if not clean_value:
            return None
        if str(predicate or "").strip().startswith("telegram.event."):
            return f"I'll remember your {clean_value}."
        return None

    def _identity_answer(known_values: dict[str, dict[str, str]]) -> str | None:
        ordered_predicates = [
            "profile.preferred_name",
            "profile.occupation",
            "profile.city",
            "profile.home_country",
            "profile.timezone",
            "profile.startup_name",
            "profile.founder_of",
            "profile.spark_role",
            "profile.current_mission",
            "profile.hack_actor",
        ]
        parts = [
            _query_answer(predicate=predicate, value=_known_value(known_values, predicate))
            for predicate in ordered_predicates
        ]
        rendered = [part for part in parts if part]
        if not rendered:
            return None
        return " ".join(rendered)

    def _explanation_answer(
        *,
        predicate: str | None,
        value: str | None,
        evidence_text: str | None,
    ) -> str | None:
        fact_answer = _query_answer(predicate=predicate, value=value)
        if not fact_answer:
            return None
        clean_evidence = str(evidence_text or "").strip()
        if clean_evidence:
            return f'Because I have a saved memory record from when you said: "{clean_evidence}" {fact_answer}'
        return f"Because I have a saved memory record for this fact. {fact_answer}"

    def _update_answer(predicate: str | None, value: str | None) -> str | None:
        clean_value = str(value or "").strip()
        if not clean_value:
            return None
        mapping = {
            "profile.preferred_name": lambda text: f"I'll remember your name is {text}.",
            "profile.startup_name": lambda text: f"I'll remember you created {text}.",
            "profile.hack_actor": lambda text: f"I'll remember the hack actor was {text}.",
            "profile.current_mission": lambda text: (
                f"I'll remember your current mission is to {text}."
            ),
            "profile.founder_of": lambda text: f"I'll remember you founded {text}.",
            "profile.occupation": lambda text: f"I'll remember you're {_with_indefinite_article(text)}.",
            "profile.spark_role": lambda text: f"I'll remember {_spark_role_sentence(text)}.",
            "profile.home_country": lambda text: f"I'll remember your country is {text}.",
            "profile.timezone": lambda text: f"I'll remember your timezone is {text}.",
            "profile.city": lambda text: f"I'll remember you live in {text}.",
        }
        renderer = mapping.get(str(predicate or "").strip())
        if renderer is not None:
            return renderer(clean_value)
        return f"I'll remember {clean_value}."

    def _read_request_question(
        facts: dict,
        *,
        session_id: str | None,
    ) -> str | None:
        method = str(facts.get("method") or "").strip().lower()
        query = str(facts.get("query") or "").strip()
        predicate = str(facts.get("predicate") or "").strip() or None
        predicate_prefix = str(facts.get("predicate_prefix") or "").strip() or None
        if query:
            return query
        if method == "explain_answer":
            return _explanation_question(predicate=predicate) or "How do you know that?"
        if method == "retrieve_evidence":
            return _explanation_question(predicate=predicate) or _query_message_from_predicate(
                predicate,
                predicate_prefix=predicate_prefix,
            )
        if method == "get_current_state":
            return _query_message_from_predicate(predicate, predicate_prefix=predicate_prefix)
        session_text = str(session_id or "").strip().lower()
        if "inspect" in session_text:
            return "Who am I?"
        if "explain" in session_text:
            return "How do you know that?"
        if "retrieval" in session_text:
            return "What evidence do you have for that?"
        return None

    def _read_result_message(
        facts: dict,
        *,
        event_type: str,
    ) -> str | None:
        method = str(facts.get("method") or "").strip().lower() or "memory_read"
        reason = str(facts.get("reason") or "").strip()
        record_count = int(facts.get("record_count", 0) or 0)
        retrieval_trace = facts.get("retrieval_trace")
        retrieval_trace_dict = retrieval_trace if isinstance(retrieval_trace, dict) else {}
        answer_explanation = facts.get("answer_explanation")
        answer_explanation_dict = answer_explanation if isinstance(answer_explanation, dict) else {}
        explanation_text = str(answer_explanation_dict.get("explanation") or "").strip()
        retrieval_operation = str(retrieval_trace_dict.get("operation") or method).strip().lower() or method
        question = str(retrieval_trace_dict.get("question") or "").strip()
        query = str(retrieval_trace_dict.get("query") or "").strip()
        predicate = str(retrieval_trace_dict.get("predicate") or "").strip() or None
        predicate_prefix = str(retrieval_trace_dict.get("predicate_prefix") or "").strip() or None
        query_text = question or query or _query_message_from_predicate(
            predicate,
            predicate_prefix=predicate_prefix,
        )
        if event_type == "memory_read_succeeded":
            if query_text:
                return f"Memory read succeeded for `{query_text}` with `{record_count}` matching records."
            return f"Memory read succeeded for `{method}` with `{record_count}` matching records."
        if reason:
            return f"Memory read abstained for `{method}` because `{reason}`."
        if explanation_text:
            return explanation_text
        if retrieval_operation == "retrieve_evidence":
            if query_text:
                return f"No supporting evidence found for `{query_text}`."
            return "No supporting evidence was found in memory."
        if retrieval_operation == "retrieve_events":
            if query_text:
                return f"No supporting events found for `{query_text}`."
            return "No supporting events were found in memory."
        if retrieval_operation in {"get_current_state", "get_historical_state"}:
            if query_text:
                return f"No supported memory answer found for `{query_text}`."
            return "No supported memory answer was found."
        return f"Memory read abstained for `{method}`."

    def _read_result_trace_metadata(
        facts: dict,
        *,
        event_type: str,
        known_values: dict[str, dict[str, str]] | None = None,
    ) -> dict[str, object]:
        retrieval_trace = facts.get("retrieval_trace")
        retrieval_trace_dict = retrieval_trace if isinstance(retrieval_trace, dict) else {}
        answer_explanation = facts.get("answer_explanation")
        answer_explanation_dict = answer_explanation if isinstance(answer_explanation, dict) else {}
        method = str(facts.get("method") or "").strip()
        reason = str(facts.get("reason") or "").strip()
        contract_reason = str(retrieval_trace_dict.get("contract_reason") or "").strip()
        memory_role = str(facts.get("memory_role") or "").strip()
        retrieval_operation = str(retrieval_trace_dict.get("operation") or "").strip()
        predicate = str(retrieval_trace_dict.get("predicate") or "").strip() or None
        predicate_prefix = str(retrieval_trace_dict.get("predicate_prefix") or "").strip() or None
        question = str(retrieval_trace_dict.get("question") or "").strip() or None
        query = str(retrieval_trace_dict.get("query") or "").strip() or None
        subject = str(retrieval_trace_dict.get("subject") or "").strip() or None
        explanation_text = str(answer_explanation_dict.get("explanation") or "").strip()
        record_count = int(facts.get("record_count", 0) or 0)
        read_outcome = "succeeded"
        supported_answer_exists = _has_supported_read_answer(
            known_values or {},
            method=method,
            predicate=predicate,
            predicate_prefix=predicate_prefix,
            question=question,
            query=query,
        )
        if event_type == "memory_read_abstained":
            if reason or contract_reason:
                read_outcome = "gap"
            elif supported_answer_exists and memory_role == "unknown" and record_count == 0:
                contract_reason = "supported_fact_unanswered"
                read_outcome = "gap"
            elif memory_role == "unknown" and record_count == 0 and (
                retrieval_operation or explanation_text.lower().startswith("no supported answer")
            ):
                read_outcome = "no_supported_answer"
            else:
                read_outcome = "unknown_abstention"
        return {
            "read_outcome": read_outcome,
            "retrieval_operation": retrieval_operation or None,
            "contract_reason": contract_reason or None,
            "observed_memory_role": str(retrieval_trace_dict.get("observed_memory_role") or "").strip() or None,
            "explanation_text": explanation_text or None,
            "predicate": predicate,
            "predicate_prefix": predicate_prefix,
            "question": question,
            "query": query,
            "subject": subject,
        }

    def _known_identity_records(
        store: dict[str, dict[str, str]],
        *,
        predicate_prefix: str = "profile.",
    ) -> list[tuple[str, str]]:
        records: list[tuple[str, str]] = []
        for predicate, entry in store.items():
            clean_predicate = str(predicate or "").strip()
            if not clean_predicate.startswith(predicate_prefix):
                continue
            value = str((entry or {}).get("value") or "").strip()
            if not value:
                continue
            records.append((clean_predicate, value))
        records.sort(key=lambda item: item[0])
        return records

    def _normalized_read_query_key(*, question: str | None, query: str | None) -> str:
        return str(question or query or "").strip().lower().rstrip("?.! ")

    def _has_supported_read_answer(
        store: dict[str, dict[str, str]],
        *,
        method: str | None,
        predicate: str | None,
        predicate_prefix: str | None,
        question: str | None,
        query: str | None,
    ) -> bool:
        if _effective_query_value(store, predicate):
            return True
        normalized_method = str(method or "").strip().lower()
        normalized_query_key = _normalized_read_query_key(question=question, query=query)
        normalized_prefix = str(predicate_prefix or "").strip()
        if (
            normalized_method in {"get_current_state", "retrieve_evidence", "explain_answer"}
            and not str(predicate or "").strip()
            and normalized_query_key in {"who am i", "what do you know about me"}
        ):
            prefix = normalized_prefix or "profile."
            return bool(_known_identity_records(store, predicate_prefix=prefix))
        return False

    def _turn_sort_key(item: dict) -> tuple[str, str]:
        return (str(item.get("timestamp") or ""), str(item.get("message_id") or ""))

    def _conversation_sort_key(conversation: dict[str, object]) -> tuple[str, str]:
        turns = [turn for turn in conversation.get("turns", []) if isinstance(turn, dict)]
        if not turns:
            return ("", "")
        return max((_turn_sort_key(turn) for turn in turns), default=("", ""))

    raw_event_limit = max(limit * 8, 200)
    supported_event_types = (
        "intent_committed",
        "delivery_succeeded",
        "memory_write_requested",
        "memory_write_succeeded",
        "memory_read_requested",
        "memory_read_succeeded",
        "memory_read_abstained",
        "plugin_or_chip_influence_recorded",
        "tool_result_received",
    )

    def _supported_event_where_clause() -> str:
        return ", ".join(f"'{event_type}'" for event_type in supported_event_types)

    def _load_supported_builder_rows(*, scan_all: bool) -> list[sqlite3.Row]:
        connection = sqlite3.connect(state_db_path)
        connection.row_factory = sqlite3.Row
        try:
            if selected_chat_id is not None or scan_all:
                return connection.execute(
                    f"""
                    SELECT
                        rowid AS row_order,
                        event_id,
                        event_type,
                        created_at,
                        request_id,
                        trace_ref,
                        channel_id,
                        session_id,
                        human_id,
                        component,
                        summary,
                        facts_json
                    FROM builder_events
                    WHERE event_type IN ({_supported_event_where_clause()})
                    ORDER BY created_at ASC, row_order ASC
                    """
                ).fetchall()
            return connection.execute(
                f"""
                SELECT *
                FROM (
                    SELECT
                        rowid AS row_order,
                        event_id,
                        event_type,
                        created_at,
                        request_id,
                        trace_ref,
                        channel_id,
                        session_id,
                        human_id,
                        component,
                        summary,
                        facts_json
                    FROM builder_events
                    WHERE event_type IN ({_supported_event_where_clause()})
                    ORDER BY created_at DESC, event_id DESC
                    LIMIT ?
                )
                ORDER BY created_at ASC, row_order ASC
                LIMIT ?
                """,
                (raw_event_limit, raw_event_limit),
            ).fetchall()
        finally:
            connection.close()

    def _load_supported_builder_rows_for_humans(human_ids: list[str]) -> list[sqlite3.Row]:
        clean_human_ids = sorted({str(human_id).strip() for human_id in human_ids if str(human_id).strip()})
        if not clean_human_ids:
            return []
        placeholders = ", ".join("?" for _ in clean_human_ids)
        connection = sqlite3.connect(state_db_path)
        connection.row_factory = sqlite3.Row
        try:
            return connection.execute(
                f"""
                SELECT
                    rowid AS row_order,
                    event_id,
                    event_type,
                    created_at,
                    request_id,
                    trace_ref,
                    channel_id,
                    session_id,
                    human_id,
                    component,
                    summary,
                    facts_json
                FROM builder_events
                WHERE event_type IN ({_supported_event_where_clause()})
                AND human_id IN ({placeholders})
                ORDER BY created_at ASC, row_order ASC
                """,
                clean_human_ids,
            ).fetchall()
        finally:
            connection.close()

    def _merge_supported_rows(*groups: list[sqlite3.Row]) -> list[dict[str, object]]:
        merged_by_key: dict[str, dict[str, object]] = {}
        for group in groups:
            for row in group:
                row_dict = dict(row)
                key = str(row_dict.get("row_order") or row_dict.get("event_id") or "")
                if not key:
                    continue
                merged_by_key[key] = row_dict
        return sorted(
            merged_by_key.values(),
            key=lambda row: (str(row.get("created_at") or ""), int(row.get("row_order") or 0)),
        )

    def _conversation_needs_supporting_history(conversation: dict[str, object]) -> bool:
        turns = [turn for turn in conversation.get("turns", []) if isinstance(turn, dict)]
        if not turns:
            return False
        has_memory_write_turn = any(
            str((turn.get("metadata") or {}).get("source_event_type") or "").strip() == "memory_write_requested"
            for turn in turns
        )
        if has_memory_write_turn:
            return False
        return any(
            str((turn.get("metadata") or {}).get("source_event_type") or "").strip()
            in {"memory_read_succeeded", "memory_read_abstained"}
            for turn in turns
        )

    def _is_synthetic_builder_identifier(value: object) -> bool:
        clean_value = str(value or "").strip().lower()
        if not clean_value:
            return False
        return any(
            marker in clean_value
            for marker in (
                "spark-memory-regression",
                "regression-user",
                "memory_regression",
                "spark-memory-soak",
                "soak-user",
            )
        )

    def _is_synthetic_builder_regression_conversation(conversation: dict[str, object]) -> bool:
        metadata = conversation.get("metadata")
        metadata_dict = metadata if isinstance(metadata, dict) else {}
        identifiers = [
            str(conversation.get("conversation_id") or "").strip().lower(),
            str(conversation.get("session_id") or "").strip().lower(),
            str(metadata_dict.get("chat_id") or "").strip().lower(),
            str(metadata_dict.get("human_id") or "").strip().lower(),
        ]
        if any(_is_synthetic_builder_identifier(value) for value in identifiers if value):
            return True
        for turn in conversation.get("turns", []):
            if not isinstance(turn, dict):
                continue
            metadata_dict = turn.get("metadata") if isinstance(turn.get("metadata"), dict) else {}
            turn_identifiers = [
                str(turn.get("message_id") or "").strip().lower(),
                str(metadata_dict.get("request_id") or "").strip().lower(),
                str(metadata_dict.get("subject") or "").strip().lower(),
            ]
            if any(_is_synthetic_builder_identifier(value) for value in turn_identifiers if value):
                return True
        return False

    def _normalize_supported_rows(
        source_rows: list[sqlite3.Row],
        *,
        keep_synthetic_regression_when_only_available: bool,
        supporting_history_human_ids: list[str] | None = None,
    ) -> tuple[list[str], dict[str, object]]:
        available_chat_ids_set: set[str] = set()
        conversations_by_key: dict[str, dict[str, object]] = {}
        supporting_history_human_id_set = {
            str(_normalize_builder_human_id(human_id) or "").strip()
            for human_id in (supporting_history_human_ids or [])
            if str(_normalize_builder_human_id(human_id) or "").strip()
        }

        def _conversation_for(chat_value: str, session_value: str | None, human_value: str | None) -> dict[str, object]:
            clean_human_value = str(_normalize_builder_human_id(human_value) or "").strip()
            if clean_human_value and clean_human_value in supporting_history_human_id_set:
                conversation_key = f"telegram-chat-{chat_value}"
            elif clean_human_value and str(session_value or "").startswith("memory-"):
                conversation_key = f"{session_value}:{clean_human_value}"
            else:
                conversation_key = str(session_value or f"telegram-chat-{chat_value}")
            conversation = conversations_by_key.setdefault(
                conversation_key,
                {
                    "conversation_id": conversation_key,
                    "session_id": conversation_key if conversation_key != str(session_value or conversation_key) else (session_value or conversation_key),
                    "metadata": {
                        "source": "spark_builder_state_db",
                        "chat_id": chat_value,
                        "human_id": clean_human_value or human_value,
                        "builder_home": str(root),
                        "state_db": str(state_db_path),
                    },
                    "turns": [],
                    "probes": [],
                },
            )
            return conversation

        legacy_groups: dict[str, dict[str, object]] = {}
        bridge_groups: dict[tuple[str, str], list[sqlite3.Row]] = {}
        for row in source_rows:
            facts = _load_facts(row["facts_json"])
            row_chat_id = _builder_chat_id(
                facts=facts,
                session_id=row["session_id"],
                human_id=row["human_id"],
            )
            available_chat_ids_set.add(row_chat_id)
            event_type = str(row["event_type"] or "")
            if event_type in {"intent_committed", "delivery_succeeded"}:
                update_id = str(facts.get("update_id") or facts.get("message_id") or row["event_id"] or row["created_at"] or "unknown")
                entry = legacy_groups.setdefault(
                    update_id,
                    {
                        "chat_id": row_chat_id,
                        "session_id": str(row["session_id"] or "") or None,
                        "human_id": _builder_human_id(facts=facts, human_id=row["human_id"]),
                        "user_turn": None,
                        "assistant_turn": None,
                    },
                )
                timestamp = _format_builder_timestamp(row["created_at"])
                if event_type == "intent_committed":
                    message_text = str(facts.get("message_text") or facts.get("text") or row["summary"] or "").strip()
                    if message_text:
                        entry["user_turn"] = {
                            "message_id": f"builder-user-{update_id}",
                            "role": "user",
                            "content": message_text,
                            "timestamp": timestamp,
                            "metadata": {
                                "chat_id": row_chat_id,
                                "update_id": update_id,
                                "source_event_type": "intent_committed",
                                "onboarding_step": str(facts.get("step") or "").strip() or None,
                                "onboarding_completed": bool(facts.get("completed")),
                            },
                        }
                elif event_type == "delivery_succeeded":
                    delivered_text = str(
                        facts.get("delivered_text")
                        or facts.get("reply_text")
                        or facts.get("message_text")
                        or row["summary"]
                        or ""
                    ).strip()
                    if delivered_text:
                        entry["assistant_turn"] = {
                            "message_id": f"builder-assistant-{update_id}",
                            "role": "assistant",
                            "content": delivered_text,
                            "timestamp": timestamp,
                            "metadata": {
                                "chat_id": row_chat_id,
                                "update_id": update_id,
                                "source_event_type": "delivery_succeeded",
                            },
                        }
                continue

            session_value = str(row["session_id"] or "")
            request_value = str(row["request_id"] or row["trace_ref"] or row["event_id"] or "")
            if session_value and request_value:
                bridge_groups.setdefault((session_value, request_value), []).append(row)

        for entry in legacy_groups.values():
            chat_value = str(entry["chat_id"] or "unknown")
            if selected_chat_id is not None and chat_value != selected_chat_id:
                continue
            conversation = _conversation_for(
                chat_value,
                entry.get("session_id"),
                entry.get("human_id"),
            )
            user_turn = entry.get("user_turn")
            assistant_turn = entry.get("assistant_turn")
            if isinstance(user_turn, dict):
                conversation["turns"].append(user_turn)
            if isinstance(assistant_turn, dict):
                conversation["turns"].append(assistant_turn)

        session_values: dict[str, dict[str, dict[str, str]]] = {}
        human_values: dict[str, dict[str, dict[str, str]]] = {}
        session_histories: dict[str, dict[str, list[dict[str, str]]]] = {}
        collapsed_duplicate_sim_write_count = 0
        for _, group in sorted(
            bridge_groups.items(),
            key=lambda item: (
                str(item[1][0]["created_at"] or ""),
                int(item[1][0]["row_order"] or 0),
                str(item[0][0]),
                str(item[0][1]),
            ),
        ):
            normalized_group = [dict(row) for row in group]
            first_row = normalized_group[0]
            first_facts = _load_facts(first_row.get("facts_json"))
            session_value = str(first_row.get("session_id") or "") or None
            human_value = _builder_human_id(facts=first_facts, human_id=first_row.get("human_id"))
            chat_value = _builder_chat_id(
                facts=first_facts,
                session_id=first_row.get("session_id"),
                human_id=first_row.get("human_id"),
            )
            if selected_chat_id is not None and chat_value != selected_chat_id:
                continue
            conversation = _conversation_for(chat_value, session_value, human_value)
            known_values = session_values.setdefault(str(session_value or chat_value), {})
            known_human_values = human_values.setdefault(str(human_value or ""), {}) if human_value else {}
            combined_known_values = {**known_human_values, **known_values}
            known_histories = session_histories.setdefault(str(session_value or chat_value), {})

            memory_write_row = next((row for row in normalized_group if str(row.get("event_type") or "") == "memory_write_requested"), None)
            memory_write_result_row = next((row for row in normalized_group if str(row.get("event_type") or "") == "memory_write_succeeded"), None)
            memory_read_request_row = next((row for row in normalized_group if str(row.get("event_type") or "") == "memory_read_requested"), None)
            memory_read_result_row = next(
                (
                    row
                    for row in normalized_group
                    if str(row.get("event_type") or "") in {"memory_read_succeeded", "memory_read_abstained"}
                ),
                None,
            )
            influence_row = next((row for row in normalized_group if str(row.get("event_type") or "") == "plugin_or_chip_influence_recorded"), None)
            tool_result_row = next((row for row in normalized_group if str(row.get("event_type") or "") == "tool_result_received"), None)

            if memory_write_row is not None:
                write_facts = _load_facts(memory_write_row.get("facts_json"))
                result_facts = _load_facts(memory_write_result_row.get("facts_json")) if memory_write_result_row is not None else {}
                accepted_count = int(result_facts.get("accepted_count", 0) or 0)
                request_id_value = str(memory_write_row.get("request_id") or memory_write_row.get("event_id") or "").strip()
                observations = write_facts.get("observations")
                if isinstance(observations, list):
                    for item in observations:
                        if not isinstance(item, dict):
                            continue
                        text = str(item.get("text") or "").strip()
                        predicate = str(item.get("predicate") or "").strip()
                        value = str(item.get("value") or "").strip()
                        if not text:
                            continue
                        memory_role = str(item.get("memory_role") or write_facts.get("memory_role") or "").strip().lower()
                        if (
                            request_id_value.lower().startswith("sim:")
                            and accepted_count > 0
                            and memory_role == "current_state"
                            and predicate
                            and value
                            and _known_value_matches(known_values, predicate=predicate, value=value)
                        ):
                            collapsed_duplicate_sim_write_count += 1
                            continue
                        conversation["turns"].append(
                            {
                                "message_id": request_id_value,
                                "role": "user",
                                "content": text,
                                "timestamp": _format_builder_timestamp(memory_write_row.get("created_at")),
                                "metadata": {
                                    "chat_id": chat_value,
                                    "channel_kind": "telegram",
                                    "component": str(memory_write_row.get("component") or ""),
                                    "request_id": str(memory_write_row.get("request_id") or ""),
                                    "trace_ref": str(memory_write_row.get("trace_ref") or ""),
                                    "source_event_id": str(memory_write_row.get("event_id") or ""),
                                    "source_event_type": "memory_write_requested",
                                    "memory_kind": "observation",
                                    "subject": str(_normalize_builder_human_id(item.get("subject")) or human_value or ""),
                                    "predicate": predicate,
                                    "value": value,
                                    "operation": str(item.get("operation") or write_facts.get("operation") or ""),
                                    "memory_role": str(item.get("memory_role") or write_facts.get("memory_role") or ""),
                                },
                            }
                        )
                        if accepted_count > 0 and predicate and value:
                            write_timestamp = _format_builder_timestamp(memory_write_row.get("created_at"))
                            history = known_histories.setdefault(predicate, [])
                            history.append(
                                {
                                    "value": value,
                                    "timestamp": str(write_timestamp or ""),
                                    "message_id": request_id_value,
                                }
                            )
                            _remember_known_value(
                                known_values,
                                predicate=predicate,
                                value=value,
                                timestamp=write_timestamp,
                                message_id=request_id_value,
                                evidence_text=text,
                            )
                            if human_value:
                                _remember_known_value(
                                    known_human_values,
                                    predicate=predicate,
                                    value=value,
                                    timestamp=write_timestamp,
                                    message_id=request_id_value,
                                    evidence_text=text,
                                )
                            distinct_value_count = len(
                                {
                                    str(item.get("value") or "").strip()
                                    for item in history
                                    if str(item.get("value") or "").strip()
                                }
                            )
                            base_probe_id = (
                                f"{conversation['session_id']}:write:{request_id_value}:{_probe_key(predicate)}"
                            )
                            _append_lookup_probes(
                                conversation,
                                base_probe_id=base_probe_id,
                                subject=str(_normalize_builder_human_id(item.get("subject")) or human_value or ""),
                                predicate=predicate,
                                expected_value=value,
                            )
                            _prune_historical_probes(
                                conversation,
                                predicate=predicate,
                                as_of=write_timestamp,
                            )
                            _append_historical_probe(
                                conversation,
                                base_probe_id=base_probe_id,
                                subject=str(_normalize_builder_human_id(item.get("subject")) or human_value or ""),
                                predicate=predicate,
                                expected_value=value,
                                as_of=write_timestamp,
                                distinct_value_count=distinct_value_count,
                            )
                        elif (
                            accepted_count > 0
                            and predicate
                            and str(item.get("operation") or write_facts.get("operation") or "").strip().lower() == "delete"
                        ):
                            _prune_historical_probes(
                                conversation,
                                predicate=predicate,
                                as_of=_format_builder_timestamp(memory_write_row.get("created_at")),
                            )
                            _forget_known_value(known_values, predicate=predicate)
                            if human_value:
                                _forget_known_value(known_human_values, predicate=predicate)
                events = write_facts.get("events")
                if isinstance(events, list):
                    for item in events:
                        if not isinstance(item, dict):
                            continue
                        text = str(item.get("text") or "").strip()
                        predicate = str(item.get("predicate") or "").strip()
                        value = str(item.get("value") or "").strip()
                        if not text:
                            continue
                        subject = str(_normalize_builder_human_id(item.get("subject")) or human_value or "")
                        conversation["turns"].append(
                            {
                                "message_id": request_id_value,
                                "role": "user",
                                "content": text,
                                "timestamp": _format_builder_timestamp(memory_write_row.get("created_at")),
                                "metadata": {
                                    "chat_id": chat_value,
                                    "channel_kind": "telegram",
                                    "component": str(memory_write_row.get("component") or ""),
                                    "request_id": str(memory_write_row.get("request_id") or ""),
                                    "trace_ref": str(memory_write_row.get("trace_ref") or ""),
                                    "source_event_id": str(memory_write_row.get("event_id") or ""),
                                    "source_event_type": "memory_write_requested",
                                    "memory_kind": "event",
                                    "subject": subject,
                                    "predicate": predicate,
                                    "value": value,
                                    "operation": str(item.get("operation") or write_facts.get("operation") or ""),
                                    "memory_role": str(item.get("memory_role") or write_facts.get("memory_role") or ""),
                                },
                            }
                        )
                        if accepted_count > 0 and predicate and value:
                            history = known_histories.setdefault(predicate, [])
                            history.append(
                                {
                                    "value": value,
                                    "timestamp": str(_format_builder_timestamp(memory_write_row.get("created_at")) or ""),
                                    "message_id": request_id_value,
                                }
                            )
                            base_probe_id = (
                                f"{conversation['session_id']}:write:{request_id_value}:{_probe_key(predicate)}"
                            )
                            summary_predicate = _telegram_event_summary_predicate(predicate)
                            if summary_predicate:
                                _remember_known_value(
                                    known_values,
                                    predicate=summary_predicate,
                                    value=value,
                                    timestamp=_format_builder_timestamp(memory_write_row.get("created_at")),
                                    message_id=request_id_value,
                                    evidence_text=text,
                                )
                                if human_value:
                                    _remember_known_value(
                                        known_human_values,
                                        predicate=summary_predicate,
                                        value=value,
                                        timestamp=_format_builder_timestamp(memory_write_row.get("created_at")),
                                        message_id=request_id_value,
                                        evidence_text=text,
                                    )
                                _append_lookup_probes(
                                    conversation,
                                    base_probe_id=f"{base_probe_id}:latest",
                                    subject=subject,
                                    predicate=summary_predicate,
                                    expected_value=value,
                                    include_current_state=True,
                                    include_evidence=False,
                                )

            if influence_row is not None and memory_write_row is None:
                influence_facts = _load_facts(influence_row.get("facts_json"))
                query_payload = influence_facts.get("detected_profile_fact_query")
                query_payload_dict = query_payload if isinstance(query_payload, dict) else {}
                event_query_payload = influence_facts.get("detected_memory_event_query")
                event_query_payload_dict = event_query_payload if isinstance(event_query_payload, dict) else {}
                bridge_mode_hint = ""
                routing_decision_hint = ""
                if tool_result_row is not None:
                    tool_facts_hint = _load_facts(tool_result_row.get("facts_json"))
                    bridge_mode_hint = str(tool_facts_hint.get("bridge_mode") or "").strip()
                    routing_decision_hint = str(tool_facts_hint.get("routing_decision") or "").strip()
                query_text = _query_message(query_payload_dict)
                if bridge_mode_hint in {"memory_telegram_event_history", "memory_telegram_event_latest"} or routing_decision_hint in {
                    "memory_telegram_event_query",
                    "memory_telegram_event_latest_query",
                }:
                    query_text = _event_query_message(event_query_payload_dict)
                elif bridge_mode_hint == "memory_profile_fact_explanation" or routing_decision_hint == "memory_profile_fact_explanation":
                    query_text = _explanation_question(
                        predicate=_query_predicate(query_payload_dict),
                        label=str(query_payload_dict.get("label") or "").strip() or None,
                    ) or query_text
                if query_text:
                    event_query_kind = str(event_query_payload_dict.get("query_kind") or "").strip() or None
                    event_query_predicate = str(event_query_payload_dict.get("predicate") or "").strip() or None
                    event_query_label = str(event_query_payload_dict.get("label") or "").strip() or None
                    conversation["turns"].append(
                        {
                            "message_id": str(influence_row.get("request_id") or influence_row.get("event_id") or ""),
                            "role": "user",
                            "content": query_text,
                            "timestamp": _format_builder_timestamp(influence_row.get("created_at")),
                            "metadata": {
                                "chat_id": chat_value,
                                "channel_kind": "telegram",
                                "component": str(influence_row.get("component") or ""),
                                "request_id": str(influence_row.get("request_id") or ""),
                                "trace_ref": str(influence_row.get("trace_ref") or ""),
                                "source_event_id": str(influence_row.get("event_id") or ""),
                                "source_event_type": "plugin_or_chip_influence_recorded",
                                "fact_name": str(query_payload_dict.get("fact_name") or "").strip() or None,
                                "label": event_query_label or str(query_payload_dict.get("label") or "").strip() or None,
                                "predicate": event_query_predicate or _query_predicate(query_payload_dict),
                                "query_kind": event_query_kind or str(query_payload_dict.get("query_kind") or "").strip() or None,
                            },
                        }
                    )
            elif memory_read_request_row is not None and memory_write_row is None:
                read_request_facts = _load_facts(memory_read_request_row.get("facts_json"))
                query_text = _read_request_question(
                    read_request_facts,
                    session_id=str(memory_read_request_row.get("session_id") or ""),
                )
                if query_text:
                    conversation["turns"].append(
                        {
                            "message_id": str(memory_read_request_row.get("request_id") or memory_read_request_row.get("event_id") or ""),
                            "role": "user",
                            "content": query_text,
                            "timestamp": _format_builder_timestamp(memory_read_request_row.get("created_at")),
                            "metadata": {
                                "chat_id": chat_value,
                                "channel_kind": "telegram",
                                "component": str(memory_read_request_row.get("component") or ""),
                                "request_id": str(memory_read_request_row.get("request_id") or ""),
                                "trace_ref": str(memory_read_request_row.get("trace_ref") or ""),
                                "source_event_id": str(memory_read_request_row.get("event_id") or ""),
                                "source_event_type": "memory_read_requested",
                                "memory_role": str(read_request_facts.get("memory_role") or "").strip() or None,
                                "method": str(read_request_facts.get("method") or "").strip() or None,
                                "subject": str(_normalize_builder_human_id(read_request_facts.get("subject")) or human_value or "") or None,
                                "predicate": str(read_request_facts.get("predicate") or "").strip() or None,
                                "predicate_prefix": str(read_request_facts.get("predicate_prefix") or "").strip() or None,
                                "query_kind": str(read_request_facts.get("method") or "").strip() or None,
                            },
                        }
                    )

            if tool_result_row is not None:
                tool_facts = _load_facts(tool_result_row.get("facts_json"))
                bridge_mode = str(tool_facts.get("bridge_mode") or "").strip()
                routing_decision = str(tool_facts.get("routing_decision") or "").strip()
                response_text = None
                predicate = str(tool_facts.get("predicate") or "").strip() or None
                value = str(tool_facts.get("value") or "").strip() or None
                if bridge_mode == "memory_profile_fact_update" or routing_decision == "memory_profile_fact_observation":
                    response_text = _update_answer(predicate, value) or str(tool_result_row.get("summary") or "").strip()
                elif bridge_mode == "memory_telegram_event_update" or routing_decision == "memory_telegram_event_observation":
                    response_text = _event_update_answer(predicate, value) or str(tool_result_row.get("summary") or "").strip()
                elif bridge_mode == "memory_profile_fact" or routing_decision == "memory_profile_fact_query":
                    query_payload = _load_facts(influence_row.get("facts_json")).get("detected_profile_fact_query") if influence_row is not None else {}
                    query_predicate = _query_predicate(query_payload if isinstance(query_payload, dict) else {}) or predicate
                    expected_value = _effective_query_value(combined_known_values, query_predicate, value)
                    response_text = _query_answer(
                        predicate=query_predicate,
                        value=expected_value,
                    )
                    _append_lookup_probes(
                        conversation,
                        base_probe_id=(
                            f"{conversation['session_id']}:query:{str(tool_result_row.get('request_id') or tool_result_row.get('event_id') or '')}:{_probe_key(query_predicate)}"
                        ),
                        subject=str(human_value or ""),
                        predicate=query_predicate,
                        expected_value=expected_value,
                    )
                    if response_text is None:
                        response_text = str(tool_result_row.get("summary") or "").strip()
                elif bridge_mode == "memory_telegram_event_latest" or routing_decision == "memory_telegram_event_latest_query":
                    query_payload = _load_facts(influence_row.get("facts_json")).get("detected_memory_event_query") if influence_row is not None else {}
                    query_payload_dict = query_payload if isinstance(query_payload, dict) else {}
                    query_predicate = str(query_payload_dict.get("predicate") or "").strip() or predicate
                    label = str(query_payload_dict.get("label") or tool_facts.get("label") or "").strip() or None
                    summary_predicate = (
                        str(tool_facts.get("summary_predicate") or "").strip()
                        or _telegram_event_summary_predicate(query_predicate)
                    )
                    expected_value = _effective_query_value(combined_known_values, summary_predicate)
                    if not expected_value:
                        latest_records = _event_history_records(known_histories, predicate=query_predicate)
                        expected_value = _ordered_unique_event_values(latest_records)[-1] if latest_records else None
                    response_text = _event_query_answer(
                        predicate=query_predicate,
                        label=label,
                        query_kind="latest_event",
                        records=(
                            [{"predicate": query_predicate or "", "value": expected_value or "", "timestamp": "", "message_id": ""}]
                            if expected_value
                            else []
                        ),
                    ) or str(tool_result_row.get("summary") or "").strip()
                    if summary_predicate and expected_value:
                        _append_lookup_probes(
                            conversation,
                            base_probe_id=(
                                f"{conversation['session_id']}:latest:{str(tool_result_row.get('request_id') or tool_result_row.get('event_id') or '')}:{_probe_key(summary_predicate)}"
                            ),
                            subject=str(human_value or ""),
                            predicate=summary_predicate,
                            expected_value=expected_value,
                            include_current_state=True,
                            include_evidence=False,
                        )
                elif bridge_mode == "memory_telegram_event_history" or routing_decision == "memory_telegram_event_query":
                    query_payload = _load_facts(influence_row.get("facts_json")).get("detected_memory_event_query") if influence_row is not None else {}
                    query_payload_dict = query_payload if isinstance(query_payload, dict) else {}
                    query_predicate = str(query_payload_dict.get("predicate") or "").strip() or predicate
                    label = str(query_payload_dict.get("label") or tool_facts.get("label") or "").strip() or None
                    query_kind = str(query_payload_dict.get("query_kind") or "recent_events").strip() or "recent_events"
                    event_records = _event_history_records(known_histories, predicate=query_predicate)
                    response_text = _event_query_answer(
                        predicate=query_predicate,
                        label=label,
                        query_kind=query_kind,
                        records=event_records,
                    ) or str(tool_result_row.get("summary") or "").strip()
                elif bridge_mode == "memory_profile_fact_explanation" or routing_decision == "memory_profile_fact_explanation":
                    query_payload = _load_facts(influence_row.get("facts_json")).get("detected_profile_fact_query") if influence_row is not None else {}
                    query_predicate = _query_predicate(query_payload if isinstance(query_payload, dict) else {}) or predicate
                    expected_value = _effective_query_value(combined_known_values, query_predicate, value)
                    _append_lookup_probes(
                        conversation,
                        base_probe_id=(
                            f"{conversation['session_id']}:explanation:{str(tool_result_row.get('request_id') or tool_result_row.get('event_id') or '')}:{_probe_key(query_predicate)}"
                        ),
                        subject=str(human_value or ""),
                        predicate=query_predicate,
                        expected_value=expected_value,
                    )
                    response_text = _explanation_answer(
                        predicate=query_predicate,
                        value=expected_value,
                        evidence_text=_effective_query_evidence_text(combined_known_values, query_predicate),
                    ) or str(tool_result_row.get("summary") or "").strip()
                elif bridge_mode == "memory_profile_identity" or routing_decision == "memory_profile_identity_summary":
                    response_text = _identity_answer(combined_known_values) or str(tool_result_row.get("summary") or "").strip()
                    prefix = str(tool_facts.get("predicate_prefix") or "profile.").strip() or "profile."
                    for probe_index, (identity_predicate, identity_value) in enumerate(
                        _known_identity_records(combined_known_values, predicate_prefix=prefix),
                        start=1,
                    ):
                        _append_lookup_probes(
                            conversation,
                            base_probe_id=(
                                f"{conversation['session_id']}:identity:{str(tool_result_row.get('request_id') or tool_result_row.get('event_id') or '')}:{probe_index}:{_probe_key(identity_predicate)}"
                            ),
                            subject=str(human_value or ""),
                            predicate=identity_predicate,
                            expected_value=identity_value,
                        )
                if response_text:
                    conversation["turns"].append(
                        {
                            "message_id": str(tool_result_row.get("request_id") or tool_result_row.get("event_id") or ""),
                            "role": "assistant",
                            "content": response_text,
                            "timestamp": _format_builder_timestamp(tool_result_row.get("created_at")),
                            "metadata": {
                                "chat_id": chat_value,
                                "channel_kind": "telegram",
                                "component": str(tool_result_row.get("component") or ""),
                                "request_id": str(tool_result_row.get("request_id") or ""),
                                "trace_ref": str(tool_result_row.get("trace_ref") or ""),
                                "source_event_id": str(tool_result_row.get("event_id") or ""),
                                "source_event_type": "tool_result_received",
                                "keepability": tool_facts.get("keepability"),
                                "promotion_disposition": tool_facts.get("promotion_disposition"),
                                "bridge_mode": bridge_mode or None,
                                "routing_decision": routing_decision or None,
                                "fact_name": str(tool_facts.get("fact_name") or "").strip() or None,
                                "label": str(tool_facts.get("label") or "").strip() or None,
                                "predicate": predicate,
                                "value": value,
                                "value_found": tool_facts.get("value_found"),
                                "evidence_summary": str(tool_facts.get("evidence_summary") or "").strip() or None,
                            },
                        }
                    )
            elif memory_read_result_row is not None and memory_write_row is None:
                read_result_facts = _load_facts(memory_read_result_row.get("facts_json"))
                response_text = _read_result_message(
                    read_result_facts,
                    event_type=str(memory_read_result_row.get("event_type") or "").strip(),
                )
                if response_text:
                    conversation["turns"].append(
                        {
                            "message_id": str(memory_read_result_row.get("request_id") or memory_read_result_row.get("event_id") or ""),
                            "role": "assistant",
                            "content": response_text,
                            "timestamp": _format_builder_timestamp(memory_read_result_row.get("created_at")),
                            "metadata": {
                                "chat_id": chat_value,
                                "channel_kind": "telegram",
                                "component": str(memory_read_result_row.get("component") or ""),
                                "request_id": str(memory_read_result_row.get("request_id") or ""),
                                "trace_ref": str(memory_read_result_row.get("trace_ref") or ""),
                                "source_event_id": str(memory_read_result_row.get("event_id") or ""),
                                "source_event_type": str(memory_read_result_row.get("event_type") or "").strip(),
                                "memory_role": str(read_result_facts.get("memory_role") or "").strip() or None,
                                "method": str(read_result_facts.get("method") or "").strip() or None,
                                "reason": str(read_result_facts.get("reason") or "").strip() or None,
                                "record_count": int(read_result_facts.get("record_count", 0) or 0),
                                **_read_result_trace_metadata(
                                    read_result_facts,
                                    event_type=str(memory_read_result_row.get("event_type") or "").strip(),
                                    known_values=combined_known_values,
                                ),
                            },
                        }
                    )

        available_chat_ids = sorted(available_chat_ids_set)
        for conversation in conversations_by_key.values():
            conversation["turns"].sort(key=_turn_sort_key)
            session_key = str(
                conversation.get("session_id")
                or (conversation.get("metadata", {}) or {}).get("chat_id")
                or ""
            )
            final_values = session_values.get(session_key, {})
            reconciled_probes: list[dict[str, object]] = []
            seen_lookup_probe_keys: set[tuple[str, str, str, str]] = set()
            for probe in conversation.get("probes", []):
                if not isinstance(probe, dict):
                    continue
                normalized_probe = dict(probe)
                probe_type = str(normalized_probe.get("probe_type") or "").strip()
                if probe_type in {"current_state", "evidence"}:
                    effective_predicate, final_value = _resolve_probe_predicate_and_value(
                        final_values,
                        predicate=normalized_probe.get("predicate"),
                        expected_value=normalized_probe.get("expected_value"),
                    )
                    expected_value = str(normalized_probe.get("expected_value") or "").strip() or None
                    if probe_type == "current_state" and expected_value and not final_value:
                        continue
                    if expected_value and final_value and expected_value != final_value:
                        continue
                    if effective_predicate:
                        normalized_probe["predicate"] = effective_predicate
                    dedupe_key = (
                        probe_type,
                        str(normalized_probe.get("subject") or "").strip(),
                        str(normalized_probe.get("predicate") or "").strip(),
                        str(normalized_probe.get("expected_value") or "").strip(),
                    )
                    if all(dedupe_key):
                        if dedupe_key in seen_lookup_probe_keys:
                            continue
                        seen_lookup_probe_keys.add(dedupe_key)
                reconciled_probes.append(normalized_probe)
            conversation["probes"] = reconciled_probes

        normalized_conversations = [
            conversation
            for conversation in conversations_by_key.values()
            if any(str(turn.get("role") or "").strip() == "user" for turn in conversation.get("turns", []) if isinstance(turn, dict))
        ]
        normalized_conversations.sort(key=_conversation_sort_key)
        synthetic_regression_conversations = [
            conversation
            for conversation in normalized_conversations
            if _is_synthetic_builder_regression_conversation(conversation)
        ]
        organic_conversations = [
            conversation
            for conversation in normalized_conversations
            if not _is_synthetic_builder_regression_conversation(conversation)
        ]
        kept_synthetic_regression_fallback = False
        used_organic_conversation_filter = False
        if selected_chat_id is None:
            if organic_conversations:
                normalized_conversations = organic_conversations
                used_organic_conversation_filter = bool(synthetic_regression_conversations)
            elif synthetic_regression_conversations and not keep_synthetic_regression_when_only_available:
                normalized_conversations = []
                used_organic_conversation_filter = True
            elif synthetic_regression_conversations:
                kept_synthetic_regression_fallback = True
        if limit > 0:
            normalized_conversations = normalized_conversations[-limit:]

        return (
            available_chat_ids,
            {
                "source": "spark_builder_state_db",
                "writable_roles": ["user"],
                "conversations": normalized_conversations,
                "trace": {
                    "organic_conversation_count": len(organic_conversations),
                    "synthetic_regression_conversation_count": len(synthetic_regression_conversations),
                    "used_organic_conversation_filter": used_organic_conversation_filter,
                    "kept_synthetic_regression_fallback": kept_synthetic_regression_fallback,
                    "collapsed_duplicate_sim_write_count": collapsed_duplicate_sim_write_count,
                    "collapsed_duplicate_supporting_sim_write_count": collapsed_duplicate_sim_write_count,
                },
            },
        )

    rows = _load_supported_builder_rows(scan_all=False)
    if not rows:
        raise ValueError(f"No supported Builder Telegram state-db events found in {state_db_path}.")

    available_chat_ids, normalized_payload = _normalize_supported_rows(
        rows,
        keep_synthetic_regression_when_only_available=False,
    )
    used_full_supported_scan = False
    used_supporting_history_backfill = False
    supporting_history_backfill_row_count = 0
    if (
        selected_chat_id is None
        and not list(normalized_payload.get("conversations", []))
        and len(rows) >= raw_event_limit
    ):
        rows = _load_supported_builder_rows(scan_all=True)
        available_chat_ids, normalized_payload = _normalize_supported_rows(
            rows,
            keep_synthetic_regression_when_only_available=True,
        )
        used_full_supported_scan = True
    if not used_full_supported_scan and selected_chat_id is None:
        base_row_count = len(rows)
        backfill_human_ids = sorted(
            {
                str((conversation.get("metadata") or {}).get("human_id") or "").strip()
                for conversation in normalized_payload.get("conversations", [])
                if isinstance(conversation, dict) and _conversation_needs_supporting_history(conversation)
            }
        )
        if backfill_human_ids:
            backfill_rows = _load_supported_builder_rows_for_humans(backfill_human_ids)
            merged_rows = _merge_supported_rows(rows, backfill_rows)
            if len(merged_rows) > len(rows):
                rows = merged_rows
                available_chat_ids, normalized_payload = _normalize_supported_rows(
                    rows,
                    keep_synthetic_regression_when_only_available=False,
                    supporting_history_human_ids=backfill_human_ids,
                )
                used_supporting_history_backfill = True
                supporting_history_backfill_row_count = max(len(rows) - base_row_count, 0)

    validation = validate_shadow_replay_payload(normalized_payload)
    contract = {
        "layer_name": "SparkBuilderTelegramStateDBAdapter",
        "description": "Reads Spark Intelligence Builder Telegram state.db events and normalizes both legacy telegram_runtime rows and bridge-native memory_orchestrator plus researcher_bridge rows into the Spark shadow replay schema.",
        "source_component": "telegram_runtime|memory_orchestrator|researcher_bridge",
        "source_table": "builder_events",
        "event_types": [
            "intent_committed",
            "delivery_succeeded",
            "memory_write_requested",
            "memory_write_succeeded",
            "memory_read_requested",
            "memory_read_succeeded",
            "memory_read_abstained",
            "plugin_or_chip_influence_recorded",
            "tool_result_received",
        ],
        "writable_roles": ["user"],
    }
    return {
        "builder_home": str(root),
        "state_db": str(state_db_path),
        "selected_chat_id": selected_chat_id,
        "available_chat_ids": available_chat_ids,
        "contract": contract,
        "normalized": normalized_payload,
        "validation": validation,
        "conversation_count": len(normalized_payload.get("conversations", [])),
        "event_count": len(rows),
        "trace": {
            "scan_mode": "full_supported_rows" if used_full_supported_scan or selected_chat_id is not None else "recent_supported_window",
            "used_full_supported_scan": used_full_supported_scan,
            "used_supporting_history_backfill": used_supporting_history_backfill,
            "supporting_history_backfill_row_count": supporting_history_backfill_row_count,
            "collapsed_duplicate_sim_write_count": int(
                normalized_payload.get("trace", {}).get("collapsed_duplicate_sim_write_count", 0) or 0
            ),
            "collapsed_duplicate_supporting_sim_write_count": int(
                normalized_payload.get("trace", {}).get("collapsed_duplicate_supporting_sim_write_count", 0)
                or normalized_payload.get("trace", {}).get("collapsed_duplicate_sim_write_count", 0)
                or 0
            ),
            "raw_event_limit": raw_event_limit,
        },
    }


def _run_spark_builder_state_telegram_intake(
    builder_home: str,
    output_dir: str,
    *,
    limit: int = 25,
    chat_id: str | None = None,
    repo_sources: list[str] | None = None,
    repo_source_manifest_files: list[str] | None = None,
) -> dict:
    effective_repo_source_manifest_files = _default_builder_repo_source_manifest_files(
        builder_home,
        repo_source_manifest_files=repo_source_manifest_files,
    )
    normalization = _normalize_builder_telegram_state_db(builder_home, limit=limit, chat_id=chat_id)
    normalized = normalization["normalized"]
    evaluations, adapter = _execute_shadow_replay_payload(normalized)
    shadow_payload = _build_shadow_report_payload_from_evaluations(evaluations)
    failure_taxonomy = _build_shadow_failure_taxonomy_payload(
        shadow_payload,
        source_mode="builder_state_telegram",
        source_dir=str(Path(builder_home)),
        source_files=[str(normalization["state_db"])],
        contract=normalization["contract"],
    )
    snapshot = adapter.sdk.export_knowledge_base_snapshot()
    resolved_repo_sources = _resolve_repo_source_files(
        repo_sources=repo_sources,
        repo_source_manifest_files=effective_repo_source_manifest_files,
    )
    compile_result = scaffold_spark_knowledge_base(
        output_dir,
        snapshot,
        vault_title="Spark Builder Telegram State Knowledge Base",
        repo_sources=resolved_repo_sources,
        filed_outputs=_build_shadow_report_filed_outputs(shadow_payload)
        + _build_shadow_failure_taxonomy_filed_outputs(shadow_payload)
        + _build_shadow_turn_audit_filed_outputs(shadow_payload),
    )
    health_report = build_spark_kb_health_report(output_dir)
    turn_audit = _build_shadow_turn_audit_payload(shadow_payload)
    return {
        "builder_home": str(Path(builder_home)),
        "state_db": str(normalization["state_db"]),
        "contract": normalization["contract"],
        "normalization": normalization,
        "shadow_report": shadow_payload["report"],
        "failure_taxonomy": failure_taxonomy,
        "turn_audit": turn_audit,
        "snapshot": snapshot,
        "compile_result": compile_result,
        "health_report": health_report,
        "summary": {
            "conversation_count": int(normalization.get("conversation_count", 0) or 0),
            "selected_chat_id": normalization.get("selected_chat_id"),
            "accepted_writes": int(shadow_payload.get("report", {}).get("summary", {}).get("accepted_writes", 0) or 0),
            "rejected_writes": int(shadow_payload.get("report", {}).get("summary", {}).get("rejected_writes", 0) or 0),
            "skipped_turns": int(shadow_payload.get("report", {}).get("summary", {}).get("skipped_turns", 0) or 0),
            "reference_turns": int(shadow_payload.get("report", {}).get("summary", {}).get("reference_turns", 0) or 0),
            "rejected_user_turn_count": int(turn_audit.get("summary", {}).get("rejected_user_turn_count", 0) or 0),
            "reference_turn_count": int(turn_audit.get("summary", {}).get("reference_turn_count", 0) or 0),
            "kb_valid": bool(health_report.get("valid", False)),
            "kb_filed_output_count": int(compile_result.get("filed_output_count", 0) or 0),
            "repo_source_manifest_file_count": len(effective_repo_source_manifest_files),
        },
        "trace": {
            "operation": "run_spark_builder_state_telegram_intake",
            "limit": limit,
            "chat_id": chat_id,
        },
    }


def _default_builder_repo_source_manifest_files(
    builder_home: str,
    *,
    repo_source_manifest_files: list[str] | None = None,
) -> list[str]:
    if repo_source_manifest_files:
        return list(repo_source_manifest_files)
    root = Path(builder_home)
    if root.is_file():
        root = root.parent
    attachments_snapshot = root / "attachments.snapshot.json"
    if attachments_snapshot.exists() and attachments_snapshot.is_file():
        return [str(attachments_snapshot)]
    return []


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


def _resolve_manifest_path_item(manifest_path: Path, value: object) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = manifest_path.parent / path
    return path


def _append_unique_repo_source_path(
    resolved_items: list[str],
    seen: set[str],
    path: Path | None,
) -> None:
    if path is None or not path.exists() or not path.is_file():
        return
    normalized = str(path)
    if normalized in seen:
        return
    seen.add(normalized)
    resolved_items.append(normalized)


def _discover_repo_source_files_from_root(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []

    discovered: list[Path] = []
    seen: set[str] = set()

    def _add(path: Path) -> None:
        _append_unique_repo_source_path(discovered_strings, seen, path)

    discovered_strings: list[str] = []
    for relative in (
        "spark-chip.json",
        "CLAUDE.md",
        "README.md",
        "README.mdx",
        "README.txt",
        "PROJECT.md",
        "ARCHITECTURE.md",
    ):
        _add(root / relative)

    for pattern in ("*.md", "*.mdx"):
        for path in sorted(root.glob(pattern)):
            _add(path)

    docs_dir = root / "docs"
    if docs_dir.exists() and docs_dir.is_dir():
        docs_paths = [
            path
            for pattern in ("*.md", "*.mdx")
            for path in sorted(docs_dir.rglob(pattern))
            if path.is_file()
        ]
        for path in docs_paths[:8]:
            _add(path)

    return [Path(item) for item in discovered_strings]


def _load_repo_source_manifest(manifest_file: str) -> list[str]:
    manifest_path = Path(manifest_file)
    payload = _load_json_file(manifest_path)
    if isinstance(payload, list):
        if not all(isinstance(item, str) for item in payload):
            raise ValueError("Repo source manifest file must contain a JSON list of strings.")
        return _load_string_list_manifest(manifest_file, key="repo_sources", label="Repo source manifest file")

    if not isinstance(payload, dict):
        raise ValueError(
            "Repo source manifest file must contain a JSON list of strings, "
            "an object with a 'repo_sources' list, or a Spark Builder attachments snapshot."
        )

    repo_sources = payload.get("repo_sources")
    if isinstance(repo_sources, list) and all(isinstance(item, str) for item in repo_sources):
        return _load_string_list_manifest(manifest_file, key="repo_sources", label="Repo source manifest file")

    resolved_items: list[str] = []
    seen: set[str] = set()
    records = payload.get("records")
    if isinstance(records, list):
        for record in records:
            if not isinstance(record, dict):
                continue
            for key in ("manifest_path", "hook_manifest_path"):
                _append_unique_repo_source_path(
                    resolved_items,
                    seen,
                    _resolve_manifest_path_item(manifest_path, record.get(key)),
                )
            repo_root = _resolve_manifest_path_item(manifest_path, record.get("repo_root"))
            for discovered in _discover_repo_source_files_from_root(repo_root or Path()):
                _append_unique_repo_source_path(resolved_items, seen, discovered)

    for key in ("chip_roots", "path_roots"):
        roots = payload.get(key)
        if not isinstance(roots, list):
            continue
        for raw_root in roots:
            root = _resolve_manifest_path_item(manifest_path, raw_root)
            for discovered in _discover_repo_source_files_from_root(root or Path()):
                _append_unique_repo_source_path(resolved_items, seen, discovered)

    if resolved_items:
        return resolved_items

    raise ValueError(
        "Repo source manifest file must contain a 'repo_sources' list or a Spark Builder attachments snapshot "
        "with records/chip_roots/path_roots that resolve to source files."
    )


def _kb_page_slug(value: object) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
    slug = normalized.strip("-") or "item"
    max_length = 80
    if len(slug) <= max_length:
        return slug
    import hashlib

    digest = hashlib.sha1(slug.encode("utf-8")).hexdigest()[:8]
    trimmed = slug[: max_length - len(digest) - 1].rstrip("-")
    return f"{trimmed}-{digest}" if trimmed else digest


def _extract_markdown_section(text: str, heading: str) -> str | None:
    pattern = rf"{re.escape(heading)}\n(.*?)(?:\n## |\Z)"
    match = re.search(pattern, text, flags=re.DOTALL)
    if not match:
        return None
    return match.group(1).strip() or None


def _load_kb_current_state_support(kb_dir: str | Path, *, subject: str, predicate: str) -> dict:
    page_path = Path(kb_dir) / "wiki" / "current-state" / f"{_kb_page_slug(subject)}-{_kb_page_slug(predicate)}.md"
    if not page_path.exists():
        return {
            "exists": False,
            "page_path": str(page_path),
            "value": None,
            "supporting_evidence_links": [],
            "supporting_evidence_count": 0,
        }
    text = page_path.read_text(encoding="utf-8")
    value = _extract_markdown_section(text, "## Value")
    supporting = _extract_markdown_section(text, "## Supporting Evidence") or ""
    evidence_links = [
        line.removeprefix("- ").strip()
        for line in supporting.splitlines()
        if line.strip().startswith("- [[evidence/")
    ]
    return {
        "exists": True,
        "page_path": str(page_path),
        "value": value,
        "supporting_evidence_links": evidence_links,
        "supporting_evidence_count": len(evidence_links),
    }


def _extract_spark_query_cases(normalized_payload: dict) -> list[dict]:
    raw_conversations = normalized_payload.get("conversations", [])
    if not isinstance(raw_conversations, list):
        return []
    cases: list[dict] = []
    for conversation in raw_conversations:
        if not isinstance(conversation, dict):
            continue
        conversation_id = str(conversation.get("conversation_id") or "").strip()
        conversation_metadata = dict(conversation.get("metadata", {}))
        subject = str(conversation_metadata.get("human_id") or "user").strip() or "user"
        turns = [turn for turn in conversation.get("turns", []) if isinstance(turn, dict)]
        assistant_by_request_id: dict[str, dict] = {}
        for turn in turns:
            turn_metadata = dict(turn.get("metadata", {}))
            if str(turn.get("role") or "") != "assistant":
                continue
            request_id = str(turn_metadata.get("request_id") or "").strip()
            if not request_id:
                continue
            assistant_by_request_id[request_id] = turn
        for turn in turns:
            turn_metadata = dict(turn.get("metadata", {}))
            if str(turn.get("role") or "") != "user":
                continue
            if str(turn_metadata.get("source_event_type") or "") != "plugin_or_chip_influence_recorded":
                continue
            predicate = str(turn_metadata.get("predicate") or "").strip()
            if not predicate:
                continue
            request_id = str(turn_metadata.get("request_id") or "").strip()
            paired_assistant = assistant_by_request_id.get(request_id, {})
            paired_metadata = dict(paired_assistant.get("metadata", {}))
            cases.append(
                {
                    "conversation_id": conversation_id,
                    "request_id": request_id,
                    "question": str(turn.get("content") or "").strip(),
                    "subject": subject,
                    "predicate": predicate,
                    "label": str(turn_metadata.get("label") or "").strip() or None,
                    "query_kind": str(turn_metadata.get("query_kind") or "").strip() or None,
                    "assistant_summary": str(paired_assistant.get("content") or "").strip() or None,
                    "bridge_mode": str(paired_metadata.get("bridge_mode") or "").strip() or None,
                    "routing_decision": str(paired_metadata.get("routing_decision") or "").strip() or None,
                    "value_found": paired_metadata.get("value_found"),
                    "evidence_summary": str(paired_metadata.get("evidence_summary") or "").strip() or None,
                }
            )
    return cases


def _build_spark_conversation_subject_index(normalized_payload: dict) -> dict[str, str]:
    raw_conversations = normalized_payload.get("conversations", [])
    if not isinstance(raw_conversations, list):
        return {}
    subject_by_conversation_id: dict[str, str] = {}
    for conversation in raw_conversations:
        if not isinstance(conversation, dict):
            continue
        conversation_id = str(conversation.get("conversation_id") or "").strip()
        metadata = conversation.get("metadata")
        if not conversation_id or not isinstance(metadata, dict):
            continue
        subject = str(metadata.get("human_id") or "").strip()
        if subject:
            subject_by_conversation_id[conversation_id] = subject
    return subject_by_conversation_id


def _classify_spark_memory_kb_comparison(
    *,
    memory_only_found: bool,
    supporting_evidence_count: int,
    value_found: object,
    bridge_mode: str | None,
    routing_decision: str | None,
    query_kind: str | None,
) -> str:
    if memory_only_found:
        return "answered_with_kb_support" if supporting_evidence_count > 0 else "answered_without_kb_support"
    if value_found is False:
        return "missing_fact_query"
    if bridge_mode or routing_decision or query_kind:
        return "query_abstention_without_kb_support"
    return "unclassified_query_gap"


def _spark_conversation_scenario_bucket(conversation_id: str) -> str:
    normalized = conversation_id.lower()
    if "boundary_abstention" in normalized:
        return "boundary_abstention_cleanroom" if "cleanroom" in normalized else "boundary_abstention"
    if "quality_lane_gauntlet" in normalized:
        return "quality_lane_gauntlet"
    if "loaded_context_abstention" in normalized:
        return "loaded_context_abstention"
    if "temporal_conflict_gauntlet" in normalized:
        return "temporal_conflict_gauntlet"
    if "identity_under_recency_pressure" in normalized:
        return "identity_under_recency_pressure"
    if "regression-user" in normalized:
        return "regression"
    return "other"


def _spark_gap_action_bucket(scenario_bucket: str) -> str:
    if scenario_bucket == "boundary_abstention_cleanroom":
        return "expected_cleanroom_boundary"
    if scenario_bucket == "regression":
        return "regression_candidate"
    if scenario_bucket == "quality_lane_gauntlet":
        return "gauntlet_candidate"
    return "other_candidate"


def _build_snapshot_subject_predicate_index(snapshot: dict[str, object]) -> dict[tuple[str, str], dict[str, int]]:
    index: dict[tuple[str, str], dict[str, int]] = {}
    for row in snapshot.get("current_state", []):
        if not isinstance(row, dict):
            continue
        subject = str(row.get("subject") or "").strip()
        predicate = str(row.get("predicate") or "").strip()
        if not subject or not predicate:
            continue
        bucket = index.setdefault((subject, predicate), {"current_state_count": 0, "observation_count": 0})
        bucket["current_state_count"] += 1
    for row in snapshot.get("observations", []):
        if not isinstance(row, dict):
            continue
        subject = str(row.get("subject") or "").strip()
        predicate = str(row.get("predicate") or "").strip()
        if not subject or not predicate:
            continue
        bucket = index.setdefault((subject, predicate), {"current_state_count": 0, "observation_count": 0})
        bucket["observation_count"] += 1
    return index


def _run_spark_memory_kb_ablation(
    data_file: str,
    *,
    limit: int | None = None,
    promotion_policy_file: str | None = None,
    recompile_kb_output_dir: str | None = None,
) -> dict:
    payload = json.loads(Path(data_file).read_text(encoding="utf-8"))
    normalization = payload.get("normalization")
    if not isinstance(normalization, dict):
        raise ValueError("Spark intake payload must contain a normalization object.")
    normalized = normalization.get("normalized")
    if not isinstance(normalized, dict):
        raise ValueError("Spark intake payload must contain normalization.normalized.")
    compile_result = payload.get("compile_result")
    if not isinstance(compile_result, dict):
        raise ValueError("Spark intake payload must contain a compile_result object.")
    kb_dir = str(compile_result.get("output_dir") or "").strip()
    if not kb_dir:
        raise ValueError("Spark intake payload must contain compile_result.output_dir.")
    adapter = None
    if promotion_policy_file:
        promotion_policy_rows = _load_spark_memory_kb_promotion_policy_rows(promotion_policy_file)
        writable_roles = normalized.get("writable_roles")
        configured_roles = (
            tuple(str(role) for role in writable_roles)
            if isinstance(writable_roles, list)
            else ("user",)
        )
        adapter = SparkShadowIngestAdapter(
            writable_roles=configured_roles,
            promotion_policy_rows=tuple(promotion_policy_rows),
        )

    _, adapter = _execute_shadow_replay_payload(normalized, adapter=adapter)
    snapshot = adapter.sdk.export_knowledge_base_snapshot()
    effective_compile_result = compile_result
    effective_health_report = None
    if recompile_kb_output_dir:
        effective_compile_result = scaffold_spark_knowledge_base(
            recompile_kb_output_dir,
            snapshot,
            vault_title="Spark Memory KB Ablation Replay",
        )
        kb_dir = str(effective_compile_result.get("output_dir") or "").strip()
        effective_health_report = build_spark_kb_health_report(kb_dir)
    snapshot_index = _build_snapshot_subject_predicate_index(snapshot)
    query_cases = _extract_spark_query_cases(normalized)
    if limit is not None:
        query_cases = query_cases[:limit]

    comparisons: list[dict] = []
    memory_only_answered = 0
    memory_plus_kb_answered = 0
    answer_delta_count = 0
    kb_supported_query_count = 0
    missing_fact_query_count = 0
    resolved_missing_fact_query_count = 0
    unresolved_missing_fact_query_count = 0
    classification_counts: dict[str, int] = {}
    missing_fact_predicates: dict[str, int] = {}
    missing_fact_examples_by_predicate: dict[str, list[dict[str, str | None]]] = {}
    missing_fact_scenarios: dict[str, int] = {}
    missing_fact_predicates_by_scenario: dict[str, dict[str, int]] = {}
    missing_fact_action_buckets: dict[str, int] = {}
    missing_fact_predicates_by_action_bucket: dict[str, dict[str, int]] = {}
    missing_fact_source_coverage: dict[str, int] = {}
    total_memory_only_latency_ms = 0.0
    total_memory_plus_kb_latency_ms = 0.0

    for case in query_cases:
        scenario_bucket = _spark_conversation_scenario_bucket(str(case["conversation_id"]))
        action_bucket = _spark_gap_action_bucket(scenario_bucket)
        snapshot_support = snapshot_index.get((str(case["subject"]), str(case["predicate"])), {})
        replay_current_state_count = int(snapshot_support.get("current_state_count", 0) or 0)
        replay_observation_count = int(snapshot_support.get("observation_count", 0) or 0)
        has_replay_source_evidence = replay_current_state_count > 0 or replay_observation_count > 0
        memory_start = perf_counter()
        memory_only = adapter.sdk.explain_answer(
            AnswerExplanationRequest(
                question=case["question"],
                subject=case["subject"],
                predicate=case["predicate"],
            )
        )
        memory_only_latency_ms = (perf_counter() - memory_start) * 1000.0

        kb_start = perf_counter()
        kb_support = _load_kb_current_state_support(
            kb_dir,
            subject=str(case["subject"]),
            predicate=str(case["predicate"]),
        )
        kb_lookup_latency_ms = (perf_counter() - kb_start) * 1000.0

        memory_only_answer = str(memory_only.answer or "").strip() or None
        kb_value = str(kb_support.get("value") or "").strip() or None
        memory_plus_kb_answer = memory_only_answer or kb_value
        memory_plus_kb_found = bool(memory_only.found or kb_value)
        answer_changed = memory_only_answer != memory_plus_kb_answer
        supporting_evidence_count = int(kb_support.get("supporting_evidence_count", 0) or 0)

        if memory_only.found:
            memory_only_answered += 1
        if memory_plus_kb_found:
            memory_plus_kb_answered += 1
        if answer_changed:
            answer_delta_count += 1
        if supporting_evidence_count > 0:
            kb_supported_query_count += 1
        if case.get("value_found") is False:
            missing_fact_query_count += 1
            if memory_only.found or memory_plus_kb_found:
                resolved_missing_fact_query_count += 1
            else:
                unresolved_missing_fact_query_count += 1
            predicate_key = str(case["predicate"])
            missing_fact_predicates[predicate_key] = missing_fact_predicates.get(predicate_key, 0) + 1
            missing_fact_scenarios[scenario_bucket] = missing_fact_scenarios.get(scenario_bucket, 0) + 1
            scenario_predicates = missing_fact_predicates_by_scenario.setdefault(scenario_bucket, {})
            scenario_predicates[predicate_key] = scenario_predicates.get(predicate_key, 0) + 1
            missing_fact_action_buckets[action_bucket] = missing_fact_action_buckets.get(action_bucket, 0) + 1
            action_predicates = missing_fact_predicates_by_action_bucket.setdefault(action_bucket, {})
            action_predicates[predicate_key] = action_predicates.get(predicate_key, 0) + 1
            source_coverage_key = "with_replay_source_evidence" if has_replay_source_evidence else "without_replay_source_evidence"
            missing_fact_source_coverage[source_coverage_key] = missing_fact_source_coverage.get(source_coverage_key, 0) + 1
            examples = missing_fact_examples_by_predicate.setdefault(predicate_key, [])
            if len(examples) < 2:
                examples.append(
                    {
                        "conversation_id": str(case["conversation_id"]),
                        "question": str(case["question"]),
                        "label": str(case["label"]) if case.get("label") is not None else None,
                        "evidence_summary": str(case["evidence_summary"]) if case.get("evidence_summary") is not None else None,
                    }
                )

        classification = _classify_spark_memory_kb_comparison(
            memory_only_found=memory_only.found,
            supporting_evidence_count=supporting_evidence_count,
            value_found=case.get("value_found"),
            bridge_mode=case.get("bridge_mode"),
            routing_decision=case.get("routing_decision"),
            query_kind=case.get("query_kind"),
        )
        classification_counts[classification] = classification_counts.get(classification, 0) + 1

        total_memory_only_latency_ms += memory_only_latency_ms
        total_memory_plus_kb_latency_ms += memory_only_latency_ms + kb_lookup_latency_ms
        comparisons.append(
            {
                "conversation_id": case["conversation_id"],
                "request_id": case["request_id"],
                "question": case["question"],
                "subject": case["subject"],
                "predicate": case["predicate"],
                "label": case["label"],
                "scenario_bucket": scenario_bucket,
                "action_bucket": action_bucket,
                "query_kind": case["query_kind"],
                "bridge_mode": case["bridge_mode"],
                "routing_decision": case["routing_decision"],
                "value_found": case["value_found"],
                "evidence_summary": case["evidence_summary"],
                "replay_source_evidence": {
                    "has_source_evidence": has_replay_source_evidence,
                    "current_state_count": replay_current_state_count,
                    "observation_count": replay_observation_count,
                },
                "memory_only": {
                    "found": memory_only.found,
                    "answer": memory_only_answer,
                    "memory_role": memory_only.memory_role,
                    "explanation": memory_only.explanation,
                    "provenance_count": len(memory_only.provenance),
                    "evidence_count": len(memory_only.evidence),
                    "event_count": len(memory_only.events),
                    "latency_ms": round(memory_only_latency_ms, 3),
                },
                "memory_plus_kb": {
                    "found": memory_plus_kb_found,
                    "answer": memory_plus_kb_answer,
                    "kb_page_exists": bool(kb_support.get("exists")),
                    "kb_page_path": kb_support.get("page_path"),
                    "kb_value": kb_value,
                    "supporting_evidence_count": supporting_evidence_count,
                    "supporting_evidence_links": list(kb_support.get("supporting_evidence_links", [])),
                    "latency_ms": round(memory_only_latency_ms + kb_lookup_latency_ms, 3),
                },
                "delta": {
                    "answer_changed": answer_changed,
                    "kb_added_support": supporting_evidence_count > 0,
                    "assistant_summary": case["assistant_summary"],
                },
                "classification": classification,
            }
        )

    query_count = len(query_cases)
    source_backed_answered_counts_by_missing_predicate: dict[str, int] = {}
    source_backed_examples_by_missing_predicate: dict[str, list[dict[str, str | None]]] = {}
    if missing_fact_predicates:
        missing_predicate_keys = set(missing_fact_predicates)
        for item in comparisons:
            predicate = str(item.get("predicate") or "")
            if predicate not in missing_predicate_keys:
                continue
            replay_source_evidence = item.get("replay_source_evidence")
            if not isinstance(replay_source_evidence, dict):
                continue
            if not bool(replay_source_evidence.get("has_source_evidence")):
                continue
            memory_only = item.get("memory_only")
            if not isinstance(memory_only, dict) or not bool(memory_only.get("found")):
                continue
            source_backed_answered_counts_by_missing_predicate[predicate] = (
                source_backed_answered_counts_by_missing_predicate.get(predicate, 0) + 1
            )
            examples = source_backed_examples_by_missing_predicate.setdefault(predicate, [])
            if len(examples) < 2:
                examples.append(
                    {
                        "conversation_id": str(item.get("conversation_id") or ""),
                        "question": str(item.get("question") or ""),
                        "answer": str(memory_only.get("answer") or "") or None,
                        "scenario_bucket": str(item.get("scenario_bucket") or "") or None,
                    }
                )

    return {
        "input_file": str(Path(data_file)),
        "kb_dir": kb_dir,
        "compile_result": effective_compile_result,
        "health_report": effective_health_report,
        "summary": {
            "query_count": query_count,
            "memory_only_answered": memory_only_answered,
            "memory_plus_kb_answered": memory_plus_kb_answered,
            "answer_delta_count": answer_delta_count,
            "kb_supported_query_count": kb_supported_query_count,
            "missing_fact_query_count": missing_fact_query_count,
            "resolved_missing_fact_query_count": resolved_missing_fact_query_count,
            "unresolved_missing_fact_query_count": unresolved_missing_fact_query_count,
            "missing_fact_predicates": dict(sorted(missing_fact_predicates.items())),
            "missing_fact_scenarios": dict(sorted(missing_fact_scenarios.items())),
            "missing_fact_predicates_by_scenario": {
                scenario: dict(sorted(predicate_counts.items()))
                for scenario, predicate_counts in sorted(missing_fact_predicates_by_scenario.items())
            },
            "missing_fact_action_buckets": dict(sorted(missing_fact_action_buckets.items())),
            "missing_fact_predicates_by_action_bucket": {
                action_bucket: dict(sorted(predicate_counts.items()))
                for action_bucket, predicate_counts in sorted(missing_fact_predicates_by_action_bucket.items())
            },
            "missing_fact_source_coverage": dict(sorted(missing_fact_source_coverage.items())),
            "source_backed_answered_counts_by_missing_predicate": dict(
                sorted(source_backed_answered_counts_by_missing_predicate.items())
            ),
            "source_backed_examples_by_missing_predicate": {
                predicate: examples
                for predicate, examples in sorted(source_backed_examples_by_missing_predicate.items())
            },
            "missing_fact_examples_by_predicate": {
                predicate: examples
                for predicate, examples in sorted(missing_fact_examples_by_predicate.items())
            },
            "classification_counts": classification_counts,
            "average_memory_only_latency_ms": round(total_memory_only_latency_ms / query_count, 3) if query_count else 0.0,
            "average_memory_plus_kb_latency_ms": round(total_memory_plus_kb_latency_ms / query_count, 3) if query_count else 0.0,
        },
        "comparisons": comparisons,
        "trace": {
            "operation": "run_spark_memory_kb_ablation",
            "limit": limit,
            "promotion_policy_file": str(Path(promotion_policy_file)) if promotion_policy_file else None,
            "recompile_kb_output_dir": str(Path(recompile_kb_output_dir)) if recompile_kb_output_dir else None,
            "kb_source": "recompiled_from_replay_snapshot" if recompile_kb_output_dir else "input_compile_result",
        },
    }


def _build_spark_memory_kb_sourcing_slice(
    ablation_file: str,
    *,
    data_file: str | None = None,
    exemplars_per_predicate: int = 1,
) -> dict:
    ablation_payload = _load_json_file(ablation_file)
    if not isinstance(ablation_payload, dict):
        raise ValueError("Spark ablation payload must be a JSON object.")
    summary = ablation_payload.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("Spark ablation payload must contain a summary object.")
    missing_fact_examples_by_predicate = summary.get("missing_fact_examples_by_predicate")
    if not isinstance(missing_fact_examples_by_predicate, dict):
        raise ValueError("Spark ablation summary must contain missing_fact_examples_by_predicate.")
    source_backed_examples_by_missing_predicate = summary.get("source_backed_examples_by_missing_predicate")
    if not isinstance(source_backed_examples_by_missing_predicate, dict):
        raise ValueError("Spark ablation summary must contain source_backed_examples_by_missing_predicate.")

    resolved_data_file = str(data_file or ablation_payload.get("input_file") or "").strip()
    if not resolved_data_file:
        raise ValueError("Provide a Spark intake data file or use an ablation payload with input_file.")
    intake_payload = _load_json_file(resolved_data_file)
    if not isinstance(intake_payload, dict):
        raise ValueError("Spark intake payload must be a JSON object.")
    normalization = intake_payload.get("normalization")
    if not isinstance(normalization, dict):
        raise ValueError("Spark intake payload must contain a normalization object.")
    normalized = normalization.get("normalized")
    if not isinstance(normalized, dict):
        raise ValueError("Spark intake payload must contain normalization.normalized.")
    conversations = normalized.get("conversations")
    if not isinstance(conversations, list):
        raise ValueError("Spark intake payload must contain normalization.normalized.conversations.")

    conversation_lookup: dict[str, dict] = {}
    for conversation in conversations:
        if not isinstance(conversation, dict):
            continue
        conversation_id = str(conversation.get("conversation_id") or "").strip()
        if conversation_id:
            conversation_lookup[conversation_id] = conversation

    predicate_targets: list[dict[str, object]] = []
    selected_conversation_ids: list[str] = []
    seen_conversation_ids: set[str] = set()
    missing_predicates = sorted(str(predicate).strip() for predicate in missing_fact_examples_by_predicate if str(predicate).strip())

    for predicate in missing_predicates:
        missing_examples_raw = missing_fact_examples_by_predicate.get(predicate, [])
        source_examples_raw = source_backed_examples_by_missing_predicate.get(predicate, [])
        missing_examples = [item for item in missing_examples_raw if isinstance(item, dict)]
        source_examples = [item for item in source_examples_raw if isinstance(item, dict)][: max(0, exemplars_per_predicate)]
        for item in [*missing_examples, *source_examples]:
            conversation_id = str(item.get("conversation_id") or "").strip()
            if conversation_id and conversation_id not in seen_conversation_ids:
                seen_conversation_ids.add(conversation_id)
                selected_conversation_ids.append(conversation_id)
        predicate_targets.append(
            {
                "predicate": predicate,
                "missing_query_count": int((summary.get("missing_fact_predicates") or {}).get(predicate, 0) or 0),
                "source_backed_answered_count": int(
                    (summary.get("source_backed_answered_counts_by_missing_predicate") or {}).get(predicate, 0) or 0
                ),
                "missing_examples": missing_examples,
                "source_backed_examples": source_examples,
            }
        )

    selected_conversations = [
        conversation_lookup[conversation_id]
        for conversation_id in selected_conversation_ids
        if conversation_id in conversation_lookup
    ]
    missing_from_source = [conversation_id for conversation_id in selected_conversation_ids if conversation_id not in conversation_lookup]

    filtered_normalized = dict(normalized)
    filtered_normalized["conversations"] = selected_conversations

    return {
        "input_ablation_file": str(Path(ablation_file)),
        "input_data_file": str(Path(resolved_data_file)),
        "summary": {
            "predicate_count": len(predicate_targets),
            "selected_conversation_count": len(selected_conversations),
            "missing_from_source_count": len(missing_from_source),
            "selected_conversation_ids": selected_conversation_ids,
            "missing_predicates": missing_predicates,
        },
        "predicate_targets": predicate_targets,
        "missing_from_source": missing_from_source,
        "normalization": {
            "normalized": filtered_normalized,
        },
        "compile_result": intake_payload.get("compile_result"),
        "trace": {
            "operation": "build_spark_memory_kb_sourcing_slice",
            "exemplars_per_predicate": exemplars_per_predicate,
        },
    }


def _parse_utc_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _format_utc_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _select_source_backed_write_turn(
    source_conversation: dict,
    *,
    predicate: str,
    answer: str | None,
) -> dict | None:
    turns = source_conversation.get("turns", [])
    if not isinstance(turns, list):
        return None
    candidates = []
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        metadata = turn.get("metadata")
        if not isinstance(metadata, dict):
            continue
        if str(turn.get("role") or "").strip().lower() != "user":
            continue
        if str(metadata.get("source_event_type") or "").strip().lower() != "memory_write_requested":
            continue
        if str(metadata.get("predicate") or "").strip() != predicate:
            continue
        candidates.append(turn)
    if not candidates:
        return None
    normalized_answer = str(answer or "").strip()
    if normalized_answer:
        exact = [turn for turn in candidates if str(dict(turn.get("metadata", {})).get("value") or "").strip() == normalized_answer]
        if exact:
            candidates = exact
    return copy.deepcopy(candidates[-1])


def _inject_source_backed_write_turns(
    normalized: dict,
    *,
    predicate_targets: list[dict],
) -> tuple[dict, list[dict], list[dict]]:
    conversations = normalized.get("conversations", [])
    if not isinstance(conversations, list):
        raise ValueError("Sourcing slice must contain normalization.normalized.conversations.")

    conversation_lookup: dict[str, dict] = {}
    for conversation in conversations:
        if not isinstance(conversation, dict):
            continue
        conversation_id = str(conversation.get("conversation_id") or "").strip()
        if conversation_id:
            conversation_lookup[conversation_id] = conversation

    injected_records: list[dict] = []
    missing_sources: list[dict] = []
    rewritten_conversations = copy.deepcopy(conversations)
    rewritten_lookup = {
        str(conversation.get("conversation_id") or "").strip(): conversation
        for conversation in rewritten_conversations
        if isinstance(conversation, dict) and str(conversation.get("conversation_id") or "").strip()
    }

    for target in predicate_targets:
        if not isinstance(target, dict):
            continue
        predicate = str(target.get("predicate") or "").strip()
        if not predicate:
            continue
        source_examples = target.get("source_backed_examples")
        missing_examples = target.get("missing_examples")
        if not isinstance(source_examples, list) or not source_examples:
            missing_sources.append({"predicate": predicate, "reason": "no_source_backed_example"})
            continue
        source_example = next((item for item in source_examples if isinstance(item, dict)), None)
        if source_example is None:
            missing_sources.append({"predicate": predicate, "reason": "invalid_source_backed_example"})
            continue
        source_conversation_id = str(source_example.get("conversation_id") or "").strip()
        source_conversation = conversation_lookup.get(source_conversation_id)
        if source_conversation is None:
            missing_sources.append(
                {
                    "predicate": predicate,
                    "reason": "source_conversation_missing",
                    "conversation_id": source_conversation_id,
                }
            )
            continue
        source_turn = _select_source_backed_write_turn(
            source_conversation,
            predicate=predicate,
            answer=str(source_example.get("answer") or "").strip() or None,
        )
        if source_turn is None:
            missing_sources.append(
                {
                    "predicate": predicate,
                    "reason": "source_write_turn_missing",
                    "conversation_id": source_conversation_id,
                }
            )
            continue
        if not isinstance(missing_examples, list):
            continue
        for missing_index, missing_example in enumerate(missing_examples):
            if not isinstance(missing_example, dict):
                continue
            target_conversation_id = str(missing_example.get("conversation_id") or "").strip()
            target_conversation = rewritten_lookup.get(target_conversation_id)
            if target_conversation is None:
                missing_sources.append(
                    {
                        "predicate": predicate,
                        "reason": "target_conversation_missing",
                        "conversation_id": target_conversation_id,
                    }
                )
                continue
            target_metadata = target_conversation.get("metadata")
            if not isinstance(target_metadata, dict):
                target_metadata = {}
                target_conversation["metadata"] = target_metadata
            target_turns = target_conversation.get("turns")
            if not isinstance(target_turns, list):
                target_turns = []
                target_conversation["turns"] = target_turns
            cloned_turn = copy.deepcopy(source_turn)
            cloned_metadata = cloned_turn.get("metadata")
            if not isinstance(cloned_metadata, dict):
                cloned_metadata = {}
                cloned_turn["metadata"] = cloned_metadata
            first_timestamp = None
            if target_turns:
                first_timestamp = _parse_utc_timestamp(str(dict(target_turns[0]).get("timestamp") or ""))
            if first_timestamp is not None:
                first_timestamp = first_timestamp - timedelta(seconds=missing_index + 1)
                cloned_turn["timestamp"] = _format_utc_timestamp(first_timestamp)
            cloned_message_id = (
                f"{cloned_turn.get('message_id', 'source-write')}:source-backed:{re.sub(r'[^a-z0-9]+', '-', predicate.lower()).strip('-')}"
                f":{missing_index + 1}"
            )
            target_human_id = str(target_metadata.get("human_id") or "").strip()
            target_chat_id = str(target_metadata.get("chat_id") or "").strip()
            cloned_turn["message_id"] = cloned_message_id
            cloned_turn["role"] = "user"
            cloned_metadata["subject"] = target_human_id or str(cloned_metadata.get("subject") or "")
            cloned_metadata["chat_id"] = target_chat_id or str(cloned_metadata.get("chat_id") or "")
            cloned_metadata["request_id"] = cloned_message_id
            cloned_metadata["source_backed_clone"] = True
            cloned_metadata["source_backed_predicate"] = predicate
            cloned_metadata["source_backed_from_conversation_id"] = source_conversation_id
            cloned_metadata["source_backed_from_message_id"] = str(source_turn.get("message_id") or "")
            cloned_metadata["source_backed_target_conversation_id"] = target_conversation_id
            target_turns.insert(0, cloned_turn)
            injected_records.append(
                {
                    "predicate": predicate,
                    "target_conversation_id": target_conversation_id,
                    "source_conversation_id": source_conversation_id,
                    "source_message_id": str(source_turn.get("message_id") or ""),
                    "cloned_message_id": cloned_message_id,
                    "value": str(cloned_metadata.get("value") or "").strip() or None,
                }
            )

    rewritten_normalized = dict(normalized)
    rewritten_normalized["conversations"] = rewritten_conversations
    return rewritten_normalized, injected_records, missing_sources


def _build_spark_memory_kb_source_backed_slice(
    sourcing_slice_file: str,
    output_dir: str,
) -> dict:
    sourcing_payload = _load_json_file(sourcing_slice_file)
    if not isinstance(sourcing_payload, dict):
        raise ValueError("Sourcing slice payload must be a JSON object.")
    predicate_targets = sourcing_payload.get("predicate_targets")
    if not isinstance(predicate_targets, list):
        raise ValueError("Sourcing slice payload must contain predicate_targets.")
    normalization = sourcing_payload.get("normalization")
    if not isinstance(normalization, dict):
        raise ValueError("Sourcing slice payload must contain a normalization object.")
    normalized = normalization.get("normalized")
    if not isinstance(normalized, dict):
        raise ValueError("Sourcing slice payload must contain normalization.normalized.")

    rewritten_normalized, injected_records, missing_sources = _inject_source_backed_write_turns(
        normalized,
        predicate_targets=predicate_targets,
    )
    _, adapter = _execute_shadow_replay_payload(rewritten_normalized)
    snapshot = adapter.sdk.export_knowledge_base_snapshot()
    compile_result = scaffold_spark_knowledge_base(
        output_dir,
        snapshot,
        vault_title="Spark Memory KB Source-Backed Slice",
    )
    health_report = build_spark_kb_health_report(output_dir)

    return {
        "input_sourcing_slice_file": str(Path(sourcing_slice_file)),
        "summary": {
            "predicate_count": len([item for item in predicate_targets if isinstance(item, dict)]),
            "injected_write_count": len(injected_records),
            "target_conversation_count": len({str(item.get('target_conversation_id') or '') for item in injected_records if str(item.get('target_conversation_id') or '')}),
            "missing_source_count": len(missing_sources),
        },
        "injected_writes": injected_records,
        "missing_sources": missing_sources,
        "normalization": {
            "normalized": rewritten_normalized,
        },
        "snapshot": snapshot,
        "compile_result": compile_result,
        "health_report": health_report,
        "trace": {
            "operation": "build_spark_memory_kb_source_backed_slice",
        },
    }


def _spark_memory_kb_query_key(row: dict) -> str:
    return "||".join(
        [
            str(row.get("conversation_id") or "").strip(),
            str(row.get("request_id") or "").strip(),
            str(row.get("predicate") or "").strip(),
            str(row.get("question") or "").strip(),
        ]
    )


def _spark_memory_kb_missing_query_status(row: dict) -> str:
    if not isinstance(row, dict) or row.get("value_found") is not False:
        return "not_missing_fact_query"
    memory_only = row.get("memory_only")
    memory_plus_kb = row.get("memory_plus_kb")
    memory_only_found = bool(isinstance(memory_only, dict) and memory_only.get("found"))
    memory_plus_kb_found = bool(isinstance(memory_plus_kb, dict) and memory_plus_kb.get("found"))
    if memory_only_found or memory_plus_kb_found:
        return "resolved_missing_fact_query"
    return "unresolved_missing_fact_query"


def _compare_spark_memory_kb_ablation(before_file: str, after_file: str) -> dict:
    before_payload = _load_json_file(before_file)
    after_payload = _load_json_file(after_file)
    if not isinstance(before_payload, dict) or not isinstance(after_payload, dict):
        raise ValueError("Spark ablation comparison requires two JSON objects.")

    before_rows = before_payload.get("comparisons")
    after_rows = after_payload.get("comparisons")
    if not isinstance(before_rows, list) or not isinstance(after_rows, list):
        raise ValueError("Spark ablation comparison requires comparisons lists in both payloads.")

    before_map = {
        _spark_memory_kb_query_key(row): row
        for row in before_rows
        if isinstance(row, dict) and _spark_memory_kb_query_key(row)
    }
    after_map = {
        _spark_memory_kb_query_key(row): row
        for row in after_rows
        if isinstance(row, dict) and _spark_memory_kb_query_key(row)
    }
    shared_keys = sorted(set(before_map) & set(after_map))

    transition_counts: dict[str, int] = {}
    resolved_missing_by_predicate: dict[str, int] = {}
    resolved_missing_by_scenario: dict[str, int] = {}
    resolved_missing_by_action_bucket: dict[str, int] = {}
    resolved_queries: list[dict[str, str | None]] = []
    still_unresolved_by_predicate: dict[str, int] = {}

    for key in shared_keys:
        before_row = before_map[key]
        after_row = after_map[key]
        before_status = _spark_memory_kb_missing_query_status(before_row)
        after_status = _spark_memory_kb_missing_query_status(after_row)
        transition_key = f"{before_status}->{after_status}"
        transition_counts[transition_key] = transition_counts.get(transition_key, 0) + 1

        if before_status == "unresolved_missing_fact_query" and after_status == "resolved_missing_fact_query":
            predicate = str(after_row.get("predicate") or "").strip()
            scenario_bucket = str(after_row.get("scenario_bucket") or "").strip()
            action_bucket = str(after_row.get("action_bucket") or "").strip()
            if predicate:
                resolved_missing_by_predicate[predicate] = resolved_missing_by_predicate.get(predicate, 0) + 1
            if scenario_bucket:
                resolved_missing_by_scenario[scenario_bucket] = resolved_missing_by_scenario.get(scenario_bucket, 0) + 1
            if action_bucket:
                resolved_missing_by_action_bucket[action_bucket] = (
                    resolved_missing_by_action_bucket.get(action_bucket, 0) + 1
                )
            if len(resolved_queries) < 10:
                resolved_queries.append(
                    {
                        "conversation_id": str(after_row.get("conversation_id") or "") or None,
                        "question": str(after_row.get("question") or "") or None,
                        "predicate": predicate or None,
                        "scenario_bucket": scenario_bucket or None,
                        "action_bucket": action_bucket or None,
                        "answer": str(dict(after_row.get("memory_only") or {}).get("answer") or "") or None,
                    }
                )
        if after_status == "unresolved_missing_fact_query":
            predicate = str(after_row.get("predicate") or "").strip()
            if predicate:
                still_unresolved_by_predicate[predicate] = still_unresolved_by_predicate.get(predicate, 0) + 1

    before_only_keys = sorted(set(before_map) - set(after_map))
    after_only_keys = sorted(set(after_map) - set(before_map))

    return {
        "before_file": str(Path(before_file)),
        "after_file": str(Path(after_file)),
        "summary": {
            "shared_query_count": len(shared_keys),
            "before_only_query_count": len(before_only_keys),
            "after_only_query_count": len(after_only_keys),
            "transition_counts": dict(sorted(transition_counts.items())),
            "resolved_missing_query_count": sum(resolved_missing_by_predicate.values()),
            "resolved_missing_by_predicate": dict(sorted(resolved_missing_by_predicate.items())),
            "resolved_missing_by_scenario": dict(sorted(resolved_missing_by_scenario.items())),
            "resolved_missing_by_action_bucket": dict(sorted(resolved_missing_by_action_bucket.items())),
            "still_unresolved_by_predicate": dict(sorted(still_unresolved_by_predicate.items())),
        },
        "resolved_queries": resolved_queries,
        "before_only_query_keys": before_only_keys,
        "after_only_query_keys": after_only_keys,
        "trace": {
            "operation": "compare_spark_memory_kb_ablation",
        },
    }


def _build_spark_memory_kb_policy_verdict(compare_file: str) -> dict:
    payload = _load_json_file(compare_file)
    if not isinstance(payload, dict):
        raise ValueError("Spark ablation comparison payload must be a JSON object.")
    summary = payload.get("summary")
    resolved_queries = payload.get("resolved_queries")
    if not isinstance(summary, dict) or not isinstance(resolved_queries, list):
        raise ValueError("Spark ablation comparison payload must contain summary and resolved_queries.")

    bucket_counts = summary.get("resolved_missing_by_action_bucket")
    if not isinstance(bucket_counts, dict):
        raise ValueError("Spark ablation comparison summary must contain resolved_missing_by_action_bucket.")

    verdicts: list[dict[str, object]] = []
    ordered_buckets = [
        "expected_cleanroom_boundary",
        "regression_candidate",
        "gauntlet_candidate",
    ]
    bucket_to_verdict = {
        "expected_cleanroom_boundary": {
            "verdict": "retain_boundary_by_default",
            "recommendation": (
                "Keep these lanes abstention-boundary in production unless a product requirement explicitly authorizes "
                "promotion of cleanroom-style facts into the target conversation."
            ),
        },
        "regression_candidate": {
            "verdict": "promotable_if_source_path_is_legitimate",
            "recommendation": (
                "These resolved once source evidence was present. Treat them as promotable sourcing candidates and "
                "audit the real upstream path that should write the fact into the target conversation."
            ),
        },
        "gauntlet_candidate": {
            "verdict": "expand_coverage_if_product_wants_recall",
            "recommendation": (
                "These resolved with source backing, so the memory/KB layer is capable. Decide whether the gauntlet "
                "lane should gain the same source coverage or intentionally remain sparse."
            ),
        },
    }

    for action_bucket in ordered_buckets:
        count = int(bucket_counts.get(action_bucket, 0) or 0)
        if count <= 0:
            continue
        resolved_bucket_queries: list[dict[str, str | None]] = []
        for row in resolved_queries:
            if not isinstance(row, dict):
                continue
            if str(row.get("action_bucket") or "").strip() != action_bucket:
                continue
            resolved_bucket_queries.append(
                {
                    "conversation_id": str(row.get("conversation_id") or "").strip() or None,
                    "predicate": str(row.get("predicate") or "").strip() or None,
                    "question": str(row.get("question") or "").strip() or None,
                    "answer": str(row.get("answer") or "").strip() or None,
                }
            )
        examples = resolved_bucket_queries[:3]
        policy = bucket_to_verdict.get(
            action_bucket,
            {
                "verdict": "needs_manual_review",
                "recommendation": "Review this action bucket manually before changing production promotion rules.",
            },
        )
        verdicts.append(
            {
                "action_bucket": action_bucket,
                "resolved_count": count,
                "verdict": policy["verdict"],
                "recommendation": policy["recommendation"],
                "resolved_queries": resolved_bucket_queries,
                "examples": examples,
            }
        )

    return {
        "input_compare_file": str(Path(compare_file)),
        "summary": {
            "resolved_missing_query_count": int(summary.get("resolved_missing_query_count", 0) or 0),
            "still_unresolved_query_count": sum(
                int(value or 0)
                for value in dict(summary.get("still_unresolved_by_predicate") or {}).values()
            ),
            "action_bucket_count": len(verdicts),
        },
        "policy_verdicts": verdicts,
        "trace": {
            "operation": "build_spark_memory_kb_policy_verdict",
        },
    }


def _build_spark_memory_kb_promotion_plan(policy_verdict_file: str, source_backed_slice_file: str) -> dict:
    policy_payload = _load_json_file(policy_verdict_file)
    source_backed_payload = _load_json_file(source_backed_slice_file)
    if not isinstance(policy_payload, dict) or not isinstance(source_backed_payload, dict):
        raise ValueError("Promotion plan inputs must be JSON objects.")

    policy_verdicts = policy_payload.get("policy_verdicts")
    injected_writes = source_backed_payload.get("injected_writes")
    if not isinstance(policy_verdicts, list) or not isinstance(injected_writes, list):
        raise ValueError("Promotion plan requires policy_verdicts and injected_writes lists.")

    injected_lookup: dict[tuple[str, str], dict] = {}
    for row in injected_writes:
        if not isinstance(row, dict):
            continue
        key = (
            str(row.get("target_conversation_id") or "").strip(),
            str(row.get("predicate") or "").strip(),
        )
        if key[0] and key[1]:
            injected_lookup[key] = row

    promotable_targets: list[dict[str, str | None]] = []
    optional_targets: list[dict[str, str | None]] = []
    excluded_targets: list[dict[str, str | None]] = []
    missing_lineage: list[dict[str, str | None]] = []

    for verdict in policy_verdicts:
        if not isinstance(verdict, dict):
            continue
        action_bucket = str(verdict.get("action_bucket") or "").strip()
        recommendation = str(verdict.get("recommendation") or "").strip() or None
        verdict_label = str(verdict.get("verdict") or "").strip() or None
        resolved_queries = verdict.get("resolved_queries")
        rows = resolved_queries if isinstance(resolved_queries, list) else verdict.get("examples")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            target_conversation_id = str(row.get("conversation_id") or "").strip()
            predicate = str(row.get("predicate") or "").strip()
            lineage = injected_lookup.get((target_conversation_id, predicate))
            target_row = {
                "action_bucket": action_bucket or None,
                "verdict": verdict_label,
                "recommendation": recommendation,
                "target_conversation_id": target_conversation_id or None,
                "predicate": predicate or None,
                "question": str(row.get("question") or "").strip() or None,
                "answer": str(row.get("answer") or "").strip() or None,
                "source_conversation_id": str(dict(lineage or {}).get("source_conversation_id") or "").strip() or None,
                "source_message_id": str(dict(lineage or {}).get("source_message_id") or "").strip() or None,
                "cloned_message_id": str(dict(lineage or {}).get("cloned_message_id") or "").strip() or None,
                "value": str(dict(lineage or {}).get("value") or "").strip() or None,
            }
            if lineage is None:
                missing_lineage.append(target_row)
            if action_bucket == "regression_candidate":
                promotable_targets.append(target_row)
            elif action_bucket == "gauntlet_candidate":
                optional_targets.append(target_row)
            elif action_bucket == "expected_cleanroom_boundary":
                excluded_targets.append(target_row)

    return {
        "input_policy_verdict_file": str(Path(policy_verdict_file)),
        "input_source_backed_slice_file": str(Path(source_backed_slice_file)),
        "summary": {
            "promotable_target_count": len(promotable_targets),
            "optional_target_count": len(optional_targets),
            "excluded_target_count": len(excluded_targets),
            "missing_lineage_count": len(missing_lineage),
        },
        "promotable_targets": promotable_targets,
        "optional_targets": optional_targets,
        "excluded_targets": excluded_targets,
        "missing_lineage": missing_lineage,
        "trace": {
            "operation": "build_spark_memory_kb_promotion_plan",
        },
    }


def _build_spark_memory_kb_promotion_policy(
    promotion_plan_file: str,
    *,
    include_optional: bool = False,
) -> dict:
    promotion_plan_payload = _load_json_file(promotion_plan_file)
    if not isinstance(promotion_plan_payload, dict):
        raise ValueError("Promotion policy input must be a JSON object.")

    promotable_targets = promotion_plan_payload.get("promotable_targets")
    optional_targets = promotion_plan_payload.get("optional_targets")
    excluded_targets = promotion_plan_payload.get("excluded_targets")
    if not isinstance(promotable_targets, list) or not isinstance(optional_targets, list) or not isinstance(excluded_targets, list):
        raise ValueError("Promotion policy requires promotable_targets, optional_targets, and excluded_targets.")

    def _policy_rows(targets: list[object], decision: str) -> list[dict[str, str | None]]:
        rows: list[dict[str, str | None]] = []
        for target in targets:
            if not isinstance(target, dict):
                continue
            rows.append(
                {
                    "policy_decision": decision,
                    "action_bucket": str(target.get("action_bucket") or "").strip() or None,
                    "verdict": str(target.get("verdict") or "").strip() or None,
                    "recommendation": str(target.get("recommendation") or "").strip() or None,
                    "target_conversation_id": str(target.get("target_conversation_id") or "").strip() or None,
                    "predicate": str(target.get("predicate") or "").strip() or None,
                    "question": str(target.get("question") or "").strip() or None,
                    "answer": str(target.get("answer") or "").strip() or None,
                    "source_conversation_id": str(target.get("source_conversation_id") or "").strip() or None,
                    "source_message_id": str(target.get("source_message_id") or "").strip() or None,
                    "cloned_message_id": str(target.get("cloned_message_id") or "").strip() or None,
                    "value": str(target.get("value") or "").strip() or None,
                }
            )
        return rows

    allowed_promotions = _policy_rows(
        [item for item in promotable_targets if isinstance(item, dict)]
        + ([item for item in optional_targets if isinstance(item, dict)] if include_optional else []),
        "allow",
    )
    deferred_promotions = [] if include_optional else _policy_rows(
        [item for item in optional_targets if isinstance(item, dict)],
        "defer",
    )
    blocked_promotions = _policy_rows(
        [item for item in excluded_targets if isinstance(item, dict)],
        "block",
    )

    distinct_target_ids = {
        str(row.get("target_conversation_id") or "").strip()
        for row in [*allowed_promotions, *deferred_promotions, *blocked_promotions]
        if str(row.get("target_conversation_id") or "").strip()
    }
    distinct_source_message_ids = {
        str(row.get("source_message_id") or "").strip()
        for row in [*allowed_promotions, *deferred_promotions, *blocked_promotions]
        if str(row.get("source_message_id") or "").strip()
    }

    return {
        "input_promotion_plan_file": str(Path(promotion_plan_file)),
        "summary": {
            "allow_count": len(allowed_promotions),
            "defer_count": len(deferred_promotions),
            "block_count": len(blocked_promotions),
            "include_optional": include_optional,
            "target_conversation_count": len(distinct_target_ids),
            "source_message_count": len(distinct_source_message_ids),
        },
        "allowed_promotions": allowed_promotions,
        "deferred_promotions": deferred_promotions,
        "blocked_promotions": blocked_promotions,
        "trace": {
            "operation": "build_spark_memory_kb_promotion_policy",
            "include_optional": include_optional,
        },
    }


def _build_spark_memory_kb_approved_promotion_slice(
    promotion_plan_file: str,
    source_backed_slice_file: str,
    output_dir: str,
    *,
    include_optional: bool = False,
) -> dict:
    promotion_plan_payload = _load_json_file(promotion_plan_file)
    source_backed_payload = _load_json_file(source_backed_slice_file)
    if not isinstance(promotion_plan_payload, dict) or not isinstance(source_backed_payload, dict):
        raise ValueError("Approved promotion slice inputs must be JSON objects.")

    promotable_targets = promotion_plan_payload.get("promotable_targets")
    optional_targets = promotion_plan_payload.get("optional_targets")
    normalization = source_backed_payload.get("normalization")
    if not isinstance(promotable_targets, list) or not isinstance(optional_targets, list) or not isinstance(normalization, dict):
        raise ValueError("Approved promotion slice requires promotable_targets, optional_targets, and normalization.")
    normalized = normalization.get("normalized")
    if not isinstance(normalized, dict):
        raise ValueError("Source-backed slice must contain normalization.normalized.")
    conversations = normalized.get("conversations")
    if not isinstance(conversations, list):
        raise ValueError("Source-backed slice must contain normalization.normalized.conversations.")

    selected_targets = [item for item in promotable_targets if isinstance(item, dict)]
    if include_optional:
        selected_targets.extend(item for item in optional_targets if isinstance(item, dict))

    selected_conversation_ids: set[str] = set()
    for target in selected_targets:
        target_conversation_id = str(target.get("target_conversation_id") or "").strip()
        source_conversation_id = str(target.get("source_conversation_id") or "").strip()
        if target_conversation_id:
            selected_conversation_ids.add(target_conversation_id)
        if source_conversation_id:
            selected_conversation_ids.add(source_conversation_id)

    filtered_conversations = [
        copy.deepcopy(conversation)
        for conversation in conversations
        if isinstance(conversation, dict)
        and str(conversation.get("conversation_id") or "").strip() in selected_conversation_ids
    ]
    filtered_normalized = dict(normalized)
    filtered_normalized["conversations"] = filtered_conversations

    _, adapter = _execute_shadow_replay_payload(filtered_normalized)
    snapshot = adapter.sdk.export_knowledge_base_snapshot()
    compile_result = scaffold_spark_knowledge_base(
        output_dir,
        snapshot,
        vault_title="Spark Memory KB Approved Promotion Slice",
    )
    health_report = build_spark_kb_health_report(output_dir)

    present_conversation_ids = {
        str(conversation.get("conversation_id") or "").strip()
        for conversation in filtered_conversations
        if isinstance(conversation, dict)
    }
    missing_conversation_ids = sorted(selected_conversation_ids - present_conversation_ids)

    return {
        "input_promotion_plan_file": str(Path(promotion_plan_file)),
        "input_source_backed_slice_file": str(Path(source_backed_slice_file)),
        "summary": {
            "selected_target_count": len(selected_targets),
            "selected_conversation_count": len(filtered_conversations),
            "include_optional": include_optional,
            "missing_conversation_count": len(missing_conversation_ids),
        },
        "selected_targets": selected_targets,
        "missing_conversation_ids": missing_conversation_ids,
        "normalization": {
            "normalized": filtered_normalized,
        },
        "snapshot": snapshot,
        "compile_result": compile_result,
        "health_report": health_report,
        "trace": {
            "operation": "build_spark_memory_kb_approved_promotion_slice",
            "include_optional": include_optional,
        },
    }


def _build_spark_memory_kb_policy_aligned_slice(
    source_backed_slice_file: str,
    promotion_policy_file: str,
    output_dir: str,
) -> dict:
    source_backed_payload = _load_json_file(source_backed_slice_file)
    if not isinstance(source_backed_payload, dict):
        raise ValueError("Source-backed slice payload must be a JSON object.")
    normalization = source_backed_payload.get("normalization")
    if not isinstance(normalization, dict):
        raise ValueError("Source-backed slice payload must contain a normalization object.")
    normalized = normalization.get("normalized")
    if not isinstance(normalized, dict):
        raise ValueError("Source-backed slice payload must contain normalization.normalized.")

    promotion_policy_rows = _load_spark_memory_kb_promotion_policy_rows(promotion_policy_file)
    writable_roles = normalized.get("writable_roles")
    configured_roles = (
        tuple(str(role) for role in writable_roles)
        if isinstance(writable_roles, list)
        else ("user",)
    )
    adapter = SparkShadowIngestAdapter(
        writable_roles=configured_roles,
        promotion_policy_rows=tuple(promotion_policy_rows),
    )
    evaluations, adapter = _execute_shadow_replay_payload(normalized, adapter=adapter)
    shadow_payload = _build_shadow_report_payload_from_evaluations(evaluations)
    snapshot = adapter.sdk.export_knowledge_base_snapshot()
    compile_result = scaffold_spark_knowledge_base(
        output_dir,
        snapshot,
        vault_title="Spark Memory KB Policy-Aligned Slice",
    )
    health_report = build_spark_kb_health_report(output_dir)

    policy_skipped_turn_count = 0
    policy_skipped_by_reason: dict[str, int] = {}
    for evaluation in shadow_payload.get("evaluations", []):
        if not isinstance(evaluation, dict):
            continue
        trace = evaluation.get("trace")
        if not isinstance(trace, dict):
            continue
        turn_traces = trace.get("turn_traces")
        if not isinstance(turn_traces, list):
            continue
        for trace in turn_traces:
            if not isinstance(trace, dict):
                continue
            if str(trace.get("action") or "").strip() != "skipped_promotion_policy":
                continue
            policy_skipped_turn_count += 1
            reason = str(trace.get("unsupported_reason") or "").strip() or "unknown"
            policy_skipped_by_reason[reason] = policy_skipped_by_reason.get(reason, 0) + 1

    shadow_summary = dict(shadow_payload.get("report", {}).get("summary", {}))
    conversations = normalized.get("conversations")
    conversation_count = len([item for item in conversations if isinstance(item, dict)]) if isinstance(conversations, list) else 0

    return {
        "input_source_backed_slice_file": str(Path(source_backed_slice_file)),
        "input_promotion_policy_file": str(Path(promotion_policy_file)),
        "summary": {
            "conversation_count": conversation_count,
            "accepted_writes": int(shadow_summary.get("accepted_writes", 0) or 0),
            "skipped_turns": int(shadow_summary.get("skipped_turns", 0) or 0),
            "policy_skipped_turn_count": policy_skipped_turn_count,
            "policy_skipped_by_reason": dict(sorted(policy_skipped_by_reason.items())),
            "current_state_page_count": int(compile_result.get("current_state_page_count", 0) or 0),
            "evidence_page_count": int(compile_result.get("evidence_page_count", 0) or 0),
        },
        "promotion_policy_rows": promotion_policy_rows,
        "normalization": {
            "normalized": normalized,
        },
        "shadow_report": shadow_payload,
        "snapshot": snapshot,
        "compile_result": compile_result,
        "health_report": health_report,
        "trace": {
            "operation": "build_spark_memory_kb_policy_aligned_slice",
        },
    }


def _build_spark_memory_kb_refresh_manifest(policy_aligned_slice_file: str) -> dict:
    payload = _load_json_file(policy_aligned_slice_file)
    if not isinstance(payload, dict):
        raise ValueError("Policy-aligned slice payload must be a JSON object.")

    summary = payload.get("summary")
    compile_result = payload.get("compile_result")
    health_report = payload.get("health_report")
    promotion_policy_rows = payload.get("promotion_policy_rows")
    if not isinstance(summary, dict) or not isinstance(compile_result, dict) or not isinstance(health_report, dict):
        raise ValueError("Policy-aligned slice payload must contain summary, compile_result, and health_report objects.")
    if not isinstance(promotion_policy_rows, list):
        raise ValueError("Policy-aligned slice payload must contain promotion_policy_rows.")

    decision_counts: dict[str, int] = {}
    target_conversation_ids: set[str] = set()
    source_conversation_ids: set[str] = set()
    source_message_ids: set[str] = set()
    policy_targets_by_decision: dict[str, list[dict[str, str | None]]] = {}
    for row in promotion_policy_rows:
        if not isinstance(row, dict):
            continue
        decision = str(row.get("policy_decision") or "").strip().lower() or "unknown"
        decision_counts[decision] = decision_counts.get(decision, 0) + 1
        target_conversation_id = str(row.get("target_conversation_id") or "").strip()
        source_conversation_id = str(row.get("source_conversation_id") or "").strip()
        source_message_id = str(row.get("source_message_id") or "").strip()
        predicate = str(row.get("predicate") or "").strip() or None
        if target_conversation_id:
            target_conversation_ids.add(target_conversation_id)
        if source_conversation_id:
            source_conversation_ids.add(source_conversation_id)
        if source_message_id:
            source_message_ids.add(source_message_id)
        examples = policy_targets_by_decision.setdefault(decision, [])
        if len(examples) < 4:
            examples.append(
                {
                    "target_conversation_id": target_conversation_id or None,
                    "predicate": predicate,
                    "source_conversation_id": source_conversation_id or None,
                    "source_message_id": source_message_id or None,
                    "value": str(row.get("value") or "").strip() or None,
                }
            )

    return {
        "input_policy_aligned_slice_file": str(Path(policy_aligned_slice_file)),
        "summary": {
            "kb_output_dir": str(compile_result.get("output_dir") or ""),
            "snapshot_file": str(compile_result.get("snapshot_file") or ""),
            "health_valid": bool(health_report.get("valid")),
            "conversation_count": int(summary.get("conversation_count", 0) or 0),
            "accepted_writes": int(summary.get("accepted_writes", 0) or 0),
            "skipped_turns": int(summary.get("skipped_turns", 0) or 0),
            "policy_skipped_turn_count": int(summary.get("policy_skipped_turn_count", 0) or 0),
            "policy_skipped_by_reason": dict(sorted(dict(summary.get("policy_skipped_by_reason", {})).items())),
            "decision_counts": dict(sorted(decision_counts.items())),
            "target_conversation_count": len(target_conversation_ids),
            "source_conversation_count": len(source_conversation_ids),
            "source_message_count": len(source_message_ids),
            "current_state_page_count": int(compile_result.get("current_state_page_count", 0) or 0),
            "evidence_page_count": int(compile_result.get("evidence_page_count", 0) or 0),
        },
        "kb": {
            "output_dir": str(compile_result.get("output_dir") or ""),
            "snapshot_file": str(compile_result.get("snapshot_file") or ""),
            "current_state_page_count": int(compile_result.get("current_state_page_count", 0) or 0),
            "evidence_page_count": int(compile_result.get("evidence_page_count", 0) or 0),
            "health_report": health_report,
        },
        "policy_targets_by_decision": {
            decision: examples for decision, examples in sorted(policy_targets_by_decision.items())
        },
        "trace": {
            "operation": "build_spark_memory_kb_refresh_manifest",
        },
    }


def _materialize_spark_memory_kb_refresh_manifest(
    refresh_manifest_file: str,
    output_dir: str,
) -> dict:
    payload = _load_json_file(refresh_manifest_file)
    if not isinstance(payload, dict):
        raise ValueError("Refresh manifest payload must be a JSON object.")
    summary = payload.get("summary")
    kb = payload.get("kb")
    if not isinstance(summary, dict) or not isinstance(kb, dict):
        raise ValueError("Refresh manifest payload must contain summary and kb objects.")

    source_output_dir = str(summary.get("kb_output_dir") or kb.get("output_dir") or "").strip()
    snapshot_file = str(summary.get("snapshot_file") or kb.get("snapshot_file") or "").strip()
    if not source_output_dir or not snapshot_file:
        raise ValueError("Refresh manifest must contain kb_output_dir and snapshot_file.")

    source_output_path = Path(source_output_dir)
    source_snapshot_path = Path(snapshot_file)
    if not source_output_path.is_dir():
        raise ValueError(f"Governed KB output_dir does not exist: {source_output_path}")
    if not source_snapshot_path.is_file():
        raise ValueError(f"Governed KB snapshot_file does not exist: {source_snapshot_path}")

    target_output_path = Path(output_dir)
    if target_output_path.exists():
        raise ValueError(f"Target output_dir already exists: {target_output_path}")

    shutil.copytree(source_output_path, target_output_path)
    target_snapshot_path = target_output_path / "raw" / "memory-snapshots" / source_snapshot_path.name
    target_health_report = build_spark_kb_health_report(target_output_path)

    return {
        "input_refresh_manifest_file": str(Path(refresh_manifest_file)),
        "summary": {
            "source_kb_output_dir": str(source_output_path),
            "materialized_kb_output_dir": str(target_output_path),
            "source_snapshot_file": str(source_snapshot_path),
            "materialized_snapshot_file": str(target_snapshot_path),
            "health_valid": bool(target_health_report.get("valid")),
            "conversation_count": int(summary.get("conversation_count", 0) or 0),
            "accepted_writes": int(summary.get("accepted_writes", 0) or 0),
            "skipped_turns": int(summary.get("skipped_turns", 0) or 0),
            "policy_skipped_turn_count": int(summary.get("policy_skipped_turn_count", 0) or 0),
            "policy_skipped_by_reason": dict(sorted(dict(summary.get("policy_skipped_by_reason", {})).items())),
            "decision_counts": dict(sorted(dict(summary.get("decision_counts", {})).items())),
            "current_state_page_count": int(summary.get("current_state_page_count", 0) or 0),
            "evidence_page_count": int(summary.get("evidence_page_count", 0) or 0),
        },
        "health_report": target_health_report,
        "trace": {
            "operation": "materialize_spark_memory_kb_refresh_manifest",
        },
    }


def _publish_spark_memory_kb_refresh_manifest(
    refresh_manifest_file: str,
    publish_root_dir: str,
) -> dict:
    manifest_payload = _load_json_file(refresh_manifest_file)
    if not isinstance(manifest_payload, dict):
        raise ValueError("Refresh manifest payload must be a JSON object.")
    summary = manifest_payload.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("Refresh manifest payload must contain a summary object.")

    source_kb_output_dir = str(summary.get("kb_output_dir") or "").strip()
    if not source_kb_output_dir:
        raise ValueError("Refresh manifest must contain summary.kb_output_dir.")
    release_hash = hashlib.sha1(source_kb_output_dir.encode("utf-8")).hexdigest()[:12]
    release_name = f"spark-kb-{release_hash}"

    publish_root_path = Path(publish_root_dir)
    releases_root_path = publish_root_path / "releases"
    release_output_dir = publish_root_path / "releases" / release_name
    if release_output_dir.exists():
        release_output_dir_resolved = release_output_dir.resolve()
        releases_root_resolved = releases_root_path.resolve(strict=False)
        if release_output_dir_resolved == releases_root_resolved:
            raise ValueError(f"Refusing to replace publish releases root: {release_output_dir}")
        try:
            release_output_dir_resolved.relative_to(releases_root_resolved)
        except ValueError as exc:
            raise ValueError(
                f"Refusing to replace release output_dir outside publish releases root: {release_output_dir}"
            ) from exc
        shutil.rmtree(release_output_dir_resolved)
    materialized_payload = _materialize_spark_memory_kb_refresh_manifest(
        refresh_manifest_file,
        str(release_output_dir),
    )
    active_refresh_file = publish_root_path / "active-refresh.json"
    active_payload = {
        "refresh_manifest_file": str(Path(refresh_manifest_file)),
        "published_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "summary": dict(materialized_payload.get("summary", {})),
        "trace": {
            "operation": "publish_spark_memory_kb_refresh_manifest",
        },
    }
    _write_json(active_refresh_file, active_payload)

    return {
        "input_refresh_manifest_file": str(Path(refresh_manifest_file)),
        "publish_root_dir": str(publish_root_path),
        "release_output_dir": str(release_output_dir),
        "active_refresh_file": str(active_refresh_file),
        "materialized_payload": materialized_payload,
        "active_refresh": active_payload,
        "trace": {
            "operation": "publish_spark_memory_kb_refresh_manifest",
        },
    }


def _resolve_spark_memory_kb_active_refresh(active_refresh_file: str) -> dict:
    payload = _load_json_file(active_refresh_file)
    if not isinstance(payload, dict):
        raise ValueError("Active refresh payload must be a JSON object.")
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("Active refresh payload must contain a summary object.")

    kb_output_dir = str(summary.get("materialized_kb_output_dir") or "").strip()
    snapshot_file = str(summary.get("materialized_snapshot_file") or "").strip()
    if not kb_output_dir or not snapshot_file:
        raise ValueError("Active refresh summary must contain materialized_kb_output_dir and materialized_snapshot_file.")

    kb_output_path = Path(kb_output_dir)
    snapshot_path = Path(snapshot_file)
    if not kb_output_path.is_dir():
        raise ValueError(f"Active governed KB output_dir does not exist: {kb_output_path}")
    if not snapshot_path.is_file():
        raise ValueError(f"Active governed KB snapshot_file does not exist: {snapshot_path}")

    health_report = build_spark_kb_health_report(kb_output_path)
    return {
        "input_active_refresh_file": str(Path(active_refresh_file)),
        "summary": {
            "kb_output_dir": str(kb_output_path),
            "snapshot_file": str(snapshot_path),
            "health_valid": bool(health_report.get("valid")),
            "conversation_count": int(summary.get("conversation_count", 0) or 0),
            "accepted_writes": int(summary.get("accepted_writes", 0) or 0),
            "skipped_turns": int(summary.get("skipped_turns", 0) or 0),
            "policy_skipped_turn_count": int(summary.get("policy_skipped_turn_count", 0) or 0),
            "policy_skipped_by_reason": dict(sorted(dict(summary.get("policy_skipped_by_reason", {})).items())),
            "decision_counts": dict(sorted(dict(summary.get("decision_counts", {})).items())),
            "current_state_page_count": int(summary.get("current_state_page_count", 0) or 0),
            "evidence_page_count": int(summary.get("evidence_page_count", 0) or 0),
        },
        "health_report": health_report,
        "trace": {
            "operation": "resolve_spark_memory_kb_active_refresh",
        },
    }


def _read_spark_memory_kb_active_refresh_support(
    active_refresh_file: str,
    *,
    subject: str,
    predicate: str,
) -> dict:
    resolution = _resolve_spark_memory_kb_active_refresh(active_refresh_file)
    summary = resolution.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("Active refresh resolution must contain a summary object.")
    kb_output_dir = str(summary.get("kb_output_dir") or "").strip()
    if not kb_output_dir:
        raise ValueError("Active refresh resolution must contain summary.kb_output_dir.")

    kb_support = _load_kb_current_state_support(
        kb_output_dir,
        subject=subject,
        predicate=predicate,
    )
    return {
        "input_active_refresh_file": str(Path(active_refresh_file)),
        "subject": subject,
        "predicate": predicate,
        "resolution": resolution,
        "kb_support": kb_support,
        "summary": {
            "kb_output_dir": kb_output_dir,
            "found": bool(kb_support.get("supporting_evidence_count", 0) or kb_support.get("value")),
            "value": kb_support.get("value"),
            "supporting_evidence_count": int(kb_support.get("supporting_evidence_count", 0) or 0),
            "page_path": kb_support.get("page_path"),
        },
        "trace": {
            "operation": "read_spark_memory_kb_active_refresh_support",
        },
    }


def _read_spark_memory_kb_active_refresh_conversation_support(
    active_refresh_file: str,
    policy_aligned_slice_file: str,
    *,
    conversation_id: str,
    predicate: str,
) -> dict:
    policy_payload = _load_json_file(policy_aligned_slice_file)
    if not isinstance(policy_payload, dict):
        raise ValueError("Policy-aligned slice payload must be a JSON object.")
    normalization = policy_payload.get("normalization")
    if not isinstance(normalization, dict):
        raise ValueError("Policy-aligned slice payload must contain a normalization object.")
    normalized = normalization.get("normalized")
    if not isinstance(normalized, dict):
        raise ValueError("Policy-aligned slice payload must contain normalization.normalized.")
    conversations = normalized.get("conversations")
    if not isinstance(conversations, list):
        raise ValueError("Policy-aligned slice payload must contain normalization.normalized.conversations.")

    resolved_subject = ""
    for conversation in conversations:
        if not isinstance(conversation, dict):
            continue
        candidate_conversation_id = str(conversation.get("conversation_id") or "").strip()
        if candidate_conversation_id != conversation_id:
            continue
        metadata = conversation.get("metadata")
        if isinstance(metadata, dict):
            resolved_subject = str(metadata.get("human_id") or "").strip()
        break
    if not resolved_subject:
        raise ValueError(f"Conversation id not found in policy-aligned slice: {conversation_id}")

    payload = _read_spark_memory_kb_active_refresh_support(
        active_refresh_file,
        subject=resolved_subject,
        predicate=predicate,
    )
    payload["conversation_id"] = conversation_id
    payload["summary"]["conversation_id"] = conversation_id
    payload["summary"]["subject"] = resolved_subject
    payload["trace"] = {
        "operation": "read_spark_memory_kb_active_refresh_conversation_support",
    }
    return payload


def _run_spark_memory_kb_active_refresh_read_report(
    active_refresh_file: str,
    policy_aligned_slice_file: str,
    *,
    limit: int | None = None,
) -> dict:
    resolution = _resolve_spark_memory_kb_active_refresh(active_refresh_file)
    resolution_summary = resolution.get("summary")
    if not isinstance(resolution_summary, dict):
        raise ValueError("Active refresh resolution must contain a summary object.")
    kb_output_dir = str(resolution_summary.get("kb_output_dir") or "").strip()
    if not kb_output_dir:
        raise ValueError("Active refresh resolution must contain summary.kb_output_dir.")

    policy_payload = _load_json_file(policy_aligned_slice_file)
    if not isinstance(policy_payload, dict):
        raise ValueError("Policy-aligned slice payload must be a JSON object.")
    normalization = policy_payload.get("normalization")
    if not isinstance(normalization, dict):
        raise ValueError("Policy-aligned slice payload must contain a normalization object.")
    normalized = normalization.get("normalized")
    if not isinstance(normalized, dict):
        raise ValueError("Policy-aligned slice payload must contain normalization.normalized.")

    subject_by_conversation_id = _build_spark_conversation_subject_index(normalized)
    query_cases = _extract_spark_query_cases(normalized)
    if limit is not None:
        query_cases = query_cases[:limit]

    comparisons: list[dict[str, object]] = []
    found_count = 0
    missing_count = 0
    resolved_missing_fact_query_count = 0
    unresolved_missing_fact_query_count = 0
    found_by_scenario: dict[str, int] = {}
    missing_by_scenario: dict[str, int] = {}
    found_by_action_bucket: dict[str, int] = {}
    missing_by_action_bucket: dict[str, int] = {}

    for case in query_cases:
        conversation_id = str(case.get("conversation_id") or "").strip()
        subject = subject_by_conversation_id.get(conversation_id, "")
        predicate = str(case.get("predicate") or "").strip()
        scenario_bucket = _spark_conversation_scenario_bucket(conversation_id)
        action_bucket = _spark_gap_action_bucket(scenario_bucket)
        kb_support = (
            _load_kb_current_state_support(kb_output_dir, subject=subject, predicate=predicate)
            if subject and predicate
            else {
                "exists": False,
                "page_path": None,
                "value": None,
                "supporting_evidence_links": [],
                "supporting_evidence_count": 0,
            }
        )
        found = bool(kb_support.get("supporting_evidence_count", 0) or kb_support.get("value"))
        if found:
            found_count += 1
            found_by_scenario[scenario_bucket] = found_by_scenario.get(scenario_bucket, 0) + 1
            found_by_action_bucket[action_bucket] = found_by_action_bucket.get(action_bucket, 0) + 1
        else:
            missing_count += 1
            missing_by_scenario[scenario_bucket] = missing_by_scenario.get(scenario_bucket, 0) + 1
            missing_by_action_bucket[action_bucket] = missing_by_action_bucket.get(action_bucket, 0) + 1
        if case.get("value_found") is False:
            if found:
                resolved_missing_fact_query_count += 1
            else:
                unresolved_missing_fact_query_count += 1

        comparisons.append(
            {
                "conversation_id": conversation_id,
                "subject": subject or None,
                "predicate": predicate,
                "question": case.get("question"),
                "scenario_bucket": scenario_bucket,
                "action_bucket": action_bucket,
                "value_found": case.get("value_found"),
                "active_refresh": {
                    "found": found,
                    "value": kb_support.get("value"),
                    "supporting_evidence_count": int(kb_support.get("supporting_evidence_count", 0) or 0),
                    "page_path": kb_support.get("page_path"),
                },
            }
        )

    return {
        "input_active_refresh_file": str(Path(active_refresh_file)),
        "input_policy_aligned_slice_file": str(Path(policy_aligned_slice_file)),
        "resolution": resolution,
        "summary": {
            "query_count": len(query_cases),
            "found_count": found_count,
            "missing_count": missing_count,
            "resolved_missing_fact_query_count": resolved_missing_fact_query_count,
            "unresolved_missing_fact_query_count": unresolved_missing_fact_query_count,
            "found_by_scenario": dict(sorted(found_by_scenario.items())),
            "missing_by_scenario": dict(sorted(missing_by_scenario.items())),
            "found_by_action_bucket": dict(sorted(found_by_action_bucket.items())),
            "missing_by_action_bucket": dict(sorted(missing_by_action_bucket.items())),
        },
        "comparisons": comparisons,
        "trace": {
            "operation": "run_spark_memory_kb_active_refresh_read_report",
            "limit": limit,
        },
    }


def _build_spark_memory_kb_active_release_summary(
    active_refresh_file: str,
    policy_aligned_slice_file: str,
    *,
    limit: int | None = None,
) -> dict:
    resolution = _resolve_spark_memory_kb_active_refresh(active_refresh_file)
    policy_verification = _verify_spark_memory_kb_active_refresh_policy(
        active_refresh_file,
        policy_aligned_slice_file,
    )
    active_read_report = _run_spark_memory_kb_active_refresh_read_report(
        active_refresh_file,
        policy_aligned_slice_file,
        limit=limit,
    )

    resolution_summary = resolution.get("summary", {})
    verification_summary = policy_verification.get("summary", {})
    read_summary = active_read_report.get("summary", {})

    return {
        "input_active_refresh_file": str(Path(active_refresh_file)),
        "input_policy_aligned_slice_file": str(Path(policy_aligned_slice_file)),
        "summary": {
            "kb_output_dir": str(resolution_summary.get("kb_output_dir") or ""),
            "snapshot_file": str(resolution_summary.get("snapshot_file") or ""),
            "health_valid": bool(resolution_summary.get("health_valid")),
            "policy_honored": bool(verification_summary.get("policy_honored")),
            "policy_row_count": int(verification_summary.get("policy_row_count", 0) or 0),
            "policy_violation_count": int(verification_summary.get("violation_count", 0) or 0),
            "query_count": int(read_summary.get("query_count", 0) or 0),
            "found_count": int(read_summary.get("found_count", 0) or 0),
            "missing_count": int(read_summary.get("missing_count", 0) or 0),
            "resolved_missing_fact_query_count": int(read_summary.get("resolved_missing_fact_query_count", 0) or 0),
            "unresolved_missing_fact_query_count": int(read_summary.get("unresolved_missing_fact_query_count", 0) or 0),
            "found_by_action_bucket": dict(sorted(dict(read_summary.get("found_by_action_bucket", {})).items())),
            "missing_by_action_bucket": dict(sorted(dict(read_summary.get("missing_by_action_bucket", {})).items())),
        },
        "resolution": resolution,
        "policy_verification": policy_verification,
        "active_read_report": active_read_report,
        "trace": {
            "operation": "build_spark_memory_kb_active_release_summary",
            "limit": limit,
        },
    }


def _check_spark_memory_kb_active_release_summary(active_release_summary_file: str) -> dict:
    payload = _load_json_file(active_release_summary_file)
    if not isinstance(payload, dict):
        raise ValueError("Active release summary payload must be a JSON object.")
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("Active release summary payload must contain a summary object.")

    health_valid = bool(summary.get("health_valid"))
    policy_honored = bool(summary.get("policy_honored"))
    policy_violation_count = int(summary.get("policy_violation_count", 0) or 0)
    found_by_action_bucket = dict(summary.get("found_by_action_bucket", {}))
    missing_by_action_bucket = dict(summary.get("missing_by_action_bucket", {}))

    failure_reasons: list[str] = []
    if not health_valid:
        failure_reasons.append("health_invalid")
    if not policy_honored:
        failure_reasons.append("policy_not_honored")
    if policy_violation_count > 0:
        failure_reasons.append("policy_violations_present")
    if int(missing_by_action_bucket.get("regression_candidate", 0) or 0) > 0:
        failure_reasons.append("regression_candidate_missing")
    if int(found_by_action_bucket.get("expected_cleanroom_boundary", 0) or 0) > 0:
        failure_reasons.append("cleanroom_boundary_exposed")
    if int(found_by_action_bucket.get("gauntlet_candidate", 0) or 0) > 0:
        failure_reasons.append("gauntlet_candidate_exposed")

    allowed_missing_action_buckets = {
        key: int(value or 0)
        for key, value in missing_by_action_bucket.items()
        if int(value or 0) > 0
    }

    return {
        "input_active_release_summary_file": str(Path(active_release_summary_file)),
        "summary": {
            "ready": len(failure_reasons) == 0,
            "failure_reason_count": len(failure_reasons),
            "failure_reasons": failure_reasons,
            "health_valid": health_valid,
            "policy_honored": policy_honored,
            "policy_violation_count": policy_violation_count,
            "found_count": int(summary.get("found_count", 0) or 0),
            "missing_count": int(summary.get("missing_count", 0) or 0),
            "found_by_action_bucket": dict(sorted((str(key), int(value or 0)) for key, value in found_by_action_bucket.items())),
            "missing_by_action_bucket": dict(sorted((str(key), int(value or 0)) for key, value in missing_by_action_bucket.items())),
            "allowed_missing_action_buckets": dict(sorted(allowed_missing_action_buckets.items())),
        },
        "trace": {
            "operation": "check_spark_memory_kb_active_release_summary",
        },
    }


def _assert_spark_memory_kb_active_release_ready(active_release_summary_file: str) -> dict:
    payload = _check_spark_memory_kb_active_release_summary(active_release_summary_file)
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("Active release gate payload must contain a summary object.")
    if not bool(summary.get("ready")):
        failure_reasons = [str(item).strip() for item in summary.get("failure_reasons", []) if str(item).strip()]
        reason_text = ", ".join(failure_reasons) if failure_reasons else "unknown_failure"
        raise SystemExit(f"Spark active release gate failed: {reason_text}")
    return payload


def _read_spark_memory_kb_governed_release_support(
    governed_release_file: str,
    *,
    subject: str,
    predicate: str,
) -> dict:
    resolution = _resolve_spark_memory_kb_governed_release(governed_release_file)
    summary = resolution.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("Governed release resolution payload must contain a summary object.")
    active_refresh_file = str(summary.get("active_refresh_file") or "").strip()
    if not active_refresh_file:
        raise ValueError("Governed release resolution must contain summary.active_refresh_file.")

    payload = _read_spark_memory_kb_active_refresh_support(
        active_refresh_file,
        subject=subject,
        predicate=predicate,
    )
    payload["input_governed_release_file"] = str(Path(governed_release_file))
    payload["governed_release_resolution"] = resolution
    payload["summary"]["publish_root_dir"] = str(summary.get("publish_root_dir") or "")
    payload["summary"]["release_output_dir"] = str(summary.get("release_output_dir") or "")
    payload["trace"] = {
        "operation": "read_spark_memory_kb_governed_release_support",
    }
    return payload


def _read_spark_memory_kb_governed_release_conversation_support(
    governed_release_file: str,
    *,
    conversation_id: str,
    predicate: str,
) -> dict:
    governed_payload = _load_json_file(governed_release_file)
    if not isinstance(governed_payload, dict):
        raise ValueError("Governed release payload must be a JSON object.")
    policy_aligned_slice_file = str(governed_payload.get("input_policy_aligned_slice_file") or "").strip()
    if not policy_aligned_slice_file:
        raise ValueError("Governed release payload must contain input_policy_aligned_slice_file.")
    if not Path(policy_aligned_slice_file).is_file():
        raise ValueError(f"Governed release policy_aligned_slice_file does not exist: {policy_aligned_slice_file}")

    resolution = _resolve_spark_memory_kb_governed_release(governed_release_file)
    summary = resolution.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("Governed release resolution payload must contain a summary object.")
    active_refresh_file = str(summary.get("active_refresh_file") or "").strip()
    if not active_refresh_file:
        raise ValueError("Governed release resolution must contain summary.active_refresh_file.")

    payload = _read_spark_memory_kb_active_refresh_conversation_support(
        active_refresh_file,
        policy_aligned_slice_file,
        conversation_id=conversation_id,
        predicate=predicate,
    )
    payload["input_governed_release_file"] = str(Path(governed_release_file))
    payload["input_policy_aligned_slice_file"] = str(Path(policy_aligned_slice_file))
    payload["governed_release_resolution"] = resolution
    payload["summary"]["publish_root_dir"] = str(summary.get("publish_root_dir") or "")
    payload["summary"]["release_output_dir"] = str(summary.get("release_output_dir") or "")
    payload["trace"] = {
        "operation": "read_spark_memory_kb_governed_release_conversation_support",
    }
    return payload


def _run_spark_memory_kb_governed_release_read_report(
    governed_release_file: str,
    *,
    limit: int | None = None,
) -> dict:
    governed_payload = _load_json_file(governed_release_file)
    if not isinstance(governed_payload, dict):
        raise ValueError("Governed release payload must be a JSON object.")
    policy_aligned_slice_file = str(governed_payload.get("input_policy_aligned_slice_file") or "").strip()
    if not policy_aligned_slice_file:
        raise ValueError("Governed release payload must contain input_policy_aligned_slice_file.")
    if not Path(policy_aligned_slice_file).is_file():
        raise ValueError(f"Governed release policy_aligned_slice_file does not exist: {policy_aligned_slice_file}")

    resolution = _resolve_spark_memory_kb_governed_release(governed_release_file)
    summary = resolution.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("Governed release resolution payload must contain a summary object.")
    active_refresh_file = str(summary.get("active_refresh_file") or "").strip()
    if not active_refresh_file:
        raise ValueError("Governed release resolution must contain summary.active_refresh_file.")

    payload = _run_spark_memory_kb_active_refresh_read_report(
        active_refresh_file,
        policy_aligned_slice_file,
        limit=limit,
    )
    payload["input_governed_release_file"] = str(Path(governed_release_file))
    payload["input_policy_aligned_slice_file"] = str(Path(policy_aligned_slice_file))
    payload["governed_release_resolution"] = resolution
    payload["summary"]["publish_root_dir"] = str(summary.get("publish_root_dir") or "")
    payload["summary"]["release_output_dir"] = str(summary.get("release_output_dir") or "")
    payload["trace"] = {
        "operation": "run_spark_memory_kb_governed_release_read_report",
        "limit": limit,
    }
    return payload


def _build_spark_memory_kb_governed_release_summary(
    governed_release_file: str,
    *,
    limit: int | None = None,
) -> dict:
    resolution = _resolve_spark_memory_kb_governed_release(governed_release_file)
    read_report = _run_spark_memory_kb_governed_release_read_report(
        governed_release_file,
        limit=limit,
    )

    resolution_summary = resolution.get("summary")
    read_summary = read_report.get("summary")
    if not isinstance(resolution_summary, dict):
        raise ValueError("Governed release resolution payload must contain a summary object.")
    if not isinstance(read_summary, dict):
        raise ValueError("Governed release read report payload must contain a summary object.")

    return {
        "input_governed_release_file": str(Path(governed_release_file)),
        "summary": {
            "publish_root_dir": str(resolution_summary.get("publish_root_dir") or ""),
            "release_output_dir": str(resolution_summary.get("release_output_dir") or ""),
            "snapshot_file": str(resolution_summary.get("snapshot_file") or ""),
            "health_valid": bool(resolution_summary.get("health_valid")),
            "policy_honored": bool(resolution_summary.get("policy_honored")),
            "ready": bool(resolution_summary.get("ready")),
            "failure_reason_count": int(resolution_summary.get("failure_reason_count", 0) or 0),
            "query_count": int(read_summary.get("query_count", 0) or 0),
            "found_count": int(read_summary.get("found_count", 0) or 0),
            "missing_count": int(read_summary.get("missing_count", 0) or 0),
            "resolved_missing_fact_query_count": int(read_summary.get("resolved_missing_fact_query_count", 0) or 0),
            "unresolved_missing_fact_query_count": int(read_summary.get("unresolved_missing_fact_query_count", 0) or 0),
            "found_by_action_bucket": dict(sorted(dict(read_summary.get("found_by_action_bucket", {})).items())),
            "missing_by_action_bucket": dict(sorted(dict(read_summary.get("missing_by_action_bucket", {})).items())),
        },
        "resolution": resolution,
        "read_report": read_report,
        "trace": {
            "operation": "build_spark_memory_kb_governed_release_summary",
            "limit": limit,
        },
    }


def _check_spark_memory_kb_governed_release_summary(governed_release_summary_file: str) -> dict:
    payload = _load_json_file(governed_release_summary_file)
    if not isinstance(payload, dict):
        raise ValueError("Governed release summary payload must be a JSON object.")
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("Governed release summary payload must contain a summary object.")

    found_by_action_bucket = dict(summary.get("found_by_action_bucket", {}))
    missing_by_action_bucket = dict(summary.get("missing_by_action_bucket", {}))
    failure_reasons: list[str] = []
    if not bool(summary.get("ready")):
        failure_reasons.append("governed_release_not_ready")
    if not bool(summary.get("health_valid")):
        failure_reasons.append("health_invalid")
    if not bool(summary.get("policy_honored")):
        failure_reasons.append("policy_not_honored")
    if int(summary.get("failure_reason_count", 0) or 0) != 0:
        failure_reasons.append("upstream_failure_reason_count_nonzero")
    if int(missing_by_action_bucket.get("regression_candidate", 0) or 0) != 0:
        failure_reasons.append("regression_candidate_missing")
    if int(found_by_action_bucket.get("expected_cleanroom_boundary", 0) or 0) != 0:
        failure_reasons.append("cleanroom_boundary_exposed")
    if int(found_by_action_bucket.get("gauntlet_candidate", 0) or 0) != 0:
        failure_reasons.append("gauntlet_candidate_exposed")

    allowed_missing_action_buckets = {
        key: int(value or 0)
        for key, value in sorted(missing_by_action_bucket.items())
        if key in {"expected_cleanroom_boundary", "gauntlet_candidate"} and int(value or 0) != 0
    }
    return {
        "input_governed_release_summary_file": str(Path(governed_release_summary_file)),
        "summary": {
            "ready": not failure_reasons,
            "failure_reason_count": len(failure_reasons),
            "failure_reasons": failure_reasons,
            "health_valid": bool(summary.get("health_valid")),
            "policy_honored": bool(summary.get("policy_honored")),
            "upstream_ready": bool(summary.get("ready")),
            "upstream_failure_reason_count": int(summary.get("failure_reason_count", 0) or 0),
            "query_count": int(summary.get("query_count", 0) or 0),
            "found_count": int(summary.get("found_count", 0) or 0),
            "missing_count": int(summary.get("missing_count", 0) or 0),
            "found_by_action_bucket": dict(sorted(found_by_action_bucket.items())),
            "missing_by_action_bucket": dict(sorted(missing_by_action_bucket.items())),
            "allowed_missing_action_buckets": allowed_missing_action_buckets,
        },
        "trace": {
            "operation": "check_spark_memory_kb_governed_release_summary",
        },
    }


def _assert_spark_memory_kb_governed_release_summary_ready(governed_release_summary_file: str) -> dict:
    payload = _check_spark_memory_kb_governed_release_summary(governed_release_summary_file)
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("Governed release gate payload must contain a summary object.")
    if not bool(summary.get("ready")):
        failure_reasons = [str(item).strip() for item in summary.get("failure_reasons", []) if str(item).strip()]
        reason_text = ", ".join(failure_reasons) if failure_reasons else "unknown_failure"
        raise SystemExit(f"Spark governed release summary gate failed: {reason_text}")
    return payload


def _resolve_spark_memory_kb_governed_release(governed_release_file: str) -> dict:
    payload = _load_json_file(governed_release_file)
    if not isinstance(payload, dict):
        raise ValueError("Governed release payload must be a JSON object.")

    publish_root_dir = str(payload.get("publish_root_dir") or "").strip()
    policy_aligned_slice_file = str(payload.get("input_policy_aligned_slice_file") or "").strip()
    active_refresh_file = str(payload.get("active_refresh_file") or "").strip()
    active_release_summary_file = str(payload.get("active_release_summary_file") or "").strip()
    active_release_gate_file = str(payload.get("active_release_gate_file") or "").strip()
    if not publish_root_dir or not active_refresh_file or not active_release_summary_file or not active_release_gate_file:
        raise ValueError(
            "Governed release payload must contain publish_root_dir, active_refresh_file, "
            "active_release_summary_file, and active_release_gate_file."
        )

    publish_root_path = Path(publish_root_dir)
    active_refresh_path = Path(active_refresh_file)
    active_release_summary_path = Path(active_release_summary_file)
    active_release_gate_path = Path(active_release_gate_file)
    if not publish_root_path.is_dir():
        raise ValueError(f"Governed release publish_root_dir does not exist: {publish_root_path}")
    if not active_refresh_path.is_file():
        raise ValueError(f"Governed release active_refresh_file does not exist: {active_refresh_path}")
    if not active_release_summary_path.is_file():
        raise ValueError(f"Governed release active_release_summary_file does not exist: {active_release_summary_path}")
    if not active_release_gate_path.is_file():
        raise ValueError(f"Governed release active_release_gate_file does not exist: {active_release_gate_path}")

    active_refresh_resolution = _resolve_spark_memory_kb_active_refresh(str(active_refresh_path))
    active_release_gate = _check_spark_memory_kb_active_release_summary(str(active_release_summary_path))
    active_release_summary_payload = _load_json_file(str(active_release_summary_path))
    if not isinstance(active_release_summary_payload, dict):
        raise ValueError("Active release summary payload must be a JSON object.")

    active_refresh_summary = active_refresh_resolution.get("summary")
    active_release_summary = active_release_summary_payload.get("summary")
    gate_summary = active_release_gate.get("summary")
    if not isinstance(active_refresh_summary, dict):
        raise ValueError("Active refresh resolution must contain a summary object.")
    if not isinstance(active_release_summary, dict):
        raise ValueError("Active release summary payload must contain a summary object.")
    if not isinstance(gate_summary, dict):
        raise ValueError("Active release gate payload must contain a summary object.")

    return {
        "input_governed_release_file": str(Path(governed_release_file)),
        "summary": {
            "publish_root_dir": str(publish_root_path),
            "policy_aligned_slice_file": policy_aligned_slice_file,
            "active_refresh_file": str(active_refresh_path),
            "active_release_summary_file": str(active_release_summary_path),
            "active_release_gate_file": str(active_release_gate_path),
            "release_output_dir": str(active_refresh_summary.get("kb_output_dir") or ""),
            "snapshot_file": str(active_refresh_summary.get("snapshot_file") or ""),
            "health_valid": bool(active_refresh_summary.get("health_valid")),
            "policy_honored": bool(active_release_summary.get("policy_honored")),
            "ready": bool(gate_summary.get("ready")),
            "failure_reason_count": int(gate_summary.get("failure_reason_count", 0) or 0),
        },
        "active_refresh_resolution": active_refresh_resolution,
        "active_release_summary": active_release_summary_payload,
        "active_release_gate": active_release_gate,
        "trace": {
            "operation": "resolve_spark_memory_kb_governed_release",
        },
    }


def _assert_spark_memory_kb_governed_release_ready(governed_release_file: str) -> dict:
    payload = _resolve_spark_memory_kb_governed_release(governed_release_file)
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("Governed release resolution payload must contain a summary object.")
    if not bool(summary.get("ready")):
        gate_payload = payload.get("active_release_gate")
        gate_summary = dict(gate_payload.get("summary", {})) if isinstance(gate_payload, dict) else {}
        failure_reasons = [str(item).strip() for item in gate_summary.get("failure_reasons", []) if str(item).strip()]
        reason_text = ", ".join(failure_reasons) if failure_reasons else "unknown_failure"
        raise SystemExit(f"Spark governed release gate failed: {reason_text}")
    return payload


def _ship_spark_memory_kb_governed_release(
    refresh_manifest_file: str,
    policy_aligned_slice_file: str,
    publish_root_dir: str,
) -> dict:
    publish_payload = _publish_spark_memory_kb_refresh_manifest(
        refresh_manifest_file,
        publish_root_dir,
    )
    active_refresh = publish_payload.get("active_refresh")
    active_refresh_file = publish_payload.get("active_refresh_file")
    if not isinstance(active_refresh, dict) or not isinstance(active_refresh_file, str) or not active_refresh_file.strip():
        raise ValueError("Publish payload must contain active_refresh metadata and active_refresh_file.")

    active_release_summary = _build_spark_memory_kb_active_release_summary(
        active_refresh_file,
        policy_aligned_slice_file,
    )
    publish_root_path = Path(publish_root_dir)
    active_release_summary_path = publish_root_path / "active-release-summary.json"
    _write_json(active_release_summary_path, active_release_summary)
    active_release_gate = _assert_spark_memory_kb_active_release_ready(str(active_release_summary_path))
    active_release_gate_path = publish_root_path / "active-release-gate.json"
    _write_json(active_release_gate_path, active_release_gate)
    governed_release_payload = {
        "input_refresh_manifest_file": str(Path(refresh_manifest_file)),
        "input_policy_aligned_slice_file": str(Path(policy_aligned_slice_file)),
        "publish_root_dir": str(publish_root_path),
        "active_refresh_file": str(Path(active_refresh_file)),
        "active_release_summary_file": str(active_release_summary_path),
        "active_release_gate_file": str(active_release_gate_path),
        "publish": publish_payload,
        "active_release_summary": active_release_summary,
        "active_release_gate": active_release_gate,
        "summary": {
            "ready": bool(dict(active_release_gate.get("summary", {})).get("ready")),
            "release_output_dir": str(publish_payload.get("release_output_dir") or ""),
            "active_refresh_file": str(Path(active_refresh_file)),
            "active_release_summary_file": str(active_release_summary_path),
            "active_release_gate_file": str(active_release_gate_path),
        },
        "trace": {
            "operation": "ship_spark_memory_kb_governed_release",
        },
    }
    governed_release_file = publish_root_path / "governed-release.json"
    governed_release_payload["governed_release_file"] = str(governed_release_file)
    _write_json(governed_release_file, governed_release_payload)
    governed_release_read_report = _run_spark_memory_kb_governed_release_read_report(str(governed_release_file))
    governed_release_read_report_file = publish_root_path / "governed-release-read-report.json"
    _write_json(governed_release_read_report_file, governed_release_read_report)
    governed_release_summary = _build_spark_memory_kb_governed_release_summary(str(governed_release_file))
    governed_release_summary_file = publish_root_path / "governed-release-summary.json"
    _write_json(governed_release_summary_file, governed_release_summary)
    governed_release_gate = _assert_spark_memory_kb_governed_release_summary_ready(str(governed_release_summary_file))
    governed_release_gate_file = publish_root_path / "governed-release-gate.json"
    _write_json(governed_release_gate_file, governed_release_gate)
    governed_release_payload["governed_release_read_report_file"] = str(governed_release_read_report_file)
    governed_release_payload["governed_release_summary_file"] = str(governed_release_summary_file)
    governed_release_payload["governed_release_gate_file"] = str(governed_release_gate_file)
    governed_release_payload["governed_release_read_report"] = governed_release_read_report
    governed_release_payload["governed_release_summary"] = governed_release_summary
    governed_release_payload["governed_release_gate"] = governed_release_gate
    governed_release_payload["summary"]["governed_release_read_report_file"] = str(governed_release_read_report_file)
    governed_release_payload["summary"]["governed_release_summary_file"] = str(governed_release_summary_file)
    governed_release_payload["summary"]["governed_release_gate_file"] = str(governed_release_gate_file)
    _write_json(governed_release_file, governed_release_payload)
    return governed_release_payload


def _verify_spark_memory_kb_active_refresh_policy(
    active_refresh_file: str,
    policy_aligned_slice_file: str,
) -> dict:
    resolution = _resolve_spark_memory_kb_active_refresh(active_refresh_file)
    resolution_summary = resolution.get("summary")
    if not isinstance(resolution_summary, dict):
        raise ValueError("Active refresh resolution must contain a summary object.")
    kb_output_dir = str(resolution_summary.get("kb_output_dir") or "").strip()
    if not kb_output_dir:
        raise ValueError("Active refresh resolution must contain summary.kb_output_dir.")

    policy_payload = _load_json_file(policy_aligned_slice_file)
    if not isinstance(policy_payload, dict):
        raise ValueError("Policy-aligned slice payload must be a JSON object.")
    normalization = policy_payload.get("normalization")
    promotion_policy_rows = policy_payload.get("promotion_policy_rows")
    if not isinstance(normalization, dict) or not isinstance(promotion_policy_rows, list):
        raise ValueError("Policy-aligned slice payload must contain normalization and promotion_policy_rows.")
    normalized = normalization.get("normalized")
    if not isinstance(normalized, dict):
        raise ValueError("Policy-aligned slice payload must contain normalization.normalized.")
    conversations = normalized.get("conversations")
    if not isinstance(conversations, list):
        raise ValueError("Policy-aligned slice payload must contain normalization.normalized.conversations.")

    subject_by_conversation_id: dict[str, str] = {}
    for conversation in conversations:
        if not isinstance(conversation, dict):
            continue
        conversation_id = str(conversation.get("conversation_id") or "").strip()
        metadata = conversation.get("metadata")
        if not conversation_id or not isinstance(metadata, dict):
            continue
        subject = str(metadata.get("human_id") or "").strip()
        if subject:
            subject_by_conversation_id[conversation_id] = subject

    honored_counts: dict[str, int] = {}
    violated_counts: dict[str, int] = {}
    subject_missing_count = 0
    checked_rows: list[dict[str, object]] = []
    violations: list[dict[str, object]] = []

    for row in promotion_policy_rows:
        if not isinstance(row, dict):
            continue
        decision = str(row.get("policy_decision") or "").strip().lower() or "unknown"
        target_conversation_id = str(row.get("target_conversation_id") or "").strip()
        predicate = str(row.get("predicate") or "").strip()
        subject = subject_by_conversation_id.get(target_conversation_id, "")
        if not subject or not predicate:
            subject_missing_count += 1
            violations.append(
                {
                    "policy_decision": decision,
                    "target_conversation_id": target_conversation_id or None,
                    "predicate": predicate or None,
                    "reason": "missing_subject",
                }
            )
            continue
        kb_support = _load_kb_current_state_support(
            kb_output_dir,
            subject=subject,
            predicate=predicate,
        )
        found = bool(kb_support.get("supporting_evidence_count", 0) or kb_support.get("value"))
        expected_found = decision == "allow"
        row_result = {
            "policy_decision": decision,
            "target_conversation_id": target_conversation_id,
            "subject": subject,
            "predicate": predicate,
            "found": found,
            "expected_found": expected_found,
            "value": kb_support.get("value"),
            "supporting_evidence_count": int(kb_support.get("supporting_evidence_count", 0) or 0),
            "page_path": kb_support.get("page_path"),
        }
        checked_rows.append(row_result)
        if found == expected_found:
            honored_counts[decision] = honored_counts.get(decision, 0) + 1
        else:
            violated_counts[decision] = violated_counts.get(decision, 0) + 1
            violations.append(dict(row_result))

    return {
        "input_active_refresh_file": str(Path(active_refresh_file)),
        "input_policy_aligned_slice_file": str(Path(policy_aligned_slice_file)),
        "resolution": resolution,
        "summary": {
            "kb_output_dir": kb_output_dir,
            "policy_row_count": len([row for row in promotion_policy_rows if isinstance(row, dict)]),
            "checked_row_count": len(checked_rows),
            "subject_missing_count": subject_missing_count,
            "honored_counts": dict(sorted(honored_counts.items())),
            "violated_counts": dict(sorted(violated_counts.items())),
            "violation_count": len(violations),
            "policy_honored": len(violations) == 0,
        },
        "violations": violations,
        "checked_rows": checked_rows,
        "trace": {
            "operation": "verify_spark_memory_kb_active_refresh_policy",
        },
    }


def _load_json_file(path: str | Path) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_spark_memory_kb_promotion_policy_rows(promotion_policy_file: str) -> list[dict[str, object]]:
    payload = _load_json_file(promotion_policy_file)
    if not isinstance(payload, dict):
        raise ValueError("Spark promotion policy file must contain a JSON object.")

    policy_rows: list[dict[str, object]] = []
    for key in ("allowed_promotions", "deferred_promotions", "blocked_promotions"):
        rows = payload.get(key)
        if not isinstance(rows, list):
            raise ValueError(f"Spark promotion policy file must contain a {key} list.")
        for row in rows:
            if isinstance(row, dict):
                policy_rows.append(dict(row))
    return policy_rows


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
    summarize_payload = _load_beam_official_eval_exports()["_summarize_beam_evaluation_payload"]
    current_payload = _load_json_file(path)
    if not isinstance(current_payload, dict):
        return None
    head_payload = _load_json_from_git_revision(repo_root=repo_root, revision="HEAD", path=path)
    current_summary = summarize_payload(current_payload)
    head_summary = summarize_payload(head_payload) if isinstance(head_payload, dict) else None
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
        resolved_repo_sources.extend(_load_repo_source_manifest(repo_source_manifest_file))
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
            resolved_repo_sources.extend(_load_repo_source_manifest(repo_source_manifest_file))
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
    beam_eval = _load_beam_official_eval_exports()
    summarize_evaluation = beam_eval["summarize_beam_official_evaluation"]
    summarize_evaluation_files = beam_eval["summarize_beam_official_evaluation_files"]
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
        summary = summarize_evaluation(path)
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

    aggregate_evaluation_summary = summarize_evaluation_files(evaluation_files) if evaluation_files else None
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
    all_noisy_series_rows: dict[tuple[str, str], dict] = {}
    for path in noisy_paths:
        family = _benchmark_runs_file_family(path)
        series = _benchmark_runs_series_key(path)
        series_row = all_noisy_series_rows.setdefault(
            (family, series),
            {
                "family": family,
                "series": series,
                "file_count": 0,
            },
        )
        series_row["file_count"] += 1
    all_noisy_ranked_series_rows = sorted(
        all_noisy_series_rows.values(),
        key=lambda row: (-row["file_count"], row["family"], row["series"]),
    )
    all_noisy_top_series_by_family: dict[str, dict] = {}
    for row in all_noisy_ranked_series_rows:
        all_noisy_top_series_by_family.setdefault(row["family"], row)
    all_noisy_series_count_by_family: dict[str, int] = {}
    for row in all_noisy_ranked_series_rows:
        family = row["family"]
        all_noisy_series_count_by_family[family] = all_noisy_series_count_by_family.get(family, 0) + 1
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
    reported_file_total = len(reported_paths)
    for row in ordered_family_rows:
        reported_file_share = round(row["file_count"] / reported_file_total, 4) if reported_file_total else 0.0
        dominance_label = "minor"
        if reported_file_share >= 0.5:
            dominance_label = "dominant"
        elif reported_file_share >= 0.25:
            dominance_label = "major"
        row["reported_file_share"] = reported_file_share
        row["dominance_label"] = dominance_label
    ranked_family_rows = sorted(
        ordered_family_rows,
        key=lambda row: (-row["file_count"], row["family"]),
    )
    ranked_family_by_name = {
        row["family"]: index
        for index, row in enumerate(ranked_family_rows)
    }
    for row in ordered_family_rows:
        row["family_rank"] = ranked_family_by_name[row["family"]] + 1
    ordered_series_rows = [
        series_rows[key]
        for key in sorted(series_rows, key=lambda item: (item[0], item[1]))
    ]
    ranked_series_rows = sorted(
        ordered_series_rows,
        key=lambda row: (-row["file_count"], row["family"], row["series"]),
    )
    top_series_by_family: dict[str, dict] = {}
    for row in ranked_series_rows:
        top_series_by_family.setdefault(row["family"], row)
    series_count_by_family: dict[str, int] = {}
    for row in ordered_series_rows:
        family = row["family"]
        series_count_by_family[family] = series_count_by_family.get(family, 0) + 1
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
    ranked_family_command_rows = sorted(
        family_commands,
        key=lambda row: (row["noisy_file_count"], row["family"]),
        reverse=True,
    )
    ranked_family_command_by_name = {
        row["family"]: index
        for index, row in enumerate(ranked_family_command_rows)
    }
    noisy_family_total = sum(row["noisy_file_count"] for row in ranked_family_command_rows)

    def _build_noisy_family_hotspot_summary(family: str) -> dict | None:
        top_series = all_noisy_top_series_by_family.get(family)
        family_noisy_file_count = noisy_family_counts.get(family, 0)
        if top_series is None or family_noisy_file_count <= 0:
            return None
        series_count = all_noisy_series_count_by_family.get(family, 0)
        top_series_share = round(top_series["file_count"] / family_noisy_file_count, 4)
        average_series_size = round(family_noisy_file_count / series_count, 4) if series_count else 0.0
        concentration_label = "diffuse"
        if top_series_share >= 0.4:
            concentration_label = "concentrated"
        elif top_series_share >= 0.2:
            concentration_label = "mixed"
        focus_mode = "family_first"
        if top_series_share >= 0.3 or series_count <= 3:
            focus_mode = "series_first"
        command = _benchmark_runs_git_report_command(
            benchmark_runs_dir=benchmark_runs_path,
            repo_root=repo_root_path,
            only_noisy=True,
            top_series_limit=top_series_limit,
            summary_only=summary_only,
            family_filter=family,
            series_prefix=top_series["series"],
        )
        return {
            "family": family,
            "family_noisy_file_count": family_noisy_file_count,
            "series_count": series_count,
            "top_series_prefix": top_series["series"],
            "top_series_noisy_file_count": top_series["file_count"],
            "top_series_share": top_series_share,
            "average_series_size": average_series_size,
            "concentration_label": concentration_label,
            "focus_mode": focus_mode,
            "command": command,
            "command_shell": " ".join(_shell_quote_arg(part) for part in command),
        }

    family_competition = []
    if ranked_family_command_rows:
        leader_row = ranked_family_command_rows[0]
        leader_share = round(leader_row["noisy_file_count"] / noisy_family_total, 4) if noisy_family_total else 0.0
        for index, row in enumerate(ranked_family_command_rows, start=1):
            share = round(row["noisy_file_count"] / noisy_family_total, 4) if noisy_family_total else 0.0
            file_count_gap_from_leader = leader_row["noisy_file_count"] - row["noisy_file_count"]
            share_gap_from_leader = round(leader_share - share, 4)
            gap_label = "leader"
            if index > 1:
                gap_label = "narrow"
                if share_gap_from_leader >= 0.25:
                    gap_label = "wide"
                elif share_gap_from_leader >= 0.1:
                    gap_label = "clear"
            top_series = all_noisy_top_series_by_family.get(row["family"])
            competition_command = _benchmark_runs_git_report_command(
                benchmark_runs_dir=benchmark_runs_path,
                repo_root=repo_root_path,
                only_noisy=True,
                top_series_limit=top_series_limit,
                summary_only=summary_only,
                family_filter=row["family"],
                series_prefix=None,
            )
            top_series_command = None
            top_series_command_shell = None
            if top_series is not None:
                top_series_command = _benchmark_runs_git_report_command(
                    benchmark_runs_dir=benchmark_runs_path,
                    repo_root=repo_root_path,
                    only_noisy=True,
                    top_series_limit=top_series_limit,
                    summary_only=summary_only,
                    family_filter=row["family"],
                    series_prefix=top_series["series"],
                )
                top_series_command_shell = " ".join(
                    _shell_quote_arg(part) for part in top_series_command
                )
            family_competition.append(
                {
                    "rank": index,
                    "family": row["family"],
                    "noisy_file_count": row["noisy_file_count"],
                    "noisy_file_share": share,
                    "noisy_file_count_gap_from_leader": file_count_gap_from_leader,
                    "noisy_share_gap_from_leader": share_gap_from_leader,
                    "gap_label": gap_label,
                    "top_series_prefix": top_series["series"] if top_series is not None else None,
                    "top_series_noisy_file_count": top_series["file_count"] if top_series is not None else None,
                    "top_series_command": top_series_command,
                    "top_series_command_shell": top_series_command_shell,
                    "command": competition_command,
                    "command_shell": " ".join(_shell_quote_arg(part) for part in competition_command),
                }
            )
        for index, row in enumerate(family_competition):
            previous_row = family_competition[index - 1] if index > 0 else None
            next_row = family_competition[index + 1] if index + 1 < len(family_competition) else None
            previous_family = previous_row["family"] if previous_row is not None else None
            previous_noisy_file_count_gap = (
                previous_row["noisy_file_count"] - row["noisy_file_count"]
                if previous_row is not None
                else None
            )
            previous_noisy_share_gap = (
                round(previous_row["noisy_file_share"] - row["noisy_file_share"], 4)
                if previous_row is not None
                else None
            )
            next_family = next_row["family"] if next_row is not None else None
            next_noisy_file_count_gap = (
                row["noisy_file_count"] - next_row["noisy_file_count"]
                if next_row is not None
                else None
            )
            next_noisy_share_gap = (
                round(row["noisy_file_share"] - next_row["noisy_file_share"], 4)
                if next_row is not None
                else None
            )
            row["previous_family"] = previous_family
            row["previous_noisy_file_count_gap"] = previous_noisy_file_count_gap
            row["previous_noisy_share_gap"] = previous_noisy_share_gap
            row["next_family"] = next_family
            row["next_noisy_file_count_gap"] = next_noisy_file_count_gap
            row["next_noisy_share_gap"] = next_noisy_share_gap
            nearest_direction = None
            nearest_row = None
            if previous_row is not None and next_row is not None:
                previous_key = (
                    previous_noisy_share_gap if previous_noisy_share_gap is not None else float("inf"),
                    previous_noisy_file_count_gap if previous_noisy_file_count_gap is not None else float("inf"),
                    0,
                )
                next_key = (
                    next_noisy_share_gap if next_noisy_share_gap is not None else float("inf"),
                    next_noisy_file_count_gap if next_noisy_file_count_gap is not None else float("inf"),
                    1,
                )
                if previous_key <= next_key:
                    nearest_direction = "previous"
                    nearest_row = previous_row
                else:
                    nearest_direction = "next"
                    nearest_row = next_row
            elif previous_row is not None:
                nearest_direction = "previous"
                nearest_row = previous_row
            elif next_row is not None:
                nearest_direction = "next"
                nearest_row = next_row
            row["nearest_competitor_direction"] = nearest_direction
            row["nearest_competitor_family"] = nearest_row["family"] if nearest_row is not None else None
            row["nearest_competitor_rank"] = nearest_row["rank"] if nearest_row is not None else None
            row["nearest_competitor_noisy_file_count_gap"] = (
                previous_noisy_file_count_gap
                if nearest_direction == "previous"
                else next_noisy_file_count_gap
                if nearest_direction == "next"
                else None
            )
            row["nearest_competitor_noisy_share_gap"] = (
                previous_noisy_share_gap
                if nearest_direction == "previous"
                else next_noisy_share_gap
                if nearest_direction == "next"
                else None
            )
            row["nearest_competitor_top_series_prefix"] = (
                nearest_row["top_series_prefix"] if nearest_row is not None else None
            )
            row["nearest_competitor_top_series_noisy_file_count"] = (
                nearest_row["top_series_noisy_file_count"] if nearest_row is not None else None
            )
            row["nearest_competitor_command"] = nearest_row["command"] if nearest_row is not None else None
            row["nearest_competitor_command_shell"] = (
                nearest_row["command_shell"] if nearest_row is not None else None
            )
            row["nearest_competitor_top_series_command"] = (
                nearest_row["top_series_command"] if nearest_row is not None else None
            )
            row["nearest_competitor_top_series_command_shell"] = (
                nearest_row["top_series_command_shell"] if nearest_row is not None else None
            )
            nearest_gap = row["nearest_competitor_noisy_share_gap"]
            competition_position_label = "solo"
            if nearest_gap is not None:
                if row["rank"] == 1:
                    if nearest_gap <= 0.05:
                        competition_position_label = "contested_leader"
                    elif nearest_gap <= 0.15:
                        competition_position_label = "clear_leader"
                    else:
                        competition_position_label = "dominant_leader"
                else:
                    if nearest_gap <= 0.05:
                        competition_position_label = "neck_and_neck"
                    elif nearest_gap <= 0.15:
                        competition_position_label = "close_chase"
                    else:
                        competition_position_label = "separated"
            row["competition_position_label"] = competition_position_label

    family_hotspots = []
    for row in ordered_family_rows:
        family = row["family"]
        top_family_series = top_series_by_family.get(family)
        if top_family_series is None:
            continue
        hotspot_command = _benchmark_runs_git_report_command(
            benchmark_runs_dir=benchmark_runs_path,
            repo_root=repo_root_path,
            only_noisy=only_noisy,
            top_series_limit=top_series_limit,
            summary_only=summary_only,
            family_filter=family,
            series_prefix=top_family_series["series"],
        )
        top_series_share = round(top_family_series["file_count"] / row["file_count"], 4) if row["file_count"] else 0.0
        average_series_size = round(row["file_count"] / series_count_by_family.get(family, 1), 4) if series_count_by_family.get(family, 0) else 0.0
        concentration_label = "diffuse"
        if top_series_share >= 0.4:
            concentration_label = "concentrated"
        elif top_series_share >= 0.2:
            concentration_label = "mixed"
        focus_mode = "family_first"
        if top_series_share >= 0.3 or series_count_by_family.get(family, 0) <= 3:
            focus_mode = "series_first"
        family_hotspots.append(
            {
                "family": family,
                "family_file_count": row["file_count"],
                "series_count": series_count_by_family.get(family, 0),
                "top_series_prefix": top_family_series["series"],
                "top_series_file_count": top_family_series["file_count"],
                "top_series_share": top_series_share,
                "average_series_size": average_series_size,
                "concentration_label": concentration_label,
                "focus_mode": focus_mode,
                "command": hotspot_command,
                "command_shell": " ".join(_shell_quote_arg(part) for part in hotspot_command),
            }
        )
    recommended_hotspot = None
    if family_hotspots:
        recommended_hotspot = max(
            family_hotspots,
            key=lambda row: (
                1 if row["focus_mode"] == "series_first" else 0,
                row["top_series_share"],
                row["top_series_file_count"],
                -row["series_count"],
                row["family"],
            ),
        )
    series_commands = []
    for row in top_noisy_series:
        series_command = _benchmark_runs_git_report_command(
            benchmark_runs_dir=benchmark_runs_path,
            repo_root=repo_root_path,
            only_noisy=True,
            top_series_limit=top_series_limit,
            summary_only=summary_only,
            family_filter=row["family"],
            series_prefix=row["series"],
        )
        series_commands.append(
            {
                "family": row["family"],
                "series_prefix": row["series"],
                "noisy_file_count": row["file_count"],
                "command": series_command,
                "command_shell": " ".join(_shell_quote_arg(part) for part in series_command),
            }
        )
    recommended_focus = None
    recommended_followups: list[dict] = []
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
        recommended_followups = [recommended_focus]
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
        recommended_followups.append(recommended_focus)
        top_family_series = top_series_by_family.get(recommended_row["family"])
        if top_family_series is not None:
            series_command = _benchmark_runs_git_report_command(
                benchmark_runs_dir=benchmark_runs_path,
                repo_root=repo_root_path,
                only_noisy=True,
                top_series_limit=top_series_limit,
                summary_only=summary_only,
                family_filter=recommended_row["family"],
                series_prefix=top_family_series["series"],
            )
            recommended_followups.append(
                {
                    "scope": "series",
                    "reason": "largest_series_in_recommended_family",
                    "family": recommended_row["family"],
                    "series_prefix": top_family_series["series"],
                    "noisy_file_count": top_family_series["file_count"],
                    "command": series_command,
                    "command_shell": " ".join(_shell_quote_arg(part) for part in series_command),
                }
            )
    if recommended_focus and recommended_focus.get("family"):
        recommended_hotspot = next(
            (row for row in family_hotspots if row["family"] == recommended_focus["family"]),
            recommended_hotspot,
        )
    recommended_drilldown = None
    if recommended_followups:
        recommended_drilldown = recommended_followups[-1]
    elif recommended_focus and recommended_focus.get("scope") == "series":
        recommended_drilldown = recommended_focus
    recommended_next_step = None
    recommended_family = None
    if recommended_focus and recommended_focus.get("family"):
        recommended_family = next(
            (row for row in ordered_family_rows if row["family"] == recommended_focus["family"]),
            None,
        )
    elif len(ordered_family_rows) == 1:
        recommended_family = ordered_family_rows[0]
    recommended_family_gap = None
    recommended_family_comparison = None
    recommended_family_competition_window = None
    recommended_family_competition_summary = None
    if recommended_family is not None:
        competition_index = next(
            (index for index, row in enumerate(family_competition) if row["family"] == recommended_family["family"]),
            None,
        )
        if competition_index is not None:
            previous_competitor = family_competition[competition_index - 1] if competition_index > 0 else None
            next_competitor = (
                family_competition[competition_index + 1]
                if competition_index + 1 < len(family_competition)
                else None
            )
            recommended_family_competition_window = {
                "scope": "competition_window",
                "family": recommended_family["family"],
                "current": family_competition[competition_index],
                "previous": previous_competitor,
                "next": next_competitor,
            }
            current_competitor = family_competition[competition_index]
            recommended_next_step = {
                "reason": "inspect_current_top_series",
                "target": "current_top_series",
                "family": current_competitor["family"],
                "rank": current_competitor["rank"],
                "top_series_prefix": current_competitor["top_series_prefix"],
                "top_series_noisy_file_count": current_competitor["top_series_noisy_file_count"],
                "command": current_competitor["top_series_command"],
                "command_shell": current_competitor["top_series_command_shell"],
            }
            if current_competitor["nearest_competitor_family"] is not None:
                if current_competitor["competition_position_label"] in {
                    "contested_leader",
                    "neck_and_neck",
                    "close_chase",
                }:
                    recommended_next_step = {
                        "reason": "compare_nearest_competitor_top_series",
                        "target": "nearest_competitor_top_series",
                        "family": current_competitor["nearest_competitor_family"],
                        "rank": current_competitor["nearest_competitor_rank"],
                        "top_series_prefix": current_competitor["nearest_competitor_top_series_prefix"],
                        "top_series_noisy_file_count": current_competitor["nearest_competitor_top_series_noisy_file_count"],
                        "command": current_competitor["nearest_competitor_top_series_command"],
                        "command_shell": current_competitor["nearest_competitor_top_series_command_shell"],
                    }
            recommended_family_competition_summary = {
                "scope": "competition_summary",
                "family": current_competitor["family"],
                "rank": current_competitor["rank"],
                "top_series_prefix": current_competitor["top_series_prefix"],
                "top_series_noisy_file_count": current_competitor["top_series_noisy_file_count"],
                "competition_position_label": current_competitor["competition_position_label"],
                "command": current_competitor["command"],
                "command_shell": current_competitor["command_shell"],
                "top_series_command": current_competitor["top_series_command"],
                "top_series_command_shell": current_competitor["top_series_command_shell"],
                "recommended_next_step": recommended_next_step,
                "nearest_competitor": {
                    "direction": current_competitor["nearest_competitor_direction"],
                    "family": current_competitor["nearest_competitor_family"],
                    "rank": current_competitor["nearest_competitor_rank"],
                    "noisy_file_count_gap": current_competitor["nearest_competitor_noisy_file_count_gap"],
                    "noisy_share_gap": current_competitor["nearest_competitor_noisy_share_gap"],
                    "top_series_prefix": current_competitor["nearest_competitor_top_series_prefix"],
                    "top_series_noisy_file_count": current_competitor["nearest_competitor_top_series_noisy_file_count"],
                    "command": current_competitor["nearest_competitor_command"],
                    "command_shell": current_competitor["nearest_competitor_command_shell"],
                    "top_series_command": current_competitor["nearest_competitor_top_series_command"],
                    "top_series_command_shell": current_competitor["nearest_competitor_top_series_command_shell"],
                },
            }
        ranked_index = ranked_family_command_by_name.get(recommended_family["family"])
        if ranked_index is not None and ranked_index + 1 < len(ranked_family_command_rows):
            current_family_command = ranked_family_command_rows[ranked_index]
            next_family_command = ranked_family_command_rows[ranked_index + 1]
            next_family_series = all_noisy_top_series_by_family.get(next_family_command["family"])
            current_noisy_share = (
                round(current_family_command["noisy_file_count"] / noisy_family_total, 4)
                if noisy_family_total
                else 0.0
            )
            next_noisy_share = (
                round(next_family_command["noisy_file_count"] / noisy_family_total, 4)
                if noisy_family_total
                else 0.0
            )
            share_gap = round(current_noisy_share - next_noisy_share, 4)
            file_count_gap = current_family_command["noisy_file_count"] - next_family_command["noisy_file_count"]
            lead_label = "narrow"
            if share_gap >= 0.25:
                lead_label = "wide"
            elif share_gap >= 0.1:
                lead_label = "clear"
            next_family_drilldown_command = None
            next_family_drilldown_command_shell = None
            next_family_series_prefix = None
            next_family_series_noisy_file_count = None
            if next_family_series is not None:
                next_family_drilldown_command = _benchmark_runs_git_report_command(
                    benchmark_runs_dir=benchmark_runs_path,
                    repo_root=repo_root_path,
                    only_noisy=True,
                    top_series_limit=top_series_limit,
                    summary_only=summary_only,
                    family_filter=next_family_command["family"],
                    series_prefix=next_family_series["series"],
                )
                next_family_drilldown_command_shell = " ".join(
                    _shell_quote_arg(part) for part in next_family_drilldown_command
                )
                next_family_series_prefix = next_family_series["series"]
                next_family_series_noisy_file_count = next_family_series["file_count"]
            recommended_family_gap = {
                "scope": "gap_to_next_family",
                "family": recommended_family["family"],
                "next_family": next_family_command["family"],
                "next_family_noisy_file_count": next_family_command["noisy_file_count"],
                "noisy_file_count_gap": file_count_gap,
                "noisy_share_gap": share_gap,
                "lead_label": lead_label,
                "next_family_command": next_family_command["command"],
                "next_family_command_shell": next_family_command["command_shell"],
                "next_family_series_prefix": next_family_series_prefix,
                "next_family_series_noisy_file_count": next_family_series_noisy_file_count,
                "next_family_drilldown_command": next_family_drilldown_command,
                "next_family_drilldown_command_shell": next_family_drilldown_command_shell,
            }
            recommended_family_comparison = {
                "scope": "leader_vs_runner_up",
                "leader_hotspot": _build_noisy_family_hotspot_summary(recommended_family["family"]),
                "runner_up_hotspot": _build_noisy_family_hotspot_summary(next_family_command["family"]),
                "gap": recommended_family_gap,
            }
        else:
            recommended_family_gap = {
                "scope": "single_family_view",
                "family": recommended_family["family"],
                "reported_file_share": recommended_family["reported_file_share"],
                "dominance_label": recommended_family["dominance_label"],
            }
            recommended_family_comparison = {
                "scope": "single_family_view",
                "leader_hotspot": _build_noisy_family_hotspot_summary(recommended_family["family"]),
            }
    recommended_sequence: list[dict] = []
    for recommendation in [recommended_focus, recommended_drilldown, recommended_next_step]:
        if recommendation is not None and recommendation not in recommended_sequence:
            recommended_sequence.append(recommendation)
    recommended_sequence_targets: list[dict] = []
    for recommendation in recommended_sequence:
        if recommendation.get("target") in {"nearest_competitor_top_series", "current_top_series"}:
            target_ref = {
                "type": "top_series",
                "target": recommendation.get("target"),
                "family": recommendation.get("family"),
                "rank": recommendation.get("rank"),
                "series_prefix": recommendation.get("top_series_prefix"),
            }
        elif recommendation.get("scope") == "family":
            target_ref = {
                "type": "family",
                "family": recommendation.get("family"),
            }
        elif recommendation.get("scope") == "series":
            target_ref = {
                "type": "series",
                "family": recommendation.get("family"),
                "series_prefix": recommendation.get("series_prefix"),
            }
        else:
            target_ref = {
                "type": recommendation.get("target") or recommendation.get("scope") or "recommendation",
                "reason": recommendation.get("reason"),
            }
        recommended_sequence_targets.append(target_ref)
    recommended_sequence_labels: list[str] = []
    for recommendation in recommended_sequence:
        if recommendation.get("target") == "nearest_competitor_top_series":
            label = (
                f"compare {recommendation.get('family')} rank {recommendation.get('rank')} "
                f"/ {recommendation.get('top_series_prefix')}"
            )
        elif recommendation.get("target") == "current_top_series":
            label = (
                f"inspect {recommendation.get('family')} rank {recommendation.get('rank')} "
                f"/ {recommendation.get('top_series_prefix')}"
            )
        elif recommendation.get("scope") == "family":
            label = f"focus family {recommendation.get('family')}"
        elif recommendation.get("scope") == "series" and recommendation.get("family"):
            label = f"focus series {recommendation.get('family')} / {recommendation.get('series_prefix')}"
        elif recommendation.get("scope") == "series":
            label = f"focus series {recommendation.get('series_prefix')}"
        else:
            label = recommendation.get("reason") or recommendation.get("scope") or "recommendation"
        recommended_sequence_labels.append(label)
    recommended_sequence_preview = " -> ".join(recommended_sequence_labels)
    recommended_sequence_shells: list[str] = []
    recommended_sequence_commands: list[list[str]] = []
    for recommendation in recommended_sequence:
        command = recommendation.get("command")
        if command and command not in recommended_sequence_commands:
            recommended_sequence_commands.append(command)
        command_shell = recommendation.get("command_shell")
        if command_shell and command_shell not in recommended_sequence_shells:
            recommended_sequence_shells.append(command_shell)
    recommended_sequence_steps: list[dict] = []
    for index, recommendation in enumerate(recommended_sequence, start=1):
        if recommendation == recommended_focus:
            phase = "focus"
        elif recommendation == recommended_drilldown:
            phase = "drilldown"
        elif recommendation == recommended_next_step:
            phase = "next_step"
        else:
            phase = "sequence"
        recommended_sequence_steps.append(
            {
                "step": index,
                "phase": phase,
                "label": recommended_sequence_labels[index - 1],
                "target": recommended_sequence_targets[index - 1],
                "command": recommendation.get("command"),
                "command_shell": recommendation.get("command_shell"),
            }
        )
    recommended_sequence_by_phase = {
        step["phase"]: step for step in recommended_sequence_steps
    }
    recommended_sequence_summary = {
        "step_count": len(recommended_sequence_steps),
        "command_step_count": sum(1 for step in recommended_sequence_steps if step["command"]),
        "non_command_step_count": sum(1 for step in recommended_sequence_steps if not step["command"]),
        "command_coverage": round(
            sum(1 for step in recommended_sequence_steps if step["command"]) / len(recommended_sequence_steps),
            4,
        ) if recommended_sequence_steps else 0.0,
        "command_coverage_label": (
            "full"
            if recommended_sequence_steps and all(step["command"] for step in recommended_sequence_steps)
            else "partial"
            if any(step["command"] for step in recommended_sequence_steps)
            else "none"
        ),
        "command_phase_order": [step["phase"] for step in recommended_sequence_steps if step["command"]],
        "non_command_phase_order": [step["phase"] for step in recommended_sequence_steps if not step["command"]],
        "command_phase_signature": "->".join(step["phase"] for step in recommended_sequence_steps if step["command"]),
        "non_command_phase_signature": "->".join(step["phase"] for step in recommended_sequence_steps if not step["command"]),
        "phase_order": [step["phase"] for step in recommended_sequence_steps],
        "phase_signature": "->".join(step["phase"] for step in recommended_sequence_steps),
        "entry_step": recommended_sequence_steps[0]["step"] if recommended_sequence_steps else None,
        "terminal_step": recommended_sequence_steps[-1]["step"] if recommended_sequence_steps else None,
        "entry_phase": recommended_sequence_steps[0]["phase"] if recommended_sequence_steps else None,
        "terminal_phase": recommended_sequence_steps[-1]["phase"] if recommended_sequence_steps else None,
        "entry_label": recommended_sequence_steps[0]["label"] if recommended_sequence_steps else None,
        "terminal_label": recommended_sequence_steps[-1]["label"] if recommended_sequence_steps else None,
        "entry_target": recommended_sequence_steps[0]["target"] if recommended_sequence_steps else None,
        "terminal_target": recommended_sequence_steps[-1]["target"] if recommended_sequence_steps else None,
        "entry_command": recommended_sequence_steps[0]["command"] if recommended_sequence_steps else None,
        "entry_command_shell": recommended_sequence_steps[0]["command_shell"] if recommended_sequence_steps else None,
        "entry_has_command": bool(recommended_sequence_steps[0]["command"]) if recommended_sequence_steps else False,
        "terminal_command": recommended_sequence_steps[-1]["command"] if recommended_sequence_steps else None,
        "terminal_command_shell": recommended_sequence_steps[-1]["command_shell"] if recommended_sequence_steps else None,
        "terminal_has_command": bool(recommended_sequence_steps[-1]["command"]) if recommended_sequence_steps else False,
        "preview": recommended_sequence_preview,
        "has_drilldown": "drilldown" in recommended_sequence_by_phase,
        "has_next_step": "next_step" in recommended_sequence_by_phase,
    }
    recommended_sequence_endpoints = {
        "first": recommended_sequence_steps[0] if recommended_sequence_steps else None,
        "last": recommended_sequence_steps[-1] if recommended_sequence_steps else None,
    }
    recommended_sequence_transitions: list[dict] = []
    for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:]):
        recommended_sequence_transitions.append(
            {
                "from_phase": previous_step["phase"],
                "to_phase": next_step["phase"],
                "from_step": previous_step["step"],
                "to_step": next_step["step"],
                "from_label": previous_step["label"],
                "to_label": next_step["label"],
            }
        )
    recommended_sequence_transition_summary = {
        "transition_count": len(recommended_sequence_transitions),
        "command_transition_count": sum(
            1
            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
            if previous_step["command"] and next_step["command"]
        ),
        "mixed_transition_count": sum(
            1
            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
            if bool(previous_step["command"]) != bool(next_step["command"])
        ),
        "non_command_transition_count": sum(
            1
            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
            if not previous_step["command"] and not next_step["command"]
        ),
        "command_transition_coverage": round(
            sum(
                1
                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                if previous_step["command"] and next_step["command"]
            ) / len(recommended_sequence_transitions),
            4,
        ) if recommended_sequence_transitions else 0.0,
        "transition_mode_counts": {
            "command": sum(
                1
                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                if previous_step["command"] and next_step["command"]
            ),
            "mixed": sum(
                1
                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                if bool(previous_step["command"]) != bool(next_step["command"])
            ),
            "non_command": sum(
                1
                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                if not previous_step["command"] and not next_step["command"]
            ),
        },
        "dominant_transition_mode": max(
            (
                ("command", sum(
                    1
                    for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                    if previous_step["command"] and next_step["command"]
                )),
                ("mixed", sum(
                    1
                    for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                    if bool(previous_step["command"]) != bool(next_step["command"])
                )),
                ("non_command", sum(
                    1
                    for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                    if not previous_step["command"] and not next_step["command"]
                )),
            ),
            key=lambda item: (item[1], {"command": 2, "mixed": 1, "non_command": 0}[item[0]]),
        )[0] if recommended_sequence_transitions else None,
        "dominant_transition_mode_count": max(
            (
                ("command", sum(
                    1
                    for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                    if previous_step["command"] and next_step["command"]
                )),
                ("mixed", sum(
                    1
                    for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                    if bool(previous_step["command"]) != bool(next_step["command"])
                )),
                ("non_command", sum(
                    1
                    for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                    if not previous_step["command"] and not next_step["command"]
                )),
            ),
            key=lambda item: (item[1], {"command": 2, "mixed": 1, "non_command": 0}[item[0]]),
        )[1] if recommended_sequence_transitions else 0,
        "dominant_transition_mode_gap": (
            sorted(
                (
                    sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if previous_step["command"] and next_step["command"]
                    ),
                    sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if bool(previous_step["command"]) != bool(next_step["command"])
                    ),
                    sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if not previous_step["command"] and not next_step["command"]
                    ),
                ),
                reverse=True,
            )[0]
            - sorted(
                (
                    sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if previous_step["command"] and next_step["command"]
                    ),
                    sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if bool(previous_step["command"]) != bool(next_step["command"])
                    ),
                    sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if not previous_step["command"] and not next_step["command"]
                    ),
                ),
                reverse=True,
            )[1]
        ) if recommended_sequence_transitions else 0,
        "dominant_transition_mode_gap_share": round(
            (
                sorted(
                    (
                        sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if previous_step["command"] and next_step["command"]
                        ),
                        sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if bool(previous_step["command"]) != bool(next_step["command"])
                        ),
                        sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if not previous_step["command"] and not next_step["command"]
                        ),
                    ),
                    reverse=True,
                )[0]
                - sorted(
                    (
                        sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if previous_step["command"] and next_step["command"]
                        ),
                        sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if bool(previous_step["command"]) != bool(next_step["command"])
                        ),
                        sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if not previous_step["command"] and not next_step["command"]
                        ),
                    ),
                    reverse=True,
                )[1]
            ) / len(recommended_sequence_transitions),
            4,
        ) if recommended_sequence_transitions else 0.0,
        "runner_up_transition_mode": sorted(
            (
                ("command", sum(
                    1
                    for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                    if previous_step["command"] and next_step["command"]
                )),
                ("mixed", sum(
                    1
                    for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                    if bool(previous_step["command"]) != bool(next_step["command"])
                )),
                ("non_command", sum(
                    1
                    for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                    if not previous_step["command"] and not next_step["command"]
                )),
            ),
            key=lambda item: (item[1], {"command": 2, "mixed": 1, "non_command": 0}[item[0]]),
            reverse=True,
        )[1][0] if recommended_sequence_transitions else None,
        "runner_up_transition_mode_count": sorted(
            (
                ("command", sum(
                    1
                    for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                    if previous_step["command"] and next_step["command"]
                )),
                ("mixed", sum(
                    1
                    for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                    if bool(previous_step["command"]) != bool(next_step["command"])
                )),
                ("non_command", sum(
                    1
                    for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                    if not previous_step["command"] and not next_step["command"]
                )),
            ),
            key=lambda item: (item[1], {"command": 2, "mixed": 1, "non_command": 0}[item[0]]),
            reverse=True,
        )[1][1] if recommended_sequence_transitions else 0,
        "transition_mode_rank_order": [
            item[0]
            for item in sorted(
                (
                    ("command", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if previous_step["command"] and next_step["command"]
                    )),
                    ("mixed", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if bool(previous_step["command"]) != bool(next_step["command"])
                    )),
                    ("non_command", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if not previous_step["command"] and not next_step["command"]
                    )),
                ),
                key=lambda item: (item[1], {"command": 2, "mixed": 1, "non_command": 0}[item[0]]),
                reverse=True,
            )
        ] if recommended_sequence_transitions else [],
        "transition_mode_rankings": [
            {
                "rank": index,
                "mode": item[0],
                "count": item[1],
                "share": round(item[1] / len(recommended_sequence_transitions), 4),
            }
            for index, item in enumerate(
                sorted(
                    (
                        ("command", sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if previous_step["command"] and next_step["command"]
                        )),
                        ("mixed", sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if bool(previous_step["command"]) != bool(next_step["command"])
                        )),
                        ("non_command", sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if not previous_step["command"] and not next_step["command"]
                        )),
                    ),
                    key=lambda item: (item[1], {"command": 2, "mixed": 1, "non_command": 0}[item[0]]),
                    reverse=True,
                ),
                start=1,
            )
        ] if recommended_sequence_transitions else [],
        "transition_mode_rank_map": {
            item["mode"]: item
            for item in [
                {
                    "rank": index,
                    "mode": ranking_item[0],
                    "count": ranking_item[1],
                    "share": round(ranking_item[1] / len(recommended_sequence_transitions), 4),
                }
                for index, ranking_item in enumerate(
                    sorted(
                        (
                            ("command", sum(
                                1
                                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                if previous_step["command"] and next_step["command"]
                            )),
                            ("mixed", sum(
                                1
                                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                if bool(previous_step["command"]) != bool(next_step["command"])
                            )),
                            ("non_command", sum(
                                1
                                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                if not previous_step["command"] and not next_step["command"]
                            )),
                        ),
                        key=lambda item: (item[1], {"command": 2, "mixed": 1, "non_command": 0}[item[0]]),
                        reverse=True,
                    ),
                    start=1,
                )
            ]
        } if recommended_sequence_transitions else {},
        "transition_mode_ranking_signature": " > ".join(
            f"{item[0]}:{item[1]}"
            for item in sorted(
                (
                    ("command", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if previous_step["command"] and next_step["command"]
                    )),
                    ("mixed", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if bool(previous_step["command"]) != bool(next_step["command"])
                    )),
                    ("non_command", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if not previous_step["command"] and not next_step["command"]
                    )),
                ),
                key=lambda item: (item[1], {"command": 2, "mixed": 1, "non_command": 0}[item[0]]),
                reverse=True,
            )
        ) if recommended_sequence_transitions else "",
        "transition_mode_share_signature": " > ".join(
            f"{item[0]}:{round(item[1] / len(recommended_sequence_transitions), 4)}"
            for item in sorted(
                (
                    ("command", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if previous_step["command"] and next_step["command"]
                    )),
                    ("mixed", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if bool(previous_step["command"]) != bool(next_step["command"])
                    )),
                    ("non_command", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if not previous_step["command"] and not next_step["command"]
                    )),
                ),
                key=lambda item: (item[1], {"command": 2, "mixed": 1, "non_command": 0}[item[0]]),
                reverse=True,
            )
        ) if recommended_sequence_transitions else "",
        "runner_up_transition_mode_share": round(
            sorted(
                (
                    ("command", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if previous_step["command"] and next_step["command"]
                    )),
                    ("mixed", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if bool(previous_step["command"]) != bool(next_step["command"])
                    )),
                    ("non_command", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if not previous_step["command"] and not next_step["command"]
                    )),
                ),
                key=lambda item: (item[1], {"command": 2, "mixed": 1, "non_command": 0}[item[0]]),
                reverse=True,
            )[1][1] / len(recommended_sequence_transitions),
            4,
        ) if recommended_sequence_transitions else 0.0,
        "is_contested_transition_mode": (
            (
                sorted(
                    (
                        sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if previous_step["command"] and next_step["command"]
                        ),
                        sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if bool(previous_step["command"]) != bool(next_step["command"])
                        ),
                        sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if not previous_step["command"] and not next_step["command"]
                        ),
                    ),
                    reverse=True,
                )[0]
                - sorted(
                    (
                        sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if previous_step["command"] and next_step["command"]
                        ),
                        sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if bool(previous_step["command"]) != bool(next_step["command"])
                        ),
                        sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if not previous_step["command"] and not next_step["command"]
                        ),
                    ),
                    reverse=True,
                )[1]
            )
            <= 1
        ) if recommended_sequence_transitions else False,
        "transition_mode_competition": {
            "dominant_mode": max(
                (
                    ("command", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if previous_step["command"] and next_step["command"]
                    )),
                    ("mixed", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if bool(previous_step["command"]) != bool(next_step["command"])
                    )),
                    ("non_command", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if not previous_step["command"] and not next_step["command"]
                    )),
                ),
                key=lambda item: (item[1], {"command": 2, "mixed": 1, "non_command": 0}[item[0]]),
            )[0],
            "dominant_count": max(
                (
                    ("command", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if previous_step["command"] and next_step["command"]
                    )),
                    ("mixed", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if bool(previous_step["command"]) != bool(next_step["command"])
                    )),
                    ("non_command", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if not previous_step["command"] and not next_step["command"]
                    )),
                ),
                key=lambda item: (item[1], {"command": 2, "mixed": 1, "non_command": 0}[item[0]]),
            )[1],
            "dominant_share": round(
                max(
                    (
                        ("command", sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if previous_step["command"] and next_step["command"]
                        )),
                        ("mixed", sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if bool(previous_step["command"]) != bool(next_step["command"])
                        )),
                        ("non_command", sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if not previous_step["command"] and not next_step["command"]
                        )),
                    ),
                    key=lambda item: (item[1], {"command": 2, "mixed": 1, "non_command": 0}[item[0]]),
                )[1] / len(recommended_sequence_transitions),
                4,
            ),
            "runner_up_mode": sorted(
                (
                    ("command", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if previous_step["command"] and next_step["command"]
                    )),
                    ("mixed", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if bool(previous_step["command"]) != bool(next_step["command"])
                    )),
                    ("non_command", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if not previous_step["command"] and not next_step["command"]
                    )),
                ),
                key=lambda item: (item[1], {"command": 2, "mixed": 1, "non_command": 0}[item[0]]),
                reverse=True,
            )[1][0],
            "runner_up_count": sorted(
                (
                    ("command", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if previous_step["command"] and next_step["command"]
                    )),
                    ("mixed", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if bool(previous_step["command"]) != bool(next_step["command"])
                    )),
                    ("non_command", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if not previous_step["command"] and not next_step["command"]
                    )),
                ),
                key=lambda item: (item[1], {"command": 2, "mixed": 1, "non_command": 0}[item[0]]),
                reverse=True,
            )[1][1],
            "runner_up_share": round(
                sorted(
                    (
                        ("command", sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if previous_step["command"] and next_step["command"]
                        )),
                        ("mixed", sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if bool(previous_step["command"]) != bool(next_step["command"])
                        )),
                        ("non_command", sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if not previous_step["command"] and not next_step["command"]
                        )),
                    ),
                    key=lambda item: (item[1], {"command": 2, "mixed": 1, "non_command": 0}[item[0]]),
                    reverse=True,
                )[1][1] / len(recommended_sequence_transitions),
                4,
            ),
            "gap": (
                sorted(
                    (
                        sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if previous_step["command"] and next_step["command"]
                        ),
                        sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if bool(previous_step["command"]) != bool(next_step["command"])
                        ),
                        sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if not previous_step["command"] and not next_step["command"]
                        ),
                    ),
                    reverse=True,
                )[0]
                - sorted(
                    (
                        sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if previous_step["command"] and next_step["command"]
                        ),
                        sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if bool(previous_step["command"]) != bool(next_step["command"])
                        ),
                        sum(
                            1
                            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                            if not previous_step["command"] and not next_step["command"]
                        ),
                    ),
                    reverse=True,
                )[1]
            ),
            "gap_share": round(
                (
                    sorted(
                        (
                            sum(
                                1
                                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                if previous_step["command"] and next_step["command"]
                            ),
                            sum(
                                1
                                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                if bool(previous_step["command"]) != bool(next_step["command"])
                            ),
                            sum(
                                1
                                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                if not previous_step["command"] and not next_step["command"]
                            ),
                        ),
                        reverse=True,
                    )[0]
                    - sorted(
                        (
                            sum(
                                1
                                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                if previous_step["command"] and next_step["command"]
                            ),
                            sum(
                                1
                                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                if bool(previous_step["command"]) != bool(next_step["command"])
                            ),
                            sum(
                                1
                                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                if not previous_step["command"] and not next_step["command"]
                            ),
                        ),
                        reverse=True,
                    )[1]
                ) / len(recommended_sequence_transitions),
                4,
            ),
            "competition_signature": (
                f"{max((('command', sum(1 for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:]) if previous_step['command'] and next_step['command'])), ('mixed', sum(1 for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:]) if bool(previous_step['command']) != bool(next_step['command']))), ('non_command', sum(1 for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:]) if not previous_step['command'] and not next_step['command']))), key=lambda item: (item[1], {'command': 2, 'mixed': 1, 'non_command': 0}[item[0]]))[0]}"
                f">{sorted((('command', sum(1 for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:]) if previous_step['command'] and next_step['command'])), ('mixed', sum(1 for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:]) if bool(previous_step['command']) != bool(next_step['command']))), ('non_command', sum(1 for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:]) if not previous_step['command'] and not next_step['command']))), key=lambda item: (item[1], {'command': 2, 'mixed': 1, 'non_command': 0}[item[0]]), reverse=True)[1][0]}"
            ),
            "gap_label": (
                "decisive"
                if (
                    sorted(
                        (
                            sum(
                                1
                                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                if previous_step["command"] and next_step["command"]
                            ),
                            sum(
                                1
                                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                if bool(previous_step["command"]) != bool(next_step["command"])
                            ),
                            sum(
                                1
                                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                if not previous_step["command"] and not next_step["command"]
                            ),
                        ),
                        reverse=True,
                    )[0]
                    - sorted(
                        (
                            sum(
                                1
                                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                if previous_step["command"] and next_step["command"]
                            ),
                            sum(
                                1
                                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                if bool(previous_step["command"]) != bool(next_step["command"])
                            ),
                            sum(
                                1
                                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                if not previous_step["command"] and not next_step["command"]
                            ),
                        ),
                        reverse=True,
                    )[1]
                )
                > 1
                else "narrow"
            ),
            "competition_label": (
                "contested"
                if (
                    (
                        sorted(
                            (
                                sum(
                                    1
                                    for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                    if previous_step["command"] and next_step["command"]
                                ),
                                sum(
                                    1
                                    for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                    if bool(previous_step["command"]) != bool(next_step["command"])
                                ),
                                sum(
                                    1
                                    for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                    if not previous_step["command"] and not next_step["command"]
                                ),
                            ),
                            reverse=True,
                        )[0]
                        - sorted(
                            (
                                sum(
                                    1
                                    for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                    if previous_step["command"] and next_step["command"]
                                ),
                                sum(
                                    1
                                    for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                    if bool(previous_step["command"]) != bool(next_step["command"])
                                ),
                                sum(
                                    1
                                    for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                    if not previous_step["command"] and not next_step["command"]
                                ),
                            ),
                            reverse=True,
                        )[1]
                    )
                    <= 1
                )
                else "clear"
            ),
            "is_contested": (
                (
                    sorted(
                        (
                            sum(
                                1
                                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                if previous_step["command"] and next_step["command"]
                            ),
                            sum(
                                1
                                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                if bool(previous_step["command"]) != bool(next_step["command"])
                            ),
                            sum(
                                1
                                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                if not previous_step["command"] and not next_step["command"]
                            ),
                        ),
                        reverse=True,
                    )[0]
                    - sorted(
                        (
                            sum(
                                1
                                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                if previous_step["command"] and next_step["command"]
                            ),
                            sum(
                                1
                                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                if bool(previous_step["command"]) != bool(next_step["command"])
                            ),
                            sum(
                                1
                                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                                if not previous_step["command"] and not next_step["command"]
                            ),
                        ),
                        reverse=True,
                    )[1]
                )
                <= 1
            ),
        } if recommended_sequence_transitions else None,
        "dominant_transition_mode_share": round(
            max(
                (
                    ("command", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if previous_step["command"] and next_step["command"]
                    )),
                    ("mixed", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if bool(previous_step["command"]) != bool(next_step["command"])
                    )),
                    ("non_command", sum(
                        1
                        for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
                        if not previous_step["command"] and not next_step["command"]
                    )),
                ),
                key=lambda item: (item[1], {"command": 2, "mixed": 1, "non_command": 0}[item[0]]),
            )[1] / len(recommended_sequence_transitions),
            4,
        ) if recommended_sequence_transitions else 0.0,
        "command_transition_coverage_label": (
            "full"
            if recommended_sequence_transitions
            and all(
                previous_step["command"] and next_step["command"]
                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
            )
            else "partial"
            if any(
                previous_step["command"] and next_step["command"]
                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
            )
            else "none"
        ),
        "command_phase_signatures": [
            f"{previous_step['phase']}->{next_step['phase']}"
            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
            if previous_step["command"] and next_step["command"]
        ],
        "transition_mode_order": [
            (
                "command"
                if previous_step["command"] and next_step["command"]
                else "mixed"
                if bool(previous_step["command"]) != bool(next_step["command"])
                else "non_command"
            )
            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
        ],
        "transition_mode_signature": "->".join(
            (
                "command"
                if previous_step["command"] and next_step["command"]
                else "mixed"
                if bool(previous_step["command"]) != bool(next_step["command"])
                else "non_command"
            )
            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
        ),
        "present_transition_modes": [
            mode
            for mode in ["command", "mixed", "non_command"]
            if mode
            in {
                (
                    "command"
                    if previous_step["command"] and next_step["command"]
                    else "mixed"
                    if bool(previous_step["command"]) != bool(next_step["command"])
                    else "non_command"
                )
                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
            }
        ],
        "present_transition_mode_signature": "|".join(
            [
                mode
                for mode in ["command", "mixed", "non_command"]
                if mode
                in {
                    (
                        "command"
                        if previous_step["command"] and next_step["command"]
                        else "mixed"
                        if bool(previous_step["command"]) != bool(next_step["command"])
                        else "non_command"
                    )
                    for previous_step, next_step in zip(
                        recommended_sequence_steps, recommended_sequence_steps[1:]
                    )
                }
            ]
        ),
        "absent_transition_modes": [
            mode
            for mode in ["command", "mixed", "non_command"]
            if mode
            not in {
                (
                    "command"
                    if previous_step["command"] and next_step["command"]
                    else "mixed"
                    if bool(previous_step["command"]) != bool(next_step["command"])
                    else "non_command"
                )
                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
            }
        ],
        "absent_transition_mode_signature": "|".join(
            [
                mode
                for mode in ["command", "mixed", "non_command"]
                if mode
                not in {
                    (
                        "command"
                        if previous_step["command"] and next_step["command"]
                        else "mixed"
                        if bool(previous_step["command"]) != bool(next_step["command"])
                        else "non_command"
                    )
                    for previous_step, next_step in zip(
                        recommended_sequence_steps, recommended_sequence_steps[1:]
                    )
                }
            ]
        ),
        "absent_transition_mode_count": len(
            {
                mode
                for mode in ["command", "mixed", "non_command"]
                if mode
                not in {
                    (
                        "command"
                        if previous_step["command"] and next_step["command"]
                        else "mixed"
                        if bool(previous_step["command"]) != bool(next_step["command"])
                        else "non_command"
                    )
                    for previous_step, next_step in zip(
                        recommended_sequence_steps, recommended_sequence_steps[1:]
                    )
                }
            }
        ),
        "is_full_transition_mode_coverage": len(
            {
                (
                    "command"
                    if previous_step["command"] and next_step["command"]
                    else "mixed"
                    if bool(previous_step["command"]) != bool(next_step["command"])
                    else "non_command"
                )
                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
            }
        )
        == 3,
        "transition_mode_coverage_label": (
            "full"
            if len(
                {
                    (
                        "command"
                        if previous_step["command"] and next_step["command"]
                        else "mixed"
                        if bool(previous_step["command"]) != bool(next_step["command"])
                        else "non_command"
                    )
                    for previous_step, next_step in zip(
                        recommended_sequence_steps, recommended_sequence_steps[1:]
                    )
                }
            )
            == 3
            else "partial"
        ),
        "transition_mode_coverage": round(
            len(
                {
                    (
                        "command"
                        if previous_step["command"] and next_step["command"]
                        else "mixed"
                        if bool(previous_step["command"]) != bool(next_step["command"])
                        else "non_command"
                    )
                    for previous_step, next_step in zip(
                        recommended_sequence_steps, recommended_sequence_steps[1:]
                    )
                }
            )
            / 3,
            4,
        ),
        "absent_transition_mode_coverage": round(
            len(
                {
                    mode
                    for mode in ["command", "mixed", "non_command"]
                    if mode
                    not in {
                        (
                            "command"
                            if previous_step["command"] and next_step["command"]
                            else "mixed"
                            if bool(previous_step["command"]) != bool(next_step["command"])
                            else "non_command"
                        )
                        for previous_step, next_step in zip(
                            recommended_sequence_steps, recommended_sequence_steps[1:]
                        )
                    }
                }
            )
            / 3,
            4,
        ),
        "absent_transition_mode_coverage_label": (
            "none"
            if len(
                {
                    mode
                    for mode in ["command", "mixed", "non_command"]
                    if mode
                    not in {
                        (
                            "command"
                            if previous_step["command"] and next_step["command"]
                            else "mixed"
                            if bool(previous_step["command"]) != bool(next_step["command"])
                            else "non_command"
                        )
                        for previous_step, next_step in zip(
                            recommended_sequence_steps, recommended_sequence_steps[1:]
                        )
                    }
                }
            )
            == 0
            else "partial"
        ),
        "has_absent_transition_modes": len(
            {
                mode
                for mode in ["command", "mixed", "non_command"]
                if mode
                not in {
                    (
                        "command"
                        if previous_step["command"] and next_step["command"]
                        else "mixed"
                        if bool(previous_step["command"]) != bool(next_step["command"])
                        else "non_command"
                    )
                    for previous_step, next_step in zip(
                        recommended_sequence_steps, recommended_sequence_steps[1:]
                    )
                }
            }
        )
        > 0,
        "transition_mode_coverage_gap": round(
            len(
                {
                    mode
                    for mode in ["command", "mixed", "non_command"]
                    if mode
                    not in {
                        (
                            "command"
                            if previous_step["command"] and next_step["command"]
                            else "mixed"
                            if bool(previous_step["command"]) != bool(next_step["command"])
                            else "non_command"
                        )
                        for previous_step, next_step in zip(
                            recommended_sequence_steps, recommended_sequence_steps[1:]
                        )
                    }
                }
            )
            / 3,
            4,
        ),
        "transition_mode_coverage_gap_label": (
            "closed"
            if len(
                {
                    mode
                    for mode in ["command", "mixed", "non_command"]
                    if mode
                    not in {
                        (
                            "command"
                            if previous_step["command"] and next_step["command"]
                            else "mixed"
                            if bool(previous_step["command"]) != bool(next_step["command"])
                            else "non_command"
                        )
                        for previous_step, next_step in zip(
                            recommended_sequence_steps, recommended_sequence_steps[1:]
                        )
                    }
                }
            )
            == 0
            else "open"
        ),
        "transition_mode_coverage_balance": round(
            (
                len(
                    {
                        (
                            "command"
                            if previous_step["command"] and next_step["command"]
                            else "mixed"
                            if bool(previous_step["command"]) != bool(next_step["command"])
                            else "non_command"
                        )
                        for previous_step, next_step in zip(
                            recommended_sequence_steps, recommended_sequence_steps[1:]
                        )
                    }
                )
                / 3
            )
            - (
                len(
                    {
                        mode
                        for mode in ["command", "mixed", "non_command"]
                        if mode
                        not in {
                            (
                                "command"
                                if previous_step["command"] and next_step["command"]
                                else "mixed"
                                if bool(previous_step["command"]) != bool(next_step["command"])
                                else "non_command"
                            )
                            for previous_step, next_step in zip(
                                recommended_sequence_steps, recommended_sequence_steps[1:]
                            )
                        }
                    }
                )
                / 3
            ),
            4,
        ),
        "transition_mode_coverage_balance_label": (
            "surplus"
            if (
                (
                    len(
                        {
                            (
                                "command"
                                if previous_step["command"] and next_step["command"]
                                else "mixed"
                                if bool(previous_step["command"]) != bool(next_step["command"])
                                else "non_command"
                            )
                            for previous_step, next_step in zip(
                                recommended_sequence_steps, recommended_sequence_steps[1:]
                            )
                        }
                    )
                    / 3
                )
                - (
                    len(
                        {
                            mode
                            for mode in ["command", "mixed", "non_command"]
                            if mode
                            not in {
                                (
                                    "command"
                                    if previous_step["command"] and next_step["command"]
                                    else "mixed"
                                    if bool(previous_step["command"]) != bool(next_step["command"])
                                    else "non_command"
                                )
                                for previous_step, next_step in zip(
                                    recommended_sequence_steps, recommended_sequence_steps[1:]
                                )
                            }
                        }
                    )
                    / 3
                )
            )
            > 0
            else "balanced"
            if (
                (
                    len(
                        {
                            (
                                "command"
                                if previous_step["command"] and next_step["command"]
                                else "mixed"
                                if bool(previous_step["command"]) != bool(next_step["command"])
                                else "non_command"
                            )
                            for previous_step, next_step in zip(
                                recommended_sequence_steps, recommended_sequence_steps[1:]
                            )
                        }
                    )
                    / 3
                )
                - (
                    len(
                        {
                            mode
                            for mode in ["command", "mixed", "non_command"]
                            if mode
                            not in {
                                (
                                    "command"
                                    if previous_step["command"] and next_step["command"]
                                    else "mixed"
                                    if bool(previous_step["command"]) != bool(next_step["command"])
                                    else "non_command"
                                )
                                for previous_step, next_step in zip(
                                    recommended_sequence_steps, recommended_sequence_steps[1:]
                                )
                            }
                        }
                    )
                    / 3
                )
            )
            == 0
            else "deficit"
        ),
        "has_transition_mode_coverage_deficit": (
            (
                (
                    len(
                        {
                            (
                                "command"
                                if previous_step["command"] and next_step["command"]
                                else "mixed"
                                if bool(previous_step["command"]) != bool(next_step["command"])
                                else "non_command"
                            )
                            for previous_step, next_step in zip(
                                recommended_sequence_steps, recommended_sequence_steps[1:]
                            )
                        }
                    )
                    / 3
                )
                - (
                    len(
                        {
                            mode
                            for mode in ["command", "mixed", "non_command"]
                            if mode
                            not in {
                                (
                                    "command"
                                    if previous_step["command"] and next_step["command"]
                                    else "mixed"
                                    if bool(previous_step["command"]) != bool(next_step["command"])
                                    else "non_command"
                                )
                                for previous_step, next_step in zip(
                                    recommended_sequence_steps, recommended_sequence_steps[1:]
                                )
                            }
                        }
                    )
                    / 3
                )
            )
            < 0
        ),
        "has_balanced_transition_mode_coverage": (
            (
                (
                    len(
                        {
                            (
                                "command"
                                if previous_step["command"] and next_step["command"]
                                else "mixed"
                                if bool(previous_step["command"]) != bool(next_step["command"])
                                else "non_command"
                            )
                            for previous_step, next_step in zip(
                                recommended_sequence_steps, recommended_sequence_steps[1:]
                            )
                        }
                    )
                    / 3
                )
                - (
                    len(
                        {
                            mode
                            for mode in ["command", "mixed", "non_command"]
                            if mode
                            not in {
                                (
                                    "command"
                                    if previous_step["command"] and next_step["command"]
                                    else "mixed"
                                    if bool(previous_step["command"]) != bool(next_step["command"])
                                    else "non_command"
                                )
                                for previous_step, next_step in zip(
                                    recommended_sequence_steps, recommended_sequence_steps[1:]
                                )
                            }
                        }
                    )
                    / 3
                )
            )
            == 0
        ),
        "has_transition_mode_coverage_surplus": (
            (
                (
                    len(
                        {
                            (
                                "command"
                                if previous_step["command"] and next_step["command"]
                                else "mixed"
                                if bool(previous_step["command"]) != bool(next_step["command"])
                                else "non_command"
                            )
                            for previous_step, next_step in zip(
                                recommended_sequence_steps, recommended_sequence_steps[1:]
                            )
                        }
                    )
                    / 3
                )
                - (
                    len(
                        {
                            mode
                            for mode in ["command", "mixed", "non_command"]
                            if mode
                            not in {
                                (
                                    "command"
                                    if previous_step["command"] and next_step["command"]
                                    else "mixed"
                                    if bool(previous_step["command"]) != bool(next_step["command"])
                                    else "non_command"
                                )
                                for previous_step, next_step in zip(
                                    recommended_sequence_steps, recommended_sequence_steps[1:]
                                )
                            }
                        }
                    )
                    / 3
                )
            )
            > 0
        ),
        "transition_mode_coverage_total": round(
            (
                len(
                    {
                        (
                            "command"
                            if previous_step["command"] and next_step["command"]
                            else "mixed"
                            if bool(previous_step["command"]) != bool(next_step["command"])
                            else "non_command"
                        )
                        for previous_step, next_step in zip(
                            recommended_sequence_steps, recommended_sequence_steps[1:]
                        )
                    }
                )
                / 3
            )
            + (
                len(
                    {
                        mode
                        for mode in ["command", "mixed", "non_command"]
                        if mode
                        not in {
                            (
                                "command"
                                if previous_step["command"] and next_step["command"]
                                else "mixed"
                                if bool(previous_step["command"]) != bool(next_step["command"])
                                else "non_command"
                            )
                            for previous_step, next_step in zip(
                                recommended_sequence_steps, recommended_sequence_steps[1:]
                            )
                        }
                    }
                )
                / 3
            ),
            4,
        ),
        "has_complete_transition_mode_coverage_partition": round(
            (
                len(
                    {
                        (
                            "command"
                            if previous_step["command"] and next_step["command"]
                            else "mixed"
                            if bool(previous_step["command"]) != bool(next_step["command"])
                            else "non_command"
                        )
                        for previous_step, next_step in zip(
                            recommended_sequence_steps, recommended_sequence_steps[1:]
                        )
                    }
                )
                / 3
            )
            + (
                len(
                    {
                        mode
                        for mode in ["command", "mixed", "non_command"]
                        if mode
                        not in {
                            (
                                "command"
                                if previous_step["command"] and next_step["command"]
                                else "mixed"
                                if bool(previous_step["command"]) != bool(next_step["command"])
                                else "non_command"
                            )
                            for previous_step, next_step in zip(
                                recommended_sequence_steps, recommended_sequence_steps[1:]
                            )
                        }
                    }
                )
                / 3
            ),
            4,
        )
        == 1.0,
        "transition_mode_coverage_total_label": (
            "unit"
            if round(
                (
                    len(
                        {
                            (
                                "command"
                                if previous_step["command"] and next_step["command"]
                                else "mixed"
                                if bool(previous_step["command"]) != bool(next_step["command"])
                                else "non_command"
                            )
                            for previous_step, next_step in zip(
                                recommended_sequence_steps, recommended_sequence_steps[1:]
                            )
                        }
                    )
                    / 3
                )
                + (
                    len(
                        {
                            mode
                            for mode in ["command", "mixed", "non_command"]
                            if mode
                            not in {
                                (
                                    "command"
                                    if previous_step["command"] and next_step["command"]
                                    else "mixed"
                                    if bool(previous_step["command"]) != bool(next_step["command"])
                                    else "non_command"
                                )
                                for previous_step, next_step in zip(
                                    recommended_sequence_steps, recommended_sequence_steps[1:]
                                )
                            }
                        }
                    )
                    / 3
                ),
                4,
            )
            == 1.0
            else "drifted"
        ),
        "is_unit_transition_mode_coverage_total": (
            round(
                (
                    len(
                        {
                            (
                                "command"
                                if previous_step["command"] and next_step["command"]
                                else "mixed"
                                if bool(previous_step["command"]) != bool(next_step["command"])
                                else "non_command"
                            )
                            for previous_step, next_step in zip(
                                recommended_sequence_steps, recommended_sequence_steps[1:]
                            )
                        }
                    )
                    / 3
                )
                + (
                    len(
                        {
                            mode
                            for mode in ["command", "mixed", "non_command"]
                            if mode
                            not in {
                                (
                                    "command"
                                    if previous_step["command"] and next_step["command"]
                                    else "mixed"
                                    if bool(previous_step["command"]) != bool(next_step["command"])
                                    else "non_command"
                                )
                                for previous_step, next_step in zip(
                                    recommended_sequence_steps, recommended_sequence_steps[1:]
                                )
                            }
                        }
                    )
                    / 3
                ),
                4,
            )
            == 1.0
        ),
        "transition_mode_coverage_partition_label": (
            "complete"
            if round(
                (
                    len(
                        {
                            (
                                "command"
                                if previous_step["command"] and next_step["command"]
                                else "mixed"
                                if bool(previous_step["command"]) != bool(next_step["command"])
                                else "non_command"
                            )
                            for previous_step, next_step in zip(
                                recommended_sequence_steps, recommended_sequence_steps[1:]
                            )
                        }
                    )
                    / 3
                )
                + (
                    len(
                        {
                            mode
                            for mode in ["command", "mixed", "non_command"]
                            if mode
                            not in {
                                (
                                    "command"
                                    if previous_step["command"] and next_step["command"]
                                    else "mixed"
                                    if bool(previous_step["command"]) != bool(next_step["command"])
                                    else "non_command"
                                )
                                for previous_step, next_step in zip(
                                    recommended_sequence_steps, recommended_sequence_steps[1:]
                                )
                            }
                        }
                    )
                    / 3
                ),
                4,
            )
            == 1.0
            else "broken"
        ),
        "is_broken_transition_mode_coverage_partition": not (
            round(
                (
                    len(
                        {
                            (
                                "command"
                                if previous_step["command"] and next_step["command"]
                                else "mixed"
                                if bool(previous_step["command"]) != bool(next_step["command"])
                                else "non_command"
                            )
                            for previous_step, next_step in zip(
                                recommended_sequence_steps, recommended_sequence_steps[1:]
                            )
                        }
                    )
                    / 3
                )
                + (
                    len(
                        {
                            mode
                            for mode in ["command", "mixed", "non_command"]
                            if mode
                            not in {
                                (
                                    "command"
                                    if previous_step["command"] and next_step["command"]
                                    else "mixed"
                                    if bool(previous_step["command"]) != bool(next_step["command"])
                                    else "non_command"
                                )
                                for previous_step, next_step in zip(
                                    recommended_sequence_steps, recommended_sequence_steps[1:]
                                )
                            }
                        }
                    )
                    / 3
                ),
                4,
            )
            == 1.0
        ),
        "present_transition_mode_count": len(
            {
                (
                    "command"
                    if previous_step["command"] and next_step["command"]
                    else "mixed"
                    if bool(previous_step["command"]) != bool(next_step["command"])
                    else "non_command"
                )
                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
            }
        ),
        "is_uniform_transition_mode": len(
            {
                (
                    "command"
                    if previous_step["command"] and next_step["command"]
                    else "mixed"
                    if bool(previous_step["command"]) != bool(next_step["command"])
                    else "non_command"
                )
                for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
            }
        ) <= 1,
        "mixed_phase_signatures": [
            f"{previous_step['phase']}->{next_step['phase']}"
            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
            if bool(previous_step["command"]) != bool(next_step["command"])
        ],
        "non_command_phase_signatures": [
            f"{previous_step['phase']}->{next_step['phase']}"
            for previous_step, next_step in zip(recommended_sequence_steps, recommended_sequence_steps[1:])
            if not previous_step["command"] and not next_step["command"]
        ],
        "phase_signatures": [
            f"{transition['from_phase']}->{transition['to_phase']}"
            for transition in recommended_sequence_transitions
        ],
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
        "recommended_drilldown": recommended_drilldown,
        "recommended_next_step": recommended_next_step,
        "recommended_sequence": recommended_sequence,
        "recommended_sequence_targets": recommended_sequence_targets,
        "recommended_sequence_labels": recommended_sequence_labels,
        "recommended_sequence_preview": recommended_sequence_preview,
        "recommended_sequence_commands": recommended_sequence_commands,
        "recommended_sequence_shells": recommended_sequence_shells,
        "recommended_sequence_steps": recommended_sequence_steps,
        "recommended_sequence_by_phase": recommended_sequence_by_phase,
        "recommended_sequence_summary": recommended_sequence_summary,
        "recommended_sequence_endpoints": recommended_sequence_endpoints,
        "recommended_sequence_transitions": recommended_sequence_transitions,
        "recommended_sequence_transition_summary": recommended_sequence_transition_summary,
        "recommended_family": recommended_family,
        "recommended_family_gap": recommended_family_gap,
        "recommended_family_comparison": recommended_family_comparison,
        "recommended_family_competition_window": recommended_family_competition_window,
        "recommended_family_competition_summary": recommended_family_competition_summary,
        "recommended_followups": recommended_followups,
        "family_competition": family_competition,
        "family_commands": family_commands,
        "family_hotspots": family_hotspots,
        "recommended_hotspot": recommended_hotspot,
        "series_commands": series_commands,
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
        git_head_path = path.replace("\\", "/")
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
                "git_show_head_command": ["git", "show", f"HEAD:{git_head_path}"],
                "git_show_head_command_shell": "git show " + _shell_quote_arg(f"HEAD:{git_head_path}"),
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
    build_spark_kb_from_shadow = subparsers.add_parser(
        "build-spark-kb-from-shadow-replay",
        help="Replay Spark shadow traffic, export governed memory, and compile a Spark KB vault from that run.",
    )
    build_spark_kb_from_shadow.add_argument("data_file")
    build_spark_kb_from_shadow.add_argument("output_dir")
    build_spark_kb_from_shadow.add_argument("--repo-source", action="append", default=[])
    build_spark_kb_from_shadow.add_argument("--repo-source-manifest", action="append", default=[])
    build_spark_kb_from_shadow.add_argument("--write")
    build_spark_kb_from_shadow_batch = subparsers.add_parser(
        "build-spark-kb-from-shadow-replay-batch",
        help="Replay a directory of Spark shadow traffic, export governed memory, and compile one Spark KB vault from the batch.",
    )
    build_spark_kb_from_shadow_batch.add_argument("data_dir")
    build_spark_kb_from_shadow_batch.add_argument("output_dir")
    build_spark_kb_from_shadow_batch.add_argument("--glob", default="*.json")
    build_spark_kb_from_shadow_batch.add_argument("--repo-source", action="append", default=[])
    build_spark_kb_from_shadow_batch.add_argument("--repo-source-manifest", action="append", default=[])
    build_spark_kb_from_shadow_batch.add_argument("--write")
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
    normalize_builder_shadow = subparsers.add_parser(
        "normalize-spark-builder-export",
        help="Normalize a Spark Builder conversation export into the shadow replay schema.",
    )
    normalize_builder_shadow.add_argument("data_file")
    normalize_builder_shadow.add_argument("--write")
    normalize_builder_shadow_batch = subparsers.add_parser(
        "normalize-spark-builder-export-batch",
        help="Normalize a directory of Spark Builder conversation exports into the shadow replay schema.",
    )
    normalize_builder_shadow_batch.add_argument("data_dir")
    normalize_builder_shadow_batch.add_argument("--glob", default="*.json")
    normalize_builder_shadow_batch.add_argument("--write")
    normalize_telegram_shadow = subparsers.add_parser(
        "normalize-spark-telegram-export",
        help="Normalize a Telegram bot export into the Spark shadow replay schema.",
    )
    normalize_telegram_shadow.add_argument("data_file")
    normalize_telegram_shadow.add_argument("--write")
    normalize_telegram_shadow_batch = subparsers.add_parser(
        "normalize-spark-telegram-export-batch",
        help="Normalize a directory of Telegram bot exports into the Spark shadow replay schema.",
    )
    normalize_telegram_shadow_batch.add_argument("data_dir")
    normalize_telegram_shadow_batch.add_argument("--glob", default="*.json")
    normalize_telegram_shadow_batch.add_argument("--write")
    run_builder_shadow = subparsers.add_parser(
        "run-spark-shadow-report-from-builder-export",
        help="Normalize a Spark Builder export and emit a shadow report without compiling a KB vault.",
    )
    run_builder_shadow.add_argument("data_file")
    run_builder_shadow.add_argument("--write")
    run_builder_shadow_batch = subparsers.add_parser(
        "run-spark-shadow-report-from-builder-export-batch",
        help="Normalize a directory of Spark Builder exports and emit one aggregate shadow report without compiling a KB vault.",
    )
    run_builder_shadow_batch.add_argument("data_dir")
    run_builder_shadow_batch.add_argument("--glob", default="*.json")
    run_builder_shadow_batch.add_argument("--write")
    run_telegram_shadow = subparsers.add_parser(
        "run-spark-shadow-report-from-telegram-export",
        help="Normalize a Telegram bot export and emit a shadow report without compiling a KB vault.",
    )
    run_telegram_shadow.add_argument("data_file")
    run_telegram_shadow.add_argument("--write")
    run_telegram_shadow_batch = subparsers.add_parser(
        "run-spark-shadow-report-from-telegram-export-batch",
        help="Normalize a directory of Telegram bot exports and emit one aggregate shadow report without compiling a KB vault.",
    )
    run_telegram_shadow_batch.add_argument("data_dir")
    run_telegram_shadow_batch.add_argument("--glob", default="*.json")
    run_telegram_shadow_batch.add_argument("--write")
    taxonomy_builder_shadow = subparsers.add_parser(
        "build-spark-shadow-failure-taxonomy-from-builder-export",
        help="Normalize a Spark Builder export, replay it, and emit a compact failure taxonomy without compiling a KB vault.",
    )
    taxonomy_builder_shadow.add_argument("data_file")
    taxonomy_builder_shadow.add_argument("--write")
    taxonomy_builder_shadow_batch = subparsers.add_parser(
        "build-spark-shadow-failure-taxonomy-from-builder-export-batch",
        help="Normalize a directory of Spark Builder exports, replay them, and emit one aggregate failure taxonomy without compiling a KB vault.",
    )
    taxonomy_builder_shadow_batch.add_argument("data_dir")
    taxonomy_builder_shadow_batch.add_argument("--glob", default="*.json")
    taxonomy_builder_shadow_batch.add_argument("--write")
    taxonomy_telegram_shadow = subparsers.add_parser(
        "build-spark-shadow-failure-taxonomy-from-telegram-export",
        help="Normalize a Telegram bot export, replay it, and emit a compact failure taxonomy without compiling a KB vault.",
    )
    taxonomy_telegram_shadow.add_argument("data_file")
    taxonomy_telegram_shadow.add_argument("--write")
    taxonomy_telegram_shadow_batch = subparsers.add_parser(
        "build-spark-shadow-failure-taxonomy-from-telegram-export-batch",
        help="Normalize a directory of Telegram bot exports, replay them, and emit one aggregate failure taxonomy without compiling a KB vault.",
    )
    taxonomy_telegram_shadow_batch.add_argument("data_dir")
    taxonomy_telegram_shadow_batch.add_argument("--glob", default="*.json")
    taxonomy_telegram_shadow_batch.add_argument("--write")
    build_spark_kb_from_builder = subparsers.add_parser(
        "build-spark-kb-from-builder-export",
        help="Normalize a Spark Builder export, replay it through governed memory, and compile a Spark KB vault.",
    )
    build_spark_kb_from_builder.add_argument("data_file")
    build_spark_kb_from_builder.add_argument("output_dir")
    build_spark_kb_from_builder.add_argument("--repo-source", action="append", default=[])
    build_spark_kb_from_builder.add_argument("--repo-source-manifest", action="append", default=[])
    build_spark_kb_from_builder.add_argument("--write")
    build_spark_kb_from_builder_batch = subparsers.add_parser(
        "build-spark-kb-from-builder-export-batch",
        help="Normalize a directory of Spark Builder exports, replay them through one governed memory runtime, and compile one Spark KB vault.",
    )
    build_spark_kb_from_builder_batch.add_argument("data_dir")
    build_spark_kb_from_builder_batch.add_argument("output_dir")
    build_spark_kb_from_builder_batch.add_argument("--glob", default="*.json")
    build_spark_kb_from_builder_batch.add_argument("--repo-source", action="append", default=[])
    build_spark_kb_from_builder_batch.add_argument("--repo-source-manifest", action="append", default=[])
    build_spark_kb_from_builder_batch.add_argument("--write")
    build_spark_kb_from_telegram = subparsers.add_parser(
        "build-spark-kb-from-telegram-export",
        help="Normalize a Telegram bot export, replay it through governed memory, and compile a Spark KB vault.",
    )
    build_spark_kb_from_telegram.add_argument("data_file")
    build_spark_kb_from_telegram.add_argument("output_dir")
    build_spark_kb_from_telegram.add_argument("--repo-source", action="append", default=[])
    build_spark_kb_from_telegram.add_argument("--repo-source-manifest", action="append", default=[])
    build_spark_kb_from_telegram.add_argument("--write")
    build_spark_kb_from_telegram_batch = subparsers.add_parser(
        "build-spark-kb-from-telegram-export-batch",
        help="Normalize a directory of Telegram bot exports, replay them through one governed memory runtime, and compile one Spark KB vault.",
    )
    build_spark_kb_from_telegram_batch.add_argument("data_dir")
    build_spark_kb_from_telegram_batch.add_argument("output_dir")
    build_spark_kb_from_telegram_batch.add_argument("--glob", default="*.json")
    build_spark_kb_from_telegram_batch.add_argument("--repo-source", action="append", default=[])
    build_spark_kb_from_telegram_batch.add_argument("--repo-source-manifest", action="append", default=[])
    build_spark_kb_from_telegram_batch.add_argument("--write")
    run_spark_builder_intake_batch = subparsers.add_parser(
        "run-spark-builder-intake-batch",
        help="Normalize a directory of Spark Builder exports, build the aggregate shadow report, build the failure taxonomy, and compile one Spark KB vault in one run.",
    )
    run_spark_builder_intake_batch.add_argument("data_dir")
    run_spark_builder_intake_batch.add_argument("output_dir")
    run_spark_builder_intake_batch.add_argument("--glob", default="*.json")
    run_spark_builder_intake_batch.add_argument("--repo-source", action="append", default=[])
    run_spark_builder_intake_batch.add_argument("--repo-source-manifest", action="append", default=[])
    run_spark_builder_intake_batch.add_argument("--write")
    run_spark_telegram_intake_batch = subparsers.add_parser(
        "run-spark-telegram-intake-batch",
        help="Normalize a directory of Telegram bot exports, build the aggregate shadow report, build the failure taxonomy, and compile one Spark KB vault in one run.",
    )
    run_spark_telegram_intake_batch.add_argument("data_dir")
    run_spark_telegram_intake_batch.add_argument("output_dir")
    run_spark_telegram_intake_batch.add_argument("--glob", default="*.json")
    run_spark_telegram_intake_batch.add_argument("--repo-source", action="append", default=[])
    run_spark_telegram_intake_batch.add_argument("--repo-source-manifest", action="append", default=[])
    run_spark_telegram_intake_batch.add_argument("--write")
    run_spark_builder_telegram_intake = subparsers.add_parser(
        "run-spark-builder-telegram-intake",
        help="Scan a Spark Intelligence Builder directory for Telegram runtime artifacts, then build the aggregate shadow report, failure taxonomy, and Spark KB vault in one run.",
    )
    run_spark_builder_telegram_intake.add_argument("builder_dir")
    run_spark_builder_telegram_intake.add_argument("output_dir")
    run_spark_builder_telegram_intake.add_argument("--glob", default=".tmp-telegram-*.json")
    run_spark_builder_telegram_intake.add_argument("--repo-source", action="append", default=[])
    run_spark_builder_telegram_intake.add_argument("--repo-source-manifest", action="append", default=[])
    run_spark_builder_telegram_intake.add_argument("--write")
    run_spark_builder_state_telegram_intake = subparsers.add_parser(
        "run-spark-builder-state-telegram-intake",
        help="Read Spark Intelligence Builder telegram_runtime events from state.db, replay them through governed memory, and compile one Spark KB vault in one run.",
    )
    run_spark_builder_state_telegram_intake.add_argument("builder_home")
    run_spark_builder_state_telegram_intake.add_argument("output_dir")
    run_spark_builder_state_telegram_intake.add_argument("--limit", type=int, default=25)
    run_spark_builder_state_telegram_intake.add_argument("--chat-id")
    run_spark_builder_state_telegram_intake.add_argument("--repo-source", action="append", default=[])
    run_spark_builder_state_telegram_intake.add_argument("--repo-source-manifest", action="append", default=[])
    run_spark_builder_state_telegram_intake.add_argument("--write")
    run_spark_memory_kb_ablation = subparsers.add_parser(
        "run-spark-memory-kb-ablation",
        help="Compare memory-only versus memory-plus-KB support over query turns extracted from a Spark intake artifact.",
    )
    run_spark_memory_kb_ablation.add_argument("data_file")
    run_spark_memory_kb_ablation.add_argument("--limit", type=int)
    run_spark_memory_kb_ablation.add_argument("--promotion-policy-file")
    run_spark_memory_kb_ablation.add_argument("--recompile-kb-output-dir")
    run_spark_memory_kb_ablation.add_argument("--write")
    build_spark_memory_kb_sourcing_slice = subparsers.add_parser(
        "build-spark-memory-kb-sourcing-slice",
        help="Build a compact replay slice containing missing-fact conversations plus answered source-backed exemplars for the same predicates.",
    )
    build_spark_memory_kb_sourcing_slice.add_argument("ablation_file")
    build_spark_memory_kb_sourcing_slice.add_argument("--data-file")
    build_spark_memory_kb_sourcing_slice.add_argument("--exemplars-per-predicate", type=int, default=1)
    build_spark_memory_kb_sourcing_slice.add_argument("--write")
    build_spark_memory_kb_source_backed_slice = subparsers.add_parser(
        "build-spark-memory-kb-source-backed-slice",
        help="Inject source-backed write turns into missing-fact conversations, replay the result, and compile a fresh Spark KB slice.",
    )
    build_spark_memory_kb_source_backed_slice.add_argument("sourcing_slice_file")
    build_spark_memory_kb_source_backed_slice.add_argument("output_dir")
    build_spark_memory_kb_source_backed_slice.add_argument("--write")
    compare_spark_memory_kb_ablation = subparsers.add_parser(
        "compare-spark-memory-kb-ablation",
        help="Compare two Spark memory-vs-KB ablation artifacts and summarize query transitions.",
    )
    compare_spark_memory_kb_ablation.add_argument("before_file")
    compare_spark_memory_kb_ablation.add_argument("after_file")
    compare_spark_memory_kb_ablation.add_argument("--write")
    build_spark_memory_kb_policy_verdict = subparsers.add_parser(
        "build-spark-memory-kb-policy-verdict",
        help="Turn a Spark source-backed transition ledger into action-bucket policy recommendations.",
    )
    build_spark_memory_kb_policy_verdict.add_argument("compare_file")
    build_spark_memory_kb_policy_verdict.add_argument("--write")
    build_spark_memory_kb_promotion_plan = subparsers.add_parser(
        "build-spark-memory-kb-promotion-plan",
        help="Join the Spark policy verdict with source-backed lineage to produce promotable, optional, and excluded targets.",
    )
    build_spark_memory_kb_promotion_plan.add_argument("policy_verdict_file")
    build_spark_memory_kb_promotion_plan.add_argument("source_backed_slice_file")
    build_spark_memory_kb_promotion_plan.add_argument("--write")
    build_spark_memory_kb_promotion_policy = subparsers.add_parser(
        "build-spark-memory-kb-promotion-policy",
        help="Turn the Spark promotion plan into explicit allow, defer, and block policy rows for upstream consumption.",
    )
    build_spark_memory_kb_promotion_policy.add_argument("promotion_plan_file")
    build_spark_memory_kb_promotion_policy.add_argument("--include-optional", action="store_true")
    build_spark_memory_kb_promotion_policy.add_argument("--write")
    build_spark_memory_kb_approved_promotion_slice = subparsers.add_parser(
        "build-spark-memory-kb-approved-promotion-slice",
        help="Filter the source-backed Spark slice down to approved promotion targets and recompile a fresh KB.",
    )
    build_spark_memory_kb_approved_promotion_slice.add_argument("promotion_plan_file")
    build_spark_memory_kb_approved_promotion_slice.add_argument("source_backed_slice_file")
    build_spark_memory_kb_approved_promotion_slice.add_argument("output_dir")
    build_spark_memory_kb_approved_promotion_slice.add_argument("--include-optional", action="store_true")
    build_spark_memory_kb_approved_promotion_slice.add_argument("--write")
    build_spark_memory_kb_policy_aligned_slice = subparsers.add_parser(
        "build-spark-memory-kb-policy-aligned-slice",
        help="Replay a source-backed Spark slice under promotion policy, then compile a policy-aligned KB artifact.",
    )
    build_spark_memory_kb_policy_aligned_slice.add_argument("source_backed_slice_file")
    build_spark_memory_kb_policy_aligned_slice.add_argument("promotion_policy_file")
    build_spark_memory_kb_policy_aligned_slice.add_argument("output_dir")
    build_spark_memory_kb_policy_aligned_slice.add_argument("--write")
    build_spark_memory_kb_refresh_manifest = subparsers.add_parser(
        "build-spark-memory-kb-refresh-manifest",
        help="Build a compact upstream refresh manifest from a policy-aligned Spark KB slice payload.",
    )
    build_spark_memory_kb_refresh_manifest.add_argument("policy_aligned_slice_file")
    build_spark_memory_kb_refresh_manifest.add_argument("--write")
    materialize_spark_memory_kb_refresh_manifest = subparsers.add_parser(
        "materialize-spark-memory-kb-refresh-manifest",
        help="Copy the governed Spark KB referenced by a refresh manifest into a caller-chosen output directory.",
    )
    materialize_spark_memory_kb_refresh_manifest.add_argument("refresh_manifest_file")
    materialize_spark_memory_kb_refresh_manifest.add_argument("output_dir")
    materialize_spark_memory_kb_refresh_manifest.add_argument("--write")
    publish_spark_memory_kb_refresh_manifest = subparsers.add_parser(
        "publish-spark-memory-kb-refresh-manifest",
        help="Publish a governed Spark KB refresh into a stable release directory plus active-refresh file.",
    )
    publish_spark_memory_kb_refresh_manifest.add_argument("refresh_manifest_file")
    publish_spark_memory_kb_refresh_manifest.add_argument("publish_root_dir")
    publish_spark_memory_kb_refresh_manifest.add_argument("--write")
    resolve_spark_memory_kb_active_refresh = subparsers.add_parser(
        "resolve-spark-memory-kb-active-refresh",
        help="Resolve and validate the active governed Spark KB referenced by an active-refresh file.",
    )
    resolve_spark_memory_kb_active_refresh.add_argument("active_refresh_file")
    resolve_spark_memory_kb_active_refresh.add_argument("--write")
    read_spark_memory_kb_active_refresh_support = subparsers.add_parser(
        "read-spark-memory-kb-active-refresh-support",
        help="Read current-state KB support for one subject/predicate pair from an active governed Spark KB refresh.",
    )
    read_spark_memory_kb_active_refresh_support.add_argument("active_refresh_file")
    read_spark_memory_kb_active_refresh_support.add_argument("subject")
    read_spark_memory_kb_active_refresh_support.add_argument("predicate")
    read_spark_memory_kb_active_refresh_support.add_argument("--write")
    read_spark_memory_kb_active_refresh_conversation_support = subparsers.add_parser(
        "read-spark-memory-kb-active-refresh-conversation-support",
        help="Read governed KB support for one conversation_id/predicate pair using the policy-aligned slice to resolve human_id.",
    )
    read_spark_memory_kb_active_refresh_conversation_support.add_argument("active_refresh_file")
    read_spark_memory_kb_active_refresh_conversation_support.add_argument("policy_aligned_slice_file")
    read_spark_memory_kb_active_refresh_conversation_support.add_argument("conversation_id")
    read_spark_memory_kb_active_refresh_conversation_support.add_argument("predicate")
    read_spark_memory_kb_active_refresh_conversation_support.add_argument("--write")
    run_spark_memory_kb_active_refresh_read_report = subparsers.add_parser(
        "run-spark-memory-kb-active-refresh-read-report",
        help="Run all query turns from a policy-aligned Spark slice through the published active governed KB.",
    )
    run_spark_memory_kb_active_refresh_read_report.add_argument("active_refresh_file")
    run_spark_memory_kb_active_refresh_read_report.add_argument("policy_aligned_slice_file")
    run_spark_memory_kb_active_refresh_read_report.add_argument("--limit", type=int)
    run_spark_memory_kb_active_refresh_read_report.add_argument("--write")
    read_spark_memory_kb_governed_release_support = subparsers.add_parser(
        "read-spark-memory-kb-governed-release-support",
        help="Read current-state KB support for one subject/predicate pair from a top-level governed Spark KB release manifest.",
    )
    read_spark_memory_kb_governed_release_support.add_argument("governed_release_file")
    read_spark_memory_kb_governed_release_support.add_argument("subject")
    read_spark_memory_kb_governed_release_support.add_argument("predicate")
    read_spark_memory_kb_governed_release_support.add_argument("--write")
    read_spark_memory_kb_governed_release_conversation_support = subparsers.add_parser(
        "read-spark-memory-kb-governed-release-conversation-support",
        help="Read governed KB support for one conversation_id/predicate pair from a top-level governed Spark KB release manifest.",
    )
    read_spark_memory_kb_governed_release_conversation_support.add_argument("governed_release_file")
    read_spark_memory_kb_governed_release_conversation_support.add_argument("conversation_id")
    read_spark_memory_kb_governed_release_conversation_support.add_argument("predicate")
    read_spark_memory_kb_governed_release_conversation_support.add_argument("--write")
    run_spark_memory_kb_governed_release_read_report = subparsers.add_parser(
        "run-spark-memory-kb-governed-release-read-report",
        help="Run all query turns from the governed release manifest through the published governed KB surface.",
    )
    run_spark_memory_kb_governed_release_read_report.add_argument("governed_release_file")
    run_spark_memory_kb_governed_release_read_report.add_argument("--limit", type=int)
    run_spark_memory_kb_governed_release_read_report.add_argument("--write")
    build_spark_memory_kb_governed_release_summary = subparsers.add_parser(
        "build-spark-memory-kb-governed-release-summary",
        help="Build one compact summary from a top-level governed Spark KB release manifest and its published read surface.",
    )
    build_spark_memory_kb_governed_release_summary.add_argument("governed_release_file")
    build_spark_memory_kb_governed_release_summary.add_argument("--limit", type=int)
    build_spark_memory_kb_governed_release_summary.add_argument("--write")
    check_spark_memory_kb_governed_release_summary = subparsers.add_parser(
        "check-spark-memory-kb-governed-release-summary",
        help="Convert a governed Spark KB release summary into a machine-friendly top-level pass/fail gate verdict.",
    )
    check_spark_memory_kb_governed_release_summary.add_argument("governed_release_summary_file")
    check_spark_memory_kb_governed_release_summary.add_argument("--write")
    assert_spark_memory_kb_governed_release_summary_ready = subparsers.add_parser(
        "assert-spark-memory-kb-governed-release-summary-ready",
        help="Exit non-zero when a governed Spark KB release summary does not pass the top-level gate.",
    )
    assert_spark_memory_kb_governed_release_summary_ready.add_argument("governed_release_summary_file")
    assert_spark_memory_kb_governed_release_summary_ready.add_argument("--write")
    build_spark_memory_kb_active_release_summary = subparsers.add_parser(
        "build-spark-memory-kb-active-release-summary",
        help="Build one release-readiness summary from the published active governed KB, policy verification, and active read report.",
    )
    build_spark_memory_kb_active_release_summary.add_argument("active_refresh_file")
    build_spark_memory_kb_active_release_summary.add_argument("policy_aligned_slice_file")
    build_spark_memory_kb_active_release_summary.add_argument("--limit", type=int)
    build_spark_memory_kb_active_release_summary.add_argument("--write")
    check_spark_memory_kb_active_release_summary = subparsers.add_parser(
        "check-spark-memory-kb-active-release-summary",
        help="Convert an active governed release summary into a machine-friendly pass/fail gate verdict.",
    )
    check_spark_memory_kb_active_release_summary.add_argument("active_release_summary_file")
    check_spark_memory_kb_active_release_summary.add_argument("--write")
    assert_spark_memory_kb_active_release_ready = subparsers.add_parser(
        "assert-spark-memory-kb-active-release-ready",
        help="Exit non-zero when the active governed Spark KB release gate is not ready.",
    )
    assert_spark_memory_kb_active_release_ready.add_argument("active_release_summary_file")
    assert_spark_memory_kb_active_release_ready.add_argument("--write")
    resolve_spark_memory_kb_governed_release = subparsers.add_parser(
        "resolve-spark-memory-kb-governed-release",
        help="Resolve a governed Spark KB release manifest into validated active paths and gate state.",
    )
    resolve_spark_memory_kb_governed_release.add_argument("governed_release_file")
    resolve_spark_memory_kb_governed_release.add_argument("--write")
    assert_spark_memory_kb_governed_release_ready = subparsers.add_parser(
        "assert-spark-memory-kb-governed-release-ready",
        help="Exit non-zero when a governed Spark KB release manifest does not resolve to a ready release.",
    )
    assert_spark_memory_kb_governed_release_ready.add_argument("governed_release_file")
    assert_spark_memory_kb_governed_release_ready.add_argument("--write")
    ship_spark_memory_kb_governed_release = subparsers.add_parser(
        "ship-spark-memory-kb-governed-release",
        help="Publish, summarize, and assert one governed Spark KB release from a refresh manifest in one step.",
    )
    ship_spark_memory_kb_governed_release.add_argument("refresh_manifest_file")
    ship_spark_memory_kb_governed_release.add_argument("policy_aligned_slice_file")
    ship_spark_memory_kb_governed_release.add_argument("publish_root_dir")
    ship_spark_memory_kb_governed_release.add_argument("--write")
    verify_spark_memory_kb_active_refresh_policy = subparsers.add_parser(
        "verify-spark-memory-kb-active-refresh-policy",
        help="Verify that a published active governed Spark KB still honors the policy rows from a policy-aligned slice payload.",
    )
    verify_spark_memory_kb_active_refresh_policy.add_argument("active_refresh_file")
    verify_spark_memory_kb_active_refresh_policy.add_argument("policy_aligned_slice_file")
    verify_spark_memory_kb_active_refresh_policy.add_argument("--write")
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

    run_locomo_multi_shadow = subparsers.add_parser(
        "run-locomo-multi-shadow-eval",
        help="Run summary vs exact-turn vs typed-graph shadow answer evaluation over a LoCoMo slice.",
    )
    run_locomo_multi_shadow.add_argument("data_file")
    run_locomo_multi_shadow.add_argument("--provider", default="heuristic_v1")
    run_locomo_multi_shadow.add_argument("--limit", type=int)
    run_locomo_multi_shadow.add_argument("--question-offset", type=int, default=0)
    run_locomo_multi_shadow.add_argument("--question-limit", type=int)
    run_locomo_multi_shadow.add_argument("--sample-id", action="append")
    run_locomo_multi_shadow.add_argument("--category", action="append")
    run_locomo_multi_shadow.add_argument("--question-id", action="append")
    run_locomo_multi_shadow.add_argument("--exclude-missing-gold", action="store_true")
    run_locomo_multi_shadow.add_argument("--conversational-limit", type=int, default=8)
    run_locomo_multi_shadow.add_argument("--graph-limit", type=int, default=6)
    run_locomo_multi_shadow.add_argument("--write")

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

    if args.command == "build-spark-kb-from-shadow-replay":
        payload = _build_spark_kb_from_shadow_replay(
            args.data_file,
            args.output_dir,
            repo_sources=args.repo_source,
            repo_source_manifest_files=args.repo_source_manifest,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "build-spark-kb-from-shadow-replay-batch":
        payload = _build_spark_kb_from_shadow_replay_batch(
            args.data_dir,
            args.output_dir,
            glob_pattern=args.glob,
            repo_sources=args.repo_source,
            repo_source_manifest_files=args.repo_source_manifest,
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

    if args.command == "normalize-spark-builder-export":
        payload = _normalize_builder_shadow_export(args.data_file)
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "normalize-spark-builder-export-batch":
        payload = _normalize_builder_shadow_export_batch(args.data_dir, glob_pattern=args.glob)
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "normalize-spark-telegram-export":
        payload = _normalize_telegram_shadow_export(args.data_file)
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "normalize-spark-telegram-export-batch":
        payload = _normalize_telegram_shadow_export_batch(args.data_dir, glob_pattern=args.glob)
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "run-spark-shadow-report-from-builder-export":
        payload = _load_shadow_report_payload_from_builder_export(args.data_file)
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "run-spark-shadow-report-from-builder-export-batch":
        payload = _load_shadow_report_payload_from_builder_export_batch(args.data_dir, glob_pattern=args.glob)
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "run-spark-shadow-report-from-telegram-export":
        payload = _load_shadow_report_payload_from_telegram_export(args.data_file)
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "run-spark-shadow-report-from-telegram-export-batch":
        payload = _load_shadow_report_payload_from_telegram_export_batch(args.data_dir, glob_pattern=args.glob)
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "build-spark-shadow-failure-taxonomy-from-builder-export":
        payload = _build_shadow_failure_taxonomy_from_builder_export(args.data_file)
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "build-spark-shadow-failure-taxonomy-from-builder-export-batch":
        payload = _build_shadow_failure_taxonomy_from_builder_export_batch(args.data_dir, glob_pattern=args.glob)
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "build-spark-shadow-failure-taxonomy-from-telegram-export":
        payload = _build_shadow_failure_taxonomy_from_telegram_export(args.data_file)
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "build-spark-shadow-failure-taxonomy-from-telegram-export-batch":
        payload = _build_shadow_failure_taxonomy_from_telegram_export_batch(args.data_dir, glob_pattern=args.glob)
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "build-spark-kb-from-builder-export":
        payload = _build_spark_kb_from_builder_export(
            args.data_file,
            args.output_dir,
            repo_sources=args.repo_source,
            repo_source_manifest_files=args.repo_source_manifest,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "build-spark-kb-from-telegram-export":
        payload = _build_spark_kb_from_telegram_export(
            args.data_file,
            args.output_dir,
            repo_sources=args.repo_source,
            repo_source_manifest_files=args.repo_source_manifest,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "build-spark-kb-from-builder-export-batch":
        payload = _build_spark_kb_from_builder_export_batch(
            args.data_dir,
            args.output_dir,
            glob_pattern=args.glob,
            repo_sources=args.repo_source,
            repo_source_manifest_files=args.repo_source_manifest,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "build-spark-kb-from-telegram-export-batch":
        payload = _build_spark_kb_from_telegram_export_batch(
            args.data_dir,
            args.output_dir,
            glob_pattern=args.glob,
            repo_sources=args.repo_source,
            repo_source_manifest_files=args.repo_source_manifest,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "run-spark-builder-intake-batch":
        payload = _run_spark_builder_intake_batch(
            args.data_dir,
            args.output_dir,
            glob_pattern=args.glob,
            repo_sources=args.repo_source,
            repo_source_manifest_files=args.repo_source_manifest,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "run-spark-telegram-intake-batch":
        payload = _run_spark_telegram_intake_batch(
            args.data_dir,
            args.output_dir,
            glob_pattern=args.glob,
            repo_sources=args.repo_source,
            repo_source_manifest_files=args.repo_source_manifest,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "run-spark-builder-telegram-intake":
        payload = _run_spark_builder_telegram_intake(
            args.builder_dir,
            args.output_dir,
            glob_pattern=args.glob,
            repo_sources=args.repo_source,
            repo_source_manifest_files=args.repo_source_manifest,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "run-spark-builder-state-telegram-intake":
        payload = _run_spark_builder_state_telegram_intake(
            args.builder_home,
            args.output_dir,
            limit=args.limit,
            chat_id=args.chat_id,
            repo_sources=args.repo_source,
            repo_source_manifest_files=args.repo_source_manifest,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "run-spark-memory-kb-ablation":
        payload = _run_spark_memory_kb_ablation(
            args.data_file,
            limit=args.limit,
            promotion_policy_file=args.promotion_policy_file,
            recompile_kb_output_dir=args.recompile_kb_output_dir,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "build-spark-memory-kb-sourcing-slice":
        payload = _build_spark_memory_kb_sourcing_slice(
            args.ablation_file,
            data_file=args.data_file,
            exemplars_per_predicate=args.exemplars_per_predicate,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "build-spark-memory-kb-source-backed-slice":
        payload = _build_spark_memory_kb_source_backed_slice(
            args.sourcing_slice_file,
            args.output_dir,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "compare-spark-memory-kb-ablation":
        payload = _compare_spark_memory_kb_ablation(
            args.before_file,
            args.after_file,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "build-spark-memory-kb-policy-verdict":
        payload = _build_spark_memory_kb_policy_verdict(
            args.compare_file,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "build-spark-memory-kb-promotion-plan":
        payload = _build_spark_memory_kb_promotion_plan(
            args.policy_verdict_file,
            args.source_backed_slice_file,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "build-spark-memory-kb-promotion-policy":
        payload = _build_spark_memory_kb_promotion_policy(
            args.promotion_plan_file,
            include_optional=args.include_optional,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "build-spark-memory-kb-approved-promotion-slice":
        payload = _build_spark_memory_kb_approved_promotion_slice(
            args.promotion_plan_file,
            args.source_backed_slice_file,
            args.output_dir,
            include_optional=args.include_optional,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "build-spark-memory-kb-policy-aligned-slice":
        payload = _build_spark_memory_kb_policy_aligned_slice(
            args.source_backed_slice_file,
            args.promotion_policy_file,
            args.output_dir,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "build-spark-memory-kb-refresh-manifest":
        payload = _build_spark_memory_kb_refresh_manifest(
            args.policy_aligned_slice_file,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "materialize-spark-memory-kb-refresh-manifest":
        payload = _materialize_spark_memory_kb_refresh_manifest(
            args.refresh_manifest_file,
            args.output_dir,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "publish-spark-memory-kb-refresh-manifest":
        payload = _publish_spark_memory_kb_refresh_manifest(
            args.refresh_manifest_file,
            args.publish_root_dir,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "resolve-spark-memory-kb-active-refresh":
        payload = _resolve_spark_memory_kb_active_refresh(
            args.active_refresh_file,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "read-spark-memory-kb-active-refresh-support":
        payload = _read_spark_memory_kb_active_refresh_support(
            args.active_refresh_file,
            subject=args.subject,
            predicate=args.predicate,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "read-spark-memory-kb-active-refresh-conversation-support":
        payload = _read_spark_memory_kb_active_refresh_conversation_support(
            args.active_refresh_file,
            args.policy_aligned_slice_file,
            conversation_id=args.conversation_id,
            predicate=args.predicate,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "run-spark-memory-kb-active-refresh-read-report":
        payload = _run_spark_memory_kb_active_refresh_read_report(
            args.active_refresh_file,
            args.policy_aligned_slice_file,
            limit=args.limit,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "read-spark-memory-kb-governed-release-support":
        payload = _read_spark_memory_kb_governed_release_support(
            args.governed_release_file,
            subject=args.subject,
            predicate=args.predicate,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "read-spark-memory-kb-governed-release-conversation-support":
        payload = _read_spark_memory_kb_governed_release_conversation_support(
            args.governed_release_file,
            conversation_id=args.conversation_id,
            predicate=args.predicate,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "run-spark-memory-kb-governed-release-read-report":
        payload = _run_spark_memory_kb_governed_release_read_report(
            args.governed_release_file,
            limit=args.limit,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "build-spark-memory-kb-governed-release-summary":
        payload = _build_spark_memory_kb_governed_release_summary(
            args.governed_release_file,
            limit=args.limit,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "check-spark-memory-kb-governed-release-summary":
        payload = _check_spark_memory_kb_governed_release_summary(
            args.governed_release_summary_file,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "assert-spark-memory-kb-governed-release-summary-ready":
        payload = _assert_spark_memory_kb_governed_release_summary_ready(
            args.governed_release_summary_file,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "build-spark-memory-kb-active-release-summary":
        payload = _build_spark_memory_kb_active_release_summary(
            args.active_refresh_file,
            args.policy_aligned_slice_file,
            limit=args.limit,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "check-spark-memory-kb-active-release-summary":
        payload = _check_spark_memory_kb_active_release_summary(
            args.active_release_summary_file,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "assert-spark-memory-kb-active-release-ready":
        payload = _assert_spark_memory_kb_active_release_ready(
            args.active_release_summary_file,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "resolve-spark-memory-kb-governed-release":
        payload = _resolve_spark_memory_kb_governed_release(
            args.governed_release_file,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "assert-spark-memory-kb-governed-release-ready":
        payload = _assert_spark_memory_kb_governed_release_ready(
            args.governed_release_file,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "ship-spark-memory-kb-governed-release":
        payload = _ship_spark_memory_kb_governed_release(
            args.refresh_manifest_file,
            args.policy_aligned_slice_file,
            args.publish_root_dir,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "verify-spark-memory-kb-active-refresh-policy":
        payload = _verify_spark_memory_kb_active_refresh_policy(
            args.active_refresh_file,
            args.policy_aligned_slice_file,
        )
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
                "builder_adapter": build_builder_shadow_adapter_contract_summary(),
                "telegram_adapter": build_telegram_shadow_adapter_contract_summary(),
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

    if args.command == "run-locomo-multi-shadow-eval":
        samples = _filter_locomo_shadow_samples(
            _limit_questions(
                load_locomo_json(args.data_file, limit=args.limit),
                question_offset=args.question_offset,
                question_limit=args.question_limit,
            ),
            sample_ids=args.sample_id,
            categories=args.category,
            question_ids=args.question_id,
            exclude_missing_gold=args.exclude_missing_gold,
        )
        payload = build_multi_shadow_answer_eval(
            samples,
            provider_name=args.provider,
            conversational_limit=args.conversational_limit,
            graph_limit=args.graph_limit,
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
        export_answers = _load_beam_official_eval_exports()["export_beam_public_answers_from_scorecard"]
        payload = export_answers(
            args.scorecard_file,
            args.output_dir,
            result_file_name=args.result_file_name,
        )
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "summarize-beam-evaluation":
        summarize_evaluation = _load_beam_official_eval_exports()["summarize_beam_official_evaluation"]
        payload = summarize_evaluation(args.evaluation_file)
        if args.write:
            _write_json(Path(args.write), payload)
        _print(payload)
        return

    if args.command == "run-beam-official-evaluation":
        run_evaluation = _load_beam_official_eval_exports()["run_beam_official_evaluation"]
        payload = run_evaluation(
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
