from domain_chip_memory.builder_read_adapter import BuilderMemoryReadRequest, execute_builder_memory_read
from domain_chip_memory.sdk import MemoryWriteRequest, SparkMemorySDK


def test_builder_read_adapter_materializes_explanation_success_for_bare_telegram_subject():
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="human:telegram:12345",
            predicate="profile.city",
            value="Dubai",
            timestamp="2025-03-01T09:00:00Z",
            supersedes="city:seed",
        )
    )

    payload = execute_builder_memory_read(
        sdk,
        BuilderMemoryReadRequest(
            method="explain_answer",
            subject="telegram:12345",
            predicate="profile.city",
            question="How do you know where I live?",
        ),
    )

    assert payload["event_type"] == "memory_read_succeeded"
    assert payload["facts"]["memory_role"] == "current_state"
    assert payload["facts"]["answer_explanation"]["answer"] == "Dubai"
    assert payload["facts"]["answer_explanation"]["evidence"]
    evidence = payload["facts"]["answer_explanation"]["evidence"][0]
    assert evidence["observation_id"]
    assert evidence["retention_class"] == "durable_profile"
    assert evidence["lifecycle"]["supersedes"] == "city:seed"
    assert payload["facts"]["retrieval_trace"]["subject"] == "telegram:12345"


def test_builder_read_adapter_materializes_identity_evidence_success():
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="human:telegram:12345",
            predicate="profile.preferred_name",
            value="Sarah",
            timestamp="2025-03-01T09:00:00Z",
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="human:telegram:12345",
            predicate="profile.occupation",
            value="entrepreneur",
            timestamp="2025-03-01T09:01:00Z",
        )
    )

    payload = execute_builder_memory_read(
        sdk,
        BuilderMemoryReadRequest(
            method="retrieve_evidence",
            subject="telegram:12345",
            query="What do you know about me?",
            limit=5,
        ),
    )

    assert payload["event_type"] == "memory_read_succeeded"
    assert payload["facts"]["record_count"] == 2
    assert payload["facts"]["retrieval_trace"]["query_intent"] == "profile_identity_summary"


def test_builder_read_adapter_materializes_source_aware_episodic_recall():
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="update",
            subject="user",
            predicate="current_focus",
            value="finish source-aware episodic recall",
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
            value="We planned episodic recall for Spark memory continuity.",
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
            subject="other-user",
            predicate="raw_turn",
            value="Other user planned a separate episodic recall path.",
            speaker="user",
            timestamp="2026-05-01T08:45:00Z",
            session_id="other-day",
            turn_id="other-day:u1",
            retention_class="episodic_archive",
            metadata={"memory_role": "episodic"},
        )
    )
    sdk.write_event(
        MemoryWriteRequest(
            text="",
            operation="event",
            subject="user",
            predicate="task.completed",
            value="Task recovery was connected to self-awareness.",
            timestamp="2026-05-01T09:00:00Z",
        )
    )

    payload = execute_builder_memory_read(
        sdk,
        BuilderMemoryReadRequest(
            method="recall_episodic_context",
            subject="user",
            query="what did we do for episodic recall?",
            since="2026-05-01T00:00:00Z",
            limit=3,
        ),
    )

    assert payload["event_type"] == "memory_read_succeeded"
    assert payload["facts"]["retrieval_trace"]["promotes_memory"] is False
    assert "current_state_for_mutable_facts" in payload["facts"]["retrieval_trace"]["authority_order"]
    buckets = {record["episodic_recall_bucket"] for record in payload["facts"]["records"]}
    assert {"current_state", "session_summaries", "matching_turns", "events"} <= buckets
    assert any(
        record["episodic_recall_bucket"] == "matching_turns"
        and record["memory_role"] == "episodic"
        and "episodic recall" in record["text"]
        for record in payload["facts"]["records"]
    )
    assert not any("Other user" in record["text"] for record in payload["facts"]["records"])
    assert any(
        label["bucket"] == "matching_turns"
        and label["authority"] == "supporting_not_authoritative"
        for label in payload["facts"]["retrieval_trace"]["source_labels"]
    )


def test_builder_read_adapter_preserves_invalid_lookup_abstention():
    sdk = SparkMemorySDK()

    payload = execute_builder_memory_read(
        sdk,
        BuilderMemoryReadRequest(
            method="get_current_state",
            subject="telegram:12345",
            predicate="",
        ),
    )

    assert payload["event_type"] == "memory_read_abstained"
    assert payload["facts"]["reason"] == "predicate_required"


def test_builder_read_adapter_passes_entity_key_to_temporal_state_reads():
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="The tiny desk plant is named Mira.",
            operation="update",
            subject="human:telegram:12345",
            predicate="entity.name",
            value="Mira",
            timestamp="2026-04-27T10:00:00Z",
            metadata={"entity_key": "named-object:tiny-desk-plant"},
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="The tiny desk plant is named Sol.",
            operation="update",
            subject="human:telegram:12345",
            predicate="entity.name",
            value="Sol",
            timestamp="2026-04-27T11:00:00Z",
            metadata={"entity_key": "named-object:tiny-desk-plant"},
        )
    )

    current_payload = execute_builder_memory_read(
        sdk,
        BuilderMemoryReadRequest(
            method="get_current_state",
            subject="telegram:12345",
            predicate="entity.name",
            entity_key="named-object:tiny-desk-plant",
        ),
    )
    historical_payload = execute_builder_memory_read(
        sdk,
        BuilderMemoryReadRequest(
            method="get_historical_state",
            subject="telegram:12345",
            predicate="entity.name",
            entity_key="named-object:tiny-desk-plant",
            as_of="2026-04-27T10:30:00Z",
        ),
    )

    assert current_payload["event_type"] == "memory_read_succeeded"
    assert current_payload["facts"]["retrieval_trace"]["entity_key"] == "named-object:tiny-desk-plant"
    assert historical_payload["event_type"] == "memory_read_succeeded"
    assert historical_payload["facts"]["retrieval_trace"]["entity_key"] == "named-object:tiny-desk-plant"
