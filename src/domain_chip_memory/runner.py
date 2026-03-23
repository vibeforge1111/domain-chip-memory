from __future__ import annotations

from typing import Any

from .baselines import build_full_context_packets, build_lexical_packets
from .contracts import NormalizedBenchmarkSample
from .memory_systems import (
    build_beam_ready_temporal_atom_router_packets,
    build_dual_store_event_calendar_hybrid_packets,
    build_observational_temporal_memory_packets,
)
from .providers import ModelProvider
from .scorecards import BaselinePrediction, build_scorecard


def run_baseline(
    samples: list[NormalizedBenchmarkSample],
    *,
    baseline_name: str,
    provider: ModelProvider,
    top_k_sessions: int = 2,
    fallback_sessions: int = 1,
) -> dict[str, Any]:
    if baseline_name == "full_context":
        manifest, packets = build_full_context_packets(samples)
    elif baseline_name == "lexical":
        manifest, packets = build_lexical_packets(
            samples,
            top_k_sessions=top_k_sessions,
            fallback_sessions=fallback_sessions,
        )
    elif baseline_name == "beam_temporal_atom_router":
        manifest, packets = build_beam_ready_temporal_atom_router_packets(
            samples,
            top_k_atoms=top_k_sessions,
            include_rehydrated_sessions=fallback_sessions,
        )
    elif baseline_name == "observational_temporal_memory":
        manifest, packets = build_observational_temporal_memory_packets(
            samples,
            max_observations=max(top_k_sessions * 2, 4),
            max_reflections=max(fallback_sessions + 2, 2),
        )
    elif baseline_name == "dual_store_event_calendar_hybrid":
        manifest, packets = build_dual_store_event_calendar_hybrid_packets(
            samples,
            max_observations=max(top_k_sessions * 2, 4),
            top_k_events=max(fallback_sessions + 2, 2),
        )
    else:
        raise ValueError(f"Unsupported baseline: {baseline_name}")

    question_lookup = {
        question.question_id: question for sample in samples for question in sample.questions
    }
    predictions: list[BaselinePrediction] = []
    for packet in packets:
        provider_response = provider.generate_answer(packet)
        question = question_lookup[packet.question_id]
        normalized_pred = " ".join(provider_response.answer.lower().strip().split())
        normalized_expected = [
            " ".join(answer.lower().strip().split()) for answer in question.expected_answers
        ]
        predictions.append(
            BaselinePrediction(
                benchmark_name=packet.benchmark_name,
                baseline_name=packet.baseline_name,
                sample_id=packet.sample_id,
                question_id=packet.question_id,
                category=question.category,
                predicted_answer=provider_response.answer,
                expected_answers=question.expected_answers,
                is_correct=bool(normalized_pred) and normalized_pred in normalized_expected,
                metadata={
                    "provider_name": provider.name,
                    **provider_response.metadata,
                    "route": packet.metadata.get("route"),
                },
            )
        )
    return build_scorecard(manifest, predictions)


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
