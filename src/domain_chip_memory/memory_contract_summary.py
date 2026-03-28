from __future__ import annotations

from typing import Any


def build_memory_system_contract_summary() -> dict[str, Any]:
    return {
        "candidate_memory_systems": [
            {
                "system_name": "beam_temporal_atom_router",
                "entrypoint": "build_beam_ready_temporal_atom_router_packets",
                "behavior": "Extract temporal atoms, apply recency-aware routing, then rehydrate the strongest source sessions.",
            },
            {
                "system_name": "observational_temporal_memory",
                "entrypoint": "build_observational_temporal_memory_packets",
                "behavior": "Build a stable observation log, reflect it into a compressed memory window, and answer from that stable context.",
            },
            {
                "system_name": "dual_store_event_calendar_hybrid",
                "entrypoint": "build_dual_store_event_calendar_hybrid_packets",
                "behavior": "Combine a stable observation window with an explicit event calendar and answer from the strongest hybrid signal.",
            },
        ],
        "memory_contracts": [
            "AnswerCandidate",
            "MemoryAtom",
            "ObservationEntry",
            "EventCalendarEntry",
            "RetrievedContextItem",
            "BaselinePromptPacket",
        ],
    }
