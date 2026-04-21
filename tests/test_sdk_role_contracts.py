from domain_chip_memory.memory_roles import canonical_memory_role
from domain_chip_memory.sdk import (
    AnswerExplanationRequest,
    CurrentStateRequest,
    EventRetrievalRequest,
    MemoryWriteRequest,
    SparkMemorySDK,
    build_sdk_contract_summary,
)


def test_sdk_contract_summary_exposes_memory_role_catalog_and_answer_candidate_types() -> None:
    payload = build_sdk_contract_summary()

    role_catalog = {item["runtime_role"]: item for item in payload["memory_roles"]}

    assert role_catalog["episodic"]["canonical_role"] == "raw_episode"
    assert role_catalog["current_state"]["canonical_role"] == "current_state"
    assert role_catalog["event"]["description"]
    assert "event_history" in payload["answer_candidate_types"]
    assert "write_memory" in payload["trace_contracts"]


def test_sdk_write_trace_reports_memory_roles_for_observations_and_events() -> None:
    sdk = SparkMemorySDK()

    observation_write = sdk.write_observation(
        MemoryWriteRequest(
            text="I moved to Dubai.",
            timestamp="2025-03-01T09:00:00Z",
        )
    )
    event_write = sdk.write_event(
        MemoryWriteRequest(
            text="",
            operation="event",
            subject="user",
            predicate="deadline",
            value="Atlas launch on May 24",
            timestamp="2025-03-02T09:00:00Z",
        )
    )

    assert observation_write.trace["memory_roles"] == ["structured_evidence", "event"]
    assert observation_write.trace["primary_memory_role"] == "structured_evidence"
    assert observation_write.trace["canonical_memory_roles"] == ["structured_evidence", "event"]
    assert event_write.trace["memory_roles"] == ["event"]
    assert event_write.trace["memory_role_counts"] == {"event": 1}


def test_sdk_read_and_explanation_traces_report_role_mix() -> None:
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
        )
    )

    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))
    events = sdk.retrieve_events(
        EventRetrievalRequest(subject="user", predicate="meeting", limit=3)
    )
    explanation = sdk.explain_answer(
        AnswerExplanationRequest(
            question="Where do I live now?",
            subject="user",
            predicate="location",
            event_limit=3,
        )
    )

    assert current_state.trace["memory_role"] == "current_state"
    assert current_state.trace["provenance_roles"] == ["current_state"]
    assert events.trace["memory_roles"] == ["event"]
    assert events.trace["primary_memory_role"] == "event"
    assert explanation.trace["state_memory_role"] == "current_state"
    assert explanation.trace["evidence_memory_roles"] == ["structured_evidence"]
    assert explanation.trace["event_memory_roles"] == ["event"]
    assert explanation.trace["canonical_memory_roles"][0] == canonical_memory_role("current_state")


def test_sdk_snapshot_exports_memory_role_contract() -> None:
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="I moved to Dubai.",
            timestamp="2025-03-01T09:00:00Z",
        )
    )

    snapshot = sdk.export_knowledge_base_snapshot()

    assert "memory_role_contract" in snapshot
    assert snapshot["memory_role_contract"]["canonical_aliases"]["episodic"] == "raw_episode"
