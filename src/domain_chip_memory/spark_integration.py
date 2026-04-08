from __future__ import annotations

from typing import Any


def build_spark_integration_contract_summary() -> dict[str, Any]:
    return {
        "integration_target": "Spark Intelligence Builder",
        "sdk_runtime": "SparkMemorySDK",
        "shadow_runtime": "SparkShadowIngestAdapter",
        "integration_objective": (
            "Use the memory SDK as a narrow memory subsystem behind Spark orchestration, "
            "not as a general planner or direct replacement for Builder control logic."
        ),
        "required_builder_systems": [
            "entity_and_field_normalizer",
            "memory_write_gate",
            "memory_query_router",
            "provenance_and_abstention_surface",
            "knowledge_base_snapshot_export",
            "knowledge_base_compiler",
            "knowledge_base_health_checks",
            "shadow_replay_runner",
            "shadow_report_storage",
            "maintenance_scheduler",
            "artifact_and_trace_store",
        ],
        "integration_vectors": {
            "writes": {
                "sdk_methods": ["write_observation", "write_event"],
                "expected_controls": [
                    "role filtering before persistence",
                    "supported operation validation",
                    "reject raw conversational residue that is only episodic",
                    "attach session, turn, and timestamp provenance",
                ],
            },
            "reads": {
                "sdk_methods": [
                    "get_current_state",
                    "get_historical_state",
                    "retrieve_evidence",
                    "retrieve_events",
                    "explain_answer",
                ],
                "expected_controls": [
                    "route the query to the narrowest valid memory method",
                    "preserve abstention instead of fabricating a value",
                    "surface provenance and memory role to Spark",
                ],
            },
            "shadow": {
                "entrypoints": [
                    "demo-spark-shadow-report",
                    "run-spark-shadow-report",
                    "run-spark-shadow-report-batch",
                ],
                "required_outputs": [
                    "accepted_rejected_skipped_write_rates",
                    "unsupported_write_reasons",
                    "probe_hit_rates",
                    "memory_role_mix",
                ],
            },
            "maintenance": {
                "sdk_methods": ["reconsolidate_manual_memory"],
                "entrypoints": [
                    "demo-sdk-maintenance",
                    "run-sdk-maintenance-report",
                ],
                "required_outputs": [
                    "manual_observations_before_after",
                    "active_deletion_count",
                    "current_state_readback",
                    "historical_state_readback",
                ],
            },
            "knowledge_base": {
                "sdk_methods": ["export_knowledge_base_snapshot"],
                "entrypoints": [
                    "spark-kb-contracts",
                    "demo-spark-kb",
                    "spark-kb-health-check",
                ],
                "required_outputs": [
                    "obsidian_friendly_vault_layout",
                    "source_pages_describing_governed_inputs",
                    "synthesis_pages_that_compile_runtime_memory",
                    "current_state_pages_with_provenance",
                    "evidence_pages",
                    "event_pages",
                    "llm_schema_file",
                    "health_report",
                ],
            },
        },
        "orchestration_rules": [
            "Spark owns conversation flow, policy, and final response generation.",
            "The memory SDK owns typed persistence, retrieval, provenance, and abstention for memory questions.",
            "The visible KB layer is compiled downstream from governed Spark memory, never treated as the source of truth.",
            "The visible KB layer should follow a Karpathy-style raw-to-wiki pattern while remaining anchored to governed memory snapshots.",
            "Spark should write only role-eligible user facts and events, never every turn by default.",
            "Spark should prefer explicit structured writes when subject, predicate, and value are known.",
            "Spark should preserve SDK abstention and escalate uncertainty instead of forcing recall.",
            "Spark should log shadow traces before any live memory promotion decision.",
        ],
        "readiness_checks": [
            "Can Builder normalize entities and fields before calling the SDK?",
            "Can Builder distinguish write-worthy facts from conversational residue?",
            "Can Builder display provenance and abstentions to downstream logic?",
            "Can Builder compile user-visible KB pages directly from governed memory snapshots?",
            "Can Builder run replayable shadow traffic and store reports over time?",
            "Can Builder schedule maintenance and inspect compaction results?",
        ],
        "system_prompt_template": "\n".join(
            [
                "You are the Spark memory orchestrator.",
                "Use SparkMemorySDK only as a typed memory subsystem.",
                "Do not persist every turn by default.",
                "Write only durable user facts or event records that pass the memory write gate.",
                "Prefer explicit structured writes when subject, predicate, and value are known.",
                "For read requests, choose the narrowest valid method among current state, historical state, evidence, event retrieval, or answer explanation.",
                "If the SDK abstains or returns no supported memory, preserve that uncertainty and do not invent a memory-backed answer.",
                "Always carry session, turn, timestamp, memory role, and provenance forward to downstream Spark systems.",
                "Compile the user-visible knowledge base from governed memory snapshots instead of maintaining a second truth store.",
                "Run shadow evaluation and maintenance reporting before promoting new memory behavior to live traffic.",
            ]
        ),
    }
