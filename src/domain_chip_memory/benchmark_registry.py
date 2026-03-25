from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class BenchmarkTarget:
    benchmark_name: str
    dataset_scope: str
    target_type: str
    current_public_leader: str
    reported_result: str
    win_condition: str
    status: str
    source_url: str
    notes: str
    next_action: str


@dataclass(frozen=True)
class ExperimentalFrontierClaim:
    system_name: str
    benchmark_name: str
    reported_result: str
    claim_type: str
    status: str
    source_url: str
    notes: str
    next_action: str


PUBLIC_TARGETS = [
    BenchmarkTarget(
        benchmark_name="LongMemEval",
        dataset_scope="LongMemEval_s",
        target_type="exact_public_score",
        current_public_leader="Chronos",
        reported_result="95.60% overall with Chronos High; 92.60% overall with Chronos Low",
        win_condition="Beat the best publicly sourced overall score with a reproducible run.",
        status="pinned",
        source_url="https://arxiv.org/abs/2603.16862",
        notes="Chronos, submitted on March 17, 2026, is the highest public LongMemEvalS claim in the current source sweep. Mastra OM remains the strongest implementation-backed public claim at 94.87% with gpt-5-mini and 84.23% with gpt-4o.",
        next_action="Treat Chronos as the frontier score target and Mastra OM as the strongest implementation-backed comparison point during reproduction.",
    ),
    BenchmarkTarget(
        benchmark_name="LoCoMo",
        dataset_scope="QA task over locomo10 subset",
        target_type="public_rank_claim",
        current_public_leader="Supermemory",
        reported_result="#1 claim, exact public score not pinned in reviewed source",
        win_condition="Pin exact sourced threshold, then beat it on the same task definition.",
        status="needs_threshold",
        source_url="https://github.com/supermemoryai/supermemory",
        notes="Public README claims #1, but exact numeric score was not visible in the source sweep.",
        next_action="Capture exact leaderboard number from official benchmark or reproducible MemoryBench run.",
    ),
    BenchmarkTarget(
        benchmark_name="GoodAI LTM Benchmark",
        dataset_scope="published benchmark configurations from 4k to 500k context spans",
        target_type="benchmark_harness_target",
        current_public_leader="GoodAI published agents and baselines",
        reported_result="Living benchmark with published configs and reported GoodAI agent baselines; exact single frontier number depends on configuration.",
        win_condition="Beat strong baselines inside the published harness on the chosen configuration set and preserve reproducibility.",
        status="active_harness",
        source_url="https://github.com/GoodAI/goodai-ltm-benchmark",
        notes="Best used as an internal core stress benchmark for long-span conversational memory and continual-memory upkeep rather than as a single public leaderboard scalar.",
        next_action="Choose the first canonical configuration set, reproduce the published baseline path, and lock the scorecard contract.",
    ),
    BenchmarkTarget(
        benchmark_name="BEAM",
        dataset_scope="100 coherent conversations and 2,000 validated questions up to 10M tokens",
        target_type="frontier_paper_benchmark",
        current_public_leader="LIGHT framework from the paper",
        reported_result="Paper reports LIGHT improving 3.5% to 12.69% over the strongest baselines depending on the backbone LLM.",
        win_condition="Reproduce the benchmark definition faithfully once code or data access is pinned, then beat the strongest reported baseline on the chosen slice.",
        status="paper_only",
        source_url="https://arxiv.org/abs/2510.27246",
        notes="High-value frontier benchmark for higher-context and million-token-scale memory pressure. Current source is the paper; the repo now has a paper-pinned local pilot slice, but the official implementation surface still needs pinning.",
        next_action="Maintain the paper-pinned local pilot lane while tracking public code or dataset release for full reproduction.",
    ),
]


EXPERIMENTAL_FRONTIER_CLAIMS = [
    ExperimentalFrontierClaim(
        system_name="Supermemory ASMR",
        benchmark_name="LongMemEval_s",
        reported_result="~98.60% with an 8-variant ensemble; ~97.20% with a 12-variant decision forest; framed as ~99% frontier memory",
        claim_type="pending_public_release",
        status="not_yet_reproducible",
        source_url="https://supermemory.ai/research/",
        notes=(
            "User-provided Supermemory ASMR writeup describes a forthcoming experimental release rather than the main production engine. "
            "The architecture uses multi-agent ingestion, agentic search, and answer ensembles. "
            "Treat it as a high-signal frontier claim to learn from, not yet as a pinned reproducible benchmark bar."
        ),
        next_action="Track the promised public release, pin the exact implementation surface, then reproduce against the same LongMemEval_s path.",
    ),
]


BENCHMARK_INVENTORY = [
    {
        "benchmark_name": "LongMemEval",
        "scope": "500 questions; six categories plus abstention; LongMemEval_s roughly 115k tokens and about 40 sessions",
        "core_strength_tested": ["knowledge-update", "temporal-reasoning", "multi-session"],
        "source_url": "https://github.com/xiaowu0162/LongMemEval",
        "license": "MIT",
    },
    {
        "benchmark_name": "LoCoMo",
        "scope": "10 very long conversations with QA and event summarization annotations",
        "core_strength_tested": ["single-hop", "multi-hop", "temporal", "adversarial"],
        "source_url": "https://github.com/snap-research/locomo",
        "license": "CC BY-NC 4.0",
    },
    {
        "benchmark_name": "GoodAI LTM Benchmark",
        "scope": "Living benchmark for long-term memory and continual-learning capabilities over very long conversations, with published configurations reaching up to 500k-token spans",
        "core_strength_tested": ["dynamic_memory_upkeep", "integration_over_long_periods", "long_span_recall", "continual_memory"],
        "source_url": "https://github.com/GoodAI/goodai-ltm-benchmark",
        "license": "MIT",
    },
    {
        "benchmark_name": "BEAM",
        "scope": "100 coherent and topically diverse conversations with 2,000 validated questions, designed to scale up to roughly 10M tokens",
        "core_strength_tested": ["million_token_memory", "long_context_reasoning", "episodic_memory", "working_memory", "scratchpad_support"],
        "source_url": "https://arxiv.org/abs/2510.27246",
        "license": "paper_source_only",
    },
]


SHADOW_BENCHMARKS = [
    {
        "benchmark_name": "ConvoMem",
        "scope": "75,336 QA pairs across user facts, assistant facts, preferences, changing facts, implicit connections, and abstention",
        "role": "shadow_regression_benchmark",
        "why": "Guardrail against overbuilding retrieval when full context still works and against regressions on preferences, changing facts, and abstention.",
        "source_url": "https://huggingface.co/datasets/Salesforce/ConvoMem",
        "license": "CC BY-NC 4.0",
    }
]


OPEN_SOURCE_MEMORY_SYSTEMS = [
    {
        "name": "Supermemory",
        "license": "MIT",
        "source_url": "https://github.com/supermemoryai/supermemory",
        "useful_patterns": [
            "memory generation from chunks",
            "relational versioning",
            "dual-layer timestamps",
            "hybrid search",
        ],
    },
    {
        "name": "MemoryBench",
        "license": "MIT",
        "source_url": "https://github.com/supermemoryai/memorybench",
        "useful_patterns": [
            "pluggable benchmarks",
            "pluggable providers",
            "checkpointed ingest-search-answer-evaluate pipeline",
        ],
    },
    {
        "name": "Mem0",
        "license": "Apache-2.0",
        "source_url": "https://github.com/mem0ai/mem0",
        "useful_patterns": [
            "memory-layer extraction",
            "production-facing SDK surfaces",
            "graph-aware memory positioning",
        ],
    },
    {
        "name": "A-Mem",
        "license": "MIT",
        "source_url": "https://github.com/WujiangXu/A-mem",
        "useful_patterns": [
            "agentic organization",
            "dynamic linking",
            "LoCoMo-facing experiment structure",
        ],
    },
    {
        "name": "Mastra Observational Memory",
        "license": "Apache-2.0 core plus enterprise-licensed ee paths",
        "source_url": "https://github.com/mastra-ai/mastra",
        "useful_patterns": [
            "stable context window",
            "observer and reflector background agents",
            "dense observation logs",
        ],
    },
    {
        "name": "Chronos",
        "license": "paper_source_only",
        "source_url": "https://arxiv.org/abs/2603.16862",
        "useful_patterns": [
            "structured event tuples",
            "event calendar plus turn calendar",
            "datetime range retrieval",
            "alias-aware temporal reasoning",
        ],
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_benchmark_scorecard() -> dict:
    pinned_count = sum(1 for target in PUBLIC_TARGETS if target.status == "pinned")
    return {
        "generated_at": utc_now(),
        "benchmark_family": "agent_memory",
        "public_targets": [asdict(target) for target in PUBLIC_TARGETS],
        "experimental_frontier_claims": [asdict(claim) for claim in EXPERIMENTAL_FRONTIER_CLAIMS],
        "benchmark_inventory": BENCHMARK_INVENTORY,
        "shadow_benchmarks": SHADOW_BENCHMARKS,
        "open_source_memory_systems": OPEN_SOURCE_MEMORY_SYSTEMS,
        "coverage_summary": {
            "target_count": len(PUBLIC_TARGETS),
            "pinned_threshold_count": pinned_count,
            "unpinned_threshold_count": len(PUBLIC_TARGETS) - pinned_count,
        },
        "verdict": (
            "LongMemEval has a pinned public bar. "
            "Supermemory ASMR is tracked separately as a pending experimental frontier claim rather than a pinned reproducible target. "
            "LoCoMo remains a frontier target with an exact public threshold still to pin. "
            "GoodAI LTM Benchmark is adopted as the third official benchmark harness. "
            "BEAM is added as a frontier higher-context benchmark pending public implementation pinning. "
            "ConvoMem is retained as a shadow regression benchmark."
        ),
    }


def suggest_mutations() -> list[dict]:
    return [
        {
            "mutation_id": "mem-001",
            "benchmark": "LongMemEval",
            "component": "schema",
            "mutation_family": "temporal_grounding",
            "rationale": "Public frontier is most differentiated on knowledge updates and temporal reasoning.",
            "parent_baseline": "epi_atom",
            "hypothesis_type": "single_component",
            "combined_components": ["ATOM", "TIME"],
            "target_failure_slice": "knowledge-update",
            "online_cost_delta": "small",
            "latency_delta": "small",
            "token_delta": "none",
            "comparison_rule": "Compare against semantic-atom retrieval without temporal logic.",
            "keep_if": "Keep only if knowledge-update improves without a broad regression elsewhere.",
        },
        {
            "mutation_id": "mem-002",
            "benchmark": "Cross-benchmark",
            "component": "retrieval",
            "mutation_family": "temporal_router_combo",
            "rationale": "The strongest lightweight path is likely semantic atoms plus time-aware routing, not raw search complexity.",
            "parent_baseline": "epi_atom_time",
            "hypothesis_type": "combination",
            "combined_components": ["ATOM", "TIME", "ROUTE"],
            "target_failure_slice": "mixed_history_generalization",
            "online_cost_delta": "small",
            "latency_delta": "small",
            "token_delta": "small",
            "comparison_rule": "Compare against the same atom-plus-time system with no query-aware routing.",
            "keep_if": "Keep only if it improves LongMemEval and does not regress on short-history shadow slices where full context should still be strong.",
        },
        {
            "mutation_id": "mem-003",
            "benchmark": "ConvoMem shadow",
            "component": "evaluation",
            "mutation_family": "abstention_gate",
            "rationale": "The shadow benchmark and LongMemEval both punish over-answering; abstention should be optimized explicitly.",
            "parent_baseline": "epi_atom_time_route",
            "hypothesis_type": "combination",
            "combined_components": ["ATOM", "TIME", "ROUTE", "ABSTAIN"],
            "target_failure_slice": "abstention",
            "online_cost_delta": "none",
            "latency_delta": "none",
            "token_delta": "none",
            "comparison_rule": "Compare against the same retrieval stack without explicit abstention calibration.",
            "keep_if": "Keep only if abstention improves without suppressing too many correct answers.",
        },
        {
            "mutation_id": "mem-004",
            "benchmark": "LoCoMo",
            "component": "retrieval",
            "mutation_family": "relation_expansion_combo",
            "rationale": "Relation expansion is one of the best second-wave additions once the temporal-semantic core is stable.",
            "parent_baseline": "epi_atom_time_profile_route_rehydrate_abstain",
            "hypothesis_type": "combination",
            "combined_components": ["ATOM", "TIME", "PROFILE", "ROUTE", "REHYDRATE", "ABSTAIN", "RELATE"],
            "target_failure_slice": "multi-hop",
            "online_cost_delta": "medium",
            "latency_delta": "small",
            "token_delta": "small",
            "comparison_rule": "Compare against the same stack with relation expansion disabled.",
            "keep_if": "Keep only if multi-hop and temporal LoCoMo slices rise enough to justify the extra retrieval work.",
        },
    ]
