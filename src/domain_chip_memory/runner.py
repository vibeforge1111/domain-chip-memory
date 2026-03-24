from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import re
from typing import Any

from .baselines import build_full_context_packets, build_lexical_packets
from .contracts import NormalizedBenchmarkSample
from .memory_systems import (
    build_beam_ready_temporal_atom_router_packets,
    build_dual_store_event_calendar_hybrid_packets,
    build_observational_temporal_memory_packets,
)
from .providers import ModelProvider
from .runs import BaselinePromptPacket
from .scorecards import BaselinePrediction, build_scorecard


RunProgressCallback = Callable[[dict[str, Any], list[BaselinePrediction], dict[str, Any]], None]

_ANSWER_IRREGULARS = {
    "appreciated": "appreciate",
    "felt": "feel",
    "went": "go",
    "made": "make",
    "did": "do",
}
_ANSWER_LEADING_FILLERS = {"a", "an", "the", "i", "she", "he", "they", "we", "it"}
_MONTH_YEAR_PATTERNS = ("%B %Y", "%B, %Y")
_FULL_DATE_PATTERNS = ("%d %B %Y", "%d %B, %Y", "%B %d %Y", "%B %d, %Y")


def _normalize_answer_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    normalized: list[str] = []
    for token in tokens:
        token = _ANSWER_IRREGULARS.get(token, token)
        if len(token) > 4 and token.endswith("ed"):
            token = token[:-2]
        elif len(token) > 5 and token.endswith("ing"):
            token = token[:-3]
        elif len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        normalized.append(token)
    while normalized and normalized[0] in _ANSWER_LEADING_FILLERS:
        normalized.pop(0)
    return normalized


def _build_manifest_and_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    baseline_name: str,
    top_k_sessions: int,
    fallback_sessions: int,
) -> tuple[dict[str, Any], list[BaselinePromptPacket]]:
    if baseline_name == "full_context":
        return build_full_context_packets(samples)
    if baseline_name == "lexical":
        return build_lexical_packets(
            samples,
            top_k_sessions=top_k_sessions,
            fallback_sessions=fallback_sessions,
        )
    if baseline_name == "beam_temporal_atom_router":
        return build_beam_ready_temporal_atom_router_packets(
            samples,
            top_k_atoms=top_k_sessions,
            include_rehydrated_sessions=fallback_sessions,
        )
    if baseline_name == "observational_temporal_memory":
        return build_observational_temporal_memory_packets(
            samples,
            max_observations=max(top_k_sessions * 2, 4),
            max_reflections=max(fallback_sessions + 2, 2),
        )
    if baseline_name == "dual_store_event_calendar_hybrid":
        return build_dual_store_event_calendar_hybrid_packets(
            samples,
            max_observations=max(top_k_sessions * 2, 4),
            top_k_events=max(fallback_sessions + 2, 2),
        )
    raise ValueError(f"Unsupported baseline: {baseline_name}")


def _ordered_predictions(
    packets: list[BaselinePromptPacket],
    prediction_by_question_id: dict[str, BaselinePrediction],
) -> list[BaselinePrediction]:
    return [
        prediction_by_question_id[packet.question_id]
        for packet in packets
        if packet.question_id in prediction_by_question_id
    ]


def _build_prediction(
    packet: BaselinePromptPacket,
    *,
    question: Any,
    provider: ModelProvider,
    answer: str,
    provider_metadata: dict[str, Any],
) -> BaselinePrediction:
    normalized_pred = " ".join(answer.lower().strip().split())
    return BaselinePrediction(
        benchmark_name=packet.benchmark_name,
        baseline_name=packet.baseline_name,
        sample_id=packet.sample_id,
        question_id=packet.question_id,
        category=question.category,
        predicted_answer=answer,
        expected_answers=question.expected_answers,
        is_correct=bool(normalized_pred) and _matches_expected_answer(normalized_pred, question.expected_answers),
        metadata={
            "provider_name": provider.name,
            **provider_metadata,
            "route": packet.metadata.get("route"),
        },
    )


def _matches_expected_answer(normalized_pred: str, expected_answers: list[str]) -> bool:
    normalized_expected = [" ".join(expected.lower().strip().split()) for expected in expected_answers]
    if (
        normalized_pred == "unknown"
        and any(expected.startswith("you did not mention this information") for expected in normalized_expected)
    ):
        return True
    if normalized_pred in normalized_expected:
        return True
    pred_tokens = _normalize_answer_tokens(normalized_pred)
    for expected in normalized_expected:
        if pred_tokens and pred_tokens == _normalize_answer_tokens(expected):
            return True
        if " or " not in expected:
            continue
        options = [option.strip() for option in expected.split(" or ") if option.strip()]
        if normalized_pred in options:
            return True
        if any(pred_tokens and pred_tokens == _normalize_answer_tokens(option) for option in options):
            return True
        if any(
            normalized_pred.endswith(option) or option.endswith(normalized_pred)
            for option in options
            if len(option) >= 3
        ):
            return True
    pred_month_year = _parse_month_year(normalized_pred)
    pred_full_date = _parse_full_date(normalized_pred)
    for expected in normalized_expected:
        expected_month_year = _parse_month_year(expected)
        if expected_month_year and pred_full_date and (
            pred_full_date.year == expected_month_year.year and pred_full_date.month == expected_month_year.month
        ):
            return True
        expected_full_date = _parse_full_date(expected)
        if pred_month_year and expected_full_date and (
            pred_month_year.year == expected_full_date.year and pred_month_year.month == expected_full_date.month
        ):
            return True
    return False


def _parse_month_year(text: str) -> datetime | None:
    normalized = text.strip().replace(",", "")
    for pattern in _MONTH_YEAR_PATTERNS:
        try:
            return datetime.strptime(normalized, pattern.replace(",", ""))
        except ValueError:
            continue
    return None


def _parse_full_date(text: str) -> datetime | None:
    normalized = text.strip().replace(",", "")
    for pattern in _FULL_DATE_PATTERNS:
        try:
            return datetime.strptime(normalized, pattern.replace(",", ""))
        except ValueError:
            continue
    return None


def run_baseline(
    samples: list[NormalizedBenchmarkSample],
    *,
    baseline_name: str,
    provider: ModelProvider,
    top_k_sessions: int = 2,
    fallback_sessions: int = 1,
    existing_predictions: list[BaselinePrediction] | None = None,
    progress_callback: RunProgressCallback | None = None,
) -> dict[str, Any]:
    manifest, packets = _build_manifest_and_packets(
        samples,
        baseline_name=baseline_name,
        top_k_sessions=top_k_sessions,
        fallback_sessions=fallback_sessions,
    )

    question_lookup = {
        question.question_id: question for sample in samples for question in sample.questions
    }
    prediction_by_question_id = {
        prediction.question_id: prediction for prediction in (existing_predictions or [])
    }
    total_packets = len(packets)
    if progress_callback and prediction_by_question_id:
        progress_callback(
            manifest,
            _ordered_predictions(packets, prediction_by_question_id),
            {
                "event": "resume",
                "completed": len(prediction_by_question_id),
                "remaining": max(total_packets - len(prediction_by_question_id), 0),
                "total": total_packets,
            },
        )

    for index, packet in enumerate(packets, start=1):
        if packet.question_id in prediction_by_question_id:
            continue
        current_predictions = _ordered_predictions(packets, prediction_by_question_id)
        if progress_callback:
            progress_callback(
                manifest,
                current_predictions,
                {
                    "event": "start",
                    "index": index,
                    "completed": len(current_predictions),
                    "total": total_packets,
                    "question_id": packet.question_id,
                    "sample_id": packet.sample_id,
                },
            )
        try:
            provider_response = provider.generate_answer(packet)
        except Exception as exc:
            if progress_callback:
                progress_callback(
                    manifest,
                    current_predictions,
                    {
                        "event": "error",
                        "index": index,
                        "completed": len(current_predictions),
                        "total": total_packets,
                        "question_id": packet.question_id,
                        "sample_id": packet.sample_id,
                        "error": str(exc),
                    },
                )
            raise
        question = question_lookup[packet.question_id]
        prediction = _build_prediction(
            packet,
            question=question,
            provider=provider,
            answer=provider_response.answer,
            provider_metadata=provider_response.metadata,
        )
        prediction_by_question_id[packet.question_id] = prediction
        current_predictions = _ordered_predictions(packets, prediction_by_question_id)
        if progress_callback:
            progress_callback(
                manifest,
                current_predictions,
                {
                    "event": "completed",
                    "index": index,
                    "completed": len(current_predictions),
                    "total": total_packets,
                    "question_id": packet.question_id,
                    "sample_id": packet.sample_id,
                    "predicted_answer": prediction.predicted_answer,
                    "is_correct": prediction.is_correct,
                },
            )

    return build_scorecard(manifest, _ordered_predictions(packets, prediction_by_question_id))


def build_runner_contract_summary() -> dict[str, object]:
    return {
        "runner_entrypoint": "run_baseline",
        "supported_baselines": [
            "full_context",
            "lexical",
            "beam_temporal_atom_router",
            "observational_temporal_memory",
            "dual_store_event_calendar_hybrid",
        ],
        "required_inputs": ["normalized_samples", "baseline_name", "provider"],
    }
