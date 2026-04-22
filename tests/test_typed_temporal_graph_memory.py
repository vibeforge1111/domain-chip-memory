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


def test_build_typed_temporal_graph_memory_promotes_alias_binding_for_conv42():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-42"
    )

    graph = build_typed_temporal_graph_memory(sample)

    assert any(
        binding.alias == "Jo"
        and binding.canonical_name == "Joanna"
        and "hey jo" in binding.provenance.source_span.lower()
        for binding in graph.alias_bindings
    )


def test_build_typed_temporal_graph_memory_promotes_commitment_record_for_conv26():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-26"
    )

    graph = build_typed_temporal_graph_memory(sample)

    assert any(
        record.trigger == "i'm going to"
        and record.time_anchor is not None
        and record.time_anchor.normalized_expression == "this month"
        and "transgender conference" in record.provenance.source_span.lower()
        for record in graph.commitment_records
    )


def test_build_typed_temporal_graph_memory_promotes_negation_and_reported_speech_records():
    samples = load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
    calvin_sample = next(
        sample
        for sample in samples
        if any("never been to boston before" in turn.text.lower() for session in sample.sessions for turn in session.turns)
    )
    tim_sample = next(
        sample
        for sample in samples
        if any("the doctor said it's not too serious" in turn.text.lower() for session in sample.sessions for turn in session.turns)
    )

    calvin_graph = build_typed_temporal_graph_memory(calvin_sample)
    tim_graph = build_typed_temporal_graph_memory(tim_sample)

    assert any(
        record.negation_cue == "never"
        and "never been to boston before" in record.claim_text.lower()
        for record in calvin_graph.negation_records
    )
    assert any(
        record.speech_verb == "said"
        and "it's not too serious" in record.reported_content.lower()
        for record in tim_graph.reported_speech_records
    )


def test_build_typed_temporal_graph_memory_promotes_unknown_record():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if any("can't remember such a game" in turn.text.lower() for session in record.sessions for turn in session.turns)
    )

    graph = build_typed_temporal_graph_memory(sample)

    assert any(
        record.uncertainty_cue == "can't_remember"
        and "can't remember such a game" in record.claim_text.lower()
        for record in graph.unknown_records
    )
