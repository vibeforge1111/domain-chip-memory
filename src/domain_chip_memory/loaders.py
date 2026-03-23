from __future__ import annotations

import json
import re
from pathlib import Path

from .adapters import GoodAILTMBenchmarkAdapter, LoCoMoAdapter, LongMemEvalAdapter
from .contracts import NormalizedBenchmarkConfig, NormalizedBenchmarkSample


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_longmemeval_json(path: str | Path, *, limit: int | None = None) -> list[NormalizedBenchmarkSample]:
    payload = _load_json(Path(path))
    if not isinstance(payload, list):
        raise ValueError("LongMemEval loader expected a JSON list of instances.")
    instances = payload[:limit] if limit is not None else payload
    return [LongMemEvalAdapter.normalize_instance(instance) for instance in instances]


def load_locomo_json(path: str | Path, *, limit: int | None = None) -> list[NormalizedBenchmarkSample]:
    payload = _load_json(Path(path))
    if not isinstance(payload, list):
        raise ValueError("LoCoMo loader expected a JSON list of conversation samples.")
    instances = payload[:limit] if limit is not None else payload
    return [LoCoMoAdapter.normalize_instance(instance) for instance in instances]


def _parse_published_goodai_yaml(path: Path) -> dict:
    run_name: str | None = None
    memory_span: int | None = None
    dataset_examples: int | None = None
    dataset_names: list[str] = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("run_name:"):
            run_name = stripped.split(":", 1)[1].strip().strip('"').strip("'")
        elif stripped.startswith("memory_span:"):
            memory_span = int(stripped.split(":", 1)[1].strip())
        elif stripped.startswith("dataset_examples:"):
            dataset_examples = int(stripped.split(":", 1)[1].strip())
        else:
            match = re.match(r'-\s+name:\s*["\']?(.+?)["\']?$', stripped)
            if match:
                dataset_names.append(match.group(1))

    return {
        "config": {"run_name": run_name or path.stem, "incompatibilities": []},
        "datasets": {
            "args": {
                "memory_span": memory_span,
                "dataset_examples": dataset_examples,
            },
            "datasets": [{"name": name} for name in dataset_names],
        },
    }


def load_goodai_config(path: str | Path) -> NormalizedBenchmarkConfig:
    config_path = Path(path)
    if config_path.suffix.lower() == ".json":
        payload = _load_json(config_path)
    else:
        payload = _parse_published_goodai_yaml(config_path)
    return GoodAILTMBenchmarkAdapter.normalize_configuration(config_path.name, payload)


def load_goodai_definitions(
    definitions_dir: str | Path,
    *,
    config: NormalizedBenchmarkConfig,
    dataset_name: str | None = None,
    limit: int | None = None,
) -> list[NormalizedBenchmarkSample]:
    root = Path(definitions_dir)
    if dataset_name:
        files = sorted((root / dataset_name).glob("*.def.json"))
    else:
        files = sorted(root.glob("*/*.def.json"))
    if limit is not None:
        files = files[:limit]

    samples: list[NormalizedBenchmarkSample] = []
    for file_path in files:
        payload = _load_json(file_path)
        samples.append(
            GoodAILTMBenchmarkAdapter.normalize_definition(
                payload,
                config_id=config.config_id,
                run_name=config.run_name,
                dataset_name=file_path.parent.name,
                definition_id=file_path.name,
                memory_span_tokens=config.memory_span_tokens,
            )
        )
    return samples


def build_loader_contract_summary() -> dict[str, object]:
    return {
        "loaders": [
            {
                "benchmark_name": "LongMemEval",
                "entrypoint": "load_longmemeval_json",
                "required_input": "path to released JSON file such as longmemeval_s_cleaned.json",
            },
            {
                "benchmark_name": "LoCoMo",
                "entrypoint": "load_locomo_json",
                "required_input": "path to locomo10.json",
            },
            {
                "benchmark_name": "GoodAI LTM Benchmark",
                "entrypoint": ["load_goodai_config", "load_goodai_definitions"],
                "required_input": "path to a published config plus a definitions directory",
            },
        ]
    }
