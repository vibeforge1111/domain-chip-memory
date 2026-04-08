"""domain-chip-memory package."""

from .sdk import (
    AnswerExplanationRequest,
    CurrentStateRequest,
    EventRetrievalRequest,
    EvidenceRetrievalRequest,
    HistoricalStateRequest,
    MemoryMaintenanceResult,
    MemoryWriteRequest,
    SparkMemorySDK,
    build_sdk_contract_summary,
    build_sdk_maintenance_replay_contract_summary,
)
from .spark_shadow import (
    SparkShadowIngestAdapter,
    SparkShadowIngestRequest,
    SparkShadowReport,
    SparkShadowProbe,
    SparkShadowTurn,
    build_shadow_report,
    build_shadow_ingest_contract_summary,
    build_shadow_replay_contract_summary,
    validate_shadow_replay_payload,
)
from .spark_integration import build_spark_integration_contract_summary
from .spark_kb import build_spark_kb_contract_summary, scaffold_spark_knowledge_base

__all__ = [
    "__version__",
    "SparkMemorySDK",
    "MemoryWriteRequest",
    "MemoryMaintenanceResult",
    "CurrentStateRequest",
    "HistoricalStateRequest",
    "EvidenceRetrievalRequest",
    "EventRetrievalRequest",
    "AnswerExplanationRequest",
    "build_sdk_contract_summary",
    "build_sdk_maintenance_replay_contract_summary",
    "SparkShadowIngestAdapter",
    "SparkShadowTurn",
    "SparkShadowIngestRequest",
    "SparkShadowProbe",
    "SparkShadowReport",
    "build_shadow_report",
    "build_shadow_ingest_contract_summary",
    "build_shadow_replay_contract_summary",
    "validate_shadow_replay_payload",
    "build_spark_integration_contract_summary",
    "build_spark_kb_contract_summary",
    "scaffold_spark_knowledge_base",
]
__version__ = "0.1.0"
