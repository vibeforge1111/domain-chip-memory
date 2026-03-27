"""domain-chip-memory package."""

from .sdk import (
    AnswerExplanationRequest,
    CurrentStateRequest,
    EventRetrievalRequest,
    EvidenceRetrievalRequest,
    HistoricalStateRequest,
    MemoryWriteRequest,
    SparkMemorySDK,
    build_sdk_contract_summary,
)
from .spark_shadow import (
    SparkShadowIngestAdapter,
    SparkShadowIngestRequest,
    SparkShadowTurn,
    build_shadow_ingest_contract_summary,
)

__all__ = [
    "__version__",
    "SparkMemorySDK",
    "MemoryWriteRequest",
    "CurrentStateRequest",
    "HistoricalStateRequest",
    "EvidenceRetrievalRequest",
    "EventRetrievalRequest",
    "AnswerExplanationRequest",
    "build_sdk_contract_summary",
    "SparkShadowIngestAdapter",
    "SparkShadowTurn",
    "SparkShadowIngestRequest",
    "build_shadow_ingest_contract_summary",
]
__version__ = "0.1.0"
