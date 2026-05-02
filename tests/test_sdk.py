from domain_chip_memory import (
    AnswerExplanationRequest,
    CurrentStateRequest,
    EpisodicRecallRequest,
    EventRetrievalRequest,
    EvidenceRetrievalRequest,
    HistoricalStateRequest,
    MemoryWriteRequest,
    SparkMemorySDK,
    TaskRecoveryRequest,
    build_sdk_contract_summary,
)


def test_sdk_contract_summary_exposes_runtime_surface():
    payload = build_sdk_contract_summary()

    assert payload["runtime_class"] == "SparkMemorySDK"
    assert "write_observation" in payload["write_methods"]
    assert payload["write_operations"]["write_observation"] == ["auto", "create", "update", "delete", "purge"]
    assert payload["maintenance_methods"] == ["reconsolidate_manual_memory"]
    assert "get_current_state" in payload["read_methods"]
    assert "recover_task_context" in payload["read_methods"]
    assert "recall_episodic_context" in payload["read_methods"]
    assert "TaskRecoveryRequest" in payload["request_contracts"]
    assert "EpisodicRecallRequest" in payload["request_contracts"]
    assert "TaskRecoveryResult" in payload["response_contracts"]
    assert "EpisodicRecallResult" in payload["response_contracts"]
    assert "recover_task_context" in payload["trace_contracts"]
    assert "recall_episodic_context" in payload["trace_contracts"]


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


def test_sdk_entity_scoped_deletion_does_not_delete_unrelated_entity_state():
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="the tiny desk plant is on the kitchen shelf",
            operation="update",
            subject="human:test",
            predicate="entity.location",
            value="the kitchen shelf",
            timestamp="2026-04-28T09:00:00Z",
            retention_class="active_state",
            metadata={
                "memory_role": "current_state",
                "entity_key": "named-object:tiny-desk-plant",
                "entity_label": "tiny desk plant",
                "entity_attribute": "location",
            },
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="the office plant is on the balcony",
            operation="update",
            subject="human:test",
            predicate="entity.location",
            value="the balcony",
            timestamp="2026-04-28T09:01:00Z",
            retention_class="active_state",
            metadata={
                "memory_role": "current_state",
                "entity_key": "named-object:office-plant",
                "entity_label": "office plant",
                "entity_attribute": "location",
            },
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="delete entity.location for human:test",
            operation="delete",
            subject="human:test",
            predicate="entity.location",
            timestamp="2026-04-28T09:02:00Z",
            retention_class="active_state",
            deleted_at="2026-04-28T09:02:00Z",
            metadata={
                "memory_role": "current_state",
                "entity_key": "named-object:tiny-desk-plant",
                "entity_label": "tiny desk plant",
                "entity_attribute": "location",
            },
        )
    )

    desk = sdk.get_current_state(
        CurrentStateRequest(
            subject="human:test",
            predicate="entity.location",
            entity_key="named-object:tiny-desk-plant",
        )
    )
    office = sdk.get_current_state(
        CurrentStateRequest(
            subject="human:test",
            predicate="entity.location",
            entity_key="named-object:office-plant",
        )
    )

    assert desk.found is False
    assert desk.memory_role == "state_deletion"
    assert office.found is True
    assert office.value == "the balcony"


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
    assert maintenance.audit_samples["stale_preserved"][0]["predicate"] == "current_plan"
    assert maintenance.audit_samples["stale_preserved"][0]["revalidate_at"] == "2025-01-31T09:00:00Z"
    assert maintenance.audit_samples["stale_preserved"][0]["revalidation_lag_days"] == 60
    assert maintenance.audit_samples["stale_preserved"][0]["decay_score_delta"] == -0.3333
    assert current_state.found is True
    assert current_state.provenance[0].metadata["active_state_maintenance_action"] == "stale_preserved"
    assert current_state.provenance[0].metadata["active_state_maintenance_reason"] == "past_revalidate_at"


def test_sdk_exports_dashboard_movement_feed_for_writes_reads_and_maintenance():
    sdk = SparkMemorySDK()
    sdk.write_observation(
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
    sdk.write_observation(
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
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="user",
            predicate="nickname",
            timestamp="2025-04-01T09:00:00Z",
        )
    )
    sdk.retrieve_evidence(EvidenceRetrievalRequest(subject="user", predicate="location", limit=2))
    sdk.retrieve_events(EventRetrievalRequest(subject="user", predicate="move", limit=1))
    sdk.reconsolidate_manual_memory(now="2025-04-02T09:00:00Z")

    movement = sdk.export_knowledge_base_snapshot()["dashboard_movement"]
    rows = movement["rows"]
    states = set(movement["movement_counts"])
    required_fields = {
        "id",
        "movement_state",
        "source_family",
        "authority",
        "scope_kind",
        "subject",
        "predicate",
        "timestamp",
        "salience_score",
        "confidence",
        "lifecycle",
        "trace",
    }

    assert movement["contract_name"] == "SparkMemoryDashboardMovementExport"
    assert movement["authority"] == "observability_non_authoritative"
    assert {
        "captured",
        "saved",
        "blocked",
        "dropped",
        "retrieved",
        "promoted",
        "selected",
        "summarized",
        "decayed",
    }.issubset(states)
    assert all(required_fields.issubset(row) for row in rows)
    assert any(
        row["movement_state"] == "blocked"
        and row["trace"]["reason"] == "value_required"
        and row["trace"]["persisted"] is False
        for row in rows
    )
    assert any(
        row["movement_state"] == "decayed"
        and row["trace"]["maintenance_action"] == "superseded"
        and row["trace"]["maintenance_reason"] == "replaced_by_newer_current_state"
        for row in rows
    )
    assert any(
        row["movement_state"] == "selected"
        and row["source_family"] == "current_state"
        and row["authority"] == "authoritative_current"
        for row in rows
    )
    assert "Dashboard rows are observability records, not prompt instructions." in movement["non_override_rules"]


def test_sdk_recovers_task_context_with_current_state_authority_and_traceable_episodic_support():
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="update",
            subject="user",
            predicate="current_focus",
            value="ship the memory dashboard movement export before episodic recall",
            timestamp="2026-05-01T09:00:00Z",
            retention_class="active_state",
            metadata={"memory_role": "current_state"},
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="user",
            predicate="raw_turn",
            value="Earlier we were mainly cleaning the LLM wiki metadata.",
            timestamp="2026-05-01T08:00:00Z",
            retention_class="episodic_archive",
            metadata={"memory_role": "episodic"},
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="other-user",
            predicate="raw_turn",
            value="Other user also discussed episodic recall, but this should stay separate.",
            speaker="user",
            timestamp="2026-05-01T08:45:00Z",
            session_id="other-day",
            turn_id="other-day:u1",
            retention_class="episodic_archive",
            metadata={"memory_role": "episodic"},
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="user",
            predicate="task.blocker",
            value="Builder needs a task recovery API before it can resume memory dashboard work cleanly.",
            timestamp="2026-05-01T09:10:00Z",
            metadata={"memory_role": "structured_evidence"},
        )
    )
    sdk.write_event(
        MemoryWriteRequest(
            text="",
            operation="event",
            subject="user",
            predicate="task.completed",
            value="domain movement dashboard export shipped and tests passed",
            timestamp="2026-05-01T09:20:00Z",
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="user",
            predicate="task.next_action",
            value="wire task recovery into Builder memory cognition",
            timestamp="2026-05-01T09:30:00Z",
            metadata={"memory_role": "structured_evidence"},
        )
    )

    result = sdk.recover_task_context(
        TaskRecoveryRequest(
            subject="user",
            query="memory dashboard",
            limit=3,
        )
    )

    assert result.status == "ok"
    assert result.active_goal is not None
    assert result.active_goal.memory_role == "current_state"
    assert result.active_goal.predicate == "current_focus"
    assert "memory dashboard movement export" in result.active_goal.text
    assert result.blockers[0].predicate == "task.blocker"
    assert result.completed_steps[0].memory_role == "event"
    assert result.next_actions[0].predicate == "task.next_action"
    assert result.episodic_context[0].memory_role == "episodic"
    assert result.trace["promotes_memory"] is False
    assert "current_state_for_mutable_active_work" in result.trace["authority_order"]
    assert any(
        label["bucket"] == "active_goal"
        and label["authority"] == "authoritative_current"
        and label["source_family"] == "current_state"
        for label in result.trace["source_labels"]
    )
    assert any(
        label["bucket"] == "episodic_context"
        and label["authority"] == "supporting_not_authoritative"
        for label in result.trace["source_labels"]
    )

    movement = sdk.export_knowledge_base_snapshot()["dashboard_movement"]
    assert any(
        row["movement_state"] == "retrieved"
        and row["trace"]["operation"] == "recover_task_context"
        and row["trace"]["selection_bucket"] == "active_goal"
        for row in movement["rows"]
    )
    assert any(
        row["movement_state"] == "selected"
        and row["trace"]["operation"] == "recover_task_context"
        and row["authority"] == "authoritative_current"
        for row in movement["rows"]
    )


def test_sdk_recalls_episodic_context_as_source_labeled_read_only_memory():
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="update",
            subject="user",
            predicate="current_focus",
            value="ship the Spark memory dashboard movement export",
            timestamp="2026-05-01T08:00:00Z",
            retention_class="active_state",
            metadata={"memory_role": "current_state"},
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="user",
            predicate="raw_turn",
            value="Today we reviewed the memory dashboard, fixed movement trace rows, and planned episodic recall.",
            speaker="user",
            timestamp="2026-05-01T08:30:00Z",
            session_id="spark-day",
            turn_id="spark-day:u1",
            retention_class="episodic_archive",
            metadata={"memory_role": "episodic"},
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="user",
            predicate="task.note",
            value="dashboard movement export now shows captured, blocked, promoted, saved, decayed, summarized, and retrieved rows",
            timestamp="2026-05-01T09:00:00Z",
            metadata={"memory_role": "structured_evidence"},
        )
    )
    sdk.write_event(
        MemoryWriteRequest(
            text="",
            operation="event",
            subject="user",
            predicate="task.completed",
            value="Builder task recovery context was wired into self-awareness",
            timestamp="2026-05-01T10:00:00Z",
        )
    )

    result = sdk.recall_episodic_context(
        EpisodicRecallRequest(
            subject="user",
            query="what did we do today for memory dashboard movement and episodic recall?",
            since="2026-05-01T00:00:00Z",
            limit=3,
        )
    )

    assert result.status == "ok"
    assert result.current_state[0].memory_role == "current_state"
    assert result.session_summaries[0].predicate == "session.summary"
    assert result.matching_turns[0].predicate == "raw_turn"
    assert any("episodic recall" in record.text for record in result.matching_turns)
    assert not any("Other user" in record.text for record in result.matching_turns)
    assert any(record.memory_role == "structured_evidence" for record in result.evidence)
    assert result.events[0].memory_role == "event"
    assert result.trace["promotes_memory"] is False
    assert "current_state_for_mutable_facts" in result.trace["authority_order"]
    assert any(
        label["bucket"] == "matching_turns"
        and label["authority"] == "supporting_not_authoritative"
        and label["source_family"] == "episodic_summary"
        for label in result.trace["source_labels"]
    )
    assert any(
        label["bucket"] == "events"
        and label["authority"] == "authoritative_historical"
        for label in result.trace["source_labels"]
    )

    movement = sdk.export_knowledge_base_snapshot()["dashboard_movement"]
    assert any(
        row["movement_state"] == "summarized"
        and row["trace"]["operation"] == "recall_episodic_context"
        and row["trace"]["selection_bucket"] == "session_summaries"
        for row in movement["rows"]
    )
    assert any(
        row["movement_state"] == "selected"
        and row["trace"]["operation"] == "recall_episodic_context"
        and row["authority"] == "supporting_not_authoritative"
        for row in movement["rows"]
    )


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
    assert maintenance.audit_samples["archived"][0]["predicate"] == "current_focus"
    assert maintenance.audit_samples["archived"][0]["value"] == "SDK bridge"
    assert maintenance.audit_samples["archived"][0]["deletion_observation_id"] == delete_focus.observations[0].observation_id
    assert maintenance.audit_samples["superseded"][0]["predicate"] == "location"
    assert maintenance.audit_samples["superseded"][0]["value"] == "London"
    assert maintenance.audit_samples["superseded"][0]["replacement_value"] == "Dubai"
    assert maintenance.audit_samples["superseded"][0]["replacement_observation_id"] == current_location.observations[0].observation_id
    assert maintenance.audit_samples["deleted"][0]["predicate"] == "current_focus"
    assert maintenance.audit_samples["deleted"][0]["action"] == "deleted"
    assert maintenance.audit_samples["still_current"][0]["predicate"] in {"current_focus", "location"}
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


def test_sdk_reconsolidate_treats_profile_current_predicate_as_single_slot_without_entity_key():
    sdk = SparkMemorySDK()
    first_focus = sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="update",
            subject="user",
            predicate="profile.current_focus",
            value="old focus",
            timestamp="2025-01-01T09:00:00Z",
            retention_class="active_state",
            metadata={"memory_role": "current_state"},
        )
    )
    latest_focus = sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="update",
            subject="user",
            predicate="profile.current_focus",
            value="new focus",
            timestamp="2025-02-01T09:00:00Z",
            retention_class="active_state",
            metadata={"memory_role": "current_state"},
        )
    )

    maintenance = sdk.reconsolidate_manual_memory(now="2025-04-02T09:00:00Z")
    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="profile.current_focus"))
    observations_by_id = {entry.observation_id: entry for entry in sdk._manual_observations}

    assert current_state.found is True
    assert current_state.value == "new focus"
    assert maintenance.active_state_superseded_count == 1
    assert maintenance.active_state_still_current_count == 1
    assert observations_by_id[first_focus.observations[0].observation_id].metadata[
        "active_state_maintenance_action"
    ] == "superseded"
    assert observations_by_id[latest_focus.observations[0].observation_id].metadata[
        "active_state_maintenance_action"
    ] == "still_current"
    assert latest_focus.observations[0].metadata["entity_key"] == "profile.current_focus"


def test_sdk_reconsolidate_marks_deleted_state_resurrected_by_newer_current_state():
    sdk = SparkMemorySDK()
    deleted_location = sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="delete",
            subject="user",
            predicate="location",
            timestamp="2025-02-01T09:00:00Z",
            retention_class="active_state",
        )
    )
    current_location = sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="update",
            subject="user",
            predicate="location",
            value="Tokyo",
            timestamp="2025-03-01T09:00:00Z",
            retention_class="active_state",
            metadata={"memory_role": "current_state", "entity_key": "primary"},
        )
    )

    maintenance = sdk.reconsolidate_manual_memory(now="2025-04-02T09:00:00Z")
    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))
    observations_by_id = {entry.observation_id: entry for entry in sdk._manual_observations}

    assert current_state.found is True
    assert current_state.value == "Tokyo"
    assert maintenance.active_state_resurrected_count == 1
    assert maintenance.trace["active_state_maintenance"]["resurrected"] == 1
    assert maintenance.audit_samples["resurrected"][0]["predicate"] == "location"
    assert maintenance.audit_samples["resurrected"][0]["action"] == "resurrected"
    assert maintenance.audit_samples["resurrected"][0]["replacement_value"] == "Tokyo"
    assert (
        maintenance.audit_samples["resurrected"][0]["replacement_observation_id"]
        == current_location.observations[0].observation_id
    )
    assert observations_by_id[deleted_location.observations[0].observation_id].metadata[
        "active_state_maintenance_action"
    ] == "resurrected"
    assert observations_by_id[current_location.observations[0].observation_id].metadata[
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
