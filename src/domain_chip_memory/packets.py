from __future__ import annotations

from .canonical_configs import get_canonical_configs
from .benchmark_registry import build_benchmark_scorecard, suggest_mutations, utc_now


def build_strategy_packet() -> dict:
    scorecard = build_benchmark_scorecard()
    return {
        "generated_at": utc_now(),
        "packet_type": "memory_system_strategy_packet",
        "north_star": "Beat the strongest public agent-memory systems with a reproducible benchmark-native architecture.",
        "benchmarks": scorecard["public_targets"],
        "experimental_frontier_claims": scorecard.get("experimental_frontier_claims", []),
        "shadow_benchmarks": scorecard.get("shadow_benchmarks", []),
        "canonical_configs": get_canonical_configs(),
        "architecture_bets": [
            "memory atoms with provenance",
            "temporal and version relations",
            "question-type-aware retrieval",
            "stable observational compression for very large context windows",
            "lightweight online path with offline consolidation",
            "failure-slice mutation loop",
        ],
        "active_optimization_lane": {
            "benchmark": "LongMemEval",
            "provider": "heuristic_v1",
            "system": "summary_synthesis_memory",
            "status": "completed full-dataset coverage",
            "evidence": {
                "slice": "full 500 LongMemEval_s samples",
                "score": "500/500",
                "accuracy": 1.0,
            },
            "why": "Current source-of-truth measured path in-repo; it closes contiguous coverage over the full official LongMemEval_s dataset and now serves as the finished benchmark reference rather than an open frontier slice.",
        },
        "ten_system_variants": [
            {
                "variant_id": "variant-01",
                "name": "Full-Context Control",
                "family": "control",
                "benchmark_posture": "use as an honesty baseline, not as the target architecture",
            },
            {
                "variant_id": "variant-02",
                "name": "Lexical Retrieval Memory",
                "family": "retrieval",
                "benchmark_posture": "cheap baseline that should lose once temporal pressure rises",
            },
            {
                "variant_id": "variant-03",
                "name": "Vector Semantic Retrieval Memory",
                "family": "retrieval",
                "benchmark_posture": "common production baseline, but weak on stale facts and time",
            },
            {
                "variant_id": "variant-04",
                "name": "Rolling Summary Memory",
                "family": "compression",
                "benchmark_posture": "lightweight but vulnerable to irreversible information loss",
            },
            {
                "variant_id": "variant-05",
                "name": "Temporal Atom Memory",
                "family": "temporal_structured",
                "benchmark_posture": "strong benchmark-native default for updates and supersession",
            },
            {
                "variant_id": "variant-06",
                "name": "Event Calendar Memory",
                "family": "temporal_structured",
                "benchmark_posture": "high-upside for temporal and multi-hop slices",
            },
            {
                "variant_id": "variant-07",
                "name": "Observational Stable-Window Memory",
                "family": "compression_temporal",
                "benchmark_posture": "important for BEAM-style pressure and stable prompt caching",
            },
            {
                "variant_id": "variant-08",
                "name": "Agentic Search Memory",
                "family": "agentic_retrieval",
                "benchmark_posture": "frontier claim lane only until lighter systems plateau",
            },
            {
                "variant_id": "variant-09",
                "name": "Relation Graph Memory",
                "family": "relational",
                "benchmark_posture": "second-wave path for multi-hop and entity-heavy slices",
            },
            {
                "variant_id": "variant-10",
                "name": "Dual-Store Consolidated Memory",
                "family": "hybrid",
                "benchmark_posture": "best long-range candidate once BEAM pressure starts to dominate",
            },
        ],
        "initial_system_ladder": [
            {
                "system_id": "system-1",
                "name": "Beam-Ready Temporal Atom Router",
                "components": ["EPI", "ATOM", "TIME", "ROUTE", "REHYDRATE", "ABSTAIN"],
                "purpose": "Lightweight default build for LongMemEval, LoCoMo, GoodAI, and early BEAM pressure.",
            },
            {
                "system_id": "system-2",
                "name": "Observational Temporal Memory",
                "components": ["OBSERVE", "REFLECT", "TIME", "PROFILE", "ABSTAIN"],
                "purpose": "Stable-window compressed memory candidate for large-context and BEAM-oriented runs.",
            },
            {
                "system_id": "system-3",
                "name": "Dual-Store Event Calendar Hybrid",
                "components": ["OBSERVE", "ATOM", "TIME", "EVENTS", "ROUTE", "REHYDRATE", "RELATE", "ABSTAIN"],
                "purpose": "Highest-upside hybrid once the first two systems define the best lightweight ingredients.",
            },
        ],
        "remaining_work": [
            "canonical scorecards per benchmark",
            "full-context baseline",
            "lexical baseline",
            "semantic-atom baseline",
            "temporal-semantic baseline",
            "observational-memory baseline",
            "beam-ready dual-store baseline",
            "shadow benchmark checks",
            "ablation runner",
            "promotion and rollback logging over real runs",
        ],
        "combination_search_doctrine": [
            "Start with a strong lightweight baseline before trying heavier combinations.",
            "Add one component family at a time and compare against the direct parent baseline.",
            "Prefer combinations that pair compact retrieval units with temporal disambiguation and selective routing.",
            "Treat heavyweight online combinations as guilty until they beat the lightweight stack clearly.",
        ],
        "candidate_combinations": [
            {
                "combo_id": "combo-a",
                "components": ["EPI", "ATOM"],
                "why": "Strong simple retrieval baseline with raw provenance.",
            },
            {
                "combo_id": "combo-b",
                "components": ["EPI", "ATOM", "TIME"],
                "why": "Most defensible V1 core for changing facts and temporal reasoning.",
            },
            {
                "combo_id": "combo-c",
                "components": ["EPI", "ATOM", "TIME", "ROUTE"],
                "why": "Adds selective routing without a heavyweight online path.",
            },
            {
                "combo_id": "combo-g",
                "components": ["EPI", "ATOM", "TIME", "PROFILE", "ROUTE", "REHYDRATE", "ABSTAIN"],
                "why": "Best current candidate for a serious benchmark-ready lightweight stack.",
            },
        ],
        "skeptical_combinations": [
            {
                "components": ["GRAPH", "SEARCH-AGENT"],
                "risk": "retrieval complexity explosion before the lightweight baseline is exhausted",
            },
            {
                "components": ["SEARCH-AGENT", "ANSWER-ENSEMBLE"],
                "risk": "online latency and token blow-up",
            },
        ],
        "priority_mutations": suggest_mutations(),
        "promotion_rule": "Do not promote a doctrine until it improves benchmark behavior and survives contradiction review.",
    }
