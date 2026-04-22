from pathlib import Path

from domain_chip_memory.loaders import load_locomo_json
from domain_chip_memory.memory_conversational_index import build_conversational_index
from domain_chip_memory.memory_conversational_retrieval import retrieve_conversational_entries
from domain_chip_memory.memory_conversational_shadow_eval import (
    _expected_answer_coverage,
    build_conversational_shadow_eval,
)


def test_build_conversational_index_keeps_full_turns_and_typed_social_atoms_for_conv48():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-48"
    )

    entries = build_conversational_index(sample)

    assert any(
        entry.entry_type == "turn" and "my mom was interested in art" in entry.text.lower()
        for entry in entries
    )
    assert any(
        entry.entry_type == "turn" and "my mom had a big passion for cooking" in entry.text.lower()
        for entry in entries
    )
    assert any(
        entry.predicate == "loss_event"
        and entry.metadata.get("relation_type") == "mother"
        and entry.metadata.get("time_normalized") == "a few years before 2023"
        for entry in entries
    )
    assert any(
        entry.predicate == "gift_event"
        and entry.metadata.get("relation_type") == "mother"
        and entry.metadata.get("time_normalized") == "in 2010"
        for entry in entries
    )
    assert any(
        entry.predicate == "relationship_edge"
        and entry.metadata.get("relation_type") == "mother"
        for entry in entries
    )
    assert any(
        entry.predicate == "support_event"
        and "peace" in str(entry.metadata.get("source_span", "")).lower()
        for entry in entries
    )


def test_retrieve_conversational_entries_finds_full_family_hobby_turns_for_conv48():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-48"
    )
    question = next(
        question
        for question in sample.questions
        if question.question == "What were Deborah's mother's hobbies?"
    )

    entries = build_conversational_index(sample)
    hits = retrieve_conversational_entries(question, entries, limit=8)
    hit_text = "\n".join(entry.text.lower() for entry in hits)

    assert "reading was one of her hobbies" in hit_text
    assert "travel was also her great passion" in hit_text
    assert "my mom was interested in art" in hit_text
    assert "my mom had a big passion for cooking" in hit_text


def test_retrieve_conversational_entries_finds_typed_temporal_and_support_hits_for_conv48():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-48"
    )
    entries = build_conversational_index(sample)

    temporal_question = next(
        question
        for question in sample.questions
        if question.question == "When did Deborah`s mother pass away?"
    )
    temporal_hits = retrieve_conversational_entries(temporal_question, entries, limit=4)
    assert any(
        entry.predicate == "loss_event"
        and entry.metadata.get("time_normalized") == "a few years before 2023"
        for entry in temporal_hits
    )

    support_question = next(
        question
        for question in sample.questions
        if question.question == "What helped Deborah find peace when grieving deaths of her loved ones?"
    )
    support_hits = retrieve_conversational_entries(support_question, entries, limit=8)
    support_text = "\n".join(entry.text.lower() for entry in support_hits)
    assert "yoga" in support_text
    assert "old photo" in support_text or "old photos" in support_text or "last photo" in support_text
    assert "flower garden" in support_text or "roses and dahlias" in support_text


def test_expected_answer_coverage_accepts_multi_item_family_answers():
    assert _expected_answer_coverage(
        "My mom was interested in art. My mom had a big passion for cooking. Reading was one of her hobbies. Travel was also her great passion.",
        ["reading, traveling, art, cooking"],
    )


def test_conversational_shadow_eval_beats_summary_retrieval_on_conv48_family_hobby_question():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-48"
    )
    question = next(
        question
        for question in sample.questions
        if question.question == "What were Deborah's mother's hobbies?"
    )
    subset = [
        type(sample)(
            benchmark_name=sample.benchmark_name,
            sample_id=sample.sample_id,
            sessions=sample.sessions,
            questions=[question],
            metadata=sample.metadata,
        )
    ]

    report = build_conversational_shadow_eval(subset, conversational_limit=8)
    row = report["rows"][0]

    assert row["summary_retrieval_covered"] is False
    assert row["conversational_retrieval_covered"] is True
    assert row["hybrid_retrieval_covered"] is True
