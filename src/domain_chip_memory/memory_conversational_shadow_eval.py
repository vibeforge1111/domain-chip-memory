from __future__ import annotations

import re
from typing import Any

from .answer_candidates import build_answer_candidate
from .baselines import build_lexical_packets
from .contracts import JsonDict, NormalizedBenchmarkSample, NormalizedQuestion
from .memory_conversational_index import build_conversational_index
from .memory_conversational_retrieval import _entry_score, retrieve_conversational_entries, retrieve_entity_linked_entries
from .memory_extraction import _tokenize
from .packet_builders import build_summary_synthesis_memory_packets
from .providers import get_provider
from .runner import _build_prediction
from .runs import BaselinePromptPacket, RetrievedContextItem, build_run_manifest
from .scorecards import _normalize_answer
from .typed_temporal_graph_memory import build_typed_temporal_graph_memory
from .typed_temporal_graph_retrieval import TypedTemporalGraphHit, retrieve_typed_temporal_graph_hits


_COVERAGE_STOPWORDS = {
    "a",
    "an",
    "and",
    "at",
    "for",
    "from",
    "her",
    "his",
    "in",
    "it",
    "me",
    "my",
    "of",
    "on",
    "our",
    "the",
    "their",
    "to",
    "with",
}

_KINSHIP_TOKENS = {
    "mother",
    "mom",
    "father",
    "dad",
    "friend",
    "friends",
    "partner",
    "husband",
    "wife",
    "sister",
    "brother",
    "family",
}

_SUPPORT_TOKENS = {
    "grief",
    "grieving",
    "helped",
    "peace",
    "support",
    "supported",
    "comfort",
    "comforting",
}

_EXACT_TURN_PREFIXES = (
    "who ",
    "where ",
    "when ",
    "which ",
    "how many ",
    "is ",
    "are ",
    "do ",
    "does ",
    "did ",
    "can ",
)

_EXACT_TURN_WHAT_KEYWORDS = {
    "activity",
    "activities",
    "area",
    "attend",
    "attended",
    "class",
    "classes",
    "city",
    "country",
    "dream",
    "dreams",
    "engines",
    "go to",
    "go with",
    "hobby",
    "hobbies",
    "instrument",
    "instruments",
    "live",
    "lives",
    "located",
    "location",
    "married",
    "own",
    "owned",
    "owns",
    "pet",
    "pets",
    "play",
    "plays",
    "resume",
    "resumed",
    "test",
    "tests",
    "view",
    "views",
    "visit",
    "visiting",
    "went with",
    "work",
    "works",
}


def _coverage_tokens(text: str) -> set[str]:
    return {
        token
        for token in _tokenize(_normalize_answer(text))
        if token not in _COVERAGE_STOPWORDS
    }


def _expected_answer_coverage(text: str, expected_answers: list[str]) -> bool:
    haystack = _normalize_answer(text)
    haystack_tokens = _coverage_tokens(text)
    if not haystack or not expected_answers:
        return False
    for expected in expected_answers:
        normalized_expected = _normalize_answer(expected)
        if normalized_expected and normalized_expected in haystack:
            return True
        expected_tokens = _coverage_tokens(expected)
        if expected_tokens and expected_tokens.issubset(haystack_tokens):
            return True
        segments = [
            segment.strip()
            for segment in re.split(r",| and ", normalized_expected)
            if segment.strip()
        ]
        if segments:
            segment_ok = True
            for segment in segments:
                segment_tokens = _coverage_tokens(segment)
                if not segment_tokens:
                    continue
                if not segment_tokens.issubset(haystack_tokens):
                    segment_ok = False
                    break
            if segment_ok:
                return True
    return False


def _question_uses_conversational_hybrid(question: NormalizedQuestion) -> bool:
    question_lower = question.question.lower()
    if any(token in question_lower for token in _KINSHIP_TOKENS):
        return True
    if any(token in question_lower for token in _SUPPORT_TOKENS):
        return True
    if any(phrase in question_lower for phrase in ("both have in common", "shared interests", "share in common", "relationship")):
        return True
    if any(token in question_lower for token in ("hobby", "hobbies", "memory", "memories", "remember")) and any(
        token in question_lower for token in _KINSHIP_TOKENS
    ):
        return True
    return False


def _question_prefers_exact_conversational_evidence(question: NormalizedQuestion) -> bool:
    question_lower = question.question.lower()
    if question_lower.startswith(_EXACT_TURN_PREFIXES):
        return True
    if question_lower.startswith("what "):
        return any(token in question_lower for token in _EXACT_TURN_WHAT_KEYWORDS)
    return False


def _question_prefers_typed_graph_evidence(question: NormalizedQuestion) -> bool:
    question_lower = question.question.lower()
    if "nickname" in question_lower:
        return True
    if question_lower.startswith("what did ") and any(token in question_lower for token in ("say", "said", "tell", "told")):
        return True
    if any(token in question_lower for token in ("remember", "know", "sure")):
        return True
    if question_lower.startswith("when ") and any(
        token in question_lower for token in ("going to", "conference", "pass away", "passed away")
    ):
        return True
    if any(token in question_lower for token in ("ever", "before")) and any(
        token in question_lower for token in ("tried", "been", "visited", "had")
    ):
        return True
    if any(token in question_lower for token in ("peace", "support", "grieving", "comfort")):
        return True
    return False


def _question_prefers_entity_linked_evidence(question: NormalizedQuestion) -> bool:
    question_lower = question.question.lower()
    if "nickname" in question_lower or "call" in question_lower:
        return True
    if any(token in question_lower for token in ("remember", "know", "sure")):
        return True
    if any(token in question_lower for token in ("ever", "before")) and any(
        token in question_lower for token in ("tried", "been", "visited", "had")
    ):
        return True
    return False


def _fused_shadow_selector(question: NormalizedQuestion) -> str:
    question_lower = question.question.lower()
    if question_lower.startswith("what did ") and any(token in question_lower for token in ("say", "said", "tell", "told")):
        return "typed_graph_first"
    if _question_prefers_entity_linked_evidence(question):
        return "entity_linked_first"
    if _question_prefers_exact_conversational_evidence(question):
        return "exact_turn_first"
    if _question_prefers_typed_graph_evidence(question):
        return "typed_graph_first"
    return "summary_backbone"


def question_uses_fused_conversational_shadow(question: NormalizedQuestion) -> bool:
    return _fused_shadow_selector(question) != "summary_backbone"


def _conversational_entry_to_retrieved_context_item(
    question: NormalizedQuestion,
    entry: Any,
    *,
    strategy: str = "exact_turn_conversational_shadow",
) -> RetrievedContextItem:
    return RetrievedContextItem(
        session_id=entry.session_id,
        turn_ids=[entry.turn_id],
        score=_entry_score(question, entry),
        strategy=strategy,
        text=f"conversational_evidence: {entry.text}",
        memory_role="evidence",
        metadata={
            "entry_type": entry.entry_type,
            "predicate": entry.predicate,
            "subject": entry.subject,
            "timestamp": entry.timestamp,
            **entry.metadata,
        },
    )


def _entry_answer_candidate_text(question: NormalizedQuestion, entry: Any) -> str:
    question_lower = question.question.lower()
    predicate = str(getattr(entry, "predicate", "")).strip().lower()
    metadata = getattr(entry, "metadata", {}) or {}
    if predicate == "alias_binding":
        if "nickname" in question_lower or "call" in question_lower:
            return str(metadata.get("alias", "")).strip()
        return ""
    if predicate == "reported_speech":
        if question_lower.startswith("what did ") and any(token in question_lower for token in ("say", "said", "tell", "told")):
            return str(metadata.get("source_span", "")).strip() or str(metadata.get("reported_content", "")).strip()
        return ""
    if predicate == "negation_record" and (
        question_lower.startswith(("is ", "are ", "do ", "does ", "did ", "can ", "has ", "have ", "had "))
        or " before" in question_lower
        or "ever " in question_lower
    ):
        return "No"
    if predicate == "unknown_record":
        if question_lower.startswith(("is ", "are ", "do ", "does ", "did ", "can ", "has ", "have ", "had ")):
            return "No"
        return "unknown"
    if predicate in {"relationship_mention", "loss_event", "gift_event", "support_event"} and question_lower.startswith(("who ", "what ", "when ")):
        return str(metadata.get("source_span", "")).strip()
    return ""


def _entity_linked_answer_candidates(
    question: NormalizedQuestion,
    entries: list[Any],
    summary_candidates: list[Any],
) -> list[Any]:
    merged_candidates: list[Any] = []
    seen_text: set[str] = set()
    for entry in entries:
        answer_text = _entry_answer_candidate_text(question, entry)
        if not answer_text:
            continue
        normalized = answer_text.strip().lower()
        if not normalized or normalized in seen_text:
            continue
        seen_text.add(normalized)
        merged_candidates.append(
            build_answer_candidate(
                question.question,
                answer_text,
                source="evidence_memory",
                metadata={
                    "source_kind": "entity_linked_conversational",
                    "predicate": getattr(entry, "predicate", ""),
                    "entry_id": getattr(entry, "entry_id", ""),
                },
            )
        )
    for candidate in summary_candidates:
        normalized = candidate.text.strip().lower()
        if not normalized or normalized in seen_text:
            continue
        seen_text.add(normalized)
        merged_candidates.append(candidate)
    return merged_candidates


def _exact_turn_answer_candidates(
    question: NormalizedQuestion,
    entries: list[Any],
    summary_candidates: list[Any],
) -> list[Any]:
    merged_candidates: list[Any] = []
    seen_text: set[str] = set()
    for entry in entries:
        answer_text = _entry_answer_candidate_text(question, entry)
        if not answer_text:
            continue
        normalized = answer_text.strip().lower()
        if not normalized or normalized in seen_text:
            continue
        seen_text.add(normalized)
        merged_candidates.append(
            build_answer_candidate(
                question.question,
                answer_text,
                source="evidence_memory",
                metadata={
                    "source_kind": "exact_turn_conversational",
                    "predicate": getattr(entry, "predicate", ""),
                    "entry_id": getattr(entry, "entry_id", ""),
                },
            )
        )
    for candidate in summary_candidates:
        normalized = candidate.text.strip().lower()
        if not normalized or normalized in seen_text:
            continue
        seen_text.add(normalized)
        merged_candidates.append(candidate)
    return merged_candidates


def _merge_retrieved_context_items(
    summary_items: list[RetrievedContextItem],
    conversational_items: list[RetrievedContextItem],
) -> list[RetrievedContextItem]:
    merged: list[RetrievedContextItem] = []
    seen_keys: set[tuple[str, tuple[str, ...], str]] = set()
    for item in [*summary_items, *conversational_items]:
        dedupe_key = (item.session_id, tuple(item.turn_ids), item.text.strip().lower())
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        merged.append(item)
    return merged


def _ordered_shadow_context_blocks(
    *,
    shadow_items: list[RetrievedContextItem],
    summary_items: list[RetrievedContextItem],
    answer_candidate_text: str | None,
) -> tuple[list[RetrievedContextItem], list[str]]:
    ordered_items = _merge_retrieved_context_items(shadow_items, summary_items)
    context_blocks = [item.text for item in ordered_items]
    if not shadow_items and answer_candidate_text:
        context_blocks.append(f"answer_candidate: {answer_candidate_text}")
    return ordered_items, context_blocks


def _graph_hit_to_retrieved_context_item(hit: TypedTemporalGraphHit) -> RetrievedContextItem:
    return RetrievedContextItem(
        session_id=str(hit.metadata.get("session_id", "")),
        turn_ids=[str(hit.metadata.get("turn_id", ""))] if str(hit.metadata.get("turn_id", "")).strip() else [],
        score=hit.score,
        strategy="typed_temporal_graph_shadow",
        text=f"graph_evidence: {hit.text}",
        memory_role="structured_evidence",
        metadata={**hit.metadata, "hit_type": hit.hit_type},
    )


def _graph_hit_answer_candidate_text(question: NormalizedQuestion, hit: TypedTemporalGraphHit) -> str:
    question_lower = question.question.lower()
    if hit.hit_type == "alias_binding":
        return str(hit.metadata.get("alias", "")).strip()
    if hit.hit_type == "reported_speech_record":
        return (
            str(hit.metadata.get("source_span", "")).strip()
            or hit.text.strip()
            or str(hit.metadata.get("reported_content", "")).strip()
        )
    if hit.hit_type in {"commitment_record", "temporal_event"} and question_lower.startswith("when "):
        return str(hit.metadata.get("time_normalized", "")).strip()
    if hit.hit_type == "relationship_fact" and question_lower.startswith(("who ", "what ")):
        return str(hit.metadata.get("object_label", "")).strip()
    if hit.hit_type == "negation_record" and (
        question_lower.startswith(("is ", "are ", "do ", "does ", "did ", "can ", "has ", "have ", "had "))
        or " before" in question_lower
        or "ever " in question_lower
    ):
        return "No"
    if hit.hit_type == "unknown_record":
        return "unknown"
    return ""


def _typed_graph_answer_candidates(
    question: NormalizedQuestion,
    graph_hits: list[TypedTemporalGraphHit],
    summary_candidates: list[Any],
) -> list[Any]:
    merged_candidates: list[Any] = []
    seen_text: set[str] = set()
    for hit in graph_hits:
        answer_text = _graph_hit_answer_candidate_text(question, hit)
        if not answer_text:
            continue
        normalized = answer_text.strip().lower()
        if not normalized or normalized in seen_text:
            continue
        seen_text.add(normalized)
        merged_candidates.append(
            build_answer_candidate(
                question.question,
                answer_text,
                source="evidence_memory",
                metadata={
                    "source_kind": "typed_temporal_graph",
                    "hit_type": hit.hit_type,
                    "hit_id": hit.hit_id,
                },
            )
        )
    for candidate in summary_candidates:
        normalized = candidate.text.strip().lower()
        if not normalized or normalized in seen_text:
            continue
        seen_text.add(normalized)
        merged_candidates.append(candidate)
    return merged_candidates


def _typed_graph_summary_fallback_items(
    question: NormalizedQuestion,
    summary_items: list[RetrievedContextItem],
    graph_hits: list[TypedTemporalGraphHit],
) -> list[RetrievedContextItem]:
    if not graph_hits or not _question_prefers_typed_graph_evidence(question):
        return summary_items
    if any(
        hit.hit_type in {"alias_binding", "reported_speech_record", "unknown_record", "negation_record"}
        for hit in graph_hits
    ):
        return []
    filtered_items = [
        item
        for item in summary_items
        if not item.text.lower().startswith(("synthesis:", "reflection:"))
    ]
    return filtered_items or summary_items


def build_exact_turn_hybrid_shadow_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    conversational_limit: int = 8,
) -> tuple[JsonDict, list[BaselinePromptPacket]]:
    manifest, summary_packets = build_summary_synthesis_memory_packets(samples)
    packet_by_question_id = {packet.question_id: packet for packet in summary_packets}
    hybrid_packets: list[BaselinePromptPacket] = []

    for sample in samples:
        index_entries = build_conversational_index(sample)
        for question in sample.questions:
            summary_packet = packet_by_question_id[question.question_id]
            hybrid_retrieved_items = list(summary_packet.retrieved_context_items)
            conversational_retrieved_items: list[RetrievedContextItem] = []
            conversational_hits: list[Any] = []
            if _question_prefers_exact_conversational_evidence(question):
                conversational_hits = retrieve_conversational_entries(
                    question,
                    index_entries,
                    limit=conversational_limit,
                )
                conversational_retrieved_items = [
                    _conversational_entry_to_retrieved_context_item(question, entry)
                    for entry in conversational_hits
                ]
            hybrid_retrieved_items, hybrid_context_blocks = _ordered_shadow_context_blocks(
                shadow_items=conversational_retrieved_items,
                summary_items=list(summary_packet.retrieved_context_items),
                answer_candidate_text=summary_packet.answer_candidates[0].text if summary_packet.answer_candidates else None,
            )
            answer_candidates = list(summary_packet.answer_candidates)
            if question.question.lower().startswith("when "):
                answer_candidates = _exact_turn_answer_candidates(
                    question,
                    conversational_hits,
                    list(summary_packet.answer_candidates),
                )
            if (
                question.question.lower().startswith("when ")
                and answer_candidates
                and getattr(answer_candidates[0], "source", "") == "evidence_memory"
            ):
                hybrid_context_blocks.append(f"answer_candidate: {answer_candidates[0].text}")
            hybrid_packets.append(
                BaselinePromptPacket(
                    benchmark_name=summary_packet.benchmark_name,
                    baseline_name="summary_synthesis_memory_exact_turn_shadow",
                    sample_id=summary_packet.sample_id,
                    question_id=summary_packet.question_id,
                    question=summary_packet.question,
                    assembled_context="\n\n".join(hybrid_context_blocks),
                    retrieved_context_items=hybrid_retrieved_items,
                    metadata={
                        **summary_packet.metadata,
                        "route": "summary_synthesis_memory_exact_turn_shadow",
                        "shadow_selector": "exact_turn_conversational_evidence",
                        "conversational_limit": conversational_limit,
                        "conversational_item_count": len(conversational_retrieved_items),
                    },
                    answer_candidates=answer_candidates,
                )
            )

    shadow_manifest = build_run_manifest(
        samples,
        baseline_name="summary_synthesis_memory_exact_turn_shadow",
        run_id=str(manifest.get("run_id", "")),
        benchmark_name=str(manifest.get("benchmark_name", "")),
        metadata={
            **dict(manifest.get("metadata", {})),
            "shadow_selector": "exact_turn_conversational_evidence",
            "conversational_limit": conversational_limit,
        },
    )
    return shadow_manifest.to_dict(), hybrid_packets


def build_lexical_hybrid_shadow_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    top_k_sessions: int = 2,
    fallback_sessions: int = 1,
) -> tuple[JsonDict, list[BaselinePromptPacket]]:
    manifest, summary_packets = build_summary_synthesis_memory_packets(samples)
    _, lexical_packets = build_lexical_packets(
        samples,
        top_k_sessions=top_k_sessions,
        fallback_sessions=fallback_sessions,
    )
    lexical_by_question_id = {packet.question_id: packet for packet in lexical_packets}
    hybrid_packets: list[BaselinePromptPacket] = []

    for summary_packet in summary_packets:
        lexical_packet = lexical_by_question_id[summary_packet.question_id]
        hybrid_retrieved_items, hybrid_context_blocks = _ordered_shadow_context_blocks(
            shadow_items=list(lexical_packet.retrieved_context_items),
            summary_items=list(summary_packet.retrieved_context_items),
            answer_candidate_text=summary_packet.answer_candidates[0].text if summary_packet.answer_candidates else None,
        )
        hybrid_packets.append(
            BaselinePromptPacket(
                benchmark_name=summary_packet.benchmark_name,
                baseline_name="summary_synthesis_memory_lexical_shadow",
                sample_id=summary_packet.sample_id,
                question_id=summary_packet.question_id,
                question=summary_packet.question,
                assembled_context="\n\n".join(hybrid_context_blocks),
                retrieved_context_items=hybrid_retrieved_items,
                metadata={
                    **summary_packet.metadata,
                    "route": "summary_synthesis_memory_lexical_shadow",
                    "shadow_selector": "lexical_session_overlap",
                    "lexical_top_k_sessions": top_k_sessions,
                    "lexical_fallback_sessions": fallback_sessions,
                    "lexical_item_count": len(lexical_packet.retrieved_context_items),
                },
                answer_candidates=summary_packet.answer_candidates,
            )
        )

    shadow_manifest = build_run_manifest(
        samples,
        baseline_name="summary_synthesis_memory_lexical_shadow",
        run_id=str(manifest.get("run_id", "")),
        benchmark_name=str(manifest.get("benchmark_name", "")),
        metadata={
            **dict(manifest.get("metadata", {})),
            "shadow_selector": "lexical_session_overlap",
            "lexical_top_k_sessions": top_k_sessions,
            "lexical_fallback_sessions": fallback_sessions,
        },
    )
    return shadow_manifest.to_dict(), hybrid_packets


def build_entity_linked_hybrid_shadow_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    entity_limit: int = 6,
) -> tuple[JsonDict, list[BaselinePromptPacket]]:
    manifest, summary_packets = build_summary_synthesis_memory_packets(samples)
    packet_by_question_id = {packet.question_id: packet for packet in summary_packets}
    hybrid_packets: list[BaselinePromptPacket] = []

    for sample in samples:
        index_entries = build_conversational_index(sample)
        for question in sample.questions:
            summary_packet = packet_by_question_id[question.question_id]
            entity_entries = retrieve_entity_linked_entries(question, index_entries, limit=entity_limit)
            entity_items = [
                _conversational_entry_to_retrieved_context_item(
                    question,
                    entry,
                    strategy="entity_linked_conversational_shadow",
                )
                for entry in entity_entries
            ]
            hybrid_retrieved_items, hybrid_context_blocks = _ordered_shadow_context_blocks(
                shadow_items=entity_items,
                summary_items=list(summary_packet.retrieved_context_items),
                answer_candidate_text=summary_packet.answer_candidates[0].text if summary_packet.answer_candidates else None,
            )
            answer_candidates = _entity_linked_answer_candidates(
                question,
                entity_entries,
                list(summary_packet.answer_candidates),
            )
            if answer_candidates:
                hybrid_context_blocks.append(f"answer_candidate: {answer_candidates[0].text}")
            hybrid_packets.append(
                BaselinePromptPacket(
                    benchmark_name=summary_packet.benchmark_name,
                    baseline_name="summary_synthesis_memory_entity_linked_shadow",
                    sample_id=summary_packet.sample_id,
                    question_id=summary_packet.question_id,
                    question=summary_packet.question,
                    assembled_context="\n\n".join(hybrid_context_blocks),
                    retrieved_context_items=hybrid_retrieved_items,
                    metadata={
                        **summary_packet.metadata,
                        "route": "summary_synthesis_memory_entity_linked_shadow",
                        "shadow_selector": "entity_linked_conversational_evidence",
                        "entity_item_count": len(entity_items),
                        "entity_limit": entity_limit,
                    },
                    answer_candidates=answer_candidates,
                )
            )

    shadow_manifest = build_run_manifest(
        samples,
        baseline_name="summary_synthesis_memory_entity_linked_shadow",
        run_id=str(manifest.get("run_id", "")),
        benchmark_name=str(manifest.get("benchmark_name", "")),
        metadata={
            **dict(manifest.get("metadata", {})),
            "shadow_selector": "entity_linked_conversational_evidence",
            "entity_limit": entity_limit,
        },
    )
    return shadow_manifest.to_dict(), hybrid_packets


def build_typed_graph_hybrid_shadow_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    graph_limit: int = 6,
) -> tuple[JsonDict, list[BaselinePromptPacket]]:
    manifest, summary_packets = build_summary_synthesis_memory_packets(samples)
    packet_by_question_id = {packet.question_id: packet for packet in summary_packets}
    hybrid_packets: list[BaselinePromptPacket] = []

    for sample in samples:
        graph = build_typed_temporal_graph_memory(sample)
        for question in sample.questions:
            summary_packet = packet_by_question_id[question.question_id]
            hybrid_retrieved_items = list(summary_packet.retrieved_context_items)
            graph_items: list[RetrievedContextItem] = []
            graph_hits: list[TypedTemporalGraphHit] = []
            if _question_prefers_typed_graph_evidence(question):
                graph_hits = retrieve_typed_temporal_graph_hits(question, graph, limit=graph_limit)
                graph_items = [_graph_hit_to_retrieved_context_item(hit) for hit in graph_hits]
            summary_fallback_items = _typed_graph_summary_fallback_items(
                question,
                list(summary_packet.retrieved_context_items),
                graph_hits,
            )
            hybrid_retrieved_items, hybrid_context_blocks = _ordered_shadow_context_blocks(
                shadow_items=graph_items,
                summary_items=summary_fallback_items,
                answer_candidate_text=summary_packet.answer_candidates[0].text if summary_packet.answer_candidates else None,
            )
            answer_candidates = _typed_graph_answer_candidates(
                question,
                graph_hits,
                list(summary_packet.answer_candidates),
            )
            if answer_candidates:
                hybrid_context_blocks.append(f"answer_candidate: {answer_candidates[0].text}")
            hybrid_packets.append(
                BaselinePromptPacket(
                    benchmark_name=summary_packet.benchmark_name,
                    baseline_name="summary_synthesis_memory_typed_graph_shadow",
                    sample_id=summary_packet.sample_id,
                    question_id=summary_packet.question_id,
                    question=summary_packet.question,
                    assembled_context="\n\n".join(hybrid_context_blocks),
                    retrieved_context_items=hybrid_retrieved_items,
                    metadata={
                        **summary_packet.metadata,
                        "route": "summary_synthesis_memory_typed_graph_shadow",
                        "shadow_selector": "typed_temporal_graph_evidence",
                        "graph_limit": graph_limit,
                        "graph_item_count": len(graph_items),
                    },
                    answer_candidates=answer_candidates,
                )
            )

    shadow_manifest = build_run_manifest(
        samples,
        baseline_name="summary_synthesis_memory_typed_graph_shadow",
        run_id=str(manifest.get("run_id", "")),
        benchmark_name=str(manifest.get("benchmark_name", "")),
        metadata={
            **dict(manifest.get("metadata", {})),
            "shadow_selector": "typed_temporal_graph_evidence",
            "graph_limit": graph_limit,
        },
    )
    return shadow_manifest.to_dict(), hybrid_packets


def build_fused_conversational_hybrid_shadow_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    entity_limit: int = 6,
    graph_limit: int = 6,
) -> tuple[JsonDict, list[BaselinePromptPacket]]:
    manifest, summary_packets = build_summary_synthesis_memory_packets(samples)
    _, exact_turn_packets = build_exact_turn_hybrid_shadow_packets(samples, conversational_limit=8)
    _, entity_packets = build_entity_linked_hybrid_shadow_packets(samples, entity_limit=entity_limit)
    _, graph_packets = build_typed_graph_hybrid_shadow_packets(samples, graph_limit=graph_limit)
    summary_by_question_id = {packet.question_id: packet for packet in summary_packets}
    exact_turn_by_question_id = {packet.question_id: packet for packet in exact_turn_packets}
    entity_by_question_id = {packet.question_id: packet for packet in entity_packets}
    graph_by_question_id = {packet.question_id: packet for packet in graph_packets}
    fused_packets: list[BaselinePromptPacket] = []

    for sample in samples:
        for question in sample.questions:
            summary_packet = summary_by_question_id[question.question_id]
            exact_turn_packet = exact_turn_by_question_id[question.question_id]
            entity_packet = entity_by_question_id[question.question_id]
            graph_packet = graph_by_question_id[question.question_id]
            selector = _fused_shadow_selector(question)
            if selector == "entity_linked_first":
                selected_packet = entity_packet
            elif selector == "exact_turn_first":
                selected_packet = exact_turn_packet
            elif selector == "typed_graph_first":
                selected_packet = graph_packet
            else:
                selected_packet = summary_packet

            fused_packets.append(
                BaselinePromptPacket(
                    benchmark_name=selected_packet.benchmark_name,
                    baseline_name="summary_synthesis_memory_fused_conversational_shadow",
                    sample_id=selected_packet.sample_id,
                    question_id=selected_packet.question_id,
                    question=selected_packet.question,
                    assembled_context=selected_packet.assembled_context,
                    retrieved_context_items=list(selected_packet.retrieved_context_items),
                    metadata={
                        **summary_packet.metadata,
                        **selected_packet.metadata,
                        "route": "summary_synthesis_memory_fused_conversational_shadow",
                        "shadow_selector": selector,
                        "fused_variant_baseline": selected_packet.baseline_name,
                        "fused_selected_item_count": len(selected_packet.retrieved_context_items),
                        "entity_limit": entity_limit,
                        "graph_limit": graph_limit,
                        "conversational_item_count": int(exact_turn_packet.metadata.get("conversational_item_count", 0)),
                        "entity_item_count": int(entity_packet.metadata.get("entity_item_count", 0)),
                        "graph_item_count": int(graph_packet.metadata.get("graph_item_count", 0)),
                    },
                    answer_candidates=list(selected_packet.answer_candidates),
                )
            )

    shadow_manifest = build_run_manifest(
        samples,
        baseline_name="summary_synthesis_memory_fused_conversational_shadow",
        run_id=str(manifest.get("run_id", "")),
        benchmark_name=str(manifest.get("benchmark_name", "")),
        metadata={
            **dict(manifest.get("metadata", {})),
            "shadow_selector": "fused_conversational_shadow",
            "entity_limit": entity_limit,
            "graph_limit": graph_limit,
        },
    )
    return shadow_manifest.to_dict(), fused_packets


def _build_shadow_answer_eval(
    samples: list[NormalizedBenchmarkSample],
    *,
    provider_name: str,
    variant_packets: list[BaselinePromptPacket],
    variant_label: str,
    variant_item_count_field: str,
    variant_packet_metadata_field: str,
) -> JsonDict:
    _, summary_packets = build_summary_synthesis_memory_packets(samples)
    question_by_id = {
        question.question_id: question
        for sample in samples
        for question in sample.questions
    }
    provider = get_provider(provider_name)
    rows: list[JsonDict] = []
    summary_correct = 0
    variant_correct = 0
    by_sample: dict[str, dict[str, int]] = {}

    for summary_packet, variant_packet in zip(summary_packets, variant_packets, strict=True):
        question = question_by_id[summary_packet.question_id]
        summary_response = provider.generate_answer(summary_packet)
        summary_prediction = _build_prediction(
            summary_packet,
            question=question,
            provider=provider,
            answer=summary_response.answer,
            provider_metadata=summary_response.metadata,
        )
        variant_response = provider.generate_answer(variant_packet)
        variant_prediction = _build_prediction(
            variant_packet,
            question=question,
            provider=provider,
            answer=variant_response.answer,
            provider_metadata=variant_response.metadata,
        )
        sample_metrics = by_sample.setdefault(
            summary_packet.sample_id,
            {"summary_correct": 0, f"{variant_label}_correct": 0, "improved": 0, "regressed": 0, "total": 0},
        )
        sample_metrics["total"] += 1
        if summary_prediction.is_correct:
            summary_correct += 1
            sample_metrics["summary_correct"] += 1
        if variant_prediction.is_correct:
            variant_correct += 1
            sample_metrics[f"{variant_label}_correct"] += 1
        if not summary_prediction.is_correct and variant_prediction.is_correct:
            sample_metrics["improved"] += 1
        if summary_prediction.is_correct and not variant_prediction.is_correct:
            sample_metrics["regressed"] += 1
        rows.append(
            {
                "sample_id": summary_packet.sample_id,
                "question_id": summary_packet.question_id,
                "question": summary_packet.question,
                "expected_answers": question.expected_answers,
                "summary_answer": summary_prediction.predicted_answer,
                "summary_correct": summary_prediction.is_correct,
                f"{variant_label}_answer": variant_prediction.predicted_answer,
                f"{variant_label}_correct": variant_prediction.is_correct,
                "improved": (not summary_prediction.is_correct and variant_prediction.is_correct),
                "regressed": (summary_prediction.is_correct and not variant_prediction.is_correct),
                "question_prefers_exact_conversational_evidence": _question_prefers_exact_conversational_evidence(
                    question
                ),
                "question_prefers_typed_graph_evidence": _question_prefers_typed_graph_evidence(question),
                "summary_retrieved_context_item_count": len(summary_packet.retrieved_context_items),
                f"{variant_label}_retrieved_context_item_count": len(variant_packet.retrieved_context_items),
                variant_item_count_field: int(variant_packet.metadata.get(variant_packet_metadata_field, 0)),
            }
        )

    total = len(rows)
    return {
        "overall": {
            "provider_name": provider.name,
            "summary_correct": summary_correct,
            f"{variant_label}_correct": variant_correct,
            "total": total,
            "summary_accuracy": round(summary_correct / total, 4) if total else 0.0,
            f"{variant_label}_accuracy": round(variant_correct / total, 4) if total else 0.0,
            f"{variant_label}_delta_vs_summary": variant_correct - summary_correct,
            "improved": sum(1 for row in rows if row["improved"]),
            "regressed": sum(1 for row in rows if row["regressed"]),
        },
        "by_sample": by_sample,
        "rows": rows,
    }


def build_exact_turn_shadow_answer_eval(
    samples: list[NormalizedBenchmarkSample],
    *,
    conversational_limit: int = 8,
    provider_name: str = "heuristic",
) -> JsonDict:
    _, hybrid_packets = build_exact_turn_hybrid_shadow_packets(
        samples,
        conversational_limit=conversational_limit,
    )
    return _build_shadow_answer_eval(
        samples,
        provider_name=provider_name,
        variant_packets=hybrid_packets,
        variant_label="hybrid",
        variant_item_count_field="hybrid_conversational_item_count",
        variant_packet_metadata_field="conversational_item_count",
    )


def build_lexical_shadow_answer_eval(
    samples: list[NormalizedBenchmarkSample],
    *,
    top_k_sessions: int = 2,
    fallback_sessions: int = 1,
    provider_name: str = "heuristic",
) -> JsonDict:
    _, hybrid_packets = build_lexical_hybrid_shadow_packets(
        samples,
        top_k_sessions=top_k_sessions,
        fallback_sessions=fallback_sessions,
    )
    return _build_shadow_answer_eval(
        samples,
        provider_name=provider_name,
        variant_packets=hybrid_packets,
        variant_label="lexical_hybrid",
        variant_item_count_field="lexical_hybrid_item_count",
        variant_packet_metadata_field="lexical_item_count",
    )


def build_entity_linked_shadow_answer_eval(
    samples: list[NormalizedBenchmarkSample],
    *,
    entity_limit: int = 6,
    provider_name: str = "heuristic",
) -> JsonDict:
    _, hybrid_packets = build_entity_linked_hybrid_shadow_packets(
        samples,
        entity_limit=entity_limit,
    )
    return _build_shadow_answer_eval(
        samples,
        provider_name=provider_name,
        variant_packets=hybrid_packets,
        variant_label="entity_hybrid",
        variant_item_count_field="entity_hybrid_item_count",
        variant_packet_metadata_field="entity_item_count",
    )


def build_typed_graph_shadow_answer_eval(
    samples: list[NormalizedBenchmarkSample],
    *,
    graph_limit: int = 6,
    provider_name: str = "heuristic",
) -> JsonDict:
    _, hybrid_packets = build_typed_graph_hybrid_shadow_packets(
        samples,
        graph_limit=graph_limit,
    )
    return _build_shadow_answer_eval(
        samples,
        provider_name=provider_name,
        variant_packets=hybrid_packets,
        variant_label="graph_hybrid",
        variant_item_count_field="graph_hybrid_graph_item_count",
        variant_packet_metadata_field="graph_item_count",
    )


def build_fused_conversational_shadow_answer_eval(
    samples: list[NormalizedBenchmarkSample],
    *,
    entity_limit: int = 6,
    graph_limit: int = 6,
    provider_name: str = "heuristic",
) -> JsonDict:
    _, hybrid_packets = build_fused_conversational_hybrid_shadow_packets(
        samples,
        entity_limit=entity_limit,
        graph_limit=graph_limit,
    )
    return _build_shadow_answer_eval(
        samples,
        provider_name=provider_name,
        variant_packets=hybrid_packets,
        variant_label="fused_hybrid",
        variant_item_count_field="fused_hybrid_selected_item_count",
        variant_packet_metadata_field="fused_selected_item_count",
    )


def build_multi_shadow_answer_eval(
    samples: list[NormalizedBenchmarkSample],
    *,
    provider_name: str = "heuristic",
    conversational_limit: int = 8,
    graph_limit: int = 6,
) -> JsonDict:
    _, summary_packets = build_summary_synthesis_memory_packets(samples)
    _, exact_turn_packets = build_exact_turn_hybrid_shadow_packets(
        samples,
        conversational_limit=conversational_limit,
    )
    _, entity_packets = build_entity_linked_hybrid_shadow_packets(samples)
    _, graph_packets = build_typed_graph_hybrid_shadow_packets(
        samples,
        graph_limit=graph_limit,
    )
    _, fused_packets = build_fused_conversational_hybrid_shadow_packets(
        samples,
        entity_limit=6,
        graph_limit=graph_limit,
    )
    question_by_id = {
        question.question_id: question
        for sample in samples
        for question in sample.questions
    }
    provider = get_provider(provider_name)
    rows: list[JsonDict] = []
    by_sample: dict[str, dict[str, int]] = {}
    summary_correct = 0
    exact_turn_correct = 0
    entity_correct = 0
    graph_correct = 0
    fused_correct = 0

    for summary_packet, exact_turn_packet, entity_packet, graph_packet, fused_packet in zip(
        summary_packets,
        exact_turn_packets,
        entity_packets,
        graph_packets,
        fused_packets,
        strict=True,
    ):
        question = question_by_id[summary_packet.question_id]
        summary_response = provider.generate_answer(summary_packet)
        summary_prediction = _build_prediction(
            summary_packet,
            question=question,
            provider=provider,
            answer=summary_response.answer,
            provider_metadata=summary_response.metadata,
        )
        exact_turn_response = provider.generate_answer(exact_turn_packet)
        exact_turn_prediction = _build_prediction(
            exact_turn_packet,
            question=question,
            provider=provider,
            answer=exact_turn_response.answer,
            provider_metadata=exact_turn_response.metadata,
        )
        entity_response = provider.generate_answer(entity_packet)
        entity_prediction = _build_prediction(
            entity_packet,
            question=question,
            provider=provider,
            answer=entity_response.answer,
            provider_metadata=entity_response.metadata,
        )
        graph_response = provider.generate_answer(graph_packet)
        graph_prediction = _build_prediction(
            graph_packet,
            question=question,
            provider=provider,
            answer=graph_response.answer,
            provider_metadata=graph_response.metadata,
        )
        fused_response = provider.generate_answer(fused_packet)
        fused_prediction = _build_prediction(
            fused_packet,
            question=question,
            provider=provider,
            answer=fused_response.answer,
            provider_metadata=fused_response.metadata,
        )
        sample_metrics = by_sample.setdefault(
            summary_packet.sample_id,
            {
                "summary_correct": 0,
                "exact_turn_correct": 0,
                "entity_correct": 0,
                "graph_correct": 0,
                "fused_correct": 0,
                "total": 0,
            },
        )
        sample_metrics["total"] += 1
        if summary_prediction.is_correct:
            summary_correct += 1
            sample_metrics["summary_correct"] += 1
        if exact_turn_prediction.is_correct:
            exact_turn_correct += 1
            sample_metrics["exact_turn_correct"] += 1
        if entity_prediction.is_correct:
            entity_correct += 1
            sample_metrics["entity_correct"] += 1
        if graph_prediction.is_correct:
            graph_correct += 1
            sample_metrics["graph_correct"] += 1
        if fused_prediction.is_correct:
            fused_correct += 1
            sample_metrics["fused_correct"] += 1
        rows.append(
            {
                "sample_id": summary_packet.sample_id,
                "question_id": summary_packet.question_id,
                "question": summary_packet.question,
                "expected_answers": question.expected_answers,
                "summary_answer": summary_prediction.predicted_answer,
                "summary_correct": summary_prediction.is_correct,
                "exact_turn_answer": exact_turn_prediction.predicted_answer,
                "exact_turn_correct": exact_turn_prediction.is_correct,
                "entity_answer": entity_prediction.predicted_answer,
                "entity_correct": entity_prediction.is_correct,
                "graph_answer": graph_prediction.predicted_answer,
                "graph_correct": graph_prediction.is_correct,
                "fused_answer": fused_prediction.predicted_answer,
                "fused_correct": fused_prediction.is_correct,
                "question_prefers_exact_conversational_evidence": _question_prefers_exact_conversational_evidence(
                    question
                ),
                "question_prefers_entity_linked_evidence": _question_prefers_entity_linked_evidence(question),
                "question_prefers_typed_graph_evidence": _question_prefers_typed_graph_evidence(question),
                "exact_turn_conversational_item_count": int(exact_turn_packet.metadata.get("conversational_item_count", 0)),
                "entity_item_count": int(entity_packet.metadata.get("entity_item_count", 0)),
                "graph_item_count": int(graph_packet.metadata.get("graph_item_count", 0)),
                "fused_selector": fused_packet.metadata.get("shadow_selector", ""),
                "fused_variant_baseline": fused_packet.metadata.get("fused_variant_baseline", ""),
            }
        )

    total = len(rows)
    return {
        "overall": {
            "provider_name": provider.name,
            "summary_correct": summary_correct,
            "exact_turn_correct": exact_turn_correct,
            "entity_correct": entity_correct,
            "graph_correct": graph_correct,
            "fused_correct": fused_correct,
            "total": total,
            "summary_accuracy": round(summary_correct / total, 4) if total else 0.0,
            "exact_turn_accuracy": round(exact_turn_correct / total, 4) if total else 0.0,
            "entity_accuracy": round(entity_correct / total, 4) if total else 0.0,
            "graph_accuracy": round(graph_correct / total, 4) if total else 0.0,
            "fused_accuracy": round(fused_correct / total, 4) if total else 0.0,
            "exact_turn_delta_vs_summary": exact_turn_correct - summary_correct,
            "entity_delta_vs_summary": entity_correct - summary_correct,
            "graph_delta_vs_summary": graph_correct - summary_correct,
            "fused_delta_vs_summary": fused_correct - summary_correct,
        },
        "by_sample": by_sample,
        "rows": rows,
    }


def build_conversational_shadow_eval(
    samples: list[NormalizedBenchmarkSample],
    *,
    conversational_limit: int = 8,
) -> JsonDict:
    _, packets = build_summary_synthesis_memory_packets(samples)
    packet_by_question_id = {packet.question_id: packet for packet in packets}

    rows: list[JsonDict] = []
    summary_covered = 0
    conversational_covered = 0
    hybrid_covered = 0
    gated_hybrid_covered = 0
    exact_turn_hybrid_covered = 0
    total = 0
    by_sample: dict[str, dict[str, int]] = {}

    for sample in samples:
        index_entries = build_conversational_index(sample)
        sample_summary_covered = 0
        sample_conversational_covered = 0
        sample_hybrid_covered = 0
        sample_gated_hybrid_covered = 0
        sample_exact_turn_hybrid_covered = 0
        sample_total = 0
        for question in sample.questions:
            packet = packet_by_question_id[question.question_id]
            summary_text = "\n".join(item.text for item in packet.retrieved_context_items)
            conversational_hits = retrieve_conversational_entries(
                question,
                index_entries,
                limit=conversational_limit,
            )
            conversational_text = "\n".join(entry.text for entry in conversational_hits)
            summary_has_coverage = _expected_answer_coverage(summary_text, question.expected_answers)
            conversational_has_coverage = _expected_answer_coverage(conversational_text, question.expected_answers)
            hybrid_has_coverage = summary_has_coverage or conversational_has_coverage
            gated_hybrid_has_coverage = summary_has_coverage or (
                _question_uses_conversational_hybrid(question) and conversational_has_coverage
            )
            exact_turn_hybrid_has_coverage = summary_has_coverage or (
                _question_prefers_exact_conversational_evidence(question) and conversational_has_coverage
            )
            rows.append(
                {
                    "sample_id": sample.sample_id,
                    "question_id": question.question_id,
                    "question": question.question,
                    "expected_answers": question.expected_answers,
                    "question_uses_conversational_hybrid": _question_uses_conversational_hybrid(question),
                    "question_prefers_exact_conversational_evidence": _question_prefers_exact_conversational_evidence(
                        question
                    ),
                    "summary_retrieval_covered": summary_has_coverage,
                    "conversational_retrieval_covered": conversational_has_coverage,
                    "hybrid_retrieval_covered": hybrid_has_coverage,
                    "gated_hybrid_retrieval_covered": gated_hybrid_has_coverage,
                    "exact_turn_hybrid_retrieval_covered": exact_turn_hybrid_has_coverage,
                    "summary_retrieval_text": summary_text,
                    "conversational_retrieval_text": conversational_text,
                }
            )
            sample_total += 1
            total += 1
            if summary_has_coverage:
                sample_summary_covered += 1
                summary_covered += 1
            if conversational_has_coverage:
                sample_conversational_covered += 1
                conversational_covered += 1
            if hybrid_has_coverage:
                sample_hybrid_covered += 1
                hybrid_covered += 1
            if gated_hybrid_has_coverage:
                sample_gated_hybrid_covered += 1
                gated_hybrid_covered += 1
            if exact_turn_hybrid_has_coverage:
                sample_exact_turn_hybrid_covered += 1
                exact_turn_hybrid_covered += 1
        by_sample[sample.sample_id] = {
            "summary_covered": sample_summary_covered,
            "conversational_covered": sample_conversational_covered,
            "hybrid_covered": sample_hybrid_covered,
            "gated_hybrid_covered": sample_gated_hybrid_covered,
            "exact_turn_hybrid_covered": sample_exact_turn_hybrid_covered,
            "total": sample_total,
        }

    return {
        "overall": {
            "summary_covered": summary_covered,
            "conversational_covered": conversational_covered,
            "hybrid_covered": hybrid_covered,
            "gated_hybrid_covered": gated_hybrid_covered,
            "exact_turn_hybrid_covered": exact_turn_hybrid_covered,
            "total": total,
            "summary_coverage_rate": round(summary_covered / total, 4) if total else 0.0,
            "conversational_coverage_rate": round(conversational_covered / total, 4) if total else 0.0,
            "hybrid_coverage_rate": round(hybrid_covered / total, 4) if total else 0.0,
            "gated_hybrid_coverage_rate": round(gated_hybrid_covered / total, 4) if total else 0.0,
            "exact_turn_hybrid_coverage_rate": round(exact_turn_hybrid_covered / total, 4) if total else 0.0,
            "coverage_delta": conversational_covered - summary_covered,
            "hybrid_delta_vs_summary": hybrid_covered - summary_covered,
            "gated_hybrid_delta_vs_summary": gated_hybrid_covered - summary_covered,
            "exact_turn_hybrid_delta_vs_summary": exact_turn_hybrid_covered - summary_covered,
        },
        "by_sample": by_sample,
        "rows": rows,
    }
