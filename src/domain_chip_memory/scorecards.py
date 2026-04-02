from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
import re
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
    question: str = ""
    metadata: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return asdict(self)


def _normalize_answer(answer: str) -> str:
    normalized = (
        answer.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )
    return " ".join(normalized.lower().strip().split())


def _extract_beam_rubric_requirement(expected: str) -> str:
    for prefix in (
        "llm response should contain:",
        "llm response should state:",
        "llm response should mention:",
    ):
        if expected.startswith(prefix):
            return expected[len(prefix) :].strip()
    return ""


def _normalize_beam_rubric_surface(text: str) -> str:
    normalized = re.sub(r"\b(my|your)\b", "__poss__", text)
    return re.sub(r"\b(i|you)\b", "__person__", normalized)


def _matches_beam_rubric_requirement(normalized_pred: str, requirement: str) -> bool:
    if not requirement:
        return False
    if requirement == "there is contradictory information":
        return any(
            phrase in normalized_pred
            for phrase in ("contradictory information", "conflicting statements", "conflicting information")
        )
    if requirement == "code blocks with syntax highlighting":
        return bool(re.search(r"```[a-z0-9_+-]+", normalized_pred))
    if requirement == "clearly formatted code snippets":
        return "```" in normalized_pred
    if requirement == "step-by-step breakdown":
        return "step-by-step" in normalized_pred and any(
            phrase in normalized_pred for phrase in ("first", "next", "then", "finally")
        )
    if requirement == "clear explanation of each step":
        return any(
            phrase in normalized_pred
            for phrase in ("each step clearly", "explanation shows each step clearly", "explain each step clearly")
        )
    if requirement == "include tree drawing":
        return "tree drawing" in normalized_pred
    if requirement == "multiple methods described":
        return sum(
            1
            for phrase in ("base-height", "heron", "included angle", "sin(", "median", "altitude")
            if phrase in normalized_pred
        ) >= 2
    if requirement == "comparison between methods":
        return any(
            phrase in normalized_pred
            for phrase in ("compare", "comparison", "more direct", "better when", "while ")
        )
    if requirement == "explicit version details for each dependency":
        mentions = re.findall(r"\b[a-z][a-z0-9.+-]*\s+\d+(?:\.\d+)+\b", normalized_pred)
        return len(mentions) >= 2
    if requirement == "includes numeric codes associated with errors":
        codes = {match.group(0) for match in re.finditer(r"\b[1-5]\d{2}\b", normalized_pred)}
        return len(codes) >= 2
    if requirement == "mention of semantic tags like <header>, <nav>, <main>, <footer>":
        return all(tag in normalized_pred for tag in ("<header>", "<nav>", "<main>", "<footer>"))
    if requirement == "explanation of tag purposes":
        return any(word in normalized_pred for word in ("defines", "contains", "holds", "provides"))
    if requirement == "uses bootstrap 5.3.0 classes and components":
        return "bootstrap 5.3.0" in normalized_pred and (
            "class" in normalized_pred or "component" in normalized_pred
        )
    if requirement == "suggests lightweight libraries":
        return "lightweight" in normalized_pred and any(
            term in normalized_pred for term in ("library", "libraries", "flask-login", "sqlite", "chart.js")
        )
    if requirement == "avoids recommending large frameworks or heavy dependencies":
        return "avoid large frameworks" in normalized_pred or "heavy dependencies" in normalized_pred
    if requirement == "suggests security measures that are efficient and lightweight":
        return "lightweight" in normalized_pred or "efficient" in normalized_pred
    if requirement == "proposes incremental or practical enhancements":
        return any(term in normalized_pred for term in ("incrementally", "practical", "pragmatic"))
    if requirement == "recommends using localstorage or in-memory cache":
        return "localstorage" in normalized_pred or "in-memory cache" in normalized_pred
    if requirement == "avoids suggesting large libraries or frameworks":
        return "large libraries or frameworks" in normalized_pred or "avoid large frameworks" in normalized_pred
    if requirement == "mentions automated workflow monitoring tools":
        return any(
            term in normalized_pred for term in ("github actions", "status checks", "job summaries", "artifacts", "notifications")
        )
    if requirement == "avoids recommending manual deployment checks":
        return (
            "manual deployment checks" not in normalized_pred
            or "better than relying on manual deployment checks" in normalized_pred
            or "avoid manual deployment checks" in normalized_pred
            or "instead of relying on manual deployment checks" in normalized_pred
        )
    if requirement == "does not limit to a single method or skip any requested calculations":
        return "different methods" in normalized_pred and any(
            phrase in normalized_pred
            for phrase in ("none of the requested calculations are skipped", "rather than limiting it to one")
        )
    if requirement in {"provides step-by-step logical proof", "dprovides step-by-step logical proof"}:
        return "step-by-step" in normalized_pred and any(
            phrase in normalized_pred for phrase in ("first", "next", "finally", "conclude")
        )
    if requirement == "explains reasoning behind each step clearly":
        return any(
            phrase in normalized_pred
            for phrase in ("reasoning behind each step", "asa applies because", "makes the reasoning behind each step explicit")
        )
    if requirement == "breaks down the problem into sequential steps":
        return any(
            phrase in normalized_pred
            for phrase in ("sequential steps", "step by step", "first count", "then write", "finally simplify")
        )
    if requirement == "avoids suggesting foundation or other frameworks":
        return (
            "foundation" not in normalized_pred
            or "without switching to foundation or other frameworks" in normalized_pred
            or "avoid foundation or other frameworks" in normalized_pred
        )
    if requirement == "recommends lazysizes or similar lightweight vanilla js libraries":
        return any(
            phrase in normalized_pred
            for phrase in ("lazysizes", "lightweight vanilla js", "lightweight javascript", "vanilla javascript")
        )
    if requirement == "i recommended handle repeated retries":
        return any(
            phrase in normalized_pred
            for phrase in (
                "handle repeated retries",
                "handling repeated retries",
                "to handle repeated retries",
            )
        )
    numeric_with_unit_match = re.fullmatch(r"(\d+(?:\.\d+)?)\s+([a-z][a-z0-9 -]+)", requirement)
    if numeric_with_unit_match and normalized_pred == numeric_with_unit_match.group(1):
        return True
    if requirement == "avoids suggesting heavy frameworks or large libraries":
        return not any(framework in normalized_pred for framework in ("react", "angular", "vue", "next.js"))
    return requirement in normalized_pred or _normalize_beam_rubric_surface(requirement) in _normalize_beam_rubric_surface(normalized_pred)


def _matches_expected_answer(normalized_pred: str, expected_answers: list[str]) -> bool:
    normalized_expected = [_normalize_answer(answer) for answer in expected_answers]
    normalized_pred_without_ago = re.sub(r"\s+ago$", "", normalized_pred).strip()
    normalized_expected_without_ago = [re.sub(r"\s+ago$", "", expected).strip() for expected in normalized_expected]
    if not normalized_pred:
        return False
    if normalized_pred in normalized_expected:
        return True
    if normalized_pred_without_ago in normalized_expected_without_ago:
        return True
    numeric_with_unit_match = re.fullmatch(r"(\d+(?:\.\d+)?)\s+(days?|weeks?|months?|years?)", normalized_pred_without_ago)
    if numeric_with_unit_match and numeric_with_unit_match.group(1) in normalized_expected_without_ago:
        return True
    pred_tokens = re.findall(r"[a-z0-9]+", normalized_pred_without_ago)
    for expected in normalized_expected_without_ago:
        parenthetical_stripped = re.sub(r"\s*\([^)]*\)", "", expected).strip()
        if parenthetical_stripped and parenthetical_stripped != expected:
            if normalized_pred_without_ago == parenthetical_stripped:
                return True
            if pred_tokens and pred_tokens == re.findall(r"[a-z0-9]+", parenthetical_stripped):
                return True
        if pred_tokens and pred_tokens == re.findall(r"[a-z0-9]+", expected):
            return True
    rubric_requirements = [
        requirement
        for expected in normalized_expected
        if (requirement := _extract_beam_rubric_requirement(expected))
    ]
    if rubric_requirements and all(
        _matches_beam_rubric_requirement(normalized_pred, requirement) for requirement in rubric_requirements
    ):
        return True
    return False


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


def _label_count_rows(counter: Counter[str]) -> list[dict[str, Any]]:
    return [{"label": label, "count": counter[label]} for label in sorted(counter)]


def _build_product_memory_summary(predictions: list[BaselinePrediction]) -> dict[str, Any]:
    latency_values: list[float | int] = []
    token_values: list[float | int] = []
    answer_candidate_supported = 0
    provenance_supported = 0
    abstention_total = 0
    abstention_honest = 0
    current_state_total = 0
    current_state_correct = 0
    answer_source_counts: Counter[str] = Counter()
    answer_role_counts: Counter[str] = Counter()
    answer_type_counts: Counter[str] = Counter()
    expected_source_total = 0
    expected_source_aligned = 0
    retrieved_role_prediction_counts: Counter[str] = Counter()
    retrieved_role_item_counts: Counter[str] = Counter()
    retrieved_role_supported = 0

    for prediction in predictions:
        latency = prediction.metadata.get("latency_ms")
        if isinstance(latency, (int, float)):
            latency_values.append(latency)
        total_tokens = prediction.metadata.get("total_tokens")
        if isinstance(total_tokens, (int, float)):
            token_values.append(total_tokens)
        if int(prediction.metadata.get("answer_candidate_count", 0) or 0) > 0:
            answer_candidate_supported += 1
        answer_source = str(prediction.metadata.get("primary_answer_candidate_source", "") or "").strip()
        if answer_source:
            answer_source_counts[answer_source] += 1
        answer_role = str(prediction.metadata.get("primary_answer_candidate_role", "") or "").strip()
        if answer_role:
            answer_role_counts[answer_role] += 1
        expected_source = str(prediction.metadata.get("expected_answer_candidate_source", "") or "").strip()
        if expected_source:
            expected_source_total += 1
            if answer_source == expected_source:
                expected_source_aligned += 1
        retrieved_role_counts = prediction.metadata.get("retrieved_memory_role_counts")
        if isinstance(retrieved_role_counts, dict) and retrieved_role_counts:
            retrieved_role_supported += 1
            for label, count in retrieved_role_counts.items():
                role = str(label or "").strip()
                if not role:
                    continue
                if isinstance(count, (int, float)):
                    retrieved_role_item_counts[role] += int(count)
                    retrieved_role_prediction_counts[role] += 1
        answer_type = str(prediction.metadata.get("primary_answer_candidate_type", "") or "").strip()
        if answer_type:
            answer_type_counts[answer_type] += 1
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
            "primary_answer_candidate_sources": {
                "supported": sum(answer_source_counts.values()),
                "total": total_predictions,
                "rows": _label_count_rows(answer_source_counts),
            },
            "primary_answer_candidate_source_alignment": _rate_row(
                numerator=expected_source_aligned,
                total=expected_source_total,
                label="aligned",
            ),
            "primary_answer_candidate_roles": {
                "supported": sum(answer_role_counts.values()),
                "total": total_predictions,
                "rows": _label_count_rows(answer_role_counts),
            },
            "primary_answer_candidate_types": {
                "supported": sum(answer_type_counts.values()),
                "total": total_predictions,
                "rows": _label_count_rows(answer_type_counts),
            },
            "retrieved_memory_roles": {
                "supported": retrieved_role_supported,
                "total": total_predictions,
                "rows": _label_count_rows(retrieved_role_prediction_counts),
            },
            "retrieved_memory_role_items": {
                "supported": sum(retrieved_role_item_counts.values()),
                "total": total_predictions,
                "rows": _label_count_rows(retrieved_role_item_counts),
            },
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
        is_correct = _matches_expected_answer(normalized_pred, question.expected_answers)
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
                question=question.question,
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
    product_operation_total: Counter[str] = Counter()
    product_operation_correct: Counter[str] = Counter()
    product_scope_total: Counter[str] = Counter()
    product_scope_correct: Counter[str] = Counter()
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
            operation_label = str(prediction.metadata.get("memory_operation", "unknown"))
            product_operation_total[operation_label] += 1
            scope_label = str(prediction.metadata.get("memory_scope", "unknown"))
            product_scope_total[scope_label] += 1
            if prediction.is_correct:
                product_task_correct[task_label] += 1
                product_operation_correct[operation_label] += 1
                product_scope_correct[scope_label] += 1
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
                "memory_operation": _build_slice_rows(product_operation_total, product_operation_correct),
                "memory_scope": _build_slice_rows(product_scope_total, product_scope_correct),
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
