from __future__ import annotations

from collections.abc import Callable
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
    normalized_expected = [
        " ".join(expected.lower().strip().split()) for expected in question.expected_answers
    ]
    return BaselinePrediction(
        benchmark_name=packet.benchmark_name,
        baseline_name=packet.baseline_name,
        sample_id=packet.sample_id,
        question_id=packet.question_id,
        category=question.category,
        predicted_answer=answer,
        expected_answers=question.expected_answers,
        is_correct=bool(normalized_pred) and normalized_pred in normalized_expected,
        metadata={
            "provider_name": provider.name,
            **provider_metadata,
            "route": packet.metadata.get("route"),
        },
    )


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
