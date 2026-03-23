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
            "predictions",
        ],
    }
