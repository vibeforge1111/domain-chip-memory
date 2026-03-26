from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

from .benchmark_issues import get_known_benchmark_issue
from .contracts import JsonDict, NormalizedBenchmarkSample, NormalizedQuestion
from .runs import BaselinePromptPacket, BenchmarkRunManifest


AUDIT_EXCLUDED_KNOWN_ISSUE_CLASSES = {"benchmark_inconsistency"}


@dataclass(frozen=True)
class BaselinePrediction:
    benchmark_name: str
    baseline_name: str
    sample_id: str
    question_id: str
    category: str
    predicted_answer: str
    expected_answers: list[str]
    is_correct: bool
    metadata: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return asdict(self)


def _normalize_answer(answer: str) -> str:
    return " ".join(answer.lower().strip().split())


def _question_lookup(samples: list[NormalizedBenchmarkSample]) -> dict[str, NormalizedQuestion]:
    return {question.question_id: question for sample in samples for question in sample.questions}


def _accuracy_row(*, correct: int, total: int, excluded: int = 0) -> dict[str, Any]:
    return {
        "correct": correct,
        "total": total,
        "excluded": excluded,
        "accuracy": round(correct / total, 4) if total else 0.0,
    }


def _build_slice_rows(
    total_by_label: Counter[str],
    correct_by_label: Counter[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label in sorted(total_by_label):
        rows.append(
            {
                "label": label,
                **_accuracy_row(correct=correct_by_label[label], total=total_by_label[label]),
            }
        )
    return rows


def _numeric_metric_summary(values: list[float | int]) -> dict[str, Any]:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return {"available": 0, "missing": 0}
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        median = ordered[midpoint]
    else:
        median = (ordered[midpoint - 1] + ordered[midpoint]) / 2
    return {
        "available": len(ordered),
        "missing": 0,
        "min": round(ordered[0], 4),
        "max": round(ordered[-1], 4),
        "mean": round(sum(ordered) / len(ordered), 4),
        "median": round(median, 4),
    }


def _rate_row(*, numerator: int, total: int, label: str) -> dict[str, Any]:
    return {
        label: numerator,
        "total": total,
        "rate": round(numerator / total, 4) if total else 0.0,
    }


def _build_product_memory_summary(predictions: list[BaselinePrediction]) -> dict[str, Any]:
    latency_values: list[float | int] = []
    token_values: list[float | int] = []
    answer_candidate_supported = 0
    provenance_supported = 0
    abstention_total = 0
    abstention_honest = 0
    current_state_total = 0
    current_state_correct = 0

    for prediction in predictions:
        latency = prediction.metadata.get("latency_ms")
        if isinstance(latency, (int, float)):
            latency_values.append(latency)
        total_tokens = prediction.metadata.get("total_tokens")
        if isinstance(total_tokens, (int, float)):
            token_values.append(total_tokens)
        if int(prediction.metadata.get("answer_candidate_count", 0) or 0) > 0:
            answer_candidate_supported += 1
        if bool(prediction.metadata.get("provenance_supported")):
            provenance_supported += 1
        if prediction.metadata.get("should_abstain"):
            abstention_total += 1
            if prediction.is_correct:
                abstention_honest += 1
        if prediction.category == "current_state":
            current_state_total += 1
            if prediction.is_correct:
                current_state_correct += 1

    total_predictions = len(predictions)
    latency_summary = _numeric_metric_summary(latency_values)
    latency_summary["missing"] = total_predictions - len(latency_values)
    token_summary = _numeric_metric_summary(token_values)
    token_summary["missing"] = total_predictions - len(token_values)

    return {
        "measured_metrics": {
            "latency_ms": latency_summary,
            "total_tokens": token_summary,
            "answer_candidate_support_rate": _rate_row(
                numerator=answer_candidate_supported,
                total=total_predictions,
                label="supported",
            ),
            "provenance_support_rate": _rate_row(
                numerator=provenance_supported,
                total=total_predictions,
                label="supported",
            ),
            "abstention_honesty": _rate_row(
                numerator=abstention_honest,
                total=abstention_total,
                label="honest",
            ),
            "current_state_accuracy": {
                **_accuracy_row(correct=current_state_correct, total=current_state_total),
            },
        },
        "unmeasured_metrics": [
            "stale_state_error_rate",
            "correction_success_rate",
            "deletion_reliability",
            "memory_drift_rate",
        ],
        "notes": [
            "This summary only reports metrics that current benchmark runs can measure honestly.",
            "Correction, deletion, and drift metrics still require dedicated product-memory evaluation tasks.",
        ],
    }


def run_baseline_predictions(
    samples: list[NormalizedBenchmarkSample],
    packets: list[BaselinePromptPacket],
    *,
    responder_name: str,
    responder: Any,
) -> list[BaselinePrediction]:
    lookup = _question_lookup(samples)
    predictions: list[BaselinePrediction] = []
    for packet in packets:
        question = lookup[packet.question_id]
        predicted_answer = str(responder(packet))
        normalized_pred = _normalize_answer(predicted_answer)
        normalized_expected = [_normalize_answer(answer) for answer in question.expected_answers]
        is_correct = bool(normalized_pred) and normalized_pred in normalized_expected
        predictions.append(
            BaselinePrediction(
                benchmark_name=packet.benchmark_name,
                baseline_name=packet.baseline_name,
                sample_id=packet.sample_id,
                question_id=packet.question_id,
                category=question.category,
                predicted_answer=predicted_answer,
                expected_answers=question.expected_answers,
                is_correct=is_correct,
                metadata={
                    "responder_name": responder_name,
                    "route": packet.metadata.get("route"),
                    "should_abstain": question.should_abstain,
                    "evidence_scope": "multi_session" if len(question.evidence_session_ids) > 1 else "single_session",
                    "temporal_scope": "dated" if question.question_date else "undated",
                },
            )
        )
    return predictions


def build_scorecard(
    manifest: BenchmarkRunManifest | dict[str, Any],
    predictions: list[BaselinePrediction],
) -> dict[str, Any]:
    manifest_dict = manifest.to_dict() if isinstance(manifest, BenchmarkRunManifest) else manifest
    enriched_predictions: list[dict[str, Any]] = []
    known_issue_rows: list[dict[str, Any]] = []
    known_issue_counts: Counter[str] = Counter()
    by_category_total: Counter[str] = Counter()
    by_category_correct: Counter[str] = Counter()
    audited_by_category_total: Counter[str] = Counter()
    audited_by_category_correct: Counter[str] = Counter()
    audited_by_category_excluded: Counter[str] = Counter()
    abstain_total: Counter[str] = Counter()
    abstain_correct: Counter[str] = Counter()
    evidence_scope_total: Counter[str] = Counter()
    evidence_scope_correct: Counter[str] = Counter()
    temporal_scope_total: Counter[str] = Counter()
    temporal_scope_correct: Counter[str] = Counter()
    product_task_total: Counter[str] = Counter()
    product_task_correct: Counter[str] = Counter()
    overall_correct = 0
    overall_total = len(predictions)
    audited_overall_correct = 0
    audited_overall_total = 0
    audited_overall_excluded = 0
    for prediction in predictions:
        by_category_total[prediction.category] += 1
        if prediction.is_correct:
            by_category_correct[prediction.category] += 1
            overall_correct += 1
        prediction_dict = prediction.to_dict()
        prediction_dict.setdefault("metadata", {}).pop("known_issue", None)
        if prediction.benchmark_name == "BEAM":
            abstain_label = "abstain" if prediction.metadata.get("should_abstain") else "answer"
            abstain_total[abstain_label] += 1
            evidence_scope = str(prediction.metadata.get("evidence_scope", "single_session"))
            evidence_scope_total[evidence_scope] += 1
            temporal_scope = str(prediction.metadata.get("temporal_scope", "undated"))
            temporal_scope_total[temporal_scope] += 1
            if prediction.is_correct:
                abstain_correct[abstain_label] += 1
                evidence_scope_correct[evidence_scope] += 1
                temporal_scope_correct[temporal_scope] += 1
        if prediction.benchmark_name == "ProductMemory":
            task_label = str(prediction.metadata.get("product_memory_task", "unknown"))
            product_task_total[task_label] += 1
            if prediction.is_correct:
                product_task_correct[task_label] += 1
        known_issue = get_known_benchmark_issue(prediction.question_id)
        is_audit_excluded = False
        if known_issue:
            prediction_dict["metadata"]["known_issue"] = known_issue
            known_issue_rows.append(
                {
                    "question_id": prediction.question_id,
                    "classification": str(known_issue["classification"]),
                    "recommended_lane": str(known_issue["recommended_lane"]),
                    "is_correct": prediction.is_correct,
                }
            )
            classification = str(known_issue["classification"])
            known_issue_counts[classification] += 1
            is_audit_excluded = classification in AUDIT_EXCLUDED_KNOWN_ISSUE_CLASSES
        if is_audit_excluded:
            audited_by_category_excluded[prediction.category] += 1
            audited_overall_excluded += 1
        else:
            audited_by_category_total[prediction.category] += 1
            audited_overall_total += 1
            if prediction.is_correct:
                audited_by_category_correct[prediction.category] += 1
                audited_overall_correct += 1
        enriched_predictions.append(prediction_dict)

    category_scores = []
    audited_category_scores = []
    for category in sorted(by_category_total):
        category_scores.append(
            {
                "category": category,
                **_accuracy_row(
                    correct=by_category_correct[category],
                    total=by_category_total[category],
                ),
            }
        )
        audited_category_scores.append(
            {
                "category": category,
                **_accuracy_row(
                    correct=audited_by_category_correct[category],
                    total=audited_by_category_total[category],
                    excluded=audited_by_category_excluded[category],
                ),
            }
        )
    return {
        "run_manifest": manifest_dict,
        "overall": _accuracy_row(correct=overall_correct, total=overall_total),
        "audited_overall": _accuracy_row(
            correct=audited_overall_correct,
            total=audited_overall_total,
            excluded=audited_overall_excluded,
        ),
        "by_category": category_scores,
        "audited_by_category": audited_category_scores,
        "known_issue_summary": {
            "total_flagged": len(known_issue_rows),
            "incorrect_flagged": sum(1 for item in known_issue_rows if not item["is_correct"]),
            "audit_excluded_total": audited_overall_excluded,
            "audit_excluded_classes": sorted(AUDIT_EXCLUDED_KNOWN_ISSUE_CLASSES),
            "by_classification": [
                {"classification": classification, "count": count}
                for classification, count in sorted(known_issue_counts.items())
            ],
            "questions": known_issue_rows,
        },
        "benchmark_slices": (
            {
                "should_abstain": _build_slice_rows(abstain_total, abstain_correct),
                "evidence_scope": _build_slice_rows(evidence_scope_total, evidence_scope_correct),
                "temporal_scope": _build_slice_rows(temporal_scope_total, temporal_scope_correct),
            }
            if manifest_dict.get("benchmark_name") == "BEAM"
            else {
                "product_memory_task": _build_slice_rows(product_task_total, product_task_correct),
            }
            if manifest_dict.get("benchmark_name") == "ProductMemory"
            else {}
        ),
        "product_memory_summary": _build_product_memory_summary(predictions),
        "predictions": enriched_predictions,
    }


def build_scorecard_contract_summary() -> dict[str, Any]:
    return {
        "prediction_contract": "BaselinePrediction",
        "scorecard_fields": [
            "run_manifest",
            "overall",
            "audited_overall",
            "by_category",
            "audited_by_category",
            "known_issue_summary",
            "benchmark_slices",
            "product_memory_summary",
            "predictions",
        ],
    }
