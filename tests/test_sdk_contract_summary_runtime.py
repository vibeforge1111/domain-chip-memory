from domain_chip_memory import build_sdk_contract_summary


def test_sdk_contract_summary_declares_runtime_memory_architecture() -> None:
    payload = build_sdk_contract_summary()

    assert payload["runtime_class"] == "SparkMemorySDK"
    assert payload["runtime_memory_architecture"] == "dual_store_event_calendar_hybrid"
    assert payload["runtime_memory_provider"] == "heuristic_v1"


def test_sdk_contract_summary_accepts_request_scoped_runtime_architecture(monkeypatch) -> None:
    monkeypatch.setenv("SPARK_MEMORY_RUNTIME_ARCHITECTURE", "env_arch_that_must_not_leak")
    monkeypatch.setenv("SPARK_MEMORY_RUNTIME_PROVIDER", "env_provider_that_must_not_leak")

    payload = build_sdk_contract_summary(
        runtime_memory_architecture="typed_temporal_graph",
        runtime_memory_provider="codex:gpt-5-codex",
    )

    assert payload["runtime_memory_architecture"] == "typed_temporal_graph"
    assert payload["runtime_memory_provider"] == "codex:gpt-5-codex"


def test_sdk_contract_summary_ignores_ambient_runtime_env(monkeypatch) -> None:
    monkeypatch.setenv("SPARK_MEMORY_RUNTIME_ARCHITECTURE", "shared_process_arch")
    monkeypatch.setenv("SPARK_MEMORY_RUNTIME_PROVIDER", "shared_process_provider")

    payload = build_sdk_contract_summary()

    assert payload["runtime_memory_architecture"] == "dual_store_event_calendar_hybrid"
    assert payload["runtime_memory_provider"] == "heuristic_v1"
