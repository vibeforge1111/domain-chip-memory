from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
import re
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
    reference_turns: int
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
        promotion_policy_rows: tuple[JsonDict, ...] = (),
    ) -> None:
        self.sdk = sdk or SparkMemorySDK()
        self.writable_roles = tuple(role.strip().lower() for role in writable_roles if role.strip())
        self.promotion_policy_rows = tuple(dict(row) for row in promotion_policy_rows if isinstance(row, dict))
        self.promotion_policy_index: dict[tuple[str, str, str, str], JsonDict] = {}
        for row in self.promotion_policy_rows:
            key = self._promotion_policy_key(row)
            if key is not None:
                self.promotion_policy_index[key] = dict(row)

    def ingest_conversation(self, request: SparkShadowIngestRequest) -> SparkShadowIngestResult:
        session_id = request.session_id or request.conversation_id
        accepted_writes = 0
        rejected_writes = 0
        skipped_turns = 0
        reference_turns = 0
        turn_traces: list[SparkShadowTurnTrace] = []

        for index, turn in enumerate(request.turns):
            normalized_role = str(turn.role or "").strip().lower()
            turn_id = f"{session_id}:shadow:{index + 1}"
            if self._is_reference_turn(turn, normalized_role):
                reference_turns += 1
                turn_traces.append(
                    SparkShadowTurnTrace(
                        message_id=turn.message_id,
                        role=normalized_role,
                        action="reference_turn",
                        session_id=session_id,
                        turn_id=turn_id,
                        accepted=False,
                        trace={
                            "operation": "shadow_ingest_turn",
                            "status": "reference_turn",
                            "conversation_id": request.conversation_id,
                            "message_id": turn.message_id,
                            "role": normalized_role,
                            "content": turn.content,
                            "timestamp": turn.timestamp,
                            "source_event_type": str(turn.metadata.get("source_event_type") or ""),
                        },
                    )
                )
                continue
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
            if self._is_low_signal_residue_turn(turn, normalized_role):
                skipped_turns += 1
                turn_traces.append(
                    SparkShadowTurnTrace(
                        message_id=turn.message_id,
                        role=normalized_role,
                        action="skipped_residue",
                        session_id=session_id,
                        turn_id=turn_id,
                        accepted=False,
                        unsupported_reason="low_signal_residue",
                        trace={
                            "operation": "shadow_ingest_turn",
                            "status": "skipped_residue",
                            "conversation_id": request.conversation_id,
                            "message_id": turn.message_id,
                            "role": normalized_role,
                            "content": turn.content,
                            "timestamp": turn.timestamp,
                        },
                    )
                )
                continue
            policy_decision, policy_row = self._promotion_policy_decision(
                request.conversation_id,
                dict(turn.metadata),
            )
            if policy_decision not in (None, "allow"):
                skipped_turns += 1
                turn_traces.append(
                    SparkShadowTurnTrace(
                        message_id=turn.message_id,
                        role=normalized_role,
                        action="skipped_promotion_policy",
                        session_id=session_id,
                        turn_id=turn_id,
                        accepted=False,
                        unsupported_reason=policy_decision,
                        trace={
                            "operation": "shadow_ingest_turn",
                            "status": "skipped_promotion_policy",
                            "conversation_id": request.conversation_id,
                            "message_id": turn.message_id,
                            "role": normalized_role,
                            "policy_decision": policy_decision,
                            "policy_row": dict(policy_row) if isinstance(policy_row, dict) else None,
                            "source_backed_clone": bool(turn.metadata.get("source_backed_clone")),
                        },
                    )
                )
                continue
            unchanged_state_reason = self._unchanged_current_state_reason(turn, normalized_role)
            if unchanged_state_reason is not None:
                skipped_turns += 1
                turn_traces.append(
                    SparkShadowTurnTrace(
                        message_id=turn.message_id,
                        role=normalized_role,
                        action="skipped_unchanged_current_state",
                        session_id=session_id,
                        turn_id=turn_id,
                        accepted=False,
                        unsupported_reason=unchanged_state_reason,
                        trace={
                            "operation": "shadow_ingest_turn",
                            "status": "skipped_unchanged_current_state",
                            "conversation_id": request.conversation_id,
                            "message_id": turn.message_id,
                            "role": normalized_role,
                            "content": turn.content,
                            "timestamp": turn.timestamp,
                        },
                    )
                )
                continue

            memory_kind = str(turn.metadata.get("memory_kind", "observation")).strip().lower()
            structured_operation = str(turn.metadata.get("operation", "auto")).strip().lower() or "auto"
            write_request = MemoryWriteRequest(
                text=turn.content,
                speaker=normalized_role,
                timestamp=turn.timestamp,
                session_id=session_id,
                turn_id=turn_id,
                operation=structured_operation,
                subject=str(turn.metadata.get("subject")) if turn.metadata.get("subject") is not None else None,
                predicate=str(turn.metadata.get("predicate")) if turn.metadata.get("predicate") is not None else None,
                value=str(turn.metadata.get("value")) if turn.metadata.get("value") is not None else None,
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
            reference_turns=reference_turns,
            turn_traces=turn_traces,
            trace={
                "operation": "ingest_conversation",
                "conversation_id": request.conversation_id,
                "session_id": session_id,
                "writable_roles": list(self.writable_roles),
                "accepted_writes": accepted_writes,
                "rejected_writes": rejected_writes,
                "skipped_turns": skipped_turns,
                "reference_turns": reference_turns,
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
        total_turns = (
            ingest_result.accepted_writes
            + ingest_result.rejected_writes
            + ingest_result.skipped_turns
            + ingest_result.reference_turns
        )

        summary = {
            "accepted_writes": ingest_result.accepted_writes,
            "rejected_writes": ingest_result.rejected_writes,
            "skipped_turns": ingest_result.skipped_turns,
            "reference_turns": ingest_result.reference_turns,
            "accepted_rate": round(ingest_result.accepted_writes / total_turns, 4) if total_turns else 0.0,
            "rejected_rate": round(ingest_result.rejected_writes / total_turns, 4) if total_turns else 0.0,
            "skipped_rate": round(ingest_result.skipped_turns / total_turns, 4) if total_turns else 0.0,
            "reference_rate": round(ingest_result.reference_turns / total_turns, 4) if total_turns else 0.0,
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
                "reference_turns": ingest_result.reference_turns,
            },
            probe_results=probe_results,
            summary=summary,
            trace={
                "operation": "evaluate_ingest",
                "conversation_id": ingest_result.conversation_id,
                "session_id": ingest_result.session_id,
                "probe_count": len(probes),
                "turn_traces": [asdict(turn_trace) for turn_trace in ingest_result.turn_traces],
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
                "content": turn.content,
                "timestamp": turn.timestamp,
                "write_trace": dict(write_result.trace),
            },
        )

    def _is_reference_turn(self, turn: SparkShadowTurn, normalized_role: str) -> bool:
        source_event_type = str(turn.metadata.get("source_event_type") or "").strip().lower()
        if normalized_role == "user" and source_event_type in {
            "plugin_or_chip_influence_recorded",
            "memory_read_requested",
        }:
            return True
        if normalized_role not in self.writable_roles and source_event_type in {
            "tool_result_received",
            "memory_read_succeeded",
            "memory_read_abstained",
        }:
            return True
        return False

    def _is_low_signal_residue_turn(self, turn: SparkShadowTurn, normalized_role: str) -> bool:
        if normalized_role not in self.writable_roles:
            return False
        metadata = dict(turn.metadata)
        if self._has_structured_memory_hints(metadata):
            return False
        if self._is_metadata_backed_residue(metadata):
            return True
        normalized_text = self._normalize_residue_text(turn.content)
        if not normalized_text:
            return True
        if normalized_text.startswith("/") and len(normalized_text.split()) <= 4:
            return True
        if not re.search(r"[a-z0-9]", normalized_text):
            return True
        return normalized_text in {
            "hello",
            "hello there",
            "hi",
            "hi there",
            "hey",
            "hey there",
            "thanks",
            "thank you",
            "ok",
            "okay",
            "ok thanks",
            "okay thanks",
            "got it",
            "sounds good",
            "cool",
            "nice",
            "great",
            "awesome",
            "sure",
        }

    def _has_structured_memory_hints(self, metadata: JsonDict) -> bool:
        operation = str(metadata.get("operation") or "").strip().lower()
        if operation and operation != "auto":
            return True
        if any(str(metadata.get(key) or "").strip() for key in ("subject", "predicate", "value")):
            return True
        if str(metadata.get("memory_kind") or "").strip().lower() == "event":
            return True
        if bool(metadata.get("source_backed_clone")):
            return True
        source_event_type = str(metadata.get("source_event_type") or "").strip().lower()
        if source_event_type in {"memory_write_requested", "plugin_or_chip_influence_recorded"}:
            return True
        return False

    def _is_metadata_backed_residue(self, metadata: JsonDict) -> bool:
        keepability = str(metadata.get("keepability") or "").strip().lower()
        promotion_disposition = str(metadata.get("promotion_disposition") or "").strip().lower()
        bridge_mode = str(metadata.get("bridge_mode") or "").strip().lower()
        routing_decision = str(metadata.get("routing_decision") or "").strip().lower()
        ephemeral_keepabilities = {
            "ephemeral_context",
            "user_preference_ephemeral",
        }
        non_promotable_bridge_modes = {
            "external_autodiscovered",
        }
        non_promotable_routing_decisions = {
            "provider_fallback_chat+manual_recommended",
            "provider_execution+manual_recommended",
        }
        if keepability in ephemeral_keepabilities:
            return True
        if promotion_disposition == "not_promotable":
            return True
        if bridge_mode in non_promotable_bridge_modes:
            return True
        if routing_decision in non_promotable_routing_decisions:
            return True
        return False

    def _unchanged_current_state_reason(self, turn: SparkShadowTurn, normalized_role: str) -> str | None:
        if normalized_role not in self.writable_roles:
            return None
        metadata = dict(turn.metadata)
        memory_kind = str(metadata.get("memory_kind") or "observation").strip().lower()
        if memory_kind == "event":
            return None
        operation = str(metadata.get("operation") or "").strip().lower()
        if operation not in {"create", "update"}:
            return None
        subject = str(metadata.get("subject") or "").strip()
        predicate = str(metadata.get("predicate") or "").strip()
        value = str(metadata.get("value") or "").strip()
        if not subject or not predicate or not value:
            return None
        current_state = self.sdk.get_current_state(
            CurrentStateRequest(
                subject=subject,
                predicate=predicate,
            )
        )
        if not current_state.found:
            return None
        existing_value = self._normalize_residue_text(str(current_state.value or ""))
        incoming_value = self._normalize_residue_text(value)
        if existing_value and incoming_value and existing_value == incoming_value:
            return "unchanged_current_state"
        return None

    def _normalize_residue_text(self, text: str) -> str:
        lowered = re.sub(r"\s+", " ", str(text or "").strip().lower())
        return lowered.strip(" \t\r\n.!?,;:-_")

    def _promotion_policy_key(self, row: JsonDict) -> tuple[str, str, str, str] | None:
        target_conversation_id = str(row.get("target_conversation_id") or "").strip()
        predicate = str(row.get("predicate") or "").strip()
        source_conversation_id = str(row.get("source_conversation_id") or "").strip()
        source_message_id = str(row.get("source_message_id") or "").strip()
        if not target_conversation_id or not predicate or not source_conversation_id or not source_message_id:
            return None
        return (
            target_conversation_id,
            predicate,
            source_conversation_id,
            source_message_id,
        )

    def _promotion_policy_decision(
        self,
        conversation_id: str,
        metadata: JsonDict,
    ) -> tuple[str | None, JsonDict | None]:
        if not self.promotion_policy_index:
            return None, None
        if not bool(metadata.get("source_backed_clone")):
            return None, None
        key = (
            str(metadata.get("source_backed_target_conversation_id") or conversation_id or "").strip(),
            str(metadata.get("source_backed_predicate") or metadata.get("predicate") or "").strip(),
            str(metadata.get("source_backed_from_conversation_id") or "").strip(),
            str(metadata.get("source_backed_from_message_id") or "").strip(),
        )
        row = self.promotion_policy_index.get(key)
        if row is None:
            return "missing_policy_row", None
        decision = str(row.get("policy_decision") or "").strip().lower() or "missing_policy_decision"
        return decision, row

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
    reference_turns = 0

    for evaluation in evaluations:
        summary = dict(evaluation.summary)
        accepted_writes += int(summary.get("accepted_writes", 0) or 0)
        rejected_writes += int(summary.get("rejected_writes", 0) or 0)
        skipped_turns += int(summary.get("skipped_turns", 0) or 0)
        reference_turns += int(summary.get("reference_turns", 0) or 0)
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
                "reference_turns": int(summary.get("reference_turns", 0) or 0),
                "probe_count": len(evaluation.probe_results),
            }
        )

    total_turns = accepted_writes + rejected_writes + skipped_turns + reference_turns
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
        "reference_turns": reference_turns,
        "total_turns": total_turns,
        "accepted_rate": round(accepted_writes / total_turns, 4) if total_turns else 0.0,
        "rejected_rate": round(rejected_writes / total_turns, 4) if total_turns else 0.0,
        "skipped_rate": round(skipped_turns / total_turns, 4) if total_turns else 0.0,
        "reference_rate": round(reference_turns / total_turns, 4) if total_turns else 0.0,
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
            "optionally apply promotion-policy gating to source-backed clone writes before persistence",
            "report accepted, rejected, skipped, and reference turns with replayable traces",
            "evaluate post-ingest current-state, historical-state, and evidence probes",
            "aggregate multiple shadow evaluations into a Spark-facing quality report",
        ],
    }


def _first_present_string(mapping: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = mapping.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _first_present_object(mapping: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, dict):
            return dict(value)
    return {}


def _first_present_list(mapping: dict[str, Any], keys: tuple[str, ...]) -> list[Any]:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, list):
            return value
    return []


def normalize_builder_shadow_export_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Builder export file must contain a JSON object.")

    raw_conversations = _first_present_list(payload, ("conversations", "threads", "chats"))
    if not raw_conversations:
        raise ValueError("Builder export file must contain conversations, threads, or chats.")

    normalized_conversations: list[dict[str, Any]] = []
    for index, raw_conversation in enumerate(raw_conversations):
        if not isinstance(raw_conversation, dict):
            raise ValueError(f"Builder conversation at index {index} must be an object.")

        conversation_id = _first_present_string(
            raw_conversation,
            ("conversation_id", "conversationId", "thread_id", "threadId", "chat_id", "chatId", "id"),
        )
        if not conversation_id:
            raise ValueError(f"Builder conversation at index {index} must include a conversation id.")

        session_id = _first_present_string(raw_conversation, ("session_id", "sessionId"))
        turns_payload = _first_present_list(raw_conversation, ("turns", "messages"))
        probes_payload = _first_present_list(raw_conversation, ("probes",))
        metadata = _first_present_object(raw_conversation, ("metadata", "meta"))

        normalized_turns: list[dict[str, Any]] = []
        for turn_index, raw_turn in enumerate(turns_payload):
            if not isinstance(raw_turn, dict):
                raise ValueError(
                    f"Builder turn {turn_index} in conversation '{conversation_id}' must be an object."
                )
            message_id = _first_present_string(raw_turn, ("message_id", "messageId", "id"))
            role = _first_present_string(raw_turn, ("role", "speaker", "author_role", "authorRole"))
            content = _first_present_string(raw_turn, ("content", "text", "message", "body"))
            if not message_id:
                raise ValueError(
                    f"Builder turn {turn_index} in conversation '{conversation_id}' must include message id."
                )
            if not role:
                raise ValueError(
                    f"Builder turn {turn_index} in conversation '{conversation_id}' must include role."
                )
            if not content:
                raise ValueError(
                    f"Builder turn {turn_index} in conversation '{conversation_id}' must include content."
                )
            timestamp = _first_present_string(raw_turn, ("timestamp", "created_at", "createdAt"))
            turn_metadata = _first_present_object(raw_turn, ("metadata", "meta"))
            normalized_turns.append(
                {
                    "message_id": message_id,
                    "role": role,
                    "content": content,
                    **({"timestamp": timestamp} if timestamp else {}),
                    **({"metadata": turn_metadata} if turn_metadata else {}),
                }
            )

        normalized_probes: list[dict[str, Any]] = []
        for probe_index, raw_probe in enumerate(probes_payload):
            if not isinstance(raw_probe, dict):
                raise ValueError(
                    f"Builder probe {probe_index} in conversation '{conversation_id}' must be an object."
                )
            probe_id = _first_present_string(raw_probe, ("probe_id", "probeId", "id"))
            probe_type = _first_present_string(raw_probe, ("probe_type", "probeType", "type"))
            if not probe_id or not probe_type:
                raise ValueError(
                    f"Builder probe {probe_index} in conversation '{conversation_id}' must include probe id and probe type."
                )
            normalized_probe = {
                "probe_id": probe_id,
                "probe_type": probe_type,
            }
            for source_key, target_key in (
                (("subject",), "subject"),
                (("predicate",), "predicate"),
                (("query",), "query"),
                (("as_of", "asOf"), "as_of"),
                (("expected_value", "expectedValue"), "expected_value"),
            ):
                value = _first_present_string(raw_probe, source_key)
                if value:
                    normalized_probe[target_key] = value
            min_results = raw_probe.get("min_results", raw_probe.get("minResults"))
            if min_results is not None:
                normalized_probe["min_results"] = int(min_results)
            normalized_probes.append(normalized_probe)

        normalized_conversation = {
            "conversation_id": conversation_id,
            "turns": normalized_turns,
        }
        if session_id:
            normalized_conversation["session_id"] = session_id
        if metadata:
            normalized_conversation["metadata"] = metadata
        if normalized_probes:
            normalized_conversation["probes"] = normalized_probes
        normalized_conversations.append(normalized_conversation)

    normalized_payload = {"conversations": normalized_conversations}
    writable_roles = payload.get("writable_roles", payload.get("writableRoles"))
    if isinstance(writable_roles, list):
        normalized_payload["writable_roles"] = [str(item) for item in writable_roles]
    return normalized_payload


def _telegram_message_text(message: dict[str, Any]) -> str | None:
    for key in ("text", "caption"):
        value = message.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _telegram_message_timestamp(message: dict[str, Any]) -> str | None:
    date_value = message.get("date")
    if isinstance(date_value, int):
        from datetime import datetime, timezone

        return datetime.fromtimestamp(date_value, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if date_value is None:
        return None
    text = str(date_value).strip()
    return text or None


def normalize_telegram_bot_export_payload(payload: Any) -> dict[str, Any]:
    updates: list[Any]
    if isinstance(payload, list):
        updates = payload
    elif isinstance(payload, dict):
        raw_updates = _first_present_list(payload, ("result", "updates", "items", "messages"))
        if raw_updates:
            updates = raw_updates
        elif any(key in payload for key in ("message", "edited_message", "channel_post", "edited_channel_post", "callback_query")):
            updates = [payload]
        else:
            raise ValueError("Telegram export file must contain a list of updates, a result/updates array, or a Telegram update object.")
    else:
        raise ValueError("Telegram export file must contain a JSON object or list.")

    grouped: dict[str, dict[str, Any]] = {}
    for index, raw_update in enumerate(updates):
        if not isinstance(raw_update, dict):
            raise ValueError(f"Telegram update at index {index} must be an object.")

        update_id = _first_present_string(raw_update, ("update_id", "updateId", "id")) or f"update-{index + 1}"
        callback_query = raw_update.get("callback_query")
        message: dict[str, Any] | None = None
        sender: dict[str, Any] = {}
        text: str | None = None
        if isinstance(callback_query, dict):
            callback_message = callback_query.get("message")
            if isinstance(callback_message, dict):
                message = callback_message
            sender = callback_query.get("from") if isinstance(callback_query.get("from"), dict) else {}
            text = _first_present_string(callback_query, ("data",))
            if not text and isinstance(message, dict):
                text = _telegram_message_text(message)
        else:
            for key in ("message", "edited_message", "channel_post", "edited_channel_post"):
                candidate = raw_update.get(key)
                if isinstance(candidate, dict):
                    message = candidate
                    break
            if isinstance(message, dict):
                sender = message.get("from") if isinstance(message.get("from"), dict) else {}
                text = _telegram_message_text(message)

        if not isinstance(message, dict):
            continue

        chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
        chat_id = _first_present_string(chat, ("id",))
        if not chat_id:
            chat_id = f"telegram-update-{update_id}"
        thread_id = _first_present_string(message, ("message_thread_id", "messageThreadId"))
        conversation_id = f"telegram-chat-{chat_id}"
        if thread_id:
            conversation_id = f"{conversation_id}-thread-{thread_id}"
        session_id = conversation_id
        if conversation_id not in grouped:
            conversation_metadata: dict[str, Any] = {
                "source": "telegram",
                "telegram_chat_id": chat_id,
            }
            chat_title = _first_present_string(chat, ("title", "username", "first_name"))
            chat_type = _first_present_string(chat, ("type",))
            if chat_title:
                conversation_metadata["telegram_chat_label"] = chat_title
            if chat_type:
                conversation_metadata["telegram_chat_type"] = chat_type
            grouped[conversation_id] = {
                "conversation_id": conversation_id,
                "session_id": session_id,
                "metadata": conversation_metadata,
                "turns": [],
            }

        message_id = _first_present_string(message, ("message_id", "messageId", "id")) or update_id
        role = "assistant" if str(sender.get("is_bot", False)).lower() == "true" or sender.get("is_bot") is True else "user"
        if not text:
            continue
        turn_metadata: dict[str, Any] = {
            "source": "telegram",
            "telegram_update_id": update_id,
            "telegram_chat_id": chat_id,
            "telegram_message_id": message_id,
        }
        sender_id = _first_present_string(sender, ("id",))
        sender_username = _first_present_string(sender, ("username",))
        sender_name = _first_present_string(sender, ("first_name",))
        if sender_id:
            turn_metadata["telegram_sender_id"] = sender_id
        if sender_username:
            turn_metadata["telegram_sender_username"] = sender_username
        if sender_name:
            turn_metadata["telegram_sender_name"] = sender_name
        if thread_id:
            turn_metadata["telegram_thread_id"] = thread_id
        grouped[conversation_id]["turns"].append(
            {
                "message_id": str(message_id),
                "role": role,
                "content": text,
                **({"timestamp": _telegram_message_timestamp(message)} if _telegram_message_timestamp(message) else {}),
                "metadata": turn_metadata,
            }
        )

    normalized_conversations = [conversation for conversation in grouped.values() if conversation.get("turns")]
    if not normalized_conversations:
        raise ValueError("Telegram export file did not contain any text-bearing messages.")
    return {
        "writable_roles": ["user"],
        "conversations": normalized_conversations,
    }


def build_builder_shadow_adapter_contract_summary() -> dict[str, Any]:
    return {
        "layer_name": "SparkBuilderShadowAdapter",
        "input_root_aliases": ["conversations", "threads", "chats"],
        "conversation_id_aliases": [
            "conversation_id",
            "conversationId",
            "thread_id",
            "threadId",
            "chat_id",
            "chatId",
            "id",
        ],
        "turn_collection_aliases": ["turns", "messages"],
        "turn_field_aliases": {
            "message_id": ["message_id", "messageId", "id"],
            "role": ["role", "speaker", "author_role", "authorRole"],
            "content": ["content", "text", "message", "body"],
            "timestamp": ["timestamp", "created_at", "createdAt"],
            "metadata": ["metadata", "meta"],
        },
        "probe_field_aliases": {
            "probe_id": ["probe_id", "probeId", "id"],
            "probe_type": ["probe_type", "probeType", "type"],
            "as_of": ["as_of", "asOf"],
            "expected_value": ["expected_value", "expectedValue"],
            "min_results": ["min_results", "minResults"],
        },
        "output_shape": "Spark shadow replay JSON compatible with validate-spark-shadow-replay and run-spark-shadow-report",
    }


def build_telegram_shadow_adapter_contract_summary() -> dict[str, Any]:
    return {
        "layer_name": "SparkTelegramShadowAdapter",
        "input_root_aliases": ["result", "updates", "items", "messages"],
        "supported_update_keys": [
            "message",
            "edited_message",
            "channel_post",
            "edited_channel_post",
            "callback_query",
        ],
        "message_text_fields": ["text", "caption", "callback_query.data"],
        "grouping": "messages are grouped by chat.id and optional message_thread_id",
        "role_mapping": {
            "telegram from.is_bot = true": "assistant",
            "telegram from.is_bot = false": "user",
        },
        "output_shape": "Spark shadow replay JSON compatible with validate-spark-shadow-replay and run-spark-shadow-report",
    }


def validate_shadow_replay_payload(payload: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    conversation_count = 0
    turn_count = 0
    probe_count = 0

    if not isinstance(payload, dict):
        return {
            "valid": False,
            "errors": ["Shadow replay file must contain a JSON object."],
            "warnings": [],
            "conversation_count": 0,
            "turn_count": 0,
            "probe_count": 0,
        }

    writable_roles = payload.get("writable_roles")
    if writable_roles is not None and not isinstance(writable_roles, list):
        errors.append("writable_roles must be a list when provided.")

    raw_conversations = payload.get("conversations")
    if not isinstance(raw_conversations, list):
        return {
            "valid": False,
            "errors": ["Shadow replay file must contain a conversations list."],
            "warnings": warnings,
            "conversation_count": 0,
            "turn_count": 0,
            "probe_count": 0,
        }

    supported_probe_types = {"current_state", "historical_state", "evidence"}
    for index, item in enumerate(raw_conversations):
        conversation_count += 1
        if not isinstance(item, dict):
            errors.append(f"Conversation at index {index} must be an object.")
            continue

        conversation_id = str(item.get("conversation_id", "")).strip()
        if not conversation_id:
            errors.append(f"Conversation at index {index} must include conversation_id.")

        turns = item.get("turns", [])
        if not isinstance(turns, list):
            errors.append(f"Conversation '{conversation_id or index}' must contain a turns list.")
            turns = []
        if not turns:
            warnings.append(f"Conversation '{conversation_id or index}' has no turns.")
        for turn_index, turn in enumerate(turns):
            turn_count += 1
            if not isinstance(turn, dict):
                errors.append(f"Turn {turn_index} in conversation '{conversation_id or index}' must be an object.")
                continue
            if not str(turn.get("message_id", "")).strip():
                errors.append(f"Turn {turn_index} in conversation '{conversation_id or index}' must include message_id.")
            if not str(turn.get("role", "")).strip():
                errors.append(f"Turn {turn_index} in conversation '{conversation_id or index}' must include role.")
            if not str(turn.get("content", "")).strip():
                errors.append(f"Turn {turn_index} in conversation '{conversation_id or index}' must include content.")
            metadata = turn.get("metadata", {})
            if metadata is not None and not isinstance(metadata, dict):
                errors.append(f"Turn {turn_index} in conversation '{conversation_id or index}' must use object metadata.")

        probes = item.get("probes", [])
        if not isinstance(probes, list):
            errors.append(f"Conversation '{conversation_id or index}' must contain a probes list when provided.")
            probes = []
        for probe_index, probe in enumerate(probes):
            probe_count += 1
            if not isinstance(probe, dict):
                errors.append(f"Probe {probe_index} in conversation '{conversation_id or index}' must be an object.")
                continue
            probe_type = str(probe.get("probe_type", "")).strip()
            if probe_type not in supported_probe_types:
                errors.append(
                    f"Probe {probe_index} in conversation '{conversation_id or index}' has unsupported probe_type '{probe_type}'."
                )
                continue
            if not str(probe.get("probe_id", "")).strip():
                errors.append(f"Probe {probe_index} in conversation '{conversation_id or index}' must include probe_id.")
            if probe_type in {"current_state", "historical_state"}:
                if not str(probe.get("subject", "")).strip():
                    errors.append(
                        f"Probe {probe_index} in conversation '{conversation_id or index}' must include subject."
                    )
                if not str(probe.get("predicate", "")).strip():
                    errors.append(
                        f"Probe {probe_index} in conversation '{conversation_id or index}' must include predicate."
                    )
            if probe_type == "historical_state" and not str(probe.get("as_of", "")).strip():
                errors.append(f"Probe {probe_index} in conversation '{conversation_id or index}' must include as_of.")
            if probe_type == "evidence":
                has_query = bool(str(probe.get("query", "")).strip())
                has_subject = bool(str(probe.get("subject", "")).strip())
                has_predicate = bool(str(probe.get("predicate", "")).strip())
                if not (has_query or has_subject or has_predicate):
                    errors.append(
                        f"Probe {probe_index} in conversation '{conversation_id or index}' must include query or subject/predicate."
                    )
            min_results = probe.get("min_results", 1)
            try:
                if int(min_results) < 1:
                    errors.append(
                        f"Probe {probe_index} in conversation '{conversation_id or index}' must use min_results >= 1."
                    )
            except (TypeError, ValueError):
                errors.append(
                    f"Probe {probe_index} in conversation '{conversation_id or index}' must use an integer min_results."
                )

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "conversation_count": conversation_count,
        "turn_count": turn_count,
        "probe_count": probe_count,
    }


def build_shadow_replay_contract_summary() -> dict[str, Any]:
    return {
        "single_file_shape": {
            "root_type": "object",
            "required_fields": ["conversations"],
            "optional_fields": ["writable_roles"],
            "conversation_fields": [
                "conversation_id",
                "turns",
                "probes",
                "session_id",
                "metadata",
            ],
            "turn_fields": [
                "message_id",
                "role",
                "content",
                "timestamp",
                "metadata",
            ],
            "probe_fields": [
                "probe_id",
                "probe_type",
                "subject",
                "predicate",
                "query",
                "as_of",
                "expected_value",
                "min_results",
            ],
        },
        "batch_shape": {
            "input": "directory of single-file replay JSON payloads",
            "default_glob": "*.json",
            "per_file_summary_fields": [
                "file",
                "run_count",
                "summary",
            ],
        },
        "supported_probe_types": [
            "current_state",
            "historical_state",
            "evidence",
        ],
        "output_fields": [
            "evaluations",
            "report",
            "source_files",
            "source_reports",
        ],
        "validation_entrypoints": [
            "validate_shadow_replay_payload(...)",
            "python -m domain_chip_memory.cli validate-spark-shadow-replay <file>",
            "python -m domain_chip_memory.cli validate-spark-shadow-replay-batch <dir>",
        ],
        "notes": [
            "Single-file replay emits evaluations and one aggregate report.",
            "Batch replay adds source_files and source_reports on top of the same aggregate report format.",
        ],
    }
