from domain_chip_memory.spark_integration import build_spark_integration_contract_summary


def test_spark_integration_contract_summary_exposes_orchestration_surface():
    payload = build_spark_integration_contract_summary()
    assert payload["sdk_runtime"] == "SparkMemorySDK"
    assert payload["shadow_runtime"] == "SparkShadowIngestAdapter"
    assert "memory_write_gate" in payload["required_builder_systems"]
    assert "maintenance_scheduler" in payload["required_builder_systems"]
    assert "write_observation" in payload["integration_vectors"]["writes"]["sdk_methods"]
    assert "run-spark-shadow-report-batch" in payload["integration_vectors"]["shadow"]["entrypoints"]
    assert "reconsolidate_manual_memory" in payload["integration_vectors"]["maintenance"]["sdk_methods"]
    assert "SparkMemorySDK" in payload["system_prompt_template"]
