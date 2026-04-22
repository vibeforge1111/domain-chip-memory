from __future__ import annotations

import re
from typing import Any

from .contracts import JsonDict, NormalizedBenchmarkSample, NormalizedQuestion
from .memory_conversational_index import build_conversational_index
from .memory_conversational_retrieval import _entry_score, retrieve_conversational_entries
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
    if question_lower.startswith("when ") and any(
        token in question_lower for token in ("going to", "conference", "pass away", "passed away")
    ):
        return True
    if any(token in question_lower for token in ("peace", "support", "grieving", "comfort")):
        return True
    return False


def _conversational_entry_to_retrieved_context_item(
    question: NormalizedQuestion,
    entry: Any,
) -> RetrievedContextItem:
    return RetrievedContextItem(
        session_id=entry.session_id,
        turn_ids=[entry.turn_id],
        score=_entry_score(question, entry),
        strategy="exact_turn_conversational_shadow",
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
                hybrid_retrieved_items = _merge_retrieved_context_items(
                    hybrid_retrieved_items,
                    conversational_retrieved_items,
                )
            hybrid_context_blocks = [item.text for item in hybrid_retrieved_items]
            if summary_packet.answer_candidates:
                hybrid_context_blocks.append(f"answer_candidate: {summary_packet.answer_candidates[0].text}")
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
                    answer_candidates=summary_packet.answer_candidates,
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
            if _question_prefers_typed_graph_evidence(question):
                graph_hits = retrieve_typed_temporal_graph_hits(question, graph, limit=graph_limit)
                graph_items = [_graph_hit_to_retrieved_context_item(hit) for hit in graph_hits]
                hybrid_retrieved_items = _merge_retrieved_context_items(
                    hybrid_retrieved_items,
                    graph_items,
                )
            hybrid_context_blocks = [item.text for item in hybrid_retrieved_items]
            if summary_packet.answer_candidates:
                hybrid_context_blocks.append(f"answer_candidate: {summary_packet.answer_candidates[0].text}")
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
                    answer_candidates=summary_packet.answer_candidates,
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


def build_exact_turn_shadow_answer_eval(
    samples: list[NormalizedBenchmarkSample],
    *,
    conversational_limit: int = 8,
    provider_name: str = "heuristic",
) -> JsonDict:
    _, summary_packets = build_summary_synthesis_memory_packets(samples)
    _, hybrid_packets = build_exact_turn_hybrid_shadow_packets(
        samples,
        conversational_limit=conversational_limit,
    )
    question_by_id = {
        question.question_id: question
        for sample in samples
        for question in sample.questions
    }
    provider = get_provider(provider_name)
    rows: list[JsonDict] = []
    summary_correct = 0
    hybrid_correct = 0
    by_sample: dict[str, dict[str, int]] = {}

    for summary_packet, hybrid_packet in zip(summary_packets, hybrid_packets, strict=True):
        question = question_by_id[summary_packet.question_id]
        summary_response = provider.generate_answer(summary_packet)
        summary_prediction = _build_prediction(
            summary_packet,
            question=question,
            provider=provider,
            answer=summary_response.answer,
            provider_metadata=summary_response.metadata,
        )
        hybrid_response = provider.generate_answer(hybrid_packet)
        hybrid_prediction = _build_prediction(
            hybrid_packet,
            question=question,
            provider=provider,
            answer=hybrid_response.answer,
            provider_metadata=hybrid_response.metadata,
        )
        sample_metrics = by_sample.setdefault(
            summary_packet.sample_id,
            {"summary_correct": 0, "hybrid_correct": 0, "improved": 0, "regressed": 0, "total": 0},
        )
        sample_metrics["total"] += 1
        if summary_prediction.is_correct:
            summary_correct += 1
            sample_metrics["summary_correct"] += 1
        if hybrid_prediction.is_correct:
            hybrid_correct += 1
            sample_metrics["hybrid_correct"] += 1
        if not summary_prediction.is_correct and hybrid_prediction.is_correct:
            sample_metrics["improved"] += 1
        if summary_prediction.is_correct and not hybrid_prediction.is_correct:
            sample_metrics["regressed"] += 1
        rows.append(
            {
                "sample_id": summary_packet.sample_id,
                "question_id": summary_packet.question_id,
                "question": summary_packet.question,
                "expected_answers": question.expected_answers,
                "summary_answer": summary_prediction.predicted_answer,
                "summary_correct": summary_prediction.is_correct,
                "hybrid_answer": hybrid_prediction.predicted_answer,
                "hybrid_correct": hybrid_prediction.is_correct,
                "improved": (not summary_prediction.is_correct and hybrid_prediction.is_correct),
                "regressed": (summary_prediction.is_correct and not hybrid_prediction.is_correct),
                "question_prefers_exact_conversational_evidence": _question_prefers_exact_conversational_evidence(
                    question
                ),
                "summary_retrieved_context_item_count": len(summary_packet.retrieved_context_items),
                "hybrid_retrieved_context_item_count": len(hybrid_packet.retrieved_context_items),
                "hybrid_conversational_item_count": int(hybrid_packet.metadata.get("conversational_item_count", 0)),
            }
        )

    total = len(rows)
    return {
        "overall": {
            "provider_name": provider.name,
            "summary_correct": summary_correct,
            "hybrid_correct": hybrid_correct,
            "total": total,
            "summary_accuracy": round(summary_correct / total, 4) if total else 0.0,
            "hybrid_accuracy": round(hybrid_correct / total, 4) if total else 0.0,
            "hybrid_delta_vs_summary": hybrid_correct - summary_correct,
            "improved": sum(1 for row in rows if row["improved"]),
            "regressed": sum(1 for row in rows if row["regressed"]),
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
