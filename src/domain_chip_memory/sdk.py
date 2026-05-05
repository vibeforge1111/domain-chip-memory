from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import re
from typing import Any

from .contracts import JsonDict, MemoryRole, NormalizedBenchmarkSample, NormalizedQuestion, NormalizedSession, NormalizedTurn, RetentionClass
from .memory_extraction import EventCalendarEntry, ObservationEntry
from .memory_conversational_index import build_conversational_index
from .memory_observation_runtime import build_event_calendar, build_observation_log
from .memory_roles import canonical_memory_role, sdk_memory_role_contracts
from .memory_retention import default_retention_class, sdk_retention_contracts, sdk_retention_defaults_by_role
from .memory_updates import (
    active_state_entity_key,
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


DEFAULT_RUNTIME_MEMORY_ARCHITECTURE = "summary_synthesis_memory"
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
DASHBOARD_MOVEMENT_STATES: tuple[str, ...] = (
    "captured",
    "blocked",
    "promoted",
    "saved",
    "decayed",
    "summarized",
    "retrieved",
    "selected",
    "dropped",
)


def _runtime_memory_architecture(value: str | None = None) -> str:
    return _normalize_scalar(value) or DEFAULT_RUNTIME_MEMORY_ARCHITECTURE


def _runtime_memory_provider(value: str | None = None) -> str:
    return _normalize_scalar(value) or DEFAULT_RUNTIME_MEMORY_PROVIDER


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
    entity_key: str | None = None


@dataclass(frozen=True)
class HistoricalStateRequest:
    subject: str
    predicate: str
    as_of: str
    entity_key: str | None = None


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
class TaskRecoveryRequest:
    query: str | None = None
    subject: str | None = None
    limit: int = 5


@dataclass(frozen=True)
class EpisodicRecallRequest:
    query: str | None = None
    subject: str | None = None
    since: str | None = None
    until: str | None = None
    limit: int = 5


@dataclass(frozen=True)
class RetrievedMemoryRecord:
    memory_role: MemoryRole
    subject: str
    predicate: str
    text: str
    session_id: str
    turn_ids: list[str]
    timestamp: str | None
    observation_id: str | None = None
    event_id: str | None = None
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
class TaskRecoveryResult:
    status: str
    active_goal: RetrievedMemoryRecord | None
    completed_steps: list[RetrievedMemoryRecord]
    blockers: list[RetrievedMemoryRecord]
    next_actions: list[RetrievedMemoryRecord]
    episodic_context: list[RetrievedMemoryRecord]
    trace: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class EpisodicRecallResult:
    status: str
    current_state: list[RetrievedMemoryRecord]
    session_summaries: list[RetrievedMemoryRecord]
    matching_turns: list[RetrievedMemoryRecord]
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
    active_state_still_current_count: int = 0
    active_state_stale_preserved_count: int = 0
    active_state_superseded_count: int = 0
    active_state_archived_count: int = 0
    active_state_resurrected_count: int = 0
    audit_samples: JsonDict = field(default_factory=dict)
    trace: JsonDict = field(default_factory=dict)


class SparkMemorySDK:
    def __init__(
        self,
        *,
        runtime_memory_architecture: str | None = None,
        runtime_memory_provider: str | None = None,
    ) -> None:
        self.runtime_memory_architecture = _runtime_memory_architecture(runtime_memory_architecture)
        self.runtime_memory_provider = _runtime_memory_provider(runtime_memory_provider)
        self._sessions: list[NormalizedSession] = []
        self._session_counter = 0
        self._manual_observations: list[ObservationEntry] = []
        self._manual_events: list[EventCalendarEntry] = []
        self._manual_current_state_snapshot: list[ObservationEntry] = []
        self._dashboard_movement_events: list[JsonDict] = []
        self._dashboard_movement_counter = 0

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
        entity_key = _normalize_scalar(request.entity_key) or None
        reflected = build_current_state_view(observations)
        matches = [
            entry
            for entry in reflected
            if entry.subject == subject and entry.predicate == predicate
            and self._entity_key_matches(entry, predicate=predicate, entity_key=entity_key)
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
                    extra_trace={"entity_key": entity_key} if entity_key else None,
                ),
            )
        if self._has_active_state_deletion(
            observations,
            subject=subject,
            predicate=predicate,
            entity_key=entity_key,
        ):
            deletion_entries = self._deletion_entries(
                observations,
                subject=subject,
                predicate=predicate,
                entity_key=entity_key,
            )
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
                    extra_trace={"entity_key": entity_key} if entity_key else None,
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
                    extra_trace={"entity_key": entity_key} if entity_key else None,
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
        entity_key = _normalize_scalar(request.entity_key) or None
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
            and self._entity_key_matches(entry, predicate=predicate, entity_key=entity_key)
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
                    extra_trace={
                        "as_of": request.as_of,
                        **({"entity_key": entity_key} if entity_key else {}),
                    },
                ),
            )
        if self._has_active_state_deletion(
            observations,
            subject=subject,
            predicate=predicate,
            entity_key=entity_key,
        ):
            deletion_entries = self._deletion_entries(
                observations,
                subject=subject,
                predicate=predicate,
                entity_key=entity_key,
            )
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
                    extra_trace={
                        "as_of": request.as_of,
                        **({"entity_key": entity_key} if entity_key else {}),
                    },
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
                    extra_trace={
                        "as_of": request.as_of,
                        **({"entity_key": entity_key} if entity_key else {}),
                    },
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
        for item in items:
            self._append_record_dashboard_movement(
                movement_state="retrieved",
                record=item,
                trace={
                    "operation": "retrieve_evidence",
                    "query": request.query,
                    "limit": request.limit,
                    "query_intent": query_intent,
                },
            )
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
        for item in items:
            self._append_record_dashboard_movement(
                movement_state="retrieved",
                record=item,
                trace={
                    "operation": "retrieve_events",
                    "query": request.query,
                    "limit": request.limit,
                },
            )
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

    def recover_task_context(self, request: TaskRecoveryRequest) -> TaskRecoveryResult:
        if request.limit < 1:
            return TaskRecoveryResult(
                status="invalid_request",
                active_goal=None,
                completed_steps=[],
                blockers=[],
                next_actions=[],
                episodic_context=[],
                trace={
                    "operation": "recover_task_context",
                    "status": "invalid_request",
                    "reason": "limit_must_be_positive",
                    "limit": request.limit,
                    "promotes_memory": False,
                },
            )

        subject = self._normalize_optional_subject(request.subject)
        current_state_records = [
            self._observation_record(entry, memory_role="current_state")
            for entry in build_current_state_view(self._current_state_observations())
            if not subject or entry.subject == subject
        ]
        observation_records = [
            self._observation_record(entry, memory_role=self._observation_memory_role(entry))
            for entry in self._observations()
            if not subject or entry.subject == subject
        ]
        event_records = [
            self._event_record(entry)
            for entry in self._events()
            if not subject or entry.subject == subject
        ]
        candidates = [*current_state_records, *observation_records, *event_records]

        active_goal = self._select_task_recovery_active_goal(
            current_state_records,
            query=request.query,
        )
        completed_steps = self._task_recovery_bucket(
            candidates,
            bucket="completed_steps",
            query=request.query,
            limit=request.limit,
        )
        blockers = self._task_recovery_bucket(
            candidates,
            bucket="blockers",
            query=request.query,
            limit=request.limit,
        )
        next_actions = self._task_recovery_bucket(
            candidates,
            bucket="next_actions",
            query=request.query,
            limit=request.limit,
        )
        episodic_context = self._task_recovery_bucket(
            observation_records,
            bucket="episodic_context",
            query=request.query,
            limit=request.limit,
        )

        selected_records = [
            *([active_goal] if active_goal else []),
            *completed_steps,
            *blockers,
            *next_actions,
            *episodic_context,
        ]
        selected_by_id = dict.fromkeys(self._record_movement_id(record) for record in selected_records)
        for record in selected_records:
            self._append_record_dashboard_movement(
                movement_state="retrieved",
                record=record,
                trace={
                    "operation": "recover_task_context",
                    "query": request.query,
                    "limit": request.limit,
                    "selection_bucket": self._task_recovery_bucket_name(record, active_goal=active_goal),
                },
            )
        for record in selected_records:
            self._append_record_dashboard_movement(
                movement_state="selected",
                record=record,
                trace={
                    "operation": "recover_task_context",
                    "query": request.query,
                    "selection_bucket": self._task_recovery_bucket_name(record, active_goal=active_goal),
                },
            )

        return TaskRecoveryResult(
            status="ok",
            active_goal=active_goal,
            completed_steps=completed_steps,
            blockers=blockers,
            next_actions=next_actions,
            episodic_context=episodic_context,
            trace=self._task_recovery_trace(
                request=request,
                active_goal=active_goal,
                completed_steps=completed_steps,
                blockers=blockers,
                next_actions=next_actions,
                episodic_context=episodic_context,
                source_counts={
                    "current_state": len(current_state_records),
                    "observations": len(observation_records),
                    "events": len(event_records),
                },
                unique_selected_count=len(selected_by_id),
            ),
        )

    def recall_episodic_context(self, request: EpisodicRecallRequest) -> EpisodicRecallResult:
        if request.limit < 1:
            return EpisodicRecallResult(
                status="invalid_request",
                current_state=[],
                session_summaries=[],
                matching_turns=[],
                evidence=[],
                events=[],
                trace={
                    "operation": "recall_episodic_context",
                    "status": "invalid_request",
                    "reason": "limit_must_be_positive",
                    "limit": request.limit,
                    "promotes_memory": False,
                },
            )

        subject = self._normalize_optional_subject(request.subject)
        sessions = self._episodic_sessions_in_window(subject=subject, since=request.since, until=request.until)
        current_state = [
            self._observation_record(entry, memory_role="current_state")
            for entry in self._rank_observations(
                build_current_state_view(self._current_state_observations()),
                query=request.query,
                subject=subject,
                predicate=None,
                limit=request.limit,
            )
        ]
        session_summaries = self._rank_episodic_records(
            [self._session_summary_record(session) for session in sessions if session.turns],
            query=request.query,
            limit=request.limit,
        )
        matching_turns = self._rank_episodic_records(
            [
                self._session_turn_record(session, turn)
                for session in sessions
                for turn in session.turns
                if str(turn.text or "").strip()
            ],
            query=request.query,
            limit=request.limit,
        )
        evidence = [
            self._observation_record(entry, memory_role=self._observation_memory_role(entry))
            for entry in self._rank_observations(
                self._observations(),
                query=request.query,
                subject=subject,
                predicate=None,
                limit=request.limit,
            )
        ]
        events = [
            self._event_record(entry)
            for entry in self._rank_events(
                self._events(),
                query=request.query,
                subject=subject,
                predicate=None,
                limit=request.limit,
            )
        ]

        selected_records = [*current_state, *session_summaries, *matching_turns, *evidence, *events]
        selected_by_id = dict.fromkeys(self._record_movement_id(record) for record in selected_records)
        for record in selected_records:
            self._append_record_dashboard_movement(
                movement_state="retrieved",
                record=record,
                trace={
                    "operation": "recall_episodic_context",
                    "query": request.query,
                    "limit": request.limit,
                    "selection_bucket": self._episodic_recall_bucket_name(record),
                },
            )
            self._append_record_dashboard_movement(
                movement_state="selected",
                record=record,
                trace={
                    "operation": "recall_episodic_context",
                    "query": request.query,
                    "selection_bucket": self._episodic_recall_bucket_name(record),
                },
            )

        for record in session_summaries:
            self._append_record_dashboard_movement(
                movement_state="summarized",
                record=record,
                trace={
                    "operation": "recall_episodic_context",
                    "query": request.query,
                    "selection_bucket": "session_summaries",
                },
            )

        return EpisodicRecallResult(
            status="ok",
            current_state=current_state,
            session_summaries=session_summaries,
            matching_turns=matching_turns,
            evidence=evidence,
            events=events,
            trace=self._episodic_recall_trace(
                request=request,
                current_state=current_state,
                session_summaries=session_summaries,
                matching_turns=matching_turns,
                evidence=evidence,
                events=events,
                source_counts={
                    "sessions": len(sessions),
                    "current_state": len(current_state),
                    "observations": len(self._observations()),
                    "events": len(self._events()),
                },
                unique_selected_count=len(selected_by_id),
            ),
        )

    def reconsolidate_manual_memory(self, *, now: str | None = None) -> MemoryMaintenanceResult:
        raw_snapshot = self._build_manual_current_state_snapshot(self._manual_observations)
        maintained_at = now or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        self._manual_observations = self._annotate_active_state_maintenance(
            self._manual_observations,
            snapshot=raw_snapshot,
            maintained_at=maintained_at,
        )
        snapshot = self._build_manual_current_state_snapshot(self._manual_observations)
        self._manual_current_state_snapshot = snapshot
        active_deletions = sum(1 for entry in snapshot if entry.predicate == "state_deletion")
        maintenance_counts = Counter(
            str(entry.metadata.get("active_state_maintenance_action") or "")
            for entry in self._manual_observations
            if entry.metadata.get("active_state_maintenance_action")
        )
        audit_samples = self._active_state_maintenance_audit_samples(self._manual_observations)
        for entry in self._manual_observations:
            action = str(entry.metadata.get("active_state_maintenance_action") or "").strip()
            if action in {"archived", "stale_preserved", "superseded"}:
                self._append_record_dashboard_movement(
                    movement_state="decayed",
                    record=self._observation_record(entry, memory_role=self._observation_memory_role(entry)),
                    trace={
                        "operation": "reconsolidate_manual_memory",
                        "maintenance_action": action,
                        "maintenance_reason": _normalize_scalar(entry.metadata.get("active_state_maintenance_reason")),
                    },
                )
        return MemoryMaintenanceResult(
            manual_observations_before=len(self._manual_observations),
            manual_observations_after=len(snapshot),
            current_state_snapshot_count=len(snapshot),
            active_deletion_count=active_deletions,
            manual_events_count=len(self._manual_events),
            active_state_still_current_count=maintenance_counts.get("still_current", 0),
            active_state_stale_preserved_count=maintenance_counts.get("stale_preserved", 0),
            active_state_superseded_count=maintenance_counts.get("superseded", 0),
            active_state_archived_count=maintenance_counts.get("archived", 0),
            active_state_resurrected_count=maintenance_counts.get("resurrected", 0),
            audit_samples=audit_samples,
            trace={
                "operation": "reconsolidate_manual_memory",
                "status": "ok",
                "active_state_maintenance": {
                    "still_current": maintenance_counts.get("still_current", 0),
                    "stale_preserved": maintenance_counts.get("stale_preserved", 0),
                    "superseded": maintenance_counts.get("superseded", 0),
                    "archived": maintenance_counts.get("archived", 0),
                    "resurrected": maintenance_counts.get("resurrected", 0),
                },
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
        dashboard_movement = self._build_dashboard_movement_export(
            current_state_records=current_state_records,
            observation_records=observation_records,
            event_records=event_records,
        )
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
            "dashboard_movement": dashboard_movement,
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
            self._append_request_dashboard_movement(
                movement_state="blocked",
                request=request,
                write_kind=write_kind,
                write_operation=operation,
                reason="empty_text",
            )
            self._append_request_dashboard_movement(
                movement_state="dropped",
                request=request,
                write_kind=write_kind,
                write_operation=operation,
                reason="empty_text",
            )
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
            self._append_request_dashboard_movement(
                movement_state="blocked",
                request=request,
                write_kind=write_kind,
                write_operation=operation,
                reason=invalid_operation_reason,
            )
            self._append_request_dashboard_movement(
                movement_state="dropped",
                request=request,
                write_kind=write_kind,
                write_operation=operation,
                reason=invalid_operation_reason,
            )
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
        normalized_turn_subject = self._normalize_optional_subject(request.subject)
        if normalized_turn_subject:
            turn_metadata.setdefault("subject", normalized_turn_subject)
        if manual_write:
            explicit_memory = self._explicit_memory_entries(
                request,
                write_kind=write_kind,
                write_operation=operation,
                session_id=session_id,
                turn_id=turn_id,
            )
            if explicit_memory["unsupported_reason"] is not None:
                self._append_request_dashboard_movement(
                    movement_state="blocked",
                    request=request,
                    write_kind=write_kind,
                    write_operation=operation,
                    reason=str(explicit_memory["unsupported_reason"]),
                )
                self._append_request_dashboard_movement(
                    movement_state="dropped",
                    request=request,
                    write_kind=write_kind,
                    write_operation=operation,
                    reason=str(explicit_memory["unsupported_reason"]),
                )
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
            observations = self._merge_observations(
                observations,
                self._build_conversational_bridge_observations(
                    session_id=session_id,
                    turn=turn,
                ),
            )

        explicit_episodic_only_write = (
            manual_write
            and bool(observations)
            and not events
            and all(self._observation_memory_role(entry) == "episodic" for entry in observations)
        )
        accepted = self._write_has_supported_memory(observations, events) or explicit_episodic_only_write
        observation_records = [
            self._observation_record(entry, memory_role=self._observation_memory_role(entry))
            for entry in observations
        ]
        event_records = [self._event_record(entry) for entry in events]
        purge_result: JsonDict = {}
        if accepted:
            if manual_write and operation == "purge":
                subject = self._normalize_subject(request.subject or "")
                predicate = self._normalize_predicate(request.predicate or "")
                value = _normalize_scalar(request.value)
                purge_result = self._purge_memory_records(subject=subject, predicate=predicate, value=value)
            self._upsert_session(session_id, turn, request.timestamp)
            if manual_write:
                self._manual_observations.extend(observations)
                self._manual_events.extend(events)
                self._manual_current_state_snapshot = []
            for record in [*observation_records, *event_records]:
                self._append_record_dashboard_movement(
                    movement_state="captured",
                    record=record,
                    trace={
                        "operation": "write_memory",
                        "write_kind": write_kind,
                        "write_operation": operation,
                    },
                )
                self._append_record_dashboard_movement(
                    movement_state="saved",
                    record=record,
                    trace={
                        "operation": "write_memory",
                        "write_kind": write_kind,
                        "write_operation": operation,
                    },
                )
                if record.memory_role in {"current_state", "state_deletion"} or record.retention_class == "active_state":
                    self._append_record_dashboard_movement(
                        movement_state="promoted",
                        record=record,
                        trace={
                            "operation": "write_memory",
                            "write_kind": write_kind,
                            "write_operation": operation,
                            "promotion_target": "current_state",
                        },
                    )
                if operation == "purge" and purge_result.get("purge"):
                    self._append_record_dashboard_movement(
                        movement_state="dropped",
                        record=record,
                        trace={
                            "operation": "write_memory",
                            "write_kind": write_kind,
                            "write_operation": operation,
                            "purge": purge_result.get("purge"),
                        },
                    )
        else:
            self._append_request_dashboard_movement(
                movement_state="blocked",
                request=request,
                write_kind=write_kind,
                write_operation=operation,
                reason="no_structured_memory_extracted",
            )
            self._append_request_dashboard_movement(
                movement_state="dropped",
                request=request,
                write_kind=write_kind,
                write_operation=operation,
                reason="no_structured_memory_extracted",
            )
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
                **purge_result,
            },
        )

    def _next_session_id(self) -> str:
        self._session_counter += 1
        return f"sdk-session-{self._session_counter}"

    def _build_conversational_bridge_observations(
        self,
        *,
        session_id: str,
        turn: NormalizedTurn,
    ) -> list[ObservationEntry]:
        bridge_sample = self._sample_for_sessions(
            [
                NormalizedSession(
                    session_id=session_id,
                    turns=[turn],
                    timestamp=turn.timestamp,
                    metadata={},
                )
            ]
        )
        entries = build_conversational_index(bridge_sample)
        return self._conversational_bridge_observations_from_entries(entries, turn_metadata=turn.metadata)

    def _conversational_bridge_observations_from_entries(
        self,
        entries: list[Any],
        *,
        turn_metadata: JsonDict,
    ) -> list[ObservationEntry]:
        observations: list[ObservationEntry] = []
        for index, entry in enumerate(entries, start=1):
            if entry.entry_type != "typed_atom":
                continue
            text = self._conversational_bridge_text(entry.predicate, entry.metadata)
            if not text:
                continue
            value = self._conversational_bridge_value(entry.predicate, entry.metadata)
            timestamp = str(entry.timestamp or "").strip() or None
            observations.append(
                ObservationEntry(
                    observation_id=f"{entry.turn_id}:bridge:{entry.predicate}:{index}",
                    subject=self._normalize_subject(entry.subject),
                    predicate=self._normalize_predicate(entry.predicate),
                    text=text,
                    session_id=entry.session_id,
                    turn_ids=[entry.turn_id],
                    timestamp=timestamp,
                    metadata={
                        **dict(turn_metadata),
                        **dict(entry.metadata),
                        "memory_role": "structured_evidence",
                        "write_operation": "auto",
                        "value": value,
                        "entity_key": f"{entry.predicate}:{value.lower()}",
                        "bridge_priority": 1,
                        "created_at": timestamp,
                        "document_time": timestamp,
                        "valid_from": timestamp,
                        "source_text": entry.text,
                    },
                )
            )
        return observations

    def _runtime_bridge_observations(self) -> list[ObservationEntry]:
        runtime_sample = self._runtime_sample()
        if not runtime_sample.sessions:
            return []
        turn_metadata_by_id: dict[str, JsonDict] = {}
        for session in runtime_sample.sessions:
            for turn in session.turns:
                turn_metadata_by_id[turn.turn_id] = dict(turn.metadata)
        entries = build_conversational_index(runtime_sample)
        observations: list[ObservationEntry] = []
        for entry in entries:
            if entry.entry_type != "typed_atom":
                continue
            observations.extend(
                self._conversational_bridge_observations_from_entries(
                    [entry],
                    turn_metadata=turn_metadata_by_id.get(entry.turn_id, {}),
                )
            )
        return observations

    def _conversational_bridge_text(self, predicate: str, metadata: JsonDict) -> str:
        source_span = _normalize_scalar(metadata.get("source_span"))
        if predicate == "alias_binding":
            alias = _normalize_scalar(metadata.get("alias"))
            return alias or source_span
        if predicate == "negation_record":
            return f"No. {source_span}".strip()
        if predicate == "unknown_record":
            return f"unknown. {source_span}".strip()
        if predicate == "reported_speech":
            return source_span or _normalize_scalar(metadata.get("reported_content"))
        if predicate == "relationship_edge":
            relation_type = _normalize_scalar(metadata.get("relation_type"))
            other_entity = _normalize_scalar(metadata.get("other_entity"))
            return source_span or f"{other_entity} is {relation_type}".strip()
        if predicate in {"support_event", "loss_event", "gift_event", "commitment_event", "visit_event"}:
            return source_span
        return ""

    def _conversational_bridge_value(self, predicate: str, metadata: JsonDict) -> str:
        if predicate == "alias_binding":
            return _normalize_scalar(metadata.get("alias"))
        if predicate == "negation_record":
            return "No"
        if predicate == "unknown_record":
            return "unknown"
        if predicate == "reported_speech":
            return _normalize_scalar(metadata.get("reported_content")) or _normalize_scalar(metadata.get("source_span"))
        if predicate == "relationship_edge":
            return _normalize_scalar(metadata.get("relation_type"))
        if predicate == "loss_event":
            return (
                _normalize_scalar(metadata.get("time_expression_raw"))
                or _normalize_scalar(metadata.get("time_normalized"))
                or _normalize_scalar(metadata.get("source_span"))
            )
        if predicate == "support_event":
            return _normalize_scalar(metadata.get("source_span"))
        if predicate == "gift_event":
            return _normalize_scalar(metadata.get("item_type")) or _normalize_scalar(metadata.get("source_span"))
        if predicate == "commitment_event":
            return _normalize_scalar(metadata.get("source_span"))
        if predicate == "visit_event":
            return (
                _normalize_scalar(metadata.get("time_normalized"))
                or _normalize_scalar(metadata.get("time_expression_raw"))
                or _normalize_scalar(metadata.get("source_span"))
            )
        return _normalize_scalar(metadata.get("source_span"))

    def _merge_observations(
        self,
        observations: list[ObservationEntry],
        bridge_observations: list[ObservationEntry],
    ) -> list[ObservationEntry]:
        merged: list[ObservationEntry] = []
        seen_keys: set[tuple[str, str, str, str | None]] = set()
        for entry in [*observations, *bridge_observations]:
            key = (entry.subject, entry.predicate, entry.text, entry.timestamp)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged.append(entry)
        return merged

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
        return [
            *build_observation_log(self._runtime_sample()),
            *self._runtime_bridge_observations(),
            *manual,
        ]

    def _observations(self) -> list[ObservationEntry]:
        return [
            *build_observation_log(self._runtime_sample()),
            *self._runtime_bridge_observations(),
            *self._manual_observations,
        ]

    def _events(self) -> list[EventCalendarEntry]:
        return [*build_event_calendar(self._runtime_sample()), *self._manual_events]

    def _deletion_entries(
        self,
        observations: list[ObservationEntry],
        *,
        subject: str,
        predicate: str,
        entity_key: str | None = None,
    ) -> list[ObservationEntry]:
        return sorted(
            [
                entry
                for entry in observations
                if entry.subject == subject and state_deletion_target(entry) == predicate
                and self._entity_key_matches(entry, predicate=predicate, entity_key=entity_key)
            ],
            key=lambda entry: (_timestamp_key(entry.timestamp), observation_id_sort_key(entry.observation_id)),
        )

    def _entity_key_matches(
        self,
        entry: ObservationEntry,
        *,
        predicate: str,
        entity_key: str | None,
    ) -> bool:
        if not entity_key:
            return True
        return active_state_entity_key(entry, predicate=predicate) == entity_key

    def _has_active_state_deletion(
        self,
        observations: list[ObservationEntry],
        *,
        subject: str,
        predicate: str,
        entity_key: str | None = None,
    ) -> bool:
        deleted = False
        for observation in sorted(observations, key=entry_sort_key):
            if observation.subject != subject:
                continue
            if state_deletion_target(observation) == predicate and self._entity_key_matches(
                observation,
                predicate=predicate,
                entity_key=entity_key,
            ):
                deleted = True
                continue
            if observation.predicate == predicate and self._entity_key_matches(
                observation,
                predicate=predicate,
                entity_key=entity_key,
            ):
                deleted = False
        return deleted

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
        query_lower = str(query or "").lower()
        ranked: list[tuple[int, str, tuple[Any, ...], str, int, ObservationEntry]] = []
        for index, entry in enumerate(observations):
            if subject and entry.subject != subject:
                continue
            if predicate and entry.predicate != predicate and state_deletion_target(entry) != predicate:
                continue
            overlap = len(query_tokens.intersection(_tokenize(entry.text))) if query_tokens else 0
            if query_tokens and overlap == 0 and not (subject or predicate):
                continue
            bridge_priority = int(entry.metadata.get("bridge_priority", 0)) if isinstance(entry.metadata, dict) else 0
            metadata_boost = 0
            if isinstance(entry.metadata, dict):
                relation_type = str(entry.metadata.get("relation_type", "")).strip().lower()
                if relation_type and relation_type in query_lower:
                    metadata_boost += 4
            ranked.append(
                (
                    overlap + bridge_priority + metadata_boost,
                    _timestamp_key(entry.timestamp),
                    observation_id_sort_key(entry.observation_id),
                    entry.observation_id,
                    index,
                    entry,
                )
            )
        ranked.sort(reverse=True)
        return [entry for _, _, _, _, _, entry in ranked[:limit]]

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
            "observation": {"auto", "create", "update", "delete", "purge"},
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
        if write_operation in {"delete", "purge"}:
            purge_digest = self._purge_digest(subject=subject, predicate=predicate, value=value) if write_operation == "purge" else None
            deleted_value = value if write_operation == "delete" else ""
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
                            "deleted_value": deleted_value,
                            "write_operation": write_operation,
                            **({"cryptographic_purge": True, "purge_digest": purge_digest} if purge_digest else {}),
                        },
                    )
                ],
                "events": [],
            }
        metadata = dict(request.metadata)
        entity_key = _normalize_scalar(metadata.get("entity_key")) or self._default_observation_entity_key(
            predicate=predicate,
            value=value,
            retention_class=request.retention_class,
            memory_role=_normalize_scalar(metadata.get("memory_role")),
        )
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
        if write_operation == "purge":
            return f"purge {predicate_text} for {subject_text}"
        if write_operation == "delete":
            return f"delete {predicate_text} for {subject_text}: {value_text}".strip(" :")
        return f"{subject_text} {predicate_text} {value_text}".strip()

    def _purge_digest(self, *, subject: str, predicate: str, value: str) -> str:
        payload = "\x1f".join(["domain-chip-memory-purge-v1", subject, predicate, value])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _memory_entry_matches_purge(self, entry: ObservationEntry | EventCalendarEntry, *, subject: str, predicate: str, value: str) -> bool:
        entry_predicate = state_deletion_target(entry) if isinstance(entry, ObservationEntry) else entry.predicate
        if entry.subject != subject or entry_predicate != predicate:
            return False
        if not value:
            return True
        metadata_value = _normalize_scalar(entry.metadata.get("value") if isinstance(entry.metadata, dict) else "")
        deleted_value = _normalize_scalar(entry.metadata.get("deleted_value") if isinstance(entry.metadata, dict) else "")
        text = _normalize_scalar(entry.text)
        lowered_value = value.lower()
        return (
            metadata_value.lower() == lowered_value
            or deleted_value.lower() == lowered_value
            or lowered_value in text.lower()
        )

    def _purge_memory_records(self, *, subject: str, predicate: str, value: str) -> JsonDict:
        observations_before = len(self._manual_observations)
        events_before = len(self._manual_events)
        matching_turn_ids: set[str] = set()

        for entry in [*self._observations(), *self._events()]:
            if self._memory_entry_matches_purge(entry, subject=subject, predicate=predicate, value=value):
                matching_turn_ids.update(entry.turn_ids)

        self._manual_observations = [
            entry for entry in self._manual_observations
            if not self._memory_entry_matches_purge(entry, subject=subject, predicate=predicate, value=value)
        ]
        self._manual_events = [
            entry for entry in self._manual_events
            if not self._memory_entry_matches_purge(entry, subject=subject, predicate=predicate, value=value)
        ]
        sessions_removed = 0
        if matching_turn_ids:
            next_sessions: list[NormalizedSession] = []
            for session in self._sessions:
                kept_turns = [turn for turn in session.turns if turn.turn_id not in matching_turn_ids]
                sessions_removed += len(session.turns) - len(kept_turns)
                if kept_turns:
                    next_sessions.append(
                        NormalizedSession(
                            session_id=session.session_id,
                            turns=kept_turns,
                            timestamp=session.timestamp,
                            metadata=session.metadata,
                        )
                    )
            self._sessions = next_sessions
        self._manual_current_state_snapshot = []
        return {
            "purge": {
                "status": "completed",
                "observation_records_removed": observations_before - len(self._manual_observations),
                "event_records_removed": events_before - len(self._manual_events),
                "session_turns_removed": sessions_removed,
            }
        }

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
        elif write_operation in {"delete", "purge"} and request.timestamp:
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
            (
                entry.subject,
                state_deletion_target(entry),
                active_state_entity_key(entry, predicate=state_deletion_target(entry))
                if state_deletion_target(entry).startswith("entity.")
                or state_deletion_target(entry).startswith("profile.current_")
                else "",
            )
            for entry in observations
            if entry.predicate == "state_deletion" and state_deletion_target(entry)
        }
        active_deletions: list[ObservationEntry] = []
        for subject, predicate, entity_key in sorted(deletion_targets):
            if not has_active_state_deletion(
                observations,
                subject=subject,
                predicate=predicate,
                entity_key=entity_key or None,
            ):
                continue
            deletion_entries = self._deletion_entries(
                observations,
                subject=subject,
                predicate=predicate,
                entity_key=entity_key or None,
            )
            if deletion_entries:
                active_deletions.append(deletion_entries[-1])
        return sorted(
            [*current_entries, *active_deletions],
            key=lambda entry: (_timestamp_key(entry.timestamp), entry.observation_id),
        )

    def _annotate_active_state_maintenance(
        self,
        observations: list[ObservationEntry],
        *,
        snapshot: list[ObservationEntry],
        maintained_at: str,
    ) -> list[ObservationEntry]:
        if not observations:
            return []
        current_observation_ids = {entry.observation_id for entry in snapshot}
        current_keys = {
            self._active_state_entry_key(entry)
            for entry in snapshot
            if entry.predicate != "state_deletion"
        }
        later_deletions_by_target: dict[tuple[str, str], list[ObservationEntry]] = {}
        later_updates_by_key: dict[tuple[str, str, str], list[ObservationEntry]] = {}
        later_updates_by_target: dict[tuple[str, str], list[ObservationEntry]] = {}
        for entry in observations:
            target = state_deletion_target(entry)
            if target:
                later_deletions_by_target.setdefault((entry.subject, target), []).append(entry)
                continue
            if self._is_active_state_observation(entry):
                later_updates_by_key.setdefault(self._active_state_entry_key(entry), []).append(entry)
                later_updates_by_target.setdefault((entry.subject, entry.predicate), []).append(entry)

        maintained: list[ObservationEntry] = []
        for entry in observations:
            if not self._is_active_state_observation(entry):
                maintained.append(entry)
                continue
            action = "still_current"
            reason = "current_snapshot"
            replacement: ObservationEntry | None = None
            deletion_replacement: ObservationEntry | None = None
            if entry.observation_id in current_observation_ids:
                if entry.predicate != "state_deletion" and self._active_state_revalidation_due(entry, maintained_at):
                    action = "stale_preserved"
                    reason = "past_revalidate_at"
            else:
                target_predicate = state_deletion_target(entry) or entry.predicate
                deletion_replacement = next(
                    (
                        deletion
                        for deletion in sorted(
                            later_deletions_by_target.get((entry.subject, target_predicate), []),
                            key=entry_sort_key,
                        )
                        if entry_sort_key(deletion) > entry_sort_key(entry)
                    ),
                    None,
                )
                if deletion_replacement is not None:
                    action = "archived"
                    reason = "deleted_by_later_state_deletion"
                else:
                    update_candidates = (
                        later_updates_by_target.get((entry.subject, target_predicate), [])
                        if entry.predicate == "state_deletion"
                        else later_updates_by_key.get(self._active_state_entry_key(entry), [])
                    )
                    replacement = next(
                        (
                            update
                            for update in sorted(
                                update_candidates,
                                key=entry_sort_key,
                            )
                            if entry_sort_key(update) > entry_sort_key(entry)
                        ),
                        None,
                    )
                if deletion_replacement is None and replacement is not None:
                    if entry.predicate == "state_deletion":
                        action = "resurrected"
                        reason = "deleted_state_resurrected_by_newer_current_state"
                    else:
                        action = "superseded"
                        reason = "replaced_by_newer_current_state"
                elif deletion_replacement is None and self._active_state_entry_key(entry) not in current_keys:
                    action = "superseded"
                    reason = "compacted_out_of_current_snapshot"
            metadata = dict(entry.metadata)
            metadata["active_state_maintenance_action"] = action
            metadata["active_state_maintenance_at"] = maintained_at
            metadata["active_state_maintenance_reason"] = reason
            if replacement is not None:
                metadata["active_state_replacement_observation_id"] = replacement.observation_id
                metadata["active_state_replacement_value"] = _normalize_scalar(
                    replacement.metadata.get("value") or replacement.text
                )
                metadata["active_state_replacement_timestamp"] = replacement.timestamp
            if deletion_replacement is not None:
                metadata["active_state_deletion_observation_id"] = deletion_replacement.observation_id
                metadata["active_state_deletion_timestamp"] = deletion_replacement.timestamp
            if action == "stale_preserved":
                lag_days = self._active_state_revalidation_lag_days(entry, maintained_at)
                if lag_days is not None:
                    metadata["active_state_revalidation_lag_days"] = lag_days
                    metadata["active_state_decay_score_delta"] = self._active_state_decay_score_delta(lag_days)
            maintained.append(replace(entry, metadata=metadata))
        return maintained

    def _active_state_maintenance_audit_samples(
        self,
        observations: list[ObservationEntry],
        *,
        limit_per_bucket: int = 3,
    ) -> JsonDict:
        buckets = {
            "archived": [],
            "deleted": [],
            "stale_preserved": [],
            "superseded": [],
            "resurrected": [],
            "still_current": [],
        }
        for entry in sorted(
            observations,
            key=lambda item: (_timestamp_key(item.timestamp), observation_id_sort_key(item.observation_id)),
            reverse=True,
        ):
            action = str(entry.metadata.get("active_state_maintenance_action") or "").strip()
            if action == "archived":
                bucket = "archived"
            elif action == "stale_preserved":
                bucket = "stale_preserved"
            elif action == "superseded":
                bucket = "superseded"
            elif action == "resurrected":
                bucket = "resurrected"
            elif action == "still_current":
                bucket = "deleted" if entry.predicate == "state_deletion" else "still_current"
            else:
                continue
            if len(buckets[bucket]) >= limit_per_bucket:
                continue
            buckets[bucket].append(self._active_state_maintenance_sample(entry, action=action))
            if all(len(items) >= limit_per_bucket for items in buckets.values()):
                break
        return buckets

    def _active_state_maintenance_sample(self, entry: ObservationEntry, *, action: str) -> JsonDict:
        target_predicate = state_deletion_target(entry) or entry.predicate
        value = _normalize_scalar(
            entry.metadata.get("deleted_value")
            or entry.metadata.get("value")
            or entry.text
        )
        return {
            "observation_id": entry.observation_id,
            "subject": entry.subject,
            "predicate": target_predicate,
            "value": value,
            "timestamp": entry.timestamp,
            "action": "deleted" if entry.predicate == "state_deletion" and action == "still_current" else action,
            "reason": _normalize_scalar(entry.metadata.get("active_state_maintenance_reason")),
            "salience_score": entry.metadata.get("salience_score"),
            "confidence": entry.metadata.get("confidence"),
            "revalidate_at": _normalize_scalar(entry.metadata.get("revalidate_at")),
            "maintenance_at": _normalize_scalar(entry.metadata.get("active_state_maintenance_at")),
            "revalidation_lag_days": entry.metadata.get("active_state_revalidation_lag_days"),
            "decay_score_delta": entry.metadata.get("active_state_decay_score_delta"),
            "replacement_observation_id": _normalize_scalar(
                entry.metadata.get("active_state_replacement_observation_id")
            ),
            "replacement_value": _normalize_scalar(entry.metadata.get("active_state_replacement_value")),
            "replacement_timestamp": _normalize_scalar(entry.metadata.get("active_state_replacement_timestamp")),
            "deletion_observation_id": _normalize_scalar(entry.metadata.get("active_state_deletion_observation_id")),
            "deletion_timestamp": _normalize_scalar(entry.metadata.get("active_state_deletion_timestamp")),
        }

    def _is_active_state_observation(self, entry: ObservationEntry) -> bool:
        metadata = entry.metadata if isinstance(entry.metadata, dict) else {}
        if entry.predicate == "state_deletion":
            return True
        if str(metadata.get("retention_class") or "").strip() == "active_state":
            return True
        return self._observation_memory_role(entry) in {"current_state", "state_deletion"}

    def _active_state_entry_key(self, entry: ObservationEntry) -> tuple[str, str, str]:
        predicate = state_deletion_target(entry) or entry.predicate
        return (
            entry.subject,
            predicate,
            active_state_entity_key(entry, predicate=predicate),
        )

    def _default_observation_entity_key(
        self,
        *,
        predicate: str,
        value: str,
        retention_class: RetentionClass | None,
        memory_role: MemoryRole | None,
    ) -> str:
        if predicate.startswith("profile.current_"):
            return predicate
        if retention_class == "active_state" and predicate.startswith("telegram.summary.latest_"):
            return predicate
        if memory_role == "current_state" and predicate.startswith("profile.current_"):
            return predicate
        return value.lower()

    def _active_state_revalidation_due(self, entry: ObservationEntry, maintained_at: str) -> bool:
        metadata = entry.metadata if isinstance(entry.metadata, dict) else {}
        revalidate_at = str(metadata.get("revalidate_at") or "").strip()
        if not revalidate_at:
            return False
        try:
            due_at = datetime.fromisoformat(revalidate_at.replace("Z", "+00:00"))
            now = datetime.fromisoformat(maintained_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return due_at <= now

    def _active_state_revalidation_lag_days(self, entry: ObservationEntry, maintained_at: str) -> int | None:
        metadata = entry.metadata if isinstance(entry.metadata, dict) else {}
        revalidate_at = str(metadata.get("revalidate_at") or "").strip()
        if not revalidate_at:
            return None
        try:
            due_at = datetime.fromisoformat(revalidate_at.replace("Z", "+00:00"))
            now = datetime.fromisoformat(maintained_at.replace("Z", "+00:00"))
        except ValueError:
            return None
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return max(0, (now - due_at).days)

    def _active_state_decay_score_delta(self, lag_days: int) -> float:
        if lag_days <= 0:
            return 0.0
        return -round(min(lag_days / 180, 1.0), 4)

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

    def _select_task_recovery_active_goal(
        self,
        records: list[RetrievedMemoryRecord],
        *,
        query: str | None,
    ) -> RetrievedMemoryRecord | None:
        candidates = [
            record
            for record in records
            if self._task_recovery_matches_bucket(record, bucket="active_goal")
        ]
        ranked = sorted(
            candidates,
            key=lambda record: self._task_recovery_rank_key(record, query=query, bucket="active_goal"),
            reverse=True,
        )
        return ranked[0] if ranked else None

    def _task_recovery_bucket(
        self,
        records: list[RetrievedMemoryRecord],
        *,
        bucket: str,
        query: str | None,
        limit: int,
    ) -> list[RetrievedMemoryRecord]:
        ranked = sorted(
            [
                record
                for record in records
                if self._task_recovery_matches_bucket(record, bucket=bucket)
            ],
            key=lambda record: self._task_recovery_rank_key(record, query=query, bucket=bucket),
            reverse=True,
        )
        deduped: list[RetrievedMemoryRecord] = []
        seen: set[str] = set()
        for record in ranked:
            record_id = self._record_movement_id(record)
            if record_id in seen:
                continue
            seen.add(record_id)
            deduped.append(record)
            if len(deduped) >= limit:
                break
        return deduped

    def _task_recovery_matches_bucket(self, record: RetrievedMemoryRecord, *, bucket: str) -> bool:
        text = self._task_recovery_search_text(record)
        tokens = _tokenize(text)
        predicate = record.predicate.lower()
        if bucket == "active_goal":
            if record.memory_role != "current_state":
                return False
            return any(
                marker in predicate
                for marker in (
                    "current_focus",
                    "current_goal",
                    "current_plan",
                    "current_mission",
                    "active_task",
                    "active_goal",
                    "active_work",
                )
            )
        if bucket == "completed_steps":
            return bool(
                tokens.intersection({"complete", "completed", "done", "finished", "shipped", "verified", "passed"})
                or any(marker in predicate for marker in ("completed", "done", "shipped", "verified"))
            )
        if bucket == "blockers":
            return bool(
                tokens.intersection({"blocker", "blocked", "blocking", "stuck", "risk", "waiting", "missing"})
                or any(marker in predicate for marker in ("blocker", "blocked", "risk", "waiting"))
            )
        if bucket == "next_actions":
            if self._task_recovery_matches_bucket(record, bucket="blockers"):
                return False
            return bool(
                tokens.intersection({"next", "todo", "continue", "resume", "implement", "wire", "connect"})
                or any(marker in predicate for marker in ("next_action", "todo", "plan", "resume"))
            )
        if bucket == "episodic_context":
            return record.memory_role == "episodic" or record.predicate == "raw_turn"
        return False

    def _task_recovery_rank_key(
        self,
        record: RetrievedMemoryRecord,
        *,
        query: str | None,
        bucket: str,
    ) -> tuple[int, str, str]:
        text = self._task_recovery_search_text(record)
        query_tokens = _tokenize(query or "")
        overlap = len(query_tokens.intersection(_tokenize(text))) if query_tokens else 0
        role_boost = 0
        if record.memory_role == "current_state":
            role_boost += 30
        elif record.memory_role == "event":
            role_boost += 12
        elif record.memory_role == "structured_evidence":
            role_boost += 8
        elif record.memory_role == "episodic":
            role_boost += 4
        bucket_boost = 0
        if bucket == "active_goal":
            bucket_boost += 20
            if "focus" in record.predicate or "goal" in record.predicate:
                bucket_boost += 8
        if query_tokens and overlap == 0 and bucket == "episodic_context":
            bucket_boost -= 20
        return (
            overlap * 10 + role_boost + bucket_boost,
            _timestamp_key(record.timestamp),
            self._record_movement_id(record),
        )

    def _task_recovery_search_text(self, record: RetrievedMemoryRecord) -> str:
        metadata_text = " ".join(
            str(value)
            for key, value in record.metadata.items()
            if key in {"value", "entity_key", "entity_label", "source_surface", "task_recovery_label"}
        )
        return " ".join(
            part
            for part in (
                record.text,
                record.subject,
                record.predicate,
                metadata_text,
            )
            if part
        )

    def _task_recovery_bucket_name(
        self,
        record: RetrievedMemoryRecord,
        *,
        active_goal: RetrievedMemoryRecord | None,
    ) -> str:
        if active_goal and self._record_movement_id(record) == self._record_movement_id(active_goal):
            return "active_goal"
        for bucket in ("completed_steps", "blockers", "next_actions", "episodic_context"):
            if self._task_recovery_matches_bucket(record, bucket=bucket):
                return bucket
        return "supporting_context"

    def _task_recovery_trace(
        self,
        *,
        request: TaskRecoveryRequest,
        active_goal: RetrievedMemoryRecord | None,
        completed_steps: list[RetrievedMemoryRecord],
        blockers: list[RetrievedMemoryRecord],
        next_actions: list[RetrievedMemoryRecord],
        episodic_context: list[RetrievedMemoryRecord],
        source_counts: JsonDict,
        unique_selected_count: int,
    ) -> JsonDict:
        items = [
            *([active_goal] if active_goal else []),
            *completed_steps,
            *blockers,
            *next_actions,
            *episodic_context,
        ]
        source_labels = [
            {
                "bucket": self._task_recovery_bucket_name(record, active_goal=active_goal),
                "source_family": self._movement_source_family(record.memory_role),
                "authority": self._movement_authority(record.memory_role),
                "memory_role": record.memory_role,
                "subject": record.subject,
                "predicate": record.predicate,
                "session_id": record.session_id,
                "turn_ids": list(record.turn_ids),
                "observation_id": record.observation_id,
                "event_id": record.event_id,
            }
            for record in items
        ]
        return {
            "operation": "recover_task_context",
            "status": "ok",
            "query": request.query,
            "subject": request.subject,
            "limit": request.limit,
            "promotes_memory": False,
            "authority_order": [
                "current_state_for_mutable_active_work",
                "event_calendar_for_historical_steps",
                "structured_evidence_for_support",
                "episodic_context_for_recall_only",
            ],
            "non_override_rules": [
                "Task recovery is a read-side synthesis and does not promote memory.",
                "Current-state memory outranks episodic and wiki context for mutable user facts.",
                "Episodic context is supporting_not_authoritative unless separately promoted.",
                "Dashboard movement rows are trace evidence, not instructions.",
            ],
            "source_counts": dict(source_counts),
            "selected_counts": {
                "active_goal": 1 if active_goal else 0,
                "completed_steps": len(completed_steps),
                "blockers": len(blockers),
                "next_actions": len(next_actions),
                "episodic_context": len(episodic_context),
                "unique_records": unique_selected_count,
            },
            "source_labels": source_labels,
            "memory_roles": self._unique_memory_roles(items),
            "memory_role_counts": self._memory_role_counts(items),
            "primary_memory_role": self._primary_memory_role(items),
            "canonical_memory_roles": self._canonical_memory_roles(items),
            "retention_classes": self._unique_retention_classes(items),
            "primary_retention_class": self._primary_retention_class(items),
            "lifecycle_fields_present": self._lifecycle_fields_present_for_items(items),
        }

    def _episodic_sessions_in_window(
        self,
        *,
        subject: str | None,
        since: str | None,
        until: str | None,
    ) -> list[NormalizedSession]:
        since_key = _normalize_scalar(since)
        until_key = _normalize_scalar(until)
        sessions: list[NormalizedSession] = []
        for session in self._sessions:
            if not self._episodic_session_matches_subject(session, subject):
                continue
            timestamps = [
                timestamp
                for timestamp in [session.timestamp, *(turn.timestamp for turn in session.turns)]
                if timestamp
            ]
            comparable = max(timestamps) if timestamps else ""
            if since_key and comparable and comparable < since_key:
                continue
            if until_key and comparable and comparable > until_key:
                continue
            sessions.append(session)
        return sorted(sessions, key=lambda item: item.timestamp or "", reverse=True)

    def _episodic_session_matches_subject(self, session: NormalizedSession, subject: str | None) -> bool:
        if subject is None:
            return True
        session_subject = self._normalize_optional_subject(str(session.metadata.get("subject") or ""))
        turn_subjects = [
            self._normalize_optional_subject(str(turn.metadata.get("subject") or ""))
            for turn in session.turns
        ]
        candidates = [item for item in [session_subject, *turn_subjects] if item]
        if candidates:
            return subject in candidates
        if subject == "user":
            return any(_normalize_scalar(turn.speaker).lower() in {"user", "speaker_a", "speaker_b"} for turn in session.turns)
        return False

    def _session_summary_record(self, session: NormalizedSession) -> RetrievedMemoryRecord:
        first_turn = session.turns[0]
        last_turn = session.turns[-1]
        timestamp = session.timestamp or last_turn.timestamp or first_turn.timestamp
        subject = (
            self._normalize_optional_subject(str(session.metadata.get("subject") or ""))
            or self._normalize_optional_subject(str(first_turn.metadata.get("subject") or ""))
            or "session"
        )
        turn_fragments = [
            f"{turn.speaker}: {_normalize_scalar(turn.text)[:180]}"
            for turn in session.turns[:6]
            if _normalize_scalar(turn.text)
        ]
        text = f"Session {session.session_id}: " + " | ".join(turn_fragments)
        return RetrievedMemoryRecord(
            memory_role="episodic",
            subject=subject,
            predicate="session.summary",
            text=text[:900],
            session_id=session.session_id,
            turn_ids=[turn.turn_id for turn in session.turns],
            timestamp=timestamp,
            retention_class="episodic_archive",
            lifecycle={
                "created_at": first_turn.timestamp or session.timestamp,
                "document_time": timestamp,
            },
            metadata={
                **dict(session.metadata),
                "source_class": "episodic_session_summary",
                "summary_kind": "extractive_session_summary",
                "turn_count": len(session.turns),
            },
        )

    def _session_turn_record(self, session: NormalizedSession, turn: NormalizedTurn) -> RetrievedMemoryRecord:
        speaker = _normalize_scalar(turn.speaker).lower() or "unknown"
        subject = (
            self._normalize_optional_subject(str(turn.metadata.get("subject") or ""))
            or ("user" if speaker in {"user", "speaker_a", "speaker_b"} else speaker)
        )
        return RetrievedMemoryRecord(
            memory_role="episodic",
            subject=subject,
            predicate="raw_turn",
            text=f"{turn.speaker}: {_normalize_scalar(turn.text)}",
            session_id=session.session_id,
            turn_ids=[turn.turn_id],
            timestamp=turn.timestamp or session.timestamp,
            retention_class="episodic_archive",
            lifecycle={
                "created_at": turn.timestamp or session.timestamp,
                "document_time": turn.timestamp or session.timestamp,
            },
            metadata={
                **dict(turn.metadata),
                "source_class": "episodic_raw_turn",
                "speaker": turn.speaker,
                "session_timestamp": session.timestamp,
            },
        )

    def _rank_episodic_records(
        self,
        records: list[RetrievedMemoryRecord],
        *,
        query: str | None,
        limit: int,
    ) -> list[RetrievedMemoryRecord]:
        query_tokens = _tokenize(query or "")
        ranked: list[tuple[int, str, str, RetrievedMemoryRecord]] = []
        for record in records:
            search_text = " ".join(
                part
                for part in (
                    record.text,
                    record.subject,
                    record.predicate,
                    str(record.metadata.get("source_class") or ""),
                    str(record.metadata.get("speaker") or ""),
                )
                if part
            )
            overlap = len(query_tokens.intersection(_tokenize(search_text))) if query_tokens else 0
            role_boost = 2 if record.predicate == "session.summary" else 0
            ranked.append(
                (
                    overlap * 10 + role_boost,
                    _timestamp_key(record.timestamp),
                    self._record_movement_id(record),
                    record,
                )
            )
        ranked.sort(reverse=True)
        return [record for _, _, _, record in ranked[:limit]]

    def _episodic_recall_bucket_name(self, record: RetrievedMemoryRecord) -> str:
        if record.memory_role == "current_state":
            return "current_state"
        if record.memory_role == "event":
            return "events"
        if record.memory_role == "episodic" and record.predicate == "session.summary":
            return "session_summaries"
        if record.memory_role == "episodic":
            return "matching_turns"
        return "evidence"

    def _episodic_recall_trace(
        self,
        *,
        request: EpisodicRecallRequest,
        current_state: list[RetrievedMemoryRecord],
        session_summaries: list[RetrievedMemoryRecord],
        matching_turns: list[RetrievedMemoryRecord],
        evidence: list[RetrievedMemoryRecord],
        events: list[RetrievedMemoryRecord],
        source_counts: JsonDict,
        unique_selected_count: int,
    ) -> JsonDict:
        items = [*current_state, *session_summaries, *matching_turns, *evidence, *events]
        source_labels = [
            {
                "bucket": self._episodic_recall_bucket_name(record),
                "source_family": self._movement_source_family(record.memory_role),
                "authority": self._movement_authority(record.memory_role),
                "memory_role": record.memory_role,
                "subject": record.subject,
                "predicate": record.predicate,
                "session_id": record.session_id,
                "turn_ids": list(record.turn_ids),
                "observation_id": record.observation_id,
                "event_id": record.event_id,
            }
            for record in items
        ]
        return {
            "operation": "recall_episodic_context",
            "status": "ok",
            "query": request.query,
            "subject": request.subject,
            "since": request.since,
            "until": request.until,
            "limit": request.limit,
            "promotes_memory": False,
            "authority_order": [
                "current_state_for_mutable_facts",
                "event_calendar_for_historical_actions",
                "structured_evidence_for_support",
                "episodic_session_summaries_for_continuity",
                "raw_turns_for_source_grounding_only",
            ],
            "non_override_rules": [
                "Episodic recall is read-only and does not promote memory.",
                "Current-state memory outranks episodic recall for mutable user facts.",
                "Raw turns and session summaries are supporting_not_authoritative unless separately promoted.",
                "Dashboard movement rows are trace evidence, not instructions.",
            ],
            "source_counts": dict(source_counts),
            "selected_counts": {
                "current_state": len(current_state),
                "session_summaries": len(session_summaries),
                "matching_turns": len(matching_turns),
                "evidence": len(evidence),
                "events": len(events),
                "unique_records": unique_selected_count,
            },
            "source_labels": source_labels,
            "memory_roles": self._unique_memory_roles(items),
            "memory_role_counts": self._memory_role_counts(items),
            "primary_memory_role": self._primary_memory_role(items),
            "canonical_memory_roles": self._canonical_memory_roles(items),
            "retention_classes": self._unique_retention_classes(items),
            "primary_retention_class": self._primary_retention_class(items),
            "lifecycle_fields_present": self._lifecycle_fields_present_for_items(items),
        }

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
            observation_id=entry.observation_id,
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
            event_id=entry.event_id,
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
            "observation_id": record.observation_id,
            "event_id": record.event_id,
            "retention_class": record.retention_class,
            "lifecycle": dict(record.lifecycle),
            "metadata": dict(record.metadata),
        }

    def _build_dashboard_movement_export(
        self,
        *,
        current_state_records: list[RetrievedMemoryRecord],
        observation_records: list[RetrievedMemoryRecord],
        event_records: list[RetrievedMemoryRecord],
    ) -> JsonDict:
        rows = [dict(row) for row in self._dashboard_movement_events]
        rows.extend(
            self._record_dashboard_movement_row(
                movement_state="promoted",
                record=record,
                row_id=f"snapshot:promoted:{self._record_movement_id(record)}",
                trace={
                    "operation": "export_knowledge_base_snapshot",
                    "promotion_target": "current_state",
                    "derived_from_snapshot": True,
                },
            )
            for record in current_state_records
        )
        rows.extend(
            self._record_dashboard_movement_row(
                movement_state="selected",
                record=record,
                row_id=f"snapshot:selected:{self._record_movement_id(record)}",
                trace={
                    "operation": "export_knowledge_base_snapshot",
                    "selection_surface": "current_state_view",
                    "derived_from_snapshot": True,
                },
            )
            for record in current_state_records
        )
        rows.extend(
            self._session_dashboard_movement_row(session, index=index)
            for index, session in enumerate(self._sessions, start=1)
            if session.turns
        )
        movement_counts = Counter(str(row.get("movement_state") or "unknown") for row in rows)
        source_family_counts = Counter(str(row.get("source_family") or "unknown") for row in rows)
        authority_counts = Counter(str(row.get("authority") or "unknown") for row in rows)
        contract = build_dashboard_movement_export_contract_summary()
        return {
            "contract_name": "SparkMemoryDashboardMovementExport",
            "authority": "observability_non_authoritative",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "movement_states": list(DASHBOARD_MOVEMENT_STATES),
            "row_count": len(rows),
            "movement_counts": dict(sorted(movement_counts.items())),
            "source_family_counts": dict(sorted(source_family_counts.items())),
            "authority_counts": dict(sorted(authority_counts.items())),
            "record_counts": {
                "current_state": len(current_state_records),
                "observations": len(observation_records),
                "events": len(event_records),
                "sessions": len(self._sessions),
            },
            "rows": rows,
            "non_override_rules": list(contract["non_override_rules"]),
        }

    def _append_record_dashboard_movement(
        self,
        *,
        movement_state: str,
        record: RetrievedMemoryRecord,
        trace: JsonDict,
    ) -> None:
        self._dashboard_movement_events.append(
            self._record_dashboard_movement_row(
                movement_state=movement_state,
                record=record,
                row_id=self._next_dashboard_movement_id(),
                trace=trace,
            )
        )

    def _append_request_dashboard_movement(
        self,
        *,
        movement_state: str,
        request: MemoryWriteRequest,
        write_kind: str,
        write_operation: str,
        reason: str,
    ) -> None:
        subject = self._normalize_subject(request.subject or "")
        predicate = self._normalize_predicate(request.predicate or "")
        self._dashboard_movement_events.append(
            self._dashboard_movement_row(
                row_id=self._next_dashboard_movement_id(),
                movement_state=movement_state,
                source_family="event" if write_kind == "event" else "evidence",
                authority="supporting_not_authoritative",
                scope_kind=self._movement_scope_kind(subject),
                subject=subject,
                predicate=predicate,
                timestamp=request.timestamp,
                salience_score=0.0,
                confidence=0.0,
                lifecycle={},
                trace={
                    "operation": "write_memory",
                    "status": "unsupported_write",
                    "reason": reason,
                    "write_kind": write_kind,
                    "write_operation": write_operation,
                    "persisted": False,
                    "source_of_truth": "SparkMemorySDK",
                },
            )
        )

    def _record_dashboard_movement_row(
        self,
        *,
        movement_state: str,
        record: RetrievedMemoryRecord,
        row_id: str,
        trace: JsonDict,
    ) -> JsonDict:
        record_id = self._record_movement_id(record)
        row_trace = {
            "source_of_truth": "SparkMemorySDK",
            "record_id": record_id,
            "memory_role": record.memory_role,
            "observation_id": record.observation_id,
            "event_id": record.event_id,
            "session_id": record.session_id,
            "turn_ids": list(record.turn_ids),
            **dict(trace),
        }
        return self._dashboard_movement_row(
            row_id=row_id,
            movement_state=movement_state,
            source_family=self._movement_source_family(record.memory_role),
            authority=self._movement_authority(record.memory_role),
            scope_kind=self._movement_scope_kind(record.subject),
            subject=record.subject,
            predicate=record.predicate,
            timestamp=record.timestamp,
            salience_score=self._movement_salience(record),
            confidence=self._movement_confidence(record),
            lifecycle=dict(record.lifecycle),
            trace=row_trace,
        )

    def _session_dashboard_movement_row(self, session: NormalizedSession, *, index: int) -> JsonDict:
        first_turn = session.turns[0]
        last_turn = session.turns[-1]
        return self._dashboard_movement_row(
            row_id=f"snapshot:summarized:{session.session_id}:{index}",
            movement_state="summarized",
            source_family="episodic_summary",
            authority="supporting_not_authoritative",
            scope_kind="session_scoped",
            subject=str(session.metadata.get("subject") or "session"),
            predicate="session.summary",
            timestamp=session.timestamp or last_turn.timestamp or first_turn.timestamp,
            salience_score=0.5,
            confidence=0.8,
            lifecycle={
                "created_at": first_turn.timestamp or session.timestamp,
                "document_time": session.timestamp or last_turn.timestamp or first_turn.timestamp,
            },
            trace={
                "operation": "export_knowledge_base_snapshot",
                "source_of_truth": "SparkMemorySDK",
                "session_id": session.session_id,
                "turn_count": len(session.turns),
                "derived_from_snapshot": True,
            },
        )

    def _dashboard_movement_row(
        self,
        *,
        row_id: str,
        movement_state: str,
        source_family: str,
        authority: str,
        scope_kind: str,
        subject: str,
        predicate: str,
        timestamp: str | None,
        salience_score: float,
        confidence: float,
        lifecycle: JsonDict,
        trace: JsonDict,
    ) -> JsonDict:
        return {
            "id": row_id,
            "movement_state": movement_state if movement_state in DASHBOARD_MOVEMENT_STATES else "dropped",
            "source_family": source_family,
            "authority": authority,
            "scope_kind": scope_kind,
            "subject": subject,
            "predicate": predicate,
            "timestamp": timestamp,
            "salience_score": salience_score,
            "confidence": confidence,
            "lifecycle": dict(lifecycle),
            "trace": dict(trace),
        }

    def _next_dashboard_movement_id(self) -> str:
        self._dashboard_movement_counter += 1
        return f"sdk-movement-{self._dashboard_movement_counter}"

    def _record_movement_id(self, record: RetrievedMemoryRecord) -> str:
        explicit_id = record.observation_id or record.event_id
        if explicit_id:
            return explicit_id
        payload = "\x1f".join(
            [record.session_id, ",".join(record.turn_ids), record.memory_role, record.subject, record.predicate]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def _movement_source_family(self, memory_role: MemoryRole) -> str:
        if memory_role in {"current_state", "state_deletion"}:
            return "current_state"
        if memory_role == "event":
            return "event"
        if memory_role == "episodic":
            return "episodic_summary"
        return "evidence"

    def _movement_authority(self, memory_role: MemoryRole) -> str:
        if memory_role in {"current_state", "state_deletion"}:
            return "authoritative_current"
        if memory_role == "event":
            return "authoritative_historical"
        if memory_role == "episodic":
            return "supporting_not_authoritative"
        return "structured_support"

    def _movement_scope_kind(self, subject: str) -> str:
        normalized = _normalize_human_subject(subject)
        if normalized == "user" or normalized.startswith("human:"):
            return "user_scoped"
        if normalized == "session":
            return "session_scoped"
        return "system_scoped"

    def _movement_salience(self, record: RetrievedMemoryRecord) -> float:
        explicit = self._movement_float(record.metadata.get("salience_score"))
        if explicit is not None:
            return explicit
        if record.memory_role in {"current_state", "state_deletion"} or record.retention_class == "active_state":
            return 1.0
        if record.memory_role == "event":
            return 0.75
        if record.memory_role == "episodic":
            return 0.4
        return 0.65

    def _movement_confidence(self, record: RetrievedMemoryRecord) -> float:
        explicit = self._movement_float(record.metadata.get("confidence"))
        return explicit if explicit is not None else 1.0

    def _movement_float(self, value: Any) -> float | None:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None


def build_sdk_contract_summary(
    *,
    runtime_memory_architecture: str | None = None,
    runtime_memory_provider: str | None = None,
) -> dict[str, Any]:
    return {
        "runtime_class": "SparkMemorySDK",
        "runtime_memory_architecture": _runtime_memory_architecture(runtime_memory_architecture),
        "runtime_memory_provider": _runtime_memory_provider(runtime_memory_provider),
        "runtime_architecture_selection": {
            "active_leader": "summary_synthesis_memory",
            "strong_challenger": "dual_store_event_calendar_hybrid",
            "sidecars": [
                "graphiti_temporal_graph",
                "obsidian_llm_wiki_packets",
                "mem0_shadow",
            ],
            "deferred_sidecars": ["cognee_optional"],
            "selection_basis": [
                "live_builder_soak",
                "external_benchmark_matrix",
                "temporal_conflict_gauntlet",
                "oss_memory_stack_prune_plan_2026_04_28",
            ],
        },
        "memory_roles": sdk_memory_role_contracts(),
        "retention_classes": sdk_retention_contracts(),
        "retention_defaults_by_memory_role": sdk_retention_defaults_by_role(),
        "lifecycle_fields": list(SDK_LIFECYCLE_FIELDS),
        "dashboard_movement_export_contract": build_dashboard_movement_export_contract_summary(),
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
            "write_observation": ["auto", "create", "update", "delete", "purge"],
            "write_event": ["auto", "event"],
        },
        "maintenance_methods": ["reconsolidate_manual_memory"],
        "export_methods": ["export_knowledge_base_snapshot"],
        "sidecar_contract": {
            "contract_name": "MemorySidecarAdapter",
            "sidecar_authority": "supporting_or_shadow_until_promoted",
            "runtime_sidecars": [
                "graphiti_temporal_graph",
                "obsidian_llm_wiki_packets",
                "mem0_shadow",
            ],
            "deferred_sidecars": ["cognee_optional"],
        },
        "read_methods": [
            "get_current_state",
            "get_historical_state",
            "retrieve_evidence",
            "retrieve_events",
            "explain_answer",
            "recover_task_context",
            "recall_episodic_context",
        ],
        "request_contracts": [
            "MemoryWriteRequest",
            "CurrentStateRequest",
            "HistoricalStateRequest",
            "EvidenceRetrievalRequest",
            "EventRetrievalRequest",
            "AnswerExplanationRequest",
            "TaskRecoveryRequest",
            "EpisodicRecallRequest",
        ],
        "response_contracts": [
            "MemoryWriteResult",
            "MemoryLookupResult",
            "MemoryRetrievalResult",
            "AnswerExplanationResult",
            "TaskRecoveryResult",
            "EpisodicRecallResult",
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
            "recover_task_context": [
                "promotes_memory",
                "authority_order",
                "non_override_rules",
                "source_counts",
                "selected_counts",
                "source_labels",
                "memory_roles",
                "memory_role_counts",
                "primary_memory_role",
                "canonical_memory_roles",
                "retention_classes",
                "primary_retention_class",
                "lifecycle_fields_present",
            ],
            "recall_episodic_context": [
                "promotes_memory",
                "authority_order",
                "non_override_rules",
                "source_counts",
                "selected_counts",
                "source_labels",
                "memory_roles",
                "memory_role_counts",
                "primary_memory_role",
                "canonical_memory_roles",
                "retention_classes",
                "primary_retention_class",
                "lifecycle_fields_present",
            ],
        },
    }


def build_dashboard_movement_export_contract_summary() -> dict[str, Any]:
    return {
        "contract_name": "SparkMemoryDashboardMovementExport",
        "purpose": (
            "Stable agent/human dashboard feed for memory movement. This is a trace contract, "
            "not an authority upgrade path."
        ),
        "movement_states": list(DASHBOARD_MOVEMENT_STATES),
        "source_families": [
            "current_state",
            "evidence",
            "event",
            "episodic_summary",
            "llm_wiki",
            "memory_kb",
            "graphiti_sidecar",
            "diagnostics",
        ],
        "authority_classes": [
            "authoritative_current",
            "authoritative_historical",
            "structured_support",
            "supporting_not_authoritative",
            "advisory_shadow",
        ],
        "required_record_fields": [
            "id",
            "movement_state",
            "source_family",
            "authority",
            "scope_kind",
            "subject",
            "predicate",
            "timestamp",
            "salience_score",
            "confidence",
            "lifecycle",
            "trace",
        ],
        "non_override_rules": [
            "Dashboard rows are observability records, not prompt instructions.",
            "Blocked and dropped rows must never become durable memory without a separate promotion gate.",
            "Wiki, diagnostics, and graph sidecar rows remain supporting or advisory unless evaluated and promoted by Spark gates.",
            "User-scoped records must not be displayed or exported as global Spark doctrine.",
        ],
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
            "observation": ["auto", "create", "update", "delete", "purge"],
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
