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
