from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import JsonDict, NormalizedBenchmarkSample
from .memory_conversational_index import ConversationalIndexEntry, build_conversational_index

_NOISY_RELATIONSHIP_OBJECT_LABELS = {
    "got",
    "had",
    "has",
    "have",
    "is",
    "was",
    "went",
}


@dataclass(frozen=True)
class ProvenanceSpan:
    session_id: str
    turn_id: str
    speaker: str
    timestamp: str | None
    source_span: str
    turn_text: str


@dataclass(frozen=True)
class PersonEntity:
    entity_id: str
    canonical_name: str
    aliases: tuple[str, ...] = ()
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class TimeAnchor:
    raw_expression: str
    normalized_expression: str
    anchor_timestamp: str | None
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class RelationshipFact:
    fact_id: str
    subject_entity_id: str
    relation_type: str
    object_label: str
    provenance: ProvenanceSpan
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class AliasBinding:
    binding_id: str
    subject_entity_id: str
    alias: str
    canonical_name: str
    provenance: ProvenanceSpan
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class CommitmentRecord:
    commitment_id: str
    subject_entity_id: str
    trigger: str
    time_anchor: TimeAnchor | None
    provenance: ProvenanceSpan
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class NegationRecord:
    negation_id: str
    subject_entity_id: str
    negation_cue: str
    claim_text: str
    provenance: ProvenanceSpan
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class ReportedSpeechRecord:
    record_id: str
    subject_entity_id: str
    speech_verb: str
    reported_content: str
    provenance: ProvenanceSpan
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class UnknownRecord:
    record_id: str
    subject_entity_id: str
    uncertainty_cue: str
    claim_text: str
    provenance: ProvenanceSpan
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class TemporalMemoryEvent:
    event_id: str
    event_type: str
    subject_entity_id: str
    relation_type: str
    object_label: str
    item_type: str
    support_kind: str
    time_anchor: TimeAnchor | None
    provenance: ProvenanceSpan
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class TypedTemporalGraphMemory:
    sample_id: str
    entities: tuple[PersonEntity, ...]
    alias_bindings: tuple[AliasBinding, ...]
    relationship_facts: tuple[RelationshipFact, ...]
    commitment_records: tuple[CommitmentRecord, ...]
    negation_records: tuple[NegationRecord, ...]
    reported_speech_records: tuple[ReportedSpeechRecord, ...]
    unknown_records: tuple[UnknownRecord, ...]
    temporal_events: tuple[TemporalMemoryEvent, ...]
    metadata: JsonDict = field(default_factory=dict)


def _canonical_entity_id(label: str) -> str:
    normalized = "".join(char if char.isalnum() else "_" for char in label.strip().lower())
    normalized = normalized.strip("_")
    return normalized or "unknown"


def _speaker_entities(sample: NormalizedBenchmarkSample) -> dict[str, PersonEntity]:
    entities: dict[str, PersonEntity] = {}
    for session in sample.sessions:
        for turn in session.turns:
            speaker = turn.speaker.strip()
            if not speaker:
                continue
            entity_id = _canonical_entity_id(speaker)
            if entity_id in entities:
                continue
            entities[entity_id] = PersonEntity(
                entity_id=entity_id,
                canonical_name=speaker,
                aliases=(speaker.lower(),),
                metadata={"entity_kind": "speaker"},
            )
    return entities


def _entity_for_label(
    entities: dict[str, PersonEntity],
    *,
    label: str,
    entity_kind: str,
) -> PersonEntity:
    entity_id = _canonical_entity_id(label)
    existing = entities.get(entity_id)
    if existing is not None:
        return existing
    entity = PersonEntity(
        entity_id=entity_id,
        canonical_name=label,
        aliases=(label.lower(),),
        metadata={"entity_kind": entity_kind},
    )
    entities[entity_id] = entity
    return entity


def _entry_provenance(entry: ConversationalIndexEntry) -> ProvenanceSpan:
    return ProvenanceSpan(
        session_id=entry.session_id,
        turn_id=entry.turn_id,
        speaker=str(entry.metadata.get("speaker", "")),
        timestamp=entry.timestamp,
        source_span=str(entry.metadata.get("source_span", "")).strip() or entry.text.strip(),
        turn_text=entry.text,
    )


def _entry_time_anchor(entry: ConversationalIndexEntry) -> TimeAnchor | None:
    raw_expression = str(entry.metadata.get("time_expression_raw", "")).strip()
    normalized_expression = str(entry.metadata.get("time_normalized", "")).strip()
    if not raw_expression and not normalized_expression:
        return None
    return TimeAnchor(
        raw_expression=raw_expression,
        normalized_expression=normalized_expression or raw_expression,
        anchor_timestamp=entry.timestamp,
        metadata={},
    )


def _normalize_object_label(*, relation_type: str, object_label: str) -> str:
    normalized = object_label.strip()
    if normalized.lower() in _NOISY_RELATIONSHIP_OBJECT_LABELS:
        return relation_type
    return normalized


def build_typed_temporal_graph_memory(sample: NormalizedBenchmarkSample) -> TypedTemporalGraphMemory:
    index_entries = build_conversational_index(sample)
    entities = _speaker_entities(sample)
    alias_bindings: list[AliasBinding] = []
    relationship_facts: list[RelationshipFact] = []
    commitment_records: list[CommitmentRecord] = []
    negation_records: list[NegationRecord] = []
    reported_speech_records: list[ReportedSpeechRecord] = []
    unknown_records: list[UnknownRecord] = []
    temporal_events: list[TemporalMemoryEvent] = []

    for entry in index_entries:
        if entry.entry_type != "typed_atom":
            continue
        subject_label = str(entry.metadata.get("speaker", "")).strip() or entry.subject
        subject_entity = _entity_for_label(entities, label=subject_label, entity_kind="speaker")
        relation_type = str(entry.metadata.get("relation_type", "")).strip()
        other_entity_label = _normalize_object_label(
            relation_type=relation_type,
            object_label=str(entry.metadata.get("other_entity", "")).strip() or relation_type,
        )
        provenance = _entry_provenance(entry)

        if entry.predicate == "relationship_edge":
            object_label = other_entity_label or "unknown"
            _entity_for_label(entities, label=object_label, entity_kind="relationship_target")
            relationship_facts.append(
                RelationshipFact(
                    fact_id=entry.entry_id,
                    subject_entity_id=subject_entity.entity_id,
                    relation_type=relation_type or "related_to",
                    object_label=object_label,
                    provenance=provenance,
                    metadata={},
                )
            )
            continue

        if entry.predicate == "alias_binding":
            canonical_name = str(entry.metadata.get("canonical_name", "")).strip()
            alias = str(entry.metadata.get("alias", "")).strip()
            if canonical_name:
                _entity_for_label(entities, label=canonical_name, entity_kind="speaker_alias_target")
            alias_bindings.append(
                AliasBinding(
                    binding_id=entry.entry_id,
                    subject_entity_id=subject_entity.entity_id,
                    alias=alias,
                    canonical_name=canonical_name,
                    provenance=provenance,
                    metadata={},
                )
            )
            continue

        if entry.predicate == "commitment_event":
            commitment_records.append(
                CommitmentRecord(
                    commitment_id=entry.entry_id,
                    subject_entity_id=subject_entity.entity_id,
                    trigger=str(entry.metadata.get("commitment_trigger", "")).strip(),
                    time_anchor=_entry_time_anchor(entry),
                    provenance=provenance,
                    metadata={},
                )
            )
            continue

        if entry.predicate == "negation_record":
            negation_records.append(
                NegationRecord(
                    negation_id=entry.entry_id,
                    subject_entity_id=subject_entity.entity_id,
                    negation_cue=str(entry.metadata.get("negation_cue", "")).strip(),
                    claim_text=str(entry.metadata.get("claim_text", "")).strip() or provenance.source_span,
                    provenance=provenance,
                    metadata={},
                )
            )
            continue

        if entry.predicate == "reported_speech":
            reported_speech_records.append(
                ReportedSpeechRecord(
                    record_id=entry.entry_id,
                    subject_entity_id=subject_entity.entity_id,
                    speech_verb=str(entry.metadata.get("speech_verb", "")).strip(),
                    reported_content=str(entry.metadata.get("reported_content", "")).strip(),
                    provenance=provenance,
                    metadata={},
                )
            )
            continue

        if entry.predicate == "unknown_record":
            unknown_records.append(
                UnknownRecord(
                    record_id=entry.entry_id,
                    subject_entity_id=subject_entity.entity_id,
                    uncertainty_cue=str(entry.metadata.get("uncertainty_cue", "")).strip(),
                    claim_text=str(entry.metadata.get("claim_text", "")).strip() or provenance.source_span,
                    provenance=provenance,
                    metadata={},
                )
            )
            continue

        if entry.predicate not in {"loss_event", "gift_event", "support_event", "visit_event"}:
            continue
        if other_entity_label:
            _entity_for_label(entities, label=other_entity_label, entity_kind="relationship_target")
        temporal_events.append(
            TemporalMemoryEvent(
                event_id=entry.entry_id,
                event_type=entry.predicate,
                subject_entity_id=subject_entity.entity_id,
                relation_type=relation_type,
                object_label=other_entity_label,
                item_type=str(entry.metadata.get("item_type", "")).strip(),
                support_kind=str(entry.metadata.get("support_kind", "")).strip(),
                time_anchor=_entry_time_anchor(entry),
                provenance=provenance,
                metadata={},
            )
        )

    return TypedTemporalGraphMemory(
        sample_id=sample.sample_id,
        entities=tuple(sorted(entities.values(), key=lambda entity: entity.entity_id)),
        alias_bindings=tuple(alias_bindings),
        relationship_facts=tuple(relationship_facts),
        commitment_records=tuple(commitment_records),
        negation_records=tuple(negation_records),
        reported_speech_records=tuple(reported_speech_records),
        unknown_records=tuple(unknown_records),
        temporal_events=tuple(temporal_events),
        metadata={"source": "conversational_index_typed_atoms"},
    )


def relationship_facts_for_subject(
    graph: TypedTemporalGraphMemory,
    *,
    subject_entity_id: str,
    relation_type: str | None = None,
) -> list[RelationshipFact]:
    return [
        fact
        for fact in graph.relationship_facts
        if fact.subject_entity_id == subject_entity_id
        and (relation_type is None or fact.relation_type == relation_type)
    ]


def temporal_events_for_subject(
    graph: TypedTemporalGraphMemory,
    *,
    subject_entity_id: str,
    event_type: str | None = None,
    relation_type: str | None = None,
) -> list[TemporalMemoryEvent]:
    return [
        event
        for event in graph.temporal_events
        if event.subject_entity_id == subject_entity_id
        and (event_type is None or event.event_type == event_type)
        and (relation_type is None or event.relation_type == relation_type)
    ]
