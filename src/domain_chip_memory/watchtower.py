from __future__ import annotations

from pathlib import Path

from .benchmark_registry import PUBLIC_TARGETS, build_benchmark_scorecard, suggest_mutations, utc_now


def build_watchtower_summary(root: Path) -> dict:
    scorecard = build_benchmark_scorecard()
    docs_root = root / "docs"
    required_docs = [
        "PRD.md",
        "ARCHITECTURE.md",
        "IMPLEMENTATION_PLAN.md",
        "BENCHMARK_STRATEGY.md",
        "AUTOLOOP_FLYWHEEL.md",
        "OPEN_SOURCE_ATTRIBUTION_PLAN.md",
    ]
    existing_docs = [name for name in required_docs if (docs_root / name).exists()]

    return {
        "generated_at": utc_now(),
        "status": "discovery",
        "benchmark_target_summary": scorecard["coverage_summary"],
        "docs_ready": {
            "required": required_docs,
            "present_count": len(existing_docs),
            "missing_count": len(required_docs) - len(existing_docs),
            "present": existing_docs,
        },
        "frontier_gaps": [
            target.next_action for target in PUBLIC_TARGETS if target.status != "pinned"
        ],
        "recommended_next_mutations": suggest_mutations(),
    }

