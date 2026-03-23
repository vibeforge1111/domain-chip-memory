from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .contracts import (
    JsonDict,
    NormalizedBenchmarkConfig,
    NormalizedBenchmarkSample,
    NormalizedQuestion,
    NormalizedSession,
    NormalizedTurn,
)


def _normalize_expected_answers(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _sorted_session_keys(conversation: Mapping[str, Any]) -> list[str]:
    session_keys = [
        key
        for key in conversation
        if key.startswith("session_") and not key.endswith("_date_time")
    ]
    return sorted(session_keys, key=lambda key: int(key.split("_")[1]))


class LongMemEvalAdapter:
    benchmark_name = "LongMemEval"

    @classmethod
    def normalize_instance(cls, instance: Mapping[str, Any]) -> NormalizedBenchmarkSample:
        session_ids = list(instance.get("haystack_session_ids", []))
        session_dates = list(instance.get("haystack_dates", []))
        raw_sessions = list(instance.get("haystack_sessions", []))
        sessions: list[NormalizedSession] = []
        evidence_turn_ids: list[str] = []

        for index, raw_session in enumerate(raw_sessions):
            session_id = str(session_ids[index]) if index < len(session_ids) else f"session-{index + 1}"
            session_timestamp = str(session_dates[index]) if index < len(session_dates) else None
            turns: list[NormalizedTurn] = []
            for turn_index, raw_turn in enumerate(raw_session):
                turn_id = f"{session_id}:turn-{turn_index + 1}"
                metadata: JsonDict = {}
                if raw_turn.get("has_answer"):
                    metadata["has_answer"] = True
                    evidence_turn_ids.append(turn_id)
                turns.append(
                    NormalizedTurn(
                        turn_id=turn_id,
                        speaker=str(raw_turn.get("role", "unknown")),
                        text=str(raw_turn.get("content", "")),
                        timestamp=session_timestamp,
                        metadata=metadata,
                    )
                )
            sessions.append(
                NormalizedSession(
                    session_id=session_id,
                    timestamp=session_timestamp,
                    turns=turns,
                    metadata={"source_format": "haystack_session"},
                )
            )

        question_id = str(instance["question_id"])
        question_type = str(instance.get("question_type", "unknown"))
        should_abstain = question_id.endswith("_abs") or question_type == "abstention"
        question = NormalizedQuestion(
            question_id=question_id,
            question=str(instance.get("question", "")),
            category=question_type,
            expected_answers=_normalize_expected_answers(instance.get("answer")),
            evidence_session_ids=[str(item) for item in instance.get("answer_session_ids", [])],
            evidence_turn_ids=evidence_turn_ids,
            question_date=str(instance["question_date"]) if instance.get("question_date") is not None else None,
            should_abstain=should_abstain,
            metadata={"source_format": "longmemeval_instance"},
        )
        return NormalizedBenchmarkSample(
            benchmark_name=cls.benchmark_name,
            sample_id=question_id,
            sessions=sessions,
            questions=[question],
            metadata={"source_format": "longmemeval_instance", "dataset_scope": "question-centric"},
        )


class LoCoMoAdapter:
    benchmark_name = "LoCoMo"

    @classmethod
    def normalize_instance(cls, instance: Mapping[str, Any]) -> NormalizedBenchmarkSample:
        conversation = instance.get("conversation", {})
        session_keys = _sorted_session_keys(conversation)
        sessions: list[NormalizedSession] = []
        dia_to_session: dict[str, str] = {}

        for session_key in session_keys:
            session_timestamp = conversation.get(f"{session_key}_date_time")
            turns: list[NormalizedTurn] = []
            for turn in conversation.get(session_key, []):
                turn_id = str(turn.get("dia_id", f"{session_key}:turn-{len(turns) + 1}"))
                dia_to_session[turn_id] = session_key
                metadata: JsonDict = {}
                for field_name in ("img_url", "blip_caption", "search_query"):
                    if turn.get(field_name) is not None:
                        metadata[field_name] = turn[field_name]
                turns.append(
                    NormalizedTurn(
                        turn_id=turn_id,
                        speaker=str(turn.get("speaker", "unknown")),
                        text=str(turn.get("text", "")),
                        timestamp=str(session_timestamp) if session_timestamp is not None else None,
                        metadata=metadata,
                    )
                )
            sessions.append(
                NormalizedSession(
                    session_id=session_key,
                    timestamp=str(session_timestamp) if session_timestamp is not None else None,
                    turns=turns,
                    metadata={"source_format": "locomo_conversation_session"},
                )
            )

        questions: list[NormalizedQuestion] = []
        for index, qa_item in enumerate(instance.get("qa", [])):
            evidence_turn_ids = [str(item) for item in qa_item.get("evidence", [])]
            evidence_session_ids = sorted(
                {dia_to_session[turn_id] for turn_id in evidence_turn_ids if turn_id in dia_to_session}
            )
            questions.append(
                NormalizedQuestion(
                    question_id=f"{instance.get('sample_id', 'locomo')}-qa-{index + 1}",
                    question=str(qa_item.get("question", "")),
                    category=str(qa_item.get("category", "unknown")),
                    expected_answers=_normalize_expected_answers(qa_item.get("answer")),
                    evidence_session_ids=evidence_session_ids,
                    evidence_turn_ids=evidence_turn_ids,
                    metadata={"source_format": "locomo_qa"},
                )
            )

        return NormalizedBenchmarkSample(
            benchmark_name=cls.benchmark_name,
            sample_id=str(instance.get("sample_id", "locomo-sample")),
            sessions=sessions,
            questions=questions,
            metadata={
                "source_format": "locomo_instance",
                "speaker_a": conversation.get("speaker_a"),
                "speaker_b": conversation.get("speaker_b"),
            },
        )


class GoodAILTMBenchmarkAdapter:
    benchmark_name = "GoodAI LTM Benchmark"

    @classmethod
    def normalize_configuration(
        cls, config_id: str, config_payload: Mapping[str, Any]
    ) -> NormalizedBenchmarkConfig:
        config_block = config_payload.get("config", {})
        datasets_block = config_payload.get("datasets", {})
        shared_args = datasets_block.get("args", {})
        dataset_specs = datasets_block.get("datasets", [])
        dataset_names = [str(item.get("name", "unknown")) for item in dataset_specs]
        return NormalizedBenchmarkConfig(
            benchmark_name=cls.benchmark_name,
            config_id=config_id,
            run_name=str(config_block.get("run_name", config_id)),
            dataset_family_names=dataset_names,
            memory_span_tokens=(
                int(shared_args["memory_span"]) if shared_args.get("memory_span") is not None else None
            ),
            dataset_examples=(
                int(shared_args["dataset_examples"])
                if shared_args.get("dataset_examples") is not None
                else None
            ),
            metadata={
                "source_format": "goodai_config",
                "incompatibilities": config_block.get("incompatibilities", []),
            },
        )

    @classmethod
    def normalize_definition(
        cls,
        definition: Mapping[str, Any],
        *,
        config_id: str,
        run_name: str,
        dataset_name: str,
        definition_id: str,
        memory_span_tokens: int | None = None,
    ) -> NormalizedBenchmarkSample:
        script = [str(item) for item in definition.get("script", [])]
        is_question = [bool(item) for item in definition.get("is_question", [])]
        time_jumps = list(definition.get("time_jumps", []))
        token_spacings = list(definition.get("token_spacings", []))
        expected_responses = _normalize_expected_answers(definition.get("expected_responses"))
        expected_index = 0
        sample_id = f"{config_id}:{dataset_name}:{definition_id}"
        session_id = f"{sample_id}:session-1"
        turns: list[NormalizedTurn] = []
        questions: list[NormalizedQuestion] = []

        for index, text in enumerate(script):
            turn_id = f"{session_id}:turn-{index + 1}"
            turn_metadata: JsonDict = {
                "is_question": is_question[index] if index < len(is_question) else False,
                "time_jump": time_jumps[index] if index < len(time_jumps) else None,
                "token_spacing": token_spacings[index] if index < len(token_spacings) else None,
            }
            turns.append(
                NormalizedTurn(
                    turn_id=turn_id,
                    speaker="benchmark",
                    text=text,
                    metadata=turn_metadata,
                )
            )
            if turn_metadata["is_question"]:
                questions.append(
                    NormalizedQuestion(
                        question_id=f"{sample_id}:q-{len(questions) + 1}",
                        question=text,
                        category=dataset_name.lower().replace(" ", "_"),
                        expected_answers=(
                            [expected_responses[expected_index]]
                            if expected_index < len(expected_responses)
                            else []
                        ),
                        evidence_session_ids=[session_id],
                        evidence_turn_ids=[turn_id],
                        metadata={
                            "source_format": "goodai_definition_question",
                            "dataset_name": dataset_name,
                            "run_name": run_name,
                        },
                    )
                )
                expected_index += 1

        return NormalizedBenchmarkSample(
            benchmark_name=cls.benchmark_name,
            sample_id=sample_id,
            sessions=[
                NormalizedSession(
                    session_id=session_id,
                    turns=turns,
                    metadata={
                        "source_format": "goodai_definition_script",
                        "dataset_name": dataset_name,
                        "config_id": config_id,
                        "memory_span_tokens": memory_span_tokens,
                    },
                )
            ],
            questions=questions,
            metadata={
                "source_format": "goodai_definition",
                "run_name": run_name,
                "config_id": config_id,
                "definition_id": definition_id,
                "dataset_name": dataset_name,
                "memory_span_tokens": memory_span_tokens,
                "uses_callback": bool(definition.get("uses_callback", False)),
                "evaluation_fn": definition.get("evaluation_fn"),
                "can_be_interleaved": bool(definition.get("can_be_interleaved", False)),
                "is_temporal": bool(definition.get("is_temporal", False)),
            },
        )


class ConvoMemShadowAdapter:
    benchmark_name = "ConvoMem"

    @classmethod
    def normalize_instance(cls, instance: Mapping[str, Any]) -> NormalizedBenchmarkSample:
        turns = [
            NormalizedTurn(
                turn_id=f"convomem:{instance.get('sample_id', 'sample')}:turn-{index + 1}",
                speaker=str(turn.get("speaker", "unknown")),
                text=str(turn.get("text", "")),
                metadata={"source_format": "convomem_turn"},
            )
            for index, turn in enumerate(instance.get("conversation", []))
        ]
        question = NormalizedQuestion(
            question_id=str(instance.get("question_id", f"{instance.get('sample_id', 'sample')}:q-1")),
            question=str(instance.get("question", "")),
            category=str(instance.get("category", "unknown")),
            expected_answers=_normalize_expected_answers(instance.get("answer")),
            evidence_session_ids=[],
            evidence_turn_ids=[str(item) for item in instance.get("evidence_turn_ids", [])],
            should_abstain=bool(instance.get("should_abstain", False)),
            metadata={"source_format": "convomem_shadow_question"},
        )
        return NormalizedBenchmarkSample(
            benchmark_name=cls.benchmark_name,
            sample_id=str(instance.get("sample_id", "convomem-sample")),
            sessions=[NormalizedSession(session_id="session-1", turns=turns)],
            questions=[question],
            metadata={"role": "shadow_regression_benchmark"},
        )


def build_adapter_contract_summary() -> JsonDict:
    return {
        "normalized_contracts": [
            "NormalizedBenchmarkConfig",
            "NormalizedBenchmarkSample",
            "NormalizedSession",
            "NormalizedTurn",
            "NormalizedQuestion",
        ],
        "official_benchmark_adapters": [
            {
                "benchmark_name": LongMemEvalAdapter.benchmark_name,
                "entrypoint": "LongMemEvalAdapter.normalize_instance",
                "source_shape": "question-centric dataset instance with timestamped haystack sessions",
            },
            {
                "benchmark_name": LoCoMoAdapter.benchmark_name,
                "entrypoint": "LoCoMoAdapter.normalize_instance",
                "source_shape": "conversation sample with session_N blocks and qa annotations",
            },
            {
                "benchmark_name": GoodAILTMBenchmarkAdapter.benchmark_name,
                "entrypoint": [
                    "GoodAILTMBenchmarkAdapter.normalize_configuration",
                    "GoodAILTMBenchmarkAdapter.normalize_definition",
                ],
                "source_shape": "benchmark harness config plus generated test definition",
            },
        ],
        "shadow_benchmark_adapters": [
            {
                "benchmark_name": ConvoMemShadowAdapter.benchmark_name,
                "entrypoint": "ConvoMemShadowAdapter.normalize_instance",
                "source_shape": "shadow regression sample for preference, changing-fact, and abstention checks",
            }
        ],
    }
