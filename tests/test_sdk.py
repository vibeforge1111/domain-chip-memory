from domain_chip_memory import (
    AnswerExplanationRequest,
    CurrentStateRequest,
    EventRetrievalRequest,
    EvidenceRetrievalRequest,
    HistoricalStateRequest,
    MemoryWriteRequest,
    SparkMemorySDK,
    build_sdk_contract_summary,
)


def test_sdk_contract_summary_exposes_runtime_surface():
    payload = build_sdk_contract_summary()

    assert payload["runtime_class"] == "SparkMemorySDK"
    assert "write_observation" in payload["write_methods"]
    assert payload["write_operations"]["write_observation"] == ["auto", "create", "update", "delete", "purge"]
    assert payload["maintenance_methods"] == ["reconsolidate_manual_memory"]
    assert "get_current_state" in payload["read_methods"]


def test_sdk_instance_stores_request_scoped_runtime_configuration():
    sdk = SparkMemorySDK(
        runtime_memory_architecture="typed_temporal_graph",
        runtime_memory_provider="codex:gpt-5-codex",
    )

    assert sdk.runtime_memory_architecture == "typed_temporal_graph"
    assert sdk.runtime_memory_provider == "codex:gpt-5-codex"


def test_sdk_write_and_get_current_state():
    sdk = SparkMemorySDK()
    first_write = sdk.write_observation(
        MemoryWriteRequest(
            text="I live in London.",
            timestamp="2025-01-01T09:00:00Z",
        )
    )
    second_write = sdk.write_observation(
        MemoryWriteRequest(
            text="I moved to Dubai.",
            timestamp="2025-03-01T09:00:00Z",
        )
    )

    assert first_write.accepted is True
    assert second_write.accepted is True

    result = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))

    assert result.found is True
    assert result.value == "Dubai"
    assert result.memory_role == "current_state"
    assert result.provenance[0].memory_role == "current_state"


def test_sdk_write_and_get_current_state_for_founder_startup_and_hack_facts():
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="I am an entrepreneur.",
            timestamp="2025-01-01T09:00:00Z",
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="My startup is Seedify.",
            timestamp="2025-01-01T09:01:00Z",
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="We were hacked by North Korea.",
            timestamp="2025-01-01T09:02:00Z",
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="I am the founder of Spark Swarm.",
            timestamp="2025-01-01T09:03:00Z",
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="I am trying to survive the hack and revive the companies.",
            timestamp="2025-01-01T09:04:00Z",
        )
    )

    startup = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="startup_name"))
    attacker = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="hack_actor"))
    founder = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="founder_of"))
    mission = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="current_mission"))

    assert startup.found is True
    assert startup.value == "Seedify"
    assert attacker.found is True
    assert attacker.value == "North Korea"
    assert founder.found is True
    assert founder.value == "Spark Swarm"
    assert mission.found is True
    assert mission.value == "survive the hack and revive the companies"


def test_sdk_get_current_state_respects_deletion():
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="I live in Dubai.",
            timestamp="2025-01-01T09:00:00Z",
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="Please forget that I live in Dubai.",
            timestamp="2025-02-01T09:00:00Z",
        )
    )

    result = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))

    assert result.found is False
    assert result.memory_role == "state_deletion"
    assert result.provenance[0].memory_role == "state_deletion"


def test_sdk_get_historical_state_uses_as_of_cutoff():
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="I live in London.",
            timestamp="2025-01-01T09:00:00Z",
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="I moved to Dubai.",
            timestamp="2025-03-01T09:00:00Z",
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="I moved to Abu Dhabi.",
            timestamp="2025-06-01T09:00:00Z",
        )
    )

    result = sdk.get_historical_state(
        HistoricalStateRequest(
            subject="user",
            predicate="location",
            as_of="2025-05-01T00:00:00Z",
        )
    )

    assert result.found is True
    assert result.value == "Dubai"
    assert result.memory_role == "structured_evidence"


def test_sdk_explicit_current_state_observation_preserves_runtime_role() -> None:
    sdk = SparkMemorySDK()

    result = sdk.write_observation(
        MemoryWriteRequest(
            text="human:test profile.current_owner Nadia",
            operation="update",
            subject="human:test",
            predicate="profile.current_owner",
            value="Nadia",
            timestamp="2025-03-01T09:00:00Z",
            retention_class="active_state",
            valid_from="2025-03-01T09:00:00Z",
            metadata={"memory_role": "current_state", "source_surface": "builder_test"},
        )
    )

    assert result.accepted is True
    assert result.observations
    assert result.observations[0].memory_role == "current_state"
    assert result.trace["memory_roles"] == ["current_state"]
    assert result.trace["primary_memory_role"] == "current_state"


def test_sdk_explicit_delete_observation_preserves_state_deletion_role() -> None:
    sdk = SparkMemorySDK()

    result = sdk.write_observation(
        MemoryWriteRequest(
            text="delete profile.current_owner for human:test: Nadia",
            operation="delete",
            subject="human:test",
            predicate="profile.current_owner",
            value="Nadia",
            timestamp="2025-03-02T09:00:00Z",
            retention_class="active_state",
            deleted_at="2025-03-02T09:00:00Z",
            metadata={
                "memory_role": "current_state",
                "write_operation": "delete",
                "deleted_at": "2025-03-02T09:00:00Z",
                "source_surface": "builder_test",
            },
        )
    )

    assert result.accepted is True
    assert result.observations
    assert result.observations[0].memory_role == "state_deletion"
    assert result.trace["memory_roles"] == ["state_deletion"]
    assert result.trace["primary_memory_role"] == "state_deletion"


def test_sdk_retrieve_evidence_and_events_return_typed_roles():
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="I moved to Dubai.",
            timestamp="2025-03-01T09:00:00Z",
        )
    )

    evidence = sdk.retrieve_evidence(
        EvidenceRetrievalRequest(subject="user", predicate="location", limit=3)
    )
    events = sdk.retrieve_events(
        EventRetrievalRequest(subject="user", predicate="location", limit=3)
    )

    assert evidence.items
    assert evidence.items[0].memory_role == "structured_evidence"
    assert events.items
    assert events.items[0].memory_role == "event"


def test_sdk_rejects_unsupported_write_without_persisting_raw_residue():
    sdk = SparkMemorySDK()

    write_result = sdk.write_observation(
        MemoryWriteRequest(
            text="Hello there.",
            timestamp="2025-03-01T09:00:00Z",
        )
    )
    evidence = sdk.retrieve_evidence(EvidenceRetrievalRequest(limit=5))

    assert write_result.accepted is False
    assert write_result.unsupported_reason == "no_structured_memory_extracted"
    assert write_result.trace["persisted"] is False
    assert evidence.items == []


def test_sdk_accepts_explicit_episodic_raw_turn_write_and_retrieves_it():
    sdk = SparkMemorySDK()

    write_result = sdk.write_observation(
        MemoryWriteRequest(
            operation="create",
            subject="user",
            predicate="raw_turn",
            value="The pricing page felt confusing during the demo.",
            text="The pricing page felt confusing during the demo.",
            timestamp="2025-03-01T09:00:00Z",
            metadata={
                "memory_role": "episodic",
                "source_surface": "builder_test",
                "raw_episode": True,
            },
        )
    )
    evidence = sdk.retrieve_evidence(
        EvidenceRetrievalRequest(
            query="What happened during the demo?",
            subject="user",
            limit=3,
        )
    )

    assert write_result.accepted is True
    assert write_result.trace["persisted"] is True
    assert write_result.observations
    assert write_result.observations[0].memory_role == "episodic"
    assert evidence.items
    assert evidence.items[0].memory_role == "episodic"
    assert "demo" in evidence.items[0].text.lower()


def test_sdk_rejects_empty_write_request():
    sdk = SparkMemorySDK()

    write_result = sdk.write_observation(MemoryWriteRequest(text="   "))

    assert write_result.accepted is False
    assert write_result.unsupported_reason == "empty_text"
    assert write_result.trace["status"] == "unsupported_write"


def test_sdk_returns_invalid_request_trace_for_bad_lookup_and_limit():
    sdk = SparkMemorySDK()

    lookup = sdk.get_current_state(CurrentStateRequest(subject="user", predicate=""))
    retrieval = sdk.retrieve_evidence(EvidenceRetrievalRequest(limit=0))

    assert lookup.found is False
    assert lookup.trace["status"] == "invalid_request"
    assert lookup.trace["reason"] == "predicate_required"
    assert retrieval.items == []
    assert retrieval.trace["status"] == "invalid_request"
    assert retrieval.trace["reason"] == "limit_must_be_positive"


def test_sdk_supports_explicit_update_and_delete_operations():
    sdk = SparkMemorySDK()
    create_result = sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="user",
            predicate="location",
            value="London",
            timestamp="2025-01-01T09:00:00Z",
        )
    )
    update_result = sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="update",
            subject="user",
            predicate="location",
            value="Dubai",
            timestamp="2025-03-01T09:00:00Z",
        )
    )
    delete_result = sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="delete",
            subject="user",
            predicate="location",
            timestamp="2025-04-01T09:00:00Z",
        )
    )

    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))
    historical_state = sdk.get_historical_state(
        HistoricalStateRequest(subject="user", predicate="location", as_of="2025-03-15T00:00:00Z")
    )

    assert create_result.accepted is True
    assert update_result.accepted is True
    assert delete_result.accepted is True
    assert update_result.trace["write_operation"] == "update"
    assert delete_result.observations[0].memory_role == "state_deletion"
    assert current_state.found is False
    assert current_state.memory_role == "state_deletion"
    assert historical_state.found is True
    assert historical_state.value == "Dubai"


def test_sdk_purge_removes_matching_plaintext_and_keeps_redacted_tombstone():
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="I live in Dubai.",
            timestamp="2025-01-01T09:00:00Z",
        )
    )

    purge_result = sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="purge",
            subject="user",
            predicate="location",
            value="Dubai",
            timestamp="2025-02-01T09:00:00Z",
        )
    )
    snapshot = sdk.export_knowledge_base_snapshot()
    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))
    serialized_snapshot = str(snapshot)

    assert purge_result.accepted is True
    assert purge_result.trace["purge"]["session_turns_removed"] == 1
    assert purge_result.observations[0].text == "purge location for user"
    assert purge_result.observations[0].metadata["cryptographic_purge"] is True
    assert len(purge_result.observations[0].metadata["purge_digest"]) == 64
    assert purge_result.observations[0].metadata["deleted_value"] == ""
    assert current_state.found is False
    assert current_state.memory_role == "state_deletion"
    assert "I live in Dubai." not in serialized_snapshot
    assert "'deleted_value': 'Dubai'" not in serialized_snapshot


def test_sdk_supports_explicit_event_write_operation():
    sdk = SparkMemorySDK()

    write_result = sdk.write_event(
        MemoryWriteRequest(
            text="",
            operation="event",
            subject="user",
            predicate="move",
            value="Dubai",
            timestamp="2025-03-01T09:00:00Z",
        )
    )
    events = sdk.retrieve_events(EventRetrievalRequest(subject="user", predicate="move", limit=5))

    assert write_result.accepted is True
    assert write_result.trace["write_operation"] == "event"
    assert events.items
    assert events.items[0].memory_role == "event"


def test_sdk_rejects_unsupported_explicit_operation():
    sdk = SparkMemorySDK()

    write_result = sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="merge",
            subject="user",
            predicate="location",
            value="Dubai",
        )
    )

    assert write_result.accepted is False
    assert write_result.unsupported_reason == "unsupported_operation"
    assert write_result.trace["write_operation"] == "merge"


def test_sdk_reconsolidates_manual_memory_into_current_state_snapshot():
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="user",
            predicate="location",
            value="London",
            timestamp="2025-01-01T09:00:00Z",
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="update",
            subject="user",
            predicate="location",
            value="Dubai",
            timestamp="2025-03-01T09:00:00Z",
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="delete",
            subject="user",
            predicate="location",
            timestamp="2025-04-01T09:00:00Z",
        )
    )
    sdk.write_event(
        MemoryWriteRequest(
            text="",
            operation="event",
            subject="user",
            predicate="move",
            value="Dubai",
            timestamp="2025-03-01T09:00:00Z",
        )
    )

    maintenance = sdk.reconsolidate_manual_memory()
    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))
    historical_state = sdk.get_historical_state(
        HistoricalStateRequest(subject="user", predicate="location", as_of="2025-03-15T00:00:00Z")
    )

    assert maintenance.manual_observations_before == 3
    assert maintenance.manual_observations_after == 1
    assert maintenance.current_state_snapshot_count == 1
    assert maintenance.active_deletion_count == 1
    assert maintenance.manual_events_count == 1
    assert maintenance.trace["operation"] == "reconsolidate_manual_memory"
    assert current_state.found is False
    assert current_state.memory_role == "state_deletion"
    assert historical_state.found is True
    assert historical_state.value == "Dubai"


def test_sdk_reconsolidate_marks_stale_active_state_as_preserved():
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="user",
            predicate="current_plan",
            value="finish the SDK bridge",
            timestamp="2025-01-01T09:00:00Z",
            retention_class="active_state",
            metadata={"memory_role": "current_state", "revalidate_at": "2025-01-31T09:00:00Z"},
        )
    )

    maintenance = sdk.reconsolidate_manual_memory(now="2025-04-01T09:00:00Z")
    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="current_plan"))

    assert maintenance.active_state_stale_preserved_count == 1
    assert maintenance.trace["active_state_maintenance"]["stale_preserved"] == 1
    assert current_state.found is True
    assert current_state.provenance[0].metadata["active_state_maintenance_action"] == "stale_preserved"
    assert current_state.provenance[0].metadata["active_state_maintenance_reason"] == "past_revalidate_at"


def test_sdk_reconsolidate_marks_superseded_and_archived_active_state_entries():
    sdk = SparkMemorySDK()
    first_location = sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="user",
            predicate="location",
            value="London",
            timestamp="2025-01-01T09:00:00Z",
            retention_class="active_state",
            metadata={"memory_role": "current_state", "entity_key": "primary"},
        )
    )
    current_location = sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="update",
            subject="user",
            predicate="location",
            value="Dubai",
            timestamp="2025-03-01T09:00:00Z",
            retention_class="active_state",
            metadata={"memory_role": "current_state", "entity_key": "primary"},
        )
    )
    first_focus = sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="user",
            predicate="current_focus",
            value="SDK bridge",
            timestamp="2025-02-01T09:00:00Z",
            retention_class="active_state",
            metadata={"memory_role": "current_state", "entity_key": "primary"},
        )
    )
    delete_focus = sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="delete",
            subject="user",
            predicate="current_focus",
            timestamp="2025-04-01T09:00:00Z",
            retention_class="active_state",
        )
    )

    maintenance = sdk.reconsolidate_manual_memory(now="2025-04-02T09:00:00Z")
    observations_by_id = {entry.observation_id: entry for entry in sdk._manual_observations}

    assert maintenance.active_state_superseded_count == 1
    assert maintenance.active_state_archived_count == 1
    assert maintenance.active_state_still_current_count == 2
    assert observations_by_id[first_location.observations[0].observation_id].metadata[
        "active_state_maintenance_action"
    ] == "superseded"
    assert observations_by_id[current_location.observations[0].observation_id].metadata[
        "active_state_maintenance_action"
    ] == "still_current"
    assert observations_by_id[first_focus.observations[0].observation_id].metadata[
        "active_state_maintenance_action"
    ] == "archived"
    assert observations_by_id[delete_focus.observations[0].observation_id].metadata[
        "active_state_maintenance_action"
    ] == "still_current"


def test_sdk_explain_answer_returns_trace_and_support():
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="I moved to Dubai.",
            timestamp="2025-03-01T09:00:00Z",
        )
    )

    result = sdk.explain_answer(
        AnswerExplanationRequest(
            question="Where do I live now?",
            subject="user",
            predicate="location",
        )
    )

    assert result.found is True
    assert result.answer == "Dubai"
    assert result.memory_role == "current_state"
    assert result.provenance
    assert result.evidence
    assert result.events
    assert result.trace["operation"] == "explain_answer"
