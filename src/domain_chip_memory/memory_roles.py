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
    "temporal_atom_router": "aggregate",
}


def source_memory_role(source: str | None) -> MemoryRole:
    cleaned = str(source or "").strip()
    if cleaned in _SOURCE_MEMORY_ROLE:
        return _SOURCE_MEMORY_ROLE[cast(AnswerCandidateSource, cleaned)]
    return "unknown"


def strategy_memory_role(strategy: str | None) -> MemoryRole:
    cleaned = str(strategy or "").strip()
    return _STRATEGY_MEMORY_ROLE.get(cleaned, "unknown")
