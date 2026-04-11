from domain_chip_memory import build_sdk_contract_summary


def test_sdk_contract_summary_declares_runtime_memory_architecture() -> None:
    payload = build_sdk_contract_summary()

    assert payload["runtime_class"] == "SparkMemorySDK"
    assert payload["runtime_memory_architecture"] == "summary_synthesis_memory"
    assert payload["runtime_memory_provider"] == "heuristic_v1"
