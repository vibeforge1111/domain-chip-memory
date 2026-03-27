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
)

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
    "SparkShadowIngestAdapter",
    "SparkShadowTurn",
    "SparkShadowIngestRequest",
    "SparkShadowProbe",
    "SparkShadowReport",
    "build_shadow_report",
    "build_shadow_ingest_contract_summary",
    "build_shadow_replay_contract_summary",
]
__version__ = "0.1.0"
