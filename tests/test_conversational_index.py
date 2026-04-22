from pathlib import Path

from domain_chip_memory.loaders import load_locomo_json
from domain_chip_memory.memory_conversational_index import build_conversational_index
from domain_chip_memory.memory_conversational_retrieval import retrieve_conversational_entries
from domain_chip_memory.memory_conversational_shadow_eval import (
    build_fused_conversational_hybrid_shadow_packets,
    build_fused_conversational_shadow_answer_eval,
    build_entity_linked_hybrid_shadow_packets,
    build_entity_linked_shadow_answer_eval,
    build_exact_turn_shadow_answer_eval,
    build_exact_turn_hybrid_shadow_packets,
    build_lexical_hybrid_shadow_packets,
    build_lexical_shadow_answer_eval,
    build_multi_shadow_answer_eval,
    build_typed_graph_shadow_answer_eval,
    build_typed_graph_hybrid_shadow_packets,
    _expected_answer_coverage,
    _question_prefers_exact_conversational_evidence,
    _question_uses_conversational_hybrid,
    build_conversational_shadow_eval,
)
from domain_chip_memory.runner import _build_prediction


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


def test_build_conversational_index_extracts_negation_record_for_boston_history():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if any("never been to boston before" in turn.text.lower() for session in record.sessions for turn in session.turns)
    )

    entries = build_conversational_index(sample)

    assert any(
        entry.predicate == "negation_record"
        and entry.metadata.get("negation_cue") == "never"
        and "never been to boston before" in str(entry.metadata.get("claim_text", "")).lower()
        for entry in entries
    )


def test_build_conversational_index_extracts_reported_speech_for_tim_injury():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if any("the doctor said it's not too serious" in turn.text.lower() for session in record.sessions for turn in session.turns)
    )

    entries = build_conversational_index(sample)

    assert any(
        entry.predicate == "reported_speech"
        and entry.metadata.get("speech_verb") == "said"
        and "it's not too serious" in str(entry.metadata.get("reported_content", "")).lower()
        for entry in entries
    )


def test_build_conversational_index_extracts_unknown_record_for_conv47_memory_gap():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if any("can't remember such a game" in turn.text.lower() for session in record.sessions for turn in session.turns)
    )

    entries = build_conversational_index(sample)

    assert any(
        entry.predicate == "unknown_record"
        and entry.metadata.get("uncertainty_cue") == "can't_remember"
        and "can't remember such a game" in str(entry.metadata.get("claim_text", "")).lower()
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
    assert packet.retrieved_context_items[0].strategy == "exact_turn_conversational_shadow"
    assert "conversational_evidence:" in packet.assembled_context.lower()
    assert "answer_candidate:" not in packet.assembled_context.lower()
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


def test_typed_graph_hybrid_shadow_packets_add_alias_binding_evidence_for_conv42():
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
    subset = [
        type(sample)(
            benchmark_name=sample.benchmark_name,
            sample_id=sample.sample_id,
            sessions=sample.sessions,
            questions=[question],
            metadata=sample.metadata,
        )
    ]

    _, packets = build_typed_graph_hybrid_shadow_packets(subset, graph_limit=4)
    packet = packets[0]

    assert packet.baseline_name == "summary_synthesis_memory_typed_graph_shadow"
    assert packet.metadata["graph_item_count"] > 0
    assert packet.retrieved_context_items[0].strategy == "typed_temporal_graph_shadow"
    assert any(item.strategy == "typed_temporal_graph_shadow" for item in packet.retrieved_context_items)
    assert "graph_evidence: hey jo" in packet.assembled_context.lower()
    assert "answer_candidate: jo" in packet.assembled_context.lower()
    assert packet.answer_candidates
    assert packet.answer_candidates[0].text == "Jo"
    assert packet.answer_candidates[0].metadata["source_kind"] == "typed_temporal_graph"


def test_typed_graph_hybrid_shadow_packets_stay_summary_only_for_broad_synthesis_question():
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

    _, packets = build_typed_graph_hybrid_shadow_packets(subset, graph_limit=4)
    packet = packets[0]

    assert packet.metadata["graph_item_count"] == 0
    assert all(item.strategy != "typed_temporal_graph_shadow" for item in packet.retrieved_context_items)


def test_typed_graph_shadow_answer_eval_tracks_alias_binding_shadow_packets():
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
    subset = [
        type(sample)(
            benchmark_name=sample.benchmark_name,
            sample_id=sample.sample_id,
            sessions=sample.sessions,
            questions=[question],
            metadata=sample.metadata,
        )
    ]

    report = build_typed_graph_shadow_answer_eval(subset, graph_limit=4, provider_name="heuristic")
    row = report["rows"][0]

    assert report["overall"]["provider_name"] == "heuristic_v1"
    assert row["question_prefers_typed_graph_evidence"] is True
    assert row["graph_hybrid_graph_item_count"] > 0
    assert "summary_answer" in row
    assert "graph_hybrid_answer" in row


def test_typed_graph_hybrid_shadow_packets_add_reported_speech_evidence_for_tim_question():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if any(question.question == "What did Tim say about his injury on 16 November, 2023?" for question in record.questions)
    )
    question = next(
        question
        for question in sample.questions
        if question.question == "What did Tim say about his injury on 16 November, 2023?"
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

    _, packets = build_typed_graph_hybrid_shadow_packets(subset, graph_limit=4)
    packet = packets[0]

    assert packet.metadata["graph_item_count"] > 0
    assert any(item.metadata.get("hit_type") == "reported_speech_record" for item in packet.retrieved_context_items)
    assert "doctor said it's not too serious" in packet.assembled_context.lower()
    assert "answer_candidate: the doctor said it's not too serious." in packet.assembled_context.lower()
    assert "synthesis:" not in packet.assembled_context.lower()
    assert "reflection:" not in packet.assembled_context.lower()
    assert "episode_observation:" not in packet.assembled_context.lower()
    assert not any(line.strip().startswith("evidence:") for line in packet.assembled_context.lower().splitlines())
    assert packet.answer_candidates[0].text == "The doctor said it's not too serious."


def test_typed_graph_hybrid_shadow_packets_add_unknown_evidence_for_memory_gap_question():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if any("can't remember such a game" in turn.text.lower() for session in record.sessions for turn in session.turns)
    )
    from domain_chip_memory.contracts import NormalizedQuestion

    question = NormalizedQuestion(
        question_id="synthetic-unknown-conv47",
        question="Can James remember such a game?",
        category="1",
        expected_answers=["No"],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={},
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

    _, packets = build_typed_graph_hybrid_shadow_packets(subset, graph_limit=4)
    packet = packets[0]

    assert packet.metadata["graph_item_count"] > 0
    assert any(item.metadata.get("hit_type") == "unknown_record" for item in packet.retrieved_context_items)
    assert "can't remember such a game" in packet.assembled_context.lower()
    assert "answer_candidate: unknown" in packet.assembled_context.lower()
    assert packet.answer_candidates[0].text == "unknown"


def test_typed_graph_prediction_projects_reported_speech_back_to_canonical_candidate():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-43"
    )
    question = next(
        question
        for question in sample.questions
        if question.question_id == "conv-43-qa-137"
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

    _, packets = build_typed_graph_hybrid_shadow_packets(subset, graph_limit=6)
    packet = packets[0]

    class _Provider:
        name = "codex"

    prediction = _build_prediction(
        packet,
        question=question,
        provider=_Provider(),
        answer="it's not too serious.",
        provider_metadata={},
    )

    assert prediction.predicted_answer == "The doctor said it's not too serious."
    assert prediction.is_correct is True


def test_typed_graph_shadow_answer_eval_projects_alias_binding_to_clean_answer():
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
    subset = [
        type(sample)(
            benchmark_name=sample.benchmark_name,
            sample_id=sample.sample_id,
            sessions=sample.sessions,
            questions=[question],
            metadata=sample.metadata,
        )
    ]

    report = build_typed_graph_shadow_answer_eval(subset, graph_limit=4, provider_name="heuristic")
    row = report["rows"][0]

    assert row["graph_hybrid_answer"] == "Jo"
    assert row["graph_hybrid_correct"] is True


def test_lexical_hybrid_shadow_packets_include_lexical_session_overlap_items():
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
    subset = [
        type(sample)(
            benchmark_name=sample.benchmark_name,
            sample_id=sample.sample_id,
            sessions=sample.sessions,
            questions=[question],
            metadata=sample.metadata,
        )
    ]

    _, packets = build_lexical_hybrid_shadow_packets(subset, top_k_sessions=2, fallback_sessions=1)
    packet = packets[0]

    assert packet.baseline_name == "summary_synthesis_memory_lexical_shadow"
    assert packet.metadata["lexical_item_count"] > 0
    assert any(item.strategy == "lexical_session_overlap" for item in packet.retrieved_context_items)


def test_lexical_shadow_answer_eval_reports_summary_and_lexical_outputs():
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
    subset = [
        type(sample)(
            benchmark_name=sample.benchmark_name,
            sample_id=sample.sample_id,
            sessions=sample.sessions,
            questions=[question],
            metadata=sample.metadata,
        )
    ]

    report = build_lexical_shadow_answer_eval(subset, top_k_sessions=2, fallback_sessions=1, provider_name="heuristic")
    row = report["rows"][0]

    assert report["overall"]["provider_name"] == "heuristic_v1"
    assert "summary_answer" in row
    assert "lexical_hybrid_answer" in row
    assert row["lexical_hybrid_item_count"] > 0


def test_entity_linked_hybrid_shadow_packets_promote_alias_binding_candidates():
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
    subset = [
        type(sample)(
            benchmark_name=sample.benchmark_name,
            sample_id=sample.sample_id,
            sessions=sample.sessions,
            questions=[question],
            metadata=sample.metadata,
        )
    ]

    _, packets = build_entity_linked_hybrid_shadow_packets(subset, entity_limit=6)
    packet = packets[0]

    assert packet.baseline_name == "summary_synthesis_memory_entity_linked_shadow"
    assert packet.metadata["entity_item_count"] > 0
    assert any(item.strategy == "entity_linked_conversational_shadow" for item in packet.retrieved_context_items)
    assert "answer_candidate: jo" in packet.assembled_context.lower()
    assert packet.answer_candidates[0].text == "Jo"
    assert packet.answer_candidates[0].metadata["source_kind"] == "entity_linked_conversational"


def test_entity_linked_shadow_answer_eval_reports_summary_and_entity_outputs():
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
    subset = [
        type(sample)(
            benchmark_name=sample.benchmark_name,
            sample_id=sample.sample_id,
            sessions=sample.sessions,
            questions=[question],
            metadata=sample.metadata,
        )
    ]

    report = build_entity_linked_shadow_answer_eval(subset, entity_limit=6, provider_name="heuristic")
    row = report["rows"][0]

    assert report["overall"]["provider_name"] == "heuristic_v1"
    assert "summary_answer" in row
    assert "entity_hybrid_answer" in row
    assert row["entity_hybrid_item_count"] > 0


def test_entity_linked_hybrid_shadow_packets_do_not_surface_alias_candidate_for_non_alias_question():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-50"
    )
    from domain_chip_memory.contracts import NormalizedQuestion

    question = NormalizedQuestion(
        question_id="synthetic-negation-conv50",
        question="Had Calvin been to Boston before?",
        category="1",
        expected_answers=["No"],
        evidence_session_ids=[],
        evidence_turn_ids=[],
        metadata={"synthetic_probe": "negation_record"},
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

    _, packets = build_entity_linked_hybrid_shadow_packets(subset, entity_limit=6)
    packet = packets[0]

    assert "answer_candidate: cal" not in packet.assembled_context.lower()
    assert not any(candidate.text == "Cal" for candidate in packet.answer_candidates)


def test_entity_linked_hybrid_shadow_packets_surface_reported_speech_candidate_for_tim_question():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-43"
    )
    question = next(
        question
        for question in sample.questions
        if question.question_id == "conv-43-qa-137"
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

    _, packets = build_entity_linked_hybrid_shadow_packets(subset, entity_limit=6)
    packet = packets[0]

    assert any(item.metadata.get("predicate") == "reported_speech" for item in packet.retrieved_context_items)
    assert "answer_candidate: the doctor said it's not too serious." in packet.assembled_context.lower()
    assert packet.answer_candidates[0].text == "The doctor said it's not too serious."


def test_fused_conversational_hybrid_shadow_packets_route_alias_questions_to_entity_lane():
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
    subset = [
        type(sample)(
            benchmark_name=sample.benchmark_name,
            sample_id=sample.sample_id,
            sessions=sample.sessions,
            questions=[question],
            metadata=sample.metadata,
        )
    ]

    _, packets = build_fused_conversational_hybrid_shadow_packets(subset, entity_limit=6, graph_limit=4)
    packet = packets[0]

    assert packet.baseline_name == "summary_synthesis_memory_fused_conversational_shadow"
    assert packet.metadata["shadow_selector"] == "entity_linked_first"
    assert packet.metadata["fused_variant_baseline"] == "summary_synthesis_memory_entity_linked_shadow"
    assert packet.answer_candidates[0].text == "Jo"


def test_fused_conversational_hybrid_shadow_packets_route_temporal_questions_to_graph_lane():
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
    subset = [
        type(sample)(
            benchmark_name=sample.benchmark_name,
            sample_id=sample.sample_id,
            sessions=sample.sessions,
            questions=[question],
            metadata=sample.metadata,
        )
    ]

    _, packets = build_fused_conversational_hybrid_shadow_packets(subset, entity_limit=6, graph_limit=6)
    packet = packets[0]

    assert packet.metadata["shadow_selector"] == "typed_graph_first"
    assert packet.metadata["fused_variant_baseline"] == "summary_synthesis_memory_typed_graph_shadow"
    assert packet.metadata["graph_item_count"] > 0


def test_fused_conversational_hybrid_shadow_packets_route_reported_speech_questions_to_graph_lane():
    sample = next(
        record
        for record in load_locomo_json(Path("benchmark_data/official/LoCoMo/data/locomo10.json"))
        if record.sample_id == "conv-43"
    )
    question = next(
        question
        for question in sample.questions
        if question.question_id == "conv-43-qa-137"
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

    _, packets = build_fused_conversational_hybrid_shadow_packets(subset, entity_limit=6, graph_limit=4)
    packet = packets[0]

    assert packet.metadata["shadow_selector"] == "typed_graph_first"
    assert packet.metadata["fused_variant_baseline"] == "summary_synthesis_memory_typed_graph_shadow"
    assert packet.answer_candidates[0].text == "The doctor said it's not too serious."


def test_fused_conversational_hybrid_shadow_packets_keep_summary_for_broad_synthesis_question():
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

    _, packets = build_fused_conversational_hybrid_shadow_packets(subset, entity_limit=6, graph_limit=6)
    packet = packets[0]

    assert packet.metadata["shadow_selector"] == "summary_backbone"
    assert packet.metadata["fused_variant_baseline"] == "summary_synthesis_memory"


def test_multi_shadow_answer_eval_reports_summary_exact_turn_and_graph_outputs():
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
    subset = [
        type(sample)(
            benchmark_name=sample.benchmark_name,
            sample_id=sample.sample_id,
            sessions=sample.sessions,
            questions=[question],
            metadata=sample.metadata,
        )
    ]

    report = build_multi_shadow_answer_eval(subset, provider_name="heuristic", conversational_limit=4, graph_limit=4)
    row = report["rows"][0]

    assert report["overall"]["provider_name"] == "heuristic_v1"
    assert "summary_answer" in row
    assert "exact_turn_answer" in row
    assert "entity_answer" in row
    assert "graph_answer" in row
    assert "fused_answer" in row
    assert row["graph_item_count"] > 0


def test_fused_conversational_shadow_answer_eval_reports_summary_and_fused_outputs():
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
    subset = [
        type(sample)(
            benchmark_name=sample.benchmark_name,
            sample_id=sample.sample_id,
            sessions=sample.sessions,
            questions=[question],
            metadata=sample.metadata,
        )
    ]

    report = build_fused_conversational_shadow_answer_eval(
        subset,
        entity_limit=6,
        graph_limit=4,
        provider_name="heuristic",
    )
    row = report["rows"][0]

    assert report["overall"]["provider_name"] == "heuristic_v1"
    assert "summary_answer" in row
    assert "fused_hybrid_answer" in row
    assert row["fused_hybrid_selected_item_count"] >= 0
