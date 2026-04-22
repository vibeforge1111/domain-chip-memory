from pathlib import Path

from domain_chip_memory.loaders import load_locomo_json
from domain_chip_memory.memory_conversational_index import build_conversational_index
from domain_chip_memory.memory_conversational_retrieval import retrieve_conversational_entries
from domain_chip_memory.memory_conversational_shadow_eval import (
    build_exact_turn_shadow_answer_eval,
    build_exact_turn_hybrid_shadow_packets,
    _expected_answer_coverage,
    _question_prefers_exact_conversational_evidence,
    _question_uses_conversational_hybrid,
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


def test_build_conversational_index_extracts_alias_binding_for_conv42():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-42"
    )

    entries = build_conversational_index(sample)

    assert any(
        entry.predicate == "alias_binding"
        and entry.metadata.get("alias") == "Jo"
        and entry.metadata.get("canonical_name") == "Joanna"
        for entry in entries
    )


def test_build_conversational_index_extracts_commitment_event_for_conv26():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-26"
    )

    entries = build_conversational_index(sample)

    assert any(
        entry.predicate == "commitment_event"
        and entry.metadata.get("time_expression_raw") == "this month"
        and "transgender conference" in str(entry.metadata.get("source_span", "")).lower()
        for entry in entries
    )


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

    assert row["question_uses_conversational_hybrid"] is True
    assert row["summary_retrieval_covered"] is False
    assert row["conversational_retrieval_covered"] is True
    assert row["hybrid_retrieval_covered"] is True
    assert row["gated_hybrid_retrieval_covered"] is True
    assert row["exact_turn_hybrid_retrieval_covered"] is True


def test_question_uses_conversational_hybrid_stays_off_for_non_social_factoid():
    question = next(
        question
        for sample in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        for question in sample.questions
        if "eternal sunshine of the spotless mind" in question.question.lower()
    )

    assert _question_uses_conversational_hybrid(question) is False


def test_question_prefers_exact_conversational_evidence_for_exact_personal_fact():
    question = next(
        question
        for sample in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        for question in sample.questions
        if question.question == "How many Prius has Evan owned?"
    )

    assert _question_prefers_exact_conversational_evidence(question) is True


def test_question_prefers_exact_conversational_evidence_stays_off_for_broad_interest_synthesis():
    question = next(
        question
        for sample in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        for question in sample.questions
        if question.question == "What kind of interests do Joanna and Nate share?"
    )

    assert _question_prefers_exact_conversational_evidence(question) is False


def test_exact_turn_hybrid_shadow_packets_add_conversational_evidence_for_exact_fact_question():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-49"
    )
    question = next(
        question
        for question in sample.questions
        if question.question == "How many Prius has Evan owned?"
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

    _, packets = build_exact_turn_hybrid_shadow_packets(subset, conversational_limit=8)
    packet = packets[0]
    retrieval_text = "\n".join(item.text.lower() for item in packet.retrieved_context_items)

    assert packet.baseline_name == "summary_synthesis_memory_exact_turn_shadow"
    assert packet.metadata["shadow_selector"] == "exact_turn_conversational_evidence"
    assert packet.metadata["conversational_item_count"] > 0
    assert "conversational_evidence:" in packet.assembled_context.lower()
    assert "prius" in retrieval_text
    assert any(item.strategy == "exact_turn_conversational_shadow" for item in packet.retrieved_context_items)


def test_exact_turn_hybrid_shadow_packets_stay_summary_only_for_broad_synthesis_question():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-42"
    )
    question = next(
        question
        for question in sample.questions
        if question.question == "What kind of interests do Joanna and Nate share?"
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

    _, packets = build_exact_turn_hybrid_shadow_packets(subset, conversational_limit=8)
    packet = packets[0]

    assert packet.metadata["conversational_item_count"] == 0
    assert all(item.strategy != "exact_turn_conversational_shadow" for item in packet.retrieved_context_items)
    assert "conversational_evidence:" not in packet.assembled_context.lower()


def test_exact_turn_shadow_answer_eval_tracks_exact_fact_shadow_packets():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-49"
    )
    question = next(
        question
        for question in sample.questions
        if question.question == "How many Prius has Evan owned?"
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

    report = build_exact_turn_shadow_answer_eval(subset, conversational_limit=8, provider_name="heuristic")
    row = report["rows"][0]

    assert report["overall"]["provider_name"] == "heuristic_v1"
    assert row["question_prefers_exact_conversational_evidence"] is True
    assert row["hybrid_conversational_item_count"] > 0
    assert row["summary_answer"] == "two"
    assert row["hybrid_answer"] == "two"
    assert row["summary_correct"] is True
    assert row["hybrid_correct"] is True
