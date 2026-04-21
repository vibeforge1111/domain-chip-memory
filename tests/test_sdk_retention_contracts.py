from domain_chip_memory.sdk import (
    AnswerExplanationRequest,
    CurrentStateRequest,
    EventRetrievalRequest,
    MemoryWriteRequest,
    SparkMemorySDK,
    build_sdk_contract_summary,
)


def test_sdk_contract_summary_exposes_retention_classes_and_lifecycle_fields() -> None:
    payload = build_sdk_contract_summary()

    retention_catalog = {item["retention_class"]: item for item in payload["retention_classes"]}

    assert retention_catalog["active_state"]["description"]
    assert payload["retention_defaults_by_memory_role"]["current_state"] == "active_state"
    assert payload["retention_defaults_by_memory_role"]["event"] == "time_bound_event"
    assert "document_time" in payload["lifecycle_fields"]
    assert "lifecycle_fields_present" in payload["trace_contracts"]["write_memory"]


def test_sdk_write_and_read_surface_retention_and_lifecycle_metadata() -> None:
    sdk = SparkMemorySDK()

    write_result = sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="update",
            subject="user",
            predicate="current_plan",
            value="launch Atlas in enterprise first",
            timestamp="2025-03-01T09:00:00Z",
            retention_class="active_state",
            document_time="2025-03-01T09:00:00Z",
            valid_from="2025-03-01T09:00:00Z",
            supersedes="plan:seed",
            conflicts_with=["plan:self_serve_first"],
        )
    )
    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="current_plan"))

    assert write_result.trace["retention_classes"] == ["active_state"]
    assert write_result.trace["primary_retention_class"] == "active_state"
    assert "document_time" in write_result.trace["lifecycle_fields_present"]
    assert current_state.trace["retention_class"] == "active_state"
    assert current_state.provenance[0].retention_class == "active_state"
    assert current_state.provenance[0].lifecycle["document_time"] == "2025-03-01T09:00:00Z"
    assert current_state.provenance[0].lifecycle["supersedes"] == "plan:seed"
    assert current_state.provenance[0].lifecycle["conflicts_with"] == ["plan:self_serve_first"]


def test_sdk_event_and_explanation_traces_surface_default_retention_classes() -> None:
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="I moved to Dubai.",
            timestamp="2025-03-01T09:00:00Z",
        )
    )
    sdk.write_event(
        MemoryWriteRequest(
            text="",
            operation="event",
            subject="user",
            predicate="meeting",
            value="Omar on May 3",
            timestamp="2025-03-02T09:00:00Z",
            event_time="2025-05-03T09:00:00Z",
        )
    )

    events = sdk.retrieve_events(EventRetrievalRequest(subject="user", predicate="meeting", limit=3))
    explanation = sdk.explain_answer(
        AnswerExplanationRequest(
            question="Where do I live now?",
            subject="user",
            predicate="location",
            event_limit=3,
        )
    )
    snapshot = sdk.export_knowledge_base_snapshot()

    assert events.trace["retention_classes"] == ["time_bound_event"]
    assert events.items[0].retention_class == "time_bound_event"
    assert events.items[0].lifecycle["event_time"] == "2025-05-03T09:00:00Z"
    assert "active_state" in explanation.trace["retention_classes"]
    assert "time_bound_event" in explanation.trace["retention_classes"]
    assert snapshot["retention_contract"]["defaults_by_memory_role"]["state_deletion"] == "active_state"
    assert "deleted_at" in snapshot["lifecycle_contract"]["fields"]
