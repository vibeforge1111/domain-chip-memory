from domain_chip_memory import (
    CurrentStateRequest,
    SparkMemorySDK,
    SparkShadowIngestAdapter,
    SparkShadowIngestRequest,
    SparkShadowTurn,
    build_shadow_ingest_contract_summary,
)


def test_shadow_ingest_contract_summary_exposes_runtime_surface():
    payload = build_shadow_ingest_contract_summary()

    assert payload["runtime_class"] == "SparkShadowIngestAdapter"
    assert "SparkShadowIngestRequest" in payload["request_contracts"]


def test_shadow_ingest_writes_user_turns_and_skips_assistant_turns():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-1",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="I live in London.",
                    timestamp="2025-01-01T09:00:00Z",
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="assistant",
                    content="Noted.",
                    timestamp="2025-01-01T09:01:00Z",
                ),
                SparkShadowTurn(
                    message_id="m3",
                    role="user",
                    content="I moved to Dubai.",
                    timestamp="2025-03-01T09:00:00Z",
                ),
            ],
        )
    )

    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))

    assert result.accepted_writes == 2
    assert result.rejected_writes == 0
    assert result.skipped_turns == 1
    assert current_state.found is True
    assert current_state.value == "Dubai"
    assert result.turn_traces[1].action == "skipped_role"


def test_shadow_ingest_counts_rejected_unsupported_writes():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-2",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="Hello there.",
                    timestamp="2025-01-01T09:00:00Z",
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="user",
                    content="I moved to Dubai.",
                    timestamp="2025-03-01T09:00:00Z",
                ),
            ],
        )
    )

    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))

    assert result.accepted_writes == 1
    assert result.rejected_writes == 1
    assert result.turn_traces[0].action == "rejected_write"
    assert result.turn_traces[0].unsupported_reason == "no_structured_memory_extracted"
    assert current_state.found is True
    assert current_state.value == "Dubai"


def test_shadow_ingest_can_route_turn_to_event_write():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-3",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="I moved to Dubai.",
                    timestamp="2025-03-01T09:00:00Z",
                    metadata={"memory_kind": "event"},
                ),
            ],
        )
    )

    assert result.accepted_writes == 1
    assert result.turn_traces[0].accepted is True
    assert result.turn_traces[0].trace["write_trace"]["operation"] == "write_memory"
