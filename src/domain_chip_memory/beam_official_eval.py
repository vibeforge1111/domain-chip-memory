from __future__ import annotations

import json
import multiprocessing
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import importlib
from pathlib import Path
from functools import partial
from typing import Any

from langchain_openai import ChatOpenAI

from .providers import DEFAULT_MINIMAX_BASE_URL, DEFAULT_OPENAI_BASE_URL


_BEAM_SAMPLE_ID_PATTERN = re.compile(r"^beam-([^-]+)-(.+)$")
_BEAM_OPENAI_COMPATIBLE_REQUEST_TIMEOUT_SECONDS = 60
_BEAM_OPENAI_COMPATIBLE_MAX_RETRIES = 2


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
    payload = _load_beam_evaluation_payload(evaluation_path)
    summary = _summarize_beam_evaluation_payload(payload)
    summary["evaluation_file"] = str(Path(evaluation_path))
    return summary


def summarize_beam_official_evaluation_files(evaluation_files: list[str | Path]) -> dict[str, Any]:
    merged_payload: dict[str, list[dict[str, Any]]] = defaultdict(list)
    normalized_files = [str(Path(path)) for path in evaluation_files]
    for path in evaluation_files:
        payload = _load_beam_evaluation_payload(path)
        for category, items in payload.items():
            if not isinstance(items, list):
                continue
            merged_payload[category].extend(item for item in items if isinstance(item, dict))
    summary = _summarize_beam_evaluation_payload(merged_payload)
    summary["evaluation_files"] = normalized_files
    summary["evaluation_file_count"] = len(normalized_files)
    return summary


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
    judge_provider: str = "minimax",
    judge_model: str | None = None,
    judge_base_url: str | None = None,
    judge_api_key_env: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    upstream_repo_path = Path(upstream_repo_dir).resolve()
    answers_root_path = Path(answers_root).resolve()
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

    judge_config = _resolve_beam_judge_config(
        judge_provider=judge_provider,
        judge_model=judge_model,
        judge_base_url=judge_base_url,
        judge_api_key_env=judge_api_key_env,
    )
    command = _beam_evaluation_command(
        python_executable=python_executable or sys.executable,
        answers_scale_dir=answers_scale_dir,
        official_scale_dir=official_scale_dir,
        start_index=start_index,
        end_index=effective_end_index,
        max_workers=max_workers,
        result_file_name=result_file_name,
        judge_config=judge_config,
    )

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
        "judge_config": {
            key: value
            for key, value in judge_config.items()
            if key not in {"api_key"}
        },
        "dry_run": dry_run,
    }
    if dry_run:
        payload["status"] = "validated"
        return payload

    if judge_config["mode"] == "official_upstream_openai":
        completed = subprocess.run(
            command,
            cwd=str(upstream_repo_path),
            capture_output=True,
            text=True,
            check=False,
        )
        exit_code = int(completed.returncode)
        stdout_tail = completed.stdout.splitlines()[-20:]
        stderr_tail = completed.stderr.splitlines()[-20:]
    else:
        result = _run_openai_compatible_upstream_evaluation(
            upstream_repo_path=upstream_repo_path,
            answers_scale_dir=answers_scale_dir,
            official_scale_dir=official_scale_dir,
            start_index=start_index,
            end_index=effective_end_index,
            max_workers=max_workers,
            result_file_name=result_file_name,
            judge_config=judge_config,
        )
        exit_code = int(result["exit_code"])
        stdout_tail = result["stdout_tail"]
        stderr_tail = result["stderr_tail"]
        evaluation_files = result.get("evaluation_files", [])

    if judge_config["mode"] == "official_upstream_openai":
        evaluation_files = [
            str(path / f"evaluation-{result_file_name}")
            for path in selected_conversations
            if (path / f"evaluation-{result_file_name}").exists()
        ]
    expected_evaluation_files = [
        str(path / f"evaluation-{result_file_name}")
        for path in selected_conversations
    ]
    missing_evaluation_files = [
        path for path in expected_evaluation_files if path not in set(evaluation_files)
    ]
    aggregate_summary = summarize_beam_official_evaluation_files(evaluation_files) if evaluation_files else None
    payload.update(
        {
            "status": (
                "completed"
                if exit_code == 0 and not missing_evaluation_files and evaluation_files
                else "partial"
                if evaluation_files
                else "failed"
            ),
            "exit_code": exit_code,
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
            "evaluation_files": evaluation_files,
            "missing_evaluation_files": missing_evaluation_files,
            "aggregate_summary": aggregate_summary,
        }
    )
    return payload


def _resolve_beam_judge_config(
    *,
    judge_provider: str,
    judge_model: str | None,
    judge_base_url: str | None,
    judge_api_key_env: str | None,
) -> dict[str, Any]:
    normalized = str(judge_provider or "minimax").strip().lower()
    if normalized == "official_openai":
        return {
            "mode": "official_upstream_openai",
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "base_url": DEFAULT_OPENAI_BASE_URL,
            "api_key_source": "upstream_llms_config.json",
            "comparability": "exact_official_upstream_judge_path",
        }
    if normalized == "minimax":
        env_name = judge_api_key_env or "MINIMAX_API_KEY"
        api_key = os.getenv(env_name)
        if not api_key:
            raise ValueError(f"{env_name} must be set to use the MiniMax judge path.")
        model = (
            judge_model
            or os.getenv("DOMAIN_CHIP_MEMORY_MINIMAX_MODEL")
            or os.getenv("MINIMAX_MODEL")
        )
        if not model:
            raise ValueError(
                "MiniMax judge path requires --judge-model or DOMAIN_CHIP_MEMORY_MINIMAX_MODEL or MINIMAX_MODEL."
            )
        base_url = (
            judge_base_url
            or os.getenv("DOMAIN_CHIP_MEMORY_MINIMAX_BASE_URL")
            or os.getenv("MINIMAX_BASE_URL")
            or DEFAULT_MINIMAX_BASE_URL
        )
        return {
            "mode": "openai_compatible_override",
            "provider": "minimax",
            "model": model,
            "base_url": base_url,
            "api_key_env": env_name,
            "api_key": api_key,
            "comparability": "alternate_openai_compatible_judge_not_exact_official",
        }
    raise ValueError(f"Unsupported BEAM judge provider: {judge_provider}")


def _beam_evaluation_command(
    *,
    python_executable: str,
    answers_scale_dir: Path,
    official_scale_dir: str,
    start_index: int,
    end_index: int,
    max_workers: int,
    result_file_name: str,
    judge_config: dict[str, Any],
) -> list[str]:
    if judge_config["mode"] != "official_upstream_openai":
        return [
            python_executable,
            "<in-process-openai-compatible-judge>",
            judge_config["provider"],
            judge_config["model"],
        ]
    return [
        python_executable,
        "-m",
        "src.evaluation.run_evaluation",
        "--input_directory",
        str(answers_scale_dir),
        "--chat_size",
        official_scale_dir,
        "--start_index",
        str(start_index),
        "--end_index",
        str(end_index),
        "--max_workers",
        str(max_workers),
        "--allowed_result_files",
        result_file_name,
    ]


def _run_openai_compatible_upstream_evaluation(
    *,
    upstream_repo_path: Path,
    answers_scale_dir: Path,
    official_scale_dir: str,
    start_index: int,
    end_index: int,
    max_workers: int,
    result_file_name: str,
    judge_config: dict[str, Any],
) -> dict[str, Any]:
    selected_conversation_ids = sorted(
        [
            path.name
            for path in answers_scale_dir.iterdir()
            if path.is_dir()
        ],
        key=lambda name: int(name) if name.isdigit() else name,
    )[start_index:end_index]
    expected_outputs = [
        answers_scale_dir / conversation_id / f"evaluation-{result_file_name}"
        for conversation_id in selected_conversation_ids
    ]

    ctx = multiprocessing.get_context("spawn")
    result_queue: multiprocessing.Queue[dict[str, Any]] = ctx.Queue()
    worker = ctx.Process(
        target=_run_openai_compatible_evaluation_worker,
        args=(
            str(upstream_repo_path),
            str(answers_scale_dir),
            official_scale_dir,
            selected_conversation_ids,
            result_file_name,
            judge_config,
            result_queue,
        ),
    )
    worker.start()

    stdout_lines = [f"Started MiniMax BEAM evaluation worker for {len(selected_conversation_ids)} conversations."]
    deadline_seconds = max(900, 180 * max(1, len(selected_conversation_ids)))
    start_time_seconds = time.monotonic()
    logged_incremental_write_warning = False
    while worker.is_alive():
        completed_outputs = [str(path) for path in expected_outputs if path.exists()]
        if len(completed_outputs) == len(expected_outputs) and not logged_incremental_write_warning:
            logged_incremental_write_warning = True
            stdout_lines.append(
                "All expected evaluation files were detected; waiting for worker exit because upstream writes them incrementally."
            )
        if time.monotonic() - start_time_seconds > deadline_seconds:
            worker.terminate()
            worker.join(timeout=10)
            completed_outputs = [str(path) for path in expected_outputs if path.exists()]
            return {
                "exit_code": 1,
                "stdout_tail": stdout_lines[-20:],
                "stderr_tail": [
                    f"Timed out waiting for MiniMax BEAM evaluation worker after {deadline_seconds} seconds."
                ],
                "evaluation_files": completed_outputs,
            }
        time.sleep(1.0)

    worker.join(timeout=10)
    completed_outputs = [str(path) for path in expected_outputs if path.exists()]
    worker_payload: dict[str, Any] = {}
    if not result_queue.empty():
        worker_payload = result_queue.get()
    stdout_lines.extend(worker_payload.get("stdout_tail", []))
    stderr_lines = worker_payload.get("stderr_tail", [])
    exit_code = int(worker_payload.get("exit_code", 1 if worker.exitcode else 0))
    return {
        "exit_code": exit_code,
        "stdout_tail": stdout_lines[-20:],
        "stderr_tail": stderr_lines[-20:],
        "evaluation_files": completed_outputs,
    }


def _resume_openai_compatible_single_conversation_evaluation(
    *,
    probing_questions_address: Path,
    answers_file: Path,
    output_file: Path,
    model: Any,
    compute_metrics_module: Any,
    run_evaluation_module: Any,
) -> None:
    answers_payload = json.loads(answers_file.read_text(encoding="utf-8"))
    if not isinstance(answers_payload, dict):
        raise ValueError(f"Expected BEAM answers payload to be an object: {answers_file}")

    existing_payload: dict[str, Any] = {}
    if output_file.exists():
        try:
            loaded_existing_payload = json.loads(output_file.read_text(encoding="utf-8"))
            if isinstance(loaded_existing_payload, dict):
                existing_payload = loaded_existing_payload
        except json.JSONDecodeError:
            existing_payload = {}

    category_evaluators = {
        "abstention": getattr(compute_metrics_module, "evaluate_abstention", None),
        "contradiction_resolution": getattr(compute_metrics_module, "evaluate_contradiction_resolution", None),
        "event_ordering": getattr(compute_metrics_module, "evaluate_event_ordering", None),
        "information_extraction": getattr(compute_metrics_module, "evaluate_information_extraction", None),
        "instruction_following": getattr(compute_metrics_module, "evaluate_instruction_following", None),
        "knowledge_update": getattr(compute_metrics_module, "evaluate_knowledge_update", None),
        "multi_session_reasoning": getattr(compute_metrics_module, "evaluate_multi_session_reasoning", None),
        "preference_following": getattr(compute_metrics_module, "evaluate_preference_following", None),
        "summarization": getattr(compute_metrics_module, "evaluate_summarization", None),
        "temporal_reasoning": getattr(compute_metrics_module, "evaluate_temporal_reasoning", None),
    }

    for category, questions in answers_payload.items():
        if category in existing_payload and existing_payload.get(category):
            print(f"Skipping completed question type: {category}")
            continue
        if category not in category_evaluators:
            continue
        if not isinstance(questions, list):
            continue

        print(f"Question Type: {category}")
        category_rows = []
        evaluator = category_evaluators[category]
        for index, question in enumerate(questions):
            print(f"Question Index: {index}")
            rubric = run_evaluation_module.get_rubric(
                probing_questions_address=str(probing_questions_address),
                key=category,
                index=index,
            )
            llm_response = str(question.get("llm_response", ""))
            probing_question = str(question.get("question", ""))
            result = evaluator(
                rubric=rubric,
                llm_response=llm_response,
                probing_question=probing_question,
                model=model,
            )
            category_rows.append(result)

        existing_payload[category] = category_rows
        output_file.write_text(json.dumps(existing_payload, indent=4), encoding="utf-8")


def _load_beam_evaluation_payload(evaluation_path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(evaluation_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("BEAM official evaluation summary expected a JSON object.")
    return payload


def _run_openai_compatible_evaluation_worker(
    upstream_repo_dir: str,
    answers_scale_dir: str,
    official_scale_dir: str,
    conversation_ids: list[str],
    result_file_name: str,
    judge_config: dict[str, Any],
    result_queue: multiprocessing.Queue,
) -> None:
    upstream_repo_path = Path(upstream_repo_dir)
    answers_scale_path = Path(answers_scale_dir)
    upstream_repo_str = str(upstream_repo_path)
    original_cwd = os.getcwd()
    inserted_path = False
    original_hf_hub_offline = os.environ.get("HF_HUB_OFFLINE")
    original_transformers_offline = os.environ.get("TRANSFORMERS_OFFLINE")
    stdout_buffer = StringIO()
    stderr_buffer = StringIO()
    module_names = (
        "src.llm",
        "src.evaluation.compute_metrics",
        "src.evaluation.run_evaluation",
    )
    try:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        if not sys.path or sys.path[0] != upstream_repo_str:
            sys.path.insert(0, upstream_repo_str)
            inserted_path = True
        for module_name in module_names:
            sys.modules.pop(module_name, None)
        os.chdir(upstream_repo_str)
        compute_metrics_module = importlib.import_module("src.evaluation.compute_metrics")
        run_evaluation_module = importlib.import_module("src.evaluation.run_evaluation")
        compute_metrics_module.SentenceTransformer = partial(
            compute_metrics_module.SentenceTransformer,
            local_files_only=True,
        )
        judge_llm = ChatOpenAI(
            model=judge_config["model"],
            openai_api_key=judge_config["api_key"],
            openai_api_base=judge_config["base_url"],
            temperature=0,
            request_timeout=_BEAM_OPENAI_COMPATIBLE_REQUEST_TIMEOUT_SECONDS,
            max_retries=_BEAM_OPENAI_COMPATIBLE_MAX_RETRIES,
        )
        failures: list[str] = []
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            compute_metrics_module.initialize_models()
            run_evaluation_module.initialize_models = lambda: None
            for conversation_id in conversation_ids:
                result_file_address = answers_scale_path / conversation_id / result_file_name
                output_address = answers_scale_path / conversation_id / f"evaluation-{result_file_name}"
                probing_question_address = (
                    upstream_repo_path
                    / "chats"
                    / official_scale_dir
                    / conversation_id
                    / "probing_questions"
                    / "probing_questions.json"
                )
                try:
                    print(f"************ Result File: {result_file_name}")
                    _resume_openai_compatible_single_conversation_evaluation(
                        probing_questions_address=probing_question_address,
                        answers_file=result_file_address,
                        output_file=output_address,
                        model=judge_llm,
                        compute_metrics_module=compute_metrics_module,
                        run_evaluation_module=run_evaluation_module,
                    )
                except Exception as exc:
                    failures.append(f"{conversation_id}: {type(exc).__name__}: {exc}")
        stderr_lines = stderr_buffer.getvalue().splitlines()
        stderr_lines.extend(failures)
        result_queue.put(
            {
                "exit_code": 0 if not failures else 1,
                "stdout_tail": stdout_buffer.getvalue().splitlines()[-20:],
                "stderr_tail": stderr_lines[-20:],
            }
        )
    except Exception as exc:
        stderr_lines = stderr_buffer.getvalue().splitlines()
        stderr_lines.append(f"{type(exc).__name__}: {exc}")
        result_queue.put(
            {
                "exit_code": 1,
                "stdout_tail": stdout_buffer.getvalue().splitlines()[-20:],
                "stderr_tail": stderr_lines[-20:],
            }
        )
    finally:
        os.chdir(original_cwd)
        if original_hf_hub_offline is None:
            os.environ.pop("HF_HUB_OFFLINE", None)
        else:
            os.environ["HF_HUB_OFFLINE"] = original_hf_hub_offline
        if original_transformers_offline is None:
            os.environ.pop("TRANSFORMERS_OFFLINE", None)
        else:
            os.environ["TRANSFORMERS_OFFLINE"] = original_transformers_offline
        for module_name in module_names:
            sys.modules.pop(module_name, None)
        if inserted_path and sys.path and sys.path[0] == upstream_repo_str:
            sys.path.pop(0)


def _summarize_beam_evaluation_payload(payload: dict[str, Any]) -> dict[str, Any]:
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
        "category_count": total_categories,
        "overall_average": round(total_score / total_categories, 4) if total_categories else 0.0,
        "categories": category_rows,
    }
