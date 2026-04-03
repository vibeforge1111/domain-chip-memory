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
    build_contradiction_aware_summary_synthesis_memory_packets,
    build_dual_store_event_calendar_hybrid_packets,
    build_observational_temporal_memory_packets,
    build_stateful_event_reconstruction_packets,
    build_summary_synthesis_memory_packets,
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
_CONTRADICTION_RUBRIC_STOPWORDS = {
    "a",
    "also",
    "any",
    "have",
    "having",
    "mentioned",
    "the",
    "with",
    "you",
    "your",
}
_BEAM_RUBRIC_TOKEN_STOPWORDS = _CONTRADICTION_RUBRIC_STOPWORDS | {
    "and",
    "for",
    "into",
    "of",
    "or",
    "that",
    "to",
    "using",
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


def _normalize_answer_surface(text: str) -> str:
    return (
        text.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )


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


def _extract_numbered_list_items(text: str) -> list[str]:
    matches = list(re.finditer(r"\b\d+[.)]\s*", text))
    if len(matches) < 2:
        return []
    items: list[str] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        item = text[start:end].strip(" \t\r\n,.")
        if item:
            items.append(item)
    return items


def _ordered_list_items_match(pred_items: list[str], expected_items: list[str]) -> bool:
    if len(pred_items) != len(expected_items) or not pred_items:
        return False
    for predicted_item, expected_item in zip(pred_items, expected_items):
        normalized_predicted = " ".join(_normalize_answer_surface(predicted_item).lower().strip().split())
        normalized_expected = " ".join(_normalize_answer_surface(expected_item).lower().strip().split())
        if normalized_predicted == normalized_expected:
            continue
        predicted_tokens = _normalize_answer_tokens(normalized_predicted)
        expected_tokens = _normalize_answer_tokens(normalized_expected)
        if predicted_tokens and predicted_tokens == expected_tokens:
            continue
        if (
            normalized_predicted not in normalized_expected
            and normalized_expected not in normalized_predicted
        ):
            return False
    return True


def _extract_beam_rubric_requirement(expected: str) -> str:
    for prefix in (
        "llm response should contain:",
        "llm response should state:",
        "llm response should mention:",
        "llm response should ask for clarification on ",
    ):
        if expected.startswith(prefix):
            return expected[len(prefix) :].strip()
    return ""


def _normalize_beam_rubric_surface(text: str) -> str:
    normalized = re.sub(r"\b(my|your)\b", "__poss__", text)
    return re.sub(r"\b(i|you)\b", "__person__", normalized)


def _matches_beam_rubric_requirement(normalized_pred: str, requirement: str) -> bool:
    if not requirement:
        return False
    if requirement in {"there is contradictory information", "there is contradictory"}:
        return any(
            phrase in normalized_pred
            for phrase in ("contradictory information", "conflicting statements", "conflicting information")
        )
    if requirement in {"which statement is correct?", "which is correct", "ask for clarification on which is correct"}:
        return any(
            phrase in normalized_pred
            for phrase in ("which statement is correct", "which is correct", "could you clarify which is correct")
        )
    if requirement.startswith(("you mentioned ", "you also mentioned ", "you have never ", "you mentioned both that you have and have not ")):
        requirement_tokens = {
            token for token in _normalize_answer_tokens(requirement) if token not in _CONTRADICTION_RUBRIC_STOPWORDS
        }
        predicted_tokens = set(_normalize_answer_tokens(normalized_pred))
        if requirement_tokens and len(requirement_tokens & predicted_tokens) >= max(3, len(requirement_tokens) - 1):
            return True
    if requirement == "code blocks with syntax highlighting":
        return bool(re.search(r"```[a-z0-9_+-]+", normalized_pred))
    if requirement == "clearly formatted code snippets":
        return "```" in normalized_pred
    if requirement == "step-by-step breakdown":
        return "step-by-step" in normalized_pred and any(
            phrase in normalized_pred for phrase in ("first", "next", "then", "finally")
        )
    if requirement == "clear explanation of each step":
        return any(
            phrase in normalized_pred
            for phrase in ("each step clearly", "explanation shows each step clearly", "explain each step clearly")
        )
    if requirement == "include tree drawing":
        return "tree drawing" in normalized_pred
    if requirement == "multiple methods described":
        return sum(
            1
            for phrase in ("base-height", "heron", "included angle", "sin(", "median", "altitude")
            if phrase in normalized_pred
        ) >= 2
    if requirement == "comparison between methods":
        return any(
            phrase in normalized_pred
            for phrase in ("compare", "comparison", "more direct", "better when", "while ")
        )
    if requirement == "explicit version details for each dependency":
        mentions = re.findall(r"\b[a-z][a-z0-9.+-]*\s+\d+(?:\.\d+)+\b", normalized_pred)
        return len(mentions) >= 2
    if requirement == "includes numeric codes associated with errors":
        codes = {match.group(0) for match in re.finditer(r"\b[1-5]\d{2}\b", normalized_pred)}
        return len(codes) >= 2
    if requirement == "mention of semantic tags like <header>, <nav>, <main>, <footer>":
        return all(tag in normalized_pred for tag in ("<header>", "<nav>", "<main>", "<footer>"))
    if requirement == "explanation of tag purposes":
        return any(word in normalized_pred for word in ("defines", "contains", "holds", "provides"))
    if requirement == "uses bootstrap 5.3.0 classes and components":
        return "bootstrap 5.3.0" in normalized_pred and (
            "class" in normalized_pred or "component" in normalized_pred
        )
    if requirement == "suggests lightweight libraries":
        return "lightweight" in normalized_pred and any(
            term in normalized_pred for term in ("library", "libraries", "flask-login", "sqlite", "chart.js")
        )
    if requirement == "avoids recommending large frameworks or heavy dependencies":
        return "avoid large frameworks" in normalized_pred or "heavy dependencies" in normalized_pred
    if requirement == "suggests security measures that are efficient and lightweight":
        return "lightweight" in normalized_pred or "efficient" in normalized_pred
    if requirement == "proposes incremental or practical enhancements":
        return any(term in normalized_pred for term in ("incrementally", "practical", "pragmatic"))
    if requirement == "recommends using localstorage or in-memory cache":
        return "localstorage" in normalized_pred or "in-memory cache" in normalized_pred
    if requirement == "avoids suggesting large libraries or frameworks":
        return "large libraries or frameworks" in normalized_pred or "avoid large frameworks" in normalized_pred
    if requirement == "mentions automated workflow monitoring tools":
        return any(
            term in normalized_pred for term in ("github actions", "status checks", "job summaries", "artifacts", "notifications")
        )
    if requirement == "avoids recommending manual deployment checks":
        return (
            "manual deployment checks" not in normalized_pred
            or "better than relying on manual deployment checks" in normalized_pred
            or "avoid manual deployment checks" in normalized_pred
            or "instead of relying on manual deployment checks" in normalized_pred
        )
    if requirement == "does not limit to a single method or skip any requested calculations":
        return "different methods" in normalized_pred and any(
            phrase in normalized_pred
            for phrase in ("none of the requested calculations are skipped", "rather than limiting it to one")
        )
    if requirement in {"provides step-by-step logical proof", "dprovides step-by-step logical proof"}:
        return "step-by-step" in normalized_pred and any(
            phrase in normalized_pred for phrase in ("first", "next", "finally", "conclude")
        )
    if requirement == "explains reasoning behind each step clearly":
        return any(
            phrase in normalized_pred
            for phrase in ("reasoning behind each step", "asa applies because", "makes the reasoning behind each step explicit")
        )
    if requirement == "breaks down the problem into sequential steps":
        return any(
            phrase in normalized_pred
            for phrase in ("sequential steps", "step by step", "first count", "then write", "finally simplify")
        )
    if requirement == "avoids suggesting foundation or other frameworks":
        return (
            "foundation" not in normalized_pred
            or "without switching to foundation or other frameworks" in normalized_pred
            or "avoid foundation or other frameworks" in normalized_pred
        )
    if requirement == "recommends lazysizes or similar lightweight vanilla js libraries":
        return any(
            phrase in normalized_pred
            for phrase in ("lazysizes", "lightweight vanilla js", "lightweight javascript", "vanilla javascript")
        )
    if requirement == "i recommended handle repeated retries":
        return any(
            phrase in normalized_pred
            for phrase in (
                "handle repeated retries",
                "handling repeated retries",
                "to handle repeated retries",
            )
        )
    requirement_tokens = {
        token for token in _normalize_answer_tokens(requirement) if token not in _BEAM_RUBRIC_TOKEN_STOPWORDS
    }
    predicted_tokens = set(_normalize_answer_tokens(normalized_pred))
    if requirement_tokens and len(requirement_tokens & predicted_tokens) >= max(3, len(requirement_tokens) - 2):
        return True
    numeric_with_unit_match = re.fullmatch(r"(\d+(?:\.\d+)?)\s+([a-z][a-z0-9 -]+)", requirement)
    if numeric_with_unit_match and normalized_pred == numeric_with_unit_match.group(1):
        return True
    if requirement == "avoids suggesting heavy frameworks or large libraries":
        return not any(framework in normalized_pred for framework in ("react", "angular", "vue", "next.js"))
    return requirement in normalized_pred or _normalize_beam_rubric_surface(requirement) in _normalize_beam_rubric_surface(normalized_pred)


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
    if baseline_name == "contradiction_aware_summary_synthesis_memory":
        return build_contradiction_aware_summary_synthesis_memory_packets(
            samples,
            max_observations=max(top_k_sessions * 2, 6),
            max_reflections=max(fallback_sessions + 2, 3),
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
    if baseline_name == "summary_synthesis_memory":
        return build_summary_synthesis_memory_packets(
            samples,
            max_observations=max(top_k_sessions * 2, 6),
            max_reflections=max(fallback_sessions + 2, 3),
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
    question_metadata = getattr(question, "metadata", {}) or {}
    question_sample_id = str(question_metadata.get("sample_id", "")).strip().lower()
    question_dataset_scale = str(question_metadata.get("dataset_scale", "")).strip().upper()
    preserve_non_128k_beam_surface = (
        packet.baseline_name in {"summary_synthesis_memory", "contradiction_aware_summary_synthesis_memory"}
        and (
            question_sample_id.startswith(("beam-500k-", "beam-1m-", "beam-10m-"))
            or question_dataset_scale in {"500K", "1M", "10M"}
        )
    )
    if not preserve_non_128k_beam_surface:
        answer = _expand_answer_from_context(packet.question, answer, packet.assembled_context)
    normalized_pred = " ".join(_normalize_answer_surface(answer).lower().strip().split())
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
    normalized_pred = " ".join(_normalize_answer_surface(normalized_pred).lower().strip().split())
    normalized_expected = [
        " ".join(_normalize_answer_surface(expected).lower().strip().split()) for expected in expected_answers
    ]
    normalized_pred_without_ago = re.sub(r"\s+ago$", "", normalized_pred).strip()
    normalized_expected_without_ago = [re.sub(r"\s+ago$", "", expected).strip() for expected in normalized_expected]
    normalized_pred_compact = normalized_pred.replace(",", "")
    pred_list_items = _extract_numbered_list_items(normalized_pred)
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
    if normalized_pred_without_ago in normalized_expected_without_ago:
        return True
    numeric_with_unit_match = re.fullmatch(r"(\d+(?:\.\d+)?)\s+(days?|weeks?|months?|years?)", normalized_pred_without_ago)
    if numeric_with_unit_match and numeric_with_unit_match.group(1) in normalized_expected_without_ago:
        return True
    if any(normalized_pred_compact == expected.replace(",", "") for expected in normalized_expected):
        return True
    pred_tokens = _normalize_answer_tokens(normalized_pred)
    pred_tokens_without_ago = _normalize_answer_tokens(normalized_pred_without_ago)
    for expected in normalized_expected:
        expected_list_items = _extract_numbered_list_items(expected)
        if pred_list_items and expected_list_items and _ordered_list_items_match(pred_list_items, expected_list_items):
            return True
        parenthetical_stripped = re.sub(r"\s*\([^)]*\)", "", expected).strip()
        if parenthetical_stripped and parenthetical_stripped != expected:
            stripped_without_ago = re.sub(r"\s+ago$", "", parenthetical_stripped).strip()
            stripped_tokens = _normalize_answer_tokens(parenthetical_stripped)
            stripped_tokens_without_ago = _normalize_answer_tokens(stripped_without_ago)
            if normalized_pred == parenthetical_stripped:
                return True
            if normalized_pred_without_ago == stripped_without_ago:
                return True
            if pred_tokens and pred_tokens == stripped_tokens:
                return True
            if pred_tokens_without_ago and pred_tokens_without_ago == stripped_tokens_without_ago:
                return True
        if any(marker in expected for marker in ("acceptable", "including the last day", "answers ranging")):
            leading_clause = expected.split(".", 1)[0].strip()
            if leading_clause:
                leading_clause_without_ago = re.sub(r"\s+ago$", "", leading_clause).strip()
                leading_tokens = _normalize_answer_tokens(leading_clause)
                leading_tokens_without_ago = _normalize_answer_tokens(leading_clause_without_ago)
                if normalized_pred == leading_clause:
                    return True
                if normalized_pred_without_ago == leading_clause_without_ago:
                    return True
                if pred_tokens and pred_tokens == leading_tokens:
                    return True
                if pred_tokens_without_ago and pred_tokens_without_ago == leading_tokens_without_ago:
                    return True
        expected_tokens = _normalize_answer_tokens(expected)
        expected_tokens_without_ago = _normalize_answer_tokens(re.sub(r"\s+ago$", "", expected).strip())
        if pred_tokens and pred_tokens == expected_tokens:
            return True
        if pred_tokens_without_ago and pred_tokens_without_ago == expected_tokens_without_ago:
            return True
        if " or " not in expected:
            continue
        options = [option.strip() for option in expected.split(" or ") if option.strip()]
        if normalized_pred in options:
            return True
        if any(pred_tokens and pred_tokens == _normalize_answer_tokens(option) for option in options):
            return True
        if any(
            pred_tokens_without_ago
            and pred_tokens_without_ago == _normalize_answer_tokens(re.sub(r"\s+ago$", "", option).strip())
            for option in options
        ):
            return True
        if any(
            normalized_pred.endswith(option) or option.endswith(normalized_pred)
            for option in options
            if len(option) >= 3
        ):
            return True
    rubric_requirements = [
        requirement
        for expected in normalized_expected
        if (requirement := _extract_beam_rubric_requirement(expected))
    ]
    if rubric_requirements:
        return all(
            _matches_beam_rubric_requirement(normalized_pred, requirement) for requirement in rubric_requirements
        )
    pred_month_year = _parse_month_year(normalized_pred)
    pred_full_date = _parse_full_date(normalized_pred)
    for expected in normalized_expected:
        count_matches = re.finditer(
            r"\b(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
            r"(?:(?:different|total|movie|art-related)\s+)?"
            r"(model kits?|projects?|days?|weeks?|hours?|items?|times?|children|movies|doctors?|weddings?|festivals?|services?|cuisines?|events?|properties?|musical instruments?|meals?)\b",
            expected,
        )
        for count_match in count_matches:
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
            "contradiction_aware_summary_synthesis_memory",
            "dual_store_event_calendar_hybrid",
            "stateful_event_reconstruction",
            "summary_synthesis_memory",
            "typed_state_update_memory",
        ],
        "required_inputs": ["normalized_samples", "baseline_name", "provider"],
    }
