from __future__ import annotations

from typing import Any

from .contracts import NormalizedBenchmarkSample
from .providers import ModelProvider
from .runner import run_baseline


DEFAULT_SYSTEMS = [
    "full_context",
    "lexical",
    "beam_temporal_atom_router",
    "observational_temporal_memory",
    "contradiction_aware_profile_memory",
    "contradiction_aware_summary_synthesis_memory",
    "dual_store_event_calendar_hybrid",
    "stateful_event_reconstruction",
    "summary_synthesis_memory",
    "typed_state_update_memory",
]


def _compact_scorecard(scorecard: dict[str, Any]) -> dict[str, Any]:
    manifest = scorecard["run_manifest"]
    return {
        "run_manifest": {
            "run_id": manifest["run_id"],
            "benchmark_name": manifest["benchmark_name"],
            "baseline_name": manifest["baseline_name"],
            "sample_count": len(manifest.get("sample_ids", [])),
            "question_count": manifest["question_count"],
            "metadata": manifest.get("metadata", {}),
        },
        "overall": scorecard["overall"],
        "audited_overall": scorecard["audited_overall"],
        "by_category": scorecard["by_category"],
        "audited_by_category": scorecard["audited_by_category"],
    }


def run_candidate_comparison(
    samples: list[NormalizedBenchmarkSample],
    *,
    provider: ModelProvider,
    systems: list[str] | None = None,
    top_k_sessions: int = 2,
    fallback_sessions: int = 1,
) -> dict[str, Any]:
    system_names = systems or DEFAULT_SYSTEMS
    return {
        "benchmark_name": samples[0].benchmark_name if samples else "unknown",
        "sample_count": len(samples),
        "question_count": sum(len(sample.questions) for sample in samples),
        "provider_name": provider.name,
        "systems": {
            name: _compact_scorecard(
                run_baseline(
                    samples,
                    baseline_name=name,
                    provider=provider,
                    top_k_sessions=top_k_sessions,
                    fallback_sessions=fallback_sessions,
                )
            )
            for name in system_names
        },
    }


def build_experiment_contract_summary() -> dict[str, Any]:
    return {
        "entrypoint": "run_candidate_comparison",
        "default_systems": DEFAULT_SYSTEMS,
        "compact_outputs": [
            "run_manifest",
            "overall",
            "audited_overall",
            "by_category",
            "audited_by_category",
        ],
    }
