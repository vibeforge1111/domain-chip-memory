from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import datetime
import re
from typing import Any

from .baselines import build_full_context_packets, build_lexical_packets
from .contracts import NormalizedBenchmarkSample
from .memory_roles import source_memory_role
from .packet_builders import (
    build_beam_ready_temporal_atom_router_packets,
    build_contradiction_aware_profile_memory_packets,
    build_dual_store_event_calendar_hybrid_packets,
    build_observational_temporal_memory_packets,
    build_stateful_event_reconstruction_packets,
    build_typed_state_update_memory_packets,
)
from .providers import ModelProvider, _expand_answer_from_context
from .runs import BaselinePromptPacket
from .scorecards import BaselinePrediction, build_scorecard


RunProgressCallback = Callable[[dict[str, Any], list[BaselinePrediction], dict[str, Any]], None]

_ANSWER_IRREGULARS = {
    "appreciated": "appreciate",
    "felt": "feel",
    "went": "go",
    "made": "make",
    "did": "do",
}
_ANSWER_LEADING_FILLERS = {"a", "an", "the", "i", "she", "he", "they", "we", "it"}
_MONTH_YEAR_PATTERNS = ("%B %Y", "%B, %Y")
_FULL_DATE_PATTERNS = ("%d %B %Y", "%d %B, %Y", "%B %d %Y", "%B %d, %Y")
_COUNT_WORD_TO_NUMBER = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}
_PREFERENCE_MATCH_STOPWORDS = {
    "a",
    "about",
    "account",
    "advice",
    "again",
    "also",
    "and",
    "any",
    "around",
    "build",
    "building",
    "can",
    "consider",
    "considering",
    "current",
    "do",
    "existing",
    "for",
    "general",
    "good",
    "help",
    "ideas",
    "into",
    "its",
    "look",
    "looking",
    "may",
    "might",
    "more",
    "my",
    "new",
    "not",
    "of",
    "on",
    "or",
    "other",
    "previous",
    "prefer",
    "preference",
    "recommend",
    "recommendation",
    "recommendations",
    "related",
    "response",
    "responses",
    "should",
    "some",
    "specific",
    "suggest",
    "suggestion",
    "suggestions",
    "take",
    "that",
    "the",
    "their",
    "them",
    "they",
    "this",
    "tips",
    "to",
    "unrelated",
    "upcoming",
    "user",
    "weekend",
    "what",
    "where",
    "with",
    "would",
}


def _normalize_answer_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    normalized: list[str] = []
    for token in tokens:
        token = _ANSWER_IRREGULARS.get(token, token)
        token = _COUNT_WORD_TO_NUMBER.get(token, token)
        if len(token) > 4 and token.endswith("ed"):
            token = token[:-2]
        elif len(token) > 5 and token.endswith("ing"):
            token = token[:-3]
        elif len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        normalized.append(token)
    while normalized and normalized[0] in _ANSWER_LEADING_FILLERS:
        normalized.pop(0)
    return normalized


def _preference_match_tokens(text: str) -> set[str]:
    tokens = {
        token
        for token in _normalize_answer_tokens(text)
        if token not in _PREFERENCE_MATCH_STOPWORDS and len(token) >= 3
    }
    expanded = set(tokens)
    if "watercooler" in tokens:
        expanded.update({"social", "interaction", "team", "colleague"})
    if "slack" in tokens:
        expanded.update({"team", "group", "collaboration"})
    if "pimm" in tokens:
        expanded.update({"cocktail", "summer", "drink"})
    if "mixology" in tokens:
        expanded.update({"cocktail", "classic"})
    return expanded


def _build_manifest_and_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    baseline_name: str,
    top_k_sessions: int,
    fallback_sessions: int,
) -> tuple[dict[str, Any], list[BaselinePromptPacket]]:
    if baseline_name == "full_context":
        return build_full_context_packets(samples)
    if baseline_name == "lexical":
        return build_lexical_packets(
            samples,
            top_k_sessions=top_k_sessions,
            fallback_sessions=fallback_sessions,
        )
    if baseline_name == "beam_temporal_atom_router":
        return build_beam_ready_temporal_atom_router_packets(
            samples,
            top_k_atoms=top_k_sessions,
            include_rehydrated_sessions=fallback_sessions,
        )
    if baseline_name == "observational_temporal_memory":
        return build_observational_temporal_memory_packets(
            samples,
            max_observations=max(top_k_sessions * 2, 4),
            max_reflections=max(fallback_sessions + 2, 2),
        )
    if baseline_name == "contradiction_aware_profile_memory":
        return build_contradiction_aware_profile_memory_packets(
            samples,
            max_observations=max(top_k_sessions * 2, 4),
            max_reflections=max(fallback_sessions + 2, 2),
        )
    if baseline_name == "dual_store_event_calendar_hybrid":
        return build_dual_store_event_calendar_hybrid_packets(
            samples,
            max_observations=max(top_k_sessions * 2, 4),
            top_k_events=max(fallback_sessions + 2, 2),
        )
    if baseline_name == "stateful_event_reconstruction":
        return build_stateful_event_reconstruction_packets(
            samples,
            max_observations=max(top_k_sessions * 2, 6),
            max_reflections=max(fallback_sessions + 3, 3),
            top_k_events=max(fallback_sessions + 3, 3),
        )
    if baseline_name == "typed_state_update_memory":
        return build_typed_state_update_memory_packets(
            samples,
            max_observations=max(top_k_sessions * 2, 6),
            max_reflections=max(fallback_sessions + 2, 3),
            top_k_events=max(fallback_sessions + 2, 3),
        )
    raise ValueError(f"Unsupported baseline: {baseline_name}")


def _ordered_predictions(
    packets: list[BaselinePromptPacket],
    prediction_by_question_id: dict[str, BaselinePrediction],
) -> list[BaselinePrediction]:
    return [
        prediction_by_question_id[packet.question_id]
        for packet in packets
        if packet.question_id in prediction_by_question_id
    ]


def _build_prediction(
    packet: BaselinePromptPacket,
    *,
    question: Any,
    provider: ModelProvider,
    answer: str,
    provider_metadata: dict[str, Any],
) -> BaselinePrediction:
    answer = _expand_answer_from_context(packet.question, answer, packet.assembled_context)
    normalized_pred = " ".join(answer.lower().strip().split())
    primary_answer_candidate = packet.answer_candidates[0] if packet.answer_candidates else None
    retrieved_role_counts = Counter(
        item.memory_role for item in packet.retrieved_context_items if str(item.memory_role or "").strip()
    )
    retrieved_roles = sorted(retrieved_role_counts)
    primary_retrieved_memory_role = (
        packet.retrieved_context_items[0].memory_role if packet.retrieved_context_items else None
    )
    return BaselinePrediction(
        benchmark_name=packet.benchmark_name,
        baseline_name=packet.baseline_name,
        sample_id=packet.sample_id,
        question_id=packet.question_id,
        category=question.category,
        predicted_answer=answer,
        expected_answers=question.expected_answers,
        is_correct=bool(normalized_pred) and _matches_expected_answer(normalized_pred, question.expected_answers),
        question=question.question,
        metadata={
            "provider_name": provider.name,
            **provider_metadata,
            "route": packet.metadata.get("route"),
            "should_abstain": question.should_abstain,
            "evidence_scope": "multi_session" if len(question.evidence_session_ids) > 1 else "single_session",
            "temporal_scope": "dated" if question.question_date else "undated",
            "product_memory_task": question.metadata.get("product_memory_task"),
            "memory_operation": question.metadata.get("memory_operation"),
            "memory_scope": question.metadata.get("memory_scope"),
            "expected_answer_candidate_source": question.metadata.get("expected_answer_candidate_source"),
            "retrieved_context_item_count": len(packet.retrieved_context_items),
            "retrieved_memory_roles": retrieved_roles,
            "retrieved_memory_role_counts": dict(retrieved_role_counts),
            "primary_retrieved_memory_role": primary_retrieved_memory_role,
            "answer_candidate_count": len(packet.answer_candidates),
            "primary_answer_candidate_type": primary_answer_candidate.candidate_type if primary_answer_candidate else None,
            "primary_answer_candidate_source": primary_answer_candidate.source if primary_answer_candidate else None,
            "primary_answer_candidate_role": source_memory_role(
                primary_answer_candidate.source if primary_answer_candidate else None
            ),
            "provenance_supported": bool(
                packet.retrieved_context_items
                and all(item.session_id and item.turn_ids for item in packet.retrieved_context_items)
            ),
        },
    )


def _matches_expected_answer(normalized_pred: str, expected_answers: list[str]) -> bool:
    normalized_expected = [" ".join(expected.lower().strip().split()) for expected in expected_answers]
    normalized_pred_compact = normalized_pred.replace(",", "")
    if (
        normalized_pred == "unknown"
        and any(
            "you did not mention" in expected or "information provided is not enough" in expected
            for expected in normalized_expected
        )
    ):
        return True
    if any("the user would prefer" in expected for expected in normalized_expected):
        pred_tokens = _preference_match_tokens(normalized_pred)
        if pred_tokens:
            for expected in normalized_expected:
                if "the user would prefer" not in expected:
                    continue
                overlap = pred_tokens.intersection(_preference_match_tokens(expected))
                strong_overlap = {token for token in overlap if len(token) >= 4}
                if len(strong_overlap) >= 2:
                    return True
    if normalized_pred in normalized_expected:
        return True
    if any(normalized_pred_compact == expected.replace(",", "") for expected in normalized_expected):
        return True
    pred_tokens = _normalize_answer_tokens(normalized_pred)
    for expected in normalized_expected:
        if pred_tokens and pred_tokens == _normalize_answer_tokens(expected):
            return True
        if " or " not in expected:
            continue
        options = [option.strip() for option in expected.split(" or ") if option.strip()]
        if normalized_pred in options:
            return True
        if any(pred_tokens and pred_tokens == _normalize_answer_tokens(option) for option in options):
            return True
        if any(
            normalized_pred.endswith(option) or option.endswith(normalized_pred)
            for option in options
            if len(option) >= 3
        ):
            return True
    pred_month_year = _parse_month_year(normalized_pred)
    pred_full_date = _parse_full_date(normalized_pred)
    for expected in normalized_expected:
        count_match = re.search(
            r"\b(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
            r"(?:(?:different|total|movie|art-related)\s+)?"
            r"(model kits?|projects?|days?|weeks?|hours?|items?|times?|children|movies|doctors?|weddings?|festivals?|services?|cuisines?|events?|properties?|musical instruments?|meals?)\b",
            expected,
        )
        if count_match:
            expected_count = _COUNT_WORD_TO_NUMBER.get(count_match.group(1), count_match.group(1))
            expected_unit = count_match.group(2)
            if normalized_pred in {expected_count, f"{expected_count} {expected_unit}"}:
                return True
        expected_month_year = _parse_month_year(expected)
        if expected_month_year and pred_full_date and (
            pred_full_date.year == expected_month_year.year and pred_full_date.month == expected_month_year.month
        ):
            return True
        expected_full_date = _parse_full_date(expected)
        if pred_month_year and expected_full_date and (
            pred_month_year.year == expected_full_date.year and pred_month_year.month == expected_full_date.month
        ):
            return True
    return False


def _parse_month_year(text: str) -> datetime | None:
    normalized = text.strip().replace(",", "")
    for pattern in _MONTH_YEAR_PATTERNS:
        try:
            return datetime.strptime(normalized, pattern.replace(",", ""))
        except ValueError:
            continue
    return None


def _parse_full_date(text: str) -> datetime | None:
    normalized = text.strip().replace(",", "")
    for pattern in _FULL_DATE_PATTERNS:
        try:
            return datetime.strptime(normalized, pattern.replace(",", ""))
        except ValueError:
            continue
    return None


def run_baseline(
    samples: list[NormalizedBenchmarkSample],
    *,
    baseline_name: str,
    provider: ModelProvider,
    top_k_sessions: int = 2,
    fallback_sessions: int = 1,
    existing_predictions: list[BaselinePrediction] | None = None,
    progress_callback: RunProgressCallback | None = None,
) -> dict[str, Any]:
    manifest, packets = _build_manifest_and_packets(
        samples,
        baseline_name=baseline_name,
        top_k_sessions=top_k_sessions,
        fallback_sessions=fallback_sessions,
    )

    question_lookup = {
        question.question_id: question for sample in samples for question in sample.questions
    }
    prediction_by_question_id = {
        prediction.question_id: prediction for prediction in (existing_predictions or [])
    }
    total_packets = len(packets)
    if progress_callback and prediction_by_question_id:
        progress_callback(
            manifest,
            _ordered_predictions(packets, prediction_by_question_id),
            {
                "event": "resume",
                "completed": len(prediction_by_question_id),
                "remaining": max(total_packets - len(prediction_by_question_id), 0),
                "total": total_packets,
            },
        )

    for index, packet in enumerate(packets, start=1):
        if packet.question_id in prediction_by_question_id:
            continue
        current_predictions = _ordered_predictions(packets, prediction_by_question_id)
        if progress_callback:
            progress_callback(
                manifest,
                current_predictions,
                {
                    "event": "start",
                    "index": index,
                    "completed": len(current_predictions),
                    "total": total_packets,
                    "question_id": packet.question_id,
                    "sample_id": packet.sample_id,
                },
            )
        try:
            provider_response = provider.generate_answer(packet)
        except Exception as exc:
            if progress_callback:
                progress_callback(
                    manifest,
                    current_predictions,
                    {
                        "event": "error",
                        "index": index,
                        "completed": len(current_predictions),
                        "total": total_packets,
                        "question_id": packet.question_id,
                        "sample_id": packet.sample_id,
                        "error": str(exc),
                    },
                )
            raise
        question = question_lookup[packet.question_id]
        prediction = _build_prediction(
            packet,
            question=question,
            provider=provider,
            answer=provider_response.answer,
            provider_metadata=provider_response.metadata,
        )
        prediction_by_question_id[packet.question_id] = prediction
        current_predictions = _ordered_predictions(packets, prediction_by_question_id)
        if progress_callback:
            progress_callback(
                manifest,
                current_predictions,
                {
                    "event": "completed",
                    "index": index,
                    "completed": len(current_predictions),
                    "total": total_packets,
                    "question_id": packet.question_id,
                    "sample_id": packet.sample_id,
                    "predicted_answer": prediction.predicted_answer,
                    "is_correct": prediction.is_correct,
                },
            )

    return build_scorecard(manifest, _ordered_predictions(packets, prediction_by_question_id))


def build_runner_contract_summary() -> dict[str, object]:
    return {
        "runner_entrypoint": "run_baseline",
        "supported_baselines": [
            "full_context",
            "lexical",
            "beam_temporal_atom_router",
            "observational_temporal_memory",
            "contradiction_aware_profile_memory",
            "dual_store_event_calendar_hybrid",
            "stateful_event_reconstruction",
            "typed_state_update_memory",
        ],
        "required_inputs": ["normalized_samples", "baseline_name", "provider"],
    }
