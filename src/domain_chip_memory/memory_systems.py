from __future__ import annotations

from . import memory_runtime_bindings as _runtime
from .packet_builders import (
    build_beam_ready_temporal_atom_router_packets,
    build_dual_store_event_calendar_hybrid_packets,
    build_memory_system_contract_summary,
    build_observational_temporal_memory_packets,
)

__all__ = [
    "build_beam_ready_temporal_atom_router_packets",
    "build_dual_store_event_calendar_hybrid_packets",
    "build_memory_system_contract_summary",
    "build_observational_temporal_memory_packets",
]


def __getattr__(name: str):
    return getattr(_runtime, name)


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(dir(_runtime)))
