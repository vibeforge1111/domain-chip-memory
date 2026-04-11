from domain_chip_memory import build_sdk_contract_summary


def test_sdk_contract_summary_declares_runtime_memory_architecture() -> None:
    payload = build_sdk_contract_summary()

    assert payload["runtime_class"] == "SparkMemorySDK"
    assert payload["runtime_memory_architecture"] == "dual_store_event_calendar_hybrid"
    assert payload["runtime_memory_provider"] == "heuristic_v1"
