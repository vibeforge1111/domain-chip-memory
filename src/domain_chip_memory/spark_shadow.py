from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import JsonDict
from .sdk import MemoryWriteRequest, MemoryWriteResult, SparkMemorySDK


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


def build_shadow_ingest_contract_summary() -> dict[str, Any]:
    return {
        "runtime_class": "SparkShadowIngestAdapter",
        "request_contracts": ["SparkShadowTurn", "SparkShadowIngestRequest"],
        "response_contracts": ["SparkShadowTurnTrace", "SparkShadowIngestResult"],
        "behavior": [
            "accept Builder-style conversation turns",
            "write only configured roles into SparkMemorySDK",
            "report accepted, rejected, and skipped turns with replayable traces",
        ],
    }
