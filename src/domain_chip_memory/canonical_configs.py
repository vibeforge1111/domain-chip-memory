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
    },
    {
        "benchmark_name": "BEAM",
        "config_id": "beam_local_pilot_v1_source.json",
        "status": "initial_local_pilot_slice",
        "rationale": (
            "Program inference: until the official BEAM implementation surface is pinned, the repo needs "
            "one explicit paper-pinned local slice to exercise adapter, scorecard, abstention, and "
            "multi-session pressure without pretending it is full benchmark reproduction."
        ),
        "next_configs": [
            "beam_local_pilot_v2_source.json",
            "beam_local_pilot_v3_source.json",
            "beam_local_pilot_v4_source.json",
            "beam_local_pilot_v5_source.json",
            "beam_local_pilot_v6_source.json",
            "beam_local_pilot_v7_source.json",
            "beam_local_pilot_v8_source.json",
            "beam_local_pilot_v9_source.json",
            "beam_local_pilot_v10_source.json",
            "beam_local_pilot_v11_source.json",
            "beam_local_pilot_v12_source.json",
            "beam_local_pilot_v13_source.json",
            "beam_local_pilot_v14_source.json",
            "beam_local_pilot_v15_source.json",
            "beam_local_pilot_v16_source.json",
            "beam_local_pilot_v17_source.json",
            "beam_local_pilot_v18_source.json",
            "official_beam_slice_once_pinned",
        ],
        "source_url": "https://arxiv.org/abs/2510.27246",
    }
]


def get_canonical_configs() -> list[dict]:
    return CANONICAL_CONFIGS
