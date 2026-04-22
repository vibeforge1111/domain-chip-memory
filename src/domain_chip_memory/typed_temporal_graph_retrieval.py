from __future__ import annotations

from dataclasses import dataclass

from .contracts import NormalizedQuestion
from .memory_extraction import _tokenize
from .typed_temporal_graph_memory import RelationshipFact, TemporalMemoryEvent, TypedTemporalGraphMemory


@dataclass(frozen=True)
class TypedTemporalGraphHit:
    hit_id: str
    hit_type: str
    score: float
    text: str
    metadata: dict[str, object]


def _question_tokens(question: str) -> set[str]:
    return set(_tokenize(question))


def _subject_name_matches(question_lower: str, subject_entity_id: str) -> bool:
    return subject_entity_id and subject_entity_id.replace("_", " ") in question_lower


def _relationship_fact_score(question: NormalizedQuestion, fact: RelationshipFact) -> float:
    question_lower = question.question.lower()
    question_tokens = _question_tokens(question.question)
    provenance_tokens = set(_tokenize(fact.provenance.source_span))
    score = 0.0
    score += 2.0 * float(len(question_tokens.intersection(provenance_tokens)))
    if _subject_name_matches(question_lower, fact.subject_entity_id):
        score += 6.0
    if fact.relation_type and fact.relation_type in question_lower:
        score += 10.0
    if fact.object_label and fact.object_label.lower() in question_lower:
        score += 4.0
    if question_lower.startswith(("who ", "what ", "is ", "does ", "do ")):
        score += 1.0
    return score


def _temporal_event_score(question: NormalizedQuestion, event: TemporalMemoryEvent) -> float:
    question_lower = question.question.lower()
    question_tokens = _question_tokens(question.question)
    provenance_tokens = set(_tokenize(event.provenance.source_span))
    score = 0.0
    score += 2.0 * float(len(question_tokens.intersection(provenance_tokens)))
    if _subject_name_matches(question_lower, event.subject_entity_id):
        score += 6.0
    if event.relation_type and event.relation_type in question_lower:
        score += 10.0
    if question_lower.startswith("when ") and event.time_anchor is not None:
        score += 12.0
    if "pass away" in question_lower and event.event_type == "loss_event":
        score += 10.0
    if any(token in question_lower for token in ("peace", "support", "grieving", "comfort")) and event.event_type == "support_event":
        score += 8.0
    if event.item_type and event.item_type in question_lower:
        score += 6.0
    return score


def retrieve_typed_temporal_graph_hits(
    question: NormalizedQuestion,
    graph: TypedTemporalGraphMemory,
    *,
    limit: int = 6,
) -> list[TypedTemporalGraphHit]:
    hits: list[TypedTemporalGraphHit] = []
    for fact in graph.relationship_facts:
        score = _relationship_fact_score(question, fact)
        if score <= 0:
            continue
        hits.append(
            TypedTemporalGraphHit(
                hit_id=fact.fact_id,
                hit_type="relationship_fact",
                score=score,
                text=fact.provenance.source_span,
                metadata={
                    "subject_entity_id": fact.subject_entity_id,
                    "relation_type": fact.relation_type,
                    "object_label": fact.object_label,
                    "session_id": fact.provenance.session_id,
                    "turn_id": fact.provenance.turn_id,
                },
            )
        )
    for event in graph.temporal_events:
        score = _temporal_event_score(question, event)
        if score <= 0:
            continue
        hits.append(
            TypedTemporalGraphHit(
                hit_id=event.event_id,
                hit_type="temporal_event",
                score=score,
                text=event.provenance.source_span,
                metadata={
                    "subject_entity_id": event.subject_entity_id,
                    "event_type": event.event_type,
                    "relation_type": event.relation_type,
                    "object_label": event.object_label,
                    "time_normalized": event.time_anchor.normalized_expression if event.time_anchor else "",
                    "support_kind": event.support_kind,
                    "session_id": event.provenance.session_id,
                    "turn_id": event.provenance.turn_id,
                },
            )
        )
    return sorted(hits, key=lambda hit: (-hit.score, hit.hit_id))[:limit]
