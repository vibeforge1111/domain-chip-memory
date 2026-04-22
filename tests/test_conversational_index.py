from pathlib import Path

from domain_chip_memory.loaders import load_locomo_json
from domain_chip_memory.memory_conversational_index import build_conversational_index


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
