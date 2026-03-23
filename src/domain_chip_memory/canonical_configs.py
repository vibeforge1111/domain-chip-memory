from __future__ import annotations


CANONICAL_CONFIGS = [
    {
        "benchmark_name": "GoodAI LTM Benchmark",
        "config_id": "benchmark-v3-32k.yml",
        "status": "initial_canonical_config",
        "rationale": (
            "Program inference: 32k is the first serious long-span setting that remains practical "
            "for early reproducible baseline loops. 1k is too weak, while 120k+ is better suited "
            "for later stress promotion."
        ),
        "next_configs": ["benchmark-v3-120k.yml", "benchmark-v3-500k.yml"],
        "source_url": "https://github.com/GoodAI/goodai-ltm-benchmark",
    }
]


def get_canonical_configs() -> list[dict]:
    return CANONICAL_CONFIGS
