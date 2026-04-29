from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

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
    backend: str | None = None
    db_path: str | None = None
    neo4j_uri: str | None = None
    neo4j_user: str | None = None
    neo4j_password: str | None = None
    telemetry_disabled: bool = True
    auto_build_indices: bool = False
    client: Any | None = None
    client_factory: Callable[["GraphitiCompatibleMemorySidecarAdapter"], Any] | None = None
    _client_initialized: bool = False

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
        client_status, client_or_error = self._get_live_client()
        if client_status != "ready":
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
                    "backend_status": client_status,
                    "backend": self.backend or "not_configured",
                    "error": client_or_error if isinstance(client_or_error, str) else None,
                    "graphiti_episode": payload,
                },
            )
        try:
            sidecar_id = self._add_episode_to_graphiti(client_or_error, payload)
        except Exception as exc:
            return MemorySidecarUpsertResult(
                sidecar_name=self.sidecar_name,
                status="error",
                sidecar_ids=[],
                trace={
                    "operation": "graphiti_upsert_episode",
                    "sidecar_name": self.sidecar_name,
                    "mode": self.mode,
                    "persisted": False,
                    "backend_configured": True,
                    "backend": self.backend or "injected_client",
                    "error": exc.__class__.__name__,
                    "graphiti_episode": payload,
                },
            )
        return MemorySidecarUpsertResult(
            sidecar_name=self.sidecar_name,
            status="persisted",
            sidecar_ids=[sidecar_id] if sidecar_id else [episode.source_record_id],
            trace={
                "operation": "graphiti_upsert_episode",
                "sidecar_name": self.sidecar_name,
                "mode": self.mode,
                "persisted": True,
                "backend_configured": True,
                "backend": self.backend or "injected_client",
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
        client_status, client_or_error = self._get_live_client()
        if client_status != "ready":
            return MemorySidecarRetrievalResult(
                sidecar_name=self.sidecar_name,
                hits=[],
                trace={
                    "operation": "graphiti_retrieve",
                    "sidecar_name": self.sidecar_name,
                    "mode": self.mode,
                    "status": "prepared",
                    "backend_configured": False,
                    "backend_status": client_status,
                    "backend": self.backend or "not_configured",
                    "error": client_or_error if isinstance(client_or_error, str) else None,
                    "query_payload": query_payload,
                },
            )
        try:
            raw_results = self._search_graphiti(client_or_error, request)
            hits = [self._graphiti_result_to_hit(result, request, index) for index, result in enumerate(raw_results)]
        except Exception as exc:
            return MemorySidecarRetrievalResult(
                sidecar_name=self.sidecar_name,
                hits=[],
                trace={
                    "operation": "graphiti_retrieve",
                    "sidecar_name": self.sidecar_name,
                    "mode": self.mode,
                    "status": "error",
                    "backend_configured": True,
                    "backend": self.backend or "injected_client",
                    "error": exc.__class__.__name__,
                    "query_payload": query_payload,
                },
            )
        return MemorySidecarRetrievalResult(
            sidecar_name=self.sidecar_name,
            hits=hits,
            trace={
                "operation": "graphiti_retrieve",
                "sidecar_name": self.sidecar_name,
                "mode": self.mode,
                "status": "ok",
                "backend_configured": True,
                "backend": self.backend or "injected_client",
                "hit_count": len(hits),
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
        client_status, client_or_error = self._get_live_client()
        if client_status == "ready":
            return MemorySidecarHealthResult(
                sidecar_name=self.sidecar_name,
                status="ok",
                enabled=True,
                mode=self.mode,
                details={
                    "runtime_effect": "shadow_live_backend",
                    "authority": "not_authoritative",
                    "backend": self.backend or "injected_client",
                    "telemetry_disabled": self.telemetry_disabled,
                    "auto_build_indices": self.auto_build_indices,
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
                "backend": self.backend or "not_configured",
                "backend_status": client_status,
                "error": client_or_error if isinstance(client_or_error, str) else None,
                "telemetry_disabled": self.telemetry_disabled,
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

    def _get_live_client(self) -> tuple[str, Any]:
        if self.telemetry_disabled:
            os.environ.setdefault("GRAPHITI_TELEMETRY_ENABLED", "false")
            os.environ.setdefault("ZEP_TELEMETRY_DISABLED", "true")
        if self.client is not None:
            return "ready", self.client
        if self.client_factory is not None:
            try:
                self.client = self.client_factory(self)
                return "ready", self.client
            except Exception as exc:
                return "client_factory_error", exc.__class__.__name__
        backend = str(self.backend or "").strip().lower()
        if not backend:
            return "not_configured", "backend_not_configured"
        try:
            if backend == "kuzu":
                self.client = self._create_kuzu_client()
            elif backend == "neo4j":
                self.client = self._create_neo4j_client()
            else:
                return "unsupported_backend", backend
            if self.auto_build_indices and not self._client_initialized and hasattr(self.client, "build_indices_and_constraints"):
                _run_maybe_async(self.client.build_indices_and_constraints())
                self._client_initialized = True
            return "ready", self.client
        except ImportError as exc:
            return "missing_dependency", exc.__class__.__name__
        except Exception as exc:
            return "client_init_error", exc.__class__.__name__

    def _create_kuzu_client(self) -> Any:
        from graphiti_core import Graphiti
        from graphiti_core.driver.kuzu_driver import KuzuDriver

        driver = KuzuDriver(db=self.db_path or os.environ.get("KUZU_DB") or ":memory:")
        try:
            return Graphiti(graph_driver=driver)
        except TypeError:
            return Graphiti(driver=driver)

    def _create_neo4j_client(self) -> Any:
        from graphiti_core import Graphiti

        uri = self.neo4j_uri or os.environ.get("NEO4J_URI")
        user = self.neo4j_user or os.environ.get("NEO4J_USER")
        password = self.neo4j_password or os.environ.get("NEO4J_PASSWORD")
        if not uri or not user or not password:
            raise ValueError("neo4j_config_incomplete")
        return Graphiti(uri, user, password)

    def _add_episode_to_graphiti(self, client: Any, payload: JsonDict) -> str | None:
        result = _run_maybe_async(
            client.add_episode(
                name=payload["name"],
                episode_body=payload["episode_body"],
                source=_graphiti_episode_type(),
                source_description=payload["source_description"],
                reference_time=_parse_graphiti_reference_time(payload.get("reference_time")),
                group_id=payload["group_id"],
            )
        )
        return str(getattr(result, "uuid", "") or payload["name"] or "")

    def _search_graphiti(self, client: Any, request: MemorySidecarRetrievalRequest) -> list[Any]:
        try:
            result = _run_maybe_async(client.search(request.query, num_results=request.top_k))
        except TypeError:
            result = _run_maybe_async(client.search(request.query))
        if result is None:
            return []
        if isinstance(result, list):
            return result[: request.top_k]
        edges = getattr(result, "edges", None)
        if isinstance(edges, list):
            return edges[: request.top_k]
        return list(result)[: request.top_k]

    def _graphiti_result_to_hit(
        self,
        result: Any,
        request: MemorySidecarRetrievalRequest,
        index: int,
    ) -> MemorySidecarHit:
        uuid = str(_get_attr_or_item(result, "uuid") or _get_attr_or_item(result, "id") or f"graphiti-hit-{index}")
        text = str(
            _get_attr_or_item(result, "fact")
            or _get_attr_or_item(result, "text")
            or _get_attr_or_item(result, "content")
            or ""
        ).strip()
        score = _coerce_float(_get_attr_or_item(result, "score"), default=max(0.1, 1.0 - (index * 0.08)))
        return MemorySidecarHit(
            sidecar_name=self.sidecar_name,
            source_class="graphiti_temporal_graph",
            source_record_id=uuid,
            text=text,
            score=score,
            provenance={
                "source": "graphiti",
                "uuid": uuid,
                "group_id": self.group_id,
                "query": request.query,
                "rank": index + 1,
            },
            validity={
                "valid_at": _stringify_optional(_get_attr_or_item(result, "valid_at")),
                "invalid_at": _stringify_optional(_get_attr_or_item(result, "invalid_at")),
            },
            confidence=score,
            entity_keys=list(request.entity_keys),
            reason_selected="graphiti_live_shadow_hit",
            metadata={
                "authority": "supporting_not_authoritative",
                "sidecar_live_backend": True,
                "scope": request.scope,
            },
        )


@dataclass
class Mem0ShadowMemorySidecarAdapter(DisabledMemorySidecarAdapter):
    sidecar_name: str = "mem0_shadow"
    mode: str = "disabled"
    enabled: bool = False
    user_id: str = "spark-memory"

    def upsert_episode(self, episode: MemorySidecarEpisode) -> MemorySidecarUpsertResult:
        payload = self.mem0_memory_payload(episode)
        if not self.enabled:
            return MemorySidecarUpsertResult(
                sidecar_name=self.sidecar_name,
                status="disabled",
                sidecar_ids=[],
                trace={
                    "operation": "mem0_add_memory",
                    "sidecar_name": self.sidecar_name,
                    "mode": self.mode,
                    "persisted": False,
                    "mem0_memory": payload,
                },
            )
        return MemorySidecarUpsertResult(
            sidecar_name=self.sidecar_name,
            status="prepared",
            sidecar_ids=[],
            trace={
                "operation": "mem0_add_memory",
                "sidecar_name": self.sidecar_name,
                "mode": self.mode,
                "persisted": False,
                "backend_configured": False,
                "mem0_memory": payload,
            },
        )

    def retrieve(self, request: MemorySidecarRetrievalRequest) -> MemorySidecarRetrievalResult:
        payload = self.mem0_query_payload(request)
        if not self.enabled:
            return MemorySidecarRetrievalResult(
                sidecar_name=self.sidecar_name,
                hits=[],
                trace={
                    "operation": "mem0_search_memory",
                    "sidecar_name": self.sidecar_name,
                    "mode": self.mode,
                    "status": "disabled",
                    "query_payload": payload,
                },
            )
        return MemorySidecarRetrievalResult(
            sidecar_name=self.sidecar_name,
            hits=[],
            trace={
                "operation": "mem0_search_memory",
                "sidecar_name": self.sidecar_name,
                "mode": self.mode,
                "status": "prepared",
                "backend_configured": False,
                "query_payload": payload,
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

    def mem0_memory_payload(self, episode: MemorySidecarEpisode) -> JsonDict:
        return {
            "messages": [{"role": "user", "content": episode.text}],
            "user_id": self.user_id,
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
                "authority": "shadow_not_authoritative",
            },
        }

    def mem0_query_payload(self, request: MemorySidecarRetrievalRequest) -> JsonDict:
        return {
            "query": request.query,
            "user_id": self.user_id,
            "limit": request.top_k,
            "filters": {
                "subject": request.subject,
                "scope": request.scope,
                "entity_keys": list(request.entity_keys),
                "time_window": dict(request.time_window),
            },
        }


def build_default_memory_sidecars(
    *,
    enable_graphiti: bool = False,
    enable_mem0_shadow: bool = False,
    graphiti_backend: str | None = None,
    graphiti_db_path: str | None = None,
    graphiti_group_id: str = "spark-memory",
    graphiti_client: Any | None = None,
    graphiti_client_factory: Callable[[GraphitiCompatibleMemorySidecarAdapter], Any] | None = None,
) -> dict[str, MemorySidecarAdapter]:
    return {
        "graphiti_temporal_graph": GraphitiCompatibleMemorySidecarAdapter(
            mode="shadow" if enable_graphiti else "disabled",
            enabled=enable_graphiti,
            backend=graphiti_backend,
            db_path=graphiti_db_path,
            group_id=graphiti_group_id,
            client=graphiti_client,
            client_factory=graphiti_client_factory,
        ),
        "mem0_shadow": Mem0ShadowMemorySidecarAdapter(
            mode="shadow" if enable_mem0_shadow else "disabled",
            enabled=enable_mem0_shadow,
        ),
    }


def memory_record_to_sidecar_episode(
    record: Any,
    *,
    source_class: str | None = None,
) -> MemorySidecarEpisode:
    metadata = dict(getattr(record, "metadata", {}) or {})
    lifecycle = dict(getattr(record, "lifecycle", {}) or {})
    observation_id = str(getattr(record, "observation_id", "") or "").strip()
    event_id = str(getattr(record, "event_id", "") or "").strip()
    session_id = str(getattr(record, "session_id", "") or "").strip()
    turn_ids = [str(item).strip() for item in getattr(record, "turn_ids", []) if str(item).strip()]
    source_record_id = (
        observation_id
        or event_id
        or _fallback_record_id(session_id=session_id, turn_ids=turn_ids)
    )
    memory_role = str(getattr(record, "memory_role", "") or "").strip() or "unknown"
    return MemorySidecarEpisode(
        source_record_id=source_record_id,
        source_class=source_class or _sidecar_source_class(memory_role),
        text=str(getattr(record, "text", "") or "").strip(),
        subject=str(getattr(record, "subject", "") or "").strip() or None,
        predicate=str(getattr(record, "predicate", "") or "").strip() or None,
        session_id=session_id or None,
        turn_ids=turn_ids,
        timestamp=str(getattr(record, "timestamp", "") or "").strip() or None,
        entity_keys=_episode_entity_keys(metadata),
        lifecycle=lifecycle,
        metadata={
            **metadata,
            "memory_role": memory_role,
            "observation_id": observation_id or None,
            "event_id": event_id or None,
            "retention_class": getattr(record, "retention_class", None),
            "sidecar_episode_export": True,
        },
    )


def memory_records_to_sidecar_episodes(records: list[Any]) -> list[MemorySidecarEpisode]:
    return [memory_record_to_sidecar_episode(record) for record in records]


def _fallback_record_id(*, session_id: str, turn_ids: list[str]) -> str:
    if session_id and turn_ids:
        return f"{session_id}:{','.join(turn_ids)}"
    if session_id:
        return session_id
    if turn_ids:
        return ",".join(turn_ids)
    return "unknown-record"


def _sidecar_source_class(memory_role: str) -> str:
    if memory_role == "event":
        return "retrieved_events"
    if memory_role == "current_state":
        return "current_state"
    if memory_role == "state_deletion":
        return "state_deletion"
    if memory_role == "episodic":
        return "recent_conversation"
    return "retrieved_evidence"


def _episode_entity_keys(metadata: JsonDict) -> list[str]:
    entity_keys = metadata.get("entity_keys")
    if isinstance(entity_keys, list):
        return [str(item).strip() for item in entity_keys if str(item).strip()]
    entity_key = str(metadata.get("entity_key") or "").strip()
    return [entity_key] if entity_key else []


def _record_id(item: JsonDict) -> str:
    for key in ("source_record_id", "observation_id", "event_id", "id"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return str(item)


def _run_maybe_async(value: Any) -> Any:
    if not hasattr(value, "__await__"):
        return value
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(value)
    raise RuntimeError("graphiti_async_call_requires_sync_context")


def _graphiti_episode_type() -> Any:
    try:
        from graphiti_core.nodes import EpisodeType

        return EpisodeType.text
    except Exception:
        return "text"


def _parse_graphiti_reference_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        normalized = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _get_attr_or_item(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _coerce_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _stringify_optional(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def build_memory_sidecar_contract_summary() -> JsonDict:
    from .wiki_packets import build_wiki_packet_reader_contract_summary

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
        "episode_export_methods": [
            "memory_record_to_sidecar_episode",
            "memory_records_to_sidecar_episodes",
        ],
        "adapter_implementations": [
            "DisabledMemorySidecarAdapter",
            "GraphitiCompatibleMemorySidecarAdapter",
            "Mem0ShadowMemorySidecarAdapter",
            "ObsidianLlmWikiPacketReader",
        ],
        "wiki_packet_reader_contract": build_wiki_packet_reader_contract_summary(),
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
