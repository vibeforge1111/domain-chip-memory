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
                "system_name": "contradiction_aware_profile_memory",
                "entrypoint": "build_contradiction_aware_profile_memory_packets",
                "behavior": "Separate profile-style current state from conflict evidence and answer contradiction questions with clarification when opposing claims are both supported.",
            },
            {
                "system_name": "dual_store_event_calendar_hybrid",
                "entrypoint": "build_dual_store_event_calendar_hybrid_packets",
                "behavior": "Combine a stable observation window with an explicit event calendar and answer from the strongest hybrid signal.",
            },
            {
                "system_name": "stateful_event_reconstruction",
                "entrypoint": "build_stateful_event_reconstruction_packets",
                "behavior": "Rehydrate scored event-calendar entries back into evidence, rebuild current state from events plus observations, and route temporal or summary questions through reconstruction-first answer selection.",
            },
            {
                "system_name": "summary_synthesis_memory",
                "entrypoint": "build_summary_synthesis_memory_packets",
                "behavior": "Promote concise synthesized support above raw turn replay, then answer direct value, update, and summary questions through synthesis-first routing.",
            },
            {
                "system_name": "typed_state_update_memory",
                "entrypoint": "build_typed_state_update_memory_packets",
                "behavior": "Compact state updates into canonical surfaces, compute current state over merged updates, and answer from typed state memory before raw passage replay.",
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
