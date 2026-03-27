from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from .contracts import JsonDict, MemoryRole, NormalizedBenchmarkSample, NormalizedQuestion, NormalizedSession, NormalizedTurn
from .memory_systems import EventCalendarEntry, ObservationEntry, build_event_calendar, build_observation_log
from .memory_updates import build_current_state_view, has_active_state_deletion, state_deletion_target


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _timestamp_key(timestamp: str | None) -> str:
    return timestamp or ""


@dataclass(frozen=True)
class MemoryWriteRequest:
    text: str
    speaker: str = "user"
    timestamp: str | None = None
    session_id: str | None = None
    turn_id: str | None = None
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


class SparkMemorySDK:
    def __init__(self) -> None:
        self._sessions: list[NormalizedSession] = []
        self._session_counter = 0

    def write_observation(self, request: MemoryWriteRequest) -> MemoryWriteResult:
        return self._write(request)

    def write_event(self, request: MemoryWriteRequest) -> MemoryWriteResult:
        return self._write(request)

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
        observations = self._observations()
        reflected = build_current_state_view(observations)
        matches = [
            entry
            for entry in reflected
            if entry.subject == subject and entry.predicate == predicate
        ]
        if matches:
            selected = sorted(matches, key=lambda entry: (_timestamp_key(entry.timestamp), entry.observation_id))[-1]
            return MemoryLookupResult(
                found=True,
                value=str(selected.metadata.get("value", "")).strip() or None,
                text=selected.text,
                memory_role="current_state",
                provenance=[self._observation_record(selected, memory_role="current_state")],
                trace={
                    "operation": "get_current_state",
                    "subject": subject,
                    "predicate": predicate,
                    "observation_count": len(observations),
                },
            )
        if has_active_state_deletion(observations, subject=subject, predicate=predicate):
            deletion_entries = self._deletion_entries(observations, subject=subject, predicate=predicate)
            return MemoryLookupResult(
                found=False,
                value=None,
                text=None,
                memory_role="state_deletion",
                provenance=[self._observation_record(deletion_entries[-1], memory_role="state_deletion")] if deletion_entries else [],
                trace={
                    "operation": "get_current_state",
                    "subject": subject,
                    "predicate": predicate,
                    "observation_count": len(observations),
                },
            )
        return MemoryLookupResult(
            found=False,
            value=None,
            text=None,
            memory_role="unknown",
            provenance=[],
            trace={
                "operation": "get_current_state",
                "subject": subject,
                "predicate": predicate,
                "observation_count": len(observations),
            },
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
            selected = sorted(matches, key=lambda entry: (_timestamp_key(entry.timestamp), entry.observation_id))[-1]
            return MemoryLookupResult(
                found=True,
                value=str(selected.metadata.get("value", "")).strip() or None,
                text=selected.text,
                memory_role="structured_evidence",
                provenance=[self._observation_record(selected, memory_role="structured_evidence")],
                trace={
                    "operation": "get_historical_state",
                    "subject": subject,
                    "predicate": predicate,
                    "as_of": request.as_of,
                    "observation_count": len(observations),
                },
            )
        if has_active_state_deletion(observations, subject=subject, predicate=predicate):
            deletion_entries = self._deletion_entries(observations, subject=subject, predicate=predicate)
            return MemoryLookupResult(
                found=False,
                value=None,
                text=None,
                memory_role="state_deletion",
                provenance=[self._observation_record(deletion_entries[-1], memory_role="state_deletion")] if deletion_entries else [],
                trace={
                    "operation": "get_historical_state",
                    "subject": subject,
                    "predicate": predicate,
                    "as_of": request.as_of,
                    "observation_count": len(observations),
                },
            )
        return MemoryLookupResult(
            found=False,
            value=None,
            text=None,
            memory_role="unknown",
            provenance=[],
            trace={
                "operation": "get_historical_state",
                "subject": subject,
                "predicate": predicate,
                "as_of": request.as_of,
                "observation_count": len(observations),
            },
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
        observations = self._observations()
        items = [
            self._observation_record(entry, memory_role=self._observation_memory_role(entry))
            for entry in self._rank_observations(
                observations,
                query=request.query,
                subject=self._normalize_optional_subject(request.subject),
                predicate=self._normalize_optional_predicate(request.predicate),
                limit=request.limit,
            )
        ]
        return MemoryRetrievalResult(
            items=items,
            trace={
                "operation": "retrieve_evidence",
                "query": request.query,
                "subject": request.subject,
                "predicate": request.predicate,
                "limit": request.limit,
            },
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
            trace={
                "operation": "retrieve_events",
                "query": request.query,
                "subject": request.subject,
                "predicate": request.predicate,
                "limit": request.limit,
            },
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
            trace={
                "operation": "explain_answer",
                "question": request.question,
                "subject": request.subject,
                "predicate": request.predicate,
                "as_of": request.as_of,
            },
        )

    def _write(self, request: MemoryWriteRequest) -> MemoryWriteResult:
        cleaned_text = str(request.text or "").strip()
        if not cleaned_text:
            return MemoryWriteResult(
                session_id=request.session_id or "",
                turn_id=request.turn_id or "",
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
                },
            )
        session_id = request.session_id or self._next_session_id()
        turn_id = request.turn_id or self._next_turn_id(session_id)
        turn = NormalizedTurn(
            turn_id=turn_id,
            speaker=request.speaker,
            text=cleaned_text,
            timestamp=request.timestamp,
            metadata=dict(request.metadata),
        )
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
        if accepted:
            self._upsert_session(session_id, turn, request.timestamp)
        return MemoryWriteResult(
            session_id=session_id,
            turn_id=turn_id,
            accepted=accepted,
            observations_written=len(observations),
            events_written=len(events),
            observations=[
                self._observation_record(entry, memory_role=self._observation_memory_role(entry))
                for entry in observations
            ],
            events=[self._event_record(entry) for entry in events],
            unsupported_reason=None if accepted else "no_structured_memory_extracted",
            trace={
                "operation": "write_memory",
                "status": "accepted" if accepted else "unsupported_write",
                "speaker": request.speaker,
                "timestamp": request.timestamp,
                "persisted": accepted,
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
        return self._sample_for_sessions(self._sessions)

    def _observations(self) -> list[ObservationEntry]:
        return build_observation_log(self._runtime_sample())

    def _events(self) -> list[EventCalendarEntry]:
        return build_event_calendar(self._runtime_sample())

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
            key=lambda entry: (_timestamp_key(entry.timestamp), entry.observation_id),
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
        ranked: list[tuple[int, str, str, ObservationEntry]] = []
        for entry in observations:
            if subject and entry.subject != subject:
                continue
            if predicate and entry.predicate != predicate and state_deletion_target(entry) != predicate:
                continue
            overlap = len(query_tokens.intersection(_tokenize(entry.text))) if query_tokens else 0
            if query_tokens and overlap == 0 and not (subject or predicate):
                continue
            ranked.append((overlap, _timestamp_key(entry.timestamp), entry.observation_id, entry))
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
        if entry.predicate == "state_deletion":
            return "state_deletion"
        if entry.predicate == "raw_turn":
            return "episodic"
        return "structured_evidence"

    def _write_has_supported_memory(
        self,
        observations: list[ObservationEntry],
        events: list[EventCalendarEntry],
    ) -> bool:
        if events:
            return True
        return any(self._observation_memory_role(entry) != "episodic" for entry in observations)

    def _normalize_subject(self, subject: str) -> str:
        return str(subject or "").strip().lower()

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
            trace=trace,
        )

    def _observation_record(self, entry: ObservationEntry, *, memory_role: MemoryRole) -> RetrievedMemoryRecord:
        return RetrievedMemoryRecord(
            memory_role=memory_role,
            subject=entry.subject,
            predicate=entry.predicate,
            text=entry.text,
            session_id=entry.session_id,
            turn_ids=entry.turn_ids,
            timestamp=entry.timestamp,
            metadata=dict(entry.metadata),
        )

    def _event_record(self, entry: EventCalendarEntry) -> RetrievedMemoryRecord:
        return RetrievedMemoryRecord(
            memory_role="event",
            subject=entry.subject,
            predicate=entry.predicate,
            text=entry.text,
            session_id=entry.session_id,
            turn_ids=entry.turn_ids,
            timestamp=entry.timestamp,
            metadata=dict(entry.metadata),
        )


def build_sdk_contract_summary() -> dict[str, Any]:
    return {
        "runtime_class": "SparkMemorySDK",
        "write_methods": ["write_observation", "write_event"],
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
            "RetrievedMemoryRecord",
        ],
    }
