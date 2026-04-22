from pathlib import Path

from domain_chip_memory.loaders import load_locomo_json
from domain_chip_memory.typed_temporal_graph_memory import (
    build_typed_temporal_graph_memory,
    relationship_facts_for_subject,
    temporal_events_for_subject,
)


def test_build_typed_temporal_graph_memory_preserves_relationship_and_temporal_provenance_for_conv48():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-48"
    )

    graph = build_typed_temporal_graph_memory(sample)

    assert any(entity.canonical_name == "Deborah" for entity in graph.entities)
    assert any(fact.relation_type == "mother" for fact in graph.relationship_facts)
    assert any(
        event.event_type == "loss_event"
        and event.relation_type == "mother"
        and event.time_anchor is not None
        and event.time_anchor.normalized_expression == "a few years before 2023"
        and "passed away" in event.provenance.source_span.lower()
        for event in graph.temporal_events
    )
    assert any(
        event.event_type == "gift_event"
        and event.item_type == "pendant"
        and event.time_anchor is not None
        and event.time_anchor.normalized_expression == "in 2010"
        and "pendant" in event.provenance.source_span.lower()
        for event in graph.temporal_events
    )
    assert any(
        event.event_type == "support_event"
        and event.support_kind == "place"
        and "peace" in event.provenance.source_span.lower()
        for event in graph.temporal_events
    )


def test_typed_temporal_graph_memory_helpers_filter_subject_and_event_family_for_conv48():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-48"
    )

    graph = build_typed_temporal_graph_memory(sample)
    deborah = next(entity for entity in graph.entities if entity.canonical_name == "Deborah")

    mother_relationships = relationship_facts_for_subject(
        graph,
        subject_entity_id=deborah.entity_id,
        relation_type="mother",
    )
    mother_events = temporal_events_for_subject(
        graph,
        subject_entity_id=deborah.entity_id,
        relation_type="mother",
    )

    assert mother_relationships
    assert any(event.event_type == "loss_event" for event in mother_events)
    assert any(event.event_type == "support_event" for event in mother_events)


def test_build_typed_temporal_graph_memory_captures_exact_fact_family_for_conv49():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-49"
    )

    graph = build_typed_temporal_graph_memory(sample)

    assert any(entity.canonical_name == "Evan" for entity in graph.entities)
    assert all(entity.canonical_name != "Got" for entity in graph.entities)
    assert any(
        fact.subject_entity_id == "evan"
        and fact.relation_type == "friend"
        and fact.object_label == "friend"
        for fact in graph.relationship_facts
    )
