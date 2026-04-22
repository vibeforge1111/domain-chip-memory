from __future__ import annotations

from dataclasses import dataclass

from .contracts import NormalizedQuestion
from .memory_extraction import _tokenize
from .typed_temporal_graph_memory import (
    AliasBinding,
    CommitmentRecord,
    NegationRecord,
    ReportedSpeechRecord,
    RelationshipFact,
    TemporalMemoryEvent,
    TypedTemporalGraphMemory,
)


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


def _alias_binding_score(question: NormalizedQuestion, binding: AliasBinding) -> float:
    question_lower = question.question.lower()
    score = 0.0
    if "nickname" in question_lower:
        score += 12.0
    if binding.canonical_name and binding.canonical_name.lower() in question_lower:
        score += 10.0
    if _subject_name_matches(question_lower, binding.subject_entity_id):
        score += 6.0
    if binding.alias and binding.alias.lower() in question_lower:
        score += 2.0
    return score


def _commitment_record_score(question: NormalizedQuestion, record: CommitmentRecord) -> float:
    question_lower = question.question.lower()
    question_tokens = _question_tokens(question.question)
    provenance_tokens = set(_tokenize(record.provenance.source_span))
    score = 0.0
    score += 2.0 * float(len(question_tokens.intersection(provenance_tokens)))
    if _subject_name_matches(question_lower, record.subject_entity_id):
        score += 6.0
    if question_lower.startswith("when "):
        score += 8.0
    if record.time_anchor is not None:
        score += 8.0
        if record.time_anchor.normalized_expression and record.time_anchor.normalized_expression in question_lower:
            score += 2.0
    if any(token in question_lower for token in ("going to", "plan", "conference", "posted")):
        score += 6.0
    return score


def _negation_record_score(question: NormalizedQuestion, record: NegationRecord) -> float:
    question_lower = question.question.lower()
    question_tokens = _question_tokens(question.question)
    claim_tokens = set(_tokenize(record.claim_text))
    score = 0.0
    score += 2.0 * float(len(question_tokens.intersection(claim_tokens)))
    if _subject_name_matches(question_lower, record.subject_entity_id):
        score += 6.0
    if any(token in question_lower for token in ("ever", "before", "yet")):
        score += 8.0
    if any(token in question_lower for token in ("tried", "been", "had", "visited")):
        score += 4.0
    if record.negation_cue and record.negation_cue in {"never", "haven't", "hasn't", "didn't", "not"}:
        score += 4.0
    return score


def _reported_speech_record_score(question: NormalizedQuestion, record: ReportedSpeechRecord) -> float:
    question_lower = question.question.lower()
    question_tokens = _question_tokens(question.question)
    content_tokens = set(_tokenize(record.reported_content))
    provenance_tokens = set(_tokenize(record.provenance.source_span))
    score = 0.0
    score += 2.0 * float(len(question_tokens.intersection(content_tokens)))
    score += 1.0 * float(len(question_tokens.intersection(provenance_tokens)))
    if _subject_name_matches(question_lower, record.subject_entity_id):
        score += 4.0
    if question_lower.startswith("what did "):
        score += 10.0
    if any(token in question_lower for token in ("say", "said", "tell", "told")):
        score += 10.0
    if record.speech_verb and record.speech_verb.split()[0] in question_lower:
        score += 2.0
    if question.question_date and record.provenance.timestamp and question.question_date in record.provenance.timestamp:
        score += 12.0
    if "injury" in question_lower and "doctor" in record.provenance.source_span.lower():
        score += 8.0
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
    for binding in graph.alias_bindings:
        score = _alias_binding_score(question, binding)
        if score <= 0:
            continue
        hits.append(
            TypedTemporalGraphHit(
                hit_id=binding.binding_id,
                hit_type="alias_binding",
                score=score,
                text=binding.provenance.source_span,
                metadata={
                    "subject_entity_id": binding.subject_entity_id,
                    "alias": binding.alias,
                    "canonical_name": binding.canonical_name,
                    "session_id": binding.provenance.session_id,
                    "turn_id": binding.provenance.turn_id,
                },
            )
        )
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
    for record in graph.commitment_records:
        score = _commitment_record_score(question, record)
        if score <= 0:
            continue
        hits.append(
            TypedTemporalGraphHit(
                hit_id=record.commitment_id,
                hit_type="commitment_record",
                score=score,
                text=record.provenance.source_span,
                metadata={
                    "subject_entity_id": record.subject_entity_id,
                    "commitment_trigger": record.trigger,
                    "time_normalized": record.time_anchor.normalized_expression if record.time_anchor else "",
                    "session_id": record.provenance.session_id,
                    "turn_id": record.provenance.turn_id,
                },
            )
        )
    for record in graph.negation_records:
        score = _negation_record_score(question, record)
        if score <= 0:
            continue
        hits.append(
            TypedTemporalGraphHit(
                hit_id=record.negation_id,
                hit_type="negation_record",
                score=score,
                text=record.provenance.source_span,
                metadata={
                    "subject_entity_id": record.subject_entity_id,
                    "negation_cue": record.negation_cue,
                    "claim_text": record.claim_text,
                    "session_id": record.provenance.session_id,
                    "turn_id": record.provenance.turn_id,
                },
            )
        )
    for record in graph.reported_speech_records:
        score = _reported_speech_record_score(question, record)
        if score <= 0:
            continue
        hits.append(
            TypedTemporalGraphHit(
                hit_id=record.record_id,
                hit_type="reported_speech_record",
                score=score,
                text=record.provenance.source_span,
                metadata={
                    "subject_entity_id": record.subject_entity_id,
                    "speech_verb": record.speech_verb,
                    "reported_content": record.reported_content,
                    "session_id": record.provenance.session_id,
                    "turn_id": record.provenance.turn_id,
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
