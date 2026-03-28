from __future__ import annotations

import json
import re
from pathlib import Path

from .adapters import BEAMAdapter, GoodAILTMBenchmarkAdapter, LoCoMoAdapter, LongMemEvalAdapter
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


def load_beam_json(path: str | Path, *, limit: int | None = None) -> list[NormalizedBenchmarkSample]:
    payload = _load_json(Path(path))
    if not isinstance(payload, list):
        raise ValueError("BEAM loader expected a JSON list of local slice instances.")
    instances = payload[:limit] if limit is not None else payload
    return [BEAMAdapter.normalize_instance(instance) for instance in instances]


def _beam_public_scale_dir_name(chat_size: str) -> str:
    normalized = str(chat_size).strip().upper()
    aliases = {
        "128K": "100K",
        "100K": "100K",
        "500K": "500K",
        "1M": "1M",
        "10M": "10M",
    }
    if normalized not in aliases:
        raise ValueError(f"Unsupported BEAM chat size: {chat_size}")
    return aliases[normalized]


def _beam_public_expected_answers(question_payload: dict[str, object]) -> list[str]:
    for field_name in ("answer", "ideal_answer", "ideal_response"):
        value = question_payload.get(field_name)
        if isinstance(value, str) and value.strip():
            return [value.strip()]
    rubric = question_payload.get("rubric")
    if isinstance(rubric, list):
        answers = [str(item).strip() for item in rubric if str(item).strip()]
        if answers:
            return answers
    return []


def _load_beam_public_conversation(
    conversation_dir: Path,
    *,
    chat_size: str,
    upstream_commit: str | None,
) -> NormalizedBenchmarkSample:
    chat_payload = _load_json(conversation_dir / "chat.json")
    probing_payload = _load_json(conversation_dir / "probing_questions" / "probing_questions.json")
    if not isinstance(chat_payload, list):
        raise ValueError(f"BEAM public chat file must contain a list: {conversation_dir / 'chat.json'}")
    if not isinstance(probing_payload, dict):
        raise ValueError(
            f"BEAM public probing questions file must contain an object: {conversation_dir / 'probing_questions' / 'probing_questions.json'}"
        )

    sessions = []
    message_id_to_refs: dict[str, tuple[str, str]] = {}
    for batch_index, batch in enumerate(chat_payload, start=1):
        if not isinstance(batch, dict):
            continue
        session_id = f"{conversation_dir.name}:batch-{batch_index}"
        session_turns = []
        turn_counter = 0
        for turn_group in batch.get("turns", []):
            if not isinstance(turn_group, list):
                continue
            for message in turn_group:
                if not isinstance(message, dict):
                    continue
                turn_counter += 1
                raw_message_id = message.get("id")
                turn_id = (
                    f"{session_id}:msg-{raw_message_id}"
                    if raw_message_id is not None
                    else f"{session_id}:turn-{turn_counter}"
                )
                session_turns.append(
                    {
                        "turn_id": turn_id,
                        "speaker": str(message.get("role", "unknown")),
                        "text": str(message.get("content", "")),
                        "timestamp": str(message.get("time_anchor")) if message.get("time_anchor") is not None else None,
                        "metadata": {
                            key: value
                            for key, value in {
                                "message_id": raw_message_id,
                                "index": message.get("index"),
                                "question_type": message.get("question_type"),
                            }.items()
                            if value is not None
                        },
                    }
                )
                if raw_message_id is not None:
                    message_id_to_refs[str(raw_message_id)] = (session_id, turn_id)
        sessions.append(
            {
                "session_id": session_id,
                "timestamp": str(batch.get("time_anchor")) if batch.get("time_anchor") is not None else None,
                "turns": session_turns,
                "metadata": {
                    key: value
                    for key, value in {
                        "batch_number": batch.get("batch_number"),
                        "time_anchor": batch.get("time_anchor"),
                    }.items()
                    if value is not None
                },
            }
        )

    questions = []
    question_counter = 0
    for category, items in probing_payload.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            question_counter += 1
            source_chat_ids = item.get("source_chat_ids", [])
            if not isinstance(source_chat_ids, list):
                source_chat_ids = []
            evidence_turn_ids = []
            evidence_session_ids = []
            for raw_chat_id in source_chat_ids:
                ref = message_id_to_refs.get(str(raw_chat_id))
                if not ref:
                    continue
                session_id, turn_id = ref
                if turn_id not in evidence_turn_ids:
                    evidence_turn_ids.append(turn_id)
                if session_id not in evidence_session_ids:
                    evidence_session_ids.append(session_id)
            expected_answers = _beam_public_expected_answers(item)
            should_abstain = str(category).strip().lower() == "abstention"
            questions.append(
                {
                    "question_id": f"{conversation_dir.name}:{category}:{question_counter}",
                    "question": str(item.get("question", "")),
                    "answer": expected_answers,
                    "category": str(category),
                    "evidence_session_ids": evidence_session_ids,
                    "evidence_turn_ids": evidence_turn_ids,
                    "should_abstain": should_abstain,
                    "metadata": {
                        key: value
                        for key, value in {
                            "difficulty": item.get("difficulty"),
                            "conversation_references": item.get("conversation_references"),
                            "source_chat_ids": source_chat_ids,
                            "official_question_type": item.get("question_type"),
                        }.items()
                        if value not in (None, [], "")
                    },
                }
            )

    return BEAMAdapter.normalize_instance(
        {
            "sample_id": f"beam-{chat_size.lower()}-{conversation_dir.name}",
            "sessions": sessions,
            "questions": questions,
            "metadata": {
                "source_format": "beam_official_public_conversation",
                "source_mode": "official_public",
                "slice_status": "official_public_commit_pinned",
                "dataset_scale": chat_size,
                "conversation_id": conversation_dir.name,
                **({"upstream_commit": upstream_commit} if upstream_commit else {}),
            },
        }
    )


def load_beam_public_dir(
    root_dir: str | Path,
    *,
    chat_size: str,
    limit: int | None = None,
    upstream_commit: str | None = None,
) -> list[NormalizedBenchmarkSample]:
    root = Path(root_dir)
    scale_dir = root / _beam_public_scale_dir_name(chat_size)
    if not scale_dir.exists():
        raise ValueError(f"BEAM public scale directory does not exist: {scale_dir}")
    conversation_dirs = sorted(path for path in scale_dir.iterdir() if path.is_dir())
    if limit is not None:
        conversation_dirs = conversation_dirs[:limit]
    return [
        _load_beam_public_conversation(
            conversation_dir,
            chat_size=chat_size,
            upstream_commit=upstream_commit,
        )
        for conversation_dir in conversation_dirs
    ]


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
            {
                "benchmark_name": "BEAM",
                "entrypoint": "load_beam_json",
                "required_input": "path to an internal BEAM local-slice JSON; official public BEAM reproduction still needs a separate loader path",
            },
            {
                "benchmark_name": "BEAM",
                "entrypoint": "load_beam_public_dir",
                "required_input": "path to an unpacked official-public BEAM chats directory plus a chat size such as 128K, 500K, 1M, or 10M",
            },
        ]
    }
