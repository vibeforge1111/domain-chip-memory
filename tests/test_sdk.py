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
    assert "get_current_state" in payload["read_methods"]


def test_sdk_write_and_get_current_state():
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
