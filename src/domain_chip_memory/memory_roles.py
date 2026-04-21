from __future__ import annotations

from typing import cast

from .contracts import AnswerCandidateSource, MemoryRole


_SOURCE_MEMORY_ROLE: dict[AnswerCandidateSource, MemoryRole] = {
    "unknown": "unknown",
    "current_state_memory": "current_state",
    "current_state_deletion": "state_deletion",
    "evidence_memory": "structured_evidence",
    "belief_memory": "belief",
    "event_calendar": "event",
    "aggregate_memory": "aggregate",
    "referential_ambiguity": "ambiguity",
    "temporal_ambiguity": "ambiguity",
    "temporal_atom_router": "aggregate",
}

_STRATEGY_MEMORY_ROLE: dict[str, MemoryRole] = {
    "full_context": "episodic",
    "lexical_session_overlap": "episodic",
    "observation_log": "episodic",
    "hybrid_observation_window": "episodic",
    "source_rehydration": "episodic",
    "topic_continuity": "episodic",
    "evidence_memory": "structured_evidence",
    "profile_memory": "current_state",
    "current_state_memory": "current_state",
    "belief_memory": "belief",
    "contradiction_memory": "ambiguity",
    "event_calendar": "event",
    "aggregate_memory": "aggregate",
    "summary_synthesis_memory": "aggregate",
    "temporal_atom_router": "aggregate",
}

_CANONICAL_MEMORY_ROLE: dict[MemoryRole, str] = {
    "unknown": "unknown",
    "episodic": "raw_episode",
    "current_state": "current_state",
    "state_deletion": "state_deletion",
    "structured_evidence": "structured_evidence",
    "belief": "belief",
    "event": "event",
    "aggregate": "aggregate",
    "ambiguity": "ambiguity",
}

_MEMORY_ROLE_DESCRIPTION: dict[MemoryRole, str] = {
    "unknown": "No supported memory role was available for the request.",
    "episodic": "Raw conversational or source-grounded episode material retained for replay and rehydration.",
    "current_state": "Latest supported truth for a mutable fact or profile slot.",
    "state_deletion": "Deletion tombstone showing that a current-state fact was explicitly removed.",
    "structured_evidence": "Extracted evidence item with provenance back to source turns.",
    "belief": "Derived reflection or synthesized belief rather than direct source truth.",
    "event": "Temporal event memory such as plans, commitments, meetings, trips, or deadlines.",
    "aggregate": "Merged or synthesized retrieval context assembled from multiple memory units.",
    "ambiguity": "A retrieval state where memory evidence is conflicting or too ambiguous to trust directly.",
}

_SDK_RUNTIME_MEMORY_ROLE_ORDER: tuple[MemoryRole, ...] = (
    "unknown",
    "episodic",
    "current_state",
    "state_deletion",
    "structured_evidence",
    "belief",
    "event",
    "aggregate",
    "ambiguity",
)


def source_memory_role(source: str | None) -> MemoryRole:
    cleaned = str(source or "").strip()
    if cleaned in _SOURCE_MEMORY_ROLE:
        return _SOURCE_MEMORY_ROLE[cast(AnswerCandidateSource, cleaned)]
    return "unknown"


def strategy_memory_role(strategy: str | None) -> MemoryRole:
    cleaned = str(strategy or "").strip()
    return _STRATEGY_MEMORY_ROLE.get(cleaned, "unknown")


def canonical_memory_role(role: MemoryRole | str | None) -> str:
    cleaned = str(role or "").strip()
    if cleaned in _CANONICAL_MEMORY_ROLE:
        return _CANONICAL_MEMORY_ROLE[cast(MemoryRole, cleaned)]
    return "unknown"


def describe_memory_role(role: MemoryRole | str | None) -> dict[str, str]:
    cleaned = str(role or "").strip()
    runtime_role = cast(MemoryRole, cleaned) if cleaned in _CANONICAL_MEMORY_ROLE else "unknown"
    return {
        "runtime_role": runtime_role,
        "canonical_role": canonical_memory_role(runtime_role),
        "description": _MEMORY_ROLE_DESCRIPTION[runtime_role],
    }


def sdk_memory_role_contracts() -> list[dict[str, str]]:
    return [describe_memory_role(role) for role in _SDK_RUNTIME_MEMORY_ROLE_ORDER]
