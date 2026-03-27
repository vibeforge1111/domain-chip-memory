from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .contracts import JsonDict
from .sdk import (
    CurrentStateRequest,
    EvidenceRetrievalRequest,
    HistoricalStateRequest,
    MemoryLookupResult,
    MemoryRetrievalResult,
    MemoryWriteRequest,
    MemoryWriteResult,
    SparkMemorySDK,
)


@dataclass(frozen=True)
class SparkShadowTurn:
    message_id: str
    role: str
    content: str
    timestamp: str | None = None
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class SparkShadowIngestRequest:
    conversation_id: str
    turns: list[SparkShadowTurn]
    session_id: str | None = None
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class SparkShadowTurnTrace:
    message_id: str
    role: str
    action: str
    session_id: str
    turn_id: str
    accepted: bool
    unsupported_reason: str | None = None
    trace: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class SparkShadowIngestResult:
    conversation_id: str
    session_id: str
    accepted_writes: int
    rejected_writes: int
    skipped_turns: int
    turn_traces: list[SparkShadowTurnTrace]
    trace: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class SparkShadowProbe:
    probe_id: str
    probe_type: str
    subject: str | None = None
    predicate: str | None = None
    query: str | None = None
    as_of: str | None = None
    expected_value: str | None = None
    min_results: int = 1


@dataclass(frozen=True)
class SparkShadowProbeResult:
    probe_id: str
    probe_type: str
    hit: bool
    matched_expected: bool | None
    returned_count: int
    memory_role: str
    trace: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class SparkShadowEvaluationResult:
    conversation_id: str
    session_id: str
    ingest_summary: JsonDict
    probe_results: list[SparkShadowProbeResult]
    summary: JsonDict
    trace: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class SparkShadowReport:
    run_count: int
    summary: JsonDict
    conversation_rows: list[JsonDict]
    trace: JsonDict = field(default_factory=dict)


class SparkShadowIngestAdapter:
    def __init__(
        self,
        sdk: SparkMemorySDK | None = None,
        *,
        writable_roles: tuple[str, ...] = ("user",),
    ) -> None:
        self.sdk = sdk or SparkMemorySDK()
        self.writable_roles = tuple(role.strip().lower() for role in writable_roles if role.strip())

    def ingest_conversation(self, request: SparkShadowIngestRequest) -> SparkShadowIngestResult:
        session_id = request.session_id or request.conversation_id
        accepted_writes = 0
        rejected_writes = 0
        skipped_turns = 0
        turn_traces: list[SparkShadowTurnTrace] = []

        for index, turn in enumerate(request.turns):
            normalized_role = str(turn.role or "").strip().lower()
            turn_id = f"{session_id}:shadow:{index + 1}"
            if normalized_role not in self.writable_roles:
                skipped_turns += 1
                turn_traces.append(
                    SparkShadowTurnTrace(
                        message_id=turn.message_id,
                        role=normalized_role,
                        action="skipped_role",
                        session_id=session_id,
                        turn_id=turn_id,
                        accepted=False,
                        trace={
                            "operation": "shadow_ingest_turn",
                            "status": "skipped_role",
                            "conversation_id": request.conversation_id,
                            "message_id": turn.message_id,
                            "role": normalized_role,
                        },
                    )
                )
                continue

            memory_kind = str(turn.metadata.get("memory_kind", "observation")).strip().lower()
            write_request = MemoryWriteRequest(
                text=turn.content,
                speaker=normalized_role,
                timestamp=turn.timestamp,
                session_id=session_id,
                turn_id=turn_id,
                metadata={
                    "conversation_id": request.conversation_id,
                    "message_id": turn.message_id,
                    "shadow_ingest": True,
                    **dict(request.metadata),
                    **dict(turn.metadata),
                },
            )
            write_result = (
                self.sdk.write_event(write_request) if memory_kind == "event" else self.sdk.write_observation(write_request)
            )
            if write_result.accepted:
                accepted_writes += 1
                action = "accepted_write"
            else:
                rejected_writes += 1
                action = "rejected_write"
            turn_traces.append(self._build_turn_trace(turn, normalized_role, action, write_result))

        return SparkShadowIngestResult(
            conversation_id=request.conversation_id,
            session_id=session_id,
            accepted_writes=accepted_writes,
            rejected_writes=rejected_writes,
            skipped_turns=skipped_turns,
            turn_traces=turn_traces,
            trace={
                "operation": "ingest_conversation",
                "conversation_id": request.conversation_id,
                "session_id": session_id,
                "writable_roles": list(self.writable_roles),
                "accepted_writes": accepted_writes,
                "rejected_writes": rejected_writes,
                "skipped_turns": skipped_turns,
            },
        )

    def evaluate_ingest(
        self,
        ingest_result: SparkShadowIngestResult,
        *,
        probes: list[SparkShadowProbe],
    ) -> SparkShadowEvaluationResult:
        unsupported_reason_counts: dict[str, int] = {}
        for turn_trace in ingest_result.turn_traces:
            reason = str(turn_trace.unsupported_reason or "").strip()
            if reason:
                unsupported_reason_counts[reason] = unsupported_reason_counts.get(reason, 0) + 1

        probe_results = [self._evaluate_probe(probe) for probe in probes]
        current_state_total = sum(1 for probe in probes if probe.probe_type == "current_state")
        current_state_hits = sum(
            1 for result in probe_results if result.probe_type == "current_state" and result.hit
        )
        evidence_total = sum(1 for probe in probes if probe.probe_type == "evidence")
        evidence_hits = sum(1 for result in probe_results if result.probe_type == "evidence" and result.hit)
        historical_total = sum(1 for probe in probes if probe.probe_type == "historical_state")
        historical_hits = sum(
            1 for result in probe_results if result.probe_type == "historical_state" and result.hit
        )
        total_turns = ingest_result.accepted_writes + ingest_result.rejected_writes + ingest_result.skipped_turns

        summary = {
            "accepted_writes": ingest_result.accepted_writes,
            "rejected_writes": ingest_result.rejected_writes,
            "skipped_turns": ingest_result.skipped_turns,
            "accepted_rate": round(ingest_result.accepted_writes / total_turns, 4) if total_turns else 0.0,
            "rejected_rate": round(ingest_result.rejected_writes / total_turns, 4) if total_turns else 0.0,
            "skipped_rate": round(ingest_result.skipped_turns / total_turns, 4) if total_turns else 0.0,
            "unsupported_reasons": [
                {"reason": reason, "count": unsupported_reason_counts[reason]}
                for reason in sorted(unsupported_reason_counts)
            ],
            "current_state_hit_rate": {
                "hits": current_state_hits,
                "total": current_state_total,
                "rate": round(current_state_hits / current_state_total, 4) if current_state_total else 0.0,
            },
            "historical_state_hit_rate": {
                "hits": historical_hits,
                "total": historical_total,
                "rate": round(historical_hits / historical_total, 4) if historical_total else 0.0,
            },
            "evidence_hit_rate": {
                "hits": evidence_hits,
                "total": evidence_total,
                "rate": round(evidence_hits / evidence_total, 4) if evidence_total else 0.0,
            },
        }
        return SparkShadowEvaluationResult(
            conversation_id=ingest_result.conversation_id,
            session_id=ingest_result.session_id,
            ingest_summary={
                "accepted_writes": ingest_result.accepted_writes,
                "rejected_writes": ingest_result.rejected_writes,
                "skipped_turns": ingest_result.skipped_turns,
            },
            probe_results=probe_results,
            summary=summary,
            trace={
                "operation": "evaluate_ingest",
                "conversation_id": ingest_result.conversation_id,
                "session_id": ingest_result.session_id,
                "probe_count": len(probes),
            },
        )

    def _build_turn_trace(
        self,
        turn: SparkShadowTurn,
        normalized_role: str,
        action: str,
        write_result: MemoryWriteResult,
    ) -> SparkShadowTurnTrace:
        return SparkShadowTurnTrace(
            message_id=turn.message_id,
            role=normalized_role,
            action=action,
            session_id=write_result.session_id,
            turn_id=write_result.turn_id,
            accepted=write_result.accepted,
            unsupported_reason=write_result.unsupported_reason,
            trace={
                "operation": "shadow_ingest_turn",
                "status": action,
                "message_id": turn.message_id,
                "role": normalized_role,
                "write_trace": dict(write_result.trace),
            },
        )

    def _evaluate_probe(self, probe: SparkShadowProbe) -> SparkShadowProbeResult:
        if probe.probe_type == "current_state":
            result = self.sdk.get_current_state(
                CurrentStateRequest(
                    subject=str(probe.subject or ""),
                    predicate=str(probe.predicate or ""),
                )
            )
            return self._lookup_probe_result(probe, result)
        if probe.probe_type == "historical_state":
            result = self.sdk.get_historical_state(
                HistoricalStateRequest(
                    subject=str(probe.subject or ""),
                    predicate=str(probe.predicate or ""),
                    as_of=str(probe.as_of or ""),
                )
            )
            return self._lookup_probe_result(probe, result)
        if probe.probe_type == "evidence":
            result = self.sdk.retrieve_evidence(
                EvidenceRetrievalRequest(
                    query=probe.query,
                    subject=probe.subject,
                    predicate=probe.predicate,
                    limit=max(probe.min_results, 1),
                )
            )
            return self._retrieval_probe_result(probe, result)
        return SparkShadowProbeResult(
            probe_id=probe.probe_id,
            probe_type=probe.probe_type,
            hit=False,
            matched_expected=None,
            returned_count=0,
            memory_role="unknown",
            trace={
                "operation": "evaluate_probe",
                "status": "unsupported_probe_type",
                "probe_type": probe.probe_type,
            },
        )

    def _lookup_probe_result(
        self,
        probe: SparkShadowProbe,
        result: MemoryLookupResult,
    ) -> SparkShadowProbeResult:
        expected_value = str(probe.expected_value or "").strip().lower()
        actual_value = str(result.value or "").strip().lower()
        matched_expected = None
        if expected_value:
            matched_expected = actual_value == expected_value
        return SparkShadowProbeResult(
            probe_id=probe.probe_id,
            probe_type=probe.probe_type,
            hit=result.found,
            matched_expected=matched_expected,
            returned_count=len(result.provenance),
            memory_role=result.memory_role,
            trace=dict(result.trace),
        )

    def _retrieval_probe_result(
        self,
        probe: SparkShadowProbe,
        result: MemoryRetrievalResult,
    ) -> SparkShadowProbeResult:
        matched_expected = None
        expected_value = str(probe.expected_value or "").strip().lower()
        if expected_value:
            matched_expected = any(expected_value in item.text.lower() for item in result.items)
        memory_role = result.items[0].memory_role if result.items else "unknown"
        return SparkShadowProbeResult(
            probe_id=probe.probe_id,
            probe_type=probe.probe_type,
            hit=len(result.items) >= max(probe.min_results, 1),
            matched_expected=matched_expected,
            returned_count=len(result.items),
            memory_role=memory_role,
            trace=dict(result.trace),
        )


def build_shadow_report(evaluations: list[SparkShadowEvaluationResult]) -> SparkShadowReport:
    unsupported_reason_counts: Counter[str] = Counter()
    probe_total_by_type: Counter[str] = Counter()
    probe_hits_by_type: Counter[str] = Counter()
    expected_total_by_type: Counter[str] = Counter()
    expected_matches_by_type: Counter[str] = Counter()
    memory_role_counts: Counter[str] = Counter()
    conversation_rows: list[JsonDict] = []
    accepted_writes = 0
    rejected_writes = 0
    skipped_turns = 0

    for evaluation in evaluations:
        summary = dict(evaluation.summary)
        accepted_writes += int(summary.get("accepted_writes", 0) or 0)
        rejected_writes += int(summary.get("rejected_writes", 0) or 0)
        skipped_turns += int(summary.get("skipped_turns", 0) or 0)
        for row in summary.get("unsupported_reasons", []):
            reason = str(row.get("reason", "") or "").strip()
            count = int(row.get("count", 0) or 0)
            if reason and count > 0:
                unsupported_reason_counts[reason] += count
        for result in evaluation.probe_results:
            probe_type = str(result.probe_type or "").strip() or "unknown"
            probe_total_by_type[probe_type] += 1
            if result.hit:
                probe_hits_by_type[probe_type] += 1
            if result.matched_expected is not None:
                expected_total_by_type[probe_type] += 1
                if result.matched_expected:
                    expected_matches_by_type[probe_type] += 1
            memory_role = str(result.memory_role or "").strip()
            if memory_role:
                memory_role_counts[memory_role] += 1
        conversation_rows.append(
            {
                "conversation_id": evaluation.conversation_id,
                "session_id": evaluation.session_id,
                "accepted_writes": int(summary.get("accepted_writes", 0) or 0),
                "rejected_writes": int(summary.get("rejected_writes", 0) or 0),
                "skipped_turns": int(summary.get("skipped_turns", 0) or 0),
                "probe_count": len(evaluation.probe_results),
            }
        )

    total_turns = accepted_writes + rejected_writes + skipped_turns
    probe_rows: list[JsonDict] = []
    for probe_type in sorted(probe_total_by_type):
        expected_total = expected_total_by_type[probe_type]
        probe_rows.append(
            {
                "probe_type": probe_type,
                "hits": probe_hits_by_type[probe_type],
                "total": probe_total_by_type[probe_type],
                "hit_rate": round(probe_hits_by_type[probe_type] / probe_total_by_type[probe_type], 4)
                if probe_total_by_type[probe_type]
                else 0.0,
                "expected_matches": expected_matches_by_type[probe_type],
                "expected_total": expected_total,
                "expected_match_rate": round(expected_matches_by_type[probe_type] / expected_total, 4)
                if expected_total
                else 0.0,
            }
        )

    summary: JsonDict = {
        "accepted_writes": accepted_writes,
        "rejected_writes": rejected_writes,
        "skipped_turns": skipped_turns,
        "total_turns": total_turns,
        "accepted_rate": round(accepted_writes / total_turns, 4) if total_turns else 0.0,
        "rejected_rate": round(rejected_writes / total_turns, 4) if total_turns else 0.0,
        "skipped_rate": round(skipped_turns / total_turns, 4) if total_turns else 0.0,
        "unsupported_reasons": [
            {"reason": reason, "count": unsupported_reason_counts[reason]}
            for reason in sorted(unsupported_reason_counts)
        ],
        "probe_rows": probe_rows,
        "memory_roles": [
            {"memory_role": role, "count": memory_role_counts[role]}
            for role in sorted(memory_role_counts)
        ],
    }
    return SparkShadowReport(
        run_count=len(evaluations),
        summary=summary,
        conversation_rows=conversation_rows,
        trace={
            "operation": "build_shadow_report",
            "run_count": len(evaluations),
        },
    )


def build_shadow_ingest_contract_summary() -> dict[str, Any]:
    return {
        "runtime_class": "SparkShadowIngestAdapter",
        "request_contracts": ["SparkShadowTurn", "SparkShadowIngestRequest", "SparkShadowProbe"],
        "response_contracts": [
            "SparkShadowTurnTrace",
            "SparkShadowIngestResult",
            "SparkShadowProbeResult",
            "SparkShadowEvaluationResult",
            "SparkShadowReport",
        ],
        "behavior": [
            "accept Builder-style conversation turns",
            "write only configured roles into SparkMemorySDK",
            "report accepted, rejected, and skipped turns with replayable traces",
            "evaluate post-ingest current-state, historical-state, and evidence probes",
            "aggregate multiple shadow evaluations into a Spark-facing quality report",
        ],
    }
