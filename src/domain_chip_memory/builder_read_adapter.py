from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sdk import (
    AnswerExplanationRequest,
    CurrentStateRequest,
    EventRetrievalRequest,
    EvidenceRetrievalRequest,
    HistoricalStateRequest,
    SparkMemorySDK,
)


@dataclass(frozen=True)
class BuilderMemoryReadRequest:
    method: str
    subject: str
    predicate: str | None = None
    entity_key: str | None = None
    predicate_prefix: str | None = None
    query: str | None = None
    question: str | None = None
    as_of: str | None = None
    limit: int = 5
    evidence_limit: int = 3
    event_limit: int = 3


def execute_builder_memory_read(
    sdk: SparkMemorySDK,
    request: BuilderMemoryReadRequest,
) -> dict[str, Any]:
    method = str(request.method or "").strip().lower()
    if method == "get_current_state":
        return _materialize_lookup_result(
            method=method,
            result=sdk.get_current_state(
                CurrentStateRequest(
                    subject=request.subject,
                    predicate=str(request.predicate or ""),
                    entity_key=request.entity_key,
                )
            ),
        )
    if method == "get_historical_state":
        return _materialize_lookup_result(
            method=method,
            result=sdk.get_historical_state(
                HistoricalStateRequest(
                    subject=request.subject,
                    predicate=str(request.predicate or ""),
                    as_of=str(request.as_of or ""),
                    entity_key=request.entity_key,
                )
            ),
        )
    if method == "retrieve_evidence":
        return _materialize_retrieval_result(
            method=method,
            result=sdk.retrieve_evidence(
                EvidenceRetrievalRequest(
                    query=request.query or request.question,
                    subject=request.subject,
                    predicate=request.predicate,
                    limit=request.limit,
                )
            ),
        )
    if method == "retrieve_events":
        return _materialize_retrieval_result(
            method=method,
            result=sdk.retrieve_events(
                EventRetrievalRequest(
                    query=request.query or request.question,
                    subject=request.subject,
                    predicate=request.predicate,
                    limit=request.limit,
                )
            ),
        )
    if method == "explain_answer":
        return _materialize_explanation_result(
            method=method,
            result=sdk.explain_answer(
                AnswerExplanationRequest(
                    question=request.question or request.query or "",
                    subject=request.subject,
                    predicate=str(request.predicate or ""),
                    as_of=request.as_of,
                    evidence_limit=request.evidence_limit,
                    event_limit=request.event_limit,
                )
            ),
        )
    return {
        "event_type": "memory_read_abstained",
        "summary": "Spark memory read abstained.",
        "facts": {
            "memory_role": "unknown",
            "method": method or "memory_read",
            "reason": "unsupported_method",
            "record_count": 0,
            "retrieval_trace": {
                "operation": method or "memory_read",
                "subject": request.subject,
                "predicate": request.predicate,
                "entity_key": request.entity_key,
                "predicate_prefix": request.predicate_prefix,
                "query": request.query,
                "question": request.question,
                "as_of": request.as_of,
            },
        },
    }


def _materialize_lookup_result(*, method: str, result: Any) -> dict[str, Any]:
    facts = {
        "memory_role": result.memory_role,
        "memory_roles": list((result.trace or {}).get("memory_roles") or []),
        "primary_memory_role": str((result.trace or {}).get("primary_memory_role") or result.memory_role),
        "canonical_memory_roles": list((result.trace or {}).get("canonical_memory_roles") or []),
        "provenance_roles": list((result.trace or {}).get("provenance_roles") or []),
        "method": method,
        "record_count": len(result.provenance),
        "retrieval_trace": dict(result.trace),
    }
    if result.found:
        return {
            "event_type": "memory_read_succeeded",
            "summary": "Spark memory read completed.",
            "facts": facts,
        }
    reason = str((result.trace or {}).get("reason") or "").strip() or None
    if reason:
        facts["reason"] = reason
    return {
        "event_type": "memory_read_abstained",
        "summary": "Spark memory read abstained.",
        "facts": facts,
    }


def _materialize_retrieval_result(*, method: str, result: Any) -> dict[str, Any]:
    first_role = result.items[0].memory_role if result.items else "unknown"
    facts = {
        "memory_role": first_role,
        "memory_roles": list((result.trace or {}).get("memory_roles") or []),
        "primary_memory_role": str((result.trace or {}).get("primary_memory_role") or first_role),
        "canonical_memory_roles": list((result.trace or {}).get("canonical_memory_roles") or []),
        "method": method,
        "record_count": len(result.items),
        "retrieval_trace": dict(result.trace),
    }
    reason = str((result.trace or {}).get("reason") or "").strip() or None
    if result.items:
        return {
            "event_type": "memory_read_succeeded",
            "summary": "Spark memory read completed.",
            "facts": facts,
        }
    if reason:
        facts["reason"] = reason
    return {
        "event_type": "memory_read_abstained",
        "summary": "Spark memory read abstained.",
        "facts": facts,
    }


def _materialize_explanation_result(*, method: str, result: Any) -> dict[str, Any]:
    answer_explanation = {
        "answer": result.answer,
        "explanation": result.explanation,
        "evidence": [_retrieved_record_dict(item) for item in result.evidence],
        "events": [_retrieved_record_dict(item) for item in result.events],
    }
    facts = {
        "memory_role": result.memory_role,
        "memory_roles": list((result.trace or {}).get("memory_roles") or []),
        "primary_memory_role": str((result.trace or {}).get("primary_memory_role") or result.memory_role),
        "canonical_memory_roles": list((result.trace or {}).get("canonical_memory_roles") or []),
        "provenance_roles": list((result.trace or {}).get("provenance_roles") or []),
        "method": method,
        "record_count": len(result.provenance),
        "answer_explanation": answer_explanation,
        "retrieval_trace": dict(result.trace),
    }
    if result.found:
        return {
            "event_type": "memory_read_succeeded",
            "summary": "Spark memory read completed.",
            "facts": facts,
        }
    return {
        "event_type": "memory_read_abstained",
        "summary": "Spark memory read abstained.",
        "facts": facts,
    }


def _retrieved_record_dict(item: Any) -> dict[str, Any]:
    return {
        "memory_role": item.memory_role,
        "subject": item.subject,
        "predicate": item.predicate,
        "text": item.text,
        "session_id": item.session_id,
        "turn_ids": list(item.turn_ids),
        "timestamp": item.timestamp,
        "observation_id": getattr(item, "observation_id", None),
        "event_id": getattr(item, "event_id", None),
        "retention_class": getattr(item, "retention_class", None),
        "lifecycle": dict(getattr(item, "lifecycle", {}) or {}),
        "metadata": dict(item.metadata),
    }
