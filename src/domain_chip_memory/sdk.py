from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
import re
from typing import Any

from .contracts import JsonDict, MemoryRole, NormalizedBenchmarkSample, NormalizedQuestion, NormalizedSession, NormalizedTurn, RetentionClass
from .memory_extraction import EventCalendarEntry, ObservationEntry
from .memory_observation_runtime import build_event_calendar, build_observation_log
from .memory_roles import canonical_memory_role, sdk_memory_role_contracts
from .memory_retention import default_retention_class, sdk_retention_contracts, sdk_retention_defaults_by_role
from .memory_updates import (
    build_current_state_view,
    entry_sort_key,
    has_active_state_deletion,
    observation_id_sort_key,
    state_deletion_target,
)


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _timestamp_key(timestamp: str | None) -> str:
    return timestamp or ""


def _normalize_scalar(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_human_subject(value: str | None) -> str:
    normalized = _normalize_scalar(value).lower()
    if normalized.startswith("human:human:"):
        normalized = normalized[len("human:") :]
    if normalized.startswith("telegram:"):
        normalized = f"human:{normalized}"
    return normalized


def _is_identity_summary_query(query: str | None) -> bool:
    normalized = _normalize_scalar(query).lower().rstrip("?.! ")
    return normalized in {"who am i", "what do you know about me"}


DEFAULT_RUNTIME_MEMORY_ARCHITECTURE = "dual_store_event_calendar_hybrid"
DEFAULT_RUNTIME_MEMORY_PROVIDER = "heuristic_v1"
SDK_LIFECYCLE_FIELDS: tuple[str, ...] = (
    "created_at",
    "document_time",
    "event_time",
    "valid_from",
    "valid_to",
    "supersedes",
    "conflicts_with",
    "deleted_at",
)


def _runtime_memory_architecture() -> str:
    return _normalize_scalar(
        os.environ.get("SPARK_MEMORY_RUNTIME_ARCHITECTURE") or DEFAULT_RUNTIME_MEMORY_ARCHITECTURE
    )


def _runtime_memory_provider() -> str:
    return _normalize_scalar(
        os.environ.get("SPARK_MEMORY_RUNTIME_PROVIDER") or DEFAULT_RUNTIME_MEMORY_PROVIDER
    )


@dataclass(frozen=True)
class MemoryWriteRequest:
    text: str
    speaker: str = "user"
    timestamp: str | None = None
    session_id: str | None = None
    turn_id: str | None = None
    operation: str = "auto"
    subject: str | None = None
    predicate: str | None = None
    value: str | None = None
    retention_class: RetentionClass | None = None
    document_time: str | None = None
    event_time: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    supersedes: str | None = None
    conflicts_with: list[str] = field(default_factory=list)
    deleted_at: str | None = None
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class CurrentStateRequest:
    subject: str
    predicate: str


@dataclass(frozen=True)
class HistoricalStateRequest:
    subject: str
    predicate: str
    as_of: str


@dataclass(frozen=True)
class EvidenceRetrievalRequest:
    query: str | None = None
    subject: str | None = None
    predicate: str | None = None
    limit: int = 5


@dataclass(frozen=True)
class EventRetrievalRequest:
    query: str | None = None
    subject: str | None = None
    predicate: str | None = None
    limit: int = 5


@dataclass(frozen=True)
class AnswerExplanationRequest:
    question: str
    subject: str
    predicate: str
    as_of: str | None = None
    evidence_limit: int = 3
    event_limit: int = 3


@dataclass(frozen=True)
class RetrievedMemoryRecord:
    memory_role: MemoryRole
    subject: str
    predicate: str
    text: str
    session_id: str
    turn_ids: list[str]
    timestamp: str | None
    retention_class: RetentionClass | None = None
    lifecycle: JsonDict = field(default_factory=dict)
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryWriteResult:
    session_id: str
    turn_id: str
    accepted: bool
    observations_written: int
    events_written: int
    observations: list[RetrievedMemoryRecord]
    events: list[RetrievedMemoryRecord]
    unsupported_reason: str | None = None
    trace: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryLookupResult:
    found: bool
    value: str | None
    text: str | None
    memory_role: MemoryRole
    provenance: list[RetrievedMemoryRecord]
    trace: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryRetrievalResult:
    items: list[RetrievedMemoryRecord]
    trace: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class AnswerExplanationResult:
    found: bool
    answer: str | None
    memory_role: MemoryRole
    explanation: str
    provenance: list[RetrievedMemoryRecord]
    evidence: list[RetrievedMemoryRecord]
    events: list[RetrievedMemoryRecord]
    trace: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryMaintenanceResult:
    manual_observations_before: int
    manual_observations_after: int
    current_state_snapshot_count: int
    active_deletion_count: int
    manual_events_count: int
    trace: JsonDict = field(default_factory=dict)


class SparkMemorySDK:
    def __init__(self) -> None:
        self._sessions: list[NormalizedSession] = []
        self._session_counter = 0
        self._manual_observations: list[ObservationEntry] = []
        self._manual_events: list[EventCalendarEntry] = []
        self._manual_current_state_snapshot: list[ObservationEntry] = []

    def write_observation(self, request: MemoryWriteRequest) -> MemoryWriteResult:
        return self._write(request, write_kind="observation")

    def write_event(self, request: MemoryWriteRequest) -> MemoryWriteResult:
        return self._write(request, write_kind="event")

    def get_current_state(self, request: CurrentStateRequest) -> MemoryLookupResult:
        invalid_reason = self._invalid_subject_predicate_reason(request.subject, request.predicate)
        if invalid_reason:
            return self._invalid_lookup_result(
                operation="get_current_state",
                subject=request.subject,
                predicate=request.predicate,
                reason=invalid_reason,
            )
        subject = self._normalize_subject(request.subject)
        predicate = self._normalize_predicate(request.predicate)
        observations = self._current_state_observations()
        reflected = build_current_state_view(observations)
        matches = [
            entry
            for entry in reflected
            if entry.subject == subject and entry.predicate == predicate
        ]
        if matches:
            selected = sorted(matches, key=entry_sort_key)[-1]
            return MemoryLookupResult(
                found=True,
                value=str(selected.metadata.get("value", "")).strip() or None,
                text=selected.text,
                memory_role="current_state",
                provenance=[self._observation_record(selected, memory_role="current_state")],
                trace=self._lookup_trace(
                    operation="get_current_state",
                    subject=subject,
                    predicate=predicate,
                    observation_count=len(observations),
                    memory_role="current_state",
                    provenance_roles=["current_state"],
                    provenance_items=[self._observation_record(selected, memory_role="current_state")],
                ),
            )
        if has_active_state_deletion(observations, subject=subject, predicate=predicate):
            deletion_entries = self._deletion_entries(observations, subject=subject, predicate=predicate)
            return MemoryLookupResult(
                found=False,
                value=None,
                text=None,
                memory_role="state_deletion",
                provenance=[self._observation_record(deletion_entries[-1], memory_role="state_deletion")] if deletion_entries else [],
                trace=self._lookup_trace(
                    operation="get_current_state",
                    subject=subject,
                    predicate=predicate,
                    observation_count=len(observations),
                    memory_role="state_deletion",
                    provenance_roles=["state_deletion"] if deletion_entries else [],
                    provenance_items=[self._observation_record(deletion_entries[-1], memory_role="state_deletion")] if deletion_entries else [],
                ),
            )
        return MemoryLookupResult(
            found=False,
            value=None,
            text=None,
            memory_role="unknown",
            provenance=[],
                trace=self._lookup_trace(
                    operation="get_current_state",
                    subject=subject,
                    predicate=predicate,
                    observation_count=len(observations),
                    memory_role="unknown",
                    provenance_roles=[],
                    provenance_items=[],
                ),
            )

    def get_historical_state(self, request: HistoricalStateRequest) -> MemoryLookupResult:
        invalid_reason = self._invalid_subject_predicate_reason(request.subject, request.predicate)
        if invalid_reason:
            return self._invalid_lookup_result(
                operation="get_historical_state",
                subject=request.subject,
                predicate=request.predicate,
                reason=invalid_reason,
                extra_trace={"as_of": request.as_of},
            )
        if not str(request.as_of or "").strip():
            return self._invalid_lookup_result(
                operation="get_historical_state",
                subject=request.subject,
                predicate=request.predicate,
                reason="as_of_required",
            )
        subject = self._normalize_subject(request.subject)
        predicate = self._normalize_predicate(request.predicate)
        observations = [
            entry
            for entry in self._observations()
            if entry.timestamp is None or entry.timestamp <= request.as_of
        ]
        reflected = build_current_state_view(observations)
        matches = [
            entry
            for entry in reflected
            if entry.subject == subject and entry.predicate == predicate
        ]
        if matches:
            selected = sorted(matches, key=entry_sort_key)[-1]
            return MemoryLookupResult(
                found=True,
                value=str(selected.metadata.get("value", "")).strip() or None,
                text=selected.text,
                memory_role="structured_evidence",
                provenance=[self._observation_record(selected, memory_role="structured_evidence")],
                trace=self._lookup_trace(
                    operation="get_historical_state",
                    subject=subject,
                    predicate=predicate,
                    observation_count=len(observations),
                    memory_role="structured_evidence",
                    provenance_roles=["structured_evidence"],
                    provenance_items=[self._observation_record(selected, memory_role="structured_evidence")],
                    extra_trace={"as_of": request.as_of},
                ),
            )
        if has_active_state_deletion(observations, subject=subject, predicate=predicate):
            deletion_entries = self._deletion_entries(observations, subject=subject, predicate=predicate)
            return MemoryLookupResult(
                found=False,
                value=None,
                text=None,
                memory_role="state_deletion",
                provenance=[self._observation_record(deletion_entries[-1], memory_role="state_deletion")] if deletion_entries else [],
                trace=self._lookup_trace(
                    operation="get_historical_state",
                    subject=subject,
                    predicate=predicate,
                    observation_count=len(observations),
                    memory_role="state_deletion",
                    provenance_roles=["state_deletion"] if deletion_entries else [],
                    provenance_items=[self._observation_record(deletion_entries[-1], memory_role="state_deletion")] if deletion_entries else [],
                    extra_trace={"as_of": request.as_of},
                ),
            )
        return MemoryLookupResult(
            found=False,
            value=None,
            text=None,
            memory_role="unknown",
            provenance=[],
                trace=self._lookup_trace(
                    operation="get_historical_state",
                    subject=subject,
                    predicate=predicate,
                    observation_count=len(observations),
                    memory_role="unknown",
                    provenance_roles=[],
                    provenance_items=[],
                    extra_trace={"as_of": request.as_of},
                ),
            )

    def retrieve_evidence(self, request: EvidenceRetrievalRequest) -> MemoryRetrievalResult:
        if request.limit < 1:
            return MemoryRetrievalResult(
                items=[],
                trace={
                    "operation": "retrieve_evidence",
                    "status": "invalid_request",
                    "reason": "limit_must_be_positive",
                    "limit": request.limit,
                },
            )
        normalized_subject = self._normalize_optional_subject(request.subject)
        normalized_predicate = self._normalize_optional_predicate(request.predicate)
        query_intent = "generic"
        observations = self._observations()
        if normalized_subject and not normalized_predicate and _is_identity_summary_query(request.query):
            query_intent = "profile_identity_summary"
            observations = [
                entry
                for entry in self._current_state_observations()
                if entry.subject == normalized_subject and entry.predicate not in {"raw_turn", "state_deletion"}
            ]
        items = [
            self._observation_record(entry, memory_role=self._observation_memory_role(entry))
            for entry in self._rank_observations(
                observations,
                query=request.query,
                subject=normalized_subject,
                predicate=normalized_predicate,
                limit=request.limit,
            )
        ]
        return MemoryRetrievalResult(
            items=items,
            trace=self._retrieval_trace(
                operation="retrieve_evidence",
                items=items,
                query=request.query,
                subject=request.subject,
                predicate=request.predicate,
                limit=request.limit,
                query_intent=query_intent,
            ),
        )

    def retrieve_events(self, request: EventRetrievalRequest) -> MemoryRetrievalResult:
        if request.limit < 1:
            return MemoryRetrievalResult(
                items=[],
                trace={
                    "operation": "retrieve_events",
                    "status": "invalid_request",
                    "reason": "limit_must_be_positive",
                    "limit": request.limit,
                },
            )
        events = self._events()
        items = [
            self._event_record(entry)
            for entry in self._rank_events(
                events,
                query=request.query,
                subject=self._normalize_optional_subject(request.subject),
                predicate=self._normalize_optional_predicate(request.predicate),
                limit=request.limit,
            )
        ]
        return MemoryRetrievalResult(
            items=items,
            trace=self._retrieval_trace(
                operation="retrieve_events",
                items=items,
                query=request.query,
                subject=request.subject,
                predicate=request.predicate,
                limit=request.limit,
            ),
        )

    def explain_answer(self, request: AnswerExplanationRequest) -> AnswerExplanationResult:
        state_result = (
            self.get_historical_state(
                HistoricalStateRequest(
                    subject=request.subject,
                    predicate=request.predicate,
                    as_of=request.as_of,
                )
            )
            if request.as_of
            else self.get_current_state(
                CurrentStateRequest(
                    subject=request.subject,
                    predicate=request.predicate,
                )
            )
        )
        evidence = self.retrieve_evidence(
            EvidenceRetrievalRequest(
                query=request.question,
                subject=request.subject,
                predicate=request.predicate,
                limit=request.evidence_limit,
            )
        )
        events = self.retrieve_events(
            EventRetrievalRequest(
                query=request.question,
                subject=request.subject,
                predicate=request.predicate,
                limit=request.event_limit,
            )
        )
        if state_result.found:
            explanation = (
                f"Resolved {request.predicate} for {request.subject} to {state_result.value} "
                f"from {state_result.memory_role}."
            )
        else:
            explanation = (
                f"No supported answer for {request.predicate} of {request.subject}; "
                f"abstained with {state_result.memory_role}."
            )
        return AnswerExplanationResult(
            found=state_result.found,
            answer=state_result.value,
            memory_role=state_result.memory_role,
            explanation=explanation,
            provenance=state_result.provenance,
            evidence=evidence.items,
            events=events.items,
            trace=self._explanation_trace(
                question=request.question,
                subject=request.subject,
                predicate=request.predicate,
                as_of=request.as_of,
                state_result=state_result,
                evidence=evidence.items,
                events=events.items,
            ),
        )

    def reconsolidate_manual_memory(self) -> MemoryMaintenanceResult:
        snapshot = self._build_manual_current_state_snapshot(self._manual_observations)
        self._manual_current_state_snapshot = snapshot
        active_deletions = sum(1 for entry in snapshot if entry.predicate == "state_deletion")
        return MemoryMaintenanceResult(
            manual_observations_before=len(self._manual_observations),
            manual_observations_after=len(snapshot),
            current_state_snapshot_count=len(snapshot),
            active_deletion_count=active_deletions,
            manual_events_count=len(self._manual_events),
            trace={
                "operation": "reconsolidate_manual_memory",
                "status": "ok",
            },
        )

    def export_knowledge_base_snapshot(self) -> JsonDict:
        current_state_records = [
            self._observation_record(entry, memory_role="current_state")
            for entry in build_current_state_view(self._current_state_observations())
        ]
        observation_records = [
            self._observation_record(entry, memory_role=self._observation_memory_role(entry))
            for entry in self._observations()
        ]
        event_records = [self._event_record(entry) for entry in self._events()]
        role_contracts = sdk_memory_role_contracts()
        return {
            "runtime_class": "SparkMemorySDK",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "memory_role_contract": {
                "roles": role_contracts,
                "canonical_aliases": {
                    contract["runtime_role"]: contract["canonical_role"] for contract in role_contracts
                },
            },
            "retention_contract": {
                "classes": sdk_retention_contracts(),
                "defaults_by_memory_role": sdk_retention_defaults_by_role(),
            },
            "lifecycle_contract": {
                "fields": list(SDK_LIFECYCLE_FIELDS),
            },
            "counts": {
                "session_count": len(self._sessions),
                "current_state_count": len(current_state_records),
                "observation_count": len(observation_records),
                "event_count": len(event_records),
                "manual_observation_count": len(self._manual_observations),
                "manual_event_count": len(self._manual_events),
            },
            "sessions": [session.to_dict() for session in self._sessions],
            "current_state": [self._retrieved_record_dict(record) for record in current_state_records],
            "observations": [self._retrieved_record_dict(record) for record in observation_records],
            "events": [self._retrieved_record_dict(record) for record in event_records],
            "trace": {
                "operation": "export_knowledge_base_snapshot",
                "source_of_truth": "SparkMemorySDK",
            },
        }

    def _write(self, request: MemoryWriteRequest, *, write_kind: str) -> MemoryWriteResult:
        operation = _normalize_scalar(request.operation).lower() or "auto"
        cleaned_text = str(request.text or "").strip()
        session_id = request.session_id or self._next_session_id()
        turn_id = request.turn_id or self._next_turn_id(session_id)

        if operation == "auto" and not cleaned_text:
            return MemoryWriteResult(
                session_id=session_id,
                turn_id=turn_id,
                accepted=False,
                observations_written=0,
                events_written=0,
                observations=[],
                events=[],
                unsupported_reason="empty_text",
                trace={
                    "operation": "write_memory",
                    "status": "unsupported_write",
                    "reason": "empty_text",
                    "write_kind": write_kind,
                    "write_operation": operation,
                    "persisted": False,
                },
            )

        invalid_operation_reason = self._unsupported_operation_reason(operation, write_kind=write_kind)
        if invalid_operation_reason:
            return MemoryWriteResult(
                session_id=session_id,
                turn_id=turn_id,
                accepted=False,
                observations_written=0,
                events_written=0,
                observations=[],
                events=[],
                unsupported_reason=invalid_operation_reason,
                trace={
                    "operation": "write_memory",
                    "status": "unsupported_write",
                    "reason": invalid_operation_reason,
                    "write_kind": write_kind,
                    "write_operation": operation,
                    "persisted": False,
                },
            )

        observations: list[ObservationEntry] = []
        events: list[EventCalendarEntry] = []
        manual_write = operation != "auto"
        turn_metadata = dict(request.metadata)
        if manual_write:
            explicit_memory = self._explicit_memory_entries(
                request,
                write_kind=write_kind,
                write_operation=operation,
                session_id=session_id,
                turn_id=turn_id,
            )
            if explicit_memory["unsupported_reason"] is not None:
                return MemoryWriteResult(
                    session_id=session_id,
                    turn_id=turn_id,
                    accepted=False,
                    observations_written=0,
                    events_written=0,
                    observations=[],
                    events=[],
                    unsupported_reason=str(explicit_memory["unsupported_reason"]),
                    trace={
                        "operation": "write_memory",
                        "status": "unsupported_write",
                        "reason": str(explicit_memory["unsupported_reason"]),
                        "write_kind": write_kind,
                        "write_operation": operation,
                        "persisted": False,
                    },
                )
            observations = list(explicit_memory["observations"])
            events = list(explicit_memory["events"])
            turn_metadata.update(
                {
                    "sdk_explicit_operation": operation,
                    "sdk_manual_memory": True,
                }
            )

        turn = NormalizedTurn(
            turn_id=turn_id,
            speaker=request.speaker,
            text=cleaned_text
            or self._manual_turn_text(
                write_operation=operation,
                write_kind=write_kind,
                subject=request.subject,
                predicate=request.predicate,
                value=request.value,
            ),
            timestamp=request.timestamp,
            metadata=turn_metadata,
        )
        if not manual_write:
            single_turn_sample = self._sample_for_sessions(
                [
                    NormalizedSession(
                        session_id=session_id,
                        turns=[turn],
                        timestamp=request.timestamp,
                        metadata={},
                    )
                ]
            )
            observations = build_observation_log(single_turn_sample)
            events = build_event_calendar(single_turn_sample)

        accepted = self._write_has_supported_memory(observations, events)
        observation_records = [
            self._observation_record(entry, memory_role=self._observation_memory_role(entry))
            for entry in observations
        ]
        event_records = [self._event_record(entry) for entry in events]
        if accepted:
            self._upsert_session(session_id, turn, request.timestamp)
            if manual_write:
                self._manual_observations.extend(observations)
                self._manual_events.extend(events)
                self._manual_current_state_snapshot = []
        return MemoryWriteResult(
            session_id=session_id,
            turn_id=turn_id,
            accepted=accepted,
            observations_written=len(observations),
            events_written=len(events),
            observations=observation_records,
            events=event_records,
            unsupported_reason=None if accepted else "no_structured_memory_extracted",
            trace={
                "operation": "write_memory",
                "status": "accepted" if accepted else "unsupported_write",
                "speaker": request.speaker,
                "timestamp": request.timestamp,
                "write_kind": write_kind,
                "write_operation": operation,
                "persisted": accepted,
                "memory_roles": self._unique_memory_roles([*observation_records, *event_records]),
                "memory_role_counts": self._memory_role_counts([*observation_records, *event_records]),
                "primary_memory_role": self._primary_memory_role([*observation_records, *event_records]),
                "canonical_memory_roles": self._canonical_memory_roles([*observation_records, *event_records]),
                "retention_classes": self._unique_retention_classes([*observation_records, *event_records]),
                "primary_retention_class": self._primary_retention_class([*observation_records, *event_records]),
                "lifecycle_fields_present": self._lifecycle_fields_present_for_items([*observation_records, *event_records]),
            },
        )

    def _next_session_id(self) -> str:
        self._session_counter += 1
        return f"sdk-session-{self._session_counter}"

    def _next_turn_id(self, session_id: str) -> str:
        for session in self._sessions:
            if session.session_id == session_id:
                return f"{session_id}:t{len(session.turns) + 1}"
        return f"{session_id}:t1"

    def _upsert_session(self, session_id: str, turn: NormalizedTurn, session_timestamp: str | None) -> None:
        for index, session in enumerate(self._sessions):
            if session.session_id != session_id:
                continue
            updated_timestamp = max(
                [value for value in [session.timestamp, session_timestamp] if value is not None],
                default=None,
            )
            self._sessions[index] = NormalizedSession(
                session_id=session.session_id,
                turns=[*session.turns, turn],
                timestamp=updated_timestamp,
                metadata=dict(session.metadata),
            )
            return
        self._sessions.append(
            NormalizedSession(
                session_id=session_id,
                turns=[turn],
                timestamp=session_timestamp,
                metadata={},
            )
        )

    def _sample_for_sessions(self, sessions: list[NormalizedSession]) -> NormalizedBenchmarkSample:
        return NormalizedBenchmarkSample(
            benchmark_name="SDK",
            sample_id="spark-memory-sdk",
            sessions=sessions,
            questions=[],
            metadata={},
        )

    def _runtime_sample(self) -> NormalizedBenchmarkSample:
        filtered_sessions: list[NormalizedSession] = []
        for session in self._sessions:
            filtered_sessions.append(
                NormalizedSession(
                    session_id=session.session_id,
                    turns=[turn for turn in session.turns if not bool(turn.metadata.get("sdk_manual_memory"))],
                    timestamp=session.timestamp,
                    metadata=dict(session.metadata),
                )
            )
        return self._sample_for_sessions(filtered_sessions)

    def _current_state_observations(self) -> list[ObservationEntry]:
        manual = self._manual_current_state_snapshot or self._manual_observations
        return [*build_observation_log(self._runtime_sample()), *manual]

    def _observations(self) -> list[ObservationEntry]:
        return [*build_observation_log(self._runtime_sample()), *self._manual_observations]

    def _events(self) -> list[EventCalendarEntry]:
        return [*build_event_calendar(self._runtime_sample()), *self._manual_events]

    def _deletion_entries(
        self,
        observations: list[ObservationEntry],
        *,
        subject: str,
        predicate: str,
    ) -> list[ObservationEntry]:
        return sorted(
            [
                entry
                for entry in observations
                if entry.subject == subject and state_deletion_target(entry) == predicate
            ],
            key=lambda entry: (_timestamp_key(entry.timestamp), observation_id_sort_key(entry.observation_id)),
        )

    def _rank_observations(
        self,
        observations: list[ObservationEntry],
        *,
        query: str | None,
        subject: str | None,
        predicate: str | None,
        limit: int,
    ) -> list[ObservationEntry]:
        query_tokens = _tokenize(query or "")
        ranked: list[tuple[int, str, tuple[Any, ...], ObservationEntry]] = []
        for entry in observations:
            if subject and entry.subject != subject:
                continue
            if predicate and entry.predicate != predicate and state_deletion_target(entry) != predicate:
                continue
            overlap = len(query_tokens.intersection(_tokenize(entry.text))) if query_tokens else 0
            if query_tokens and overlap == 0 and not (subject or predicate):
                continue
            ranked.append((overlap, _timestamp_key(entry.timestamp), observation_id_sort_key(entry.observation_id), entry))
        ranked.sort(reverse=True)
        return [entry for _, _, _, entry in ranked[:limit]]

    def _rank_events(
        self,
        events: list[EventCalendarEntry],
        *,
        query: str | None,
        subject: str | None,
        predicate: str | None,
        limit: int,
    ) -> list[EventCalendarEntry]:
        query_tokens = _tokenize(query or "")
        ranked: list[tuple[int, str, str, EventCalendarEntry]] = []
        for entry in events:
            if subject and entry.subject != subject:
                continue
            if predicate and entry.predicate != predicate:
                continue
            overlap = len(query_tokens.intersection(_tokenize(entry.text))) if query_tokens else 0
            if query_tokens and overlap == 0 and not (subject or predicate):
                continue
            ranked.append((overlap, _timestamp_key(entry.timestamp), entry.event_id, entry))
        ranked.sort(reverse=True)
        return [entry for _, _, _, entry in ranked[:limit]]

    def _observation_memory_role(self, entry: ObservationEntry) -> MemoryRole:
        metadata = entry.metadata if isinstance(entry.metadata, dict) else {}
        if entry.predicate == "state_deletion":
            return "state_deletion"
        write_operation = str(metadata.get("write_operation") or "").strip().lower()
        if write_operation == "delete" or metadata.get("deleted_at"):
            return "state_deletion"
        if entry.predicate == "raw_turn":
            return "episodic"
        explicit_role = str(metadata.get("memory_role") or "").strip()
        if explicit_role in {"current_state", "state_deletion", "structured_evidence", "episodic", "belief", "aggregate", "ambiguity"}:
            return explicit_role  # type: ignore[return-value]
        return "structured_evidence"

    def _unsupported_operation_reason(self, operation: str, *, write_kind: str) -> str | None:
        supported_by_kind = {
            "observation": {"auto", "create", "update", "delete"},
            "event": {"auto", "event"},
        }
        if operation in supported_by_kind.get(write_kind, set()):
            return None
        return "unsupported_operation"

    def _explicit_memory_entries(
        self,
        request: MemoryWriteRequest,
        *,
        write_kind: str,
        write_operation: str,
        session_id: str,
        turn_id: str,
    ) -> JsonDict:
        subject = self._normalize_subject(request.subject or "")
        predicate = self._normalize_predicate(request.predicate or "")
        value = _normalize_scalar(request.value)
        if not subject:
            return {"unsupported_reason": "subject_required", "observations": [], "events": []}
        if not predicate:
            return {"unsupported_reason": "predicate_required", "observations": [], "events": []}
        if write_kind == "event":
            if not value:
                return {"unsupported_reason": "value_required", "observations": [], "events": []}
            return {
                "unsupported_reason": None,
                "observations": [],
                "events": [
                    EventCalendarEntry(
                        event_id=f"{turn_id}:event:1",
                        subject=subject,
                        predicate=predicate,
                        text=self._manual_turn_text(
                            write_operation=write_operation,
                            write_kind=write_kind,
                            subject=subject,
                            predicate=predicate,
                            value=value,
                        ),
                        session_id=session_id,
                        turn_ids=[turn_id],
                        timestamp=request.timestamp,
                        metadata={
                            **dict(request.metadata),
                            **self._request_contract_metadata(request, write_operation=write_operation),
                            "value": value,
                            "write_operation": write_operation,
                        },
                    )
                ],
            }
        if write_operation in {"create", "update"} and not value:
            return {"unsupported_reason": "value_required", "observations": [], "events": []}
        if write_operation == "delete":
            return {
                "unsupported_reason": None,
                "observations": [
                    ObservationEntry(
                        observation_id=f"{turn_id}:observation:1",
                        subject=subject,
                        predicate="state_deletion",
                        text=self._manual_turn_text(
                            write_operation=write_operation,
                            write_kind=write_kind,
                            subject=subject,
                            predicate=predicate,
                            value=value,
                        ),
                        session_id=session_id,
                        turn_ids=[turn_id],
                        timestamp=request.timestamp,
                        metadata={
                            **dict(request.metadata),
                            **self._request_contract_metadata(request, write_operation=write_operation),
                            "target_predicate": predicate,
                            "deleted_value": value,
                            "write_operation": write_operation,
                        },
                    )
                ],
                "events": [],
            }
        metadata = dict(request.metadata)
        entity_key = _normalize_scalar(metadata.get("entity_key")) or value.lower()
        return {
            "unsupported_reason": None,
            "observations": [
                ObservationEntry(
                    observation_id=f"{turn_id}:observation:1",
                    subject=subject,
                    predicate=predicate,
                    text=self._manual_turn_text(
                        write_operation=write_operation,
                        write_kind=write_kind,
                        subject=subject,
                        predicate=predicate,
                        value=value,
                    ),
                    session_id=session_id,
                    turn_ids=[turn_id],
                    timestamp=request.timestamp,
                    metadata={
                        **metadata,
                        **self._request_contract_metadata(request, write_operation=write_operation),
                        "value": value,
                        "entity_key": entity_key,
                        "write_operation": write_operation,
                    },
                )
            ],
            "events": [],
        }

    def _manual_turn_text(
        self,
        *,
        write_operation: str,
        write_kind: str,
        subject: str | None,
        predicate: str | None,
        value: str | None,
    ) -> str:
        subject_text = _normalize_scalar(subject) or "user"
        predicate_text = _normalize_scalar(predicate) or "memory"
        value_text = _normalize_scalar(value)
        if write_kind == "event":
            return f"event {predicate_text} for {subject_text}: {value_text}"
        if write_operation == "delete":
            return f"delete {predicate_text} for {subject_text}: {value_text}".strip(" :")
        return f"{subject_text} {predicate_text} {value_text}".strip()

    def _request_contract_metadata(
        self,
        request: MemoryWriteRequest,
        *,
        write_operation: str,
    ) -> JsonDict:
        metadata: JsonDict = {}
        if request.retention_class is not None:
            metadata["retention_class"] = request.retention_class
        if request.document_time:
            metadata["document_time"] = request.document_time
        if request.event_time:
            metadata["event_time"] = request.event_time
        if request.valid_from:
            metadata["valid_from"] = request.valid_from
        if request.valid_to:
            metadata["valid_to"] = request.valid_to
        if request.supersedes:
            metadata["supersedes"] = request.supersedes
        if request.conflicts_with:
            metadata["conflicts_with"] = [str(item).strip() for item in request.conflicts_with if str(item).strip()]
        if request.deleted_at:
            metadata["deleted_at"] = request.deleted_at
        elif write_operation == "delete" and request.timestamp:
            metadata["deleted_at"] = request.timestamp
        if request.timestamp:
            metadata.setdefault("created_at", request.timestamp)
            metadata.setdefault("document_time", request.document_time or request.timestamp)
            if write_operation in {"create", "update", "event"}:
                metadata.setdefault("valid_from", request.valid_from or request.timestamp)
        return metadata

    def _build_manual_current_state_snapshot(
        self,
        observations: list[ObservationEntry],
    ) -> list[ObservationEntry]:
        if not observations:
            return []
        current_entries = [
            entry for entry in build_current_state_view(observations) if entry.predicate != "raw_turn"
        ]
        deletion_targets = {
            (entry.subject, state_deletion_target(entry))
            for entry in observations
            if entry.predicate == "state_deletion" and state_deletion_target(entry)
        }
        active_deletions: list[ObservationEntry] = []
        for subject, predicate in sorted(deletion_targets):
            if not has_active_state_deletion(observations, subject=subject, predicate=predicate):
                continue
            deletion_entries = self._deletion_entries(observations, subject=subject, predicate=predicate)
            if deletion_entries:
                active_deletions.append(deletion_entries[-1])
        return sorted(
            [*current_entries, *active_deletions],
            key=lambda entry: (_timestamp_key(entry.timestamp), entry.observation_id),
        )

    def _write_has_supported_memory(
        self,
        observations: list[ObservationEntry],
        events: list[EventCalendarEntry],
    ) -> bool:
        if events:
            return True
        return any(self._observation_memory_role(entry) != "episodic" for entry in observations)

    def _normalize_subject(self, subject: str) -> str:
        return _normalize_human_subject(subject)

    def _normalize_predicate(self, predicate: str) -> str:
        return str(predicate or "").strip().lower()

    def _normalize_optional_subject(self, subject: str | None) -> str | None:
        cleaned = self._normalize_subject(subject or "")
        return cleaned or None

    def _normalize_optional_predicate(self, predicate: str | None) -> str | None:
        cleaned = self._normalize_predicate(predicate or "")
        return cleaned or None

    def _invalid_subject_predicate_reason(self, subject: str, predicate: str) -> str | None:
        if not self._normalize_subject(subject):
            return "subject_required"
        if not self._normalize_predicate(predicate):
            return "predicate_required"
        return None

    def _invalid_lookup_result(
        self,
        *,
        operation: str,
        subject: str,
        predicate: str,
        reason: str,
        extra_trace: JsonDict | None = None,
    ) -> MemoryLookupResult:
        trace: JsonDict = {
            "operation": operation,
            "status": "invalid_request",
            "reason": reason,
            "subject": subject,
            "predicate": predicate,
        }
        if extra_trace:
            trace.update(extra_trace)
        return MemoryLookupResult(
            found=False,
            value=None,
            text=None,
            memory_role="unknown",
            provenance=[],
            trace=self._with_role_trace(trace, memory_role="unknown", provenance_roles=[], items=[]),
        )

    def _lookup_trace(
        self,
        *,
        operation: str,
        subject: str,
        predicate: str,
        observation_count: int,
        memory_role: MemoryRole,
        provenance_roles: list[MemoryRole],
        provenance_items: list[RetrievedMemoryRecord] | None = None,
        extra_trace: JsonDict | None = None,
    ) -> JsonDict:
        trace: JsonDict = {
            "operation": operation,
            "subject": subject,
            "predicate": predicate,
            "observation_count": observation_count,
        }
        if extra_trace:
            trace.update(extra_trace)
        return self._with_role_trace(
            trace,
            memory_role=memory_role,
            provenance_roles=provenance_roles,
            items=provenance_items or [],
        )

    def _retrieval_trace(
        self,
        *,
        operation: str,
        items: list[RetrievedMemoryRecord],
        query: str | None,
        subject: str | None,
        predicate: str | None,
        limit: int,
        query_intent: str | None = None,
    ) -> JsonDict:
        trace: JsonDict = {
            "operation": operation,
            "query": query,
            "subject": subject,
            "predicate": predicate,
            "limit": limit,
        }
        if query_intent is not None:
            trace["query_intent"] = query_intent
        trace["memory_roles"] = self._unique_memory_roles(items)
        trace["memory_role_counts"] = self._memory_role_counts(items)
        trace["primary_memory_role"] = self._primary_memory_role(items)
        trace["canonical_memory_roles"] = self._canonical_memory_roles(items)
        trace["retention_classes"] = self._unique_retention_classes(items)
        trace["primary_retention_class"] = self._primary_retention_class(items)
        trace["lifecycle_fields_present"] = self._lifecycle_fields_present_for_items(items)
        return trace

    def _explanation_trace(
        self,
        *,
        question: str,
        subject: str,
        predicate: str,
        as_of: str | None,
        state_result: MemoryLookupResult,
        evidence: list[RetrievedMemoryRecord],
        events: list[RetrievedMemoryRecord],
    ) -> JsonDict:
        memory_roles = self._unique_memory_roles([*state_result.provenance, *evidence, *events])
        if state_result.memory_role not in memory_roles:
            memory_roles = [state_result.memory_role, *memory_roles]
        return {
            "operation": "explain_answer",
            "question": question,
            "subject": subject,
            "predicate": predicate,
            "as_of": as_of,
            "memory_role": state_result.memory_role,
            "primary_memory_role": state_result.memory_role,
            "memory_roles": memory_roles,
            "state_memory_role": state_result.memory_role,
            "evidence_memory_roles": self._unique_memory_roles(evidence),
            "event_memory_roles": self._unique_memory_roles(events),
            "canonical_memory_roles": [canonical_memory_role(role) for role in memory_roles],
            "retention_classes": self._unique_retention_classes([*state_result.provenance, *evidence, *events]),
            "primary_retention_class": self._primary_retention_class([*state_result.provenance, *evidence, *events]),
            "lifecycle_fields_present": self._lifecycle_fields_present_for_items([*state_result.provenance, *evidence, *events]),
        }

    def _with_role_trace(
        self,
        trace: JsonDict,
        *,
        memory_role: MemoryRole,
        provenance_roles: list[MemoryRole],
        items: list[RetrievedMemoryRecord],
    ) -> JsonDict:
        unique_provenance_roles = list(dict.fromkeys(provenance_roles))
        trace["memory_role"] = memory_role
        trace["primary_memory_role"] = memory_role
        trace["memory_roles"] = [memory_role] if memory_role != "unknown" else []
        trace["provenance_roles"] = unique_provenance_roles
        trace["canonical_memory_roles"] = [canonical_memory_role(role) for role in trace["memory_roles"]]
        trace["retention_class"] = self._primary_retention_class(items)
        trace["retention_classes"] = self._unique_retention_classes(items)
        trace["lifecycle_fields_present"] = self._lifecycle_fields_present_for_items(items)
        return trace

    def _memory_role_counts(self, items: list[RetrievedMemoryRecord]) -> JsonDict:
        counts = Counter(item.memory_role for item in items if str(item.memory_role or "").strip())
        return {role: counts[role] for role in sorted(counts)}

    def _unique_memory_roles(self, items: list[RetrievedMemoryRecord]) -> list[str]:
        return list(dict.fromkeys(item.memory_role for item in items if str(item.memory_role or "").strip()))

    def _canonical_memory_roles(self, items: list[RetrievedMemoryRecord]) -> list[str]:
        return list(dict.fromkeys(canonical_memory_role(item.memory_role) for item in items if str(item.memory_role or "").strip()))

    def _primary_memory_role(self, items: list[RetrievedMemoryRecord]) -> str:
        return items[0].memory_role if items else "unknown"

    def _unique_retention_classes(self, items: list[RetrievedMemoryRecord]) -> list[str]:
        return list(
            dict.fromkeys(
                item.retention_class for item in items if str(item.retention_class or "").strip()
            )
        )

    def _primary_retention_class(self, items: list[RetrievedMemoryRecord]) -> str | None:
        for item in items:
            if str(item.retention_class or "").strip():
                return item.retention_class
        return None

    def _lifecycle_fields_present_for_items(self, items: list[RetrievedMemoryRecord]) -> list[str]:
        present: list[str] = []
        for field_name in SDK_LIFECYCLE_FIELDS:
            if any(self._lifecycle_has_value(item.lifecycle.get(field_name)) for item in items):
                present.append(field_name)
        return present

    def _lifecycle_has_value(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, list):
            return any(self._lifecycle_has_value(item) for item in value)
        return str(value).strip() != ""

    def _record_retention_class(
        self,
        *,
        memory_role: MemoryRole,
        metadata: JsonDict,
    ) -> RetentionClass | None:
        return default_retention_class(memory_role, metadata=metadata)

    def _record_lifecycle(
        self,
        *,
        memory_role: MemoryRole,
        timestamp: str | None,
        metadata: JsonDict,
    ) -> JsonDict:
        created_at = _normalize_scalar(metadata.get("created_at")) or _normalize_scalar(timestamp)
        document_time = _normalize_scalar(metadata.get("document_time")) or created_at
        lifecycle: JsonDict = {}
        if created_at:
            lifecycle["created_at"] = created_at
        if document_time:
            lifecycle["document_time"] = document_time
        event_time = _normalize_scalar(metadata.get("event_time"))
        if event_time:
            lifecycle["event_time"] = event_time
        valid_from = _normalize_scalar(metadata.get("valid_from"))
        if not valid_from and memory_role in {"current_state", "structured_evidence", "event"}:
            valid_from = created_at
        if valid_from:
            lifecycle["valid_from"] = valid_from
        valid_to = _normalize_scalar(metadata.get("valid_to"))
        if valid_to:
            lifecycle["valid_to"] = valid_to
        supersedes = _normalize_scalar(metadata.get("supersedes"))
        if supersedes:
            lifecycle["supersedes"] = supersedes
        conflicts_with = metadata.get("conflicts_with")
        if isinstance(conflicts_with, list):
            normalized_conflicts = [str(item).strip() for item in conflicts_with if str(item).strip()]
            if normalized_conflicts:
                lifecycle["conflicts_with"] = normalized_conflicts
        deleted_at = _normalize_scalar(metadata.get("deleted_at"))
        if not deleted_at and memory_role == "state_deletion":
            deleted_at = created_at
        if deleted_at:
            lifecycle["deleted_at"] = deleted_at
        return lifecycle

    def _observation_record(self, entry: ObservationEntry, *, memory_role: MemoryRole) -> RetrievedMemoryRecord:
        metadata = dict(entry.metadata)
        return RetrievedMemoryRecord(
            memory_role=memory_role,
            subject=entry.subject,
            predicate=entry.predicate,
            text=entry.text,
            session_id=entry.session_id,
            turn_ids=entry.turn_ids,
            timestamp=entry.timestamp,
            retention_class=self._record_retention_class(memory_role=memory_role, metadata=metadata),
            lifecycle=self._record_lifecycle(memory_role=memory_role, timestamp=entry.timestamp, metadata=metadata),
            metadata=metadata,
        )

    def _event_record(self, entry: EventCalendarEntry) -> RetrievedMemoryRecord:
        metadata = dict(entry.metadata)
        return RetrievedMemoryRecord(
            memory_role="event",
            subject=entry.subject,
            predicate=entry.predicate,
            text=entry.text,
            session_id=entry.session_id,
            turn_ids=entry.turn_ids,
            timestamp=entry.timestamp,
            retention_class=self._record_retention_class(memory_role="event", metadata=metadata),
            lifecycle=self._record_lifecycle(memory_role="event", timestamp=entry.timestamp, metadata=metadata),
            metadata=metadata,
        )

    def _retrieved_record_dict(self, record: RetrievedMemoryRecord) -> JsonDict:
        return {
            "memory_role": record.memory_role,
            "subject": record.subject,
            "predicate": record.predicate,
            "text": record.text,
            "session_id": record.session_id,
            "turn_ids": list(record.turn_ids),
            "timestamp": record.timestamp,
            "retention_class": record.retention_class,
            "lifecycle": dict(record.lifecycle),
            "metadata": dict(record.metadata),
        }


def build_sdk_contract_summary() -> dict[str, Any]:
    return {
        "runtime_class": "SparkMemorySDK",
        "runtime_memory_architecture": _runtime_memory_architecture(),
        "runtime_memory_provider": _runtime_memory_provider(),
        "memory_roles": sdk_memory_role_contracts(),
        "retention_classes": sdk_retention_contracts(),
        "retention_defaults_by_memory_role": sdk_retention_defaults_by_role(),
        "lifecycle_fields": list(SDK_LIFECYCLE_FIELDS),
        "answer_candidate_types": [
            "generic",
            "exact_numeric",
            "currency",
            "date",
            "location",
            "preference",
            "current_state",
            "event_history",
            "abstain",
        ],
        "write_methods": ["write_observation", "write_event"],
        "write_operations": {
            "write_observation": ["auto", "create", "update", "delete"],
            "write_event": ["auto", "event"],
        },
        "maintenance_methods": ["reconsolidate_manual_memory"],
        "export_methods": ["export_knowledge_base_snapshot"],
        "read_methods": [
            "get_current_state",
            "get_historical_state",
            "retrieve_evidence",
            "retrieve_events",
            "explain_answer",
        ],
        "request_contracts": [
            "MemoryWriteRequest",
            "CurrentStateRequest",
            "HistoricalStateRequest",
            "EvidenceRetrievalRequest",
            "EventRetrievalRequest",
            "AnswerExplanationRequest",
        ],
        "response_contracts": [
            "MemoryWriteResult",
            "MemoryLookupResult",
            "MemoryRetrievalResult",
            "AnswerExplanationResult",
            "MemoryMaintenanceResult",
            "RetrievedMemoryRecord",
        ],
        "trace_contracts": {
            "write_memory": [
                "memory_roles",
                "memory_role_counts",
                "primary_memory_role",
                "canonical_memory_roles",
                "retention_classes",
                "primary_retention_class",
                "lifecycle_fields_present",
            ],
            "read_memory": [
                "memory_role",
                "memory_roles",
                "primary_memory_role",
                "provenance_roles",
                "canonical_memory_roles",
                "retention_class",
                "retention_classes",
                "lifecycle_fields_present",
            ],
            "retrieve_memory": [
                "memory_roles",
                "memory_role_counts",
                "primary_memory_role",
                "canonical_memory_roles",
                "retention_classes",
                "primary_retention_class",
                "lifecycle_fields_present",
            ],
            "explain_answer": [
                "memory_role",
                "memory_roles",
                "state_memory_role",
                "evidence_memory_roles",
                "event_memory_roles",
                "canonical_memory_roles",
                "retention_classes",
                "primary_retention_class",
                "lifecycle_fields_present",
            ],
        },
    }


def build_sdk_maintenance_replay_contract_summary() -> dict[str, Any]:
    return {
        "single_file_shape": {
            "root_type": "object",
            "required_fields": ["writes"],
            "optional_fields": ["checks"],
            "write_fields": [
                "write_kind",
                "text",
                "speaker",
                "timestamp",
                "session_id",
                "turn_id",
                "operation",
                "subject",
                "predicate",
                "value",
                "metadata",
            ],
            "check_groups": {
                "current_state": [
                    "subject",
                    "predicate",
                ],
                "historical_state": [
                    "subject",
                    "predicate",
                    "as_of",
                ],
            },
        },
        "supported_write_kinds": [
            "observation",
            "event",
        ],
        "supported_operations": {
            "observation": ["auto", "create", "update", "delete"],
            "event": ["auto", "event"],
        },
        "maintenance_method": "reconsolidate_manual_memory",
        "output_fields": [
            "write_results",
            "maintenance",
            "before",
            "after",
        ],
        "notes": [
            "The replay file models explicit SDK writes rather than Builder conversation turns.",
            "Checks are optional and are evaluated before and after maintenance to verify reconsolidation behavior.",
        ],
    }
