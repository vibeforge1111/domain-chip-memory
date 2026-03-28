from __future__ import annotations

import json
import re
import subprocess
import sys
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


def run_beam_official_evaluation(
    upstream_repo_dir: str | Path,
    answers_root: str | Path,
    *,
    chat_size: str,
    result_file_name: str = "domain_chip_memory_answers.json",
    start_index: int = 0,
    end_index: int | None = None,
    max_workers: int = 10,
    python_executable: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    upstream_repo_path = Path(upstream_repo_dir)
    answers_root_path = Path(answers_root)
    official_scale_dir = _official_chat_size_dir(chat_size)
    answers_scale_dir = answers_root_path / official_scale_dir

    if start_index < 0:
        raise ValueError("start_index must be non-negative.")
    if end_index is not None and end_index < start_index:
        raise ValueError("end_index must be greater than or equal to start_index.")
    if max_workers <= 0:
        raise ValueError("max_workers must be positive.")

    evaluation_script = upstream_repo_path / "src" / "evaluation" / "run_evaluation.py"
    llm_config = upstream_repo_path / "src" / "llms_config.json"
    chat_scale_dir = upstream_repo_path / "chats" / official_scale_dir
    if not evaluation_script.exists():
        raise ValueError(f"Missing upstream BEAM evaluation script: {evaluation_script}")
    if not llm_config.exists():
        raise ValueError(f"Missing upstream BEAM llm config: {llm_config}")
    if not chat_scale_dir.exists():
        raise ValueError(f"Missing upstream BEAM chats directory for scale {official_scale_dir}: {chat_scale_dir}")
    if not answers_scale_dir.exists():
        raise ValueError(f"Missing answers directory for scale {official_scale_dir}: {answers_scale_dir}")

    answer_conversation_dirs = sorted(
        [path for path in answers_scale_dir.iterdir() if path.is_dir()],
        key=lambda path: int(path.name) if path.name.isdigit() else path.name,
    )
    if not answer_conversation_dirs:
        raise ValueError(f"No conversation directories found in {answers_scale_dir}")

    missing_result_files = [
        path.name for path in answer_conversation_dirs if not (path / result_file_name).exists()
    ]
    if missing_result_files:
        raise ValueError(
            "Missing BEAM answer files for result export: "
            + ", ".join(f"{conversation}/{result_file_name}" for conversation in missing_result_files)
        )

    missing_probing_questions = [
        path.name
        for path in answer_conversation_dirs
        if not (chat_scale_dir / path.name / "probing_questions" / "probing_questions.json").exists()
    ]
    if missing_probing_questions:
        raise ValueError(
            "Missing upstream probing questions for conversations: " + ", ".join(missing_probing_questions)
        )

    effective_end_index = len(answer_conversation_dirs) if end_index is None else end_index
    if effective_end_index > len(answer_conversation_dirs):
        raise ValueError(
            f"end_index={effective_end_index} exceeds available conversation count {len(answer_conversation_dirs)}."
        )

    command = [
        python_executable or sys.executable,
        "src/evaluation/run_evaluation.py",
        "--input_directory",
        str(answers_scale_dir),
        "--chat_size",
        official_scale_dir,
        "--start_index",
        str(start_index),
        "--end_index",
        str(effective_end_index),
        "--max_workers",
        str(max_workers),
        "--allowed_result_files",
        result_file_name,
    ]

    selected_conversations = answer_conversation_dirs[start_index:effective_end_index]
    payload: dict[str, Any] = {
        "benchmark_name": "BEAM",
        "source_mode": "official_public_upstream_eval",
        "official_chat_size_dir": official_scale_dir,
        "requested_chat_size": str(chat_size).strip().upper(),
        "upstream_repo_dir": str(upstream_repo_path),
        "answers_root": str(answers_root_path),
        "input_directory": str(answers_scale_dir),
        "result_file_name": result_file_name,
        "start_index": start_index,
        "end_index": effective_end_index,
        "max_workers": max_workers,
        "conversation_count": len(selected_conversations),
        "conversation_ids": [path.name for path in selected_conversations],
        "command": command,
        "cwd": str(upstream_repo_path),
        "llm_config_file": str(llm_config),
        "dry_run": dry_run,
    }
    if dry_run:
        payload["status"] = "validated"
        return payload

    completed = subprocess.run(
        command,
        cwd=str(upstream_repo_path),
        capture_output=True,
        text=True,
        check=False,
    )
    evaluation_files = [
        str(path / f"evaluation-{result_file_name}")
        for path in selected_conversations
        if (path / f"evaluation-{result_file_name}").exists()
    ]
    payload.update(
        {
            "status": "completed" if completed.returncode == 0 else "failed",
            "exit_code": int(completed.returncode),
            "stdout_tail": completed.stdout.splitlines()[-20:],
            "stderr_tail": completed.stderr.splitlines()[-20:],
            "evaluation_files": evaluation_files,
        }
    )
    return payload
