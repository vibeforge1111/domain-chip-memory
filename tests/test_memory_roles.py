from domain_chip_memory.memory_roles import source_memory_role


def test_source_memory_role_maps_runtime_sources_to_normalized_roles():
    assert source_memory_role("current_state_memory") == "current_state"
    assert source_memory_role("current_state_deletion") == "state_deletion"
    assert source_memory_role("evidence_memory") == "structured_evidence"
    assert source_memory_role("belief_memory") == "belief"
    assert source_memory_role("event_calendar") == "event"
    assert source_memory_role("aggregate_memory") == "aggregate"
    assert source_memory_role("referential_ambiguity") == "ambiguity"
    assert source_memory_role("temporal_ambiguity") == "ambiguity"
    assert source_memory_role("temporal_atom_router") == "aggregate"


def test_source_memory_role_falls_back_to_unknown_for_untyped_sources():
    assert source_memory_role(None) == "unknown"
    assert source_memory_role("") == "unknown"
    assert source_memory_role("unsupported_source") == "unknown"
