from domain_chip_memory.builder_read_adapter import BuilderMemoryReadRequest, execute_builder_memory_read
from domain_chip_memory.sdk import MemoryWriteRequest, SparkMemorySDK


def test_builder_read_adapter_surfaces_lookup_role_inventory() -> None:
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="human:telegram:12345",
            predicate="profile.city",
            value="Dubai",
            timestamp="2025-03-01T09:00:00Z",
        )
    )

    payload = execute_builder_memory_read(
        sdk,
        BuilderMemoryReadRequest(
            method="get_current_state",
            subject="telegram:12345",
            predicate="profile.city",
        ),
    )

    assert payload["facts"]["memory_role"] == "current_state"
    assert payload["facts"]["memory_roles"] == ["current_state"]
    assert payload["facts"]["primary_memory_role"] == "current_state"
    assert payload["facts"]["canonical_memory_roles"] == ["current_state"]
    assert payload["facts"]["provenance_roles"] == ["current_state"]


def test_builder_read_adapter_surfaces_retrieval_role_inventory() -> None:
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="human:telegram:12345",
            predicate="location",
            value="Dubai",
            timestamp="2025-03-01T09:00:00Z",
        )
    )
    sdk.write_event(
        MemoryWriteRequest(
            text="",
            operation="event",
            subject="human:telegram:12345",
            predicate="meeting",
            value="Omar on May 3",
            timestamp="2025-03-02T09:00:00Z",
        )
    )

    evidence_payload = execute_builder_memory_read(
        sdk,
        BuilderMemoryReadRequest(
            method="retrieve_evidence",
            subject="telegram:12345",
            predicate="location",
            query="Where do I live?",
            limit=5,
        ),
    )
    event_payload = execute_builder_memory_read(
        sdk,
        BuilderMemoryReadRequest(
            method="retrieve_events",
            subject="telegram:12345",
            predicate="meeting",
            query="What meeting do I have?",
            limit=5,
        ),
    )

    assert evidence_payload["facts"]["memory_roles"] == ["structured_evidence"]
    assert evidence_payload["facts"]["canonical_memory_roles"] == ["structured_evidence"]
    assert event_payload["facts"]["memory_roles"] == ["event"]
    assert event_payload["facts"]["primary_memory_role"] == "event"


def test_builder_read_adapter_surfaces_explanation_role_inventory() -> None:
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="human:telegram:12345",
            predicate="profile.city",
            value="Dubai",
            timestamp="2025-03-01T09:00:00Z",
        )
    )
    sdk.write_event(
        MemoryWriteRequest(
            text="",
            operation="event",
            subject="human:telegram:12345",
            predicate="meeting",
            value="Omar on May 3",
            timestamp="2025-03-02T09:00:00Z",
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

    assert payload["facts"]["memory_role"] == "current_state"
    assert payload["facts"]["memory_roles"][0] == "current_state"
    assert payload["facts"]["canonical_memory_roles"][0] == "current_state"
