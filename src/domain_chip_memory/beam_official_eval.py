from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


_BEAM_SAMPLE_ID_PATTERN = re.compile(r"^beam-([^-]+)-(.+)$")


def _official_chat_size_dir(scale: str) -> str:
    normalized = str(scale).strip().upper()
    aliases = {
        "128K": "100K",
        "100K": "100K",
        "500K": "500K",
        "1M": "1M",
        "10M": "10M",
    }
    if normalized not in aliases:
        raise ValueError(f"Unsupported BEAM dataset scale: {scale}")
    return aliases[normalized]


def _parse_beam_sample_id(sample_id: str) -> tuple[str, str]:
    match = _BEAM_SAMPLE_ID_PATTERN.match(str(sample_id).strip())
    if not match:
        raise ValueError(f"Unrecognized BEAM sample_id format: {sample_id}")
    return match.group(1).upper(), match.group(2)


def export_beam_public_answers_from_scorecard(
    scorecard_path: str | Path,
    output_root: str | Path,
    *,
    result_file_name: str = "domain_chip_memory_answers.json",
) -> dict[str, Any]:
    payload = json.loads(Path(scorecard_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("BEAM scorecard export expected a JSON object.")

    run_manifest = payload.get("run_manifest", {})
    if not isinstance(run_manifest, dict) or run_manifest.get("benchmark_name") != "BEAM":
        raise ValueError("BEAM scorecard export requires a BEAM run_manifest.")
    manifest_metadata = run_manifest.get("metadata", {})
    if not isinstance(manifest_metadata, dict):
        manifest_metadata = {}
    source_modes = manifest_metadata.get("source_modes", [])
    if source_modes and "official_public" not in source_modes:
        raise ValueError("BEAM scorecard export only supports official_public BEAM runs.")

    raw_predictions = payload.get("predictions", [])
    if not isinstance(raw_predictions, list):
        raise ValueError("BEAM scorecard export expected a predictions list.")

    grouped_predictions: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for item in raw_predictions:
        if not isinstance(item, dict):
            continue
        sample_id = str(item.get("sample_id", "")).strip()
        category = str(item.get("category", "")).strip()
        question = str(item.get("question", "") or item.get("metadata", {}).get("question", "")).strip()
        llm_response = str(item.get("predicted_answer", "")).strip()
        if not sample_id or not category or not question:
            continue
        scale, conversation_id = _parse_beam_sample_id(sample_id)
        grouped_predictions[(scale, conversation_id)][category].append(
            {
                "question": question,
                "llm_response": llm_response,
                "question_id": item.get("question_id"),
                "predicted_answer": item.get("predicted_answer"),
            }
        )

    output_root_path = Path(output_root)
    written_files = []
    for (scale, conversation_id), by_category in grouped_predictions.items():
        conversation_dir = output_root_path / _official_chat_size_dir(scale) / conversation_id
        conversation_dir.mkdir(parents=True, exist_ok=True)
        output_path = conversation_dir / result_file_name
        ordered_payload = {category: rows for category, rows in by_category.items()}
        output_path.write_text(json.dumps(ordered_payload, indent=2) + "\n", encoding="utf-8")
        written_files.append(
            {
                "dataset_scale": scale,
                "conversation_id": conversation_id,
                "output_file": str(output_path),
                "category_count": len(ordered_payload),
                "question_count": sum(len(rows) for rows in ordered_payload.values()),
            }
        )

    return {
        "benchmark_name": "BEAM",
        "source_mode": "official_public",
        "result_file_name": result_file_name,
        "conversation_count": len(written_files),
        "written_files": written_files,
    }


def summarize_beam_official_evaluation(evaluation_path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(evaluation_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("BEAM official evaluation summary expected a JSON object.")

    category_rows = []
    total_score = 0.0
    total_categories = 0
    for category, items in payload.items():
        if not isinstance(items, list) or not items:
            continue
        if category == "event_ordering":
            metric_name = "tau_norm"
            values = [float(item.get("tau_norm", 0.0)) for item in items if isinstance(item, dict)]
        else:
            metric_name = "llm_judge_score"
            values = [float(item.get("llm_judge_score", 0.0)) for item in items if isinstance(item, dict)]
        if not values:
            continue
        average_score = sum(values) / len(values)
        category_rows.append(
            {
                "category": category,
                "metric": metric_name,
                "question_count": len(values),
                "average_score": round(average_score, 4),
            }
        )
        total_score += average_score
        total_categories += 1

    category_rows.sort(key=lambda row: row["category"])
    return {
        "benchmark_name": "BEAM",
        "source_mode": "official_public_evaluation",
        "evaluation_file": str(Path(evaluation_path)),
        "category_count": total_categories,
        "overall_average": round(total_score / total_categories, 4) if total_categories else 0.0,
        "categories": category_rows,
    }
