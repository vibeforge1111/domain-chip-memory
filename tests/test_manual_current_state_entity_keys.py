from domain_chip_memory import CurrentStateRequest, HistoricalStateRequest, MemoryWriteRequest, SparkMemorySDK


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


def test_entity_key_scopes_current_and_historical_state_reads() -> None:
    sdk = SparkMemorySDK()

    sdk.write_observation(
        MemoryWriteRequest(
            text="The tiny desk plant is named Mira.",
            timestamp="2026-04-27T10:00:00Z",
            operation="update",
            subject="human:telegram:test",
            predicate="entity.name",
            value="Mira",
            metadata={"entity_key": "named-object:tiny-desk-plant"},
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="The tiny desk plant is named Sol.",
            timestamp="2026-04-27T11:00:00Z",
            operation="update",
            subject="human:telegram:test",
            predicate="entity.name",
            value="Sol",
            metadata={"entity_key": "named-object:tiny-desk-plant"},
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="The office project is named Harbor.",
            timestamp="2026-04-27T12:00:00Z",
            operation="update",
            subject="human:telegram:test",
            predicate="entity.name",
            value="Harbor",
            metadata={"entity_key": "named-object:office-project"},
        )
    )

    current_plant = sdk.get_current_state(
        CurrentStateRequest(
            subject="human:telegram:test",
            predicate="entity.name",
            entity_key="named-object:tiny-desk-plant",
        )
    )
    current_project = sdk.get_current_state(
        CurrentStateRequest(
            subject="human:telegram:test",
            predicate="entity.name",
            entity_key="named-object:office-project",
        )
    )
    plant_before_update = sdk.get_historical_state(
        HistoricalStateRequest(
            subject="human:telegram:test",
            predicate="entity.name",
            entity_key="named-object:tiny-desk-plant",
            as_of="2026-04-27T10:30:00Z",
        )
    )

    assert current_plant.found is True
    assert current_plant.value == "Sol"
    assert current_plant.trace["entity_key"] == "named-object:tiny-desk-plant"
    assert current_project.found is True
    assert current_project.value == "Harbor"
    assert plant_before_update.found is True
    assert plant_before_update.value == "Mira"
    assert plant_before_update.trace["entity_key"] == "named-object:tiny-desk-plant"
