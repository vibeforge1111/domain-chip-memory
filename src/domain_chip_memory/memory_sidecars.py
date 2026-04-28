from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .contracts import JsonDict


SIDECAR_AUTHORITY_ORDER: tuple[str, ...] = (
    "current_state",
    "entity_current_state",
    "historical_state",
    "recent_conversation",
    "retrieved_evidence",
    "retrieved_events",
    "graphiti_temporal_graph",
    "obsidian_llm_wiki_packets",
    "diagnostics_maintenance",
    "workflow_residue",
    "mem0_shadow",
)


@dataclass(frozen=True)
class MemorySidecarEpisode:
    source_record_id: str
    source_class: str
    text: str
    subject: str | None = None
    predicate: str | None = None
    session_id: str | None = None
    turn_ids: list[str] = field(default_factory=list)
    timestamp: str | None = None
    entity_keys: list[str] = field(default_factory=list)
    lifecycle: JsonDict = field(default_factory=dict)
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class MemorySidecarUpsertResult:
    sidecar_name: str
    status: str
    sidecar_ids: list[str] = field(default_factory=list)
    trace: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class MemorySidecarRetrievalRequest:
    query: str
    subject: str | None = None
    scope: str | None = None
    time_window: JsonDict = field(default_factory=dict)
    entity_keys: list[str] = field(default_factory=list)
    top_k: int = 5


@dataclass(frozen=True)
class MemorySidecarHit:
    sidecar_name: str
    source_class: str
    source_record_id: str
    text: str
    score: float
    provenance: JsonDict
    validity: JsonDict = field(default_factory=dict)
    confidence: float | None = None
    entity_keys: list[str] = field(default_factory=list)
    reason_selected: str | None = None
    reason_discarded: str | None = None
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class MemorySidecarRetrievalResult:
    sidecar_name: str
    hits: list[MemorySidecarHit]
    trace: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class MemorySidecarHealthResult:
    sidecar_name: str
    status: str
    enabled: bool
    mode: str
    details: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class MemorySidecarShadowComparison:
    sidecar_name: str
    query: str
    local_hit_count: int
    sidecar_hit_count: int
    overlap_record_ids: list[str] = field(default_factory=list)
    missing_from_sidecar_record_ids: list[str] = field(default_factory=list)
    sidecar_only_record_ids: list[str] = field(default_factory=list)
    trace: JsonDict = field(default_factory=dict)


class MemorySidecarAdapter(Protocol):
    sidecar_name: str
    mode: str

    def upsert_episode(self, episode: MemorySidecarEpisode) -> MemorySidecarUpsertResult:
        ...

    def retrieve(self, request: MemorySidecarRetrievalRequest) -> MemorySidecarRetrievalResult:
        ...

    def explain(self, hit: MemorySidecarHit) -> JsonDict:
        ...

    def health(self) -> MemorySidecarHealthResult:
        ...

    def shadow_compare(
        self,
        *,
        query: str,
        local_hits: list[JsonDict],
        sidecar_hits: list[MemorySidecarHit],
    ) -> MemorySidecarShadowComparison:
        ...


@dataclass
class DisabledMemorySidecarAdapter:
    sidecar_name: str
    mode: str = "disabled"

    def upsert_episode(self, episode: MemorySidecarEpisode) -> MemorySidecarUpsertResult:
        return MemorySidecarUpsertResult(
            sidecar_name=self.sidecar_name,
            status="disabled",
            sidecar_ids=[],
            trace={
                "operation": "sidecar_upsert_episode",
                "sidecar_name": self.sidecar_name,
                "mode": self.mode,
                "persisted": False,
                "source_record_id": episode.source_record_id,
            },
        )

    def retrieve(self, request: MemorySidecarRetrievalRequest) -> MemorySidecarRetrievalResult:
        return MemorySidecarRetrievalResult(
            sidecar_name=self.sidecar_name,
            hits=[],
            trace={
                "operation": "sidecar_retrieve",
                "sidecar_name": self.sidecar_name,
                "mode": self.mode,
                "query": request.query,
                "subject": request.subject,
                "scope": request.scope,
                "top_k": request.top_k,
                "status": "disabled",
            },
        )

    def explain(self, hit: MemorySidecarHit) -> JsonDict:
        return {
            "sidecar_name": self.sidecar_name,
            "status": "disabled",
            "source_class": hit.source_class,
            "source_record_id": hit.source_record_id,
            "provenance": dict(hit.provenance),
            "validity": dict(hit.validity),
        }

    def health(self) -> MemorySidecarHealthResult:
        return MemorySidecarHealthResult(
            sidecar_name=self.sidecar_name,
            status="disabled",
            enabled=False,
            mode=self.mode,
            details={
                "runtime_effect": "none",
                "authority": "not_authoritative",
            },
        )

    def shadow_compare(
        self,
        *,
        query: str,
        local_hits: list[JsonDict],
        sidecar_hits: list[MemorySidecarHit],
    ) -> MemorySidecarShadowComparison:
        local_ids = [_record_id(hit) for hit in local_hits]
        sidecar_ids = [hit.source_record_id for hit in sidecar_hits if hit.source_record_id]
        overlap = sorted(set(local_ids).intersection(sidecar_ids))
        return MemorySidecarShadowComparison(
            sidecar_name=self.sidecar_name,
            query=query,
            local_hit_count=len(local_hits),
            sidecar_hit_count=len(sidecar_hits),
            overlap_record_ids=overlap,
            missing_from_sidecar_record_ids=sorted(set(local_ids) - set(sidecar_ids)),
            sidecar_only_record_ids=sorted(set(sidecar_ids) - set(local_ids)),
            trace={
                "operation": "sidecar_shadow_compare",
                "sidecar_name": self.sidecar_name,
                "mode": self.mode,
                "status": "disabled" if self.mode == "disabled" else "ok",
            },
        )


@dataclass
class GraphitiCompatibleMemorySidecarAdapter(DisabledMemorySidecarAdapter):
    sidecar_name: str = "graphiti_temporal_graph"
    mode: str = "disabled"
    enabled: bool = False
    group_id: str = "spark-memory"

    def upsert_episode(self, episode: MemorySidecarEpisode) -> MemorySidecarUpsertResult:
        payload = self.graphiti_episode_payload(episode)
        if not self.enabled:
            return MemorySidecarUpsertResult(
                sidecar_name=self.sidecar_name,
                status="disabled",
                sidecar_ids=[],
                trace={
                    "operation": "graphiti_upsert_episode",
                    "sidecar_name": self.sidecar_name,
                    "mode": self.mode,
                    "persisted": False,
                    "graphiti_episode": payload,
                },
            )
        return MemorySidecarUpsertResult(
            sidecar_name=self.sidecar_name,
            status="prepared",
            sidecar_ids=[],
            trace={
                "operation": "graphiti_upsert_episode",
                "sidecar_name": self.sidecar_name,
                "mode": self.mode,
                "persisted": False,
                "backend_configured": False,
                "graphiti_episode": payload,
            },
        )

    def retrieve(self, request: MemorySidecarRetrievalRequest) -> MemorySidecarRetrievalResult:
        query_payload = self.graphiti_query_payload(request)
        if not self.enabled:
            return MemorySidecarRetrievalResult(
                sidecar_name=self.sidecar_name,
                hits=[],
                trace={
                    "operation": "graphiti_retrieve",
                    "sidecar_name": self.sidecar_name,
                    "mode": self.mode,
                    "status": "disabled",
                    "query_payload": query_payload,
                },
            )
        return MemorySidecarRetrievalResult(
            sidecar_name=self.sidecar_name,
            hits=[],
            trace={
                "operation": "graphiti_retrieve",
                "sidecar_name": self.sidecar_name,
                "mode": self.mode,
                "status": "prepared",
                "backend_configured": False,
                "query_payload": query_payload,
            },
        )

    def health(self) -> MemorySidecarHealthResult:
        if not self.enabled:
            return MemorySidecarHealthResult(
                sidecar_name=self.sidecar_name,
                status="disabled",
                enabled=False,
                mode=self.mode,
                details={
                    "runtime_effect": "none",
                    "authority": "not_authoritative",
                    "backend": "not_configured",
                },
            )
        return MemorySidecarHealthResult(
            sidecar_name=self.sidecar_name,
            status="stub_ready",
            enabled=True,
            mode=self.mode,
            details={
                "runtime_effect": "shadow_contract_only",
                "authority": "not_authoritative",
                "backend": "not_configured",
            },
        )

    def graphiti_episode_payload(self, episode: MemorySidecarEpisode) -> JsonDict:
        return {
            "group_id": self.group_id,
            "name": episode.source_record_id,
            "episode_body": episode.text,
            "source_description": episode.source_class,
            "reference_time": episode.timestamp,
            "metadata": {
                **dict(episode.metadata),
                "source_record_id": episode.source_record_id,
                "source_class": episode.source_class,
                "subject": episode.subject,
                "predicate": episode.predicate,
                "session_id": episode.session_id,
                "turn_ids": list(episode.turn_ids),
                "entity_keys": list(episode.entity_keys),
                "lifecycle": dict(episode.lifecycle),
                "authority": "supporting",
            },
        }

    def graphiti_query_payload(self, request: MemorySidecarRetrievalRequest) -> JsonDict:
        return {
            "group_id": self.group_id,
            "query": request.query,
            "num_results": request.top_k,
            "scope": request.scope,
            "filters": {
                "subject": request.subject,
                "entity_keys": list(request.entity_keys),
                "time_window": dict(request.time_window),
            },
        }


def build_default_memory_sidecars(
    *,
    enable_graphiti: bool = False,
    enable_mem0_shadow: bool = False,
) -> dict[str, MemorySidecarAdapter]:
    return {
        "graphiti_temporal_graph": GraphitiCompatibleMemorySidecarAdapter(
            mode="shadow" if enable_graphiti else "disabled",
            enabled=enable_graphiti,
        ),
        "mem0_shadow": DisabledMemorySidecarAdapter(
            sidecar_name="mem0_shadow",
            mode="shadow" if enable_mem0_shadow else "disabled",
        ),
    }


def _record_id(item: JsonDict) -> str:
    for key in ("source_record_id", "observation_id", "event_id", "id"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return str(item)


def build_memory_sidecar_contract_summary() -> JsonDict:
    return {
        "contract_name": "MemorySidecarAdapter",
        "authority_policy": {
            "domain_chip_memory": "source_of_truth",
            "sidecars": "supporting_or_shadow_until_promoted",
            "authority_order": list(SIDECAR_AUTHORITY_ORDER),
            "non_override_rules": [
                "Graphiti-compatible hits cannot override current_state for current questions.",
                "Mem0 results are shadow candidates until separately promoted.",
                "Obsidian/LLM-wiki packets guide project knowledge but do not own mutable facts.",
                "Workflow residue remains advisory only.",
            ],
        },
        "adapter_methods": [
            "upsert_episode",
            "retrieve",
            "explain",
            "health",
            "shadow_compare",
        ],
        "adapter_implementations": [
            "DisabledMemorySidecarAdapter",
            "GraphitiCompatibleMemorySidecarAdapter",
        ],
        "runtime_sidecars": {
            "graphiti_temporal_graph": {
                "mode": "shadow_then_limited_runtime",
                "purpose": "temporal entity graph, validity windows, relationships, provenance",
                "first_runtime_candidate": True,
                "authoritative": False,
            },
            "obsidian_llm_wiki_packets": {
                "mode": "supporting_context",
                "purpose": "compiled project knowledge, research, decisions, handoffs",
                "first_runtime_candidate": True,
                "authoritative": False,
            },
            "mem0_shadow": {
                "mode": "shadow_baseline",
                "purpose": "personal memory extraction/search comparison",
                "first_runtime_candidate": False,
                "authoritative": False,
            },
            "cognee_optional": {
                "mode": "deferred",
                "purpose": "connector/document graph-RAG only if wiki packets plus Graphiti are insufficient",
                "first_runtime_candidate": False,
                "authoritative": False,
            },
        },
        "request_contracts": [
            "MemorySidecarEpisode",
            "MemorySidecarRetrievalRequest",
        ],
        "response_contracts": [
            "MemorySidecarUpsertResult",
            "MemorySidecarRetrievalResult",
            "MemorySidecarHit",
            "MemorySidecarHealthResult",
            "MemorySidecarShadowComparison",
        ],
        "required_hit_fields": [
            "sidecar_name",
            "source_class",
            "source_record_id",
            "text",
            "score",
            "provenance",
            "validity",
            "confidence",
            "entity_keys",
            "reason_selected",
            "reason_discarded",
        ],
        "promotion_gates": [
            "current_vs_stale_conflict",
            "previous_value_recall",
            "open_ended_recall",
            "source_swamp_resistance",
            "identity_entity_resolution",
            "temporal_event_ordering",
            "source_explanation",
            "telegram_acceptance",
        ],
    }
