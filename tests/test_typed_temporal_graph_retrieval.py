from pathlib import Path

from domain_chip_memory.loaders import load_locomo_json
from domain_chip_memory.typed_temporal_graph_memory import build_typed_temporal_graph_memory
from domain_chip_memory.typed_temporal_graph_retrieval import retrieve_typed_temporal_graph_hits


def test_retrieve_typed_temporal_graph_hits_recovers_conv48_loss_anchor():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-48"
    )
    question = next(
        question
        for question in sample.questions
        if question.question == "When did Deborah`s mother pass away?"
    )

    graph = build_typed_temporal_graph_memory(sample)
    hits = retrieve_typed_temporal_graph_hits(question, graph, limit=4)

    assert hits
    assert hits[0].hit_type == "temporal_event"
    assert hits[0].metadata["event_type"] == "loss_event"
    assert hits[0].metadata["relation_type"] == "mother"
    assert hits[0].metadata["time_normalized"] == "a few years before 2023"
    assert "passed away" in hits[0].text.lower()


def test_retrieve_typed_temporal_graph_hits_recovers_conv48_support_spans():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-48"
    )
    question = next(
        question
        for question in sample.questions
        if question.question == "What helped Deborah find peace when grieving deaths of her loved ones?"
    )

    graph = build_typed_temporal_graph_memory(sample)
    hits = retrieve_typed_temporal_graph_hits(question, graph, limit=8)
    hit_text = "\n".join(hit.text.lower() for hit in hits)

    assert any(hit.metadata["event_type"] == "support_event" for hit in hits)
    assert "peace" in hit_text or "yoga" in hit_text or "flower" in hit_text


def test_retrieve_typed_temporal_graph_hits_avoids_bogus_conv49_friend_name():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-49"
    )
    question = next(
        question
        for question in sample.questions
        if question.question == "Which country was Evan visiting in May 2023?"
    )

    graph = build_typed_temporal_graph_memory(sample)
    hits = retrieve_typed_temporal_graph_hits(question, graph, limit=8)

    assert all(hit.metadata.get("object_label") != "Got" for hit in hits)


def test_retrieve_typed_temporal_graph_hits_recovers_conv42_alias_binding():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-42"
    )
    question = next(
        question
        for question in sample.questions
        if question.question == "What nickname does Nate use for Joanna?"
    )

    graph = build_typed_temporal_graph_memory(sample)
    hits = retrieve_typed_temporal_graph_hits(question, graph, limit=4)

    assert hits
    assert hits[0].hit_type == "alias_binding"
    assert hits[0].metadata["alias"] == "Jo"
    assert hits[0].metadata["canonical_name"] == "Joanna"
    assert "hey jo" in hits[0].text.lower()


def test_retrieve_typed_temporal_graph_hits_recovers_conv26_commitment_record():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-26"
    )
    question = next(
        question
        for question in sample.questions
        if question.question == "When is Caroline going to the transgender conference?"
    )

    graph = build_typed_temporal_graph_memory(sample)
    hits = retrieve_typed_temporal_graph_hits(question, graph, limit=4)

    assert hits
    assert hits[0].hit_type == "commitment_record"
    assert hits[0].metadata["time_normalized"] == "this month"
    assert "transgender conference" in hits[0].text.lower()
