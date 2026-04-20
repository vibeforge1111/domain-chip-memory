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
