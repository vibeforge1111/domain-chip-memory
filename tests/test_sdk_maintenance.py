from domain_chip_memory.sdk import build_sdk_maintenance_replay_contract_summary


def test_sdk_maintenance_replay_contract_summary_exposes_file_shape():
    payload = build_sdk_maintenance_replay_contract_summary()
    assert payload["single_file_shape"]["required_fields"] == ["writes"]
    assert payload["single_file_shape"]["check_groups"]["current_state"] == [
        "subject",
        "predicate",
    ]
    assert payload["supported_write_kinds"] == ["observation", "event"]
    assert payload["supported_operations"]["observation"] == ["auto", "create", "update", "delete"]
    assert payload["maintenance_method"] == "reconsolidate_manual_memory"
