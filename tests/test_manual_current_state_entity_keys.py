from domain_chip_memory import CurrentStateRequest, MemoryWriteRequest, SparkMemorySDK


def test_explicit_update_respects_custom_entity_key_for_mutable_current_state_slot() -> None:
    sdk = SparkMemorySDK()

    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            timestamp="2026-04-21T10:00:00Z",
            operation="update",
            subject="human:telegram:test",
            predicate="telegram.summary.latest_flight",
            value="flight to London on May 6",
            metadata={"entity_key": "latest-flight"},
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            timestamp="2026-04-22T10:00:00Z",
            operation="update",
            subject="human:telegram:test",
            predicate="telegram.summary.latest_flight",
            value="flight to Paris on May 9",
            metadata={"entity_key": "latest-flight"},
        )
    )

    current = sdk.get_current_state(
        CurrentStateRequest(subject="human:telegram:test", predicate="telegram.summary.latest_flight")
    )

    assert current.found is True
    assert current.value == "flight to Paris on May 9"

    snapshot = sdk.export_knowledge_base_snapshot()
    current_records = [
        entry
        for entry in snapshot["current_state"]
        if entry["subject"] == "human:telegram:test" and entry["predicate"] == "telegram.summary.latest_flight"
    ]
    assert len(current_records) == 1
    assert current_records[0]["metadata"]["value"] == "flight to Paris on May 9"
    assert current_records[0]["metadata"]["entity_key"] == "latest-flight"
