from __future__ import annotations

import re
from typing import Any

from .contracts import NormalizedBenchmarkSample, NormalizedQuestion, NormalizedSession
from .runs import BaselinePromptPacket, RetrievedContextItem, build_run_manifest


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "do",
    "does",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "now",
    "of",
    "on",
    "or",
    "the",
    "to",
    "was",
    "what",
    "when",
    "where",
    "who",
    "why",
    "you",
}


def _tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in STOPWORDS]


def _serialize_session(session: NormalizedSession) -> str:
    lines = []
    header = f"Session {session.session_id}"
    if session.timestamp:
        header += f" @ {session.timestamp}"
    lines.append(header)
    for turn in session.turns:
        lines.append(f"{turn.speaker}: {turn.text}")
    return "\n".join(lines)


def _session_lexical_score(question: NormalizedQuestion, session: NormalizedSession) -> float:
    question_tokens = _tokenize(question.question)
    if not question_tokens:
        return 0.0
    session_tokens = _tokenize(" ".join(turn.text for turn in session.turns))
    if not session_tokens:
        return 0.0
    score = 0.0
    for token in question_tokens:
        score += session_tokens.count(token)
    return score


def _latest_sessions(sessions: list[NormalizedSession], limit: int) -> list[NormalizedSession]:
    return sorted(sessions, key=lambda session: session.timestamp or "", reverse=True)[:limit]


def build_full_context_packets(
    samples: list[NormalizedBenchmarkSample], *, run_id: str = "full-context-v1"
) -> tuple[dict[str, Any], list[BaselinePromptPacket]]:
    packets: list[BaselinePromptPacket] = []
    for sample in samples:
        context = "\n\n".join(_serialize_session(session) for session in sample.sessions)
        retrieved_items = [
            RetrievedContextItem(
                session_id=session.session_id,
                turn_ids=[turn.turn_id for turn in session.turns],
                score=1.0,
                strategy="full_context",
                text=_serialize_session(session),
            )
            for session in sample.sessions
        ]
        for question in sample.questions:
            packets.append(
                BaselinePromptPacket(
                    benchmark_name=sample.benchmark_name,
                    baseline_name="full_context",
                    sample_id=sample.sample_id,
                    question_id=question.question_id,
                    question=question.question,
                    assembled_context=context,
                    retrieved_context_items=retrieved_items,
                    metadata={"route": "full_context"},
                )
            )
    manifest = build_run_manifest(
        samples,
        baseline_name="full_context",
        run_id=run_id,
        metadata={"baseline_type": "deterministic_prompt_builder"},
    )
    return manifest.to_dict(), packets


def build_lexical_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    top_k_sessions: int = 2,
    fallback_sessions: int = 1,
    run_id: str = "lexical-v1",
) -> tuple[dict[str, Any], list[BaselinePromptPacket]]:
    packets: list[BaselinePromptPacket] = []
    for sample in samples:
        for question in sample.questions:
            scored_sessions = [
                (session, _session_lexical_score(question, session)) for session in sample.sessions
            ]
            positive = [(session, score) for session, score in scored_sessions if score > 0]
            if positive:
                ranked = sorted(
                    positive,
                    key=lambda item: (item[1], item[0].timestamp or ""),
                    reverse=True,
                )[:top_k_sessions]
            else:
                ranked = [(session, 0.0) for session in _latest_sessions(sample.sessions, fallback_sessions)]
            retrieved_items = [
                RetrievedContextItem(
                    session_id=session.session_id,
                    turn_ids=[turn.turn_id for turn in session.turns],
                    score=score,
                    strategy="lexical_session_overlap",
                    text=_serialize_session(session),
                    metadata={"timestamp": session.timestamp},
                )
                for session, score in ranked
            ]
            context = "\n\n".join(item.text for item in retrieved_items)
            packets.append(
                BaselinePromptPacket(
                    benchmark_name=sample.benchmark_name,
                    baseline_name="lexical",
                    sample_id=sample.sample_id,
                    question_id=question.question_id,
                    question=question.question,
                    assembled_context=context,
                    retrieved_context_items=retrieved_items,
                    metadata={
                        "route": "lexical_session_overlap",
                        "top_k_sessions": top_k_sessions,
                        "fallback_sessions": fallback_sessions,
                    },
                )
            )
    manifest = build_run_manifest(
        samples,
        baseline_name="lexical",
        run_id=run_id,
        metadata={
            "baseline_type": "deterministic_lexical_retrieval",
            "top_k_sessions": top_k_sessions,
            "fallback_sessions": fallback_sessions,
        },
    )
    return manifest.to_dict(), packets


def build_baseline_contract_summary() -> dict[str, Any]:
    return {
        "run_contracts": [
            "BenchmarkRunManifest",
            "BaselinePromptPacket",
            "RetrievedContextItem",
        ],
        "baselines": [
            {
                "baseline_name": "full_context",
                "entrypoint": "build_full_context_packets",
                "behavior": "Assemble every normalized session into one context packet per question.",
            },
            {
                "baseline_name": "lexical",
                "entrypoint": "build_lexical_packets",
                "behavior": "Rank sessions by lexical overlap with the question and assemble the top context.",
            },
        ],
    }
