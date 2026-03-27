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
    assert payload["write_operations"]["write_observation"] == ["auto", "create", "update", "delete"]
    assert "get_current_state" in payload["read_methods"]


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
