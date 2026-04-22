from __future__ import annotations

import re
from typing import Any

from .contracts import JsonDict, NormalizedBenchmarkSample, NormalizedQuestion
from .memory_conversational_index import build_conversational_index
from .memory_conversational_retrieval import retrieve_conversational_entries
from .memory_extraction import _tokenize
from .packet_builders import build_summary_synthesis_memory_packets
from .scorecards import _normalize_answer


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
    total = 0
    by_sample: dict[str, dict[str, int]] = {}

    for sample in samples:
        index_entries = build_conversational_index(sample)
        sample_summary_covered = 0
        sample_conversational_covered = 0
        sample_hybrid_covered = 0
        sample_gated_hybrid_covered = 0
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
            rows.append(
                {
                    "sample_id": sample.sample_id,
                    "question_id": question.question_id,
                    "question": question.question,
                    "expected_answers": question.expected_answers,
                    "question_uses_conversational_hybrid": _question_uses_conversational_hybrid(question),
                    "summary_retrieval_covered": summary_has_coverage,
                    "conversational_retrieval_covered": conversational_has_coverage,
                    "hybrid_retrieval_covered": hybrid_has_coverage,
                    "gated_hybrid_retrieval_covered": gated_hybrid_has_coverage,
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
        by_sample[sample.sample_id] = {
            "summary_covered": sample_summary_covered,
            "conversational_covered": sample_conversational_covered,
            "hybrid_covered": sample_hybrid_covered,
            "gated_hybrid_covered": sample_gated_hybrid_covered,
            "total": sample_total,
        }

    return {
        "overall": {
            "summary_covered": summary_covered,
            "conversational_covered": conversational_covered,
            "hybrid_covered": hybrid_covered,
            "gated_hybrid_covered": gated_hybrid_covered,
            "total": total,
            "summary_coverage_rate": round(summary_covered / total, 4) if total else 0.0,
            "conversational_coverage_rate": round(conversational_covered / total, 4) if total else 0.0,
            "hybrid_coverage_rate": round(hybrid_covered / total, 4) if total else 0.0,
            "gated_hybrid_coverage_rate": round(gated_hybrid_covered / total, 4) if total else 0.0,
            "coverage_delta": conversational_covered - summary_covered,
            "hybrid_delta_vs_summary": hybrid_covered - summary_covered,
            "gated_hybrid_delta_vs_summary": gated_hybrid_covered - summary_covered,
        },
        "by_sample": by_sample,
        "rows": rows,
    }
